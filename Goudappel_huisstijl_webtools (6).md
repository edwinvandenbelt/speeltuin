# Goudappel huisstijl voor webtools

> Gebaseerd op de vormgeving van goudappel.nl · Huisstijl-tool v1.6.0 (2026-11-03) · Opgesteld door: Tom Gerrits

## Gebruik van dit document

Dit document beschrijft hoe webtools van Goudappel eruitzien en werken, zodat ze aansluiten bij goudappel.nl en praktisch bruikbaar zijn. Het is bedoeld voor ontwikkelaars en AI-assistenten die een tool bouwen.

1. Sla **Volledige CSS** op als `styles/goudappel-web.css` en **Volledige JS** als `scripts/goudappel-web.js`, en plak de **Sprite** (logo en iconen) direct na `<body>`. Andere bestanden van de huisstijl zijn niet nodig.
2. Begin met het **Startsjabloon**. De kopbalk ligt vast, inclusief **Contact** en **NL | EN** rechts. Voor een werktool volg je het patroon **Toolindeling**.
3. **Maak de tool tweetalig (Nederlands en Engels).** Dit is verplicht, tenzij de opdrachtgever expliciet om één taal vraagt. Zet alle zichtbare tekst in `scripts/i18n.js` (`GA_I18N`, met `nl` en `en` per sleutel) en volg **Tweetaligheid**.
4. **Maak `scripts/tools-meta.js` volgens het sjabloon bij Versie-info en contact.** `TOOL_META` bevat alleen informatie over de tool (naam, versie, datum, beschrijving); die verschijnt onder de versieknop. Naam, e-mail en telefoon van de ontwikkelaar of contactpersoon horen in `TOOL_CONTACTS` en verschijnen alleen in het Contact-menu. Vraag de opdrachtgever om deze gegevens en verzin ze niet.
5. Gebruik de `ga-`-classes uit de voorbeelden. Eigen onderdelen bouw je met de CSS-variabelen (`var(--ga-…)`) en de iconenstijl.
6. *Vast* volg je altijd, *Standaard* volg je tenzij er een goede reden is, *Richtlijn* vul je vrij in binnen de huisstijl.
7. Laat de credits van de huisstijl staan: het commentaar in de `<head>` van het startsjabloon en bovenaan de CSS en de JS.

## Uitgangspunten

- **De kopbalk ligt vast, de rest is een richtlijn.** De indeling van je tool (zijpaneel, werkvlak, tabel) bepaal je zelf, maar een zijpaneel is altijd in- en uitklapbaar (zie Toolindeling).
- **Rood is een accent.** Gebruik rood voor de primaire actie, de actieve status en links. Gebruik één rode knop per paneel; al het andere is zwart, grijs of wit.
- **Bruikbaarheid gaat voor.** Tools zijn compacter dan de website: tekst van 14–16px, kleine knoppen en weinig witruimte. Maak niets groter alleen omdat het in de huisstijl staat.
- **Gereedschap als iconen, gegroepeerd per thema.** Gebruik iconen uit de set, met een tooltip, en groepeer ze onder elkaar (Selectie, Navigatie, Tekenen, Bewerken, Weergave).
- **Rustige basis:** Open Sans, een wit vlak, zwarte tekst en lichtgrijze scheidingslijnen. Gebruik geen extra kleuren, verlopen, schaduwen of afrondingen.
- **Afwijken mag** waar het werk erom vraagt, zoals bij kaartlagen, grafieken of datakleuren. Gebruik dan wel de variabelen, het lettertype en de iconenstijl.
- **Tweetalig: Nederlands en Engels.** Elke tool heeft rechts in de kopbalk de wissel NL | EN en is in beide talen volledig te gebruiken. Alleen als de opdrachtgever expliciet om één taal vraagt, laat je dit weg.
- **Tool en persoon gescheiden.** De versieknop toont alleen informatie over de tool. Naam, e-mail en telefoon van de contactpersoon staan alleen onder Contact, rechts in de kopbalk.

## Kleuren

| Kleur | HEX | Variabele | Gebruik |
|---|---|---|---|
| Goudappel rood | `#DE0058` | `--ga-rood` | Primaire knop, links, accenten |
| Rood donker | `#AB0144` | `--ga-rood-donker` | Hover en actieve status |
| Rood licht | `#FFF4F4` | `--ga-rood-licht` | Achtergrond van een actief of geselecteerd item |
| Zwart | `#000000` | `--ga-tekst` | Tekst, koppen en iconen |
| Donkergrijs | `#4B5159` | `--ga-tekst-2` | Secundaire tekst en metadata |
| Randgrijs | `#746E73` | `--ga-rand` | Rand van invoervelden |
| Lichtgrijs | `#E8E7E8` | `--ga-lijn` | Scheidingslijnen en randen van panelen |
| Vlakgrijs | `#F6F6F6` | `--ga-vlak` | Werkvlak (kaart, canvas) en hover van iconen |
| Uitgeschakeld | `#EFEFEF` | `--ga-uit` | Uitgeschakelde velden |
| Focus roze | `#EE7EAA` | `--ga-focus-veld` | Rand van een actief invoerveld |
| Focus blauw | `#0058DE` | `--ga-focus` | Focusrand bij toetsenbordbediening |
| Foutrood | `#E63312` | `--ga-fout` | Foutmeldingen |

# Start

## Snelstart

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Een nieuwe tool begin je met dit sjabloon. Het bevat de kopbalk (met Contact en NL | EN), een zijpaneel en een werkvlak. Download de CSS en JS met de knop bovenaan en plak de sprite (zie Iconen) direct na `<body>`. De sprite bevat het logo en alle iconen, dus losse bestanden zijn niet nodig.

- Laad eerst `goudappel-web.css` en daarna de eigen CSS van de tool. Overschrijf daarin geen `ga-`-classes, maar maak eigen classes met de variabelen.
- Onderaan de pagina, in deze volgorde: `goudappel-web.js` (huisstijl), `i18n.js` (vertaaltabel), `tools-meta.js` (versie en contact) en de eigen scripts van de tool.
- Laat de ids `versionBtn` en `gaContact` staan: daarmee vult de huisstijl het versievenster en het Contact-menu.
- Een tool zonder zijpaneel (bijvoorbeeld een formulier of rapport) zet de inhoud in `.ga-container`.
- Het zijpaneel links (instellingen) staat standaard open, het paneel rechts is optioneel en staat standaard dicht. Beide klap je in en uit met de verticale tab in de balk aan de rand. Heb je geen paneel rechts nodig, laat het dan weg.
- De volledige toolindeling staat bij Patronen › Toolindeling.

```html
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Opmaak volgens de Goudappel huisstijl voor webtools, opgesteld door Tom Gerrits -->
  <title data-i18n="pagina.titel">Naam van de tool | Goudappel</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700;800&display=swap">
  <link rel="stylesheet" href="styles/goudappel-web.css">
  <link rel="stylesheet" href="styles/main.css"> <!-- eigen opmaak van de tool -->
</head>
<body>
  <!-- Plak hier de sprite met logo en iconen (Iconen › Sprite) -->

  <header class="ga-header">
    <a class="ga-header__logo" href="./"><svg class="ga-logo" viewBox="0 0 182 32" role="img" aria-label="Goudappel"><use href="#ga-logo"/></svg></a>
    <div class="ga-header__tool">
      <span class="ga-header__title" data-i18n="tool.naam">Naam van de tool</span>
      <button class="ga-header__version" id="versionBtn" type="button">v1.0.0</button>
    </div>
    <nav class="ga-nav" aria-label="Hoofdmenu" data-i18n-attr="aria-label:nav.label">
      <a href="#" aria-current="page" data-i18n="nav.overzicht">Overzicht</a>
    </nav>
    <div class="ga-header__meta">
      <div class="ga-dropdown ga-contact">
        <button class="ga-header__link" type="button" aria-expanded="false" aria-haspopup="true" data-ga-dropdown>Contact <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-down"/></svg></button>
        <div class="ga-dropdown__menu" id="gaContact" role="menu" hidden></div> <!-- gevuld vanuit tools-meta.js -->
      </div>
      <div class="ga-lang" role="group" aria-label="Taal / Language">
        <button type="button" data-lang="nl" aria-pressed="true" title="Nederlands">NL</button>
        <span class="ga-lang__sep" aria-hidden="true">|</span>
        <button type="button" data-lang="en" aria-pressed="false" title="English">EN</button>
      </div>
    </div>
  </header>

  <div class="ga-app">
    <!-- Zijpaneel links: standaard uitgeklapt. Meer panelen = meer tabs in dezelfde balk. -->
    <div class="ga-side ga-side--links" data-ga-side="links">
      <div class="ga-side__bar" role="group" aria-label="Panelen links">
        <button class="ga-side__tab" type="button" aria-expanded="true" aria-controls="paneelInstellingen"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-right"/></svg><span data-i18n="paneel.instellingen">Instellingen</span></button>
      </div>
      <aside class="ga-side__panel" id="paneelInstellingen">
        <h1 class="ga-h3" data-i18n="tool.naam">Naam van de tool</h1>
        <p class="ga-small ga-muted" data-i18n="tool.uitleg">Wat doet deze tool, in één zin.</p>
        <!-- Inklapbare secties met instellingen -->
      </aside>
    </div>
    <main class="ga-app__main ga-workspace">
      <!-- Werkvlak: kaart, tabel, grafiek… -->
    </main>
    <!-- Optioneel: zijpaneel rechts voor naslag of informatie, standaard ingeklapt -->
    <div class="ga-side ga-side--rechts" data-ga-side="rechts">
      <div class="ga-side__bar" role="group" aria-label="Panelen rechts">
        <button class="ga-side__tab" type="button" aria-expanded="false" aria-controls="paneelInformatie"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-right"/></svg><span data-i18n="paneel.informatie">Informatie</span></button>
      </div>
      <aside class="ga-side__panel" id="paneelInformatie" hidden>
        <!-- Uitleg, resultaten of legenda -->
      </aside>
    </div>
  </div>

  <script src="scripts/goudappel-web.js"></script> <!-- Volledige JS van de huisstijl -->
  <script src="scripts/i18n.js"></script>          <!-- vertaaltabel GA_I18N -->
  <script src="scripts/tools-meta.js"></script>    <!-- versie, wijzigingen en contact -->
  <script src="scripts/main.js"></script>          <!-- eigen code van de tool -->
</body>
</html>
```

## Tweetaligheid (NL | EN)

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Tools zijn standaard tweetalig: Nederlands en Engels. Rechts in de kopbalk staat de wissel **NL | EN**, zoals op goudappel.nl. Een klik vertaalt de pagina direct, zonder te herladen. De keuze wordt onthouden in de browser (localStorage, sleutel `ga-lang`) en geldt zo ook voor andere Goudappel-tools.

- Elke tool is in het Nederlands en het Engels volledig te gebruiken. Laat de wissel alleen weg als de opdrachtgever expliciet om één taal vraagt.
- Alle zichtbare tekst staat in de vertaaltabel `GA_I18N` (`scripts/i18n.js`), met voor elke sleutel een `nl`- en een `en`-tekst. Dat geldt ook voor knoppen, tooltips, placeholders, meldingen, foutteksten, lege staten en de paginatitel.
- Vaste tekst in de HTML krijgt `data-i18n="sleutel"`; een attribuut krijgt `data-i18n-attr="placeholder:sleutel;aria-label:sleutel"`. Zet de Nederlandse tekst er ook in, als beginwaarde.
- Tekst die JavaScript maakt, haal je op met `gaT('sleutel')`, eventueel met waarden: `gaT('melding.klaar', { n: 12 })`. Teksten in gegevens, zoals in `tools-meta.js`, mogen `{ nl: …, en: … }` zijn; die lees je met `gaL(…)`.
- Bij een taalwissel stuurt de pagina het event `ga-lang`. Bouw daarop alles opnieuw op wat JavaScript heeft gemaakt: lijsten, tabellen, legenda's en grafieklabels.
- Getallen en datums volgen de taal: `toLocaleString(gaGetLang() === 'en' ? 'en-GB' : 'nl-NL')`.
- Vertaal geen gegevens: plaatsnamen, kolomnamen uit een bestand en invoer van de gebruiker blijven zoals ze zijn.

```html
<!-- De wissel staat in de kopbalk (zie Kopbalk) -->
<div class="ga-lang" role="group" aria-label="Taal / Language">
  <button type="button" data-lang="nl" aria-pressed="true" title="Nederlands">NL</button>
  <span class="ga-lang__sep" aria-hidden="true">|</span>
  <button type="button" data-lang="en" aria-pressed="false" title="English">EN</button>
</div>

<!-- Vaste tekst en attributen -->
<h3 class="ga-h3" data-i18n="tool.naam">Bereikbaarheid</h3>
<div class="ga-row">
  <input class="ga-input ga-input--sm" type="search" placeholder="Zoeken…" aria-label="Zoeken…" data-i18n-attr="placeholder:veld.zoeken;aria-label:veld.zoeken" style="width:180px">
  <button class="ga-btn ga-btn--sm" type="button" data-i18n="actie.berekenen">Berekenen</button>
</div>
```

`i18n.js`:

```js
// ============================================================
// i18n.js — vertaaltabel van deze tool (Nederlands en Engels)
// Elke sleutel heeft een nl- en een en-tekst. {n} wordt ingevuld
// via gaT('sleutel', { n: 12 }).
// ============================================================
const GA_I18N = {
  nl: {
    'pagina.titel':    'Bereikbaarheid | Goudappel',
    'tool.naam':       'Bereikbaarheid',
    'nav.label':       'Hoofdmenu',
    'nav.kaart':       'Kaart',
    'actie.berekenen': 'Berekenen',
    'veld.zoeken':     'Zoeken…',
    'melding.klaar':   'Klaar: {n} inwoners bereikbaar'
  },
  en: {
    'pagina.titel':    'Accessibility | Goudappel',
    'tool.naam':       'Accessibility',
    'nav.label':       'Main menu',
    'nav.kaart':       'Map',
    'actie.berekenen': 'Calculate',
    'veld.zoeken':     'Search…',
    'melding.klaar':   'Done: {n} residents within reach'
  }
};
```

```js
// Tweetaligheid (NL | EN): teksten uit GA_I18N, keuze bewaard in localStorage
var GA_LANG_KEY = 'ga-lang';
var gaLangNu = null;
function gaGetLang() {
  if (!gaLangNu) { try { gaLangNu = localStorage.getItem(GA_LANG_KEY); } catch (e) {} }
  return gaLangNu === 'en' ? 'en' : 'nl';
}
function gaFindText(key) {
  var d = typeof GA_I18N !== 'undefined' ? GA_I18N : {};
  var lang = gaGetLang();
  if (d[lang] && d[lang][key] != null) return d[lang][key];
  if (d.nl && d.nl[key] != null) return d.nl[key];
  return null;
}
// gaT('sleutel') of gaT('sleutel', { n: 12 }) voor tekst met {n}
function gaT(key, vars) {
  var s = gaFindText(key);
  if (s == null) return key;
  return String(s).replace(/\{(\w+)\}/g, function (m, k) { return vars && vars[k] != null ? vars[k] : m; });
}
// gaL({ nl: '…', en: '…' }) kiest de tekst in de huidige taal; een gewone tekst blijft gelijk
function gaL(v) {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return v;
  var lang = gaGetLang();
  return v[lang] != null ? v[lang] : v.nl;
}
function gaApplyLang() {
  var lang = gaGetLang();
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(function (el) {
    var s = gaFindText(el.getAttribute('data-i18n'));
    if (s != null) el.textContent = s;
  });
  document.querySelectorAll('[data-i18n-attr]').forEach(function (el) {
    el.getAttribute('data-i18n-attr').split(';').forEach(function (pair) {
      var p = pair.split(':');
      var s = p.length === 2 ? gaFindText(p[1].trim()) : null;
      if (s != null) el.setAttribute(p[0].trim(), s);
    });
  });
  document.querySelectorAll('.ga-lang [data-lang]').forEach(function (b) {
    b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === lang));
  });
  document.dispatchEvent(new CustomEvent('ga-lang', { detail: { lang: lang } }));
}
function gaSetLang(lang) {
  gaLangNu = lang;
  try { localStorage.setItem(GA_LANG_KEY, lang); } catch (e) {}
  gaApplyLang();
}
document.addEventListener('click', function (e) {
  var b = e.target.closest('.ga-lang [data-lang]');
  if (b && b.getAttribute('aria-pressed') !== 'true') gaSetLang(b.getAttribute('data-lang'));
});
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', gaApplyLang);
else gaApplyLang();
```

## Versie-info en contact

**Status: Vast** — Gebruik zoals beschreven.

Elke tool heeft `scripts/tools-meta.js`. Daaruit vult de huisstijl twee plekken in de kopbalk. De **versieknop** naast de toolnaam opent informatie over de tool zelf: naam, versie, datum, beschrijving, wijzigingen en links naar andere tools. **Contact** rechts in de kopbalk opent een menu met de contactpersoon: naam, rol, e-mail en telefoon.

- Houd tool en persoon gescheiden. `TOOL_META` bevat alleen informatie over de tool. Naam, e-mailadres en telefoonnummer van de ontwikkelaar of contactpersoon staan alleen in `TOOL_CONTACTS` en verschijnen alleen in het Contact-menu.
- Neem de contactgegevens over van de opdrachtgever en verzin ze niet. Is iets niet bekend, laat het veld dan leeg (`''`); het wordt dan weggelaten.
- Meer contactpersonen mag, bijvoorbeeld een ontwikkelaar en een inhoudelijk contactpersoon. Geef ieder een rol.
- `CHANGELOG` is voor eindgebruikers: korte zinnen over wat ze zien of kunnen doen, nieuwste versie bovenaan. `TOOL_META.version` en `date` zijn gelijk aan de bovenste entry.
- Teksten mogen tweetalig zijn als `{ nl: …, en: … }`, de wijzigingen per versie als `{ nl: […], en: […] }`.
- De weergave zit in de huisstijl-JS: het versievenster en het Contact-menu worden vanzelf gevuld als de kopbalk `#versionBtn` en `#gaContact` bevat. Schrijf hier geen eigen code voor.

`tools-meta.js`:

```js
// ============================================================
// tools-meta.js — versie, wijzigingen en contact van deze tool
// De weergave (versievenster en Contact-menu) zit in de huisstijl-JS.
// Teksten mogen tweetalig zijn: { nl: '…', en: '…' }.
// ============================================================

// Alleen informatie over de tool. Verschijnt onder de versieknop.
const TOOL_META = {
  name:        { nl: 'Naam van de tool', en: 'Name of the tool' },
  version:     '1.0.0',
  date:        '2026-01-01',
  description: { nl: 'Wat de tool doet, in één zin.', en: 'What the tool does, in one sentence.' }
};

// Persoonsgegevens van de ontwikkelaar of contactpersoon.
// Verschijnen alleen in het Contact-menu rechts in de kopbalk.
// Gebruik de gegevens die de opdrachtgever opgeeft; verzin niets.
// Een leeg veld ('') wordt weggelaten.
const TOOL_CONTACTS = [
  {
    name:  'Voornaam Achternaam',
    role:  { nl: 'Ontwikkelaar', en: 'Developer' },
    team:  'Team',
    email: 'naam@goudappel.nl',
    phone: ''
  }
];

// Wijzigingen voor eindgebruikers, nieuwste bovenaan.
// TOOL_META.version en date zijn gelijk aan de bovenste entry.
const CHANGELOG = [
  {
    version: '1.0.0', date: '2026-01-01',
    changes: {
      nl: ['Eerste versie van de tool'],
      en: ['First version of the tool']
    }
  }
];

// Optioneel: links naar andere tools (verschijnen in het versievenster).
const OTHER_TOOLS = [
  // { name: { nl: 'Huisstijl', en: 'Branding' }, url: 'https://…' }
];
```

```js
// Versievenster en Contact-menu, gevuld uit tools-meta.js
// (TOOL_META, CHANGELOG, TOOL_CONTACTS en OTHER_TOOLS)
var GA_INFO_TXT = {
  nl: { info: 'Versie-informatie', version: 'Versie', date: 'Datum', description: 'Beschrijving',
        changes: 'Wijzigingen bekijken', changelog: 'Wijzigingen', back: 'Terug', others: 'Andere tools', close: 'Sluiten' },
  en: { info: 'Version information', version: 'Version', date: 'Date', description: 'Description',
        changes: 'View changes', changelog: 'Changes', back: 'Back', others: 'Other tools', close: 'Close' }
};
var gaInfoView = 'info';
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
  document.addEventListener('ga-lang', gaRenderToolInfo);
  gaRenderToolInfo();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', gaInitToolInfo);
else gaInitToolInfo();
```

# Fundament

## Kleuren en basis

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Dit blok bevat de variabelen en de basisopmaak. Alle andere onderdelen bouwen erop voort. Klik op een kleur om de HEX-code te kopiëren.

