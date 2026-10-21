from pathlib import Path

p = Path("tg_bot/bot.py")
content = p.read_text(encoding="utf-8")

old_publish_async = """def _do_single_publish_async(chat_id: int, message_id: int, sess: dict):
    out_mp4 = None
    out_thumb = None
    try:
        codec = sess.get("codec", "h264")
        codec_name = "HEVC (H.265)" if codec == "hevc" else "H.264"
        direct_pt = sess.get("direct_passthrough", False)

        src_vid = Path(sess["temp_vid"])"""

new_publish_async = """def _do_single_publish_async(chat_id: int, message_id: int, sess: dict):
    out_mp4 = None
    out_thumb = None
    try:
        temp_vid_path = sess.get("temp_vid")
        if not temp_vid_path or not Path(temp_vid_path).exists():
            bot.edit_message_text(
                "⚠️ <b>Сессия устарела или файл не найден на сервере.</b>\\n\\n"
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

        src_vid = Path(temp_vid_path)"""

old_handle_publish = """    if action != "yes":
        reset_session(chat_id)
        bot.edit_message_text("❌ Публикация отменена.", chat_id=chat_id, message_id=call.message.message_id)
        return

    # Run heavy processing asynchronously in worker thread
    threading.Thread(
        target=_do_single_publish_async,
        args=(chat_id, call.message.message_id, dict(sess)),
        daemon=True
    ).start()"""

new_handle_publish = """    if action != "yes":
        reset_session(chat_id)
        bot.edit_message_text("❌ Публикация отменена.", chat_id=chat_id, message_id=call.message.message_id)
        return

    temp_vid_path = sess.get("temp_vid")
    if not temp_vid_path or not Path(temp_vid_path).exists():
        bot.edit_message_text(
            "⚠️ <b>Сессия устарела или файл не найден на сервере.</b>\\n\\n"
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
    ).start()"""

content_norm = content.replace("\r\n", "\n")
if old_publish_async.replace("\r\n", "\n") in content_norm:
    content_norm = content_norm.replace(old_publish_async.replace("\r\n", "\n"), new_publish_async.replace("\r\n", "\n"))
if old_handle_publish.replace("\r\n", "\n") in content_norm:
    content_norm = content_norm.replace(old_handle_publish.replace("\r\n", "\n"), new_handle_publish.replace("\r\n", "\n"))

p.write_text(content_norm, encoding="utf-8")
print("[+] Protected _do_single_publish_async and handle_publish_decision against NoneType temp_vid!")
