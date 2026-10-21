from pathlib import Path

theme_path = Path("downloader/include/ui/theme.hpp")
content = theme_path.read_text(encoding="utf-8").replace("\r\n", "\n")

old_block = """    // 4IFIR Signature Neon Glow Accent (Cyan -> Pink/Magenta Gradient)
    constexpr Color COLOR_FOCUS_CYAN   = {0x00, 0xE5, 0xFF, 0xFF}; // #00E5FF Electric Cyan
    constexpr Color COLOR_FOCUS_PINK   = {0xEC, 0x48, 0x99, 0xFF}; // #EC4899 Neon Magenta / Pink
    constexpr Color COLOR_FOCUS_RING   = COLOR_FOCUS_CYAN;
    constexpr Color COLOR_FOCUS_FILL   = {0x00, 0xE5, 0xFF, 0x1C}; // Soft translucent cyan glass tint
    
    // Typography & Accents
    constexpr Color COLOR_TEXT_PRIMARY = {0xFF, 0xFF, 0xFF, 0xFF}; // #FFFFFF Crisp White
    constexpr Color COLOR_TEXT_MUTED   = {0x8E, 0x9D, 0xB0, 0xFF}; // #8E9DB0 Slate Muted
    constexpr Color COLOR_ACCENT       = {0x00, 0xE5, 0xFF, 0xFF}; // #00E5FF 4IFIR Cyan"""

new_block = """#ifdef H3H_AFTER_DARK
    // Neon Cyber-Pink / Magenta Aesthetic for After Dark (18+)
    constexpr Color COLOR_FOCUS_CYAN   = {0xFF, 0x2E, 0x93, 0xFF}; // #FF2E93 Neon Cyber-Pink
    constexpr Color COLOR_FOCUS_PINK   = {0xD9, 0x46, 0xEF, 0xFF}; // #D946EF Neon Purple / Fuchsia
    constexpr Color COLOR_FOCUS_RING   = {0xFF, 0x2E, 0x93, 0xFF};
    constexpr Color COLOR_FOCUS_FILL   = {0xFF, 0x2E, 0x93, 0x24}; // Translucent cyber-pink glass tint
    constexpr Color COLOR_ACCENT       = {0xFF, 0x2E, 0x93, 0xFF}; // Cyber Pink Accent
#else
    // 4IFIR Signature Neon Glow Accent (Cyan -> Pink/Magenta Gradient)
    constexpr Color COLOR_FOCUS_CYAN   = {0x00, 0xE5, 0xFF, 0xFF}; // #00E5FF Electric Cyan
    constexpr Color COLOR_FOCUS_PINK   = {0xEC, 0x48, 0x99, 0xFF}; // #EC4899 Neon Magenta / Pink
    constexpr Color COLOR_FOCUS_RING   = COLOR_FOCUS_CYAN;
    constexpr Color COLOR_FOCUS_FILL   = {0x00, 0xE5, 0xFF, 0x1C}; // Soft translucent cyan glass tint
    constexpr Color COLOR_ACCENT       = {0x00, 0xE5, 0xFF, 0xFF}; // #00E5FF 4IFIR Cyan
#endif

    // Typography & Accents
    constexpr Color COLOR_TEXT_PRIMARY = {0xFF, 0xFF, 0xFF, 0xFF}; // #FFFFFF Crisp White
    constexpr Color COLOR_TEXT_MUTED   = {0x8E, 0x9D, 0xB0, 0xFF}; // #8E9DB0 Slate Muted"""

assert old_block in content, "old_block not found in theme.hpp"
content = content.replace(old_block, new_block)
theme_path.write_text(content, encoding="utf-8")
print("[+] theme.hpp updated with Cyber-Pink theme for After Dark!")
