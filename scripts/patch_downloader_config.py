from pathlib import Path

p = Path("downloader/include/core/config.hpp")
code = p.read_text(encoding="utf-8")

if "DEFAULT_SWITCH_ICONS_DIR" not in code:
    code = code.replace(
        'static constexpr const char* DEFAULT_SWITCH_RECORDINGS_DIR = "sdmc:/recordings";',
        'static constexpr const char* DEFAULT_SWITCH_RECORDINGS_DIR = "sdmc:/recordings";\n    static constexpr const char* DEFAULT_SWITCH_ICONS_DIR = "sdmc:/recordings/icons";'
    )

if "getTargetIconFileName" not in code:
    icon_helpers = '''    // Computes target 4IFIR icon filename strictly from Title ID
    static std::string getTargetIconFileName(const std::string& titleId) {
        return normalizeTitleId(titleId) + ".mp4";
    }

    // Computes backup icon filename strictly from Title ID
    static std::string getBackupIconFileName(const std::string& titleId) {
        return normalizeTitleId(titleId) + ".bak";
    }

    // Computes temporary download icon filename
    static std::string getTempIconFileName(const std::string& titleId) {
        return normalizeTitleId(titleId) + "_icon.tmp";
    }
'''
    code = code.replace("};", icon_helpers + "\n};")

p.write_text(code, encoding="utf-8")
print("[+] Updated downloader/include/core/config.hpp")
