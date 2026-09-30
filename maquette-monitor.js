/**
 * maquette-monitor.js — laat zien wat de camera ziet, en waar.
 *
 * Achtergrond: de camera kijkt bijna altijd ruimer dan de beamer projecteert.
 * Een zwart vlak dat de camera oppikt kán dus best buiten het geprojecteerde
 * gebied liggen. De calibratie rekent zo'n punt netjes door naar een
 * kaartpositie, maar die ligt dan buiten de kaart — en dan wordt er een wegvak
 * afgesloten dat je niet eens ziet. Precies dat verwarrende gedrag maakt deze
 * module zichtbaar:
 *
 *   • de omtrek van het **camerabeeld** op de kaart (wat de camera bestrijkt);
 *   • een **rood kader** om elk gedetecteerd zwart vlak;
 *   • ligt zo'n vlak buiten beeld, dan een **pijl langs de rand** die ernaar wijst;
 *   • en een **meldingenbalk** die zegt wat er gesignaleerd is, en of het binnen
 *     het geprojecteerde gebied valt.
 *
 * Het camerascript sluit niets meer af buiten dat gebied; hier zie je waarom.
 *
 * Gevoed door het `maquette-detections`-event dat index.html doorgeeft vanuit de
 * SSE-stroom. Afhankelijk van: window.map.
 */
