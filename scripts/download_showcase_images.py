import urllib.request
import json
import shutil
import subprocess
from pathlib import Path

art_dir = Path(r"C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\showcase_icons")
art_dir.mkdir(parents=True, exist_ok=True)

tmp_dir = Path("tmp/icon_showcase/downloads")
tmp_dir.mkdir(parents=True, exist_ok=True)

data = json.loads(Path("tmp/icon_showcase/candidates.json").read_text(encoding="utf-8"))

downloaded_previews = []

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

for idx, entry in enumerate(data, 1):
    gname = entry["game"]
    tid = entry["title_id"]
    candidates = entry["candidates"]
    if not candidates:
        continue
    
    top = candidates[0]
    title = top.get("title", gname)
    src_label = top.get("source_label", "Online")
    thumb_url = top.get("thumb_url") or top.get("url")
    video_url = top.get("url")
    fmt = top.get("format", "mp4")
    
    slug = "".join(c for c in gname.lower() if c.isalnum() or c == "_")[:15]
    img_name = f"{idx}_{slug}.jpg"
    dest_path = art_dir / img_name
    
    print(f"[{idx}/10] Downloading preview for {gname}: {thumb_url[:60]}...")
    
    try:
        # Download thumb
        req = urllib.request.Request(thumb_url, headers=headers)
        temp_thumb = tmp_dir / f"temp_{idx}.raw"
        with urllib.request.urlopen(req, timeout=15) as resp, open(temp_thumb, "wb") as f:
            temp_thumb.write_bytes(resp.read())
            
        # Convert whatever format (WebP/GIF/PNG/MP4 frame) to a clean square 256x256 JPG preview
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", str(temp_thumb),
            "-vf", "scale=256:256:force_original_aspect_ratio=increase,crop=256:256",
            "-vframes", "1",
            str(dest_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"    [+] Created preview image: {dest_path.name} ({dest_path.stat().st_size} bytes)")
        
        downloaded_previews.append({
            "index": idx,
            "game": gname,
            "title_id": tid,
            "title": title,
            "source_label": src_label,
            "format": fmt,
            "video_url": video_url,
            "img_path": str(dest_path).replace("\\", "/")
        })
    except Exception as e:
        print(f"    [-] Failed to process {gname}: {e}")

out_meta = Path("tmp/icon_showcase/showcase_meta.json")
out_meta.write_text(json.dumps(downloaded_previews, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[+] Successfully processed {len(downloaded_previews)} / 10 preview cards!")
