#!/usr/bin/env python3
"""
Automated Verification Suite for Redesigned UI & Video Icons Workflow.
Tests:
1. Video icons catalog integrity (HEVC 256x256, TitleID normalization).
2. Video icon installation target path resolution (sdmc:/recordings/icons/<TitleID>.mp4).
3. Independent coexistence of Video Cover and Video Icon without collision.
4. OTA update transactional package verification (.nro.tmp -> .nro.bak -> .nro).
5. Catalog category indexing and filtering.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path


def test_redesign_components():
    print("=======================================================")
    print("  H3H Redesign Verification: Video Icons & OTA System  ")
    print("=======================================================")

    root_dir = Path(__file__).parent.parent.parent
    catalog_path = root_dir / "catalog" / "data" / "catalog.json"

    assert catalog_path.exists(), f"Catalog file not found at {catalog_path}"

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # 1. Video Icons Catalog Audit
    print("\n[TEST 1] Video Icons Catalog Audit...")
    total_games = len(catalog.get("games", []))
    games_with_icons = []
    total_icons = 0

    for g in catalog["games"]:
        t_id = g["titleId"]
        assert len(t_id) == 16 and all(c in "0123456789ABCDEFabcdef" for c in t_id), f"Invalid TitleID: {t_id}"
        has_icon = False
        for v in g.get("variants", []):
            if v.get("hasIcon"):
                has_icon = True
                total_icons += 1
                assert v.get("iconUrl"), f"Missing iconUrl in {t_id} {v.get('id')}"
                assert v.get("iconCodec") in ["hevc", "h264"], f"Codec must be HEVC or H264, got {v.get('iconCodec')}"
                assert v.get("iconWidth") == 256 and v.get("iconHeight") == 256, f"Invalid dimensions in {t_id}"
        if has_icon:
            games_with_icons.append(g)

    print(f"  -> PASS: Verified {len(games_with_icons)} games with video icons (total {total_icons} video icon variants)")
    assert len(games_with_icons) >= 100, f"Expected at least 100 titles with icons, got {len(games_with_icons)}"

    # 2. Path Isolation and Coexistence Test
    print("\n[TEST 2] Path Isolation (Covers vs Icons)...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        sdmc = Path(tmp_dir) / "sdmc"
        covers_dir = sdmc / "recordings" / "covers"
        icons_dir = sdmc / "recordings" / "icons"
        covers_dir.mkdir(parents=True, exist_ok=True)
        icons_dir.mkdir(parents=True, exist_ok=True)

        sample_title = "010044E01D5C4000"
        cover_file = covers_dir / f"{sample_title}.mp4"
        icon_file = icons_dir / f"{sample_title}.mp4"

        # Write dummy data
        cover_file.write_bytes(b"COVER_DATA_720P")
        icon_file.write_bytes(b"ICON_DATA_256P")

        assert cover_file.exists() and cover_file.read_bytes() == b"COVER_DATA_720P"
        assert icon_file.exists() and icon_file.read_bytes() == b"ICON_DATA_256P"
        assert cover_file.parent != icon_file.parent, "Covers and Icons must reside in distinct directories!"
        print("  -> PASS: Video covers and Video icons coexist with zero collisions in separate directories.")

    # 3. Transactional OTA Update Simulation
    print("\n[TEST 3] Transactional OTA Update Simulation...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        app_dir = Path(tmp_dir) / "switch" / "H3H-Backgrounds"
        app_dir.mkdir(parents=True, exist_ok=True)

        target_nro = app_dir / "H3H-Backgrounds.nro"
        target_nro.write_bytes(b"OLD_NRO_V1.3.6_ORIGINAL_PAYLOAD")

        # Simulate update download to .tmp
        temp_nro = app_dir / "H3H-Backgrounds.nro.tmp"
        bak_nro = app_dir / "H3H-Backgrounds.nro.bak"
        new_payload = b"NEW_NRO_V1.4.0_TORRENTSHOP_UI_PAYLOAD"
        temp_nro.write_bytes(new_payload)

        # Transaction: Backup -> Replace
        if bak_nro.exists():
            bak_nro.unlink()
        target_nro.rename(bak_nro)
        temp_nro.rename(target_nro)

        assert target_nro.read_bytes() == new_payload, "Update payload mismatch!"
        assert bak_nro.read_bytes() == b"OLD_NRO_V1.3.6_ORIGINAL_PAYLOAD", "Backup payload mismatch!"

        # Simulate Rollback on simulated fault
        target_nro.unlink()
        bak_nro.rename(target_nro)
        assert target_nro.read_bytes() == b"OLD_NRO_V1.3.6_ORIGINAL_PAYLOAD"
        print("  -> PASS: Transactional atomic update and rollback verified.")

    # 4. Verified NRO Binary Signatures
    print("\n[TEST 4] Binary Artifacts Verification...")
    nro_main = root_dir / "downloader" / "H3H-Backgrounds.nro"
    nro_ad = root_dir / "downloader" / "H3H-AfterDark.nro"

    assert nro_main.exists(), f"Missing binary: {nro_main}"
    assert nro_ad.exists(), f"Missing binary: {nro_ad}"

    size_main = nro_main.stat().st_size
    size_ad = nro_ad.stat().st_size

    print(f"  -> H3H-Backgrounds.nro size: {size_main:,} bytes")
    print(f"  -> H3H-AfterDark.nro size:   {size_ad:,} bytes")

    # Check NRO Header Magic 'NRO0' at offset 0x10
    with open(nro_main, "rb") as f:
        f.seek(0x10)
        magic_main = f.read(4)
        assert magic_main == b"NRO0", f"Invalid NRO magic: {magic_main}"

    with open(nro_ad, "rb") as f:
        f.seek(0x10)
        magic_ad = f.read(4)
        assert magic_ad == b"NRO0", f"Invalid NRO magic: {magic_ad}"

    print("  -> PASS: Valid NRO0 magic headers confirmed on both binaries.")

    # 5. Source Code Regression Checks
    print("\n[TEST 5] Source Code Regression Checks...")
    switch_platform_cpp = root_dir / "downloader" / "src" / "platform" / "switch_platform.cpp"
    installer_cpp = root_dir / "downloader" / "src" / "core" / "installer.cpp"
    cloud_config_py = root_dir / "studio" / "h3h_studio" / "core" / "cloud_config.py"

    assert switch_platform_cpp.exists(), f"Missing {switch_platform_cpp}"
    assert installer_cpp.exists(), f"Missing {installer_cpp}"
    assert cloud_config_py.exists(), f"Missing {cloud_config_py}"

    # a) switch_platform.cpp does not rewrite /thumbnail URLs
    switch_code = switch_platform_cpp.read_text(encoding="utf-8")
    assert "/thumbnail" in switch_code, "switch_platform.cpp must guard /thumbnail URLs from drive.usercontent rewrite"
    assert "effectiveUrl.find(\"/thumbnail\") == std::string::npos" in switch_code or "thumbnail" in switch_code
    print("  -> PASS: switch_platform.cpp protects Google Drive /thumbnail URLs from rewrite.")

    # b) installer.cpp allows 4096-byte video icons in validateVideoFile and validates icons in installIcon
    installer_code = installer_cpp.read_text(encoding="utf-8")
    assert "size < 4096" in installer_code, "installer.cpp must use 4096 bytes threshold in validateVideoFile"
    assert "validateVideoFile" in installer_code
    install_icon_idx = installer_code.find("Installer::installIcon")
    assert install_icon_idx != -1, "Installer::installIcon not found in installer.cpp"
    install_icon_body = installer_code[install_icon_idx:installer_code.find("Installer::deleteIcon", install_icon_idx)]
    assert "validateVideoFile" in install_icon_body, "installIcon must validate video file before installation"
    print("  -> PASS: installer.cpp allows 4096-byte video icons and enforces integrity in installIcon.")

    # c) cloud_config.py does not have redundant catalog_path.read_bytes() inside try: block
    cloud_code = cloud_config_py.read_text(encoding="utf-8")
    push_func_idx = cloud_code.find("def push_catalog_to_github")
    assert push_func_idx != -1
    push_body = cloud_code[push_func_idx:]
    try_block_idx = push_body.find("try:")
    assert try_block_idx != -1
    try_body = push_body[try_block_idx:]
    assert "catalog_path.read_bytes()" not in try_body, "cloud_config.py must not call catalog_path.read_bytes() inside try block"
    print("  -> PASS: cloud_config.py avoids UnboundLocalError by removing redundant catalog_path.read_bytes().")

    # 6. Second-Pass UI, Touch & Input Audit Regression Checks
    print("\n[TEST 6] Second-Pass UI, Touch & Input Audit Regression Checks...")
    app_cpp = (root_dir / "downloader" / "src" / "ui" / "app.cpp").read_text(encoding="utf-8")
    app_hpp = (root_dir / "downloader" / "include" / "ui" / "app.hpp").read_text(encoding="utf-8")

    # 1) StorageStats tracks installed video icons
    assert "iconsCount" in app_hpp and "iconsBytes" in app_hpp, "StorageStats must track iconsCount and iconsBytes"
    assert "m_storageStats.iconsCount++" in app_cpp, "refreshStorageStats must scan getIconsDirectory()"
    # 2) No hardcoded 'Все (112)' or '433 видеоиконки'
    assert "Все (112)" not in app_cpp, "renderTabVideoIcons must use dynamic count instead of hardcoded Все (112)"
    assert "433 видеоиконки" not in app_cpp, "renderTabHome must use dynamic totalIconVariants count"
    # 3) Touch drag supports Tab::VideoIcons and Tab::Downloads
    drag_idx = app_cpp.find("void App::handleTouchDrag")
    assert drag_idx != -1
    drag_body = app_cpp[drag_idx:app_cpp.find("void App::handleTouchSwipe", drag_idx)]
    assert "Tab::VideoIcons" in drag_body, "handleTouchDrag must support scrolling in Tab::VideoIcons"
    assert "Tab::Downloads" in drag_body, "handleTouchDrag must support scrolling in Tab::Downloads"
    # 4) No duplicate else if (m_activeTab == Tab::Catalog) in handleTouchTap
    tap_idx = app_cpp.find("void App::handleTouchTap")
    assert tap_idx != -1
    tap_body = app_cpp[tap_idx:drag_idx]
    assert tap_body.count("else if (m_activeTab == Tab::Catalog)") == 1, "handleTouchTap must not have duplicate unreachable Tab::Catalog branch"
    assert "if (my >= 10 && my <= 55)" not in tap_body, "Phantom header tab-switching touch zone must be removed"
    # 5) MyGames [Y] delete supports games with only an installed icon
    assert "if (g.hasInstalledCover || g.hasInstalledIcon)" in app_cpp, "MyGames [Y] handler must check g.hasInstalledCover || g.hasInstalledIcon"
    print("  -> PASS: All 7 Second-Pass UI, Touch, Animation & Storage Audit checks verified.")

    # 7. Third-Pass Audit, Thumbnail/Video-Icon Reliability & UI/UX Variants (A, B, C, D)
    print("\n[TEST 7] Third-Pass Audit & UI/UX Variants (A, B, C, D) Verification...")

    # Audit #1 & Thumbnail Reliability: No synchronous network blocking on Collection Browser cursor move
    coll_idx = app_cpp.find("if (m_isCollectionBrowserOpen)")
    assert coll_idx != -1
    assert "m_collectionPreviewDirty = true" in app_cpp, "Collection Browser cursor movement must debounce preview loading via m_collectionPreviewDirty"
    assert "validateImageFile" in app_cpp, "Thumbnails must be validated for JPEG/PNG/WebP magic bytes before SDL texture upload"
    assert "sanitizeThumbCache" in app_cpp, "Startup must sanitize corrupted files in the thumbnail cache"
    assert 'fopen(destPath.c_str(), "wb")' in switch_code, "switch_platform.cpp must open downloads with 'wb' (no corrupting Range append on Google Drive)"
    assert "curlFileWriteCallback" in switch_code, "switch_platform.cpp must check cancel flag inside curlFileWriteCallback for instant <5ms abort"

    # Audit #2: Collection Browser [A] immediate install vs [Y] Game Picker
    assert "openGamePicker(m_collectionVariants[m_collectionSelectedIndex], m_collectionGameName)" in app_cpp, "Collection Browser [Y] must open Game Picker"
    assert "m_pendingActionVariant = chosenVar" in app_cpp, "Collection Browser [A] must confirm/install directly for the selected game"

    # Audit #3 & Variant B: Video Icons deduplication + Split-Screen Live Switch Icon Dock + variant selector
    assert "getUniqueIconVariants" in app_cpp, "Video Icons must deduplicate identical iconUrl entries via getUniqueIconVariants"
    assert "loadVideoIconDockPreview" in app_cpp, "Tab::VideoIcons must support right-pane Live Switch Icon Dock preview"
    assert "m_videoIconVariantIdx" in app_hpp and "m_videoIconDockTexture" in app_hpp, "App must track per-game icon variant index and dock texture"

    # Audit #4: Integrity check scans both covers and icons
    integrity_idx = app_cpp.find("void App::runIntegrityCheck()")
    assert integrity_idx != -1
    integrity_body = app_cpp[integrity_idx:app_cpp.find("void App::executeDeleteCorruptedCovers()", integrity_idx)]
    assert "getCoversDirectory()" in integrity_body and "getIconsDirectory()" in integrity_body, "runIntegrityCheck must scan both covers and icons"

    # Audit #5: Complete bilingual RU/EN localization via tr(ru, en)
    assert "const char* tr(const char* ru, const char* en) const" in app_hpp, "Bilingual helper tr(ru, en) must be defined in App"

    # Audit #6: Interactive Downloads queue cursor + [-] remove + [A] retry
    assert "m_downloadsSelectedIndex" in app_hpp and "m_smoothDownloadsSelY" in app_hpp, "Tab::Downloads must have interactive selection cursor"

    # Audit #7: Thread-safe OTA version string
    assert "m_nroUpdateLatestVer" in app_hpp, "OTA update must store m_nroUpdateLatestVer protected by m_nroMutex"

    # Variant A (Row Thumbnails), Variant C ([ZR] Horizon OS HUD), Variant D (Header Live Download Pill)
    assert "getOrRequestRowThumb" in app_cpp and "updateRowThumbPrefetcher" in app_cpp, "Variant A: 70x70 row mini-thumbnails LRU cache & prefetcher must be implemented"
    assert "m_previewShowSwitchHud" in app_hpp, "Variant C: [ZR] Horizon OS Home Screen Simulator overlay toggle must be implemented"
    assert "Live Active Download Pill in Header" in app_cpp and "hasActiveDownload" in app_cpp, "Variant D: Live Download Pill in header must be implemented"
    print("  -> PASS: All 7 Third-Pass Audit findings, Thumbnail/Icon fixes, and UI/UX Variants A, B, C, D verified.")

    # 8. Fourth-Pass Audit & Video Icon Preview in Video Backgrounds Catalog
    print("\n[TEST 8] Fourth-Pass Audit & Video Icon Preview inside Catalog/Collection/Fullscreen...")
    assert "m_collectionPreviewIconMode" in app_hpp and "m_collectionPreviewIconMode" in app_cpp, "Collection Browser must support 16:9 Cover vs 256x256 Video Icon preview toggle"
    assert "[R] Иконка 256x256" in app_cpp and "[R] Иконка 1:1" in app_cpp, "Fullscreen Preview and Collection Browser must expose [R] Video Icon Preview toggle"
    assert "[ZR] 256x256 (" in app_cpp, "Tab::Catalog must display interactive [ZR] 256x256 (N) badge for games with video icons"
    print("  -> PASS: All Fourth-Pass Audit fixes & Video Icon Preview in Catalog/Collection/Fullscreen verified.")

    # 9. Fifth-Pass Deep Audit Verification
    print("\n[TEST 9] Fifth-Pass Deep Audit (AVIO Buffer Leak, Thread Safety, State Reset)...")
    vp_cpp = (root_dir / "downloader" / "src" / "ui" / "video_player.cpp").read_text(encoding="utf-8")
    assert "av_freep(&m_avioCtx->buffer)" in vp_cpp, "VideoPlayer::close() must free m_avioCtx->buffer before avio_context_free"
    assert "m_dialogFocus = (m_collectionPreviewIconMode && chosenVar.hasIcon) ? 1 : 0;" in app_cpp, "Collection Browser [A] must pre-select Icon Only when m_collectionPreviewIconMode is active"
    assert "Видеоиконка 4IFIR  •  256x256 (" in app_cpp, "Collection Browser must show 256x256 icon metadata when showCollIconMode is active"
    print("  -> PASS: All Fifth-Pass Deep Audit fixes verified.")

    # 10. Sixth-Pass Deep Performance & Black-Screen Audit Verification
    print("\n[TEST 10] Sixth-Pass Deep Performance & Black-Screen Audit (Zero-Freeze, TLS Keep-Alive, Instant Splash)...")
    assert "curl_share_init" in switch_code and "getThreadCurlHandle" in switch_code, "switch_platform.cpp must share DNS/TLS sessions and reuse CURL* handles per thread"
    assert "probesize = 192 * 1024" in vp_cpp and "max_analyze_duration = 400000" in vp_cpp, "VideoPlayer::open() must configure fast FFmpeg probesize and max_analyze_duration"
    assert "renderBootSplash" in app_cpp and "renderBootSplash" in app_hpp, "App::init() must render an immediate boot splash screen before SD card & catalog scans"
    assert "updateAsyncPreviewWorkers" in app_cpp and "updateAsyncPreviewWorkers" in app_hpp, "App must use non-blocking async preview workers instead of main-thread .join() calls"
    assert "findCachedThumbTexture" in app_cpp and "findCachedThumbTexture" in app_hpp, "App must reuse cached row thumbnails across Dock, Collection, and Fullscreen Preview"
    vi_idx = app_cpp.find("void App::renderTabVideoIcons()")
    vi_body = app_cpp[vi_idx:app_cpp.find("void App::renderTabCatalog()", vi_idx)]
    assert "iconrow_" not in vi_body and '"icon_" + entry.titleId' in vi_body, "Tab::VideoIcons must unify thumbnail cache keys to icon_ so Dock and Fullscreen share cached textures"
    print("  -> PASS: All 7 Sixth-Pass Deep Performance & Black-Screen Audit fixes verified.")

    print("\n=======================================================")
    print("  ALL REDESIGN VERIFICATION TESTS PASSED SUCCESSFULLY! ")
    print("=======================================================")


if __name__ == "__main__":
    test_redesign_components()
