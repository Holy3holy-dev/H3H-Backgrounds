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

    // Palette Tokens (High-Contrast Console Ergonomics)
    constexpr Color COLOR_BG_BASE      = {0x12, 0x14, 0x18, 0xFF}; // #121418 Main canvas
    constexpr Color COLOR_BG_SURFACE   = {0x1B, 0x1F, 0x26, 0xFF}; // #1B1F26 Sidebar / Cards
    constexpr Color COLOR_BG_ELEVATED  = {0x25, 0x2B, 0x35, 0xFF}; // #252B35 Active / Modals
    constexpr Color COLOR_BORDER       = {0x32, 0x3B, 0x47, 0xFF}; // #323B47 Subtle dividers
    constexpr Color COLOR_FOCUS_RING   = {0x00, 0xE5, 0xFF, 0xFF}; // #00E5FF Neon Cyan focus border
    constexpr Color COLOR_FOCUS_FILL   = {0x0D, 0x33, 0x49, 0xFF}; // #0D3349 List item selection highlight
    constexpr Color COLOR_TEXT_PRIMARY = {0xFF, 0xFF, 0xFF, 0xFF}; // #FFFFFF
    constexpr Color COLOR_TEXT_MUTED   = {0x9A, 0xA4, 0xB2, 0xFF}; // #9AA4B2 Secondary text
    constexpr Color COLOR_ACCENT       = {0x3B, 0x82, 0xF6, 0xFF}; // #3B82F6 Cobalt Blue
    constexpr Color COLOR_SUCCESS      = {0x10, 0xB9, 0x81, 0xFF}; // #10B981 Emerald Green
    constexpr Color COLOR_WARNING      = {0xF5, 0x9E, 0x0B, 0xFF}; // #F59E0B Amber
    constexpr Color COLOR_DANGER       = {0xEF, 0x44, 0x44, 0xFF}; // #EF4444 Crimson
}

} // namespace ui
} // namespace h3h
