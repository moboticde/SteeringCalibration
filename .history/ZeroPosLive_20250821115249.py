import math
import cv2
import numpy as np
import time
import matplotlib.pyplot as plt

# ------------------- CONFIG -------------------
CAMERA_ID = 0
FPS_TARGET = 30
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
INPUT_SCALE = 1.0
DISPLAY_SCALE = 1.0

# ROI limits
X1, X2 = 100, 1300
Y1, Y2 = None, None

# Detection parameters
MIN_AREA = 10
R_MIN, R_MAX = 10, 100
CIRC_MIN = 0.4
INNER_RADIUS = 315
OUTER_RADIUS = 440

# Main circle parameters
MIN_AREA_MAIN = 1000
TARGET_RADIUS_MAIN = 100
RADIUS_TOLERANCE_MAIN = 20
CIRC_MIN_MAIN = 0.25

# Lines
VERTICAL_ANGLE_TOLERANCE = 10
MIN_LINE_LENGTH = 220
LINE_THICKNESS = 3
ANGLE_EPS = 0.5  # stickiness band in degrees

# ---- ROI modes ----
ROI_MODE = "auto_circle"   # "manual_base", "relative", or "auto_circle"
ROI_MARGIN = 30            # px around the outer circle (for auto_circle)

# If ROI_MODE == "manual_base": interpret X1..Y2 in BASE_W×BASE_H space
BASE_W, BASE_H = 1920, 1080

# If ROI_MODE == "relative": use these fractions [0..1]
X1_REL, X2_REL = 0.05, 0.95
Y1_REL, Y2_REL = 0.00, 1.00

DEBUG_DRAW_ALL_CONTOURS = True

# ------------------- HELPERS -------------------

def center_of(cnt):
    M = cv2.moments(cnt)
    if M["m00"] == 0:
        return None
    return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))


