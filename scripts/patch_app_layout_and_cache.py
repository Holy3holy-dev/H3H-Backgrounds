from pathlib import Path
import json
import re

# 1. Update catalog.json variant IDs for RDR and Cuphead
cat_path = Path(r"e:\videofon\catalog\data\catalog.json")
cat = json.loads(cat_path.read_text(encoding="utf-8"))

for g in cat.get("games", []):
    if g.get("titleId") == "01007820196A6000":
        for v in g.get("variants", []):
            v["id"] = "rdr-clean-motion-hero"
            print("[+] Updated RDR variant id to rdr-clean-motion-hero")
    elif g.get("titleId") == "0100A5C00D162000":
        for v in g.get("variants", []):
            v["id"] = "cuphead-clean-motion"
            print("[+] Updated Cuphead variant id to cuphead-clean-motion")

cat_path.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")

# Sync to romfs/catalog.json
romfs_cat = Path(r"e:\videofon\downloader\romfs\catalog.json")
romfs_cat.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
print("[+] Synced to downloader/romfs/catalog.json")

# 2. Patch app.cpp
app_path = Path(r"e:\videofon\downloader\src\ui\app.cpp")
text = app_path.read_text(encoding="utf-8")

# A. Replace variant rendering in renderTabMyGames
old_var_render = re.compile(
    r'// Variant Title & Style \(bounded so it never overlaps install button\).*?vY \+= 80;',
    re.DOTALL
)

new_var_render = '''// Variant Title & Style (bounded so it never overlaps install button)
                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                drawText(vTitle, 545, vY + 12, isVarSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 450);

                // Tech Specs Line (Width capped at 230 to avoid overlap with badges)
                std::string meta = std::to_string(v.width) + "x" + std::to_string(v.height) + " @" +
                                   std::to_string(static_cast<int>(v.fps)) + "fps  |  " +
                                   ([&]() {
                    double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
                    char buf[16];
                    if (mb >= 0.1) snprintf(buf, sizeof(buf), "%.1f MB", mb);
                    else snprintf(buf, sizeof(buf), "~3.5 MB");
                    return std::string(buf);
                })();
                drawText(meta, 545, vY + 41, Theme::COLOR_TEXT_MUTED, 12, 230);

                // Active installed background badge
                bool isActiveOnConsole = false;
                if (selGame.hasInstalledCover && selGame.installedCoverSizeBytes > 0 && v.sizeBytes > 0) {
                    if (std::abs((int64_t)v.sizeBytes - (int64_t)selGame.installedCoverSizeBytes) <= 2048) {
                        isActiveOnConsole = true;
                    }
                }
                if (isActiveOnConsole) {
                    drawRect(785, vY + 38, 105, 22, {0x10, 0xB9, 0x81, 0x44});
                    drawRectOutline(785, vY + 38, 105, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("УСТАНОВЛЕН", 797, vY + 43, Theme::COLOR_SUCCESS, 10);
                }

                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(905, vY + 38, 70, 22, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(905, vY + 38, 70, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", 924, vY + 43, Theme::COLOR_SUCCESS, 10);
                } else {
                    drawRect(905, vY + 38, 85, 22, {0x28, 0x33, 0x47, 0x44});
                    drawRectOutline(905, vY + 38, 85, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", 916, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                }

                if (isVarSelected) {
                    drawRect(1005, vY + 18, 205, 36, Theme::COLOR_FOCUS_FILL);
                    drawRectOutline(1005, vY + 18, 205, 36, Theme::COLOR_FOCUS_CYAN, 1);
                    std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                    drawText(btnText, 1025, vY + 27, Theme::COLOR_FOCUS_CYAN, 13);
                }

                vY += 80;'''

text, c1 = old_var_render.subn(new_var_render, text)
print(f"Replaced variant rendering in TabMyGames: {c1}")

# B. Replace renderFullscreenPreview bottom HUD layout and opacity
old_hud = re.compile(
    r'// 2\. Bottom 4IFIR Cyber-Glass HUD overlay.*?drawText\("\[B\] Закрыть", hudX \+ 1115, hudY \+ 62, Theme::COLOR_TEXT_MUTED, 13\);',
    re.DOTALL
)

