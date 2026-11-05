# Plan: wegvakken bewerken (digital twin + analyzer)

## Situatie

- **"Aanpassingen"** (paneel in beide apps) is een what-if: je wijzigt capaciteit, snelheid of flow van een link,
  of tekent een nieuwe link. "Doorvoeren" doet `POST /processes/adjust/execution` (`_execute_adjust`,
  `digital-twin/server.py:2649`). Dat maakt **altijd een nieuw scenario** (map met `.src-area-id` +
  `<id>-changes.json`) en rekent het verkeer opnieuw door (`adjust.core.adjust_core.run_pipeline`).
  Een wegvak afsluiten gaat nu via `capacity: 0`.
- Wat `adjust` begrijpt (`adjust_core.py` `_split_changes` :138, `apply_link_adjustments` :291): alleen
  `capacity` óf `speed`, en `flow`. Rijstroken, stoep, fietsstrook, breedte en verharding kan niemand wijzigen.
- Een wegvak is een **gerichte link** in `<id>-NETWORK-<MODE>.parquet` (LineString). De andere rijrichting is een
  aparte rij, te vinden via **`reverseLinkIds`** (meestal `[-linkId]`). Let op: `oppositeLinkId` is níet de
  tegenrichting, maar een andere link die op dezelfde knoop uitkomt (zie stap 0). Relevante kolommen:

  | groep        | kolommen                                                                          |
  |--------------|-----------------------------------------------------------------------------------|
  | profiel      | `sidewalkLeft/Right`, `cyclewayLeft/Right`, `parkingLeft/Right`, `busway`          |
  | weg          | `surface`, `smoothness`, `lit`, `roadWidthM`, `roadWidthMinM/MaxM`, `osmName`      |
  | verkeer      | `lanes`, `osmLanesInDirection`, `capacity`, `speed`, `speedLimit`, `length`        |
  | topologie    | `linkId`, `fromNode`, `toNode`, `oppositeLinkId`, `reverseLinkIds`, `parallelLinkIds` |

  Links/rechts is relatief aan de tekenrichting van de link. Voor de tegenrichting zijn ze dus gespiegeld.
  `linkId` is **niet uniek**: de zone-joiner knipt links op zonegrenzen en geeft beide delen hetzelfde `linkId`
  (knopen `<linkId>_<k>_in` / `_out`). Een bewerking op een `linkId` raakt dus alle rijen met dat id.
- Weergave: het wegprofiel komt op "Kaart"/"Kaart 2" via `MontrealBasemap.setNetwork()`
  (`common/js/montreal-basemap.js:642`, `_matchRoad` :396, `_netWidthM` :299). Na "Doorvoeren" roept
  `loadAdjustedResult` (`digital-twin/index.html:18414`) `setNetwork` **niet** opnieuw aan.
- Er is al een link-selectie (`makeLinkEditLayer` `index.html:14429`, klik via `map.on('click')` :16184,
  `hoveredLinkId`) en een lijst met wachtende wijzigingen (`pendingChanges` :16128). Er is geen undo.
- Beide servers (`analyzer/server.py`, `digital-twin/server.py`) hebben grotendeels dubbele code. Gedeelde code
  staat in `common/js/` en `common/py/`.
