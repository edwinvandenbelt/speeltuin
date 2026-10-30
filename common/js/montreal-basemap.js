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
 */
(function () {
  'use strict';

  const _MTL_PALETTES = {
    day:   { land:'#e6e9dc', water:'#8fc7ca', green:'#b8c99e', forest:'#acbf97', road:'#c9cec5',
             sidewalk:'#f4f1e4', line:'#91a197', marking:'#f2d373', laneMarking:'#fffdf3' },
    night: { land:'#111c29', water:'#081321', green:'#162b29', forest:'#142522', road:'#26313b',
             sidewalk:'#3c454a', line:'#101b25', marking:'#8c805f', laneMarking:'#76868c' },
  };

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
    // werkelijke breedte + extraM: (m + extraM) · netK · 2^z px. Exponentieel
    // grondtal 2 tussen de stops is daarvoor exact.
    const width = (a, b, c, extraM = 0) => {
      const at = (z, px) => ['case', ['has', 'netWidthM'],
        ['*', ['+', ['get', 'netWidthM'], extraM], ['get', 'netK'], Math.pow(2, z)], px];
      return ['interpolate', ['exponential', 2], ['zoom'], 12, at(12, a), 16, at(16, b), 19, at(19, c), 22, at(22, c)];
    };
    const surfaceColor = ['match', ['coalesce', ['get', 'netSurface'], ''],
      ...Object.entries(_MTL_SURFACE.day).flat(), p.road];
    const round = { 'line-cap': 'round', 'line-join': 'round' };
    const butt  = { 'line-cap': 'butt',  'line-join': 'round' };
    const tr = { source: roadSrc, 'source-layer': 'transportation' };
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
                 'line-width': width(byClass(3.2, 2.7, 2, 1), byClass(12, 10.5, 9, 5.5), byClass(68, 56, 46, 28), _NET_EDGE_M) } },
      { id: 'mtl-road-sidewalk', type: 'line', ...tr, filter: roads, layout: round,
        paint: { 'line-color': p.sidewalk,
                 'line-width': width(byClass(2.6, 2.1, 1.5, 0.75), byClass(10, 8.5, 7, 4), byClass(62, 50, 40, 24), _NET_SIDEWALK_M) } },
      { id: 'mtl-roads', type: 'line', ...tr, filter: roads, layout: round,
        paint: { 'line-color': surfaceColor,
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
    const roadSrc = _ensureRoadSource(m, src) || src;
    for (const layer of _montrealLayers(src, _MTL_PALETTES.day, roadSrc)) {
      layer.layout = { ...(layer.layout || {}), visibility: 'none' };
      m.addLayer(layer, beforeId);
    }
  }

  function setVisible(m, visible) {
    for (const l of m.getStyle().layers) {
      if (l.id.startsWith('mtl-')) m.setLayoutProperty(l.id, 'visibility', visible ? 'visible' : 'none');
    }
  }

  // ── Netwerkdata in de wegen-tiles ───────────────────────────────────────
  // De 'transportation'-laag van de OFM-tiles gaat via een eigen protocol
  // (mtlnet://). Daar krijgt elke weg die op NETWORK-links ligt de breedte
  // (netWidthM, met netK = px per meter op z0) en de verhardingsklasse
  // (netSurface) van die links. Er wordt niets overheen getekend: de
  // mtl-weglagen stylen gewoon op die extra properties.

  const _NET_WIDTH_MIN_M = 2;
  const _NET_WIDTH_MAX_M = 12;
  const _NET_SIDEWALK_M  = 0.4;   // extra breedte van mtl-road-sidewalk (totaal)
  const _NET_EDGE_M      = 0.9;   // extra breedte van mtl-road-edge (totaal)
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
      links.push({ coords, widthM: _netWidthM(p, hasOpposite), surface: _surfaceClass(p) });
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

  // Dichtstbijzijnde, ongeveer evenwijdige link bij punt (mx,my) met richting (dx,dy).
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
        if (d < bestD) { bestD = d; best = s.link; }
      }
    }
    return best;
  }

  // Lijnen (wereldcoördinaten) → { netSurface, netWidthM } of null. Stemt per
  // stukje van ≤ 10 m: verharding = meeste lengte, breedte = lengte-gewogen.
  function _matchRoad(lines) {
    const mPerW = _net.mPerW;
    const surfLen = new Map();
    let total = 0, matched = 0, widthSum = 0;
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
          const link = _nearestLink(ax + t * dx, ay + t * dy, dx, dy);
          if (!link) continue;
          matched += pieceM;
          widthSum += link.widthM * pieceM;
          surfLen.set(link.surface, (surfLen.get(link.surface) || 0) + pieceM);
        }
      }
    }
    if (!total || matched / total < _MATCH_MIN_RATIO) return null;
    let surface = 'onbekend', bestLen = -1;
    for (const [s, l] of surfLen) if (l > bestLen) { bestLen = l; surface = s; }
    return { netSurface: surface, netWidthM: Math.round(widthSum / matched * 10) / 10 };
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
  // netSurface/netWidthM/netK op gematchte wegen; null = niets gematcht.
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
      extraTags.set(fi, [k0, valIndex(m.netSurface), k0 + 1, valIndex(m.netWidthM), k0 + 2, valIndex(netK)]);
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
    for (const k of ['netSurface', 'netWidthM', 'netK']) w.lenDelim(3, _utf8enc.encode(k));
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
    surfaceClass: _surfaceClass };
})();
