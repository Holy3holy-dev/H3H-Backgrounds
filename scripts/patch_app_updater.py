with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    m_nroUpdateThread = std::thread([this]() {
        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        std::string targetNro = appDir + "/H3H-Backgrounds.nro";

        std::atomic<bool> cancel{false};
        std::string err;
        bool ok = m_platform->downloadFile(nroUrl, tempNro, nullptr, cancel, err);
        bool success = false;
        if (ok) {
            std::remove(targetNro.c_str());
            if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                success = true;
                // Automatically delete duplicate old NRO from root /switch/ folder
                std::remove("sdmc:/switch/H3H-Backgrounds.nro");
                std::remove("sdmc:/switch/H3H-Backgrounds.nro.tmp");
            } else {
                err = "Failed to replace H3H-Backgrounds.nro file";
            }
        }'''

replacement = '''    m_nroUpdateThread = std::thread([this]() {
        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        
        std::vector<std::string> targetNros = {
            appDir + "/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds.nro"
        };

        std::atomic<bool> cancel{false};
        std::string err;
        bool ok = m_platform->downloadFile(nroUrl, tempNro, nullptr, cancel, err);
        bool success = false;
        if (ok) {
            // Release romfs handle so Horizon OS FAT32 unlocks the executing .nro file
            m_platform->releaseRomfs();

            for (const auto& targetNro : targetNros) {
                std::error_code ec;
                std::filesystem::create_directories(std::filesystem::path(targetNro).parent_path(), ec);

                // 1. Try rename
                std::remove(targetNro.c_str());
                if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                    success = true;
                    break;
                }

                // 2. Binary stream copy fallback
                std::ifstream src(tempNro, std::ios::binary);
                if (src.is_open()) {
                    std::ofstream dst(targetNro, std::ios::binary | std::ios::trunc);
                    if (dst.is_open()) {
                        dst << src.rdbuf();
                        dst.flush();
                        success = true;
                        break;
                    }
                }
            }

            std::remove(tempNro.c_str());
            m_platform->restoreRomfs();

            if (!success) {
                err = "Failed to replace H3H-Backgrounds.nro file";
            }
        }'''

content_norm = content.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
replacement_norm = replacement.replace('\r\n', '\n')

if target_norm in content_norm:
    new_content = content_norm.replace(target_norm, replacement_norm)
    with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('SUCCESS: app.cpp updater updated!')
else:
    print('Target not matched in app.cpp.')
