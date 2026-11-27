# Plan: Evenementen toevoegen aan de aanpassingen-lijst (analyzer) — #30

## Context

De `adjust`-package (gmt-adjustment-pipeline, zie `.venv/Lib/site-packages/adjust/core/adjust_core.py`)
ondersteunt al volledig een **event-adjustment**: een tijdelijke, tijdgebonden
productie/attractie op een knoop of zone (`_split_changes`, `_validate_event_adjustment`,
`apply_event_adjustments`). Shape van zo'n wijziging:

```json
{
  "nodeId": "123",           // óf "zoneId": "456" — precies één van beide
  "arrival":   { "date": "2026-06-01", "startTime": "14:00", "endTime": "18:00" },  // optioneel
  "departure": { "date": "2026-06-01", "startTime": "22:00", "endTime": "23:00" },  // optioneel — minstens 1 van arrival/departure
  "attraction": "+2000",     // verplicht als "arrival" aanwezig is
  "production": "+1800",     // verplicht als "departure" aanwezig is
  "avgDistanceKm": 25
}
```

`server.py` (`_execute_adjust`) stuurt de `changes`-array ongewijzigd door naar
`_adjust_run_pipeline` — er is **geen backend-wijziging nodig**, alleen een
front-end feature in `analyzer/index.html` + `analyzer/scripts/main.js` om zo'n
entry via de UI samen te stellen en toe te voegen aan `pendingChanges`, net als
de bestaande knoop- en zone-explode-wijzigingen.

Referentiepatroon in de huidige code: de zone-explode-feature (knop
`zoneExplodeBtn`, dialoog `#zoneExplodeDialog`, state `zoneExplodeActive`,
functies `openZoneExplodeDialog`/`closeZoneExplodeDialog`, handler
`zoneExplodeDialogOk`, en de takken in `renderChangesList()` /
`highlightChange()` / `serializeChange()` voor `c._isZoneExplode`).

## Stappen

- [x] **Stap 1 — Toolbar-knop, dialoog en volledige JS-wiring (NL)**
  - Nieuwe knop `eventEditBtn` in `index.html` (Aanpassingen-paneel, naast
    `zoneExplodeBtn`), eigen icoon.
  - Nieuw dialoogblok `#eventDialog` in `index.html` (na `#zoneExplodeDialog`):
    twee optionele secties **Aankomst** (datum, starttijd, eindtijd, attractie)
    en **Vertrek** (datum, starttijd, eindtijd, productie), plus één veld
    **Gemiddelde reisafstand (km)**.
  - In `scripts/main.js`:
    - State `eventEditActive`, opgenomen in alle bestaande mutual-exclusivity-
      plekken (waar nu `nodeEditActive`/`zoneExplodeActive` elkaar uitzetten).
    - Klik-op-knoop/zone-handler: bij `eventEditActive` → `openEventDialog`.
    - `openEventDialog` / `closeEventDialog`, inclusief vooraf invullen bij een
      bestaande wijziging op diezelfde knoop/zone.
    - OK-handler: validatie (minstens aankomst of vertrek aangevinkt; attractie
      verplicht bij aankomst, productie verplicht bij vertrek; afstand > 0),
      pusht entry met `_isEvent: true` naar `pendingChanges`.
    - `renderChangesList()`: samenvattingslabel voor `c._isEvent`.
    - `highlightChange()`: controleren of de bestaande fallback (zoekt op
      `zoneId`/`nodeId`) volstaat, zo niet een expliciete tak toevoegen.
    - `serializeChange()`: schone payload (`nodeId`/`zoneId`, `arrival`/
      `departure`, `attraction`/`production`, `avgDistanceKm`) voor de API-call.
    - Nederlandse i18n-strings (`TRANSLATIONS.NL`) voor knop, dialoog en
      wijzigingen-label.
  - CSS in `styles/main.css`: `#eventDialog` toevoegen aan de bestaande gedeelde
    selectors van de andere dialogen; kleine aanvullende stijl voor de twee
    subsecties.
  - **Stop hier voor test/akkoord door gebruiker in de browser.**

- [x] **Tussenstap — Wizard geïntegreerd in het Aanpassingen-blok i.p.v. los dialoogvenster**
  - De evenement-dialoog liep bij een klik dicht bij de vensterrand makkelijk
    buiten beeld (floating `position:absolute` bij het klikpunt, net als
    `#nodeDialog`/`#zoneExplodeDialog`). Omgebouwd naar een vast inline
    sub-paneel `#eventWizardPopup` binnen `#editPanelBody`, net als
    `#nodeSelectPopup`/`#linkSelectPopup`: toont een wachttekst ("Klik een
    knoop of zone…") tot er geklikt wordt, vult dan de velden met de
    geselecteerde knoop/zone.
  - "Andere selectie" (voorheen Annuleren) zet de wizard terug naar de
    wachtstand zonder de aanpassing-modus te verlaten.
  - Na "Toevoegen" wordt de evenement-toevoegmodus automatisch weer
    uitgeschakeld (knop + node-laag + paneel), zoals gevraagd.
  - **Stop voor test/akkoord.**

- [x] **Tussenstap — "Tot" op de volgende dag + Attractie kopiëren naar Productie**
  - Per tijdvak (aankomst/vertrek) een checkbox "Eindigt de volgende dag"
    toegevoegd; indien aangevinkt wordt een `endDate` (datum + 1 dag) aan het
    venster-object toegevoegd. `adjust_core._validate_event_adjustment`
    controleert alleen op de aanwezigheid van `date`/`startTime`/`endTime` en
    laat extra sleutels ongemoeid — geverifieerd dat een venster met
    `endDate` nog steeds geldig gevalideerd wordt.
  - Attractie wordt live gekopieerd naar Productie zolang de gebruiker
    Productie niet zelf heeft aangepast (per sessie/selectie); bij het openen
    van een bestaand evenement met een eigen Productie-waarde wordt dat gedrag
    uitgezet, zodat een bewuste afwijkende waarde niet wordt overschreven.
    Productie blijft te allen tijde los wijzigbaar.
  - **Stop voor test/akkoord.**

- [x] **Stap 2 — CSS-fijnslijpen**
  - Dialoog krijgt `max-height`/`overflow-y:auto` (veiligheidsnet bij kleine vensters).
  - Visuele scheiding tussen Aankomst/Vertrek-secties (dunne lijn) en een
    lichte inspringing/linker-accentlijn voor de velden onder elke sectie-
    checkbox, zodat duidelijk is welke velden bij welke sectie horen.
  - Datum/tijd-invoervelden iets compacter (`font-size`/`padding`) zodat twee
    tijdvelden naast elkaar prettig passen in de 300px-brede dialoog.
  - Scheidingslijn boven het (gedeelde) afstandsveld.
  - **Stop voor akkoord.**

- [ ] **Stap 3 — Engelse en Finse vertalingen**
  - Dezelfde strings toevoegen aan `TRANSLATIONS.EN` en `TRANSLATIONS.FI`.
  - **Stop voor test/akkoord.**

- [ ] **Stap 4 — Weergave van historische (server-side) event-wijzigingen**
  - In `renderChangesList()`'s historische sectie (`_historicalChanges`): een
    tak toevoegen zodat een opgeslagen event-wijziging (herkenbaar aan
    `arrival`/`departure`) een nette samenvatting krijgt i.p.v. in de
    node/zone-fallback te vallen.
  - **Stop voor test/akkoord.**
