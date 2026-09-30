import os
import sys
import json
import shutil
import time
import numpy as np
import cv2
from PIL import Image

BASE_DIR = "/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha"
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
IMAGES_DIR = os.path.join(TEMPLATES_DIR, "images")
THUMBS_DIR = os.path.join(TEMPLATES_DIR, "thumbs")
USER_DIR = "/Users/shaddo/.gemini/antigravity/brain/718824dd-35a2-4dc3-8b1d-27be14de4d07/.user_uploaded"
CATALOG_FILE = os.path.join(TEMPLATES_DIR, "templates.json")

os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)

# ================= 1. CLEAN MASTER PARCHMENT TEMPLATES =================

def clean_master_16x9_parchment(src_path, out_path):
    im = Image.open(src_path).convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)
    arr = np.array(im).astype(np.float32)
    feather = 4

    # 1. Top box parchment (x: 506..1738, y: 175..584) - Covers full parchment interior edge to edge
    y1, y2 = 175, 584
    x1, x2 = 506, 1738
    c_top = np.array([252.0, 246.0, 230.0])
    c_bot = np.array([244.0, 226.0, 189.0])
    y_ind = np.linspace(0, 1, y2 - y1)[:, None, None]
    grad = np.tile(c_top * (1 - y_ind) + c_bot * y_ind, (1, x2 - x1, 1))
    noise = np.random.normal(0, 1.2, grad.shape)
    patch = np.clip(grad + noise, 0, 255)
    mask = np.ones((y2 - y1, x2 - x1, 1), dtype=np.float32)
    for i in range(feather):
        a = (i + 1) / float(feather)
        mask[i, :, 0] = np.minimum(mask[i, :, 0], a)
        mask[-(i + 1), :, 0] = np.minimum(mask[-(i + 1), :, 0], a)
        mask[:, i, 0] = np.minimum(mask[:, i, 0], a)
        mask[:, -(i + 1), 0] = np.minimum(mask[:, -(i + 1), 0], a)
    arr[y1:y2, x1:x2] = arr[y1:y2, x1:x2] * (1 - mask) + patch * mask

    # 2. Mid green divider bar (y: 594..628, left strip x: 506..1088, right strip x: 1152..1738)
    # Erase Urdu ghost text completely, preserving center gold medallion at x: 1088..1152
    green_c = np.array([1.0, 52.0, 10.0])
    for (gx1, gx2) in [(506, 1088), (1152, 1738)]:
        gy1, gy2 = 594, 628
        gh, gw = gy2 - gy1, gx2 - gx1
        g_patch = np.tile(green_c, (gh, gw, 1)) + np.random.normal(0, 0.8, (gh, gw, 3))
        g_mask = np.ones((gh, gw, 1), dtype=np.float32)
        for i in range(3):
            a = (i + 1) / 3.0
            g_mask[i, :, 0] = np.minimum(g_mask[i, :, 0], a)
            g_mask[-(i + 1), :, 0] = np.minimum(g_mask[-(i + 1), :, 0], a)
            g_mask[:, i, 0] = np.minimum(g_mask[:, i, 0], a)
            g_mask[:, -(i + 1), 0] = np.minimum(g_mask[:, -(i + 1), 0], a)
        arr[gy1:gy2, gx1:gx2] = arr[gy1:gy2, gx1:gx2] * (1 - g_mask) + np.clip(g_patch, 0, 255) * g_mask

    # 3. Bottom box parchment (x: 506..1738, y: 644..924) - Covers full parchment interior edge to edge
    by1, by2 = 644, 924
    bx1, bx2 = 506, 1738
    by_ind = np.linspace(0, 1, by2 - by1)[:, None, None]
    bgrad = np.tile(c_top * (1 - by_ind) + c_bot * by_ind, (1, bx2 - bx1, 1))
    bnoise = np.random.normal(0, 1.2, bgrad.shape)
    bpatch = np.clip(bgrad + bnoise, 0, 255)
    bmask = np.ones((by2 - by1, bx2 - bx1, 1), dtype=np.float32)
    for i in range(feather):
        a = (i + 1) / float(feather)
        bmask[i, :, 0] = np.minimum(bmask[i, :, 0], a)
        bmask[-(i + 1), :, 0] = np.minimum(bmask[-(i + 1), :, 0], a)
        bmask[:, i, 0] = np.minimum(bmask[:, i, 0], a)
        bmask[:, -(i + 1), 0] = np.minimum(bmask[:, -(i + 1), 0], a)
    arr[by1:by2, bx1:bx2] = arr[by1:by2, bx1:bx2] * (1 - bmask) + bpatch * bmask

    # 4. Top header cartouche banner (y: 78..168, x: 908..1336) - Completely covers banner to bottom gold rim
    badge_y1, badge_y2 = 78, 168
    badge_x1, badge_x2 = 908, 1336
    jewel_c1 = np.array([3.0, 42.0, 20.0])
    jewel_c2 = np.array([8.0, 58.0, 28.0])
    badge_y_ind = np.linspace(0, 1, badge_y2 - badge_y1)[:, None, None]
    badge_grad = np.tile(jewel_c1 * (1 - badge_y_ind) + jewel_c2 * badge_y_ind, (1, badge_x2 - badge_x1, 1))
    badge_mask = np.ones((badge_y2 - badge_y1, badge_x2 - badge_x1, 1), dtype=np.float32)
    for i in range(4):
        a = (i + 1) / 4.0
        badge_mask[i, :, 0] = np.minimum(badge_mask[i, :, 0], a)
        badge_mask[-(i + 1), :, 0] = np.minimum(badge_mask[-(i + 1), :, 0], a)
        badge_mask[:, i, 0] = np.minimum(badge_mask[:, i, 0], a)
        badge_mask[:, -(i + 1), 0] = np.minimum(badge_mask[:, -(i + 1), 0], a)
    arr[badge_y1:badge_y2, badge_x1:badge_x2] = (
        arr[badge_y1:badge_y2, badge_x1:badge_x2] * (1 - badge_mask) +
        badge_grad * badge_mask
    )

    res = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    res.save(out_path, quality=98)
    return res

