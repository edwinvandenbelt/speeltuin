# Plan: 4 stress-lagen (auto / fiets-CROW / fiets-Mekuria / voetganger)

Vier onafhankelijke stress-lagen die per wegvak een **stress-score 1–4** (+ `stressClass`)
berekenen, geëxposeerd als OGC-collecties + deck.gl-lagen. Basisgeometrie = het
**autonetwerk** (`NETWORK-CAR`), verrijkt met wegenscan-uitkomsten, OSM/BGT fiets- en
voetpaden, en kruispunt-/oversteek-kenmerken.

```
NETWORK-CAR ──┐
              ├─(join spectrumId)─ WEGENSCAN ──┐
TRAFFIC-ASSETS├─(spatial snap)─ fiets/voetpaden├─► stress-engine ─► 4 collecties
   (punten)   └─(spatial join node)─ oversteken┘   (car / bike-CROW / bike-Mekuria / ped)
```

Buiten scope (later): `count × stress`-prioritering (od2net-stijl).

---

## DEEL A — Verzoek aan de gmt-library (wijzigingen in de invoerbestanden)

> Wegenscan blijft **ongemoeid** (aparte geojson). Nodes en de fiets/voet-koppeling doet de
> speeltuin zelf. Onderstaande wijzigingen betreffen alleen `NETWORK-*.parquet` en
> `TRAFFIC-ASSETS.parquet`.

### A1. `NETWORK-{MODE}.parquet` — nieuwe kolommen + 1 bevestiging

| Kolom        | Type          | Status               | Omschrijving |
| ------------ | ------------- | -------------------- | ------------ |
| `speedLimit` | int (km/u)    | **nieuw, verplicht** | Wettelijke maximumsnelheid per wegvak (NWB of OSM `maxspeed`). Nu is er alleen model-`speed` (freeflow) en `highway`. |
| `gradient`   | double (%)    | **nieuw, verplicht** | Gemiddelde helling in voorwaartse richting per wegvak (hoogtemodel/AHN of OSM). Ontbreekt nu volledig. |
| `flow24hrs`  | double        | **bevestiging**      | Bevestig: motorvoertuigen per etmaal, **beide** rijrichtingen samen? Zo niet: lever `aadt` (mvt/etmaal, beide richtingen) als expliciet veld. |

Optioneel (niet blokkerend): `lit` (bool), `surface` (string) per wegvak.

### A2. `TRAFFIC-ASSETS.parquet` — fiets-/voetpaden als lijn-features

Voeg **`LineString`-features** toe (het bestand bevat nu alleen Point + Polygon):

| `assetType` | Geometrie  | Bron |
| ----------- | ---------- | ---- |
| `cyclePath` | LineString | OSM `highway=cycleway` / `cycleway=*`, of BGT |
| `footPath`  | LineString | OSM `highway=footway/path/pedestrian` / `sidewalk=*`, of BGT |

Met per feature deze attributen:

| Attribuut    | Type                                     | Omschrijving |
| ------------ | ---------------------------------------- | ------------ |
| `pathType`   | enum (`separated`/`lane`/`bus`/`shared`) | Soort voorziening |
| `width`      | double (m)                               | Breedte |
| `oneway`     | bool                                     | Eenrichting |
| `segregated` | bool                                     | Fiets/voet gescheiden op zelfde pad |
| `surface`    | string                                   | Verharding |
| `lit`        | bool                                     | Verlichting |

> **Geen `alongLinkId` nodig** — de koppeling aan het autonetwerk doet de speeltuin ruimtelijk.

### A3. Bestaande punt-assets — alleen bevestiging

`pedestrianCrossing`, `trafficSignal`, `giveWay`, `stopSign` blijven ongewijzigd. Enig
verzoek: zorg dat hun coördinaat **op/dicht bij het kruispunt** ligt, zodat de
node-toewijzing (straal ~20 m) klopt.

---

## DEEL B — Speeltuin (eigen werk)

