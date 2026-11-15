"""
ArUco marker detection module.
Detects ArUco objectmarkers and returns precise 4-point polygon boundaries,
the decoded marker ID, bbox and center for each one.

Local, self-contained copy for digital-twin/maquette_camera.py — see
kien-camera-maquette/README.md in the GMP/kien-maquette repo for the original
project this is vendored from (which also has a GUI/calibration pipeline
around these same detection/tracking modules).
"""
import cv2
import numpy as np
import config
from utils.geometry_utils import is_point_in_polygon


def _polygon_center(polygon: np.ndarray) -> tuple:
    """Return the (x, y) center of a 4-point polygon via its min-area rect."""
    rect = cv2.minAreaRect(polygon)
    return (float(rect[0][0]), float(rect[0][1]))


class ArucoMarkerDetector:
    """High-level API for ArUco objectmarker detection."""

    def __init__(self, detection_area=None, dictionary=config.ARUCO_DICTIONARY):
        self.frame_counter = 0
        self.detection_area = detection_area  # Polygon vertices for region of interest

        aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        aruco_params = cv2.aruco.DetectorParameters()
        self._detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

        if self.detection_area is not None and len(self.detection_area) > 0:
            print(f"Detection area enabled with {len(self.detection_area)} vertices")
        elif self.detection_area is None:
            if config.VERBOSE:
                print("No detection area defined. All detections will be included.")

    def is_point_in_detection_area(self, x, y):
        """
        Check if a point is inside the detection area polygon using point-in-polygon test.

        Args:
            x, y: Point coordinates

        Returns:
            bool: True if point is inside detection area (or no detection area defined)
        """
        return is_point_in_polygon(x, y, self.detection_area)

    def polygon_coverage_in_detection_area(self, polygon):
        """Return the fraction of polygon pixels that lie inside detection_area."""
        if self.detection_area is None or len(self.detection_area) < 3:
            return 1.0

        obj_poly = np.array(polygon, dtype=np.float32)
        roi_poly = np.array(self.detection_area, dtype=np.float32)
        if obj_poly.shape[0] < 3:
            return 0.0

        all_pts = np.vstack((obj_poly, roi_poly))
        min_x = int(np.floor(np.min(all_pts[:, 0])))
        min_y = int(np.floor(np.min(all_pts[:, 1])))
        max_x = int(np.ceil(np.max(all_pts[:, 0])))
        max_y = int(np.ceil(np.max(all_pts[:, 1])))

        width = max(1, max_x - min_x + 1)
        height = max(1, max_y - min_y + 1)

        obj_shifted = np.round(obj_poly - np.array([min_x, min_y], dtype=np.float32)).astype(np.int32)
        roi_shifted = np.round(roi_poly - np.array([min_x, min_y], dtype=np.float32)).astype(np.int32)

        obj_mask = np.zeros((height, width), dtype=np.uint8)
        roi_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(obj_mask, [obj_shifted], 255)
        cv2.fillPoly(roi_mask, [roi_shifted], 255)

        obj_pixels = obj_mask > 0
        obj_count = int(np.count_nonzero(obj_pixels))
        if obj_count == 0:
            return 0.0

        inside_count = int(np.count_nonzero(obj_pixels & (roi_mask > 0)))
        return float(inside_count / obj_count)

    def detect_markers(self, frame, min_area=config.MIN_OBJECT_AREA,
                        max_area=config.MAX_OBJECT_AREA, known_ids=None):
        """
        Detect ArUco objectmarkers in a frame.

        ``known_ids``, if given, restricts acceptance to those marker IDs;
        anything else is rejected as ``unknown_marker_id`` (e.g. a marker
        from the wrong dictionary, or physical damage flipping a bit).

        Args:
            frame: Input frame (BGR image)
            min_area: Minimum marker-polygon area in pixels
            max_area: Maximum marker-polygon area in pixels
            known_ids: Optional iterable of acceptable marker IDs

        Returns:
            List of detections: [{'marker_id', 'bbox', 'conf', 'polygon',
            'center', 'area'}, ...]
            polygon is ordered [top-left, top-right, bottom-right, bottom-left]
            (OpenCV's own ArUco corner order).
        """
        marker_evaluations = self.analyze_marker_contours(
            frame,
            min_area=min_area,
            max_area=max_area,
            known_ids=known_ids,
        )
        return [
            item["detection"]
            for item in marker_evaluations
            if item.get("accepted") and item.get("detection") is not None
        ]

    def analyze_marker_contours(self, frame, min_area=config.MIN_OBJECT_AREA,
                                 max_area=config.MAX_OBJECT_AREA, known_ids=None):
        """Return per-marker accept/reject diagnostics for tuning and visualization."""
        self.frame_counter += 1

        corners, ids, _rejected = self._detector.detectMarkers(frame)
        evaluations = []
        if ids is None:
            return evaluations

        known_id_set = set(known_ids) if known_ids is not None else None

        for marker_corners, marker_id_arr in zip(corners, ids):
            marker_id = int(marker_id_arr[0])
            polygon = marker_corners.reshape(4, 2).astype(np.float32)
            area = float(cv2.contourArea(polygon))
            px, py, pw, ph = cv2.boundingRect(polygon.astype(np.int32))
            center = _polygon_center(polygon)

            evaluation = {
                "marker_id": marker_id,
                "accepted": False,
                "reason": "unknown",
                "bbox": [int(px), int(py), int(px + pw), int(py + ph)],
                "raw_area": area,
                "center": center,
                "detection": None,
            }

            if known_id_set is not None and marker_id not in known_id_set:
                evaluation["reason"] = "unknown_marker_id"
                evaluations.append(evaluation)
                continue

            if area < min_area:
                evaluation["reason"] = "raw_area_too_small"
                evaluations.append(evaluation)
                continue
            if area > max_area:
                evaluation["reason"] = "raw_area_too_large"
                evaluations.append(evaluation)
                continue

            # Filter by ROI overlap: require most of the detected marker inside ROI.
            roi_coverage = self.polygon_coverage_in_detection_area(polygon)
            evaluation["roi_coverage"] = roi_coverage
            if roi_coverage < config.ROI_MIN_MARKER_COVERAGE:
                evaluation["reason"] = "outside_roi"
                evaluations.append(evaluation)
                continue

            detection = {
                'marker_id': marker_id,
                'bbox': [float(px), float(py), float(px + pw), float(py + ph)],
                'conf': 1.0,
                'polygon': polygon.tolist(),
                'center': center,
                'area': area,
            }
            evaluation["reason"] = "accepted"
            evaluation["accepted"] = True
            evaluation["detection"] = detection
            evaluations.append(evaluation)

        return evaluations
