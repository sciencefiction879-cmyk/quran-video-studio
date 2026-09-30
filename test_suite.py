#!/usr/bin/env python3
import os
import sys
import json
import time
import urllib.request
import subprocess

BASE_DIR = "/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha"
OUT_DIR = os.path.join(BASE_DIR, "test_output")
os.makedirs(OUT_DIR, exist_ok=True)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed_tests = 0
failed_tests = 0

def log_test(name):
    print(f"\n{CYAN}{BOLD}==> TEST: {name}{RESET}")

def assert_true(cond, msg):
    global passed_tests, failed_tests
    if cond:
        print(f"  {GREEN}✔ PASS:{RESET} {msg}")
        passed_tests += 1
    else:
        print(f"  {RED}✖ FAIL:{RESET} {msg}")
        failed_tests += 1
        raise AssertionError(msg)

def run_ffprobe(fpath):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", fpath
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(res.stdout)

# -------------------------------------------------------------
# 1. API Status & Version 1.1
# -------------------------------------------------------------
log_test("1. API Status & Version 1.2 Endpoint")
try:
    req = urllib.request.urlopen("http://localhost:8765/api/status", timeout=5)
    data = json.loads(req.read().decode())
    assert_true(data.get("status") == "running", "Server reports status == running")
    assert_true(data.get("version") == "1.2", f"Server reports version == 1.2 (got {data.get('version')})")
except Exception as e:
    assert_true(False, f"API Status failed: {e}")

# -------------------------------------------------------------
# 2. 114 Surah Catalog API
# -------------------------------------------------------------
log_test("2. Full Surah Catalog API (114 Surahs)")
try:
    req = urllib.request.urlopen("http://localhost:8765/api/surahs", timeout=5)
    surahs = json.loads(req.read().decode())
    assert_true(len(surahs) == 114, f"Total 114 Surahs returned (got {len(surahs)})")
    fatihah = next(s for s in surahs if s["number"] == 1)
    rahman = next(s for s in surahs if s["number"] == 55)
    nas = next(s for s in surahs if s["number"] == 114)
    assert_true(fatihah["verses"] == 7, "Surah 1 Al-Fatihah has 7 verses")
    assert_true(rahman["verses"] == 78, "Surah 55 Ar-Rahman has 78 verses")
    assert_true(nas["verses"] == 6, "Surah 114 An-Nas has 6 verses")
except Exception as e:
    assert_true(False, f"Surah catalog test failed: {e}")

# -------------------------------------------------------------
# 3. Audio Fetch & Multi-Reciter CDN
# -------------------------------------------------------------
log_test("3. Audio Retrieval for Multiple Reciters")
try:
    reciters = ["alafasy", "sudais", "hani", "abdulbasit"]
    for rec in reciters:
        from studio_video_generator import RECITER_PREFIXES
        name, folder = RECITER_PREFIXES[rec]
        url = f"https://everyayah.com/data/{folder}/001001.mp3"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            assert_true(len(content) > 5000, f"Reciter '{name}' audio stream accessible ({len(content)} bytes)")
except Exception as e:
    assert_true(False, f"Audio retrieval failed: {e}")

# -------------------------------------------------------------
# 4. ASMR Audio Synthesis
# -------------------------------------------------------------
log_test("4. ASMR Atmospheric Audio Presets (Rain, Wind, Waves, Drone)")
try:
    from studio_video_generator import ASMR_PRESETS
    for preset_name, filter_expr in ASMR_PRESETS.items():
        if not filter_expr:
            continue
        test_wav = os.path.join(OUT_DIR, f"test_asmr_{preset_name}.wav")
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", filter_expr,
            "-t", "1.5",
            "-c:a", "pcm_s16le", test_wav
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        probe = run_ffprobe(test_wav)
        dur = float(probe["format"]["duration"])
        assert_true(dur >= 1.4, f"ASMR preset '{preset_name}' synthesizes correctly (dur: {dur:.2f}s)")
        os.remove(test_wav)
