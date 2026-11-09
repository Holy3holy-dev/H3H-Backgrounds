#include "core/installer.hpp"
#include "core/config.hpp"
#include "core/sha256.hpp"

#include <filesystem>
#include <fstream>
#include <algorithm>
#include <cctype>

namespace fs = std::filesystem;

namespace h3h {

namespace {

std::string toLowerString(const std::string& str) {
    std::string lower = str;
    std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char c) {
        return std::tolower(c);
    });
    return lower;
}

bool caseInsensitiveCompare(const std::string& a, const std::string& b) {
    return toLowerString(a) == toLowerString(b);
}

} // namespace


std::vector<InstalledCoverVariant> Installer::findInstalledCoverVariants(
    const std::string& coversDir,
    const std::string& titleId
) {
    std::vector<InstalledCoverVariant> variants;
    if (!Config::isValidTitleId(titleId)) return variants;

    std::error_code ec;
    if (!fs::exists(coversDir, ec) || !fs::is_directory(coversDir, ec)) {
        return variants;
    }

    std::string normTitleId = Config::normalizeTitleId(titleId);
    std::string lowerTitleId = toLowerString(normTitleId);

    for (const auto& entry : fs::directory_iterator(coversDir, ec)) {
        if (ec) break;
        if (!entry.is_regular_file(ec)) continue;

        std::string filename = entry.path().filename().string();
        std::string lowerFilename = toLowerString(filename);

        // Name must start with lowerTitleId and end with .mp4
        if (lowerFilename.length() >= 20 &&
            lowerFilename.rfind(".mp4") == (lowerFilename.length() - 4) &&
            lowerFilename.rfind(lowerTitleId, 0) == 0) {

            std::string middle = lowerFilename.substr(lowerTitleId.length(), lowerFilename.length() - 4 - lowerTitleId.length());
            InstalledCoverVariant var;
            var.filePath = entry.path().string();
            var.filename = filename;
            var.sizeBytes = entry.file_size(ec);

            if (middle.empty()) {
                // Exact match: TITLEID.mp4 -> Active cover (index 0)
                var.index = 0;
                var.isActive = true;
                variants.push_back(var);
            } else if (middle.length() >= 2 && middle[0] == '_') {
                // Numbered match: TITLEID_1.mp4, TITLEID_2.mp4, etc.
                std::string numPart = middle.substr(1);
                bool allDigits = !numPart.empty() && std::all_of(numPart.begin(), numPart.end(), [](unsigned char c) {
                    return std::isdigit(c);
                });
                if (allDigits) {
                    try {
                        var.index = std::stoi(numPart);
                        var.isActive = false;
                        variants.push_back(var);
                    } catch (...) {
                    }
                }
            }
        }
    }

    // Sort: active first, then ascending by index
    std::sort(variants.begin(), variants.end(), [](const InstalledCoverVariant& a, const InstalledCoverVariant& b) {
        if (a.isActive != b.isActive) return a.isActive;
        return a.index < b.index;
    });

    return variants;
}

std::string Installer::getNextAvailableCoverPath(
    const std::string& coversDir,
    const std::string& titleId,
    int* outIndex
) {
    auto existing = findInstalledCoverVariants(coversDir, titleId);
    std::string normTitleId = Config::normalizeTitleId(titleId);

    bool hasActive = false;
    std::vector<int> usedIndices;
    for (const auto& v : existing) {
        if (v.index == 0) hasActive = true;
        usedIndices.push_back(v.index);
    }

    if (!hasActive) {
        if (outIndex) *outIndex = 0;
        return (fs::path(coversDir) / Config::getTargetCoverFileName(normTitleId)).string();
    }

    int nextIdx = 1;
    while (std::find(usedIndices.begin(), usedIndices.end(), nextIdx) != usedIndices.end()) {
        nextIdx++;
    }

    if (outIndex) *outIndex = nextIdx;
    return (fs::path(coversDir) / Config::getCoverVariantFileName(normTitleId, nextIdx)).string();
}

bool Installer::switchActiveCover(
    const std::string& coversDir,
    const std::string& titleId,
    int targetIndex
) {
    if (!Config::isValidTitleId(titleId) || targetIndex <= 0) return false;

    std::error_code ec;
    std::string normTitleId = Config::normalizeTitleId(titleId);
    fs::path activePath = fs::path(coversDir) / Config::getTargetCoverFileName(normTitleId);
    fs::path targetPath = fs::path(coversDir) / Config::getCoverVariantFileName(normTitleId, targetIndex);

    if (!fs::exists(targetPath, ec)) return false;

    if (!fs::exists(activePath, ec)) {
        fs::rename(targetPath, activePath, ec);
        return !ec;
    }

    fs::path swapPath = fs::path(coversDir) / (normTitleId + ".swap.tmp");
    if (fs::exists(swapPath, ec)) {
        fs::remove(swapPath, ec);
    }

    fs::rename(activePath, swapPath, ec);
    if (ec) return false;

    fs::rename(targetPath, activePath, ec);
    if (ec) {
        std::error_code rb;
        fs::rename(swapPath, activePath, rb);
        return false;
    }

    fs::rename(swapPath, targetPath, ec);
    if (ec) {
        std::error_code rb;
        fs::rename(activePath, targetPath, rb);
        fs::rename(swapPath, activePath, rb);
        return false;
    }

    return true;
}

