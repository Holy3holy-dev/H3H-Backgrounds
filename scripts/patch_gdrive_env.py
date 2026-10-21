from pathlib import Path

p = Path("studio/h3h_studio/core/google_drive.py")
text = p.read_text(encoding="utf-8")
is_crlf = "\r\n" in text
if is_crlf:
    text = text.replace("\r\n", "\n")

old = """        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[-] Warning reading {cls.CONFIG_FILE}: {e}")
        return {}"""

new = """        cfg = {}
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception as e:
                print(f"[-] Warning reading {cls.CONFIG_FILE}: {e}")
        
        # Override / inject from environment variables (for Docker / Render cloud deployment)
        import os
        if os.getenv("GDRIVE_REFRESH_TOKEN"):
            cfg["refresh_token"] = os.getenv("GDRIVE_REFRESH_TOKEN").strip()
        if os.getenv("GDRIVE_TOKEN"):
            cfg["token"] = os.getenv("GDRIVE_TOKEN").strip()
        if os.getenv("GDRIVE_FOLDER_ID"):
            cfg["folder_id"] = os.getenv("GDRIVE_FOLDER_ID").strip()
            cfg["project_folder_id"] = os.getenv("GDRIVE_FOLDER_ID").strip()
        return cfg"""

if old in text:
    text = text.replace(old, new)
    if is_crlf:
        text = text.replace("\n", "\r\n")
    p.write_text(text, encoding="utf-8")
    print("[+] Successfully added ENV support to google_drive.py!")
else:
    print("[-] Old text not found in google_drive.py")
