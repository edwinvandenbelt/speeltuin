# Plan: "Pagina reageert niet / Wachten" in Analyzer en Digital Twin

Tijdens demo's (met Zoom/Teams screen-sharing) toont Chrome regelmatig "Wachten". Beide apps
(`analyzer/index.html`, `digital-twin/index.html`; MapLibre 5.24 + deck.gl 8.9 interleaved) doen alles
op de main thread. Screen-sharing vraagt zelf GPU/CPU (capture + encoderen), waardoor de marge die er
normaal nog is, verdwijnt.

Werkwijze: **stap voor stap**. Na elke stap stoppen, testen, akkoord, dan pas de volgende stap.

Regelnummers: **A** = `analyzer/index.html`, **DT** = `digital-twin/index.html` (stand 2026-10-27,
verschuiven tijdens het werk). Veel code is in beide bestanden gedupliceerd, dus elke fix geldt voor beide.

## Oorzaken (samengevat)

1. **Echte lange blokkades** (seconden): de Dijkstra-schatting voor een link zonder routedata draait bij
   **elke** `updateOverlay` opnieuw in plaats van uit `_estimatedRouteCache` te komen. Dit is de meest
   waarschijnlijke oorzaak van de "Wachten"-dialoog.
2. **Per-frame verspilling**: `updateOverlay(true)` bouwt elke frame ~20–25 deck-lagen met *nieuwe*
   data-arrays (`.filter(...)`, nieuwe FeatureCollection-wrappers). deck.gl tesselleert dan alles opnieuw.
   In de Analyzer gebeurt dit zelfs terwijl er geen auto's getekend worden (`makeCarLayers` returnt `[]`),
   namelijk nadat een edit-modus is verlaten (`paused = false`).
3. **GPU-druk**: `antialias: true` (MSAA) op volle devicePixelRatio, pitch 58 + 3D-gebouwen + sky/fog, en
   ~15 panelen met `backdrop-filter: blur()` boven een canvas dat elke frame hertekent.

---

## Fase 1 — Quick wins (grootste effect, laag risico)

### Stap 1 — Routes parsen: linklengte cachen (A + DT `_parseAndAddRoutes`)
Gemeten in de Analyzer (66.406 routes): `_parseAndAddRoutes` 11.056 ms, `calibrateRouteProductions`
931 ms; `TOTAL post-routes sync` 17.443 ms. Dat totaal bevat ook ~5,4 s download/parse, omdat `_tPost` vóór
`await _rtFetch` start.
Oorzaak: per route werd voor elke link `segmentLength(coords)` (haversine over alle coördinaten)
opnieuw berekend, dus dezelfde link duizenden keren.
- [x] De lengte wordt nu één keer per link berekend (`linkLenCache`, lokaal per aanroep). Het filter op
      ontbrekende/korte geometrie en de `parseInt`-normalisatie zitten in dezelfde lus.
- [x] Het `length`-attribuut uit het netwerkbestand gebruiken waar dat er is (`linkLengthM(f)`, naast
      `segmentLength`). Dit gebeurt bij het opbouwen van `segments` (bij het laden en na een linkbewerking).
      `linkLenCache` wordt voorgevuld met die segmentlengtes; haversine is alleen nog de fallback.
- [ ] Testen: Analyzer en DT opnieuw laden en de `[perf]`-regels vergelijken. Het aantal routes
      (`buildLinkRouteMap … routes:`) moet gelijk blijven (66.406).

### Stap 2 — Analyzer: panden pas ophalen bij gebruik
- [x] De panden worden niet meer bij het opstarten opgehaald, maar pas wanneer
      'Pand productie/attractie' ≠ uit (`_ensureBuildingsLoaded`, aangeroepen vanuit `_applyBuildingDisplay`).
      Daarmee vervallen bij het opstarten: de NDJSON-download, filter/hoogte, `_tryZoneJoin` (met de
      O(parking × gebouwen)-lus) en `setData`.
      Bijeffect: de vloeroppervlak-uitsplitsing in de zone-tooltip verschijnt pas nadat de panden geladen zijn.
- [ ] Testen.

### Stap 3 — Dijkstra-schatting uit de cache halen
- [ ] In de zone-centroid-laag (A ~10894, DT ~13444) de aanroep `computeEstimatedLinkRouteData(selectedLinkId)`
      vervangen door een cache-lookup, zoals A ~11027 / DT ~13577 al doen:
      ```js
      const est = _estimatedRouteCache.get(Number(selectedLinkId));
      if (est) ({ flowByFromZone, flowByToZone } = est);
      ```
      De klik-handler (A ~12428, DT ~14972) berekent het resultaat al asynchroon en vult de cache.
