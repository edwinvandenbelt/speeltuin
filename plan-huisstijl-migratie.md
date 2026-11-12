# Consequenties Goudappel-huisstijl voor analyzer & digital-twin

## Context

Er is een nieuwe huisstijlgids binnengekomen: `Goudappel_huisstijl_webtools (6).md` (v1.6.0, 2026-11-03, Tom Gerrits). Die beschrijft hoe elke Goudappel-webtool eruit moet zien en werken (kopbalk, kleuren, componenten, tweetaligheid, versie-info/contact). De vraag is wat dit betekent voor de twee bestaande tools in deze repo — **analyzer** en **digital-twin** — en wat er concreet moet veranderen.

Beide tools zijn onderzocht (read-only). Belangrijkste constatering vooraf: dit is geen kleine CSS-tweak. Beide tools zijn **monolithische single-file apps** (analyzer: 15.392 regels `index.html`, digital-twin: 20.774 regels `index.html`), met alle CSS en JS inline, geen CSS-variabelenlaag, geen bundler, en gedeelde code via `common/js/` (`left-menu-panel.js`, `montreal-basemap.js`, `animated-water.js`) die **beide tools tegelijk raakt**.

Vastgestelde beslissingen (met opdrachtgever afgestemd):
- **Fins (FI) blijft behouden** naast de verplichte NL|EN-wissel in de kopbalk. Dit is een bewuste afwijking van het vaste NL|EN-patroon uit de gids, gemotiveerd door bestaande gebruikers.
- De **bestaande i18n-infrastructuur wordt hergebruikt**, niet opnieuw gebouwd: beide tools hebben al een werkend systeem (`TRANSLATIONS`-object met NL/EN/FI, `T(key)`-functie, `data-i18n`/`data-i18n-title`/`data-i18n-ph` attributen, taalkeuze in `localStorage['ui-lang']`). Dit zit nu alleen verstopt (`display:none`) in een instellingenpaneel i.p.v. zichtbaar in een kopbalk.

## Huidige staat (beide tools, vergelijkbaar patroon)

| Aspect | Analyzer | Digital-twin | Gids vereist |
|---|---|---|---|
| Kopbalk | Geen; branding in teal (`#00a5ab`) balkje bovenin sidebar (`.lmp-header`) | Geen; branding in groene balkje bovenin sidebar (`#leftMenuHeader`) | Vaste witte `ga-header`: logo, naam+versie, menu, Contact, NL\|EN |
| Kleuren | ~300+ hardcoded hex-literals, geen `:root`-variabelen. Merk-kleuren nu teal + magenta (`#de0058` toevallig al Goudappel-rood) | Zelfde probleem; `#49a748` ("Goudappel-groen") staat er als losse code-comment, niet gesystematiseerd | `--ga-rood` etc. als CSS-variabelen, rood als accent, rest zwart/grijs/wit |
| Lettertype | Segoe UI (systeemfont) | Segoe UI (systeemfont) | Open Sans (Google Fonts) |
| Iconen | Unicode-emoji (🚗🚲🚶⚙) + losse inline SVG's, geen sprite | Zelfde patroon | GA icon-sprite, één keer na `<body>`, `.ga-tool`/`.ga-icon` |
| Zijpaneel | Eén vast links paneel, accordion-stijl (`.lmp-block`), in-/uitklapbaar via margin-offset | Zelfde patroon (`#leftMenuPanel`/`.lmp-block`) | Verticale-tab-balk aan schermrand, meerdere panelen/kanten mogelijk, `ga-side`-event |
| Gereedschap | Zwevende pil-toolbar (`#toolbar`), modus/schakelaar-knoppen al aanwezig | Toolbar grotendeels gemigreerd naar sidebar, `display:none`-restje | `.ga-palette`, gegroepeerd per thema, in kolom |
| Kaart | MapLibre GL 5.24 + deck.gl 8.9, basemaps: OpenFreeMap, Esri World Imagery, 3D BAG — **geen PDOK** | Zelfde stack | Leaflet 1.9.4 + PDOK BRT Grijs/Luchtfoto (met verplichte bronvermelding) |
| Tweetaligheid | Werkt (NL/EN/FI), dekking onvolledig, wissel verborgen | Werkt (NL/EN/FI), dekking onvolledig, wissel verborgen | Zichtbare NL\|EN-wissel in kopbalk, volledige dekking |
| Versie/contact | Niets aanwezig | Niets aanwezig | `tools-meta.js` met `TOOL_META`/`TOOL_CONTACTS`/`CHANGELOG`, verplicht |
| Componenten (knoppen, tabellen, dialogen, dropdowns) | Allemaal custom, per instantie eigen CSS, geen gedeelde classes | Zelfde | `.ga-btn`, `.ga-table`, `.ga-modal`, `.ga-dropdown`, `.ga-select` |
| Build | Geen bundler, statische bestanden, Flask serveert direct | Zelfde | Statische `styles/`- en `scripts/`-bestanden (past op huidige aanpak) |

