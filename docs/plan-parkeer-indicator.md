# Plan: parkeer-indicator (aanbod van parkeerruimte)

Een nieuwe kaartlaag + achterliggende data-pipeline die inzicht geeft in het
**parkeeraanbod**: waar kán er langs de weg geparkeerd worden, en hoeveel
capaciteit bieden parkeervlakken en (later) private terreinen. Dit wordt de
basis voor een "parkeer-indicator" per straat/gebied.

Scope van dit plan is nadrukkelijk **gefaseerd** — fase 1 t/m 3 zijn met de
huidige data (grotendeels) te bouwen; fase 3b vraagt om een kleine uitbreiding
van de fetch-pijplijn; fase 4 en 5 vragen om verdere samenvoeging respectievelijk
nieuwe databronnen/handmatige verrijking.

```
NETWORK-CAR ──(speed/road_category/profile)──┐
TRAFFIC-ASSETS (parkingArea, E-borden) ───────┼─► parkeer-engine ─► parkeer-collectie(s)
BUILDINGS (footprint/landuse) ─────(later)────┘        + parkeer-indicator per straat/gebied
```

---

## Uitgangspunten / requirements (samengevat uit het gesprek)

1. Langsparkeren alleen tonen op wegen die er "voor bedoeld zijn" — dus **niet**
   op 80/60 km/u-wegen (GOW/stroomweg-achtig), wél op ETW's (30/50 km/u,
   erftoegangswegen).
2. Geen parkeervak binnen **5 m van een kruising** (zichtlijnen/veiligheid).
3. Geen parkeervak ter hoogte van een **parkeerverbod-bord** (RVV E1) of een
   `parking:condition=no`-achtige regel, én rekening houden met de
   **werkingsrichting/lengte** van zo'n bord (borden gelden vanaf het bord tot
   het volgende kruispunt of onderbord-einde).
4. Bij **smalle straten** niet zomaar beide zijden als parkeermogelijkheid
   aanmerken — de rijbaan + eventuele parkeerstroken moeten samen binnen de
   beschikbare wegbreedte passen (langsparkeren ≈ 2 m, haaks/schuin meer).
5. Losstaand van langsparkeren: **parkeervlakken** (P-terreinen, `parkeervlak`
   uit BGT, `amenity=parking` uit OSM) los in kaart brengen.
6. Op termijn ook **off-street bij panden** (SHPV = "search for hidden parking
   volume"-achtig: kan er op eigen terrein geparkeerd worden, bijv. oprit/tuin
   bij een woning) — dit is het minst harde-data-rijke onderdeel en wordt dus
   nadrukkelijk als losse, latere fase behandeld.
7. Eindbeeld: een **parkeer-indicator** die het aanbod samenvat per straat, per
   parkeervlak, en (uiteindelijk) off-street — in die volgorde van prioriteit.

---

## Wat er al is (hergebruiken, niet opnieuw bouwen)

| Onderdeel | Waar | Bruikbaar voor |
| --- | --- | --- |
| `parking_area_fetcher` (gmt_calculation_lib) | haalt `parkeervlak` (BGT `wegdeel`) + `amenity=parking`/`park_ride` (OSM) op als polygonen, met `parkingCapacity` uit OSM `capacity`-tag | **Fase 1**: parkeervlakken-laag (los van de weg) |
| `add_parking.py` (wegenscan) | levert per wegvak `parking_location` (`langsparkeren`/`haaksparkeren`/`op de rijbaan`/`niet van toepassing`) + `parking_width`, o.b.v. NWB `wkd_parkvlak` + fallback-regels op `road_category`/`bicycle_location`/`max_speed` | **Fase 2**: basis voor "mag hier geparkeerd worden" per wegvak |
| `road_category`/`max_speed` (wegenscan) | wegcategorie (ETW/GOW/…) en snelheidslimiet per wegvak | **Fase 2**: snelheids-/categoriefilter (geen 60/80 km/u-wegen) |
| E-serie verkeersborden (traffic_signs_fetcher + NDW-iconen) | `rvvCode` genormaliseerd (o.a. `E1` t/m `E13`), positie + (indien beschikbaar) rijrichting/geldigheidsbord | **Fase 3**: parkeerverbod-zones uitsluiten |
| Netwerktopologie in de frontend (`adj`/`nodeCoords`, `index.html`) | knooppunten + afstand-langs-link | **Fase 3**: 5 m-uitsluiting bij kruisingen en zebra-oversteken |
| `pedestrianCrossing`/`busStop` (TRAFFIC-ASSETS) | puntposities van oversteekplaatsen en bushaltes | **Fase 3**: 5 m-zone rond oversteek/halte |
| `buildings_fetcher` (footprint + `_landuse`) | pand-polygonen + globale landgebruiksclassificatie | **Fase 5** (ruwe eerste heuristiek voor terrein-parkeren) |

