from pathlib import Path
import html

p = Path("tg_bot/bot.py")
content = p.read_text(encoding="utf-8")

old_code = '''def get_catalog_stats() -> dict:
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

new_code = '''def get_catalog_stats() -> dict:
    std_games = 0
    std_vars = 0
    std_icons = 0
    std_icon_titles = []
    ad_games = 0
    ad_vars = 0
    ad_icons = 0
    try:
        p_std = PROJECT_ROOT / CATALOG_PATH_STANDARD
        if p_std.exists():
            data = json.loads(p_std.read_text(encoding="utf-8"))
            std_games = len(data.get("games", []))
            std_vars = sum(len(g.get("variants", [])) for g in data.get("games", []))
            for g in data.get("games", []):
                icons_in_g = sum(1 for v in g.get("variants", []) if v.get("hasIcon") or v.get("iconUrl") or "icon" in v.get("style", "").lower())
                if icons_in_g > 0:
                    std_icons += icons_in_g
                    std_icon_titles.append({
                        "titleId": g.get("titleId", ""),
                        "title": g.get("title", ""),
                        "iconsCount": icons_in_g
                    })
    except Exception:
        pass
    try:
        p_ad = PROJECT_ROOT / CATALOG_PATH_AFTER_DARK
        if p_ad.exists():
            data = json.loads(p_ad.read_text(encoding="utf-8"))
            ad_games = len(data.get("games", []))
            ad_vars = sum(len(g.get("variants", [])) for g in data.get("games", []))
            ad_icons = sum(sum(1 for v in g.get("variants", []) if v.get("hasIcon") or v.get("iconUrl")) for g in data.get("games", []))
    except Exception:
        pass
    return {
        "std_games": std_games,
        "std_vars": std_vars,
        "std_icons": std_icons,
        "std_icon_games": len(std_icon_titles),
        "std_icon_titles": std_icon_titles,
        "ad_games": ad_games,
        "ad_vars": ad_vars,
        "ad_icons": ad_icons,
        "total_icons": std_icons + ad_icons,
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
        f"• <b>Версия:</b> v1.3.4-cloud\\n"
        f"• <b>Google Drive:</b> {gdrive_status}\\n"
        f"• <b>Каталог H3H:</b> {stats['std_games']} игр ({stats['std_vars']} видеофонов)\\n"
        f"• <b>Видеоиконки 4IFIR:</b> {stats['std_icons']} иконок ({stats['std_icon_games']} тайтлов)\\n"
        f"• <b>Каталог After Dark:</b> {stats['ad_games']} игр ({stats['ad_vars']} видеофонов)\\n"
        f"• <b>База поиска Title ID:</b> {stats['resolver_db']} игр (Switch + Homebrew)\\n\\n"
        f"<i>Сервер работает 24/7 в облаке. Можете отправлять видеофайлы!</i>\\n\\n"
        f"💡 <i>Список всех тайтлов с видеоиконками:</i> /icons",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["icons", "videoicons", "iconlist"])
def cmd_list_icons(message: types.Message):
    chat_id = message.chat.id
    query = ""
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) > 1:
        query = parts[1].strip().lower()

    stats = get_catalog_stats()
    icon_titles = stats.get("std_icon_titles", [])

    if query:
        filtered = [t for t in icon_titles if query in t["title"].lower() or query in t["titleId"].lower()]
        if not filtered:
            bot.reply_to(
                message,
                f"🔍 <b>Поиск видеоиконок:</b> <i>'{html.escape(query)}'</i>\\n\\n"
                f"❌ Ничего не найдено по запросу <code>{html.escape(query)}</code>.\\n"
                f"Всего в каталоге {stats['std_icon_games']} игр с видеоиконками. Отправьте /icons для полного списка.",
                parse_mode="HTML"
            )
            return

        lines = [
            f"🔍 <b>Результаты поиска видеоиконок</b> (найдено: {len(filtered)}):\\n"
        ]
        for t in filtered[:35]:
            lines.append(f"• <b>{html.escape(t['title'])}</b>\\n  <code>{t['titleId']}</code> — <i>{t['iconsCount']} вар. иконок</i>")
        
        bot.reply_to(message, "\\n".join(lines), parse_mode="HTML")
        return

    # If no query, send summary and full list
    header = (
        f"🔲 <b>Каталог видеоиконок 4IFIR (256x256)</b>\\n\\n"
        f"• <b>Всего загружено:</b> <b>{stats['std_icons']}</b> видеоиконок\\n"
        f"• <b>Охвачено тайтлов:</b> <b>{stats['std_icon_games']}</b> популярных игр\\n"
        f"• <b>Формат:</b> 256x256 HEVC/H.264, 30fps, 4 сек. бесшовный луп\\n\\n"
        f"💡 <i>Быстрый поиск по названию или Title ID:</i>\\n"
        f"<code>/icons mario</code> или <code>/icons zelda</code>\\n\\n"
        f"📋 <b>Список игр с видеоиконками:</b>\\n"
    )

    sorted_titles = sorted(icon_titles, key=lambda x: x["title"].lower())
    chunk_size = 35
    chunks = [sorted_titles[i:i + chunk_size] for i in range(0, len(sorted_titles), chunk_size)]

    if not chunks:
        bot.send_message(chat_id, header + "\\n<i>В каталоге пока нет видеоиконок.</i>", parse_mode="HTML")
        return

    first = True
    for chunk_idx, chunk in enumerate(chunks, 1):
        msg_lines = []
        if first:
            msg_lines.append(header)
            first = False
        else:
            msg_lines.append(f"📋 <b>Список игр с видеоиконками (часть {chunk_idx}/{len(chunks)}):</b>\\n")

        for t in chunk:
            msg_lines.append(f"• <b>{html.escape(t['title'])}</b> (<code>{t['titleId']}</code>) — <i>{t['iconsCount']} вар.</i>")

        bot.send_message(chat_id, "\\n".join(msg_lines), parse_mode="HTML")'''

norm_content = content.replace("\r\n", "\n")
norm_old = old_code.replace("\r\n", "\n")
norm_new = new_code.replace("\r\n", "\n")

if norm_old in norm_content:
    updated = norm_content.replace(norm_old, norm_new)
    old_start = "• 🌸 Поддерживать как обычный каталог, так и коллекцию <b>After Dark (18+)</b>\\n\\n"
    new_start = "• 🌸 Поддерживать как обычный каталог, так и коллекцию <b>After Dark (18+)</b>\\n• 🔲 <b>/icons</b> — Посмотреть все игры с анимированными видеоиконками 4IFIR\\n\\n"
    if old_start in updated:
        updated = updated.replace(old_start, new_start)
    p.write_text(updated, encoding="utf-8")
    print("[+] Successfully patched tg_bot/bot.py!")
else:
    print("[-] Match not found in tg_bot/bot.py")
