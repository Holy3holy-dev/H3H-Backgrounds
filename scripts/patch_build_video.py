from pathlib import Path

path = Path("scripts/build_nro.py")
content = path.read_text(encoding="utf-8")

old_sources = """SOURCES = [
    "src/main.cpp",
    "src/core/catalog_manager.cpp",
    "src/core/installer.cpp",
    "src/core/sha256.cpp",
    "src/platform/switch_platform.cpp",
    "src/platform/desktop_platform.cpp",
    "src/platform/webp_stub.cpp",
    "src/ui/app.cpp",
]"""

new_sources = """SOURCES = [
    "src/main.cpp",
    "src/core/catalog_manager.cpp",
    "src/core/installer.cpp",
    "src/core/sha256.cpp",
    "src/platform/switch_platform.cpp",
    "src/platform/desktop_platform.cpp",
    "src/platform/webp_stub.cpp",
    "src/ui/video_player.cpp",
    "src/ui/app.cpp",
]"""

old_libs = """LIBS = [
    "-lSDL2_ttf",
    "-lSDL2_image",
    "-lSDL2","""

new_libs = """LIBS = [
    "-lSDL2_ttf",
    "-lSDL2_image",
    "-lSDL2",
    "-lavformat",
    "-lavcodec",
    "-lswscale",
    "-lavutil",
    "-lswresample",
    "-ldav1d","""

assert old_sources in content, "old_sources not found"
assert old_libs in content, "old_libs not found"

content = content.replace(old_sources, new_sources, 1)
content = content.replace(old_libs, new_libs, 1)

path.write_text(content, encoding="utf-8")
print("Patched scripts/build_nro.py successfully!")