- **Wegenscan** (wheel `wegenscan-2.1.0`, `build_invoer` + `calculate_kpis`): 21 veiligheids-KPI's per segment.
  - Elke invoer is één waarde per dwarsdoorsnede. De wheel kent geen zijden en geen richting.
  - Alleen de analyzer roept hem aan: `_run_wegenscan_job` (`analyzer/server.py:2769`) →
    `analyzer/wegenscan_pipeline.run_pipeline`. Uitvoer gaat naar `{area}-WEGENSCAN-{mode}.geojson`.
  - De DT-front-end roept `/processes/wegenscan/execution` (`digital-twin/index.html:20037`) en
    `/collections/wegenscan/items` (:12200) aan, maar de DT-server kent die niet: de knop werkt daar niet.
  - De invoer komt nu uit vier bronnen tegelijk, bij **elke run** opnieuw afgeleid:
    1. NETWORK-kolommen via de adapter `analyzer/wegenscan_inputs.py` (`derive_inputs` :301);
    2. TRAFFIC-ASSETS `parkingArea`/`speedBump`, run-time gekoppeld (`analyzer/wegenscan_assets.py`). Dit gaat vóór
       `parkingLeft/Right` (`wegenscan_inputs.py:247`);
    3. optioneel Databricks (NWB/WKD), voor `max_speed_s85`, wegcategorie, profiel, parkeren en drempels;
    4. vaste defaults.
  - De pipeline scoort **elke gerichte rij apart**:
    - zijden worden samengevoegd met "een van beide" (`_sides` :114);
    - `flow` is de flow in één richting, terwijl de wheel etmaalintensiteit over de doorsnede verwacht;
    - de twee richtingen van één weg scoren daardoor soms verschillend: Hasselt 504 van 2.999 paren, Deventer_SND
      122 van 5.662;
    - de front-end gebruikt `linkId` als sleutel (`analyzer/index.html:8217`), dus zone-joiner-delen overschrijven
      elkaar.

## Aanpak

**Wegvakbewerking is iets anders dan Aanpassingen.** Bij Aanpassingen stel je een what-if-vraag aan het
verkeersmodel. Bij Bewerken corrigeer of ontwerp je het **netwerk zelf**. Daarom kies je in de front-end waar de
bewerking terechtkomt:

| doel                     | wat er gebeurt                                                                 |
|--------------------------|--------------------------------------------------------------------------------|
| **Dit scenario bewerken** | De NETWORK-parquet van het huidige gebied/scenario wordt in-place gepatcht.   |
| **Nieuw scenario**        | Nieuwe scenariomap (zelfde structuur als bij adjust), met de gepatchte netwerk-parquet; ROUTES/ZONE/FEEDLINK worden gekopieerd. |

### Soorten bewerkingen

**Scope (besluit 4-11-2026):** alleen klasse A. Bewerkingen waardoor routes opnieuw berekend moeten worden,
laten we voorlopig buiten beschouwing. Daaronder valt ook rijstroken: een andere capaciteit laat `adjust`
herrouteren. Klasse B en C staan hieronder alleen als achtergrond voor later.

| klasse          | bewerkingen                                                     | gevolg                                        |
|-----------------|-----------------------------------------------------------------|-----------------------------------------------|
| A. Profiel      | stoep, fietsstrook/-pad, parkeren, busbaan per zijde; verharding, verlichting, breedte, naam; alle wegenscan-kolommen (zie hieronder) | Alleen patchen, plus wegenscan herberekenen. Geen verkeersberekening. |
| B. Rijstroken *(later)* | `lanes` / `osmLanesInDirection` per richting                     | Capaciteit = `adjust_core._capacity_for_speed(speed, lanes)` (snelheidstabel × rijstroken, :261). Flows blijven staan. Optioneel daarna "verkeer herberekenen". |
| C. Topologie *(later)*  | wegvak verwijderen, wegvak opknippen, vertices verplaatsen       | `length` opnieuw berekenen. Verwijderen = eerst de bestaande adjust-afsluiting (`capacity: 0` op link + tegenrichting; adjust splitst omleidingen in of herrouteert, `_redistribute_routes` :1200), daarna de rijen uit NETWORK halen. Opknippen: `linkId` behouden (zoals de zone-joiner) en de nieuwe knoop in `nodePath` van ROUTES invoegen. |

Klasse A is synchroon: één request, < 1 s, geen job. ROUTES, ZONE en FEEDLINK blijven ongewijzigd.
Velden die het verkeer raken (`lanes`, `capacity`, `speed`, `length`, geometrie, topologie) weigert de server
met 400, zodat er niet per ongeluk een netwerk ontstaat dat niet meer bij de routes past.

### Wegenscan: het netwerk als enige bron (besluit 5-11-2026)

Alles wat de wegenscan nodig heeft, komt als kolom in de NETWORK-parquet. De wegenscan leest daarna **alleen** het
netwerk; TRAFFIC-ASSETS, Databricks en de vuistregels worden niet meer bij elke run geraadpleegd. Zo werkt een
bewerking van een wegvak direct door in de wegenscan. Al deze kolommen zijn profiel-attributen (klasse A): ze raken
het verkeersmodel niet.

