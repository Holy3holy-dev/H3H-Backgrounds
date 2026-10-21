from pathlib import Path

p = Path("tg_bot/bot.py")
content = p.read_text(encoding="utf-8")

old_marker = """# ----------------- Single Video Publishing -----------------

def _do_single_publish_async(chat_id: int, message_id: int, sess: dict):"""

new_code = """# Concurrency limiters for multi-user community stability
TRANSCODE_SEMAPHORE = threading.Semaphore(1)  # Process FFmpeg sequentially to avoid cloud CPU starvation
CATALOG_LOCK = threading.Lock()               # Synchronize catalog modification & GitHub pushing

# ----------------- Single Video Publishing -----------------

def _do_single_publish_async(chat_id: int, message_id: int, sess: dict):"""

old_transcode = """        # Step 1: Process video
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
                transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec=codec)
        else:
            bot.edit_message_text(
                f"⏳ <b>Начинаю обработку ролика...</b>\\n1/3: ⚙️ Быстрая конвертация FFmpeg ({codec_name} 720p 30fps)...",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML"
            )
            transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec=codec)"""

new_transcode = """        # Step 1: Process video (with multi-user queuing)
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
                TRANSCODE_SEMAPHORE.release()"""

old_step3 = """        # Step 3: Register in catalog & Push to GitHub
        target_catalog_rel = CATALOG_PATH_AFTER_DARK if category == "after_dark" else CATALOG_PATH_STANDARD
        target_branch = GITHUB_BRANCH_AFTER_DARK if category == "after_dark" else GITHUB_BRANCH

        append_variant_to_catalog(
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
        )

        commit_msg = f"feat(catalog): add '{sess['variant_name']}' for {sess['title_id']} by @{sess['author']} via TG Bot"
        push_ok = push_catalog_to_github(target_catalog_rel, commit_msg, branch=target_branch)
        if not push_ok:
            raise RuntimeError("Не удалось опубликовать изменения в репозиторий GitHub.")"""

new_step3 = """        # Step 3: Register in catalog & Push to GitHub (thread-safe lock)
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
                direct_url=direct_url,
                preview_url=preview_url,
                file_size=file_size,
                codec=codec
            )

            commit_msg = f"feat(catalog): add '{sess['variant_name']}' for {sess['title_id']} by @{sess['author']} via TG Bot"
            push_ok = push_catalog_to_github(target_catalog_rel, commit_msg, branch=target_branch)
            if not push_ok:
                raise RuntimeError("Не удалось опубликовать изменения в репозиторий GitHub.")"""

# Replace markers
content_norm = content.replace("\r\n", "\n")
if old_marker.replace("\r\n", "\n") in content_norm:
    content_norm = content_norm.replace(old_marker.replace("\r\n", "\n"), new_code.replace("\r\n", "\n"))
if old_transcode.replace("\r\n", "\n") in content_norm:
    content_norm = content_norm.replace(old_transcode.replace("\r\n", "\n"), new_transcode.replace("\r\n", "\n"))
if old_step3.replace("\r\n", "\n") in content_norm:
    content_norm = content_norm.replace(old_step3.replace("\r\n", "\n"), new_step3.replace("\r\n", "\n"))

p.write_text(content_norm, encoding="utf-8")
print("[+] Applied multi-user concurrency protection (TRANSCODE_SEMAPHORE + CATALOG_LOCK)!")
