"""
H3H Backgrounds & After Dark - Official Community Telegram Uploader Bot.

Enables community members to submit video backgrounds directly via Telegram:
1. Receives video, animation, or ZIP archives (up to 20MB)
2. Automatically extracts Title ID from filename / caption if present (e.g. 0100F2C0115B6000.mp4)
   or matches game name / slang / characters via TitleIdResolver
3. Transcodes to Nintendo Switch standard 720p 30fps H.264 (+faststart)
4. Uploads to Google Drive
5. Registers into catalog.json / catalog_after_dark.json and pushes to GitHub main!
"""

import os
import sys
import re
import json
import time
import uuid
import shutil
import zipfile
import subprocess
import threading
import html
import base64
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler

import telebot
from telebot import types

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from tg_bot.config import (
    BOT_TOKEN,
    GITHUB_TOKEN,
    GITHUB_REPO,
    GITHUB_BRANCH,
    GITHUB_BRANCH_AFTER_DARK,
    GDRIVE_FOLDER_ID,
    GDRIVE_AFTER_DARK_FOLDER_ID,
    GDRIVE_ICONS_FOLDER_ID,
    GDRIVE_REFRESH_TOKEN,
    VERIFIED_REFRESH_TOKEN,
    VERIFIED_CLIENT_ID,
    VERIFIED_CLIENT_SECRET,
    GDRIVE_CLIENT_ID,
    GDRIVE_CLIENT_SECRET,
    ADMIN_IDS,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK,
    TEMP_DIR,
    detect_local_proxy
)
from scripts.title_id_resolver import TitleIdResolver
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher

# Auto-detect local proxy for stable Telegram connectivity
local_proxy = detect_local_proxy()
if local_proxy:
    print(f"[*] Detected local proxy on {local_proxy}, configuring telebot & urllib...")
    from telebot import apihelper
    apihelper.proxy = {'http': local_proxy, 'https': local_proxy}
    os.environ["HTTP_PROXY"] = local_proxy
    os.environ["HTTPS_PROXY"] = local_proxy
    os.environ["http_proxy"] = local_proxy
    os.environ["https_proxy"] = local_proxy

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# --- Cloud Web Health Check Server & Anti-Sleep Self-Pinger (Port 10000 for Render) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'<h1>H3H Backgrounds Telegram Bot is Live (24/7 Anti-Sleep)!</h1>')

    def log_message(self, format, *args):
        pass

def keep_alive_self_pinger():
    """Pings Render external URL every 8 minutes through public edge to prevent 15-min idle spin-down."""
    time.sleep(30)  # Wait for initial boot
    url = (os.getenv("RENDER_EXTERNAL_URL") or os.getenv("RENDER_SERVICE_URL") or "").strip()
    if not url:
        return
    print(f"[*] Render Anti-Sleep Self-Pinger activated for: {url}")
    while True:
        time.sleep(8 * 60)  # Ping every 8 minutes (Render spins down at 15 minutes)
        try:
            req = urllib.request.Request(
                f"{url.rstrip('/')}/",
                headers={"User-Agent": "H3H-AntiSleep-KeepAlive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"[*] Keep-Alive self-ping OK ({resp.status})")
        except Exception as e:
            print(f"[-] Keep-Alive ping notice: {e}")

def start_health_server():
    port = int(os.getenv('PORT', 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f'[*] Health check server listening on 0.0.0.0:{port}')
        server.serve_forever()
    except Exception as e:
        print(f'[*] Health check server notice (safe to ignore locally): {e}')

threading.Thread(target=start_health_server, daemon=True).start()
threading.Thread(target=keep_alive_self_pinger, daemon=True).start()

resolver = TitleIdResolver(str(PROJECT_ROOT / CATALOG_PATH_STANDARD))

# --- User Session Management ---

user_sessions: Dict[int, Dict[str, Any]] = {}
user_preferences: Dict[int, Dict[str, Any]] = {}

def get_user_category_pref(chat_id: int) -> str:
    """Returns user's default category preference ('standard' or 'after_dark')."""
    return user_preferences.get(chat_id, {}).get("category", "standard")

def set_user_category_pref(chat_id: int, category: str):
    """Sets user's default category preference."""
    if chat_id not in user_preferences:
        user_preferences[chat_id] = {}
    user_preferences[chat_id]["category"] = category


def get_session(chat_id: int) -> Dict[str, Any]:
    if chat_id not in user_sessions:
        pref = get_user_category_pref(chat_id)
        user_sessions[chat_id] = {
            "state": "IDLE",
            "temp_vid": None,
            "title_id": None,
            "game_name": None,
            "variant_name": None,
            "suggested_variant": None,
            "batch_items": [],
            "zip_dir": None,
            "category": pref,
            "author": ""
        }
    return user_sessions[chat_id]

def reset_session(chat_id: int):
    sess = get_session(chat_id)
    if sess.get("temp_vid") and Path(sess["temp_vid"]).exists():
        try:
            Path(sess["temp_vid"]).unlink(missing_ok=True)
        except Exception:
            pass
    if sess.get("zip_dir") and Path(sess["zip_dir"]).exists():
        try:
            shutil.rmtree(sess["zip_dir"], ignore_errors=True)
        except Exception:
            pass
    pref = get_user_category_pref(chat_id)
    user_sessions[chat_id] = {
        "state": "IDLE",
        "temp_vid": None,
        "title_id": None,
        "game_name": None,
        "variant_name": None,
        "suggested_variant": None,
        "batch_items": [],
        "zip_dir": None,
        "category": pref,
        "author": "",
        "codec": "h264"
    }

# --- Core Processing Helpers ---

def probe_video_stream(video_path: Path) -> Dict[str, Any]:
    """Inspects video stream with ffprobe for codec, dimensions, and duration."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,duration",
        "-of", "json",
        str(video_path)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        info = json.loads(res.stdout)
        streams = info.get("streams", [])
        if streams:
            return streams[0]
    except Exception:
        pass
    return {}

def is_switch_720p_ready(stream_info: Dict[str, Any]) -> Tuple[bool, str]:
    """Returns (is_ready, codec) if the video is already 1280x720 AVC or HEVC."""
    codec = stream_info.get("codec_name", "").lower()
    try:
        width = int(stream_info.get("width", 0))
        height = int(stream_info.get("height", 0))
    except (ValueError, TypeError):
        width, height = 0, 0

    if width == 1280 and height == 720:
        if codec in ("h264", "avc1"):
            return True, "h264"
        elif codec in ("hevc", "h265", "hvc1"):
            return True, "hevc"
    return False, codec

def passthrough_switch_video(src_vid: Path, out_mp4: Path, out_thumb: Path, is_hevc: bool = False) -> bool:
    """Copies pre-encoded Switch video stream without lossy re-encoding and generates thumbnail."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    cmd_copy = [
        "ffmpeg", "-y", "-nostdin",
        "-i", str(src_vid),
        "-c:v", "copy",
        "-an",
        "-sn",
        "-dn",
        "-movflags", "+faststart"
    ]
    if is_hevc:
        cmd_copy.extend(["-tag:v", "hvc1"])
    cmd_copy.append(str(out_mp4))

    subprocess.run(cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)

    cmd_thumb = [
        "ffmpeg", "-y", "-nostdin",
        "-threads", "1",
        "-ss", "1",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    except Exception:
        pass
    return True

def transcode_to_switch_icon(src_vid: Path, out_mp4: Path, out_thumb: Path, dur_sec: float = 6.0) -> bool:
    """Converts input video to exact 4IFIR video icon standard: 256x256 HEVC, 24fps, silent, +faststart."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    crop_filter = "crop=min(iw\\,ih):min(iw\\,ih),scale=256:256:flags=fast_bilinear"
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-threads", "2",
        "-ss", "0",
        "-t", str(max(1.0, dur_sec)),
        "-i", str(src_vid),
        "-vf", crop_filter,
        "-r", "24",
        "-pix_fmt", "yuv420p",
        "-an",
        "-c:v", "libx265",
        "-preset", "ultrafast",
        "-crf", "26",
        "-tag:v", "hvc1",
        "-movflags", "+faststart",
        str(out_mp4)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=60)

    # Extract 256x256 thumbnail
    cmd_thumb = [
        "ffmpeg", "-y", "-nostdin",
        "-threads", "1",
        "-ss", "0.5",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    except Exception:
        pass
    return out_mp4.exists()

def transcode_to_switch_720p(src_vid: Path, out_mp4: Path, out_thumb: Path, codec: str = "h264") -> bool:
    """Converts input video to Switch 720p 30fps H.264 or HEVC (+faststart) and extracts thumbnail."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    is_hevc = (codec.lower() in ("hevc", "h265"))

    # Optimized for cloud containers (Render CPU quota):
    # -threads 2 prevents CFS quota exhaustion & thread contention
    # flags=fast_bilinear avoids heavy floating-point software scaling
    # -crf 23 eliminates two-pass VBV buffer lookahead overhead
    cmd_ffmpeg = [
        "ffmpeg", "-y", "-nostdin",
        "-threads", "2",
        "-ss", "0",
        "-t", "30",
        "-i", str(src_vid),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "-threads", "2",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-an",
        "-sn",
        "-dn",
        "-movflags", "+faststart"
    ]

    if is_hevc:
        cmd_ffmpeg.extend([
            "-c:v", "libx265",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-x265-params", "fast-intra=1:no-info=1:no-open-gop=1:scenecut=0:pools=2:frame-threads=2",
            "-crf", "26",
            "-tag:v", "hvc1",
            str(out_mp4)
        ])
    else:
        cmd_ffmpeg.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-profile:v", "high",
            "-level", "4.1",
            "-crf", "23",
            "-maxrate", "3500k",
            "-bufsize", "6000k",
            str(out_mp4)
        ])

    try:
        subprocess.run(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=300)
    except subprocess.TimeoutExpired:
        if is_hevc:
            print("[!] HEVC timed out on cloud CPU, auto-falling back to H.264 ultrafast...")
            return transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec="h264")
        raise RuntimeError("Конвертация FFmpeg превысила лимит времени (300с). Ролик слишком длинный или повреждён.")
    except subprocess.CalledProcessError as e:
        if is_hevc:
            return transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec="h264")
        err = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg ошибка: {err[-250:].strip()}")

    cmd_thumb = [
        "ffmpeg", "-y", "-nostdin",
        "-threads", "1",
        "-ss", "1",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
    except Exception:
        pass
    return True

def get_gdrive_auth(category: str = "standard") -> Tuple[Optional[str], Optional[str]]:
    """Returns (access_token, folder_id) for Google Drive operations based on category with robust failover."""
    gdrive_cfg = GoogleDriveHelper.get_stored_config()

    candidates = []
    # Candidate 1: Environment variable
    env_tok = (os.getenv("GDRIVE_REFRESH_TOKEN") or "").strip()
    env_cid = (os.getenv("GDRIVE_CLIENT_ID") or "").strip() or GDRIVE_CLIENT_ID
    env_sec = (os.getenv("GDRIVE_CLIENT_SECRET") or "").strip() or GDRIVE_CLIENT_SECRET
    if env_tok:
        candidates.append((env_tok, env_cid, env_sec))

    # Candidate 2: Verified permanent credentials (guaranteed regardless of env overrides)
    if VERIFIED_REFRESH_TOKEN and (VERIFIED_REFRESH_TOKEN, VERIFIED_CLIENT_ID, VERIFIED_CLIENT_SECRET) not in candidates:
        candidates.append((VERIFIED_REFRESH_TOKEN, VERIFIED_CLIENT_ID, VERIFIED_CLIENT_SECRET))

    # Candidate 3: Config fallback
    if GDRIVE_REFRESH_TOKEN and (GDRIVE_REFRESH_TOKEN, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET) not in candidates:
        candidates.append((GDRIVE_REFRESH_TOKEN, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET))

    # Candidate 3: Stored config
    cfg_tok = (gdrive_cfg.get("refresh_token") or "").strip()
    cfg_cid = (gdrive_cfg.get("client_id") or "").strip() or GDRIVE_CLIENT_ID
    cfg_sec = (gdrive_cfg.get("client_secret") or "").strip() or GDRIVE_CLIENT_SECRET
    if cfg_tok and (cfg_tok, cfg_cid, cfg_sec) not in candidates:
        candidates.append((cfg_tok, cfg_cid, cfg_sec))

    access_tok = None
    for r_tok, c_id, c_sec in candidates:
        try:
            tok = GoogleDriveHelper.refresh_access_token(
                refresh_token=r_tok,
                client_id=c_id,
                client_secret=c_sec
            )
            if tok and tok.startswith("ya29."):
                access_tok = tok
                break
        except Exception:
            continue

    if not access_tok:
        cand = gdrive_cfg.get("token")
        if cand:
            test = GoogleDriveClient.test_connection(cand)
            if test.get("ok"):
                access_tok = cand
    else:
        gdrive_cfg["token"] = access_tok
        try:
            GoogleDriveHelper.save_stored_config(gdrive_cfg)
        except Exception:
            pass

    if category == "after_dark":
        folder_id = (
            os.getenv("GDRIVE_AFTER_DARK_FOLDER_ID")
            or GDRIVE_AFTER_DARK_FOLDER_ID
            or gdrive_cfg.get("after_dark_folder_id")
            or "1SXWjp12pKxPPT6YRMZ7tle8cgZdrKkHk"
        )
    else:
        folder_id = (
            os.getenv("GDRIVE_FOLDER_ID")
            or GDRIVE_FOLDER_ID
            or gdrive_cfg.get("project_folder_id")
            or gdrive_cfg.get("folder_id")
            or "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
        )
    return access_tok, folder_id

def fetch_remote_catalog_json(catalog_rel: Path, branch: str) -> Optional[dict]:
    """Fetches freshest catalog directly from GitHub REST API to ensure atomic updates across branches."""
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if not gh_token:
        gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
    if not gh_token:
        return None
    repo_name = GITHUB_REPO or GitHubPublisher.get_repo_name()
    rel_str = str(catalog_rel).replace("\\", "/")
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Background-Uploader-Bot"
    }
    url = f"https://api.github.com/repos/{repo_name}/contents/{rel_str}?ref={branch}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_bytes = base64.b64decode(data.get("content", ""))
            return json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        return None

