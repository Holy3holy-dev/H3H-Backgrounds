from pathlib import Path

p = Path("scripts/auto_video_harvester.py")
text = p.read_text(encoding="utf-8")

needle = '    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"])\n]),'
assert needle in text

pos = text.find(needle)
end_bracket = text.find("]", pos + 50)
new_text = text[:pos] + '    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"])\n]' + text[end_bracket + 1:]

with open(p, "w", newline="\n", encoding="utf-8") as f:
    f.write(new_text)

print("[SUCCESS] auto_video_harvester.py syntax verified and fixed!")
