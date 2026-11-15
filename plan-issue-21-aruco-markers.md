# Issue #21 — ArUco-markers i.p.v. zwart blokje op de maquette

## Context

De maquette-koppeling (`digital-twin/maquette_camera.py`) detecteert nu een
simpel "zwart blokje" (in de praktijk een telefoon) via een HSV/contrast-
heuristiek (`kien-camera-maquette/detection.py`). Dat is fragiel: drempels
voor helderheid/verzadiging/lokale-donkerte moeten per lichtomstandigheid
getuned worden, en er kan maar één object tegelijk herkend worden — zodra er
één stabiele detectie is, voert het script één aanpassing uit en **stopt het
proces zichzelf** (`maquette_camera.py:1271`).

Issue #21 vraagt om ArUco-markers in plaats van het blokje. In overleg is de
scope als volgt vastgesteld:

- de oude detector wordt **volledig vervangen** (geen fallback-modus);
- **elke bewerking krijgt zijn eigen vaste marker-ID**: niet "een marker
  sluit altijd de dichtstbijzijnde weg af", maar een vaste tabel
  marker-ID → bewerkingstype + parameter. Voor v1 precies drie bewerkingen:
  1. **Wegvak afsluiten** (capaciteit → 0, dichtstbijzijnde link)
  2. **30 km/u instellen** (dichtstbijzijnde link)
  3. **+100 productie** (dichtstbijzijnde *zone*, niet knoop)
- elk bewerkingstype mag maar **één keer tegelijk actief** zijn (geen
  meerdere fysieke kopieën van dezelfde marker tegelijk) — dat houdt
  marker-ID bruikbaar als zowel bewerkingstype-sleutel als track-identiteit,
  zonder extra positie-scoping in de tracker;
- de markers moeten als **PNG/PDF** gegenereerd kunnen worden, mét het
  label van de bewerking erbij afgedrukt, zodat de operator weet welke tag
  wat doet.

Vooronderzoek bevestigt twee dingen die de scope beperken:

- **Server:** `/processes/adjust/execution` classificeert een `changes`-item
  puur op de aanwezige sleutels (`adjust/core/adjust_core.py::_split_changes`)
  — er is geen apart `"type"`-veld. De drie bewerkingen hierboven zijn dus
  simpelweg drie verschillende sleutelcombinaties in dezelfde `changes`-array,
  die (zoals de hoofd-UI al doet via `pendingChanges`) in één keer vanaf het
  vaste basis-`area_id` wordt ingediend:
  - afsluiten: `{"linkId": id, "capacity": 0}`
  - 30 km/u: `{"linkId": id, "speed": 30}` (server herberekent capaciteit zelf
    via de snelheid→capaciteit-tabel in `adjust_core.py`)
  - productie: `{"zoneId": id, "production": "+100"}`
  **Geen serverwijziging nodig.**
- **Nearest-feature-lookup:** voor link-gerichte bewerkingen hergebruikt
  `maquette_camera.py` gewoon `find_nearest_link` (ongewijzigd). Voor de
  productie-marker bestaat nog geen "dichtstbijzijnde zone"-equivalent — dat
  wordt een nieuwe, kleine `find_nearest_zone`-functie, naar hetzelfde
  patroon (Shapely-afstand tot de zone-geometrie). De zone-geometrieën zijn al
  via een bestaand endpoint op te halen: `/collections/zones/items?areaId=
  …&mode=…` (zelfde patroon als `load_network_features` voor
  `/collections/network/items`, zie `apiUrl()`/`mkUrl()` in `scripts/main.js`
  regel 2152-2156).

Dit maakt het script ook structureel anders: van "één gebeurtenis, dan
stoppen" naar "doorlopend volgen van alle drie de objectmarkers, live
bijwerken welke bewerkingen actief zijn". Een marker weghalen van de
maquette maakt zijn bewerking ongedaan (nieuwe berekening zonder die entry
in de `changes`-set) — voor alle drie de typen (afsluiting gaat open,
snelheid terug naar origineel, productie terug naar origineel).

Naamgeving: de app kent al "markers 1-4" voor de vier punten die de beamer
projecteert tijdens **calibratie** (homografie, `maquette-calibration.js`).
Om verwarring te voorkomen heten de nieuwe fysieke ArUco-tags in code/docs
**"objectmarkers"**.

## Stappen

- [x] **Stap 1 — Detectielaag (`kien-camera-maquette/detection.py` + `config.py`)**
  Vervang `BlackObjectDetector`/`_build_dark_mask`/`analyze_black_object_contours`
  door een ArUco-detector (`cv2.aruco.ArucoDetector`, `DICT_4X4_50`). Per
  marker: `corners` (al TL/TR/BR/BL geordend), `marker_id`, `center`,
  `bbox`, `area`; `conf` vast op 1.0. Detecties met een onbekend `marker_id`
  (niet in de actie-tabel, zie stap 3) worden afgewezen als
  `unknown_marker_id`. Hergebruik `polygon_coverage_in_detection_area` en de
  min/max-oppervlaktefilters. `config.py`: HSV/contrast-drempels eruit,
  `ARUCO_DICTIONARY`-constante erin; `ROI_MIN_BLOCK_COVERAGE`/`STABILITY_*`
  blijven. Vooraf verifiëren:
  `python -c "import cv2; cv2.aruco.getPredefinedDictionary"` werkt met de
  gepinde `opencv-python==4.13.0.92` (anders overstappen op
  `opencv-contrib-python`).

