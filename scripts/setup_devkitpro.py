"""
Automated devkitPro & devkitA64 Toolchain Downloader for Nintendo Switch.
Downloads pre-built official devkitPro packages and installs them into C:/devkitPro without admin/UAC.
"""

import io
import lzma
import os
import shutil
import sys
import tarfile
import urllib.request
import zstandard

TARGET_DIR = r"C:\devkitPro"

PACKAGES = [
    # Binutils & GCC
    "https://pkg.devkitpro.org/packages/windows/x86_64/devkita64-binutils-2.46.0-1-x86_64.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/windows/x86_64/devkita64-gcc-16.1.0-1-x86_64.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/devkita64-newlib-4.6.0.20260123-4-any.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/devkita64-rules-1.1.1-1-any.pkg.tar.zst",
    # Switch & General Tools
    "https://pkg.devkitpro.org/packages/windows/x86_64/switch-tools-1.13.1-1-x86_64.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/windows/x86_64/general-tools-1.4.4-1-x86_64.pkg.tar.zst",
    # libnx
    "https://pkg.devkitpro.org/packages/libnx-4.12.0-1-any.pkg.tar.zst",
    # Switch Portlibs
    "https://pkg.devkitpro.org/packages/switch-zlib-1.3.1-1-any.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/switch-bzip2-1.0.8-1-any.pkg.tar.xz",
    "https://pkg.devkitpro.org/packages/switch-libpng-1.6.48-1-any.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/switch-libjpeg-turbo-2.1.2-2-any.pkg.tar.xz",
    "https://pkg.devkitpro.org/packages/switch-freetype-2.13.3-1-any.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/switch-sdl2-2.28.5-4-any.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/switch-sdl2_ttf-2.22.0-2-any.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/switch-sdl2_image-2.0.4-1-any.pkg.tar.xz",
    "https://pkg.devkitpro.org/packages/switch-mbedtls-2.28.10-1-any.pkg.tar.zst",
    "https://pkg.devkitpro.org/packages/switch-curl-7.69.1-5-any.pkg.tar.zst",
]

def decompress_archive(raw_bytes: bytes, filename: str) -> bytes:
    if filename.endswith(".zst"):
        dctx = zstandard.ZstdDecompressor()
        return dctx.stream_reader(io.BytesIO(raw_bytes)).read()
    elif filename.endswith(".xz"):
        return lzma.decompress(raw_bytes)
    else:
        return raw_bytes

def install_package(url: str, target_root: str):
    filename = url.split("/")[-1]
    marker = os.path.join(target_root, f".installed_{filename}")
    if os.path.exists(marker):
        print(f"[*] Package {filename} already installed. Skipping.")
        return

    print(f"[*] Downloading {filename}...")
    req = urllib.request.Request(url, headers={"User-Agent": "pacman/6.0"})
    with urllib.request.urlopen(req) as resp:
        raw_bytes = resp.read()
    
    print(f"    Decompressing {filename} ({len(raw_bytes) / 1024 / 1024:.2f} MB)...")
    tar_bytes = decompress_archive(raw_bytes, filename)
    
    tf = tarfile.open(fileobj=io.BytesIO(tar_bytes))
    print(f"    Extracting to {target_root}...")
    
    for member in tf.getmembers():
        # DevkitPro packages have paths like opt/devkitpro/...
        name = member.name
        if name.startswith("opt/devkitpro/"):
            rel_path = name[len("opt/devkitpro/"):]
        elif name.startswith("opt/"):
            rel_path = name[len("opt/"):]
        elif name.startswith("."):
            continue
        else:
            rel_path = name
        
        if not rel_path:
            continue
            
        dest_path = os.path.join(target_root, rel_path.replace("/", os.sep))
        
        if member.isdir():
            os.makedirs(dest_path, exist_ok=True)
        elif member.isreg():
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f_out:
                f_in = tf.extractfile(member)
                if f_in:
                    shutil.copyfileobj(f_in, f_out)
        elif member.issym() or member.islnk():
            # Create a copy or pointer if symlink is not permitted on Windows
            target_link = member.linkname
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            # If target exists relative to dest_path
            src_target = os.path.normpath(os.path.join(os.path.dirname(dest_path), target_link.replace("/", os.sep)))
            if os.path.exists(src_target) and os.path.isfile(src_target):
                try:
                    shutil.copy2(src_target, dest_path)
                except Exception:
                    pass
    with open(marker, "w") as f:
        f.write("ok")

def main():
    os.makedirs(TARGET_DIR, exist_ok=True)
    print(f"=== Installing devkitA64 and Switch SDK to {TARGET_DIR} ===")
    for i, url in enumerate(PACKAGES, 1):
        print(f"[{i}/{len(PACKAGES)}] Processing {url.split('/')[-1]}")
        install_package(url, TARGET_DIR)
    print("=== Toolchain setup completed successfully! ===")

if __name__ == "__main__":
    main()
