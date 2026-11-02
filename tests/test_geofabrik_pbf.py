"""Tests for scripts.geofabrik_pbf (thin layer over gmt_shared.geofabrik)."""

from pathlib import Path

import gmt_shared.geofabrik

import scripts.geofabrik_pbf as gpf

SIMPLE_POLY = """netherlands
1
   0.0   0.0
   1.0   0.0
   1.0   1.0
   0.0   1.0
   0.0   0.0
END
END
"""


def test_is_within_netherlands(tmp_path: Path) -> None:
    # A cached .poly keeps load_poly off the network.
    (tmp_path / "netherlands.poly").write_text(SIMPLE_POLY, encoding="utf-8")
    assert gpf.is_within_netherlands(0.1, 0.1, 0.9, 0.9, cache_dir=tmp_path)
    assert not gpf.is_within_netherlands(0.5, 0.5, 1.5, 0.9, cache_dir=tmp_path)


def test_reexports_gmt_shared() -> None:
    assert gpf.local_pbf_for_bbox is gmt_shared.geofabrik.local_pbf_for_bbox
    assert gpf.OSM_PBF_ENV_VAR == "OSM_PBF_PATH"
    assert gpf.OSM_PBF_CACHE_DIR_ENV_VAR == "OSM_PBF_CACHE_DIR"
