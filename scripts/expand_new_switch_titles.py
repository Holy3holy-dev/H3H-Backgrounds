"""
H3H Title Library Expansion Pipeline (Strictly 1 New Switch 1 Game per Video Background).
Expands the number of unique Nintendo Switch 1 games in catalog/data/catalog.json by targeting ONLY
titles from switch_titles_db.json that are NOT YET in catalog.json (0 variants).

Triple High-Quality Source Fallback per New Title:
1. Wallpaper Engine Online Repository (moewalls.com/games/) with strict full-title verification.
2. Official Steam Store HD Video Stream (hls_h264 1280x720 midpoint cut via FFmpeg with proxy).
3. SteamGridDB Animated Heroes / Motion Grids.
"""

import os
import sys
import re
import json
import time
import hashlib
import argparse
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

from h3h_studio.core.steamgriddb import SteamGridDBClient
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import GDRIVE_FOLDER_ID, CATALOG_PATH_STANDARD, detect_local_proxy

LOCAL_PROXY = detect_local_proxy()

STAGE_DIR = Path(r"H:\h3h_stage") if Path(r"H:\h3h_stage").exists() else (PROJECT_ROOT / "tmp" / "h3h_stage")
RAW_DIR = STAGE_DIR / "raw_expand"
P720_DIR = STAGE_DIR / "720p_expand"
for d in (STAGE_DIR, RAW_DIR, P720_DIR):
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}

SESSION = requests.Session()
if LOCAL_PROXY:
    SESSION.proxies = {"http": LOCAL_PROXY, "https": LOCAL_PROXY}
SESSION.headers.update(HEADERS)

STOP_WORDS = {"the", "of", "and", "in", "to", "for", "on", "with", "edition", "collection", "deluxe", "remastered", "hd", "switch", "nintendo", "version", "complete", "definitive", "ultimate"}

# Priority curated Switch 1 games that might be missing or need guaranteed clean names
CURATED_MISSING_CANDIDATES = [
    ("01007F600B134000", "Metal Gear Solid: Master Collection Vol. 1", "Metal Gear Solid"),
    ("01004990172B0000", "Sifu", "Sifu"),
    ("01004E9013A66000", "NINJA GAIDEN: Master Collection", "Ninja Gaiden"),
    ("010099F003C4E000", "Darkest Dungeon", "Darkest Dungeon"),
    ("01005F600B3C2000", "Slay the Spire", "Slay the Spire"),
    ("0100E4A00CBCE000", "Risk of Rain 2", "Risk of Rain 2"),
    ("01009B9013E56000", "Factorio", "Factorio"),
    ("010075100BFEC000", "Don't Starve Together", "Don't Starve Together"),
    ("010022A011A62000", "Crysis Remastered", "Crysis Remastered"),
    ("010063F014170000", "Danganronpa: Trigger Happy Havoc", "Danganronpa"),
    ("0100B3900C3E2000", "Phoenix Wright: Ace Attorney Trilogy", "Phoenix Wright: Ace Attorney Trilogy"),
    ("01002F401C950000", "Tsukihime -A piece of blue glass moon-", "Tsukihime"),
    ("01007560153F0000", "Five Nights at Freddy's: Security Breach", "Five Nights at Freddy's: Security Breach"),
    ("010035301980C000", "Poppy Playtime: Chapter 1", "Poppy Playtime"),
    ("01007300020FA000", "Astral Chain", "Astral Chain"),
    ("01008CF01BAAC000", "The Legend of Zelda: Echoes of Wisdom", "The Legend of Zelda: Echoes of Wisdom"),
    ("0100ECD018EBE000", "Paper Mario: The Thousand-Year Door", "Paper Mario: The Thousand-Year Door"),
    ("0100BC0018138000", "Super Mario RPG", "Super Mario RPG"),
    ("0100B7C00933A000", "Pikmin 4", "Pikmin 4"),
    ("0100702008E12000", "Donkey Kong Country: Tropical Freeze", "Donkey Kong Country: Tropical Freeze"),
    ("0100A6301214E000", "Fire Emblem Engage", "Fire Emblem Engage")
]


