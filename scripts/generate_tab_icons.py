import os
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ICONS_DIR = Path("downloader/romfs/icons")
ICONS_DIR.mkdir(parents=True, exist_ok=True)

SIZE = 160
SCALE = 4  # 4x supersampling for ultra crisp anti-aliasing
W = SIZE * SCALE
H = SIZE * SCALE

# 4IFIR Cyber-Glass Palette
COLOR_CYAN = (0, 210, 255, 255)
COLOR_PINK = (236, 72, 153, 255)
COLOR_PURPLE = (168, 85, 247, 255)
COLOR_WHITE = (255, 255, 255, 255)
COLOR_DARK = (15, 23, 42, 255)
COLOR_OBSIDIAN = (9, 12, 19, 255)
COLOR_GLASS = (19, 27, 46, 230)

def create_super_canvas():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))

def finalize(img, filename):
    # Downscale with high-quality Lanczos resampling
    final = img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    out_path = ICONS_DIR / filename
    final.save(out_path, "PNG")
    print(f"[+] Saved {out_path} ({SIZE}x{SIZE})")

# 1. CATALOG ICON (Cartridge + Storefront)
def make_catalog_icon():
    img = create_super_canvas()
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, H // 2

    # Subtle neon glow behind
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - 180, cy - 180, cx + 180, cy + 180), fill=(0, 210, 255, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    img.paste(glow, (0, 0), glow)

    # Cartridge on left
    cart_x1, cart_y1 = cx - 210, cy - 120
    cart_x2, cart_y2 = cx - 50, cy + 150
    # Cartridge body
    d.rounded_rectangle((cart_x1, cart_y1, cart_x2, cart_y2), radius=36, fill=(19, 27, 46, 255), outline=COLOR_CYAN, width=10)
    # Cartridge top notch
    d.rounded_rectangle((cart_x1 + 30, cart_y1 + 25, cart_x2 - 30, cart_y1 + 80), radius=16, fill=COLOR_PINK)
    # Cartridge label artwork
    d.rounded_rectangle((cart_x1 + 25, cart_y1 + 105, cart_x2 - 25, cart_y2 - 30), radius=20, fill=(11, 16, 27, 255), outline=(0, 210, 255, 160), width=6)
    # Label stripe
    d.line((cart_x1 + 40, cart_y1 + 160, cart_x2 - 40, cart_y1 + 160), fill=COLOR_CYAN, width=12)

    # Storefront on right
    store_x1, store_y1 = cx - 40, cy - 80
    store_x2, store_y2 = cx + 210, cy + 150
    # Main store building
    d.rounded_rectangle((store_x1, store_y1, store_x2, store_y2), radius=30, fill=(16, 24, 40, 245), outline=COLOR_CYAN, width=10)
    # Awning roof with stripes
    awning_w = store_x2 - store_x1 + 40
    awning_x1 = store_x1 - 20
    awning_y1 = store_y1 - 60
    awning_y2 = store_y1 + 20
    d.rounded_rectangle((awning_x1, awning_y1, awning_x1 + awning_w, awning_y2), radius=20, fill=COLOR_CYAN)
    stripe_w = awning_w / 5
    for s in range(5):
        if s % 2 == 1:
            sx = int(awning_x1 + s * stripe_w)
            d.rounded_rectangle((sx, awning_y1, int(sx + stripe_w), awning_y2), radius=10, fill=COLOR_PINK)

    # Store door and display window
    d.rounded_rectangle((store_x1 + 30, store_y1 + 45, store_x1 + 95, store_y2 - 20), radius=16, fill=(0, 210, 255, 70), outline=COLOR_CYAN, width=6)
    d.rounded_rectangle((store_x1 + 120, store_y1 + 45, store_x2 - 30, store_y1 + 120), radius=16, fill=(236, 72, 153, 90), outline=COLOR_PINK, width=6)

    finalize(img, "tab_catalog.png")

# 2. VIDEO ICONS ICON (1:1 Frame + Play Triangle)
def make_video_icons_icon():
    img = create_super_canvas()
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, H // 2

    # Glowing backdrop
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - 190, cy - 190, cx + 190, cy + 190), fill=(236, 72, 153, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(35))
    img.paste(glow, (0, 0), glow)

    # 1:1 Rounded frame
    fw, fh = 360, 340
    fx1, fy1 = cx - fw // 2, cy - fh // 2 - 15
    fx2, fy2 = cx + fw // 2, cy + fh // 2 - 15
    d.rounded_rectangle((fx1, fy1, fx2, fy2), radius=70, fill=(15, 23, 42, 245), outline=COLOR_CYAN, width=12)

    # Secondary inner neon rim (Magenta)
    d.rounded_rectangle((fx1 + 16, fy1 + 16, fx2 - 16, fy2 - 16), radius=55, outline=(236, 72, 153, 180), width=6)

    # Film perforations on corners / sides
    for py in [fy1 + 50, cy - 25, fy2 - 70]:
        d.rounded_rectangle((fx1 + 25, py, fx1 + 45, py + 30), radius=8, fill=(0, 210, 255, 180))
        d.rounded_rectangle((fx2 - 45, py, fx2 - 25, py + 30), radius=8, fill=(236, 72, 153, 180))

    # Centered Play Triangle (Neon Cyan)
    tri_cx = cx + 15
    tri_cy = cy - 20
    tri_r = 75
    p1 = (tri_cx - 50, tri_cy - tri_r)
    p2 = (tri_cx - 50, tri_cy + tri_r)
    p3 = (tri_cx + 70, tri_cy)
    d.polygon([p1, p2, p3], fill=COLOR_CYAN)

    # Bottom Pill Badge: "256x256"
    bw, bh = 220, 60
    bx1 = cx - bw // 2
    by1 = fy2 - 20
    d.rounded_rectangle((bx1, by1, bx1 + bw, by1 + bh), radius=24, fill=COLOR_PINK, outline=COLOR_WHITE, width=4)
    # Dots or text representation
    d.rectangle((cx - 70, by1 + 25, cx + 70, by1 + 35), fill=COLOR_WHITE)

    finalize(img, "tab_video_icons.png")

