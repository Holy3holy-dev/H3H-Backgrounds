import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional

# Bundled offline database of popular Switch games with Title IDs and official boxart
KNOWN_SWITCH_TITLES: List[Dict[str, str]] = [
    {
        "titleId": "01005CA01580E000",
        "title": "Teenage Mutant Ninja Turtles: Shredder's Revenge",
        "publisher": "Dotemu",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/01005CA01580E000.jpg"
    },
    {
        "titleId": "01007EF00011E000",
        "title": "The Legend of Zelda: Breath of the Wild",
        "publisher": "Nintendo",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/01007EF00011E000.jpg"
    },
    {
        "titleId": "0100F2C0115B6000",
        "title": "The Legend of Zelda: Tears of the Kingdom",
        "publisher": "Nintendo",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/0100F2C0115B6000.jpg"
    },
    {
        "titleId": "0100000000010000",
        "title": "Super Mario Odyssey",
        "publisher": "Nintendo",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/0100000000010000.jpg"
    },
    {
        "titleId": "01008C3003A48000",
        "title": "Metroid Dread",
        "publisher": "Nintendo",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/01008C3003A48000.jpg"
    },
    {
        "titleId": "0100F8F0000A2000",
        "title": "Animal Crossing: New Horizons",
        "publisher": "Nintendo",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/0100F8F0000A2000.jpg"
    },
    {
        "titleId": "01006A800016E000",
        "title": "Super Smash Bros. Ultimate",
        "publisher": "Nintendo",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/01006A800016E000.jpg"
    },
    {
        "titleId": "0100284000C16000",
        "title": "Hollow Knight",
        "publisher": "Team Cherry",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/0100284000C16000.jpg"
    },
    {
        "titleId": "010015100B5B4000",
        "title": "Cuphead",
        "publisher": "Studio MDHR",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/010015100B5B4000.jpg"
    },
    {
        "titleId": "01004BC00B136000",
        "title": "Cyberpunk 2077 / Witcher 3: Wild Hunt Complete",
        "publisher": "CD PROJEKT RED",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/01004BC00B136000.jpg"
    },
    {
        "titleId": "0100D870045B6000",
        "title": "DOOM Eternal",
        "publisher": "Bethesda",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/0100D870045B6000.jpg"
    },
    {
        "titleId": "01002DA013484000",
        "title": "Persona 5 Royal",
        "publisher": "SEGA / ATLUS",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/01002DA013484000.jpg"
    },
    {
        "titleId": "01008C200C024000",
        "title": "Super Mario 3D World + Bowser's Fury",
        "publisher": "Nintendo",
        "artUrl": "https://raw.githubusercontent.com/h3h-backgrounds/assets/main/icons/01008C200C024000.jpg"
    }
]


class OnlineFetcher:
    @classmethod
    def search_switch_games(cls, query: str) -> List[Dict[str, str]]:
        q = query.strip().lower()
        if not q:
            return KNOWN_SWITCH_TITLES

        results = []
        for item in KNOWN_SWITCH_TITLES:
            if q in item["title"].lower() or q in item["titleId"].lower():
                results.append(item)

        # Also search H3H Catalog data
        catalog_path = Path(__file__).parent.parent.parent.parent / "catalog" / "data" / "catalog.json"
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    cat = json.load(f)
                for g in cat.get("games", []):
                    tid = g.get("titleId", "")
                    title = g.get("title", "")
                    if (q in title.lower() or q in tid.lower()) and not any(r["titleId"] == tid for r in results):
                        results.append({
                            "titleId": tid,
                            "title": title,
                            "publisher": g.get("publisher", "Nintendo Switch"),
                            "artUrl": g.get("iconUrl", "")
                        })
            except Exception:
                pass

        return results

    @classmethod
    def download_image(cls, url: str, dest_dir: Path, filename_prefix: str) -> Optional[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{filename_prefix}_artwork.jpg"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as resp, open(dest_file, "wb") as f:
                f.write(resp.read())
            return dest_file
        except Exception as e:
            print(f"[-] Failed to download image from {url}: {e}")
            return None

    @classmethod
    def download_video_stream(cls, url: str, dest_dir: Path, filename_prefix: str) -> Optional[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{filename_prefix}_downloaded.mp4"

        # Check if direct MP4 URL
        if url.lower().endswith(".mp4") or url.lower().endswith(".mkv") or "github.com" in url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=20) as resp, open(dest_file, "wb") as f:
                    f.write(resp.read())
                return dest_file
            except Exception as e:
                print(f"[-] Direct download failed: {e}")

        # Use yt-dlp to download video from YouTube / web media stream
        yt_dlp = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
        if not yt_dlp:
            # Check Python Scripts dir
            py_scripts = Path(sys.executable).parent / "Scripts" / "yt-dlp.exe"
            if py_scripts.exists():
                yt_dlp = str(py_scripts)

        if yt_dlp:
            cmd = [
                yt_dlp,
                "-f", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", str(dest_file),
                url
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                if dest_file.exists():
                    return dest_file
            except Exception as e:
                print(f"[-] yt-dlp download failed: {e}")

        return None
