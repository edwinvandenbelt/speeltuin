# Plan: spoorlijnen en bewegend water in F4Map-stijl (digital twin)

## Context

- **Spoor ontbreekt.** "Kaart" toont in de digital twin de Montréal-ondergrond (`common/js/montreal-basemap.js`).
  In die modus gaan alle Liberty-lagen op de OpenFreeMap-source uit, behalve de labels
  (`hiddenBaseLayerIds`). Daarmee verdwijnen ook de Liberty-spoorlagen (`*_rail*`). De `mtl-*`-set heeft zelf
  geen spoor. De analyzer heeft hetzelfde probleem, want die gebruikt dezelfde module.
- **Water** is nu een vlakke fill (`mtl-water`, `#8fc7ca`) plus lijnen (`mtl-waterways`). F4Map tekent water
  met bewegende golfjes, een lichtere lucht-weerspiegeling onder schuine hoek (fresnel), schittering van de zon
  en spiegelbeelden van gebouwen.

## Aanpak water

We maken een **MapLibre custom layer** (WebGL) op de plek van `mtl-water`:

- **Geometrie:** de `water`-polygonen uit de vectortiles, via `map.querySourceFeatures(src, {sourceLayer:'water'})`
  per `sourcedata`/`moveend`. Triangulatie met `earcut` (jsDelivr). De mesh krijgt per tegel een cache.
- **Shader:**
  - golfnormalen uit een paar bewegende sinus/ruis-lagen in wereldmeters, zodat ze niet meeschalen met de zoom;
  - fresnel-menging tussen de waterkleur en de luchtkleur (`_sunState` / `setSky`);
  - zonneschittering (specular) in de richting van de gesimuleerde zon. 's Nachts wordt het water donker en
    zonder schittering.
- **Animatie:** `triggerRepaint` met een eigen rAF-lus, alleen als er water in beeld is.
  `prefers-reduced-motion` zet de golfjes stil.
- **Terugval:** zonder WebGL2 of bij een fout blijft de gewone fill `mtl-water` staan.

**Spiegelbeelden van gebouwen** zijn een apart, onzeker stuk. Het vraagt een planaire reflectie: de 3D
BAG-meshes gespiegeld (z → −z) in een offscreen-buffer tekenen en die in de watershader samplen. deck.gl 8.9 in
interleaved-modus deelt de GL-context met MapLibre, dus het kan in principe. Een `MaskExtension` op gespiegelde
meshes werkt niet: die maskeert op het punt *onder* het gebouw (land), zodat panden aan de kade nooit
spiegelen. Daarom eerst een spike (stap 4).

## Stappen

Spiegelbeelden van gebouwen vallen af (besluit 30-10-2026, eventueel later). De overige stappen zijn in één keer
uitgevoerd.

- [x] **1. Spoor in de Montréal-ondergrond** (`montreal-basemap.js`, dus ook in de analyzer)
  - `mtl-rail-bed` (ballastbedding), `mtl-rail-ties` (dwarsliggers via dasharray, vanaf z16,5), `mtl-rail-line`
    (dunne lijn tot z16) en `mtl-rails` (twee rails via `line-gap-width`, vanaf z16). Alle lagen gebruiken
    `transportation` met `class` = `rail`, zonder tunnels. Tram/metro (`class` = `transit`) krijgt alleen rails.
  - De breedtes volgen ongeveer de werkelijke maten op z19 (grondtal 2). De lagen liggen boven de wegen.
  - Kleuren staan in het palet (`railBed`, `railTie`, `rail`, ook voor `night`).
- [x] **2. Bewegend water** — nieuw: `common/js/animated-water.js` (`window.AnimatedWater`). Alleen de digital twin
  laadt het; het staat ook in `deploy.ps1`.
  - Custom layer `mtl-water-anim` direct boven `mtl-water`. Het tekent alleen zolang `mtl-water` zichtbaar is,
    want custom layers ontbreken in `getStyle().layers`, dus `setVisible` ziet ze niet.
  - Geometrie: `querySourceFeatures(…, 'water')` → earcut (lui geladen van jsDelivr). De mesh krijgt meters
    t.o.v. een vaste oorsprong (geen float32-gejitter). Herbouw bij `sourcedata`/`moveend` (250 ms debounce).
  - MapLibre 5 geeft `modelViewProjectionMatrix` in wereldpixels: in JS ×(512·2^zoom) naar mercator 0..1. De
    camerapositie komt uit de inverse van die matrix (`getFreeCameraOptions` bestaat niet in v5).
  - Shader: golfhoogte uit 4 octaven simplex-ruis (8 / 3,7 / 1,7 / 0,8 m), die op afstand vervagen.
    Daarbij fresnel naar lucht (horizon → zenit), een lichte golfschaduw en zon-specular. Sinusgolven gaven op
    afstand een ruitpatroon.
  - ~~Animatie ~30 fps via `triggerRepaint`~~ — teruggedraaid (besluit 30-10-2026): continu hertekenen
    (MapLibre + alle deck.gl-lagen) maakte de site vrijwel onbruikbaar. De golven staan nu stil. Er wordt alleen
    hertekend na een herbouw van de geometrie, bij een zonwissel of op `styledata` (ondergrond-keuze).
    Gecontroleerd: 0 renders in 3 s stilstand.
- [x] **3. Koppeling aan de zon** — `updateSunLight` → `AnimatedWater.setSun(sun)`. Overdag reflecteert het de
  lucht- en horizonkleur, met schittering in de zonrichting (lage zon → warme strepen). 's Nachts is het mild
  gedempt blauwig, zonder schittering.
- [ ] ~~**4. Spike: spiegelbeelden van gebouwen**~~ — later.
- [x] **5. Testen** (headless Chrome, Den Bosch – Spoorzone)
  - Spoor op z16–19,6: bedding, dwarsliggers, rails en wissels zichtbaar.
  - Water: golfjes zichtbaar, ver weg lichter door de luchtweerspiegeling.
  - 20:00 → gedempt water; lage zon (handmatige `setSun`) → warme glinstering.
  - Nog niet getest: analyzer (spoor), split-view `map2`, maquette-modus, fps op een zwakke laptop.

## Aandachtspunten
- Echt bewegend water kan pas als het hertekenen goedkoop is, bijv. alleen meeliften op frames die de
  simulatie al tekent (dan beweegt het water alleen als de simulatie loopt).
- De smalle waterlopen (`mtl-waterways`, lijnen) bewegen niet mee.
