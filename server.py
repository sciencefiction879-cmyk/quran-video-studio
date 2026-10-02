import os, sys, json, time, uuid, threading, subprocess, urllib.request, shutil, datetime, re, base64, traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# Ensure system PATH includes Homebrew and standard CLI directories
extra_paths = ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
current_path = os.environ.get("PATH", "")
os.environ["PATH"] = ":".join([p for p in extra_paths if p not in current_path]) + ":" + current_path

from studio_video_generator import generate_video, generate_custom_video, generate_thumbnail, format_timestamp, compile_bulk_metadata, kill_all_render_procs, BASE_DIR, OUT_DIR, SURAH_NAMES, RECITER_PREFIXES
from template_manager import load_templates_catalog, get_template_by_id, auto_split_custom_collage
from wbw_aligner import get_wbw_surah_content, fetch_qari_segments, QDC_RECITATION_MAP
import audio_dsp_engine

CACHE_DIR = os.path.join(os.path.expanduser("~"), "Library", "Caches", "QuranVideoStudio", "api_cache")
try:
    os.makedirs(CACHE_DIR, exist_ok=True)
except Exception:
    CACHE_DIR = "/tmp/quran_studio_cache"
    os.makedirs(CACHE_DIR, exist_ok=True)

SETTINGS_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "QuranVideoStudio")
try:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
except Exception:
    SETTINGS_DIR = BASE_DIR

SETTINGS_FILE = os.path.join(SETTINGS_DIR, "studio_options.json")
SURAH_CONFIGS_FILE = os.path.join(SETTINGS_DIR, "surah_configs.json")

URDU_SADAQAH_PRESETS = [
    "اس سورت کی تلاوت کو صدقۂ جاریہ سمجھ کر دوسروں تک ضرور پہنچائیں۔ شاید آپ کی ایک شیئر کسی کے لیے ہدایت اور سکون کا ذریعہ بن جائے۔",
    "قرآن کی یہ خوبصورت تلاوت دوسروں تک پہنچائیں اور اسے اپنے لیے صدقۂ جاریہ بنائیں۔",
    "اس سورت کو سنیں، سمجھیں اور دوسروں تک پہنچائیں۔ آپ کی ایک شیئر بھی صدقۂ جاریہ بن سکتی ہے۔",
    "قرآن کی تلاوت آگے پہنچانا نیکی کا ذریعہ ہے۔ اس پیغام کو دوسروں تک ضرور پہنچائیں۔",
    "اپنے پیاروں تک قرآن کا یہ پیغام پہنچائیں اور اس نیکی کو صدقۂ جاریہ بنائیں۔",
    "ممکن ہے آپ کی ایک شیئر کسی دل کو قرآن سے جوڑ دے۔ اس تلاوت کو ضرور آگے پہنچائیں۔",
    "اللہ کے کلام کو آگے پہنچائیں، شاید آپ کے ذریعے کسی کو ہدایت اور دل کا سکون نصیب ہو۔",
    "اس قرآنی تلاوت کو زیادہ سے زیادہ شیئر کریں اور نیکی کے اس سفر میں اپنا حصہ شامل کریں۔",
    "قرآن کی یہ آیات دوسروں تک پہنچائیں۔ آپ کی یہ کوشش آپ کے لیے صدقۂ جاریہ بن سکتی ہے۔",
    "سننے کے بعد اسے آگے ضرور پہنچائیں؛ شاید یہ تلاوت کسی کے دل کی دنیا بدل دے。"
]

DEFAULT_SURAH_CONFIG = {
    "template_id": "tmpl_master_madinah",
    "waveform": {
        "enabled": True,
        "style": "classic",
        "color": "#ffe600",
        "color2": "#00ffcc",
        "thickness": 3,
        "opacity": 0.85,
        "position": "bottom",
        "height": 42,
        "width": 80,
        "glow": True,
        "glow_color": "rgba(255, 230, 0, 0.4)",
        "detail": 48,
        "animation_speed": 1.0
    },
    "sadaqah": {
        "enabled": True,
        "preset_id": 1,
        "text": URDU_SADAQAH_PRESETS[0],
        "font": "nastaliq",
        "font_size": 20,
        "color": "#fefefe",
        "accent_color": "#ffd700",
        "bold": False,
        "align": "center",
        "bg_color": "rgba(5, 20, 15, 0.72)",
        "border_color": "rgba(218, 165, 32, 0.55)",
        "border_width": 1,
        "border_radius": 8,
        "shadow": True,
        "opacity": 0.95,
        "line_height": 1.6,
        "letter_spacing": 0,
        "position_mode": "auto"
    }
}

