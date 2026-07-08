"""
Verkeersnetwerk-visualisatie — Flask back-end (OGC API Features + Processes)
============================================================================

Start:
    python server.py [--data <map>] [--port <poort>]

OGC API:
    GET  /                                        -> f=html: SPA; f=json: landing page
    GET  /conformance
    GET  /collections                             -> 7 collections
    GET  /collections/{id}
    GET  /collections/{id}/items
    GET  /collections/{id}/items/{featureId}      -> 501
    GET  /processes                               -> alleen beschikbare processen
    GET  /processes/{processId}
    POST /processes/{processId}/execution
    GET  /jobs
    GET  /jobs/{jobId}
    GET  /jobs/{jobId}/results
"""

import argparse
import contextlib
import datetime as _dt
import io
import json
import os
import re
import shutil
import threading
import urllib.request as _urllib_req
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, make_response, request, send_from_directory
from flask_compress import Compress

# ---------------------------------------------------------------------------
# GeoParquet-ondersteuning (optioneel)
# ---------------------------------------------------------------------------

try:
    import geopandas as _gpd
    import pyarrow.parquet as _pq
    _GEOPANDAS_AVAILABLE = True
except ImportError:
    _gpd = None  # type: ignore[assignment]
    _pq  = None  # type: ignore[assignment]
    _GEOPANDAS_AVAILABLE = False

_GEOPARQUET_EXTS = ('.geoparquet', '.parquet')

# ---------------------------------------------------------------------------
# .env laden
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv
    _env_file = Path(os.getcwd()) / '.env'
    if not _env_file.exists():
        _env_file = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
        print(f'.env geladen: {_env_file}')
except ImportError:
    pass  # python-dotenv niet geïnstalleerd

# ---------------------------------------------------------------------------
# Pipeline-imports
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

try:
    from flow_scaler.core.flow_scaler_core import (
        load_purpose_index, parse_date, normalise_temperature,
        normalise_weather, filterNetwork, determineIndiceKeys,
        read_indexes, applyIndices, Params as FlowScalerParams,
    )
    _FLOW_SCALER_AVAILABLE = True
except ImportError as _e:
    load_purpose_index = normalise_temperature = normalise_weather = None  # type: ignore[assignment]
    parse_date = filterNetwork = determineIndiceKeys = read_indexes = applyIndices = None  # type: ignore[assignment]
    FlowScalerParams = None  # type: ignore[assignment,misc]
    _FLOW_SCALER_AVAILABLE = False
    print(f'[server] WAARSCHUWING: flow_scaler niet beschikbaar — {_e}')

try:
    from whatif.nvp_whatif_data_lib import read_data_geojson as _whatif_read_data_geojson
    from whatif.nvp_whatif_data_lib import export_network_whatif as _whatif_export_network
    from whatif.nvp_whatif_lib import (
        prepare_data             as _wi_prepare_data,
        initialize_weights       as _wi_initialize_weights,
        initialize_mask          as _wi_initialize_mask,
        get_nsegments            as _wi_get_nsegments,
        get_selection            as _wi_get_selection,
        clean_trips              as _wi_clean_trips,
        calibrate_tripvolumes    as _wi_calibrate_tripvolumes,
        get_graphs_base          as _wi_get_graphs_base,
        get_ods                  as _wi_get_ods,
        selected_od_flows        as _wi_selected_od_flows,
        adopt_reduction          as _wi_adopt_reduction,
        get_new_paths            as _wi_get_new_paths,
        full_assignment          as _wi_full_assignment,
        get_difference_flows     as _wi_get_difference_flows,
    )
    _WHATIF_AVAILABLE = True
except ImportError as _e:
    _whatif_read_data_geojson = _whatif_export_network = None  # type: ignore[assignment]
    _wi_prepare_data = _wi_initialize_weights = _wi_initialize_mask = None  # type: ignore[assignment]
    _wi_get_nsegments = _wi_get_selection = _wi_clean_trips = None  # type: ignore[assignment]
    _wi_calibrate_tripvolumes = _wi_get_graphs_base = _wi_get_ods = None  # type: ignore[assignment]
    _wi_selected_od_flows = _wi_adopt_reduction = _wi_get_new_paths = None  # type: ignore[assignment]
    _wi_full_assignment = _wi_get_difference_flows = None  # type: ignore[assignment]
    _WHATIF_AVAILABLE = False
    print(f'[server] WAARSCHUWING: what_if_quick_scan niet beschikbaar — {_e}')

from buildings_fetcher.core.buildings_fetcher_core import (  # noqa: E402
    BUILDINGS_QUERY_VER as _BUILDINGS_QUERY_VER,
    fetch_buildings_overpass as _fetch_buildings_overpass,
)

from traffic_signs_fetcher.core.traffic_signs_fetcher_core import (  # noqa: E402
    TRAFFIC_SIGNS_QUERY_VER as _TRAFFIC_SIGNS_QUERY_VER,
    is_netherlands as _is_netherlands,
    download_ndw_dataset as _download_ndw_dataset,
    fetch_traffic_signs_ndw as _fetch_traffic_signs_ndw,
    fetch_traffic_signs_overpass as _fetch_traffic_signs_overpass,
)

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
_SAFE_RE   = re.compile(r'^[A-Za-z0-9_\-]+$')


def _work_dir() -> Path:
    """Submap van DATA_DIR waar alle gegenereerde bestanden worden opgeslagen."""
    d = DATA_DIR / 'work'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _has_network_file(directory: Path, area_id: str) -> bool:
    """Controleer of de map een NETWORK-bestand bevat (GeoJSON of GeoParquet)."""
    if any(directory.glob(f'{area_id}-NETWORK-*.geojson')):
        return True
    if _GEOPANDAS_AVAILABLE:
        for ext in _GEOPARQUET_EXTS:
            if any(directory.glob(f'{area_id}-NETWORK-*{ext}')):
                return True
    return False


def _find_data_file(directory: Path, stem: str) -> 'Path | None':
    """Zoek een geodata-bestand: eerst GeoJSON, dan GeoParquet (als geopandas beschikbaar is)."""
    for ext in ('.geojson', '.json'):
        p = directory / f'{stem}{ext}'
        if p.exists():
            return p
    if _GEOPANDAS_AVAILABLE:
        for ext in _GEOPARQUET_EXTS:
            p = directory / f'{stem}{ext}'
            if p.exists():
                return p
    return None


def _read_geodata(path: Path) -> dict:
    """Lees een GeoJSON of GeoParquet bestand en geef een GeoJSON FeatureCollection dict terug.

    Voor GeoParquet worden top-level properties (name, area_id, bbox, …) opgeslagen in de
    Parquet-bestandsmetadata onder de sleutel ``geojson_properties``.  Als die metadata
    ontbreekt, wordt een lege properties-dict gebruikt.
    """
    if path.suffix.lower() in _GEOPARQUET_EXTS:
        if not _GEOPANDAS_AVAILABLE:
            raise ImportError(
                'geopandas en pyarrow zijn vereist voor het lezen van GeoParquet-bestanden. '
                'Installeer ze via: pip install geopandas pyarrow'
            )
        gdf = _gpd.read_parquet(path)  # type: ignore[union-attr]
        # Herprojecteer naar WGS 84 (EPSG:4326) als de CRS afwijkt
        if gdf.crs is not None and not gdf.crs.equals('EPSG:4326'):
            gdf = gdf.to_crs('EPSG:4326')
        fc: dict = json.loads(gdf.to_json())
        # Kolommen die als JSON-string zijn opgeslagen in Parquet terugzetten naar Python-objecten
        # (geopandas slaat complexe types op als serialised JSON string; to_json() emit ze as-is)
        for feat in fc.get('features', []):
            props = feat.get('properties') or {}
            for key, val in props.items():
                if isinstance(val, str) and len(val) > 1 and val[0] in ('{', '['):
                    try:
                        props[key] = json.loads(val)
                    except (json.JSONDecodeError, ValueError):
                        pass
        # Probeer top-level properties te herstellen uit Parquet-bestandsmetadata.
        # Ondersteunt zowel de eigen 'geojson_properties'-key als de GMT-productiepipeline
        # die 'gmt_properties' schrijft (met o.a. name, areaId, baseAreaId, bbox).
        try:
            file_meta = _pq.read_metadata(path).metadata  # type: ignore[union-attr]
            raw = file_meta.get(b'geojson_properties') or file_meta.get(b'gmt_properties')
            if raw:
                fc['properties'] = json.loads(raw.decode('utf-8'))
        except Exception:
            pass
        return fc
    # GeoJSON / JSON
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# OGC API metadata
# ---------------------------------------------------------------------------

_COLLECTIONS = {
    'areas': {
        'title': 'Beschikbare gebieden',
        'description': 'Alle beschikbare verkeersgebieden in de werkmap.',
    },
    'network': {
        'title': 'Verkeersnetwerk',
        'description': 'Wegvakken en verkeersvolumes per gebied en transportmodus.',
    },
    'routes': {
        'title': 'Routes',
        'description': 'Ritten en routepaden per gebied en transportmodus.',
    },
    'zones': {
        'title': 'Zones',
        'description': 'Verkeerstoedelingszones per gebied en transportmodus.',
    },
    'feedlinks': {
        'title': 'Aansluitingslinks',
        'description': 'Aansluitingslinks per gebied en transportmodus.',
    },
    'comparison': {
        'title': 'Vergelijking',
        'description': 'Verschilnetwerk ten opzichte van het basisscenario.',
    },
    'flows': {
        'title': 'Verkeersflows (geschaald)',
        'description': 'Verkeersflows geschaald naar datum, weer en reismotief.',
    },
    'buildings': {
        'title': 'Gebouwen',
        'description': 'Gebouwen in het studiegebied (OpenStreetMap / Overpass, gecached).',
    },
    'traffic_signs': {
        'title': 'Verkeersborden',
        'description': 'Verkeersborden in het studiegebied (NDW voor NL, OSM Overpass voor buitenland, gecached).',
    },
    'changes': {
        'title': 'Wijzigingen',
        'description': 'Gecumuleerde wijzigingen in de scenario-keten voor een gebied.',
    },
}

