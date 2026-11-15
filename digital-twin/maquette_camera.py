"""
maquette_camera.py — Fysieke maquette koppeling via camera-detectie
====================================================================

Detecteert ArUco-objectmarkers op de maquette en past het netwerk aan via de
adjust-pipeline. Elke marker-ID staat voor precies één vaste bewerking (zie
`aruco_marker_actions.py` — wegvak afsluiten, 30 km/u, of +100 productie).
Zodra de tracker (tracking.py) een marker als stabiel (ruisvrij) herkent
binnen het geprojecteerde gebied, komt zijn bewerking in de actieve set;
haal je de marker weg, dan vervalt hij weer uit die set. Bij elke wijziging
wordt de **volledige actuele set** in één keer doorgerekend vanaf het vaste
basis-area_id van de sessie — nooit een keten van opeenvolgende deltas, dus
een verwijderde marker maakt zijn eigen bewerking altijd ongedaan zonder de
andere te raken. Het script blijft draaien tot je het met Ctrl+C stopt.

Dit script **calibreert niet zelf**. De camera staat doorgaans schuin boven de
maquette, zodat het beeld perspectivisch vervormd is. Die vervorming wordt in de
browser vastgelegd (`maquette-calibration.js`): daar ligt het live camerabeeld
half-transparant over de kaart en sleept de gebruiker vier hoekpunten tot beide
samenvallen. Het resultaat is een 3x3 homografie in
`work/<area>/<area>-CALIBRATION.json`, die dit script alleen nog inleest.

Die calibratie legt ook het **werkgebied** vast: de vierhoek in het camerabeeld
die de maquette voorstelt: de vierhoek die je bij het calibreren hebt aangewezen.
Alleen dat stuk wordt uitgesneden en aan de detector gevoerd (zie `_roi_polygon`
/ `_apply_roi`). Wat de camera daarbuiten ziet — tafelrand, vloer, muur, de
gebruiker — hoort niet bij de maquette en zou anders meedingen naar een
objectmarker-detectie.

Pas op met het onderscheid tussen die aangewezen vierhoek en het *geprojecteerde
vlak*: de **calibratiemarkers** (de vier punten die de beamer tijdens het
calibreren projecteert, niet te verwarren met de fysieke objectmarkers hier)
liggen met hun inzet binnen de projectie, dus het geprojecteerde vlak is groter
(bij 6% inzet 1,3x, bij 25% ruim 4x in oppervlak). Het werkgebied is standaard
de aangewezen vierhoek; `--mask-region projection` neemt de hele projectie.

Een objectmarker is een afgedrukte ArUco-tag (zie `generate_aruco_markers.py`),
dus een vlak van vaste, bekende afmeting — hoe groot dat er in beeld uitziet
hangt wel af van resolutie en afstand tot de camera. Er is daarom geen
bovengrens aan de objectgrootte. De ondergrens wordt als *percentage van het
gecalibreerde vlak* opgegeven (`--min-object-area`) en niet in pixels, omdat
pixels met resolutie en afstand meeschalen en een percentage niet — zie
`_area_thresholds`.

Twee standen:

* ``--preview``  — stuurt alleen camerabeeld naar de server, geen detectie.
  Draait terwijl de gebruiker in de browser calibreert.
* standaard      — detectie met de opgeslagen calibratie.

Gebruik:
    python maquette_camera.py \\
        --server http://127.0.0.1:5000 \\
        --area-id <uuid> \\
        --mode CAR \\
        --width 1920 --height 1080 \\
        [--camera-id 0] [--preview] [--anchor bottom] [--show-video]

Bij ``--camera-id -1`` (virtuele modus) is er geen camera: de browser post dan
zijn cursorpositie, inclusief de ge-unprojecte lon/lat, naar /maquette/cursor.
Deze modus simuleert één blokje, geen objectmarkers; de ArUco-koppeling
hierboven geldt alleen voor de fysieke camera.

Afhankelijkheden (naast standaard-bibliotheek en opencv/shapely/requests):
    detection.py + tracking.py, vendored (gekopieerd, niet een extern pad) in
    `kien-camera-maquette/` naast dit script. Zie dat project
    (GMP/kien-maquette) voor de bron en de volledige GUI/calibratiepijplijn
    eromheen.
"""

import argparse
import json
import math
import sys
import threading
import time
from pathlib import Path

# Console-uitvoer naar UTF-8 forceren zodat Unicode-tekens (→, …) niet crashen
# op Windows-consoles met een cp1252-codepage.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

import cv2
import numpy as np
import requests

# ---------------------------------------------------------------------------
# Importeer de vendored detectie/tracking-modules uit kien-camera-maquette/,
# een submap van dit project (geen extern pad). Die submap heeft ook een
# eigen `config` module; vandaar het eigen sys.path-entry in plaats van een
# gewone package-import.
# ---------------------------------------------------------------------------

_KIEN_DIR = Path(__file__).resolve().parent / "kien-camera-maquette"
if not (_KIEN_DIR / "detection.py").is_file() or not (_KIEN_DIR / "tracking.py").is_file():
    sys.exit(
        f"[camera] FOUT: {_KIEN_DIR} mist detection.py/tracking.py. "
        "Die submap hoort gewoon in de repo te staan (vendored vanuit "
        "GMP/kien-maquette/kien-camera-maquette)."
    )
if str(_KIEN_DIR) not in sys.path:
    sys.path.insert(0, str(_KIEN_DIR))

import config  # noqa: E402  (kien-camera-maquette/config.py, voor drempelwaarden in logging)
from detection import ArucoMarkerDetector  # noqa: E402
from tracking import DetectionTracker  # noqa: E402

# Coördinaten- en calibratiewiskunde staat in een eigen module zonder
# afhankelijkheden, zodat ze zonder camera-opstelling te testen is.
from maquette_calibration import load_calibration  # noqa: E402

# Vaste koppeling marker-ID -> bewerking; zie het bestand zelf voor de tabel.
from aruco_marker_actions import MARKER_ACTIONS, known_marker_ids  # noqa: E402

# ---------------------------------------------------------------------------
# Network/zones laden en dichtstbijzijnde link/zone vinden
# ---------------------------------------------------------------------------


def load_network_features(server_url: str, area_id: str, mode: str) -> list:
    """
    Haal alle network-features op van de server.
    Geeft een lijst van GeoJSON Feature-dicts terug.
    """
    url = f"{server_url}/collections/network/items?areaId={area_id}&mode={mode}"
    print(f"[camera] Network laden van {url} …")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    features = resp.json().get("features", [])
    print(f"[camera] {len(features)} features geladen.")
    return features


def load_zone_features(server_url: str, area_id: str, mode: str) -> list:
    """
    Haal alle zone-features op van de server (voor de productie-objectmarker).
    Geeft een lijst van GeoJSON Feature-dicts terug; zelfde endpointpatroon
    als `load_network_features`, zie `apiUrl()` in scripts/main.js.
    """
    url = f"{server_url}/collections/zones/items?areaId={area_id}&mode={mode}"
    print(f"[camera] Zones laden van {url} …")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    features = resp.json().get("features", [])
    print(f"[camera] {len(features)} zones geladen.")
    return features


def _extract_coords(geom: dict) -> list[tuple[float, float]]:
    """Geef een platte lijst van (lon, lat) tuples terug uit een GeoJSON-geometrie."""
    gtype = geom.get("type", "")
    coords = geom.get("coordinates", [])
    if gtype == "Point":
        return [tuple(coords[:2])]
    if gtype in ("LineString", "MultiPoint"):
        return [tuple(c[:2]) for c in coords]
    if gtype in ("Polygon", "MultiLineString"):
        return [tuple(c[:2]) for ring in coords for c in ring]
    if gtype == "MultiPolygon":
        return [tuple(c[:2]) for poly in coords for ring in poly for c in ring]
    return []


