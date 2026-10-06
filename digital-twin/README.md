# Verkeersnetwerk-visualisatie + maquette-koppeling

Webapplicatie voor het visualiseren en doorrekenen van verkeersmodellen, met een
optionele **fysieke maquette-koppeling**: een camera (of virtuele cursor)
detecteert een zwart blokje op de maquette, sluit het dichtstbijzijnde wegvak af
en rekent het scenario door. De resultaten worden op een MapLibre/deck.gl-kaart
getoond die via een beamer op de maquette geprojecteerd kan worden.

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
  - `opencv-python` (staat al in `requirements.txt`);
  - `shapely` (voor het vinden van het dichtstbijzijnde wegvak);
  - de detectie-/tracking-modules in `kien-camera-maquette/` (`detection.py`,
    `tracking.py` en hun `config.py`) — een lokale, vendored kopie die gewoon
    in deze repo staat, geen extern pad nodig. Bron: het losstaande
    kien-camera-maquette project (GMP/kien-maquette), dat er ook een
    GUI/calibratiepijplijn omheen heeft.

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
2. **Fase 1 — markers.** Het scherm wordt zwart met **vier genummerde markers**,
   die dus op de maquette geprojecteerd worden. In het paneel zie je klein het
   live camerabeeld: richt de camera tot alle vier de markers daarin staan.
   - Met de schuifregelaar **Inzet** schuif je de markers naar binnen of naar
     buiten. Op 0 % staan ze precies op de hoeken van het geprojecteerde vlak.
   - Zorg dat elke marker op een **vlak stuk maquette** valt, niet op een
     gebouw: een marker op een dak ligt hoger dan het grondvlak en trekt de
     calibratie scheef.
3. **Fase 2 — vastleggen.** Klik op **"Beeld vastleggen"**. Er wordt één
   camerabeeld bevroren. Vanaf dat moment maakt het niet meer uit wat de beamer
   toont.
4. **Fase 3 — aanwijzen.** Het stilstaande beeld vult het scherm met vier
   genummerde handvatten erop. Sleep handvat **1** op marker **1**, **2** op
   **2**, enzovoort.
5. Klik op **"Controleren"**: het vastgelegde beeld wordt vervormd over de kaart
   gelegd. Vallen de wegen samen, dan klopt het.
6. Klik op **"Opslaan & camera starten"**. De detectie begint.

Zodra het blokje 3 seconden stil op een plek staat, licht het dichtstbijzijnde
wegvak op en wordt het scenario doorgerekend.

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

Waarom de app markers projecteert in plaats van jou het camerabeeld op de kaart
te laten leggen: het bedienscherm is meestal hetzelfde scherm dat de beamer
projecteert. Een camerabeeld dat je op dat scherm toont, wordt dus mee
geprojecteerd en weer gefilmd — een terugkoppellus. Markers geven bovendien een
scherp mikpunt, terwijl "wegen op wegen leggen" giswerk is.

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
- een **rood kader** om elk gedetecteerd zwart vlak, met een stip op het punt dat
  voor de wegvak-keuze telt. Doorgetrokken = binnen het geprojecteerde gebied,
  gestippeld = erbuiten;
- ligt een vlak buiten het kaartbeeld, dan een **rode pijl langs de rand** die
  ernaar wijst, met de afstand erbij;
- linksonder een **meldingenbalk**: wat er gesignaleerd is en of het meetelt.

**Buiten het geprojecteerde gebied wordt niets afgesloten.** De camera ziet
immers ook maquette waar geen kaart op staat; een positie daar heeft geen
betekenis, en zou anders een willekeurig wegvak sluiten dat niet eens in beeld is.
De meldingenbalk zegt in dat geval waaróm er niets gebeurt, met de positie in het
geprojecteerde vlak erbij (binnen = 0 tot 1 in beide richtingen).

Houd het blokje op de maquette en kijk waar het rode kader verschijnt:

