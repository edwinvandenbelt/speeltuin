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
from collections import OrderedDict
import os
import queue
import time
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request as _urllib_req
import uuid
from pathlib import Path

# Console-uitvoer naar UTF-8 forceren. Zonder dit loopt elke print met een
# Unicode-teken (→, …) stuk zodra de uitvoer niet naar een echte console gaat
# maar naar een bestand of pipe met een cp1252-codepage. Dat trof onder meer
# _sse_put(), waardoor élk SSE-event een HTTP 500 opleverde en de maquette
# stilviel zonder zichtbare oorzaak.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

# ---------------------------------------------------------------------------
# Gedeelde code (common/py, zie ../common/) op sys.path zetten. Dit bestand
# leeft in analyzer/ of digital-twin/; common/py is een sibling van die map.
# In een geflatten deployment (deploy.ps1-zip) bestaat ../common/py niet en
# staan gedeelde packages (bv. buildings_fetcher/) gewoon naast dit bestand —
# die vindt Python al via het standaard sys.path[0] (de scriptmap), dus dit
# blok is dan een no-op.
# ---------------------------------------------------------------------------
_COMMON_PY_DIR = (Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "common" / "py").resolve()
if _COMMON_PY_DIR.is_dir():
    sys.path.insert(0, str(_COMMON_PY_DIR))

import requests
from flask import (
    Flask,
    Response,
    abort,
    g,
    jsonify,
    make_response,
    request,
    send_from_directory,
    stream_with_context,
)
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
    _pq = None  # type: ignore[assignment]
    _GEOPANDAS_AVAILABLE = False

_GEOPARQUET_EXTS = (".geoparquet", ".parquet")

# ---------------------------------------------------------------------------
# .env laden
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv

    _env_file = Path(os.getcwd()) / ".env"
    if not _env_file.exists():
        _env_file = Path(os.path.dirname(os.path.abspath(__file__))) / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
        print(f".env geladen: {_env_file}")
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
    print(f"[server] WAARSCHUWING: adjust niet beschikbaar — {_e}")

try:
    from network_link_inserter.core.network_link_inserter_core import (
        insert_links as _insert_links,
    )

    _LINK_INSERTER_AVAILABLE = True
except ImportError as _e:
    _insert_links = None  # type: ignore[assignment]
    _LINK_INSERTER_AVAILABLE = False
    print(f"[server] WAARSCHUWING: network_link_inserter niet beschikbaar — {_e}")

try:
    from prepare.core.prepare_core import run_pipeline as _prepare_run_pipeline

    _PREPARE_AVAILABLE = True
except ImportError as _e:
    _prepare_run_pipeline = None  # type: ignore[assignment]
    _PREPARE_AVAILABLE = False
    print(f"[server] WAARSCHUWING: prepare niet beschikbaar — {_e}")

try:
    from osm.osm_prepare.core.osm_prepare_core import (
        run_pipeline as _osm_prepare_run_pipeline,
    )

    _OSM_PREPARE_AVAILABLE = True
except ImportError as _e:
    _osm_prepare_run_pipeline = None  # type: ignore[assignment]
    _OSM_PREPARE_AVAILABLE = False
    print(f"[server] WAARSCHUWING: osm_prepare niet beschikbaar — {_e}")

try:
    from scripts.geofabrik_pbf import (
        resolve_or_download_pbf as _resolve_or_download_pbf,
        is_within_netherlands as _is_within_netherlands,
        OSM_PBF_ENV_VAR as _OSM_PBF_ENV_VAR,
        OSM_PBF_CACHE_DIR_ENV_VAR as _OSM_PBF_CACHE_DIR_ENV_VAR,
        DEFAULT_CACHE_DIR as _DEFAULT_PBF_CACHE_DIR,
    )

    _GEOFABRIK_PBF_AVAILABLE = True
except ImportError as _e:
    _resolve_or_download_pbf = None  # type: ignore[assignment]
    _is_within_netherlands = None  # type: ignore[assignment]
    _OSM_PBF_ENV_VAR = "OSM_PBF_PATH"
    _OSM_PBF_CACHE_DIR_ENV_VAR = "OSM_PBF_CACHE_DIR"
    _DEFAULT_PBF_CACHE_DIR = Path(tempfile.gettempdir()) / "geofabrik_pbf"
    _GEOFABRIK_PBF_AVAILABLE = False
    print(f"[server] WAARSCHUWING: geofabrik_pbf helper niet beschikbaar — {_e}")

try:
    from flow_scaler.core.flow_scaler_core import (
        load_purpose_index,
        parse_date,
        normalise_temperature,
        normalise_weather,
        filterNetwork,
        resolve_indexes_by_mode,
        applyIndices,
        Params as FlowScalerParams,
    )

    _FLOW_SCALER_AVAILABLE = True
except ImportError as _e:
    load_purpose_index = normalise_temperature = normalise_weather = None  # type: ignore[assignment]
    parse_date = filterNetwork = resolve_indexes_by_mode = applyIndices = None  # type: ignore[assignment]
    FlowScalerParams = None  # type: ignore[assignment,misc]
    _FLOW_SCALER_AVAILABLE = False
    print(f"[server] WAARSCHUWING: flow_scaler niet beschikbaar — {_e}")

try:
    from whatif.nvp_whatif_data_lib import (
        read_data_geojson as _whatif_read_data_geojson,
    )
    from whatif.nvp_whatif_data_lib import (
        export_network_whatif as _whatif_export_network,
    )
    from whatif.nvp_whatif_lib import (
        prepare_data as _wi_prepare_data,
        initialize_weights as _wi_initialize_weights,
        initialize_mask as _wi_initialize_mask,
        get_nsegments as _wi_get_nsegments,
        get_selection as _wi_get_selection,
        clean_trips as _wi_clean_trips,
        calibrate_tripvolumes as _wi_calibrate_tripvolumes,
        get_graphs_base as _wi_get_graphs_base,
        get_ods as _wi_get_ods,
        selected_od_flows as _wi_selected_od_flows,
        adopt_reduction as _wi_adopt_reduction,
        get_new_paths as _wi_get_new_paths,
        full_assignment as _wi_full_assignment,
        get_difference_flows as _wi_get_difference_flows,
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
    print(f"[server] WAARSCHUWING: what_if_quick_scan niet beschikbaar — {_e}")

try:
    from wegenscan_pipeline import run_pipeline as _ws_run_pipeline

    _WEGENSCAN_AVAILABLE = True
except ImportError as _e:
    _ws_run_pipeline = None  # type: ignore[assignment]
    _WEGENSCAN_AVAILABLE = False
    print(f"[server] WAARSCHUWING: wegenscan niet beschikbaar — {_e}")

from buildings_fetcher.core.buildings_fetcher_core import (  # noqa: E402
    BUILDINGS_QUERY_VER as _BUILDINGS_QUERY_VER,
    fetch_buildings_overpass as _fetch_buildings_overpass,
)

from vegetation_fetcher.core.vegetation_fetcher_core import (  # noqa: E402
    VEGETATION_QUERY_VER as _VEGETATION_QUERY_VER,
    fetch_vegetation_overpass as _fetch_vegetation_overpass,
)

from traffic_signs_fetcher.core.traffic_signs_fetcher_core import (  # noqa: E402
    TRAFFIC_SIGNS_QUERY_VER as _TRAFFIC_SIGNS_QUERY_VER,
    is_netherlands as _is_netherlands,
    download_ndw_dataset as _download_ndw_dataset,
    fetch_traffic_signs_ndw as _fetch_traffic_signs_ndw,
    fetch_traffic_signs_overpass as _fetch_traffic_signs_overpass,
)

# ── Optionele rekenmodules uit gmt_calculation_lib (geluid & emissie) ──────
# Puur fc -> fc; worden on-the-fly op de network-FC toegepast. Ontbreken ze,
# dan draait de server gewoon door zonder deze kaartlagen.
try:
    from noise_estimator.core.noise_estimator_core import (  # noqa: E402
        estimate_noise_emission as _estimate_noise_emission,
    )

    _NOISE_AVAILABLE = True
except ImportError as _e:  # pragma: no cover
    _estimate_noise_emission = None  # type: ignore[assignment]
    _NOISE_AVAILABLE = False
    print(f"[server] WAARSCHUWING: noise_estimator niet beschikbaar - {_e}")

try:
    from emission_estimator.core.emission_estimator_core import (  # noqa: E402
        estimate_emissions as _estimate_emissions,
    )

    _EMISSION_AVAILABLE = True
except ImportError as _e:  # pragma: no cover
    _estimate_emissions = None  # type: ignore[assignment]
    _EMISSION_AVAILABLE = False
    print(f"[server] WAARSCHUWING: emission_estimator niet beschikbaar - {_e}")

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Verkeersnetwerk-visualisatie server")
parser.add_argument(
    "--data",
    default=os.path.dirname(os.path.abspath(__file__)),
    help="Map met GeoJSON-bestanden (standaard: scriptmap)",
)
parser.add_argument(
    "--port", type=int, default=5000, help="TCP-poort (standaard: 5000)"
)
parser.add_argument(
    "--no-threaded",
    action="store_true",
    help="Draai de dev-server single-threaded (standaard: multi-threaded)",
)
parser.add_argument(
    "--timing",
    action="store_true",
    help="Log de duur van elke request (standaard: alleen trage requests >500ms)",
)
args, _ = parser.parse_known_args()

DATA_DIR = Path(args.data).resolve()
STATIC_DIR = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
# Gedeelde statische/data-bestanden (common/js, common/data). Bestaan niet in
# een geflatten deployment (zie _COMMON_PY_DIR hierboven) — dan staan die
# bestanden al gewoon in STATIC_DIR en zijn deze mappen eenvoudigweg leeg/afwezig.
COMMON_JS_DIR = (STATIC_DIR / ".." / "common" / "js").resolve()
COMMON_DATA_DIR = (STATIC_DIR / ".." / "common" / "data").resolve()
_SAFE_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _work_dir() -> Path:
    """Submap van DATA_DIR waar alle gegenereerde bestanden worden opgeslagen."""
    d = DATA_DIR / "work"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _areas_cache_path() -> Path:
    """Pad naar het gebieden-cache-bestand."""
    return _work_dir() / "areas-cache.json"


def _areas_cache_invalidate():
    """Verwijder het gebieden-cache-bestand zodat het bij de volgende aanvraag opnieuw wordt opgebouwd."""
    try:
        _areas_cache_path().unlink(missing_ok=True)
    except Exception as _e:
        print(f"[areas-cache] invalidatie mislukt: {_e}")


# ---------------------------------------------------------------------------
# S3-ondersteuning (optioneel — backward compatible)
# Stel S3_WORK_BUCKET in om S3 te gebruiken; zonder configuratie werkt de
# server volledig lokaal zoals voorheen.
# ---------------------------------------------------------------------------

_S3_BUCKET: str = os.environ.get("S3_WORK_BUCKET", "").strip()
_S3_PREFIX: str = os.environ.get("S3_WORK_PREFIX", "work").strip().strip("/") + "/"
_s3_client_cache = None

# ---------------------------------------------------------------------------
# GMT (mobilitytwin) upload-configuratie — ingesteld via .env
# ---------------------------------------------------------------------------
_GMT_BASE_URL: str = os.environ.get(
    "GMT_BASE_URL", "https://mobilitytwin.goudappel.nl"
).rstrip("/")
_GMT_USERNAME: str = os.environ.get("GMT_USERNAME", "")
_GMT_PASSWORD: str = os.environ.get("GMT_PASSWORD", "")

# OSM/ODbL-attributie. De geprepareerde/geüploade data is deels afgeleid van
# OpenStreetMap (o.a. trafficSignal-annotatie, verkeersobjecten, gebouwen,
# groen). De ODbL vereist bronvermelding zodra deze data publiek gedeeld of
# gedistribueerd wordt; daarom reizen deze velden mee met de GMT-upload.
_OSM_ATTRIBUTION_TEXT: str = "© OpenStreetMap contributors"
_OSM_LICENSE: str = "ODbL-1.0"
_OSM_LICENSE_URL: str = "https://www.openstreetmap.org/copyright"


def _s3_enabled() -> bool:
    return bool(_S3_BUCKET)


def _s3_client():
    global _s3_client_cache
    if _s3_client_cache is None:
        import boto3

        _s3_client_cache = boto3.client("s3")
    return _s3_client_cache


def _s3_key(area_id: str, filename: str) -> str:
    return f"{_S3_PREFIX}{area_id}/{filename}"


def _s3_area_prefix(area_id: str) -> str:
    return f"{_S3_PREFIX}{area_id}/"


def _s3_list_keys(prefix: str) -> list:
    """Geef alle S3-objectsleutels terug met het opgegeven prefix."""
    paginator = _s3_client().get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def _s3_exists(key: str) -> bool:
    try:
        _s3_client().head_object(Bucket=_S3_BUCKET, Key=key)
        return True
    except Exception:
        return False


def _s3_read_bytes(key: str) -> bytes:
    response = _s3_client().get_object(Bucket=_S3_BUCKET, Key=key)
    return response["Body"].read()


def _s3_write_bytes(
    key: str, data: bytes, content_type: str = "application/octet-stream"
) -> None:
    _s3_client().put_object(
        Bucket=_S3_BUCKET, Key=key, Body=data, ContentType=content_type
    )


def _s3_write_text(key: str, text: str) -> None:
    _s3_write_bytes(key, text.encode("utf-8"), "text/plain")


def _s3_read_text(key: str) -> str:
    return _s3_read_bytes(key).decode("utf-8")


def _s3_delete_prefix(prefix: str) -> None:
    """Verwijder alle S3-objecten waarvan de sleutel begint met *prefix*."""
    keys = _s3_list_keys(prefix)
    if not keys:
        return
    for i in range(0, len(keys), 1000):
        _s3_client().delete_objects(
            Bucket=_S3_BUCKET,
            Delete={"Objects": [{"Key": k} for k in keys[i : i + 1000]]},
        )


def _s3_sync_to(local_dir: Path, area_id: str) -> None:
    """Upload alle bestanden in *local_dir* naar S3 onder {prefix}{area_id}/."""
    if not _s3_enabled():
        return
    for f in local_dir.iterdir():
        if not f.is_file():
            continue
        key = _s3_key(area_id, f.name)
        ct = (
            "application/json"
            if f.suffix.lower() in (".json", ".geojson")
            else "application/octet-stream"
        )
        _s3_write_bytes(key, f.read_bytes(), ct)
        print(f"[s3] geüpload: s3://{_S3_BUCKET}/{key}")


def _s3_sync_from(area_id: str, local_dir: Path) -> bool:
    """Download alle bestanden voor *area_id* van S3 naar *local_dir*.

    Geeft True terug als er minstens één bestand gevonden is.
    """
    if not _s3_enabled():
        return False
    keys = _s3_list_keys(_s3_area_prefix(area_id))
    if not keys:
        return False
    local_dir.mkdir(parents=True, exist_ok=True)
    for key in keys:
        filename = key.split("/")[-1]
        if not filename:
            continue
        local_path = local_dir / filename
        local_path.write_bytes(_s3_read_bytes(key))
        print(f"[s3] gedownload: {key} → {local_path}")
    return True


def _has_network_file(directory: Path, area_id: str) -> bool:
    """Controleer of de map een NETWORK-bestand bevat (GeoJSON of GeoParquet)."""
    if any(directory.glob(f"{area_id}-NETWORK-*.geojson")):
        return True
    if _GEOPANDAS_AVAILABLE:
        for ext in _GEOPARQUET_EXTS:
            if any(directory.glob(f"{area_id}-NETWORK-*{ext}")):
                return True
    return False


def _find_data_file(directory: Path, stem: str) -> "Path | None":
    """Zoek een geodata-bestand: eerst GeoJSON, dan GeoParquet (als geopandas beschikbaar is).

    Als het bestand lokaal niet gevonden wordt én S3 geconfigureerd is, wordt het
    automatisch van S3 gedownload naar de lokale cache-map.
    """
    for ext in (".geojson", ".json"):
        p = directory / f"{stem}{ext}"
        if p.exists():
            return p
    if _GEOPANDAS_AVAILABLE:
        for ext in _GEOPARQUET_EXTS:
            p = directory / f"{stem}{ext}"
            if p.exists():
                return p

    # S3 read-through: zoek bestand in S3 en download naar lokale cache
    if _s3_enabled():
        area_id = directory.name
        for ext in (".geojson", ".json") + _GEOPARQUET_EXTS:
            key = _s3_key(area_id, f"{stem}{ext}")
            if _s3_exists(key):
                try:
                    local_path = directory / f"{stem}{ext}"
                    directory.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(_s3_read_bytes(key))
                    print(f"[s3] gecached: {key} → {local_path}")
                    return local_path
                except Exception as _e:
                    print(f"[s3] download mislukt ({key}): {_e}")

    return None


# ---------------------------------------------------------------------------
# Geodata response-cache
# Slaat geconverteerde GeoJSON-data in-memory op per (pad, mtime).
# Voorkomt herhaalde parquet → GeoDataFrame → GeoJSON-conversies bij elke aanvraag.
# ---------------------------------------------------------------------------
import gzip as _gzip

_GEODATA_CACHE: dict = {}  # (path_str, mtime_ms) → data dict
_GEODATA_CACHE_LOCK = threading.Lock()  # beschermt cache-mutaties bij threaded server


def _geodata_cache_get(path: Path):
    """Geeft gecachede data-dict terug als in cache, anders None."""
    mtime_ms = int(path.stat().st_mtime * 1000)
    with _GEODATA_CACHE_LOCK:
        return _GEODATA_CACHE.get((str(path), mtime_ms))


def _geodata_cache_set(path: Path, data: dict):
    """Sla data op; verwijder verouderde entries voor hetzelfde pad."""
    mtime_ms = int(path.stat().st_mtime * 1000)
    key = (str(path), mtime_ms)
    with _GEODATA_CACHE_LOCK:
        _GEODATA_CACHE[key] = data
        for k in [k for k in _GEODATA_CACHE if k[0] == str(path) and k != key]:
            _GEODATA_CACHE.pop(k, None)


_JSON_FILE_CACHE: dict = {}  # (path_str, mtime_ms) → geparste waarde
_JSON_FILE_CACHE_LOCK = threading.Lock()


def _json_file_cache_get(path: Path):
    """Geeft de gecachede waarde voor ``path`` terug (mtime-gekeyed), anders None."""
    mtime_ms = int(path.stat().st_mtime * 1000)
    with _JSON_FILE_CACHE_LOCK:
        return _JSON_FILE_CACHE.get((str(path), mtime_ms))


def _json_file_cache_set(path: Path, value):
    """Sla ``value`` op voor ``path``; verwijder verouderde entries voor hetzelfde pad."""
    mtime_ms = int(path.stat().st_mtime * 1000)
    key = (str(path), mtime_ms)
    with _JSON_FILE_CACHE_LOCK:
        _JSON_FILE_CACHE[key] = value
        for k in [k for k in _JSON_FILE_CACHE if k[0] == str(path) and k != key]:
            _JSON_FILE_CACHE.pop(k, None)


_NETWORK_DERIVED_CACHE: dict = {}  # (path_str, mtime_ms, kind) → volledige verrijkte FC
# Versietag voor de afgeleide lagen (geluid/emissie); verhoog dit als de
# output-properties wijzigen zodat client-side HTTP-caches (ETag) ongeldig worden.
_DERIVED_VER = "d1"

# Welke properties elke afgeleide laag teruggeeft (naast altijd linkId).
_NOISE_PROPS = (
    "noiseDay",
    "noiseEvening",
    "noiseNight",
    "noiseLden",
    "noiseLnight",
    "noiseSourceType",
)
_EMISSION_PROPS = ("co2Kg", "noxKg", "pm10Kg", "pm25Kg", "vehicleKm", "length")


_FLOWS_RESULT_CACHE: "OrderedDict" = OrderedDict()  # key -> resultaat-dict
_FLOWS_RESULT_CACHE_LOCK = threading.Lock()
_FLOWS_RESULT_CACHE_MAX = 64  # LRU-cap: voorkomt onbegrensde groei over veel param-combinaties


def _flows_result_cache_get(key):
    with _FLOWS_RESULT_CACHE_LOCK:
        value = _FLOWS_RESULT_CACHE.get(key)
        if value is not None:
            _FLOWS_RESULT_CACHE.move_to_end(key)
        return value


def _flows_result_cache_set(key, value):
    with _FLOWS_RESULT_CACHE_LOCK:
        _FLOWS_RESULT_CACHE[key] = value
        _FLOWS_RESULT_CACHE.move_to_end(key)
        while len(_FLOWS_RESULT_CACHE) > _FLOWS_RESULT_CACHE_MAX:
            _FLOWS_RESULT_CACHE.popitem(last=False)


def _network_derived_fc(path: Path, kind: str) -> dict:
    """Bereken de geluid- (``kind='noise'``) of emissie- (``kind='emission'``)
    verrijking voor een NETWORK-bestand en geef de volledige FC terug.

    De pure ``fc -> fc`` kernen uit ``gmt_calculation_lib`` worden aangeroepen op
    de (gecachede) netwerk-FC. Het resultaat wordt per (bestand, soort) mtime-
    gekeyed gecached zodat de kernen niet bij elke aanvraag opnieuw rekenen.
    """
    mtime_ms = int(path.stat().st_mtime * 1000)
    key = (str(path), mtime_ms, kind)
    cached = _NETWORK_DERIVED_CACHE.get(key)
    if cached is not None:
        return cached
    data = _read_geodata(path)
    if kind == "noise":
        fc = _estimate_noise_emission(data)  # type: ignore[misc]
    else:
        fc = _estimate_emissions(data)  # type: ignore[misc]
    _NETWORK_DERIVED_CACHE[key] = fc
    with _GEODATA_CACHE_LOCK:
        for k in [
            k
            for k in _NETWORK_DERIVED_CACHE
            if k[0] == str(path) and k[2] == kind and k != key
        ]:
            _NETWORK_DERIVED_CACHE.pop(k, None)
    return fc


def _slim_derived_fc(fc: dict, prop_names, include_geometry: bool) -> dict:
    """Bouw een slanke FeatureCollection met enkel ``linkId`` + de gevraagde
    properties. De geometrie wordt alleen meegegeven als ``include_geometry``
    True is (de viewer heeft de netwerkgeometrie meestal al ingeladen)."""
    feats = []
    for feat in fc.get("features", []):
        src = feat.get("properties") or {}
        props = {"linkId": src.get("linkId")}
        for name in prop_names:
            if name in src:
                props[name] = src[name]
        feats.append(
            {
                "type": "Feature",
                "geometry": feat.get("geometry") if include_geometry else None,
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def _read_geodata(path: Path) -> dict:
    """Lees een GeoJSON of GeoParquet bestand en geef een GeoJSON FeatureCollection dict terug.

    Voor GeoParquet worden top-level properties (name, area_id, bbox, …) opgeslagen in de
    Parquet-bestandsmetadata onder de sleutel ``geojson_properties``.  Als die metadata
    ontbreekt, wordt een lege properties-dict gebruikt.

    Resultaten worden in-memory gecached (mtime-gekeyed) zodat herhaalde aanvragen
    (bijv. traffic_assets/heights bij elke map-beweging) het bestand niet telkens
    opnieuw hoeven te parsen.
    """
    cached = _geodata_cache_get(path)
    if cached is not None:
        return cached
    if path.suffix.lower() in _GEOPARQUET_EXTS:
        if not _GEOPANDAS_AVAILABLE:
            raise ImportError(
                "geopandas en pyarrow zijn vereist voor het lezen van GeoParquet-bestanden. "
                "Installeer ze via: pip install geopandas pyarrow"
            )
        gdf = _gpd.read_parquet(path)  # type: ignore[union-attr]
        # Herprojecteer naar WGS 84 (EPSG:4326) als de CRS afwijkt
        if gdf.crs is not None and not gdf.crs.equals("EPSG:4326"):
            gdf = gdf.to_crs("EPSG:4326")
        fc: dict = json.loads(gdf.to_json())
        # Kolommen die als JSON-string zijn opgeslagen in Parquet terugzetten naar Python-objecten
        # (geopandas slaat complexe types op als serialised JSON string; to_json() emit ze as-is)
        for feat in fc.get("features", []):
            props = feat.get("properties") or {}
            for key, val in props.items():
                if isinstance(val, str) and len(val) > 1 and val[0] in ("{", "["):
                    try:
                        props[key] = json.loads(val)
                    except (json.JSONDecodeError, ValueError):
                        pass
        # Probeer top-level properties te herstellen uit Parquet-bestandsmetadata.
        # Ondersteunt zowel de eigen 'geojson_properties'-key als de GMT-productiepipeline
        # die 'gmt_properties' schrijft (met o.a. name, areaId, baseAreaId, bbox).
        try:
            file_meta = _pq.read_metadata(path).metadata  # type: ignore[union-attr]
            raw = file_meta.get(b"geojson_properties") or file_meta.get(
                b"gmt_properties"
            )
            if raw:
                fc["properties"] = json.loads(raw.decode("utf-8"))
        except Exception:
            pass
        _geodata_cache_set(path, fc)
        return fc
    # GeoJSON / JSON
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    _geodata_cache_set(path, data)
    return data


# ---------------------------------------------------------------------------
# OGC API metadata
# ---------------------------------------------------------------------------

_COLLECTIONS = {
    "areas": {
        "title": "Beschikbare gebieden",
        "description": "Alle beschikbare verkeersgebieden in de werkmap.",
    },
    "network": {
        "title": "Verkeersnetwerk",
        "description": "Wegvakken en verkeersvolumes per gebied en transportmodus.",
    },
    "routes": {
        "title": "Routes",
        "description": "Ritten en routepaden per gebied en transportmodus.",
    },
    "zones": {
        "title": "Zones",
        "description": "Verkeerstoedelingszones per gebied en transportmodus.",
    },
    "feedlinks": {
        "title": "Aansluitingslinks",
        "description": "Aansluitingslinks per gebied en transportmodus.",
    },
    "comparison": {
        "title": "Vergelijking",
        "description": "Verschilnetwerk ten opzichte van het basisscenario.",
    },
    "flows": {
        "title": "Verkeersflows (geschaald)",
        "description": "Verkeersflows geschaald naar datum, weer en reismotief.",
    },
    "buildings": {
        "title": "Gebouwen",
        "description": "Gebouwen in het studiegebied (OpenStreetMap / Overpass, gecached).",
    },
    "traffic_signs": {
        "title": "Verkeersborden",
        "description": "Verkeersborden in het studiegebied (NDW voor NL, OSM Overpass voor buitenland, gecached).",
    },
    "traffic_assets": {
        "title": "Verkeersobjecten",
        "description": "Verkeersobjecten (borden, verkeerslichten, e.a.) uit het geprepareerde TRAFFIC-ASSETS bestand; ondersteunt bbox-filtering en optioneel assetType-filtering.",
    },
    "vegetation": {
        "title": "Vegetatie",
        "description": "Bomen, struiken en bos/bosschage uit het geprepareerde VEGETATION bestand (OpenStreetMap); ondersteunt bbox-filtering.",
    },
    "heights": {
        "title": "Hoogte- en constructie-objecten",
        "description": "Wegvakken met hoogte-informatie (viaducten/bruggen, tunnels) en geluidsschermen uit het geprepareerde HEIGHTS bestand (CIMLK); ondersteunt bbox-filtering.",
    },
    "changes": {
        "title": "Wijzigingen",
        "description": "Gecumuleerde wijzigingen in de scenario-keten voor een gebied.",
    },
    "wegenscan": {
        "title": "Wegenscan (veiligheidsscores)",
        "description": "21 veiligheids-KPI's + generic_safety per wegvak, berekend door de wegenscan.",
    },
    "noise": {
        "title": "Geluid (afgeleid)",
        "description": "Geluidsemissie per wegvak (Lden/Lnight, dB(A)), afgeleid uit het NETWORK-bestand. Join op linkId.",
    },
    "emission": {
        "title": "Uitstoot (afgeleid)",
        "description": "Emissie per wegvak (CO2/NOx/PM10/PM2.5, kg/etmaal + length), afgeleid uit het NETWORK-bestand. Join op linkId.",
    },
}

# Mapping van collection-id naar bestandstype-suffix
_COLLECTION_FILE_TYPE = {
    "network": "NETWORK",
    "routes": "ROUTES",
    "zones": "ZONE",
    "feedlinks": "FEEDLINK",
    "comparison": "COMPARE",
    "wegenscan": "WEGENSCAN",
}

_PROCESS_DESCRIPTIONS = {
    "prepare": {
        "id": "prepare",
        "title": "Gebied voorbereiden",
        "description": "Download en verwerk verkeersgegevens voor een nieuw gebied.",
        "version": "1.0.0",
        "jobControlOptions": ["async-execute"],
        "outputTransmission": ["value"],
        "inputs": {
            "name": {
                "title": "Gebiedsnaam",
                "schema": {"type": "string"},
                "minOccurs": 1,
            },
            "mode": {
                "title": "Modus (enkelvoudig, achterwaartse compatibiliteit)",
                "schema": {"type": "string", "enum": ["CAR", "BIKE", "PEDESTRIAN"]},
                "minOccurs": 0,
            },
            "modes": {
                "title": "Modi",
                "schema": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["CAR", "BIKE", "PEDESTRIAN"]},
                },
                "minOccurs": 0,
            },
            "mode_label": {
                "title": "Modusaanduiding (bijv. MIXED)",
                "schema": {"type": "string"},
                "minOccurs": 0,
            },
            "min_lon": {
                "title": "Min. lengtegraad",
                "schema": {"type": "number"},
                "minOccurs": 1,
            },
            "min_lat": {
                "title": "Min. breedtegraad",
                "schema": {"type": "number"},
                "minOccurs": 1,
            },
            "max_lon": {
                "title": "Max. lengtegraad",
                "schema": {"type": "number"},
                "minOccurs": 1,
            },
            "max_lat": {
                "title": "Max. breedtegraad",
                "schema": {"type": "number"},
                "minOccurs": 1,
            },
            "catalog": {
                "title": "Catalogus",
                "schema": {"type": "string"},
                "minOccurs": 0,
            },
            "schema": {"title": "Schema", "schema": {"type": "string"}, "minOccurs": 0},
            "refresh": {
                "title": "Vernieuwen",
                "schema": {"type": "boolean"},
                "minOccurs": 0,
            },
            "debug": {"title": "Debug", "schema": {"type": "boolean"}, "minOccurs": 0},
        },
        "outputs": {
            "collection": {"title": "Collectie-URL", "schema": {"type": "string"}},
        },
    },
    "adjust": {
        "id": "adjust",
        "title": "Scenario aanpassen",
        "description": "Herbereken verkeersstromen op basis van zone-wijzigingen.",
        "version": "1.0.0",
        "jobControlOptions": ["async-execute"],
        "outputTransmission": ["value"],
        "inputs": {
            "area_id": {
                "title": "Gebied-ID",
                "schema": {"type": "string"},
                "minOccurs": 1,
            },
            "mode": {"title": "Modus", "schema": {"type": "string"}, "minOccurs": 1},
            "changes": {
                "title": "Wijzigingen",
                "schema": {"type": "array"},
                "minOccurs": 1,
            },
            "scenario_name": {
                "title": "Scenarionaam",
                "schema": {"type": "string"},
                "minOccurs": 0,
            },
            "debug": {"title": "Debug", "schema": {"type": "boolean"}, "minOccurs": 0},
        },
        "outputs": {
            "new_area_id": {"title": "Nieuw gebied-ID", "schema": {"type": "string"}},
            "collection": {"title": "Collectie-URL", "schema": {"type": "string"}},
            "compare_url": {"title": "Vergelijkings-URL", "schema": {"type": "string"}},
        },
    },
    "whatif-road-closure": {
        "id": "whatif-road-closure",
        "title": "What-if wegafsluiting",
        "description": "Simuleer de gevolgen van het afsluiten van één of meer wegvakken.",
        "version": "1.0.0",
        "jobControlOptions": ["async-execute"],
        "outputTransmission": ["value"],
        "inputs": {
            "area_id": {
                "title": "Gebied-ID",
                "schema": {"type": "string"},
                "minOccurs": 1,
            },
            "mode": {"title": "Modus", "schema": {"type": "string"}, "minOccurs": 1},
            "selected_links": {
                "title": "Geselecteerde links",
                "schema": {"type": "array", "items": {"type": "integer"}},
                "minOccurs": 1,
            },
            "direction": {
                "title": "Richting",
                "schema": {"type": "string", "enum": ["both", "same", "opposite"]},
                "minOccurs": 0,
            },
            "scenario_name": {
                "title": "Scenarionaam",
                "schema": {"type": "string"},
                "minOccurs": 0,
            },
            "nroutes": {
                "title": "Aantal routes",
                "schema": {"type": "integer"},
                "minOccurs": 0,
            },
            "motive": {
                "title": "Reismotief",
                "schema": {"type": "string"},
                "minOccurs": 0,
            },
            "period": {
                "title": "Tijdvak",
                "schema": {"type": "string"},
                "minOccurs": 0,
            },
            "measure": {
                "title": "Maatregel",
                "schema": {"type": "string", "enum": ["closure", "capacity", "speed"]},
                "minOccurs": 0,
            },
            "reduction_factor": {
                "title": "Reductiefactor",
                "schema": {"type": "number"},
                "minOccurs": 0,
            },
        },
        "outputs": {
            "new_area_id": {"title": "Nieuw gebied-ID", "schema": {"type": "string"}},
            "collection": {"title": "Collectie-URL", "schema": {"type": "string"}},
        },
    },
    "wegenscan": {
        "id": "wegenscan",
        "title": "Wegenscan – veiligheids-KPI's",
        "description": (
            "Verrijkt een bestaand netwerk met NWB-attributen via Databricks en "
            "berekent 21 veiligheids-KPI's per wegvak (GOED/REDELIJK/MATIG/SLECHT)."
        ),
        "version": "2.1.0",
        "jobControlOptions": ["async-execute"],
        "outputTransmission": ["value"],
        "inputs": {
            "area_id": {
                "title": "Gebied-ID",
                "schema": {"type": "string"},
                "minOccurs": 1,
            },
            "mode": {
                "title": "Modus",
                "schema": {
                    "type": "string",
                    "enum": ["CAR", "BIKE", "PEDESTRIAN", "MIXED"],
                },
                "minOccurs": 1,
            },
        },
        "outputs": {
            "collection": {"title": "Collectie-URL", "schema": {"type": "string"}},
        },
    },
    "delete-area": {
        "id": "delete-area",
        "title": "Gebied verwijderen",
        "description": "Verwijder een gebied en alle bijbehorende bestanden definitief.",
        "version": "1.0.0",
        "jobControlOptions": ["sync-execute"],
        "outputTransmission": ["value"],
        "inputs": {
            "id": {"title": "Gebied-ID", "schema": {"type": "string"}, "minOccurs": 1},
        },
        "outputs": {
            "deleted": {"title": "Verwijderd gebied-ID", "schema": {"type": "string"}},
        },
    },
    "set-directory": {
        "id": "set-directory",
        "title": "Data-map instellen",
        "description": "Stel de werkmap in waaruit gebieden worden geladen.",
        "version": "1.0.0",
        "jobControlOptions": ["sync-execute"],
        "outputTransmission": ["value"],
        "inputs": {
            "path": {"title": "Pad", "schema": {"type": "string"}, "minOccurs": 1},
        },
        "outputs": {
            "dir": {"title": "Ingestelde map", "schema": {"type": "string"}},
            "areas": {"title": "Beschikbare gebieden", "schema": {"type": "array"}},
        },
    },
    "upload-to-gmt": {
        "id": "upload-to-gmt",
        "title": "Uploaden naar GMT",
        "description": "Converteert het netwerk-parquet naar GeoJSON en uploadt het naar mobilitytwin.goudappel.nl.",
        "version": "1.0.0",
        "jobControlOptions": ["async-execute"],
        "outputTransmission": ["value"],
        "inputs": {
            "areaId": {
                "title": "Gebied-ID",
                "schema": {"type": "string"},
                "minOccurs": 1,
            },
            "mode": {
                "title": "Modus",
                "schema": {"type": "string"},
                "minOccurs": 1,
            },
        },
        "outputs": {
            "areaId": {"title": "Geüpload gebied-ID", "schema": {"type": "string"}},
            "mode": {"title": "Modus", "schema": {"type": "string"}},
        },
    },
}

# ---------------------------------------------------------------------------
# What-if model-coëfficiënten
# ---------------------------------------------------------------------------

_WI_FRACT_CHANGE = [0.10, 0.25, 0.50, 0.80, 0.95]
_WI_MIN_NVP = 10
_WI_MIN_RADIUS_ODNODE = 200
_WI_CWEIGHT_ADD = 0.3
_WI_POWER_RATIO = {"capacity": 0.45, "speed": 0.20}
_WI_MOTIVES = {
    "totaal": 0,
    "werk": 1,
    "zakelijk": 2,
    "onderwijs": 3,
    "recreatief": 4,
    "winkel": 5,
    "overig": 6,
}
_WI_PERIODS = {"etmaal": 0, "ochtendspits": 1, "avondspits": 2, "restdag": 3}

# ---------------------------------------------------------------------------
# Flask-app
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=None)
Compress(app)

