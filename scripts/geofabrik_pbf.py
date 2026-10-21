"""Geofabrik-extract discovery, coverage check and download helpers.

Used by the prepare pipeline to avoid hard-coding a single .osm.pbf path:
given a WGS-84 bounding box we find the smallest known Geofabrik extract
whose polygon fully contains it, download the extract if it is not cached,
and return the local file path.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

GEOFABRIK_BASE = "https://download.geofabrik.de"
OSM_PBF_ENV_VAR = "OSM_PBF_PATH"
OSM_PBF_CACHE_DIR_ENV_VAR = "OSM_PBF_CACHE_DIR"


def _default_cache_dir() -> Path:
    env = os.environ.get(OSM_PBF_CACHE_DIR_ENV_VAR, "").strip()
    return Path(env) if env else Path(tempfile.gettempdir()) / "geofabrik_pbf"


DEFAULT_CACHE_DIR = _default_cache_dir()


@dataclass(frozen=True)
class Extract:
    slug: str
    name: str
    path: str
    size_mb: int
    description: str = ""

    @property
    def poly_url(self) -> str:
        return f"{GEOFABRIK_BASE}/{self.path}.poly"

    @property
    def pbf_url(self) -> str:
        return f"{GEOFABRIK_BASE}/{self.path}-latest.osm.pbf"


# Registry ordered from small (provinces) to large (countries/continents).
# File sizes are rough Geofabrik estimates and only used for sort order.
_GEOFABRIK_REGISTRY: list[Extract] = [
    # Netherlands provinces
    Extract("zeeland", "Zeeland", "europe/netherlands/zeeland", 42),
    Extract("flevoland", "Flevoland", "europe/netherlands/flevoland", 34),
    Extract("groningen", "Groningen", "europe/netherlands/groningen", 53),
    Extract("drenthe", "Drenthe", "europe/netherlands/drenthe", 60),
    Extract("friesland", "Friesland", "europe/netherlands/friesland", 84),
    Extract("utrecht", "Utrecht", "europe/netherlands/utrecht", 93),
    Extract("limburg", "Limburg", "europe/netherlands/limburg", 96),
    Extract("overijssel", "Overijssel", "europe/netherlands/overijssel", 108),
    Extract("gelderland", "Gelderland", "europe/netherlands/gelderland", 185),
    Extract("noord-holland", "Noord-Holland", "europe/netherlands/noord-holland", 180),
    Extract("noord-brabant", "Noord-Brabant", "europe/netherlands/noord-brabant", 197),
    Extract("zuid-holland", "Zuid-Holland", "europe/netherlands/zuid-holland", 201),
    # Country extracts
    Extract("netherlands", "Netherlands", "europe/netherlands", 1300),
    Extract("belgium", "Belgium", "europe/belgium", 450),
    Extract("germany", "Germany", "europe/germany", 4000),
    # Continent fallback
    Extract("europe", "Europe", "europe", 32600),
]


def _http_get_text(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "speeltuin-pbf-resolver/1.0"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8")


def _http_download(url: str, dest: Path, timeout: int = 600) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "speeltuin-pbf-resolver/1.0"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        with dest.open("wb") as fh:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                fh.write(chunk)


def parse_poly(text: str) -> Polygon | MultiPolygon:
    """Parse an Osmosis/Geofabrik .poly file into a Shapely geometry."""
    lines = text.strip().splitlines()
    if not lines:
        raise ValueError("empty .poly file")

    # First line is the region name; subsequent sections each describe one ring.
    idx = 1
    rings: list[list[tuple[float, float]]] = []
    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1
        if line == "END":
            break
        if not line:
            continue
        ring: list[tuple[float, float]] = []
        while idx < len(lines):
            coord_line = lines[idx].strip()
            idx += 1
            if coord_line == "END":
                break
            parts = coord_line.split()
            if len(parts) < 2:
                continue
            lon, lat = float(parts[0]), float(parts[1])
            ring.append((lon, lat))
        if len(ring) >= 3:
            rings.append(ring)

    if not rings:
        raise ValueError("no valid rings found in .poly file")

    polygons = [Polygon(ring) for ring in rings]
    if len(polygons) == 1:
        return polygons[0]
    return MultiPolygon(polygons)


def _poly_cache_path(extract: Extract, cache_dir: Path) -> Path:
    return cache_dir / f"{extract.slug}.poly"


def _pbf_cache_path(extract: Extract, cache_dir: Path) -> Path:
    return cache_dir / f"{extract.slug}.osm.pbf"


def fetch_poly(
    extract: Extract, cache_dir: Path, *, refresh: bool = False
) -> Polygon | MultiPolygon:
    cache_path = _poly_cache_path(extract, cache_dir)
    if not refresh and cache_path.exists():
        text = cache_path.read_text(encoding="utf-8")
    else:
        logger.info("downloading %s", extract.poly_url)
        text = _http_get_text(extract.poly_url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    return parse_poly(text)


def bbox_polygon(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float
) -> Polygon:
    return box(min_lon, min_lat, max_lon, max_lat)


def _covers_bbox(geometry: Polygon | MultiPolygon, bbox: Polygon) -> bool:
    return bool(geometry.contains(bbox) or geometry.equals(bbox))


def find_covering_extracts(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    cache_dir: Path | None = None,
) -> list[Extract]:
    """Return all registry extracts whose polygon fully contains the bbox.

    The returned list is sorted smallest-first by the registry's size estimate.
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    bbox = bbox_polygon(min_lon, min_lat, max_lon, max_lat)
    matches: list[tuple[int, Extract]] = []
    for extract in _GEOFABRIK_REGISTRY:
        try:
            geometry = fetch_poly(extract, cache_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not fetch polygon for %s: %s", extract.slug, exc)
            continue
        if _covers_bbox(geometry, bbox):
            matches.append((extract.size_mb, extract))
    matches.sort(key=lambda item: item[0])
    return [extract for _, extract in matches]


def find_covering_extract(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    cache_dir: Path | None = None,
) -> Extract | None:
    """Return the smallest extract that fully contains the bbox, or None."""
    matches = find_covering_extracts(
        min_lon, min_lat, max_lon, max_lat, cache_dir=cache_dir
    )
    return matches[0] if matches else None


def is_within_netherlands(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    cache_dir: Path | None = None,
) -> bool:
    """Return True when the bbox lies completely inside the Netherlands extract."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    try:
        nl_extract = next(e for e in _GEOFABRIK_REGISTRY if e.slug == "netherlands")
        geometry = fetch_poly(nl_extract, cache_dir)
    except StopIteration as exc:
        raise RuntimeError("netherlands extract not found in registry") from exc
    bbox = bbox_polygon(min_lon, min_lat, max_lon, max_lat)
    return _covers_bbox(geometry, bbox)


def _valid_pbf_path(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".pbf"


def resolve_explicit_pbf_path(osm_path: str | None = None) -> Path | None:
    """Return a valid local PBF path from the argument or OSM_PBF_PATH env var."""
    raw = (osm_path or "").strip()
    if not raw:
        raw = os.environ.get(OSM_PBF_ENV_VAR, "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not _valid_pbf_path(path):
        raise ValueError(f"OSM PBF path is not a readable .pbf file: {path}")
    return path


def resolve_or_download_pbf(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    *,
    osm_path: str | None = None,
    cache_dir: Path | str | None = None,
    allow_download: bool = True,
    ignore_explicit: bool = False,
) -> tuple[Path, Extract | None]:
    """Return a local PBF path and the extract that covers the bbox.

    Resolution order (unless *ignore_explicit* is True):
    1. Explicit *osm_path* argument.
    2. OSM_PBF_PATH environment variable.
    3. The smallest Geofabrik extract whose polygon contains the bbox
       (cached locally, or downloaded when *allow_download* is True).

    *ignore_explicit* skips steps 1/2 and always does the bbox-based lookup.
    A caller uses this after it has already determined — by its own means —
    that an explicitly configured OSM_PBF_PATH does not actually cover the
    requested bbox (e.g. a fixed province snapshot used for a different
    area): without this flag, step 2 would silently re-discover the same
    environment variable and undo that fallback.
    """
    explicit = None if ignore_explicit else resolve_explicit_pbf_path(osm_path)
    if explicit is not None:
        return explicit, None

    cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
    extract = find_covering_extract(
        min_lon, min_lat, max_lon, max_lat, cache_dir=cache_dir
    )
    if extract is None:
        raise ValueError(
            f"bbox ({min_lon}, {min_lat}, {max_lon}, {max_lat}) is not covered by any known Geofabrik extract"
        )

    pbf_path = _pbf_cache_path(extract, cache_dir)
    if _valid_pbf_path(pbf_path):
        logger.info("using cached PBF for %s: %s", extract.slug, pbf_path)
        return pbf_path, extract

    if not allow_download:
        raise FileNotFoundError(f"cached PBF not found for {extract.slug}: {pbf_path}")

    logger.info("downloading %s PBF for %s", extract.name, extract.pbf_url)
    pbf_path.parent.mkdir(parents=True, exist_ok=True)
    _http_download(extract.pbf_url, pbf_path)
    if not _valid_pbf_path(pbf_path):
        raise RuntimeError(f"downloaded file is missing or not a .pbf: {pbf_path}")
    return pbf_path, extract


def coverage_geojson(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    *,
    cache_dir: Path | str | None = None,
) -> dict:
    """Return a GeoJSON FeatureCollection with the bbox and covering extracts."""
    cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
    bbox = bbox_polygon(min_lon, min_lat, max_lon, max_lat)
    features = [
        {
            "type": "Feature",
            "properties": {"kind": "bbox"},
            "geometry": bbox.__geo_interface__,
        }
    ]
    for extract in find_covering_extracts(
        min_lon, min_lat, max_lon, max_lat, cache_dir=cache_dir
    ):
        geometry = fetch_poly(extract, cache_dir)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "kind": "extract",
                    "slug": extract.slug,
                    "name": extract.name,
                },
                "geometry": geometry.__geo_interface__,
            }
        )
    return {"type": "FeatureCollection", "features": features}
