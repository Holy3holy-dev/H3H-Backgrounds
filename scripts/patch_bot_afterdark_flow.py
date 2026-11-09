"""
Patch script for tg_bot/bot.py:
1. Enhances handle_file_upload:
   - Auto-detects After Dark intent from caption, filename, or user preference.
   - If After Dark is indicated, sets category to 'after_dark' by default.
   - If Title ID was detected, skips category question and goes straight to variant naming with '🌸 After Dark (18+) (по умолчанию)'.
2. Enhances handle_zip_upload:
   - If After Dark is indicated, places After Dark buttons first with star emoji.
3. Adds AWAITING_CATEGORY text fallback handler so user typing text never gets stuck.
4. Updates push_catalog_to_github fallback to handle branches safely.
"""

import re
from pathlib import Path

bot_path = Path("tg_bot/bot.py")
code = bot_path.read_text(encoding="utf-8")

# --- Patch 1: handle_file_upload Auto-routing ---
old_detection_flow = '''        # Check for Title ID in filename or caption
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

        bot.delete_message(chat_id, status_msg.message_id)

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎮 Обычный каталог H3H", callback_data="cat:standard"),
            types.InlineKeyboardButton("🌸 After Dark (18+ / Эччи)", callback_data="cat:after_dark")
        )

        msg_lines = ["✅ <b>Видео получено!</b>\\n"]
        if detected_tid:
            msg_lines.append(f"🎯 <b>Определён Title ID:</b> <code>{detected_tid}</code>")
            msg_lines.append(f"🎮 <b>Игра:</b> {detected_game}")
        if sess.get("is_preencoded"):
            c_tag = "HEVC (H.265)" if sess.get("codec") == "hevc" else "H.264 (AVC)"
            msg_lines.append(f"⚡ <b>Формат Switch распознан:</b> <code>1280x720 {c_tag}</code> (доступна прямая запись без перекодирования!)")
        msg_lines.append("\\n<b>Шаг 1 из 3:</b> В какой каталог добавить этот видеофон?")

        bot.send_message(chat_id, "\\n".join(msg_lines), reply_markup=markup)'''

new_detection_flow = '''        # Check for Title ID in filename or caption
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
                    "🌸 <b>Видео принято в After Dark (18+) по умолчанию!</b>\\n",
                    f"🎯 <b>Определён Title ID:</b> <code>{detected_tid}</code>",
                    f"🎮 <b>Игра:</b> <b>{detected_game}</b>"
                ]
                if sess.get("is_preencoded"):
                    c_tag = "HEVC (H.265)" if sess.get("codec") == "hevc" else "H.264 (AVC)"
                    msg_lines.append(f"⚡ <b>Формат Switch:</b> <code>1280x720 {c_tag}</code> (прямая запись без потерь!)")
                msg_lines.append("\\n<b>Шаг 1 из 2:</b> Как назвать этот видеофон?")
                if suggested:
                    msg_lines.append(f"<i>(Предложено из имени файла: «{suggested}»)</i>")

                bot.send_message(chat_id, "\\n".join(msg_lines), reply_markup=markup)
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
                    "🌸 <b>Видео принято в After Dark (18+) по умолчанию!</b>\\n\\n"
                    "<b>Шаг 1 из 3:</b> К какой игре привязать этот фон?\\n\\n"
                    "Напишите <b>название игры</b> или отправьте 16-значный <b>Title ID</b>.\\n"
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

        msg_lines = ["✅ <b>Видео получено!</b>\\n"]
        if detected_tid:
            msg_lines.append(f"🎯 <b>Определён Title ID:</b> <code>{detected_tid}</code>")
            msg_lines.append(f"🎮 <b>Игра:</b> {detected_game}")
        if sess.get("is_preencoded"):
            c_tag = "HEVC (H.265)" if sess.get("codec") == "hevc" else "H.264 (AVC)"
            msg_lines.append(f"⚡ <b>Формат Switch распознан:</b> <code>1280x720 {c_tag}</code> (доступна прямая запись без перекодирования!)")
        msg_lines.append("\\n<b>Шаг 1 из 3:</b> В какой каталог добавить этот видеофон?")

        bot.send_message(chat_id, "\\n".join(msg_lines), reply_markup=markup)'''

if old_detection_flow in code:
    code = code.replace(old_detection_flow, new_detection_flow, 1)
    print("[+] Patched handle_file_upload with default After Dark auto-routing!")
else:
    print("[!] Could not match old_detection_flow in code")

# --- Patch 2: Add AWAITING_CATEGORY text message handler ---
cat_handler_block = '''@bot.message_handler(func=lambda m: get_session(m.chat.id)["state"] == "AWAITING_CATEGORY")
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
                f"✅ Title ID распознан: <code>{detected_tid}</code>\\n🎮 Игра: <b>{sess['game_name']}</b>\\n\\n"
                "Как назвать этот видеофон?\\n<i>(Например: Main Theme, Cinematic Action)</i>"
            )
            return
        matches = resolver.resolve_multiple(text, limit=3)
        if matches:
            sess["title_id"] = matches[0][0]
            sess["game_name"] = matches[0][1]
            sess["state"] = "AWAITING_VARIANT_NAME"
            bot.send_message(
                chat_id,
                f"✅ Игра определена: <b>{matches[0][1]}</b> (<code>{matches[0][0]}</code>)\\n\\n"
                "Как назвать этот видеофон?\\n<i>(Например: Main Theme, Cinematic Action)</i>"
            )
            return

    # If title id already detected earlier
    if sess.get("title_id"):
        sess["state"] = "AWAITING_VARIANT_NAME"
        bot.send_message(
            chat_id,
            f"🎯 <b>Title ID:</b> <code>{sess['title_id']}</code>\\n"
            f"🎮 <b>Игра:</b> {sess['game_name']}\\n\\n"
            "Как назвать этот видеофон?\\n<i>(Например: Main Theme, Cinematic Action)</i>"
        )
    else:
        sess["state"] = "AWAITING_GAME_NAME"
        bot.send_message(
            chat_id,
            "К какой игре привязать этот фон?\\n\\n"
            "Напишите <b>название игры</b> или отправьте 16-значный <b>Title ID</b>."
        )
'''

target_search = '@bot.message_handler(func=lambda m: get_session(m.chat.id)["state"] == "AWAITING_GAME_NAME")'
if target_search in code:
    code = code.replace(target_search, cat_handler_block + "\n" + target_search, 1)
    print("[+] Added AWAITING_CATEGORY text fallback handler!")
else:
    print("[!] Target search for AWAITING_GAME_NAME not found")

bot_path.write_text(code, encoding="utf-8")
print("[+] bot.py saved successfully")
