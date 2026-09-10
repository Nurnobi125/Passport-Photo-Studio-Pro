from PIL import Image, ImageOps


def mm_to_px(mm, dpi=300):
    """Convert millimeters to pixels at target DPI."""
    return max(1, round((float(mm) / 25.4) * dpi))


def inches_to_px(inches, dpi=300):
    """Convert inches to pixels at target DPI."""
    return max(1, round(float(inches) * dpi))


def calculate_a4_layout(
    photo,
    dpi=300,
    margin_x_mm=3.5,
    margin_y_mm=15.0,
    gap_x_mm=5.1562,   # 0.203 inches = 5.1562 mm
    gap_y_mm=5.1562,   # 0.203 inches = 5.1562 mm
    border_mm=0.1,
    requested_cols=5,
):
    """Return validated A4 layout metrics with exact millimeter and inch conversions."""
    if requested_cols < 1:
        raise ValueError("Photos per line must be at least 1.")
    if min(margin_x_mm, margin_y_mm, gap_x_mm, gap_y_mm, border_mm) < 0:
        raise ValueError("Margins, gaps, and borders cannot be negative.")

    # Standard A4 size in mm (210 x 297 mm) converted to pixels
    a4 = (mm_to_px(210, dpi), mm_to_px(297, dpi))
    
    border_px = max(1, mm_to_px(border_mm, dpi))
    gap_x = mm_to_px(gap_x_mm, dpi)
    gap_y = mm_to_px(gap_y_mm, dpi)
    mx = mm_to_px(margin_x_mm, dpi)
    my = mm_to_px(margin_y_mm, dpi)

    # Expand base image with border
    bordered = ImageOps.expand(photo.convert("RGB"), border=border_px, fill=(160, 160, 160))
    bw, bh = bordered.size

    usable_w = a4[0] - (2 * mx)
    usable_h = a4[1] - (2 * my)

    # Calculate max possible columns
    natural_cols = max(1, int((usable_w + gap_x) // (bw + gap_x)))
    cols = int(requested_cols)

    if cols > natural_cols:
        gap_in = round(gap_x_mm / 25.4, 3)
        raise ValueError(
            f"{cols} photos per line do not fit on A4 with gap {gap_x_mm} mm ({gap_in} in). "
            f"Maximum allowed is {natural_cols} per line."
        )

    rows = max(1, int((usable_h + gap_y) // (bh + gap_y)))
    capacity = cols * rows
    required_width_px = cols * bw + (cols - 1) * gap_x
    required_height_px = rows * bh + (rows - 1) * gap_y

    return {
        "a4_size": a4,
        "photo_size": (bw, bh),
        "margin_px": (mx, my),
        "gap_px": (gap_x, gap_y),
        "columns": cols,
        "rows": rows,
        "capacity": capacity,
        "natural_columns": natural_cols,
        "required_width_px": required_width_px,
        "required_height_px": required_height_px,
        "usable_size": (usable_w, usable_h),
    }


def make_a4_sheet(
    photo,
    quantity,
    dpi=300,
    margin_x_mm=3.5,
    margin_y_mm=15.0,
    gap_x_mm=5.1562,   # 0.203 inches = 5.1562 mm
    gap_y_mm=5.1562,   # 0.203 inches = 5.1562 mm
    border_mm=0.1,
    border_color=(160, 160, 160),
    requested_cols=5,
    center_last_row=False,  # Left-to-right alignment matching Photoshop
):
    """Generate the full A4 canvas with exact spacing between images."""
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")

    layout = calculate_a4_layout(
        photo=photo,
        dpi=dpi,
        margin_x_mm=margin_x_mm,
        margin_y_mm=margin_y_mm,
        gap_x_mm=gap_x_mm,
        gap_y_mm=gap_y_mm,
        border_mm=border_mm,
        requested_cols=requested_cols,
    )

    cols = layout["columns"]
    rows = layout["rows"]
    capacity = layout["capacity"]

    if quantity > capacity:
        raise ValueError(
            f"Quantity {quantity} does not fit on A4. "
            f"Maximum capacity is {capacity} ({cols} per line × {rows} rows)."
        )

    a4 = layout["a4_size"]
    mx, my = layout["margin_px"]
    gap_x, gap_y = layout["gap_px"]

    bordered = ImageOps.expand(
        photo.convert("RGB"),
        border=max(1, mm_to_px(border_mm, dpi)),
        fill=border_color,
    )
    bw, bh = bordered.size

    canvas = Image.new("RGB", a4, "white")

    for i in range(quantity):
        row, col = divmod(i, cols)
        items_in_row = min(cols, quantity - row * cols)

        if center_last_row and items_in_row < cols:
            row_width = items_in_row * bw + (items_in_row - 1) * gap_x
            start_x = (a4[0] - row_width) // 2
        else:
            start_x = mx

        # Standard grid positioning: Image 1, gap, Image 2, gap, Image 3...
        x = start_x + col * (bw + gap_x)
        y = my + row * (bh + gap_y)
        canvas.paste(bordered, (x, y))

    canvas.info["dpi"] = (dpi, dpi)
    return canvas, cols, rows, capacity