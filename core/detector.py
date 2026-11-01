"""
MORM - Reference Detector Module
Automatically detect a reference sheet, card, or four-corner plane in an image.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from .rectifier import order_points


def auto_detect_paper_corners(image: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    """
    Automatically detect the most prominent four-corner document, sheet, or card boundary.

    Returns:
        [(x0,y0), (x1,y1), (x2,y2), (x3,y3)] ordered top-left, top-right, bottom-right, bottom-left,
        or None if no suitable boundary is detected.
    """
    h, w = image.shape[:2]
    img_area = h * w

    # Convert to grayscale and reduce noise
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Estimate dynamic thresholds for edge detection
    median_val = np.median(blurred)
    lower = int(max(0, 0.66 * median_val))
    upper = int(min(255, 1.33 * median_val))
    edges = cv2.Canny(blurred, lower, upper)

    # Dilate edges to connect nearby segments
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    # Sort contours by descending area
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for cnt in contours[:10]:
        area = cv2.contourArea(cnt)
        # Require at least 5% of the image area
        if area < img_area * 0.05:
            continue

        perimeter = cv2.arcLength(cnt, True)
        # Approximate polygons at several tolerances
        for eps_factor in [0.02, 0.03, 0.04, 0.05]:
            approx = cv2.approxPolyDP(cnt, eps_factor * perimeter, True)

            # Is this a convex quadrilateral?
            if len(approx) == 4 and cv2.isContourConvex(approx):
                pts = approx.reshape(4, 2)
                ordered = order_points(pts)
                return [(float(pt[0]), float(pt[1])) for pt in ordered]

    # Do not present an arbitrary inset rectangle as a successful detection.
    return None


def detect_aruco_markers(image: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detect ArUco fiducial markers, if present.
    """
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        corners, ids, rejected = detector.detectMarkers(gray)

        results = []
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                pts = corners[i].reshape(4, 2)
                results.append({
                    "id": int(marker_id),
                    "corners": [(float(p[0]), float(p[1])) for p in pts]
                })
        return results
    except Exception:
        return []
