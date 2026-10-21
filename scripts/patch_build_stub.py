from pathlib import Path

p = Path("scripts/build_nro.py")
text = p.read_text(encoding="utf-8").replace("\r\n", "\n")

old_part = '"src/platform/desktop_platform.cpp",'
new_part = '"src/platform/desktop_platform.cpp",\n    "src/platform/webp_stub.cpp",'

if old_part in text:
    text = text.replace(old_part, new_part, 1)
    p.write_text(text, encoding="utf-8")
    print("[+] Added webp_stub.cpp to build_nro.py")
else:
    print("[-] old_part not found")
