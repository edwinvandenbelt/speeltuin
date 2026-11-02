# Plan: Digital Twin bevriest ~27 s na het openen van Deventer

Werkwijze: **stap voor stap**. Na elke stap stoppen, testen, akkoord, dan pas de volgende stap.
Regelnummers verwijzen naar `digital-twin/index.html` (stand 2026-11-02, inclusief tijdelijke tracing).

## Diagnose (trace 2026-11-02, Deventer CAR, 13.547 OD-paren / 66.407 routes)

Na het laden van de routes roept `_loadRoutesInBackground` `rebuildCars()` aan. Dat blokkeert de main
thread **~27 s** (longtask 27.065 ms, heap ~1,5 GB). Bijna alles daarvan zit in `buildCarList` (route-modus,
vulmethode Little's Law):

| Deelstap | Duur | Wat er gebeurt |
|---|---|---|
| Stap 1: paden | 14.643 ms | `buildPathFromLinks` voor **alle** 65.987 routes: 3,37 M links, haversine over alle coördinaten, en **135 M coördinaten** gekopieerd naar `mergedCoords` |
| Stap 2+3: dichtheid | 10.617 ms | per route opnieuw `segmentLength(lo.coords)` voor elke link (3,37 M keer haversine, dezelfde links duizenden keren) |
| Plaatsing | 486 ms | `buildWeightedPath` bouwt per auto (3.108) nóg een keer een pad |
| `computeCarData` | 107 ms | geen probleem |

Uiteindelijk krijgen maar ~3.100 auto's een plek, maar er worden 66 K volledige paden met geometrie gebouwd.
De rest van het opstarten is snel: `_parseAndAddRoutes` 265 ms, `buildLinkRouteMap` 55 ms,
`calibrateRouteProductions` 862 ms.

Dit is hetzelfde patroon als stap 1 van `plan-browser-performance.md` (`linkLenCache` in
`_parseAndAddRoutes`), maar nu in `buildCarList`.

---

### Stap 1: lengte per link één keer berekenen
Er zijn twee soorten lengte, en die mogen niet door elkaar gebruikt worden:
- **Attribuut-lengte** (`properties.length`, al beschikbaar als `seg.length` via `linkLengthM`): goed voor
  rekenwerk zoals reistijd en dichtheid. Ook `_parseAndAddRoutes` gebruikt deze al.
- **Geometrische lengte** (haversine over de coördinaten): nodig voor `path.length`/`boundaries`, want
  `interpolatePosition` loopt de coördinaten af met haversine naar `offset × path.length`. Als de
  attribuut-lengte daar afwijkt, staan auto's verkeerd: ze komen te vroeg of te laat bij de knoop, of
  springen bij een linkovergang.

- [ ] LL stap 3 (`travelTime`): `seg.length` (attribuut) via een `linkId → m`-map, i.p.v.
      `segmentLength(lo.coords)`. Die map wordt gevuld waar `linkGeomMap` wordt opgebouwd (~r. 11024 bij het
      laden, ~r. 18321 in `loadAdjustedResult`).
- [ ] `buildPathFromLinks`: een geometrische lengte-cache per link (`linkId → m`), lazy gevuld, dus
      haversine één keer per unieke link i.p.v. 3,37 M keer. Wordt geleegd samen met `linkGeomMap`.
      Zonder `lo.id` (segment-modus) blijft het zoals nu `segmentLength`.
- [ ] Testen: trace Deventer. Verwachting: stap 2+3 van ~10,6 s naar < 0,3 s.

### Stap 2: paden pas bouwen als ze nodig zijn (lazy `rp.path`)
- [ ] Stap 1 van `buildCarList` berekent alleen `length` (som van de gecachte geometrische linklengtes) en de snelheid van
      de eerste link (voor `canPark` en het filter `< 30 m`). Er wordt geen `mergedCoords` meer gekopieerd.
- [ ] `rp.path` wordt een lazy getter die `buildPathFromLinks` één keer aanroept en het resultaat bewaart.
      Zo blijft het pad-object hetzelfde per route, en daarvan zijn `enforceInitialSpacing` (groepeert op
      `car.path`) en `spawnProductionCar` (`odGroups`) afhankelijk. Alleen routes die een auto krijgen,
      of later via productie gekozen worden, bouwen dan nog geometrie.
- [ ] Testen: trace Deventer. Verwachting: stap 1 van ~14,6 s naar < 0,5 s, en een duidelijk lagere heap.
      Controleren dat auto's rijden, parkeren en via productie blijven verschijnen.

### Stap 3: plaatsing hergebruikt `rp.path`
- [ ] `buildWeightedPath` bouwt geen nieuw pad per auto meer, maar kiest de startpositie op `rp.path`
      (`boundaries` + gewichten flow × lengte uit `linkFlowMap`).
- [ ] Testen: dezelfde verdeling van auto's over het netwerk (visueel), en een kortere plaatsing.

### Stap 4: overige vulmethoden en gebieden controleren
- [ ] Vulmethoden LD (`link`) en CB (`cap`) gebruiken `rp.path.boundaries`/`links` voor álle routes met
      gewicht > 0. Met lazy paden worden die alsnog allemaal gebouwd. Meten, en zo nodig de boundaries
      zonder coördinaten berekenen.
- [ ] Een ander gebied (bijv. Eindhoven, Montréal) en MIXED-modus: gedrag ongewijzigd, geen regressie.
- [ ] Scenario wisselen (`loadAdjustedResult`) en de Terug-knop: de cache wordt correct ververst.

### Stap 5: opruimen
- [ ] Tijdelijke tracing verwijderen (het blok "TIJDELIJK: tracing" bovenaan het hoofdscript, de
      `_trace`/`_traceTime`-aanroepen en de deelstap-traces in `buildCarList`). De bestaande `[perf]`-regels
      blijven staan.
- [ ] Fix doorzetten naar `analyzer/index.html` als `buildCarList` daar gedupliceerd is (nagaan).
