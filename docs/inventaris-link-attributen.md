# Inventarisatie: link-attributen in de GMP-speeltuin

Doel: alle attributen die ergens in de keten (PBF/OSM-enrichment, NWB/WKD,
wegenscan, digital-twin, analyzer) aan een netwerk-link hangen, als basis voor
de "klik op een link → popup met alle attributen"-functie in `scenario-editor/`.

**Methode**: grep/read door `digital-twin/`, `analyzer/`, `common/`, de
inhoud van `gmt_network_core`, `gmt_network_enrichment`, `gmt_routing`,
`gmt_shared` en `wegenscan` (uitgepakt uit de wheels in de repo-root), en één
voorbeeld-`NETWORK-CAR.parquet` uit `work/`.

## Belangrijk: wat "gericht" en "weg-breed" betekenen in deze codebase

Het netwerk wordt **bidirectioneel opgehaald** (één record per fysieke weg,
met `*_heen`/`*_terug`-velden, zie `gmt_network_core.network_fetcher`) en
daarna door de `bidirectional_splitter` **gesplitst in twee gerichte
link-features** (voorwaarts/terug), elk met hun eigen `linkId` (de terugkant
krijgt een negatieve id) en hun eigen geometrie (omgekeerd).

De OSM-verrijking (`road_enricher_core.py`) maakt dit onderscheid expliciet in
code via twee constanten:

- `UNDIRECTED_ATTRS` — gestemd **per wegvak** (`wvkIds`), identiek voor beide
  rijrichtingen.
- `DIRECTED_ATTRS` — gestemd **per wegvak + rijrichting**, dus verschillend
  per gerichte link.

**Links/rechts-attributen (`...Left`/`...Right`) zijn al naar rijrichting
georiënteerd** (`_oriented()` in `osm_tags.py`): ze staan dus wél als los veld
per gerichte link, maar betekenen "links/rechts van de rijrichting van déze
link" — niet links/rechts van de OSM-weg. Voor een UI die één link toont is
dit de juiste interpretatie; voor "beide richtingen moeten consistent zijn"
betekent het dat `cyclewayLeft` van de voorwaartse link gelijk moet zijn aan
`cyclewayRight` van de terugkant (gespiegeld), niet aan elkaar gelijk.

Zie onderaan de aparte sectie met expliciet weg-brede attributen.

---

## A. Identificatie, topologie, geometrie

| Attribuut | Betekenis | Bron | Scope |
|---|---|---|---|
| `linkId` | Gerichte link-id (negatief = terugrichting) | `network_fetcher`/`bidirectional_splitter` | gericht |
| `spectrumId` | Onderliggend Spectrum-segment-id | NETWORK-parquet | weg-breed |
| `fromNode` / `toNode` | Begin-/eindknoop (richting-afhankelijk) | `network_fetcher` | gericht |
| `mode` | `CAR`/`BIKE`/`PEDESTRIAN`/`BUS`/`TRAM`/`METRO`/`TRAIN` | `network_fetcher` | — |
| `length` | Lengte (m) | `network_fetcher` | weg-breed |
| `heading` | Kompasrichting van de link | NETWORK-parquet | gericht |
| `carLinkIds` | Gekoppelde CAR-link-id's (voor niet-CAR modi) | NETWORK-parquet | — |
| `reverseLinkIds` | Id van de tegenovergestelde richting | `bidirectional_splitter` | gericht (verwijst naar partner) |
| `parallelLinkIds` | Parallelle links (bv. fiets naast auto) | `parallel_link_finder` | — |
| `wvkIds` | Gematchte NWB `WVK_ID`'s (koppeling naar WKD/NWB) | `wkd_fetcher` | weg-breed |
| `geometry` | LineString | — | gericht (omgekeerd t.o.v. partner) |

## B. Capaciteit, snelheid, intensiteit (gericht; basis van de huidige editor)

