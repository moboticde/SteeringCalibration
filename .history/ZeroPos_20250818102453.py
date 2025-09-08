# Find ALL hole centers robustly (blob + Hough), then keep only those in x∈[500,1500]
import cv2
import numpy as np
import matplotlib.pyplot as plt

IMAGE_PATH = r'C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\WIN_20250804_12_29_34_Pro.jpg'
X1, X2 = 500, 1500                     # ROI in X; full-height Y by default

# ---------- load & preprocess ----------
img  = cv2.imread(IMAGE_PATH)
if img is None:
    raise FileNotFoundError(IMAGE_PATH)

H, W = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# boost local contrast + de-noise (helps Hough/Blob a lot)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
g = clahe.apply(gray)
g = cv2.medianBlur(g, 5)

# ---------- detector A: SimpleBlob (for dark & bright circular blobs) ----------
def make_blob_detector(minArea=60, maxArea=5000, minCircularity=0.6,
                       minInertia=0.2, minConvexity=0.7):
    p = cv2.SimpleBlobDetector_Params()
    p.minThreshold = 5
    p.maxThreshold = 220
    p.thresholdStep = 5

    p.filterByArea = True;        p.minArea = float(minArea); p.maxArea = float(maxArea)
    p.filterByCircularity = True; p.minCircularity = float(minCircularity)
    p.filterByInertia = True;     p.minInertiaRatio = float(minInertia)
    p.filterByConvexity = True;   p.minConvexity = float(minConvexity)
    p.filterByColor = False       # we’ll run on both g and 255-g
    return cv2.SimpleBlobDetector_create(p)

det = make_blob_detector()

kps_dark  = det.detect(g)          # dark holes
kps_bright= det.detect(255 - g)    # sometimes rims/bolts are bright

blob_pts = [(int(k.pt[0]), int(k.pt[1]), 0.5*k.size) for k in (kps_dark + kps_bright)]

# ---------- detector B: HoughCircles (catches missed ones) ----------
# Radius range is fairly wide; tune if needed
circles = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=28,
                           param1=120, param2=18, minRadius=6, maxRadius=40)
hough_pts = []
if circles is not None:
    circles = np.round(circles[0, :]).astype(int)
    for x, y, r in circles:
        hough_pts.append((int(x), int(y), float(r)))

# ---------- merge & dedupe ----------
candidates = blob_pts + hough_pts

def dedupe(points, min_dist=18):
    out = []
    for x, y, r in points:
        keep = True
        for X, Y, R in out:
            if (x-X)**2 + (y-Y)**2 <= min_dist**2:
                keep = False
                break
        if keep:
            out.append((x, y, r))
    return out

centers_all = dedupe(candidates, min_dist=20)

# ---------- ROI filter ----------
centers_roi = [(x, y, r) for (x, y, r) in centers_all if X1 <= x <= X2 and 0 <= y < H]

# ---------- visualize ----------
vis = img.copy()
# draw ROI for reference
cv2.line(vis, (X1, 0), (X1, H), (0, 255, 255), 3)
cv2.line(vis, (X2, 0), (X2, H), (0, 255, 255), 3)

for x, y, r in centers_roi:
    cv2.circle(vis, (x, y), int(max(6, r)), (0, 255, 0), 2)
    cv2.circle(vis, (x, y), 5, (255, 0, 0), -1)

plt.figure(figsize=(7,7))
plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
plt.title('Hole centers in ROI [500, 1500]')
plt.axis('off')
plt.show()

# ---------- print results ----------
print(f'Hole centers found in ROI: {len(centers_roi)}')
print([(x, y) for x, y, _ in centers_roi])
