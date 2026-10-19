#pragma once

#include "core/types.hpp"
#include <string>
#include <functional>

namespace h3h {

struct InstallResult {
    bool success{false};
    std::string message;
    bool rollbackOccurred{false};
    std::string installedPath;
    std::string backupPath;
};

class Installer {
public:
    // Finds existing cover on disk (strictly case-insensitive match for FAT32/exFAT compatibility)
    static bool findExistingCover(
        const std::string& coversDir,
        const std::string& titleId,
        std::string& outCoverPath,
        uint64_t& outSizeBytes
    );

    // Finds existing backup on disk (.bak)
    static bool findExistingBackup(
        const std::string& coversDir,
        const std::string& titleId,
        std::string& outBackupPath,
        uint64_t& outSizeBytes
    );

    // Full atomic installation pipeline with SHA-256 validation and automatic rollback
    static InstallResult installVariant(
        const std::string& coversDir,
        const std::string& titleId,
        const std::string& tempFilePath,
        const std::string& expectedSha256,
        uint64_t expectedSizeBytes,
        bool createBackup = true
    );

    // Restores an existing backup (.bak) to active cover (.mp4)
    static InstallResult restoreBackup(
        const std::string& coversDir,
        const std::string& titleId
    );

    // Deletes an installed cover, optionally keeping or deleting backup
    static bool deleteCover(
        const std::string& coversDir,
        const std::string& titleId,
        bool deleteBackup = false
    );
};

} // namespace h3h
