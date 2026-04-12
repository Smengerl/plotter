"""Compatibility adapter for mediapipe API differences.

Provides a single entrypoint `generate_annotation(img_rgb, max_faces, min_confidence)`
that returns an RGB numpy array with face annotations (or zeros if mediapipe not
available). The adapter tries the old `mp.solutions` API first, then the newer
`mediapipe.tasks` API, and falls back to a no-op image when unavailable.
"""
from __future__ import annotations

from typing import Optional
import warnings
import numpy as np

try:
    import mediapipe as mp
except Exception:
    mp = None


def _has_solutions_api() -> bool:
    return mp is not None and hasattr(mp, "solutions")


def _has_tasks_api() -> bool:
    # Newer mediapipe versions expose 'tasks' (mediapipe.tasks).
    return mp is not None and hasattr(mp, "tasks")


def generate_annotation(img_rgb: np.ndarray, max_faces: int, min_confidence: float) -> np.ndarray:
    """Return an RGB annotation image (same shape as img_rgb) or zeros if not available.

    Args:
        img_rgb: HxWx3 uint8 RGB image
        max_faces: number of faces to detect
        min_confidence: detection confidence threshold

    Returns:
        HxWx3 uint8 image containing annotations or zeros if no annotator available.
    """
    if not isinstance(img_rgb, np.ndarray):
        raise TypeError("img_rgb must be a numpy array")
    if img_rgb.ndim != 3 or img_rgb.shape[2] != 3:
        raise ValueError("img_rgb must be HxWx3 RGB image")

    # Old API: mp.solutions.FaceMesh
    if _has_solutions_api():
        try:
            mp_drawing = mp.solutions.drawing_utils
            mp_face_mesh = mp.solutions.face_mesh
        except Exception:
            warnings.warn("mediapipe.solutions import failed despite attribute existing; falling back")
        else:
            try:
                with mp_face_mesh.FaceMesh(
                    static_image_mode=True,
                    max_num_faces=max_faces,
                    refine_landmarks=True,
                    min_detection_confidence=min_confidence,
                ) as facemesh:
                    results = facemesh.process(img_rgb).multi_face_landmarks
                    if results is None:
                        return np.zeros_like(img_rgb)
                    empty = np.zeros_like(img_rgb)
                    for face_landmarks in results:
                        try:
                            mp_drawing.draw_landmarks(
                                empty,
                                face_landmarks,
                                mp_face_mesh.FACEMESH_TESSELATION,
                            )
                        except Exception:
                            # best-effort: ignore per-face drawing errors
                            continue
                    # convert BGR->RGB if needed (mp drawing uses RGB here)
                    return empty
            except Exception:
                warnings.warn("mediapipe FaceMesh failed; falling back to other API or no-op")

    # Newer API: mediapipe.tasks (FaceLandmarker)
    if _has_tasks_api():
        try:
            # Import lazily to avoid hard dependency on older mediapipe
            from mediapipe.tasks import python as mp_tasks
            from mediapipe.tasks.python import vision as mp_vision
        except Exception:
            warnings.warn("mediapipe.tasks import failed; falling back")
        else:
            try:
                options = mp_vision.FaceLandmarkerOptions(
                    base_options=mp_tasks.BaseOptions(),
                    num_faces=max_faces,
                    min_face_confidence=min_confidence,
                )
                with mp_vision.FaceLandmarker.create_from_options(options) as landmarker:
                    detection_result = landmarker.detect(img_rgb)
                    if not detection_result.face_landmarks:
                        return np.zeros_like(img_rgb)
                    empty = np.zeros_like(img_rgb)
                    # Simple drawing: draw landmarks as small squares
                    for face in detection_result.face_landmarks:
                        for lm in face:
                            x = int(lm.x * img_rgb.shape[1])
                            y = int(lm.y * img_rgb.shape[0])
                            x0 = max(0, x - 1)
                            y0 = max(0, y - 1)
                            empty[y0:y0 + 3, x0:x0 + 3] = (255, 255, 255)
                    return empty
            except Exception:
                warnings.warn("mediapipe.tasks FaceLandmarker failed; falling back to no-op")

    # No mediapipe available or all strategies failed
    warnings.warn("Mediapipe not available or incompatible; returning empty annotation image", RuntimeWarning)
    return np.zeros_like(img_rgb)
