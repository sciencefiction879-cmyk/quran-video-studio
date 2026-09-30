import os, sys, json, urllib.request, subprocess, argparse, time, random, concurrent.futures, re
from wbw_aligner import get_wbw_surah_content
try:
    import audio_dsp_engine
except ImportError:
    audio_dsp_engine = None

# Ensure system PATH includes Homebrew and standard CLI directories
extra_paths = ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
current_path = os.environ.get("PATH", "")
os.environ["PATH"] = ":".join([p for p in extra_paths if p not in current_path]) + ":" + current_path

# Resolve BASE_DIR dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def is_dir_writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, ".test_write")
        with open(test_file, "w") as f: f.write("1")
        os.remove(test_file)
        return True
    except Exception:
        return False

user_home = os.path.expanduser("~")
if is_dir_writable(os.path.join(BASE_DIR, "video_render")):
    RENDER_DIR = os.path.join(BASE_DIR, "video_render")
else:
    RENDER_DIR = os.path.join(user_home, "Library", "Caches", "QuranVideoStudio", "render")

if is_dir_writable(os.path.join(BASE_DIR, "generated_videos")):
    OUT_DIR = os.path.join(BASE_DIR, "generated_videos")
else:
    OUT_DIR = os.path.join(user_home, "Movies", "QuranVideoStudio")

