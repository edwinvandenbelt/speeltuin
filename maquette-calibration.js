/**
 * maquette-calibration.js — camerabeeld over de kaart leggen en passend maken.
 *
 * De beamer projecteert de kaart op de fysieke maquette; de camera kijkt naar
 * die maquette. Omdat de camera niet loodrecht staat, is haar beeld
 * perspectivisch vervormd en kan een simpele schaal/offset dat niet corrigeren.
 *
 * Deze module legt daarom het live camerabeeld half-transparant over de kaart
 * en geeft de vier hoeken ervan sleephandles. Je sleept tot de kaart die de
 * camera in beeld heeft samenvalt met de kaart eronder. Daarmee ligt een 3x3
 * homografie vast die elke camerapixel op de kaart afbeeldt — perspectief
 * inbegrepen. De calibratie bevestigt zichzelf: je ziet dat het klopt.
 *
 * Verankering in SCHERMruimte, niet in geo
 * ----------------------------------------
 * Wat fysiek vastligt is de relatie camerapixel ↔ schermpixel (de beamer
 * projecteert het browservenster). Daarom worden de vier punten als fractie van
 * de kaartcontainer opgeslagen. De geo-punten zijn daaruit afgeleid en worden
 * opnieuw berekend als de kaart beweegt — de calibratie zelf blijft geldig.
 *
 * Twee standen:
 *   cameraId >= 0  → calibratie-UI met live camerabeeld.
 *   cameraId == -1 → geen camera; de cursor doet het werk. Deze module post dan
 *                    alleen de cursorpositie (inclusief lon/lat) naar de server,
 *                    zodat maquette_camera.py geen Windows-cursor hoeft uit te
 *                    lezen en er geen calibratie nodig is.
 *
 * Afhankelijk van index.html: window.map, window.AREA_ID, window.MODE.
 */
