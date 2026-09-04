# CIMLK hoogte-/constructie-objecten — data-contract voor de gmt-library

## Doel

Vastleggen hoe de **gmt-calculation-lib** CIMLK-constructieobjecten (viaducten,
bruggen, tunnels, keermuren, duikers, geluidsschermen en onderdoorgangen) moet
aanleveren, zodat de speeltuin-viewer ze automatisch 2.5D kan renderen.

De viewer-rendering is al geïmplementeerd (`index.html`,
`makeHeightAssetLayers`). Zodra de library rijen met de juiste `assetType` en
properties in het TRAFFIC-ASSETS-bestand zet, verschijnen ze bij inzoomen
(zoom ≥ 16) met de laag "verkeersobjecten" actief. **Geen serverwijziging
nodig**: de OGC-endpoint `traffic_assets` geeft alle parquet-kolommen
ongefilterd door als GeoJSON-properties.

---

## Aanlevering

- **Bestand:** `{areaId}-TRAFFIC-ASSETS.parquet` (zelfde bestand als borden,
  verkeerslichten, straatmeubilair enz.).
- **Geometrie:** `LineString` (of `MultiLineString`) in **WGS84 / EPSG:4326**,
  langs de as van het wegvak/de constructie.
- **Discriminator:** kolom **`assetType`** (camelCase, exact zoals hieronder).
- **Properties:** camelCase kolomnamen. Onbekende/extra kolommen zijn toegestaan
  (verschijnen in de hover-tooltip) maar worden niet gebruikt voor rendering.

---

## Types en velden

| `assetType`     | Geometrie   | Rendering in viewer                                   | Gebruikte properties        |
|-----------------|-------------|-------------------------------------------------------|-----------------------------|
| `viaduct`       | LineString  | Verhoogde grijze wegdek-ribbon op z = `heightM`       | `heightM`, `belowGround`    |
| `bridge`        | LineString  | Lichter betongrijs brugdek op z = `heightM`           | `heightM`, `belowGround`    |
| `tunnel`        | LineString  | Donkere dekband op wegniveau + doorschijnend dak op z = `heightM` | `heightM`         |
| `screen`        | LineString  | Geëxtrudeerde dunne muur (geluidsscherm), hoogte `heightM` | `heightM`, `belowGround` |
| `retainingWall` | LineString  | Dikkere geëxtrudeerde betonmuur (keermuur), hoogte `heightM` | `heightM`              |
| `culvert`       | LineString  | Lage smalle donkere kruising op wegniveau (duiker)    | —                           |
| `underpass`     | LineString  | Doorschijnende overspanning die boven de weg zweeft   | `heightM`                   |

### Property-definities

| Property      | Type    | Eenheid | Betekenis | Fallback in viewer |
|---------------|---------|---------|-----------|--------------------|
| `heightM`     | number  | meter   | Voor `viaduct`/`bridge`/`underpass`: hoogte van het wegdek/de overspanning boven maaiveld. Voor `tunnel`: vrije hoogte van het tunneldak. Voor `screen`/`retainingWall`: hoogte van de muur. | viaduct 1.0, bridge 1.5, tunnel 4.5, screen 3.0, retainingWall 2.0, underpass 4.0 |
| `belowGround` | boolean | —       | `true` = de constructie ligt verdiept / de weg gaat eronderdoor. Zie hieronder. | `false` |

---

## `belowGround` en onderdoorgangen

De viewer maakt onderscheid tussen "de weg gaat eroverheen" en "de weg gaat
eronderdoor":

- `viaduct`/`bridge` met `belowGround` = `false` → getekend als **verhoogd
  wegdek** (de weg gaat eroverheen).
- `viaduct`/`bridge` met `belowGround` = `true` → getekend als **`underpass`**:
  een doorschijnende overspanning die op `heightM` (fallback 4.0 m) boven de
  verdiepte weg zweeft.
- `assetType` = `underpass` mag ook direct worden aangeleverd (identiek gedrag).
- `screen` met `belowGround` = `true` wordt **niet** getekend (scherm hoort bij
  een verdiept tracé dat niet zichtbaar is).

Kies bij voorkeur **één** conventie:
- **Aanbevolen:** lever `viaduct`/`bridge` met een correcte `belowGround`-vlag
  en laat de viewer de `underpass`-weergave afleiden.
- Alternatief: lever expliciete `underpass`-rijen.

---

## Voorbeeld-features (GeoJSON-equivalent)

```jsonc
// Viaduct dat over een kruising heen gaat
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[6.01,52.16],[6.012,52.161]] },
  "properties": { "assetType": "viaduct", "heightM": 5.5, "belowGround": false } }

// Weg die onder een viaduct doorgaat → onderdoorgang
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[6.02,52.16],[6.022,52.16]] },
  "properties": { "assetType": "viaduct", "heightM": 4.5, "belowGround": true } }

// Tunnel
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[6.03,52.15],[6.035,52.151]] },
  "properties": { "assetType": "tunnel", "heightM": 4.2 } }

// Keermuur langs verdiepte bak
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[6.04,52.15],[6.041,52.152]] },
  "properties": { "assetType": "retainingWall", "heightM": 2.5 } }

// Duiker onder de weg
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[6.05,52.14],[6.0505,52.14]] },
  "properties": { "assetType": "culvert" } }
```

---

## Renderconstanten (viewer, ter referentie)

Gedefinieerd in `index.html` (`makeHeightAssetLayers`-blok); pas hier aan als de
proporties bijgesteld moeten worden:

| Constante              | Waarde | Betekenis                              |
|------------------------|--------|----------------------------------------|
| `_TA_VIADUCT_WIDTH_M`  | 7.5 m  | breedte viaduct-ribbon                 |
| `_TA_BRIDGE_WIDTH_M`   | 7.5 m  | breedte brugdek                        |
| `_TA_TUNNEL_WIDTH_M`   | 8.0 m  | breedte tunnelbuis-band                |
| `_TA_TUNNEL_DEF_H`     | 4.5 m  | fallback tunneldak-hoogte              |
| `_TA_SCREEN_HALF_M`    | 0.15 m | halve dikte geluidsscherm              |
| `_TA_SCREEN_DEF_H`     | 3 m    | fallback schermhoogte                  |
| `_TA_RETWALL_HALF_M`   | 0.30 m | halve dikte keermuur                   |
| `_TA_RETWALL_DEF_H`    | 2 m    | fallback keermuurhoogte                |
| `_TA_CULVERT_WIDTH_M`  | 2.5 m  | breedte duiker-kruising                |
| `_TA_UNDERPASS_H_M`    | 4.0 m  | zweefhoogte overspanning bij onderdoorgang |

Alle objecten zijn zichtbaar vanaf zoomniveau `_TA_MINZOOM` (16) wanneer de
laag "verkeersobjecten" actief is.
