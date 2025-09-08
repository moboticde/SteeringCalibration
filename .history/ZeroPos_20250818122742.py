# Detect ONLY bolt-hole centers inside a given x-range [500, 1500]
# - filters to child contours that are round-ish and within a radius range
# - draws only the accepted hole contours and their centers
# - no "line centers" are computed or plotted

import cv2
import numpy as np
import matplotlib.pyplot as plt

# ------------------- CONFIG -------------------
IMAGE_PATH = r'C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\WIN_20250804_12_29_34_Pro.jpg'

# ROI limits (x from 500 to 1500; full height by default)
X1, X2 = 500, 1500
Y1, Y2 = None, None  # set integers if you also want a y-limit (e.g., 200, 950)

# Hole shape/size filters (tune to your image scale)
MIN_AREA = 2
R_MIN, R_MAX = 15, 100
CIRC_MIN = 0.5  # Lowered to accept partial circles
ROUND_RANGE = (0.75, 2.0)  # Adjusted for partial circles
MIN_ARC_PERCENT = 0.6  # Minimum percentage of circle perimeter required

TARGET_RADIUS = 75  # Target circle radius
RADIUS_TOLERANCE = 10  # How much the radius can differ from target

# ---------------------------------------------

# 1) Load image
img = cv2.imread(IMAGE_PATH)
if img is None:
    raise FileNotFoundError(f"Cannot read image: {IMAGE_PATH}")

H, W = img.shape[:2]
if Y1 is None: Y1 = 0
if Y2 is None: Y2 = H

# 2) Preprocess & edges
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
# Apply stronger blur to reduce noise
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
# Add morphological operations to close gaps
kernel = np.ones((3,3), np.uint8)
dilated = cv2.dilate(blurred, kernel, iterations=1)
eroded = cv2.erode(dilated, kernel, iterations=1)
# Adjust Canny parameters for better edge detection
edges = cv2.Canny(eroded, 50, 150)
# Close small gaps in edges
edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)


# 3) Find contours with hierarchy
contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
if hierarchy is None:
    hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

# 4) Keep only round child contours (holes)
holes = []
for i, cnt in enumerate(contours):
    # must have a parent (child contour inside something)
    if hierarchy[0][i][3] == -1:
        continue

    area = cv2.contourArea(cnt)
    if area < MIN_AREA:
        continue

    # Get the minimum enclosing circle
    (cxcy, r) = cv2.minEnclosingCircle(cnt)
    r = float(r)

    
    # Additional check for minimum contour points
    if len(cnt) < 40:  # Require minimum number of points
        continue
    
    # Calculate full circle perimeter
    full_circle_perimeter = 2 * np.pi * r
    
    # Get actual contour perimeter
    peri = cv2.arcLength(cnt, False)  # Changed to False for open contours
    
    # Calculate what fraction of a full circle we have
    arc_percentage = peri / full_circle_perimeter
    
    # Calculate circularity and roundness
    circularity = 4 * np.pi * area / (peri * peri + 1e-6)
    roundness = area / (np.pi * r * r + 1e-6)

    # Accept if it's either a full circle or a significant portion of one AND has the correct radius
    if (((circularity >= CIRC_MIN and ROUND_RANGE[0] <= roundness <= ROUND_RANGE[1]) or 
        (arc_percentage >= MIN_ARC_PERCENT)) and 
        (abs(r - TARGET_RADIUS) <= RADIUS_TOLERANCE)):  # New radius check
        holes.append(cnt)


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
            # Calculate distance between centers
            dist = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            if dist < min_distance:
                used.add(j)
    
    return filtered

# 5) Centers
def center_of(cnt):
    M = cv2.moments(cnt)
    if M["m00"] == 0:
        return None
    return (int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"]))

hole_centers_all = [c for c in (center_of(h) for h in holes) if c is not None]

# 6) ROI filter
hole_centers_roi = [(x, y) for (x, y) in hole_centers_all if (X1 <= x <= X2 and Y1 <= y <= Y2)]
hole_centers_roi = filter_overlapping_circles(hole_centers_roi)

# 7) Draw only hole contours (for context) + ROI box
if hole_centers_roi:
    # Calculate image center
    center_x = W // 2
    center_y = H // 2
    
    # Get the detected circle center (using first detected hole)
    detected_x, detected_y = hole_centers_roi[0]
    
    # Calculate required translation
    dx = center_x - detected_x
    dy = center_y - detected_y
    
    # Create translation matrix
    M = np.float32([[1, 0, dx],
                    [0, 1, dy]])
    
    # Apply translation to the original image
    img = cv2.warpAffine(img, M, (W, H))
    
    # Update hole centers coordinates
    hole_centers_roi = [(x + dx, y + dy) for (x, y) in hole_centers_roi]
    
    # Update hole contours
    holes = [cv2.transform(cnt.reshape(1, -1, 2), M).reshape(-1, 2) for cnt in holes]
    
    # Update ROI coordinates
    X1 += int(dx)
    X2 += int(dx)

# Now continue with visualization using translated coordinates
vis = img.copy()
cv2.drawContours(vis, holes, -1, (0, 255, 0), 2)
cv2.rectangle(vis, (X1, Y1), (X2, Y2), (0, 255, 255), 3)

for cnt in holes:
    (x, y), radius = cv2.minEnclosingCircle(cnt)
    center = (int(x), int(y))
    radius = int(radius)
    cv2.circle(vis, center, radius, (255, 0, 0), 2)

center_x = W // 2
center_y = H // 2
radius = 75  # 150/2 for diameter of 150
cv2.circle(vis, (center_x, center_y), radius, (0, 0, 255), 2)  # Red circle in BGR format

# 8) Plot
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

# 9) Print results
print(f"Detected hole centers inside ROI [{X1}:{X2}] x [{Y1}:{Y2}]: {len(hole_centers_roi)}")
for p in hole_centers_roi:
    print(p)