**Kolommen.** Soort "weg": in **beide** gerichte rijen dezelfde waarde. Soort "zijde": `…Left/Right` relatief aan de
tekenrichting, gespiegeld in de tegenrichting.

| wegenscan-invoer          | NETWORK-kolom                               | soort  | nu                                                  |
|---------------------------|---------------------------------------------|--------|-----------------------------------------------------|
| `road_category`           | `roadCategory` (7 DV-waarden, bv. `GOW 50 km/h`) | weg | **nieuw**; nu afgeleid uit `osmHighway` + `speedLimit` |
| `max_speed`               | `speedLimit`                                | weg    | bestaat                                             |
| `max_speed_s85`           | `speedV85`                                  | weg    | **nieuw**; nu limiet of Databricks                  |
| `width`                   | `roadWidthTotalM`                           | weg    | **nieuw**; nu regel min/max → `roadWidthM`×2 → `osmWidth` |
| `surface`                 | `surface`                                   | weg    | bestaat                                             |
| `profile`                 | afgeleid uit `osmOneway` + `cyclewayLeft/Right` | weg | blijft afgeleid; geen eigen kolom, dan kan het niet tegenstrijdig worden |
| `flow`                    | `flow` + `flow` van de tegenrichting        | weg    | adapter telt beide richtingen op (verkeersuitkomst, niet bewerkbaar) |
| `separation`              | `separation`                                | weg    | **nieuw**; nu altijd default                        |
| `longitudinal_markings`   | `longitudinalMarkings`                      | weg    | **nieuw**; nu altijd default                        |
| `speed_bumps`             | `speedBumps` (enum)                         | weg    | **nieuw**; nu assets / `numSpeedBumps`              |
| `pedestrian_location`     | `sidewalkLeft/Right`                        | zijde  | bestaat                                             |
| `pedestrian_width`        | `sidewalkWidthLeftM/RightM`                 | zijde  | **nieuw**; nu altijd 0 → altijd SLECHT              |
| `pedestrian_crossing`     | `pedestrianCrossing` (enum)                 | weg    | **nieuw**; nu uit `numPedestrianCrossings`/`numRefugeAreas` |
| `bicycle_location`        | `cyclewayLeft/Right`, plus waarden `track_twoway` en `parallel_road` | zijde | bestaat; die twee wegenscan-waarden kunnen nu niet voorkomen |
| `bicycle_width`           | `cyclewayWidthLeftM/RightM`                 | zijde  | **nieuw**; nu altijd 0 → altijd SLECHT              |
| `bicycle_crossing`        | `bicycleCrossing` (enum)                    | weg    | **nieuw**; nu altijd default                        |
| `parking_location`        | `parkingLeft/Right` (OSM-waarden, plus `perpendicular`/`diagonal` → haaks) | zijde | bestaat (2 % gevuld); nu vooral assets en vuistregel |
| `parking_width`           | `parkingDepthLeftM/RightM`                  | zijde  | **nieuw**; nu alleen uit assets                     |
| `bus_frequency`           | `busFrequency` (enum)                       | weg    | **nieuw**; nu altijd default                        |
| `bus_facility`            | `busStopLeft/Right` (`bay`/`on_road`/leeg)  | zijde  | **nieuw**; nu altijd default                        |
| `social_interaction`      | `socialInteraction` (ja/nee)                | weg    | **nieuw**; nu altijd default                        |

- **Herkomst:** per rij één JSON-kolom `wsSources`, bv. `{"speedV85": "databricks", "parkingLeft": "assets",
  "separation": "default"}`. Een bewerking zet de bron op `"bewerkt"`. Die informatie toont de analyzer nu al als
  badges (`wsSourceBadge`); ze komt dan uit het netwerk in plaats van uit de run.
- **Domeinen** (toegestane waarden) komen uit één schema in `common/py/network_edit/schema.py`. Validatie van de
  editor en vertaling naar de wegenscan gebruiken allebei dat schema. Waar de wheel een vaste lijst heeft,
  importeren we die lijst uit de wheel (`core/functie_vorm.py`, `core/vorm_gebruik.py`).