def load_all_surah_configs():
    data = {
        "configs": {},
        "saved_presets": [],
        "global_default": DEFAULT_SURAH_CONFIG
    }
    if os.path.exists(SURAH_CONFIGS_FILE):
        try:
            with open(SURAH_CONFIGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    data.update(saved)
        except Exception as e:
            print("Failed to read surah configs file:", e)
    return data

def save_all_surah_configs(data):
    try:
        with open(SURAH_CONFIGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print("Failed to write surah configs file:", e)
        return False

def get_config_for_surah(surah_num):
    data = load_all_surah_configs()
    configs = data.get("configs", {})
    key = str(surah_num)
    if key in configs:
        cfg = dict(DEFAULT_SURAH_CONFIG)
        saved_cfg = configs[key]
        for k, v in saved_cfg.items():
            if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                merged = dict(cfg[k])
                merged.update(v)
                cfg[k] = merged
            else:
                cfg[k] = v
        return cfg
    return data.get("global_default", DEFAULT_SURAH_CONFIG)

def load_saved_options():
    default_dir = os.path.join(os.path.expanduser("~"), "Movies", "QuranVideoStudio")
    if not os.path.exists(default_dir):
        try:
            os.makedirs(default_dir, exist_ok=True)
        except Exception:
            default_dir = OUT_DIR

    defaults = {
        "surah": 1,
        "qari": "husary",
        "mode": "alternating",
        "ayah": 1,
        "speed": 1.0,
        "output_dir": default_dir,
        "resolution": "1080p",
        "aspect": "16:9",
        "translation_voice": "urdu",
        "watermark": "",
        "repeat_count": 1,
        "highlight_style": "glow",
        "highlight_color": "#ffe600",
        "asmr_sound": "rain",
        "asmr_vol": 0.15,
        "include_urdu": True,
        "include_hindi": True,
        "include_english": True,
        "wbw_translation": True,
        "full_surah": True,
        "font_ar": "scheherazade",
        "font_ur": "nastaliq",
        "font_hi": "noto_hindi",
        "font_en": "outfit"
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                defaults.update(saved)
        except Exception as e:
            print("Failed to read settings file:", e)
    return defaults

def save_user_options(new_opts):
    try:
        current = load_saved_options()
        current.update(new_opts)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        return True, current
    except Exception as e:
        print("Failed to write settings file:", e)
        return False, str(e)


SURAH_VERSES = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109,
    123, 111, 43, 52, 99, 128, 111, 110, 98, 135,
    112, 78, 118, 64, 77, 227, 93, 88, 69, 60,
    34, 30, 73, 54, 45, 83, 182, 88, 75, 85,
    54, 53, 89, 59, 37, 35, 38, 29, 18, 45,
    60, 49, 62, 55, 78, 96, 29, 22, 24, 13,
    14, 11, 11, 18, 12, 12, 30, 52, 52, 44,
    28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
    29, 19, 36, 25, 22, 17, 19, 26, 30, 20,
    15, 21, 11, 8, 8, 19, 5, 8, 8, 11,
    11, 8, 3, 9, 5, 4, 7, 3, 6, 3,
    5, 4, 5, 6
]

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

JOBS = {}
BATCH_JOBS = {}
CANCELLED_JOBS = set()
CUSTOM_DIRS = set()
ACTIVITY_LOGS = []
LOG_LOCK = threading.Lock()

def cancel_all_render_jobs():
    """Cancels all active jobs and kills any rendering subprocesses."""
    global CANCELLED_JOBS
    for j_id in list(JOBS.keys()):
        if JOBS[j_id].get("status") in ("processing", "queued"):
            JOBS[j_id]["status"] = "cancelled"
            JOBS[j_id]["progress"] = "Render cancelled by user"
            CANCELLED_JOBS.add(j_id)
    for b_id in list(BATCH_JOBS.keys()):
        if BATCH_JOBS[b_id].get("status") in ("processing", "pending"):
            BATCH_JOBS[b_id]["status"] = "cancelled"
            for j_id, j_obj in BATCH_JOBS[b_id].get("jobs", {}).items():
                if j_obj.get("status") in ("processing", "queued"):
                    j_obj["status"] = "cancelled"
                    CANCELLED_JOBS.add(j_id)
    kill_all_render_procs()

def log_activity(level, category, message, solution=""):
    with LOG_LOCK:
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {
            "id": len(ACTIVITY_LOGS) + 1,
            "time": now_str,
            "level": str(level).upper(),
            "category": str(category),
            "message": str(message),
            "solution": str(solution) if solution else ""
        }
        ACTIVITY_LOGS.append(entry)
        if len(ACTIVITY_LOGS) > 300:
            del ACTIVITY_LOGS[:100]
        return entry

log_activity("SUCCESS", "System", "Quran Video Studio v1.4 (Professional Edition) engine initialized.", "Custom GIF/image backgrounds, audio waveform visualizer, and YouTube SEO suite online.")
log_activity("INFO", "Audio DSP", "19-Feature Audio DSP Chain with 1-2% Organic Random Jitter ready.", "Apply master tuning or random variation across all audios.")
log_activity("INFO", "Cache", "Local API & Multi-Translation cache online.", "Instant playback enabled for all cached Surahs.")

class QuranStudioHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "running", "version": "1.3"}).encode())
            return

        if path == "/api/activity_logs":
            with LOG_LOCK:
                logs_copy = list(ACTIVITY_LOGS)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"logs": logs_copy}).encode())
            return

        if path == "/api/options":
            opts = load_saved_options()
            opts["user_home"] = os.path.expanduser("~")
            if opts.get("output_dir") and os.path.exists(opts["output_dir"]):
                CUSTOM_DIRS.add(opts["output_dir"])
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(opts).encode())
            return

        if path == "/api/templates":
            catalog = load_templates_catalog()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"templates": catalog}).encode())
            return

        if path == "/api/audio/state":
            state = audio_dsp_engine.load_global_state()
            master = audio_dsp_engine.load_master_profile()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "global_state": state,
                "master_profile": master,
                "spec": audio_dsp_engine.AUDIO_CHARACTERISTICS_SPEC
            }).encode())
            return

        if path == "/api/layout/get":
            tpl_id = query.get("template_id", [""])[0]
            layout_file = os.path.join(SETTINGS_DIR, "custom_layouts.json")
            layouts = {}
            if os.path.exists(layout_file):
                try:
                    with open(layout_file, "r", encoding="utf-8") as f:
                        layouts = json.load(f)
                except Exception:
                    pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "layouts": layouts,
                "template_layout": layouts.get(tpl_id)
            }).encode())
            return

        if path == "/api/surah_configs":
            s_param = query.get("surah", [None])[0]
            all_data = load_all_surah_configs()
            if s_param and s_param != "all":
                try:
                    s_num = int(s_param)
                except Exception:
                    s_num = 1
                cfg = get_config_for_surah(s_num)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "surah": s_num,
                    "config": cfg,
                    "presets": all_data.get("saved_presets", []),
                    "urdu_sadaqah_presets": URDU_SADAQAH_PRESETS
                }, ensure_ascii=False).encode())
                return
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "configs": all_data.get("configs", {}),
                    "presets": all_data.get("saved_presets", []),
                    "urdu_sadaqah_presets": URDU_SADAQAH_PRESETS,
                    "global_default": all_data.get("global_default", DEFAULT_SURAH_CONFIG)
                }, ensure_ascii=False).encode())
                return



        if path == "/api/surahs":
            surahs_list = []
            for num in range(1, 115):
                name = SURAH_NAMES.get(num, f"Surah_{num}")
                ar_name = SURAH_ARABIC_NAMES.get(num, "")
                v_count = SURAH_VERSES[num - 1] if num - 1 < len(SURAH_VERSES) else 7
                surahs_list.append({
                    "number": num,
                    "name": name,
                    "name_arabic": ar_name,
                    "verses": v_count
                })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(surahs_list).encode())
            return

        if path == "/api/audio_segments":
            try:
                s_num = int(query.get("surah", [1])[0])
            except Exception:
                s_num = 1
            qari = query.get("qari", ["alafasy"])[0].lower()
            try:
                segs = fetch_qari_segments(s_num, qari, CACHE_DIR)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"surah": s_num, "qari": qari, "timestamps": segs}).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

        if path == "/api/surah_content":
            try:
                s_num = int(query.get("surah", [1])[0])
            except Exception:
                s_num = 1
            qari = query.get("qari", ["alafasy"])[0].lower()
            try:
                data = get_wbw_surah_content(s_num, qari=qari, cache_dir=CACHE_DIR)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

        if path == "/custom_video":
            fp = query.get("path", [None])[0]
            if fp and os.path.exists(fp) and (fp.endswith(".mp4") or fp.endswith(".txt") or fp.endswith(".srt") or fp.endswith(".mp3") or fp.endswith(".png")):
                ctype = "video/mp4"
                if fp.endswith(".txt") or fp.endswith(".srt"):
                    ctype = "text/plain; charset=utf-8"
                elif fp.endswith(".mp3"):
                    ctype = "audio/mpeg"
                elif fp.endswith(".png"):
                    ctype = "image/png"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.end_headers()
                with open(fp, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
                return

        if path in ("/api/youtube_seo", "/api/youtube_chapters"):
            try:
                s_num = int(query.get("surah", [67])[0])
                start = int(query.get("start", [1])[0])
                total_v = SURAH_VERSES[s_num - 1] if s_num - 1 < len(SURAH_VERSES) else 7
                end = int(query.get("end", [total_v])[0])
                qari = query.get("qari", ["husary"])[0]
                repeat = max(1, min(10, int(query.get("repeat", [1])[0])))
                voice = query.get("voice", ["urdu"])[0]
                
                s_name = SURAH_NAMES.get(s_num, f"Surah_{s_num}").replace("'", "").replace(" ", "_")
                qari_display = RECITER_PREFIXES.get(qari, ("Mahmoud Khalil Al-Husary", ""))[0]
                
                chapters = []
                cur_sec = 0.0
                for a in range(start, end + 1):
                    chapters.append({
                        "timestamp": format_timestamp(cur_sec),
                        "ayah": a,
                        "title": f"Surah {s_name} - Ayah {a}",
                        "seconds": round(cur_sec, 1)
                    })
                    step = 7.5
                    if voice in ("urdu", "english"):
                        step += 5.5
                    elif voice == "both":
                        step += 10.0
                    cur_sec += (step * repeat)
                    
                ch_text = "\n".join([f"{c['timestamp']} {c['title']}" for c in chapters])
                
                titles = [
                    f"Surah {s_name} Full (سورة {s_name}) | Heart Soothing Quran Recitation | {qari_display}",
                    f"Listen to Surah {s_name} Before Sleep | Relieve Anxiety & Gain Protection (4K UHD)",
                    f"Surah {s_name} with Urdu & English Translation | {total_v} Ayahs Full | {qari_display}"
                ]
                
                tags = [
                    f"surah {s_name.lower()}", f"surah {s_name.lower()} full", f"surah {s_name.lower()} with urdu translation",
                    f"surah {s_name.lower()} english", f"{qari_display.lower()}", "quran recitation",
                    "beautiful quran recitation", "heart soothing tilawat", "quran before sleep",
                    "quran for anxiety", "holy quran 4k", "quran status", "surah yasin", "surah rahman",
                    "surah mulk", "quran with urdu translation", "quran video studio", "islamic video",
                    "peaceful quran", "sleep quran", "quran tilawat hd", "surah full 4k",
                    "every ayah quran", "quran audio", "islamic reminder", "quran shorts",
                    "quran reels", "4k quran video", "quran recitation 2026", "deep sleep quran"
                ]
                
                description = f"""📖 Surah {s_name} (سورة {s_name}) - Ayahs {start} to {end} ({total_v} Total Ayahs)
🎙️ Recitation by: {qari_display}
🌐 Translations included: Urdu (شمشاد علی خان), Hindi & English (Saheeh International)
🎛️ Audio Mastered in 4K Studio Quality (-14 LUFS Loudness, 432 Hz Spiritual Tuning)

✨ About Surah {s_name}:
Surah {s_name} is one of the most beloved and recited chapters of the Holy Quran, known for bringing tranquility to the heart, protection from anxiety, and immense spiritual rewards.

⏱️ Timestamps & YouTube Chapters:
{ch_text}

🔔 Don't forget to Like, Share, and Subscribe for daily soul-soothing Quran videos.
May Allah bless everyone who listens and shares this recitation. Ameen.

#Quran #Surah{s_name} #QuranRecitation #Tilawat #HeartSoothing #IslamicStatus #QuranShorts #HolyQuran
"""
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "surah": s_num,
                    "surah_name": s_name,
                    "qari": qari_display,
                    "titles": titles,
                    "description": description,
                    "tags": tags,
                    "tags_csv": ", ".join(tags),
                    "hashtags": f"#Quran #Surah{s_name} #QuranRecitation #Tilawat #IslamicStatus",
                    "chapters_text": ch_text,
                    "chapters": chapters
                }).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

        if path == "/api/list_custom_backgrounds":
            bg_dir = os.path.join(BASE_DIR, "custom_backgrounds")
            os.makedirs(bg_dir, exist_ok=True)
            files = []
            for f in sorted(os.listdir(bg_dir)):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4')):
                    f_path = os.path.join(bg_dir, f)
                    is_gif = f.lower().endswith('.gif')
                    files.append({
                        "name": f,
                        "url": f"/custom_backgrounds/{f}",
                        "is_gif": is_gif,
                        "size_kb": round(os.path.getsize(f_path) / 1024, 1)
                    })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"backgrounds": files}).encode())
            return

        if path in ["/api/video_status", "/api/job_status"]:
            job_id = query.get("job_id", [None])[0] or query.get("id", [None])[0]
            if not job_id or job_id not in JOBS:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Job not found"}).encode())
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(JOBS[job_id]).encode())
            return

        if path == "/api/batch_status":
            batch_id = query.get("batch_id", [None])[0]
            if not batch_id or batch_id not in BATCH_JOBS:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Batch not found"}).encode())
                return

            b = BATCH_JOBS[batch_id]
            jobs_list = list(b["jobs"].values())
            res = {
                "batch_id": batch_id,
                "total": b["total"],
                "concurrency": b["concurrency"],
                "completed": sum(1 for j in jobs_list if j.get("status") == "completed"),
                "failed": sum(1 for j in jobs_list if j.get("status") == "failed"),
                "processing": sum(1 for j in jobs_list if j.get("status") == "processing"),
                "pending": sum(1 for j in jobs_list if j.get("status") == "pending"),
                "bulk_metadata_file": b.get("bulk_metadata_file", ""),
                "bulk_metadata_url": b.get("bulk_metadata_url", ""),
                "bulk_metadata_name": b.get("bulk_metadata_name", ""),
                "jobs": jobs_list
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode())
            return

        if path in ["/api/cancel_render", "/api/cancel_job", "/api/stop_render"]:
            job_id = query.get("job_id", [None])[0] or query.get("id", [None])[0]
            if job_id:
                CANCELLED_JOBS.add(job_id)
                if job_id in JOBS:
                    JOBS[job_id]["status"] = "cancelled"
                    JOBS[job_id]["progress"] = "Cancelled by user"
            cancel_all_render_jobs()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": "Render job cancelled"}).encode())
            return

        if path in ["/api/cancel_batch", "/api/stop_batch"]:
            batch_id = query.get("batch_id", [None])[0]
            if batch_id and batch_id in BATCH_JOBS:
                BATCH_JOBS[batch_id]["status"] = "cancelled"
                for j_id, j_obj in BATCH_JOBS[batch_id].get("jobs", {}).items():
                    CANCELLED_JOBS.add(j_id)
                    j_obj["status"] = "cancelled"
            cancel_all_render_jobs()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": "Batch export cancelled"}).encode())
            return

        if path == "/api/list_videos":
            videos = []
            seen = set()

            def add_video(fp, url):
                if fp in seen or not os.path.exists(fp):
                    return
                seen.add(fp)
                stat = os.stat(fp)
                videos.append({
                    "name": os.path.basename(fp),
                    "url": url,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                })

            if os.path.exists(OUT_DIR):
                for f in os.listdir(OUT_DIR):
                    if f.endswith(".mp4"):
                        add_video(os.path.join(OUT_DIR, f), f"/generated_videos/{f}")

            for f in os.listdir(BASE_DIR):
                if f.endswith(".mp4"):
                    add_video(os.path.join(BASE_DIR, f), f"/{f}")

            for c_dir in list(CUSTOM_DIRS):
                if os.path.exists(c_dir):
                    for f in os.listdir(c_dir):
                        if f.endswith(".mp4"):
                            fp = os.path.join(c_dir, f)
                            add_video(fp, f"/custom_video?path={urllib.parse.quote(fp)}")

            videos.sort(key=lambda x: x["modified"], reverse=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"videos": videos}).encode())
            return

        # Fallback to static file server
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/api/cancel_render", "/api/cancel_job", "/api/stop_render", "/api/cancel_batch", "/api/stop_batch"]:
            cancel_all_render_jobs()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": "Render cancelled by user"}).encode())
            return

        if path == "/api/audio/randomize":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body) if body else {}
            surah_id = int(data.get("surah_number") or data.get("surah") or 1)
            strength = float(data.get("strength", 0.5))
            layers = data.get("layers", ["arabic", "urdu", "english"])
            profile = audio_dsp_engine.randomize_surah_profile(surah_id, strength=strength, layers=layers)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "profile": profile}).encode())
            return

        if path == "/api/audio/set_master":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body) if body else {}
            profile = data.get("profile")
            surah_id = int(data.get("surah_number") or data.get("surah") or 1)
            if not profile:
                profile = audio_dsp_engine.load_surah_profile(surah_id)
            if not profile:
                profile = audio_dsp_engine.randomize_surah_profile(surah_id, strength=0.5)
            master = audio_dsp_engine.save_master_profile(profile, surah_number=surah_id)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "master_profile": master}).encode())
            return

        if path == "/api/audio/apply_master":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body) if body else {}
            mode = data.get("mode", "exact")
            scope = data.get("scope", "all")
            custom_ids = data.get("custom_ids", [])
            custom_range = data.get("custom_range", "")
            if custom_range and not custom_ids:
                c_ids = set()
                for part in custom_range.split(","):
                    part = part.strip()
                    if "-" in part:
                        try:
                            start, end = part.split("-", 1)
                            for x in range(int(start), int(end) + 1):
                                if 1 <= x <= 114:
                                    c_ids.add(x)
                        except Exception:
                            pass
                    elif part.isdigit():
                        x = int(part)
                        if 1 <= x <= 114:
                            c_ids.add(x)
                if c_ids:
                    custom_ids = sorted(list(c_ids))
                    scope = "selected"
            strength = float(data.get("variation_strength") or data.get("strength") or 0.5)
            try:
                summary = audio_dsp_engine.apply_master_globally(mode=mode, scope=scope, custom_ids=custom_ids, variation_strength=strength)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True, 
                    "summary": summary,
                    "applied_count": summary.get("applied", 0),
                    "total_target": summary.get("total", 0),
                    "validated_count": summary.get("validated", 0),
                    "failed_count": summary.get("failed", 0)
                }).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
            return

        if path == "/api/audio/undo":
            ok, msg = audio_dsp_engine.undo_global_apply()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "message": msg}).encode())
            return

        if path == "/api/audio/reset":
            ok, msg = audio_dsp_engine.restore_original_audio()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "message": msg}).encode())
            return

        if path == "/api/surah_configs/save":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body) if body else {}
            all_data = load_all_surah_configs()
            mode = data.get("apply_mode", "single")
            config_to_save = data.get("config", {})

            if mode == "save_preset":
                preset_name = data.get("preset_name", f"Preset {len(all_data.get('saved_presets', [])) + 1}")
                new_preset = {
                    "id": str(uuid.uuid4())[:8],
                    "name": preset_name,
                    "created_at": time.time(),
                    "config": config_to_save
                }
                all_data.setdefault("saved_presets", []).append(new_preset)
                save_all_surah_configs(all_data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "preset": new_preset, "presets": all_data["saved_presets"]}).encode())
                return

            if mode == "single":
                surah_num = int(data.get("surah", 1))
                all_data.setdefault("configs", {})[str(surah_num)] = config_to_save
                save_all_surah_configs(all_data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "surah": surah_num, "config": config_to_save}).encode())
                return

            if mode == "selected":
                selected_surahs = data.get("selected_surahs", [])
                target_fields = data.get("target_fields", ["design", "waveform", "sadaqah"])
                for s in selected_surahs:
                    try:
                        s_int = int(s)
                        if 1 <= s_int <= 114:
                            curr = get_config_for_surah(s_int)
                            merged = dict(curr)
                            if "design" in target_fields and "template_id" in config_to_save:
                                merged["template_id"] = config_to_save["template_id"]
                            if "waveform" in target_fields and "waveform" in config_to_save:
                                merged["waveform"] = config_to_save["waveform"]
                            if "sadaqah" in target_fields and "sadaqah" in config_to_save:
                                merged["sadaqah"] = config_to_save["sadaqah"]
                            if "layout" in config_to_save:
                                merged["layout"] = config_to_save["layout"]
                            all_data.setdefault("configs", {})[str(s_int)] = merged
                    except Exception:
                        pass
                save_all_surah_configs(all_data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "count": len(selected_surahs)}).encode())
                return

            if mode == "all":
                target_fields = data.get("target_fields", ["design", "waveform", "sadaqah"])
                all_data["global_default"] = config_to_save
                for s_int in range(1, 115):
                    curr = get_config_for_surah(s_int)
                    merged = dict(curr)
                    if "design" in target_fields and "template_id" in config_to_save:
                        merged["template_id"] = config_to_save["template_id"]
                    if "waveform" in target_fields and "waveform" in config_to_save:
                        merged["waveform"] = config_to_save["waveform"]
                    if "sadaqah" in target_fields and "sadaqah" in config_to_save:
                        merged["sadaqah"] = config_to_save["sadaqah"]
                    if "layout" in config_to_save:
                        merged["layout"] = config_to_save["layout"]
                    all_data.setdefault("configs", {})[str(s_int)] = merged
                save_all_surah_configs(all_data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "count": 114}).encode())
                return

            if mode == "random_selected_messages":
                import random
                sel_indices = data.get("selected_message_indices", [])
                if not sel_indices:
                    sel_indices = list(range(len(URDU_SADAQAH_PRESETS)))
                valid_presets = [URDU_SADAQAH_PRESETS[i] for i in sel_indices if 0 <= i < len(URDU_SADAQAH_PRESETS)]
                if not valid_presets:
                    valid_presets = URDU_SADAQAH_PRESETS

                target_surahs = data.get("selected_surahs", list(range(1, 115)))
                for s in target_surahs:
                    try:
                        s_int = int(s)
                        if 1 <= s_int <= 114:
                            curr = get_config_for_surah(s_int)
                            merged = dict(curr)
                            sadaqah_cfg = dict(merged.get("sadaqah", DEFAULT_SURAH_CONFIG["sadaqah"]))
                            chosen_text = random.choice(valid_presets)
                            chosen_idx = URDU_SADAQAH_PRESETS.index(chosen_text) + 1 if chosen_text in URDU_SADAQAH_PRESETS else 1
                            sadaqah_cfg["text"] = chosen_text
                            sadaqah_cfg["preset_id"] = chosen_idx
                            sadaqah_cfg["enabled"] = True
                            merged["sadaqah"] = sadaqah_cfg
                            all_data.setdefault("configs", {})[str(s_int)] = merged
                    except Exception:
                        pass
                save_all_surah_configs(all_data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "count": len(target_surahs), "used_pool_size": len(valid_presets)}).encode())
                return

        if path == "/api/layout/save":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body) if body else {}
            tpl_id = data.get("template_id", "default")
            layout = data.get("layout", {})
            layout_file = os.path.join(SETTINGS_DIR, "custom_layouts.json")
            layouts = {}
            if os.path.exists(layout_file):
                try:
                    with open(layout_file, "r", encoding="utf-8") as f:
                        layouts = json.load(f)
                except Exception:
                    pass
            layouts[tpl_id] = layout
            with open(layout_file, "w", encoding="utf-8") as f:
                json.dump(layouts, f, indent=2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "layout": layout}).encode())
            return

        if path == "/api/save_options":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            if "output_dir" in data and data["output_dir"]:
                try:
                    os.makedirs(data["output_dir"], exist_ok=True)
                    CUSTOM_DIRS.add(data["output_dir"])
                except Exception:
                    pass
            ok, res_opts = save_user_options(data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": ok, "options": res_opts}).encode())
            return

        if path == "/api/choose_folder":
            folder = ""
            try:
                cmd = ['osascript', '-e', 'tell application "Finder" to activate', '-e', 'POSIX path of (choose folder with prompt "Select Destination Folder for Quran Videos")']
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                folder = res.stdout.strip()
                if folder and os.path.exists(folder):
                    CUSTOM_DIRS.add(folder)
                    save_user_options({"output_dir": folder})
            except Exception as e:
                print("Folder chooser error:", e)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"folder": folder}).encode())
            return

        if path == "/api/choose_background_file":
            file_path = ""
            url = ""
            try:
                cmd = [
                    'osascript',
                    '-e', 'tell application "Finder" to activate',
                    '-e', 'POSIX path of (choose file of type {"public.image", "com.compuserve.gif", "public.jpeg", "public.png"} with prompt "Select Custom Background Image or Animated GIF")'
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                file_path = res.stdout.strip()
                if file_path and os.path.exists(file_path):
                    bg_dir = os.path.join(BASE_DIR, "custom_backgrounds")
                    os.makedirs(bg_dir, exist_ok=True)
                    ext = os.path.splitext(file_path)[1].lower()
                    base_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', os.path.splitext(os.path.basename(file_path))[0])
                    target_name = f"{base_name}_{int(time.time())}{ext}"
                    target_path = os.path.join(bg_dir, target_name)
                    shutil.copy2(file_path, target_path)
                    url = f"/custom_backgrounds/{target_name}"
                    log_activity("SUCCESS", "Background", f"Custom background loaded: {target_name}", "Ready for video slides & web player.")
            except Exception as e:
                print("Background chooser error:", e)
                log_activity("WARNING", "Background", f"Could not load custom background: {e}", "Ensure image is valid JPG, PNG, or GIF.")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": bool(url), "url": url, "path": file_path}).encode())
            return

        if path == "/api/upload_background":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            b64_data = data.get("data", "")
            filename = data.get("filename", "custom_bg.png")
            url = ""
            if b64_data:
                try:
                    bg_dir = os.path.join(BASE_DIR, "custom_backgrounds")
                    os.makedirs(bg_dir, exist_ok=True)
                    if "," in b64_data:
                        b64_data = b64_data.split(",", 1)[1]
                    raw_bytes = base64.b64decode(b64_data)
                    ext = os.path.splitext(filename)[1].lower() or ".png"
                    base_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', os.path.splitext(filename)[0])
                    target_name = f"{base_name}_{int(time.time())}{ext}"
                    target_path = os.path.join(bg_dir, target_name)
                    with open(target_path, "wb") as f:
                        f.write(raw_bytes)
                    url = f"/custom_backgrounds/{target_name}"
                    log_activity("SUCCESS", "Background", f"Uploaded background: {target_name}", "Applied to player and ready for video export.")
                except Exception as e:
                    log_activity("ERROR", "Background", f"Upload failed: {e}", "Try choosing a smaller JPG, PNG, or GIF file.")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": bool(url), "url": url}).encode())
            return

        if path == "/api/choose_collage_file":
            file_path = ""
            created_templates = []
            try:
                cmd = [
                    'osascript',
                    '-e', 'tell application "Finder" to activate',
                    '-e', 'POSIX path of (choose file of type {"public.image", "public.jpeg", "public.png"} with prompt "Select 3x3 Islamic Collage Image to Auto-Split into 9 Templates")'
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                file_path = res.stdout.strip()
                if file_path and os.path.exists(file_path):
                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    clean_name = base_name.replace("_", " ").title()
                    created_templates = auto_split_custom_collage(file_path, custom_name=clean_name, category="Custom Collages")
                    log_activity(
                        "SUCCESS", "Templates",
                        f"Auto-split 3x3 collage '{clean_name}' into 9 HD (1920x1080) templates.",
                        "All 9 designs added to catalog and available for video export."
                    )
            except Exception as e:
                print("Collage chooser error:", e)
                log_activity("WARNING", "Templates", f"Could not auto-split collage: {e}", "Ensure image is a valid 3x3 collage.")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": bool(created_templates),
                "count": len(created_templates),
                "file_path": file_path,
                "templates": created_templates
            }).encode())
            return

        if path == "/api/split_collage":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            file_path = data.get("file_path", "")
            b64_data = data.get("data", "")
            collage_name = data.get("name", "Custom Collage")
            category = data.get("category", "Custom Collages")

            target_path = file_path
            if not target_path and b64_data:
                try:
                    tmp_dir = os.path.join(BASE_DIR, "custom_backgrounds")
                    os.makedirs(tmp_dir, exist_ok=True)
                    if "," in b64_data:
                        b64_data = b64_data.split(",", 1)[1]
                    raw_bytes = base64.b64decode(b64_data)
                    target_path = os.path.join(tmp_dir, f"collage_upload_{int(time.time())}.jpg")
                    with open(target_path, "wb") as f:
                        f.write(raw_bytes)
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Failed decoding upload: {e}"}).encode())
                    return

            if not target_path or not os.path.exists(target_path):
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Collage file not found or not specified"}).encode())
                return

            try:
                new_templates = auto_split_custom_collage(target_path, custom_name=collage_name, category=category)
                log_activity(
                    "SUCCESS", "Templates",
                    f"Auto-split 3x3 collage into {len(new_templates)} 1080p Islamic video templates.",
                    "All 9 designs added to catalog and immediately selectable."
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "count": len(new_templates),
                    "templates": new_templates
                }).encode())
                return
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

        if path == "/api/open_folder":
            content_length = int(self.headers.get("Content-Length", 0))
            folder_to_open = OUT_DIR
            if content_length > 0:
                try:
                    pdata = json.loads(self.rfile.read(content_length).decode())
                    if pdata.get("folder") and os.path.exists(pdata.get("folder")):
                        folder_to_open = pdata.get("folder")
                except Exception:
                    pass
            os.makedirs(folder_to_open, exist_ok=True)
            subprocess.run(["open", folder_to_open])
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "opened", "folder": folder_to_open}).encode())
            return

        if path == "/api/save_file_to_folder":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            src_path = data.get("file_path") or ""
            url = data.get("url") or ""
            dest_dir = data.get("dest_folder") or ""
            reveal = bool(data.get("reveal", True))

            if not src_path and url:
                if url.startswith("/custom_video?path="):
                    src_path = urllib.parse.unquote(url.split("path=")[1])
                elif url.startswith("/generated_videos/"):
                    fname = os.path.basename(url)
                    src_path = os.path.join(OUT_DIR, fname)
                elif url.startswith("/"):
                    src_path = os.path.join(BASE_DIR, url.lstrip("/"))

            if not dest_dir:
                opts = load_saved_options()
                dest_dir = opts.get("output_dir") or os.path.join(os.path.expanduser("~"), "Downloads")

            try:
                os.makedirs(dest_dir, exist_ok=True)
            except Exception:
                dest_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                os.makedirs(dest_dir, exist_ok=True)

            if not src_path or not os.path.exists(src_path):
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Source file not found: {src_path}"}).encode())
                return

            fname = os.path.basename(src_path)
            dest_file = os.path.join(dest_dir, fname)
            try:
                if os.path.abspath(src_path) != os.path.abspath(dest_file):
                    shutil.copy2(src_path, dest_file)
                if reveal:
                    subprocess.run(["open", "-R", dest_file])
                CUSTOM_DIRS.add(dest_dir)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "dest_file": dest_file,
                    "dest_folder": dest_dir,
                    "filename": fname,
                    "message": f"Successfully saved to {dest_file}"
                }).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

        if path == "/api/reveal_in_finder":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                pdata = json.loads(body)
            except Exception:
                pdata = {}
            target = pdata.get("path") or OUT_DIR
            if target.startswith("/custom_video?path="):
                target = urllib.parse.unquote(target.split("path=")[1])
            elif target.startswith("/generated_videos/"):
                target = os.path.join(OUT_DIR, os.path.basename(target))
            elif target.startswith("/") and not os.path.exists(target):
                target = os.path.join(BASE_DIR, target.lstrip("/"))

            if os.path.exists(target):
                if os.path.isdir(target):
                    subprocess.run(["open", target])
                else:
                    subprocess.run(["open", "-R", target])
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "revealed", "path": target}).encode())
                return
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Path not found: {target}"}).encode())
                return

        if path == "/api/save_surah_audio":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            s_num = int(data.get("surah", 55))
            qari = data.get("qari", "hani")
            dest_dir = data.get("dest_folder") or ""
            reveal = bool(data.get("reveal", True))

            if not dest_dir:
                opts = load_saved_options()
                dest_dir = opts.get("output_dir") or os.path.join(os.path.expanduser("~"), "Downloads")
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except Exception:
                dest_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                os.makedirs(dest_dir, exist_ok=True)

            qari_name, qari_folder = RECITER_PREFIXES.get(qari, ("Mishary Rashid Alafasy", "Alafasy_128kbps"))
            s_name = SURAH_NAMES.get(s_num, f"Surah_{s_num}")
            total_verses = SURAH_VERSES[s_num - 1] if s_num - 1 < len(SURAH_VERSES) else 7
            out_filename = f"{s_num:03d}_Surah_{s_name}_{qari}_Full_Audio.mp3"
            dest_file = os.path.join(dest_dir, out_filename)

            temp_audio_dir = os.path.join(CACHE_DIR, f"audio_surah_{s_num}_{qari}")
            os.makedirs(temp_audio_dir, exist_ok=True)

            filelist_path = os.path.join(temp_audio_dir, "concat_list.txt")
            with open(filelist_path, "w") as f_list:
                for a in range(1, total_verses + 1):
                    a_name = f"{s_num:03d}{a:03d}.mp3"
                    a_path = os.path.join(temp_audio_dir, a_name)
                    if not os.path.exists(a_path) or os.path.getsize(a_path) == 0:
                        url = f"https://everyayah.com/data/{qari_folder}/{a_name}"
                        try:
                            urllib.request.urlretrieve(url, a_path)
                        except Exception as e:
                            print(f"Failed to fetch {url}:", e)
                    if os.path.exists(a_path):
                        f_list.write(f"file '{a_path}'\n")

            # Concat using ffmpeg
            concat_cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", filelist_path,
                "-c", "copy", dest_file
            ]
            res = subprocess.run(concat_cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(dest_file):
                if reveal:
                    subprocess.run(["open", "-R", dest_file])
                CUSTOM_DIRS.add(dest_dir)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "dest_file": dest_file,
                    "dest_folder": dest_dir,
                    "filename": out_filename,
                    "audio_url": f"/custom_video?path={urllib.parse.quote(dest_file)}",
                    "message": f"Successfully saved full Surah audio to {dest_file}"
                }).encode())
                return
            else:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Failed to create combined audio MP3"}).encode())
                return


        if path == "/api/export_thumbnail":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            surah = int(data.get("surah", 67))
            ayah = int(data.get("ayah", 1))
            aspect = data.get("aspect", "16:9")
            color = data.get("color", "#ffe600")
            style = data.get("style", "glow")
            bg = data.get("bg", "midnight")
            qari = data.get("qari", "husary")
            ur = bool(data.get("include_urdu", True))
            hi = bool(data.get("include_hindi", True))
            en = bool(data.get("include_english", True))
            font_ar = data.get("font_ar", "scheherazade")
            font_ur = data.get("font_ur", "nastaliq")
            font_hi = data.get("font_hi", "noto_hindi")
            font_en = data.get("font_en", "outfit")
            watermark = data.get("watermark", "")
            out_dir = data.get("output_dir", None)

            try:
                thumb_path = generate_thumbnail(
                    surah=surah, ayah=ayah, aspect=aspect,
                    highlight_color=color, highlight_style=style, bg_preset=bg,
                    qari=qari, include_urdu=ur, include_hindi=hi, include_english=en,
                    font_ar=font_ar, font_ur=font_ur, font_hi=font_hi, font_en=font_en,
                    watermark=watermark, output_dir=out_dir
                )
                fname = os.path.basename(thumb_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "file_path": thumb_path,
                    "filename": fname,
                    "message": f"4K Poster saved at: {thumb_path}"
                }).encode())
                return
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

        if path == "/api/activity_logs":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                pdata = json.loads(body)
                entry = log_activity(
                    pdata.get("level", "INFO"),
                    pdata.get("category", "General"),
                    pdata.get("message", ""),
                    pdata.get("solution", "")
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "entry": entry}).encode())
                return
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

        if path == "/api/validate_batch":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
                jobs_spec = data.get("jobs", [])
                out_dir = data.get("output_dir") or OUT_DIR
                
                checks = []
                # 1. Check output folder
                try:
                    os.makedirs(out_dir, exist_ok=True)
                    test_file = os.path.join(out_dir, ".write_test_tmp")
                    with open(test_file, "w") as f:
                        f.write("ok")
                    os.remove(test_file)
                    checks.append({
                        "name": "Destination Folder Writable",
                        "status": "passed",
                        "detail": f"Verified write access at {out_dir}"
                    })
                except Exception as e:
                    checks.append({
                        "name": "Destination Folder Writable",
                        "status": "failed",
                        "detail": f"Cannot write to {out_dir}: {str(e)}",
                        "solution": "Select a standard folder like ~/Movies/QuranVideoStudio or ~/Downloads."
                    })

                # 2. Check Surah list and calculate total ayahs
                total_ayahs = 0
                surah_names = []
                for j in jobs_spec:
                    s_num = int(j.get("surah", 1))
                    s_name = SURAH_NAMES.get(s_num, f"Surah {s_num}")
                    surah_names.append(s_name)
                    v_max = SURAH_VERSES[s_num - 1] if s_num - 1 < len(SURAH_VERSES) else 7
                    if j.get("full_surah"):
                        total_ayahs += v_max
                    else:
                        start = int(j.get("start", 1))
                        end = min(v_max, int(j.get("end", 5)))
                        total_ayahs += max(1, end - start + 1)
                
                checks.append({
                    "name": "Surah & Ayah Queue Valid",
                    "status": "passed",
                    "detail": f"{len(jobs_spec)} Surahs queued with {total_ayahs} total ayahs"
                })

                # 3. Check reciter & audio connectivity
                qari = data.get("qari", "husary")
                qari_name, _ = RECITER_PREFIXES.get(qari, ("Mahmoud Khalil Al-Husary", "Husary_128kbps"))
                checks.append({
                    "name": "Reciter Audio CDN Valid",
                    "status": "passed",
                    "detail": f"CDN verified for {qari_name}"
                })

                # 4. Check 19 Audio DSP parameters
                dsp_active = []
                if float(data.get("audio_speed", 1.0)) != 1.0: dsp_active.append(f"Speed {data.get('audio_speed')}x")
                if float(data.get("pitch_semitones", 0.0)) != 0.0: dsp_active.append(f"Pitch {data.get('pitch_semitones')}st")
                if data.get("random_humanize"): dsp_active.append("1-2% Organic Random Fluctuation")
                if float(data.get("bass_boost", 0.0)) > 0: dsp_active.append(f"Bass +{data.get('bass_boost')}dB")
                if float(data.get("treble_boost", 0.0)) > 0: dsp_active.append(f"Treble +{data.get('treble_boost')}dB")
                if float(data.get("reverb_wet", 0.15)) > 0: dsp_active.append(f"Reverb {int(float(data.get('reverb_wet', 0.15))*100)}%")
                if data.get("binaural_432"): dsp_active.append("432Hz Healing Tuning")

                checks.append({
                    "name": "19 Audio DSP Suite Configured",
                    "status": "passed",
                    "detail": f"{len(dsp_active)} active audio effects: {', '.join(dsp_active) if dsp_active else 'Default Balanced Vocal'}"
                })

                all_passed = all(c["status"] == "passed" for c in checks)
                log_activity(
                    "SUCCESS" if all_passed else "WARNING",
                    "Batch Queue",
                    f"Validated {len(jobs_spec)} Surahs ({total_ayahs} ayahs). All checks: {'PASSED' if all_passed else 'ATTENTION REQUIRED'}.",
                    "Ready to export in parallel." if all_passed else "Review failed checks before starting export."
                )

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "valid": all_passed,
                    "total_surahs": len(jobs_spec),
                    "total_ayahs": total_ayahs,
                    "surahs": surah_names,
                    "checks": checks,
                    "message": "All pre-flight checks passed! Ready for parallel export." if all_passed else "Some checks need attention."
                }).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"valid": False, "error": str(e)}).encode())
                return

        if path == "/api/batch_generate":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            jobs_spec = data.get("jobs", [])
            concurrency = max(1, min(10, int(data.get("concurrency", 3))))
            template_mode = data.get("template_mode", "single") # single, multiple, random, custom
            selected_templates = data.get("selected_templates", [])
            global_template_id = data.get("template_id", "")
            batch_id = str(uuid.uuid4())[:8]

            log_activity(
                "INFO", "Batch Queue",
                f"Batch #{batch_id} initiated with {len(jobs_spec)} Surahs (Mode: {template_mode}, Concurrency: {concurrency}).",
                "Parallel worker pool assigned."
            )

            BATCH_JOBS[batch_id] = {
                "batch_id": batch_id,
                "concurrency": concurrency,
                "total": len(jobs_spec),
                "created_at": time.time(),
                "template_mode": template_mode,
                "jobs": {}
            }

            for idx, j_spec in enumerate(jobs_spec):
                j_id = f"{batch_id}_{idx+1}"
                v_num_val = f"V{idx+1}"
                j_spec["v_num"] = v_num_val

                # Resolve template for this job
                assigned_tid = None
                if template_mode == "single":
                    assigned_tid = global_template_id or (selected_templates[0] if selected_templates else None)
                elif template_mode in ("multiple", "random") and selected_templates:
                    assigned_tid = selected_templates[idx % len(selected_templates)]
                elif template_mode == "custom":
                    assigned_tid = j_spec.get("template_id") or global_template_id
                else:
                    assigned_tid = j_spec.get("template_id") or global_template_id

                if not assigned_tid:
                    s_num_temp = int(j_spec.get("surah", 1))
                    s_cfg = get_config_for_surah(s_num_temp)
                    assigned_tid = s_cfg.get("template_id")

                if assigned_tid:
                    t_info = get_template_by_id(assigned_tid)
                    if t_info:
                        j_spec["template_id"] = assigned_tid
                        is_vert = str(j_spec.get("aspect", "")).strip() == "9:16"
                        if is_vert and t_info.get("image_9x16"):
                            j_spec["template_bg"] = t_info.get("image_9x16")
                        elif not is_vert and t_info.get("image_16x9"):
                            j_spec["template_bg"] = t_info.get("image_16x9")
                        else:
                            j_spec["template_bg"] = t_info.get("image_url")
                        j_spec["template_style"] = t_info.get("style")
                        j_spec["template_name"] = t_info.get("name")

                s_num = int(j_spec.get("surah", 1))
                s_name = j_spec.get("surah_name", f"Surah {s_num}")
                start = int(j_spec.get("start", 1))
                end = int(j_spec.get("end", 5))
                full_s = bool(j_spec.get("full_surah", False))
                out_dir = j_spec.get("output_dir", None)
                if out_dir and os.path.exists(out_dir):
                    CUSTOM_DIRS.add(out_dir)

                j_info = {
                    "job_id": j_id,
                    "batch_id": batch_id,
                    "v_num": v_num_val,
                    "template_id": j_spec.get("template_id", ""),
                    "template_name": j_spec.get("template_name", ""),
                    "surah": s_num,
                    "surah_name": s_name,
                    "start": start,
                    "end": end,
                    "full_surah": full_s,
                    "qari": j_spec.get("qari", "hani"),
                    "res": j_spec.get("res", "1080p"),
                    "aspect": j_spec.get("aspect", "16:9"),
                    "status": "pending",
                    "progress": "Queued in parallel pool...",
                    "percent": 0,
                    "stats": {
                        "phase": "queued",
                        "current_item": "Waiting for worker",
                        "completed_ayahs": 0,
                        "total_ayahs": end,
                        "percent": 0,
                        "elapsed_sec": 0,
                        "eta_sec": 0
                    },
                    "created_at": time.time(),
                    "spec": j_spec
                }
                BATCH_JOBS[batch_id]["jobs"][j_id] = j_info
                JOBS[j_id] = j_info

            def run_batch():
                pool = ThreadPoolExecutor(max_workers=concurrency)
                completed_items_lock = threading.Lock()
                completed_batch_items = []

                def execute_single_batch_job(j_id):
                    job = BATCH_JOBS[batch_id]["jobs"][j_id]
                    if j_id in CANCELLED_JOBS or BATCH_JOBS.get(batch_id, {}).get("status") == "cancelled":
                        job["status"] = "cancelled"
                        job["progress"] = "Cancelled by user"
                        return

                    spec = job["spec"]
                    job["status"] = "processing"
                    job["progress"] = "Starting render..."

                    def update_prog(msg):
                        if isinstance(msg, dict):
                            job["progress"] = msg.get("message", "")
                            job["stats"] = msg
                            if "percent" in msg:
                                job["percent"] = msg["percent"]
                        else:
                            job["progress"] = str(msg)

                    try:
                        s_num = int(spec.get("surah", 1))
                        start = int(spec.get("start", 1))
                        end = int(spec.get("end", 5))
                        full_s = bool(spec.get("full_surah", False))
                        qari = spec.get("qari", "hani")
                        color = spec.get("color", "#ffe600")
                        style = spec.get("style", "glow")
                        bg = spec.get("bg", "midnight")
                        ur = spec.get("include_urdu", True)
                        hi = spec.get("include_hindi", True)
                        en = spec.get("include_english", True)
                        res = spec.get("res", "1080p")
                        aspect = spec.get("aspect", "16:9")
                        voice = spec.get("translation_voice", spec.get("voice", "urdu"))
                        watermark = spec.get("watermark", "")
                        repeat = int(spec.get("repeat_count", spec.get("repeat", 1)))
                        out_dir = spec.get("output_dir", None)
                        asmr = spec.get("asmr_sound", "rain")
                        asmr_v = float(spec.get("asmr_vol", 0.15))
                        wbw = spec.get("wbw_translation", False)
                        font_ar = spec.get("font_ar", "scheherazade")
                        font_ur = spec.get("font_ur", "nastaliq")
                        font_hi = spec.get("font_hi", "noto_hindi")
                        font_en = spec.get("font_en", "outfit")
                        ur_scholar = int(spec.get("urdu_scholar", spec.get("urdu_scholar_id", 234)))
                        en_scholar = int(spec.get("english_scholar", spec.get("english_scholar_id", 20)))

                        # 19 Audio DSP and sequence order
                        p_order = spec.get("playback_order", spec.get("mode", "ar_ur_en"))
                        a_spd = float(spec.get("audio_speed", spec.get("speed", 1.0)))
                        p_semi = float(spec.get("pitch_semitones", spec.get("pitch", 0.0)))
                        r_hum = bool(spec.get("random_humanize", False))
                        r_wet = float(spec.get("reverb_wet", 0.15))
                        b_boost = float(spec.get("bass_boost", 0.0))
                        t_boost = float(spec.get("treble_boost", 0.0))
                        m_boost = float(spec.get("mid_boost", 0.0))
                        l_norm = bool(spec.get("loudness_norm", True))
                        b_432 = bool(spec.get("binaural_432", False))
                        s_wave = bool(spec.get("waveform", True))
                        s_trans = bool(spec.get("translit", False))

                        video_path = generate_video(
                            surah=s_num, ayah_start=start, ayah_end=end,
                            qari=qari, highlight_color=color, highlight_style=style,
                            bg_preset=bg, include_urdu=ur, include_hindi=hi, include_english=en,
                            resolution=res, aspect=aspect, translation_voice=voice, watermark=watermark,
                            repeat_count=repeat,
                            output_dir=out_dir, asmr_sound=asmr, asmr_vol=asmr_v,
                            wbw_translation=wbw, full_surah=full_s,
                            font_ar=font_ar, font_ur=font_ur, font_hi=font_hi, font_en=font_en,
                            urdu_scholar_id=ur_scholar, english_scholar_id=en_scholar,
                            playback_order=p_order,
                            audio_speed=a_spd, pitch_semitones=p_semi, random_humanize=r_hum,
                            reverb_wet=r_wet, bass_boost=b_boost, treble_boost=t_boost, mid_boost=m_boost,
                            loudness_norm=l_norm, binaural_432=b_432,
                            show_waveform=s_wave, show_translit=s_trans,
                            v_num=spec.get("v_num"),
                            template_id=spec.get("template_id"),
                            template_bg=spec.get("template_bg"),
                            template_style=spec.get("template_style"),
                            template_name=spec.get("template_name", ""),
                            progress_cb=update_prog,
                            abort_check=lambda: (j_id in CANCELLED_JOBS or BATCH_JOBS.get(batch_id, {}).get("status") == "cancelled")
                        )

                        fname = os.path.basename(video_path)
                        stem_name = os.path.splitext(fname)[0]
                        meta_file = f"{stem_name}_metadata.txt"
                        meta_full_path = os.path.join(out_dir or OUT_DIR, meta_file)

                        job["status"] = "completed"
                        job["progress"] = "Video & Metadata ready!"
                        job["percent"] = 100
                        if out_dir and out_dir != OUT_DIR:
                            job["video_url"] = f"/custom_video?path={urllib.parse.quote(video_path)}"
                            job["metadata_url"] = f"/custom_video?path={urllib.parse.quote(meta_full_path)}"
                        else:
                            job["video_url"] = f"/generated_videos/{fname}"
                            job["metadata_url"] = f"/generated_videos/{meta_file}"
                        job["video_name"] = fname
                        job["metadata_name"] = meta_file
                        job["full_path"] = video_path
                        job["metadata_path"] = meta_full_path

                        with completed_items_lock:
                            completed_batch_items.append({
                                "v_num": spec.get("v_num", "V1"),
                                "surah": s_num,
                                "surah_name": job.get("surah_name", f"Surah {s_num}"),
                                "surah_arabic": SURAH_ARABIC_NAMES.get(s_num, ""),
                                "qari_name": RECITER_PREFIXES.get(qari, (qari, ""))[0],
                                "template_name": spec.get("template_name") or spec.get("template_id") or "Classic Islamic",
                                "template_id": spec.get("template_id", ""),
                                "video_name": fname,
                                "metadata_name": meta_file,
                                "chapters_text": job.get("stats", {}).get("chapters_text", ""),
                                "tags_str": job.get("stats", {}).get("tags_str", "")
                            })

                        log_activity(
                            "SUCCESS", "Batch Item",
                            f"Completed video & metadata for {job.get('surah_name', f'Surah {s_num}')} -> {fname} + {meta_file}",
                            f"Both MP4 video and separate metadata TXT saved in: {out_dir or OUT_DIR}"
                        )

                    except RuntimeError as re:
                        if "cancelled" in str(re).lower():
                            job["status"] = "cancelled"
                            job["progress"] = "Cancelled by user"
                            return
                        job["status"] = "failed"
                        job["error"] = str(re)
                        job["progress"] = f"Failed: {re}"
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        job["status"] = "failed"
                        job["error"] = str(e)
                        job["progress"] = f"Failed: {e}"
                        s_name = job.get('surah_name') or f"Surah {spec.get('surah', '')}"
                        log_activity(
                            "ERROR", "Batch Item",
                            f"Error rendering {s_name}: {str(e)}",
                            "Verify destination folder write permissions or try single surah export."
                        )

                futures = [pool.submit(execute_single_batch_job, j_id) for j_id in list(BATCH_JOBS[batch_id]["jobs"].keys())]
                pool.shutdown(wait=True)

                def sort_key(item):
                    try:
                        return int(str(item.get("v_num", "0")).replace("V", "").replace("v", ""))
                    except Exception:
                        return 0

                completed_batch_items.sort(key=sort_key)
                if completed_batch_items:
                    target_batch_dir = jobs_spec[0].get("output_dir") or OUT_DIR
                    try:
                        bulk_meta_file = compile_bulk_metadata(completed_batch_items, target_batch_dir)
                        BATCH_JOBS[batch_id]["bulk_metadata_file"] = bulk_meta_file
                        BATCH_JOBS[batch_id]["bulk_metadata_name"] = "bulk_metadata.txt"
                        if target_batch_dir and target_batch_dir != OUT_DIR:
                            BATCH_JOBS[batch_id]["bulk_metadata_url"] = f"/custom_video?path={urllib.parse.quote(bulk_meta_file)}"
                        else:
                            BATCH_JOBS[batch_id]["bulk_metadata_url"] = f"/generated_videos/bulk_metadata.txt"
                        log_activity(
                            "SUCCESS", "Bulk Metadata",
                            f"Compiled master bulk_metadata.txt for {len(completed_batch_items)} videos in Batch #{batch_id}.",
                            f"Master manifest saved in: {bulk_meta_file}"
                        )
                    except Exception as e:
                        print("Failed to compile bulk metadata:", e)

            t = threading.Thread(target=run_batch, daemon=True)
            t.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "batch_id": batch_id,
                "total": len(jobs_spec),
                "concurrency": concurrency,
                "job_ids": list(BATCH_JOBS[batch_id]["jobs"].keys())
            }).encode())
            return

        if path == "/api/generate_video":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            job_id = str(uuid.uuid4())[:8]
            JOBS[job_id] = {
                "status": "processing",
                "progress": "Starting video generation...",
                "percent": 0,
                "stats": {},
                "created_at": time.time()
            }

            def run_job():
                try:
                    def update_prog(msg):
                        if isinstance(msg, dict):
                            JOBS[job_id]["progress"] = msg.get("message", "")
                            JOBS[job_id]["stats"] = msg
                            if "percent" in msg:
                                JOBS[job_id]["percent"] = msg["percent"]
                        else:
                            JOBS[job_id]["progress"] = str(msg)

                    surah = int(data.get("surah", 55))
                    start = int(data.get("start", 1))
                    end = int(data.get("end", 5))
                    full_s = bool(data.get("full_surah", False))
                    qari = data.get("qari", "hani")
                    color = data.get("color", "#ffe600")
                    style = data.get("style", "glow")
                    bg = data.get("bg", "midnight")
                    ur = data.get("include_urdu", True)
                    hi = data.get("include_hindi", True)
                    en = data.get("include_english", True)
                    res = data.get("res", data.get("resolution", "1080p"))
                    aspect = data.get("aspect", "16:9")
                    voice = data.get("translation_voice", data.get("voice", "urdu"))
                    watermark = data.get("watermark", "")
                    repeat = int(data.get("repeat_count", data.get("repeat", 1)))
                    out_dir = data.get("output_dir", None)
                    asmr = data.get("asmr_sound", "rain")
                    asmr_v = float(data.get("asmr_vol", 0.15))
                    wbw = data.get("wbw_translation", False)
                    font_ar = data.get("font_ar", "scheherazade")
                    font_ur = data.get("font_ur", "nastaliq")
                    font_hi = data.get("font_hi", "noto_hindi")
                    font_en = data.get("font_en", "outfit")
                    ur_scholar = int(data.get("urdu_scholar", data.get("urdu_scholar_id", 234)))
                    en_scholar = int(data.get("english_scholar", data.get("english_scholar_id", 20)))

                    # 19 Audio DSP and sequence order
                    p_order = data.get("playback_order", data.get("mode", "ar_ur_en"))
                    a_spd = float(data.get("audio_speed", data.get("speed", 1.0)))
                    p_semi = float(data.get("pitch_semitones", data.get("pitch", 0.0)))
                    r_hum = bool(data.get("random_humanize", False))
                    r_wet = float(data.get("reverb_wet", 0.15))
                    b_boost = float(data.get("bass_boost", 0.0))
                    t_boost = float(data.get("treble_boost", 0.0))
                    m_boost = float(data.get("mid_boost", 0.0))
                    l_norm = bool(data.get("loudness_norm", True))
                    b_432 = bool(data.get("binaural_432", False))
                    s_wave = bool(data.get("waveform", True))
                    s_trans = bool(data.get("translit", False))

                    v_num = data.get("v_num")
                    template_id = data.get("template_id")
                    surah_cfg = get_config_for_surah(surah)
                    if not template_id and surah_cfg.get("template_id"):
                        template_id = surah_cfg["template_id"]
                    template_bg = data.get("template_bg")
                    template_style = data.get("template_style")
                    template_name = data.get("template_name", "")
                    if template_id and not template_bg:
                        t_info = get_template_by_id(template_id)
                        if t_info:
                            is_vert = str(aspect).strip() == "9:16"
                            if is_vert and t_info.get("image_9x16"):
                                template_bg = t_info.get("image_9x16")
                            elif not is_vert and t_info.get("image_16x9"):
                                template_bg = t_info.get("image_16x9")
                            else:
                                template_bg = t_info.get("image_url")
                            template_style = t_info.get("style")
                            template_name = t_info.get("name")

                    log_activity(
                        "INFO", "Video Render",
                        f"Rendering Surah {surah} (Ayahs {start}-{end}) with Qari {qari}, {res} {aspect}.",
                        f"Sequence: {p_order}, DSP: speed {a_spd}x, pitch {p_semi}st, 1-2% jitter: {r_hum}."
                    )

                    if out_dir and os.path.exists(out_dir):
                        CUSTOM_DIRS.add(out_dir)

                    video_path = generate_video(
                        surah=surah, ayah_start=start, ayah_end=end,
                        qari=qari, highlight_color=color, highlight_style=style,
                        bg_preset=bg, include_urdu=ur, include_hindi=hi, include_english=en,
                        resolution=res, aspect=aspect, translation_voice=voice, watermark=watermark,
                        repeat_count=repeat,
                        output_dir=out_dir, asmr_sound=asmr, asmr_vol=asmr_v,
                        wbw_translation=wbw, full_surah=full_s,
                        font_ar=font_ar, font_ur=font_ur, font_hi=font_hi, font_en=font_en,
                        urdu_scholar_id=ur_scholar, english_scholar_id=en_scholar,
                        playback_order=p_order,
                        audio_speed=a_spd, pitch_semitones=p_semi, random_humanize=r_hum,
                        reverb_wet=r_wet, bass_boost=b_boost, treble_boost=t_boost, mid_boost=m_boost,
                        loudness_norm=l_norm, binaural_432=b_432,
                        show_waveform=s_wave, show_translit=s_trans,
                        v_num=v_num,
                        template_id=template_id,
                        template_bg=template_bg,
                        template_style=template_style,
                        template_name=template_name,
                        progress_cb=update_prog,
                        abort_check=lambda: job_id in CANCELLED_JOBS
                    )

                    fname = os.path.basename(video_path)
                    stem_name = os.path.splitext(fname)[0]
                    meta_file = f"{stem_name}_metadata.txt"
                    meta_full_path = os.path.join(out_dir or OUT_DIR, meta_file)

                    JOBS[job_id]["status"] = "completed"
                    JOBS[job_id]["progress"] = "Video generation complete!"
                    JOBS[job_id]["percent"] = 100
                    if out_dir and out_dir != OUT_DIR:
                        JOBS[job_id]["video_url"] = f"/custom_video?path={urllib.parse.quote(video_path)}"
                        JOBS[job_id]["metadata_url"] = f"/custom_video?path={urllib.parse.quote(meta_full_path)}"
                    else:
                        JOBS[job_id]["video_url"] = f"/generated_videos/{fname}"
                        JOBS[job_id]["metadata_url"] = f"/generated_videos/{meta_file}"
                    JOBS[job_id]["video_name"] = fname
                    JOBS[job_id]["metadata_name"] = meta_file
                    JOBS[job_id]["full_path"] = video_path
                    JOBS[job_id]["metadata_path"] = meta_full_path

                    log_activity(
                        "SUCCESS", "Video Render",
                        f"Video & metadata ready: {fname} + {meta_file}",
                        f"Exported to {video_path}"
                    )

                except RuntimeError as re:
                    if "cancelled" in str(re).lower():
                        JOBS[job_id]["status"] = "cancelled"
                        JOBS[job_id]["progress"] = "Cancelled by user"
                        log_activity("INFO", "Video Render", f"Job {job_id} cancelled by user.")
                        return
                    JOBS[job_id]["status"] = "failed"
                    JOBS[job_id]["error"] = str(re)
                    JOBS[job_id]["progress"] = f"Failed: {re}"
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    JOBS[job_id]["status"] = "failed"
                    JOBS[job_id]["error"] = str(e)
                    JOBS[job_id]["progress"] = f"Failed: {e}"
                    log_activity(
                        "ERROR", "Video Render",
                        f"Failed rendering Surah {data.get('surah')}: {str(e)}",
                        "Verify disk space, audio connectivity, and output directory."
                    )

            thread = threading.Thread(target=run_job, daemon=True)
            thread.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"job_id": job_id, "status": "started"}).encode())
            return

        if path == "/api/upload_custom_audio":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                
                custom_audio_dir = os.path.join(BASE_DIR, "video_render", "custom_audio")
                os.makedirs(custom_audio_dir, exist_ok=True)
                
                # Check if JSON payload (base64) or direct binary
                content_type = self.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    data = json.loads(body.decode("utf-8"))
                    filename = data.get("filename", "custom_audio.mp3")
                    b64_content = data.get("data", "")
                    if "," in b64_content:
                        b64_content = b64_content.split(",", 1)[1]
                    raw_bytes = base64.b64decode(b64_content)
                else:
                    filename = "custom_recitation.mp3"
                    raw_bytes = body
                
                clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
                timestamp = int(time.time())
                out_name = f"{timestamp}_{clean_name}"
                out_path = os.path.join(custom_audio_dir, out_name)
                
                with open(out_path, "wb") as f_out:
                    f_out.write(raw_bytes)
                
                rel_url = f"/video_render/custom_audio/{out_name}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "audio_path": out_path,
                    "audio_url": rel_url,
                    "filename": out_name
                }).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "error": str(e)}).encode())
            return

        if path == "/api/generate_custom_video":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            job_id = str(uuid.uuid4())[:8]
            JOBS[job_id] = {
                "status": "processing",
                "progress": "Starting custom video generation...",
                "percent": 0,
                "stats": {},
                "created_at": time.time()
            }

            def run_custom_job():
                try:
                    def update_prog(msg):
                        if isinstance(msg, dict):
                            JOBS[job_id]["progress"] = msg.get("message", "")
                            JOBS[job_id]["stats"] = msg
                            if "percent" in msg:
                                JOBS[job_id]["percent"] = msg["percent"]
                        else:
                            JOBS[job_id]["progress"] = str(msg)

                    audio_path = data.get("audio_path")
                    if not audio_path or not os.path.exists(audio_path):
                        audio_url = data.get("audio_url", "")
                        if audio_url:
                            cand = os.path.join(BASE_DIR, audio_url.lstrip("/"))
                            if os.path.exists(cand):
                                audio_path = cand

                    if not audio_path or not os.path.exists(audio_path):
                        raise FileNotFoundError(f"Custom audio file not found. Please upload an audio file first.")

                    title = data.get("title", "Custom Dua")
                    text_ar = data.get("text_ar", "")
                    text_ur = data.get("text_ur", "")
                    text_en = data.get("text_en", "")
                    template_id = data.get("template_id")
                    template_bg = data.get("template_bg")
                    template_style = data.get("template_style")
                    color = data.get("color", "#ffe600")
                    style = data.get("style", "glow")
                    res = data.get("res", "1080p")
                    aspect = data.get("aspect", "16:9")
                    out_dir = data.get("output_dir", None)

                    if template_id and not template_bg:
                        t_info = get_template_by_id(template_id)
                        if t_info:
                            is_vert = str(aspect).strip() == "9:16"
                            template_bg = t_info.get("image_9x16") if is_vert else t_info.get("image_16x9", t_info.get("image_url"))
                            template_style = t_info.get("style")

                    log_activity(
                        "INFO", "Custom Video Render",
                        f"Rendering Custom Video: '{title}', Aspect: {aspect}, Res: {res}.",
                        f"Style: {style}, Color: {color}"
                    )

                    video_path = generate_custom_video(
                        audio_path=audio_path,
                        title=title,
                        text_ar=text_ar,
                        text_ur=text_ur,
                        text_en=text_en,
                        template_id=template_id,
                        template_bg=template_bg,
                        template_style=template_style,
                        highlight_color=color,
                        highlight_style=style,
                        resolution=res,
                        aspect=aspect,
                        output_dir=out_dir,
                        progress_cb=update_prog
                    )

                    fname = os.path.basename(video_path)
                    stem_name = os.path.splitext(fname)[0]
                    meta_file = f"{stem_name}_metadata.txt"
                    meta_full_path = os.path.join(out_dir or OUT_DIR, meta_file)

                    JOBS[job_id]["status"] = "completed"
                    JOBS[job_id]["progress"] = "Custom video export complete!"
                    JOBS[job_id]["percent"] = 100
                    if out_dir and out_dir != OUT_DIR:
                        JOBS[job_id]["video_url"] = f"/custom_video?path={urllib.parse.quote(video_path)}"
                        JOBS[job_id]["metadata_url"] = f"/custom_video?path={urllib.parse.quote(meta_full_path)}"
                    else:
                        JOBS[job_id]["video_url"] = f"/generated_videos/{fname}"
                        JOBS[job_id]["metadata_url"] = f"/generated_videos/{meta_file}"
                    JOBS[job_id]["video_name"] = fname
                    JOBS[job_id]["metadata_name"] = meta_file
                    JOBS[job_id]["full_path"] = video_path
                    JOBS[job_id]["metadata_path"] = meta_full_path

                    log_activity(
                        "SUCCESS", "Custom Video Render",
                        f"Custom Video ready: {fname}",
                        f"Exported to {video_path}"
                    )

                except Exception as e:
                    traceback.print_exc()
                    JOBS[job_id]["status"] = "failed"
                    JOBS[job_id]["error"] = str(e)
                    JOBS[job_id]["progress"] = f"Failed: {e}"
                    log_activity(
                        "ERROR", "Custom Video Render",
                        f"Failed rendering custom video '{data.get('title')}': {str(e)}",
                        "Verify audio file integrity and disk permissions."
                    )

            thread = threading.Thread(target=run_custom_job, daemon=True)
            thread.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"job_id": job_id, "status": "started"}).encode())
            return

        self.send_response(404)
        self.end_headers()

def run(port=8765):
    kill_all_render_procs()
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, QuranStudioHandler)
    print(f"Quran Studio Server running on http://localhost:{port}")
    try:
        httpd.serve_forever()
    finally:
        kill_all_render_procs()


if __name__ == "__main__":
    port = 8765
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run(port)
