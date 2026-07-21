# drivers/driver_QRreader.py
import os
import subprocess
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

WINDOW_NAME = "QR Reader"
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30
FULL_FRAME_FALLBACK_INTERVAL = 5
STICKER_QR_ROI = (0.22, 0.34, 0.17, 0.30)


def on_mouse(event, x, y, flags, userdata):
    pass


def _preprocess_variants(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
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
    return [
        ("bgr", frame),
        ("gray", gray),
        ("clahe", eq),
        ("sharp", sharp),
        ("adapt", th_adapt),
        ("otsu", th_otsu),
    ]


def _rescale_points(points, scale):
    if points is None:
        return None
    pts = np.asarray(points, dtype=np.float32)
    return pts / float(scale)


def _offset_points(points, offset_x, offset_y):
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


def _camera_candidates(camera, *env_names):
    candidates = []

    def add(value):
        if value is None or value == "":
            return
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if value not in candidates:
            candidates.append(value)

    for env_name in env_names:
        add(os.environ.get(env_name))
    add(camera)

    for dev_name in sorted(os.listdir("/dev") if os.path.isdir("/dev") else []):
        if dev_name.startswith("video"):
            suffix = dev_name[5:]
            if suffix.isdigit():
                add(int(suffix))

    return candidates


def _camera_busy_details():
    devices = [
        f"/dev/{name}"
        for name in sorted(os.listdir("/dev") if os.path.isdir("/dev") else [])
        if name.startswith("video")
    ]
    if not devices:
        return "No /dev/video* devices found."
    try:
        result = subprocess.run(
            ["fuser", "-v", *devices],
            text=True,
            capture_output=True,
            timeout=2.0,
            check=False,
        )
    except Exception:
        return ""
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())


def _open_camera_capture(camera=0, *env_names):
    errors = []
    for candidate in _camera_candidates(camera, *env_names):
        attempts = []
        if isinstance(candidate, int):
            attempts.append((candidate, cv2.CAP_V4L2, f"camera index {candidate}"))
        else:
            attempts.append((candidate, cv2.CAP_V4L2, str(candidate)))
            attempts.append((candidate, cv2.CAP_ANY, str(candidate)))

        for source, backend, label in attempts:
            cap = cv2.VideoCapture(source, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print(f"[INFO] Camera opened: {label}")
                return cap
            cap.release()
            errors.append(label)

    busy = _camera_busy_details()
    message = f"Cannot open camera. Tried: {', '.join(errors) or camera}."
    if busy:
        message += f" Camera device users/details:\n{busy}"
    raise RuntimeError(message)


def _normalize_points(points):
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
    results = []
    if hasattr(detector, "detectAndDecodeMulti"):
        try:
            ok, texts, points, _ = detector.detectAndDecodeMulti(img)
            if ok and texts:
                for i, text in enumerate(texts):
                    if text:
                        pts = None
                        if points is not None and len(points) > i:
                            pts = _normalize_points(points[i])
                        results.append((text, pts))
                if results:
                    return results
        except Exception:
            pass

    try:
        text, points, _ = detector.detectAndDecode(img)
        if text:
            return [(text, _normalize_points(points))]
    except Exception:
        pass

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
    variants = _preprocess_variants(frame)
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
                all_results.append((text, _normalize_points(pts)))

            if all_results:
                return all_results

    return all_results


def _find_qr(detector, frame, miss_count=0):
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
    on_decode=None,
    return_first: bool = False,
    cap=None,
):
    owns_cap = cap is None
    if owns_cap:
        cap = _open_camera_capture(camera, "QR_READER_CAMERA", "ST_CAMERA_DEVICE")

    detector = cv2.QRCodeDetector()
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
                        cv2.line(frame, tuple(pts_i[j]), tuple(pts_i[(j + 1) % 4]), (0, 255, 0), 2)
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
                cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
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


def _main():
    restore_sigint = install_deferred_keyboard_interrupt(label="QR reader")
    try:
        print("[INFO] Scanning QR code. Preview is disabled by default on Wayland.")
        qrcode = run_qr_reader(show="--show" in sys.argv, once=True, return_first=True)
        if not qrcode:
            print("[ERROR] No QR detected. Aborting.")
            sys.exit(1)
        print(qrcode)
    finally:
        restore_sigint()


if __name__ == "__main__":
    _main()
