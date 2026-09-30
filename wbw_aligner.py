import os, sys, json, re, urllib.request, math

# Quran.com & QDC Recitation ID Mapping
QDC_RECITATION_MAP = {
    "alafasy": 7,
    "husary": 6,
    "husary_muallim": 12,
    "husary_mujawwad": 6,
    "abdulbasit": 2,
    "abdulbasit_mujawwad": 1,
    "sudais": 3,
    "shatri": 4,
    "hani": 5,
    "minshawi": 9,
    "minshawi_mujawwad": 8,
    "shuraym": 10,
    "tablawi": 11,
    "dussary": 97,
}

LONG_VOWELS = set(["ا", "ى", "و", "ي", "آ", "أ", "إ", "ء"])
MADDAH = "ۤ"
SHADDAH = "ّ"

def calculate_phonetic_weight(word_ar):
    """
    Computes accurate relative duration weight for an Arabic word based on
    syllables, consonants, long vowels, and Tajweed markers (maddah, shaddah).
    """
    if not word_ar:
        return 1.0
    weight = len(word_ar) * 0.8
    for ch in word_ar:
        if ch in LONG_VOWELS:
            weight += 1.6
        elif ch == MADDAH:
            weight += 3.2
        elif ch == SHADDAH:
            weight += 1.4
    return max(1.0, weight)

def estimate_phonetic_timings(words_list, total_dur=None):
    """
    Fallback acoustic estimator when remote speech-alignment segments are unavailable.
    Weights each word by phonetics and long vowels rather than static intervals.
    """
    if not words_list:
        return {}
    
    weights = [calculate_phonetic_weight(w.get("text_uthmani") or w.get("arabic", "")) for w in words_list]
    total_w = sum(weights) or 1.0

    if total_dur is None or total_dur <= 0:
        # Heuristic: Average recited word is ~0.92 seconds
        total_dur = len(words_list) * 0.92

    seg_map = {}
    cur_t = 0.0
    for idx, w in enumerate(words_list):
        pos = w.get("position", idx + 1)
        w_dur = (weights[idx] / total_w) * total_dur
        seg_map[pos] = (round(cur_t, 3), round(cur_t + w_dur, 3))
        cur_t += w_dur
    return seg_map

def fetch_qari_segments(surah_num, qari, cache_dir):
    """
    Fetches millisecond-accurate speech alignment segments from Quran.com / QDC.
    """
    rec_id = QDC_RECITATION_MAP.get(qari.lower(), None)
    if not rec_id:
        return {}

    seg_cache = os.path.join(cache_dir, f"seg_rec{rec_id}_s{surah_num}.json")
    if os.path.exists(seg_cache):
        try:
            with open(seg_cache, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    timestamps_by_ayah = {}
    try:
        if rec_id == 97:
            # Yasser Ad-Dussary via QDC
            url = f"https://api.qurancdn.com/api/qdc/audio/reciters/97/audio_files?chapter={surah_num}&segments=true"
        else:
            # Standard Quran.com v4
            url = f"https://api.quran.com/api/v4/chapter_recitations/{rec_id}/{surah_num}?segments=true"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 QuranStudio/1.1"})
        res = urllib.request.urlopen(req, timeout=8)
        data = json.loads(res.read().decode("utf-8"))

        ts_list = []
        if "audio_file" in data and "timestamps" in data["audio_file"]:
            ts_list = data["audio_file"]["timestamps"]
        elif "audio_files" in data and len(data["audio_files"]) > 0:
            first_f = data["audio_files"][0]
            ts_list = first_f.get("verse_timings", []) or first_f.get("timestamps", [])

        for ts in ts_list:
            vkey = ts.get("verse_key")
            if vkey:
                timestamps_by_ayah[vkey] = ts

        if timestamps_by_ayah:
            try:
                with open(seg_cache, "w", encoding="utf-8") as f:
                    json.dump(timestamps_by_ayah, f, ensure_ascii=False)
            except Exception:
                pass
    except Exception as e:
        print(f"[WBW] Note: Could not fetch remote segments for Qari {qari} ({e}), falling back to phonetic alignment.")

    return timestamps_by_ayah

def _robust_http_get_json(url, max_retries=3, initial_delay=0.8, timeout=14):
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 QuranStudio/1.4",
                "Accept": "application/json"
            })
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = initial_delay * (2 ** attempt)
                time.sleep(sleep_time)
            else:
                raise e

