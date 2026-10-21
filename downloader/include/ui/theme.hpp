#pragma once

#include <cstdint>

namespace h3h {
namespace ui {

struct Color {
    uint8_t r, g, b, a;
};

namespace Theme {
    // 720p Reference Frame Dimensions (Internal logical coordinate space)
    constexpr int SCREEN_WIDTH  = 1280;
    constexpr int SCREEN_HEIGHT = 720;

    // 4IFIR Cyber-Glass High-Tech Palette (Matching Official 4IFIR System Screenshots)
    constexpr Color COLOR_BG_BASE      = {0x0A, 0x0D, 0x14, 0xFF}; // Deep OLED Obsidian / Glass Canvas
    constexpr Color COLOR_BG_SURFACE   = {0x13, 0x18, 0x24, 0xDD}; // Frosted glass cards (87% alpha)
    constexpr Color COLOR_BG_ELEVATED  = {0x1B, 0x22, 0x30, 0xF0}; // Active cards / Elevated glass
    constexpr Color COLOR_BG_MODAL     = {0x10, 0x14, 0x1E, 0xF8}; // Dark acrylic dialog
    constexpr Color COLOR_BORDER       = {0x28, 0x33, 0x47, 0x99}; // Subtle glass border (60% alpha)
    constexpr Color COLOR_DIVIDER      = {0xFF, 0xFF, 0xFF, 0x18}; // 10% white separator line
    
#ifdef H3H_AFTER_DARK
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
    constexpr Color COLOR_TEXT_MUTED   = {0x8E, 0x9D, 0xB0, 0xFF}; // #8E9DB0 Slate Muted
    constexpr Color COLOR_SUCCESS      = {0x10, 0xB9, 0x81, 0xFF}; // #10B981 Emerald Green
    constexpr Color COLOR_WARNING      = {0xF5, 0x9E, 0x0B, 0xFF}; // #F59E0B Amber
    constexpr Color COLOR_DANGER       = {0xF4, 0x3F, 0x5E, 0xFF}; // #F43F5E Rose / Coral
}

} // namespace ui
} // namespace h3h
