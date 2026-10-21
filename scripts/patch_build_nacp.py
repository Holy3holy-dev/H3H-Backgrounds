import re
from pathlib import Path

bld_path = Path("scripts/build_nro.py")
text = bld_path.read_text(encoding="utf-8")

old_code = '''    nacp_cmd = [
        NACPTOOL,
        "--create",
        "H3H Backgrounds (4IFIR)",
        "H3H Team",
        "1.0.0",
        nacp_path
    ]'''

new_code = '''    # Read version dynamically from version.json or config.hpp
    app_version = "1.0.3"
    v_file = os.path.join(ROOT_DIR, "version.json")
    if os.path.exists(v_file):
        try:
            import json
            with open(v_file, "r", encoding="utf-8") as vf:
                app_version = json.load(vf).get("latestVersion", "1.0.3")
        except Exception:
            pass

    nacp_cmd = [
        NACPTOOL,
        "--create",
        "H3H Backgrounds (4IFIR)",
        "H3H Team",
        app_version,
        nacp_path
    ]'''

if old_code in text:
    text = text.replace(old_code, new_code, 1)
    bld_path.write_text(text, encoding="utf-8")
    print(f"[+] Patched scripts/build_nro.py to use dynamic app_version in NACP")
else:
    print("[-] Target in build_nro.py not found")
