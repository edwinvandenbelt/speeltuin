"""Tests for analyzer/wegenscan_inputs.py."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyzer"))

import wegenscan_inputs as wi  # noqa: E402
from wegenscan import calculate_kpis  # noqa: E402


@pytest.mark.parametrize(
    "surface, expected",
    [
        ("paved", "gesloten (o.a. asfalt)"),
        ("unpaved", "gedeeltelijk open"),
        ("asphalt", "gesloten (o.a. asfalt)"),
        ("paving_stones", "open (o.a.klinkers)"),
        ("concrete:plates", "gesloten (o.a. asfalt)"),
        ("sand", "gedeeltelijk open"),
    ],
)
def test_surface_follows_map_classes(surface, expected):
    assert wi.derive_surface({"surface": surface})[0] == expected


@pytest.mark.parametrize("surface", [None, math.nan, "", "asphalt;paved", "weird"])
def test_unknown_surface_is_default(surface):
    assert wi.derive_surface({"surface": surface}) == (None, None)


def test_surface_override_in_invoer():
    # translate_surface zou 'unpaved' als open (klinkers) zien.
    props = {"surface": "unpaved"}
    values, _ = wi.derive_inputs(props)
    props.update(values)
    assert wi.build_invoer_from_network(props)["r_surface"] == "gedeeltelijk open"


def test_width_rules():
    assert wi.derive_width({"roadWidthMinM": 4.0, "roadWidthMaxM": 6.0}) == (5.0, "netwerk:roadWidthMinM/MaxM")
    assert wi.derive_width({"roadWidthM": 2.5, "roadWidthMinM": math.nan}) == (5.0, "netwerk:roadWidthM")
    assert wi.derive_width({"osmWidth": 3.2})[0] == 3.2
    assert wi.derive_width({"roadWidthM": None}) == (None, None)


def test_missing_width_stays_default():
    _, sources = wi.derive_inputs({})
    assert sources["width"] == "default"


@pytest.mark.parametrize(
    "highway, speed, expected",
    [
        ("residential", 30, "ETW 30 km/h"),
        ("residential", 15, "ETW 15 km/h"),
        ("living_street", 15, "ETW 15 km/h"),
        ("secondary", 50, "GOW 50 km/h"),
        ("primary", 80, "GOW 80 km/h"),
        ("tertiary", 60, "ETW-I 60 km/h"),
        ("unclassified", 60, "ETW-II 60 km/h"),
        ("residential", 50, "GOW 50 km/h"),
        ("motorway", 100, None),
        # Zonder wegtype (netwerk zonder road-enricher): alleen op snelheid.
        (None, 30, "ETW 30 km/h"),
        (None, 50, "GOW 50 km/h"),
        (None, 80, None),
    ],
)
def test_road_category(highway, speed, expected):
    assert wi.derive_road_category_from_network({"osmHighway": highway}, speed)[0] == expected


def test_cycleway_track():
    props = {"cyclewayLeft": None, "cyclewayRight": "track", "osmOneway": False}
    values, sources = wi.derive_inputs(props)
    assert values["bicycle_location"] == "vrijliggend fietspad (eenrichting)"
    assert values["profile"] == "rijbaan auto 2 richtingen (geen fietsers)"
    assert sources["bicycle_location"] == "netwerk:cyclewayLeft/Right"


def test_cycleway_lane_oneway():
    values, _ = wi.derive_inputs({"cyclewayLeft": "lane", "osmOneway": True})
    assert values["bicycle_location"] == "fietsstroken"
    assert values["profile"] == "fietsstroken (auto 1, fiets 1 richting)"


def test_sidewalks_and_crossings():
    values, _ = wi.derive_inputs({"sidewalkLeft": "no", "sidewalkRight": "no", "speedLimit": 80})
    assert values["pedestrian_location"] == "niet van toepassing"
    assert values["pedestrian_crossing"] == "niet van toepassing"
    values, _ = wi.derive_inputs({"sidewalkRight": "separate", "numPedestrianCrossings": 1})
    assert values["pedestrian_location"] == "op voetpad/trottoir"
    assert values["pedestrian_crossing"] == "in de voorrang / zebrapad"


def test_speed_from_limit():
    values, sources = wi.derive_inputs({"speedLimit": 50.0, "osmMaxspeed": 30.0})
    assert values["max_speed"] == values["max_speed_s85"] == 50
    assert sources["max_speed"] == "netwerk:speedLimit"


def test_goor_like_link_produces_kpis():
    """Een volledig netwerklink levert geen ONBEKEND-scores op door rare strings."""
    props = {
        "speedLimit": 30.0, "osmHighway": "residential", "surface": "paving_stones",
        "roadWidthMinM": 4.4, "roadWidthMaxM": 5.4, "osmOneway": False,
        "cyclewayLeft": "shared_lane", "cyclewayRight": "shared_lane",
        "sidewalkLeft": "yes", "sidewalkRight": "yes",
        "parkingLeft": "no", "parkingRight": "no", "flow": 800.0,
    }
    values, sources = wi.derive_inputs(props)
    props.update(values)
    invoer = wi.build_invoer_from_network(props)
    assert invoer["r_category"] == "ETW 30 km/h"
    assert invoer["r_width"] == pytest.approx(4.9)
    kpis = calculate_kpis(invoer)
    assert "ONBEKEND" not in kpis.values()
    assert all(src != "default" for f, src in sources.items() if f not in ("pedestrian_crossing", "speed_bumps"))


def test_category_without_highway_has_own_source():
    assert wi.derive_road_category_from_network({}, 30) == ("ETW 30 km/h", "netwerk:speedLimit (zonder wegtype)")


@pytest.mark.parametrize(
    "props, expected",
    [
        ({"speedLimit": 30.0, "osmHighway": "residential"}, "op de rijbaan"),
        ({"speedLimit": 50.0, "osmHighway": "secondary"}, "niet van toepassing"),       # GOW 50
        ({"speedLimit": 30.0, "osmHighway": "residential", "cyclewayLeft": "lane"}, "niet van toepassing"),
        ({"speedLimit": 80.0, "osmHighway": "primary"}, "niet van toepassing"),
    ],
)
def test_parking_rule_of_thumb_is_assumption(props, expected):
    values, sources = wi.derive_inputs(props)
    assert values["parking_location"] == expected
    assert sources["parking_location"] == "aanname:vuistregel"
    assert wi.is_assumed(sources["parking_location"])


def test_parking_from_network_wins():
    values, sources = wi.derive_inputs({"speedLimit": 30.0, "parkingRight": "street_side"})
    assert values["parking_location"] == "langsparkeren"
    assert sources["parking_location"] == "netwerk:parkingLeft/Right"


def test_coverage_ignores_assumptions():
    feats = [{"properties": {"speedLimit": 30.0, "osmHighway": "residential"}}]
    cov = wi.enrich_from_network(feats)
    assert cov["parking_location"] == 0
    assert cov["road_category"] == 100
