
# Detect ONLY bolt-hole centers inside a given x-range [500, 1500]
# - filters to child contours that are round-ish and within a radius range
# - draws only the accepted hole contours and their centers
# - no "line centers" are computed or plotted

import cv2
import numpy as np
import matplotlib.pyplot as plt

# ------------------- CONFIG -------------------
IMAGE_PATH = r'C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\P3.jpg'

# ROI limits (x from 500 to 1500; full height by default)
X1, X2 = 500, 1500
Y1, Y2 = None, None  # set integers if you also want a y-limit (e.g., 200, 950)

# Hole shape/size filters (tune to your image scale)
MIN_AREA = 2
R_MIN, R_MAX = 10, 100
CIRC_MIN = 0.2  # Lowered to accept partial circles
ROUND_RANGE = (0.75, 2.0)  # Adjusted for partial circles
MIN_ARC_PERCENT = 0.6  # Minimum percentage of circle perimeter required
TARGET_RADIUS = 75  # Target circle radius
RADIUS_TOLERANCE = 10  # How much the radius can differ from target
INNER_RADIUS = 330
OUTER_RADIUS = 420

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
        # Mark all nearby centers as used
        for j, (x2, y2) in enumerate(centers):
            if j <= i or j in used:
                continue
            dist = np.sqrt((x2-x1)**2 + (y2-y1)**2)
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
    eroded = cv2.erode(dilated, kernel, iterations=1)
    edges = cv2.Canny(eroded, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return edges

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

# Find the main circle
main_hole = None
for i, cnt in enumerate(contours):
    if hierarchy[0][i][3] == -1:
        continue
    area = cv2.contourArea(cnt)
    if area < MIN_AREA:
        continue
    (cxcy, r) = cv2.minEnclosingCircle(cnt)
    r = float(r)

    if abs(r - TARGET_RADIUS) <= RADIUS_TOLERANCE:
        main_hole = cnt
        break
if main_hole is not None:
    debug_vis = img.copy()
    cv2.drawContours(debug_vis, [main_hole], -1, (0, 255, 0), 2)
    plt.imshow(cv2.cvtColor(debug_vis, cv2.COLOR_BGR2RGB))
    plt.title('Main Circle Detection')
    plt.show()
    
# Align image if main circle found
if main_hole is not None:
    center = center_of(main_hole)
    (_, r) = cv2.minEnclosingCircle(main_hole)
    print(f"Main circle: center={center}, radius={r}")
    if center:
        center_x, center_y = 1000, 500
        dx = center_x - center[0]
        dy = center_y - center[1]
        M = np.float32([[1, 0, dx],
                        [0, 1, dy]])
        img = cv2.warpAffine(img, M, (W, H))
        
        # Update ROI coordinates
        X1 += int(dx)
        X2 += int(dx)
        Y1 += int(dy)
        Y2 += int(dy)
        
        # Reprocess aligned image
        edges = process_image(img)
        contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

# Detect all holes in aligned image
holes = []
center_x, center_y = 1000, 500  # Our reference center

for i, cnt in enumerate(contours):
    if hierarchy[0][i][3] == -1:
        continue

    # Get the center of the current contour
    cnt_center = center_of(cnt)
    if cnt_center is None:
        continue
    
    # Calculate distance from reference center
    dx = cnt_center[0] - center_x
    dy = cnt_center[1] - center_y
    distance = np.sqrt(dx*dx + dy*dy)
    
    # Check if the hole is within our radius range
    if not (INNER_RADIUS <= distance <= OUTER_RADIUS):
        continue

    area = cv2.contourArea(cnt)
    if area < MIN_AREA:
        continue

    (cxcy, r) = cv2.minEnclosingCircle(cnt)
    r = float(r)
    
    if len(cnt) < 40:  # Minimum points check
        continue
    
    full_circle_perimeter = 2 * np.pi * r
    peri = cv2.arcLength(cnt, False)
    arc_percentage = peri / full_circle_perimeter
    
    circularity = 4 * np.pi * area / (peri * peri + 1e-6)
    roundness = area / (np.pi * r * r + 1e-6)

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
    center = (int(x), int(y))
    radius = int(radius)
    cv2.circle(vis, center, radius, (255, 0, 0), 2)

# Draw central reference circle
center_x = 1000
center_y = 500
cv2.circle(vis, (center_x, center_y), TARGET_RADIUS, (0, 0, 255), 2)

cv2.circle(vis, (center_x, center_y), 330, (0, 0, 255), 2)  # Inner radius circle
cv2.circle(vis, (center_x, center_y), 397, (0, 0, 255), 2)  # Outer radius circle

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
    plt.scatter(xs, ys, s=120, edgecolors='k', facecolors='dodgerblue', linewidths=1.5, label='Hole Centers (ROI)')
plt.legend(loc='upper right')
plt.axis('on')

plt.tight_layout()
plt.show()

# Print results
print(f"Detected hole centers inside ROI [{X1}:{X2}] x [{Y1}:{Y2}]: {len(hole_centers_roi)}")
for p in hole_centers_roi:
    print(p)