def extract_clean_english_title(raw_title: str) -> Tuple[str, str]:
    """Extracts clean English title and core title without editions/tags."""
    t = raw_title
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'\+.*$', '', t)
    t = re.sub(r'\bv\d+(\.\d+)*\b', '', t, flags=re.IGNORECASE)
    if ' / ' in t:
        parts = [p.strip() for p in t.split(' / ') if p.strip()]
        latin_parts = [p for p in parts if not re.search(r'[а-яА-ЯёЁ]', p) and re.search(r'[a-zA-Z]', p)]
        t = max(latin_parts, key=len) if latin_parts else parts[-1]
    t = re.sub(r'[а-яА-ЯёЁ]+', '', t)
    t = re.sub(r'\s+', ' ', t).strip(' -–:/|•')
    core = re.sub(r'\b(remastered|deluxe|collection|edition|ultimate|complete|hd|dx|trilogy|vol\.?\s*\d+)\b', '', t, flags=re.IGNORECASE)
    core = re.sub(r'\s+', ' ', core).strip(' -–:/|•')
    return t, (core if len(core) >= 3 else t)


def significant_words(title: str) -> List[str]:
    words = re.findall(r'[a-z0-9]+', title.lower())
    return [w for w in words if len(w) >= 3 and w not in STOP_WORDS]


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


def extract_video_url_from_html(p_html: str) -> Optional[str]:
    m = re.search(r'https://[^\s"\'<>]+?\.mp4', p_html)
    if m:
        return m.group(0)
    m_w = re.search(r'<source\s+src="([^"]+\.(?:webm|mp4))"', p_html, re.IGNORECASE)
    if m_w:
        u = m_w.group(1).strip()
        if u.startswith('/'):
            u = f"https://moewalls.com{u}"
        return u
    return None


def search_we_repo_strict(clean_game_name: str) -> Optional[Tuple[str, str]]:
    """Searches Wallpaper Engine repository and verifies that ALL significant game words appear in the result."""
    sig = significant_words(clean_game_name)
    if not sig or len(clean_game_name) < 4:
        return None

    url = f"https://moewalls.com/?s={urllib.parse.quote(clean_game_name)}"
    try:
        resp = SESSION.get(url, timeout=10)
        html = resp.text
        articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*title="([^"]+)"', html, re.DOTALL)
        if not articles:
            articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
        for page_url, raw_title in articles:
            clean_t = re.sub('<[^<]+?>', '', raw_title).replace("Live Wallpaper", "").strip()
            combined_low = (clean_t + " " + page_url).lower()
            tokens_in_art = set(re.findall(r'[a-z0-9]+', combined_low))
            if all(w in tokens_in_art for w in sig):
                p_resp = SESSION.get(page_url, timeout=10)
                v_url = extract_video_url_from_html(p_resp.text)
                if v_url:
                    return v_url, clean_t
    except Exception:
        pass
    return None


def search_steam_official_trailer(clean_game_name: str) -> Optional[Tuple[str, str]]:
    """Finds exact matching game on Steam Store and returns its official HLS H.264 stream URL."""
    sig = significant_words(clean_game_name)
    if not sig:
        return None
    try:
        s_url = f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(clean_game_name)}&l=english&cc=US"
        r1 = SESSION.get(s_url, timeout=10)
        data = r1.json()
        items = data.get("items", [])
        if not items:
            return None

        target_appid = None
        matched_steam_name = None
        for it in items[:5]:
            st_name = it.get("name", "")
            st_tokens = set(re.findall(r'[a-z0-9]+', st_name.lower()))
            if all(w in st_tokens for w in sig):
                if any(bad in st_tokens for bad in ("soundtrack", "ost", "demo", "artbook", "dlc", "pack")):
                    continue
                if len(st_tokens) > len(sig) * 4 + 4:
                    continue
                target_appid = it.get("id")
                matched_steam_name = st_name
                break

        if not target_appid:
            return None

        d_url = f"https://store.steampowered.com/api/appdetails?appids={target_appid}&l=english"
        r2 = SESSION.get(d_url, timeout=10)
        d_data = r2.json()
        app_info = d_data.get(str(target_appid), {}).get("data", {})
        movies = app_info.get("movies", [])
        if not movies:
            return None

        for mv in movies:
            hls = mv.get("hls_h264")
            mp4_dict = mv.get("mp4") or {}
            direct_mp4 = mp4_dict.get("max") or mp4_dict.get("480")
            stream_url = direct_mp4 or hls
            if stream_url:
                mv_name = mv.get("name", f"{matched_steam_name} Official Cinematic").strip()
                return stream_url, f"{matched_steam_name} — {mv_name}"
    except Exception:
        pass
    return None



