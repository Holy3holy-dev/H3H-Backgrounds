from pathlib import Path

p = Path("tg_bot/bot.py")
content = p.read_text(encoding="utf-8")

old_text = "import html\nfrom pathlib import Path"
new_text = "import html\nimport base64\nimport urllib.request\nimport urllib.parse\nimport urllib.error\nfrom pathlib import Path"

content_norm = content.replace("\r\n", "\n")
if old_text in content_norm:
    content_norm = content_norm.replace(old_text, new_text)
    p.write_text(content_norm, encoding="utf-8")
    print("[+] Successfully added missing urllib and base64 imports to tg_bot/bot.py!")
else:
    print("[-] Target import block not found")
