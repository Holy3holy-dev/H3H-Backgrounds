from pathlib import Path

p = Path("tg_bot/bot.py")
code = p.read_text(encoding="utf-8")

old_func_start = '''def _do_single_publish_async(chat_id: int, message_id: int, sess: dict):
    out_mp4 = None
    out_thumb = None
    try:'''

new_func_start = '''def _do_single_publish_async(chat_id: int, message_id: int, sess: dict):
    out_mp4 = None
    out_thumb = None
    out_icon_mp4 = None
    out_icon_thumb = None
    try:'''

assert old_func_start in code, "old_func_start not found"
code = code.replace(old_func_start, new_func_start, 1)

old_transcode_block = '''        # Step 1: Process video (with multi-user queuing)
        if direct_pt:
            bot.edit_message_text(
                f"⏳ <b>Обработка ролика...</b>\\n1/3: 🚀 Прямая запись потока ({codec_name} 720p без потерь)...",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )
            try:
                passthrough_switch_video(src_vid, out_mp4, out_thumb, is_hevc=(codec == "hevc"))
            except Exception as e:
                print(f"[!] Direct stream copy error: {e}, falling back to transcode")
                with TRANSCODE_SEMAPHORE:
                    transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec=codec)
        else:
            acquired = TRANSCODE_SEMAPHORE.acquire(blocking=False)
            if not acquired:
                bot.edit_message_text(
                    "⏳ <b>Сервер обрабатывает предыдущий ролик...</b>\\n"
                    "Вы в очереди на конвертацию. Скоро начнем (~5-10 сек)!",
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML"
                )
                TRANSCODE_SEMAPHORE.acquire(blocking=True)

            try:
                bot.edit_message_text(
                    f"⏳ <b>Начинаю обработку ролика...</b>\\n1/3: ⚙️ Быстрая конвертация FFmpeg ({codec_name} 720p 30fps)...",
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML"
                )
                transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec=codec)
            finally:
                TRANSCODE_SEMAPHORE.release()'''

new_transcode_block = '''        upload_mode = sess.get("upload_mode", "both")

        # Step 1: Process video assets (with concurrency control)
        with TRANSCODE_SEMAPHORE:
            # 1a. Transcode Cover (if pack or cover)
            if upload_mode in ("cover", "both"):
                if direct_pt:
                    bot.edit_message_text(
                        f"⏳ <b>Обработка...</b>\\n1/3: 🚀 Прямая запись фона ({codec_name} 720p без потерь)...",
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
                        f"⏳ <b>Обработка...</b>\\n1/3: ⚙️ Конвертация фонового видео ({codec_name} 720p 30fps)...",
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode="HTML"
                    )
                    transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec=codec)

            # 1b. Transcode 4IFIR Video Icon (if pack or icon)
            if upload_mode in ("icon", "both"):
                bot.edit_message_text(
                    "⏳ <b>Обработка...</b>\\n1/3: 🔲 Создание видеоиконки 4IFIR (256x256 HEVC, 24fps)...",
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML"
                )
                out_icon_mp4 = PROJECT_ROOT / TEMP_DIR / f"{sess['title_id']}_{uuid.uuid4().hex[:6]}_icon.mp4"
                out_icon_thumb = PROJECT_ROOT / TEMP_DIR / f"{sess['title_id']}_{uuid.uuid4().hex[:6]}_icon.jpg"
                transcode_to_switch_icon(src_vid, out_icon_mp4, out_icon_thumb, dur_sec=6.0)'''

assert old_transcode_block in code, "old_transcode_block not found"
code = code.replace(old_transcode_block, new_transcode_block, 1)

old_upload_block = '''        # Step 2: Google Drive Upload
        category = sess.get("category", "standard")
        access_tok, folder_id = get_gdrive_auth(category)
        if not access_tok:
            bot.edit_message_text(
                "❌ <b>Ошибка авторизации Google Drive</b>\\nТокен истёк или недоступен. Обратитесь к администратору бота.",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )
            reset_session(chat_id)
            return

        upload_res = GoogleDriveClient.upload_file(
            file_path=out_mp4,
            folder_id=folder_id,
            token=access_tok
        )

        direct_url = upload_res.get("directUrl")
        preview_url = upload_res.get("previewUrl")
        file_size = upload_res.get("size", out_mp4.stat().st_size)'''

new_upload_block = '''        # Step 2: Google Drive Upload
        category = sess.get("category", "standard")
        access_tok, folder_id = get_gdrive_auth(category)
        if not access_tok:
            bot.edit_message_text(
                "❌ <b>Ошибка авторизации Google Drive</b>\\nТокен истёк или недоступен. Обратитесь к администратору бота.",
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
                "⏳ <b>Загрузка...</b>\\n2/3: ☁️ Загрузка фона на Google Диск...",
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
                "⏳ <b>Загрузка...</b>\\n2/3: 🔲 Загрузка видеоиконки в облако...",
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
            icon_size = i_upload_res.get("size", out_icon_mp4.stat().st_size)'''

assert old_upload_block in code, "old_upload_block not found"
code = code.replace(old_upload_block, new_upload_block, 1)

# In Step 3 append_variant_to_catalog call:
old_append_call = '''            append_variant_to_catalog(
                catalog_rel=target_catalog_rel,
                title_id=sess["title_id"],
                game_name=sess["game_name"],
                variant_name=sess["variant_name"],
                author=sess["author"],
                category=category,
                direct_url=direct_url,
                preview_url=preview_url,
                file_size=file_size,
                codec=codec
            )'''

new_append_call = '''            append_variant_to_catalog(
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
            )'''

assert old_append_call in code, "old_append_call not found"
code = code.replace(old_append_call, new_append_call, 1)

# Update cleanup finally
old_cleanup = '''    finally:
        # Cleanup temp transcode files
        if out_mp4 and out_mp4.exists():
            out_mp4.unlink(missing_ok=True)
        if out_thumb and out_thumb.exists():
            out_thumb.unlink(missing_ok=True)'''

new_cleanup = '''    finally:
        # Cleanup temp transcode files
        for f in (out_mp4, out_thumb, out_icon_mp4, out_icon_thumb):
            if f and f.exists():
                f.unlink(missing_ok=True)'''

assert old_cleanup in code, "old_cleanup not found"
code = code.replace(old_cleanup, new_cleanup, 1)

p.write_text(code, encoding="utf-8")
print("[+] Successfully updated _do_single_publish_async in tg_bot/bot.py")