- **Van zijden naar één doorsnede-waarde** (in de adapter, één keer voor het wegvak):
  - locatie: de beste voorziening van beide zijden (zoals nu);
  - breedte: de kleinste breedte van de zijden die die voorziening hebben (conservatief);
  - parkeren: haaks gaat vóór langs, langs vóór op de rijbaan.
- **Netwerkverrijking.** Een eenmalige stap per gebied vult de nieuwe kolommen met de afleidingen die nu bij elke
  run gebeuren: adapter-regels, assets-koppeling, optioneel Databricks. Daarna worden de rijrichtingen consistent
  gemaakt (spiegelen; bij conflict wint de rij met de meest specifieke waarde, gelogd).
  - Wordt een OGC-process `enrich-network`, met dezelfde `.orig`-back-up en `edits.json`-regel als bewerken
    (bron `"verrijking"`).
  - Geprepareerde data blijft terug te zetten.
- **Wegenscan-library-gebruik aanpassen:**
  - `analyzer/wegenscan_{inputs,assets,pipeline}.py` verhuizen naar `common/py/wegenscan_adapter/`, zodat de DT
    dezelfde code gebruikt;
  - `run_pipeline` leest alleen nog netwerkkolommen. Assets en Databricks verhuizen naar de verrijkingsstap;
  - de DT krijgt het `wegenscan`-process en de `wegenscan`-collectie, zodat de bestaande knop daar werkt;
  - er wordt **per wegvak** gescoord (een paar via `reverseLinkIds`, plus zone-joiner-delen). Beide gerichte rijen
    krijgen hetzelfde resultaat;
  - de front-end gebruikt als sleutel `linkId|fromNode` in plaats van alleen `linkId`;
  - na een bewerking herberekent het `edit-network`-endpoint de wegenscan voor de bewerkte wegvakken, als het
    WEGENSCAN-bestand bestaat. Dat is een pure functie per feature, dus snel en synchroon.
  - Gevolg: scores veranderen ten opzichte van de huidige uitvoer, vooral door de opgetelde flow en de breedtes die
    niet meer 0 zijn. Dat is bedoeld, maar wel benoemen.

### Datamodel

- Een bewerking is een JSON-object, per **wegvak** (beide rijrichtingen samen), niet per gerichte link:
  ```json
  {"op": "set", "linkId": "600855823", "side": "left", "attr": "sidewalk", "value": "separate"}
  {"op": "set", "linkId": "600855823", "attr": "surface", "value": "paving_stones"}
  {"op": "set", "linkId": "600855823", "side": "right", "attr": "cyclewayWidthM", "value": 1.8}
  {"op": "set", "linkId": "600855823", "attr": "roadCategory", "value": "GOW 50 km/h"}
  ```
  De server zoekt de tegenrichting via `reverseLinkIds` en schrijft weg-attributen in beide rijen en
  zij-attributen gespiegeld, zodat beide richtingen consistent zijn. Ontbreekt een profielkolom in het netwerk
  (oudere preparaties), dan maakt de server hem aan.
- Per gebied/scenario komt er een `<id>-edits.json`: de geordende lijst van toegepaste bewerkingen, met tijdstip.
- **Back-up bij in-place bewerken:** de eerste keer wordt `<id>-NETWORK-<MODE>.orig.parquet` bewaard.
  Geprepareerde data kan de server niet opnieuw maken (die komt uit de PBF-pipeline), dus in-place bewerken moet
  altijd terug te draaien zijn: "alle bewerkingen terugdraaien" = `.orig` terugzetten en eventueel een deel van
  `edits.json` opnieuw toepassen.
- **Gelijktijdig bewerken:** het opslaan-request stuurt de ETag van het netwerk mee (`If-Match`). Is het bestand
  intussen gewijzigd, dan antwoordt de server met 412 en laadt de client opnieuw.

### Gedeelde code

- **`common/py/network_edit/`**: pure functies zonder Flask: `apply_edits(features, edits) -> features`,
  `validate(edits)`, `reverse_index(features)`, plus `schema.py`. Beide servers importeren dit; de module is
  met pytest te testen.