# 3. MY GAMES ICON (Game Case + Cartridges)
def make_my_games_icon():
    img = create_super_canvas()
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, H // 2

    # Glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - 180, cy - 180, cx + 180, cy + 180), fill=(168, 85, 247, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    img.paste(glow, (0, 0), glow)

    # 3 peeking cartridges behind folder
    # Cartridge 1 (Pink)
    d.rounded_rectangle((cx - 150, cy - 160, cx - 40, cy - 20), radius=20, fill=COLOR_PINK, outline=COLOR_WHITE, width=6)
    # Cartridge 2 (Cyan)
    d.rounded_rectangle((cx - 55, cy - 180, cx + 55, cy - 20), radius=20, fill=COLOR_CYAN, outline=COLOR_WHITE, width=6)
    # Cartridge 3 (Purple)
    d.rounded_rectangle((cx + 40, cy - 150, cx + 150, cy - 20), radius=20, fill=COLOR_PURPLE, outline=COLOR_WHITE, width=6)

    # Main Case Body (Folder)
    fx1, fy1 = cx - 190, cy - 60
    fx2, fy2 = cx + 190, cy + 160
    d.rounded_rectangle((fx1, fy1, fx2, fy2), radius=45, fill=(18, 26, 44, 250), outline=COLOR_CYAN, width=12)

    # Top tab of folder
    d.rounded_rectangle((fx1 + 30, fy1 - 35, fx1 + 160, fy1 + 10), radius=16, fill=(18, 26, 44, 250), outline=COLOR_CYAN, width=8)
    d.rectangle((fx1 + 35, fy1, fx1 + 155, fy1 + 15), fill=(18, 26, 44, 250)) # cover border seam

    # Inner "MY GAMES" plate
    plate_w, plate_h = 240, 75
    px1 = cx - plate_w // 2
    py1 = cy + 20
    d.rounded_rectangle((px1, py1, px1 + plate_w, py1 + plate_h), radius=24, fill=(9, 13, 22, 240), outline=COLOR_CYAN, width=8)

    # Switch Joy-Cons mini emblem on plate
    d.rounded_rectangle((cx - 70, py1 + 20, cx - 25, py1 + 55), radius=12, fill=COLOR_CYAN)
    d.rounded_rectangle((cx + 25, py1 + 20, cx + 70, py1 + 55), radius=12, fill=COLOR_PINK)
    d.ellipse((cx - 52, py1 + 28, cx - 42, py1 + 38), fill=(9, 13, 22, 255))
    d.ellipse((cx + 42, py1 + 38, cx + 52, py1 + 48), fill=(9, 13, 22, 255))

    finalize(img, "tab_my_games.png")

