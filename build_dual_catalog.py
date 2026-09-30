import os
import sys
import json
import re
import shutil
import numpy as np
from PIL import Image

BASE_DIR = "/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha"
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
IMAGES_DIR = os.path.join(TEMPLATES_DIR, "images")
THUMBS_DIR = os.path.join(TEMPLATES_DIR, "thumbs")
CATALOG_FILE = os.path.join(TEMPLATES_DIR, "templates.json")

# 1. Generate 12th Master Template: Amethyst Twilight (Deep Purple / Violet & Royal Gold)
print("=== Generating 12th Master: Royal Amethyst Twilight ===")
base_16x9 = np.array(Image.open(os.path.join(IMAGES_DIR, "tmpl_master_madinah_16x9.jpg"))).astype(np.float32)
base_9x16 = np.array(Image.open(os.path.join(IMAGES_DIR, "tmpl_master_madinah_9x16.jpg"))).astype(np.float32)

def make_amethyst(arr, is_vertical=False):
    out = arr.copy()
    is_green = (arr[:,:,1] > 28) & (arr[:,:,1] > arr[:,:,0]*1.15) & (arr[:,:,1] > arr[:,:,2]*1.05)
    if not is_vertical:
        is_green[:, :510] = False
    g_val = arr[:,:,1][is_green]
    # Deep royal amethyst purple
    out[:,:,0][is_green] = np.clip(g_val * 1.35 + 40, 0, 255)
    out[:,:,1][is_green] = g_val * 0.18
    out[:,:,2][is_green] = np.clip(g_val * 1.50 + 55, 0, 255)
    if not is_vertical:
        out[:,:510,0] = np.clip(out[:,:510,0] * 1.05, 0, 255)
        out[:,:510,2] = np.clip(out[:,:510,2] * 1.10, 0, 255)
    return np.clip(out, 0, 255).astype(np.uint8)

arr_amethyst_16 = make_amethyst(base_16x9, is_vertical=False)
arr_amethyst_9 = make_amethyst(base_9x16, is_vertical=True)

im_am_16 = Image.fromarray(arr_amethyst_16)
im_am_16.save(os.path.join(IMAGES_DIR, "tmpl_master_amethyst_twilight_16x9.jpg"), quality=95)
im_am_16.resize((320, 180), Image.Resampling.LANCZOS).save(os.path.join(THUMBS_DIR, "tmpl_master_amethyst_twilight_16x9_thumb.jpg"), quality=90)

im_am_9 = Image.fromarray(arr_amethyst_9)
im_am_9.save(os.path.join(IMAGES_DIR, "tmpl_master_amethyst_twilight_9x16.jpg"), quality=95)
im_am_9.resize((180, 320), Image.Resampling.LANCZOS).save(os.path.join(THUMBS_DIR, "tmpl_master_amethyst_twilight_9x16_thumb.jpg"), quality=90)
print("Saved tmpl_master_amethyst_twilight (16:9 and 9:16) successfully.")

