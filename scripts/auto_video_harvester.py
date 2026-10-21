"""
H3H Automated Video Background Harvester Pipeline.
Streamlined, continuous harvesting ("на поток") for both:
1. Main Branch: High-quality, atmospheric, SFW gaming video backgrounds for Nintendo Switch.
   Sources: SteamGridDB (animated heroes/grids for Switch games) + MoeWalls (cinematic Switch exclusives).
2. After Dark Branch: Mature, ecchi, 18+, anime/waifu video backgrounds.
   Sources: MoeWalls (mature tags/waifus) + Community collections.

Features:
- Dual-source harvesting (SteamGridDB + MoeWalls)
- Codec selection: AVC (H.264) or HEVC (H.265 with NVDEC hvc1 tag)
- Continuous streaming loop mode (--continuous) with configurable intervals and batch sizes
- Automatic Google Drive token refresh (runs indefinitely without auth expiry)
- Atomic progress logging and duplicate prevention on H: drive
- Automated GitHub catalog sync and branch pushing
"""

import os
import sys
import json
import time
import re
import argparse
import hashlib
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

# Path configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from scripts.title_id_resolver import TitleIdResolver
from h3h_studio.core.steamgriddb import SteamGridDBClient
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import (
    GDRIVE_FOLDER_ID,
    GDRIVE_AFTER_DARK_FOLDER_ID,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK
)

STAGE_DIR = Path(r"H:\h3h_stage")
RAW_DIR = STAGE_DIR / "raw"
P720_DIR = STAGE_DIR / "720p"
THUMB_DIR = STAGE_DIR / "thumbs"

for d in [STAGE_DIR, RAW_DIR, P720_DIR, THUMB_DIR]:
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# Priority games queue for SteamGridDB harvesting (high yield of animated heroes & motion grids)
PRIORITY_STEAMGRID_GAMES = [
    # Top Action & Shooters
    ("01007820196A6000", "Red Dead Redemption", "Red Dead Redemption"),
    ("0100ABD01785C000", "Portal Companion Collection", "Portal"),
    ("01000B900D8B0000", "DOOM Eternal", "DOOM Eternal"),
    ("0100BC0005C8A000", "DOOM (2016)", "DOOM"),
    ("010034400C3DA000", "Wolfenstein II: The New Colossus", "Wolfenstein II: The New Colossus"),
    ("010014200B0D0000", "Metro 2033 Redux", "Metro 2033"),
    ("01000F400B0D2000", "Metro: Last Light Redux", "Metro: Last Light"),
    ("01008C3005A66000", "Dead Cells", "Dead Cells"),
    ("01004AB00A260000", "Dark Souls Remastered", "Dark Souls"),
    ("010029600D56A000", "Katana Zero", "Katana ZERO"),
    ("010079C009494000", "Cuphead", "Cuphead"),
    ("01002B30028F6000", "Celeste", "Celeste"),
    ("010052300B254000", "Hades", "Hades"),
    ("010036500ECF2000", "Hollow Knight", "Hollow Knight"),
    ("0100CD801CE5E000", "Balatro", "Balatro"),
    ("010097F018538000", "Dave the Diver", "Dave the Diver"),
    ("01002E7016C46000", "Cult of the Lamb", "Cult of the Lamb"),
    ("010027F017B12000", "Inscryption", "Inscryption"),
    ("0100DA801624E000", "Tunic", "Tunic"),
    ("0100307018934000", "Signalis", "Signalis"),
    ("01008C0016544000", "Sea of Stars", "Sea of Stars"),
    ("010093800B8C8000", "Stardew Valley", "Stardew Valley"),
    ("01003D100E9C6000", "The Witcher 3: Wild Hunt", "The Witcher 3: Wild Hunt"),
    ("01005CA01580E000", "Persona 5 Royal", "Persona 5 Royal"),
    ("01005C000B2AE000", "NieR:Automata", "NieR:Automata"),
    ("01000A10041EA000", "The Elder Scrolls V: Skyrim", "The Elder Scrolls V: Skyrim"),
    ("0100559011540000", "Monster Hunter Rise", "Monster Hunter Rise"),
    ("010040801A4C8000", "Blasphemous 2", "Blasphemous 2"),
    ("010006700C7E2000", "Blasphemous", "Blasphemous"),
    ("010038800C3DC000", "BioShock Remastered", "BioShock Remastered"),
    ("010065000C3DE000", "BioShock Infinite", "BioShock Infinite"),
    ("01000F900C404000", "Borderlands 2", "Borderlands 2"),
    ("01005A300C3FA000", "Borderlands: The Pre-Sequel", "Borderlands: The Pre-Sequel"),
    ("010076F0049A2000", "Bayonetta", "Bayonetta"),
    ("01003BC0000A0000", "Kirby and the Forgotten Land", "Kirby and the Forgotten Land"),
    ("01002DA013484000", "Metroid Dread", "Metroid Dread"),
    ("010086C00AF7C000", "Ori and the Will of the Wisps", "Ori and the Will of the Wisps")
]

