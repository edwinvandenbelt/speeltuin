// ============================================================
// tools-meta.js — versie, wijzigingen en contact van deze tool
// De weergave (versievenster en Contact-menu) zit hieronder.
// Hergebruikt de bestaande taal-infrastructuur van main.js
// (currentLang / T()) i.p.v. een los GA-taalsysteem.
// ============================================================

// Alleen informatie over de tool. Verschijnt onder de versieknop.
const TOOL_META = {
  name:        'GMT Digital Twin',
  version:     '2026.11.12',
  date:        '2026-11-12',
  description: {
    nl: 'Digitale tweeling van een verkeersnetwerk: 3D-visualisatie en simulatie van een gebied.',
    en: 'Digital twin of a traffic network: 3D visualisation and simulation of an area.',
    fi: 'Liikenneverkon digitaalinen kaksonen: alueen 3D-visualisointi ja simulointi.'
  }
};

// Persoonsgegevens van de contactpersoon. Verschijnen alleen in het
// Contact-menu rechts in de kopbalk. Een leeg veld ('') wordt weggelaten.
const TOOL_CONTACTS = [
  {
    name:  'Edwin van den Belt',
    role:  'Business developer',
    team:  '',
    email: 'evdbelt@dat.nl',
    phone: ''
  }
];

// Wijzigingen voor eindgebruikers, nieuwste bovenaan.
// TOOL_META.version en date zijn gelijk aan de bovenste entry.
const CHANGELOG = [
  {
    version: '2026.11.12', date: '2026-11-12',
    changes: {
      nl: ['Goudappel-huisstijl toegepast: kopbalk, kleuren, iconen, taalwissel en versie-/contactinformatie.'],
      en: ['Applied the Goudappel house style: header, colours, icons, language switch and version/contact info.'],
      fi: ['Goudappelin ilme otettu käyttöön: yläpalkki, värit, kuvakkeet, kielivalinta sekä versio- ja yhteystiedot.']
    }
  }
];

// Optioneel: links naar andere tools (verschijnen in het versievenster).
const OTHER_TOOLS = [
  // { name: { nl: 'Analyzer', en: 'Analyzer' }, url: 'https://…' }
];

// ── Weergave: versievenster en Contact-menu ────────────────────────────────
// Leest de taal via de bestaande currentLang-variabele van main.js (NL/EN/FI),
// niet via een los GA-taalsysteem.
var GA_INFO_TXT = {
  nl: { info: 'Versie-informatie', version: 'Versie', date: 'Datum', description: 'Beschrijving',
        changes: 'Wijzigingen bekijken', changelog: 'Wijzigingen', back: 'Terug', others: 'Andere tools', close: 'Sluiten' },
  en: { info: 'Version information', version: 'Version', date: 'Date', description: 'Description',
        changes: 'View changes', changelog: 'Changes', back: 'Back', others: 'Other tools', close: 'Close' },
  fi: { info: 'Versiotiedot', version: 'Versio', date: 'Pvm', description: 'Kuvaus',
        changes: 'Näytä muutokset', changelog: 'Muutokset', back: 'Takaisin', others: 'Muut työkalut', close: 'Sulje' }
};
var gaInfoView = 'info';

