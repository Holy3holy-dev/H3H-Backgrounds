# scripts/patch_v120_step2.py
from pathlib import Path

inst_cpp_path = Path("downloader/src/core/installer.cpp")
text = inst_cpp_path.read_text(encoding="utf-8")

# In installVariant, after checking actualSize < 1024:
validation_check = """
    uint64_t actualSize = fs::file_size(tempFilePath, ec);
    if (actualSize < 1024) {
        fs::remove(tempFilePath, ec);
        result.success = false;
        result.message = "Downloaded file is empty or corrupted";
        return result;
    }

    // Feature 5: Pre-install integrity check - never install corrupted/HTML error files
    std::string valErr;
    if (!validateVideoFile(tempFilePath, valErr)) {
        fs::remove(tempFilePath, ec);
        result.success = false;
        result.message = "Файл повреждён при скачивании: " + valErr;
        return result;
    }
"""

if "Pre-install integrity check" not in text:
    old_size_check = """    uint64_t actualSize = fs::file_size(tempFilePath, ec);
    if (actualSize < 1024) {
        fs::remove(tempFilePath, ec);
        result.success = false;
        result.message = "Downloaded file is empty or corrupted";
        return result;
    }"""
    text = text.replace(old_size_check, validation_check.strip())

# New functions to append before "} // namespace h3h"
new_methods = """
bool Installer::validateVideoFile(const std::string& filePath, std::string& outReason) {
    std::error_code ec;
    if (!fs::exists(filePath, ec) || !fs::is_regular_file(filePath, ec)) {
        outReason = "Файл не существует или недоступен";
        return false;
    }

    uint64_t size = fs::file_size(filePath, ec);
    if (size < 64 * 1024) {
        outReason = "Размер файла слишком мал (" + std::to_string(size) + " байт) — файл пуст или прерван";
        return false;
    }

    std::ifstream f(filePath, std::ios::binary);
    if (!f.is_open()) {
        outReason = "Не удалось открыть файл для чтения";
        return false;
    }

    char header[512] = {0};
    f.read(header, sizeof(header));
    std::streamsize bytesRead = f.gcount();
    if (bytesRead < 32) {
        outReason = "Файл слишком короткий для видео-контейнера";
        return false;
    }

    std::string headerStr(header, bytesRead);
    std::string headerLower = toLowerString(headerStr);

    // Check for HTML/XML/JSON error responses from web servers (e.g. Google Drive limits)
    if (headerLower.find("<!doctype") != std::string::npos ||
        headerLower.find("<html") != std::string::npos ||
        headerLower.find("404 not found") != std::string::npos ||
        headerLower.find("accessdenied") != std::string::npos ||
        headerLower.find("too many requests") != std::string::npos ||
        (headerLower.find("\"error\"") != std::string::npos && headerLower.find("\"message\"") != std::string::npos)) {
        outReason = "HTML/JSON ошибка сервера вместо видео (сбой CDN или лимит)";
        return false;
    }

    // Check MP4 / QuickTime box signature
    bool hasMp4Box = (headerStr.find("ftyp") != std::string::npos ||
                      headerStr.find("moov") != std::string::npos ||
                      headerStr.find("mdat") != std::string::npos ||
                      headerStr.find("skip") != std::string::npos ||
                      headerStr.find("wide") != std::string::npos);
    if (!hasMp4Box) {
        outReason = "Отсутствует корректный заголовок контейнера MP4";
        return false;
    }

    return true;
}

IntegrityReport Installer::validateAllInstalledCovers(const std::string& coversDir) {
    IntegrityReport report;
    std::error_code ec;
    if (!fs::exists(coversDir, ec) || !fs::is_directory(coversDir, ec)) {
        return report;
    }

    for (const auto& entry : fs::directory_iterator(coversDir, ec)) {
        if (ec) break;
        if (!entry.is_regular_file(ec)) continue;

        std::string filename = entry.path().filename().string();
        std::string ext = toLowerString(entry.path().extension().string());
        if (ext != ".mp4") continue;

        report.totalChecked++;
        std::string reason;
        if (!validateVideoFile(entry.path().string(), reason)) {
            IntegrityIssue issue;
            issue.filename = filename;
            issue.fullPath = entry.path().string();
            issue.fileSizeBytes = entry.file_size(ec);
            issue.reason = reason;

            std::string stem = entry.path().stem().string();
            if (Config::isValidTitleId(stem)) {
                issue.titleId = Config::normalizeTitleId(stem);
            } else {
                issue.titleId = stem;
            }
            report.issues.push_back(issue);
        } else {
            report.totalValid++;
        }
    }
    return report;
}

int Installer::deleteCorruptedCovers(const std::vector<IntegrityIssue>& issues) {
    int count = 0;
    std::error_code ec;
    for (const auto& issue : issues) {
        if (fs::exists(issue.fullPath, ec)) {
            fs::remove(issue.fullPath, ec);
            if (!ec) {
                count++;
            }
        }
    }
    return count;
}

static std::string formatRecordingSize(uint64_t bytes) {
    if (bytes < 1024) return std::to_string(bytes) + " B";
    if (bytes < 1024 * 1024) return std::to_string(bytes / 1024) + " KB";
    uint64_t mb = bytes / (1024 * 1024);
    uint64_t dec = (bytes / (1024 * 102)) % 10;
    return std::to_string(mb) + "." + std::to_string(dec) + " MB";
}

std::vector<LocalRecording> Installer::listLocalRecordings(const std::string& recordingsDir) {
    std::vector<LocalRecording> list;
    std::error_code ec;
    if (!fs::exists(recordingsDir, ec) || !fs::is_directory(recordingsDir, ec)) {
        return list;
    }

    struct EntryWithTime {
        LocalRecording rec;
        fs::file_time_type writeTime;
    };
    std::vector<EntryWithTime> entries;

    for (const auto& entry : fs::recursive_directory_iterator(recordingsDir, fs::directory_options::skip_permission_denied, ec)) {
        if (ec) break;
        if (!entry.is_regular_file(ec)) continue;

        std::string p = entry.path().string();
        std::string fn = entry.path().filename().string();
        std::string ext = toLowerString(entry.path().extension().string());

        // Strictly skip anything inside covers folder or temp/backup files
        if (p.find("/covers/") != std::string::npos ||
            p.find("\\\\covers\\\\") != std::string::npos ||
            p.find("/covers") != std::string::npos ||
            p.find("\\\\covers") != std::string::npos ||
            fn.find(".bak") != std::string::npos ||
            fn.find(".tmp") != std::string::npos) {
            continue;
        }

        if (ext == ".mp4" || ext == ".mkv" || ext == ".m4v") {
            LocalRecording rec;
            rec.filename = fn;
            rec.fullPath = p;
            rec.sizeBytes = entry.file_size(ec);
            rec.formattedSize = formatRecordingSize(rec.sizeBytes);
            rec.dateModified = "";

            auto ftime = entry.last_write_time(ec);
            entries.push_back({rec, ftime});
        }
    }

    // Sort newest first so recent captures are at the top
    std::sort(entries.begin(), entries.end(), [](const EntryWithTime& a, const EntryWithTime& b) {
        return a.writeTime > b.writeTime;
    });

    for (auto& item : entries) {
        list.push_back(item.rec);
    }

    return list;
}

InstallResult Installer::installLocalRecording(
    const std::string& coversDir,
    const std::string& titleId,
    const std::string& sourceRecordingPath,
    bool createBackup
) {
    InstallResult result;
    std::error_code ec;

    if (!Config::isValidTitleId(titleId)) {
        result.success = false;
        result.message = "Неверный формат Title ID";
        return result;
    }

    if (!fs::exists(sourceRecordingPath, ec) || !fs::is_regular_file(sourceRecordingPath, ec)) {
        result.success = false;
        result.message = "Файл записи не найден на карте памяти";
        return result;
    }

    std::string valReason;
    if (!validateVideoFile(sourceRecordingPath, valReason)) {
        result.success = false;
        result.message = "Выбранный файл записи повреждён: " + valReason;
        return result;
    }

    if (!fs::exists(coversDir, ec)) {
        fs::create_directories(coversDir, ec);
    }

    std::string normTitleId = Config::normalizeTitleId(titleId);
    fs::path tempPath = fs::path(coversDir) / (normTitleId + ".local.tmp");

    // Copy source to temporary location so the original recording is preserved
    fs::copy_file(sourceRecordingPath, tempPath, fs::copy_options::overwrite_existing, ec);
    if (ec) {
        result.success = false;
        result.message = "Ошибка копирования записи: " + ec.message();
        return result;
    }

    // Atomic install with backup handling
    result = installVariant(coversDir, normTitleId, tempPath.string(), "", 0, createBackup);
    if (result.success) {
        result.message = "Запись 4IFIR успешно установлена как видеофон!";
    }
    return result;
}

} // namespace h3h
"""

if "Installer::validateVideoFile" not in text:
    last_brace = text.rfind("} // namespace h3h")
    if last_brace != -1:
        text = text[:last_brace] + new_methods.strip() + "\n"
        inst_cpp_path.write_text(text, encoding="utf-8")
        print("Patched installer.cpp successfully")
    else:
        print("Could not find closing namespace brace")
else:
    print("installer.cpp already has validateVideoFile")
