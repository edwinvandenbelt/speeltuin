"""
Black object detection module using HSV color masking and contrast analysis.
Detects dark objects against bright backgrounds without any ML model.
Returns precise 4-point polygon boundaries for each detected object.

Local, self-contained copy for digital-twin/maquette_camera.py — see
kien-camera-maquette/README.md in the GMP/kien-maquette repo for the original
project this is vendored from (which also has a GUI/calibration pipeline
around these same detection/tracking modules).
"""
import cv2
import numpy as np
import config
from utils.geometry_utils import is_point_in_polygon

# Padding (pixels) around a detected bounding box used to sample the
# surrounding brightness for the contrast check.
_CONTRAST_RING_PX = 20


def _order_polygon_points(points):
    """Return four points ordered as top-left, top-right, bottom-right, bottom-left."""
    pts = np.array(points, dtype=np.float32)
    if pts.shape != (4, 2):
        return pts

    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)

    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(sums)]
    ordered[2] = pts[np.argmax(sums)]
    ordered[1] = pts[np.argmin(diffs)]
    ordered[3] = pts[np.argmax(diffs)]
    return ordered


def _build_dark_mask(frame, value_threshold, sat_threshold):
    """Build a candidate mask for dark objects on bright, projected backgrounds."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    hsv_lower = np.array([0, 0, 0], dtype=np.uint8)
    hsv_upper = np.array([180, sat_threshold, value_threshold], dtype=np.uint8)
    hsv_mask = cv2.inRange(hsv, hsv_lower, hsv_upper)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred_background = cv2.GaussianBlur(gray, (0, 0), sigmaX=51, sigmaY=51)
    local_darkness = cv2.subtract(blurred_background, gray)
    _, adaptive_mask = cv2.threshold(
        local_darkness,
        config.BLACK_OBJECT_LOCAL_DARKNESS_THRESHOLD,
        255,
        cv2.THRESH_BINARY,
    )

    dark_mask = cv2.bitwise_or(hsv_mask, adaptive_mask)

    kernel = np.ones((3, 3), dtype=np.uint8)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return dark_mask, hsv, local_darkness


def build_mask_preview(
    frame,
    value_threshold=config.BLACK_OBJECT_VALUE_THRESHOLD,
    sat_threshold=config.BLACK_OBJECT_SAT_THRESHOLD,
):
    """Return the current binary mask plus a masked-frame preview for tuning."""
    dark_mask, _, _ = _build_dark_mask(frame, value_threshold, sat_threshold)
    masked_frame = cv2.bitwise_and(frame, frame, mask=dark_mask)
    return dark_mask, masked_frame

class BlackObjectDetector:
    """High-level API for black object detection using HSV color masking."""

    def __init__(
        self,
        detection_area=None,
        value_threshold=config.BLACK_OBJECT_VALUE_THRESHOLD,
        sat_threshold=config.BLACK_OBJECT_SAT_THRESHOLD,
    ):
        self.frame_counter = 0
        self.detection_area = detection_area  # Polygon vertices for region of interest
        self.value_threshold = value_threshold
        self.sat_threshold = sat_threshold

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
    
    def detect_black_objects(self, frame, conf_threshold=config.MINIMUM_CONTRAST_SCORE,
                             min_area=config.MIN_OBJECT_AREA,
                             max_area=config.MAX_OBJECT_AREA, use_color_filter=True):
        """
        Detect dark objects against a bright background using HSV color masking.

        ``conf_threshold`` is the minimum contrast score (0–1) required for a
        blob to be accepted.  A score of 0.2 means the surrounding region must
        be at least 20 % brighter (in HSV Value) than the object interior.

        Args:
            frame: Input frame (BGR image)
            conf_threshold: Minimum contrast score (0–1) for acceptance
            min_area: Minimum contour area in pixels
            max_area: Maximum contour area in pixels
            use_color_filter: Ignored — kept for call-site backward compatibility

        Returns:
            List of detections: [{'bbox', 'conf', 'polygon', 'center', 'area',
            'mean_v', 'mean_s', 'mean_local_darkness'}, ...]
            polygon is ordered [top-left, top-right, bottom-right, bottom-left].
        """
        contour_evaluations = self.analyze_black_object_contours(
            frame,
            conf_threshold=conf_threshold,
            min_area=min_area,
            max_area=max_area,
            use_color_filter=use_color_filter,
        )
        return [
            item["detection"]
            for item in contour_evaluations
            if item.get("accepted") and item.get("detection") is not None
        ]

    def analyze_black_object_contours(self, frame, conf_threshold=config.MINIMUM_CONTRAST_SCORE,
                                      min_area=config.MIN_OBJECT_AREA,
                                      max_area=config.MAX_OBJECT_AREA, use_color_filter=True):
        """Return per-contour accept/reject diagnostics for tuning and visualization."""
        self.frame_counter += 1
        fh, fw = frame.shape[:2]

        # Projected scenes can tint "black" objects, so use both HSV and local darkness.
        dark_mask, hsv, local_darkness_map = _build_dark_mask(
            frame,
            self.value_threshold,
            self.sat_threshold,
        )

        contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        v_channel = hsv[:, :, 2]  # brightness channel for contrast sampling
        s_channel = hsv[:, :, 1]  # saturation channel for block-stat sampling
        evaluations = []

        for contour in contours:
            area = float(cv2.contourArea(contour))
            bx, by, bw, bh = cv2.boundingRect(contour)

            evaluation = {
                "contour": contour,
                "accepted": False,
                "reason": "unknown",
                "bbox": [int(bx), int(by), int(bx + bw), int(by + bh)],
                "raw_area": area,
                "contrast_score": 0.0,
                "center": (float(bx + bw * 0.5), float(by + bh * 0.5)),
                "detection": None,
            }

            if area < min_area:
                evaluation["reason"] = "raw_area_too_small"
                evaluations.append(evaluation)
                continue
            if area > max_area:
                evaluation["reason"] = "raw_area_too_large"
                evaluations.append(evaluation)
                continue

            # --- Contrast check ---
            # Measure object stats on the actual contour mask (not full bbox)
            # so rotated/slender blobs are not diluted by bright background pixels.
            obj_roi = v_channel[by:by + bh, bx:bx + bw]
            sat_roi = s_channel[by:by + bh, bx:bx + bw]
            local_darkness_roi = local_darkness_map[by:by + bh, bx:bx + bw]

            contour_roi = contour.copy()
            contour_roi[:, 0, 0] -= bx
            contour_roi[:, 0, 1] -= by
            obj_mask = np.zeros((bh, bw), dtype=np.uint8)
            cv2.drawContours(obj_mask, [contour_roi], -1, 255, thickness=-1)
            obj_pixels = obj_mask > 0

            if np.any(obj_pixels):
                mean_v_obj = float(np.mean(obj_roi[obj_pixels]))
                mean_s_obj = float(np.mean(sat_roi[obj_pixels]))
                mean_local_darkness = float(np.mean(local_darkness_roi[obj_pixels]))
            else:
                mean_v_obj = float(np.mean(obj_roi)) if obj_roi.size > 0 else 0.0
                mean_s_obj = float(np.mean(sat_roi)) if sat_roi.size > 0 else 0.0
                mean_local_darkness = (
                    float(np.mean(local_darkness_roi)) if local_darkness_roi.size > 0 else 0.0
                )

            # Sample a border ring around the contour, clamped to frame bounds.
            # Exclude object pixels and other dark-mask pixels so surrounding
            # brightness is estimated from the actual projected background.
            rx1 = max(0, bx - _CONTRAST_RING_PX)
            ry1 = max(0, by - _CONTRAST_RING_PX)
            rx2 = min(fw, bx + bw + _CONTRAST_RING_PX)
            ry2 = min(fh, by + bh + _CONTRAST_RING_PX)
            ring_roi = v_channel[ry1:ry2, rx1:rx2]
            ring_dark_roi = dark_mask[ry1:ry2, rx1:rx2]

            ring_obj_mask = np.zeros(ring_roi.shape, dtype=np.uint8)
            ring_contour = contour.copy()
            ring_contour[:, 0, 0] -= rx1
            ring_contour[:, 0, 1] -= ry1
            cv2.drawContours(ring_obj_mask, [ring_contour], -1, 255, thickness=-1)

            ring_background = (ring_obj_mask == 0)
            bright_background = ring_background & (ring_dark_roi == 0)
            surrounding_pixels = ring_roi[bright_background]

            if surrounding_pixels.size == 0:
                surrounding_pixels = ring_roi[ring_background]

            mean_v_surround = (
                float(np.mean(surrounding_pixels)) if surrounding_pixels.size > 0 else mean_v_obj
            )

            contrast_score = max(0.0, (mean_v_surround - mean_v_obj) / (mean_v_surround + 1e-6))
            evaluation["contrast_score"] = contrast_score
            evaluation["mean_v"] = mean_v_obj
            evaluation["mean_s"] = mean_s_obj
            evaluation["mean_local_darkness"] = mean_local_darkness

            # The dark_mask candidate can come from `adaptive_mask` alone (a
            # patch merely darker than its *local* surround, e.g. road lines,
            # UI icons or projector banding), without ever satisfying the
            # absolute HSV black test. Without this gate, any locally-dark
            # gray patch with enough contrast to its surround is accepted as
            # if it were the black phone. Re-check the absolute brightness/
            # saturation here so "black" still means black, not "darker than
            # its neighbours".
            if mean_v_obj > self.value_threshold or mean_s_obj > self.sat_threshold:
                evaluation["reason"] = "not_absolutely_black"
                evaluations.append(evaluation)
                continue

            if contrast_score < conf_threshold:
                evaluation["reason"] = "contrast_too_low"
                evaluations.append(evaluation)
                continue

            # --- Fit 4-point polygon ---
            perimeter = cv2.arcLength(contour, True)
            polygon = None
            for eps in (0.02, 0.03, 0.04, 0.05, 0.06):
                approx = cv2.approxPolyDP(contour, eps * perimeter, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    polygon = approx.reshape(4, 2).astype(np.float32)
                    break

            if polygon is None:
                rect = cv2.minAreaRect(contour)
                w_r, h_r = rect[1]
                if w_r <= 1 or h_r <= 1:
                    evaluation["reason"] = "degenerate_rect"
                    evaluations.append(evaluation)
                    continue
                polygon = cv2.boxPoints(rect).astype(np.float32)

            polygon = _order_polygon_points(polygon)
            rect = cv2.minAreaRect(polygon)
            center_x, center_y = rect[0]
            evaluation["center"] = (float(center_x), float(center_y))

            # Filter by ROI overlap: require most of the detected block inside ROI.
            roi_coverage = self.polygon_coverage_in_detection_area(polygon)
            evaluation["roi_coverage"] = roi_coverage
            if roi_coverage < config.ROI_MIN_BLOCK_COVERAGE:
                evaluation["reason"] = "outside_roi"
                evaluations.append(evaluation)
                continue

            poly_area = float(cv2.contourArea(polygon))
            px, py, pw, ph = cv2.boundingRect(polygon.astype(np.int32))
            bbox_area = float(max(0, pw) * max(0, ph))
            evaluation["bbox"] = [int(px), int(py), int(px + pw), int(py + ph)]

            detection = {
                'bbox': [float(px), float(py), float(px + pw), float(py + ph)],
                'conf': contrast_score,
                'polygon': polygon.tolist(),
                'center': (float(center_x), float(center_y)),
                'area': poly_area,
                'mean_v': mean_v_obj,
                'mean_s': mean_s_obj,
                'mean_local_darkness': mean_local_darkness,
            }
            evaluation["reason"] = "accepted"
            evaluation["accepted"] = True
            evaluation["detection"] = detection
            evaluations.append(evaluation)

        return evaluations

    def set_black_thresholds(self, value_threshold: int, sat_threshold: int) -> None:
        """Update runtime thresholds used by the color filter."""
        self.value_threshold = value_threshold
        self.sat_threshold = sat_threshold