def get_wbw_surah_content(surah_num, qari="alafasy", cache_dir="/tmp", urdu_scholar_id=234, english_scholar_id=20, hindi_scholar_id=122):
    """
    Loads complete chapter content with synchronized Word-By-Word (WBW)
    triplets: Arabic (Uthmani) + Urdu Meaning + English Meaning + Speech-Aligned Timestamps.
    Features multi-tier caching, lightweight queries, exponential retries, and pagination fallbacks.
    """
    import time
    surah_num = int(surah_num)
    fname = f"surah_{surah_num}_{qari}_wbw_v11.json"
    
    # 0. Multi-Tier Cache Lookup
    std_cache = os.path.join(os.path.expanduser("~"), "Library", "Caches", "QuranVideoStudio", "api_cache")
    this_dir = os.path.dirname(os.path.abspath(__file__))
    render_cache = os.path.join(this_dir, "video_render")

    candidate_caches = [
        os.path.join(cache_dir, fname) if cache_dir else None,
        os.path.join(std_cache, fname),
        os.path.join(render_cache, fname),
        os.path.join(this_dir, fname)
    ]

    for cpath in candidate_caches:
        if cpath and os.path.exists(cpath) and os.path.getsize(cpath) > 2000:
            try:
                with open(cpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and data.get("verses") and len(data["verses"]) > 0:
                        return data
            except Exception:
                pass

    # 1. Fetch Chapter Metadata with retries
    chapter_info = {}
    try:
        ch_url = f"https://api.quran.com/api/v4/chapters/{surah_num}?language=ur"
        ch_data = _robust_http_get_json(ch_url, max_retries=3, timeout=10)
        chapter_info = ch_data.get("chapter", {})
    except Exception as e:
        print(f"[WBW] Chapter metadata warning for Surah {surah_num}: {e}")
        chapter_info = {"id": surah_num, "name_simple": f"Surah {surah_num}"}

    # 2. Build lean translations set (default: 234 Urdu Jalandhry, 20 English Saheeh, 122 Hindi)
    scholar_set = {234, 20, 122}
    if urdu_scholar_id:
        try: scholar_set.add(int(urdu_scholar_id))
        except Exception: pass
    if english_scholar_id:
        try: scholar_set.add(int(english_scholar_id))
        except Exception: pass
    if hindi_scholar_id:
        try: scholar_set.add(int(hindi_scholar_id))
        except Exception: pass
    trans_str = ",".join(str(x) for x in sorted(scholar_set))

    # 3. Fetch Verses with Urdu Word-by-Word + Sentence Translations
    data_ur = None
    # Attempt 1: Fetch all verses in one query with lean translations
    ur_url = f"https://api.quran.com/api/v4/verses/by_chapter/{surah_num}?language=ur&words=true&word_fields=text_uthmani,location,translation&translations={trans_str}&fields=text_uthmani&per_page=300"
    try:
        data_ur = _robust_http_get_json(ur_url, max_retries=3, timeout=15)
    except Exception as e1:
        print(f"[WBW] Lean query failed for Surah {surah_num} ({e1}), falling back to paginated fetch...")
        # Attempt 2: Paginated fetch (50 verses per page) to bypass 503 / gateway timeouts on big chapters
        verses_acc = []
        page = 1
        while True:
            p_url = f"https://api.quran.com/api/v4/verses/by_chapter/{surah_num}?language=ur&words=true&word_fields=text_uthmani,location,translation&translations={trans_str}&fields=text_uthmani&per_page=50&page={page}"
            try:
                p_data = _robust_http_get_json(p_url, max_retries=3, timeout=12)
                p_verses = p_data.get("verses", [])
                if not p_verses:
                    break
                verses_acc.extend(p_verses)
                if len(p_verses) < 50:
                    break
                page += 1
            except Exception as e_page:
                print(f"[WBW] Pagination error at page {page}: {e_page}")
                break
        if verses_acc:
            data_ur = {"verses": verses_acc}
        else:
            # Attempt 3: Ultimate fallback without translation join
            alt_url = f"https://api.quran.com/api/v4/verses/by_chapter/{surah_num}?language=ur&words=true&word_fields=text_uthmani,location,translation&fields=text_uthmani&per_page=300"
            data_ur = _robust_http_get_json(alt_url, max_retries=3, timeout=15)

    # 4. Fetch English Word-by-Word
    data_en = {}
    try:
        en_url = f"https://api.quran.com/api/v4/verses/by_chapter/{surah_num}?language=en&words=true&word_fields=translation&per_page=300"
        data_en = _robust_http_get_json(en_url, max_retries=3, timeout=12)
    except Exception as e:
        print(f"[WBW] English WBW warning for Surah {surah_num}: {e}")

    # 5. Fetch Qari Speech-Aligned Audio Segments
    timestamps_by_ayah = fetch_qari_segments(surah_num, qari, cache_dir or render_cache)

    verses_ur = (data_ur or {}).get("verses", [])
    verses_en = (data_en or {}).get("verses", [])

    combined_verses = []
    for idx in range(len(verses_ur)):
        v_ur = verses_ur[idx]
        v_en = verses_en[idx] if idx < len(verses_en) else {}
        vkey = v_ur.get("verse_key", f"{surah_num}:{idx + 1}")

        ts = timestamps_by_ayah.get(vkey, {})
        segments = ts.get("segments", []) or ts.get("verse_timings", [])
        valid_segs = [s for s in segments if isinstance(s, list) and len(s) >= 3]

        seg_map = {}
        if valid_segs:
            ayah_base = valid_segs[0][1]
            for s in valid_segs:
                w_pos, s_ms, e_ms = s[0], s[1], s[2]
                st = max(0.0, (s_ms - ayah_base) / 1000.0)
                et = max(st + 0.05, (e_ms - ayah_base) / 1000.0)
                seg_map[w_pos] = (round(st, 3), round(et, 3))
        else:
            raw_w_list = [w for w in v_ur.get("words", []) if w.get("char_type_name") == "word"]
            seg_map = estimate_phonetic_timings(raw_w_list)

        words_list = []
        words_u = v_ur.get("words", [])
        words_e = v_en.get("words", [])
        e_map = {w.get("position"): w for w in words_e}

        for w_u in words_u:
            if w_u.get("char_type_name") == "word":
                pos = w_u.get("position")
                timing = seg_map.get(pos, (0.0, 0.0))
                w_e = e_map.get(pos, {})
                words_list.append({
                    "position": pos,
                    "arabic": w_u.get("text_uthmani", ""),
                    "urdu": (w_u.get("translation") or {}).get("text", "").strip(),
                    "english": (w_e.get("translation") or {}).get("text", "").strip(),
                    "start": timing[0],
                    "end": timing[1]
                })

        v_ur["wbw_words"] = words_list
        combined_verses.append(v_ur)

    payload = {
        "chapter": chapter_info,
        "verses": combined_verses,
        "qari": qari,
        "version": "1.4"
    }

    # Save to both target cache and central std cache
    target_saves = set()
    if cache_dir:
        target_saves.add(os.path.join(cache_dir, fname))
    target_saves.add(os.path.join(std_cache, fname))
    target_saves.add(os.path.join(render_cache, fname))

    for s_path in target_saves:
        try:
            os.makedirs(os.path.dirname(s_path), exist_ok=True)
            with open(s_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

    return payload