# ---------------------------------------------------------------------------
# Job-store
# ---------------------------------------------------------------------------

_jobs: dict = {}
_jobs_lock = threading.Lock()
# Serialiseert redirect_stdout/redirect_stderr over alle job-threads: contextlib.redirect_*
# past sys.stdout/sys.stderr globaal aan, dus gelijktijdige jobs zouden elkaars stream
# overschrijven.  Door de pipeline-uitvoering te serialiseren voorkom je dat.
_pipeline_stdout_lock = threading.Lock()

# Circuit breaker voor Overpass-queries: na _OVERPASS_FAIL_THRESHOLD opeenvolgende
# mislukkingen (per collection) stoppen we tot server-herstart. Reset bij succes.
_OVERPASS_FAIL_THRESHOLD = 5
_overpass_fail_counts: dict = {}
_overpass_breaker_lock = threading.Lock()


def _overpass_breaker_check(collection: str) -> None:
    """Abort met 503 als de circuit breaker voor deze collection open staat."""
    with _overpass_breaker_lock:
        count = _overpass_fail_counts.get(collection, 0)
    if count >= _OVERPASS_FAIL_THRESHOLD:
        abort(
            503,
            f"Overpass tijdelijk uitgeschakeld voor {collection} na "
            f"{count} opeenvolgende mislukkingen. Herstart de server om opnieuw te proberen.",
        )


def _overpass_breaker_failure(collection: str) -> None:
    """Registreer een mislukte Overpass-poging voor deze collection."""
    with _overpass_breaker_lock:
        _overpass_fail_counts[collection] = _overpass_fail_counts.get(collection, 0) + 1


def _overpass_breaker_success(collection: str) -> None:
    """Reset de teller na een geslaagde Overpass-poging."""
    with _overpass_breaker_lock:
        _overpass_fail_counts.pop(collection, None)


# SSE follow-modus: area_id → set van queue.SimpleQueue-objecten voor verbonden browsers
_sse_listeners: dict = {}
_sse_listeners_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Maquette-camera proces
# ---------------------------------------------------------------------------

_maquette_process: "subprocess.Popen | None" = None
_maquette_process_lock = threading.Lock()
_maquette_area_id: str = ""  # area_id waarvoor de camera loopt (voor heartbeat SSE)

# --- Camerabeeld-relais (preview tijdens calibratie) -------------------------
# maquette_camera.py pusht JPEG-frames hierheen; browsers halen ze op als
# MJPEG-stream. Eén "laatste frame"-slot in plaats van een queue per client:
# een trage browser slaat frames over en kan de bron nooit afremmen of het
# geheugen laten vollopen.
_mjpeg_cond = threading.Condition()
_mjpeg_frame: "bytes | None" = None
_mjpeg_seq: int = 0
_mjpeg_meta: dict = {"width": 0, "height": 0, "ts": 0.0}
_mjpeg_clients: int = 0
# De browser houdt per origin maar 6 HTTP/1.1-verbindingen aan, en de
# SSE-stream bezet er al één. Meer dan een paar tegelijk is altijd een lek.
_MJPEG_MAX_CLIENTS = 4

# --- Cursorpositie voor de virtuele maquette-modus (cameraId=-1) -------------
# De browser kent de cursor in kaartcoördinaten; die posten is exact en maakt
# het uitlezen van de Windows-cursor (met alle DPI- en vensterrand-ellende)
# overbodig.
_cursor_lock = threading.Lock()
_cursor_slot: "dict | None" = None

# ---------------------------------------------------------------------------
# NDW-achtergronddownload (verkeersborden NL)
# ---------------------------------------------------------------------------

# _ndw_ready wordt gezet zodra het NDW-bestand beschikbaar is (of de download
# is mislukt).  Route-handlers voor traffic_signs wachten op dit event.
_ndw_ready: threading.Event = threading.Event()
_ndw_error: "str | None" = None


def _ensure_ndw_data() -> None:
    """Controleer of het NDW-bestand aanwezig is; download het indien nodig."""
    global _ndw_error
    p = DATA_DIR / "ndw_traffic_signs.json"
    if p.exists():
        _ndw_ready.set()
        return
    print("[server] NDW-verkeersborden downloaden …")
    ok = _download_ndw_dataset(p)
    if ok:
        print(f"[server] NDW-verkeersborden opgeslagen: {p}")
    else:
        _ndw_error = "NDW-download mislukt"
        print(f"[server]  {_ndw_error}")
    _ndw_ready.set()


threading.Thread(target=_ensure_ndw_data, daemon=True).start()


class _LogStream(io.TextIOBase):
    """Schrijft stdout/stderr van run_pipeline door naar de job-loglijst.

    Thread-safe: meerdere threads (bijv. ThreadPoolExecutor-workers in run_pipeline)
    kunnen gelijktijdig schrijven.  _buf_lock beschermt de buffer; _lock beschermt
    de gedeelde loglijst.
    """

    def __init__(self, log_list, lock):
        self._log = log_list
        self._lock = lock
        self._buf = ""
        self._buf_lock = threading.Lock()

    def write(self, s):
        with self._buf_lock:
            self._buf += s
            lines = []
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                lines.append(line)
        if lines:
            with self._lock:
                self._log.extend(lines)
        return len(s)

    def flush(self):
        with self._buf_lock:
            remainder = self._buf
            self._buf = ""
        if remainder:
            with self._lock:
                self._log.append(remainder)


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def _safe(value) -> bool:
    return bool(value and _SAFE_RE.match(value))


_AREA_DIR_CACHE: dict = {}  # area_id -> Path
_AREA_DIR_CACHE_LOCK = threading.Lock()


def _find_area_dir(area_id: str) -> Path:
    """Zoek de work-submap die de bestanden voor area_id bevat.

    Als het gebied lokaal niet gevonden wordt én S3 geconfigureerd is, wordt het
    automatisch van S3 gedownload naar de lokale cache-map.

    Het resultaat wordt in-memory gecached per area_id, zodat niet bij elke
    aanvraag opnieuw alle submappen van work/ doorzocht hoeven te worden
    (linear scan + glob per map). Een cache-hit wordt gevalideerd (map bestaat
    nog en bevat nog het networkbestand) voordat hij wordt teruggegeven.
    """
    with _AREA_DIR_CACHE_LOCK:
        cached = _AREA_DIR_CACHE.get(area_id)
    if cached is not None and cached.is_dir() and _has_network_file(cached, area_id):
        return cached

    work = _work_dir()
    direct = work / area_id
    found: "Path | None" = None
    if direct.is_dir() and _has_network_file(direct, area_id):
        found = direct
    else:
        for subdir in work.iterdir():
            if subdir.is_dir() and _has_network_file(subdir, area_id):
                found = subdir
                break

    if found is None and _s3_enabled():
        # S3 fallback: download het volledige gebied naar lokale cache
        if _s3_sync_from(area_id, direct):
            found = direct

    if found is None:
        found = direct  # fallback (leidt tot 404 downstream)
    else:
        with _AREA_DIR_CACHE_LOCK:
            _AREA_DIR_CACHE[area_id] = found
    return found


def _geojson_path(area_id: str, mode: str, file_type: str) -> Path:
    return _find_area_dir(area_id) / f"{area_id}-{file_type}-{mode}.geojson"


def _data_path(area_id: str, mode: str, file_type: str) -> "Path | None":
    """Zoek het beste geodata-bestand (GeoJSON heeft voorrang op GeoParquet)."""
    return _find_data_file(_find_area_dir(area_id), f"{area_id}-{file_type}-{mode}")


def _area_parent_id(area_id: str) -> "str | None":
    """Geef de baseAreaId van een gebied terug via de NETWORK-properties, of None.

    Scenario's verwijzen via ``baseAreaId`` naar hun bronscenario; het basis-
    scenario zelf heeft geen ouder.
    """
    cur_dir = _find_area_dir(area_id)
    nw_list = list(cur_dir.glob(f"{area_id}-NETWORK-*.geojson"))
    if not nw_list and _GEOPANDAS_AVAILABLE:
        for ext in _GEOPARQUET_EXTS:
            nw_list = list(cur_dir.glob(f"{area_id}-NETWORK-*{ext}"))
            if nw_list:
                break
    if not nw_list:
        return None
    try:
        props = _read_geodata(nw_list[0]).get("properties", {})
    except Exception:
        return None
    return props.get("baseAreaId") or None


def _find_prepared_with_base_fallback(area_id: str, file_type: str) -> "Path | None":
    """Zoek een geprepareerd bestand ``{areaId}-{file_type}`` in het gebied zelf
    en, als het ontbreekt, in de baseAreaId-keten.

    Scenario's kopiëren statische data (VEGETATION, TRAFFIC-ASSETS, HEIGHTS) niet
    altijd door; die mag van het basisscenario geleend worden.
    """
    visited = {area_id}
    cur_id = area_id
    for _ in range(8):
        path = _find_data_file(_find_area_dir(cur_id), f"{cur_id}-{file_type}")
        if path is not None:
            return path
        parent_id = _area_parent_id(cur_id)
        if not parent_id or parent_id in visited:
            break
        visited.add(parent_id)
        cur_id = parent_id
    return None


def _collect_descendant_area_ids(area_id: str) -> list:
    """Geef alle afstammelingen (sub-scenario's) van *area_id* terug, diep.

    Scenario's verwijzen via ``srcAreaId`` (afgeleid uit ``.src-area-id`` of de
    ``baseAreaId``-property) naar hun directe bronscenario.  Deze functie loopt de
    volledige boom af en geeft de area-ids van álle nakomelingen terug (exclusief
    *area_id* zelf).  De volgorde is deterministisch en breadth-first.
    """
    # Bouw parent -> set(children) uit de (per-modus) gebiedenlijst; ontdubbel
    # meteen op area-id zodat meerdere modi niet tot dubbele takken leiden.
    children: dict = {}
    for a in _discover_areas():
        src = a.get("srcAreaId")
        aid = a.get("areaId")
        if src and aid:
            children.setdefault(src, set()).add(aid)

    descendants: list = []
    seen: set = {area_id}
    queue: list = [area_id]
    while queue:
        current = queue.pop(0)
        for child in sorted(children.get(current, ())):
            if child in seen:
                continue  # bescherming tegen (theoretische) cykels
            seen.add(child)
            descendants.append(child)
            queue.append(child)
    return descendants


