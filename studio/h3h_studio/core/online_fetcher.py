"""
Online Switch Game, Homebrew & Artwork Fetcher for H3H Studio.
Searches over 7,200 titles (commercial, homebrew, source ports, translations) and retrieves boxart.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional


def is_valid_image(data: bytes) -> bool:
    if len(data) < 16:
        return False
    # JPEG
    if data.startswith(b"\xff\xd8\xff"):
        return True
    # PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    # WebP
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return True
    # BMP
    if data.startswith(b"BM"):
        return True
    return False


class OnlineFetcher:
    _cached_db: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def _load_db(cls) -> List[Dict[str, Any]]:
        if cls._cached_db is not None:
            return cls._cached_db

        db_path = Path(__file__).parent.parent / "data" / "switch_titles_db.json"
        if not db_path.exists() and hasattr(sys, "_MEIPASS"):
            db_path = Path(sys._MEIPASS) / "h3h_studio" / "data" / "switch_titles_db.json"

        if db_path.exists():
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    cls._cached_db = json.load(f)
                    return cls._cached_db
            except Exception as e:
                print(f"[-] Failed to load switch_titles_db.json: {e}")

        cls._cached_db = []
        return cls._cached_db

    @classmethod
    def get_total_titles_count(cls) -> int:
        return len(cls._load_db())

    @classmethod
    def search_switch_games(cls, query: str, category: str = "all", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search 7,200+ Switch titles, Homebrew, and Ports without artificial truncation.
        category options: 'all', 'homebrew', 'official'
        """
        db = cls._load_db()
        q = query.strip().lower()

        # Clean query tokens
        q_tokens = [re.sub(r"[^\w]", "", token) for token in q.split() if token]

        results = []
        for item in db:
            is_hb = item.get("isHomebrew", False)
            if category == "homebrew" and not is_hb:
                continue
            if category == "official" and is_hb:
                continue

            if not q_tokens:
                results.append(item)
                if limit is not None and len(results) >= limit:
                    break
                continue

            title_clean = re.sub(r"[^\w]", " ", item.get("title", "").lower())
            tid = item.get("titleId", "").lower()
            pub = item.get("publisher", "").lower()
            genre = item.get("genre", "").lower()

            # Match all tokens
            matches = True
            for tok in q_tokens:
                token_matched = (tok in title_clean or tok in tid or tok in pub or tok in genre)
                if not token_matched and len(tok) == 16 and len(tid) == 16:
                    # Base Title ID match (first 12 hex chars match e.g. base 0000 vs update 0800)
                    if tok[:12] == tid[:12]:
                        token_matched = True
                if not token_matched:
                    matches = False
                    break

            if matches:
                results.append(item)
                if limit is not None and len(results) >= limit:
                    break

        return results

    @classmethod
    def search_cover_fallback_online(cls, title: str) -> Optional[str]:
        """
        Queries DuckDuckGo / web images when no direct cover URL is available in DB.
        """
        clean_name = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
        search_query = f"{clean_name} Nintendo Switch box art cover"
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(search_query)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                matches = re.findall(r"//external-content\.duckduckgo\.com/iu/\?u=([^&\"\'\s]+)", html)
                if matches:
                    return urllib.parse.unquote(matches[0])
        except Exception as e:
            print(f"[-] Web image fallback failed: {e}")

        return None

    @classmethod
    def download_image(cls, url: Optional[str], dest_dir: Path, filename_prefix: str, fallback_title: str = "") -> Optional[Path]:
        """
        Downloads cover art image, validating that content is a real image.
        If URL fails or is empty, attempts online web image search.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{filename_prefix}_artwork.jpg"

        # List of candidate URLs to try
        candidates = []
        if url and url.startswith("http"):
            candidates.append(url)

        # GameTDB candidate if titleId is valid
        if re.match(r"^0100[0-9A-Fa-f]{12}$", filename_prefix):
            candidates.append(f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{filename_prefix}.jpg")

        for cand_url in candidates:
            try:
                req = urllib.request.Request(
                    cand_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                    if is_valid_image(data):
                        with open(dest_file, "wb") as f:
                            f.write(data)
                        return dest_file
            except Exception:
                continue

        # Try online fallback search if direct URLs failed
        if fallback_title:
            fallback_url = cls.search_cover_fallback_online(fallback_title)
            if fallback_url:
                try:
                    req = urllib.request.Request(
                        fallback_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = resp.read()
                        if is_valid_image(data):
                            with open(dest_file, "wb") as f:
                                f.write(data)
                            return dest_file
                except Exception as e:
                    print(f"[-] Fallback download failed: {e}")

        return None

    @classmethod
    def download_video_stream(cls, url: str, dest_dir: Path, filename_prefix: str) -> Optional[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{filename_prefix}_downloaded.mp4"

        # Direct MP4 URL
        if url.lower().endswith(".mp4") or url.lower().endswith(".mkv") or "github.com" in url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=20) as resp, open(dest_file, "wb") as f:
                    f.write(resp.read())
                return dest_file
            except Exception as e:
                print(f"[-] Direct download failed: {e}")

        # yt-dlp download
        yt_dlp = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
        if not yt_dlp:
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
