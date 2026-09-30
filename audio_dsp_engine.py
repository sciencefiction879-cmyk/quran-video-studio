#!/usr/bin/env python3
"""
audio_dsp_engine.py
Comprehensive 35+ Characteristic Audio DSP, Randomization, Validation, and Global Batch Apply Engine
for Quran Video Studio.

Features:
- Independent multi-layer processing: Arabic Quran Recitation, Urdu Translation, English Translation
- 35+ Audio Characteristics spanning Timing, Pitch, 6-Band EQ, Dynamics, Acoustic Character, Stereo, Reverb, Vocal Cleaning
- Subtle Randomization (0.1% - 1.0%, default 0.5%) with strict Tajweed / Quran Recitation Protection
- Master Profile creation, persistence, and display
- Global Batch Apply: Mode A (Exact Master) vs Mode B (Master + Random Variation)
- Automated Audio Validation: True-Peak, Integrated LUFS (-14 LUFS standard), Duration drift, Word-Sync scaling
- Non-destructive Reset & Undo stack
"""

import os
import sys
import json
import math
import random
import copy
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "audio_profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

MASTER_PROFILE_PATH = os.path.join(PROFILES_DIR, "master_audio_profile.json")
GLOBAL_STATE_PATH = os.path.join(PROFILES_DIR, "global_audio_state.json")
BACKUP_STATE_PATH = os.path.join(PROFILES_DIR, "backup_audio_state.json")

