import re

harvest_path = "scripts/harvest_100_video_icons.py"
with open(harvest_path, "r", encoding="utf-8") as f:
    hc = f.read()

# Replace transcode_video_icon body
pattern = r'(def transcode_video_icon\([^\)]+\) -> bool:\s*""".*?""")(.*?)(res = subprocess\.run\(cmd_mp4)'
replacement = r'''\1
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    
    crop_expr = f"crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)*{crop_x_ratio}:(ih-oh)/2,scale=256:256:flags=lanczos,unsharp=3:3:0.6:3:3:0.0,fps={fps},format=yuv420p"
    
    cmd_mp4 = [
        "ffmpeg", "-y", "-nostdin",
        "-stream_loop", "-1",
        "-ss", str(start_sec),
        "-i", str(input_path),
        "-t", str(duration_sec),
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
        str(output_mp4)
    ]
    
    \3'''

new_hc = re.sub(pattern, replacement, hc, flags=re.DOTALL)
if new_hc != hc:
    with open(harvest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_hc)
    print("[+] harvest_100_video_icons.py transcode_video_icon successfully updated with 1.2M Lanczos+Unsharp!")
else:
    print("[-] Pattern not matched")
