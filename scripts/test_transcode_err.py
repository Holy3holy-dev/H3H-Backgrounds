import subprocess
from pathlib import Path

sample_path = Path("tmp/batch_hq_icons/sample_01001AE005166000.mp4")
out_mp4 = Path("tmp/batch_hq_icons/test_icon.mp4")

if not sample_path.exists():
    print("Sample doesn't exist!")
    exit(1)

print(f"Sample size: {sample_path.stat().st_size} bytes")

crop_expr = "crop=ih:ih:(iw-ih)/2:0,scale=256:256:flags=lanczos,unsharp=3:3:0.6:3:3:0.0,fps=30,format=yuv420p"

cmd = [
    "ffmpeg", "-y", "-nostdin",
    "-i", str(sample_path),
    "-t", "4.0",
    "-vf", crop_expr,
    "-c:v", "libx264",
    "-preset", "fast",
    "-profile:v", "baseline",
    "-level", "3.0",
    "-b:v", "1200k",
    "-an",
    "-movflags", "+faststart",
    str(out_mp4)
]

res = subprocess.run(cmd, capture_output=True, text=True)
print("Returncode:", res.returncode)
print("STDERR tail:")
print("\n".join(res.stderr.splitlines()[-15:]))
if out_mp4.exists():
    print(f"Output size: {out_mp4.stat().st_size} bytes")
