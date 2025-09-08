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
MIN_AREA = 100  # Increased from 2
R_MIN, R_MAX = 10, 100
CIRC_MIN = 0.3  # Relaxed from 0.5
ROUND_RANGE = (0.6, 2.0)
MIN_ARC_PERCENT = 0.5
TARGET_RADIUS = 75
INNER_RADIUS = 310
OUTER_RADIUS = 420

# Main circle parameters
MIN_AREA_MAIN = 5000  # Increased from 1000
TARGET_RADIUS_MAIN = 220  # Adjusted for 1280x720 resolution
RADIUS_TOLERANCE_MAIN = 30
CIRC_MIN_MAIN = 0.3  # Relaxed from 0.2

# Vertical lines parameters
VERTICAL_ANGLE_TOLERANCE = 10
MIN_LINE_LENGTH = 200

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
    edges = cv2.Canny(eroded, 40, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return edges



def detect_lines(edges, angle_tolerance=10,max_tilt=90):
    """
    Detect lines fully inside the OUTER circle and return both
    the kept lines and the best (min) tilt from vertical.

    Returns:
        lines_info: list of (x1, y1, x2, y2, tilt_deg)
        best_tilt: float or None
    """
    H, W = edges.shape[:2]
    cx, cy = W // 2, H // 2

    # Match the scaling used for the red reference circle
    scale_factor = CAMERA_WIDTH / 1920.0
    R = int(OUTER_RADIUS * scale_factor)

    raw = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=100,
        minLineLength=MIN_LINE_LENGTH, maxLineGap=20
    )

    def in_circle(x, y):
        dx, dy = x - cx, y - cy
        return dx * dx + dy * dy <= R * R

    lines_info = []
    best_tilt = None
    best_len = -1.0

    if raw is not None:
        for x1, y1, x2, y2 in raw.reshape(-1, 4):
            # keep only if BOTH endpoints are inside the outer circle
            if not (in_circle(x1, y1) and in_circle(x2, y2)):
                continue

            # angle vs x-axis -> tilt from vertical
            ang_x = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))  # 0..180 to x-axis
            #tilt = abs(90.0 - ang_x)  # 0 = perfectly vertical

            seg_len = np.hypot(x2 - x1, y2 - y1)

            lines_info.append((x1, y1, x2, y2, ang_x))
            if seg_len > best_len:
                best_len = seg_len
                best_tilt = ang_x

    return lines_info, best_tilt


def detect_main_hole(contours, hierarchy):
    main_hole = None
    max_circularity = 0
    
    for i, cnt in enumerate(contours):
        # Look for parent contours (changed from child)
        if hierarchy[0][i][3] != -1:  # This is correct for parent contours
            continue
            
        area = cv2.contourArea(cnt)
        if area < MIN_AREA_MAIN:
            continue
            
        (cxcy, r) = cv2.minEnclosingCircle(cnt)
        r = float(r)
        
        # Calculate circularity
        peri = cv2.arcLength(cnt, True)
        circularity = 4 * np.pi * area / (peri * peri + 1e-6)
        
        # Check for main circle with adjusted parameters
        if (circularity >= CIRC_MIN_MAIN and 
            abs(r - TARGET_RADIUS_MAIN) <= RADIUS_TOLERANCE_MAIN):
            if circularity > max_circularity:
                max_circularity = circularity
                main_hole = cnt
    
    return main_hole, max_circularity

# Update detect_holes function
def detect_holes(contours, hierarchy, center_x, center_y, inner_radius, outer_radius):
    holes = []
    
    for i, cnt in enumerate(contours):
        # Look for child contours (changed condition)
        if hierarchy[0][i][3] == -1:  # Changed from != to ==
            continue
            
        area = cv2.contourArea(cnt)
        if area < MIN_AREA:
            continue

        # Get the center
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

        (cxcy, r) = cv2.minEnclosingCircle(cnt)
        r = float(r)
        
        # Calculate shape metrics
        peri = cv2.arcLength(cnt, True)  # Changed from False to True
        circularity = 4 * np.pi * area / (peri * peri + 1e-6)
        
        # Simplified hole detection criteria
        if (R_MIN <= r <= R_MAX and circularity >= CIRC_MIN):
            holes.append(cnt)
            
    return holes


