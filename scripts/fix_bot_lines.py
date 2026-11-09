with open('tg_bot/bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if '@bot.message_handler(commands=["afterdark"' in line:
        start_idx = i
    if '@bot.message_handler(commands=["cancel"])' in line:
        end_idx = i
        break

print('start:', start_idx, 'end:', end_idx)
new_lines = [
    '@bot.message_handler(commands=["afterdark", "ad", "nsfw", "ecchi"])\n',
    'def cmd_afterdark_mode(message: types.Message):\n',
    '    chat_id = message.chat.id\n',
    '    set_user_category_pref(chat_id, "after_dark")\n',
    '    sess = get_session(chat_id)\n',
    '    sess["category"] = "after_dark"\n',
    '    bot.reply_to(\n',
    '        message,\n',
    '        "🌸 <b>Режим After Dark (18+) АКТИВИРОВАН ПО УМОЛЧАНИЮ!</b>\\n\\n"\n',
    '        "Теперь все ваши загружаемые ролики будут автоматически публиковаться в каталог <b>After Dark</b> (ветка <code>after-dark</code>).\\n\\n"\n',
    '        "💡 <i>Чтобы переключиться обратно на семейный/основной каталог, отправьте /standard</i>",\n',
    '        parse_mode="HTML"\n',
    '    )\n\n',
    '@bot.message_handler(commands=["standard", "main"])\n',
    'def cmd_standard_mode(message: types.Message):\n',
    '    chat_id = message.chat.id\n',
    '    set_user_category_pref(chat_id, "standard")\n',
    '    sess = get_session(chat_id)\n',
    '    sess["category"] = "standard"\n',
    '    bot.reply_to(\n',
    '        message,\n',
    '        "🎮 <b>Режим Обычного каталога H3H активирован!</b>\\n\\n"\n',
    '        "Все загружаемые ролики будут публиковаться в основной каталог на ветку <code>main</code>.\\n\\n"\n',
    '        "💡 <i>Чтобы включить After Dark по умолчанию, отправьте /afterdark</i>",\n',
    '        parse_mode="HTML"\n',
    '    )\n\n',
    '@bot.message_handler(commands=["mode"])\n',
    'def cmd_show_mode(message: types.Message):\n',
    '    chat_id = message.chat.id\n',
    '    pref = get_user_category_pref(chat_id)\n',
    '    mode_str = "🌸 After Dark (18+)" if pref == "after_dark" else "🎮 Обычный каталог H3H"\n',
    '    bot.reply_to(\n',
    '        message,\n',
    '        f"⚙️ <b>Текущий режим загрузки:</b> <b>{mode_str}</b>\\n\\n"\n',
    '        "• Для After Dark по умолчанию: /afterdark\\n"\n',
    '        "• Для обычного каталога: /standard",\n',
    '        parse_mode="HTML"\n',
    '    )\n\n'
]

lines[start_idx:end_idx] = new_lines

with open('tg_bot/bot.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('[+] Successfully replaced lines!')