def append_variant_to_catalog(
    catalog_rel: Path,
    title_id: str,
    game_name: str,
    variant_name: str,
    author: str,
    category: str,
    direct_url: str,
    preview_url: str,
    file_size: int,
    codec: str = "h264",
    branch: Optional[str] = None,
    has_icon: bool = False,
    icon_url: str = "",
    icon_size_bytes: int = 0,
    icon_codec: str = "hevc"
) -> Dict[str, Any]:
    """Adds a new background variant to catalog JSON file and updates metadata."""
    target_catalog_path = PROJECT_ROOT / catalog_rel
    target_branch = branch or (GITHUB_BRANCH_AFTER_DARK if category == "after_dark" else GITHUB_BRANCH)
    remote_data = fetch_remote_catalog_json(catalog_rel, target_branch)
    if remote_data:
        cat_data = remote_data
    else:
        cat_data = json.loads(target_catalog_path.read_text(encoding="utf-8"))
    games_list = cat_data.get("games", [])

    game_entry = None
    for g in games_list:
        if g.get("titleId", "").upper() == title_id.upper():
            game_entry = g
            break

    if not game_entry:
        game_entry = {
            "titleId": title_id.upper(),
            "title": game_name,
            "publisher": "Community",
            "variants": []
        }
        games_list.append(game_entry)

    var_id = f"var-{uuid.uuid4().hex[:8]}"
    author_tag = f"@{author}" if author and not author.startswith("@") else (author or "@Community")
    style_label = "4IFIR Dynamic Pack" if (direct_url and has_icon) else ("4IFIR Video Icon" if has_icon else ("Community Animated" if category == "standard" else "After Dark (18+)"))
    new_var = {
        "id": var_id,
        "name": variant_name,
        "style": style_label,
        "version": "1.0",
        "url": direct_url,
        "previewUrl": preview_url,
        "sizeBytes": file_size,
        "sha256": "",
        "durationSec": 20.0,
        "author": author_tag,
        "codec": "hevc" if codec.lower() in ("hevc", "h265") else "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "hasIcon": has_icon,
        "notes": f"Submitted via Telegram by {author_tag}"
    }
    if has_icon and icon_url:
        new_var["iconUrl"] = icon_url
        new_var["iconSizeBytes"] = icon_size_bytes
        new_var["iconCodec"] = icon_codec
        new_var["iconWidth"] = 256
        new_var["iconHeight"] = 256
    game_entry["variants"].append(new_var)

    cat_data["totalGames"] = len(games_list)
    cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in games_list)
    cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

    target_catalog_path.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return new_var

