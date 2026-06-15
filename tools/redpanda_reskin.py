#!/usr/bin/env python3
"""
Red Panda Reskin Tool

Transforms cat sprites into red panda sprites by recoloring fill pixels
while preserving pose geometry, outlines, transparency, and dimensions.

Algorithm:
1. Keep all black outline pixels (0,0,0,255) unchanged — they define the pose.
2. Keep all transparent pixels (0,0,0,0) unchanged — they define the silhouette.
3. Detect "interior features" — black pixels fully surrounded by opaque pixels
   (eyes, nose marks) that lie in the upper half of the character's bounding box.
4. BFS outward from upper-half features through white pixels (radius 3).
5. Cap face pixels at 30% of total white pixels (closest to features first).
6. Recolor face-region white pixels to cream (warm white).
7. Recolor remaining white pixels to reddish-brown (red panda body).
8. Preserve any non-standard colors (e.g., red mouth in yawn2.png).
"""

import os
import sys
import shutil
import numpy as np
from PIL import Image
from collections import deque

# === Red Panda Color Palette ===
BODY_COLOR = np.array([204, 78, 34, 255], dtype=np.uint8)
FACE_COLOR = np.array([255, 232, 210, 255], dtype=np.uint8)

FACE_RADIUS = 3
FACE_FRACTION = 0.30

SPRITES_DIR = os.path.join(os.path.dirname(__file__), "..", "sprites")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "sprites_backup")


def find_interior_features(arr):
    """Find black pixels completely surrounded by non-transparent pixels."""
    features = set()
    h, w = arr.shape[:2]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            r, g, b, a = arr[y, x]
            if a == 0 or r != 0 or g != 0 or b != 0:
                continue
            all_filled = True
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    if arr[y + dy, x + dx, 3] == 0:
                        all_filled = False
                        break
                if not all_filled:
                    break
            if all_filled:
                features.add((y, x))
    return features


def character_bbox(arr):
    """Bounding box of non-transparent pixels: (ymin, ymax, xmin, xmax)."""
    alpha = arr[:, :, 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any():
        return (0, 0, 0, 0)
    ymin, ymax = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1])
    xmin, xmax = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])
    return (ymin, ymax, xmin, xmax)


def find_face_region(arr, interior_features):
    """BFS from upper-half interior features through white, capped by fraction."""
    h, w = arr.shape[:2]
    ymin, ymax, _, _ = character_bbox(arr)
    y_mid = ymin + (ymax - ymin) * 0.50

    upper_features = {(y, x) for y, x in interior_features if y <= y_mid}
    if not upper_features:
        return set()

    white_mask = (
        (arr[:, :, 0] == 255) & (arr[:, :, 1] == 255)
        & (arr[:, :, 2] == 255) & (arr[:, :, 3] == 255)
    )
    total_white = int(white_mask.sum())
    max_face = int(total_white * FACE_FRACTION)

    # BFS recording distances
    distances = {}
    visited = set()
    queue = deque()

    for fy, fx in upper_features:
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            ny, nx = fy + dy, fx + dx
            if 0 <= ny < h and 0 <= nx < w and white_mask[ny, nx]:
                if (ny, nx) not in visited:
                    queue.append((ny, nx, 1))
                    visited.add((ny, nx))

    while queue:
        y, x, dist = queue.popleft()
        distances[(y, x)] = dist
        if dist < FACE_RADIUS:
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and white_mask[ny, nx]:
                    if (ny, nx) not in visited:
                        queue.append((ny, nx, dist + 1))
                        visited.add((ny, nx))

    # Take closest pixels up to the cap
    sorted_pixels = sorted(distances.items(), key=lambda item: item[1])
    face_pixels = set(p for p, _ in sorted_pixels[:max_face])
    return face_pixels


def reskin_sprite(arr):
    """Reskin a single sprite array and return (result, face_count, body_count)."""
    h, w = arr.shape[:2]

    white_mask = (
        (arr[:, :, 0] == 255)
        & (arr[:, :, 1] == 255)
        & (arr[:, :, 2] == 255)
        & (arr[:, :, 3] == 255)
    )

    white_count = int(white_mask.sum())
    if white_count == 0:
        return arr, 0, 0

    interior_features = find_interior_features(arr)
    face_pixels = find_face_region(arr, interior_features) if interior_features else set()

    result = arr.copy()
    face_count = 0
    body_count = 0

    for y in range(h):
        for x in range(w):
            if white_mask[y, x]:
                if (y, x) in face_pixels:
                    result[y, x] = FACE_COLOR
                    face_count += 1
                else:
                    result[y, x] = BODY_COLOR
                    body_count += 1

    return result, face_count, body_count


def main():
    sprites_dir = os.path.normpath(SPRITES_DIR)
    backup_dir = os.path.normpath(BACKUP_DIR)

    if not os.path.isdir(sprites_dir):
        print(f"ERROR: sprites directory not found: {sprites_dir}", file=sys.stderr)
        sys.exit(1)

    # Restore from backup before re-processing
    if os.path.isdir(backup_dir):
        print(f"Restoring originals from {backup_dir} before reskinning...")
        for f in os.listdir(backup_dir):
            if f.endswith(".png"):
                shutil.copy2(os.path.join(backup_dir, f), os.path.join(sprites_dir, f))
    else:
        shutil.copytree(sprites_dir, backup_dir)
        print(f"Backed up originals to {backup_dir}")

    sprite_files = sorted(f for f in os.listdir(sprites_dir) if f.endswith(".png"))

    if not sprite_files:
        print("ERROR: no PNG files found in sprites/", file=sys.stderr)
        sys.exit(1)

    print(f"\nProcessing {len(sprite_files)} sprites...\n")
    print(f"{'Sprite':<25} {'Face px':>8} {'Body px':>8} {'Total':>8} {'Face%':>6}")
    print("-" * 65)

    total_face = 0
    total_body = 0
    skipped = 0

    for filename in sprite_files:
        filepath = os.path.join(sprites_dir, filename)
        img = Image.open(filepath).convert("RGBA")
        arr = np.array(img)

        result, face_count, body_count = reskin_sprite(arr)
        total_px = face_count + body_count

        if total_px == 0:
            print(f"{filename:<25} {'—':>8} {'—':>8} {'—':>8} {'—':>6} skipped")
            skipped += 1
        else:
            Image.fromarray(result).save(filepath)
            pct = f"{face_count/total_px*100:.0f}%"
            total_face += face_count
            total_body += body_count
            print(f"{filename:<25} {face_count:>8} {body_count:>8} {total_px:>8} {pct:>6}")

    print("-" * 65)
    print(f"Totals: {len(sprite_files)} sprites, "
          f"{len(sprite_files) - skipped} reskinned, {skipped} skipped")
    print(f"Pixels: {total_face} face (cream) + {total_body} body (reddish-brown) "
          f"= {total_face + total_body}")
    print(f"Overall face ratio: {total_face / (total_face + total_body) * 100:.1f}%")


if __name__ == "__main__":
    main()
