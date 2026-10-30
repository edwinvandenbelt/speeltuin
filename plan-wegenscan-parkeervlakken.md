# Plan: parkeervlakken (TRAFFIC-ASSETS) in de Wegenscan

## Context

Na `plan-wegenscan-netwerkdata.md` is de grootste resterende aanname in de Wegenscan
"parkeren op de rijbaan". Die trekt 2 m af van de rijbaanbreedte. In Goor hangen
626 van de 1004 links met rijbaanbreedte SLECHT af van die aanname. OSM
`parking:<side>` dekt maar 2% van de links.

TRAFFIC-ASSETS bevat `parkingArea`-polygonen (BGT via PDOK, OSM als aanvulling).
Daaruit is af te leiden of een link parkeervakken langs zich heeft, en hoe breed
die zijn: breder dan 3,5 m is haaksparkeren, smaller langsparkeren. Dat is
dezelfde regel als `add_parking.derive_parking`. Hetzelfde bestand levert ook
`speedBump` en `pedestrianCrossing`, die nu op 0% dekking staan.

## Stappen

### Stap 1: TRAFFIC-ASSETS maken voor Goor (Ouderkerk op verzoek weggelaten)
- [x] Prepare draaien in `only_dt`-modus met `fetch_parking_areas`,
  `fetch_bgt_assets` en `fetch_osm_assets` aan, en buildings/vegetatie uit.
  Script: `make_assets.py` in de scratchpad.
- [x] Vooraf een back-up van het NETWORK-bestand maken, omdat `only_dt` het
  netwerk herschrijft (de road-enricher draait opnieuw mee).
- [x] Controleren hoeveel `parkingArea`, `speedBump` en `pedestrianCrossing` er
  zijn, en of het netwerk zijn kolommen heeft behouden.
- Let op: de server-job "Full digital twin" zet `fetch_parking_areas` niet aan,
  dus die job levert geen parkeervlakken op.

### Stap 2: Koppeling parkeervlak → link (`analyzer/wegenscan_assets.py`)
- [x] Per link alle `parkingArea`-polygonen binnen een paar meter van de
  lijn zoeken (spatial index, metrisch CRS).
- [x] Diepte van een vak gemeten loodrecht op de link, niet als korte zijde:
  een los haaks vak van 2,5 × 5 m zou anders als langs tellen. Daarna de regel
  van `derive_parking` (> 3,5 m haaks, anders langs).
- [x] Bron `assets:parkingArea`. Een vak dat alleen een kruising raakt, telt niet.
  Daarvoor geldt een minimale overlap langs de link.
- [x] Tests met synthetische polygonen.

### Stap 3: Drempels en oversteekplaatsen uit dezelfde assets
- [x] `speedBump` binnen een paar meter van de link → `speed_bumps = "op wegvakken"`.
- [x] ~~`pedestrianCrossing` uit assets~~: niet nodig, want prepare vult `numPedestrianCrossings` in het netwerk nu zelf (7 links in Goor), en dat wordt al gebruikt.

### Stap 4: Server en pipeline
- [x] `_run_wegenscan_job` laadt TRAFFIC-ASSETS (met base-fallback, zoals de
  `traffic_assets`-collectie) en geeft het mee aan `run_pipeline`.
- [x] Zonder assets-bestand gedraagt alles zich zoals nu.
- [x] Frontend: bronlabel "assets" (BGT/OSM) naast netwerk/NWB/aanname.

### Stap 5: Herberekenen en vergelijken
- [x] Goor opnieuw draaien, en de rijbaanbreedte en het totaaloordeel
  vergelijken met de huidige uitvoer.

## Bevindingen

- **Stap 1:**
  - Prepare `only_dt` voor Goor duurde ~20 min, waarvan ~17 min PDOK-parkeervlakken.
  - Resultaat: 1333 parkeervlakken (1311 uit de BGT, 22 uit OSM) en 94 BGT-drempels.
  - Het netwerk is intact gebleven: 1734 links, geen kolommen kwijt, flows identiek. Er zijn kolommen bijgekomen (o.a. `numCycleCrossings`, POI-oppervlakken), en `numPedestrianCrossings` is nu gevuld.
  - De back-up van het netwerk staat in de scratchpad (`backup/Goor/`).
  - De assets beslaan de studiegebied-bbox uit de metadata, dus niet de randwegen. Dat is dezelfde conventie als bij De Kien.
- **BGT-historie:**
  - 593 van de 1311 BGT-parkeervlakken en 21 van de 94 drempels zijn vervangen versies (`eind_registratie` gezet). `wegenscan_assets._active` filtert die eruit en ontdubbelt per `lokaal_id`.
  - Waarschijnlijk toont de `traffic_assets`-kaartlaag die historische objecten nu ook. Niet onderzocht.
- **Koppeling:**
  - Een vak telt als de rand binnen halve wegbreedte + 2,5 m van de as ligt en het minstens min(15 m, 30% van de link) langs de link dekt.
  - De diepte wordt loodrecht op de weg gemeten: > 3,5 m is haaksparkeren, > 8 m is een terrein en telt niet mee.
  - Drempels binnen 15 m van een eindpunt liggen 'op kruispunten'.
  - Binnen de assets-bbox is "geen BGT-drempel" een waarneming (`assets:speedBump (geen)`), maar alleen als het bestand BGT-objecten bevat.
- **Resultaat Goor:**
  - Parkeren uit data: van 2% naar 22% (371 links: 220 langs, 151 haaks). Drempels uit data: van 0% naar 48%.
  - Totaaloordeel van GOED 43% / REDELIJK 41% / MATIG 16% naar GOED 50% / REDELIJK 36% / MATIG 14%. 153 links (9%) veranderen, vooral REDELIJK → GOED.
  - Rijbaanbreedte SLECHT van 58% naar 48%. Van de 371 links met BGT-parkeren gaan er 150 van SLECHT naar GOED.
- **Server:**
  - `_wegenscan_assets()` laadt TRAFFIC-ASSETS (met base-fallback), filtert op `parkingArea`/`speedBump` en geeft ze mee aan `run_pipeline(assets=…)`.
  - Frontend: nieuw bronlabel "BGT/OSM" (paars), en bij parkeren de vakdiepte.
- **Testen:**
  - Getest op een eigen serverinstantie (poort 5055), want de server op 5000 reageerde niet meer. Daar luisteren twee processen (PID 32712 en 31124) en één werkproces gebruikt continu 100% CPU.
  - De Goor-uitvoer in `work/` is via 5055 opnieuw berekend.
- **Tests:** `tests/test_wegenscan_assets.py` (9 tests). In totaal slagen 54 wegenscan-tests.

### Nastap: "Full digital twin"-job (`fetch_osm`) gerepareerd
- [x] De job gaf de verplichte `refresh`/`debug` niet mee aan `run_pipeline()` en faalde dus altijd met een TypeError. Gecontroleerd door de oude en nieuwe aanroep te binden tegen de echte signatuur.
- [x] Alle digital-twin-bronnen staan nu standaard aan, net als bij een nieuwe prepare: verkeerslichten, borden, BGT, OSM-objecten, **parkeervlakken** en vegetatie. Per bron is uitzetten mogelijk met dezelfde invoernamen als de wizard (`parking`, `bgtAssets`, …). Daarnaast worden `fetch_buildings=True` en `ndw_data_uri` meegegeven.
- Niet live gedraaid: een run duurt ~20 min per gebied (zie stap 1).

## Werkwijze
Stap voor stap. Na elke stap stoppen voor akkoord.
