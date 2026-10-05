"""Local runner for buildings_fetcher.

Haalt OSM-gebouwen op voor een opgegeven bounding box en schrijft het
resultaat als GeoJSON FeatureCollection naar een bestand.

Gebruik
-------
    python -m buildings_fetcher.buildings_fetcher_runner \\
        --bbox 4.87 52.34 5.02 52.41 \\
        --output ./amsterdam-BUILDINGS.geojson

    # Met tegel-cache (hergebruikt eerdere Overpass-resultaten):
    python -m buildings_fetcher.buildings_fetcher_runner \\
        --bbox 4.87 52.34 5.02 52.41 \\
        --output ./amsterdam-BUILDINGS.geojson \\
        --tile-cache-dir ./tiles/amsterdam/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Haal OSM-gebouwen op via Overpass en sla op als GeoJSON.',
    )
    parser.add_argument(
        '--bbox',
        nargs=4,
        type=float,
        required=True,
        metavar=('MIN_LON', 'MIN_LAT', 'MAX_LON', 'MAX_LAT'),
        help='Bounding box als vier getallen: minLon minLat maxLon maxLat.',
    )
    parser.add_argument(
        '--output',
        required=True,
        metavar='PAD',
        help='Uitvoerbestand voor de samengevoegde GeoJSON FeatureCollection.',
    )
    parser.add_argument(
        '--tile-cache-dir',
        default=None,
        metavar='MAP',
        help='Map voor de tegel-cache (optioneel; wordt aangemaakt indien nodig).',
    )
    parser.add_argument(
        '--fallback-tile-cache-dir',
        default=None,
        metavar='MAP',
        help='Tegel-cache van een bovenliggend basis-scenario (optioneel).',
    )
    args = parser.parse_args()

    from buildings_fetcher.core.buildings_fetcher_core import fetch_buildings_overpass  # noqa: PLC0415

    tile_cache_dir          = Path(args.tile_cache_dir)          if args.tile_cache_dir          else None
    fallback_tile_cache_dir = Path(args.fallback_tile_cache_dir) if args.fallback_tile_cache_dir else None

    print(f'Bbox              : {args.bbox}')
    if tile_cache_dir:
        print(f'Tegel-cache       : {tile_cache_dir}')
    if fallback_tile_cache_dir:
        print(f'Fallback-cache    : {fallback_tile_cache_dir}')

    result = fetch_buildings_overpass(
        bbox=args.bbox,
        tile_cache_dir=tile_cache_dir,
        fallback_tile_cache_dir=fallback_tile_cache_dir,
    )

    n        = len(result.get('features', []))
    partial  = result.get('properties', {}).get('_partial', False)

    print(f'Gebouwen gevonden : {n}')
    if partial:
        print('Waarschuwing      : resultaat is onvolledig (_partial=True); '
              'niet alle tegels zijn opgehaald.', file=sys.stderr)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    print(f'Geschreven naar   : {output_path}')


if __name__ == '__main__':
    main()
