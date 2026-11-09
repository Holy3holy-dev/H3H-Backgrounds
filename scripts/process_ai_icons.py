import os
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

paths = [
    (r'C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\catalog_tab_icon_1793286878936.jpg', 'tab_catalog.png'),
    (r'C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\video_icons_tab_icon_1793286877196.jpg', 'tab_video_icons.png'),
    (r'C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\game_manager_icon_1793286878987.jpg', 'tab_my_games.png'),
    (r'C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\tab_downloads_cyberglass_1793286876994.jpg', 'tab_downloads.png'),
    (r'C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\settings_cyber_glass_icon_1793286876204.jpg', 'tab_settings.png')
]

out_dir = r'downloader\romfs\icons'
os.makedirs(out_dir, exist_ok=True)

processed_imgs = []

for src_path, filename in paths:
    img = Image.open(src_path).convert('RGBA')
    w, h = img.size

    # We want a high-grade 192x192 icon with soft rounded glass edges or transparent background
    # Let's inspect the background color
    bg_r, bg_g, bg_b = 8, 12, 23
    
    # Create an RGBA version where dark outer areas fade gracefully to alpha
    arr = np.array(img, dtype=np.float32)
    
    # Calculate distance from background color
    diff = np.sqrt(
        (arr[:, :, 0] - bg_r) ** 2 +
        (arr[:, :, 1] - bg_g) ** 2 +
        (arr[:, :, 2] - bg_b) ** 2
    )
    
    # Smooth alpha mask based on luminance / distance from bg
    # If diff < 15 -> alpha = 0; if diff > 45 -> alpha = 255; smooth lerp in between
    alpha_from_diff = np.clip((diff - 12.0) / 28.0, 0.0, 1.0) * 255.0
    
    # Also add a radial vignette from center (radius 480px) to prevent any border edge artifacts
    y, x = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((x - w/2)**2 + (y - h/2)**2)
    radial_mask = np.clip((480.0 - dist_from_center) / 60.0, 0.0, 1.0)
    
    final_alpha = (alpha_from_diff * radial_mask).astype(np.uint8)
    
    arr[:, :, 3] = final_alpha
    processed = Image.fromarray(arr.astype(np.uint8), mode='RGBA')
    
    # Resize to 192x192 with Lanczos
    target_size = 192
    resized = processed.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    dest_path = os.path.join(out_dir, filename)
    resized.save(dest_path, 'PNG', optimize=True)
    print(f"Saved {dest_path} ({os.path.getsize(dest_path)} bytes)")
    processed_imgs.append((filename, resized))

# Create preview montage on switch tile background
montage_w = 1280
montage_h = 360
montage = Image.new('RGBA', (montage_w, montage_h), (9, 12, 19, 255))
m_draw = ImageDraw.Draw(montage)

tile_w = 225
tile_h = 208
gap = 18
start_x = (montage_w - (5 * tile_w + 4 * gap)) // 2
tile_y = 60

titles = ["Каталог", "Видеоиконки", "Менеджер игр", "Загрузки", "Настройки"]

for i, (fn, icon_img) in enumerate(processed_imgs):
    tx = start_x + i * (tile_w + gap)
    is_focused = (i == 1)
    
    # Tile background
    bg_col = (20, 27, 44, 255) if is_focused else (14, 19, 32, 255)
    border_col = (0, 210, 255, 255) if is_focused else (30, 41, 62, 255)
    
    m_draw.rounded_rectangle([tx, tile_y, tx + tile_w, tile_y + tile_h], radius=24, fill=bg_col, outline=border_col, width=3 if is_focused else 1)
    
    # Paste icon centered
    icon_draw_size = 96 if is_focused else 90
    ic_scaled = icon_img.resize((icon_draw_size, icon_draw_size), Image.Resampling.LANCZOS)
    ic_x = tx + (tile_w - icon_draw_size) // 2
    ic_y = tile_y + 36
    montage.alpha_composite(ic_scaled, (ic_x, ic_y))
    
    # Title
    t_col = (0, 210, 255, 255) if is_focused else (241, 245, 249, 255)
    m_draw.text((tx + tile_w // 2, tile_y + tile_h - 32), titles[i], fill=t_col, anchor="mm")

preview_out = r'C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\new_ai_tab_icons_preview.png'
montage.save(preview_out)
print(f"Saved montage preview: {preview_out}")
