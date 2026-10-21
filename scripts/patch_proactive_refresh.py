from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8")

old_func = '''def get_gdrive_credentials() -> Tuple[str, str]:
    if GDRIVE_CFG_PATH.exists():
        try:
            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
            tok = cfg.get("token") or DEFAULT_TOKEN
            f_id = cfg.get("folder_id") or cfg.get("project_folder_id") or DEFAULT_FOLDER_ID
            return tok.strip(), f_id.strip()
        except Exception:
            pass
    return DEFAULT_TOKEN, DEFAULT_FOLDER_ID'''

new_func = '''def get_gdrive_credentials() -> Tuple[str, str]:
    if GDRIVE_CFG_PATH.exists():
        try:
            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
            tok = cfg.get("token") or DEFAULT_TOKEN
            ref = cfg.get("refresh_token")
            f_id = cfg.get("folder_id") or cfg.get("project_folder_id") or DEFAULT_FOLDER_ID

            # If token expired or close to expiry, auto-refresh via refresh_token silently
            test_res = GoogleDriveClient.test_connection(tok)
            if not test_res.get("ok") and ref:
                print("  [*] Автоматическое обновление токена Google Drive через Refresh Token...")
                new_tok = GoogleDriveHelper.refresh_access_token(ref)
                if new_tok:
                    cfg["token"] = new_tok
                    GDRIVE_CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                    return new_tok.strip(), f_id.strip()

            return tok.strip(), f_id.strip()
        except Exception:
            pass
    return DEFAULT_TOKEN, DEFAULT_FOLDER_ID'''

assert old_func in text, "old_func not found in auto_harvest_pipeline.py"
text = text.replace(old_func, new_func)
p.write_text(text, encoding="utf-8")
print("Proactive auto-refresh added to get_gdrive_credentials!")