- [x] **Stap 2 — Tracking (`kien-camera-maquette/tracking.py`)**
  `DetectionTracker.match_detection` matcht op `marker_id` (exact) i.p.v.
  dichtstbijzijnde centrum — marker-ID is zowel bewerkingssleutel als
  track-identiteit (elk type maar één keer tegelijk actief). Afstandsmatching
  alleen als fallback. Stabiliteits-/EMA-logica blijft ongewijzigd.

- [x] **Stap 3 — Actie-tabel (`digital-twin/aruco_marker_actions.py`, nieuw)**
  Eén centrale tabel, single source of truth voor zowel runtime-gedrag als
  het printvel:
  ```python
  MARKER_ACTIONS = {
      0: {"label": "Wegvak afsluiten", "action": "close_link"},
      1: {"label": "30 km/u",          "action": "set_speed",      "params": {"speed": 30}},
      2: {"label": "+100 productie",   "action": "add_production", "params": {"delta": "+100"}},
  }
  ```

- [x] **Stap 4 — Orchestratie (`maquette_camera.py`)**
  Grootste gedragswijziging: van single-shot ("eerste stabiele detectie →
  één aanpassing → proces stopt") naar een doorlopende lus die per
  stabiele, binnen-de-projectie-liggende marker de action/params uit
  `MARKER_ACTIONS` opzoekt, het doel bepaalt (`find_nearest_link` voor
  `close_link`/`set_speed`, nieuwe `find_nearest_zone` voor
  `add_production`) en een `desired: dict[marker_id, change_dict]`
  bijhoudt. Bij wijziging t.o.v. de laatst ingediende set, en alleen als er
  geen job loopt, wordt de **volledige** actuele set als één `changes`-array
  ingediend vanaf het vaste basis-`area_id` (zelfde patroon als `main.js`'s
  `pendingChanges`). Marker weg → bewerking ongedaan bij eerstvolgende
  indiening. Wijziging tijdens een lopende job → onthouden ("dirty") en na
  afloop opnieuw indienen. `return` die het proces beëindigt (±regel 1271)
  verwijderen; stoppen blijft via Ctrl+C. `_log_rejections`/
  `_is_reportable_rejection` omzetten naar ArUco-eigen afwijsredenen.
  `_AdjustRunner.trigger()` neemt voortaan de volledige `changes`-array.
  SSE-payload (`_send_detections`/`_detection_report`) krijgt `marker_id` +
  `label` erbij.

- [x] **Stap 5 — Marker-generator (`digital-twin/generate_aruco_markers.py`, nieuw)**
  CLI-script (stijl van `sumo/export_to_sumo.py`) dat `MARKER_ACTIONS`
  uitleest en per marker-ID een PNG genereert (`cv2.aruco.generateImageMarker`,
  witte rustzone) plus één gecombineerd PDF-vel op echte mm-schaal met het
  `label` als bijschrift. Opties: `--dict`, `--size-mm`, `--out-dir`. Nieuwe
  dependency **Pillow** in `requirements.txt`.

- [x] **Stap 6 — Documentatie (`digital-twin/README.md`, module-docstring `maquette_camera.py`)**
  Blokje/contrast-taal vervangen door ArUco-taal; nieuwe sectie
  "Objectmarkers" met de drie bewerkingen, gebruik van het generator-script,
  en montagetips. Docstring van `maquette_camera.py` bijwerken.

- [x] **Stap 7 — Tests (`digital-twin/tests/test_aruco_detection.py`, nieuw)**
  Synthetische frames met gegenereerde markers: juiste
  `marker_id`/`polygon`/`center`; onbekend ID → `unknown_marker_id`;
  coverage/oppervlak-afwijzingen. Unit-test voor de drie
  `MARKER_ACTIONS`-takken in `maquette_camera.py` (`add_production` met
  gemockte zone-lookup). Bestaande `test_maquette_calibration.py` blijft
  ongewijzigd.

- [x] **Stap 8 — Kleine UI-toevoeging (`scripts/main.js` / `maquette-monitor.js`)**
  Label uit `MARKER_ACTIONS` tonen bij elk rood kader, zodat op de kaart
  zichtbaar is welke bewerking actief is.

## Kritieke bestanden

- `digital-twin/kien-camera-maquette/detection.py`
- `digital-twin/kien-camera-maquette/config.py`
- `digital-twin/kien-camera-maquette/tracking.py`
- `digital-twin/aruco_marker_actions.py` (nieuw)
- `digital-twin/maquette_camera.py`
- `digital-twin/generate_aruco_markers.py` (nieuw)
- `digital-twin/requirements.txt`
- `digital-twin/README.md`
- `digital-twin/tests/test_aruco_detection.py` (nieuw)
- `digital-twin/scripts/main.js` / `maquette-monitor.js`

## Verificatie (per stap relevant, eindcontrole aan het einde)

1. `python -c "import cv2; print(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))"`
2. `pytest digital-twin/tests/`
3. `python digital-twin/generate_aruco_markers.py --out-dir <tmp>` → drie
   PNG's + één PDF op schaal, met de juiste labels.
4. End-to-end: calibreren zoals gebruikelijk, de drie objectmarkers één voor
   één (en in combinatie) op de maquette leggen, bevestigen dat elk zijn
   eigen bewerking + label toont en de resulterende `changes` correct zijn.
   Eén marker weghalen → precies die bewerking wordt ongedaan gemaakt, de
   andere blijven staan.
5. Bij twijfel over rendering in `maquette-monitor.js`: headless Chrome +
   CDP tegen de server op :5001.
