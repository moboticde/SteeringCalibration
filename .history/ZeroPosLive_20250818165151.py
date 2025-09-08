# Detect ONLY bolt-hole centers inside a given x-range [500, 1500]
# - filters to child contours that are round-ish and within a radius range
# - draws only the accepted hole contours and their centers
# - no "line centers" are computed or plotted

import cv2
import numpy as np
import matplotlib.pyplot as plt
import time

# ------------------- CONFIG -------------------

# Camera settings
CAMERA_ID = 0
FPS_TARGET = 30
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
INPUT_SCALE = 1.0  # No need to scale down at this resolution
DISPLAY_SCALE = 1.0  # Show at native resolution

# ROI limits
X1, X2 = 500, 1500
Y1, Y2 = None, None

# Detection parameters
MIN_AREA = 2
R_MIN, R_MAX = 10, 100
CIRC_MIN = 0.5
ROUND_RANGE = (0.6, 2.0)
MIN_ARC_PERCENT = 0.5
TARGET_RADIUS = 75
INNER_RADIUS = 330
OUTER_RADIUS = 420

# Main circle parameters
MIN_AREA_MAIN = 1000
TARGET_RADIUS_MAIN = 350
RADIUS_TOLERANCE_MAIN = 50
CIRC_MIN_MAIN = 0.2

# Vertical lines parameters
VERTICAL_ANGLE_TOLERANCE = 10
MIN_LINE_LENGTH = 250
LINE_RANGE_1 = (900, 930)
LINE_RANGE_2 = (1070, 1100)

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


def rescale_frame(frame, scale=0.75):
    """Rescale frame while maintaining aspect ratio"""
    width = int(frame.shape[1] * scale)
    height = int(frame.shape[0] * scale)
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

def process_frame(frame):
    """Process a single frame and return the visualization"""
    H, W = frame.shape[:2]
    
    # Create visualization frame
    vis = frame.copy()
    
    # Calculate center coordinates
    center_x = int(W / 2)
    center_y = int(H / 2)
    
    # Scale circle radii using same scale factor as ROI
    scale_factor = CAMERA_WIDTH / 1920
    scaled_inner = int(INNER_RADIUS * scale_factor)
    scaled_outer = int(OUTER_RADIUS * scale_factor)
    
    # Draw reference circles in red
    cv2.circle(vis, (center_x, center_y), scaled_inner, (0, 0, 255), 2)  # Inner circle
    cv2.circle(vis, (center_x, center_y), scaled_outer, (0, 0, 255), 2)  # Outer circle
    
    # Scale and draw ROI rectangle
    scaled_x1 = int(X1 * scale_factor)
    scaled_x2 = int(X2 * scale_factor)
    scaled_y1 = 0 if Y1 is None else int(Y1 * scale_factor)
    scaled_y2 = H if Y2 is None else int(Y2 * scale_factor)
    
    # Draw ROI rectangle in yellow
    cv2.rectangle(vis, (scaled_x1, scaled_y1), (scaled_x2, scaled_y2), 
                 (0, 255, 255), 2)
    
    return vis

def main():
    # Initialize webcam
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    # Set camera properties with your resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS_TARGET)
    
    # Verify actual camera resolution
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera resolution: {actual_width}x{actual_height}")
    
    # Create window with specific size
    cv2.namedWindow('Hole Detection', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Hole Detection', CAMERA_WIDTH, CAMERA_HEIGHT)
    
    # Scale ROI coordinates for 1280x720
    global X1, X2
    scale_factor = CAMERA_WIDTH / 1920  # Original coords were for 1920 width
    X1 = int(X1 * scale_factor)  # Scale from 500 to ~333
    X2 = int(X2 * scale_factor)  # Scale from 1500 to ~1000
    
    print("Press 'q' to quit")
    
    while True:
        start_time = time.time()
        
        # Read frame
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        # Process frame
        result = process_frame(frame)
        
        # Scale for display
        if DISPLAY_SCALE != 1.0:
            result = cv2.resize(result, None, 
                              fx=DISPLAY_SCALE, fy=DISPLAY_SCALE,
                              interpolation=cv2.INTER_AREA)
        
        # Show FPS
        fps = 1.0 / (time.time() - start_time + 1e-6)
        cv2.putText(result, f"FPS: {fps:.1f}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Show result
        cv2.imshow('Hole Detection', result)
        
        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()