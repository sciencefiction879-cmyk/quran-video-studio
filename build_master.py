import subprocess, json, os

base_dir = "/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha"
render_dir = os.path.join(base_dir, "video_render")
alafasy_dir = os.path.join(base_dir, "audio/alafasy")
urdu_dir = os.path.join(base_dir, "audio/urdu_translation")
master_audio = os.path.join(render_dir, "master_audio.wav")
timeline_txt = os.path.join(render_dir, "master_timeline.txt")
final_output = os.path.join(base_dir, "Surah_Al_Fatihah_Master_1080p.mp4")

with open(os.path.join(base_dir, "wbw_data.json")) as f:
    wbw_data = json.load(f)

def get_duration(fpath):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", fpath]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(json.loads(res.stdout)["format"]["duration"])

# 1. Generate standard 0.4s silence pause
silence_04 = os.path.join(render_dir, "silence_04.wav")
subprocess.run([
    "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
    "-t", "0.4", "-c:a", "pcm_s16le", silence_04
], check=True, capture_output=True)

audio_segments = []
slides_timeline = []

for item in wbw_data:
    ayah = item["ayah"]
    words = item["words"]
    
    # Process Arabic Audio: highpass=75, lowpass=11000, gentle studio reverb, 48kHz stereo
    raw_ar = os.path.join(alafasy_dir, f"001{ayah:03d}.mp3")
    proc_ar = os.path.join(render_dir, f"proc_ar_{ayah}.wav")
    cmd_ar = [
        "ffmpeg", "-y", "-i", raw_ar,
        "-af", "aresample=48000,aformat=channel_layouts=stereo:sample_fmts=s16,highpass=f=75,lowpass=f=11000,aecho=0.8:0.7:50|100:0.25|0.15,volume=1.05",
        proc_ar
    ]
    subprocess.run(cmd_ar, check=True, capture_output=True)
    dur_ar = get_duration(proc_ar)
    
    # Process Urdu Audio: clean vocal EQ, 48kHz stereo
    raw_ur = os.path.join(urdu_dir, f"001{ayah:03d}.mp3")
    proc_ur = os.path.join(render_dir, f"proc_ur_{ayah}.wav")
    cmd_ur = [
        "ffmpeg", "-y", "-i", raw_ur,
        "-af", "aresample=48000,aformat=channel_layouts=stereo:sample_fmts=s16,highpass=f=80,lowpass=f=12000,volume=1.0",
        proc_ur
    ]
    subprocess.run(cmd_ur, check=True, capture_output=True)
    dur_ur = get_duration(proc_ur)
    
    # Audio sequence: Arabic -> Silence(0.4s) -> Urdu -> Silence(0.4s)
    audio_segments.extend([proc_ar, silence_04, proc_ur, silence_04])
    
    # Slide timeline:
    spent_time = 0.0
    for idx in range(len(words) - 1):
        w = words[idx]
        w_dur = w["duration"]
        img = os.path.join(render_dir, f"hq_slide_{ayah}_w_{w['word_idx']}.png")
        slides_timeline.append((img, w_dur))
        spent_time += w_dur
        
    # Last word holds for remaining Arabic audio + 0.4s silence
    last_w = words[-1]
    last_dur = max(dur_ar - spent_time, 0.5) + 0.4
    img_last = os.path.join(render_dir, f"hq_slide_{ayah}_w_{last_w['word_idx']}.png")
    slides_timeline.append((img_last, round(last_dur, 3)))
    
    # Urdu slide holds for Urdu audio + 0.4s silence
    img_ur = os.path.join(render_dir, f"hq_slide_{ayah}_ur.png")
    slides_timeline.append((img_ur, round(dur_ur + 0.4, 3)))

# Concat master audio into single continuous file
audio_concat_txt = os.path.join(render_dir, "audio_concat.txt")
with open(audio_concat_txt, "w") as f:
    for a in audio_segments:
        f.write(f"file \x27{a}\x27\n")

print("Merging master continuous 48kHz audio track...")
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", audio_concat_txt,
    "-c:a", "pcm_s16le", "-ar", "48000", master_audio
], check=True, capture_output=True)

# Write master slides timeline
with open(timeline_txt, "w") as f:
    for img, dur in slides_timeline:
        f.write(f"file \x27{img}\x27\n")
        f.write(f"duration {dur}\n")
    # Concat demuxer requirement: repeat last image
    f.write(f"file \x27{slides_timeline[-1][0]}\x27\n")

print("Encoding master video in single-pass (Zero DTS errors, perfect A/V sync)...")
cmd_master = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", timeline_txt,
    "-i", master_audio,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-tune", "stillimage",
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
    "-movflags", "+faststart",
    "-shortest",
    final_output
]
subprocess.run(cmd_master, check=True)
print("MASTER VIDEO GENERATED SUCCESSFULLY AT:", final_output)
