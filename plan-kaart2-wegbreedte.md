# Plan: wegbreedte (en later verharding) uit het NETWORK-bestand in 'Kaart 2'

## Situatie

'Kaart 2' (Montréal-ondergrond, `common/js/montreal-basemap.js`) tekent de wegen uit de
OpenFreeMap-tiles, met vaste pixelbreedtes per OSM-klasse. Het NETWORK-bestand heeft
`roadWidthM` (de rijbaan, ongeveer de helft van de weg) en `roadWidthMinM` /
`roadWidthMaxM` (de totale wegbreedte).

Deventer - geheel, CAR, 6488 unieke links (min/max bekend bij 5621):
- p10 = 3,2 m, mediaan = 4,95 m, p90 = 7,1 m, p99 = 10 m.
- Per 10 cm afgerond zijn dat 117 verschillende waarden.

## Keuze: klassen voor de verharding, een afgeronde waarde voor de breedte

- **Breedte:** wordt afgerond op 10 cm en begrensd op 2–12 m (`netWidthM`). Er komt geen
  lookup-tabel: de omrekening van meters naar pixels per zoomniveau is toch al één
  data-gestuurde expressie.
- **Verharding:** krijgt een categorische klasse (`netSurface`), met `match` voor kleur en
  later een patroon. Voorlopig is de waarde altijd `'onbekend'`.

## Stappen

- [x] 1. `montreal-basemap.js`: `setNetworkRoads(map, features)`
  - Links ontdubbelen op |linkId|.
  - `netWidthM` bepalen: het gemiddelde van min en max, anders `roadWidthM × 2`, anders
    `lanes × 3` (×2 bij tegenrichting). Afronden op 0,1 en begrenzen op 2–12.
  - `netSurface` bepalen via `_surfaceClass(props)`. Dat geeft nu altijd `'onbekend'`.
  - Een GeoJSON-source `mtl-network` en de lagen `mtl-net-edge` en `mtl-net-road`,
    direct boven `mtl-roads`.
  - Breedte: `interpolate` (exponentieel, grondtal 2) op zoom, met meters × k(z), waarbij
    k = 2^z / (78271,5·cos lat).
  - Kleur: `match` op `netSurface` via `_MTL_SURFACE` (`onbekend → p.road`).
- [x] 2. `digital-twin/index.html`: `setNetworkRoads` aanroepen na het laden van het
      netwerk, voor `map` en `map2`. Bij MIXED alleen de CAR-features meegeven. Ook
      aanroepen in `_applyBasemapStyle` na `ensure()`.
- [ ] 3. Testen: Deventer, Kaart 2 van z12 tot z19 en vergelijken met de luchtfoto,
      wisselen tussen de ondergronden, map2/3D-view, en de analyzer op Kaart 2 zonder
      fouten.
- [ ] 4. (Later) Echte verhardingsbron in `_surfaceClass` met de bijbehorende kleuren of
      patronen. Daarnaast apart besluiten over het verbergen van OFM-wegen en markeringen
      binnen het netwerkgebied.