# Mapping van collection-id naar bestandstype-suffix
_COLLECTION_FILE_TYPE = {
    'network':    'NETWORK',
    'routes':     'ROUTES',
    'zones':      'ZONE',
    'feedlinks':  'FEEDLINK',
    'comparison': 'COMPARE',
}

_PROCESS_DESCRIPTIONS = {
    'prepare': {
        'id': 'prepare',
        'title': 'Gebied voorbereiden',
        'description': 'Download en verwerk verkeersgegevens voor een nieuw gebied.',
        'version': '1.0.0',
        'jobControlOptions': ['async-execute'],
        'outputTransmission': ['value'],
        'inputs': {
            'name':       {'title': 'Gebiedsnaam', 'schema': {'type': 'string'}, 'minOccurs': 1},
            'mode':       {'title': 'Modus (enkelvoudig, achterwaartse compatibiliteit)', 'schema': {'type': 'string', 'enum': ['CAR', 'BIKE', 'PEDESTRIAN']}, 'minOccurs': 0},
            'modes':      {'title': 'Modi', 'schema': {'type': 'array', 'items': {'type': 'string', 'enum': ['CAR', 'BIKE', 'PEDESTRIAN']}}, 'minOccurs': 0},
            'mode_label': {'title': 'Modusaanduiding (bijv. MIXED)', 'schema': {'type': 'string'}, 'minOccurs': 0},
            'min_lon':    {'title': 'Min. lengtegraad', 'schema': {'type': 'number'}, 'minOccurs': 1},
            'min_lat':    {'title': 'Min. breedtegraad', 'schema': {'type': 'number'}, 'minOccurs': 1},
            'max_lon':    {'title': 'Max. lengtegraad', 'schema': {'type': 'number'}, 'minOccurs': 1},
            'max_lat':    {'title': 'Max. breedtegraad', 'schema': {'type': 'number'}, 'minOccurs': 1},
            'catalog':    {'title': 'Catalogus', 'schema': {'type': 'string'}, 'minOccurs': 0},
            'schema':     {'title': 'Schema', 'schema': {'type': 'string'}, 'minOccurs': 0},
            'refresh':    {'title': 'Vernieuwen', 'schema': {'type': 'boolean'}, 'minOccurs': 0},
            'debug':      {'title': 'Debug', 'schema': {'type': 'boolean'}, 'minOccurs': 0},
        },
        'outputs': {
            'collection': {'title': 'Collectie-URL', 'schema': {'type': 'string'}},
        },
    },
    'adjust': {
        'id': 'adjust',
        'title': 'Scenario aanpassen',
        'description': 'Herbereken verkeersstromen op basis van zone-wijzigingen.',
        'version': '1.0.0',
        'jobControlOptions': ['async-execute'],
        'outputTransmission': ['value'],
        'inputs': {
            'area_id':       {'title': 'Gebied-ID', 'schema': {'type': 'string'}, 'minOccurs': 1},
            'mode':          {'title': 'Modus', 'schema': {'type': 'string'}, 'minOccurs': 1},
            'changes':       {'title': 'Wijzigingen', 'schema': {'type': 'array'}, 'minOccurs': 1},
            'scenario_name': {'title': 'Scenarionaam', 'schema': {'type': 'string'}, 'minOccurs': 0},
            'debug':         {'title': 'Debug', 'schema': {'type': 'boolean'}, 'minOccurs': 0},
        },
        'outputs': {
            'new_area_id': {'title': 'Nieuw gebied-ID', 'schema': {'type': 'string'}},
            'collection':  {'title': 'Collectie-URL', 'schema': {'type': 'string'}},
            'compare_url': {'title': 'Vergelijkings-URL', 'schema': {'type': 'string'}},
        },
    },
    'whatif-road-closure': {
        'id': 'whatif-road-closure',
        'title': 'What-if wegafsluiting',
        'description': 'Simuleer de gevolgen van het afsluiten van één of meer wegvakken.',
        'version': '1.0.0',
        'jobControlOptions': ['async-execute'],
        'outputTransmission': ['value'],
        'inputs': {
            'area_id':          {'title': 'Gebied-ID', 'schema': {'type': 'string'}, 'minOccurs': 1},
            'mode':             {'title': 'Modus', 'schema': {'type': 'string'}, 'minOccurs': 1},
            'selected_links':   {'title': 'Geselecteerde links', 'schema': {'type': 'array', 'items': {'type': 'integer'}}, 'minOccurs': 1},
            'direction':        {'title': 'Richting', 'schema': {'type': 'string', 'enum': ['both', 'same', 'opposite']}, 'minOccurs': 0},
            'scenario_name':    {'title': 'Scenarionaam', 'schema': {'type': 'string'}, 'minOccurs': 0},
            'nroutes':          {'title': 'Aantal routes', 'schema': {'type': 'integer'}, 'minOccurs': 0},
            'motive':           {'title': 'Reismotief', 'schema': {'type': 'string'}, 'minOccurs': 0},
            'period':           {'title': 'Tijdvak', 'schema': {'type': 'string'}, 'minOccurs': 0},
            'measure':          {'title': 'Maatregel', 'schema': {'type': 'string', 'enum': ['closure', 'capacity', 'speed']}, 'minOccurs': 0},
            'reduction_factor': {'title': 'Reductiefactor', 'schema': {'type': 'number'}, 'minOccurs': 0},
        },
        'outputs': {
            'new_area_id': {'title': 'Nieuw gebied-ID', 'schema': {'type': 'string'}},
            'collection':  {'title': 'Collectie-URL', 'schema': {'type': 'string'}},
        },
    },
    'delete-area': {
        'id': 'delete-area',
        'title': 'Gebied verwijderen',
        'description': 'Verwijder een gebied en alle bijbehorende bestanden definitief.',
        'version': '1.0.0',
        'jobControlOptions': ['sync-execute'],
        'outputTransmission': ['value'],
        'inputs': {
            'id': {'title': 'Gebied-ID', 'schema': {'type': 'string'}, 'minOccurs': 1},
        },
        'outputs': {
            'deleted': {'title': 'Verwijderd gebied-ID', 'schema': {'type': 'string'}},
        },
    },
    'set-directory': {
        'id': 'set-directory',
        'title': 'Data-map instellen',
        'description': 'Stel de werkmap in waaruit gebieden worden geladen.',
        'version': '1.0.0',
        'jobControlOptions': ['sync-execute'],
        'outputTransmission': ['value'],
        'inputs': {
            'path': {'title': 'Pad', 'schema': {'type': 'string'}, 'minOccurs': 1},
        },
        'outputs': {
            'dir':   {'title': 'Ingestelde map', 'schema': {'type': 'string'}},
            'areas': {'title': 'Beschikbare gebieden', 'schema': {'type': 'array'}},
        },
    },
}

# ---------------------------------------------------------------------------
# What-if model-coëfficiënten
# ---------------------------------------------------------------------------

_WI_FRACT_CHANGE         = [0.10, 0.25, 0.50, 0.80, 0.95]
_WI_MIN_NVP              = 10
_WI_MIN_RADIUS_ODNODE    = 200
_WI_CWEIGHT_ADD          = 0.3
_WI_POWER_RATIO          = {'capacity': 0.45, 'speed': 0.20}
_WI_MOTIVES              = {'totaal': 0, 'werk': 1, 'zakelijk': 2, 'onderwijs': 3,
                             'recreatief': 4, 'winkel': 5, 'overig': 6}
_WI_PERIODS              = {'etmaal': 0, 'ochtendspits': 1, 'avondspits': 2, 'restdag': 3}

# ---------------------------------------------------------------------------
# Flask-app
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=None)
Compress(app)

# ---------------------------------------------------------------------------
# Job-store
# ---------------------------------------------------------------------------

_jobs: dict = {}
_jobs_lock  = threading.Lock()
# Serialiseert redirect_stdout/redirect_stderr over alle job-threads: contextlib.redirect_*
# past sys.stdout/sys.stderr globaal aan, dus gelijktijdige jobs zouden elkaars stream
# overschrijven.  Door de pipeline-uitvoering te serialiseren voorkom je dat.
_pipeline_stdout_lock = threading.Lock()

# ---------------------------------------------------------------------------
# NDW-achtergronddownload (verkeersborden NL)
# ---------------------------------------------------------------------------

# _ndw_ready wordt gezet zodra het NDW-bestand beschikbaar is (of de download
# is mislukt).  Route-handlers voor traffic_signs wachten op dit event.
_ndw_ready:  threading.Event = threading.Event()
_ndw_error:  'str | None'    = None


def _ensure_ndw_data() -> None:
    """Controleer of het NDW-bestand aanwezig is; download het indien nodig."""
    global _ndw_error
    p = DATA_DIR / 'ndw_traffic_signs.json'
    if p.exists():
        _ndw_ready.set()
        return
    print('[server] NDW-verkeersborden downloaden …')
    ok = _download_ndw_dataset(p)
    if ok:
        print(f'[server] NDW-verkeersborden opgeslagen: {p}')
    else:
        _ndw_error = 'NDW-download mislukt'
        print(f'[server]  {_ndw_error}')
    _ndw_ready.set()


threading.Thread(target=_ensure_ndw_data, daemon=True).start()


class _LogStream(io.TextIOBase):
    """Schrijft stdout/stderr van run_pipeline door naar de job-loglijst.

    Thread-safe: meerdere threads (bijv. ThreadPoolExecutor-workers in run_pipeline)
    kunnen gelijktijdig schrijven.  _buf_lock beschermt de buffer; _lock beschermt
    de gedeelde loglijst.
    """
    def __init__(self, log_list, lock):
        self._log      = log_list
        self._lock     = lock
        self._buf      = ''
        self._buf_lock = threading.Lock()

    def write(self, s):
        with self._buf_lock:
            self._buf += s
            lines = []
            while '\n' in self._buf:
                line, self._buf = self._buf.split('\n', 1)
                lines.append(line)
        if lines:
            with self._lock:
                self._log.extend(lines)
        return len(s)

    def flush(self):
        with self._buf_lock:
            remainder = self._buf
            self._buf = ''
        if remainder:
            with self._lock:
                self._log.append(remainder)


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def _safe(value) -> bool:
    return bool(value and _SAFE_RE.match(value))


