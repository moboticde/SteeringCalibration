import math
import os
import sys
import cv2
import numpy as np
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.interrupt_guard import install_deferred_keyboard_interrupt

# ------------------- CONFIG -------------------
CAMERA_ID = int(os.environ.get("ST_CAMERA_ID", "0"))
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
INNER_RADIUS = 220
OUTER_RADIUS = 300

# Main circle parameters
MIN_AREA_MAIN = 1000
TARGET_RADIUS_MAIN = 430
CIRC_MIN_MAIN = 0.25

# Lines / pointer
LINE_THICKNESS = 3
MIN_LINE_LENGTH = 40
MAX_LINE_LENGTH = 170

# Angle tracking / smoothing
ANGLE_HISTORY = deque(maxlen=30)
MERGE_ANGLE_TOL = 5.0
ANGLE_FOLLOW_BAND = 18.0
ANGLE_SMOOTH_ALPHA = 0.35
ZERO_POINT_ROTATION_CW_DEG = 90.0

# Pointer detection inside inner disk
RADIAL_ALIGN_MIN = 0.80
CENTER_EXCLUDE_RADIUS = 20      # ignore tiny noisy center region
POINTER_MIN_TIP_RADIUS = 55     # far endpoint must be at least this far from center
POINTER_SEARCH_MARGIN = 10      # search until slightly before inner circle

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
RULER_BAND = 26
RULER_MAJOR = 100
RULER_MINOR = 10

# Mouse state
MOUSE_POS = (-1, -1)

# --- origin + ruler units ---
ORIGIN_CENTER = True
Y_AXIS_UP = True
RULER_IN_BASE_UNITS = True
RULER_MAJOR_UNITS = 100
RULER_MINOR_UNITS = 10

# Origin offset in base units (where base (-50, 10) becomes display zero)
ORIGIN_OFFSET_X_BASE = 50
ORIGIN_OFFSET_Y_BASE = 25
ORIGIN_OFFSET_X_PIXEL = ORIGIN_OFFSET_X_BASE * (CAMERA_WIDTH / BASE_W)
ORIGIN_OFFSET_Y_PIXEL = ORIGIN_OFFSET_Y_BASE * (CAMERA_HEIGHT / BASE_H)


# ------------------- HELPERS -------------------

def on_mouse(event, x, y, flags, userdata):
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

    kernel1 = np.ones((3, 3), np.uint8)
    kernel2 = np.ones((3, 3), np.uint8)

    dilated = cv2.dilate(blurred, kernel1, iterations=1)
    eroded = cv2.erode(dilated, kernel2, iterations=3)

    edges = cv2.Canny(eroded, 100, 300)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel2)
    return eroded, edges


# ------------------- RULER + CURSOR OVERLAYS -------------------