# 12 Flagship Master Templates Definition
MASTER_TEMPLATES = [
    {
        "id": "tmpl_master_madinah",
        "name": "Master Emerald & Gold Madinah Sunset",
        "category": "Emerald & Gold Luxury",
        "style": "emerald_gold"
    },
    {
        "id": "tmpl_master_sapphire_madinah",
        "name": "Royal Sapphire & Gold Madinah Twilight",
        "category": "Emerald & Gold Luxury",
        "style": "dark_luxury"
    },
    {
        "id": "tmpl_master_obsidian_gold",
        "name": "Black Obsidian & Gold Royal Palace",
        "category": "Dark Luxury & Gold",
        "style": "dark_luxury"
    },
    {
        "id": "tmpl_master_ruby_rose",
        "name": "Ruby Rose & Oud Royal Archway",
        "category": "Floral & Serene Gardens",
        "style": "cherry_blossom_rose"
    },
    {
        "id": "tmpl_master_kaaba_stars",
        "name": "Royal Kaaba under Celestial Stars",
        "category": "Mosques & Holy Sites",
        "style": "dark_luxury"
    },
    {
        "id": "tmpl_master_golden_alaqsa",
        "name": "Golden Al-Aqsa Dome at Sunset",
        "category": "Mosques & Holy Sites",
        "style": "emerald_gold"
    },
    {
        "id": "tmpl_master_desert_oasis",
        "name": "Warm Desert Oasis & Glowing Lanterns",
        "category": "Nature & Waterfalls",
        "style": "emerald_gold"
    },
    {
        "id": "tmpl_master_celestial_galaxy",
        "name": "Celestial Earth Orbit & Milky Way",
        "category": "Cosmic & Deep Ocean",
        "style": "dark_luxury"
    },
    {
        "id": "tmpl_master_marble_dawn",
        "name": "White Marble Mosque Colonnade at Dawn",
        "category": "Mosques & Holy Sites",
        "style": "cinematic_clean"
    },
    {
        "id": "tmpl_master_amethyst_twilight",
        "name": "Royal Amethyst Twilight & Gold Calligraphy",
        "category": "Dark Luxury & Gold",
        "style": "dark_luxury"
    },
    {
        "id": "tmpl_rehl_sunset",
        "name": "Holy Quran on Rehl in Madinah Sunset",
        "category": "Sacred Quran & Lanterns",
        "style": "emerald_gold"
    },
    {
        "id": "tmpl_rehl_courtyard",
        "name": "Madinah Courtyard with Golden Lanterns & Rehl",
        "category": "Sacred Quran & Lanterns",
        "style": "emerald_gold"
    }
]

# 2. Cinematic 9:16 Generator for Collage Templates
def make_9x16_cinematic(src_path, out_img, out_thumb):
    src = Image.open(src_path)
    sw, sh = src.size # 1920, 1080
    target_w, target_h = 1080, 1920
    scale = max(target_w / sw, target_h / sh)
    bg_w, bg_h = int(sw * scale), int(sh * scale)
    bg = src.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    cx = (bg_w - target_w) // 2
    cy = (bg_h - target_h) // 2
    bg_cropped = bg.crop((cx, cy, cx + target_w, cy + target_h))
    
    # Subtle vignette for video subtitle clarity
    bg_arr = np.array(bg_cropped).astype(np.float32)
    for y in range(target_h):
        if y < 450:
            factor = 0.55 + 0.45 * (y / 450.0)
        elif y > 1400:
            factor = 1.0 - 0.40 * ((y - 1400.0) / 520.0)
        else:
            factor = 1.0
        bg_arr[y, :, :] *= factor
        
    res = Image.fromarray(np.clip(bg_arr, 0, 255).astype(np.uint8))
    res.save(out_img, quality=95)
    
    # 180x320 thumbnail
    thumb = res.resize((180, 320), Image.Resampling.LANCZOS)
    thumb.save(out_thumb, quality=90)

# Import themes from template_manager
from template_manager import COLLAGE_THEMES

catalog = []