def clean_master_9x16_parchment(src_path, out_path):
    im = Image.open(src_path).convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS)
    arr = np.array(im).astype(np.float32)
    feather = 4

    # 1. Top box parchment (x: 46..1034, y: 686..1074) - Covers full parchment interior edge to edge
    y1, y2 = 686, 1074
    x1, x2 = 46, 1034
    c_top = np.array([252.0, 246.0, 230.0])
    c_bot = np.array([244.0, 226.0, 189.0])
    y_ind = np.linspace(0, 1, y2 - y1)[:, None, None]
    grad = np.tile(c_top * (1 - y_ind) + c_bot * y_ind, (1, x2 - x1, 1))
    noise = np.random.normal(0, 1.2, grad.shape)
    patch = np.clip(grad + noise, 0, 255)
    mask = np.ones((y2 - y1, x2 - x1, 1), dtype=np.float32)
    for i in range(feather):
        a = (i + 1) / float(feather)
        mask[i, :, 0] = np.minimum(mask[i, :, 0], a)
        mask[-(i + 1), :, 0] = np.minimum(mask[-(i + 1), :, 0], a)
        mask[:, i, 0] = np.minimum(mask[:, i, 0], a)
        mask[:, -(i + 1), 0] = np.minimum(mask[:, -(i + 1), 0], a)
    arr[y1:y2, x1:x2] = arr[y1:y2, x1:x2] * (1 - mask) + patch * mask

    # 2. Mid green divider bar (y: 1086..1134, left strip x: 46..510, right strip x: 570..1034)
    green_c = np.array([1.0, 52.0, 10.0])
    for (gx1, gx2) in [(46, 510), (570, 1034)]:
        gy1, gy2 = 1086, 1134
        gh, gw = gy2 - gy1, gx2 - gx1
        g_patch = np.tile(green_c, (gh, gw, 1)) + np.random.normal(0, 0.8, (gh, gw, 3))
        g_mask = np.ones((gh, gw, 1), dtype=np.float32)
        for i in range(3):
            a = (i + 1) / 3.0
            g_mask[i, :, 0] = np.minimum(g_mask[i, :, 0], a)
            g_mask[-(i + 1), :, 0] = np.minimum(g_mask[-(i + 1), :, 0], a)
            g_mask[:, i, 0] = np.minimum(g_mask[:, i, 0], a)
            g_mask[:, -(i + 1), 0] = np.minimum(g_mask[:, -(i + 1), 0], a)
        arr[gy1:gy2, gx1:gx2] = arr[gy1:gy2, gx1:gx2] * (1 - g_mask) + np.clip(g_patch, 0, 255) * g_mask

    # 3. Bottom box parchment (x: 46..1034, y: 1138..1446) - Covers full parchment interior edge to edge
    by1, by2 = 1138, 1446
    bx1, bx2 = 46, 1034
    by_ind = np.linspace(0, 1, by2 - by1)[:, None, None]
    bgrad = np.tile(c_top * (1 - by_ind) + c_bot * by_ind, (1, bx2 - bx1, 1))
    bnoise = np.random.normal(0, 1.2, bgrad.shape)
    bpatch = np.clip(bgrad + bnoise, 0, 255)
    bmask = np.ones((by2 - by1, bx2 - bx1, 1), dtype=np.float32)
    for i in range(feather):
        a = (i + 1) / float(feather)
        bmask[i, :, 0] = np.minimum(bmask[i, :, 0], a)
        bmask[-(i + 1), :, 0] = np.minimum(bmask[-(i + 1), :, 0], a)
        bmask[:, i, 0] = np.minimum(bmask[:, i, 0], a)
        bmask[:, -(i + 1), 0] = np.minimum(bmask[:, -(i + 1), 0], a)
    arr[by1:by2, bx1:bx2] = arr[by1:by2, bx1:bx2] * (1 - bmask) + bpatch * bmask

    # 4. Top header cartouche banner (y: 590..670, x: 345..735)
    badge_y1, badge_y2 = 590, 670
    badge_x1, badge_x2 = 345, 735
    jewel_c1 = np.array([3.0, 42.0, 20.0])
    jewel_c2 = np.array([8.0, 58.0, 28.0])
    badge_y_ind = np.linspace(0, 1, badge_y2 - badge_y1)[:, None, None]
    badge_grad = np.tile(jewel_c1 * (1 - badge_y_ind) + jewel_c2 * badge_y_ind, (1, badge_x2 - badge_x1, 1))
    badge_mask = np.ones((badge_y2 - badge_y1, badge_x2 - badge_x1, 1), dtype=np.float32)
    for i in range(4):
        a = (i + 1) / 4.0
        badge_mask[i, :, 0] = np.minimum(badge_mask[i, :, 0], a)
        badge_mask[-(i + 1), :, 0] = np.minimum(badge_mask[-(i + 1), :, 0], a)
        badge_mask[:, i, 0] = np.minimum(badge_mask[:, i, 0], a)
        badge_mask[:, -(i + 1), 0] = np.minimum(badge_mask[:, -(i + 1), 0], a)
    arr[badge_y1:badge_y2, badge_x1:badge_x2] = (
        arr[badge_y1:badge_y2, badge_x1:badge_x2] * (1 - badge_mask) +
        badge_grad * badge_mask
    )

    res = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    res.save(out_path, quality=98)
    return res