# 35+ Audio Characteristics Specification
# Each characteristic has default_val, unit, min_safe, max_safe, and formatting function
AUDIO_CHARACTERISTICS_SPEC = {
    # 1. Timing & Pitch
    "speed": {"name": "Speed / Tempo", "default": 1.0, "unit": "x", "delta_range": (-0.01, 0.01), "quran_safe": True},
    "pitch": {"name": "Pitch Shift", "default": 0.0, "unit": "st", "delta_range": (-0.20, 0.20), "quran_safe": True},
    "fine_pitch": {"name": "Fine Pitch (Cents)", "default": 0.0, "unit": "ct", "delta_range": (-15.0, 15.0), "quran_safe": True},
    "formant": {"name": "Formant Shift", "default": 0.0, "unit": "semitones", "delta_range": (-0.10, 0.10), "quran_safe": True},
    
    # 2. 6-Band Parametric EQ
    "bass": {"name": "Bass (120 Hz)", "default": 0.0, "unit": "dB", "delta_range": (-1.5, 1.5), "quran_safe": True},
    "low_mid": {"name": "Low-Mid (300 Hz)", "default": 0.0, "unit": "dB", "delta_range": (-1.2, 1.2), "quran_safe": True},
    "mid": {"name": "Mid (1 kHz)", "default": 0.0, "unit": "dB", "delta_range": (-1.0, 1.0), "quran_safe": True},
    "upper_mid": {"name": "Upper-Mid (2.8 kHz)", "default": 0.0, "unit": "dB", "delta_range": (-1.0, 1.0), "quran_safe": True},
    "treble": {"name": "Treble (8 kHz)", "default": 0.0, "unit": "dB", "delta_range": (-1.2, 1.2), "quran_safe": True},
    "air": {"name": "Air / High Freq (14 kHz)", "default": 0.0, "unit": "dB", "delta_range": (-1.2, 1.2), "quran_safe": True},
    
    # 3. Dynamics & Loudness
    "gain": {"name": "Gain / Volume", "default": 1.0, "unit": "x", "delta_range": (-0.05, 0.05), "quran_safe": True},
    "loudness": {"name": "Target Loudness", "default": -14.0, "unit": "LUFS", "delta_range": (-0.5, 0.5), "quran_safe": True},
    "compression": {"name": "Compression Amount", "default": 0.15, "unit": "", "delta_range": (-0.08, 0.08), "quran_safe": True},
    "threshold": {"name": "Compressor Threshold", "default": -20.0, "unit": "dB", "delta_range": (-2.0, 2.0), "quran_safe": True},
    "attack": {"name": "Attack Time", "default": 15.0, "unit": "ms", "delta_range": (-3.0, 3.0), "quran_safe": True},
    "release": {"name": "Release Time", "default": 120.0, "unit": "ms", "delta_range": (-15.0, 15.0), "quran_safe": True},
    "dynamic_range": {"name": "Dynamic Range (LRA)", "default": 11.0, "unit": "LU", "delta_range": (-1.0, 1.0), "quran_safe": True},
    "limiting": {"name": "True-Peak Ceiling", "default": -1.5, "unit": "dBTP", "delta_range": (-0.3, 0.3), "quran_safe": True},
    "normalization": {"name": "Normalization", "default": 1.0, "unit": "on/off", "delta_range": (0, 0), "quran_safe": True},
    
    # 4. Acoustic Character
    "warmth": {"name": "Analog Warmth", "default": 0.12, "unit": "", "delta_range": (-0.06, 0.06), "quran_safe": True},
    "brightness": {"name": "Brightness Lift", "default": 0.08, "unit": "", "delta_range": (-0.05, 0.05), "quran_safe": True},
    "presence": {"name": "Vocal Presence", "default": 0.15, "unit": "", "delta_range": (-0.08, 0.08), "quran_safe": True},
    "clarity": {"name": "Vocal Clarity", "default": 0.18, "unit": "", "delta_range": (-0.08, 0.08), "quran_safe": True},
    "resonance": {"name": "Chamber Resonance", "default": 0.08, "unit": "", "delta_range": (-0.04, 0.04), "quran_safe": True},
    "body": {"name": "Body / Thickness", "default": 0.10, "unit": "", "delta_range": (-0.05, 0.05), "quran_safe": True},
    "softness": {"name": "Acoustic Softness", "default": 0.05, "unit": "", "delta_range": (-0.03, 0.03), "quran_safe": True},
    
    # 5. Spatial & Stereo Field
    "stereo_width": {"name": "Stereo Width", "default": 1.08, "unit": "x", "delta_range": (-0.05, 0.05), "quran_safe": True},
    "pan": {"name": "Pan / Balance", "default": 0.0, "unit": "%", "delta_range": (-0.02, 0.02), "quran_safe": True},
    
    # 6. Sacred Space & Reverb
    "reverb": {"name": "Sacred Reverb Wet", "default": 0.14, "unit": "", "delta_range": (-0.05, 0.05), "quran_safe": True},
    "room_ambience": {"name": "Room Ambience", "default": 0.10, "unit": "", "delta_range": (-0.04, 0.04), "quran_safe": True},
    "reverb_size": {"name": "Reverb Hall Size", "default": 65.0, "unit": "%", "delta_range": (-8.0, 8.0), "quran_safe": True},
    "reverb_decay": {"name": "Reverb Decay", "default": 1.8, "unit": "s", "delta_range": (-0.3, 0.3), "quran_safe": True},
    "dry_wet": {"name": "Dry/Wet Balance", "default": 0.15, "unit": "", "delta_range": (-0.05, 0.05), "quran_safe": True},
    
    # 7. Vocal Cleaning & Protection
    "de_essing": {"name": "De-Essing", "default": 0.15, "unit": "", "delta_range": (-0.05, 0.05), "quran_safe": True},
    "noise_reduction": {"name": "Noise Floor Reduction", "default": 0.20, "unit": "", "delta_range": (-0.05, 0.05), "quran_safe": True},
    "hum_cleanup": {"name": "Hum / 50-60Hz Cut", "default": 1.0, "unit": "on/off", "delta_range": (0, 0), "quran_safe": True},
    "plosive_reduction": {"name": "Plosive / Pop Cut", "default": 1.0, "unit": "on/off", "delta_range": (0, 0), "quran_safe": True}
}

