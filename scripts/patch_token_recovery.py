import sys
from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8")

# 1. Add line buffering to top
text = text.replace(
    "sys.stdout.reconfigure(encoding='utf-8')\nsys.stderr.reconfigure(encoding='utf-8')",
    "sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)\nsys.stderr.reconfigure(encoding='utf-8', line_buffering=True)"
)

# 2. Add save_gdrive_token and prompt_new_gdrive_token functions
token_helpers = '''
def save_gdrive_token(new_token: str) -> None:
    try:
        cfg = {}
        if GDRIVE_CFG_PATH.exists():
            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
        cfg["token"] = new_token.strip()
        GDRIVE_CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[-] Failed to save updated token to {GDRIVE_CFG_PATH}: {e}")


def prompt_new_gdrive_token() -> str:
    """Interactive recovery handler when Google Drive access token expires."""
    print("\\n" + "=" * 68)
    print("  🔑 [ВНИМАНИЕ] Срок действия токена Google Drive (1 час) истек!")
    print("=" * 68)
    print("  1. Зайдите в Google OAuth Playground (developers.google.com/oauthplayground)")
    print("     или откройте H3H-Studio -> 'Управление каталогом'.")
    print("  2. В OAuth Playground нажмите кнопку 'Refresh access token' (или Exchange)")
    print("     и скопируйте новый Access token (начинается с ya29...).")
    print("  3. Вставьте его сюда и нажмите Enter:")
    print("=" * 68)

    while True:
        try:
            val = input(">> Вставьте новый Access Token (ya29...): ").strip()
        except (EOFError, KeyboardInterrupt):
            val = ""

        if not val:
            # Re-read from disk in case user saved it in studio or file
            cfg_tok, _ = get_gdrive_credentials()
            val = cfg_tok

        print("  [*] Проверка токена связи с Google Drive...")
        res = GoogleDriveClient.test_connection(val)
        if res.get("ok"):
            user_name = res.get("displayName") or res.get("user") or "Успешно"
            print(f"  [✓] Авторизация успешна! Аккаунт: {user_name}\\n")
            save_gdrive_token(val)
            return val
        else:
            err = res.get("error", "Неверный токен")
            print(f"  [-] Токен не подошел: {err}. Пожалуйста, попробуйте еще раз.")
'''

if "def prompt_new_gdrive_token" not in text:
    target_place = "def clean_game_title(raw_title: str) -> str:"
    text = text.replace(target_place, token_helpers + "\n\n" + target_place)

# 3. Replace upload block with retry and 401 recovery
old_upload = '''            # Upload to Google Drive
            print(f"  [*] Uploading to Google Drive...")
            try:
                gdrive_res = GoogleDriveClient.upload_file(
                    file_path=out_file,
                    folder_id=folder_id,
                    token=gdrive_token
                )
                drive_id = gdrive_res["id"]
                dl_url = f"https://drive.google.com/uc?export=download&id={drive_id}"
                thumb_url = f"https://drive.google.com/thumbnail?id={drive_id}&sz=w640"
                print(f"  [✓] Uploaded! Drive ID: {drive_id}")
            except Exception as ue:
                print(f"  [-] Google Drive upload failed: {ue}")
                continue'''

new_upload = '''            # Upload to Google Drive (with automatic 401 expiry recovery)
            print(f"  [*] Uploading to Google Drive...")
            uploaded = False
            drive_id = ""
            dl_url = ""
            thumb_url = ""

            for upload_attempt in range(3):
                try:
                    gdrive_res = GoogleDriveClient.upload_file(
                        file_path=out_file,
                        folder_id=folder_id,
                        token=gdrive_token
                    )
                    drive_id = gdrive_res["id"]
                    dl_url = f"https://drive.google.com/uc?export=download&id={drive_id}"
                    thumb_url = f"https://drive.google.com/thumbnail?id={drive_id}&sz=w640"
                    print(f"  [✓] Uploaded! Drive ID: {drive_id}")
                    uploaded = True
                    break
                except Exception as ue:
                    err_str = str(ue)
                    if "401" in err_str or "Unauthorized" in err_str or "Invalid Credentials" in err_str:
                        gdrive_token = prompt_new_gdrive_token()
                        continue
                    else:
                        print(f"  [-] Google Drive upload failed: {ue}")
                        break

            if not uploaded:
                print(f"  [-] Skipping {clean_title} due to upload error.")
                continue'''

assert old_upload in text, "old_upload block not found in auto_harvest_pipeline.py"
text = text.replace(old_upload, new_upload)

p.write_text(text, encoding="utf-8")
print("Successfully enhanced auto_harvest_pipeline.py with token recovery and line buffering!")
