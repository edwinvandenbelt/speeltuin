# Plan: historische BGT-objecten al bij het ophalen wegfilteren

## Context

De BGT-API van PDOK (`api.pdok.nl/lv/bgt/ogc/v1`) geeft standaard alle versies van een
object terug, dus ook vervangen versies waarvan `eind_registratie` gezet is. In Goor
is 593 van de 1311 parkeervlakken en 21 van de 94 drempels historisch. Die objecten
komen nu in TRAFFIC-ASSETS terecht. Alleen de Wegenscan filtert ze achteraf weg
(`wegenscan_assets._active`). De kaartlaag `traffic_assets` laat ze dus waarschijnlijk dubbel zien.

**Getest:** de API ondersteunt CQL2-filters (OGC API Features part 3). Op een stukje
Goor (bbox 6.57,52.27,6.59,52.28, collectie `wegdeel`):

| query                                              | features | historisch |
|----------------------------------------------------|---------:|-----------:|
| alleen bbox                                        |      376 |        207 |
| `filter=eind_registratie IS NULL`                  |      169 |          0 |
| `functie=parkeervlak`                              |       10 |          2 |
| `functie=parkeervlak` + `eind_registratie IS NULL` |        8 |          0 |

`eind_registratie` is een queryable in alle collecties die we gebruiken: `wegdeel`,
`scheiding_lijn`, `scheiding_vlak`, `overbruggingsdeel`, `tunneldeel`, `bak` en
`begroeidterreindeel` (vegetatie).

Alle BGT-aanroepen lopen via één functie: `gmt_shared.ogc_features.fetch_collection_items`.
Die wordt gebruikt door:
- `gmt-network-enrichment`: `bgt_fetcher_core` (5 collecties) en `parking_area_fetcher_core`
- `gmt-calculation-lib`: `osm_vegetation_fetcher_core` (`begroeidterreindeel`)

## Stappen

### Stap 1: filter in `gmt-shared` (`src/gmt_shared/ogc_features.py`)
- [x] `fetch_collection_items` krijgt `current_only: bool = True`. Daarmee gaat
  `filter=eind_registratie IS NULL&filter-lang=cql2-text` mee in de query.
- [x] `properties: dict[str, str] | None` voor filters op attribuutwaarden
  (bijv. `functie=parkeervlak`), voor stap 3.
- [x] De cache-sleutel is de URL, dus oude cache-items worden niet meer geraakt.
- [x] Unit-tests voor de URL-opbouw. Daarna handmatig testen tegen PDOK.
- [x] Versie ophogen (0.5.3 → 0.5.4) en de wheel bouwen.

### Stap 2: aanroepers in `gmt-network-enrichment`
- [x] Het filter staat standaard aan, dus de aanroepers hoeven inhoudelijk niet te veranderen.
  Wel `BGT_QUERY_VER` (5 → 6) en `PARKING_QUERY_VER` (1 → 2) ophogen.
- [x] De minimumversie van `gmt-shared` in de dependency verhogen. Daarna een nieuwe wheel bouwen.
- [x] Vegetatie (`gmt-calculation-lib`) profiteert automatisch zodra de nieuwe
  `gmt-shared` geïnstalleerd is. ~~Dependency-pin~~ niet aangepast, omdat die repo een
  niet-gecommitte wijziging heeft (`adjust_core.py`). Zie bevindingen.

### Stap 3 (optioneel): parkeervlakken met een filter op `functie` ophalen
- [x] `parking_area_fetcher_core` vraagt alleen `functie=parkeervlak` op in plaats van
  alle wegdelen. In het teststukje scheelt dat 376 → 8 features. In Goor kostte het
  ophalen van de parkeervlakken ~17 min, en dat zou dan grotendeels wegvallen.
- [x] `filter_parking_areas` blijft lokaal filteren als vangnet.