- **`common/py/wegenscan_adapter/`**: de verhuisde wegenscan-adapter (zie hierboven).
- **`common/js/wegvak-editor.js`**: bewerkpaneel, eigen undo/redo-stapel en serialisatie. Wordt door beide
  `index.html`'s geladen, net als `montreal-basemap.js`. De app levert alleen kaart, selectie en `fetch` aan.
- **Endpoint (beide servers):** `POST /processes/edit-network/execution` met
  `{area_id, mode, target: "inplace" | "new", scenario_name?, edits: [...]}`.
  Antwoord 200 met de nieuwe ETag (in-place) of het nieuwe `areaId` (nieuw scenario). De collectie `changes`
  (`server.py:3336`) neemt ook `edits.json` mee, zodat het overzicht van bewerkingen de hele keten toont.

### UI (beide apps)

- Nieuwe knop **"Wegvak bewerken"** naast de bestaande tools in het Aanpassingen-paneel, maar met een eigen
  bewerkingslijst. De twee lijsten worden nooit samen doorgevoerd.
- Klik op een wegvak → paneel met:
  - een **dwarsprofiel-schets** (stoep | fietsstrook | parkeren | rijstroken ⇄ | parkeren | fietsstrook | stoep),
    met per vak een keuzelijst. De rijstroken staan er alleen ter oriëntatie; die zijn niet te bewerken.
    Per vak ook de breedte (stoep, fietsstrook, parkeerdiepte) en de bushalte;
  - wegkenmerken (verharding, verlichting, totale breedte, naam);
  - een blok **Wegenscan**: categorie, V85, scheiding, langsmarkering, drempels, oversteek voetganger/fiets,
    busfrequentie, sociale interactie. Elke waarde met een bron-badge (`wsSources`), en de KPI-score van het
    wegvak die na het opslaan ververst.
- Wijzigingen zijn direct zichtbaar (lokaal toegepast op `_networkFeatures` + `setNetwork`). Ctrl+Z en Ctrl+Y
  werken op de stapel.
- **Opslaan** opent een dialoog: ◉ *Dit scenario bewerken* / ○ *Opslaan als nieuw scenario: [naam]*.
  Bij een basisgebied (geen `.src-area-id`) staat "Nieuw scenario" voorgeselecteerd, en in-place geeft een
  waarschuwing.
- Na het opslaan: netwerk opnieuw laden en `MontrealBasemap.setNetwork()` aanroepen. Dat lost ook het gat in
  `loadAdjustedResult` op.

## Besluiten na stap 0

- Tegenrichting via `reverseLinkIds`, niet via `oppositeLinkId`.
- Bewerkingen per `linkId` raken alle rijen met dat id (zone-joiner-delen).
- Bij profielwaarden die tussen de rijrichtingen niet kloppen, toont de editor een waarschuwing. Opslaan maakt ze
  consistent.
- Geen bewerkingen die herrouteren (rijstroken, verwijderen, opknippen, geometrie). Voor later: verwijderen kan
  de adjust-afsluiting hergebruiken; opknippen kan het `linkId` behouden en `nodePath` bijwerken.
- MIXED: eerst alleen niet-MIXED gebieden ondersteunen. Een MIXED-netwerk is één bestand met een `mode`-kolom
  (`_merge_mixed_outputs`). Daar later per `mode` filteren.
- In-place bewerken van een basisgebied raakt afgeleide scenario's niet: die hebben een eigen NETWORK-kopie.
- `common/py/network_edit` en `common/py/wegenscan_adapter` moeten ook in `analyzer/deploy.ps1` en
  `digital-twin/deploy.ps1` (lijst bij `common/py/buildings_fetcher`). `analyzer/deploy.ps1` noemt nu
  `wegenscan_pipeline.py` los (:28); dat gaat mee.

## Stappen

Na elke stap stoppen voor akkoord.

