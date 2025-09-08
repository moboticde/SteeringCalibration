import cv2
import numpy as np
import matplotlib.pyplot as plt

# ------------------- CONFIG -------------------
IMAGE_PATH = r'C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\P1.jpg'

# ROI (x from 500 to 1500; full height by default)
X1, X2 = 500, 1500
Y1, Y2 = None, None

# Bolt-hole filters
MIN_AREA = 2
R_MIN, R_MAX = 10, 100
CIRC_MIN = 0.40
ROUND_RANGE = (0.75, 2.0)
MIN_ARC_PERCENT = 0.60

# Reference geometry
REF_CX, REF_CY = 1000.0, 500.0
TARGET_RADIUS = 75
INNER_RADIUS = 330
OUTER_RADIUS = 397

# Main-hole (center bore) checks (stricter)
MAIN_MIN_POINTS   = 60
MAIN_RADIUS_TOL   = 12
MAIN_CIRC_MIN     = 0.78
MAIN_ROUND_RANGE  = (0.85, 1.15)
MAIN_MIN_ARC_PCT  = 0.55
MAIN_MAX_ASPECT   = 1.60
MAIN_MIN_SOLIDITY = 0.85

# ------------------- HELPERS -------------------
def filter_overlapping_circles(centers, min_distance=30):
    if not centers: return []
    filtered, used = [], set()
    for i, (x1, y1) in enumerate(centers):
        if i in used: continue
        filtered.append((x1, y1))
        for j, (x2, y2) in enumerate(centers):
            if j <= i or j in used: continue
            if np.hypot(x2-x1, y2-y1) < min_distance:
                used.add(j)
    return filtered

def center_of(cnt):
    M = cv2.moments(cnt)
    if M["m00"] == 0: return None
    return (int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"]))

def process_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = np.ones((3,3), np.uint8)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return edges

def shape_metrics(cnt):
    if len(cnt) < 5: return None
    area = cv2.contourArea(cnt)
    if area <= 0: return None

    peri_c = cv2.arcLength(cnt, True)
    peri_o = cv2.arcLength(cnt, False)
    ((cx, cy), r) = cv2.minEnclosingCircle(cnt); r = float(r)

    circularity = 4.0 * np.pi * area / (peri_c * peri_c + 1e-6)
    roundness   = area / (np.pi * r * r + 1e-6)
    arc_pct     = peri_o / (2.0 * np.pi * r + 1e-6)

    ( (ex,ey), (MA,ma), _ ) = cv2.fitEllipse(cnt)
    aspect_ellipse = max(MA, ma) / (min(MA, ma) + 1e-6)

    ( (rx,ry), (w,h), _ ) = cv2.minAreaRect(cnt)
    aspect_rect = max(w, h) / (min(w, h) + 1e-6) if min(w,h) > 1e-6 else float('inf')
    aspect = max(aspect_ellipse, aspect_rect)

    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull) + 1e-6
    solidity = area / hull_area

    return {
        "center": (cx, cy),  # float center from minEnclosingCircle
        "r": r,
        "area": area,
        "circularity": circularity,
        "roundness": roundness,
        "arc_pct": arc_pct,
        "aspect": aspect,
        "solidity": solidity
    }

def fit_circle_kasa(cnt):
    """Least-squares circle fit (Kåsa). Returns (cx, cy, r) in float."""
    pts = cnt.reshape(-1, 2).astype(np.float64)
    x, y = pts[:,0], pts[:,1]
    A = np.column_stack([2*x, 2*y, np.ones_like(x)])
    b = x*x + y*y
    (cx, cy, d), *_ = np.linalg.lstsq(A, b, rcond=None)
    r = np.sqrt(max(cx*cx + cy*cy - d, 0.0))
    return float(cx), float(cy), float(r)

# ------------------- MAIN -------------------
img = cv2.imread(IMAGE_PATH)
if img is None: raise FileNotFoundError(IMAGE_PATH)
H, W = img.shape[:2]
if Y1 is None: Y1 = 0
if Y2 is None: Y2 = H

# Find contours
edges = process_image(img)
contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
if hierarchy is None:
    hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

# --------- MAIN HOLE SELECTION + REFINEMENT ----------
candidates = []
for i, cnt in enumerate(contours):
    if hierarchy[0][i][3] == -1:      # only child (hole) contours
        continue
    if len(cnt) < MAIN_MIN_POINTS:
        continue
    m = shape_metrics(cnt)
    if m is None: continue
    if abs(m["r"] - TARGET_RADIUS) > MAIN_RADIUS_TOL: continue
    if (m["circularity"] < MAIN_CIRC_MIN or
        not (MAIN_ROUND_RANGE[0] <= m["roundness"] <= MAIN_ROUND_RANGE[1]) or
        m["arc_pct"] < MAIN_MIN_ARC_PCT or
        m["aspect"] > MAIN_MAX_ASPECT or
        m["solidity"] < MAIN_MIN_SOLIDITY):
        continue
    candidates.append((cnt, m))

