"""Tests voor de ArUco-objectmarker-detectie (issue #21).

Dekt drie lagen:
- `kien-camera-maquette/detection.py` (ArucoMarkerDetector): marker-ID,
  polygon/center/bbox, en de afwijsredenen (onbekend ID, oppervlak, ROI).
- `kien-camera-maquette/tracking.py` (DetectionTracker): matchen/stabiliteit
  op `marker_id` i.p.v. afstand.
- `maquette_camera.py`: `find_nearest_link`/`find_nearest_zone` en
  `_build_marker_changes` (de vertaling marker → change-dict per bewerking
  uit `aruco_marker_actions.MARKER_ACTIONS`).

Gebruikt een echte, gegenereerde ArUco-bitmap (geen mocks) zodat de tests ook
een kapotte dictionary-keuze of cv2-API-wijziging zouden opmerken.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

_DIGITAL_TWIN_DIR = Path(__file__).resolve().parent.parent
_KIEN_DIR = _DIGITAL_TWIN_DIR / "kien-camera-maquette"
for p in (_DIGITAL_TWIN_DIR, _KIEN_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import config  # noqa: E402  (kien-camera-maquette/config.py)
from detection import ArucoMarkerDetector  # noqa: E402
from tracking import DetectionTracker  # noqa: E402

import maquette_camera as mc  # noqa: E402
from aruco_marker_actions import MARKER_ACTIONS  # noqa: E402


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def _frame_with_marker(marker_id: int, marker_px: int = 200, frame_size: int = 400,
                        offset: "tuple[int, int]" = (100, 100)) -> np.ndarray:
    """Een wit BGR-frame met één ArUco-marker erop geplakt op `offset`."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.ARUCO_DICTIONARY)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_px)
    marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

    frame = np.full((frame_size, frame_size, 3), 255, dtype=np.uint8)
    ox, oy = offset
    frame[oy:oy + marker_px, ox:ox + marker_px] = marker_bgr
    return frame


# ---------------------------------------------------------------------------
# ArucoMarkerDetector
# ---------------------------------------------------------------------------


def test_detect_markers_reports_id_polygon_center_bbox():
    frame = _frame_with_marker(marker_id=1, marker_px=200, offset=(100, 100))
    detector = ArucoMarkerDetector()

    detections = detector.detect_markers(frame, min_area=0, max_area=1e9, known_ids={1, 2, 3})

    assert len(detections) == 1
    det = detections[0]
    assert det["marker_id"] == 1
    assert det["conf"] == 1.0
    assert len(det["polygon"]) == 4
    # Het geplakte vlak loopt van (100,100) tot net onder (300,300) - de
    # ArUco-hoeken liggen op de buitenrand van de zwart/wit-patches, dus
    # een paar pixel binnen de geplakte 200x200 regio.
    cx, cy = det["center"]
    assert 190 < cx < 210
    assert 190 < cy < 210
    assert det["area"] == pytest.approx(200 * 200, rel=0.02)


def test_unknown_marker_id_is_rejected_with_reason():
    frame = _frame_with_marker(marker_id=7)
    detector = ArucoMarkerDetector()

    evaluations = detector.analyze_marker_contours(
        frame, min_area=0, max_area=1e9, known_ids={1, 2, 3}
    )

    assert len(evaluations) == 1
    assert evaluations[0]["accepted"] is False
    assert evaluations[0]["reason"] == "unknown_marker_id"
    assert evaluations[0]["marker_id"] == 7


def test_marker_rejected_when_too_small_or_too_large():
    frame = _frame_with_marker(marker_id=1, marker_px=200)
    detector = ArucoMarkerDetector()

    too_small = detector.analyze_marker_contours(frame, min_area=1e9, max_area=1e10, known_ids={1})
    assert too_small[0]["reason"] == "raw_area_too_small"

    too_large = detector.analyze_marker_contours(frame, min_area=0, max_area=10, known_ids={1})
    assert too_large[0]["reason"] == "raw_area_too_large"


def test_marker_mostly_outside_detection_area_is_rejected():
    # Marker van (100,100)-(300,300); detectiegebied dekt alleen de linkerhelft.
    frame = _frame_with_marker(marker_id=1, marker_px=200, offset=(100, 100))
    detection_area = [[0, 0], [150, 0], [150, 400], [0, 400]]
    detector = ArucoMarkerDetector(detection_area=detection_area)

    evaluations = detector.analyze_marker_contours(frame, min_area=0, max_area=1e9, known_ids={1})

    assert evaluations[0]["reason"] == "outside_roi"
    assert evaluations[0]["roi_coverage"] < config.ROI_MIN_MARKER_COVERAGE


def test_no_markers_in_frame_returns_empty_list():
    frame = np.full((200, 200, 3), 255, dtype=np.uint8)
    detector = ArucoMarkerDetector()

    assert detector.detect_markers(frame) == []
    assert detector.analyze_marker_contours(frame) == []