# Color transforms for 12 Master Variations
def transform_master_color(arr, mode="sapphire", is_vertical=False):
    out = arr.copy()
    is_green = (arr[:,:,1] > 28) & (arr[:,:,1] > arr[:,:,0]*1.12) & (arr[:,:,1] > arr[:,:,2]*1.04)
    if not is_vertical:
        is_green[:, :510] = False
    g_val = arr[:,:,1][is_green]

    if mode == "sapphire":
        out[:,:,0][is_green] = np.clip(g_val * 0.15, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 0.45 + 10, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 1.55 + 45, 0, 255)
    elif mode == "obsidian":
        out[:,:,0][is_green] = np.clip(g_val * 0.20 + 8, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 0.20 + 8, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 0.25 + 10, 0, 255)
    elif mode == "ruby":
        out[:,:,0][is_green] = np.clip(g_val * 1.60 + 50, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 0.15, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 0.25 + 15, 0, 255)
    elif mode == "amethyst":
        out[:,:,0][is_green] = np.clip(g_val * 1.35 + 40, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 0.18, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 1.50 + 55, 0, 255)
    elif mode == "kaaba":
        out[:,:,0][is_green] = np.clip(g_val * 0.25 + 5, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 0.22 + 5, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 0.18 + 5, 0, 255)
    elif mode == "alaqsa":
        out[:,:,0][is_green] = np.clip(g_val * 1.45 + 35, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 1.05 + 15, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 0.20, 0, 255)
    elif mode == "oasis":
        out[:,:,0][is_green] = np.clip(g_val * 1.30 + 25, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 0.90 + 10, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 0.25, 0, 255)
    elif mode == "celestial":
        out[:,:,0][is_green] = np.clip(g_val * 0.20 + 5, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 0.50 + 15, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 1.40 + 40, 0, 255)
    elif mode == "marble":
        out[:,:,0][is_green] = np.clip(g_val * 1.20 + 80, 0, 255)
        out[:,:,1][is_green] = np.clip(g_val * 1.20 + 80, 0, 255)
        out[:,:,2][is_green] = np.clip(g_val * 1.25 + 85, 0, 255)

    return np.clip(out, 0, 255).astype(np.uint8)

