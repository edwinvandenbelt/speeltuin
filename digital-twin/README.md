# Verkeersnetwerk-visualisatie + maquette-koppeling

Webapplicatie voor het visualiseren en doorrekenen van verkeersmodellen, met een
optionele **fysieke maquette-koppeling**: een camera (of virtuele cursor)
detecteert **ArUco-objectmarkers** op de maquette. Elke marker staat voor een
vaste bewerking — wegvak afsluiten, 30 km/u instellen, of +100 productie op de
dichtstbijzijnde zone/link (zie "Objectmarkers" verderop) — en het scenario
wordt doorgerekend. Haal je een marker weg, dan maakt de eerstvolgende
berekening zijn bewerking weer ongedaan. De resultaten worden op een
MapLibre/deck.gl-kaart getoond die via een beamer op de maquette geprojecteerd
kan worden.

---

## Architectuur in het kort

Je start **maar één proces: `server.py`** (de Flask-server).

```
  ┌───────────┐        HTTP / SSE        ┌────────────┐
  │  Browser  │◄────────────────────────►│  server.py │
  │ (kaart /  │                          │  (Flask)   │
  │  beamer)  │   klik "Camera aan"      └─────┬──────┘
  └───────────┘   → POST /maquette/start       │ subprocess.Popen(...)
                                                ▼
                                        ┌───────────────────┐
                                        │ maquette_camera.py │  ← automatisch
                                        │ (camera / cursor)  │     gestart
                                        └───────────────────┘
```

- **`server.py`** — de enige server die je zelf start.
- **`maquette_camera.py`** — start je **nooit handmatig**. De server start dit
  script automatisch als subprocess zodra je in de browser op **"Camera aan"**
  klikt (`POST /maquette/start`). Bij "Camera uit" of het stoppen van de server
  wordt het subprocess weer beëindigd.

---

## Vereisten

- **Windows** (de maquette-modus gebruikt Windows-specifieke API's voor
  cursor- en vensterdetectie).
- **Python 3** met een virtuele omgeving. `start.bat` maakt deze automatisch aan
  en installeert `requirements.txt`.
- Voor de **fysieke camera** (`cameraId=0`) daarnaast:
  - `opencv-python` (staat al in `requirements.txt`, inclusief `cv2.aruco`);
  - `shapely` (voor het vinden van het dichtstbijzijnde wegvak of de
    dichtstbijzijnde zone);
  - de detectie-/tracking-modules in `kien-camera-maquette/` (`detection.py`,
    `tracking.py` en hun `config.py`) — een lokale, vendored kopie die gewoon
    in deze repo staat, geen extern pad nodig. Bron: het losstaande
    kien-camera-maquette project (GMP/kien-maquette), dat er ook een
    GUI/calibratiepijplijn omheen heeft.
- Voor het **printen van objectmarkers** (eenmalig, los van het draaien van de
  camera): `Pillow` (staat al in `requirements.txt`) — zie "Objectmarkers"
  verderop.

> De **virtuele cursor-modus** (`cameraId=-1`) gebruikt geen echte camera, maar
> importeert dezelfde modules.

---

## De server normaal starten (zonder maquette)

**Aanbevolen — via `start.bat`** (maakt/updatet de venv, installeert
requirements en start de server):

```bat
start.bat
```

**Handmatig** (venv al aanwezig):

```bat
.venv\Scripts\python server.py
```

Opties:

| Optie      | Standaard         | Betekenis                                  |
| ---------- | ----------------- | ------------------------------------------ |
| `--port`   | `5000`            | TCP-poort van de server                    |
| `--data`   | scriptmap         | Map met de gegevens (bevat submap `work/`) |

Met `DATA_DIR=<map>` in `.env` wijs je de scenario-map direct aan: die map bevat
dan zelf de scenario-submappen (er komt geen `work/` achter). Dit gaat vóór
`--data`/`work`; `ndw_traffic_signs.json` blijft in de `--data`-map staan.

Open daarna de browser op:

```
http://localhost:5000
```

Kies een gebied in het overzicht en gebruik de applicatie zoals gebruikelijk.

---

## De maquette gebruiken

De server start je op **exact dezelfde manier** als hierboven. De maquette-modus
is puur een kwestie van de juiste **URL-parameters** in de (beamer-)browser.

### 1. Snelste manier — via het overzicht

1. Start de server en open `http://localhost:5000`.
2. Klik in het gebiedsoverzicht op de **`···`**-knop naast het gewenste gebied.
3. Kies **"Maquette"**. De kaart opent meteen in maquette-modus met de virtuele
   cursor als blokje (`cameraId=-1`).

### 2. Handmatig — via de URL

Open de browser met de volgende parameters:

```
http://localhost:5000/?areaId=<ID>&mode=CAR&maquette=true&follow=true&cameraId=-1
```

