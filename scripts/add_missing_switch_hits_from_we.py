"""

H3H Switch Hits & Missing Games Harvester via Wallpaper Engine (60fps).

Directly enriches catalog/data/catalog.json with top Nintendo Switch 1 games

by downloading verified live wallpaper videos from MoeWalls / Wallpaper Engine.

"""



import os

import sys

import re

import json

import time

import hashlib

import subprocess

import requests

import urllib.parse

from pathlib import Path

from datetime import datetime, timezone

from typing import Dict, Any, List, Optional, Tuple



sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)



PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT))

sys.path.insert(0, str(PROJECT_ROOT / "studio"))



from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient

from h3h_studio.core.github_publisher import GitHubPublisher

from tg_bot.config import GDRIVE_FOLDER_ID, CATALOG_PATH_STANDARD, detect_local_proxy



LOCAL_PROXY = detect_local_proxy()



STAGE_DIR = Path(r"H:\h3h_stage") if Path(r"H:\h3h_stage").exists() else (PROJECT_ROOT / "tmp" / "h3h_stage")

RAW_DIR = STAGE_DIR / "raw_we"

P720_DIR = STAGE_DIR / "720p_we"

for d in (STAGE_DIR, RAW_DIR, P720_DIR):

    d.mkdir(parents=True, exist_ok=True)



HEADERS = {

    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',

    'Referer': 'https://moewalls.com/'

}



SESSION = requests.Session()

if LOCAL_PROXY:

    SESSION.proxies = {"http": LOCAL_PROXY, "https": LOCAL_PROXY}

SESSION.headers.update(HEADERS)



TARGET_SWITCH_GAMES = [

    ("01004990172B0000", "Sifu", ["sifu", "sifu kung fu"]),

    ("010063F014170000", "Danganronpa: Trigger Happy Havoc", ["danganronpa", "monokuma"]),

    ("01007F600B134000", "Metal Gear Solid: Master Collection Vol. 1", ["metal gear solid", "solid snake"]),

    ("010099F003C4E000", "Darkest Dungeon", ["darkest dungeon"]),

    ("01002F401C950000", "Tsukihime -A piece of blue glass moon-", ["tsukihime"]),

    ("0100B3900C3E2000", "Phoenix Wright: Ace Attorney Trilogy", ["phoenix wright", "ace attorney"]),

    ("01004E9013A66000", "NINJA GAIDEN: Master Collection", ["ninja gaiden", "ryu hayabusa"]),

    ("0100E95004038000", "Xenoblade Chronicles 2", ["xenoblade", "xenoblade chronicles 2", "pyra mythra"]),

    ("010074F013262000", "Xenoblade Chronicles 3", ["xenoblade", "xenoblade chronicles 3"]),

    ("0100FF500E34A000", "Xenoblade Chronicles: Definitive Edition", ["xenoblade chronicles", "shulk"]),

    ("0100057003A40000", "Bayonetta 2", ["bayonetta"]),

    ("0100C8800B8DC000", "Bayonetta 3", ["bayonetta 3", "bayonetta"]),

    ("0100702008E12000", "Donkey Kong Country: Tropical Freeze", ["donkey kong", "tropical freeze"]),

    ("0100B7C00933A000", "Pikmin 4", ["pikmin"]),

    ("0100BC0018138000", "Super Mario RPG", ["super mario", "mario"]),

    ("0100ECD018EBE000", "Paper Mario: The Thousand-Year Door", ["paper mario", "mario"]),

    ("01008CF01BAAC000", "The Legend of Zelda: Echoes of Wisdom", ["zelda", "link"]),

    ("0100A6301214E000", "Fire Emblem Engage", ["fire emblem", "fire emblem engage"]),

    ("0100BF500207C000", "Metroid Prime Remastered", ["metroid", "samus aran"]),

    ("01007300020FA000", "Astral Chain", ["astral chain"]),

    ("010022A011A62000", "Crysis Remastered", ["crysis", "nanosuit"]),

    ("01009B9013E56000", "Factorio", ["factorio"]),

    ("010075100BFEC000", "Don't Starve Together", ["dont starve", "don't starve"]),

    ("0100E4A00CBCE000", "Risk of Rain 2", ["risk of rain", "risk of rain 2"]),

    ("01005F600B3C2000", "Slay the Spire", ["slay the spire"]),

    ("01007560153F0000", "Five Nights at Freddy's: Security Breach", ["five nights at freddys", "fnaf"]),

    ("01004060153FA000", "Sonic Frontiers", ["sonic frontiers", "sonic the hedgehog"]),

    ("01000A10041EA000", "Persona 5 Royal", ["persona 5", "joker persona", "phantom thieves"]),

    ("0100C4601445E000", "NieR:Automata The End of YoRHa Edition", ["nier automata", "2b nier", "9s nier"]),

    ("01005C800CE32000", "Cuphead", ["cuphead", "mugman"]),

    ("01006BB00C6F0000", "Hollow Knight", ["hollow knight", "hornet"]),

    ("0100346008F42000", "Celeste", ["celeste madeline"]),

    ("010081E00B2B4000", "Dead Cells", ["dead cells"]),

    ("01001A80113B6000", "Ori and the Will of the Wisps", ["ori and the will of the wisps", "ori and the blind forest"]),

    ("0100B04011742000", "Monster Hunter Rise", ["monster hunter rise", "magnamalo"]),

    ("0100535012974000", "Hades", ["hades zagreus", "zagreus hades"])

]





