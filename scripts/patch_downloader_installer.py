from pathlib import Path

# 1. installer.hpp
p_h = Path("downloader/include/core/installer.hpp")
c_h = p_h.read_text(encoding="utf-8")
if "findExistingIcon" not in c_h:
    decl = '''    // 4IFIR Video Icon Support
    static bool findExistingIcon(
        const std::string& iconsDir,
        const std::string& titleId,
        std::string& outIconPath,
        uint64_t& outSizeBytes
    );

    static InstallResult installIcon(
        const std::string& iconsDir,
        const std::string& titleId,
        const std::string& tempFilePath,
        uint64_t expectedSizeBytes = 0,
        bool createBackup = true
    );

    static bool deleteIcon(
        const std::string& iconsDir,
        const std::string& titleId
    );
'''
    c_h = c_h.replace("    // Feature 5: Video file validation", decl + "\n    // Feature 5: Video file validation")
    p_h.write_text(c_h, encoding="utf-8")
    print("[+] Updated downloader/include/core/installer.hpp")

# 2. installer.cpp
p_cpp = Path("downloader/src/core/installer.cpp")
c_cpp = p_cpp.read_text(encoding="utf-8")
if "findExistingIcon" not in c_cpp:
    impl = '''bool Installer::findExistingIcon(
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
'''
    c_cpp = c_cpp.replace("InstallResult Installer::installVariant(", impl + "\nInstallResult Installer::installVariant(")
    p_cpp.write_text(c_cpp, encoding="utf-8")
    print("[+] Updated downloader/src/core/installer.cpp")
