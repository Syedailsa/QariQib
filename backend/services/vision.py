"""
services/vision.py — YOLO + MediaPipe inference

Models are loaded once (lazy) on first call and reused across all threads.
analyze_frame() is the single public entry point.
"""

import os
import numpy as np
import cv2
from dataclasses import dataclass

# ─── Thresholds ───────────────────────────────────────────────────────────────
BLACK_FRAME_THRESHOLD = 30    # mean brightness below this = camera off / avatar
PHONE_CONF_THRESHOLD  = 0.40
FACE_CONF_THRESHOLD   = 0.50
PHONE_CLASS           = 0     # fine-tuned model class 0 = phone
CONTAINMENT_THRESHOLD = 0.72  # dedup: smaller box mostly inside larger = same object

FACE_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'face_detector.tflite')

# ─── Lazy model singletons ────────────────────────────────────────────────────
_yolo_model     = None
_face_detector  = None


PHONE_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'phone_ft.pt')


def _load_phone_model():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO(PHONE_MODEL_PATH)
        print('[VISION] Phone model loaded', flush=True)
    return _yolo_model


def _load_face_detector():
    global _face_detector
    if _face_detector is None:
        import urllib.request
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision as mp_vision

        if not os.path.exists(FACE_MODEL_PATH):
            print('[VISION] Downloading face_detector.tflite ...', flush=True)
            urllib.request.urlretrieve(
                'https://storage.googleapis.com/mediapipe-models/face_detector/'
                'blaze_face_short_range/float16/1/blaze_face_short_range.tflite',
                FACE_MODEL_PATH
            )

        options = mp_vision.FaceDetectorOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=FACE_MODEL_PATH),
            min_detection_confidence=FACE_CONF_THRESHOLD,
        )
        _face_detector = mp_vision.FaceDetector.create_from_options(options)
        print('[VISION] MediaPipe face detector loaded', flush=True)
    return _face_detector


# ─── Result type ──────────────────────────────────────────────────────────────

@dataclass
class VisionResult:
    camera_on:        bool
    face_visible:     bool
    phone_detected:   bool
    phone_confidence: float
    mean_brightness:  float


# ─── Phone deduplication ──────────────────────────────────────────────────────

def _deduplicate(detections: list) -> list:
    """
    Remove duplicate phone detections where the smaller box is largely
    contained inside the larger one (same phone detected at two scales).
    Keeps the highest-confidence detection.
    """
    if len(detections) <= 1:
        return detections

    detections = sorted(detections, key=lambda d: d['conf'], reverse=True)
    kept = []

    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        area = max((x2 - x1) * (y2 - y1), 1)
        suppress = False

        for kd in kept:
            kx1, ky1, kx2, ky2 = kd['bbox']
            karea = max((kx2 - kx1) * (ky2 - ky1), 1)
            ix1 = max(x1, kx1); iy1 = max(y1, ky1)
            ix2 = min(x2, kx2); iy2 = min(y2, ky2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            if inter > 0 and inter / min(area, karea) >= CONTAINMENT_THRESHOLD:
                suppress = True
                break

        if not suppress:
            kept.append(det)

    return kept


# ─── Public API ───────────────────────────────────────────────────────────────

def analyze_frame(frame: np.ndarray) -> VisionResult:
    """
    Run all vision checks on a single BGR numpy frame.
    Thread-safe: models are read-only after loading.
    """
    import mediapipe as mp

    gray            = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(gray))

    # Camera off — skip all inference
    if mean_brightness < BLACK_FRAME_THRESHOLD:
        return VisionResult(
            camera_on=False, face_visible=False,
            phone_detected=False, phone_confidence=0.0,
            mean_brightness=mean_brightness,
        )

    # ── Phone detection ───────────────────────────────────────────────────────
    model  = _load_phone_model()
    yolo_r = model(frame, verbose=False)[0]
    raw    = []
    for box in yolo_r.boxes:
        if int(box.cls[0]) == PHONE_CLASS and float(box.conf[0]) >= PHONE_CONF_THRESHOLD:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w, h = x2 - x1, y2 - y1
            # Reject flat wide boxes — Zoom name labels, banners, UI overlays
            if h > 0 and (w / h) > 3.0:
                continue
            raw.append({'conf': float(box.conf[0]), 'bbox': (x1, y1, x2, y2)})

    phones          = _deduplicate(raw)
    phone_detected  = len(phones) > 0
    phone_conf      = phones[0]['conf'] if phones else 0.0

    # ── Face detection ────────────────────────────────────────────────────────
    face_visible = False
    try:
        detector  = _load_face_detector()
        rgb       = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        face_r    = detector.detect(mp_image)
        face_visible = len(face_r.detections) > 0
    except Exception as e:
        print(f'[VISION] Face detection error: {e}', flush=True)

    return VisionResult(
        camera_on=True,
        face_visible=face_visible,
        phone_detected=phone_detected,
        phone_confidence=phone_conf,
        mean_brightness=mean_brightness,
    )
