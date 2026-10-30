/**
 * animated-water.js — bewegend water met lucht-weerspiegeling (F4Map-stijl)
 * als MapLibre custom layer boven 'mtl-water' (Montréal-ondergrond, zie
 * montreal-basemap.js).
 *
 * Geometrie: de 'water'-polygonen uit de OpenFreeMap-vectortiles
 * (querySourceFeatures), getrianguleerd met earcut (jsDelivr, lui geladen).
 * Shader: golfnormalen uit een paar lopende golven in wereldmeters, fresnel-
 * menging tussen waterkleur en luchtkleur, en zonneschittering. De laag is
 * ondoorzichtig; zolang er nog geen geometrie is, blijft 'mtl-water' zichtbaar.
 *
 * API: window.AnimatedWater.ensure(map)
 *        → voegt 'mtl-water-anim' toe als 'mtl-water' bestaat; de laag tekent
 *          alleen als 'mtl-water' zichtbaar is.
 *      window.AnimatedWater.setSun(sun)
 *        → zonnestand { isDay, intensity, lightColor, skyColor, horizonColor,
 *          azimuthal, polar } (zie _getSunState in de digital twin).
 */
(function () {
  'use strict';

  const LAYER_ID   = 'mtl-water-anim';
  const EARCUT_URL = 'https://cdn.jsdelivr.net/npm/earcut@2.2.4/dist/earcut.min.js';
  const FRAME_MS   = 33;            // ~30 fps is genoeg voor golfjes
  const ORIGIN_RESET_M = 30000;     // nieuwe oorsprong als de kaart zo ver verschuift
  const REDUCED_MOTION = !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  const _hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255);
  const _mul = (a, b) => a.map((v, i) => v * b[i]);

  // Kleuren; setSun overschrijft lucht en zon.
  const _look = {
    base:    _mul(_hex('#8fc7ca'), [0.86, 0.88, 0.9]),  // iets donkerder dan mtl-water: weerspiegeling licht op
    skyZen:  _hex('#87b9e8'),
    skyHor:  _hex('#c8dff0'),
    sunDir:  [0, -0.6, 0.8],
    sunCol:  [1, 1, 1],
  };
  const _maps = new Set();

  function setSun(sun) {
    if (!sun) return;
    const waterHex = window.MontrealBasemap?.palettes?.day?.water || '#8fc7ca';
    if (sun.isDay) {
      _look.base   = _mul(_hex(waterHex), [0.86, 0.88, 0.9]);
      _look.skyZen = _hex(sun.skyColor || '#87b9e8');
      _look.skyHor = _hex(sun.horizonColor || '#c8dff0');
      const el = (90 - sun.polar) * Math.PI / 180, az = sun.azimuthal * Math.PI / 180;
      _look.sunDir = [Math.sin(az) * Math.cos(el), Math.cos(az) * Math.cos(el), Math.sin(el)];
      _look.sunCol = _hex(sun.lightColor || '#ffffff').map(c => c * (sun.intensity ?? 0.8));
    } else {
      // Nacht: gedempt blauwig (zoals de 3D BAG-panden), geen schittering.
      // Mild: de lichte ondergrond en de waterlopen worden 's nachts nauwelijks donkerder.
      _look.base   = _mul(_hex(waterHex), [0.68, 0.72, 0.82]);
      _look.skyZen = _mul(_hex(waterHex), [0.56, 0.6, 0.74]);
      _look.skyHor = _mul(_hex(waterHex), [0.78, 0.82, 0.9]);
      _look.sunCol = [0, 0, 0];
    }
    for (const m of _maps) m.triggerRepaint();
  }

  // ── earcut lui laden ───────────────────────────────────────────────────
  let _earcutPromise = null;
  function _loadEarcut() {
    if (window.earcut) return Promise.resolve(window.earcut);
    if (!_earcutPromise) {
      _earcutPromise = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = EARCUT_URL;
        s.onload = () => window.earcut ? resolve(window.earcut) : reject(new Error('earcut ontbreekt'));
        s.onerror = () => reject(new Error('earcut niet geladen'));
        document.head.appendChild(s);
      });
    }
    return _earcutPromise;
  }

  // ── Shaders (GLSL ES 1.00, werkt in WebGL1 en 2) ───────────────────────
  const VS = `
    attribute vec2 a_pos;        // meters t.o.v. de oorsprong (x oost, y noord)
    uniform mat4 u_matrix;
    varying vec2 v_pos;
    void main() {
      v_pos = a_pos;
      gl_Position = u_matrix * vec4(a_pos, 0.0, 1.0);
    }`;

  const FS = `
    precision highp float;
    varying vec2 v_pos;
    uniform vec3  u_cam;         // camera in dezelfde meters, z = hoogte
    uniform float u_time;
    uniform vec3  u_base, u_skyZen, u_skyHor, u_sunDir, u_sunCol;

    // 2D simplex-ruis (Ashima Arts / Stefan Gustavson, MIT).
    vec3 permute(vec3 x) { return mod(((x * 34.0) + 1.0) * x, 289.0); }
    float snoise(vec2 v) {
      const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
      vec2 i  = floor(v + dot(v, C.yy));
      vec2 x0 = v - i + dot(i, C.xx);
      vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
      vec4 x12 = x0.xyxy + C.xxzz;
      x12.xy -= i1;
      i = mod(i, 289.0);
      vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
      vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy), dot(x12.zw, x12.zw)), 0.0);
      m = m * m; m = m * m;
      vec3 x = 2.0 * fract(p * C.www) - 1.0;
      vec3 h = abs(x) - 0.5;
      vec3 a0 = x - floor(x + 0.5);
      m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
      vec3 g;
      g.x  = a0.x * x0.x + h.x * x0.y;
      g.yz = a0.yz * x12.xz + h.yz * x12.yw;
      return 130.0 * dot(m, g);
    }

    // Golfhoogte (m): octaven die elk een eigen kant op drijven. Korte golven
    // vervagen op afstand (anders flikkering/patronen).
    float octave(vec2 p, float L, float A, vec2 drift, float d) {
      float fade = 1.0 - smoothstep(L * 25.0, L * 90.0, d);
      return fade < 0.001 ? 0.0 : A * fade * snoise(p / L + drift * u_time / L);
    }
    float height(vec2 p, float d) {
      return octave(p, 8.0,  0.10,  vec2( 0.45,  0.20), d)
           + octave(p, 3.7,  0.05,  vec2(-0.20,  0.38), d)
           + octave(p, 1.7,  0.022, vec2( 0.30, -0.25), d)
           + octave(p, 0.8,  0.010, vec2(-0.22, -0.18), d);
    }

    void main() {
      vec3  toCam = u_cam - vec3(v_pos, 0.0);
      float d     = length(toCam);
      vec3  V     = toCam / d;

      const float e = 0.08;
      float h0 = height(v_pos, d);
      vec2  g  = vec2(height(v_pos + vec2(e, 0.0), d) - h0,
                      height(v_pos + vec2(0.0, e), d) - h0) / e;
      vec3 N = normalize(vec3(-g, 1.0));

      // Fresnel (artistiek: iets sterker dan Schlick voor water)
      float ndv = max(dot(N, V), 0.0);
      float F   = 0.05 + 0.75 * pow(1.0 - ndv, 3.0);
      vec3  R   = reflect(-V, N);
      vec3  sky = mix(u_skyHor, u_skyZen, pow(max(R.z, 0.0), 0.45));
      vec3  col = mix(u_base, sky, F);

      // Lichte golfschaduw: ook van bovenaf zichtbaar
      col *= 1.0 + 0.45 * dot(N.xy, vec2(0.45, 0.6));

      // Zon: scherpe glinsteringen + brede glans
      float s = max(dot(R, u_sunDir), 0.0);
      col += u_sunCol * (pow(s, 600.0) * 3.0 + pow(s, 40.0) * 0.12);

      gl_FragColor = vec4(col, 1.0);
    }`;

  function _compile(gl, type, src) {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
    return sh;
  }

  // Camerapositie (mercator-eenheden) uit de view-projectiematrix: het oog
  // projecteert op clip (0,0,c,0), dus oog = kolom 2 van inv(m), gedeeld door w.
  function _eye(m) {
    const a = m;
    const b00 = a[0] * a[5] - a[1] * a[4], b01 = a[0] * a[6] - a[2] * a[4];
    const b02 = a[0] * a[7] - a[3] * a[4], b03 = a[1] * a[6] - a[2] * a[5];
    const b04 = a[1] * a[7] - a[3] * a[5], b05 = a[2] * a[7] - a[3] * a[6];
    const b06 = a[8] * a[13] - a[9] * a[12], b07 = a[8] * a[14] - a[10] * a[12];
    const b08 = a[8] * a[15] - a[11] * a[12], b09 = a[9] * a[14] - a[10] * a[13];
    const b10 = a[9] * a[15] - a[11] * a[13], b11 = a[10] * a[15] - a[11] * a[14];
    const det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
    if (!det) return null;
    // Kolom 2 van de inverse (gl-matrix mat4.invert, elementen 8..11).
    const x = a[4] * b10 - a[5] * b08 + a[7] * b06;
    const y = a[1] * b08 - a[0] * b10 - a[3] * b06;
    const z = a[12] * b04 - a[13] * b02 + a[15] * b00;
    const w = a[9] * b02 - a[8] * b04 - a[11] * b00;
    return w ? [x / w, y / w, z / w] : null;
  }

  // ── Custom layer per kaart ─────────────────────────────────────────────
  function _makeLayer(srcId) {
    let map = null, gl = null, prog = null, loc = null, vao = null;
    let vbuf = null, ibuf = null, nIdx = 0, failed = false;
    let origin = null;            // { x, y, mpu, lat } in mercator-eenheden
    let sig = '', timer = 0, raf = 0, lastFrame = 0;   // sig: laatst getrianguleerde set

    // Volgt 'mtl-water': custom layers ontbreken in getStyle().layers, dus
    // MontrealBasemap.setVisible schakelt deze laag zelf niet.
    const visible = () => !!map.getLayer('mtl-water') && map.getLayoutProperty('mtl-water', 'visibility') !== 'none';

    function schedule() {
      clearTimeout(timer);
      timer = setTimeout(rebuild, 250);
    }

    async function rebuild() {
      if (!map || failed || !visible()) return;
      let earcut;
      try { earcut = await _loadEarcut(); } catch (e) { console.warn('Bewegend water:', e); failed = true; return; }
      if (!map) return;

      const c = map.getCenter();
      const cm = maplibregl.MercatorCoordinate.fromLngLat(c);
      if (!origin || Math.hypot(cm.x - origin.x, cm.y - origin.y) * origin.mpu > ORIGIN_RESET_M) {
        origin = { x: cm.x, y: cm.y, lat: c.lat, mpu: 40075016.686 * Math.cos(c.lat * Math.PI / 180) };
      }

      let feats;
      try {
        feats = map.querySourceFeatures(srcId, { sourceLayer: 'water',
          filter: ['!=', ['get', 'brunnel'], 'tunnel'] });
      } catch (_) { return; }

      // Polygonen; dubbele tegels overlappen, maar de laag is ondoorzichtig.
      const polys = [];
      let nCoords = 0;
      for (const f of feats) {
        const geom = f.geometry;
        if (!geom) continue;
        if (geom.type === 'Polygon') polys.push(geom.coordinates);
        else if (geom.type === 'MultiPolygon') polys.push(...geom.coordinates);
      }
      for (const p of polys) for (const r of p) nCoords += r.length;
      const newSig = polys.length + ':' + nCoords + ':' + origin.x;
      if (newSig === sig) return;
      sig = newSig;

      const pos = [], idx = [];
      const { x: ox, y: oy, mpu } = origin;
      for (const rings of polys) {
        const flat = [], holes = [];
        for (const ring of rings) {
          if (flat.length) holes.push(flat.length / 2);
          for (const [lng, lat] of ring) {
            const m = maplibregl.MercatorCoordinate.fromLngLat([lng, lat]);
            flat.push((m.x - ox) * mpu, -(m.y - oy) * mpu);
          }
        }
        const tri = earcut(flat, holes.length ? holes : null, 2);
        const base = pos.length / 2;
        for (let i = 0; i < flat.length; i++) pos.push(flat[i]);
        for (let i = 0; i < tri.length; i++) idx.push(base + tri[i]);
      }

      gl.bindBuffer(gl.ARRAY_BUFFER, vbuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(pos), gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, null);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibuf);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(idx), gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, null);
      nIdx = idx.length;
      map.triggerRepaint();
    }

    // Animatie: ~30 fps hertekenen zolang de laag zichtbaar is en er water is.
    // Net zichtbaar geworden (ondergrond-keuze) → geometrie bijwerken.
    let wasVisible = false;
    function tick(t) {
      raf = requestAnimationFrame(tick);
      const v = visible();
      if (v && !wasVisible) schedule();
      wasVisible = v;
      if (!v || REDUCED_MOTION || !nIdx || t - lastFrame < FRAME_MS) return;
      lastFrame = t;
      map.triggerRepaint();
    }

    const onSourceData = e => { if (e.sourceId === srcId && e.tile) schedule(); };
    const onMoveEnd = () => schedule();

    return {
      id: LAYER_ID, type: 'custom', renderingMode: '2d',

      onAdd(m, g) {
        map = m; gl = g;
        try {
          prog = gl.createProgram();
          gl.attachShader(prog, _compile(gl, gl.VERTEX_SHADER, VS));
          gl.attachShader(prog, _compile(gl, gl.FRAGMENT_SHADER, FS));
          gl.linkProgram(prog);
          if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
          if (!(typeof WebGL2RenderingContext !== 'undefined' && gl instanceof WebGL2RenderingContext)
              && !gl.getExtension('OES_element_index_uint')) throw new Error('geen 32-bit indices');
        } catch (e) {
          console.warn('Bewegend water uitgeschakeld:', e);
          failed = true;
          return;
        }
        loc = {
          pos: gl.getAttribLocation(prog, 'a_pos'),
          matrix: gl.getUniformLocation(prog, 'u_matrix'),
          cam: gl.getUniformLocation(prog, 'u_cam'),
          time: gl.getUniformLocation(prog, 'u_time'),
          base: gl.getUniformLocation(prog, 'u_base'),
          skyZen: gl.getUniformLocation(prog, 'u_skyZen'),
          skyHor: gl.getUniformLocation(prog, 'u_skyHor'),
          sunDir: gl.getUniformLocation(prog, 'u_sunDir'),
          sunCol: gl.getUniformLocation(prog, 'u_sunCol'),
        };
        vbuf = gl.createBuffer();
        ibuf = gl.createBuffer();
        if (gl.createVertexArray) {
          vao = gl.createVertexArray();
          gl.bindVertexArray(vao);
          gl.bindBuffer(gl.ARRAY_BUFFER, vbuf);
          gl.enableVertexAttribArray(loc.pos);
          gl.vertexAttribPointer(loc.pos, 2, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibuf);
          gl.bindVertexArray(null);
        }
        map.on('sourcedata', onSourceData);
        map.on('moveend', onMoveEnd);
        _maps.add(map);
        raf = requestAnimationFrame(tick);
        schedule();
      },

      onRemove() {
        cancelAnimationFrame(raf);
        clearTimeout(timer);
        map.off('sourcedata', onSourceData);
        map.off('moveend', onMoveEnd);
        _maps.delete(map);
        if (gl && !failed) {
          gl.deleteBuffer(vbuf); gl.deleteBuffer(ibuf); gl.deleteProgram(prog);
          if (vao) gl.deleteVertexArray(vao);
        }
        map = gl = null;
      },

      render(g, args) {
        if (failed || !nIdx || !origin || !visible()) return;
        // MapLibre 5: modelViewProjectionMatrix werkt in wereldpixels
        // (512·2^zoom per wereld) → schalen naar mercator 0..1 (ook z, zodat
        // _eye mercator-eenheden geeft). Oudere versies: matrix zelf, al 0..1.
        let m = args;
        if (args?.modelViewProjectionMatrix) {
          const ws = 512 * Math.pow(2, map.getZoom());
          m = Array.from(args.modelViewProjectionMatrix, (v, i) => i < 12 ? v * ws : v);
        }
        const { x: ox, y: oy, mpu } = origin;
        // M = m · T(ox, oy) · diag(1/mpu, −1/mpu, 1, 1), in float64 berekend.
        const M = new Float32Array(16);
        for (let r = 0; r < 4; r++) {
          M[r]      =  m[r] / mpu;
          M[4 + r]  = -m[4 + r] / mpu;
          M[8 + r]  =  m[8 + r];
          M[12 + r] =  m[r] * ox + m[4 + r] * oy + m[12 + r];
        }
        const cp = _eye(m);
        const cam = cp ? [(cp[0] - ox) * mpu, -(cp[1] - oy) * mpu, Math.max(1, cp[2] * mpu)] : [0, 0, 1000];
        const t = REDUCED_MOTION ? 0 : (performance.now() / 1000) % 3600;

        gl.useProgram(prog);
        gl.disable(gl.DEPTH_TEST);
        gl.disable(gl.STENCIL_TEST);
        gl.disable(gl.CULL_FACE);
        gl.disable(gl.BLEND);
        gl.uniformMatrix4fv(loc.matrix, false, M);
        gl.uniform3fv(loc.cam, cam);
        gl.uniform1f(loc.time, t);
        gl.uniform3fv(loc.base, _look.base);
        gl.uniform3fv(loc.skyZen, _look.skyZen);
        gl.uniform3fv(loc.skyHor, _look.skyHor);
        gl.uniform3fv(loc.sunDir, _look.sunDir);
        gl.uniform3fv(loc.sunCol, _look.sunCol);
        if (vao) {
          gl.bindVertexArray(vao);
        } else {
          gl.bindBuffer(gl.ARRAY_BUFFER, vbuf);
          gl.enableVertexAttribArray(loc.pos);
          gl.vertexAttribPointer(loc.pos, 2, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibuf);
        }
        gl.drawElements(gl.TRIANGLES, nIdx, gl.UNSIGNED_INT, 0);
        if (vao) gl.bindVertexArray(null);
        else gl.disableVertexAttribArray(loc.pos);
      },
    };
  }

  function ensure(m) {
    if (m.getLayer(LAYER_ID)) return;
    const water = m.getLayer('mtl-water');
    if (!water) return;
    const before = m.getStyle().layers.find((l, i, all) => all[i - 1]?.id === 'mtl-water')?.id;
    m.addLayer(_makeLayer(water.source), before);
  }

  window.AnimatedWater = { ensure, setSun };
})();