- Gebruik altijd een variabele (`var(--ga-rood)`) en geen losse hexcode.
- De pagina is wit en de tekst zwart. Een werkvlak, zoals een kaart of canvas, krijgt vlakgrijs (#F6F6F6).
- Scheid vlakken met lichtgrijze lijnen (#E8E7E8), niet met achtergrondkleuren of schaduwen.
- Deze kleuren zijn voor de interface. Voor grafieken en kaartklassen gebruik je de **Datakleuren**.
- Overgangen duren 200ms. De focus via het toetsenbord is een blauwe rand van 2px (#0058DE).

## Datakleuren voor grafieken

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Grafieken, diagrammen en kaartklassen in een tool krijgen dezelfde kleuren als in rapporten: de grafiekvolgorde van Goudappel. De interfacekleuren hierboven blijven leidend voor de rest van de tool. Klik op een kleur om de HEX-code te kopiëren.

- Gebruik deze kleuren alleen voor data: reeksen, categorieën en kaartklassen. Knoppen, links en de actieve status blijven in de interfacekleuren.
- Volg de volgorde: de eerste reeks rood, de tweede lichtgrijs, de derde donkergrijs, enzovoort. Sla geen kleuren over.
- In CSS gebruik je `var(--ga-data-1)` t/m `var(--ga-data-10)`. Een grafiekbibliotheek (Chart.js, ECharts, Plotly, D3) krijgt de lijst uit `gaDataColors()`.
- Lichtgrijs (#E8E7E8) valt weg op wit: geef lichte vlakken een rand van 1px in `--ga-tekst-2`, of gebruik bij twee of drie reeksen rood en donkergrijs.
- Laat kleur niet de enige drager zijn: zet labels of een legenda bij de reeksen.
- Meer dan 10 reeksen? Groepeer de kleinste als ‘Overig’ in Midgrijs (`--ga-data-8`).

| # | Kleur | HEX | Variabele | RGB |
|---|---|---|---|---|
| 1 | Goudappel rood | `#DE0058` | `--ga-data-1` | 222, 0, 88 |
| 2 | Lichtgrijs | `#E8E7E8` | `--ga-data-2` | 232, 232, 232 |
| 3 | Donkergrijs | `#4B5159` | `--ga-data-3` | 75, 81, 89 |
| 4 | Lichtblauw | `#00A7E7` | `--ga-data-4` | 0, 167, 231 |
| 5 | Grijs/paars | `#4F4757` | `--ga-data-5` | 79, 71, 87 |
| 6 | Groen | `#53B151` | `--ga-data-6` | 83, 177, 81 |
| 7 | Grijs/blauw | `#394053` | `--ga-data-7` | 57, 64, 83 |
| 8 | Midgrijs | `#6A757C` | `--ga-data-8` | 106, 117, 124 |
| 9 | Geel/oranje | `#FDC300` | `--ga-data-9` | 253, 195, 0 |
| 10 | Paars | `#5A427E` | `--ga-data-10` | 90, 66, 126 |

```js
// Datakleuren als lijst, voor grafiekbibliotheken. Leest --ga-data-1 t/m --ga-data-10.
function gaDataColors() {
  var st = getComputedStyle(document.documentElement), out = [];
  for (var i = 1; i <= 10; i++) out.push(st.getPropertyValue('--ga-data-' + i).trim());
  return out;
}
```

## Lettertype en tekst

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Open Sans, zoals op goudappel.nl. Tools gebruiken een vaste, compacte schaal. Lijsten hebben de rode opsommingstekens van de website.

- Gebruik drie gewichten: 400 voor tekst, 600 voor koppen, knoppen en menu, en 800 voor vet en labels.
- Koppen hebben gewicht 600 en een letterafstand van −0,5px. Tools: h1 28px · h2 22px · h3 18px.
- Tekst is 16px. In panelen, tabellen en tooltips 14px. Nooit kleiner dan 12px.
- Lijn tekst links uit. Centreer alleen korte, losse meldingen, zoals een lege staat.
- Getallen in tabellen staan rechts uitgelijnd, met cijfers van vaste breedte.

```html
<h1 class="ga-h1">Kop 1 — paginatitel</h1>
<h2 class="ga-h2">Kop 2 — sectie</h2>
<h3 class="ga-h3">Kop 3 — paneel of groep</h3>
<p>Platte tekst van 16px. Goudappel start per jaar gemiddeld <strong>2500 nieuwe projecten</strong>.</p>
<p class="ga-small ga-muted">Kleine secundaire tekst (14px), bijvoorbeeld een bron of toelichting.</p>
<ul class="ga-list">
  <li>Opsomming met rode punt</li>
  <li>Zoals in de teksten op goudappel.nl</li>
</ul>
<ol class="ga-list">
  <li>Genummerde stap</li>
  <li>Met rood cijfer</li>
</ol>
```

## Iconen

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Lijniconen in de stijl van goudappel.nl (de pijl, het vergrootglas en het chevronpijltje). Klik op een icoon om de losse SVG te kopiëren. In een tool gebruik je de sprite: die plak je één keer in de pagina.

- 24×24, lijndikte 2, ronde uiteinden, geen vulling. De kleur komt van de tekst (`currentColor`).
- Formaat: 16px naast tekst in een actieknop, 18px in kleine knoppen en 20px in het gereedschapspalet.
- Een icoon zonder tekst krijgt altijd een `aria-label` en een tooltip (`data-tip`).
- Een icoon heeft geen eigen kleur. Het wordt zwart, of rood donker bij hover of als het actief is.
- Ontbreekt een icoon? Teken het in dezelfde stijl. Gebruik geen iconen uit andere sets door elkaar.

| Icoon-id | Naam | Groep |
|---|---|---|
| `ga-i-select` | Selecteren | Selectie en navigatie |
| `ga-i-select-box` | Rechthoek selecteren | Selectie en navigatie |
| `ga-i-pan` | Verschuiven | Selectie en navigatie |
| `ga-i-zoom-in` | Inzoomen | Selectie en navigatie |
| `ga-i-zoom-out` | Uitzoomen | Selectie en navigatie |
| `ga-i-extent` | Passend in beeld | Selectie en navigatie |
| `ga-i-fullscreen` | Volledig scherm | Selectie en navigatie |
| `ga-i-search` | Zoeken | Selectie en navigatie |
| `ga-i-point` | Punt | Tekenen en bewerken |
| `ga-i-line` | Lijn | Tekenen en bewerken |
| `ga-i-polygon` | Vlak | Tekenen en bewerken |
| `ga-i-measure` | Meten | Tekenen en bewerken |
| `ga-i-edit` | Bewerken | Tekenen en bewerken |
| `ga-i-copy` | Kopiëren | Tekenen en bewerken |
| `ga-i-delete` | Verwijderen | Tekenen en bewerken |
| `ga-i-undo` | Ongedaan maken | Tekenen en bewerken |
| `ga-i-redo` | Opnieuw | Tekenen en bewerken |
| `ga-i-layers` | Lagen | Weergave |
| `ga-i-visible` | Zichtbaar | Weergave |
| `ga-i-hidden` | Verborgen | Weergave |
| `ga-i-labels` | Labels | Weergave |
| `ga-i-grid` | Raster | Weergave |
| `ga-i-legend` | Legenda | Weergave |
| `ga-i-cluster` | Clusters | Weergave |
| `ga-i-map` | Kaart | Weergave |
| `ga-i-table` | Tabel | Weergave |
| `ga-i-chart` | Grafiek | Weergave |
| `ga-i-download` | Downloaden | Bestand en acties |
| `ga-i-upload` | Uploaden | Bestand en acties |
| `ga-i-save` | Opslaan | Bestand en acties |
| `ga-i-link` | Link | Bestand en acties |
| `ga-i-filter` | Filter | Bestand en acties |
| `ga-i-settings` | Instellingen | Bestand en acties |
| `ga-i-info` | Informatie | Interface |
| `ga-i-help` | Help | Interface |
| `ga-i-close` | Sluiten | Interface |
| `ga-i-plus` | Toevoegen | Interface |
| `ga-i-minus` | Min | Interface |
| `ga-i-check` | Gereed | Interface |
| `ga-i-chevron-down` | Uitklappen | Interface |
| `ga-i-chevron-right` | Verder | Interface |
| `ga-i-arrow-right` | Pijl | Interface |
| `ga-i-menu` | Menu | Interface |
| `ga-i-code` | Code | Interface |
| `ga-i-mail` | E-mail | Interface |
| `ga-i-phone` | Telefoon | Interface |

```html
<!-- Eén keer per pagina, direct na <body>: de sprite (tab Sprite) -->
<svg class="ga-icon" aria-hidden="true"><use href="#ga-i-zoom-in"/></svg>

<!-- Icoonknop met tooltip -->
<button class="ga-tool ga-tool--icon" type="button" aria-label="Inzoomen" data-tip="Inzoomen (+)">
  <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-zoom-in"/></svg>
</button>
```

## Ruimte en uitlijning

**Status: Richtlijn** — Vrij in te vullen binnen de huisstijl.

De maten van de website, vertaald naar bouwstenen voor tools. Er is geen vaste indeling.

- Ruimte gaat in stappen van 4, 8, 12, 16, 24, 32 en 48px. Tussen elementen 8–16px, tussen secties 24–32px.
- Gebruik `.ga-row` voor een rij knoppen of velden en `.ga-stack` voor elementen onder elkaar.
- Een tekstpagina staat in `.ga-container`: maximaal 1236px breed, met een marge van 20px (mobiel), 40px (vanaf 600px) of 48px (vanaf 1400px).
- Breekpunten: 600px (tablet), 960px (meerdere kolommen), 1140px (volledige kopbalk) en 1400px (breed).
- Kaarten en tegels verdelen zich automatisch met `.ga-grid`.

```html
<div class="ga-row">
  <button class="ga-btn ga-btn--sm" type="button">Opslaan</button>
  <button class="ga-btn ga-btn--sm ga-btn--outline" type="button">Annuleren</button>
</div>

<div class="ga-grid">
  <div class="ga-panel">Tegel</div>
  <div class="ga-panel">Tegel</div>
  <div class="ga-panel">Tegel</div>
</div>
```

# Componenten

## Kopbalk

**Status: Vast** — Gebruik zoals beschreven.

Een witte balk met een lichte schaduw, zoals op goudappel.nl. Van links naar rechts: logo, toolnaam met versie, het menu met een rode onderstreping, en rechts Contact en de taalwissel NL | EN. Dit is het herkenningspunt van elke tool.

- Hoogte 40px, vanaf 1140px 44px. De balk is wit, heeft een schaduw van `0 0 15px 5px rgba(0,0,0,.04)` en blijft bovenaan staan.
- Links staat het logo: 100px breed, vanaf 1140px 120px.
- Daarna volgt de toolnaam, met aan beide kanten een korte lichtgrijze lijn. De naam (16px, gewicht 700) staat op één regel met het versienummer erachter (12px, grijs, klikbaar voor de versie-informatie). Dit blok leest als titel en niet als tabblad.
- Daarna volgt het menu met de hoofdweergaven: één regel, 17px, gewicht 600. Het actieve item is rood donker met een lijn van 2px aan de onderkant van de balk.
- Rechts staan, net als op goudappel.nl, **Contact** en de taalwissel **NL | EN** (17px, gewicht 600). Contact opent een menu met naam, rol, e-mail en telefoon van de contactpersoon (zie Versie-info en contact). In NL | EN is de actieve taal rood donker (zie Tweetaligheid).
- Daarachter mogen, na een korte lichtgrijze lijn, kleine icoonknoppen staan zoals help. Zet hier geen gereedschap of primaire knop.
- Op een smal scherm (onder 600px) vervalt het blok met toolnaam en versie. Het menu scrolt dan horizontaal; Contact en NL | EN blijven staan.
- Het logo zit in de sprite (`#ga-logo`). Je gebruikt het met `<svg class="ga-logo"><use href="#ga-logo"/></svg>`. Een los bestand staat onder Code › Logo.

```html
<header class="ga-header">
  <a class="ga-header__logo" href="./"><svg class="ga-logo" viewBox="0 0 182 32" role="img" aria-label="Goudappel"><use href="#ga-logo"/></svg></a>
  <div class="ga-header__tool">
    <span class="ga-header__title">Naam van de tool</span>
    <button class="ga-header__version" type="button" title="Versie-informatie">v1.0.0</button>
  </div>
  <nav class="ga-nav" aria-label="Hoofdmenu">
    <a href="#kaart" aria-current="page">Kaart</a>
    <a href="#tabel">Tabel</a>
    <a href="#rapport">Rapport</a>
  </nav>
  <div class="ga-header__meta">
    <div class="ga-dropdown ga-contact">
      <button class="ga-header__link" type="button" aria-expanded="false" aria-haspopup="true" data-ga-dropdown>Contact <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-down"/></svg></button>
      <div class="ga-dropdown__menu" role="menu" hidden>
        <div class="ga-contact__person"><span class="ga-contact__name">Voornaam Achternaam</span><span class="ga-contact__role">Ontwikkelaar · Team</span></div>
        <a class="ga-dropdown__item" role="menuitem" href="mailto:naam@goudappel.nl"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-mail"/></svg>naam@goudappel.nl</a>
        <a class="ga-dropdown__item" role="menuitem" href="tel:+31000000000"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-phone"/></svg>+31 (0)0 000 0000</a>
      </div>
    </div>
    <div class="ga-lang" role="group" aria-label="Taal / Language">
      <button type="button" data-lang="nl" aria-pressed="true" title="Nederlands">NL</button>
      <span class="ga-lang__sep" aria-hidden="true">|</span>
      <button type="button" data-lang="en" aria-pressed="false" title="English">EN</button>
    </div>
  </div>
  <div class="ga-header__actions">
    <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Help" data-tip="Help"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-help"/></svg></button>
  </div>
</header>
```

## Knoppen

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Er zijn twee soorten knoppen. Een **actieknop** (rode pil, zoals op de website) gebruik je voor de hoofdactie van een paneel. Een **kleine knop** (`.ga-tool`) is rustig en compact, voor alles daaromheen.

- Gebruik één rode actieknop per paneel, bijvoorbeeld "Berekenen" of "Opslaan". Een tweede actie wordt omlijnd, een derde een tekstlink met pijl.
- In panelen en dialogen gebruik je `.ga-btn--sm`. Het normale formaat alleen op ruime pagina's.
- Kleine knoppen (32px, 14px tekst) zijn voor secundaire acties zoals Exporteren of Instellingen, met of zonder icoon.
- Bij hover wordt een actieknop rood donker. Een uitgeschakelde knop heeft 40% dekking.
- Knopteksten zijn werkwoorden: "Exporteren", niet "Export".

```html
<div class="ga-row">
  <button class="ga-btn" type="button">Berekenen</button>
  <button class="ga-btn ga-btn--outline" type="button">Annuleren</button>
  <a class="ga-btn ga-btn--link" href="#">Meer informatie <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-arrow-right"/></svg></a>
</div>
<div class="ga-row">
  <button class="ga-btn ga-btn--sm" type="button">Opslaan</button>
  <button class="ga-btn ga-btn--sm ga-btn--outline" type="button">Sluiten</button>
  <button class="ga-btn ga-btn--sm" type="button" disabled>Uitgeschakeld</button>
</div>
<div class="ga-row">
  <button class="ga-tool" type="button"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-download"/></svg> Exporteren</button>
  <button class="ga-tool" type="button"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-upload"/></svg> Importeren</button>
  <button class="ga-tool ga-tool--icon" type="button" aria-label="Instellingen" data-tip="Instellingen"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-settings"/></svg></button>
</div>
```

## Gereedschapspalet

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Gereedschap groepeer je per thema, onder elkaar, met alleen iconen en een tooltip met sneltoets. Standaard staat alles in **één kolom**, zonder titels: de thema's zijn gescheiden door lijnen. Alleen bij veel gereedschap gebruik je **twee kolommen**, en dan staat de naam van het thema boven elke groep.

- Groepeer per thema, in een vaste volgorde: Selectie, Navigatie, Tekenen, Bewerken, Weergave. Laat groepen weg die de tool niet nodig heeft.
- Er zijn drie soorten gereedschap. Een **modus** (`data-mode`) is één tegelijk actief, bijvoorbeeld Selecteren of Lijn tekenen. Een **schakelaar** (`aria-pressed`) zet iets aan of uit, bijvoorbeeld Labels. Een **actie** (geen status) voert direct iets uit, bijvoorbeeld Inzoomen.
- Het actieve gereedschap is lichtroze met een rode rand. De andere knoppen zijn randloos en worden lichtgrijs bij hover. Zo blijft een palet met 20 knoppen rustig.
- Knoppen zijn 36×36px met een icoon van 20px. **Eén kolom:** de thema's zijn gescheiden door een lijn, zonder titel, en de tooltip staat rechts. **Twee kolommen** (`.ga-palette--2kol`) alleen bij meer dan circa 12 knoppen: dan met een themanaam boven elke groep en de tooltip eronder. Meer dan twee kolommen nooit.
- Geef in de HTML altijd de themanaam mee (`.ga-palette__title`). Bij één kolom is die alleen hoorbaar voor schermlezers.
- Op een kaart of canvas zweeft het palet linksboven, met `.ga-palette--zwevend`.
- De tooltip noemt de functie en de sneltoets, bijvoorbeeld "Lijn tekenen (L)". Een niet-beschikbare actie wordt uitgeschakeld, niet verborgen.

```html
<!-- Eén kolom (standaard): geen titels, thema's gescheiden door lijnen.
     Op een kaart of canvas: voeg ga-palette--zwevend toe -->
<div class="ga-palette" role="toolbar" aria-label="Gereedschap" aria-orientation="vertical">
  <div class="ga-palette__group" role="group" aria-label="Selectie">
    <span class="ga-palette__title">Selectie</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="true" aria-label="Selecteren" data-tip="Selecteren (V)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-select"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Verschuiven" data-tip="Verschuiven (H)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-pan"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Navigatie">
    <span class="ga-palette__title">Navigatie</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Inzoomen" data-tip="Inzoomen (+)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-zoom-in"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Uitzoomen" data-tip="Uitzoomen (−)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-zoom-out"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Passend in beeld" data-tip="Passend in beeld (0)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-extent"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Tekenen">
    <span class="ga-palette__title">Tekenen</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Punt plaatsen" data-tip="Punt plaatsen (P)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-point"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Lijn tekenen" data-tip="Lijn tekenen (L)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-line"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Vlak tekenen" data-tip="Vlak tekenen (G)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-polygon"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Weergave">
    <span class="ga-palette__title">Weergave</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-pressed="false" aria-label="Lagen" data-tip="Lagen"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-layers"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-pressed="true" aria-label="Labels" data-tip="Labels"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-labels"/></svg></button>
    </div>
  </div>
</div>

<!-- Twee kolommen: alleen bij veel gereedschap, met themanaam -->
<div class="ga-palette ga-palette--2kol" role="toolbar" aria-label="Gereedschap" aria-orientation="vertical">
  <div class="ga-palette__group" role="group" aria-label="Selectie">
    <span class="ga-palette__title">Selectie</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="true" aria-label="Selecteren" data-tip="Selecteren (V)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-select"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Rechthoek selecteren" data-tip="Rechthoek selecteren (R)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-select-box"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Verschuiven" data-tip="Verschuiven (H)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-pan"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Navigatie">
    <span class="ga-palette__title">Navigatie</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Inzoomen" data-tip="Inzoomen (+)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-zoom-in"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Uitzoomen" data-tip="Uitzoomen (−)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-zoom-out"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Passend in beeld" data-tip="Passend in beeld (0)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-extent"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Volledig scherm" data-tip="Volledig scherm (F)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-fullscreen"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Tekenen">
    <span class="ga-palette__title">Tekenen</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Punt plaatsen" data-tip="Punt plaatsen (P)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-point"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Lijn tekenen" data-tip="Lijn tekenen (L)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-line"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Vlak tekenen" data-tip="Vlak tekenen (G)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-polygon"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Afstand meten" data-tip="Afstand meten (M)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-measure"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Bewerken">
    <span class="ga-palette__title">Bewerken</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Vormpunten bewerken" data-tip="Vormpunten bewerken (E)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-edit"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Verwijderen" data-tip="Verwijderen (Del)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-delete"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Ongedaan maken" data-tip="Ongedaan maken (Ctrl+Z)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-undo"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" disabled aria-label="Opnieuw" data-tip="Opnieuw (Ctrl+Y)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-redo"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Weergave">
    <span class="ga-palette__title">Weergave</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-pressed="false" aria-label="Lagen" data-tip="Lagen"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-layers"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-pressed="true" aria-label="Labels" data-tip="Labels"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-labels"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-pressed="false" aria-label="Raster" data-tip="Raster"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-grid"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-pressed="true" aria-label="Legenda" data-tip="Legenda"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-legend"/></svg></button>
    </div>
  </div>
</div>
```

```js
// Gereedschapspalet: modi zijn exclusief, schakelaars wisselen aan/uit
document.addEventListener('click', function (e) {
  var t = e.target.closest('.ga-palette .ga-tool');
  if (!t || t.disabled) return;
  if (t.hasAttribute('data-mode')) {
    t.closest('.ga-palette').querySelectorAll('[data-mode]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b === t));
    });
  } else if (t.hasAttribute('aria-pressed')) {
    t.setAttribute('aria-pressed', String(t.getAttribute('aria-pressed') !== 'true'));
  }
});
```

## Invoervelden en dropdowns

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Invoervelden en keuzelijsten zoals in de projectfilters op goudappel.nl: een duidelijke grijze rand die roze wordt bij focus.

- Het label staat boven het veld, met gewicht 600. Een placeholder is een voorbeeld en vervangt het label niet.
- Velden zijn 44px hoog, met een rand van 2px en een afronding van 4px. In het zijpaneel en in werkbalken gebruik je `--sm`: 32px hoog, 14px tekst.
- Een filter boven een overzicht mag de pilvorm van de website hebben (`.ga-select--filter`).
- De uitklaplijst van een keuzelijst is een wit paneel met een lichtgrijze rand. Bij hover is een optie lichtroze en de gekozen optie is vet en rood donker. Dit werkt in Chrome en Edge (`appearance: base-select`); andere browsers tonen de standaardlijst van het systeem.
- Selectievakjes en keuzerondjes zijn browserelementen in Goudappel rood (`accent-color`).
- Een foutmelding staat direct onder het veld, in rood, en de rand wordt ook rood.

```html
<div class="ga-field">
  <label class="ga-label" for="v-naam">Projectnaam</label>
  <input class="ga-input" id="v-naam" type="text" placeholder="Bijv. Bereikbaarheid Zwolle">
</div>
<div class="ga-field">
  <label class="ga-label" for="v-exp">Expertise</label>
  <select class="ga-select" id="v-exp">
    <option>Alle expertises</option>
    <option>Strategie en ruimte</option>
  </select>
</div>
<div class="ga-field">
  <label class="ga-label" for="v-jaar">Jaar</label>
  <input class="ga-input is-error" id="v-jaar" type="number" value="1850">
  <p class="ga-field__error">Kies een jaar tussen 2000 en 2050.</p>
</div>
<div class="ga-field">
  <label class="ga-check"><input type="checkbox" checked> Toon labels</label>
  <label class="ga-check"><input type="radio" name="v-r" checked> Auto</label>
  <label class="ga-check"><input type="radio" name="v-r"> Fiets</label>
</div>
<div class="ga-row">
  <select class="ga-select ga-select--filter" aria-label="Thema"><option>Alle thema's</option></select>
  <input class="ga-input ga-input--sm" type="search" placeholder="Zoeken…" aria-label="Zoeken" style="width:180px">
  <select class="ga-select ga-select--sm" aria-label="Jaar" style="width:auto"><option>2030</option></select>
</div>
```

## Dropdownmenu

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Een uitklapmenu voor acties, zoals "Exporteren als…". Voor een keuze in een formulier gebruik je een gewone keuzelijst.

- De knop die het menu opent heeft een chevron en `aria-expanded`.
- Het menu is een wit paneel met een lichtgrijze rand en een zachte schaduw. Items zijn 14px, met een icoon als dat helpt.
- Het menu sluit na een keuze, bij een klik ernaast en met Escape.
- Hooguit 8 items. Zijn het er meer, groepeer dan met een scheidingslijn of gebruik een zoekveld.

```html
<div class="ga-dropdown">
  <button class="ga-tool" type="button" aria-expanded="false" aria-haspopup="true" data-ga-dropdown>
    <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-download"/></svg> Exporteren <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-down"/></svg>
  </button>
  <div class="ga-dropdown__menu" role="menu" hidden>
    <button class="ga-dropdown__item" role="menuitem" type="button">Als PNG</button>
    <button class="ga-dropdown__item" role="menuitem" type="button">Als PDF</button>
    <hr class="ga-dropdown__sep">
    <button class="ga-dropdown__item" role="menuitem" type="button">Gegevens als Excel</button>
  </div>
</div>
```

```js
// Dropdownmenu's: openen/sluiten, klik ernaast en Escape sluiten
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
```

## Inklapbare secties

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Een zijpaneel met veel instellingen deel je op in secties die je kunt in- en uitklappen. Elke sectie staat in een eigen kader, zodat je in één oogopslag ziet waar een sectie begint en eindigt.

- Gebruik het standaard `<details>`-element. Dat werkt zonder JavaScript en met het toetsenbord.
- Elke sectie heeft één onderwerp: Gebied, Lagen, Weergave. Laat de belangrijkste sectie standaard open.
- Een sectie is een wit kader met een lichtgrijze rand en 8px ruimte ertussen. De titelbalk is vlakgrijs; bij een open sectie staat links een rode streep en een lijn onder de titel.
- Een titel is 15px, gewicht 600, met een chevron rechts. Bij hover wordt de titel rood donker.
- Stapel geen secties in secties. Is het te veel, of raakt een belangrijke sectie onderaan uit beeld, geef die dan een eigen tab in de balk van het zijpaneel (zie Toolindeling) of een tabblad in de kopbalk.

```html
<details class="ga-collapse" open>
  <summary>Gebied</summary>
  <div class="ga-collapse__body">
    <label class="ga-label" for="c-gem">Gemeente</label>
    <select class="ga-select ga-select--sm" id="c-gem"><option>Deventer</option></select>
  </div>
</details>
<details class="ga-collapse" open>
  <summary>Lagen</summary>
  <div class="ga-collapse__body ga-stack">
    <label class="ga-check"><input type="checkbox" checked> Wegen</label>
    <label class="ga-check"><input type="checkbox" checked> Fietspaden</label>
    <label class="ga-check"><input type="checkbox"> OV-haltes</label>
  </div>
</details>
<details class="ga-collapse">
  <summary>Weergave</summary>
  <div class="ga-collapse__body">Instellingen voor kleuren en labels.</div>
</details>
```

## Tabbladen

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Tabbladen binnen een paneel, in dezelfde vormtaal als het menu: zwart, en rood donker met een lijn eronder als het tabblad actief is.

- Gebruik tabbladen voor gelijkwaardige weergaven van dezelfde inhoud, bijvoorbeeld Resultaat, Invoer en Toelichting.
- Gebruik er twee tot zes. Hoofdweergaven van de hele tool horen in het menu van de kopbalk.

```html
<div class="ga-tabs" role="tablist">
  <button class="ga-tab" role="tab" aria-selected="true" type="button">Resultaat</button>
  <button class="ga-tab" role="tab" aria-selected="false" type="button">Invoer</button>
  <button class="ga-tab" role="tab" aria-selected="false" type="button">Toelichting</button>
</div>
```

```js
// Tabbladen: aria-selected wisselen
document.addEventListener('click', function (e) {
  var tab = e.target.closest('.ga-tab');
  if (!tab) return;
  tab.parentElement.querySelectorAll('.ga-tab').forEach(function (t) {
    t.setAttribute('aria-selected', String(t === tab));
  });
});
```

## Labels en dubbele lijn

**Status: Richtlijn** — Vrij in te vullen binnen de huisstijl.

Labels in hoofdletters, zoals "PROJECT" op de projectkaarten. De dubbele lijn is het kenmerk van Goudappel en staat op de website boven de paginatitel.

- Een label is in hoofdletters, 12px, gewicht 800, met een letterafstand van 1px en zonder afronding.
- Gebruik gevuld rood voor het belangrijkste kenmerk. Lichtroze of grijs voor gewone statussen, zodat een lijst rustig blijft.
- De dubbele lijn bestaat uit twee rode lijnen van 3px. Gebruik hem één keer per pagina, boven de titel, en alleen op tekstpagina's of een startscherm, niet in een werktool.

```html
<div class="ga-row">
  <span class="ga-tag">Project</span>
  <span class="ga-tag ga-tag--licht">Concept</span>
  <span class="ga-tag ga-tag--neutraal">Archief</span>
  <span class="ga-meta">12 oktober 2026</span>
</div>

<span class="ga-lines" aria-hidden="true"></span>
<h1 class="ga-h1">Paginatitel</h1>
```

## Panelen en kaarten

**Status: Richtlijn** — Vrij in te vullen binnen de huisstijl.

Panelen groeperen inhoud. Een kaart is een klikbaar paneel, bijvoorbeeld in een overzicht van projecten of scenario's.

- Een paneel is wit, met een rand van 1px lichtgrijs, 4px afronding en 16–20px binnenruimte.
- Gebruik `--zwevend` (schaduw zonder rand) alleen voor iets dat boven een werkvlak ligt.
- Een klikbare kaart schuift bij hover 4px omhoog en de titel wordt rood donker.

```html
<div class="ga-grid">
  <div class="ga-panel">
    <h3 class="ga-h3">Resultaat</h3>
    <p class="ga-small ga-muted">Paneel met lichtgrijze rand.</p>
  </div>
  <a class="ga-panel ga-card" href="#">
    <span class="ga-tag">Scenario</span>
    <h3 class="ga-h3">Variant B — autoluw centrum</h3>
    <span class="ga-meta">Gewijzigd 12 oktober 2026</span>
  </a>
</div>
```

## Tabellen

**Status: Richtlijn** — Vrij in te vullen binnen de huisstijl.

Compacte, rustige tabellen met alleen horizontale lijnen.

- De tekst is 14px. De kopregel heeft gewicht 600 en een lijn van 2px eronder, en blijft staan bij scrollen.
- Getallen staan rechts uitgelijnd (`.ga-num`). Een geselecteerde rij krijgt een lichtroze achtergrond.
- Gebruik geen zebrastrepen, gekleurde kopregels of verticale lijnen.

```html
<table class="ga-table">
  <thead>
    <tr><th>Gemeente</th><th class="ga-num">Inwoners</th><th class="ga-num">Fietsaandeel</th></tr>
  </thead>
  <tbody>
    <tr><td>Deventer</td><td class="ga-num">101.890</td><td class="ga-num">38%</td></tr>
    <tr class="is-selected"><td>Zwolle</td><td class="ga-num">132.411</td><td class="ga-num">41%</td></tr>
    <tr><td>Apeldoorn</td><td class="ga-num">166.093</td><td class="ga-num">33%</td></tr>
  </tbody>
</table>
```

## Dialoogvenster en melding

**Status: Richtlijn** — Vrij in te vullen binnen de huisstijl.

Een dialoogvenster voor een bevestiging, en een korte melding (toast) na een actie.

- Een dialoogvenster is maximaal 520px breed. Het sluitkruis staat rechtsboven, de knoppen rechtsonder met de primaire knop als laatste.
- Escape en een klik op de achtergrond sluiten het venster.
- Een melding staat 2 tot 3 seconden onderaan in het midden, als een zwart vlak. Een foutmelding is rood. Een fout in een veld toon je bij dat veld, niet als melding.

```html
<div class="ga-overlay is-open">
  <div class="ga-modal" role="dialog" aria-modal="true" aria-labelledby="m-titel">
    <button class="ga-modal__close ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Sluiten"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-close"/></svg></button>
    <h2 class="ga-h2" id="m-titel">Scenario verwijderen?</h2>
    <p>Het scenario "Variant B" wordt definitief verwijderd.</p>
    <div class="ga-modal__actions">
      <button class="ga-btn ga-btn--sm ga-btn--outline" type="button">Annuleren</button>
      <button class="ga-btn ga-btn--sm" type="button">Verwijderen</button>
    </div>
  </div>
</div>

<div class="ga-toast is-visible" role="status">Gekopieerd naar klembord</div>
```

# Patronen voor tools

## Toolindeling

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Zo ziet een werktool eruit. De kopbalk staat bovenaan. Links een zijpaneel met instellingen en de primaire actie, in het midden het werkvlak met een zwevend palet en een statusbalk, en rechts eventueel een paneel met informatie. Elk zijpaneel klap je in en uit met een verticale tab aan de rand van het scherm. Leidraad: overzicht en werkruimte gaan vóór. Een paneel is nooit kwijt, want de tab blijft altijd staan, en een uitgeklapt paneel toont de inhoud volledig.

- **Altijd inklapbaar.** Elk zijpaneel dat kan scrollen (instellingen, lagen, informatie, overzicht) hangt aan een smalle balk van 32px die altijd zichtbaar blijft. In de balk staat een verticale tab met de naam van het paneel en een pijltje. Een klik klapt het paneel in of uit.
- **De balk staat aan de buitenrand** van het scherm, uiterst links of uiterst rechts, niet op de grens tussen paneel en werkvlak. Zo staat de tab altijd op dezelfde plek.
- **Standaard open of dicht.** Panelen waar je mee werkt, zoals instellingen, staan standaard uitgeklapt (`aria-expanded="true"`). Panelen met alleen naslag of informatie staan standaard ingeklapt (`aria-expanded="false"` en `hidden` op het paneel), zodat het werkvlak breed blijft.
- **Uitgeklapt toont alles.** Een paneel is 320px breed (`--ga-side-w`) en groeit mee met de inhoud, tot de helft van het scherm. Een paneel scrolt nooit horizontaal. Is één onderdeel breder, zoals een grote tabel, zet het dan in `.ga-side__breed`: dan scrolt alleen dat onderdeel.
- **Het werkvlak schuift mee.** Bij uitklappen wordt het werkvlak smaller; het paneel ligt er niet overheen. Na elke wijziging stuurt de pagina het event `ga-side`. Laat een kaart daarop haar maat opnieuw bepalen, bij Leaflet met `kaart.invalidateSize()`.
- **Meerdere tabs per balk.** Een balk mag meerdere tabs hebben, elk met een eigen paneel, bijvoorbeeld rechts *Informatie* en *Legenda*, of *Stap 1*, *Stap 2* en *Stap 3*. Liever losse tabs dan secties onder elkaar die uit beeld raken. Per balk is één paneel open; de actieve tab is lichtroze met een rode streep aan de rand.
- **De toestand wordt onthouden.** Per balk bewaart de pagina welk paneel open stond (localStorage) en herstelt dat bij een volgende keer. Geef elke balk daarvoor een unieke `data-ga-side`. De huisstijl-JS regelt dit, net als de bediening met het toetsenbord (Tab, Enter, pijltjes) en `aria-expanded` en `aria-controls`. Voeg je panelen later toe met JavaScript, roep dan `gaInitSides()` aan.
- **Smal scherm** (onder 760px): een paneel klapt zo ver uit als past en een open paneel aan de andere kant klapt vanzelf in. De tab blijft bereikbaar om weer in te klappen. Alleen hier mag een paneel als noodoplossing horizontaal scrollen.
- In het instellingenpaneel staan bovenin de titel en één zin uitleg, onderin de primaire actieknop. De knop blijft zichtbaar door `position: sticky`.
- Het werkvlak (kaart, canvas, tabel) vult de rest en is vlakgrijs. Het gereedschap zweeft er linksboven op, in één kolom.
- De statusbalk onderaan toont 13px grijze tekst: schaal, selectie, laatst berekend. Laat hem weg als er niets zinnigs te melden is.
- Een werktool heeft geen voettekst en geen dubbele lijn. De versie staat bij de toolnaam, Contact en NL | EN staan rechts in de kopbalk.

```html
<header class="ga-header">
  <a class="ga-header__logo" href="./"><svg class="ga-logo" viewBox="0 0 182 32" role="img" aria-label="Goudappel"><use href="#ga-logo"/></svg></a>
  <div class="ga-header__tool">
    <span class="ga-header__title">Naam van de tool</span>
    <button class="ga-header__version" type="button" title="Versie-informatie">v1.0.0</button>
  </div>
  <nav class="ga-nav" aria-label="Hoofdmenu">
    <a href="#kaart" aria-current="page">Kaart</a>
    <a href="#tabel">Tabel</a>
    <a href="#rapport">Rapport</a>
  </nav>
  <div class="ga-header__meta">
    <div class="ga-dropdown ga-contact">
      <button class="ga-header__link" type="button" aria-expanded="false" aria-haspopup="true" data-ga-dropdown>Contact <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-down"/></svg></button>
      <div class="ga-dropdown__menu" role="menu" hidden>
        <div class="ga-contact__person"><span class="ga-contact__name">Voornaam Achternaam</span><span class="ga-contact__role">Ontwikkelaar · Team</span></div>
        <a class="ga-dropdown__item" role="menuitem" href="mailto:naam@goudappel.nl"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-mail"/></svg>naam@goudappel.nl</a>
        <a class="ga-dropdown__item" role="menuitem" href="tel:+31000000000"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-phone"/></svg>+31 (0)0 000 0000</a>
      </div>
    </div>
    <div class="ga-lang" role="group" aria-label="Taal / Language">
      <button type="button" data-lang="nl" aria-pressed="true" title="Nederlands">NL</button>
      <span class="ga-lang__sep" aria-hidden="true">|</span>
      <button type="button" data-lang="en" aria-pressed="false" title="English">EN</button>
    </div>
  </div>
  <div class="ga-header__actions">
    <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Help" data-tip="Help"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-help"/></svg></button>
  </div>
</header>
<div class="ga-app">
  <div class="ga-side ga-side--links" data-ga-side="voorbeeld-links">
    <div class="ga-side__bar" role="group" aria-label="Panelen links">
      <button class="ga-side__tab" type="button" aria-expanded="true" aria-controls="t-instellingen"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-right"/></svg><span>Instellingen</span></button>
    </div>
    <aside class="ga-side__panel" id="t-instellingen" aria-label="Instellingen">
      <h1 class="ga-h3">Bereikbaarheid</h1>
      <p class="ga-small ga-muted">Bereken hoeveel inwoners een locatie binnen 15 minuten bereiken.</p>
      <details class="ga-collapse" open>
        <summary>Gebied</summary>
        <div class="ga-collapse__body">
          <label class="ga-label" for="t-gem">Gemeente</label>
          <select class="ga-select ga-select--sm" id="t-gem"><option>Deventer</option></select>
        </div>
      </details>
      <details class="ga-collapse" open>
        <summary>Vervoerwijze</summary>
        <div class="ga-collapse__body ga-stack">
          <label class="ga-check"><input type="radio" name="t-vw" checked> Fiets</label>
          <label class="ga-check"><input type="radio" name="t-vw"> Auto</label>
          <label class="ga-check"><input type="radio" name="t-vw"> Openbaar vervoer</label>
        </div>
      </details>
      <details class="ga-collapse">
        <summary>Weergave</summary>
        <div class="ga-collapse__body">Kleuren en labels.</div>
      </details>
      <div class="ga-app__actions">
        <button class="ga-btn ga-btn--sm" type="button">Berekenen</button>
      </div>
    </aside>
  </div>
  <main class="ga-app__main ga-workspace">
    <div class="ga-palette ga-palette--zwevend" role="toolbar" aria-label="Gereedschap" aria-orientation="vertical">
  <div class="ga-palette__group" role="group" aria-label="Selectie">
    <span class="ga-palette__title">Selectie</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="true" aria-label="Selecteren" data-tip="Selecteren (V)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-select"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Verschuiven" data-tip="Verschuiven (H)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-pan"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Navigatie">
    <span class="ga-palette__title">Navigatie</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Inzoomen" data-tip="Inzoomen (+)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-zoom-in"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Uitzoomen" data-tip="Uitzoomen (−)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-zoom-out"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-label="Passend in beeld" data-tip="Passend in beeld (0)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-extent"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Tekenen">
    <span class="ga-palette__title">Tekenen</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Punt plaatsen" data-tip="Punt plaatsen (P)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-point"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Lijn tekenen" data-tip="Lijn tekenen (L)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-line"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" data-mode aria-pressed="false" aria-label="Vlak tekenen" data-tip="Vlak tekenen (G)"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-polygon"/></svg></button>
    </div>
  </div>
  <div class="ga-palette__group" role="group" aria-label="Weergave">
    <span class="ga-palette__title">Weergave</span>
    <div class="ga-palette__tools">
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-pressed="false" aria-label="Lagen" data-tip="Lagen"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-layers"/></svg></button>
      <button class="ga-tool ga-tool--icon ga-tool--ghost" type="button" aria-pressed="true" aria-label="Labels" data-tip="Labels"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-labels"/></svg></button>
    </div>
  </div>
</div>
    <div class="ga-workspace__canvas">
      <div class="ga-empty">
        <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-map"/></svg>
        <p class="ga-empty__title">Nog geen berekening</p>
        <p>Kies links een gemeente en klik op Berekenen.</p>
      </div>
    </div>
    <div class="ga-statusbar"><span>Schaal 1:25.000</span><span>0 objecten geselecteerd</span></div>
  </main>
  <div class="ga-side ga-side--rechts" data-ga-side="voorbeeld-rechts">
    <div class="ga-side__bar" role="group" aria-label="Panelen rechts">
      <button class="ga-side__tab" type="button" aria-expanded="false" aria-controls="t-informatie"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-right"/></svg><span>Informatie</span></button>
      <button class="ga-side__tab" type="button" aria-expanded="false" aria-controls="t-legenda"><svg class="ga-icon" aria-hidden="true"><use href="#ga-i-chevron-right"/></svg><span>Legenda</span></button>
    </div>
    <aside class="ga-side__panel" id="t-informatie" aria-label="Informatie" hidden>
      <h2 class="ga-h3">Informatie</h2>
      <p class="ga-small ga-muted">Inwoners binnen 15 minuten, per gemeente.</p>
      <table class="ga-table">
        <thead>
          <tr><th>Gemeente</th><th class="ga-num">Fiets</th><th class="ga-num">Auto</th><th class="ga-num">Openbaar vervoer</th></tr>
        </thead>
        <tbody>
          <tr><td>Deventer</td><td class="ga-num">64.210</td><td class="ga-num">98.540</td><td class="ga-num">31.870</td></tr>
          <tr><td>Zwolle</td><td class="ga-num">88.930</td><td class="ga-num">127.300</td><td class="ga-num">45.120</td></tr>
          <tr><td>Apeldoorn</td><td class="ga-num">71.640</td><td class="ga-num">152.880</td><td class="ga-num">29.450</td></tr>
        </tbody>
      </table>
    </aside>
    <aside class="ga-side__panel" id="t-legenda" aria-label="Legenda" hidden>
      <h2 class="ga-h3">Legenda</h2>
      <ul class="ga-list ga-small">
        <li>Binnen 5 minuten</li>
        <li>5 tot 10 minuten</li>
        <li>10 tot 15 minuten</li>
      </ul>
    </aside>
  </div>
</div>
```

```js
// Inklapbare zijpanelen: verticale tabs in een balk aan de buitenrand.
// Per balk is één paneel open; de toestand wordt per pagina bewaard in localStorage.
var GA_SIDE_SMAL = 760;
function gaSideKey(side) {
  return 'ga-side:' + location.pathname + ':' + (side.getAttribute('data-ga-side') || '');
}
function gaSideTabs(side) {
  return Array.prototype.slice.call(side.querySelectorAll('.ga-side__tab'));
}
// tab = de tab van het paneel dat open moet, of null om in te klappen
function gaSideOpen(side, tab, save) {
  gaSideTabs(side).forEach(function (t) {
    var on = t === tab;
    t.setAttribute('aria-expanded', String(on));
    var panel = document.getElementById(t.getAttribute('aria-controls'));
    if (panel) panel.hidden = !on;
  });
  side.classList.toggle('is-open', !!tab);
  // Smal scherm: een open paneel aan de andere kant klapt in (niet bewaren)
  if (tab && window.innerWidth < GA_SIDE_SMAL && side.parentElement) {
    side.parentElement.querySelectorAll(':scope > .ga-side.is-open').forEach(function (s) {
      if (s !== side) gaSideOpen(s, null, false);
    });
  }
  if (save) {
    try { localStorage.setItem(gaSideKey(side), tab ? tab.getAttribute('aria-controls') : ''); } catch (e) {}
  }
  side.dispatchEvent(new CustomEvent('ga-side', { bubbles: true, detail: { open: tab ? tab.getAttribute('aria-controls') : null } }));
}
// Begintoestand: bewaarde keuze, anders de tab met aria-expanded="true" in de HTML
function gaInitSides(root) {
  (root || document).querySelectorAll('.ga-side').forEach(function (side) {
    var saved = null, tab = null;
    try { saved = localStorage.getItem(gaSideKey(side)); } catch (e) {}
    gaSideTabs(side).forEach(function (t) {
      var match = saved != null ? t.getAttribute('aria-controls') === saved : t.getAttribute('aria-expanded') === 'true';
      if (match && !tab) tab = t;
    });
    gaSideOpen(side, tab, false);
  });
}
document.addEventListener('click', function (e) {
  var tab = e.target.closest('.ga-side__tab');
  if (!tab) return;
  gaSideOpen(tab.closest('.ga-side'), tab.getAttribute('aria-expanded') === 'true' ? null : tab, true);
});
// Pijltjes omhoog/omlaag, Home en End verplaatsen de focus tussen de tabs van een balk
document.addEventListener('keydown', function (e) {
  var tab = e.target.closest && e.target.closest('.ga-side__tab');
  if (!tab || ['ArrowUp', 'ArrowDown', 'Home', 'End'].indexOf(e.key) < 0) return;
  var tabs = gaSideTabs(tab.closest('.ga-side__bar')), i = tabs.indexOf(tab);
  i = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (i + (e.key === 'ArrowDown' ? 1 : -1) + tabs.length) % tabs.length;
  tabs[i].focus();
  e.preventDefault();
});
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { gaInitSides(); });
else gaInitSides();
```

```css
.ga-app { display: flex; height: calc(100vh - var(--ga-header-h)); }

/* Inklapbare zijpanelen: balk met verticale tabs aan de buitenrand, paneel ernaast */
.ga-side { display: flex; flex: 0 0 auto; min-height: 0; background: #fff; }
.ga-side--rechts { flex-direction: row-reverse; }
.ga-side__bar {
  display: flex; flex-direction: column; gap: 2px;
  flex: 0 0 32px; width: 32px;
  padding: 8px 0;
  border-right: 1px solid var(--ga-lijn);
  overflow-y: auto;
}
.ga-side--rechts .ga-side__bar { border-right: 0; border-left: 1px solid var(--ga-lijn); }
.ga-side__tab {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  width: 100%; padding: 12px 0;
  border: 0; background: none;
  color: var(--ga-tekst);
  font: 600 14px/1 var(--ga-font);
  cursor: pointer;
  transition: color var(--ga-snel), background var(--ga-snel);
}
.ga-side__tab > span { writing-mode: vertical-rl; white-space: nowrap; }
.ga-side__tab .ga-icon { flex: 0 0 auto; width: 16px; height: 16px; transition: transform var(--ga-snel); }
.ga-side__tab:hover { color: var(--ga-rood-donker); background: var(--ga-vlak); }
.ga-side__tab[aria-expanded="true"] { color: var(--ga-rood-donker); background: var(--ga-rood-licht); box-shadow: inset 3px 0 0 var(--ga-rood); }
.ga-side--rechts .ga-side__tab[aria-expanded="true"] { box-shadow: inset -3px 0 0 var(--ga-rood); }
.ga-side__tab:focus-visible { outline-offset: -2px; }
/* Het pijltje wijst de kant op waarheen het paneel gaat bij een klik */
.ga-side--links .ga-side__tab[aria-expanded="true"] .ga-icon,
.ga-side--rechts .ga-side__tab[aria-expanded="false"] .ga-icon { transform: rotate(180deg); }

.ga-side__panel {
  display: flex; flex-direction: column;
  flex: 0 0 auto;
  width: var(--ga-side-w, 320px);
  min-width: min-content;   /* groeit mee met de inhoud: geen horizontale scrollbalk */
  max-width: 50vw;
  padding: 16px 20px 0;
  border-right: 1px solid var(--ga-lijn);
  overflow-y: auto;
}
.ga-side--rechts .ga-side__panel { border-right: 0; border-left: 1px solid var(--ga-lijn); }
.ga-side__panel[hidden] { display: none; }
.ga-side__panel > :last-child:not(.ga-app__actions) { margin-bottom: 16px; }
/* Inhoud houdt haar hoogte: is het paneel te hoog, dan scrolt het paneel
   in plaats van dat secties (overflow: hidden) worden platgedrukt */
.ga-side__panel > *, .ga-app__sidebar > * { flex-shrink: 0; }
/* Een onderdeel breder dan een half scherm (grote tabel) scrolt zelf */
.ga-side__breed { max-width: calc(50vw - 72px); overflow-x: auto; }

/* Vast zijpaneel (oude indeling, zonder tabbalk) */
.ga-app__sidebar {
  display: flex; flex-direction: column;
  flex: 0 0 320px;
  padding: 16px 20px 0;
  border-right: 1px solid var(--ga-lijn);
  overflow-y: auto;
}
.ga-app__actions {
  position: sticky; bottom: 0;
  margin-top: auto;
  padding: 12px 0 16px;
  background: #fff;
}
.ga-app__main { flex: 1 1 auto; min-width: 0; }

.ga-workspace { position: relative; display: flex; flex-direction: column; background: var(--ga-vlak); }
.ga-workspace__canvas { flex: 1 1 auto; min-height: 0; position: relative; display: flex; flex-direction: column; }
.ga-workspace__canvas > .ga-empty { flex: 1 1 auto; }
.ga-workspace > .ga-palette { position: absolute; top: 12px; left: 12px; z-index: 10; }

.ga-statusbar {
  display: flex; flex-wrap: wrap; gap: 4px 20px;
  padding: 6px 12px;
  background: #fff;
  border-top: 1px solid var(--ga-lijn);
  font-size: 13px; color: var(--ga-tekst-2);
}

@media (max-width: 759px) {
  /* Inklapbare panelen: zo breed als past, de tab blijft bereikbaar; scrollen alleen als noodoplossing */
  .ga-side__panel { min-width: 0; max-width: calc(100vw - 64px); overflow-x: auto; }
  .ga-side__breed { max-width: none; }
  /* Vast zijpaneel: boven het werkvlak */
  .ga-app:has(> .ga-app__sidebar) { flex-direction: column; height: auto; }
  .ga-app__sidebar { flex-basis: auto; border-right: 0; border-bottom: 1px solid var(--ga-lijn); }
  .ga-app:has(> .ga-app__sidebar) .ga-workspace { min-height: 70vh; }
}
```

## Achtergrondkaarten

**Status: Standaard** — Gebruik dit, tenzij er een goede reden is om af te wijken.

Een tool met een kaart gebruikt standaard de achtergrondkaarten van PDOK: gratis en zonder API-sleutel. **BRT Grijs** is de standaard, omdat eigen data daarop het best opvalt. Daarnaast is er de actuele **luchtfoto** van PDOK, met of zonder straat- en plaatsnamen erover.

- Bied deze achtergronden aan, in deze volgorde: **BRT Grijs** (standaard), **Luchtfoto + straatnamen** en **Luchtfoto**. Andere BRT-varianten (standaard, pastel) voeg je alleen toe als het werk erom vraagt.
- Straat- en plaatsnamen op de luchtfoto komen uit de BRT-laag `labels`: een doorzichtige laag die je over de luchtfoto legt. Op BRT Grijs staan de namen al in de kaart.
- Vermeld altijd de bron, rechtsonder in de kaart: `© Kadaster · PDOK` bij BRT en `© Beeldmateriaal Nederland · PDOK` bij de luchtfoto, en `© Beeldmateriaal Nederland, © Kadaster · PDOK` met straatnamen. De tekst wisselt mee met de achtergrond. Dit is verplicht onder de licentie (CC BY 4.0).
- Een export (PNG, PDF) bevat dezelfde bronvermelding, bijvoorbeeld in de legenda of rechtsonder in de afbeelding.
- Gebruik Leaflet 1.9.4 met tegels in EPSG:3857, tot zoomniveau 19 (`maxNativeZoom: 19`).
- De keuze van de achtergrond is een `.ga-select--sm` in het zijpaneel (sectie Weergave) en wordt onthouden in localStorage. De namen van de achtergronden zijn tweetalig.

```html
<!-- In <head>: Leaflet -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">

<!-- Zijpaneel, sectie Weergave: keuze van de achtergrond (gevuld door kaart.js) -->
<label class="ga-label" for="achtergrond" data-i18n="kaart.achtergrond">Achtergrond</label>
<select class="ga-select ga-select--sm" id="achtergrond"></select>

<!-- Werkvlak: de kaart -->
<div class="ga-map" id="kaart"></div>

<!-- Onderaan, vóór kaart.js -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="scripts/kaart.js"></script>
```

`kaart.js`:

```js
// Achtergrondkaarten van PDOK (geen API-sleutel nodig), met bronvermelding
var PDOK_BRT = 'https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0';
var PDOK_LUCHTFOTO = 'https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg';
var PDOK_LABELS = PDOK_BRT + '/labels/EPSG:3857/{z}/{x}/{y}.png';
var KADASTER = '© <a href="https://www.kadaster.nl" target="_blank" rel="noopener">Kadaster</a>';
var BEELDMATERIAAL = '© <a href="https://www.beeldmateriaal.nl" target="_blank" rel="noopener">Beeldmateriaal Nederland</a>';
var PDOK = '<a href="https://www.pdok.nl" target="_blank" rel="noopener">PDOK</a>';

// Eerste = standaard. bron = verplichte bronvermelding (CC BY 4.0), rechtsonder in de kaart.
var GA_BASEMAPS = {
  grijs: {
    name: { nl: 'BRT Grijs', en: 'BRT Grey' },
    layers: [PDOK_BRT + '/grijs/EPSG:3857/{z}/{x}/{y}.png'],
    bron: KADASTER + ' · ' + PDOK
  },
  luchtfoto_labels: {
    name: { nl: 'Luchtfoto + straatnamen', en: 'Aerial photo + street names' },
    layers: [PDOK_LUCHTFOTO, PDOK_LABELS],
    bron: BEELDMATERIAAL + ', ' + KADASTER + ' · ' + PDOK
  },
  luchtfoto: {
    name: { nl: 'Luchtfoto', en: 'Aerial photo' },
    layers: [PDOK_LUCHTFOTO],
    bron: BEELDMATERIAAL + ' · ' + PDOK
  }
};
var GA_BASEMAP_KEY = 'ga-basemap';

var kaart = L.map('kaart', { zoomControl: false }).setView([52.2, 5.3], 8);
kaart.attributionControl.setPrefix(false);
var achtergrondLagen = [];

function zetAchtergrond(key) {
  var def = GA_BASEMAPS[key] || GA_BASEMAPS[Object.keys(GA_BASEMAPS)[0]];
  achtergrondLagen.forEach(function (l) { kaart.removeLayer(l); });
  achtergrondLagen = def.layers.map(function (url, i) {
    return L.tileLayer(url, { maxZoom: 19, maxNativeZoom: 19, attribution: i === 0 ? def.bron : '' }).addTo(kaart);
  });
  try { localStorage.setItem(GA_BASEMAP_KEY, key); } catch (e) {}
}

var keuze = Object.keys(GA_BASEMAPS)[0];
try { keuze = localStorage.getItem(GA_BASEMAP_KEY) || keuze; } catch (e) {}
if (!GA_BASEMAPS[keuze]) keuze = Object.keys(GA_BASEMAPS)[0];
zetAchtergrond(keuze);

// Keuzelijst vullen, opnieuw bij een taalwissel
var achtergrondSelect = document.getElementById('achtergrond');
function vulAchtergronden() {
  achtergrondSelect.innerHTML = '';
  Object.keys(GA_BASEMAPS).forEach(function (k) {
    achtergrondSelect.add(new Option(gaL(GA_BASEMAPS[k].name), k));
  });
  achtergrondSelect.value = keuze;
}
achtergrondSelect.addEventListener('change', function () { keuze = achtergrondSelect.value; zetAchtergrond(keuze); });
document.addEventListener('ga-lang', vulAchtergronden);
vulAchtergronden();
```

## Lege staat en laden

**Status: Richtlijn** — Vrij in te vullen binnen de huisstijl.

Laat altijd zien wat er aan de hand is: of er nog niets is (en wat de gebruiker moet doen), of dat er gerekend wordt.

- Een lege staat bestaat uit een grijs icoon, een korte titel en één zin met de volgende stap. Eventueel met een knop.
- Laden: een kleine rode spinner met een tekst die zegt wat er gebeurt ("Bezig met berekenen…"). Zet dit op de plek waar het resultaat komt.
- Duurt het langer dan een paar seconden? Toon dan de voortgang of een tussenresultaat.

```html
<div class="ga-empty">
  <svg class="ga-icon" aria-hidden="true"><use href="#ga-i-table"/></svg>
  <p class="ga-empty__title">Geen resultaten</p>
  <p>Pas de filters aan of wis het zoekveld.</p>
  <button class="ga-tool" type="button">Filters wissen</button>
</div>

<div class="ga-loading"><span class="ga-spinner" aria-hidden="true"></span> Bezig met berekenen…</div>
```

# Bestanden

## Sprite (logo en iconen)

```html
<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">
  <symbol id="ga-logo" viewBox="0 0 182 32"><defs><polygon id="ga-logo-p1" points="0.000376470588 0.456156863 19.1194353 0.456156863 19.1194353 26.0990118 0.000376470588 26.0990118"></polygon><polygon id="ga-logo-p3" points="0.316047059 0.25292549 8.70588235 0.25292549 8.70588235 25.4714353 0.316047059 25.4714353"></polygon><polygon id="ga-logo-p5" points="0.403890196 0.25305098 5.56862745 0.25305098 5.56862745 22.2458353 0.403890196 22.2458353"></polygon></defs><g fill="#1D1D1B" fill-rule="evenodd"><path d="M107.654337,31.5186824 L106.788455,31.5186824 L106.788455,16.1969569 C106.788455,14.8165647 106.8192,13.6758588 106.967906,12.5966431 C107.526337,8.65248627 110.595827,6.2982902 115.179357,6.2982902 C119.763514,6.2982902 122.833004,8.65248627 123.390808,12.5953882 C123.540141,13.6758588 123.570886,14.8165647 123.570886,16.1969569 C123.570886,17.577349 123.540141,18.7180549 123.390808,19.7966431 C122.833004,23.7414275 119.763514,26.0956235 115.179357,26.0956235 C114.656063,26.0956235 114.14218,26.0636235 113.651514,26.0015059 L113.76069,25.1425255 C114.214965,25.200251 114.692455,25.2297412 115.179357,25.2297412 C119.292298,25.2297412 122.041788,23.1541333 122.53371,19.6774275 C122.675514,18.6484078 122.705004,17.5422118 122.705004,16.1969569 C122.705004,14.851702 122.675514,13.7455059 122.53371,12.7152314 C122.041788,9.23978039 119.292298,7.16417255 115.179357,7.16417255 C111.066416,7.16417255 108.317553,9.23978039 107.825631,12.7164863 C107.6832,13.7455059 107.654337,14.851702 107.654337,16.1969569 L107.654337,31.5186824 Z M110.879435,31.5186824 L110.013553,31.5186824 L110.013553,16.1969569 C110.013553,15.1641725 110.013553,14.2725647 110.158494,13.2937412 C110.40069,11.5757804 111.467984,9.52401569 115.179357,9.52401569 C118.891357,9.52401569 119.959278,11.5757804 120.200847,13.2968784 C120.345161,14.2725647 120.345161,15.1641725 120.345161,16.1969569 C120.345161,17.2297412 120.345161,18.121349 120.20022,19.1001725 C119.959278,20.8181333 118.891357,22.869898 115.179357,22.869898 C114.617788,22.869898 114.093239,22.8222118 113.621396,22.7280941 L113.790808,21.8791529 C114.207435,21.9619765 114.674259,22.0040157 115.179357,22.0040157 C117.695435,22.0040157 119.057631,21.013898 119.343749,18.9759373 C119.479906,18.0579765 119.479906,17.1952314 119.479906,16.1969569 C119.479906,15.1986824 119.479906,14.3359373 119.343749,13.4204863 C119.057631,11.3800157 117.695435,10.3892706 115.179357,10.3892706 C112.663906,10.3892706 111.30171,11.3800157 111.015592,13.4179765 C110.879435,14.3359373 110.879435,15.1986824 110.879435,16.1969569 L110.879435,31.5186824 Z"></path><path d="M129.335592,31.5186824 L128.470337,31.5186824 L128.470337,16.1969569 C128.470337,14.8165647 128.500455,13.6758588 128.649788,12.5966431 C129.207592,8.65248627 132.277082,6.2982902 136.861239,6.2982902 C141.444769,6.2982902 144.514259,8.65248627 145.072063,12.5953882 C145.221396,13.6758588 145.251514,14.8165647 145.251514,16.1969569 C145.251514,17.577349 145.221396,18.7180549 145.072063,19.7966431 C144.514259,23.7414275 141.444769,26.0956235 136.861239,26.0956235 C136.337318,26.0956235 135.822808,26.0636235 135.332141,26.0015059 L135.441945,25.1425255 C135.89622,25.200251 136.37371,25.2297412 136.861239,25.2297412 C140.973553,25.2297412 143.723043,23.1541333 144.214965,19.6774275 C144.356769,18.6484078 144.386259,17.5422118 144.386259,16.1969569 C144.386259,14.851702 144.356769,13.7455059 144.214965,12.7152314 C143.723043,9.23978039 140.973553,7.16417255 136.861239,7.16417255 C132.748298,7.16417255 129.998808,9.23978039 129.506886,12.7164863 C129.364455,13.7455059 129.335592,14.851702 129.335592,16.1969569 L129.335592,31.5186824 Z M132.56069,31.5186824 L131.694808,31.5186824 L131.694808,16.1969569 C131.694808,15.1641725 131.694808,14.2725647 131.840376,13.2937412 C132.081318,11.5757804 133.149239,9.52401569 136.861239,9.52401569 C140.572612,9.52401569 141.640533,11.5757804 141.882102,13.2968784 C142.026416,14.2725647 142.026416,15.1641725 142.026416,16.1969569 C142.026416,17.2297412 142.026416,18.121349 141.881475,19.1001725 C141.640533,20.8181333 140.572612,22.869898 136.861239,22.869898 C136.299043,22.869898 135.775122,22.8222118 135.302651,22.7280941 L135.472063,21.8791529 C135.88869,21.9619765 136.355514,22.0040157 136.861239,22.0040157 C139.376063,22.0040157 140.738259,21.013898 141.025004,18.9759373 C141.160533,18.0579765 141.160533,17.1952314 141.160533,16.1969569 C141.160533,15.1986824 141.160533,14.3359373 141.025004,13.4204863 C140.738259,11.3800157 139.376063,10.3892706 136.861239,10.3892706 C134.345161,10.3892706 132.982965,11.3800157 132.696847,13.4179765 C132.56069,14.3359373 132.56069,15.1986824 132.56069,16.1969569 L132.56069,31.5186824 Z"></path><path d="M31.4844235,10.3929098 C28.9689725,10.3929098 27.6067765,11.3830275 27.3206588,13.4209882 C27.184502,14.338949 27.184502,15.2016941 27.184502,16.1999686 C27.184502,17.1988706 27.184502,18.0616157 27.3200314,18.9764392 C27.6067765,21.0175373 28.9689725,22.0076549 31.4844235,22.0076549 C33.9998745,22.0076549 35.3620706,21.0175373 35.6481882,18.9795765 C35.7843451,18.0616157 35.7843451,17.1988706 35.7843451,16.1999686 C35.7843451,15.2016941 35.7843451,14.338949 35.6488157,13.4241255 C35.3620706,11.3830275 33.9998745,10.3929098 31.4844235,10.3929098 M31.4844235,22.8735373 C27.773051,22.8735373 26.7051294,20.8217725 26.4635608,19.1000471 C26.3186196,18.1249882 26.3186196,17.2327529 26.3186196,16.1999686 C26.3186196,15.1678118 26.3186196,14.2755765 26.4635608,13.2973804 C26.7051294,11.5787922 27.773051,9.52702745 31.4844235,9.52702745 C35.1957961,9.52702745 36.2637176,11.5787922 36.5059137,13.3005176 C36.6502275,14.2755765 36.6502275,15.1678118 36.6502275,16.1999686 C36.6502275,17.2327529 36.6502275,18.1249882 36.5052863,19.1031843 C36.2637176,20.8217725 35.1957961,22.8735373 31.4844235,22.8735373 M31.4844235,7.16718431 C27.3714824,7.16718431 24.6226196,9.24341961 24.130698,12.719498 C23.9882667,13.7485176 23.9594039,14.8553412 23.9594039,16.1999686 C23.9594039,17.5452235 23.9882667,18.6520471 24.130698,19.6823216 C24.6226196,23.1571451 27.3714824,25.2333804 31.4844235,25.2333804 C35.5973647,25.2333804 38.3462275,23.1571451 38.8387765,19.6804392 C38.9805804,18.6520471 39.0094431,17.5452235 39.0094431,16.1999686 C39.0094431,14.8553412 38.9805804,13.7485176 38.838149,12.7188706 C38.3462275,9.24341961 35.5973647,7.16718431 31.4844235,7.16718431 M31.4844235,26.0986353 C26.9008941,26.0986353 23.8314039,23.7450667 23.2729725,19.8015373 C23.1242667,18.7210667 23.0935216,17.5809882 23.0935216,16.1999686 C23.0935216,14.8195765 23.1242667,13.679498 23.2729725,12.6002824 C23.8314039,8.65549804 26.9008941,6.30192941 31.4844235,6.30192941 C36.0679529,6.30192941 39.1374431,8.65549804 39.6958745,12.5990275 C39.8445804,13.679498 39.8753255,14.8195765 39.8753255,16.1999686 C39.8753255,17.5809882 39.8445804,18.7210667 39.6958745,19.8002824 C39.1374431,23.7450667 36.0679529,26.0986353 31.4844235,26.0986353"></path><path d="M72.8260392,22.8732863 C69.1146667,22.8732863 68.0467451,20.8215216 67.8051765,19.1004235 C67.6602353,18.1247373 67.6602353,17.2331294 67.6602353,16.2003451 C67.6602353,15.1675608 67.6602353,14.2759529 67.8051765,13.2971294 C68.0467451,11.5791686 69.1146667,9.52740392 72.8260392,9.52740392 C73.3876078,9.52740392 73.9121569,9.5750902 74.3846275,9.66920784 L74.2145882,10.518149 C73.7979608,10.4353255 73.3311373,10.3932863 72.8260392,10.3932863 C70.3105882,10.3932863 68.9483922,11.3834039 68.6622745,13.4213647 C68.5261176,14.3393255 68.5261176,15.2020706 68.5261176,16.2003451 C68.5261176,17.1986196 68.5261176,18.0613647 68.6616471,18.9761882 C68.9483922,21.0172863 70.3105882,22.0080314 72.8260392,22.0080314 C75.3414902,22.0080314 76.7036863,21.0172863 76.9898039,18.9793255 C77.1259608,18.0613647 77.1259608,17.1986196 77.1259608,16.2003451 L77.1259608,0.87987451 L77.9918431,0.87987451 L77.9918431,16.2003451 C77.9918431,17.2331294 77.9918431,18.1247373 77.846902,19.1035608 C77.6053333,20.8215216 76.5380392,22.8732863 72.8260392,22.8732863 M72.8260392,26.0990118 C68.2425098,26.0990118 65.1730196,23.7448157 64.6152157,19.8019137 C64.4658824,18.7214431 64.4351373,17.5807373 64.4351373,16.2003451 C64.4351373,14.8199529 64.4658824,13.6792471 64.6145882,12.6006588 C65.1730196,8.65587451 68.2425098,6.30167843 72.8260392,6.30167843 C73.3493333,6.30167843 73.8638431,6.33305098 74.3545098,6.39579608 L74.2447059,7.25477647 C73.7904314,7.19705098 73.3129412,7.16756078 72.8260392,7.16756078 C68.713098,7.16756078 65.9642353,9.24316863 65.4716863,12.7198745 C65.3298824,13.7488941 65.3010196,14.8550902 65.3010196,16.2003451 C65.3010196,17.5456 65.3298824,18.6517961 65.4723137,19.6820706 C65.9642353,23.1575216 68.713098,25.2331294 72.8260392,25.2331294 C76.9389804,25.2331294 79.6878431,23.1575216 80.1803922,19.6808157 C80.3221961,18.6517961 80.3516863,17.5456 80.3516863,16.2003451 L80.3516863,0.87987451 L81.2169412,0.87987451 L81.2169412,16.2003451 C81.2169412,17.5807373 81.1861961,18.7214431 81.0374902,19.8006588 C80.4790588,23.7448157 77.4095686,26.0990118 72.8260392,26.0990118"></path><path d="M52.2897569,22.8732863 C48.5783843,22.8732863 47.5104627,20.8215216 47.2688941,19.1004235 C47.1239529,18.1247373 47.1239529,17.2331294 47.1239529,16.2003451 L47.1239529,6.76222745 L47.9898353,6.76222745 L47.9898353,16.2003451 C47.9898353,17.1986196 47.9898353,18.0613647 48.1253647,18.9761882 C48.4121098,21.0172863 49.7743059,22.0080314 52.2897569,22.0080314 C54.8052078,22.0080314 56.1674039,21.0172863 56.4535216,18.9793255 C56.5896784,18.0613647 56.5896784,17.1986196 56.5896784,16.2003451 L56.5896784,6.76222745 L57.4555608,6.76222745 L57.4555608,16.2003451 C57.4555608,17.2331294 57.4555608,18.1247373 57.3106196,19.1035608 C57.069051,20.8215216 56.0017569,22.8732863 52.2897569,22.8732863 M52.2897569,26.0990118 C47.7062275,26.0990118 44.6367373,23.7448157 44.0783059,19.8019137 C43.9296,18.7214431 43.8988549,17.5807373 43.8988549,16.2003451 L43.8988549,6.76222745 L44.7647373,6.76222745 L44.7647373,16.2003451 C44.7647373,17.5456 44.7936,18.6517961 44.9360314,19.6820706 C45.4279529,23.1575216 48.1768157,25.2331294 52.2897569,25.2331294 C56.402698,25.2331294 59.1515608,23.1575216 59.6441098,19.6808157 C59.7859137,18.6517961 59.8154039,17.5456 59.8154039,16.2003451 L59.8154039,6.76222745 L60.6806588,6.76222745 L60.6806588,16.2003451 C60.6806588,17.5807373 60.6499137,18.7214431 60.5012078,19.8006588 C59.9427765,23.7448157 56.8732863,26.0990118 52.2897569,26.0990118"></path><g><mask id="ga-logo-m2" fill="white"><use href="#ga-logo-p1"></use></mask><path d="M9.60288627,22.8732863 C5.80053333,22.8732863 3.90625882,21.7595608 3.48210196,19.2679529 L3.45700392,19.2698353 C3.30955294,18.2765804 3.22547451,14.2226196 3.22547451,13.2726588 L3.22923922,12.8397176 C3.24555294,11.4436392 3.32649412,8.33712941 3.45763137,7.45305098 C3.82280784,4.84661961 5.7152,3.68207059 9.59347451,3.68144314 L9.59974902,3.68144314 C13.5413961,3.68144314 15.3779451,4.8096 15.7500235,7.45242353 L14.8929255,7.57352157 C14.6369255,5.75705098 13.6399059,4.54669804 9.60916078,4.54669804 L9.60288627,4.54669804 C5.32680784,4.54795294 4.53496471,6.00363922 4.31410196,7.57665882 C4.18108235,8.47579608 4.09198431,12.2279529 4.09261176,13.2726588 L4.09261176,13.5430902 C4.10327843,14.8212078 4.1804549,17.9390118 4.29276863,18.9812078 L4.31347451,18.9793255 C4.53433725,20.5523451 5.32743529,22.0080314 9.59347451,22.0080314 C13.6399059,22.0080314 14.6369255,20.797051 14.892298,18.9793255 C15.0284549,18.0613647 15.0284549,17.1986196 15.0284549,16.2003451 L15.0284549,16.0554039 C15.0246902,15.8188549 15.0228078,15.7077961 14.4016314,15.7077961 L12.0292392,15.7077961 L12.0292392,14.8419137 L14.4016314,14.8419137 C14.8044549,14.8419137 15.8742588,14.8419137 15.8937098,16.0478745 L15.8937098,16.2003451 C15.8937098,17.2331294 15.8937098,18.1247373 15.7493961,19.1035608 C15.3779451,21.7451294 13.5395137,22.8732863 9.60288627,22.8732863 M9.60288627,26.0990118 C4.39378824,26.0990118 0.816062745,23.6864627 0.266415686,19.8019137 C0.1152,18.7076392 0.000376470588,14.6072471 0.000376470588,13.2726588 L0.00414117647,12.8397176 C0.0217098039,11.1129725 0.135278431,7.70716863 0.266415686,6.75720784 C0.814807843,2.87140392 4.39190588,0.456972549 9.60163137,0.455717647 L9.60790588,0.455717647 C13.4592,0.455717647 18.202102,1.54873725 18.9399843,6.75030588 L18.0822588,6.87203137 C17.5602196,3.18889412 14.7090824,1.3216 9.60790588,1.3216 L9.60163137,1.3216 C4.85621961,1.3228549 1.60727843,3.45116863 1.12414118,6.87642353 C0.987984314,7.86277647 0.866886275,11.8219922 0.866886275,13.2726588 L0.866886275,13.5688157 C0.880690196,15.2058353 0.996141176,18.7584627 1.12351373,19.6820706 C1.60790588,23.1054431 4.85684706,25.2331294 9.60288627,25.2331294 C14.7084549,25.2331294 17.5614745,23.3645804 18.0822588,19.6808157 C18.2246902,18.6517961 18.2535529,17.5456 18.2535529,16.2003451 L18.2535529,15.5114039 C18.2416314,13.6422275 17.5821804,12.4820706 14.3344941,12.4820706 L12.0292392,12.4820706 L12.0292392,11.6168157 L14.3344941,11.6168157 C17.6267294,11.6168157 19.1024941,12.8171294 19.1194353,15.5088941 L19.1194353,16.2003451 C19.1194353,17.5807373 19.0886902,18.7214431 18.9399843,19.8006588 C18.2027294,25.0059922 13.4560627,26.0990118 9.60288627,26.0990118" mask="url(#ga-logo-m2)"></path></g><path d="M158.933898,22.8732863 C155.221898,22.8732863 154.154604,20.8215216 153.912408,19.1004235 C153.768094,18.1247373 153.768094,17.2331294 153.768094,16.2003451 C153.768094,15.1675608 153.768094,14.2759529 153.913035,13.2971294 C154.154604,11.5791686 155.221898,9.52740392 158.933898,9.52740392 C160.854525,9.44144314 162.288251,9.82042353 163.187388,10.6549333 C164.02629,11.4336 164.062682,12.3283451 164.06331,12.3666196 C164.116643,12.9639529 164.126055,13.8599529 163.585192,14.4497569 C163.238839,14.8281098 162.727467,15.0201098 162.066133,15.0201098 L157.392251,15.0201098 L157.392251,14.1542275 L162.066133,14.1542275 C162.480878,14.1542275 162.768251,14.0601098 162.947075,13.8649725 C163.257035,13.5267765 163.240094,12.8761098 163.19931,12.4168157 C163.193035,12.3076392 163.03931,10.2100706 158.953349,10.3926588 C156.418447,10.3932863 155.056251,11.3834039 154.770133,13.4213647 C154.633976,14.3393255 154.633976,15.2020706 154.633976,16.2003451 C154.633976,17.1986196 154.633976,18.0613647 154.769506,18.9761882 C155.056251,21.0172863 156.418447,22.0080314 158.933898,22.0080314 C160.680722,22.0080314 162.01782,21.7965804 163.548173,21.2789333 L163.824878,22.0990118 C162.199153,22.6486588 160.782369,22.8732863 158.933898,22.8732863 M158.933898,26.0990118 C154.350369,26.0990118 151.280878,23.7448157 150.722447,19.8019137 C150.573741,18.7214431 150.542996,17.5807373 150.542996,16.2003451 C150.542996,14.8199529 150.573741,13.6792471 150.722447,12.6006588 C151.280878,8.65587451 154.350369,6.30167843 158.933898,6.30167843 C163.805427,6.30167843 166.779545,8.35846275 167.307859,12.0917961 C167.595859,13.885051 167.25829,15.4116392 166.331545,16.4990118 C165.357741,17.6416 163.749584,18.2458353 161.680878,18.2458353 L157.392251,18.2458353 L157.392251,17.3799529 L161.680878,17.3799529 C163.513663,17.3799529 164.857035,16.8949333 165.672722,15.9374431 C166.430055,15.0489725 166.699859,13.7639529 166.452016,12.221051 C166.125741,9.91140392 164.557114,7.16756078 158.933898,7.16756078 C154.820957,7.16756078 152.072094,9.24316863 151.579545,12.7198745 C151.437741,13.7488941 151.408251,14.8550902 151.408251,16.2003451 C151.408251,17.5456 151.437741,18.6517961 151.579545,19.6820706 C152.072094,23.1575216 154.820957,25.2331294 158.933898,25.2331294 C160.945506,25.2331294 162.655937,24.9972078 164.479937,24.4676392 L164.721506,25.2983843 C162.815937,25.8524235 161.030839,26.0990118 158.933898,26.0990118"></path><path d="M93.260549,22.8851451 C91.6015686,22.8851451 90.3422745,22.5030275 89.5265882,21.7456941 C88.6876863,20.9670275 88.6519216,20.0722824 88.6506667,20.0340078 C88.5973333,19.4366745 88.5879216,18.541302 89.1287843,17.9508706 C89.4751373,17.5725176 89.9865098,17.3805176 90.6478431,17.3805176 L95.3217255,17.3805176 L95.3217255,18.2464 L90.6478431,18.2464 C90.2337255,18.2464 89.945098,18.3411451 89.766902,18.5356549 C89.4563137,18.8744784 89.4745098,19.5245176 89.5146667,19.9831843 C89.5209412,20.0936157 89.6809412,22.1899294 93.7612549,22.0079686 C96.2961569,22.0079686 97.6577255,21.0172235 97.9444706,18.9792627 C98.0806275,18.061302 98.0806275,17.1985569 98.0806275,16.2002824 C98.0806275,15.2020078 98.0806275,14.3392627 97.945098,13.4238118 C97.6577255,11.3833412 96.2961569,10.3932235 93.7807059,10.3932235 C92.0332549,10.3932235 90.6967843,10.6040471 89.1664314,11.1216941 L88.889098,10.3016157 C90.5148235,9.75196863 91.9322353,9.52734118 93.7807059,9.52734118 C97.4920784,9.52734118 98.5593725,11.5791059 98.8015686,13.3002039 C98.9458824,14.2758902 98.9458824,15.167498 98.9458824,16.2002824 C98.9458824,17.2330667 98.9458824,18.1246745 98.8015686,19.103498 C98.5593725,20.8214588 97.4920784,22.8732235 93.7807059,22.8732235 C93.6031373,22.8813804 93.4293333,22.8851451 93.260549,22.8851451 M93.7807059,26.098949 C88.9079216,26.098949 85.9338039,24.0427922 85.4054902,20.3082039 C85.1181176,18.5155765 85.4556863,16.9883608 86.3824314,15.9016157 C87.3568627,14.7590275 88.9643922,14.1547922 91.0324706,14.1547922 L95.3217255,14.1547922 L95.3217255,15.0206745 L91.0324706,15.0206745 C89.2003137,15.0206745 87.8569412,15.5056941 87.0412549,16.4631843 C86.2839216,17.3510275 86.0141176,18.6366745 86.2619608,20.1795765 C86.5882353,22.4892235 88.1568627,25.2330667 93.7807059,25.2330667 C97.8936471,25.2330667 100.64251,23.1574588 101.134431,19.6807529 C101.276863,18.6517333 101.305725,17.5455373 101.305725,16.2002824 C101.305725,14.8550275 101.276863,13.7488314 101.134431,12.7185569 C100.64251,9.24310588 97.8936471,7.16749804 93.7807059,7.16749804 C91.7684706,7.16749804 90.0580392,7.40341961 88.2340392,7.93361569 L87.9924706,7.10224314 C89.8980392,6.54883137 91.6831373,6.30161569 93.7807059,6.30161569 C98.3642353,6.30161569 101.433725,8.65581176 101.991529,12.5987137 C102.140863,13.6791843 102.17098,14.8198902 102.17098,16.2002824 C102.17098,17.5806745 102.140863,18.7213804 101.992157,19.8005961 C101.433725,23.7447529 98.3642353,26.098949 93.7807059,26.098949"></path><g transform="translate(171.921569, 0.627451)"><mask id="ga-logo-m4" fill="white"><use href="#ga-logo-p3"></use></mask><path d="M8.70694902,25.4714353 C4.12341961,25.4714353 1.05392941,23.1172392 0.495498039,19.1743373 C0.339262745,18.0417882 0.316047059,16.6752 0.316047059,15.9617882 L0.316047059,0.25292549 L1.18192941,0.25292549 L1.18192941,15.9617882 C1.18192941,16.6532392 1.2038902,17.974651 1.35259608,19.0544941 C1.8451451,22.5299451 4.59400784,24.6055529 8.70694902,24.6055529 L8.70694902,25.4714353 Z" mask="url(#ga-logo-m4)"></path></g><g transform="translate(175.058824, 0.627451)"><mask id="ga-logo-m6" fill="white"><use href="#ga-logo-p5"></use></mask><path d="M5.56969412,22.2458353 C1.85832157,22.2458353 0.7904,20.1940706 0.548203922,18.4729725 C0.403890196,17.4972863 0.403890196,16.432502 0.403890196,15.4028549 L0.404517647,0.25305098 L1.26977255,0.25305098 L1.26977255,15.4028549 C1.26977255,16.4011294 1.26977255,17.4339137 1.40530196,18.3487373 C1.69204706,20.3898353 3.05424314,21.3805804 5.56969412,21.3805804 L5.56969412,22.2458353 Z" mask="url(#ga-logo-m6)"></path></g></g></symbol>
  <symbol id="ga-i-select" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3v16l4.5-4.5 3 6.5 2.6-1.2-3-6.3H18z"/></symbol>
  <symbol id="ga-i-select-box" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="1" stroke-dasharray="2 4"/></symbol>
  <symbol id="ga-i-pan" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"/></symbol>
  <symbol id="ga-i-zoom-in" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21M10.5 7.5v6M7.5 10.5h6"/></symbol>
  <symbol id="ga-i-zoom-out" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21M7.5 10.5h6"/></symbol>
  <symbol id="ga-i-extent" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></symbol>
  <symbol id="ga-i-fullscreen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/></symbol>
  <symbol id="ga-i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></symbol>
  <symbol id="ga-i-point" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.2"/></symbol>
  <symbol id="ga-i-line" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6.2 16.6 9.6 10.6M11.6 10.4l1.8 2.2M15.4 12.2l2.4-4.4"/><circle cx="5" cy="18.5" r="1.8"/><circle cx="10.5" cy="9" r="1.8"/><circle cx="14.5" cy="14" r="1.8"/><circle cx="19" cy="5.5" r="1.8"/></symbol>
  <symbol id="ga-i-polygon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 9l7-5 7 5-2.5 10h-9z"/></symbol>
  <symbol id="ga-i-measure" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16 16 3l5 5L8 21z"/><path d="m7 12 2 2M10 9l2 2M13 6l2 2"/></symbol>
  <symbol id="ga-i-edit" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20v-4L16 4l4 4L8 20z"/><path d="m13 7 4 4"/></symbol>
  <symbol id="ga-i-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="8" width="12" height="12" rx="1.5"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/></symbol>
  <symbol id="ga-i-delete" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5"/></symbol>
  <symbol id="ga-i-undo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></symbol>
  <symbol id="ga-i-redo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/></symbol>
  <symbol id="ga-i-layers" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 21 8l-9 5-9-5z"/><path d="m3 12.5 9 5 9-5M3 16.5l9 5 9-5"/></symbol>
  <symbol id="ga-i-visible" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></symbol>
  <symbol id="ga-i-hidden" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/><path d="M3 3l18 18"/></symbol>
  <symbol id="ga-i-labels" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h8l10 10-8 8L3 11z"/><circle cx="7.5" cy="7.5" r="1.5"/></symbol>
  <symbol id="ga-i-grid" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="1.5"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/></symbol>
  <symbol id="ga-i-legend" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="4" height="4" rx=".5"/><rect x="3" y="15" width="4" height="4" rx=".5"/><path d="M11 7h10M11 17h10"/></symbol>
  <symbol id="ga-i-cluster" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="8" r="3.5"/><circle cx="16.5" cy="7.5" r="2.5"/><circle cx="12.5" cy="16" r="4.5"/></symbol>
  <symbol id="ga-i-map" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z"/><path d="M9 4v13.5M15 6.5V20"/></symbol>
  <symbol id="ga-i-table" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M3 10h18M3 15h18M9 10v10"/></symbol>
  <symbol id="ga-i-chart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 20h18M6.5 16v-4M11.5 16V6M16.5 16v-7"/></symbol>
  <symbol id="ga-i-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 10l5 5 5-5M4 20h16"/></symbol>
  <symbol id="ga-i-upload" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4M7 9l5-5 5 5M4 20h16"/></symbol>
  <symbol id="ga-i-save" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3h11l3 3v15H5z"/><path d="M8 3v5h7V3M8 21v-7h8v7"/></symbol>
  <symbol id="ga-i-link" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14a4.5 4.5 0 0 0 6.4 0l3.2-3.2a4.5 4.5 0 0 0-6.4-6.4L12 5.6M14 10a4.5 4.5 0 0 0-6.4 0l-3.2 3.2a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2"/></symbol>
  <symbol id="ga-i-filter" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h18l-7 8.5V19l-4 2v-8.5z"/></symbol>
  <symbol id="ga-i-settings" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></symbol>
  <symbol id="ga-i-info" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.01"/></symbol>
  <symbol id="ga-i-help" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.4 2.3c-.6.3-.9.8-.9 1.5v.4M12 16.8v.01"/></symbol>
  <symbol id="ga-i-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6 6 18"/></symbol>
  <symbol id="ga-i-plus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></symbol>
  <symbol id="ga-i-minus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/></symbol>
  <symbol id="ga-i-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7"/></symbol>
  <symbol id="ga-i-chevron-down" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></symbol>
  <symbol id="ga-i-chevron-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></symbol>
  <symbol id="ga-i-arrow-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h18M15 6l6 6-6 6"/></symbol>
  <symbol id="ga-i-menu" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h16"/></symbol>
  <symbol id="ga-i-code" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 7-5 5 5 5M16 7l5 5-5 5"/></symbol>
  <symbol id="ga-i-mail" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="m3.5 6.5 8.5 6.5 8.5-6.5"/></symbol>
  <symbol id="ga-i-phone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5.5 3.5h3l1.5 4.5-2.2 1.4a11 11 0 0 0 6.8 6.8l1.4-2.2 4.5 1.5v3a1.5 1.5 0 0 1-1.6 1.5A16.5 16.5 0 0 1 4 5.1 1.5 1.5 0 0 1 5.5 3.5z"/></symbol>
</svg>
```

## Logo als los bestand (`logo-goudappel.svg`)

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 182 32" width="182" height="32" role="img" aria-label="Goudappel"><defs><polygon id="ga-logo-p1" points="0.000376470588 0.456156863 19.1194353 0.456156863 19.1194353 26.0990118 0.000376470588 26.0990118"></polygon><polygon id="ga-logo-p3" points="0.316047059 0.25292549 8.70588235 0.25292549 8.70588235 25.4714353 0.316047059 25.4714353"></polygon><polygon id="ga-logo-p5" points="0.403890196 0.25305098 5.56862745 0.25305098 5.56862745 22.2458353 0.403890196 22.2458353"></polygon></defs><g fill="#1D1D1B" fill-rule="evenodd"><path d="M107.654337,31.5186824 L106.788455,31.5186824 L106.788455,16.1969569 C106.788455,14.8165647 106.8192,13.6758588 106.967906,12.5966431 C107.526337,8.65248627 110.595827,6.2982902 115.179357,6.2982902 C119.763514,6.2982902 122.833004,8.65248627 123.390808,12.5953882 C123.540141,13.6758588 123.570886,14.8165647 123.570886,16.1969569 C123.570886,17.577349 123.540141,18.7180549 123.390808,19.7966431 C122.833004,23.7414275 119.763514,26.0956235 115.179357,26.0956235 C114.656063,26.0956235 114.14218,26.0636235 113.651514,26.0015059 L113.76069,25.1425255 C114.214965,25.200251 114.692455,25.2297412 115.179357,25.2297412 C119.292298,25.2297412 122.041788,23.1541333 122.53371,19.6774275 C122.675514,18.6484078 122.705004,17.5422118 122.705004,16.1969569 C122.705004,14.851702 122.675514,13.7455059 122.53371,12.7152314 C122.041788,9.23978039 119.292298,7.16417255 115.179357,7.16417255 C111.066416,7.16417255 108.317553,9.23978039 107.825631,12.7164863 C107.6832,13.7455059 107.654337,14.851702 107.654337,16.1969569 L107.654337,31.5186824 Z M110.879435,31.5186824 L110.013553,31.5186824 L110.013553,16.1969569 C110.013553,15.1641725 110.013553,14.2725647 110.158494,13.2937412 C110.40069,11.5757804 111.467984,9.52401569 115.179357,9.52401569 C118.891357,9.52401569 119.959278,11.5757804 120.200847,13.2968784 C120.345161,14.2725647 120.345161,15.1641725 120.345161,16.1969569 C120.345161,17.2297412 120.345161,18.121349 120.20022,19.1001725 C119.959278,20.8181333 118.891357,22.869898 115.179357,22.869898 C114.617788,22.869898 114.093239,22.8222118 113.621396,22.7280941 L113.790808,21.8791529 C114.207435,21.9619765 114.674259,22.0040157 115.179357,22.0040157 C117.695435,22.0040157 119.057631,21.013898 119.343749,18.9759373 C119.479906,18.0579765 119.479906,17.1952314 119.479906,16.1969569 C119.479906,15.1986824 119.479906,14.3359373 119.343749,13.4204863 C119.057631,11.3800157 117.695435,10.3892706 115.179357,10.3892706 C112.663906,10.3892706 111.30171,11.3800157 111.015592,13.4179765 C110.879435,14.3359373 110.879435,15.1986824 110.879435,16.1969569 L110.879435,31.5186824 Z"></path><path d="M129.335592,31.5186824 L128.470337,31.5186824 L128.470337,16.1969569 C128.470337,14.8165647 128.500455,13.6758588 128.649788,12.5966431 C129.207592,8.65248627 132.277082,6.2982902 136.861239,6.2982902 C141.444769,6.2982902 144.514259,8.65248627 145.072063,12.5953882 C145.221396,13.6758588 145.251514,14.8165647 145.251514,16.1969569 C145.251514,17.577349 145.221396,18.7180549 145.072063,19.7966431 C144.514259,23.7414275 141.444769,26.0956235 136.861239,26.0956235 C136.337318,26.0956235 135.822808,26.0636235 135.332141,26.0015059 L135.441945,25.1425255 C135.89622,25.200251 136.37371,25.2297412 136.861239,25.2297412 C140.973553,25.2297412 143.723043,23.1541333 144.214965,19.6774275 C144.356769,18.6484078 144.386259,17.5422118 144.386259,16.1969569 C144.386259,14.851702 144.356769,13.7455059 144.214965,12.7152314 C143.723043,9.23978039 140.973553,7.16417255 136.861239,7.16417255 C132.748298,7.16417255 129.998808,9.23978039 129.506886,12.7164863 C129.364455,13.7455059 129.335592,14.851702 129.335592,16.1969569 L129.335592,31.5186824 Z M132.56069,31.5186824 L131.694808,31.5186824 L131.694808,16.1969569 C131.694808,15.1641725 131.694808,14.2725647 131.840376,13.2937412 C132.081318,11.5757804 133.149239,9.52401569 136.861239,9.52401569 C140.572612,9.52401569 141.640533,11.5757804 141.882102,13.2968784 C142.026416,14.2725647 142.026416,15.1641725 142.026416,16.1969569 C142.026416,17.2297412 142.026416,18.121349 141.881475,19.1001725 C141.640533,20.8181333 140.572612,22.869898 136.861239,22.869898 C136.299043,22.869898 135.775122,22.8222118 135.302651,22.7280941 L135.472063,21.8791529 C135.88869,21.9619765 136.355514,22.0040157 136.861239,22.0040157 C139.376063,22.0040157 140.738259,21.013898 141.025004,18.9759373 C141.160533,18.0579765 141.160533,17.1952314 141.160533,16.1969569 C141.160533,15.1986824 141.160533,14.3359373 141.025004,13.4204863 C140.738259,11.3800157 139.376063,10.3892706 136.861239,10.3892706 C134.345161,10.3892706 132.982965,11.3800157 132.696847,13.4179765 C132.56069,14.3359373 132.56069,15.1986824 132.56069,16.1969569 L132.56069,31.5186824 Z"></path><path d="M31.4844235,10.3929098 C28.9689725,10.3929098 27.6067765,11.3830275 27.3206588,13.4209882 C27.184502,14.338949 27.184502,15.2016941 27.184502,16.1999686 C27.184502,17.1988706 27.184502,18.0616157 27.3200314,18.9764392 C27.6067765,21.0175373 28.9689725,22.0076549 31.4844235,22.0076549 C33.9998745,22.0076549 35.3620706,21.0175373 35.6481882,18.9795765 C35.7843451,18.0616157 35.7843451,17.1988706 35.7843451,16.1999686 C35.7843451,15.2016941 35.7843451,14.338949 35.6488157,13.4241255 C35.3620706,11.3830275 33.9998745,10.3929098 31.4844235,10.3929098 M31.4844235,22.8735373 C27.773051,22.8735373 26.7051294,20.8217725 26.4635608,19.1000471 C26.3186196,18.1249882 26.3186196,17.2327529 26.3186196,16.1999686 C26.3186196,15.1678118 26.3186196,14.2755765 26.4635608,13.2973804 C26.7051294,11.5787922 27.773051,9.52702745 31.4844235,9.52702745 C35.1957961,9.52702745 36.2637176,11.5787922 36.5059137,13.3005176 C36.6502275,14.2755765 36.6502275,15.1678118 36.6502275,16.1999686 C36.6502275,17.2327529 36.6502275,18.1249882 36.5052863,19.1031843 C36.2637176,20.8217725 35.1957961,22.8735373 31.4844235,22.8735373 M31.4844235,7.16718431 C27.3714824,7.16718431 24.6226196,9.24341961 24.130698,12.719498 C23.9882667,13.7485176 23.9594039,14.8553412 23.9594039,16.1999686 C23.9594039,17.5452235 23.9882667,18.6520471 24.130698,19.6823216 C24.6226196,23.1571451 27.3714824,25.2333804 31.4844235,25.2333804 C35.5973647,25.2333804 38.3462275,23.1571451 38.8387765,19.6804392 C38.9805804,18.6520471 39.0094431,17.5452235 39.0094431,16.1999686 C39.0094431,14.8553412 38.9805804,13.7485176 38.838149,12.7188706 C38.3462275,9.24341961 35.5973647,7.16718431 31.4844235,7.16718431 M31.4844235,26.0986353 C26.9008941,26.0986353 23.8314039,23.7450667 23.2729725,19.8015373 C23.1242667,18.7210667 23.0935216,17.5809882 23.0935216,16.1999686 C23.0935216,14.8195765 23.1242667,13.679498 23.2729725,12.6002824 C23.8314039,8.65549804 26.9008941,6.30192941 31.4844235,6.30192941 C36.0679529,6.30192941 39.1374431,8.65549804 39.6958745,12.5990275 C39.8445804,13.679498 39.8753255,14.8195765 39.8753255,16.1999686 C39.8753255,17.5809882 39.8445804,18.7210667 39.6958745,19.8002824 C39.1374431,23.7450667 36.0679529,26.0986353 31.4844235,26.0986353"></path><path d="M72.8260392,22.8732863 C69.1146667,22.8732863 68.0467451,20.8215216 67.8051765,19.1004235 C67.6602353,18.1247373 67.6602353,17.2331294 67.6602353,16.2003451 C67.6602353,15.1675608 67.6602353,14.2759529 67.8051765,13.2971294 C68.0467451,11.5791686 69.1146667,9.52740392 72.8260392,9.52740392 C73.3876078,9.52740392 73.9121569,9.5750902 74.3846275,9.66920784 L74.2145882,10.518149 C73.7979608,10.4353255 73.3311373,10.3932863 72.8260392,10.3932863 C70.3105882,10.3932863 68.9483922,11.3834039 68.6622745,13.4213647 C68.5261176,14.3393255 68.5261176,15.2020706 68.5261176,16.2003451 C68.5261176,17.1986196 68.5261176,18.0613647 68.6616471,18.9761882 C68.9483922,21.0172863 70.3105882,22.0080314 72.8260392,22.0080314 C75.3414902,22.0080314 76.7036863,21.0172863 76.9898039,18.9793255 C77.1259608,18.0613647 77.1259608,17.1986196 77.1259608,16.2003451 L77.1259608,0.87987451 L77.9918431,0.87987451 L77.9918431,16.2003451 C77.9918431,17.2331294 77.9918431,18.1247373 77.846902,19.1035608 C77.6053333,20.8215216 76.5380392,22.8732863 72.8260392,22.8732863 M72.8260392,26.0990118 C68.2425098,26.0990118 65.1730196,23.7448157 64.6152157,19.8019137 C64.4658824,18.7214431 64.4351373,17.5807373 64.4351373,16.2003451 C64.4351373,14.8199529 64.4658824,13.6792471 64.6145882,12.6006588 C65.1730196,8.65587451 68.2425098,6.30167843 72.8260392,6.30167843 C73.3493333,6.30167843 73.8638431,6.33305098 74.3545098,6.39579608 L74.2447059,7.25477647 C73.7904314,7.19705098 73.3129412,7.16756078 72.8260392,7.16756078 C68.713098,7.16756078 65.9642353,9.24316863 65.4716863,12.7198745 C65.3298824,13.7488941 65.3010196,14.8550902 65.3010196,16.2003451 C65.3010196,17.5456 65.3298824,18.6517961 65.4723137,19.6820706 C65.9642353,23.1575216 68.713098,25.2331294 72.8260392,25.2331294 C76.9389804,25.2331294 79.6878431,23.1575216 80.1803922,19.6808157 C80.3221961,18.6517961 80.3516863,17.5456 80.3516863,16.2003451 L80.3516863,0.87987451 L81.2169412,0.87987451 L81.2169412,16.2003451 C81.2169412,17.5807373 81.1861961,18.7214431 81.0374902,19.8006588 C80.4790588,23.7448157 77.4095686,26.0990118 72.8260392,26.0990118"></path><path d="M52.2897569,22.8732863 C48.5783843,22.8732863 47.5104627,20.8215216 47.2688941,19.1004235 C47.1239529,18.1247373 47.1239529,17.2331294 47.1239529,16.2003451 L47.1239529,6.76222745 L47.9898353,6.76222745 L47.9898353,16.2003451 C47.9898353,17.1986196 47.9898353,18.0613647 48.1253647,18.9761882 C48.4121098,21.0172863 49.7743059,22.0080314 52.2897569,22.0080314 C54.8052078,22.0080314 56.1674039,21.0172863 56.4535216,18.9793255 C56.5896784,18.0613647 56.5896784,17.1986196 56.5896784,16.2003451 L56.5896784,6.76222745 L57.4555608,6.76222745 L57.4555608,16.2003451 C57.4555608,17.2331294 57.4555608,18.1247373 57.3106196,19.1035608 C57.069051,20.8215216 56.0017569,22.8732863 52.2897569,22.8732863 M52.2897569,26.0990118 C47.7062275,26.0990118 44.6367373,23.7448157 44.0783059,19.8019137 C43.9296,18.7214431 43.8988549,17.5807373 43.8988549,16.2003451 L43.8988549,6.76222745 L44.7647373,6.76222745 L44.7647373,16.2003451 C44.7647373,17.5456 44.7936,18.6517961 44.9360314,19.6820706 C45.4279529,23.1575216 48.1768157,25.2331294 52.2897569,25.2331294 C56.402698,25.2331294 59.1515608,23.1575216 59.6441098,19.6808157 C59.7859137,18.6517961 59.8154039,17.5456 59.8154039,16.2003451 L59.8154039,6.76222745 L60.6806588,6.76222745 L60.6806588,16.2003451 C60.6806588,17.5807373 60.6499137,18.7214431 60.5012078,19.8006588 C59.9427765,23.7448157 56.8732863,26.0990118 52.2897569,26.0990118"></path><g><mask id="ga-logo-m2" fill="white"><use href="#ga-logo-p1"></use></mask><path d="M9.60288627,22.8732863 C5.80053333,22.8732863 3.90625882,21.7595608 3.48210196,19.2679529 L3.45700392,19.2698353 C3.30955294,18.2765804 3.22547451,14.2226196 3.22547451,13.2726588 L3.22923922,12.8397176 C3.24555294,11.4436392 3.32649412,8.33712941 3.45763137,7.45305098 C3.82280784,4.84661961 5.7152,3.68207059 9.59347451,3.68144314 L9.59974902,3.68144314 C13.5413961,3.68144314 15.3779451,4.8096 15.7500235,7.45242353 L14.8929255,7.57352157 C14.6369255,5.75705098 13.6399059,4.54669804 9.60916078,4.54669804 L9.60288627,4.54669804 C5.32680784,4.54795294 4.53496471,6.00363922 4.31410196,7.57665882 C4.18108235,8.47579608 4.09198431,12.2279529 4.09261176,13.2726588 L4.09261176,13.5430902 C4.10327843,14.8212078 4.1804549,17.9390118 4.29276863,18.9812078 L4.31347451,18.9793255 C4.53433725,20.5523451 5.32743529,22.0080314 9.59347451,22.0080314 C13.6399059,22.0080314 14.6369255,20.797051 14.892298,18.9793255 C15.0284549,18.0613647 15.0284549,17.1986196 15.0284549,16.2003451 L15.0284549,16.0554039 C15.0246902,15.8188549 15.0228078,15.7077961 14.4016314,15.7077961 L12.0292392,15.7077961 L12.0292392,14.8419137 L14.4016314,14.8419137 C14.8044549,14.8419137 15.8742588,14.8419137 15.8937098,16.0478745 L15.8937098,16.2003451 C15.8937098,17.2331294 15.8937098,18.1247373 15.7493961,19.1035608 C15.3779451,21.7451294 13.5395137,22.8732863 9.60288627,22.8732863 M9.60288627,26.0990118 C4.39378824,26.0990118 0.816062745,23.6864627 0.266415686,19.8019137 C0.1152,18.7076392 0.000376470588,14.6072471 0.000376470588,13.2726588 L0.00414117647,12.8397176 C0.0217098039,11.1129725 0.135278431,7.70716863 0.266415686,6.75720784 C0.814807843,2.87140392 4.39190588,0.456972549 9.60163137,0.455717647 L9.60790588,0.455717647 C13.4592,0.455717647 18.202102,1.54873725 18.9399843,6.75030588 L18.0822588,6.87203137 C17.5602196,3.18889412 14.7090824,1.3216 9.60790588,1.3216 L9.60163137,1.3216 C4.85621961,1.3228549 1.60727843,3.45116863 1.12414118,6.87642353 C0.987984314,7.86277647 0.866886275,11.8219922 0.866886275,13.2726588 L0.866886275,13.5688157 C0.880690196,15.2058353 0.996141176,18.7584627 1.12351373,19.6820706 C1.60790588,23.1054431 4.85684706,25.2331294 9.60288627,25.2331294 C14.7084549,25.2331294 17.5614745,23.3645804 18.0822588,19.6808157 C18.2246902,18.6517961 18.2535529,17.5456 18.2535529,16.2003451 L18.2535529,15.5114039 C18.2416314,13.6422275 17.5821804,12.4820706 14.3344941,12.4820706 L12.0292392,12.4820706 L12.0292392,11.6168157 L14.3344941,11.6168157 C17.6267294,11.6168157 19.1024941,12.8171294 19.1194353,15.5088941 L19.1194353,16.2003451 C19.1194353,17.5807373 19.0886902,18.7214431 18.9399843,19.8006588 C18.2027294,25.0059922 13.4560627,26.0990118 9.60288627,26.0990118" mask="url(#ga-logo-m2)"></path></g><path d="M158.933898,22.8732863 C155.221898,22.8732863 154.154604,20.8215216 153.912408,19.1004235 C153.768094,18.1247373 153.768094,17.2331294 153.768094,16.2003451 C153.768094,15.1675608 153.768094,14.2759529 153.913035,13.2971294 C154.154604,11.5791686 155.221898,9.52740392 158.933898,9.52740392 C160.854525,9.44144314 162.288251,9.82042353 163.187388,10.6549333 C164.02629,11.4336 164.062682,12.3283451 164.06331,12.3666196 C164.116643,12.9639529 164.126055,13.8599529 163.585192,14.4497569 C163.238839,14.8281098 162.727467,15.0201098 162.066133,15.0201098 L157.392251,15.0201098 L157.392251,14.1542275 L162.066133,14.1542275 C162.480878,14.1542275 162.768251,14.0601098 162.947075,13.8649725 C163.257035,13.5267765 163.240094,12.8761098 163.19931,12.4168157 C163.193035,12.3076392 163.03931,10.2100706 158.953349,10.3926588 C156.418447,10.3932863 155.056251,11.3834039 154.770133,13.4213647 C154.633976,14.3393255 154.633976,15.2020706 154.633976,16.2003451 C154.633976,17.1986196 154.633976,18.0613647 154.769506,18.9761882 C155.056251,21.0172863 156.418447,22.0080314 158.933898,22.0080314 C160.680722,22.0080314 162.01782,21.7965804 163.548173,21.2789333 L163.824878,22.0990118 C162.199153,22.6486588 160.782369,22.8732863 158.933898,22.8732863 M158.933898,26.0990118 C154.350369,26.0990118 151.280878,23.7448157 150.722447,19.8019137 C150.573741,18.7214431 150.542996,17.5807373 150.542996,16.2003451 C150.542996,14.8199529 150.573741,13.6792471 150.722447,12.6006588 C151.280878,8.65587451 154.350369,6.30167843 158.933898,6.30167843 C163.805427,6.30167843 166.779545,8.35846275 167.307859,12.0917961 C167.595859,13.885051 167.25829,15.4116392 166.331545,16.4990118 C165.357741,17.6416 163.749584,18.2458353 161.680878,18.2458353 L157.392251,18.2458353 L157.392251,17.3799529 L161.680878,17.3799529 C163.513663,17.3799529 164.857035,16.8949333 165.672722,15.9374431 C166.430055,15.0489725 166.699859,13.7639529 166.452016,12.221051 C166.125741,9.91140392 164.557114,7.16756078 158.933898,7.16756078 C154.820957,7.16756078 152.072094,9.24316863 151.579545,12.7198745 C151.437741,13.7488941 151.408251,14.8550902 151.408251,16.2003451 C151.408251,17.5456 151.437741,18.6517961 151.579545,19.6820706 C152.072094,23.1575216 154.820957,25.2331294 158.933898,25.2331294 C160.945506,25.2331294 162.655937,24.9972078 164.479937,24.4676392 L164.721506,25.2983843 C162.815937,25.8524235 161.030839,26.0990118 158.933898,26.0990118"></path><path d="M93.260549,22.8851451 C91.6015686,22.8851451 90.3422745,22.5030275 89.5265882,21.7456941 C88.6876863,20.9670275 88.6519216,20.0722824 88.6506667,20.0340078 C88.5973333,19.4366745 88.5879216,18.541302 89.1287843,17.9508706 C89.4751373,17.5725176 89.9865098,17.3805176 90.6478431,17.3805176 L95.3217255,17.3805176 L95.3217255,18.2464 L90.6478431,18.2464 C90.2337255,18.2464 89.945098,18.3411451 89.766902,18.5356549 C89.4563137,18.8744784 89.4745098,19.5245176 89.5146667,19.9831843 C89.5209412,20.0936157 89.6809412,22.1899294 93.7612549,22.0079686 C96.2961569,22.0079686 97.6577255,21.0172235 97.9444706,18.9792627 C98.0806275,18.061302 98.0806275,17.1985569 98.0806275,16.2002824 C98.0806275,15.2020078 98.0806275,14.3392627 97.945098,13.4238118 C97.6577255,11.3833412 96.2961569,10.3932235 93.7807059,10.3932235 C92.0332549,10.3932235 90.6967843,10.6040471 89.1664314,11.1216941 L88.889098,10.3016157 C90.5148235,9.75196863 91.9322353,9.52734118 93.7807059,9.52734118 C97.4920784,9.52734118 98.5593725,11.5791059 98.8015686,13.3002039 C98.9458824,14.2758902 98.9458824,15.167498 98.9458824,16.2002824 C98.9458824,17.2330667 98.9458824,18.1246745 98.8015686,19.103498 C98.5593725,20.8214588 97.4920784,22.8732235 93.7807059,22.8732235 C93.6031373,22.8813804 93.4293333,22.8851451 93.260549,22.8851451 M93.7807059,26.098949 C88.9079216,26.098949 85.9338039,24.0427922 85.4054902,20.3082039 C85.1181176,18.5155765 85.4556863,16.9883608 86.3824314,15.9016157 C87.3568627,14.7590275 88.9643922,14.1547922 91.0324706,14.1547922 L95.3217255,14.1547922 L95.3217255,15.0206745 L91.0324706,15.0206745 C89.2003137,15.0206745 87.8569412,15.5056941 87.0412549,16.4631843 C86.2839216,17.3510275 86.0141176,18.6366745 86.2619608,20.1795765 C86.5882353,22.4892235 88.1568627,25.2330667 93.7807059,25.2330667 C97.8936471,25.2330667 100.64251,23.1574588 101.134431,19.6807529 C101.276863,18.6517333 101.305725,17.5455373 101.305725,16.2002824 C101.305725,14.8550275 101.276863,13.7488314 101.134431,12.7185569 C100.64251,9.24310588 97.8936471,7.16749804 93.7807059,7.16749804 C91.7684706,7.16749804 90.0580392,7.40341961 88.2340392,7.93361569 L87.9924706,7.10224314 C89.8980392,6.54883137 91.6831373,6.30161569 93.7807059,6.30161569 C98.3642353,6.30161569 101.433725,8.65581176 101.991529,12.5987137 C102.140863,13.6791843 102.17098,14.8198902 102.17098,16.2002824 C102.17098,17.5806745 102.140863,18.7213804 101.992157,19.8005961 C101.433725,23.7447529 98.3642353,26.098949 93.7807059,26.098949"></path><g transform="translate(171.921569, 0.627451)"><mask id="ga-logo-m4" fill="white"><use href="#ga-logo-p3"></use></mask><path d="M8.70694902,25.4714353 C4.12341961,25.4714353 1.05392941,23.1172392 0.495498039,19.1743373 C0.339262745,18.0417882 0.316047059,16.6752 0.316047059,15.9617882 L0.316047059,0.25292549 L1.18192941,0.25292549 L1.18192941,15.9617882 C1.18192941,16.6532392 1.2038902,17.974651 1.35259608,19.0544941 C1.8451451,22.5299451 4.59400784,24.6055529 8.70694902,24.6055529 L8.70694902,25.4714353 Z" mask="url(#ga-logo-m4)"></path></g><g transform="translate(175.058824, 0.627451)"><mask id="ga-logo-m6" fill="white"><use href="#ga-logo-p5"></use></mask><path d="M5.56969412,22.2458353 C1.85832157,22.2458353 0.7904,20.1940706 0.548203922,18.4729725 C0.403890196,17.4972863 0.403890196,16.432502 0.403890196,15.4028549 L0.404517647,0.25305098 L1.26977255,0.25305098 L1.26977255,15.4028549 C1.26977255,16.4011294 1.26977255,17.4339137 1.40530196,18.3487373 C1.69204706,20.3898353 3.05424314,21.3805804 5.56969412,21.3805804 L5.56969412,22.2458353 Z" mask="url(#ga-logo-m6)"></path></g></g></svg>
```

## Volledige JS (`scripts/goudappel-web.js`)

```js
// Goudappel huisstijl voor webtools — opmaak en code: Tom Gerrits

// Tweetaligheid (NL | EN): teksten uit GA_I18N, keuze bewaard in localStorage
var GA_LANG_KEY = 'ga-lang';
var gaLangNu = null;
function gaGetLang() {
  if (!gaLangNu) { try { gaLangNu = localStorage.getItem(GA_LANG_KEY); } catch (e) {} }
  return gaLangNu === 'en' ? 'en' : 'nl';
}
function gaFindText(key) {
  var d = typeof GA_I18N !== 'undefined' ? GA_I18N : {};
  var lang = gaGetLang();
  if (d[lang] && d[lang][key] != null) return d[lang][key];
  if (d.nl && d.nl[key] != null) return d.nl[key];
  return null;
}
// gaT('sleutel') of gaT('sleutel', { n: 12 }) voor tekst met {n}
function gaT(key, vars) {
  var s = gaFindText(key);
  if (s == null) return key;
  return String(s).replace(/\{(\w+)\}/g, function (m, k) { return vars && vars[k] != null ? vars[k] : m; });
}
// gaL({ nl: '…', en: '…' }) kiest de tekst in de huidige taal; een gewone tekst blijft gelijk
function gaL(v) {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return v;
  var lang = gaGetLang();
  return v[lang] != null ? v[lang] : v.nl;
}
function gaApplyLang() {
  var lang = gaGetLang();
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(function (el) {
    var s = gaFindText(el.getAttribute('data-i18n'));
    if (s != null) el.textContent = s;
  });
  document.querySelectorAll('[data-i18n-attr]').forEach(function (el) {
    el.getAttribute('data-i18n-attr').split(';').forEach(function (pair) {
      var p = pair.split(':');
      var s = p.length === 2 ? gaFindText(p[1].trim()) : null;
      if (s != null) el.setAttribute(p[0].trim(), s);
    });
  });
  document.querySelectorAll('.ga-lang [data-lang]').forEach(function (b) {
    b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === lang));
  });
  document.dispatchEvent(new CustomEvent('ga-lang', { detail: { lang: lang } }));
}
function gaSetLang(lang) {
  gaLangNu = lang;
  try { localStorage.setItem(GA_LANG_KEY, lang); } catch (e) {}
  gaApplyLang();
}
document.addEventListener('click', function (e) {
  var b = e.target.closest('.ga-lang [data-lang]');
  if (b && b.getAttribute('aria-pressed') !== 'true') gaSetLang(b.getAttribute('data-lang'));
});
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', gaApplyLang);
else gaApplyLang();

// Versievenster en Contact-menu, gevuld uit tools-meta.js
// (TOOL_META, CHANGELOG, TOOL_CONTACTS en OTHER_TOOLS)
var GA_INFO_TXT = {
  nl: { info: 'Versie-informatie', version: 'Versie', date: 'Datum', description: 'Beschrijving',
        changes: 'Wijzigingen bekijken', changelog: 'Wijzigingen', back: 'Terug', others: 'Andere tools', close: 'Sluiten' },
  en: { info: 'Version information', version: 'Version', date: 'Date', description: 'Description',
        changes: 'View changes', changelog: 'Changes', back: 'Back', others: 'Other tools', close: 'Close' }
};
var gaInfoView = 'info';
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
  document.addEventListener('ga-lang', gaRenderToolInfo);
  gaRenderToolInfo();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', gaInitToolInfo);
else gaInitToolInfo();

// Datakleuren als lijst, voor grafiekbibliotheken. Leest --ga-data-1 t/m --ga-data-10.
function gaDataColors() {
  var st = getComputedStyle(document.documentElement), out = [];
  for (var i = 1; i <= 10; i++) out.push(st.getPropertyValue('--ga-data-' + i).trim());
  return out;
}

// Gereedschapspalet: modi zijn exclusief, schakelaars wisselen aan/uit
document.addEventListener('click', function (e) {
  var t = e.target.closest('.ga-palette .ga-tool');
  if (!t || t.disabled) return;
  if (t.hasAttribute('data-mode')) {
    t.closest('.ga-palette').querySelectorAll('[data-mode]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b === t));
    });
  } else if (t.hasAttribute('aria-pressed')) {
    t.setAttribute('aria-pressed', String(t.getAttribute('aria-pressed') !== 'true'));
  }
});

// Dropdownmenu's: openen/sluiten, klik ernaast en Escape sluiten
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

// Tabbladen: aria-selected wisselen
document.addEventListener('click', function (e) {
  var tab = e.target.closest('.ga-tab');
  if (!tab) return;
  tab.parentElement.querySelectorAll('.ga-tab').forEach(function (t) {
    t.setAttribute('aria-selected', String(t === tab));
  });
});

// Inklapbare zijpanelen: verticale tabs in een balk aan de buitenrand.
// Per balk is één paneel open; de toestand wordt per pagina bewaard in localStorage.
var GA_SIDE_SMAL = 760;
function gaSideKey(side) {
  return 'ga-side:' + location.pathname + ':' + (side.getAttribute('data-ga-side') || '');
}
function gaSideTabs(side) {
  return Array.prototype.slice.call(side.querySelectorAll('.ga-side__tab'));
}
// tab = de tab van het paneel dat open moet, of null om in te klappen
function gaSideOpen(side, tab, save) {
  gaSideTabs(side).forEach(function (t) {
    var on = t === tab;
    t.setAttribute('aria-expanded', String(on));
    var panel = document.getElementById(t.getAttribute('aria-controls'));
    if (panel) panel.hidden = !on;
  });
  side.classList.toggle('is-open', !!tab);
  // Smal scherm: een open paneel aan de andere kant klapt in (niet bewaren)
  if (tab && window.innerWidth < GA_SIDE_SMAL && side.parentElement) {
    side.parentElement.querySelectorAll(':scope > .ga-side.is-open').forEach(function (s) {
      if (s !== side) gaSideOpen(s, null, false);
    });
  }
  if (save) {
    try { localStorage.setItem(gaSideKey(side), tab ? tab.getAttribute('aria-controls') : ''); } catch (e) {}
  }
  side.dispatchEvent(new CustomEvent('ga-side', { bubbles: true, detail: { open: tab ? tab.getAttribute('aria-controls') : null } }));
}
// Begintoestand: bewaarde keuze, anders de tab met aria-expanded="true" in de HTML
function gaInitSides(root) {
  (root || document).querySelectorAll('.ga-side').forEach(function (side) {
    var saved = null, tab = null;
    try { saved = localStorage.getItem(gaSideKey(side)); } catch (e) {}
    gaSideTabs(side).forEach(function (t) {
      var match = saved != null ? t.getAttribute('aria-controls') === saved : t.getAttribute('aria-expanded') === 'true';
      if (match && !tab) tab = t;
    });
    gaSideOpen(side, tab, false);
  });
}
document.addEventListener('click', function (e) {
  var tab = e.target.closest('.ga-side__tab');
  if (!tab) return;
  gaSideOpen(tab.closest('.ga-side'), tab.getAttribute('aria-expanded') === 'true' ? null : tab, true);
});
// Pijltjes omhoog/omlaag, Home en End verplaatsen de focus tussen de tabs van een balk
document.addEventListener('keydown', function (e) {
  var tab = e.target.closest && e.target.closest('.ga-side__tab');
  if (!tab || ['ArrowUp', 'ArrowDown', 'Home', 'End'].indexOf(e.key) < 0) return;
  var tabs = gaSideTabs(tab.closest('.ga-side__bar')), i = tabs.indexOf(tab);
  i = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (i + (e.key === 'ArrowDown' ? 1 : -1) + tabs.length) % tabs.length;
  tabs[i].focus();
  e.preventDefault();
});
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { gaInitSides(); });
else gaInitSides();
```

## Volledige CSS (`styles/goudappel-web.css`)

```css
@import url("https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700;800&display=swap");

