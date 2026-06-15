#!/usr/bin/env python3
"""
Red Panda Sprite Validation Tool

Compares reskinned sprites against original backups to verify that the reskin
preserved all structural properties while only changing fill colors.

Checks:
1. Dimensions — every sprite must be 32x32.
2. Transparency — alpha channel must be identical to original.
3. Bounding box — non-transparent bounding box must match original.
4. Sprite center — centroid of non-transparent pixels must match original.
5. Duplicate frames — no two reskinned sprites should be pixel-identical.
6. Missing frames — all required sprite files exist.
7. Sheet dimensions — assets/neko.png must be 256x128 (if it exists).
8. Outline preservation — black outline pixels must be unchanged.
9. Fill coverage — every original white pixel must now be a non-white color.
"""

import os
import sys
import numpy as np
from PIL import Image
from itertools import combinations

BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SPRITES_DIR = os.path.join(BASE_DIR, "sprites")
BACKUP_DIR = os.path.join(BASE_DIR, "sprites_backup")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

REQUIRED_SPRITES = [
    "up1.png", "up2.png",
    "upright1.png", "upright2.png",
    "right1.png", "right2.png",
    "downright1.png", "downright2.png",
    "down1.png", "down2.png",
    "downleft1.png", "downleft2.png",
    "left1.png", "left2.png",
    "upleft1.png", "upleft2.png",
    "awake.png",
    "sleep1.png", "sleep2.png",
    "yawn1.png", "yawn2.png",
    "scratch1.png", "scratch2.png",
    "wash1.png",
]

ALL_EXPECTED = REQUIRED_SPRITES + [
    "downclaw1.png", "downclaw2.png",
    "leftclaw1.png", "leftclaw2.png",
    "rightclaw1.png", "rightclaw2.png",
    "upclaw1.png", "upclaw2.png",
    "fp_down.png", "fp_downleft.png", "fp_downright.png",
    "fp_left.png", "fp_right.png", "fp_up.png",
    "fp_upleft.png", "fp_upright.png",
]


