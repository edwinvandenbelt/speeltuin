# Plan: gebouwen in F4Map-stijl via 3D BAG (issue #18)

## Context

F4Map (demo.f4map.com) haalt zijn gebouwvormen uit **OpenStreetMap, volgens het "Simple 3D Buildings"-schema**
(`height`, `roof:shape`, `building:part`, `roof:colour`, …) en vult ontbrekende tags zelf in. Belichting met
schaduw zorgt voor de diepte.

In NL is OSM daarvoor te mager. Gemeten in Aalten (10.139 panden): `roof:shape` 181×, `height` 1×.
Nu tekent `digital-twin/index.html` de panden als `fill-extrusion` (`buildings-3d`): platte dozen met hoogte
`height`, anders `levels × 3`, anders 4 m.

**Keuze:** we gebruiken de **echte LoD2.2-panden uit de 3D BAG** (TU Delft, alle NL-panden). De tooltip blijft
gebaseerd op onze eigen pand-data.

## Uitkomst spike (stap 1)

De testpagina (`digital-twin/spike-3dbag.html`) is na afloop verwijderd; de loader leeft verder in `index.html`.

- **`Tile3DLayer` is onbruikbaar.**
  - In deck.gl 8.9 weigert loaders.gl 3D Tiles 1.1. Na het herschrijven van de versie gaan de
    sub-tilesets en de `.glb` alsnog mis.
  - deck.gl 9.4 met loaders.gl 4 laadt de tegels wel, maar negeert de `byteStride` van de interleaved
    meshopt-bufferView. Indices tot 4,29 miljard en posities duizenden km hoog → verminkte geometrie.
- **Eigen loader werkt, op deck.gl 8.9 (geen upgrade nodig).** De stappen:
  1. tileset doorlopen op bbox;
  2. `.glb` parsen en decoderen met `meshoptimizer@1.3.0` (jsDelivr, ES-module);
  3. node-matrix → ECEF → lokale ENU-meters per tegel;
  4. per pand het laagste punt naar z = 0 (vlakke kaart, dus geen NAP-/geoïde-correctie nodig);
  5. tekenen met `SimpleMeshLayer`.
- **Meetwaarden** (Deventer-centrum, straal 500 m):
  - 8 tegels, 14,3 MB, 12.378 panden, 1,54 M vertices;
  - decoderen ~400 ms; eerste tegel na 1,2 s, alles na 1,9 s;
  - **60 fps**, ook met schaduw.
- **Kleur:** deck.gl 8.9 overschrijft vertex-`colors` van een mesh. Daarom splitsen we per tegel in drie meshes
  (gevel / schuin dak / plat dak, op basis van de normaal), elk met een eigen `getColor`. Ziet er F4-achtig uit.
- **Metadata per pand zit in de tegel** (`EXT_structural_metadata` + `_FEATURE_ID_0`): o.a. `identificatie`
  (= `NL.IMBAG.Pand.<id>`, koppelbaar aan onze `ref:bag`), `b3_dak_type`, `b3_h_nok`, `b3_h_maaiveld`,
  `b3_bouwlagen`.
- **3D-pick werkt:** `deck.pickObject({…, unproject3D: true})` geeft het punt op dak of gevel (z 8–15 m). Daarmee
  vinden we het juiste BAG-pand.
- **Schaduw:** `_SunLight` met `_shadow` werkt op de gebouwen zelf (60 fps), maar valt **niet op de grond**: de
  MapLibre-basiskaart kan geen deck.gl-schaduw ontvangen. Er zijn ook lichte strepen zichtbaar (shadow acne).

## Stappen