- [ ] In `dijkstraWithPaths` en de andere Dijkstra-varianten (A ~7894/7932/7956, DT ~10520) het patroon
      `open.sort()` + `open.shift()` vervangen door een kleine binaire min-heap.
      Dit brengt de complexiteit van O(V² log V) naar O(E log V).
- [ ] Testen: een link zonder routedata selecteren met de simulatie aan. De kaart blijft vloeiend en de
      tegenpool-zones zijn gelijk aan die vóór de fix.

### Stap 4 — Analyzer: autosimulatie volledig verwijderd
De Analyzer toonde geen rijdende auto's (`makeCarLayers` gaf `[]` terug), maar bouwde en simuleerde ze wel.
Bij het opstarten werden 66k routepaden opgebouwd (`buildCarList` → `buildPathFromLinks`, met haversine
per link per route). Dat gebeurde opnieuw bij elke dagdeel- of klokwissel (2×). Daarnaast liep er een
eeuwige `requestAnimationFrame`-lus die elke frame alle lagen opnieuw opbouwde.
- [x] Verwijderd uit `analyzer/index.html` (~1.950 regels):
      - het opbouwen van de auto's: `buildCarList`, `buildPathFromLinks`, `enforceInitialSpacing`,
        `computeCarData`, `buildPathGroups`, `rebuildCars` en alle aanroepen daarvan;
      - de simulatie zelf: `animate()` (car-following, voorrang, parkeren, productie) en `odGroups`;
      - de 3D-weergave: voertuig-meshes, `makeCarLayers` en `SimpleMeshLayer`;
      - de Voertuigteller (⊕): knop, paneel, CSS, i18n en passage-detectie;
      - de instelling 'Initiële vulling' (LL/LD/CB) en de autostatistieken in het debugpaneel.
- [x] `avgVehicleLengthForMode` (bezettingsgraad-metric) gebruikt nu vaste gewogen gemiddelden:
      4,725 m voor auto's en 1,85 m voor fietsen. Dat zijn dezelfde waarden als voorheen.
- [x] `paused`, de simulatieklok en het afspeelvinkje blijven bestaan, want ze sturen dagdeel en flows.
- [x] Controle: `node --check` en `eslint no-undef` zijn schoon. Daarbij bleek `_linkIdsToCoords` nog nodig
      te zijn; die is teruggezet.
- [ ] Testen: opstarten (`[perf]`-regels en tijd tot het laadscherm verdwijnt), dagdeel/klok wisselen,
      afspelen/pauzeren, edit-modi openen/sluiten, zone- en linkselectie, split-view en de debug-modus.

### Stap 4b — Analyzer: klok alleen nog dagdelen
- [x] Bug: na het verlaten van een bewerkmodus werd `paused = false`. Daarna wisselde het klokknopje AM/PM,
      verscheen er een kloktijd (`08:00`) en werd het datumveld actief. `paused` en de verborgen afspeel-toggle
      zijn verwijderd, dus de klok kent alleen nog 24 uur → ochtendspits → restdag → avondspits.
- [x] Opgeruimd: de wijzer, `simHour`, de tick-lus (5 s), `updateClockUI`/`setSimHour`/`daypartForHour`, de
      AM/PM-tekst, de tooltip "Sleep de wijzer…" en de bijbehorende CSS en i18n.
- [x] Datumveld blijft staan (keuze gebruiker), maar blijft niet aanpasbaar zoals voorheen. Ochtend- en
      avondspits worden nog als `datum 08:00` / `datum 17:00` opgevraagd. Een datumwijziging herberekent
      alleen tijdens een spits.
- [ ] Testen: door de 4 dagdelen klikken. Een bewerkmodus openen en sluiten en daarna opnieuw klikken:
      er mag geen AM/PM of kloktijd verschijnen.

### Stap 5 — Data-referenties stabiel houden (memoization)
deck.gl hergebruikt GPU-buffers alleen als `data` dezelfde referentie houdt.
- [ ] Het MIXED-modusfilter op `geojson.features` cachen op `(MODE, visibleModes, netwerkversie)`.
      Plekken: A ~9960/10295/10368/10569/10674 en DT ~12510/12845/12918/13119/13224.
