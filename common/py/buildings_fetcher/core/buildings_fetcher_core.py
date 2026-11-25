"""buildings_fetcher.core — haalt OSM-gebouwen op via de Overpass API.

Publieke API
------------
    fetch_buildings_overpass(bbox, tile_cache_dir, fallback_tile_cache_dir, osm_path)
        Hoofdfunctie: leest bij voorkeur een lokaal .osm.pbf-extract; anders
        verdeelt hij het gebied in tegels, raadpleegt de cache-hiërarchie en doet
        zo nodig Overpass-verzoeken. Geeft een GeoJSON FeatureCollection terug.

    elements_to_building_features(elements)
        Converteert ruwe Overpass-elementen naar GeoJSON Feature-dicts.

    filter_features_to_zone_class(data, zone_fc, zone_class)
        Houdt alleen features over waarvan de voetafdruk een zone van de
        opgegeven klasse (bv. "STUDY") overlapt, zodat gebouwen uit de (veel
        bredere) invloedsgebied-zones niet in de viewer belanden.

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

# Gedeelde Overpass-client (gmt_shared) kan een query ook tegen een lokaal
# .osm.pbf-extract evalueren i.p.v. de remote API — zie fetch_buildings_overpass.
# Optioneel: als gmt_shared niet geïnstalleerd is, werkt alles gewoon met de
# hand-geschreven urllib-tiling hieronder (remote Overpass, zoals voorheen).
try:
    from gmt_shared.overpass import (
        fetch_overpass as _shared_fetch_overpass,
        _resolve_pbf_path as _resolve_osm_pbf_path,
    )

    _GMT_SHARED_OVERPASS_AVAILABLE = True
except ImportError:
    _shared_fetch_overpass = None  # type: ignore[assignment]
    _resolve_osm_pbf_path = None  # type: ignore[assignment]
    _GMT_SHARED_OVERPASS_AVAILABLE = False

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
# Filteren op zone-klasse (bv. STUDY), zodat alleen gebouwen binnen het
# eigenlijke studiegebied worden teruggegeven — niet de (veel bredere)
# invloedsgebied-zones die wél meetellen voor de OD-productie/attractie maar
# niet bedoeld zijn om als 3D-laag getoond te worden.
# ---------------------------------------------------------------------------


def _polygon_rings(geometry: dict) -> list:
    """Geeft de polygonen van een Polygon- of MultiPolygon-geometrie terug, elk
    als lijst van rings (buitenring gevolgd door eventuele gat-rings). Andere
    geometrietypen (Point, LineString, …) geven een lege lijst."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if not coords:
        return []
    if gtype == "Polygon":
        return [coords]
    if gtype == "MultiPolygon":
        return coords
    return []