def rescale_frame(frame, scale=0.75):
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
    
    # Process frame to get edges and contours
    edges = process_image(frame)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, 
                                         cv2.CHAIN_APPROX_SIMPLE)
    lines_info, best_tilt = detect_lines(edges, angle_tolerance=VERTICAL_ANGLE_TOLERANCE)
    # Create visualization frame
    vis = frame.copy()
    
    # Draw center circles with proper scaling
    center_x = int(W / 2)  # Center X of frame
    center_y = int(H / 2)  # Center Y of frame
    
    # Scale circle radii using same scale factor as ROI
    scale_factor = CAMERA_WIDTH / 1920  
    scaled_inner = int(INNER_RADIUS * scale_factor)
    scaled_outer = int(OUTER_RADIUS * scale_factor)
    
    # Draw both circles in red
    cv2.circle(vis, (center_x, center_y), scaled_inner, (0, 0, 255), 2)
    cv2.circle(vis, (center_x, center_y), scaled_outer, (0, 0, 255), 2)
    
    # Scale ROI coordinates
    scaled_x1 = int(X1 * INPUT_SCALE)
    scaled_x2 = int(X2 * INPUT_SCALE)
    scaled_y1 = int(Y1 * INPUT_SCALE) if Y1 is not None else 0
    scaled_y2 = int(Y2 * INPUT_SCALE) if Y2 is not None else H
    
    # Draw ROI rectangle
    cv2.rectangle(vis, (scaled_x1, scaled_y1), (scaled_x2, scaled_y2), 
                 (0, 255, 255), 2)
     # Draw kept lines + annotate their tilt
    for (x1, y1, x2, y2, tilt) in lines_info:
        cv2.line(vis, (x1, y1), (x2, y2), (0, 255, 255), 2)
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.putText(vis, f"{tilt:.1f}", (mx + 6, my - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    # Process contours if found
    if contours is not None and len(contours) > 0:
        if hierarchy is None:
            hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)
            
        # Find and process main circle
        main_hole, _ = detect_main_hole(contours, hierarchy)
        
        if main_hole is not None:
            center = center_of(main_hole)
            if center:
                # Draw main hole
                cv2.drawContours(vis, [main_hole], -1, (0, 255, 0), 2)
                cv2.circle(vis, center, 5, (0, 0, 255), -1)
                
                # Detect and draw holes
                holes = detect_holes(contours, hierarchy, 
                                   center_x, center_y,  # Use frame center
                                   scaled_inner, scaled_outer)
                
                for hole in holes:
                    cv2.drawContours(vis, [hole], -1, (255, 0, 0), 2)
                    hole_center = center_of(hole)
                    if hole_center:
                        x, y = hole_center
                        if (scaled_x1 <= x <= scaled_x2 and 
                            scaled_y1 <= y <= scaled_y2):
                            cv2.circle(vis, (x, y), 3, (0, 255, 255), -1)
    
    return vis, best_tilt

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
    cv2.namedWindow('Zero Position', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Zero Position', CAMERA_WIDTH, CAMERA_HEIGHT)


    print("Press 'q' to quit")
    
    while True:
        start_time = time.time()
        
        # Read frame
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        # Process frame
        result, tilt = process_frame(frame)

        if DISPLAY_SCALE != 1.0:
            result = cv2.resize(result, None, fx=DISPLAY_SCALE, fy=DISPLAY_SCALE, interpolation=cv2.INTER_AREA)

        fps = 1.0 / (time.time() - start_time + 1e-6)
        text = f"FPS: {fps:.1f}" + (f" | Tilt: {tilt:.1f}°" if tilt is not None else "")
        cv2.putText(result, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Show result
        cv2.imshow('Zero Position', result)

        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()