// Leest 'ui-lang' rechtstreeks uit localStorage (dezelfde sleutel als main.js
// gebruikt voor currentLang) i.p.v. een directe scriptverwijzing — dat voorkomt
// laadvolgorde-afhankelijkheid tussen dit bestand en scripts/main.js.
function gaGetLang() {
  var l = 'NL';
  try { l = localStorage.getItem('ui-lang') || 'NL'; } catch (e) {}
  l = l.toLowerCase();
  return (l === 'en' || l === 'fi') ? l : 'nl';
}
// gaL({ nl: '…', en: '…' }) kiest de tekst in de huidige taal; een gewone tekst blijft gelijk
function gaL(v) {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return v;
  var lang = gaGetLang();
  return v[lang] != null ? v[lang] : v.nl;
}
function gaEsc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}
function gaInfoHtml() {
  var t = GA_INFO_TXT[gaGetLang()], m = TOOL_META;
  var html = '<button class="ga-modal__close ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="' + t.close + '">' +
    '<svg class="ga-icon" aria-hidden="true"><use href="#ga-i-close"/></svg></button>';
  if (gaInfoView === 'changelog') {
    var log = typeof CHANGELOG !== 'undefined' ? CHANGELOG : [];
    return html + '<h2 class="ga-h2" id="gaInfoTitel">' + t.changelog + '</h2>' +
      log.map(function (v) {
        return '<div class="ga-changelog"><div class="ga-row"><span class="ga-tag">v' + gaEsc(v.version) + '</span>' +
          '<span class="ga-meta">' + gaEsc(v.date) + '</span></div><ul class="ga-list">' +
          (gaL(v.changes) || []).map(function (c) { return '<li>' + gaEsc(c) + '</li>'; }).join('') + '</ul></div>';
      }).join('') +
      '<div class="ga-modal__actions"><button class="ga-btn ga-btn--sm ga-btn--outline" type="button" data-ga-info="info">' + t.back + '</button></div>';
  }
  var others = typeof OTHER_TOOLS !== 'undefined' ? OTHER_TOOLS : [];
  return html + '<h2 class="ga-h2" id="gaInfoTitel">' + gaEsc(gaL(m.name)) + '</h2>' +
    '<table class="ga-info">' +
      '<tr><th>' + t.version + '</th><td>' + gaEsc(m.version) + '</td></tr>' +
      '<tr><th>' + t.date + '</th><td>' + gaEsc(m.date) + '</td></tr>' +
      (m.description ? '<tr><th>' + t.description + '</th><td>' + gaEsc(gaL(m.description)) + '</td></tr>' : '') +
    '</table>' +
    (others.length ? '<h3 class="ga-h3">' + t.others + '</h3><ul class="ga-list">' + others.map(function (o) {
      return '<li><a href="' + gaEsc(o.url) + '" target="_blank" rel="noopener">' + gaEsc(gaL(o.name)) + '</a></li>';
    }).join('') + '</ul>' : '') +
    '<div class="ga-modal__actions"><button class="ga-btn ga-btn--sm ga-btn--outline" type="button" data-ga-info="changelog">' + t.changes + '</button></div>';
}
function gaContactHtml(p) {
  var role = [gaL(p.role), p.team].filter(Boolean).join(' · ');
  var icon = function (id) { return '<svg class="ga-icon" aria-hidden="true"><use href="#ga-i-' + id + '"/></svg>'; };
  return '<div class="ga-contact__person"><span class="ga-contact__name">' + gaEsc(p.name) + '</span>' +
      (role ? '<span class="ga-contact__role">' + gaEsc(role) + '</span>' : '') + '</div>' +
    (p.email ? '<a class="ga-dropdown__item" role="menuitem" href="mailto:' + gaEsc(p.email) + '">' + icon('mail') + gaEsc(p.email) + '</a>' : '') +
    (p.phone ? '<a class="ga-dropdown__item" role="menuitem" href="tel:' + gaEsc(String(p.phone).replace(/[^+0-9]/g, '')) + '">' + icon('phone') + gaEsc(p.phone) + '</a>' : '');
}
function gaRenderToolInfo() {
  if (typeof TOOL_META === 'undefined') return;
  var btn = document.getElementById('versionBtn');
  if (btn) { btn.textContent = 'v' + TOOL_META.version; btn.title = GA_INFO_TXT[gaGetLang()].info; }
  var menu = document.getElementById('gaContact');
  if (menu) {
    var people = typeof TOOL_CONTACTS !== 'undefined' ? TOOL_CONTACTS : [];
    menu.closest('.ga-contact').hidden = !people.length;
    menu.innerHTML = people.map(gaContactHtml).join('<hr class="ga-dropdown__sep">');
  }
  var box = document.getElementById('gaInfoBox');
  if (box) box.innerHTML = gaInfoHtml();
}
function gaInitToolInfo() {
  if (typeof TOOL_META === 'undefined' || document.getElementById('gaInfo')) return;
  var ov = document.createElement('div');
  ov.className = 'ga-overlay';
  ov.id = 'gaInfo';
  ov.innerHTML = '<div class="ga-modal" id="gaInfoBox" role="dialog" aria-modal="true" aria-labelledby="gaInfoTitel"></div>';
  document.body.appendChild(ov);
  var btn = document.getElementById('versionBtn');
  var close = function () { ov.classList.remove('is-open'); if (btn) btn.focus(); };
  if (btn) btn.addEventListener('click', function () {
    gaInfoView = 'info';
    gaRenderToolInfo();
    ov.classList.add('is-open');
    ov.querySelector('.ga-modal__close').focus();
  });
  ov.addEventListener('click', function (e) {
    var view = e.target.closest('[data-ga-info]');
    if (view) { gaInfoView = view.getAttribute('data-ga-info'); gaRenderToolInfo(); ov.querySelector('.ga-modal__close').focus(); }
    else if (e.target === ov || e.target.closest('.ga-modal__close')) close();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && ov.classList.contains('is-open')) close();
  });
  gaRenderToolInfo();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', gaInitToolInfo);
else gaInitToolInfo();

// ── Dropdownmenu's (o.a. Contact): openen/sluiten, klik ernaast en Escape sluiten ──
document.addEventListener('click', function (e) {
  var btn = e.target.closest('[data-ga-dropdown]');
  document.querySelectorAll('[data-ga-dropdown][aria-expanded="true"]').forEach(function (b) {
    if (b !== btn) { b.setAttribute('aria-expanded', 'false'); b.nextElementSibling.hidden = true; }
  });
  if (btn) {
    var open = btn.getAttribute('aria-expanded') !== 'true';
    btn.setAttribute('aria-expanded', String(open));
    btn.nextElementSibling.hidden = !open;
  } else if (e.target.closest('.ga-dropdown__item')) {
    var menu = e.target.closest('.ga-dropdown__menu');
    menu.hidden = true;
    menu.previousElementSibling.setAttribute('aria-expanded', 'false');
  }
});
document.addEventListener('keydown', function (e) {
  if (e.key !== 'Escape') return;
  document.querySelectorAll('[data-ga-dropdown][aria-expanded="true"]').forEach(function (b) {
    b.setAttribute('aria-expanded', 'false'); b.nextElementSibling.hidden = true; b.focus();
  });
});
