import cv2
import numpy as np
import matplotlib.pyplot as plt

# ------------------- CONFIG -------------------
IMAGE_PATH = r'C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\WIN_20250804_12_29_34_Pro.jpg'

# ROI limits (x from 500 to 1500; full height by default)
X1, X2 = 500, 1500
Y1, Y2 = None, None  # set integers for y-limit (e.g., 200, 950)

# Hole size/shape filters (tune to image scale)
MIN_AREA = 12
R_MIN, R_MAX = 3, 120
CIRC_MIN = 0.60                # contour circularity threshold
ROUND_RANGE = (0.80, 1.35)     # area/(pi*r^2)
SOLIDITY_MIN = 0.90            # area/convexHullArea
RESIDUAL_MAX_FRAC = 0.10       # circle-fit RMS / radius
USE_HOUGH = False              # optional: fuse with HoughCircles
# ---------------------------------------------

def fit_circle_ls(contour):
    """Algebraic least-squares circle fit + residuals."""
    pts = contour.reshape(-1, 2).astype(np.float64)
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack((2 * x, 2 * y, np.ones_like(x)))
    b = x * x + y * y
    c, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy, c0 = c
    r = np.sqrt(c0 + cx * cx + cy * cy)
    rad = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    residual = rad - r
    rms = np.sqrt(np.mean(residual ** 2))
    mad = np.median(np.abs(residual))
    return float(cx), float(cy), float(r), float(rms), float(mad)

# 1) Load + ROI
img = cv2.imread(IMAGE_PATH)
if img is None:
    raise FileNotFoundError(f"Cannot read image: {IMAGE_PATH}")
H, W = img.shape[:2]
Y1 = 0 if Y1 is None else Y1
Y2 = H if Y2 is None else Y2
roi = img[Y1:Y2, X1:X2].copy()

# 2) Preprocess: equalize, denoise, enhance
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
g_eq = clahe.apply(gray)
g_denoised = cv2.bilateralFilter(g_eq, d=7, sigmaColor=75, sigmaSpace=75)
# mild unsharp mask for cleaner edges
g_blur = cv2.GaussianBlur(g_denoised, (0, 0), 1.0)
g_sharp = cv2.addWeighted(g_denoised, 1.5, g_blur, -0.5, 0)

# 3) Blob segmentation robust to lighting
#    Use black-hat (dark holes) and top-hat (bright dots), pick stronger response
se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
blackhat = cv2.morphologyEx(g_sharp, cv2.MORPH_BLACKHAT, se)
tophat   = cv2.morphologyEx(g_sharp, cv2.MORPH_TOPHAT,   se)

# choose the better enhancer by 95th percentile of response
if np.percentile(blackhat, 95) >= np.percentile(tophat, 95):
    enh = blackhat  # dark holes on lighter background
else:
    enh = tophat    # bright holes on darker background

# Otsu threshold on enhanced image -> bright blobs = hole candidates
_, bin0 = cv2.threshold(enh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

# 4) Clean up edges: close gaps, remove speckles
k_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
bin1 = cv2.morphologyEx(bin0, cv2.MORPH_CLOSE, k_small, iterations=2)
bin1 = cv2.morphologyEx(bin1, cv2.MORPH_OPEN,  k_small, iterations=1)

# Remove very small CCs fast
num, labels, stats, _ = cv2.connectedComponentsWithStats(bin1, connectivity=8)
min_keep = max(MIN_AREA, int(np.pi * (R_MIN ** 2) * 0.25))
mask = np.zeros_like(bin1)
for i in range(1, num):
    if stats[i, cv2.CC_STAT_AREA] >= min_keep:
        mask[labels == i] = 255

# 5) Contours & circle-quality filtering
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

detections = []
for cnt in contours:
    area = cv2.contourArea(cnt)
    if area < MIN_AREA:
        continue

    peri = cv2.arcLength(cnt, True)
    circularity = 4 * np.pi * area / (peri * peri + 1e-6)

    # minEnclosingCircle for quick r + roundness
    (cx0, cy0), r0 = cv2.minEnclosingCircle(cnt)
    r0 = float(r0)
    if not (R_MIN <= r0 <= R_MAX):
        continue
    roundness = area / (np.pi * r0 * r0 + 1e-6)

    # solidity
    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull)
    solidity = area / (hull_area + 1e-6)

    # precise circle fit on edge points (RMS residual)
    cx, cy, r, rms, mad = fit_circle_ls(cnt)
    if r <= 0 or not (R_MIN <= r <= R_MAX):
        continue
    if circularity < CIRC_MIN or not (ROUND_RANGE[0] <= roundness <= ROUND_RANGE[1]):
        continue
    if solidity < SOLIDITY_MIN:
        continue
    if (rms / r) > RESIDUAL_MAX_FRAC:
        continue

    # edge completeness proxy
    coverage = min(1.0, peri / (2 * np.pi * r + 1e-6))

    detections.append({
        "center_roi": (cx, cy),  # float, in ROI coords
        "radius": r,
        "circularity": circularity,
        "roundness": roundness,
        "solidity": solidity,
        "rms_frac": rms / r,
        "coverage": coverage,
        "contour": cnt
    })