def _find_area_dir(area_id: str) -> Path:
    """Zoek de work-submap die de bestanden voor area_id bevat."""
    work   = _work_dir()
    direct = work / area_id
    if direct.is_dir() and _has_network_file(direct, area_id):
        return direct
    for subdir in work.iterdir():
        if subdir.is_dir() and _has_network_file(subdir, area_id):
            return subdir
    return direct  # fallback (leidt tot 404 downstream)


def _geojson_path(area_id: str, mode: str, file_type: str) -> Path:
    return _find_area_dir(area_id) / f'{area_id}-{file_type}-{mode}.geojson'


def _data_path(area_id: str, mode: str, file_type: str) -> 'Path | None':
    """Zoek het beste geodata-bestand (GeoJSON heeft voorrang op GeoParquet)."""
    return _find_data_file(_find_area_dir(area_id), f'{area_id}-{file_type}-{mode}')


def _discover_areas() -> list:
    areas   = []
    seen: set = set()
    pattern_geojson    = re.compile(r'^(.+)-NETWORK-([A-Za-z0-9_]+)\.geojson$')
    pattern_geoparquet = re.compile(r'^(.+)-NETWORK-([A-Za-z0-9_]+)\.(?:geo)?parquet$')
    work    = _work_dir()
    for subdir in sorted(work.iterdir()):
        if not subdir.is_dir():
            continue
        # Verzamel NETWORK-kandidaten: GeoJSON heeft voorrang op GeoParquet
        candidates: dict = {}
        for f in sorted(subdir.glob('*-NETWORK-*.geojson')):
            m = pattern_geojson.match(f.name)
            if m:
                candidates[(m.group(1), m.group(2))] = f
        if _GEOPANDAS_AVAILABLE:
            for ext in _GEOPARQUET_EXTS:
                for f in sorted(subdir.glob(f'*-NETWORK-*{ext}')):
                    m = pattern_geoparquet.match(f.name)
                    if m:
                        key = (m.group(1), m.group(2))
                        if key not in candidates:
                            candidates[key] = f
        for (area_id, mode), f in sorted(candidates.items()):
            if (area_id, mode) in seen:
                continue
            seen.add((area_id, mode))
            name    = area_id
            src_area_id = None
            try:
                data        = _read_geodata(f)
                props       = data.get('properties', {})
                name        = props.get('name', area_id)
                src_area_id = props.get('baseAreaId') or None
            except Exception:
                pass
            if not src_area_id:
                src_id_path = subdir / '.src-area-id'
                if src_id_path.exists():
                    try:
                        src_area_id = src_id_path.read_text(encoding='utf-8').strip() or None
                    except Exception:
                        pass
            has_compare    = (subdir / f'{area_id}-COMPARE-{mode}.geojson').exists()
            has_nvp_routes = (subdir / f'{area_id}-NVP-ROUTES-{mode}.parquet').exists()
            areas.append({'areaId': area_id, 'mode': mode, 'name': name,
                          'hasCompare': has_compare, 'srcAreaId': src_area_id,
                          'hasNvpRoutes': has_nvp_routes})
    return areas


def _discover_constituent_modes(area_id: str, src_dir: Path) -> list:
    """Geef de per-modus namen terug waarvoor een ROUTES-bestand bestaat (niet MIXED zelf).

    Gebruikt bij adjust op een MIXED-gebied om te weten welke modi verwerkt moeten worden.
    """
    stem_pat = re.compile(
        r'^' + re.escape(area_id) + r'-ROUTES-([A-Za-z0-9]+)\.(geojson|json|parquet|geoparquet)$'
    )
    modes: list = []
    seen: set   = set()
    for f in sorted(src_dir.iterdir()):
        m = stem_pat.match(f.name)
        if m:
            mode_m = m.group(1).upper()
            if mode_m != 'MIXED' and mode_m not in seen:
                modes.append(mode_m)
                seen.add(mode_m)
    return modes


def _merge_mixed_outputs(new_area_id: str, output_folder: Path, modes: list) -> None:
    """Samenvoegen van per-modus adjust-output naar een MIXED-artefact.

    Per bestandstype:
    - NETWORK, COMPARE: features uit alle modi samenvoegen; mode-property toevoegen indien absent.
    - ZONE, FEEDLINK:   eerste beschikbare per-modus versie overnemen als MIXED-variant.
    - Per-modus NETWORK- en COMPARE-bestanden worden verwijderd zodat _discover_areas
      de uitvoer niet als afzonderlijke CAR/BIKE-gebieden toont.
    """
    # ── NETWORK en COMPARE: merge ────────────────────────────────────────────
    for file_type in ('NETWORK', 'COMPARE'):
        all_features: list = []
        any_found = False
        for m in modes:
            path = output_folder / f'{new_area_id}-{file_type}-{m}.geojson'
            if not path.exists():
                continue
            any_found = True
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except Exception:
                continue
            for feat in data.get('features', []):
                feat.setdefault('properties', {})
                if 'mode' not in feat['properties']:
                    feat['properties']['mode'] = m
            all_features.extend(data.get('features', []))
            path.unlink()   # verwijder per-modus bestand
        if any_found:
            merged_path = output_folder / f'{new_area_id}-{file_type}-MIXED.geojson'
            merged_path.write_text(
                json.dumps({'type': 'FeatureCollection', 'features': all_features},
                           ensure_ascii=False),
                encoding='utf-8',
            )

    # ── ZONE en FEEDLINK: eerste beschikbare modus als MIXED ────────────────
    for file_type in ('ZONE', 'FEEDLINK'):
        for m in modes:
            path = output_folder / f'{new_area_id}-{file_type}-{m}.geojson'
            if path.exists():
                mixed_path = output_folder / f'{new_area_id}-{file_type}-MIXED.geojson'
                if not mixed_path.exists():
                    path.rename(mixed_path)
                else:
                    path.unlink()
                break


def _post_process_mixed_output(new_area_id: str, output_folder: Path,
                               src_area_id: str, src_dir: Path,
                               adjusted_mode: str, all_modes: list) -> None:
    """Verwerk de output van één per-modus adjust-run tot een compleet MIXED-artefact.

    Na een adjust-run voor bijv. CAR op een MIXED-brongebied:
    1. ROUTES voor niet-aangepaste modi van bron kopiëren.
    2. Features van niet-aangepaste modi uit bron-NETWORK-MIXED extraheren.
    3. Aangepaste NETWORK-{mode}.geojson samenvoegen met de overige features
       → NETWORK-MIXED.geojson.  Per-modus bestand verwijderen.
    4. ZONE en FEEDLINK hernoemen van {adjusted_mode} → MIXED.
    5. COMPARE hernoemen van {adjusted_mode} → MIXED.
    """
    import shutil

    other_modes = [m for m in all_modes if m != adjusted_mode]

    # ── 1. ROUTES voor niet-aangepaste modi kopiëren ────────────────────────
    for m in other_modes:
        src_routes = _find_data_file(src_dir, f'{src_area_id}-ROUTES-{m}')
        if src_routes:
            dst = output_folder / f'{new_area_id}-ROUTES-{m}{src_routes.suffix}'
            if not dst.exists():
                shutil.copy2(str(src_routes), str(dst))

    # ── 2. Features van niet-aangepaste modi uit bron halen ─────────────────
    other_features: list = []
    src_network_path = _find_data_file(src_dir, f'{src_area_id}-NETWORK-MIXED')
    if src_network_path is not None:
        try:
            fc_src = _read_geodata(src_network_path)
            for feat in fc_src.get('features', []):
                feat_mode = ((feat.get('properties') or {}).get('mode') or 'CAR').upper()
                if feat_mode != adjusted_mode:
                    other_features.append(feat)
        except Exception as exc:
            print(f'[adjust-mixed] Kon bron-NETWORK-MIXED niet lezen: {exc}')
    else:
        # Geketende aanroep: bron kan per-modus NETWORK-bestanden hebben
        for m in other_modes:
            src_net_m = _find_data_file(src_dir, f'{src_area_id}-NETWORK-{m}')
            if src_net_m:
                try:
                    fc_m = _read_geodata(src_net_m)
                    for feat in fc_m.get('features', []):
                        feat.setdefault('properties', {}).setdefault('mode', m)
                    other_features.extend(fc_m.get('features', []))
                except Exception as exc:
                    print(f'[adjust-mixed] Kon bron-NETWORK-{m} niet lezen: {exc}')

    # ── 3. Aangepaste NETWORK samenvoegen met overige features ───────────────
    adj_network = output_folder / f'{new_area_id}-NETWORK-{adjusted_mode}.geojson'
    adj_features: list = []
    if adj_network.exists():
        try:
            fc_adj = json.loads(adj_network.read_text(encoding='utf-8'))
            for feat in fc_adj.get('features', []):
                feat.setdefault('properties', {}).setdefault('mode', adjusted_mode)
            adj_features = fc_adj.get('features', [])
        except Exception as exc:
            print(f'[adjust-mixed] Kon aangepast NETWORK-{adjusted_mode} niet lezen: {exc}')
    merged_path = output_folder / f'{new_area_id}-NETWORK-MIXED.geojson'
    merged_path.write_text(
        json.dumps({'type': 'FeatureCollection', 'features': adj_features + other_features},
                   ensure_ascii=False),
        encoding='utf-8',
    )
    if adj_network.exists():
        adj_network.unlink()

    # ── 4. ZONE en FEEDLINK hernoemen naar MIXED ─────────────────────────────
    for file_type in ('ZONE', 'FEEDLINK'):
        src_f = output_folder / f'{new_area_id}-{file_type}-{adjusted_mode}.geojson'
        dst_f = output_folder / f'{new_area_id}-{file_type}-MIXED.geojson'
        if src_f.exists() and not dst_f.exists():
            src_f.rename(dst_f)

    # ── 5. COMPARE hernoemen naar MIXED ──────────────────────────────────────
    c_src = output_folder / f'{new_area_id}-COMPARE-{adjusted_mode}.geojson'
    c_dst = output_folder / f'{new_area_id}-COMPARE-MIXED.geojson'
    if c_src.exists() and not c_dst.exists():
        c_src.rename(c_dst)


def _find_local_file(filename: str):
    """Zoek bestand in DATA_DIR en STATIC_DIR; geeft None als niet gevonden."""
    for base in (DATA_DIR, STATIC_DIR):
        p = base / filename
        if p.exists():
            return p
    return None


