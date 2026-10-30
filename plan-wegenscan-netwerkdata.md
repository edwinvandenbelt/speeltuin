# Plan: Wegenscan (Veiligheid) op bestaande netwerkdata laten draaien

## Context

De Veiligheid-scan (Wegenscan, `wegenscan-2.1.0` wheel, gewrapt door
`analyzer/wegenscan_pipeline.py`) haalt in `enrich_features()` zelf zes attributen
op via live Databricks-SQL (snelheid/s85, wegcategorie, profiel/fietsvoorziening,
voetgangers, parkeren, drempels), gejoind op `spectrumId == wvk_id`.

Problemen:
- **Overlap**: de prepare/PBF-pipeline heeft het meeste al in de NETWORK-parquet:
  `surface`, `roadWidthM/Min/Max`, `osmWidth`, `speedLimit`, `osmMaxspeed`,
  `osmHighway`, `cyclewayLeft/Right`, `sidewalkLeft/Right`, `parkingLeft/Right`,
  `busway`, `numSpeedBumps`, `numPedestrianCrossings`, `numRefugeAreas`, `lit`,
  `osmLanes`, `osmOneway`, `wvkIds`.
- **Het werkt nu feitelijk niet**: in alle 7 `work/**/*-WEGENSCAN-*.geojson` staan
  `max_speed=-1`, `wegcat_number=None`, `speed_bumps="niet aanwezig"`, dus alle
  Databricks-lookups vielen terug op defaults.
- **Bug**: `build_invoer` leest `props["width"]`, maar die kolom bestaat niet, dus
  elke weg krijgt 6,0 m. Dat raakt rijstrookbreedte, rijbaanbreedte, bermschade en
  de fiets-KPI's.
- **Twee classificaties voor wegdek**: `translate_surface` (substring, `paved` en
  `unpaved` worden allebei "open") wijkt af van `MontrealBasemap.surfaceClass`
  (`common/js/montreal-basemap.js:164-178`), die de Wegprofiel-laag gebruikt.

Doel: de KPI-engine van het wheel blijft ongewijzigd, maar haalt zijn invoer uit
de NETWORK-attributen die de app al heeft. Elke invoer krijgt een zichtbare bron
(netwerk of default). Databricks wordt optioneel.

## Aanpak

De KPI-functies (`build_invoer`, `calculate_kpis`, `calculate_generic_safety`)
blijven zoals ze zijn. Het wheel passen we niet aan. Vóór `build_invoer` komt een
**adapterlaag** in de speeltuin die NETWORK-kolommen vertaalt naar de
property-namen en waardedomeinen van Wegenscan.

### Stap 1: Mappingmodule `analyzer/wegenscan_inputs.py` (nieuw)
- [x] Per Wegenscan-veld één pure functie `props -> (waarde, bron)`:
  - `width`: gemiddelde van `roadWidthMinM`/`MaxM`, anders `roadWidthM × 2`,
    anders `osmWidth`, anders geen waarde. Dezelfde regel als `_designWidthM`
    (`analyzer/index.html:~4936`), zodat de kaart en de score dezelfde breedte
    gebruiken.
  - `max_speed` / `max_speed_s85`: `speedLimit`, dan `osmMaxspeed`. Voor s85 is
    er geen bron, dus die gelijk aan de limiet zetten en bron = "limiet".
  - `road_category`: afgeleid uit `osmHighway` + snelheid (bijvoorbeeld
    residential/living_street + 30 → "ETW 30 km/h", primary/secondary + 50 →
    "GOW 50 km/h", buiten de kom op snelheid). De categorie-strings komen uit de
    tabel van `derive_road_category`, en de functie wordt waar mogelijk
    hergebruikt (`add_road_category.derive_road_category(wegcat, max_speed)`).
  - `surface`: één canonieke classificatie (asfalt, klinkers, beton, halfverhard,
    onverhard, onbekend), gelijk aan `_SURFACE_CLASS` in montreal-basemap.js.
    Daarna vertaald naar de drie Wegenscan-waarden (gesloten / open /
    gedeeltelijk open). Deze waarde zetten we direct als `r_surface`, zodat de
    foutieve substring-match van `translate_surface` wordt omzeild.
  - `bicycle_location` / `profile`: uit `cyclewayLeft/Right` (track →
    vrijliggend, lane → fietsstrook, shared_lane/no → op de rijbaan) en
    `osmOneway`/`osmLanes`.
  - `pedestrian_location`: uit `sidewalkLeft/Right`.
  - `pedestrian_crossing`: uit `numPedestrianCrossings` en `numRefugeAreas`.
  - `parking_location`: uit `parkingLeft/Right`.
  - `speed_bumps`: `numSpeedBumps > 0` → "aanwezig".
  - `bus_facility`: uit `busway`.
