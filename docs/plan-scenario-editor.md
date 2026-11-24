# Plan: scenario-editor (prototype)

Nieuwe derde webapplicatie, consistent met `digital-twin/` en `analyzer/`: zelfde
skelet (Flask OGC-API-laag, `index.html` + `scripts/main.js` + `scripts/tools-meta.js`
+ `styles/goudappel-web.css`/`main.css`), werkend op dezelfde `work/<areaId>/...`
bestanden. Doel: een scenario kiezen (zelfde startscherm-patroon als digital-twin),
dan in een bewerkingsdeel wegen, bomen, gebouwen en lantaarnpalen aanpassen, en na
opslaan automatisch een nieuwe toedeling draaien wanneer het netwerk gewijzigd is.

## Architectuurkeuzes

- Map `scenario-editor/`, default poort **5002** (digital-twin=5001, analyzer=5000).
- `server.py` is afgeleid van `digital-twin/server.py`: zelfde OGC-laag
  (`/collections`, `/processes`, `/jobs`), zelfde collecties (`areas`, `network`,
  `zones`, `buildings`, `vegetation`, `changes`) plus één nieuwe collectie
  `streetlights`.
- Scenario-startscherm = hergebruik van digital-twin's "geen `AREA_ID`"-tak
  (area-tree via `srcAreaId`, lichte overzichtskaart, klik → `/?areaId=...`).
- Wegen bewerken = 1-op-1 hergebruik van bestaande code (`openLinkDialog`,
  link-tekenen, `/processes/adjust/execution`) — dit werkt al en triggert nu al
  een route-herberekening; dat blijft de "toedeling" voor wegwijzigingen.
- Gebouwen/bomen/lantaarnpalen zijn nieuw en volgen een eigen wijzigingskanaal
  (`pendingChanges` per domein), die samen met eventuele netwerkwijzigingen in
  één nieuw OGC-proces `edit_scenario` worden verwerkt tot een nieuw scenario
  (`new_area_id`), net zoals `adjust` dat nu al doet voor wegen.
- Productie/attractie komt als **apart per-gebouw veld** op de buildings-collectie
  (niet als overschrijving van de bestaande zone-CBS-waarden — die koppeling naar
  zone-aggregatie valt buiten dit prototype).

## Fase 0 — Scaffold

- [ ] Map `scenario-editor/` aanmaken: `server.py` (afgeleid van digital-twin),
      `index.html`, `scripts/main.js` (afgeleid van digital-twin: boot, `AREA_ID`,
      startscherm/area-tree, kaart-init, wegen-editing ongewijzigd overgenomen),
      `scripts/tools-meta.js` (eigen naam/versie, `OTHER_TOOLS` naar digital-twin
      + analyzer), `styles/` (kopie, eigen accentkleur).
- [ ] `start.bat`, `deploy.ps1`, `Dockerfile`, `requirements.txt` naar analogie,
      default poort 5002.
- [ ] Kort `README.md`: wat het is, hoe starten, URL-parameters.
- **Stop voor test/akkoord:** app start, toont bestaand startscherm met scenario's,
  klikken opent kaart met werkende wegen-editing (ongewijzigd hergebruikt).

## Fase 1 — Gebouwen bewerken

- [ ] Server: `edit_scenario`-inputs voor building-overrides (`wallColor`,
      `roofColorPitched`, `roofColorFlat`, `productie`, `attractie`); schrijft
      nieuw `BUILDINGS`-bestand voor het nieuwe scenario.
- [ ] Client: klik-op-gebouw dialoog (kleurkiezers + 2 numerieke velden),
      apart `buildingChanges`-kanaal, optimistische weergave op de kaart.
- **Stop voor test/akkoord.**

## Fase 2 — Bomen bewerken

- [ ] Server: `vegetationChanges` verwerken → nieuw `VEGETATION`-bestand
      (bestaande features aanpassen + nieuwe puntfeatures toevoegen).
- [ ] Client: klik-op-boom dialoog (hoogte, kroonbreedte, soort), plaats-tool
      voor nieuwe boom, verwijderen.
- **Stop voor test/akkoord.**

## Fase 3 — Lantaarnpalen (nieuwe collectie, end-to-end)

- [ ] Server: nieuw bestandstype `STREETLIGHTS` + collectie-registratie
      (`_COLLECTIONS`/`_COLLECTION_FILE_TYPE`), leeg startbestand per scenario.
- [ ] Server: `streetlightChanges` verwerken in `edit_scenario`.
- [ ] Client: puntlaag renderen, plaats/bewerk/verwijder-tool, eigen icoon.
- **Stop voor test/akkoord.**

## Fase 4 — Eén "Toepassen"-knop + nieuwe toedeling

- [ ] `edit_scenario` registreren in `_PROCESS_DESCRIPTIONS` + dispatch,
      jobs-polling zoals bij `adjust`.
- [ ] Bij netwerkwijzigingen: hergebruik `adjust_core`/`run_pipeline` +
      `recompute_routes_for_pairs` (bestaande toedeling); bij uitsluitend
      gebouw/boom/lantaarnpaal-wijzigingen: alleen bestanden wegschrijven.
- [ ] Client: verzamel alle change-kanalen, één POST, navigeer na succes naar
      `/?areaId=<new_area_id>`.
- **Stop voor integraal testen** (wegen + gebouw + boom + lantaarnpaal in één run).

## Fase 5 — Afronding

- [ ] Renderbugs reproduceren via headless Chrome-aanpak.
- [ ] README/changelog (`tools-meta.js`) bijwerken.
