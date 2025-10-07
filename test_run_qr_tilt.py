#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import cv2

from drivers.driver_cam_st import (
    process_frame,
    record_line_tilt_and_get_avg,
    clear_line_tilt_history,
)

# --- QR helper (no windows, single frame pump) ---
_qr = cv2.QRCodeDetector()
def detect_qr_in_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if hasattr(_qr, "detectAndDecodeMulti"):
        ok, texts, points, _ = _qr.detectAndDecodeMulti(gray)
        if ok and texts:
            for t in texts:
                if t:
                    return t
    else:
        t, _, _ = _qr.detectAndDecode(gray)
        if t:
            return t
    return None

def main():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # DSHOW is stable on Windows
    # Camera tuning (best-effort; ignored if unsupported)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cap.set(cv2.CAP_PROP_FOCUS, 50)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cap.set(cv2.CAP_PROP_EXPOSURE, -6)

    if not cap.isOpened():
        raise RuntimeError("Cannot open camera")

    try:
        # ------------ Phase 1: QR (max 10s) ------------
        qr_text = None
        t0 = time.time()
        while (time.time() - t0) < 10.0 and qr_text is None:
            ok, frame = cap.read()
            if not ok:
                continue
            qr_text = detect_qr_in_frame(frame)
        print("QR:", qr_text)

        # Optional small buffer flush before switching tasks
        for _ in range(4):
            cap.grab()
        time.sleep(0.05)

        # ------------ Phase 2: Tilt (collect 10 valid samples or 6s) ------------
        clear_line_tilt_history()
        valid = 0
        last_avg10 = None
        t1 = time.time()
        while valid < 10 and (time.time() - t1) < 6.0:
            ok, frame = cap.read()
            if not ok:
                continue
            vis, tilt = process_frame(frame, visualize=False)
            if tilt is not None:
                last_avg10 = record_line_tilt_and_get_avg(tilt)
                valid += 1

        print("Tilt avg10:", last_avg10)

    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
