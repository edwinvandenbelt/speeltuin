# Plan: "Snelheid"-menu + straf-seconden per wegvak

Een nieuwe kaartlaag-groep ("Snelheid") die per wegvak laat zien welke
factoren de reistijd beïnvloeden (oversteken, verkeerslichten, voorrang,
tegenliggerhinder, …), plus een geaggregeerde **straf-seconden**-laag die deze
factoren optelt tot één getal per wegvak. Routing-integratie is **expliciet
buiten scope** van dit plan — de data wordt wel zo opgezet dat een later
routing-plan er direct op kan aansluiten.

```
NETWORK-CAR (flow/aadt) ──┐
TRAFFIC-ASSETS (oversteken,│
 verkeerslichten, borden) ─┼─► knooppunt-/conflictmodel ─► straf-componenten ─► straf-seconden-laag
BGT wegdeel (breedte) ─────┘        (fase 0)                    (fase 1-4)           (fase 5)
```

---

## Uitgangspunten (samengevat uit het gesprek)

1. Nieuw menu-item **"Snelheid"**, met sub-lagen voor alles wat de reistijd op
   een wegvak kan beïnvloeden: zebrapaden, fietsoversteken, verkeerslichten,
   stopstrepen/haaientanden, vluchtheuvels (midden op de weg), verkeer van
   rechts, tegenliggerhinder.
2. **Alle wegvakken** worden getekend; een wegvak krijgt een duidelijke kleur
   zodra één van deze factoren erop van toepassing is.
3. Een aparte kaartlaag toont het aantal **straf-seconden** per wegvak — de
   som van alle factoren. De seconden per factor zijn nu een **inschatting**
   (voorstel hieronder), geen harde waarheid.
4. Straftijd moet uiteindelijk meewegen in de **routing-algoritmes** — dat
   volgt in een apart, later plan.
5. Straftijd moet uiteindelijk ook afhankelijk worden van de **drukte**
   (voetgangers/fietsers) bij een oversteek — voor nu bewust **uitgesteld**,
   want er is geen bruikbare databron.
6. **Verkeer van rechts**, **linksaf-hinder** en **tegenliggerhinder** zijn
   niet vaste getallen, maar afhankelijk van de **flow op de conflicterende
   tak** — dus per conflict moet de `linkId` van die tak worden vastgelegd
   (niet alleen een strafwaarde). De visualisatie-laag toont de **ruwe flow**
   (vtg/u, per dagdeel); de straf-seconden gebruiken diezelfde flow.
7. **Fietsoversteken** hoeven niet apart gefetcht te worden: ze zijn direct
   beschikbaar via `numCyclePaths`/`numCycleCrossings` op `NETWORK-CAR`.
8. **Tegenliggerhinder** (geen middenscheiding/te smal) wordt afgeleid uit
   **BGT `wegdeel`-polygonen** (echte breedte), niet uit de huidige
   default-only `separation`-kolom van wegenscan.

---

## DEEL A — Verzoek aan de gmt-library (concreet, over te dragen)

> Dit blok is bewust zo geschreven dat het **los overhandigd kan worden** aan
> de gmt-library als invoerspecificatie — net als de "DEEL A"-secties in
> `plan-stress-lagen.md` en de open-vragen-tabellen in
> `plan-parkeer-indicator.md`. De geometrie-/conflictberekening (bearing-
> vergelijking tussen takken, BGT-doorsnedes) hoort beter thuis in de
> Python/GIS-laag van de gmt-library dan in de browser-JS van deze speeltuin.

### A1. `NETWORK-CAR.parquet` — nieuwe kolommen per wegvak

