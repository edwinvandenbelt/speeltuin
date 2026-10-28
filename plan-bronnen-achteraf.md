# Plan: bronnen achteraf ophalen vanuit de 3D-weergave

## Context
Lochem is geprepareerd zonder extra databronnen, dus er is geen `{id}-TRAFFIC-ASSETS.parquet`.
- digital-twin `/collections/traffic_assets/items` geeft 404 (`digital-twin/server.py:3265`).
- De frontend zet dan paden, kunstwerken, meubilair en drempels hard op 0 (`index.html:9812-9817`, vlag `_trafficAssetsNoFile`).
- `_apply_stage05` (`gmt-calculation-lib/src/prepare/core/prepare_core.py:1215-1222`) schrijft TRAFFIC-ASSETS in één keer, alleen uit de bronnen van díe run. Er wordt niets samengevoegd en niets geregistreerd. Losse bronnen later toevoegen overschrijft dus de rest.

Doel: als je in 3D een categorie aanvinkt en de bijbehorende bron ontbreekt, haalt de server die bron op in de achtergrond (zelfde 201+jobID-patroon als vegetatie). De bron wordt samengevoegd in TRAFFIC-ASSETS en geregistreerd.

Besluiten van de gebruiker:
- Alleen TRAFFIC-ASSETS wordt bijgewerkt, NETWORK niet.
- De logica komt in gmt-calculation-lib.

## Bronnen en categorieën
| bron | fetcher (gmt_network_enrichment) | assetTypes | waar |
|---|---|---|---|
| `osm` | `osm_asset_fetcher_core.fetch_osm_assets` + `elements_to_asset_features` (zonder network_fc) | footPath, cyclePath, mailbox, busShelter, mast, streetLight, bikeGate, infoBoard, trashBin, busStop, pedestrianCrossing, stopSign, laneMarkArrow, refugeArea*, … (speedBump alleen buiten NL) | overal; lokale PBF of Overpass |
| `bgt` | `bgt_fetcher_core.fetch_bgt_assets` | speedBump, bridge, tunnel, bak, screen | alleen NL |
| `signs` | `traffic_sign_fetcher_core.fetch_sign_features` | trafficSign | NDW (NL) of Overpass |
| `signals` | `fetch_signal_coords` + `signals_to_features` (zonder `annotate_network`) | trafficSignal | overal |
| `parking` | `parking_area_fetcher_core.fetch_parking_areas` | parkingArea | overal (BGT-deel alleen NL) |

Welke categorie welke bronnen nodig heeft:
- signs → signs, signals, osm
- paths → osm
- furniture → osm
- height → bgt
- bumps → bgt in NL, osm daarbuiten

viaduct, culvert, underpass en retainingWall worden door geen enkele bron geleverd. Die blijven 0.

## Stappen
_Na akkoord eerst dit plan als `plan-bronnen-achteraf.md` in de repo-root zetten, met checkboxes. Na elke stap stoppen voor akkoord._

### 1. gmt-calculation-lib: bronnenregister + `add_traffic_asset_sources`
- [x] Nieuwe module `src/prepare/core/traffic_asset_sources.py` met:
  - `SOURCE_ASSET_TYPES` en `sources_for_asset_types(types, in_nl) -> set[str]`.
  - `read_sources(path) -> dict`: leest `gmt_properties["sources"]` uit de parquet-footer via `from_geoparquet` in `gmt_shared/geoparquet.py`. Heeft een legacy-bestand geen register, dan leidt hij de bronnen af uit de features en kent hij elke feature een `src` toe:
    - `osm_id` → osm
    - BGT-types → bgt
    - trafficSignal → signals
    - trafficSign zonder `osm_id` → signs
    - parkingArea → parking
  - `add_traffic_asset_sources(traffic_assets_path, *, area_id, bbox, sources, osm_path=None, ndw_data_uri=None, bgt_url=None, …) -> dict`:
    - haalt per bron op via de bestaande fetchers;
    - zet `src=<bron>` op elke feature;
    - vervangt alleen de features met dezelfde `src`;
    - werkt het register bij: `{bron: {fetchedAt, count, via}}`. Ook een bron met 0 resultaten wordt geregistreerd, zodat die niet steeds opnieuw wordt opgehaald;
    - schrijft atomair (temp-bestand + `os.replace`).

    Mislukt een bron, dan wordt die niet geregistreerd en gaat de exception terug naar de aanroeper. De bronnen die wél gelukt zijn worden geschreven.
- [x] `_apply_stage05` (`prepare_core.py:1215`): tag features met `src` en schrijf hetzelfde register in de footer. Zo registreert ook een gewone prepare zijn bronnen. Bronnen die in die run uit staan, staan niet in het register.
- [x] Tests in `src/prepare/tests/test_core.py`, naast `TestApplyStage05` (:800):
  - merge vervangt alleen de eigen bron;
  - legacy-afleiding;
  - register met count=0;
  - een mislukte bron wordt niet geregistreerd;
  - `_apply_stage05` schrijft het register.
