import os
import glob
import json
import subprocess
import time

SRC_DIR = r"C:\Users\HL\Downloads\Telegram Desktop\recordings\recordings\covers"
OUT_DIR = r"E:\videofon\tmp\community_covers"
os.makedirs(OUT_DIR, exist_ok=True)

files = sorted(glob.glob(os.path.join(SRC_DIR, "*.mp4")))
print(f"[*] Found {len(files)} video recordings to process in {SRC_DIR}")

t0 = time.time()
processed = 0

for idx, src in enumerate(files, 1):
    fname = os.path.basename(src)
    tid = os.path.splitext(fname)[0].upper()
    dst_vid = os.path.join(OUT_DIR, f"{tid}.mp4")
    dst_thumb = os.path.join(OUT_DIR, f"{tid}.jpg")

    print(f"[{idx}/{len(files)}] Processing {tid}...")

    # Probe audio
    probe_cmd = ['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', src]
    has_audio = False
    try:
        out = subprocess.check_output(probe_cmd)
        pdata = json.loads(out)
        for s in pdata.get('streams', []):
            if s.get('codec_type') == 'audio':
                has_audio = True
                break
    except Exception as e:
        print(f"  [!] Probe error: {e}")

    # Transcode video
    cmd_vid = [
        'ffmpeg', '-y', '-i', src,
        '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2',
        '-r', '30', '-c:v', 'libx264', '-profile:v', 'main', '-level', '4.1',
        '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p',
    ]
    if has_audio:
        cmd_vid += ['-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-ac', '2']
    else:
        cmd_vid += ['-an']
    cmd_vid += ['-movflags', '+faststart', dst_vid]

    res = subprocess.run(cmd_vid, capture_output=True)
    if res.returncode != 0:
        print(f"  [!] Failed to transcode {fname}: {res.stderr.decode('utf-8', errors='replace')[:200]}")
        continue

    # Extract thumbnail
    cmd_thumb = [
        'ffmpeg', '-y', '-ss', '00:00:02', '-i', dst_vid,
        '-vframes', '1', '-q:v', '2', dst_thumb
    ]
    subprocess.run(cmd_thumb, capture_output=True)

    v_sz = os.path.getsize(dst_vid) / (1024 * 1024)
    print(f"  [+] Done {tid}: {v_sz:.1f} MB (audio: {has_audio})")
    processed += 1

elapsed = time.time() - t0
print(f"[*] Processed {processed}/{len(files)} recordings in {elapsed:.1f}s")