### B1. Node-graaf opbouwen
- Topologisch uit `NETWORK-CAR` `fromNode`/`toNode` + geometrie-eindpunten → node-tabel met
  `nodeId`, coördinaat, `degree`, aanliggende `linkId`s + hun `lanes`/`speedLimit`.
- Punt-assets toewijzen via **nearest-node ≤ 20 m** (anders negeren).
- **In-memory** herberekenen per stress-run (geen apart bestand).

### B2. Wegenscan runtime-join
- `WEGENSCAN-{MODE}.geojson` joinen op `spectrumId` (fallback `linkId`) → o.a.
  `generic_safety`, `profile`, `separation`, `bicycle_location`, `pedestrian_location`,
  `parking_location`, `max_speed`, `speed_bumps`.
- **NL-only**: daarbuiten defaults + OSM-fallback (`highway`, `speedLimit`, TRAFFIC-ASSETS).

### B3. OSM-supplement uit TRAFFIC-ASSETS
- `cyclePath`/`footPath`-lijnen **ruimtelijk** snappen (buffer + hoek-match) aan het
  dichtstbijzijnde auto-`linkId` → per wegvak `cyclewayType/width/oneway` en
  `sidewalkType/width`.
- Punt-assets → nodes (B1): `nodeControl` (`signalized`/`priority`/`roundabout`/
  `uncontrolled`), `crossingType` (`zebra`/`signalized`/`island`/`unmarked`), `lanesToCross`.

### B4. Rotondes
- Heuristisch afleiden uit de netwerkgeometrie (geen expliciet veld).

### B5. Vier stress-engines
Elk een los, testbaar `GeoJSON → GeoJSON`-module (patroon van `noise_estimator`/
`emission_estimator`), output `stress` 1–4 + `stressClass`, met LTS-drempels als
**expliciete, apart bewerkbare configuratietabel**.

1. **`car_stress`** — mapt wegenscan `generic_safety` (GOED…SLECHT) → 1–4; context
   `speedLimit`/`aadt`.
2. **`bike_stress_crow`** — nieuwste CROW-systematiek (Ontwerpwijzer fietsverkeer /
   CROW Fietsberaad): voorziening × snelheidsregime × intensiteit + kruispunt-term.
   Drempeltabel te kalibreren op de CROW-bron zodra beschikbaar.
3. **`bike_stress_mekuria`** — Mekuria BLTS-tabel (od2net-variant): `cyclewayType` ×
   `speedLimit` × `lanes` × parkeren + kruispunt-stress → max(segment-LTS, kruispunt-LTS).
4. **`ped_stress`** — trottoir (`sidewalkType`/`width`/buffer=`separation`) × `speedLimit`
   × `aadt` × `lanes` + oversteek-term (`crossingType`/`lanesToCross`).

### B6. Server / OGC / frontend
- Vier nieuwe OGC-collecties + `stress`-proces(sen) in `server.py` (naast `wegenscan`),
  async job-patroon hergebruiken.
- Output per area: `{area}-STRESS-{CAR|BIKE_CROW|BIKE_MEKURIA|PED}.geojson`.
- deck.gl `GeoJsonLayer` met 4-kleuren stress-schaal + laagkeuze in de UI; koppelbaar aan de
  bestaande `comparison`-flow.

---

## Vastgelegde keuzes
- **Node-bron**: topologisch (`fromNode`/`toNode`). **Asset→node**: nearest-node ≤ 20 m.
  **Opslag**: in-memory.
- **Rotondes**: heuristisch.
- **CROW**: nieuwste Ontwerpwijzer fietsverkeer; drempels als config, te kalibreren op de
  aangeleverde tabel.
- **Wegenscan**: ongemoeid, runtime joinen.
- **`alongLinkId`**: niet beschikbaar → ruimtelijke snap in de speeltuin.

## Openstaand
- CROW-drempeltabel uit de nieuwste Ontwerpwijzer aanleveren voor exacte kalibratie
  (anders beargumenteerde eerste versie, later bij te stellen zonder codewijziging).
- Bevestiging `flow24hrs`-semantiek door de gmt-library.
</content>
</invoke>