# Known popular Switch games for SFW Main catalog search queries on MoeWalls
POPULAR_SWITCH_SFW_GAMES = [
    # Top Nintendo Exclusives
    ("0100000000010000", "Super Mario Odyssey", ["super mario odyssey", "mario odyssey"]),
    ("0100152000022000", "Mario Kart 8 Deluxe", ["mario kart 8", "mario kart"]),
    ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild", ["breath of the wild", "zelda botw"]),
    ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom", ["tears of the kingdom", "zelda totk"]),
    ("01006F8002326000", "Animal Crossing: New Horizons", ["animal crossing new horizons", "animal crossing"]),
    ("01000A10041EA000", "Super Smash Bros. Ultimate", ["super smash bros ultimate", "smash ultimate"]),
    ("0100A3900C3E2000", "Pokemon Sword / Shield", ["pokemon sword shield", "pokemon zacian"]),
    ("0100ABF008968000", "Pokemon Scarlet / Violet", ["pokemon scarlet violet", "koraidon miraidon"]),
    ("01002DA013484000", "Metroid Dread", ["metroid dread", "samus aran dread"]),
    ("01000320000CC000", "Splatoon 2 / 3", ["splatoon", "splatoon 3"]),
    ("0100E95004038000", "Xenoblade Chronicles 2", ["xenoblade chronicles 2 scenery", "xenoblade world"]),
    ("010074600E9F2000", "Xenoblade Chronicles 3", ["xenoblade chronicles 3 scenery", "xenoblade 3"]),
    ("01003BC0000A0000", "Kirby and the Forgotten Land", ["kirby forgotten land", "kirby"]),
    ("0100559011540000", "Monster Hunter Rise", ["monster hunter rise", "monster hunter kamura"]),

    # Top Acclaimed Multiplatform Switch Ports
    ("010036500ECF2000", "Hollow Knight", ["hollow knight", "hallownest", "hollow knight silksong"]),
    ("0100E8B00BDC6000", "The Witcher 3: Wild Hunt", ["witcher 3 scenery", "geralt of rivia kaer morhen", "witcher 3 novigrad"]),
    ("01005C000B2AE000", "NieR:Automata", ["nier automata city ruins", "nier automata amusement park"]),
    ("01004AB00A260000", "Dark Souls: Remastered", ["dark souls bonfire", "dark souls anor londo", "dark souls firelink"]),
    ("010091200CDA4000", "Persona 5 Royal", ["persona 5 shibuya", "persona 5 royal phantom thieves"]),
    ("010052300B254000", "Hades", ["hades game underworld", "zagreus hades"]),
    ("0100B9600AA90000", "Celeste", ["celeste mountain", "celeste game"]),
    ("01008C3005A66000", "Dead Cells", ["dead cells prisoner", "dead cells game"]),
    ("010076F0049A2000", "Bayonetta", ["bayonetta action", "bayonetta umbra"]),
    ("010079C009494000", "Cuphead", ["cuphead boss", "cuphead game"]),
    ("010086C00AF7C000", "Ori and the Will of the Wisps", ["ori and the will of the wisps", "ori blind forest"]),
    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"]),
    ("01000B900D8B0000", "Doom Eternal", ["doom eternal slayer", "doom eternal fortress"])
]

