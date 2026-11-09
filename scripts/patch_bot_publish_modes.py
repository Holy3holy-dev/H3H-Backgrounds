from pathlib import Path

p = Path("tg_bot/bot.py")
code = p.read_text(encoding="utf-8")

# 1. Update prompt_publish_confirmation to show & toggle upload format
old_prompt_body = '''    toggle_target = "hevc" if codec == "h264" else "h264"
    toggle_text = "⚡ Переключить на HEVC (H.265)" if codec == "h264" else "🎬 Переключить на H.264 (AVC)"

    markup.add(types.InlineKeyboardButton(toggle_text, callback_data=f"codec:{toggle_target}"))'''

new_prompt_body = '''    toggle_target = "hevc" if codec == "h264" else "h264"
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
    markup.add(types.InlineKeyboardButton(toggle_text, callback_data=f"codec:{toggle_target}"))'''

assert old_prompt_body in code, "old_prompt_body not found"
code = code.replace(old_prompt_body, new_prompt_body, 1)

# Add callback handler for mode toggle
mode_handler = '''@bot.callback_query_handler(func=lambda call: call.data.startswith("mode:"))
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

'''
code = code.replace('@bot.callback_query_handler(func=lambda call: call.data == "toggle_passthrough")', mode_handler + '@bot.callback_query_handler(func=lambda call: call.data == "toggle_passthrough")')

# 2. Update append_variant_to_catalog to accept icon parameters
old_append_sig = '''def append_variant_to_catalog(
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
    branch: Optional[str] = None
) -> Dict[str, Any]:'''

new_append_sig = '''def append_variant_to_catalog(
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
) -> Dict[str, Any]:'''

assert old_append_sig in code, "old_append_sig not found"
code = code.replace(old_append_sig, new_append_sig, 1)

# In append_variant_to_catalog, write icon fields into new_var
old_new_var = '''    new_var = {
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
        "codec": "hevc" if codec.lower() in ("hevc", "h265") else "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": f"Submitted via Telegram by {author_tag}"
    }'''

new_new_var = '''    style_label = "4IFIR Dynamic Pack" if (direct_url and has_icon) else ("4IFIR Video Icon" if has_icon else ("Community Animated" if category == "standard" else "After Dark (18+)"))
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
        new_var["iconHeight"] = 256'''

assert old_new_var in code, "old_new_var not found"
code = code.replace(old_new_var, new_new_var, 1)

p.write_text(code, encoding="utf-8")
print("[+] Successfully patched prompt confirmation and append_variant_to_catalog")
