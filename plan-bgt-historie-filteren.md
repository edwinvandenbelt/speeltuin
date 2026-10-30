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
- [ ] `fetch_collection_items` krijgt `current_only: bool = True`. Daarmee gaat
  `filter=eind_registratie IS NULL&filter-lang=cql2-text` mee in de query.
- [ ] Optioneel `properties: dict[str, str] | None` voor filters op attribuutwaarden
  (bijv. `functie=parkeervlak`), voor stap 3.
- [ ] De cache-sleutel is de URL, dus oude cache-items worden niet meer geraakt.
- [ ] Unit-tests voor de URL-opbouw. Daarna handmatig testen tegen PDOK.
- [ ] Versie ophogen (0.5.3 → 0.5.4) en de wheel bouwen.

### Stap 2: aanroepers in `gmt-network-enrichment`
- [ ] Het filter staat standaard aan, dus de aanroepers hoeven inhoudelijk niet te veranderen.
  Wel `BGT_QUERY_VER` (5 → 6) en `PARKING_QUERY_VER` (1 → 2) ophogen.
- [ ] De minimumversie van `gmt-shared` in de dependency verhogen. Daarna een nieuwe wheel bouwen.
- [ ] Vegetatie (`gmt-calculation-lib`) profiteert automatisch zodra de nieuwe
  `gmt-shared` geïnstalleerd is. Daar is alleen de dependency-pin nodig.

### Stap 3 (optioneel): parkeervlakken met een filter op `functie` ophalen
- [ ] `parking_area_fetcher_core` vraagt alleen `functie=parkeervlak` op in plaats van
  alle wegdelen. In het teststukje scheelt dat 376 → 8 features. In Goor kostte het
  ophalen van de parkeervlakken ~17 min, en dat zou dan grotendeels wegvallen.
- [ ] `filter_parking_areas` blijft lokaal filteren als vangnet.

### Stap 4: bestaande TRAFFIC-ASSETS in de speeltuin
- [ ] De `traffic_assets`-collectie in `analyzer/server.py` filtert bij het lezen ook op
  `eind_registratie`, met dezelfde logica als `wegenscan_assets._active`. Zo
  zijn bestaande bestanden direct schoon zonder opnieuw te preparen. De bestanden zelf
  blijven staan.
- [ ] Nieuwe wheels in de speeltuin zetten, `requirements.txt` bijwerken en de venv bijwerken.

### Stap 5: controleren
- [ ] Prepare voor Goor (alleen digital twin) opnieuw draaien. Er mogen 0 objecten met
  `eind_registratie` zijn, en er moeten ~718 BGT-parkeervlakken en ~73 drempels zijn.
- [ ] De Wegenscan moet dezelfde uitkomst geven als nu, want `_active` filterte al.

## Werkwijze
Stap voor stap. Na elke stap stoppen voor akkoord.
