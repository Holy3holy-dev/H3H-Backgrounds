import subprocess
import os

DKP = r"C:\devkitPro"
GXX = os.path.join(DKP, "devkitA64", "bin", "aarch64-none-elf-g++.exe")
PORTLIBS = os.path.join(DKP, "portlibs", "switch")

test_cpp = """
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libswscale/swscale.h>
}
#include <iostream>

int main() {
    std::cout << avformat_configuration() << std::endl;
    return 0;
}
"""

with open("test_av.cpp", "w") as f:
    f.write(test_cpp)

cmd = [
    GXX,
    "-specs=" + os.path.join(DKP, "libnx", "switch.specs").replace("\\", "/"),
    "-march=armv8-a+crc+crypto", "-mtune=cortex-a57", "-mtp=soft", "-fPIE", "-O2",
    "-I" + os.path.join(PORTLIBS, "include").replace("\\", "/"),
    "test_av.cpp",
    "-L" + os.path.join(PORTLIBS, "lib").replace("\\", "/"),
    "-L" + os.path.join(DKP, "libnx", "lib").replace("\\", "/"),
    "-lavformat", "-lavcodec", "-lswscale", "-lavutil", "-lswresample", "-ldav1d", "-lz", "-lbz2", "-lnx",
    "-o", "test_av.elf"
]
res = subprocess.run(cmd, capture_output=True, text=True)
print("Returncode:", res.returncode)
if res.returncode != 0:
    print("Stderr:", res.stderr)
else:
    print("SUCCESS! test_av.elf linked cleanly!")
if os.path.exists("test_av.cpp"): os.remove("test_av.cpp")
if os.path.exists("test_av.elf"): os.remove("test_av.elf")
