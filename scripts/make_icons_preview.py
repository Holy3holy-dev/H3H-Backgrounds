import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ICONS_DIR = Path("e:/videofon/downloader/romfs/icons")
OUT_PATH = Path(r"C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\tab_icons_preview.png")

icons = [
    ("tab_catalog.png", "Каталог"),
    ("tab_video_icons.png", "Видеоиконки"),
    ("tab_my_games.png", "Менеджер игр"),
    ("tab_downloads.png", "Загрузки"),
    ("tab_settings.png", "Настройки")
]

card_w, card_h = 200, 220
gap = 20
total_w = 5 * card_w + 6 * gap
total_h = card_h + 80

preview = Image.new("RGBA", (total_w, total_h), (9, 12, 19, 255))
d = ImageDraw.Draw(preview)

d.text((total_w // 2, 25), "4IFIR Cyber-Glass Tab Icons (Main & After Dark)", fill=(0, 210, 255, 255), anchor="mm")

for i, (fn, title) in enumerate(icons):
    x = gap + i * (card_w + gap)
    y = 55
    d.rounded_rectangle((x, y, x + card_w, y + card_h), radius=20, fill=(19, 27, 46, 240), outline=(0, 210, 255, 120), width=2)
    icon_path = ICONS_DIR / fn
    if icon_path.exists():
        ico = Image.open(icon_path).convert("RGBA")
        ico_scaled = ico.resize((120, 120), Image.Resampling.LANCZOS)
        preview.paste(ico_scaled, (x + (card_w - 120) // 2, y + 25), ico_scaled)
    d.text((x + card_w // 2, y + card_h - 30), title, fill=(255, 255, 255, 255), anchor="mm")

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
preview.save(OUT_PATH, "PNG")
print(f"[+] Saved preview montage to {OUT_PATH}")