new_hud = '''// 2. Bottom 4IFIR Cyber-Glass HUD overlay
    int hudX = 40;
    int hudY = 585;
    int hudW = 1200;
    int hudH = 105;
    // Solid dark obsidian to prevent underlying video text/artifacts from bleeding through
    drawRect(hudX, hudY, hudW, hudH, {0x0D, 0x11, 0x1A, 0xF6});
    drawNeonGradientOutline(hudX, hudY, hudW, hudH, 2);

    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
        const auto& g = m_installedGames[m_myGamesSelectedIndex];
        if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
            int totalV = static_cast<int>(g.catalogEntry.variants.size());
            int curV = std::clamp(m_selectedVariantIndex, 0, totalV - 1);
            const auto& v = g.catalogEntry.variants[curV];

            // Game Name (Left top)
            drawText(g.name, hudX + 25, hudY + 12, Theme::COLOR_TEXT_PRIMARY, 19, 580);

            // Variant Name & Style (Left middle)
            std::string varTitle = std::to_string(curV + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
            drawText(varTitle, hudX + 25, hudY + 38, Theme::COLOR_FOCUS_CYAN, 16, 580);

            // Tech specs + Audio pill (Left bottom)
            double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
            char mbBuf[16];
            if (mb >= 0.1) snprintf(mbBuf, sizeof(mbBuf), "%.1f MB", mb);
            else snprintf(mbBuf, sizeof(mbBuf), "~3.5 MB");

            std::string specs = "1280x720 @30fps  |  " + std::string(mbBuf) +
                                "  |  Вариант " + std::to_string(curV + 1) + " из " + std::to_string(totalV);
            drawText(specs, hudX + 25, hudY + 68, Theme::COLOR_TEXT_MUTED, 13, 390);

            if (v.hasAudio) {
                drawRect(hudX + 430, hudY + 66, 75, 22, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(hudX + 430, hudY + 66, 75, 22, Theme::COLOR_SUCCESS, 1);
                drawText("ЗВУК", hudX + 451, hudY + 70, Theme::COLOR_SUCCESS, 10);
            } else {
                drawRect(hudX + 430, hudY + 66, 85, 22, {0x28, 0x33, 0x47, 0x44});
                drawRectOutline(hudX + 430, hudY + 66, 85, 22, Theme::COLOR_BORDER, 1);
                drawText("БЕЗ ЗВУКА", hudX + 439, hudY + 70, Theme::COLOR_TEXT_MUTED, 10);
            }

            bool isActiveVariant = false;
            if (g.hasInstalledCover && g.installedCoverSizeBytes > 0 && v.sizeBytes > 0) {
                if (std::abs((int64_t)v.sizeBytes - (int64_t)g.installedCoverSizeBytes) <= 2048) {
                    isActiveVariant = true;
                }
            }

            if (isActiveVariant) {
                drawRect(hudX + 530, hudY + 66, 185, 22, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(hudX + 530, hudY + 66, 185, 22, Theme::COLOR_SUCCESS, 1);
                drawText("УСТАНОВЛЕН НА SWITCH", hudX + 542, hudY + 70, Theme::COLOR_SUCCESS, 10);
            }

            // Right side buttons
            if (isActiveVariant) {
                drawRect(hudX + 900, hudY + 14, 270, 38, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_SUCCESS, 1);
                drawText("[A] Переустановить", hudX + 950, hudY + 24, Theme::COLOR_SUCCESS, 14);
            } else {
                drawRect(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_FILL);
                drawRectOutline(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_CYAN, 1);
                drawText("[A] Установить видеофон", hudX + 930, hudY + 24, Theme::COLOR_FOCUS_CYAN, 14);
            }

            if (totalV > 1) {
                drawText("[◀ / ▶ D-Pad] Варианты на лету", hudX + 880, hudY + 68, Theme::COLOR_FOCUS_PINK, 12);
            }
            drawText("[B] Закрыть", hudX + 1100, hudY + 68, Theme::COLOR_TEXT_MUTED, 13);'''

text, c2 = old_hud.subn(new_hud, text)
print(f"Replaced fullscreen preview HUD: {c2}")

# C. In loadPreviewTexture, check cached video size validity
old_cache_check = re.compile(
    r'\} else if \(std::filesystem::exists\(vidFile, ec\) && std::filesystem::file_size\(vidFile, ec\) > 50000\) \{\s*'
    r'// Play directly from cached MP4!\s*'
    r'm_videoPlayer\.open\(vidFile, m_renderer\);\s*'
    r'\}',
    re.MULTILINE
)

new_cache_check = '''} else if (std::filesystem::exists(vidFile, ec)) {
        uint64_t cachedSz = std::filesystem::file_size(vidFile, ec);
        bool isCachedValid = false;
        if (variant.sizeBytes > 0 && std::abs((int64_t)cachedSz - (int64_t)variant.sizeBytes) <= 4096) {
            isCachedValid = true;
        } else if (variant.sizeBytes == 0 && cachedSz > 50000) {
            isCachedValid = true;
        } else {
            // Stale cache from older version -> remove so fresh clean video is downloaded
            std::filesystem::remove(vidFile, ec);
            std::filesystem::remove(thumbFile, ec);
        }
        if (isCachedValid) {
            m_videoPlayer.open(vidFile, m_renderer);
        }
    }'''

text, c3 = old_cache_check.subn(new_cache_check, text)
print(f"Replaced cached video validation in loadPreviewTexture: {c3}")

app_path.write_text(text, encoding="utf-8")
print("[+] Successfully patched app.cpp!")