def _discover_areas() -> list:
    """Geef de lijst van beschikbare gebieden terug, met cache.

    Leest ``work/areas-cache.json`` als dat aanwezig is. Ontbreekt het bestand,
    dan wordt ``_discover_areas_uncached()`` aangeroepen en het resultaat gecached.
    """
    cache = _areas_cache_path()
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception as _e:
            print(f"[areas-cache] lezen mislukt, bouw opnieuw op: {_e}")
    areas = _discover_areas_uncached()
    try:
        cache.write_text(
            json.dumps(areas, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as _e:
        print(f"[areas-cache] schrijven mislukt: {_e}")
    return areas


def _discover_areas_uncached() -> list:
    """Bouw de gebiedenlijst op door de work-map (en S3) te scannen."""
    areas = []
    seen: set = set()
    pattern_geojson = re.compile(r"^(.+)-NETWORK-([A-Za-z0-9_]+)\.geojson$")
    pattern_geoparquet = re.compile(r"^(.+)-NETWORK-([A-Za-z0-9_]+)\.(?:geo)?parquet$")
    work = _work_dir()
    for subdir in sorted(work.iterdir()):
        if not subdir.is_dir():
            continue
        # Verzamel NETWORK-kandidaten: GeoJSON heeft voorrang op GeoParquet
        candidates: dict = {}
        for f in sorted(subdir.glob("*-NETWORK-*.geojson")):
            m = pattern_geojson.match(f.name)
            if m:
                candidates[(m.group(1), m.group(2))] = f
        if _GEOPANDAS_AVAILABLE:
            for ext in _GEOPARQUET_EXTS:
                for f in sorted(subdir.glob(f"*-NETWORK-*{ext}")):
                    m = pattern_geoparquet.match(f.name)
                    if m:
                        key = (m.group(1), m.group(2))
                        if key not in candidates:
                            candidates[key] = f
        for (area_id, mode), f in sorted(candidates.items()):
            if (area_id, mode) in seen:
                continue
            seen.add((area_id, mode))
            name = area_id
            src_area_id = None
            bbox = None
            # Snel pad voor parquet: lees alleen file-level metadata (geen volledige
            # deserialise van de geometrieën).
            if f.suffix.lower() in _GEOPARQUET_EXTS and _GEOPANDAS_AVAILABLE:
                try:
                    raw_meta = _pq.read_metadata(f).metadata
                    gmt = raw_meta.get(b"gmt_properties") or raw_meta.get(
                        b"geojson_properties"
                    )
                    if not gmt:
                        raise ValueError("geen gmt_properties in parquet-metadata")
                    props = json.loads(gmt.decode("utf-8"))
                    name = props.get("name", area_id)
                    src_area_id = props.get("baseAreaId") or None
                    bbox = props.get("bbox") or None
                except Exception:
                    # Fallback: volledig lezen (o.a. voor bestanden zonder metadata)
                    try:
                        data = _read_geodata(f)
                        props = data.get("properties", {})
                        name = props.get("name", area_id)
                        src_area_id = props.get("baseAreaId") or None
                        bbox = props.get("bbox") or None
                    except Exception:
                        pass
            else:
                # GeoJSON (wordt uitgefaseerd) of geen parquet-ondersteuning
                try:
                    data = _read_geodata(f)
                    props = data.get("properties", {})
                    name = props.get("name", area_id)
                    src_area_id = props.get("baseAreaId") or None
                    bbox = props.get("bbox") or None
                except Exception:
                    pass
            if not bbox:
                bbox = _network_bbox(f)
            if not src_area_id:
                src_id_path = subdir / ".src-area-id"
                if src_id_path.exists():
                    try:
                        src_area_id = (
                            src_id_path.read_text(encoding="utf-8").strip() or None
                        )
                    except Exception:
                        pass
            # .area-name heeft altijd prioriteit (expliciet opgegeven scenarionaam)
            area_name_path = subdir / ".area-name"
            if area_name_path.exists():
                try:
                    name = area_name_path.read_text(encoding="utf-8").strip() or name
                except Exception:
                    pass
            has_compare = (subdir / f"{area_id}-COMPARE-{mode}.geojson").exists()
            has_nvp_routes = (subdir / f"{area_id}-NVP-ROUTES-{mode}.parquet").exists()
            gmt_uploaded = (subdir / f".gmt-uploaded-{mode}").exists()
            # Full digital twin = expliciete marker (echte OSM/BGT-verrijking gedraaid).
            # Niet afleiden uit TRAFFIC-ASSETS: dat bestand wordt ook geschreven bij
            # een prepare zonder OSM-verrijking (no_osm=True).
            is_full_twin = (subdir / ".full-twin").exists()
            areas.append(
                {
                    "areaId": area_id,
                    "mode": mode,
                    "name": name,
                    "hasCompare": has_compare,
                    "srcAreaId": src_area_id,
                    "hasNvpRoutes": has_nvp_routes,
                    "gmtUploaded": gmt_uploaded,
                    "isFullTwin": is_full_twin,
                    "bbox": bbox,
                }
            )

    # S3: voeg gebieden toe die alleen in S3 bestaan (niet lokaal gecached)
    if _s3_enabled():
        try:
            all_keys = _s3_list_keys(_S3_PREFIX)
        except Exception as _exc:
            print(f"[s3] _discover_areas S3-listing mislukt: {_exc}")
            all_keys = []

        s3_candidates: dict = {}
        for key in all_keys:
            filename = key.split("/")[-1]
            for pat in (pattern_geojson, pattern_geoparquet):
                m = pat.match(filename)
                if m:
                    aid, mod = m.group(1), m.group(2)
                    if (aid, mod) not in s3_candidates:
                        s3_candidates[(aid, mod)] = key

        for (area_id, mode), key in sorted(s3_candidates.items()):
            if (area_id, mode) in seen:
                continue
            seen.add((area_id, mode))
            name = area_id
            src_area_id = None
            bbox = None
            try:
                data = json.loads(_s3_read_bytes(key).decode("utf-8"))
                props = data.get("properties", {})
                name = props.get("name", area_id)
                src_area_id = props.get("baseAreaId") or None
                bbox = props.get("bbox") or None
            except Exception:
                pass
            if not src_area_id:
                try:
                    src_area_id = (
                        _s3_read_text(_s3_key(area_id, ".src-area-id")).strip() or None
                    )
                except Exception:
                    pass
            has_compare = _s3_exists(
                _s3_key(area_id, f"{area_id}-COMPARE-{mode}.geojson")
            )
            has_nvp_routes = _s3_exists(
                _s3_key(area_id, f"{area_id}-NVP-ROUTES-{mode}.parquet")
            )
            is_full_twin = _s3_exists(_s3_key(area_id, ".full-twin"))
            areas.append(
                {
                    "areaId": area_id,
                    "mode": mode,
                    "name": name,
                    "hasCompare": has_compare,
                    "srcAreaId": src_area_id,
                    "hasNvpRoutes": has_nvp_routes,
                    "isFullTwin": is_full_twin,
                    "bbox": bbox,
                }
            )

    return areas


def _work_dir_has_network_file(directory: Path) -> bool:
    """Controleer of de map een NETWORK-bestand bevat, ongeacht area-id-prefix."""
    if any(directory.glob("*-NETWORK-*.geojson")):
        return True
    if _GEOPANDAS_AVAILABLE:
        for ext in _GEOPARQUET_EXTS:
            if any(directory.glob(f"*-NETWORK-*{ext}")):
                return True
    return False


def _cleanup_work_dir():
    """Ruim verweesde scenario-mappen en overbodige losse .json-bestanden op in work/.

    Wordt eenmalig uitgevoerd bij het opstarten van de server, vóór app.run(). Een
    scenario-map zonder NETWORK-bestand kan op dat moment nooit een nog-lopende job
    van dit proces zijn (die mappen worden pas aangemaakt ná het starten van de
    server) en is dus altijd het resultaat van een eerder afgebroken job. Mappen die
    beginnen met '_' zijn systeemmappen (bv. _measure_uploads) en worden overgeslagen.
    """
    work = _work_dir()
    for sub in sorted(work.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        if _work_dir_has_network_file(sub):
            continue
        try:
            shutil.rmtree(str(sub))
            print(f"[cleanup] verweesde scenario-map verwijderd: {sub.name}")
        except Exception as _e:
            print(f"[cleanup] verwijderen van map {sub.name} mislukt: {_e}")

    for f in sorted(work.glob("*.json")):
        if f.name == "areas-cache.json":
            continue
        try:
            f.unlink()
            print(f"[cleanup] overbodig bestand verwijderd: {f.name}")
        except Exception as _e:
            print(f"[cleanup] verwijderen van bestand {f.name} mislukt: {_e}")

    _areas_cache_invalidate()


def _discover_constituent_modes(area_id: str, src_dir: Path) -> list:
    """Geef de per-modus namen terug waarvoor een ROUTES-bestand bestaat (niet MIXED zelf).

    Gebruikt bij adjust op een MIXED-gebied om te weten welke modi verwerkt moeten worden.
    """
    stem_pat = re.compile(
        r"^"
        + re.escape(area_id)
        + r"-ROUTES-([A-Za-z0-9]+)\.(geojson|json|parquet|geoparquet)$"
    )
    modes: list = []
    seen: set = set()
    for f in sorted(src_dir.iterdir()):
        m = stem_pat.match(f.name)
        if m:
            mode_m = m.group(1).upper()
            if mode_m != "MIXED" and mode_m not in seen:
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
    for file_type in ("NETWORK", "COMPARE"):
        all_features: list = []
        any_found = False
        for m in modes:
            path = output_folder / f"{new_area_id}-{file_type}-{m}.geojson"
            if not path.exists():
                continue
            any_found = True
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for feat in data.get("features", []):
                feat.setdefault("properties", {})
                if "mode" not in feat["properties"]:
                    feat["properties"]["mode"] = m
            all_features.extend(data.get("features", []))
            path.unlink()  # verwijder per-modus bestand
        if any_found:
            merged_path = output_folder / f"{new_area_id}-{file_type}-MIXED.geojson"
            merged_path.write_text(
                json.dumps(
                    {"type": "FeatureCollection", "features": all_features},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    # ── ZONE en FEEDLINK: eerste beschikbare modus als MIXED ────────────────
    for file_type in ("ZONE", "FEEDLINK"):
        for m in modes:
            path = output_folder / f"{new_area_id}-{file_type}-{m}.geojson"
            if path.exists():
                mixed_path = output_folder / f"{new_area_id}-{file_type}-MIXED.geojson"
                if not mixed_path.exists():
                    path.rename(mixed_path)
                else:
                    path.unlink()
                break


def _post_process_mixed_output(
    new_area_id: str,
    output_folder: Path,
    src_area_id: str,
    src_dir: Path,
    adjusted_mode: str,
    all_modes: list,
) -> None:
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
        src_routes = _find_data_file(src_dir, f"{src_area_id}-ROUTES-{m}")
        if src_routes:
            dst = output_folder / f"{new_area_id}-ROUTES-{m}{src_routes.suffix}"
            if not dst.exists():
                shutil.copy2(str(src_routes), str(dst))

    # ── 2. Features van niet-aangepaste modi uit bron halen ─────────────────
    other_features: list = []
    src_network_path = _find_data_file(src_dir, f"{src_area_id}-NETWORK-MIXED")
    if src_network_path is not None:
        try:
            fc_src = _read_geodata(src_network_path)
            for feat in fc_src.get("features", []):
                feat_mode = (
                    (feat.get("properties") or {}).get("mode") or "CAR"
                ).upper()
                if feat_mode != adjusted_mode:
                    other_features.append(feat)
        except Exception as exc:
            print(f"[adjust-mixed] Kon bron-NETWORK-MIXED niet lezen: {exc}")
    else:
        # Geketende aanroep: bron kan per-modus NETWORK-bestanden hebben
        for m in other_modes:
            src_net_m = _find_data_file(src_dir, f"{src_area_id}-NETWORK-{m}")
            if src_net_m:
                try:
                    fc_m = _read_geodata(src_net_m)
                    for feat in fc_m.get("features", []):
                        feat.setdefault("properties", {}).setdefault("mode", m)
                    other_features.extend(fc_m.get("features", []))
                except Exception as exc:
                    print(f"[adjust-mixed] Kon bron-NETWORK-{m} niet lezen: {exc}")

    # ── 3. Aangepaste NETWORK samenvoegen met overige features ───────────────
    merged_path = output_folder / f"{new_area_id}-NETWORK-MIXED.geojson"

    # Geval A: library heeft al een compleet NETWORK-MIXED geschreven omdat de
    # bronmap ook MIXED was (mode-detectie levert 'MIXED', niet adjusted_mode).
    # Dit bestand bevat al alle modi; direct converteren naar geojson is voldoende.
    adj_mixed_src = _find_data_file(output_folder, f"{new_area_id}-NETWORK-MIXED")
    if adj_mixed_src and adj_mixed_src != merged_path:
        try:
            fc_complete = _read_geodata(adj_mixed_src)
            merged_path.write_text(
                json.dumps(fc_complete, ensure_ascii=False),
                encoding="utf-8",
            )
            if adj_mixed_src.suffix != ".geojson":
                adj_mixed_src.unlink()
        except Exception as exc:
            print(f"[adjust-mixed] Kon NETWORK-MIXED-output niet converteren: {exc}")
    else:
        # Geval B: library schreef een per-modus bestand (bron was per-modus).
        adj_network = output_folder / f"{new_area_id}-NETWORK-{adjusted_mode}.geojson"
        adj_features: list = []
        if adj_network.exists():
            try:
                fc_adj = json.loads(adj_network.read_text(encoding="utf-8"))
                for feat in fc_adj.get("features", []):
                    feat.setdefault("properties", {}).setdefault("mode", adjusted_mode)
                adj_features = fc_adj.get("features", [])
            except Exception as exc:
                print(
                    f"[adjust-mixed] Kon aangepast NETWORK-{adjusted_mode} niet lezen: {exc}"
                )
        merged_path.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": adj_features + other_features,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if adj_network.exists():
            adj_network.unlink()

    # ── 4. ZONE en FEEDLINK hernoemen naar MIXED ─────────────────────────────
    for file_type in ("ZONE", "FEEDLINK"):
        src_f = output_folder / f"{new_area_id}-{file_type}-{adjusted_mode}.geojson"
        dst_f = output_folder / f"{new_area_id}-{file_type}-MIXED.geojson"
        if src_f.exists() and not dst_f.exists():
            src_f.rename(dst_f)

    # ── 5. COMPARE hernoemen naar MIXED ──────────────────────────────────────
    c_src = output_folder / f"{new_area_id}-COMPARE-{adjusted_mode}.geojson"
    c_dst = output_folder / f"{new_area_id}-COMPARE-MIXED.geojson"
    if c_src.exists() and not c_dst.exists():
        c_src.rename(c_dst)


def _get_area_name(area_id: str) -> str:
    """Geef de weergavenaam van een gebied terug.

    Leest op volgorde: .area-name bestand → GeoJSON/parquet properties.name → area_id.
    Dezelfde logica als _discover_areas_uncached.
    """
    src_dir = _find_area_dir(area_id)
    area_name_path = src_dir / ".area-name"
    if area_name_path.exists():
        try:
            name = area_name_path.read_text(encoding="utf-8").strip()
            if name:
                return name
        except Exception:
            pass
    # Zoek een NETWORK-bestand en lees name uit de properties
    for f in sorted(src_dir.glob(f"{area_id}-NETWORK-*")):
        try:
            if f.suffix.lower() in _GEOPARQUET_EXTS and _GEOPANDAS_AVAILABLE:
                raw_meta = _pq.read_metadata(f).metadata
                gmt = raw_meta.get(b"gmt_properties") or raw_meta.get(
                    b"geojson_properties"
                )
                if gmt:
                    props = json.loads(gmt.decode("utf-8"))
                    name = props.get("name", "").strip()
                    if name:
                        return name
            else:
                data = _read_geodata(f)
                name = (data.get("properties") or {}).get("name", "").strip()
                if name:
                    return name
        except Exception:
            continue
    return area_id


def _find_local_file(filename: str) -> "Path | None":
    """Zoek bestand in DATA_DIR, STATIC_DIR en COMMON_DATA_DIR; geeft None als niet gevonden."""
    for base in (DATA_DIR, STATIC_DIR, COMMON_DATA_DIR):
        p = base / filename
        if p.exists():
            return p
    return None


def _patch_geojson_properties(area_id: str, mode: str, name: str):
    """Pas top-level properties.name en properties.area_id aan in alle output-GeoJSON's."""
    for file_type in ("NETWORK", "ZONE", "FEEDLINK", "ROUTES", "COMPARE"):
        path = _find_area_dir(area_id) / f"{area_id}-{file_type}-{mode}.geojson"
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            props = data.setdefault("properties", {})
            props["area_id"] = area_id
            props["name"] = name
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
        except Exception as exc:
            print(f"[server] Kon {path.name} niet patchen: {exc}")


def _get_available_processes() -> set:
    """Geef de set van processIds die momenteel beschikbaar zijn."""
    avail = {"delete-area", "set-directory", "upload-to-gmt"}
    if _PREPARE_AVAILABLE:
        avail.add("prepare")
        avail.add("fetch_osm")
    if _ADJUST_AVAILABLE:
        avail.add("adjust")
    if _WHATIF_AVAILABLE:
        avail.add("whatif-road-closure")
    if _WEGENSCAN_AVAILABLE:
        avail.add("wegenscan")
    return avail


def _job_to_status(job: dict) -> dict:
    """Geef OGC-conform job-statusobject terug (zonder _results)."""
    job_id = job["jobID"]
    return {
        "jobID": job_id,
        "processID": job["processID"],
        "status": job["status"],
        "log": job.get("log", []),
        "created": job.get("created"),
        "started": job.get("started"),
        "finished": job.get("finished"),
        "links": [
            {
                "href": f"/jobs/{job_id}",
                "rel": "self",
                "type": "application/json",
                "title": "Job status",
            },
            {
                "href": f"/jobs/{job_id}/results",
                "rel": "results",
                "type": "application/json",
                "title": "Job resultaten",
            },
        ],
    }


def _ogc_items_response(
    collection_id: str, data, self_url: str, *, as_ndgeojson: bool = False
):
    """Wrap een GeoJSON FeatureCollection in de OGC API Features envelope."""
    if not isinstance(data, dict):
        try:
            data = dict(data)
        except Exception:
            data = {"type": "FeatureCollection", "features": []}

    features = data.get("features", [])
    top_props = (
        data.get("properties") if isinstance(data.get("properties"), dict) else {}
    )
    other = {
        k: v
        for k, v in data.items()
        if k not in ("type", "features", "links", "properties")
    }
    merged = {**top_props, **other}

    # ND-GeoJSON: compact newline-delimited stream zonder wrapper (geen links)
    if as_ndgeojson:
        lines = [json.dumps(feat, ensure_ascii=False) for feat in features]
        body = "\n".join(lines)
        resp = make_response(body)
        resp.headers["Content-Type"] = "application/x-ndgeo+json"
        return resp

    result: dict = {
        "type": "FeatureCollection",
        "features": features,
        "links": [
            {
                "href": self_url,
                "rel": "self",
                "type": "application/geo+json",
                "title": "Dit document",
            },
            {
                "href": f"/collections/{collection_id}",
                "rel": "collection",
                "type": "application/json",
                "title": "Collectiebeschrijving",
            },
        ],
        "timeStamp": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "numberMatched": len(features),
        "numberReturned": len(features),
    }
    if merged:
        result["properties"] = merged

    resp = make_response(json.dumps(result, ensure_ascii=False))
    resp.headers["Content-Type"] = "application/geo+json"
    return resp


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None).isoformat() + "Z"


# ---------------------------------------------------------------------------
# Achtergrond-job runners
# ---------------------------------------------------------------------------


def _sse_notify(src_area_id: str, new_area_id: str, compare_url, mode: str) -> None:
    """Stuur een SSE 'message' event naar alle browsers die dit gebied volgen."""
    payload = json.dumps(
        {
            "new_area_id": new_area_id,
            "compare_url": compare_url,
            "mode": mode,
        }
    )
    _sse_put(src_area_id, "message", payload)


def _sse_notify_started(src_area_id: str, mode: str, job_id: str) -> None:
    """Stuur een SSE 'started' event: berekening is gestart voor dit gebied."""
    _sse_put(src_area_id, "started", json.dumps({"mode": mode, "job_id": job_id}))


def _sse_put(src_area_id: str, event: str, data: str) -> None:
    """Plaatst een (event, data)-tuple in elke queue die luistert op src_area_id."""
    with _sse_listeners_lock:
        listeners = list(_sse_listeners.get(src_area_id, set()))
    print(f"[SSE] {event} → {src_area_id} ({len(listeners)} listener(s))")
    for q in listeners:
        try:
            q.put_nowait((event, data))
        except Exception:
            pass


def _osm_source_summary(osm_path: str | None = None) -> str:
    """Beschrijf de effectieve OSM-databron voor de prepare-pipeline.

    ``osm_path``/``osm_workers`` worden niet via de server-kwargs meegegeven maar
    binnen de pipeline uit de omgeving (``OSM_PBF_PATH`` / ``OSM_PBF_WORKERS``,
    geladen uit ``.env``) geresolved.  Zonder deze regel zou de gelogde aanroep
    ten onrechte suggereren dat de (geheugenlichtere) Overpass HTTP-API gebruikt
    wordt, terwijl lokaal juist de volledige PBF wordt ingelezen — de meest
    waarschijnlijke bron van OOM.
    """
    pbf = (osm_path or os.environ.get("OSM_PBF_PATH", "")).strip()
    if not pbf:
        return "OSM-bron: Overpass HTTP-API (geen OSM_PBF_PATH ingesteld)"
    raw_workers = os.environ.get("OSM_PBF_WORKERS", "").strip()
    cpu = os.cpu_count() or 1
    try:
        from shared._osm_pbf_scan import resolve_workers  # noqa: PLC0415

        n_workers = resolve_workers(raw_workers or None, cpu)
    except ValueError:
        req = 0
        n_workers = max(1, min(req, cpu)) if req > 0 else max(1, min(cpu, 8))
    exists = "aanwezig" if Path(pbf).is_file() else "ONTBREEKT"
    return (
        f"OSM-bron: lokale PBF {pbf!r} ({exists}); "
        f"osm_workers={n_workers} (OSM_PBF_WORKERS={raw_workers or 'onset'}, cpu={cpu})"
    )


def _format_pipeline_call(func_name: str, kwargs: dict) -> str:
    """Formatteer een pipeline-aanroep als leesbare, reproduceerbare Python-call.

    Wordt vóór elke prepare-run in de job-log geschreven zodat de exacte aanroep
    (inclusief bbox, modes en OSM-vlaggen) achteraf te herleiden is — handig bij
    het diagnosticeren van bv. OOM-situaties tijdens de OSM/Overpass-fetch.
    """
    parts = []
    for k, v in kwargs.items():
        # Path-objecten en overige waarden compact en eenduidig weergeven.
        parts.append(f"{k}={v!r}" if not isinstance(v, Path) else f"{k}={str(v)!r}")
    return f"{func_name}(\n    " + ",\n    ".join(parts) + ",\n)"


def _call_prepare_run_pipeline(**kwargs):
    """Roep de prepare-library aan en vertaal verouderde kwarg-namen.

    De server gebruikt historisch 'no_osm'/'only_osm'; de huidige prepare-library
    verwacht 'no_dt'/'only_dt' (digital-twin i.p.v. osm). Vertaal hier zodat de
    aanroep blijft werken zonder alle call-sites aan te passen.
    """
    if "no_osm" in kwargs:
        kwargs["no_dt"] = bool(kwargs.pop("no_osm"))
    if "only_osm" in kwargs:
        kwargs["only_dt"] = bool(kwargs.pop("only_osm"))
    return _prepare_run_pipeline(**kwargs)


def _run_prepare_job(
    job_id: str, out_dir: Path, kwargs: dict, name: str, mode_label: str
):
    """Voer prepare-pipeline uit in achtergrondthread.

    De nieuwe pipeline-versie accepteert 'modes' (lijst) en 'mode_label' rechtstreeks,
    zodat kwargs ongewijzigd doorgegeven kan worden.
    """
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()
    stream = _LogStream(_jobs[job_id]["log"], _jobs_lock)
    try:
        with (
            _pipeline_stdout_lock,
            contextlib.redirect_stdout(stream),
            contextlib.redirect_stderr(stream),
        ):
            print("[server] prepare-pipeline aanroep:")
            print(_format_pipeline_call("run_pipeline", kwargs))
            print(f"[server] {_osm_source_summary(kwargs.get('osm_path'))}")
            _call_prepare_run_pipeline(**kwargs)
        stream.flush()

        # Schrijf .full-twin marker als de OSM/BGT-verrijking gedraaid heeft, zodat
        # het menu-item "Full digital twin" terecht als "klaar" wordt getoond.
        if not kwargs.get("no_osm"):
            try:
                (out_dir / ".full-twin").write_text(_now_iso(), encoding="utf-8")
            except Exception as _e:
                print(f"[full-twin] marker schrijven mislukt: {_e}")

        # Sync naar S3 als geconfigureerd
        if _s3_enabled():
            try:
                _s3_sync_to(out_dir, name)
            except Exception as _e:
                print(f"[s3] sync na prepare mislukt: {_e}")

        _areas_cache_invalidate()
        with _jobs_lock:
            _jobs[job_id]["returncode"] = 0
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {
                "collection": f"/collections/network/items?areaId={name}&mode={mode_label}",
            }
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]["log"].append(f"[server] Fout: {type(exc).__name__}: {exc}")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["returncode"] = -1
            _jobs[job_id]["finished"] = _now_iso()


def _run_osm_prepare_job(job_id: str, out_dir: Path, kwargs: dict, name: str):
    """Voer de OSM-only prepare-pipeline uit in achtergrondthread."""
    env_var = kwargs.get("osm_pbf_env_var", "OSM_PBF_PATH")
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()
    stream = _LogStream(_jobs[job_id]["log"], _jobs_lock)
    old_osm_pbf = os.environ.get(env_var)
    try:
        with (
            _pipeline_stdout_lock,
            contextlib.redirect_stdout(stream),
            contextlib.redirect_stderr(stream),
        ):
            pbf_path = kwargs["osm_path"]
            os.environ[env_var] = str(pbf_path)
            run_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k not in ("osm_path", "osm_pbf_env_var")
            }
            print("[server] osm_prepare-pipeline aanroep:")
            print(_format_pipeline_call("run_pipeline", run_kwargs))
            print(f"[server] {_osm_source_summary(pbf_path)}")
            _osm_prepare_run_pipeline(**run_kwargs)
        stream.flush()

        try:
            (out_dir / ".full-twin").write_text(_now_iso(), encoding="utf-8")
        except Exception as _e:
            print(f"[full-twin] marker schrijven mislukt: {_e}")

        if _s3_enabled():
            try:
                _s3_sync_to(out_dir, name)
            except Exception as _e:
                print(f"[s3] sync na prepare mislukt: {_e}")

        _areas_cache_invalidate()
        with _jobs_lock:
            _jobs[job_id]["returncode"] = 0
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {
                "collection": f"/collections/network/items?areaId={name}&mode=CAR",
            }
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]["log"].append(f"[server] Fout: {type(exc).__name__}: {exc}")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["returncode"] = -1
            _jobs[job_id]["finished"] = _now_iso()
    finally:
        if old_osm_pbf is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = old_osm_pbf


def _run_adjust_job(
    job_id: str,
    kwargs: dict,
    src_area_id: str,
    new_area_id: str,
    mode: str,
    scenario_name,
    all_constituent_modes=None,
):
    """Voer adjust-pipeline uit in achtergrondthread.

    Als *all_constituent_modes* opgegeven is (lijst met ≥2 modi, bijv. ['CAR', 'BIKE'])
    weet de functie dat de bron een MIXED-gebied is.  Na de pipeline-run wordt
    _post_process_mixed_output aangeroepen om de per-modus output samen te voegen
    tot een volledig MIXED-artefact; het resultaat krijgt dan mode='MIXED'.
    """
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()
    stream = _LogStream(_jobs[job_id]["log"], _jobs_lock)
    try:
        with (
            _pipeline_stdout_lock,
            contextlib.redirect_stdout(stream),
            contextlib.redirect_stderr(stream),
        ):
            _adjust_run_pipeline(**kwargs)
        stream.flush()

        # Post-process naar MIXED als bron een MIXED-gebied was
        is_mixed = all_constituent_modes and len(all_constituent_modes) > 1
        if is_mixed:
            src_dir = kwargs["folder"]
            output_folder = kwargs["output_folder"]
            _post_process_mixed_output(
                new_area_id,
                output_folder,
                src_area_id,
                src_dir,
                mode,
                all_constituent_modes,
            )
            result_mode = "MIXED"
        else:
            result_mode = mode

        if scenario_name:
            _patch_geojson_properties(new_area_id, result_mode, scenario_name)

        compare_file = _geojson_path(new_area_id, result_mode, "COMPARE")
        compare_url = (
            f"/collections/comparison/items?areaId={new_area_id}&mode={result_mode}"
            if compare_file.exists()
            else None
        )

        # Sync naar S3 als geconfigureerd
        if _s3_enabled():
            try:
                _s3_sync_to(kwargs["output_folder"], new_area_id)
            except Exception as _e:
                print(f"[s3] sync na adjust mislukt: {_e}")

        _areas_cache_invalidate()
        with _jobs_lock:
            _jobs[job_id]["returncode"] = 0
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {
                "new_area_id": new_area_id,
                "collection": f"/collections/network/items?areaId={new_area_id}&mode={result_mode}",
                "compare_url": compare_url,
            }
        _sse_notify(src_area_id, new_area_id, compare_url, result_mode)
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]["log"].append(f"[server] Fout: {type(exc).__name__}: {exc}")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["returncode"] = -1
            _jobs[job_id]["finished"] = _now_iso()


