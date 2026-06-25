# drivers/driver_QRreader.py
import os
import sys
import time
from pathlib import Path

def _configure_qt_environment():
    for font_dir in (
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype",
        "/usr/share/fonts",
    ):
        if os.path.isdir(font_dir):
            os.environ["QT_QPA_FONTDIR"] = font_dir
            break

    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


_configure_qt_environment()

import cv2
import numpy as np

_configure_qt_environment()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.interrupt_guard import install_deferred_keyboard_interrupt

# Window / camera configuration
WINDOW_NAME = "QR Reader"
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30
FULL_FRAME_FALLBACK_INTERVAL = 5

# Fixed camera sticker area. Normalized as (x, y, width, height) so it
# follows the actual capture resolution.
STICKER_QR_ROI = (0.22, 0.34, 0.17, 0.30)


def on_mouse(event, x, y, flags, userdata):
    """Mouse callback for window interaction."""
    pass


def _preprocess_variants(frame):
    """
    Build several representations of the same frame.
    Different QR codes and lighting conditions respond better to different variants.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    eq = clahe.apply(gray)

    # Proper unsharp mask: original - blurred component
    blur = cv2.GaussianBlur(eq, (0, 0), 1.2)
    sharp = cv2.addWeighted(eq, 1.6, blur, -0.6, 0)

    th_adapt = cv2.adaptiveThreshold(
        sharp,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        3,
    )

    _, th_otsu = cv2.threshold(
        sharp,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    # Try original first, then progressively more aggressive preprocessing
    return [
        ("bgr", frame),
        ("gray", gray),
        ("clahe", eq),
        ("sharp", sharp),
        ("adapt", th_adapt),
        ("otsu", th_otsu),
    ]


def _rescale_points(points, scale):
    """Scale QR corner points back to original image coordinates."""
    if points is None:
        return None
    pts = np.asarray(points, dtype=np.float32)
    return pts / float(scale)


def _offset_points(points, offset_x, offset_y):
    """Move QR corner points from ROI-local coordinates to frame coordinates."""
    pts = _normalize_points(points)
    if pts is None:
        return None
    pts = pts.astype(np.float32, copy=True)
    pts[:, 0] += float(offset_x)
    pts[:, 1] += float(offset_y)
    return pts


def _roi_from_normalized(frame, normalized_roi):
    h, w = frame.shape[:2]
    x, y, roi_w, roi_h = normalized_roi
    x1 = max(0, min(w - 1, int(round(x * w))))
    y1 = max(0, min(h - 1, int(round(y * h))))
    x2 = max(x1 + 1, min(w, int(round((x + roi_w) * w))))
    y2 = max(y1 + 1, min(h, int(round((y + roi_h) * h))))
    return (x1, y1, x2 - x1, y2 - y1)


def _preview_allowed(show):
    if not show:
        return False
    if os.environ.get("QR_READER_FORCE_PREVIEW") == "1":
        return True
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        print("[WARN] OpenCV preview disabled on Wayland to avoid Qt segfault.")
        print("[WARN] Use QR_READER_FORCE_PREVIEW=1 only if the preview is stable on this machine.")
        return False
    return True


def _normalize_points(points):
    """Ensure points are in shape (4, 2) if available."""
    if points is None:
        return None
    pts = np.asarray(points)
    if pts.size == 0:
        return None
    pts = pts.reshape(-1, 2)
    if pts.shape[0] < 4:
        return None
    return pts[:4]


def _decode_with_fallback(detector, img):
    """
    Try multi-decode first, then single decode, then detect -> decode,
    then detect -> decodeCurved.
    Returns: list of (text, points)
    """
    results = []

    # 1) Multi-decode if supported
    if hasattr(detector, "detectAndDecodeMulti"):
        try:
            ok, texts, points, _ = detector.detectAndDecodeMulti(img)
            if ok and texts:
                for i, t in enumerate(texts):
                    if t:
                        pts = None
                        if points is not None and len(points) > i:
                            pts = _normalize_points(points[i])
                        results.append((t, pts))
                if results:
                    return results
        except Exception:
            pass

    # 2) Single detect+decode
    try:
        text, points, _ = detector.detectAndDecode(img)
        if text:
            return [(text, _normalize_points(points))]
    except Exception:
        pass

    # 3) detect -> decode / decodeCurved fallback
    try:
        ok, points = detector.detect(img)
        if ok and points is not None:
            pts = _normalize_points(points)

            try:
                text, _ = detector.decode(img, points)
                if text:
                    return [(text, pts)]
            except Exception:
                pass

            if hasattr(detector, "decodeCurved"):
                try:
                    text, _ = detector.decodeCurved(img, points)
                    if text:
                        return [(text, pts)]
                except Exception:
                    pass
    except Exception:
        pass

    return []


def _scan_qr_image(detector, frame):
    """
    Try multiple image variants and scales.
    Returns list of (text, points) in input-image coordinates.
    """
    variants = _preprocess_variants(frame)

    # Upscaling often helps when the QR code is small in the image
    scales = [1.0, 1.5, 2.0, 3.0]

    all_results = []
    seen_texts = set()

    for _, img in variants:
        for scale in scales:
            if scale != 1.0:
                h, w = img.shape[:2]
                test = cv2.resize(
                    img,
                    (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_CUBIC,
                )
            else:
                test = img

            found = _decode_with_fallback(detector, test)
            if not found:
                continue

            for text, pts in found:
                if not text or text in seen_texts:
                    continue

                seen_texts.add(text)

                if pts is not None and scale != 1.0:
                    pts = _rescale_points(pts, scale)

                pts = _normalize_points(pts)
                all_results.append((text, pts))

            if all_results:
                return all_results

    return all_results


def _find_qr(detector, frame, miss_count=0):
    """
    Scan the fixed sticker area first for speed, then occasionally retry the
    whole frame as a recovery path if the part or camera position drifts.
    """
    x, y, w, h = _roi_from_normalized(frame, STICKER_QR_ROI)
    roi_frame = frame[y:y + h, x:x + w]

    results = []
    for text, pts in _scan_qr_image(detector, roi_frame):
        results.append((text, _offset_points(pts, x, y)))
    if results:
        return results

    if miss_count % FULL_FRAME_FALLBACK_INTERVAL == 0:
        return _scan_qr_image(detector, frame)

    return []


def run_qr_reader(
    camera: int = 0,
    show: bool = True,
    once: bool = False,
    timeout: float = 0.0,
    on_decode=None,          # optional callback(text:str, points:np.ndarray|None)
    return_first: bool = False,
    cap=None,
):
    """
    Start webcam QR reader.

    Returns first decoded text if return_first=True, else None.

    on_decode:
        Called for every NEW text seen (deduplicated).
        Signature: on_decode(text, points)
        where points is a 4x2 corner array or None.
    """
    owns_cap = cap is None
    if owns_cap:
        # Prefer V4L2 on Linux
        cap = cv2.VideoCapture(camera, cv2.CAP_V4L2)

        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {camera}")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

        # Small buffer helps avoid stale frames
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    detector = cv2.QRCodeDetector()

    # Detector tuning. These setters may not exist in every OpenCV build.
    if hasattr(detector, "setEpsX"):
        detector.setEpsX(0.2)
    if hasattr(detector, "setEpsY"):
        detector.setEpsY(0.1)
    if hasattr(detector, "setUseAlignmentMarkers"):
        detector.setUseAlignmentMarkers(True)

    seen = set()
    first_text = None
    miss_count = 0
    start_time = time.time()
    prev_time = time.time()
    show = _preview_allowed(show)

    if show:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, CAMERA_WIDTH, CAMERA_HEIGHT)
        cv2.setMouseCallback(WINDOW_NAME, on_mouse, None)

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            got_new = False
            results = _find_qr(detector, frame, miss_count=miss_count)
            miss_count = 0 if results else miss_count + 1

            for text, pts in results:
                if text not in seen:
                    seen.add(text)
                    got_new = True

                    if on_decode:
                        on_decode(text, pts)
                    else:
                        print(text)

                    if return_first and first_text is None:
                        first_text = text

                if show and pts is not None:
                    pts_i = pts.astype(int).reshape(-1, 2)
                    for j in range(4):
                        cv2.line(
                            frame,
                            tuple(pts_i[j]),
                            tuple(pts_i[(j + 1) % 4]),
                            (0, 255, 0),
                            2,
                        )
                    cx, cy = pts_i.mean(axis=0).astype(int)
                    cv2.circle(frame, (int(cx), int(cy)), 4, (0, 255, 0), -1)
                    cv2.putText(
                        frame,
                        text,
                        (int(pts_i[0][0]), max(20, int(pts_i[0][1]) - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2,
                    )

            if show:
                now = time.time()
                fps = 1.0 / max(now - prev_time, 1e-6)
                prev_time = now

                display_frame = frame.copy()
                rx, ry, rw, rh = _roi_from_normalized(display_frame, STICKER_QR_ROI)
                cv2.rectangle(display_frame, (rx, ry), (rx + rw, ry + rh), (255, 180, 0), 2)
                fps_text = f"FPS: {fps:.1f}"
                cv2.putText(
                    display_frame,
                    fps_text,
                    (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )

                cv2.imshow(WINDOW_NAME, display_frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break

            if once and got_new:
                break

            if timeout and (time.time() - start_time) >= timeout:
                break

    finally:
        if owns_cap and cap is not None:
            cap.release()
        if show:
            cv2.destroyAllWindows()

    return first_text if return_first else None


if __name__ == "__main__":
    restore_sigint = install_deferred_keyboard_interrupt(label="QR reader")
    try:
        print("[INFO] Scanning QR code. Preview is disabled by default on Wayland.")
        qrcode = run_qr_reader(show="--show" in sys.argv, once=True, return_first=True)
        if not qrcode:
            print("[ERROR] No QR detected. Aborting.")
            sys.exit(1)
    finally:
        restore_sigint()