def push_catalog_to_github(catalog_rel: Path, commit_msg: str, branch: Optional[str] = None) -> bool:
    """Commits catalog changes and pushes to GitHub branch via GitHub REST API (rock-solid on Render/containers)."""
    push_catalog_to_github.last_error = ""
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if not gh_token:
        gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
    if not gh_token:
        push_catalog_to_github.last_error = "Отсутствует GITHUB_TOKEN"
        print(f"[!] No GitHub token available for pushing to remote.")
        return False

    target_branch = branch or GITHUB_BRANCH or "main"
    repo_name = GITHUB_REPO or GitHubPublisher.get_repo_name()
    catalog_path = PROJECT_ROOT / catalog_rel

    if not catalog_path.exists():
        print(f"[!] Catalog file does not exist: {catalog_path}")
        return False

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Background-Uploader-Bot"
    }

    rel_str = str(catalog_rel).replace("\\", "/")

    # Primary: Push via GitHub REST API (Works everywhere without git binary, user email, or detached HEAD)
    try:
        content_url = f"https://api.github.com/repos/{repo_name}/contents/{rel_str}?ref={target_branch}"
        req_get = urllib.request.Request(content_url, headers=headers)
        file_sha = None
        try:
            with urllib.request.urlopen(req_get, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                file_sha = data.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[!] Warning checking file sha: {e}")

        raw_bytes = catalog_path.read_bytes()
        b64_content = base64.b64encode(raw_bytes).decode("ascii")

        put_payload = {
            "message": commit_msg,
            "content": b64_content,
            "branch": target_branch
        }
        if file_sha:
            put_payload["sha"] = file_sha

        put_url = f"https://api.github.com/repos/{repo_name}/contents/{rel_str}"
        req_put = urllib.request.Request(
            put_url,
            data=json.dumps(put_payload).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="PUT"
        )
        with urllib.request.urlopen(req_put, timeout=20) as resp:
            put_res = json.loads(resp.read().decode("utf-8"))
            commit_sha = put_res.get("commit", {}).get("sha", "")
            print(f"[+] Successfully pushed {rel_str} to GitHub ({target_branch}) via REST API! Commit: {commit_sha[:8]}")

        return True
    except Exception as e:
        print(f"[!] GitHub API push error: {e}")

    # Fallback to local git CLI if API failed
    try:
        repo_url = f"https://x-access-token:{gh_token}@github.com/{repo_name}.git"
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "config", "user.name", "H3H Uploader Bot"], check=False)
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "config", "user.email", "bot@h3h-backgrounds.local"], check=False)
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "add", str(catalog_rel)], check=True)
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "push", repo_url, f"HEAD:{target_branch}"], check=True)
        return True
    except Exception as e2:
        print(f"[!] Git CLI fallback error: {e2}")
        return False

# ----------------- Commands -----------------

@bot.message_handler(commands=["status", "ping"])
def handle_status(message: types.Message):
    access_tok, folder_id = get_gdrive_auth("standard")
    last_err = getattr(GoogleDriveHelper, "last_error", "Нет деталей")
    if access_tok:
        gdrive_status = "✅ Авторизован (токен получен)"
    else:
        gdrive_status = f"❌ Ошибка: {last_err}"
    bot.reply_to(
        message,
        f"🤖 <b>H3H Uploader Bot Status</b>\n\n"
        f"• <b>Версия:</b> v1.3.3-cloud (rev 2)\n"
        f"• <b>Google Drive:</b> {gdrive_status}\n"
        f"• <b>Папка Диска:</b> <code>{folder_id}</code>\n"
        f"• <b>Каталог:</b> {len(resolver.games)} игр в базе\n\n"
        f"<i>Сервер работает 24/7 в облаке. Можете отправлять видеофайлы!</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["start", "help"])
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() in ["старт", "start", "начать", "помощь", "help", "меню", "menu"])
def cmd_start(message: types.Message):
    chat_id = message.chat.id
    u_name = message.from_user.username or message.from_user.first_name or str(chat_id)
    print(f"[*] [TG CMD] /start from @{u_name} (chat_id: {chat_id})")
    reset_session(chat_id)
    text = (
        "👋 <b>Добро пожаловать в H3H Video Backgrounds Uploader!</b>\n\n"
        "С помощью этого бота вы можете добавить свой живой видеофон для Nintendo Switch (4IFIR):\n\n"
        "✨ <b>Что умеет бот:</b>\n"
        "• 📹 Принимать видео и анимации (MP4, WEBM, MOV, GIF)\n"
        "• 📦 Принимать <b>ZIP архивы</b> с несколькими фонами (до 20 МБ)\n"
        "• 🆔 Автоматически считывать <b>Title ID</b> прямо из имени файла (например: <code>0100F2C0115B6000.mp4</code>)\n"
        "• 🧠 Распознавать игру по названию, сленгу и персонажам (Ботва, Ведьмак, 2B, Пайра)\n"
        "• ⚙️ Конвертировать в идеальный Switch-формат <b>720p 30fps H.264</b>\n"
        "• ☁️ Загружать на Google Диск и сразу обновлять каталог на <b>GitHub</b>\n"
        "• 🌸 Поддерживать как обычный каталог, так и коллекцию <b>After Dark (18+)</b>\n\n"
        "🎬 <b>Чтобы начать, просто отправьте видеофайл или ZIP архив!</b>"
    )
    bot.send_message(chat_id, text)

