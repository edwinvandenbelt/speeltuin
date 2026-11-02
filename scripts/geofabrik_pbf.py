"""Lokale OSM-data voor een bbox — dunne laag over ``gmt_shared.geofabrik``.

``local_pbf_for_bbox(bbox)`` levert een kleine, gecachte ``.osm.pbf``-uitsnede:
uit het Geofabrik-provincie-extract dat de bbox dekt, uit de samenvoeging van
twee provincies als de bbox over een grens valt, anders uit het Nederland-
extract. Een expliciet ``osm_path`` / ``OSM_PBF_PATH`` is de bron zolang het de
bbox dekt (zie ``gmt_shared.geofabrik.explicit_pbf_covers_bbox``).
"""

from __future__ import annotations

from pathlib import Path

from gmt_shared.geofabrik import (
    NETHERLANDS,
    OSM_PBF_CACHE_DIR_ENV_VAR,
    default_cache_dir,
    load_poly,
    local_pbf_for_bbox,
)
from gmt_shared.overpass import OSM_PBF_ENV_VAR
from shapely.geometry import box

__all__ = [
    "DEFAULT_CACHE_DIR",
    "OSM_PBF_CACHE_DIR_ENV_VAR",
    "OSM_PBF_ENV_VAR",
    "is_within_netherlands",
    "local_pbf_for_bbox",
]

DEFAULT_CACHE_DIR = default_cache_dir()


def is_within_netherlands(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    cache_dir: Path | None = None,
) -> bool:
    """True als de bbox volledig binnen het Geofabrik-extract van Nederland ligt."""
    netherlands = load_poly(NETHERLANDS, Path(cache_dir or DEFAULT_CACHE_DIR))
    return bool(netherlands.covers(box(min_lon, min_lat, max_lon, max_lat)))
