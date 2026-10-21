"""
Nintendo Switch .nro native builder for H3H After Dark (18+).
Compiles C++ sources with devkitA64 using -DH3H_AFTER_DARK flag and Cyber-Pink theme,
generating H3H-AfterDark.nro.
"""

import os
import sys
import shutil
import subprocess

DKP = r"C:\devkitPro"
A64_BIN = os.path.join(DKP, "devkitA64", "bin")
TOOLS_BIN = os.path.join(DKP, "tools", "bin")
GXX = os.path.join(A64_BIN, "aarch64-none-elf-g++.exe")
ELF2NRO = os.path.join(TOOLS_BIN, "elf2nro.exe")
NACPTOOL = os.path.join(TOOLS_BIN, "nacptool.exe")

ROOT_DIR = r"E:\videofon"
SRC_DIR = os.path.join(ROOT_DIR, "downloader")
BUILD_DIR = os.path.join(SRC_DIR, "build_switch_after_dark")

SOURCES = [
    "src/main.cpp",
    "src/core/catalog_manager.cpp",
    "src/core/installer.cpp",
    "src/core/sha256.cpp",
    "src/platform/switch_platform.cpp",
    "src/platform/desktop_platform.cpp",
    "src/platform/webp_stub.cpp",
    "src/ui/video_player.cpp",
    "src/ui/app.cpp",
]

INCLUDES = [
    os.path.join(SRC_DIR, "include"),
    os.path.join(SRC_DIR, "include", "core"),
    os.path.join(SRC_DIR, "include", "ui"),
    os.path.join(SRC_DIR, "include", "platform"),
    os.path.join(DKP, "libnx", "include"),
    os.path.join(DKP, "portlibs", "switch", "include"),
    os.path.join(DKP, "portlibs", "switch", "include", "SDL2"),
]

LIBPATHS = [
    os.path.join(DKP, "libnx", "lib"),
    os.path.join(DKP, "portlibs", "switch", "lib"),
]

LIBS = [
    "-lSDL2_ttf",
    "-lSDL2_image",
    "-lSDL2",
    "-lavformat",
    "-lavcodec",
    "-lswscale",
    "-lavutil",
    "-lswresample",
    "-ldav1d",
    "-lEGL",
    "-lglapi",
    "-ldrm_nouveau",
    "-lfreetype",
    "-lharfbuzz",
    "-lpng",
    "-ljpeg",
    "-lbz2",
    "-lz",
    "-lcurl",
    "-lmbedtls",
    "-lmbedcrypto",
    "-lmbedx509",
    "-lnx",
]

CFLAGS = [
    "-march=armv8-a+crc+crypto",
    "-mtune=cortex-a57",
    "-mtp=soft",
    "-fPIE",
    "-O2",
    "-Wall",
    "-std=c++17",
    "-D__SWITCH__",
    "-DHAS_SDL2",
    "-DH3H_AFTER_DARK",
]

LDFLAGS = [
    f"-specs={os.path.join(DKP, 'libnx', 'switch.specs').replace(os.sep, '/')}",
    "-march=armv8-a+crc+crypto",
    "-mtune=cortex-a57",
    "-mtp=soft",
    "-fPIE",
]

def build():
    if not os.path.exists(GXX):
        print(f"ERROR: Compiler not found at {GXX}")
        return 1

    os.makedirs(BUILD_DIR, exist_ok=True)

    env = os.environ.copy()
    tmp_dir = os.path.join(ROOT_DIR, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    env['TMP'] = tmp_dir
    env['TEMP'] = tmp_dir
    env["DEVKITPRO"] = DKP
    env["PATH"] = f"{TOOLS_BIN};{A64_BIN};" + env.get("PATH", "")

    obj_files = []
    for src in SOURCES:
        src_path = os.path.join(SRC_DIR, src)
        obj_name = src.replace("/", "_").replace("\\", "_") + ".o"
        obj_path = os.path.join(BUILD_DIR, obj_name)
        obj_files.append(obj_path)

        print(f"[*] Compiling {src} (After Dark)...")
        cmd = [GXX] + CFLAGS
        for inc in INCLUDES:
            cmd.append(f"-I{inc.replace(os.sep, '/')}")
        cmd += ["-c", src_path.replace(os.sep, "/"), "-o", obj_path.replace(os.sep, "/")]

        res = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode != 0:
            print(f"Compilation error in {src}:")
            print(res.stderr.encode('ascii', errors='replace').decode('ascii'))
            return 1

    elf_path = os.path.join(BUILD_DIR, "H3H-AfterDark.elf")
    print("[*] Linking ELF executable...")
    link_cmd = [GXX] + LDFLAGS + obj_files
    for lp in LIBPATHS:
        link_cmd.append(f"-L{lp.replace(os.sep, '/')}")
    link_cmd += LIBS + ["-o", elf_path.replace(os.sep, "/")]

    res = subprocess.run(link_cmd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if res.returncode != 0:
        print("Linker error:")
        print(res.stderr.encode('ascii', errors='replace').decode('ascii'))
        return 1

    print(f"[*] ELF successfully generated ({os.path.getsize(elf_path)} bytes)")

    # Generate NACP metadata
    nacp_path = os.path.join(BUILD_DIR, "H3H-AfterDark.nacp")
    print("[*] Generating NACP metadata...")
    app_version = "1.2.7"

    nacp_cmd = [
        NACPTOOL,
        "--create",
        "H3H After Dark (18+)",
        "H3H Team",
        app_version,
        nacp_path
    ]
    res = subprocess.run(nacp_cmd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if res.returncode != 0:
        print("nacptool error:")
        print(res.stderr.encode('ascii', errors='replace').decode('ascii'))
        return 1

    # Convert ELF to NRO
    target_nro = os.path.join(SRC_DIR, "H3H-AfterDark.nro")
    print(f"[*] Packaging to {target_nro}...")
    romfs_dir = os.path.join(SRC_DIR, "romfs")
    icon_path = os.path.join(SRC_DIR, "icon_after_dark.jpg")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(SRC_DIR, "icon.jpg")

    nro_cmd = [
        ELF2NRO,
        elf_path,
        target_nro,
        f"--nacp={nacp_path}"
    ]
    if os.path.exists(icon_path):
        nro_cmd.append(f"--icon={icon_path}")
    if os.path.exists(romfs_dir):
        nro_cmd.append(f"--romfsdir={romfs_dir}")

    res = subprocess.run(nro_cmd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if res.returncode != 0:
        print("elf2nro error:")
        print(res.stderr.encode('ascii', errors='replace').decode('ascii'))
        return 1

    # Copy to workspace root and drive H:
    root_nro = os.path.join(ROOT_DIR, "H3H-AfterDark.nro")
    shutil.copy2(target_nro, root_nro)
    h_stage_nro = r"H:\h3h_stage\H3H-AfterDark.nro"
    try:
        shutil.copy2(target_nro, h_stage_nro)
    except Exception:
        pass

    print("==================================================")
    print("SUCCESS! Nintendo Switch H3H After Dark NRO created:")
    print(f"  -> {target_nro} ({os.path.getsize(target_nro)} bytes)")
    print(f"  -> {root_nro} ({os.path.getsize(root_nro)} bytes)")
    if os.path.exists(h_stage_nro):
        print(f"  -> {h_stage_nro} ({os.path.getsize(h_stage_nro)} bytes)")
    print("==================================================")
    return 0

if __name__ == "__main__":
    sys.exit(build())