def _patch_geojson_properties(area_id: str, mode: str, name: str):
    """Pas top-level properties.name en properties.area_id aan in alle output-GeoJSON's."""
    for file_type in ('NETWORK', 'ZONE', 'FEEDLINK', 'ROUTES', 'COMPARE'):
        path = _find_area_dir(area_id) / f'{area_id}-{file_type}-{mode}.geojson'
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


def _get_available_processes() -> set:
    """Geef de set van processIds die momenteel beschikbaar zijn."""
    avail = {'delete-area', 'set-directory'}
    if _PREPARE_AVAILABLE:
        avail.add('prepare')
    if _ADJUST_AVAILABLE:
        avail.add('adjust')
    if _WHATIF_AVAILABLE:
        avail.add('whatif-road-closure')
    return avail


def _job_to_status(job: dict) -> dict:
    """Geef OGC-conform job-statusobject terug (zonder _results)."""
    job_id = job['jobID']
    return {
        'jobID':     job_id,
        'processID': job['processID'],
        'status':    job['status'],
        'log':       job.get('log', []),
        'created':   job.get('created'),
        'started':   job.get('started'),
        'finished':  job.get('finished'),
        'links': [
            {'href': f'/jobs/{job_id}',         'rel': 'self',    'type': 'application/json', 'title': 'Job status'},
            {'href': f'/jobs/{job_id}/results',  'rel': 'results', 'type': 'application/json', 'title': 'Job resultaten'},
        ],
    }


def _ogc_items_response(collection_id: str, data, self_url: str):
    """Wrap een GeoJSON FeatureCollection in de OGC API Features envelope."""
    if not isinstance(data, dict):
        try:
            data = dict(data)
        except Exception:
            data = {'type': 'FeatureCollection', 'features': []}

    features  = data.get('features', [])
    top_props = data.get('properties') if isinstance(data.get('properties'), dict) else {}
    other     = {k: v for k, v in data.items()
                 if k not in ('type', 'features', 'links', 'properties')}
    merged    = {**top_props, **other}

    result: dict = {
        'type':            'FeatureCollection',
        'features':        features,
        'links': [
            {'href': self_url,                   'rel': 'self',       'type': 'application/geo+json', 'title': 'Dit document'},
            {'href': f'/collections/{collection_id}', 'rel': 'collection', 'type': 'application/json',     'title': 'Collectiebeschrijving'},
        ],
        'timeStamp':      _dt.datetime.now(_dt.timezone.utc).isoformat(timespec='seconds'),
        'numberMatched':  len(features),
        'numberReturned': len(features),
    }
    if merged:
        result['properties'] = merged

    resp = make_response(json.dumps(result, ensure_ascii=False))
    resp.headers['Content-Type'] = 'application/geo+json'
    return resp


def _now_iso() -> str:
    return _dt.datetime.utcnow().isoformat() + 'Z'


# ---------------------------------------------------------------------------
# Achtergrond-job runners
# ---------------------------------------------------------------------------

def _run_prepare_job(job_id: str, out_dir: Path, kwargs: dict, name: str, mode_label: str):
    """Voer prepare-pipeline uit in achtergrondthread.

    De nieuwe pipeline-versie accepteert 'modes' (lijst) en 'mode_label' rechtstreeks,
    zodat kwargs ongewijzigd doorgegeven kan worden.
    """
    with _jobs_lock:
        _jobs[job_id]['status']  = 'running'
        _jobs[job_id]['started'] = _now_iso()
    stream = _LogStream(_jobs[job_id]['log'], _jobs_lock)
    try:
        with _pipeline_stdout_lock, \
             contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            _prepare_run_pipeline(**kwargs)
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['returncode'] = 0
            _jobs[job_id]['status']     = 'successful'
            _jobs[job_id]['finished']   = _now_iso()
            _jobs[job_id]['_results']   = {
                'collection': f'/collections/network/items?areaId={name}&mode={mode_label}',
            }
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['log'].append(f'[server] Fout: {type(exc).__name__}: {exc}')
            _jobs[job_id]['status']     = 'failed'
            _jobs[job_id]['returncode'] = -1
            _jobs[job_id]['finished']   = _now_iso()


def _run_adjust_job(job_id: str, kwargs: dict, src_area_id: str,
                    new_area_id: str, mode: str, scenario_name,
                    all_constituent_modes=None):
    """Voer adjust-pipeline uit in achtergrondthread.

    Als *all_constituent_modes* opgegeven is (lijst met ≥2 modi, bijv. ['CAR', 'BIKE'])
    weet de functie dat de bron een MIXED-gebied is.  Na de pipeline-run wordt
    _post_process_mixed_output aangeroepen om de per-modus output samen te voegen
    tot een volledig MIXED-artefact; het resultaat krijgt dan mode='MIXED'.
    """
    with _jobs_lock:
        _jobs[job_id]['status']  = 'running'
        _jobs[job_id]['started'] = _now_iso()
    stream = _LogStream(_jobs[job_id]['log'], _jobs_lock)
    try:
        with _pipeline_stdout_lock, \
             contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            _adjust_run_pipeline(**kwargs)
        stream.flush()

        # Post-process naar MIXED als bron een MIXED-gebied was
        is_mixed = all_constituent_modes and len(all_constituent_modes) > 1
        if is_mixed:
            src_dir = kwargs['folder']
            output_folder = kwargs['output_folder']
            _post_process_mixed_output(
                new_area_id, output_folder,
                src_area_id, src_dir,
                mode, all_constituent_modes,
            )
            result_mode = 'MIXED'
        else:
            result_mode = mode

        if scenario_name:
            _patch_geojson_properties(new_area_id, result_mode, scenario_name)

        compare_file = _geojson_path(new_area_id, result_mode, 'COMPARE')
        compare_url  = (f'/collections/comparison/items?areaId={new_area_id}&mode={result_mode}'
                        if compare_file.exists() else None)

        with _jobs_lock:
            _jobs[job_id]['returncode'] = 0
            _jobs[job_id]['status']     = 'successful'
            _jobs[job_id]['finished']   = _now_iso()
            _jobs[job_id]['_results']   = {
                'new_area_id': new_area_id,
                'collection':  f'/collections/network/items?areaId={new_area_id}&mode={result_mode}',
                'compare_url': compare_url,
            }
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['log'].append(f'[server] Fout: {type(exc).__name__}: {exc}')
            _jobs[job_id]['status']     = 'failed'
            _jobs[job_id]['returncode'] = -1
            _jobs[job_id]['finished']   = _now_iso()


def _run_adjust_job_mixed(job_id: str, base_kwargs: dict, src_area_id: str,
                          new_area_id: str, routes_per_mode: dict, scenario_name):
    """Voer adjust-pipeline uit voor elk samenstellend modus van een MIXED-gebied.

    Volgorde:
    1. Per modus (bijv. CAR, BIKE) de adjust-pipeline draaien met de bijbehorende routes.
    2. Per-modus NETWORK/COMPARE/ZONE/FEEDLINK samenvoegen tot MIXED-artefacten.
    3. Job-status bijwerken.
    """
    with _jobs_lock:
        _jobs[job_id]['status']  = 'running'
        _jobs[job_id]['started'] = _now_iso()
    stream      = _LogStream(_jobs[job_id]['log'], _jobs_lock)
    output_folder = base_kwargs['output_folder']
    try:
        with _pipeline_stdout_lock, \
             contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            for m, routes_path in routes_per_mode.items():
                print(f'[adjust-mixed] Modus {m} verwerken …')
                kwargs_m = {**base_kwargs, 'routes_path': routes_path}
                _adjust_run_pipeline(**kwargs_m)
        stream.flush()

        _merge_mixed_outputs(new_area_id, output_folder, list(routes_per_mode.keys()))

        if scenario_name:
            _patch_geojson_properties(new_area_id, 'MIXED', scenario_name)

        compare_file = _geojson_path(new_area_id, 'MIXED', 'COMPARE')
        compare_url  = (f'/collections/comparison/items?areaId={new_area_id}&mode=MIXED'
                        if compare_file.exists() else None)

        with _jobs_lock:
            _jobs[job_id]['returncode'] = 0
            _jobs[job_id]['status']     = 'successful'
            _jobs[job_id]['finished']   = _now_iso()
            _jobs[job_id]['_results']   = {
                'new_area_id': new_area_id,
                'collection':  f'/collections/network/items?areaId={new_area_id}&mode=MIXED',
                'compare_url': compare_url,
            }
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['log'].append(f'[server] Fout: {type(exc).__name__}: {exc}')
            _jobs[job_id]['status']     = 'failed'
            _jobs[job_id]['returncode'] = -1
            _jobs[job_id]['finished']   = _now_iso()


