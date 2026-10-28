# Plan: 3D-objecten — laadindicatie, totaal-aantallen en OGC-paging

## Context

Na het aanzetten van de 3D-objecten in de digital twin is er geen laadindicatie en geen totaalaantal, en
verschijnen voet-/fietspaden, kunstwerken, straatmeubilair en drempels niet. Oorzaken:

1. **Data ontbreekt grotendeels.** De TRAFFIC-ASSETS-parquets bevatten:
   - De Kien: parkingArea 9805, speedBump 1374, trafficSignal 174, pedestrianCrossing 147, giveWay 45, trafficSign 31
   - Den Bosch – Spoorzone: parkingArea 8665, speedBump 1734, bak 1415, bridge 769, tunnel 28
   - Deventer – geheel: alleen parkingArea 20510

   Geen `footPath`/`cyclePath`/meubilair: die komen uit `osm_asset_fetcher` en worden alleen met
   `fetch_osm_assets=True` in de prepare-pipeline meegenomen (staat standaard uit). Buiten scope.
2. Laden gebeurt pas vanaf zoom 16; daaronder stopt de client stil zonder indicatie.
3. Het aantal tussen haakjes is viewport-gebonden en verandert bij elke pan.
4. De server parst bij elk bbox-verzoek het hele parquet opnieuw (geen cache) en stuurt parkingArea mee.
5. Drempels worden als grijs vlak onder de netwerklaag getekend — controleren.

**Doel:** spinner achter elke 3D-checkbox zolang data binnenkomt, en het **totaal in de hele uitsnede**
tussen haakjes (b.v. `Bomen (5105)`). Ophalen via OGC API Features GeoJSON met `limit`/`offset`-paging.

## Stappen

- [x] **1. Server: OGC-paging in `_ogc_items_response`** — `limit`/`offset`, `numberMatched` (totaal),
      `numberReturned`, `rel=next`-link; `limit=0` = alleen telling; zonder `limit` alles (compatibel).
- [x] **2. Server: caching, filters, bbox-test** — `_geodata_cache` voor traffic_assets/vegetation/heights;
      `_geom_bbox` als module-helper en overlap-test voor alle drie; `vegType`-filter bij vegetation.
- [x] **3. Client: helpers** — `_fetchOgcPaged`, `_fetchOgcCount`, category → assetType-map
      (bbox-fetch zonder parkingArea).
- [x] **4. Client: verkeersobjecten** — totaal per categorie (`_taTotals`, los van zoom), spinner per categorie,
      gepagineerde bbox-load met progressieve render, `_loadSpeedBumpsForArea` zonder NDGeoJSON,
      zoom-hint onder zoom 16.
- [x] **5. Client: bomen en drempels** — `Bomen (totaal)` via `vegType=tree&limit=0`, gepagineerde
      `loadVegetationInView`; zichtbaarheid drempels controleren/repareren.

- [ ] **6. Geforceerd opnieuw maken van TRAFFIC-ASSETS + VEGETATION** — OGC-proces `refresh-scenery` dat
      `prepare.run_pipeline(only_dt=True, fetch_buildings=False)` draait op het bestaande netwerk van het
      gebied dat de bestanden bezit (baseAreaId-keten); `.bak`-kopieën vooraf, terugzetten bij fout, oude
      `VEGETATION.geojson` → `.bak`, aantallen per assetType in de job-log. Knop "↻ Opnieuw ophalen" in het
      3D-blok met bevestiging, spinners tijdens de job, daarna totalen en objecten opnieuw laden.

## Verificatie

- `curl "http://127.0.0.1:<port>/collections/traffic_assets/items?areaId=1648b7ef-…&assetType=speedBump&limit=0"`
  → `numberMatched: 1374`, geen features; `limit=500` → 500 features + `next`-link; zonder `limit` → alles.
- `vegetation?…&vegType=tree&limit=0` → 5105.
- Browser De Kien: Borden ≈ 397, Drempels 1374, Paden 0, Meubilair 0, Kunstwerken 0, Bomen 5105 — direct na
  aanvinken, ook onder zoom 16; totaal verandert niet bij pannen.
- Den Bosch: Kunstwerken (2212), Bomen (0).

## Buiten scope

Paden en straatmeubilair vereisen opnieuw prepareren met `fetch_osm_assets=True` (PBF/prepare-pipeline).
Bestaande work/-parquets niet wissen.
