import cv2
import numpy as np
import matplotlib.pyplot as plt

# 1. Load image
img = cv2.imread('C:\Users\DaniilYegarmin\OneDrive - Mobotic GmbH\Desktop\Photos\WIN_20250804_12_29_34_Pro.jpg')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)

# 2. Edge detection
edges = cv2.Canny(blurred, 50, 150)

# 3. Find contours
contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

# 4. Draw detected contours
contour_img = img.copy()
cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)

# 5. Find holes: contours with parents (hierarchy info)
holes = []
lines = []
for i, cnt in enumerate(contours):
    area = cv2.contourArea(cnt)
    peri = cv2.arcLength(cnt, True)
    if hierarchy[0][i][3] != -1 and area > 100:  # holes (child contours with parent)
        holes.append(cnt)
        cv2.drawContours(contour_img, [cnt], -1, (255, 0, 0), 3)
    elif area > 500 and area < 80000:
        lines.append(cnt)
        cv2.drawContours(contour_img, [cnt], -1, (0, 0, 255), 2)

# 6. Get positions (centers) of holes and lines
def get_center(cnt):
    M = cv2.moments(cnt)
    if M["m00"] == 0: return (0,0)
    cx = int(M["m10"]/M["m00"])
    cy = int(M["m01"]/M["m00"])
    return (cx, cy)

hole_centers = [get_center(c) for c in holes]
line_centers = [get_center(c) for c in lines]

# 7. Plot results
plt.figure(figsize=(16,8))
plt.subplot(1,2,1)
plt.title('Edges')
plt.imshow(edges, cmap='gray')
plt.subplot(1,2,2)
plt.title('Contours/Holes/Lines')
plt.imshow(cv2.cvtColor(contour_img, cv2.COLOR_BGR2RGB))
plt.scatter(*zip(*hole_centers), color='blue', s=80, label='Hole Centers')
plt.scatter(*zip(*line_centers), color='red', s=80, label='Line Centers')
plt.legend()
plt.show()

# 8. Print hole and line positions
print("Hole centers (pixel):", hole_centers)
print("Line centers (pixel):", line_centers)