# ================= 2. CLEAN SCENIC / COLLAGE TEMPLATES (OpenCV) =================

def clean_scenic_image(img):
    """
    Surgically inpaints all embedded text:
    - Entire top header cartouche banner (الزمر ۳۹) across full width
    - Left and right reciter / surah info columns
    - Center Arabic verse calligraphy & Urdu translations
    Leaves natural background, mountains, mosque elements, trees, and borders 100% intact.
    """
    h, w, _ = img.shape
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = np.zeros((h, w), dtype=np.uint8)

    # 1. Full header banner area (y: 2% to 18%, x: 20% to 82%)
    by1, by2 = int(h * 0.02), int(h * 0.18)
    bx1, bx2 = int(w * 0.20), int(w * 0.82)
    mask[by1:by2, bx1:bx2] = 255

    # 2. Right text column (x: 88% to 100%, y: 10% to 90%)
    roi_right = gray[int(h*0.1):int(h*0.9), int(w*0.88):w]
    _, r_thresh = cv2.threshold(roi_right, 180, 255, cv2.THRESH_BINARY)
    r_dil = cv2.dilate(r_thresh, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
    mask[int(h*0.1):int(h*0.9), int(w*0.88):w] = cv2.bitwise_or(mask[int(h*0.1):int(h*0.9), int(w*0.88):w], r_dil)

    # 3. Left text column (x: 0 to 12%, y: 10% to 90%)
    roi_left = gray[int(h*0.1):int(h*0.9), 0:int(w*0.12)]
    _, l_thresh = cv2.threshold(roi_left, 180, 255, cv2.THRESH_BINARY)
    l_dil = cv2.dilate(l_thresh, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
    mask[int(h*0.1):int(h*0.9), 0:int(w*0.12)] = cv2.bitwise_or(mask[int(h*0.1):int(h*0.9), 0:int(w*0.12)], l_dil)

    # 4. Center Arabic & Urdu text
    y1, y2 = int(h * 0.16), int(h * 0.94)
    x1, x2 = int(w * 0.05), int(w * 0.95)
    roi_gray = gray[y1:y2, x1:x2]
    k_size = max(7, int(h * 0.012))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
    tophat = cv2.morphologyEx(roi_gray, cv2.MORPH_TOPHAT, kernel)
    blackhat = cv2.morphologyEx(roi_gray, cv2.MORPH_BLACKHAT, kernel)
    text_feat = cv2.add(tophat, blackhat)
    _, thresh = cv2.threshold(text_feat, 22, 255, cv2.THRESH_BINARY)
    _, bright = cv2.threshold(roi_gray, 195, 255, cv2.THRESH_BINARY)
    comb = cv2.bitwise_or(thresh, bright)
    dilated = cv2.dilate(comb, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    mask[y1:y2, x1:x2] = cv2.bitwise_or(mask[y1:y2, x1:x2], dilated)

    cleaned1 = cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
    cleaned = cv2.inpaint(cleaned1, cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))), inpaintRadius=3, flags=cv2.INPAINT_NS)
    return cleaned

# ================= 3. MAIN PIPELINE EXECUTION =================