def download_steam_fmp4(master_url: str, out_file: Path, max_chunks: int = 5) -> bool:
    try:
        base_url = master_url.rsplit('/', 1)[0] + '/'
        master_text = SESSION.get(master_url, timeout=10).text

        # 1. Video track: prefer 720p (1280x720)
        m_vid = re.search(r'RESOLUTION=1280x720[^\n]*\n([^\n]+)', master_text)
        if not m_vid:
            m_vid = re.search(r'(\bhls_264_\d+_video\.m3u8\b)', master_text)
        if not m_vid:
            return False

        video_m3u8 = m_vid.group(1).strip()
        v_url = base_url + video_m3u8
        v_text = SESSION.get(v_url, timeout=10).text

        m_vinit = re.search(r'URI="([^"]+init[^"]+)"', v_text)
        if not m_vinit:
            return False
        v_init_url = base_url + m_vinit.group(1)
        v_chunks = re.findall(r'(dash_h264/chunk[^\n\r]+)', v_text)[:max_chunks]

        v_bytes = bytearray(SESSION.get(v_init_url, timeout=10).content)
        for vc in v_chunks:
            v_bytes.extend(SESSION.get(base_url + vc, timeout=10).content)

        raw_v = RAW_DIR / f"temp_v_{out_file.stem}.mp4"
        raw_v.write_bytes(v_bytes)

        # 2. Audio track
        m_aud = re.search(r'URI="([^"]+audio\.m3u8)"', master_text)
        has_audio = False
        raw_a = RAW_DIR / f"temp_a_{out_file.stem}.mp4"
        if m_aud:
            audio_m3u8 = m_aud.group(1).strip()
            a_text = SESSION.get(base_url + audio_m3u8, timeout=10).text
            m_ainit = re.search(r'URI="([^"]+init[^"]+)"', a_text)
            if m_ainit:
                a_init_url = base_url + m_ainit.group(1)
                a_chunks = re.findall(r'(dash_h264/chunk[^\n\r]+)', a_text)[:max_chunks]
                a_bytes = bytearray(SESSION.get(a_init_url, timeout=10).content)
                for ac in a_chunks:
                    a_bytes.extend(SESSION.get(base_url + ac, timeout=10).content)
                raw_a.write_bytes(a_bytes)
                has_audio = True

        if out_file.exists():
            try: out_file.unlink()
            except Exception: pass

        if has_audio:
            cmd = ['ffmpeg', '-y', '-i', str(raw_v), '-i', str(raw_a), '-c', 'copy', '-movflags', '+faststart', str(out_file)]
        else:
            cmd = ['ffmpeg', '-y', '-i', str(raw_v), '-c', 'copy', '-movflags', '+faststart', str(out_file)]

        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        for f in (raw_v, raw_a):
            try:
                if f.exists(): f.unlink()
            except Exception: pass

        if res.returncode == 0 and out_file.exists() and out_file.stat().st_size > 200_000:
            return True
    except Exception as e:
        print(f"  [!] fmp4 fetch error: {e}")
    return False


def encode_to_switch_mp4(source_url: str, out_mp4: Path, is_hls_trailer: bool = False) -> bool:
    if out_mp4.exists():
        try:
            out_mp4.unlink()
        except Exception:
            pass

    cmd = ["ffmpeg", "-y", "-nostdin"]
    if LOCAL_PROXY:
        cmd += ["-http_proxy", LOCAL_PROXY]
        
    cmd += [
        "-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n",
        "-i", source_url
    ]
    cmd += [
        "-t", "14",
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
        proc.communicate(timeout=50)
        if proc.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size > 150_000:
            return True
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
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
            capture_output=True, text=True, timeout=8
        )
        return "codec_type=audio" in res.stdout
    except Exception:
        return False