# First, register 12 Master Templates (Parchment & Plaque)
print("=== Registering 12 Master Templates ===")
for m in MASTER_TEMPLATES:
    m_id = m["id"]
    f_16 = f"{m_id}_16x9.jpg"
    f_9 = f"{m_id}_9x16.jpg"
    t_16 = f"{m_id}_16x9_thumb.jpg"
    t_9 = f"{m_id}_9x16_thumb.jpg"
    
    # Also create non-suffixed copy if needed
    f_default = f"{m_id}.jpg"
    t_default = f"{m_id}_thumb.jpg"
    if not os.path.exists(os.path.join(IMAGES_DIR, f_default)):
        shutil.copy2(os.path.join(IMAGES_DIR, f_16), os.path.join(IMAGES_DIR, f_default))
    if not os.path.exists(os.path.join(THUMBS_DIR, t_default)):
        shutil.copy2(os.path.join(THUMBS_DIR, t_16), os.path.join(THUMBS_DIR, t_default))
        
    entry = {
        "id": m_id,
        "name": m["name"],
        "category": m["category"],
        "style": m["style"],
        "aspect": "both",
        "is_master": True,
        "image_url": f"/templates/images/{f_16}",
        "thumb_url": f"/templates/thumbs/{t_16}",
        "image_path": os.path.join(IMAGES_DIR, f_16),
        "image_16x9": f"/templates/images/{f_16}",
        "image_9x16": f"/templates/images/{f_9}",
        "thumb_16x9": f"/templates/thumbs/{t_16}",
        "thumb_9x16": f"/templates/thumbs/{t_9}",
        "image_path_16x9": os.path.join(IMAGES_DIR, f_16),
        "image_path_9x16": os.path.join(IMAGES_DIR, f_9)
    }
    catalog.append(entry)

print(f"Registered {len(catalog)} Master Templates.")

# Next, process and register all 72 Collage Templates
print("=== Processing 72 Collage Templates for Dual Ratios (16:9 and 9:16) ===")
collage_count = 0
for c_idx, theme in enumerate(COLLAGE_THEMES):
    prefix = theme["prefix"]
    for tile_slug, tile_name, tile_cat in theme["tiles"]:
        t_id = f"tmpl_{prefix}_{tile_slug}"
        src_16 = os.path.join(IMAGES_DIR, f"{t_id}.jpg")
        if not os.path.exists(src_16):
            print(f"Warning: source {src_16} missing!")
            continue
            
        f_16 = f"{t_id}_16x9.jpg"
        f_9 = f"{t_id}_9x16.jpg"
        t_16 = f"{t_id}_16x9_thumb.jpg"
        t_9 = f"{t_id}_9x16_thumb.jpg"
        
        path_16 = os.path.join(IMAGES_DIR, f_16)
        path_9 = os.path.join(IMAGES_DIR, f_9)
        path_t16 = os.path.join(THUMBS_DIR, t_16)
        path_t9 = os.path.join(THUMBS_DIR, t_9)
        
        # Ensure 16:9 file and thumb
        if not os.path.exists(path_16):
            shutil.copy2(src_16, path_16)
        src_thumb = os.path.join(THUMBS_DIR, f"{t_id}_thumb.jpg")
        if os.path.exists(src_thumb) and not os.path.exists(path_t16):
            shutil.copy2(src_thumb, path_t16)
        elif not os.path.exists(path_t16):
            Image.open(src_16).resize((320, 180), Image.Resampling.LANCZOS).save(path_t16, quality=90)
            
        # Ensure 9:16 file and thumb
        if not os.path.exists(path_9) or not os.path.exists(path_t9):
            make_9x16_cinematic(src_16, path_9, path_t9)
            
        entry = {
            "id": t_id,
            "name": tile_name,
            "category": tile_cat,
            "style": theme.get("style", "emerald_gold"),
            "aspect": "both",
            "is_master": False,
            "image_url": f"/templates/images/{f_16}",
            "thumb_url": f"/templates/thumbs/{t_16}",
            "image_path": path_16,
            "image_16x9": f"/templates/images/{f_16}",
            "image_9x16": f"/templates/images/{f_9}",
            "thumb_16x9": f"/templates/thumbs/{t_16}",
            "thumb_9x16": f"/templates/thumbs/{t_9}",
            "image_path_16x9": path_16,
            "image_path_9x16": path_9
        }
        catalog.append(entry)
        collage_count += 1

print(f"Total collages processed: {collage_count}")
print(f"Total unified templates in catalog: {len(catalog)}")

with open(CATALOG_FILE, "w", encoding="utf-8") as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print("Saved catalog to", CATALOG_FILE)
