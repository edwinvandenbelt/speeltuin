"""buildings_fetcher.core — haalt OSM-gebouwen op via de Overpass API.

Publieke API
------------
    fetch_buildings_overpass(bbox, tile_cache_dir, fallback_tile_cache_dir)
        Hoofdfunctie: verdeelt het gebied in tegels, raadpleegt de cache-hiërarchie
        en doet zo nodig Overpass-verzoeken. Geeft een GeoJSON FeatureCollection terug.

    elements_to_building_features(elements)
        Converteert ruwe Overpass-elementen naar GeoJSON Feature-dicts.

Constanten
----------
    BUILDINGS_QUERY_VER   — verhoog dit getal om alle caches te invalideren.
    OVERPASS_GRID         — N×N tegels per gebied.
"""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Overpass-endpoint uit .env (server.py laadt .env bij import); default = publiek.
OVERPASS_URL: str = os.environ.get(
    "OVERPASS_URL", "https://overpass-api.de/api/interpreter"
)

# ---------------------------------------------------------------------------
# Constanten
# ---------------------------------------------------------------------------

# Verhoog dit getal als de Overpass-query of het dataformaat wijzigt.
# Bestaande cachebestanden met een lager versienummer worden automatisch vernieuwd.
BUILDINGS_QUERY_VER: int = 5

OVERPASS_GRID: int = 3  # N×N tegels per gebied; vergroot bij aanhoudende time-outs

BUILDING_TAGS: frozenset = frozenset(
    {
        "building",
        "shop",
        "amenity",
        "public_transport",
        "railway",
        "leisure",
    }
)

# Mapping van OSM landuse-waarden naar intern gebouwtype
LANDUSE_TYPE: dict = {
    "residential": "residential",
    "housing": "residential",
    "commercial": "commercial",
    "retail": "commercial",
    "industrial": "industrial",
    "port": "industrial",
    "depot": "industrial",
    "harbour": "industrial",
    "brownfield": "industrial",
    "railway": "transport",
    "transportation": "transport",
    "education": "education",
    "recreation_ground": "recreation",
    "allotments": "recreation",
    "village_green": "recreation",
    "grass": "recreation",
    "greenfield": "other",
    "military": "other",
    "construction": "other",
    "farmland": "other",
    "farmyard": "other",
}

# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def overpass_query_for_bbox(b: str) -> str:
    """Geef een Overpass-query terug voor de opgegeven bbox-string 'S,W,N,E'."""
    return (
        f"[out:json][timeout:40];"
        f"("
        f'  way["building"]({b});'
        f'  way["shop"]({b});'
        f'  way["amenity"~"parking|bus_station|ferry_terminal|fuel|marketplace"]({b});'
        f'  way["public_transport"~"station|stop_area"]({b});'
        f'  way["railway"~"station|halt"]({b});'
        f'  way["leisure"~"sports_centre|stadium|swimming_pool|ice_rink"]({b});'
        f'  way["landuse"]({b});'
        f");"
        f"out body geom;"
    )


def fetch_one_tile(b: str) -> tuple[list, bool]:
    """Voer één Overpass-query uit voor bbox 'S,W,N,E'.

    Geeft (elements, ok) terug: elements is de lijst OSM-elementen,
    ok=False als de response afgebroken of onleesbaar was.
    Bij HTTP 429 wordt eenmalig 12 seconden gewacht en opnieuw geprobeerd.
    """
    query = overpass_query_for_bbox(b)
    url = OVERPASS_URL + "?" + urllib.parse.urlencode({"data": query})
    req = urllib.request.Request(url, headers={"User-Agent": "GMP-speeltuin/1.0"})
    raw = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=50) as resp_ov:
                raw = resp_ov.read()
            break  # gelukt
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(12)  # rate-limit: wacht en probeer opnieuw
                continue
            return [], False  # andere HTTP-fout: tegel overslaan
        except http.client.IncompleteRead as exc:
            raw = exc.partial  # gebruik ontvangen bytes en stop
            break
    if raw is None:
        return [], False
    try:
        return json.loads(raw.decode("utf-8")).get("elements", []), True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [], False  # afgekapte JSON: tegel overslaan


