from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8").replace("\r\n", "\n")

target = '    return cat_data\n\n    """Removes release tags'
replacement = '    return cat_data\n\n\ndef clean_game_title(raw_title: str) -> str:\n    """Removes release tags'

if target in text:
    text = text.replace(target, replacement, 1)
    p.write_text(text, encoding="utf-8")
    print("[+] Successfully restored clean_game_title in auto_harvest_pipeline.py!")
else:
    print("[-] Target not found")
