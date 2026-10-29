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

    // 4IFIR Cyber-Glass High-Tech Palette
    constexpr Color COLOR_BG_BASE       = {0x09, 0x0C, 0x13, 0xFF}; // Deep OLED Obsidian Canvas
    constexpr Color COLOR_BG_HEADER     = {0x07, 0x0A, 0x10, 0xF5}; // Dark frosted top bar
    constexpr Color COLOR_BG_SURFACE    = {0x13, 0x1A, 0x28, 0xE6}; // Frosted glass cards (87% alpha)
    constexpr Color COLOR_BG_ELEVATED   = {0x1A, 0x22, 0x32, 0xF0}; // Active cards / Elevated glass
    constexpr Color COLOR_BG_MODAL      = {0x0E, 0x12, 0x1C, 0xF8}; // Dark acrylic dialog
    constexpr Color COLOR_BG_TILE       = {0x14, 0x1D, 0x2C, 0xE6}; // TorrentShopNX Dashboard Tile Background
    constexpr Color COLOR_BORDER        = {0x28, 0x33, 0x47, 0x99}; // Subtle glass border (60% alpha)
    constexpr Color COLOR_BORDER_STRONG = {0x3D, 0x4F, 0x6E, 0xCC}; // Elevated card border
    constexpr Color COLOR_DIVIDER       = {0xFF, 0xFF, 0xFF, 0x15}; // Subtle separator line
    
#ifdef H3H_AFTER_DARK
    // Neon Cyber-Pink / Magenta Aesthetic for After Dark (18+)
    constexpr Color COLOR_FOCUS_CYAN    = {0xFF, 0x2E, 0x93, 0xFF}; // #FF2E93 Neon Cyber-Pink
    constexpr Color COLOR_FOCUS_PINK    = {0xD9, 0x46, 0xEF, 0xFF}; // #D946EF Neon Purple / Fuchsia
    constexpr Color COLOR_FOCUS_RING    = {0xFF, 0x2E, 0x93, 0xFF};
    constexpr Color COLOR_FOCUS_FILL    = {0xFF, 0x2E, 0x93, 0x26}; // Translucent cyber-pink glass tint
    constexpr Color COLOR_ACCENT        = {0xFF, 0x2E, 0x93, 0xFF}; // Cyber Pink Accent
    constexpr Color COLOR_TILE_GLOW     = {0xFF, 0x2E, 0x93, 0x40}; // Focused tile neon glow
#else
    // 4IFIR Signature Neon Glow Accent (Cyan -> Pink/Magenta Gradient)
    constexpr Color COLOR_FOCUS_CYAN    = {0x00, 0xD2, 0xFF, 0xFF}; // #00E5FF Electric Cyan
    constexpr Color COLOR_FOCUS_PINK    = {0xEC, 0x48, 0x99, 0xFF}; // #EC4899 Neon Magenta / Pink
    constexpr Color COLOR_FOCUS_RING    = COLOR_FOCUS_CYAN;
    constexpr Color COLOR_FOCUS_FILL    = {0x00, 0xE5, 0xFF, 0x1E}; // Soft translucent cyan glass tint
    constexpr Color COLOR_ACCENT        = {0x00, 0xD2, 0xFF, 0xFF}; // #00E5FF 4IFIR Cyan
    constexpr Color COLOR_TILE_GLOW     = {0x00, 0xE5, 0xFF, 0x3A}; // Focused tile neon glow
#endif

    // Typography & Accents
    constexpr Color COLOR_TEXT_PRIMARY  = {0xFF, 0xFF, 0xFF, 0xFF}; // #FFFFFF Crisp White
    constexpr Color COLOR_TEXT_SECONDARY= {0xC2, 0xCE, 0xDC, 0xFF}; // #C2CEDC Secondary text
    constexpr Color COLOR_TEXT_MUTED    = {0x80, 0x91, 0xA5, 0xFF}; // #8091A5 Slate Muted
    constexpr Color COLOR_SUCCESS       = {0x10, 0xB9, 0x81, 0xFF}; // #10B981 Emerald Green
    constexpr Color COLOR_WARNING       = {0xF5, 0x9E, 0x0B, 0xFF}; // #F59E0B Amber
    constexpr Color COLOR_DANGER        = {0xF4, 0x3F, 0x5E, 0xFF}; // #F43F5E Rose / Coral

    // 4IFIR Video Icon Badge Colors (Vibrant Neon Cyan / Emerald)
    constexpr Color COLOR_ICON_BADGE         = {0x00, 0xD2, 0xFF, 0xFF}; // Radiant Electric Cyan
    constexpr Color COLOR_ICON_BADGE_FILL    = {0x08, 0x42, 0x5B, 0xCC}; // High-contrast translucent cyan tint
    constexpr Color COLOR_MUTED_BADGE_FILL   = {0x20, 0x2A, 0x3B, 0x88}; // Muted badge background
    constexpr Color COLOR_SUCCESS_BADGE_FILL = {0x0E, 0x4D, 0x38, 0xCC}; // Success badge background
    constexpr Color COLOR_PILL_BG            = {0x18, 0x20, 0x2E, 0xDD}; // Pill button background
    constexpr Color COLOR_STATUS_BAR_BG      = {0x06, 0x09, 0x0F, 0xF5}; // Dark bottom status bar
}

} // namespace ui
} // namespace h3h