def _run_adjust_job_mixed(
    job_id: str,
    base_kwargs: dict,
    src_area_id: str,
    new_area_id: str,
    routes_per_mode: dict,
    scenario_name,
):
    """Voer adjust-pipeline uit voor elk samenstellend modus van een MIXED-gebied.

    Volgorde:
    1. Per modus (bijv. CAR, BIKE) de adjust-pipeline draaien met de bijbehorende routes.
    2. Per-modus NETWORK/COMPARE/ZONE/FEEDLINK samenvoegen tot MIXED-artefacten.
    3. Job-status bijwerken.
    """
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()
    stream = _LogStream(_jobs[job_id]["log"], _jobs_lock)
    output_folder = base_kwargs["output_folder"]
    try:
        with (
            _pipeline_stdout_lock,
            contextlib.redirect_stdout(stream),
            contextlib.redirect_stderr(stream),
        ):
            for m, routes_path in routes_per_mode.items():
                print(f"[adjust-mixed] Modus {m} verwerken …")
                kwargs_m = {**base_kwargs, "routes_path": routes_path}
                _adjust_run_pipeline(**kwargs_m)
        stream.flush()

        _merge_mixed_outputs(new_area_id, output_folder, list(routes_per_mode.keys()))

        if scenario_name:
            _patch_geojson_properties(new_area_id, "MIXED", scenario_name)

        compare_file = _geojson_path(new_area_id, "MIXED", "COMPARE")
        compare_url = (
            f"/collections/comparison/items?areaId={new_area_id}&mode=MIXED"
            if compare_file.exists()
            else None
        )

        # Sync naar S3 als geconfigureerd
        if _s3_enabled():
            try:
                _s3_sync_to(output_folder, new_area_id)
            except Exception as _e:
                print(f"[s3] sync na adjust-mixed mislukt: {_e}")

        _areas_cache_invalidate()
        with _jobs_lock:
            _jobs[job_id]["returncode"] = 0
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {
                "new_area_id": new_area_id,
                "collection": f"/collections/network/items?areaId={new_area_id}&mode=MIXED",
                "compare_url": compare_url,
            }
        _sse_notify(src_area_id, new_area_id, compare_url, "MIXED")
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]["log"].append(f"[server] Fout: {type(exc).__name__}: {exc}")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["returncode"] = -1
            _jobs[job_id]["finished"] = _now_iso()


def _run_whatif_road_closure_job(
    job_id: str,
    path_geojson: str,
    path_csv: str,
    output_folder: Path,
    new_area_id: str,
    src_area_id: str,
    mode: str,
    selected_links: list,
    direction: str,
    motive: str,
    period: str,
    nroutes: int,
    measure: str,
    reduction_factor: float,
    scenario_name,
):
    """Voer de what-if wegafsluiting uit in een achtergrondthread."""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()
    stream = _LogStream(_jobs[job_id]["log"], _jobs_lock)

    try:
        with (
            _pipeline_stdout_lock,
            contextlib.redirect_stdout(stream),
            contextlib.redirect_stderr(stream),
        ):
            # ── 1. Inlezen ────────────────────────────────────────────────
            print("[whatif] Netwerk en NVP-routes inlezen …")
            nodes, links, links_opposite, volumes, segments, tripsarr, trippaths = (
                _whatif_read_data_geojson(path_geojson, path_csv)
            )

            # ── 2. Voorbereiden ───────────────────────────────────────────
            print("[whatif] Data voorbereiden …")
            imotive = _WI_MOTIVES[motive]
            iperiod = _WI_PERIODS[period]
            sel_links_grouped = [[lid] for lid in selected_links]

            (
                nodexys,
                selected_segments,
                opposite_segments,
                qsegsmodel,
                qmodel,
                segments_to_links,
            ) = _wi_prepare_data(
                nodes,
                links,
                links_opposite,
                segments,
                volumes,
                sel_links_grouped,
                direction,
                imotive,
                iperiod,
            )

            # ── 3. Selectie ───────────────────────────────────────────────
            print("[whatif] Ritpaden selecteren …")
            nsel_pass = 1
            tripweights = _wi_initialize_weights(tripsarr)
            trippaths2, tripweights2, trippaths12, trippaths21 = _wi_get_selection(
                trippaths, tripweights, selected_segments, nsel_pass
            )

            # ── 4. Aantal segmenten ───────────────────────────────────────
            nsegment, nsegment2 = _wi_get_nsegments(segments, trippaths21)

            # ── 5. Rondritten opschonen ───────────────────────────────────
            print("[whatif] Rondritten opschonen …")
            tripweights2 = _wi_clean_trips(
                selected_segments,
                opposite_segments,
                tripweights2,
                trippaths2,
                trippaths12,
            )

            # ── 6. Kalibratie ─────────────────────────────────────────────
            print("[whatif] Ritvolumes kalibreren …")
            porttrips2_all = _wi_initialize_mask(trippaths2["trip"])
            ratio_model, qsegs_sel, qsegs_sel2 = _wi_calibrate_tripvolumes(
                selected_segments,
                qsegsmodel,
                trippaths12,
                trippaths21,
                trippaths2,
                tripweights2,
                porttrips2_all,
                nsegment,
                nsegment2,
            )

            # ── 7. Grafen (basissituatie) ─────────────────────────────────
            print("[whatif] Grafen opbouwen …")
            G, Gback, nodepairs_segs, nodecosts = _wi_get_graphs_base(
                segments, selected_segments, qsegsmodel, nsegment
            )

            # ── 8. OD-knopen en paden ─────────────────────────────────────
            print("[whatif] OD-relaties bepalen …")
            onodes, dnodes, osegs2, dsegs2, opaths, dpaths = _wi_get_ods(
                G,
                Gback,
                segments,
                nsegment,
                selected_segments,
                opposite_segments,
                trippaths12,
                trippaths21,
                trippaths2,
                tripweights2,
                porttrips2_all,
                nsegment2,
                _WI_FRACT_CHANGE,
                _WI_MIN_NVP,
                nodexys,
                _WI_MIN_RADIUS_ODNODE,
            )

            # ── 9. Nieuwe paden (omleidingen) ─────────────────────────────
            print("[whatif] Omleidingspaden zoeken …")
            newpaths, validpaths = _wi_get_new_paths(
                G, onodes, dnodes, selected_segments
            )

            # ── 10. OD-flows op geselecteerd segment ──────────────────────
            print("[whatif] OD-flows berekenen …")
            qsegsmodel_od = _wi_selected_od_flows(
                selected_segments,
                qsegsmodel,
                qsegs_sel,
                ratio_model,
                nsegment,
                nsegment2,
                trippaths12,
                trippaths21,
                trippaths2,
                tripweights2,
                porttrips2_all,
                onodes,
                dnodes,
                osegs2,
                dsegs2,
                validpaths,
            )

            # ── 11. Reductiefactor toepassen ──────────────────────────────
            qsegsmodel_od = _wi_adopt_reduction(
                qsegsmodel_od, measure, reduction_factor, _WI_POWER_RATIO
            )

            # ── 12. Volledige toewijzing ───────────────────────────────────
            print(f"[whatif] Volledige toewijzing ({nroutes} routes) …")
            qsegsmodel_dmin, qsegsmodel_dplus = _wi_full_assignment(
                segments,
                selected_segments,
                nsegment,
                qsegsmodel,
                qsegsmodel_od,
                G,
                Gback,
                nodepairs_segs,
                nodecosts,
                onodes,
                dnodes,
                opaths,
                dpaths,
                newpaths,
                validpaths,
                _WI_CWEIGHT_ADD,
                nroutes,
            )

            # ── 13. Verschilflows links ───────────────────────────────────
            qmodel_dmin, qmodel_dplus = _wi_get_difference_flows(
                links, qmodel, segments_to_links, qsegsmodel_dmin, qsegsmodel_dplus
            )

            # ── 14. Export what-if NETWORK GeoJSON ────────────────────────
            print("[whatif] Resultaat exporteren …")
            output_folder.mkdir(parents=True, exist_ok=True)
            path_network_out = output_folder / f"{new_area_id}-NETWORK-{mode}.geojson"
            _whatif_export_network(
                links,
                qmodel,
                qmodel_dmin,
                qmodel_dplus,
                path_geojson,
                str(path_network_out),
            )

            # ── 15. Originele ROUTES en ZONE kopiëren ────────────────────
            src_dir = _find_area_dir(src_area_id)
            for file_type in ("ROUTES", "ZONE", "FEEDLINK"):
                src_file = src_dir / f"{src_area_id}-{file_type}-{mode}.geojson"
                if src_file.exists():
                    dst_file = (
                        output_folder / f"{new_area_id}-{file_type}-{mode}.geojson"
                    )
                    shutil.copy2(str(src_file), str(dst_file))

            # ── 16. Patcheer top-level properties ────────────────────────
            if scenario_name:
                _patch_geojson_properties(new_area_id, mode, scenario_name)

            # ── 17. Sla brongebied op voor ScenarioVergelijker ────────────
            (output_folder / ".src-area-id").write_text(src_area_id, encoding="utf-8")

        stream.flush()
        _areas_cache_invalidate()
        with _jobs_lock:
            _jobs[job_id]["returncode"] = 0
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {
                "new_area_id": new_area_id,
                "collection": f"/collections/network/items?areaId={new_area_id}&mode={mode}",
            }

    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]["log"].append(f"[server] Fout: {type(exc).__name__}: {exc}")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["returncode"] = -1
            _jobs[job_id]["finished"] = _now_iso()


# ---------------------------------------------------------------------------
# Process execute helpers
# ---------------------------------------------------------------------------


def _run_wegenscan_job(job_id: str, area_id: str, mode: str):
    """Voer wegenscan-pipeline (enrichment + KPI-berekening) uit in achtergrondthread."""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()
    stream = _LogStream(_jobs[job_id]["log"], _jobs_lock)
    try:
        with (
            _pipeline_stdout_lock,
            contextlib.redirect_stdout(stream),
            contextlib.redirect_stderr(stream),
        ):
            network_path = _data_path(area_id, mode, "NETWORK")
            if network_path is None:
                raise FileNotFoundError(
                    f"Geen NETWORK-bestand gevonden voor area_id={area_id!r}, mode={mode!r}"
                )
            print(f"[wegenscan] Netwerk laden: {network_path.name}")
            geojson = _read_geodata(network_path)
            print(f"[wegenscan] {len(geojson.get('features', []))} features geladen")
            result = _ws_run_pipeline(geojson, id_field="spectrumId")  # type: ignore[misc]
        stream.flush()

        out_path = _find_area_dir(area_id) / f"{area_id}-WEGENSCAN-{mode}.geojson"
        out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(f"[wegenscan] Resultaat opgeslagen: {out_path.name}")

        with _jobs_lock:
            _jobs[job_id]["returncode"] = 0
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {
                "collection": f"/collections/wegenscan/items?areaId={area_id}&mode={mode}",
            }
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]["log"].append(f"[server] Fout: {type(exc).__name__}: {exc}")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["returncode"] = -1
            _jobs[job_id]["finished"] = _now_iso()


def _network_bbox(net_path: Path) -> "list | None":
    """Bepaal de bbox [min_lon, min_lat, max_lon, max_lat] uit een NETWORK-bestand."""
    try:
        ndata = _read_geodata(net_path)
    except Exception:
        return None
    bbox = ndata.get("properties", {}).get("bbox")
    if bbox and len(bbox) >= 4:
        return list(bbox[:4])
    lons, lats = [], []
    for feat in ndata.get("features", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        # Ondersteun zowel LineString als (Multi)Polygon door plat te maken
        stack = [coords]
        while stack:
            cur = stack.pop()
            if (
                isinstance(cur, (list, tuple))
                and len(cur) >= 2
                and isinstance(cur[0], (int, float))
                and isinstance(cur[1], (int, float))
            ):
                lons.append(cur[0])
                lats.append(cur[1])
            elif isinstance(cur, (list, tuple)):
                stack.extend(cur)
    if lons:
        return [min(lons), min(lats), max(lons), max(lats)]
    return None


def _bbox_to_polygon(bbox: "list | None") -> "dict | None":
    """Zet een bbox [min_lon, min_lat, max_lon, max_lat] om naar een GeoJSON Polygon."""
    if not bbox or len(bbox) < 4:
        return None
    min_lon, min_lat, max_lon, max_lat = bbox[:4]
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def _run_fetch_osm_job(job_id: str, area_id: str):
    """Verrijk een bestaand gebied met OSM-data (Full digital twin).

    Draait prepare's stage-5 opnieuw met only_osm=True voor elk mode_label van
    het gebied. Herschrijft NETWORK (trafficSignal), TRAFFIC-ASSETS en BUILDINGS.
    """
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()
    stream = _LogStream(_jobs[job_id]["log"], _jobs_lock)
    try:
        area_dir = _find_area_dir(area_id)
        if not area_dir.is_dir():
            raise FileNotFoundError(f"Geen map gevonden voor gebied: {area_id}")

        # Bepaal alle mode_labels via de NETWORK-bestanden van dit gebied
        net_files: dict = {}
        for ext in (".geojson", *_GEOPARQUET_EXTS):
            for p in area_dir.glob(f"{area_id}-NETWORK-*{ext}"):
                m = re.match(
                    rf"^{re.escape(area_id)}-NETWORK-(.+){re.escape(ext)}$", p.name
                )
                if m:
                    label = m.group(1).upper()
                    net_files.setdefault(label, p)
        if not net_files:
            raise FileNotFoundError(
                f"Geen NETWORK-bestand gevonden voor area_id={area_id!r}"
            )

        name = area_dir.name
        with (
            _pipeline_stdout_lock,
            contextlib.redirect_stdout(stream),
            contextlib.redirect_stderr(stream),
        ):
            for mode_label, net_path in sorted(net_files.items()):
                bbox = _network_bbox(net_path)
                if not bbox:
                    raise RuntimeError(
                        f"Geen bbox beschikbaar voor NETWORK {net_path.name}"
                    )
                if mode_label == "MIXED":
                    modes = ["CAR", "BIKE"]
                else:
                    modes = [mode_label]
                print(f"[fetch_osm] OSM-verrijking voor mode_label={mode_label}")
                _osm_kwargs = dict(
                    min_lon=bbox[0],
                    min_lat=bbox[1],
                    max_lon=bbox[2],
                    max_lat=bbox[3],
                    modes=modes,
                    mode_label=mode_label,
                    name=name,
                    out_dir=area_dir,
                    area_id=area_id,
                    catalog="spectrum",
                    schema="2024_01",
                    only_osm=True,
                )
                print("[server] prepare-pipeline aanroep (only_osm):")
                print(_format_pipeline_call("run_pipeline", _osm_kwargs))
                print(f"[server] {_osm_source_summary()}")
                _call_prepare_run_pipeline(**_osm_kwargs)
        stream.flush()

        # Schrijf .full-twin marker: dit gebied heeft nu echte OSM/BGT-verrijking.
        try:
            (area_dir / ".full-twin").write_text(_now_iso(), encoding="utf-8")
        except Exception as _e:
            print(f"[full-twin] marker schrijven mislukt: {_e}")

        if _s3_enabled():
            try:
                _s3_sync_to(area_dir, name)
            except Exception as _e:
                print(f"[s3] sync na fetch_osm mislukt: {_e}")

        _areas_cache_invalidate()
        with _jobs_lock:
            _jobs[job_id]["returncode"] = 0
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {"areaId": area_id}
    except BaseException as exc:
        stream.flush()
        with _jobs_lock:
            _jobs[job_id]["log"].append(f"[server] Fout: {type(exc).__name__}: {exc}")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["returncode"] = -1
            _jobs[job_id]["finished"] = _now_iso()


def _execute_fetch_osm(inputs: dict):
    """Start OSM-verrijking (Full digital twin) als async job."""
    if not _PREPARE_AVAILABLE:
        abort(503, "prepare-package niet beschikbaar")

    area_id = str(inputs.get("area_id", "")).strip()
    if not _safe(area_id):
        abort(400, f"Ongeldige of ontbrekende area_id: {area_id!r}")

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "jobID": job_id,
            "processID": "fetch_osm",
            "status": "accepted",
            "log": [],
            "returncode": None,
            "created": _now_iso(),
            "started": None,
            "finished": None,
            "_results": {},
        }
    threading.Thread(
        target=_run_fetch_osm_job,
        args=(job_id, area_id),
        daemon=True,
    ).start()
    return {"jobID": job_id, "status": "accepted"}, 201, {"Location": f"/jobs/{job_id}"}


def _execute_prepare(inputs: dict):
    """Start prepare als async job. Geeft (body, 201, headers) terug."""
    if not _PREPARE_AVAILABLE:
        abort(503, "prepare-package niet beschikbaar")

    name = str(inputs.get("name", "")).strip()
    out_dir = Path(inputs.get("out_dir") or str(_work_dir() / name)).resolve()

    # Modes: accepteer 'modes' (array) of 'mode' (string, achterwaartse compatibiliteit)
    raw_modes = inputs.get("modes")
    if raw_modes and isinstance(raw_modes, list) and len(raw_modes) > 0:
        modes = [str(m).upper() for m in raw_modes]
    else:
        modes = [str(inputs.get("mode", "CAR")).upper()]

    # Valideer modes
    _valid_modes = {"CAR", "BIKE", "PEDESTRIAN"}
    for m in modes:
        if m not in _valid_modes:
            abort(
                400,
                f"Ongeldige modus: {m!r}. Toegestaan: {', '.join(sorted(_valid_modes))}",
            )
    if len(modes) > 1 and "PEDESTRIAN" in modes:
        abort(400, "PEDESTRIAN kan niet gecombineerd worden met andere modi")

    # mode_label: expliciet meegegeven of automatisch bepaald
    raw_label = str(inputs.get("mode_label", "")).strip().upper()
    mode_label = raw_label if raw_label else ("MIXED" if len(modes) > 1 else modes[0])

    try:
        min_lon = float(inputs["min_lon"])
        min_lat = float(inputs["min_lat"])
        max_lon = float(inputs["max_lon"])
        max_lat = float(inputs["max_lat"])
    except (KeyError, ValueError, TypeError):
        abort(400, "Ongeldige of ontbrekende bbox-parameters")

    if not name:
        abort(400, 'Parameter "name" ontbreekt')

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".area-uuid").write_text(name, encoding="utf-8")
    if _s3_enabled():
        try:
            _s3_write_text(_s3_key(name, ".area-uuid"), name)
        except Exception as _e:
            print(f"[s3] .area-uuid schrijven mislukt: {_e}")

    # Bepaal de OSM-bron. Een expliciet pad (input of env) heeft voorrang;
    # anders wordt het kleinste Geofabrik-extract dat de bbox bevat opgehaald.
    explicit_osm_path = (
        inputs.get("osm_path") or os.environ.get(_OSM_PBF_ENV_VAR) or ""
    ).strip()
    pbf_cache_dir = Path(
        inputs.get("pbf_cache_dir")
        or os.environ.get(_OSM_PBF_CACHE_DIR_ENV_VAR, "")
        or _DEFAULT_PBF_CACHE_DIR
    )
    if explicit_osm_path:
        pbf_path_obj = Path(explicit_osm_path)
        if not pbf_path_obj.is_file() or pbf_path_obj.suffix.lower() != ".pbf":
            abort(
                400, f"OSM PBF pad is geen leesbaar .pbf bestand: {explicit_osm_path}"
            )
        pbf_path = str(pbf_path_obj)
    else:
        if not _GEOFABRIK_PBF_AVAILABLE:
            abort(
                503,
                "Geofabrik PBF resolver niet beschikbaar en geen OSM_PBF_PATH ingesteld",
            )
        try:
            pbf_path_obj, _ = _resolve_or_download_pbf(
                min_lon,
                min_lat,
                max_lon,
                max_lat,
                cache_dir=pbf_cache_dir,
            )
        except Exception as exc:
            abort(400, f"Kon geen passend Geofabrik-extract vinden/downloaden: {exc}")
        pbf_path = str(pbf_path_obj)

    # Bepaal of de bbox in Nederland ligt; dat kiest de pipeline.
    if _GEOFABRIK_PBF_AVAILABLE:
        within_nl = _is_within_netherlands(
            min_lon, min_lat, max_lon, max_lat, cache_dir=pbf_cache_dir
        )
    else:
        within_nl = _is_netherlands([min_lon, min_lat, max_lon, max_lat])

    # Vegetatie-vinkje (voorheen "Full digital twin"). De OSM/BGT-verrijking
    # zelf draait altijd; dit vinkje schakelt alleen het ophalen van vegetatie.
    fetch_vegetation = bool(inputs.get("vegetation", True))
    # Hoogte-vinkje: haalt AHN-hoogtedata op voor de wegvakken. Kost extra tijd
    # (één request per batch wegvakken), vandaar uitschakelbaar.
    fetch_elevation = bool(inputs.get("elevation", True))

    job_id = str(uuid.uuid4())

    if within_nl:
        if not _PREPARE_AVAILABLE:
            abort(503, "prepare-package niet beschikbaar")
        kwargs = dict(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            modes=modes,
            mode_label=mode_label,
            name=name,
            out_dir=out_dir,
            max_routes=5,
            catalog=inputs.get("catalog", "spectrum"),
            schema=inputs.get("schema", "2024_01"),
            refresh=bool(inputs.get("refresh")),
            debug=bool(inputs.get("debug", False)),
            osm_path=pbf_path,
            fetch_vegetation=fetch_vegetation,
            add_elevation=fetch_elevation,
        )
        with _jobs_lock:
            _jobs[job_id] = {
                "jobID": job_id,
                "processID": "prepare",
                "status": "accepted",
                "log": [],
                "returncode": None,
                "out_dir": str(out_dir),
                "created": _now_iso(),
                "started": None,
                "finished": None,
                "_results": {},
            }
        threading.Thread(
            target=_run_prepare_job,
            args=(job_id, out_dir, kwargs, name, mode_label),
            daemon=True,
        ).start()
    else:
        if not _OSM_PREPARE_AVAILABLE:
            abort(
                503,
                "osm_prepare-package niet beschikbaar voor gebieden buiten Nederland",
            )
        kwargs = dict(
            min_lon=min_lon,
            min_lat=min_lat,
            max_lon=max_lon,
            max_lat=max_lat,
            out_dir=out_dir,
            area_id=name,
            name=name,
            refresh=bool(inputs.get("refresh")),
            debug=bool(inputs.get("debug", False)),
            osm_path=pbf_path,
            osm_pbf_env_var=_OSM_PBF_ENV_VAR,
        )
        with _jobs_lock:
            _jobs[job_id] = {
                "jobID": job_id,
                "processID": "prepare",
                "status": "accepted",
                "log": [],
                "returncode": None,
                "out_dir": str(out_dir),
                "created": _now_iso(),
                "started": None,
                "finished": None,
                "_results": {},
            }
        threading.Thread(
            target=_run_osm_prepare_job,
            args=(job_id, out_dir, kwargs, name),
            daemon=True,
        ).start()

    return {"jobID": job_id, "status": "accepted"}, 201, {"Location": f"/jobs/{job_id}"}