/* Versievenster */
.ga-info { width: 100%; margin-bottom: 16px; border-collapse: collapse; font-size: 14px; }
.ga-info th, .ga-info td { padding: 8px 0; border-bottom: 1px solid var(--ga-lijn); text-align: left; vertical-align: top; }
.ga-info th { width: 120px; padding-right: 12px; font-weight: 600; }
.ga-modal .ga-h3 { margin-top: 16px; }
.ga-changelog { margin-bottom: 16px; }
.ga-changelog .ga-row { margin-bottom: 4px; }
.ga-changelog .ga-list { margin: 0; font-size: 14px; }

/* Goudappel huisstijl voor webtools — gebaseerd op goudappel.nl
   Opgesteld door: Tom Gerrits */

:root {
  --ga-rood: #DE0058;
  --ga-rood-donker: #AB0144;
  --ga-rood-licht: #FFF4F4;
  --ga-tekst: #000000;
  --ga-tekst-2: #4B5159;
  --ga-rand: #746E73;
  --ga-lijn: #E8E7E8;
  --ga-vlak: #F6F6F6;
  --ga-placeholder: #A1A1A1;
  --ga-uit: #EFEFEF;
  --ga-focus-veld: #EE7EAA;
  --ga-focus: #0058DE;
  --ga-fout: #E63312;
  --ga-datmobility: #3FCFD5;

  --ga-font: "Open Sans", "Segoe UI", Arial, sans-serif;
  --ga-mono: Consolas, "Cascadia Mono", monospace;
  --ga-radius: 4px;
  --ga-pil: 9999px;
  --ga-schaduw: 0 0 15px 5px rgba(0, 0, 0, .04);
  --ga-schaduw-zwevend: 0 4px 16px rgba(0, 0, 0, .10);
  --ga-snel: 200ms ease;
  --ga-header-h: 40px;

  /* Ruimte: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 */
  --ga-s1: 4px;  --ga-s2: 8px;  --ga-s3: 12px; --ga-s4: 16px;
  --ga-s5: 24px; --ga-s6: 32px; --ga-s7: 48px; --ga-s8: 64px;
}
@media (min-width: 1140px) { :root { --ga-header-h: 44px; } }

