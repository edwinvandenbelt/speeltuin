"""
maquette_camera.py — Fysieke maquette koppeling via camera-detectie
====================================================================

Detecteert een zwart blokje op de maquette en sluit de dichtstbijzijnde weg
af via de adjust-pipeline zodra het blokje ≥ STABLE_SECONDS stilstaat.

Gebruik:
    python maquette_camera.py \\
        --server http://localhost:8080 \\
        --area-id <uuid> \\
        --mode CAR \\
        [--camera-id 0] [--stable-seconds 3.0] [--cooldown 10] [--show-video]

De viewport-bounds worden automatisch afgeleid uit de bbox van het netwerk.
De pixelafmetingen worden afgeleid uit de werkelijke camera-resolutie.

Afhankelijkheden (naast standaard-bibliotheek en opencv/shapely/requests):
    C:\\sources\\GMP\\kien-maquette\\kien-camera-maquette\\  (detection + tracking)
"""

import argparse
import ctypes
import json
import ctypes.wintypes
import math
import sys
import threading
import time
import webbrowser

# Console-uitvoer naar UTF-8 forceren zodat Unicode-tekens (→, …) niet crashen
# op Windows-consoles met een cp1252-codepage.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

import cv2
import requests

# ---------------------------------------------------------------------------
# Importeer detectie/tracking-modules uit het kien-camera-maquette project.
# De modules gebruiken een `config` module op datzelfde pad.
# ---------------------------------------------------------------------------
_KIEN_DIR = r"C:\sources\GMP\kien-maquette\kien-camera-maquette"
if _KIEN_DIR not in sys.path:
    sys.path.insert(0, _KIEN_DIR)

from detection import BlackObjectDetector  # noqa: E402
from tracking import DetectionTracker  # noqa: E402

# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


def _merc(lat_deg: float) -> float:
    """Web-Mercator Y voor een breedtegraad (zelfde formule als MapLibre)."""
    lat_rad = math.radians(lat_deg)
    return math.log(math.tan(math.pi / 4 + lat_rad / 2))


def _merc_inv(y: float) -> float:
    """Inverse Web-Mercator Y → breedtegraad in graden."""
    return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


def pixel_to_wgs84(
    cx: float,
    cy: float,
    west: float,
    north: float,
    east: float,
    south: float,
    width: int,
    height: int,
) -> tuple[float, float]:
    """
    Camera-pixel (cx, cy) → (lon, lat) WGS84.

    Aanname: camera is exact loodrecht boven de maquette gemonteerd en de
    beamer projecteert exact hetzelfde gebied → pixel-coördinaten zijn lineair
    gemapt op de viewport-bounds die ook in index.html gebruikt worden.

    west=x=0, north=y=0 zijn gegarandeerd door de JS-implementatie.
    """
    lon = west + (cx / width) * (east - west)
    merc_n = _merc(north)
    merc_s = _merc(south)
    merc_y = merc_n + (cy / height) * (merc_s - merc_n)
    lat = _merc_inv(merc_y)
    return lon, lat


# Kaartweergave (center/zoom/bearing/pitch) die de browser tijdens calibratie
# had. Wordt via --view-json meegegeven en in het calibratiebestand opgeslagen,
# zodat de kaart bij heropenen exact hersteld kan worden.
_CALIB_VIEW: "dict | None" = None


