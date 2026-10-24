"""
Animated Icons & Loops Fetcher for H3H Studio.
Aggregates animations from:
1. SteamGridDB (Animated Grids & Icons via API v2)
2. Steam Points Shop (Official looping MP4/WebM avatars & mini-profiles via Steam API)
3. Tenor (Game loops and cinemagraphs)
"""

import json
import re
import urllib.request
import urllib.parse
import subprocess
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

class AnimatedIconsFetcher:
    STEAMGRID_KEY = "4200e73768d97fa592e9d9b7eed012fb"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    @classmethod
    def search_steamgriddb(cls, game_name: str) -> List[Dict[str, Any]]:
        results = []
        try:
            term = urllib.parse.quote(game_name.strip(), safe='')
            auto_url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{term}"
            req = urllib.request.Request(auto_url, headers={
                "Authorization": f"Bearer {cls.STEAMGRID_KEY}",
                "User-Agent": cls.USER_AGENT
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                gdata = json.loads(resp.read().decode())
                games = gdata.get("data", [])
                if not games:
                    return []
                gid = games[0]["id"]
                matched_name = games[0].get("name", game_name)

            # 1. Animated Icons
            url_icons = f"https://www.steamgriddb.com/api/v2/icons/game/{gid}?types=animated"
            req = urllib.request.Request(url_icons, headers={
                "Authorization": f"Bearer {cls.STEAMGRID_KEY}",
                "User-Agent": cls.USER_AGENT
            })
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    idata = json.loads(resp.read().decode())
                    for item in idata.get("data", []):
                        results.append({
                            "title": f"{matched_name} (Иконка)",
                            "source": "steamgriddb",
                            "source_label": "SteamGridDB",
                            "url": item.get("url"),
                            "thumb_url": item.get("thumb") or item.get("url"),
                            "format": (item.get("mime") or "image/webp").split("/")[-1],
                            "width": item.get("width", 512),
                            "height": item.get("height", 512),
                        })
            except Exception:
                pass

            # 2. Animated Grids
            url_grids = f"https://www.steamgriddb.com/api/v2/grids/game/{gid}?types=animated"
            req = urllib.request.Request(url_grids, headers={
                "Authorization": f"Bearer {cls.STEAMGRID_KEY}",
                "User-Agent": cls.USER_AGENT
            })
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    gdata = json.loads(resp.read().decode())
                    for item in gdata.get("data", []):
                        results.append({
                            "title": f"{matched_name} (Арт {item.get('width')}x{item.get('height')})",
                            "source": "steamgriddb",
                            "source_label": "SteamGridDB",
                            "url": item.get("url"),
                            "thumb_url": item.get("thumb") or item.get("url"),
                            "format": (item.get("mime") or "image/webp").split("/")[-1],
                            "width": item.get("width", 600),
                            "height": item.get("height", 900),
                        })
            except Exception:
                pass

        except Exception as e:
            print(f"[-] SteamGridDB search error: {e}")

        return results

    @classmethod
    def search_steam_points(cls, game_name: str) -> List[Dict[str, Any]]:
        results = []
        try:
            store_url = f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(game_name)}&l=english&cc=US"
            req = urllib.request.Request(store_url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                sdata = json.loads(resp.read().decode())
                items = sdata.get("items", [])
                if not items:
                    return []
                appid = items[0]["id"]
                appname = items[0]["name"]

            points_url = f"https://api.steampowered.com/ILoyaltyRewardsService/QueryRewardItems/v1/?appids[0]={appid}&count=50"
            req = urllib.request.Request(points_url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                pdata = json.loads(resp.read().decode())
                defs = pdata.get("response", {}).get("definitions", [])
                for d in defs:
                    cdata = d.get("community_item_data", {})
                    title = cdata.get("item_title", "Steam Animated")
                    murl = cdata.get("item_movie_mp4", "") or cdata.get("item_movie_webm", "")
                    img = cdata.get("item_image_large", "") or cdata.get("item_image_small", "")
                    
                    if murl:
                        full_murl = f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{murl}"
                        full_thumb = f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{img}" if img else full_murl
                        results.append({
                            "title": f"{appname} — {title}",
                            "source": "steam_points",
                            "source_label": "Магазин Steam",
                            "url": full_murl,
                            "thumb_url": full_thumb,
                            "format": "mp4",
                            "width": 300,
                            "height": 300,
                        })
        except Exception as e:
            print(f"[-] Steam Points search error: {e}")

        return results

    @classmethod
    def search_tenor(cls, game_name: str) -> List[Dict[str, Any]]:
        results = []
        try:
            clean_term = re.sub(r"[^\w\s]", "", game_name).strip().replace(" ", "-").lower()
            url = f"https://tenor.com/search/{clean_term}-gifs"
            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                mp4s = list(set(re.findall(r"https://media\.tenor\.com/[^\s\"\'<>]+\.mp4", html)))
                gifs = list(set(re.findall(r"https://media\.tenor\.com/[^\s\"\'<>]+\.gif", html)))

                for i, m in enumerate(mp4s[:20]):
                    thumb = gifs[i] if i < len(gifs) else m
                    name_part = m.split("/")[-1].replace(".mp4", "").replace("-", " ").capitalize()
                    results.append({
                        "title": f"{game_name} — {name_part[:30]}",
                        "source": "tenor",
                        "source_label": "Tenor / Гифки",
                        "url": m,
                        "thumb_url": thumb,
                        "format": "mp4",
                        "width": 256,
                        "height": 256,
                    })
        except Exception as e:
            print(f"[-] Tenor search error: {e}")

        return results

    @classmethod
    def search_all(cls, game_name: str, source_filter: str = "all") -> List[Dict[str, Any]]:
        all_results = []
        if source_filter in ["all", "steam_points"]:
            all_results.extend(cls.search_steam_points(game_name))
        if source_filter in ["all", "steamgriddb"]:
            all_results.extend(cls.search_steamgriddb(game_name))
        if source_filter in ["all", "tenor"]:
            all_results.extend(cls.search_tenor(game_name))
        return all_results

    @classmethod
    def download_and_convert_to_mp4(
        cls,
        item: Dict[str, Any],
        dest_dir: Path,
        on_progress: Optional[Any] = None
    ) -> Optional[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        url = item["url"]
        fmt = item.get("format", "mp4").lower()
        
        # Use a safe UUID filename to prevent any Unicode/path escaping bugs
        safe_id = f"icon_{uuid.uuid4().hex[:10]}"
        raw_ext = "webp" if "webp" in fmt else ("gif" if "gif" in fmt else ("webm" if "webm" in fmt else "mp4"))
        raw_file = dest_dir / f"{safe_id}_raw.{raw_ext}"
        out_mp4 = dest_dir / f"{safe_id}.mp4"

        try:
            if on_progress:
                on_progress(25, "Скачивание анимации...")

            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp, open(raw_file, "wb") as f:
                f.write(resp.read())

            if not raw_file.exists() or raw_file.stat().st_size == 0:
                return None

            # If already mp4, copy directly
            if raw_ext == "mp4":
                shutil.copy2(raw_file, out_mp4)
                return out_mp4

            # Convert WebP / GIF / WebM to MP4 via ffmpeg
            if on_progress:
                on_progress(65, "Конвертация в видеоформат...")

            ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
            cmd = [
                ffmpeg_bin, "-y", "-nostdin",
                "-i", str(raw_file),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-vf", "scale='trunc(iw/2)*2':'trunc(ih/2)*2'",
                "-movflags", "+faststart",
                "-an",
                str(out_mp4)
            ]
            subprocess.run(cmd, check=True, capture_output=True)

            if out_mp4.exists():
                return out_mp4

        except Exception as e:
            print(f"[!] download_and_convert_to_mp4 error: {e}")

        return None
