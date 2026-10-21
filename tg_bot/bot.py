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
    GDRIVE_FOLDER_ID,
    GDRIVE_AFTER_DARK_FOLDER_ID,
    GDRIVE_REFRESH_TOKEN,
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
    print(f"[*] Detected local proxy on {local_proxy}, configuring telebot...")
    from telebot import apihelper
    apihelper.proxy = {'http': local_proxy, 'https': local_proxy}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# --- Cloud Web Health Check Server (Port 10000 for Render) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'<h1>H3H Backgrounds Telegram Bot is Live!</h1>')

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f'[*] Health check server listening on 0.0.0.0:{port}')
    server.serve_forever()

threading.Thread(target=start_health_server, daemon=True).start()

resolver = TitleIdResolver(str(PROJECT_ROOT / CATALOG_PATH_STANDARD))

# --- User Session Management ---

user_sessions: Dict[int, Dict[str, Any]] = {}

def get_session(chat_id: int) -> Dict[str, Any]:
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "state": "IDLE",
            "temp_vid": None,
            "title_id": None,
            "game_name": None,
            "variant_name": None,
            "suggested_variant": None,
            "batch_items": [],
            "zip_dir": None,
            "category": "standard",
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
    user_sessions[chat_id] = {
        "state": "IDLE",
        "temp_vid": None,
        "title_id": None,
        "game_name": None,
        "variant_name": None,
        "suggested_variant": None,
        "batch_items": [],
        "zip_dir": None,
        "category": "standard",
        "author": ""
    }

# --- Core Processing Helpers ---

