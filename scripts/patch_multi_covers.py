"""
Script to patch C++ Downloader sources for Multi-Video Cover Support.
Implements:
1. Config helper: getCoverVariantFileName(titleId, index)
2. Installer:
   - findInstalledCoverVariants: detects TITLEID.mp4, TITLEID_1.mp4, TITLEID_2.mp4...
   - getNextAvailableCoverPath: finds next free slot (e.g. TITLEID_1.mp4)
   - installVariant: preserves all existing covers (moves active to TITLEID_N.mp4, new becomes TITLEID.mp4)
   - switchActiveCover: swaps active with target numbered variant
   - deleteCoverVariant: deletes a single numbered variant or active
   - deleteAllCoverVariants: deletes all variants of a title
3. Platform layer (switch_platform.cpp & desktop_platform.cpp):
   - populates installedCoverVariants and installedCoversCount
4. UI (app.cpp):
   - displays count of installed covers
   - adds [X] Switch Video Cover button & action
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADER = os.path.join(ROOT, "downloader")

# 1. Update config.hpp
config_path = os.path.join(DOWNLOADER, "include", "core", "config.hpp")
with open(config_path, "r", encoding="utf-8") as f:
    config_code = f.read()

if "getCoverVariantFileName" not in config_code:
    pattern = r"(static std::string getTargetCoverFileName\([^\)]+\)\s*\{[^}]+\})"
    match = re.search(pattern, config_code)
    if match:
        insertion = """\n\n    // Computes numbered cover variant filename strictly from Title ID and index (1, 2, 3...)
    static std::string getCoverVariantFileName(const std::string& titleId, int index) {
        if (index <= 0) return getTargetCoverFileName(titleId);
        return normalizeTitleId(titleId) + "_" + std::to_string(index) + ".mp4";
    }"""
        config_code = config_code[:match.end()] + insertion + config_code[match.end():]
        with open(config_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(config_code)
        print("[+] config.hpp patched successfully")
    else:
        print("[-] Target pattern not found in config.hpp")
else:
    print("[*] config.hpp already contains getCoverVariantFileName")

# 2. Update installer.hpp
installer_hpp_path = os.path.join(DOWNLOADER, "include", "core", "installer.hpp")
with open(installer_hpp_path, "r", encoding="utf-8") as f:
    installer_hpp = f.read()

if "findInstalledCoverVariants" not in installer_hpp:
    pattern = r"(\s*static bool findExistingCover\([^\)]+\);\n)"
    match = re.search(pattern, installer_hpp)
    if match:
        new_methods_decl = """    // Multi-cover variant detection (TITLEID.mp4, TITLEID_1.mp4, TITLEID_2.mp4...)
    static std::vector<InstalledCoverVariant> findInstalledCoverVariants(
        const std::string& coversDir,
        const std::string& titleId
    );

    static std::string getNextAvailableCoverPath(
        const std::string& coversDir,
        const std::string& titleId,
        int* outIndex = nullptr
    );

    // Switch active cover (atomic swap between TITLEID.mp4 and TITLEID_<targetIndex>.mp4)
    static bool switchActiveCover(
        const std::string& coversDir,
        const std::string& titleId,
        int targetIndex
    );

    // Delete single variant (or active)
    static bool deleteCoverVariant(
        const std::string& coversDir,
        const std::string& titleId,
        int index
    );

    // Delete all variants for a game
    static bool deleteAllCoverVariants(
        const std::string& coversDir,
        const std::string& titleId
    );