| Parameter        | Verplicht | Betekenis                                                        |
| ---------------- | --------- | ---------------------------------------------------------------- |
| `areaId`         | ja        | ID van het gebied                                                |
| `mode`           | nee       | `CAR` (standaard), `BIKE` of `PEDESTRIAN`                        |
| `maquette=true`  | ja        | Blok-cursor, panelen verborgen, gebouwen verborgen, camera-knop  |
| `follow=true`    | ja        | Live herladen van resultaten + camera-status + calibratie-feedback |
| `cameraId`       | nee       | `-1` = virtuele cursor (standaard), `0`/`1`/… = fysieke camera    |
| `width`/`height` | nee       | Forceer een vaste viewport-grootte in pixels                     |
| `calibrate=true` | nee       | Open meteen het uitlijnscherm (negeer de opgeslagen calibratie)  |

> Vlaggen mogen als `=true`, `=1`, `=yes` of zonder waarde. In maquette-stand
> staat `follow` automatisch aan; zonder die verbinding komt er geen enkel
> bericht van de camera binnen.
| `bbox`/`polygon` | nee       | Begrens/positioneer de kaart bij het openen                      |

> `follow=true` mag weg: in maquette-stand zet de app hem zelf aan. (Zonder die
> verbinding komt er geen camera-status, geen oplichtend wegvak en geen
> controleweergave binnen.)
>
> Voor een **fysieke camera** vervang je `cameraId=-1` door `cameraId=0` of `1`.

### 3. Camera calibreren — het volledige proces

**Vooraf**, één keer per opstelling:

1. Leg de kaart met de beamer goed op de maquette (tabblad casten of bureaublad
   dupliceren). Zet daarna **zoom, scherpstelling en keystone van de beamer
   vast** — verandert daar later iets aan, dan klopt de calibratie niet meer.
2. Richt de camera grofweg op de maquette.

**Calibreren:**

1. Open de kaart met `&cameraId=<n>&calibrate=true` (of klik op "Camera aan"
   als er nog geen calibratie is). De server start de camera in preview-stand.
2. **Fase 1 — calibratiemarkers.** Het scherm wordt zwart met **vier
   genummerde calibratiemarkers**, die dus op de maquette geprojecteerd
   worden. Dit zijn niet de fysieke objectmarkers (zie "Objectmarkers"
   verderop) maar vier punten die alleen tijdens het calibreren even
   verschijnen, puur om de homografie te bepalen. In het paneel zie je klein
   het live camerabeeld: richt de camera tot alle vier de calibratiemarkers
   daarin staan.
   - Met de schuifregelaar **Inzet** schuif je de calibratiemarkers naar
     binnen of naar buiten. Op 0 % staan ze precies op de hoeken van het
     geprojecteerde vlak.
   - Zorg dat elke marker op een **vlak stuk maquette** valt, niet op een
     gebouw: een marker op een dak ligt hoger dan het grondvlak en trekt de
     calibratie scheef.
3. **Fase 2 — vastleggen.** Klik op **"Beeld vastleggen"**. Er wordt één
   camerabeeld bevroren. Vanaf dat moment maakt het niet meer uit wat de beamer
   toont.
4. **Fase 3 — aanwijzen.** Het stilstaande beeld vult het scherm met vier
   genummerde handvatten erop. Sleep handvat **1** op calibratiemarker **1**,
   **2** op **2**, enzovoort.
5. Klik op **"Controleren"**: het vastgelegde beeld wordt vervormd over de kaart
   gelegd. Vallen de wegen samen, dan klopt het.
6. Klik op **"Opslaan & camera starten"**. De detectie begint.

Leg nu een of meer objectmarkers (zie "Objectmarkers" verderop) op de
maquette. Zodra de tracker een marker stabiel binnen het geprojecteerde
gebied ziet, komt zijn bewerking in de actieve set en wordt het scenario
doorgerekend; haal je de marker weer weg, dan vervalt zijn bewerking.
Meerdere markers tegelijk werken onafhankelijk van elkaar.

De virtuele cursor-modus (`cameraId=-1`) hoeft **niet** gecalibreerd te worden:
de browser geeft de cursorpositie al in kaartcoördinaten door.

---

## Calibratie

De koppeling tussen camerapixels en geografische coördinaten wordt per gebied
opgeslagen in:

```
work/<area_id>/<area_id>-CALIBRATION.json
```

De camera staat doorgaans **schuin** boven de maquette, zodat haar beeld
perspectivisch vervormd is. Vier punten waarvan bekend is waar ze op het scherm
staan én waar ze in het camerabeeld terechtkwamen, leggen een **3×3 homografie**
vast die perspectief, rotatie, schaal en offset in één keer corrigeert. (De
oudste calibratie mat twee tegenoverliggende hoeken op en kon perspectief
principieel niet vangen — daar liep de fout naar de randen van het beeld toe op.)