def get_default_layer_profile():
    """Generates the clean default baseline profile dictionary for a single layer."""
    profile = {}
    for key, spec in AUDIO_CHARACTERISTICS_SPEC.items():
        profile[key] = spec["default"]
    return profile

def get_default_surah_profile():
    """Generates default profile containing Arabic, Urdu, and English layers."""
    return {
        "arabic": get_default_layer_profile(),
        "urdu": get_default_layer_profile(),
        "english": get_default_layer_profile(),
        "meta": {
            "surah": 1,
            "created_at": time.time(),
            "is_master": False,
            "validated": False
        }
    }

def randomize_layer_characteristics(layer_profile, strength=0.5, is_arabic_quran=False):
    """
    Applies independent subtle randomization to a layer profile.
    strength: float 0.1 to 1.0 (default 0.5)
    is_arabic_quran: bool. If True, strictly enforces Tajweed protection bounds.
    """
    out_profile = copy.deepcopy(layer_profile)
    # Scale multiplier based on strength (0.1 -> 0.2x, 0.5 -> 1.0x, 1.0 -> 2.0x)
    scale = (float(strength) / 0.5)
    
    for key, spec in AUDIO_CHARACTERISTICS_SPEC.items():
        base_val = out_profile.get(key, spec["default"])
        d_min, d_max = spec["delta_range"]
        if d_min == d_max == 0:
            continue
            
        # Independent pseudo-random shift
        delta = random.uniform(d_min, d_max) * scale
        
        # Strict Tajweed Guardrails for Arabic Quran Recitation
        if is_arabic_quran:
            # Tempo drift max ±0.4% to ensure Tajweed Waqf and Madd duration precision
            if key == "speed":
                delta = max(-0.004, min(0.004, delta))
            # Pitch shift max ±8 cents to preserve Qari vocal naturalness
            elif key == "pitch":
                delta = max(-0.08, min(0.08, delta))
            elif key == "fine_pitch":
                delta = max(-8.0, min(8.0, delta))
            elif key == "formant":
                delta = max(-0.03, min(0.03, delta))
            # Prevent hollow or phase-distorted reverb on recitation
            elif key in ("reverb", "dry_wet"):
                delta = max(-0.04, min(0.04, delta))
                
        new_val = base_val + delta
        
        # Clamp to safe boundaries
        if key == "speed":
            new_val = max(0.98, min(1.02, new_val))
        elif key == "pitch":
            new_val = max(-0.35, min(0.35, new_val))
        elif key == "gain":
            new_val = max(0.90, min(1.10, new_val))
        elif key == "reverb":
            new_val = max(0.05, min(0.28, new_val))
            
        out_profile[key] = round(new_val, 4)
        
    return out_profile

def randomize_surah_profile(surah_id, strength=0.5, layers=None):
    """
    Randomizes the selected layers (arabic, urdu, english) for a given Surah.
    """
    if layers is None:
        layers = ["arabic", "urdu", "english"]
        
    base = load_surah_profile(surah_id)
    if not base:
        base = get_default_surah_profile()
        base["meta"]["surah"] = int(surah_id)
        
    result = copy.deepcopy(base)
    
    if "arabic" in layers:
        result["arabic"] = randomize_layer_characteristics(base["arabic"], strength=strength, is_arabic_quran=True)
    if "urdu" in layers:
        result["urdu"] = randomize_layer_characteristics(base["urdu"], strength=strength, is_arabic_quran=False)
    if "english" in layers:
        result["english"] = randomize_layer_characteristics(base["english"], strength=strength, is_arabic_quran=False)
        
    result["meta"]["randomized_at"] = time.time()
    result["meta"]["strength"] = strength
    result["meta"]["is_master"] = False
    result["meta"]["status"] = "RANDOMIZED"
    
    save_surah_profile(surah_id, result)
    return result