| Attribuut | Betekenis | Bron | Scope | Al in digital-twin `openLinkDialog`? |
|---|---|---|---|---|
| `capacity` | Capaciteit (pae/uur) | `bidirectional_splitter` (uit `cap_heen`/`cap_terug`) | gericht | **Ja** — bewerkbaar |
| `speed` | Ontwerpsnelheid (km/h) | idem (`max_snelheid_*`) | gericht | **Ja** — bewerkbaar via snelheidsknoppen |
| `lanes` | Aantal rijstroken in deze richting | idem (`rijstroken_*`) | gericht | nee (alleen afgeleid stapgrootte) |
| `flow` | Dict `{work, recreational, education, shopping, unknown}` | `network_fetcher` | gericht | nee |
| `flow24hrs` | Totale 24-uurs flow | assignment/`emission_estimator`-schema | gericht | **Ja** — los dialoogje "doorstroming" (bewerkbaar als delta) |
| `flowsPerMotive` | Flow per motief (na toedeling) | assignment | gericht | nee |
| `flowTemporalUnit` / `flowsPerDaypart` | Flow per dagdeel | `network_fetcher`/assignment | gericht | nee |
| `remainingCap` | Resterende capaciteit na toedeling | assignment | gericht | nee (alleen gebruikt voor styling/knelpunten) |
| `osmMaxspeed` | Snelheidslimiet uit OSM, in rijrichting | `road_enricher` | gericht | nee |
| `osmLanesInDirection` | Rijstroken in rijrichting uit OSM | `road_enricher` | gericht | nee |

## C. Classificatie & naamgeving

| Attribuut | Betekenis | Bron | Scope |
|---|---|---|---|
| `name` | Straatnaam (voor dialoogtitel) | NETWORK-parquet | weg-breed |
| `ref` | Wegnummer (bv. N-weg) | NETWORK-parquet | weg-breed |
| `highway` | OSM-wegtype op het NETWORK-bestand zelf | NETWORK-parquet | weg-breed |
| `osmHighway` | OSM `highway`-tag (motorway…living_street) | `road_enricher` (UNDIRECTED) | weg-breed |
| `osmName` / `osmRef` | Naam/nummer uit OSM | `road_enricher` (UNDIRECTED) | weg-breed |
| `road_category` (wegenscan) | NWB-categorie (bv. "GOW 50 km/h", "ETW 30 km/h") | `analyzer/wegenscan_inputs.py` (afgeleid uit `osmHighway`+snelheid) | weg-breed |
| `priorityRoad` / `priorityRoadSource` | Voorrangsweg + bron (NDW-bord B1/B3, OSM-tag, rotonde) | `priority_roundabout_enricher` | weg-breed (tags negeren richting expliciet) |
| `isRoundabout` / `roundaboutType` | Rotonde + type | `priority_roundabout_enricher` | weg-breed |
| `numGiveWays` | Afgeleid: aantal voorrangskruisingen aan het eind | `priority_roundabout_enricher` | gericht (hangt af van welk uiteinde) |

## D. Wegdek & dwarsprofiel

| Attribuut | Betekenis | Bron | Scope |
|---|---|---|---|
| `surface` | Ruwe OSM `surface`-tag | `road_enricher` (UNDIRECTED) | weg-breed |
| `surfaceConfidence` | Aandeel stemmen voor winnende surface (0-1) | `road_enricher` | weg-breed |
| `smoothness` | OSM `smoothness` | `road_enricher` (UNDIRECTED) | weg-breed |
| `lit` | Straatverlichting aanwezig (OSM `lit`) | `road_enricher` (UNDIRECTED) | weg-breed |
| `osmWidth` | Rijbaanbreedte uit OSM `width`-tag (m) | `road_enricher` (UNDIRECTED) | weg-breed |
| `osmLanes` | Totaal aantal rijstroken (OSM `lanes`) | `road_enricher` (UNDIRECTED) | weg-breed |
| `osmOneway` | Eenrichtingsverkeer (expliciet of impliciet, bv. rotonde/snelweg) | `road_enricher` (UNDIRECTED) | weg-breed |
| `roadWidthM` / `roadWidthMinM` / `roadWidthMaxM` | Gemeten wegbreedte (mediaan/min/max) uit NDW WKD | `wkd_fetcher` | weg-breed |
| `roadWidthReliability` | Betrouwbaarheidsklasse WKD-meting | `wkd_fetcher` | weg-breed |
| `osmMatchRatio` | Dekkingsgraad van de OSM-matching (diagnose, niet inhoudelijk) | `road_enricher` | gericht (per evidence) |

## E. Voorzieningen per zijde (al naar rijrichting georiënteerd — zie uitleg boven)