*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0;
  font-family: var(--ga-font);
  font-size: 16px;
  line-height: 1.5;
  color: var(--ga-tekst);
  background: #fff;
  -webkit-font-smoothing: antialiased;
}
b, strong { font-weight: 800; }
a { color: var(--ga-rood); text-underline-offset: 3px; transition: color var(--ga-snel); }
a:hover { color: var(--ga-rood-donker); }
:focus-visible { outline: 2px solid var(--ga-focus); outline-offset: 3px; }
::selection { background: var(--ga-rood); color: #fff; }

/* Datakleuren voor grafieken en kaartklassen (grafiekvolgorde Goudappel) */
:root {
  --ga-data-1: #DE0058;  /* Goudappel rood */
  --ga-data-2: #E8E7E8;  /* Lichtgrijs */
  --ga-data-3: #4B5159;  /* Donkergrijs */
  --ga-data-4: #00A7E7;  /* Lichtblauw */
  --ga-data-5: #4F4757;  /* Grijs/paars */
  --ga-data-6: #53B151;  /* Groen */
  --ga-data-7: #394053;  /* Grijs/blauw */
  --ga-data-8: #6A757C;  /* Midgrijs */
  --ga-data-9: #FDC300;  /* Geel/oranje */
  --ga-data-10: #5A427E;  /* Paars */
}

h1, h2, h3, h4, .ga-h1, .ga-h2, .ga-h3 {
  margin: 0 0 .5em;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: -.5px;
  color: var(--ga-tekst);
}
h1, .ga-h1 { font-size: 28px; }
h2, .ga-h2 { font-size: 22px; }
h3, .ga-h3 { font-size: 18px; }
h4 { font-size: 16px; }
p { margin: 0 0 1em; }
.ga-small { font-size: 14px; }
.ga-muted { color: var(--ga-tekst-2); }

.ga-list { margin: 0 0 1em; padding: 0; list-style: none; }
.ga-list li { position: relative; padding: 2px 0 2px 24px; }
ul.ga-list li::before {
  content: ""; position: absolute; left: 4px; top: .7em;
  width: 4px; height: 4px; border-radius: 3px; background: var(--ga-rood);
}
ol.ga-list { counter-reset: ga-li; }
ol.ga-list li::before {
  counter-increment: ga-li; content: counter(ga-li);
  position: absolute; left: 2px; top: 4px;
  font-size: 12px; font-weight: 800; color: var(--ga-rood);
}

.ga-icon {
  width: 18px; height: 18px; flex: 0 0 auto;
  fill: none; stroke: currentColor; stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round;
}

.ga-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.ga-stack { display: flex; flex-direction: column; gap: 12px; }
.ga-container { max-width: 1236px; margin: 0 auto; padding: 0 20px; }
@media (min-width: 600px)  { .ga-container { padding: 0 40px; } }
@media (min-width: 1400px) { .ga-container { padding: 0 48px; } }
.ga-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }

.ga-header {
  position: sticky; top: 0; z-index: 100;
  display: flex; align-items: stretch; gap: 24px;
  height: var(--ga-header-h);
  padding: 0 20px;
  background: #fff;
  box-shadow: var(--ga-schaduw);
}
@media (min-width: 1140px) { .ga-header { padding: 0 48px; } }

.ga-header__logo { display: flex; align-items: center; flex: 0 0 auto; text-decoration: none; }
.ga-logo { display: block; width: 100px; height: auto; aspect-ratio: 182 / 32; }
@media (min-width: 1140px) { .ga-header__logo .ga-logo { width: 120px; } }

.ga-header__tool {
  display: flex; align-items: baseline; gap: 8px;
  align-self: center;
  padding: 2px 24px;
  border-left: 1px solid var(--ga-lijn);
  border-right: 1px solid var(--ga-lijn);
  white-space: nowrap;
}
.ga-header__title { font-size: 16px; font-weight: 700; line-height: 1.2; letter-spacing: -.3px; }
.ga-header__version {
  padding: 0; border: 0; background: none; text-align: left;
  font: 400 12px/1 var(--ga-font);
  color: var(--ga-tekst-2);
  cursor: pointer;
  transition: color var(--ga-snel);
}
.ga-header__version:hover { color: var(--ga-rood-donker); text-decoration: underline; text-underline-offset: 3px; }