- [x] Een `enrich_from_network(features)` die de velden zet, en per feature een
  `wegenscan_sources`-dict met per veld `"netwerk:<kolom>"` of `"default"`.
- [x] Unit-tests in `tests/test_wegenscan_inputs.py` (bestaande testmap), met als
  minimumcases `paved`, `unpaved`, `asphalt;paved`, ontbrekende breedte en
  cycleway=track.

> Voor de exacte waardedomeinen (de strings in `DEFAULTS`,
> `.venv/Lib/site-packages/wegenscan.py:84-105`, en de lookup-tabellen in
> `core/functie_vorm.py` en `core/vorm_gebruik.py`) eerst de wheel-code lezen.
> Alleen waarden gebruiken die daar voorkomen, anders levert de KPI-functie stil
> ONBEKEND op.

**Afwijkingen / bevindingen stap 1**
- `busway` niet gebruikt: dat is een busstrook, geen halte-voorziening (`bus_facility` kent alleen halteren op rijbaan / haltehaven / n.v.t.).
- `numSpeedBumps`, `numPedestrianCrossings` en `numRefugeAreas` staan in Goor overal op 0; 0 telt daarom als "onbekend" (default), alleen > 0 als netwerkwaarde.
- `build_invoer` leest `surface` zelf; daarom `build_invoer_from_network()` die `r_surface` overschrijft.
- Bestaande bug: `surface` = NaN (parquet) laat `translate_surface` crashen, waardoor 327/1734 Goor-links NVT kregen. Wordt nu afgevangen.
- `derive_road_category` levert ook strings die niet in de KPI-tabellen staan (`ETW 15 km/h (erf)`, `geen categorie,50 km/uur`, `none`). Die worden gealiast of op None gezet.
- Proefrun Goor (1734 links): dekking categorie/snelheid/breedte/profiel 100%, wegdek 81%, fiets 39%, voetganger 40%, parkeren 2%, drempels 0%. 0 fouten, 0 ONBEKEND.

### Stap 2: Pipeline omzetten (`analyzer/wegenscan_pipeline.py`)
- [x] `run_pipeline(geojson, id_field, use_databricks=False)`. Standaard alleen
  `enrich_from_network`.
- [x] Met `use_databricks=True` mogen de bestaande `_enrich_*`-stappen alleen
  velden overschrijven waarvoor het netwerk geen waarde had (de bron is dan
  "default"). Databricks wordt daarmee een aanvulling, geen hoofdbron.
- [x] Bij Databricks liever joinen op `wvkIds` (spatiale WKD-match, al in
  NETWORK) dan op de aanname `spectrumId == wvk_id`. Bij meerdere ids per link
  het meest restrictieve of het meerderheidsresultaat nemen.
- [x] `_enrich_defaults` blijft voor markeringen, scheiding en sociale
  interactie, want daarvoor is geen bron.
- [x] Docstring bovenaan bijwerken.

**Afwijkingen / bevindingen stap 2**
- De `_enrich_*`-stappen zijn vervangen door `_query_lookups` (alleen lookups, geen defaults) + `_supplement_from_databricks`. Een mislukte query verandert daardoor niets meer; voorheen werd `max_speed=-1` gezet.
- Databricks-modules worden lazy geïmporteerd; zonder `use_databricks` wordt er geen verbinding gemaakt.
- `max_speed_s85` wordt altijd uit Databricks overgenomen als die er is (het netwerk heeft alleen de limiet).
- Join: meerderheidswaarde over `wvkIds` (JSON-string in parquet, of een lijst), met `spectrumId` als terugval.
- Autosnelweg/autoweg (`osmHighway` motorway/trunk) → `generic_safety` NVT, buiten scope.
- **Bestaande bug gevonden:** `run_pipeline` muteerde de features in-place, terwijl `_read_geodata` de FeatureCollection cachet. Daardoor kwamen wegenscan-velden in de gecachte `/collections/network`-data. De pipeline werkt nu op kopieën.
- De output-FeatureCollection krijgt `wegenscan_coverage` (dekking per veld in %) voor stap 3/4.
- Tests: `tests/test_wegenscan_pipeline.py` (Databricks gemockt). Goor eind-tot-eind: 1734/1734 links berekend, in beide modi.