(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  // Vlaggen soepel lezen (?x=true, ?x=1, ?x=yes, ?x): index.html doet hetzelfde.
  // Een ?maquette=1 zou anders stilzwijgend deze hele module uitschakelen.
  const flag = window._maquetteFlag || (name => {
    const v = params.get(name);
    return v !== null && ['', 'true', '1', 'yes', 'ja'].includes(v.toLowerCase());
  });

  const MAQUETTE = flag('maquette');
  if (!MAQUETTE) return;

  const CAMERA_ID = parseInt(params.get('cameraId') ?? '-1', 10);
  // `calibrate` is de nieuwe naam; `recalibrate` blijft werken.
  const FORCE_CALIBRATE = flag('calibrate') || flag('recalibrate');

  // Volgorde van de vier punten, overal identiek: linksboven, rechtsboven,
  // rechtsonder, linksonder — gezien vanuit het camerabeeld.
  const CORNER_LABELS = ['LB', 'RB', 'RO', 'LO'];

  // ───────────────────────────────────────────────────────────────────────────
  // Homografie: zelfde methode als maquette_calibration.py, zodat browser en
  // camera-script bit-voor-bit dezelfde afbeelding beschrijven.
  // ───────────────────────────────────────────────────────────────────────────

  /** Hartley-normalisatie: centroïde naar de oorsprong, gemiddelde afstand √2. */
  function normalization(points) {
    const n = points.length;
    let cx = 0, cy = 0;
    for (const p of points) { cx += p[0]; cy += p[1]; }
    cx /= n; cy /= n;
    let mean = 0;
    for (const p of points) mean += Math.hypot(p[0] - cx, p[1] - cy);
    mean /= n;
    if (mean < 1e-15) throw new Error('ontaarde puntenset');
    return { cx, cy, s: Math.SQRT2 / mean };
  }

  /** Los a·x = b op met Gaussische eliminatie en partial pivoting. */
  function solveLinear(a, b) {
    const n = b.length;
    const m = a.map((row, i) => row.concat([b[i]]));
    for (let col = 0; col < n; col++) {
      let pivot = col;
      for (let r = col + 1; r < n; r++) {
        if (Math.abs(m[r][col]) > Math.abs(m[pivot][col])) pivot = r;
      }
      if (Math.abs(m[pivot][col]) < 1e-14) {
        throw new Error('singulier stelsel: punten collineair of samenvallend');
      }
      const tmp = m[col]; m[col] = m[pivot]; m[pivot] = tmp;
      const inv = 1 / m[col][col];
      for (let j = col; j <= n; j++) m[col][j] *= inv;
      for (let r = 0; r < n; r++) {
        if (r === col) continue;
        const f = m[r][col];
        if (f === 0) continue;
        for (let j = col; j <= n; j++) m[r][j] -= f * m[col][j];
      }
    }
    return m.map(row => row[n]);
  }

  function mat3mul(a, b) {
    const out = new Array(9).fill(0);
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 3; c++) {
        out[r * 3 + c] =
          a[r * 3] * b[c] + a[r * 3 + 1] * b[3 + c] + a[r * 3 + 2] * b[6 + c];
      }
    }
    return out;
  }

  /** 3x3 homografie die `src` op `dst` afbeeldt (rij-major, 9 getallen). */
  function solveHomography(src, dst) {
    if (src.length !== dst.length || src.length < 4) {
      throw new Error('solveHomography verwacht minstens vier gelijke puntparen');
    }
    const ns = normalization(src);
    const nd = normalization(dst);
    const S = src.map(p => [(p[0] - ns.cx) * ns.s, (p[1] - ns.cy) * ns.s]);
    const D = dst.map(p => [(p[0] - nd.cx) * nd.s, (p[1] - nd.cy) * nd.s]);

    const a = [], b = [];
    for (let i = 0; i < S.length; i++) {
      const [u, v] = S[i];
      const [x, y] = D[i];
      a.push([u, v, 1, 0, 0, 0, -u * x, -v * x]); b.push(x);
      a.push([0, 0, 0, u, v, 1, -u * y, -v * y]); b.push(y);
    }

    let h;
    if (a.length === 8) {
      h = solveLinear(a, b);
    } else {
      // Overbepaald: normaalvergelijkingen AᵀA·h = Aᵀb, weer een 8x8-stelsel.
      const ata = [];
      for (let i = 0; i < 8; i++) {
        const row = [];
        for (let j = 0; j < 8; j++) {
          let sum = 0;
          for (const r of a) sum += r[i] * r[j];
          row.push(sum);
        }
        ata.push(row);
      }
      const atb = [];
      for (let i = 0; i < 8; i++) {
        let sum = 0;
        for (let k = 0; k < a.length; k++) sum += a[k][i] * b[k];
        atb.push(sum);
      }
      h = solveLinear(ata, atb);
    }

    const hn = h.concat([1]);
    const tSrc = [ns.s, 0, -ns.s * ns.cx, 0, ns.s, -ns.s * ns.cy, 0, 0, 1];
    const tDstInv = [1 / nd.s, 0, nd.cx, 0, 1 / nd.s, nd.cy, 0, 0, 1];
    const H = mat3mul(tDstInv, mat3mul(hn, tSrc));
    if (Math.abs(H[8]) < 1e-15) throw new Error('ontaarde homografie');
    return H.map(v => v / H[8]);
  }

  /**
   * CSS-transform die de bronrechthoek op de vier doelpunten legt.
   * matrix3d is kolom-major; de derde rij/kolom blijft de identiteit.
   */
  function homographyToMatrix3d(h) {
    return `matrix3d(${h[0]},${h[3]},0,${h[6]},` +
           `${h[1]},${h[4]},0,${h[7]},` +
           `0,0,1,0,` +
           `${h[2]},${h[5]},0,${h[8]})`;
  }

  /**
   * Is de vierhoek convex en niet gedraaid? Bij een zelfdoorsnijdende vierhoek
   * klapt het beeld binnenstebuiten of verdwijnt het achter de horizon.
   */
  function quadIsConvex(pts) {
    let sign = 0;
    for (let i = 0; i < 4; i++) {
      const a = pts[i], b = pts[(i + 1) % 4], c = pts[(i + 2) % 4];
      const cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
      if (Math.abs(cross) < 1e-9) continue;
      const s = Math.sign(cross);
      if (sign === 0) sign = s;
      else if (s !== sign) return false;
    }
    return sign !== 0;
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Virtuele modus: cursorpositie doorgeven
  // ───────────────────────────────────────────────────────────────────────────

  function installCursorReporter(map) {
    let last = null;      // laatst bekende positie binnen de kaart
    let lastSent = 0;

    function send() {
      if (!last) return;
      lastSent = performance.now();
      fetch('/maquette/cursor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(last),
        keepalive: true,
      }).catch(() => { /* best-effort: een gemist sample is niet erg */ });
    }

    document.addEventListener('mousemove', evt => {
      const rect = map.getContainer().getBoundingClientRect();
      const x = evt.clientX - rect.left;
      const y = evt.clientY - rect.top;
      if (x < 0 || y < 0 || x > rect.width || y > rect.height) {
        // Buiten de kaart: niets meer sturen. Het camera-script ziet de samples
        // verouderen en zet de stabiliteitsteller terug op nul.
        last = null;
        return;
      }
      let ll;
      try {
        ll = map.unproject([x, y]);
      } catch (_) {
        return;
      }
      last = { x, y, lon: ll.lng, lat: ll.lat };
      // 20 Hz is ruim voor een handbeweging en houdt het aantal requests laag.
      if (performance.now() - lastSent >= 50) send();
    }, { passive: true });

    // Blijf de positie herhalen zolang de cursor op de kaart staat. Dat is
    // essentieel: het blokje moet drie seconden *stil* liggen, en zonder
    // herhaling zou het camera-script de samples als verouderd afschrijven
    // juist op het moment dat de gebruiker niet beweegt.
    setInterval(() => {
      if (performance.now() - lastSent >= 150) send();
    }, 100);

    console.log('[maquette] cursorpositie wordt naar de server gestuurd.');
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Calibratie-UI
  //
  // Drie fasen. De opstelling dwingt die volgorde af: het bedienscherm is
  // meestal hetzelfde scherm dat de beamer projecteert, dus alles wat we tonen
  // belandt op de maquette en wordt door de camera teruggefilmd.
  //
  //   A. markers   — vier genummerde markers op bekende schermposities, zodat
  //                  er een scherp mikpunt is in plaats van "wegen op wegen".
  //   B. bevriezen — één camerabeeld vastleggen. Dít doorbreekt de
  //                  terugkoppellus: vanaf nu maakt het niet meer uit wat de
  //                  beamer laat zien.
  //   C. aanwijzen — vier handvatten over dat stilstaande beeld slepen, op de
  //                  markers.
  // ───────────────────────────────────────────────────────────────────────────

  // Vier markers, in de volgorde die overal in het calibratiebestand geldt:
  // linksboven, rechtsboven, rechtsonder, linksonder.
  const MARKERS = [
    { n: 1, label: 'LB', color: '#ff2bd1' },
    { n: 2, label: 'RB', color: '#00e5ff' },
    { n: 3, label: 'RO', color: '#ffe500' },
    { n: 4, label: 'LO', color: '#44e06a' },
  ];

  const PHASE = { MARKERS: 'markers', POINT: 'point' };

  const state = {
    open: false,
    phase: PHASE.MARKERS,
    map: null,
    container: null,
    stage: null,        // schermvullende laag met markers of het stilstaande beeld
    still: null,        // <img> met het bevroren camerabeeld
    stillUrl: null,     // object-URL van dat beeld (bevriest het écht)
    warp: null,         // <img> voor de controleweergave over de kaart
    svg: null,
    poly: null,
    markerEls: [],
    handles: [],
    panel: null,
    thumb: null,        // klein live camerabeeld om de camera op te richten
    // Inzet van de markers als fractie van de container. 0 = precies op de
    // hoeken van het geprojecteerde vlak.
    inset: 0.06,
    // Aangewezen punten, als fractie van het *stilstaande beeld* (0..1).
    picked: null,
    frame: { width: 0, height: 0 },
    // Hoe het stilstaande beeld in de container past (contain-schaling).
    fit: { scale: 1, offsetX: 0, offsetY: 0, width: 0, height: 0 },
    dragging: null,
    rafPending: false,
    infoTimer: null,
    statusEl: null,
    saveBtn: null,
    captureBtn: null,
    checking: false,
  };

  function injectStyles() {
    if (document.getElementById('maqCalibStyles')) return;
    const style = document.createElement('style');
    style.id = 'maqCalibStyles';
    style.textContent = `
      /* Schermvullende laag: in fase A zwart met markers, in fase C het
         bevroren camerabeeld. Zwart maakt de markers in het camerabeeld
         onmiskenbaar en laat meteen de rand van de projectie zien. */
      #maqCalibStage {
        position: absolute; left: 0; top: 0; right: 0; bottom: 0;
        background: #000;
        z-index: 500;
        overflow: hidden;
      }
      #maqCalibStage.transparent { background: transparent; pointer-events: none; }
      #maqCalibStill {
        position: absolute;
        image-rendering: crisp-edges;
      }
      .maq-marker {
        position: absolute;
        width: 76px; height: 76px;
        margin-left: -38px; margin-top: -38px;
        pointer-events: none;
        /* Boven het paneel, zodat het paneel nooit een marker afdekt in de
           projectie — dan zou je iets moeten aanwijzen wat er niet staat. */
        z-index: 10000;
      }
      .maq-marker .ring {
        position: absolute; inset: 0;
        border-radius: 50%;
        border: 5px solid #fff;
        box-shadow: 0 0 0 3px #000;
      }
      .maq-marker .dot {
        position: absolute; left: 50%; top: 50%;
        width: 14px; height: 14px; margin: -7px 0 0 -7px;
        border-radius: 50%;
      }
      .maq-marker .cross-h,
      .maq-marker .cross-v {
        position: absolute; background: #fff;
      }
      .maq-marker .cross-h { left: 8px; right: 8px; top: 50%; height: 3px; margin-top: -1.5px; }
      .maq-marker .cross-v { top: 8px; bottom: 8px; left: 50%; width: 3px; margin-left: -1.5px; }
      .maq-marker .num {
        position: absolute; left: 50%; top: 100%;
        transform: translateX(-50%);
        margin-top: 4px;
        font: 700 22px 'Segoe UI', sans-serif;
        text-shadow: 0 0 4px #000, 0 0 4px #000;
      }
      .maq-calib-svg {
        position: absolute; left: 0; top: 0;
        width: 100%; height: 100%;
        pointer-events: none;
        z-index: 501;
      }
      .maq-calib-handle {
        position: absolute;
        width: 30px; height: 30px;
        margin-left: -15px; margin-top: -15px;
        border-radius: 50%;
        border: 2px solid #fff;
        box-shadow: 0 1px 5px rgba(0,0,0,.6);
        color: #000;
        font: 700 13px 'Segoe UI', sans-serif;
        display: flex; align-items: center; justify-content: center;
        cursor: grab;
        touch-action: none;
        z-index: 502;
      }
      .maq-calib-handle::after {
        /* Dradenkruis: het midden van het handvat is het aangewezen punt. */
        content: ''; position: absolute; left: 50%; top: 50%;
        width: 44px; height: 44px; margin: -22px 0 0 -22px;
        border-left: 1px solid rgba(255,255,255,.7);
        border-top: 1px solid rgba(255,255,255,.7);
        transform: rotate(45deg);
        pointer-events: none;
      }
      .maq-calib-handle.dragging { transform: scale(1.3); cursor: grabbing; }
      .maq-calib-handle.invalid  { outline: 3px solid #de0058; }
      #maqCamWarp {
        position: absolute; left: 0; top: 0;
        transform-origin: 0 0;
        will-change: transform;
        pointer-events: none;
        z-index: 499;
        opacity: .55;
      }
      #maqCalibPanel {
        position: fixed; top: 52px; right: 16px; z-index: 9999;
        width: 268px;
        background: rgba(255,255,255,.95);
        border: 1px solid rgba(0,165,171,.35);
        border-radius: 12px;
        padding: 12px 14px;
        font: 12px 'Segoe UI', sans-serif;
        color: #233139;
        box-shadow: 0 4px 18px rgba(0,0,0,.18);
      }
      #maqCalibPanel h4 { margin: 0 0 6px; font-size: 13px; color: #00a5ab; }
      #maqCalibPanel p  { margin: 0 0 10px; line-height: 1.45; color: rgba(35,49,57,.75); }
      #maqCalibPanel p.hint { color: #a8003f; }
      #maqCalibPanel label { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
      #maqCalibPanel input[type=range] { flex: 1; accent-color: #00a5ab; }
      #maqCalibPanel .maq-thumb {
        width: 100%; border-radius: 6px; background: #000; display: block;
        margin-bottom: 10px; min-height: 60px;
      }
      #maqCalibPanel .maq-status {
        margin: 0 0 10px; font-size: 11px; color: rgba(35,49,57,.6); min-height: 15px;
      }
      #maqCalibPanel .maq-status.warn { color: #de0058; }
      #maqCalibPanel button {
        width: 100%; margin-top: 6px; padding: 7px 10px;
        border-radius: 8px; border: 1px solid rgba(0,165,171,.45);
        background: #00a5ab; color: #fff; font-size: 12px; cursor: pointer;
      }
      #maqCalibPanel button.secondary { background: #fff; color: #00a5ab; }
      #maqCalibPanel button:disabled { opacity: .45; cursor: default; }
      #maqCalibPanel .maq-step { display: none; }
      #maqCalibPanel .maq-step.active { display: block; }

      /* Tijdens het calibreren moet de muisaanwijzer zichtbaar zijn, en het
         zwarte blokje weg — de beamer zou dat op de maquette projecteren en de
         detector zou het als object kunnen zien. */
      body.maquette-calibrating,
      body.maquette-calibrating * { cursor: auto !important; }
      body.maquette-calibrating .maq-calib-handle { cursor: grab !important; }
      body.maquette-calibrating .maq-calib-handle.dragging { cursor: grabbing !important; }
      body.maquette-mode.maquette-calibrating::after { display: none !important; }
    `;
    document.head.appendChild(style);
  }

  function containerSize() {
    const r = state.map.getContainer().getBoundingClientRect();
    return { width: r.width, height: r.height };
  }

  /** Markerposities als fractie van de container — de *bekende* kant. */
  function markerFractions() {
    const i = state.inset;
    return [[i, i], [1 - i, i], [1 - i, 1 - i], [i, 1 - i]];
  }

  /** Markerposities in container-pixels. */
  function markerPixels() {
    const { width, height } = containerSize();
    return markerFractions().map(p => [p[0] * width, p[1] * height]);
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Opbouw van de DOM
  // ───────────────────────────────────────────────────────────────────────────

  function buildStage() {
    const container = state.map.getContainer();
    state.container = container;

    const stage = document.createElement('div');
    stage.id = 'maqCalibStage';
    container.appendChild(stage);
    state.stage = stage;

    const still = document.createElement('img');
    still.id = 'maqCalibStill';
    still.alt = '';
    still.style.display = 'none';
    stage.appendChild(still);
    state.still = still;

    // Controleweergave: hetzelfde bevroren beeld, maar vervormd over de kaart.
    const warp = document.createElement('img');
    warp.id = 'maqCamWarp';
    warp.alt = '';
    warp.style.display = 'none';
    container.appendChild(warp);
    state.warp = warp;

    state.markerEls = MARKERS.map(m => {
      const el = document.createElement('div');
      el.className = 'maq-marker';
      el.innerHTML =
        `<div class="ring"></div>` +
        `<div class="cross-h"></div><div class="cross-v"></div>` +
        `<div class="dot" style="background:${m.color}"></div>` +
        `<div class="num" style="color:${m.color}">${m.n}</div>`;
      container.appendChild(el);
      return el;
    });

    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('class', 'maq-calib-svg');
    const poly = document.createElementNS(svgNS, 'polygon');
    poly.setAttribute('fill', 'rgba(0,224,255,0.08)');
    poly.setAttribute('stroke', '#00e0ff');
    poly.setAttribute('stroke-width', '2');
    poly.setAttribute('stroke-dasharray', '7 5');
    svg.appendChild(poly);
    svg.style.display = 'none';
    container.appendChild(svg);
    state.svg = svg;
    state.poly = poly;

    state.handles = MARKERS.map((m, idx) => {
      const h = document.createElement('div');
      h.className = 'maq-calib-handle';
      h.textContent = String(m.n);
      h.style.background = m.color;
      h.style.display = 'none';
      h.title = `Sleep dit op marker ${m.n} in het camerabeeld`;
      attachDrag(h, idx);
      container.appendChild(h);
      return h;
    });
  }

  function attachDrag(handle, idx) {
    handle.addEventListener('pointerdown', evt => {
      evt.preventDefault();
      evt.stopPropagation();
      handle.setPointerCapture(evt.pointerId);
      handle.classList.add('dragging');
      state.dragging = idx;
    });

    handle.addEventListener('pointermove', evt => {
      if (state.dragging !== idx) return;
      evt.preventDefault();
      const rect = state.map.getContainer().getBoundingClientRect();
      const x = evt.clientX - rect.left;
      const y = evt.clientY - rect.top;
      // Terugrekenen naar een fractie van het stilstaande beeld, zodat de
      // aangewezen punten losstaan van de weergaveschaal.
      const f = state.fit;
      state.picked[idx] = [
        (x - f.offsetX) / f.width,
        (y - f.offsetY) / f.height,
      ];
      scheduleRender();
    });

    const stop = evt => {
      if (state.dragging !== idx) return;
      try { handle.releasePointerCapture(evt.pointerId); } catch (_) { /* al vrij */ }
      handle.classList.remove('dragging');
      state.dragging = null;
      render();
    };
    handle.addEventListener('pointerup', stop);
    handle.addEventListener('pointercancel', stop);
  }

  function scheduleRender() {
    if (state.rafPending) return;
    state.rafPending = true;
    requestAnimationFrame(() => {
      state.rafPending = false;
      render();
    });
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Tekenen
  // ───────────────────────────────────────────────────────────────────────────

  /** Bereken hoe het stilstaande beeld passend in de container valt. */
  function computeFit() {
    const { width: cw, height: ch } = containerSize();
    const { width: iw, height: ih } = state.frame;
    if (!iw || !ih) return;
    const scale = Math.min(cw / iw, ch / ih);
    const w = iw * scale;
    const h = ih * scale;
    state.fit = {
      scale,
      width: w,
      height: h,
      offsetX: (cw - w) / 2,
      offsetY: (ch - h) / 2,
    };
  }

  /** Aangewezen punten in container-pixels. */
  function pickedPixels() {
    const f = state.fit;
    return state.picked.map(p => [f.offsetX + p[0] * f.width, f.offsetY + p[1] * f.height]);
  }

  function render() {
    if (!state.open) return;

    if (state.phase === PHASE.MARKERS) {
      const pts = markerPixels();
      state.markerEls.forEach((el, i) => {
        el.style.display = '';
        el.style.left = `${pts[i][0]}px`;
        el.style.top = `${pts[i][1]}px`;
      });
      state.handles.forEach(h => { h.style.display = 'none'; });
      state.svg.style.display = 'none';
      state.still.style.display = 'none';
      state.warp.style.display = 'none';
      state.stage.classList.remove('transparent');
      return;
    }

    // Fase C: stilstaand beeld met vier handvatten.
    state.markerEls.forEach(el => { el.style.display = 'none'; });
    computeFit();
    const f = state.fit;

    if (state.checking) {
      // Controleweergave: kaart zichtbaar, bevroren beeld erover vervormd.
      state.stage.classList.add('transparent');
      state.still.style.display = 'none';
      state.svg.style.display = 'none';
      state.handles.forEach(h => { h.style.display = 'none'; });
      renderWarp();
      return;
    }

    state.stage.classList.remove('transparent');
    state.warp.style.display = 'none';
    state.still.style.display = '';
    state.still.style.left = `${f.offsetX}px`;
    state.still.style.top = `${f.offsetY}px`;
    state.still.style.width = `${f.width}px`;
    state.still.style.height = `${f.height}px`;

    const pts = pickedPixels();
    state.handles.forEach((h, i) => {
      h.style.display = '';
      h.style.left = `${pts[i][0]}px`;
      h.style.top = `${pts[i][1]}px`;
    });
    state.svg.style.display = '';
    state.poly.setAttribute('points', pts.map(p => `${p[0]},${p[1]}`).join(' '));

    const convex = quadIsConvex(pts);
    state.handles.forEach(h => h.classList.toggle('invalid', !convex));
    if (state.saveBtn) state.saveBtn.disabled = !convex;
    setStatus(
      convex
        ? 'Sleep elk genummerd handvat op de marker met hetzelfde nummer.'
        : 'De punten kruisen elkaar — zet ze in de volgorde 1, 2, 3, 4 rond.',
      !convex,
    );
  }

  /** Legt het bevroren camerabeeld vervormd over de kaart, ter controle. */
  function renderWarp() {
    const { width, height } = state.frame;
    let H;
    try {
      H = solveHomography(imagePointsPx(), markerPixels());
    } catch (_) {
      state.warp.style.display = 'none';
      setStatus('Kan de vervorming niet berekenen — controleer de punten.', true);
      return;
    }
    state.warp.src = state.stillUrl;
    state.warp.style.width = `${width}px`;
    state.warp.style.height = `${height}px`;
    state.warp.style.transform = homographyToMatrix3d(H);
    state.warp.style.display = '';
    setStatus('Vallen de wegen samen met de kaart? Dan klopt de calibratie.');
  }

  function setStatus(text, warn) {
    if (!state.statusEl) return;
    state.statusEl.textContent = text;
    state.statusEl.classList.toggle('warn', !!warn);
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Paneel
  // ───────────────────────────────────────────────────────────────────────────

  function buildPanel() {
    const panel = document.createElement('div');
    panel.id = 'maqCalibPanel';
    panel.innerHTML = `
      <h4>Camera calibreren</h4>

      <div class="maq-step" data-step="markers">
        <p>Op de maquette staan nu vier genummerde markers. Richt de camera tot
           je ze alle vier in het beeld hieronder ziet.</p>
        <img class="maq-thumb" id="maqCalibThumb" alt="">
        <label>Inzet
          <input type="range" id="maqCalibInset" min="0" max="25" value="6">
          <span id="maqCalibInsetVal">6%</span>
        </label>
        <p class="hint">Leg de markers op een vlak stuk maquette — een marker op
           een gebouw ligt hoger dan het grondvlak en trekt de calibratie scheef.</p>
        <p class="maq-status" id="maqCalibStatus"></p>
        <button id="maqCalibCapture" disabled>Beeld vastleggen</button>
        <button id="maqCalibCancel" class="secondary">Annuleren</button>
      </div>

      <div class="maq-step" data-step="point">
        <p>Sleep elk handvat naar de marker met hetzelfde nummer in het
           vastgelegde camerabeeld.</p>
        <p class="maq-status" id="maqCalibStatus2"></p>
        <button id="maqCalibSave">Opslaan &amp; camera starten</button>
        <button id="maqCalibCheck" class="secondary">Controleren</button>
        <button id="maqCalibRetake" class="secondary">Opnieuw vastleggen</button>
        <button id="maqCalibCancel2" class="secondary">Annuleren</button>
      </div>
    `;
    document.body.appendChild(panel);
    state.panel = panel;
    state.thumb = panel.querySelector('#maqCalibThumb');
    state.captureBtn = panel.querySelector('#maqCalibCapture');
    state.saveBtn = panel.querySelector('#maqCalibSave');

    const insetInput = panel.querySelector('#maqCalibInset');
    const insetVal = panel.querySelector('#maqCalibInsetVal');
    insetInput.addEventListener('input', evt => {
      state.inset = evt.target.value / 100;
      insetVal.textContent = `${evt.target.value}%`;
      scheduleRender();
    });

    state.captureBtn.addEventListener('click', capture);
    state.saveBtn.addEventListener('click', save);
    panel.querySelector('#maqCalibRetake').addEventListener('click', backToMarkers);
    panel.querySelector('#maqCalibCheck').addEventListener('click', toggleCheck);
    panel.querySelector('#maqCalibCancel').addEventListener('click', () => close(true));
    panel.querySelector('#maqCalibCancel2').addEventListener('click', () => close(true));

    showStep(PHASE.MARKERS);
  }

  function showStep(phase) {
    state.phase = phase;
    state.panel.querySelectorAll('.maq-step').forEach(el => {
      el.classList.toggle('active', el.dataset.step === phase);
    });
    state.statusEl = state.panel.querySelector(
      phase === PHASE.MARKERS ? '#maqCalibStatus' : '#maqCalibStatus2',
    );
  }

  function toggleCheck() {
    state.checking = !state.checking;
    const btn = state.panel.querySelector('#maqCalibCheck');
    btn.textContent = state.checking ? 'Terug naar aanwijzen' : 'Controleren';
    render();
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Camerabeeld
  // ───────────────────────────────────────────────────────────────────────────

  async function startPreview() {
    const size = containerSize();
    const resp = await fetch('/maquette/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        area_id: window.AREA_ID,
        mode: window.MODE,
        camera_id: CAMERA_ID,
        preview: true,
        viewport: {
          width: Math.round(size.width),
          height: Math.round(size.height),
        },
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || resp.statusText);
  }

  async function streamInfo() {
    const resp = await fetch('/maquette/stream-info');
    return resp.json();
  }

  /** Houdt het miniatuurbeeld en de status bij tijdens fase A. */
  function watchStream() {
    let attached = false;
    state.infoTimer = setInterval(async () => {
      if (state.phase !== PHASE.MARKERS) return;
      let info;
      try {
        info = await streamInfo();
      } catch (_) {
        return;
      }
      if (!info.available) {
        setStatus('Wachten op camerabeeld…');
        return;
      }
      state.frame = { width: info.width, height: info.height };
      if (!attached) {
        attached = true;
        // Het miniatuurbeeld wordt mee geprojecteerd en dus teruggefilmd. Dat
        // is te klein om een marker te raken en de recursie dooft uit.
        state.thumb.src = '/maquette/stream.mjpg';
        state.captureBtn.disabled = false;
      }
      const stale = info.age != null && info.age > 3;
      setStatus(
        stale
          ? 'Camerabeeld staat stil — loopt het camera-script nog?'
          : `Camerabeeld ${info.width}×${info.height}.`,
        stale,
      );
    }, 1000);
  }

  /**
   * Bevries één camerabeeld. Wacht tot `seq` twee is opgehoogd: anders zou je
   * een frame van vóór het tonen van de markers kunnen krijgen en punten
   * aanwijzen die er niet staan.
   */
  async function capture() {
    state.captureBtn.disabled = true;
    setStatus('Beeld vastleggen…');

    let startSeq;
    try {
      startSeq = (await streamInfo()).seq;
    } catch (err) {
      setStatus(`Camerabeeld niet bereikbaar: ${err.message}`, true);
      state.captureBtn.disabled = false;
      return;
    }

    const deadline = Date.now() + 8000;
    let info = null;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 120));
      try {
        info = await streamInfo();
      } catch (_) {
        continue;
      }
      if (info.available && info.seq >= startSeq + 2) break;
      info = null;
    }
    if (!info) {
      setStatus('Geen vers camerabeeld ontvangen — draait het camera-script?', true);
      state.captureBtn.disabled = false;
      return;
    }

    state.frame = { width: info.width, height: info.height };

    // Het miniatuur loslaten: die MJPEG-verbinding hebben we niet meer nodig en
    // ze zou een van de zes verbindingen per origin bezet houden.
    if (state.thumb) state.thumb.src = '';

    // Als blob vastleggen, niet als URL. /maquette/frame.jpg wordt met
    // `no-store` geserveerd en levert altijd het *nieuwste* frame op; met een
    // URL zou de controleweergave dus een ander beeld kunnen tonen dan het
    // beeld waarop je de punten hebt aangewezen. Een object-URL bevriest echt.
    try {
      const resp = await fetch(`/maquette/frame.jpg?t=${Date.now()}`);
      if (!resp.ok) throw new Error(resp.statusText);
      revokeStill();
      state.stillUrl = URL.createObjectURL(await resp.blob());
      await new Promise((resolve, reject) => {
        state.still.onload = resolve;
        state.still.onerror = () => reject(new Error('beeld laden mislukt'));
        state.still.src = state.stillUrl;
      });
    } catch (err) {
      setStatus(`Beeld vastleggen mislukt: ${err.message}`, true);
      state.captureBtn.disabled = false;
      return;
    }

    if (!state.picked) state.picked = defaultPicked();
    computeFit();
    state.checking = false;
    const checkBtn = state.panel.querySelector('#maqCalibCheck');
    if (checkBtn) checkBtn.textContent = 'Controleren';
    showStep(PHASE.POINT);
    render();
  }

  function backToMarkers() {
    state.checking = false;
    showStep(PHASE.MARKERS);
    state.captureBtn.disabled = false;
    if (state.thumb) state.thumb.src = '/maquette/stream.mjpg';
    render();
  }

  /** Startvierhoek in het stilstaande beeld: 20% inzet. */
  function defaultPicked() {
    return [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]];
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Opslaan
  // ───────────────────────────────────────────────────────────────────────────

  /** De aangewezen punten in echte camerapixels. */
  function imagePointsPx() {
    const { width, height } = state.frame;
    return state.picked.map(p => [p[0] * width, p[1] * height]);
  }

  /** Geo-punten onder de markers — afgeleid, want de markers zijn bekend. */
  function geoPoints() {
    return markerPixels().map(p => {
      const ll = state.map.unproject(p);
      return [ll.lng, ll.lat];
    });
  }

  function calibrationPayload() {
    const c = state.map.getCenter();
    return {
      type: 'homography',
      mode: window.MODE,
      camera_id: CAMERA_ID,
      frame: { width: state.frame.width, height: state.frame.height },
      // Waar de markers in het camerabeeld terechtkwamen — door jou aangewezen.
      image_points: imagePointsPx(),
      // Waar ze op de kaart staan.
      geo_points: geoPoints(),
      // En waar ze op het scherm stonden. Dat is wat fysiek vastligt: de beamer
      // projecteert het browservenster, dus camerapixel ↔ schermpixel verandert
      // niet als de kaart beweegt. Hiermee zijn de geo-punten herberekenbaar.
      screen_points: markerFractions(),
      view: {
        center: [c.lng, c.lat],
        zoom: state.map.getZoom(),
        bearing: state.map.getBearing(),
        pitch: state.map.getPitch(),
      },
      created: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
    };
  }

  async function postCalibration(payload) {
    const resp = await fetch('/maquette/calibration', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ area_id: window.AREA_ID, calibration: payload }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || resp.statusText);
  }

  async function save() {
    state.saveBtn.disabled = true;
    setStatus('Opslaan…');
    try {
      await postCalibration(calibrationPayload());
    } catch (err) {
      setStatus(`Opslaan mislukt: ${err.message}`, true);
      state.saveBtn.disabled = false;
      return;
    }
    close(false);
    // Camera opnieuw starten, nu in detectiestand.
    if (typeof window._maquetteStartDetection === 'function') {
      window._maquetteStartDetection();
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Openen / sluiten
  // ───────────────────────────────────────────────────────────────────────────

  /** Hergebruik de vorige aanwijzing als er al een calibratie is. */
  async function loadExisting() {
    try {
      const resp = await fetch(
        `/maquette/calibration?area_id=${encodeURIComponent(window.AREA_ID)}` +
        `&mode=${encodeURIComponent(window.MODE)}`,
      );
      const data = await resp.json();
      const calib = data?.calibration;
      if (!calib) return;
      const screen = calib.screen_points;
      if (Array.isArray(screen) && screen.length === 4) {
        // De inzet is symmetrisch, dus de eerste coördinaat volstaat.
        const inset = Number(screen[0][0]);
        if (inset >= 0 && inset <= 0.25) state.inset = inset;
      }
      const img = calib.image_points;
      const frame = calib.frame;
      if (Array.isArray(img) && img.length === 4 && frame?.width && frame?.height) {
        state.picked = img.map(p => [p[0] / frame.width, p[1] / frame.height]);
      }
    } catch (_) { /* geen bruikbare calibratie: standaardwaarden gebruiken */ }
  }

  async function open() {
    if (state.open) return;
    const map = window.map;
    if (!map) { console.warn('[maquette] kaart nog niet beschikbaar'); return; }
    state.map = map;
    state.open = true;

    // De homografie geldt voor het grondvlak; met pitch zou de bovenrand van
    // het scherm richting de horizon lopen en onbruikbaar worden.
    if (map.getPitch() !== 0) map.setPitch(0);

    injectStyles();
    document.body.classList.add('maquette-calibrating');
    await loadExisting();
    buildStage();
    buildPanel();

    const insetInput = state.panel.querySelector('#maqCalibInset');
    insetInput.value = String(Math.round(state.inset * 100));
    state.panel.querySelector('#maqCalibInsetVal').textContent =
      `${Math.round(state.inset * 100)}%`;

    render();

    window.addEventListener('resize', scheduleRender);
    map.on('resize', scheduleRender);
    window.addEventListener('beforeunload', releaseStream);

    try {
      await startPreview();
    } catch (err) {
      setStatus(`Camera starten mislukt: ${err.message}`, true);
      return;
    }
    watchStream();
  }

  /** De MJPEG-verbinding loslaten. Zonder dit blijft een van de zes
   *  browserverbindingen per origin permanent bezet. */
  function releaseStream() {
    if (state.thumb) state.thumb.src = '';
    if (state.infoTimer) { clearInterval(state.infoTimer); state.infoTimer = null; }
  }

  function revokeStill() {
    if (state.stillUrl) { URL.revokeObjectURL(state.stillUrl); state.stillUrl = null; }
  }

  function close(stopCamera) {
    if (!state.open) return;
    state.open = false;
    releaseStream();
    revokeStill();
    window.removeEventListener('resize', scheduleRender);
    if (state.map) state.map.off('resize', scheduleRender);
    document.body.classList.remove('maquette-calibrating');
    [state.stage, state.svg, state.warp, state.panel,
     ...state.markerEls, ...state.handles].forEach(el => {
      if (el && el.parentNode) el.parentNode.removeChild(el);
    });
    state.markerEls = [];
    state.handles = [];
    state.stage = state.still = state.warp = state.svg = state.poly = null;
    state.panel = state.statusEl = state.saveBtn = state.captureBtn = null;
    state.thumb = null;
    state.checking = false;
    if (stopCamera) {
      fetch('/maquette/stop', { method: 'POST' }).catch(() => {});
      // Het knoplabel in index.html staat nog op "Uitlijnen…".
      if (typeof window._maquetteCalibrationCancelled === 'function') {
        window._maquetteCalibrationCancelled();
      }
    }
  }

  /**
   * Herbereken de geo-punten als de kaart beweegt. De markers zitten vast aan
   * het scherm (daar kijkt de camera naar), dus de calibratie blijft geldig —
   * maar het camera-script rekent met geo-punten en die moeten dan mee.
   */
  function installGeoResync(map) {
    let timer = null;
    map.on('moveend', () => {
      if (state.open) return; // tijdens calibreren slaan we pas bij Opslaan op
      clearTimeout(timer);
      timer = setTimeout(async () => {
        let calib;
        try {
          const resp = await fetch(
            `/maquette/calibration?area_id=${encodeURIComponent(window.AREA_ID)}` +
            `&mode=${encodeURIComponent(window.MODE)}`,
          );
          const data = await resp.json();
          calib = data?.calibration;
        } catch (_) { return; }
        if (!calib || !Array.isArray(calib.screen_points)) return;

        const r = map.getContainer().getBoundingClientRect();
        const updated = calib.screen_points.map(p => {
          const ll = map.unproject([p[0] * r.width, p[1] * r.height]);
          return [ll.lng, ll.lat];
        });
        const c = map.getCenter();
        calib.geo_points = updated;
        calib.view = {
          center: [c.lng, c.lat],
          zoom: map.getZoom(),
          bearing: map.getBearing(),
          pitch: map.getPitch(),
        };
        postCalibration(calib).catch(() => {});
      }, 400);
    });
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Opstarten
  // ───────────────────────────────────────────────────────────────────────────

  window.MaquetteCalibration = {
    open,
    close: () => close(true),
    isOpen: () => state.open,
    // Blootgesteld zodat index.html kan bepalen of calibreren nodig is.
    needsCalibration: FORCE_CALIBRATE,
  };

  function install() {
    if (!window.AREA_ID) return;
    const map = window.map;
    if (!map) { setTimeout(install, 200); return; }

    if (CAMERA_ID === -1) {
      installCursorReporter(map);
      return;
    }

    installGeoResync(map);
    if (FORCE_CALIBRATE) {
      // Wacht tot de kaart geladen is, anders klopt unproject nog niet.
      if (map.loaded()) open();
      else map.once('load', open);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