(function () {
  'use strict';

  const flag = window._maquetteFlag || (name => {
    const v = new URLSearchParams(window.location.search).get(name);
    return v !== null && ['', 'true', '1', 'yes', 'ja'].includes(v.toLowerCase());
  });
  if (!flag('maquette')) return;

  const SRC_DETECTIONS = 'maquette-detections';
  const SRC_CAMERA_VIEW = 'maquette-camera-view';

  // Een detectie is "vers" zolang ze binnen deze tijd nog gemeld werd. Het
  // camerascript stuurt 5x per seconde, dus dit dooft snel uit als er niets
  // meer in beeld is.
  const STALE_MS = 1200;

  const state = {
    map: null,
    detections: [],
    cameraView: null,
    lastUpdate: 0,
    arrows: [],
    noticeEl: null,
    installed: false,
  };

  // ───────────────────────────────────────────────────────────────────────────
  // Opmaak
  // ───────────────────────────────────────────────────────────────────────────

  function injectStyles() {
    if (document.getElementById('maqMonitorStyles')) return;
    const style = document.createElement('style');
    style.id = 'maqMonitorStyles';
    style.textContent = `
      #maqMonitorNotice {
        position: fixed; left: 16px; bottom: 16px; z-index: 9998;
        max-width: 420px;
        background: rgba(20,26,31,.86);
        color: #fff;
        border-radius: 10px;
        padding: 10px 13px;
        font: 12px 'Segoe UI', sans-serif;
        line-height: 1.5;
        pointer-events: none;
        box-shadow: 0 3px 14px rgba(0,0,0,.35);
      }
      #maqMonitorNotice .maq-title {
        font-weight: 600; font-size: 12px; margin-bottom: 3px;
        display: flex; align-items: center; gap: 7px;
      }
      #maqMonitorNotice .maq-lamp {
        width: 9px; height: 9px; border-radius: 50%; background: #6b7780;
        flex-shrink: 0;
      }
      #maqMonitorNotice.ok    .maq-lamp { background: #49e06a; }
      #maqMonitorNotice.warn  .maq-lamp { background: #ffb020; }
      #maqMonitorNotice.error .maq-lamp { background: #ff3b3b; }
      #maqMonitorNotice .maq-detail { color: rgba(255,255,255,.72); font-size: 11px; }
      #maqMonitorNotice.warn .maq-detail,
      #maqMonitorNotice.error .maq-detail { color: #ffd9a0; }

      .maq-arrow {
        position: absolute;
        width: 0; height: 0;
        margin-left: -13px; margin-top: -13px;
        pointer-events: none;
        z-index: 600;
      }
      .maq-arrow .head {
        position: absolute; left: -12px; top: -12px;
        width: 0; height: 0;
        border-left: 12px solid transparent;
        border-right: 12px solid transparent;
        border-bottom: 24px solid #ff3b3b;
        filter: drop-shadow(0 0 3px rgba(0,0,0,.7));
      }
      .maq-arrow .dist {
        position: absolute; left: 50%; top: 16px;
        transform: translateX(-50%);
        font: 700 11px 'Segoe UI', sans-serif;
        color: #fff;
        background: rgba(255,59,59,.9);
        border-radius: 8px;
        padding: 1px 6px;
        white-space: nowrap;
      }
    `;
    document.head.appendChild(style);
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Kaartlagen
  // ───────────────────────────────────────────────────────────────────────────

  function ensureLayers() {
    const map = state.map;
    if (map.getSource(SRC_CAMERA_VIEW)) return;

    // Wat de camera bestrijkt. Bewust onder de detecties, en gestippeld, zodat
    // het als achtergrondinformatie leest.
    map.addSource(SRC_CAMERA_VIEW, {
      type: 'geojson', data: { type: 'FeatureCollection', features: [] },
    });
    map.addLayer({
      id: 'maquette-camera-view-fill',
      type: 'fill',
      source: SRC_CAMERA_VIEW,
      paint: { 'fill-color': '#00b0ff', 'fill-opacity': 0.06 },
    });
    map.addLayer({
      id: 'maquette-camera-view-line',
      type: 'line',
      source: SRC_CAMERA_VIEW,
      paint: {
        'line-color': '#00b0ff',
        'line-width': 2,
        'line-dasharray': [3, 3],
        'line-opacity': 0.8,
      },
    });

    map.addSource(SRC_DETECTIONS, {
      type: 'geojson', data: { type: 'FeatureCollection', features: [] },
    });
    // Rood kader om elk gedetecteerd zwart vlak.
    map.addLayer({
      id: 'maquette-detections-fill',
      type: 'fill',
      source: SRC_DETECTIONS,
      filter: ['==', ['geometry-type'], 'Polygon'],
      paint: {
        'fill-color': '#ff3b3b',
        'fill-opacity': ['case', ['get', 'in_range'], 0.22, 0.10],
      },
    });
    // Twee lijnlagen in plaats van één: `line-dasharray` staat in MapLibre geen
    // data-afhankelijke expressie toe, dus het onderscheid doorgetrokken /
    // gestippeld moet via een filter per laag.
    map.addLayer({
      id: 'maquette-detections-line',
      type: 'line',
      source: SRC_DETECTIONS,
      filter: ['all', ['==', ['geometry-type'], 'Polygon'], ['get', 'in_range']],
      paint: { 'line-color': '#ff3b3b', 'line-width': 3 },
    });
    map.addLayer({
      id: 'maquette-detections-line-out',
      type: 'line',
      source: SRC_DETECTIONS,
      filter: ['all', ['==', ['geometry-type'], 'Polygon'], ['!', ['get', 'in_range']]],
      paint: {
        'line-color': '#ff3b3b',
        'line-width': 3,
        // Gestippeld: dit vlak ligt buiten het geprojecteerde gebied en telt niet mee.
        'line-dasharray': [2, 2],
      },
    });
    map.addLayer({
      id: 'maquette-detections-dot',
      type: 'circle',
      source: SRC_DETECTIONS,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 6,
        'circle-color': '#ff3b3b',
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff',
      },
    });
  }

  function ringFeature(points, props) {
    const ring = points.map(p => [p[0], p[1]]);
    ring.push(ring[0]);
    return {
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [ring] },
      properties: props || {},
    };
  }

  function drawMap() {
    const map = state.map;
    const camSrc = map.getSource(SRC_CAMERA_VIEW);
    if (camSrc) {
      camSrc.setData({
        type: 'FeatureCollection',
        features: state.cameraView && state.cameraView.length === 4
          ? [ringFeature(state.cameraView, { kind: 'camera' })]
          : [],
      });
    }

    const src = map.getSource(SRC_DETECTIONS);
    if (!src) return;
    const features = [];
    state.detections.forEach(d => {
      const inRange = d.in_range !== false;
      if (Array.isArray(d.outline) && d.outline.length >= 3) {
        features.push(ringFeature(d.outline, { in_range: inRange }));
      }
      if (typeof d.lon === 'number' && typeof d.lat === 'number') {
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [d.lon, d.lat] },
          properties: { in_range: inRange },
        });
      }
    });
    src.setData({ type: 'FeatureCollection', features });
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Pijlen langs de rand voor wat buiten beeld ligt
  // ───────────────────────────────────────────────────────────────────────────

  function clearArrows() {
    state.arrows.forEach(el => el.parentNode && el.parentNode.removeChild(el));
    state.arrows = [];
  }

  /** Waar snijdt de lijn van het midden naar `p` de rand van de kaart? */
  function edgePoint(width, height, p) {
    const cx = width / 2, cy = height / 2;
    const dx = p.x - cx, dy = p.y - cy;
    if (dx === 0 && dy === 0) return { x: cx, y: cy };
    const pad = 26;
    // Grootste schaalfactor waarbij het punt nog net binnen de rand valt.
    const scaleX = dx === 0 ? Infinity : (width / 2 - pad) / Math.abs(dx);
    const scaleY = dy === 0 ? Infinity : (height / 2 - pad) / Math.abs(dy);
    const s = Math.min(scaleX, scaleY);
    return { x: cx + dx * s, y: cy + dy * s };
  }

  function metresBetween(a, b) {
    const R = 6371000;
    const toRad = d => (d * Math.PI) / 180;
    const dLat = toRad(b.lat - a.lat);
    const dLon = toRad(b.lng - a.lng);
    const lat1 = toRad(a.lat), lat2 = toRad(b.lat);
    const h = Math.sin(dLat / 2) ** 2 +
              Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function drawArrows() {
    clearArrows();
    const map = state.map;
    const container = map.getContainer();
    const rect = container.getBoundingClientRect();
    const centre = map.getCenter();

    state.detections.forEach(d => {
      if (typeof d.lon !== 'number' || typeof d.lat !== 'number') return;
      let p;
      try {
        p = map.project([d.lon, d.lat]);
      } catch (_) {
        return;
      }
      const onScreen = p.x >= 0 && p.y >= 0 && p.x <= rect.width && p.y <= rect.height;
      if (onScreen) return;

      const edge = edgePoint(rect.width, rect.height, p);
      const angle = Math.atan2(p.y - rect.height / 2, p.x - rect.width / 2);

      const el = document.createElement('div');
      el.className = 'maq-arrow';
      el.style.left = `${edge.x}px`;
      el.style.top = `${edge.y}px`;
      // De punt van de driehoek wijst standaard omlaag; +90° laat hem naar het
      // doel wijzen.
      el.style.transform = `rotate(${(angle * 180) / Math.PI + 90}deg)`;

      const metres = metresBetween(centre, { lng: d.lon, lat: d.lat });
      const label = metres > 1500
        ? `${(metres / 1000).toFixed(1)} km`
        : `${Math.round(metres)} m`;
      el.innerHTML = `<div class="head"></div><div class="dist">${label}</div>`;

      container.appendChild(el);
      state.arrows.push(el);
    });
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Meldingen
  // ───────────────────────────────────────────────────────────────────────────

  function ensureNotice() {
    if (state.noticeEl) return;
    const el = document.createElement('div');
    el.id = 'maqMonitorNotice';
    el.innerHTML = `<div class="maq-title"><span class="maq-lamp"></span>
                    <span class="maq-head">Camera uit</span></div>
                    <div class="maq-detail"></div>`;
    document.body.appendChild(el);
    state.noticeEl = el;
  }

  function setNotice(level, head, detail) {
    ensureNotice();
    const el = state.noticeEl;
    el.classList.remove('ok', 'warn', 'error');
    if (level) el.classList.add(level);
    el.querySelector('.maq-head').textContent = head;
    el.querySelector('.maq-detail').textContent = detail || '';
  }

  function updateNotice() {
    const fresh = Date.now() - state.lastUpdate < STALE_MS;
    if (!fresh) {
      setNotice('', 'Geen camerabeeld', 'Het camera-script stuurt niets door.');
      return;
    }
    const dets = state.detections;
    if (dets.length === 0) {
      setNotice('', 'Camera kijkt mee', 'Geen zwart vlak in beeld.');
      return;
    }
    const inside = dets.filter(d => d.in_range !== false);
    const outside = dets.filter(d => d.in_range === false);

    if (inside.length > 0) {
      const d = inside[0];
      setNotice(
        'ok',
        `Zwart vlak gesignaleerd — binnen het geprojecteerde gebied`,
        `${dets.length} vlak(ken) in beeld. Camerapixel (${d.px}, ${d.py}).` +
        (outside.length ? `  ${outside.length} vlak(ken) vallen erbuiten.` : ''),
      );
      return;
    }

    const d = outside[0];
    const where = (typeof d.u === 'number')
      ? `  Positie in het geprojecteerde vlak: ${d.u.toFixed(2)}, ${d.v.toFixed(2)} ` +
        `(binnen = 0 tot 1).`
      : '';
    setNotice(
      'warn',
      `Zwart vlak BUITEN het geprojecteerde gebied — genegeerd`,
      `De camera ziet ruimer dan de beamer projecteert. Er wordt niets ` +
      `afgesloten. Camerapixel (${d.px}, ${d.py}).${where}`,
    );
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Bijwerken
  // ───────────────────────────────────────────────────────────────────────────

  function refresh() {
    if (!state.map) return;
    if (Date.now() - state.lastUpdate >= STALE_MS) {
      state.detections = [];
    }
    ensureLayers();
    drawMap();
    drawArrows();
    updateNotice();
  }

  function install() {
    if (state.installed) return;
    const map = window.map;
    if (!map) { setTimeout(install, 200); return; }
    state.installed = true;
    state.map = map;

    injectStyles();
    ensureNotice();

    const start = () => { ensureLayers(); refresh(); };
    if (map.loaded()) start(); else map.once('load', start);

    document.addEventListener('maquette-detections', evt => {
      const data = evt.detail || {};
      state.detections = Array.isArray(data.detections) ? data.detections : [];
      if (Array.isArray(data.camera_view) && data.camera_view.length === 4) {
        state.cameraView = data.camera_view;
      }
      state.lastUpdate = Date.now();
      refresh();
    });

    // Pijlen moeten mee als de kaart beweegt: hun plek hangt van de weergave af.
    map.on('move', drawArrows);
    map.on('resize', drawArrows);

    // Uitdoven wanneer er niets meer binnenkomt.
    setInterval(() => {
      if (state.detections.length && Date.now() - state.lastUpdate >= STALE_MS) refresh();
      else if (!state.detections.length) updateNotice();
    }, 500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
