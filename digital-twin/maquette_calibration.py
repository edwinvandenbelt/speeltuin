"""
maquette_calibration.py — coördinaten- en calibratiewiskunde voor de maquette
=============================================================================

Deze module bevat **alleen rekenwerk**: geen OpenCV, geen requests, geen
Windows-API's en geen afhankelijkheid van het externe `kien-camera-maquette`
project. Daardoor is ze zonder camera-opstelling te importeren en te testen.

`maquette_camera.py` importeert hieruit; de browser heeft een eigen kopie van de
homografie-solver in `maquette-calibration.js`.

Drie calibratieformaten worden gelezen (`load_calibration`):

1. ``type: "homography"`` — het huidige formaat. Vier beeldpunten (camerapixels)
   gekoppeld aan vier geo-punten, opgelost als één 3x3 homografie. Corrigeert
   perspectief, en dus een camera die niet loodrecht boven de maquette hangt.
2. ``corners`` + ``pixels`` — legacy: twee opgemeten hoeken, bilineair over vier
   geo-hoeken geïnterpoleerd. Vangt offset/schaal/rotatie, geen perspectief.
3. ``bounds`` — legacy: noord-uitgelijnde bbox.

Waarom Web-Mercator en niet lon/lat
-----------------------------------
Camera → maquette-oppervlak is een projectieve afbeelding, maquette →
beamerbeeld ook, en beamerbeeld → Web-Mercator is een gelijkvormigheid (de
maquette-modus forceert ``pitch = 0``). De samenstelling is dus opnieuw
projectief en wordt exact beschreven door één 3x3 homografie — mits je in
Mercator-ruimte rekent (``x = lon``, ``y = _merc(lat)``). In lon/lat zou de
afbeelding niet-projectief zijn en zou de fout noord-zuid oplopen.
"""

import math

__all__ = [
    "_merc",
    "_merc_inv",
    "pixel_to_wgs84",
    "solve_homography",
    "apply_homography",
    "invert_homography",
    "homography_residual",
    "Homography",
    "Calibration",
    "load_calibration",
]


# ---------------------------------------------------------------------------
# Web-Mercator helpers
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
    Camera-pixel (cx, cy) → (lon, lat) WGS84 — terugval zonder calibratie.

    Aanname: camera exact loodrecht boven de maquette en de beamer projecteert
    exact hetzelfde gebied, zodat pixels lineair op de viewport-bounds mappen.
    """
    lon = west + (cx / width) * (east - west)
    merc_n = _merc(north)
    merc_s = _merc(south)
    merc_y = merc_n + (cy / height) * (merc_s - merc_n)
    lat = _merc_inv(merc_y)
    return lon, lat


# ---------------------------------------------------------------------------
# Homografie
# ---------------------------------------------------------------------------


def _normalization(points: "list[tuple[float, float]]") -> tuple[float, float, float]:
    """Hartley-normalisatie: (cx, cy, s) zodat de punten rond de oorsprong

    liggen met gemiddelde afstand sqrt(2). Zonder deze stap is het 8x8-stelsel
    slecht geconditioneerd: beeldpixels liggen rond 10^3 terwijl mercator-
    coördinaten rond 6,17 en 0,92 liggen met zeven significante cijfers.
    """
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    mean_dist = sum(math.hypot(p[0] - cx, p[1] - cy) for p in points) / n
    if mean_dist < 1e-15:
        raise ValueError("ontaarde puntenset: alle punten vallen samen")
    return cx, cy, math.sqrt(2.0) / mean_dist


def _solve_linear(a: "list[list[float]]", b: "list[float]") -> "list[float]":
    """Los a·x = b op met Gaussische eliminatie en partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-14:
            raise ValueError("singulier stelsel: punten zijn collineair of vallen samen")
        m[col], m[pivot] = m[pivot], m[col]

        inv = 1.0 / m[col][col]
        for j in range(col, n + 1):
            m[col][j] *= inv

        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                m[r][j] -= factor * m[col][j]

    return [m[i][n] for i in range(n)]


