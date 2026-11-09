from pathlib import Path

p = Path("scripts/create_release_v135.py")
c = p.read_text(encoding="utf-8")

old_s = """    assets_to_upload = [
        (ROOT_DIR / "downloader" / "H3H-Backgrounds.nro", "H3H-Backgrounds.nro"),
        (ROOT_DIR / "downloader" / "H3H-AfterDark.nro", "H3H-AfterDark.nro"),
    ]"""

new_s = """    assets_to_upload = [
        (ROOT_DIR / "downloader" / "H3H-Backgrounds.nro", "H3H-Backgrounds.nro"),
        (ROOT_DIR / "downloader" / "H3H-AfterDark.nro", "H3H-AfterDark.nro"),
        (ROOT_DIR / "H3H-Background-Studio.exe", "H3H-Background-Studio.exe"),
        (ROOT_DIR / "H3H-Background-Studio-v1.3.5-Portable.zip", "H3H-Background-Studio-v1.3.5-Portable.zip"),
    ]"""

assert old_s in c, "old_s not found"
c = c.replace(old_s, new_s, 1)
p.write_text(c, encoding="utf-8")
print("SUCCESS: create_release_v135.py updated!")
