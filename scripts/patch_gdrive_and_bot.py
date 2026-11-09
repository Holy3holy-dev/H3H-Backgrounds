import re
from pathlib import Path

# 1. Patch studio/h3h_studio/core/google_drive.py
p_gdrive = Path(r"E:\videofon\studio\h3h_studio\core\google_drive.py")
txt = p_gdrive.read_text(encoding="utf-8")

# Ensure get_stored_config checks permanent_gdrive_credentials.txt
if "permanent_gdrive_credentials.txt" not in txt:
    target = '        # Override / inject from environment variables (for Docker / Render cloud deployment)'
    injection = '''        # Fallback to permanent_gdrive_credentials.txt if not in cfg
        try:
            cred_file = Path(__file__).parent.parent.parent.parent / "permanent_gdrive_credentials.txt"
            if cred_file.exists():
                for line in cred_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("GDRIVE_REFRESH_TOKEN=") and not cfg.get("refresh_token"):
                        cfg["refresh_token"] = line.split("=", 1)[1].strip()
                    elif line.startswith("GDRIVE_CLIENT_ID=") and not cfg.get("client_id"):
                        cfg["client_id"] = line.split("=", 1)[1].strip()
                    elif line.startswith("GDRIVE_CLIENT_SECRET=") and not cfg.get("client_secret"):
                        cfg["client_secret"] = line.split("=", 1)[1].strip()
        except Exception:
            pass

        # Override / inject from environment variables (for Docker / Render cloud deployment)'''
    txt = txt.replace(target, injection, 1)

# Ensure refresh_access_token saves fresh token
target_tok = '''                    new_tok = res_data.get("access_token")
                    if new_tok and new_tok.startswith("ya29."):
                        return new_tok'''
repl_tok = '''                    new_tok = res_data.get("access_token")
                    if new_tok and new_tok.startswith("ya29."):
                        cfg["token"] = new_tok
                        cls.save_stored_config(cfg)
                        return new_tok'''
if target_tok in txt:
    txt = txt.replace(target_tok, repl_tok, 1)

p_gdrive.write_text(txt, encoding="utf-8")
print("[+] Patched google_drive.py")

# 2. Patch tg_bot/config.py
p_cfg = Path(r"E:\videofon\tg_bot\config.py")
txt_cfg = p_cfg.read_text(encoding="utf-8")

proxy_func_old = '''def detect_local_proxy() -> str | None:
    """Auto-detects active local proxy (v2rayN/sing-box/clash) if running on Windows."""
    for port in [10809, 7890, 10808, 8080]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                s.close()
                return f"http://127.0.0.1:{port}"
            s.close()
        except Exception:
            pass
    return None'''

proxy_func_new = '''def detect_local_proxy() -> str | None:
    """Auto-detects active local proxy (v2rayN/sing-box/clash) if running on Windows and sets environment."""
    for port in [10809, 7890, 10808, 8080]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                s.close()
                proxy_url = f"http://127.0.0.1:{port}"
                os.environ["HTTP_PROXY"] = proxy_url
                os.environ["HTTPS_PROXY"] = proxy_url
                os.environ["http_proxy"] = proxy_url
                os.environ["https_proxy"] = proxy_url
                return proxy_url
            s.close()
        except Exception:
            pass
    return None'''

if proxy_func_old in txt_cfg:
    txt_cfg = txt_cfg.replace(proxy_func_old, proxy_func_new, 1)
    p_cfg.write_text(txt_cfg, encoding="utf-8")
    print("[+] Patched tg_bot/config.py")

# 3. Patch tg_bot/bot.py
p_bot = Path(r"E:\videofon\tg_bot\bot.py")
txt_bot = p_bot.read_text(encoding="utf-8")

# Update imports in bot.py
old_import = '''    GDRIVE_REFRESH_TOKEN,
    ADMIN_IDS,'''
new_import = '''    GDRIVE_REFRESH_TOKEN,
    GDRIVE_CLIENT_ID,
    GDRIVE_CLIENT_SECRET,
    ADMIN_IDS,'''
if old_import in txt_bot:
    txt_bot = txt_bot.replace(old_import, new_import, 1)

# Update get_gdrive_auth in bot.py
old_auth = '''def get_gdrive_auth(category: str = "standard") -> Tuple[Optional[str], Optional[str]]:
    """Returns (access_token, folder_id) for Google Drive operations based on category."""
    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = os.getenv("GDRIVE_REFRESH_TOKEN") or GDRIVE_REFRESH_TOKEN or gdrive_cfg.get("refresh_token")
    access_tok = GoogleDriveHelper.refresh_access_token(refresh_tok) or gdrive_cfg.get("token")

    if category == "after_dark":'''

new_auth = '''def get_gdrive_auth(category: str = "standard") -> Tuple[Optional[str], Optional[str]]:
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

    if category == "after_dark":'''

if old_auth in txt_bot:
    txt_bot = txt_bot.replace(old_auth, new_auth, 1)

# Ensure local proxy sets environment variables in bot.py startup
old_proxy_init = '''local_proxy = detect_local_proxy()
if local_proxy:
    print(f"[*] Detected local proxy on {local_proxy}, configuring telebot...")
    from telebot import apihelper
    apihelper.proxy = {'http': local_proxy, 'https': local_proxy}'''

new_proxy_init = '''local_proxy = detect_local_proxy()
if local_proxy:
    print(f"[*] Detected local proxy on {local_proxy}, configuring telebot & urllib...")
    from telebot import apihelper
    apihelper.proxy = {'http': local_proxy, 'https': local_proxy}
    os.environ["HTTP_PROXY"] = local_proxy
    os.environ["HTTPS_PROXY"] = local_proxy
    os.environ["http_proxy"] = local_proxy
    os.environ["https_proxy"] = local_proxy'''

if old_proxy_init in txt_bot:
    txt_bot = txt_bot.replace(old_proxy_init, new_proxy_init, 1)

p_bot.write_text(txt_bot, encoding="utf-8")
print("[+] Patched tg_bot/bot.py")