def _mat3_mul(a: "list[float]", b: "list[float]") -> "list[float]":
    """Vermenigvuldig twee 3x3-matrices (rij-major, 9 floats)."""
    out = [0.0] * 9
    for r in range(3):
        for c in range(3):
            out[r * 3 + c] = (
                a[r * 3 + 0] * b[0 * 3 + c]
                + a[r * 3 + 1] * b[1 * 3 + c]
                + a[r * 3 + 2] * b[2 * 3 + c]
            )
    return out


def solve_homography(
    src: "list[tuple[float, float]]",
    dst: "list[tuple[float, float]]",
) -> "list[float]":
    """
    Bepaal de 3x3 homografie H die de punten `src` op `dst` afbeeldt.

    Geeft 9 floats terug in rij-major volgorde, genormaliseerd op H[8] == 1.
    Beide lijsten moeten even lang zijn en in dezelfde volgorde staan.

    Vier punten geven een exacte oplossing. **Meer** punten worden in
    kleinste-kwadratenzin opgelost — dat is geen luxe: met precies vier punten
    is het residu per constructie nul, zodat modelfouten (met name
    lensvertekening van een groothoekcamera) onzichtbaar blijven. Met extra
    controlepunten wordt `residual` een echte maat voor de restfout.
    """
    if len(src) != len(dst):
        raise ValueError("solve_homography verwacht even veel bron- als doelpunten")
    if len(src) < 4:
        raise ValueError("solve_homography verwacht minstens vier puntparen")

    # --- Hartley-normalisatie aan beide kanten ---
    scx, scy, ss = _normalization(src)
    dcx, dcy, ds = _normalization(dst)
    ns = [((p[0] - scx) * ss, (p[1] - scy) * ss) for p in src]
    nd = [((p[0] - dcx) * ds, (p[1] - dcy) * ds) for p in dst]

    # --- Stelsel voor de genormaliseerde punten (h22 = 1) ---
    a: "list[list[float]]" = []
    b: "list[float]" = []
    for (u, v), (x, y) in zip(ns, nd):
        a.append([u, v, 1.0, 0.0, 0.0, 0.0, -u * x, -v * x])
        b.append(x)
        a.append([0.0, 0.0, 0.0, u, v, 1.0, -u * y, -v * y])
        b.append(y)

    if len(a) == 8:
        h = _solve_linear(a, b)
    else:
        # Overbepaald: normaalvergelijkingen AᵀA·h = Aᵀb — weer een 8x8-stelsel,
        # dus dezelfde eliminatiecode.
        ata = [[sum(row[i] * row[j] for row in a) for j in range(8)] for i in range(8)]
        atb = [sum(row[i] * b[k] for k, row in enumerate(a)) for i in range(8)]
        h = _solve_linear(ata, atb)

    h_norm = [h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], 1.0]

    # --- Normalisatie terugdraaien: H = T_dst^-1 · Ĥ · T_src ---
    t_src = [ss, 0.0, -ss * scx, 0.0, ss, -ss * scy, 0.0, 0.0, 1.0]
    t_dst_inv = [1.0 / ds, 0.0, dcx, 0.0, 1.0 / ds, dcy, 0.0, 0.0, 1.0]
    result = _mat3_mul(t_dst_inv, _mat3_mul(h_norm, t_src))

    if abs(result[8]) < 1e-15:
        raise ValueError("ontaarde homografie")
    return [value / result[8] for value in result]


def homography_residual(
    h: "list[float]",
    src: "list[tuple[float, float]]",
    dst: "list[tuple[float, float]]",
) -> tuple[float, float]:
    """Geef (rms, max) afwijking van H·src t.o.v. dst, in eenheden van dst.

    Bij vier punten is dit per constructie ~0 en dus alleen een controle op de
    solver zelf. Bij meer punten is het de werkelijke modelfout.
    """
    errors = []
    for (u, v), (x, y) in zip(src, dst):
        px, py = apply_homography(h, u, v)
        errors.append(math.hypot(px - x, py - y))
    if not errors:
        return 0.0, 0.0
    rms = math.sqrt(sum(e * e for e in errors) / len(errors))
    return rms, max(errors)


