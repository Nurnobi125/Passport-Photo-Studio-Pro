from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np

def mm_to_px(mm, dpi=300):
    return max(1, round(mm / 25.4 * dpi))

def resize_to_preset(img, width_mm, height_mm, dpi=300):
    return img.resize((mm_to_px(width_mm, dpi), mm_to_px(height_mm, dpi)), Image.Resampling.LANCZOS)

def center_crop(img, target_ratio):
    w, h = img.size
    ratio = w / h
    if ratio > target_ratio:
        new_w = round(h * target_ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    new_h = round(w / target_ratio)
    top = max(0, (h - new_h) // 3)
    return img.crop((0, top, w, top + new_h))

def _find_face_cascade():
    """Load the bundled Haar cascade reliably in source and PyInstaller builds."""
    import sys
    from pathlib import Path

    candidates = []

    # PyInstaller extracts bundled data under _MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(
            Path(meipass) / "assets" / "cascades" / "haarcascade_frontalface_default.xml"
        )

    # Normal source-tree execution.
    candidates.append(
        Path(__file__).resolve().parents[1]
        / "assets" / "cascades" / "haarcascade_frontalface_default.xml"
    )

    # Final fallback to OpenCV's installed data directory.
    try:
        candidates.append(
            Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        )
    except Exception:
        pass

    for path in candidates:
        try:
            if path.is_file():
                classifier = cv2.CascadeClassifier(str(path))
                if not classifier.empty():
                    return classifier
        except Exception:
            continue

    return None


def detect_face_crop(img, target_ratio):
    rgb = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    cascade = _find_face_cascade()
    # Never call detectMultiScale() on an empty classifier. If a packaged
    # build cannot load the cascade, safely fall back to a centered crop.
    if cascade is None:
        return center_crop(img, target_ratio)

    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.08, minNeighbors=5, minSize=(80, 80)
    )
    if len(faces) == 0:
        return center_crop(img, target_ratio)

    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])

    # Keep extra room around the head and shoulders.
    face_cx = x + w / 2
    face_top = max(0, y - int(h * 1.0))
    face_bottom = min(img.height, y + int(h * 3.1))
    desired_h = max(face_bottom - face_top, int(h * 4.0))
    desired_w = int(desired_h * target_ratio)

    cx = int(face_cx)
    left = cx - desired_w // 2
    top = int(y + h * 0.5 - desired_h * 0.38)

    left = max(0, min(left, img.width - desired_w))
    top = max(0, min(top, img.height - desired_h))

    if desired_w > img.width or desired_h > img.height:
        return center_crop(img, target_ratio)
    return img.crop((left, top, left + desired_w, top + desired_h))

def smart_crop_and_resize(img, width_mm, height_mm, dpi=300):
    ratio = width_mm / height_mm
    crop = detect_face_crop(img, ratio)
    return resize_to_preset(crop, width_mm, height_mm, dpi)

def enhance(img, brightness=1.03, contrast=1.05, color=1.04, sharpness=1.10, smoothing=0.10):
    arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)

    if smoothing > 0:
        smoothed = cv2.bilateralFilter(arr, 7, 45, 45)
        amount = max(0.0, min(float(smoothing), 1.0))
        arr = cv2.addWeighted(arr, 1.0 - amount, smoothed, amount, 0)

    blur = cv2.GaussianBlur(arr, (0, 0), 1.1)
    arr = cv2.addWeighted(arr, float(sharpness), blur, 1.0 - float(sharpness), 0)

    out = Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))
    out = ImageEnhance.Brightness(out).enhance(brightness)
    out = ImageEnhance.Contrast(out).enhance(contrast)
    out = ImageEnhance.Color(out).enhance(color)
    return out

def apply_adjustments(img, brightness, contrast, color, sharpness, smoothing):
    return enhance(img, brightness, contrast, color, sharpness, smoothing)


# ---------------------------------------------------------------------------
# Photoshop-style editing tools
# ---------------------------------------------------------------------------

def rotate_image(img, degrees, fill=(255, 255, 255)):
    """Rotate by an arbitrary angle (positive = clockwise), expanding the canvas."""
    return img.rotate(-degrees, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=fill)

def rotate_90(img, clockwise=True):
    return img.transpose(Image.Transpose.ROTATE_270 if clockwise else Image.Transpose.ROTATE_90)

def flip_horizontal(img):
    return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

def flip_vertical(img):
    return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

def adjust_temperature(img, value):
    """value in [-1, 1]: negative = cooler (blue), positive = warmer (orange)."""
    value = max(-1.0, min(1.0, float(value)))
    r, g, b = img.convert("RGB").split()
    shift = int(value * 35)
    if shift >= 0:
        r = r.point(lambda p: min(255, p + shift))
        b = b.point(lambda p: max(0, p - shift))
    else:
        r = r.point(lambda p: max(0, p + shift))
        b = b.point(lambda p: min(255, p - shift))
    return Image.merge("RGB", (r, g, b))