def find_nearest_link(lon: float, lat: float, features: list) -> list[int] | None:
    """
    Geef de lijst van linkIds terug die afgesloten moeten worden voor het
    dichtstbijzijnde wegvak. Controleert welke richtingen (+id / -id)
    daadwerkelijk in de features zitten zodat niet-bestaande richtingen
    (eenrichtingsverkeer) niet meegestuurd worden naar de adjust-API.

    Geeft een lijst van 1 of 2 integers terug, of None als niets gevonden.
    """
    try:
        from shapely.geometry import Point, shape
    except ImportError:
        print("[camera] FOUT: shapely niet geïnstalleerd. `pip install shapely`")
        return None

    # Verzamel alle linkIds die in het netwerk zitten (met teken)
    known_ids: set[int] = set()
    for feat in features:
        raw = feat.get("properties", {}).get("linkId")
        if raw is not None:
            known_ids.add(int(raw))

    pt = Point(lon, lat)
    best_id: int | None = None
    best_dist = float("inf")

    for feat in features:
        try:
            geom = shape(feat["geometry"])
            dist = pt.distance(geom)
            if dist < best_dist:
                best_dist = dist
                raw_id = feat.get("properties", {}).get("linkId")
                if raw_id is not None:
                    best_id = abs(int(raw_id))
        except Exception:
            continue

    if best_id is None:
        return None

    # Stuur alleen de richtingen mee die ook in het netwerk bestaan
    directions = [d for d in (best_id, -best_id) if d in known_ids]
    return directions if directions else None


def find_nearest_zone(lon: float, lat: float, zone_features: list) -> "str | int | None":
    """
    Geef de `zoneId` van de dichtstbijzijnde zone terug, of None als er geen
    zones zijn (of geen Shapely). Analoog aan `find_nearest_link`, maar zonder
    richting-logica: een zone heeft geen rijrichtingen.
    """
    try:
        from shapely.geometry import Point, shape
    except ImportError:
        print("[camera] FOUT: shapely niet geïnstalleerd. `pip install shapely`")
        return None

    pt = Point(lon, lat)
    best_id: "str | int | None" = None
    best_dist = float("inf")

    for feat in zone_features:
        try:
            geom = shape(feat["geometry"])
            dist = pt.distance(geom)
            if dist < best_dist:
                zone_id = feat.get("properties", {}).get("zoneId")
                if zone_id is not None:
                    best_dist = dist
                    best_id = zone_id
        except Exception:
            continue

    return best_id