except Exception as e:
    assert_true(False, f"ASMR synthesis failed: {e}")

# -------------------------------------------------------------
# 5. Slide Rendering & Typography Engine
# -------------------------------------------------------------
log_test("5. Typography & Highlight Styles Slide Capture")
try:
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    styles_to_test = [
        ("brush", "scheherazade", "nastaliq", "#ffe600"),
        ("invert", "amiri_quran", "gulzar", "#10b981"),
        ("glow", "noto_naskh", "amiri", "#38bdf8")
    ]
    for style, font_ar, font_ur, col in styles_to_test:
        test_slide = os.path.join(OUT_DIR, f"test_slide_{style}.png")
        encoded_col = col.replace('#', '%23')
        url = f"http://localhost:8765/video_render/render_studio_slide.html?surah=108&ayah=1&mode=arabic&color={encoded_col}&style={style}&bg=midnight&ur=1&hi=1&en=1&font_ar={font_ar}&font_ur={font_ur}&font_hi=noto_hindi&font_en=outfit"
        cmd = [
            chrome_bin, "--headless", "--disable-gpu", "--hide-scrollbars",
            "--virtual-time-budget=4000", "--window-size=1280,720",
            f"--screenshot={test_slide}", url
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        assert_true(os.path.exists(test_slide) and os.path.getsize(test_slide) > 20000,
                    f"Slide captured with style='{style}', font_ar='{font_ar}', font_ur='{font_ur}' ({os.path.getsize(test_slide)} bytes)")
        os.remove(test_slide)
except Exception as e:
    assert_true(False, f"Slide rendering failed: {e}")

# -------------------------------------------------------------
# 6. Single Surah Video Generation with Custom Parameters
# -------------------------------------------------------------
log_test("6. Single Video Generation (Custom Output Folder, Highlight 'brush', ASMR 'rain', 720p)")
try:
    from studio_video_generator import generate_video
    custom_folder = os.path.join(OUT_DIR, "single_run")
    os.makedirs(custom_folder, exist_ok=True)
    
    vid_path = generate_video(
        surah=1, ayah_start=1, ayah_end=2, qari="sudais",
        highlight_color="#f59e0b", highlight_style="brush", bg_preset="midnight",
        include_urdu=True, include_hindi=True, include_english=True,
        resolution="720p", output_dir=custom_folder, asmr_sound="rain", asmr_vol=0.10,
        full_surah=False, font_ar="scheherazade", font_ur="nastaliq"
    )
    assert_true(os.path.exists(vid_path), f"Video created at: {vid_path}")
    probe = run_ffprobe(vid_path)
    v_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert_true(v_stream["codec_name"] == "h264", f"Video codec is h264")
    assert_true(v_stream["width"] == 1280 and v_stream["height"] == 720, f"Resolution is 1280x720 (720p)")
    assert_true(a_stream["codec_name"] == "aac", f"Audio codec is aac")
    assert_true(float(probe["format"]["duration"]) > 3.0, f"Duration is valid ({probe['format']['duration']}s)")
    assert_true("001_Surah_Al-Fatihah_sudais" in os.path.basename(vid_path), "Filename follows Surah number and clean name standard")
except Exception as e:
    assert_true(False, f"Single video generation failed: {e}")

# -------------------------------------------------------------
# 7. 1-Click Full Surah Video Generation
# -------------------------------------------------------------
log_test("7. 1-Click Full Surah Video Generation (Surah 108 Al-Kawthar - All 3 Ayahs)")
try:
    full_folder = os.path.join(OUT_DIR, "full_surah_run")
    os.makedirs(full_folder, exist_ok=True)
    
    full_vid_path = generate_video(
        surah=108, qari="alafasy", highlight_color="#ffe600",
        highlight_style="invert", bg_preset="twilight",
        include_urdu=True, include_hindi=False, include_english=True,
        resolution="720p", output_dir=full_folder, asmr_sound="none",
        full_surah=True
    )
    assert_true(os.path.exists(full_vid_path), f"Full Surah video created at: {full_vid_path}")
    assert_true("Full_Surah" in os.path.basename(full_vid_path), "Filename includes 'Full_Surah' identifier")
    probe = run_ffprobe(full_vid_path)
    dur = float(probe["format"]["duration"])
    assert_true(dur >= 10.0, f"Full Surah duration covers all 3 Ayahs ({dur:.1f}s)")
except Exception as e:
    assert_true(False, f"1-Click Full Surah failed: {e}")

# -------------------------------------------------------------
# 8. Batch Multi-Surah Parallel Generation & Live Telemetry
# -------------------------------------------------------------
log_test("8. Batch Multi-Surah Parallel Engine with Concurrency 2 & Live Stats")
try:
    batch_folder = os.path.join(OUT_DIR, "batch_parallel_run")
    os.makedirs(batch_folder, exist_ok=True)

    payload = {
        "concurrency": 2,
        "jobs": [
            {
                "surah": 113,
                "start": 1,
                "end": 5,
                "full_surah": True,
                "qari": "alafasy",
                "color": "#10b981",
                "style": "brush",
                "bg": "emerald",
                "include_urdu": True,
                "include_hindi": False,
                "include_english": True,
                "res": "720p",
                "output_dir": batch_folder,
                "asmr_sound": "none"
            },
            {
                "surah": 114,
                "start": 1,
                "end": 6,
                "full_surah": True,
                "qari": "alafasy",
                "color": "#ffe600",
                "style": "invert",
                "bg": "midnight",
                "include_urdu": True,
                "include_hindi": False,
                "include_english": True,
                "res": "720p",
                "output_dir": batch_folder,
                "asmr_sound": "none"
            }
        ]
    }
    
    req = urllib.request.Request(
        "http://localhost:8765/api/batch_generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        resp_data = json.loads(resp.read().decode())
        batch_id = resp_data.get("batch_id")
        assert_true(batch_id is not None, f"Batch created with ID: {batch_id}")
        assert_true(resp_data.get("concurrency") == 2, "Concurrency set to 2")

    # Poll batch status and observe live telemetry
    poll_count = 0
    max_polls = 100
    final_status = None
    telemetry_seen = False
    
    while poll_count < max_polls:
        time.sleep(2)
        poll_count += 1
        st_req = urllib.request.urlopen(f"http://localhost:8765/api/batch_status?batch_id={batch_id}")
        st_data = json.loads(st_req.read().decode())
        
        # Check telemetry
        for j_val in st_data.get("jobs", []):
            st = j_val.get("stats", {})
            if st.get("phase") in ["downloading_audio", "rendering_slide", "ayah_completed", "mixing_audio", "encoding_mp4"]:
                telemetry_seen = True
                
        print(f"    [Batch Progress] Completed: {st_data['completed']}/{st_data['total']} | Processing: {st_data.get('processing', 0)} | Pending: {st_data.get('pending', 0)}")
        if st_data["completed"] == st_data["total"]:
            final_status = st_data
            break
            
    assert_true(final_status is not None, "Batch completed all parallel jobs within timeout")
    assert_true(telemetry_seen, "Live telemetry (phase, elapsed, ETA, ayahs) was active during processing")
    assert_true(final_status["failed"] == 0, "No jobs failed in batch")
    
    for j_val in final_status["jobs"]:
        vid_p = j_val["full_path"]
        assert_true(os.path.exists(vid_p), f"Parallel batch output exists: {os.path.basename(vid_p)}")
        probe = run_ffprobe(vid_p)
        assert_true(probe["format"]["format_name"].startswith("mov,mp4"), "Valid MP4 container verified")

except Exception as e:
    assert_true(False, f"Batch parallel test failed: {e}")

# -------------------------------------------------------------
# 9. macOS Native App & DMG Bundle Integrity
# -------------------------------------------------------------
log_test("9. macOS Native App & DMG Bundle Integrity")
try:
    app_path = os.path.join(BASE_DIR, "QuranVideoStudio.app")
    plist_path = os.path.join(app_path, "Contents/Info.plist")
    bin_path = os.path.join(app_path, "Contents/MacOS/QuranVideoStudio")
    dmg_path = os.path.join(BASE_DIR, "QuranVideoStudio.dmg")
    
    assert_true(os.path.exists(app_path), "QuranVideoStudio.app bundle exists")
    assert_true(os.path.exists(bin_path) and os.access(bin_path, os.X_OK), "QuranVideoStudio native binary is executable")
    
    # Check Info.plist version
    res_v = subprocess.run(["defaults", "read", plist_path, "CFBundleShortVersionString"], capture_output=True, text=True)
    assert_true(res_v.stdout.strip() == "1.2", f"Info.plist version is 1.2 (got {res_v.stdout.strip()})")
    
    # Check DMG exists and is non-empty
    dmg_size_mb = os.path.getsize(dmg_path) / (1024 * 1024)
    assert_true(os.path.exists(dmg_path) and dmg_size_mb > 200, f"QuranVideoStudio.dmg exists and is healthy ({dmg_size_mb:.1f} MB)")
    
    # Verify DMG checksum / header integrity
    verify_cmd = subprocess.run(["hdiutil", "verify", dmg_path], capture_output=True, text=True)
    assert_true(verify_cmd.returncode == 0, "hdiutil verify on QuranVideoStudio.dmg passed with 0 exit code")

except Exception as e:
    assert_true(False, f"macOS App & DMG integrity check failed: {e}")

# -------------------------------------------------------------
# 10. Studio Options, Folder Selection & Full Audio Save Verification
# -------------------------------------------------------------
log_test("10. Studio Options, Folder Selection & Full Audio Save Verification")
try:
    # Test GET /api/options
    req = urllib.request.urlopen("http://localhost:8765/api/options", timeout=5)
    opts = json.loads(req.read().decode())
    assert_true("output_dir" in opts, "Options returns output_dir")
    assert_true("user_home" in opts, f"Options returns user_home ({opts.get('user_home')})")
    assert_true(opts.get("surah") in [55, 67, 108], f"Options has valid surah selection ({opts.get('surah')})")

    # Test POST /api/save_options
    save_payload = json.dumps({
        "surah": 67,
        "qari": "husary",
        "mode": "alternating",
        "speed": 1.0,
        "ayah": 1,
        "output_dir": os.path.join(OUT_DIR, "custom_save_dir")
    }).encode("utf-8")
    save_req = urllib.request.Request("http://localhost:8765/api/save_options", data=save_payload, headers={"Content-Type": "application/json"})
    save_resp = json.loads(urllib.request.urlopen(save_req).read().decode())
    assert_true(save_resp.get("success") is True, "POST /api/save_options returned success")
    assert_true(save_resp.get("options", {}).get("surah") == 67, "Saved surah option persisted (67)")
    assert_true(save_resp.get("options", {}).get("qari") == "husary", "Saved qari option persisted (husary)")

    # Test POST /api/save_file_to_folder
    copy_payload = json.dumps({
        "url": "/generated_videos/108_Surah_Al-Kawthar_alafasy_Full_Surah_720p.mp4",
        "dest_folder": os.path.join(OUT_DIR, "custom_save_dir"),
        "reveal": False
    }).encode("utf-8")
    copy_req = urllib.request.Request("http://localhost:8765/api/save_file_to_folder", data=copy_payload, headers={"Content-Type": "application/json"})
    copy_resp = json.loads(urllib.request.urlopen(copy_req).read().decode())
    assert_true(copy_resp.get("success") is True, "POST /api/save_file_to_folder succeeded")
    assert_true(os.path.exists(copy_resp.get("dest_file")), f"File saved in target directory ({copy_resp.get('dest_file')})")

    # Test POST /api/save_surah_audio (Full Audio MP3)
    audio_payload = json.dumps({
        "surah": 108,
        "qari": "alafasy",
        "dest_folder": os.path.join(OUT_DIR, "custom_save_dir"),
        "reveal": False
    }).encode("utf-8")
    audio_req = urllib.request.Request("http://localhost:8765/api/save_surah_audio", data=audio_payload, headers={"Content-Type": "application/json"})
    audio_resp = json.loads(urllib.request.urlopen(audio_req).read().decode())
    assert_true(audio_resp.get("success") is True, "POST /api/save_surah_audio succeeded")
    audio_file = audio_resp.get("dest_file")
    assert_true(os.path.exists(audio_file), f"Full Surah Audio MP3 exists ({audio_file})")
    audio_probe = run_ffprobe(audio_file)
    assert_true(audio_probe["format"]["format_name"] == "mp3", "Valid MP3 format verified for saved audio")
    assert_true(float(audio_probe["format"]["duration"]) > 10.0, "Full Surah audio duration verified")

except Exception as e:
    assert_true(False, f"Options & Audio Save Verification failed: {e}")

# -------------------------------------------------------------
# 11. 4K UHD Poster / Thumbnail Generation (16:9 Landscape & 9:16 Vertical)
# -------------------------------------------------------------
log_test("11. 4K UHD Poster Export (16:9 Landscape & 9:16 Vertical)")
try:
    poster_folder = os.path.join(OUT_DIR, "posters_test")
    os.makedirs(poster_folder, exist_ok=True)
    
    # 16:9 Landscape 4K
    p16_payload = json.dumps({
        "surah": 67,
        "ayah": 1,
        "aspect": "16:9",
        "style": "brush",
        "bg": "midnight",
        "color": "#ffe600",
        "watermark": "Quran Studio",
        "dest_folder": poster_folder,
        "reveal": False
    }).encode("utf-8")
    p16_req = urllib.request.Request("http://localhost:8765/api/export_thumbnail", data=p16_payload, headers={"Content-Type": "application/json"})
    p16_resp = json.loads(urllib.request.urlopen(p16_req).read().decode())
    assert_true(p16_resp.get("success") is True, "POST /api/export_thumbnail 16:9 returned success")
    p16_file = p16_resp.get("dest_file")
    assert_true(os.path.exists(p16_file), f"16:9 4K Poster file exists: {os.path.basename(p16_file)}")
    probe16 = run_ffprobe(p16_file)
    v16 = probe16["streams"][0]
    assert_true(v16["width"] == 3840 and v16["height"] == 2160, f"16:9 4K resolution is 3840x2160 (got {v16['width']}x{v16['height']})")

    # 9:16 Vertical 4K
    p9_payload = json.dumps({
        "surah": 67,
        "ayah": 1,
        "aspect": "9:16",
        "style": "invert",
        "bg": "twilight",
        "color": "#10b981",
        "watermark": "Peace Quran",
        "dest_folder": poster_folder,
        "reveal": False
    }).encode("utf-8")
    p9_req = urllib.request.Request("http://localhost:8765/api/export_thumbnail", data=p9_payload, headers={"Content-Type": "application/json"})
    p9_resp = json.loads(urllib.request.urlopen(p9_req).read().decode())
    assert_true(p9_resp.get("success") is True, "POST /api/export_thumbnail 9:16 returned success")
    p9_file = p9_resp.get("dest_file")
    assert_true(os.path.exists(p9_file), f"9:16 4K Poster file exists: {os.path.basename(p9_file)}")
    probe9 = run_ffprobe(p9_file)
    v9 = probe9["streams"][0]
    assert_true(v9["width"] == 2160 and v9["height"] == 3840, f"9:16 4K resolution is 2160x3840 (got {v9['width']}x{v9['height']})")

except Exception as e:
    assert_true(False, f"4K Poster generation failed: {e}")

# -------------------------------------------------------------
# 12. YouTube Chapter Timestamps & SRT Subtitles Generator
# -------------------------------------------------------------
log_test("12. YouTube Chapters Timestamps & SRT Subtitles API")
try:
    yt_url = "http://localhost:8765/api/youtube_chapters?surah=67&start=1&end=3&qari=husary&repeat=1&voice=urdu"
    yt_req = urllib.request.urlopen(yt_url, timeout=10)
    yt_data = json.loads(yt_req.read().decode())
    assert_true(yt_data.get("surah_name") == "Al-Mulk", f"Surah name is Al-Mulk (got {yt_data.get('surah_name')})")
    assert_true(len(yt_data.get("chapters", [])) == 3, f"3 chapters returned for Ayahs 1 to 3 (got {len(yt_data.get('chapters'))})")
    desc = yt_data.get("formatted_description", "")
    assert_true("00:00 - Ayah 1" in desc, "00:00 - Ayah 1 is in YouTube description")
    assert_true("Mahmoud Khalil Al-Husary" in desc, "Reciter Husary mentioned in description")

except Exception as e:
    assert_true(False, f"YouTube Chapters API failed: {e}")

# -------------------------------------------------------------
# 13. 9:16 Shorts/Reels Video with English Voiceover & Watermark
# -------------------------------------------------------------
log_test("13. 9:16 Shorts/TikTok Video with English Voiceover & Watermark")
try:
    from studio_video_generator import generate_video
    shorts_folder = os.path.join(OUT_DIR, "shorts_run")
    os.makedirs(shorts_folder, exist_ok=True)
    
    shorts_vid = generate_video(
        surah=108, ayah_start=1, ayah_end=1, qari="alafasy",
        highlight_color="#10b981", highlight_style="brush", bg_preset="midnight",
        include_urdu=False, include_hindi=False, include_english=True,
        resolution="720p", output_dir=shorts_folder, asmr_sound="none",
        full_surah=False, aspect="9:16", translation_voice="english",
        watermark="Peace Quran"
    )
    assert_true(os.path.exists(shorts_vid), f"9:16 Shorts video created at: {shorts_vid}")
    probe_s = run_ffprobe(shorts_vid)
    vs = next(s for s in probe_s["streams"] if s["codec_type"] == "video")
    assert_true(vs["width"] == 720 and vs["height"] == 1280, f"9:16 vertical resolution is 720x1280 (got {vs['width']}x{vs['height']})")
    
    # Check that SRT and Chapters were also auto-created alongside the video
    stem = os.path.splitext(shorts_vid)[0]
    srt_p = f"{stem}.srt"
    chp_p = f"{stem}_chapters.txt"
    assert_true(os.path.exists(srt_p), f"SRT subtitle file exists: {os.path.basename(srt_p)}")
    assert_true(os.path.exists(chp_p), f"YouTube chapters file exists: {os.path.basename(chp_p)}")

except Exception as e:
    assert_true(False, f"9:16 Shorts Video generation failed: {e}")




# -------------------------------------------------------------
# Final Summary
# -------------------------------------------------------------
print(f"\n{BOLD}======================================================{RESET}")
print(f"{BOLD}TOTAL TESTS PASSED: {GREEN}{passed_tests}{RESET}")
print(f"{BOLD}TOTAL TESTS FAILED: {RED}{failed_tests}{RESET}")
print(f"{BOLD}======================================================{RESET}")

if failed_tests > 0:
    sys.exit(1)
else:
    print(f"\n{GREEN}{BOLD}🎉 ALL FEATURES ARE VERIFIED AND 100% OPERATIONAL!{RESET}\n")
