import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.analyzer import VideoAnalyzer

OUTPUT_DIR = Path(r"e:\videofon\downloaded_official_backgrounds")

targets = [
    {'name': "Pokemon Let's Go Pikachu", 'titleId': '010003F003A34000', 'filename': '010003F003A34000_Pokemon_Lets_Go_Pikachu.mp4', 'query': 'Pokemon Lets Go Pikachu trailer nintendo switch', 'time_range': '*00:05-00:25'},
    {'name': 'Splatoon 3', 'titleId': '0100C2500FC20000', 'filename': '0100C2500FC20000_Splatoon_3.mp4', 'query': 'Splatoon 3 launch trailer nintendo switch', 'time_range': '*00:10-00:30'},
    {'name': 'Ori and the Blind Forest', 'titleId': '010061D00DB74000', 'filename': '010061D00DB74000_Ori_and_the_Blind_Forest.mp4', 'query': 'Ori and the Blind Forest trailer switch', 'time_range': '*00:05-00:25'},
    {'name': 'The Binding of Isaac: Repentance', 'titleId': '010021C000B6A000', 'filename': '010021C000B6A000_The_Binding_of_Isaac_Repentance.mp4', 'query': 'The Binding of Isaac Repentance trailer switch', 'time_range': '*00:05-00:25'}
]

def encode_to_4ifir(input_path: Path, output_path: Path) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
        "-crf", "20", "-maxrate", "3500k", "-bufsize", "7000k",
        "-an", str(output_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if res.returncode == 0 and output_path.exists():
        analysis = VideoAnalyzer.analyze_file(output_path)
        return analysis.is_compliant
    return False

for item in targets:
    out_file = OUTPUT_DIR / item["filename"]
    if out_file.exists() and out_file.stat().st_size > 50000:
        print(f"[SKIP] {item['name']} already exists ({out_file.stat().st_size} bytes)")
        continue

    print(f"[*] Processing {item['name']}...")
    raw_tmp = OUTPUT_DIR / f"temp_{item['titleId']}.mp4"
    if raw_tmp.exists():
        raw_tmp.unlink()

    dl_cmd = [
        "py", "-m", "yt_dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]/best[ext=mp4]/best",
        "--download-sections", item["time_range"],
        "--force-keyframes-at-cuts",
        "--no-playlist",
        "--no-warnings",
        "-o", str(raw_tmp),
        f"ytsearch1:{item['query']}"
    ]

    subprocess.run(dl_cmd, capture_output=True, text=True)
    if not raw_tmp.exists() or raw_tmp.stat().st_size < 10000:
        # Fallback without section download
        dl_fallback = [
            "py", "-m", "yt_dlp",
            "-f", "bestvideo[height<=1080][ext=mp4]/best[ext=mp4]/best",
            "--no-playlist",
            "--no-warnings",
            "-o", str(raw_tmp),
            f"ytsearch1:{item['query']}"
        ]
        subprocess.run(dl_fallback, capture_output=True, text=True)

    if raw_tmp.exists() and raw_tmp.stat().st_size > 10000:
        print(f"[+] Downloaded raw video ({raw_tmp.stat().st_size} bytes). Encoding to 4IFIR...")
        if encode_to_4ifir(raw_tmp, out_file):
            print(f"[SUCCESS] Encoded {out_file.name} ({out_file.stat().st_size} bytes)")
            raw_tmp.unlink(missing_ok=True)
        else:
            print(f"[-] Encoding failed for {item['name']}")
    else:
        print(f"[-] Download failed for {item['name']}")

print("\nDone missing batch 9.")
