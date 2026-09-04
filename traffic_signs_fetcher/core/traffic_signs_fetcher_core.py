"""traffic_signs_fetcher.core — haalt verkeersborden op via NDW (NL) of OSM Overpass.

Publieke API
------------
    fetch_traffic_signs_overpass(bbox, tile_cache_dir, fallback_tile_cache_dir)
        Haalt OSM-verkeersborden op via de Overpass API.  Verdeelt het gebied in
        tegels, raadpleegt de cache-hiërarchie en doet zo nodig Overpass-verzoeken.
        Geeft een GeoJSON FeatureCollection terug.

    fetch_traffic_signs_ndw(data_path, bbox)
        Laadt het lokale NDW-bestand (GeoJSON) en filtert op bounding box.
        Geeft een GeoJSON FeatureCollection terug.

    download_ndw_dataset(output_path)
        Downloadt het volledige NDW-verkeersborden dataset naar output_path als
        GeoJSON.  Geeft True terug bij succes, anders False.

    is_netherlands(bbox)
        Geeft True als het zwaartepunt van de bbox in Nederland ligt.

Constanten
----------
    TRAFFIC_SIGNS_QUERY_VER   — verhoog dit getal om alle caches te invalideren.
    OVERPASS_GRID             — N×N tegels per gebied.
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

TRAFFIC_SIGNS_QUERY_VER: int = 1
OVERPASS_GRID: int = 3  # N×N tegels per gebied

NDW_API_URL: str = (
    "https://data.ndw.nu/api/rest/static-road-data/traffic-signs/v4/current-state"
)

# Bounding box van Nederland [minLon, minLat, maxLon, maxLat]
_NL_BBOX: list = [3.3, 50.7, 7.3, 53.6]

# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def is_netherlands(bbox: list) -> bool:
    """Geeft True als het zwaartepunt van de bbox in Nederland ligt."""
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    return _NL_BBOX[0] <= cx <= _NL_BBOX[2] and _NL_BBOX[1] <= cy <= _NL_BBOX[3]


def download_ndw_dataset(output_path: Path) -> bool:
    """Download het volledige NDW-verkeersborden dataset naar *output_path* als GeoJSON.

    Geeft True terug bij succes, anders False.  Het bestand wordt pas op disk
    geschreven nadat de download volledig en geldig is.
    """
    req = urllib.request.Request(
        NDW_API_URL,
        headers={
            "Accept": "application/geo+json, application/json",
            "User-Agent": "GMP-speeltuin/1.0",
        },
    )
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
        # Basisvalidatie: moet een FeatureCollection zijn
        parsed = json.loads(raw.decode("utf-8"))
        if parsed.get("type") != "FeatureCollection":
            return False
        output_path.write_bytes(raw)
        return True
    except Exception:
        return False


def filter_ndw_by_bbox(data: dict, bbox: list) -> dict:
    """Filter een GeoJSON FeatureCollection op bounding box (Point-features).

    *bbox* = [minLon, minLat, maxLon, maxLat].
    Geeft een nieuwe FeatureCollection terug.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    filtered: list = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            filtered.append(feat)
    return {
        "type": "FeatureCollection",
        "features": filtered,
        "properties": {"_qv": TRAFFIC_SIGNS_QUERY_VER},
    }


def overpass_query_for_bbox(b: str) -> str:
    return f'[out:json][timeout:40];(  node["traffic_sign"]({b}););out body;'


def fetch_one_tile(b: str) -> tuple[list, bool]:
    query = overpass_query_for_bbox(b)
    url = OVERPASS_URL + "?" + urllib.parse.urlencode({"data": query})
    req = urllib.request.Request(url, headers={"User-Agent": "GMP-speeltuin/1.0"})
    raw: bytes | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=50) as resp_ov:
                raw = resp_ov.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(12)
                continue
            return [], False
        except http.client.IncompleteRead as exc:
            raw = exc.partial
            break
    if raw is None:
        return [], False
    try:
        return json.loads(raw.decode("utf-8")).get("elements", []), True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [], False


