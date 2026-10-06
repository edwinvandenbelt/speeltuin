"""
Detection/tracking configuration for the digital-twin maquette camera.

Local, self-contained copy for digital-twin/maquette_camera.py: only the
constants that detection.py and tracking.py actually read. The full
kien-camera-maquette project (GMP/kien-maquette repo) has a much larger
config.py with calibration-GUI/camera-device settings that don't apply here
— maquette_calibration.py and maquette_camera.py's own CLI flags cover that
for the digital twin.
"""

# Detection settings
# the minimum contrast score (0-1) for color-mask detections: the surrounding region must be
# this fraction brighter (in HSV Value) than the object interior.
MINIMUM_CONTRAST_SCORE = 0.2  # 0.2 = 20 % brightness difference required
BLACK_OBJECT_VALUE_THRESHOLD = 150  # Maximum brightness (V in HSV) for black objects
# Was 50: under normal room lighting (not a dark projected background) the
# phone's own mean V measured 93-132, so 50 rejected it outright as
# "not_absolutely_black" before it ever reached the tracker. 150 leaves
# headroom above that while still excluding clearly bright/white surfaces.
BLACK_OBJECT_SAT_THRESHOLD = 255  # Maximum saturation (S in HSV) for black objects
BLACK_OBJECT_LOCAL_DARKNESS_THRESHOLD = 18  # Minimum local brightness drop for projected dark blocks
# Fallback area bounds (pixels). detection.py reads these as default argument
# values, but maquette_camera.py always passes explicit min_area/max_area
# (derived from the calibrated ROI as a percentage, see `_area_thresholds`),
# so these two are never actually used there.
MIN_OBJECT_AREA = 400
MAX_OBJECT_AREA = 2500
# Minimum fraction of a detected block polygon that must be inside the ROI.
ROI_MIN_BLOCK_COVERAGE = 0.8

# Detection stability/temporal filtering
# (For stationary blocks on projected surface - prevents false positives from moving blocks)
STABILITY_FRAMES = 5  # Number of consecutive detections required
# Minimum bbox overlap (IoU, 0-1) required between each of the last STABILITY_FRAMES
# detections and the one before it for the block to count as "stable".
STABILITY_OVERLAP_THRESHOLD = 0.75
STABILITY_MAX_DISTANCE = 80  # Max distance to match detection to previous frame (pixels)

# Debug and logging
DEBUG_MODE = False
VERBOSE = False
