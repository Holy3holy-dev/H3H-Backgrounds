# Patch script for H3H Switch applications audit improvements
import sys
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC_DIR = ROOT / "downloader" / "src"

# 1. Patch catalog_manager.cpp
cat_mgr_file = SRC_DIR / "core" / "catalog_manager.cpp"
cat_content = cat_mgr_file.read_text(encoding="utf-8")

old_cat = """void CatalogManager::matchInstalledTitles(std::vector<InstalledTitle>& installedTitles) const {
    for (auto& installed : installedTitles) {
        const auto* match = findByTitleId(installed.titleId);
        if (match) {
            installed.hasCatalogMatch = true;
            installed.catalogEntry = *match;
        } else {
            installed.hasCatalogMatch = false;
        }
    }
}"""

new_cat = """void CatalogManager::matchInstalledTitles(std::vector<InstalledTitle>& installedTitles) const {
    for (auto& installed : installedTitles) {
        const auto* match = findByTitleId(installed.titleId);
        if (match) {
            installed.hasCatalogMatch = true;
            installed.catalogEntry = *match;
            if (installed.name.empty() || installed.name == "Unknown Game") {
                installed.name = match->title;
            }
            if (installed.author.empty() || installed.author == "Unknown Publisher") {
                installed.author = match->publisher;
            }
        } else {
            installed.hasCatalogMatch = false;
        }
    }
}"""

if old_cat in cat_content:
    cat_content = cat_content.replace(old_cat, new_cat, 1)
    cat_mgr_file.write_text(cat_content, encoding="utf-8")
    print("[+] Patched catalog_manager.cpp: matchInstalledTitles()")
else:
    print("[!] catalog_manager.cpp already patched or old block not found")

# 2. Patch video_player.cpp
vp_file = SRC_DIR / "ui" / "video_player.cpp"
vp_content = vp_file.read_text(encoding="utf-8")

old_vp_eof = """        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) {
            // EOF reached: seek back to beginning for seamless loop
            av_seek_frame(m_formatCtx, m_videoStream, 0, AVSEEK_FLAG_BACKWARD);
            avcodec_flush_buffers(m_codecCtx);
            continue;
        }"""

new_vp_eof = """        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) {
            // EOF reached: seek back to beginning for seamless loop
            int sret = av_seek_frame(m_formatCtx, m_videoStream, 0, AVSEEK_FLAG_BACKWARD);
            avcodec_flush_buffers(m_codecCtx);
            if (sret < 0) {
                // Seek failed -> break out of loop to avoid tight CPU spin
                break;
            }
            continue;
        }"""

if old_vp_eof in vp_content:
    vp_content = vp_content.replace(old_vp_eof, new_vp_eof, 1)
    vp_file.write_text(vp_content, encoding="utf-8")
    print("[+] Patched video_player.cpp: EOF seek error break")
else:
    print("[!] video_player.cpp already patched or old block not found")

print("[*] Completed step 1 (catalog_manager & video_player)")
