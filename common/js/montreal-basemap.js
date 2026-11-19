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
 *      window.MontrealBasemap.setNetwork(features)
 *        → NETWORK-links (GeoJSON) waarmee de wegen in de tiles breedte en
 *          verharding krijgen; geldt voor alle kaarten.
 *      window.MontrealBasemap.setSidewalks(features)
 *        → BGT-stoepen en -fietspaden (TRAFFIC-ASSETS, assetType 'sidewalk' /
 *          'bikePath', polygonen); geldt voor alle kaarten.
 *      window.MontrealBasemap.setSidewalksVisible(bool)
 *        → stoepen/fietspaden aan of uit (alleen zichtbaar in Montréal-modus).
 *      window.MontrealBasemap.setSeason(map, month)
 *        → kleurt het gras/de begroeiing naar het seizoen van `month` (1–12);
 *          herfst = de oorspronkelijke paletkleur.
 */
(function () {
  'use strict';

  const _MTL_PALETTES = {
    day:   { land:'#e6e9dc', water:'#8fc7ca', green:'#b8c99e', forest:'#acbf97', road:'#c9cec5',
             sidewalk:'#ddd3b8', kerb:'#b3a98c', shore:'#f4f1e4', line:'#91a197', marking:'#f2d373', laneMarking:'#fffdf3',
             railBed:'#bdb5aa', railTie:'#8c8073', rail:'#5b6066', bikePath:'#d9a596' },
    night: { land:'#111c29', water:'#081321', green:'#162b29', forest:'#142522', road:'#26313b',
             sidewalk:'#515d63', kerb:'#3a434a', shore:'#3c454a', line:'#101b25', marking:'#8c805f', laneMarking:'#76868c',
             railBed:'#2c3238', railTie:'#3a3530', rail:'#7a838c', bikePath:'#4a3433' },
  };

  // Seizoenskleuren voor het gras ('mtl-green-land'/'mtl-parks') en de
  // begroeiing ('mtl-woodland') — 'herfst' is de bestaande (hierboven
  // gedefinieerde) kleur, dus niet apart herhaald.
  const _GRASS_SEASON_COLORS = {
    spring: { green: '#a9d37a', forest: '#9cc073' }, // fris voorjaarsgroen
    summer: { green: '#8fb662', forest: '#84ab5d' }, // iets donkerder dan het voorjaar
    winter: { green: '#c2a855', forest: '#b79a52' }, // geel-bruin-groenig
  };
  function _seasonOfMonth(month) {
    if (month >= 3 && month <= 5)  return 'spring';
    if (month >= 6 && month <= 8)  return 'summer';
    if (month >= 9 && month <= 11) return 'autumn';
    return 'winter';
  }
  /** Past de gras-/begroeiingskleur van de Montréal-ondergrond aan op het
   *  seizoen van `month` (1–12); herfst = de oorspronkelijke paletkleur. */
  function setSeason(m, month) {
    if (!m) return;
    const season = _seasonOfMonth(month);
    const colors = season === 'autumn'
      ? { green: _MTL_PALETTES.day.green, forest: _MTL_PALETTES.day.forest }
      : _GRASS_SEASON_COLORS[season];
    for (const id of ['mtl-green-land', 'mtl-parks']) {
      if (m.getLayer(id)) { try { m.setPaintProperty(id, 'fill-color', colors.green); } catch (_) {} }
    }
    if (m.getLayer('mtl-woodland')) { try { m.setPaintProperty('mtl-woodland', 'fill-color', colors.forest); } catch (_) {} }
  }

  // roadSrc: source voor de transportation-lagen (mtl-ofm-roads, met de
  // netwerk-properties), of de OFM-source zelf als dat niet lukt.
  function _montrealLayers(src, p, roadSrc = src) {
    const roads = ['all', ['==', '$type', 'LineString'],
      ['in', 'class', 'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor', 'service', 'busway', 'bus_guideway'],
      ['!=', 'brunnel', 'tunnel']];
    const twoWay = ['all', roads, ['!in', 'oneway', 1, -1]];
    const oneWay = ['all', roads, ['in', 'oneway', 1, -1]];
    const byClass = (big, mid, other, service) => ['match', ['get', 'class'],
      ['motorway', 'trunk'], big, ['primary', 'secondary'], mid, 'service', service, other];
    // Breedte per klasse (px op z12/16/19); wegen met netWidthM krijgen hun
    // werkelijke breedte: m · netK · 2^z px. Exponentieel grondtal 2 tussen
    // de stops is daarvoor exact.
    const width = (a, b, c) => {
      const at = (z, px) => ['case', ['has', 'netWidthM'],
        ['*', ['get', 'netWidthM'], ['get', 'netK'], Math.pow(2, z)], px];
      return ['interpolate', ['exponential', 2], ['zoom'], 12, at(12, a), 16, at(16, b), 19, at(19, c), 22, at(22, c)];
    };
    // Breedte in meters → px (alleen wegen met netK, dus met netwerkdata).
    const metres = m => ['interpolate', ['exponential', 2], ['zoom'],
      15, ['*', m, ['get', 'netK'], Math.pow(2, 15)], 22, ['*', m, ['get', 'netK'], Math.pow(2, 22)]];
    // Haarlijn (px) voor de wegrand en de buitenrand van de stoep.
    const hairline = ['interpolate', ['linear'], ['zoom'], 12, 0.5, 16, 1];
    // Lijn evenwijdig aan de weg aan de kant waar de link flag heeft (side
    // -1 = links, 1 = rechts), op centerM meter buiten de wegrand (negatief =
    // op het wegdek).
    const sideLine = (id, side, flag, centerM, color, lineWidth, extra = {}) => ({
      id, type: 'line', ...tr, minzoom: 15, layout: round, filter: ['all', roads, ['==', flag, 1]], ...extra,
      paint: { 'line-color': color, 'line-opacity': fadeIn, 'line-width': lineWidth,
               'line-offset': metres(['*', side, ['+', ['/', ['get', 'netWidthM'], 2], centerM]]),
               ...extra.paint } });
    // Stoep: strook van _SIDEWALK_STRIP_M, met aan de wegkant een donkerdere
    // stoeprand (_KERB_M) en aan de buitenkant een haarlijn.
    const sidewalk = (name, side, flag) => [
      sideLine(`mtl-road-sidewalk-${name}`, side, flag, _SIDEWALK_STRIP_M / 2, p.sidewalk, metres(_SIDEWALK_STRIP_M)),
      sideLine(`mtl-road-sidewalk-${name}-kerb`, side, flag, _KERB_M / 2, p.kerb, metres(_KERB_M)),
      sideLine(`mtl-road-sidewalk-${name}-edge`, side, flag, _SIDEWALK_STRIP_M, p.line, hairline),
    ];
    // Fietsstrook op het wegdek: rode strook langs de wegrand, met een
    // onderbroken witte streep aan de kant van de rijbaan. Breedte schaalt
    // mee met de weg: _CYCLELANE_SHARE van de wegbreedte, begrensd.
    const laneM = ['min', _CYCLELANE_MAX_M, ['max', _CYCLELANE_MIN_M, ['*', _CYCLELANE_SHARE, ['get', 'netWidthM']]]];
    const cycleLane = (name, side, flag) => [
      sideLine(`mtl-road-cyclelane-${name}`, side, flag, ['/', laneM, -2], p.bikePath, metres(laneM),
        { layout: butt }),
      sideLine(`mtl-road-cyclelane-${name}-line`, side, flag, ['*', laneM, -1], p.laneMarking,
        ['interpolate', ['linear'], ['zoom'], 16, 1, 19, 1.8],
        { minzoom: 16.5, layout: butt, paint: { 'line-dasharray': [3, 3] } }),
    ];
    const roadWidth = width(byClass(1.8, 1.4, 1, 0.5), byClass(8, 6.5, 5, 2.8), byClass(56, 44, 36, 20));
    const surfaceColor = ['match', ['coalesce', ['get', 'netSurface'], ''],
      ...Object.entries(_MTL_SURFACE.day).flat(), p.road];
    const round = { 'line-cap': 'round', 'line-join': 'round' };
    const butt  = { 'line-cap': 'butt',  'line-join': 'round' };
    const tr = { source: roadSrc, 'source-layer': 'transportation' };
    const rail = { source: src, 'source-layer': 'transportation' };
    const walk = { source: _SIDEWALK_SRC };
    const fadeIn = ['interpolate', ['linear'], ['zoom'], 15, 0, 15.5, 1];
    const railOf = cls => ['all', ['==', '$type', 'LineString'], ['==', 'class', cls], ['!=', 'brunnel', 'tunnel']];
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
        paint: { 'line-color': p.shore, 'line-width': 0.8, 'line-opacity': 0.5 } },
      { id: 'mtl-paths', type: 'line', ...tr, minzoom: 15, layout: round,
        filter: ['all', ['==', '$type', 'LineString'], ['in', 'class', 'path', 'track'],
                 ['!=', 'brunnel', 'tunnel'], ['!=', 'indoor', 1]],
        paint: { 'line-color': p.road, 'line-opacity': 0.65,
                 'line-width': ['interpolate', ['exponential', 2], ['zoom'], 15, 0.5, 19, 5] } },
      // BGT-stoepen (vlakken, setSidewalks) onder de wegranden: dekken de
      // OSM-voetpadlijnen van mtl-paths af, de wegen liggen eroverheen.
      { id: 'mtl-sidewalk-fill', type: 'fill', ...walk, minzoom: 15, filter: ['==', 'assetType', 'sidewalk'],
        paint: { 'fill-color': p.sidewalk, 'fill-opacity': fadeIn } },
      // Wegrand: haarlijn direct langs het wegdek (gap = wegbreedte).
      { id: 'mtl-road-edge', type: 'line', ...tr, filter: roads, layout: round,
        paint: { 'line-color': p.line, 'line-width': hairline, 'line-gap-width': roadWidth } },
      // Stoepen uit het netwerk (sidewalkLeft/Right = 'yes'), boven de wegrand.
      ...sidewalk('left', -1, 'netSwL'),
      ...sidewalk('right', 1, 'netSwR'),
      // BGT-fietspaden (rood asfalt) boven de wegrand en stoepstroken (die
      // anders over het fietspad vallen), maar onder het wegdek. Geen eigen omtreklijn: de
      // BGT-vlakken liggen in stukken naast elkaar, een lijn tekent elke naad.
      { id: 'mtl-bikepath-fill', type: 'fill', ...walk, minzoom: 15, filter: ['==', 'assetType', 'bikePath'],
        paint: { 'fill-color': p.bikePath, 'fill-opacity': fadeIn } },
      { id: 'mtl-roads', type: 'line', ...tr, filter: roads, layout: round,
        paint: { 'line-color': surfaceColor,
                 'line-width': roadWidth } },
      // Fietsstroken uit het netwerk (cyclewayLeft/Right = 'lane'/'shared_lane'), op het wegdek.
      ...cycleLane('left', -1, 'netCwL'),
      ...cycleLane('right', 1, 'netCwR'),
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
      // Spoor (boven de wegen, dus ook over overwegen en bruggen): treinspoor
      // met ballastbedding, dwarsliggers en twee rails; tram/metro ('transit')
      // alleen rails. Breedtes ≈ werkelijke maten op z19 (bedding ~4,5 m,
      // dwarsligger ~2,6 m, spoorwijdte 1,435 m), grondtal 2 schaalt mee.
      { id: 'mtl-rail-bed', type: 'line', ...rail, filter: railOf('rail'), layout: round,
        paint: { 'line-color': p.railBed,
                 'line-width': ['interpolate', ['exponential', 2], ['zoom'], 12, 0.8, 15, 3, 19, 48, 22, 384] } },
      { id: 'mtl-rail-ties', type: 'line', ...rail, filter: railOf('rail'), minzoom: 16.5, layout: butt,
        paint: { 'line-color': p.railTie, 'line-dasharray': [0.1, 0.13],
                 'line-width': ['interpolate', ['exponential', 2], ['zoom'], 16.5, 4.8, 19, 28, 22, 224] } },
      { id: 'mtl-rail-line', type: 'line', ...rail, maxzoom: 16, layout: round,
        filter: ['any', railOf('rail'), railOf('transit')],
        paint: { 'line-color': p.rail, 'line-opacity': 0.8,
                 'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 16, 1.2] } },
      { id: 'mtl-rails', type: 'line', ...rail, minzoom: 16, layout: butt,
        filter: ['any', railOf('rail'), railOf('transit')],
        paint: { 'line-color': p.rail,
                 'line-width':     ['interpolate', ['exponential', 2], ['zoom'], 16, 0.4, 19, 1.4, 22, 11],
                 'line-gap-width': ['interpolate', ['exponential', 2], ['zoom'], 16, 2, 19, 15, 22, 120] } },
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
    const roadSrc = _ensureRoadSource(m, src) || src;
    _ensureSidewalkSource(m);
    for (const layer of _montrealLayers(src, _MTL_PALETTES.day, roadSrc)) {
      layer.layout = { ...(layer.layout || {}), visibility: 'none' };
      m.addLayer(layer, beforeId);
    }
  }

  function setVisible(m, visible) {
    for (const l of m.getStyle().layers) {
      if (!l.id.startsWith('mtl-')) continue;
      const on = visible && (_sidewalksOn || !_isSidewalkLayer(l));
      m.setLayoutProperty(l.id, 'visibility', on ? 'visible' : 'none');
    }
  }

  // ── Stoepen en fietspaden (BGT) ─────────────────────────────────────────
  // Eén GeoJSON-source per kaart; de features gelden voor alle kaarten.
  const _SIDEWALK_SRC = 'mtl-sidewalks';
  const _EMPTY_FC = { type: 'FeatureCollection', features: [] };
  let _sidewalkFC = _EMPTY_FC;
  let _sidewalksOn = true;
  const _sidewalkMaps = new Set();

  // BGT-vlakken en de stoepen en fietsstroken uit het netwerk.
  const _isSidewalkLayer = l => l.source === _SIDEWALK_SRC
    || l.id.startsWith('mtl-road-sidewalk-') || l.id.startsWith('mtl-road-cyclelane-');

  function _ensureSidewalkSource(m) {
    if (!m.getSource(_SIDEWALK_SRC)) m.addSource(_SIDEWALK_SRC, { type: 'geojson', data: _sidewalkFC });
    _sidewalkMaps.add(m);
  }

  function setSidewalks(features) {
    _sidewalkFC = Array.isArray(features) && features.length
      ? { type: 'FeatureCollection', features } : _EMPTY_FC;
    for (const m of _sidewalkMaps) m.getSource(_SIDEWALK_SRC)?.setData(_sidewalkFC);
  }

  // Alleen zichtbaar als ook de Montréal-ondergrond aanstaat (mtl-ground).
  function setSidewalksVisible(on) {
    _sidewalksOn = !!on;
    for (const m of _sidewalkMaps) {
      if (!m.getLayer('mtl-ground')) continue;
      const mtlOn = m.getLayoutProperty('mtl-ground', 'visibility') !== 'none';
      for (const l of m.getStyle().layers) {
        if (_isSidewalkLayer(l)) m.setLayoutProperty(l.id, 'visibility', mtlOn && _sidewalksOn ? 'visible' : 'none');
      }
    }
  }

  // ── Netwerkdata in de wegen-tiles ───────────────────────────────────────
  // De 'transportation'-laag van de OFM-tiles gaat via een eigen protocol
  // (mtlnet://). Daar krijgt elke weg die op NETWORK-links ligt de breedte
  // (netWidthM, met netK = px per meter op z0), de verhardingsklasse
  // (netSurface), de stoepen (netSwL/netSwR = 1) en fietsstroken
  // (netCwL/netCwR = 1) (links/rechts t.o.v. de
  // tekenrichting van de weg) van die links. Er wordt niets overheen getekend: de
  // mtl-weglagen stylen gewoon op die extra properties.

  const _NET_WIDTH_MIN_M = 2;
  const _NET_WIDTH_MAX_M = 12;
  const _SIDEWALK_STRIP_M = 1;    // breedte van de stoepstrook per kant (incl. stoeprand)
  const _KERB_M           = 0.2;  // breedte van de stoeprand
  const _CYCLELANE_SHARE  = 0.25; // fietsstrook = dit deel van de wegbreedte,
  const _CYCLELANE_MIN_M  = 0.75; //   maar minstens
  const _CYCLELANE_MAX_M  = 2;    //   en hoogstens zoveel meter
  const _MATCH_DIST_M    = 8;     // max. afstand weg ↔ link
  const _MATCH_COS       = Math.cos(30 * Math.PI / 180);  // max. hoekverschil 30°
  const _MATCH_PIECE_M   = 10;    // wegen worden in stukjes van ≤ 10 m getoetst
  const _MATCH_MIN_RATIO = 0.5;   // aandeel van de weglengte dat moet matchen
  const _GRID_CELL_M     = 50;
  const _ROAD_CLASSES = new Set(['motorway', 'trunk', 'primary', 'secondary', 'tertiary',
    'minor', 'service', 'busway', 'bus_guideway']);

  // Kleur per verhardingsklasse; ontbrekende klassen vallen terug op p.road.
  // Asfalt en onbekend = de gewone wegkleur, de rest net warmer/koeler.
  const _MTL_SURFACE = {
    day:   { asfalt: _MTL_PALETTES.day.road,   onbekend: _MTL_PALETTES.day.road,
             klinkers: '#d6c8b6', beton: '#d9dcd6', halfverhard: '#dacfa9', onverhard: '#c9bb93' },
    night: { asfalt: _MTL_PALETTES.night.road, onbekend: _MTL_PALETTES.night.road,
             klinkers: '#37302e', beton: '#2f3a43', halfverhard: '#38352a', onverhard: '#332e24' },
  };

  // Ruwe OSM-surface (road-enricher, gmt_network_enrichment ≥ 0.6) → klasse.
  const _SURFACE_CLASS = {};
  for (const [cls, values] of Object.entries({
    asfalt:      ['asphalt', 'paved', 'chipseal'],
    klinkers:    ['paving_stones', 'sett', 'bricks', 'cobblestone', 'unhewn_cobblestone'],
    beton:       ['concrete', 'concrete:plates', 'concrete:lanes'],
    halfverhard: ['compacted', 'fine_gravel', 'gravel', 'pebblestone'],
    onverhard:   ['unpaved', 'ground', 'dirt', 'earth', 'grass', 'sand', 'mud'],
  })) for (const v of values) _SURFACE_CLASS[v] = cls;

  // Verhardingsklasse van een link; zonder (bekende) surface → 'onbekend'.
  function _surfaceClass(props) {
    const s = typeof props.surface === 'string' ? props.surface.trim().toLowerCase() : '';
    return _SURFACE_CLASS[s] || 'onbekend';
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

  // Wereldcoördinaten (Web Mercator, 0..1, y van boven naar beneden).
  const _wx = lon => (lon + 180) / 360;
  const _wy = lat => {
    const r = lat * Math.PI / 180;
    return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2;
  };
  const _latOfWy = wy => Math.atan(Math.sinh(Math.PI * (1 - 2 * wy))) * 180 / Math.PI;

  // Huidig netwerk: linksegmenten in een raster (wereldcoördinaten).
  let _net = null;          // { grid, cell, mPerW } of null
  let _netFeatures = null;
  let _netVersion = 0;
  const _maps = new Set();  // kaarten met een mtl-ofm-roads-source

  // Fietsstrook op het wegdek: 'lane' en 'shared_lane' (suggestiestrook).
  const _isCycleLane = v => v === 'lane' || v === 'shared_lane';

  function _buildNetIndex(features) {
    const ids = new Set(features.map(f => f.properties?.linkId));
    const seen = new Set();
    const links = [];
    let latSum = 0;
    for (const f of features) {
      const p = f.properties || {};
      const coords = f.geometry?.type === 'LineString' ? f.geometry.coordinates : null;
      if (!coords || coords.length < 2) continue;
      const absId = Math.abs(p.linkId ?? 0);
      if (absId && seen.has(absId)) continue;
      if (absId) seen.add(absId);
      const hasOpposite = p.linkId != null && ids.has(-p.linkId);
      links.push({ coords, widthM: _netWidthM(p, hasOpposite), surface: _surfaceClass(p),
                   swL: p.sidewalkLeft === 'yes', swR: p.sidewalkRight === 'yes',
                   cwL: _isCycleLane(p.cyclewayLeft), cwR: _isCycleLane(p.cyclewayRight) });
      latSum += coords[0][1];
    }
    if (!links.length) return null;
    const mPerW = 40075016.686 * Math.cos((latSum / links.length) * Math.PI / 180);
    const cell = _GRID_CELL_M / mPerW;
    const grid = new Map();
    for (const link of links) {
      for (let i = 1; i < link.coords.length; i++) {
        const seg = {
          ax: _wx(link.coords[i - 1][0]), ay: _wy(link.coords[i - 1][1]),
          bx: _wx(link.coords[i][0]),     by: _wy(link.coords[i][1]), link,
        };
        const x0 = Math.floor(Math.min(seg.ax, seg.bx) / cell), x1 = Math.floor(Math.max(seg.ax, seg.bx) / cell);
        const y0 = Math.floor(Math.min(seg.ay, seg.by) / cell), y1 = Math.floor(Math.max(seg.ay, seg.by) / cell);
        for (let gx = x0; gx <= x1; gx++) for (let gy = y0; gy <= y1; gy++) {
          const key = gx + ',' + gy;
          let list = grid.get(key);
          if (!list) grid.set(key, list = []);
          list.push(seg);
        }
      }
    }
    return { grid, cell, mPerW };
  }

  // Dichtstbijzijnde, ongeveer evenwijdig linksegment bij punt (mx,my) met
  // richting (dx,dy); { link, same } met same = zelfde richting als (dx,dy).
  function _nearestLink(mx, my, dx, dy) {
    const { grid, cell, mPerW } = _net;
    const maxD = _MATCH_DIST_M / mPerW;
    const dl = Math.hypot(dx, dy);
    let best = null, bestD = maxD;
    const gx0 = Math.floor((mx - maxD) / cell), gx1 = Math.floor((mx + maxD) / cell);
    const gy0 = Math.floor((my - maxD) / cell), gy1 = Math.floor((my + maxD) / cell);
    for (let gx = gx0; gx <= gx1; gx++) for (let gy = gy0; gy <= gy1; gy++) {
      const list = grid.get(gx + ',' + gy);
      if (!list) continue;
      for (const s of list) {
        const sx = s.bx - s.ax, sy = s.by - s.ay;
        const sl2 = sx * sx + sy * sy;
        if (!sl2) continue;
        if (Math.abs(sx * dx + sy * dy) / (Math.sqrt(sl2) * dl) < _MATCH_COS) continue;
        const t = Math.max(0, Math.min(1, ((mx - s.ax) * sx + (my - s.ay) * sy) / sl2));
        const d = Math.hypot(mx - (s.ax + t * sx), my - (s.ay + t * sy));
        if (d < bestD) { bestD = d; best = { link: s.link, same: sx * dx + sy * dy > 0 }; }
      }
    }
    return best;
  }

  // Lijnen (wereldcoördinaten) → { netSurface, netWidthM, netSwL/R, netCwL/R } of
  // null. Stemt per stukje van ≤ 10 m: verharding = meeste lengte, breedte =
  // lengte-gewogen, stoep/fietsstrook = op meer dan de helft van de gematchte lengte.
  // Links/rechts van een tegengesteld getekende link worden omgedraaid.
  function _matchRoad(lines) {
    const mPerW = _net.mPerW;
    const surfLen = new Map();
    let total = 0, matched = 0, widthSum = 0, swLLen = 0, swRLen = 0, cwLLen = 0, cwRLen = 0;
    for (const line of lines) {
      for (let i = 1; i < line.length; i++) {
        const [ax, ay] = line[i - 1], [bx, by] = line[i];
        const dx = bx - ax, dy = by - ay;
        const lenM = Math.hypot(dx, dy) * mPerW;
        if (!lenM) continue;
        const n = Math.max(1, Math.ceil(lenM / _MATCH_PIECE_M));
        const pieceM = lenM / n;
        for (let k = 0; k < n; k++) {
          const t = (k + 0.5) / n;
          total += pieceM;
          const hit = _nearestLink(ax + t * dx, ay + t * dy, dx, dy);
          if (!hit) continue;
          const link = hit.link;
          matched += pieceM;
          if (hit.same ? link.swL : link.swR) swLLen += pieceM;
          if (hit.same ? link.swR : link.swL) swRLen += pieceM;
          if (hit.same ? link.cwL : link.cwR) cwLLen += pieceM;
          if (hit.same ? link.cwR : link.cwL) cwRLen += pieceM;
          widthSum += link.widthM * pieceM;
          surfLen.set(link.surface, (surfLen.get(link.surface) || 0) + pieceM);
        }
      }
    }
    if (!total || matched / total < _MATCH_MIN_RATIO) return null;
    let surface = 'onbekend', bestLen = -1;
    for (const [s, l] of surfLen) if (l > bestLen) { bestLen = l; surface = s; }
    return { netSurface: surface, netWidthM: Math.round(widthSum / matched * 10) / 10,
             netSwL: swLLen > matched / 2, netSwR: swRLen > matched / 2,
             netCwL: cwLLen > matched / 2, netCwR: cwRLen > matched / 2 };
  }

  // ── Mini-protobuf/MVT: alleen wat nodig is om tags toe te voegen ────────
  function _readVarint(buf, pos) {
    let val = 0, mul = 1, b;
    do { b = buf[pos.i++]; val += (b & 0x7f) * mul; mul *= 128; } while (b & 0x80);
    return val;
  }
  // Velden binnen [start, end): { field, wire, tagStart, dataStart, dataEnd }.
  function* _fields(buf, start, end) {
    const pos = { i: start };
    while (pos.i < end) {
      const tagStart = pos.i;
      const tag = _readVarint(buf, pos);
      const field = Math.floor(tag / 8), wire = tag & 7;
      let dataStart = pos.i;
      if (wire === 0) _readVarint(buf, pos);
      else if (wire === 1) pos.i += 8;
      else if (wire === 2) { const len = _readVarint(buf, pos); dataStart = pos.i; pos.i += len; }
      else if (wire === 5) pos.i += 4;
      else throw new Error('MVT: onbekend wiretype ' + wire);
      yield { field, wire, tagStart, dataStart, dataEnd: pos.i };
    }
  }
  function _packedVarints(buf, start, end) {
    const out = [], pos = { i: start };
    while (pos.i < end) out.push(_readVarint(buf, pos));
    return out;
  }
  const _utf8dec = new TextDecoder(), _utf8enc = new TextEncoder();

  class _Writer {
    constructor() { this.buf = new Uint8Array(1024); this.len = 0; }
    _grow(n) {
      if (this.len + n <= this.buf.length) return;
      let size = this.buf.length * 2;
      while (size < this.len + n) size *= 2;
      const nb = new Uint8Array(size); nb.set(this.buf.subarray(0, this.len)); this.buf = nb;
    }
    varint(v) {
      this._grow(10);
      while (v >= 128) { this.buf[this.len++] = (v % 128) | 0x80; v = Math.floor(v / 128); }
      this.buf[this.len++] = v;
    }
    bytes(b) { this._grow(b.length); this.buf.set(b, this.len); this.len += b.length; }
    tag(field, wire) { this.varint(field * 8 + wire); }
    lenDelim(field, b) { this.tag(field, 2); this.varint(b.length); this.bytes(b); }
    result() { return this.buf.subarray(0, this.len); }
  }

  // MVT Value: string (veld 1) of double (veld 3).
  function _encodeValue(v) {
    const w = new _Writer();
    if (typeof v === 'string') w.lenDelim(1, _utf8enc.encode(v));
    else { w.tag(3, 1); w.bytes(new Uint8Array(new Float64Array([v]).buffer)); }
    return w.result();
  }

  // Geometrie (MVT-commando's) → lijnen in tile-coördinaten.
  function _decodeLines(cmds) {
    const lines = [];
    let x = 0, y = 0, line = null;
    for (let i = 0; i < cmds.length;) {
      const id = cmds[i] & 7, count = cmds[i] >> 3; i++;
      if (id === 7) continue;
      for (let c = 0; c < count; c++) {
        const v1 = cmds[i++], v2 = cmds[i++];
        x += (v1 >> 1) ^ -(v1 & 1); y += (v2 >> 1) ^ -(v2 & 1);
        if (id === 1) lines.push(line = []);
        line.push([x, y]);
      }
    }
    return lines;
  }

  // Transportation-laag (bytes [start, end)) opnieuw schrijven met de tags
  // netSurface/netWidthM/netK (en netSwL/R, netCwL/R) op gematchte wegen; null = niets gematcht.
  // MVT: Layer name=1 features=2 keys=3 values=4 extent=5; Feature tags=2 type=3 geometry=4.
  function _enrichTransportation(buf, start, end, z, tx, ty) {
    const keys = [], values = [], features = [];
    let extent = 4096;
    for (const f of _fields(buf, start, end)) {
      if (f.field === 3) keys.push(_utf8dec.decode(buf.subarray(f.dataStart, f.dataEnd)));
      else if (f.field === 4) values.push(f);
      else if (f.field === 2) features.push(f);
      else if (f.field === 5) extent = _readVarint(buf, { i: f.dataStart });
    }
    const classKey = keys.indexOf('class');
    if (classKey < 0) return null;
    const stringValue = vi => {
      for (const f of _fields(buf, values[vi].dataStart, values[vi].dataEnd)) {
        if (f.field === 1) return _utf8dec.decode(buf.subarray(f.dataStart, f.dataEnd));
      }
      return null;
    };

    const scale = Math.pow(2, z);
    const lat = _latOfWy((ty + 0.5) / scale);
    const netK = 1 / (78271.517 * Math.cos(lat * Math.PI / 180));  // px per m op z0 (512px-tiles)
    const newValues = [], valueIdx = new Map();
    const valIndex = v => {
      const k = typeof v + ':' + v;
      if (!valueIdx.has(k)) { valueIdx.set(k, values.length + newValues.length); newValues.push(v); }
      return valueIdx.get(k);
    };
    const extraTags = new Map();  // feature-index → [key, value, …]
    features.forEach((feat, fi) => {
      let tags = null, type = 0, geom = null;
      for (const f of _fields(buf, feat.dataStart, feat.dataEnd)) {
        if (f.field === 2) tags = _packedVarints(buf, f.dataStart, f.dataEnd);
        else if (f.field === 3) type = _readVarint(buf, { i: f.dataStart });
        else if (f.field === 4) geom = _packedVarints(buf, f.dataStart, f.dataEnd);
      }
      if (type !== 2 || !tags || !geom) return;
      let cls = null;
      for (let i = 0; i < tags.length; i += 2) if (tags[i] === classKey) cls = stringValue(tags[i + 1]);
      if (!_ROAD_CLASSES.has(cls)) return;
      const lines = _decodeLines(geom).map(l => l.map(([px, py]) =>
        [(tx + px / extent) / scale, (ty + py / extent) / scale]));
      const m = _matchRoad(lines);
      if (!m) return;
      const k0 = keys.length;
      const extra = [k0, valIndex(m.netSurface), k0 + 1, valIndex(m.netWidthM), k0 + 2, valIndex(netK)];
      if (m.netSwL) extra.push(k0 + 3, valIndex(1));
      if (m.netSwR) extra.push(k0 + 4, valIndex(1));
      if (m.netCwL) extra.push(k0 + 5, valIndex(1));
      if (m.netCwR) extra.push(k0 + 6, valIndex(1));
      extraTags.set(fi, extra);
    });
    if (!extraTags.size) return null;

    // Alle velden raw overnemen, behalve features met extra tags; de nieuwe
    // keys/values komen achteraan, zodat hun indices op de bestaande aansluiten.
    const w = new _Writer();
    let fi = 0;
    for (const f of _fields(buf, start, end)) {
      const extra = f.field === 2 ? extraTags.get(fi++) : null;
      if (!extra) { w.bytes(buf.subarray(f.tagStart, f.dataEnd)); continue; }
      const fw = new _Writer();
      for (const ff of _fields(buf, f.dataStart, f.dataEnd)) {
        if (ff.field !== 2) { fw.bytes(buf.subarray(ff.tagStart, ff.dataEnd)); continue; }
        const tw = new _Writer();
        for (const t of _packedVarints(buf, ff.dataStart, ff.dataEnd)) tw.varint(t);
        for (const t of extra) tw.varint(t);
        fw.lenDelim(2, tw.result());
      }
      w.lenDelim(2, fw.result());
    }
    for (const k of ['netSurface', 'netWidthM', 'netK', 'netSwL', 'netSwR', 'netCwL', 'netCwR']) w.lenDelim(3, _utf8enc.encode(k));
    for (const v of newValues) w.lenDelim(4, _encodeValue(v));
    return w.result();
  }

  // Tile (ArrayBuffer) → tile met verrijkte transportation-laag. Tile: layers=3.
  function _enrichTile(data, z, x, y) {
    if (!_net) return data;
    const buf = new Uint8Array(data);
    const w = new _Writer();
    let changed = false;
    for (const f of _fields(buf, 0, buf.length)) {
      if (f.field === 3) {
        let name = null;
        for (const lf of _fields(buf, f.dataStart, f.dataEnd)) {
          if (lf.field === 1) { name = _utf8dec.decode(buf.subarray(lf.dataStart, lf.dataEnd)); break; }
        }
        const layer = name === 'transportation' ? _enrichTransportation(buf, f.dataStart, f.dataEnd, z, x, y) : null;
        if (layer) { w.lenDelim(3, layer); changed = true; continue; }
      }
      w.bytes(buf.subarray(f.tagStart, f.dataEnd));
    }
    return changed ? w.result().slice().buffer : data;
  }

  // mtlnet://<versie>/<z>/<x>/<y>?src=<OFM-tile-template, ge-encodeerd>
  let _protocolAdded = false;
  function _ensureProtocol() {
    if (_protocolAdded || !window.maplibregl?.addProtocol) return _protocolAdded;
    maplibregl.addProtocol('mtlnet', async (params, abortController) => {
      const m = /^mtlnet:\/\/\d+\/(\d+)\/(\d+)\/(\d+)\?src=(.*)$/.exec(params.url);
      if (!m) throw new Error('mtlnet: ongeldige url ' + params.url);
      const [z, x, y] = [+m[1], +m[2], +m[3]];
      const url = decodeURIComponent(m[4]).replace('{z}', z).replace('{x}', x).replace('{y}', y);
      const resp = await fetch(url, { signal: abortController.signal });
      if (resp.status === 204 || resp.status === 404) return { data: new ArrayBuffer(0) };
      if (!resp.ok) throw new Error(`mtlnet: ${resp.status} ${url}`);
      const data = await resp.arrayBuffer();
      try { return { data: _enrichTile(data, z, x, y) }; }
      catch (e) { console.warn('Montréal-wegen: tile niet verrijkt', z, x, y, e); return { data }; }
    });
    return _protocolAdded = true;
  }

  const _roadTilesUrl = template =>
    `mtlnet://${_netVersion}/{z}/{x}/{y}?src=${encodeURIComponent(template)}`;

  // Eigen source voor de transportation-lagen; null → gebruik de OFM-source zelf.
  function _ensureRoadSource(m, ofmSrc) {
    if (m.getSource('mtl-ofm-roads')) return 'mtl-ofm-roads';
    const s = m.getSource(ofmSrc);
    const template = s?.tiles?.[0];
    if (!template || !_ensureProtocol()) return null;
    m.addSource('mtl-ofm-roads', {
      type: 'vector', tiles: [_roadTilesUrl(template)],
      minzoom: s.minzoom ?? 0, maxzoom: s.maxzoom ?? 14,
    });
    m.getSource('mtl-ofm-roads')._mtlTemplate = template;
    _maps.add(m);
    return 'mtl-ofm-roads';
  }

  // NETWORK-links (GeoJSON LineStrings) voor alle kaarten. Bij een nieuw
  // netwerk worden de wegen-tiles opnieuw opgehaald (browsercache) en verrijkt.
  function setNetwork(features) {
    if (features === _netFeatures) return;
    _netFeatures = features;
    _net = Array.isArray(features) && features.length ? _buildNetIndex(features) : null;
    _netVersion++;
    for (const m of _maps) {
      const s = m.getSource('mtl-ofm-roads');
      if (s?._mtlTemplate) s.setTiles([_roadTilesUrl(s._mtlTemplate)]);
    }
  }

  window.MontrealBasemap = { palettes: _MTL_PALETTES, ensure, setVisible, hiddenBaseLayerIds, setNetwork,
    setSidewalks, setSidewalksVisible, surfaceClass: _surfaceClass, setSeason };
})();
