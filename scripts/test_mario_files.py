import json
import urllib.request
import subprocess
from pathlib import Path

test_dir = Path("tmp/test_mario")
test_dir.mkdir(parents=True, exist_ok=True)

files = [
    ("mario_odyssey_1", "https://drive.google.com/uc?export=download&id=1VOePFspJ7BBScL9v_vNpr6kC0Qx4bAV_", "https://drive.google.com/thumbnail?id=1VOePFspJ7BBScL9v_vNpr6kC0Qx4bAV_&sz=w1280"),
    ("mario_odyssey_2", "https://drive.google.com/uc?export=download&id=1MQa9RJbq1xD3PSdZhGakMg7Ha5FDniUR", "https://drive.google.com/thumbnail?id=1MQa9RJbq1xD3PSdZhGakMg7Ha5FDniUR&sz=w1280"),
    ("mario_odyssey_3", "https://drive.google.com/uc?export=download&id=1nIFJHGealY_B6hlQK70Vl9BS0IwE8TaB", "https://drive.google.com/thumbnail?id=1nIFJHGealY_B6hlQK70Vl9BS0IwE8TaB&sz=w1280"),
    ("mario_kart_1",    "https://drive.google.com/uc?export=download&id=1j06zTSWO__FvEz5ezzi5QflClru39kKV", "https://drive.google.com/thumbnail?id=1j06zTSWO__FvEz5ezzi5QflClru39kKV&sz=w1280"),
    ("mario_kart_2",    "https://drive.google.com/uc?export=download&id=1aZrWpw28vqW1shanjvbQuIrboinSLDCC", "https://drive.google.com/thumbnail?id=1aZrWpw28vqW1shanjvbQuIrboinSLDCC&sz=w1280"),
]

ua = 'Mozilla/5.0 (Nintendo Switch; ShareApplet) AppleWebKit/609.4 (KHTML, like Gecko) NF/6.0.2.22.5 NintendoBrowser/5.1.0.22474'

for name, v_url, t_url in files:
    print(f"\n==================== {name} ====================")
    v_path = test_dir / f"{name}.mp4"
    t_path = test_dir / f"{name}.jpg"

    # Download thumbnail
    try:
        req = urllib.request.Request(t_url, headers={'User-Agent': ua})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
            t_path.write_bytes(data)
            print(f"Thumb: {len(data)} bytes, Content-Type: {r.headers.get('Content-Type')}, starts with: {data[:4].hex()}")
    except Exception as e:
        print(f"Thumb ERR: {e}")

    # Download video
    try:
        req = urllib.request.Request(v_url, headers={'User-Agent': ua})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
            v_path.write_bytes(data)
            print(f"Video: {len(data)} bytes, Content-Type: {r.headers.get('Content-Type')}, starts with: {data[:16]}")
    except Exception as e:
        print(f"Video ERR: {e}")

    # FFprobe video
    if v_path.exists():
        ff = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_name,profile,pix_fmt,width,height,r_frame_rate,nb_frames,has_b_frames",
            "-show_entries", "format=duration,size,bit_rate",
            "-of", "json", str(v_path)
        ], capture_output=True, text=True)
        print("FFprobe video:", ff.stdout.strip())