| Kolom | Type | Status | Omschrijving |
| --- | --- | --- | --- |
| `nodeControlFrom` / `nodeControlTo` | enum (`signalized`/`priority`/`roundabout`/`uncontrolled`) | **geleverd (Lochem)** | Regelingstype van het knooppunt aan resp. het begin (`fromNode`) en einde (`toNode`) van het wegvak. Bepaalt of "verkeer van rechts" überhaupt van toepassing is op deze tak. |
| `fromRightLinkId` | int / linkId (nullable) | **geleverd (Lochem)** | De `linkId` van de tak die bij een `uncontrolled`-knooppunt van rechts nadert t.o.v. dit wegvak (de tak waar dit wegvak voorrang aan moet verlenen). `null` als niet van toepassing (geregeld knooppunt, rotonde, of doodlopend). |
| `fromRightFlow` | double (mvt/etmaal) | **geleverd (Lochem)** | De flow behorend bij `fromRightLinkId`, gebruikt als basis voor de flow-afhankelijke verkeer-van-rechts-straf (fase 3.1). |
| `fromLeftFlow` | double (mvt/etmaal) | **geleverd (Lochem)** | Flow van de tak die van links nadert op de `toNode`; gebruikt voor linksaf- en rechtsaf-hinder (fase 3.2/3.3). |
| `oppositeLinkId` | int / linkId (nullable) | **geleverd (Lochem)** | De `linkId` van de tak die ongeveer tegenover dit wegvak ligt bij hetzelfde knooppunt (rechtdoorgaand/tegemoetkomend verkeer, relevant voor linksafslaand verkeer). `null` als niet van toepassing. |
| `oppositeFlow` | double (mvt/etmaal) | **geleverd (Lochem)** | De flow behorend bij `oppositeLinkId`, gebruikt voor de linksaf-straf (fase 3.2). |
| `leftTurnRatio` | double 0–1 | **geleverd (Lochem)** | Aandeel verkeer op dit wegvak dat aan `toNode` linksaf slaat. Wordt gebruikt om de linksaf-hinder alleen toe te passen op het deel dat daadwerkelijk linksaf slaat. |
| `rightTurnRatio` | double 0–1 | **geleverd (Lochem)** | Aandeel verkeer op dit wegvak dat aan `toNode` rechtsaf slaat. Wordt gebruikt voor de (marginale) rechtsaf-hinder. |
| `roadWidthM` | double (m) | **geleverd (Lochem)** | Werkelijke rijbaanbreedte, afgeleid uit BGT `wegdeel`-polygonen (loodrechte doorsnedes langs het wegvak, zie fase 4.1) — **niet** de huidige KPI-only `r_road_width` uit wegenscan. Nodig voor zowel de tegenligger-hinder-straf hier als de smalle-straten-breedtecheck in `docs/plan-parkeer-indicator.md` fase 2.3 (dus één gedeelde kolom voor twee plannen). |
| `hasCenterSeparation` | bool | **gewenst** | Of er een fysieke/markering-gebaseerde middenscheiding is. In Lochem nog niet geleverd; frontend valt terug op `false` (conservatief). |
| `numPedestrianCrossings`, `numGiveWays`, `numStoppingLanes`, `numRefugeAreas`, `numSpeedBumps`, `trafficSignal`, `numCyclePaths` | int/bool | **geleverd (Lochem)** | Aantallen/booleans voor verkeersobjecten op het wegvak. Maakt de v0 Snelheid-sub-lagen onafhankelijk van de viewport-bbox traffic-assets fetch. `numCyclePaths` wordt gebruikt als proxy voor fietsoversteken; `numCycleCrossings` is de voorkeur als die beschikbaar komt. |

### A2. Bestaande kolommen — alleen bevestiging

| Kolom | Vraag |
| --- | --- |
| `flow24hrs`/`aadt` | Gebruikt voor `fromRightFlow`/`oppositeFlow`; de gmt-library levert deze flows nu direct mee op het wegvak, waardoor er geen aparte join nodig is. De vraag of `flow24hrs` per richting is gesplitst is hierdoor minder kritisch, maar blijft relevant voor validatie. |

### A3. Optioneel (verrijkt de nauwkeurigheid, niet blokkerend)

