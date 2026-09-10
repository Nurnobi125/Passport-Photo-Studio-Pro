from PIL import Image
from pathlib import Path

def save_image(image, path, dpi=300, quality=95):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        image.convert("RGB").save(path, quality=quality, subsampling=0, dpi=(dpi, dpi))
    elif ext == ".png":
        image.save(path, dpi=(dpi, dpi), compress_level=1)
    else:
        raise ValueError("Use .jpg, .jpeg or .png")
