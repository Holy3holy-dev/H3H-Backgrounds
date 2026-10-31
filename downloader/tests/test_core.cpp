#include "core/types.hpp"
#include "core/config.hpp"
#include "core/sha256.hpp"
#include "core/installer.hpp"
#include "core/catalog_manager.hpp"
#include "platform/platform_interface.hpp"

#include <iostream>
#include <cassert>
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;
using namespace h3h;

static std::string makeMockMp4Payload(const std::string& tag, size_t totalBytes = 8192) {
    std::string data = std::string("\x00\x00\x00\x20", 4) + "ftypisom" + std::string("\x00\x00\x02\x00", 4) + "isomiso2mp41";
    data += tag;
    if (data.size() < totalBytes) {
        data.append(totalBytes - data.size(), 'A');
    }
    return data;
}

void testSha256Vectors() {
    std::cout << "[TEST] Running SHA-256 Known Vectors..." << std::endl;
    // Known vector 1: empty string
    std::string h1 = SHA256::hashBuffer("", 0);
    assert(h1 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");

    // Known vector 2: "abc"
    std::string h2 = SHA256::hashBuffer("abc", 3);
    assert(h2 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");

    std::cout << "  -> SHA-256 vectors PASS" << std::endl;
}

void testTitleIdValidation() {
    std::cout << "[TEST] Running Title ID validation & normalization..." << std::endl;
    assert(Config::isValidTitleId("01005CA01580E000") == true);
    assert(Config::isValidTitleId("01005ca01580e000") == true); // case-insensitive
    assert(Config::isValidTitleId("0100000000010000") == true);
    
    // Invalid checks
    assert(Config::isValidTitleId("01005CA01580E00") == false);   // 15 chars (short)
    assert(Config::isValidTitleId("01005CA01580E0000") == false);  // 17 chars (long)
    assert(Config::isValidTitleId("01005CA01580E00G") == false);  // G is not hex
    assert(Config::isValidTitleId("01005CA01580E00Z") == false);  // Z is not hex
    assert(Config::isValidTitleId("0000000000000000") == true);   // 16 hex chars (After Dark special)
    assert(Config::isValidTitleId("../../../01005CA") == false);   // Path traversal injection

    // Normalization check
    assert(Config::normalizeTitleId("01005ca01580e000") == "01005CA01580E000");
    assert(Config::getTargetCoverFileName("01005ca01580e000") == "01005CA01580E000.mp4");
    assert(Config::getBackupCoverFileName("01005ca01580e000") == "01005CA01580E000.bak");

    std::cout << "  -> Title ID validation PASS" << std::endl;
}

void testCatalogManager() {
    std::cout << "[TEST] Running CatalogManager tests..." << std::endl;
    CatalogManager mgr;
    std::string err;
    std::string fixturePath = "catalog/fixtures/test_catalog.json";
    if (!fs::exists(fixturePath)) {
        if (fs::exists("../catalog/fixtures/test_catalog.json")) {
            fixturePath = "../catalog/fixtures/test_catalog.json";
        } else if (fs::exists("../../catalog/fixtures/test_catalog.json")) {
            fixturePath = "../../catalog/fixtures/test_catalog.json";
        } else if (fs::exists("E:/videofon/catalog/fixtures/test_catalog.json")) {
            fixturePath = "E:/videofon/catalog/fixtures/test_catalog.json";
        }
    }
    bool loaded = mgr.loadFromFile(fixturePath, err);
    if (!loaded) {
        std::cerr << "Failed to load fixture: " << err << std::endl;
    }
    assert(loaded);
    assert(mgr.getGamesCount() == 2);
    assert(mgr.getTotalVariantsCount() == 3);

    // Find by Title ID case-insensitively
    const auto* g1 = mgr.findByTitleId("01005ca01580e000");
    assert(g1 != nullptr);
    assert(g1->titleId == "01005CA01580E000");
    assert(g1->variants.size() == 2);

    // Search by title substring
    auto results = mgr.searchByTitle("mario");
    assert(results.size() == 1);
    assert(results[0].titleId == "0100000000010000");

    // Match installed titles
    std::vector<InstalledTitle> mockInstalled;
    InstalledTitle it1;
    it1.titleId = "01005CA01580E000";
    InstalledTitle it2;
    it2.titleId = "0100FFFFFFFF0000"; // Not in catalog

    mockInstalled.push_back(it1);
    mockInstalled.push_back(it2);

    mgr.matchInstalledTitles(mockInstalled);
    assert(mockInstalled[0].hasCatalogMatch == true);
    assert(mockInstalled[0].catalogEntry.variants.size() == 2);
    assert(mockInstalled[1].hasCatalogMatch == false);

    std::cout << "  -> CatalogManager PASS" << std::endl;
}

void testInstallerPipeline() {
    std::cout << "[TEST] Running Installer atomic pipeline & rollback tests..." << std::endl;
    std::string testDir = "./test_run_covers";
    std::error_code ec;
    fs::remove_all(testDir, ec);
    fs::create_directories(testDir, ec);

    std::string titleId = "01005CA01580E000";

    // 1. Create a mock downloaded temp file
    std::string tempFile = testDir + "/download.tmp";
    std::string mockVideoContent = makeMockMp4Payload("TEST_H3H_MP4_VIDEO_STREAM_DATA_SAMPLE", 8192);
    {
        std::ofstream out(tempFile, std::ios::binary);
        out << mockVideoContent;
    }
    std::string expectedHash = SHA256::hashBuffer(mockVideoContent.data(), mockVideoContent.size());
    uint64_t expectedSize = mockVideoContent.size();

    // 2. Test SHA-256 failure handling (bad hash)
    InstallResult badResult = Installer::installVariant(
        testDir,
        titleId,
        tempFile,
        "0000000000000000000000000000000000000000000000000000000000000000",
        expectedSize,
        true
    );
    assert(badResult.success == false);
    assert(!fs::exists(tempFile)); // Should delete temp file on integrity failure

    // Recreate temp file for valid install
    {
        std::ofstream out(tempFile, std::ios::binary);
        out << mockVideoContent;
    }

    // 3. Test clean first-time install
    InstallResult res1 = Installer::installVariant(testDir, titleId, tempFile, expectedHash, expectedSize, true);
    assert(res1.success == true);
    std::string expectedMp4 = testDir + "/" + titleId + ".mp4";
    assert(fs::exists(expectedMp4));
    assert(!fs::exists(testDir + "/" + titleId + ".bak"));

    // Verify existing cover detection
    std::string foundPath;
    uint64_t foundSize = 0;
    assert(Installer::findExistingCover(testDir, "01005ca01580e000", foundPath, foundSize) == true);
    assert(foundSize == expectedSize);

    // 4. Test replacement with automatic backup creation
    std::string updatedContent = makeMockMp4Payload("UPDATED_H3H_MP4_NEW_STREAM_DATA", 8192);
    std::string tempFile2 = testDir + "/download2.tmp";
    {
        std::ofstream out(tempFile2, std::ios::binary);
        out << updatedContent;
    }
    std::string hash2 = SHA256::hashBuffer(updatedContent.data(), updatedContent.size());
    uint64_t size2 = updatedContent.size();

    InstallResult res2 = Installer::installVariant(testDir, titleId, tempFile2, hash2, size2, true);
    assert(res2.success == true);
    assert(fs::exists(expectedMp4));
    assert(fs::exists(testDir + "/" + titleId + ".bak")); // Backup must exist!

    // Verify backup size equals the original file size
    uint64_t backupSize = 0;
    std::string backupPath;
    assert(Installer::findExistingBackup(testDir, titleId, backupPath, backupSize) == true);
    assert(backupSize == expectedSize);

    // 5. Test Restore Backup
    InstallResult resRestore = Installer::restoreBackup(testDir, titleId);
    assert(resRestore.success == true);
    assert(!fs::exists(testDir + "/" + titleId + ".bak")); // Consumed backup
    assert(fs::exists(expectedMp4));

    // Verify file content matches original
    std::string restoredContent;
    {
        std::ifstream in(expectedMp4, std::ios::binary);
        std::stringstream ss;
        ss << in.rdbuf();
        restoredContent = ss.str();
    }
    assert(restoredContent == mockVideoContent);

    // 6. Test Delete Cover
    bool deleted = Installer::deleteCover(testDir, titleId, true);
    assert(deleted == true);
    assert(!fs::exists(expectedMp4));
    assert(!fs::exists(testDir + "/" + titleId + ".bak"));

    // Cleanup test dir
    fs::remove_all(testDir, ec);

    std::cout << "  -> Installer pipeline PASS" << std::endl;
}

void testVideoIconValidationAndInstall() {
    std::cout << "[TEST] Running Video Icon validation & install tests..." << std::endl;
    std::string testIconsDir = "./test_run_icons";
    std::error_code ec;
    fs::remove_all(testIconsDir, ec);
    fs::create_directories(testIconsDir, ec);

    std::string titleId = "01005CA01580E000";

    // a) Installer::validateVideoFile() accepts a valid 6 KB (6144 bytes) MP4 video icon file with ftyp header
    std::string valid6KbFile = testIconsDir + "/valid_6kb_icon.mp4";
    std::string valid6KbData = makeMockMp4Payload("HEVC_256_ICON", 6144);
    assert(valid6KbData.size() == 6144);
    {
        std::ofstream out(valid6KbFile, std::ios::binary);
        out << valid6KbData;
    }
    std::string valReason;
    bool isValid = Installer::validateVideoFile(valid6KbFile, valReason);
    if (!isValid) {
        std::cerr << "Validation failed unexpectedly: " << valReason << std::endl;
    }
    assert(isValid == true);

    // b) Installer::validateVideoFile() rejects an HTML error page (<!DOCTYPE html><html>404 Not Found</html> padded to 8 KB)
    std::string htmlErrorFile = testIconsDir + "/html_error.mp4";
    std::string htmlData = "<!DOCTYPE html><html><head><title>404 Not Found</title></head><body>404 Not Found</body></html>";
    if (htmlData.size() < 8192) {
        htmlData.append(8192 - htmlData.size(), ' ');
    }
    assert(htmlData.size() >= 8192);
    {
        std::ofstream out(htmlErrorFile, std::ios::binary);
        out << htmlData;
    }
    std::string htmlReason;
    bool isHtmlValid = Installer::validateVideoFile(htmlErrorFile, htmlReason);
    assert(isHtmlValid == false);
    assert(!htmlReason.empty());

    // First install a valid icon into testIconsDir so there is an existing valid icon
    std::string tempValidIcon = testIconsDir + "/temp_valid.tmp";
    {
        std::ofstream out(tempValidIcon, std::ios::binary);
        out << valid6KbData;
    }
    InstallResult initInstall = Installer::installIcon(testIconsDir, titleId, tempValidIcon, valid6KbData.size(), false);
    assert(initInstall.success == true);
    std::string targetInstalledPath = testIconsDir + "/" + Config::getTargetIconFileName(titleId);
    assert(fs::exists(targetInstalledPath));
    uint64_t originalInstalledSize = fs::file_size(targetInstalledPath, ec);
    assert(originalInstalledSize == 6144);

    // c) Installer::installIcon() rejects an HTML error file and deletes the temp file without overwriting an existing valid icon
    std::string tempHtmlIcon = testIconsDir + "/temp_html.tmp";
    {
        std::ofstream out(tempHtmlIcon, std::ios::binary);
        out << htmlData;
    }
    InstallResult badIconInstall = Installer::installIcon(testIconsDir, titleId, tempHtmlIcon, htmlData.size(), true);
    assert(badIconInstall.success == false);
    assert(!fs::exists(tempHtmlIcon)); // Temporary file must be deleted on failure
    assert(fs::exists(targetInstalledPath)); // Existing valid icon must still exist
    assert(fs::file_size(targetInstalledPath, ec) == originalInstalledSize); // Not overwritten!

    // Verify existing icon content is still intact
    {
        std::ifstream in(targetInstalledPath, std::ios::binary);
        std::stringstream ss;
        ss << in.rdbuf();
        assert(ss.str() == valid6KbData);
    }

    // Cleanup
    fs::remove_all(testIconsDir, ec);
    std::cout << "  -> Video Icon validation & install PASS" << std::endl;
}

int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "  H3H Downloader Core Test Suite        " << std::endl;
    std::cout << "========================================" << std::endl;

    testSha256Vectors();
    testTitleIdValidation();
    testCatalogManager();
    testInstallerPipeline();
    testVideoIconValidationAndInstall();

    std::cout << "========================================" << std::endl;
    std::cout << "  ALL 5 TEST MODULES PASSED (100% OK)   " << std::endl;
    std::cout << "========================================" << std::endl;
    return 0;
}