| Behoefte | Waarom |
| --- | --- |
| Cyclustijd/groentijd per `trafficSignal`-punt | Vervangt de vaste aanname van +10 sec (fase 5) door een echte gemiddelde-wachttijd-berekening |
| `cyclePath`/`footPath` als LineString (zie ook `plan-stress-lagen.md` Deel A) | Vervallen als harde afhankelijkheid: in Lochem is `numCycleCrossings` al beschikbaar op `NETWORK-CAR`, waarmee fase 2 al direct renderbaar is. De geometrische afleiding uit lijnen blijft een mogelijke verfijning voor later. |
| `elevationFrom` / `elevationTo` | Hellingspercentage per wegvak; gebruikt voor de nieuwe hellingsvertragings-laag (zie Fase 6 hieronder). |

---

## Wat er al is (hergebruiken)

| Onderdeel | Waar | Bruikbaar voor |
| --- | --- | --- |
| `pedestrianCrossing`, `trafficSignal`, `giveWay`, `stopSign` (TRAFFIC-ASSETS) | al gefetcht, al gerenderd (net gefixt qua rotatie) | Fase 1: eerste sub-lagen zonder nieuwe fetch |
| `flow`/`flow24hrs`/`aadt` per wegvak | `linkFlowMap`/`segFlow()` in `index.html` | Fase 3/4: flow-afhankelijke straffen |
| `colorMetric`-mechanisme (`<optgroup>`, `getMetricValue`, `METRIC_LIMITS`-banding) | `index.html:1488-1509`, `10401-10423` | Fase 1 & 5: kleurcodering van wegvakken op straf(component) |
| `laneMarkArrow`/`turn:lanes` (net gefixt qua rotatie/plaatsing) | `index.html` (`_prepareLaneMarkArrows`) | Fase 3: bepalen welke takken een linksafslaande strook hebben |
| BGT `wegdeel`-toegang | al gebruikt door `parking_area_fetcher` (zie `docs/plan-parkeer-indicator.md`) | Fase 4: basis voor de door de gmt-library aan te leveren `roadWidthM` (Deel A) |
| Knooppunt-/graafopzet (`adj`/`nodeCoords`, `dijkstraPath`) | `index.html:8415-8525` | Fase 0: patroon voor de (fallback-)knooppuntgraaf, niet voor de routing-cost zelf |
| Geplande `cyclePath`/`footPath`-lijnen | `plan-stress-lagen.md` Deel A (nog niet geleverd) | Fase 2: fietsoversteek-afleiding (afhankelijkheid, geen blocker voor de rest) |

---

## Fase 0 — Knooppunt-/conflictmodel (fundament)

