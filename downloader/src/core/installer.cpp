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
    if (expectedSizeBytes > 0 && actualSize != expectedSizeBytes) {
        fs::remove(tempFilePath, ec);
        result.success = false;
        result.message = "File size mismatch (expected " + std::to_string(expectedSizeBytes) +
                         " bytes, got " + std::to_string(actualSize) + " bytes)";
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
        if (createBackup) {
            // Remove old stale backup if present
            if (fs::exists(backupPath, ec)) {
                fs::remove(backupPath, ec);
            }

            // Rename existing cover to backup
            fs::rename(existingCoverPath, backupPath, ec);
            if (ec) {
                fs::remove(tempFilePath, ec);
                result.success = false;
                result.message = "Failed to create backup of existing cover: " + ec.message();
                return result;
            }
            backupCreated = true;
            backupCreatedFrom = existingCoverPath;
            result.backupPath = backupPath.string();
        } else {
            fs::remove(existingCoverPath, ec);
        }
    }

    // 7. Atomic Commit Point: rename temp file to target cover
    fs::rename(tempFilePath, targetPath, ec);
    if (ec) {
        // Rollback: restore backup if we created one
        if (backupCreated) {
            std::error_code rb_ec;
            fs::rename(backupPath, backupCreatedFrom, rb_ec);
            result.rollbackOccurred = true;
        }
        fs::remove(tempFilePath, ec);
        result.success = false;
        result.message = "Atomic commit failed: " + ec.message() + (result.rollbackOccurred ? " (Rollback successful)" : "");
        return result;
    }

    result.success = true;
    result.installedPath = targetPath.string();
    result.message = "Successfully installed video cover for " + normTitleId;
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

} // namespace h3h