def py_pip(px: float, py: float, ring: list) -> bool:
    """Ray-casting point-in-polygon test (identiek aan de JS-versie in index.html)."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Hoofd-API
# ---------------------------------------------------------------------------


def elements_to_building_features(elements: list) -> list:
    """Converteer ruwe Overpass-elementen naar een lijst GeoJSON building-Features.

    Alleen elementen met een gebouwtag worden omgezet; landuse-areas worden
    gebruikt voor de ruimtelijke join (_landuse-property) maar niet opgeslagen.
    """
    # Bouw landuse-opzoekstructuur uit de niet-gebouw elementen
    landuse_lookup = []
    for elem in elements:
        tags = elem.get("tags", {})
        if any(t in tags for t in BUILDING_TAGS):
            continue
        landuse = tags.get("landuse", "")
        if not landuse:
            continue
        coords = [[node["lon"], node["lat"]] for node in elem.get("geometry", [])]
        if len(coords) < 3:
            continue
        ring = coords if coords[0] == coords[-1] else coords + [coords[0]]
        landuse_lookup.append(
            {
                "landuse": landuse,
                "ring": ring,
                "mnX": min(c[0] for c in ring),
                "mxX": max(c[0] for c in ring),
                "mnY": min(c[1] for c in ring),
                "mxY": max(c[1] for c in ring),
            }
        )

    # Converteer gebouwen naar GeoJSON Features
    features = []
    for elem in elements:
        tags = elem.get("tags", {})
        if not any(t in tags for t in BUILDING_TAGS):
            continue
        coords = [[node["lon"], node["lat"]] for node in elem.get("geometry", [])]
        if len(coords) < 4:
            continue
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        n_pts = len(coords) - 1
        cx = sum(c[0] for c in coords[:n_pts]) / max(n_pts, 1)
        cy = sum(c[1] for c in coords[:n_pts]) / max(n_pts, 1)

        lu = None
        for lz in landuse_lookup:
            if cx < lz["mnX"] or cx > lz["mxX"] or cy < lz["mnY"] or cy > lz["mxY"]:
                continue
            if py_pip(cx, cy, lz["ring"]):
                lu = lz["landuse"]
                break

        props: dict = {**tags, "osm_id": elem["id"]}
        if lu:
            props["_landuse"] = lu
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": props,
            }
        )
    return features


def fetch_buildings_overpass(
    bbox: list,
    tile_cache_dir: Path | None = None,
    fallback_tile_cache_dir: Path | None = None,
) -> dict:
    """Haal gebouwen op via Overpass API en sla ze op als GeoJSON per tegel.

    Parameters
    ----------
    bbox:
        [minLon, minLat, maxLon, maxLat]
    tile_cache_dir:
        Map voor de eigen tegel-cache van dit gebied (optioneel).
    fallback_tile_cache_dir:
        Tegel-cache van het bovenliggende basis-scenario (optioneel).

    Het gebied wordt opgesplitst in OVERPASS_GRID × OVERPASS_GRID tegels.
    Per tegel geldt de volgende voorkeursvolgorde:
      1. Eigen tegel-cache (tile_cache_dir)
      2. Tegel-cache van het basis-scenario (fallback_tile_cache_dir)
      3. Ophalen via Overpass

    Elke tegel-cache is een geldig GeoJSON FeatureCollection met uitsluitend
    gebouw-features (landuse-areas worden niet opgeslagen).

    Geeft een GeoJSON FeatureCollection terug.  Als niet alle tegels geslaagd
    zijn, wordt ``properties._partial = True`` gezet en wordt er géén
    samengevoegd cachebestand geschreven door de aanroeper.
    """
    minLon, minLat, maxLon, maxLat = bbox
    n = OVERPASS_GRID
    dLon = (maxLon - minLon) / n
    dLat = (maxLat - minLat) / n

    seen_ids: set = set()
    all_features: list = []
    complete = True

    for col in range(n):
        for row in range(n):
            w = minLon + col * dLon
            e = minLon + (col + 1) * dLon
            s = minLat + row * dLat
            nt = minLat + (row + 1) * dLat
            b = f"{s},{w},{nt},{e}"

            tile_path = (
                (tile_cache_dir / f"tile-{col}x{row}.geojson")
                if tile_cache_dir
                else None
            )
            tile_features = None

            # 1) Eigen tegel-cache
            if tile_path and tile_path.exists():
                try:
                    fc = json.loads(tile_path.read_text(encoding="utf-8"))
                    if (
                        fc.get("type") == "FeatureCollection"
                        and fc.get("_qv") == BUILDINGS_QUERY_VER
                    ):
                        tile_features = fc.get("features", [])
                except Exception:
                    pass  # corrupte tile-cache: verder zoeken

            # 2) Tegel-cache van het basis-scenario
            if tile_features is None and fallback_tile_cache_dir:
                fb_path = fallback_tile_cache_dir / f"tile-{col}x{row}.geojson"
                if fb_path.exists():
                    try:
                        fc = json.loads(fb_path.read_text(encoding="utf-8"))
                        if (
                            fc.get("type") == "FeatureCollection"
                            and fc.get("_qv") == BUILDINGS_QUERY_VER
                        ):
                            tile_features = fc.get("features", [])
                    except Exception:
                        pass

            # 3) Ophalen via Overpass en omzetten naar GeoJSON-features
            if tile_features is None:
                if col > 0 or row > 0:
                    time.sleep(1)  # voorkom rate-limiting bij snelle opeenvolging
                elements, ok = fetch_one_tile(b)
                if ok:
                    tile_features = elements_to_building_features(elements)
                    if tile_cache_dir and tile_path:
                        try:
                            tile_cache_dir.mkdir(parents=True, exist_ok=True)
                            tile_path.write_text(
                                json.dumps(
                                    {
                                        "type": "FeatureCollection",
                                        "_qv": BUILDINGS_QUERY_VER,
                                        "features": tile_features,
                                    },
                                    ensure_ascii=False,
                                ),
                                encoding="utf-8",
                            )
                        except Exception:
                            pass
                else:
                    complete = False
                    tile_features = []

            # Dedupliceer op osm_id (gebouwen kunnen in meerdere tegels vallen)
            for feat in tile_features:
                osm_id = feat.get("properties", {}).get("osm_id")
                if osm_id is not None and osm_id in seen_ids:
                    continue
                if osm_id is not None:
                    seen_ids.add(osm_id)
                all_features.append(feat)

    meta: dict = {"_qv": BUILDINGS_QUERY_VER}
    if not complete:
        meta["_partial"] = True
    return {
        "type": "FeatureCollection",
        "features": all_features,
        "properties": meta,
    }