def _run_whatif_road_closure_job(job_id: str, path_geojson: str, path_csv: str,
                                  output_folder: Path, new_area_id: str, src_area_id: str,
                                  mode: str, selected_links: list, direction: str,
                                  motive: str, period: str, nroutes: int,
                                  measure: str, reduction_factor: float,
                                  scenario_name):
    """Voer de what-if wegafsluiting uit in een achtergrondthread."""
    with _jobs_lock:
        _jobs[job_id]['status']  = 'running'
        _jobs[job_id]['started'] = _now_iso()
    stream = _LogStream(_jobs[job_id]['log'], _jobs_lock)

    try:
        with _pipeline_stdout_lock, \
             contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):

            # ── 1. Inlezen ────────────────────────────────────────────────
            print('[whatif] Netwerk en NVP-routes inlezen …')
            nodes, links, links_opposite, volumes, segments, tripsarr, trippaths = \
                _whatif_read_data_geojson(path_geojson, path_csv)

            # ── 2. Voorbereiden ───────────────────────────────────────────
            print('[whatif] Data voorbereiden …')
            imotive = _WI_MOTIVES[motive]
            iperiod = _WI_PERIODS[period]
            sel_links_grouped = [[lid] for lid in selected_links]

            nodexys, selected_segments, opposite_segments, qsegsmodel, qmodel, segments_to_links = \
                _wi_prepare_data(nodes, links, links_opposite, segments, volumes,
                                 sel_links_grouped, direction, imotive, iperiod)

            # ── 3. Selectie ───────────────────────────────────────────────
            print('[whatif] Ritpaden selecteren …')
            nsel_pass   = 1
            tripweights = _wi_initialize_weights(tripsarr)
            trippaths2, tripweights2, trippaths12, trippaths21 = _wi_get_selection(
                trippaths, tripweights, selected_segments, nsel_pass)

            # ── 4. Aantal segmenten ───────────────────────────────────────
            nsegment, nsegment2 = _wi_get_nsegments(segments, trippaths21)

            # ── 5. Rondritten opschonen ───────────────────────────────────
            print('[whatif] Rondritten opschonen …')
            tripweights2 = _wi_clean_trips(selected_segments, opposite_segments,
                                           tripweights2, trippaths2, trippaths12)

            # ── 6. Kalibratie ─────────────────────────────────────────────
            print('[whatif] Ritvolumes kalibreren …')
            porttrips2_all = _wi_initialize_mask(trippaths2['trip'])
            ratio_model, qsegs_sel, qsegs_sel2 = _wi_calibrate_tripvolumes(
                selected_segments, qsegsmodel,
                trippaths12, trippaths21,
                trippaths2, tripweights2, porttrips2_all,
                nsegment, nsegment2)

            # ── 7. Grafen (basissituatie) ─────────────────────────────────
            print('[whatif] Grafen opbouwen …')
            G, Gback, nodepairs_segs, nodecosts = _wi_get_graphs_base(
                segments, selected_segments, qsegsmodel, nsegment)

            # ── 8. OD-knopen en paden ─────────────────────────────────────
            print('[whatif] OD-relaties bepalen …')
            onodes, dnodes, osegs2, dsegs2, opaths, dpaths = _wi_get_ods(
                G, Gback, segments, nsegment,
                selected_segments, opposite_segments,
                trippaths12, trippaths21,
                trippaths2, tripweights2, porttrips2_all, nsegment2,
                _WI_FRACT_CHANGE, _WI_MIN_NVP, nodexys, _WI_MIN_RADIUS_ODNODE)

            # ── 9. Nieuwe paden (omleidingen) ─────────────────────────────
            print('[whatif] Omleidingspaden zoeken …')
            newpaths, validpaths = _wi_get_new_paths(G, onodes, dnodes, selected_segments)

            # ── 10. OD-flows op geselecteerd segment ──────────────────────
            print('[whatif] OD-flows berekenen …')
            qsegsmodel_od = _wi_selected_od_flows(
                selected_segments, qsegsmodel, qsegs_sel,
                ratio_model, nsegment, nsegment2,
                trippaths12, trippaths21,
                trippaths2, tripweights2, porttrips2_all,
                onodes, dnodes, osegs2, dsegs2, validpaths)

            # ── 11. Reductiefactor toepassen ──────────────────────────────
            qsegsmodel_od = _wi_adopt_reduction(qsegsmodel_od, measure,
                                                reduction_factor, _WI_POWER_RATIO)

            # ── 12. Volledige toewijzing ───────────────────────────────────
            print(f'[whatif] Volledige toewijzing ({nroutes} routes) …')
            qsegsmodel_dmin, qsegsmodel_dplus = _wi_full_assignment(
                segments, selected_segments, nsegment,
                qsegsmodel, qsegsmodel_od,
                G, Gback, nodepairs_segs, nodecosts,
                onodes, dnodes, opaths, dpaths,
                newpaths, validpaths,
                _WI_CWEIGHT_ADD, nroutes)

            # ── 13. Verschilflows links ───────────────────────────────────
            qmodel_dmin, qmodel_dplus = _wi_get_difference_flows(
                links, qmodel, segments_to_links,
                qsegsmodel_dmin, qsegsmodel_dplus)

            # ── 14. Export what-if NETWORK GeoJSON ────────────────────────
            print('[whatif] Resultaat exporteren …')
            output_folder.mkdir(parents=True, exist_ok=True)
            path_network_out = output_folder / f'{new_area_id}-NETWORK-{mode}.geojson'
            _whatif_export_network(links, qmodel, qmodel_dmin, qmodel_dplus,
                                   path_geojson, str(path_network_out))

            # ── 15. Originele ROUTES en ZONE kopiëren ────────────────────
            src_dir = _find_area_dir(src_area_id)
            for file_type in ('ROUTES', 'ZONE', 'FEEDLINK'):
                src_file = src_dir / f'{src_area_id}-{file_type}-{mode}.geojson'
                if src_file.exists():
                    dst_file = output_folder / f'{new_area_id}-{file_type}-{mode}.geojson'
                    shutil.copy2(str(src_file), str(dst_file))

            # ── 16. Patcheer top-level properties ────────────────────────
            if scenario_name:
                _patch_geojson_properties(new_area_id, mode, scenario_name)

            # ── 17. Sla brongebied op voor ScenarioVergelijker ────────────
            (output_folder / '.src-area-id').write_text(src_area_id, encoding='utf-8')

        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['returncode'] = 0
            _jobs[job_id]['status']     = 'successful'
            _jobs[job_id]['finished']   = _now_iso()
            _jobs[job_id]['_results']   = {
                'new_area_id': new_area_id,
                'collection':  f'/collections/network/items?areaId={new_area_id}&mode={mode}',
            }

    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]['log'].append(f'[server] Fout: {type(exc).__name__}: {exc}')
            _jobs[job_id]['status']     = 'failed'
            _jobs[job_id]['returncode'] = -1
            _jobs[job_id]['finished']   = _now_iso()


# ---------------------------------------------------------------------------
# Process execute helpers
# ---------------------------------------------------------------------------

def _execute_prepare(inputs: dict):
    """Start prepare als async job. Geeft (body, 201, headers) terug."""
    if not _PREPARE_AVAILABLE:
        abort(503, 'prepare-package niet beschikbaar')

    name    = str(inputs.get('name', '')).strip()
    out_dir = Path(inputs.get('out_dir') or str(_work_dir() / name)).resolve()

    # Modes: accepteer 'modes' (array) of 'mode' (string, achterwaartse compatibiliteit)
    raw_modes = inputs.get('modes')
    if raw_modes and isinstance(raw_modes, list) and len(raw_modes) > 0:
        modes = [str(m).upper() for m in raw_modes]
    else:
        modes = [str(inputs.get('mode', 'CAR')).upper()]

    # Valideer modes
    _valid_modes = {'CAR', 'BIKE', 'PEDESTRIAN'}
    for m in modes:
        if m not in _valid_modes:
            abort(400, f'Ongeldige modus: {m!r}. Toegestaan: {", ".join(sorted(_valid_modes))}')
    if len(modes) > 1 and 'PEDESTRIAN' in modes:
        abort(400, 'PEDESTRIAN kan niet gecombineerd worden met andere modi')

    # mode_label: expliciet meegegeven of automatisch bepaald
    raw_label  = str(inputs.get('mode_label', '')).strip().upper()
    mode_label = raw_label if raw_label else ('MIXED' if len(modes) > 1 else modes[0])

    try:
        min_lon = float(inputs['min_lon'])
        min_lat = float(inputs['min_lat'])
        max_lon = float(inputs['max_lon'])
        max_lat = float(inputs['max_lat'])
    except (KeyError, ValueError, TypeError):
        abort(400, 'Ongeldige of ontbrekende bbox-parameters')

    if not name:
        abort(400, 'Parameter "name" ontbreekt')

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / '.area-uuid').write_text(name, encoding='utf-8')

    kwargs = dict(
        min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat,
        modes=modes, mode_label=mode_label, name=name, out_dir=out_dir,
        catalog=inputs.get('catalog', 'spectrum'),
        schema=inputs.get('schema', '2023_01'),
        refresh=bool(inputs.get('refresh')),
        debug=bool(inputs.get('debug', False)),
    )

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            'jobID':      job_id,
            'processID':  'prepare',
            'status':     'accepted',
            'log':        [],
            'returncode': None,
            'out_dir':    str(out_dir),
            'created':    _now_iso(),
            'started':    None,
            'finished':   None,
            '_results':   {},
        }

    threading.Thread(target=_run_prepare_job,
                     args=(job_id, out_dir, kwargs, name, mode_label),
                     daemon=True).start()
    return {'jobID': job_id, 'status': 'accepted'}, 201, {'Location': f'/jobs/{job_id}'}


