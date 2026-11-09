from pathlib import Path

p = Path("tg_bot/bot.py")
code = p.read_text(encoding="utf-8")

old_status = '''@bot.message_handler(commands=["status", "ping"])
def handle_status(message: types.Message):
    access_tok, folder_id = get_gdrive_auth("standard")
    last_err = getattr(GoogleDriveHelper, "last_error", "Нет деталей")
    if access_tok:
        gdrive_status = "✅ Авторизован (токен получен)"
    else:
        gdrive_status = f"❌ Ошибка: {last_err}"
    bot.reply_to(
        message,
        f"🤖 <b>H3H Uploader Bot Status</b>\\n\\n"
        f"• <b>Версия:</b> v1.3.3-cloud (rev 2)\\n"
        f"• <b>Google Drive:</b> {gdrive_status}\\n"
        f"• <b>Папка Диска:</b> <code>{folder_id}</code>\\n"
        f"• <b>Каталог:</b> {len(resolver.games)} игр в базе\\n\\n"
        f"<i>Сервер работает 24/7 в облаке. Можете отправлять видеофайлы!</i>",
        parse_mode="HTML"
    )'''

new_status = '''def get_catalog_stats() -> dict:
    std_games = 0
    std_vars = 0
    ad_games = 0
    ad_vars = 0
    try:
        p_std = PROJECT_ROOT / CATALOG_PATH_STANDARD
        if p_std.exists():
            data = json.loads(p_std.read_text(encoding="utf-8"))
            std_games = len(data.get("games", []))
            std_vars = sum(len(g.get("variants", [])) for g in data.get("games", []))
    except Exception:
        pass
    try:
        p_ad = PROJECT_ROOT / CATALOG_PATH_AFTER_DARK
        if p_ad.exists():
            data = json.loads(p_ad.read_text(encoding="utf-8"))
            ad_games = len(data.get("games", []))
            ad_vars = sum(len(g.get("variants", [])) for g in data.get("games", []))
    except Exception:
        pass
    return {
        "std_games": std_games,
        "std_vars": std_vars,
        "ad_games": ad_games,
        "ad_vars": ad_vars,
        "resolver_db": len(resolver.games)
    }

@bot.message_handler(commands=["status", "ping"])
def handle_status(message: types.Message):
    access_tok, folder_id = get_gdrive_auth("standard")
    last_err = getattr(GoogleDriveHelper, "last_error", "Нет деталей")
    if access_tok:
        gdrive_status = "✅ Авторизован (токен получен)"
    else:
        gdrive_status = f"❌ Ошибка: {last_err}"

    stats = get_catalog_stats()
    bot.reply_to(
        message,
        f"🤖 <b>H3H Uploader Bot Status</b>\\n\\n"
        f"• <b>Версия:</b> v1.3.3-cloud\\n"
        f"• <b>Google Drive:</b> {gdrive_status}\\n"
        f"• <b>Каталог H3H:</b> {stats['std_games']} игр ({stats['std_vars']} видеофонов)\\n"
        f"• <b>Каталог After Dark:</b> {stats['ad_games']} игр ({stats['ad_vars']} видеофонов)\\n"
        f"• <b>База поиска Title ID:</b> {stats['resolver_db']} игр (Switch + Homebrew)\\n\\n"
        f"<i>Сервер работает 24/7 в облаке. Можете отправлять видеофайлы!</i>",
        parse_mode="HTML"
    )'''

assert old_status in code, "old_status not found"
code = code.replace(old_status, new_status, 1)

p.write_text(code, encoding="utf-8")
print("[+] Successfully fixed bot status catalog count in tg_bot/bot.py")