@bot.message_handler(commands=["afterdark", "ad", "nsfw", "ecchi"])
def cmd_afterdark_mode(message: types.Message):
    chat_id = message.chat.id
    set_user_category_pref(chat_id, "after_dark")
    sess = get_session(chat_id)
    sess["category"] = "after_dark"
    bot.reply_to(
        message,
        "🌸 <b>Режим After Dark (18+) АКТИВИРОВАН ПО УМОЛЧАНИЮ!</b>\n\n"
        "Теперь все ваши загружаемые ролики будут автоматически публиковаться в каталог <b>After Dark</b> (ветка <code>after-dark</code>).\n\n"
        "💡 <i>Чтобы переключиться обратно на семейный/основной каталог, отправьте /standard</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["standard", "main"])
def cmd_standard_mode(message: types.Message):
    chat_id = message.chat.id
    set_user_category_pref(chat_id, "standard")
    sess = get_session(chat_id)
    sess["category"] = "standard"
    bot.reply_to(
        message,
        "🎮 <b>Режим Обычного каталога H3H активирован!</b>\n\n"
        "Все загружаемые ролики будут публиковаться в основной каталог на ветку <code>main</code>.\n\n"
        "💡 <i>Чтобы включить After Dark по умолчанию, отправьте /afterdark</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["mode"])
def cmd_show_mode(message: types.Message):
    chat_id = message.chat.id
    pref = get_user_category_pref(chat_id)
    mode_str = "🌸 After Dark (18+)" if pref == "after_dark" else "🎮 Обычный каталог H3H"
    bot.reply_to(
        message,
        f"⚙️ <b>Текущий режим загрузки:</b> <b>{mode_str}</b>\n\n"
        "• Для After Dark по умолчанию: /afterdark\n"
        "• Для обычного каталога: /standard",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["icon", "upload_icon"])
def cmd_upload_icon(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)
    sess = get_session(chat_id)
    sess["upload_mode"] = "icon"
    sess["state"] = "AWAITING_FILE"
    bot.reply_to(
        message,
        "🔲 <b>Загрузка видеоиконки 4IFIR (256x256 HEVC)</b>\n\n"
        "Отправьте квадратное видео или видеоролик для создания видеоиконки.\n"
        "Бот автоматически кадрирует его в квадрат 1:1, сожмет в 256x256 24fps HEVC без звука, "
        "загрузит в облако и привяжет к игре на Nintendo Switch!"
    )

@bot.message_handler(commands=["cancel"])
def cmd_cancel(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)
    bot.send_message(chat_id, "❌ Текущая операция отменена. Отправьте новое видео или архив для начала.")

# ----------------- Video & Archive Reception -----------------

@bot.message_handler(content_types=["video", "document", "animation"])
def handle_file_upload(message: types.Message):
    chat_id = message.chat.id
    u_name = message.from_user.username or message.from_user.first_name or str(chat_id)
    reset_session(chat_id)
    sess = get_session(chat_id)

    fsize = getattr(message.video or message.document or message.animation, 'file_size', 0)
    if fsize and fsize > 20 * 1024 * 1024:
        mb = fsize / (1024 * 1024)
        print(f"[!] [TG REJECT] File from @{u_name} is too large ({mb:.1f} MB > 20 MB)")
        bot.reply_to(
            message,
            f"⚠️ <b>Файл слишком большой ({mb:.1f} МБ)</b>.\n\n"
            "Официальное ограничение Telegram Bot API не позволяет ботам скачивать файлы более <b>20 МБ</b>.\n\n"
            "💡 <i>Пожалуйста, сожмите видео или отправьте фрагмент покороче (10–30 секунд для фона вполне достаточно).</i>"
        )
        return

    file_id = None
    file_name = f"upload_{uuid.uuid4().hex[:8]}.mp4"

    if message.content_type == "video":
        file_id = message.video.file_id
        if message.video.file_name:
            file_name = message.video.file_name
    elif message.content_type == "animation":
        file_id = message.animation.file_id
    elif message.content_type == "document":
        file_id = message.document.file_id
        if message.document.file_name:
            file_name = message.document.file_name

    if not file_id:
        bot.reply_to(message, "⚠️ Не удалось прочитать файл. Пожалуйста, отправьте видеоролик или ZIP архив.")
        return

    ext = Path(file_name).suffix.lower()
    if message.content_type == "document" and message.document and message.document.mime_type:
        mime = message.document.mime_type.lower()
        if mime.startswith("video/") and ext not in [".mp4", ".webm", ".mov", ".mkv", ".gif"]:
            ext = ".mp4"
            file_name = file_name + ".mp4"

    # Route ZIP archives to batch handler
    if ext == ".zip":
        handle_zip_upload(message, file_id, file_name)
        return

    # Check video extension
    valid_vid_exts = [".mp4", ".webm", ".mov", ".mkv", ".gif"]
    if ext not in valid_vid_exts:
        bot.reply_to(message, "⚠️ Поддерживаются форматы: MP4, WEBM, MOV, MKV, GIF, а также ZIP архивы.")
        return

    print(f"[*] [TG UPLOAD] Receiving {file_name} from @{u_name} ({chat_id})...")

    bot.send_chat_action(chat_id, "typing")
    status_msg = bot.reply_to(message, "⏳ Скачиваю видеофайл из Telegram...")

    try:
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
    except telebot.apihelper.ApiTelegramException as e:
        if "file is too big" in str(e).lower():
            bot.edit_message_text(
                "⚠️ <b>Файл слишком большой (> 20 МБ)</b>.\n\n"
                "Официальное ограничение Telegram Bot API не позволяет ботам скачивать файлы более 20 МБ.\n"
                "💡 <i>Рекомендация: сожмите ролик или отправьте более короткий фрагмент.</i>",
                chat_id=chat_id,
                message_id=status_msg.message_id
            )
            return
        bot.edit_message_text(f"❌ Ошибка Telegram API: {e}", chat_id=chat_id, message_id=status_msg.message_id)
        return

    try:
        target_path = PROJECT_ROOT / TEMP_DIR / f"{chat_id}_{file_name}"
        target_path.write_bytes(downloaded)

        sess["temp_vid"] = str(target_path)
        sess["state"] = "AWAITING_CATEGORY"
        sess["author"] = message.from_user.username or message.from_user.first_name or "Community"

        # Detect upload mode (cover, icon, both)
        combined_meta = f"{message.caption or ''} {file_name}".lower()
        if re.search(r'(?i)(#icon|#иконка|icon|иконка|256x256)', combined_meta) or sess.get("upload_mode") == "icon":
            sess["upload_mode"] = "icon"
        elif re.search(r'(?i)(#pack|#пак|pack|fullpack|полный)', combined_meta):
            sess["upload_mode"] = "both"
        else:
            sess["upload_mode"] = sess.get("upload_mode", "both")

        # Probe video format for direct Switch passthrough
        v_info = probe_video_stream(target_path)
        is_ready, det_codec = is_switch_720p_ready(v_info)
        if is_ready:
            sess["is_preencoded"] = True
            sess["codec"] = det_codec
            sess["direct_passthrough"] = True
        else:
            sess["is_preencoded"] = False
            sess["direct_passthrough"] = False

        # Check for Title ID in filename or caption
        detected_tid = TitleIdResolver.extract_title_id(file_name)
        if not detected_tid and message.caption:
            detected_tid = TitleIdResolver.extract_title_id(message.caption)

        detected_game = None
        suggested_variant = None
        if detected_tid:
            detected_game = resolver.resolve_by_title_id(detected_tid)
            if not detected_game and message.caption:
                cap_no_tid = re.sub(r'(?i)[0-9a-f]{16}', '', message.caption).strip(" _-")
                cap_match = re.match(r'^(.*?)\s*[\(\[]([^\)\]]+)[\)\]]\s*$', cap_no_tid)
                if cap_match:
                    detected_game = cap_match.group(1).strip()
                    suggested_variant = cap_match.group(2).strip()
                elif cap_no_tid:
                    detected_game = cap_no_tid
            if not detected_game:
                detected_game = f"Игра ({detected_tid})"
            sess["title_id"] = detected_tid
            sess["game_name"] = detected_game

            if not suggested_variant:
                stem = Path(file_name).stem
                clean_stem = re.sub(r'(?i)[0-9a-f]{16}', '', stem).strip(" _-").replace('_', ' ').replace('-', ' ').title()
                if len(clean_stem) >= 2:
                    suggested_variant = clean_stem
            if suggested_variant:
                sess["suggested_variant"] = suggested_variant

        # Auto-detect After Dark intent from caption, filename, or user preference
        user_pref = get_user_category_pref(chat_id)
        combined_text = f"{message.caption or ''} {file_name}".lower()
        has_ad_keyword = bool(re.search(r'(?i)(after[-_\s]*dark|18\+|nsfw|ecchi|hentai|хентай|эччи|афтер[-_\s]*дарк)', combined_text))

        is_after_dark = has_ad_keyword or (user_pref == "after_dark")
        if is_after_dark:
            sess["category"] = "after_dark"

        bot.delete_message(chat_id, status_msg.message_id)

        # If After Dark is indicated by default:
        if is_after_dark:
            if detected_tid:
                sess["state"] = "AWAITING_VARIANT_NAME"
                suggested = sess.get("suggested_variant")
                markup = types.InlineKeyboardMarkup(row_width=1)
                if suggested:
                    markup.add(types.InlineKeyboardButton(f"✅ Назвать: «{suggested}»", callback_data="var:use_suggested"))
                else:
                    markup.add(types.InlineKeyboardButton("✅ Назвать: «Dynamic Theme»", callback_data="var:use_default"))
                markup.add(types.InlineKeyboardButton("✏️ Ввести другое название", callback_data="var:custom"))
                markup.add(types.InlineKeyboardButton("🔄 Сменить каталог на Обычный H3H", callback_data="cat:standard"))

                msg_lines = [
                    "🌸 <b>Видео принято в After Dark (18+) по умолчанию!</b>\n",
                    f"🎯 <b>Определён Title ID:</b> <code>{detected_tid}</code>",
                    f"🎮 <b>Игра:</b> <b>{detected_game}</b>"
                ]
                if sess.get("is_preencoded"):
                    c_tag = "HEVC (H.265)" if sess.get("codec") == "hevc" else "H.264 (AVC)"
                    msg_lines.append(f"⚡ <b>Формат Switch:</b> <code>1280x720 {c_tag}</code> (прямая запись без потерь!)")
                msg_lines.append("\n<b>Шаг 1 из 2:</b> Как назвать этот видеофон?")
                if suggested:
                    msg_lines.append(f"<i>(Предложено из имени файла: «{suggested}»)</i>")

                bot.send_message(chat_id, "\n".join(msg_lines), reply_markup=markup)
                return
            else:
                sess["state"] = "AWAITING_GAME_NAME"
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("✨ Свободный фон (для любой игры)", callback_data="game:free"),
                    types.InlineKeyboardButton("🔄 Сменить каталог на Обычный H3H", callback_data="cat:standard")
                )
                bot.send_message(
                    chat_id,
                    "🌸 <b>Видео принято в After Dark (18+) по умолчанию!</b>\n\n"
                    "<b>Шаг 1 из 3:</b> К какой игре привязать этот фон?\n\n"
                    "Напишите <b>название игры</b> или отправьте 16-значный <b>Title ID</b>.\n"
                    "<i>(Или нажмите кнопку ниже для свободного фона)</i>",
                    reply_markup=markup
                )
                return

        # Default standard flow
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎮 Обычный каталог H3H", callback_data="cat:standard"),
            types.InlineKeyboardButton("🌸 After Dark (18+ / Эччи)", callback_data="cat:after_dark")
        )

        msg_lines = ["✅ <b>Видео получено!</b>\n"]
        if detected_tid:
            msg_lines.append(f"🎯 <b>Определён Title ID:</b> <code>{detected_tid}</code>")
            msg_lines.append(f"🎮 <b>Игра:</b> {detected_game}")
        if sess.get("is_preencoded"):
            c_tag = "HEVC (H.265)" if sess.get("codec") == "hevc" else "H.264 (AVC)"
            msg_lines.append(f"⚡ <b>Формат Switch распознан:</b> <code>1280x720 {c_tag}</code> (доступна прямая запись без перекодирования!)")
        msg_lines.append("\n<b>Шаг 1 из 3:</b> В какой каталог добавить этот видеофон?")

        bot.send_message(chat_id, "\n".join(msg_lines), reply_markup=markup)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при загрузке: {e}")
        reset_session(chat_id)

# ----------------- ZIP Archive Batch Handler -----------------

