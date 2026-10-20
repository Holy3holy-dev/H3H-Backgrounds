import time
"""
SteamGridDB API v2 Client and 4IFIR Video Background Converter.
Allows searching games, fetching community-created animated heroes/grids,
and converting them to 100% 4IFIR-compliant Nintendo Switch MP4 covers.
"""

import json
import logging
import os
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class SteamGridDBClient:
    BASE_URL = "https://www.steamgriddb.com/api/v2"
    DEFAULT_API_KEY = "4200e73768d97fa592e9d9b7eed012fb"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key.strip() if api_key else self.DEFAULT_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "H3H-Studio/1.0"
        }

    def _fetch_json_with_retry(self, url: str, retries: int = 2) -> Optional[Dict[str, Any]]:
        req = urllib.request.Request(url, headers=self._get_headers())
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                if attempt == retries:
                    logger.warning("SteamGridDB request failed after %d retries: %s (%s)", retries, url, e)
                time.sleep(1)
        return None

    def search_game(self, query: str) -> List[Dict[str, Any]]:
        """Search SteamGridDB for games matching query string."""
        if not query or not query.strip():
            return []
        term = urllib.parse.quote(query.strip(), safe='')
        url = f"{self.BASE_URL}/search/autocomplete/{term}"
        data = self._fetch_json_with_retry(url)
        if data and data.get("success"):
            return data.get("data", [])
        return []

    def get_animated_heroes(self, game_id: int) -> List[Dict[str, Any]]:
        """Get animated hero artworks (wide banners) for a game."""
        url = f"{self.BASE_URL}/heroes/game/{game_id}?types=animated"
        data = self._fetch_json_with_retry(url)
        if data and data.get("success"):
            return data.get("data", [])
        return []

    def get_animated_grids(self, game_id: int) -> List[Dict[str, Any]]:
        """Get animated grid artworks (covers) for a game."""
        url = f"{self.BASE_URL}/grids/game/{game_id}?types=animated"
        data = self._fetch_json_with_retry(url)
        if data and data.get("success"):
            return data.get("data", [])
        return []

    def download_and_convert(
        self,
        art_url: str,
        output_mp4_path: Path,
        max_duration_sec: float = 20.0
    ) -> bool:
        """
        Download an animated hero/grid (WebP/WebM/GIF) and encode to 4IFIR profile:
        1280x720, 30fps, H.264 High 4.1, yuv420p, no audio, cropped/scaled to 16:9.
        """
        output_mp4_path = Path(output_mp4_path)
        output_mp4_path.parent.mkdir(parents=True, exist_ok=True)

        ext = art_url.split("?")[0].split(".")[-1].lower()
        if ext not in ["webp", "webm", "gif", "mp4", "png"]:
            ext = "webp"

        temp_base = Path(r"H:\H3H_Backgrounds\temp")
        custom_dir = str(temp_base) if temp_base.exists() else None
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", dir=custom_dir, delete=False) as tmp_in:
            tmp_in_path = Path(tmp_in.name)

        try:
            req = urllib.request.Request(art_url, headers={"User-Agent": "H3H-Studio/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with open(tmp_in_path, "wb") as f:
                        f.write(resp.read())
            except urllib.error.HTTPError as he:
                logger.warning("HTTP error downloading %s: %s", art_url, he)
                return False
            except Exception as e:
                logger.warning("Network error downloading %s: %s", art_url, e)
                return False

            if not tmp_in_path.exists() or tmp_in_path.stat().st_size < 1000:
                logger.error("Downloaded asset is empty or too small: %s", art_url)
                return False

            cmd = [
                "ffmpeg", "-y", "-i", str(tmp_in_path),
                "-t", str(max_duration_sec),
                "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30,format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
                "-crf", "20", "-maxrate", "3500k", "-bufsize", "7000k",
                "-map", "0:v:0", "-map", "0:a?", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", str(output_mp4_path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
            if res.returncode == 0 and output_mp4_path.exists() and output_mp4_path.stat().st_size > 50000:
                return True
            else:
                logger.error("FFmpeg error converting %s: %s", art_url, res.stderr[:500])
                return False
        finally:
            if tmp_in_path.exists():
                try:
                    tmp_in_path.unlink()
                except OSError:
                    pass