def post_adjust(server_url: str, area_id: str, mode: str, changes: "list[dict]") -> str:
    """
    Dien een volledige set netwerkwijzigingen in via de adjust-API.
    Geeft de jobID terug.
    """
    url = f"{server_url}/processes/adjust/execution"
    payload = {
        "inputs": {
            "area_id": area_id,
            "mode": mode,
            "changes": changes,
        }
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    job_id = resp.json().get("jobID") or resp.json().get("jobId")
    if not job_id:
        raise ValueError(f"Geen jobID in respons: {resp.text[:200]}")
    return job_id


def poll_job(server_url: str, job_id: str, timeout: float = 300.0) -> dict:
    """
    Poll /jobs/{job_id} tot status successful of failed.
    Geeft het volledige job-dict terug.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{server_url}/jobs/{job_id}", timeout=10)
        resp.raise_for_status()
        job = resp.json()
        status = job.get("status", "")
        if status in ("successful", "failed"):
            return job
        time.sleep(1.5)
    raise TimeoutError(f"Job {job_id} niet klaar na {timeout}s")


# ---------------------------------------------------------------------------
# Achtergrond-thread: adjust uitvoeren en area_id bijwerken
# ---------------------------------------------------------------------------


class _AdjustRunner:
    """
    Voert adjust-aanroepen uit in een achtergrondthread zodat de camera-loop
    niet blokkeert, en bewaakt dat er nooit twee tegelijk lopen.

    Elke aanroep dient de **volledige actuele set** objectmarker-bewerkingen
    in, vanaf het vaste basis-area_id van de sessie (`_base_area_id`) — nooit
    een keten van deltas op elkaar. Wordt `submit()` aangeroepen terwijl er al
    een job loopt, dan onthoudt dit de nieuwste gewenste set ("laatste wint",
    zelfde patroon als `_DetectionSender`/`_PreviewPublisher` hieronder) en
    start die meteen na afloop van de lopende job.

    `_display_area_id` is apart: dat is het laatst berekende scenario, voor
    weergave op de kaart (heartbeat/detecties) — niet de bron voor de
    volgende indiening.
    """

    def __init__(self, server_url: str, mode: str):
        self.server_url = server_url
        self.mode = mode
        self._area_id_lock = threading.Lock()
        self._base_area_id: str = ""
        self._display_area_id: str = ""
        self._state_lock = threading.Lock()
        self._busy = threading.Event()
        self._pending: "tuple[list[dict], object, object] | None" = None

    def set_initial_area_id(self, area_id: str) -> None:
        with self._area_id_lock:
            self._base_area_id = area_id
            self._display_area_id = area_id

    def get_area_id(self) -> str:
        """Area_id voor weergave (heartbeat/detecties): het laatst berekende scenario."""
        with self._area_id_lock:
            return self._display_area_id

    def is_busy(self) -> bool:
        return self._busy.is_set()

    def submit(self, changes: "list[dict]", on_started=None, on_done=None) -> None:
        """Dien `changes` in als de volledige huidige set bewerkingen.

        Loopt er al een job, dan wordt dit de nieuwste gewenste set en start
        er direct na afloop daarvan een nieuwe job mee.
        """
        with self._state_lock:
            if self._busy.is_set():
                self._pending = (changes, on_started, on_done)
                return
            self._busy.set()
        self._start(changes, on_started, on_done)

    def _start(self, changes: "list[dict]", on_started, on_done) -> None:
        with self._area_id_lock:
            base_area_id = self._base_area_id
        t = threading.Thread(
            target=self._run, args=(base_area_id, changes, on_started, on_done), daemon=True
        )
        t.start()

    def _run(self, base_area_id: str, changes: "list[dict]", on_started, on_done) -> None:
        job_id = None
        try:
            print(f"[camera] POST adjust: area={base_area_id} changes={changes}")
            job_id = post_adjust(self.server_url, base_area_id, self.mode, changes)
            print(f"[camera] Job gestart: {job_id}")
        except Exception as exc:
            print(f"[camera] Fout bij starten van adjust: {exc}")
        finally:
            # Ongeacht succes/falen van de POST: de aanroeper mag nu al
            # verder, zonder op de uitkomst van de berekening te wachten.
            if on_started:
                try:
                    on_started()
                except Exception:
                    pass
        if job_id is not None:
            try:
                job = poll_job(self.server_url, job_id)
                if job["status"] == "successful":
                    # GET /jobs/{id} geeft geen _results terug (bewust gestript);
                    # haal de resultaten op via het aparte /results-endpoint.
                    results_resp = requests.get(
                        f"{self.server_url}/jobs/{job_id}/results", timeout=10
                    )
                    results_resp.raise_for_status()
                    results = results_resp.json()
                    new_area_id = results.get("new_area_id", base_area_id)
                    with self._area_id_lock:
                        self._display_area_id = new_area_id
                    print(f"[camera] Bewerkingen bijgewerkt. Nieuw area_id: {new_area_id}")
                else:
                    log = "\n".join(job.get("log", [])[-5:])
                    print(f"[camera] Adjust mislukt (job {job_id}):\n{log}")
            except Exception as exc:
                print(f"[camera] Fout bij adjust: {exc}")
        if on_done:
            try:
                on_done()
            except Exception:
                pass

        # Is er tijdens deze job een nieuwere gewenste set binnengekomen, dien
        # die dan nu in - nooit meer dan één job tegelijk.
        with self._state_lock:
            pending = self._pending
            self._pending = None
            if pending is None:
                self._busy.clear()
        if pending is not None:
            self._start(*pending)


# ---------------------------------------------------------------------------
# Browser openen + heartbeat via SSE
# ---------------------------------------------------------------------------

_HEARTBEAT_INTERVAL = 5  # seconden tussen heartbeats


def _send_heartbeat(server_url: str, area_id: str, active: bool) -> None:
    """Stuur één heartbeat naar de server (best-effort, nooit exception)."""
    try:
        requests.post(
            f"{server_url}/maquette/heartbeat",
            json={"area_id": area_id, "active": active},
            timeout=3,
        )
    except Exception:
        pass


_PREVIEW_DELAY = 2.0  # seconden tussen oplichten en starten van de berekening

# Hoe vaak de gevonden objectmarkers naar de browser gaan. 5x per seconde is
# vloeiend genoeg om een marker te volgen en belast de server nauwelijks.
_DETECTIONS_INTERVAL = 0.2


class _DetectionSender:
    """Stuurt de gevonden objectmarkers naar de browser, buiten de framelus om.

    Hiermee kun je op de kaart zien wát de camera ziet en wáár ze denkt dat het
    ligt — zonder dat er iets wordt aangepast. Dat is het enige middel om een
    scheve calibratie te herkennen: ligt de marker op de kaart ergens anders
    dan op de maquette, dan klopt de calibratie niet.

    Eén slot met "laatste wint", net als bij de preview-beelden: een trage of
    even bezette server mag de detectie nooit laten haperen.
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._pending: "tuple[str, str, dict] | None" = None
        self._thread: "threading.Thread | None" = None

    def send(self, server_url: str, area_id: str, payload: dict) -> None:
        with self._cond:
            self._pending = (server_url, area_id, payload)
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()
            self._cond.notify()

    def _loop(self) -> None:
        session = requests.Session()
        while True:
            with self._cond:
                while self._pending is None:
                    self._cond.wait()
                server_url, area_id, payload = self._pending
                self._pending = None
            try:
                session.post(
                    f"{server_url}/maquette/detections",
                    json={"area_id": area_id, **payload},
                    timeout=2,
                )
            except Exception:
                pass  # een gemiste controleweergave is niet erg


_detection_sender = _DetectionSender()


def _send_detections(
    server_url: str,
    area_id: str,
    detections: list,
    camera_view: "list | None" = None,
) -> None:
    """Zie _DetectionSender — niet-blokkerend.

    `camera_view` zijn de vier hoeken van het camerabeeld in (lon, lat). Daarmee
    kan de kaart tonen hoe ver de camera kijkt — doorgaans een stuk ruimer dan
    wat de beamer projecteert, en precies daar zit de verwarring.
    """
    payload: dict = {"detections": detections}
    if camera_view:
        payload["camera_view"] = camera_view
    _detection_sender.send(server_url, area_id, payload)


def _send_preview(server_url: str, area_id: str, link_ids: list[int]) -> None:
    """Stuur een preview-event naar de server zodat de browser het wegvak laat
    oplichten vóór de berekening start. Best-effort, nooit exception."""
    try:
        requests.post(
            f"{server_url}/maquette/preview",
            json={"area_id": area_id, "link_ids": link_ids},
            timeout=3,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Calibratie: server-communicatie
# ---------------------------------------------------------------------------


def _fetch_calibration(server_url: str, area_id: str, mode: str):
    """Haal de calibratie op van de server. None als er geen is.

    Calibreren gebeurt volledig in de browser (`maquette-calibration.js`): daar
    wordt het camerabeeld over de kaart gelegd en met vier sleeppunten passend
    gemaakt. Dit script leest het resultaat alleen.
    """
    try:
        resp = requests.get(
            f"{server_url}/maquette/calibration",
            params={"area_id": area_id, "mode": mode},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("exists") and data.get("calibration"):
            return load_calibration(data["calibration"])
    except Exception as exc:
        print(f"[camera] Calibratie ophalen mislukt: {exc}")
    return None


def _start_heartbeat_thread(
    server_url: str, runner: "_AdjustRunner", stop_event: threading.Event
) -> None:
    """Start een daemon-thread die elke HEARTBEAT_INTERVAL seconden een heartbeat stuurt.

    Gebruikt runner.get_area_id() zodat de heartbeat altijd naar het actuele
    area_id gaat, ook nadat een adjust een nieuw area_id heeft opgeleverd.
    """

    def _loop():
        while not stop_event.wait(_HEARTBEAT_INTERVAL):
            _send_heartbeat(server_url, runner.get_area_id(), active=True)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Virtuele camera: cursorpositie uit de browser (camera_id == -1)
# ---------------------------------------------------------------------------

# Stabilititeitsdrempel in pixels: cursor mag dit veel bewegen en telt nog als
# "stilstaand". Eigen, eenvoudiger stabiliteitscheck dan DetectionTracker
# hieronder gebruikt: hier is maar één (virtueel) object, dus is er geen
# matching tussen meerdere tracks nodig.
_VIRTUAL_STABILITY_PX = 10

# Een cursorsample ouder dan dit betekent: muis staat stil buiten de kaart, of
# de browser is weg. In beide gevallen mag er niets getriggerd worden.
# De browser post nu 1x/seconde (CURSOR_SEND_INTERVAL_MS in
# maquette-calibration.js); deze drempel moet ruim daarboven liggen, anders
# reset de stabiliteitsteller tussen twee posts in.
_CURSOR_MAX_AGE = 1.5


def _fetch_cursor(session: requests.Session, server_url: str) -> "dict | None":
    """Haal de laatst gemelde cursorpositie op, of None als die er niet (meer) is.

    De browser post zijn cursor inclusief de ge-unprojecte lon/lat. Dat is exact:
    de browser kent de kaartweergave, terwijl het uitlezen van de Windows-cursor
    een DPI-correctie en een correctie voor de browserbalken zou vergen (de
    client-area van het venster bevat namelijk ook tabbladen en adresbalk).
    """
    try:
        resp = session.get(f"{server_url}/maquette/cursor", timeout=2)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    if not data.get("available"):
        return None
    if float(data.get("age", 999)) > _CURSOR_MAX_AGE:
        return None
    return data


def _run_virtual(
    server_url: str,
    area_id: str,
    mode: str,
    features: list,
    stable_seconds: float,
    cooldown_seconds: float,
    runner: "_AdjustRunner",
) -> None:
    """
    Cursor-tracking voor de virtuele camera-modus (camera_id == -1).

    De cursor stelt het zwarte blokje voor (al ingesteld door ?maquette=true).
    Na `stable_seconds` zonder beweging wordt de dichtstbijzijnde weg afgesloten.

    Er is hier geen calibratie nodig: de browser levert de positie al in
    kaartcoordinaten aan.
    """
    print("[camera] Virtuele camera: cursor uit de browser wordt als blokje gebruikt.")

    session = requests.Session()
    triggered_links: set[int] = set()
    cooldown_until: float = 0.0

    stable_pos: "tuple[float, float] | None" = None  # positie waar stabiliteit begon
    stable_since: float = 0.0
    last_log_second: int = -1
    warned_no_cursor = False

    print(
        f"[camera] Cursor-tracking gestart. Stabiel na {stable_seconds}s, "
        f"cooldown {cooldown_seconds}s."
    )
    print("[camera] Druk op Ctrl+C om te stoppen.")

    INTERVAL = 1 / _CAMERA_FPS  # zelfde framerate als de fysieke camera, niet sneller

    try:
        while True:
            t0 = time.time()
            cursor = _fetch_cursor(session, server_url)

            if cursor is None:
                # Geen verse cursor: stabiliteit resetten, niet triggeren.
                if not warned_no_cursor:
                    print(
                        "[camera] Wachten op cursorpositie uit de browser "
                        "(staat de kaart open met ?maquette=true&follow=true?)"
                    )
                    warned_no_cursor = True
                stable_pos = None
                time.sleep(INTERVAL)
                continue
            warned_no_cursor = False

            cx, cy = float(cursor["x"]), float(cursor["y"])
            lon, lat = float(cursor["lon"]), float(cursor["lat"])
            now = time.time()

            # Stabiliteitscheck op schermpixels: een drempel in pixels is
            # betekenisvol, een drempel in graden niet (die hangt van de zoom af).
            if stable_pos is None:
                stable_pos = (cx, cy)
                stable_since = now
            elif math.hypot(cx - stable_pos[0], cy - stable_pos[1]) > _VIRTUAL_STABILITY_PX:
                stable_pos = (cx, cy)
                stable_since = now

            duration = now - stable_since

            # Progress-feedback elke seconde
            cur_second = int(duration)
            if cur_second != last_log_second and cur_second > 0:
                last_log_second = cur_second
                print(
                    f"[camera] Cursor stabiel {duration:.1f}s  "
                    f"px=({cx:.0f},{cy:.0f})  "
                    f"wgs84=({lon:.6f},{lat:.6f})"
                )
            elif cur_second == 0:
                last_log_second = 0

            in_cooldown = now < cooldown_until
            adjust_busy = runner.is_busy()

            if duration >= stable_seconds and not in_cooldown and not adjust_busy:
                link_ids = find_nearest_link(lon, lat, features)

                if link_ids is None:
                    print("[camera] Geen link gevonden nabij cursor.")
                elif any(lid in triggered_links for lid in link_ids):
                    pass  # stil laten: al afgesloten
                else:
                    print(
                        f"[camera] Cursor {stable_seconds}s stabiel op "
                        f"({lon:.6f}, {lat:.6f}) -> links {link_ids} oplichten, "
                        f"berekening over {_PREVIEW_DELAY}s ..."
                    )
                    triggered_links.update(link_ids)
                    cooldown_until = now + cooldown_seconds
                    _send_preview(server_url, runner.get_area_id(), link_ids)
                    time.sleep(_PREVIEW_DELAY)
                    _adjust_started = threading.Event()
                    runner.submit(
                        [{"linkId": lid, "capacity": 0} for lid in link_ids],
                        on_started=_adjust_started.set,
                    )
                    _adjust_started.wait()
                    print(
                        "[camera] Berekening gestart - camera wordt nu al uitgeschakeld. "
                        "Zet 'm handmatig weer aan voor een volgende meting."
                    )
                    return

            elapsed = time.time() - t0
            time.sleep(max(0.0, INTERVAL - elapsed))

    except KeyboardInterrupt:
        print("\n[camera] Gestopt.")


# ---------------------------------------------------------------------------
# Hoofdlus (fysieke camera)
# ---------------------------------------------------------------------------


class _PreviewPublisher:
    """Stuurt camerabeelden naar de server zodat de browser kan calibreren.

    Draait als daemon-thread met een slot voor precies een frame: staat er al
    een frame klaar dat nog niet verstuurd is, dan wordt dat overschreven. Zo
    kan een trage POST de camera-uitleeslus nooit ophouden.
    """

    # 12 fps is ruim genoeg om een vierhoek op zijn plaats te slepen, en houdt
    # de JPEG-encodering en de netwerklast bescheiden.
    INTERVAL = 1 / 12

    def __init__(self, server_url: str):
        self.server_url = server_url
        self._cond = threading.Condition()
        self._pending: "tuple[bytes, int, int] | None" = None
        self._stop = False
        self._last_offer = 0.0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def offer(self, frame) -> None:
        """Bied een frame aan (niet-blokkerend, throttled, laatste wint)."""
        now = time.time()
        if now - self._last_offer < self.INTERVAL:
            return
        self._last_offer = now
        try:
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        except Exception:
            return
        if not ok:
            return
        height, width = frame.shape[:2]
        with self._cond:
            self._pending = (buf.tobytes(), width, height)
            self._cond.notify()

    def stop(self) -> None:
        with self._cond:
            self._stop = True
            self._cond.notify()

    def _loop(self) -> None:
        session = requests.Session()
        while True:
            with self._cond:
                while self._pending is None and not self._stop:
                    self._cond.wait()
                if self._stop:
                    return
                data, width, height = self._pending
                self._pending = None
            try:
                session.post(
                    f"{self.server_url}/maquette/frame",
                    params={"w": width, "h": height},
                    data=data,
                    headers={"Content-Type": "image/jpeg"},
                    timeout=5,
                )
            except Exception:
                pass  # een gemist previewframe is niet erg


def run_preview(server_url: str, camera_id: int, width: int, height: int) -> None:
    """Preview-stand: alleen camerabeeld doorgeven, geen detectie.

    Wordt gebruikt terwijl de gebruiker in de browser het camerabeeld over de
    kaart legt en de vier hoekpunten versleept.
    """
    if camera_id < 0:
        print("[camera] Preview-stand vereist een fysieke camera (--camera-id >= 0).")
        return

    cap = _open_camera(camera_id, width, height)
    if cap is None:
        sys.exit(1)

    publisher = _PreviewPublisher(server_url)
    frame_h, frame_w = 0, 0
    print("[camera] Preview gestart - calibreer nu in de browser. Ctrl+C stopt.")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            if not frame_w:
                frame_h, frame_w = frame.shape[:2]
                print(f"[camera] Previewresolutie: {frame_w}x{frame_h}")
            publisher.offer(frame)
    except KeyboardInterrupt:
        print("\n[camera] Preview gestopt.")
    finally:
        publisher.stop()
        cap.release()


# Framerate van de fysieke camera. Ook de virtuele cursor-modus (_run_virtual)
# polt niet sneller dan dit: een echte camera levert toch niet meer op.
_CAMERA_FPS = 10


def _open_camera(camera_id: int, width: int, height: int):
    """Open een fysieke camera. Geeft None als dat niet lukt."""
    print(f"[camera] Camera {camera_id} openen ...")
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"[camera] FOUT: camera {camera_id} kon niet geopend worden.")
        return None
    cap.set(cv2.CAP_PROP_FPS, _CAMERA_FPS)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


# ---------------------------------------------------------------------------
# Uitsnede: alleen het gecalibreerde vlak aan de detector voeren
# ---------------------------------------------------------------------------
#
# De camera ziet meer dan de maquette: tafelrand, vloer, muur, kabels, de
# gebruiker. Daar hoort geen objectmarker gevonden te worden, en het scheelt
# de ArUco-detector onnodig werk op pixels die toch nooit meetellen.
#
# De calibratie kent de omtrek van het geprojecteerde vlak in camerapixels
# (`projection_polygon`). Alles daarbuiten wordt vóór de detectie vervangen door
# de gemiddelde kleur van wat er binnen ligt — een vlakke vulling zonder
# randen of patroon, zodat de uitsnede zelf nooit als marker wordt gelezen.


def _roi_polygon(
    calibration, margin: float, region: str = "picked"
) -> "list[list[float]] | None":
    """De uit te snijden vierhoek in camerapixels, of None als die er niet is.

    `region` bepaalt wat het werkgebied is:

    * ``picked`` (default) — de vierhoek die je tijdens het calibreren hebt
      aangewezen. Dát is wat je hebt afgebakend als maquette.
    * ``projection`` — het hele vlak dat de beamer projecteert. Dat is groter:
      de markers liggen met hun inzet erbinnen, dus bij 6% inzet 1,3x en bij
      25% ruim 4x in oppervlak. Alleen zinvol als de maquette echt tot aan de
      rand van de projectie doorloopt.

    Legacy-calibraties (bilineair) kennen geen vlak; dan blijft het hele beeld
    in gebruik, zoals voorheen.
    """
    getter = getattr(
        calibration,
        "projection_polygon" if region == "projection" else "picked_polygon",
        None,
    )
    if getter is None:
        return None
    try:
        polygon = getter(margin)
    except ValueError:
        return None
    if not polygon or len(polygon) != 4:
        return None
    # Een bijna-ontaarde homografie kan hoekpunten op de horizon leggen; die
    # zouden als astronomisch grote coördinaten terugkomen. Afkappen op een ruim
    # veelvoud van het beeld houdt fillPoly werkbaar.
    limit = 1e5
    if any(not math.isfinite(v) or abs(v) > limit for p in polygon for v in p):
        return None
    return [[float(p[0]), float(p[1])] for p in polygon]


def _roi_mask(frame_shape, polygon: "list[list[float]]"):
    """Binair masker (255 binnen de vierhoek) ter grootte van het frame.

    Geeft None als de vierhoek geen enkele pixel van het beeld raakt — dan is er
    niets uit te snijden en klopt de calibratie niet bij deze camerastand.
    """
    height, width = frame_shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    pts = np.round(np.array(polygon, dtype=np.float64)).astype(np.int32)
    cv2.fillPoly(mask, [pts], 255)
    covered = int(cv2.countNonZero(mask))
    if covered == 0:
        return None
    return mask


def _apply_roi(frame, mask):
    """Vervang alles buiten het masker door de gemiddelde kleur binnen."""
    fill = cv2.mean(frame, mask=mask)[:3]
    out = np.empty_like(frame)
    out[:] = [int(round(c)) for c in fill]
    cv2.copyTo(frame, mask, out)
    return out


# ---------------------------------------------------------------------------
# Objectgrootte: hoe klein mag een objectmarker zijn om nog te tellen
# ---------------------------------------------------------------------------
#
# Alleen een ondergrens, om ruis en losse foutdetecties te weren. Een
# bovengrens is er niet: een objectmarker is een afgedrukte ArUco-tag van
# vaste fysieke afmeting (zie generate_aruco_markers.py --size-mm), maar hoe
# groot die in beeld staat hangt volledig af van resolutie en afstand tot de
# camera.
#
# Die ondergrens in vaste pixels uitdrukken is een slechte maat, om dezelfde
# reden: dezelfde marker beslaat bij een andere resolutie of afstand een ander
# aantal pixels. Als *fractie van het gecalibreerde vlak* is dat getal wél
# stabiel — marker en geprojecteerd vlak schalen samen mee.

# Alleen een ondergrens, laag genoeg om ruis en losse foutdetecties te weren.
# Er is bewust géén bovengrens: hoe groot de marker is doet er niet toe. Wat
# te groot is om de marker te zijn valt af op de uitsnede
# (ROI_MIN_MARKER_COVERAGE) of op de ArUco-fit zelf, niet op een getal — een
# plafond kostte eerder juist de detectie die we zochten.
_DEFAULT_MIN_OBJECT_AREA_PCT = 0.1


def _area_thresholds(
    roi_area_px: float,
    min_pct: float,
    min_override: "float | None",
    max_override: "float | None",
) -> tuple[float, float]:
    """Reken het percentage om naar een contouroppervlak in pixels.

    De bovengrens is oneindig tenzij er expliciet één is meegegeven.
    """
    min_area = max(1.0, roi_area_px * min_pct / 100.0)
    if min_override is not None:
        min_area = float(min_override)
    max_area = math.inf if max_override is None else float(max_override)
    return min_area, max_area


def _format_area_range(min_area: float, max_area: float) -> str:
    """De toegestane grootte, leesbaar — ook als er geen bovengrens is."""
    if math.isinf(max_area):
        return f"vanaf {min_area:.0f} px², geen bovengrens"
    return f"{min_area:.0f}-{max_area:.0f} px²"


# Niet vaker dan dit een samenvatting van afgewezen vlakken tonen.
_REJECT_LOG_INTERVAL = 3.0

# Pas een gewijzigde set objectmarker-bewerkingen indienen nadat ze dit lang
# ongewijzigd is gebleven. Voorkomt een nieuwe adjust-aanroep per frame zodra
# een marker een stukje schuift; de tracker filtert ruis al uit, dit is puur
# een extra marge tegen te gretig herindienen.
_RECOMPUTE_DEBOUNCE = 1.0


def _is_reportable_rejection(evaluation: dict) -> bool:
    """Is deze afwijzing het melden waard?

    `outside_roi` is dat niet. Die vlakken liggen buiten het afgebakende gebied
    en zijn daarmee geen bijna-detectie maar ruis: de tafelrand, een kabel, een
    stoel. Ze in beeld of in de log tonen wekt precies de verkeerde indruk —
    namelijk dat ze meetellen.
    """
    return not evaluation.get("accepted") and evaluation.get("reason") != "outside_roi"


def _log_rejections(evaluations: list, min_area: float, max_area: float) -> None:
    """Vertel waaróm er niets gevonden is.

    Zonder dit is een verkeerde drempel onzichtbaar: de detector zwijgt even
    hard bij "niets in beeld" als bij "de marker is vier keer te groot
    bevonden". De reden en het gemeten oppervlak maken dat verschil zichtbaar.
    """
    rejected = [e for e in evaluations if _is_reportable_rejection(e)]
    if not rejected:
        return
    by_reason: dict[str, list[dict]] = {}
    for item in rejected:
        by_reason.setdefault(item.get("reason", "onbekend"), []).append(item)
    parts = []
    for reason, items in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        biggest = max(items, key=lambda it: float(it.get("raw_area", 0.0)))
        detail = f"grootste {float(biggest.get('raw_area', 0.0)):.0f} px²"
        # Bij "unknown_marker_id" is er wél een geldige ArUco-marker gevonden,
        # alleen niet een met een gedefinieerde bewerking - de gezien ID's
        # tonen meteen of het om het verkeerde dictionary, een beschadigde tag
        # of gewoon een verkeerd geprinte marker gaat.
        if reason == "unknown_marker_id":
            seen_ids = sorted(
                {it.get("marker_id") for it in items if it.get("marker_id") is not None}
            )
            detail += f", gezien ID's {seen_ids} (verwacht: {sorted(known_marker_ids())})"
        parts.append(f"{reason}x{len(items)} ({detail})")
    print(
        f"[camera] Niets geaccepteerd; toegestaan "
        f"{_format_area_range(min_area, max_area)}. " + ", ".join(parts[:3])
    )


def _with_smoothed_position(det: dict) -> dict:
    """Vervang center/bbox/polygon door de gladgestreken (EMA) variant van de
    tracker, voor weergave op de kaart.

    De rauwe per-frame fit wiebelt een paar pixels, ook als de marker
    doodstil ligt - zonder dit sprong het getekende vlak op de kaart elk
    frame een beetje mee. De stabiliteitsbepaling in `tracking.py` blijft wel
    op de rauwe posities rekenen, dus echte beweging wordt hier niet
    gemaskeerd.
    """
    merged = dict(det)
    if det.get("smoothed_center") is not None:
        merged["center"] = det["smoothed_center"]
    if det.get("smoothed_bbox"):
        merged["bbox"] = det["smoothed_bbox"]
    if det.get("smoothed_polygon"):
        merged["polygon"] = det["smoothed_polygon"]
    return merged


def _detection_report(det: dict, anchor: str, to_wgs84, calibration=None) -> dict:
    """Vertaal één detectie naar iets dat de browser kan tekenen.

    Naast het ankerpunt (waarop de doel-keuze wordt gebaseerd) gaat ook de
    omtrek mee, plus de positie binnen het geprojecteerde vlak, het
    marker-ID en het bijbehorende label (zie `aruco_marker_actions.py`) zodat
    de kaart kan tonen wélke bewerking actief is. Zie je op de kaart een vlak
    van de verkeerde grootte of op de verkeerde plek staan, dan weet je
    meteen of het aan de detectie of aan de calibratie ligt.
    """
    ax, ay = _detection_point(det, anchor)
    lon, lat = to_wgs84(ax, ay)
    marker_id = det.get("marker_id")
    action_def = MARKER_ACTIONS.get(marker_id)
    report = {
        "lon": lon,
        "lat": lat,
        "px": round(ax, 1),
        "py": round(ay, 1),
        "area": det.get("area"),
        "track_id": det.get("track_id"),
        "marker_id": marker_id,
        "label": action_def["label"] if action_def else None,
        "in_range": True,
    }
    bbox = det.get("bbox")
    if bbox and len(bbox) >= 4:
        x1, y1, x2, y2 = (float(v) for v in bbox[:4])
        report["outline"] = [
            list(to_wgs84(x, y))
            for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
        ]
    if calibration is not None and hasattr(calibration, "pixel_to_screen"):
        uv = calibration.pixel_to_screen(ax, ay)
        if uv is not None:
            report["u"], report["v"] = round(uv[0], 4), round(uv[1], 4)
            report["in_range"] = calibration.is_in_projection(ax, ay)
    return report


def _detection_point(det: dict, anchor: str) -> tuple[float, float]:
    """Het punt van een detectie dat als positie op de maquette telt.

    `center` is het zwaartepunt van de marker en ligt dus op ongeveer halve
    hoogte van het object waarop hij gemonteerd is. Bij een schuin opgestelde
    camera valt dat punt naast de voetafdruk: de verschuiving is ruwweg
    (h/2)*tan(kijkhoek). `bottom` gebruikt het midden van de onderrand, dat
    wel op het grondvlak ligt - de homografie is immers voor het grondvlak
    bepaald.
    """
    if anchor == "bottom":
        bbox = det.get("bbox")
        if bbox and len(bbox) >= 4:
            return (float(bbox[0]) + float(bbox[2])) * 0.5, float(bbox[3])
    cx, cy = det["center"]
    return float(cx), float(cy)


def _build_marker_changes(
    action_def: dict, lon: float, lat: float, features: list, zone_features: list
) -> "list[dict] | None":
    """Bouw de change-dict(s) voor één actieve objectmarker.

    Meestal is dat één dict; bij een link met beide rijrichtingen zijn het er
    twee (zelfde signed-linkId-conventie als `find_nearest_link`: +id en -id
    zijn losse change-items). Geeft None als er geen doel (link/zone) in de
    buurt gevonden is.
    """
    action = action_def["action"]
    params = action_def.get("params", {})

    if action == "close_link":
        link_ids = find_nearest_link(lon, lat, features)
        if link_ids is None:
            return None
        return [{"linkId": lid, "capacity": 0} for lid in link_ids]

    if action == "set_speed":
        link_ids = find_nearest_link(lon, lat, features)
        if link_ids is None:
            return None
        return [{"linkId": lid, "speed": params["speed"]} for lid in link_ids]

    if action == "add_production":
        zone_id = find_nearest_zone(lon, lat, zone_features)
        if zone_id is None:
            return None
        return [{"zoneId": zone_id, "production": params["delta"]}]

    raise ValueError(f"Onbekende actie in MARKER_ACTIONS: {action!r}")


def run(
    server_url: str,
    area_id: str,
    mode: str,
    width: int,
    height: int,
    camera_id: int = -1,
    stable_seconds: float = 3.0,
    cooldown_seconds: float = 10.0,
    show_video: bool = False,
    anchor: str = "center",
    mask_margin: float = 0.0,
    mask_region: str = "picked",
    min_object_area_pct: float = _DEFAULT_MIN_OBJECT_AREA_PCT,
    min_area: "float | None" = None,
    max_area: "float | None" = None,
) -> None:
    # --- Netwerk + zones laden (voor de link/zone-lookup per objectmarker) ---
    features = load_network_features(server_url, area_id, mode)
    if not features:
        print("[camera] FOUT: geen features geladen. Controleer area_id en mode.")
        sys.exit(1)
    # Alleen de "+100 productie"-marker heeft zones nodig; een gebied zonder
    # zones mag de camera verder gewoon starten (de andere twee bewerkingen
    # werken dan nog steeds).
    zone_features = load_zone_features(server_url, area_id, mode)

    # --- Adjust-runner (gedeeld door beide modi) ---
    runner = _AdjustRunner(server_url=server_url, mode=mode)
    runner.set_initial_area_id(area_id)

    # --- Heartbeat starten (browser is al open, geen webbrowser.open nodig) ---
    _stop_heartbeat = threading.Event()
    _send_heartbeat(server_url, area_id, active=True)
    _start_heartbeat_thread(server_url, runner, _stop_heartbeat)

    try:
        # -----------------------------------------------------------------------
        # Modus -1: virtuele camera - cursorpositie komt uit de browser
        # -----------------------------------------------------------------------
        if camera_id == -1:
            _run_virtual(
                server_url=server_url,
                area_id=area_id,
                mode=mode,
                features=features,
                stable_seconds=stable_seconds,
                cooldown_seconds=cooldown_seconds,
                runner=runner,
            )
            return

        # -----------------------------------------------------------------------
        # Modus >= 0: fysieke camera
        # -----------------------------------------------------------------------
        calibration = _fetch_calibration(server_url, area_id, mode)
        if calibration is None:
            print(
                "[camera] FOUT: geen calibratie gevonden voor dit gebied.\n"
                "         Open de kaart met &calibrate=true en leg het camerabeeld\n"
                "         eerst over de kaart. Zonder calibratie zou elke gemeten\n"
                "         positie er stelselmatig naast liggen."
            )
            return
        print("[camera] Calibratie geladen.")

        cap = _open_camera(camera_id, width, height)
        if cap is None:
            sys.exit(1)
        ret, probe = cap.read()
        if not ret:
            print("[camera] FOUT: kon geen frame lezen van camera.")
            sys.exit(1)
        frame_h, frame_w = probe.shape[:2]
        print(f"[camera] Camera actief: {frame_w}x{frame_h}")

        # Levert de camera een andere resolutie dan tijdens het calibreren, dan
        # blijft het beeldveld gelijk en hoeft alleen de pixelschaal mee.
        calib_frame_w = getattr(calibration, "frame_w", 0)
        calib_frame_h = getattr(calibration, "frame_h", 0)
        if (
            calib_frame_w
            and calib_frame_h
            and (calib_frame_w, calib_frame_h) != (frame_w, frame_h)
        ):
            print(
                f"[camera] Let op: gecalibreerd op {calib_frame_w}x{calib_frame_h}, "
                f"camera levert {frame_w}x{frame_h} - calibratie wordt meegeschaald."
            )
            calibration = calibration.rescaled(frame_w, frame_h)

        # --- Uitsnede van het gecalibreerde vlak ---
        roi_polygon = _roi_polygon(calibration, mask_margin, mask_region)
        roi_mask = _roi_mask(probe.shape, roi_polygon) if roi_polygon else None
        if roi_mask is not None:
            coverage = cv2.countNonZero(roi_mask) / float(frame_w * frame_h)
            corners = ", ".join(f"({p[0]:.0f},{p[1]:.0f})" for p in roi_polygon)
            what = (
                "het geprojecteerde vlak"
                if mask_region == "projection"
                else "het bij het calibreren aangewezen vierkant"
            )
            print(
                f"[camera] Uitsnede actief ({what}): {corners} — "
                f"{coverage * 100:.0f}% van het beeld. Alles daarbuiten telt niet mee."
            )
        elif roi_polygon:
            print(
                "[camera] FOUT: het gecalibreerde vlak valt volledig buiten het "
                "camerabeeld. Staat de camera nog zoals tijdens het calibreren?"
            )
            return
        else:
            print(
                "[camera] Let op: deze calibratie kent geen vlak (oud formaat) — "
                "er wordt op het hele camerabeeld gedetecteerd."
            )

        # --- Toegestane objectgrootte, afgeleid van de uitsnede ---
        roi_area_px = (
            float(cv2.countNonZero(roi_mask))
            if roi_mask is not None
            else float(frame_w * frame_h)
        )
        area_min, area_max = _area_thresholds(
            roi_area_px, min_object_area_pct, min_area, max_area
        )
        print(
            f"[camera] Objectgrootte: {_format_area_range(area_min, area_max)} "
            f"(ondergrens = {min_object_area_pct:g}% van het vlak)."
        )

        # --- Detector / tracker ---
        # De vierhoek gaat óók als detection_area mee: het masker houdt de
        # omgeving buiten beeld, deze controle gooit markers weg die nog over
        # de rand heen steken (config.ROI_MIN_MARKER_COVERAGE).
        detector = ArucoMarkerDetector(detection_area=roi_polygon)
        # overlap_threshold is een IoU-fractie (niet een pixel-afstand): elke van
        # de laatste `stability_frames` detecties moet minstens dit aandeel met de
        # vorige overlappen. Een pixel-drempel brak hier regelmatig doordat
        # autootjes net het vlak in/uit reden en het contour van de marker
        # daardoor iets van vorm/grootte veranderde, zonder dat het echt bewoog.
        tracker = DetectionTracker(
            stability_frames=5, overlap_threshold=0.75, max_allowed_distance=80
        )

        def _to_wgs84(px: float, py: float) -> tuple[float, float]:
            return calibration.pixel_to_wgs84(px, py)

        # --- State ---
        last_detections_sent: float = 0.0
        last_reject_log: float = 0.0
        # Hoeken van het camerabeeld op de kaart: verandert niet, dus eenmalig.
        camera_view = (
            calibration.projection_corners_wgs84()
            if hasattr(calibration, "projection_corners_wgs84")
            else None
        )
        # Doorlopende staat van de actieve objectmarker-bewerkingen (zie
        # _build_marker_changes/_RECOMPUTE_DEBOUNCE hieronder): welke set nu
        # zou moeten gelden, welke set daadwerkelijk ingediend is, en sinds
        # wanneer de gewenste set ongewijzigd is (voor de debounce).
        pending_desired: "dict[int, list[dict]] | None" = None
        pending_since: float = 0.0
        last_submitted: "dict[int, list[dict]]" = {}

        print(
            f"[camera] Detectie gestart. Stabiliteit wordt bepaald door de tracker "
            f"(tracking.py); zodra een objectmarker stabiel binnen het "
            f"geprojecteerde gebied staat, komt zijn bewerking in de actieve set "
            f"en wordt die (na {_RECOMPUTE_DEBOUNCE:g}s debounce) doorgerekend. "
            f"Haal je de marker weg, dan vervalt zijn bewerking weer."
        )
        print("[camera] Druk op Ctrl+C om te stoppen.")

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[camera] Frame lezen mislukt, opnieuw proberen …")
                time.sleep(0.1)
                continue

            now = time.time()

            # --- Detectie + tracking, uitsluitend op het gecalibreerde vlak ---
            frame_roi = _apply_roi(frame, roi_mask) if roi_mask is not None else frame
            # `analyze_…` levert dezelfde detecties als `detect_markers`, plus
            # de afgewezen kandidaten met hun reden. Dat kost niets extra —
            # detect_markers filtert precies deze lijst — en maakt een
            # verkeerd afgestelde drempel of een verkeerd geprinte marker
            # meteen zichtbaar.
            evaluations = detector.analyze_marker_contours(
                frame_roi, min_area=area_min, max_area=area_max, known_ids=known_marker_ids()
            )
            detections = [
                e["detection"]
                for e in evaluations
                if e.get("accepted") and e.get("detection") is not None
            ]
            stable_dets = tracker.update(detections)

            if not detections and now - last_reject_log >= _REJECT_LOG_INTERVAL:
                last_reject_log = now
                _log_rejections(evaluations, area_min, area_max)

            # --- Alles wat de camera ziet naar de kaart sturen ---
            # Bewust alle tracks, niet alleen de stabiele: je wilt ook zien
            # wanneer de camera een marker ziet die (nog) niet stabiel is. Dit
            # zijn de tracker's eigen tracks (incl. die net deze frame niet
            # opnieuw gevonden zijn, tot _MAX_MISSING_FRAMES) in plaats van de
            # rauwe per-frame detecties: elke contourfit wiebelt een paar
            # pixels, en een enkel gemist frame (flikkerend beamerlicht) liet
            # het vlak eerder even helemaal verdwijnen op de kaart. De tracker
            # houdt positie/omtrek dus gladgestreken (EMA) en blijft ze een
            # paar frames vasthouden na een gemiste detectie.
            if now - last_detections_sent >= _DETECTIONS_INTERVAL:
                last_detections_sent = now
                visual_stable, visual_unstable = tracker.get_visualization_detections()
                _send_detections(
                    server_url,
                    runner.get_area_id(),
                    [
                        _detection_report(_with_smoothed_position(d), anchor, _to_wgs84, calibration)
                        for d in visual_stable + visual_unstable
                    ],
                    camera_view=camera_view,
                )

            # --- Objectmarkers: gewenste bewerkingen opbouwen ---
            # Elke stabiele, binnen-de-projectie-liggende marker levert zijn
            # eigen change-dict(s) op (MARKER_ACTIONS). Geen eigen wachttijd
            # hier: een detectie is pas een `stable_det` nadat tracker.update()
            # (tracking.py) ruis al heeft uitgefilterd.
            desired: "dict[int, list[dict]]" = {}
            for det in stable_dets:
                marker_id = det.get("marker_id")
                action_def = MARKER_ACTIONS.get(marker_id)
                if action_def is None:
                    continue  # zou niet moeten gebeuren: de detector filtert al op known_ids

                cx, cy = _detection_point(det, anchor)

                # De camera ziet méér dan de beamer projecteert. Ligt de marker
                # buiten dat vlak, dan staat er geen kaart onder en zou
                # find_nearest_link/_zone een doel kiezen dat niet eens in beeld is.
                if not calibration.is_in_projection(cx, cy):
                    uv = calibration.pixel_to_screen(cx, cy)
                    where = f"  (positie in het vlak: {uv[0]:.2f}, {uv[1]:.2f})" if uv else ""
                    print(
                        f"[camera] Marker #{marker_id} op px=({cx:.0f},{cy:.0f}) ligt "
                        f"BUITEN het geprojecteerde gebied - genegeerd.{where}"
                    )
                    continue

                lon, lat = _to_wgs84(cx, cy)
                marker_changes = _build_marker_changes(action_def, lon, lat, features, zone_features)
                if marker_changes is None:
                    print(
                        f"[camera] Geen doel gevonden voor marker #{marker_id} "
                        f"({action_def['label']})."
                    )
                    continue
                desired[marker_id] = marker_changes

            # --- Debounce + indienen van de volledige actuele set ---
            if desired != pending_desired:
                pending_desired = desired
                pending_since = now

            if (
                pending_desired is not None
                and pending_desired != last_submitted
                and now - pending_since >= _RECOMPUTE_DEBOUNCE
            ):
                last_submitted = pending_desired
                changes = [c for marker_changes in pending_desired.values() for c in marker_changes]
                if pending_desired:
                    active = ", ".join(
                        f"#{mid} {MARKER_ACTIONS[mid]['label']}" for mid in pending_desired
                    )
                    print(f"[camera] Objectmarkers actief: {active} → indienen …")
                else:
                    print("[camera] Geen objectmarkers meer actief — alles terug naar origineel.")
                preview_link_ids = [c["linkId"] for c in changes if "linkId" in c]
                if preview_link_ids:
                    _send_preview(server_url, runner.get_area_id(), preview_link_ids)
                runner.submit(changes)

            # --- Optioneel: debug-video ---
            if show_video:
                # Bewust het uitgesneden beeld: dan zie je letterlijk waar de
                # detector naar kijkt, en niet wat de camera toevallig ook ziet.
                display = frame_roi.copy()
                if roi_polygon:
                    cv2.polylines(
                        display,
                        [np.round(np.array(roi_polygon)).astype(np.int32)],
                        True,
                        (255, 224, 0),
                        2,
                    )
                # Afgewezen kandidaten grijs, met reden en oppervlak. Zo zie je
                # meteen of een marker wél gevonden maar afgekeurd is. Wat
                # buiten de uitsnede ligt blijft weg: dat telt niet mee en hoort
                # dus ook niet in het beeld dat laat zien wát meetelt.
                for item in evaluations:
                    if not _is_reportable_rejection(item):
                        continue
                    bx1, by1, bx2, by2 = (int(v) for v in item["bbox"])
                    cv2.rectangle(display, (bx1, by1), (bx2, by2), (150, 150, 150), 1)
                    cv2.putText(
                        display,
                        f"{item.get('reason', '?')} {item.get('raw_area', 0):.0f}",
                        (bx1, max(12, by1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        (150, 150, 150),
                        1,
                    )
                # Teken stabiele detecties groen, onstabiel rood. Stabiel (tracker)
                # betekent hier meteen trigger-klaar - er is geen aparte
                # stabilisatiewachttijd meer die nog "oranje" (bijna zover) zou zijn.
                all_stable, all_unstable = tracker.get_visualization_detections()
                for d in all_unstable:
                    cx, cy = int(d["center"][0]), int(d["center"][1])
                    cv2.circle(display, (cx, cy), 8, (0, 0, 200), 2)
                for d in all_stable:
                    cx, cy = int(d["center"][0]), int(d["center"][1])
                    color = (0, 200, 0)
                    cv2.circle(display, (cx, cy), 10, color, 2)
                    cv2.putText(
                        display,
                        f"{d.get('frames_tracked', 0)}f",
                        (cx + 12, cy),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        1,
                    )
                cv2.imshow("Maquette Camera", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        print("\n[camera] Gestopt.")
    finally:
        _stop_heartbeat.set()
        _send_heartbeat(server_url, area_id, active=False)
        cap_local = locals().get("cap")
        if cap_local is not None:
            cap_local.release()
        if show_video:
            cv2.destroyAllWindows()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args():
    p = argparse.ArgumentParser(
        description="Maquette camera - detecteert ArUco-objectmarkers en past het netwerk aan."
    )
    p.add_argument(
        "--server",
        default="http://127.0.0.1:8080",
        help="Server base URL (gebruik 127.0.0.1, niet localhost: een "
        "DNS-lookup van localhost kost op sommige machines seconden)",
    )
    p.add_argument("--area-id", required=True, help="Initieel area_id (UUID)")
    p.add_argument("--mode", default="CAR", help="Transportmodus (CAR/BIKE/PEDESTRIAN)")
    p.add_argument(
        "--width", type=int, required=True, help="Gewenste camerabreedte in pixels"
    )
    p.add_argument(
        "--height", type=int, required=True, help="Gewenste camerahoogte in pixels"
    )
    p.add_argument(
        "--camera-id",
        type=int,
        default=-1,
        help="Camera-index (default: -1 = virtuele cursor-modus, 0+ = fysieke camera)",
    )
    p.add_argument(
        "--stable-seconds",
        type=float,
        default=3.0,
        help="Seconden stilstand voordat weg wordt afgesloten — geldt alleen voor "
        "de virtuele cursor-modus (--camera-id -1). Bij een fysieke camera bepaalt "
        "de tracker (tracking.py) zelf wanneer een objectmarker stabiel is; de "
        "indiening volgt dan na een korte debounce, zonder deze wachttijd (default: 3.0)",
    )
    p.add_argument(
        "--cooldown",
        type=float,
        default=10.0,
        help="Seconden cooldown na afsluiting (default: 10)",
    )
    p.add_argument(
        "--show-video",
        action="store_true",
        help="Toon live camera-feed met detectie-overlay (debug, alleen fysieke camera)",
    )
    p.add_argument(
        "--preview",
        action="store_true",
        help="Preview-stand: stuur alleen camerabeeld naar de browser (voor "
        "de calibratie), zonder detectie",
    )
    p.add_argument(
        "--mask-margin",
        type=float,
        default=0.0,
        help="Speling op de uitsnede, als fractie van het gecalibreerde vlak. "
        "0 (default) snijdt precies op het vlak; 0.05 laat 5%% extra staan aan "
        "elke kant, voor het geval de camera iets verschoven is",
    )
    p.add_argument(
        "--mask-region",
        choices=("picked", "projection"),
        default="picked",
        help="Wat het werkgebied is. 'picked' (default) is de vierhoek die je "
        "bij het calibreren hebt aangewezen; 'projection' is het hele vlak dat "
        "de beamer projecteert, en dat is groter — de markers liggen met hun "
        "inzet erbinnen (bij 25%% inzet ruim 4x in oppervlak)",
    )
    p.add_argument(
        "--min-object-area",
        type=float,
        metavar="PCT",
        default=_DEFAULT_MIN_OBJECT_AREA_PCT,
        help="Ondergrens voor de objectgrootte, als percentage van het "
        "gecalibreerde vlak (default: %(default)s). Een percentage in plaats van "
        "pixels, omdat pixels met de cameraresolutie en de afstand meeschalen en "
        "een percentage niet. Er is geen bovengrens",
    )
    p.add_argument(
        "--min-area",
        type=float,
        default=None,
        help="Ondergrens in pixels, overschrijft --min-object-area (voor "
        "fijnregelen aan de hand van wat --show-video toont)",
    )
    p.add_argument(
        "--max-area",
        type=float,
        default=None,
        help="Bovengrens in pixels. Standaard is er géén bovengrens; geef deze "
        "alleen op als iets groots in beeld structureel voor het object "
        "aangezien wordt",
    )
    p.add_argument(
        "--anchor",
        choices=("center", "bottom"),
        default="center",
        help="Welk punt van de objectmarker telt als positie: 'center' is het "
        "zwaartepunt van de marker, 'bottom' het midden van de onderrand. "
        "Bij een schuin opgestelde camera ligt alleen 'bottom' op het grondvlak "
        "waarvoor de calibratie geldt (default: center)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.preview:
        run_preview(
            server_url=args.server,
            camera_id=args.camera_id,
            width=args.width,
            height=args.height,
        )
    else:
        run(
            server_url=args.server,
            area_id=args.area_id,
            mode=args.mode,
            width=args.width,
            height=args.height,
            camera_id=args.camera_id,
            stable_seconds=args.stable_seconds,
            cooldown_seconds=args.cooldown,
            show_video=args.show_video,
            anchor=args.anchor,
            mask_margin=args.mask_margin,
            mask_region=args.mask_region,
            min_object_area_pct=args.min_object_area,
            min_area=args.min_area,
            max_area=args.max_area,
        )