def handle_zip_upload(message: types.Message, file_id: str, file_name: str):
    chat_id = message.chat.id
    sess = get_session(chat_id)
    sess["author"] = message.from_user.username or message.from_user.first_name or "Community"

    status_msg = bot.reply_to(message, "⏳ <b>Скачиваю и распаковываю ZIP архив...</b>")

    try:
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
    except telebot.apihelper.ApiTelegramException as e:
        if "file is too big" in str(e).lower():
            bot.edit_message_text(
                "⚠️ <b>Файл архива слишком большой (> 20 МБ)</b>.\n\n"
                "Официальное ограничение Telegram Bot API для ботов — 20 МБ на файл.\n"
                "💡 <i>Рекомендация: сожмите видеоролики в архиве или отправляйте файлы напрямую.</i>",
                chat_id=chat_id,
                message_id=status_msg.message_id
            )
            return
        bot.edit_message_text(f"❌ Ошибка при скачивании архива: {e}", chat_id=chat_id, message_id=status_msg.message_id)
        return

    zip_dir = PROJECT_ROOT / TEMP_DIR / f"zip_{chat_id}_{uuid.uuid4().hex[:6]}"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_file = zip_dir / file_name
    zip_file.write_bytes(downloaded)

    try:
        with zipfile.ZipFile(zip_file, 'r') as zf:
            zf.extractall(zip_dir)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка распаковки ZIP: {e}", chat_id=chat_id, message_id=status_msg.message_id)
        return

    valid_vid_exts = {".mp4", ".webm", ".mov", ".mkv", ".gif"}
    extracted_videos = []
    for p in zip_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in valid_vid_exts and not p.name.startswith("."):
            extracted_videos.append(p)

    if not extracted_videos:
        bot.edit_message_text(
            "⚠️ <b>В архиве не найдено видеофайлов</b> (поддерживаются MP4, WEBM, MOV, MKV, GIF).",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )
        return

    batch_items = []
    for vid_path in extracted_videos:
        fname = vid_path.name
        stem = vid_path.stem
        tid = TitleIdResolver.extract_title_id(fname)
        game_name = None
        var_name = ""

        if tid:
            game_name = resolver.resolve_by_title_id(tid) or f"Игра ({tid})"
            var_name = re.sub(r'(?i)[0-9a-f]{16}', '', stem).strip(" _-").replace('_', ' ').replace('-', ' ').title()
        else:
            resolved = resolver.resolve(stem)
            if resolved:
                tid, game_name = resolved
                var_name = "Dynamic Theme"
            else:
                tid = "0000000000000000"
                game_name = "★ Коллекция (Свободный выбор)"
                var_name = stem.replace('_', ' ').title()

        if not var_name:
            var_name = "Community Theme"

        batch_items.append({
            "path": str(vid_path),
            "file_name": fname,
            "title_id": tid,
            "game_name": game_name,
            "variant_name": var_name
        })

    sess["batch_items"] = batch_items
    sess["zip_dir"] = str(zip_dir)

    lines = [f"📦 <b>В архиве обнаружено {len(batch_items)} видеофонов:</b>\n"]
    for i, item in enumerate(batch_items[:8], 1):
        lines.append(f"{i}. 🎮 <b>{item['game_name']}</b> (<code>{item['title_id']}</code>)\n   🎬 <i>{item['variant_name']}</i>")
    if len(batch_items) > 8:
        lines.append(f"... и ещё {len(batch_items) - 8} видео.")

    lines.append("\n<b>Выберите категорию и кодек для пакета:</b>")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎮 В Обычный каталог (H.264)", callback_data="batch_cat:standard:h264"),
        types.InlineKeyboardButton("⚡ В Обычный каталог (HEVC / H.265)", callback_data="batch_cat:standard:hevc"),
        types.InlineKeyboardButton("🌸 В After Dark (18+) (H.264)", callback_data="batch_cat:after_dark:h264"),
        types.InlineKeyboardButton("🔥 В After Dark (18+) (HEVC / H.265)", callback_data="batch_cat:after_dark:hevc"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="batch_cat:cancel")
    )

    bot.edit_message_text(
        "\n".join(lines),
        chat_id=chat_id,
        message_id=status_msg.message_id,
        reply_markup=markup
    )

