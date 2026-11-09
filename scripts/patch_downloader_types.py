from pathlib import Path

p = Path("downloader/include/core/types.hpp")
code = p.read_text(encoding="utf-8")

# 1. Add icon fields to Variant
if "hasIcon" not in code:
    code = code.replace(
        '    std::string notes;\n};',
        '    std::string notes;\n    bool hasIcon{false};\n    std::string iconUrl;\n    uint64_t iconSizeBytes{0};\n    std::string iconCodec{"hevc"};\n    int iconWidth{256};\n    int iconHeight{256};\n};'
    )

# 2. Add installed icon fields to InstalledTitle
if "hasInstalledIcon" not in code:
    code = code.replace(
        '    uint64_t backupSizeBytes{0};',
        '    uint64_t backupSizeBytes{0};\n    bool hasInstalledIcon{false};\n    std::string installedIconPath;\n    uint64_t installedIconSizeBytes{0};'
    )

p.write_text(code, encoding="utf-8")
print("[+] Updated downloader/include/core/types.hpp")
