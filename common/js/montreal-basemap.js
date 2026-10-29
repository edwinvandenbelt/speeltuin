/**
 * montreal-basemap.js — Montréal-ondergrond voor MapLibre-kaarten met de
 * OpenFreeMap Liberty-stijl (analyzer, digital-twin).
 *
 * Port van de stijl van allemannsdata.com/examples/montreal_kart (functie Ct +
 * palet St in hun bundle), zonder terrein, gebouwen en POI's. De lagen
 * gebruiken dezelfde OpenFreeMap-vectorsource als Liberty en worden als
 * 'mtl-*'-lagen in de bestaande stijl gezet, zodat eigen lagen blijven staan.
 *
 * API: window.MontrealBasemap.ensure(map, libertyLayerIds)
 *        → voegt de lagen (verborgen) toe als ze nog ontbreken.
 *      window.MontrealBasemap.setVisible(map, bool)
 *      window.MontrealBasemap.hiddenBaseLayerIds(map)
 *        → Set met Liberty-lagen die in Montréal-modus uit moeten.
 */
(function () {
  'use strict';

  const _MTL_PALETTES = {
    day:   { land:'#e6e9dc', water:'#8fc7ca', green:'#b8c99e', forest:'#acbf97', road:'#c9cec5',
             sidewalk:'#f4f1e4', line:'#91a197', marking:'#f2d373', laneMarking:'#fffdf3' },
    night: { land:'#111c29', water:'#081321', green:'#162b29', forest:'#142522', road:'#26313b',
             sidewalk:'#3c454a', line:'#101b25', marking:'#8c805f', laneMarking:'#76868c' },
  };

  function _montrealLayers(src, p) {
    const roads = ['all', ['==', '$type', 'LineString'],
      ['in', 'class', 'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor', 'service', 'busway', 'bus_guideway'],
      ['!=', 'brunnel', 'tunnel']];
    const twoWay = ['all', roads, ['!in', 'oneway', 1, -1]];
    const oneWay = ['all', roads, ['in', 'oneway', 1, -1]];
    const byClass = (big, mid, other, service) => ['match', ['get', 'class'],
      ['motorway', 'trunk'], big, ['primary', 'secondary'], mid, 'service', service, other];
    const width = (a, b, c) => ['interpolate', ['exponential', 2], ['zoom'], 12, a, 16, b, 19, c];
    const round = { 'line-cap': 'round', 'line-join': 'round' };
    const butt  = { 'line-cap': 'butt',  'line-join': 'round' };
    const tr = { source: src, 'source-layer': 'transportation' };
    return [
      { id: 'mtl-ground', type: 'background', paint: { 'background-color': p.land } },
      { id: 'mtl-woodland', type: 'fill', source: src, 'source-layer': 'landcover',
        filter: ['in', 'class', 'wood', 'grass'], paint: { 'fill-color': p.forest, 'fill-opacity': 0.55 } },
      { id: 'mtl-green-land', type: 'fill', source: src, 'source-layer': 'landuse',
        filter: ['in', 'class', 'grass', 'cemetery', 'recreation_ground', 'village_green'],
        paint: { 'fill-color': p.green } },
      { id: 'mtl-parks', type: 'fill', source: src, 'source-layer': 'park',
        paint: { 'fill-color': p.green, 'fill-opacity': 0.7 } },
      { id: 'mtl-water', type: 'fill', source: src, 'source-layer': 'water', paint: { 'fill-color': p.water } },
      { id: 'mtl-waterways', type: 'line', source: src, 'source-layer': 'waterway',
        paint: { 'line-color': p.water, 'line-width': 2 } },
      { id: 'mtl-shore', type: 'line', source: src, 'source-layer': 'water',
        paint: { 'line-color': p.sidewalk, 'line-width': 0.8, 'line-opacity': 0.5 } },
      { id: 'mtl-paths', type: 'line', ...tr, minzoom: 15, layout: round,
        filter: ['all', ['==', '$type', 'LineString'], ['in', 'class', 'path', 'track'],
                 ['!=', 'brunnel', 'tunnel'], ['!=', 'indoor', 1]],
        paint: { 'line-color': p.road, 'line-opacity': 0.65,
                 'line-width': ['interpolate', ['exponential', 2], ['zoom'], 15, 0.5, 19, 5] } },
      { id: 'mtl-road-edge', type: 'line', ...tr, filter: roads, layout: round,
        paint: { 'line-color': p.line,
                 'line-width': width(byClass(3.2, 2.7, 2, 1), byClass(12, 10.5, 9, 5.5), byClass(68, 56, 46, 28)) } },
      { id: 'mtl-road-sidewalk', type: 'line', ...tr, filter: roads, layout: round,
        paint: { 'line-color': p.sidewalk,
                 'line-width': width(byClass(2.6, 2.1, 1.5, 0.75), byClass(10, 8.5, 7, 4), byClass(62, 50, 40, 24)) } },
      { id: 'mtl-roads', type: 'line', ...tr, filter: roads, layout: round,
        paint: { 'line-color': p.road,
                 'line-width': width(byClass(1.8, 1.4, 1, 0.5), byClass(8, 6.5, 5, 2.8), byClass(56, 44, 36, 20)) } },
      { id: 'mtl-road-centre-major', type: 'line', ...tr, minzoom: 16.5, layout: butt,
        filter: ['all', twoWay, ['in', 'class', 'primary', 'secondary']],
        paint: { 'line-color': p.marking, 'line-opacity': 0.94,
                 'line-width':     ['interpolate', ['linear'], ['zoom'], 16.5, 0.8, 19, 1.8],
                 'line-gap-width': ['interpolate', ['linear'], ['zoom'], 16.5, 0.7, 19, 2.2] } },
      { id: 'mtl-road-markings', type: 'line', ...tr, minzoom: 17, layout: butt,
        filter: ['all', twoWay, ['in', 'class', 'tertiary', 'minor']],
        paint: { 'line-color': p.marking, 'line-opacity': 0.9, 'line-dasharray': [6, 5],
                 'line-width': ['interpolate', ['linear'], ['zoom'], 17, 1, 19, 1.8] } },
      { id: 'mtl-road-lane-dividers', type: 'line', ...tr, minzoom: 17, layout: butt,
        filter: ['all', oneWay, ['in', 'class', 'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor']],
        paint: { 'line-color': p.laneMarking, 'line-opacity': 0.94, 'line-dasharray': [6, 5],
                 'line-width': ['interpolate', ['linear'], ['zoom'], 17, 1, 19, 1.9] } },
    ];
  }

  // Voegt de 'mtl-*'-lagen (verborgen) toe aan een kaart, direct boven de
  // Liberty-achtergrond zodat ze onder alle eigen lagen liggen.
  function _vectorSource(style) {
    return Object.keys(style.sources).find(k => {
      const s = style.sources[k];
      return s.type === 'vector' && /openfreemap|openmaptiles/.test(String(s.url || k));
    }) || 'openmaptiles';
  }

  // Ids van de Liberty-ondergrondlagen die in Montréal-modus uit moeten:
  // achtergrond + alle niet-label-lagen op de OpenFreeMap-source. Eigen lagen
  // (andere sources) en labels (symbol) blijven dus ongemoeid.
  function hiddenBaseLayerIds(m) {
    const style = m.getStyle();
    const src = _vectorSource(style);
    return new Set(style.layers
      .filter(l => !l.id.startsWith('mtl-'))
      .filter(l => l.type === 'background' || (l.source === src && l.type !== 'symbol'))
      .map(l => l.id));
  }

  function ensure(m, libertyLayerIds) {
    if (m.getLayer('mtl-ground')) return;
    const style = m.getStyle();
    const src = _vectorSource(style);
    const liberty = new Set(libertyLayerIds || []);
    const beforeId = style.layers.find(l => liberty.has(l.id) && l.type !== 'background')?.id;
    for (const layer of _montrealLayers(src, _MTL_PALETTES.day)) {
      layer.layout = { ...(layer.layout || {}), visibility: 'none' };
      m.addLayer(layer, beforeId);
    }
  }

  function setVisible(m, visible) {
    for (const l of m.getStyle().layers) {
      if (l.id.startsWith('mtl-')) m.setLayoutProperty(l.id, 'visibility', visible ? 'visible' : 'none');
    }
  }

  window.MontrealBasemap = { palettes: _MTL_PALETTES, ensure, setVisible, hiddenBaseLayerIds };
})();