bool Installer::deleteCoverVariant(
    const std::string& coversDir,
    const std::string& titleId,
    int index
) {
    if (!Config::isValidTitleId(titleId)) return false;
    std::string normTitleId = Config::normalizeTitleId(titleId);
    std::error_code ec;

    if (index > 0) {
        fs::path varPath = fs::path(coversDir) / Config::getCoverVariantFileName(normTitleId, index);
        if (fs::exists(varPath, ec)) {
            fs::remove(varPath, ec);
            return !ec;
        }
        return false;
    }

    fs::path activePath = fs::path(coversDir) / Config::getTargetCoverFileName(normTitleId);
    if (fs::exists(activePath, ec)) {
        fs::remove(activePath, ec);

        // Auto-promote TITLEID_1.mp4 to TITLEID.mp4 if present
        fs::path alt1Path = fs::path(coversDir) / Config::getCoverVariantFileName(normTitleId, 1);
        if (fs::exists(alt1Path, ec)) {
            fs::rename(alt1Path, activePath, ec);
        }
        return true;
    }
    return false;
}

bool Installer::deleteAllCoverVariants(
    const std::string& coversDir,
    const std::string& titleId
) {
    auto variants = findInstalledCoverVariants(coversDir, titleId);
    std::error_code ec;
    bool anyDeleted = false;
    for (const auto& v : variants) {
        if (fs::exists(v.filePath, ec)) {
            fs::remove(v.filePath, ec);
            anyDeleted = true;
        }
    }
    std::string bPath;
    uint64_t bSize = 0;
    if (findExistingBackup(coversDir, titleId, bPath, bSize)) {
        fs::remove(bPath, ec);
    }
    return anyDeleted;
}

bool Installer::findExistingCover(
    const std::string& coversDir,
    const std::string& titleId,
    std::string& outCoverPath,
    uint64_t& outSizeBytes
) {
    if (!Config::isValidTitleId(titleId)) return false;

    std::error_code ec;
    if (!fs::exists(coversDir, ec) || !fs::is_directory(coversDir, ec)) {
        return false;
    }

    std::string targetTargetName = Config::getTargetCoverFileName(titleId);

    for (const auto& entry : fs::directory_iterator(coversDir, ec)) {
        if (ec) break;
        if (!entry.is_regular_file(ec)) continue;

        std::string filename = entry.path().filename().string();
        if (caseInsensitiveCompare(filename, targetTargetName)) {
            outCoverPath = entry.path().string();
            outSizeBytes = entry.file_size(ec);
            return true;
        }
    }

    return false;
}

bool Installer::findExistingBackup(
    const std::string& coversDir,
    const std::string& titleId,
    std::string& outBackupPath,
    uint64_t& outSizeBytes
) {
    if (!Config::isValidTitleId(titleId)) return false;

    std::error_code ec;
    if (!fs::exists(coversDir, ec) || !fs::is_directory(coversDir, ec)) {
        return false;
    }

    std::string targetBackupName = Config::getBackupCoverFileName(titleId);

    for (const auto& entry : fs::directory_iterator(coversDir, ec)) {
        if (ec) break;
        if (!entry.is_regular_file(ec)) continue;

        std::string filename = entry.path().filename().string();
        if (caseInsensitiveCompare(filename, targetBackupName)) {
            outBackupPath = entry.path().string();
            outSizeBytes = entry.file_size(ec);
            return true;
        }
    }

    return false;
}

bool Installer::findExistingIcon(
    const std::string& iconsDir,
    const std::string& titleId,
    std::string& outIconPath,
    uint64_t& outSizeBytes
) {
    if (!Config::isValidTitleId(titleId)) return false;

    std::error_code ec;
    if (!fs::exists(iconsDir, ec) || !fs::is_directory(iconsDir, ec)) {
        return false;
    }

    std::string targetTargetName = Config::getTargetIconFileName(titleId);

    for (const auto& entry : fs::directory_iterator(iconsDir, ec)) {
        if (ec) break;
        if (!entry.is_regular_file(ec)) continue;

        std::string filename = entry.path().filename().string();
        if (caseInsensitiveCompare(filename, targetTargetName)) {
            outIconPath = entry.path().string();
            outSizeBytes = entry.file_size(ec);
            return true;
        }
    }

    return false;
}