\n"""
        installer_hpp = installer_hpp[:match.start()] + new_methods_decl + installer_hpp[match.start():]
        with open(installer_hpp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(installer_hpp)
        print("[+] installer.hpp patched successfully")
    else:
        print("[-] Target pattern not found in installer.hpp")
else:
    print("[*] installer.hpp already contains multi-cover declarations")

print("[*] Headers patched.")

# 3. Update installer.cpp
installer_cpp_path = os.path.join(DOWNLOADER, "src", "core", "installer.cpp")
with open(installer_cpp_path, "r", encoding="utf-8") as f:
    installer_cpp = f.read()

new_methods_impl = """
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
"""

if "Installer::findInstalledCoverVariants" not in installer_cpp:
    # Insert new methods before Installer::findExistingCover
    anchor = "bool Installer::findExistingCover("
    idx = installer_cpp.find(anchor)
    if idx != -1:
        installer_cpp = installer_cpp[:idx] + new_methods_impl + "\n" + installer_cpp[idx:]
        print("[+] installer.cpp multi-cover methods added")
    else:
        print("[-] Anchor findExistingCover not found in installer.cpp")

# Update installVariant implementation to keep existing covers
old_install_logic = """    if (hadExistingCover) {
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
    return result;"""

new_install_logic = """    if (hadExistingCover) {
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
    return result;"""

if "Multi-cover support: NEVER delete old video covers!" not in installer_cpp:
    if old_install_logic in installer_cpp:
        installer_cpp = installer_cpp.replace(old_install_logic, new_install_logic)
        print("[+] installer.cpp installVariant updated to preserve old covers")
    else:
        # Normalize CRLF and try replacement
        inst_cr = installer_cpp.replace("\r\n", "\n")
        old_cr = old_install_logic.replace("\r\n", "\n")
        if old_cr in inst_cr:
            inst_cr = inst_cr.replace(old_cr, new_install_logic.replace("\r\n", "\n"))
            installer_cpp = inst_cr
            print("[+] installer.cpp installVariant updated (normalized CRLF)")
        else:
            print("[-] old_install_logic block not matched in installer.cpp")

with open(installer_cpp_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(installer_cpp)
print("[+] installer.cpp written")

# 4. Update switch_platform.cpp & desktop_platform.cpp
switch_plat_path = os.path.join(DOWNLOADER, "src", "platform", "switch_platform.cpp")
with open(switch_plat_path, "r", encoding="utf-8") as f:
    sp = f.read()

old_sp_block = """                // Check local cover on SD card
                std::string coverPath;
                uint64_t coverSize = 0;
                if (Installer::findExistingCover(coversDir, titleIdStr, coverPath, coverSize)) {
                    title.hasInstalledCover = true;
                    title.installedCoverPath = coverPath;
                    title.installedCoverSizeBytes = coverSize;
                    title.status = CoverStatus::Installed;
                } else {
                    title.status = CoverStatus::NoCover;
                }"""

new_sp_block = """                // Multi-cover variant detection
                title.installedCoverVariants = Installer::findInstalledCoverVariants(coversDir, titleIdStr);
                title.installedCoversCount = static_cast<int>(title.installedCoverVariants.size());
                if (!title.installedCoverVariants.empty()) {
                    title.hasInstalledCover = true;
                    bool foundActive = false;
                    for (const auto& var : title.installedCoverVariants) {
                        if (var.isActive) {
                            title.installedCoverPath = var.filePath;
                            title.installedCoverSizeBytes = var.sizeBytes;
                            foundActive = true;
                            break;
                        }
                    }
                    if (!foundActive) {
                        title.installedCoverPath = title.installedCoverVariants[0].filePath;
                        title.installedCoverSizeBytes = title.installedCoverVariants[0].sizeBytes;
                    }
                    title.status = CoverStatus::Installed;
                } else {
                    title.hasInstalledCover = false;
                    title.status = CoverStatus::NoCover;
                }"""

if "title.installedCoverVariants = Installer::findInstalledCoverVariants" not in sp:
    if old_sp_block in sp:
        sp = sp.replace(old_sp_block, new_sp_block)
    else:
        sp_norm = sp.replace("\r\n", "\n")
        old_sp_norm = old_sp_block.replace("\r\n", "\n")
        if old_sp_norm in sp_norm:
            sp = sp_norm.replace(old_sp_norm, new_sp_block.replace("\r\n", "\n"))
    with open(switch_plat_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sp)
    print("[+] switch_platform.cpp updated")

# desktop_platform.cpp
desk_plat_path = os.path.join(DOWNLOADER, "src", "platform", "desktop_platform.cpp")
with open(desk_plat_path, "r", encoding="utf-8") as f:
    dp = f.read()

old_dp_block = """            // Check SD card mock covers
            std::string coverPath;
            uint64_t coverSize = 0;
            if (Installer::findExistingCover(coversDir, t.titleId, coverPath, coverSize)) {
                t.hasInstalledCover = true;
                t.installedCoverPath = coverPath;
                t.installedCoverSizeBytes = coverSize;
                t.status = CoverStatus::Installed;
            } else {
                t.status = CoverStatus::NoCover;
            }"""

new_dp_block = """            // Multi-cover variant detection
            t.installedCoverVariants = Installer::findInstalledCoverVariants(coversDir, t.titleId);
            t.installedCoversCount = static_cast<int>(t.installedCoverVariants.size());
            if (!t.installedCoverVariants.empty()) {
                t.hasInstalledCover = true;
                bool foundActive = false;
                for (const auto& var : t.installedCoverVariants) {
                    if (var.isActive) {
                        t.installedCoverPath = var.filePath;
                        t.installedCoverSizeBytes = var.sizeBytes;
                        foundActive = true;
                        break;
                    }
                }
                if (!foundActive) {
                    t.installedCoverPath = t.installedCoverVariants[0].filePath;
                    t.installedCoverSizeBytes = t.installedCoverVariants[0].sizeBytes;
                }
                t.status = CoverStatus::Installed;
            } else {
                t.hasInstalledCover = false;
                t.status = CoverStatus::NoCover;
            }"""

if "t.installedCoverVariants = Installer::findInstalledCoverVariants" not in dp:
    if old_dp_block in dp:
        dp = dp.replace(old_dp_block, new_dp_block)
    else:
        dp_norm = dp.replace("\r\n", "\n")
        old_dp_norm = old_dp_block.replace("\r\n", "\n")
        if old_dp_norm in dp_norm:
            dp = dp_norm.replace(old_dp_norm, new_dp_block.replace("\r\n", "\n"))
    with open(desk_plat_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dp)
    print("[+] desktop_platform.cpp updated")

# 5. Update app.hpp
app_hpp_path = os.path.join(DOWNLOADER, "include", "ui", "app.hpp")
with open(app_hpp_path, "r", encoding="utf-8") as f:
    app_hpp = f.read()

if "executeCycleNextCover" not in app_hpp:
    pattern = r"(\s*void executeDeleteCover\(const std::string& titleId\);)"
    replacement = r"\1\n    void executeCycleNextCover(const std::string& titleId);\n    void executeDeleteCoverVariant(const std::string& titleId, int index);\n    void executeDeleteAllCovers(const std::string& titleId);"
    app_hpp = re.sub(pattern, replacement, app_hpp)
    with open(app_hpp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(app_hpp)
    print("[+] app.hpp updated")

# 6. Update app.cpp
app_cpp_path = os.path.join(DOWNLOADER, "src", "ui", "app.cpp")
with open(app_cpp_path, "r", encoding="utf-8") as f:
    app_cpp = f.read()

# Add executeCycleNextCover implementation after executeDeleteCover
cycle_methods = """
void App::executeCycleNextCover(const std::string& titleId) {
    auto variants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), titleId);
    if (variants.size() <= 1) return;

    int targetIndex = 1;
    for (const auto& v : variants) {
        if (!v.isActive && v.index > 0) {
            targetIndex = v.index;
            break;
        }
    }

    bool switched = Installer::switchActiveCover(m_platform->getCoversDirectory(), titleId, targetIndex);
    if (switched) {
        m_statusNotification = (m_language == Language::Russian)
            ? ("Активным назначен видеофон #" + std::to_string(targetIndex))
            : ("Active video cover switched to #" + std::to_string(targetIndex));
    } else {
        m_statusNotification = "Не удалось сменить видеофон";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
}

void App::executeDeleteCoverVariant(const std::string& titleId, int index) {
    bool deleted = Installer::deleteCoverVariant(m_platform->getCoversDirectory(), titleId, index);
    if (deleted) {
        m_statusNotification = (m_language == Language::Russian)
            ? ("Вариант видеофона #" + std::to_string(index) + " удалён")
            : ("Cover variant #" + std::to_string(index) + " deleted");
    } else {
        m_statusNotification = "Файл видеофона не найден";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
}

void App::executeDeleteAllCovers(const std::string& titleId) {
    bool deleted = Installer::deleteAllCoverVariants(m_platform->getCoversDirectory(), titleId);
    if (deleted) {
        InstalledRegistry::instance().remove(m_platform->getAppDirectory(), titleId);
        m_statusNotification = (m_language == Language::Russian)
            ? "Все видеофоны игры удалены с консоли"
            : "All video covers removed for this game";
    } else {
        m_statusNotification = "Видеофоны не найдены";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
    rebuildVideoIconsFilter();
}
"""

if "void App::executeCycleNextCover" not in app_cpp:
    anchor = "void App::executeDeleteCover("
    idx = app_cpp.find(anchor)
    if idx != -1:
        # Find closing brace of executeDeleteCover
        end_idx = app_cpp.find("}", idx)
        if end_idx != -1:
            app_cpp = app_cpp[:end_idx+1] + "\n" + cycle_methods + app_cpp[end_idx+1:]
            print("[+] app.cpp executeCycleNextCover added")

# Update refreshInstalledGames multi-cover rescan
scan_needle = "        if (Installer::findExistingIcon(m_platform->getIconsDirectory(), game.titleId, iconPath, iconSize)) {"
scan_add = """        // Refresh multi-cover variants
        game.installedCoverVariants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), game.titleId);
        game.installedCoversCount = static_cast<int>(game.installedCoverVariants.size());
        if (game.installedCoversCount > 0) {
            game.hasInstalledCover = true;
            for (const auto& var : game.installedCoverVariants) {
                if (var.isActive) {
                    game.installedCoverPath = var.filePath;
                    game.installedCoverSizeBytes = var.sizeBytes;
                    break;
                }
            }
            if (game.installedCoverPath.empty()) {
                game.installedCoverPath = game.installedCoverVariants[0].filePath;
                game.installedCoverSizeBytes = game.installedCoverVariants[0].sizeBytes;
            }
            game.status = CoverStatus::Installed;
        }
"""
if "Refresh multi-cover variants" not in app_cpp:
    if scan_needle in app_cpp:
        app_cpp = app_cpp.replace(scan_needle, scan_add + "\n" + scan_needle)
        print("[+] app.cpp refreshInstalledGames multi-cover rescan added")

# Update MINUS button in MyGames
minus_needle = "                if (g.hasBackup) {"
minus_replacement = """                if (g.installedCoversCount > 1) {
                    executeCycleNextCover(g.titleId);
                    return;
                } else if (g.hasBackup) {"""

if "if (g.installedCoversCount > 1) {" not in app_cpp:
    if minus_needle in app_cpp:
        app_cpp = app_cpp.replace(minus_needle, minus_replacement)
        print("[+] app.cpp MINUS button multi-cover cycling added")

# Update My Games UI render details & buttons
old_cover_info = """        // Status details
        std::string coverInfo;
        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: Видеофон (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB) + Иконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledCover) {
            coverInfo = "Активный видеофон: " + Config::getTargetCoverFileName(selGame.titleId) + " (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: Иконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB, без видеофона)";
        } else {
            coverInfo = "Видеофон и видеоиконка не установлены";
        }"""

new_cover_info = """        // Status details (with multi-cover support)
        std::string coverInfo;
        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
            std::string covSub = (selGame.installedCoversCount > 1)
                ? (std::to_string(selGame.installedCoversCount) + " видеофона (активный + " + std::to_string(selGame.installedCoversCount - 1) + " доп.)")
                : ("Видеофон (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)");
            coverInfo = "Активно: " + covSub + " + Иконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledCover) {
            if (selGame.installedCoversCount > 1) {
                coverInfo = "Активный фон: " + Config::getTargetCoverFileName(selGame.titleId) + "  |  Всего: " + std::to_string(selGame.installedCoversCount) + " видеофона ([-] Сменить фон)";
            } else {
                coverInfo = "Активный видеофон: " + Config::getTargetCoverFileName(selGame.titleId) + " (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)";
            }
        } else if (selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: Иконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB, без видеофона)";
        } else {
            coverInfo = "Видеофон и видеоиконка не установлены";
        }"""

if "with multi-cover support" not in app_cpp:
    app_cpp_norm = app_cpp.replace("\r\n", "\n")
    old_ci_norm = old_cover_info.replace("\r\n", "\n")
    if old_ci_norm in app_cpp_norm:
        app_cpp_norm = app_cpp_norm.replace(old_ci_norm, new_cover_info.replace("\r\n", "\n"))
        app_cpp = app_cpp_norm
        print("[+] app.cpp My Games status text updated for multi-covers")

# Add button [-] Сменить фон when installedCoversCount > 1
old_btn_row = """            if (selGame.hasBackup) {
                drawRect(770, 202, 230, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_ACCENT, 1);
                drawText("[-] Восстановить (.bak)", 785, 210, Theme::COLOR_ACCENT, 13);
            }"""

new_btn_row = """            if (selGame.installedCoversCount > 1) {
                drawRect(770, 202, 230, 32, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_SUCCESS, 1);
                drawText("[-] Сменить фон (" + std::to_string(selGame.installedCoversCount) + ")", 785, 210, Theme::COLOR_SUCCESS, 13);
            } else if (selGame.hasBackup) {
                drawRect(770, 202, 230, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_ACCENT, 1);
                drawText("[-] Восстановить (.bak)", 785, 210, Theme::COLOR_ACCENT, 13);
            }"""

if "[-] Сменить фон" not in app_cpp:
    app_cpp_norm = app_cpp.replace("\r\n", "\n")
    old_btn_norm = old_btn_row.replace("\r\n", "\n")
    if old_btn_norm in app_cpp_norm:
        app_cpp_norm = app_cpp_norm.replace(old_btn_norm, new_btn_row.replace("\r\n", "\n"))
        app_cpp = app_cpp_norm
        print("[+] app.cpp My Games button [-] Сменить фон added")

with open(app_cpp_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(app_cpp)
print("[+] app.cpp written successfully")
