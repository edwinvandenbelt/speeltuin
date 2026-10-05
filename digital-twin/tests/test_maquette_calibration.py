"""Tests voor maquette_calibration.py.

Deze module heeft bewust geen afhankelijkheden (geen OpenCV, geen requests, geen
Windows-API's, niet het externe kien-camera-maquette project), zodat deze tests
overal draaien.
"""

import json
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maquette_calibration import (  # noqa: E402
    Calibration,
    Homography,
    _merc,
    _merc_inv,
    apply_homography,
    homography_residual,
    invert_homography,
    load_calibration,
    solve_homography,
)


# Een realistische maquette-opstelling: camerabeeld van 1920x1080 dat schuin op
# een gebied rond Deventer kijkt. De geo-hoeken vormen bewust geen rechthoek —
# dat is precies het perspectief dat de oude calibratie niet kon vangen.
FRAME_W, FRAME_H = 1920, 1080
IMAGE_POINTS = [[0, 0], [1920, 0], [1920, 1080], [0, 1080]]
GEO_POINTS = [
    [6.157042, 52.259559],
    [6.174050, 52.258102],
    [6.171338, 52.251549],
    [6.158901, 52.252914],
]


def _random_quad(rng):
    """Een willekeurige, niet-ontaarde vierhoek."""
    return [
        [rng.uniform(-50, 50), rng.uniform(-50, 50)],
        [rng.uniform(950, 1050), rng.uniform(-50, 50)],
        [rng.uniform(950, 1050), rng.uniform(750, 850)],
        [rng.uniform(-50, 50), rng.uniform(750, 850)],
    ]


# ---------------------------------------------------------------------------
# 1. Solver-rondgang
# ---------------------------------------------------------------------------


def test_solver_maps_source_onto_destination_exactly():
    rng = random.Random(20260928)
    src = [(0.0, 0.0), (1920.0, 0.0), (1920.0, 1080.0), (0.0, 1080.0)]
    for _ in range(50):
        dst = [tuple(p) for p in _random_quad(rng)]
        h = solve_homography(src, dst)
        for (u, v), (x, y) in zip(src, dst):
            px, py = apply_homography(h, u, v)
            assert math.hypot(px - x, py - y) < 1e-9


def test_solver_is_invertible_round_trip():
    """H gevolgd door de omgekeerde H brengt een willekeurig punt terug."""
    src = [(0.0, 0.0), (1920.0, 0.0), (1920.0, 1080.0), (0.0, 1080.0)]
    dst = [(10.0, 20.0), (1900.0, -40.0), (1850.0, 1100.0), (60.0, 1000.0)]
    forward = solve_homography(src, dst)
    backward = solve_homography(dst, src)
    for u, v in [(0.0, 0.0), (960.0, 540.0), (1919.0, 1079.0), (123.0, 456.0)]:
        x, y = apply_homography(forward, u, v)
        bu, bv = apply_homography(backward, x, y)
        assert math.hypot(bu - u, bv - v) < 1e-6


def test_solver_rejects_degenerate_input():
    src = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]  # collineair
    dst = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    with pytest.raises(ValueError):
        solve_homography(src, dst)

    same = [(5.0, 5.0)] * 4
    with pytest.raises(ValueError):
        solve_homography(same, dst)

    with pytest.raises(ValueError):
        solve_homography(src[:3], dst[:3])


# ---------------------------------------------------------------------------
# 2. Vergelijking met OpenCV als onafhankelijk orakel
# ---------------------------------------------------------------------------


def test_matches_opencv_get_perspective_transform():
    cv2 = pytest.importorskip("cv2")
    numpy = pytest.importorskip("numpy")

    rng = random.Random(7)
    src = [(0.0, 0.0), (1920.0, 0.0), (1920.0, 1080.0), (0.0, 1080.0)]
    for _ in range(20):
        dst = [tuple(p) for p in _random_quad(rng)]
        ours = solve_homography(src, dst)
        theirs = cv2.getPerspectiveTransform(
            numpy.array(src, dtype=numpy.float32),
            numpy.array(dst, dtype=numpy.float32),
        ).flatten()
        theirs = [v / theirs[8] for v in theirs]
        # OpenCV rekent op float32-invoer, vandaar de ruimere marge; het gaat
        # erom dat beide dezelfde afbeelding beschrijven.
        for u, v in [(0.0, 0.0), (960.0, 540.0), (1920.0, 1080.0)]:
            ax, ay = apply_homography(ours, u, v)
            bx, by = apply_homography(list(theirs), u, v)
            assert math.hypot(ax - bx, ay - by) < 1e-3


