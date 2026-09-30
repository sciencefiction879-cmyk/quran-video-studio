import os
import sys
import json
import subprocess
import time
import glob
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
IMAGES_DIR = os.path.join(TEMPLATES_DIR, "images")
THUMBS_DIR = os.path.join(TEMPLATES_DIR, "thumbs")
CATALOG_FILE = os.path.join(TEMPLATES_DIR, "templates.json")

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)

# Predefined naming themes for the 8 collages
COLLAGE_THEMES = [
    # Collage 1: media_1790421831321
    {
        "prefix": "c1_cinematic",
        "category": "Cinematic & Nature",
        "style": "cinematic_clean",
        "tiles": [
            ("mosque_sunlight_arch", "Sunlight Arch in Sacred Mosque", "Mosques & Holy Sites"),
            ("earth_space_orbit", "Celestial Earth from Orbit", "Cosmic & Deep Ocean"),
            ("sunlit_green_tree", "Tree of Life under Bright Sky", "Nature & Waterfalls"),
            ("sunset_stone_path", "Stone Path Toward Golden Sunset", "Nature & Waterfalls"),
            ("parchment_gold_border", "Parchment Manuscript with Floral Border", "Ancient Scrolls & Arches"),
            ("quran_lantern_library", "Holy Quran & Glowing Lantern Library", "Sacred Quran & Lanterns"),
            ("underwater_coral_reef", "Deep Ocean Coral Reef & Sunbeams", "Cosmic & Deep Ocean"),
            ("mountain_peak_sunrise", "Serene Mountain Sunrise above Clouds", "Nature & Waterfalls"),
            ("night_mosque_full_moon", "Sacred Night Mosque & Glowing Full Moon", "Mosques & Holy Sites")
        ]
    },
    # Collage 2: media_1790421837369
    {
        "prefix": "c2_framed",
        "category": "Emerald & Gold Luxury",
        "style": "emerald_gold",
        "tiles": [
            ("kaaba_night_moon", "Kaaba Sharif Night Courtyard & Moon", "Mosques & Holy Sites"),
            ("mountain_valley_rehl", "Mountain Valley Sunrise with Holy Quran", "Sacred Quran & Lanterns"),
            ("library_candle_lantern", "Scholarly Library with Warm Candlelight", "Sacred Quran & Lanterns"),
            ("tropical_waterfall_garden", "Tropical Waterfall & Paradise Garden", "Nature & Waterfalls"),
            ("crescent_space_dawn", "Crescent Moon & Earth Dawn from Space", "Cosmic & Deep Ocean"),
            ("marble_mosque_palace", "White Marble Mosque Palace Archway", "Ancient Scrolls & Arches"),
            ("palm_river_sunset", "Date Palm River Sunset Oasis", "Nature & Waterfalls"),
            ("waterfront_night_mosque", "Illuminated Waterfront Mosque & Crescent", "Mosques & Holy Sites"),
            ("madinah_garden_dome", "Madinah Courtyard with Green Dome View", "Mosques & Holy Sites")
        ]
    },
    # Collage 3: media_1790421843734
    {
        "prefix": "c3_dark_luxury",
        "category": "Dark Luxury & Gold",
        "style": "dark_luxury",
        "tiles": [
            ("royal_kaaba_stars", "Royal Kaaba Courtyard under Starry Sky", "Mosques & Holy Sites"),
            ("alpine_quran_horizon", "Alpine Mountain Valley with Quran on Rehl", "Sacred Quran & Lanterns"),
            ("grand_library_lanterns", "Historic Islamic Library with Hanging Lanterns", "Sacred Quran & Lanterns"),
            ("paradise_cascade_arch", "Paradise Waterfalls through Archway", "Nature & Waterfalls"),
            ("solar_eclipse_earth", "Solar Corona & Blue Earth Sphere", "Cosmic & Deep Ocean"),
            ("golden_hall_arches", "Royal Islamic Hall with Golden Chandelier", "Ancient Scrolls & Arches"),
            ("oasis_sunset_palms", "Desert Oasis Sunset with Ancient Rehl", "Nature & Waterfalls"),
            ("medina_night_lake", "Madinah Mosque Reflection in Calm Waters", "Mosques & Holy Sites"),
            ("palace_garden_balcony", "Palace Balcony overlooking Madinah Domes", "Ancient Scrolls & Arches")
        ]
    },
    # Collage 4: media_1790421850356
    {
        "prefix": "c4_floral_pastel",
        "category": "Floral & Serene Gardens",
        "style": "cherry_blossom_rose",
        "tiles": [
            ("madinah_cherry_blossom", "Prophet's Mosque with Pink Spring Blossoms", "Mosques & Holy Sites"),
            ("madinah_night_moonlight", "Grand Madinah Mosque under Glowing Moon", "Mosques & Holy Sites"),
            ("valley_cascade_sunrise", "Mountain Stream Cascade at Golden Dawn", "Nature & Waterfalls"),
            ("rose_garden_archway", "Rose Garden with Islamic Archway", "Nature & Waterfalls"),
            ("misty_valley_mountains", "Misty Blue Mountain Valley at Sunrise", "Nature & Waterfalls"),
            ("heritage_library_parchment", "Heritage Library with Manuscript Books", "Sacred Quran & Lanterns"),
            ("marble_courtyard_sunset", "White Marble Courtyard at Sunset", "Mosques & Holy Sites"),
            ("cosmic_nebula_horizon", "Cosmic Galaxy Nebula above Planet Horizon", "Cosmic & Deep Ocean"),
            ("spring_lantern_oasis", "Spring Flowers with Illuminated Lantern", "Nature & Waterfalls")
        ]
    },
    # Collage 5: media_1790421877906
    {
        "prefix": "c5_autumn_nature",
        "category": "Nature & Waterfalls",
        "style": "emerald_gold",
        "tiles": [
            ("madinah_morning_sun", "Madinah Green Dome in Golden Morning Sun", "Mosques & Holy Sites"),
            ("night_minarets_moon", "Majestic Night Minarets & Crescent Moon", "Mosques & Holy Sites"),
            ("autumn_red_waterfall", "Autumn Red Maple River & Waterfall", "Nature & Waterfalls"),
            ("stained_glass_mosque", "Stained Glass Mosque Windows with Sunbeams", "Ancient Scrolls & Arches"),
            ("golden_cloud_mountains", "Golden Cloud Sea above Majestic Peaks", "Nature & Waterfalls"),
            ("tea_lantern_library", "Cozy Library Table with Tea & Quran", "Sacred Quran & Lanterns"),
            ("crystal_ocean_corals", "Crystal Turquoise Ocean with Exotic Fish", "Cosmic & Deep Ocean"),
            ("mountain_cave_waterfall", "Paradise Waterfall seen from Grotto Cave", "Nature & Waterfalls"),
            ("desert_palace_night", "Desert Palace at Night with Glowing Lanterns", "Ancient Scrolls & Arches")
        ]
    },
    # Collage 6: media_1790421890870
    {
        "prefix": "c6_emerald_arches",
        "category": "Emerald & Gold Luxury",
        "style": "emerald_gold",
        "tiles": [
            ("kaaba_gold_glow", "Holy Kaaba with Golden Divine Aura", "Mosques & Holy Sites"),
            ("misty_summit_rehl", "Misty Mountain Summit with Wooden Rehl", "Nature & Waterfalls"),
            ("vintage_reading_lantern", "Vintage Quran Reading Desk with Lantern", "Sacred Quran & Lanterns"),
            ("pink_petals_madinah", "Pink Petals Garden overlooking Green Dome", "Mosques & Holy Sites"),
            ("space_crescent_earth", "Space Crescent Orbit over Mother Earth", "Cosmic & Deep Ocean"),
            ("tropical_river_paradise", "Emerald Tropical River with Waterfall", "Nature & Waterfalls"),
            ("sunset_palace_lanterns", "Sunset Mosque Palace with Twin Lanterns", "Ancient Scrolls & Arches"),
            ("marble_veranda_madinah", "Marble Veranda overlooking Prophet Mosque", "Mosques & Holy Sites"),
            ("starry_night_lake_mosque", "Starry Night Lake with Glowing Mosque", "Mosques & Holy Sites")
        ]
    },
    # Collage 7: media_1790421896415
    {
        "prefix": "c7_parchment_scrolls",
        "category": "Ancient Scrolls & Arches",
        "style": "parchment_scroll",
        "tiles": [
            ("ancient_papyrus_scroll", "Ancient Papyrus Scroll with Royal Lanterns", "Ancient Scrolls & Arches"),
            ("blue_lagoon_night_mosque", "Blue Lagoon Mosque with Radiant Full Moon", "Mosques & Holy Sites"),
            ("sunburst_over_peaks", "Golden Sunburst over Mountain Horizon", "Nature & Waterfalls"),
            ("lush_paradise_stream", "Lush Paradise Stream with Greenery", "Nature & Waterfalls"),
            ("marble_colonnade_madinah", "Marble Colonnade Archways of Madinah", "Mosques & Holy Sites"),
            ("gold_filigree_black_hall", "Gold Filigree Arch over Obsidian Hall", "Dark Luxury & Gold"),
            ("spring_blossoms_dome", "Spring Cherry Blossoms around Green Dome", "Mosques & Holy Sites"),
            ("sunset_silhouettes_mosque", "Sunset City Silhouettes through Arched Window", "Mosques & Holy Sites"),
            ("coastal_sea_arch", "Coastal Sea Cliff with Emerald Waves", "Nature & Waterfalls")
        ]
    },
    # Collage 8: media_1790421902485
    {
        "prefix": "c8_turquoise_night",
        "category": "Dark Luxury & Gold",
        "style": "dark_luxury",
        "tiles": [
            ("royal_black_gold_card", "Royal Black & Gold Ornate Floral Card", "Dark Luxury & Gold"),
            ("emerald_forest_falls", "Emerald Forest Cascading Waterfalls", "Nature & Waterfalls"),
            ("golden_twilight_peaks", "Golden Twilight Mountain Range with Quran", "Nature & Waterfalls"),
            ("white_palace_blue_sky", "White Islamic Palace under Clear Blue Sky", "Ancient Scrolls & Arches"),
            ("planetary_sunburst_dawn", "Planetary Sunburst Dawn from Deep Space", "Cosmic & Deep Ocean"),
            ("ancient_scroll_desk", "Ancient Script Scroll on Carved Wood Desk", "Ancient Scrolls & Arches"),
            ("cherry_blossom_pavilion", "Pink Cherry Blossom Garden Pavilion", "Floral & Serene Gardens"),
            ("sunset_window_lantern", "Sunset Palace Window with Candle Lantern", "Ancient Scrolls & Arches"),
            ("turquoise_pool_garden", "Turquoise Water Pool in Palace Garden", "Nature & Waterfalls")
        ]
    }
]

