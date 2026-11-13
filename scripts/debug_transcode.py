import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subprocess
from scripts.generate_batch_hq_icons import download_video_chunk, TMP_ICONS_DIR

test_url = "https://drive.google.com/uc?export=download&id=1RSj17SlAuso-7l3BSZEdjColjt-cgGqq"
sample_file = TMP_ICONS_DIR / "debug_sample.mp4"
out_file = TMP_ICONS_DIR / "debug_icon.mp4"

print("Downloading chunk...")
ok = download_video_chunk(test_url, sample_file, max_bytes=3500000)
print(f"Download result: {ok}, size: {sample_file.stat().st_size if sample_file.exists() else 0}")

if sample_file.exists():
    crop_expr = "crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)*0.5:(ih-oh)/2,scale=256:256:flags=lanczos,unsharp=3:3:0.6:3:3:0.0,fps=30,format=yuv420p"
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "0.5",
        "-i", str(sample_file),
        "-t", "4.0",
        "-vf", crop_expr,
        "-c:v", "libx264",
        "-preset", "fast",
        "-profile:v", "main",
        "-crf", "18",
        "-b:v", "1200k",
        "-maxrate", "1800k",
        "-bufsize", "2400k",
        "-an",
        "-movflags", "+faststart",
        str(out_file)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("Returncode:", res.returncode)
    print("Stderr tail:\n", "\n".join(res.stderr.splitlines()[-10:]))
    if out_file.exists():
        print(f"Icon created! Size: {out_file.stat().st_size} bytes")