| Attribuut | Betekenis | Bron | Scope |
|---|---|---|---|
| `cyclewayLeft` / `cyclewayRight` | Fietsvoorziening: `lane`/`track`/`shared_lane`/`share_busway`/`no`/… | `road_enricher` (DIRECTED) | gericht, L/R t.o.v. rijrichting |
| `sidewalkLeft` / `sidewalkRight` | Trottoir: `yes`/`no`/`separate` | `road_enricher` (DIRECTED) | gericht |
| `parkingLeft` / `parkingRight` | Langsparkeren: `lane`/`street_side`/`on_kerb`/`half_on_kerb`/`shoulder`/`separate`/`no` | `road_enricher` (DIRECTED) | gericht |
| `busway` | Busstrook in deze rijrichting | `road_enricher` (DIRECTED) | gericht |

## F. Wegenscan-afgeleide KPI-invoer (al als kant-en-klare UI in `analyzer`!)

`analyzer/wegenscan_inputs.py` leidt deze velden af uit de NETWORK-properties
hierboven (met expliciete bron-tracking), en `analyzer/scripts/main.js` toont
ze **al** in een zijpaneel (`wegenscanInputsHtml()` / `WS_INPUT_ROWS`,
main.js:5674-5759) mét bron-badge (netwerk/NWB/BGT-OSM/aanname/geen bron).
Dit is direct herbruikbare UI-logica voor de nieuwe link-popup.

| Veld (`wegenscan_invoer`) | Label (NL, uit i18n) | Afgeleid uit | Scope |
|---|---|---|---|
| `r_category` | Wegcategorie | `osmHighway` + snelheid | weg-breed |
| `r_speed` | Snelheid (V85) | `speedLimit`/`osmMaxspeed` (benadering: limiet, geen echte V85) | gericht (richting-afhankelijk in theorie, in praktijk = snelheidslimiet) |
| `r_width` | Wegbreedte | `roadWidthMinM/MaxM` of `roadWidthM`/`osmWidth` | weg-breed |
| `r_surface` | Wegdek | `surface` → verhardingsklasse → wegenscan-KPI-waarde | weg-breed |
| `r_flow` | Intensiteit | `flow`-dict geaggregeerd | gericht |
| `r_profile` | Profiel | `osmOneway` + fietsvoorziening | gericht (oneway is richtingsafhankelijk) |
| `r_bicycle_location` | Fietsers | `cyclewayLeft/Right` | gericht |
| `r_pedestrian_location` | Voetgangers | `sidewalkLeft/Right` + snelheid | gericht |
| `r_pedestrian_crossing` | Oversteek voetgangers | `numPedestrianCrossings`/`numRefugeAreas` | weg-breed (telling nabij link) |
| `r_parking_location` | Parkeren | `assetParkingLocation` of `parkingLeft/Right` | gericht |
| `r_parking_width` | Diepte parkeervak | `assetParkingWidth` | — |
| `r_speed_bumps` | Drempels | `assetSpeedBumps`/`numSpeedBumps` | weg-breed |
| `r_longitudinal_markings` | Kantmarkering | **geen bron — altijd default `"niet aanwezig"`** | **weg-breed (bedoeld)** |
| `r_separation` | **Rijrichtingscheiding** | **geen bron — altijd default** (zie sectie hieronder) | **weg-breed (bedoeld)** |
| `r_bus_facility` | Bushalte | **geen bron — altijd default** | weg-breed |
| `r_social_interaction` | Sociale interactie | **geen bron — altijd default `"ja"`** | weg-breed |
| `r_bicycle_width`, `r_bicycle_crossing`, `r_pedestrian_width` | Breedte/oversteek fiets, breedte voetpad | genoemd in `build_invoer`, maar in de huidige `wegenscan_inputs.py`-afleiding niet gevuld (alleen in de losstaande NWB-scripts) | — |

## G. Assets/tellingen nabij de link (puntobjecten, niet de link zelf)