.ga-nav { display: flex; align-items: stretch; gap: 16px; overflow-x: auto; scrollbar-width: none; }
.ga-nav a, .ga-nav button {
  position: relative;
  display: flex; align-items: center;
  margin: 0 8px; padding: 0;
  border: 0; background: none;
  font: 600 17px/1 var(--ga-font);
  color: var(--ga-tekst);
  text-decoration: none; white-space: nowrap;
  cursor: pointer;
  transition: color var(--ga-snel);
}
.ga-nav a::after, .ga-nav button::after {
  content: ""; position: absolute; left: 0; right: 0; bottom: 0;
  height: 2px; background: var(--ga-rood-donker);
  opacity: 0; transition: opacity var(--ga-snel);
}
.ga-nav a:hover, .ga-nav button:hover,
.ga-nav [aria-current="page"], .ga-nav .is-active { color: var(--ga-rood-donker); }
.ga-nav a:hover::after, .ga-nav button:hover::after,
.ga-nav [aria-current="page"]::after, .ga-nav .is-active::after { opacity: 1; }
.ga-nav :focus-visible { outline-offset: -2px; }

.ga-header__actions {
  display: flex; align-items: center; gap: 4px;
  align-self: center;
  margin-left: auto;
  padding-left: 16px;
  border-left: 1px solid var(--ga-lijn);
}
.ga-header__actions:empty { display: none; }

