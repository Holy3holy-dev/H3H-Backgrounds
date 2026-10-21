# scripts/patch_v120_step1.py
from pathlib import Path

# 1. Patch types.hpp
types_path = Path("downloader/include/core/types.hpp")
types_content = types_path.read_text(encoding="utf-8")
types_add = """
struct LocalRecording {
    std::string filename;
    std::string fullPath;
    uint64_t sizeBytes{0};
    std::string formattedSize;
    std::string dateModified;
};

struct IntegrityIssue {
    std::string titleId;
    std::string filename;
    std::string fullPath;
    uint64_t sizeBytes{0};
    std::string reason;
};

struct IntegrityReport {
    int totalChecked{0};
    int totalValid{0};
    std::vector<IntegrityIssue> issues;
};

} // namespace h3h
"""
if "struct LocalRecording" not in types_content:
    types_content = types_content.replace("} // namespace h3h", types_add)
    types_path.write_text(types_content, encoding="utf-8")
    print("Patched types.hpp")

# 2. Patch config.hpp
config_path = Path("downloader/include/core/config.hpp")
config_content = config_path.read_text(encoding="utf-8")
config_content = config_content.replace('APP_VERSION = "1.1.0"', 'APP_VERSION = "1.2.0"')
if "DEFAULT_SWITCH_RECORDINGS_DIR" not in config_content:
    config_content = config_content.replace(
        'DEFAULT_SWITCH_COVERS_DIR = "sdmc:/recordings/covers";',
        'DEFAULT_SWITCH_COVERS_DIR = "sdmc:/recordings/covers";\n    static constexpr const char* DEFAULT_SWITCH_RECORDINGS_DIR = "sdmc:/recordings";'
    )
config_path.write_text(config_content, encoding="utf-8")
print("Patched config.hpp")

# 3. Patch platform_interface.hpp
plat_path = Path("downloader/include/platform/platform_interface.hpp")
plat_content = plat_path.read_text(encoding="utf-8")
if "getRecordingsDirectory" not in plat_content:
    plat_content = plat_content.replace(
        "virtual std::string getCoversDirectory() = 0;",
        "virtual std::string getCoversDirectory() = 0;\n    virtual std::string getRecordingsDirectory() = 0;"
    )
    plat_path.write_text(plat_content, encoding="utf-8")
    print("Patched platform_interface.hpp")

# 4. Patch switch_platform.cpp
sw_path = Path("downloader/src/platform/switch_platform.cpp")
sw_content = sw_path.read_text(encoding="utf-8")
if "getRecordingsDirectory" not in sw_content:
    sw_content = sw_content.replace(
        "std::string getCoversDirectory() override {",
        "std::string getRecordingsDirectory() override {\n        return Config::DEFAULT_SWITCH_RECORDINGS_DIR;\n    }\n\n    std::string getCoversDirectory() override {"
    )
    sw_path.write_text(sw_content, encoding="utf-8")
    print("Patched switch_platform.cpp")

# 5. Patch desktop_platform.cpp
desk_path = Path("downloader/src/platform/desktop_platform.cpp")
desk_content = desk_path.read_text(encoding="utf-8")
if "getRecordingsDirectory" not in desk_content:
    desk_content = desk_content.replace(
        "std::string getCoversDirectory() override {",
        'std::string getRecordingsDirectory() override {\n        return (fs::current_path() / "recordings").string();\n    }\n\n    std::string getCoversDirectory() override {'
    )
    desk_path.write_text(desk_content, encoding="utf-8")
    print("Patched desktop_platform.cpp")