Waarom de app calibratiemarkers projecteert in plaats van jou het camerabeeld
op de kaart te laten leggen: het bedienscherm is meestal hetzelfde scherm dat
de beamer projecteert. Een camerabeeld dat je op dat scherm toont, wordt dus
mee geprojecteerd en weer gefilmd — een terugkoppellus. Calibratiemarkers
geven bovendien een scherp mikpunt, terwijl "wegen op wegen leggen" giswerk is.

De vier punten worden als fractie van het scherm bewaard. Wat fysiek vastligt is
namelijk de relatie *camerapixel ↔ schermpixel*: de beamer projecteert het
browservenster. Beweegt de kaart, dan worden de geo-punten automatisch opnieuw
berekend en blijft de calibratie geldig.

**Opnieuw calibreren:** voeg `&calibrate=true` toe aan de URL en klik op
"Camera aan", of verwijder het `*-CALIBRATION.json`-bestand. Calibratiebestanden
in het oude formaat blijven gewoon leesbaar.

### Controleren of de calibratie klopt

Zodra de camera draait, laat de kaart live zien wat ze ziet:

- een **blauwe stippellijn** rond het gebied dat de **camera** bestrijkt — dat is
  bijna altijd ruimer dan wat de beamer projecteert;
- een **rood kader** om elke gedetecteerde objectmarker, met zijn label (de
  bewerking) en een stip op het punt dat voor de doel-keuze telt. Doorgetrokken
  = binnen het geprojecteerde gebied, gestippeld = erbuiten;
- ligt een marker buiten het kaartbeeld, dan een **rode pijl langs de rand**
  die ernaar wijst, met de afstand erbij;
- linksonder een **meldingenbalk**: wat er gesignaleerd is en of het meetelt.

**Buiten het geprojecteerde gebied wordt niets aangepast.** De camera ziet
immers ook maquette waar geen kaart op staat; een positie daar heeft geen
betekenis, en zou anders een willekeurig wegvak/zone kiezen dat niet eens in
beeld is. De meldingenbalk zegt in dat geval waaróm er niets gebeurt, met de
positie in het geprojecteerde vlak erbij (binnen = 0 tot 1 in beide richtingen).

Houd een objectmarker op de maquette en kijk waar het rode kader verschijnt:

| Wat je ziet | Wat er aan de hand is |
| --- | --- |
| Geen rood kader | De camera herkent de marker niet (te klein, te ver weg, verkeerde `cameraId`, of beschadigd/gedraaid zodat het ArUco-patroon niet leesbaar is). |
| Kader zonder label, melding "onbekend marker-ID" | De marker is wel gevonden, maar zijn ID zit niet in `aruco_marker_actions.MARKER_ACTIONS` — verkeerde marker geprint, of met het verkeerde dictionary (zie "Objectmarkers"). |
| Kader op de juiste plek | Calibratie klopt. Wordt toch het verkeerde wegvak/zone gekozen? Dan ligt het aan de afstandskeuze of aan `--anchor`. |
| Kader **gespiegeld of gedraaid** | Bij het calibreren zijn de handvatten op de verkeerde calibratiemarkers gezet (1 op 2, enzovoort). Opnieuw calibreren. |
| Kader steeds dezelfde kant op verschoven | De projectie is verschoven sinds het calibreren, of de beamer-zoom is veranderd. |
| Randpijl terwijl de marker midden op de maquette ligt | De calibratie staat ver mis. Kijk of het rode kader meebeweegt als je de marker verschuift. |
| Blauwe stippellijn valt samen met het kaartbeeld | Dan ziet de camera precies het geprojecteerde vlak. Is hij veel groter, dan kijkt de camera ruim naast de maquette. |

### Nauwkeurigheid

Drie foutbronnen die de homografie **niet** wegneemt:

- **Calibratiemarkers op een gebouw.** De homografie geldt voor het grondvlak.
  Valt een calibratiemarker tijdens het calibreren op een gebouwdak, dan ligt
  dat punt fysiek hoger en staat de hele calibratie scheef. Verschuif de
  calibratiemarkers met de **Inzet**-regelaar tot ze alle vier op vlak terrein
  liggen.
- **Hoogte van de objectmarker.** De calibratie geldt voor het grondvlak.
  Standaard telt het zwaartepunt van de marker als positie, en dat ligt op
  halve hoogte van het object waarop hij gemonteerd is — bij een schuine
  camera dus naast de voetafdruk. Start het script met `--anchor bottom` om
  in plaats daarvan het midden van de onderrand te gebruiken, dat wél op het
  grondvlak ligt.