# 4. DOWNLOADS ICON (Switch Console + Down Arrow)
def make_downloads_icon():
    img = create_super_canvas()
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, H // 2

    # Glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - 180, cy - 180, cx + 180, cy + 180), fill=(0, 210, 255, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    img.paste(glow, (0, 0), glow)

    # Switch Console
    # Center screen
    scr_w, scr_h = 250, 180
    sx1 = cx - scr_w // 2
    sy1 = cy - 30
    sx2 = cx + scr_w // 2
    sy2 = cy + 150
    d.rounded_rectangle((sx1, sy1, sx2, sy2), radius=25, fill=(11, 16, 27, 255), outline=COLOR_CYAN, width=10)

    # Left Joy-Con (Cyan)
    d.rounded_rectangle((sx1 - 65, sy1 + 5, sx1 - 10, sy2 - 5), radius=28, fill=COLOR_CYAN)
    # Left stick
    d.ellipse((sx1 - 45, sy1 + 35, sx1 - 25, sy1 + 55), fill=(9, 13, 22, 255))

    # Right Joy-Con (Pink)
    d.rounded_rectangle((sx2 + 10, sy1 + 5, sx2 + 65, sy2 - 5), radius=28, fill=COLOR_PINK)
    # Right stick
    d.ellipse((sx2 + 25, sy2 - 60, sx2 + 45, sy2 - 40), fill=(9, 13, 22, 255))

    # Bold Neon Download Arrow entering screen
    arr_w = 40
    arr_top = cy - 170
    arr_neck = cy + 10
    d.rounded_rectangle((cx - arr_w // 2, arr_top, cx + arr_w // 2, arr_neck), radius=14, fill=COLOR_CYAN)
    # Arrow head
    head_w = 120
    head_h = 70
    p1 = (cx - head_w // 2, arr_neck)
    p2 = (cx + head_w // 2, arr_neck)
    p3 = (cx, arr_neck + head_h)
    d.polygon([p1, p2, p3], fill=COLOR_CYAN)

    # Progress bar indicator inside screen
    d.rounded_rectangle((cx - 80, sy2 - 45, cx + 80, sy2 - 25), radius=10, fill=(28, 34, 48, 255))
    d.rounded_rectangle((cx - 80, sy2 - 45, cx + 25, sy2 - 25), radius=10, fill=COLOR_PINK)

    finalize(img, "tab_downloads.png")

# 5. SETTINGS ICON (Cyber Cogwheel Gear)
def make_settings_icon():
    img = create_super_canvas()
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, H // 2

    # Glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - 180, cy - 180, cx + 180, cy + 180), fill=(0, 210, 255, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    img.paste(glow, (0, 0), glow)

    # Outer Gear with 8 Teeth
    num_teeth = 8
    r_outer = 175
    r_base = 135
    r_inner = 70
    r_core = 35

    # Draw 8 gear teeth
    for i in range(num_teeth):
        angle = i * (2 * math.pi / num_teeth)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        tx = cx + (r_base + 20) * cos_a
        ty = cy + (r_base + 20) * sin_a

        # Tooth polygon
        tw = 45
        th = 40
        # perpendicular vector
        px = -sin_a * (tw / 2)
        py = cos_a * (tw / 2)
        # radial vector
        rx = cos_a * th
        ry = sin_a * th

        pt1 = (tx - px - rx, ty - py - ry)
        pt2 = (tx + px - rx, ty + py - ry)
        pt3 = (tx + px + rx * 0.4, ty + py + ry * 0.4)
        pt4 = (tx - px + rx * 0.4, ty - py + rx * 0.4)
        d.polygon([pt1, pt2, pt3, pt4], fill=COLOR_CYAN)

    # Main outer wheel ring
    d.ellipse((cx - r_base, cy - r_base, cx + r_base, cy + r_base), fill=(24, 34, 52, 255), outline=COLOR_CYAN, width=12)

    # 4 Neon indicator notches around perimeter (Magenta)
    for i in range(4):
        ang = i * (math.pi / 2) + math.pi / 4
        nx = cx + (r_base - 18) * math.cos(ang)
        ny = cy + (r_base - 18) * math.sin(ang)
        d.ellipse((nx - 12, ny - 12, nx + 12, ny + 12), fill=COLOR_PINK)

    # Inner wheel ring
    d.ellipse((cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner), fill=(11, 16, 27, 255), outline=COLOR_PINK, width=10)

    # Center glowing energy core
    d.ellipse((cx - r_core, cy - r_core, cx + r_core, cy + r_core), fill=COLOR_CYAN, outline=COLOR_WHITE, width=6)

    finalize(img, "tab_settings.png")

if __name__ == "__main__":
    print("=== Generating 4IFIR Cyber-Glass Tab Icons ===")
    make_catalog_icon()
    make_video_icons_icon()
    make_my_games_icon()
    make_downloads_icon()
    make_settings_icon()
    print("All 5 tab icons generated successfully!")
