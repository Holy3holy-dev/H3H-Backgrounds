from pathlib import Path

# 1. platform_interface.hpp
p_if = Path("downloader/include/platform/platform_interface.hpp")
c_if = p_if.read_text(encoding="utf-8")
if "getIconsDirectory" not in c_if:
    c_if = c_if.replace(
        "virtual std::string getCoversDirectory() = 0;",
        "virtual std::string getCoversDirectory() = 0;\n    virtual std::string getIconsDirectory() = 0;"
    )
    p_if.write_text(c_if, encoding="utf-8")
    print("[+] Updated platform_interface.hpp")

# 2. switch_platform.cpp
p_sw = Path("downloader/src/platform/switch_platform.cpp")
c_sw = p_sw.read_text(encoding="utf-8")
if "getIconsDirectory" not in c_sw:
    c_sw = c_sw.replace(
        "    std::string getCoversDirectory() override {\n        return Config::DEFAULT_SWITCH_COVERS_DIR;\n    }",
        "    std::string getCoversDirectory() override {\n        return Config::DEFAULT_SWITCH_COVERS_DIR;\n    }\n\n    std::string getIconsDirectory() override {\n        return Config::DEFAULT_SWITCH_ICONS_DIR;\n    }"
    )
    p_sw.write_text(c_sw, encoding="utf-8")
    print("[+] Updated switch_platform.cpp")

# 3. desktop_platform.cpp
p_dk = Path("downloader/src/platform/desktop_platform.cpp")
c_dk = p_dk.read_text(encoding="utf-8")
if "getIconsDirectory" not in c_dk:
    c_dk = c_dk.replace(
        "    std::string getCoversDirectory() override {\n        return \"./recordings/covers\";\n    }",
        "    std::string getCoversDirectory() override {\n        return \"./recordings/covers\";\n    }\n\n    std::string getIconsDirectory() override {\n        return \"./recordings/icons\";\n    }"
    )
    c_dk = c_dk.replace(
        "fs::create_directories(getCoversDirectory(), ec);",
        "fs::create_directories(getCoversDirectory(), ec);\n        fs::create_directories(getIconsDirectory(), ec);"
    )
    p_dk.write_text(c_dk, encoding="utf-8")
    print("[+] Updated desktop_platform.cpp")