| Wat je ziet | Wat er aan de hand is |
| --- | --- |
| Geen rood kader | De camera herkent het blokje niet (te klein, te weinig contrast, of `cameraId` wijst naar een andere camera). |
| Kader op de juiste plek | Calibratie klopt. Sluit het verkeerde wegvak toch af? Dan ligt het aan de afstandskeuze of aan `--anchor`. |
| Kader **gespiegeld of gedraaid** | Bij het calibreren zijn de handvatten op de verkeerde markers gezet (1 op 2, enzovoort). Opnieuw calibreren. |
| Kader steeds dezelfde kant op verschoven | De projectie is verschoven sinds het calibreren, of de beamer-zoom is veranderd. |
| Randpijl terwijl het blokje midden op de maquette ligt | De calibratie staat ver mis, óf de camera pikt iets ánders zwarts op. Kijk of het rode kader meebeweegt als je het blokje verschuift. |
| Blauwe stippellijn valt samen met het kaartbeeld | Dan ziet de camera precies het geprojecteerde vlak. Is hij veel groter, dan kijkt de camera ruim naast de maquette. |

### Nauwkeurigheid

Drie foutbronnen die de homografie **niet** wegneemt:

- **Markers op een gebouw.** De homografie geldt voor het grondvlak. Valt een
  marker tijdens het calibreren op een gebouwdak, dan ligt dat punt fysiek
  hoger en staat de hele calibratie scheef. Verschuif de markers met de
  **Inzet**-regelaar tot ze alle vier op vlak terrein liggen.
- **Hoogte van het blokje.** De calibratie geldt voor het grondvlak. Standaard
  telt het zwaartepunt van het silhouet als positie, en dat ligt op halve
  blokhoogte — bij een schuine camera dus naast de voetafdruk. Start het script
  met `--anchor bottom` om in plaats daarvan het midden van de onderrand te
  gebruiken, dat wél op het grondvlak ligt.
- **Lensvertekening.** Een groothoeklens buigt rechte lijnen; met precies vier
  punten is dat per constructie onzichtbaar (het residu is dan altijd nul). Zet
  de groothoek-/fisheye-stand van de camera uit als de randen niet willen passen.

---

## Probleemoplossing

| Probleem                                   | Oplossing                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------- |
| "Camera aan" doet ogenschijnlijk niets     | Staat `follow=true` in de URL? Zonder dat komt er geen status/voortgang.  |
| Fysieke camera start niet                  | Controleer `opencv-python` en of `kien-camera-maquette/detection.py`/`tracking.py` naast `maquette_camera.py` staan. |
| Poort 5000 is bezet                        | Start met `server.py --port <andere-poort>`.                              |
| Geen camerabeeld in het calibratiescherm   | Draait de server multi-threaded? Met `--no-threaded` werkt de beeldstream niet. |
| Camerabeeld blijft hangen                  | Het camera-script is gestopt; sluit het calibratiescherm en klik opnieuw op "Camera aan". |
| Markers niet zichtbaar in het vastgelegde beeld | Camera kijkt er langs, of de inzet staat te laag. Klik "Opnieuw vastleggen", richt bij of verhoog de **Inzet**. |
| Verkeerd wegvak wordt afgesloten           | Opnieuw calibreren via `&calibrate=true`; helpt dat niet, probeer dan `--anchor bottom` (zie Nauwkeurigheid). |
| Afgesloten wegvak ligt buiten het kaartbeeld | Kan niet meer: buiten het geprojecteerde gebied wordt niets afgesloten. Zie je toch een randpijl, dan staat de calibratie mis — zie "Controleren of de calibratie klopt". |
| Er gebeurt niets, melding "BUITEN het geprojecteerde gebied" | De camera zet je blokje buiten het vlak dat de beamer toont. Opnieuw calibreren; let erop dat handvat 1 op marker 1 komt. |