def _execute_adjust(inputs: dict):
    """Start adjust als async job. Geeft (body, 201, headers) terug."""
    if not _ADJUST_AVAILABLE:
        abort(503, 'adjust-package niet beschikbaar')

    area_id       = str(inputs.get('area_id', '')).strip()
    mode          = str(inputs.get('mode', 'CAR')).upper()
    changes       = inputs.get('changes', [])
    scenario_name = str(inputs.get('scenario_name', '')).strip() or None

    if not area_id:
        abort(400, 'Parameter "area_id" ontbreekt')
    if not isinstance(changes, list) or not changes:
        abort(400, 'Parameter "changes" moet een niet-lege array zijn')

    src_dir = _find_area_dir(area_id)

    # ── Bepaal routes-bestand(en) ────────────────────────────────────────────
    if mode == 'MIXED':
        # MIXED-gebied: per samenstellend modus (bijv. CAR, BIKE) een eigen ROUTES-bestand
        constituent_modes = _discover_constituent_modes(area_id, src_dir)
        if not constituent_modes:
            abort(404, f'Geen per-modus ROUTES-bestanden gevonden voor MIXED-gebied: {area_id}')
        routes_per_mode: dict = {}
        for m in constituent_modes:
            rf = _find_data_file(src_dir, f'{area_id}-ROUTES-{m}')
            if rf is None:
                abort(404, f'Routes-bestand niet gevonden: {area_id}-ROUTES-{m}')
            routes_per_mode[m] = rf
    else:
        routes_file = _find_data_file(src_dir, f'{area_id}-ROUTES-{mode}')
        if routes_file is None:
            abort(404, f'Routes-bestand niet gevonden: {area_id}-ROUTES-{mode}')

        # Detecteer of de bron een MIXED-gebied is (heeft ROUTES voor ≥2 modi)
        all_constituent = _discover_constituent_modes(area_id, src_dir)
        is_mixed_source = len(all_constituent) > 1 and mode in all_constituent

    new_area_id = str(uuid.uuid4())
    if scenario_name:
        folder_name = re.sub(r'[^\w\-]', '_', scenario_name.strip())
        folder_name = re.sub(r'_+', '_', folder_name).strip('_') or new_area_id
    else:
        folder_name = new_area_id
    output_folder = _work_dir() / folder_name
    output_folder.mkdir(parents=True, exist_ok=True)

    (output_folder / '.src-area-id').write_text(area_id, encoding='utf-8')

    changes_file = output_folder / f'{new_area_id}-changes.json'
    changes_file.write_text(json.dumps(changes, ensure_ascii=False), encoding='utf-8')

    (src_dir / '.area-uuid').write_text(area_id, encoding='utf-8')

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            'jobID':      job_id,
            'processID':  'adjust',
            'status':     'accepted',
            'log':        [],
            'returncode': None,
            'out_dir':    str(output_folder),
            'created':    _now_iso(),
            'started':    None,
            'finished':   None,
            '_results':   {},
        }

    if mode == 'MIXED':
        base_kwargs = dict(
            folder=src_dir,
            changes=str(changes_file),
            output_folder=output_folder,
            new_area_id=new_area_id,
            min_link_trips=1.0,
            debug=bool(inputs.get('debug', False)),
        )
        threading.Thread(target=_run_adjust_job_mixed,
                         args=(job_id, base_kwargs, area_id, new_area_id,
                               routes_per_mode, scenario_name),
                         daemon=True).start()
    else:
        kwargs = dict(
            folder=src_dir,
            changes=str(changes_file),
            output_folder=output_folder,
            routes_path=routes_file,
            new_area_id=new_area_id,
            min_link_trips=1.0,
            debug=bool(inputs.get('debug', False)),
        )
        threading.Thread(target=_run_adjust_job,
                         args=(job_id, kwargs, area_id, new_area_id, mode, scenario_name,
                               all_constituent if is_mixed_source else None),
                         daemon=True).start()
    return {'jobID': job_id, 'status': 'accepted'}, 201, {'Location': f'/jobs/{job_id}'}


def _execute_whatif_road_closure(inputs: dict):
    """Start what-if wegafsluiting als async job. Geeft (body, 201, headers) terug."""
    if not _WHATIF_AVAILABLE:
        abort(503, 'what_if_quick_scan-package niet beschikbaar')

    area_id          = str(inputs.get('area_id', '')).strip()
    mode             = str(inputs.get('mode', 'CAR')).upper()
    selected_links   = inputs.get('selected_links', [])
    direction        = str(inputs.get('direction', 'both')).lower()
    scenario_name    = str(inputs.get('scenario_name', '')).strip() or None
    nroutes          = int(inputs.get('nroutes', 5))
    motive           = str(inputs.get('motive', 'totaal')).lower()
    period           = str(inputs.get('period', 'etmaal')).lower()
    measure          = str(inputs.get('measure', 'closure')).lower()
    reduction_factor = float(inputs.get('reduction_factor', 0.5))

    if not area_id:
        abort(400, 'Parameter "area_id" ontbreekt')
    if not isinstance(selected_links, list) or not selected_links:
        abort(400, 'Parameter "selected_links" moet een niet-lege array zijn')
    if direction not in ('both', 'same', 'opposite'):
        abort(400, 'Parameter "direction" moet "both", "same" of "opposite" zijn')
    if motive not in _WI_MOTIVES:
        abort(400, f'Ongeldig motief. Toegestaan: {", ".join(_WI_MOTIVES)}')
    if period not in _WI_PERIODS:
        abort(400, f'Ongeldig tijdvak. Toegestaan: {", ".join(_WI_PERIODS)}')

    try:
        selected_links = [int(lid) for lid in selected_links]
    except (ValueError, TypeError):
        abort(400, 'selected_links moet een array van integers zijn')

    src_dir      = _find_area_dir(area_id)
    path_geojson = src_dir / f'{area_id}-NETWORK-{mode}.geojson'
    path_csv     = src_dir / f'{area_id}-NVP-ROUTES-{mode}.csv'

    if not path_geojson.exists():
        abort(404, f'Netwerkbestand niet gevonden: {path_geojson.name}')
    if not path_csv.exists():
        abort(404,
              f'NVP-routes bestand ontbreekt ({path_csv.name}). '
              f'Bereid het gebied opnieuw voor met de nvp_mapper stap (nvp_table + nvp_year).')

    new_area_id = str(uuid.uuid4())
    if scenario_name:
        folder_name = re.sub(r'[^\w\-]', '_', scenario_name.strip())
        folder_name = re.sub(r'_+', '_', folder_name).strip('_') or new_area_id
    else:
        folder_name = new_area_id
    output_folder = _work_dir() / folder_name
    output_folder.mkdir(parents=True, exist_ok=True)
    (output_folder / '.area-uuid').write_text(new_area_id, encoding='utf-8')

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            'jobID':      job_id,
            'processID':  'whatif-road-closure',
            'status':     'accepted',
            'log':        [],
            'returncode': None,
            'out_dir':    str(output_folder),
            'created':    _now_iso(),
            'started':    None,
            'finished':   None,
            '_results':   {},
        }

    threading.Thread(
        target=_run_whatif_road_closure_job,
        args=(job_id, str(path_geojson), str(path_csv),
              output_folder, new_area_id, area_id,
              mode, selected_links, direction,
              motive, period, nroutes,
              measure, reduction_factor,
              scenario_name),
        daemon=True,
    ).start()
    return {'jobID': job_id, 'status': 'accepted'}, 201, {'Location': f'/jobs/{job_id}'}


def _execute_delete_area(inputs: dict):
    """Verwijder gebied synchroon. Geeft (body, 200, {}) terug."""
    area_id = str(inputs.get('id', '')).strip()
    if not _safe(area_id):
        abort(400, f'Ongeldige of ontbrekende area_id: {area_id!r}')
    area_dir = _find_area_dir(area_id)
    if not area_dir.is_dir():
        abort(404, f'Geen map gevonden voor gebied: {area_id}')
    try:
        shutil.rmtree(str(area_dir))
    except Exception as exc:
        abort(500, str(exc))
    return {'deleted': area_id}, 200, {}


def _execute_set_directory(inputs: dict):
    """Stel data-map in synchroon. Geeft (body, 200, {}) terug."""
    global DATA_DIR
    raw = str(inputs.get('path', '')).strip()
    if not raw:
        abort(400, 'Parameter "path" ontbreekt')
    p = Path(raw).resolve()
    if p.is_file():
        p = p.parent
    if not p.is_dir():
        abort(404, f'Map niet gevonden: {p}')
    DATA_DIR = p
    return {'dir': str(DATA_DIR), 'areas': _discover_areas()}, 200, {}


# ---------------------------------------------------------------------------
# OGC API Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    fmt = request.args.get('f', 'html').lower()
    if fmt == 'json':
        return jsonify({
            'title': 'Verkeersnetwerk-visualisatie',
            'description': 'OGC API Features + Processes — verkeersnetwerk visualisatie en scenarioanalyse.',
            'links': [
                {'href': '/?f=json',    'rel': 'self',        'type': 'application/json', 'title': 'Landing page'},
                {'href': '/conformance','rel': 'conformance',  'type': 'application/json', 'title': 'OGC conformantieklassen'},
                {'href': '/collections','rel': 'data',         'type': 'application/json', 'title': 'Collecties'},
                {'href': '/processes',  'rel': 'processes',    'type': 'application/json', 'title': 'Processen'},
                {'href': '/jobs',       'rel': 'monitor',      'type': 'application/json', 'title': 'Actieve jobs'},
            ],
        })
    return send_from_directory(str(STATIC_DIR), 'index.html')


@app.route('/conformance')
def ogc_conformance():
    return jsonify({
        'conformsTo': [
            'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core',
            'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30',
            'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson',
            'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core',
            'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json',
            'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/job-management',
        ]
    })


@app.route('/collections')
def ogc_collections():
    colls = []
    for cid, info in _COLLECTIONS.items():
        colls.append({
            'id':          cid,
            'title':       info['title'],
            'description': info['description'],
            'links': [
                {'href': f'/collections/{cid}',       'rel': 'self',  'type': 'application/json',     'title': info['title']},
                {'href': f'/collections/{cid}/items', 'rel': 'items', 'type': 'application/geo+json', 'title': f'{info["title"]} — items'},
            ],
        })
    return jsonify({
        'collections': colls,
        'links': [
            {'href': '/collections', 'rel': 'self', 'type': 'application/json', 'title': 'Collecties'},
        ],
    })


@app.route('/collections/<collection_id>')
def ogc_collection(collection_id):
    info = _COLLECTIONS.get(collection_id)
    if info is None:
        abort(404, f'Collectie niet gevonden: {collection_id}')
    return jsonify({
        'id':          collection_id,
        'title':       info['title'],
        'description': info['description'],
        'links': [
            {'href': f'/collections/{collection_id}',       'rel': 'self',  'type': 'application/json',     'title': info['title']},
            {'href': f'/collections/{collection_id}/items', 'rel': 'items', 'type': 'application/geo+json', 'title': f'{info["title"]} — items'},
        ],
    })


@app.route('/collections/<collection_id>/items/<feature_id>')
def ogc_collection_feature(collection_id, feature_id):
    abort(501, 'Ophalen van individuele features wordt niet ondersteund.')