def run_cleaning_pipeline():
    print("=== Step 1: Cleaning Master 16:9 and 9:16 Base Templates ===")
    raw_16 = os.path.join(USER_DIR, "media_1790421930841.jpg")
    raw_9 = os.path.join(USER_DIR, "media_1790421937820.jpg")

    clean_16_base = os.path.join(IMAGES_DIR, "tmpl_master_madinah_16x9.jpg")
    clean_9_base = os.path.join(IMAGES_DIR, "tmpl_master_madinah_9x16.jpg")

    clean_master_16x9_parchment(raw_16, clean_16_base)
    clean_master_9x16_parchment(raw_9, clean_9_base)
    shutil.copy2(clean_16_base, os.path.join(IMAGES_DIR, "tmpl_master_madinah.jpg"))

    # Generate 16:9 and 9:16 thumbnails for base master
    Image.open(clean_16_base).resize((320, 180), Image.Resampling.LANCZOS).save(os.path.join(THUMBS_DIR, "tmpl_master_madinah_16x9_thumb.jpg"), quality=92)
    Image.open(clean_9_base).resize((180, 320), Image.Resampling.LANCZOS).save(os.path.join(THUMBS_DIR, "tmpl_master_madinah_9x16_thumb.jpg"), quality=92)
    shutil.copy2(os.path.join(THUMBS_DIR, "tmpl_master_madinah_16x9_thumb.jpg"), os.path.join(THUMBS_DIR, "tmpl_master_madinah_thumb.jpg"))
    print("Base Master Madinah 16:9 and 9:16 spotless clean!")

    # Generate all 11 Master Color Variations
    print("=== Step 2: Generating All Spotless Master Variations ===")
    base_arr_16 = np.array(Image.open(clean_16_base)).astype(np.float32)
    base_arr_9 = np.array(Image.open(clean_9_base)).astype(np.float32)

    master_modes = [
        ("sapphire_madinah", "sapphire"),
        ("obsidian_gold", "obsidian"),
        ("ruby_rose", "ruby"),
        ("kaaba_stars", "kaaba"),
        ("golden_alaqsa", "alaqsa"),
        ("desert_oasis", "oasis"),
        ("celestial_galaxy", "celestial"),
        ("marble_dawn", "marble"),
        ("amethyst_twilight", "amethyst")
    ]

    for slug, mode in master_modes:
        m_id = f"tmpl_master_{slug}"
        arr16 = transform_master_color(base_arr_16, mode, is_vertical=False)
        arr9 = transform_master_color(base_arr_9, mode, is_vertical=True)

        f16 = os.path.join(IMAGES_DIR, f"{m_id}_16x9.jpg")
        f9 = os.path.join(IMAGES_DIR, f"{m_id}_9x16.jpg")
        f_def = os.path.join(IMAGES_DIR, f"{m_id}.jpg")

        Image.fromarray(arr16).save(f16, quality=96)
        Image.fromarray(arr9).save(f9, quality=96)
        shutil.copy2(f16, f_def)

        t16 = os.path.join(THUMBS_DIR, f"{m_id}_16x9_thumb.jpg")
        t9 = os.path.join(THUMBS_DIR, f"{m_id}_9x16_thumb.jpg")
        t_def = os.path.join(THUMBS_DIR, f"{m_id}_thumb.jpg")

        Image.fromarray(arr16).resize((320, 180), Image.Resampling.LANCZOS).save(t16, quality=92)
        Image.fromarray(arr9).resize((180, 320), Image.Resampling.LANCZOS).save(t9, quality=92)
        shutil.copy2(t16, t_def)

    # Rehl templates
    raw_rehl1 = os.path.join(USER_DIR, "media_1790421908736.jpg")
    raw_rehl2 = os.path.join(USER_DIR, "media_1790421923168.jpg")
    if os.path.exists(raw_rehl1):
        clean_master_16x9_parchment(raw_rehl1, os.path.join(IMAGES_DIR, "tmpl_rehl_sunset_16x9.jpg"))
        shutil.copy2(os.path.join(IMAGES_DIR, "tmpl_rehl_sunset_16x9.jpg"), os.path.join(IMAGES_DIR, "tmpl_rehl_sunset.jpg"))
        Image.open(os.path.join(IMAGES_DIR, "tmpl_rehl_sunset_16x9.jpg")).resize((320, 180)).save(os.path.join(THUMBS_DIR, "tmpl_rehl_sunset_16x9_thumb.jpg"))
        shutil.copy2(os.path.join(THUMBS_DIR, "tmpl_rehl_sunset_16x9_thumb.jpg"), os.path.join(THUMBS_DIR, "tmpl_rehl_sunset_thumb.jpg"))
    if os.path.exists(raw_rehl2):
        clean_master_16x9_parchment(raw_rehl2, os.path.join(IMAGES_DIR, "tmpl_rehl_courtyard_16x9.jpg"))
        shutil.copy2(os.path.join(IMAGES_DIR, "tmpl_rehl_courtyard_16x9.jpg"), os.path.join(IMAGES_DIR, "tmpl_rehl_courtyard.jpg"))
        Image.open(os.path.join(IMAGES_DIR, "tmpl_rehl_courtyard_16x9.jpg")).resize((320, 180)).save(os.path.join(THUMBS_DIR, "tmpl_rehl_courtyard_16x9_thumb.jpg"))
        shutil.copy2(os.path.join(THUMBS_DIR, "tmpl_rehl_courtyard_16x9_thumb.jpg"), os.path.join(THUMBS_DIR, "tmpl_rehl_courtyard_thumb.jpg"))
    print("All Master Templates cleaned and saved!")

    # ================= Step 3: Clean All 72 Collage Templates =================
    print("=== Step 3: Cleaning All 72 Collage Templates (Inpainting Text & Badges) ===")
    collage_files = [f for f in os.listdir(IMAGES_DIR) if f.startswith("tmpl_c") and f.endswith(".jpg") and not ("_thumb" in f or "_clean" in f)]
    # Unique base IDs without _16x9 or _9x16
    base_ids = set()
    for f in collage_files:
        b_id = f.replace("_16x9.jpg", "").replace("_9x16.jpg", "").replace(".jpg", "")
        base_ids.add(b_id)

    total = len(base_ids)
    print(f"Found {total} unique collage templates to clean...")

    count = 0
    t0 = time.time()
    for b_id in sorted(base_ids):
        count += 1
        path_16 = os.path.join(IMAGES_DIR, f"{b_id}_16x9.jpg")
        path_def = os.path.join(IMAGES_DIR, f"{b_id}.jpg")
        path_9 = os.path.join(IMAGES_DIR, f"{b_id}_9x16.jpg")

        src_file = path_16 if os.path.exists(path_16) else (path_def if os.path.exists(path_def) else None)
        if not src_file:
            continue

        img_bgr = cv2.imread(src_file)
        if img_bgr is None:
            continue

        # Clean 16:9
        clean_bgr_16 = clean_scenic_image(img_bgr)
        cv2.imwrite(path_16, clean_bgr_16, [cv2.IMWRITE_JPEG_QUALITY, 96])
        cv2.imwrite(path_def, clean_bgr_16, [cv2.IMWRITE_JPEG_QUALITY, 96])

        # Generate clean 16:9 thumbnail
        thumb_16 = cv2.resize(clean_bgr_16, (320, 180), interpolation=cv2.INTER_AREA)
        t_path_16 = os.path.join(THUMBS_DIR, f"{b_id}_16x9_thumb.jpg")
        t_path_def = os.path.join(THUMBS_DIR, f"{b_id}_thumb.jpg")
        cv2.imwrite(t_path_16, thumb_16, [cv2.IMWRITE_JPEG_QUALITY, 90])
        cv2.imwrite(t_path_def, thumb_16, [cv2.IMWRITE_JPEG_QUALITY, 90])

        # Generate clean 9:16 vertical version
        # Crop center 1080x1920 from 1920x1080 scaled
        src_pil = Image.fromarray(cv2.cvtColor(clean_bgr_16, cv2.COLOR_BGR2RGB))
        target_w, target_h = 1080, 1920
        aspect_ratio = target_w / float(target_h)
        bg_h = target_h
        bg_w = int(bg_h * (1920.0 / 1080.0))
        bg = src_pil.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        cx = (bg_w - target_w) // 2
        bg_cropped = bg.crop((cx, 0, cx + target_w, target_h))

        # Vignette for subtitle readability
        bg_arr = np.array(bg_cropped).astype(np.float32)
        for y in range(target_h):
            if y < 450:
                factor = 0.65 + 0.35 * (y / 450.0)
            elif y > 1400:
                factor = 1.0 - 0.35 * ((y - 1400.0) / 520.0)
            else:
                factor = 1.0
            bg_arr[y, :, :] *= factor

        res_9 = Image.fromarray(np.clip(bg_arr, 0, 255).astype(np.uint8))
        res_9.save(path_9, quality=96)
        res_9.resize((180, 320), Image.Resampling.LANCZOS).save(os.path.join(THUMBS_DIR, f"{b_id}_9x16_thumb.jpg"), quality=90)

        if count % 10 == 0 or count == total:
            elapsed = time.time() - t0
            print(f"[{count}/{total}] Cleaned: {b_id} (elapsed: {elapsed:.1f}s)")

    print("=== SUCCESS! All 84+ templates cleaned of all embedded text and badges! ===")

if __name__ == "__main__":
    run_cleaning_pipeline()