| Attribuut | Betekenis | Bron | Scope |
|---|---|---|---|
| `numPedestrianCrossings` | Aantal voetgangersoversteekplaatsen binnen ~20 m, loodrecht op link | `network_asset_enricher` | weg-breed |
| `numCyclePaths` | Aantal kruisende fietspaden binnen ~20 m | `network_asset_enricher` | weg-breed |
| `numRefugeAreas` | Aantal verkeerseilanden/middengeleiders binnen ~20 m | `network_asset_enricher` | weg-breed |
| `trafficSignal` | Verkeerslicht bij `toNode` | `traffic_signal_annotator` | gericht (hangt af van welk uiteinde `toNode` is) |
| `numSpeedBumps` | Aantal drempels (OSM) | losstaand (wegenscan NWB-scripts) | weg-breed |
| `assetSpeedBumps` | Drempel aanwezig (BGT/OSM-assets) | `osm_asset_fetcher`/TRAFFIC-ASSETS | weg-breed |
| `assetParkingLocation` / `assetParkingWidth` | Parkeervlak-info uit BGT/OSM | `parking_area_fetcher` + koppeling in `wegenscan_inputs.py` | gericht (koppeling aan één kant) |
| `assetsCovered` | Dekkingsvlag: BGT-assetdata is compleet voor dit gebied | project-interne vlag | — |

## H. Berekende/afgeleide grootheden (read-only, geen brondata om te bewerken)

| Attribuut | Betekenis | Bron |
|---|---|---|
| `elevationFrom` / `elevationTo` | Hoogte (m) bij start-/eindpunt | `elevation_annotator` (Open-Meteo) |
| `co2Kg`, `noxKg`, `pm10Kg`, `pm25Kg`, `vehicleKm` (+ dagdeel-varianten) | Emissies | `emission_estimator` |
| `noiseDay`, `noiseEvening`, `noiseNight`, `noiseLden`, `noiseLnight`, `noiseSourceType` | Geluidemissie | `noise_estimator` |
| `generic_safety` | Samengestelde veiligheidsscore uit de 21 wegenscan-KPI's | `wegenscan.calculate_kpis` |
| 21 KPI-velden (GOED/REDELIJK/MATIG/SLECHT) | Individuele veiligheids-KPI's (bermschade, obstakelvrije zone, etc.) | `wegenscan.calculate_kpis` |

---

## Weg-brede attributen die op beide gerichte records geregistreerd moeten (blijven) staan

Dit zijn attributen die conceptueel bij de **hele weg** horen (onafhankelijk
van rijrichting). In de huidige dataflow worden ze al **identiek** op beide
gerichte links gezet (ze zitten in `UNDIRECTED_ATTRS` of komen ongesplitst uit
de bidirectionele bronrecord) — maar als de scenario-editor ze ooit bewerkbaar
maakt, moet een wijziging **op beide richtingen tegelijk** worden weggeschreven
om deze garantie niet te breken:

- `surface`, `smoothness`, `lit`, `osmHighway`, `osmName`, `osmRef`,
  `osmWidth`, `osmLanes`, `osmOneway` (expliciet `UNDIRECTED_ATTRS` in
  `road_enricher_core.py`)
- `roadWidthM` / `roadWidthMinM` / `roadWidthMaxM` / `roadWidthReliability`
  (WKD-wegbreedte — geldt voor de volle doorsnede, niet per rijstrook-richting)
