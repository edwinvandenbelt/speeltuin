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
    POST /api/adjust                           -> start adjust-pipeline (achtergrond)
    GET  /api/adjust/<job_id>                  -> status van adjust-job
"""

import argparse
import contextlib
import io
import json
import os
import re
import shutil
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
# Importeer pipeline-functies direct uit de geïnstalleerde packages
# ---------------------------------------------------------------------------

try:
    from adjust.core.adjust_core import run_pipeline as _adjust_run_pipeline
    _ADJUST_AVAILABLE = True
except ImportError as _e:
    _adjust_run_pipeline = None  # type: ignore[assignment]
    _ADJUST_AVAILABLE = False
    print(f'[server] WAARSCHUWING: adjust niet beschikbaar — {_e}')

try:
    from prepare.core.prepare_core import run_pipeline as _prepare_run_pipeline
    _PREPARE_AVAILABLE = True
except ImportError as _e:
    _prepare_run_pipeline = None  # type: ignore[assignment]
    _PREPARE_AVAILABLE = False
    print(f'[server] WAARSCHUWING: prepare niet beschikbaar — {_e}')

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

VALID_TYPES = {'NETWORK', 'ROUTES', 'ZONE', 'COMPARE'}
_SAFE_RE    = re.compile(r'^[A-Za-z0-9_\\-]+$')

app = Flask(__name__, static_folder=None)

# ---------------------------------------------------------------------------
# Achtergrond-jobs
# ---------------------------------------------------------------------------

_jobs = {}          # job_id -> { status, log, returncode, out_dir }
_jobs_lock = threading.Lock()


class _LogStream(io.TextIOBase):
    """Schrijft stdout/stderr van run_pipeline door naar de job-loglijst."""
    def __init__(self, log_list, lock):
        self._log  = log_list
        self._lock = lock
        self._buf  = ''

    def write(self, s):
        self._buf += s
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            with self._lock:
                self._log.append(line)
        return len(s)

    def flush(self):
        if self._buf:
            with self._lock:
                self._log.append(self._buf)
            self._buf = ''


def _run_prepare_job(job_id, out_dir, kwargs):
    """Voer prepare-pipeline direct uit in achtergrondthread."""
    with _jobs_lock:
        _jobs[job_id]['status'] = 'running'
    stream = _LogStream(_jobs[job_id]['log'], _jobs_lock)
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            _prepare_run_pipeline(**kwargs)
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['returncode'] = 0
            _jobs[job_id]['status']     = 'done'
    except Exception as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['log'].append(f'[server] Fout: {exc}')
            _jobs[job_id]['status']     = 'error'
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
        has_compare = (DATA_DIR / f'{area_id}-COMPARE-{mode}.geojson').exists()
        areas.append({'areaId': area_id, 'mode': mode, 'name': name, 'hasCompare': has_compare})
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
    if not _PREPARE_AVAILABLE:
        abort(503, 'prepare-package niet beschikbaar')

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

    kwargs = dict(
        min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat,
        mode=mode, name=name, out_dir=out_dir,
        catalog=body.get('catalog', 'spectrum'),
        schema=body.get('schema', '2023_01'),
        refresh=bool(body.get('refresh')),
        debug=bool(body.get('debug', False)),
    )

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            'status': 'pending',
            'log': [],
            'returncode': None,
            'out_dir': str(out_dir),
        }

    threading.Thread(target=_run_prepare_job, args=(job_id, out_dir, kwargs), daemon=True).start()
    return jsonify({'job_id': job_id}), 202


@app.route('/api/prepare/<job_id>')
def api_prepare_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        abort(404, f'Job niet gevonden: {job_id}')
    return jsonify(job)


@app.route('/api/adjust', methods=['POST'])
def api_adjust():
    """
    Start de adjust-pipeline als achtergrondproces.

    Body (JSON):
        area_id   - bestaande area-id (bronmap = DATA_DIR)
        mode      - transportmodus (CAR / BIKE / PEDESTRIAN)
        changes   - array van wijzigingen (zoneId/nodeId + production/attraction)
    """
    body = request.get_json(force=True, silent=True) or {}

    area_id       = str(body.get('area_id',       '')).strip()
    mode          = str(body.get('mode',          'CAR')).upper()
    changes       = body.get('changes', [])
    scenario_name = str(body.get('scenario_name', '')).strip() or None

    if not area_id:
        abort(400, 'Parameter "area_id" ontbreekt')
    if not isinstance(changes, list) or not changes:
        abort(400, 'Parameter "changes" moet een niet-lege array zijn')
    if not _ADJUST_AVAILABLE:
        abort(503, 'adjust-package niet beschikbaar')

    src_dir     = DATA_DIR
    routes_file = src_dir / f'{area_id}-ROUTES-{mode}.geojson'
    if not routes_file.exists():
        abort(404, f'Routes-bestand niet gevonden: {routes_file.name}')

    new_area_id  = str(uuid.uuid4())
    changes_file = DATA_DIR / f'{new_area_id}-changes.json'
    changes_file.write_text(json.dumps(changes, ensure_ascii=False), encoding='utf-8')

    # adjust_core leest .area-uuid uit 'folder' om bronbestanden te vinden.
    (DATA_DIR / '.area-uuid').write_text(area_id, encoding='utf-8')

    # Output in submap DATA_DIR/{new_area_id}/ zodat source != output
    output_folder = DATA_DIR / new_area_id

    kwargs = dict(
        folder=src_dir,
        changes=str(changes_file),
        output_folder=output_folder,
        routes_path=routes_file,
        new_area_id=new_area_id,
        min_link_trips=1.0,
        refresh=False,
        debug=True,
    )

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            'status':        'pending',
            'log':           [],
            'returncode':    None,
            'out_dir':       str(DATA_DIR),
            'new_area_id':   new_area_id,
            'scenario_name': scenario_name,
            'compare_url':   None,
        }

    threading.Thread(target=_run_adjust_job,
                     args=(job_id, kwargs, area_id, new_area_id, mode, scenario_name),
                     daemon=True).start()
    return jsonify({'job_id': job_id}), 202


def _run_adjust_job(job_id, kwargs, src_area_id, new_area_id, mode, scenario_name):
    """Voer adjust-pipeline direct uit in achtergrondthread."""
    with _jobs_lock:
        _jobs[job_id]['status'] = 'running'
    stream = _LogStream(_jobs[job_id]['log'], _jobs_lock)
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            _adjust_run_pipeline(**kwargs)
        stream.flush()

        # Kopieer output-bestanden van submap naar DATA_DIR
        sub_dir = DATA_DIR / new_area_id
        if sub_dir.is_dir():
            for f in sub_dir.iterdir():
                if f.is_file():
                    shutil.copy2(str(f), str(DATA_DIR / f.name))

        # Patch top-level properties in output-GeoJSON met scenario_name
        if scenario_name:
            _patch_geojson_properties(new_area_id, mode, scenario_name)

        # Herstel .area-uuid naar new_area_id zodat een volgende adjust hierop aansluit
        (DATA_DIR / '.area-uuid').write_text(new_area_id, encoding='utf-8')

        compare_file = DATA_DIR / f'{new_area_id}-COMPARE-{mode}.geojson'
        compare_url  = (f'/api/geojson?areaId={new_area_id}&mode={mode}&type=COMPARE'
                        if compare_file.exists() else None)
        with _jobs_lock:
            _jobs[job_id]['returncode']  = 0
            _jobs[job_id]['status']      = 'done'
            _jobs[job_id]['compare_url'] = compare_url
    except Exception as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['log'].append(f'[server] Fout: {exc}')
            _jobs[job_id]['status']     = 'error'
            _jobs[job_id]['returncode'] = -1


def _patch_geojson_properties(area_id, mode, name):
    """Pas top-level properties.name en properties.area_id aan in alle output-GeoJSON's."""
    for file_type in ('NETWORK', 'ZONE', 'FEEDLINK', 'ROUTES', 'COMPARE'):
        path = DATA_DIR / f'{area_id}-{file_type}-{mode}.geojson'
        if not path.exists():
            continue
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
            props = data.setdefault('properties', {})
            props['area_id'] = area_id
            props['name']    = name
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, ensure_ascii=False)
        except Exception as exc:
            print(f'[server] Kon {path.name} niet patchen: {exc}')


@app.route('/api/adjust/<job_id>')
def api_adjust_status(job_id):
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
    print(f'prepare  : {"beschikbaar" if _PREPARE_AVAILABLE else "NIET beschikbaar"}')
    print(f'adjust   : {"beschikbaar" if _ADJUST_AVAILABLE else "NIET beschikbaar"}')
    print(f'Beschikbare gebieden: {_discover_areas()}')
    print(f'Server   : http://localhost:{args.port}')
    app.run(host='0.0.0.0', port=args.port, debug=True)
