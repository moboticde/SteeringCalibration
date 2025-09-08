# Detect ONLY bolt-hole centers inside a given x-range [500, 1500]
# - filters to child contours that are round-ish and within a radius range
# - draws only the accepted hole contours and their centers
# - no "line centers" are computed or plotted

import cv2
import numpy as np
import matplotlib.pyplot as plt

# ------------------- CONFIG -------------------
IMAGE_PATH = r'C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\P1.jpg'

# ROI limits (x from 500 to 1500; full height by default)
X1, X2 = 500, 1500
Y1, Y2 = None, None  # set integers if you also want a y-limit (e.g., 200, 950)

# Hole shape/size filters (tune to your image scale)
MIN_AREA = 2
R_MIN, R_MAX = 10, 100
CIRC_MIN = 0.5  # Lowered to accept partial circles
ROUND_RANGE = (0.6, 2.0)  # Adjusted for partial circles
MIN_ARC_PERCENT = 0.5 # Minimum percentage of circle perimeter required
TARGET_RADIUS = 75  # Target circle radius
INNER_RADIUS = 330
OUTER_RADIUS = 420

# Update CONFIG section with main circle parameters
MIN_AREA_MAIN = 1000  # Much larger for main circle
TARGET_RADIUS_MAIN = 350  # Larger radius for main circle
RADIUS_TOLERANCE_MAIN = 50  # More tolerance for main circle
CIRC_MIN_MAIN = 0.2  # Higher circularity requirement for main circle

# Add to CONFIG section
VERTICAL_ANGLE_TOLERANCE = 10  # Degrees tolerance for vertical lines
MIN_LINE_LENGTH = 250  # Minimum length for vertical lines

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
    ret, thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3,3), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=2)
    eroded = cv2.erode(dilated, kernel, iterations=2)
    edges = cv2.Canny(eroded, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return edges


# Update HoughLinesP parameters in detect_vertical_lines function
def detect_vertical_lines(edges, angle_tolerance=10):
    """Detect vertical lines using HoughLinesP."""
    lines = cv2.HoughLinesP(edges, 
                           rho=1, 
                           theta=np.pi/180, 
                           threshold=50,
                           minLineLength=MIN_LINE_LENGTH,  # Using longer minimum length
                           maxLineGap=20)  # Increased gap to connect nearby segments
    
    vertical_lines = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            
            if x2 - x1 == 0:  # Perfectly vertical
                angle = 90
            else:
                angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            
            # Check if line is vertical and long enough
            if abs(angle - 90) <= angle_tolerance and length >= MIN_LINE_LENGTH:
                vertical_lines.append(line[0])
    
    return vertical_lines

def detect_main_hole(contours, hierarchy):
    main_hole = None
    max_circularity = 0
    
    for i, cnt in enumerate(contours):
        # Look for parent contours
        if hierarchy[0][i][3] != -1:
            continue
            
        area = cv2.contourArea(cnt)
        if area < MIN_AREA_MAIN:
            continue
            
        (cxcy, r) = cv2.minEnclosingCircle(cnt)
        r = float(r)
        
        # Calculate circularity
        peri = cv2.arcLength(cnt, True)
        circularity = 4 * np.pi * area / (peri * peri + 1e-6)
        
        # Check for main circle
        if circularity >= CIRC_MIN_MAIN and abs(r - TARGET_RADIUS_MAIN) <= RADIUS_TOLERANCE_MAIN:
            if circularity > max_circularity:
                max_circularity = circularity
                main_hole = cnt
    
    return main_hole, max_circularity

def detect_holes(contours, hierarchy, center_x, center_y, inner_radius, outer_radius):
    holes = []
    
    for i, cnt in enumerate(contours):
        # Look for child contours
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
        if not (inner_radius <= distance <= outer_radius):
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
            
    return holes

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

# Find the main circle using the new function
main_hole, max_circularity = detect_main_hole(contours, hierarchy)

# Add debug visualization with more information
if main_hole is not None:
    debug_vis = img.copy()
    cv2.drawContours(debug_vis, [main_hole], -1, (0, 255, 0), 2)
    center = center_of(main_hole)
    if center:
        cv2.circle(debug_vis, center, 5, (0, 0, 255), -1)
    (_, r) = cv2.minEnclosingCircle(main_hole)
    plt.figure(figsize=(12, 8))
    plt.imshow(cv2.cvtColor(debug_vis, cv2.COLOR_BGR2RGB))
    plt.title(f'Main Circle Detection\nCircularity: {max_circularity:.2f}, Radius: {r:.1f}')
    plt.show()
else:
    print("No main circle detected!")

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
        
        # Reprocess aligned image
        edges = process_image(img)
        contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

# Detect all holes in aligned image
holes = detect_holes(contours, hierarchy, 
                    center_x=1000, 
                    center_y=500, 
                    inner_radius=INNER_RADIUS, 
                    outer_radius=OUTER_RADIUS)

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

# Draw lines
print(f"Detected hole centers inside ROI [{X1}:{X2}] x [{Y1}:{Y2}]: {len(hole_centers_roi)}")
for p in hole_centers_roi:
    print(p)

# Add debug visualization for vertical lines
vertical_lines = detect_vertical_lines(edges)
debug_lines = img.copy()
for line in vertical_lines:
    x1, y1, x2, y2 = line
    cv2.line(debug_lines, (x1, y1), (x2, y2), (0, 0, 255), 2)

plt.figure(figsize=(16, 8))

plt.subplot(1, 2, 1)
plt.title('Edges')
plt.imshow(edges, cmap='gray')
plt.axis('on')

plt.subplot(1, 2, 2)
plt.title('Contours / Hole Centers & Vertical Lines (ROI)')
vis_combined = vis.copy()

# Draw vertical lines in the ROI
for line in vertical_lines:
    x1, y1, x2, y2 = line
    # Only draw lines that are within the ROI
    if X1 <= x1 <= X2 and X1 <= x2 <= X2:
        cv2.line(vis_combined, (x1, y1), (x2, y2), (0, 0, 255), 2)

plt.imshow(cv2.cvtColor(vis_combined, cv2.COLOR_BGR2RGB))
if hole_centers_roi:
    xs, ys = zip(*hole_centers_roi)
    plt.scatter(xs, ys, s=120, edgecolors='k', facecolors='dodgerblue', linewidths=1.5, label='Hole Centers (ROI)')

# Add legend entries for both holes and lines
plt.plot([], [], color='red', linewidth=2, label='Vertical Lines')
plt.legend(loc='upper right')
plt.axis('on')

plt.tight_layout()
plt.show()

# Print results
print(f"Detected hole centers inside ROI [{X1}:{X2}] x [{Y1}:{Y2}]: {len(hole_centers_roi)}")
print(f"Number of vertical lines in ROI: {sum(1 for line in vertical_lines if X1 <= line[0] <= X2)}")