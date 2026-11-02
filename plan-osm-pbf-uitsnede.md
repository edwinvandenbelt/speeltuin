# Plan: kleine PBF-uitsnede als een gebied over een extractgrens valt

## Aanleiding (2026-11-02)
Voor "Deventer - geheel" valt de netwerk-bbox (6,113–6,219 / 52,228–52,274) over de grens Overijssel/Gelderland.
`resolve_or_download_pbf` kiest dan het kleinste extract dat de hele bbox dekt: `netherlands.osm.pbf` (1,4 GB).
De achtergrondjobs voor gebouwen, vegetatie en verkeersobjecten lezen dat bestand met de pure-Python reader
van `gmt_shared` (pyosmium was niet geïnstalleerd), per query in meerdere volledige passes. Ze lopen
daardoor zo lang dat er nooit een `{area}-BUILDINGS.geojson` of `{area}-VEGETATION.geojson` ontstond.

Gekozen: pyosmium installeren. `gmt_shared` gebruikt daardoor automatisch zijn C++-backend, voor alle
OSM-queries (ook in de prepare-pipeline). Daarnaast wordt per bbox eenmalig een uitsnede gemaakt.

## Stappen
- [x] `osmium` (pyosmium 4.3.2) in de root-`.venv`; `osmium>=4.0` toegevoegd aan `digital-twin/requirements.txt`
      en `analyzer/requirements.txt`.
- [x] `scripts/geofabrik_pbf.py`:
  - `bbox_crosses_extract_border`: geeft True als een kleiner registry-extract de bbox raakt.
  - `clip_pbf_to_bbox`: de uitsnede. Bevat de nodes in de bbox (+ ~1 km marge), de ways met minstens één
    van die nodes (compleet), en multipolygon-relaties met een lid in de bbox (compleet). Grens- en
    routerelaties blijven bewust weg.
  - `clipped_pbf_for_bbox`: cachet de uitsnede in `{OSM_PBF_CACHE_DIR}/clips/`. Hij wordt opnieuw
    gemaakt als het bronextract nieuwer is. Een lock per uitsnede zorgt dat gelijktijdige jobs op één
    uitsnede wachten. Bij een fout wordt het volledige extract gebruikt.
- [x] `_resolve_local_pbf` in `digital-twin/server.py` en `analyzer/server.py` gebruikt
      `clipped_pbf_for_bbox`. Een expliciet `OSM_PBF_PATH` blijft ongewijzigd.
- [ ] Uitsnede Deventer meten: duur, grootte, en controleren dat alle way-nodes erin zitten.
- [ ] Servers herstarten (de draaiende servers kennen de nieuwe code nog niet) en in de DT voor Deventer
      gebouwen, Bomen en verkeersborden aanzetten. Verwachting: de jobs worden `successful` en
      `{area}-BUILDINGS.geojson`/`-VEGETATION.geojson` verschijnen in `work/Deventer - geheel/`.
- [ ] Een gebied binnen één provincie (bijv. Lochem): er wordt geen uitsnede gemaakt, het gedrag is ongewijzigd.

## Open (bewust niet gedaan)
- Waarom het hele land wordt gekozen en niet Overijssel + Gelderland samen: zo laten.
- `digital-twin/test-deploy/` en `analyzer/test-deploy/` bevatten kopieën van `scripts/`; die worden bij
  de deploy ververst.

## Vervolg (2026-11-02): naar gmt-shared
- De uitsnede-logica staat nu in `gmt_shared.geofabrik` (gmt-shared 0.5.5), zodat ook de prepare-pipeline
  (gmt-calculation-lib) en de road_enricher hem gebruiken. `scripts/geofabrik_pbf.py` is een dunne laag erover.
- Een bbox over een provinciegrens gebruikt nu Overijssel + Gelderland (beide uitgesneden en samengevoegd)
  in plaats van heel Nederland; Nederland is alleen nog de terugvaloptie (> 2 provincies). Er wordt altijd
  een uitsnede gemaakt, ook binnen één provincie en van een expliciet `OSM_PBF_PATH`.
- De node-pass decodeert DenseNodes met numpy: Harderwijk (Gelderland + Flevoland) 11 s, uit NL 39 s.
- De dekkingscheck voor een expliciet `OSM_PBF_PATH` (provinciegrenzen, anders PBF-header) zit nu ook in
  gmt-shared.
- Na de release van gmt-shared 0.5.5 moet de `gmt_shared`-wheel in de repo-root worden vervangen; met de
  oude wheel valt de import weg en gebruiken de servers de Overpass-API.
