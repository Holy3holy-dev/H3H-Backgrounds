from pathlib import Path
import re

app_path = Path(r"e:\videofon\downloader\src\ui\app.cpp")
text = app_path.read_text(encoding="utf-8")

# 1. Fix m_dialogMessage construction
old_msg = re.compile(
    r'm_dialogMessage = \(m_language == Language::Russian\)\s*'
    r'\?\s*\("Загрузка H3H-Backgrounds\.nro с GitHub \(" \+ releaseNotes \+ "\)\.\.\."\)\s*'
    r':\s*\("Downloading new release from GitHub\.\.\."\);',
    re.MULTILINE
)
new_msg = 'm_dialogMessage = (m_language == Language::Russian)\n' \
          '            ? "Загрузка H3H-Backgrounds.nro с GitHub..."\n' \
          '            : "Downloading H3H-Backgrounds.nro from GitHub...";'

text, count1 = old_msg.subn(new_msg, text)
print(f"Replaced dialog message: {count1}")

# 2. Fix UpdateProgress renderDialog
old_upd_dlg = re.compile(
    r'if \(m_activeDialog == DialogType::UpdateProgress\) \{\s*'
    r'drawText\(m_dialogMessage, dx \+ 35, dy \+ 70, Theme::COLOR_TEXT_PRIMARY, 15\);',
    re.MULTILINE
)
new_upd_dlg = 'if (m_activeDialog == DialogType::UpdateProgress) {\n' \
              '        drawText(m_dialogTitle, dx + 35, dy + 25, Theme::COLOR_FOCUS_CYAN, 20, dw - 70);\n' \
              '        drawText(m_dialogMessage, dx + 35, dy + 70, Theme::COLOR_TEXT_PRIMARY, 15, dw - 70);'

text, count2 = old_upd_dlg.subn(new_upd_dlg, text)
print(f"Replaced update dialog drawText: {count2}")

# 3. Add maxWidth to dialog footer text in UpdateProgress
old_footer = re.compile(
    r'drawText\("Обновление безопасно заменяет файл на SD карте без перезаписи в Horizon OS", dx \+ 35, dy \+ 185, Theme::COLOR_TEXT_MUTED, 12\);',
    re.MULTILINE
)
new_footer = 'drawText("Обновление безопасно заменяет файл на SD карте без перезаписи в Horizon OS", dx + 35, dy + 185, Theme::COLOR_TEXT_MUTED, 12, dw - 70);'
text, count3 = old_footer.subn(new_footer, text)
print(f"Replaced update dialog footer: {count3}")

# 4. Fix hardcoded v1.0.3 in TabSettings
old_settings_row = re.compile(
    r'\{"Обновление приложения \(NRO\)", "Проверить и установить новую версию H3H-Backgrounds\.nro с GitHub", "v1\.0\.3 \[A - Обновить\]", Theme::COLOR_FOCUS_CYAN\},',
    re.MULTILINE
)
new_settings_row = '{"Обновление приложения (NRO)", "Проверить и установить новую версию H3H-Backgrounds.nro с GitHub", std::string("v") + Config::APP_VERSION + " [A - Обновить]", Theme::COLOR_FOCUS_CYAN},'
text, count4 = old_settings_row.subn(new_settings_row, text)
print(f"Replaced settings row: {count4}")

# 5. Add maxWidth to Settings rows
old_rows_draw = re.compile(
    r'drawText\(rows\[i\]\.title, 75, rowY \+ 14, isFocused \? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17\);\s*'
    r'drawText\(rows\[i\]\.desc, 75, rowY \+ 42, Theme::COLOR_TEXT_MUTED, 13\);\s*'
    r'// Right value pill\s*'
    r'drawText\(rows\[i\]\.value, 950, rowY \+ 26, rows\[i\]\.valColor, 15\);',
    re.MULTILINE
)
new_rows_draw = 'drawText(rows[i].title, 75, rowY + 14, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17, 850);\n' \
                '        drawText(rows[i].desc, 75, rowY + 42, Theme::COLOR_TEXT_MUTED, 13, 850);\n\n' \
                '        // Right value pill\n' \
                '        drawText(rows[i].value, 950, rowY + 26, rows[i].valColor, 15, 260);'
text, count5 = old_rows_draw.subn(new_rows_draw, text)
print(f"Replaced settings rows drawText: {count5}")

app_path.write_text(text, encoding="utf-8")
print("Done patching app.cpp!")
