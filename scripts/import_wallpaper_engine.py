"""
H3H After Dark: Wallpaper Engine Importer & Catalog Generator.
Processes Wallpaper Engine animated wallpapers (.mp4, .webm, project.json),
converts them to Nintendo Switch 720p 30fps H.264 (+faststart),
resolves the correct Switch Title ID automatically via TitleIdResolver,
and registers them into catalog/data/catalog_after_dark.json.
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))
from scripts.title_id_resolver import TitleIdResolver

FFMPEG_CMD = "ffmpeg"

def probe_video(file_path: Path) -> Optional[Dict[str, Any]]:
    try:
        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,codec_name,r_frame_rate",
            "-show_entries", "format=duration,size",
            "-of", "json", str(file_path)
        ], capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        print(f"[-] ffprobe error on {file_path.name}: {e}")
        return None

def convert_to_switch_720p(input_file: Path, output_file: Path, duration_sec: int = 25) -> bool:
    """
    Converts any video to Nintendo Switch 720p 30fps H.264 with +faststart.
    Clamps duration to max `duration_sec` for seamless looping.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_CMD, "-y",
        "-i", str(input_file),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-b:v", "2500k",
        "-maxrate", "3000k",
        "-bufsize", "5000k",
        "-an",
        "-movflags", "+faststart",
        "-t", str(duration_sec),
        str(output_file)
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_file.exists() and output_file.stat().st_size > 50000
    except subprocess.CalledProcessError as e:
        print(f"[-] FFmpeg conversion failed for {input_file.name}: {e.stderr.decode('utf-8', errors='ignore')[:300]}")
        return False

def extract_thumbnail(video_file: Path, thumb_file: Path) -> bool:
    thumb_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_CMD, "-y",
        "-ss", "2",
        "-i", str(video_file),
        "-vframes", "1",
        "-vf", "scale=640:360",
        "-f", "image2",
        str(thumb_file)
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return thumb_file.exists() and thumb_file.stat().st_size > 1000
    except Exception:
        return False

def scan_wallpaper_engine_dir(root_dir: Path) -> List[Dict[str, Any]]:
    """
    Scans a directory (e.g. Wallpaper Engine workshop content) for wallpapers.
    Reads project.json if available.
    """
    items = []
    video_exts = {".mp4", ".webm", ".mkv", ".mov"}

    # Search for project.json files or direct video files
    for p in root_dir.rglob("*"):
        if p.name.lower() == "project.json":
            try:
                pj = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                title = pj.get("title", p.parent.name)
                tags = pj.get("tags", [])
                file_rel = pj.get("file", "")
                vid_path = p.parent / file_rel if file_rel else None
                if not (vid_path and vid_path.exists()):
                    # Find any video in the directory
                    vids = [f for f in p.parent.glob("*") if f.suffix.lower() in video_exts]
                    vid_path = vids[0] if vids else None
                
                if vid_path and vid_path.exists():
                    items.append({
                        "title": title,
                        "tags": tags,
                        "video_path": vid_path,
                        "project_dir": p.parent
                    })
            except Exception as e:
                print(f"[-] Error reading {p}: {e}")
        elif p.is_file() and p.suffix.lower() in video_exts and not (p.parent / "project.json").exists():
            items.append({
                "title": p.stem.replace("_", " ").title(),
                "tags": [],
                "video_path": p,
                "project_dir": p.parent
            })
    return items

def add_to_catalog(
    catalog_path: Path,
    title_id: str,
    game_title: str,
    variant_name: str,
    video_url: str,
    preview_url: str,
    size_bytes: int,
    notes: str = ""
):
    if not catalog_path.exists():
        return
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    
    # Find or create game entry
    game = None
    for g in data.get("games", []):
        if g.get("titleId") == title_id:
            game = g
            break
            
    if not game:
        game = {
            "titleId": title_id,
            "title": game_title,
            "publisher": "After Dark Community",
            "variants": []
        }
        data["games"].append(game)

    import uuid
    var_id = f"var-ad-{uuid.uuid4().hex[:8]}"
    variant = {
        "id": var_id,
        "name": variant_name,
        "style": "After Dark (18+)",
        "version": "1.0",
        "url": video_url,
        "previewUrl": preview_url,
        "sizeBytes": size_bytes,
        "sha256": "",
        "durationSec": 20.0,
        "author": "Holy3holy-dev",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": notes
    }
    game["variants"].append(variant)

    data["totalGames"] = len(data["games"])
    data["totalVariants"] = sum(len(g.get("variants", [])) for g in data["games"])
    catalog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Added variant '{variant_name}' to game '{game_title}' ({title_id}) in catalog.")

def main():
    parser = argparse.ArgumentParser(description="H3H After Dark: Wallpaper Engine Importer")
    parser.add_argument("--source", type=str, required=True, help="Directory containing Wallpaper Engine wallpapers or videos")
    parser.add_argument("--outdir", type=str, default="tmp/after_dark_converted", help="Output directory for converted 720p MP4s")
    parser.add_argument("--catalog", type=str, default="catalog/data/catalog_after_dark.json", help="Path to catalog_after_dark.json")
    args = parser.parse_args()

    src_path = Path(args.source)
    if not src_path.exists():
        print(f"[-] Source path does not exist: {src_path}")
        return 1

    resolver = TitleIdResolver()
    items = scan_wallpaper_engine_dir(src_path)
    print(f"[*] Found {len(items)} wallpapers to process.")

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, item in enumerate(items, 1):
        title = item["title"]
        vid_path = item["video_path"]
        print(f"\n[{i}/{len(items)}] Processing: {title} ({vid_path.name})")

        # 1. Resolve Title ID
        res = resolver.resolve(title)
        if res:
            tid, game_name = res
            print(f"  -> Match found: {game_name} ({tid})")
        else:
            tid = "0000000000000000"
            game_name = "★ Коллекция After Dark (Свободный выбор)"
            print(f"  -> Universal 18+ Wallpaper (Title ID: {tid})")

        # 2. Convert to 720p 30fps H.264
        import hashlib
        slug = "".join([c if c.isalnum() else "_" for c in title.lower()])[:30]
        out_mp4 = out_dir / f"{tid}_{slug}.mp4"
        out_jpg = out_dir / f"{tid}_{slug}.jpg"

        print(f"  -> Converting to Switch 720p H.264...")
        ok = convert_to_switch_720p(vid_path, out_mp4)
        if not ok:
            print("  [-] Conversion failed!")
            continue

        extract_thumbnail(out_mp4, out_jpg)
        print(f"  [+] Converted: {out_mp4.stat().st_size // 1024} KB")

        # 3. Add to catalog
        add_to_catalog(
            catalog_path=Path(args.catalog),
            title_id=tid,
            game_title=game_name,
            variant_name=title,
            video_url=f"local:{out_mp4.name}",
            preview_url=f"local:{out_jpg.name}",
            size_bytes=out_mp4.stat().st_size,
            notes=f"Wallpaper Engine: {title}"
        )

    print("\n==================================================")
    print(f"[+] All {len(items)} items processed successfully!")
    print(f"Catalog saved to: {args.catalog}")
    print("==================================================")
    return 0

if __name__ == "__main__":
    sys.exit(main())
