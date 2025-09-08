import cv2
import numpy as np
import matplotlib.pyplot as plt

# ------------------- CONFIG -------------------
IMAGE_PATH = r'C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\P9.jpg'

# ROI limits (x from 500 to 1500; full height by default)
X1, X2 = 500, 1500
Y1, Y2 = None, None  # set integers if you also want a y-limit (e.g., 200, 950)

# Bolt-hole shape/size filters (tune to your image scale)
MIN_AREA = 2
R_MIN, R_MAX = 15, 100
CIRC_MIN = 0.40                 # relaxed for partial/dirty bolt holes
ROUND_RANGE = (0.75, 2.0)
MIN_ARC_PERCENT = 0.60
TARGET_RADIUS = 75
RADIUS_TOLERANCE = 5
INNER_RADIUS = 330
OUTER_RADIUS = 420

# --- main-hole (center bore) checks (stricter!) ---
MAIN_MIN_POINTS   = 60
MAIN_RADIUS_TOL   = 12          # ±px around TARGET_RADIUS
MAIN_CIRC_MIN     = 0.78        # 4πA/P²
MAIN_ROUND_RANGE  = (0.85, 1.15) # A/(π r²)
MAIN_MIN_ARC_PCT  = 0.55
MAIN_MAX_ASPECT   = 1.60        # ellipse/minAreaRect axis ratio ≤ this
MAIN_MIN_SOLIDITY = 0.85        # A / A(hull)

# --------------------------------------------------

def filter_overlapping_circles(centers, min_distance=30):
    """Filter out overlapping circle centers, keeping the first occurrence."""
    if not centers:
        return []
    filtered = []
    used = set()
    for i, (x1, y1) in enumerate(centers):
        if i in used:
            continue
        filtered.append((x1, y1))
        for j, (x2, y2) in enumerate(centers):
            if j <= i or j in used:
                continue
            dist = np.hypot(x2 - x1, y2 - y1)
            if dist < min_distance:
                used.add(j)
    return filtered

