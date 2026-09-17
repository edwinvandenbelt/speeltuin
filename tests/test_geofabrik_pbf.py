"""Tests for scripts.geofabrik_pbf."""

from pathlib import Path

import pytest
from shapely.geometry import Polygon

import scripts.geofabrik_pbf as gpf


SIMPLE_POLY = """none
1
   0.0   0.0
   1.0   0.0
   1.0   1.0
   0.0   1.0
   0.0   0.0
END
END
"""

MULTI_POLY = """test
1
   0.0   0.0
   1.0   0.0
   1.0   1.0
   0.0   1.0
   0.0   0.0
END
2
   2.0   2.0
   3.0   2.0
   3.0   3.0
   2.0   3.0
   2.0   2.0
END
END
"""


class TestParsePoly:
    def test_simple_polygon(self) -> None:
        geom = gpf.parse_poly(SIMPLE_POLY)
        assert isinstance(geom, Polygon)
        assert geom.area == pytest.approx(1.0)

    def test_multi_polygon(self) -> None:
        geom = gpf.parse_poly(MULTI_POLY)
        assert geom.geom_type == "MultiPolygon"
        assert geom.area == pytest.approx(2.0)


def test_bbox_polygon() -> None:
    bbox = gpf.bbox_polygon(0.1, 0.1, 0.9, 0.9)
    assert bbox.area == pytest.approx(0.64)


def test_find_covering_extracts(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    extract = gpf.Extract("test", "Test", "dummy/test", 10)

    # Monkeypatch registry for the test
    original_registry = gpf._GEOFABRIK_REGISTRY
    gpf._GEOFABRIK_REGISTRY = [extract]
    # Write the polygon into cache so fetch_poly does not hit the network
    (cache_dir / "test.poly").write_text(SIMPLE_POLY, encoding="utf-8")

    try:
        matches = gpf.find_covering_extracts(0.1, 0.1, 0.9, 0.9, cache_dir=cache_dir)
        assert len(matches) == 1
        assert matches[0].slug == "test"

        outside = gpf.find_covering_extracts(1.5, 1.5, 1.9, 1.9, cache_dir=cache_dir)
        assert outside == []
    finally:
        gpf._GEOFABRIK_REGISTRY = original_registry


def test_resolve_explicit_pbf_path(tmp_path: Path) -> None:
    pbf = tmp_path / "test.osm.pbf"
    pbf.write_bytes(b"dummy")
    assert gpf.resolve_explicit_pbf_path(str(pbf)) == pbf
    assert gpf.resolve_explicit_pbf_path(None) is None


def test_resolve_explicit_pbf_path_from_env(tmp_path: Path, monkeypatch) -> None:
    pbf = tmp_path / "env.osm.pbf"
    pbf.write_bytes(b"dummy")
    monkeypatch.setenv(gpf.OSM_PBF_ENV_VAR, str(pbf))
    assert gpf.resolve_explicit_pbf_path() == pbf
