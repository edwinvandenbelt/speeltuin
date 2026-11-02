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
