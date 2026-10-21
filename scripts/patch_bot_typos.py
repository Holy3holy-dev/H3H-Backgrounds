import re
from pathlib import Path

bot_file = Path("tg_bot/bot.py")
text = bot_file.read_text(encoding="utf-8")

old_handler = '''@bot.message_handler(func=lambda m: get_session(m.chat.id)["state"] == "AWAITING_GAME_NAME")
def handle_game_name(message: types.Message):
    chat_id = message.chat.id
    sess = get_session(chat_id)
    text = message.text.strip()

    # Check if text is direct 16-hex Title ID
    if len(text) == 16 and all(c in "0123456789ABCDEFabcdef" for c in text):
        sess["title_id"] = text.upper()
        sess["game_name"] = f"Игра ({sess['title_id']})"
        sess["state"] = "AWAITING_VARIANT_NAME"
        bot.send_message(
            chat_id,
            f"✅ <b>Title ID распознан:</b> <code>{sess['title_id']}</code>\\n\\n"
            "<b>Шаг 3 из 4:</b> Как назвать этот вариант видеофона?\\n"
            "<i>(Например: Dynamic Action, Title Screen, Anime Remix)</i>"
        )
        return

    # Use TitleIdResolver
    res = resolver.resolve(text)
    if res:
        tid, name = res
        sess["candidate_tid"] = tid
        sess["candidate_name"] = name

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(f"✅ Да, это {name}", callback_data="confirm_game:yes"),
            types.InlineKeyboardButton("🔍 Ввести другое название или Title ID", callback_data="confirm_game:no")
        )
        bot.send_message(
            chat_id,
            f"🎯 <b>Найдено совпадение:</b>\\n\\n"
            f"🎮 <b>{name}</b>\\n"
            f"🆔 Title ID: <code>{tid}</code>\\n\\n"
            "Подтверждаете привязку к этой игре?",
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id,
            f"⚠️ Не удалось точно определить Title ID по запросу <i>'{text}'</i>.\\n\\n"
            "Пожалуйста, отправьте точный 16-значный <b>Title ID</b> (например, <code>0100F2C0115B6000</code>) "
            "или напишите более точное название игры."
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_game:"))
def handle_confirm_game(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    sess = get_session(chat_id)
    action = call.data.split(":")[1]

    if action == "yes":
        sess["title_id"] = sess.pop("candidate_tid")
        sess["game_name"] = sess.pop("candidate_name")
        sess["state"] = "AWAITING_VARIANT_NAME"

        bot.edit_message_text(
            f"✅ Игра выбрана: <b>{sess['game_name']}</b> (<code>{sess['title_id']}</code>)\\n\\n"
            "<b>Шаг 3 из 4:</b> Как назвать этот видеофон?\\n"
            "<i>(Например: Main Theme, Cinematic Gameplay, Anime Cutscene)</i>",
            chat_id=chat_id,
            message_id=call.message.message_id
        )
    else:
        bot.edit_message_text(
            "Пожалуйста, отправьте 16-значный <b>Title ID</b> или уточнённое название игры сообщением:",
            chat_id=chat_id,
            message_id=call.message.message_id
        )'''

new_handler = '''@bot.message_handler(func=lambda m: get_session(m.chat.id)["state"] == "AWAITING_GAME_NAME")
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
            f"✅ <b>Title ID распознан:</b> <code>{sess['title_id']}</code>\\n\\n"
            "<b>Шаг 3 из 4:</b> Как назвать этот вариант видеофона?\\n"
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
            f"🎯 <b>По запросу '{raw_text}' найдены совпадения:</b>\\n\\n"
            "Выберите нужную игру из списка ниже:",
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id,
            f"⚠️ Не удалось найти игру по запросу <i>'{raw_text}'</i>.\\n\\n"
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
        f"✅ Игра выбрана: <b>{game_name}</b>\\n"
        f"🆔 Title ID: <code>{choice}</code>\\n\\n"
        "<b>Шаг 3 из 4:</b> Как назвать этот видеофон?\\n"
        "<i>(Например: Main Theme, Cinematic Gameplay, Anime Cutscene)</i>",
        chat_id=chat_id,
        message_id=call.message.message_id
    )'''

if old_handler in text:
    text = text.replace(old_handler, new_handler)
    bot_file.write_text(text, encoding="utf-8")
    print("[+] Updated bot.py with interactive typo-tolerant multi-choice flow!")
else:
    print("[-] old_handler not found in bot.py")
