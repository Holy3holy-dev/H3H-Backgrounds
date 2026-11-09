with open('tg_bot/bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

fixed_cmds = '''@bot.message_handler(commands=["afterdark", "ad", "nsfw", "ecchi"])
def cmd_afterdark_mode(message: types.Message):
    chat_id = message.chat.id
    set_user_category_pref(chat_id, "after_dark")
    sess = get_session(chat_id)
    sess["category"] = "after_dark"
    bot.reply_to(
        message,
        "🌸 <b>Режим After Dark (18+) АКТИВИРОВАН ПО УМОЛЧАНИЮ!</b>\\n\\n"
        "Теперь все ваши загружаемые ролики будут автоматически публиковаться в каталог <b>After Dark</b> (ветка <code>after-dark</code>).\\n\\n"
        "💡 <i>Чтобы переключиться обратно на семейный/основной каталог, отправьте /standard</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["standard", "main"])
def cmd_standard_mode(message: types.Message):
    chat_id = message.chat.id
    set_user_category_pref(chat_id, "standard")
    sess = get_session(chat_id)
    sess["category"] = "standard"
    bot.reply_to(
        message,
        "🎮 <b>Режим Обычного каталога H3H активирован!</b>\\n\\n"
        "Все загружаемые ролики будут публиковаться в основной каталог на ветку <code>main</code>.\\n\\n"
        "💡 <i>Чтобы включить After Dark по умолчанию, отправьте /afterdark</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["mode"])
def cmd_show_mode(message: types.Message):
    chat_id = message.chat.id
    pref = get_user_category_pref(chat_id)
    mode_str = "🌸 After Dark (18+)" if pref == "after_dark" else "🎮 Обычный каталог H3H"
    bot.reply_to(
        message,
        f"⚙️ <b>Текущий режим загрузки:</b> <b>{mode_str}</b>\\n\\n"
        "• Для After Dark по умолчанию: /afterdark\\n"
        "• Для обычного каталога: /standard",
        parse_mode="HTML"
    )
'''

pattern = r'@bot\.message_handler\(commands=\["afterdark", "ad", "nsfw", "ecchi"\]\)[\s\S]*?(?=@bot\.message_handler\(commands=\["cancel"\]\))'
text = re.sub(pattern, fixed_cmds + '\n', text)

with open('tg_bot/bot.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('[+] Fixed command strings in bot.py')
