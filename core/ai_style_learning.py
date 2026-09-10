"""Local example-based photo style learning.

Learns a compact style profile from 5-20 example photos using image statistics.
No cloud service or model download is required. This is intentionally conservative:
it learns color/exposure/contrast/sharpness/background/crop characteristics rather
than identity or facial features.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageStat, ImageFilter, ImageEnhance


def _stats(path):
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mean = arr.mean(axis=(0, 1))
    std = arr.std(axis=(0, 1))
    gray = arr.mean(axis=2)
    # Approximate perceived contrast and detail.
    contrast = float(gray.std())
    edge = np.abs(np.diff(gray, axis=1)).mean() + np.abs(np.diff(gray, axis=0)).mean()
    # Estimate corner background color (robust average of 4 corner patches).
    s = max(8, min(img.width, img.height) // 12)
    corners = np.concatenate([
        arr[:s, :s].reshape(-1, 3), arr[:s, -s:].reshape(-1, 3),
        arr[-s:, :s].reshape(-1, 3), arr[-s:, -s:].reshape(-1, 3)
    ])
    bg = corners.mean(axis=0)
    return {
        "width": img.width, "height": img.height,
        "ratio": img.width / max(1, img.height),
        "mean_rgb": mean.tolist(), "std_rgb": std.tolist(),
        "contrast": contrast, "detail": float(edge), "bg_rgb": bg.tolist(),
    }


def learn_style(paths, name="AI Learned Style"):
    if not paths or len(paths) < 3:
        raise ValueError("Please select at least 3 example photos. 5-20 examples are recommended.")
    if len(paths) > 20:
        paths = paths[:20]
    rows = [_stats(p) for p in paths]
    avg = lambda k: float(np.mean([r[k] for r in rows]))
    rgb = np.mean([r["mean_rgb"] for r in rows], axis=0)
    bg = np.mean([r["bg_rgb"] for r in rows], axis=0)
    profile = {
        "name": name,
        "trainer": "example-statistics-v1",
        "examples": len(rows),
        "target_ratio": avg("ratio"),
        "target_mean_rgb": rgb.tolist(),
        "target_contrast": avg("contrast"),
        "target_detail": avg("detail"),
        "background_rgb": [int(round(x * 255)) for x in bg],
        "source_files": [str(p) for p in paths],
        "notes": "Learned locally from example images. Does not learn identity or facial features.",
    }
    return profile


def save_learned_style(path, profile):
    Path(path).write_text(json.dumps(profile, indent=2), encoding="utf-8")


def load_learned_style(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_learned_style(img, profile):
    """Adaptively match global style characteristics of learned examples."""
    base = img.convert("RGB")
    arr = np.asarray(base, dtype=np.float32) / 255.0
    cur_mean = arr.mean(axis=(0, 1))
    cur_contrast = float(arr.mean(axis=2).std())
    target_mean = np.asarray(profile.get("target_mean_rgb", cur_mean), dtype=np.float32)
    target_contrast = float(profile.get("target_contrast", cur_contrast))

    # Gentle color/exposure matching, clamped to avoid unnatural results.
    scale = np.clip(target_mean / np.maximum(cur_mean, 1e-4), 0.82, 1.18)
    arr = np.clip(arr * scale.reshape(1, 1, 3), 0, 1)
    gray = arr.mean(axis=2, keepdims=True)
    current = float(gray.std())
    if current > 1e-5:
        factor = float(np.clip(target_contrast / current, 0.85, 1.18))
        arr = np.clip((arr - 0.5) * factor + 0.5, 0, 1)

    out = Image.fromarray((arr * 255).astype(np.uint8), "RGB")
    # Detail matching is intentionally subtle.
    cur_detail = float(np.abs(np.diff(arr.mean(axis=2), axis=1)).mean() + np.abs(np.diff(arr.mean(axis=2), axis=0)).mean())
    target_detail = float(profile.get("target_detail", cur_detail))
    if cur_detail > 1e-5:
        sharp = float(np.clip(target_detail / cur_detail, 0.92, 1.12))
        out = ImageEnhance.Sharpness(out).enhance(sharp)
    return out
