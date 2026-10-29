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
 *      window.MontrealBasemap.setNetworkRoads(map, features)
 *        → tekent NETWORK-links op werkelijke breedte (na ensure()).
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

  // ── Netwerkwegen op werkelijke breedte ──────────────────────────────────
  // Wegen uit het NETWORK-bestand, getekend boven de OFM-wegen (mtl-roads) met
  // hun breedte in meters. Breedte: afgerond op 10 cm (netWidthM); verharding:
  // categorische klasse (netSurface) voor kleur/patroon.

  const _NET_WIDTH_MIN_M = 2;
  const _NET_WIDTH_MAX_M = 12;
  const _NET_EDGE_M      = 0.6;   // extra breedte van de randlijn (totaal, beide kanten)

  // Kleur per verhardingsklasse; ontbrekende klassen vallen terug op p.road.
  const _MTL_SURFACE = {
    day:   { onbekend: _MTL_PALETTES.day.road },
    night: { onbekend: _MTL_PALETTES.night.road },
  };

  // Verhardingsklasse van een link. Er is nog geen bron in het NETWORK-bestand.
  function _surfaceClass(props) {
    return 'onbekend';
  }

  // Totale wegbreedte (m): gemiddelde van min/max, anders 2× rijbaanbreedte,
  // anders 3 m per rijstrook (×2 bij een tegenrichting).
  function _netWidthM(props, hasOpposite) {
    const lo = props.roadWidthMinM, hi = props.roadWidthMaxM;
    let w;
    if (lo != null && hi != null) w = (lo + hi) / 2;
    else if (props.roadWidthM != null) w = props.roadWidthM * 2;
    else w = (props.lanes || 1) * 3 * (hasOpposite ? 2 : 1);
    w = Math.min(_NET_WIDTH_MAX_M, Math.max(_NET_WIDTH_MIN_M, w));
    return Math.round(w * 10) / 10;
  }

  // Features → ontdubbelde FeatureCollection met alleen de stijl-properties,
  // plus de gemiddelde breedtegraad (voor de meter→pixel-omrekening).
  const _netCache = new WeakMap();
  function _buildNetwork(features) {
    const cached = _netCache.get(features);
    if (cached) return cached;
    const ids = new Set(features.map(f => f.properties?.linkId));
    const seen = new Set();
    const out = [];
    let latSum = 0, latN = 0;
    for (const f of features) {
      const p = f.properties || {};
      const absId = Math.abs(p.linkId ?? 0);
      if (absId && seen.has(absId)) continue;
      if (absId) seen.add(absId);
      const hasOpposite = p.linkId != null && ids.has(-p.linkId);
      out.push({
        type: 'Feature',
        geometry: f.geometry,
        properties: { linkId: p.linkId, netWidthM: _netWidthM(p, hasOpposite), netSurface: _surfaceClass(p) },
      });
      const c = f.geometry?.coordinates?.[0];
      if (Array.isArray(c) && typeof c[1] === 'number') { latSum += c[1]; latN++; }
    }
    const result = { fc: { type: 'FeatureCollection', features: out }, lat: latN ? latSum / latN : 52 };
    _netCache.set(features, result);
    return result;
  }

  // line-width (px) voor een breedte in meters, op elke zoom correct
  // (512px-tiles: m/px = 78271,5·cos(lat) / 2^z).
  function _metersToPx(lat, extraM) {
    const k = z => Math.pow(2, z) / (78271.517 * Math.cos(lat * Math.PI / 180));
    const w = ['+', ['get', 'netWidthM'], extraM];
    return ['interpolate', ['exponential', 2], ['zoom'], 10, ['*', w, k(10)], 22, ['*', w, k(22)]];
  }

  // Vereist dat ensure() al gedraaid heeft (de lagen komen boven mtl-roads);
  // anders gebeurt er niets en moet de aanroeper het na ensure() herhalen.
  function setNetworkRoads(m, features, theme = 'day') {
    if (!m || !Array.isArray(features) || !m.getLayer('mtl-roads')) return;
    const { fc, lat } = _buildNetwork(features);
    const p = _MTL_PALETTES[theme] || _MTL_PALETTES.day;
    const surf = _MTL_SURFACE[theme] || _MTL_SURFACE.day;
    const surfaceColor = ['match', ['get', 'netSurface'],
      ...Object.entries(surf).flat(), p.road];

    const src = m.getSource('mtl-network');
    if (src) src.setData(fc);
    else m.addSource('mtl-network', { type: 'geojson', data: fc });

    // Direct boven mtl-roads (onder de OFM-markeringen en alle eigen lagen).
    const layers = m.getStyle().layers;
    const roadsIdx = layers.findIndex(l => l.id === 'mtl-roads');
    const beforeId = roadsIdx >= 0 ? layers[roadsIdx + 1]?.id : undefined;
    const visibility = m.getLayoutProperty('mtl-roads', 'visibility') || 'visible';
    const layout = { 'line-cap': 'round', 'line-join': 'round', visibility };

    const defs = [
      { id: 'mtl-net-edge', paint: { 'line-color': p.line,       'line-width': _metersToPx(lat, _NET_EDGE_M) } },
      { id: 'mtl-net-road', paint: { 'line-color': surfaceColor, 'line-width': _metersToPx(lat, 0) } },
    ];
    for (const { id, paint } of defs) {
      if (m.getLayer(id)) {
        for (const [k, v] of Object.entries(paint)) m.setPaintProperty(id, k, v);
      } else {
        m.addLayer({ id, type: 'line', source: 'mtl-network', layout, paint }, beforeId);
      }
    }
  }

  window.MontrealBasemap = { palettes: _MTL_PALETTES, ensure, setVisible, hiddenBaseLayerIds, setNetworkRoads };
})();
