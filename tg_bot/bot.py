"""
H3H Backgrounds & After Dark - Official Community Telegram Uploader Bot.

Enables community members to submit video backgrounds directly via Telegram:
1. Receives video / animation file
2. Automatically matches game name to Nintendo Switch Title ID (via TitleIdResolver)
3. Transcodes to Nintendo Switch standard 720p 30fps H.264 (+faststart)
4. Uploads to Google Drive (Standard or After Dark 18+ folder)
5. Registers into catalog.json / catalog_after_dark.json and pushes to GitHub main!
"""

import os
import sys
import json
import uuid
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import telebot
from telebot import types

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from tg_bot.config import (
    BOT_TOKEN,
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
resolver = TitleIdResolver(str(PROJECT_ROOT / CATALOG_PATH_STANDARD))

# User session state storage
# chat_id -> dict with keys: 'state', 'temp_vid', 'title_id', 'game_name', 'variant_name', 'category', 'author'
user_sessions: Dict[int, Dict[str, Any]] = {}

def get_session(chat_id: int) -> Dict[str, Any]:
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "state": "IDLE",
            "temp_vid": None,
            "title_id": None,
            "game_name": None,
            "variant_name": None,
            "category": "standard", # 'standard' or 'after_dark'
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
    user_sessions[chat_id] = {
        "state": "IDLE",
        "temp_vid": None,
        "title_id": None,
        "game_name": None,
        "variant_name": None,
        "category": "standard",
        "author": ""
    }

# ----------------- Commands -----------------

@bot.message_handler(commands=["start", "help"])
def cmd_start(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)
    text = (
        "👋 <b>Добро пожаловать в H3H Video Backgrounds Uploader!</b>\n\n"
        "С помощью этого бота вы можете добавить свой живой видеофон для Nintendo Switch (4IFIR):\n\n"
        "✨ <b>Что я умею:</b>\n"
        "• Принимать видео и анимации (MP4, WEBM, MOV, GIF)\n"
        "• Автоматически находить правильный <b>Title ID</b> игры\n"
        "• Конвертировать ролик в идеальный для Switch <b>720p 30fps H.264</b>\n"
        "• Загружать на Google Диск и сразу обновлять каталог на <b>GitHub</b>\n"
        "• Поддерживать как обычный каталог, так и коллекцию <b>After Dark (18+)</b>\n\n"
        "🎬 <b>Чтобы начать, просто отправьте мне видеофайл!</b>"
    )
    bot.send_message(chat_id, text)

@bot.message_handler(commands=["cancel"])
def cmd_cancel(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)
    bot.send_message(chat_id, "❌ Текущая операция отменена. Отправьте новое видео для начала.")

# ----------------- Video Reception -----------------

@bot.message_handler(content_types=["video", "document", "animation"])
def handle_video_upload(message: types.Message):
    chat_id = message.chat.id
    sess = get_session(chat_id)

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
        bot.reply_to(message, "⚠️ Не удалось прочитать файл. Пожалуйста, отправьте видеоролик.")
        return

    # Check file extension
    valid_exts = [".mp4", ".webm", ".mov", ".mkv", ".gif"]
    ext = Path(file_name).suffix.lower()
    if ext not in valid_exts:
        bot.reply_to(message, "⚠️ Поддерживаются форматы: MP4, WEBM, MOV, MKV, GIF.")
        return

    bot.send_chat_action(chat_id, "typing")
    status_msg = bot.reply_to(message, "⏳ Скачиваю видеофайл из Telegram...")

    try:
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        target_path = PROJECT_ROOT / TEMP_DIR / f"{chat_id}_{file_name}"
        target_path.write_bytes(downloaded)

        sess["temp_vid"] = str(target_path)
        sess["state"] = "AWAITING_CATEGORY"
        sess["author"] = message.from_user.username or message.from_user.first_name or "Community"

        bot.delete_message(chat_id, status_msg.message_id)

        # Step 1: Select Category
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎮 Обычный каталог H3H", callback_data="cat:standard"),
            types.InlineKeyboardButton("🌸 After Dark (18+ / Эччи)", callback_data="cat:after_dark")
        )
        bot.send_message(
            chat_id,
            "✅ <b>Видео получено!</b>\n\n"
            "<b>Шаг 1 из 4:</b> В какой каталог добавить этот видеофон?",
            reply_markup=markup
        )

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при загрузке: {e}")
        reset_session(chat_id)

