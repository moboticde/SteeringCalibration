# drivers/driver_QRreader.py
import cv2
import time

def run_qr_reader(
    camera: int = 0,
    width: int = 1280,
    height: int = 720,
    show: bool = True,
    once: bool = False,
    timeout: float = 0.0,
    on_decode=None,          # optional callback(text:str, points:np.ndarray|None)
    return_first: bool = False
):
    """
    Start webcam QR reader. Returns first decoded text if return_first=True, else None.

    on_decode: called for every NEW text seen (deduplicated).
               signature: on_decode(text, points) where points is 4x2 corner array or None.
    """
    # CAP_DSHOW is helpful on Windows; harmless elsewhere
    cap = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
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

            # Prefer multi-decode if available
            if hasattr(detector, "detectAndDecodeMulti"):
                ok_multi, texts, points, _ = detector.detectAndDecodeMulti(frame)
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
    import argparse
    ap = argparse.ArgumentParser(description="Read QR codes from a camera and print text.")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--timeout", type=float, default=0)
    args = ap.parse_args()
    run_qr_reader(
        camera=args.camera,
        width=args.width,
        height=args.height,
        show=args.show,
        once=args.once,
        timeout=args.timeout
    )