def transcode_to_switch_720p(src_vid: Path, out_mp4: Path, out_thumb: Path) -> bool:
    """Converts input video to Switch 720p 30fps H.264 (+faststart) and extracts thumbnail."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd_ffmpeg = [
        "ffmpeg", "-y",
        "-i", str(src_vid),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-b:v", "2500k",
        "-maxrate", "3000k",
        "-bufsize", "5000k",
        "-an",
        "-movflags", "+faststart",
        "-t", "25",
        str(out_mp4)
    ]
    subprocess.run(cmd_ffmpeg, capture_output=True, check=True)

    cmd_thumb = [
        "ffmpeg", "-y",
        "-ss", "2",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360",
        "-f", "image2",
        str(out_thumb)
    ]
    subprocess.run(cmd_thumb, capture_output=True)
    return True

def get_gdrive_auth(category: str = "standard") -> Tuple[Optional[str], Optional[str]]:
    """Returns (access_token, folder_id) for Google Drive operations based on category."""
    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = os.getenv("GDRIVE_REFRESH_TOKEN") or GDRIVE_REFRESH_TOKEN or gdrive_cfg.get("refresh_token")
    access_tok = GoogleDriveHelper.refresh_access_token(refresh_tok) or gdrive_cfg.get("token")

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

def append_variant_to_catalog(
    catalog_rel: Path,
    title_id: str,
    game_name: str,
    variant_name: str,
    author: str,
    category: str,
    direct_url: str,
    preview_url: str,
    file_size: int
) -> Dict[str, Any]:
    """Adds a new background variant to catalog JSON file and updates metadata."""
    target_catalog_path = PROJECT_ROOT / catalog_rel
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
    new_var = {
        "id": var_id,
        "name": variant_name,
        "style": "Community Animated" if category == "standard" else "After Dark (18+)",
        "version": "1.0",
        "url": direct_url,
        "previewUrl": preview_url,
        "sizeBytes": file_size,
        "sha256": "",
        "durationSec": 20.0,
        "author": author_tag,
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": f"Submitted via Telegram by {author_tag}"
    }
    game_entry["variants"].append(new_var)

    cat_data["totalGames"] = len(games_list)
    cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in games_list)
    cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

    target_catalog_path.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return new_var

def push_catalog_to_github(catalog_rel: Path, commit_msg: str) -> bool:
    """Commits catalog changes and pushes to GitHub main branch."""
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if not gh_token:
        gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
    if not gh_token:
        print("[!] No GitHub token available for pushing to remote.")
        return False
    repo_name = GITHUB_REPO or GitHubPublisher.get_repo_name()
    repo_url = f"https://x-access-token:{gh_token}@github.com/{repo_name}.git"
    try:
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "add", str(catalog_rel)], check=True)
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "push", repo_url, GITHUB_BRANCH], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] Git commit/push error: {e}")
        return False

# ----------------- Commands -----------------

@bot.message_handler(commands=["start", "help"])
def cmd_start(message: types.Message):
    chat_id = message.chat.id
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

@bot.message_handler(commands=["cancel"])
def cmd_cancel(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)
    bot.send_message(chat_id, "❌ Текущая операция отменена. Отправьте новое видео или архив для начала.")

# ----------------- Video & Archive Reception -----------------

@bot.message_handler(content_types=["video", "document", "animation"])
def handle_file_upload(message: types.Message):
    chat_id = message.chat.id
    sess = get_session(chat_id)
    reset_session(chat_id)

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

    # Route ZIP archives to batch handler
    if ext == ".zip":
        handle_zip_upload(message, file_id, file_name)
        return

    # Check video extension
    valid_vid_exts = [".mp4", ".webm", ".mov", ".mkv", ".gif"]
    if ext not in valid_vid_exts:
        bot.reply_to(message, "⚠️ Поддерживаются форматы: MP4, WEBM, MOV, MKV, GIF, а также ZIP архивы.")
        return

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

        # Check for Title ID in filename or caption
        detected_tid = TitleIdResolver.extract_title_id(file_name)
        if not detected_tid and message.caption:
            detected_tid = TitleIdResolver.extract_title_id(message.caption)

        detected_game = None
        suggested_variant = None
        if detected_tid:
            detected_game = resolver.resolve_by_title_id(detected_tid) or f"Игра ({detected_tid})"
            sess["title_id"] = detected_tid
            sess["game_name"] = detected_game
            # Deduce variant name by stripping title ID from filename
            stem = Path(file_name).stem
            clean_stem = re.sub(r'(?i)[0-9a-f]{16}', '', stem).strip(" _-").replace('_', ' ').replace('-', ' ').title()
            if len(clean_stem) >= 2:
                suggested_variant = clean_stem
                sess["suggested_variant"] = suggested_variant

        bot.delete_message(chat_id, status_msg.message_id)

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎮 Обычный каталог H3H", callback_data="cat:standard"),
            types.InlineKeyboardButton("🌸 After Dark (18+ / Эччи)", callback_data="cat:after_dark")
        )

        msg_lines = ["✅ <b>Видео получено!</b>\n"]
        if detected_tid:
            msg_lines.append(f"🎯 <b>Определён Title ID из файла:</b> <code>{detected_tid}</code>")
            msg_lines.append(f"🎮 <b>Игра:</b> {detected_game}\n")
        msg_lines.append("<b>Шаг 1 из 3:</b> В какой каталог добавить этот видеофон?")

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

    lines.append("\n<b>Куда опубликовать все эти фоны?</b>")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎮 Опубликовать все в Обычный каталог", callback_data="batch_cat:standard"),
        types.InlineKeyboardButton("🌸 Опубликовать все в After Dark (18+)", callback_data="batch_cat:after_dark"),
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
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🚀 Запустить публикацию!", callback_data="publish:yes"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="publish:cancel")
    )

    text = (
        "📋 <b>Проверьте данные перед публикацией:</b>\n\n"
        f"📁 <b>Категория:</b> {cat_label}\n"
        f"🎮 <b>Игра:</b> {sess['game_name']}\n"
        f"🆔 <b>Title ID:</b> <code>{sess['title_id']}</code>\n"
        f"🎬 <b>Название фона:</b> {sess['variant_name']}\n"
        f"👤 <b>Автор:</b> @{sess['author']}\n\n"
        "Нажмите <b>Запустить публикацию</b>, чтобы конвертировать видео, загрузить его на Google Диск и добавить на GitHub!"
    )

    if edit_msg_id:
        bot.edit_message_text(text, chat_id=chat_id, message_id=edit_msg_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

# ----------------- Single Video Publishing -----------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("publish:"))
def handle_publish_decision(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    action = call.data.split(":")[1]

    if action != "yes":
        reset_session(chat_id)
        bot.edit_message_text("❌ Публикация отменена.", chat_id=chat_id, message_id=call.message.message_id)
        return

    bot.edit_message_text("⏳ <b>Начинаю обработку ролика...</b>\n1/3: Конвертация FFmpeg в 720p 30fps...", chat_id=chat_id, message_id=call.message.message_id)

    src_vid = Path(sess["temp_vid"])
    out_mp4 = PROJECT_ROOT / TEMP_DIR / f"{sess['title_id']}_{uuid.uuid4().hex[:6]}.mp4"
    out_thumb = PROJECT_ROOT / TEMP_DIR / f"{sess['title_id']}_{uuid.uuid4().hex[:6]}.jpg"

    # Step 1: Transcode
    try:
        transcode_to_switch_720p(src_vid, out_mp4, out_thumb)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка конвертации FFmpeg: {e}")
        reset_session(chat_id)
        return

    bot.edit_message_text(
        "⏳ <b>Обработка ролика...</b>\n"
        "2/3: Загрузка на Google Диск...",
        chat_id=chat_id,
        message_id=call.message.message_id
    )

    # Step 2: Google Drive Upload
    access_tok, folder_id = get_gdrive_auth(sess.get("category", "standard"))
    if not access_tok:
        bot.send_message(chat_id, "❌ Ошибка авторизации Google Drive (токен истёк). Обратитесь к администратору бота.")
        reset_session(chat_id)
        return

    try:
        upload_res = GoogleDriveClient.upload_file(
            file_path=out_mp4,
            folder_id=folder_id,
            token=access_tok
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ Сбой загрузки на Google Диск: {e}")
        reset_session(chat_id)
        return

    direct_url = upload_res.get("directUrl")
    preview_url = upload_res.get("previewUrl")
    file_size = upload_res.get("size", out_mp4.stat().st_size)

    bot.edit_message_text(
        "⏳ <b>Обработка ролика...</b>\n"
        "3/3: Регистрация в каталоге и отправка на GitHub...",
        chat_id=chat_id,
        message_id=call.message.message_id
    )

    # Step 3: Register in catalog & Push to GitHub
    target_catalog_rel = CATALOG_PATH_AFTER_DARK if sess["category"] == "after_dark" else CATALOG_PATH_STANDARD

    try:
        append_variant_to_catalog(
            catalog_rel=target_catalog_rel,
            title_id=sess["title_id"],
            game_name=sess["game_name"],
            variant_name=sess["variant_name"],
            author=sess["author"],
            category=sess["category"],
            direct_url=direct_url,
            preview_url=preview_url,
            file_size=file_size
        )

        commit_msg = f"feat(catalog): add '{sess['variant_name']}' for {sess['title_id']} by @{sess['author']} via TG Bot"
        push_catalog_to_github(target_catalog_rel, commit_msg)

        celebrate_text = (
            "🎉 <b>ВИДЕОФОН УСПЕШНО ОПУБЛИКОВАН!</b>\n\n"
            f"🎮 <b>Игра:</b> {sess['game_name']}\n"
            f"🆔 <b>Title ID:</b> <code>{sess['title_id']}</code>\n"
            f"🎬 <b>Вариант:</b> {sess['variant_name']}\n"
            f"👤 <b>Автор:</b> @{sess['author']}\n"
            f"📁 <b>Каталог:</b> {'Обычный H3H' if sess['category'] == 'standard' else '🌸 After Dark (18+)'}\n\n"
            "✨ <i>Каталог на GitHub обновлён! Фон уже доступен для установки всем пользователям в приложении на Nintendo Switch!</i>"
        )

        if out_thumb.exists():
            with open(out_thumb, "rb") as photo:
                bot.send_photo(chat_id, photo, caption=celebrate_text)
        else:
            bot.send_message(chat_id, celebrate_text)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при публикации на GitHub/Каталоге: {e}")

    finally:
        try:
            out_mp4.unlink(missing_ok=True)
            out_thumb.unlink(missing_ok=True)
        except Exception:
            pass
        reset_session(chat_id)

# ----------------- Batch ZIP Processing -----------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("batch_cat:"))
def handle_batch_category(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    choice = call.data.split(":")[1]

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
        args=(chat_id, msg_id, items, target_category, author, zip_dir),
        daemon=True
    ).start()

def process_batch_upload(chat_id: int, msg_id: int, items: List[Dict[str, Any]], category: str, author: str, zip_dir: Optional[str]):
    total = len(items)
    success_count = 0
    target_catalog_rel = CATALOG_PATH_AFTER_DARK if category == "after_dark" else CATALOG_PATH_STANDARD

    access_tok, folder_id = get_gdrive_auth(category)
    if not access_tok:
        bot.edit_message_text("❌ Ошибка авторизации Google Drive (токен истёк).", chat_id=chat_id, message_id=msg_id)
        return

    published_titles = []

    for idx, item in enumerate(items, 1):
        try:
            bot.edit_message_text(
                f"⏳ <b>Пакетная обработка ({idx}/{total}):</b>\n\n"
                f"🎮 <b>{item['game_name']}</b>\n"
                f"🎬 Вариант: <i>{item['variant_name']}</i>\n"
                "⚙️ Конвертация 720p ➔ Загрузка на Google Диск...",
                chat_id=chat_id,
                message_id=msg_id
            )

            src_vid = Path(item["path"])
            out_mp4 = PROJECT_ROOT / TEMP_DIR / f"{item['title_id']}_{uuid.uuid4().hex[:6]}.mp4"
            out_thumb = PROJECT_ROOT / TEMP_DIR / f"{item['title_id']}_{uuid.uuid4().hex[:6]}.jpg"

            transcode_to_switch_720p(src_vid, out_mp4, out_thumb)

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
                file_size=file_size
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
        push_catalog_to_github(target_catalog_rel, commit_msg)

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

# ----------------- Main Entrypoint -----------------

def main():
    print("[*] H3H Telegram Uploader Bot starting...")
    print(f"[*] Loaded {len(resolver.games)} games into TitleIdResolver.")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
        except telebot.apihelper.ApiTelegramException as e:
            if getattr(e, 'error_code', None) == 409:
                print("[!] 409 Conflict: Previous instance is terminating. Retrying in 6 seconds...")
                time.sleep(6)
            else:
                print(f"[!] Telegram API error ({e}). Retrying in 5 seconds...")
                time.sleep(5)
        except Exception as e:
            print(f"[!] Polling loop exception: {e}. Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
