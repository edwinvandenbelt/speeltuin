"""
Verkeersnetwerk-visualisatie — Flask back-end
=============================================

Start:
    python server.py [--data <map>] [--port <poort>]

API:
    GET  /                                     -> index.html
    GET  /api/geojson?areaId=&mode=&type=      -> GeoJSON-bestand
    GET  /api/areas                            -> beschikbare gebieden
    GET  /api/setdir?path=                     -> stel data-map in
    POST /api/prepare                          -> start prepare-pipeline (achtergrond)
    GET  /api/prepare/<job_id>                 -> status van een job
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

# Laad .env uit de werkdirectory (of scriptmap) indien aanwezig
try:
    from dotenv import load_dotenv
    _env_file = Path(os.getcwd()) / '.env'
    if not _env_file.exists():
        _env_file = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
        print(f'.env geladen: {_env_file}')
except ImportError:
    pass  # python-dotenv niet geïnstalleerd — env vars moeten al gezet zijn

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
_SAFE_RE    = re.compile(r'^[A-Za-z0-9_\\-]+$')

app = Flask(__name__, static_folder=None)

# ---------------------------------------------------------------------------
# Achtergrond-jobs
# ---------------------------------------------------------------------------

_jobs = {}          # job_id -> { status, log, returncode, out_dir }
_jobs_lock = threading.Lock()


def _run_prepare_job(job_id, cmd):
    """Voer prepare-pipeline uit in achtergrondthread."""
    with _jobs_lock:
        _jobs[job_id]['status'] = 'running'
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=os.environ.copy(),   # geeft geladen .env-variabelen door aan subproces
        )
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ''):
            with _jobs_lock:
                _jobs[job_id]['log'].append(line.rstrip())
        proc.wait()
        with _jobs_lock:
            _jobs[job_id]['returncode'] = proc.returncode
            _jobs[job_id]['status'] = 'done' if proc.returncode == 0 else 'error'
    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id]['log'].append(f'[server] Fout: {exc}')
            _jobs[job_id]['status'] = 'error'
            _jobs[job_id]['returncode'] = -1

# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def _safe(value):
    return bool(value and _SAFE_RE.match(value))


def _geojson_path(area_id, mode, file_type):
    return DATA_DIR / f"{area_id}-{file_type}-{mode}.geojson"


def _discover_areas():
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
    return jsonify(_discover_areas())


@app.route('/api/setdir')
def api_setdir():
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


@app.route('/api/prepare', methods=['POST'])
def api_prepare():
    """
    Start de prepare-pipeline als achtergrondproces.

    Body (JSON):
        name                              - gebiedsnaam
        mode                              - transportmodus (CAR / BIKE / PEDESTRIAN)
        min_lon, min_lat, max_lon, max_lat - bbox in decimale graden
        out_dir                           - (optioneel) uitvoermap; standaard DATA_DIR
        refresh                           - (optioneel) bool
    """
    body = request.get_json(force=True, silent=True) or {}

    name    = str(body.get('name', '')).strip()
    mode    = str(body.get('mode', 'CAR')).upper()
    out_dir = Path(body.get('out_dir') or str(DATA_DIR)).resolve()

    try:
        min_lon = float(body['min_lon'])
        min_lat = float(body['min_lat'])
        max_lon = float(body['max_lon'])
        max_lat = float(body['max_lat'])
    except (KeyError, ValueError, TypeError):
        abort(400, 'Ongeldige of ontbrekende bbox-parameters')

    if not name:
        abort(400, 'Parameter "name" ontbreekt')

    out_dir.mkdir(parents=True, exist_ok=True)

    # Schrijf altijd een nieuwe area_id naar .area-uuid zodat elke run
    # eigen outputbestanden krijgt en vorige runs niet worden overschreven.
    uuid_file = out_dir / '.area-uuid'
    uuid_file.write_text(str(uuid.uuid4()), encoding='utf-8')

    cmd = [
        sys.executable, '-m', 'prepare.prepare_runner',
        str(min_lon), str(min_lat), str(max_lon), str(max_lat),
        mode, name, str(out_dir),
    ]
    if body.get('refresh'):
        cmd.append('--refresh')

    # Stabiele job_id op basis van naam + modus zodat hetzelfde gebied
    # niet meerdere keren tegelijk geprepareerd kan worden.
    job_id = str(uuid.uuid4())

    with _jobs_lock:
        _jobs[job_id] = {
            'status': 'pending',
            'log': [],
            'returncode': None,
            'out_dir': str(out_dir),
        }

    threading.Thread(target=_run_prepare_job, args=(job_id, cmd), daemon=True).start()
    return jsonify({'job_id': job_id}), 202


@app.route('/api/prepare/<job_id>')
def api_prepare_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        abort(404, f'Job niet gevonden: {job_id}')
    return jsonify(job)


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