SINGLE_MASTER_TEMPLATES = [
    {
        "id": "tmpl_master_madinah_16x9",
        "name": "Master Emerald & Gold Madinah Sunset (16:9)",
        "category": "Emerald & Gold Luxury",
        "style": "emerald_gold",
        "aspect": "16:9",
        "source": "media_1790421930841.jpg"
    },
    {
        "id": "tmpl_master_madinah_9x16",
        "name": "Master Emerald & Gold Madinah Vertical (9:16 Shorts/Reels)",
        "category": "Emerald & Gold Luxury",
        "style": "emerald_gold",
        "aspect": "9:16",
        "source": "media_1790421937820.jpg"
    },
    {
        "id": "tmpl_rehl_sunset_16x9",
        "name": "Holy Quran on Rehl in Madinah Sunset",
        "category": "Sacred Quran & Lanterns",
        "style": "emerald_gold",
        "aspect": "16:9",
        "source": "media_1790421908736.jpg"
    },
    {
        "id": "tmpl_rehl_courtyard_16x9",
        "name": "Madinah Courtyard with Golden Lanterns & Rehl",
        "category": "Sacred Quran & Lanterns",
        "style": "emerald_gold",
        "aspect": "16:9",
        "source": "media_1790421923168.jpg"
    }
]