def process_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(blurred, kernel, iterations=2)
    eroded = cv2.erode(dilated, kernel, iterations=1)
    edges = cv2.Canny(eroded, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return eroded, edges


# ------------------- LINES -------------------

def detect_lines(edges, angle_tolerance=10, max_tilt=90):
    """
    Detect lines fully inside the OUTER circle.
    Returns:
        lines_info: list of (x1, y1, x2, y2, ang_x_deg)  # angle to x-axis
        best_ang_x: float or None                        # ang_x of the longest line
    """
    H, W = edges.shape[:2]
    cx, cy = W // 2, H // 2

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
    best_ang_x = None
    best_len = -1.0

    if raw is not None:
        for x1, y1, x2, y2 in raw.reshape(-1, 4):
            if not (in_circle(x1, y1) and in_circle(x2, y2)):
                continue
            ang_x = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            seg_len = math.hypot(x2 - x1, y2 - y1)
            lines_info.append((x1, y1, x2, y2, ang_x))
            if seg_len > best_len:
                best_len = seg_len
                best_ang_x = ang_x

    return lines_info, best_ang_x


# ------------------- HOLES -------------------

def detect_main_hole(contours, hierarchy, roi_bounds):
    """Detect main hole within ROI bounds"""
    x1, y1, x2, y2 = roi_bounds
    main_hole = None
    max_circularity = 0
    
    for i, cnt in enumerate(contours):
        if hierarchy[0][i][3] != -1:  # keep only parents (root)
            continue
            
        # Check if contour center is within ROI
        cnt_center = center_of(cnt)
        if cnt_center is None:
            continue
        cx, cy = cnt_center
        if not (x1 <= cx <= x2 and y1 <= cy <= y2):
            continue
            
        area = cv2.contourArea(cnt)
        if area < MIN_AREA_MAIN:
            continue
        (_, r) = cv2.minEnclosingCircle(cnt)
        r = float(r)
        peri = cv2.arcLength(cnt, True)
        circularity = 4 * np.pi * area / (peri * peri + 1e-6)
        if (circularity >= CIRC_MIN_MAIN and r <= TARGET_RADIUS_MAIN):
            if circularity > max_circularity:
                max_circularity = circularity
                main_hole = cnt
    return main_hole, max_circularity


def detect_holes(contours, hierarchy, center_x, center_y, inner_radius, outer_radius, roi_bounds):
    """Detect holes within ROI bounds"""
    x1, y1, x2, y2 = roi_bounds
    holes = []
    
    for i, cnt in enumerate(contours):
        if hierarchy[0][i][3] == -1:  # skip parents; keep children
            continue
            
        area = cv2.contourArea(cnt)
        if area < MIN_AREA:
            continue
            
        cnt_center = center_of(cnt)
        if cnt_center is None:
            continue
            
        # Check if hole is within ROI
        hx, hy = cnt_center
        if not (x1 <= hx <= x2 and y1 <= hy <= y2):
            continue
            
        dx = hx - center_x
        dy = hy - center_y
        distance = math.hypot(dx, dy)
        if not (inner_radius <= distance <= outer_radius):
            continue
            
        (_, r) = cv2.minEnclosingCircle(cnt)
        peri = cv2.arcLength(cnt, True)
        circularity = 4 * np.pi * cv2.contourArea(cnt) / (peri * peri + 1e-6)
        if (R_MIN <= r <= R_MAX and circularity >= CIRC_MIN):
            holes.append(cnt)
    return holes


# ------------------- FRAME PIPELINE -------------------

def process_frame(frame):
    frame = cv2.resize(frame, None, fx=INPUT_SCALE, fy=INPUT_SCALE, interpolation=cv2.INTER_AREA)
    H, W = frame.shape[:2]

    eroded, edges = process_image(frame)

    vis = frame.copy()
    vis = cv2.cvtColor(eroded, cv2.COLOR_GRAY2BGR)
    
    # Get ROI bounds first
    def get_roi():
        center_x, center_y = int(W / 2), int(H / 2)
        scale_factor = CAMERA_WIDTH / 1920
        scaled_outer = int(OUTER_RADIUS * scale_factor)
        
        if ROI_MODE == "auto_circle":
            x1 = max(0, center_x - scaled_outer - ROI_MARGIN)
            x2 = min(W - 1, center_x + scaled_outer + ROI_MARGIN)
            y1 = max(0, center_y - scaled_outer - ROI_MARGIN)
            y2 = min(H - 1, center_y + scaled_outer + ROI_MARGIN)
            return x1, y1, x2, y2

        elif ROI_MODE == "relative":
            x1 = int(X1_REL * W); x2 = int(X2_REL * W)
            y1 = int(Y1_REL * H); y2 = int(Y2_REL * H)
            return x1, y1, x2, y2

        else:  # "manual_base" - scale your X1..Y2 from BASE_W×BASE_H into current frame
            _x1 = 0 if X1 is None else X1
            _x2 = W if X2 is None else X2
            _y1 = 0 if Y1 is None else Y1
            _y2 = H if Y2 is None else Y2
            x1 = int(_x1 * W / BASE_W)
            x2 = int(_x2 * W / BASE_W)
            y1 = int(_y1 * H / BASE_H)
            y2 = int(_y2 * H / BASE_H)
            # clamp
            x1 = max(0, min(x1, W-1)); x2 = max(0, min(x2, W-1))
            y1 = max(0, min(y1, H-1)); y2 = max(0, min(y2, H-1))
            return x1, y1, x2, y2

    roi_bounds = get_roi()
    scaled_x1, scaled_y1, scaled_x2, scaled_y2 = roi_bounds
    
    # Lines inside circle (returns ang_x); we convert to vertical tilt
    lines_info, _ = detect_lines(edges, angle_tolerance=VERTICAL_ANGLE_TOLERANCE)

    # Pick stable line with ±ANGLE_EPS stickiness
    prev_tilt = getattr(process_frame, "prev_tilt", None)
    selected = None
    if lines_info:
        info = []  # (length, vtilt, x1,y1,x2,y2)
        for (x1, y1, x2, y2, ang_x) in lines_info:
            vtilt = abs(90.0 - float(ang_x))
            length = math.hypot(x2 - x1, y2 - y1)
            info.append((length, vtilt, x1, y1, x2, y2))
        if prev_tilt is not None:
            close = [t for t in info if abs(t[1] - prev_tilt) <= ANGLE_EPS]
            selected = max(close, key=lambda t: t[0]) if close else max(info, key=lambda t: t[0])
        else:
            selected = max(info, key=lambda t: t[0])

    best_tilt = None
    if selected is not None:
        length, tilt, x1, y1, x2, y2 = selected
        best_tilt = tilt
        cv2.line(vis, (x1, y1), (x2, y2), (0, 255, 255), LINE_THICKNESS)
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.putText(vis, f"{tilt:.2f}", (mx + 6, my - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # remember last tilt (for stickiness next frame)
    process_frame.prev_tilt = best_tilt if best_tilt is not None else prev_tilt

    # --- Visual references ---
    center_x, center_y = int(W / 2), int(H / 2)
    scale_factor = CAMERA_WIDTH / 1920
    scaled_inner = int(INNER_RADIUS * scale_factor)
    scaled_outer = int(OUTER_RADIUS * scale_factor)
    cv2.circle(vis, (center_x, center_y), scaled_inner, (0, 0, 255), 2)
    cv2.circle(vis, (center_x, center_y), scaled_outer, (0, 0, 255), 2)

    # Draw ROI rectangle
    cv2.rectangle(vis, (scaled_x1, scaled_y1), (scaled_x2, scaled_y2), (0, 255, 255), 2)

    # --- Holes with ROI constraint ---
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if contours is not None and len(contours) > 0:
        if hierarchy is None:
            hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)
            
        # Detect main hole within ROI
        main_hole, _ = detect_main_hole(contours, hierarchy, roi_bounds)
        if main_hole is not None:
            center = center_of(main_hole)
            if center:
                cv2.drawContours(vis, [main_hole], -1, (0, 255, 0), 2)
                cv2.circle(vis, center, 5, (0, 0, 255), -1)
                
                # Detect other holes within ROI
                holes = detect_holes(contours, hierarchy, center_x, center_y, scaled_inner, scaled_outer, roi_bounds)
                for hole in holes:
                    cv2.drawContours(vis, [hole], -1, (255, 0, 0), 2)
                    hc = center_of(hole)
                    if hc:
                        cv2.circle(vis, hc, 3, (0, 255, 255), -1)
                        
    if DEBUG_DRAW_ALL_CONTOURS and contours:
        cv2.drawContours(vis, contours, -1, (255, 0, 255), 1)  
        
    return vis, best_tilt


# ------------------- MAIN -------------------

def AngleDetection():
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS_TARGET)

    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera resolution: {actual_width}x{actual_height}")

    cv2.namedWindow('Zero Position', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Zero Position', CAMERA_WIDTH, CAMERA_HEIGHT)

    print("Press 'q' to quit")

    while True:
        start_time = time.time()
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break

        result, tilt = process_frame(frame)

        if DISPLAY_SCALE != 1.0:
            result = cv2.resize(result, None, fx=DISPLAY_SCALE, fy=DISPLAY_SCALE, interpolation=cv2.INTER_AREA)

        fps = 1.0 / (time.time() - start_time + 1e-6)
        text = f"FPS: {fps:.1f}" + (f" | Tilt: {tilt:.1f}" if tilt is not None else "")
        cv2.putText(result, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('Zero Position', result)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    
if __name__ == "__main__":
    AngleDetection()