class Calibration:
    """Pixel→WGS84 mapping op basis van een scherm-uitgelijnde rechthoek.

    De browser tekent een rechthoek die *rechtop staat t.o.v. het scherm* (niet
    noord-zuid). De vier schermhoeken worden ge-unproject naar geo-coördinaten,
    wat een (bij kaartrotatie) geroteerde vierhoek in geo-ruimte oplevert:

        corners = { bl, br, tr, tl }   (elk (lon, lat))

    Fysiek/virtueel worden twee tegenoverliggende hoeken opgemeten:
        bottom_left-pixel  ↔  corners['bl']
        top_right-pixel    ↔  corners['tr']

    Een willekeurige pixel wordt via de fractie (fx, fy) t.o.v. die twee
    opgemeten hoeken *bilineair* over de vier geo-hoeken geïnterpoleerd, zodat
    kaartrotatie correct wordt meegenomen.
    """

    def __init__(
        self,
        corners: dict,
        px_bl: float,
        py_bl: float,
        px_tr: float,
        py_tr: float,
    ):
        # corners: {'bl':[lon,lat], 'br':[lon,lat], 'tr':[lon,lat], 'tl':[lon,lat]}
        self.corners = corners
        self.px_bl = px_bl
        self.py_bl = py_bl
        self.px_tr = px_tr
        self.py_tr = py_tr

    def pixel_to_wgs84(self, px: float, py: float) -> tuple[float, float]:
        """Camera-/cursorpixel (px, py) → (lon, lat) via bilineaire interpolatie."""
        dx = self.px_tr - self.px_bl
        dy = self.py_tr - self.py_bl
        fx = (px - self.px_bl) / dx if dx else 0.0
        fy = (py - self.py_bl) / dy if dy else 0.0

        bl = self.corners["bl"]
        br = self.corners["br"]
        tr = self.corners["tr"]
        tl = self.corners["tl"]

        def _bilerp(v_bl, v_br, v_tr, v_tl):
            # fx: bl→br (langs onder) / tl→tr (langs boven); fy: bl→tl / br→tr
            return (
                (1 - fx) * (1 - fy) * v_bl
                + fx * (1 - fy) * v_br
                + fx * fy * v_tr
                + (1 - fx) * fy * v_tl
            )

        lon = _bilerp(bl[0], br[0], tr[0], tl[0])
        merc_y = _bilerp(_merc(bl[1]), _merc(br[1]), _merc(tr[1]), _merc(tl[1]))
        lat = _merc_inv(merc_y)
        return lon, lat

    def to_dict(self, mode: str, camera_id: int, frame_w: int, frame_h: int) -> dict:
        d = {
            "mode": mode,
            "camera_id": camera_id,
            "corners": {
                "bl": list(self.corners["bl"]),
                "br": list(self.corners["br"]),
                "tr": list(self.corners["tr"]),
                "tl": list(self.corners["tl"]),
            },
            "pixels": {
                "bottom_left": [self.px_bl, self.py_bl],
                "top_right": [self.px_tr, self.py_tr],
            },
            "frame": {"width": frame_w, "height": frame_h},
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if _CALIB_VIEW:
            d["view"] = _CALIB_VIEW
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Calibration | None":
        try:
            p = d["pixels"]
            bl_px = p["bottom_left"]
            tr_px = p["top_right"]
            if "corners" in d:
                c = d["corners"]
                corners = {
                    "bl": [float(c["bl"][0]), float(c["bl"][1])],
                    "br": [float(c["br"][0]), float(c["br"][1])],
                    "tr": [float(c["tr"][0]), float(c["tr"][1])],
                    "tl": [float(c["tl"][0]), float(c["tl"][1])],
                }
            else:
                # Terugval op oud bbox-formaat (noord-uitgelijnd)
                b = d["bounds"]
                w, s = float(b["west"]), float(b["south"])
                e, n = float(b["east"]), float(b["north"])
                corners = {
                    "bl": [w, s],
                    "br": [e, s],
                    "tr": [e, n],
                    "tl": [w, n],
                }
            return cls(
                corners=corners,
                px_bl=float(bl_px[0]),
                py_bl=float(bl_px[1]),
                px_tr=float(tr_px[0]),
                py_tr=float(tr_px[1]),
            )
        except (KeyError, TypeError, ValueError, IndexError):
            return None


# ---------------------------------------------------------------------------
# Network laden en dichtstbijzijnde link vinden
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


def bbox_from_features(features: list) -> tuple[float, float, float, float]:
    """
    Bereken de bounding box (west, south, east, north) uit alle feature-coördinaten.
    """
    lons, lats = [], []
    for feat in features:
        geom = feat.get("geometry", {})
        coords = _extract_coords(geom)
        for lon, lat in coords:
            lons.append(lon)
            lats.append(lat)
    if not lons:
        raise ValueError("Geen coördinaten gevonden in network-features.")
    return min(lons), min(lats), max(lons), max(lats)


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


def post_adjust(server_url: str, area_id: str, mode: str, link_ids: list[int]) -> str:
    """
    Sluit de opgegeven link-richtingen af via de adjust-API.
    Geeft de jobID terug.
    """
    url = f"{server_url}/processes/adjust/execution"
    payload = {
        "inputs": {
            "area_id": area_id,
            "mode": mode,
            "changes": [{"linkId": lid, "capacity": 0} for lid in link_ids],
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
    Voert adjust-aanroepen sequentieel uit in een achtergrondthread
    zodat de camera-loop niet blokkeert.
    """

    def __init__(self, server_url: str, mode: str):
        self.server_url = server_url
        self.mode = mode
        self._area_id_lock = threading.Lock()
        self._current_area_id: str = ""
        self._busy = threading.Event()

    def set_initial_area_id(self, area_id: str) -> None:
        with self._area_id_lock:
            self._current_area_id = area_id

    def get_area_id(self) -> str:
        with self._area_id_lock:
            return self._current_area_id

    def is_busy(self) -> bool:
        return self._busy.is_set()

    def trigger(self, link_ids: list[int], on_done=None) -> None:
        """Start de adjust in een daemon-thread."""
        area_id = self.get_area_id()
        t = threading.Thread(
            target=self._run, args=(area_id, link_ids, on_done), daemon=True
        )
        t.start()

    def _run(self, area_id: str, link_ids: list[int], on_done) -> None:
        self._busy.set()
        try:
            print(f"[camera] POST adjust: area={area_id} links={link_ids}")
            job_id = post_adjust(self.server_url, area_id, self.mode, link_ids)
            print(f"[camera] Job gestart: {job_id}")
            job = poll_job(self.server_url, job_id)
            if job["status"] == "successful":
                # GET /jobs/{id} geeft geen _results terug (bewust gestript);
                # haal de resultaten op via het aparte /results-endpoint.
                results_resp = requests.get(
                    f"{self.server_url}/jobs/{job_id}/results", timeout=10
                )
                results_resp.raise_for_status()
                results = results_resp.json()
                new_area_id = results.get("new_area_id", area_id)
                with self._area_id_lock:
                    self._current_area_id = new_area_id
                print(f"[camera] Weg afgesloten. Nieuw area_id: {new_area_id}")
            else:
                log = "\n".join(job.get("log", [])[-5:])
                print(f"[camera] Adjust mislukt (job {job_id}):\n{log}")
        except Exception as exc:
            print(f"[camera] Fout bij adjust: {exc}")
        finally:
            self._busy.clear()
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Browser openen + heartbeat via SSE
# ---------------------------------------------------------------------------

_HEARTBEAT_INTERVAL = 5  # seconden tussen heartbeats


def _build_browser_url(
    server_url: str,
    area_id: str,
    mode: str,
    west: float,
    south: float,
    east: float,
    north: float,
) -> str:
    """Bouw de URL op waarmee de browser de kaart opent in maquette+follow modus.

    De bbox-parameter zorgt dat de kaart exact hetzelfde gebied toont als de
    coördinaten die de camera-script gebruikt voor de pixel→WGS84 mapping.
    """
    bbox = f"{west},{south},{east},{north}"
    return (
        f"{server_url}/?areaId={area_id}&mode={mode}"
        f"&follow=true&maquette=true&bbox={bbox}"
    )


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

_CALIB_STABLE_SECONDS = 3.0  # seconden stilstand per hoek tijdens calibratie
_CALIB_MOVE_AWAY_PX = 40  # pixels die het blokje moet wegbewegen tussen hoek 1 en 2


def _fetch_calibration(
    server_url: str, area_id: str, mode: str
) -> "Calibration | None":
    """Haal een bestaande calibratie op van de server. None als niet aanwezig."""
    try:
        resp = requests.get(
            f"{server_url}/maquette/calibration",
            params={"area_id": area_id, "mode": mode},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("exists") and data.get("calibration"):
            return Calibration.from_dict(data["calibration"])
    except Exception:
        pass
    return None


def _post_calibration(server_url: str, area_id: str, payload: dict) -> bool:
    """Schrijf een calibratie weg via de server. Geeft True bij succes."""
    try:
        resp = requests.post(
            f"{server_url}/maquette/calibration",
            json={"area_id": area_id, "calibration": payload},
            timeout=5,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[camera] Calibratie wegschrijven mislukt: {exc}")
        return False


def _send_calib_progress(
    server_url: str, area_id: str, corner: str, state: str, seconds: float = 0.0
) -> None:
    """Stuur calibratie-voortgang naar de browser (best-effort).

    corner: "bl" (linksonder) of "tr" (rechtsboven)
    state:  "waiting" | "counting" | "recorded" | "done" | "failed"
    """
    try:
        requests.post(
            f"{server_url}/maquette/calibration-progress",
            json={
                "area_id": area_id,
                "corner": corner,
                "state": state,
                "seconds": round(seconds, 1),
            },
            timeout=3,
        )
    except Exception:
        pass


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
# Virtuele camera: cursor-tracking via het browser-venster (camera_id == -1)
# ---------------------------------------------------------------------------

# Stabilititeitsdrempel in pixels: cursor mag dit veel bewegen en telt nog als
# "stilstaand" (zelfde semantiek als STABILITY_POSITION_THRESHOLD in tracking.py)
_VIRTUAL_STABILITY_PX = 10


def _get_cursor_pos() -> tuple[int, int]:
    """Geeft de huidige cursor-positie terug in schermcoördinaten (Windows)."""
    pt = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _find_browser_window(
    server_url: str,
    want_w: int = 0,
    want_h: int = 0,
) -> tuple[int, int, int, int] | None:
    """
    Zoekt het browser-venster dat de kaartpagina toont.

    Er kunnen meerdere kandidaat-vensters zijn (bv. een kleine popup naast het
    echte kaartvenster). We kiezen niet op titel-prioriteit maar op de client-
    area die het best past bij de doorgegeven browser-viewport (want_w×want_h);
    zonder hint kiezen we simpelweg het grootste venster. Zo wordt het echte
    kaartvenster gekozen i.p.v. een kleiner/foutief venster.

    Geeft (left, top, width, height) terug, of None als niets gevonden is.
    """
    host = server_url.split("//")[-1].split("/")[0].split(":")[0].lower()
    keywords = [host, "maquette", "chrome", "firefox", "edge", "msedge"]

    found: list[tuple[int, int, int, int]] = []  # (left, top, w, h)

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )

    def _enum_cb(hwnd, _lParam):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.lower()
        if not any(kw in title for kw in keywords):
            return True
        # Gebruik GetClientRect + ClientToScreen zodat de afmetingen
        # overeenkomen met window.innerWidth/Height uit de browser.
        # GetWindowRect zou de outer bounds (inclusief titelregel en
        # randen) teruggeven, wat een systematische offset geeft.
        client_rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect))
        w = client_rect.right
        h = client_rect.bottom
        if w > 200 and h > 200:
            pt = ctypes.wintypes.POINT()  # (0,0) = linkerbovenhoek client area
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
            found.append((pt.x, pt.y, w, h))
        return True

    ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

    if not found:
        return None

    if want_w > 0 and want_h > 0:
        # Kies het venster met de kleinste afwijking t.o.v. de gevraagde viewport.
        def _score(win):
            _, _, w, h = win
            return abs(w - want_w) + abs(h - want_h)

        best = min(found, key=_score)
    else:
        # Geen hint: kies het grootste venster (grootste client-area).
        best = max(found, key=lambda win: win[2] * win[3])

    left, top, w, h = best
    return left, top, w, h


# ---------------------------------------------------------------------------
# Calibratie: gedeelde hoek-collector (werkt op elke pixel-bron)
# ---------------------------------------------------------------------------


def _calibrate_collect_corner(
    server_url: str,
    area_id: str,
    corner: str,
    get_pixel,
    stable_px: float,
    require_away_from: tuple[float, float] | None = None,
    move_away_px: float = 0.0,
) -> tuple[float, float] | None:
    """Wacht tot de pixel-bron `_CALIB_STABLE_SECONDS` stabiel op één plek staat
    en geef die pixelpositie terug.

    get_pixel() geeft (px, py) of None (geen blokje/cursor beschikbaar).
    Voor de tweede hoek moet het blokje eerst `move_away_px` van hoek 1 weg zijn
    voordat een nieuwe stabiele positie geaccepteerd wordt.
    Geeft None terug bij KeyboardInterrupt.
    """
    INTERVAL = 1 / 30
    stable_pos: tuple[float, float] | None = None
    stable_since = 0.0
    last_reported = -1
    moved_away = require_away_from is None
    last_waiting_sent = 0.0

    def _send_waiting():
        # Throttle "waiting" naar ~2x/sec zodat de server niet volloopt.
        nonlocal last_waiting_sent
        now_ = time.time()
        if now_ - last_waiting_sent >= 0.5:
            last_waiting_sent = now_
            _send_calib_progress(server_url, area_id, corner, "waiting")

    try:
        last_dbg = 0.0

        def _dbg(msg: str):
            nonlocal last_dbg
            t = time.time()
            if t - last_dbg >= 0.7:
                last_dbg = t
                print(f"[camera] calib[{corner}] {msg}")

        while True:
            t0 = time.time()
            px = get_pixel()
            now = time.time()

            if px is None:
                stable_pos = None
                _send_waiting()
                _dbg("geen blokje/cursor gedetecteerd — wachten")
                time.sleep(INTERVAL)
                continue

            cx, cy = px

            # Voor hoek 2: eerst voldoende wegbewegen van hoek 1
            if not moved_away and require_away_from is not None:
                dist = math.hypot(cx - require_away_from[0], cy - require_away_from[1])
                if dist >= move_away_px:
                    moved_away = True
                    print(
                        f"[camera] calib[{corner}] weg van hoek 1 ({dist:.0f}px) — meten kan starten"
                    )
                else:
                    stable_pos = None
                    _send_waiting()
                    _dbg(
                        f"nog te dicht bij hoek 1 ({dist:.0f}<{move_away_px}px) — beweeg blokje verder weg"
                    )
                    time.sleep(INTERVAL)
                    continue

            if stable_pos is None:
                stable_pos = (cx, cy)
                stable_since = now
            elif math.hypot(cx - stable_pos[0], cy - stable_pos[1]) > stable_px:
                stable_pos = (cx, cy)
                stable_since = now

            duration = now - stable_since
            _dbg(f"blokje op ({cx:.0f},{cy:.0f}) stabiel {duration:.1f}s")
            cur = int(duration)
            if cur != last_reported:
                last_reported = cur
                _send_calib_progress(server_url, area_id, corner, "counting", duration)

            if duration >= _CALIB_STABLE_SECONDS:
                _send_calib_progress(server_url, area_id, corner, "recorded", duration)
                return stable_pos

            elapsed = time.time() - t0
            time.sleep(max(0.0, INTERVAL - elapsed))
    except KeyboardInterrupt:
        return None


def _calibrate_virtual(
    server_url: str,
    area_id: str,
    mode: str,
    corners: dict,
    win_left: int,
    win_top: int,
    win_w: int,
    win_h: int,
) -> "Calibration | None":
    """Calibreer de virtuele (cursor) camera door twee hoeken op te meten.

    De browser projecteert een rode stip op resp. de linksonder- (corners['bl'])
    en rechtsboven-hoek (corners['tr']) van het scherm-uitgelijnde vierkant. De
    gebruiker beweegt de cursor naar de stip en houdt stil; de bijbehorende
    pixelpositie wordt vastgelegd.
    """
    print(
        "[camera] Calibratie (virtueel): beweeg cursor naar de rode stip en houd stil."
    )

    def get_pixel() -> tuple[float, float] | None:
        cx, cy = _get_cursor_pos()
        rel_x = cx - win_left
        rel_y = cy - win_top
        if 0 <= rel_x < win_w and 0 <= rel_y < win_h:
            return (float(rel_x), float(rel_y))
        return None

    bl = _calibrate_collect_corner(
        server_url, area_id, "bl", get_pixel, stable_px=_VIRTUAL_STABILITY_PX
    )
    if bl is None:
        return None
    tr = _calibrate_collect_corner(
        server_url,
        area_id,
        "tr",
        get_pixel,
        stable_px=_VIRTUAL_STABILITY_PX,
        require_away_from=bl,
        move_away_px=_CALIB_MOVE_AWAY_PX,
    )
    if tr is None:
        return None

    calib = Calibration(
        corners=corners,
        px_bl=bl[0],
        py_bl=bl[1],
        px_tr=tr[0],
        py_tr=tr[1],
    )
    _post_calibration(server_url, area_id, calib.to_dict(mode, -1, win_w, win_h))
    _send_calib_progress(server_url, area_id, "tr", "done")
    print(f"[camera] Calibratie klaar: bl-px={bl}  tr-px={tr}  corners={corners}")
    return calib


def _run_virtual(
    server_url: str,
    area_id: str,
    mode: str,
    features: list,
    west: float,
    north: float,
    east: float,
    south: float,
    stable_seconds: float,
    cooldown_seconds: float,
    runner: "_AdjustRunner",
    width: int = 0,
    height: int = 0,
    calibrate: bool = False,
    calibration: "Calibration | None" = None,
    corners: "dict | None" = None,
    pixels: "dict | None" = None,
) -> None:
    """
    Cursor-tracking loop voor virtuele camera-modus (camera_id == -1).

    De cursor stelt het zwarte blokje voor (al ingesteld door ?maquette=true).
    Na `stable_seconds` zonder beweging wordt de dichtstbijzijnde weg afgesloten.
    """
    print("[camera] Virtuele camera: cursor wordt als blokje gebruikt.")

    win = _find_browser_window(server_url, width, height)
    if win:
        win_left, win_top, win_w, win_h = win
        print(
            f"[camera] Browser-venster gevonden op "
            f"({win_left},{win_top}) {win_w}x{win_h}px"
        )
    else:
        print(
            "[camera] WAARSCHUWING: browser-venster niet gevonden. "
            "Schermresolutie wordt gebruikt als fallback."
        )
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        win_left, win_top, win_w, win_h = 0, 0, screen_w, screen_h

    # --- Calibratie uitvoeren indien gevraagd en nog niet aanwezig ---
    if calibrate and calibration is None:
        if not corners:
            print(
                "[camera] FOUT: geen hoek-coördinaten (corners) ontvangen voor calibratie."
            )
            return
        # Virtuele modus: we meten de twee hoeken op met de cursor. Zolang
        # calibratie én runtime beide GetCursorPos - win_origin in HETZELFDE
        # venster gebruiken, is de bilineaire mapping self-consistent —
        # ongeacht venster-offset of DPI-schaling.
        calibration = _calibrate_virtual(
            server_url,
            area_id,
            mode,
            corners,
            win_left,
            win_top,
            win_w,
            win_h,
        )
        if calibration is None:
            print("[camera] Calibratie afgebroken.")
            return

    def _to_wgs84(px: float, py: float) -> tuple[float, float]:
        if calibration is not None:
            return calibration.pixel_to_wgs84(px, py)
        return pixel_to_wgs84(px, py, west, north, east, south, win_w, win_h)

    triggered_links: set[int] = set()
    cooldown_until: float = 0.0

    # Cursor-stability state
    stable_pos: tuple[int, int] | None = None  # positie waar stabiliteit begon
    stable_since: float = 0.0
    last_log_second: int = -1

    print(
        f"[camera] Cursor-tracking gestart. Stabiel na {stable_seconds}s, "
        f"cooldown {cooldown_seconds}s."
    )
    print("[camera] Druk op Ctrl+C om te stoppen.")

    INTERVAL = 1 / 30  # ~30 polls per seconde

    try:
        while True:
            t0 = time.time()
            cx, cy = _get_cursor_pos()

            # Cursor buiten browser-venster? → reset stabiliteit
            rel_x = cx - win_left
            rel_y = cy - win_top
            if not (0 <= rel_x < win_w and 0 <= rel_y < win_h):
                stable_pos = None
                time.sleep(INTERVAL)
                continue

            now = time.time()

            # Stabiliteitscheck
            if stable_pos is None:
                stable_pos = (cx, cy)
                stable_since = now
            else:
                dx = cx - stable_pos[0]
                dy = cy - stable_pos[1]
                moved = math.sqrt(dx * dx + dy * dy)
                if moved > _VIRTUAL_STABILITY_PX:
                    stable_pos = (cx, cy)
                    stable_since = now

            duration = now - stable_since

            # Progress-feedback elke seconde
            cur_second = int(duration)
            if cur_second != last_log_second and cur_second > 0:
                last_log_second = cur_second
                lon, lat = _to_wgs84(rel_x, rel_y)
                print(
                    f"[camera] Cursor stabiel {duration:.1f}s  "
                    f"px=({rel_x},{rel_y})  "
                    f"wgs84=({lon:.6f},{lat:.6f})"
                )
            else:
                last_log_second = cur_second if cur_second == 0 else last_log_second

            in_cooldown = now < cooldown_until
            adjust_busy = runner.is_busy()

            if duration >= stable_seconds and not in_cooldown and not adjust_busy:
                lon, lat = _to_wgs84(rel_x, rel_y)
                link_ids = find_nearest_link(lon, lat, features)

                if link_ids is None:
                    print("[camera] Geen link gevonden nabij cursor.")
                elif any(lid in triggered_links for lid in link_ids):
                    pass  # stil laten: al afgesloten
                else:
                    print(
                        f"[camera] Cursor {stable_seconds}s stabiel op "
                        f"({lon:.6f}, {lat:.6f}) → links {link_ids} oplichten, "
                        f"berekening over {_PREVIEW_DELAY}s …"
                    )
                    triggered_links.update(link_ids)
                    cooldown_until = now + cooldown_seconds
                    _send_preview(server_url, runner.get_area_id(), link_ids)
                    time.sleep(_PREVIEW_DELAY)
                    _adjust_done = threading.Event()
                    runner.trigger(link_ids, on_done=_adjust_done.set)
                    print("[camera] Eén berekening gestart — wachten op afronding …")
                    _adjust_done.wait()
                    print(
                        "[camera] Berekening klaar — camera wordt uitgeschakeld. "
                        "Zet 'm handmatig weer aan voor een volgende meting."
                    )
                    return
            elif in_cooldown and duration >= stable_seconds:
                pass  # cooldown-melding alleen tonen als net overschreden

            elapsed = time.time() - t0
            sleep_time = max(0.0, INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[camera] Gestopt.")


# ---------------------------------------------------------------------------
# Hoofdlus (fysieke camera)
# ---------------------------------------------------------------------------


def _calibrate_physical(
    server_url: str,
    area_id: str,
    mode: str,
    corners: dict,
    cap,
    detector,
    tracker,
    frame_w: int,
    frame_h: int,
) -> "Calibration | None":
    """Calibreer de fysieke camera door twee hoeken op te meten.

    De browser projecteert een rode stip op de linksonder- (corners['bl']) en
    daarna rechtsboven-hoek (corners['tr']) van het scherm-uitgelijnde vierkant.
    De gebruiker legt het blokje op de stip en houdt het stil; het gedetecteerde
    centrum (framecoördinaten) wordt vastgelegd.
    """
    print("[camera] Calibratie (fysiek): leg blokje op de rode stip en houd stil.")

    def get_pixel() -> tuple[float, float] | None:
        ret, frame = cap.read()
        if not ret:
            return None
        dets = detector.detect_black_objects(frame)
        stable = tracker.update(dets)
        if not stable:
            return None
        cx, cy = stable[0]["center"]
        return (float(cx), float(cy))

    bl = _calibrate_collect_corner(server_url, area_id, "bl", get_pixel, stable_px=10.0)
    if bl is None:
        return None
    tr = _calibrate_collect_corner(
        server_url,
        area_id,
        "tr",
        get_pixel,
        stable_px=10.0,
        require_away_from=bl,
        move_away_px=_CALIB_MOVE_AWAY_PX,
    )
    if tr is None:
        return None

    calib = Calibration(
        corners=corners,
        px_bl=bl[0],
        py_bl=bl[1],
        px_tr=tr[0],
        py_tr=tr[1],
    )
    _post_calibration(server_url, area_id, calib.to_dict(mode, 0, frame_w, frame_h))
    _send_calib_progress(server_url, area_id, "tr", "done")
    print(f"[camera] Calibratie klaar: bl-px={bl}  tr-px={tr}  corners={corners}")
    return calib


def run(
    server_url: str,
    area_id: str,
    mode: str,
    viewport_west: float,
    viewport_north: float,
    viewport_east: float,
    viewport_south: float,
    width: int,
    height: int,
    camera_id: int = -1,
    stable_seconds: float = 3.0,
    cooldown_seconds: float = 10.0,
    show_video: bool = False,
    calibrate: bool = False,
    corners: "dict | None" = None,
    pixels: "dict | None" = None,
) -> None:
    # --- DPI-awareness: zorg dat GetCursorPos/GetClientRect in fysieke pixels
    # rekenen, zodat cursor- en venstercoördinaten in dezelfde ruimte liggen. ---
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    # --- Netwerk laden (alleen voor road-lookup, niet meer voor viewport) ---
    features = load_network_features(server_url, area_id, mode)
    if not features:
        print("[camera] FOUT: geen features geladen. Controleer area_id en mode.")
        sys.exit(1)

    west, north, east, south = (
        viewport_west,
        viewport_north,
        viewport_east,
        viewport_south,
    )
    print(
        f"[camera] Viewport (browser): west={west:.6f} north={north:.6f} "
        f"east={east:.6f} south={south:.6f}  {width}x{height}px"
    )

    # --- Calibratie: bestaande ophalen tenzij (her)calibratie gevraagd is ---
    calibration: "Calibration | None" = None
    if calibrate:
        print("[camera] Calibratiemodus actief — bestaande calibratie wordt genegeerd.")
    else:
        calibration = _fetch_calibration(server_url, area_id, mode)
        if calibration is not None:
            print("[camera] Bestaande calibratie geladen.")
        else:
            print("[camera] Geen calibratie gevonden — viewport-mapping als fallback.")

    # --- Adjust-runner (gedeeld door beide modi) ---
    runner = _AdjustRunner(server_url=server_url, mode=mode)
    runner.set_initial_area_id(area_id)

    # --- Heartbeat starten (browser is al open, geen webbrowser.open nodig) ---
    _stop_heartbeat = threading.Event()
    _send_heartbeat(server_url, area_id, active=True)
    _start_heartbeat_thread(server_url, runner, _stop_heartbeat)

    try:
        # -----------------------------------------------------------------------
        # Modus -1: virtuele camera — cursor tracken vanuit browser-venster
        # -----------------------------------------------------------------------
        if camera_id == -1:
            _run_virtual(
                server_url=server_url,
                area_id=area_id,
                mode=mode,
                features=features,
                west=west,
                north=north,
                east=east,
                south=south,
                stable_seconds=stable_seconds,
                cooldown_seconds=cooldown_seconds,
                runner=runner,
                width=width,
                height=height,
                calibrate=calibrate,
                calibration=calibration,
                corners=corners,
                pixels=pixels,
            )
            return

        # -----------------------------------------------------------------------
        # Modus ≥ 0: fysieke camera
        # -----------------------------------------------------------------------

        # --- Camera openen ---
        print(f"[camera] Camera {camera_id} openen …")
        cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print(f"[camera] FOUT: camera {camera_id} kon niet geopend worden.")
            sys.exit(1)
        cap.set(cv2.CAP_PROP_FPS, 30)

        # Gebruik de opgegeven viewport-afmetingen als camera-resolutie
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        ret, probe = cap.read()
        if not ret:
            print("[camera] FOUT: kon geen frame lezen van camera.")
            sys.exit(1)
        frame_h, frame_w = probe.shape[:2]
        print(f"[camera] Camera actief: {frame_w}x{frame_h}")
        # Voor de coördinaat-mapping gebruiken we de opgegeven viewport-dimensies
        # (gelijk aan de browser-resolutie), niet de camera-resolutie.
        # Als de camera een andere resolutie heeft, schaalt de transform mee.
        map_w, map_h = width, height

        # --- Detector / tracker ---
        detector = BlackObjectDetector()
        tracker = DetectionTracker(
            stability_frames=5, position_threshold=10, max_allowed_distance=80
        )

        # --- Calibratie uitvoeren indien gevraagd en nog niet aanwezig ---
        if calibrate and calibration is None:
            if not corners:
                print(
                    "[camera] FOUT: geen hoek-coördinaten (corners) ontvangen voor calibratie."
                )
                return
            calibration = _calibrate_physical(
                server_url,
                area_id,
                mode,
                corners,
                cap,
                detector,
                tracker,
                frame_w,
                frame_h,
            )
            if calibration is None:
                print("[camera] Calibratie afgebroken.")
                return

        def _to_wgs84(px: float, py: float) -> tuple[float, float]:
            if calibration is not None:
                return calibration.pixel_to_wgs84(px, py)
            return pixel_to_wgs84(px, py, west, north, east, south, frame_w, frame_h)

        # --- State ---
        # track_id → timestamp waarop dit track voor het eerst als stabiel gemarkeerd werd
        stable_since: dict[int, float] = {}
        # link_ids die al zijn afgesloten in deze sessie (geen heractivatie)
        triggered_links: set[int] = set()
        cooldown_until: float = 0.0

        print(
            f"[camera] Detectie gestart. Stabiel na {stable_seconds}s, cooldown {cooldown_seconds}s."
        )
        print("[camera] Druk op Ctrl+C om te stoppen.")

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[camera] Frame lezen mislukt, opnieuw proberen …")
                time.sleep(0.1)
                continue

            now = time.time()

            # --- Detectie + tracking ---
            detections = detector.detect_black_objects(frame)
            stable_dets = tracker.update(detections)

            # --- Bijhouden welke track-ids momenteel stabiel zijn ---
            stable_ids_this_frame = {d["track_id"] for d in stable_dets}

            # Verwijder stable_since-entries voor tracks die niet meer stabiel zijn
            for tid in list(stable_since.keys()):
                if tid not in stable_ids_this_frame:
                    del stable_since[tid]

            # --- Trigger-check ---
            in_cooldown = now < cooldown_until
            adjust_busy = runner.is_busy()

            for det in stable_dets:
                track_id = det["track_id"]

                # Registreer eerste moment van stabiliteit
                if track_id not in stable_since:
                    stable_since[track_id] = now

                duration = now - stable_since[track_id]

                # Progress-feedback elke seconde
                if int(duration) != int(duration - 0.033):  # ~30fps ticks
                    cx, cy = det["center"]
                    lon, lat = _to_wgs84(cx, cy)
                    print(
                        f"[camera] Blokje stabiel {duration:.1f}s  "
                        f"px=({cx:.0f},{cy:.0f})  "
                        f"wgs84=({lon:.6f},{lat:.6f})"
                    )

                if duration < stable_seconds:
                    continue
                if in_cooldown or adjust_busy:
                    if in_cooldown:
                        remaining = cooldown_until - now
                        print(f"[camera] Cooldown actief, nog {remaining:.0f}s")
                    continue

                # Pixel → WGS84
                cx, cy = det["center"]
                lon, lat = _to_wgs84(cx, cy)

                # Dichtstbijzijnde link
                link_ids = find_nearest_link(lon, lat, features)
                if link_ids is None:
                    print("[camera] Geen link gevonden nabij blokje.")
                    continue

                if any(lid in triggered_links for lid in link_ids):
                    print(
                        f"[camera] Links {link_ids} al eerder afgesloten, overgeslagen."
                    )
                    continue

                # Oplichten + wachten + afsluiten
                print(
                    f"[camera] Blokje {stable_seconds}s stabiel op "
                    f"({lon:.6f}, {lat:.6f}) → links {link_ids} oplichten, "
                    f"berekening over {_PREVIEW_DELAY}s …"
                )
                triggered_links.update(link_ids)
                cooldown_until = now + cooldown_seconds
                _send_preview(server_url, runner.get_area_id(), link_ids)
                time.sleep(_PREVIEW_DELAY)
                _adjust_done = threading.Event()
                runner.trigger(link_ids, on_done=_adjust_done.set)
                print("[camera] Eén berekening gestart — wachten op afronding …")
                _adjust_done.wait()
                print(
                    "[camera] Berekening klaar — camera wordt uitgeschakeld. "
                    "Zet 'm handmatig weer aan voor een volgende meting."
                )
                return

            # --- Optioneel: debug-video ---
            if show_video:
                display = frame.copy()
                # Teken stabiele detecties groen, onstabiel rood
                all_stable, all_unstable = tracker.get_visualization_detections()
                for d in all_unstable:
                    cx, cy = int(d["center"][0]), int(d["center"][1])
                    cv2.circle(display, (cx, cy), 8, (0, 0, 200), 2)
                for d in all_stable:
                    cx, cy = int(d["center"][0]), int(d["center"][1])
                    tid = d["track_id"]
                    duration = now - stable_since.get(tid, now)
                    color = (0, 200, 0) if duration >= stable_seconds else (0, 165, 255)
                    cv2.circle(display, (cx, cy), 10, color, 2)
                    cv2.putText(
                        display,
                        f"{duration:.1f}s",
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
        description="Maquette camera — detecteert zwart blokje en sluit wegvak af."
    )
    p.add_argument("--server", default="http://localhost:8080", help="Server base URL")
    p.add_argument("--area-id", required=True, help="Initieel area_id (UUID)")
    p.add_argument("--mode", default="CAR", help="Transportmodus (CAR/BIKE/PEDESTRIAN)")
    p.add_argument(
        "--viewport-west", type=float, required=True, help="Viewport west-grens (lon)"
    )
    p.add_argument(
        "--viewport-north", type=float, required=True, help="Viewport noord-grens (lat)"
    )
    p.add_argument(
        "--viewport-east", type=float, required=True, help="Viewport oost-grens (lon)"
    )
    p.add_argument(
        "--viewport-south", type=float, required=True, help="Viewport zuid-grens (lat)"
    )
    p.add_argument(
        "--width", type=int, required=True, help="Viewport breedte in pixels"
    )
    p.add_argument(
        "--height", type=int, required=True, help="Viewport hoogte in pixels"
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
        help="Seconden stilstand voordat weg wordt afgesloten (default: 3.0)",
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
        "--calibrate",
        action="store_true",
        help="Start in calibratiemodus: meet twee hoeken op en negeer bestaande calibratie",
    )
    p.add_argument(
        "--view-json",
        default="",
        help="JSON met kaartweergave (center/zoom/bearing/pitch) om in de calibratie op te slaan",
    )
    p.add_argument(
        "--corners-json",
        default="",
        help="JSON met de 4 geo-hoeken {bl,br,tr,tl} van het scherm-uitgelijnde vierkant",
    )
    p.add_argument(
        "--pixels-json",
        default="",
        help="JSON met scherm-pixelhoeken {bl:[x,y],tr:[x,y]} (virtuele modus: directe calibratie)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.view_json:
        try:
            _CALIB_VIEW = json.loads(args.view_json)
        except (ValueError, TypeError):
            _CALIB_VIEW = None
    _corners = None
    if args.corners_json:
        try:
            _corners = json.loads(args.corners_json)
        except (ValueError, TypeError):
            _corners = None
    _pixels = None
    if args.pixels_json:
        try:
            _pixels = json.loads(args.pixels_json)
        except (ValueError, TypeError):
            _pixels = None
    run(
        server_url=args.server.rstrip("/"),
        area_id=args.area_id,
        mode=args.mode,
        viewport_west=args.viewport_west,
        viewport_north=args.viewport_north,
        viewport_east=args.viewport_east,
        viewport_south=args.viewport_south,
        width=args.width,
        height=args.height,
        camera_id=args.camera_id,
        stable_seconds=args.stable_seconds,
        cooldown_seconds=args.cooldown,
        show_video=args.show_video,
        calibrate=args.calibrate,
        corners=_corners,
        pixels=_pixels,
    )