def _execute_adjust(inputs: dict):
    """Start adjust als async job. Geeft (body, 201, headers) terug."""
    if not _ADJUST_AVAILABLE:
        abort(503, "adjust-package niet beschikbaar")

    area_id = str(inputs.get("area_id", "")).strip()
    mode = str(inputs.get("mode", "CAR")).upper()
    changes = inputs.get("changes", [])
    scenario_name = str(inputs.get("scenario_name", "")).strip() or None

    if not area_id:
        abort(400, 'Parameter "area_id" ontbreekt')
    if not isinstance(changes, list) or not changes:
        abort(400, 'Parameter "changes" moet een niet-lege array zijn')

    # ── Voeg datum/tijd toe aan de scenarionaam ──────────────────────────────
    # Haal de naam van het bronscenario op via de helper (zelfde logica als
    # _discover_areas: .area-name → GeoJSON properties → area_id als fallback).
    _src_base_name = _get_area_name(area_id)
    # Knip een eventuele vorige tijdstempel af (patroon " — HH:MM") zodat bij
    # geketende scenario's de naam niet steeds langer wordt.
    _src_base_name = re.sub(r"\s*—\s*\d{2}:\d{2}$", "", _src_base_name)
    _ts = _dt.datetime.now().strftime("%H:%M")
    scenario_name = f"{scenario_name or _src_base_name} — {_ts}"

    # ── Splits link-inserties (geometry aanwezig, geen linkId) van reguliere wijzigingen
    link_inserts = [
        c for c in changes if c.get("geometry") is not None and not c.get("linkId")
    ]
    regular_changes = [
        c
        for c in changes
        if not (c.get("geometry") is not None and not c.get("linkId"))
    ]
    has_inserts = bool(link_inserts)
    if has_inserts and not _LINK_INSERTER_AVAILABLE:
        abort(503, "network_link_inserter-package niet beschikbaar voor link-inserties")

    src_dir = _find_area_dir(area_id)

    # ── Bepaal routes-bestand(en) ────────────────────────────────────────────
    if mode == "MIXED":
        # MIXED-gebied: per samenstellend modus (bijv. CAR, BIKE) een eigen ROUTES-bestand
        constituent_modes = _discover_constituent_modes(area_id, src_dir)
        if not constituent_modes:
            abort(
                404,
                f"Geen per-modus ROUTES-bestanden gevonden voor MIXED-gebied: {area_id}",
            )
        routes_per_mode: dict = {}
        for m in constituent_modes:
            rf = _find_data_file(src_dir, f"{area_id}-ROUTES-{m}")
            if rf is None:
                abort(404, f"Routes-bestand niet gevonden: {area_id}-ROUTES-{m}")
            routes_per_mode[m] = rf
    else:
        routes_file = _find_data_file(src_dir, f"{area_id}-ROUTES-{mode}")
        if routes_file is None:
            abort(404, f"Routes-bestand niet gevonden: {area_id}-ROUTES-{mode}")

        # Detecteer of de bron een MIXED-gebied is (heeft ROUTES voor ≥2 modi)
        all_constituent = _discover_constituent_modes(area_id, src_dir)
        is_mixed_source = len(all_constituent) > 1 and mode in all_constituent

    new_area_id = str(uuid.uuid4())
    if scenario_name:
        folder_name = re.sub(r"[^\w\-]", "_", scenario_name.strip())
        folder_name = re.sub(r"_+", "_", folder_name).strip("_") or new_area_id
    else:
        folder_name = new_area_id
    output_folder = _work_dir() / folder_name
    output_folder.mkdir(parents=True, exist_ok=True)

    (output_folder / ".src-area-id").write_text(area_id, encoding="utf-8")
    if scenario_name:
        (output_folder / ".area-name").write_text(scenario_name, encoding="utf-8")

    # Neem de maquette-calibratie mee naar het nieuwe scenario. De fysieke
    # opstelling (camera/beamer + kaartweergave) verandert niet door een
    # afsluiting, dus de calibratie blijft geldig. Zonder deze kopie zou de
    # camera bij het opnieuw aanzetten opnieuw willen calibreren omdat er in de
    # nieuwe area-directory geen <new_area_id>-CALIBRATION.json staat.
    try:
        src_calib = _calibration_path(area_id)
        if src_calib.is_file():
            dst_calib = output_folder / f"{new_area_id}-CALIBRATION.json"
            shutil.copyfile(src_calib, dst_calib)
    except Exception as _e:
        print(f"[maquette] calibratie kopiëren naar nieuw scenario mislukt: {_e}")

    changes_file = output_folder / f"{new_area_id}-changes.json"
    # Schrijf alleen reguliere wijzigingen (geen link-inserties) naar het changes-bestand
    changes_file.write_text(
        json.dumps(regular_changes, ensure_ascii=False), encoding="utf-8"
    )

    (src_dir / ".area-uuid").write_text(area_id, encoding="utf-8")

    if _s3_enabled():
        try:
            _s3_write_text(_s3_key(new_area_id, ".src-area-id"), area_id)
            _s3_write_bytes(
                _s3_key(new_area_id, f"{new_area_id}-changes.json"),
                json.dumps(changes, ensure_ascii=False).encode("utf-8"),
                "application/json",
            )
            _s3_write_text(_s3_key(area_id, ".area-uuid"), area_id)
        except Exception as _e:
            print(f"[s3] metadata schrijven mislukt: {_e}")

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "jobID": job_id,
            "processID": "adjust",
            "status": "accepted",
            "log": [],
            "returncode": None,
            "out_dir": str(output_folder),
            "created": _now_iso(),
            "started": None,
            "finished": None,
            "_results": {},
        }

    if mode == "MIXED":
        base_kwargs = dict(
            folder=src_dir,
            changes=str(changes_file),
            output_folder=output_folder,
            new_area_id=new_area_id,
            min_link_trips=1.0,
            debug=bool(inputs.get("debug", False)),
        )
        threading.Thread(
            target=_run_adjust_job_mixed,
            args=(
                job_id,
                base_kwargs,
                area_id,
                new_area_id,
                routes_per_mode,
                scenario_name,
            ),
            daemon=True,
        ).start()
        _sse_notify_started(area_id, "MIXED", job_id)
    else:
        kwargs = dict(
            folder=src_dir,
            changes=str(changes_file),
            output_folder=output_folder,
            routes_path=routes_file,
            new_area_id=new_area_id,
            min_link_trips=1.0,
            debug=bool(inputs.get("debug", False)),
        )
        if has_inserts:
            threading.Thread(
                target=_run_adjust_with_inserts_job,
                args=(
                    job_id,
                    kwargs,
                    link_inserts,
                    src_dir,
                    area_id,
                    new_area_id,
                    mode,
                    scenario_name,
                    all_constituent if is_mixed_source else None,
                ),
                daemon=True,
            ).start()
            _sse_notify_started(area_id, mode, job_id)
        else:
            threading.Thread(
                target=_run_adjust_job,
                args=(
                    job_id,
                    kwargs,
                    area_id,
                    new_area_id,
                    mode,
                    scenario_name,
                    all_constituent if is_mixed_source else None,
                ),
                daemon=True,
            ).start()
            _sse_notify_started(area_id, mode, job_id)
    return {"jobID": job_id, "status": "accepted"}, 201, {"Location": f"/jobs/{job_id}"}


# ---------------------------------------------------------------------------
# Adjust met link-inserties
# ---------------------------------------------------------------------------


def _run_adjust_with_inserts_job(
    job_id: str,
    job_kwargs: dict,
    link_inserts: "list[dict]",
    src_dir: Path,
    area_id: str,
    new_area_id: str,
    mode: str,
    scenario_name: "str | None",
    all_constituent: "list | None",
):
    """
    Voert eerst network_link_inserter.insert_links() uit op het bronnetwerk,
    herberekent daarna alle routes via Dijkstra en start vervolgens de normale
    adjust-pipeline voor eventuele resterende wijzigingen (cap/speed/flow/OD).
    """
    from shared.geoparquet import from_geoparquet, to_geoparquet  # type: ignore[import]
    from route_explorer.core.route_explorer_core import (  # type: ignore[import]
        recompute_routes_for_pairs,
    )

    def log(msg: str):
        with _jobs_lock:
            _jobs[job_id]["log"].append(msg)
        print(f"[adjust+insert] {msg}")

    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()

    output_folder: Path = job_kwargs["output_folder"]

    try:
        # ── 1. Laad bronbestanden ────────────────────────────────────────────
        log("Bronbestanden laden…")
        net_path = _data_path(area_id, mode, "NETWORK")
        zone_path = _data_path(area_id, mode, "ZONE")
        feed_path = _data_path(area_id, mode, "FEEDLINK")
        routes_path = Path(job_kwargs["routes_path"])

        if not net_path or not net_path.exists():
            raise FileNotFoundError(f"NETWORK niet gevonden voor {area_id}/{mode}")
        if not zone_path or not zone_path.exists():
            raise FileNotFoundError(f"ZONE niet gevonden voor {area_id}/{mode}")
        if not feed_path or not feed_path.exists():
            raise FileNotFoundError(f"FEEDLINK niet gevonden voor {area_id}/{mode}")

        network_fc = _read_geodata(net_path)
        zones_fc = _read_geodata(zone_path)
        feedlinks_fc = _read_geodata(feed_path)
        routes_bytes = routes_path.read_bytes()
        routes_fc = from_geoparquet(routes_bytes)
        log(
            f"Netwerk: {len(network_fc.get('features', []))} features | "
            f"Zones: {len(zones_fc.get('features', []))} | "
            f"Routes: {len(routes_fc.get('features', []))}"
        )

        # ── 2. Voeg nieuwe wegvakken in ──────────────────────────────────────
        log(f"Nieuwe wegvakken invoegen ({len(link_inserts)} stuk(s))…")
        insert_changes = [
            {
                "linkId": None,
                "geometry": ins["geometry"],
                "speed": float(ins.get("speed", 50)),
                "capacity": float(ins.get("capacity", 900)),
                "lanes": int(ins.get("lanes", 1)),
                "direction": "forward",
            }
            for ins in link_inserts
        ]

        modified_network_fc, report = _insert_links(network_fc, insert_changes)
        # network_link_inserter's report gebruikt "inserted"/"links_added" (int-tellers,
        # geen "inserted_links"/"split_links" lijsten) — splits zijn alleen af te leiden
        # uit de per-wijziging outcomes (start/end_snapped met method "split").
        n_new = report.get("inserted", 0)
        n_split = sum(
            1
            for ch in report.get("changes", [])
            for key in ("start_snapped", "end_snapped")
            if isinstance(ch.get(key), dict) and ch[key].get("method") == "split"
        )
        log(f"Ingevoegd: {n_new} nieuwe wegvakken, {n_split} bestaande gesplitst")
        for _w in report.get("warnings", []):
            log(f"Waarschuwing: {_w}")

        # ── 3. Schrijf gewijzigd NETWORK naar outputmap ──────────────────────
        log("Gewijzigd netwerk opslaan…")
        net_out = output_folder / f"{new_area_id}-NETWORK-{mode}.parquet"
        net_out.write_bytes(to_geoparquet(modified_network_fc))

        # ── 4. Kopieer ZONE en FEEDLINK ──────────────────────────────────────
        import shutil

        zone_out = output_folder / f"{new_area_id}-ZONE-{mode}.parquet"
        feed_out = output_folder / f"{new_area_id}-FEEDLINK-{mode}.parquet"
        shutil.copy2(zone_path, zone_out)
        shutil.copy2(feed_path, feed_out)
        log("ZONE en FEEDLINK gekopieerd")

        # ── 5. Herbereken alle routes op nieuw netwerk ───────────────────────
        log("Alle routes herberekenen op gewijzigd netwerk (Dijkstra)…")
        seen_pairs: set = set()
        existing_pairs: list = []
        for feat in routes_fc.get("features", []):
            p = feat.get("properties", {})
            from_id = p.get("fromZoneId")
            to_id = p.get("toZoneId")
            if from_id is None or to_id is None:
                continue
            key = (str(from_id), str(to_id))
            if key not in seen_pairs:
                seen_pairs.add(key)
                existing_pairs.append(
                    {
                        "fromId": from_id,
                        "toId": to_id,
                        "fromType": p.get("fromType", "zone"),
                        "toType": p.get("toType", "zone"),
                        "tripFraction": p.get("tripFraction", 0),
                    }
                )
        log(f"{len(existing_pairs)} OD-paren herberekenen…")
        new_routes_fc = recompute_routes_for_pairs(
            modified_network_fc,
            feedlinks_fc,
            zones_fc,
            existing_pairs,
        )
        log(f"Routes herberekend: {len(new_routes_fc.get('features', []))} OD-paren")

        routes_out = output_folder / f"{new_area_id}-ROUTES-{mode}.parquet"
        routes_out.write_bytes(to_geoparquet(new_routes_fc))
        log("Nieuwe ROUTES opgeslagen")

        # ── 6. Metadata ──────────────────────────────────────────────────────
        (output_folder / ".src-area-id").write_text(area_id, encoding="utf-8")
        if scenario_name:
            (output_folder / ".area-name").write_text(scenario_name, encoding="utf-8")

        # ── 7. Reguliere adjust-pipeline voor resterende wijzigingen ─────────
        remaining_changes_path = output_folder / f"{new_area_id}-changes.json"
        remaining_changes = json.loads(
            remaining_changes_path.read_text(encoding="utf-8")
        )
        if remaining_changes:
            log(
                f"Reguliere adjust-pipeline starten ({len(remaining_changes)} wijzigingen)…"
            )
            _adjust_run_pipeline(
                folder=str(output_folder),
                changes=str(remaining_changes_path),
                output_folder=str(output_folder),
                routes_path=str(routes_out),
                new_area_id=new_area_id,
                min_link_trips=1.0,
                debug=bool(job_kwargs.get("debug", False)),
            )
            log("Adjust-pipeline klaar")
        else:
            log("Geen aanvullende wijzigingen — adjust-pipeline overgeslagen")

        # ── 8. Post-processing MIXED ─────────────────────────────────────────
        if all_constituent:
            log("Post-processing MIXED…")
            _post_process_mixed_output(output_folder, new_area_id, all_constituent)

        _areas_cache_invalidate()

        result_mode = "MIXED" if all_constituent else mode
        _ins_compare_file = _geojson_path(new_area_id, result_mode, "COMPARE")
        _ins_compare_url = (
            f"/collections/comparison/items?areaId={new_area_id}&mode={result_mode}"
            if _ins_compare_file.exists()
            else None
        )

        with _jobs_lock:
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {
                "new_area_id": new_area_id,
                "inserted_links": n_new,
                "split_links": n_split,
                "compare_url": _ins_compare_url,
            }
        _sse_notify(area_id, new_area_id, _ins_compare_url, result_mode)
        log(f"Klaar — nieuw gebied: {new_area_id}")

    except Exception as exc:
        import traceback as _tb

        log(f"Fout: {type(exc).__name__}: {exc}\n{_tb.format_exc()}")
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["finished"] = _now_iso()


def _execute_whatif_road_closure(inputs: dict):
    """Start what-if wegafsluiting als async job. Geeft (body, 201, headers) terug."""
    if not _WHATIF_AVAILABLE:
        abort(503, "what_if_quick_scan-package niet beschikbaar")

    area_id = str(inputs.get("area_id", "")).strip()
    mode = str(inputs.get("mode", "CAR")).upper()
    selected_links = inputs.get("selected_links", [])
    direction = str(inputs.get("direction", "both")).lower()
    scenario_name = str(inputs.get("scenario_name", "")).strip() or None
    nroutes = int(inputs.get("nroutes", 5))
    motive = str(inputs.get("motive", "totaal")).lower()
    period = str(inputs.get("period", "etmaal")).lower()
    measure = str(inputs.get("measure", "closure")).lower()
    reduction_factor = float(inputs.get("reduction_factor", 0.5))

    if not area_id:
        abort(400, 'Parameter "area_id" ontbreekt')
    if not isinstance(selected_links, list) or not selected_links:
        abort(400, 'Parameter "selected_links" moet een niet-lege array zijn')
    if direction not in ("both", "same", "opposite"):
        abort(400, 'Parameter "direction" moet "both", "same" of "opposite" zijn')
    if motive not in _WI_MOTIVES:
        abort(400, f"Ongeldig motief. Toegestaan: {', '.join(_WI_MOTIVES)}")
    if period not in _WI_PERIODS:
        abort(400, f"Ongeldig tijdvak. Toegestaan: {', '.join(_WI_PERIODS)}")

    try:
        selected_links = [int(lid) for lid in selected_links]
    except (ValueError, TypeError):
        abort(400, "selected_links moet een array van integers zijn")

    src_dir = _find_area_dir(area_id)
    path_geojson = src_dir / f"{area_id}-NETWORK-{mode}.geojson"
    path_csv = src_dir / f"{area_id}-NVP-ROUTES-{mode}.csv"

    if not path_geojson.exists():
        abort(404, f"Netwerkbestand niet gevonden: {path_geojson.name}")
    if not path_csv.exists():
        abort(
            404,
            f"NVP-routes bestand ontbreekt ({path_csv.name}). "
            f"Bereid het gebied opnieuw voor met de nvp_mapper stap (nvp_table + nvp_year).",
        )

    new_area_id = str(uuid.uuid4())
    if scenario_name:
        folder_name = re.sub(r"[^\w\-]", "_", scenario_name.strip())
        folder_name = re.sub(r"_+", "_", folder_name).strip("_") or new_area_id
    else:
        folder_name = new_area_id
    output_folder = _work_dir() / folder_name
    output_folder.mkdir(parents=True, exist_ok=True)
    (output_folder / ".area-uuid").write_text(new_area_id, encoding="utf-8")
    if scenario_name:
        (output_folder / ".area-name").write_text(scenario_name, encoding="utf-8")

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "jobID": job_id,
            "processID": "whatif-road-closure",
            "status": "accepted",
            "log": [],
            "returncode": None,
            "out_dir": str(output_folder),
            "created": _now_iso(),
            "started": None,
            "finished": None,
            "_results": {},
        }

    threading.Thread(
        target=_run_whatif_road_closure_job,
        args=(
            job_id,
            str(path_geojson),
            str(path_csv),
            output_folder,
            new_area_id,
            area_id,
            mode,
            selected_links,
            direction,
            motive,
            period,
            nroutes,
            measure,
            reduction_factor,
            scenario_name,
        ),
        daemon=True,
    ).start()
    return {"jobID": job_id, "status": "accepted"}, 201, {"Location": f"/jobs/{job_id}"}


def _execute_wegenscan(inputs: dict):
    """Start wegenscan als async job. Geeft (body, 201, headers) terug."""
    if not _WEGENSCAN_AVAILABLE:
        abort(503, "wegenscan-package niet beschikbaar")

    area_id = str(inputs.get("area_id", "")).strip()
    mode = str(inputs.get("mode", "CAR")).strip().upper()

    if not _safe(area_id):
        abort(400, f"Ongeldige of ontbrekende area_id: {area_id!r}")
    valid_modes = {"CAR", "BIKE", "PEDESTRIAN", "MIXED"}
    if mode not in valid_modes:
        abort(
            400,
            f"Ongeldige modus: {mode!r}. Toegestaan: {', '.join(sorted(valid_modes))}",
        )

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "jobID": job_id,
            "processID": "wegenscan",
            "status": "accepted",
            "log": [],
            "created": _now_iso(),
            "started": None,
            "finished": None,
        }
    threading.Thread(
        target=_run_wegenscan_job,
        args=(job_id, area_id, mode),
        daemon=True,
    ).start()
    return {"jobID": job_id, "status": "accepted"}, 201, {"Location": f"/jobs/{job_id}"}


def _execute_delete_area(inputs: dict):
    """Verwijder gebied én al zijn sub-scenario's (de hele boom). Synchroon.

    Bij het verwijderen van een scenario worden alle afgeleide scenario's
    (kinderen, kleinkinderen, …) meeverwijderd zodat er geen verweesde
    sub-scenario's achterblijven.  Geeft (body, 200, {}) terug.
    """
    area_id = str(inputs.get("id", "")).strip()
    if not _safe(area_id):
        abort(400, f"Ongeldige of ontbrekende area_id: {area_id!r}")
    area_dir = _find_area_dir(area_id)
    if not area_dir.is_dir():
        abort(404, f"Geen map gevonden voor gebied: {area_id}")

    # Verzamel de volledige subboom (nakomelingen) vóór verwijdering; het te
    # verwijderen gebied zelf als laatste, zodat afgeleide scenario's altijd eerst
    # opgeruimd worden.
    descendants = _collect_descendant_area_ids(area_id)
    to_delete = descendants + [area_id]

    deleted: list = []
    errors: list = []
    for aid in to_delete:
        if not _safe(aid):
            errors.append({"id": aid, "error": "onveilige area_id"})
            continue
        try:
            d = _find_area_dir(aid)
            if d.is_dir():
                shutil.rmtree(str(d))
            deleted.append(aid)
        except Exception as exc:
            errors.append({"id": aid, "error": str(exc)})
        if _s3_enabled():
            try:
                _s3_delete_prefix(_s3_area_prefix(aid))
            except Exception as _e:
                print(f"[s3] delete-area S3 mislukt voor {aid}: {_e}")

    _areas_cache_invalidate()

    if errors and area_id not in deleted:
        # Het hoofdgebied kon niet verwijderd worden → als fout rapporteren.
        abort(500, "; ".join(f"{e['id']}: {e['error']}" for e in errors))

    return {"deleted": area_id, "deletedTree": deleted, "errors": errors}, 200, {}


def _execute_set_directory(inputs: dict):
    """Stel data-map in synchroon. Geeft (body, 200, {}) terug."""
    global DATA_DIR
    raw = str(inputs.get("path", "")).strip()
    if not raw:
        abort(400, 'Parameter "path" ontbreekt')
    p = Path(raw).resolve()
    if p.is_file():
        p = p.parent
    if not p.is_dir():
        abort(404, f"Map niet gevonden: {p}")
    DATA_DIR = p
    return {"dir": str(DATA_DIR), "areas": _discover_areas()}, 200, {}


# ---------------------------------------------------------------------------
# GMT upload — job runner en execute-functie
# ---------------------------------------------------------------------------


