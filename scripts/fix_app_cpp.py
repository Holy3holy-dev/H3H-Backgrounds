# scripts/fix_app_cpp.py
from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
text = p.read_text(encoding="utf-8")

# Fix open call
text = text.replace("m_videoPlayer.open(rec.fullPath);", "m_videoPlayer.open(rec.fullPath, m_renderer);")

# Fix unescaped newlines in runIntegrityCheck
old_integrity = text[text.find("void App::runIntegrityCheck()"):text.find("void App::executeDeleteCorruptedCovers()")]

new_integrity = """void App::runIntegrityCheck() {
    IntegrityReport report = Installer::validateAllInstalledCovers(m_platform->getCoversDirectory());
    m_lastIntegrityTotalChecked = report.totalChecked;

    if (report.issues.empty()) {
        m_activeDialog = DialogType::IntegrityCheckResult;
        m_dialogTitle = "Целостность видеофонов";
        if (report.totalChecked == 0) {
            m_dialogMessage = "В папке recordings/covers/ пока нет установленных видеофонов.";
        } else {
            m_dialogMessage = "Проверено видеофонов: " + std::to_string(report.totalChecked) +
                              "\\n\\nВсе установленные файлы полностью исправны, не повреждены и готовы к работе в меню Switch!";
        }
    } else {
        m_detectedIntegrityIssues = report.issues;
        m_activeDialog = DialogType::ConfirmDeleteCorrupted;
        m_dialogTitle = "Обнаружены повреждённые видеофоны!";
        std::string msg = "Найдено повреждений: " + std::to_string(report.issues.size()) +
                          " из " + std::to_string(report.totalChecked) + " файлов:\\n";
        for (size_t i = 0; i < report.issues.size() && i < 3; ++i) {
            msg += "• " + report.issues[i].filename + " (" + report.issues[i].reason + ")\\n";
        }
        if (report.issues.size() > 3) {
            msg += "• ... и ещё " + std::to_string(report.issues.size() - 3) + " файл(ов)\\n";
        }
        msg += "\\nУдалить повреждённые файлы во избежание сбоя или зависания меню Switch?";
        m_dialogMessage = msg;
        m_dialogFocus = 0;
    }
}

"""

text = text[:text.find("void App::runIntegrityCheck()")] + new_integrity + text[text.find("void App::executeDeleteCorruptedCovers()"):]
p.write_text(text, encoding="utf-8")
print("Fixed app.cpp syntax and newlines")