def split_single_tile(src_img, row, col, out_img_16x9, out_thumb_16x9, out_img_9x16=None, out_thumb_9x16=None):
    """Crops 1 tile out of a 3x3 collage using ffmpeg with lanczos scaling into 16:9 and 9:16."""
    # 1. 16:9 tile (1920x1080)
    filter_complex = f"[0:v]crop=in_w/3:in_h/3:{col}*(in_w/3):{row}*(in_h/3),scale=1920:1080:flags=lanczos[out]"
    cmd = ["ffmpeg", "-y", "-i", src_img, "-filter_complex", filter_complex, "-map", "[out]", "-q:v", "2", out_img_16x9]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 16:9 Thumbnail (320x180)
    cmd_thumb = ["ffmpeg", "-y", "-i", out_img_16x9, "-filter_complex", "[0:v]scale=320:180:flags=lanczos[out]", "-map", "[out]", "-q:v", "3", out_thumb_16x9]
    subprocess.run(cmd_thumb, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 2. 9:16 Vertical tile (1080x1920) if requested
    if out_img_9x16 and out_thumb_9x16:
        # Scale to fill 1080x1920 with centered framing
        v_filter = "[0:v]scale=3413:1920:flags=lanczos,crop=1080:1920:(in_w-1080)/2:0[out]"
        cmd_v = ["ffmpeg", "-y", "-i", out_img_16x9, "-filter_complex", v_filter, "-map", "[out]", "-q:v", "2", out_img_9x16]
        subprocess.run(cmd_v, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        cmd_v_thumb = ["ffmpeg", "-y", "-i", out_img_9x16, "-filter_complex", "[0:v]scale=180:320:flags=lanczos[out]", "-map", "[out]", "-q:v", "3", out_thumb_9x16]
        subprocess.run(cmd_v_thumb, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def process_single_full_image(src_img, out_img, out_thumb, target_w=1920, target_h=1080, is_vertical=False):
    """Processes full image into 1920x1080 (or 1080x1920) and thumbnail."""
    w = 1080 if is_vertical else target_w
    h = 1920 if is_vertical else target_h
    scale_filter = f"[0:v]scale={w}:{h}:flags=lanczos[out]"
    cmd = ["ffmpeg", "-y", "-i", src_img, "-filter_complex", scale_filter, "-map", "[out]", "-q:v", "2", out_img]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    thumb_w = 180 if is_vertical else 320
    thumb_h = 320 if is_vertical else 180
    cmd_thumb = ["ffmpeg", "-y", "-i", out_img, "-filter_complex", f"[0:v]scale={thumb_w}:{thumb_h}:flags=lanczos[out]", "-map", "[out]", "-q:v", "3", out_thumb]
    subprocess.run(cmd_thumb, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def initialize_templates_catalog():
    """Extracts all 12 user images into templates directory and builds catalog."""
    catalog = []
    user_upload_dir = "/Users/shaddo/.gemini/antigravity/brain/718824dd-35a2-4dc3-8b1d-27be14de4d07/.user_uploaded"
    
    # 8 Collages
    collage_filenames = [
        "media_1790421831321.jpg",
        "media_1790421837369.jpg",
        "media_1790421843734.jpg",
        "media_1790421850356.jpg",
        "media_1790421877906.jpg",
        "media_1790421890870.jpg",
        "media_1790421896415.jpg",
        "media_1790421902485.jpg"
    ]

    print("--- Initializing Islamic Design Templates from Collages ---")
    for c_idx, fname in enumerate(collage_filenames):
        src_path = os.path.join(user_upload_dir, fname)
        if not os.path.exists(src_path):
            print(f"Warning: Collage file {fname} not found in {user_upload_dir}")
            continue

        theme_info = COLLAGE_THEMES[c_idx] if c_idx < len(COLLAGE_THEMES) else {
            "prefix": f"c{c_idx+1}", "category": "General", "style": "emerald_gold", "tiles": []
        }

        print(f"Processing Collage {c_idx+1}/8: {fname} ({theme_info['category']})...")
        tile_idx = 0
        for r in range(3):
            for c in range(3):
                if tile_idx < len(theme_info.get("tiles", [])):
                    tile_slug, tile_name, tile_cat = theme_info["tiles"][tile_idx]
                else:
                    tile_slug, tile_name, tile_cat = (f"tile_{r}_{c}", f"Design Style {c_idx+1}-{tile_idx+1}", theme_info["category"])

                t_id = f"tmpl_{theme_info['prefix']}_{tile_slug}"
                out_img_name = f"{t_id}.jpg"
                out_thumb_name = f"{t_id}_thumb.jpg"
                out_img_path = os.path.join(IMAGES_DIR, out_img_name)
                out_thumb_path = os.path.join(THUMBS_DIR, out_thumb_name)

                if not os.path.exists(out_img_path) or os.path.getsize(out_img_path) == 0:
                    split_single_tile(src_path, r, c, out_img_path, out_thumb_path)

                catalog.append({
                    "id": t_id,
                    "name": tile_name,
                    "category": tile_cat,
                    "style": theme_info.get("style", "emerald_gold"),
                    "aspect": "16:9",
                    "image_url": f"/templates/images/{out_img_name}",
                    "thumb_url": f"/templates/thumbs/{out_thumb_name}",
                    "image_path": out_img_path
                })
                tile_idx += 1

    # 4 Master Single Templates
    print("Processing Single Full-Frame Master Templates...")
    for s_info in SINGLE_MASTER_TEMPLATES:
        src_path = os.path.join(user_upload_dir, s_info["source"])
        if not os.path.exists(src_path):
            continue

        t_id = s_info["id"]
        is_vert = (s_info.get("aspect") == "9:16")
        out_img_name = f"{t_id}.jpg"
        out_thumb_name = f"{t_id}_thumb.jpg"
        out_img_path = os.path.join(IMAGES_DIR, out_img_name)
        out_thumb_path = os.path.join(THUMBS_DIR, out_thumb_name)

        if not os.path.exists(out_img_path) or os.path.getsize(out_img_path) == 0:
            process_single_full_image(src_path, out_img_path, out_thumb_path, is_vertical=is_vert)

        catalog.append({
            "id": t_id,
            "name": s_info["name"],
            "category": s_info["category"],
            "style": s_info["style"],
            "aspect": s_info["aspect"],
            "image_url": f"/templates/images/{out_img_name}",
            "thumb_url": f"/templates/thumbs/{out_thumb_name}",
            "image_path": out_img_path
        })

    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"Catalog saved: {len(catalog)} Islamic video design templates registered!")
    return catalog

def load_templates_catalog():
    if os.path.exists(CATALOG_FILE):
        try:
            with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("Error loading templates catalog:", e)
    return initialize_templates_catalog()

def get_template_by_id(t_id):
    if not t_id:
        return None
    catalog = load_templates_catalog()
    # 1. Exact match
    for t in catalog:
        if t.get("id") == t_id:
            return t
    # 2. Match without _16x9 or _9x16 suffix
    base_id = re.sub(r'_(16x9|9x16)$', '', t_id)
    for t in catalog:
        if t.get("id") == base_id:
            return t
    # 3. Substring match (e.g. "c6_kaaba_gold_glow" matching "tmpl_c6_emerald_arches_kaaba_gold_glow")
    for t in catalog:
        t_tid = t.get("id", "")
        if t_id in t_tid or t_tid.endswith(t_id):
            return t
    return None

def auto_split_custom_collage(uploaded_file_path, custom_name="Custom Collage", category="Custom Uploads"):
    """
    On-demand splitter for user-uploaded 3x3 collages.
    Splits into 9 templates in BOTH 16:9 and 9:16 aspect ratios, registers them in templates.json.
    """
    if not os.path.exists(uploaded_file_path):
        raise FileNotFoundError(f"File not found: {uploaded_file_path}")

    current_catalog = load_templates_catalog()
    slug = re.sub(r'[^a-zA-Z0-9]', '_', custom_name.lower().strip()) or f"collage_{int(time.time())}"
    timestamp = int(time.time())

    created_templates = []
    tile_idx = 1
    for r in range(3):
        for c in range(3):
            t_id = f"tmpl_user_{slug}_{timestamp}_t{tile_idx}"
            out_img_16 = f"{t_id}_16x9.jpg"
            out_thumb_16 = f"{t_id}_16x9_thumb.jpg"
            out_img_9 = f"{t_id}_9x16.jpg"
            out_thumb_9 = f"{t_id}_9x16_thumb.jpg"
            
            p_img_16 = os.path.join(IMAGES_DIR, out_img_16)
            p_thumb_16 = os.path.join(THUMBS_DIR, out_thumb_16)
            p_img_9 = os.path.join(IMAGES_DIR, out_img_9)
            p_thumb_9 = os.path.join(THUMBS_DIR, out_thumb_9)

            # Generate both 16:9 and 9:16
            split_single_tile(uploaded_file_path, r, c, p_img_16, p_thumb_16, p_img_9, p_thumb_9)

            # Also maintain legacy unsuffixed copy
            shutil.copy2(p_img_16, os.path.join(IMAGES_DIR, f"{t_id}.jpg"))
            shutil.copy2(p_thumb_16, os.path.join(THUMBS_DIR, f"{t_id}_thumb.jpg"))

            t_obj = {
                "id": t_id,
                "name": f"{custom_name} - Style #{tile_idx}",
                "category": category,
                "style": "emerald_gold",
                "aspect": "both",
                "is_master": False,
                "image_url": f"/templates/images/{out_img_16}",
                "thumb_url": f"/templates/thumbs/{out_thumb_16}",
                "image_path": p_img_16,
                "image_16x9": f"/templates/images/{out_img_16}",
                "image_9x16": f"/templates/images/{out_img_9}",
                "thumb_16x9": f"/templates/thumbs/{out_thumb_16}",
                "thumb_9x16": f"/templates/thumbs/{out_thumb_9}",
                "image_path_16x9": p_img_16,
                "image_path_9x16": p_img_9
            }
            created_templates.append(t_obj)
            current_catalog.append(t_obj)
            tile_idx += 1

    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(current_catalog, f, indent=2, ensure_ascii=False)

    return created_templates

if __name__ == "__main__":
    catalog = initialize_templates_catalog()
    print(f"Total templates generated: {len(catalog)}")