def apply_homography(h: "list[float]", u: float, v: float) -> tuple[float, float]:
    """Pas homografie `h` toe op punt (u, v)."""
    w = h[6] * u + h[7] * v + h[8]
    if abs(w) < 1e-15:
        raise ValueError("punt valt op de horizon van de homografie")
    return (
        (h[0] * u + h[1] * v + h[2]) / w,
        (h[3] * u + h[4] * v + h[5]) / w,
    )


def invert_homography(h: "list[float]") -> "list[float]":
    """Inverse van een 3x3 homografie (rij-major, 9 floats).

    Nodig om de andere kant op te rekenen: van een positie in het geprojecteerde
    vlak terug naar de camerapixel die daarbij hoort. Daarmee is de omtrek van
    dat vlak in camerapixels uit te drukken — en dus uit te snijden.

    Resultaat is weer genormaliseerd op H[8] == 1.
    """
    m00, m01, m02, m10, m11, m12, m20, m21, m22 = h
    det = (
        m00 * (m11 * m22 - m12 * m21)
        - m01 * (m10 * m22 - m12 * m20)
        + m02 * (m10 * m21 - m11 * m20)
    )
    if abs(det) < 1e-18:
        raise ValueError("singuliere homografie: niet te inverteren")

    # Adjugaat = getransponeerde cofactormatrix.
    adj = [
        m11 * m22 - m12 * m21,
        m02 * m21 - m01 * m22,
        m01 * m12 - m02 * m11,
        m12 * m20 - m10 * m22,
        m00 * m22 - m02 * m20,
        m02 * m10 - m00 * m12,
        m10 * m21 - m11 * m20,
        m01 * m20 - m00 * m21,
        m00 * m11 - m01 * m10,
    ]
    inv = [value / det for value in adj]
    if abs(inv[8]) < 1e-15:
        raise ValueError("ontaarde inverse homografie")
    return [value / inv[8] for value in inv]