- [x] **0. Onderzoek** (Deventer - geheel, Apeldoorn, Lochem, Fietsmodel Eindhoven; 4-11-2026)
  - **Tegenrichting:** `oppositeLinkId` is een andere link naar dezelfde `toNode` (bv. `418348005` →
    `-418348069`), dus níet de tegenrichting. Die staat in `reverseLinkIds`: Apeldoorn 14.626 van 15.171 links
    hebben er precies één, in 13.771 gevallen `-linkId`. Knopen zijn bij 94 % omgedraaid. De geometrie is bij
    94 % omgekeerd gelijk (< 1e-4°); de rest heeft meer of minder vertices door de zone-joiner.
  - **`linkId` niet uniek:** 7–8 dubbele id's per gebied, afkomstig van de zone-joiner
    (`gmt_network_core/network_zone_joiner/domain/joiner.py:149`). `adjust` kan daar al mee overweg
    (`by_link_id` → lijst).
  - **Profielkolommen alleen in nieuwere preparaties:** Apeldoorn heeft 66 kolommen, inclusief
    `sidewalk*`/`cycleway*`/`parking*`/`osmLanesInDirection`. Deventer - geheel (45) en Lochem (46) hebben ze
    **niet**. Testgebied voor het profiel wordt dus Apeldoorn, of een opnieuw geprepareerd gebied.
  - **Spiegel-consistentie** (Apeldoorn, paren via `reverseLinkIds`, lege paren niet meegeteld):

    | kolom      | gespiegeld | gelijk, niet gespiegeld | anders |
    |------------|-----------:|------------------------:|-------:|
    | sidewalk   | 5.485      | 180                     | 565    |
    | cycleway   | 4.708      | 1.128                   | 1.090  |
    | parking    | 449        | 5                       | 60     |

    Dat is 12 % inconsistent bij stoep en 32 % bij fietsstrook. Bij fietsstroken waarschijnlijk deels terecht
    (eenrichtings-`cycleway:left/right`), deels een verrijkingsfout. Verder verschillen `surface` (12 %),
    `lit` (17 %) en `roadWidthM` (61 %) tussen de richtingen. Breedte per richting is bewust: `roadWidthM` is
    één rijbaan.
  - **Rijstroken → capaciteit:** 1 strook 1.200–2.175, 2 stroken 3.000–4.454, 3 stroken ≈ 6.422. Dat past bij
    `_capacity_for_speed` (`adjust_core.py:261`); die hergebruiken.
  - **ROUTES:** 13.547 OD-paren (Deventer, 12 MB). Kolom `routes` (JSON) per route met `linkPath` (linkId's als
    string) en `nodePath`. `adjust` behandelt `capacity == 0` als afsluiting: omleiding insplitsen (met
    `nodePath`) of `recompute_routes_for_pairs`. Dat werkt dus al voor verwijderen. Looptijd niet gemeten
    (verwijderen is buiten scope).
  - **MIXED:** lokaal is er geen MIXED-gebied (alle gebieden zijn CAR of alleen BIKE), dus de vraag of linkId's
    per modus gelijk zijn kon ik niet beantwoorden. Zie de besluiten hierboven.
  - **Analyzer versus DT:** dezelfde helpers (`_execute_adjust` verschilt 14 regels, `_find_area_dir`,
    `_find_data_file`, `_read_geodata`, S3, `_merge_mixed_outputs`). Beide zetten `common/py` al op `sys.path`.
    Een gedeelde module werkt dus in beide; het endpoint zelf blijft een dunne laag per server.
- [x] **0b. Onderzoek wegenscan** (5-11-2026)
  - Invoer, huidige bron en aanwezigheid in NETWORK: zie de tabel bij "Wegenscan: het netwerk als enige bron".
  - Van de 21 invoervelden komen er 7 al uit netwerkkolommen, 4 deels, en de rest is altijd default:
    `separation`, `longitudinal_markings`, `bicycle_crossing`, `bus_*` en `social_interaction`.
    `pedestrian_width` en `bicycle_width` zijn altijd 0, waardoor die KPI's altijd SLECHT zijn zodra er een stoep
    of fietsstrook is.
  - Valkuilen in de wheel:
    - `r_speed` komt uit `max_speed_s85`, maar alleen als `max_speed` gevuld is (`wegenscan.py:119`);
    - `width` moet > 0 zijn;
    - een onbekende enum-waarde geeft een KeyError en maakt het hele wegvak NVT. Validatie bij het bewerken is dus
      nodig, niet alleen handig.
  - Apeldoorn heeft geen TRAFFIC-ASSETS: parkeren en drempels uit assets zijn daar dus niet te testen. Gebruik daar
    Deventer of Lochem voor.
