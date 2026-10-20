"""
Generate authentic 4IFIR-styled app icons for H3H Backgrounds on Nintendo Switch.
Uses exact 4IFIR colors:
- Background: Deep obsidian/OLED black (#0A0E17 / #0D111A)
- Border: 4IFIR signature Cyan-to-Magenta gradient (#00F2FE -> #FF007F)
- Typography: Clean, modern, crisp geometric letter 'H'
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ARTIFACT_DIR = r"C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967"
SIZE = 512

def create_gradient_color(t, col1, col2):
    return (
        int(col1[0] + (col2[0] - col1[0]) * t),
        int(col1[1] + (col2[1] - col1[1]) * t),
        int(col1[2] + (col2[2] - col1[2]) * t),
    )

def draw_neon_rounded_rect(draw_img, rect, radius, col1, col2, thickness=6):
    x0, y0, x1, y1 = rect
    w = x1 - x0
    h = y1 - y0
    
    # Draw gradient outline pixel by pixel or segment
    for th in range(thickness):
        rx0, ry0, rx1, ry1 = x0 + th, y0 + th, x1 - th, y1 - th
        # We can draw using a mask
        pass

def build_icon(option_type: str, output_path: str):
    img = Image.new("RGBA", (SIZE, SIZE), (11, 15, 23, 255))
    
    # Subtle radial dark blue/purple backdrop glow in center
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = SIZE // 2, SIZE // 2
    for r in range(220, 0, -5):
        alpha = int(45 * (1.0 - (r / 220.0)))
        glow_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(14, 165, 233, alpha))
    img = Image.alpha_composite(img, glow)
    
    # 4IFIR Neon Gradient Rounded Frame
    # Outer margin: 36px, border radius: 36px
    margin = 38
    b_rad = 34
    thick = 8
    
    # Draw gradient mask
    grad_mask = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(grad_mask)
    g_draw.rounded_rectangle([margin, margin, SIZE - margin, SIZE - margin], radius=b_rad, outline=(255, 255, 255, 255), width=thick)
    
    # Create the gradient texture: top-left (0, 242, 254) to bottom-right (255, 0, 128)
    cyan = (0, 242, 254)
    pink = (255, 0, 128)
    
    grad_img = Image.new("RGBA", (SIZE, SIZE))
    for y in range(SIZE):
        for x in range(SIZE):
            t = (x + y) / (2.0 * SIZE)
            r = int(cyan[0] + (pink[0] - cyan[0]) * t)
            g = int(cyan[1] + (pink[1] - cyan[1]) * t)
            b = int(cyan[2] + (pink[2] - cyan[2]) * t)
            grad_img.putpixel((x, y), (r, g, b, 255))
            
    # Composite frame outline with gradient
    frame_line = Image.composite(grad_img, Image.new("RGBA", (SIZE, SIZE), (0,0,0,0)), grad_mask)
    
    # Add neon bloom to frame
    bloom = frame_line.filter(ImageFilter.GaussianBlur(radius=8))
    img = Image.alpha_composite(img, bloom)
    img = Image.alpha_composite(img, frame_line)
    
    # Load fonts
    font_path = r"C:\Windows\Fonts\segoeuib.ttf"
    if not os.path.exists(font_path):
        font_path = r"C:\Windows\Fonts\arialbd.ttf"
        
    font_h = ImageFont.truetype(font_path, 240)
    font_sub = ImageFont.truetype(font_path, 34)
    font_small = ImageFont.truetype(font_path, 22)
    
    draw = ImageDraw.Draw(img)
    
    # Center position for "H"
    # Get bounding box of "H"
    bbox = font_h.getbbox("H")
    hw = bbox[2] - bbox[0]
    hh = bbox[3] - bbox[1]
    hx = (SIZE - hw) // 2 - bbox[0]
    hy = (SIZE - hh) // 2 - bbox[1] - 25
    
    if option_type == "classic_white":
        # Option 1: Clean, pure crisp white letter "H" with soft cyan neon shadow
        # Soft shadow
        draw.text((hx, hy + 4), "H", font=font_h, fill=(0, 242, 254, 120))
        # White text
        draw.text((hx, hy), "H", font=font_h, fill=(255, 255, 255, 255))
        
        # Subtitle: 4IFIR
        sub_text = "4IFIR"
        sbox = font_sub.getbbox(sub_text)
        sw = sbox[2] - sbox[0]
        sx = (SIZE - sw) // 2 - sbox[0]
        sy = 390
        # Pill under 4IFIR
        draw.rounded_rectangle([sx - 18, sy - 4, sx + sw + 18, sy + 38], radius=10, fill=(15, 23, 42, 220), outline=(0, 242, 254, 200), width=2)
        draw.text((sx, sy), sub_text, font=font_sub, fill=(0, 242, 254, 255))
        
    elif option_type == "gradient_h":
        # Option 2: The letter "H" itself has the vibrant 4IFIR gradient (Cyan to Pink)
        h_mask = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        h_draw = ImageDraw.Draw(h_mask)
        h_draw.text((hx, hy), "H", font=font_h, fill=(255, 255, 255, 255))
        
        # Fill with gradient
        h_colored = Image.composite(grad_img, Image.new("RGBA", (SIZE, SIZE), (0,0,0,0)), h_mask)
        h_bloom = h_colored.filter(ImageFilter.GaussianBlur(radius=10))
        img = Image.alpha_composite(img, h_bloom)
        img = Image.alpha_composite(img, h_colored)
        
        # Subtitle: 4IFIR BACKGROUNDS
        sub_text = "4 I F I R"
        sbox = font_sub.getbbox(sub_text)
        sw = sbox[2] - sbox[0]
        sx = (SIZE - sw) // 2 - sbox[0]
        sy = 395
        draw.text((sx, sy), sub_text, font=font_sub, fill=(255, 255, 255, 240))
        
    elif option_type == "h3h_cyan":
        # Option 3: Electric Cyan H with white core and H3H logo
        draw.text((hx, hy), "H", font=font_h, fill=(0, 242, 254, 255))
        draw.text((hx + 2, hy + 2), "H", font=font_h, fill=(255, 255, 255, 240))
        
        # Subtitle: H3H BACKGROUNDS
        sub_text = "H3H BACKGROUNDS"
        sbox = font_small.getbbox(sub_text)
        sw = sbox[2] - sbox[0]
        sx = (SIZE - sw) // 2 - sbox[0]
        sy = 396
        draw.rounded_rectangle([sx - 14, sy - 4, sx + sw + 14, sy + 30], radius=8, fill=(15, 23, 42, 240), outline=(255, 0, 128, 200), width=1)
        draw.text((sx, sy), sub_text, font=font_small, fill=(255, 0, 128, 255))

    elif option_type == "pure_4ifir":
        # Option 4: Pure 4IFIR minimal - big bold white H centered, no clutter, exact replica of 4IFIR UI
        hy = (SIZE - hh) // 2 - bbox[1] # perfectly centered
        draw.text((hx - 2, hy), "H", font=font_h, fill=(0, 242, 254, 180))
        draw.text((hx + 2, hy), "H", font=font_h, fill=(255, 0, 128, 180))
        draw.text((hx, hy), "H", font=font_h, fill=(255, 255, 255, 255))
        
        # Subtle "4R" style star or dot in top right corner
        dot_x, dot_y = SIZE - margin - 25, margin + 25
        draw.ellipse([dot_x - 6, dot_y - 6, dot_x + 6, dot_y + 6], fill=(0, 242, 254, 255))

    # Convert to RGB and save
    final_rgb = img.convert("RGB")
    final_rgb.save(output_path, "JPEG", quality=98)
    
    # Also save 256x256
    thumb = final_rgb.resize((256, 256), Image.Resampling.LANCZOS)
    p256 = output_path.replace(".jpg", "_256.jpg")
    thumb.save(p256, "JPEG", quality=95)
    print(f"Generated {option_type} at {output_path}")

def main():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    
    options = [
        ("classic_white", "4ifir_icon_option_1_white.jpg"),
        ("gradient_h", "4ifir_icon_option_2_gradient.jpg"),
        ("h3h_cyan", "4ifir_icon_option_3_cyan.jpg"),
        ("pure_4ifir", "4ifir_icon_option_4_pure.jpg"),
    ]
    
    for opt, filename in options:
        out = os.path.join(ARTIFACT_DIR, filename)
        build_icon(opt, out)
        
    print("\n[+] All 4IFIR icon options generated successfully!")

if __name__ == "__main__":
    main()
