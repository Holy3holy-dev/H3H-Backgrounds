import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from scripts.title_id_resolver import TitleIdResolver

def main():
    root = Path(r"E:\SteamLibrary\steamapps\workshop\content\431960")
    if not root.exists():
        print(f"[-] Workshop folder not found: {root}")
        return

    resolver = TitleIdResolver()
    results = []

    valid_vids = {".mp4", ".webm"}

    for d in root.iterdir():
        if not d.is_dir():
            continue
        p_json = d / "project.json"
        if not p_json.exists():
            continue

        try:
            info = json.loads(p_json.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        title = info.get("title", d.name)
        rating = info.get("contentrating", "Everyone")
        tags = info.get("tags", [])

        # Find video file
        vid_files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in valid_vids]
        if not vid_files:
            continue

        vid = vid_files[0]
        # Find preview
        preview_file = None
        for cand in ["preview.jpg", "preview.gif", "preview.png"]:
            if (d / cand).exists():
                preview_file = str(d / cand)
                break

        # Check game match
        game_match = resolver.resolve(title)

        results.append({
            "workshop_id": d.name,
            "title": title,
            "rating": rating,
            "tags": tags,
            "video_path": str(vid),
            "video_size_mb": round(vid.stat().st_size / (1024 * 1024), 1),
            "preview_path": preview_file,
            "game_match": game_match
        })

    print(f"[*] Found {len(results)} video wallpapers in Steam Workshop folder.")
    matched = [r for r in results if r["game_match"]]
    print(f"[*] {len(matched)} matched to Nintendo Switch games via TitleIdResolver:")
    for m in matched:
        print(f"  - [{m['workshop_id']}] '{m['title']}' -> {m['game_match'][1]} ({m['game_match'][0]}) [{m['video_size_mb']} MB]")

if __name__ == "__main__":
    main()