- [x] **1. Spike: 3D BAG-tegels laden** — zie hierboven.
- [x] **2. Loader + laag in de digital twin** — sectie "3D BAG-panden" in `digital-twin/index.html`
  (na `_tryAddBuildings`), `makeBag3dLayers()` in `updateOverlay`.
  - Start in stand "3D" zodra onze panden binnen zijn. Bbox = die van onze (al op STUDY gefilterde) panden;
    per BAG-pand filtert de client met dezelfde regel als de server (middelpunt in een STUDY-zonepolygoon,
    fail-open naar de bbox). Eenmalig per gebied, 6 tegels tegelijk.
  - De extrusie blijft staan tot alle tegels verwerkt zijn, daarna gaat `buildings-3d` uit. Geschaalde modi
    en "uit" gedragen zich zoals voorheen; maquette-modus laadt niets.
  - Status in "Pand weergave": `3D BAG: x/y tegels` → `3D BAG: 9.880 panden`, of `beschikbaar (geen 3D BAG)`.
  - Attributie "3D BAG © TU Delft 3D geoinformation (CC BY 4.0)" toegevoegd.
  - Getest: De Kien → 12 tegels, 9.880 panden (wij: 10.686 OSM-panden), ~8 s; wisselen
    3D → geschaald → uit → 3D werkt; Tampere → terugval op extrusie.
- [ ] ~~**3. Tooltip en selectie**~~ — vervalt voor de digital twin (besluit 30-10-2026). In stand "3D" hebben
  panden dus geen tooltip/klikselectie; in de geschaalde modi wel. Oorspronkelijke opzet, voor als het later
  toch nodig is:
  - Pick met `unproject3D` → feature-id in de tegel → BAG-id → ons pand (`ref:bag`) → bestaande `_bTip`-tooltip
    en gele selectiecontour.
  - Point-in-polygon op onze footprints als terugval.
- [x] **4. Uiterlijk** — kleuren gevel/schuin dak/plat dak licht bijgesteld; `_b3SunTint()` kleurt ze mee met
  de zonnestand uit `updateSunLight` (`_sunState`): overdag neutraal, lage zon warmer, nacht gedempt blauwig
  (bewust mild: de Montréal-ondergrond wordt 's nachts nauwelijks donkerder).
  - Lichtrichting niet gekoppeld: dat vraagt een `LightingEffect` op de hele overlay en verandert ook auto's/bomen.
  - ~~Schaduw~~ — vervalt (besluit 30-10-2026).
- [x] **5. Terugvalpad en caching**
  - Server-proxy `GET /3dbag/<pad>` in `server.py` (`_BAG3D_VERSION = "v20250903"`): cache in
    `work/_3dbag_cache/<versie>/` (valt buiten de opruimroutine en git) en in S3 (`<prefix>_3dbag/…`),
    `Cache-Control: immutable`, padvalidatie (alleen `*.json`/`*.glb`, geen `..`).
  - Client: index via `/3dbag/tileset.json`; lukt dat niet, dan rechtstreeks `data.3dbag.nl` (getest door de
    proxy te blokkeren). Buiten NL, lege index of ≥3 mislukte tegels zonder succes → extrusie.
- [x] **6. Laden per kaartbeeld + opkomst-animatie**
  - Eenmalig de tegel-index (bbox van de STUDY-zones, anders van onze panden — hoeft niet meer op de
    panden-data te wachten), daarna per `moveend` alleen de tegels in beeld (+15 %), dichtstbijzijnde eerst,
    max. 6 tegelijk, vanaf zoom 13. Geladen tegels blijven bewaard.
  - Opkomst: per tegel `born`; `getScale` z van ~0 → 1 (easeOutBack, 900 ms). Bomen/struiken idem, uniform
    geschaald, met vaste spreiding per boom (0–0,5 s). rAF-lus alleen zolang er iets groeit;
    `prefers-reduced-motion` zet het uit. NB: constante `getScale` werkt niet in deck.gl 8.9 (instanceModelMatrix
    wordt niet herberekend) → functie-accessor + `updateTriggers`.
  - Getest (De Kien, pitch 62°): 8 van 12 tegels in beeld, alles binnen ~2,3 s na aanzetten (was ~9 s);
    pand-schaal 0,61 → 1,07 → 1; boom 0 → 1,07 → 1.

Buiten scope (eventueel aparte issues): bewegend water, hoogspanningsmasten, raamtexturen.

## Te controleren
- Deventer-geheel (grootste gebied): geheugen na veel pannen (geladen tegels worden niet opgeruimd).
- Tampere: terugval naar extrusie.
- Maquette-modus, wisselen tussen 3D en geschaald.
- Attributie: "3D BAG © TU Delft 3D geoinformation (CC BY 4.0)".
