# qr_reader.py
# pip install opencv-python
import cv2
import argparse
import time
from collections import deque

def decode_and_print(detector, frame, seen, show=False):
    printed_something = False

    # Prefer multi-decode if available
    if hasattr(detector, "detectAndDecodeMulti"):
        ok, texts, points, _ = detector.detectAndDecodeMulti(frame)
        if ok and texts:
            for i, t in enumerate(texts):
                if t:
                    if t not in seen:
                        print(f"[{time.strftime('%H:%M:%S')}] {t}")
                        seen.add(t)
                        printed_something = True
                    if show and points is not None:
                        pts = points[i].astype(int).reshape(-1, 2)
                        for j in range(4):
                            p1 = tuple(pts[j])
                            p2 = tuple(pts[(j+1) % 4])
                            cv2.line(frame, p1, p2, (0, 255, 0), 2)
                        cx, cy = pts.mean(axis=0).astype(int)
                        cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)
    else:
        text, points, _ = detector.detectAndDecode(frame)
        if text:
            if text not in seen:
                print(f"[{time.strftime('%H:%M:%S')}] {text}")
                seen.add(text)
                printed_something = True
            if show and points is not None:
                pts = points.astype(int).reshape(-1, 2)
                for j in range(4):
                    p1 = tuple(pts[j])
                    p2 = tuple(pts[(j+1) % 4])
                    cv2.line(frame, p1, p2, (0, 255, 0), 2)

    if show:
        cv2.imshow("QR Reader (press Q to quit)", frame)
    return printed_something

def read():
    ap = argparse.ArgumentParser(description="Read QR codes from a camera and print text.")
    ap.add_argument("--camera", type=int, default=1, help="Camera index (default: 0)")
    ap.add_argument("--width", type=int, default=1280, help="Capture width")
    ap.add_argument("--height", type=int, default=720, help="Capture height")
    ap.add_argument("--show", action="store_true", help="Show video preview with boxes")
    ap.add_argument("--once", action="store_true", help="Exit after first successful decode")
    ap.add_argument("--timeout", type=float, default=0, help="Exit after N seconds (0=never)")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)  # CAP_DSHOW helps on Windows; safe on others too
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {args.camera}")

    detector = cv2.QRCodeDetector()
    seen = set()
    start_time = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            got_new = decode_and_print(detector, frame, seen, show=args.show)

            if args.once and got_new:
                break

            if args.show and (cv2.waitKey(1) & 0xFF) == ord("q"):
                break

            if args.timeout and (time.time() - start_time) >= args.timeout:
                break

    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    read()