### Stap 3: Server (`analyzer/server.py`)
- [x] `_execute_wegenscan` / `_run_wegenscan_job` (`:2831-2871`, `:3813-3846`):
  - optionele procesparameter `useDatabricks` (standaard false) toevoegen aan de
    procesbeschrijving (`:1187-1215`);
  - de Databricks-import niet meer verplicht laten zijn voor
    `_WEGENSCAN_AVAILABLE` (`:446-453`).
- [x] Oudere gebieden zonder road-enricher-kolommen (Deventer - geheel, Aalten)
  draaien wel, maar met veel defaults. Het job-resultaat logt per veld de
  dekking (bijvoorbeeld "breedte 94%, wegdek 61%, …").

**Afwijkingen / bevindingen stap 3**
- `useDatabricks` (boolean, standaard false; ook "true"/"ja" als string) gaat door naar `run_pipeline`. De procesbeschrijving is bijgewerkt en heeft een extra output `coverage`.
- Job-resultaat (`/jobs/<id>/results`) bevat `coverage`. In `/collections/wegenscan/items` staat die onder `properties.wegenscan_coverage`, via de bestaande merge van top-level keys in `_ogc_items_response`.
- Databricks-*credentials* zijn niet meer nodig. Het *package* `databricks-sql-connector` blijft wel een importvereiste, omdat `derive_road_category` uit `add_road_category` komt en die module `db` importeert. Het staat in requirements.txt, dus dat laat ik zo.
- Gebieden zonder road-enricher-kolommen geven een waarschuwing in de log. Aalten: dekking alleen snelheid en breedte 100%, de rest 0%.
- Live getest op de draaiende server (127.0.0.1:5000): Goor-job geslaagd (1734/1734). `/collections/network/items` bevat daarna geen wegenscan-velden meer (cache-vervuiling opgelost).
- De oude Goor-output is in de scratchpad bewaard voor de vergelijking in stap 5; `work/Goor/…-WEGENSCAN-CAR.geojson` is nu overschreven door de nieuwe run.

### Stap 4: Frontend (`analyzer/index.html`, Veiligheid-subpanel `:8132-8288`)
- [x] In het zijpaneel per link de invoerwaarden tonen, met de bron
  (netwerk/default) gemarkeerd. Zo is te zien waaróm een score MATIG is.
- [x] In de banner de dekkingspercentages uit stap 3 tonen.
- [x] De wegdekklasse in het zijpaneel moet dezelfde zijn als die in de
  Inrichting → Wegprofiel-laag.
- [x] De oude kopie in `digital-twin/index.html` laten we buiten scope.

**Afwijkingen / bevindingen stap 4**
- De pipeline slaat per link `wegenscan_invoer` op (de echte invoer incl. defaults). Daardoor kan het paneel ook aannames tonen, niet alleen netwerkwaarden.
- Zijpaneel: blok "Invoer" boven de KPI's, per veld de waarde en een bronlabel: netwerk (teal), NWB (blauw), aanname (oranje), geen bron (grijs). De tooltip toont de precieze kolom. Bij wegdek ook de kaartklasse en de ruwe OSM-waarde, bijvoorbeeld "Klinkers (paving_stones) → open (o.a.klinkers)". Een snelheid uit de limiet krijgt "(limiet)".
- Dekking staat niet in de banner (die is alleen zichtbaar zonder data) maar als regel onder "Totaal" in het Veiligheid-blok, met een link "Opnieuw berekenen".
- Oude runs zonder bronnen tonen "Berekend met een oudere versie…" met dezelfde link. De run-knop is een herbruikbare `runWegenscan()`; na afloop wordt de knop weer ingeschakeld en het zijpaneel gesloten.
- `flow` heeft nu ook een bron (`netwerk:flow`).
- Vertalingen NL/EN/FI toegevoegd (`ws*`-keys).
- Gecontroleerd met Playwright en Chrome (headless) op 127.0.0.1:5000. Oude-run-melding, rerun via de link, nieuwe dekking en zijpaneel werken. Geen JS-fouten.

