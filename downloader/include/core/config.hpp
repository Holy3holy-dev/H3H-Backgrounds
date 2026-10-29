#pragma once



#include <string>

#include <regex>

#include <algorithm>

#include <cstdint>



namespace h3h {



class Config {

public:

    // Default 4IFIR recordings covers directory on SD card

    static constexpr const char* DEFAULT_SWITCH_COVERS_DIR = "sdmc:/recordings/covers";

    static constexpr const char* DEFAULT_SWITCH_RECORDINGS_DIR = "sdmc:/recordings";
    static constexpr const char* DEFAULT_SWITCH_ICONS_DIR = "sdmc:/recordings/icons";

#ifdef H3H_AFTER_DARK

    static constexpr const char* DEFAULT_SWITCH_APP_DIR    = "sdmc:/switch/H3H-AfterDark";

    static constexpr const char* APP_NAME                  = "H3H-AfterDark";

    static constexpr const char* DEFAULT_CATALOG_URL       = "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/after-dark/catalog/data/catalog_after_dark.json";

#else

    static constexpr const char* DEFAULT_SWITCH_APP_DIR    = "sdmc:/switch/H3H-Backgrounds";

    static constexpr const char* APP_NAME                  = "H3H-Backgrounds";

    static constexpr const char* DEFAULT_CATALOG_URL       = "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog.json";

#endif



    static constexpr bool isAfterDark() {

#ifdef H3H_AFTER_DARK

        return true;

#else

        return false;

#endif

    }

    

    // Application Version

    static constexpr const char* APP_VERSION = "1.4.2";

    static constexpr const char* VERSION_CHECK_URL =

        "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/version.json";



    // Safety buffer for free disk space checks (20 MB minimum reserve)

    static constexpr uint64_t STORAGE_SAFETY_BUFFER_BYTES = 20 * 1024 * 1024;



    // Strict validation for Nintendo Switch Title ID (16 hex chars)

    static bool isValidTitleId(const std::string& titleId) {

        if (titleId.length() != 16) return false;

        for (char c : titleId) {

            if (!std::isxdigit(static_cast<unsigned char>(c))) {

                return false;

            }

        }

        return true;

    }



    // Normalizes Title ID to uppercase 16-hex characters

    static std::string normalizeTitleId(const std::string& titleId) {

        std::string upper = titleId;

        std::transform(upper.begin(), upper.end(), upper.begin(), [](unsigned char c) {

            return std::toupper(c);

        });

        return upper;

    }



    // Computes target MP4 filename strictly from Title ID (prevents path traversal)

    static std::string getTargetCoverFileName(const std::string& titleId) {

        return normalizeTitleId(titleId) + ".mp4";

    }



    // Computes backup filename strictly from Title ID

    static std::string getBackupCoverFileName(const std::string& titleId) {

        return normalizeTitleId(titleId) + ".bak";

    }



    // Computes temporary download filename

    static std::string getTempCoverFileName(const std::string& titleId) {

        return normalizeTitleId(titleId) + ".tmp";

    }

    // Computes target 4IFIR icon filename strictly from Title ID
    static std::string getTargetIconFileName(const std::string& titleId) {
        return normalizeTitleId(titleId) + ".mp4";
    }

    // Computes backup icon filename strictly from Title ID
    static std::string getBackupIconFileName(const std::string& titleId) {
        return normalizeTitleId(titleId) + ".bak";
    }

    // Computes temporary download icon filename
    static std::string getTempIconFileName(const std::string& titleId) {
        return normalizeTitleId(titleId) + "_icon.tmp";
    }

};



} // namespace h3h

