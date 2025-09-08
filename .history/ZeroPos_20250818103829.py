"""
Hole center detector with FEWER false positives
------------------------------------------------
Strategy:
1) Find the main disk center using HoughCircles (large radii).
2) Segment dark circular blobs via Black-Hat + Otsu, then contour shape filters.
3) Keep only blobs that are:
   - inside the x∈[X1,X2] ROI (and optional y-range),
   - sufficiently circular and within a radius range,
   - darker than their immediate neighborhood (local contrast test),
   - close to a single bolt circle: distance to disk center within a tight radial band
     around the median radius of candidates (annulus constraint).

Tune the PARAMS section to your image scale.
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

# Candidate size/shape filters
MIN_AREA = 50           # px
MAX_AREA = 8000         # px
R_MIN, R_MAX = 6, 40    # min/max radius (px) of minEnclosingCircle for a hole
CIRC_MIN = 0.65         # 1.0 = perfect circle
ROUND_RANGE = (0.70, 1.30)  # area/(pi*r^2)

# Morphology / thresholding
KERNEL_SIZE = 9         # Black-hat kernel (odd). Try 7/9/11
BLUR = 5                # GaussianBlur ksize for Otsu pre-smoothing

# Local intensity contrast test
# mean(gray inside 0.6*r) must be darker than mean in ring [1.2*r, 1.7*r]
CONTRAST_MIN = 12       # minimum difference (ring - inner) in gray levels (0..255)

# Annulus constraint (distance to disk center around median radius)
ANNULUS_TOL = 28        # tolerance (px) around median bolt radius

# Hough for finding disk center (large radii)
HOUGH_DP = 1.2
HOUGH_PARAM1 = 120
HOUGH_PARAM2 = 50
DISK_RMIN_FRAC = 0.35   # minRadius ≈ this * min(H, W)
DISK_RMAX_FRAC = 0.55   # maxRadius ≈ this * min(H, W)
# ------------------------------------------------


def _roi_bounds(h: int, w: int):
    y1 = 0 if Y1 is None else max(0, min(h-1, Y1))
    y2 = h if Y2 is None else max(0, min(h, Y2))
    x1 = max(0, min(w-1, X1))
    x2 = max(0, min(w, X2))
    return x1, x2, y1, y2


def _dedupe(points: List[Tuple[int, int, float]], min_dist: int = 18):
    out: List[Tuple[int, int, float]] = []
    for x, y, r in points:
        ok = True
        for X, Y, R in out:
            if (x - X) ** 2 + (y - Y) ** 2 <= min_dist ** 2:
                ok = False
                break
        if ok:
            out.append((x, y, r))
    return out


def find_disk_center(gray: np.ndarray):
    h, w = gray.shape
    minR = int(min(h, w) * DISK_RMIN_FRAC)
    maxR = int(min(h, w) * DISK_RMAX_FRAC)
    g = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(g, 60, 160)
    circles = cv2.HoughCircles(edges, cv2.HOUGH_GRADIENT, dp=HOUGH_DP,
                               minDist=min(h, w) // 2,
                               param1=HOUGH_PARAM1, param2=HOUGH_PARAM2,
                               minRadius=minR, maxRadius=maxR)
    if circles is None:
        # fallback to image center
        return (w // 2, h // 2), int(0.45 * min(h, w)), False
    # choose the largest circle near image center
    cands = np.round(circles[0]).astype(int)
    cx, cy, r = max(cands, key=lambda c: c[2])
    return (int(cx), int(cy)), int(r), True


def local_contrast(gray: np.ndarray, cx: int, cy: int, r: float,
                   inner_ratio: float = 0.6, ring_in: float = 1.2, ring_out: float = 1.7):
    h, w = gray.shape
    Y, X = np.ogrid[:h, :w]
    dist2 = (X - cx) ** 2 + (Y - cy) ** 2
    r_in = (inner_ratio * r) ** 2
    r1 = (ring_in * r) ** 2
    r2 = (ring_out * r) ** 2

    inner_mask = dist2 <= r_in
    ring_mask = (dist2 >= r1) & (dist2 <= r2)

    if not np.any(inner_mask) or not np.any(ring_mask):
        return 0.0
    inner_mean = float(gray[inner_mask].mean())
    ring_mean = float(gray[ring_mask].mean())
    return ring_mean - inner_mean


def detect_holes(img_bgr: np.ndarray):
    h, w = img_bgr.shape[:2]
    x1, x2, y1, y2 = _roi_bounds(h, w)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # equalize for specular reflections
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    ge = clahe.apply(gray)

    # main disk center
    (cx_disk, cy_disk), r_disk, confident = find_disk_center(ge)

    # Black-hat → Otsu segmentation (dark blobs)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (KERNEL_SIZE, KERNEL_SIZE))
    bh = cv2.morphologyEx(ge, cv2.MORPH_BLACKHAT, kernel)
    bh = cv2.GaussianBlur(bh, (BLUR, BLUR), 0)
    _, mask = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), 1)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    prelim: List[Tuple[int, int, float]] = []
    kept_cnts = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < MIN_AREA or area > MAX_AREA:
            continue
        peri = cv2.arcLength(c, True)
        circularity = 4 * np.pi * area / (peri * peri + 1e-6)
        (xy, r) = cv2.minEnclosingCircle(c)
        r = float(r)
        if r < R_MIN or r > R_MAX:
            continue
        roundness = area / (np.pi * r * r + 1e-6)
        if circularity < CIRC_MIN or not (ROUND_RANGE[0] <= roundness <= ROUND_RANGE[1]):
            continue
        M = cv2.moments(c)
        if not M['m00']:
            continue
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])
        if not (x1 <= cx <= x2 and y1 <= cy < y2):
            continue
        # Local contrast test (holes should be darker than surroundings)
        contrast = local_contrast(ge, cx, cy, r)
        if contrast < CONTRAST_MIN:
            continue
        prelim.append((cx, cy, r))
        kept_cnts.append(c)

    # Annulus radius filter: use median of candidate radii from disk center
    if prelim:
        rho = np.array([np.hypot(cx - cx_disk, cy - cy_disk) for cx, cy, _ in prelim])
        r_med = float(np.median(rho))
        finals = [(cx, cy, r) for (cx, cy, r), rr in zip(prelim, rho) if abs(rr - r_med) <= ANNULUS_TOL]
    else:
        finals = []

    finals = _dedupe(finals, min_dist=18)

    dbg = {
        'gray': gray,
        'clahe': ge,
        'blackhat': bh,
        'mask': mask,
        'disk_center': (cx_disk, cy_disk),
        'disk_radius': r_disk,
    }
    return prelim, finals, kept_cnts, dbg


if __name__ == '__main__':
    img = cv2.imread(IMAGE_PATH)
    assert img is not None, f'Image not found: {IMAGE_PATH}'
    h, w = img.shape[:2]
    x1, x2, y1, y2 = _roi_bounds(h, w)

    prelim, finals, kept_cnts, dbg = detect_holes(img)

    vis = img.copy()
    # draw ROI and disk center
    cv2.line(vis, (x1, 0), (x1, h), (0, 255, 255), 3)
    cv2.line(vis, (x2, 0), (x2, h), (0, 255, 255), 3)
    cx_d, cy_d = dbg['disk_center']
    cv2.circle(vis, (int(cx_d), int(cy_d)), 6, (255, 0, 255), -1)

    # optional: draw prelim contours and all centers (light green) then finals (blue)
    cv2.drawContours(vis, kept_cnts, -1, (0, 180, 0), 2)
    for x, y, r in prelim:
        cv2.circle(vis, (x, y), max(6, int(r)), (120, 255, 120), 2)
    for x, y, r in finals:
        cv2.circle(vis, (x, y), max(6, int(r)), (0, 255, 0), 2)
        cv2.circle(vis, (x, y), 5, (30, 144, 255), -1)

    # Left panel: edges (for reference)
    edges = cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0), 50, 150)

    plt.figure(figsize=(18, 6))
    plt.subplot(1, 2, 1)
    plt.title('Edges')
    plt.imshow(edges, cmap='gray')
    plt.axis('on')

    plt.subplot(1, 2, 2)
    plt.title('Filtered hole centers (annulus + contrast)')
    plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
    plt.axis('on')
    plt.tight_layout()
    plt.show()

    print(f"Candidates before annulus filter: {len(prelim)} | Final holes in ROI: {len(finals)}")
    print([(x, y) for (x, y, r) in finals])
