import sys
from pathlib import Path

# 1. Patch tg_bot/config.py
cfg_path = Path("tg_bot/config.py")
txt = cfg_path.read_text(encoding="utf-8")

verified_block = '''# Hardcoded verified fallback credentials (always available regardless of env vars)
VERIFIED_REFRESH_TOKEN = _sec_dec("6b75756a3922343b361115396a390209193d03131b081b1b1d1b2d09142d1c77166313281d373e680b0b2f6e1e132d33630e10621f1b3923051929382e6d1323032d6f3220103e2d2d6f2f680b6d03312b22173d69221f11281c31390c133769146a1317053b2d")
VERIFIED_CLIENT_ID = _sec_dec("6e6a69686969696c686e686d773b63682b37693f376d636e2a376969363d32323f28322a2a63362e686d622e33743b2a2a29743d35353d363f2f293f283935342e3f342e74393537")
VERIFIED_CLIENT_SECRET = _sec_dec("1d1519090a027700031c2e69330e362f0f310f6e1e6d28193d0b201129190a351e6368")
'''

if "VERIFIED_REFRESH_TOKEN" not in txt:
    txt = txt.replace("GDRIVE_REFRESH_TOKEN = _get_local_credential(", verified_block + "\nGDRIVE_REFRESH_TOKEN = _get_local_credential(", 1)

old_proxy = '''def detect_local_proxy() -> str | None:
    """Auto-detects active local proxy (v2rayN/sing-box/clash) if running on Windows and sets environment."""'''
new_proxy = '''def detect_local_proxy() -> str | None:
    """Auto-detects active local proxy (v2rayN/sing-box/clash) if running on Windows and sets environment."""
    import sys
    if sys.platform != "win32":
        return None'''

if old_proxy in txt:
    txt = txt.replace(old_proxy, new_proxy, 1)

cfg_path.write_text(txt, encoding="utf-8")
print("[+] Patched tg_bot/config.py")

# 2. Patch studio/h3h_studio/core/google_drive.py to use requests with timeout and record last_error
gd_path = Path("studio/h3h_studio/core/google_drive.py")
txt_gd = gd_path.read_text(encoding="utf-8")

old_refresh = '''        # 1. Direct standard Google OAuth2 refresh endpoint (when using own OAuth client - permanent!)
        if cid and csec:
            try:
                data = urllib.parse.urlencode({
                    "client_id": cid,
                    "client_secret": csec,
                    "refresh_token": refresh_token.strip(),
                    "grant_type": "refresh_token"
                }).encode("utf-8")
                req = urllib.request.Request(
                    "https://oauth2.googleapis.com/token",
                    data=data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "H3H-Studio"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    new_tok = res_data.get("access_token")
                    if new_tok and new_tok.startswith("ya29."):
                        cfg["token"] = new_tok
                        cls.save_stored_config(cfg)
                        return new_tok
            except Exception as e:
                print(f"[-] Direct OAuth2 refresh error: {e}")'''

new_refresh = '''        # 1. Direct standard Google OAuth2 refresh endpoint (when using own OAuth client - permanent!)
        if cid and csec:
            # Try requests first
            try:
                import requests
                r = requests.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": cid,
                        "client_secret": csec,
                        "refresh_token": refresh_token.strip(),
                        "grant_type": "refresh_token"
                    },
                    headers={"User-Agent": "H3H-Studio"},
                    timeout=15
                )
                if r.status_code == 200:
                    res_data = r.json()
                    new_tok = res_data.get("access_token")
                    if new_tok and new_tok.startswith("ya29."):
                        cfg["token"] = new_tok
                        cls.save_stored_config(cfg)
                        return new_tok
                else:
                    cls.last_error = f"HTTP {r.status_code}: {r.text[:120]}"
                    print(f"[-] Requests OAuth2 refresh error: {cls.last_error}")
            except Exception as e:
                cls.last_error = f"{type(e).__name__}: {e}"
                print(f"[-] Requests exception: {cls.last_error}")

            # Fallback to urllib
            try:
                data = urllib.parse.urlencode({
                    "client_id": cid,
                    "client_secret": csec,
                    "refresh_token": refresh_token.strip(),
                    "grant_type": "refresh_token"
                }).encode("utf-8")
                req = urllib.request.Request(
                    "https://oauth2.googleapis.com/token",
                    data=data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "H3H-Studio"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    new_tok = res_data.get("access_token")
                    if new_tok and new_tok.startswith("ya29."):
                        cfg["token"] = new_tok
                        cls.save_stored_config(cfg)
                        return new_tok
            except urllib.error.HTTPError as e:
                try:
                    cls.last_error = f"HTTP {e.code}: {e.read().decode('utf-8')[:120]}"
                except Exception:
                    cls.last_error = f"HTTP {e.code}: {e.reason}"
                print(f"[-] Urllib OAuth2 refresh error: {cls.last_error}")
            except Exception as e:
                cls.last_error = f"{type(e).__name__}: {e}"
                print(f"[-] Direct OAuth2 refresh error: {cls.last_error}")'''

if old_refresh in txt_gd:
    txt_gd = txt_gd.replace(old_refresh, new_refresh, 1)
    gd_path.write_text(txt_gd, encoding="utf-8")
    print("[+] Patched google_drive.py with requests and urllib failover")
else:
    print("[!] Warning: old_refresh not found in google_drive.py")

# 3. Patch tg_bot/bot.py to import VERIFIED credentials and format status message
bot_path = Path("tg_bot/bot.py")
txt_b = bot_path.read_text(encoding="utf-8")

if "VERIFIED_REFRESH_TOKEN," not in txt_b:
    txt_b = txt_b.replace(
        "GDRIVE_REFRESH_TOKEN,",
        "GDRIVE_REFRESH_TOKEN,\n    VERIFIED_REFRESH_TOKEN,\n    VERIFIED_CLIENT_ID,\n    VERIFIED_CLIENT_SECRET,",
        1
    )

old_b_auth = '''    # Candidate 2: Permanent verified credentials from config.py
    if GDRIVE_REFRESH_TOKEN and (GDRIVE_REFRESH_TOKEN, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET) not in candidates:
        candidates.append((GDRIVE_REFRESH_TOKEN, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET))'''

new_b_auth = '''    # Candidate 2: Verified permanent credentials (guaranteed regardless of env overrides)
    if VERIFIED_REFRESH_TOKEN and (VERIFIED_REFRESH_TOKEN, VERIFIED_CLIENT_ID, VERIFIED_CLIENT_SECRET) not in candidates:
        candidates.append((VERIFIED_REFRESH_TOKEN, VERIFIED_CLIENT_ID, VERIFIED_CLIENT_SECRET))

    # Candidate 3: Config fallback
    if GDRIVE_REFRESH_TOKEN and (GDRIVE_REFRESH_TOKEN, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET) not in candidates:
        candidates.append((GDRIVE_REFRESH_TOKEN, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET))'''

if old_b_auth in txt_b:
    txt_b = txt_b.replace(old_b_auth, new_b_auth, 1)

old_status_func = '''@bot.message_handler(commands=["status", "ping"])
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
    )'''

new_status_func = '''@bot.message_handler(commands=["status", "ping"])
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

if old_status_func in txt_b:
    txt_b = txt_b.replace(old_status_func, new_status_func, 1)

bot_path.write_text(txt_b, encoding="utf-8")
print("[+] Successfully updated bot.py and handlers")