### Stap 5: Herberekenen en vergelijken
- [x] De Wegenscan opnieuw draaien voor Goor en Ouderkerk aan de Amstel
  (De Kien bleek géén road-enricher-kolommen te hebben; zie hieronder). De verdeling van `generic_safety` en van een paar
  KPI's (`r_lane_width`, `r_road_surface`, `r_bicycle_facility`) vergelijken met
  de oude output.
- [x] De oude `WEGENSCAN-*.geojson` niet wissen maar overschrijven via een
  nieuwe run (zie memory over work/-data).

**Afwijkingen / bevindingen stap 5**
- Alleen **Goor** heeft de volledige road-enricher-kolommen. De Kien heeft ze niet en ook geen breedtes. Als tweede gebied is daarom **Ouderkerk aan de Amstel** gekozen: alleen breedtes en snelheid, en wel een oude scan om mee te vergelijken.
- **Bug in wegenscan 2.1.0** gevonden: `VormGebruik.get_bermschade_waarden` gaf een NameError bij een breedte boven 20 m. Dit is opgevangen met een gedocumenteerde patch in `wegenscan_pipeline.py`, plus een test.
- **Twee verslechteringen uit stap 2 hersteld:**
  - Zonder `osmHighway` werd de categorie "ETW 15 km/h" (de default van het pakket); de oude pipeline gebruikte ETW 30. Nu wordt de categorie afgeleid uit alleen de snelheid, met bron `netwerk:speedLimit (zonder wegtype)`.
  - De parkeer-vuistregels van het pakket (`derive_parking_from_*`) vielen weg. Ze zijn terug, met bron `aanname:vuistregel`; die telt niet mee in de dekking en Databricks mag hem overschrijven.
- **Resultaat Goor** (1726 links):
  - Totaaloordeel oud: GOED 81% / REDELIJK 17% / MATIG 3%. Nieuw: GOED 43% / REDELIJK 41% / MATIG 16%. Bij 50% van de links verandert het oordeel.
  - Breedte: oud overal 6,0 m, nu 1,9–11,4 m (mediaan 4,7).
  - Rijstrookbreedte: van 100% MATIG naar 34% GOED / 61% MATIG / 5% SLECHT.
  - Wegdek: van 44% naar 68% GOED.
  - Fietsfaciliteit wordt nu voor 39% beoordeeld (was overal NVT).
- **Resultaat Ouderkerk** (7149 links): totaaloordeel oud GOED 77% / REDELIJK 16% / MATIG 7%, nieuw GOED 23% / REDELIJK 61% / MATIG 15%.
- **Open punt, de grootste resterende aanname:** "parkeren op de rijbaan" (−2 m in rijbaanbreedte).
  - In Goor zijn 626 van de 1004 links met rijbaanbreedte SLECHT afhankelijk van die aanname; zonder die aanname zouden er 421 GOED zijn.
  - OSM-parkeerdata dekt maar 2%. Mogelijke bron: `parkingArea` uit TRAFFIC-ASSETS (BGT+OSM).
- De oude uitvoer (vóór dit plan) van Goor en Ouderkerk staat in de scratchpad (`oud/`).

## Bestanden
- nieuw: `analyzer/wegenscan_inputs.py` en `analyzer/tests/test_wegenscan_inputs.py`
- wijzigen: `analyzer/wegenscan_pipeline.py`, `analyzer/server.py`,
  `analyzer/index.html`
- hergebruik:
  - `derive_road_category` (wheel `add_road_category`)
  - `build_invoer` / `calculate_kpis` (wheel `wegenscan`)
  - de breedteregel van `_designWidthM` en de wegdekklassen van
    `MontrealBasemap.surfaceClass`, ook in Python, met een opmerking die naar de
    JS-bron verwijst

## Verificatie
1. `pytest analyzer/tests/test_wegenscan_inputs.py`.
2. De server starten en via `http://127.0.0.1:...` (niet localhost) de wegenscan
   uitvoeren voor Goor, zonder Databricks-env vars. De job moet slagen.
3. In de output controleren dat `width` per link varieert, dat `max_speed` ≠ -1
   waar `speedLimit` bekend is, en dat `wegenscan_sources` gevuld is.
4. In de analyzer bij Netwerk → Veiligheid de KPI-kleuring en het zijpaneel met
   bronnen bekijken, en het wegdek naast de Wegprofiel-laag leggen.

## Werkwijze
Bij uitvoering kopieer ik dit plan naar `plan-wegenscan-netwerkdata.md` in de
repo-root. Ik werk het stap voor stap af en stop na elke stap voor akkoord.
