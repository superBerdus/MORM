"""
MORM - Planar Image Rectifier
Planar homography and metric-scale perspective rectifier
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Any, Optional


MAX_OUTPUT_PIXELS = 32_000_000


def validate_quad(pts):
    points = np.asarray(pts, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Exactly four valid corner coordinates are required.")
    if len(np.unique(points, axis=0)) != 4:
        raise ValueError("All four corners must be distinct.")
    if not cv2.isContourConvex(points.reshape(-1, 1, 2)) or abs(cv2.contourArea(points)) < 25:
        raise ValueError("Corners must follow the perimeter order and form a non-degenerate, non-self-intersecting quadrilateral.")
    return points


def order_points(pts: np.ndarray) -> np.ndarray:
    """Detector-only ordering; centroid sorting avoids duplicate diamond corners.
    The UI must still assign P1-P4 to the intended physical width/height edges.
    """
    points = np.asarray(pts, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Exactly four valid corners are required.")
    center = points.mean(axis=0)
    ring = points[np.argsort(np.arctan2(points[:, 1]-center[1], points[:, 0]-center[0]))]
    # At a diagonal tie, prefer the upper point; never select the same point twice.
    start = min(range(4), key=lambda i: (float(ring[i].sum()), float(ring[i,1])))
    return validate_quad(np.roll(ring, -start, axis=0))


def validate_output_size(w, h):
    if w < 2 or h < 2 or max(w, h) > 16000 or w*h > MAX_OUTPUT_PIXELS:
        raise ValueError("Output size exceeds the limit (32 megapixels / 16,000 pixels per edge). Reduce the sampling density.")


def rectify_planar_image(
    image: np.ndarray,
    corners: List[Tuple[float, float]],
    target_width_mm: float,
    target_height_mm: float,
    pixels_per_mm: float = 10.0,
    margin_mm: float = 0.0
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Rectify an image to a top-down orthographic view using four corners
    and the reference rectangle dimensions in millimeters.

    Args:
        image: Input image (BGR NumPy array)
        corners: Four points [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
        target_width_mm: Physical width of the reference plane (mm)
        target_height_mm: Physical height of the reference plane (mm)
        pixels_per_mm: Output pixels per mm (default: 10 px/mm; not an accuracy guarantee)
        margin_mm: Extra border outside the reference plane (mm)

    Returns:
        (warped_image, metadata)
    """
    # Preserve the user's explicit P1-P4 mapping instead of guessing orientation.
    src = validate_quad(corners)
    if not all(np.isfinite(v) and v > 0 for v in (target_width_mm, target_height_mm, pixels_per_mm)):
        raise ValueError("Dimensions and sampling density must be positive.")
    if not np.isfinite(margin_mm) or margin_mm < 0:
        raise ValueError("Margin cannot be negative.")

    # Calculate output pixel dimensions
    total_w_mm = target_width_mm + (margin_mm * 2)
    total_h_mm = target_height_mm + (margin_mm * 2)

    target_w_px = int(round(total_w_mm * pixels_per_mm))
    target_h_px = int(round(total_h_mm * pixels_per_mm))

    validate_output_size(target_w_px, target_h_px)

    offset_x = margin_mm * pixels_per_mm
    offset_y = margin_mm * pixels_per_mm

    # Destination coordinates
    dst = np.array([
        [offset_x, offset_y],
        [offset_x + (target_width_mm * pixels_per_mm) - 1, offset_y],
        [offset_x + (target_width_mm * pixels_per_mm) - 1, offset_y + (target_height_mm * pixels_per_mm) - 1],
        [offset_x, offset_y + (target_height_mm * pixels_per_mm) - 1]
    ], dtype="float32")

    # Homography matrix
    M = cv2.getPerspectiveTransform(src, dst)

    # Rectify with high-quality Lanczos4 interpolation
    warped = cv2.warpPerspective(
        image,
        M,
        (target_w_px, target_h_px),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    metadata = {
        "width_mm": total_w_mm,
        "height_mm": total_h_mm,
        "width_px": target_w_px,
        "height_px": target_h_px,
        "pixels_per_mm": pixels_per_mm,
        "margin_mm": margin_mm,
        "aspect_ratio": total_w_mm / total_h_mm if total_h_mm > 0 else 1.0,
        "homography_matrix": M.tolist()
    }

    return warped, metadata


def rectify_with_ruler_scale(
    image: np.ndarray,
    plane_corners: List[Tuple[float, float]],
    ruler_pt1: Tuple[float, float],
    ruler_pt2: Tuple[float, float],
    ruler_length_mm: float,
    pixels_per_mm: float = 10.0
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Legacy entry point: apparent image edge lengths cannot supply metric aspect.

    Four arbitrary plane corners plus ONE distance do not determine the plane's
    Euclidean aspect ratio without extra camera/scene constraints. The older
    implementation guessed max(edge lengths) and could distort the other axis.
    Use a known rectangle with rectify_planar_image instead.
    """
    raise ValueError("A single ruler distance cannot determine an unknown aspect ratio. Use a rectangle with known dimensions.")


def scale_by_ruler_only(
    image: np.ndarray,
    ruler_pt1: Tuple[float, float],
    ruler_pt2: Tuple[float, float],
    ruler_length_mm: float,
    pixels_per_mm: float = 10.0
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Apply uniform scaling from two ruler points without correcting perspective.
    This provides metric scale only for nearly front-facing, planar images where
    lens distortion is negligible. One distance cannot metrically rectify both
    axes of an oblique photo.
    """
    if not np.isfinite(ruler_length_mm) or ruler_length_mm <= 0 or not np.isfinite(pixels_per_mm) or pixels_per_mm <= 0:
        raise ValueError("Ruler length and sampling density must be positive.")
    if not np.isfinite(np.array([ruler_pt1, ruler_pt2])).all():
        raise ValueError("Ruler coordinates are invalid.")
    p1 = np.array(ruler_pt1, dtype=np.float32)
    p2 = np.array(ruler_pt2, dtype=np.float32)
    measured_pixel_dist = float(np.linalg.norm(p2 - p1))

    if measured_pixel_dist <= 0:
        raise ValueError("The distance between ruler points cannot be zero.")

    # Current image pixels per millimeter
    raw_ppm = measured_pixel_dist / ruler_length_mm
    # Uniform scale factor needed to reach the requested sampling density
    scale_factor = pixels_per_mm / raw_ppm

    h, w = image.shape[:2]
    target_w_px = int(round(w * scale_factor))
    target_h_px = int(round(h * scale_factor))

    validate_output_size(target_w_px, target_h_px)

    # High-quality Lanczos4 resampling
    scaled_image = cv2.resize(
        image,
        (target_w_px, target_h_px),
        interpolation=cv2.INTER_LANCZOS4 if scale_factor >= 1.0 else cv2.INTER_AREA
    )

    metadata = {
        "width_mm": target_w_px / pixels_per_mm,
        "height_mm": target_h_px / pixels_per_mm,
        "width_px": target_w_px,
        "height_px": target_h_px,
        "pixels_per_mm": pixels_per_mm,
        "ruler_measured_px": measured_pixel_dist,
        "ruler_length_mm": ruler_length_mm,
        "scale_factor": scale_factor,
        "aspect_ratio": target_w_px / target_h_px if target_h_px > 0 else 1.0
    }

    return scaled_image, metadata
