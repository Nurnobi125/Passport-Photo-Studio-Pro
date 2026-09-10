"""Local manual-crop learning engine.

The user draws a crop exactly like a Photoshop Crop Tool.  Training stores the
crop geometry *relative to the detected face* so the same composition can be
recreated on new photos with different resolutions/distances.  This is a
lightweight geometry learner, not identity recognition or model fine-tuning.
"""
from __future__ import annotations
import json
from pathlib import Path
from statistics import median
from PIL import Image
from .advanced_detection import detect_advanced

DEFAULT_PROFILE = {
    "version": 3,
    "name": "Manual Crop Bot",
    "examples": 0,
    "source": "photoshop-manual-crop-template",
    "identity_learning": False,
    "apply_mode": "face-anchored-template",
    "top_from_face": -0.25,
    "left_from_face": -1.0,
    "width_from_face": 3.0,
    "height_from_face": 4.1,
    "face_center_x": 0.5,
    "face_center_y": 0.30,
    "target_ratio": 38/48,
}


def _features(rect, face):
    l, t, r, b = map(float, rect)
    x, y, w, h = map(float, face)
    w = max(1.0, w); h = max(1.0, h)
    cw = max(1.0, r-l); ch = max(1.0, b-t)
    # Exact crop rectangle expressed in face-relative units.
    return {
        "top_from_face": (t-y)/h,
        "left_from_face": (l-x)/w,
        "width_from_face": cw/w,
        "height_from_face": ch/h,
        "face_center_x": (x+w/2-l)/cw,
        "face_center_y": (y+h/2-t)/ch,
        "face_ratio": h/ch,
        "top_ratio": max(0.0,(y-t)/ch),
        "center_ratio": (x+w/2-l)/cw,
        "bottom_face_multiplier": max(0.5,(b-y)/h),
    }


def make_example(image_path, crop_rect, name="example"):
    img = Image.open(image_path).convert("RGB")
    det = detect_advanced(img, use_hog=False)
    if not det.face:
        raise ValueError("No face detected in this training image.")
    return {
        "name": name,
        "image": str(image_path),
        "crop": list(map(int, crop_rect)),
        "face": list(det.face),
        "features": _features(crop_rect, det.face),
        "manual": True,
        "learner_version": 3,
    }


def learn_profile(examples, name="My Manual Crop Bot"):
    if not examples:
        raise ValueError("No training examples.")
    p = dict(DEFAULT_PROFILE)
    p["name"] = name
    p["examples"] = len(examples)
    keys = ("top_from_face", "left_from_face", "width_from_face", "height_from_face",
            "face_center_x", "face_center_y", "face_ratio", "top_ratio",
            "center_ratio", "bottom_face_multiplier")
    for k in keys:
        vals = [float(e["features"][k]) for e in examples if "features" in e and k in e["features"]]
        if vals:
            p[k] = float(median(vals))
    # The latest manual example is the strongest explicit template when only one
    # example is supplied. With many examples, median is robust to outliers.
    p["template_example"] = examples[-1]
    p["examples_data"] = examples[-100:]
    return p


def save_profile(path, profile):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def load_profile(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fit_ratio(left, top, width, height, ratio, iw, ih, anchor_x, anchor_y):
    """Fit a proposed crop to target aspect ratio while preserving its anchor."""
    width = max(2.0, float(width)); height = max(2.0, float(height))
    # Prefer the trained center and top. Increase/shrink around center to match ratio.
    width = height * ratio
    left = anchor_x - width/2
    top = anchor_y - height*0.30
    if left < 0: left = 0
    if top < 0: top = 0
    if left + width > iw: left = max(0, iw-width)
    if top + height > ih: top = max(0, ih-height)
    if width > iw:
        width = iw * .98; height = width/ratio
        left = max(0, min(iw-width, anchor_x-width/2))
    if height > ih:
        height = ih * .98; width = height*ratio
        left = max(0, min(iw-width, anchor_x-width/2))
    top = max(0, min(ih-height, top))
    return (int(round(left)), int(round(top)),
            int(round(left+width)), int(round(top+height)))


def apply_profile_to_geometry(face, iw, ih, ratio, profile):
    x, y, w, h = map(float, face)
    w = max(1.0,w); h = max(1.0,h)
    # v3 face-anchored template: reconstruct the user's manual crop from the
    # same normalized geometry. This is considerably more stable than using
    # only face-height percentage.
    left_rel = float(profile.get("left_from_face", -1.0))
    top_rel = float(profile.get("top_from_face", -0.25))
    width_rel = float(profile.get("width_from_face", 3.0))
    height_rel = float(profile.get("height_from_face", 4.1))
    cx_rel = float(profile.get("face_center_x", .5))
    cy_rel = float(profile.get("face_center_y", .30))

    trained_w = max(0.5, width_rel) * w
    trained_h = max(0.5, height_rel) * h
    # Keep the trained face position inside the crop, but use target ratio.
    face_cx = x + w/2
    anchor_x = face_cx + (0.5-cx_rel) * trained_w
    anchor_y = y + h/2 + (0.30-cy_rel) * trained_h
    top = y + top_rel*h
    left = x + left_rel*w

    # Scale the crop so its top edge remains close to the learned top margin.
    height = max(trained_h, 2.0)
    width = height * ratio
    # If the user's learned width is more restrictive, preserve the average scale.
    if trained_w > 2:
        width = max(width, trained_w)
        height = width / ratio
    # Re-anchor using the trained face-center location.
    left = anchor_x - width*cx_rel
    top = y + top_rel*h
    if top < 0: top = 0
    if top + height > ih: top = max(0, ih-height)
    if left < 0: left = 0
    if left + width > iw: left = max(0, iw-width)

    # Exact ratio and safe bounds.
    width = min(width, iw*.98)
    height = width/ratio
    if height > ih*.98:
        height = ih*.98; width = height*ratio
    left = max(0, min(iw-width, left))
    top = max(0, min(ih-height, top))
    return (int(round(left)), int(round(top)), int(round(left+width)), int(round(top+height)))