# Optional: fuse with HoughCircles for tough cases
if USE_HOUGH:
    # dp=1.2 is a good default, tune param2 for sensitivity
    circles = cv2.HoughCircles(g_sharp, cv2.HOUGH_GRADIENT, dp=1.2,
                               minDist=max(8, int(R_MIN * 2)),
                               param1=120, param2=20,
                               minRadius=max(1, int(R_MIN - 2)),
                               maxRadius=int(R_MAX + 2))
    if circles is not None:
        for (x, y, r) in np.round(circles[0, :]).astype(int):
            # quick merge: add only if no existing detection within 0.5*r
            ok = True
            for d in detections:
                dx = d["center_roi"][0] - x
                dy = d["center_roi"][1] - y
                if (dx*dx + dy*dy) ** 0.5 < 0.5 * r:
                    ok = False
                    break
            if ok:
                detections.append({
                    "center_roi": (float(x), float(y)),
                    "radius": float(r),
                    "circularity": np.nan,
                    "roundness": np.nan,
                    "solidity": np.nan,
                    "rms_frac": np.nan,
                    "coverage": np.nan,
                    "contour": None
                })

# 6) Map back to full-image coords & apply outer ROI gate (for safety)
holes_xy = []
for d in detections:
    x, y = d["center_roi"]
    cx_full, cy_full = int(x + X1), int(y + Y1)
    if X1 <= cx_full <= X2 and Y1 <= cy_full <= Y2:
        d["center_full"] = (cx_full, cy_full)
        holes_xy.append(d)

# 7) Visualization
vis = img.copy()
# ROI box
cv2.rectangle(vis, (X1, Y1), (X2, Y2), (0, 255, 255), 2)

for d in holes_xy:
    cx, cy = map(int, d["center_full"])
    r = int(round(d["radius"]))
    # circle + center
    cv2.circle(vis, (cx, cy), r, (0, 255, 0), 2)
    cv2.circle(vis, (cx, cy), 2, (255, 0, 0), -1)
    # quality label
    txt = f"q={1.0 - (0 if np.isnan(d['rms_frac']) else min(0.99, d['rms_frac'])):.2f}"
    cv2.putText(vis, txt, (cx + 6, cy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(vis, txt, (cx + 6, cy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)

plt.figure(figsize=(16, 9))
plt.subplot(1, 3, 1); plt.title('Enhanced (BH/TH)'); plt.imshow(enh, cmap='gray'); plt.axis('off')
plt.subplot(1, 3, 2); plt.title('Binary (cleaned)'); plt.imshow(mask, cmap='gray'); plt.axis('off')
plt.subplot(1, 3, 3); plt.title('Detections'); plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)); plt.axis('off')
plt.tight_layout(); plt.show()

# 8) Print results
print(f"Detected holes in ROI [{X1}:{X2}] x [{Y1}:{Y2}]: {len(holes_xy)}")
for i, d in enumerate(holes_xy, 1):
    print(f"{i:02d}: center={d['center_full']}, r={d['radius']:.2f}, "
          f"circ={d['circularity']:.3f}, round={d['roundness']:.3f}, "
          f"sol={d['solidity']:.3f}, rms/r={d['rms_frac']:.3f}, cov={d['coverage']:.2f}")