os.makedirs(RENDER_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
]
CHROME_BIN = next((c for c in CHROME_CANDIDATES if os.path.exists(c)), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

RECITER_PREFIXES = {
    "husary": ("Mahmoud Khalil Al-Husary", "Husary_128kbps"),
    "husary_mujawwad": ("Mahmoud Khalil Al-Husary (Mujawwad)", "Husary_128kbps"),
    "husary_muallim": ("Mahmoud Khalil Al-Husary (Muallim)", "Husary_Muallim_128kbps"),
    "alafasy": ("Mishary Rashid Alafasy", "Alafasy_128kbps"),
    "sudais": ("Abdur-Rahman As-Sudais", "Abdurrahmaan_As-Sudais_192kbps"),
    "shuraym": ("Sa'ud Ash-Shuraym", "Saood_ash-Shuraym_128kbps"),
    "abdulbasit": ("Abdul Basit Murattal", "Abdul_Basit_Murattal_192kbps"),
    "abdulbasit_mujawwad": ("Abdul Basit Mujawwad", "Abdul_Basit_Mujawwad_128kbps"),
    "minshawi": ("Mohamed Siddiq Al-Minshawi", "Minshawy_Murattal_128kbps"),
    "minshawi_mujawwad": ("Al-Minshawi Mujawwad", "Minshawy_Mujawwad_192kbps"),
    "muaiqly": ("Maher Al-Muaiqly", "Maher_AlMuaiqly_64kbps"),
    "hani": ("Hani Ar-Rifai", "Hani_Rifai_192kbps"),
    "ghamadi": ("Saad Al-Ghamdi", "Ghamadi_40kbps"),
    "dussary": ("Yasser Ad-Dussary", "Yasser_Ad-Dussary_128kbps"),
    "shatri": ("Abu Bakr Al-Shatri", "Abu_Bakr_Ash-Shaatree_128kbps"),
    "hudhaify": ("Ali Al-Hudhaify", "Hudhaify_128kbps"),
    "qatami": ("Nasser Al-Qatami", "Nasser_Alqatami_128kbps"),
    "ayyoub": ("Muhammad Ayoub", "Muhammad_Ayyoub_128kbps"),
    "budair": ("Salah Al-Budair", "Salah_Al_Budair_128kbps"),
    "juhany": ("Abdullah Awad Al-Juhany", "Abdullaah_3awwaad_Al-Juhaynee_128kbps"),
    "ajamy": ("Ahmed Al-Ajamy", "ahmed_ibn_ali_al_ajamy_128kbps"),
    "tablawi": ("Mohammad Al-Tablawi", "Mohammad_al_Tablaway_128kbps"),
    "bukhatir": ("Salah Bukhatir", "Salaah_AbdulRahman_Bukhatir_128kbps"),
    "abbad": ("Fares Abbad", "Fares_Abbad_64kbps"),
    "banna": ("Mahmoud Ali Al-Banna", "mahmoud_ali_al_banna_32kbps"),
    "jaber": ("Ali Jaber", "Ali_Jaber_64kbps"),
    "basfar": ("Abdullah Basfar", "Abdullah_Basfar_192kbps"),
    "mustafa_ismail": ("Mustafa Ismail", "Mustafa_Ismail_48kbps"),
    "jibreel": ("Muhammad Jibreel", "Muhammad_Jibreel_128kbps"),
    "ayman_sowaid": ("Dr. Ayman Sowaid", "Ayman_Sowaid_64kbps"),
    "aziz_alili": ("Aziz Alili", "aziz_alili_128kbps"),
    "yaser_salamah": ("Yaser Salamah", "Yaser_Salamah_128kbps"),
    "akram": ("Akram Al-Alaqmi", "Akram_AlAlaqimy_128kbps"),
    "ali_hajjaj": ("Ali Hajjaj Souissi", "Ali_Hajjaj_AlSuesy_128kbps")
}

RESOLUTIONS = {
    "720p": {"w": 1280, "h": 720, "crf": 22, "ab": "160k", "suffix": "720p"},
    "1080p": {"w": 1920, "h": 1080, "crf": 20, "ab": "192k", "suffix": "1080p"},
    "2k": {"w": 2560, "h": 1440, "crf": 18, "ab": "256k", "suffix": "2K"},
    "4k": {"w": 3840, "h": 2160, "crf": 16, "ab": "320k", "suffix": "4K"}
}

ASMR_PRESETS = {
    "rain": "anoisesrc=c=pink:r=48000:a=0.07,lowpass=f=1200,highpass=f=200,aecho=0.8:0.7:60|120:0.25|0.15",
    "wind": "anoisesrc=c=brown:r=48000:a=0.08,lowpass=f=450,tremolo=f=0.2:d=0.7",
    "waves": "anoisesrc=c=pink:r=48000:a=0.10,lowpass=f=600,tremolo=f=0.15:d=0.85",
    "drone": "anoisesrc=c=brown:r=48000:a=0.05,lowpass=f=250,aecho=0.9:0.8:100|200:0.3|0.2",
    "none": None
}

SURAH_NAMES = {
    1: "Al-Fatihah", 2: "Al-Baqarah", 3: "Ali_Imran", 4: "An-Nisa", 5: "Al-Maidah",
    6: "Al-Anam", 7: "Al-Araf", 8: "Al-Anfal", 9: "At-Tawbah", 10: "Yunus",
    11: "Hud", 12: "Yusuf", 13: "Ar-Rad", 14: "Ibrahim", 15: "Al-Hijr",
    16: "An-Nahl", 17: "Al-Isra", 18: "Al-Kahf", 19: "Maryam", 20: "Ta-Ha",
    21: "Al-Anbiya", 22: "Al-Hajj", 23: "Al-Muminun", 24: "An-Nur", 25: "Al-Furqan",
    26: "Ash-Shuara", 27: "An-Naml", 28: "Al-Qasas", 29: "Al-Ankabut", 30: "Ar-Rum",
    31: "Luqman", 32: "As-Sajdah", 33: "Al-Ahzab", 34: "Saba", 35: "Fatir",
    36: "Ya-Sin", 37: "As-Saffat", 38: "Sad", 39: "Az-Zumar", 40: "Ghafir",
    41: "Fussilat", 42: "Ash-Shura", 43: "Az-Zukhruf", 44: "Ad-Dukhan", 45: "Al-Jathiyah",
    46: "Al-Ahqaf", 47: "Muhammad", 48: "Al-Fath", 49: "Al-Hujurat", 50: "Qaf",
    51: "Adh-Dhariyat", 52: "At-Tur", 53: "An-Najm", 54: "Al-Qamar", 55: "Ar-Rahman",
    56: "Al-Waqiah", 57: "Al-Hadid", 58: "Al-Mujadila", 59: "Al-Hashr", 60: "Al-Mumtahanah",
    61: "As-Saff", 62: "Al-Jumuah", 63: "Al-Munafiqun", 64: "At-Taghabun", 65: "At-Talaq",
    66: "At-Tahrim", 67: "Al-Mulk", 68: "Al-Qalam", 69: "Al-Haqqah", 70: "Al-Maarij",
    71: "Nuh", 72: "Al-Jinn", 73: "Al-Muzzammil", 74: "Al-Muddaththir", 75: "Al-Qiyamah",
    76: "Al-Insan", 77: "Al-Mursalat", 78: "An-Naba", 79: "An-Naziat", 80: "Abasa",
    81: "At-Takwir", 82: "Al-Infitar", 83: "Al-Mutaffifin", 84: "Al-Inshiqaq", 85: "Al-Buruj",
    86: "At-Tariq", 87: "Al-Ala", 88: "Al-Ghashiyah", 89: "Al-Fajr", 90: "Al-Balad",
    91: "Ash-Shams", 92: "Al-Layl", 93: "Ad-Duha", 94: "Ash-Sharh", 95: "At-Tin",
    96: "Al-Alaq", 97: "Al-Qadr", 98: "Al-Bayyinah", 99: "Az-Zalzalah", 100: "Al-Adiyat",
    101: "Al-Qariah", 102: "At-Takathur", 103: "Al-Asr", 104: "Al-Humazah", 105: "Al-Fil",
    106: "Quraysh", 107: "Al-Maun", 108: "Al-Kawthar", 109: "Al-Kafirun", 110: "An-Nasr",
    111: "Al-Masad", 112: "Al-Ikhlas", 113: "Al-Falaq", 114: "An-Nas"
}

SURAH_ARABIC_NAMES = {
    1: "الفاتحة", 2: "البقرة", 3: "آل عمران", 4: "النساء", 5: "المائدة",
    6: "الأنعام", 7: "الأعراف", 8: "الأنفال", 9: "التوبة", 10: "يونس",
    11: "هود", 12: "يوسف", 13: "الرعد", 14: "إبراهيم", 15: "الحجر",
    16: "النحل", 17: "الإسراء", 18: "الكهف", 19: "مريم", 20: "طه",
    21: "الأنبياء", 22: "الحج", 23: "المؤمنون", 24: "النور", 25: "الفرقان",
    26: "الشعراء", 27: "النمل", 28: "القصص", 29: "العنكبوت", 30: "الروم",
    31: "لقمان", 32: "السجدة", 33: "الأحزاب", 34: "سبأ", 35: "فاطر",
    36: "يس", 37: "الصافات", 38: "ص", 39: "الزمر", 40: "غافر",
    41: "فصلت", 42: "الشورى", 43: "الزخرف", 44: "الدخان", 45: "الجاثية",
    46: "الأحقاف", 47: "محمد", 48: "الفتح", 49: "الحجرات", 50: "ق",
    51: "الذاريات", 52: "الطور", 53: "النجم", 54: "القمر", 55: "الرحمن",
    56: "الواقعة", 57: "الحديد", 58: "المجادلة", 59: "الحشر", 60: "الممتحنة",
    61: "الصف", 62: "الجمعة", 63: "المنافقون", 64: "التغابن", 65: "الطلاق",
    66: "التحريم", 67: "الملك", 68: "القلم", 69: "الحاقة", 70: "المعارج",
    71: "نوح", 72: "الجن", 73: "المزمل", 74: "المدثر", 75: "القيامة",
    76: "الإنسان", 77: "المرسلات", 78: "النبأ", 79: "النازعات", 80: "عبس",
    81: "التكوير", 82: "الانفطار", 83: "المطففين", 84: "الانشقاق", 85: "البروج",
    86: "الطارق", 87: "الأعلى", 88: "الغاشية", 89: "الفجر", 90: "البلد",
    91: "الشمس", 92: "الليل", 93: "الضحى", 94: "الشرح", 95: "التين",
    96: "العلق", 97: "القدر", 98: "البينة", 99: "الزلزلة", 100: "العاديات",
    101: "القارعة", 102: "التكاثر", 103: "العصر", 104: "الهمزة", 105: "الفيل",
    106: "قريش", 107: "الماعون", 108: "الكوثر", 109: "الكافرون", 110: "النصر",
    111: "المسد", 112: "الإخلاص", 113: "الفلق", 114: "الناس"
}

def get_duration(fpath):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", fpath]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(json.loads(res.stdout)["format"]["duration"])

def format_timestamp(seconds, srt=False):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if srt:
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"
    else:
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        else:
            return f"{mins:02d}:{secs:02d}"

def generate_thumbnail(
    surah=67, ayah=1, aspect="16:9",
    highlight_color="#ffe600", highlight_style="glow", bg_preset="midnight",
    qari="husary", include_urdu=True, include_hindi=True, include_english=True,
    font_ar="scheherazade", font_ur="nastaliq", font_hi="noto_hindi", font_en="outfit",
    watermark="", output_dir=None,
    template_id=None, template_bg=None, template_style=None
):
    surah_name_clean = SURAH_NAMES.get(surah, f"Surah_{surah}").replace("'", "").replace(" ", "_")
    target_out_dir = output_dir if output_dir and os.path.exists(output_dir) else os.path.join(OUT_DIR, "Thumbnails")
    os.makedirs(target_out_dir, exist_ok=True)

    is_vertical = (str(aspect).strip() == "9:16")
    w_size = "2160,3840" if is_vertical else "3840,2160"
    aspect_slug = "9x16_Vertical" if is_vertical else "16x9_Landscape"

    filename = f"{surah:03d}_Surah_{surah_name_clean}_Ayah_{ayah}_Poster_{aspect_slug}_4K.png"
    out_png = os.path.join(target_out_dir, filename)

    effective_bg = template_bg if template_bg else bg_preset
    tpl_qs = ""
    if template_id:
        tpl_qs += f"&template_id={urllib.parse.quote(str(template_id))}"
    if template_style:
        tpl_qs += f"&tpl_style={template_style}"
    if template_bg:
        tpl_qs += f"&template_bg={urllib.parse.quote(template_bg)}"

    url = (
        f"http://localhost:8765/video_render/render_studio_slide.html?surah={surah}&ayah={ayah}&mode=arabic"
        f"&color={highlight_color.replace('#','%23')}&style={highlight_style}&bg={urllib.parse.quote(effective_bg)}{tpl_qs}"
        f"&ur={'1' if include_urdu else '0'}&hi={'1' if include_hindi else '0'}&en={'1' if include_english else '0'}"
        f"&qari={qari}&res=4k&aspect={aspect}&font_ar={font_ar}&font_ur={font_ur}&font_hi={font_hi}&font_en={font_en}"
    )
    if watermark:
        url += f"&watermark={urllib.parse.quote(watermark)}"

    cmd_cap = [
        CHROME_BIN, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--virtual-time-budget=6000", f"--window-size={w_size}",
        f"--screenshot={out_png}", url
    ]
    subprocess.run(cmd_cap, check=True, capture_output=True)
    try:
        subprocess.run(["open", "-R", out_png])
    except Exception:
        pass
    return out_png

def build_audio_filter_chain(
    speed=1.0, pitch_semitones=0.0, random_humanize=False,
    reverb_wet=0.15, bass_boost=0.0, treble_boost=0.0,
    mid_boost=0.0, loudness_norm=True, binaural_432=False,
    base_vol=1.05
):
    """
    19-Feature Studio Audio DSP filter builder for FFmpeg.
    """
    filters = ["aresample=48000", "aformat=channel_layouts=stereo:sample_fmts=s16"]
    
    cur_speed = float(speed or 1.0)
    cur_pitch = float(pitch_semitones or 0.0)
    
    # 1. 1-2% Organic Random Pitch & Tempo Micro-Jitter (Humanize / YouTube Anti-Duplicate)
    if random_humanize:
        jitter_pct = random.uniform(-0.018, 0.018) # Up to 1.8% micro-tempo fluctuation
        cur_speed *= (1.0 + jitter_pct)
        cur_pitch += random.uniform(-0.16, 0.16) # Up to ±16 cents micro-pitch variation
        
    # 2. 432 Hz Healing / Spiritual tuning (shift 440Hz -> 432Hz)
    if binaural_432:
        cur_pitch -= 0.31766
        
    # 3. Pitch shift with duration preservation
    if abs(cur_pitch) > 0.01:
        pitch_factor = 2.0 ** (cur_pitch / 12.0)
        target_sr = int(round(48000 * pitch_factor))
        filters.append(f"asetrate={target_sr}")
        filters.append("aresample=48000")
        inv_tempo = 1.0 / pitch_factor
        if 0.5 <= inv_tempo <= 2.0:
            filters.append(f"atempo={inv_tempo:.4f}")
        elif inv_tempo > 2.0:
            filters.append("atempo=2.0")
            filters.append(f"atempo={inv_tempo/2.0:.4f}")
        elif inv_tempo < 0.5:
            filters.append("atempo=0.5")
            filters.append(f"atempo={inv_tempo*2.0:.4f}")

    # 4. Playback Speed adjustment
    if abs(cur_speed - 1.0) > 0.005:
        if 0.5 <= cur_speed <= 2.0:
            filters.append(f"atempo={cur_speed:.4f}")
        elif cur_speed > 2.0:
            filters.append("atempo=2.0")
            filters.append(f"atempo={cur_speed/2.0:.4f}")
        elif cur_speed < 0.5:
            filters.append("atempo=0.5")
            filters.append(f"atempo={cur_speed*2.0:.4f}")

    # 5. Clean Bandpass vocal clarity
    filters.append("highpass=f=75")
    filters.append("lowpass=f=12000")

    # 6. Low Shelf (Bass warmth)
    b_boost = float(bass_boost or 0.0)
    if b_boost > 0.1:
        filters.append(f"bass=g={min(b_boost, 8.0):.1f}:f=120")

    # 7. High Shelf (Treble air)
    t_boost = float(treble_boost or 0.0)
    if t_boost > 0.1:
        filters.append(f"treble=g={min(t_boost, 8.0):.1f}:f=8000")

    # 8. Parametric EQ (Midrange presence)
    m_boost = float(mid_boost or 0.0)
    if m_boost > 0.1:
        filters.append(f"equalizer=f=2500:t=q:w=1.2:g={min(m_boost, 6.0):.1f}")

    # 9. Sacred Reverb
    rev = float(reverb_wet or 0.15)
    if rev > 0.02:
        in_gain = max(0.6, 1.0 - (rev * 0.3))
        echo_g1 = round(rev * 0.7, 2)
        echo_g2 = round(rev * 0.45, 2)
        filters.append(f"aecho={in_gain:.2f}:0.7:50|110:{echo_g1}|{echo_g2}")

    # 10. Base volume
    vol = float(base_vol or 1.0)
    filters.append(f"volume={vol:.2f}")

    # 11. YouTube Loudness normalization (-14 LUFS)
    if loudness_norm:
        filters.append("loudnorm=I=-14:TP=-1.5:LRA=11")

    return ",".join(filters)

def batch_render_all_slides(slide_manifest_items, width, height, progress_cb=None, start_time=None):
    """
    Renders all slides in batch using render_slides_fast.mjs via persistent Chrome CDP.
    Falls back to parallel ThreadPoolExecutor if node script fails.
    """
    if not slide_manifest_items:
        return
    manifest_path = os.path.join(RENDER_DIR, f"slides_manifest_{int(time.time()*1000)}.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "width": width,
            "height": height,
            "items": slide_manifest_items
        }, f, indent=2)

    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_slides_fast.mjs")
    total_slides = sum(
        (1 if item.get("base_out") else 0) + len(item.get("word_outs", []))
        if item.get("type") in ("wbw", "urdu_wbw") else 1
        for item in slide_manifest_items
    )

    success = False
    try:
        proc = subprocess.Popen(
            ["node", script_path, manifest_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        import select
        last_progress_time = time.time()
        while proc.poll() is None:
            rlist, _, _ = select.select([proc.stdout], [], [], 1.5)
            if rlist:
                line = proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                last_progress_time = time.time()
                try:
                    data = json.loads(line)
                    if data.get("type") == "progress":
                        c = data.get("completed", 0)
                        t = data.get("total", total_slides)
                        if progress_cb:
                            el = round(time.time() - (start_time or time.time()), 1)
                            progress_cb({
                                "phase": "rendering_slides",
                                "message": f"Rendering slides ({c}/{t} frames captured)...",
                                "current_item": os.path.basename(data.get("file", "")),
                                "completed_ayahs": c,
                                "total_ayahs": t,
                                "percent": 15 + int((c / max(t, 1)) * 75),
                                "elapsed_sec": int(el),
                                "eta_sec": max(1, int((el / max(c, 1)) * (t - c))) if c > 0 else 3
                            })
                except Exception:
                    pass
            else:
                if time.time() - last_progress_time > 40:
                    print("Warning: render_slides_fast.mjs inactive for 40s. Terminating and falling back to parallel Chrome capture.")
                    try: proc.kill()
                    except Exception: pass
                    break

        try:
            proc.wait(timeout=5)
            if proc.returncode == 0:
                success = True
        except Exception:
            try: proc.kill()
            except Exception: pass
    except Exception as e:
        print(f"render_slides_fast execution error: {e}")

    # Fallback to ThreadPoolExecutor if any slides were missed
    if not success:
        print("Falling back to multi-worker headless chrome capture...")
        fallback_tasks = []
        w_size = f"{width},{height}"
        for item in slide_manifest_items:
            t = item.get("type")
            u = item.get("url")
            if t == "wbw":
                if item.get("base_out") and (not os.path.exists(item["base_out"]) or os.path.getsize(item["base_out"]) < 10000):
                    fallback_tasks.append((f"{u}&wbw=1&active_word=-1", item["base_out"]))
                for w_idx, w_out in item.get("word_outs", []):
                    if not os.path.exists(w_out) or os.path.getsize(w_out) < 10000:
                        fallback_tasks.append((f"{u}&wbw=1&active_word={w_idx}", w_out))
            elif t == "urdu_wbw":
                for w_idx, w_out in item.get("word_outs", []):
                    if not os.path.exists(w_out) or os.path.getsize(w_out) < 10000:
                        fallback_tasks.append((f"{u}&ur_word={w_idx}", w_out))
            else:
                out = item.get("out")
                if out and (not os.path.exists(out) or os.path.getsize(out) < 10000):
                    fallback_tasks.append((u, out))

        def _cap(url_and_path):
            url_c, path_c = url_and_path
            cmd = [
                CHROME_BIN, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--virtual-time-budget=2500", f"--window-size={w_size}",
                f"--screenshot={path_c}", url_c
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=18)
            except Exception:
                pass

        if fallback_tasks:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(_cap, fallback_tasks))

    try:
        if os.path.exists(manifest_path):
            os.remove(manifest_path)
    except Exception:
        pass

def generate_video(
    surah=55, ayah_start=1, ayah_end=5, qari="alafasy",
    highlight_color="#ffe600", highlight_style="glow", bg_preset="midnight",
    include_urdu=True, include_hindi=True, include_english=True,
    resolution="1080p", aspect="16:9", translation_voice="urdu", watermark="",
    repeat_count=1,
    output_dir=None, asmr_sound="rain", asmr_vol=0.15,
    wbw_translation=False, full_surah=False,
    font_ar="scheherazade", font_ur="nastaliq", font_hi="noto_hindi", font_en="outfit",
    urdu_scholar_id=234, english_scholar_id=20,
    playback_order="ar_ur_en",
    audio_speed=1.0, pitch_semitones=0.0, random_humanize=False,
    reverb_wet=0.15, bass_boost=0.0, treble_boost=0.0, mid_boost=0.0,
    loudness_norm=True, binaural_432=False,
    show_waveform=True, show_translit=False,
    v_num=None, template_id=None, template_bg=None, template_style=None, template_name="",
    progress_cb=None
):
    qari_name, qari_folder = RECITER_PREFIXES.get(qari, ("Mishary Rashid Alafasy", "Alafasy_128kbps"))
    surah_padded = f"{surah:03d}"
    target_out_dir = output_dir if output_dir and os.path.exists(output_dir) else OUT_DIR
    os.makedirs(target_out_dir, exist_ok=True)
    
    is_vertical = (str(aspect).strip() == "9:16")

    # Resolve Effective Template / Background based on Aspect Ratio
    if template_id:
        try:
            from template_manager import get_template_by_id
            t_obj = get_template_by_id(template_id)
            if t_obj:
                if is_vertical and t_obj.get("image_9x16"):
                    template_bg = t_obj.get("image_9x16")
                elif not is_vertical and t_obj.get("image_16x9"):
                    template_bg = t_obj.get("image_16x9")
                elif t_obj.get("image_url"):
                    template_bg = t_obj.get("image_url")
                if not template_style:
                    template_style = t_obj.get("style", "")
                if not template_name:
                    template_name = t_obj.get("name", "")
        except Exception as e:
            print("Error resolving template by id:", e)

    if template_bg:
        if is_vertical:
            if "_16x9" in template_bg:
                cand = template_bg.replace("_16x9", "_9x16")
                cand_path = os.path.join(BASE_DIR, cand.lstrip("/"))
                if os.path.exists(cand_path):
                    template_bg = cand
            elif "_9x16" not in template_bg:
                cand = template_bg.replace(".jpg", "_9x16.jpg")
                cand_path = os.path.join(BASE_DIR, cand.lstrip("/"))
                if os.path.exists(cand_path):
                    template_bg = cand
        else:
            if "_9x16" in template_bg:
                cand = template_bg.replace("_9x16", "_16x9")
                cand_path = os.path.join(BASE_DIR, cand.lstrip("/"))
                if os.path.exists(cand_path):
                    template_bg = cand

    effective_bg = template_bg if template_bg else bg_preset
    effective_style = template_style or ""
    res_key = (resolution or "1080p").lower()
    res_cfg = RESOLUTIONS.get(res_key, RESOLUTIONS["1080p"]).copy()
    if is_vertical:
        orig_w, orig_h = res_cfg["w"], res_cfg["h"]
        res_cfg["w"] = orig_h
        res_cfg["h"] = orig_w
        res_suffix = f"{res_cfg['suffix']}_9x16_Shorts"
    else:
        res_suffix = res_cfg["suffix"]
    w_size = f"{res_cfg['w']},{res_cfg['h']}"
    
    # Fetch Verses with synchronized WBW triplets (Arabic, Urdu, English) and Qari speech-alignment
    try:
        data = get_wbw_surah_content(
            surah, qari=qari, cache_dir=RENDER_DIR,
            urdu_scholar_id=urdu_scholar_id, english_scholar_id=english_scholar_id
        )
    except Exception as e:
        print(f"[Generator] Direct fetch fallback for Surah {surah}: {e}")
        api_url = f"https://api.quran.com/api/v4/verses/by_chapter/{surah}?language=ur&words=true&word_fields=text_uthmani,location,translation&translations=234,20,122&fields=text_uthmani&per_page=300"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 QuranStudio/1.4"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
    total_chapter_verses = len(data["verses"])

    if full_surah or ayah_end is None or ayah_end <= 0 or ayah_end > total_chapter_verses:
        ayah_end = total_chapter_verses

    surah_name_clean = SURAH_NAMES.get(surah, f"Surah_{surah}").replace("'", "").replace(" ", "_")
    msg = f"Generating Video ({res_suffix}) for Surah {surah} (Ayahs {ayah_start} to {ayah_end}{' - Full Surah' if (ayah_start == 1 and ayah_end == total_chapter_verses) else ''}) with Qari {qari_name}..."
    print(msg)
    if progress_cb: progress_cb(msg)
    
    verses = data["verses"][ayah_start - 1 : ayah_end]
    
    # 0.4s silence
    silence_wav = os.path.join(RENDER_DIR, "silence_04.wav")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", "0.4", "-c:a", "pcm_s16le", silence_wav
    ], check=True, capture_output=True)
    
    audio_segments = []
    slides_timeline = []
    chapters = []
    srt_entries = []
    current_sec = 0.0
    start_time = time.time()

    v_voice = (translation_voice or ("urdu" if include_urdu else "none")).lower()
    play_urdu_voice = (v_voice in ("urdu", "both")) and include_urdu
    play_english_voice = (v_voice in ("english", "both")) and include_english
    repeat_times = max(1, min(10, int(repeat_count or 1)))

    # Phase 0: Parallel Pre-fetch all needed audio tracks
    download_tasks = []
    ur_folder = "urdu_farhat_hashmi" if translation_voice in ["urdu_farhat", "farhat"] else "urdu_shamshad_ali_khan_46kbps"
    for v_idx, v in enumerate(verses):
        a_num = ayah_start + v_idx
        a_pad = f"{a_num:03d}"
        
        ar_file = os.path.join(RENDER_DIR, f"audio_{surah}_{a_num}_ar.mp3")
        ar_url = f"https://everyayah.com/data/{qari_folder}/{surah_padded}{a_pad}.mp3"
        download_tasks.append((ar_url, ar_file))
        
        if play_urdu_voice:
            ur_file = os.path.join(RENDER_DIR, f"audio_{surah}_{a_num}_ur.mp3")
            ur_url = f"https://everyayah.com/data/translations/{ur_folder}/{surah_padded}{a_pad}.mp3"
            download_tasks.append((ur_url, ur_file))
            
        if play_english_voice:
            en_file = os.path.join(RENDER_DIR, f"audio_{surah}_{a_num}_en.mp3")
            en_url = f"https://everyayah.com/data/English/Sahih_Intnl_Ibrahim_Walk_192kbps/{surah_padded}{a_pad}.mp3"
            download_tasks.append((en_url, en_file))

    def _fetch_audio(url_and_path):
        url, path_out = url_and_path
        if os.path.exists(path_out) and os.path.getsize(path_out) > 1000:
            return path_out
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 QuranStudio/1.4"
                })
                with urllib.request.urlopen(req, timeout=15) as r, open(path_out, "wb") as f_out:
                    f_out.write(r.read())
                if os.path.exists(path_out) and os.path.getsize(path_out) > 1000:
                    return path_out
            except Exception:
                time.sleep(0.4 * (attempt + 1))
        return None

    if progress_cb:
        progress_cb({
            "phase": "downloading",
            "message": f"Pre-fetching audio tracks ({len(download_tasks)} tracks in parallel)...",
            "current_item": "Audio tracks",
            "completed_ayahs": 0,
            "total_ayahs": len(verses),
            "percent": 5,
            "elapsed_sec": int(time.time() - start_time),
            "eta_sec": 3
        })
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(_fetch_audio, download_tasks))

    # Phase 1: Build Slide Manifest for Entire Video & Batch Render via High-Speed CDP
    tpl_qs = ""
    if template_id:
        tpl_qs += f"&template_id={urllib.parse.quote(str(template_id))}"
    if effective_style:
        tpl_qs += f"&tpl_style={effective_style}"
    if template_bg:
        tpl_qs += f"&template_bg={urllib.parse.quote(template_bg)}"

    slide_manifest_items = []
    should_render_ar_global = (playback_order != "only_ur" and playback_order != "only_en")
    should_render_ur_global = (playback_order != "only_ar" and playback_order != "only_en") and (play_urdu_voice or playback_order == "only_ur" or "ur" in playback_order)
    should_render_en_global = (playback_order != "only_ar" and playback_order != "only_ur") and (play_english_voice or playback_order == "only_en" or "en" in playback_order)

    for v_idx, v in enumerate(verses):
        ayah_num = ayah_start + v_idx
        wbw_words = v.get("wbw_words", [])

        # Arabic slide manifest item
        if should_render_ar_global:
            url_ar = f"http://localhost:8765/video_render/render_studio_slide.html?surah={surah}&ayah={ayah_num}&total_ayahs={total_chapter_verses}&mode=arabic&color={highlight_color.replace('#','%23')}&style={highlight_style}&bg={urllib.parse.quote(effective_bg)}{tpl_qs}&ur={'1' if include_urdu else '0'}&hi={'1' if include_hindi else '0'}&en={'1' if include_english else '0'}&qari={qari}&res={res_key}&aspect={aspect}&font_ar={font_ar}&font_ur={font_ur}&font_hi={font_hi}&font_en={font_en}&waveform={'1' if show_waveform else '0'}&translit={'1' if show_translit else '0'}"
            if watermark:
                url_ar += f"&watermark={urllib.parse.quote(watermark)}"

            if wbw_translation and wbw_words and len(wbw_words) > 0:
                first_st = wbw_words[0].get("start", 0.0)
                slide_ar_base = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ar_base{'_9x16' if is_vertical else ''}.png") if first_st > 0.1 else None
                word_outs = []
                for w_i in range(len(wbw_words)):
                    slide_ar_w = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ar_w{w_i}{'_9x16' if is_vertical else ''}.png")
                    word_outs.append([w_i, slide_ar_w])
                slide_manifest_items.append({
                    "type": "wbw",
                    "url": f"{url_ar}&wbw=1",
                    "base_out": slide_ar_base,
                    "word_outs": word_outs
                })
            else:
                slide_ar = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ar{'_9x16' if is_vertical else ''}.png")
                slide_manifest_items.append({
                    "type": "static",
                    "url": url_ar,
                    "out": slide_ar
                })

        # Urdu slide manifest item
        if should_render_ur_global:
            trans_ur_obj = next((t for t in v.get("translations", []) if t.get("resource_id") == 234), None)
            clean_ur = re.sub(r'<[^>]*>', '', trans_ur_obj.get("text", "")).strip() if trans_ur_obj else ""
            ur_words = clean_ur.split() if clean_ur else []
            url_ur = f"http://localhost:8765/video_render/render_studio_slide.html?surah={surah}&ayah={ayah_num}&total_ayahs={total_chapter_verses}&mode=urdu&color={highlight_color.replace('#','%23')}&style={highlight_style}&bg={urllib.parse.quote(effective_bg)}{tpl_qs}&ur=1&hi={'1' if include_hindi else '0'}&en={'1' if include_english else '0'}&qari={qari}&res={res_key}&aspect={aspect}&font_ar={font_ar}&font_ur={font_ur}&font_hi={font_hi}&font_en={font_en}&waveform={'1' if show_waveform else '0'}&translit={'1' if show_translit else '0'}"
            if watermark:
                url_ur += f"&watermark={urllib.parse.quote(watermark)}"

            if wbw_translation and len(ur_words) > 1:
                ur_word_outs = []
                for w_idx in range(len(ur_words)):
                    slide_ur_w = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ur_w{w_idx}{'_9x16' if is_vertical else ''}.png")
                    ur_word_outs.append([w_idx, slide_ur_w])
                slide_manifest_items.append({
                    "type": "urdu_wbw",
                    "url": url_ur,
                    "word_outs": ur_word_outs
                })
            else:
                slide_ur = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ur{'_9x16' if is_vertical else ''}.png")
                slide_manifest_items.append({
                    "type": "static",
                    "url": url_ur,
                    "out": slide_ur
                })

        # English slide manifest item
        if should_render_en_global:
            url_en = f"http://localhost:8765/video_render/render_studio_slide.html?surah={surah}&ayah={ayah_num}&total_ayahs={total_chapter_verses}&mode=english&color={highlight_color.replace('#','%23')}&style={highlight_style}&bg={urllib.parse.quote(effective_bg)}{tpl_qs}&ur={'1' if include_urdu else '0'}&hi={'1' if include_hindi else '0'}&en=1&qari={qari}&res={res_key}&aspect={aspect}&font_ar={font_ar}&font_ur={font_ur}&font_hi={font_hi}&font_en={font_en}&waveform={'1' if show_waveform else '0'}&translit={'1' if show_translit else '0'}"
            if watermark:
                url_en += f"&watermark={urllib.parse.quote(watermark)}"
            slide_en = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_en{'_9x16' if is_vertical else ''}.png")
            slide_manifest_items.append({
                "type": "static",
                "url": url_en,
                "out": slide_en
            })

    # Execute Ultra-Fast Batch Slide Render via CDP
    batch_render_all_slides(slide_manifest_items, res_cfg["w"], res_cfg["h"], progress_cb, start_time)

    # Phase 2: Rapid Assembly of Timeline & Audio Segments
    for v_idx, v in enumerate(verses):
        ayah_num = ayah_start + v_idx
        ayah_padded = f"{ayah_num:03d}"
        elapsed = round(time.time() - start_time, 1)
        eta = round((elapsed / max(v_idx, 1)) * (len(verses) - v_idx), 1) if v_idx > 0 else 5.0
        
        if progress_cb:
            progress_cb({
                "phase": "assembling",
                "message": f"Assembling Ayah {ayah_num}/{ayah_end} ({v_idx+1}/{len(verses)})",
                "current_item": f"Ayah {ayah_num}",
                "completed_ayahs": v_idx,
                "total_ayahs": len(verses),
                "percent": 80 + int((v_idx / max(len(verses), 1)) * 12),
                "elapsed_sec": int(elapsed),
                "eta_sec": int(eta)
            })
        
        ar_audio_file = os.path.join(RENDER_DIR, f"audio_{surah}_{ayah_num}_ar.mp3")
        ur_audio_file = os.path.join(RENDER_DIR, f"audio_{surah}_{ayah_num}_ur.mp3") if play_urdu_voice else None
        en_audio_file = os.path.join(RENDER_DIR, f"audio_{surah}_{ayah_num}_en.mp3") if play_english_voice else None
                
        # 1. Process Arabic Audio
        proc_ar = None
        dur_ar = 0.0
        arabic_timeline_items = []
        should_render_ar = should_render_ar_global
        
        # Check for customized audio DSP profile for this Surah or active Master
        surah_audio_prof = None
        if audio_dsp_engine:
            surah_audio_prof = audio_dsp_engine.load_surah_profile(surah) or audio_dsp_engine.load_master_profile()
        
        if should_render_ar and ar_audio_file and os.path.exists(ar_audio_file):
            proc_ar = os.path.join(RENDER_DIR, f"proc_{surah}_{ayah_num}_ar.wav")
            if surah_audio_prof and "arabic" in surah_audio_prof:
                af_ar = audio_dsp_engine.build_ffmpeg_filter_chain(surah_audio_prof["arabic"])
            else:
                af_ar = build_audio_filter_chain(
                    speed=audio_speed, pitch_semitones=pitch_semitones, random_humanize=random_humanize,
                    reverb_wet=reverb_wet, bass_boost=bass_boost, treble_boost=treble_boost, mid_boost=mid_boost,
                    loudness_norm=loudness_norm, binaural_432=binaural_432, base_vol=1.05
                )
            subprocess.run([
                "ffmpeg", "-y", "-i", ar_audio_file,
                "-af", af_ar,
                proc_ar
            ], check=True, capture_output=True)
            dur_ar = get_duration(proc_ar)
            wbw_words = v.get("wbw_words", [])

            if wbw_translation and wbw_words and len(wbw_words) > 0:
                first_st = wbw_words[0].get("start", 0.0)
                slide_ar_base = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ar_base{'_9x16' if is_vertical else ''}.png")
                if first_st > 0.1 and os.path.exists(slide_ar_base):
                    arabic_timeline_items.append((slide_ar_base, first_st))

                for w_i, w_obj in enumerate(wbw_words):
                    slide_ar_w = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ar_w{w_i}{'_9x16' if is_vertical else ''}.png")
                    if w_i < len(wbw_words) - 1:
                        w_hold = max(0.1, wbw_words[w_i + 1]["start"] - w_obj["start"])
                    else:
                        w_hold = max(0.2, dur_ar - w_obj["start"])
                    arabic_timeline_items.append((slide_ar_w, w_hold))

                if arabic_timeline_items:
                    arabic_timeline_items.append((arabic_timeline_items[-1][0], 0.4))
            else:
                slide_ar = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ar{'_9x16' if is_vertical else ''}.png")
                arabic_timeline_items.append((slide_ar, dur_ar + 0.4))

        # 2. Process Urdu Audio & Slide if enabled
        proc_ur = None
        dur_ur = 0.0
        urdu_timeline_items = []
        should_render_ur = should_render_ur_global
        if should_render_ur and ur_audio_file and os.path.exists(ur_audio_file):
            proc_ur = os.path.join(RENDER_DIR, f"proc_{surah}_{ayah_num}_ur.wav")
            if surah_audio_prof and "urdu" in surah_audio_prof:
                af_ur = audio_dsp_engine.build_ffmpeg_filter_chain(surah_audio_prof["urdu"])
            else:
                af_ur = build_audio_filter_chain(
                    speed=audio_speed, pitch_semitones=pitch_semitones, random_humanize=random_humanize,
                    reverb_wet=reverb_wet * 0.7, bass_boost=bass_boost, treble_boost=treble_boost, mid_boost=mid_boost,
                    loudness_norm=loudness_norm, binaural_432=binaural_432, base_vol=1.0
                )
            subprocess.run([
                "ffmpeg", "-y", "-i", ur_audio_file,
                "-af", af_ur,
                proc_ur
            ], check=True, capture_output=True)
            dur_ur = get_duration(proc_ur)
            
            trans_ur_obj = next((t for t in v.get("translations", []) if t.get("resource_id") == 234), None)
            clean_ur = re.sub(r'<[^>]*>', '', trans_ur_obj.get("text", "")).strip() if trans_ur_obj else ""
            ur_words = clean_ur.split() if clean_ur else []

            if wbw_translation and len(ur_words) > 1:
                w_dur = dur_ur / len(ur_words)
                last_slide = None
                for w_idx in range(len(ur_words)):
                    slide_ur_w = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ur_w{w_idx}{'_9x16' if is_vertical else ''}.png")
                    urdu_timeline_items.append((slide_ur_w, w_dur))
                    last_slide = slide_ur_w
                if last_slide:
                    urdu_timeline_items.append((last_slide, 0.4))
            else:
                slide_ur = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_ur{'_9x16' if is_vertical else ''}.png")
                urdu_timeline_items.append((slide_ur, dur_ur + 0.4))

        # 3. Process English Audio & Slide if enabled
        proc_en = None
        dur_en = 0.0
        slide_en = None
        should_render_en = should_render_en_global
        if should_render_en and en_audio_file and os.path.exists(en_audio_file):
            proc_en = os.path.join(RENDER_DIR, f"proc_{surah}_{ayah_num}_en.wav")
            if surah_audio_prof and "english" in surah_audio_prof:
                af_en = audio_dsp_engine.build_ffmpeg_filter_chain(surah_audio_prof["english"])
            else:
                af_en = build_audio_filter_chain(
                    speed=audio_speed, pitch_semitones=pitch_semitones, random_humanize=random_humanize,
                    reverb_wet=reverb_wet * 0.7, bass_boost=bass_boost, treble_boost=treble_boost, mid_boost=mid_boost,
                    loudness_norm=loudness_norm, binaural_432=binaural_432, base_vol=1.0
                )
            subprocess.run([
                "ffmpeg", "-y", "-i", en_audio_file,
                "-af", af_en,
                proc_en
            ], check=True, capture_output=True)
            dur_en = get_duration(proc_en)
            slide_en = os.path.join(RENDER_DIR, f"slide_{surah}_{ayah_num}_en{'_9x16' if is_vertical else ''}.png")

        # Record YouTube Chapter start timestamp
        ayah_start_sec = current_sec
        chapters.append(f"{format_timestamp(ayah_start_sec)} Surah {surah_name_clean} - Ayah {ayah_num}")

        # Assemble Repeat Iterations and Sequence for this Ayah based on playback_order
        p_order = (playback_order or "ar_ur_en").lower()
        ar_item = (proc_ar, arabic_timeline_items, dur_ar + 0.4) if (proc_ar and arabic_timeline_items) else None
        ur_item = (proc_ur, urdu_timeline_items, dur_ur + 0.4) if (proc_ur and urdu_timeline_items) else None
        en_item = (proc_en, [(slide_en, dur_en + 0.4)] if slide_en else [], dur_en + 0.4) if (proc_en and slide_en) else None

        items_sequence = []
        if p_order == "only_ar":
            if ar_item: items_sequence.append(ar_item)
        elif p_order == "only_ur":
            if ur_item: items_sequence.append(ur_item)
            elif ar_item: items_sequence.append(ar_item)
        elif p_order == "only_en":
            if en_item: items_sequence.append(en_item)
            elif ar_item: items_sequence.append(ar_item)
        elif p_order in ["trans_first", "ur_en_ar"]:
            if ur_item: items_sequence.append(ur_item)
            if en_item: items_sequence.append(en_item)
            if ar_item: items_sequence.append(ar_item)
        elif p_order == "ur_ar":
            if ur_item: items_sequence.append(ur_item)
            if ar_item: items_sequence.append(ar_item)
        elif p_order == "ar_ur":
            if ar_item: items_sequence.append(ar_item)
            if ur_item: items_sequence.append(ur_item)
        elif p_order == "ar_en":
            if ar_item: items_sequence.append(ar_item)
            if en_item: items_sequence.append(en_item)
        elif p_order == "en_ar":
            if en_item: items_sequence.append(en_item)
            if ar_item: items_sequence.append(ar_item)
        else: # default "ar_ur_en" / "alternating"
            if ar_item: items_sequence.append(ar_item)
            if ur_item: items_sequence.append(ur_item)
            if en_item: items_sequence.append(en_item)

        if not items_sequence and ar_item:
            items_sequence.append(ar_item)

        for rep in range(repeat_times):
            for audio_file, slides_list, seg_dur in items_sequence:
                if audio_file:
                    audio_segments.append(audio_file)
                    audio_segments.append(silence_wav)
                if isinstance(slides_list, list):
                    slides_timeline.extend(slides_list)
                else:
                    slides_timeline.append((slides_list, seg_dur))
                current_sec += seg_dur

        # Record SRT Subtitle Entry
        ar_text = v.get("text_uthmani", "")
        trans_ur_obj = next((t for t in v.get("translations", []) if t.get("resource_id") == 234), None)
        ur_text = re.sub(r'<[^>]*>', '', trans_ur_obj.get("text", "")).strip() if trans_ur_obj else ""
        trans_en_obj = next((t for t in v.get("translations", []) if t.get("resource_id") == 20), None)
        en_text = re.sub(r'<[^>]*>', '', trans_en_obj.get("text", "")).strip() if trans_en_obj else ""
        srt_entries.append({
            "index": v_idx + 1,
            "start": ayah_start_sec,
            "end": current_sec,
            "ar": ar_text,
            "ur": ur_text if include_urdu else "",
            "en": en_text if include_english else ""
        })
            
        msg = f"Ayah {ayah_num} processed ({v_idx+1}/{len(verses)})."
        print(msg)
        if progress_cb:
            progress_cb({
                "phase": "ayah_completed",
                "message": msg,
                "completed_ayahs": v_idx + 1,
                "total_ayahs": len(verses),
                "percent": int(((v_idx + 1) / len(verses)) * 80),
                "elapsed_sec": int(round(time.time() - start_time, 1)),
                "eta_sec": int(eta)
            })

    # Concat master audio
    el_audio = int(round(time.time() - start_time, 1))
    if progress_cb:
        progress_cb({
            "phase": "mixing_audio",
            "message": "Synthesizing master studio audio...",
            "percent": 84,
            "elapsed_sec": el_audio,
            "eta_sec": 6
        })
    concat_audio_txt = os.path.join(RENDER_DIR, f"master_audio_list_{surah}.txt")
    with open(concat_audio_txt, "w") as f:
        for a in audio_segments:
            f.write(f"file \x27{a}\x27\n")
            
    master_wav = os.path.join(RENDER_DIR, f"master_audio_{surah}.wav")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_audio_txt,
        "-c:a", "pcm_s16le", "-ar", "48000", master_wav
    ], check=True, capture_output=True)

    # Mix Atmospheric ASMR Background Sound if enabled
    final_audio_wav = master_wav
    asmr_filter = ASMR_PRESETS.get((asmr_sound or "none").lower())
    if asmr_filter:
        if progress_cb: progress_cb(f"Synthesizing soothing atmospheric {asmr_sound} audio...")
        master_dur = get_duration(master_wav)
        ambient_wav = os.path.join(RENDER_DIR, f"ambient_{surah}.wav")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", asmr_filter,
            "-t", str(master_dur),
            "-c:a", "pcm_s16le", ambient_wav
        ], check=True, capture_output=True)

        mixed_wav = os.path.join(RENDER_DIR, f"master_mixed_{surah}.wav")
        vol_val = max(0.03, min(0.40, float(asmr_vol or 0.15)))
        subprocess.run([
            "ffmpeg", "-y",
            "-i", master_wav,
            "-i", ambient_wav,
            "-filter_complex", f"[0:a]volume=1.0[vocal];[1:a]volume={vol_val}[amb];[vocal][amb]amix=inputs=2:duration=first:dropout_transition=2",
            "-c:a", "pcm_s16le", "-ar", "48000", mixed_wav
        ], check=True, capture_output=True)
        final_audio_wav = mixed_wav
    
    # Concat timeline
    if progress_cb: progress_cb(f"Building {res_suffix} video timeline...")
    timeline_txt = os.path.join(RENDER_DIR, f"master_timeline_{surah}.txt")
    with open(timeline_txt, "w") as f:
        for img, dur in slides_timeline:
            f.write(f"file \x27{img}\x27\n")
            f.write(f"duration {dur}\n")
        f.write(f"file \x27{slides_timeline[-1][0]}\x27\n")
        
    v_raw = str(v_num).strip() if (v_num is not None and str(v_num).strip()) else ""
    if v_raw:
        v_str = v_raw.upper() if v_raw.upper().startswith("V") else f"V{v_raw}"
    else:
        v_str = ""

    if v_str:
        if ayah_start == 1 and ayah_end == total_chapter_verses:
            filename = f"{v_str}_{surah:03d}_{surah_name_clean}_{res_suffix}.mp4"
        else:
            filename = f"{v_str}_{surah:03d}_{surah_name_clean}_Ayah_{ayah_start}_to_{ayah_end}_{res_suffix}.mp4"
    else:
        if ayah_start == 1 and ayah_end == total_chapter_verses:
            filename = f"{surah:03d}_Surah_{surah_name_clean}_{qari}_Full_Surah_{res_suffix}.mp4"
        else:
            filename = f"{surah:03d}_Surah_{surah_name_clean}_{qari}_Ayah_{ayah_start}_to_{ayah_end}_{res_suffix}.mp4"
    out_mp4 = os.path.join(target_out_dir, filename)
    stem_name = os.path.splitext(filename)[0]
    chapters_path = os.path.join(target_out_dir, f"{stem_name}_chapters.txt")
    srt_path = os.path.join(target_out_dir, f"{stem_name}.srt")
    metadata_path = os.path.join(target_out_dir, f"{stem_name}_metadata.txt")

    # Write YouTube Chapters
    try:
        with open(chapters_path, "w", encoding="utf-8") as f_chap:
            f_chap.write("\n".join(chapters) + "\n")
    except Exception as e:
        print("Could not write chapters:", e)

    # Write Subtitles (.srt)
    try:
        with open(srt_path, "w", encoding="utf-8") as f_srt:
            for s_entry in srt_entries:
                f_srt.write(f"{s_entry['index']}\n")
                f_srt.write(f"{format_timestamp(s_entry['start'], srt=True)} --> {format_timestamp(s_entry['end'], srt=True)}\n")
                lines = [s_entry["ar"]]
                if s_entry["ur"]: lines.append(s_entry["ur"])
                if s_entry["en"]: lines.append(s_entry["en"])
                f_srt.write("\n".join(lines) + "\n\n")
    except Exception as e:
        print("Could not write SRT:", e)

    # Write Full YouTube SEO & Metadata TXT (ہر ویڈیو کا الگ الگ مکمل میٹا ڈیٹا)
    try:
        s_ar_name = SURAH_ARABIC_NAMES.get(surah, "")
        ch_text = "\n".join(chapters)
        tags_list = [
            f"surah {surah_name_clean.lower()}",
            f"surah {surah_name_clean.lower()} full",
            f"surah {surah_name_clean.lower()} with urdu translation",
            f"surah {surah_name_clean.lower()} english",
            f"surah {surah_name_clean.lower()} 4k",
            f"{qari_name.lower()}",
            "quran recitation",
            "beautiful quran recitation",
            "heart soothing tilawat",
            "quran before sleep",
            "quran for anxiety",
            "holy quran 4k",
            "quran status",
            "quran shorts",
            "quran reels",
            "quran video studio",
            "islamic video",
            "islamic reminder",
            "peaceful quran",
            "sleep quran",
            "quran tilawat hd",
            "surah full 4k",
            "every ayah quran",
            "quran audio",
            "4k quran video",
            "quran recitation 2026",
            "deep sleep quran",
            f"surah {surah}",
            f"{s_ar_name}",
            f"سورة {s_ar_name}"
        ]
        tags_str = ", ".join(tags_list)

        applied_design_label = template_name or template_id or bg_preset
        seq_label = f"Sequential Video #: {v_str}\n" if v_str else ""
        meta_content = f"""======================================================================
QURAN VIDEO STUDIO • YOUTUBE SEO & METADATA MASTER FILE
======================================================================
Generated Date: {time.strftime('%Y-%m-%d %H:%M:%S')}
Video Master: {filename}
{seq_label}Applied Design: {applied_design_label}
Format: MP4 (H.264 / AAC)
Resolution: {res_key.upper()} ({res_cfg['w']}x{res_cfg['h']})
Aspect Ratio: {aspect} ({'9:16 Vertical Shorts / Reels / TikTok' if is_vertical else '16:9 Landscape YouTube Widescreen'})
Surah: {surah}. {surah_name_clean} (سورة {s_ar_name})
Ayah Range: Ayah {ayah_start} to {ayah_end} (Total Ayahs in Chapter: {total_chapter_verses})
Qari / Reciter: {qari_name} ({qari})
Translations: Urdu: {'Yes' if include_urdu else 'No'} | Hindi: {'Yes' if include_hindi else 'No'} | English: {'Yes' if include_english else 'No'}
Translation Voiceover: {translation_voice}
Audio DSP Settings: Speed: {audio_speed}x | Pitch: {pitch_semitones:+.1f}st | Reverb: {reverb_wet} | 432Hz: {binaural_432} | LoudnessNorm: {loudness_norm}
ASMR Sound: {asmr_sound} (Volume: {asmr_vol})
Branding / Watermark: {watermark or 'None'}

======================================================================
1. RECOMMENDED YOUTUBE VIDEO TITLES (Pick One):
======================================================================
[Title 1 - High CTR Widescreen]:
Surah {surah_name_clean} Full (سورة {s_ar_name}) | Heart Soothing Quran Recitation | {qari_name}

[Title 2 - Peace & Anxiety Relief]:
Listen to Surah {surah_name_clean} Before Sleep | Relieve Anxiety & Gain Inner Peace (4K UHD)

[Title 3 - Multi-Language Translation]:
Surah {surah_name_clean} with Urdu & English Translation | Beautiful Voice | {qari_name}

[Title 4 - Shorts / Reels / TikTok (9:16)]:
Surah {surah_name_clean} (Ayah {ayah_start}-{ayah_end}) ✨ Heart Melting Tilawat | {qari_name} #Shorts #Quran

======================================================================
2. YOUTUBE VIDEO DESCRIPTION (Ready to Paste):
======================================================================
📖 Surah {surah_name_clean} (سورة {s_ar_name}) - Ayahs {ayah_start} to {ayah_end}
🎙️ Recited by: {qari_name}
🌐 Translations Included: Urdu (شمشاد علی خان / تفہیم), English (Saheeh International), Hindi
🎛️ Audio Mastered in Studio Quality (-14 LUFS Standard, 432 Hz Resonance)
📐 Format: {res_cfg['w']}x{res_cfg['h']} {'9:16 Shorts' if is_vertical else '16:9 Widescreen'} MP4 Master

✨ About Surah {surah_name_clean}:
Surah {surah_name_clean} is one of the most beloved and spiritually uplifting chapters of the Holy Quran. Reciting and listening to its verses with understanding brings deep peace to the heart, eases worldly stress and anxiety, and invites divine blessings into one's life.

⏱️ Timestamps & Chapters:
{ch_text}

🤲 Dua:
May Allah SWT accept this recitation from us, grant us the wisdom of the Holy Quran, and make it an ongoing charity (Sadaqah Jariyah) for everyone who listens and shares. Ameen.

🔔 Subscribe to our channel for daily soul-soothing Quran videos, translations, and beautiful recitations.
👍 Please Like, Comment, and Share to help spread the divine message of Allah.

#Quran #Surah{surah_name_clean} #QuranRecitation #Tilawat #HeartSoothing #IslamicStatus #QuranShorts #HolyQuran #{qari.replace(' ', '')}

======================================================================
3. TIMESTAMPS / CHAPTERS ONLY (For YouTube Description):
======================================================================
{ch_text}

======================================================================
4. 30+ RANKED YOUTUBE TAGS (Copy & Paste directly into YouTube Tags box):
======================================================================
{tags_str}

======================================================================
5. HASHTAGS:
======================================================================
#Quran #Surah{surah_name_clean} #Tilawat #QuranRecitation #{qari_name.replace(' ', '')} #IslamicVideo #QuranShorts #4KQuran #SoulSoothing #HeartMeltingTilawat

======================================================================
Associated Files for this Video:
- Video Master: {filename}
- Chapters File: {stem_name}_chapters.txt
- Subtitles File: {stem_name}.srt
- Metadata & SEO: {stem_name}_metadata.txt
======================================================================
"""
        with open(metadata_path, "w", encoding="utf-8") as f_meta:
            f_meta.write(meta_content)
        print(f"SUCCESS! Separate Metadata TXT created at: {metadata_path}")
    except Exception as e:
        print("Could not write metadata TXT:", e)
    
    el_enc = int(round(time.time() - start_time, 1))
    if progress_cb:
        progress_cb({
            "phase": "encoding_mp4",
            "message": f"Encoding final {res_suffix} MP4 master (Apple Silicon Hardware Acceleration)...",
            "percent": 94,
            "elapsed_sec": el_enc,
            "eta_sec": 3
        })
    cmd_master = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", timeline_txt,
        "-i", final_audio_wav,
        "-c:v", "h264_videotoolbox", "-b:v", "12M", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", res_cfg["ab"], "-ar", "48000",
        "-movflags", "+faststart",
        "-shortest",
        out_mp4
    ]
    try:
        subprocess.run(cmd_master, check=True, capture_output=True)
    except Exception as e_enc:
        print(f"Hardware VideoToolbox encode fallback to libx264 ultrafast: {e_enc}")
        cmd_fallback = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", timeline_txt,
            "-i", final_audio_wav,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(res_cfg["crf"]), "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", res_cfg["ab"], "-ar", "48000",
            "-movflags", "+faststart",
            "-shortest",
            out_mp4
        ]
        subprocess.run(cmd_fallback, check=True)
    print(f"SUCCESS! Video created at: {out_mp4}")
    
    # Open folder in macOS Finder and highlight the video file
    try:
        subprocess.run(["open", "-R", out_mp4])
    except Exception as e:
        print(f"Could not open Finder: {e}")
        
    tot_time = int(round(time.time() - start_time, 1))
    if progress_cb:
        progress_cb({
            "phase": "completed",
            "message": f"Finished! {filename}",
            "percent": 100,
            "elapsed_sec": tot_time,
            "eta_sec": 0,
            "video_url": f"/generated_videos/{filename}" if target_out_dir == OUT_DIR else f"/custom_video?path={urllib.parse.quote(out_mp4)}",
            "video_name": filename,
            "full_path": out_mp4,
            "chapters_file": chapters_path,
            "srt_file": srt_path,
            "metadata_file": metadata_path,
            "metadata_name": os.path.basename(metadata_path),
            "metadata_url": f"/generated_videos/{os.path.basename(metadata_path)}" if target_out_dir == OUT_DIR else f"/custom_video?path={urllib.parse.quote(metadata_path)}",
            "v_num": v_str,
            "surah": surah,
            "surah_name": surah_name_clean,
            "qari_name": qari_name,
            "template_name": applied_design_label,
            "template_id": template_id or "",
            "chapters_text": ch_text,
            "tags_str": tags_str
        })
    return out_mp4

