"""
Generates the official 256x256 Cyber-Pink / Neon Magenta 4IFIR icon for H3H-AfterDark.nro.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

def generate_icon(output_path: Path):
    size = (256, 256)
    img = Image.new("RGB", size, (10, 13, 20))
    draw = ImageDraw.Draw(img)

    # 1. Background OLED gradient with radial glow
    for y in range(256):
        ratio = y / 255.0
        # Dark obsidian base with subtle purple/magenta ambient at the bottom
        r = int(10 + 20 * ratio)
        g = int(13 + 5 * ratio)
        b = int(20 + 25 * ratio)
        draw.line([(0, y), (255, y)], fill=(r, g, b))

    # Glow layer for Neon Pink ambient
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    # Magenta center glow
    glow_draw.ellipse([30, 30, 226, 226], fill=(255, 46, 147, 45))
    glow_draw.ellipse([60, 60, 196, 196], fill=(217, 70, 239, 65))
    glow = glow.filter(ImageFilter.GaussianBlur(24))
    img.paste(glow, (0, 0), glow)

    # 2. Sleek Glass Frame (Chamfered / Rounded Card)
    card_bounds = [16, 16, 239, 239]
    # Draw card border with neon pink glow
    card_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_layer)
    card_draw.rounded_rectangle(card_bounds, radius=28, fill=(19, 24, 36, 180), outline=(255, 46, 147, 200), width=2)
    # Top edge glass highlight
    card_draw.line([(40, 17), (215, 17)], fill=(255, 255, 255, 90), width=1)
    img.paste(card_layer, (0, 0), card_layer)

    # 3. Stylized Cyber-Geometric 'H' (4IFIR Signature)
    # Left pillar: [65, 55, 95, 175]
    # Right pillar: [160, 55, 190, 175]
    # Crossbar: [95, 103, 160, 127]
    h_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(h_layer)

    # Glow under H
    h_draw.rounded_rectangle([62, 52, 98, 178], radius=8, fill=(255, 46, 147, 160))
    h_draw.rounded_rectangle([157, 52, 193, 178], radius=8, fill=(217, 70, 239, 160))
    h_draw.rounded_rectangle([92, 100, 163, 130], radius=6, fill=(255, 46, 147, 160))
    h_layer = h_layer.filter(ImageFilter.GaussianBlur(8))
    img.paste(h_layer, (0, 0), h_layer)

    # Solid H with Neon Gradient (Pink -> Purple)
    h_solid = Image.new("RGBA", size, (0, 0, 0, 0))
    h_solid_draw = ImageDraw.Draw(h_solid)
    h_solid_draw.rounded_rectangle([65, 55, 95, 175], radius=6, fill=(255, 46, 147, 255), outline=(255, 255, 255, 180), width=1)
    h_solid_draw.rounded_rectangle([160, 55, 190, 175], radius=6, fill=(217, 70, 239, 255), outline=(255, 255, 255, 180), width=1)
    h_solid_draw.rounded_rectangle([95, 103, 160, 127], radius=4, fill=(240, 60, 180, 255))
    # Bevel lines on H
    h_solid_draw.line([(68, 58), (68, 172)], fill=(255, 255, 255, 140), width=1)
    h_solid_draw.line([(163, 58), (163, 172)], fill=(255, 255, 255, 140), width=1)
    img.paste(h_solid, (0, 0), h_solid)

    # 4. High-Tech Badge: "AFTER DARK" / "18+"
    badge_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(badge_layer)
    b_draw.rounded_rectangle([48, 195, 208, 225], radius=8, fill=(255, 46, 147, 40), outline=(255, 46, 147, 220), width=1)
    
    # Try loading a font, fallback to default
    try:
        font = ImageFont.truetype("arialbd.ttf", 13)
    except Exception:
        font = ImageFont.load_default()

    text = "★ AFTER DARK 18+ ★"
    bbox = b_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (256 - tw) // 2
    ty = 195 + (30 - th) // 2 - 2
    b_draw.text((tx, ty), text, fill=(255, 255, 255), font=font)
    img.paste(badge_layer, (0, 0), badge_layer)

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=98)
    print(f"[+] Saved After Dark icon to: {output_path}")

if __name__ == "__main__":
    generate_icon(Path("downloader/icon_after_dark.jpg"))