## Belangrijkste consequenties per onderdeel van de gids

1. **Kopbalk (Vast).** Moet nieuw gebouwd worden — er is nu geen bovenbalk, alleen een gekleurde strip in het zijpaneel. De strip-inhoud (home-knop, titel, instellingen-tandwiel) verhuist deels naar de nieuwe kopbalk (toolnaam+versie, Contact, NL\|EN\|FI), deels blijft functioneel in het zijpaneel (instellingen-opening).

2. **Kleuren & CSS-variabelen.** Grootste en risicovolste klus: er bestaat geen variabelenlaag, dus een paletwissel is geen simpele find-replace. Voorstel: eerst `:root`-variabelen (`--ga-rood` t/m `--ga-data-10`) invoeren, dan de ~300+ hardcoded hexwaarden per stuk vervangen. Cruciaal onderscheid: **interfacekleuren** (knoppen, randen, actieve status) vs **datakleuren** (snelheid/flow-rampen, diff-plots, simulatiekleuren zoals rood/groen voor verkeerslichten) — alleen interfacekleuren volgen de huisstijl 1-op-1, datakleuren mogen afwijken (gids: "Afwijken mag... bij datakleuren") maar gebruiken bij voorkeur wel `--ga-data-*` waar dat past.

3. **Lettertype.** Open Sans toevoegen via Google Fonts-link, Segoe UI vervangen. Risico: layout-metrics (knopbreedtes, tabel-kolommen) kunnen verschuiven bij een ander lettertype — visueel checken nodig.

4. **Iconen.** Emoji/ad-hoc SVG's vervangen door de GA-sprite + `.ga-tool`-knoppen. De bestaande verkeersbordensprite (`common/data/traffic_sign_sprite`) is kaartdata, geen UI-chrome, en blijft ongemoeid.

5. **Zijpaneel-structuur.** Het huidige accordion-zijpaneel (`.lmp-block`) past qua *inhoud* prima in het nieuwe GA-patroon (de `<details class="ga-collapse">`-aanpak lijkt al sterk op wat er nu gebeurt), maar de **buitenkant** moet om: een smalle verticale-tab-balk aan de schermrand i.p.v. de huidige margin-offset-animatie. Omdat dit in `common/js/left-menu-panel.js` zit, raakt een wijziging **beide tools tegelijk** — dit moet gecoördineerd, niet los per tool.

6. **Gereedschapspalet.** De bestaande modus/schakelaar-logica (`data-mode`/`aria-pressed` idee zit er impliciet al in) sluit goed aan bij het GA-patroon — vooral een restyling/regroepering + icoon-vervanging, geen herontwerp van het gedrag.

