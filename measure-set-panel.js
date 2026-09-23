/**
 * Measure-set panel ("maatregelset") — GeoPackage upload + adjust scenario.
 *
 * Deze module is geladen in index.html als apart script. Hij opent een
 * uitschuifpaneel vanuit een toolbar-knop, laat de gebruiker een GeoPackage
 * slepen of selecteren, kiest een laag / veld / waarde, en genereert op de
 * server een wijzigingenlijst (capaciteit=0 per link) die als scenario kan
 * worden doorgerekend.
 *
 * Afhankelijkheden: de globale variabelen/functies uit index.html:
 *   AREA_ID, MODE, scenarioCounter, T(), pendingChanges, renderChangesList(),
 *   _setChangesPanelReadOnly(), loadAdjustedResult(), updateOverlay(),
 *   clearHighlight(), geojson, segments, linkGeomMap.
 */
(function () {
  'use strict';

  // -- DOM-referenties (elementen in index.html) ---------------------------
  const PANEL_ID         = 'measureSetPanel';
  const SCENARIO_INPUT_ID = 'scenarioNameInput'; // bestaand

  // -- Interne state --------------------------------------------------------
  let _uploadId = null;
  let _layers   = [];
  let _currentLayer = null;
  let _currentField = null;
  let _currentValue = null;
  let _generatedMeasures = [];
  let _uploadedGeoJson = null; // alle features van de geselecteerde laag

  const LAYER_ID = 'measure-set-layer';
  const LAYER_OUTLINE_ID = 'measure-set-layer-outline';

  // -- Hulpjes --------------------------------------------------------------
  const byId = id => document.getElementById(id);
  const el   = (tag, cls, html) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  };

  // -- Const referenties naar index.html-closure globals --------------------
  // pendingChanges/renderChangesList zijn in index.html gedefinieerd als `let`
  // binnen de grote inline script-closure. Ze zijn **niet** op `window` gezet.
  // Omdat client-scripts die in hetzelfde document na de inline script worden
  // geladen in dezelfde global scope leven, kunnen we ze direct benaderen via
  // de global object-referenties. Deze variabelen mogen we niet overschrijven.
  const _getPendingChanges = () => window.pendingChanges;
  const _getRenderChangesList = () => window.renderChangesList;
  const _getSetReadOnly = () => window._setChangesPanelReadOnly;

  // -- Localisatie: val terug op key-teksten als de index.html T() ontbreekt
  const i18n = {
    measureSetPanelTitle:       'Maatregelsets',
    measureSetBtnTitle:         'GeoPackage maatregelset importeren',
    measureSetDropHint:         'Sleep een .gpkg-bestand hierheen of klik om te kiezen',
    measureSetLayerLabel:       'Laag',
    measureSetFieldLabel:       'Veld',
    measureSetValueLabel:       'Waarde (maatregelset)',
    measureSetGenerateBtn:      'Genereer wijzigingen',
    measureSetUseAllBtn:        'Maatregelen plaatsen',
    measureSetApplyBtn:         'Scenario berekenen',
    measureSetCloseTitle:       'Sluiten',
    measureSetUploading:        'Bezig met uploaden…',
    measureSetLoadingValues:    'Waarden laden…',
    measureSetGenerating:       'Wijzigingen genereren…',
    measureSetNoValueSelected:  'Selecteer een waarde om door te rekenen.',
    measureSetGeneratedFor:     '{0} maatregelset(s) gegenereerd',
    measureSetEmptyResult:      'Geen wijzigingen gegenereerd voor deze selectie.',
    measureSetUploadError:      'Upload mislukt: {0}',
    measureSetValuesError:      'Waarden laden mislukt: {0}',
    measureSetGenerateError:    'Genereren mislukt: {0}',
    measureSetStatusReady:      'Klaar om scenario door te rekenen.',
    measureSetScenarioName:     'Maatregelset {0}',
  };
  function t(key, ...args) {
    let val = typeof T === 'function' ? T(key, ...args) : null;
    if (val == null || val === key) val = i18n[key] ?? key;
    if (args.length && typeof val === 'string') {
      args.forEach((a, i) => { val = val.replace(new RegExp(`\\{${i}\\}`, 'g'), String(a != null ? a : '')); });
    }
    return val;
  }

  // -- Paneel aanmaken ------------------------------------------------------
  function ensurePanel() {
    let panel = byId(PANEL_ID);
    if (panel) return panel;

    panel = el('div', 'measure-set-panel', `
      <div class="measure-set-header">
        <span class="measure-set-title">${t('measureSetPanelTitle')}</span>
        <button class="measure-set-close" title="${t('measureSetCloseTitle')}">✕</button>
      </div>
      <div class="measure-set-body">
        <div class="measure-set-dropzone" id="measureSetDropzone">
          <div class="measure-set-drop-icon">📦</div>
          <div class="measure-set-drop-text">${t('measureSetDropHint')}</div>
          <input type="file" id="measureSetFileInput" accept=".gpkg" />
        </div>
        <div class="measure-set-controls">
          <label>
            <span>${t('measureSetLayerLabel')}</span>
            <select id="measureSetLayerSelect" disabled></select>
          </label>
          <label>
            <span>${t('measureSetFieldLabel')}</span>
            <select id="measureSetFieldSelect" disabled></select>
          </label>
          <label>
            <span>${t('measureSetValueLabel')}</span>
            <select id="measureSetValueSelect" disabled></select>
          </label>
        </div>
        <div class="measure-set-buttons">
          <button id="measureSetGenerateBtn" disabled>${t('measureSetGenerateBtn')}</button>
          <button id="measureSetUseAllBtn" disabled>${t('measureSetUseAllBtn')}</button>
        </div>
        <div class="measure-set-status" id="measureSetStatus"></div>
        <div class="measure-set-results" id="measureSetResults"></div>
      </div>
    `);
    panel.id = PANEL_ID;
    document.body.appendChild(panel);

    const closeBtn = panel.querySelector('.measure-set-close');
    closeBtn.addEventListener('click', () => {
      clearMapLayer();
      setPanelVisible(false);
    });

    // Drag & drop
    const dz = byId('measureSetDropzone');
    dz.addEventListener('click', () => byId('measureSetFileInput').click());
    dz.addEventListener('dragover', e => {
      e.preventDefault();
      dz.classList.add('dragover');
    });
    dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
    dz.addEventListener('drop', e => {
      e.preventDefault();
      dz.classList.remove('dragover');
      const file = e.dataTransfer.files?.[0];
      if (file) uploadFile(file);
    });
    byId('measureSetFileInput').addEventListener('change', e => {
      const file = e.target.files?.[0];
      if (file) uploadFile(file);
    });

    // Selecties
    byId('measureSetLayerSelect').addEventListener('change', onLayerChange);
    byId('measureSetFieldSelect').addEventListener('change', onFieldChange);
    byId('measureSetValueSelect').addEventListener('change', onValueChange);
    byId('measureSetGenerateBtn').addEventListener('click', () => {
      clearMapLayer();
      generateForSelectedValue();
    });
    byId('measureSetUseAllBtn').addEventListener('click', useAllGeneratedMeasures);

    return panel;
  }

  function ensureToolbarButton() {
    let btn = byId('measureSetBtn');
    if (!btn) return;

    btn.style.display = 'flex';
    btn.title = t('measureSetBtnTitle');
    btn.addEventListener('click', () => {
      ensurePanel();
      setPanelVisible(!isPanelVisible());
    });
  }

  function isPanelVisible() {
    const p = byId(PANEL_ID);
    return p ? p.classList.contains('visible') : false;
  }

  function setPanelVisible(visible) {
    const p = ensurePanel();
    p.classList.toggle('visible', visible);
    const btn = byId('measureSetBtn');
    if (btn) btn.classList.toggle('active', visible);
  }

  function setStatus(html, type = '') {
    const s = byId('measureSetStatus');
    if (!s) return;
    s.innerHTML = html;
    s.className = 'measure-set-status' + (type ? ' ' + type : '');
  }

  // -- Upload + inspectie ---------------------------------------------------
  async function uploadFile(file) {
    ensurePanel();
    setStatus(t('measureSetUploading'));
    _uploadId = null;
    _layers   = [];
    resetControls();
    clearMapLayer();

    const form = new FormData();
    form.append('file', file);

    try {
      const r = await fetch('/measure-sets/upload', { method: 'POST', body: form });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      _uploadId = data.uploadId;
      _layers   = data.layers || [];
      populateLayers();
      // Selecteer automatisch de eerste geschikte laag en teken die op de kaart.
      const firstPolygon = _layers.find(l =>
        /polygon/i.test(l.geometryType || '') || l.fields?.length
      ) || _layers[0];
      if (firstPolygon) {
        const layerSel = byId('measureSetLayerSelect');
        layerSel.value = firstPolygon.name;
        _currentLayer = firstPolygon.name;
        await loadLayerGeoJson();
      }
      setStatus(`${file.name} · ${_layers.length} laag(len) gevonden.`);
    } catch (err) {
      setStatus(t('measureSetUploadError', err?.message || err), 'error');
    }
  }

  function resetControls() {
    clearMapLayer();
    _currentLayer = null;
    _currentField = null;
    _currentValue = null;
    _generatedMeasures = [];
    _uploadedGeoJson = null;

    const layerSel = byId('measureSetLayerSelect');
    const fieldSel = byId('measureSetFieldSelect');
    const valueSel = byId('measureSetValueSelect');
    const genBtn   = byId('measureSetGenerateBtn');
    const useBtn   = byId('measureSetUseAllBtn');

    layerSel.innerHTML = '';
    fieldSel.innerHTML = '';
    valueSel.innerHTML = '';
    layerSel.disabled = true;
    fieldSel.disabled = true;
    valueSel.disabled = true;
    genBtn.disabled   = true;
    useBtn.disabled   = true;

    const results = byId('measureSetResults');
    if (results) results.innerHTML = '';
  }

  function populateLayers() {
    const sel = byId('measureSetLayerSelect');
    sel.innerHTML = '<option value="">-- Kies laag --</option>';
    for (const layer of _layers) {
      const opt = document.createElement('option');
      opt.value = layer.name;
      opt.textContent = `${layer.name} (${layer.featureCount})`;
      sel.appendChild(opt);
    }
    sel.disabled = false;
  }

  async function onLayerChange() {
    _currentLayer = byId('measureSetLayerSelect').value || null;
    _currentField = null;
    _currentValue = null;
    _generatedMeasures = [];
    await loadLayerGeoJson();
    drawSelectedLayerOnMap();

    const layer = _layers.find(l => l.name === _currentLayer);
    const fieldSel = byId('measureSetFieldSelect');
    const valueSel = byId('measureSetValueSelect');
    fieldSel.innerHTML = '<option value="">-- Kies veld --</option>';
    valueSel.innerHTML = '<option value="">-- Kies waarde --</option>';
    valueSel.disabled = true;

    if (layer && layer.fields?.length) {
      for (const f of layer.fields) {
        const opt = document.createElement('option');
        opt.value = f;
        opt.textContent = f;
        fieldSel.appendChild(opt);
      }
      fieldSel.disabled = false;
    } else {
      fieldSel.disabled = true;
    }

    updateGenerateButton();
    byId('measureSetResults').innerHTML = '';
  }

  function onFieldChange() {
    _currentField = byId('measureSetFieldSelect').value || null;
    _currentValue = null;
    _generatedMeasures = [];

    const valueSel = byId('measureSetValueSelect');
    valueSel.innerHTML = '<option value="">-- Kies waarde --</option>';
    valueSel.disabled = true;

    if (_uploadId && _currentLayer && _currentField) {
      loadFieldValues();
    }

    updateGenerateButton();
    byId('measureSetResults').innerHTML = '';
  }

  async function loadFieldValues() {
    setStatus(t('measureSetLoadingValues'));
    try {
      const url = `/measure-sets/${encodeURIComponent(_uploadId)}/layers/${encodeURIComponent(_currentLayer)}/values?field=${encodeURIComponent(_currentField)}`;
      const r = await fetch(url);
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      const valueSel = byId('measureSetValueSelect');
      valueSel.innerHTML = '<option value="">-- Kies waarde --</option>';
      for (const v of data.values || []) {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        valueSel.appendChild(opt);
      }
      valueSel.disabled = false;
      setStatus(`${data.count} unieke waarden geladen.`);
    } catch (err) {
      setStatus(t('measureSetValuesError', err?.message || err), 'error');
    }
  }

  function onValueChange() {
    _currentValue = byId('measureSetValueSelect').value || null;
    _generatedMeasures = [];
    byId('measureSetResults').innerHTML = '';
    updateGenerateButton();
    showValueFeature(_currentValue);
  }

  function updateGenerateButton() {
    const genBtn = byId('measureSetGenerateBtn');
    const useBtn = byId('measureSetUseAllBtn');
    const canGenerate = !!(_uploadId && _currentLayer && _currentField && _currentValue);
    genBtn.disabled = !canGenerate;
    useBtn.disabled = _generatedMeasures.length === 0;
  }

  // -- Kaartlaag: getekende polygonen uit de GeoPackage ----------------------
  function getMap() {
    return window.map || (typeof map !== 'undefined' ? map : null);
  }

  function ensureMapLayer() {
    const map = getMap();
    if (!map) return null;
    if (!map.getSource(LAYER_ID)) {
      map.addSource(LAYER_ID, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
      });
      map.addLayer({
        id: LAYER_ID,
        type: 'fill',
        source: LAYER_ID,
        paint: { 'fill-color': '#de0058', 'fill-opacity': 0.18 }
      });
      map.addLayer({
        id: LAYER_OUTLINE_ID,
        type: 'line',
        source: LAYER_ID,
        paint: { 'line-color': '#de0058', 'line-width': 2, 'line-opacity': 0.8 }
      });
      map.on('mousemove', LAYER_ID, onMeasureSetFeatureHover);
      map.on('mouseleave', LAYER_ID, hideMeasureSetTooltip);
    }
    return map;
  }

  function onMeasureSetFeatureHover(e) {
    const map = getMap();
    if (!map || !_currentField) return;
    const feature = e.features?.[0];
    if (!feature) { hideMeasureSetTooltip(); return; }

    const value = feature.properties?.[_currentField];
    if (value == null || value === '') { hideMeasureSetTooltip(); return; }

    let tooltip = byId('measureSetTooltip');
    if (!tooltip) {
      tooltip = el('div', 'measure-set-tooltip');
      tooltip.id = 'measureSetTooltip';
      document.body.appendChild(tooltip);
    }
    tooltip.textContent = String(value);
    tooltip.style.display = 'block';
    tooltip.style.left = (e.originalEvent.clientX + 12) + 'px';
    tooltip.style.top  = (e.originalEvent.clientY + 12) + 'px';
  }

  function hideMeasureSetTooltip() {
    const tooltip = byId('measureSetTooltip');
    if (tooltip) tooltip.style.display = 'none';
  }

  function clearMapLayer() {
    hideMeasureSetTooltip();
    const map = getMap();
    if (!map || !map.getSource(LAYER_ID)) return;
    map.getSource(LAYER_ID).setData({ type: 'FeatureCollection', features: [] });
  }

  async function loadLayerGeoJson() {
    if (!_uploadId || !_currentLayer) {
      // Nog geen laag geselecteerd; laad alleen de eerste laag in
      // zodat we meteen iets kunnen tekenen als de gebruiker die kiest.
      return;
    }
    try {
      const url = `/measure-sets/${encodeURIComponent(_uploadId)}/layers/${encodeURIComponent(_currentLayer)}/features`;
      const r = await fetch(url);
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      _uploadedGeoJson = data;
      drawSelectedLayerOnMap();
    } catch (err) {
      console.warn('Kon GeoPackage-laag niet als GeoJSON laden:', err);
      _uploadedGeoJson = null;
    }
  }

  function drawSelectedLayerOnMap() {
    if (!_uploadedGeoJson || !_currentLayer) return;
    const map = ensureMapLayer();
    if (!map) return;

    const features = (_uploadedGeoJson.features || [])
      .filter(f => f.geometry && ['Polygon', 'MultiPolygon', 'LineString', 'Point'].includes(f.geometry.type));

    map.getSource(LAYER_ID).setData({
      type: 'FeatureCollection',
      features
    });

    if (features.length) {
      try {
        const coords = [];
        for (const f of features) {
          collectCoords(f.geometry.coordinates, coords);
        }
        if (coords.length) {
          const lons = coords.map(c => c[0]);
          const lats = coords.map(c => c[1]);
          map.fitBounds([
            [Math.min(...lons), Math.min(...lats)],
            [Math.max(...lons), Math.max(...lats)]
          ], { padding: 60, maxZoom: 16, duration: 600 });
        }
      } catch (e) { console.warn(e); }
    }
  }

  function collectCoords(geomCoords, out) {
    if (Array.isArray(geomCoords) && geomCoords.length === 2 && typeof geomCoords[0] === 'number' && typeof geomCoords[1] === 'number') {
      out.push(geomCoords);
    } else if (Array.isArray(geomCoords)) {
      geomCoords.forEach(c => collectCoords(c, out));
    }
  }

  function showValueFeature(value) {
    const map = ensureMapLayer();
    if (!map || !_uploadedGeoJson || !_currentField) return;
    if (!value) {
      clearMapLayer();
      return;
    }
    const features = (_uploadedGeoJson.features || []).filter(f => {
      const props = f.properties || {};
      return String(props[_currentField] ?? '') === value;
    });

    map.getSource(LAYER_ID).setData({
      type: 'FeatureCollection',
      features
    });

    if (features.length) {
      const coords = [];
      for (const f of features) collectCoords(f.geometry.coordinates, coords);
      if (coords.length) {
        const lons = coords.map(c => c[0]);
        const lats = coords.map(c => c[1]);
        map.fitBounds([
          [Math.min(...lons), Math.min(...lats)],
          [Math.max(...lons), Math.max(...lats)]
        ], { padding: 60, maxZoom: 16, duration: 600 });
      }
    }
  }

  // -- Wijzigingen genereren ------------------------------------------------
  async function generateForSelectedValue() {
    if (!_uploadId || !_currentLayer || !_currentField || !_currentValue) return;

    setStatus(t('measureSetGenerating'));
    _generatedMeasures = [];
    updateGenerateButton();

    const body = {
      area_id: window.AREA_ID,
      mode: window.MODE,
      upload_id: _uploadId,
      layer: _currentLayer,
      field: _currentField,
    };

    try {
      const r = await fetch('/measure-sets/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      const allSets = data.measureSets || [];
      // De server maakt namen als "<laagnaam>, <veldwaarde>". Filter op de
      // veldwaarde zodat het niet uitmaakt hoe de laag heet.
      _generatedMeasures = allSets.filter(ms => {
        const suffix = String(ms.name ?? '').split(/,\s*/).pop();
        return suffix === _currentValue;
      });
      renderResults(_generatedMeasures, allSets.length);
      updateGenerateButton();
      if (_generatedMeasures.length) {
        prefillScenarioName(_currentValue);
      }
    } catch (err) {
      setStatus(t('measureSetGenerateError', err?.message || err), 'error');
    }
  }

  function renderResults(measures, totalGenerated) {
    const results = byId('measureSetResults');
    results.innerHTML = '';

    if (!measures.length) {
      setStatus(t('measureSetEmptyResult'), 'info');
      return;
    }

    const summary = el('div', 'measure-set-summary', t('measureSetGeneratedFor', measures.length));
    results.appendChild(summary);

    // Toon de wijzigingen van de geselecteerde maatregelset
    const ms = measures[0];
    const changes = ms.changes || [];
    if (changes.length) {
      const list = el('div', 'measure-set-changes');
      const head = el('div', 'measure-set-changes-header', `${ms.name}: ${changes.length} wegvak(ken)`);
      list.appendChild(head);
      changes.slice(0, 25).forEach(ch => {
        list.appendChild(el('div', 'measure-set-change-item',
          `link <b>${ch.linkId}</b> → capaciteit ${ch.capacity ?? 0}`));
      });
      if (changes.length > 25) {
        list.appendChild(el('div', 'measure-set-change-item more',
          `… en ${changes.length - 25} meer`));
      }
      results.appendChild(list);
    }

    setStatus(t('measureSetStatusReady'));
  }

  function prefillScenarioName(value) {
    const input = byId(SCENARIO_INPUT_ID);
    if (input && !input.value.trim()) {
      input.value = t('measureSetScenarioName', value);
    }
  }

  // -- Inladen als scenario -------------------------------------------------
  function useAllGeneratedMeasures() {
    if (!_generatedMeasures.length) return;

    const applyBtn = byId('applyChangesBtn');
    if (!applyBtn) {
      alert('Wijzigingen-paneel is niet beschikbaar.');
      return;
    }

    // Converteer gegenereerde maatregelsets naar pendingChanges.
    // We nemen alle wijzigingen uit alle geselecteerde measure sets samen.
    // Duplicaten (zelfde linkId) worden samengevoegd: de laatste wint.
    const changeMap = new Map();
    for (const ms of _generatedMeasures) {
      for (const ch of (ms.changes || [])) {
        if (ch.linkId == null) continue;
        const linkId = ch.linkId;
        // Blijf consistent met het handmatige capaciteit-dialoogje in index.html:
        // linkId wordt als string opgeslagen, zodat lookups in linkGeomMap
        // met zowel numerieke als string-sleutels werken.
        changeMap.set(String(linkId), {
          _isLink: true,
          linkId: String(linkId),
          capacity: ch.capacity ?? 0,
          _label: `${ms.name}: link ${linkId}`,
        });
      }
    }

    const newChanges = Array.from(changeMap.values());

    if (!newChanges.length) {
      setStatus(t('measureSetEmptyResult'), 'info');
      return;
    }

    const pc = _getPendingChanges();
    if (!Array.isArray(pc)) {
      console.error('Geen pendingChanges array gevonden. Is index.html aangepast met de register-call?');
      alert('Kon wijzigingen niet inladen: wijzigingenpaneel is niet beschikbaar.');
      return;
    }
    pc.push(...newChanges);

    // Zorg dat het wijzigingenpaneel zichtbaar is (niet in read-only modus)
    const panel = byId('changesPanel');
    if (panel) panel.style.display = 'block';

    const setReadOnly = _getSetReadOnly();
    if (typeof setReadOnly === 'function') {
      try { setReadOnly(false); } catch (e) { console.warn(e); }
    } else {
      // Geen setReadOnly functie: zorg dat read-only styling uitstaat
      if (panel) panel.classList.remove('changesPanel--readonly');
    }

    const renderList = _getRenderChangesList();
    if (typeof renderList === 'function') {
      renderList();
    }

    prefillScenarioName(_currentValue);

    // Sluit dit paneel
    setPanelVisible(false);
    clearMapLayer();

    // Scroll / focus
    setTimeout(() => {
      applyBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      applyBtn.focus();
    }, 50);
  }

  // -- CSS injecteren -------------------------------------------------------
  function injectStyles() {
    if (byId('measureSetPanelStyles')) return;
    const style = document.createElement('style');
    style.id = 'measureSetPanelStyles';
    style.textContent = `
      .measure-set-panel {
        position: fixed; top: 60px; right: -420px;
        width: 360px; max-height: calc(100vh - 80px);
        background: #ffffff; border: 1px solid #e3e6ea;
        border-radius: 10px; box-shadow: 0 8px 28px rgba(35,41,49,0.14);
        font-family: 'Segoe UI', system-ui, sans-serif; font-size: 12px;
        display: flex; flex-direction: column; z-index: 80;
        transition: right 0.25s ease;
      }
      .measure-set-panel.visible { right: 16px; }
      .measure-set-header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 12px 14px; border-bottom: 1px solid #e3e6ea;
      }
      .measure-set-title { font-weight: 700; color: #de0058; font-size: 14px; }
      .measure-set-close {
        background: none; border: none; color: #6a757c; font-size: 16px;
        cursor: pointer; line-height: 1; padding: 2px;
      }
      .measure-set-close:hover { color: #de0058; }
      .measure-set-body { padding: 14px; overflow-y: auto; }
      .measure-set-dropzone {
        border: 2px dashed rgba(0,165,171,0.35); border-radius: 8px;
        padding: 18px 12px; text-align: center; color: #6a757c;
        cursor: pointer; transition: background 0.15s, border-color 0.15s;
        margin-bottom: 12px;
      }
      .measure-set-dropzone.dragover {
        background: rgba(0,165,171,0.08);
        border-color: rgba(0,165,171,0.7);
      }
      .measure-set-drop-icon { font-size: 22px; margin-bottom: 6px; }
      .measure-set-drop-text { font-size: 12px; line-height: 1.35; }
      .measure-set-dropzone input[type="file"] { display: none; }
      .measure-set-controls label {
        display: block; margin-bottom: 10px; color: #4b5159;
      }
      .measure-set-controls label > span {
        display: block; font-size: 11px; font-weight: 600;
        text-transform: uppercase; letter-spacing: .05em;
        color: #6a757c; margin-bottom: 4px;
      }
      .measure-set-controls select {
        width: 100%; padding: 6px 8px; font-size: 12px;
        border: 1px solid #e3e6ea; border-radius: 6px;
        background: #f4f6f8; color: #232931;
        font-family: inherit;
      }
      .measure-set-buttons { display: flex; gap: 8px; margin-top: 12px; }
      .measure-set-buttons button {
        flex: 1 1 auto; padding: 8px 10px; border-radius: 7px;
        border: 1px solid #e3e6ea; background: #f4f6f8; color: #4b5159;
        font-size: 12px; cursor: pointer; font-weight: 600; font-family: inherit;
      }
      .measure-set-buttons button:disabled {
        opacity: 0.5; cursor: not-allowed;
      }
      .measure-set-buttons button:not(:disabled):hover { background: #e8ebee; }
      #measureSetGenerateBtn {
        background: #00a5ab; border-color: #00a5ab; color: #fff;
      }
      #measureSetGenerateBtn:not(:disabled):hover { background: #008f94; }
      #measureSetUseAllBtn {
        background: #dd7a00; border-color: #dd7a00; color: #fff;
      }
      #measureSetUseAllBtn:not(:disabled):hover { background: #c96800; }
      .measure-set-status {
        margin-top: 10px; font-size: 11px; color: #00a5ab; min-height: 15px;
        line-height: 1.35;
      }
      .measure-set-status.error { color: #e63312; }
      .measure-set-status.info { color: #6a757c; }
      .measure-set-results { margin-top: 12px; }
      .measure-set-summary {
        font-weight: 700; color: #232931; margin-bottom: 8px;
      }
      .measure-set-changes {
        border: 1px solid #e3e6ea; border-radius: 6px; overflow: hidden;
        max-height: 240px; overflow-y: auto;
      }
      .measure-set-changes-header {
        background: #f4f6f8; padding: 6px 8px; font-weight: 600;
        color: #4b5159; border-bottom: 1px solid #e3e6ea;
      }
      .measure-set-change-item {
        padding: 5px 8px; border-bottom: 1px solid rgba(35,41,49,0.04);
        font-size: 11px; color: #4b5159;
      }
      .measure-set-change-item.more { color: #6a757c; font-style: italic; }
      .measure-set-change-item:last-child { border-bottom: none; }
      .measure-set-tooltip {
        position: fixed; z-index: 100;
        background: rgba(35, 41, 49, 0.9); color: #fff;
        padding: 6px 10px; border-radius: 6px;
        font-family: 'Segoe UI', system-ui, sans-serif; font-size: 12px;
        pointer-events: none; white-space: nowrap;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
      }
      .measure-set-tooltip:empty { display: none; }
    `;
    document.head.appendChild(style);
  }

  // -- Initialisatie --------------------------------------------------------
  function init() {
    injectStyles();
    ensureToolbarButton();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
