"""Shared geometry helpers for polygon and bounding-box operations."""

import cv2
import numpy as np


def is_point_in_polygon(x, y, polygon):
    """Return True when point (x, y) lies inside or on the boundary of polygon."""
    if polygon is None or len(polygon) < 3:
        return True

    poly = np.array(polygon, dtype=np.int32)
    result = cv2.pointPolygonTest(poly, (float(x), float(y)), False)
    return result >= 0


def bbox_to_polygon(bbox):
    """Convert [x1, y1, x2, y2] to 4-corner polygon (TL, TR, BR, BL)."""
    x1, y1, x2, y2 = bbox
    return [
        (x1, y1),
        (x2, y1),
        (x2, y2),
        (x1, y2),
    ]


def bbox_iou(bbox_a, bbox_b):
    """Return Intersection-over-Union of two [x1, y1, x2, y2] boxes (0..1)."""
    ax1, ay1, ax2, ay2 = bbox_a
    bx1, by1, bx2, by2 = bbox_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0.0:
        return 0.0

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area
    if union_area <= 0.0:
        return 0.0

    return inter_area / union_area