def compile_bulk_metadata(completed_jobs, target_out_dir):
    """
    Creates a single unified bulk_metadata.txt containing blocks formatted with
    V-number, Surah Name, Video Title, Description, Chapters, Tags, and Applied Design.
    """
    out_file = os.path.join(target_out_dir, "bulk_metadata.txt")
    lines = [
        "======================================================================",
        "QURAN VIDEO STUDIO • BULK EXPORT MASTER METADATA MANIFEST",
        "======================================================================",
        f"Export Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Videos in Batch: {len(completed_jobs)}",
        "======================================================================\n"
    ]

    for item in completed_jobs:
        v_raw = str(item.get("v_num") or "V1").strip()
        v_num = v_raw.upper() if v_raw.upper().startswith("V") else f"V{v_raw}"
        s_num = item.get("surah", 1)
        canonical_name = SURAH_NAMES.get(s_num, "")
        raw_name = canonical_name or item.get("surah_name") or f"{s_num}"
        s_short = raw_name[6:].strip() if raw_name.startswith("Surah ") else raw_name.strip()
        s_display = f"Surah {s_short}"
        s_ar = SURAH_ARABIC_NAMES.get(s_num, "")
        qari_name = item.get("qari_name") or item.get("qari", "Reciter")
        tpl_name = item.get("template_name") or item.get("template_id") or "Classic Islamic"
        video_name = item.get("video_name", "")
        meta_name = item.get("metadata_name", "")

        block = f"""----------------------------------------------------------------------
VIDEO {v_num}: {s_display} (سورة {s_ar})
----------------------------------------------------------------------
Video File: {video_name}
Metadata File: {meta_name}
Applied Design: {tpl_name}
Reciter: {qari_name}

[RECOMMENDED YOUTUBE TITLE]
{s_display} Full (سورة {s_ar}) | Heart Soothing Quran Recitation | {qari_name}

[YOUTUBE DESCRIPTION]
📖 {s_display} (سورة {s_ar})
🎙️ Recited by: {qari_name}
🎨 Visual Theme: {tpl_name}
✨ Reciting and listening to {s_display} brings deep peace to the heart, removes worries, and invites Allah's mercy.

🤲 Dua: May Allah SWT accept this recitation from us and make it a continuous charity (Sadaqah Jariyah). Ameen.

[TIMESTAMPS / CHAPTERS]
{item.get('chapters_text', '00:00 Surah ' + s_name + ' Full Recitation')}

[30+ YOUTUBE TAGS]
{item.get('tags_str', f'surah {s_name.lower()}, surah {s_name.lower()} full, quran recitation')}

"""
        lines.append(block)

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"SUCCESS! Bulk metadata master file saved at: {out_file}")
    return out_file