# ----------------- Category Callbacks -----------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat:"))
def handle_category_choice(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    choice = call.data.split(":")[1]

    sess["category"] = choice
    cat_title = "Обычный каталог" if choice == "standard" else "🌸 After Dark (18+)"

    # If Title ID was already auto-detected from filename or caption!
    if sess.get("title_id"):
        sess["state"] = "AWAITING_VARIANT_NAME"
        suggested = sess.get("suggested_variant")
        markup = types.InlineKeyboardMarkup(row_width=1)
        if suggested:
            markup.add(types.InlineKeyboardButton(f"✅ Назвать: «{suggested}»", callback_data="var:use_suggested"))
        else:
            markup.add(types.InlineKeyboardButton("✅ Назвать: «Dynamic Theme»", callback_data="var:use_default"))
        markup.add(types.InlineKeyboardButton("✏️ Ввести другое название", callback_data="var:custom"))

        bot.edit_message_text(
            f"Выбрана категория: <b>{cat_title}</b>\n\n"
            f"🎯 <b>Title ID определён:</b> <code>{sess['title_id']}</code>\n"
            f"🎮 <b>Игра:</b> <b>{sess['game_name']}</b>\n\n"
            f"<b>Шаг 2 из 3:</b> Как назвать этот видеофон?"
            + (f"\n<i>(Предложено из имени файла: «{suggested}»)</i>" if suggested else ""),
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    # If Title ID not yet detected, ask for game name / Title ID
    sess["state"] = "AWAITING_GAME_NAME"
    bot.edit_message_text(
        f"Выбрана категория: <b>{cat_title}</b>\n\n"
        "<b>Шаг 2 из 4:</b> К какой игре привязать этот фон?\n\n"
        "Напишите <b>название игры</b> (например, <code>Zelda Tears of the Kingdom</code>, <code>Nier Automata</code>, <code>Mario Odyssey</code>, <code>Witcher 3</code>)\n"
        "Или отправьте сразу 16-значный <b>Title ID</b> (например, <code>0100F2C0115B6000</code>).\n\n"
        "<i>(Если это свободный арт для After Dark, напишите «Свободный» или нажмите кнопку ниже)</i>",
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("✨ Свободный фон (для любой игры)", callback_data="game:free")
        ) if choice == "after_dark" else None
    )

# ----------------- Variant Choice Callbacks -----------------

@bot.callback_query_handler(func=lambda call: call.data in ["var:use_suggested", "var:use_default", "var:custom"])
def handle_variant_choice(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)

    if call.data == "var:custom":
        sess["state"] = "AWAITING_VARIANT_NAME"
        bot.edit_message_text(
            "✏️ Напишите желаемое название для видеофона в ответном сообщении:\n<i>(Например: Main Theme, Cinematic Action, Title Screen)</i>",
            chat_id=chat_id,
            message_id=call.message.message_id
        )
        return

    if call.data == "var:use_suggested":
        sess["variant_name"] = sess.get("suggested_variant", "Dynamic Theme")
    else:
        sess["variant_name"] = "Dynamic Theme"

    sess["state"] = "AWAITING_CONFIRMATION"
    prompt_publish_confirmation(chat_id, call.message.message_id)

# ----------------- Free Wallpaper Callback -----------------

@bot.callback_query_handler(func=lambda call: call.data == "game:free")
def handle_free_game(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    sess["title_id"] = "0000000000000000"
    sess["game_name"] = "★ Коллекция After Dark (Свободный выбор)"
    sess["state"] = "AWAITING_VARIANT_NAME"

    bot.edit_message_text(
        "Выбран <b>Свободный фон</b> (пользователи на Switch смогут привязать его к любой установленной игре!).\n\n"
        "<b>Шаг 3 из 4:</b> Как назвать этот видеофон?\n"
        "<i>(Например: 2B Cyberpunk Night, Bowsette Flame, Purah Lab)</i>",
        chat_id=chat_id,
        message_id=call.message.message_id
    )

# ----------------- Text Handlers (Game, Title ID, Variant) -----------------

@bot.message_handler(func=lambda m: get_session(m.chat.id)["state"] == "AWAITING_CATEGORY")
def handle_category_text_fallback(message: types.Message):
    chat_id = message.chat.id
    sess = get_session(chat_id)
    text = (message.text or "").strip().lower()

    if any(k in text for k in ["after", "dark", "афтер", "дарк", "18+", "nsfw", "ecchi", "hentai", "хентай", "эччи"]):
        sess["category"] = "after_dark"
        bot.reply_to(message, "🌸 Выбран каталог: <b>After Dark (18+)</b>")
    elif any(k in text for k in ["обычный", "стандарт", "main", "standard"]):
        sess["category"] = "standard"
        bot.reply_to(message, "🎮 Выбран каталог: <b>Обычный H3H</b>")
    else:
        # User typed game name or Title ID directly!
        detected_tid = TitleIdResolver.extract_title_id(text)
        if detected_tid:
            sess["title_id"] = detected_tid
            sess["game_name"] = resolver.resolve_by_title_id(detected_tid) or f"Игра ({detected_tid})"
            sess["state"] = "AWAITING_VARIANT_NAME"
            bot.send_message(
                chat_id,
                f"✅ Title ID распознан: <code>{detected_tid}</code>\n🎮 Игра: <b>{sess['game_name']}</b>\n\n"
                "Как назвать этот видеофон?\n<i>(Например: Main Theme, Cinematic Action)</i>"
            )
            return
        matches = resolver.resolve_multiple(text, limit=3)
        if matches:
            sess["title_id"] = matches[0][0]
            sess["game_name"] = matches[0][1]
            sess["state"] = "AWAITING_VARIANT_NAME"
            bot.send_message(
                chat_id,
                f"✅ Игра определена: <b>{matches[0][1]}</b> (<code>{matches[0][0]}</code>)\n\n"
                "Как назвать этот видеофон?\n<i>(Например: Main Theme, Cinematic Action)</i>"
            )
            return

    # If title id already detected earlier
    if sess.get("title_id"):
        sess["state"] = "AWAITING_VARIANT_NAME"
        bot.send_message(
            chat_id,
            f"🎯 <b>Title ID:</b> <code>{sess['title_id']}</code>\n"
            f"🎮 <b>Игра:</b> {sess['game_name']}\n\n"
            "Как назвать этот видеофон?\n<i>(Например: Main Theme, Cinematic Action)</i>"
        )
    else:
        sess["state"] = "AWAITING_GAME_NAME"
        bot.send_message(
            chat_id,
            "К какой игре привязать этот фон?\n\n"
            "Напишите <b>название игры</b> или отправьте 16-значный <b>Title ID</b>."
        )

@bot.message_handler(func=lambda m: get_session(m.chat.id)["state"] == "AWAITING_GAME_NAME")
def handle_game_name(message: types.Message):
    chat_id = message.chat.id
    sess = get_session(chat_id)
    raw_text = message.text.strip()

    # Direct 16-hex Title ID check
    detected_tid = TitleIdResolver.extract_title_id(raw_text)
    if detected_tid:
        sess["title_id"] = detected_tid
        sess["game_name"] = resolver.resolve_by_title_id(detected_tid) or f"Игра ({detected_tid})"
        sess["state"] = "AWAITING_VARIANT_NAME"
        bot.send_message(
            chat_id,
            f"✅ <b>Title ID распознан:</b> <code>{sess['title_id']}</code>\n"
            f"🎮 <b>Игра:</b> <b>{sess['game_name']}</b>\n\n"
            "<b>Шаг 3 из 4:</b> Как назвать этот вариант видеофона?\n"
            "<i>(Например: Dynamic Action, Title Screen, Anime Remix)</i>"
        )
        return

    # Fuzzy Multiple Matcher (Typo & Slang tolerant)
    matches = resolver.resolve_multiple(raw_text, limit=4)
    if matches:
        sess["candidates"] = {tid: name for tid, name, _ in matches}
        markup = types.InlineKeyboardMarkup(row_width=1)
        for tid, name, score in matches:
            short_name = (name[:38] + "..") if len(name) > 40 else name
            markup.add(types.InlineKeyboardButton(f"🎮 {short_name}", callback_data=f"pick_game:{tid}"))

        markup.add(types.InlineKeyboardButton("🔍 Ввести другое название или Title ID", callback_data="pick_game:retry"))

        bot.send_message(
            chat_id,
            f"🎯 <b>По запросу '{raw_text}' найдены совпадения:</b>\n\n"
            "Выберите нужную игру из списка ниже:",
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id,
            f"⚠️ Не удалось найти игру по запросу <i>'{raw_text}'</i>.\n\n"
            "Попробуйте написать другое ключевое слово (например: <code>Zelda</code>, <code>Mario</code>, <code>Witcher</code>, <code>Nier</code>) "
            "или отправьте точный 16-значный <b>Title ID</b> (например, <code>0100F2C0115B6000</code>)."
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("pick_game:"))
def handle_pick_game(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    choice = call.data.split(":")[1]

    if choice == "retry":
        bot.edit_message_text(
            "Пожалуйста, отправьте название игры или 16-значный <b>Title ID</b> сообщением:",
            chat_id=chat_id,
            message_id=call.message.message_id
        )
        return

    candidates = sess.get("candidates", {})
    game_name = candidates.get(choice, f"Игра ({choice})")
    sess["title_id"] = choice
    sess["game_name"] = game_name
    sess["state"] = "AWAITING_VARIANT_NAME"

    bot.edit_message_text(
        f"✅ Игра выбрана: <b>{game_name}</b>\n"
        f"🆔 Title ID: <code>{choice}</code>\n\n"
        "<b>Шаг 3 из 4:</b> Как назвать этот видеофон?\n"
        "<i>(Например: Main Theme, Cinematic Gameplay, Anime Cutscene)</i>",
        chat_id=chat_id,
        message_id=call.message.message_id
    )

@bot.message_handler(func=lambda m: get_session(m.chat.id)["state"] == "AWAITING_VARIANT_NAME")
def handle_variant_name_input(message: types.Message):
    chat_id = message.chat.id
    sess = get_session(chat_id)
    var_name = message.text.strip()
    if not var_name:
        var_name = "Custom Variant"

    sess["variant_name"] = var_name
    sess["state"] = "AWAITING_CONFIRMATION"
    prompt_publish_confirmation(chat_id)

def prompt_publish_confirmation(chat_id: int, edit_msg_id: Optional[int] = None):
    sess = get_session(chat_id)
    cat_label = "Обычный каталог" if sess["category"] == "standard" else "🌸 After Dark (18+)"
    codec = sess.get("codec", "h264")
    codec_label = "🎬 H.264 (Стандарт)" if codec == "h264" else "⚡ HEVC / H.265 (High-Efficiency)"
    is_pre = sess.get("is_preencoded", False)
    direct_pt = sess.get("direct_passthrough", False)

    markup = types.InlineKeyboardMarkup(row_width=1)

    if is_pre:
        pt_btn = "🔄 Принудительно перекодировать" if direct_pt else "🚀 Включить прямую запись без потерь"
        markup.add(types.InlineKeyboardButton(pt_btn, callback_data="toggle_passthrough"))

    toggle_target = "hevc" if codec == "h264" else "h264"
    toggle_text = "⚡ Переключить на HEVC (H.265)" if codec == "h264" else "🎬 Переключить на H.264 (AVC)"

    upload_mode = sess.get("upload_mode", "both")
    if upload_mode == "both":
        mode_btn_text = "✨ Формат: Полный пак (Фон + Иконка)"
        next_mode = "cover"
    elif upload_mode == "cover":
        mode_btn_text = "🎬 Формат: Только видеофон (720p)"
        next_mode = "icon"
    else:
        mode_btn_text = "🔲 Формат: Только видеоиконка (256x256)"
        next_mode = "both"

    markup.add(types.InlineKeyboardButton(mode_btn_text, callback_data=f"mode:{next_mode}"))
    markup.add(types.InlineKeyboardButton(toggle_text, callback_data=f"codec:{toggle_target}"))
    markup.row(
        types.InlineKeyboardButton("🚀 Запустить публикацию!", callback_data="publish:yes"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="publish:cancel")
    )

    if direct_pt:
        mode_desc = f"🚀 <b>Режим:</b> <code>Прямая запись потока (-c copy, без перекодирования)</code>\n"
        mode_hint = "💡 <i>Видео уже в точном стандарте Switch 720p — качество сохраняется на 100%, без артефактов перекодирования!</i>\n\n"
    else:
        mode_desc = f"⚙️ <b>Режим:</b> <code>Конвертация FFmpeg ({codec_label} 720p 30fps)</code>\n"
        mode_hint = "💡 <i>HEVC (H.265) даёт меньший вес при том же качестве и аппаратно декодируется NVDEC на Switch. H.264 даёт максимальную совместимость.</i>\n\n"

    text = (
        "📋 <b>Проверьте данные перед публикацией:</b>\n\n"
        f"📁 <b>Категория:</b> {cat_label}\n"
        f"🎮 <b>Игра:</b> {sess['game_name']}\n"
        f"🆔 <b>Title ID:</b> <code>{sess['title_id']}</code>\n"
        f"🎬 <b>Название фона:</b> {sess['variant_name']}\n"
        f"⚙️ <b>Кодек:</b> <code>{codec_label}</code>\n"
        f"{mode_desc}"
        f"👤 <b>Автор:</b> @{sess['author']}\n\n"
        f"{mode_hint}"
        "Нажмите <b>Запустить публикацию</b>, чтобы отправить фон на Google Диск и добавить на GitHub!"
    )

    if edit_msg_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=edit_msg_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("mode:"))
def handle_mode_toggle(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    new_mode = call.data.split(":")[1]
    sess["upload_mode"] = new_mode
    mode_labels = {
        "both": "✨ Полный пак (Фон + Иконка)",
        "cover": "🎬 Только видеофон (720p)",
        "icon": "🔲 Только видеоиконка 4IFIR"
    }
    try:
        bot.answer_callback_query(call.id, f"Выбран режим: {mode_labels.get(new_mode, new_mode)}")
    except Exception:
        pass
    prompt_publish_confirmation(chat_id, edit_msg_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "toggle_passthrough")
def handle_toggle_passthrough(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    cur = sess.get("direct_passthrough", False)
    sess["direct_passthrough"] = not cur
    try:
        status = "Прямая запись (-c copy)" if sess["direct_passthrough"] else "Перекодирование FFmpeg"
        bot.answer_callback_query(call.id, f"Режим: {status}")
    except Exception:
        pass
    prompt_publish_confirmation(chat_id, edit_msg_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("codec:"))
def handle_codec_toggle(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    new_codec = call.data.split(":")[1]
    sess["codec"] = new_codec
    try:
        label = "HEVC (H.265)" if new_codec == "hevc" else "H.264 (AVC)"
        bot.answer_callback_query(call.id, f"Выбран кодек: {label}")
    except Exception:
        pass
    prompt_publish_confirmation(chat_id, edit_msg_id=call.message.message_id)

# Concurrency limiters for multi-user community stability
TRANSCODE_SEMAPHORE = threading.Semaphore(1)  # Process FFmpeg sequentially to avoid cloud CPU starvation
CATALOG_LOCK = threading.Lock()               # Synchronize catalog modification & GitHub pushing

# ----------------- Single Video Publishing -----------------

def _do_single_publish_async(chat_id: int, message_id: int, sess: dict):
    out_mp4 = None
    out_thumb = None
    out_icon_mp4 = None
    out_icon_thumb = None
    try:
        temp_vid_path = sess.get("temp_vid")
        if not temp_vid_path or not Path(temp_vid_path).exists():
            bot.edit_message_text(
                "⚠️ <b>Сессия устарела или файл не найден на сервере.</b>\n\n"
                "Пожалуйста, отправьте видеофайл заново сообщением.",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )
            reset_session(chat_id)
            return

        codec = sess.get("codec", "h264")
        codec_name = "HEVC (H.265)" if codec == "hevc" else "H.264"
        direct_pt = sess.get("direct_passthrough", False)

        src_vid = Path(temp_vid_path)
        out_mp4 = PROJECT_ROOT / TEMP_DIR / f"{sess['title_id']}_{uuid.uuid4().hex[:6]}.mp4"
        out_thumb = PROJECT_ROOT / TEMP_DIR / f"{sess['title_id']}_{uuid.uuid4().hex[:6]}.jpg"

        upload_mode = sess.get("upload_mode", "both")

        # Step 1: Process video assets (with concurrency control)
        with TRANSCODE_SEMAPHORE:
            # 1a. Transcode Cover (if pack or cover)
            if upload_mode in ("cover", "both"):
                if direct_pt:
                    bot.edit_message_text(
                        f"⏳ <b>Обработка...</b>\n1/3: 🚀 Прямая запись фона ({codec_name} 720p без потерь)...",
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode="HTML"
                    )
                    try:
                        passthrough_switch_video(src_vid, out_mp4, out_thumb, is_hevc=(codec == "hevc"))
                    except Exception as e:
                        print(f"[!] Direct stream copy error: {e}, falling back to transcode")
                        transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec=codec)
                else:
                    bot.edit_message_text(
                        f"⏳ <b>Обработка...</b>\n1/3: ⚙️ Конвертация фонового видео ({codec_name} 720p 30fps)...",
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode="HTML"
                    )
                    transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec=codec)

            # 1b. Transcode 4IFIR Video Icon (if pack or icon)
            if upload_mode in ("icon", "both"):
                bot.edit_message_text(
                    "⏳ <b>Обработка...</b>\n1/3: 🔲 Создание видеоиконки 4IFIR (256x256 HEVC, 24fps)...",
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML"
                )
                out_icon_mp4 = PROJECT_ROOT / TEMP_DIR / f"{sess['title_id']}_{uuid.uuid4().hex[:6]}_icon.mp4"
                out_icon_thumb = PROJECT_ROOT / TEMP_DIR / f"{sess['title_id']}_{uuid.uuid4().hex[:6]}_icon.jpg"
                transcode_to_switch_icon(src_vid, out_icon_mp4, out_icon_thumb, dur_sec=6.0)

        bot.edit_message_text(
            "⏳ <b>Обработка ролика...</b>\n"
            "2/3: ☁️ Загрузка на Google Диск...",
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML"
        )

        # Step 2: Google Drive Upload
        category = sess.get("category", "standard")
        access_tok, folder_id = get_gdrive_auth(category)
        if not access_tok:
            bot.edit_message_text(
                "❌ <b>Ошибка авторизации Google Drive</b>\nТокен истёк или недоступен. Обратитесь к администратору бота.",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )
            reset_session(chat_id)
            return

        direct_url = ""
        preview_url = ""
        file_size = 0
        icon_direct_url = ""
        icon_size = 0

        # Upload cover if produced
        if out_mp4 and out_mp4.exists():
            bot.edit_message_text(
                "⏳ <b>Загрузка...</b>\n2/3: ☁️ Загрузка фона на Google Диск...",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )
            upload_res = GoogleDriveClient.upload_file(
                file_path=out_mp4,
                folder_id=folder_id,
                token=access_tok
            )
            direct_url = upload_res.get("directUrl", "")
            preview_url = upload_res.get("previewUrl", "")
            file_size = upload_res.get("size", out_mp4.stat().st_size)

        # Upload icon if produced
        if out_icon_mp4 and out_icon_mp4.exists():
            bot.edit_message_text(
                "⏳ <b>Загрузка...</b>\n2/3: 🔲 Загрузка видеоиконки в облако...",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )
            i_upload_res = GoogleDriveClient.upload_file(
                file_path=out_icon_mp4,
                folder_id=GDRIVE_ICONS_FOLDER_ID,
                token=access_tok
            )
            icon_direct_url = i_upload_res.get("directUrl", "")
            icon_size = i_upload_res.get("size", out_icon_mp4.stat().st_size)

        bot.edit_message_text(
            "⏳ <b>Обработка ролика...</b>\n"
            "3/3: 🚀 Регистрация в каталоге и отправка на GitHub...",
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML"
        )

        # Step 3: Register in catalog & Push to GitHub (thread-safe lock)
        target_catalog_rel = CATALOG_PATH_AFTER_DARK if category == "after_dark" else CATALOG_PATH_STANDARD
        target_branch = GITHUB_BRANCH_AFTER_DARK if category == "after_dark" else GITHUB_BRANCH

        with CATALOG_LOCK:
            append_variant_to_catalog(
                catalog_rel=target_catalog_rel,
                title_id=sess["title_id"],
                game_name=sess["game_name"],
                variant_name=sess["variant_name"],
                author=sess["author"],
                category=category,
                direct_url=direct_url or icon_direct_url,
                preview_url=preview_url,
                file_size=file_size or icon_size,
                codec=codec,
                has_icon=bool(icon_direct_url),
                icon_url=icon_direct_url,
                icon_size_bytes=icon_size,
                icon_codec="hevc"
            )

            commit_msg = f"feat(catalog): add '{sess['variant_name']}' for {sess['title_id']} by @{sess['author']} via TG Bot"
            push_ok = push_catalog_to_github(target_catalog_rel, commit_msg, branch=target_branch)
            if not push_ok:
                err_msg = getattr(push_catalog_to_github, "last_error", "") or "Ошибка API / прав доступа"
                raise RuntimeError(f"Не удалось опубликовать изменения в репозиторий GitHub: {err_msg}")

        celebrate_text = (
            "🎉 <b>ВИДЕОФОН УСПЕШНО ОПУБЛИКОВАН!</b>\n\n"
            f"🎮 <b>Игра:</b> {sess['game_name']}\n"
            f"🆔 <b>Title ID:</b> <code>{sess['title_id']}</code>\n"
            f"🎬 <b>Вариант:</b> {sess['variant_name']}\n"
            f"👤 <b>Автор:</b> @{sess['author']}\n"
            f"📁 <b>Каталог:</b> {'Обычный H3H' if category == 'standard' else '🌸 After Dark (18+)'}\n\n"
            "✨ <i>Каталог на GitHub обновлён! Фон уже доступен для установки всем пользователям в приложении на Nintendo Switch!</i>"
        )

        if out_thumb and out_thumb.exists():
            with open(out_thumb, "rb") as photo:
                bot.send_photo(chat_id, photo, caption=celebrate_text, parse_mode="HTML")
            try:
                bot.delete_message(chat_id, message_id)
            except Exception:
                pass
        else:
            bot.edit_message_text(celebrate_text, chat_id=chat_id, message_id=message_id, parse_mode="HTML")

        reset_session(chat_id)

    except Exception as e:
        safe_err = html.escape(str(e))
        bot.edit_message_text(
            f"❌ <b>Ошибка при обработке ролика:</b>\n\n<code>{safe_err}</code>\n\n"
            "💡 <i>Попробуйте отправить ролик заново или проверьте его формат.</i>",
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML"
        )
        reset_session(chat_id)
    finally:
        # Cleanup temp transcode files
        for f in (out_mp4, out_thumb, out_icon_mp4, out_icon_thumb):
            if f and f.exists():
                f.unlink(missing_ok=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("publish:"))
def handle_publish_decision(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    action = call.data.split(":")[1]

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if action != "yes":
        reset_session(chat_id)
        bot.edit_message_text("❌ Публикация отменена.", chat_id=chat_id, message_id=call.message.message_id)
        return

    temp_vid_path = sess.get("temp_vid")
    if not temp_vid_path or not Path(temp_vid_path).exists():
        bot.edit_message_text(
            "⚠️ <b>Сессия устарела или файл не найден на сервере.</b>\n\n"
            "Пожалуйста, отправьте видеофайл заново сообщением.",
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )
        reset_session(chat_id)
        return

    # Run heavy processing asynchronously in worker thread
    threading.Thread(
        target=_do_single_publish_async,
        args=(chat_id, call.message.message_id, dict(sess)),
        daemon=True
    ).start()

# ----------------- Batch ZIP Processing -----------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("batch_cat:"))
def handle_batch_category(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    parts = call.data.split(":")
    choice = parts[1]
    batch_codec = parts[2] if len(parts) > 2 else "h264"

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if choice == "cancel":
        reset_session(chat_id)
        bot.edit_message_text("❌ Пакетная загрузка отменена.", chat_id=chat_id, message_id=call.message.message_id)
        return

    items = sess.get("batch_items", [])
    if not items:
        bot.edit_message_text("❌ Список видео пуст или сессия истекла. Отправьте архив заново.", chat_id=chat_id, message_id=call.message.message_id)
        return

    target_category = choice
    msg_id = call.message.message_id
    author = sess.get("author", "Community")
    zip_dir = sess.get("zip_dir")

    threading.Thread(
        target=process_batch_upload,
        args=(chat_id, msg_id, items, target_category, author, zip_dir, batch_codec),
        daemon=True
    ).start()

def process_batch_upload(chat_id: int, msg_id: int, items: List[Dict[str, Any]], category: str, author: str, zip_dir: Optional[str], codec: str = "h264"):
    total = len(items)
    success_count = 0
    target_catalog_rel = CATALOG_PATH_AFTER_DARK if category == "after_dark" else CATALOG_PATH_STANDARD

    access_tok, folder_id = get_gdrive_auth(category)
    if not access_tok:
        bot.edit_message_text("❌ Ошибка авторизации Google Drive (токен истёк).", chat_id=chat_id, message_id=msg_id)
        return

    published_titles = []
    codec_tag = "HEVC (H.265)" if codec == "hevc" else "H.264"

    for idx, item in enumerate(items, 1):
        try:
            bot.edit_message_text(
                f"⏳ <b>Пакетная обработка ({idx}/{total}):</b>\n\n"
                f"🎮 <b>{item['game_name']}</b>\n"
                f"🎬 Вариант: <i>{item['variant_name']}</i>\n"
                f"⚙️ Быстрая конвертация 720p ({codec_tag}) ➔ Google Диск...",
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode="HTML"
            )

            src_vid = Path(item["path"])
            out_mp4 = PROJECT_ROOT / TEMP_DIR / f"{item['title_id']}_{uuid.uuid4().hex[:6]}.mp4"
            out_thumb = PROJECT_ROOT / TEMP_DIR / f"{item['title_id']}_{uuid.uuid4().hex[:6]}.jpg"

            # Check if video is already ready-made Switch 720p
            v_info = probe_video_stream(src_vid)
            is_ready, det_codec = is_switch_720p_ready(v_info)
            if is_ready:
                item_codec = det_codec
                passthrough_switch_video(src_vid, out_mp4, out_thumb, is_hevc=(item_codec == "hevc"))
            else:
                item_codec = codec
                transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec=item_codec)

            upload_res = GoogleDriveClient.upload_file(
                file_path=out_mp4,
                folder_id=folder_id,
                token=access_tok
            )

            direct_url = upload_res.get("directUrl")
            preview_url = upload_res.get("previewUrl")
            file_size = upload_res.get("size", out_mp4.stat().st_size)

            append_variant_to_catalog(
                catalog_rel=target_catalog_rel,
                title_id=item["title_id"],
                game_name=item["game_name"],
                variant_name=item["variant_name"],
                author=author,
                category=category,
                direct_url=direct_url,
                preview_url=preview_url,
                file_size=file_size,
                codec=item_codec
            )

            success_count += 1
            published_titles.append(f"• <b>{item['game_name']}</b> — <i>{item['variant_name']}</i>")

            out_mp4.unlink(missing_ok=True)
            out_thumb.unlink(missing_ok=True)

        except Exception as e:
            print(f"[!] Batch item {item.get('file_name')} error: {e}")

    # Commit all changes to GitHub in a single commit!
    if success_count > 0:
        bot.edit_message_text(
            f"⏳ <b>Синхронизация с GitHub...</b>\nПубликую {success_count} новых фонов в репозиторий...",
            chat_id=chat_id,
            message_id=msg_id
        )
        commit_msg = f"feat(catalog): batch add {success_count} backgrounds by @{author} via TG Bot"
        target_branch = GITHUB_BRANCH_AFTER_DARK if category == "after_dark" else GITHUB_BRANCH
        push_catalog_to_github(target_catalog_rel, commit_msg, branch=target_branch)

    # Clean up unpacked zip directory
    if zip_dir and Path(zip_dir).exists():
        try:
            shutil.rmtree(zip_dir, ignore_errors=True)
        except Exception:
            pass

    reset_session(chat_id)

    cat_label = "Обычный каталог H3H" if category == "standard" else "🌸 After Dark (18+)"
    summary_text = (
        f"🎉 <b>ПАКЕТНАЯ ЗАГРУЗКА ЗАВЕРШЕНА!</b>\n\n"
        f"✅ Успешно опубликовано: <b>{success_count} из {total}</b>\n"
        f"📁 Каталог: <b>{cat_label}</b>\n"
        f"👤 Автор: @{author}\n\n"
        "<b>Добавленные фоны:</b>\n"
        + "\n".join(published_titles[:10])
    )
    if len(published_titles) > 10:
        summary_text += f"\n... и ещё {len(published_titles) - 10} фонов."

    summary_text += "\n\n✨ <i>Все фоны сразу доступны в приложении на Nintendo Switch!</i>"
    bot.edit_message_text(summary_text, chat_id=chat_id, message_id=msg_id)


# ----------------- Fallback Text Handler (for IDLE state & Links) -----------------

@bot.message_handler(content_types=["text"])
def handle_text_fallback(message: types.Message):
    chat_id = message.chat.id
    u_name = message.from_user.username or message.from_user.first_name or str(chat_id)
    text = (message.text or "").strip()
    print(f"[*] [TG TEXT] Chat {chat_id} (@{u_name}): '{text}'")

    sess = get_session(chat_id)
    state = sess.get("state", "IDLE")

    if state == "IDLE":
        if text.lower().startswith("http://") or text.lower().startswith("https://"):
            bot.reply_to(
                message,
                "💡 <b>Вы отправили ссылку на ролик.</b>\n\n"
                "Telegram-боты не имеют прямого доступа к скачиванию по внешним ссылкам. Пожалуйста, отправьте <b>сам видеофайл (.mp4, .webm, .mov)</b> или ZIP-архив прямо в этот чат!"
            )
            return

        bot.reply_to(
            message,
            "👋 <b>H3H Backgrounds Uploader Bot</b>\n\n"
            "Чтобы добавить живой видеофон на Nintendo Switch:\n"
            "1. 📹 <b>Отправьте сюда видеофайл</b> (.mp4, .webm, .mov) или <b>ZIP-архив</b> (до 20 МБ).\n"
            "2. Бот автоматически подготовит его для Switch (720p 30fps), загрузит на Google Диск и опубликует в каталог!\n\n"
            "<i>Нажмите /start для сброса или подробного описания.</i>"
        )

# ----------------- Main Entrypoint -----------------

def main():
    print("=" * 60)
    print("  H3H BACKGROUNDS - COMMUNITY TELEGRAM UPLOADER BOT")
    print(f"  Bot Username: @h3h_uploader_bot")
    print(f"  Bot Link:     https://t.me/h3h_uploader_bot")
    print(f"  Loaded {len(resolver.games)} games into TitleIdResolver.")
    if local_proxy:
        print(f"  Active Proxy: {local_proxy}")
    print("  [>] Ready! Send video (.mp4/.webm) or ZIP archive to the bot.")
    print("=" * 60)
    while True:
        try:
            bot.infinity_polling(skip_pending=False, timeout=20, long_polling_timeout=20)
        except telebot.apihelper.ApiTelegramException as e:
            if getattr(e, 'error_code', None) == 409:
                print("[!] 409 Conflict: another bot instance is polling or closing. Retrying in 6s...")
                time.sleep(6)
            else:
                print(f"[!] Telegram API error ({e}). Retrying in 5s...")
                time.sleep(5)
        except Exception as e:
            print(f"[!] Polling loop exception: {e}. Retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()
