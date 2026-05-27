"""
Verkeersnetwerk-visualisatie — Flask back-end
=============================================

Start:
    python server.py [--data <map>] [--port <poort>]

Standaard worden GeoJSON-bestanden gezocht in dezelfde map als dit script.
Gebruik --data om een andere map op te geven.

Bestandsconventie:
    {areaId}-NETWORK-{MODE}.geojson
    {areaId}-ROUTES-{MODE}.geojson
    {areaId}-ZONE-{MODE}.geojson

API:
    GET /                                      → index.html
    GET /api/geojson?areaId=…&mode=…&type=…   → GeoJSON-bestand
         type ∈ {NETWORK, ROUTES, ZONE}
    GET /api/areas                             → beschikbare (areaId, mode, name)-combinaties
    GET /api/setdir?path=…                     → stel data-map in, geeft areas terug
"""

import argparse
import json
import os
import re
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description='Verkeersnetwerk-visualisatie server')
parser.add_argument('--data', default=os.path.dirname(os.path.abspath(__file__)),
                    help='Map met GeoJSON-bestanden (standaard: scriptmap)')
parser.add_argument('--port', type=int, default=5000,
                    help='TCP-poort (standaard: 5000)')
args, _ = parser.parse_known_args()

DATA_DIR   = Path(args.data).resolve()
STATIC_DIR = Path(os.path.dirname(os.path.abspath(__file__))).resolve()

VALID_TYPES = {'NETWORK', 'ROUTES', 'ZONE'}
_SAFE_RE    = re.compile(r'^[A-Za-z0-9_\-]+$')

app = Flask(__name__, static_folder=None)

# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def _safe(value: str) -> bool:
    return bool(value and _SAFE_RE.match(value))


def _geojson_path(area_id: str, mode: str, file_type: str) -> Path:
    filename = f"{area_id}-{file_type}-{mode}.geojson"
    return DATA_DIR / filename


def _discover_areas():
    """
    Zoek alle beschikbare (areaId, mode)-combinaties in DATA_DIR.
    Leest 'name' uit top-level GeoJSON properties indien beschikbaar.
    """
    areas   = []
    pattern = re.compile(r'^(.+)-NETWORK-([A-Za-z0-9_]+)\.geojson$')
    for f in sorted(DATA_DIR.glob('*-NETWORK-*.geojson')):
        m = pattern.match(f.name)
        if not m:
            continue
        area_id = m.group(1)
        mode    = m.group(2)
        name    = area_id
        try:
            with open(f, encoding='utf-8') as fh:
                data = json.load(fh)
                name = data.get('properties', {}).get('name', area_id)
        except Exception:
            pass
        areas.append({'areaId': area_id, 'mode': mode, 'name': name})
    return areas

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return send_from_directory(str(STATIC_DIR), 'index.html')


@app.route('/api/areas')
def api_areas():
    """Geeft [{ areaId, mode, name }, ...] voor de huidige data-map."""
    return jsonify(_discover_areas())


@app.route('/api/setdir')
def api_setdir():
    """
    Stel de data-map dynamisch in.

    Query-parameters:
        path — volledig pad naar een GeoJSON-bestand of een map

    Response: { dir, areas: [{ areaId, mode, name }, ...] }
    """
    global DATA_DIR
    raw = request.args.get('path', '').strip()
    if not raw:
        abort(400, 'Parameter "path" ontbreekt')

    p = Path(raw).resolve()
    if p.is_file():
        p = p.parent
    if not p.is_dir():
        abort(404, f'Map niet gevonden: {p}')

    DATA_DIR = p
    return jsonify({'dir': str(DATA_DIR), 'areas': _discover_areas()})


@app.route('/api/geojson')
def api_geojson():
    area_id   = request.args.get('areaId',  '')
    mode      = request.args.get('mode',    '').upper()
    file_type = request.args.get('type',    '').upper()

    if not _safe(area_id):
        abort(400, 'Ongeldige of ontbrekende parameter: areaId')
    if not _safe(mode):
        abort(400, 'Ongeldige of ontbrekende parameter: mode')
    if file_type not in VALID_TYPES:
        abort(400, f'Ongeldige parameter type. Toegestaan: {", ".join(sorted(VALID_TYPES))}')

    path = _geojson_path(area_id, mode, file_type)
    if not path.exists():
        abort(404, f'Bestand niet gevonden: {path.name}')

    return send_file(str(path), mimetype='application/geo+json')


@app.errorhandler(400)
@app.errorhandler(404)
def error_handler(e):
    return jsonify(error=str(e.description)), e.code


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print(f'Data-map : {DATA_DIR}')
    print(f'Beschikbare gebieden: {_discover_areas()}')
    print(f'Server   : http://localhost:{args.port}')
    app.run(host='0.0.0.0', port=args.port, debug=True)
