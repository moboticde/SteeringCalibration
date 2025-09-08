import cv2
import numpy as np
import matplotlib.pyplot as plt

# 1. Load image
img = cv2.imread(r'C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\WIN_20250804_12_29_34_Pro.jpg')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)

# --- ROI you asked for ---
X1, X2 = 500, 1500
Y1, Y2 = 0, img.shape[0]                 # full height; change if you also want a y-limit

# 2. Edge detection
edges = cv2.Canny(blurred, 50, 150)

# 3. Find contours
contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

# 4. Draw detected contours
contour_img = img.copy()
cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)

# Draw ROI on the right subplot for reference
cv2.rectangle(contour_img, (X1, Y1), (X2, Y2), (0, 255, 255), 3)

# 5. Classify contours
holes = []
lines = []
for i, cnt in enumerate(contours):
    area = cv2.contourArea(cnt)
    if hierarchy[0][i][3] != -1 and area > 100:  # holes (child contours with parent)
        holes.append(cnt)
        cv2.drawContours(contour_img, [cnt], -1, (255, 0, 0), 3)
    elif 500 < area < 80000:
        lines.append(cnt)
        cv2.drawContours(contour_img, [cnt], -1, (0, 0, 255), 2)

# 6. Centers
def get_center(cnt):
    M = cv2.moments(cnt)
    if M["m00"] == 0:
        return None
    return (int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"]))

hole_centers_all = [c for c in (get_center(h) for h in holes) if c is not None]

# --- keep only hole centers in the requested x-range (and y-range if you set it) ---
hole_centers_roi = [(x, y) for (x, y) in hole_centers_all if X1 <= x <= X2 and Y1 <= y <= Y2]

# 7. Plot results
plt.figure(figsize=(16, 8))

plt.subplot(1, 2, 1)
plt.title('Edges')
plt.imshow(edges, cmap='gray')

plt.subplot(1, 2, 2)
plt.title('Contours/Holes/Lines')
plt.imshow(cv2.cvtColor(contour_img, cv2.COLOR_BGR2RGB))

if hole_centers_roi:
    plt.scatter(*zip(*hole_centers_roi), color='blue', s=80, label='Hole Centers (ROI)')
else:
    print("No hole centers inside ROI.")

if line_centers:
    plt.scatter(*zip(*line_centers), color='red', s=80, label='Line Centers')

plt.legend()
plt.show()

# 8. Print positions
print("Hole centers inside ROI (pixel):", hole_centers_roi)
print("Line centers (pixel):", line_centers)