# ---------------------------------------------------------------------------
# DetectionTracker: matchen/stabiliteit op marker_id
# ---------------------------------------------------------------------------


def _det(marker_id, cx, cy, half=50):
    return {
        "marker_id": marker_id,
        "bbox": [cx - half, cy - half, cx + half, cy + half],
        "conf": 1.0,
        "polygon": [[cx - half, cy - half], [cx + half, cy - half],
                    [cx + half, cy + half], [cx - half, cy + half]],
        "center": (cx, cy),
        "area": (2 * half) ** 2,
    }


def test_two_markers_become_stable_independently_by_id():
    tracker = DetectionTracker(stability_frames=5, overlap_threshold=0.75, max_allowed_distance=80)

    for _ in range(5):
        stable = tracker.update([_det(0, 100, 100), _det(1, 300, 300)])

    assert {s["marker_id"] for s in stable} == {0, 1}
    assert {s["track_id"] for s in stable} == {0, 1}  # track_id == marker_id


def test_removed_marker_is_cleaned_up_without_affecting_the_other():
    tracker = DetectionTracker(stability_frames=5, overlap_threshold=0.75, max_allowed_distance=80)
    for _ in range(5):
        tracker.update([_det(0, 100, 100), _det(1, 300, 300)])
    assert set(tracker.tracked_objects.keys()) == {0, 1}

    for _ in range(11):  # > _MAX_MISSING_FRAMES
        tracker.update([_det(1, 300, 300)])

    assert set(tracker.tracked_objects.keys()) == {1}


def test_fallback_matching_without_marker_id_uses_distance():
    # Verdedigingspad: zonder marker_id valt de tracker terug op afstand,
    # niet op exacte ID-matching (zie match_detection). Niet verwacht met
    # ArUco-input (die zet altijd een marker_id), maar wel zo bedoeld.
    tracker = DetectionTracker(stability_frames=1, overlap_threshold=0.0, max_allowed_distance=80)

    def det_without_id():
        return {
            "bbox": [0, 0, 10, 10],
            "conf": 1.0,
            "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "center": (5.0, 5.0),
            "area": 100.0,
        }

    tracker.update([det_without_id()])  # eerste frame: track wordt aangemaakt, nog niet stabiel
    stable = tracker.update([det_without_id()])  # tweede frame: binnen max_allowed_distance -> gematcht

    assert len(stable) == 1
    assert stable[0].get("marker_id") is None


# ---------------------------------------------------------------------------
# maquette_camera: find_nearest_link / find_nearest_zone / _build_marker_changes
# ---------------------------------------------------------------------------

_FEATURES = [
    {
        "type": "Feature",
        "properties": {"linkId": 100},
        "geometry": {"type": "LineString", "coordinates": [[5.0, 52.0], [5.001, 52.0]]},
    },
    {
        "type": "Feature",
        "properties": {"linkId": -100},
        "geometry": {"type": "LineString", "coordinates": [[5.001, 52.0], [5.0, 52.0]]},
    },
]

_ZONE_FEATURES = [
    {
        "type": "Feature",
        "properties": {"zoneId": "Z1"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[5.0, 52.0], [5.001, 52.0], [5.001, 52.001], [5.0, 52.001], [5.0, 52.0]]],
        },
    },
]

_NEAR_LINK_LON_LAT = (5.0005, 52.0)
_NEAR_ZONE_LON_LAT = (5.0005, 52.0005)


def test_find_nearest_link_returns_both_signed_directions():
    link_ids = mc.find_nearest_link(*_NEAR_LINK_LON_LAT, _FEATURES)
    assert link_ids is not None
    assert set(link_ids) == {100, -100}


def test_find_nearest_zone_returns_zone_id():
    assert mc.find_nearest_zone(*_NEAR_ZONE_LON_LAT, _ZONE_FEATURES) == "Z1"


def test_find_nearest_zone_without_zones_returns_none():
    assert mc.find_nearest_zone(*_NEAR_ZONE_LON_LAT, []) is None


@pytest.mark.parametrize(
    "marker_id,expected",
    [
        (0, [{"linkId": 100, "capacity": 0}, {"linkId": -100, "capacity": 0}]),
        (1, [{"linkId": 100, "speed": 30}, {"linkId": -100, "speed": 30}]),
        (2, [{"zoneId": "Z1", "production": "+100"}]),
    ],
)
def test_build_marker_changes_for_each_action(marker_id, expected):
    action_def = MARKER_ACTIONS[marker_id]
    changes = mc._build_marker_changes(
        action_def, *_NEAR_ZONE_LON_LAT, _FEATURES, _ZONE_FEATURES
    )
    assert changes == expected


def test_build_marker_changes_returns_none_without_a_target():
    close_link = MARKER_ACTIONS[0]
    assert mc._build_marker_changes(close_link, 100.0, 100.0, [], []) is None

    production = MARKER_ACTIONS[2]
    assert mc._build_marker_changes(production, 5.0005, 52.0005, _FEATURES, []) is None
