from pathlib import Path

p = Path("tg_bot/bot.py")
c = p.read_text(encoding="utf-8")
is_crlf = "\r\n" in c
if is_crlf:
    c = c.replace("\r\n", "\n")

target = """@bot.message_handler(content_types=["video", "document", "animation"])
def handle_file_upload(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)
    sess = get_session(chat_id)"""

replacement = """@bot.message_handler(content_types=["video", "document", "animation"])
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
            f"⚠️ <b>Файл слишком большой ({mb:.1f} МБ)</b>.\\n\\n"
            "Официальное ограничение Telegram Bot API не позволяет ботам скачивать файлы более <b>20 МБ</b>.\\n\\n"
            "💡 <i>Пожалуйста, сожмите видео или отправьте фрагмент покороче (10–30 секунд для фона вполне достаточно).</i>"
        )
        return"""

if target in c:
    c = c.replace(target, replacement)
    if is_crlf:
        c = c.replace("\n", "\r\n")
    p.write_text(c, encoding="utf-8")
    print("[+] Successfully added size check!")
else:
    print("[-] Target not found in tg_bot/bot.py")
