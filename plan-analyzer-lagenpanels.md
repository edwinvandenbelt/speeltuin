# Plan: analyzer – 'Netwerk' opsplitsen in 5 panels + lagen voor verharding, breedte en stoepen

## Context

In het linker menu van de analyzer (`analyzer/index.html`) staat nu één blok 'Netwerk' met
alle kaartlagen onder elkaar (losse `<span>`-kopjes). Het wordt te lang en er komen lagen bij:
verharding, breedteklassen en stoepen (sinds gmt_network_enrichment 0.6.0 staan `surface`,
`sidewalkLeft/Right` en de WKD-breedtes op de links). 'Veiligheid' is nu één laag
(`generic_safety`), terwijl de wegenscan per link 22 losse KPI's levert (`props.safety[key]`).

Doel: vijf panels **Verkeer, Veiligheid, Geluid, Uitstoot, Inrichting**, elk met zijn eigen lagen;
Veiligheid krijgt het totaal plus alle 22 KPI's als losse lagen; de nieuwe lagen komen in
Inrichting. Er is altijd maximaal één laag tegelijk zichtbaar.

## Gekozen visualisatie (afgestemd)

- **Accordeon**: vijf losse `.lmp-block`s; er staat er hooguit één open. Een ander panel openen
  klapt het vorige dicht (alleen binnen deze vijf; Analyse, Zone/Pand productie blijven los).
- Alle radio's houden `name="lmpMetric"` → de browser zorgt al dat er maar één aan staat.
- Ingeklapt panel met de actieve laag: kop krijgt een accentstreep (`#de0058`) en rechts de
  naam van de actieve laag in klein grijs, zodat je ook dichtgeklapt ziet wát er aanstaat.
- **Uitzetten**: nogmaals klikken op de actieve radio → `none`. De losse 'Geen'-regel vervalt.
- Legenda blijft in de bestaande `#legendStrip` onderaan; categorale lagen krijgen daar
  kleurvakjes met labels (generaliseren van de bestaande `speed_intersections`-code).
- Veiligheid **gegroepeerd**: Totaal, dan kopjes Wegvak / Voetganger / Fiets / Parkeren & bus / Overig.

## Lagen per panel

| Panel | Lagen (waarde in `#colorMetric`) |
|---|---|
| Verkeer | flow, flow_scaled, occupancy, occupancy_scaled, coverage, coverage_scaled, speed, capacity |
| Veiligheid | `safety` (totaal) + `safety:<kpi>` voor de 22 keys uit `KPI_LABELS` (index.html ~7857) |
| Geluid | noise_lden, noise_lnight |
| Uitstoot | emis_co2, emis_nox, emis_pm10 |
| Inrichting | priority_roads, speed_crossings, speed_intersections, speed_yield, speed_refuge, speed_from_right, speed_left_turn, speed_oncoming, speed_elevation, **surface_class**, **width_class**, **sidewalks** |

Veiligheid-groepen:
- Wegvak: functional_usage, longitudinal_marking, directional_separation, lane_width, road_width, road_surface, speed_bumps, roadside_damage
- Voetganger: pedestrian_facility, pedestrian_width, pedestrian_crossing
- Fiets: bicycle_facility, bicycle_width, bicycle_crossing, bike_speed, bike_usage, bike_parking
- Parkeren & bus: parking_facility, parking_location, bus_stop_facility, bus_location
- Overig: social_interaction

Nieuwe lagen (categoraal, kleur per klasse, grijs = onbekend):
- **Verharding** (`surface_class`): klasse via de bestaande tabel in `common/js/montreal-basemap.js`
  (`_surfaceClass`) → exporteren als `surfaceClass`. Eigen, duidelijk onderscheidbare kleuren
  (asfalt donkergrijs, klinkers terracotta, beton lichtblauwgrijs, halfverhard oker, onverhard bruin, onbekend lichtgrijs).
- **Breedte** (`width_class`): totale wegbreedte zoals Kaart 2: (min+max)/2, anders `roadWidthM×2`;
  **zonder gemeten breedte → onbekend** (geen lanes-schatting). Klassen < 4 · 4–5,5 · 5,5–7 · 7–9 · ≥ 9 m (sequentieel).
- **Stoepen** (`sidewalks`): `sidewalkLeft/Right` (`yes`/`separate` = aanwezig, `no` = niet) →
  geen / links / rechts / beide / onbekend (beide null). Links/rechts t.o.v. rijrichting van de link.
