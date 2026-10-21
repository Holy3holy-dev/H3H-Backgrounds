from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8")

target = """    gdrive_token, folder_id = get_gdrive_credentials()
    client = SteamGridDBClient(api_key=sgdb_key)"""

replacement = """    gdrive_token, folder_id = get_gdrive_credentials()
    client = SteamGridDBClient(api_key=sgdb_key)

    # Verify Google Drive token upfront before processing
    test_res = GoogleDriveClient.test_connection(gdrive_token)
    if not test_res.get("ok"):
        print(f"\\n[⚠️] Текущий токен Google Drive истек или недействителен: {test_res.get('error', 'HTTP 401')}")
        gdrive_token = prompt_new_gdrive_token()
    else:
        u_name = test_res.get("displayName") or test_res.get("user") or "OK"
        print(f"[*] Связь с Google Drive подтверждена: {u_name}")"""

assert target in text, "Target not found in auto_harvest_pipeline.py"
text = text.replace(target, replacement)
p.write_text(text, encoding="utf-8")
print("Startup check added!")
