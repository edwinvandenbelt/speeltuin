# Plan: wegbreedte en verharding uit het NETWORK-bestand in 'Kaart 2'

## Situatie

'Kaart 2' (Montréal-ondergrond, `common/js/montreal-basemap.js`) tekent de wegen uit de
OpenFreeMap-tiles, met vaste pixelbreedtes per OSM-klasse. Het NETWORK-bestand heeft
`roadWidthM` (de rijbaan, ongeveer de helft van de weg) en `roadWidthMinM` /
`roadWidthMaxM` (de totale wegbreedte). Sinds gmt_network_enrichment 0.6.0 heeft het
ook `surface` (ruwe OSM-waarde, via `osm.road_enricher`).

Deventer - geheel, CAR, 6488 unieke links (min/max bekend bij 5621):
- p10 = 3,2 m, mediaan = 4,95 m, p90 = 7,1 m, p99 = 10 m.
- Per 10 cm afgerond zijn dat 117 verschillende waarden.

Goor (met road-enricher), 1734 links: paving_stones 750, asphalt 609, geen 327, rest < 20.

## Aanpak: de vectortiles zelf verrijken (geen overlay)

Eerste poging was een overlay: de netwerklinks als eigen GeoJSON-laag over de kaart
tekenen. **Vervallen** — de kaart zelf moet de breedte en verharding tonen.

Nieuwe aanpak: de OFM-tiles voor de wegen gaan via een eigen protocol
(`maplibregl.addProtocol('mtlnet', …)`):

1. De echte tile ophalen bij OpenFreeMap (de tile-URL uit de TileJSON van de Liberty-source).
2. Alleen de laag `transportation` uitpakken; alle andere lagen worden byte voor byte
   doorgegeven. Eigen mini-MVT-reader/-writer, geen externe bibliotheken.
3. Per weg-feature (de wegklassen van `mtl-roads`) de geometrie in stukjes van ≤ 10 m
   hakken; per stukje de dichtstbijzijnde netwerklink zoeken (≤ 8 m, hoekverschil
   ≤ 30°) via een ruimtelijk raster. Stem op lengte.
4. Als ≥ 50 % van de feature-lengte gematcht is: de winnende link levert
   `netSurface` (klasse) en `netWidthM` als extra properties op de feature.
5. Tile weer inpakken en teruggeven.

Stijl (`mtl-road-edge`, `mtl-road-sidewalk`, `mtl-roads`):
- Breedte: `interpolate` (exponentieel, grondtal 2) op zoom, per stop
  `case has(netWidthM) → meters × k(z) | huidige klassebreedte`, met
  k = 2^z / (78271,5·cos lat). Randen: +0,4 m (sidewalk) en +0,9 m (edge), ongeveer de
  huidige verhoudingen.
- Kleur `mtl-roads`: `match` op `netSurface` via `_MTL_SURFACE`; zonder → `p.road`.

Breedte: afgerond op 10 cm, begrensd op 2–12 m. Verharding: klasse via de tabel:

| klasse        | OSM `surface`                                                |
|---------------|--------------------------------------------------------------|
| `asfalt`      | asphalt, paved, chipseal                                     |
| `klinkers`    | paving_stones, sett, bricks, cobblestone, unhewn_cobblestone |
| `beton`       | concrete, concrete:plates, concrete:lanes                    |
| `halfverhard` | compacted, fine_gravel, gravel, pebblestone                  |
| `onverhard`   | unpaved, ground, dirt, earth, grass, sand, mud               |
| `onbekend`    | `None` / overig                                              |

Bekende beperkingen:
- Een OFM-weg die over links met verschillende verharding loopt, krijgt één waarde
  (de meerderheid). Opknippen is een latere stap.
- OFM levert tot z14; daarboven wordt overzoomd, dus er worden weinig tiles bewerkt.
- Komt het netwerk binnen nadat tiles al geladen zijn, dan wordt de wegen-source
  herladen (nieuwe tile-URL-versie; de browsercache levert de tile opnieuw).

## Stappen

- [x] 0. (Vervallen) Overlay `setNetworkRoads` met lagen `mtl-net-*`. Wordt verwijderd
      in stap 1.
- [x] 1. `montreal-basemap.js`:
  - Overlay-code weg (`setNetworkRoads`, `mtl-network`, `mtl-net-*`).
  - `setNetwork(features)`: links ontdubbelen op |linkId|, per link `netWidthM` en
    `netSurface`, ruimtelijk raster in wereldcoördinaten; daarna de wegen-source van
    alle bekende kaarten herladen.
  - Protocol `mtlnet` + mini-MVT-reader/-writer + matching.
  - In `ensure()`: eigen vector-source `mtl-ofm-roads` (`mtlnet://…`, maxzoom 14) voor de
    `transportation`-lagen; de stijlexpressies voor breedte en kleur.
- [x] 2. `digital-twin/index.html`: na het laden van het netwerk `setNetwork(...)`
      aanroepen (bij MIXED alleen CAR). De aanroepen van `setNetworkRoads` weg.
- [ ] 3. Testen: Goor en Deventer, Kaart 2 van z12 tot z19, vergelijken met de luchtfoto;
      tijd per tile meten; wisselen tussen de ondergronden; map2/3D-view; gebied zonder
      netwerk ongewijzigd.
- [x] 4. Analyzer: `montreal-basemap.js` gebruiken in plaats van de eigen kopie, en
      `setNetwork` aanroepen (ook na het herladen van een scenario). Deploy-scripts
      van analyzer en digital-twin nemen `montreal-basemap.js` nu mee.
- [ ] 5. Data: de oudere NETWORK-parquets in `work/` hebben nog geen `surface`; de
      road-enricher zit in de PBF-pipeline (buiten deze repo). Goor heeft het al.
- [ ] 6. (Later) OFM-wegen opknippen waar de verharding binnen één weg wisselt.
