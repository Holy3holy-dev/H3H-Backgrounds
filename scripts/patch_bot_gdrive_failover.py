from pathlib import Path

bot_py = Path("tg_bot/bot.py")
text = bot_py.read_text(encoding="utf-8")

old_get_gdrive = '''def get_gdrive_auth(category: str = "standard") -> Tuple[Optional[str], Optional[str]]:
    """Returns (access_token, folder_id) for Google Drive operations based on category."""
    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = os.getenv("GDRIVE_REFRESH_TOKEN") or GDRIVE_REFRESH_TOKEN or gdrive_cfg.get("refresh_token")
    client_id = os.getenv("GDRIVE_CLIENT_ID") or GDRIVE_CLIENT_ID or gdrive_cfg.get("client_id")
    client_secret = os.getenv("GDRIVE_CLIENT_SECRET") or GDRIVE_CLIENT_SECRET or gdrive_cfg.get("client_secret")

    access_tok = GoogleDriveHelper.refresh_access_token(
        refresh_token=refresh_tok,
        client_id=client_id,
        client_secret=client_secret
    )
    if not access_tok:
        cand = gdrive_cfg.get("token")
        if cand:
            test = GoogleDriveClient.test_connection(cand)
            if test.get("ok"):
                access_tok = cand
    else:
        gdrive_cfg["token"] = access_tok
        GoogleDriveHelper.save_stored_config(gdrive_cfg)

    if category == "after_dark":
        folder_id = (
            os.getenv("GDRIVE_AFTER_DARK_FOLDER_ID")
            or GDRIVE_AFTER_DARK_FOLDER_ID
            or gdrive_cfg.get("after_dark_folder_id")
            or "1SXWjp12pKxPPT6YRMZ7tle8cgZdrKkHk"
        )
    else:
        folder_id = (
            os.getenv("GDRIVE_FOLDER_ID")
            or GDRIVE_FOLDER_ID
            or gdrive_cfg.get("project_folder_id")
            or gdrive_cfg.get("folder_id")
            or "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
        )
    return access_tok, folder_id'''

new_get_gdrive = '''def get_gdrive_auth(category: str = "standard") -> Tuple[Optional[str], Optional[str]]:
    """Returns (access_token, folder_id) for Google Drive operations based on category with robust failover."""
    gdrive_cfg = GoogleDriveHelper.get_stored_config()

    candidates = []
    # Candidate 1: Environment variable
    env_tok = (os.getenv("GDRIVE_REFRESH_TOKEN") or "").strip()
    env_cid = (os.getenv("GDRIVE_CLIENT_ID") or "").strip() or GDRIVE_CLIENT_ID
    env_sec = (os.getenv("GDRIVE_CLIENT_SECRET") or "").strip() or GDRIVE_CLIENT_SECRET
    if env_tok:
        candidates.append((env_tok, env_cid, env_sec))

    # Candidate 2: Permanent verified credentials from config.py
    if GDRIVE_REFRESH_TOKEN and (GDRIVE_REFRESH_TOKEN, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET) not in candidates:
        candidates.append((GDRIVE_REFRESH_TOKEN, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET))

    # Candidate 3: Stored config
    cfg_tok = (gdrive_cfg.get("refresh_token") or "").strip()
    cfg_cid = (gdrive_cfg.get("client_id") or "").strip() or GDRIVE_CLIENT_ID
    cfg_sec = (gdrive_cfg.get("client_secret") or "").strip() or GDRIVE_CLIENT_SECRET
    if cfg_tok and (cfg_tok, cfg_cid, cfg_sec) not in candidates:
        candidates.append((cfg_tok, cfg_cid, cfg_sec))

    access_tok = None
    for r_tok, c_id, c_sec in candidates:
        try:
            tok = GoogleDriveHelper.refresh_access_token(
                refresh_token=r_tok,
                client_id=c_id,
                client_secret=c_sec
            )
            if tok and tok.startswith("ya29."):
                access_tok = tok
                break
        except Exception:
            continue

    if not access_tok:
        cand = gdrive_cfg.get("token")
        if cand:
            test = GoogleDriveClient.test_connection(cand)
            if test.get("ok"):
                access_tok = cand
    else:
        gdrive_cfg["token"] = access_tok
        try:
            GoogleDriveHelper.save_stored_config(gdrive_cfg)
        except Exception:
            pass

    if category == "after_dark":
        folder_id = (
            os.getenv("GDRIVE_AFTER_DARK_FOLDER_ID")
            or GDRIVE_AFTER_DARK_FOLDER_ID
            or gdrive_cfg.get("after_dark_folder_id")
            or "1SXWjp12pKxPPT6YRMZ7tle8cgZdrKkHk"
        )
    else:
        folder_id = (
            os.getenv("GDRIVE_FOLDER_ID")
            or GDRIVE_FOLDER_ID
            or gdrive_cfg.get("project_folder_id")
            or gdrive_cfg.get("folder_id")
            or "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
        )
    return access_tok, folder_id'''

if old_get_gdrive in text:
    text = text.replace(old_get_gdrive, new_get_gdrive)
    print("[+] Patched get_gdrive_auth with multi-candidate failover")
else:
    old_crlf = old_get_gdrive.replace("\n", "\r\n")
    if old_crlf in text:
        text = text.replace(old_crlf, new_get_gdrive.replace("\n", "\r\n"))
        print("[+] Patched get_gdrive_auth with multi-candidate failover (CRLF)")
    else:
        print("[!] Warning: old_get_gdrive pattern not found")

# Add /status command
old_start = '@bot.message_handler(commands=["start", "help"])'
new_start = '''@bot.message_handler(commands=["status", "ping"])
def handle_status(message: types.Message):
    access_tok, folder_id = get_gdrive_auth("standard")
    gdrive_status = "✅ Авторизован (токен получен)" if access_tok else "❌ Токен не получен"
    bot.reply_to(
        message,
        f"🤖 <b>H3H Uploader Bot Status</b>\\n\\n"
        f"• <b>Версия:</b> v1.3.3-cloud\\n"
        f"• <b>Google Drive:</b> {gdrive_status}\\n"
        f"• <b>Папка Диска:</b> <code>{folder_id}</code>\\n"
        f"• <b>Каталог:</b> {len(resolver.games)} игр в базе\\n\\n"
        f"<i>Сервер работает 24/7 в облаке. Можете отправлять видеофайлы!</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["start", "help"])'''

if old_start in text:
    text = text.replace(old_start, new_start, 1)
    print("[+] Added /status command handler")

bot_py.write_text(text, encoding="utf-8")
print("[+] Successfully updated tg_bot/bot.py")