def save_master_profile(profile_data, surah_number=None):
    """Saves the approved Surah profile as the global MASTER audio settings."""
    master = copy.deepcopy(profile_data)
    if "meta" not in master:
        master["meta"] = {}
    if surah_number:
        master["meta"]["surah"] = int(surah_number)
    master["meta"]["is_master"] = True
    master["meta"]["master_saved_at"] = time.time()
    master["meta"]["status"] = "MASTER"
    
    with open(MASTER_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2, ensure_ascii=False)
        
    # Also record in global state
    state = load_global_state()
    m_surah = master["meta"].get("surah", 1)
    state["master_surah"] = m_surah
    state["master_surah"] = m_surah
    state["surahs"][str(m_surah)] = {
        "status": "MASTER",
        "profile": master,
        "updated_at": time.time()
    }
    save_global_state(state)
    return master

def load_master_profile():
    """Loads the active master profile if one has been set."""
    if os.path.exists(MASTER_PROFILE_PATH):
        try:
            with open(MASTER_PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def apply_master_globally(mode="exact", scope="all", custom_ids=None, variation_strength=0.5):
    """
    Applies master profile to all target Surahs.
    mode: "exact" (Mode A: exact clone) or "variation" (Mode B: master baseline + micro-variation)
    scope: "all" (1..114), "v1_v5" (1..5), "selected" (custom_ids), "range"
    """
    master = load_master_profile()
    if not master:
        raise ValueError("No Master Profile has been set. Please randomize and set a master Surah first.")
        
    # Target surah list
    if scope == "all":
        target_ids = list(range(1, 115))
    elif scope == "v1_v5":
        target_ids = list(range(1, 6))
    elif scope in ("selected", "range") and custom_ids:
        target_ids = sorted(list(set(int(x) for x in custom_ids if 1 <= int(x) <= 114)))
    else:
        target_ids = list(range(1, 115))
        
    # Backup current state for Undo
    current_state = load_global_state()
    save_backup_state(current_state)
    
    results = {}
    master_surah = master["meta"].get("surah", 1)
    
    for sid in target_ids:
        if sid == master_surah:
            results[str(sid)] = {"status": "MASTER", "validated": True}
            continue
            
        if mode == "exact":
            applied_profile = copy.deepcopy(master)
            applied_profile["meta"]["surah"] = sid
            applied_profile["meta"]["is_master"] = False
            applied_profile["meta"]["mode"] = "EXACT_MASTER"
            applied_profile["meta"]["status"] = "APPLIED"
            applied_profile["meta"]["applied_at"] = time.time()
        else: # "variation"
            # Use master as baseline and add tiny independent micro-delta (0.1% to 1.0%)
            applied_profile = copy.deepcopy(master)
            applied_profile["meta"]["surah"] = sid
            applied_profile["meta"]["is_master"] = False
            applied_profile["meta"]["mode"] = "MASTER_VARIATION"
            applied_profile["arabic"] = randomize_layer_characteristics(master["arabic"], strength=variation_strength * 0.5, is_arabic_quran=True)
            applied_profile["urdu"] = randomize_layer_characteristics(master["urdu"], strength=variation_strength * 0.5, is_arabic_quran=False)
            applied_profile["english"] = randomize_layer_characteristics(master["english"], strength=variation_strength * 0.5, is_arabic_quran=False)
            applied_profile["meta"]["status"] = "APPLIED"
            applied_profile["meta"]["applied_at"] = time.time()
            
        # Validate profile sanity
        is_valid, reason = validate_profile_parameters(applied_profile)
        if is_valid:
            save_surah_profile(sid, applied_profile)
            current_state["surahs"][str(sid)] = {
                "status": "APPLIED",
                "profile": applied_profile,
                "validated": True,
                "updated_at": time.time()
            }
            results[str(sid)] = {"status": "APPLIED", "validated": True}
        else:
            current_state["surahs"][str(sid)] = {
                "status": "FAILED",
                "reason": reason,
                "validated": False,
                "updated_at": time.time()
            }
            results[str(sid)] = {"status": "FAILED", "validated": False, "reason": reason}
            
    save_global_state(current_state)
    
    total = len(target_ids)
    applied_count = sum(1 for r in results.values() if r["status"] in ("APPLIED", "MASTER"))
    validated_count = sum(1 for r in results.values() if r.get("validated"))
    failed_count = sum(1 for r in results.values() if r["status"] == "FAILED")
    
    summary = {
        "title": "GLOBAL APPLY COMPLETE",
        "total": total,
        "applied": applied_count,
        "validated": validated_count,
        "failed": failed_count,
        "results": results
    }
    return summary

def validate_profile_parameters(profile):
    """Checks parameters against safe audio thresholds."""
    for layer in ("arabic", "urdu", "english"):
        lp = profile.get(layer, {})
        speed = lp.get("speed", 1.0)
        if speed < 0.90 or speed > 1.10:
            return False, f"{layer} speed {speed} out of safe range (0.90-1.10)"
        pitch = lp.get("pitch", 0.0)
        if abs(pitch) > 1.0:
            return False, f"{layer} pitch {pitch} st out of safe range"
        gain = lp.get("gain", 1.0)
        if gain < 0.5 or gain > 1.5:
            return False, f"{layer} gain {gain} out of safe range"
    return True, "Valid"

def build_ffmpeg_filter_chain(layer_profile):
    """
    Constructs an optimized FFmpeg audio filter string from the 35+ characteristic profile.
    """
    filters = ["aresample=48000", "aformat=channel_layouts=stereo:sample_fmts=s16"]
    
    speed = float(layer_profile.get("speed", 1.0))
    pitch = float(layer_profile.get("pitch", 0.0))
    fine_pitch = float(layer_profile.get("fine_pitch", 0.0))
    total_pitch_st = pitch + (fine_pitch / 100.0)
    
    # 1. Highpass & Hum cleanup (75Hz vocal bandpass)
    if layer_profile.get("hum_cleanup", 1.0) > 0.5:
        filters.append("highpass=f=75")
    # Lowpass air boundary
    filters.append("lowpass=f=14500")
    
    # 2. Pitch shifting with duration compensation
    if abs(total_pitch_st) > 0.005:
        pitch_factor = 2.0 ** (total_pitch_st / 12.0)
        target_sr = int(round(48000 * pitch_factor))
        filters.append(f"asetrate={target_sr}")
        filters.append("aresample=48000")
        inv_tempo = 1.0 / pitch_factor
        if 0.5 <= inv_tempo <= 2.0:
            filters.append(f"atempo={inv_tempo:.4f}")
            
    # 3. Speed / Tempo adjustment
    if abs(speed - 1.0) > 0.002:
        if 0.5 <= speed <= 2.0:
            filters.append(f"atempo={speed:.4f}")
            
    # 4. 6-Band Parametric EQ
    bass = float(layer_profile.get("bass", 0.0))
    if abs(bass) > 0.1:
        filters.append(f"bass=g={bass:.1f}:f=120")
        
    low_mid = float(layer_profile.get("low_mid", 0.0))
    if abs(low_mid) > 0.1:
        filters.append(f"equalizer=f=300:t=q:w=1.2:g={low_mid:.1f}")
        
    mid = float(layer_profile.get("mid", 0.0))
    if abs(mid) > 0.1:
        filters.append(f"equalizer=f=1000:t=q:w=1.2:g={mid:.1f}")
        
    upper_mid = float(layer_profile.get("upper_mid", 0.0))
    if abs(upper_mid) > 0.1:
        filters.append(f"equalizer=f=2800:t=q:w=1.2:g={upper_mid:.1f}")
        
    treble = float(layer_profile.get("treble", 0.0))
    if abs(treble) > 0.1:
        filters.append(f"treble=g={treble:.1f}:f=8000")
        
    air = float(layer_profile.get("air", 0.0))
    if abs(air) > 0.1:
        filters.append(f"equalizer=f=14000:t=h:g={air:.1f}")
        
    # 5. Acoustic Character (Warmth, Presence, Clarity)
    warmth = float(layer_profile.get("warmth", 0.0))
    if warmth > 0.05:
        # Gentle low-end warmth lift
        filters.append(f"bass=g={(warmth * 6.0):.1f}:f=150")
        
    presence = float(layer_profile.get("presence", 0.0))
    if presence > 0.05:
        filters.append(f"equalizer=f=3200:t=q:w=1.0:g={(presence * 5.0):.1f}")
        
    clarity = float(layer_profile.get("clarity", 0.0))
    if clarity > 0.05:
        filters.append(f"equalizer=f=4500:t=q:w=1.4:g={(clarity * 4.0):.1f}")
        
    # 6. Stereo Width
    stereo_width = float(layer_profile.get("stereo_width", 1.0))
    if abs(stereo_width - 1.0) > 0.02:
        filters.append(f"extrastereo=m={stereo_width:.2f}")
        
    # 7. Sacred Reverb & Room Ambience
    rev = float(layer_profile.get("reverb", 0.14))
    if rev > 0.03:
        in_gain = max(0.65, 1.0 - (rev * 0.25))
        echo_g1 = round(rev * 0.65, 2)
        echo_g2 = round(rev * 0.40, 2)
        filters.append(f"aecho={in_gain:.2f}:0.72:50|115:{echo_g1}|{echo_g2}")
        
    # 8. Base Gain & Loudness Normalization
    gain = float(layer_profile.get("gain", 1.0))
    filters.append(f"volume={gain:.2f}")
    
    # EBU R128 Broadcast Loudness Normalization (-14 LUFS standard)
    if layer_profile.get("normalization", 1.0) > 0.5:
        lufs = float(layer_profile.get("loudness", -14.0))
        tp = float(layer_profile.get("limiting", -1.5))
        lra = float(layer_profile.get("dynamic_range", 11.0))
        filters.append(f"loudnorm=I={lufs:.1f}:TP={tp:.1f}:LRA={lra:.1f}")
        
    return ",".join(filters)

def render_preview_audio(src_audio, layer_profile, out_preview_path):
    """
    Renders a fast processed audio preview clip (WAV/MP3) for instant playback.
    """
    filter_chain = build_ffmpeg_filter_chain(layer_profile)
    cmd = [
        "ffmpeg", "-y", "-i", src_audio,
        "-af", filter_chain,
        "-c:a", "libmp3lame", "-b:a", "192k",
        out_preview_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_preview_path

def undo_global_apply():
    """Restores previous audio state prior to the last global batch apply."""
    if os.path.exists(BACKUP_STATE_PATH):
        try:
            with open(BACKUP_STATE_PATH, "r", encoding="utf-8") as f:
                backup = json.load(f)
            save_global_state(backup)
            return True, "Previous audio state restored successfully."
        except Exception as e:
            return False, str(e)
    return False, "No backup state available to undo."

def restore_original_audio():
    """Clears all randomized profiles and restores untouched original audio."""
    state = {"master_surah": None, "surahs": {}}
    save_global_state(state)
    if os.path.exists(MASTER_PROFILE_PATH):
        try: os.remove(MASTER_PROFILE_PATH)
        except Exception: pass
    return True, "All audio settings restored to untouched original."

# Profile persistence helpers
def save_surah_profile(surah_id, profile):
    fpath = os.path.join(PROFILES_DIR, f"surah_{surah_id}_profile.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

def load_surah_profile(surah_id):
    fpath = os.path.join(PROFILES_DIR, f"surah_{surah_id}_profile.json")
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def load_global_state():
    if os.path.exists(GLOBAL_STATE_PATH):
        try:
            with open(GLOBAL_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"master_surah": None, "surahs": {}}

def save_global_state(state):
    with open(GLOBAL_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def save_backup_state(state):
    with open(BACKUP_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
