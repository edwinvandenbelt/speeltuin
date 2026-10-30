"""Tests for analyzer/wegenscan_assets.py (synthetische geometrie in RD New)."""

import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyzer"))

import wegenscan_assets as wa  # noqa: E402
import wegenscan_inputs as wi  # noqa: E402

# Oost-west-weg van 100 m in Goor (RD-coördinaten), 6 m breed.
X0, Y0 = 237000.0, 474000.0
ROAD_RD = LineString([(X0, Y0), (X0 + 100, Y0)])


def _link(**props):
    geom = gpd.GeoSeries([ROAD_RD], crs="EPSG:28992").to_crs("EPSG:4326").iloc[0]
    return {"type": "Feature", "geometry": mapping(geom),
            "properties": {"roadWidthMinM": 6.0, "roadWidthMaxM": 6.0, **props}}


def _assets(rows):
    """rows: (assetType, polygon in RD, extra props)."""
    return gpd.GeoDataFrame(
        [{"assetType": t, "source": "BGT", **extra} for t, _, extra in rows],
        geometry=[g for _, g, _ in rows],
        crs="EPSG:28992",
    ).to_crs("EPSG:4326")


def _run(rows, **props):
    feats = [_link(**props)]
    wa.link_assets(feats, _assets(rows))
    return feats[0]["properties"]


def test_langsparkeren_strip():
    # 2 m diep, 60 m lang, direct naast de rijbaan (rand op 3 m van de as).
    p = _run([("parkingArea", box(X0 + 20, Y0 + 3, X0 + 80, Y0 + 5), {})])
    assert p["assetParkingLocation"] == "langsparkeren"
    assert abs(p["assetParkingWidth"] - 2.0) < 0.01


def test_haaksparkeren_strip():
    p = _run([("parkingArea", box(X0 + 20, Y0 + 3, X0 + 80, Y0 + 8), {})])
    assert p["assetParkingLocation"] == "haaksparkeren"


def test_parking_lot_is_ignored():
    p = _run([("parkingArea", box(X0 + 20, Y0 + 3, X0 + 80, Y0 + 40), {})])
    assert "assetParkingLocation" not in p


def test_parking_on_crossing_street_is_ignored():
    # Vak langs een noord-zuidstraat bij het eindpunt: dekt maar ~2 m van de link.
    p = _run([("parkingArea", box(X0 + 101, Y0 + 3, X0 + 103, Y0 + 50), {})])
    assert "assetParkingLocation" not in p


def test_historical_bgt_version_is_ignored():
    p = _run([("parkingArea", box(X0 + 20, Y0 + 3, X0 + 80, Y0 + 5),
               {"eind_registratie": "2022-06-03T00:28:36Z"})])
    assert "assetParkingLocation" not in p


def test_speed_bumps_section_and_junction():
    mid = _run([("speedBump", box(X0 + 48, Y0 - 3, X0 + 52, Y0 + 3), {})])
    assert mid["assetSpeedBumps"] == "op wegvakken"
    end = _run([("speedBump", box(X0 + 95, Y0 - 3, X0 + 99, Y0 + 3), {})])
    assert end["assetSpeedBumps"] == "op kruispunten"


# Twee verre vakjes zodat de bbox van de assets de weg omvat.
FAR_CORNERS = [("parkingArea", box(X0 - 500, Y0 - 500, X0 - 495, Y0 - 495), {}),
               ("parkingArea", box(X0 + 600, Y0 + 500, X0 + 605, Y0 + 505), {})]


def test_no_bump_in_bgt_area_is_observation():
    p = _run(FAR_CORNERS)
    values, sources = wi.derive_inputs(p)
    assert values["speed_bumps"] == "niet aanwezig"
    assert sources["speed_bumps"] == "assets:speedBump (geen)"


def test_without_bgt_no_observation():
    feats = [_link()]
    assets = _assets(FAR_CORNERS)
    assets["source"] = "OSM"
    wa.link_assets(feats, assets)
    assert "assetsCovered" not in feats[0]["properties"]


def test_asset_parking_wins_over_rule_of_thumb():
    p = _run([("parkingArea", box(X0 + 20, Y0 + 3, X0 + 80, Y0 + 8), {})],
             speedLimit=30.0, osmHighway="residential")
    values, sources = wi.derive_inputs(p)
    assert values["parking_location"] == "haaksparkeren"
    assert sources["parking_location"] == "assets:parkingArea"
    assert values["parking_width"] > 3.5