### Stap 4: bestaande TRAFFIC-ASSETS in de speeltuin
- [x] De `traffic_assets`-collectie in `analyzer/server.py` filtert bij het lezen ook op
  `eind_registratie`, met dezelfde logica als `wegenscan_assets._active`. Zo
  zijn bestaande bestanden direct schoon zonder opnieuw te preparen. De bestanden zelf
  blijven staan.
- [x] Nieuwe wheels in de speeltuin zetten, `requirements.txt` bijwerken en de venv bijwerken.

### Stap 5: controleren
- [x] ~~Prepare voor Goor opnieuw draaien~~ → in plaats daarvan de ophalers rechtstreeks voor de Goor-bbox gedraaid (work/ ongemoeid). Er mogen 0 objecten met
  `eind_registratie` zijn, en er moeten ~718 BGT-parkeervlakken en ~73 drempels zijn.
- [x] De Wegenscan moet dezelfde uitkomst geven als nu, want `_active` filterte al.

## Bevindingen

- **Stap 1:**
  - `build_items_url()` is nieuw en wordt ook gebruikt voor de cache-sleutel. `fetch_collection_items(..., current_only=True, properties=None)`.
  - PDOK neemt het filter mee in de `next`-links. Met limit=50 kwamen er 169 objecten over 4 pagina's, waarvan 0 historisch.
  - Tests: 6 nieuw (`test_ogc_features.py`); alle 130 tests in gmt-shared slagen. Ruff schoon. De 2 mypy-meldingen bestonden al.
  - Wheel: `gmt-shared/dist/gmt_shared-0.5.4-py3-none-any.whl` (nog niet gecommit of gepubliceerd).
- **Stap 2/3:** (`gmt-network-enrichment` 0.6.1)
  - `BGT_QUERY_VER` is nu 6 en `PARKING_QUERY_VER` 2. De dependency is `gmt-shared>=0.5.4`.
  - De parkeerophaler stuurt `functie=parkeervlak` mee; lokaal filteren blijft als vangnet. Er is een test die controleert dat het filter wordt meegestuurd.
  - Twee bestaande tests faalden al. Ze patchten de oude module `shared.*`; dat is nu `gmt_shared.*`. Alle 249 tests slagen.
- **Stap 4:**
  - `_current_bgt_features()` staat in `analyzer/server.py` en `digital-twin/server.py` en wordt gebruikt in de `traffic_assets`-collectie.
  - Het filter haalt objecten met `eind_registratie`/`termination_date` eruit en ontdubbelt per (`lokaal_id`, `assetType`). Dat laatste is nodig omdat één wegdeel zowel voetpad als drempel kan zijn.
  - Wheels zijn vervangen (`gmt_shared-0.5.4`, `gmt_network_enrichment-0.6.1`), beide requirements bijgewerkt en de venv geïnstalleerd.
  - VEGETATION-bestanden hebben geen BGT-velden, dus filteren bij het lezen kan daar niet. Die worden pas schoon na een nieuwe prepare.
- **Stap 5 (Goor):**
  - Filter bij het lezen op de bestaande TRAFFIC-ASSETS: parkingArea BGT 1311→718, speedBump 94→73, sidewalk 2208→931, bikePath 149→67, bridge 34→30. OSM en NDW blijven gelijk. Voor parkeren en drempels gelijk aan `_active` (740 incl. OSM, 73).
  - Live ophalen met de nieuwe wheels: precies dezelfde aantallen en 0 historisch. **Parkeervlakken in 2 s in plaats van ~17 min.**
  - Alle 60 speeltuin-tests slagen. De Wegenscan verandert niet, want `_active` filterte al.
- **Open:**
  - `gmt-calculation-lib` laten verwijzen naar `gmt-shared>=0.5.4` (na je eigen wijziging in `adjust_core.py`).
  - Commits/publicatie van de wheels in gmt-shared en gmt-network-enrichment.
  - Opnieuw preparen voor schone VEGETATION.

## Werkwijze
Stap voor stap. Na elke stap stoppen voor akkoord.