def _run_upload_to_gmt_job(
    job_id: str,
    area_id: str,
    mode: str,
    area_dir: Path,
    max_flow: "float | None" = None,
):
    """Upload het netwerk-parquet als GeoJSON naar mobilitytwin (achtergrondthread)."""

    def log(msg: str):
        with _jobs_lock:
            _jobs[job_id]["log"].append(msg)
        print(f"[upload-to-gmt] {msg}")

    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = _now_iso()

    try:
        # 1. Zoek het netwerk-bestand (parquet of geojson)
        net_path = _data_path(area_id, mode, "NETWORK")
        if net_path is None or not net_path.exists():
            raise FileNotFoundError(
                f"Geen NETWORK-bestand gevonden voor {area_id}/{mode}"
            )
        log(f"Netwerk-bestand gevonden: {net_path.name}")

        # 2. Lees parquet → GeoJSON dict (gebruikt bestaande _read_geodata)
        log("Parquet omzetten naar GeoJSON…")
        geojson_data = _read_geodata(net_path)

        # Optioneel: filter features boven max_flow
        if max_flow is not None:
            features_before = len(geojson_data.get("features", []))
            geojson_data["features"] = [
                f
                for f in geojson_data.get("features", [])
                if float(f.get("properties", {}).get("flow24hrs") or 0) <= max_flow
            ]
            features_after = len(geojson_data["features"])
            log(
                f"Filter toegepast (≤ {max_flow} pae/dag): "
                f"{features_before - features_after} features verwijderd, "
                f"{features_after} resterend"
            )

        geojson_str = json.dumps(geojson_data, ensure_ascii=False)
        log(f"GeoJSON gegenereerd ({len(geojson_str) // 1024} KB)")

        # Voeg OSM/ODbL-attributie toe als foreign members op de FeatureCollection
        # (RFC 7946 staat aanvullende leden toe). Zo blijft de bronvermelding bij
        # de data zelf, ook los van de GMT-inputs-metadata hieronder.
        if isinstance(geojson_data, dict):
            geojson_data.setdefault("attribution", _OSM_ATTRIBUTION_TEXT)
            geojson_data.setdefault("license", _OSM_LICENSE)
            geojson_data.setdefault("licenseUrl", _OSM_LICENSE_URL)

        # 3. Authenticeer bij GMT
        log("Authenticeren bij GMT…")
        if not _GMT_USERNAME or not _GMT_PASSWORD:
            raise ValueError("GMT_USERNAME of GMT_PASSWORD niet ingesteld in .env")
        auth_resp = requests.post(
            f"{_GMT_BASE_URL}/authenticate",
            json={"username": _GMT_USERNAME, "password": _GMT_PASSWORD},
            timeout=30,
        )
        if not auth_resp.ok:
            raise RuntimeError(
                f"Authenticatie mislukt: HTTP {auth_resp.status_code} — {auth_resp.text[:200]}"
            )
        token = auth_resp.json().get("token", "")
        if not token:
            raise RuntimeError("Authenticatie mislukt: geen token in response")
        log("Authenticatie geslaagd")

        # 4. Upload naar GMT
        log("Uploaden naar GMT…")
        upload_body = {
            "inputs": {
                "mode": mode,
                "type": "network",
                "areaId": area_id,
                "geojson": geojson_data,
                "attribution": _OSM_ATTRIBUTION_TEXT,
                "license": _OSM_LICENSE,
                "licenseUrl": _OSM_LICENSE_URL,
            }
        }
        upload_resp = requests.post(
            f"{_GMT_BASE_URL}/processes/upload-geojson/execution",
            json=upload_body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        if not upload_resp.ok:
            raise RuntimeError(
                f"Upload mislukt: HTTP {upload_resp.status_code} — {upload_resp.text[:200]}"
            )
        log(f"Upload geslaagd (HTTP {upload_resp.status_code})")

        # 5. Schrijf marker-bestand zodat de status onthouden wordt
        marker = area_dir / f".gmt-uploaded-{mode}"
        marker.write_text(_now_iso(), encoding="utf-8")
        _areas_cache_invalidate()
        log("Status opgeslagen")

        with _jobs_lock:
            _jobs[job_id]["status"] = "successful"
            _jobs[job_id]["finished"] = _now_iso()
            _jobs[job_id]["_results"] = {"areaId": area_id, "mode": mode}

    except Exception as exc:
        log(f"Fout: {type(exc).__name__}: {exc}")
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["finished"] = _now_iso()


def _execute_upload_to_gmt(inputs: dict):
    """Start een asynchrone GMT-upload job. Geeft (body, 201, headers) terug."""
    area_id = str(inputs.get("areaId", "")).strip()
    mode = str(inputs.get("mode", "")).strip().upper()
    if not area_id or not _safe(area_id):
        abort(400, f"Ongeldige of ontbrekende areaId: {area_id!r}")
    if not mode:
        abort(400, "Parameter 'mode' ontbreekt")

    # Optionele max-flow drempel
    max_flow_raw = inputs.get("maxFlow")
    max_flow: "float | None" = None
    if max_flow_raw is not None and str(max_flow_raw).strip() != "":
        try:
            max_flow = float(max_flow_raw)
        except (TypeError, ValueError):
            abort(400, f"Ongeldige maxFlow waarde: {max_flow_raw!r}")

    area_dir = _find_area_dir(area_id)
    if not area_dir.is_dir():
        abort(404, f"Geen map gevonden voor gebied: {area_id}")

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "jobID": job_id,
            "processID": "upload-to-gmt",
            "status": "accepted",
            "log": [],
            "created": _now_iso(),
            "started": None,
            "finished": None,
        }
    threading.Thread(
        target=_run_upload_to_gmt_job,
        args=(job_id, area_id, mode, area_dir),
        kwargs={"max_flow": max_flow},
        daemon=True,
    ).start()
    return (
        {"jobID": job_id, "status": "accepted"},
        201,
        {"Location": f"/jobs/{job_id}"},
    )


# ---------------------------------------------------------------------------
# Area-specifieke hulp-endpoints
# ---------------------------------------------------------------------------


@app.route("/api/areas/<area_id>/max-flow")
def api_area_max_flow(area_id: str):
    """Geeft de maximale flow24hrs-waarde terug voor het netwerk van een gebied."""
    mode = request.args.get("mode", "CAR").strip().upper()
    if not _safe(area_id):
        abort(400, f"Ongeldige areaId: {area_id!r}")
    net_path = _data_path(area_id, mode, "NETWORK")
    if net_path is None or not net_path.exists():
        abort(404, f"Geen NETWORK-bestand gevonden voor {area_id}/{mode}")
    try:
        geojson_data = _read_geodata(net_path)
    except Exception as exc:
        abort(500, f"Fout bij lezen netwerk: {exc}")
    max_flow = 0.0
    for feat in geojson_data.get("features", []):
        val = feat.get("properties", {}).get("flow24hrs")
        if val is not None:
            try:
                max_flow = max(max_flow, float(val))
            except (TypeError, ValueError):
                pass
    return jsonify({"maxFlow": max_flow})


# ---------------------------------------------------------------------------
# OGC API Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    fmt = request.args.get("f", "html").lower()
    if fmt == "json":
        return jsonify(
            {
                "title": "Verkeersnetwerk-visualisatie",
                "description": "OGC API Features + Processes — verkeersnetwerk visualisatie en scenarioanalyse.",
                "links": [
                    {
                        "href": "/?f=json",
                        "rel": "self",
                        "type": "application/json",
                        "title": "Landing page",
                    },
                    {
                        "href": "/conformance",
                        "rel": "conformance",
                        "type": "application/json",
                        "title": "OGC conformantieklassen",
                    },
                    {
                        "href": "/collections",
                        "rel": "data",
                        "type": "application/json",
                        "title": "Collecties",
                    },
                    {
                        "href": "/processes",
                        "rel": "processes",
                        "type": "application/json",
                        "title": "Processen",
                    },
                    {
                        "href": "/jobs",
                        "rel": "monitor",
                        "type": "application/json",
                        "title": "Actieve jobs",
                    },
                ],
            }
        )
    return send_from_directory(str(STATIC_DIR), "index.html")


