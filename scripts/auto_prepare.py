"""Local/CLI entrypoint for the smart prepare pipeline.

Makes a small cached .osm.pbf clip for the requested bbox (from the Geofabrik
province extract(s) covering it, downloaded if necessary; see
gmt_shared.geofabrik.local_pbf_for_bbox), then routes to either the full Databricks-based
`prepare` pipeline ( bbox inside the Netherlands) or the OSM-only
`osm_prepare` pipeline (bbox outside the Netherlands).

Usage
-----
    python scripts/auto_prepare.py \
        --bbox 6.15 51.95 6.25 52.00 \
        --output-folder ./output/ \
        --name Deventer

    # use a specific cached/download directory
    python scripts/auto_prepare.py --bbox ... --output-folder ./out/ --pbf-cache-dir ./pbf-cache

    # force use of an existing PBF file
    OSM_PBF_PATH=/data/netherlands.osm.pbf python scripts/auto_prepare.py --bbox ... --output-folder ./out/
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any


# Ensure the repository root is on sys.path so `scripts.geofabrik_pbf` imports
# work regardless of the current working directory.
def _bootstrap_path() -> None:
    here = Path(__file__).resolve().parent
    root = here.parent
    for p in (str(root), str(here)):
        if p not in sys.path:
            sys.path.insert(0, p)


_bootstrap_path()

from scripts.geofabrik_pbf import (  # noqa: E402
    local_pbf_for_bbox,
    is_within_netherlands,
    DEFAULT_CACHE_DIR,
    OSM_PBF_ENV_VAR,
    OSM_PBF_CACHE_DIR_ENV_VAR,
)


def _read_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw_val = line.partition("=")
        key = key.strip()
        val = raw_val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if key:
            result[key] = val
    return result


def _parse_bbox(raw: list[str]) -> tuple[float, float, float, float]:
    if len(raw) == 1:
        raw = raw[0].split(",")
    if len(raw) != 4:
        raise ValueError(f"--bbox expects exactly 4 coordinates, got {len(raw)}")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(v) for v in raw)
    except ValueError as exc:
        raise ValueError(f"--bbox values must be numbers: {exc}") from exc
    return min_lon, min_lat, max_lon, max_lat


def _run_prepare_pipeline(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    out_dir: Path,
    *,
    pbf_path: Path,
    name: str | None,
    modes: list[str],
    fetch_vegetation: bool,
    refresh: bool,
    debug: bool,
) -> str:
    from prepare.core.prepare_core import run_pipeline  # noqa: PLC0415

    kwargs: dict[str, Any] = dict(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        modes=modes,
        name=name or "area",
        out_dir=out_dir,
        mode_label="MIXED" if len(modes) > 1 else modes[0],
        catalog="spectrum",
        schema="2024_01",
        refresh=refresh,
        debug=debug,
        max_routes=5,
        osm_path=str(pbf_path),
        fetch_vegetation=fetch_vegetation,
    )
    return run_pipeline(**kwargs)


def _run_osm_prepare_pipeline(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    out_dir: Path,
    *,
    pbf_path: Path,
    name: str | None,
    refresh: bool,
    debug: bool,
) -> str:
    from osm.osm_prepare.core.osm_prepare_core import run_pipeline  # noqa: PLC0415

    old_osm_pbf = os.environ.get(OSM_PBF_ENV_VAR)
    try:
        os.environ[OSM_PBF_ENV_VAR] = str(pbf_path)
        return run_pipeline(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            out_dir=out_dir,
            area_id=name,
            name=name,
            refresh=refresh,
            debug=debug,
        )
    finally:
        if old_osm_pbf is None:
            os.environ.pop(OSM_PBF_ENV_VAR, None)
        else:
            os.environ[OSM_PBF_ENV_VAR] = old_osm_pbf


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Smart prepare entrypoint: auto-downloads the right Geofabrik PBF "
            "and routes to the Databricks or OSM-only pipeline."
        )
    )
    parser.add_argument(
        "--bbox",
        required=True,
        nargs="+",
        metavar="COORD",
        help="Bounding box: MIN_LON MIN_LAT MAX_LON MAX_LAT (or comma-separated).",
    )
    parser.add_argument(
        "--output-folder",
        required=True,
        metavar="DIR",
        help="Output directory. Created automatically when missing.",
    )
    parser.add_argument("--name", default=None, help="Human-readable area name.")
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["CAR"],
        help="Transport modes for the full prepare pipeline. Default: CAR.",
    )
    parser.add_argument(
        "--pbf-cache-dir",
        default=None,
        metavar="DIR",
        help=(
            "Directory for cached/downloaded PBF files. "
            f"Default: ${OSM_PBF_CACHE_DIR_ENV_VAR} env var or {DEFAULT_CACHE_DIR}"
        ),
    )
    parser.add_argument(
        "--osm-path",
        default=None,
        metavar="PATH",
        help="Use this local .osm.pbf file instead of auto-discovery/download.",
    )
    parser.add_argument(
        "--no-vegetation",
        dest="fetch_vegetation",
        action="store_false",
        default=True,
        help="Skip vegetation fetch in the full prepare pipeline.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-run all steps even when outputs exist.",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Write intermediate snapshots."
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file for credentials/overrides.",
    )
    args = parser.parse_args()

    if args.env_file:
        env_file_path = Path(args.env_file)
    else:
        env_file_path = Path(__file__).resolve().parent.parent / "tools" / ".env"
    for k, v in _read_env_file(env_file_path).items():
        os.environ.setdefault(k, v)

    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        level=logging.INFO,
    )

    min_lon, min_lat, max_lon, max_lat = _parse_bbox(args.bbox)
    out_dir = Path(args.output_folder).resolve()
    cache_dir = Path(args.pbf_cache_dir) if args.pbf_cache_dir else DEFAULT_CACHE_DIR

    if args.osm_path:
        explicit = Path(args.osm_path)
        if not explicit.is_file() or explicit.suffix.lower() != ".pbf":
            print(
                f"error: --osm-path is not a readable .pbf: {explicit}", file=sys.stderr
            )
            sys.exit(2)
    # Small cached clip for the bbox: from --osm-path / OSM_PBF_PATH when that
    # covers the bbox, else from the Geofabrik province extract(s).
    pbf_path = local_pbf_for_bbox(
        [min_lon, min_lat, max_lon, max_lat],
        osm_path=args.osm_path or None,
        cache_dir=cache_dir,
    )
    print(f"[auto-prepare] using PBF: {pbf_path}")

    modes = [m.upper() for m in args.modes]
    invalid = [m for m in modes if m not in {"CAR", "BIKE", "PEDESTRIAN"}]
    if invalid:
        print(f"error: invalid modes: {invalid}", file=sys.stderr)
        sys.exit(2)

    if is_within_netherlands(min_lon, min_lat, max_lon, max_lat, cache_dir=cache_dir):
        print(
            "[auto-prepare] bbox is inside the Netherlands → using full prepare pipeline"
        )
        area_id = _run_prepare_pipeline(
            min_lon,
            min_lat,
            max_lon,
            max_lat,
            out_dir,
            pbf_path=pbf_path,
            name=args.name,
            modes=modes,
            fetch_vegetation=args.fetch_vegetation,
            refresh=args.refresh,
            debug=args.debug,
        )
    else:
        print(
            "[auto-prepare] bbox is outside the Netherlands → using OSM-only prepare pipeline"
        )
        if not args.fetch_vegetation:
            print(
                "warning: --no-vegetation is ignored by the OSM-only pipeline",
                file=sys.stderr,
            )
        area_id = _run_osm_prepare_pipeline(
            min_lon,
            min_lat,
            max_lon,
            max_lat,
            out_dir,
            pbf_path=pbf_path,
            name=args.name,
            refresh=args.refresh,
            debug=args.debug,
        )

    print()
    print(f"Area ID: {area_id}")
    print("Done.")


if __name__ == "__main__":
    main()