def build_missing_titles_queue(catalog: Dict[str, Any], tried_tids: set) -> List[Tuple[str, str, str, str]]:
    """Returns list of (titleId, display_title, clean_query, core_query) for Switch 1 games NOT in catalog."""
    existing_tids = {g.get("titleId", "").upper() for g in catalog.get("games", []) if len(g.get("variants", [])) > 0}
    queue = []
    seen_tids = set()

    # 1. Curated missing Switch 1 titles first
    for tid, disp, q in CURATED_MISSING_CANDIDATES:
        u_tid = tid.upper()
        if u_tid not in existing_tids and u_tid not in tried_tids and u_tid not in seen_tids:
            queue.append((u_tid, disp, q, q))
            seen_tids.add(u_tid)

    # 2. All missing titles from switch_titles_db.json with clean English names
    db_path = PROJECT_ROOT / "studio" / "h3h_studio" / "data" / "switch_titles_db.json"
    if db_path.exists():
        db_data = json.loads(db_path.read_text(encoding="utf-8"))
        for entry in db_data:
            tid = (entry.get("titleId") or "").upper()
            if not (len(tid) == 16 and tid.startswith("0100")):
                continue
            if tid in existing_tids or tid in tried_tids or tid in seen_tids:
                continue
            raw_t = entry.get("title", "")
            clean_en, core_en = extract_clean_english_title(raw_t)
            sig = significant_words(clean_en)
            if len(clean_en) >= 4 and len(sig) >= 1 and (len(sig) >= 2 or len(sig[0]) >= 5):
                queue.append((tid, clean_en, clean_en, core_en))
                seen_tids.add(tid)

    return queue