def denoise(img, strength=7):
    """Removes sensor noise / grain from low-light phone photos."""
    arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    den = cv2.fastNlMeansDenoisingColored(arr, None, strength, strength, 7, 21)
    return Image.fromarray(cv2.cvtColor(den, cv2.COLOR_BGR2RGB))

def auto_white_balance(img):
    """Simple percentile-based gray-world white balance / auto-levels correction."""
    arr = np.array(img.convert("RGB")).astype(np.float32)
    out = np.empty_like(arr)
    for c in range(3):
        channel = arr[:, :, c]
        lo, hi = np.percentile(channel, (0.5, 99.5))
        if hi <= lo:
            out[:, :, c] = channel
            continue
        out[:, :, c] = np.clip((channel - lo) * 255.0 / (hi - lo), 0, 255)
    return Image.fromarray(out.astype(np.uint8))

FILTER_PRESETS = ["Natural", "Studio Vivid", "Warm Tone", "Cool Tone", "Classic B&W", "Soft Portrait"]

def apply_filter_preset(img, name):
    """One-click professional-style looks, similar to Lightroom/Photoshop presets."""
    base = img.convert("RGB")
    if name == "Natural" or not name:
        return base
    if name == "Studio Vivid":
        out = ImageEnhance.Color(base).enhance(1.28)
        out = ImageEnhance.Contrast(out).enhance(1.12)
        return ImageEnhance.Sharpness(out).enhance(1.15)
    if name == "Warm Tone":
        return adjust_temperature(ImageEnhance.Color(base).enhance(1.08), 0.35)
    if name == "Cool Tone":
        return adjust_temperature(ImageEnhance.Color(base).enhance(1.02), -0.30)
    if name == "Classic B&W":
        gray = base.convert("L")
        out = ImageEnhance.Contrast(gray).enhance(1.15)
        return out.convert("RGB")
    if name == "Soft Portrait":
        arr = cv2.cvtColor(np.array(base), cv2.COLOR_RGB2BGR)
        smooth = cv2.bilateralFilter(arr, 9, 60, 60)
        blended = cv2.addWeighted(arr, 0.45, smooth, 0.55, 0)
        out = Image.fromarray(cv2.cvtColor(blended, cv2.COLOR_BGR2RGB))
        return ImageEnhance.Brightness(out).enhance(1.03)
    return base


# ---------------------------------------------------------------------------
# v3.0 professional photo tools
# ---------------------------------------------------------------------------

def adjust_exposure(img, value=0.0):
    """Exposure-style adjustment. value is approximately -2..+2 stops."""
    factor = 2.0 ** float(max(-2.0, min(2.0, value)))
    return ImageEnhance.Brightness(img.convert("RGB")).enhance(factor)

def adjust_saturation(img, value=1.0):
    """Saturation multiplier, 0..2."""
    return ImageEnhance.Color(img.convert("RGB")).enhance(max(0.0, min(2.0, float(value))))

def adjust_highlights_shadows(img, highlights=0.0, shadows=0.0):
    """Gentle tonal recovery for portrait photos."""
    arr = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    hi_mask = np.clip((lum - 0.55) / 0.45, 0, 1)[..., None]
    sh_mask = np.clip((0.45 - lum) / 0.45, 0, 1)[..., None]
    h = float(max(-1, min(1, highlights)))
    sh = float(max(-1, min(1, shadows)))
    arr = arr + hi_mask * (-h * 0.22) + sh_mask * (sh * 0.22)
    return Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8))

def vignette(img, amount=0.0):
    """Subtle portrait vignette, amount 0..1."""
    amount = max(0.0, min(1.0, float(amount)))
    base = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w = base.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    dx = (xx - w / 2) / max(1, w / 2)
    dy = (yy - h / 2) / max(1, h / 2)
    radius = np.sqrt(dx * dx + dy * dy)
    mask = np.clip((radius - 0.35) / 0.65, 0, 1)
    factor = 1.0 - mask * amount * 0.35
    base *= factor[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))

def sharpen_portrait(img, amount=1.25):
    """Controlled portrait sharpening."""
    return ImageEnhance.Sharpness(img.convert("RGB")).enhance(max(0.0, min(2.0, float(amount))))

def auto_enhance_portrait(img):
    """Balanced one-click enhancement for ID/passport portraits."""
    out = auto_white_balance(img)
    out = ImageEnhance.Contrast(out).enhance(1.06)
    out = ImageEnhance.Color(out).enhance(1.05)
    out = ImageEnhance.Brightness(out).enhance(1.02)
    return ImageEnhance.Sharpness(out).enhance(1.10)