7. **Kaart/achtergrondkaarten — aanbevolen afwijking.** De gids gaat uit van Leaflet + PDOK. Beide tools draaien op MapLibre GL + deck.gl voor vectortiles, 3D-gebouwen (3D BAG) en complexe overlays — dat teruglopen naar Leaflet zou functionaliteit kosten (met name voor digital-twin's 3D-aspect). Dit valt onder de gids-clausule "Afwijken mag waar het werk erom vraagt, zoals bij kaartlagen": **voorstel is MapLibre/deck.gl te behouden**, en waar haalbaar PDOK BRT Grijs/Luchtfoto als extra achtergrondoptie toe te voegen naast de bestaande OpenFreeMap/Esri-lagen, met bronvermelding conform de gids (rechtsonder, exacte copyright-tekst, wisselend met de gekozen achtergrond).

8. **Tweetaligheid.** Geen nieuwbouw, wel verplaatsing: de bestaande `TRANSLATIONS`/`T()`/`data-i18n`-aanpak blijft, wordt gekoppeld aan een zichtbare NL\|EN\|FI-wissel in de kopbalk, en de nu onvolledige `data-i18n`-dekking (met name nieuwere dialogen/debugpaneel) wordt aangevuld.

9. **Versie-info en contact.** Volledig nieuw (ontbreekt nu in beide tools): `tools-meta.js` per tool met `TOOL_META` (naam, versie, datum, beschrijving) en `TOOL_CONTACTS` (naam/rol/e-mail/telefoon — gegevens bij de opdrachtgever opvragen, niet verzinnen). Laag risico, duidelijke winst.

10. **Componenten (knoppen/tabellen/dialogen/dropdowns).** Analyzer heeft 7 custom dialogen, digital-twin 7 vergelijkbare — stuk voor stuk omzetten naar `.ga-modal`/`.ga-btn`/`.ga-dropdown`. Mechanisch werk, maar met grote oppervlakte (veel plekken) en dus veel regressiekans.

11. **Monoliet-risico.** Omdat alles inline in één HTML-bestand van 15k/20k regels staat, is grootschalig herstylen in-place risicovol (moeilijk te reviewen, makkelijk iets te breken in bestaande 3D/kaart-state). Voorstel: als eerste stap de inline `<style>`/`<script>`-blokken uitsplitsen naar losse bestanden volgens het gids-sjabloon (`styles/goudappel-web.css`, `styles/main.css`, `scripts/goudappel-web.js`, `scripts/i18n.js`, `scripts/tools-meta.js`, `scripts/main.js`) — dit is toch al wat de gids verwacht, en maakt de daaropvolgende kleurwissel beter review-baar.

## Aanbevolen fasering (uitvoering, stap voor stap met akkoord per stap)

- [x] **Fase 0 — vastleggen scope:** dit document als uitgangspunt, opgeslagen in de repo-root.
- [x] **Fase 1 — ontvlechten (analyzer):** inline CSS/JS uitgesplitst naar `styles/main.css`/`scripts/main.js`, zonder visuele wijziging. Geverifieerd.
- [x] **Fase 2 — fundament (analyzer):** `styles/goudappel-web.css` (GA-variabelen, Open Sans, volledige componenten-CSS) + sprite toegevoegd, `'Segoe UI'` → `var(--ga-font)`. Geverifieerd.
- [x] **Fase 3 — kopbalk (analyzer):** `ga-header` gebouwd (logo, titel, nav, instellingenknop), oude `.lmp-header`-strip verwijderd, layout-hoogtes doorgerekend. Geverifieerd.
- [x] **Fase 4 — kleurwissel (analyzer):** interfacekleuren (~300 plekken, CSS + inline HTML-styles) naar GA-variabelen; datakleuren/statuslichten/Goudappel-groen (map-data) bewust uitgezonderd. Geverifieerd.
- [x] **Fase 5 — zijpaneel (analyzer):** op uitdrukkelijk verzoek GEEN tabbalk-patroon — alleen `.lmp-block`-accordions en de bestaande schuif-tab (`#leftMenuPanelToggle`) herstyled, inklapbaar gedrag ongewijzigd. Geverifieerd.
- [x] **Fase 6 — gereedschapspalet & iconen (analyzer):** het oorspronkelijke `#toolbar`-element bleek dood (permanent `display:none`) en is met rust gelaten; 12 echte, zichtbare icoon-knoppen (upload, plus/minus, sluiten, vinkje) omgezet naar de GA-sprite. Geverifieerd.
- [x] **Fase 7 — componenten (analyzer):** dialogen/popovers visueel herstyled (GA-schaduw, radius, geen overlay/positionering gewijzigd), radius-sweep door de hele app (~75 plekken), groen→rood voor 'toevoegen'-acties, groen/rood-statuslichten en data-legenda's bewust ongemoeid. Geverifieerd.
- [x] **Fase 8 — tweetaligheid (analyzer):** NL\|EN\|FI zichtbaar en werkend in de kopbalk (hergebruikt bestaande i18n-systeem), plus een beperkte dekkingssweep (5 zijpaneel-sectietitels alsnog vertaald). Geverifieerd.
- [x] **Fase 9 — versie & contact (analyzer):** `scripts/tools-meta.js` met echte gegevens (Edwin van den Belt, Business developer, evdbelt@dat.nl), versieknop + Contact-dropdown in de kopbalk, volledig vertaald (NL/EN/FI). Geverifieerd.
- [~] **Fase 10 — achtergrondkaarten (analyzer):** OVERGESLAGEN op verzoek van de gebruiker (2026-11-11). PDOK-opties worden niet toegevoegd; bestaande OpenFreeMap/Esri-achtergronden blijven ongewijzigd.
- [x] **Fase 11 — herhalen voor digital-twin (2026-11-11/12):** fase 1–9 toegepast, exact hetzelfde pad als analyzer, op uitdrukkelijk verzoek van de gebruiker. Maquette-functionaliteit (fysieke schaalmodel-opstelling, `maquette-calibration.js`/`maquette-monitor.js`) bewust volledig buiten beschouwing gelaten — gebruiker overweegt dit naar een aparte applicatie te verplaatsen. Fase 10 ook hier overgeslagen. Alle fases geverifieerd:
  - Fase 1 (ontvlechten): `styles/main.css`/`scripts/main.js` uitgesplitst.
  - Fase 2 (fundament): `styles/goudappel-web.css` + sprite + Open Sans.
  - Fase 3 (kopbalk): `ga-header` gebouwd, oude `#leftMenuHeader`-strip verwijderd.
  - Fase 4 (kleurwissel): standaardmapping + oranje/groen→rood in de bewerk-workflow meteen meegenomen (lessen uit analyzer's nasleep-correctie). Tussentijds gevonden en gefixt: een inline SVG-klokwijzer (`#simClockHand`, `stroke="#00a5ab"`) die buiten de CSS/JS-sweep viel, plus een bijbehorende volledige inline-kleuren-check van `index.html`.
  - Fase 5 (zijpaneel): `.lmp-block`-restyle + schuif-tab-restyle, geen tabbalk. (Digital-twin heeft geen geneste `.lmp-network-block`-variant zoals analyzer.)
  - Fase 6 (iconen): `#toolbar` ook hier dood bevestigd; 15 icoon-knoppen omgezet naar de GA-sprite (geen `measureSetBtn`/📦 aanwezig in dit tool, verder gelijk aan analyzer).
  - Fase 7 (componenten): dialoog-schaduw/radius-token + volledige radius-sweep + `.tb-badge`-cirkel-fix.
  - Fase 8 (tweetaligheid): NL\|EN\|FI zichtbaar in de kopbalk; 6 sectietitels (Simulatie/Aanpassingen/Analyse/Netwerk/Pand weergave/3D weergave) + "Kaart"-link alsnog vertaald (incl. een gevonden-en-gefixte "navKaart"-tekstbug).
  - Fase 9 (versie & contact): `scripts/tools-meta.js` met dezelfde contactpersoon (Edwin van den Belt), versie "2026.11.12".

## Verificatie

- Na elke fase: visueel controleren via headless Chrome + CDP tegen de lokale server (bestaande werkwijze in dit project), met `127.0.0.1` i.p.v. `localhost` (voorkomt DNS-vertraging).
- Check specifiek dat kaart-state (MapLibre/deck.gl lagen, 3D-gebouwen) na CSS/layout-wijzigingen nog correct resized/redrawt (equivalent van Leaflet's `invalidateSize()` — bij MapLibre is dat `map.resize()`).
- Check dat de datakleur-ramps (snelheid/flow/diff) ongemoeid blijven na de interfacekleur-sweep.
- Geen bestaande geprepareerde data (`work/`-parquets) aanraken — dit is puur frontend.

## Openstaande vragen voor opdrachtgever/eigenaar

- Contactgegevens (naam, rol, e-mail, telefoon) voor `TOOL_CONTACTS` — niet zelf verzinnen.
- Akkoord op de voorgestelde afwijking: MapLibre/deck.gl behouden i.p.v. Leaflet+PDOK (functioneel noodzakelijk voor 3D/vector-features).
- Akkoord op FI als derde taaloptie naast de verplichte NL\|EN.
