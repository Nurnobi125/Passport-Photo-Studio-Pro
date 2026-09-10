from PIL import Image


def composite_on_color(rgba, color):
    """Composite a cutout onto an exact RGB background color.

    Uses the alpha channel directly and returns RGB, so the selected color is
    applied uniformly without leaving transparent/old-background pixels.
    """
    rgba = rgba.convert("RGBA")
    rgb_color = tuple(max(0, min(255, int(v))) for v in color[:3])
    bg = Image.new("RGBA", rgba.size, rgb_color + (255,))
    return Image.alpha_composite(bg, rgba).convert("RGB")
