"""
H3H Top Hits Wallpaper Engine Harvester (Full Extraction).
Harvests cinematic, atmospheric 60fps live wallpapers from the Wallpaper Engine repository (moewalls.com)
specifically for existing iconic Nintendo Switch titles in catalog/data/catalog.json.

Ensures zero duplicates, converts to 720p 30fps H.264 (+faststart),
uploads to Google Drive, updates catalog.json, and pushes directly to GitHub main.
"""

import os
import sys
import re
import json
import time
import html
import hashlib
import subprocess
import urllib.request
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
detect_local_proxy()

STAGE_DIR = Path(r"H:\h3h_stage") if Path(r"H:\h3h_stage").exists() else (PROJECT_ROOT / "tmp" / "h3h_stage")
RAW_DIR = STAGE_DIR / "raw_tophits"
P720_DIR = STAGE_DIR / "720p_tophits"
for d in (STAGE_DIR, RAW_DIR, P720_DIR):
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}

TOP_SWITCH_HITS = [
    # Nintendo Switch 1 Exclusives & Flagships
    ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom", ["tag:tears-of-the-kingdom", "tag:the-legend-of-zelda", "tears of the kingdom", "zelda sky islands"]),
    ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild", ["tag:breath-of-the-wild", "breath of the wild", "zelda botw", "zelda campfire"]),
    ("0100000000010000", "Super Mario Odyssey", ["tag:super-mario", "mario odyssey", "super mario odyssey", "new donk city"]),
    ("010015100B514000", "Super Mario Bros. Wonder", ["super mario bros wonder", "mario wonder", "wonder flower"]),
    ("010093801237C000", "Metroid Dread", ["tag:metroid", "tag:samus-aran", "metroid dread", "samus dread"]),
    ("010012101468C000", "Metroid Prime Remastered", ["tag:metroid", "metroid prime", "samus aran"]),
    ("0100FF500E34A000", "Xenoblade Chronicles Definitive Edition", ["tag:xenoblade-chronicles", "xenoblade shulk", "monado xenoblade"]),
    ("0100E95004038000", "Xenoblade Chronicles 2", ["tag:xenoblade-chronicles-2", "xenoblade pyra", "xenoblade mythra"]),
    ("010074F013262000", "Xenoblade Chronicles 3", ["xenoblade chronicles 3", "xenoblade 3 mio", "xenoblade 3 eunie"]),
    ("01006F8002326000", "Animal Crossing: New Horizons", ["tag:animal-crossing", "animal crossing night", "animal crossing"]),
    ("01000A10041EA000", "Super Smash Bros. Ultimate", ["tag:super-smash-bros", "smash bros ultimate", "super smash bros"]),
    ("01003BC0000A0000", "Kirby and the Forgotten Land", ["tag:kirby", "kirby forgotten land", "kirby"]),
    ("0100C2500FC20000", "Splatoon 3", ["tag:splatoon", "splatoon 3", "splatoon"]),
    ("01001F5010DFA000", "Pokemon Legends: Arceus", ["tag:pokemon", "pokemon arceus", "pokemon dialga"]),
    ("0100A3D008C5C000", "Pokemon Scarlet", ["tag:pokemon", "pokemon koraidon", "pokemon miraidon"]),
    ("0100ABF008968000", "Pokemon Sword", ["tag:pokemon", "pokemon zacian", "pokemon zamazenta"]),
    ("010055D009F78000", "Fire Emblem: Three Houses", ["tag:fire-emblem", "fire emblem edelgard", "fire emblem three houses"]),
    ("0100A6301214E000", "Fire Emblem Engage", ["fire emblem engage", "fire emblem alear"]),
    ("01007300020FA000", "Astral Chain", ["tag:astral-chain", "astral chain"]),
    ("010076F0049A2000", "Bayonetta", ["tag:bayonetta", "bayonetta cereza"]),
    ("010076F0049A4000", "Bayonetta 2", ["tag:bayonetta-2", "bayonetta 2", "bayonetta jeanne"]),
    ("01004A4010FEA000", "Bayonetta 3", ["tag:bayonetta", "bayonetta 3"]),
    ("0100B7C00933A000", "Pikmin 4", ["tag:pikmin", "pikmin 4"]),
    ("0100702008E12000", "Donkey Kong Country: Tropical Freeze", ["tag:donkey-kong", "donkey kong"]),

    # Masterpiece RPGs & Action Hits
    ("01003D100E9C6000", "The Witcher 3: Wild Hunt", ["tag:the-witcher-3-wild-hunt", "tag:the-witcher", "tag:geralt-of-rivia", "witcher 3 scenery"]),
    ("01005CA01580E000", "Persona 5 Royal", ["tag:persona-5", "tag:persona", "persona 5 shibuya", "persona 5 leblanc"]),
    ("010062B01525C000", "Persona 4 Golden", ["tag:persona-4", "persona 4 inaba", "persona 4 golden"]),
    ("0100DCD01525A000", "Persona 3 Portable", ["tag:persona-3", "persona 3 reload", "persona 3 portable"]),
    ("01005C000B2AE000", "NieR:Automata", ["tag:nier-automata", "tag:nier", "nier automata ruins", "nier automata amusement park"]),
    ("01004AB00A260000", "Dark Souls Remastered", ["tag:dark-souls", "tag:dark-souls-iii", "dark souls bonfire", "firelink shrine", "artorias"]),
    ("010028D005A3C000", "The Elder Scrolls V: Skyrim", ["tag:skyrim", "tag:the-elder-scrolls", "skyrim aurora", "skyrim scenery"]),
    ("0100B04011742000", "Monster Hunter Rise", ["tag:monster-hunter", "monster hunter rise", "kamura village"]),
    ("0100A5B00BDC6000", "Final Fantasy VII", ["tag:final-fantasy-vii", "tag:final-fantasy", "cloud strife", "sephiroth"]),
    ("01000B900D8B0000", "DOOM Eternal", ["tag:doom-eternal", "tag:doom", "doom slayer", "doom eternal"]),
    ("0100BC0005C8A000", "DOOM (2016)", ["tag:doom", "doom 2016"]),
    ("01007C000E5B2000", "Devil May Cry 3 Special Edition", ["tag:devil-may-cry", "vergil dmc", "dante dmc"]),
    ("010099A00BC1E000", "Resident Evil 4", ["tag:resident-evil", "resident evil 4", "leon kennedy"]),
    ("01007820196A6000", "Red Dead Redemption", ["tag:red-dead-redemption", "john marston red dead"]),
    ("01003F00163CE000", "Batman: Arkham Trilogy", ["tag:batman-arkham", "batman arkham knight", "batman"]),
    ("010038800C3DC000", "BioShock Remastered", ["tag:bioshock", "rapture bioshock"]),
    ("010065000C3DE000", "BioShock Infinite", ["tag:bioshock", "columbia bioshock", "elizabeth bioshock"]),
    ("0100ABD01785C000", "Portal Companion Collection", ["tag:portal", "portal 2", "glados portal"]),
    ("010042400D600000", "No Man's Sky", ["tag:no-mans-sky", "no mans sky space"]),
    ("0100E5F00E88C000", "Subnautica", ["tag:subnautica", "subnautica underwater", "subnautica"]),
    ("01008DF01290C000", "Ghostrunner", ["tag:ghostrunner", "ghostrunner cyberpunk"]),
    ("01004990172B0000", "Sifu", ["tag:sifu", "sifu kung fu"]),
    ("01004E9013A66000", "NINJA GAIDEN: Master Collection", ["tag:ninja-gaiden", "ryu hayabusa"]),

    # Legendary Indie Hits
    ("010036500ECF2000", "Hollow Knight", ["tag:hollow-knight", "city of tears", "hollow knight dirtmouth"]),
    ("010052300B254000", "Hades", ["tag:hades", "hades zagreus", "house of hades"]),
    ("01008C3005A66000", "Dead Cells", ["tag:dead-cells", "dead cells prisoner"]),
    ("0100698009C6E000", "Blasphemous", ["tag:blasphemous", "penitent one"]),
    ("010086C00AF7C000", "Ori and the Will of the Wisps", ["tag:ori", "ori and the will of the wisps", "niwen forest ori"]),
    ("010079C009494000", "Cuphead", ["tag:cuphead", "cuphead mugman"]),
    ("01002B30028F6000", "Celeste", ["tag:celeste", "madeline celeste"]),
    ("010029600D56A000", "Katana ZERO", ["tag:katana-zero", "katana zero neo"]),
    ("0100307018934000", "SIGNALIS", ["tag:signalis", "elster signalis", "signalis"]),
    ("010093800B8C8000", "Stardew Valley", ["tag:stardew-valley", "stardew valley farm"]),
    ("0100D71004694000", "Minecraft", ["tag:minecraft", "minecraft shaders"]),
    ("0100646009FBE000", "Terraria", ["tag:terraria", "terraria forest"]),
    ("010080B00AD66000", "Undertale", ["tag:undertale", "tag:deltarune", "sans undertale"]),
    ("01003DC0144B6000", "Outer Wilds", ["tag:outer-wilds", "outer wilds campfire"]),
    ("01002E7016C46000", "Cult of the Lamb", ["tag:cult-of-the-lamb", "cult of the lamb"]),
    ("010099F003C4E000", "Darkest Dungeon", ["tag:darkest-dungeon", "darkest dungeon"]),
    ("01005F600B3C2000", "Slay the Spire", ["tag:slay-the-spire", "slay the spire"]),
    ("0100E4A00CBCE000", "Risk of Rain 2", ["tag:risk-of-rain", "risk of rain 2"]),
    ("01009B9013E56000", "Factorio", ["tag:factorio", "factorio base"]),
    ("010075100BFEC000", "Don't Starve Together", ["tag:dont-starve", "dont starve"]),
    ("010063F014170000", "Danganronpa Decadence", ["tag:danganronpa", "monokuma danganronpa"]),
    ("0100B3900C3E2000", "Phoenix Wright: Ace Attorney Trilogy", ["tag:ace-attorney", "phoenix wright court"]),
    ("01007560153F0000", "Five Nights at Freddy's: Security Breach", ["tag:five-nights-at-freddys", "springtrap fnaf", "fnaf security breach"]),
    ("01004060153FA000", "Sonic Frontiers", ["tag:sonic-the-hedgehog", "tag:shadow-the-hedgehog", "sonic frontiers"])
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

def extract_video_url(post_url: str) -> Optional[str]:
    try:
        p_req = urllib.request.Request(post_url, headers=HEADERS)
        p_html = urllib.request.urlopen(p_req, timeout=12).read().decode('utf-8', errors='ignore')
        vids = re.findall(r'<source[^>]*src="([^"]+\.(?:webm|mp4))"', p_html)
        if not vids:
            vids = re.findall(r'href="([^"]+\.(?:webm|mp4))"', p_html)
        if vids:
            v_url = vids[0]
            if v_url.startswith("/"):
                v_url = "https://moewalls.com" + v_url
            return v_url
    except Exception:
        pass
    return None

def is_relevant_to_game(clean_title: str, post_url: str, game_name: str) -> bool:
    comb = (clean_title + " " + post_url).lower()
    # General non-Switch PC junk to ignore
    if any(bad in comb for bad in ["dota", "league of legends", "valorant", "counter strike", "genshin impact", "honkai"]):
        return False
    g_low = game_name.lower()
    if "persona" in g_low and "persona" not in comb:
        return False
    if "witcher" in g_low and not any(k in comb for k in ["witcher", "geralt", "ciri", "yennefer", "triss"]):
        return False
    if "zelda" in g_low and not any(k in comb for k in ["zelda", "link", "hyrule", "ganon"]):
        return False
    if "mario" in g_low and not any(k in comb for k in ["mario", "luigi", "bowser", "peach", "toad"]):
        return False
    if "metroid" in g_low and not any(k in comb for k in ["metroid", "samus"]):
        return False
    if "dark souls" in g_low and not any(k in comb for k in ["dark souls", "bonfire", "artorias", "firelink", "solaire"]):
        return False
    if "hollow knight" in g_low and not any(k in comb for k in ["hollow knight", "hornet", "knight", "hallownest"]):
        return False
    if "skyrim" in g_low and not any(k in comb for k in ["skyrim", "dovahkiin", "dragonborn", "elder scrolls"]):
        return False
    if "nier" in g_low and not any(k in comb for k in ["nier", "2b", "a2", "9s", "yorha"]):
        return False
    if "doom" in g_low and not any(k in comb for k in ["doom", "slayer"]):
        return False
    if "monster hunter" in g_low and not any(k in comb for k in ["monster hunter", "rathalos", "kamura", "felyne", "palico", "magnamalo"]):
        return False
    if "final fantasy" in g_low and not any(k in comb for k in ["final fantasy", "cloud", "sephiroth", "tifa", "aerith", "zack"]):
        return False
    if "resident evil" in g_low and not any(k in comb for k in ["resident evil", "leon", "ada wong", "jill valentine"]):
        return False
    if "devil may cry" in g_low and not any(k in comb for k in ["devil may cry", "dmc", "dante", "vergil", "nero"]):
        return False
    if "batman" in g_low and not any(k in comb for k in ["batman", "joker", "arkham", "gotham"]):
        return False
    if "bioshock" in g_low and not any(k in comb for k in ["bioshock", "rapture", "columbia", "big daddy", "elizabeth"]):
        return False
    if "subnautica" in g_low and not any(k in comb for k in ["subnautica", "leviathan", "cyclops", "seamoth"]):
        return False
    return True


def search_we_wallpapers(query: str, game_name: str, limit: int = 6) -> List[Tuple[str, str]]:
    results = []
    is_tag = query.startswith("tag:")
    if is_tag:
        tag_name = query.split(":", 1)[1].strip()
        url = f"https://moewalls.com/tag/{tag_name}/"
    else:
        url = f"https://moewalls.com/?s={urllib.parse.quote(query)}"

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        page_html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
        items = re.findall(r'<a\s+title="([^"]+)"\s+class="g1-frame"\s+href="([^"]+)"', page_html)
        if not items:
            items = [(t, u) for u, t in re.findall(r'<h[23]\s+class="entry-title[^"]*"><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.DOTALL)]

        for raw_title, post_url in items:
            if not is_tag:
                if "/games/" not in post_url and "/pixel-art/" not in post_url:
                    continue

            clean_t = html.unescape(re.sub('<[^<]+?>', '', raw_title)).replace("Live Wallpaper", "").strip(' -–')
            if not is_relevant_to_game(clean_t, post_url, game_name):
                continue
            vid_url = extract_video_url(post_url)
            if vid_url:
                results.append((vid_url, clean_t))
                if len(results) >= limit:
                    break
    except Exception:
        pass
    return results

def encode_to_switch_mp4(source_url: str, out_mp4: Path) -> bool:
    if out_mp4.exists():
        try:
            out_mp4.unlink()
        except Exception:
            pass
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n",
        "-i", source_url,
        "-t", "24",
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
        str(out_mp4)
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.communicate(timeout=45)
        return proc.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size > 150_000
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

def harvest_top_hits():
    cat_path = PROJECT_ROOT / CATALOG_PATH_STANDARD
    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    games_map = {g["titleId"].upper(): g for g in catalog.get("games", [])}

    log_path = PROJECT_ROOT / "catalog" / "data" / "tophits_we_log.json"
    harvested_urls = set()
    if log_path.exists():
        try:
            harvested_urls = set(json.loads(log_path.read_text(encoding="utf-8")).get("urls", []))
        except Exception:
            pass

    existing_var_names = {}
    for tid, _, _ in TOP_SWITCH_HITS:
        g = games_map.get(tid.upper())
        if g:
            existing_var_names[tid.upper()] = {v.get("name", "").lower() for v in g.get("variants", [])}

    gdrive_token = get_gdrive_token()
    if not gdrive_token:
        print("[-] Error obtaining Google Drive token.")
        return

    total_added = 0
    print("\n========================================================")
    print("  H3H TOP HITS WALLPAPER ENGINE HARVESTER STARTED")
    print("========================================================")

    for tid, game_name, queries in TOP_SWITCH_HITS:
        u_tid = tid.upper()
        if u_tid not in games_map:
            new_game = {
                "titleId": u_tid,
                "title": game_name,
                "publisher": "Nintendo Switch",
                "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{u_tid}.jpg",
                "variants": []
            }
            catalog["games"].append(new_game)
            games_map[u_tid] = new_game
            print(f"  [+] Created NEW Switch 1 title entry: {game_name} [{u_tid}]")

        target_game = games_map[u_tid]
        print(f"\n🎮 [SWITCH HIT] {game_name} (Current backgrounds: {len(target_game.get('variants', []))})")
        game_added = 0

        for q in queries:
            if game_added >= 2:
                break
            print(f"  🔍 Searching WE repo for: '{q}'...")
            items = search_we_wallpapers(q, game_name=game_name, limit=4)
            for mp4_url, clean_title in items:
                if game_added >= 2:
                    break
                if mp4_url in harvested_urls:
                    continue
                if clean_title.lower() in existing_var_names.get(u_tid, set()):
                    continue

                out_mp4 = P720_DIR / f"{u_tid}_hit_{int(time.time())}.mp4"
                print(f"    [*] Found: '{clean_title}'. Downloading and encoding for Switch...")
                if not encode_to_switch_mp4(mp4_url, out_mp4):
                    print(f"    [-] Encoding failed, skipping.")
                    harvested_urls.add(mp4_url)
                    continue

                gdrive_token = get_gdrive_token() or gdrive_token
                print(f"    [*] Uploading {out_mp4.name} ({out_mp4.stat().st_size/1024/1024:.2f} MB) to Google Drive...")
                try:
                    up_res = GoogleDriveClient.upload_file(out_mp4, GDRIVE_FOLDER_ID, gdrive_token)
                    file_id = up_res.get("fileId")
                    direct_url = up_res.get("directUrl") or f"https://drive.google.com/uc?export=download&id={file_id}"
                    preview_url = up_res.get("previewUrl") or f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"
                except Exception as e:
                    print(f"    [-] Upload failed: {e}")
                    continue

                var_id = f"v_{hashlib.md5(f'{u_tid}_{mp4_url}'.encode()).hexdigest()[:8]}"
                sha = compute_sha256(out_mp4)

                new_var = {
                    "id": var_id,
                    "name": clean_title[:45],
                    "style": "Wallpaper Engine 60fps",
                    "version": "1.0",
                    "url": direct_url,
                    "previewUrl": preview_url,
                    "sizeBytes": out_mp4.stat().st_size,
                    "sha256": sha,
                    "durationSec": 28.0,
                    "author": "Wallpaper Engine / MoeWalls",
                    "codec": "h264",
                    "width": 1280,
                    "height": 720,
                    "fps": 30.0,
                    "hasAudio": True,
                    "notes": f"Switch 720p 30fps H264 | {clean_title[:38]}"
                }

                target_game.setdefault("variants", []).append(new_var)
                existing_var_names.setdefault(u_tid, set()).add(clean_title.lower())
                harvested_urls.add(mp4_url)
                game_added += 1
                total_added += 1
                print(f"    [+] Successfully added to {game_name}: '{clean_title}'!")

                try:
                    out_mp4.unlink()
                except Exception:
                    pass

                log_path.write_text(json.dumps({"urls": list(harvested_urls)}, indent=2, ensure_ascii=False), encoding="utf-8")

        # After each game, persist catalog and push
        if game_added > 0:
            catalog["updatedAt"] = datetime.now(timezone.utc).isoformat()
            catalog["lastUpdated"] = catalog["updatedAt"]
            catalog["totalGames"] = len(catalog["games"])
            catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog["games"])
            cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

            gh_token, _ = GitHubPublisher.get_stored_credentials()
            repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
            git_env = os.environ.copy()
            git_env["GIT_EDITOR"] = ":"
            try:
                subprocess.run(["git", "pull", "--rebase", repo_url, "main"], env=git_env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["git", "add", "catalog/data/catalog.json"], check=True)
                subprocess.run(["git", "commit", "-m", f"feat(tophits): add Wallpaper Engine live themes for {game_name} [skip render] [skip ci]"], env=git_env, check=True)
                subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)
                print(f"    [+] Pushed update for {game_name} to GitHub main!")
            except Exception as pe:
                print(f"    [!] Push notice: {pe}")

    print(f"\n[DONE] Added {total_added} top-tier Wallpaper Engine backgrounds to existing hits!")

if __name__ == "__main__":
    harvest_top_hits()