- **Lensvertekening.** Een groothoeklens buigt rechte lijnen; met precies vier
  punten is dat per constructie onzichtbaar (het residu is dan altijd nul). Zet
  de groothoek-/fisheye-stand van de camera uit als de randen niet willen passen.

---

## Objectmarkers

De fysieke tags die je op de maquette legt zijn **ArUco-markers**
(dictionary `DICT_4X4_50`). Elke marker-ID staat voor precies één vaste
bewerking; die koppeling staat in `digital-twin/aruco_marker_actions.py`:

| Marker-ID | Label          | Bewerking                                             |
| --------- | -------------- | ------------------------------------------------------ |
| 0         | Wegvak afsluiten | Capaciteit van de dichtstbijzijnde link → 0            |
| 1         | 30 km/u        | Snelheid van de dichtstbijzijnde link → 30 km/u          |
| 2         | +100 productie | Productie van de dichtstbijzijnde **zone** → +100       |

Elke marker mag maar **één keer tegelijk** op de maquette liggen (er is maar
één tag per bewerking geprint). Meerdere markers tegelijk werken onafhankelijk
van elkaar: samen met het huidige netwerk worden ze in één keer doorgerekend.
Haal je een marker weg, dan vervalt zijn bewerking weer bij de eerstvolgende
berekening — de andere, nog aanwezige markers blijven ongemoeid.

Een nieuwe bewerking toevoegen is één nieuwe regel in `MARKER_ACTIONS` (en, als
het doel een ander type feature is dan een link of een zone, een nieuwe
"dichtstbijzijnde"-helper in `maquette_camera.py`).

### Markers printen

```bat
.venv\Scripts\python generate_aruco_markers.py --size-mm 60 --out-dir aruco_markers
```

Dit levert in `aruco_markers/` op:

- één PNG per marker-ID (`aruco_marker_<id>.png`), met het label eronder;
- één `aruco_markers.pdf` met alle markers op echte mm-schaal (verdeeld over
  zoveel pagina's als nodig) — print dit **op 100%** met "fit to page" uit,
  anders klopt de fysieke maat niet meer.

`--size-mm` (default 60) is de afdrukgrootte van de marker zelf, zonder de
witte rustzone eromheen. Begin met de default, test op de werkelijke
camera-afstand en pas aan: te klein geprint, en de marker valt onder de
`--min-object-area`-drempel of is simpelweg niet scherp genoeg om te
decoderen.

### Monteren

- Plak elke marker plat op een stevig, vlak voorwerp (karton, een houten
  blokje) — niet buigen of plooien, dat vervormt het patroon.
- Vermijd glans/lamineerfolie: een reflectie van de beamer of de camera-flits
  kan de hoekpunten onleesbaar maken.
- Laat de witte rustzone rondom intact; die heeft de ArUco-detector nodig om
  de marker van de achtergrond te onderscheiden.

---

## Probleemoplossing

| Probleem                                   | Oplossing                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------- |
| "Camera aan" doet ogenschijnlijk niets     | Staat `follow=true` in de URL? Zonder dat komt er geen status/voortgang.  |
| Fysieke camera start niet                  | Controleer `opencv-python` en of `kien-camera-maquette/detection.py`/`tracking.py` naast `maquette_camera.py` staan. |
| Poort 5000 is bezet                        | Start met `server.py --port <andere-poort>`.                              |
| Geen camerabeeld in het calibratiescherm   | Draait de server multi-threaded? Met `--no-threaded` werkt de beeldstream niet. |
| Camerabeeld blijft hangen                  | Het camera-script is gestopt; sluit het calibratiescherm en klik opnieuw op "Camera aan". |
| Calibratiemarkers niet zichtbaar in het vastgelegde beeld | Camera kijkt er langs, of de inzet staat te laag. Klik "Opnieuw vastleggen", richt bij of verhoog de **Inzet**. |
| Verkeerd wegvak/zone wordt aangepast        | Opnieuw calibreren via `&calibrate=true`; helpt dat niet, probeer dan `--anchor bottom` (zie Nauwkeurigheid). |
| Aangepast wegvak ligt buiten het kaartbeeld | Kan niet meer: buiten het geprojecteerde gebied wordt niets aangepast. Zie je toch een randpijl, dan staat de calibratie mis — zie "Controleren of de calibratie klopt". |
| Er gebeurt niets, melding "BUITEN het geprojecteerde gebied" | De camera ziet je objectmarker buiten het vlak dat de beamer toont. Opnieuw calibreren; let erop dat handvat 1 op calibratiemarker 1 komt. |
| Geen label bij het rode kader, marker wordt genegeerd | Het ArUco-ID van deze marker staat niet in `aruco_marker_actions.MARKER_ACTIONS` — zie "Objectmarkers". |