main_hole_cnt, main_fit = None, None
if candidates:
    def score(m):
        return (-abs(m["r"] - TARGET_RADIUS), m["circularity"], m["arc_pct"], -m["aspect"], m["solidity"])
    main_hole_cnt, m0 = max(candidates, key=lambda cm: score(cm[1]))
    # refine center with least-squares circle fit
    cx, cy, r = fit_circle_kasa(main_hole_cnt)
    main_fit = {"center": (cx, cy), "r": r}

# Visualize detected main hole (pre-align)
if main_fit:
    print(f"[MAIN before align] center={main_fit['center']} r={main_fit['r']:.2f}")
    dbg = img.copy()
    cv2.circle(dbg, (int(main_fit['center'][0]), int(main_fit['center'][1])), int(main_fit['r']), (0,255,0), 2)
    plt.figure(); plt.imshow(cv2.cvtColor(dbg, cv2.COLOR_BGR2RGB)); plt.title('Main hole (pre-align)'); plt.axis('off'); plt.show()

# --------- ALIGN BY TRANSLATION (NO ROUNDING) ----------
if main_fit:
    dx = REF_CX - main_fit['center'][0]
    dy = REF_CY - main_fit['center'][1]
    M = np.float32([[1,0,dx],[0,1,dy]])
    img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # Update ROI (ints are fine only for ROI bookkeeping)
    X1 = int(X1 + dx); X2 = int(X2 + dx)
    Y1 = int(Y1 + dy); Y2 = int(Y2 + dy)

    # Recompute edges/contours after shift
    edges = process_image(img)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

# --------- BOLT HOLES DETECTION (annulus gate) ----------
holes = []
for i, cnt in enumerate(contours):
    if hierarchy[0][i][3] == -1:
        continue
    c = center_of(cnt)
    if c is None: continue
    d = np.hypot(c[0] - REF_CX, c[1] - REF_CY)
    if not (INNER_RADIUS <= d <= OUTER_RADIUS):
        continue
    area = cv2.contourArea(cnt)
    if area < MIN_AREA or len(cnt) < 40:
        continue

    ((_, _), r) = cv2.minEnclosingCircle(cnt); r = float(r)
    peri_c = cv2.arcLength(cnt, True)
    peri_o = cv2.arcLength(cnt, False)
    full = 2*np.pi*r
    arc_pct = peri_o / (full + 1e-6)
    circularity = 4*np.pi*area / (peri_c*peri_c + 1e-6)
    roundness = area / (np.pi*r*r + 1e-6)

    if (((circularity >= CIRC_MIN and ROUND_RANGE[0] <= roundness <= ROUND_RANGE[1]) or
         (arc_pct >= MIN_ARC_PERCENT)) and (R_MIN <= r <= R_MAX)):
        holes.append(cnt)

# Centers in ROI
hole_centers_all = [center_of(h) for h in holes if center_of(h) is not None]
hole_centers_roi = [(x,y) for (x,y) in hole_centers_all if X1 <= x <= X2 and Y1 <= y <= Y2]
hole_centers_roi = filter_overlapping_circles(hole_centers_roi)

# --------- VISUALIZATION ----------
vis = img.copy()
cv2.drawContours(vis, holes, -1, (0,255,0), 2)
cv2.rectangle(vis, (X1, Y1), (X2, Y2), (0,255,255), 3)

for cnt in holes:
    (x, y), radius = cv2.minEnclosingCircle(cnt)
    cv2.circle(vis, (int(x), int(y)), int(radius), (255,0,0), 2)

# reference circles (centered exactly at REF_CX/REF_CY after alignment)
cv2.circle(vis, (int(REF_CX), int(REF_CY)), TARGET_RADIUS, (0,0,255), 2)
cv2.circle(vis, (int(REF_CX), int(REF_CY)), INNER_RADIUS, (0,0,255), 2)
cv2.circle(vis, (int(REF_CX), int(REF_CY)), OUTER_RADIUS, (0,0,255), 2)

plt.figure(figsize=(16,8))
plt.subplot(1,2,1); plt.title('Edges'); plt.imshow(edges, cmap='gray'); plt.axis('on')
plt.subplot(1,2,2); plt.title('Contours / Hole Centers (ROI)')
plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
if hole_centers_roi:
    xs, ys = zip(*hole_centers_roi)
    plt.scatter(xs, ys, s=120, edgecolors='k', facecolors='dodgerblue', linewidths=1.5, label='Hole Centers (ROI)')
plt.legend(loc='upper right'); plt.axis('on'); plt.tight_layout(); plt.show()

print(f"Detected hole centers inside ROI [{X1}:{X2}] x [{Y1}:{Y2}]: {len(hole_centers_roi)}")
for p in hole_centers_roi:
    print(p)