def center_of(cnt):
    """Calculate the center of a contour using moments."""
    M = cv2.moments(cnt)
    if M["m00"] == 0:
        return None
    return (int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"]))

def process_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = np.ones((3,3), np.uint8)
    dilated = cv2.dilate(blurred, kernel, iterations=1)
    eroded  = cv2.erode(dilated, kernel, iterations=1)
    edges = cv2.Canny(eroded, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return edges

def shape_metrics(cnt):
    """Return geometric metrics for a contour used to verify 'roundness'."""
    if len(cnt) < 5:
        return None
    area = cv2.contourArea(cnt)
    if area <= 0:
        return None

    peri_closed = cv2.arcLength(cnt, True)
    peri_open   = cv2.arcLength(cnt, False)
    ((cx, cy), r) = cv2.minEnclosingCircle(cnt)
    r = float(r)

    circularity = 4.0 * np.pi * area / (peri_closed * peri_closed + 1e-6)
    roundness   = area / (np.pi * r * r + 1e-6)
    arc_pct     = peri_open / (2.0 * np.pi * r + 1e-6)

    # aspect by ellipse & min-area-rect
    aspect_ellipse = 1.0
    (cxy,(MA,ma),_) = cv2.fitEllipse(cnt)
    aspect_ellipse = max(MA, ma) / (min(MA, ma) + 1e-6)
    ((rx, ry), (w, h), _) = cv2.minAreaRect(cnt)
    aspect_rect = (max(w, h) / (min(w, h) + 1e-6)) if min(w, h) > 1e-6 else float('inf')
    aspect = max(aspect_ellipse, aspect_rect)

    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull) + 1e-6
    solidity = area / hull_area

    return {
        "center": (int(cx), int(cy)),
        "r": r,
        "area": area,
        "circularity": circularity,
        "roundness": roundness,
        "arc_pct": arc_pct,
        "aspect": aspect,
        "solidity": solidity
    }

# ------------------- MAIN -------------------

# 1) Load image
img = cv2.imread(IMAGE_PATH)
if img is None:
    raise FileNotFoundError(f"Cannot read image: {IMAGE_PATH}")

H, W = img.shape[:2]
if Y1 is None: Y1 = 0
if Y2 is None: Y2 = H

# First pass to find main circle
edges = process_image(img)
contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
if hierarchy is None:
    hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

# Find the main circle using shape constraints and scoring
main_hole, best = None, None
candidates = []
for i, cnt in enumerate(contours):
    # inner (hole) contours only
    if hierarchy[0][i][3] == -1:
        continue
    if len(cnt) < MAIN_MIN_POINTS:
        continue

    m = shape_metrics(cnt)
    if m is None:
        continue

    if abs(m["r"] - TARGET_RADIUS) > MAIN_RADIUS_TOL:
        continue
    if (m["circularity"] < MAIN_CIRC_MIN or
        not (MAIN_ROUND_RANGE[0] <= m["roundness"] <= MAIN_ROUND_RANGE[1]) or
        m["arc_pct"] < MAIN_MIN_ARC_PCT or
        m["aspect"] > MAIN_MAX_ASPECT or
        m["solidity"] < MAIN_MIN_SOLIDITY):
        continue

    candidates.append((cnt, m))

if candidates:
    def score(m):
        # Prefer radius close to target, then high circularity, then arc coverage,
        # then lower aspect (more round), then higher solidity.
        return (-abs(m["r"] - TARGET_RADIUS), m["circularity"], m["arc_pct"], -m["aspect"], m["solidity"])
    cnt, m = max(candidates, key=lambda cm: score(cm[1]))
    main_hole, best = cnt, m

if main_hole is not None:
    print(f"[MAIN] center={best['center']} r={best['r']:.1f} "
          f"circ={best['circularity']:.3f} round={best['roundness']:.3f} "
          f"arc={best['arc_pct']:.2f} aspect={best['aspect']:.2f} solid={best['solidity']:.2f}")
    debug_vis = img.copy()
    cv2.drawContours(debug_vis, [main_hole], -1, (0, 255, 0), 2)
    cv2.circle(debug_vis, best["center"], int(best["r"]), (0, 255, 0), 2)
    plt.imshow(cv2.cvtColor(debug_vis, cv2.COLOR_BGR2RGB))
    plt.title('Main Circle Detection')
    plt.show()

# Align image if main circle found
if main_hole is not None:
    ref_cx, ref_cy = 1000, 500
    cx, cy = best['center']
    dx, dy = ref_cx - cx, ref_cy - cy
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    img = cv2.warpAffine(img, M, (W, H))

    # Update ROI coordinates to follow the content
    X1 += int(dx); X2 += int(dx)
    Y1 += int(dy); Y2 += int(dy)

    # Reprocess aligned image
    edges = process_image(img)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

# Detect all bolt holes in aligned image (annulus gate + roundness checks)
holes = []
center_x, center_y = 1000, 500  # reference center

for i, cnt in enumerate(contours):
    if hierarchy[0][i][3] == -1:
        continue  # only child contours

    cnt_center = center_of(cnt)
    if cnt_center is None:
        continue

    dx = cnt_center[0] - center_x
    dy = cnt_center[1] - center_y
    distance = np.hypot(dx, dy)

    if not (INNER_RADIUS <= distance <= OUTER_RADIUS):
        continue

    area = cv2.contourArea(cnt)
    if area < MIN_AREA:
        continue

    if len(cnt) < 40:
        continue

    # metrics for bolt holes (more tolerant than main-hole)
    ((_, _), r) = cv2.minEnclosingCircle(cnt)
    r = float(r)
    peri_closed = cv2.arcLength(cnt, True)
    peri_open   = cv2.arcLength(cnt, False)
    full_circle_perimeter = 2 * np.pi * r
    arc_percentage = peri_open / (full_circle_perimeter + 1e-6)
    circularity = 4 * np.pi * area / (peri_closed * peri_closed + 1e-6)
    roundness   = area / (np.pi * r * r + 1e-6)

    if (((circularity >= CIRC_MIN and ROUND_RANGE[0] <= roundness <= ROUND_RANGE[1]) or
         (arc_percentage >= MIN_ARC_PERCENT)) and
        (R_MIN <= r <= R_MAX)):
        holes.append(cnt)

# Get centers
hole_centers_all = [c for c in (center_of(h) for h in holes) if c is not None]
hole_centers_roi = [(x, y) for (x, y) in hole_centers_all if (X1 <= x <= X2 and Y1 <= y <= Y2)]
hole_centers_roi = filter_overlapping_circles(hole_centers_roi)

# Visualization
vis = img.copy()
cv2.drawContours(vis, holes, -1, (0, 255, 0), 2)
cv2.rectangle(vis, (X1, Y1), (X2, Y2), (0, 255, 255), 3)

for cnt in holes:
    (x, y), radius = cv2.minEnclosingCircle(cnt)
    center_pt = (int(x), int(y))
    radius = int(radius)
    cv2.circle(vis, center_pt, radius, (255, 0, 0), 2)

# Draw central reference circles
cv2.circle(vis, (center_x, center_y), TARGET_RADIUS, (0, 0, 255), 2)
cv2.circle(vis, (center_x, center_y), INNER_RADIUS, (0, 0, 255), 2)
cv2.circle(vis, (center_x, center_y), OUTER_RADIUS, (0, 0, 255), 2)

# Plot results
plt.figure(figsize=(16, 8))

plt.subplot(1, 2, 1)
plt.title('Edges')
plt.imshow(edges, cmap='gray')
plt.axis('on')

plt.subplot(1, 2, 2)
plt.title('Contours / Hole Centers (ROI)')
plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
if hole_centers_roi:
    xs, ys = zip(*hole_centers_roi)
    plt.scatter(xs, ys, s=120, edgecolors='k', facecolors='dodgerblue',
                linewidths=1.5, label='Hole Centers (ROI)')
plt.legend(loc='upper right')
plt.axis('on')

plt.tight_layout()
plt.show()

# Print results
print(f"Detected hole centers inside ROI [{X1}:{X2}] x [{Y1}:{Y2}]: {len(hole_centers_roi)}")
for p in hole_centers_roi:
    print(p)
