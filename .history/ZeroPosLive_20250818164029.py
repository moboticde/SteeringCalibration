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
INPUT_SCALE = 0.5
DISPLAY_SCALE = 0.75

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


def rescale_frame(frame, scale):
    """Rescale frame while maintaining aspect ratio"""
    width = int(frame.shape[1] * scale)
    height = int(frame.shape[0] * scale)
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

def process_frame(frame):
    """Process a single frame and return the visualization"""
    # Scale input frame
    frame = cv2.resize(frame, None, fx=INPUT_SCALE, fy=INPUT_SCALE, 
                      interpolation=cv2.INTER_AREA)
    H, W = frame.shape[:2]
    
    # Scale ROI coordinates
    scaled_x1 = int(X1 * INPUT_SCALE)
    scaled_x2 = int(X2 * INPUT_SCALE)
    scaled_y1 = int(Y1 * INPUT_SCALE) if Y1 is not None else 0
    scaled_y2 = int(Y2 * INPUT_SCALE) if Y2 is not None else H
    
    # Process frame
    edges = process_image(frame)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, 
                                         cv2.CHAIN_APPROX_SIMPLE)
    
    # Create visualization frame
    vis = frame.copy()
    
    if contours is not None and len(contours) > 0:
        if hierarchy is None:
            hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)
            
        # Find and process main circle
        main_hole, _ = detect_main_hole(contours, hierarchy)
        
        if main_hole is not None:
            center = center_of(main_hole)
            if center:
                # Scale center coordinates and radii
                center_x = int(1000 * INPUT_SCALE)
                center_y = int(500 * INPUT_SCALE)
                scaled_target = int(TARGET_RADIUS * INPUT_SCALE)
                scaled_inner = int(INNER_RADIUS * INPUT_SCALE)
                scaled_outer = int(OUTER_RADIUS * INPUT_SCALE)
                
                # Draw circles
                cv2.drawContours(vis, [main_hole], -1, (0, 255, 0), 2)
                cv2.circle(vis, center, 5, (0, 0, 255), -1)
                cv2.circle(vis, (center_x, center_y), scaled_target, (0, 0, 255), 2)
                cv2.circle(vis, (center_x, center_y), scaled_inner, (0, 0, 255), 2)
                cv2.circle(vis, (center_x, center_y), scaled_outer, (0, 0, 255), 2)
                
                # Detect holes
                holes = detect_holes(contours, hierarchy, 
                                   center_x, center_y,
                                   scaled_inner, scaled_outer)
                
                # Draw holes and centers
                for hole in holes:
                    cv2.drawContours(vis, [hole], -1, (255, 0, 0), 2)
                    hole_center = center_of(hole)
                    if hole_center:
                        x, y = hole_center
                        if (scaled_x1 <= x <= scaled_x2 and 
                            scaled_y1 <= y <= scaled_y2):
                            cv2.circle(vis, (x, y), 3, (0, 255, 255), -1)
    
    # Draw ROI rectangle
    cv2.rectangle(vis, (scaled_x1, scaled_y1), (scaled_x2, scaled_y2), 
                 (0, 255, 255), 2)
    
    return vis

def main():
    # Initialize webcam
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, FPS_TARGET)
    
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