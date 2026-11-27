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

- [ ] **Stap 1 — Toolbar-knop, dialoog en volledige JS-wiring (NL)**
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

- [ ] **Stap 2 — CSS-fijnslijpen**
  - Eventuele visuele correcties naar aanleiding van de test in Stap 1.
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