# ----------------- Category Callback -----------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat:"))
def handle_category_choice(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    choice = call.data.split(":")[1]

    sess["category"] = choice
    sess["state"] = "AWAITING_GAME_NAME"

    cat_title = "Обычный каталог" if choice == "standard" else "🌸 After Dark (18+)"
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

    # 1. Direct 16-hex Title ID check
    if len(raw_text) == 16 and all(c in "0123456789ABCDEFabcdef" for c in raw_text):
        sess["title_id"] = raw_text.upper()
        sess["game_name"] = f"Игра ({sess['title_id']})"
        sess["state"] = "AWAITING_VARIANT_NAME"
        bot.send_message(
            chat_id,
            f"✅ <b>Title ID распознан:</b> <code>{sess['title_id']}</code>\n\n"
            "<b>Шаг 3 из 4:</b> Как назвать этот вариант видеофона?\n"
            "<i>(Например: Dynamic Action, Title Screen, Anime Remix)</i>"
        )
        return

    # 2. Fuzzy Multiple Matcher (Typo & Slang tolerant)
    matches = resolver.resolve_multiple(raw_text, limit=4)
    if matches:
        # Cache candidates for this chat
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
def handle_variant_name(message: types.Message):
    chat_id = message.chat.id
    sess = get_session(chat_id)
    var_name = message.text.strip()
    if not var_name:
        var_name = "Custom Variant"

    sess["variant_name"] = var_name
    sess["state"] = "AWAITING_CONFIRMATION"

    cat_label = "Обычный каталог" if sess["category"] == "standard" else "🌸 After Dark (18+)"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🚀 Запустить публикацию!", callback_data="publish:yes"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="publish:cancel")
    )

    bot.send_message(
        chat_id,
        "📋 <b>Проверьте данные перед публикацией:</b>\n\n"
        f"📁 <b>Категория:</b> {cat_label}\n"
        f"🎮 <b>Игра:</b> {sess['game_name']}\n"
        f"🆔 <b>Title ID:</b> <code>{sess['title_id']}</code>\n"
        f"🎬 <b>Название фона:</b> {sess['variant_name']}\n"
        f"👤 <b>Автор:</b> @{sess['author']}\n\n"
        "Нажмите <b>Запустить публикацию</b>, чтобы конвертировать видео, загрузить его на Google Диск и добавить на GitHub!",
        reply_markup=markup
    )

# ----------------- Processing & Publishing -----------------

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

    # Step 1: Transcode via FFmpeg
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
    try:
        subprocess.run(cmd_ffmpeg, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        bot.send_message(chat_id, f"❌ Ошибка конвертации FFmpeg: {e.stderr.decode('utf-8', errors='ignore')[:300]}")
        reset_session(chat_id)
        return

    # Extract thumbnail
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

    bot.edit_message_text(
        "⏳ <b>Обработка ролика...</b>\n"
        "2/3: Загрузка на Google Диск...",
        chat_id=chat_id,
        message_id=call.message.message_id
    )

    # Step 2: Upload to Google Drive
    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = gdrive_cfg.get("refresh_token")
    access_tok = GoogleDriveHelper.refresh_access_token(refresh_tok) or gdrive_cfg.get("token")
    folder_id = gdrive_cfg.get("project_folder_id") or gdrive_cfg.get("folder_id")

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

    # Step 3: Register in catalog.json or catalog_after_dark.json
    target_catalog_rel = CATALOG_PATH_AFTER_DARK if sess["category"] == "after_dark" else CATALOG_PATH_STANDARD
    target_catalog_path = PROJECT_ROOT / target_catalog_rel

    try:
        cat_data = json.loads(target_catalog_path.read_text(encoding="utf-8"))
        games_list = cat_data.get("games", [])

        # Find or add game
        game_entry = None
        for g in games_list:
            if g.get("titleId") == sess["title_id"]:
                game_entry = g
                break

        if not game_entry:
            game_entry = {
                "titleId": sess["title_id"],
                "title": sess["game_name"],
                "publisher": "Community",
                "variants": []
            }
            games_list.append(game_entry)

        var_id = f"var-{uuid.uuid4().hex[:8]}"
        new_var = {
            "id": var_id,
            "name": sess["variant_name"],
            "style": "Community Animated" if sess["category"] == "standard" else "After Dark (18+)",
            "version": "1.0",
            "url": direct_url,
            "previewUrl": preview_url,
            "sizeBytes": file_size,
            "sha256": "",
            "durationSec": 20.0,
            "author": f"@{sess['author']}",
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "hasAudio": False,
            "notes": f"Submitted via Telegram by @{sess['author']}"
        }
        game_entry["variants"].append(new_var)

        cat_data["totalGames"] = len(games_list)
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in games_list)
        cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

        target_catalog_path.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Step 4: Git commit and push to GitHub
        gh_token, _ = GitHubPublisher.get_stored_credentials()
        if gh_token:
            repo_url = f"https://x-access-token:{gh_token}@github.com/{GitHubPublisher.get_repo_name()}.git"
            subprocess.run(["git", "-C", str(PROJECT_ROOT), "add", str(target_catalog_rel)], check=True)
            subprocess.run([
                "git", "-C", str(PROJECT_ROOT), "commit", "-m",
                f"feat(catalog): add '{sess['variant_name']}' for {sess['title_id']} by @{sess['author']} via TG Bot"
            ], check=True)
            subprocess.run(["git", "-C", str(PROJECT_ROOT), "push", repo_url, "main"], check=True)

        # Success message with thumbnail!
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
        # Cleanup
        try:
            out_mp4.unlink(missing_ok=True)
            out_thumb.unlink(missing_ok=True)
        except Exception:
            pass
        reset_session(chat_id)

def main():
    print("[*] H3H Telegram Uploader Bot starting...")
    print(f"[*] Loaded {len(resolver.games)} games into TitleIdResolver.")
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    main()