def draw_rulers(img, band=RULER_BAND, major=RULER_MAJOR, minor=RULER_MINOR):
    if band <= 0:
        return img

    h, w = img.shape[:2]
    cx = int(w // 2 - ORIGIN_OFFSET_X_PIXEL)
    cy = int(h // 2 - ORIGIN_OFFSET_Y_PIXEL)

    cv2.rectangle(img, (0, 0), (w, band), (40, 40, 40), -1)
    cv2.rectangle(img, (0, 0), (band, h), (40, 40, 40), -1)

    if not RULER_IN_BASE_UNITS:
        for x in range(0, w, RULER_MINOR):
            if x % RULER_MAJOR == 0:
                tlen, thick, col = band - 2, 2, (210, 210, 210)
            elif x % (RULER_MAJOR // 2) == 0:
                tlen, thick, col = band // 2 + 4, 1, (180, 180, 180)
            else:
                tlen, thick, col = band // 3, 1, (160, 160, 160)
            cv2.line(img, (x, band), (x, band - tlen), col, thick)
            if x % RULER_MAJOR == 0:
                cv2.putText(
                    img, f"{x - (cx if ORIGIN_CENTER else 0)}",
                    (x + 2, band - 6),
                    cv2.FONT_HERSHEY_PLAIN, 1.0, (230, 230, 230), 1, cv2.LINE_AA
                )

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
                cv2.putText(
                    img, f"{val}",
                    (4, y - 4 if y - 4 > 10 else y + 12),
                    cv2.FONT_HERSHEY_PLAIN, 1.0, (230, 230, 230), 1, cv2.LINE_AA
                )

        if ORIGIN_CENTER:
            cv2.line(img, (cx, band), (cx, 0), (255, 255, 255), 1)
            cv2.line(img, (band, cy), (0, cy), (255, 255, 255), 1)
        return img

    scale_x = (CAMERA_WIDTH / float(BASE_W)) * DISPLAY_SCALE
    scale_y = (CAMERA_HEIGHT / float(BASE_H)) * DISPLAY_SCALE
    if scale_x <= 1e-9 or scale_y <= 1e-9:
        return img

    if ORIGIN_CENTER:
        min_base_x = -(cx) / scale_x
        max_base_x = (w - cx) / scale_x
        min_base_y = -(cy) / scale_y
        max_base_y = (h - cy) / scale_y
    else:
        min_base_x, max_base_x = 0.0, w / scale_x
        min_base_y, max_base_y = 0.0, h / scale_y

    maj_x = float(RULER_MAJOR_UNITS)
    min_x = float(RULER_MINOR_UNITS)
    maj_y = float(RULER_MAJOR_UNITS)
    min_y = float(RULER_MINOR_UNITS)

    def start_at(minv, step):
        return math.ceil(minv / step) * step

    x_base = start_at(min_base_x, min_x)
    while x_base <= max_base_x + 1e-6:
        x_disp = int(round((cx if ORIGIN_CENTER else 0) + x_base * scale_x))
        if abs((x_base / maj_x) - round(x_base / maj_x)) < 1e-6:
            tlen, thick, col = band - 2, 2, (210, 210, 210)
            do_label = True
        elif abs((x_base / (maj_x / 2.0)) - round(x_base / (maj_x / 2.0))) < 1e-6:
            tlen, thick, col = band // 2 + 4, 1, (180, 180, 180)
            do_label = False
        else:
            tlen, thick, col = band // 3, 1, (160, 160, 160)
            do_label = False

        cv2.line(img, (x_disp, band), (x_disp, band - tlen), col, thick)
        if do_label:
            cv2.putText(
                img, f"{int(round(x_base))}",
                (x_disp + 2, band - 6),
                cv2.FONT_HERSHEY_PLAIN, 1.0, (230, 230, 230), 1, cv2.LINE_AA
            )
        x_base += min_x

    y_base = start_at(min_base_y, min_y)
    while y_base <= max_base_y + 1e-6:
        y_disp = int(round((cy if ORIGIN_CENTER else 0) + (-y_base if Y_AXIS_UP else y_base) * scale_y))
        if abs((y_base / maj_y) - round(y_base / maj_y)) < 1e-6:
            tlen, thick, col = band - 2, 2, (210, 210, 210)
            do_label = True
        elif abs((y_base / (maj_y / 2.0)) - round(y_base / (maj_y / 2.0))) < 1e-6:
            tlen, thick, col = band // 2 + 4, 1, (180, 180, 180)
            do_label = False
        else:
            tlen, thick, col = band // 3, 1, (160, 160, 160)
            do_label = False

        cv2.line(img, (band, y_disp), (band - tlen, y_disp), col, thick)
        if do_label:
            cv2.putText(
                img, f"{int(round(y_base))}",
                (4, y_disp - 4 if y_disp - 4 > 10 else y_disp + 12),
                cv2.FONT_HERSHEY_PLAIN, 1.0, (230, 230, 230), 1, cv2.LINE_AA
            )
        y_base += min_y

    if ORIGIN_CENTER:
        cv2.line(img, (cx, band), (cx, 0), (255, 255, 255), 1)
        cv2.line(img, (band, cy), (0, cy), (255, 255, 255), 1)

    return img

def draw_cursor_overlay(img, mouse_xy, disp_scale, in_scale):
    if mouse_xy is None:
        return img

    h, w = img.shape[:2]
    x_disp, y_disp = mouse_xy
    if x_disp < 0 or y_disp < 0 or x_disp >= w or y_disp >= h:
        return img

    cx = int(w // 2 - ORIGIN_OFFSET_X_PIXEL)
    cy = int(h // 2 - ORIGIN_OFFSET_Y_PIXEL)

    cv2.line(img, (x_disp, 0), (x_disp, h - 1), (0, 255, 0), 1, cv2.LINE_AA)
    cv2.line(img, (0, y_disp), (w - 1, y_disp), (0, 255, 0), 1, cv2.LINE_AA)
    cv2.circle(img, (x_disp, y_disp), 3, (0, 255, 0), -1, cv2.LINE_AA)

    x0_disp = x_disp - cx if ORIGIN_CENTER else x_disp
    y0_disp = (cy - y_disp) if (ORIGIN_CENTER and Y_AXIS_UP) else ((y_disp - cy) if ORIGIN_CENTER else y_disp)

    scale_x = (CAMERA_WIDTH / float(BASE_W)) * DISPLAY_SCALE
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


# ------------------- ANGLE HELPERS -------------------

def wrap_angle_deg(a):
    return a % 360.0

def angle_cw_from_segment(x1, y1, x2, y2, cx, cy):
    """
    Angle in [0,360): clockwise, with zero rotated clockwise from +Y,
    using the endpoint farther from center as the pointer tip.
    """
    d1 = (x1 - cx) ** 2 + (y1 - cy) ** 2
    d2 = (x2 - cx) ** 2 + (y2 - cy) ** 2
    xf, yf = (x2, y2) if d2 > d1 else (x1, y1)

    vx = xf - cx
    vy = cy - yf
    raw_angle = math.degrees(math.atan2(vx, vy))
    return wrap_angle_deg(raw_angle - ZERO_POINT_ROTATION_CW_DEG)

def ang_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)

def circular_mean(angles_deg):
    if not angles_deg:
        return None
    s = sum(math.sin(math.radians(a)) for a in angles_deg)
    c = sum(math.cos(math.radians(a)) for a in angles_deg)
    if abs(s) < 1e-12 and abs(c) < 1e-12:
        return None
    return wrap_angle_deg(math.degrees(math.atan2(s, c)))

def weighted_circular_mean(angles_deg, weights):
    if not angles_deg:
        return None
    s = 0.0
    c = 0.0
    for a, w in zip(angles_deg, weights):
        r = math.radians(a)
        s += w * math.sin(r)
        c += w * math.cos(r)
    if abs(s) < 1e-12 and abs(c) < 1e-12:
        return None
    return wrap_angle_deg(math.degrees(math.atan2(s, c)))

def circular_lerp_deg(prev_angle, new_angle, alpha):
    if prev_angle is None:
        return new_angle
    delta = ((new_angle - prev_angle + 180.0) % 360.0) - 180.0
    return wrap_angle_deg(prev_angle + alpha * delta)

def record_angle_and_get_avg(angle_deg):
    if angle_deg is not None and 0.0 <= angle_deg < 360.0:
        ANGLE_HISTORY.append(float(angle_deg))
    return circular_mean(list(ANGLE_HISTORY)) if ANGLE_HISTORY else None

def clear_angle_history():
    ANGLE_HISTORY.clear()

def reset_tracking_state():
    clear_angle_history()
    if hasattr(process_frame, "prev_angle"):
        process_frame.prev_angle = None

def make_pointer_mask(h, w, cx, cy, search_radius, roi_bounds):
    """
    Mask for pointer detection:
    - inside inner disk
    - excluding tiny center region
    - clipped by ROI rectangle
    """
    x1, y1, x2, y2 = roi_bounds

    disk = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(disk, (cx, cy), int(search_radius), 255, -1)
    cv2.circle(disk, (cx, cy), int(CENTER_EXCLUDE_RADIUS), 0, -1)

    roi = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(roi, (x1, y1), (x2, y2), 255, -1)

    return cv2.bitwise_and(disk, roi)

def merge_angle_candidates(candidates, tol_deg=MERGE_ANGLE_TOL):
    groups = []

    for cand in sorted(candidates, key=lambda c: c["score"], reverse=True):
        placed = False
        for g in groups:
            if ang_diff(cand["angle"], g["angle"]) <= tol_deg:
                g["items"].append(cand)
                g["angle"] = weighted_circular_mean(
                    [it["angle"] for it in g["items"]],
                    [it["score"] for it in g["items"]],
                )
                placed = True
                break

        if not placed:
            groups.append({
                "angle": cand["angle"],
                "items": [cand],
            })

    merged = []
    for g in groups:
        items = g["items"]
        best_seg = max(items, key=lambda c: c["score"])
        merged.append({
            "angle": weighted_circular_mean(
                [it["angle"] for it in items],
                [it["score"] for it in items],
            ),
            "score": sum(it["score"] for it in items),
            "best_seg": best_seg,
            "items": items,
        })

    merged.sort(key=lambda c: c["score"], reverse=True)
    return merged

def detect_pointer_candidates(edges, center_x, center_y, search_radius, roi_bounds, prev_angle=None):
    """
    Detect pointer line inside the INNER disk.
    """
    H, W = edges.shape[:2]
    mask = make_pointer_mask(H, W, center_x, center_y, search_radius, roi_bounds)
    masked_edges = cv2.bitwise_and(edges, edges, mask=mask)

    raw = cv2.HoughLinesP(
        masked_edges,
        rho=1,
        theta=np.pi / 360,
        threshold=10,
        minLineLength=MIN_LINE_LENGTH,
        maxLineGap=12,
    )

    candidates = []
    if raw is None:
        return [], masked_edges

    for x1, y1, x2, y2 in raw.reshape(-1, 4):
        dx = x2 - x1
        dy = y2 - y1
        seg_len = math.hypot(dx, dy)

        if seg_len < MIN_LINE_LENGTH or seg_len > MAX_LINE_LENGTH:
            continue

        r1 = math.hypot(x1 - center_x, y1 - center_y)
        r2 = math.hypot(x2 - center_x, y2 - center_y)

        r_far = max(r1, r2)
        r_near = min(r1, r2)

        # Pointer should start closer to center and extend outward inside inner disk
        if r_far < POINTER_MIN_TIP_RADIUS:
            continue
        if r_far > search_radius + 8:
            continue
        if r_near > search_radius:
            continue

        # Use farther endpoint as pointer tip direction
        if r2 > r1:
            fx, fy = x2 - center_x, y2 - center_y
        else:
            fx, fy = x1 - center_x, y1 - center_y

        rf = math.hypot(fx, fy)
        if rf < 1e-6:
            continue

        ux, uy = dx / seg_len, dy / seg_len

        # Segment direction must align with radius from center
        radial_align = abs((ux * fx + uy * fy) / rf)
        if radial_align < RADIAL_ALIGN_MIN:
            continue

        angle = angle_cw_from_segment(x1, y1, x2, y2, center_x, center_y)

        score = 0.0
        score += 3.0 * radial_align
        score += 1.0 * (seg_len / max(MAX_LINE_LENGTH, 1))
        score += 1.0 * (r_far / max(search_radius, 1))

        if prev_angle is not None:
            d = ang_diff(angle, prev_angle)
            if d <= ANGLE_FOLLOW_BAND:
                score += 1.5 * (1.0 - d / ANGLE_FOLLOW_BAND)

        candidates.append({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "length": seg_len,
            "angle": angle,
            "score": score,
            "radial_align": radial_align,
            "r_far": r_far,
            "r_near": r_near,
        })

    merged = merge_angle_candidates(candidates, tol_deg=MERGE_ANGLE_TOL)
    return merged, masked_edges


# ------------------- HOLES -------------------

def detect_main_hole(contours, hierarchy, roi_bounds):
    x1, y1, x2, y2 = roi_bounds
    main_hole = None
    max_circularity = 0

    for i, cnt in enumerate(contours):
        if hierarchy[0][i][3] != -1:
            continue

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

        if circularity >= CIRC_MIN_MAIN and r <= TARGET_RADIUS_MAIN:
            if circularity > max_circularity:
                max_circularity = circularity
                main_hole = cnt

    return main_hole, max_circularity

def detect_holes(contours, hierarchy, center_x, center_y, inner_radius, outer_radius, roi_bounds):
    x1, y1, x2, y2 = roi_bounds
    holes = []

    for i, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        if area < MIN_AREA:
            continue

        cnt_center = center_of(cnt)
        if cnt_center is None:
            continue

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

        if R_MIN <= r <= R_MAX and circularity >= CIRC_MIN:
            holes.append(cnt)

    return holes


# ------------------- FRAME PIPELINE -------------------

def process_frame(frame, visualize=False):
    frame = cv2.resize(frame, None, fx=INPUT_SCALE, fy=INPUT_SCALE, interpolation=cv2.INTER_AREA)
    H, W = frame.shape[:2]

    eroded, edges = process_image(frame)
    vis = cv2.cvtColor(eroded, cv2.COLOR_GRAY2BGR) if visualize else None

    def get_roi():
        center_x = int(W / 2 - ORIGIN_OFFSET_X_PIXEL)
        center_y = int(H / 2 - ORIGIN_OFFSET_Y_PIXEL)
        scale_factor = CAMERA_WIDTH / 1920.0
        scaled_outer = int(OUTER_RADIUS * scale_factor)

        if ROI_MODE == "auto_circle":
            x1 = max(0, center_x - scaled_outer - ROI_MARGIN)
            x2 = min(W - 1, center_x + scaled_outer + ROI_MARGIN)
            y1 = max(0, center_y - scaled_outer - ROI_MARGIN)
            y2 = min(H - 1, center_y + scaled_outer + ROI_MARGIN)
            return x1, y1, x2, y2

        elif ROI_MODE == "relative":
            x1 = int(X1_REL * W)
            x2 = int(X2_REL * W)
            y1 = int(Y1_REL * H)
            y2 = int(Y2_REL * H)
            return x1, y1, x2, y2

        else:  # manual_base
            _x1 = 0 if X1 is None else X1
            _x2 = W if X2 is None else X2
            _y1 = 0 if Y1 is None else Y1
            _y2 = H if Y2 is None else Y2

            x1 = int(_x1 * W / BASE_W)
            x2 = int(_x2 * W / BASE_W)
            y1 = int(_y1 * H / BASE_H)
            y2 = int(_y2 * H / BASE_H)

            x1 = max(0, min(x1, W - 1))
            x2 = max(0, min(x2, W - 1))
            y1 = max(0, min(y1, H - 1))
            y2 = max(0, min(y2, H - 1))
            return x1, y1, x2, y2

    roi_bounds = get_roi()
    scaled_x1, scaled_y1, scaled_x2, scaled_y2 = roi_bounds

    center_x = int(W / 2 - ORIGIN_OFFSET_X_PIXEL)
    center_y = int(H / 2 - ORIGIN_OFFSET_Y_PIXEL)
    scale_factor = CAMERA_WIDTH / 1920.0
    scaled_inner = int(INNER_RADIUS * scale_factor)
    scaled_outer = int(OUTER_RADIUS * scale_factor)
    pointer_search_radius = max(40, scaled_inner - POINTER_SEARCH_MARGIN)

    prev_angle = getattr(process_frame, "prev_angle", None)

    merged_candidates, masked_edges = detect_pointer_candidates(
        edges,
        center_x,
        center_y,
        pointer_search_radius,
        roi_bounds,
        prev_angle=prev_angle,
    )

    best_angle = None
    selected_seg = None

    if merged_candidates:
        top = merged_candidates[:3]
        leader = top[0]
        pool = [c for c in top if ang_diff(c["angle"], leader["angle"]) <= 6.0]

        raw_angle = weighted_circular_mean(
            [c["angle"] for c in pool],
            [c["score"] for c in pool],
        )

        best_angle = circular_lerp_deg(prev_angle, raw_angle, ANGLE_SMOOTH_ALPHA)
        selected_seg = leader["best_seg"]

    process_frame.prev_angle = best_angle if best_angle is not None else prev_angle

    if visualize and vis is not None:
        # Main reference circles
        cv2.circle(vis, (center_x, center_y), scaled_inner, (0, 0, 255), 2)
        cv2.circle(vis, (center_x, center_y), scaled_outer, (0, 0, 255), 2)

        # Pointer search area
        cv2.circle(vis, (center_x, center_y), pointer_search_radius, (0, 255, 0), 1)
        cv2.circle(vis, (center_x, center_y), CENTER_EXCLUDE_RADIUS, (0, 255, 255), 1)

        # ROI
        cv2.rectangle(vis, (scaled_x1, scaled_y1), (scaled_x2, scaled_y2), (0, 255, 255), 2)

        # Masked edges overlay
        edge_overlay = cv2.cvtColor(masked_edges, cv2.COLOR_GRAY2BGR)
        vis = cv2.addWeighted(vis, 1.0, edge_overlay, 0.25, 0)

        # Draw final selected/smoothed angle
        if selected_seg is not None and best_angle is not None:
            x1, y1 = selected_seg["x1"], selected_seg["y1"]
            x2, y2 = selected_seg["x2"], selected_seg["y2"]

            cv2.line(vis, (x1, y1), (x2, y2), (165, 42, 42), LINE_THICKNESS)

            d1 = (x1 - center_x) ** 2 + (y1 - center_y) ** 2
            d2 = (x2 - center_x) ** 2 + (y2 - center_y) ** 2
            lx, ly = (x2, y2) if d2 > d1 else (x1, y1)

            cv2.putText(
                vis,
                f"{best_angle:6.2f}",
                (lx + 6, ly - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (165, 42, 42),
                2,
            )

        contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if contours is not None and len(contours) > 0:
            if hierarchy is None:
                hierarchy = np.zeros((1, len(contours), 4), dtype=np.int32)

            holes = detect_holes(
                contours, hierarchy, center_x, center_y,
                scaled_inner, scaled_outer, roi_bounds
            )
            for hole in holes:
                cv2.drawContours(vis, [hole], -1, (255, 0, 0), 2)
                hc = center_of(hole)
                if hc:
                    cv2.circle(vis, hc, 3, (0, 255, 255), -1)

            if DEBUG_DRAW_ALL_CONTOURS:
                cv2.drawContours(vis, contours, -1, (255, 0, 255), 1)

    return vis, best_angle


# ------------------- MAIN -------------------

def AngleDetection(debug=False, return_after=10, timeout_s=None, cap=None):
    """
    Two modes:
      - debug=True  -> visual mode with window, rulers, cursor, live HUD; quit with 'q'
      - debug=False -> headless mode, returns avg angle after `return_after` samples or `timeout_s`
    """
    global MOUSE_POS
    RULER_ENABLED = debug
    start_all = time.time()
    last_avg = None

    reset_tracking_state()

    owns_cap = cap is None
    if owns_cap:
        if sys.platform.startswith("linux"):
            cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(CAMERA_ID)
        else:
            cap = cv2.VideoCapture(CAMERA_ID)
        if not cap.isOpened():
            print(f"Error: Could not open webcam camera_id={CAMERA_ID}")
            return None

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, FPS_TARGET)

        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if debug:
            print(f"Camera resolution: {actual_width}x{actual_height}")

    if debug:
        timeout_s = None
        window_name = "Zero Position"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, CAMERA_WIDTH, CAMERA_HEIGHT)
        cv2.setMouseCallback(window_name, on_mouse, None)
        print("Press 'q' to quit | 'r' to reset average buffer")

    frames_read = 0
    detected_samples = 0

    while True:
        if (not debug) and (timeout_s is not None) and ((time.time() - start_all) >= timeout_s):
            break

        start_time = time.time()
        ret, frame = cap.read()
        if not ret:
            print(f"Error: Could not read frame from camera_id={CAMERA_ID}")
            break
        frames_read += 1

        vis, angleCW = process_frame(frame, visualize=debug)
        if angleCW is not None:
            detected_samples += 1
        avg_angle = record_angle_and_get_avg(angleCW)
        if avg_angle is not None:
            last_avg = avg_angle

        if (not debug) and (return_after is not None) and (len(ANGLE_HISTORY) >= return_after):
            break

        if debug:
            result = vis if vis is not None else frame.copy()
            if DISPLAY_SCALE != 1.0:
                result = cv2.resize(result, None, fx=DISPLAY_SCALE, fy=DISPLAY_SCALE, interpolation=cv2.INTER_AREA)

            if RULER_ENABLED:
                draw_rulers(result, band=RULER_BAND, major=RULER_MAJOR, minor=RULER_MINOR)

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
            if k == ord("q"):
                break
            elif k == ord("r"):
                reset_tracking_state()
                last_avg = None

    if owns_cap:
        cap.release()
    if debug:
        cv2.destroyAllWindows()

    if last_avg is None and not debug:
        print(
            "[ERROR] Camera angle detection returned no stable angle: "
            f"camera_id={CAMERA_ID} frames_read={frames_read} "
            f"valid_angle_samples={detected_samples} required_samples={return_after} "
            f"timeout_s={timeout_s}"
        )

    return last_avg


if __name__ == "__main__":
    restore_sigint = install_deferred_keyboard_interrupt(label="camera angle detection")
    try:
        avgAngle = AngleDetection(debug=True, return_after=10, timeout_s=None)
        print(f"Angle: {avgAngle}")
    finally:
        restore_sigint()