InstallResult Installer::installIcon(
    const std::string& iconsDir,
    const std::string& titleId,
    const std::string& tempFilePath,
    uint64_t expectedSizeBytes,
    bool createBackup
) {
    InstallResult result;
    result.success = false;

    if (!Config::isValidTitleId(titleId)) {
        result.message = "Неверный формат Title ID";
        return result;
    }

    std::error_code ec;
    if (!fs::exists(tempFilePath, ec)) {
        result.message = "Временный файл иконки не найден";
        return result;
    }

    // Pre-install integrity check - never install corrupted/HTML error files as video icons
    std::string valErr;
    if (!validateVideoFile(tempFilePath, valErr)) {
        fs::remove(tempFilePath, ec);
        result.success = false;
        result.message = "Ошибка валидации видео: " + valErr;
        return result;
    }

    fs::create_directories(iconsDir, ec);

    std::string targetIconName = Config::getTargetIconFileName(titleId);
    fs::path targetPath = fs::path(iconsDir) / targetIconName;
    fs::path backupPath = fs::path(iconsDir) / Config::getBackupIconFileName(titleId);

    // Existing icon backup
    std::string existingIconPath;
    uint64_t existingSize = 0;
    bool hasExisting = findExistingIcon(iconsDir, titleId, existingIconPath, existingSize);

    if (hasExisting && createBackup) {
        fs::copy_file(existingIconPath, backupPath, fs::copy_options::overwrite_existing, ec);
        result.backupPath = backupPath.string();
    }

    // Replace target with temp file
    fs::rename(tempFilePath, targetPath, ec);
    if (ec) {
        fs::copy_file(tempFilePath, targetPath, fs::copy_options::overwrite_existing, ec);
        fs::remove(tempFilePath, ec);
    }

    result.success = true;
    result.installedPath = targetPath.string();
    result.message = "Видеоиконка 4IFIR успешно установлена";
    return result;
}

bool Installer::deleteIcon(
    const std::string& iconsDir,
    const std::string& titleId
) {
    std::string iconPath;
    uint64_t sz = 0;
    if (findExistingIcon(iconsDir, titleId, iconPath, sz)) {
        std::error_code ec;
        fs::remove(iconPath, ec);
        return !ec;
    }
    return false;
}

InstallResult Installer::installVariant(
    const std::string& coversDir,
    const std::string& titleId,
    const std::string& tempFilePath,
    const std::string& expectedSha256,
    uint64_t expectedSizeBytes,
    bool createBackup
) {
    InstallResult result;
    std::error_code ec;

    // 1. Boundary check: Title ID validation
    if (!Config::isValidTitleId(titleId)) {
        result.success = false;
        result.message = "Invalid Nintendo Switch Title ID format";
        return result;
    }

    // 2. Ensure covers directory exists
    if (!fs::exists(coversDir, ec)) {
        fs::create_directories(coversDir, ec);
        if (ec) {
            result.success = false;
            result.message = "Failed to create covers directory: " + ec.message();
            return result;
        }
    }

    // 3. Verify downloaded temp file existence
    if (!fs::exists(tempFilePath, ec) || !fs::is_regular_file(tempFilePath, ec)) {
        result.success = false;
        result.message = "Temporary download file not found";
        return result;
    }

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

    // 4. Verify SHA-256 checksum (if provided)
    if (!expectedSha256.empty()) {
        std::string computedHash;
        if (!SHA256::hashFile(tempFilePath, computedHash)) {
            fs::remove(tempFilePath, ec);
            result.success = false;
            result.message = "Failed to compute SHA-256 of downloaded file";
            return result;
        }

        if (!caseInsensitiveCompare(computedHash, expectedSha256)) {
            fs::remove(tempFilePath, ec);
            result.success = false;
            result.message = "SHA-256 integrity verification failed! (computed: " + computedHash +
                             ", expected: " + expectedSha256 + ")";
            return result;
        }
    }

    // 5. Deterministic target path (always uppercase TITLEID.mp4)
    std::string normTitleId = Config::normalizeTitleId(titleId);
    fs::path targetPath = fs::path(coversDir) / Config::getTargetCoverFileName(normTitleId);
    fs::path backupPath = fs::path(coversDir) / Config::getBackupCoverFileName(normTitleId);

    // 6. Check for existing cover (case-insensitive search)
    std::string existingCoverPath;
    uint64_t existingSize = 0;
    bool hadExistingCover = findExistingCover(coversDir, normTitleId, existingCoverPath, existingSize);

    bool backupCreated = false;
    std::string backupCreatedFrom;

    if (hadExistingCover) {
        // Multi-cover support: NEVER delete old video covers!
        // Find next free numbered index for alternative cover
        int nextIndex = 1;
        getNextAvailableCoverPath(coversDir, normTitleId, &nextIndex);
        if (nextIndex <= 0) nextIndex = 1;

        // Move existing active cover to TITLEID_N.mp4
        fs::path altPath = fs::path(coversDir) / Config::getCoverVariantFileName(normTitleId, nextIndex);
        fs::rename(existingCoverPath, altPath, ec);
        if (ec) {
            fs::copy_file(existingCoverPath, altPath, fs::copy_options::overwrite_existing, ec);
            fs::remove(existingCoverPath, ec);
        }

        // Install downloaded file as active TITLEID.mp4
        fs::rename(tempFilePath, targetPath, ec);
        if (ec) {
            fs::copy_file(tempFilePath, targetPath, fs::copy_options::overwrite_existing, ec);
            fs::remove(tempFilePath, ec);
        }

        result.success = true;
        result.installedPath = targetPath.string();
        result.message = "Новый видеофон установлен как активный. Прежний сохранён как вариант #" + std::to_string(nextIndex);
        return result;
    }

    // Direct installation for first cover
    fs::rename(tempFilePath, targetPath, ec);
    if (ec) {
        fs::copy_file(tempFilePath, targetPath, fs::copy_options::overwrite_existing, ec);
        fs::remove(tempFilePath, ec);
    }

    result.success = true;
    result.installedPath = targetPath.string();
    result.message = "Видеофон успешно установлен для " + normTitleId;
    return result;
}

