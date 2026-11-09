"""
Applies robustness improvements to tg_bot/bot.py:
1. Wrap start_health_server in try/except so local runs without port 10000 do not fail.
2. Add text aliases and logging to cmd_start.
3. Add pre-flight size check and logging to handle_file_upload.
4. Add friendly text fallback handler for IDLE state.
5. Set skip_pending=False and add rich status banner in main().
"""

from pathlib import Path
import re

bot_path = Path("tg_bot/bot.py")
content = bot_path.read_text(encoding="utf-8")
is_crlf = "\r\n" in content
if is_crlf:
    content = content.replace("\r\n", "\n")

# 1. Health server try/except
old_health = """def start_health_server():
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f'[*] Health check server listening on 0.0.0.0:{port}')
    server.serve_forever()"""

new_health = """def start_health_server():
    port = int(os.getenv('PORT', 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f'[*] Health check server listening on 0.0.0.0:{port}')
        server.serve_forever()
    except Exception as e:
        print(f'[*] Health check server notice (safe to ignore locally): {e}')"""

if old_health in content:
    content = content.replace(old_health, new_health)
    print("[+] Patched start_health_server")

# 2. cmd_start text aliases & logging
old_cmd_start = """@bot.message_handler(commands=["start", "help"])
def cmd_start(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)"""

new_cmd_start = """@bot.message_handler(commands=["start", "help"])
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() in ["старт", "start", "начать", "помощь", "help", "меню", "menu"])
def cmd_start(message: types.Message):
    chat_id = message.chat.id
    u_name = message.from_user.username or message.from_user.first_name or str(chat_id)
    print(f"[*] [TG CMD] /start from @{u_name} (chat_id: {chat_id})")
    reset_session(chat_id)"""

if old_cmd_start in content:
    content = content.replace(old_cmd_start, new_cmd_start)
    print("[+] Patched cmd_start")

# 3. handle_file_upload pre-flight check & logging
old_file_upload_top = """@bot.message_handler(content_types=["video", "document", "animation"])
def handle_file_upload(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)
    sess = get_session(chat_id)

    file_id = None
    file_name = f"upload_{uuid.uuid4().hex[:8]}.mp4" """

new_file_upload_top = """@bot.message_handler(content_types=["video", "document", "animation"])
def handle_file_upload(message: types.Message):
    chat_id = message.chat.id
    u_name = message.from_user.username or message.from_user.first_name or str(chat_id)
    reset_session(chat_id)
    sess = get_session(chat_id)

    # Pre-flight Telegram 20 MB size limit check
    fsize = getattr(message.video or message.document or message.animation, 'file_size', 0)
    if fsize and fsize > 20 * 1024 * 1024:
        mb = fsize / (1024 * 1024)
        print(f"[!] [TG REJECT] File from @{u_name} is too large ({mb:.1f} MB > 20 MB)")
        bot.reply_to(
            message,
            f"⚠️ <b>Файл слишком большой ({mb:.1f} МБ)</b>.\\n\\n"
            "Официальное ограничение Telegram Bot API не позволяет ботам скачивать файлы более <b>20 МБ</b>.\\n\\n"
            "💡 <i>Пожалуйста, сожмите видео или отправьте фрагмент покороче (10–30 секунд для фона вполне достаточно).</i>"
        )
        return

    file_id = None
    file_name = f"upload_{uuid.uuid4().hex[:8]}.mp4" """

if old_file_upload_top in content:
    content = content.replace(old_file_upload_top, new_file_upload_top)
    print("[+] Patched handle_file_upload size check")

# Also add mime_type fallback for document
old_ext_check = """    ext = Path(file_name).suffix.lower()

    # Route ZIP archives to batch handler
    if ext == ".zip":
        handle_zip_upload(message, file_id, file_name)
        return

    # Check video extension
    valid_vid_exts = [".mp4", ".webm", ".mov", ".mkv", ".gif"]
    if ext not in valid_vid_exts:
        bot.reply_to(message, "⚠️ Поддерживаются форматы: MP4, WEBM, MOV, MKV, GIF, а также ZIP архивы.")
        return"""

new_ext_check = """    ext = Path(file_name).suffix.lower()
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

    print(f"[*] [TG UPLOAD] Receiving {file_name} from @{u_name} ({chat_id})...")"""

if old_ext_check in content:
    content = content.replace(old_ext_check, new_ext_check)
    print("[+] Patched ext_check with mime and logging")

# 4. Add fallback text handler before main
fallback_handler_code = """
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
                "💡 <b>Вы отправили ссылку на ролик.</b>\\n\\n"
                "Telegram-боты не имеют прямого доступа к скачиванию по внешним ссылкам. Пожалуйста, отправьте <b>сам видеофайл (.mp4, .webm, .mov)</b> или ZIP-архив прямо в этот чат!"
            )
            return

        bot.reply_to(
            message,
            "👋 <b>H3H Backgrounds Uploader Bot</b>\\n\\n"
            "Чтобы добавить живой видеофон на Nintendo Switch:\\n"
            "1. 📹 <b>Отправьте сюда видеофайл</b> (.mp4, .webm, .mov) или <b>ZIP-архив</b> (до 20 МБ).\\n"
            "2. Бот автоматически подготовит его для Switch (720p 30fps), загрузит на Google Диск и опубликует в каталог!\\n\\n"
            "<i>Нажмите /start для сброса или подробного описания.</i>"
        )
"""

old_main_top = "# ----------------- Main Entrypoint -----------------"
if old_main_top in content and "handle_text_fallback" not in content:
    content = content.replace(old_main_top, fallback_handler_code + "\n" + old_main_top)
    print("[+] Added handle_text_fallback")

# 5. Update main() with skip_pending=False and banner
old_main = """def main():
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
            time.sleep(5)"""

new_main = """def main():
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
            time.sleep(5)"""

if old_main in content:
    content = content.replace(old_main, new_main)
    print("[+] Patched main() with skip_pending=False")

if is_crlf:
    content = content.replace("\n", "\r\n")

bot_path.write_text(content, encoding="utf-8")
print("[+] Successfully saved tg_bot/bot.py!")
