"""
Detection/tracking configuration for the digital-twin maquette camera.

Local, self-contained copy for digital-twin/maquette_camera.py: only the
constants that detection.py and tracking.py actually read. The full
kien-camera-maquette project (GMP/kien-maquette repo) has a much larger
config.py with calibration-GUI/camera-device settings that don't apply here
— maquette_calibration.py and maquette_camera.py's own CLI flags cover that
for the digital twin.
"""
import cv2

# Detection settings
# ArUco dictionary used for the physical objectmarkers (see
# aruco_marker_actions.py). DICT_4X4_50 is small and robust, which suits
# markers read at close range (roughly 1-1.5 m).
ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50
# Fallback area bounds (pixels). detection.py reads these as default argument
# values, but maquette_camera.py always passes explicit min_area/max_area
# (derived from the calibrated ROI as a percentage, see `_area_thresholds`),
# so these two are never actually used there.
MIN_OBJECT_AREA = 400
MAX_OBJECT_AREA = 2500
# Minimum fraction of a detected marker polygon that must be inside the ROI.
ROI_MIN_MARKER_COVERAGE = 0.8

# Detection stability/temporal filtering
# (For stationary markers - prevents false positives from a marker being
# placed/moved or a transient misread)
STABILITY_FRAMES = 5  # Number of consecutive detections required
# Minimum bbox overlap (IoU, 0-1) required between each of the last STABILITY_FRAMES
# detections and the one before it for the marker to count as "stable".
STABILITY_OVERLAP_THRESHOLD = 0.75
# Only used by tracking.py's fallback/defensive distance-matching path (no
# marker_id on the detection) - exact marker_id matching needs no distance
# threshold. Kept for that fallback and for tests exercising it directly.
STABILITY_MAX_DISTANCE = 80  # Max distance to match detection to previous frame (pixels)

# Debug and logging
DEBUG_MODE = False
VERBOSE = False
