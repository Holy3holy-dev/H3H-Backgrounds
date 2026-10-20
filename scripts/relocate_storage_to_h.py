import re
from pathlib import Path

# 1. Patch scripts/auto_harvest_pipeline.py
pipeline_py = Path("scripts/auto_harvest_pipeline.py")
text = pipeline_py.read_text(encoding="utf-8")

old_target = """OUTPUT_DIR = ROOT_DIR / "downloaded_official_backgrounds"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)"""

new_target = """# Primary high-capacity storage on drive H: to save C: disk space
H_STORAGE_DIR = Path(r"H:\\H3H_Backgrounds")
if H_STORAGE_DIR.exists():
    OUTPUT_DIR = H_STORAGE_DIR
    TEMP_DIR = H_STORAGE_DIR / "temp"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(TEMP_DIR)
    os.environ["TEMP"] = str(TEMP_DIR)
    os.environ["TMP"] = str(TEMP_DIR)
    print(f"[*] Использование хранилища высокой ёмкости: {OUTPUT_DIR} (temp: {TEMP_DIR})")
else:
    OUTPUT_DIR = ROOT_DIR / "downloaded_official_backgrounds"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)"""

if old_target in text:
    text = text.replace(old_target, new_target, 1)
    pipeline_py.write_text(text, encoding="utf-8")
    print("[+] Patched scripts/auto_harvest_pipeline.py to use H:\\H3H_Backgrounds")
else:
    print("[*] scripts/auto_harvest_pipeline.py already modified or target not matched")

# 2. Patch studio/h3h_studio/core/steamgriddb.py
sgdb_py = Path("studio/h3h_studio/core/steamgriddb.py")
text_sgdb = sgdb_py.read_text(encoding="utf-8")

old_sgdb = 'with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp_in:'
new_sgdb = '''temp_base = Path(r"H:\\H3H_Backgrounds\\temp")
        custom_dir = str(temp_base) if temp_base.exists() else None
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", dir=custom_dir, delete=False) as tmp_in:'''

if old_sgdb in text_sgdb:
    text_sgdb = text_sgdb.replace(old_sgdb, new_sgdb, 1)
    sgdb_py.write_text(text_sgdb, encoding="utf-8")
    print("[+] Patched studio/h3h_studio/core/steamgriddb.py to use H:\\H3H_Backgrounds\\temp")
else:
    print("[*] steamgriddb.py already modified or target not matched")

# 3. Patch scripts/upload_remaining_to_drive.py
up_py = Path("scripts/upload_remaining_to_drive.py")
if up_py.exists():
    text_up = up_py.read_text(encoding="utf-8")
    text_up = text_up.replace(
        'LOCAL_DIR = Path(r"e:\\videofon\\downloaded_official_backgrounds")',
        'LOCAL_DIR = Path(r"H:\\H3H_Backgrounds") if Path(r"H:\\H3H_Backgrounds").exists() else Path(r"e:\\videofon\\downloaded_official_backgrounds")'
    )
    up_py.write_text(text_up, encoding="utf-8")
    print("[+] Patched scripts/upload_remaining_to_drive.py to use H:\\H3H_Backgrounds")

# 4. Patch scripts/download_official_backgrounds.py
dl_py = Path("scripts/download_official_backgrounds.py")
if dl_py.exists():
    text_dl = dl_py.read_text(encoding="utf-8")
    text_dl = text_dl.replace(
        'OUTPUT_DIR = Path("downloaded_official_backgrounds")',
        'OUTPUT_DIR = Path(r"H:\\H3H_Backgrounds") if Path(r"H:\\H3H_Backgrounds").exists() else Path("downloaded_official_backgrounds")'
    )
    dl_py.write_text(text_dl, encoding="utf-8")
    print("[+] Patched scripts/download_official_backgrounds.py to use H:\\H3H_Backgrounds")

# 5. Patch studio/h3h_studio/ui/main_window.py
mw_py = Path("studio/h3h_studio/ui/main_window.py")
if mw_py.exists():
    text_mw = mw_py.read_text(encoding="utf-8")
    text_mw = text_mw.replace(
        'temp_dir = Path(tempfile.gettempdir()) / "h3h_studio_videos"',
        'temp_dir = Path(r"H:\\H3H_Backgrounds\\temp") if Path(r"H:\\H3H_Backgrounds\\temp").exists() else (Path(tempfile.gettempdir()) / "h3h_studio_videos")'
    )
    mw_py.write_text(text_mw, encoding="utf-8")
    print("[+] Patched studio/h3h_studio/ui/main_window.py to use H:\\H3H_Backgrounds\\temp")
