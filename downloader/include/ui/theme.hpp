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
    constexpr Color COLOR_BG_BASE      = {0x0F, 0x13, 0x1A, 0xFF}; // #0F131A Main canvas
    constexpr Color COLOR_BG_SURFACE   = {0x1C, 0x24, 0x33, 0xFF}; // #1C2433 Sidebar / Cards
    constexpr Color COLOR_BG_ELEVATED  = {0x28, 0x33, 0x47, 0xFF}; // #283347 Active / Modals
    constexpr Color COLOR_BORDER       = {0x3D, 0x4B, 0x61, 0xFF}; // #3D4B61 Clear dividers
    constexpr Color COLOR_FOCUS_RING   = {0x00, 0xE5, 0xFF, 0xFF}; // #00E5FF Neon Cyan focus border
    constexpr Color COLOR_FOCUS_FILL   = {0x0F, 0x42, 0x66, 0xFF}; // #0F4266 List item selection highlight
    constexpr Color COLOR_TEXT_PRIMARY = {0xFF, 0xFF, 0xFF, 0xFF}; // #FFFFFF
    constexpr Color COLOR_TEXT_MUTED   = {0xA0, 0xAE, 0xC0, 0xFF}; // #A0AEC0 Secondary text
    constexpr Color COLOR_ACCENT       = {0x3B, 0x82, 0xF6, 0xFF}; // #3B82F6 Cobalt Blue
    constexpr Color COLOR_SUCCESS      = {0x10, 0xB9, 0x81, 0xFF}; // #10B981 Emerald Green
    constexpr Color COLOR_WARNING      = {0xF5, 0x9E, 0x0B, 0xFF}; // #F59E0B Amber
    constexpr Color COLOR_DANGER       = {0xEF, 0x44, 0x44, 0xFF}; // #EF4444 Crimson
}

} // namespace ui
} // namespace h3h
