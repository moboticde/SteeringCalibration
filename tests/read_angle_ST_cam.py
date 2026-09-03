import math
import cv2
import numpy as np
import time
import matplotlib.pyplot as plt
from collections import deque

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
R_MIN, R_MAX = 5, 100
CIRC_MIN = 0.6
INNER_RADIUS = 225
OUTER_RADIUS = 300

# Main circle parameters
MIN_AREA_MAIN = 1000
TARGET_RADIUS_MAIN = 430
CIRC_MIN_MAIN = 0.25

# Lines
VERTICAL_ANGLE_TOLERANCE = 10
LINE_THICKNESS = 3
ANGLE_EPS = 0.5  # stickiness band in degrees

# ---- NEW: angle history (replaces LINE_TILT_HISTORY) ----
ANGLE_HISTORY = deque(maxlen=30)

# ---- ROI modes ----
ROI_MODE = "auto_circle"   # "manual_base", "relative", or "auto_circle"
ROI_MARGIN = 30            # px around the outer circle (for auto_circle)

# If ROI_MODE == "manual_base": interpret X1..Y2 in BASE_W×BASE_H space
BASE_W, BASE_H = 1920, 1080

# If ROI_MODE == "relative": use these fractions [0..1]
X1_REL, X2_REL = 0.05, 0.95
Y1_REL, Y2_REL = 0.00, 1.00

DEBUG_DRAW_ALL_CONTOURS = True

# ---- Ruler overlay config ----
RULER_BAND = 26          # thickness of top/left ruler bands in px
RULER_MAJOR = 100        # major tick every N px
RULER_MINOR = 10         # minor tick every N px

# mouse state (updated by callback on the displayed window)
MOUSE_POS = (-1, -1)

# --- origin + ruler units ---
ORIGIN_CENTER = True        # keep (0,0) in center
Y_AXIS_UP = True            # up is +Y (set False for image-style down=+Y)
RULER_IN_BASE_UNITS = True  # <-- show labels in base units (1920×1080)
RULER_MAJOR_UNITS = 100     # major tick every 100 base units
RULER_MINOR_UNITS = 10      # minor tick every 10 base units

# Origin offset in base units (where base (-50, 10) becomes display zero)
ORIGIN_OFFSET_X_BASE = 50
ORIGIN_OFFSET_Y_BASE = 16
ORIGIN_OFFSET_X_PIXEL = ORIGIN_OFFSET_X_BASE * (CAMERA_WIDTH / BASE_W)
ORIGIN_OFFSET_Y_PIXEL = ORIGIN_OFFSET_Y_BASE * (CAMERA_HEIGHT / BASE_H)


# ------------------- HELPERS -------------------

def on_mouse(event, x, y, flags, userdata):
    """Tracks the mouse position over the displayed window."""
    global MOUSE_POS
    if event == cv2.EVENT_MOUSEMOVE:
        MOUSE_POS = (x, y)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def center_of(cnt):
    M = cv2.moments(cnt)
    if M["m00"] == 0:
        return None
    return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

def process_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(blurred, kernel, iterations=1) # save this
    eroded = cv2.erode(dilated, kernel, iterations=3) # save this
    edges = cv2.Canny(eroded, 200, 300)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return eroded, edges

# ------------------- RULER + CURSOR OVERLAYS -------------------

