import urllib.request
import zstandard
import tarfile
import lzma
import io
from pathlib import Path

DEVKITPRO = Path(r"C:\devkitPro")
PORTLIBS = DEVKITPRO / "portlibs" / "switch"

PACKAGES = [
    "switch-libfribidi-1.0.12-1-any.pkg.tar.xz",
    "switch-libass-0.17.3-1-any.pkg.tar.zst",
    "switch-dav1d-1.5.0-1-any.pkg.tar.zst",
    "switch-ffmpeg-7.1-5-any.pkg.tar.zst",
]

def main():
    print("[*] Downloading and installing FFmpeg portlibs for Nintendo Switch...")
    for pkg in PACKAGES:
        url = f"https://pkg.devkitpro.org/packages/{pkg}"
        print(f"\n[*] Fetching {pkg}...")
        req = urllib.request.Request(url, headers={"User-Agent": "pacman/6.0"})
        data = urllib.request.urlopen(req).read()
        print(f"    Downloaded {len(data)} bytes. Decompressing...")

        if pkg.endswith(".tar.zst"):
            dctx = zstandard.ZstdDecompressor()
            decomp = dctx.decompress(data, max_output_size=120 * 1024 * 1024)
            tar = tarfile.open(fileobj=io.BytesIO(decomp))
        elif pkg.endswith(".tar.xz"):
            decomp = lzma.decompress(data)
            tar = tarfile.open(fileobj=io.BytesIO(decomp))
        else:
            raise ValueError(f"Unknown format: {pkg}")

        extracted_count = 0
        for member in tar.getmembers():
            # Paths look like opt/devkitpro/portlibs/switch/include/... or lib/...
            if "portlibs/switch/" in member.name:
                rel_path = member.name.split("portlibs/switch/")[1]
                if not rel_path:
                    continue
                dest = PORTLIBS / rel_path
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    f_data = tar.extractfile(member).read()
                    dest.write_bytes(f_data)
                    extracted_count += 1

        print(f"    Extracted {extracted_count} files to {PORTLIBS}")

    print("\n[+] All FFmpeg portlibs successfully installed!")
    
    # Verify installation
    av_h = PORTLIBS / "include" / "libavcodec" / "avcodec.h"
    av_a = PORTLIBS / "lib" / "libavcodec.a"
    print(f"avcodec.h exists: {av_h.exists()}")
    print(f"libavcodec.a exists: {av_a.exists()} ({av_a.stat().st_size if av_a.exists() else 0} bytes)")

if __name__ == "__main__":
    main()