Dit fundament wordt door bijna alle volgende fases gebruikt. **De kern hiervan
(regelingstype + conflicterende `linkId`'s) wordt bij voorkeur door de
gmt-library geleverd (zie Deel A, `A1`)** — bearing-vergelijking tussen takken
en BGT-doorsnedes zijn geometrie-bewerkingen die beter in de Python/GIS-laag
passen dan in browser-JS. Hieronder staat wat de speeltuin zelf doet met die
aangeleverde velden, plus een fallback-aanpak mocht de levering vertragen.

1. **Knooppuntgraaf**: bouw (client-side) een lichte graaf van
   `fromNode`/`toNode` met graad per node — zelfde patroon als de bestaande
   `adj`/`nodeCoords`-opbouw in `index.html`, alleen om de aangeleverde
   `nodeControl*`/`fromRightLinkId`/`oppositeLinkId`-velden (Deel A) te
   kunnen visualiseren en filteren — niet om ze zelf te berekenen.
2. **Regelings-classificatie per knooppunt** (`nodeControlFrom`/
   `nodeControlTo`, Deel A/A1): `signalized` / `priority` / `roundabout` /
   `uncontrolled`. **Fallback** (totdat de gmt-library dit levert): zelf
   snappen van `trafficSignal`/`giveWay`/`stopSign`-punten naar het
   dichtstbijzijnde knooppunt (≤20 m, zelfde marge als
   `plan-stress-lagen.md` B3) en hieruit een grove classificatie afleiden.
3. **Conflict-model per ongeregeld knooppunt** (`fromRightLinkId`,
   `oppositeLinkId`, Deel A/A1): dit is de data die een later routing-plan
   direct kan hergebruiken. **Fallback** (totdat geleverd): een eigen,
   eenvoudiger bearing-vergelijking tussen aftakkende links bij een
   knooppunt, met de kanttekening dat dit minder betrouwbaar is dan een
   GIS-laag-implementatie (bijv. bij meer dan 4 takken, of bij afwijkende
   geometrie vlak bij het knooppunt).
4. **Linksaf-afhankelijkheid**: koppel aan elke aftakkende tak of er een
   linksafslaande strook is, via de al bestaande `turn:lanes`/
   `laneMarkArrow`-data (dit blijft **eigen werk**, geen gmt-library-vraag,
   want deze data bestaat al). Alleen die takken krijgen later een aparte
   linksaf-straf (fase 3.2) — niet elk wegvak uniform.

**Output van deze fase**: een herbruikbare `nodeControl`-classificatie +
conflict-tabel (idealiter direct uit `NETWORK-CAR`, zie Deel A). Nog geen
kleur, nog geen seconden.

> **Geïmplementeerd (v0, fallback)**: stap 2 (regelings-classificatie) en de
> koppeling van zebra/verkeerslicht/haaientanden/stopbord aan het
> dichtstbijzijnde wegvak zijn al gebouwd (`rebuildSpeedLayers()` in
> `index.html`), inclusief het "Snelheid"-menu en de straf-seconden-laag met
> alleen de vaste componenten (fase 1 + fase 5 v0). Stap 3 (bearing-conflict-
> model voor verkeer van rechts/linksaf) is **nog niet** gebouwd — die volgt
> pas met de gmt-library-levering (Deel A) of als aparte vervolgstap.
>
> **Bekende beperking van deze v0-fallback**: de onderliggende punt-data
> (`pedestrianCrossing`/`trafficSignal`/`giveWay`/`stopSign`) wordt pas
> opgehaald vanaf zoomniveau ≥16 (`_TA_MINZOOM`, bestaande drempel bedoeld
> voor icoon-rendering, niet voor deze wegvak-brede kleurlaag). Bij lagere
> zoomniveaus tonen de "Snelheid"-sub-lagen en de straf-seconden-laag dus nog
> niets, ook al is de netwerk-laag zelf wel zichtbaar. **Bewuste keuze:** dit
> nu niet apart oplossen (bv. door de fetch-drempel te verlagen of los te
> koppelen van de icoon-rendering) — zodra de gmt-library de classificatie/
> straf-informatie direct als kolommen op `NETWORK-CAR` aanlevert (Deel A),
> is dit probleem vanzelf opgelost: het netwerk wordt namelijk altijd
> volledig geladen bij het openen van een gebied, ongeacht zoomniveau, in
> tegenstelling tot de viewport-bbox-gebonden traffic-assets-fetch.

---

## Fase 1 — "Snelheid"-menu + eerste sub-lagen (bestaande data)

> **Status: geïmplementeerd** (`<optgroup label="Snelheid">` in de
> `#colorMetric`-dropdown, `index.html`). De onderliggende data komt nu
> bij voorkeur direct uit `NETWORK-CAR` (`trafficSignal`,
> `numPedestrianCrossings`, `numGiveWays`, `numStoppingLanes`,
> `numRefugeAreas`, `numSpeedBumps`), waardoor de zoom-16-beperking van de
> traffic-assets fetch niet meer geldt. De punt-assets blijven als fallback
> beschikbaar voor oudere exports zonder deze kolommen.

1. Nieuw menu-item **"Snelheid"**: een `<optgroup>` in het bestaande
   `colorMetric`-dropdown-patroon (`index.html:1488-1509`).
2. Sub-lagen met **NETWORK-CAR attributen** (primair) of traffic-assets
   (fallback):
   - Zebrapaden (`numPedestrianCrossings > 0` of `pedestrianCrossing`)
   - Verkeerslichten (`trafficSignal === true` of `trafficSignal`)
   - Haaientanden/stopstrepen (`numGiveWays > 0` / `numStoppingLanes > 0`
     of `giveWay`/`stopSign`)
   - Vluchtheuvels (`numRefugeAreas > 0`), exclusief objecten die binnen
     ~15 m van een knooppunt liggen. De visuele weergave van vluchtheuvels
     (de gedetailleerde polygonen op het wegdek) blijft afkomstig van de
     traffic-assets, maar de **penalty en de speed_refuge laag** gebruiken
     uitsluitend de `NETWORK-CAR` registratie. Als `numRefugeAreas` niet
     correct is, moet de gmt-library dit aanpassen.
3. **Alle wegvakken blijven getekend** — wegvakken zonder factor krijgen een
   neutrale kleur, wegvakken mét factor een opvallende kleur.

---

## Fase 2 — Fietsoversteek (direct uit NETWORK-CAR)

> **Status: geïmplementeerd** via `numCycleCrossings` op `NETWORK-CAR`
> (beschikbaar in Lochem). De geometrische afleiding uit
> `cyclePath`/`footPath` LineStrings is hierdoor niet langer een harde
> afhankelijkheid.

1. Data komt direct uit `numCycleCrossings` op `NETWORK-CAR`; geen aparte
   fetch of geometrische snapping nodig.
2. De laag `speed_cycle_crossings` kleurt oranje waar
   `numCycleCrossings > 0`.
3. In gebieden zonder `numCycleCrossings` blijft de laag grijs totdat de
   data beschikbaar is.

---

## Fase 3 — Verkeer van rechts + linksaf/rechtsaf-straf (flow-afhankelijk)

> **Status: geïmplementeerd** — de Deel A kolommen zijn in Lochem geleverd
> en worden direct gebruikt.

Bouwt rechtstreeks op de door de gmt-library aangeleverde velden (Deel A/A1):
`fromRightLinkId`, `fromLeftLinkId`, `oppositeLinkId`, `leftTurnRatio` en
`rightTurnRatio`. De flows worden **runtime** opgehaald uit de doellink
(via `linkFlowMap` / `flowsPerDaypart`), zodat ze per dagdeel wisselen.

### Visualisatie (ruwe flows)

- `speed_from_right`: toont de uurintensiteit (vtg/u) op `fromRightLinkId`.
- `speed_left_turn`: toont `oppositeFlow + fromLeftFlow` (vtg/u).
- `speed_oncoming`: toont de tegenliggers-flow `oppositeFlow` (vtg/u).

Deze lagen gebruiken dezelfde kleurschaal en -schalen als de gewone
intensiteitskaart (`flow`), zodat ze direct vergelijkbaar zijn.

### Straf-seconden (penalty total)

1. **Verkeer-van-rechts-straf**: voor elk wegvak met een niet-lege
   `fromRightLinkId`:
   `straf_rechts = k_rechts · fromRightFlow_runtime`.
   Huidige startwaarde: `k_rechts = 3 / 600` (≈ 3 sec bij 600 veh/24h).
   Geen `fromRightLinkId` betekent: geen weg van rechts, dus geen straf.

2. **Linksaf-straf**: linksafslaan kruist zowel tegenliggers als verkeer van
   links. Alleen het daadwerkelijke linksafslaande aandeel (`leftTurnRatio`)
   krijgt de straf:
   `straf_links = k_links · (oppositeFlow_runtime + fromLeftFlow_runtime) · leftTurnRatio`.
   Huidige startwaarde: `k_links = 4 / 800`.

3. **Rechtsaf-straf**: rechtsafslaan kruist alleen verkeer van links. Deze
   straf is marginaal:
   `straf_rechts_af = k_rechts_af · fromLeftFlow_runtime · rightTurnRatio`.
   Huidige startwaarde: `k_rechts_af = 1 / 800`.

4. **Output per wegvak**: losse componenten (`fromRight`, `leftTurn`,
   `rightTurn`) die mee opgeteld worden in `speed_penalty_total` en in de
   tooltip getoond worden.

5. De conflict-`linkId`'s zelf (`fromRightLinkId`/`oppositeLinkId`) blijven
   ook zichtbaar/beschikbaar voor eventueel later gebruik in routing.

---

## Fase 4 — Tegenliggerhinder (BGT-gebaseerd)

> **Status: geïmplementeerd** — gebruikt `roadWidthM` uit Lochem. `hasCenterSeparation`
> is nog niet geleverd; frontend valt terug op `false` (dus iedere smalle weg
> zonder scheiding telt mee totdat het veld beschikbaar is).

1. **Wegbreedte** (`roadWidthM`, Deel A): afgeleid uit BGT `wegdeel`-
   polygonen. In Lochem heeft dit veld waarden rond 1,5–3,0 m; dit lijkt de
   **rijstrookbreedte per richting** te zijn. Voor de tegenliggerhinder
   berekenen we daarom de **effectieve tweerichtingsbreedte**:
   `effectiveWidth = roadWidthM · lanes · 2`.
2. **Visualisatie** (`speed_oncoming`): toont de ruwe tegenliggers-flow
   `oppositeFlow` (vtg/u) op wegen waarvan de effectieve breedte kleiner is
   dan **5,5 m**.
3. **Straf-seconden**: als `effectiveWidth < 5.5 m` **en**
   `hasCenterSeparation = false`:
   `straf_oncoming = k_oncoming · max(0, 5.5 − effectiveWidth) · oppositeFlow_runtime`.
   Huidige startwaarde: `k_oncoming = 2 / 600`.
4. Deze rekenlogica moet apart worden gevalideerd (bijv. steekproeven tegen
   Streetview/luchtfoto). Zodra `hasCenterSeparation` geleverd wordt, wordt
   het meegenomen om false-positives te voorkomen.

---

## Fase 5 — Straf-seconden-aggregatielaag

> **Status: geïmplementeerd** — `speed_penalty_total` sommeert de vaste
> componenten, de flow-afhankelijke componenten uit fase 3/4 en de
> hellingsvertraging uit fase 6. De constanten zijn voorlopige startwaarden.

1. **Som per wegvak**: vaste componenten (zebra/verkeerslicht/haaientanden/
    stopbord/vluchtheuvel) + flow-afhankelijke componenten (fase 3 + fase 4) +
    hellingsvertraging (fase 6):

   | Factor | Voorstel (vast of formule) | Toelichting |
   | --- | --- | --- |
   | Zebra, ongeregeld | +2 sec | gemiddeld afremmen voor overstekende voetganger |
   | Zebra, met verkeerslicht | (telt mee via verkeerslicht-component, niet dubbel) | |
   | Fietsoversteek, ongeregeld | +2 sec | |
   | Verkeerslicht (kruispunt) | +10 sec | ruwe aanname o.b.v. gemiddelde wachttijd; cyclustijd onbekend |
   | Haaientanden (voorrang verlenen) | +2 sec | |
   | Stopbord | +4 sec | verplicht stilstaan + optrekken |
   | Vluchtheuvel, midden op de weg | +2 sec | versmalling/ontwijkmanoeuvre; vluchtheuvels aan het eind van het wegvak (bij een kruising) tellen hier niet mee |
   | Verkeer van rechts | `k_rechts · fromRightFlow_runtime` | flow-afhankelijk, `k_rechts = 3 / 600` |
   | Linksaf-hinder | `k_links · (oppositeFlow_runtime + fromLeftFlow_runtime) · leftTurnRatio` | flow-afhankelijk, `k_links = 4 / 800` |
   | Rechtsaf-hinder | `k_rechts_af · fromLeftFlow_runtime · rightTurnRatio` | marginaal, `k_rechts_af = 1 / 800` |
   | Tegenliggerhinder | `k_oncoming · max(0, 5.5 − (roadWidthM · lanes · 2)) · oppositeFlow_runtime` | zie fase 4.2, `k_oncoming = 2 / 600` |
   | Hellingsvertraging (omhoog) | lineair van 0 sec bij ≤3% tot 6 sec bij ≥15% | zie fase 6 |

   Alle constanten (`k_rechts`, `k_links`, `k_breedte`, en de vaste seconden)
   zijn **startwaarden ter discussie**, geen gevalideerde cijfers.
2. Nieuwe `colorMetric`-optie `penalty_seconds`, met absolute banding —
   zelfde patroon als de bestaande geluid/uitstoot-metrics
   (`METRIC_LIMITS`, `index.html:10401-10423`).
3. **Tooltip toont de volledige breakdown** per component (welke factoren
   gelden hier, en hoeveel seconden elk bijdraagt) — essentieel om de
   voorstelwaarden later te kunnen valideren/kalibreren, en om te snappen
   waaróm een wegvak een hoge straf heeft.
4. De datastructuur (`penaltySec` per wegvak + de onderliggende componenten
   + de conflict-tabel uit fase 0.3) wordt zo opgezet dat een **later
   routing-plan** dit direct kan hergebruiken. Het aanpassen van de
   routing-cost-functies zelf (frontend-Dijkstra in `index.html`, en de
   Python `whatif`-package) valt **niet** onder dit plan.

## Nieuw voorstel voor de strafseconden:

   | Factor | Voorstel (vast of formule) | Toelichting |
   | --- | --- | --- |
   | Zebra, ongeregeld | max 3 sec, maar direct gerelateerd aan de nabijheid van de POIs (voetganger) en de eigen 'remainingCap', dus afhankelijk van OS/AS/RD of uur van de dag. Bij weinig remainingCap wordt de factor hoog, bij hoge remainingCap (dus ook de kans dat je iemand op het zebrapad tegenkomt) wordt de factor hoog. | gemiddeld afremmen voor overstekende voetganger [TODO: maak een nette formule voor dit] |
   | Zebra, met verkeerslicht | (telt mee via verkeerslicht-component, niet dubbel) | Mee eens |
   | Fietsoversteek, ongeregeld | max 2 sec, vergelijkbaar met de zebra, maar dan nabijheid van de POIs (fiets) gebruiken | |
   | Verkeerslicht (kruispunt) | +10 sec, maar afhankelijk van de totale flow op het kruispunt en de verhouding van de flow op de link en de totale flow. Bij veel verkeer (groot kruispunt) zal de wachttijd meer zijn, en als je op een onbetekenende tak richting het kruispunt aankomt, zal jouw wachttijd waarschijnlijk ook hoger zijn | ruwe aanname o.b.v. gemiddelde wachttijd; cyclustijd onbekend |
   | Haaientanden (voorrang verlenen) | 2 sec, maar afhankelijk van de flow van rechtsaf. Het kan ook veel hoger worden | |
| Stopbord | 4 sec | verplicht stilstaan + optrekken, maar ook vergelijkbaar met de haaientanden |
| Vluchtheuvel, midden op de weg | +1 sec | versmalling/ontwijkmanoeuvre; vluchtheuvels aan het eind van het wegvak (bij een kruising) tellen hier niet mee |
| Verkeer van rechts | `k_rechts · fromRightFlow_runtime` | flow-afhankelijk, `k_rechts = 3 / 600` |
| Linksaf-hinder | `k_links · (oppositeFlow_runtime + fromLeftFlow_runtime) · leftTurnRatio` | flow-afhankelijk, `k_links = 4 / 800` |
| Rechtsaf-hinder | `k_rechts_af · fromLeftFlow_runtime · rightTurnRatio` | marginaal, `k_rechts_af = 1 / 800` |
| Tegenliggerhinder | `k_oncoming · max(0, 5.5 − (roadWidthM · lanes · 2)) · oppositeFlow_runtime` | zie fase 4.2 |
| Hellingsvertraging (omhoog) | lineair 0 sec (≤3%) → 6 sec (≥15%) | zie fase 6 |

---

## Buiten scope (bewust uitgesteld)

- **Routing-integratie**: aparte, latere planfase zodra de straf-
  seconden-waarden gevalideerd zijn. Raakt zowel de frontend-Dijkstra
  (`index.html:8504`, nu zuiver afstand-gebaseerd) als de Python
  `whatif`-package (`networkx`-gebaseerd, nu lengte×congestie-gewicht) —
  beide moeten om naar een tijd-gebaseerde kostfunctie + straf-term, wat een
  eigen ontwerp verdient.
- **Voetgangers-/fietsersvolume-inschatting (attractie/productie)**: geen
  bruikbare databron beschikbaar (alleen een ruwe gebouw-proxy mogelijk via
  `buildings_fetcher`); bewust uitgesteld totdat er betere data is (echte
  tellingen, landgebruiksmodel, of iets vergelijkbaars). Zodra dit er is,
  kunnen de vaste crossing-straffen (zebra/fietsoversteek/verkeerslicht)
  drukte-afhankelijk gemaakt worden in plaats van vaste constantes.

---

## Open vragen (niet gmt-library-specifiek)

De concrete data-verzoeken aan de gmt-library staan gebundeld in **Deel A**
(bovenaan dit document, direct overhandigbaar). Onderstaande punten zijn
overige open vragen die niet (alleen) bij de gmt-library liggen:

| Behoefte | Waarom | Status |
| --- | --- | --- |
| Voetgangers-/fietserstellingen of landgebruiksmodel | Druktecorrectie op crossing-straffen | **bewust uitgesteld**, wacht op betere data (zie "Buiten scope") |
| Kalibratie van `k_rechts`/`k_links`/`k_breedte` en de vaste seconden-waarden | Fase 5, correctheid van de straf-seconden-laag | **nieuw, gewenst** — vraagt validatie door een verkeerskundige, niet (alleen) door de gmt-library |
| Keuze menu-patroon (`<optgroup>` vs. `.sp-section`) | Fase 1, UI-implementatie | **intern te beslissen**, geen externe afhankelijkheid |
| Uitleg/validatie `roadWidthM` in Lochem (waarden rond 1,5–3,0 m; lijkt de rijbaanbreedte per richting te zijn, niet totaal) | Fase 4, tegenliggerhinder is hier direct op gebaseerd | **nieuw, gewenst** — waarschijnlijk een verkeerskundige/data-afkomst check |

---

## Fase 6 — Hellingsvertraging (elevationFrom / elevationTo)

> **Status: geïmplementeerd** — maakt gebruik van de `elevationFrom` en
> `elevationTo` kolommen op `NETWORK-CAR` (beschikbaar in Lochem).

1. Bereken hellingspercentage:
   `slope_pct = (elevationTo − elevationFrom) / length × 100`.
2. Alleen **positieve** helling (omhoog rijden) telt mee.
3. Strafseconden lineair:
   - `≤ 3%`: 0 sec
   - `3% → 15%`: `0 … 6` sec
   - `≥ 15%`: 6 sec
4. Component wordt toegevoegd aan `speed_penalty_total` en getoond in de
   tooltip. Binaire laag `speed_elevation` (kleur: oranje/indicatie) is
   beschikbaar in het Snelheid-menu.

---

## Volgorde-advies (samenvatting)

1. **Fase 0** — knooppunt-/conflictmodel (fundament voor bijna alles erna).
2. **Fase 1** — "Snelheid"-menu + zebra/verkeerslicht/haaientanden-sub-lagen
   (direct op `NETWORK-CAR`, geen zoom-afhankelijkheid meer).
3. **Fase 2** — fietsoversteek (`numCycleCrossings` op `NETWORK-CAR`).
4. **Fase 3** — verkeer van rechts + linksaf-straf (Deel A kolommen zijn
   geleverd).
5. **Fase 4** — tegenliggerhinder (data is geleverd, maar `roadWidthM`
   moet nog gevalideerd worden alvorens het meetelt in de totaalscore).
6. **Fase 5** — straf-seconden-aggregatielaag (werkt nu met fase 1, 2, 3
   en 6; fase 4 kan later worden toegevoegd).
7. Routing-integratie en drukte-afhankelijke crossing-straffen: **aparte,
   latere plannen**, buiten scope hier.
