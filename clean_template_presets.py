import os
import sys
import numpy as np
from PIL import Image

BASE_DIR = "/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha"
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
IMAGES_DIR = os.path.join(TEMPLATES_DIR, "images")
THUMBS_DIR = os.path.join(TEMPLATES_DIR, "thumbs")
USER_DIR = "/Users/shaddo/.gemini/antigravity/brain/718824dd-35a2-4dc3-8b1d-27be14de4d07/.user_uploaded"

def clean_16x9_parchment(src_path, out_path):
    """Clean 16:9 2-box parchment template with 100% spotless parchment & badge."""
    im = Image.open(src_path).convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)
    arr = np.array(im).astype(np.float32)

    feather = 12
    # 1. Top box parchment (x: 535..1705, y: 172..562)
    y1, y2 = 172, 562
    x1, x2 = 535, 1705
    y_ind = np.linspace(0, 1, y2 - y1)[:, None, None]
    c_top = np.array([251.0, 246.0, 230.0])
    c_bot = np.array([241.0, 224.0, 189.0])
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

    # 2. Bottom box parchment (x: 535..1705, y: 638..892)
    by1, by2 = 638, 892
    bx1, bx2 = 535, 1705
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

    # 3. Top badge: fill inner jewel cartouche cleanly
    badge_y1, badge_y2 = 82, 148
    badge_x1, badge_x2 = 940, 1300
    # Clean jewel emerald gradient
    jewel_c1 = np.array([8.0, 48.0, 26.0])
    jewel_c2 = np.array([14.0, 62.0, 35.0])
    badge_y_ind = np.linspace(0, 1, badge_y2 - badge_y1)[:, None, None]
    badge_grad = np.tile(jewel_c1 * (1 - badge_y_ind) + jewel_c2 * badge_y_ind, (1, badge_x2 - badge_x1, 1))
    badge_mask = np.ones((badge_y2 - badge_y1, badge_x2 - badge_x1, 1), dtype=np.float32)
    b_feather = 6
    for i in range(b_feather):
        a = (i + 1) / float(b_feather)
        badge_mask[i, :, 0] = np.minimum(badge_mask[i, :, 0], a)
        badge_mask[-(i + 1), :, 0] = np.minimum(badge_mask[-(i + 1), :, 0], a)
        badge_mask[:, i, 0] = np.minimum(badge_mask[:, i, 0], a)
        badge_mask[:, -(i + 1), 0] = np.minimum(badge_mask[:, -(i + 1), 0], a)
    arr[badge_y1:badge_y2, badge_x1:badge_x2] = (
        arr[badge_y1:badge_y2, badge_x1:badge_x2] * (1 - badge_mask) +
        badge_grad * badge_mask
    )

    res = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    res.save(out_path, quality=96)
    return res

def clean_9x16_parchment(src_path, out_path):
    """Clean 9:16 vertical 2-box parchment template with 100% spotless parchment & badge."""
    im = Image.open(src_path).convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS)
    arr = np.array(im).astype(np.float32)

    feather = 10
    # 1. Top box: y=685 to 1070, x=60 to 1020
    y1, y2 = 685, 1070
    x1, x2 = 60, 1020
    y_ind = np.linspace(0, 1, y2 - y1)[:, None, None]
    c_top = np.array([251.0, 246.0, 230.0])
    c_bot = np.array([241.0, 224.0, 189.0])
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

    # 2. Bottom box: y=1140 to 1445, x=60 to 1020
    by1, by2 = 1140, 1445
    bx1, bx2 = 60, 1020
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

    # 3. Top badge: y=595 to 665, x=355 to 725
    badge_y1, badge_y2 = 595, 665
    badge_x1, badge_x2 = 355, 725
    jewel_c1 = np.array([8.0, 48.0, 26.0])
    jewel_c2 = np.array([14.0, 62.0, 35.0])
    badge_y_ind = np.linspace(0, 1, badge_y2 - badge_y1)[:, None, None]
    badge_grad = np.tile(jewel_c1 * (1 - badge_y_ind) + jewel_c2 * badge_y_ind, (1, badge_x2 - badge_x1, 1))
    badge_mask = np.ones((badge_y2 - badge_y1, badge_x2 - badge_x1, 1), dtype=np.float32)
    b_feather = 6
    for i in range(b_feather):
        a = (i + 1) / float(b_feather)
        badge_mask[i, :, 0] = np.minimum(badge_mask[i, :, 0], a)
        badge_mask[-(i + 1), :, 0] = np.minimum(badge_mask[-(i + 1), :, 0], a)
        badge_mask[:, i, 0] = np.minimum(badge_mask[:, i, 0], a)
        badge_mask[:, -(i + 1), 0] = np.minimum(badge_mask[:, -(i + 1), 0], a)
    arr[badge_y1:badge_y2, badge_x1:badge_x2] = (
        arr[badge_y1:badge_y2, badge_x1:badge_x2] * (1 - badge_mask) +
        badge_grad * badge_mask
    )

    res = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    res.save(out_path, quality=96)
    return res

if __name__ == "__main__":
    raw_16 = os.path.join(USER_DIR, "media_1790421930841.jpg")
    raw_9 = os.path.join(USER_DIR, "media_1790421937820.jpg")
    
    clean_16 = os.path.join(IMAGES_DIR, "tmpl_master_madinah_16x9.jpg")
    clean_9 = os.path.join(IMAGES_DIR, "tmpl_master_madinah_9x16.jpg")
    
    clean_16x9_parchment(raw_16, clean_16)
    clean_9x16_parchment(raw_9, clean_9)

    raw_rehl1 = os.path.join(USER_DIR, "media_1790421908736.jpg")
    raw_rehl2 = os.path.join(USER_DIR, "media_1790421923168.jpg")
    if os.path.exists(raw_rehl1):
        clean_16x9_parchment(raw_rehl1, os.path.join(IMAGES_DIR, "tmpl_rehl_sunset_16x9.jpg"))
    if os.path.exists(raw_rehl2):
        clean_16x9_parchment(raw_rehl2, os.path.join(IMAGES_DIR, "tmpl_rehl_courtyard_16x9.jpg"))
    print("Cleaned base master images successfully.")