class Homography:
    """Camerapixel → WGS84 via een perspectivische (projectieve) afbeelding.

    De browser koppelt vier beeldpunten — standaard de hoeken van het
    camerabeeld — aan vier punten op de kaart, door het live camerabeeld over de
    kaart te leggen en de hoeken te verslepen tot beide beelden samenvallen.

    Volgorde van de punten is overal `tl, tr, br, bl`, maar de wiskunde vereist
    alleen dat `image_points` en `geo_points` in dezelfde volgorde staan.
    """

    type = "homography"

    def __init__(
        self,
        image_points: "list[list[float]]",
        geo_points: "list[list[float]]",
        frame_w: int = 0,
        frame_h: int = 0,
        view: "dict | None" = None,
        screen_points: "list[list[float]] | None" = None,
    ):
        self.image_points = [[float(p[0]), float(p[1])] for p in image_points]
        self.geo_points = [[float(p[0]), float(p[1])] for p in geo_points]
        self.frame_w = int(frame_w)
        self.frame_h = int(frame_h)
        self.view = view
        # Rekenen gebeurt in Mercator-ruimte; alleen daar is de afbeelding
        # projectief en dus exact door één matrix te beschrijven.
        merc_points = [(p[0], _merc(p[1])) for p in self.geo_points]
        img_points = [(p[0], p[1]) for p in self.image_points]
        self.h = solve_homography(img_points, merc_points)
        # Restfout in mercator-eenheden; bij vier punten ~0, bij meer punten de
        # werkelijke modelfout (lensvertekening).
        self.residual_rms, self.residual_max = homography_residual(
            self.h, img_points, merc_points
        )

        # Tweede afbeelding: camerapixel → positie binnen het geprojecteerde
        # vlak, als fractie (0..1 in beide richtingen). De camera ziet namelijk
        # méér dan de beamer projecteert; buiten dat vlak is de kaart niet
        # zichtbaar en heeft een gemeten positie geen betekenis.
        self.screen_points = (
            [[float(p[0]), float(p[1])] for p in screen_points]
            if screen_points
            else None
        )
        self.h_screen = None
        if self.screen_points and len(self.screen_points) == len(img_points):
            try:
                self.h_screen = solve_homography(
                    img_points, [(p[0], p[1]) for p in self.screen_points]
                )
            except ValueError:
                self.h_screen = None

    def pixel_to_wgs84(self, px: float, py: float) -> tuple[float, float]:
        """Camerapixel (px, py) → (lon, lat)."""
        lon, merc_y = apply_homography(self.h, px, py)
        return lon, _merc_inv(merc_y)

    def pixel_to_screen(self, px: float, py: float) -> "tuple[float, float] | None":
        """Camerapixel → fractie binnen het geprojecteerde vlak (0..1).

        Geeft None als de calibratie geen schermpunten bevat (oud bestand).
        """
        if self.h_screen is None:
            return None
        try:
            return apply_homography(self.h_screen, px, py)
        except ValueError:
            return None

    def is_in_projection(self, px: float, py: float, margin: float = 0.0) -> bool:
        """Ligt deze camerapixel binnen het gebied dat de beamer projecteert?

        Zonder schermpunten (oud calibratiebestand) valt dit niet vast te
        stellen; dan gaan we ervan uit van wel, zodat oude opstellingen blijven
        werken zoals ze deden.
        """
        uv = self.pixel_to_screen(px, py)
        if uv is None:
            return True
        u, v = uv
        return -margin <= u <= 1 + margin and -margin <= v <= 1 + margin

    def picked_polygon(self, margin: float = 0.0) -> "list[list[float]]":
        """De vierhoek die je tijdens het calibreren hebt aangewezen.

        Dit is letterlijk `image_points`: de vier punten waar je de handvatten op
        de markers hebt gelegd. Dat is het gebied dat je zelf als maquettevlak
        hebt afgebakend, en dus het gebied dat telt.

        `margin` rekt de vierhoek op om zijn eigen middelpunt; 0,05 geeft 5%
        speling aan elke kant.
        """
        cx = sum(p[0] for p in self.image_points) / 4
        cy = sum(p[1] for p in self.image_points) / 4
        scale = 1.0 + 2.0 * margin
        return [
            [cx + (p[0] - cx) * scale, cy + (p[1] - cy) * scale]
            for p in self.image_points
        ]

    def projection_polygon(self, margin: float = 0.0) -> "list[list[float]]":
        """De omtrek van het hele geprojecteerde vlak, in camerapixels.

        Let op het verschil met `picked_polygon`: de markers liggen met hun
        inzet *binnen* de projectie, dus dit vlak is groter dan de vierhoek die
        je hebt aangewezen — bij een inzet van 6% zo'n 1,3x, bij 25% ruim 4x in
        oppervlak. Voor het afbakenen van het werkgebied is dat de verkeerde
        keuze: buiten jouw vierhoek ligt weliswaar nog kaart, maar niet meer per
        se maquette.

        Het is wél het vlak waar de kaart zichtbaar is, en daarmee de juiste
        maat voor `is_in_projection`.
        """
        if self.h_screen is not None:
            corners = [
                (-margin, -margin),
                (1.0 + margin, -margin),
                (1.0 + margin, 1.0 + margin),
                (-margin, 1.0 + margin),
            ]
            try:
                inverse = invert_homography(self.h_screen)
                return [list(apply_homography(inverse, u, v)) for u, v in corners]
            except ValueError:
                pass

        # Geen (bruikbare) schermpunten — oud calibratiebestand. Dan is de
        # aangewezen vierhoek zelf het beste dat we hebben; die valt iets krapper
        # uit dan het geprojecteerde vlak, precies de inzet van de markers.
        return self.picked_polygon(margin)

    def projection_corners_wgs84(self) -> "list[list[float]] | None":
        """De vier hoeken van het camerabeeld in (lon, lat).

        Daarmee kun je op de kaart tekenen hoe ver de camera kijkt.
        """
        if not self.frame_w or not self.frame_h:
            return None
        w, h = float(self.frame_w), float(self.frame_h)
        try:
            return [
                list(self.pixel_to_wgs84(x, y))
                for x, y in ((0.0, 0.0), (w, 0.0), (w, h), (0.0, h))
            ]
        except ValueError:
            return None

    def rescaled(self, frame_w: int, frame_h: int) -> "Homography":
        """Zelfde calibratie, omgerekend naar een andere cameraresolutie.

        Nodig als de camera bij het starten een andere resolutie levert dan
        tijdens het calibreren; het beeldveld blijft dan gelijk, alleen de
        pixelschaal verandert.
        """
        if not self.frame_w or not self.frame_h:
            return self
        sx = frame_w / self.frame_w
        sy = frame_h / self.frame_h
        return Homography(
            image_points=[[p[0] * sx, p[1] * sy] for p in self.image_points],
            geo_points=self.geo_points,
            frame_w=frame_w,
            frame_h=frame_h,
            view=self.view,
            screen_points=self.screen_points,
        )

    def to_dict(self, mode: str, camera_id: int) -> dict:
        d = {
            "type": "homography",
            "mode": mode,
            "camera_id": camera_id,
            "frame": {"width": self.frame_w, "height": self.frame_h},
            "image_points": [list(p) for p in self.image_points],
            "geo_points": [list(p) for p in self.geo_points],
        }
        if self.screen_points:
            d["screen_points"] = [list(p) for p in self.screen_points]
        if self.view:
            d["view"] = self.view
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Homography | None":
        try:
            frame = d.get("frame") or {}
            return cls(
                image_points=d["image_points"],
                geo_points=d["geo_points"],
                frame_w=int(frame.get("width", 0) or 0),
                frame_h=int(frame.get("height", 0) or 0),
                view=d.get("view"),
                screen_points=d.get("screen_points"),
            )
        except (KeyError, TypeError, ValueError, IndexError):
            return None