def get_gdrive_token() -> Optional[str]:

    cfg = GoogleDriveHelper.get_stored_config()

    ref = cfg.get("refresh_token")

    if ref:

        tok = GoogleDriveHelper.refresh_access_token(ref)

        if tok:

            cfg["token"] = tok

            GoogleDriveHelper.save_stored_config(cfg)

            return tok

    return cfg.get("token")





def is_relevant_for_game(wallpaper_title: str, post_url: str, game_name: str) -> bool:

    comb = (wallpaper_title + " " + post_url).lower()

    # General non-Switch PC clutter

    if any(bad in comb for bad in ["league of legends", "valorant", "dota 2", "genshin impact", "honkai", "counter strike"]):

        return False

        

    g_low = game_name.lower()

    if "sifu" in g_low and "sifu" not in comb:

        return False

    if "danganronpa" in g_low and not any(k in comb for k in ["danganronpa", "monokuma", "chiaki", "junko", "makoto"]):

        return False

    if "metal gear" in g_low and not any(k in comb for k in ["metal gear", "snake", "big boss", "raiden"]):

        return False

    if "darkest dungeon" in g_low and "darkest dungeon" not in comb:

        return False

    if "tsukihime" in g_low and not any(k in comb for k in ["tsukihime", "arcueid", "ciel", "akiha", "shiki"]):

        return False

    if "phoenix wright" in g_low and not any(k in comb for k in ["phoenix wright", "ace attorney", "edgeworth", "maya fey"]):

        return False

    if "ninja gaiden" in g_low and not any(k in comb for k in ["ninja gaiden", "ryu hayabusa", "hayabusa"]):

        return False

    if "xenoblade" in g_low and not any(k in comb for k in ["xenoblade", "pyra", "mythra", "shulk", "noah", "mio"]):

        return False

    if "bayonetta" in g_low and not any(k in comb for k in ["bayonetta", "cereza", "jeanne"]):

        return False

    if "donkey kong" in g_low and not any(k in comb for k in ["donkey kong", "diddy", "tropical freeze"]):

        return False

    if "zelda" in g_low and not any(k in comb for k in ["zelda", "link", "hyrule", "ganon"]):

        return False

    if "mario" in g_low and not any(k in comb for k in ["mario", "luigi", "bowser", "peach", "toad"]):

        return False

    if "metroid" in g_low and not any(k in comb for k in ["metroid", "samus"]):

        return False

    if "persona" in g_low and not any(k in comb for k in ["persona", "joker", "phantom thieves", "kasumi", "makoto"]):

        return False

    if "nier" in g_low and not any(k in comb for k in ["nier", "2b", "9s", "a2", "yorha"]):

        return False

    if "cuphead" in g_low and not any(k in comb for k in ["cuphead", "mugman", "chalice"]):

        return False

    if "hollow knight" in g_low and not any(k in comb for k in ["hollow knight", "hornet", "knight", "hallownest"]):

        return False

    if "celeste" in g_low and not any(k in comb for k in ["celeste", "madeline"]):

        return False

    if "dead cells" in g_low and not any(k in comb for k in ["dead cells", "beheaded"]):

        return False

    if "ori" in g_low and not any(k in comb for k in ["ori", "ku", "nibel", "niwen"]):

        return False

    if "monster hunter" in g_low and not any(k in comb for k in ["monster hunter", "kamura", "magnamalo", "malzeno", "palico"]):

        return False

    if "hades" in g_low and not any(k in comb for k in ["hades", "zagreus", "melinoe", "nyx", "thanatos"]):

        return False

    return True





