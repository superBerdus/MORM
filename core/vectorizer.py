"""
MORM - SVG Vectorizer Module
Extract pencil sketches and outlines as metric-scale SVG paths.
"""

import cv2
import numpy as np
from typing import Dict, Any, List


def extract_contours_to_svg(
    image: np.ndarray,
    metadata: Dict[str, Any],
    threshold_sensitivity: int = 128,
    min_contour_length_mm: float = 5.0
) -> str:
    """
    Extract pencil strokes from a rectified image and produce an SVG at the same millimeter scale.
    """
    width_mm = metadata.get("width_mm", 210.0)
    height_mm = metadata.get("height_mm", 297.0)
    ppm = metadata.get("pixels_per_mm", 10.0)

    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Increase contrast and apply light smoothing
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Threshold dark pencil strokes against the light background
    # Adaptive or Otsu thresholding
    _, thresh = cv2.threshold(blurred, threshold_sensitivity, 255, cv2.THRESH_BINARY_INV)

    # Remove small noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    # Find contours
    contours, hierarchy = cv2.findContours(
        cleaned,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_TC89_KCOS
    )

    svg_paths: List[str] = []
    min_points = int(min_contour_length_mm * ppm)

    for cnt in contours:
        # Ignore tiny dust and speckle contours
        if len(cnt) < 10 or cv2.arcLength(cnt, True) < min_points:
            continue

        # Convert contour coordinates to millimeters
        path_data = []
        for i, pt in enumerate(cnt):
            px, py = pt[0]
            mm_x = px / ppm
            mm_y = py / ppm
            cmd = "M" if i == 0 else "L"
            path_data.append(f"{cmd} {mm_x:.3f},{mm_y:.3f}")

        path_data.append("Z")
        svg_paths.append(" ".join(path_data))

    # SVG header with physical millimeter dimensions
    svg_header = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{width_mm:.2f}mm"
     height="{height_mm:.2f}mm"
     viewBox="0 0 {width_mm:.2f} {height_mm:.2f}">
    <title>MORM 1:1 Scaled Contours</title>
    <desc>Extracted outline contours (1:1 mm scale)</desc>
    <!-- Reference frame -->
    <rect x="0" y="0" width="{width_mm:.2f}" height="{height_mm:.2f}" 
          fill="none" stroke="#94a3b8" stroke-width="0.2" stroke-dasharray="2,2" />
    <g id="contours" fill="none" stroke="#2563eb" stroke-width="0.3" stroke-linecap="round" stroke-linejoin="round">
'''

    svg_body = "\n".join([f'        <path d="{p}" />' for p in svg_paths])
    svg_footer = "\n    </g>\n</svg>"

    return svg_header + svg_body + svg_footer