- [x] Versie ophogen en wheel bouwen. Controleren of de geïnstalleerde gmt_network_enrichment-versie de gebruikte functies heeft: de `.venv`-versie wijkt af van de bron.

### 2. digital-twin server: on-demand job
- [x] `requirements.txt` naar de nieuwe calc-lib-wheel. Import met try/except (`_TA_SOURCES_AVAILABLE`), zoals de andere optionele imports (:125-145).
- [x] Endpoint `traffic_assets` (`server.py:3253`):
  1. Bepaal de gevraagde types (`assetType`, of alle types).
  2. Bepaal de benodigde bronnen met `sources_for_asset_types(types, in_nl)`.
  3. Vergelijk met `read_sources(path)`. Geen bestand betekent dat alle bronnen ontbreken.
  4. Ontbreken er ophaalbare bronnen, dan volgt 201 + jobID, met dedup per gebied (zoals `_vegetation_jobs_by_area`, :757) en de circuit breaker (`_overpass_breaker_*`, :763).
  5. Anders 200 zoals nu.

  404 alleen als de lib niet beschikbaar is en er ook geen bestand is.
- [x] `_run_traffic_assets_job`, naar het voorbeeld van `_run_vegetation_job` (:879):
  - bbox via `_network_bbox` (:2134);
  - `_resolve_local_pbf(bbox)` als `osm_path`;
  - NDW-pad `BASE_DIR/"ndw_traffic_signs.json"` na `_ndw_ready.wait()`;
  - roept `add_traffic_asset_sources` aan;
  - doelbestand: het gebied dat het bestand bezit. Volg de `baseAreaId`-keten (`_area_parent_id`, :1124) naar de wortel, zodat scenario's meeërven;
  - per gebied één lopende job (lock), zodat er geen updates verloren gaan;
  - daarna S3-upload, zoals bij vegetatie.

  Cache-invalidatie gaat vanzelf: `_read_geodata_cached` cachet op mtime.

### 3. digital-twin frontend
- [x] `_waitForVegetationJob` / `...Shared` (`index.html:9457-9490`) generiek maken tot `_waitForJobShared(jobId, areaId)` en hergebruiken.
- [x] `_ensureTaTotal` (:9797), `loadTrafficAssetsInView` (:9936) en `_loadSpeedBumpsForArea` (:9745):
  - bij 201 wachten op de job en opnieuw proberen, zoals bij vegetatie, maximaal ~4 pogingen;
  - de spinner van de categorie blijft draaien zolang de job loopt.
- [x] ~~De bbox-load vraagt alleen de types van de aangevinkte categorieën op~~ → afwijking: de bbox-load vraagt alle types op met `fetch=0` (alleen serveren wat er is), omdat de Snelheid- en Kruispunten-lagen ook types van niet-aangevinkte categorieën gebruiken. Alleen het telverzoek van een aangevinkte categorie start een job. Na de job: `_reloadTrafficAssetsInView()`.
- [x] Hard-0 bij 404 weghalen. De NDW/Overpass-bordenfallback (`_loadTrafficSignsFallback`) alleen nog gebruiken als de job mislukt of de server 404/503 geeft.

### 4. Verificatie
- [ ] Lib-tests: `pytest src/prepare/tests/test_core.py` in gmt-calculation-lib.
- [ ] End-to-end met Lochem (via 127.0.0.1, niet localhost):
  - digital-twin starten, 3D, "Straatmeubilair" aanvinken → spinner en job, daarna telling > 0 en objecten zichtbaar;
  - footer controleren: `sources.osm` aanwezig;
  - "Kunstwerken" aanvinken → `bgt` wordt toegevoegd en het aantal osm-features blijft gelijk;
  - server herstarten → geen nieuwe fetch;
  - scenario `Lochem_ZW_Splits_09_03` toont dezelfde objecten via de base-fallback;
  - De Kien (legacy-bestand) laadt zonder nieuwe fetch voor bronnen die al aanwezig zijn.

## Buiten scope (gevonden, niet in dit plan)
- `enrich_network_with_osm_assets` zet bij elke aanroep alle tellers op 0. Daardoor gaan BGT-drempeltellers verloren als ook OSM aan staat.
- Afgeleide giveWay-markers komen in de NL-prepare nooit in TRAFFIC-ASSETS.
- Het menu-item "Full digital twin" in de digital twin post naar `fetch_osm`, maar dat proces kent de digital-twin-server niet (404). Bovendien wordt `.full-twin` altijd geschreven.
