# Zero Position – fixed: stable single-line angle + bolt-hole detection
# Key fixes:
# - Corrected indentation in line-selection block
# - Safe handling when no lines are detected
# - Clear separation: ang_x (to x-axis) → vtilt (to vertical)
# - Minor cleanups; kept your geometry/holes logic intact

import math
import cv2
import numpy as np
import time

# ------------------- CONFIG -------------------
CAMERA_ID = 0
FPS_TARGET = 30
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
INPUT_SCALE = 1.0
DISPLAY_SCALE = 1.0

# ROI limits
X1, X2 = 500, 1500
Y1, Y2 = None, None

# Detection parameters
MIN_AREA = 100
R_MIN, R_MAX = 10, 100
CIRC_MIN = 0.3
ROUND_RANGE = (0.6, 2.0)
MIN_ARC_PERCENT = 0.5
TARGET_RADIUS = 75
INNER_RADIUS = 310
OUTER_RADIUS = 420

# Main circle parameters
MIN_AREA_MAIN = 5000
TARGET_RADIUS_MAIN = 220
RADIUS_TOLERANCE_MAIN = 30
CIRC_MIN_MAIN = 0.3

# Lines
VERTICAL_ANGLE_TOLERANCE = 10
MIN_LINE_LENGTH = 200
LINE_THICKNESS = 3
ANGLE_EPS = 0.5  # stickiness band in degrees

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
    edges = cv2.Canny(eroded, 40, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    return edges


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

def detect_main_hole(contours, hierarchy):
    main_hole = None
    max_circularity = 0
    for i, cnt in enumerate(contours):
        if hierarchy[0][i][3] != -1:  # keep only parents (root)
            continue
        area = cv2.contourArea(cnt)
        if area < MIN_AREA_MAIN:
            continue
        (_, r) = cv2.minEnclosingCircle(cnt)
        r = float(r)
        peri = cv2.arcLength(cnt, True)
        circularity = 4 * np.pi * area / (peri * peri + 1e-6)
        if (circularity >= CIRC_MIN_MAIN and abs(r - TARGET_RADIUS_MAIN) <= RADIUS_TOLERANCE_MAIN):
            if circularity > max_circularity:
                max_circularity = circularity
                main_hole = cnt
    return main_hole, max_circularity


def detect_holes(contours, hierarchy, center_x, center_y, inner_radius, outer_radius):
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
        dx = cnt_center[0] - center_x
        dy = cnt_center[1] - center_y
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

    edges = process_image(frame)
    vis = frame.copy()

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

    scaled_x1 = int(X1 * INPUT_SCALE)
    scaled_x2 = int(X2 * INPUT_SCALE)
    scaled_y1 = int(Y1 * INPUT_SCALE) if Y1 is not None else 0
    scaled_y2 = int(Y2 * INPUT_SCALE) if Y2 is not None else H
    cv2.rectangle(vis, (scaled_x1, scaled_y1), (scaled_x2, scaled_y2), (0, 255, 255), 2)

    # --- Holes (optional) ---
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if contours is not None and len(contours) > 0:
        if hierarchy is None:
            hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)
        main_hole, _ = detect_main_hole(contours, hierarchy)
        if main_hole is not None:
            center = center_of(main_hole)
            if center:
                cv2.drawContours(vis, [main_hole], -1, (0, 255, 0), 2)
                cv2.circle(vis, center, 5, (0, 0, 255), -1)
                holes = detect_holes(contours, hierarchy, center_x, center_y, scaled_inner, scaled_outer)
                for hole in holes:
                    cv2.drawContours(vis, [hole], -1, (255, 0, 0), 2)
                    hc = center_of(hole)
                    if hc:
                        x, y = hc
                        if (scaled_x1 <= x <= scaled_x2 and scaled_y1 <= y <= scaled_y2):
                            cv2.circle(vis, (x, y), 3, (0, 255, 255), -1)

    return vis, best_tilt


# ------------------- MAIN -------------------

def main():
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
    main()