def run_expansion_batch(batch_size: int = 5) -> int:
    cat_path = PROJECT_ROOT / CATALOG_PATH_STANDARD
    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    games_map = {g["titleId"].upper(): g for g in catalog.get("games", [])}

    log_path = PROJECT_ROOT / "catalog" / "data" / "title_expansion_log.json"
    if log_path.exists():
        try:
            exp_log = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            exp_log = {"tried_tids": [], "added_tids": []}
    else:
        exp_log = {"tried_tids": [], "added_tids": []}

    tried_set = set(exp_log.get("tried_tids", []))
    queue = build_missing_titles_queue(catalog, tried_set)
    print(f"\n[*] Missing Switch 1 titles in queue: {len(queue)} (Currently in catalog: {len(catalog['games'])} games)")

    gdrive_token = get_gdrive_token()
    if not gdrive_token:
        print("[-] Failed to obtain Google Drive token.")
        return 0

    added_in_batch = 0
    for tid, display_title, clean_q, core_q in queue:
        if added_in_batch >= batch_size:
            break

        tried_set.add(tid)
        exp_log["tried_tids"] = list(tried_set)

        print(f"\n🔍 [NEW TITLE CANDIDATE] {display_title} [{tid}] (Query: '{clean_q}')")
        source_url = None
        var_name = None
        author = None
        style = "Cinematic"
        is_hls = False

        # Source 1: Wallpaper Engine Repository (full name or core name)
        we_hit = search_we_repo_strict(clean_q) or (search_we_repo_strict(core_q) if core_q != clean_q else None)
        if we_hit:
            source_url, var_name = we_hit
            author = "Wallpaper Engine / MoeWalls"
            style = "Wallpaper Engine 60fps"
            print(f"  [+] Found in Wallpaper Engine Repository: {var_name}")
        else:
            # Source 2: Official Steam Store HD Video Stream (clean or core query)
            st_hit = search_steam_official_trailer(clean_q) or (search_steam_official_trailer(core_q) if core_q != clean_q else None)
            if st_hit:
                source_url, var_name = st_hit
                author = "Steam Official HD"
                style = "Official Cinematic"
                is_hls = True
                print(f"  [+] Found Official Steam HD Stream: {var_name}")

        if not source_url:
            log_path.write_text(json.dumps(exp_log, indent=2, ensure_ascii=False), encoding="utf-8")
            continue

        out_mp4 = P720_DIR / f"{tid}_expand.mp4"
        print(f"  [*] Processing 1280x720 30fps Switch MP4 for {display_title}...")
        ok = False
        if is_hls and ".m3u8" in source_url:
            ok = download_steam_fmp4(source_url, out_mp4, max_chunks=5)
        if not ok:
            ok = encode_to_switch_mp4(source_url, out_mp4, is_hls_trailer=is_hls)
        if not ok:
            print(f"  [-] Encoding failed for {display_title}, skipping.")
            log_path.write_text(json.dumps(exp_log, indent=2, ensure_ascii=False), encoding="utf-8")
            continue

        # Refresh token right before upload
        gdrive_token = get_gdrive_token() or gdrive_token
        print(f"  [*] Uploading {out_mp4.name} ({out_mp4.stat().st_size / 1024 / 1024:.2f} MB) to Google Drive...")
        try:
            up_res = GoogleDriveClient.upload_file(out_mp4, GDRIVE_FOLDER_ID, gdrive_token)
            file_id = up_res.get("fileId")
            direct_url = up_res.get("directUrl") or f"https://drive.google.com/uc?export=download&id={file_id}"
            preview_url = up_res.get("previewUrl") or f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"
        except Exception as e:
            print(f"  [-] Upload error: {e}")
            continue

        sha256_hex = compute_sha256(out_mp4)
        size_bytes = out_mp4.stat().st_size
        has_aud = check_has_audio(out_mp4)
        var_id = f"v_{hashlib.md5(f'{tid}_{source_url}'.encode()).hexdigest()[:8]}"

        new_variant = {
            "id": var_id,
            "name": var_name[:48],
            "style": style,
            "version": "1.0",
            "url": direct_url,
            "previewUrl": preview_url,
            "sizeBytes": size_bytes,
            "sha256": sha256_hex,
            "durationSec": 24.0,
            "author": author,
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "hasAudio": has_aud,
            "notes": f"Switch 720p 30fps H264 | {var_name[:40]}"
        }

        if tid not in games_map:
            new_game_entry = {
                "titleId": tid,
                "title": display_title,
                "publisher": "Nintendo Switch",
                "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{tid}.jpg",
                "variants": [new_variant]
            }
            catalog["games"].append(new_game_entry)
            games_map[tid] = new_game_entry
        else:
            games_map[tid].setdefault("variants", []).append(new_variant)

        try:
            out_mp4.unlink()
        except Exception:
            pass

        exp_log.setdefault("added_tids", []).append({"tid": tid, "title": display_title, "source": author})
        log_path.write_text(json.dumps(exp_log, indent=2, ensure_ascii=False), encoding="utf-8")

        added_in_batch += 1
        print(f"  [SUCCESS] Added NEW Switch 1 Game #{len(catalog['games'])}: {display_title} [{tid}] ({added_in_batch}/{batch_size})")

    if added_in_batch > 0:
        catalog["updatedAt"] = datetime.now(timezone.utc).isoformat()
        catalog["lastUpdated"] = catalog["updatedAt"]
        catalog["totalGames"] = len(catalog["games"])
        catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog["games"])
        cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"\n[+] Catalog expanded to {catalog['totalGames']} games ({catalog['totalVariants']} variants)! Pushing to GitHub...")
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
            subprocess.run(["git", "commit", "-m", f"feat(catalog): add {added_in_batch} new Switch 1 game titles ({catalog['totalGames']} total) [skip render] [skip ci]"], env=git_env, check=True)
            subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)
            print(f"[+] Pushed +{added_in_batch} new game titles to GitHub main!")
        except Exception as e:
            print(f"[!] Git push notice: {e}")

    return added_in_batch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=5, help="New game titles per batch")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=15, help="Pause between batches")
    args = parser.parse_args()

    b = 1
    while True:
        print(f"\n================ [TITLE EXPANSION BATCH {b}] ================")
        try:
            run_expansion_batch(batch_size=args.batch)
        except Exception as e:
            print(f"[!] Batch error: {e}")
        if not args.continuous:
            break
        time.sleep(args.interval)
        b += 1


if __name__ == "__main__":
    main()
