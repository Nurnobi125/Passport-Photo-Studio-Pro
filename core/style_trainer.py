"""Local PDF instruction -> photo style profile helper.

This is an instruction/rule trainer, not model fine-tuning. It extracts text from a
user-supplied PDF and turns common photo-editing instructions into a reusable style
profile that can be applied to future photos.
"""
import json
import re
from pathlib import Path

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

DEFAULT_PROFILE = {
    "name": "My Style",
    "background": None,
    "brightness": None,
    "contrast": None,
    "color": None,
    "sharpness": None,
    "smooth_skin": None,
    "exposure": None,
    "saturation": None,
    "highlights": None,
    "shadows": None,
    "vignette": None,
    "preset_mm": None,
    "notes": "",
}


def extract_pdf_text(path):
    if PdfReader is None:
        raise RuntimeError("PDF support is not installed. Install pypdf first.")
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def _num(text, key):
    m = re.search(rf"{key}[^\\d+-]*([+-]?\\d+(?:[.,]\\d+)?)", text, re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_instructions(text, name="My Style"):
    t = " ".join(text.lower().split())
    p = dict(DEFAULT_PROFILE)
    p["name"] = name
    p["notes"] = text[:3000]

    colors = {
        "white": (255, 255, 255), "off-white": (248, 248, 245),
        "light blue": (173, 216, 230), "blue": (67, 142, 219),
        "gray": (210, 210, 210), "grey": (210, 210, 210),
        "light gray": (235, 235, 235), "red": (220, 40, 40),
    }
    for word, rgb in colors.items():
        if word in t and any(k in t for k in ("background", "backdrop", "bg")):
            p["background"] = rgb
            break

    for key in ("brightness", "contrast", "color", "sharpness", "smooth skin", "exposure", "saturation", "highlights", "shadows", "vignette"):
        val = _num(t, re.escape(key))
        if val is not None:
            p[key.replace(" ", "_")] = val

    # Friendly percentage forms, e.g. "brightness +5%".
    for key in ("brightness", "contrast", "saturation", "sharpness", "smooth skin"):
        m = re.search(rf"{re.escape(key)}[^\\d+-]*([+-]?\\d+(?:[.,]\\d+)?)\\s*%", t, re.I)
        if m:
            v = float(m.group(1).replace(",", "."))
            # UI sliders use multiplicative values for most quick retouching controls.
            if key in ("brightness", "contrast", "saturation", "sharpness"):
                p[key.replace(" ", "_")] = 1.0 + v / 100.0
            else:
                p[key.replace(" ", "_")] = max(0.0, min(0.5, v / 100.0))

    # Common crop dimensions: 35x45 mm, 2x2 inch, etc.
    m = re.search(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm", t, re.I)
    if m:
        p["preset_mm"] = [float(m.group(1)), float(m.group(2))]
    elif re.search(r"2\s*[x×]\s*2\s*(?:inch|in)", t, re.I):
        p["preset_mm"] = [50.8, 50.8]

    # Semantic instructions when no numeric value is supplied.
    if "auto enhance" in t or "natural enhance" in t:
        p["auto_enhance"] = True
    if "white balance" in t or "auto color" in t:
        p["auto_white_balance"] = True
    if "denoise" in t or "noise reduction" in t:
        p["denoise"] = True
    return p


def save_profile(path, profile):
    Path(path).write_text(json.dumps(profile, indent=2), encoding="utf-8")


def load_profile(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