# Queries specifically for After Dark (18+ / Ecchi / Mature / Anime Waifu)
AFTER_DARK_QUERIES = [
    "ecchi", "bikini", "swimsuit", "bunny girl",
    "nier 2b", "nier a2", "tifa lockhart",
    "nikke", "stellar blade eve", "azur lane",
    "genshin impact", "honkai star rail", "blue archive",
    "chainsaw man makima", "fate grand order"
]

NSFW_KEYWORDS = [
    "bikini", "swimsuit", "bunny", "ecchi", "nsfw", "18+", "erotic", "nude",
    "naked", "cleavage", "lingerie", "boobs", "ass", "thighs", "waifu", "hentai",
    "sensual", "undressing"
]

def clean_switch_title(raw_title: str) -> str:
    """Clean Switch release filenames to canonical game names."""
    t = re.sub(r'\[.*?\]', '', raw_title)
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'(\+.*$)', '', t)
    t = re.sub(r'v\d+(\.\d+)*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[:\-–_]+', ' ', t)
    return ' '.join(t.split())


class AutoVideoHarvester:
    def __init__(self, mode: str = "main", codec: str = "h264", source: str = "all"):
        self.mode = mode.lower()  # "main" or "after_dark"
        if self.mode == "after-dark":
            self.mode = "after_dark"
        self.codec = codec.lower()  # "h264" or "hevc"
        self.source = source.lower()  # "all", "steamgriddb", "moewalls"
        
        self.resolver = TitleIdResolver()
        self.sgdb_client = SteamGridDBClient()
        
        self.log_file = PROJECT_ROOT / "catalog" / "data" / f"video_harvest_log_{self.mode}.json"
        self.log_data = self._load_log()
        
        self.catalog_path = PROJECT_ROOT / (CATALOG_PATH_AFTER_DARK if self.mode == "after_dark" else CATALOG_PATH_STANDARD)
        self.branch = "after-dark" if self.mode == "after_dark" else "main"
        self.folder_id = GDRIVE_AFTER_DARK_FOLDER_ID if self.mode == "after_dark" else GDRIVE_FOLDER_ID

    def _load_log(self) -> Dict[str, Any]:
        if self.log_file.exists():
            try:
                return json.loads(self.log_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"harvested_urls": {}, "total_harvested": 0, "last_updated": ""}

    def _save_log(self):
        self.log_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text(json.dumps(self.log_data, indent=2, ensure_ascii=False), encoding="utf-8")

    def is_url_harvested(self, url: str) -> bool:
        return url in self.log_data["harvested_urls"]

    def mark_harvested(self, url: str, info: Dict[str, Any]):
        self.log_data["harvested_urls"][url] = info
        self.log_data["total_harvested"] = len(self.log_data["harvested_urls"])
        self._save_log()

    def get_gdrive_token(self) -> Optional[str]:
        gdrive_cfg = GoogleDriveHelper.get_stored_config()
        refresh_tok = gdrive_cfg.get("refresh_token")
        if not refresh_tok:
            return None
        return GoogleDriveHelper.refresh_access_token(refresh_tok)

    @staticmethod
    def is_nsfw_text(text: str) -> bool:
        t_low = text.lower()
        return any(kw in t_low for kw in NSFW_KEYWORDS)

    def search_moewalls_articles(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        url = f"https://moewalls.com/?s={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers=HEADERS)
        results = []
        try:
            html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
            articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
            for page_url, raw_title in articles:
                clean_title = re.sub('<[^<]+?>', '', raw_title).strip()
                if self.mode == "main" and self.is_nsfw_text(clean_title):
                    continue
                results.append({"title": clean_title, "page_url": page_url})
                if len(results) >= limit:
                    break
        except Exception as e:
            print(f"[!] Moewalls search error for '{query}': {e}")
        return results

    def extract_direct_video_url(self, page_url: str) -> Optional[str]:
        req = urllib.request.Request(page_url, headers=HEADERS)
        try:
            html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
            vids = re.findall(r'<source[^>]*src="([^"]+\.(?:webm|mp4))"', html)
            if not vids:
                vids = re.findall(r'href="([^"]+\.(?:webm|mp4))"', html)
            if vids:
                v_url = vids[0]
                if v_url.startswith("/"):
                    v_url = "https://moewalls.com" + v_url
                return v_url
        except Exception as e:
            print(f"[!] Video extraction error for {page_url}: {e}")
        return None

    def transcode_video(self, raw_path: Path, out_mp4: Path, out_thumb: Path) -> bool:
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_thumb.parent.mkdir(parents=True, exist_ok=True)
        is_hevc = (self.codec == "hevc")

        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-t", "30",
            "-i", str(raw_path),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black",
            "-threads", "4",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart"
        ]
        if is_hevc:
            cmd.extend([
                "-c:v", "libx265",
                "-preset", "ultrafast",
                "-tag:v", "hvc1",
                "-b:v", "1800k", "-maxrate", "2400k", "-bufsize", "4000k"
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-profile:v", "high", "-level", "4.1",
                "-b:v", "2500k", "-maxrate", "3000k", "-bufsize", "5000k"
            ])
        cmd.append(str(out_mp4))

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        except Exception as e:
            print(f"[!] FFmpeg transcode error: {e}")
            return False

        # Thumbnail
        cmd_thumb = [
            "ffmpeg", "-y", "-nostdin",
            "-ss", "00:00:01",
            "-i", str(out_mp4),
            "-vframes", "1",
            "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black",
            str(out_thumb)
        ]
        try:
            subprocess.run(cmd_thumb, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except Exception:
            pass

        return True

    def process_and_upload_asset(
        self,
        asset_url: str,
        title_id: str,
        game_title: str,
        var_name: str,
        author: str,
        style: str,
        catalog: Dict[str, Any],
        games_map: Dict[str, Any],
        gdrive_token: str
    ) -> bool:
        """Download raw asset, transcode to 720p 30fps Switch format, upload to Drive, and register in catalog."""
        var_id = "v_" + hashlib.md5(asset_url.encode()).hexdigest()[:8]
        ext = ".webm" if ".webm" in asset_url else (".webp" if ".webp" in asset_url else ".mp4")
        raw_file = RAW_DIR / f"{var_id}{ext}"
        out_mp4 = P720_DIR / f"{var_id}.mp4"
        out_thumb = THUMB_DIR / f"{var_id}.jpg"

        try:
            if not raw_file.exists() or raw_file.stat().st_size == 0:
                print(f"  -> Downloading stream ({ext})...")
                req = urllib.request.Request(asset_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp, open(raw_file, 'wb') as vf:
                    vf.write(resp.read())

            if not raw_file.exists() or raw_file.stat().st_size < 1000:
                print("  [!] Downloaded file is invalid or too small.")
                return False

            print(f"  -> Transcoding to 720p 30fps {self.codec.upper()}...")
            ok = self.transcode_video(raw_file, out_mp4, out_thumb)
            if not ok or not out_mp4.exists() or out_mp4.stat().st_size == 0:
                return False

            print(f"  -> Uploading to Google Drive...")
            up_res = GoogleDriveClient.upload_file(out_mp4, self.folder_id, gdrive_token)
            fid = up_res.get("id")
            if not fid:
                print("  [!] Failed to upload to Google Drive.")
                return False

            GoogleDriveClient.make_public(fid, gdrive_token)
            direct_url = GoogleDriveHelper.to_direct_download_url(fid)
            preview_url = GoogleDriveHelper.to_preview_url(fid)

            size_bytes = out_mp4.stat().st_size
            h_sha = hashlib.sha256(out_mp4.read_bytes()).hexdigest().upper()

            variant_entry = {
                "id": var_id,
                "name": var_name or "Atmospheric Theme",
                "style": style,
                "version": "1.0",
                "url": direct_url,
                "previewUrl": preview_url,
                "sizeBytes": size_bytes,
                "sha256": h_sha,
                "durationSec": 30.0,
                "author": author,
                "codec": self.codec,
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": False,
                "notes": f"Switch 720p 30fps {self.codec.upper()} | {var_name}"
            }

            tid_upper = title_id.upper()
            if tid_upper not in games_map:
                g_entry = {
                    "titleId": tid_upper,
                    "title": game_title,
                    "publisher": "Nintendo Switch" if tid_upper != "0000000000000000" else "H3H Studio",
                    "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{tid_upper}.jpg" if tid_upper != "0000000000000000" else "",
                    "variants": []
                }
                catalog["games"].append(g_entry)
                games_map[tid_upper] = g_entry

            games_map[tid_upper]["variants"].append(variant_entry)

            self.mark_harvested(asset_url, {
                "title": var_name,
                "titleId": tid_upper,
                "gameName": game_title,
                "varId": var_id,
                "driveId": fid,
                "mode": self.mode,
                "codec": self.codec,
                "author": author
            })
            return True

        except Exception as ex:
            print(f"  [!] Processing error: {ex}")
            return False

    def harvest_from_steamgriddb(self, limit: int, catalog: Dict[str, Any], games_map: Dict[str, Any], gdrive_token: str) -> int:
        """Harvest animated heroes and motion art from SteamGridDB across Switch library."""
        harvested = 0

        # Build prioritized list of targets
        targets: List[Tuple[str, str, str]] = list(PRIORITY_STEAMGRID_GAMES)

        # Also load switch_titles_db.json for long-tail games
        db_path = PROJECT_ROOT / "studio" / "h3h_studio" / "data" / "switch_titles_db.json"
        if db_path.exists():
            try:
                switch_db = json.loads(db_path.read_text(encoding="utf-8"))
                existing_tids = {t[0] for t in targets}
                for entry in switch_db:
                    tid = entry.get("titleId", "").upper()
                    raw_title = entry.get("title", "")
                    if len(tid) == 16 and tid not in existing_tids:
                        c_title = clean_switch_title(raw_title)
                        if len(c_title) >= 3:
                            targets.append((tid, raw_title, c_title))
            except Exception as e:
                print(f"[!] Warning reading switch_titles_db: {e}")

        # Prioritize games missing or with few variants in catalog
        targets.sort(key=lambda t: len(games_map.get(t[0].upper(), {}).get("variants", [])))

        for tid, full_game_name, search_query in targets:
            if harvested >= limit:
                break

            current_vars = len(games_map.get(tid.upper(), {}).get("variants", []))
            if current_vars >= 4:
                continue

            print(f"\n🔍 [SteamGridDB] Searching for '{search_query}' (ID: {tid})...")
            try:
                sg_results = self.sgdb_client.search_game(search_query)
            except Exception as e:
                print(f"  [!] SteamGridDB search failed: {e}")
                continue

            if not sg_results:
                continue

            # Find best match
            matched_game = None
            q_low = search_query.lower()
            for cand in sg_results:
                cand_name = cand.get("name", "").lower()
                if q_low in cand_name or cand_name in q_low:
                    matched_game = cand
                    break

            if not matched_game:
                matched_game = sg_results[0]

            sg_id = matched_game["id"]
            sg_name = matched_game["name"]

            # Check animated heroes first
            candidates = []
            try:
                heroes = self.sgdb_client.get_animated_heroes(sg_id)
                for h in heroes:
                    if self.mode == "main" and h.get("nsfw"):
                        continue
                    u = h.get("url") or h.get("thumb")
                    if u and not self.is_url_harvested(u):
                        author = h.get("author", {}).get("name", "SteamGridDB Community")
                        candidates.append((u, f"{sg_name} Hero", author, "Community Hero"))
            except Exception as e:
                print(f"  [!] Hero fetch error: {e}")

            # Check animated grids if no heroes found
            if not candidates:
                try:
                    grids = self.sgdb_client.get_animated_grids(sg_id)
                    for gr in grids:
                        if self.mode == "main" and gr.get("nsfw"):
                            continue
                        u = gr.get("url") or gr.get("thumb")
                        if u and not self.is_url_harvested(u):
                            author = gr.get("author", {}).get("name", "SteamGridDB Community")
                            candidates.append((u, f"{sg_name} Motion Cover", author, "Motion Grid"))
                except Exception as e:
                    print(f"  [!] Grid fetch error: {e}")

            for asset_url, var_name, author, style in candidates:
                if harvested >= limit:
                    break
                print(f"\n[*] Harvesting SteamGridDB asset for '{sg_name}': {asset_url}")
                ok = self.process_and_upload_asset(
                    asset_url=asset_url,
                    title_id=tid,
                    game_title=full_game_name,
                    var_name=var_name,
                    author=author,
                    style=style,
                    catalog=catalog,
                    games_map=games_map,
                    gdrive_token=gdrive_token
                )
                if ok:
                    harvested += 1
                    print(f"  [+] Success! ({harvested}/{limit}) Added {var_name} to {full_game_name}")

        return harvested

    def harvest_from_moewalls(self, limit: int, catalog: Dict[str, Any], games_map: Dict[str, Any], gdrive_token: str) -> int:
        """Harvest cinematic live video wallpapers from MoeWalls."""
        query_queue: List[Tuple[str, str, str]] = []  # (titleId, gameName, query)
        if self.mode == "main":
            for tid, gname, qlist in POPULAR_SWITCH_SFW_GAMES:
                for q in qlist:
                    query_queue.append((tid, gname, q))
        else:
            for q in AFTER_DARK_QUERIES:
                query_queue.append(("0000000000000000", "★ Коллекция After Dark (Свободный выбор)", q))

        harvested = 0
        for tid, default_game_name, q in query_queue:
            if harvested >= limit:
                break

            print(f"\n🔍 [MoeWalls] Searching for: '{q}' ({default_game_name})...")
            articles = self.search_moewalls_articles(q, limit=3)
            for art in articles:
                if harvested >= limit:
                    break

                page_url = art["page_url"]
                if self.is_url_harvested(page_url):
                    continue

                vid_url = self.extract_direct_video_url(page_url)
                if not vid_url or self.is_url_harvested(vid_url):
                    continue

                title = art["title"].replace("Live Wallpaper", "").strip(" -–")
                clean_name = re.sub(r'\(.*?\)', '', title).strip()
                if len(clean_name) > 40:
                    clean_name = clean_name[:40].strip()

                print(f"\n[*] Harvesting MoeWalls video: '{clean_name}' (Target: {default_game_name})")
                ok = self.process_and_upload_asset(
                    asset_url=vid_url,
                    title_id=tid,
                    game_title=default_game_name,
                    var_name=clean_name or "Atmospheric Theme",
                    author="MoeWalls / Community",
                    style="Ecchi / Mature" if self.mode == "after_dark" else "Cinematic",
                    catalog=catalog,
                    games_map=games_map,
                    gdrive_token=gdrive_token
                )
                if ok:
                    self.mark_harvested(page_url, {"page": True, "vid": vid_url})
                    harvested += 1
                    print(f"  [+] Success! ({harvested}/{limit}) Added {clean_name} to {default_game_name}")

        return harvested

    def harvest_stream(self, limit: int = 10) -> int:
        print(f"\n==================================================")
        print(f"[*] Starting Video Harvester (Mode: {self.mode.upper()}, Source: {self.source.upper()}, Codec: {self.codec.upper()})")
        print(f"[*] Target Catalog: {self.catalog_path}")
        print(f"[*] Target GDrive Folder ID: {self.folder_id}")
        print(f"==================================================")

        gdrive_token = self.get_gdrive_token()
        if not gdrive_token:
            print("[-] Error: Failed to obtain Google Drive token.")
            return 0

        if not self.catalog_path.exists():
            print(f"[-] Catalog file not found: {self.catalog_path}")
            return 0

        catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        games_map = {g["titleId"].upper(): g for g in catalog.get("games", [])}

        harvested_count = 0

        # Run SteamGridDB if requested and main mode
        if self.source in ["all", "steamgriddb"] and self.mode == "main":
            sg_limit = limit if self.source == "steamgriddb" else max(1, limit // 2)
            c = self.harvest_from_steamgriddb(sg_limit, catalog, games_map, gdrive_token)
            harvested_count += c

        # Run MoeWalls if requested or after-dark
        remaining = limit - harvested_count
        if remaining > 0 and (self.source in ["all", "moewalls"] or self.mode == "after_dark"):
            c = self.harvest_from_moewalls(remaining, catalog, games_map, gdrive_token)
            harvested_count += c

        if harvested_count > 0:
            catalog["updatedAt"] = datetime.now(timezone.utc).isoformat()
            catalog["totalGames"] = len(catalog["games"])
            catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog["games"])

            with open(self.catalog_path, "w", encoding="utf-8") as cf:
                json.dump(catalog, cf, ensure_ascii=False, indent=2)

            print(f"\n[+] Catalog updated: {catalog['totalGames']} games, {catalog['totalVariants']} variants.")
            print(f"[*] Pushing updates to GitHub branch '{self.branch}'...")

            gh_token, _ = GitHubPublisher.get_stored_credentials()
            repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
            rel_cat = str(self.catalog_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

            subprocess.run(["git", "add", rel_cat, str(self.log_file.relative_to(PROJECT_ROOT))], check=True)
            subprocess.run(["git", "commit", "-m", f"feat(harvest): automated batch harvest {harvested_count} {self.mode} video themes ({self.codec.upper()})"], check=True)
            if self.mode == "after_dark":
                subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/after-dark"], check=True)
            subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)
            print(f"[SUCCESS] Successfully pushed {harvested_count} new video backgrounds to GitHub!")

        return harvested_count


def main():
    parser = argparse.ArgumentParser(description="H3H Automated Video Harvester Pipeline")
    parser.add_argument("--mode", choices=["main", "after-dark", "all"], default="main", help="Target catalog mode")
    parser.add_argument("--source", choices=["all", "steamgriddb", "moewalls"], default="all", help="Source provider")
    parser.add_argument("--codec", choices=["h264", "hevc"], default="h264", help="Video codec (h264 or hevc)")
    parser.add_argument("--limit", type=int, default=10, help="Number of backgrounds to harvest per batch")
    parser.add_argument("--continuous", action="store_true", help="Run continuously in a loop ('на поток')")
    parser.add_argument("--interval", type=int, default=60, help="Interval in seconds between continuous batches")
    args = parser.parse_args()

    modes = ["main", "after-dark"] if args.mode == "all" else [args.mode]

    batch_num = 1
    while True:
        print(f"\n>>> [BATCH {batch_num}] Starting harvesting stream at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} <<<")
        for m in modes:
            h = AutoVideoHarvester(mode=m, codec=args.codec, source=args.source)
            h.harvest_stream(limit=args.limit)

        if not args.continuous:
            break

        print(f"\n[INFO] Batch {batch_num} complete. Sleeping {args.interval}s before next stream batch... (Press Ctrl+C to stop)")
        time.sleep(args.interval)
        batch_num += 1

if __name__ == "__main__":
    main()