# ---------------------------------------------------------------------------
# 3. Conditionering met echte Mercator-coördinaten
# ---------------------------------------------------------------------------


def test_conditioning_with_real_mercator_coordinates():
    """Het stelsel blijft nauwkeurig met echte, slecht geschaalde coördinaten.

    Mercator-coördinaten liggen rond 6,17 en 0,92 terwijl beeldpixels rond 10^3
    liggen; de verschillen die het stelsel moet oplossen zijn ~1e-3 van de
    absolute waarden. Gemeten: met vier punten haalt float64 dit ook zonder
    Hartley-normalisatie (~2e-15 graden). De normalisatie is er voor de
    kleinste-kwadraten-tak, waar AᵀA het conditiegetal kwadrateert.
    """
    src = [(float(p[0]), float(p[1])) for p in IMAGE_POINTS]
    dst = [(p[0], _merc(p[1])) for p in GEO_POINTS]
    h = solve_homography(src, dst)

    rms, worst = homography_residual(h, src, dst)
    assert worst < 1e-12, f"residu te groot: {worst}"
    assert rms < 1e-12

    # Omgerekend naar meters moet de hoekfout verwaarloosbaar zijn.
    lat = GEO_POINTS[0][1]
    metres_per_lon_degree = 111_320 * math.cos(math.radians(lat))
    assert worst * metres_per_lon_degree < 1e-6


# ---------------------------------------------------------------------------
# 4. Homography-klasse
# ---------------------------------------------------------------------------


def test_homography_maps_image_corners_to_geo_corners():
    hom = Homography(IMAGE_POINTS, GEO_POINTS, FRAME_W, FRAME_H)
    for (px, py), (lon, lat) in zip(IMAGE_POINTS, GEO_POINTS):
        got_lon, got_lat = hom.pixel_to_wgs84(px, py)
        assert abs(got_lon - lon) < 1e-11
        assert abs(got_lat - lat) < 1e-11


def test_homography_centre_pixel_lies_inside_the_quad():
    hom = Homography(IMAGE_POINTS, GEO_POINTS, FRAME_W, FRAME_H)
    lon, lat = hom.pixel_to_wgs84(FRAME_W / 2, FRAME_H / 2)
    assert min(p[0] for p in GEO_POINTS) < lon < max(p[0] for p in GEO_POINTS)
    assert min(p[1] for p in GEO_POINTS) < lat < max(p[1] for p in GEO_POINTS)


def test_homography_survives_a_dict_round_trip():
    hom = Homography(IMAGE_POINTS, GEO_POINTS, FRAME_W, FRAME_H, view={"zoom": 15.7})
    restored = Homography.from_dict(json.loads(json.dumps(hom.to_dict("CAR", 1))))
    assert restored is not None
    for px, py in [(0, 0), (500, 400), (1919, 1079)]:
        assert restored.pixel_to_wgs84(px, py) == pytest.approx(
            hom.pixel_to_wgs84(px, py), abs=1e-12
        )