# ---------------------------------------------------------------------------
# Legacy: bilineaire calibratie op twee opgemeten hoeken
# ---------------------------------------------------------------------------


class Calibration:
    """Pixel→WGS84 mapping op basis van een scherm-uitgelijnde rechthoek.

    Legacy-formaat, alleen nog om bestaande `*-CALIBRATION.json` te kunnen
    lezen. Nieuwe calibraties zijn altijd een `Homography`.

    De browser tekende een rechthoek die rechtop stond t.o.v. het scherm (niet
    noord-zuid). De vier schermhoeken zijn ge-unproject naar geo-coördinaten,
    wat bij kaartrotatie een geroteerde vierhoek in geo-ruimte oplevert:

        corners = { bl, br, tr, tl }   (elk (lon, lat))

    Twee tegenoverliggende hoeken werden opgemeten:
        bottom_left-pixel  ↔  corners['bl']
        top_right-pixel    ↔  corners['tr']

    Een willekeurige pixel wordt via de fractie (fx, fy) t.o.v. die twee
    opgemeten hoeken bilineair over de vier geo-hoeken geïnterpoleerd.
    """

    type = "bilinear"

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
                # Terugval op oudste bbox-formaat (noord-uitgelijnd)
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
# Dispatcher
# ---------------------------------------------------------------------------


def load_calibration(d: "dict | None") -> "Homography | Calibration | None":
    """Lees een calibratie-dict in het huidige of een van de legacy-formaten.

    Geeft een object met `.pixel_to_wgs84(px, py)` terug, of None als de dict
    niet te interpreteren is.
    """
    if not isinstance(d, dict):
        return None
    if d.get("type") == "homography" or "image_points" in d:
        return Homography.from_dict(d)
    return Calibration.from_dict(d)
