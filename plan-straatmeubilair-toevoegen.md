# Plan: Straatmeubilair toevoegen (lantaarnpaal, bushokje, etc.)

Doel: dezelfde handmatige plaatsingsmodus als "Boom toevoegen" (commit 178037d),
maar dan voor straatmeubilair. De 3D-rendering (`_taFurnMeshes` /
`makeFurnitureLayers` in `main.js:7640-7809`) en het automatisch ophalen uit OSM
bestaan al (`assetType` via `/collections/traffic_assets/items`); er ontbreekt
alleen de "klik op de kaart om te plaatsen + opslaan"-workflow.

Types (bestaande assetType-waarden, al gerenderd): `mailbox` (brievenbus),
`busShelter` (bushokje), `mast`, `streetLight` (lantaarnpaal), `bikeGate`
(fietssluis), `infoBoard` (infobord), `trashBin` (prullenbak).

Opslag: `{areaId}-TRAFFIC-ASSETS.parquet` (geoparquet, i.t.t. de GeoJSON
VEGETATION-file bij bomen) — nieuwe features krijgen `src: "manual"` en worden
via `write_traffic_assets_atomic` (uit het geïnstalleerde
`prepare.core.traffic_asset_sources`-pakket) atomair toegevoegd aan de
bestaande features, zonder het bronnenregister van de fetchbare bronnen te
verstoren.

## Stappen

- [x] **1. index.html** — toolbar-knop `furnitureAddBtn` (naast `treeAddBtn`)
      + sub-paneel `furnitureAddPopup` met 7 type-knoppen, hint, teller,
      opslaan/wis-knoppen, statusregel. Toevoegen aan maquette-/follow-mode
      hide-lijsten (in main.css).
- [x] **2. main.js (i18n + state)** — NL/EN teksten
      (`furnitureAddBtnTitle`, `furnitureAddPanelTitle`,
      `furnitureType<Type>Label/Title`, hint/teller/opslaan-teksten);
      state (`furnitureAddActive`, `furnitureAddType`, `_furnitureAddPending`).
- [x] **3. main.js (render + plaatsen)** — pending features meerenderen in
      `makeFurnitureLayers()` (zelfde aanpak als `_vegTreeFeatures.concat(_treeAddPending)`
      bij bomen, met de bestaande oriëntatiemodus per type: along/across/none);
      `_addPendingFurniture(lng, lat)`, map-click handler, cursor.
- [x] **4. main.js (knoppen + opslaan)** — toggle-knop met wederzijdse
      uitsluiting t.o.v. de andere edit-modi (incl. `treeAddBtn` en vice versa);
      bij activeren automatisch het "Straatmeubilair"-vinkje aanzetten;
      `_saveFurnitureAddPending()` → POST naar nieuwe server-endpoint, daarna
      `loadTrafficAssetsInView()` opnieuw.
- [x] **5. server.py** — nieuwe route `POST /traffic-assets/furniture`:
      valideert Point-features + toegestane `assetType`, vindt/maakt het
      TRAFFIC-ASSETS-parquet-bestand (zelfde resolutielogica als het
      bbox-ophalen: `_traffic_assets_owner` / `_find_prepared_with_base_fallback`),
      voegt features toe met `src: "manual"`, schrijft atomair, spiegelt naar S3
      indien actief.
- [x] **6. main.css** — stijl voor `#furnitureAddPopup` (hergebruikt bestaande
      `.tree-ctrl-btn` / `.sim-opt-btn`-achtige klassen waar mogelijk i.p.v.
      dupliceren).
- [ ] **7. Handmatige check** — server starten, boom- én meubilair-plaatsing
      naast elkaar testen (plaatsen, zichtbaar vóór opslaan, opslaan, na reload
      nog aanwezig).

Ga ik akkoord krijgen om te starten met stap 1?
