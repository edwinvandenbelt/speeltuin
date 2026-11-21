# Plan: issue #7 — "Geparkeerde auto's naast grote wegen"

## Context

[Issue #7](https://github.com — zie `gh issue view 7`) meldt dat auto's in de digital-twin
verkeerssimulatie kunnen "parkeren" op wegen met een snelheid >50 km/u, wat onrealistisch is.
De auteur licht in een comment een rijkere achterliggende wens toe: auto's zouden moeten
vertrekken/aankomen bij plausibele parkeerlocaties, afhankelijk van het reismotief
(woon-werkverkeer 's ochtends van huis → werk, 's middags andersom; winkelverkeer bij
winkels/winkelcentra). Doel van dit plan is tweeledig: (A) de kernfout direct repareren, en
(B) een eerste, kleine stap richting motief-bewust parkeren zetten — zonder de volledige
motief-gebaseerde oplossing in één keer te bouwen (dat is expliciet een vervolgtraject, net als
`docs/plan-parkeer-indicator.md` dat al gefaseerd aanpakt voor parkeer-aanbod in de analyzer).

Alle wijzigingen zitten in `digital-twin/scripts/main.js` (de simulatie-engine van de digital
twin; `analyzer/scripts/main.js` en `temp/_main.js` zijn ongerelateerde/oudere kopieën).

---

## Deel A — Kernfix: nooit parkeren op een link >50 km/u

### Hoofdoorzaak

`canPark` wordt nu **per route** bepaald, puur op basis van de snelheid van de **eerste** link
van die route (`main.js:10847-10861`):
```js
const canPark = firstSpeedMs <= (50 / 3.6) && (route.vehicleMode ?? MODE) !== 'BIKE';
```
Deze ene vlag wordt daarna hergebruikt om te bepalen of een auto ergens willekeurig op de
**hele** route (gewogen naar flow×lengte, over alle links heen) als "geparkeerd" wordt neergezet
— ook als die positie op een snellere link dan de eerste valt. Dit gebeurt op drie plekken
(initiële vul-methodes `link`, `cap`, `LL` — `main.js:10942`, `11006`, `11078`), plus een
runtime-overgang aan het eind van een route (`main.js:14513-14518`) die dezelfde verouderde,
route-brede vlag gebruikt (en bovendien niet herberekend wordt na route-chaining via
`pendingPath`, `main.js:14504-14508`).

### Wijzigingen

1. **Nieuwe constante** naast de bestaande `PARK_*`-constanten (`main.js:2632-2636`):
   ```js
   const PARK_MAX_SPEED_MS = 50 / 3.6;
   ```
2. **Stap 1 van `buildCarList` vereenvoudigen** (`main.js:10840-10861`): `firstSpeedMs`/`canPark`
   helemaal weglaten — parkeerbaarheid is niet meer route-breed te bepalen.
   `_makeRoutePath` (`main.js:10797-10815`) verliest de `canPark`-parameter; voeg een lazy
   getter `canParkAtEnd` toe die kijkt naar de **laatste** link van de route (nodig voor punt 6).
3. **`weightedOffsetOnPath` uitbreiden** (`main.js:10771-10788`) met een optioneel
   `maxSpeedMs`-filter: alleen links met `speedMs <= maxSpeedMs` komen in de kandidatenpool;
   retourneert `null` als geen enkele link geschikt is. Bestaande aanroepen (zonder 2e argument)
   blijven ongewijzigd gedrag vertonen.
4. **LL-methode** (default, `main.js:11074-11112`): volgorde omdraaien — eerst proberen een
   geparkeerde positie te vinden via `weightedOffsetOnPath(rp.path, PARK_MAX_SPEED_MS)`; alleen
   bij succes `isParked = true`; anders (of bij de parkRatio-worp die niet raakt) normale
   ongefilterde offset.
5. **`link`/`cap`-methodes** (`main.js:10908-10967`, `10968-11031`): deze itereren al per
   concrete link mét bekende `speedMs` (`main.js:10917`, `10978`) vóórdat een auto geplaatst
   wordt — rechttoe-rechtaan `rp.canPark` vervangen door een check op déze link se snelheid.
6. **Car-object veld** (`main.js:10955, 11019, 11101, 11197`): `canPark: rp.canPark` →
   `canPark: rp.canParkAtEnd`.
7. **Runtime-overgang** (`main.js:14513-14518`): niet meer vertrouwen op het gecachete
   `car.canPark`-veld — herbereken direct uit `car.path.links` (laatste link se snelheid). Lost
   zowel de route-brede-vlag-bug als de staleness-bug na route-chaining in één keer op.
   Omdat na deze wijziging niets meer `car.canPark` leest, wordt het veld op het car-object
   verwijderd (geen ongebruikte state achterlaten).

### Edge cases

- Route zonder enige link ≤50 km/u (bv. een zuivere snelwegroute): levert nooit een geparkeerde
  auto op — `weightedOffsetOnPath(..., PARK_MAX_SPEED_MS)` geeft `null`, auto blijft "moving".
- Fietsen: expliciete `!== 'BIKE'`-guard blijft behouden op alle plekken (bestaand gedrag:
  fietsen parkeren niet in de digital twin).
- Links zonder bekende snelheid: bestaande fallback `linkSpeedMap.get(id) ?? 10` (10 m/s ≈ 36
  km/u) blijft gelden — valt al onder de drempel, geen aparte behandeling nodig.
- Eén-link routes en zeer korte routes (<30 m): bestaande filters blijven ongewijzigd van kracht.

### Verificatie

- Geen testharnas voor `main.js` (bevestigd: geen tests onder `digital-twin/`). Handmatige
  controle via de browserconsole na `buildCarList()`:
  ```js
  cars.filter(c => c.state === 'parked')
      .some(c => /* bepaal werkelijke link-snelheid onder c.offset via c.path.boundaries/links */
                 ... > PARK_MAX_SPEED_MS)   // verwacht: false
  ```
- Visueel: geen geparkeerde auto's meer op 60/80/100 km/u-wegen, in alle drie vul-methodes
  (`initFillMethod`: link/cap/LL) en in alle dagdelen (`mrh`/`erh`/`rest`, want `PARK_RATIOS`
  verschilt per dagdeel).
- Sanity-check op de aanname dat `route.linkIds[0]` het punt dichtbij `fromZoneId` is (relevant
  voor Deel B hieronder): vergelijk het eerste/laatste coördinaat van een paar routes met de
  zone-centroïden van `fromZoneId`/`toZoneId`.

---

## Deel B v1 — Eerste stap richting motief-bewust parkeren

### Wat al bestaat en hergebruikt wordt (geen nieuwe databron nodig)

- `route.motifRatio` — motief-verdeling per OD-paar (`work/shopping/recreational/school/
  hospital/parking/other/unclassified`), al aanwezig per route (`main.js:10098`), nu alleen
  gebruikt voor het aggregaat-taartdiagram ("Motiefverdeling").
- `flowDaypart` (`mrh`/`erh`/`rest`) en de bestaande dagdeel-machinerie (`DP_FRACTION`,
  `PARK_RATIOS`) — al overal beschikbaar.
- Routerichting: `route.linkIds` wordt in volgorde gebruikt om `path.boundaries` op te bouwen
  (`main.js:10628-10668`), dus offset 0 ≈ `fromZoneId`-kant, offset 1 ≈ `toZoneId`-kant
  (aanname, te bevestigen — zie verificatie Deel A).

### Ontwerp: U-vormige, dagdeel/motief-gewogen eindbias (alleen LL-methode)

Een geparkeerde auto stelt een voertuig voor dat ofwel nog niet vertrokken is (hoort bij het
herkomst-eind) of al is aangekomen en wacht (hoort bij het bestemmings-eind). In plaats van de
bestaande uniforme flow×lengte-weging over de hele route, introduceren we — alleen voor de
parkeer-poging binnen de LL-methode — een gewicht per kandidaat-link dat:
1. beide uiteinden van de route zwaarder weegt dan het midden (U-vorm), én
2. voor routes met motief `work` tijdens dagdeel `mrh` (ochtendspits) het herkomst-eind extra
   zwaar weegt, en tijdens `erh` (avondspits) het bestemmings-eind — voor alle overige motieven/
   dagdelen blijft de symmetrische U-vorm gelden (al een reële verbetering t.o.v. nu).

Nieuwe functie `weightedParkOffsetOnPath(rp)` naast de bestaande `weightedOffsetOnPath`,
aangeroepen in plaats daarvan op de parkeer-poging-plek in de LL-methode (`main.js:11074-11112`,
zie Deel A punt 4). Richting hoeft niet per route-paar (heen/terug) apart afgehandeld te worden:
een heen- en terugroute zijn al losse `routeList`-items met eigen `motifRatio` en eigen,
dagdeel-geschaalde flow — dezelfde regel toegepast op beide routes onafhankelijk versterkt
vanzelf dezelfde plausibele locatie (bv. "bij het werk" tijdens de avondspits, ongeacht of je
naar de heen- of terugroute kijkt).

### Scope v1 (nu bouwen)

- Alleen de LL-vulmethode (de standaard/meest gebruikte). `link`/`cap` plaatsen auto's al lokaal
  binnen één specifieke link, dus het "auto zweeft midden op de route zonder context"-probleem
  speelt daar minder — uitbreiden daarnaar is een latere, aparte wijziging.
  - Dit is een afwijking van het "fix overal consistent"-instinct: in overleg geaccepteerd omdat
    `link`/`cap` al single-link plaatsing doen en de meeste meerwaarde van de eindbias zit in de
    multi-link LL-route-sampling.
- Alleen motief `work` krijgt een richtingsvoorkeur; alle andere motieven (`shopping`,
  `recreational`, `school`, `hospital`, `parking`, `other`, `unclassified`, of ontbrekend)
  krijgen de neutrale symmetrische U-vorm.
- Geen nieuwe databron, geen wijziging aan `server.py`, geen spatial join met gebouwen.

### Expliciet uitgesteld (eigen vervolgplan, naar analogie van `docs/plan-parkeer-indicator.md`)

- **v2 — winkelen-bij-winkels**: parkeerpositie bias richting links nabij gebouwen die
  `classifyBuilding()` (`main.js:3957-4049`) als `commercial` classificeert, of
  `_isPhysicalParking()`-gebouwen (`main.js:4055-4062`). Vereist een nieuwe link↔gebouw
  ruimtelijke koppeling (bestaat nu niet) en een vertaaltabel tussen `motifRatio`-sleutels en
  `classifyBuilding`-categorieën (niet 1-op-1; bv. `hospital` heeft nu geen eigen bucket).
  Performance-gevoelig op de schaal van tienduizenden routes — vraagt een ruimtelijke index,
  geen lineaire scan per auto.
- **v3 — echte parkeervlak-polygonen**: hergebruik `parking_area_fetcher` (al gebruikt in
  `analyzer/wegenscan_assets.py:98-128`) en het fase-1-patroon uit
  `docs/plan-parkeer-indicator.md` om `assetType=parkingArea` ook voor de digital-twin-bbox te
  fetchen/serveren (vandaag: nul referenties in `digital-twin/server.py`, en `main.js` sluit
  `parkingArea` expliciet uit van de bestaande TRAFFIC-ASSETS-fetch, zie rond `main.js:8265` en
  `main.js:8920`). Pas dan wordt de vaste `PARK_OFFSET_M`-nudge (~3.5 m naast de weg-as,
  `main.js:11241-11258`) heroverwogen, want "geparkeerd binnen een echt parkeervlak" oogt anders
  dan een vaste berm-offset.

---

## Samenvatting kritieke bestanden

- `digital-twin/scripts/main.js` — alle Deel A/B v1-wijzigingen:
  - `2632-2636` (constantes), `10771-10815` (`weightedOffsetOnPath`/`_makeRoutePath`),
    `10840-11114` (`buildCarList`, alle drie vulmethodes), `14480-14524` (runtime-overgangen).
- `docs/plan-parkeer-indicator.md` — referentiepatroon voor het vervolgplan (v2/v3).
- `analyzer/wegenscan_assets.py` — referentie voor hoe `parking_area_fetcher` al wordt aangeroepen (voor v3).
- `digital-twin/server.py` — alleen relevant voor v3 (TRAFFIC-ASSETS fetch-pipeline).