def elements_to_sign_features(elements: list) -> list:
    """Converteer ruwe Overpass-nodes naar GeoJSON Feature-dicts.

    Het OSM ``traffic_sign``-tag wordt genormaliseerd: een landprefix als
    ``NL:A01`` wordt teruggebracht tot ``A01`` zodat het aansluit bij de
    RVV-codering die ook in het NDW-dataset wordt gebruikt.
    """
    features: list = []
    for elem in elements:
        if elem.get("type") != "node":
            continue
        lat = elem.get("lat")
        lon = elem.get("lon")
        if lat is None or lon is None:
            continue
        tags = elem.get("tags", {})
        raw_sign = tags.get("traffic_sign", "")
        # Normaliseer: strip landprefix, bijv. "NL:A01" → "A01"
        if ":" in raw_sign:
            raw_sign = raw_sign.split(":", 1)[1]
        props: dict = {**tags, "osm_id": elem["id"], "rvvCode": raw_sign}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )
    return features


# ---------------------------------------------------------------------------
# Hoofd-API
# ---------------------------------------------------------------------------


def fetch_traffic_signs_ndw(data_path: Path, bbox: list) -> dict:
    """Laad het lokale NDW-bestand en filter op bounding box.

    *data_path* is het pad naar het NDW GeoJSON-bestand.
    *bbox* = [minLon, minLat, maxLon, maxLat].
    """
    with open(data_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return filter_ndw_by_bbox(data, bbox)


def fetch_traffic_signs_overpass(
    bbox: list,
    tile_cache_dir: Path | None = None,
    fallback_tile_cache_dir: Path | None = None,
) -> dict:
    """Haal OSM-verkeersborden op via de Overpass API, met tile-cache.

    Gebruikt een N×N tegel-raster (zie OVERPASS_GRID), raadpleegt eerst de
    eigen tegel-cache, dan de fallback-cache (base-scenario), en doet pas
    daarna een live Overpass-verzoek.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    n = OVERPASS_GRID
    d_lon = (max_lon - min_lon) / n
    d_lat = (max_lat - min_lat) / n

    seen_ids: set = set()
    all_features: list = []
    complete = True

    for col in range(n):
        for row in range(n):
            w = min_lon + col * d_lon
            e = min_lon + (col + 1) * d_lon
            s = min_lat + row * d_lat
            nt = min_lat + (row + 1) * d_lat
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
                        and fc.get("_qv") == TRAFFIC_SIGNS_QUERY_VER
                    ):
                        tile_features = fc.get("features", [])
                except Exception:
                    pass

            # 2) Fallback tegel-cache (base-scenario)
            if tile_features is None and fallback_tile_cache_dir:
                fb_path = fallback_tile_cache_dir / f"tile-{col}x{row}.geojson"
                if fb_path.exists():
                    try:
                        fc = json.loads(fb_path.read_text(encoding="utf-8"))
                        if (
                            fc.get("type") == "FeatureCollection"
                            and fc.get("_qv") == TRAFFIC_SIGNS_QUERY_VER
                        ):
                            tile_features = fc.get("features", [])
                    except Exception:
                        pass

            # 3) Live Overpass-verzoek
            if tile_features is None:
                if col > 0 or row > 0:
                    time.sleep(1)
                elements, ok = fetch_one_tile(b)
                if ok:
                    tile_features = elements_to_sign_features(elements)
                    if tile_cache_dir and tile_path:
                        try:
                            tile_cache_dir.mkdir(parents=True, exist_ok=True)
                            tile_path.write_text(
                                json.dumps(
                                    {
                                        "type": "FeatureCollection",
                                        "_qv": TRAFFIC_SIGNS_QUERY_VER,
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

            # Deduplicatie op osm_id
            for feat in tile_features:
                osm_id = feat.get("properties", {}).get("osm_id")
                if osm_id is not None and osm_id in seen_ids:
                    continue
                if osm_id is not None:
                    seen_ids.add(osm_id)
                all_features.append(feat)

    meta: dict = {"_qv": TRAFFIC_SIGNS_QUERY_VER}
    if not complete:
        meta["_partial"] = True
    return {
        "type": "FeatureCollection",
        "features": all_features,
        "properties": meta,
    }
