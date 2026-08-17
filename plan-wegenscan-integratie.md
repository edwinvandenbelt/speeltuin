# Plan: Wegenscan integratie in de Speeltuin

## Doel

De `wegenscan-2.1.0` package ontsluiten als OGC API Process in de speeltuin-server,
zodat gebruikers per bestaand gebied een veiligheids-KPI-scan kunnen starten en de
resultaten (21 KPI's + geaggregeerde score) kunnen bekijken in de kaartviewer.

---

## Analyse

### Wat doet de wegenscan?

De pipeline bestaat uit twee fasen:

**Fase A – Enrichment** (data ophalen uit Databricks, toevoegen aan GeoJSON-properties)

| Script | Wat het toevoegt | Databricks-tabel | Spatial filter |
|---|---|---|---|
| `add_speed_attributes.py` | `max_speed`, `max_speed_s85` | `nwb.wegvakken` + snelheden | bbox (al ingebouwd) |
| `add_road_category.py` | `road_category`, `wegcat` | `nwb.wkd_weg_catv2` | nee (heel NL) |
| `add_profile.py` | `profile`, `bicycle_location` | `nwb.wkd_verkeerstypen` | nee |
| `add_pedestrian.py` | `pedestrian_location`, `pedestrian_crossing` | diverse NWB-tabellen | nee |
| `add_parking.py` | `parking_location`, `parking_width` | `nwb.wkd_parkvlak` | nee |
| `add_markings.py` | `longitudinal_markings`, `separation` | _(defaults)_ | — |
| `add_speed_bumps.py` | `speed_bumps` | drempeldata of default | — |
| `add_bus.py` | `bus_frequency`, `bus_facility` | _(defaults)_ | — |
| `add_social_interaction.py` | `social_interaction` | _(default: 'ja')_ | — |
| `add_surface.py` | `surface` | OSM via mapmatch | **fase 2** |

**Fase B – KPI-berekening** (`wegenscan.py` + `core/`)

- `build_invoer(props)` – vertaalt GeoJSON-properties naar invoerdict (met defaults voor ontbrekende waarden)
- `calculate_kpis(invoer)` – berekent 21 veiligheids-KPI's (GOED / REDELIJK / MATIG / SLECHT / NVT)
- `calculate_generic_safety(safety)` – geaggregeerde score op basis van gemiddelde

De 21 KPI's zijn verdeeld over drie modules:

| Module | KPI's |
|---|---|
| `FunctieGebruik` | `r_functional_usage` |
| `FunctieVorm` | `r_longitudinal_marking`, `r_directional_separation`, `r_lane_width`, `r_road_surface`, `r_pedestrian_facility`, `r_bicycle_facility`, `r_parking_facility`, `r_bus_stop_facility`, `r_speed_bumps` |
| `VormGebruik` | `r_roadside_damage`, `r_road_width`, `r_pedestrian_width`, `r_bicycle_width`, `r_parking_location`, `r_bus_location`, `r_pedestrian_crossing`, `r_bicycle_crossing`, `r_bike_speed`, `r_bike_usage`, `r_bike_parking`, `r_social_interaction` |

---

### Koppeling speeltuin ↔ wegenscan

De speeltuin-NETWORK-bestanden zijn Spectrum-gebaseerd. De enrichment-scripts verwachten
NWB `wvk_id` als join-key. **Aanname: `spectrumId` = `wvk_id`** in de Nederlandse context.

Dit betekent dat de enrichment-scripts zonder inhoudelijke aanpassing werken: de
`wvk_id`-lookup wordt gevoed met `props["spectrumId"]` in plaats van `props["wvk_id"]`.

**Al aanwezig in NETWORK-GeoJSON (direct bruikbaar voor KPI-berekening):**
- `flow` → `r_flow` via `compute_total_flow()` ✓
- `speed` → initiële schatting `r_speed` (overschreven door `add_speed_attributes`)

**Ontbreekt, geleverd door enrichment:**
`road_category`, `max_speed`, `width`, `profile`, `surface`,
`separation`, `longitudinal_markings`, `pedestrian_*`, `bicycle_*`, `parking_*`, `speed_bumps`

---

## Architectuur

```
POST /processes/wegenscan/execution
    → job aanmaken (async)
    → _run_wegenscan_job() in achtergrondthread
        1. Laad NETWORK-GeoJSON (area_id + mode)
        2. Enrichment via wegenscan_pipeline.run_pipeline()
           – spectrumId als wvk_id join-key
           – Databricks-queries in volgorde: speed → road_category → profile
             → pedestrian → parking → markings/bumps/bus/social (defaults)
        3. KPI-berekening per feature (21 KPI's + generic_safety)
        4. Schrijf {area_id}-WEGENSCAN-{mode}.geojson

GET /collections/wegenscan/items?areaId=...&mode=...
    → levert WEGENSCAN-GeoJSON terug als OGC FeatureCollection
```

---

## Implementatiestappen

### Stap 1 – `requirements.txt`

Twee regels toevoegen:

```
./wegenscan-2.1.0-py3-none-any.whl
databricks-sql-connector>=3.0.0
```

> `databricks-sql-connector` vereist credentials in `.env`:
> `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`,
> `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`

---

### Stap 2 – Nieuw bestand `wegenscan_pipeline.py`

De enrichment-scripts in de package zijn CLI-tools (alleen `main()` als entrypoint).
Een dunne wrapper maakt ze aanroepbaar als library-functies.

```python
# wegenscan_pipeline.py
"""
Wegenscan enrichment + KPI pipeline als herbruikbare functie.
Ontworpen voor integratie in speeltuin server.py.

spectrumId (Spectrum-netwerk) wordt als join-key gebruikt op NWB wvk_id.
"""

from wegenscan import build_invoer, calculate_kpis, calculate_generic_safety
from db import execute_sql

# Enrichment-functies importeren uit de wegenscan-package
from add_speed_attributes import build_sql as _speed_sql, build_speed_lookup
from add_road_category import (
    build_wegcat_lookup, derive_road_category, derive_wegcat, SQL_QUERY as _WEGCAT_SQL
)
from add_profile import build_profile_lookup, SQL_QUERY as _PROFILE_SQL
from add_pedestrian import build_pedestrian_lookup, SQL_QUERY as _PEDESTRIAN_SQL
from add_parking import build_parking_lookup, SQL_QUERY as _PARKING_SQL


def enrich_features(features: list, id_field: str = "spectrumId") -> list:
    """
    Verrijkt een lijst GeoJSON-features met NWB-attributen via Databricks.
    Volgorde: speed → road_category → profile → pedestrian → parking →
              markings/speed_bumps/bus/social_interaction (defaults).
    """
    ...


def run_kpis(features: list) -> list:
    """
    Berekent 21 KPI's per feature. Voegt toe:
      props["safety"]          – dict met 21 KPI-sleutels
      props["generic_safety"]  – GOED / REDELIJK / MATIG / SLECHT
    """
    ...


def run_pipeline(geojson: dict, id_field: str = "spectrumId") -> dict:
    """Volledige enrichment + KPI op een GeoJSON FeatureCollection dict."""
    features = enrich_features(geojson["features"], id_field)
    features = run_kpis(features)
    return {**geojson, "features": features}
```

**Aandachtspunten bij implementatie:**

- `add_road_category` verwacht dat `max_speed` al aanwezig is op het feature →
  volgorde speed → category is verplicht.
- `add_road_category` en `add_profile` halen heel-NL op (geen bbox-filter). Optimaliseer
  door `WHERE wvk_id IN (...)` toe te voegen op basis van de `spectrumId`-set van het gebied.
- `add_speed_attributes` heeft al een bbox-filter ingebouwd; de bbox wordt afgeleid
  uit de GeoJSON-geometrieën als `properties.bbox` ontbreekt.

---

### Stap 3 – `server.py` – import

```python
try:
    from wegenscan_pipeline import run_pipeline as _ws_run_pipeline
    _WEGENSCAN_AVAILABLE = True
except ImportError as _e:
    _ws_run_pipeline = None
    _WEGENSCAN_AVAILABLE = False
    print(f"[server] WAARSCHUWING: wegenscan niet beschikbaar — {_e}")
```

---

### Stap 4 – `server.py` – process-beschrijving in `_PROCESS_DESCRIPTIONS`

```python
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
```

---

### Stap 5 – `server.py` – collection

In `_COLLECTIONS`:

```python
"wegenscan": {
    "title": "Wegenscan (veiligheidsscores)",
    "description": "21 veiligheids-KPI's + generic_safety per wegvak, berekend door de wegenscan.",
},
```

In `_COLLECTION_FILE_TYPE`:

```python
"wegenscan": "WEGENSCAN",
```

Bestandspatroon: `{area_id}-WEGENSCAN-{mode}.geojson`

---

### Stap 6 – `server.py` – job-runner `_run_wegenscan_job`

```python
def _run_wegenscan_job(job_id: str, area_id: str, mode: str):
    """Voer wegenscan-pipeline uit in achtergrondthread."""
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
                raise FileNotFoundError(f"Geen NETWORK-bestand voor {area_id}/{mode}")
            geojson = _read_geodata(network_path)
            result = _ws_run_pipeline(geojson, id_field="spectrumId")
        stream.flush()

        out_path = _find_area_dir(area_id) / f"{area_id}-WEGENSCAN-{mode}.geojson"
        out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")

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
```

---

### Stap 7 – `server.py` – route-dispatcher & beschikbaarheidscheck

In `POST /processes/{processId}/execution` (na de `whatif-road-closure` tak):

```python
elif process_id == "wegenscan" and _WEGENSCAN_AVAILABLE:
    area_id = inputs.get("area_id")
    mode    = inputs.get("mode", "CAR").upper()
    if not _safe(area_id):
        abort(400, description="Ongeldig area_id")
    threading.Thread(
        target=_run_wegenscan_job,
        args=(job_id, area_id, mode),
        daemon=True,
    ).start()
```

In `_get_available_processes()`:

```python
if _WEGENSCAN_AVAILABLE:
    avail.add("wegenscan")
```

---

### Stap 8 – `index.html` – frontend uitbreidingen

#### 8a – "Veiligheid" in de weergave-dropdown

Voeg `"Veiligheid"` toe aan de bestaande keuzelijst naast intensiteitsopties
(bijv. "Intensiteit auto", "Capaciteitsbenutting").

#### 8b – Wegenscan starten vanuit de UI

Als "Veiligheid" gekozen wordt maar er nog geen WEGENSCAN-bestand bestaat:
toon een knop **"Wegenscan uitvoeren"** die:

1. `POST /processes/wegenscan/execution` aanroept met `area_id` + `mode`
2. De job-status pollt (`GET /jobs/{jobId}`)
3. Na voltooiing de WEGENSCAN-laag laadt

#### 8c – Kaartkleur op `generic_safety`

| Waarde | Kleur |
|---|---|
| `GOED` | groen |
| `REDELIJK` | geel |
| `MATIG` | oranje |
| `SLECHT` | rood |
| `NVT` | grijs |

#### 8d – KPI-zijpaneel (alle 21 KPI's)

Bij klik op een wegvak in de veiligheidsweergave: open een zijpaneel met
alle 21 KPI-waarden als scorekaart:

```
┌─────────────────────────────────────┐
│ Wegvak: N307 – Kampen               │
│ Veiligheid: ● REDELIJK              │
├─────────────────────────────────────┤
│ Functioneel gebruik      ● GOED     │
│ Rijbaanbreedte           ● MATIG    │
│ Wegdek                   ● GOED     │
│ Rijrichtingscheiding     ● SLECHT   │
│ …                                   │
├─────────────────────────────────────┤
│ [✕ Sluiten]  → terug naar intensiteit│
└─────────────────────────────────────┘
```

Het paneel sluit door op ✕ te klikken of door een andere weergave te kiezen;
daarna herstelt de kaart naar de vorige laag (intensiteit).

---

## Bestandswijzigingen samengevat

| Bestand | Type | Wijziging |
|---|---|---|
| `requirements.txt` | Bestaand | wegenscan wheel + databricks-sql-connector |
| `wegenscan_pipeline.py` | **Nieuw** | Enrichment + KPI wrapper |
| `server.py` | Bestaand | Import · process-beschrijving · collection · job-runner · dispatcher · beschikbaarheidscheck |
| `index.html` | Bestaand | Dropdown-uitbreiding · veiligheidslaag · KPI-zijpaneel |

---

## Fasering

### Fase 1 – MVP (dit plan)
- Stappen 1 t/m 7: backend volledig werkend
- Stap 8a t/m 8c: dropdown + wegenscan starten + `generic_safety` heatmap

### Fase 2 – Uitbreidingen
- Stap 8d: volledig KPI-zijpaneel met alle 21 scores
- `add_surface.py` integreren (vereist OSM-mapmatch via Databricks)
- `WHERE wvk_id IN (...)` optimalisatie voor de heel-NL Databricks-queries
- S3-opslag van WEGENSCAN-resultaten (als `_s3_enabled()`)

---

## Openstaande risico's

| # | Risico | Mitigatie |
|---|---|---|
| 1 | **`spectrumId` ≠ `wvk_id`** voor sommige wegvakken | Valideren met testgebied vóór implementatie; niet-matchende wegvakken vallen terug op KPI-defaults |
| 2 | **Databricks-querygrootte** – `add_road_category` en `add_profile` halen heel NL op | `WHERE wvk_id IN (...)` filter toevoegen o.b.v. `spectrumId`-set van het gebied |
| 3 | **`add_surface` ontbreekt** – wegdektype valt terug op default `"gesloten (o.a. asfalt)"` | Acceptabel voor fase 1; OSM-mapmatch inbouwen in fase 2 |
| 4 | **KPI's voor BIKE/PEDESTRIAN** – tabellen zijn primair voor auto-infrastructuur | Resultaten voor fiets/voetganger zijn indicatief; documenteren in UI |