Kortom: fase 1–3 zijn vrijwel volledig te bouwen op bestaande, al gefetchte
data. De grootste nieuwe inspanning zit in **combineren or ontbreken** van
attributen (rijbaanbreedte, exacte werkingsrichting van borden) en in het
**client- of server-side samenvoegen** tot één samenhangende parkeer-laag.

---

## Fase 1 — Parkeervlakken tonen (off-street, "niet-langs-de-straat")

Laagste risico, meeste directe waarde, én expliciet genoemd als eerste
categorie in de requirements ("per parkeer-vlak, niet langs de straat").

1. **Data**: `parking_area_fetcher.fetch_parking_areas()` uitvoeren per gebied
   (net als `buildings_fetcher`/`vegetation_fetcher`) en wegschrijven als
   eigen laag in `{areaId}-TRAFFIC-ASSETS.parquet` (assetType `parkingArea`,
   zoals de module zelf al documenteert), of als losse
   `{areaId}-PARKING-AREAS.parquet`.
2. **Server**: nieuwe/uitgebreide OGC-collectie `parking_areas` in `server.py`,
   naar het patroon van `traffic_assets`/`vegetation` (bbox-filter + prepared
   parquet, met Overpass-fallback zoals bij buildings).
3. **Frontend**: nieuwe `PolygonLayer` (net als de vluchtheuvels/refugeArea's),
   met tooltip: bron (BGT/OSM), capaciteit indien bekend, oppervlak (afgeleid
   als capaciteit ontbreekt: `oppervlak / ~12,5 m² per auto` als schatting).
4. **UI**: aan/uit-toggle "Parkeervlakken" in het lagenmenu, kleurcodering op
   capaciteit (bekend vs. geschat) zodat gebruikers meteen zien welke cijfers
   hard zijn.

**Output van deze fase**: een werkende, op zichzelf staande kaartlaag —
onafhankelijk van de latere langsparkeren-logica.

---

## Fase 2 — Langsparkeren: kandidaat-wegvakken bepalen

Doel: per wegvak (of per zijde van een wegvak) bepalen *of* er in principe
langs de weg geparkeerd mag/kan worden, vóórdat we kruisingen en borden
verrekenen.

1. **Snelheids-/categoriefilter**: alleen wegvakken met `max_speed <= 50`
   (en/of `road_category` in `{ETW 30, ETW 50}`) worden kandidaat. GOW/50+
   stroomwegen en alles ≥ 60 km/u vervalt.
2. **`parking_location`-filter**: alleen wegvakken waar wegenscan al
   `langsparkeren` of `haaksparkeren`/`schuinparkeren` aangeeft (niet
   `niet van toepassing` of `op de rijbaan` zonder vak).
3. **Breedte-check (smalle straten)**: reconstrueer de beschikbare
   wegbreedte (`r_road_width`/`profile`) en bepaal hoeveel parkeerstroken
   erbij passen:
   - rijbaan nodig voor 2-richtingverkeer (of 1 bij eenrichting) + minimaal
     1 parkeerstrook (~2 m langsparkeren) → **1 zijde**.
   - rijbaan + 2 parkeerstroken past → **2 zijden**.
   - past zelfs 1 parkeerstrook niet (te smal) → **geen kant**, ondanks een
     "langsparkeren"-label van wegenscan (dat is nl. een categorische
     inschatting, geen garantie).
   - Dit voorkomt precies het genoemde probleem: bij smalle straatjes niet
     zomaar beide kanten aanmerken.
   - Zolang er geen betrouwbare rijbaanbreedte per wegvak is (zie "Open
     vragen"), begint dit met een **conservatieve vuistregel** (bijv. wegen
     < ~5,5 m rijbaanbreedte → hoogstens 1 zijde) die later verfijnd wordt.
4. **Zijde-toewijzing**: bij "1 zijde" moet je kiezen wélke kant. Eerste
   heuristiek: de kant zonder inrit-concentratie/opstelstroken (zie
   `TRAFFIC-ASSETS`/`laneMarkArrow` als negatieve indicator), anders default
   rechterzijde in rijrichting (of gewoon: geometrisch de kant met de meeste
   beschikbare wegbermruimte, indien dat ooit beschikbaar komt via BGT
   `wegdeel`/berm-polygonen).

**Output**: per wegvak 0, 1 of 2 kandidaat-parkeerstroken (met zijde-label),
nog zonder rekening te houden met kruisingen of parkeerverbodsborden.

---

## Fase 3 — Uitsluitingen: kruisingen, oversteken, halten en parkeerverbod

Dit zijn de uitsluitingen die met **bestaande** data (geen nieuwe fetch nodig)
gebouwd kunnen worden. RVV 1990 art. 24 kent meer "algemene parkeerverboden"
dan alleen de kruising en het E1-bord; onderstaande lijst is een selectie
daarvan die nu al haalbaar is. Fase 3b (hierna) behandelt de rest.

1. **5 m van een kruising** (RVV art. 24 lid 1 sub i): voor elk
   kandidaat-wegvak (fase 2) de eerste en laatste 5 m langs de lijn uitsluiten
   van de parkeerstrook-geometrie (analoog aan hoe `laneMarkArrow`s al met
   afstand-langs-lijn werken). Bij hele korte wegvakken (< 10 m) resulteert
   dit in "geen parkeerplek" op dat vak.
2. **Zebra-oversteek buiten een kruising** (zelfde 5 m-beginsel als bij
   kruisingen, RVV art. 24): de bestaande `pedestrianCrossing`-punten die
   *niet* op een kruispunt liggen (dus midden op een wegvak) krijgen ook een
   5 m-uitsluitingszone aan weerszijden, langs de lijn. Dit is een direct
   herbruikbare toepassing van dezelfde "afstand-langs-lijn"-logica als punt 1.
3. **Bushalte-zone** (RVV art. 24 lid 1 sub j): rond elk `busStop`-punt een
   uitsluitingszone langs de weg. Omdat er geen haltelengte-geometrie
   beschikbaar is (alleen een punt), begint dit met een **vaste marge**
   (bijv. ±8 m rond het punt) totdat een betere haltelengte bekend is.
4. **Gehandicaptenparkeerplaats (E9/E14)**: deze plekken zijn *gereserveerd*
   en tellen niet mee als algemeen/publiek aanbod. De bordpositie is al
   beschikbaar (E-serie fetch); de betreffende plek wordt **uitgesloten van
   het algemene aanbod** (en optioneel apart getoond als "gereserveerd
   parkeren", los van de hoofd-indicator).
5. **Parkeerverbod (E1/E2 e.a.)**: voor elk E-serie-bord (E1 "verboden te
   parkeren", E2 "verboden stil te staan", eventueel E3–E13 met specifieke
   voorwaarden) een **werkingsvak** bepalen langs het wegvak: vanaf de
   bordpositie tot de eerstvolgende kruising in de aangegeven richting (of
   tot een onderbord met einde-afstand, indien dat gegeven ooit meekomt).
   Dat vak wordt afgetrokken van de kandidaat-parkeerstrook.
   - Zolang de exacte "geldigheidsrichting" van een bord niet betrouwbaar
     bekend is (zie open vragen), begin conservatief: bord sluit het hele
     wegvak (of een vaste marge, bv. 15 m rond het bord) uit, in plaats van
     precies te bereken tot de volgende kruising.
6. **Resultaat samenvoegen**: per wegvak/zijde een resterende
   parkeerstrook-geometrie (kan leeg zijn), plus een geschatte capaciteit
   (`lengte_beschikbaar / 5,5 m` per auto voor langsparkeren; andere kental
   voor haaks/schuin uit `parking_location`).

**Output**: een "op-straat-parkeren"-laag met per segment een concrete
geometrie + geschatte capaciteit — dit is het eerste moment dat we een
harde uitspraak doen over *hoeveel* auto's er ergens passen.

---

## Fase 3b — Aanvullende uitsluitingen (vereisen nieuwe databronnen)

Deze categorieën horen inhoudelijk bij dezelfde RVV art. 24-uitsluitingen,
maar vereisen een **uitbreiding van de fetch-pijplijn** (nieuwe OSM-tags of
een nieuwe correlatiestap) voordat ze automatisch toegepast kunnen worden.
Ze worden daarom als aparte sub-fase behandeld, met per item een concreet
verzoek richting de gmt-library (zelfde stijl als `plan-stress-lagen.md`).

| # | Uitsluiting | Wettelijke basis | Status nu | Voorstel |
| --- | --- | --- | --- | --- |
| 1 | Inritten/uitritten (opritten) | RVV art. 24 lid 1 sub a | ❌ niet gefetcht | Nieuw `KIND_DRIVEWAY` in `osm_asset_fetcher_core.py` (OSM `service=driveway` / `amenity=parking_entrance`), puntgeometrie + vaste marge (bv. ±1 m aan weerszijden van de inrit) |
| 2 | Brandkranen | RVV art. 24 lid 1 sub l | ❌ niet gefetcht | Nieuw `KIND_FIRE_HYDRANT` (OSM `emergency=fire_hydrant`), puntbuffer (~1 m) |
| 3 | Spoorwegovergangen | RVV art. 24 lid 1 sub m ("in de nabijheid") | ❌ niet gefetcht | Nieuw `KIND_LEVEL_CROSSING` (OSM `railway=level_crossing`), puntbuffer — voorlopig dezelfde 5 m-logica als bij kruisingen, totdat een preciezere afstand bepaald is |
| 4 | Ziekenhuis-/hulpdiensten in-/uitgang | RVV art. 24 lid 1 sub k | ⚠️ ruwe gebouw-tag (`amenity=hospital`) aanwezig, maar geen ingang-/inrit-locatie | **Afhankelijk van item 1** (inritten): zodra inritten gefetcht worden, filter op inritten die grenzen aan een `amenity=hospital`-gebouw. Tot die tijd niet automatiseerbaar |
| 5 | C-serie geslotenverklaringen ("verboden in te rijden", bv. C1/C6/C12) | Geen parkeerverbod-artikel, maar wel relevant: een wegvak dat niet ingereden mag worden is ook geen zinvol parkeer-"aanbod" | ⚠️ ruwe bordpunten worden al generiek gefetcht, maar zonder koppel-logica naar wegvakken | Nieuwe correlatiestap: match C-serie bordpunten aan het dichtstbijzijnde wegvak-uiteinde → dat wegvak (in die richting) uitsluiten van de parkeer-berekening |

**Volgorde-advies binnen 3b**: begin met item 1 (inritten) — dit ontgrendelt
meteen ook item 4 (ziekenhuis-uitgang) — gevolgd door 2 en 3 (kleine,
onafhankelijke puntfetches), en item 5 als laatste (vereist een nieuwe
correlatiestap, geen simpele puntfetch).

---

## Fase 4 — Kaartlaag + parkeer-indicator (aggregatie)

1. **Nieuwe deck.gl-laag** `ta-parking-onstreet-deck` (PathLayer/ribbon langs
   de resterende parkeerstrook-geometrie uit fase 3) + de al bestaande
   parkeervlakken-laag (fase 1) samen zichtbaar, met eigen kleur/legenda
   (aanbod op straat vs. vlak).
2. **Aggregatie per straat** (`streetName`/`linkGroup`, of bij ontbreken
   daarvan: aaneengesloten wegvakken met dezelfde naam/wegcategorie):
   som van geschatte capaciteit op straat.
3. **Aggregatie per gebied** (bijv. per buurt/postcode, of per
   getekende zone zoals de bestaande zone-tool): totaal aanbod
   op-straat + parkeervlakken.
4. **Parkeer-indicator (eerste versie)**: simpele kaart/tooltip met
   "geschat aanbod: N plaatsen (M op straat + K in vlakken)" per
   straat/zone — nog **zonder vraagkant** (bezetting/behoefte), dat is
   nadrukkelijk buiten scope van dit plan.

**Output**: de eerste bruikbare "parkeer-indicator", volledig gebaseerd op
aanbod, in de door de gebruiker gevraagde volgorde: per straat → per
parkeervlak → (later) off-street.

---

## Fase 5 — Off-street bij panden (verkennend, lagere prioriteit)

Dit is het minst hard-data-onderbouwde onderdeel en wordt daarom expliciet
als losse, optionele fase behandeld:

1. **Heuristiek 1 (grof)**: pand is `landuse=residential` +
   vrijstaand/twee-onder-een-kap (geometrisch: footprint met veel omliggende
   onbebouwde ruimte binnen het kadastrale/perceel-oppervlak, indien
   perceeldata beschikbaar komt, bv. BGT `pand` + BRK-percelen) →
   waarschijnlijk oprit/eigen terrein.
2. **Heuristiek 2 (beter, meer data nodig)**: OSM `amenity=parking` met
   `access=private`, of `building` met `parking=*`-tags, indien aanwezig in
   de bron. Op dit moment blijkt uit onderzoek dat dit soort tags **niet**
   standaard wordt meegenomen door `buildings_fetcher`/`parking_area_fetcher`
   — dit vereist een uitbreiding van de fetch-queries (zie "Open vragen aan
   de gmt-library" hieronder).
3. **Heuristiek 3 (beeldherkenning, ver weg)**: luchtfoto/AHN-gebaseerde
   detectie van verharde opritten — expliciet **niet** in scope van dit plan,
   alleen genoemd als mogelijk toekomstig spoor.
4. Resultaat: een indicatieve, nadrukkelijk **niet-authoritatieve** laag
   ("mogelijk eigen parkeergelegenheid"), duidelijk visueel onderscheiden van
   de hardere fase 1–4 lagen (bijv. gestreept/transparant), zodat gebruikers
   het verschil in betrouwbaarheid meteen zien.

---

## Open vragen / verzoeken richting databronnen (gmt-library / NWB / OSM-fetch)

Net als in `plan-stress-lagen.md` hieronder een lijst van dingen die we nodig
hebben maar nu (nog) niet (betrouwbaar) beschikbaar zijn:

| Behoefte | Waarom | Status |
| --- | --- | --- |
| Rijbaanbreedte per wegvak (`r_road_width` is nu een KPI-*output*, geen brongegeven) | Fase 2, breedte-check smalle straten | **nieuw, gewenst** |
| Werkingsrichting/-lengte van E-serie borden (vanaf bord tot volgende kruising, of onderbord-afstand) | Fase 3, precies parkeerverbod-vak bepalen i.p.v. hele wegvak uitsluiten | **nieuw, gewenst** |
| `streetName` op wegvak-niveau | Fase 4, aggregatie per straat | **bevestiging nodig** (mogelijk al in ruwe NWB/OSM-data, niet doorgezet) |
| OSM `parking:lane:*` / `parking:condition:*` tags meenemen in fetch | Alternatieve/aanvullende bron voor fase 2/3 die al expliciet per wegzijde parkeerregels beschrijft in OSM | **nieuw, optioneel** (kan veel handwerk in fase 2/3 vervangen waar OSM dit al tagt) |
| OSM `service=driveway` / `amenity=parking_entrance` (inritten) fetchen | Fase 3b #1, en voorwaarde voor 3b #4 (ziekenhuis-uitgang) | **nieuw, gewenst** |
| OSM `emergency=fire_hydrant` fetchen | Fase 3b #2 | **nieuw, optioneel** |
| OSM `railway=level_crossing` fetchen | Fase 3b #3 | **nieuw, optioneel** |
| Correlatie C-serie bordpunten ↔ wegvak-uiteinde | Fase 3b #5 | **nieuw, optioneel** (rekenstap, geen nieuwe fetch — bordpunten zijn al beschikbaar) |
| Haltelengte-geometrie bij bushaltes (i.p.v. alleen een punt) | Fase 3, preciezere bushalte-uitsluitingszone i.p.v. vaste marge | **nieuw, optioneel** |
| Wegberm-geometrie (`berm`) | Fase 2, kant-toewijzing bij smalle straten; ook relevant voor "niet parkeren in de berm" (RVV art. 24 lid 1 sub g) | **nieuw, langere termijn** — geen OSM-equivalent, vereist BGT (bv. `bgt_functioneelgebied`/bermclassificatie) |
| Gele doorgetrokken streep (wegmarkering, parkeerverbod zonder bord) | Fase 3/3b, parkeerverbod puur op basis van markering | **nieuw, langere termijn** — geen OSM-equivalent, vereist BGT-wegmarkeringsdata |
| `amenity=parking` met `access=private`/`parking`-tags op panden | Fase 5 | **nieuw, optioneel** |
| Perceel-/kadastergrenzen (BRK) | Fase 5, onderscheid "eigen terrein" vs. openbare ruimte bij een pand | **nieuw, optioneel** |

---

## Volgorde-advies (samenvatting)

1. Fase 1 — parkeervlakken tonen (snel, direct nuttig, geen nieuwe databehoefte).
2. Fase 2 — kandidaat-wegvakken voor langsparkeren (snelheid/categorie/
   parking_location + conservatieve breedte-vuistregel).
3. Fase 3 — kruising-, zebra-oversteek-, bushalte- en parkeerverbod-
   uitsluitingen (alles met bestaande data; conservatief beginnen bij
   E-borden, verfijnen zodra borden-richting/-lengte beschikbaar is).
4. Fase 3b — aanvullende uitsluitingen die een nieuwe fetch vereisen: eerst
   inritten (ontgrendelt meteen ook de ziekenhuis-uitgang), dan brandkranen
   en spoorwegovergangen, tot slot de C-serie-correlatie.
5. Fase 4 — samenvoegen tot kaartlaag + eerste parkeer-indicator (aanbod
   per straat / per vlak).
6. Fase 5 — off-street bij panden, nadrukkelijk als indicatieve, aparte laag.
