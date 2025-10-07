# drivers/driver_QRreader.py
import sys
import cv2
import time

def _preprocess_for_qr(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    g = clahe.apply(g)
    blur = cv2.GaussianBlur(g, (0,0), 1.0)
    sharp = cv2.addWeighted(g, 1.5, blur, -0.5, 0)  # unsharp mask
    return sharp


def run_qr_reader(
    camera: int = 0,
    show: bool = True,
    once: bool = False,
    timeout: float = 0.0,
    on_decode=None,          # optional callback(text:str, points:np.ndarray|None)
    return_first: bool = False,
    cap = None,
):
    """
    Start webcam QR reader. Returns first decoded text if return_first=True, else None.

    on_decode: called for every NEW text seen (deduplicated).
               signature: on_decode(text, points) where points is 4x2 corner array or None.
    """
    # CAP_DSHOW is helpful on Windows; harmless elsewhere
    owns_cap = cap is None
    if owns_cap:
        cap = cv2.VideoCapture(camera, cv2.CAP_DSHOW) 
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)   # higher native res -> more modules visible
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 60)             # if your camera supports it
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)       # cut capture latency

        # Try to freeze optics (may be ignored if backend/driver blocks it)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        cap.set(cv2.CAP_PROP_FOCUS, 50)           # tune for your working distance
        # Exposure (semantics vary by backend; values are device-specific)
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        cap.set(cv2.CAP_PROP_EXPOSURE, -6)

        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {camera}")

    detector = cv2.QRCodeDetector()
    seen = set()
    start = time.time()
    first_text = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            got_new = False
            work = _preprocess_for_qr(frame)   # <<< use this

            # if you try multiple scales:
            for scale in (1.0, 1.5, 2.0):
                img = work if scale == 1.0 else cv2.resize(work, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


            # Prefer multi-decode if available
            if hasattr(detector, "detectAndDecodeMulti"):
                ok_multi, texts, points, _ = detector.detectAndDecodeMulti(img)
                if ok_multi and texts:
                    for i, t in enumerate(texts):
                        if t:
                            if t not in seen:
                                seen.add(t)
                                got_new = True
                                if on_decode:
                                    on_decode(t, points[i] if points is not None else None)
                                else:
                                    print(t)
                                if return_first and first_text is None:
                                    first_text = t
                                if show and points is not None:
                                    pts = points[i].astype(int).reshape(-1, 2)
                                    for j in range(4):
                                        cv2.line(frame, tuple(pts[j]),
                                                 tuple(pts[(j + 1) % 4]), (0, 255, 0), 2)
                                    cx, cy = pts.mean(axis=0).astype(int)
                                    cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)
            else:
                t, pts, _ = detector.detectAndDecode(frame)
                if t:
                    if t not in seen:
                        seen.add(t)
                        got_new = True
                        if on_decode:
                            on_decode(t, pts)
                        else:
                            print(t)
                        if return_first and first_text is None:
                            first_text = t
                    if show and pts is not None:
                        pts = pts.astype(int).reshape(-1, 2)
                        for j in range(4):
                            cv2.line(frame, tuple(pts[j]),
                                     tuple(pts[(j + 1) % 4]), (0, 255, 0), 2)

            if show:
                cv2.imshow("QR Reader (press Q to quit)", frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break

            if once and got_new:
                break

            if timeout and (time.time() - start) >= timeout:
                break
    finally:
        cap.release()
        if show:
            cv2.destroyAllWindows()

    return first_text if return_first else None


# --- CLI entrypoint remains available ---
if __name__ == "__main__":
    qrcode = run_qr_reader(show=True, once=True, return_first=True)
    if not qrcode:
        print("[ERROR] No QR detected. Aborting.")
        sys.exit(1)