def test_homography_rescales_to_a_different_camera_resolution():
    """Levert de camera een andere resolutie, dan blijft het beeldveld gelijk."""
    hom = Homography(IMAGE_POINTS, GEO_POINTS, FRAME_W, FRAME_H)
    half = hom.rescaled(FRAME_W // 2, FRAME_H // 2)
    # Dezelfde relatieve positie in het beeld moet dezelfde plek op de kaart geven.
    assert half.pixel_to_wgs84(480, 270) == pytest.approx(
        hom.pixel_to_wgs84(960, 540), abs=1e-12
    )


def test_extra_points_reveal_a_model_error():
    """Vier punten geven altijd residu nul; een vijfde punt legt de fout bloot.

    Dit is de reden dat de solver kleinste kwadraten aankan: met alleen de vier
    hoeken zou lensvertekening onzichtbaar blijven.
    """
    exact = Homography(IMAGE_POINTS, GEO_POINTS, FRAME_W, FRAME_H)
    assert exact.residual_max < 1e-12

    # Een vijfde meting midden op de bovenrand, 30 px verschoven zoals
    # tonvormige vertekening dat zou doen.
    true_lon, true_lat = exact.pixel_to_wgs84(960, 0)
    skewed = Homography(
        IMAGE_POINTS + [[960, 30]],
        GEO_POINTS + [[true_lon, true_lat]],
        FRAME_W,
        FRAME_H,
    )
    assert skewed.residual_max > 0.0


# ---------------------------------------------------------------------------
# 5. Legacy-formaten blijven leesbaar
# ---------------------------------------------------------------------------


LEGACY_BOUNDS = {
    "mode": "CAR",
    "camera_id": -1,
    "bounds": {
        "west": 6.157042597236995,
        "south": 52.25154967323704,
        "east": 6.174050692238325,
        "north": 52.25955959585369,
    },
    "pixels": {"bottom_left": [564.0, 424.0], "top_right": [86.0, 354.0]},
    "frame": {"width": 958, "height": 683},
}

LEGACY_CORNERS = {
    "mode": "CAR",
    "camera_id": 0,
    "corners": {
        "bl": [6.158901, 52.252914],
        "br": [6.171338, 52.251549],
        "tr": [6.174050, 52.258102],
        "tl": [6.157042, 52.259559],
    },
    "pixels": {"bottom_left": [446.0, 768.0], "top_right": [1438.0, 159.0]},
    "frame": {"width": 1920, "height": 1080},
}


@pytest.mark.parametrize("payload", [LEGACY_BOUNDS, LEGACY_CORNERS])
def test_legacy_formats_still_load(payload):
    calib = load_calibration(payload)
    assert isinstance(calib, Calibration)
    lon, lat = calib.pixel_to_wgs84(500.0, 400.0)
    assert 6.0 < lon < 6.3
    assert 52.1 < lat < 52.4


def test_legacy_reader_is_unchanged_at_the_measured_corners():
    """Regressie: de twee opgemeten hoeken moeten exact hun geo-hoek opleveren."""
    calib = load_calibration(LEGACY_CORNERS)
    assert calib.pixel_to_wgs84(446.0, 768.0) == pytest.approx(
        tuple(LEGACY_CORNERS["corners"]["bl"]), abs=1e-12
    )
    assert calib.pixel_to_wgs84(1438.0, 159.0) == pytest.approx(
        tuple(LEGACY_CORNERS["corners"]["tr"]), abs=1e-12
    )


def test_load_calibration_dispatches_on_type():
    hom = Homography(IMAGE_POINTS, GEO_POINTS, FRAME_W, FRAME_H)
    assert isinstance(load_calibration(hom.to_dict("CAR", 1)), Homography)
    assert isinstance(load_calibration(LEGACY_CORNERS), Calibration)
    assert load_calibration(None) is None
    assert load_calibration({"onzin": True}) is None


def test_mercator_helpers_round_trip():
    for lat in (-60.0, -0.5, 0.0, 52.25, 71.0):
        assert _merc_inv(_merc(lat)) == pytest.approx(lat, abs=1e-12)


# ---------------------------------------------------------------------------
# 6. Het geprojecteerde vlak: de camera ziet meer dan de beamer laat zien
# ---------------------------------------------------------------------------

# Markers op 6% inzet: het geprojecteerde vlak loopt van 0 tot 1, de markers
# staan daarbinnen. De camera kijkt ruimer, dus buiten die vierhoek liggen ook
# nog camerapixels — en daar heeft een gemeten positie geen betekenis.
SCREEN_POINTS = [[0.06, 0.06], [0.94, 0.06], [0.94, 0.94], [0.06, 0.94]]
# Waar die vier markers in het camerabeeld terechtkwamen (scheve camera).
MARKED_IN_IMAGE = [[223.4, 118.2], [1057.7, 74.1], [1143.4, 611.0], [155.7, 566.8]]


def _projected_calibration():
    geo = [
        [6.158901, 52.252914],
        [6.171338, 52.251549],
        [6.174050, 52.258102],
        [6.157042, 52.259559],
    ]
    return Homography(
        MARKED_IN_IMAGE, geo, 1280, 720, screen_points=SCREEN_POINTS
    )


def test_markers_map_back_onto_their_own_screen_positions():
    hom = _projected_calibration()
    for (px, py), (u, v) in zip(MARKED_IN_IMAGE, SCREEN_POINTS):
        got = hom.pixel_to_screen(px, py)
        assert got == pytest.approx((u, v), abs=1e-12)


def test_detection_inside_the_projection_is_accepted():
    hom = _projected_calibration()
    # Het midden van de vier markers ligt per definitie binnen het vlak.
    cx = sum(p[0] for p in MARKED_IN_IMAGE) / 4
    cy = sum(p[1] for p in MARKED_IN_IMAGE) / 4
    assert hom.is_in_projection(cx, cy)
    u, v = hom.pixel_to_screen(cx, cy)
    assert 0 < u < 1 and 0 < v < 1


def test_detection_outside_the_projection_is_rejected():
    """Dit is de kern: een blokje naast het geprojecteerde vlak mag niet tellen.

    Anders wordt er een wegvak afgesloten dat niet eens op de kaart staat.
    """
    hom = _projected_calibration()
    # Hoeken van het camerabeeld liggen ruim buiten de markervierhoek.
    for px, py in [(0, 0), (1279, 0), (1279, 719), (0, 719)]:
        assert not hom.is_in_projection(px, py), f"({px},{py}) zou buiten moeten vallen"
        u, v = hom.pixel_to_screen(px, py)
        assert not (0 <= u <= 1 and 0 <= v <= 1)


def test_margin_widens_the_accepted_area():
    hom = _projected_calibration()
    # Een punt net buiten de rand: zonder marge afgewezen, met marge geaccepteerd.
    px, py = MARKED_IN_IMAGE[0]
    outside = (px - 40, py - 30)
    assert not hom.is_in_projection(*outside)
    assert hom.is_in_projection(*outside, margin=0.5)


def test_camera_footprint_is_larger_than_the_projected_area():
    """De voetafdruk van het camerabeeld omvat het geprojecteerde vlak."""
    hom = _projected_calibration()
    corners = hom.projection_corners_wgs84()
    assert corners is not None and len(corners) == 4

    lons = [p[0] for p in corners]
    lats = [p[1] for p in corners]
    for lon, lat in hom.geo_points:          # de vier markers
        assert min(lons) < lon < max(lons)
        assert min(lats) < lat < max(lats)


def test_calibration_without_screen_points_stays_permissive():
    """Oude bestanden hebben geen schermpunten; die moeten blijven werken."""
    hom = Homography(IMAGE_POINTS, GEO_POINTS, FRAME_W, FRAME_H)
    assert hom.pixel_to_screen(100, 100) is None
    assert hom.is_in_projection(-500, -500) is True


def test_screen_points_survive_a_dict_round_trip_and_rescale():
    hom = _projected_calibration()
    restored = Homography.from_dict(json.loads(json.dumps(hom.to_dict("CAR", 1))))
    assert restored is not None
    assert restored.pixel_to_screen(640, 360) == pytest.approx(
        hom.pixel_to_screen(640, 360), abs=1e-12
    )
    half = hom.rescaled(640, 360)
    assert half.pixel_to_screen(320, 180) == pytest.approx(
        hom.pixel_to_screen(640, 360), abs=1e-12
    )


# ---------------------------------------------------------------------------
# 7. De uitsnede: welk stuk camerabeeld hoort bij de maquette
# ---------------------------------------------------------------------------


def _point_in_quad(px, py, quad):
    """Ligt (px, py) binnen de (convexe) vierhoek? Puur voor de tests."""
    sign = 0
    for i in range(4):
        ax, ay = quad[i]
        bx, by = quad[(i + 1) % 4]
        cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        if abs(cross) < 1e-12:
            continue
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def test_inverse_homography_is_a_true_inverse():
    hom = _projected_calibration()
    inverse = invert_homography(hom.h_screen)
    for px, py in [(100.0, 80.0), (640.0, 360.0), (1200.0, 700.0)]:
        u, v = apply_homography(hom.h_screen, px, py)
        assert apply_homography(inverse, u, v) == pytest.approx((px, py), abs=1e-6)


def test_projection_polygon_maps_back_onto_the_unit_square():
    """De uitsnede is precies het geprojecteerde vlak: schermfracties 0..1."""
    hom = _projected_calibration()
    polygon = hom.projection_polygon()
    assert len(polygon) == 4
    expected = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for (px, py), want in zip(polygon, expected):
        assert hom.pixel_to_screen(px, py) == pytest.approx(want, abs=1e-9)


def test_projection_polygon_contains_the_markers_and_excludes_the_rest():
    """De kern: het blokje op de maquette telt mee, de kamer eromheen niet."""
    hom = _projected_calibration()
    polygon = hom.projection_polygon()

    # De markers staan op 6% inzet en liggen dus binnen het vlak.
    for px, py in MARKED_IN_IMAGE:
        assert _point_in_quad(px, py, polygon), f"marker ({px},{py}) valt buiten"

    # De hoeken van het camerabeeld kijken naast de maquette.
    for px, py in [(0, 0), (1279, 0), (1279, 719), (0, 719)]:
        assert not _point_in_quad(px, py, polygon), f"({px},{py}) valt binnen"


def test_projection_polygon_agrees_with_is_in_projection():
    """Uitsnede en triggercontrole moeten hetzelfde gebied beschrijven.

    Zouden ze uiteenlopen, dan verdwijnen detecties die wel getriggerd hadden
    mogen worden — of andersom.
    """
    hom = _projected_calibration()
    polygon = hom.projection_polygon()
    rng = random.Random(20260929)
    for _ in range(400):
        px = rng.uniform(-200, 1480)
        py = rng.uniform(-200, 920)
        assert _point_in_quad(px, py, polygon) == hom.is_in_projection(px, py)


def test_mask_margin_widens_the_cutout():
    hom = _projected_calibration()
    tight = hom.projection_polygon()
    loose = hom.projection_polygon(0.10)
    for px, py in tight:
        assert _point_in_quad(px, py, loose)
    for px, py in loose:
        assert not _point_in_quad(px, py, tight)


def test_picked_polygon_is_exactly_what_was_pointed_at():
    """Het werkgebied is de vierhoek die je hebt aangewezen — niet meer."""
    hom = _projected_calibration()
    for got, want in zip(hom.picked_polygon(), MARKED_IN_IMAGE):
        assert got == pytest.approx(want, abs=1e-9)


def test_picked_polygon_is_smaller_than_the_projected_plane():
    """Het verschil dat eerder vlakken buiten de maquette liet meetellen.

    De markers liggen met hun inzet *binnen* de projectie, dus het
    geprojecteerde vlak is ruimer dan wat je hebt afgebakend. Uitsnijden op de
    projectie laat daarom een rand buiten de maquette staan.
    """
    hom = _projected_calibration()
    picked = hom.picked_polygon()
    projected = hom.projection_polygon()
    for px, py in picked:
        assert _point_in_quad(px, py, projected)
    for px, py in projected:
        assert not _point_in_quad(px, py, picked)


def _quad_area(quad):
    return abs(
        sum(
            quad[i][0] * quad[(i + 1) % 4][1] - quad[(i + 1) % 4][0] * quad[i][1]
            for i in range(4)
        )
    ) / 2


def test_projected_plane_grows_with_the_marker_inset():
    """Hoe verder de markers naar binnen staan, hoe groter het verschil.

    De ondergrens is de vlakke schatting (1/(1-2·inzet))²: bij 6% inzet
    beslaan de markers 88% van de zijde, dus ~1,3x in oppervlak. Perspectief
    maakt het in de praktijk iets méér, nooit minder — en bij een kwart inzet
    loopt het op tot ruim vier keer het afgebakende gebied.
    """
    ratios = []
    for inset in (0.06, 0.15, 0.25):
        screen = [
            [inset, inset],
            [1 - inset, inset],
            [1 - inset, 1 - inset],
            [inset, 1 - inset],
        ]
        hom = Homography(MARKED_IN_IMAGE, GEO_POINTS, 1280, 720, screen_points=screen)
        ratio = _quad_area(hom.projection_polygon()) / _quad_area(hom.picked_polygon())
        flat = (1 / (1 - 2 * inset)) ** 2
        assert flat <= ratio <= flat * 1.15
        ratios.append(ratio)

    assert ratios == sorted(ratios)
    assert ratios[-1] > 4.0


def test_projection_polygon_falls_back_to_the_picked_quad():
    """Oud calibratiebestand zonder schermpunten: dan is de aangewezen vierhoek
    het werkgebied. Krapper dan het echte vlak, maar nooit het hele beeld."""
    hom = Homography(MARKED_IN_IMAGE, GEO_POINTS, 1280, 720)
    polygon = hom.projection_polygon()
    for got, want in zip(polygon, MARKED_IN_IMAGE):
        assert got == pytest.approx(want, abs=1e-9)
    assert not _point_in_quad(0, 0, polygon)
