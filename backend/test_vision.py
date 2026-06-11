#!/usr/bin/env python3
"""
QaraQib Week 1 — Vision Model Test Script

Tests three things against a real Zoom class screenshot:
  1. Camera-off detection (black frame check)
  2. Phone detection — YOLOv8n (COCO class 67)
  3. Face detection  — MediaPipe (purpose-built for video call faces)
  4. Face detection  — YOLOv8n-face (comparison)

Usage:
    python test_vision.py path/to/screenshot.jpg
    python test_vision.py path/to/screenshot.jpg --threshold 0.4

Output:
    Prints confidence scores and detection counts.
    Saves annotated images: output_phone.jpg, output_face_mp.jpg, output_face_yolo.jpg
"""

import sys
import os
import time
import argparse
import numpy as np
import cv2

OUTPUT_DIR = 'Pic_output'

# ─── THRESHOLDS (tune these based on your test results) ──────────────────
PHONE_CONF = 0.15   # below this = ignore phone detection (reduce false positives)
FACE_CONF  = 0.50   # below this = ignore face detection
BLACK_MEAN = 15     # frame mean pixel value below this = camera is off
PHONE_CLASS = 67    # COCO dataset class 67 = 'cell phone'


# ─── BLACK FRAME CHECK ────────────────────────────────────────────────────

def check_camera_off(frame: np.ndarray) -> tuple[bool, float]:
    """
    Returns (is_off, mean_brightness).
    Brightness < BLACK_MEAN means camera is off or covered.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = float(np.mean(gray))
    return mean < BLACK_MEAN, round(mean, 2)


# ─── DEDUPLICATION ───────────────────────────────────────────────────────

def deduplicate_boxes(detections: list, containment_threshold: float = 0.72) -> list:
    """
    Remove duplicate detections caused by multi-scale YOLO detection.

    Standard IoU-based NMS misses the case where a small tight box (e.g. camera
    module) is mostly inside a large box (e.g. full phone + hand), because the
    IoU is low even though they're the same object.

    This adds a containment check: if the SMALLER box's area is >= 72% contained
    within the LARGER box, suppress the lower-confidence one.

    Sorted by confidence desc so the best detection is always kept first.
    """
    if len(detections) <= 1:
        return detections

    detections = sorted(detections, key=lambda d: d['conf'], reverse=True)
    kept = []

    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        area = (x2 - x1) * (y2 - y1)
        suppress = False

        for kept_det in kept:
            kx1, ky1, kx2, ky2 = kept_det['bbox']
            karea = (kx2 - kx1) * (ky2 - ky1)

            # Intersection
            ix1, iy1 = max(x1, kx1), max(y1, ky1)
            ix2, iy2 = min(x2, kx2), min(y2, ky2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)

            if inter == 0:
                continue

            # How much of the SMALLER box is inside the larger one?
            smaller_area = min(area, karea)
            containment = inter / smaller_area if smaller_area > 0 else 0

            if containment >= containment_threshold:
                suppress = True
                break

        if not suppress:
            kept.append(det)

    return kept


# ─── CONTRAST PREPROCESSING ──────────────────────────────────────────────

def enhance_contrast(frame: np.ndarray) -> np.ndarray:
    """
    CLAHE in LAB color space — boosts local contrast without blowing out colors.
    Helps YOLO find dark phones on dark backgrounds.
    Only the L (lightness) channel is modified; hue/saturation unchanged.
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab_enhanced = cv2.merge([clahe.apply(l), a, b])
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)


# ─── PHONE DETECTION — YOLOv8n ───────────────────────────────────────────

_phone_model = None

def _get_phone_model():
    global _phone_model
    if _phone_model is None:
        from ultralytics import YOLO
        print('  Loading yolov8n.pt ...')
        _phone_model = YOLO('yolov8n.pt')
        print('  Model loaded.')
    return _phone_model