- Safety-KPI's: zelfde 4 kleuren als `kpiColor()`/`safetyToRgba()` (GOED/REDELIJK/MATIG/SLECHT) + NVT grijs.

## Aanpak (bestanden)

`analyzer/index.html` (hoofdwerk), `common/js/montreal-basemap.js` (export `surfaceClass`).

1. **Markup** (~2214-2252): blok 'Netwerk' vervangen door vijf `.lmp-block`s met
   `data-block="layers-<cat>"` en klasse `lmp-layer-block`; kopjes als `<div class="lmp-subhead">`.
   Veiligheid-KPI-radio's dynamisch genereren uit `KPI_LABELS` + groepsdefinitie (geen 22× markup).
   `#colorMetric` krijgt de nieuwe `<option>`s (KPI-opties ook dynamisch), want de radio↔select-sync
   (~4248) vereist dat elke waarde als optie bestaat.
2. **CSS**: `.lmp-subhead`, accentstreep/actief-label in `.lmp-block-header` (`.lmp-active-name`).
3. **Gedrag** (~4241-4267): accordeon voor `.lmp-layer-block`; nogmaals-klik-op-actieve → `none`;
   functie `syncLayerPanels()` die radios, actieve-kop en label bijwerkt; aanroepen bij `change` én na
   de programmatische resets naar `flow` (~12986, ~14239, ~14257), die nu geen event sturen.
4. **Safety-KPI's**: helper `isSafetyMetric(m)` (`m==='safety' || m.startsWith('safety:')`) en die
   gebruiken op de plekken die nu `=== 'safety'` testen (change-handler ~14203 → wegenscan laden/banner,
   kaartklik ~10984 → wegenscanpaneel, `makeNetworkLayer` ~8838, tooltip ~8656, legenda ~5487).
   Kleur: `wegenscanByLinkId.get(id).safety[key]` → 4-klassen-RGBA.
5. **Nieuwe lagen in render**: in `evalMetric` (~8106) de klasse teruggeven; in `makeNetworkLayer`
   (~8838) een generieke categorale tak via één tabel `CATEGORICAL_LAYERS = {metric: {classOf(p), colors, labels}}`
   (ook gebruikt voor safety-KPI's). Tooltip (`_segTipRender` ~8607) toont klasse + ruwe waarde.
6. **Legenda** (`updateLegend` ~5330): categorale tak generiek maken op basis van `CATEGORICAL_LAYERS`
   (en `speed_intersections` daarin opnemen); `metricMeta` en `legendKeyMap` aanvullen.
7. **i18n** (NL ~2695, EN ~2969, FI ~3229): panelnamen, groepkopjes, nieuwe laagnamen en klassen,
   ontbrekende `legendSafety`. KPI-namen NL uit `KPI_LABELS`; EN/FI vertalingen toevoegen.

Niet in scope: split-view `makeNetworkLayer2` (heeft nu ook geen safety), `analyzer/test-deploy/`.

## Werkwijze

Bij start uitvoering: dit plan als `plan-analyzer-lagenpanels.md` in de repo-root zetten met
checkboxes per stap hieronder, en per stap stoppen voor akkoord.

- [x] 1. Markup + CSS + accordeon/sync-gedrag (bestaande lagen, nog zonder nieuwe)
- [x] 2. Veiligheid: KPI-lagen (render, legenda, tooltip, klik)
- [x] 3. Inrichting: verharding, breedte, stoepen (+ export `surfaceClass`)
- [x] 4. i18n NL/EN/FI
- [ ] 5. Testen

## Verificatie

- Server starten (`analyzer/start.bat`), openen via `http://127.0.0.1:…` (niet `localhost`).
- Goor (heeft `surface`/sidewalks) en Deventer (oudere data → verharding/stoepen 'onbekend').
- Accordeon: één panel open; actieve-laag-label op ingeklapt panel; dubbelklik zet laag uit.
- Elke laag één keer aan: kaartkleur, legenda (vakjes/gradient), tooltip.
- Veiligheid zonder wegenscan-data → banner 'Wegenscan uitvoeren'; met data alle 22 KPI's.
- Programmatische reset naar `flow` (scenario wisselen, compare uit) → radio/kop volgen mee.
- Taal wisselen NL/EN/FI: kopjes, labels en legenda vertaald.
