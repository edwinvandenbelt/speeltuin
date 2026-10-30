"""Tests for analyzer/wegenscan_pipeline.py (zonder echte Databricks)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyzer"))

import wegenscan_pipeline as wp  # noqa: E402


def _fc(*props_list):
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[6.0, 52.0], [6.001, 52.001]]},
             "properties": dict(p)}
            for p in props_list
        ],
    }


NETWORK_LINK = {
    "spectrumId": 1, "speedLimit": 30.0, "osmHighway": "residential", "surface": "asphalt",
    "roadWidthMinM": 4.0, "roadWidthMaxM": 6.0, "osmOneway": False,
    "sidewalkLeft": "yes", "flow": 500.0, "wvkIds": "[11, 12]",
}


def test_wvk_keys():
    assert wp._wvk_keys({"wvkIds": "[1, 2]"}, "spectrumId") == ["1", "2"]
    assert wp._wvk_keys({"wvkIds": [3]}, "spectrumId") == ["3"]
    assert wp._wvk_keys({"wvkIds": None, "spectrumId": 7}, "spectrumId") == ["7"]
    assert wp._wvk_keys({"wvkIds": "[]", "spectrumId": 7}, "spectrumId") == ["7"]
    assert wp._wvk_keys({}, "spectrumId") == []


def test_majority():
    assert wp._majority({"1": "a", "2": "b", "3": "b"}, ["1", "2", "3"]) == "b"
    assert wp._majority({"1": "a"}, ["9"]) is None


def test_network_only_needs_no_databricks(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("Databricks mag niet aangeroepen worden")

    monkeypatch.setattr(wp, "_query_lookups", boom)
    result = wp.run_pipeline(_fc(NETWORK_LINK))
    props = result["features"][0]["properties"]
    assert props["width"] == 5.0
    assert props["road_category"] == "ETW 30 km/h"
    assert props["generic_safety"] in ("GOED", "REDELIJK", "MATIG", "SLECHT")
    assert result["wegenscan_coverage"]["width"] == 100


def test_motorway_out_of_scope():
    result = wp.run_pipeline(_fc({**NETWORK_LINK, "osmHighway": "motorway", "speedLimit": 100.0}))
    props = result["features"][0]["properties"]
    assert props["generic_safety"] == "NVT"
    assert props["safety"] == {}


def test_databricks_only_fills_defaults(monkeypatch):
    lookups = {
        "speed": {"11": (50, 47), "12": (50, 47)},
        "wegcat": {"11": 6},
        "profile": {"11": {"profile": "fietsstroken (auto 2, fiets 2 richtingen)",
                           "bicycle_location": "fietsstroken"}},
        "pedestrian": {"11": {"pedestrian_location": "niet van toepassing"}},
        "parking": {"12": {"parking_location": "langsparkeren", "parking_width": 2.0}},
        "bumps": {"11": "op wegvakken"},
    }
    monkeypatch.setattr(wp, "_query_lookups", lambda _g: lookups)
    result = wp.run_pipeline(_fc(NETWORK_LINK), use_databricks=True)
    props = result["features"][0]["properties"]
    src = props["wegenscan_sources"]

    # Netwerkwaarden blijven staan.
    assert props["max_speed"] == 30 and src["max_speed"] == "netwerk:speedLimit"
    assert props["road_category"] == "ETW 30 km/h"
    assert props["pedestrian_location"] == "op voetpad/trottoir"
    # s85 komt altijd uit Databricks.
    assert props["max_speed_s85"] == 47 and src["max_speed_s85"] == "databricks:s85"
    # Defaults worden aangevuld.
    assert props["bicycle_location"] == "fietsstroken"
    assert src["bicycle_location"] == "databricks:wkd_vrkrstpnv2"
    assert props["parking_location"] == "langsparkeren" and props["parking_width"] == 2.0
    assert props["speed_bumps"] == "op wegvakken"


def test_failed_queries_change_nothing(monkeypatch):
    empty = {k: {} for k in ("speed", "wegcat", "profile", "pedestrian", "parking", "bumps")}
    monkeypatch.setattr(wp, "_query_lookups", lambda _g: empty)
    with_db = wp.run_pipeline(_fc(NETWORK_LINK), use_databricks=True)["features"][0]["properties"]
    without = wp.run_pipeline(_fc(NETWORK_LINK))["features"][0]["properties"]
    assert with_db["safety"] == without["safety"]
    assert with_db.get("max_speed") != -1


def test_very_wide_road_does_not_crash():
    """Bermschade-tabel stopt bij 20 m; bredere wegen gaven een NameError in het wheel."""
    result = wp.run_pipeline(_fc({**NETWORK_LINK, "roadWidthMinM": 22.0, "roadWidthMaxM": 26.0}))
    props = result["features"][0]["properties"]
    assert props["safety"]["r_roadside_damage"] in ("GOED", "REDELIJK", "SLECHT")