- [ ] **1. Schema**: `common/py/network_edit/schema.py` met alle bewerkbare kolommen: naam, weg/zijde, domein,
  eenheid, default, wegenscan-veld. Plus tests: domeinen gelijk aan de enum-lijsten van de wheel.
- [ ] **2. Wegenscan-adapter naar `common/py`**:
  - `wegenscan_{inputs,assets,pipeline}.py` verhuizen;
  - de adapter leest alleen schema-kolommen;
  - zijden samenvoegen volgens de regels hierboven;
  - flow over beide richtingen optellen;
  - scoren per wegvak.

  Bestaande tests (`tests/test_wegenscan_*.py`) meeverhuizen en aanpassen. Analyzer-server laten importeren uit de
  nieuwe plek; uitkomst vergelijken met de huidige WEGENSCAN-bestanden en verschillen verklaren.
- [ ] **3. Netwerkverrijking** (`enrich-network`, beide servers): nieuwe kolommen vullen uit de huidige afleidingen
  (regels, assets, optioneel Databricks), `wsSources` zetten, rijrichtingen consistent maken, `.orig`-back-up.
  Draaien op Apeldoorn, Deventer - geheel en Lochem; dekking per kolom vastleggen in dit plan.
- [ ] **4. `common/py/network_edit`**: `apply_edits` (weg-attributen in beide rijen, zij-attributen gespiegeld,
  ontbrekende kolommen aanmaken, `wsSources` → `"bewerkt"`) en `validate` (tegen het schema; verkeersvelden → fout).
  pytest in `tests/test_network_edit.py` met een klein synthetisch netwerk.
- [ ] **5. Endpoint `edit-network` (DT)**: in-place (met `.orig`-back-up, `edits.json`, ETag/If-Match) en nieuw
  scenario (map + kopieën + `.src-area-id`). Wegenscan herberekenen voor de bewerkte wegvakken. `changes`-collectie
  uitbreiden. Ook naar S3 schrijven als dat aan staat. Testen met de Flask-testclient.
- [ ] **6. Wegenscan in de DT**: `wegenscan`-process en `-collectie` op de DT-server (gedeelde adapter), zodat de
  bestaande knop en laag werken.
- [ ] **7. Front-end (DT)**: `common/js/wegvak-editor.js`, knop + paneel + dwarsprofiel + wegenscan-blok met
  bron-badges, undo/redo, opslaan-dialoog, en na het opslaan netwerk, Kaart en wegenscan-laag verversen.
- [ ] **8. Analyzer**: zelfde endpoint en `wegvak-editor.js` inbouwen in `analyzer/index.html`. Het bestaande icoon
  `overzicht-bewerkingen.svg` hergebruiken. Wegenscan-sleutel `linkId|fromNode`.
- [ ] **9. Test end-to-end**: headless Chrome tegen :5001 (en :5000), gebieden Apeldoorn en Deventer - geheel:
  - stoep en fietsstrook wijzigen → zichtbaar op de Kaart; opslaan in-place en als nieuw scenario; herladen
    → bewerking blijft staan; terugdraaien → origineel terug;
  - fietsstrookbreedte 0 → 1,8 m → wegenscan-KPI fietsstrookbreedte gaat van SLECHT omhoog, in beide richtingen
    gelijk;
  - ROUTES/ZONE/FEEDLINK van het nieuwe scenario byte-gelijk aan de bron; flows ongewijzigd;
  - een request met `lanes`, `capacity` of een onbekende enum-waarde → 400.

## Later (buiten scope)

- Rijstroken (capaciteit via `_capacity_for_speed`, daarna adjust laten herrouteren).
- Wegvak verwijderen (adjust-afsluiting, daarna de rijen verwijderen; looptijd van herrouteren meten).
- Opknippen en vorm aanpassen (`length` opnieuw berekenen, `nodePath` bijwerken).
- MIXED-gebieden.