_STATIC_EXTS = {
    ".html",
    ".js",
    ".css",
    ".json",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


@app.route("/<path:filename>")
def static_asset(filename):
    """Serveer statische bestanden uit de scriptmap (index.html, js, css, …).

    Alleen bestanden met een bekende statische extensie worden served, zodat
    OGC API-paden zoals /conformance en /collections niet worden onderschept.
    """
    ext = Path(filename).suffix.lower()
    if ext not in _STATIC_EXTS:
        abort(404)
    p = STATIC_DIR / filename
    if p.is_file():
        return send_from_directory(str(STATIC_DIR), filename)
    # Niet in de eigen scriptmap: val terug op common/js (bv. left-menu-panel.js),
    # dat index.html via een kale bestandsnaam ("<script src=...>") opvraagt.
    p = COMMON_JS_DIR / filename
    if p.is_file():
        return send_from_directory(str(COMMON_JS_DIR), filename)
    abort(404)


@app.route("/svg/<path:filename>")
def svg_asset(filename):
    """Serveer statische SVG-iconen (o.a. de laneMarkArrow-pijlen) uit svg/."""
    return send_from_directory(str(STATIC_DIR / "svg"), filename)


@app.route("/conformance")
def ogc_conformance():
    return jsonify(
        {
            "conformsTo": [
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
                "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
                "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core",
                "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json",
                "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/job-management",
            ]
        }
    )


@app.route("/collections")
def ogc_collections():
    colls = []
    for cid, info in _COLLECTIONS.items():
        colls.append(
            {
                "id": cid,
                "title": info["title"],
                "description": info["description"],
                "links": [
                    {
                        "href": f"/collections/{cid}",
                        "rel": "self",
                        "type": "application/json",
                        "title": info["title"],
                    },
                    {
                        "href": f"/collections/{cid}/items",
                        "rel": "items",
                        "type": "application/geo+json",
                        "title": f"{info['title']} — items",
                    },
                ],
            }
        )
    return jsonify(
        {
            "collections": colls,
            "links": [
                {
                    "href": "/collections",
                    "rel": "self",
                    "type": "application/json",
                    "title": "Collecties",
                },
            ],
        }
    )


@app.route("/collections/<collection_id>")
def ogc_collection(collection_id):
    info = _COLLECTIONS.get(collection_id)
    if info is None:
        abort(404, f"Collectie niet gevonden: {collection_id}")
    return jsonify(
        {
            "id": collection_id,
            "title": info["title"],
            "description": info["description"],
            "links": [
                {
                    "href": f"/collections/{collection_id}",
                    "rel": "self",
                    "type": "application/json",
                    "title": info["title"],
                },
                {
                    "href": f"/collections/{collection_id}/items",
                    "rel": "items",
                    "type": "application/geo+json",
                    "title": f"{info['title']} — items",
                },
            ],
        }
    )


@app.route("/collections/<collection_id>/items/<feature_id>")
def ogc_collection_feature(collection_id, feature_id):
    abort(501, "Ophalen van individuele features wordt niet ondersteund.")


@app.route("/collections/<collection_id>/items")
def ogc_collection_items(collection_id):
    info = _COLLECTIONS.get(collection_id)
    if info is None:
        abort(404, f"Collectie niet gevonden: {collection_id}")

    self_url = request.url

    # ── areas: geen bestandsparameters vereist ────────────────────────────
    if collection_id == "areas":
        areas = _discover_areas()
        features = [
            {
                "type": "Feature",
                "id": a["areaId"],
                "geometry": _bbox_to_polygon(a.get("bbox")),
                "properties": a,
            }
            for a in areas
        ]
        return _ogc_items_response(
            "areas", {"type": "FeatureCollection", "features": features}, self_url
        )

    # ── changes: gecumuleerde wijzigingen over de scenario-keten ─────────────
    if collection_id == "changes":
        area_id = request.args.get("areaId", "").strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, "Ongeldige parameter: areaId")

        features, visited, current_id, depth = [], set(), area_id, 0
        while current_id and depth < 20 and current_id not in visited:
            visited.add(current_id)
            area_dir = _find_area_dir(current_id)

            # Scenario-naam ophalen uit eerste gevonden NETWORK-bestand
            name = current_id
            _nf_list = list(area_dir.glob(f"{current_id}-NETWORK-*.geojson"))
            if not _nf_list and _GEOPANDAS_AVAILABLE:
                for _ext in _GEOPARQUET_EXTS:
                    _nf_list = list(area_dir.glob(f"{current_id}-NETWORK-*{_ext}"))
                    if _nf_list:
                        break
            if _nf_list:
                try:
                    props = _read_geodata(_nf_list[0]).get("properties", {})
                    name = props.get("name", current_id)
                except Exception:
                    pass

            # Delta-wijzigingen lezen
            cp = area_dir / f"{current_id}-changes.json"
            if cp.exists():
                try:
                    for i, c in enumerate(json.loads(cp.read_text(encoding="utf-8"))):
                        features.append(
                            {
                                "type": "Feature",
                                "id": f"{current_id}|{i}",
                                "geometry": None,
                                "properties": {
                                    "areaId": current_id,
                                    "scenarioName": name,
                                    **c,
                                },
                            }
                        )
                except Exception:
                    pass

            # Keten omhoog via .src-area-id
            parent_id = None
            src_path = area_dir / ".src-area-id"
            if src_path.exists():
                try:
                    parent_id = src_path.read_text(encoding="utf-8").strip() or None
                except Exception:
                    pass
            # Fallback: baseAreaId in bestandseigenschappen (GeoJSON of GeoParquet)
            if not parent_id:
                _nf_list2 = list(area_dir.glob(f"{current_id}-NETWORK-*.geojson"))
                if not _nf_list2 and _GEOPANDAS_AVAILABLE:
                    for _ext in _GEOPARQUET_EXTS:
                        _nf_list2 = list(area_dir.glob(f"{current_id}-NETWORK-*{_ext}"))
                        if _nf_list2:
                            break
                if _nf_list2:
                    try:
                        props = _read_geodata(_nf_list2[0]).get("properties", {})
                        parent_id = props.get("baseAreaId") or None
                    except Exception:
                        pass

            current_id = parent_id
            depth += 1

        # Oudste scenario eerst (keten staat nu in omgekeerde volgorde)
        features.reverse()
        fc = {"type": "FeatureCollection", "features": features}
        return _ogc_items_response("changes", fc, self_url)

    # ── flows: flow-scaler berekening ─────────────────────────────────────
    if collection_id == "flows":
        if not _FLOW_SCALER_AVAILABLE:
            abort(503, "flow_scaler-package niet beschikbaar")

        area_id = request.args.get("areaId", "").strip()
        mode = request.args.get("mode", "CAR").upper().strip()

        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, "Ongeldige parameter: areaId")

        network_path = _data_path(area_id, mode, "NETWORK")
        if network_path is None or not network_path.exists():
            abort(404, f"Netwerkbestand niet gevonden: {area_id}-NETWORK-{mode}")

        purpose_index_path = _find_local_file("purpose_index.json")
        if purpose_index_path is None:
            abort(503, "purpose_index.json niet gevonden")
        # Statisch bestand (~5.7MB / ~49k entries): parse + load_purpose_index()
        # (~130ms) hoeft niet bij elke aanvraag herhaald te worden.
        purpose_index = _json_file_cache_get(purpose_index_path)
        if purpose_index is None:
            with open(purpose_index_path, encoding="utf-8") as fh:
                purpose_index_raw = json.load(fh)
            purpose_index = load_purpose_index(purpose_index_raw)
            _json_file_cache_set(purpose_index_path, purpose_index)

        daylight_raw = []
        daylight_path = _find_local_file("daylight.json")
        if daylight_path is not None:
            daylight_raw = _json_file_cache_get(daylight_path)
            if daylight_raw is None:
                try:
                    with open(daylight_path, encoding="utf-8") as fh:
                        daylight_raw = json.load(fh)
                    _json_file_cache_set(daylight_path, daylight_raw)
                except Exception as exc:
                    daylight_raw = []
                    print(
                        f"[server] daylight.json laden mislukt, wordt overgeslagen: {exc}"
                    )

        date_str = request.args.get("date") or None
        raw_temp = request.args.get("temperature", "Medium")
        raw_weather = request.args.get("weather", "cloudy")
        raw_purpose = request.args.get("purpose") or None
        regio = request.args.get("regio", "midden").lower()

        dt = parse_date(date_str)
        temperature = normalise_temperature(raw_temp)
        weather = normalise_weather(raw_weather, dt, daylight_raw)
        purpose = None if raw_purpose in (None, "all", "") else raw_purpose.lower()

        holiday_path = _find_local_file("holiday_indices.csv")
        holiday_index = str(holiday_path) if holiday_path is not None else ""

        # Resultaat is volledig deterministisch voor deze parametercombinatie
        # zolang het netwerkbestand en purpose_index.json niet wijzigen. De
        # sim-klok in de client herhaalt dezelfde combinatie typisch ~60s lang,
        # dus een LRU-cache voorkomt dat filterNetwork/resolve_indexes_by_mode/
        # applyIndices (deepcopy + scaling van alle features) telkens opnieuw
        # draaien. dt.date()+dt.hour volstaat: de index wordt alleen op dagtype
        # en uur gezocht, niet op minuut/seconde.
        network_mtime_ms = int(network_path.stat().st_mtime * 1000)
        purpose_index_mtime_ms = int(purpose_index_path.stat().st_mtime * 1000)
        cache_key = (
            area_id,
            mode,
            str(network_path),
            network_mtime_ms,
            str(purpose_index_path),
            purpose_index_mtime_ms,
            regio,
            purpose,
            temperature,
            weather,
            dt.date().isoformat() if dt is not None else None,
            dt.hour if dt is not None else None,
        )
        result = _flows_result_cache_get(cache_key)
        if result is None:
            params = FlowScalerParams(
                mode=mode,
                dt=dt,
                temperature=temperature,
                weather=weather,
                regio=regio,
                purpose=purpose,
                holiday_index=holiday_index,
            )

            try:
                network_fc = _read_geodata(network_path)
            except ImportError as exc:
                abort(503, str(exc))

            n_features = len(network_fc.get("features", []))
            filtered = filterNetwork(
                network_fc, bbox=None, offset=0, limit=max(n_features, 1)
            )
            filtered.params = params

            indexes_by_mode = resolve_indexes_by_mode(params, filtered, purpose_index)
            # run_cleaner=False: behoud o.a. flowTemporalUnit (1 = specifiek uur, 24 = dagtotaal)
            # zodat de client kan onderscheiden of 'flow' een uurwaarde of een dagtotaal is.
            result = applyIndices(filtered, indexes_by_mode, run_cleaner=False)

            # Normaliseer naar plain dict voor OGC-envelope
            if not isinstance(result, dict):
                try:
                    result = dict(result)
                except Exception:
                    result = {"type": "FeatureCollection", "features": []}

            _flows_result_cache_set(cache_key, result)

        return _ogc_items_response("flows", result, self_url)

    # ── buildings: OSM-gebouwen, gecached per gebied ──────────────────────
    if collection_id == "buildings":
        area_id = request.args.get("areaId", "").strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, "Ongeldige parameter: areaId")

        area_dir = _find_area_dir(area_id)
        cache_path = area_dir / f"{area_id}-BUILDINGS.geojson"

        # 0) Autoritatief: geprepareerd BUILDINGS-parquet uit de gmt-library.
        #    Bevat vooraf verrijkte gebouwen (met OSM-tags onder 'tag_'-prefix en
        #    afgeleide velden zoals buildingType/parkingCapacity). Als dit bestaat
        #    winnen we het altijd van de Overpass-cache: geen live query, geen
        #    '-BUILDINGS-tiles'-map. De motief-kleuring gebeurt client-side.
        prep_path = None
        if _GEOPANDAS_AVAILABLE:
            for _ext in _GEOPARQUET_EXTS:
                _pp = area_dir / f"{area_id}-BUILDINGS{_ext}"
                if _pp.exists():
                    prep_path = _pp
                    break
        if prep_path is None and _s3_enabled():
            # S3 read-through: haal parquet op als het daar staat.
            for _ext in _GEOPARQUET_EXTS:
                _key = _s3_key(area_id, f"{area_id}-BUILDINGS{_ext}")
                if _s3_exists(_key):
                    try:
                        _local = area_dir / f"{area_id}-BUILDINGS{_ext}"
                        area_dir.mkdir(parents=True, exist_ok=True)
                        _local.write_bytes(_s3_read_bytes(_key))
                        prep_path = _local
                        break
                    except Exception as _e:
                        print(f"[s3] BUILDINGS-parquet download mislukt ({_key}): {_e}")
        if prep_path is not None:
            try:
                data = _read_geodata(prep_path)
            except Exception as exc:
                abort(500, f"Fout bij lezen BUILDINGS-parquet: {exc}")
            # Properties normaliseren zodat het parquet een drop-in vervanger is
            # voor de Overpass-GeoJSON: strip de 'tag_'-prefix (→ kale OSM-keys
            # die de viewer verwacht: building/amenity/building:levels/…) en laat
            # lege (NaN/None) waarden weg. Afgeleide velden blijven behouden.
            for feat in data.get("features", []):
                props = feat.get("properties") or {}
                newp = {}
                for k, v in props.items():
                    if v is None:
                        continue
                    # NaN-detectie (float('nan') != zichzelf) zonder harde import.
                    if isinstance(v, float) and v != v:
                        continue
                    newp[k[4:] if k.startswith("tag_") else k] = v
                feat["properties"] = newp
            return _ogc_items_response("buildings", data, self_url)

        # 1) Gebruik cache als aanwezig én actueel (versienummer klopt)
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("properties", {}).get("_qv") == _BUILDINGS_QUERY_VER:
                return _ogc_items_response("buildings", data, self_url)
            # Verouderde cache: verwijder en herlaad
            try:
                cache_path.unlink()
            except Exception:
                pass

        # 2) Zoek in ouder-gebieden via baseAreaId-keten
        visited = {area_id}
        cur_id = area_id
        base_tile_cache_dir = (
            None  # tegel-cache van het dichtstbijzijnde basis-scenario
        )
        for _ in range(6):
            try:
                cur_dir = _find_area_dir(cur_id)
                _nw_list = list(cur_dir.glob(f"{cur_id}-NETWORK-*.geojson"))
                if not _nw_list and _GEOPANDAS_AVAILABLE:
                    for _ext in _GEOPARQUET_EXTS:
                        _nw_list = list(cur_dir.glob(f"{cur_id}-NETWORK-*{_ext}"))
                        if _nw_list:
                            break
                if not _nw_list:
                    break
                props = _read_geodata(_nw_list[0]).get("properties", {})
                parent_id = props.get("baseAreaId") or None
            except Exception:
                break
            if not parent_id or parent_id in visited:
                break
            visited.add(parent_id)
            cur_id = parent_id
            parent_dir = _find_area_dir(parent_id)
            parent_cache = parent_dir / f"{parent_id}-BUILDINGS.geojson"
            if parent_cache.exists():
                with open(parent_cache, encoding="utf-8") as fh:
                    data = json.load(fh)
                if data.get("properties", {}).get("_qv") == _BUILDINGS_QUERY_VER:
                    return _ogc_items_response("buildings", data, self_url)
                try:
                    parent_cache.unlink()
                except Exception:
                    pass
            # Bewaar tegel-cache van dit ouder-gebied (eerste treffer wint)
            ptcd = parent_dir / f"{parent_id}-BUILDINGS-tiles"
            if ptcd.exists() and base_tile_cache_dir is None:
                base_tile_cache_dir = ptcd

        # 3) Bepaal bbox en query Overpass
        bbox = None
        try:
            _nw_list2 = list(area_dir.glob(f"{area_id}-NETWORK-*.geojson"))
            if not _nw_list2 and _GEOPANDAS_AVAILABLE:
                for _ext in _GEOPARQUET_EXTS:
                    _nw_list2 = list(area_dir.glob(f"{area_id}-NETWORK-*{_ext}"))
                    if _nw_list2:
                        break
            if _nw_list2:
                ndata = _read_geodata(_nw_list2[0])
                props = ndata.get("properties", {})
                bbox = props.get("bbox")
                if not bbox or len(bbox) < 4:
                    lons, lats = [], []
                    for feat in ndata.get("features", []):
                        for coord in feat.get("geometry", {}).get("coordinates", []):
                            lons.append(coord[0])
                            lats.append(coord[1])
                    if lons:
                        bbox = [min(lons), min(lats), max(lons), max(lats)]
        except Exception as exc:
            abort(500, f"Fout bij lezen netwerk voor bbox: {exc}")

        if not bbox:
            abort(404, "Geen bbox beschikbaar voor gebouwen-query")

        try:
            tile_cache_dir = area_dir / f"{area_id}-BUILDINGS-tiles"
            _overpass_breaker_check("buildings")
            data = _fetch_buildings_overpass(
                bbox,
                tile_cache_dir=tile_cache_dir,
                fallback_tile_cache_dir=base_tile_cache_dir,
            )
            _overpass_breaker_success("buildings")
        except Exception as exc:
            _overpass_breaker_failure("buildings")
            abort(502, f"Overpass-query mislukt: {exc}")

        # Cache opslaan — alleen als alle tegels succesvol waren
        try:
            if not data.get("properties", {}).get("_partial"):
                area_dir.mkdir(parents=True, exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False)
                if _s3_enabled():
                    try:
                        _s3_write_bytes(
                            _s3_key(area_id, cache_path.name),
                            json.dumps(data, ensure_ascii=False).encode("utf-8"),
                            "application/json",
                        )
                    except Exception as _e:
                        print(f"[s3] buildings-cache uploaden mislukt: {_e}")
        except Exception:
            pass

        return _ogc_items_response("buildings", data, self_url)

    # ── traffic_assets: verkeersobjecten uit geprepareerd TRAFFIC-ASSETS bestand ──
    if collection_id == "traffic_assets":
        area_id = request.args.get("areaId", "").strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, "Ongeldige parameter: areaId")

        area_dir = _find_area_dir(area_id)
        # Scenario's erven TRAFFIC-ASSETS van hun basisscenario als ze het zelf
        # niet hebben (wordt bij het aanmaken niet altijd doorgekopieerd).
        path = _find_prepared_with_base_fallback(area_id, "TRAFFIC-ASSETS")
        if path is None:
            abort(404, "Geen TRAFFIC-ASSETS bestand voor dit gebied")

        # Optionele bbox-filtering (OGC API Features): bbox=minLon,minLat,maxLon,maxLat
        bbox = None
        bbox_arg = request.args.get("bbox", "").strip()
        if bbox_arg:
            parts = bbox_arg.split(",")
            if len(parts) != 4:
                abort(400, "Ongeldige bbox: verwacht minLon,minLat,maxLon,maxLat")
            try:
                bbox = [float(p) for p in parts]
            except ValueError:
                abort(400, "Ongeldige bbox: waarden moeten numeriek zijn")

        # Optioneel assetType-filter (komma-gescheiden lijst, b.v. speedBump).
        asset_types = None
        asset_type_arg = request.args.get("assetType", "").strip()
        if asset_type_arg:
            asset_types = {t.strip() for t in asset_type_arg.split(",") if t.strip()}

        # Minimale property-set die de frontend echt gebruikt. Dit scheelt
        # aanzienlijk in payload (veel lege / ongebruikte BGT/OSM-kolommen).
        _TRAFFIC_ASSET_KEEP_PROPS = {
            "assetType",
            "name",
            "traffic_sign",  # bevat soms rvvCode (oudere data)
            "osm_id",
            "rvvCode",
            "blackCode",
            "direction",
            "bearing",  # orientatie voor borden/lantaarns/meubilair
            "width",
            "surface",
            "linkId",
            "nodeId",
            "ref",
            "bench",
            "bus",
            "public_transport",
            "ref:IFOPT",
            "shelter",
            "amenity",
            "shelter_type",
            "man_made",
            "tower:type",
            "description",
            "board_type",
            "information",
            "tourism",
            "operator",
            "collection_times",
            "colour",
            "operator:wikidata",
            "check_date",
            "waste",
            "cycle_barrier",
            "cycle_barrier:installation",
            "wheelchair",
            "emergency",
            "manufacturer",
            "siren:model",
            "siren:purpose",
            "siren:type",
            "support",
            "lamp_mount",
            "lamp_type",
            "opening_hours",
            "parkingId",
            "parkingCapacity",
            "tag_amenity",
            "tag_fee",
            "tag_name",
            "tag_parking",
            "tag_access",
            "tag_capacity",
            "tag_park_ride",
            "tag_source",
            "tag_supervised",
            "tag_surface",
            "tag_wheelchair",
            "tag_lit",
            "tag_opening_hours",
            "tag_smoothness",
            "tag_operator",
            "tag_orientation",
            "tag_parking:right",
            "belowGround",
            "heightM",
        }

        try:
            data = _read_geodata(path)
        except Exception as exc:
            abort(500, f"Fout bij lezen TRAFFIC-ASSETS: {exc}")

        feats = data.get("features", [])

        def _slim_traffic_props(props: dict) -> dict:
            if not isinstance(props, dict):
                return {}
            out = {}
            for k, v in props.items():
                if k not in _TRAFFIC_ASSET_KEEP_PROPS:
                    continue
                # Sla lege waarden over, behalve assetType (altijd nodig).
                if k != "assetType":
                    if v is None:
                        continue
                    if isinstance(v, float) and v != v:
                        continue
                    if v == "":
                        continue
                out[k] = v
            return out

        if asset_types is not None:
            feats = [
                f
                for f in feats
                if (f.get("properties") or {}).get("assetType") in asset_types
            ]

        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            filtered = []
            for feat in feats:
                geom = feat.get("geometry") or {}
                coords = geom.get("coordinates")
                # Neem het eerste vertex als representatief punt; werkt voor
                # Point/LineString/Polygon/Multi* (speedBump = Polygon).
                pt = coords
                while isinstance(pt, list) and pt and isinstance(pt[0], list):
                    pt = pt[0]
                if not pt or len(pt) < 2:
                    continue
                lon, lat = pt[0], pt[1]
                if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                    filtered.append(feat)
            feats = filtered

        # Strip ongebruikte/lege properties en laat geometry intact.
        slim_feats = []
        for feat in feats:
            slim_feats.append(
                {
                    "type": "Feature",
                    "properties": _slim_traffic_props(feat.get("properties")),
                    "geometry": feat.get("geometry"),
                }
            )
        data = {"type": "FeatureCollection", "features": slim_feats}

        as_nd = request.args.get("f", "").strip().lower() == "ndgeojson"
        return _ogc_items_response("traffic_assets", data, self_url, as_ndgeojson=as_nd)

    # ── heights: hoogte-/constructie-objecten uit geprepareerd HEIGHTS bestand ──
    if collection_id == "heights":
        area_id = request.args.get("areaId", "").strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, "Ongeldige parameter: areaId")

        area_dir = _find_area_dir(area_id)
        # Scenario's erven HEIGHTS van hun basisscenario als ze het zelf niet hebben.
        path = _find_prepared_with_base_fallback(area_id, "HEIGHTS")
        if path is None:
            abort(404, "Geen HEIGHTS bestand voor dit gebied")

        # Optionele bbox-filtering (OGC API Features): bbox=minLon,minLat,maxLon,maxLat
        bbox = None
        bbox_arg = request.args.get("bbox", "").strip()
        if bbox_arg:
            parts = bbox_arg.split(",")
            if len(parts) != 4:
                abort(400, "Ongeldige bbox: verwacht minLon,minLat,maxLon,maxLat")
            try:
                bbox = [float(p) for p in parts]
            except ValueError:
                abort(400, "Ongeldige bbox: waarden moeten numeriek zijn")

        try:
            data = _read_geodata(path)
        except Exception as exc:
            abort(500, f"Fout bij lezen HEIGHTS: {exc}")

        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            feats = []
            for feat in data.get("features", []):
                geom = feat.get("geometry") or {}
                coords = geom.get("coordinates")
                # Neem het eerste vertex als representatief punt; werkt voor
                # Point/LineString/Polygon/Multi*.
                pt = coords
                while isinstance(pt, list) and pt and isinstance(pt[0], list):
                    pt = pt[0]
                if not pt or len(pt) < 2:
                    continue
                lon, lat = pt[0], pt[1]
                if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                    feats.append(feat)
            data = {**data, "features": feats}

        return _ogc_items_response("heights", data, self_url)

    # ── vegetation: bomen/struiken/bos uit geprepareerd VEGETATION bestand ──
    if collection_id == "vegetation":
        area_id = request.args.get("areaId", "").strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, "Ongeldige parameter: areaId")

        area_dir = _find_area_dir(area_id)

        # Optionele bbox-filtering (OGC API Features): bbox=minLon,minLat,maxLon,maxLat
        bbox = None
        bbox_arg = request.args.get("bbox", "").strip()
        if bbox_arg:
            parts = bbox_arg.split(",")
            if len(parts) != 4:
                abort(400, "Ongeldige bbox: verwacht minLon,minLat,maxLon,maxLat")
            try:
                bbox = [float(p) for p in parts]
            except ValueError:
                abort(400, "Ongeldige bbox: waarden moeten numeriek zijn")

        # Alleen een vooraf geprepareerd VEGETATION-bestand wordt uitgeleverd.
        # Als dit ontbreekt, retourneert het endpoint 404. De frontend gebruikt
        # deze 404 om te stoppen met onnodige retry's.
        prep_path = _find_prepared_with_base_fallback(area_id, "VEGETATION")
        if prep_path is None:
            abort(404, "Geen VEGETATION bestand voor dit gebied")

        try:
            data = _read_geodata(prep_path)
        except Exception as exc:
            abort(500, f"Fout bij lezen VEGETATION: {exc}")

        # bbox-filter op de response. Voor vlakken (Polygon/MultiPolygon) en
        # lijnen mag NIET op één representatief punt gefiltert worden: een groot
        # bosvlak waarvan het eerste hoekpunt buiten beeld valt zou dan volledig
        # verdwijnen (flikkeren bij pannen). We testen daarom of de geometrie-
        # bounding-box de query-bbox overlapt.
        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox

            def _geom_bbox(coords):
                lo_x = lo_y = float("inf")
                hi_x = hi_y = float("-inf")
                stack = [coords]
                while stack:
                    cur = stack.pop()
                    if not isinstance(cur, list) or not cur:
                        continue
                    if isinstance(cur[0], (int, float)) and len(cur) >= 2:
                        x, y = cur[0], cur[1]
                        if x < lo_x:
                            lo_x = x
                        if x > hi_x:
                            hi_x = x
                        if y < lo_y:
                            lo_y = y
                        if y > hi_y:
                            hi_y = y
                    else:
                        stack.extend(cur)
                if lo_x == float("inf"):
                    return None
                return lo_x, lo_y, hi_x, hi_y

            feats = []
            for feat in data.get("features", []):
                geom = feat.get("geometry") or {}
                gb = _geom_bbox(geom.get("coordinates"))
                if gb is None:
                    continue
                g_min_lon, g_min_lat, g_max_lon, g_max_lat = gb
                # Rechthoek-overlap (geen disjunctie).
                if (
                    g_min_lon <= max_lon
                    and g_max_lon >= min_lon
                    and g_min_lat <= max_lat
                    and g_max_lat >= min_lat
                ):
                    feats.append(feat)
            data = {**data, "features": feats}

        return _ogc_items_response("vegetation", data, self_url)

    # ── traffic_signs: verkeersborden, gecached per gebied ────────────────
    if collection_id == "traffic_signs":
        area_id = request.args.get("areaId", "").strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, "Ongeldige parameter: areaId")

        area_dir = _find_area_dir(area_id)
        cache_path = area_dir / f"{area_id}-TRAFFIC-SIGNS.geojson"

        # 1) Gebruik aggregate cache als aanwezig én actueel
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("properties", {}).get("_qv") == _TRAFFIC_SIGNS_QUERY_VER:
                return _ogc_items_response("traffic_signs", data, self_url)
            # Verouderde cache: verwijder en herlaad
            try:
                cache_path.unlink()
            except Exception:
                pass

        # 2) Bepaal bbox uit NETWORK-bestand
        bbox = None
        try:
            _nw_list = list(area_dir.glob(f"{area_id}-NETWORK-*.geojson"))
            if not _nw_list and _GEOPANDAS_AVAILABLE:
                for _ext in _GEOPARQUET_EXTS:
                    _nw_list = list(area_dir.glob(f"{area_id}-NETWORK-*{_ext}"))
                    if _nw_list:
                        break
            if _nw_list:
                ndata = _read_geodata(_nw_list[0])
                props = ndata.get("properties", {})
                bbox = props.get("bbox")
                if not bbox or len(bbox) < 4:
                    lons, lats = [], []
                    for feat in ndata.get("features", []):
                        for coord in feat.get("geometry", {}).get("coordinates", []):
                            lons.append(coord[0])
                            lats.append(coord[1])
                    if lons:
                        bbox = [min(lons), min(lats), max(lons), max(lats)]
        except Exception as exc:
            abort(500, f"Fout bij lezen netwerk voor bbox: {exc}")

        if not bbox:
            abort(404, "Geen bbox beschikbaar voor verkeersborden-query")

        # 3) NDW (NL) of Overpass (buitenland)
        if _is_netherlands(bbox):
            # Wacht tot de NDW-achtergronddownload klaar is (blokkeert request)
            _ndw_ready.wait()
            if _ndw_error:
                abort(502, f"NDW-dataset niet beschikbaar: {_ndw_error}")
            ndw_path = DATA_DIR / "ndw_traffic_signs.json"
            if not ndw_path.exists():
                abort(503, "NDW-dataset nog niet beschikbaar, probeer later opnieuw")
            try:
                data = _fetch_traffic_signs_ndw(ndw_path, bbox)
            except Exception as exc:
                abort(500, f"Fout bij lezen NDW-dataset: {exc}")
        else:
            # Zoek fallback tegel-cache in base-scenario (via baseAreaId-keten)
            visited = {area_id}
            cur_id = area_id
            base_tile_cache_dir = None
            for _ in range(6):
                try:
                    cur_dir = _find_area_dir(cur_id)
                    _nw2 = list(cur_dir.glob(f"{cur_id}-NETWORK-*.geojson"))
                    if not _nw2 and _GEOPANDAS_AVAILABLE:
                        for _ext in _GEOPARQUET_EXTS:
                            _nw2 = list(cur_dir.glob(f"{cur_id}-NETWORK-*{_ext}"))
                            if _nw2:
                                break
                    if not _nw2:
                        break
                    p2 = _read_geodata(_nw2[0]).get("properties", {})
                    parent_id = p2.get("baseAreaId") or None
                except Exception:
                    break
                if not parent_id or parent_id in visited:
                    break
                visited.add(parent_id)
                cur_id = parent_id
                parent_dir = _find_area_dir(parent_id)
                ptcd = parent_dir / f"{parent_id}-TRAFFIC-SIGNS-tiles"
                if ptcd.exists() and base_tile_cache_dir is None:
                    base_tile_cache_dir = ptcd

            try:
                tile_cache_dir = area_dir / f"{area_id}-TRAFFIC-SIGNS-tiles"
                _overpass_breaker_check("traffic-signs")
                data = _fetch_traffic_signs_overpass(
                    bbox,
                    tile_cache_dir=tile_cache_dir,
                    fallback_tile_cache_dir=base_tile_cache_dir,
                )
                _overpass_breaker_success("traffic-signs")
            except Exception as exc:
                _overpass_breaker_failure("traffic-signs")
                abort(502, f"Overpass-query mislukt: {exc}")

        # Cache opslaan — alleen als volledig
        try:
            if not data.get("properties", {}).get("_partial"):
                area_dir.mkdir(parents=True, exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False)
                if _s3_enabled():
                    try:
                        _s3_write_bytes(
                            _s3_key(area_id, cache_path.name),
                            json.dumps(data, ensure_ascii=False).encode("utf-8"),
                            "application/json",
                        )
                    except Exception as _e:
                        print(f"[s3] traffic-signs-cache uploaden mislukt: {_e}")
        except Exception:
            pass

        return _ogc_items_response("traffic_signs", data, self_url)

    # ── noise / emission: afgeleide lagen berekend uit het NETWORK-bestand ───
    # Deze endpoints "vervuilen" het network-bestand niet: ze berekenen de
    # geluid- resp. emissie-properties on-the-fly en geven een slanke FC terug
    # (linkId + properties, geometrie optioneel via ?geometry=1). De viewer joint
    # zelf op linkId met de reeds ingeladen netwerkgeometrie.
    if collection_id in ("noise", "emission"):
        kind = "noise" if collection_id == "noise" else "emission"
        available = _NOISE_AVAILABLE if kind == "noise" else _EMISSION_AVAILABLE
        prop_names = _NOISE_PROPS if kind == "noise" else _EMISSION_PROPS

        area_id = request.args.get("areaId", "").strip()
        mode = request.args.get("mode", "").upper().strip()
        if not area_id:
            abort(400, 'Parameter "areaId" ontbreekt')
        if not _safe(area_id):
            abort(400, "Ongeldige parameter: areaId")
        if not mode:
            abort(400, 'Parameter "mode" ontbreekt')
        if not _safe(mode):
            abort(400, "Ongeldige parameter: mode")

        if not available:
            abort(
                503,
                f"Rekenmodule voor '{kind}' niet beschikbaar (gmt_calculation_lib niet geïnstalleerd).",
            )

        path = _data_path(area_id, mode, "NETWORK")
        if path is None or not path.exists():
            abort(404, f"Bestand niet gevonden: {area_id}-NETWORK-{mode}")

        include_geometry = request.args.get("geometry", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "ja",
        )

        mtime = path.stat().st_mtime
        etag = (
            f'"{int(mtime * 1000):x}-{kind}-{_DERIVED_VER}-'
            f'{"g" if include_geometry else "n"}"'
        )
        last_modified = _dt.datetime.fromtimestamp(mtime, tz=_dt.timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        if request.headers.get("If-None-Match") == etag:
            resp = make_response("", 304)
            resp.headers["ETag"] = etag
            resp.headers["Cache-Control"] = "no-cache"
            return resp

        try:
            full_fc = _network_derived_fc(path, kind)
        except ImportError as exc:
            abort(503, str(exc))
        except Exception as exc:
            abort(500, f"Fout bij berekenen van '{kind}': {exc}")

        slim = _slim_derived_fc(full_fc, prop_names, include_geometry)
        resp = _ogc_items_response(collection_id, slim, self_url)
        resp.headers["ETag"] = etag
        resp.headers["Last-Modified"] = last_modified
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # ── overige collections: lees geodata-bestand (GeoJSON of GeoParquet) ────
    area_id = request.args.get("areaId", "").strip()
    mode = request.args.get("mode", "").upper().strip()

    if not area_id:
        abort(400, 'Parameter "areaId" ontbreekt')
    if not _safe(area_id):
        abort(400, "Ongeldige parameter: areaId")
    if not mode:
        abort(400, 'Parameter "mode" ontbreekt')
    if not _safe(mode):
        abort(400, "Ongeldige parameter: mode")

    file_type = _COLLECTION_FILE_TYPE[collection_id]
    path = _data_path(area_id, mode, file_type)

    if path is None or not path.exists():
        abort(404, f"Bestand niet gevonden: {area_id}-{file_type}-{mode}")

    # HTTP-caching: ETag gebaseerd op bestandswijzigingstijd (milliseconde-nauwkeurig).
    mtime = path.stat().st_mtime
    etag = f'"{int(mtime * 1000):x}"'
    last_modified = _dt.datetime.fromtimestamp(mtime, tz=_dt.timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    if request.headers.get("If-None-Match") == etag:
        resp = make_response("", 304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # Server-side cache: sla geconverteerde GeoJSON-data in-memory op.
    # De OGC-envelope (timeStamp, links) wordt er elke keer omheen gelegd (is verwaarloosbaar).
    data = _geodata_cache_get(path)
    if data is None:
        try:
            data = _read_geodata(path)
        except ImportError as exc:
            abort(503, str(exc))
        _geodata_cache_set(path, data)

    # properties.name van het NETWORK-bestand volgt altijd de expliciete
    # scenarionaam uit .area-name (zie _discover_areas_uncached): het brondata-
    # bestand zelf (vaak GeoParquet) wordt bij het aanmaken van een scenario niet
    # altijd met de nieuwe naam gepatcht (_patch_geojson_properties kent alleen
    # .geojson). Zonder deze override tonen tabtitel en linkerbalk de naam van
    # het basisscenario in plaats van het eigen scenario.
    if file_type == "NETWORK" and isinstance(data, dict):
        area_name_path = _find_area_dir(area_id) / ".area-name"
        if area_name_path.exists():
            try:
                override_name = area_name_path.read_text(encoding="utf-8").strip()
            except Exception:
                override_name = ""
            if override_name:
                data.setdefault("properties", {})["name"] = override_name

    # NDJSON / GeoJSONL-streaming (alleen routes): één JSON-object per regel.
    # Regel 1 = header-object met metadata; daarna één feature per regel. Zo
    # hoeft de client geen monolithische JSON.parse te doen en kan progressief
    # renderen. Getriggerd via ?format=ndjson.
    if (
        collection_id == "routes"
        and request.args.get("format", "").strip().lower() == "ndjson"
    ):
        features = data.get("features", []) if isinstance(data, dict) else []
        top_props = (
            data.get("properties")
            if isinstance(data, dict) and isinstance(data.get("properties"), dict)
            else {}
        )

        def _ndjson_gen():
            header = {
                "type": "Header",
                "collection": collection_id,
                "numberMatched": len(features),
                "timeStamp": _dt.datetime.now(_dt.timezone.utc).isoformat(
                    timespec="seconds"
                ),
                "properties": top_props,
            }
            yield json.dumps(header, ensure_ascii=False) + "\n"
            for feat in features:
                yield json.dumps(feat, ensure_ascii=False) + "\n"

        resp = Response(
            stream_with_context(_ndjson_gen()),
            mimetype="application/x-ndjson",
        )
        resp.headers["ETag"] = etag
        resp.headers["Last-Modified"] = last_modified
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["X-Accel-Buffering"] = "no"  # Nginx: geen buffering
        return resp

    resp = _ogc_items_response(collection_id, data, self_url)
    resp.headers["ETag"] = etag
    resp.headers["Last-Modified"] = last_modified
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/proxy/mvt/<path:layer_uuid>/<int:z>/<int:x>/<int:y>.mvt")
def proxy_mvt(layer_uuid, z, x, y):
    """Pass-through proxy voor Spectrum MVT-tiles.
    Stuurt de ruwe protobuf-bytes door zodat Mapbox GL ze direct kan renderen."""
    mapping_uuid = request.args.get("mappingUuid", default="")
    if not mapping_uuid:
        abort(400)
    url = (
        f"https://analytics.dat.nl/api/v1/vectortiles/layers/"
        f"{layer_uuid}/{z}/{x}/{y}.mvt?mappingUuid={mapping_uuid}"
    )
    try:
        tile_resp = requests.get(url, timeout=10)
        tile_resp.raise_for_status()
    except Exception as exc:
        app.logger.warning("MVT tile ophalen mislukt: %s", exc)
        abort(502)
    resp = make_response(tile_resp.content)
    resp.headers["Content-Type"] = "application/x-protobuf"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/traffic-sign-icon/<string:code>")
def traffic_sign_icon(code):
    """Serveer een NDW PNG-icoon voor een RVV-bordcode; 404 als niet beschikbaar.

    Naast een exacte match worden enkele naamvarianten geprobeerd, omdat de
    NDW-brondata codes gebruikt die iets afwijken van de iconbestandsnamen:
      * voorloopnullen in het eerste segment (``A01`` → ``A1``, ``C08`` → ``C8``);
      * een zone-suffix (``-ZB`` = Zone Begin, ``-ZE`` = Zone Eind, e.d.) die
        het onderliggende bord niet verandert en dus wordt weggelaten.
    """
    safe = re.sub(
        r"[^A-Za-z0-9.\-]", "", code
    )  # koppelteken en decimaalpunt toegestaan
    icon_dir = Path(__file__).parent / "traffic_sign_icons"

    def _norm_zeros(name: str) -> str:
        parts = name.split("-")
        m = re.match(r"^([A-Za-z]+)0*([0-9].*)$", parts[0])
        if m:
            parts[0] = m.group(1) + m.group(2)
        return "-".join(parts)

    # Bouw kandidaat-namen in volgorde van voorkeur (eerste die bestaat wint).
    candidates: list[str] = []

    def _add(name: str) -> None:
        if name and name not in candidates:
            candidates.append(name)

    _add(safe)
    # Zone-suffix (-ZB/-ZE/-ZP/…) van het einde strippen.
    _base = re.sub(r"-Z[A-Za-z]$", "", safe)
    _add(_base)
    # Voorloopnullen normaliseren (met en zonder zone-suffix).
    _add(_norm_zeros(safe))
    _add(_norm_zeros(_base))
    # Alias voor bekende niet-RVV codes (bv. bebouwde kom → H1).
    _ICON_ALIASES = {"citylimit": "H1"}
    _add(_ICON_ALIASES.get(_base.lower()))

    match = next((c for c in candidates if (icon_dir / f"{c}.png").exists()), None)
    if match is None:
        from flask import abort

        abort(404)
    resp = send_from_directory(str(icon_dir), f"{match}.png", mimetype="image/png")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ---------------------------------------------------------------------------
# Maatregelsets uit een geüploade GeoPackage (measure_set_creator)
# ---------------------------------------------------------------------------
# Ondersteunt het "maatregelset"-paneel in measure-set-panel.js: een GeoPackage
# wordt geüpload en server-side geïnspecteerd (lagen + velden + waarden), en
# kan vervolgens tegen het netwerk van een gebied worden gesneden om per
# polygon-feature een 'adjust'-wijzigingenlijst te bouwen (via de vendored
# gmt_calculation_lib measure_set_creator).


def _measure_uploads_dir() -> Path:
    """Map waar geüploade GeoPackages tijdelijk worden bewaard."""
    d = _work_dir() / "_measure_uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _measure_upload_path(upload_id: str) -> Path:
    if not upload_id or not _safe(upload_id):
        abort(400, "Ongeldige upload_id")
    return _measure_uploads_dir() / f"{upload_id}.gpkg"


@app.route("/measure-sets/upload", methods=["POST"])
def measure_sets_upload():
    """Upload een .gpkg-bestand en geef de lagen (+velden) erin terug."""
    if not _GEOPANDAS_AVAILABLE:
        abort(503, "geopandas is vereist voor het lezen van GeoPackage-bestanden.")

    f = request.files.get("file")
    if f is None or not f.filename:
        abort(400, "Geen bestand ontvangen (form-veld 'file')")
    if not f.filename.lower().endswith(".gpkg"):
        abort(400, "Alleen .gpkg-bestanden (GeoPackage) worden ondersteund")

    upload_id = uuid.uuid4().hex
    path = _measure_upload_path(upload_id)
    f.save(path)

    try:
        import pyogrio

        layer_infos = pyogrio.list_layers(path)
        layers = []
        for row in layer_infos:
            name = str(row[0])
            geom_type = str(row[1]) if len(row) > 1 and row[1] is not None else None
            gdf = _gpd.read_file(path, layer=name)
            fields = [c for c in gdf.columns if c != "geometry"]
            layers.append(
                {
                    "name": name,
                    "geometryType": geom_type,
                    "fields": fields,
                    "featureCount": int(len(gdf)),
                }
            )
    except Exception as exc:
        path.unlink(missing_ok=True)
        abort(400, f"Kon GeoPackage niet lezen: {exc}")

    return jsonify({"uploadId": upload_id, "layers": layers})


@app.route("/measure-sets/<upload_id>/layers/<layer>/features")
def measure_sets_layer_features(upload_id, layer):
    """Geef alle features van een laag terug als GeoJSON."""
    if not _GEOPANDAS_AVAILABLE:
        abort(503, "geopandas is vereist voor het lezen van GeoPackage-bestanden.")

    path = _measure_upload_path(upload_id)
    if not path.exists():
        abort(404, "Upload niet gevonden (mogelijk verlopen — opnieuw uploaden)")

    try:
        gdf = _gpd.read_file(path, layer=layer)
    except Exception as exc:
        abort(400, f"Kon laag '{layer}' niet lezen: {exc}")
    if gdf.crs is not None and str(gdf.crs).upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    for col in gdf.columns:
        if col == "geometry":
            continue
        try:
            if not _is_json_safe_dtype(gdf[col].dtype):
                gdf[col] = gdf[col].astype("string")
        except Exception:
            gdf[col] = gdf[col].astype(str)
        if hasattr(gdf[col], "dt"):
            gdf[col] = gdf[col].dt.strftime("%Y-%m-%dT%H:%M:%S.%f").replace("NaT", "")

    return gdf.to_json()


def _is_json_safe_dtype(dtype):
    name = dtype.name.lower()
    return name in (
        "int64",
        "int32",
        "int16",
        "int8",
        "uint64",
        "uint32",
        "uint16",
        "uint8",
        "float64",
        "float32",
        "float16",
        "object",
        "string",
        "bool",
        "category",
    )


@app.route("/measure-sets/<upload_id>/layers/<layer>/values")
def measure_sets_field_values(upload_id, layer):
    """Geef alle unieke waarden in `field` van `layer` terug (voor de
    veld-verkenner in het paneel: welke maatregelset-namen komen voor)."""
    if not _GEOPANDAS_AVAILABLE:
        abort(503, "geopandas is vereist voor het lezen van GeoPackage-bestanden.")

    field = request.args.get("field", "").strip()
    if not field:
        abort(400, 'Parameter "field" ontbreekt')

    path = _measure_upload_path(upload_id)
    if not path.exists():
        abort(404, "Upload niet gevonden (mogelijk verlopen — opnieuw uploaden)")

    try:
        gdf = _gpd.read_file(path, layer=layer)
    except Exception as exc:
        abort(400, f"Kon laag '{layer}' niet lezen: {exc}")
    if field not in gdf.columns:
        abort(400, f"Veld '{field}' bestaat niet in laag '{layer}'")

    values = sorted({str(v) for v in gdf[field].dropna().tolist()})
    return jsonify(
        {"layer": layer, "field": field, "values": values, "count": len(values)}
    )


@app.route("/measure-sets/generate", methods=["POST"])
def measure_sets_generate():
    """Snijd een GeoPackage-laag met het netwerk van een gebied en bouw per
    polygon-feature een maatregelset (adjust-wijzigingenlijst).

    Body: {area_id, mode, upload_id, layer, field}
    Retourneert: {measureSets: [{name, changes:[{linkId, capacity}, ...]}, ...]}
    """
    if not _GEOPANDAS_AVAILABLE:
        abort(503, "geopandas is vereist voor het lezen van GeoPackage-bestanden.")

    body = request.get_json(force=True, silent=True) or {}
    area_id = str(body.get("area_id", "")).strip()
    mode = str(body.get("mode", "")).strip().upper()
    upload_id = str(body.get("upload_id", "")).strip()
    layer = str(body.get("layer", "")).strip()
    field = str(body.get("field", "")).strip()

    if not area_id or not _safe(area_id):
        abort(400, "Ongeldige of ontbrekende area_id")
    if not mode or not _safe(mode):
        abort(400, "Ongeldige of ontbrekende mode")
    if not layer or not field:
        abort(400, "layer en field zijn verplicht")

    path = _measure_upload_path(upload_id)
    if not path.exists():
        abort(404, "Upload niet gevonden (mogelijk verlopen — opnieuw uploaden)")

    net_path = _data_path(area_id, mode, "NETWORK")
    if net_path is None or not net_path.exists():
        abort(404, f"Netwerkbestand niet gevonden voor {area_id}/{mode}")
    try:
        network_fc = _read_geodata(net_path)
    except Exception as exc:
        abort(500, f"Kon netwerk niet lezen: {exc}")

    try:
        gdf = _gpd.read_file(path, layer=layer)
    except Exception as exc:
        abort(400, f"Kon laag '{layer}' niet lezen: {exc}")
    if gdf.crs is not None and str(gdf.crs).upper() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    # Standaardiseer niet-JSON-serialiseerbare eigenschappen (oa. datumvelden
    # die GeoPackage-features kan bevatten, zoals CreationDate).
    for col in gdf.columns:
        if col == "geometry":
            continue
        try:
            if not _is_json_safe_dtype(gdf[col].dtype):
                gdf[col] = gdf[col].astype("string")
        except Exception:
            gdf[col] = gdf[col].astype(str)
        if hasattr(gdf[col], "dt"):
            gdf[col] = gdf[col].dt.strftime("%Y-%m-%dT%H:%M:%S.%f").replace("NaT", "")

    layer_features = json.loads(gdf.to_json()).get("features", [])

    try:
        from measure_set_creator.core.measure_set_creator_core import (
            create_measure_sets,
        )
    except ImportError as exc:
        abort(503, f"measure_set_creator (gmt_calculation_lib) niet beschikbaar: {exc}")

    try:
        measure_sets = create_measure_sets(network_fc, layer_features, layer, field)
    except Exception as exc:
        abort(500, f"Fout bij bouwen van maatregelsets: {exc}")

    return jsonify({"measureSets": measure_sets})


@app.route("/processes")
def ogc_processes():
    avail = _get_available_processes()
    procs = []
    for pid in _PROCESS_DESCRIPTIONS:
        if pid not in avail:
            continue
        desc = _PROCESS_DESCRIPTIONS[pid]
        procs.append(
            {
                "id": pid,
                "title": desc["title"],
                "description": desc["description"],
                "version": desc["version"],
                "jobControlOptions": desc["jobControlOptions"],
                "outputTransmission": desc["outputTransmission"],
                "links": [
                    {
                        "href": f"/processes/{pid}",
                        "rel": "self",
                        "type": "application/json",
                        "title": desc["title"],
                    },
                ],
            }
        )
    return jsonify(
        {
            "processes": procs,
            "links": [
                {
                    "href": "/processes",
                    "rel": "self",
                    "type": "application/json",
                    "title": "Processen",
                },
            ],
        }
    )


@app.route("/processes/<process_id>")
def ogc_process(process_id):
    avail = _get_available_processes()
    if process_id not in _PROCESS_DESCRIPTIONS:
        abort(404, f"Proces niet gevonden: {process_id}")
    if process_id not in avail:
        abort(503, f"Proces niet beschikbaar: {process_id}")
    desc = dict(_PROCESS_DESCRIPTIONS[process_id])
    desc["links"] = [
        {
            "href": f"/processes/{process_id}",
            "rel": "self",
            "type": "application/json",
            "title": desc["title"],
        },
        {
            "href": f"/processes/{process_id}/execution",
            "rel": "execute",
            "type": "application/json",
            "title": f"{desc['title']} uitvoeren",
        },
    ]
    return jsonify(desc)


@app.route("/processes/<process_id>/execution", methods=["POST"])
def ogc_process_execute(process_id):
    avail = _get_available_processes()
    if process_id not in _PROCESS_DESCRIPTIONS:
        abort(404, f"Proces niet gevonden: {process_id}")
    if process_id not in avail:
        abort(503, f"Proces niet beschikbaar: {process_id}")

    raw_body = request.get_json(force=True, silent=True) or {}
    # Ondersteun zowel OGC {"inputs": {...}} als flat body
    inputs = raw_body.get("inputs", raw_body)

    dispatch = {
        "prepare": _execute_prepare,
        "adjust": _execute_adjust,
        "whatif-road-closure": _execute_whatif_road_closure,
        "wegenscan": _execute_wegenscan,
        "fetch_osm": _execute_fetch_osm,
        "delete-area": _execute_delete_area,
        "set-directory": _execute_set_directory,
        "upload-to-gmt": _execute_upload_to_gmt,
    }
    body, status, headers = dispatch[process_id](inputs)
    resp = jsonify(body)
    resp.status_code = status
    for k, v in headers.items():
        resp.headers[k] = v
    return resp


@app.route("/events")
def sse_events():
    """SSE-stream voor ?follow=true: stuurt een event zodra een adjust klaar is.

    Query-param: areaId — het gebied waarop de client zich abonneert.
    Event-payload (JSON): { new_area_id, compare_url, mode }

    De verbinding blijft open; elke 25 seconden wordt een keep-alive comment
    gestuurd zodat proxies de verbinding niet verbreken.
    """
    area_id = request.args.get("areaId", "")
    q: queue.SimpleQueue = queue.SimpleQueue()

    with _sse_listeners_lock:
        _sse_listeners.setdefault(area_id, set()).add(q)

    def generate():
        try:
            # Stuur retry-hint eenmalig
            yield "retry: 3000\n\n"
            while True:
                try:
                    event, data = q.get(timeout=25)
                    yield f"event: {event}\ndata: {data}\n\n"
                except queue.Empty:
                    # Keep-alive — voorkomt dat proxies/load-balancers de verbinding sluiten
                    yield ": keepalive\n\n"
        finally:
            with _sse_listeners_lock:
                _sse_listeners.get(area_id, set()).discard(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx: schakel buffering uit
        },
    )


@app.route("/maquette/preview", methods=["POST"])
def maquette_preview():
    """Ontvang een preview-melding van maquette_camera.py en stuur een SSE-event
    naar alle actieve browsers zodat het wegvak kan oplichten vóór de berekening.

    Body (JSON): { "area_id": "...", "link_ids": [123, -123] }
    """
    body = request.get_json(silent=True) or {}
    link_ids = body.get("link_ids", [])
    payload = json.dumps({"link_ids": link_ids})
    with _sse_listeners_lock:
        all_ids = list(_sse_listeners.keys())
    for aid in all_ids:
        _sse_put(aid, "link_preview", payload)
    return jsonify({"ok": True})


@app.route("/maquette/detections", methods=["POST"])
def maquette_detections():
    """Relais de zwarte vlakken die de camera ziet naar de browsers via SSE.

    Body (JSON): { "area_id": "...", "detections": [ {lon, lat, outline, …} ] }

    Puur ter controle: hiermee tekent de kaart live wat de camera detecteert,
    zonder dat er iets wordt afgesloten. Ligt het vlak op de kaart ergens anders
    dan het blokje op de maquette, dan is de calibratie scheef.
    """
    body = request.get_json(silent=True) or {}
    payload = json.dumps(
        {
            "detections": body.get("detections", []),
            "camera_view": body.get("camera_view"),
        }
    )
    with _sse_listeners_lock:
        all_ids = list(_sse_listeners.keys())
    for aid in all_ids:
        _sse_put(aid, "maquette_detections", payload)
    return jsonify({"ok": True})


@app.route("/maquette/heartbeat", methods=["POST"])
def maquette_heartbeat():
    """Ontvang een heartbeat van maquette_camera.py en stuur het als SSE-event
    naar alle actieve SSE-listeners, ongeacht area_id.

    Camera-status is globaal (één camera per server), dus er is geen reden om
    dit te beperken tot één area_id — zeker niet als de browser via een adjust
    ondertussen een nieuw area_id heeft gekregen.

    Body (JSON): { "area_id": "...", "active": true/false }
    """
    body = request.get_json(silent=True) or {}
    area_id = body.get("area_id", "")
    active = bool(body.get("active", True))
    if not area_id:
        return jsonify({"error": "area_id vereist"}), 400
    payload = json.dumps({"active": active})
    with _sse_listeners_lock:
        all_ids = list(_sse_listeners.keys())
    for aid in all_ids:
        _sse_put(aid, "camera_status", payload)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Camerabeeld-relais: maquette_camera.py → browser
# ---------------------------------------------------------------------------


@app.route("/maquette/frame", methods=["POST"])
def maquette_post_frame():
    """Ontvang één JPEG-frame van maquette_camera.py (body = ruwe JPEG).

    Query: ?w=<breedte>&h=<hoogte> — de werkelijke cameraresolutie, die de
    browser nodig heeft om de calibratie in camerapixels uit te drukken.
    """
    global _mjpeg_frame, _mjpeg_seq, _mjpeg_meta
    data = request.get_data(cache=False)
    if not data:
        return jsonify({"error": "leeg frame"}), 400
    try:
        width = int(request.args.get("w", 0))
        height = int(request.args.get("h", 0))
    except ValueError:
        width = height = 0
    with _mjpeg_cond:
        _mjpeg_frame = data
        _mjpeg_seq += 1
        _mjpeg_meta = {"width": width, "height": height, "ts": time.time()}
        clients = _mjpeg_clients
        _mjpeg_cond.notify_all()
    return jsonify({"ok": True, "clients": clients})


@app.route("/maquette/stream.mjpg")
def maquette_stream():
    """Live camerabeeld als MJPEG (multipart/x-mixed-replace).

    Elke client leest altijd het *actuele* frame; wie te traag consumeert slaat
    frames over in plaats van een wachtrij te laten vollopen.
    """
    global _mjpeg_clients
    with _mjpeg_cond:
        if _mjpeg_clients >= _MJPEG_MAX_CLIENTS:
            return jsonify({"error": "te veel gelijktijdige kijkers"}), 503
        _mjpeg_clients += 1

    def _gen():
        global _mjpeg_clients
        last = -1
        try:
            while True:
                with _mjpeg_cond:
                    if not _mjpeg_cond.wait_for(
                        lambda: _mjpeg_seq != last and _mjpeg_frame is not None,
                        timeout=5.0,
                    ):
                        # Time-out: een lege boundary houdt de verbinding levend
                        # en laat een verbroken socket alsnog blijken.
                        yield b"--frame\r\n\r\n"
                        continue
                    frame = _mjpeg_frame
                    last = _mjpeg_seq
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(frame)).encode()
                    + b"\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
        finally:
            with _mjpeg_cond:
                _mjpeg_clients -= 1

    return Response(
        _gen(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/maquette/frame.jpg")
def maquette_frame_jpg():
    """Het laatste frame als los plaatje — terugval als MJPEG niet werkt."""
    with _mjpeg_cond:
        frame = _mjpeg_frame
    if frame is None:
        abort(404)
    return Response(
        frame,
        mimetype="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.route("/maquette/stream-info")
def maquette_stream_info():
    """Status van het camerabeeld: resolutie, ouderdom en aantal kijkers."""
    with _mjpeg_cond:
        meta = dict(_mjpeg_meta)
        seq = _mjpeg_seq
        clients = _mjpeg_clients
        have = _mjpeg_frame is not None
    age = (time.time() - meta.get("ts", 0.0)) if have else None
    return jsonify(
        {
            "available": have,
            "width": meta.get("width", 0),
            "height": meta.get("height", 0),
            "seq": seq,
            "age": age,
            "clients": clients,
        }
    )


# ---------------------------------------------------------------------------
# Cursorpositie voor de virtuele maquette-modus
# ---------------------------------------------------------------------------


@app.route("/maquette/cursor", methods=["POST"])
def maquette_post_cursor():
    """Ontvang de cursorpositie van de browser (virtuele maquette-modus).

    Body (JSON): { "x": 123.0, "y": 456.0, "lon": 6.17, "lat": 52.25 }
    x/y zijn CSS-pixels t.o.v. de kaartcontainer, lon/lat de ge-unprojecte
    positie. De browser rekent zelf om: die kent de kaartweergave exact, terwijl
    de Windows-cursor uitlezen een DPI- en vensterrandcorrectie zou vergen.
    """
    global _cursor_slot
    body = request.get_json(silent=True) or {}
    try:
        slot = {
            "x": float(body["x"]),
            "y": float(body["y"]),
            "lon": float(body["lon"]),
            "lat": float(body["lat"]),
            "ts": time.time(),
        }
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "x, y, lon en lat vereist"}), 400
    with _cursor_lock:
        _cursor_slot = slot
    return jsonify({"ok": True})


@app.route("/maquette/cursor", methods=["GET"])
def maquette_get_cursor():
    """Geef de laatst ontvangen cursorpositie terug, met de ouderdom erbij."""
    with _cursor_lock:
        slot = dict(_cursor_slot) if _cursor_slot else None
    if slot is None:
        return jsonify({"available": False})
    slot["age"] = time.time() - slot["ts"]
    slot["available"] = True
    return jsonify(slot)


def _calibration_path(area_id: str) -> Path:
    """Pad naar het calibratiebestand voor een basis-area."""
    return _find_area_dir(area_id) / f"{area_id}-CALIBRATION.json"


@app.route("/maquette/calibration", methods=["GET"])
def maquette_get_calibration():
    """Geef de opgeslagen calibratie voor een area terug.

    Query: ?area_id=...&mode=CAR
    Antwoord: { "exists": bool, "calibration": {...} | null }
    """
    area_id = str(request.args.get("area_id", "")).strip()
    if not area_id:
        return jsonify({"error": "area_id vereist"}), 400
    path = _calibration_path(area_id)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return jsonify({"exists": True, "calibration": data})
        except Exception as exc:
            return jsonify({"exists": False, "calibration": None, "error": str(exc)})
    return jsonify({"exists": False, "calibration": None})


@app.route("/maquette/calibration", methods=["POST"])
def maquette_post_calibration():
    """Sla een calibratie op voor een area.

    Body (JSON): { "area_id": "...", "calibration": {...} }
    """
    body = request.get_json(silent=True) or {}
    area_id = str(body.get("area_id", "")).strip()
    calibration = body.get("calibration")
    if not area_id or not isinstance(calibration, dict):
        return jsonify({"error": "area_id en calibration vereist"}), 400
    path = _calibration_path(area_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(calibration, indent=2), encoding="utf-8")
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"ok": True})