def draw_rulers(img, band=RULER_BAND, major=RULER_MAJOR, minor=RULER_MINOR):
    """
    Draw top/left ruler bands.
    If RULER_IN_BASE_UNITS=True, ticks/labels are in BASE_W/BASE_H units (your code units),
    mapped to the current display via CAMERA_* and DISPLAY_SCALE.
    """
    if band <= 0:
        return img
    h, w = img.shape[:2]
    cx = int(w // 2 - ORIGIN_OFFSET_X_PIXEL)
    cy = int(h // 2 - ORIGIN_OFFSET_Y_PIXEL)

    # dark bands
    cv2.rectangle(img, (0, 0), (w, band), (40, 40, 40), -1)   # top
    cv2.rectangle(img, (0, 0), (band, h), (40, 40, 40), -1)   # left

    if not RULER_IN_BASE_UNITS:
        # original pixel-based ticks (from image edges)
        for x in range(0, w, RULER_MINOR):
            if x % RULER_MAJOR == 0:
                tlen, thick, col = band - 2, 2, (210, 210, 210)
            elif x % (RULER_MAJOR // 2) == 0:
                tlen, thick, col = band // 2 + 4, 1, (180, 180, 180)
            else:
                tlen, thick, col = band // 3, 1, (160, 160, 160)
            cv2.line(img, (x, band), (x, band - tlen), col, thick)
            if x % RULER_MAJOR == 0:
                cv2.putText(img, f"{x - (cx if ORIGIN_CENTER else 0)}",
                            (x + 2, band - 6),
                            cv2.FONT_HERSHEY_PLAIN, 1.0, (230, 230, 230), 1, cv2.LINE_AA)

        for y in range(0, h, RULER_MINOR):
            if y % RULER_MAJOR == 0:
                tlen, thick, col = band - 2, 2, (210, 210, 210)
            elif y % (RULER_MAJOR // 2) == 0:
                tlen, thick, col = band // 2 + 4, 1, (180, 180, 180)
            else:
                tlen, thick, col = band // 3, 1, (160, 160, 160)
            cv2.line(img, (band, y), (band - tlen, y), col, thick)
            if y % RULER_MAJOR == 0:
                val = (cy - y) if (ORIGIN_CENTER and Y_AXIS_UP) else ((y - cy) if ORIGIN_CENTER else y)
                cv2.putText(img, f"{val}", (4, y - 4 if y - 4 > 10 else y + 12),
                            cv2.FONT_HERSHEY_PLAIN, 1.0, (230, 230, 230), 1, cv2.LINE_AA)
        # center markers
        if ORIGIN_CENTER:
            cv2.line(img, (cx, band), (cx, 0), (255, 255, 255), 1)
            cv2.line(img, (band, cy), (0, cy), (255, 255, 255), 1)
        return img

    # -------- Base-units ruler --------
    # mapping: base -> display pixels
    scale_x = (CAMERA_WIDTH  / float(BASE_W)) * DISPLAY_SCALE
    scale_y = (CAMERA_HEIGHT / float(BASE_H)) * DISPLAY_SCALE
    if scale_x <= 1e-9 or scale_y <= 1e-9:
        return img

    # visible base ranges
    if ORIGIN_CENTER:
        min_base_x = -(cx) / scale_x
        max_base_x =  (w - cx) / scale_x
        min_base_y = -(cy) / scale_y
        max_base_y =  (h - cy) / scale_y
    else:
        min_base_x, max_base_x = 0.0, w / scale_x
        min_base_y, max_base_y = 0.0, h / scale_y

    # tick steps (in base units)
    maj_x = float(RULER_MAJOR_UNITS)
    min_x = float(RULER_MINOR_UNITS)
    maj_y = float(RULER_MAJOR_UNITS)
    min_y = float(RULER_MINOR_UNITS)

    def start_at(minv, step):
        return math.ceil(minv / step) * step

    # --- top (x) ---
    x_base = start_at(min_base_x, min_x)
    while x_base <= max_base_x + 1e-6:
        x_disp = int(round((cx if ORIGIN_CENTER else 0) + x_base * scale_x))
        if abs((x_base / maj_x) - round(x_base / maj_x)) < 1e-6:
            tlen, thick, col = band - 2, 2, (210, 210, 210); do_label = True
        elif abs((x_base / (maj_x / 2.0)) - round(x_base / (maj_x / 2.0))) < 1e-6:
            tlen, thick, col = band // 2 + 4, 1, (180, 180, 180); do_label = False
        else:
            tlen, thick, col = band // 3, 1, (160, 160, 160); do_label = False
        cv2.line(img, (x_disp, band), (x_disp, band - tlen), col, thick)
        if do_label:
            cv2.putText(img, f"{int(round(x_base))}", (x_disp + 2, band - 6),
                        cv2.FONT_HERSHEY_PLAIN, 1.0, (230, 230, 230), 1, cv2.LINE_AA)
        x_base += min_x

    # --- left (y) ---
    y_base = start_at(min_base_y, min_y)
    while y_base <= max_base_y + 1e-6:
        y_disp = int(round((cy if ORIGIN_CENTER else 0) + (-y_base if Y_AXIS_UP else y_base) * scale_y))
        if abs((y_base / maj_y) - round(y_base / maj_y)) < 1e-6:
            tlen, thick, col = band - 2, 2, (210, 210, 210); do_label = True
        elif abs((y_base / (maj_y / 2.0)) - round(y_base / (maj_y / 2.0))) < 1e-6:
            tlen, thick, col = band // 2 + 4, 1, (180, 180, 180); do_label = False
        else:
            tlen, thick, col = band // 3, 1, (160, 160, 160); do_label = False
        cv2.line(img, (band, y_disp), (band - tlen, y_disp), col, thick)
        if do_label:
            cv2.putText(img, f"{int(round(y_base))}",
                        (4, y_disp - 4 if y_disp - 4 > 10 else y_disp + 12),
                        cv2.FONT_HERSHEY_PLAIN, 1.0, (230, 230, 230), 1, cv2.LINE_AA)
        y_base += min_y

    if ORIGIN_CENTER:
        cv2.line(img, (cx, band), (cx, 0), (255, 255, 255), 1)
        cv2.line(img, (band, cy), (0, cy), (255, 255, 255), 1)
    return img


def draw_cursor_overlay(img, mouse_xy, disp_scale, in_scale):
    """Crosshair + coordinate bubble with base-unit readout."""
    if mouse_xy is None:
        return img
    h, w = img.shape[:2]
    x_disp, y_disp = mouse_xy
    if x_disp < 0 or y_disp < 0 or x_disp >= w or y_disp >= h:
        return img

    cx = int(w // 2 - ORIGIN_OFFSET_X_PIXEL)
    cy = int(h // 2 - ORIGIN_OFFSET_Y_PIXEL)

    # crosshair
    cv2.line(img, (x_disp, 0), (x_disp, h - 1), (0, 255, 0), 1, cv2.LINE_AA)
    cv2.line(img, (0, y_disp), (w - 1, y_disp), (0, 255, 0), 1, cv2.LINE_AA)
    cv2.circle(img, (x_disp, y_disp), 3, (0, 255, 0), -1, cv2.LINE_AA)

    # display-centered pixels
    x0_disp = x_disp - cx if ORIGIN_CENTER else x_disp
    y0_disp = (cy - y_disp) if (ORIGIN_CENTER and Y_AXIS_UP) else ((y_disp - cy) if ORIGIN_CENTER else y_disp)

    # base-units mapping
    scale_x = (CAMERA_WIDTH  / float(BASE_W)) * DISPLAY_SCALE
    scale_y = (CAMERA_HEIGHT / float(BASE_H)) * DISPLAY_SCALE
    x0_base = x0_disp / max(scale_x, 1e-9)
    y0_base = y0_disp / max(scale_y, 1e-9)

    label = f"base:({int(round(x0_base))},{int(round(y0_base))})  disp:({x_disp},{y_disp})"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    bx = max(0, min(x_disp + 10, w - tw - 12))
    by = max(th + 8, min(y_disp - 10, h))
    cv2.rectangle(img, (bx - 4, by - th - 6), (bx + tw + 4, by + 4), (20, 20, 20), -1)
    cv2.putText(img, label, (bx, by - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1, cv2.LINE_AA)
    return img


# ------------------- NEW: Angle helpers -------------------

def angle_cw_from_segment(x1, y1, x2, y2, cx, cy):
    """
    Angle in [0,360): clockwise from +Y (12 o'clock),
    using the endpoint farther from center as the ray tip.
    """
    d1 = (x1 - cx) ** 2 + (y1 - cy) ** 2
    d2 = (x2 - cx) ** 2 + (y2 - cy) ** 2
    xf, yf = (x2, y2) if d2 > d1 else (x1, y1)

    vx = xf - cx
    vy = cy - yf          # image Y↓ -> math Y↑
    ang = (math.degrees(math.atan2(vx, vy)) + 360.0) % 360.0
    return ang

def ang_diff(a, b):
    """Smallest absolute difference between two angles (deg)."""
    return abs((a - b + 180.0) % 360.0 - 180.0)

def circular_mean(angles_deg):
    """Mean direction of angles (deg) on the circle."""
    if not angles_deg:
        return None
    s = sum(math.sin(math.radians(a)) for a in angles_deg)
    c = sum(math.cos(math.radians(a)) for a in angles_deg)
    if abs(s) < 1e-12 and abs(c) < 1e-12:
        return None
    return (math.degrees(math.atan2(s, c)) + 360.0) % 360.0

def record_angle_and_get_avg(angle_deg):
    """Record angle (deg) and return circular mean of the last N."""
    if angle_deg is not None and 0.0 <= angle_deg < 360.0:
        ANGLE_HISTORY.append(float(angle_deg))
    return circular_mean(list(ANGLE_HISTORY)) if ANGLE_HISTORY else None

def clear_angle_history():
    ANGLE_HISTORY.clear()


# ------------------- LINES -------------------

def detect_lines(edges, angle_tolerance=10, max_tilt=90):
    """
    Detect lines fully inside the OUTER circle.
    Returns:
        lines_info: list of (x1, y1, x2, y2, ang_x_deg)  # angle to x-axis
        best_ang_x: float or None                        # ang_x of the longest line
    """
    H, W = edges.shape[:2]
    cx = int(W // 2 - ORIGIN_OFFSET_X_PIXEL)
    cy = int(H // 2 - ORIGIN_OFFSET_Y_PIXEL)

    scale_factor = CAMERA_WIDTH / 1920.0
    R = int(OUTER_RADIUS * scale_factor)

    raw = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi/360, threshold=10,
        minLineLength=80, maxLineGap=None
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
# ------------------- FRAME PIPELINE -------------------

def process_frame(frame, visualize=False):
    frame = cv2.resize(frame, None, fx=INPUT_SCALE, fy=INPUT_SCALE, interpolation=cv2.INTER_AREA)
    H, W = frame.shape[:2]

    eroded, edges = process_image(frame)
    vis = cv2.cvtColor(eroded, cv2.COLOR_GRAY2BGR) if visualize else None

    # ROI bounds
    def get_roi():
        center_x = int(W / 2 - ORIGIN_OFFSET_X_PIXEL)
        center_y = int(H / 2 - ORIGIN_OFFSET_Y_PIXEL)
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

        else:  # "manual_base"
            _x1 = 0 if X1 is None else X1
            _x2 = W if X2 is None else X2
            _y1 = 0 if Y1 is None else Y1
            _y2 = H if Y2 is None else Y2
            x1 = int(_x1 * W / BASE_W)
            x2 = int(_x2 * W / BASE_W)
            y1 = int(_y1 * H / BASE_H)
            y2 = int(_y2 * H / BASE_H)
            x1 = max(0, min(x1, W-1)); x2 = max(0, min(x2, W-1))
            y1 = max(0, min(y1, H-1)); y2 = max(0, min(y2, H-1))
            return x1, y1, x2, y2

    roi_bounds = get_roi()
    scaled_x1, scaled_y1, scaled_x2, scaled_y2 = roi_bounds

    # Center + circles (aligned to origin offset)
    center_x = int(W / 2 - ORIGIN_OFFSET_X_PIXEL)
    center_y = int(H / 2 - ORIGIN_OFFSET_Y_PIXEL)
    scale_factor = CAMERA_WIDTH / 1920
    scaled_inner = int(INNER_RADIUS * scale_factor)
    scaled_outer = int(OUTER_RADIUS * scale_factor)

    # Lines inside circle
    lines_info, _ = detect_lines(edges, angle_tolerance=VERTICAL_ANGLE_TOLERANCE)

    prev_angle = getattr(process_frame, "prev_angle", None)
    selected = None
    best_angle = None

    if lines_info:
        # Build candidates: (length, angleCW, x1,y1,x2,y2)
        cand = []
        for (x1, y1, x2, y2, _ang_x_unused) in lines_info:
            length = math.hypot(x2 - x1, y2 - y1)
            angleCW = angle_cw_from_segment(x1, y1, x2, y2, center_x, center_y)
            cand.append((length, angleCW, x1, y1, x2, y2))

        if prev_angle is not None:
            close = [t for t in cand if ang_diff(t[1], prev_angle) <= ANGLE_EPS]
            selected = max(close, key=lambda t: t[0]) if close else max(cand, key=lambda t: t[0])
        else:
            selected = max(cand, key=lambda t: t[0])

    if selected is not None:
        length, angleCW, x1, y1, x2, y2 = selected
        best_angle = angleCW
        if visualize and vis is not None:
            cv2.line(vis, (x1, y1), (x2, y2), (165, 42, 42), LINE_THICKNESS)
            # Label near farther endpoint (pointer tip)
            d1 = (x1 - center_x)**2 + (y1 - center_y)**2
            d2 = (x2 - center_x)**2 + (y2 - center_y)**2
            lx, ly = (x2, y2) if d2 > d1 else (x1, y1)
            cv2.putText(vis, f"{angleCW:6.2f}", (lx + 6, ly - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (165, 42, 42), 2)

    # remember across frames (wrap-safe)
    process_frame.prev_angle = best_angle if best_angle is not None else prev_angle

    if visualize and vis is not None:
        # Visual references
        cv2.circle(vis, (center_x, center_y), scaled_inner, (0, 0, 255), 2)
        cv2.circle(vis, (center_x, center_y), scaled_outer, (0, 0, 255), 2)
        # Draw ROI rectangle
        cv2.rectangle(vis, (scaled_x1, scaled_y1), (scaled_x2, scaled_y2), (0, 255, 255), 2)

        # Holes (only for debug visuals)
        contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if contours is not None and len(contours) > 0:
            if hierarchy is None:
                hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)
            main_hole, _ = detect_main_hole(contours, hierarchy, roi_bounds)
            if main_hole is not None:
                center = center_of(main_hole)
                if center:
                    cv2.drawContours(vis, [main_hole], -1, (0, 255, 0), 2)
                    cv2.circle(vis, center, 5, (0, 0, 255), -1)
                    holes = detect_holes(contours, hierarchy, center_x, center_y, scaled_inner, scaled_outer, roi_bounds)
                    for hole in holes:
                        cv2.drawContours(vis, [hole], -1, (255, 0, 0), 2)
                        hc = center_of(hole)
                        if hc:
                            cv2.circle(vis, hc, 3, (0, 255, 255), -1)

        if DEBUG_DRAW_ALL_CONTOURS and contours is not None and len(contours) > 0:
            cv2.drawContours(vis, contours, -1, (255, 0, 255), 1)  

    return vis, best_angle


# ------------------- MAIN -------------------

def AngleDetection(debug=False, return_after=10, timeout_s=None, cap=None):
    """
    Two modes:
      - debug=True  → visual mode with window, rulers, cursor, live HUD; quit with 'q'
      - debug=False → headless mode, returns avg angle after `return_after` samples or `timeout_s`
    """
    global MOUSE_POS
    RULER_ENABLED = debug
    start_all = time.time()
    last_avg = None

    owns_cap = cap is None
    if owns_cap:
        cap = cv2.VideoCapture(CAMERA_ID,cv2.CAP_V4L2)
        if not cap.isOpened():
            print("Error: Could not open webcam")
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, FPS_TARGET)

        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if debug:
            print(f"Camera resolution: {actual_width}x{actual_height}")

    if debug:
        timeout_s = None  # no hard stop in debug
        window_name = 'Zero Position'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, CAMERA_WIDTH, CAMERA_HEIGHT)
        cv2.setMouseCallback(window_name, on_mouse, None)
        print("Press 'q' to quit | 'r' to reset average buffer")

    while True:
        # headless timeout
        if (not debug) and (timeout_s is not None) and ((time.time() - start_all) >= timeout_s):
            break

        start_time = time.time()
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break

        vis, angleCW = process_frame(frame, visualize=debug)
        avg_angle = record_angle_and_get_avg(angleCW)
        if avg_angle is not None:
            last_avg = avg_angle

        # headless early exit once enough samples collected
        if (not debug) and (return_after is not None) and (len(ANGLE_HISTORY) >= return_after):
            break

        if debug:
            result = vis if vis is not None else cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if DISPLAY_SCALE != 1.0:
                result = cv2.resize(result, None, fx=DISPLAY_SCALE, fy=DISPLAY_SCALE, interpolation=cv2.INTER_AREA)
            # Ruler overlay
            if RULER_ENABLED:
                draw_rulers(result, band=RULER_BAND, major=RULER_MAJOR, minor=RULER_MINOR)
            # Cursor overlay
            if MOUSE_POS is not None:
                draw_cursor_overlay(result, MOUSE_POS, disp_scale=DISPLAY_SCALE, in_scale=INPUT_SCALE)

            fps = 1.0 / (time.time() - start_time + 1e-6)
            parts = [f"FPS: {fps:.1f}"]
            if angleCW is not None:
                parts.append(f"Angle: {angleCW:.1f}")
            if avg_angle is not None:
                parts.append(f"Avg30: {avg_angle:.1f}")
            text = " | ".join(parts)

            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            H, W = result.shape[:2]
            cv2.putText(result, text, (W - tw - 10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            cv2.imshow(window_name, result)
            k = cv2.waitKey(1) & 0xFF
            if k == ord('q'):
                break
            elif k == ord('r'):
                clear_angle_history()
                last_avg = None

    if owns_cap:
        cap.release()
    if debug:
        cv2.destroyAllWindows()
    return last_avg

if __name__ == "__main__":
    # Example runs:
    # 1) Headless: grab 10 samples and return their circular mean
    avgAngle = AngleDetection(debug=True, return_after=10, timeout_s=None)
    print(f"Angle: {avgAngle}")

    # 2) Visual debug (press 'q' to quit)
    # avgAngle = AngleDetection(debug=True)

