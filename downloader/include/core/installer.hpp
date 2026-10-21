#pragma once

#include "core/types.hpp"
#include <string>
#include <vector>
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

    // Full atomic installation pipeline with validation and automatic rollback
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

    // Feature 5: Video file validation & Integrity Scanner
    static bool validateVideoFile(const std::string& filePath, std::string& outReason);
    static IntegrityReport validateAllInstalledCovers(const std::string& coversDir);
    static int deleteCorruptedCovers(const std::vector<IntegrityIssue>& issues);

    // Feature 3: Local gameplay recordings from sdmc:/recordings/
    static std::vector<LocalRecording> listLocalRecordings(const std::string& recordingsDir);
    static InstallResult installLocalRecording(
        const std::string& coversDir,
        const std::string& titleId,
        const std::string& sourceRecordingPath,
        bool createBackup = true
    );
};

} // namespace h3h
