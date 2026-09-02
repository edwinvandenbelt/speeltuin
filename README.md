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
  - de externe detectie-/tracking-modules op het vaste pad
    `C:\sources\GMP\kien-maquette\kien-camera-maquette` (`detection.py`,
    `tracking.py` en hun `config`).

> De **virtuele cursor-modus** (`cameraId=-1`) gebruikt geen echte camera, maar
> importeert dezelfde modules. Zorg dat bovenstaand pad bereikbaar is.

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
| `cameraId`       | nee       | `-1` = virtuele cursor (standaard), `0` = eerste fysieke camera   |
| `width`/`height` | nee       | Forceer een vaste viewport-grootte in pixels                     |
| `recalibrate=true` | nee     | Forceer een nieuwe calibratie (negeer de opgeslagen calibratie)  |
| `bbox`/`polygon` | nee       | Begrens/positioneer de kaart bij het openen                      |

> **Let op:** `follow=true` is nodig. Zonder deze parameter reageren de
> camera-status en de calibratie-voortgang niet, ook al is de camera-knop
> zichtbaar door `maquette=true`.
>
> Voor een **fysieke camera** vervang je `cameraId=-1` door `cameraId=0`.

### 3. Camera starten + calibreren

1. Positioneer/zoom de kaart zoals hij op de maquette geprojecteerd moet worden.
2. Klik op **"Camera aan"**. De server start `maquette_camera.py` automatisch.
3. **Bestaat er nog geen calibratie** voor dit gebied, dan start de
   calibratieprocedure:
   1. **Teken een vierkant** op de kaart met **twee klikken** (een hoek en de
      tegenoverliggende hoek). Dit bepaalt het referentiegebied.
   2. Er verschijnt een **rode stip linksonder**. Zet het blokje (of beweeg de
      cursor) daarop en houd **3 seconden stil**.
   3. De stip springt naar **rechtsboven**. Beweeg het blokje daarheen en houd
      opnieuw **3 seconden stil**.
   4. De calibratie wordt opgeslagen en de **live-detectie start automatisch**.
4. **Bestaat de calibratie al**, dan start de live-detectie meteen.

Zodra het blokje/de cursor 3 seconden stil op een plek staat, licht het
dichtstbijzijnde wegvak op en wordt het scenario doorgerekend.

---

## Calibratie

De koppeling tussen camerapixels en geografische coördinaten wordt per gebied
opgeslagen in:

```
work/<area_id>/<area_id>-CALIBRATION.json
```

De calibratie meet twee tegenoverliggende hoeken op en corrigeert daarmee
offset- en schaalfouten door camerapositie of beamer-uitlijning — nauwkeuriger
dan een simpele aanname dat camerapixels lineair op het beeld mappen.

**Opnieuw calibreren:** voeg `&recalibrate=true` toe aan de URL en klik op
"Camera aan", of verwijder het `*-CALIBRATION.json`-bestand.

---

## Probleemoplossing

| Probleem                                   | Oplossing                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------- |
| "Camera aan" doet ogenschijnlijk niets     | Staat `follow=true` in de URL? Zonder dat komt er geen status/voortgang.  |
| Fysieke camera start niet                  | Controleer `opencv-python` en het pad `...\kien-camera-maquette` (detection/tracking). |
| Poort 5000 is bezet                        | Start met `server.py --port <andere-poort>`.                              |
| Verkeerd wegvak wordt afgesloten           | Opnieuw calibreren via `&recalibrate=true`.                               |