@app.route('/collections/<collection_id>/items')
def ogc_collection_items(collection_id):
    info = _COLLECTIONS.get(collection_id)
    if info is None:
        abort(404, f'Collectie niet gevonden: {collection_id}')

    self_url = request.url

    # ── areas: geen bestandsparameters vereist ────────────────────────────
    if collection_id == 'areas':
        areas    = _discover_areas()
        features = [
            {'type': 'Feature', 'id': a['areaId'], 'geometry': None, 'properties': a}
            for a in areas
        ]
        return _ogc_items_response('areas', {'type': 'FeatureCollection', 'features': features}, self_url)

    # ── changes: gecumuleerde wijzigingen over de scenario-keten ─────────────
    if collection_id == 'changes':
        area_id = request.args.get('areaId', '').strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, 'Ongeldige parameter: areaId')

        features, visited, current_id, depth = [], set(), area_id, 0
        while current_id and depth < 20 and current_id not in visited:
            visited.add(current_id)
            area_dir = _find_area_dir(current_id)

            # Scenario-naam ophalen uit eerste gevonden NETWORK-bestand
            name = current_id
            _nf_list = list(area_dir.glob(f'{current_id}-NETWORK-*.geojson'))
            if not _nf_list and _GEOPANDAS_AVAILABLE:
                for _ext in _GEOPARQUET_EXTS:
                    _nf_list = list(area_dir.glob(f'{current_id}-NETWORK-*{_ext}'))
                    if _nf_list:
                        break
            if _nf_list:
                try:
                    props = _read_geodata(_nf_list[0]).get('properties', {})
                    name  = props.get('name', current_id)
                except Exception:
                    pass

            # Delta-wijzigingen lezen
            cp = area_dir / f'{current_id}-changes.json'
            if cp.exists():
                try:
                    for i, c in enumerate(json.loads(cp.read_text(encoding='utf-8'))):
                        features.append({
                            'type': 'Feature',
                            'id': f'{current_id}|{i}',
                            'geometry': None,
                            'properties': {'areaId': current_id, 'scenarioName': name, **c},
                        })
                except Exception:
                    pass

            # Keten omhoog via .src-area-id
            parent_id = None
            src_path  = area_dir / '.src-area-id'
            if src_path.exists():
                try:
                    parent_id = src_path.read_text(encoding='utf-8').strip() or None
                except Exception:
                    pass
            # Fallback: baseAreaId in bestandseigenschappen (GeoJSON of GeoParquet)
            if not parent_id:
                _nf_list2 = list(area_dir.glob(f'{current_id}-NETWORK-*.geojson'))
                if not _nf_list2 and _GEOPANDAS_AVAILABLE:
                    for _ext in _GEOPARQUET_EXTS:
                        _nf_list2 = list(area_dir.glob(f'{current_id}-NETWORK-*{_ext}'))
                        if _nf_list2:
                            break
                if _nf_list2:
                    try:
                        props     = _read_geodata(_nf_list2[0]).get('properties', {})
                        parent_id = props.get('baseAreaId') or None
                    except Exception:
                        pass

            current_id = parent_id
            depth     += 1

        # Oudste scenario eerst (keten staat nu in omgekeerde volgorde)
        features.reverse()
        fc = {'type': 'FeatureCollection', 'features': features}
        return _ogc_items_response('changes', fc, self_url)

    # ── flows: flow-scaler berekening ─────────────────────────────────────
    if collection_id == 'flows':
        if not _FLOW_SCALER_AVAILABLE:
            abort(503, 'flow_scaler-package niet beschikbaar')

        area_id = request.args.get('areaId', '').strip()
        mode    = request.args.get('mode', 'CAR').upper().strip()

        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, 'Ongeldige parameter: areaId')

        network_path = _data_path(area_id, mode, 'NETWORK')
        if network_path is None or not network_path.exists():
            abort(404, f'Netwerkbestand niet gevonden: {area_id}-NETWORK-{mode}')

        purpose_index_path = _find_local_file('purpose_index.json')
        if purpose_index_path is None:
            abort(503, 'purpose_index.json niet gevonden')
        with open(purpose_index_path, encoding='utf-8') as fh:
            purpose_index_raw = json.load(fh)
        purpose_index = load_purpose_index(purpose_index_raw)

        daylight_raw  = []
        daylight_path = _find_local_file('daylight.json')
        if daylight_path is not None:
            try:
                with open(daylight_path, encoding='utf-8') as fh:
                    daylight_raw = json.load(fh)
            except Exception as exc:
                print(f'[server] daylight.json laden mislukt, wordt overgeslagen: {exc}')

        date_str    = request.args.get('date') or None
        raw_temp    = request.args.get('temperature', 'Medium')
        raw_weather = request.args.get('weather', 'cloudy')
        raw_purpose = request.args.get('purpose') or None
        regio       = request.args.get('regio', 'midden').lower()

        dt          = parse_date(date_str)
        temperature = normalise_temperature(raw_temp)
        weather     = normalise_weather(raw_weather, dt, daylight_raw)
        purpose     = None if raw_purpose in (None, 'all', '') else raw_purpose.lower()

        holiday_path  = _find_local_file('holiday_indices.csv')
        holiday_index = str(holiday_path) if holiday_path is not None else ''

        params = FlowScalerParams(
            mode=mode, dt=dt, temperature=temperature, weather=weather,
            regio=regio, purpose=purpose, holiday_index=holiday_index,
        )

        try:
            network_fc = _read_geodata(network_path)
        except ImportError as exc:
            abort(503, str(exc))

        n_features = len(network_fc.get('features', []))
        filtered   = filterNetwork(network_fc, bbox=None, offset=0, limit=max(n_features, 1))
        filtered.params = params

        keys    = determineIndiceKeys(params, filtered.metadata)
        indexes = read_indexes(keys, purpose_index)
        result  = applyIndices(filtered, indexes, run_cleaner=False)

        # Normaliseer naar plain dict voor OGC-envelope
        if not isinstance(result, dict):
            try:
                result = dict(result)
            except Exception:
                result = {'type': 'FeatureCollection', 'features': []}

        return _ogc_items_response('flows', result, self_url)

    # ── buildings: OSM-gebouwen, gecached per gebied ──────────────────────
    if collection_id == 'buildings':
        area_id = request.args.get('areaId', '').strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, 'Ongeldige parameter: areaId')

        area_dir   = _find_area_dir(area_id)
        cache_path = area_dir / f'{area_id}-BUILDINGS.geojson'

        # 1) Gebruik cache als aanwezig én actueel (versienummer klopt)
        if cache_path.exists():
            with open(cache_path, encoding='utf-8') as fh:
                data = json.load(fh)
            if data.get('properties', {}).get('_qv') == _BUILDINGS_QUERY_VER:
                return _ogc_items_response('buildings', data, self_url)
            # Verouderde cache: verwijder en herlaad
            try:
                cache_path.unlink()
            except Exception:
                pass

        # 2) Zoek in ouder-gebieden via baseAreaId-keten
        visited = {area_id}
        cur_id  = area_id
        base_tile_cache_dir = None   # tegel-cache van het dichtstbijzijnde basis-scenario
        for _ in range(6):
            try:
                cur_dir       = _find_area_dir(cur_id)
                _nw_list = list(cur_dir.glob(f'{cur_id}-NETWORK-*.geojson'))
                if not _nw_list and _GEOPANDAS_AVAILABLE:
                    for _ext in _GEOPARQUET_EXTS:
                        _nw_list = list(cur_dir.glob(f'{cur_id}-NETWORK-*{_ext}'))
                        if _nw_list:
                            break
                if not _nw_list:
                    break
                props     = _read_geodata(_nw_list[0]).get('properties', {})
                parent_id = props.get('baseAreaId') or None
            except Exception:
                break
            if not parent_id or parent_id in visited:
                break
            visited.add(parent_id)
            cur_id       = parent_id
            parent_dir   = _find_area_dir(parent_id)
            parent_cache = parent_dir / f'{parent_id}-BUILDINGS.geojson'
            if parent_cache.exists():
                with open(parent_cache, encoding='utf-8') as fh:
                    data = json.load(fh)
                if data.get('properties', {}).get('_qv') == _BUILDINGS_QUERY_VER:
                    return _ogc_items_response('buildings', data, self_url)
                try:
                    parent_cache.unlink()
                except Exception:
                    pass
            # Bewaar tegel-cache van dit ouder-gebied (eerste treffer wint)
            ptcd = parent_dir / f'{parent_id}-BUILDINGS-tiles'
            if ptcd.exists() and base_tile_cache_dir is None:
                base_tile_cache_dir = ptcd

        # 3) Bepaal bbox en query Overpass
        bbox = None
        try:
            _nw_list2 = list(area_dir.glob(f'{area_id}-NETWORK-*.geojson'))
            if not _nw_list2 and _GEOPANDAS_AVAILABLE:
                for _ext in _GEOPARQUET_EXTS:
                    _nw_list2 = list(area_dir.glob(f'{area_id}-NETWORK-*{_ext}'))
                    if _nw_list2:
                        break
            if _nw_list2:
                ndata = _read_geodata(_nw_list2[0])
                props = ndata.get('properties', {})
                bbox  = props.get('bbox')
                if not bbox or len(bbox) < 4:
                    lons, lats = [], []
                    for feat in ndata.get('features', []):
                        for coord in feat.get('geometry', {}).get('coordinates', []):
                            lons.append(coord[0])
                            lats.append(coord[1])
                    if lons:
                        bbox = [min(lons), min(lats), max(lons), max(lats)]
        except Exception as exc:
            abort(500, f'Fout bij lezen netwerk voor bbox: {exc}')

        if not bbox:
            abort(404, 'Geen bbox beschikbaar voor gebouwen-query')

        try:
            tile_cache_dir = area_dir / f'{area_id}-BUILDINGS-tiles'
            data = _fetch_buildings_overpass(bbox, tile_cache_dir=tile_cache_dir,
                                             fallback_tile_cache_dir=base_tile_cache_dir)
        except Exception as exc:
            abort(502, f'Overpass-query mislukt: {exc}')

        # Cache opslaan — alleen als alle tegels succesvol waren
        try:
            if not data.get('properties', {}).get('_partial'):
                area_dir.mkdir(parents=True, exist_ok=True)
                with open(cache_path, 'w', encoding='utf-8') as fh:
                    json.dump(data, fh, ensure_ascii=False)
        except Exception:
            pass

        return _ogc_items_response('buildings', data, self_url)

    # ── traffic_signs: verkeersborden, gecached per gebied ────────────────
    if collection_id == 'traffic_signs':
        area_id = request.args.get('areaId', '').strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, 'Ongeldige parameter: areaId')

        area_dir   = _find_area_dir(area_id)
        cache_path = area_dir / f'{area_id}-TRAFFIC-SIGNS.geojson'

        # 1) Gebruik aggregate cache als aanwezig én actueel
        if cache_path.exists():
            with open(cache_path, encoding='utf-8') as fh:
                data = json.load(fh)
            if data.get('properties', {}).get('_qv') == _TRAFFIC_SIGNS_QUERY_VER:
                return _ogc_items_response('traffic_signs', data, self_url)
            # Verouderde cache: verwijder en herlaad
            try:
                cache_path.unlink()
            except Exception:
                pass

        # 2) Bepaal bbox uit NETWORK-bestand
        bbox = None
        try:
            _nw_list = list(area_dir.glob(f'{area_id}-NETWORK-*.geojson'))
            if not _nw_list and _GEOPANDAS_AVAILABLE:
                for _ext in _GEOPARQUET_EXTS:
                    _nw_list = list(area_dir.glob(f'{area_id}-NETWORK-*{_ext}'))
                    if _nw_list:
                        break
            if _nw_list:
                ndata = _read_geodata(_nw_list[0])
                props = ndata.get('properties', {})
                bbox  = props.get('bbox')
                if not bbox or len(bbox) < 4:
                    lons, lats = [], []
                    for feat in ndata.get('features', []):
                        for coord in feat.get('geometry', {}).get('coordinates', []):
                            lons.append(coord[0])
                            lats.append(coord[1])
                    if lons:
                        bbox = [min(lons), min(lats), max(lons), max(lats)]
        except Exception as exc:
            abort(500, f'Fout bij lezen netwerk voor bbox: {exc}')

        if not bbox:
            abort(404, 'Geen bbox beschikbaar voor verkeersborden-query')

        # 3) NDW (NL) of Overpass (buitenland)
        if _is_netherlands(bbox):
            # Wacht tot de NDW-achtergronddownload klaar is (blokkeert request)
            _ndw_ready.wait()
            if _ndw_error:
                abort(502, f'NDW-dataset niet beschikbaar: {_ndw_error}')
            ndw_path = DATA_DIR / 'ndw_traffic_signs.json'
            if not ndw_path.exists():
                abort(503, 'NDW-dataset nog niet beschikbaar, probeer later opnieuw')
            try:
                data = _fetch_traffic_signs_ndw(ndw_path, bbox)
            except Exception as exc:
                abort(500, f'Fout bij lezen NDW-dataset: {exc}')
        else:
            # Zoek fallback tegel-cache in base-scenario (via baseAreaId-keten)
            visited = {area_id}
            cur_id  = area_id
            base_tile_cache_dir = None
            for _ in range(6):
                try:
                    cur_dir  = _find_area_dir(cur_id)
                    _nw2     = list(cur_dir.glob(f'{cur_id}-NETWORK-*.geojson'))
                    if not _nw2 and _GEOPANDAS_AVAILABLE:
                        for _ext in _GEOPARQUET_EXTS:
                            _nw2 = list(cur_dir.glob(f'{cur_id}-NETWORK-*{_ext}'))
                            if _nw2:
                                break
                    if not _nw2:
                        break
                    p2        = _read_geodata(_nw2[0]).get('properties', {})
                    parent_id = p2.get('baseAreaId') or None
                except Exception:
                    break
                if not parent_id or parent_id in visited:
                    break
                visited.add(parent_id)
                cur_id    = parent_id
                parent_dir = _find_area_dir(parent_id)
                ptcd = parent_dir / f'{parent_id}-TRAFFIC-SIGNS-tiles'
                if ptcd.exists() and base_tile_cache_dir is None:
                    base_tile_cache_dir = ptcd

            try:
                tile_cache_dir = area_dir / f'{area_id}-TRAFFIC-SIGNS-tiles'
                data = _fetch_traffic_signs_overpass(
                    bbox,
                    tile_cache_dir=tile_cache_dir,
                    fallback_tile_cache_dir=base_tile_cache_dir,
                )
            except Exception as exc:
                abort(502, f'Overpass-query mislukt: {exc}')

        # Cache opslaan — alleen als volledig
        try:
            if not data.get('properties', {}).get('_partial'):
                area_dir.mkdir(parents=True, exist_ok=True)
                with open(cache_path, 'w', encoding='utf-8') as fh:
                    json.dump(data, fh, ensure_ascii=False)
        except Exception:
            pass

        return _ogc_items_response('traffic_signs', data, self_url)

    # ── overige collections: lees geodata-bestand (GeoJSON of GeoParquet) ────
    area_id = request.args.get('areaId', '').strip()
    mode    = request.args.get('mode', '').upper().strip()

    if not area_id:
        abort(400, 'Parameter "areaId" ontbreekt')
    if not _safe(area_id):
        abort(400, 'Ongeldige parameter: areaId')
    if not mode:
        abort(400, 'Parameter "mode" ontbreekt')
    if not _safe(mode):
        abort(400, 'Ongeldige parameter: mode')

    file_type = _COLLECTION_FILE_TYPE[collection_id]
    path      = _data_path(area_id, mode, file_type)

    if path is None or not path.exists():
        abort(404, f'Bestand niet gevonden: {area_id}-{file_type}-{mode}')

    # HTTP-caching: ETag gebaseerd op bestandswijzigingstijd (milliseconde-nauwkeurig)
    mtime         = path.stat().st_mtime
    etag          = f'"{int(mtime * 1000):x}"'
    last_modified = _dt.datetime.fromtimestamp(mtime, tz=_dt.timezone.utc).strftime(
        '%a, %d %b %Y %H:%M:%S GMT'
    )
    if request.headers.get('If-None-Match') == etag:
        resp = make_response('', 304)
        resp.headers['ETag']          = etag
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    try:
        data = _read_geodata(path)
    except ImportError as exc:
        abort(503, str(exc))

    resp = _ogc_items_response(collection_id, data, self_url)
    resp.headers['ETag']          = etag
    resp.headers['Last-Modified'] = last_modified
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/traffic-sign-icon/<string:code>')
def traffic_sign_icon(code):
    """Serveer een NDW PNG-icoon voor een RVV-bordcode; 404 als niet beschikbaar."""
    safe = re.sub(r'[^A-Za-z0-9.\-]', '', code)   # koppelteken en decimaalpunt toegestaan
    icon_dir = Path(__file__).parent / 'traffic_sign_icons'
    png_path = icon_dir / f'{safe}.png'
    if not png_path.exists():
        from flask import abort
        abort(404)
    resp = send_from_directory(str(icon_dir), f'{safe}.png', mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/processes')
def ogc_processes():
    avail = _get_available_processes()
    procs = []
    for pid in _PROCESS_DESCRIPTIONS:
        if pid not in avail:
            continue
        desc = _PROCESS_DESCRIPTIONS[pid]
        procs.append({
            'id':                  pid,
            'title':               desc['title'],
            'description':         desc['description'],
            'version':             desc['version'],
            'jobControlOptions':   desc['jobControlOptions'],
            'outputTransmission':  desc['outputTransmission'],
            'links': [
                {'href': f'/processes/{pid}', 'rel': 'self', 'type': 'application/json', 'title': desc['title']},
            ],
        })
    return jsonify({
        'processes': procs,
        'links': [
            {'href': '/processes', 'rel': 'self', 'type': 'application/json', 'title': 'Processen'},
        ],
    })


@app.route('/processes/<process_id>')
def ogc_process(process_id):
    avail = _get_available_processes()
    if process_id not in _PROCESS_DESCRIPTIONS:
        abort(404, f'Proces niet gevonden: {process_id}')
    if process_id not in avail:
        abort(503, f'Proces niet beschikbaar: {process_id}')
    desc = dict(_PROCESS_DESCRIPTIONS[process_id])
    desc['links'] = [
        {'href': f'/processes/{process_id}',           'rel': 'self',    'type': 'application/json', 'title': desc['title']},
        {'href': f'/processes/{process_id}/execution', 'rel': 'execute', 'type': 'application/json', 'title': f'{desc["title"]} uitvoeren'},
    ]
    return jsonify(desc)


@app.route('/processes/<process_id>/execution', methods=['POST'])
def ogc_process_execute(process_id):
    avail = _get_available_processes()
    if process_id not in _PROCESS_DESCRIPTIONS:
        abort(404, f'Proces niet gevonden: {process_id}')
    if process_id not in avail:
        abort(503, f'Proces niet beschikbaar: {process_id}')

    raw_body = request.get_json(force=True, silent=True) or {}
    # Ondersteun zowel OGC {"inputs": {...}} als flat body
    inputs = raw_body.get('inputs', raw_body)

    dispatch = {
        'prepare':             _execute_prepare,
        'adjust':              _execute_adjust,
        'whatif-road-closure': _execute_whatif_road_closure,
        'delete-area':         _execute_delete_area,
        'set-directory':       _execute_set_directory,
    }
    body, status, headers = dispatch[process_id](inputs)
    resp = jsonify(body)
    resp.status_code = status
    for k, v in headers.items():
        resp.headers[k] = v
    return resp


@app.route('/jobs')
def ogc_jobs():
    with _jobs_lock:
        jobs_copy = list(_jobs.values())
    return jsonify({
        'jobs': [_job_to_status(j) for j in jobs_copy],
        'links': [
            {'href': '/jobs', 'rel': 'self', 'type': 'application/json', 'title': 'Actieve jobs'},
        ],
    })


@app.route('/jobs/<job_id>')
def ogc_job(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        abort(404, f'Job niet gevonden: {job_id}')
    return jsonify(_job_to_status(job))


@app.route('/jobs/<job_id>/results')
def ogc_job_results(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        abort(404, f'Job niet gevonden: {job_id}')
    if job['status'] not in ('successful',):
        abort(404, f'Job {job_id} heeft nog geen resultaten (status: {job["status"]})')
    return jsonify(job.get('_results', {}))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(500)
@app.errorhandler(501)
@app.errorhandler(503)
def error_handler(e):
    return jsonify(error=str(e.description)), e.code


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print(f'Data-map    : {DATA_DIR}')
    print(f'prepare     : {"beschikbaar" if _PREPARE_AVAILABLE else "NIET beschikbaar"}')
    print(f'adjust      : {"beschikbaar" if _ADJUST_AVAILABLE else "NIET beschikbaar"}')
    print(f'flow_scaler : {"beschikbaar" if _FLOW_SCALER_AVAILABLE else "NIET beschikbaar"}')
    print(f'whatif      : {"beschikbaar" if _WHATIF_AVAILABLE else "NIET beschikbaar"}')
    print(f'Server      : http://localhost:{args.port}')
    app.run(host='0.0.0.0', port=args.port, debug=True)