def _stop_maquette_process() -> None:
    """Beëindig het lopende maquette-camera proces (thread-safe)."""
    global _maquette_process, _maquette_area_id
    with _maquette_process_lock:
        proc = _maquette_process
        aid = _maquette_area_id
        _maquette_process = None
        _maquette_area_id = ""
    if proc is not None:
        try:
            proc.terminate()
        except Exception:
            pass
    if aid:
        _sse_put(aid, "camera_status", json.dumps({"active": False}))


@app.route("/maquette/start", methods=["POST"])
def maquette_start():
    """Start maquette_camera.py als subprocess.

    Body (JSON):
    {
      "area_id":   "...",
      "mode":      "CAR",
      "camera_id": -1,
      "preview":   false,
      "viewport":  { "width": 1280, "height": 720 }
    }

    `viewport` geeft alleen nog de gewenste camera-resolutie door. De koppeling
    tussen camerapixels en kaart komt uit het calibratiebestand, dat de browser
    schrijft; geo-grenzen zijn daarvoor niet meer nodig.
    """
    global _maquette_process, _maquette_area_id

    body = request.get_json(silent=True) or {}
    area_id = str(body.get("area_id", "")).strip()
    mode = str(body.get("mode", "CAR")).upper()
    camera_id = int(body.get("camera_id", -1))
    vp = body.get("viewport") or {}
    preview = bool(body.get("preview", False))

    if not area_id:
        return jsonify({"error": "area_id vereist"}), 400

    if not all(k in vp for k in ("width", "height")):
        return jsonify({"error": "viewport vereist: ('width', 'height')"}), 400

    # Stop eventueel lopend proces
    _stop_maquette_process()

    script = Path(__file__).parent / "maquette_camera.py"
    cmd = [
        sys.executable,
        str(script),
        "--server",
        # Bewust 127.0.0.1 en niet localhost: een DNS-lookup van localhost kost
        # op deze machines ~2 s, wat de frame-push tot stilstand zou brengen.
        f"http://127.0.0.1:{request.host.split(':')[-1]}",
        "--area-id",
        area_id,
        "--mode",
        mode,
        "--camera-id",
        str(camera_id),
        "--width",
        str(int(vp["width"])),
        "--height",
        str(int(vp["height"])),
    ]

    # Preview-stand: alleen camerabeeld doorgeven, geen detectie. Wordt gebruikt
    # terwijl de gebruiker in de browser de calibratie-vierhoek versleept.
    if preview:
        cmd.append("--preview")

    print(f"[maquette] starten: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=str(Path(__file__).parent))

    with _maquette_process_lock:
        _maquette_process = proc
        _maquette_area_id = area_id

    return jsonify({"ok": True, "pid": proc.pid})


@app.route("/maquette/stop", methods=["POST"])
def maquette_stop():
    """Stop het lopende maquette-camera proces."""
    _stop_maquette_process()
    return jsonify({"ok": True})


@app.route("/maquette/status")
def maquette_status():
    """Geeft de status van het maquette-camera proces terug."""
    with _maquette_process_lock:
        proc = _maquette_process
        aid = _maquette_area_id
    running = proc is not None and proc.poll() is None
    return jsonify(
        {"running": running, "area_id": aid, "pid": proc.pid if running else None}
    )


@app.route("/jobs")
def ogc_jobs():
    with _jobs_lock:
        jobs_copy = list(_jobs.values())
    return jsonify(
        {
            "jobs": [_job_to_status(j) for j in jobs_copy],
            "links": [
                {
                    "href": "/jobs",
                    "rel": "self",
                    "type": "application/json",
                    "title": "Actieve jobs",
                },
            ],
        }
    )


@app.route("/jobs/<job_id>")
def ogc_job(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        abort(404, f"Job niet gevonden: {job_id}")
    return jsonify(_job_to_status(job))


@app.route("/jobs/<job_id>/results")
def ogc_job_results(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        abort(404, f"Job niet gevonden: {job_id}")
    if job["status"] not in ("successful",):
        abort(404, f"Job {job_id} heeft nog geen resultaten (status: {job['status']})")
    return jsonify(job.get("_results", {}))


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
# Request-timing: log trage requests (>500ms), of alle requests met --timing.
# ---------------------------------------------------------------------------
_TIMING_SLOW_MS = 500.0


@app.before_request
def _timing_start():
    g._t0 = time.perf_counter()


@app.after_request
def _timing_end(response):
    t0 = getattr(g, "_t0", None)
    if t0 is not None:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if args.timing or elapsed_ms > _TIMING_SLOW_MS:
            tag = "[timing]" if args.timing else "[slow]"
            print(
                f"{tag} {request.method} {request.full_path} "
                f"{response.status_code} {elapsed_ms:.0f}ms"
            )
    return response


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        print("work opschonen...")
        _cleanup_work_dir()
    print(f"Data-map    : {DATA_DIR}")
    print(
        f"prepare     : {'beschikbaar' if _PREPARE_AVAILABLE else 'NIET beschikbaar'}"
    )
    print(f"adjust      : {'beschikbaar' if _ADJUST_AVAILABLE else 'NIET beschikbaar'}")
    print(
        f"flow_scaler : {'beschikbaar' if _FLOW_SCALER_AVAILABLE else 'NIET beschikbaar'}"
    )
    print(f"whatif      : {'beschikbaar' if _WHATIF_AVAILABLE else 'NIET beschikbaar'}")
    print(f"Server      : http://localhost:{args.port}")
    _threaded = not args.no_threaded
    print(f"threading   : {'multi-threaded' if _threaded else 'single-threaded'}")
    if not _threaded:
        print(
            "WAARSCHUWING : single-threaded — het camerabeeld van de maquette "
            "(/maquette/stream.mjpg) blokkeert dan de hele server. Gebruik de "
            "maquette-calibratie alleen multi-threaded."
        )
    app.run(host="0.0.0.0", port=args.port, debug=True, threaded=_threaded)