/* Rechts: Contact en NL | EN */
.ga-header__meta { display: flex; align-items: center; gap: 24px; flex: 0 0 auto; align-self: center; margin-left: auto; }
.ga-header__meta + .ga-header__actions { margin-left: 0; }
.ga-header__link {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 0; border: 0; background: none;
  font: 600 17px/1 var(--ga-font);
  color: var(--ga-tekst);
  cursor: pointer;
  transition: color var(--ga-snel);
}
.ga-header__link:hover, .ga-header__link[aria-expanded="true"] { color: var(--ga-rood-donker); }
.ga-contact[hidden] { display: none; }
.ga-contact .ga-dropdown__menu { left: auto; right: 0; min-width: 260px; }
.ga-contact__person { display: flex; flex-direction: column; gap: 2px; padding: 8px 10px 6px; }
.ga-contact__name { font-size: 15px; font-weight: 700; }
.ga-contact__role { font-size: 13px; color: var(--ga-tekst-2); }

.ga-lang { display: flex; align-items: center; gap: 4px; font: 600 17px/1 var(--ga-font); }
.ga-lang button {
  padding: 0; border: 0; background: none;
  font: inherit; color: var(--ga-tekst);
  text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 3px;
  cursor: pointer;
  transition: color var(--ga-snel);
}
.ga-lang button:hover, .ga-lang button[aria-pressed="true"] { color: var(--ga-rood-donker); }
.ga-lang button[aria-pressed="true"] { cursor: default; }

