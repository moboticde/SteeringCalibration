"""
Robust hole center detection in an ROI using:
1) Morphology Black-Hat + Otsu to segment dark circular holes under uneven lighting
2) Shape filtering (area, circularity, roundness)
3) Optional HoughCircles fallback to recover misses

Only points with x in [X1, X2] (and optional y in [Y1, Y2]) are reported.

Tune the PARAMS section to your image scale.  Works with the photo you shared.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple

# ------------------- PARAMS -------------------
IMAGE_PATH = r'C:\\Users\\DaniilYegarmin\\OneDrive - Mobotic GmbH\\Desktop\\Photos\\WIN_20250804_12_29_34_Pro.jpg'

# ROI limits (x from 500 to 1500; full height by default)
X1, X2 = 500, 1500
Y1, Y2 = None, None  # set integers to restrict vertical range

# Segmentation / shape filters
MIN_AREA = 40          # minimal blob area (px)
MAX_AREA = 10000       # maximal blob area (px) — keep wide
CIRC_MIN = 0.60        # circularity threshold (≈1 for perfect circle)
ROUND_RANGE = (0.65, 1.35)  # area / (pi*r^2)
R_MIN, R_MAX = 5, 50   # min/max radius (px) for minEnclosingCircle

# Morphology & thresholding
KERNEL_SIZE = 9        # for black-hat (odd, try 7/9/11)
GAUSS_BLUR = 5         # Gaussian blur ksize for smoothing before Otsu

# Hough fallback (set USE_HOUGH=False to disable)
USE_HOUGH = True
HOUGH_DP = 1.2
HOUGH_MIN_DIST = 26
HOUGH_PARAM1 = 120
HOUGH_PARAM2 = 16      # lower → more sensitive, more false positives
HOUGH_RMIN = 5
HOUGH_RMAX = 52
# ------------------------------------------------


def _roi_bounds(h: int, w: int):
    y1 = 0 if Y1 is None else max(0, min(h-1, Y1))
    y2 = h if Y2 is None else max(0, min(h, Y2))
    x1 = max(0, min(w-1, X1))
    x2 = max(0, min(w, X2))
    return x1, x2, y1, y2


def _dedupe(points: List[Tuple[int,int,float]], min_dist: int = 18):
    out = []
    for x, y, r in points:
        keep = True
        for X, Y, R in out:
            if (x-X)**2 + (y-Y)**2 <= min_dist**2:
                keep = False
                break
        if keep:
            out.append((x, y, r))
    return out


def detect_holes(img_bgr: np.ndarray):
    """Return (centers_all, centers_roi, debug_images)"""
    h, w = img_bgr.shape[:2]
    x1, x2, y1, y2 = _roi_bounds(h, w)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Contrast equalization (CLAHE helps a lot on metal glare)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    g = clahe.apply(gray)

    # Black-hat to emphasize dark holes on brighter background
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (KERNEL_SIZE, KERNEL_SIZE))
    blackhat = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, kernel)

    # Smooth then Otsu threshold to binary mask
    bh_blur = cv2.GaussianBlur(blackhat, (GAUSS_BLUR, GAUSS_BLUR), 0)
    _, mask = cv2.threshold(bh_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Clean the mask (remove tiny noise, close small gaps)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
                            iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
                            iterations=1)

    # Contours on mask (filled blobs, not edges)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    centers = []
    keep_cnts = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < MIN_AREA or area > MAX_AREA:
            continue
        peri = cv2.arcLength(c, True)
        circularity = 4 * np.pi * area / (peri * peri + 1e-6)
        (cxcy, r) = cv2.minEnclosingCircle(c)
        r = float(r)
        if r < R_MIN or r > R_MAX:
            continue
        roundness = area / (np.pi * r * r + 1e-6)
        if circularity >= CIRC_MIN and (ROUND_RANGE[0] <= roundness <= ROUND_RANGE[1]):
            M = cv2.moments(c)
            if M['m00']:
                cx = int(M['m10']/M['m00'])
                cy = int(M['m01']/M['m00'])
                centers.append((cx, cy, r))
                keep_cnts.append(c)

    # Optional Hough fallback to recover misses
    if USE_HOUGH:
        g_med = cv2.medianBlur(g, 5)
        circles = cv2.HoughCircles(g_med, cv2.HOUGH_GRADIENT, dp=HOUGH_DP,
                                   minDist=HOUGH_MIN_DIST, param1=HOUGH_PARAM1,
                                   param2=HOUGH_PARAM2, minRadius=HOUGH_RMIN,
                                   maxRadius=HOUGH_RMAX)
        if circles is not None:
            for x, y, r in np.round(circles[0, :]).astype(int):
                if R_MIN <= r <= R_MAX:
                    centers.append((int(x), int(y), float(r)))

    centers = _dedupe(centers, min_dist=18)
    centers_roi = [(x, y, r) for (x, y, r) in centers if x1 <= x <= x2 and y1 <= y < y2]

    # Debug images
    dbg = {
        'gray': gray,
        'clahe': g,
        'blackhat': blackhat,
        'mask': mask
    }
    return centers, centers_roi, keep_cnts, dbg


if __name__ == '__main__':
    img = cv2.imread(IMAGE_PATH)
    if img is None:
        raise FileNotFoundError(IMAGE_PATH)

    H, W = img.shape[:2]
    x1, x2, y1, y2 = _roi_bounds(H, W)

    centers_all, centers_roi, hole_cnts, dbg = detect_holes(img)

    # Visualization
    vis = img.copy()
    # draw ROI guides
    cv2.line(vis, (x1, 0), (x1, H), (0, 255, 255), 3)
    cv2.line(vis, (x2, 0), (x2, H), (0, 255, 255), 3)
    # draw contour outlines (optional)
    cv2.drawContours(vis, hole_cnts, -1, (0, 255, 0), 2)
    # draw centers
    for x, y, r in centers_roi:
        cv2.circle(vis, (x, y), max(6, int(r)), (0, 255, 0), 2)
        cv2.circle(vis, (x, y), 5, (255, 0, 0), -1)

    # Edges for the left panel (just like your original view)
    blurred = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    plt.figure(figsize=(18, 6))
    plt.subplot(1, 2, 1)
    plt.title('Edges')
    plt.imshow(edges, cmap='gray')
    plt.axis('on')

    plt.subplot(1, 2, 2)
    plt.title('Contours / Hole Centers (ROI)')
    plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
    plt.legend(['Hole Centers (ROI)'], loc='upper right')
    plt.axis('on')
    plt.tight_layout()
    plt.show()

    print(f"Total centers: {len(centers_all)}; In ROI: {len(centers_roi)}")
    print([(x, y) for (x, y, r) in centers_roi])
