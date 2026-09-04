"""vegetation_fetcher.core — haalt OSM-bomen op via de Overpass API.

Publieke API
------------
    fetch_vegetation_overpass(bbox, tile_cache_dir, fallback_tile_cache_dir)
        Hoofdfunctie: verdeelt het gebied in tegels, raadpleegt de cache-hiërarchie
        en doet zo nodig Overpass-verzoeken. Geeft een GeoJSON FeatureCollection terug.

    elements_to_vegetation_features(elements)
        Converteert ruwe Overpass-elementen naar GeoJSON Feature-dicts.

Constanten
----------
    VEGETATION_QUERY_VER  — verhoog dit getal om alle caches te invalideren.
    OVERPASS_GRID         — N×N tegels per gebied.
    MAX_TREES             — bovengrens op het aantal boom-punten (thinnen daarboven).

Ontwerpkeuzes
-------------
    Alleen "echte" losse begroeiing wordt opgehaald: individuele bomen
    (``natural=tree``, punt) en boomrijen (``natural=tree_row``, lijn).
    Bos-/struik-/grasvlakken worden bewust NIET opgehaald — de onderliggende
    basiskaart toont die groenzones al.
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
VEGETATION_QUERY_VER: int = 1

OVERPASS_GRID: int = 3  # N×N tegels per gebied; vergroot bij aanhoudende time-outs

MAX_TREES: int = 15000  # harde bovengrens op boom-PUNTEN (tree_row telt niet mee)

# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def overpass_query_for_bbox(b: str) -> str:
    """Geef een Overpass-query terug voor de opgegeven bbox-string 'S,W,N,E'.

    Alleen losse bomen (punt) en boomrijen (lijn); geen vlakken.
    """
    return (
        f"[out:json][timeout:40];"
        f"("
        f'  node["natural"="tree"]({b});'
        f'  way["natural"="tree_row"]({b});'
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
            with urllib.request.urlopen(req, timeout=12) as resp_ov:
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


def _parse_float(val) -> "float | None":
    """Parse een OSM-numerieke tag (bv. '12', '12 m', '12.5') → float of None."""
    if val is None:
        return None
    try:
        s = str(val).strip().replace(",", ".")
        # neem het eerste numerieke deel (voor bv. '12 m')
        num = ""
        for ch in s:
            if ch.isdigit() or ch in ".-":
                num += ch
            elif num:
                break
        return float(num) if num else None
    except (ValueError, TypeError):
        return None


def _normalize_leaf_type(val) -> "str | None":
    """Normaliseer OSM leaf_type → 'broadleaved' | 'needleleaved' | None."""
    if not val:
        return None
    v = str(val).strip().lower()
    if v in ("broadleaved", "needleleaved"):
        return v
    return None


# ---------------------------------------------------------------------------
# Hoofd-API
# ---------------------------------------------------------------------------


def elements_to_vegetation_features(elements: list) -> list:
    """Converteer ruwe Overpass-elementen naar een lijst GeoJSON boom-Features.

    De propertysleutels (vegType/height/crown/leafType/species/osmId) komen
    exact overeen met wat de client (index.html) verwacht.
    """
    features = []
    for elem in elements:
        etype = elem.get("type")
        tags = elem.get("tags", {}) or {}

        props: dict = {"osmId": elem.get("id")}
        height = _parse_float(tags.get("height") or tags.get("est_height"))
        crown = _parse_float(tags.get("diameter_crown"))
        leaf = _normalize_leaf_type(tags.get("leaf_type"))
        species = tags.get("species") or tags.get("genus")
        if height is not None:
            props["height"] = height
        if crown is not None:
            props["crown"] = crown
        if leaf:
            props["leafType"] = leaf
        if species:
            props["species"] = species

        if etype == "node":
            lon, lat = elem.get("lon"), elem.get("lat")
            if lon is None or lat is None:
                continue
            props["vegType"] = "tree"
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": props,
                }
            )
        elif etype == "way":
            coords = [
                [nd["lon"], nd["lat"]]
                for nd in elem.get("geometry", [])
                if "lon" in nd and "lat" in nd
            ]
            if len(coords) < 2:
                continue
            props["vegType"] = "tree_row"
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": props,
                }
            )
    return features


def _thin_trees(features: list, max_trees: int) -> list:
    """Cap het aantal boom-PUNTEN op max_trees door deterministisch te dunnen.

    tree_row-lijnen blijven altijd behouden (de client sampelt die zelf).
    """
    points = [f for f in features if f.get("geometry", {}).get("type") == "Point"]
    rows = [f for f in features if f.get("geometry", {}).get("type") != "Point"]
    if len(points) <= max_trees:
        return features
    step = len(points) / float(max_trees)
    kept = [points[int(i * step)] for i in range(max_trees)]
    return kept + rows


def fetch_vegetation_overpass(
    bbox: list,
    tile_cache_dir: Path | None = None,
    fallback_tile_cache_dir: Path | None = None,
) -> dict:
    """Haal bomen op via Overpass API en sla ze op als GeoJSON per tegel.

    Parameters
    ----------
    bbox:
        [minLon, minLat, maxLon, maxLat]
    tile_cache_dir:
        Map voor de eigen tegel-cache van dit gebied (optioneel).
    fallback_tile_cache_dir:
        Tegel-cache van het bovenliggende basis-scenario (optioneel).

    Het gebied wordt opgesplitst in OVERPASS_GRID × OVERPASS_GRID tegels.
    Per tegel geldt de voorkeursvolgorde:
      1. Eigen tegel-cache (tile_cache_dir)
      2. Tegel-cache van het basis-scenario (fallback_tile_cache_dir)
      3. Ophalen via Overpass

    Geeft een GeoJSON FeatureCollection terug. Als niet alle tegels geslaagd
    zijn, wordt ``properties._partial = True`` gezet zodat de aanroeper het
    aggregaat niet cachet.
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
                        and fc.get("_qv") == VEGETATION_QUERY_VER
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
                            and fc.get("_qv") == VEGETATION_QUERY_VER
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
                    tile_features = elements_to_vegetation_features(elements)
                    if tile_cache_dir and tile_path:
                        try:
                            tile_cache_dir.mkdir(parents=True, exist_ok=True)
                            tile_path.write_text(
                                json.dumps(
                                    {
                                        "type": "FeatureCollection",
                                        "_qv": VEGETATION_QUERY_VER,
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

            # Dedupliceer op osmId (bomen kunnen in meerdere tegels vallen)
            for feat in tile_features:
                osm_id = feat.get("properties", {}).get("osmId")
                if osm_id is not None and osm_id in seen_ids:
                    continue
                if osm_id is not None:
                    seen_ids.add(osm_id)
                all_features.append(feat)

    all_features = _thin_trees(all_features, MAX_TREES)

    meta: dict = {"_qv": VEGETATION_QUERY_VER}
    if not complete:
        meta["_partial"] = True
    return {
        "type": "FeatureCollection",
        "features": all_features,
        "properties": meta,
    }