- `priorityRoad` / `priorityRoadSource`, `isRoundabout` / `roundaboutType`
  (expliciet in code gedocumenteerd: *"Directional suffixes are ignored
  because priority applies in both directions"*)
- `name`, `ref`, `length`, `spectrumId`, `wvkIds` (identificatie/geometrie van
  het onderliggende wegvak)
- wegenscan: `r_category`, `r_width`, `r_surface`, `r_longitudinal_markings`,
  **`r_separation`**, `r_bus_facility`, `r_social_interaction`,
  `r_pedestrian_crossing`, `r_speed_bumps`

**Over "middenbermscheiding" specifiek**: er bestaat in de hele keten **geen
los attribuut met die naam**. Het dichtstbijzijnde is wegenscan's
`separation`/`r_separation` (NL-label: **"Rijrichtingscheiding"**) — conceptueel
exact de rijrichtingscheiding/middenberm die de gebruiker bedoelde, maar deze
heeft in de huidige pipeline **geen echte databron**: `add_markings.py` zet
hem altijd op de hardcoded default `"niet aanwezig"`. Elke link toont dus nu
hetzelfde (lege) antwoord voor dit kenmerk. Als de scenario-editor dit
bewerkbaar maakt, is het een goed archetype-voorbeeld van een weg-breed
attribuut: een wijziging moet op beide gerichte link-records landen.

---

## Wat `openLinkDialog` nu al toont/bewerkt (digital-twin, `scripts/main.js:15908`)

Alleen: **capaciteit** (bewerkbaar, met snelheidsknoppen die een vaste
snelheid→capaciteit-tabel toepassen), **snelheid** (impliciet via dezelfde
knoppen) en, via een los dialoogje, **flow24hrs** (als absolute/delta-waarde).
Geen van de attributen uit groepen C–H wordt getoond. Er is dus geen
bestaande "volledige attributen-popup" in digital-twin zelf.

De **wél bestaande, herbruikbare bouwsteen** staat in `analyzer/scripts/main.js`
(`wegenscanInputsHtml`, `WS_INPUT_ROWS`, `wsSourceBadge`): een read-only lijst
van ~15 mens-leesbare wegenscan-kenmerken met i18n-labels en bron-badge. Die
veronderstelt wel dat de wegenscan-pipeline al gedraaid heeft (`props.
wegenscan_invoer`/`wegenscan_sources` aanwezig) — in de kale `scenario-editor/`
is dat niet het geval, dus voor een simpele link-popup zijn de **ruwe
NETWORK-properties** (groepen A-E) het directere en eenvoudigere startpunt;
de wegenscan-rijen zijn vooral nuttig als voorbeeld van presentatie
(label + eenheid + bron-badge) en als "doel"-vocabulaire voor weg-brede vs.
gerichte attributen.

---

## Onzekerheden / aannames

- Het enige NETWORK-bestand dat ik kon inspecteren
  (`work/Spoorzone 2024/...-NETWORK-CAR.parquet`) bevat maar 24 kolommen
  (routing/assignment-schema: `capacity`, `lanes`, `speed`, `flow*`, `length`,
  `mode`, `carOneway`, `highway`, `ref`, `name`, `heading`,
  `reverseLinkIds`/`parallelLinkIds`/`carLinkIds`) — **niet** de rijkere
  OSM/WKD-kolommen (`osmHighway`, `cyclewayLeft`, `roadWidthM`, …) die
  `road_enricher`/`wkd_fetcher` toevoegen. Of die kolommen in productie-areas
  wél aanwezig zijn hangt af van welke prepare-pipeline voor dat gebied
  gedraaid is (`gmt_network_enrichment` ≥ 0.6, zie docstring
  `wegenscan_inputs.py`). **Voor implementatie: verifieer op een area die wél
  via de volledige enrichment-pipeline is opgebouwd welke kolommen echt
  aanwezig zijn**, anders toont de popup voor oudere/eenvoudiger areas vooral
  lege velden.
- `r_longitudinal_markings`, `r_separation`, `r_bus_facility`,
  `r_social_interaction` zijn in de huidige analyzer-pipeline (via
  `wegenscan_inputs.py`) altijd afwezig/default — ze worden alleen gevuld door
  de **losstaande** NWB-preprocessing-scripts (`wegenscan` package se
  `add_*.py`), die niet aantoonbaar deel uitmaken van de live
  speeltuin-pipeline. Behandel ze in de UI expliciet als "geen databron" (zoals
  de bestaande bron-badge al doet) totdat bevestigd is of/hoe ze gevuld worden.
- Ik heb de `common/py/buildings_fetcher`-module niet onderzocht (gebouwen,
  niet links — buiten scope).
- `gmt-modules-noise-emission-integratie.md` niet apart gelezen; de
  `noise_estimator`/`emission_estimator`-coretabellen in de wheel zelf waren
  voldoende autoritatief en zijn hierboven al verwerkt (groep H).
- TRAFFIC-ASSETS-properties (bankjes, fietsenrekken, parkeervlak-tags als
  `tag_amenity`, `tag_fee`, …, gezien in `digital-twin/server.py:2286-2295`)
  zijn punt-/vlakobjecten gekoppeld aán links, geen link-attributen zelf — hier
  bewust buiten de tabellen gelaten, met uitzondering van de velden die al in
  een link-property zijn gekopieerd (`assetParkingLocation`, `assetSpeedBumps`, …).