@media (max-width: 759px) {
  .ga-header { gap: 12px; }
  .ga-header__tool { padding: 2px 12px; }
  .ga-header__meta { gap: 16px; }
}
@media (max-width: 599px) {
  .ga-header__tool { display: none; }
  .ga-nav a, .ga-nav button { font-size: 15px; margin: 0 4px; }
  .ga-header__link, .ga-lang { font-size: 15px; }
}

/* Actieknop (website) */
.ga-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  min-width: 100px;
  padding: 10px 22px;
  border: 2px solid var(--ga-rood);
  border-radius: var(--ga-pil);
  background: var(--ga-rood);
  color: #fff;
  font: 600 16px/1.25 var(--ga-font);
  text-decoration: none;
  cursor: pointer;
  transition: all var(--ga-snel);
}
.ga-btn:hover { background: var(--ga-rood-donker); border-color: var(--ga-rood-donker); color: #fff; }
.ga-btn:disabled, .ga-btn[aria-disabled="true"] {
  opacity: .4; cursor: not-allowed; background: var(--ga-rood); border-color: var(--ga-rood);
}
.ga-btn--outline { background: #fff; color: var(--ga-rood); }
.ga-btn--outline:hover { background: var(--ga-rood-donker); border-color: var(--ga-rood-donker); color: #fff; }
.ga-btn--link {
  min-width: 0; padding-left: 0; padding-right: 0;
  background: transparent; border-color: transparent; color: var(--ga-rood);
}
.ga-btn--link:hover { background: transparent; border-color: transparent; color: var(--ga-rood-donker); text-decoration: underline; }
.ga-btn--sm { min-width: 0; padding: 5px 14px; font-size: 14px; }
.ga-btn .ga-icon { width: 16px; height: 16px; }

/* Kleine knop (tools) */
.ga-tool {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--ga-lijn);
  border-radius: var(--ga-radius);
  background: #fff;
  color: var(--ga-tekst);
  font: 600 14px/1 var(--ga-font);
  white-space: nowrap;
  cursor: pointer;
  transition: border-color var(--ga-snel), color var(--ga-snel), background var(--ga-snel);
}
.ga-tool:hover { border-color: var(--ga-rand); color: var(--ga-rood-donker); }
.ga-tool[aria-pressed="true"], .ga-tool.is-active {
  border-color: var(--ga-rood); background: var(--ga-rood-licht); color: var(--ga-rood-donker);
}
.ga-tool:disabled { opacity: .4; cursor: not-allowed; border-color: var(--ga-lijn); color: var(--ga-tekst); }
.ga-tool--icon { width: 32px; padding: 0; }
.ga-tool--sm { height: 26px; padding: 0 8px; font-size: 13px; }
.ga-tool--ghost { border-color: transparent; background: transparent; }
.ga-tool--ghost:hover:not([aria-pressed="true"]):not(:disabled) { border-color: transparent; background: var(--ga-vlak); }
.ga-tool--ghost:disabled { border-color: transparent; }

/* Tooltip: data-tip="Tekst" op een knop */
[data-tip] { position: relative; }
[data-tip]::after {
  content: attr(data-tip);
  position: absolute; left: 50%; top: calc(100% + 6px); z-index: 60;
  transform: translateX(-50%);
  padding: 4px 8px;
  border-radius: var(--ga-radius);
  background: var(--ga-tekst); color: #fff;
  font: 600 12px/1.3 var(--ga-font); letter-spacing: 0;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity 120ms ease;
}
[data-tip]:hover::after, [data-tip]:focus-visible::after { opacity: 1; transition-delay: 400ms; }

/* Eén kolom (standaard): geen titels, lijnen tussen de thema's, tooltip rechts */
.ga-palette {
  display: inline-flex; flex-direction: column; gap: 4px;
  padding: 4px;
  background: #fff;
  border: 1px solid var(--ga-lijn);
  border-radius: var(--ga-radius);
}
.ga-palette__group { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.ga-palette__group + .ga-palette__group { padding-top: 4px; border-top: 1px solid var(--ga-lijn); }
.ga-palette__title {
  position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
}
.ga-palette__tools { display: grid; grid-template-columns: 36px; gap: 2px; }
.ga-palette .ga-tool { width: 36px; height: 36px; }
.ga-palette .ga-icon { width: 20px; height: 20px; }
.ga-palette [data-tip]::after { left: calc(100% + 8px); top: 50%; transform: translateY(-50%); }

/* Twee kolommen: met themanaam boven elke groep, tooltip eronder */
.ga-palette--2kol { gap: 10px; padding: 10px 12px 12px; }
.ga-palette--2kol .ga-palette__group + .ga-palette__group { padding-top: 10px; }
.ga-palette--2kol .ga-palette__title {
  position: static; width: auto; height: auto; overflow: visible; clip: auto;
  text-align: center;
  font-size: 12px; font-weight: 800; letter-spacing: 1px; line-height: 1.3;
  text-transform: uppercase; color: var(--ga-tekst-2);
}
.ga-palette--2kol .ga-palette__tools { grid-template-columns: repeat(2, 36px); gap: 4px; }
.ga-palette--2kol [data-tip]::after { left: 50%; top: calc(100% + 6px); transform: translateX(-50%); }

.ga-palette--zwevend { border-color: transparent; box-shadow: var(--ga-schaduw-zwevend); }

.ga-field { margin-bottom: 16px; }
.ga-label { display: block; margin-bottom: 6px; font-weight: 600; font-size: 15px; }

.ga-input, .ga-select, .ga-textarea {
  width: 100%;
  height: 44px;
  padding: 8px 12px;
  border: 2px solid var(--ga-rand);
  border-radius: var(--ga-radius);
  background-color: #fff;
  color: var(--ga-tekst);
  font: 16px/1.25 var(--ga-font);
  transition: border-color var(--ga-snel);
}
.ga-textarea { height: auto; min-height: 120px; resize: vertical; line-height: 1.5; }
.ga-input:focus, .ga-select:focus, .ga-textarea:focus { outline: none; border-color: var(--ga-focus-veld); }
.ga-input::placeholder, .ga-textarea::placeholder { color: var(--ga-placeholder); }
.ga-input:disabled, .ga-select:disabled, .ga-textarea:disabled {
  background-color: var(--ga-uit); border-color: #7B848F; cursor: not-allowed;
}

.ga-select {
  appearance: none;
  padding-right: 40px;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  background-size: 16px;
}
.ga-select--filter {
  width: auto; max-width: 310px;
  border-radius: 1000px;
  padding-left: 22px; padding-right: 44px;
  background-position: right 18px center;
}

.ga-input--sm, .ga-select--sm { height: 32px; padding: 4px 8px; border-width: 1px; font-size: 14px; }
.ga-select--sm { padding-right: 30px; background-position: right 8px center; background-size: 14px; }

/* Uitklaplijst in huisstijl (Chrome en Edge); andere browsers tonen de standaardlijst */
@supports (appearance: base-select) {
  .ga-select, .ga-select::picker(select) { appearance: base-select; }
  .ga-select::picker-icon { display: none; }
  .ga-select:open { border-color: var(--ga-focus-veld); }
  .ga-select::picker(select) {
    margin-top: 4px;
    padding: 4px;
    background: #fff;
    border: 1px solid var(--ga-lijn);
    border-radius: var(--ga-radius);
    box-shadow: var(--ga-schaduw-zwevend);
  }
  .ga-select option {
    padding: 7px 10px;
    border-radius: 3px;
    font-size: 14px;
    color: var(--ga-tekst);
  }
  .ga-select option::checkmark { display: none; }
  .ga-select option:hover, .ga-select option:focus-visible {
    outline: none; background: var(--ga-rood-licht); color: var(--ga-rood-donker);
  }
  .ga-select option:checked { font-weight: 600; color: var(--ga-rood-donker); }
}

.ga-check { display: inline-flex; align-items: flex-start; gap: 8px; margin-right: 16px; cursor: pointer; }
.ga-check input { flex: none; width: 18px; height: 18px; margin: 2px 0 0; accent-color: var(--ga-rood); }

.ga-input.is-error, .ga-select.is-error, .ga-textarea.is-error { border-color: var(--ga-fout); }
.ga-field__error { margin: 6px 0 0; font-size: 14px; color: var(--ga-fout); }

.ga-dropdown { position: relative; display: inline-block; }
.ga-dropdown [data-ga-dropdown] .ga-icon:last-child { width: 14px; height: 14px; transition: transform var(--ga-snel); }
.ga-dropdown [aria-expanded="true"] .ga-icon:last-child { transform: rotate(180deg); }
.ga-dropdown__menu {
  position: absolute; top: calc(100% + 4px); left: 0; z-index: 50;
  min-width: 200px;
  padding: 4px;
  background: #fff;
  border: 1px solid var(--ga-lijn);
  border-radius: var(--ga-radius);
  box-shadow: var(--ga-schaduw-zwevend);
}
.ga-dropdown__menu[hidden] { display: none; }
.ga-dropdown__item {
  display: flex; align-items: center; gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border: 0; border-radius: 3px;
  background: none;
  color: var(--ga-tekst);
  font: 400 14px/1.4 var(--ga-font);
  text-align: left; text-decoration: none;
  cursor: pointer;
}
.ga-dropdown__item:hover, .ga-dropdown__item:focus-visible {
  outline: none; background: var(--ga-rood-licht); color: var(--ga-rood-donker);
}
.ga-dropdown__sep { margin: 4px 0; border: 0; border-top: 1px solid var(--ga-lijn); }

.ga-collapse {
  border: 1px solid var(--ga-lijn);
  border-radius: var(--ga-radius);
  background: #fff;
  overflow: hidden;
}
.ga-collapse + .ga-collapse { margin-top: 8px; }
.ga-collapse > summary {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 9px 12px;
  background: var(--ga-vlak);
  font-size: 15px; font-weight: 600;
  list-style: none;
  cursor: pointer;
  transition: color var(--ga-snel);
}
.ga-collapse > summary::-webkit-details-marker { display: none; }
.ga-collapse > summary::after {
  content: ""; flex: 0 0 auto;
  width: 7px; height: 7px; margin: 0 4px 4px 0;
  border-right: 2px solid currentColor; border-bottom: 2px solid currentColor;
  transform: rotate(45deg);
  transition: transform var(--ga-snel);
}
.ga-collapse[open] > summary::after { transform: rotate(-135deg); margin-bottom: -2px; }
.ga-collapse[open] > summary { border-bottom: 1px solid var(--ga-lijn); box-shadow: inset 3px 0 0 var(--ga-rood); }
.ga-collapse > summary:hover { color: var(--ga-rood-donker); }
.ga-collapse > summary:focus-visible { outline-offset: -2px; }
.ga-collapse__body { padding: 10px 12px 14px; font-size: 14px; }
.ga-collapse__body .ga-label { font-size: 14px; }
.ga-collapse__body .ga-stack { gap: 6px; }

.ga-tabs { display: flex; gap: 24px; box-shadow: inset 0 -2px 0 var(--ga-lijn); overflow-x: auto; overflow-y: hidden; }
.ga-tab {
  position: relative;
  padding: 10px 0;
  border: 0; background: none;
  color: var(--ga-tekst);
  font: 600 15px/1.2 var(--ga-font);
  white-space: nowrap;
  cursor: pointer;
  transition: color var(--ga-snel);
}
.ga-tab::after {
  content: ""; position: absolute; left: 0; right: 0; bottom: 0;
  height: 2px; background: transparent;
  transition: background var(--ga-snel);
}
.ga-tab:hover, .ga-tab[aria-selected="true"] { color: var(--ga-rood-donker); }
.ga-tab[aria-selected="true"]::after { background: var(--ga-rood-donker); }
.ga-tab:focus-visible { outline-offset: -2px; }

.ga-tag {
  display: inline-flex; align-items: center;
  padding: 4px 12px;
  background: var(--ga-rood); color: #fff;
  font-size: 12px; font-weight: 800; line-height: 1.3; letter-spacing: 1px;
  text-transform: uppercase;
}
.ga-tag--licht { background: var(--ga-rood-licht); color: var(--ga-rood-donker); }
.ga-tag--neutraal { background: var(--ga-lijn); color: var(--ga-tekst-2); }
.ga-meta { font-size: 14px; color: var(--ga-tekst-2); }

.ga-lines {
  display: block; width: 72px; height: 15px; margin-bottom: 16px;
  border-top: 3px solid var(--ga-rood); border-bottom: 3px solid var(--ga-rood);
}
.ga-lines--datmobility { border-color: var(--ga-datmobility); }

.ga-panel {
  display: block;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid var(--ga-lijn);
  border-radius: var(--ga-radius);
}
.ga-panel > :last-child { margin-bottom: 0; }
.ga-panel--zwevend { border-color: transparent; box-shadow: var(--ga-schaduw-zwevend); }

.ga-card { color: inherit; text-decoration: none; transition: transform 250ms ease-in-out, box-shadow 250ms ease-in-out; }
.ga-card:hover { color: inherit; transform: translateY(-4px); box-shadow: var(--ga-schaduw); }
.ga-card .ga-tag { margin-bottom: 8px; }
.ga-card .ga-h3 { margin-bottom: 4px; transition: color var(--ga-snel); }
.ga-card:hover .ga-h3 { color: var(--ga-rood-donker); }

.ga-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.ga-table th, .ga-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--ga-lijn); }
.ga-table th {
  position: sticky; top: 0;
  background: #fff;
  font-weight: 600;
  border-bottom: 2px solid var(--ga-tekst-2);
}
.ga-table .ga-num { text-align: right; font-variant-numeric: tabular-nums; }
.ga-table tbody tr:hover td { background: var(--ga-vlak); }
.ga-table tr.is-selected td { background: var(--ga-rood-licht); }

.ga-overlay {
  position: fixed; inset: 0; z-index: 1000;
  display: none; align-items: center; justify-content: center;
  padding: 16px;
  background: rgba(0, 0, 0, .5);
}
.ga-overlay.is-open { display: flex; }
.ga-modal {
  position: relative;
  width: 100%; max-width: 520px;
  max-height: calc(100vh - 32px); overflow: auto;
  padding: 24px 28px;
  background: #fff;
  border-radius: var(--ga-radius);
  box-shadow: var(--ga-schaduw-zwevend);
}
.ga-modal__close { position: absolute; top: 12px; right: 12px; }
.ga-modal .ga-h2 { padding-right: 32px; }
.ga-modal__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; }

.ga-toast {
  position: fixed; left: 50%; bottom: 24px; z-index: 2000;
  max-width: calc(100vw - 32px);
  padding: 10px 18px;
  background: var(--ga-tekst); color: #fff;
  border-radius: var(--ga-radius);
  font-size: 15px; font-weight: 600;
  opacity: 0; pointer-events: none;
  transform: translate(-50%, 12px);
  transition: opacity var(--ga-snel), transform var(--ga-snel);
}
.ga-toast.is-visible { opacity: 1; transform: translate(-50%, 0); }
.ga-toast--fout { background: var(--ga-fout); }

.ga-app { display: flex; height: calc(100vh - var(--ga-header-h)); }

/* Inklapbare zijpanelen: balk met verticale tabs aan de buitenrand, paneel ernaast */
.ga-side { display: flex; flex: 0 0 auto; min-height: 0; background: #fff; }
.ga-side--rechts { flex-direction: row-reverse; }
.ga-side__bar {
  display: flex; flex-direction: column; gap: 2px;
  flex: 0 0 32px; width: 32px;
  padding: 8px 0;
  border-right: 1px solid var(--ga-lijn);
  overflow-y: auto;
}
.ga-side--rechts .ga-side__bar { border-right: 0; border-left: 1px solid var(--ga-lijn); }
.ga-side__tab {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  width: 100%; padding: 12px 0;
  border: 0; background: none;
  color: var(--ga-tekst);
  font: 600 14px/1 var(--ga-font);
  cursor: pointer;
  transition: color var(--ga-snel), background var(--ga-snel);
}
.ga-side__tab > span { writing-mode: vertical-rl; white-space: nowrap; }
.ga-side__tab .ga-icon { flex: 0 0 auto; width: 16px; height: 16px; transition: transform var(--ga-snel); }
.ga-side__tab:hover { color: var(--ga-rood-donker); background: var(--ga-vlak); }
.ga-side__tab[aria-expanded="true"] { color: var(--ga-rood-donker); background: var(--ga-rood-licht); box-shadow: inset 3px 0 0 var(--ga-rood); }
.ga-side--rechts .ga-side__tab[aria-expanded="true"] { box-shadow: inset -3px 0 0 var(--ga-rood); }
.ga-side__tab:focus-visible { outline-offset: -2px; }
/* Het pijltje wijst de kant op waarheen het paneel gaat bij een klik */
.ga-side--links .ga-side__tab[aria-expanded="true"] .ga-icon,
.ga-side--rechts .ga-side__tab[aria-expanded="false"] .ga-icon { transform: rotate(180deg); }

.ga-side__panel {
  display: flex; flex-direction: column;
  flex: 0 0 auto;
  width: var(--ga-side-w, 320px);
  min-width: min-content;   /* groeit mee met de inhoud: geen horizontale scrollbalk */
  max-width: 50vw;
  padding: 16px 20px 0;
  border-right: 1px solid var(--ga-lijn);
  overflow-y: auto;
}
.ga-side--rechts .ga-side__panel { border-right: 0; border-left: 1px solid var(--ga-lijn); }
.ga-side__panel[hidden] { display: none; }
.ga-side__panel > :last-child:not(.ga-app__actions) { margin-bottom: 16px; }
/* Inhoud houdt haar hoogte: is het paneel te hoog, dan scrolt het paneel
   in plaats van dat secties (overflow: hidden) worden platgedrukt */
.ga-side__panel > *, .ga-app__sidebar > * { flex-shrink: 0; }
/* Een onderdeel breder dan een half scherm (grote tabel) scrolt zelf */
.ga-side__breed { max-width: calc(50vw - 72px); overflow-x: auto; }

/* Vast zijpaneel (oude indeling, zonder tabbalk) */
.ga-app__sidebar {
  display: flex; flex-direction: column;
  flex: 0 0 320px;
  padding: 16px 20px 0;
  border-right: 1px solid var(--ga-lijn);
  overflow-y: auto;
}
.ga-app__actions {
  position: sticky; bottom: 0;
  margin-top: auto;
  padding: 12px 0 16px;
  background: #fff;
}
.ga-app__main { flex: 1 1 auto; min-width: 0; }

.ga-workspace { position: relative; display: flex; flex-direction: column; background: var(--ga-vlak); }
.ga-workspace__canvas { flex: 1 1 auto; min-height: 0; position: relative; display: flex; flex-direction: column; }
.ga-workspace__canvas > .ga-empty { flex: 1 1 auto; }
.ga-workspace > .ga-palette { position: absolute; top: 12px; left: 12px; z-index: 10; }

.ga-statusbar {
  display: flex; flex-wrap: wrap; gap: 4px 20px;
  padding: 6px 12px;
  background: #fff;
  border-top: 1px solid var(--ga-lijn);
  font-size: 13px; color: var(--ga-tekst-2);
}

@media (max-width: 759px) {
  /* Inklapbare panelen: zo breed als past, de tab blijft bereikbaar; scrollen alleen als noodoplossing */
  .ga-side__panel { min-width: 0; max-width: calc(100vw - 64px); overflow-x: auto; }
  .ga-side__breed { max-width: none; }
  /* Vast zijpaneel: boven het werkvlak */
  .ga-app:has(> .ga-app__sidebar) { flex-direction: column; height: auto; }
  .ga-app__sidebar { flex-basis: auto; border-right: 0; border-bottom: 1px solid var(--ga-lijn); }
  .ga-app:has(> .ga-app__sidebar) .ga-workspace { min-height: 70vh; }
}

/* Kaart (Leaflet) en bronvermelding */
.ga-map { width: 100%; height: 100%; min-height: 300px; background: var(--ga-vlak); font-family: var(--ga-font); }
.ga-map .leaflet-control-attribution {
  padding: 2px 6px;
  background: rgba(255, 255, 255, .85);
  font-size: 11px; line-height: 1.4;
  color: var(--ga-tekst-2);
}
.ga-map .leaflet-control-attribution a { color: var(--ga-tekst-2); text-decoration: underline; }

.ga-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px;
  height: 100%; min-height: 160px;
  padding: 32px 16px;
  text-align: center;
  font-size: 14px; color: var(--ga-tekst-2);
}
.ga-empty > .ga-icon { width: 32px; height: 32px; margin-bottom: 4px; color: var(--ga-rand); }
.ga-empty p { margin: 0; }
.ga-empty .ga-empty__title { font-size: 16px; font-weight: 600; color: var(--ga-tekst); }
.ga-empty .ga-tool { margin-top: 8px; }

.ga-loading { display: inline-flex; align-items: center; gap: 10px; font-size: 14px; color: var(--ga-tekst-2); }
.ga-spinner {
  width: 18px; height: 18px; flex: 0 0 auto;
  border: 2px solid var(--ga-lijn); border-top-color: var(--ga-rood);
  border-radius: 50%;
  animation: ga-spin 800ms linear infinite;
}
@keyframes ga-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .ga-spinner { animation-duration: 2s; } }
```
