# Plan: stoepen en fietspaden op Kaart 2 (digital twin + analyzer)

## Situatie

- De kaart toont nu geen echte stoepen. `mtl-road-sidewalk` in `common/js/montreal-basemap.js` is alleen een
  lichte rand om de weglijn (vaste breedte per wegklasse). `mtl-paths` tekent OSM-paden als dunne lijnen.
- De echte stoepen staan al in het geprepareerde **TRAFFIC-ASSETS**-bestand: BGT `wegdeel` met
  `functie = voetpad` → `assetType = "sidewalk"`, als **polygonen** (`bgt_fetcher.filter_sidewalks`).
  Ze worden nergens getekend. (`footPath`/`cyclePath` zijn andere objecten: lijnen voor de "Paden"-checkbox.)
- Beschikbaarheid per gebied:

  | gebied               | sidewalk-polygonen |
  |----------------------|--------------------|
  | Deventer - geheel    | 12.986             |
  | Lochem               | 4.241              |
  | Groenlo              | 1.406              |
  | De Kien, Den Bosch – Spoorzone | 0 (geprepareerd zonder BGT-assets) |

  Gebieden zonder BGT-assets krijgen dus geen stoepen totdat ze opnieuw met BGT-verrijking geprepareerd zijn.

## Aanpak

Eén gedeelde implementatie in `montreal-basemap.js`, omdat beide apps die module gebruiken:

- `MontrealBasemap.setSidewalks(map, featureCollection)` voegt een GeoJSON-source `mtl-sidewalks` toe met:
  - `mtl-sidewalk-fill` (fill, `p.sidewalk`) **direct onder `mtl-road-edge`**, dus boven landgebruik/water
    maar onder wegen, spoor, gebouwen en deck.gl-lagen;
  - Minzoom 15. Kleuren ook voor het nachtpalet.
- Fietspaden (`bikePath`, ook BGT-polygonen) op dezelfde manier: `mtl-bikepath-fill` in rood asfalt, boven de
  stoepen en ook onder `mtl-road-edge` (besluit 2-11-2026).
- Alleen zichtbaar in de Montréal-ondergrond ("Kaart 2"; in de DT "Kaart"), net als de andere `mtl-*`-lagen
  (besluit 2-11-2026). Voorstel om
  `mtl-road-sidewalk` (de nep-rand) te laten staan: die vult het gat waar geen BGT-stoep is.
- Data: per gebied één keer `/collections/traffic_assets/items?areaId=…&assetType=sidewalk,bikePath` (ndgeojson),
  bij het laden van het gebied en bij een gebiedswissel. Historische BGT-versies filtert de server al.
  Nieuwe query-parameter `simplify=<m>` op `traffic_assets` (beide servers): Douglas-Peucker + afronden op
  6 decimalen. Client vraagt `assetType=sidewalk,bikePath&simplify=0.1`.
- Aan/uit: checkbox **"Stoepen en fietspaden"** (standaard aan) — in de DT naast "Paden" in het '3D weergave'-blok, in de
  analyzer in het lagenpanel bij de ondergrond.

## Stappen

- [x] **1. Payload meten** (Deventer - geheel, DT-server :5001)
  - `sidewalk`: 12.986 polygonen, **1,68 mln. punten, 69 MB**, 2,9 s; `bikePath`: 1.298, 0,29 mln. punten, 11,6 MB.
    Properties zijn al gestript; het zit in de geometrie (BGT-bogen zijn fijn verdicht) en 15 decimalen.
  - Het antwoord komt **ongecomprimeerd** binnen, ondanks flask_compress (waarschijnlijk staat
    `application/geo+json` niet in `COMPRESS_MIMETYPES`, of het is een gestreamd antwoord).
  - Vereenvoudigen op ~0,1 m (1e-6°) + 6 decimalen: sidewalk 197.593 punten, **5,0 MB / 1,0 MB gzip**;
    bikePath 0,6 MB / 0,13 MB gzip. Op 0,3 m: 4,2 MB / 0,8 MB — geen groot extra voordeel.
  - Conclusie: één fetch per gebied is prima, mits server-side vereenvoudigd (en liefst gzip). Geen bbox-fetch.
- [x] **2. Server** — `simplify`-parameter in `traffic_assets` (analyzer + digital-twin `server.py`), en
  `application/geo+json` gzippen.
  - `_simplify_query_arg` / `_simplify_features`: Douglas-Peucker (`preserve_topology`) + 6 decimalen;
    0 < m ≤ 10, anders 400. Zonder bbox gecachet per (bestand, mtime, tolerantie, types).
  - `application/geo+json` en `application/x-ndgeo+json` toegevoegd aan de flask_compress-mimetypes. Dat geldt
    voor álle OGC-items-antwoorden.
  - Getest met de Flask-testclient (Deventer, `sidewalk,bikePath`, 14.284 features): zonder simplify 79 MB
    (nu 24,9 MB gzip); met `simplify=0.1` **6,6 MB → 1,2 MB over de lijn**. Eerste keer 3,2 s (DT) /
    4,4 s (analyzer), daarna uit de cache 0,2 / 0,5 s. `abc` en `50` → 400.
- [x] **2b. Basemap-lagen** — `setSidewalks` (stoepen + fietspaden) + lagen + palet in `montreal-basemap.js`.
  - Source `mtl-sidewalks` (GeoJSON, per kaart, data gedeeld). `mtl-sidewalk-fill` (`p.sidewalk`, crème) direct
    onder `mtl-road-edge`; dekt de OSM-voetpadlijnen af. `mtl-bikepath-fill` (`p.bikePath`, rood asfalt
    `#d9a596`) boven de lichte wegrand en onder het wegdek. Vanaf z15, invloeien tot z15,5.
  - `setSidewalksVisible(bool)`; `setVisible` respecteert die vlag.
  - Stoeprand-lijn (`mtl-sidewalk-kerb`) geprobeerd en weer weggehaald: de BGT-vlakken liggen in stukken naast
    elkaar, zodat elke naad een streep werd (ladder-effect). De wegrand (`mtl-road-edge`) doet nu dienst als
    stoeprand.
  - Het nachtpalet kreeg ook `bikePath`, maar wordt (nog) nergens toegepast.
  - Getest in de DT (headless, Deventer centrum, data handmatig met bbox opgehaald): stoepen en fietspaden
    zichtbaar op z16–18,5; aan/uit werkt.
- [ ] **3. Digital twin** — fetch per gebied, `setSidewalks` aanroepen, checkbox "Stoepen en fietspaden".
- [ ] **4. Analyzer** — idem.
- [ ] **5. Testen** (nog open: de nep-rand `mtl-road-sidewalk` om elke weg lijkt op een stoep; weghalen
  waar BGT-stoepen zijn?) (headless Chrome tegen :5001) — Deventer en Lochem op z15–19, dag/nacht, split-view
  `map2`, gebied zonder BGT-assets (geen fout, gewoon geen stoepen).