InstallResult Installer::restoreBackup(
    const std::string& coversDir,
    const std::string& titleId
) {
    InstallResult result;
    std::error_code ec;

    if (!Config::isValidTitleId(titleId)) {
        result.success = false;
        result.message = "Invalid Title ID";
        return result;
    }

    std::string normTitleId = Config::normalizeTitleId(titleId);
    std::string backupPathStr;
    uint64_t backupSize = 0;

    if (!findExistingBackup(coversDir, normTitleId, backupPathStr, backupSize)) {
        result.success = false;
        result.message = "No backup (.bak) found for Title ID " + normTitleId;
        return result;
    }

    // Find if active cover exists
    std::string existingCoverStr;
    uint64_t existingCoverSize = 0;
    bool hasActiveCover = findExistingCover(coversDir, normTitleId, existingCoverStr, existingCoverSize);

    fs::path targetPath = fs::path(coversDir) / Config::getTargetCoverFileName(normTitleId);
    fs::path backupPath = fs::path(backupPathStr);

    // If active cover exists, remove it
    if (hasActiveCover) {
        fs::remove(existingCoverStr, ec);
        if (ec) {
            result.success = false;
            result.message = "Failed to remove active cover during restore: " + ec.message();
            return result;
        }
    }

    // Rename backup to target MP4
    fs::rename(backupPath, targetPath, ec);
    if (ec) {
        result.success = false;
        result.message = "Failed to restore backup file: " + ec.message();
        return result;
    }

    result.success = true;
    result.installedPath = targetPath.string();
    result.message = "Backup successfully restored for " + normTitleId;
    return result;
}

bool Installer::deleteCover(
    const std::string& coversDir,
    const std::string& titleId,
    bool deleteBackup
) {
    if (!Config::isValidTitleId(titleId)) return false;

    std::string normTitleId = Config::normalizeTitleId(titleId);
    std::string coverPath;
    uint64_t coverSize = 0;
    std::error_code ec;

    bool deletedSomething = false;
    if (findExistingCover(coversDir, normTitleId, coverPath, coverSize)) {
        fs::remove(coverPath, ec);
        if (!ec) deletedSomething = true;
    }

    if (deleteBackup) {
        std::string backupPath;
        uint64_t backupSize = 0;
        if (findExistingBackup(coversDir, normTitleId, backupPath, backupSize)) {
            fs::remove(backupPath, ec);
            if (!ec) deletedSomething = true;
        }
    }

    return deletedSomething;
}

bool Installer::validateVideoFile(const std::string& filePath, std::string& outReason) {
    std::error_code ec;
    if (!fs::exists(filePath, ec) || !fs::is_regular_file(filePath, ec)) {
        outReason = "Файл не существует или недоступен";
        return false;
    }

    uint64_t size = fs::file_size(filePath, ec);
    if (size < 4096) {
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
        (headerLower.find("error") != std::string::npos && headerLower.find("message") != std::string::npos)) {
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
            issue.sizeBytes = entry.file_size(ec);
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
            p.find("\\covers\\") != std::string::npos ||
            p.find("/covers") != std::string::npos ||
            p.find("\\covers") != std::string::npos ||
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
