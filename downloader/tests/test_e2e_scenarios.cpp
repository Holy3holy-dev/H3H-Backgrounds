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
#include <sstream>

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

void runE2ETests() {
    std::cout << "=================================================" << std::endl;
    std::cout << "  H3H Stage 5: Comprehensive E2E Verification    " << std::endl;
    std::cout << "=================================================" << std::endl;

    std::string testCoversDir = "./test_e2e_covers";
    std::error_code ec;
    fs::remove_all(testCoversDir, ec);
    fs::create_directories(testCoversDir, ec);

    std::string titleId = "01005CA01580E000";
    std::string targetMp4 = testCoversDir + "/" + titleId + ".mp4";
    std::string backupFile = testCoversDir + "/" + titleId + ".bak";

    // -------------------------------------------------------------------------
    // Scenario 1: Clean First-Time Installation
    // -------------------------------------------------------------------------
    std::cout << "[SCENARIO 1] Clean First-Time Installation..." << std::endl;
    std::string v1Content = makeMockMp4Payload("H3H_VIDEO_V1_OPENING_INTRO_STREAM_BYTES", 8192);
    std::string tmp1 = testCoversDir + "/v1.tmp";
    {
        std::ofstream f(tmp1, std::ios::binary);
        f << v1Content;
    }
    std::string hash1 = SHA256::hashBuffer(v1Content.data(), v1Content.size());
    uint64_t size1 = v1Content.size();

    InstallResult res1 = Installer::installVariant(testCoversDir, titleId, tmp1, hash1, size1, true);
    assert(res1.success == true);
    assert(fs::exists(targetMp4));
    assert(!fs::exists(backupFile)); // No backup should exist for first install
    assert(!fs::exists(tmp1));       // Temp file must be consumed
    std::cout << "  -> PASS: Video installed atomically without orphan files." << std::endl;

    // -------------------------------------------------------------------------
    // Scenario 2: Corrupted Network / Checksum Mismatch
    // -------------------------------------------------------------------------
    std::cout << "[SCENARIO 2] Corrupted Network / SHA-256 Mismatch..." << std::endl;
    std::string corruptContent = makeMockMp4Payload("CORRUPTED_INCOMPLETE_STREAM", 8192);
    std::string tmpCorrupt = testCoversDir + "/corrupt.tmp";
    {
        std::ofstream f(tmpCorrupt, std::ios::binary);
        f << corruptContent;
    }
    // Deliberately wrong checksum
    InstallResult resCorrupt = Installer::installVariant(
        testCoversDir, titleId, tmpCorrupt, "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        corruptContent.size(), true
    );
    assert(resCorrupt.success == false);
    assert(!fs::exists(tmpCorrupt)); // Temporary corrupted file must be deleted
    // Existing active video must remain completely intact!
    {
        std::ifstream f(targetMp4, std::ios::binary);
        std::stringstream ss;
        ss << f.rdbuf();
        assert(ss.str() == v1Content);
    }
    std::cout << "  -> PASS: Corrupt download rejected, temp deleted, existing video protected." << std::endl;

    // -------------------------------------------------------------------------
    // Scenario 3: Update / Replacement with Automatic Backup
    // -------------------------------------------------------------------------
    std::cout << "[SCENARIO 3] Update / Replacement with Automatic Backup..." << std::endl;
    std::string v2Content = makeMockMp4Payload("H3H_VIDEO_V2_NEW_GAMEPLAY_ACTION_LOOP", 8192);
    std::string tmp2 = testCoversDir + "/v2.tmp";
    {
        std::ofstream f(tmp2, std::ios::binary);
        f << v2Content;
    }
    std::string hash2 = SHA256::hashBuffer(v2Content.data(), v2Content.size());
    uint64_t size2 = v2Content.size();

    InstallResult res2 = Installer::installVariant(testCoversDir, titleId, tmp2, hash2, size2, true);
    assert(res2.success == true);
    assert(fs::exists(targetMp4));
    assert(fs::exists(backupFile)); // Backup MUST exist now!

    // Verify backup contains v1 and target contains v2
    {
        std::ifstream fb(backupFile, std::ios::binary);
        std::stringstream ssb;
        ssb << fb.rdbuf();
        assert(ssb.str() == v1Content);

        std::ifstream ft(targetMp4, std::ios::binary);
        std::stringstream sst;
        sst << ft.rdbuf();
        assert(sst.str() == v2Content);
    }
    std::cout << "  -> PASS: Replacement succeeded, previous file archived to .bak." << std::endl;

    // -------------------------------------------------------------------------
    // Scenario 4: Rollback / Restore Previous Backup
    // -------------------------------------------------------------------------
    std::cout << "[SCENARIO 4] Rollback / Restore Backup (.bak -> .mp4)..." << std::endl;
    InstallResult resRestore = Installer::restoreBackup(testCoversDir, titleId);
    assert(resRestore.success == true);
    assert(!fs::exists(backupFile)); // Backup consumed
    assert(fs::exists(targetMp4));

    // Verify target content is now back to v1!
    {
        std::ifstream ft(targetMp4, std::ios::binary);
        std::stringstream sst;
        sst << ft.rdbuf();
        assert(sst.str() == v1Content);
    }
    std::cout << "  -> PASS: Rollback restored original video file 100% bit-for-bit." << std::endl;

    // -------------------------------------------------------------------------
    // Scenario 5: Case-Insensitive Matching
    // -------------------------------------------------------------------------
    std::cout << "[SCENARIO 5] Case-Insensitive Filesystem Resolution..." << std::endl;
    // Rename existing file to lowercase
    std::string lowerMp4 = testCoversDir + "/01005ca01580e000.mp4";
    fs::rename(targetMp4, lowerMp4, ec);

    std::string foundPath;
    uint64_t foundSize = 0;
    bool found = Installer::findExistingCover(testCoversDir, "01005CA01580E000", foundPath, foundSize);
    assert(found == true);
    assert(foundSize == size1);

    // Also find with mixed case
    found = Installer::findExistingCover(testCoversDir, "01005Ca01580E000", foundPath, foundSize);
    assert(found == true);
    std::cout << "  -> PASS: Case-insensitive Title ID lookup works across lowercase/uppercase." << std::endl;

    // -------------------------------------------------------------------------
    // Scenario 6: Path Traversal Security
    // -------------------------------------------------------------------------
    std::cout << "[SCENARIO 6] Path Traversal and Malicious Title ID Defense..." << std::endl;
    assert(Config::isValidTitleId("../../atmosphere") == false);
    assert(Config::isValidTitleId("01005CA01580E000/../../") == false);
    assert(Config::isValidTitleId("01005CA01580E000/evil") == false);
    assert(Config::isValidTitleId(std::string("01005CA01580E000\0evil", 21)) == false);

    std::string badTemp = testCoversDir + "/bad.tmp";
    {
        std::ofstream f(badTemp);
        f << "bad";
    }
    InstallResult resTraversal = Installer::installVariant(
        testCoversDir, "../atmosphere/kips", badTemp, "abc", 3, true
    );
    assert(resTraversal.success == false);
    assert(resTraversal.message.find("Invalid") != std::string::npos);
    std::cout << "  -> PASS: Path traversal injection strictly rejected at boundary." << std::endl;

    // -------------------------------------------------------------------------
    // Scenario 7: Deletion Safety
    // -------------------------------------------------------------------------
    std::cout << "[SCENARIO 7] Deletion Safety..." << std::endl;
    // Create an unrelated user file
    std::string unrelatedFile = testCoversDir + "/0100000000010000.mp4";
    {
        std::ofstream f(unrelatedFile);
        f << "MARIO_VIDEO";
    }

    bool deleted = Installer::deleteCover(testCoversDir, titleId, true);
    assert(deleted == true);
    assert(!fs::exists(lowerMp4));
    assert(!fs::exists(targetMp4));
    // Unrelated file must still exist untouched!
    assert(fs::exists(unrelatedFile));
    std::cout << "  -> PASS: Cover removed without touching unrelated game covers." << std::endl;

    // Cleanup
    fs::remove_all(testCoversDir, ec);

    std::cout << "=================================================" << std::endl;
    std::cout << "  ALL 7 E2E SCENARIOS VERIFIED SUCCESSFULLY!     " << std::endl;
    std::cout << "=================================================" << std::endl;
}

int main() {
    runE2ETests();
    return 0;
}
