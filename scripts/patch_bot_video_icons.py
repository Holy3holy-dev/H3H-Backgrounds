from pathlib import Path

p = Path("tg_bot/bot.py")
code = p.read_text(encoding="utf-8")

# 1. Add GDRIVE_ICONS_FOLDER_ID import
if "GDRIVE_ICONS_FOLDER_ID" not in code:
    code = code.replace(
        "GDRIVE_AFTER_DARK_FOLDER_ID,",
        "GDRIVE_AFTER_DARK_FOLDER_ID,\n    GDRIVE_ICONS_FOLDER_ID,"
    )

# 2. Add transcode_to_switch_icon function
if "def transcode_to_switch_icon" not in code:
    icon_fn = '''def transcode_to_switch_icon(src_vid: Path, out_mp4: Path, out_thumb: Path, dur_sec: float = 6.0) -> bool:
    """Converts input video to exact 4IFIR video icon standard: 256x256 HEVC, 24fps, silent, +faststart."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    crop_filter = "crop=min(iw\\\\,ih):min(iw\\\\,ih),scale=256:256:flags=fast_bilinear"
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

'''
    code = code.replace("def transcode_to_switch_720p", icon_fn + "def transcode_to_switch_720p")

# 3. Add command /icon
if "cmd_upload_icon" not in code:
    icon_cmd = '''@bot.message_handler(commands=["icon", "upload_icon"])
def cmd_upload_icon(message: types.Message):
    chat_id = message.chat.id
    reset_session(chat_id)
    sess = get_session(chat_id)
    sess["upload_mode"] = "icon"
    sess["state"] = "AWAITING_FILE"
    bot.reply_to(
        message,
        "🔲 <b>Загрузка видеоиконки 4IFIR (256x256 HEVC)</b>\\n\\n"
        "Отправьте квадратное видео или видеоролик для создания видеоиконки.\\n"
        "Бот автоматически кадрирует его в квадрат 1:1, сожмет в 256x256 24fps HEVC без звука, "
        "загрузит в облако и привяжет к игре на Nintendo Switch!"
    )

'''
    code = code.replace('@bot.message_handler(commands=["cancel"])', icon_cmd + '@bot.message_handler(commands=["cancel"])')

# 4. In handle_file_upload, detect icon/pack keyword from caption/filename
old_sess_init = '''        sess["temp_vid"] = str(target_path)
        sess["state"] = "AWAITING_CATEGORY"
        sess["author"] = message.from_user.username or message.from_user.first_name or "Community"'''

new_sess_init = '''        sess["temp_vid"] = str(target_path)
        sess["state"] = "AWAITING_CATEGORY"
        sess["author"] = message.from_user.username or message.from_user.first_name or "Community"

        # Detect upload mode (cover, icon, both)
        combined_meta = f"{message.caption or ''} {file_name}".lower()
        if re.search(r'(?i)(#icon|#иконка|icon|иконка|256x256)', combined_meta) or sess.get("upload_mode") == "icon":
            sess["upload_mode"] = "icon"
        elif re.search(r'(?i)(#pack|#пак|pack|fullpack|полный)', combined_meta):
            sess["upload_mode"] = "both"
        else:
            sess["upload_mode"] = sess.get("upload_mode", "both")'''

assert old_sess_init in code, "old_sess_init not found"
code = code.replace(old_sess_init, new_sess_init, 1)

p.write_text(code, encoding="utf-8")
print("[+] Successfully added icon handling foundation in tg_bot/bot.py")
