from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8")

# 1. Add startup cleanup in App::init()
init_target = "refreshInstalledGames();"
init_replacement = """// Clean up duplicate legacy NRO at sdmc:/switch/H3H-Backgrounds.nro if we are running in subfolder
    FILE* checkOld = fopen("sdmc:/switch/H3H-Backgrounds.nro", "rb");
    FILE* checkNew = fopen("sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro", "rb");
    if (checkOld && checkNew) {
        fclose(checkOld);
        fclose(checkNew);
        std::remove("sdmc:/switch/H3H-Backgrounds.nro");
        std::cout << "[+] Cleaned up duplicate legacy sdmc:/switch/H3H-Backgrounds.nro" << std::endl;
    } else {
        if (checkOld) fclose(checkOld);
        if (checkNew) fclose(checkNew);
    }

    refreshInstalledGames();"""

# 2. Add cleanup after successful update in updateApplicationNro()
nro_target = """            if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                success = true;
            }"""
nro_replacement = """            if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                success = true;
                // Automatically delete duplicate old NRO from root /switch/ folder
                std::remove("sdmc:/switch/H3H-Backgrounds.nro");
                std::remove("sdmc:/switch/H3H-Backgrounds.nro.tmp");
            }"""

if init_target in text and nro_target in text:
    text = text.replace(init_target, init_replacement, 1)
    text = text.replace(nro_target, nro_replacement, 1)
    app_cpp.write_text(text, encoding="utf-8")
    print("SUCCESS: updated app.cpp with duplicate NRO auto-cleanup!")
else:
    print("Failed to find targets:", init_target in text, nro_target in text)