def _ring_bbox(ring: list) -> tuple:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _segments_intersect(p1, p2, p3, p4) -> bool:
    """True als lijnstuk p1-p2 het lijnstuk p3-p4 kruist (bedoeld als overlap-
    test tussen twee polygonranden, geen exacte-rakingslogica nodig)."""
    def side(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1, d2 = side(p3, p4, p1), side(p3, p4, p2)
    d3, d4 = side(p1, p2, p3), side(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _ring_overlaps_polygon(ring: list, rings: list) -> bool:
    """True als de (buiten)ring `ring` van een gebouw-voetafdruk de polygon
    `rings` (buitenring + eventuele gaten, van een zone) overlapt: een
    hoekpunt van het gebouw in de zone (buiten de gaten), een hoekpunt van de
    zone-buitenring in het gebouw, of een rand van het gebouw die een rand
    van de zone-buitenring kruist. Werkt ook voor grote, niet-convexe
    voetafdrukken (vleugels rond een binnenplaats), waarbij een enkel
    representatief punt soms buiten het gebouw zelf valt."""
    outer, holes = rings[0], rings[1:]
    for x, y in ring:
        if py_pip(x, y, outer) and not any(py_pip(x, y, h) for h in holes):
            return True
    for x, y in outer:
        if py_pip(x, y, ring):
            return True
    n, m = len(ring), len(outer)
    for i in range(n):
        a1, a2 = ring[i], ring[(i + 1) % n]
        for j in range(m):
            if _segments_intersect(a1, a2, outer[j], outer[(j + 1) % m]):
                return True
    return False


def feature_footprint_parts(feature: dict) -> list:
    """Geeft de voetafdruk van een GeoJSON-feature terug als lijst van
    buitenringen (één per polygoondeel; gaten in het gebouw zelf tellen niet
    mee voor een overlap-test). Lege lijst voor niet-ondersteunde
    geometrietypen (bv. LineString) of lege geometrie."""
    return [rings[0] for rings in _polygon_rings(feature.get("geometry") or {}) if rings and rings[0]]


def zone_class_polygons(zone_fc: dict | None, zone_class: str) -> list:
    """Geeft alle polygonen (met voorberekende bbox) van zones met de opgegeven
    `zoneClass` terug, als lijst van {"rings": [...], "bbox": (minx,miny,maxx,maxy)}."""
    out = []
    for feat in (zone_fc or {}).get("features", []):
        if (feat.get("properties") or {}).get("zoneClass") != zone_class:
            continue
        for rings in _polygon_rings(feat.get("geometry") or {}):
            if not rings or not rings[0]:
                continue
            out.append({"rings": rings, "bbox": _ring_bbox(rings[0])})
    return out


def filter_features_to_zone_class(data: dict, zone_fc: dict | None, zone_class: str) -> dict:
    """Beperkt `data["features"]` tot features waarvan de voetafdruk een zone
    van `zone_class` overlapt (bv. de STUDY-zones van het gebied) — niet enkel
    een representatief punt: bij grote, niet-convexe panden (vleugels rond een
    binnenplaats, zoals een kazerne) kan zo'n punt buiten het gebouw zelf
    vallen, waardoor het hele pand ten onrechte wegviel terwijl het
    grotendeels in het gebied ligt.

    Fail-open: als er geen zones van die klasse gevonden worden (geen ZONE-bestand,
    oud bestand zonder zoneClass-metadata, …) wordt `data` ongewijzigd teruggegeven
    in plaats van alles weg te filteren.

    Muteert `data` niet: geeft een nieuwe FeatureCollection-dict terug met dezelfde
    top-level properties en een nieuwe (gefilterde) features-lijst.
    """
    zones = zone_class_polygons(zone_fc, zone_class)
    if not zones:
        return data
    kept = []
    for feat in data.get("features", []):
        parts = feature_footprint_parts(feat)
        if not parts:
            continue
        for ring in parts:
            bx0, by0, bx1, by1 = _ring_bbox(ring)
            matched = False
            for z in zones:
                minx, miny, maxx, maxy = z["bbox"]
                if bx1 < minx or bx0 > maxx or by1 < miny or by0 > maxy:
                    continue
                if _ring_overlaps_polygon(ring, z["rings"]):
                    kept.append(feat)
                    matched = True
                    break
            if matched:
                break
    result = dict(data)
    result["features"] = kept
    return result


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
    osm_path: str | None = None,
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
    osm_path:
        Pad naar een lokaal .osm.pbf-extract (optioneel). Als dit is opgegeven,
        wordt de hele bbox in één keer lokaal gelezen via
        gmt_shared.overpass.fetch_overpass — geen tiling, tegel-cache of
        rate-limiting nodig, dat bestaat alleen om verzoeken aan de remote
        Overpass-API klein te houden. OSM_PBF_PATH uit de omgeving wordt hier
        bewust níet gelezen: de aanroeper bepaalt welk extract de bbox dekt.

    Zonder lokaal extract wordt het gebied opgesplitst in
    OVERPASS_GRID × OVERPASS_GRID tegels.
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

    # Alleen een expliciet meegegeven osm_path: géén stille terugval op
    # OSM_PBF_PATH uit de omgeving — de server controleert eerst of het extract
    # de bbox echt dekt (een vaste provincie-PBF levert anders 0 gebouwen op).
    if _GMT_SHARED_OVERPASS_AVAILABLE and osm_path:
        try:
            pbf_path = _resolve_osm_pbf_path(osm_path)
        except ValueError:
            pbf_path = None  # ongeldig pad: val terug op de remote Overpass-API
        if pbf_path is not None:
            b = f"{minLat},{minLon},{maxLat},{maxLon}"
            data = _shared_fetch_overpass(overpass_query_for_bbox(b), osm_path=str(pbf_path))
            return {
                "type": "FeatureCollection",
                "features": elements_to_building_features(data.get("elements", [])),
                "properties": {"_qv": BUILDINGS_QUERY_VER},
            }

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
