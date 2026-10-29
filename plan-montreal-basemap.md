# Plan: Montréal-achtergrond als extra basemap-keuze

Bron: de functie `Ct(theme)` in de bundle van allemannsdata.com/examples/montreal_kart.
Deze functie bouwt de stijl in code op. Er is dus geen style.json. Kleuren staan in het
palet `St` (day/evening/night). De tiles zijn dezelfde OpenFreeMap-tiles die Liberty
gebruikt.

## Aanpak

De analyzer wisselt van achtergrond door **lagen aan en uit te zetten** binnen de
Liberty-stijl, en dus niet met `setStyle`. Zo blijven de eigen lagen (verkeer,
gebouwen enzovoort) staan. Daarom voegen we de Montréal-lagen toe als een extra set
lagen met het voorvoegsel `mtl-` op de bestaande Liberty-source. In de modus
`montreal` gaan de Liberty-lagen uit en de `mtl-*`-lagen aan.

We nemen over: ground, woodland, green-land, parks, water, waterways, shore, paths,
road-edge, road-sidewalk, roads, road-centre-major, road-markings en
road-lane-dividers, plus de straatnamen.

We nemen niet over: terrain/hillshade (externe DEM), gebouwen (de analyzer heeft eigen
gebouwlogica), POI-iconen, bomen, auto's, fietsers, OV en de React-shell.

## Stappen

- [x] 1. Het palet `St` en een functie `_buildMontrealLayers(sourceId, palette)` toevoegen
      bij `_applyBasemapStyle`. Dit is een port van `Ct` zonder terrain en gebouwen.
- [x] 2. De lagen toevoegen aan `map` en `map2` op het load-moment, direct boven de
      Liberty-achtergrond en onder de eigen lagen. Standaard staan ze op `visibility: none`.
- [x] 3. `_applyBasemapStyle`: de nieuwe waarde `'montreal'` verbergt de Liberty-lagen en
      toont de `mtl-*`-lagen. Bij alle andere modi gaan de `mtl-*`-lagen uit.
- [x] 4. In de UI een radio-optie toevoegen aan `lmpBasemap` (common/js/left-menu-panel.js; `spBasemap` bestaat niet meer in de HTML), alleen als `window._basemapSupportsMontreal`, plus de
      i18n-sleutel `settingsBasemapMontreal` in NL, EN en FI.
- [ ] 5. Dag/nacht: als `_applyGroundNightTint(false)` actief is en de modus `montreal`
      is, het `night`-palet zetten via `setPaintProperty`, anders `day`.
- [ ] 6. Testen: wisselen tussen alle modi, de 3D-view (map2), gebouwradio's, nachttint
      en herladen met de opgeslagen keuze.

## Digital twin

- [x] 7. De lagen naar `common/js/montreal-basemap.js` verplaatst, zodat analyzer en
      digital twin dezelfde code gebruiken.
- [x] 8. Digital twin: "Kaart" (`'map'`) toont de Montréal-ondergrond. De nachttint
      staat daar voorlopig uit, want die zou ook water en wegen donker maken.
      Een opgeslagen `'montreal'` wordt als `'map'` gelezen.
- [ ] 9. Testen in de digital twin: alle ondergrond-opties, maquette-modus, 3D-view.