def search_moewalls_wallpapers(query: str, game_name: str, limit: int = 5) -> List[Tuple[str, str]]:

    url = f"https://moewalls.com/?s={urllib.parse.quote(query)}" if not query.startswith("tag:") else f"https://moewalls.com/{query.replace(':', '/')}/"

    results = []

    try:

        resp = SESSION.get(url, timeout=12)

        items = re.findall(r'<a\s+title="([^"]+)"\s+class="g1-frame"\s+href="([^"]+)"', resp.text)

        if not items:

            items = [(t, u) for u, t in re.findall(r'<h[23]\s+class="entry-title[^"]*"><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.DOTALL)]

        for raw_title, post_url in items:

            clean_t = re.sub('<[^<]+?>', '', raw_title).replace("Live Wallpaper", "").strip()

            if is_relevant_for_game(clean_t, post_url, game_name):

                results.append((clean_t, post_url))

                if len(results) >= limit:

                    break

    except Exception as e:

        print(f"    [!] Search error for '{query}': {e}")

    return results





def extract_direct_video_url(post_url: str) -> Optional[str]:

    try:

        resp = SESSION.get(post_url, timeout=12)

        vids = re.findall(r'<source[^>]*src="([^"]+\.(?:webm|mp4))"', resp.text)

        if not vids:

            vids = re.findall(r'href="([^"]+\.(?:webm|mp4))"', resp.text)

        if vids:

            v_url = vids[0].strip()

            if v_url.startswith("/"):

                v_url = "https://moewalls.com" + v_url

            return v_url

    except Exception:

        pass

    return None





def download_file_fast(url: str, out_path: Path) -> bool:

    try:

        if out_path.exists():

            out_path.unlink()

        with SESSION.get(url, stream=True, timeout=20) as r:

            r.raise_for_status()

            with open(out_path, 'wb') as f:

                for chunk in r.iter_content(chunk_size=65536):

                    if chunk:

                        f.write(chunk)

        return out_path.exists() and out_path.stat().st_size > 50_000

    except Exception as e:

        print(f"    [!] Download error: {e}")

        return False





def encode_local_to_switch_mp4(in_path: Path, out_path: Path) -> bool:

    if out_path.exists():

        try:

            out_path.unlink()

        except Exception:

            pass

    cmd = [

        "ffmpeg", "-y", "-nostdin",

        "-i", str(in_path),

        "-t", "18",

        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30",

        "-c:v", "libx264",

        "-preset", "veryfast",

        "-crf", "22",

        "-maxrate", "3500k",

        "-bufsize", "7000k",

        "-pix_fmt", "yuv420p",

        "-movflags", "+faststart",

        "-c:a", "aac",

        "-b:a", "128k",

        str(out_path)

    ]

    try:

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        proc.communicate(timeout=30)

        return proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 150_000

    except Exception:

        try:

            proc.kill()

        except Exception:

            pass

        return False





def compute_sha256(path: Path) -> str:

    h = hashlib.sha256()

    with open(path, "rb") as f:

        for chunk in iter(lambda: f.read(65536), b""):

            h.update(chunk)

    return h.hexdigest().upper()





def check_has_audio(path: Path) -> bool:

    try:

        res = subprocess.run(

            ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "a", str(path)],

            capture_output=True, text=True, timeout=6

        )

        return "codec_type=audio" in res.stdout

    except Exception:

        return False





def harvest_all_target_games():

    cat_path = PROJECT_ROOT / CATALOG_PATH_STANDARD

    catalog = json.loads(cat_path.read_text(encoding="utf-8"))

    games_map = {g["titleId"].upper(): g for g in catalog.get("games", [])}



    gdrive_token = get_gdrive_token()

    if not gdrive_token:

        print("[-] Cannot authenticate to Google Drive.")

        return



    total_added = 0

    for tid, disp_name, queries in TARGET_SWITCH_GAMES:

        u_tid = tid.upper()

        existing_game = games_map.get(u_tid)

        existing_vars = existing_game.get("variants", []) if existing_game else []

        existing_names = {v.get("name", "").lower() for v in existing_vars}



        print(f"\n🎮 [SWITCH TITLE] {disp_name} [{u_tid}] (Current backgrounds: {len(existing_vars)})")



        found_new_for_game = 0

        for q in queries:

            if found_new_for_game >= 2:

                break

            print(f"  🔍 Searching WE repo for: '{q}'...")

            wallpapers = search_moewalls_wallpapers(q, disp_name, limit=3)



            for clean_t, post_url in wallpapers:

                if any(clean_t.lower() in en for en in existing_names) or any(en in clean_t.lower() for en in existing_names):

                    continue



                v_url = extract_direct_video_url(post_url)

                if not v_url:

                    continue



                print(f"    [*] Found Wallpaper Engine 60fps theme: '{clean_t}'")

                ext = ".webm" if v_url.endswith(".webm") else ".mp4"

                raw_file = RAW_DIR / f"{u_tid}_raw{ext}"

                out_mp4 = P720_DIR / f"{u_tid}_hit_{int(time.time())}.mp4"



                # 1. Download

                print(f"    [*] Fast-downloading video from MoeWalls...")

                if not download_file_fast(v_url, raw_file):

                    continue



                # 2. Encode to Switch 720p 30fps MP4

                print(f"    [*] Encoding to Switch 720p 30fps H.264...")

                if not encode_local_to_switch_mp4(raw_file, out_mp4):

                    try: raw_file.unlink()

                    except Exception: pass

                    continue



                try: raw_file.unlink()

                except Exception: pass



                # 3. Upload to Google Drive

                gdrive_token = get_gdrive_token() or gdrive_token

                print(f"    [*] Uploading {out_mp4.name} ({out_mp4.stat().st_size / 1024 / 1024:.2f} MB) to Google Drive...")

                try:

                    up_res = GoogleDriveClient.upload_file(out_mp4, GDRIVE_FOLDER_ID, gdrive_token)

                    file_id = up_res.get("fileId")

                    direct_url = up_res.get("directUrl") or f"https://drive.google.com/uc?export=download&id={file_id}"

                    preview_url = up_res.get("previewUrl") or f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"

                except Exception as e:

                    print(f"    [-] Upload failed: {e}")

                    try: out_mp4.unlink()

                    except Exception: pass

                    continue



                sha256_hex = compute_sha256(out_mp4)

                size_bytes = out_mp4.stat().st_size

                has_aud = check_has_audio(out_mp4)

                var_id = f"v_{hashlib.md5(f'{u_tid}_{v_url}'.encode()).hexdigest()[:8]}"



                new_var = {

                    "id": var_id,

                    "name": clean_t[:48],

                    "style": "Wallpaper Engine 60fps",

                    "version": "1.0",

                    "url": direct_url,

                    "previewUrl": preview_url,

                    "sizeBytes": size_bytes,

                    "sha256": sha256_hex,

                    "durationSec": 18.0,

                    "author": "Wallpaper Engine / MoeWalls",

                    "codec": "h264",

                    "width": 1280,

                    "height": 720,

                    "fps": 30.0,

                    "hasAudio": has_aud,

                    "notes": f"Switch 720p 30fps H264 | {clean_t[:40]}"

                }



                if not existing_game:

                    new_game_entry = {

                        "titleId": u_tid,

                        "title": disp_name,

                        "publisher": "Nintendo Switch",

                        "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{u_tid}.jpg",

                        "variants": [new_var]

                    }

                    catalog["games"].append(new_game_entry)

                    games_map[u_tid] = new_game_entry

                    existing_game = new_game_entry

                    print(f"    [+] Created NEW Switch Title #{len(catalog['games'])}: {disp_name} [{u_tid}]")

                else:

                    existing_game.setdefault("variants", []).append(new_var)



                try: out_mp4.unlink()

                except Exception: pass



                existing_names.add(clean_t.lower())

                found_new_for_game += 1

                total_added += 1

                print(f"    [+] Successfully added to {disp_name}: '{clean_t}'!")



        if found_new_for_game > 0:

            catalog["updatedAt"] = datetime.now(timezone.utc).isoformat()

            catalog["lastUpdated"] = catalog["updatedAt"]

            catalog["totalGames"] = len(catalog["games"])

            catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog["games"])

            cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")



            # Push to GitHub

            gh_token, _ = GitHubPublisher.get_stored_credentials()

            repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"

            git_env = os.environ.copy()

            git_env["GIT_EDITOR"] = ":"

            if LOCAL_PROXY:

                git_env["http_proxy"] = LOCAL_PROXY

                git_env["https_proxy"] = LOCAL_PROXY

            try:

                subprocess.run(["git", "pull", "--rebase", repo_url, "main"], env=git_env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                subprocess.run(["git", "add", "catalog/data/catalog.json"], check=True)

                subprocess.run(["git", "commit", "-m", f"feat(tophits): add Wallpaper Engine live themes for {disp_name} [skip render] [skip ci]"], env=git_env, check=True)

                subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)

                print(f"    [+] Pushed update for {disp_name} to GitHub main!")

            except Exception as e:

                print(f"    [!] Git push notice: {e}")



    print(f"\n=======================================================")

    print(f"[+] Complete! Total new Wallpaper Engine backgrounds added: {total_added}")

    print(f"[+] Catalog now contains: {catalog['totalGames']} games, {catalog['totalVariants']} variants")





if __name__ == "__main__":

    harvest_all_target_games()

