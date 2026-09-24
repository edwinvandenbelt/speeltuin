/**
 * left-menu-panel.js — "Achtergronden"-blok voor het linker menu-paneel.
 *
 * Deze module is los geladen in index.html (na de hoofdscript) en injecteert
 * alleen het "Achtergronden"-blok (radiobuttons Kaart/Luchtfoto/Geen) als
 * laatste blok in #leftMenuBody, direct boven de legenda.
 *
 * Hergebruikt de bestaande CSS-klassen (.lmp-block, .lmp-block-header,
 * .lmp-block-arrow, .lmp-block-body, .lmp-radio-row) die al in index.html
 * gedefinieerd zijn — er wordt hier geen eigen CSS geïnjecteerd.
 *
 * Afhankelijkheden: de globale variabelen/functies uit index.html:
 *   window._applyBasemapStyle(style), window._basemapStyleSafe,
 *   window.applyLang / T() (optioneel, voor i18n-labels).
 */
(function () {
  'use strict';

  const byId = id => document.getElementById(id);
  const el = (tag, cls, html) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  };

  // -- Localisatie: val terug op NL-teksten als de index.html T() ontbreekt
  const i18n = {
    settingsBasemapLabel: 'Achtergronden',
    settingsBasemapMap:   'Kaart',
    settingsBasemapSat:   'Luchtfoto',
    settingsBasemapNone:  'Geen',
  };
  function t(key) {
    let val = typeof T === 'function' ? T(key) : null;
    if (val == null || val === key) val = i18n[key] ?? key;
    return val;
  }

  function buildBlock() {
    const block = el('div', 'lmp-block collapsed');
    block.dataset.block = 'backgrounds';

    const header = el('div', 'lmp-block-header');
    header.innerHTML =
      `<span data-i18n="settingsBasemapLabel">${t('settingsBasemapLabel')}</span>` +
      `<span class="lmp-block-arrow">▾</span>`;
    header.addEventListener('click', () => block.classList.toggle('collapsed'));

    const body = el('div', 'lmp-block-body');

    const options = [
      { value: 'map',       key: 'settingsBasemapMap' },
      { value: 'satellite', key: 'settingsBasemapSat' },
      { value: 'none',      key: 'settingsBasemapNone' },
    ];

    const current = window._basemapStyleSafe || localStorage.getItem('basemapStyle') || 'map';

    options.forEach(opt => {
      const row = el('label', 'lmp-radio-row');
      const radio = el('input');
      radio.type = 'radio';
      radio.name = 'lmpBasemap';
      radio.value = opt.value;
      radio.checked = opt.value === current;
      radio.addEventListener('change', () => {
        if (radio.checked && typeof window._applyBasemapStyle === 'function') {
          window._applyBasemapStyle(opt.value);
        }
      });

      const label = el('span');
      label.dataset.i18n = opt.key;
      label.textContent = t(opt.key);

      row.appendChild(radio);
      row.appendChild(label);
      body.appendChild(row);
    });

    block.appendChild(header);
    block.appendChild(body);
    return block;
  }

  function install() {
    const leftMenuBody = byId('leftMenuBody');
    if (!leftMenuBody) return; // niet aanwezig (bijv. index2.html)
    if (byId('leftMenuBody').querySelector('[data-block="backgrounds"]')) return; // al geïnstalleerd

    leftMenuBody.appendChild(buildBlock());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
