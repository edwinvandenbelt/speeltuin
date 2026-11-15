"""
Detection tracking and stability filtering module.
Tracks ArUco objectmarkers across frames to ensure they are stationary
before registering as valid detections.
Prevents false positives from moving markers or transient misreads.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import config
from utils.geometry_utils import bbox_iou

# Tracks missing for more than this many consecutive frames are discarded
_MAX_MISSING_FRAMES = 10
# Smoothing factor (EMA) for the displayed position/outline of a track: the
# weight given to the new, raw sample. Each frame re-fits the corners from
# scratch, so even a perfectly still marker wobbles a few pixels frame to
# frame - a lower value damps that wobble more but reacts slower to real
# movement. Deliberately separate from `recent_min_overlap`/stability below,
# which keeps using the raw bboxes so genuine movement is never masked.
_SMOOTHING_ALPHA = 0.3
# Starting value for the fallback sequential-ID space (detections without a
# `marker_id`, not expected with ArUco input). Offset well above any real
# ArUco ID so it can never collide with a track keyed by `marker_id` directly
# (see `match_detection`/`_create_new_track`).
_FALLBACK_ID_START = 1_000_000


def _ema_point(prev: Tuple[float, float], new: Tuple[float, float], alpha: float) -> Tuple[float, float]:
    return (prev[0] + alpha * (new[0] - prev[0]), prev[1] + alpha * (new[1] - prev[1]))


def _ema_sequence(prev: List[float], new: List[float], alpha: float) -> List[float]:
    if not prev or len(prev) != len(new):
        return list(new)
    return [p + alpha * (n - p) for p, n in zip(prev, new)]


def _ema_polygon(prev, new, alpha: float):
    if not prev or not new or len(prev) != len(new):
        return new
    return [
        [p[0] + alpha * (n[0] - p[0]), p[1] + alpha * (n[1] - p[1])]
        for p, n in zip(prev, new)
    ]


@dataclass
class Track:
    """All state for a single tracked object."""
    id: int
    first_seen_frame: int
    last_frame_number: int
    # The ArUco marker ID this track represents, or None for the
    # fallback/defensive distance-matched path (no marker_id on input).
    # Equal to `id` whenever a marker_id is present.
    marker_id: Optional[int] = None
    frames_seen: int = 1
    last_center: Tuple[float, float] = (0.0, 0.0)
    last_bbox: List[float] = field(default_factory=list)
    last_detection: Dict[str, Any] = field(default_factory=dict)
    bbox_history: List[List[float]] = field(default_factory=list)
    recent_min_overlap: float = 1.0
    matched_this_frame: bool = True
    # Smoothed (display) position/outline - see `_SMOOTHING_ALPHA`.
    smoothed_center: Tuple[float, float] = (0.0, 0.0)
    smoothed_bbox: List[float] = field(default_factory=list)
    smoothed_polygon: Optional[List[List[float]]] = None

    def is_stable(self, stability_frames: int, overlap_threshold: float) -> bool:
        """True when the track has been present long enough and consecutive
        detections keep overlapping the previous one by at least `overlap_threshold`."""
        return (
            self.frames_seen >= stability_frames
            and self.recent_min_overlap >= overlap_threshold
        )

    def stability_confidence(self, stability_frames: int, overlap_threshold: float) -> float:
        """Score in [0, 1] — higher means more stable."""
        frames_confidence = min(1.0, self.frames_seen / (stability_frames * 2))
        overlap_confidence = max(0.0, min(1.0, self.recent_min_overlap))
        return (frames_confidence + overlap_confidence) / 2


class DetectionTracker:
    """
    Tracks detections across frames to measure stability and motion.
    Only reports detections that remain stationary for a minimum duration.
    """

    def __init__(self,
                 stability_frames=config.STABILITY_FRAMES,
                 overlap_threshold=config.STABILITY_OVERLAP_THRESHOLD,
                 max_allowed_distance=config.STABILITY_MAX_DISTANCE):
        self.stability_frames = stability_frames
        self.overlap_threshold = overlap_threshold
        self.max_allowed_distance = max_allowed_distance

        self.tracked_objects: Dict[int, Track] = {}
        self.next_id = _FALLBACK_ID_START
        self.frame_count = 0

    def match_detection(self, detection: Dict[str, Any]) -> Optional[int]:
        """Return the ID of the matching unmatched track, or None.

        Primary match is exact, on `marker_id`: each objectmarker type is
        only ever active once at a time (see aruco_marker_actions.py), so
        the ArUco ID doubles as the track identity - no distance heuristic
        needed, and no ambiguity if two markers momentarily pass close to
        each other. Falls back to nearest-center matching only when
        `marker_id` is absent, which ArucoMarkerDetector never produces -
        purely defensive for non-ArUco callers.
        """
        marker_id = detection.get('marker_id')
        if marker_id is not None:
            track = self.tracked_objects.get(marker_id)
            if track is not None and not track.matched_this_frame:
                return marker_id
            return None

        detection_center = detection['center']
        best_match = None
        best_distance = float('inf')

        for obj_id, track in self.tracked_objects.items():
            if track.matched_this_frame:
                continue
            distance = np.sqrt(
                (detection_center[0] - track.last_center[0])**2
                + (detection_center[1] - track.last_center[1])**2
            )
            if distance < self.max_allowed_distance and distance < best_distance:
                best_match = obj_id
                best_distance = distance

        return best_match

    def update(self, detections) -> List[Dict[str, Any]]:
        """
        Update tracking with new frame detections.

        Args:
            detections: List of detection dicts with 'bbox', 'center', 'conf', etc.

        Returns:
            List of stable detections (stationary for required duration)
        """
        self.frame_count += 1

        for track in self.tracked_objects.values():
            track.matched_this_frame = False

        stable_detections = []
        matched_indices = set()

        for det_idx, detection in enumerate(detections):
            matching_id = self.match_detection(detection)
            if matching_id is not None:
                stable = self._update_existing_track(matching_id, detection)
                if stable:
                    stable_detections.append(stable)
                matched_indices.add(det_idx)

        for det_idx, detection in enumerate(detections):
            if det_idx not in matched_indices:
                self._create_new_track(detection)

        self._cleanup_old_tracks()
        return stable_detections

    def _update_existing_track(self, obj_id: int, detection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a matched track; return a stable detection dict if the track qualifies."""
        track = self.tracked_objects[obj_id]
        track.last_center = detection['center']
        track.last_bbox = detection['bbox']
        track.frames_seen += 1
        track.matched_this_frame = True
        track.last_frame_number = self.frame_count

        track.smoothed_center = _ema_point(track.smoothed_center, detection['center'], _SMOOTHING_ALPHA)
        track.smoothed_bbox = _ema_sequence(track.smoothed_bbox, detection['bbox'], _SMOOTHING_ALPHA)
        track.smoothed_polygon = _ema_polygon(track.smoothed_polygon, detection.get('polygon'), _SMOOTHING_ALPHA)
        detection['track_id'] = obj_id
        detection['smoothed_center'] = track.smoothed_center
        detection['smoothed_bbox'] = track.smoothed_bbox
        detection['smoothed_polygon'] = track.smoothed_polygon
        track.last_detection = detection

        track.bbox_history.append(detection['bbox'])
        recent = track.bbox_history[-self.stability_frames:]
        if len(recent) > 1:
            track.recent_min_overlap = min(
                bbox_iou(recent[i - 1], recent[i])
                for i in range(1, len(recent))
            )
        else:
            track.recent_min_overlap = 1.0
        # Bound history growth; only the last `stability_frames` entries are ever used.
        if len(track.bbox_history) > self.stability_frames:
            track.bbox_history = track.bbox_history[-self.stability_frames:]

        if track.is_stable(self.stability_frames, self.overlap_threshold):
            stable = detection.copy()
            stable['track_id'] = obj_id
            stable['frames_tracked'] = track.frames_seen
            stable['is_stable'] = True
            stable['stability_confidence'] = track.stability_confidence(
                self.stability_frames, self.overlap_threshold
            )
            return stable
        return None

    def _create_new_track(self, detection: Dict[str, Any]) -> None:
        """Register a detection as a new track.

        The track is keyed by `marker_id` directly when present, so the
        ArUco ID is the track identity; only the defensive no-marker_id path
        falls back to a sequential ID (see `_FALLBACK_ID_START`).
        """
        marker_id = detection.get('marker_id')
        if marker_id is not None:
            obj_id = marker_id
        else:
            obj_id = self.next_id
            self.next_id += 1
        detection['track_id'] = obj_id
        detection['smoothed_center'] = detection['center']
        detection['smoothed_bbox'] = list(detection['bbox'])
        detection['smoothed_polygon'] = detection.get('polygon')
        self.tracked_objects[obj_id] = Track(
            id=obj_id,
            marker_id=marker_id,
            first_seen_frame=self.frame_count,
            last_frame_number=self.frame_count,
            last_center=detection['center'],
            last_bbox=detection['bbox'],
            last_detection=detection,
            bbox_history=[list(detection['bbox'])],
            smoothed_center=detection['smoothed_center'],
            smoothed_bbox=detection['smoothed_bbox'],
            smoothed_polygon=detection['smoothed_polygon'],
        )
        if config.VERBOSE:
            print(f"[TRACKER] New object #{obj_id} at frame {self.frame_count}")

    def _cleanup_old_tracks(self) -> None:
        """Remove tracks that haven't been seen for _MAX_MISSING_FRAMES consecutive frames."""
        to_remove = [
            obj_id for obj_id, track in self.tracked_objects.items()
            if self.frame_count - track.last_frame_number > _MAX_MISSING_FRAMES
        ]
        for obj_id in to_remove:
            if config.DEBUG_MODE:
                print(f"[TRACKER] Removing track #{obj_id} (seen {self.tracked_objects[obj_id].frames_seen} frames)")
            del self.tracked_objects[obj_id]

    def get_visualization_detections(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return (stable, unstable) detection dicts for frame annotation."""
        stable = []
        unstable = []

        for obj_id, track in self.tracked_objects.items():
            detection = track.last_detection.copy()
            detection['track_id'] = obj_id
            detection['frames_tracked'] = track.frames_seen
            detection['stability_confidence'] = track.stability_confidence(
                self.stability_frames, self.overlap_threshold
            )

            if track.is_stable(self.stability_frames, self.overlap_threshold):
                detection['is_stable'] = True
                stable.append(detection)
            else:
                detection['is_stable'] = False
                unstable.append(detection)

        return stable, unstable

    def get_statistics(self) -> Dict[str, Any]:
        """Return a summary of tracker state."""
        return {
            'frame': self.frame_count,
            'active_tracks': len(self.tracked_objects),
            'total_ids_issued': self.next_id,
            'tracked_objects': self.tracked_objects,
        }