def generate_custom_video(
    audio_path,
    title="Custom Dua",
    text_ar="",
    text_ur="",
    text_en="",
    template_id=None,
    template_bg=None,
    template_style=None,
    highlight_color="#ffe600",
    highlight_style="glow",
    resolution="1080p",
    aspect="16:9",
    output_dir=None,
    progress_cb=None
):
    start_time = time.time()
    target_out_dir = output_dir if output_dir and os.path.exists(output_dir) else OUT_DIR
    os.makedirs(target_out_dir, exist_ok=True)
    os.makedirs(RENDER_DIR, exist_ok=True)

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Audio duration
    dur_sec = get_duration(audio_path)
    if dur_sec <= 0:
        dur_sec = 10.0

    is_vertical = (str(aspect).strip() == "9:16")

    # Template resolution
    if template_id and not template_bg:
        try:
            from template_manager import get_template_by_id
            t_obj = get_template_by_id(template_id)
            if t_obj:
                if is_vertical and t_obj.get("image_9x16"):
                    template_bg = t_obj.get("image_9x16")
                elif not is_vertical and t_obj.get("image_16x9"):
                    template_bg = t_obj.get("image_16x9")
                elif t_obj.get("image_url"):
                    template_bg = t_obj.get("image_url")
                if not template_style:
                    template_style = t_obj.get("style", "")
        except Exception:
            pass

    res_key = (resolution or "1080p").lower()
    res_cfg = RESOLUTIONS.get(res_key, RESOLUTIONS["1080p"]).copy()
    if is_vertical:
        orig_w, orig_h = res_cfg["w"], res_cfg["h"]
        res_cfg["w"] = orig_h
        res_cfg["h"] = orig_w
        res_suffix = f"{res_cfg['suffix']}_9x16_Shorts"
    else:
        res_suffix = res_cfg["suffix"]

    if progress_cb:
        progress_cb({"phase": "rendering_slide", "message": "Rendering custom slide...", "percent": 20})

    tpl_qs = ""
    if template_style:
        tpl_qs += f"&tpl_style={template_style}"
    if template_bg:
        tpl_qs += f"&template_bg={urllib.parse.quote(template_bg)}"

    url_slide = (
        f"http://localhost:8765/video_render/render_studio_slide.html?custom=1"
        f"&title={urllib.parse.quote(title)}"
        f"&text_ar={urllib.parse.quote(text_ar)}"
        f"&text_ur={urllib.parse.quote(text_ur)}"
        f"&text_en={urllib.parse.quote(text_en)}"
        f"&color={highlight_color.replace('#','%23')}&style={highlight_style}"
        f"&res={res_key}&aspect={aspect}{tpl_qs}"
    )

    slide_img = os.path.join(RENDER_DIR, f"custom_slide_{int(start_time)}{'_9x16' if is_vertical else ''}.png")
    
    slide_manifest = [{
        "type": "static",
        "url": url_slide,
        "out": slide_img
    }]
    batch_render_all_slides(slide_manifest, res_cfg["w"], res_cfg["h"], progress_cb, start_time)

    if not os.path.exists(slide_img):
        cmd_shot = [
            CHROME_BIN, "--headless", "--disable-gpu", "--hide-scrollbars",
            f"--window-size={res_cfg['w']},{res_cfg['h']}",
            f"--screenshot={slide_img}",
            url_slide
        ]
        subprocess.run(cmd_shot, check=True, capture_output=True)

    if progress_cb:
        progress_cb({"phase": "encoding_mp4", "message": "Encoding video master (Apple Silicon Acceleration)...", "percent": 75})

    clean_title = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]+', '_', title).strip('_') or "Custom_Dua"
    filename = f"{clean_title}_{res_suffix}_{int(start_time)}.mp4"
    out_mp4 = os.path.join(target_out_dir, filename)
    stem_name = os.path.splitext(filename)[0]
    metadata_path = os.path.join(target_out_dir, f"{stem_name}_metadata.txt")

    cmd_enc = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", slide_img,
        "-i", audio_path,
        "-c:v", "h264_videotoolbox", "-b:v", "12M", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", res_cfg["ab"], "-ar", "48000",
        "-t", str(dur_sec),
        "-movflags", "+faststart",
        "-shortest",
        out_mp4
    ]
    try:
        subprocess.run(cmd_enc, check=True, capture_output=True)
    except Exception:
        cmd_fallback = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", slide_img,
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(res_cfg["crf"]), "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", res_cfg["ab"], "-ar", "48000",
            "-t", str(dur_sec),
            "-movflags", "+faststart",
            "-shortest",
            out_mp4
        ]
        subprocess.run(cmd_fallback, check=True)

    meta_content = f"""======================================================================
QURAN VIDEO STUDIO • CUSTOM RECITATION & DUA VIDEO
======================================================================
Date: {time.strftime('%Y-%m-%d %H:%M:%S')}
Title: {title}
Video Master: {filename}
Resolution: {res_key.upper()} ({res_cfg['w']}x{res_cfg['h']})
Aspect Ratio: {aspect}
Duration: {dur_sec:.1f}s

Arabic Text:
{text_ar}

Urdu Translation:
{text_ur}

English Translation:
{text_en}
======================================================================
"""
    with open(metadata_path, "w", encoding="utf-8") as f_meta:
        f_meta.write(meta_content)

    if progress_cb:
        progress_cb({"phase": "completed", "message": "Custom video exported successfully!", "percent": 100})

    return out_mp4

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--surah", type=int, default=55)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=4)
    parser.add_argument("--full", action="store_true", help="Export full Surah")
    parser.add_argument("--qari", type=str, default="hani")
    parser.add_argument("--color", type=str, default="#ffe600")
    parser.add_argument("--style", type=str, default="glow")
    parser.add_argument("--bg", type=str, default="midnight")
    parser.add_argument("--res", type=str, default="1080p")
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--asmr", type=str, default="rain")
    parser.add_argument("--asmr-vol", type=float, default=0.15)
    parser.add_argument("--template", type=str, default="", help="Template ID from catalog")
    parser.add_argument("--aspect", type=str, default="16:9", choices=["16:9", "9:16"], help="Aspect ratio (16:9 YouTube or 9:16 Shorts/Reels)")
    parser.add_argument("--voice", type=str, default="urdu", choices=["urdu", "english", "both", "none"], help="Translation voiceover")
    parser.add_argument("--watermark", type=str, default="", help="Channel branding watermark text")
    parser.add_argument("--repeat", type=int, default=1, help="Hifz repeat count per Ayah")
    parser.add_argument("--wbw", action="store_true", default=True, help="Enable Word-by-Word karaoke synchronization")
    args = parser.parse_args()
    
    t_id = args.template or (args.bg if args.bg.startswith("tmpl_") else None)

    video_path = generate_video(
        surah=args.surah, ayah_start=args.start, ayah_end=args.end,
        qari=args.qari, highlight_color=args.color, highlight_style=args.style,
        bg_preset=args.bg, template_id=t_id, resolution=args.res, aspect=args.aspect,
        translation_voice=args.voice, watermark=args.watermark, repeat_count=args.repeat,
        output_dir=args.out, asmr_sound=args.asmr, asmr_vol=args.asmr_vol,
        wbw_translation=args.wbw, full_surah=args.full
    )