def bounding_box(alpha):
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any():
        return (0, 0, 0, 0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    return (int(rmin), int(cmin), int(rmax), int(cmax))


def centroid(alpha):
    ys, xs = np.where(alpha > 0)
    if len(ys) == 0:
        return (0.0, 0.0)
    return (float(np.mean(ys)), float(np.mean(xs)))


class ValidationReport:
    def __init__(self):
        self.checks = []
        self.passed = 0
        self.failed = 0
        self.warned = 0

    def check(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        self.checks.append((status, name, detail))
        if ok:
            self.passed += 1
        else:
            self.failed += 1

    def warn(self, name, detail=""):
        self.checks.append(("WARN", name, detail))
        self.warned += 1

    def print_report(self):
        print("\n" + "=" * 70)
        print("RED PANDA SPRITE VALIDATION REPORT")
        print("=" * 70)

        for status, name, detail in self.checks:
            icon = {"PASS": "+", "FAIL": "!", "WARN": "?"}[status]
            line = f"  [{icon}] {status}: {name}"
            if detail:
                line += f" — {detail}"
            print(line)

        print("-" * 70)
        print(f"  Results: {self.passed} passed, {self.failed} failed, {self.warned} warnings")
        print("=" * 70)

        return self.failed == 0


def main():
    report = ValidationReport()

    has_backups = os.path.isdir(BACKUP_DIR)
    if not has_backups:
        report.warn("Backup directory", f"{BACKUP_DIR} not found, skipping comparison checks")

    # --- Check 6: Missing frames ---
    for sprite in REQUIRED_SPRITES:
        path = os.path.join(SPRITES_DIR, sprite)
        report.check(f"Required file: {sprite}", os.path.isfile(path))

    # --- Load all current sprites ---
    sprite_files = sorted(f for f in os.listdir(SPRITES_DIR) if f.endswith(".png"))
    sprites = {}
    for filename in sprite_files:
        img = Image.open(os.path.join(SPRITES_DIR, filename)).convert("RGBA")
        sprites[filename] = np.array(img)

    # --- Check 1: Dimensions ---
    for filename, arr in sprites.items():
        h, w = arr.shape[:2]
        report.check(f"Dimensions: {filename}", h == 32 and w == 32, f"{w}x{h}")

    # --- Checks 2, 3, 4, 8, 9: Compare against originals ---
    if has_backups:
        for filename, new_arr in sprites.items():
            backup_path = os.path.join(BACKUP_DIR, filename)
            if not os.path.isfile(backup_path):
                report.warn(f"No backup for {filename}", "cannot compare")
                continue

            orig = np.array(Image.open(backup_path).convert("RGBA"))

            # Check 2: Transparency (alpha channel identical)
            alpha_match = np.array_equal(new_arr[:, :, 3], orig[:, :, 3])
            report.check(f"Alpha preserved: {filename}", alpha_match)

            # Check 3: Bounding box
            orig_bb = bounding_box(orig[:, :, 3])
            new_bb = bounding_box(new_arr[:, :, 3])
            report.check(f"Bounding box: {filename}", orig_bb == new_bb,
                         f"orig={orig_bb} new={new_bb}")

            # Check 4: Sprite center
            orig_c = centroid(orig[:, :, 3])
            new_c = centroid(new_arr[:, :, 3])
            dist = ((orig_c[0] - new_c[0]) ** 2 + (orig_c[1] - new_c[1]) ** 2) ** 0.5
            report.check(f"Centroid: {filename}", dist < 0.01,
                         f"orig=({orig_c[0]:.2f},{orig_c[1]:.2f}) "
                         f"new=({new_c[0]:.2f},{new_c[1]:.2f}) dist={dist:.4f}")

            # Check 8: Outline preservation
            orig_black = (
                (orig[:, :, 0] == 0) & (orig[:, :, 1] == 0)
                & (orig[:, :, 2] == 0) & (orig[:, :, 3] == 255)
            )
            new_pixels_at_outlines = new_arr[orig_black]
            if len(new_pixels_at_outlines) > 0:
                outlines_ok = np.all(
                    (new_pixels_at_outlines[:, 0] == 0)
                    & (new_pixels_at_outlines[:, 1] == 0)
                    & (new_pixels_at_outlines[:, 2] == 0)
                    & (new_pixels_at_outlines[:, 3] == 255)
                )
            else:
                outlines_ok = True
            report.check(f"Outlines preserved: {filename}", bool(outlines_ok))

            # Check 9: Fill coverage (no original white pixels left white)
            orig_white = (
                (orig[:, :, 0] == 255) & (orig[:, :, 1] == 255)
                & (orig[:, :, 2] == 255) & (orig[:, :, 3] == 255)
            )
            if orig_white.any():
                still_white = (
                    (new_arr[:, :, 0] == 255) & (new_arr[:, :, 1] == 255)
                    & (new_arr[:, :, 2] == 255) & (new_arr[:, :, 3] == 255)
                )
                remaining = int((orig_white & still_white).sum())
                report.check(f"Fill recolored: {filename}", remaining == 0,
                             f"{remaining} white pixels remain" if remaining else "")
            else:
                report.check(f"Fill recolored: {filename}", True, "no fill pixels (footprint)")

    # --- Check 5: Duplicate frames ---
    required_hashes = {}
    for filename in REQUIRED_SPRITES:
        if filename in sprites:
            h = sprites[filename].tobytes()
            required_hashes.setdefault(h, []).append(filename)

    for h, names in required_hashes.items():
        if len(names) > 1:
            report.check(f"No duplicates: {', '.join(names)}", False,
                         "these sprites are pixel-identical")

    if all(len(v) == 1 for v in required_hashes.values()):
        report.check("No duplicate frames among required sprites", True,
                     f"{len(required_hashes)} unique frames")

    # --- Check 7: Sheet dimensions ---
    sheet_path = os.path.join(ASSETS_DIR, "neko.png")
    if os.path.isfile(sheet_path):
        sheet = Image.open(sheet_path)
        sw, sh = sheet.size
        report.check("Sheet dimensions", sw == 256 and sh == 128, f"{sw}x{sh}")
    else:
        report.warn("Sheet file", "assets/neko.png not found, regenerate with GENSHEET=1")

    # --- Print report ---
    all_passed = report.print_report()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
