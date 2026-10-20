#include "ui/app.hpp"
#include "platform/platform_interface.hpp"
#include <iostream>

int main(int argc, char* argv[]) {
    std::cout << "========================================" << std::endl;
    std::cout << "  H3H Backgrounds — 4IFIR Downloader    " << std::endl;
    std::cout << "========================================" << std::endl;

    try {
        auto platform = h3h::createPlatform();
        if (!platform) {
            std::cerr << "[-] Error: Failed to create platform instance." << std::endl;
            return 1;
        }

        h3h::ui::App app(std::move(platform));
        if (argc > 0 && argv[0] != nullptr) {
            app.setRunningNroPath(argv[0]);
        }

        if (!app.init()) {
            std::cerr << "[-] Error: Application initialization failed." << std::endl;
            return 1;
        }

        std::cout << "[*] Starting main application loop..." << std::endl;
        app.run();
    } catch (const std::exception& ex) {
        std::cerr << "[-] Fatal exception: " << ex.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "[-] Unknown fatal exception occurred." << std::endl;
        return 1;
    }

    std::cout << "[*] Exiting cleanly." << std::endl;
    return 0;
}