- [ ] De speedbump-wrapper (A ~7203 / DT ~8012) één keer opbouwen wanneer de bron verandert.
      Hetzelfde geldt voor de DT-bronnen:
      - `.filter(okLine)` op asset-paden (~8524–8676);
      - road-marks (~8079);
      - refuges (~8187);
      - vegetatie (~9257–9260);
      - zonegrenzen + `PathStyleExtension` (~13273–13292).
- [ ] `computeZoneRouteData()` (3× per update) en `computeLinkRouteData()` (2× per update) memoizen op
      selectie, routes-versie en dagdeel.
- [ ] In `makeNetworkLayer` de min/max van de segmenten berekenen bij het laden of bij een flow-wijziging,
      niet per frame.
- [ ] Testen: MIXED-filter, zone- en linkselectie, vegetatie en assets op zoom ≥ 16 werken ongewijzigd.

### Stap 6 — Lichtere rendering ("demo-modus")
- [ ] MapLibre standaard instellen op `pixelRatio: Math.min(window.devicePixelRatio, 1.5)`, voor de main- en
      de split-map (A ~5694/14871, DT ~5494/17268).
- [ ] Een optie `?lite=1` toevoegen (of een toggle die in localStorage staat en bij het opstarten wordt gelezen;
      `antialias` kan alleen bij het aanmaken van de context worden gezet). Deze optie zet:
      - `antialias: false` en `pixelRatio: 1`;
      - `backdrop-filter` uit, via `body.lite` met een solide, iets transparante achtergrond;
      - in DT: sky/fog uit (~5476–5477);
      - in DT: de overlay-update tijdens de simulatie begrensd op ~30 fps.
- [ ] Testen: in lite-modus is de kaart scherp genoeg, de panelen zijn leesbaar en de GPU-belasting is
      zichtbaar lager (Taakbeheer → GPU).

### Stap 7 — Kleine opruimacties
- [ ] DT: de "TIJDELIJK" fetch-trace verwijderen (`setInterval` ~2559 + `console.log` per fetch, ~2535–2567).
- [ ] DT: de `console.log` in `computeEstimatedLinkRouteData` (~10734) verwijderen.
- [ ] NDJSON-readers (A ~5471/5521, DT ~5241–5284): niet meer per regel `buf.slice(nl+1)` doen, maar een
      index bijhouden en één keer per chunk slicen.
- [ ] A: `_counterPrevPos` van `Map` naar `WeakMap` omzetten (lek), zoals DT al doet.

---

## Fase 2 — Structureel (alleen als fase 1 niet genoeg is)

- [ ] DT `interpolatePosition` (~4598): cumulatieve lengtes vooraf berekenen per pad en daarin binair
      zoeken, in plaats van per auto per frame een haversine-loop vanaf het begin.
- [ ] `_tryZoneJoin`: de parkeerherclassificatie is nu O(parking × gebouwen) (A ~6513, DT ~6340);
      dit omzetten naar een grid-index.
- [ ] DT asset-bearing (`_taRoadBearingAt` ~7555/7680, ~8806): een grid-index op netwerksegmenten.
- [ ] De gebouwen-join en `calibrateRouteProductions` naar een Web Worker verplaatsen.

---

## Tips zonder code (direct bruikbaar bij demo's)

- Deel in Teams/Zoom alleen het **browservenster**, niet het hele scherm. Zet "optimaliseren voor video" uit.
- Controleer in Chrome dat hardwareversnelling aan staat (`chrome://gpu`) en open weinig andere tabs.
- Laat de laptop aan de lader: in energiebesparingsmodus wordt de GPU teruggeschroefd.
- Op een 4K/HiDPI-scherm het browservenster kleiner maken of 100% schaal gebruiken. Het aantal pixels
  schaalt kwadratisch mee.
- Zolang stap 3 er niet in zit: selecteer geen link zonder routedata terwijl de simulatie loopt.

## Verificatie (per stap en aan het eind)

1. Chrome DevTools → Performance: een opname maken vóór en na de fix, met de simulatie aan, een geselecteerde
   link zonder routes en een geselecteerde zone. Het doel is: geen long tasks > 200 ms en een frametijd van
   ~16–33 ms.
2. Functioneel: de zone- en linkselectie tonen dezelfde stromen en paden als vóór de fix.
3. De bestaande tests draaien (`digital-twin/tests`, `tests/`).
4. Beide servers lokaal starten via `127.0.0.1` (niet `localhost`) en de apps handmatig bekijken,
   eventueel met een actieve Teams-share.