def run_phone_detection(frame: np.ndarray, conf_threshold: float) -> dict:
    """
    Detects mobile phones using YOLOv8n trained on COCO.
    Model is cached after first load — subsequent calls are fast.
    yolov8n.pt auto-downloads ~6MB on first run.
    Runs YOLO on both raw and CLAHE-enhanced frame, merges results.
    """
    model    = _get_phone_model()
    enhanced = enhance_contrast(frame)

    def _detect(img, label):
        t0 = time.perf_counter()
        res = model(img, verbose=False)[0]
        ms = round((time.perf_counter() - t0) * 1000, 1)
        hits, below = [], []
        for box in res.boxes:
            if int(box.cls[0]) != PHONE_CLASS:
                continue
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            entry = {'conf': conf, 'bbox': (x1, y1, x2, y2)}
            if conf >= conf_threshold:
                hits.append(entry)
            else:
                below.append(entry)
        return hits, below, ms

    raw_hits,  raw_below,  ms_raw  = _detect(frame,    'raw')
    enh_hits,  enh_below,  ms_enh  = _detect(enhanced, 'CLAHE')

    print(f'    Raw frame    : {len(raw_hits)} accepted, {len(raw_below)} sub-threshold  ({ms_raw} ms)')
    print(f'    CLAHE frame  : {len(enh_hits)} accepted, {len(enh_below)} sub-threshold  ({ms_enh} ms)')

    # Report sub-threshold from whichever pass saw something
    for label, below in [('raw', raw_below), ('CLAHE', enh_below)]:
        if below:
            print(f'    Sub-threshold ({label}, conf < {conf_threshold}):')
            for d in sorted(below, key=lambda x: x['conf'], reverse=True):
                print(f'      conf={d["conf"]:.3f}  bbox={d["bbox"]}')
    if not raw_hits and not enh_hits and not raw_below and not enh_below:
        print(f'    No class-67 signal in either pass — YOLO sees no phone at all')

    # Merge accepted hits from both passes (prefer CLAHE result if overlapping)
    merged = deduplicate_boxes(enh_hits + raw_hits)
    ms     = ms_raw + ms_enh

    annotated = frame.copy()
    for p in merged:
        x1, y1, x2, y2 = p['bbox']
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(annotated, f'Phone {p["conf"]:.2f}', (x1, max(y1 - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

    for d in (enh_below + raw_below):
        x1, y1, x2, y2 = d['bbox']
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 140, 255), 1)
        cv2.putText(annotated, f'? {d["conf"]:.2f}', (x1, max(y1 - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 140, 255), 1)

    # Also save the CLAHE-enhanced frame so you can see what YOLO saw
    cv2.imwrite(os.path.join(OUTPUT_DIR, 'output_phone_clahe_input.jpg'), enhanced)

    suppressed = (len(enh_hits) + len(raw_hits)) - len(merged)
    if suppressed:
        print(f'    Duplicates removed : {suppressed} (multi-scale/cross-pass overlap)')

    return {'hits': merged, 'count': len(merged), 'ms': ms, 'frame': annotated}


# ─── FACE DETECTION — MediaPipe ──────────────────────────────────────────

def run_face_mediapipe(frame: np.ndarray, conf_threshold: float) -> dict:
    """
    Detects faces using MediaPipe Face Detection.
    Supports both mediapipe >= 0.10 (Tasks API) and < 0.10 (solutions API).
    Tasks API auto-downloads blaze_face_short_range.tflite (~1MB) on first run.
    """
    import mediapipe as mp
    import os, urllib.request

    h, w      = frame.shape[:2]
    faces     = []
    annotated = frame.copy()

    # ── New API: mediapipe >= 0.10 ────────────────────────────────────────
    try:
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision as mp_vision

        model_path = 'face_detector.tflite'
        if not os.path.exists(model_path):
            print('  Downloading face_detector.tflite (~800KB) ...')
            urllib.request.urlretrieve(
                'https://storage.googleapis.com/mediapipe-models/face_detector/'
                'blaze_face_short_range/float16/1/blaze_face_short_range.tflite',
                model_path
            )
            print('  Download complete.')

        options = mp_vision.FaceDetectorOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=model_path),
            min_detection_confidence=conf_threshold
        )

        t0 = time.perf_counter()
        with mp_vision.FaceDetector.create_from_options(options) as detector:
            mp_img = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            )
            result = detector.detect(mp_img)
        ms = round((time.perf_counter() - t0) * 1000, 1)

        for det in result.detections:
            conf_val = det.categories[0].score if det.categories else 0.0
            bb = det.bounding_box
            x1 = max(bb.origin_x, 0)
            y1 = max(bb.origin_y, 0)
            x2 = min(bb.origin_x + bb.width,  w)
            y2 = min(bb.origin_y + bb.height, h)
            faces.append({'conf': conf_val, 'bbox': (x1, y1, x2, y2)})
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
            cv2.putText(annotated, f'Face {conf_val:.2f}', (x1, max(y1 - 8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 0), 2)

        return {'hits': faces, 'count': len(faces), 'ms': ms, 'frame': annotated}

    except (ImportError, AttributeError):
        pass  # fall through to legacy API

    # ── Legacy API: mediapipe < 0.10 ──────────────────────────────────────
    mp_fd = mp.solutions.face_detection

    t0 = time.perf_counter()
    with mp_fd.FaceDetection(
        model_selection=0,
        min_detection_confidence=conf_threshold
    ) as detector:
        results = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    ms = round((time.perf_counter() - t0) * 1000, 1)

    if results.detections:
        for det in results.detections:
            conf_val = float(det.score[0])
            bb = det.location_data.relative_bounding_box
            x1 = max(int(bb.xmin * w), 0)
            y1 = max(int(bb.ymin * h), 0)
            x2 = min(int((bb.xmin + bb.width)  * w), w)
            y2 = min(int((bb.ymin + bb.height) * h), h)
            faces.append({'conf': conf_val, 'bbox': (x1, y1, x2, y2)})
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
            cv2.putText(annotated, f'Face {conf_val:.2f}', (x1, max(y1 - 8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 0), 2)

    return {'hits': faces, 'count': len(faces), 'ms': ms, 'frame': annotated}


# ─── FACE DETECTION — YOLOv8n-face ───────────────────────────────────────

def run_face_yolo(frame: np.ndarray, conf_threshold: float) -> dict:
    """
    Detects faces using YOLOv8n-face (community model, auto-downloads).
    If the model is not available, returns an error dict so the script
    continues without crashing.
    """
    from ultralytics import YOLO

    try:
        print('  Loading yolov8n-face.pt ...')
        model = YOLO('yolov8n-face.pt')
    except Exception as e:
        return {
            'hits': [], 'count': 0, 'ms': 0, 'frame': frame.copy(),
            'error': (
                'yolov8n-face.pt could not be loaded automatically.\n'
                '  Download it manually from: https://github.com/akanametov/yolov8-face/releases\n'
                f'  Original error: {e}'
            )
        }

    t0 = time.perf_counter()
    results = model(frame, verbose=False)[0]
    ms = round((time.perf_counter() - t0) * 1000, 1)

    faces     = []
    annotated = frame.copy()

    for box in results.boxes:
        conf = float(box.conf[0])
        if conf >= conf_threshold:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            faces.append({'conf': conf, 'bbox': (x1, y1, x2, y2)})
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 120, 0), 2)
            label = f'Face {conf:.2f}'
            cv2.putText(annotated, label, (x1, max(y1 - 8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 120, 0), 2)

    return {'hits': faces, 'count': len(faces), 'ms': ms, 'frame': annotated}


# ─── HELPERS ──────────────────────────────────────────────────────────────

def sep(char='─', n=62):
    print(char * n)

def verdict(label: str, detected: bool) -> str:
    return f'{"✓  YES" if detected else "✗  No "} — {label}'


# ─── MAIN ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='QaraQib Vision Model Validator')
    parser.add_argument('image', help='Path to a Zoom class screenshot (JPG/PNG)')
    parser.add_argument(
        '--phone-conf', type=float, default=PHONE_CONF,
        help=f'Phone detection confidence threshold (default: {PHONE_CONF})'
    )
    parser.add_argument(
        '--face-conf', type=float, default=FACE_CONF,
        help=f'Face detection confidence threshold (default: {FACE_CONF})'
    )
    args = parser.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        print(f'ERROR: Cannot load image: {args.image}')
        print('  Make sure the path is correct and the file is a valid JPG/PNG.')
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    h, w = frame.shape[:2]

    sep('═')
    print('  QaraQib — Vision Model Test')
    sep('═')
    print(f'  Image   : {args.image}')
    print(f'  Size    : {w} × {h} px')
    print(f'  Phone threshold : {args.phone_conf}')
    print(f'  Face threshold  : {args.face_conf}')
    sep()

    # ── 1. Camera off check ───────────────────────────────────────────────
    print('\n[1] Camera-Off Detection (black frame check)')
    is_off, brightness = check_camera_off(frame)
    print(f'    Mean brightness : {brightness}  (threshold: < {BLACK_MEAN})')
    print(f'    Camera status   : {"OFF — frame is black/blank" if is_off else "ON  — image has content"}')

    if is_off:
        sep()
        print('\n  Camera is off — skipping face and phone detection.')
        print('  This is the correct behaviour for the production pipeline.')
        sep()
        return

    # ── 2. Phone detection ────────────────────────────────────────────────
    print('\n[2] Phone Detection — YOLOv8n (COCO class 67)')
    phone = run_phone_detection(frame, args.phone_conf)
    print(f'    Phones found : {phone["count"]}')
    for i, h_ in enumerate(phone['hits'], 1):
        print(f'    #{i}  confidence={h_["conf"]:.3f}   bbox={h_["bbox"]}')
    print(f'    Inference    : {phone["ms"]} ms')
    phone_out = os.path.join(OUTPUT_DIR, 'output_phone.jpg')
    cv2.imwrite(phone_out, phone['frame'])
    print(f'    Saved        : {phone_out}')

    # ── 3. Face detection — MediaPipe ─────────────────────────────────────
    print('\n[3] Face Detection — MediaPipe')
    mp_r = run_face_mediapipe(frame, args.face_conf)
    print(f'    Faces found  : {mp_r["count"]}')
    for i, h_ in enumerate(mp_r['hits'], 1):
        print(f'    #{i}  confidence={h_["conf"]:.3f}   bbox={h_["bbox"]}')
    print(f'    Inference    : {mp_r["ms"]} ms')
    mp_out = os.path.join(OUTPUT_DIR, 'output_face_mp.jpg')
    cv2.imwrite(mp_out, mp_r['frame'])
    print(f'    Saved        : {mp_out}')

    # ── 4. Face detection — YOLOv8n-face ─────────────────────────────────
    print('\n[4] Face Detection — YOLOv8n-face')
    yf_r = run_face_yolo(frame, args.face_conf)
    if 'error' in yf_r:
        print(f'    SKIPPED: {yf_r["error"]}')
    else:
        print(f'    Faces found  : {yf_r["count"]}')
        for i, h_ in enumerate(yf_r['hits'], 1):
            print(f'    #{i}  confidence={h_["conf"]:.3f}   bbox={h_["bbox"]}')
        print(f'    Inference    : {yf_r["ms"]} ms')
        yf_out = os.path.join(OUTPUT_DIR, 'output_face_yolo.jpg')
        cv2.imwrite(yf_out, yf_r['frame'])
        print(f'    Saved        : {yf_out}')

    # ── Summary ───────────────────────────────────────────────────────────
    sep()
    print('\n  RESULTS SUMMARY')
    sep()
    print(f'  {verdict("Phone present", phone["count"] > 0)}')
    print(f'  {verdict("Face visible (MediaPipe)", mp_r["count"] > 0)}')
    if 'error' not in yf_r:
        print(f'  {verdict("Face visible (YOLO-face)", yf_r["count"] > 0)}')
    else:
        print('       —  Face (YOLO-face): not available')

    print()
    print('  Speed comparison (lower = faster):')
    print(f'    Phone (YOLO)       : {phone["ms"]:>6} ms')
    print(f'    Face (MediaPipe)   : {mp_r["ms"]:>6} ms')
    if 'error' not in yf_r:
        print(f'    Face (YOLO-face)   : {yf_r["ms"]:>6} ms')

    sep()
    print()
    print(f'  Open the output images in {OUTPUT_DIR}/ to inspect bounding boxes:')
    print(f'    output_phone.jpg        — red boxes   = phone detections')
    print(f'    output_face_mp.jpg      — green boxes = MediaPipe faces')
    if 'error' not in yf_r:
        print(f'    output_face_yolo.jpg    — orange boxes = YOLO-face detections')
    print()
    print('  NEXT STEP:')
    print('  Run this on 5-6 different screenshots covering these cases:')
    print('    • Teacher clearly visible (face detection accuracy)')
    print('    • Student with phone in hand (phone detection accuracy)')
    print('    • Student camera off / black tile (camera-off detection)')
    print('    • Low-light / small face tile (find the limits)')
    print('    • Multiple students in one screenshot (multi-face detection)')
    sep('═')


if __name__ == '__main__':
    main()
