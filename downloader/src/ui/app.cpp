
#include "ui/app.hpp"
#include "core/installed_registry.hpp"
#include "core/config.hpp"
#include "core/installer.hpp"
#include "core/json.hpp"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <fstream>
#include <filesystem>
#include <cmath>

#ifdef __SWITCH__
#include <switch.h>
#endif

#ifdef HAS_SDL2
#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <SDL2/SDL_image.h>
#endif

namespace h3h {
namespace ui {

#ifdef HAS_SDL2
namespace {
static bool validateImageFile(const std::string& path) {
    if (path.empty()) return false;
    FILE* fp = fopen(path.c_str(), "rb");
    if (!fp) return false;
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return false;
    }
    long sz = ftell(fp);
    if (sz < 512) {
        fclose(fp);
        return false;
    }
    fseek(fp, 0, SEEK_SET);
    unsigned char hdr[8] = {0};
    size_t readBytes = fread(hdr, 1, sizeof(hdr), fp);
    fclose(fp);
    if (readBytes < 4) return false;
    // JPEG magic: FF D8 FF
    if (hdr[0] == 0xFF && hdr[1] == 0xD8 && hdr[2] == 0xFF) return true;
    // PNG magic: 89 50 4E 47
    if (hdr[0] == 0x89 && hdr[1] == 0x50 && hdr[2] == 0x4E && hdr[3] == 0x47) return true;
    return false;
}

static SDL_Texture* loadTextureFromFile(SDL_Renderer* renderer, const std::string& path) {
    if (!renderer || path.empty()) return nullptr;
    FILE* fp = fopen(path.c_str(), "rb");
    if (!fp) return nullptr;
    SDL_RWops* rw = SDL_RWFromFP(fp, SDL_TRUE);
    if (!rw) {
        fclose(fp);
        return nullptr;
    }
    SDL_Surface* surf = IMG_Load_RW(rw, 1);
    if (!surf) return nullptr;
    SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
    SDL_FreeSurface(surf);
    if (tex) {
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_BLEND);
    }
    return tex;
}

// UTF-8 lowercase conversion for English and Russian Cyrillic
static std::string utf8ToLower(const std::string& s) {
    std::string result;
    result.reserve(s.size());
    for (size_t i = 0; i < s.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        if (c < 0x80) {
            result.push_back(static_cast<char>(std::tolower(c)));
        } else if (c == 0xD0 && i + 1 < s.size()) {
            unsigned char c2 = static_cast<unsigned char>(s[i + 1]);
            if (c2 == 0x81) { // Ё -> ё (0xD1 0x91)
                result.push_back(static_cast<char>(0xD1));
                result.push_back(static_cast<char>(0x91));
                i++;
            } else if (c2 >= 0x90 && c2 <= 0x9F) { // А..П -> а..п (0xD0 0xB0..0xBF)
                result.push_back(static_cast<char>(0xD0));
                result.push_back(static_cast<char>(c2 + 0x20));
                i++;
            } else if (c2 >= 0xA0 && c2 <= 0xAF) { // Р..Я -> р..я (0xD1 0x80..0x8F)
                result.push_back(static_cast<char>(0xD1));
                result.push_back(static_cast<char>(c2 - 0x20));
                i++;
            } else {
                result.push_back(s[i]);
            }
        } else {
            result.push_back(s[i]);
        }
    }
    return result;
}
} // anonymous namespace
#endif

static std::string extractDriveIdFromUrl(const std::string& url) {
    size_t idPos = url.find("id=");
    if (idPos != std::string::npos) {
        std::string drvId = url.substr(idPos + 3);
        size_t amp = drvId.find('&');
        if (amp != std::string::npos) drvId = drvId.substr(0, amp);
        return drvId;
    }
    size_t dPos = url.find("/d/");
    if (dPos != std::string::npos) {
        std::string drvId = url.substr(dPos + 3);
        size_t slash = drvId.find('/');
        if (slash != std::string::npos) drvId = drvId.substr(0, slash);
        return drvId;
    }
    return "";
}

std::vector<Variant> App::getUniqueIconVariants(const GameCatalogEntry& entry) {
    std::vector<Variant> result;
    std::set<std::string> seenIconKeys;

    // Pass 1: Dedicated standalone 256x256 icon-* variants first
    for (const auto& v : entry.variants) {
        bool isDedicatedIcon = (v.id.rfind("icon-", 0) == 0) || (v.width == 256 && v.height == 256);
        if (!isDedicatedIcon) continue;
        std::string iconLink = !v.iconUrl.empty() ? v.iconUrl : v.url;
        if (iconLink.empty()) continue;

        std::string drvId = extractDriveIdFromUrl(iconLink);
        std::string dedupKey = !drvId.empty() ? drvId : iconLink;
        if (seenIconKeys.count(dedupKey) > 0) continue;
        seenIconKeys.insert(dedupKey);

        Variant iv = v;
        iv.hasIcon = true;
        iv.url = iconLink;
        iv.iconUrl = iconLink;
        iv.width = 256;
        iv.height = 256;
        iv.iconWidth = 256;
        iv.iconHeight = 256;
        if (iv.iconSizeBytes > 0) iv.sizeBytes = iv.iconSizeBytes;
        if (!drvId.empty()) {
            iv.previewUrl = "https://drive.google.com/thumbnail?id=" + drvId + "&sz=w320";
        }
        result.push_back(std::move(iv));
    }

    // Pass 2: Any attached iconUrl on 16:9 variants not already in result
    for (const auto& v : entry.variants) {
        if (!v.hasIcon || v.iconUrl.empty()) continue;
        std::string drvId = extractDriveIdFromUrl(v.iconUrl);
        std::string dedupKey = !drvId.empty() ? drvId : v.iconUrl;
        if (seenIconKeys.count(dedupKey) > 0) continue;
        seenIconKeys.insert(dedupKey);

        Variant iv = v;
        iv.hasIcon = true;
        iv.url = v.iconUrl;
        iv.iconUrl = v.iconUrl;
        iv.width = 256;
        iv.height = 256;
        iv.iconWidth = 256;
        iv.iconHeight = 256;
        if (iv.iconSizeBytes > 0) iv.sizeBytes = iv.iconSizeBytes;
        if (!drvId.empty()) {
            iv.previewUrl = "https://drive.google.com/thumbnail?id=" + drvId + "&sz=w320";
        }
        result.push_back(std::move(iv));
    }

    return result;
}

std::vector<Variant> App::getCoverVariants(const GameCatalogEntry& entry) {
    std::vector<Variant> covers;
    for (const auto& v : entry.variants) {
        bool isPureIcon = (v.id.rfind("icon-", 0) == 0) || (v.width == 256 && v.height == 256);
        if (!isPureIcon) {
            covers.push_back(v);
        }
    }
    if (covers.empty()) {
        covers = entry.variants;
    }
    return covers;
}

void App::sanitizeThumbCache() {
    if (!m_platform) return;
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    if (!std::filesystem::exists(thumbDir, ec)) return;

    int purgedCount = 0;
    for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
        if (!entry.is_regular_file(ec)) continue;
        std::string ext = entry.path().extension().string();
        uint64_t fsz = entry.file_size(ec);
        // Fast metadata-only check on startup (eliminates slow FAT32 fopen/fseek across hundreds of files on boot)
        if (ext == ".tmp" || fsz < 512) {
            std::filesystem::remove(entry.path(), ec);
            purgedCount++;
        }
    }
    if (purgedCount > 0) {
        std::cout << "[+] Sanitized thumb cache: purged " << purgedCount << " leftover/corrupted files." << std::endl;
    }
}

void App::clearRowThumbTextures() {
#ifdef HAS_SDL2
    m_cancelRowThumb.store(true);
    if (m_rowThumbThread.joinable()) {
        m_rowThumbThread.join();
    }
    m_cancelRowThumb.store(false);
    m_rowThumbBusy.store(false);
    for (auto& kv : m_rowThumbTextures) {
        if (kv.second) {
            SDL_DestroyTexture(kv.second);
        }
    }
    m_rowThumbTextures.clear();
    m_failedRowThumbs.clear();
    {
        std::lock_guard<std::mutex> lock(m_rowThumbMutex);
        m_pendingRowThumbKey.clear();
        m_pendingRowThumbPath.clear();
        m_queuedRowThumbKey.clear();
        m_queuedRowThumbUrl.clear();
        m_queuedRowThumbDest.clear();
    }
#endif
}

SDL_Texture* App::getOrRequestRowThumb(const std::string& cacheKey, const std::string& thumbUrl, bool highPriority) {
#ifdef HAS_SDL2
    if (!m_renderer || cacheKey.empty()) return nullptr;
    auto it = m_rowThumbTextures.find(cacheKey);
    if (it != m_rowThumbTextures.end()) {
        return it->second;
    }
    if (m_failedRowThumbs.count(cacheKey) > 0) {
        return nullptr;
    }

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::string thumbFile = thumbDir + "/" + cacheKey + ".jpg";
    std::error_code ec;
    // Also check legacy iconrow_ alias on disk if cacheKey starts with icon_
    std::string altFile;
    if (cacheKey.rfind("icon_", 0) == 0) {
        altFile = thumbDir + "/iconrow_" + cacheKey.substr(5) + ".jpg";
    }
    std::string existingFile;
    if (std::filesystem::exists(thumbFile, ec)) {
        existingFile = thumbFile;
    } else if (!altFile.empty() && std::filesystem::exists(altFile, ec)) {
        existingFile = altFile;
    }

    if (!existingFile.empty()) {
        if (validateImageFile(existingFile)) {
            if (m_rowThumbTextures.size() >= 64) {
                auto firstIt = m_rowThumbTextures.begin();
                if (firstIt->second) SDL_DestroyTexture(firstIt->second);
                m_rowThumbTextures.erase(firstIt);
            }
            SDL_Texture* tex = loadTextureFromFile(m_renderer, existingFile);
            if (tex) {
                m_rowThumbTextures[cacheKey] = tex;
                return tex;
            }
        }
        std::filesystem::remove(existingFile, ec);
    }

    // Queue background download (focused row overwrites queued item so scrolling is always responsive!)
    if (!thumbUrl.empty()) {
        std::lock_guard<std::mutex> lock(m_rowThumbMutex);
        if (highPriority || m_queuedRowThumbKey.empty()) {
            m_queuedRowThumbKey = cacheKey;
            m_queuedRowThumbUrl = thumbUrl;
            m_queuedRowThumbDest = thumbFile;
        }
    }
#else
    (void)cacheKey; (void)thumbUrl; (void)highPriority;
#endif
    return nullptr;
}

SDL_Texture* App::findCachedThumbTexture(const std::string& titleId, const Variant& variant, bool isIcon) {
#ifdef HAS_SDL2
    if (!m_renderer || titleId.empty()) return nullptr;
    std::vector<std::string> candidateKeys;
    if (isIcon) {
        candidateKeys.push_back("icon_" + titleId + "_" + variant.id);
        candidateKeys.push_back("iconrow_" + titleId + "_" + variant.id);
        candidateKeys.push_back(titleId + "_" + variant.id);
    } else {
        candidateKeys.push_back(titleId + "_" + variant.id);
        candidateKeys.push_back("icon_" + titleId + "_" + variant.id);
    }

    for (const auto& k : candidateKeys) {
        auto it = m_rowThumbTextures.find(k);
        if (it != m_rowThumbTextures.end() && it->second != nullptr) {
            return it->second;
        }
    }

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    for (const auto& k : candidateKeys) {
        std::string f = thumbDir + "/" + k + ".jpg";
        if (std::filesystem::exists(f, ec) && validateImageFile(f)) {
            SDL_Texture* tex = loadTextureFromFile(m_renderer, f);
            if (tex) {
                if (m_rowThumbTextures.size() >= 64) {
                    auto firstIt = m_rowThumbTextures.begin();
                    if (firstIt->second) SDL_DestroyTexture(firstIt->second);
                    m_rowThumbTextures.erase(firstIt);
                }
                m_rowThumbTextures[k] = tex;
                return tex;
            }
        }
    }
#else
    (void)titleId; (void)variant; (void)isIcon;
#endif
    return nullptr;
}

void App::updateRowThumbPrefetcher() {
#ifdef HAS_SDL2
    // 1. Upload completed row thumbnail on main thread
    std::string doneKey;
    std::string donePath;
    {
        std::lock_guard<std::mutex> lock(m_rowThumbMutex);
        if (!m_pendingRowThumbKey.empty()) {
            doneKey = std::move(m_pendingRowThumbKey);
            donePath = std::move(m_pendingRowThumbPath);
            m_pendingRowThumbKey.clear();
            m_pendingRowThumbPath.clear();
        }
    }
    if (!doneKey.empty()) {
        if (!donePath.empty() && validateImageFile(donePath) && m_renderer) {
            if (m_rowThumbTextures.size() >= 64) {
                auto firstIt = m_rowThumbTextures.begin();
                if (firstIt->second) SDL_DestroyTexture(firstIt->second);
                m_rowThumbTextures.erase(firstIt);
            }
            SDL_Texture* tex = loadTextureFromFile(m_renderer, donePath);
            if (tex) {
                m_rowThumbTextures[doneKey] = tex;
            } else {
                m_failedRowThumbs.insert(doneKey);
            }
        } else {
            m_failedRowThumbs.insert(doneKey);
        }
    }

    // 2. Pause row prefetcher while Fullscreen Preview or Collection/Dock video is actively downloading
    // so 100% of Switch Wi-Fi bandwidth goes to the user's open preview!
    if (m_previewWorkerBusy.load() || m_collectionWorkerBusy.load() || m_isFullscreenPreview) {
        return;
    }

    // 3. Start next queued row thumbnail download if worker is idle
    if (!m_rowThumbBusy.load()) {
        std::string nextKey, nextUrl, nextDest;
        {
            std::lock_guard<std::mutex> lock(m_rowThumbMutex);
            if (!m_queuedRowThumbKey.empty()) {
                nextKey = std::move(m_queuedRowThumbKey);
                nextUrl = std::move(m_queuedRowThumbUrl);
                nextDest = std::move(m_queuedRowThumbDest);
                m_queuedRowThumbKey.clear();
                m_queuedRowThumbUrl.clear();
                m_queuedRowThumbDest.clear();
            }
        }
        if (!nextKey.empty() && !nextUrl.empty()) {
            if (m_rowThumbThread.joinable()) {
                m_rowThumbThread.join();
            }
            m_rowThumbBusy.store(true);
            m_cancelRowThumb.store(false);
            m_rowThumbThread = std::thread([this, nextKey, nextUrl, nextDest]() {
                std::error_code ec;
                std::filesystem::create_directories(std::filesystem::path(nextDest).parent_path(), ec);
                std::string tmpDest = nextDest + ".tmp";
                std::string err;
                bool ok = m_platform->downloadFile(nextUrl, tmpDest, nullptr, m_cancelRowThumb, err);
                std::string validPath;
                if (ok && !m_cancelRowThumb.load() && validateImageFile(tmpDest)) {
                    std::filesystem::rename(tmpDest, nextDest, ec);
                    validPath = nextDest;
                } else {
                    std::filesystem::remove(tmpDest, ec);
                }
                {
                    std::lock_guard<std::mutex> lock(m_rowThumbMutex);
                    m_pendingRowThumbKey = nextKey;
                    m_pendingRowThumbPath = validPath;
                }
                m_rowThumbBusy.store(false);
            });
        }
    }
#endif
}

void App::updateAsyncPreviewWorkers() {
#ifdef HAS_SDL2
    // 1. Non-blocking Fullscreen Preview worker dispatcher (NEVER blocks main thread on .join()!)
    if (!m_previewWorkerBusy.load()) {
        if (m_previewThread.joinable()) {
            m_previewThread.join();
        }
        if (m_previewTransferQueued && m_isFullscreenPreview) {
            m_previewTransferQueued = false;
            std::string thumbUrl = m_queuedPreviewThumbUrl;
            std::string videoUrl = m_queuedPreviewVideoUrl;
            std::string thumbFile = m_queuedPreviewThumbFile;
            std::string vidFile = m_queuedPreviewVidFile;
            std::string key = m_queuedPreviewKey;
            bool isIcon = m_queuedPreviewIsIcon;

            m_cancelPreview.store(false);
            m_previewWorkerBusy.store(true);
            m_previewDownloadBytes.store(0);

            m_previewThread = std::thread([this, thumbUrl, videoUrl, thumbFile, vidFile, key, isIcon]() {
                std::error_code ec2;
                std::filesystem::create_directories(std::filesystem::path(thumbFile).parent_path(), ec2);
                auto progCb = [this](uint64_t dlNow, uint64_t dlTot, double) {
                    m_previewDownloadBytes.store(dlNow);
                    if (dlTot > 0) m_previewDownloadTotal.store(dlTot);
                };

                if (isIcon) {
                    // For 256x256 Video Icons (88-212 KB): download the MP4 FIRST!
                    // Direct MP4 download from drive.usercontent.google.com is faster than Google Drive's /thumbnail generator
                    // and immediately plays 30 FPS video (and decodes frame #1 as the texture)!
                    bool videoOk = false;
                    if (!m_cancelPreview.load() && !videoUrl.empty() && !std::filesystem::exists(vidFile, ec2)) {
                        std::string err;
                        std::string tmpVid = vidFile + ".tmp";
                        bool ok = m_platform->downloadFile(videoUrl, tmpVid, progCb, m_cancelPreview, err);
                        m_videoDownloading = false;
                        if (ok && !m_cancelPreview.load() && std::filesystem::exists(tmpVid, ec2)) {
                            std::string valErr;
                            if (Installer::validateVideoFile(tmpVid, valErr)) {
                                std::filesystem::rename(tmpVid, vidFile, ec2);
                                videoOk = true;
                                if (m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                                    std::lock_guard<std::mutex> lock(m_previewMutex);
                                    m_pendingVideoToOpen = vidFile;
                                }
                            } else {
                                std::filesystem::remove(tmpVid, ec2);
                            }
                        } else {
                            std::filesystem::remove(tmpVid, ec2);
                        }
                    } else {
                        m_videoDownloading = false;
                        videoOk = std::filesystem::exists(vidFile, ec2);
                    }

                    // Only fetch static JPEG fallback if MP4 did not open
                    if (!videoOk && !m_cancelPreview.load() && !std::filesystem::exists(thumbFile, ec2) && !thumbUrl.empty()) {
                        std::string err;
                        std::string tmpThumb = thumbFile + ".tmp";
                        bool ok = m_platform->downloadFile(thumbUrl, tmpThumb, nullptr, m_cancelPreview, err);
                        if (ok && !m_cancelPreview.load() && validateImageFile(tmpThumb)) {
                            std::filesystem::rename(tmpThumb, thumbFile, ec2);
                            if (m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                                std::lock_guard<std::mutex> lock(m_previewMutex);
                                m_pendingPreviewFileToLoad = thumbFile;
                            }
                        } else {
                            std::filesystem::remove(tmpThumb, ec2);
                        }
                    }
                    m_previewLoading = false;
                } else {
                    // For 16:9 HD Video Covers (3-6 MB):
                    // Step 1: If static thumbnail is not yet cached on SD, fetch lightweight w640 JPEG first
                    if (!std::filesystem::exists(thumbFile, ec2) && !thumbUrl.empty() && m_previewLoading.load()) {
                        std::string err;
                        std::string tmpThumb = thumbFile + ".tmp";
                        bool ok = m_platform->downloadFile(thumbUrl, tmpThumb, nullptr, m_cancelPreview, err);
                        m_previewLoading = false;
                        if (ok && !m_cancelPreview.load() && validateImageFile(tmpThumb)) {
                            std::filesystem::rename(tmpThumb, thumbFile, ec2);
                            if (m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                                std::lock_guard<std::mutex> lock(m_previewMutex);
                                m_pendingPreviewFileToLoad = thumbFile;
                            }
                        } else {
                            std::filesystem::remove(tmpThumb, ec2);
                        }
                    } else {
                        m_previewLoading = false;
                    }

                    // Step 2: Stream 16:9 MP4 video with live byte progress
                    if (!m_cancelPreview.load() && !videoUrl.empty() && !std::filesystem::exists(vidFile, ec2)) {
                        std::string err;
                        std::string tmpVid = vidFile + ".tmp";
                        bool ok = m_platform->downloadFile(videoUrl, tmpVid, progCb, m_cancelPreview, err);
                        m_videoDownloading = false;
                        if (ok && !m_cancelPreview.load() && std::filesystem::exists(tmpVid, ec2)) {
                            std::string valErr;
                            if (Installer::validateVideoFile(tmpVid, valErr)) {
                                std::filesystem::rename(tmpVid, vidFile, ec2);
                                if (m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                                    std::lock_guard<std::mutex> lock(m_previewMutex);
                                    m_pendingVideoToOpen = vidFile;
                                }
                            } else {
                                std::filesystem::remove(tmpVid, ec2);
                            }
                        } else {
                            std::filesystem::remove(tmpVid, ec2);
                        }
                    } else {
                        m_videoDownloading = false;
                    }
                }
                m_previewWorkerBusy.store(false);
            });
        }
    }

    // 2. Non-blocking Collection Browser & VideoIcons Dock worker dispatcher (NEVER blocks main thread on .join()!)
    if (!m_collectionWorkerBusy.load()) {
        if (m_collectionThumbThread.joinable()) {
            m_collectionThumbThread.join();
        }
        if (m_collectionTransferQueued && (m_isCollectionBrowserOpen || m_activeTab == Tab::VideoIcons)) {
            m_collectionTransferQueued = false;
            std::string thumbUrl = m_queuedCollThumbUrl;
            std::string videoUrl = m_queuedCollVideoUrl;
            std::string thumbFile = m_queuedCollThumbFile;
            std::string vidFile = m_queuedCollVidFile;
            std::string key = m_queuedCollKey;
            bool isIcon = m_queuedCollIsIcon;
            bool forDock = m_queuedCollForDock;

            m_cancelCollectionThumb.store(false);
            m_collectionWorkerBusy.store(true);
            m_collectionDownloadBytes.store(0);

            m_collectionThumbThread = std::thread([this, thumbUrl, videoUrl, thumbFile, vidFile, key, isIcon, forDock]() {
                std::string err;
                std::error_code ec2;
                std::filesystem::create_directories(std::filesystem::path(thumbFile).parent_path(), ec2);
                auto progCb = [this](uint64_t dlNow, uint64_t dlTot, double) {
                    m_collectionDownloadBytes.store(dlNow);
                    if (dlTot > 0) m_collectionDownloadTotal.store(dlTot);
                };

                if (isIcon) {
                    // For 256x256 Video Icons: download lightweight MP4 FIRST for instant live playback!
                    bool videoOk = false;
                    if (!m_cancelCollectionThumb.load() && !videoUrl.empty() && !std::filesystem::exists(vidFile, ec2)) {
                        std::string tmpVid = vidFile + ".tmp";
                        bool ok = m_platform->downloadFile(videoUrl, tmpVid, progCb, m_cancelCollectionThumb, err);
                        m_collectionVideoDownloading = false;
                        if (ok && !m_cancelCollectionThumb.load() && std::filesystem::exists(tmpVid, ec2)) {
                            std::string valErr;
                            if (Installer::validateVideoFile(tmpVid, valErr)) {
                                std::filesystem::rename(tmpVid, vidFile, ec2);
                                videoOk = true;
                                if (m_collectionCurrentThumbVariantId == key) {
                                    std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
                                    if (forDock) m_pendingVideoIconDockVideo = vidFile;
                                    else m_pendingCollectionVideoToOpen = vidFile;
                                }
                            } else {
                                std::filesystem::remove(tmpVid, ec2);
                            }
                        } else {
                            std::filesystem::remove(tmpVid, ec2);
                        }
                    } else {
                        m_collectionVideoDownloading = false;
                        videoOk = std::filesystem::exists(vidFile, ec2);
                    }

                    if (!videoOk && !m_cancelCollectionThumb.load() && !std::filesystem::exists(thumbFile, ec2) && !thumbUrl.empty()) {
                        std::string tmpThumb = thumbFile + ".tmp";
                        bool ok = m_platform->downloadFile(thumbUrl, tmpThumb, nullptr, m_cancelCollectionThumb, err);
                        if (ok && !m_cancelCollectionThumb.load() && validateImageFile(tmpThumb)) {
                            std::filesystem::rename(tmpThumb, thumbFile, ec2);
                            if (m_collectionCurrentThumbVariantId == key) {
                                std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
                                if (forDock) m_pendingVideoIconDockThumb = thumbFile;
                                else m_pendingCollectionThumbToLoad = thumbFile;
                            }
                        } else {
                            std::filesystem::remove(tmpThumb, ec2);
                        }
                    }
                    m_collectionThumbLoading = false;
                } else {
                    // For 16:9 Cover Variants: fetch static thumbnail if not already cached, then stream MP4
                    if (!std::filesystem::exists(thumbFile, ec2) && !thumbUrl.empty() && m_collectionThumbLoading.load()) {
                        std::string tmpThumb = thumbFile + ".tmp";
                        bool ok = m_platform->downloadFile(thumbUrl, tmpThumb, nullptr, m_cancelCollectionThumb, err);
                        m_collectionThumbLoading = false;
                        if (ok && !m_cancelCollectionThumb.load() && validateImageFile(tmpThumb)) {
                            std::filesystem::rename(tmpThumb, thumbFile, ec2);
                            if (m_collectionCurrentThumbVariantId == key) {
                                std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
                                if (forDock) m_pendingVideoIconDockThumb = thumbFile;
                                else m_pendingCollectionThumbToLoad = thumbFile;
                            }
                        } else {
                            std::filesystem::remove(tmpThumb, ec2);
                        }
                    } else {
                        m_collectionThumbLoading = false;
                    }

                    if (!m_cancelCollectionThumb.load() && !videoUrl.empty() && !std::filesystem::exists(vidFile, ec2)) {
                        std::string tmpVid = vidFile + ".tmp";
                        bool ok = m_platform->downloadFile(videoUrl, tmpVid, progCb, m_cancelCollectionThumb, err);
                        m_collectionVideoDownloading = false;
                        if (ok && !m_cancelCollectionThumb.load() && std::filesystem::exists(tmpVid, ec2)) {
                            std::string valErr;
                            if (Installer::validateVideoFile(tmpVid, valErr)) {
                                std::filesystem::rename(tmpVid, vidFile, ec2);
                                if (m_collectionCurrentThumbVariantId == key) {
                                    std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
                                    if (forDock) m_pendingVideoIconDockVideo = vidFile;
                                    else m_pendingCollectionVideoToOpen = vidFile;
                                }
                            } else {
                                std::filesystem::remove(tmpVid, ec2);
                            }
                        } else {
                            std::filesystem::remove(tmpVid, ec2);
                        }
                    } else {
                        m_collectionVideoDownloading = false;
                    }
                }
                m_collectionWorkerBusy.store(false);
            });
        }
    }
#endif
}

void App::renderBootSplash(const std::string& statusText, double progressPct) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, Theme::COLOR_BG_BASE.r, Theme::COLOR_BG_BASE.g, Theme::COLOR_BG_BASE.b, 255);
    SDL_RenderClear(m_renderer);

    int cw = 680, ch = 260;
    int cx = (Theme::SCREEN_WIDTH - cw) / 2;
    int cy = (Theme::SCREEN_HEIGHT - ch) / 2;

    drawGlassCard(cx, cy, cw, ch, true, true);
    drawNeonGradientOutline(cx, cy, cw, ch, 2);

    drawTextCentered(Config::APP_NAME, Theme::SCREEN_WIDTH / 2, cy + 42, Theme::COLOR_FOCUS_CYAN, 26);
    drawTextCentered("4IFIR CYBER-GLASS ENGINE  •  60 FPS", Theme::SCREEN_WIDTH / 2, cy + 82, Theme::COLOR_FOCUS_PINK, 13);
    drawTextCentered(statusText, Theme::SCREEN_WIDTH / 2, cy + 138, Theme::COLOR_TEXT_PRIMARY, 16);

    drawCapsuleProgressBar(cx + 60, cy + 185, cw - 120, 18, progressPct);
    SDL_RenderPresent(m_renderer);
#else
    (void)statusText; (void)progressPct;
#endif
}

int App::getSelectedVideoIconVariantIndex(const GameCatalogEntry& entry) const {
    if (entry.variants.empty()) return 0;
    auto it = m_videoIconVariantIdx.find(entry.titleId);
    if (it == m_videoIconVariantIdx.end()) return 0;
    return std::clamp(it->second, 0, static_cast<int>(entry.variants.size()) - 1);
}

App::App(std::unique_ptr<IPlatform> platform)
    : m_platform(std::move(platform)) {}

void App::loadTabIcons() {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    const char* names[5] = {
        "tab_catalog.png",
        "tab_video_icons.png",
        "tab_my_games.png",
        "tab_downloads.png",
        "tab_settings.png"
    };

    const char* prefixes[] = {
        "romfs:/icons/",
        "downloader/romfs/icons/",
        "sdmc:/switch/H3H-Backgrounds/icons/",
        "sdmc:/switch/H3H-AfterDark/icons/"
    };

    for (int i = 0; i < 5; ++i) {
        if (m_tabIconTextures[i]) continue;
        for (const char* pfx : prefixes) {
            std::string fullPath = std::string(pfx) + names[i];
            SDL_Texture* tex = loadTextureFromFile(m_renderer, fullPath);
            if (tex) {
                m_tabIconTextures[i] = tex;
                break;
            }
        }
    }
#endif
}

void App::clearTextCache() {
#ifdef HAS_SDL2
    for (auto& pair : m_textCache) {
        if (pair.second.texture) {
            SDL_DestroyTexture(pair.second.texture);
            pair.second.texture = nullptr;
        }
    }
    m_textCache.clear();
    m_textWidthCache.clear();
#endif
}

void App::freeTabIcons() {
#ifdef HAS_SDL2
    for (int i = 0; i < 5; ++i) {
        if (m_tabIconTextures[i]) {
            SDL_DestroyTexture(m_tabIconTextures[i]);
            m_tabIconTextures[i] = nullptr;
        }
    }
#endif
}

App::~App() {
    shutdown();
}

bool App::init() {
    if (!m_platform || !m_platform->initialize()) {
        std::cerr << "[-] Failed to initialize platform layer" << std::endl;
        return false;
    }

#ifdef HAS_SDL2
    SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");
    SDL_SetHint(SDL_HINT_MOUSE_TOUCH_EVENTS, "0");

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER) != 0) {
        std::cerr << "[-] SDL_Init failed: " << SDL_GetError() << std::endl;
        return false;
    }

    if (TTF_Init() != 0) {
        std::cerr << "[-] TTF_Init failed: " << TTF_GetError() << std::endl;
    }

    int imgFlags = IMG_INIT_JPG | IMG_INIT_PNG;
    if ((IMG_Init(imgFlags) & imgFlags) != imgFlags) {
        std::cerr << "[-] IMG_Init warning: " << IMG_GetError() << std::endl;
    }

#ifdef __SWITCH__
    PlFontData fontData;
    Result rc = plGetSharedFontByType(&fontData, PlSharedFontType_Standard);
    if (R_SUCCEEDED(rc) && fontData.address && fontData.size > 0) {
        m_fontMemBuffer = fontData.address;
        m_fontMemSize = fontData.size;
        std::cout << "[+] Loaded Switch Horizon shared font (" << fontData.size << " bytes)" << std::endl;
    } else {
        std::cerr << "[-] plGetSharedFontByType returned 0x" << std::hex << rc << std::endl;
    }
#endif

    m_window = SDL_CreateWindow(
        Config::APP_NAME,
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        Theme::SCREEN_WIDTH,
        Theme::SCREEN_HEIGHT,
        SDL_WINDOW_SHOWN
    );

    if (!m_window) {
        std::cerr << "[-] SDL_CreateWindow failed: " << SDL_GetError() << std::endl;
        return false;
    }

    m_renderer = SDL_CreateRenderer(
        m_window,
        -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
    );

    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }

    SDL_RenderSetLogicalSize(m_renderer, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT);

    // Enable high-quality alpha blending for 4IFIR frosted glass effects
    SDL_SetRenderDrawBlendMode(m_renderer, SDL_BLENDMODE_BLEND);

    // Immediately render 4IFIR Cyber-Glass Splash Screen so Switch never shows a black screen during boot!
    renderBootSplash("Инициализация графического ядра 4IFIR...", 20.0);
    loadTabIcons();
#endif

    m_sysInfo = m_platform->getSystemInfo();
    loadAppSettings();
    sanitizeThumbCache();

    renderBootSplash("Загрузка базы каталога видеофонов и иконок...", 50.0);

    // Load initial catalog: automatically prefer newer built-in romfs:/catalog.json over stale SD cache.json!
    std::string catError;
    std::string cachePath = m_platform->getAppDirectory() + "/cache.json";
    bool hasCache = m_catalogManager.loadFromFile(cachePath, catError);
    CatalogManager romfsCat;
    std::string romfsErr;
    bool hasRomfs = romfsCat.loadFromFile("romfs:/catalog.json", romfsErr);
    if (hasRomfs && (!hasCache ||
                     romfsCat.getTotalVariantsCount() > m_catalogManager.getTotalVariantsCount() ||
                     (!romfsCat.getUpdatedAt().empty() && romfsCat.getUpdatedAt() > m_catalogManager.getUpdatedAt()))) {
        m_catalogManager = std::move(romfsCat);
        m_catalogManager.saveToCacheFile(cachePath);
    } else if (!hasCache && !hasRomfs) {
#ifdef H3H_AFTER_DARK
        m_catalogManager.loadFromFile("catalog/data/catalog_after_dark.json", catError);
#else
        m_catalogManager.loadFromFile("catalog/data/catalog.json", catError);
#endif
    }

    renderBootSplash("Сканирование установленных игр Nintendo Switch...", 80.0);

    refreshInstalledGames();
    detectNewInstalledGamesOnBoot();
    runAutoCoverRotationOnBoot();
    rebuildCatalogFilter();

    m_videoIconsCatalog.clear();
    for (const auto& game : m_catalogManager.getAllGames()) {
        std::vector<Variant> uniqueIcons = getUniqueIconVariants(game);
        if (!uniqueIcons.empty()) {
            GameCatalogEntry iconEntry = game;
            iconEntry.variants = std::move(uniqueIcons);
            m_videoIconsCatalog.push_back(std::move(iconEntry));
        }
    }
    rebuildVideoIconsFilter();
    renderBootSplash("Готово! Запуск главного меню...", 100.0);

#ifdef HAS_SDL2

    // Register 1:1 physical Switch button mapping in SDL2 GameController database:
    // Physical Joy-Con / Pro Controller layout:
    // A = Button 0 (East / Right) -> SDL_CONTROLLER_BUTTON_A
    // B = Button 1 (South / Bottom) -> SDL_CONTROLLER_BUTTON_B
    // X = Button 2 (North / Top) -> SDL_CONTROLLER_BUTTON_X
    // Y = Button 3 (West / Left) -> SDL_CONTROLLER_BUTTON_Y
    //
    // By default, devkitPro SDL2 uses Xbox-style layout: a:b1, b:b0, x:b3, y:b2
    // which inverts A <-> B and X <-> Y.
    // Registering 1:1 mappings ensures that physical button A confirms/installs,
    // and physical button B cancels/returns.
    const char* switchGuid = "000038f853776974636820436f6e7400";
    std::string defaultSwitchMapping = std::string(switchGuid) + ",Switch Controller,"
        "a:b0,b:b1,back:b11,dpdown:b15,dpleft:b12,dpright:b14,dpup:b13,"
        "leftshoulder:b6,leftstick:b4,lefttrigger:b8,leftx:a0,lefty:a1,"
        "rightshoulder:b7,rightstick:b5,righttrigger:b9,rightx:a2,righty:a3,"
        "start:b10,x:b2,y:b3,";
    SDL_GameControllerAddMapping(defaultSwitchMapping.c_str());

    for (int i = 0; i < SDL_NumJoysticks(); ++i) {
        SDL_JoystickGUID guid = SDL_JoystickGetDeviceGUID(i);
        char guidStr[64];
        SDL_JoystickGetGUIDString(guid, guidStr, sizeof(guidStr));
        std::string customMapping = std::string(guidStr) + ",Switch Controller,"
            "a:b0,b:b1,back:b11,dpdown:b15,dpleft:b12,dpright:b14,dpup:b13,"
            "leftshoulder:b6,leftstick:b4,lefttrigger:b8,leftx:a0,lefty:a1,"
            "rightshoulder:b7,rightstick:b5,righttrigger:b9,rightx:a2,righty:a3,"
            "start:b10,x:b2,y:b3,";
        SDL_GameControllerAddMapping(customMapping.c_str());
        if (SDL_IsGameController(i)) {
            SDL_GameControllerOpen(i);
        }
    }
#endif

    loadFavorites();
    refreshStorageStats();

    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
    return true;
}

void App::shutdown() {
    saveFavorites();
    saveAppSettings();
    m_cancelQueue.store(true);
    if (m_queueThread.joinable()) {
        m_queueThread.join();
    }
    if (m_catalogThread.joinable()) {
        m_catalogThread.join();
    }
    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }
    if (m_startupUpdateThread.joinable()) {
        m_startupUpdateThread.join();
    }
    m_videoPlayer.close();
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }
    m_cancelCollectionThumb.store(true);
    if (m_collectionThumbThread.joinable()) {
        m_collectionThumbThread.join();
    }
    clearRowThumbTextures();

#ifdef HAS_SDL2
    clearTextCache();
    freeTabIcons();
    if (m_collectionThumbTexture) {
        SDL_DestroyTexture(m_collectionThumbTexture);
        m_collectionThumbTexture = nullptr;
    }
    if (m_videoIconDockTexture) {
        SDL_DestroyTexture(m_videoIconDockTexture);
        m_videoIconDockTexture = nullptr;
    }
    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }
    for (auto& pair : m_fonts) {
        if (pair.second) {
            TTF_CloseFont(pair.second);
        }
    }
    m_fonts.clear();

    if (m_renderer) {
        SDL_DestroyRenderer(m_renderer);
        m_renderer = nullptr;
    }
    if (m_window) {
        SDL_DestroyWindow(m_window);
        m_window = nullptr;
    }
    TTF_Quit();
    IMG_Quit();
    SDL_Quit();
#endif
    if (m_platform) {
        m_platform->shutdown();
    }
}

void App::refreshInstalledGames() {
    m_platform->listInstalledTitles(m_installedGames);
    m_catalogManager.matchInstalledTitles(m_installedGames);

    // In After Dark build, pin the After Dark Collection (0000000000000000) at top if present in catalog
    if (Config::isAfterDark()) {
        const auto* match = m_catalogManager.findByTitleId("0000000000000000");
        if (match && !match->variants.empty()) {
            bool found = false;
            for (const auto& ig : m_installedGames) {
                if (ig.titleId == "0000000000000000") { found = true; break; }
            }
            if (!found) {
                InstalledTitle collTitle;
                collTitle.titleId = "0000000000000000";
                collTitle.name = match->title;
                collTitle.author = match->publisher;
                collTitle.hasCatalogMatch = true;
                collTitle.catalogEntry = *match;
                collTitle.hasInstalledCover = false;
                m_installedGames.insert(m_installedGames.begin(), collTitle);
            }
        }
    }

    // Resolve exact installed variant IDs from persistent registry
    InstalledRegistry::instance().load(m_platform->getAppDirectory());
    for (auto& game : m_installedGames) {
        for (auto& v : game.catalogEntry.variants) {
            bool isPureIcon = (v.id.rfind("icon-", 0) == 0) || (v.width == 256 && v.height == 256);
            if (isPureIcon) {
                if (v.url.empty() && !v.iconUrl.empty()) v.url = v.iconUrl;
                if (v.sizeBytes == 0 && v.iconSizeBytes > 0) v.sizeBytes = v.iconSizeBytes;
                v.width = 256;
                v.height = 256;
            }
        }
        // Check for 4IFIR video icon on SD card (sdmc:/recordings/icons/<TitleID>.mp4)
        std::string iconPath;
        uint64_t iconSize = 0;
        // Refresh multi-cover variants
        game.installedCoverVariants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), game.titleId);
        game.installedCoversCount = static_cast<int>(game.installedCoverVariants.size());
        if (game.installedCoversCount > 0) {
            game.hasInstalledCover = true;
            for (const auto& var : game.installedCoverVariants) {
                if (var.isActive) {
                    game.installedCoverPath = var.filePath;
                    game.installedCoverSizeBytes = var.sizeBytes;
                    break;
                }
            }
            if (game.installedCoverPath.empty()) {
                game.installedCoverPath = game.installedCoverVariants[0].filePath;
                game.installedCoverSizeBytes = game.installedCoverVariants[0].sizeBytes;
            }
            game.status = CoverStatus::Installed;
        }

        if (Installer::findExistingIcon(m_platform->getIconsDirectory(), game.titleId, iconPath, iconSize)) {
            game.hasInstalledIcon = true;
            game.installedIconPath = iconPath;
            game.installedIconSizeBytes = iconSize;
        }
        if (game.hasInstalledCover) {
            std::string regVarId = InstalledRegistry::instance().getVariantId(game.titleId);
            if (!regVarId.empty()) {
                // Trust registry entry explicitly
                game.installedVariantId = regVarId;
                if (regVarId.rfind("local:", 0) == 0) {
                    std::string clipName = regVarId.substr(6);
                    bool hasLocal = false;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.id == regVarId) { hasLocal = true; break; }
                    }
                    if (!hasLocal) {
                        Variant localVar;
                        localVar.id = regVarId;
                        localVar.name = "Запись 4IFIR: " + clipName;
                        localVar.style = CoverStyle::Gameplay;
                        localVar.url = game.installedCoverPath;
                        localVar.previewUrl = game.installedCoverPath;
                        localVar.notes = "Собственный клип из sdmc:/recordings/";
                        game.catalogEntry.variants.insert(game.catalogEntry.variants.begin(), localVar);
                    }
                }
            } else if (!game.catalogEntry.variants.empty()) {
                // If not found in registry (e.g. initial scan of manually dropped files):
                // Only associate automatically if exactly 1 variant exists
                if (game.catalogEntry.variants.size() == 1) {
                    game.installedVariantId = game.catalogEntry.variants[0].id;
                    InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), game.titleId, game.installedVariantId);
                } else {
                    // Check if file size matches uniquely within 4 KB margin
                    int64_t bestDiff = INT64_MAX;
                    std::string bestId;
                    int matchCount = 0;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.sizeBytes > 0 && game.installedCoverSizeBytes > 0) {
                            int64_t diff = std::abs((int64_t)v.sizeBytes - (int64_t)game.installedCoverSizeBytes);
                            if (diff < 4096) {
                                matchCount++;
                                if (diff < bestDiff) {
                                    bestDiff = diff;
                                    bestId = v.id;
                                }
                            }
                        }
                    }
                    if (matchCount == 1 && !bestId.empty()) {
                        game.installedVariantId = bestId;
                        InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), game.titleId, game.installedVariantId);
                    }
                }
            }
        }
    }
    rebuildMyGamesFilter();
}

void App::fetchRemoteCatalog() {
    if (m_isFetchingCatalog.load()) {
        m_statusNotification = (m_language == Language::Russian)
            ? "Каталог уже загружается..."
            : "Catalog download is already in progress...";
        m_notificationFramesRemaining = 90;
        return;
    }

    m_statusNotification = (m_language == Language::Russian)
        ? "Загрузка каталога с GitHub..."
        : "Fetching catalog from GitHub...";
    m_notificationFramesRemaining = 120;
    m_isFetchingCatalog = true;

    if (m_catalogThread.joinable()) {
        m_catalogThread.join();
    }

    m_catalogThread = std::thread([this]() {
        std::string jsonStr;
        std::string err;
        bool ok = m_platform->fetchCatalog(Config::DEFAULT_CATALOG_URL, jsonStr, err);
        {
            std::lock_guard<std::mutex> lock(m_catalogMutex);
            m_fetchedJson = std::move(jsonStr);
            m_fetchError = std::move(err);
            m_fetchSuccess = ok;
        }
        m_catalogFetchDone.store(true);
        m_isFetchingCatalog.store(false);
    });
}

void App::updateApplicationNro() {
    if (m_isUpdatingNro.load()) {
        return;
    }

    m_nroUpdateBytesDownloaded.store(0);
    m_nroUpdateTotalBytes.store(25165824); // ~24 MB expected release size
    m_activeDialog = DialogType::UpdateProgress;
    m_dialogOpenedAt = SDL_GetTicks();
    m_dialogTitle = (m_language == Language::Russian) ? "Проверка обновлений..." : "Checking for updates...";
    m_dialogMessage = (m_language == Language::Russian)
        ? "Связь с GitHub Releases и проверка версии..."
        : "Checking latest version on GitHub...";
    m_isUpdatingNro = true;

    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }

    m_nroUpdateThread = std::thread([this]() {
        // Step 1: Check remote version without downloading NRO (with cache-buster query)
        std::string versionJsonStr;
        std::string checkErr;
        std::string checkUrl = std::string(Config::VERSION_CHECK_URL) + "?t=" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
        bool checkOk = m_platform->fetchCatalog(checkUrl, versionJsonStr, checkErr);

        std::string latestVer = Config::APP_VERSION;
        std::string releaseNotes = "Пакет обновлений H3H Backgrounds";
        if (checkOk && !versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
                if (vJson.contains("latestVersion")) {
                    latestVer = vJson["latestVersion"].get<std::string>();
                }
                if (vJson.contains("releaseNotes")) {
                    releaseNotes = vJson["releaseNotes"].get<std::string>();
                }
            } catch (...) {}
        }

        auto isSemverGreater = [](const std::string& cand, const std::string& cur) -> bool {
            auto parseParts = [](const std::string& v) {
                std::vector<int> parts;
                int val = 0;
                bool hasDigit = false;
                for (char c : v) {
                    if (c >= '0' && c <= '9') {
                        val = val * 10 + (c - '0');
                        hasDigit = true;
                    } else if (c == '.') {
                        parts.push_back(val);
                        val = 0;
                        hasDigit = false;
                    }
                }
                if (hasDigit || !parts.empty()) parts.push_back(val);
                while (parts.size() < 3) parts.push_back(0);
                return parts;
            };
            return parseParts(cand) > parseParts(cur);
        };

        // If current version is already up to date (or newer local dev build), skip download completely
        if (!isSemverGreater(latestVer, Config::APP_VERSION)) {
            {
                std::lock_guard<std::mutex> lock(m_nroMutex);
                m_nroUpdateError = "ALREADY_UP_TO_DATE";
                m_nroUpdateSuccess = false;
            }
            m_nroUpdateDone.store(true);
            m_isUpdatingNro.store(false);
            return;
        }

        // Step 2: New version found -> download and install
#ifdef H3H_AFTER_DARK
        std::string nroFileName = "H3H-AfterDark.nro";
        std::string defaultNroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-AfterDark.nro";
        std::string targetSubdir = "H3H-AfterDark";
#else
        std::string nroFileName = "H3H-Backgrounds.nro";
        std::string defaultNroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string targetSubdir = "H3H-Backgrounds";
#endif

        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            m_nroUpdateLatestVer = latestVer;
        }

        std::string nroUrl = defaultNroUrl;
        if (!versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
#ifdef H3H_AFTER_DARK
                if (vJson.contains("afterDarkDownloadUrl")) {
                    nroUrl = vJson["afterDarkDownloadUrl"].get<std::string>();
                }
#else
                if (vJson.contains("downloadUrl")) {
                    nroUrl = vJson["downloadUrl"].get<std::string>();
                }
#endif
            } catch (...) {}
        }

        // Determine exact destination on MicroSD
        std::string targetNro = m_runningNroPath;
        if (targetNro.empty()) {
            std::string appDir = m_platform->getAppDirectory();
            targetNro = appDir + "/" + nroFileName;
        }

        // Ensure target directory exists
        {
            std::error_code ec;
            std::filesystem::create_directories(std::filesystem::path(targetNro).parent_path(), ec);
        }

        // Temporary download and backup paths in the EXACT same directory to guarantee atomic operations
        std::string tempNro = targetNro + ".new";
        std::string bakNro  = targetNro + ".bak";

        std::atomic<bool> cancel{false};
        std::string err;
        auto progressCb = [this](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
            (void)speedBps;
            m_nroUpdateBytesDownloaded.store(bytesDownloaded);
            if (totalBytes > 0) m_nroUpdateTotalBytes.store(totalBytes);
        };

        // Remove any stale temp download before starting
        std::remove(tempNro.c_str());

        bool ok = m_platform->downloadFile(nroUrl, tempNro, progressCb, cancel, err);
        bool success = false;

        if (ok) {
            // CRITICAL STEP: Integrity Verification before touching existing binary
            bool validNro = false;
            FILE* fp = fopen(tempNro.c_str(), "rb");
            if (fp) {
                fseek(fp, 0, SEEK_END);
                long fsize = ftell(fp);
                // Minimum size for valid H3H NRO with FFmpeg is 15 MB
                if (fsize >= 15 * 1024 * 1024) {
                    fseek(fp, 0x10, SEEK_SET);
                    char magic[4] = {0};
                    if (fread(magic, 1, 4, fp) == 4) {
                        if (magic[0] == 'N' && magic[1] == 'R' && magic[2] == 'O' && magic[3] == '0') {
                            validNro = true;
                        }
                    }
                }
                fclose(fp);
            }

            if (!validNro) {
                std::remove(tempNro.c_str());
                err = (m_language == Language::Russian)
                    ? "Ошибка проверки целостности: загруженный файл поврежден или неполон"
                    : "Integrity check failed: downloaded NRO is incomplete or corrupted";
            } else {
                // Release RomFS so devoptab closes internal handle to argv[0]
                m_platform->releaseRomfs();

                // Safe swap:
                // 1. Rename existing running NRO to .bak
                std::remove(bakNro.c_str());
                std::rename(targetNro.c_str(), bakNro.c_str());

                // 2. Rename .new to targetNro
                if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                    // Success! Remove backup
                    std::remove(bakNro.c_str());
                    success = true;
                } else {
                    // Rename failed (e.g. locked). Try chunked C stream copy
                    FILE* fsrc = fopen(tempNro.c_str(), "rb");
                    FILE* fdst = fopen(targetNro.c_str(), "wb");
                    if (fsrc && fdst) {
                        std::vector<char> buf(64 * 1024);
                        size_t bytesRead;
                        bool copyOk = true;
                        while ((bytesRead = fread(buf.data(), 1, buf.size(), fsrc)) > 0) {
                            if (fwrite(buf.data(), 1, bytesRead, fdst) != bytesRead) {
                                copyOk = false;
                                break;
                            }
                        }
                        fflush(fdst);
                        fclose(fdst);
                        fclose(fsrc);
                        if (copyOk) {
                            std::remove(tempNro.c_str());
                            std::remove(bakNro.c_str());
                            success = true;
                        }
                    } else {
                        if (fsrc) fclose(fsrc);
                        if (fdst) fclose(fdst);
                    }

                    if (!success) {
                        // Rollback from backup! Target is guaranteed intact!
                        std::remove(targetNro.c_str());
                        std::rename(bakNro.c_str(), targetNro.c_str());
                        std::remove(tempNro.c_str());
                        err = "Failed to swap NRO on MicroSD (original preserved)";
                    }
                }
            }
        }

        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            m_nroUpdateError = std::move(err);
            m_nroUpdateSuccess = success;
        }
        m_nroUpdateDone.store(true);
        m_isUpdatingNro.store(false);
    });
}

void App::update() {
#ifdef HAS_SDL2
    uint32_t currentTicks = SDL_GetTicks();
    float timeMs = static_cast<float>(currentTicks);

    // 1. Smooth 60 FPS spring-lerp tile scale for Home Dashboard
    for (int i = 0; i < 5; ++i) {
        float targetScale = (m_homeFocusedTile == i) ? 1.055f : 1.0f;
        m_tileAnimScale[i] += (targetScale - m_tileAnimScale[i]) * 0.22f;
    }

    // 2. Continuous idle animation parameters
    m_gearAngle += 0.025f;
    if (m_gearAngle > 6.2831853f) m_gearAngle -= 6.2831853f;

    m_downloadArrowBob = std::sin(timeMs * 0.006f) * 3.5f;

    // 3. Header Equalizer bars animation (smooth audio wave visualizer)
    m_equalizerHeights[0] = 16.0f + 6.0f * std::sin(timeMs * 0.005f);
    m_equalizerHeights[1] = 22.0f + 8.0f * std::sin(timeMs * 0.007f + 1.2f);
    m_equalizerHeights[2] = 14.0f + 5.0f * std::sin(timeMs * 0.006f + 2.4f);

    // 4. Subtle cyber-glow breathing pulse
    m_glowPulse = 0.82f + 0.18f * std::sin(timeMs * 0.005f);

    // 5. Button click bounce decay
    if (m_buttonPressAnim > 0.01f) {
        m_buttonPressAnim *= 0.78f;
    } else {
        m_buttonPressAnim = 0.0f;
    }

    // 6. Smooth tab transition alpha fade-in
    if (m_tabTransitionAlpha < 255.0f) {
        m_tabTransitionAlpha = std::min(255.0f, m_tabTransitionAlpha + 24.0f);
    }

    // 7. Continuous spinner rotation & fullscreen preview fade-in
    m_spinnerAngle += 0.12f;
    if (m_spinnerAngle > 6.2831853f) m_spinnerAngle -= 6.2831853f;
    if ((m_isFullscreenPreview || m_isCollectionBrowserOpen || m_activeTab == Tab::VideoIcons || m_activeTab == Tab::Catalog) &&
        (m_videoPlayer.isPlaying() || m_previewTexture != nullptr || m_collectionThumbTexture != nullptr || m_videoIconDockTexture != nullptr)) {
        m_previewFadeAlpha += (255.0f - m_previewFadeAlpha) * 0.20f;
    }

    // 8. Smooth 60 FPS list selection Y-interpolation across all tabs
    float catBaseY = m_linkingTargetTitleId.empty() ? 134.0f : 158.0f;
    float targetCatY = catBaseY + static_cast<float>(std::clamp(m_catalogSelectedIndex - m_catalogScrollOffset, 0, 4)) * 96.0f;
    m_smoothCatalogSelY += (targetCatY - m_smoothCatalogSelY) * 0.30f;

    float targetIcoY = 136.0f + static_cast<float>(std::clamp(m_videoIconsSelectedIndex - m_videoIconsScrollOffset, 0, 4)) * 98.0f;
    m_smoothVideoIconsSelY += (targetIcoY - m_smoothVideoIconsSelY) * 0.30f;

    float targetMyGamesY = 122.0f + static_cast<float>(std::clamp(m_myGamesSelectedIndex - m_myGamesScrollOffset, 0, 6)) * 66.0f;
    m_smoothMyGamesSelY += (targetMyGamesY - m_smoothMyGamesSelY) * 0.30f;

    float targetDlY = 160.0f + static_cast<float>(std::clamp(m_downloadsSelectedIndex - m_downloadsScrollOffset, 0, 4)) * 94.0f;
    m_smoothDownloadsSelY += (targetDlY - m_smoothDownloadsSelY) * 0.30f;

    float targetSettingsY = 232.0f + static_cast<float>(std::clamp(m_settingsSelectedIndex, 0, 7)) * 47.0f;
    m_smoothSettingsSelY += (targetSettingsY - m_smoothSettingsSelY) * 0.30f;

    // 9. Update non-blocking preview workers & 70x70 row mini-thumbnails prefetcher
    updateAsyncPreviewWorkers();
    updateRowThumbPrefetcher();

    // 10. Debounced non-blocking preview trigger for Collection Browser & VideoIcons Live Dock (fast 60ms response)
    if (m_isCollectionBrowserOpen && m_collectionPreviewDirty && !m_isFullscreenPreview) {
        if (currentTicks - m_lastCollectionMoveTime >= 60) {
            m_collectionPreviewDirty = false;
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < static_cast<int>(m_collectionVariants.size())) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
        }
    }
    if (m_activeTab == Tab::VideoIcons && !m_isFullscreenPreview && !m_isCollectionBrowserOpen) {
        if (!m_filteredVideoIcons.empty() && m_videoIconsSelectedIndex >= 0 &&
            m_videoIconsSelectedIndex < static_cast<int>(m_filteredVideoIcons.size())) {
            const auto& curEntry = m_filteredVideoIcons[m_videoIconsSelectedIndex];
            if (!curEntry.variants.empty()) {
                int vIdx = getSelectedVideoIconVariantIndex(curEntry);
                const auto& curVar = curEntry.variants[vIdx];
                std::string wantKey = "icon_" + curEntry.titleId + "_" + curVar.id;
                if (m_videoIconDockCurrentKey != wantKey) {
                    m_videoIconDockDirty = true;
                }
                if (m_videoIconDockDirty && (currentTicks - m_lastVideoIconMoveTime >= 60)) {
                    m_videoIconDockDirty = false;
                    loadVideoIconDockPreview(curEntry, curVar);
                }
            }
        }
    }
    if (m_activeTab == Tab::Catalog && !m_isFullscreenPreview && !m_isCollectionBrowserOpen) {
        if (!m_filteredCatalogGames.empty() && m_catalogSelectedIndex >= 0 &&
            m_catalogSelectedIndex < static_cast<int>(m_filteredCatalogGames.size())) {
            const auto& curEntry = m_filteredCatalogGames[m_catalogSelectedIndex];
            auto covVars = getCoverVariants(curEntry);
            if (!covVars.empty()) {
                int vIdx = std::clamp(getSelectedCatalogVariantIndex(curEntry), 0, static_cast<int>(covVars.size()) - 1);
                const auto& curVar = covVars[vIdx];
                std::string wantKey = "catdock_" + curEntry.titleId + "_" + curVar.id;
                if (m_catalogDockCurrentKey != wantKey) {
                    m_catalogDockDirty = true;
                }
                if (m_catalogDockDirty && (currentTicks - m_lastCatalogMoveTime >= 110)) {
                    m_catalogDockDirty = false;
                    loadCatalogDockPreview(curEntry, curVar);
                }
            }
        }
    }

    std::string previewPath;
    std::string vidPath;
    {
        std::lock_guard<std::mutex> lock(m_previewMutex);
        if (!m_pendingPreviewFileToLoad.empty()) {
            previewPath = m_pendingPreviewFileToLoad;
            m_pendingPreviewFileToLoad.clear();
        }
        if (!m_pendingVideoToOpen.empty()) {
            vidPath = m_pendingVideoToOpen;
            m_pendingVideoToOpen.clear();
        }
    }
    std::string pendingCollThumb;
    std::string pendingCollVideo;
    std::string pendingDockThumb;
    std::string pendingDockVideo;
    {
        std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
        pendingCollThumb = std::move(m_pendingCollectionThumbToLoad);
        m_pendingCollectionThumbToLoad.clear();
        pendingCollVideo = std::move(m_pendingCollectionVideoToOpen);
        m_pendingCollectionVideoToOpen.clear();
        pendingDockThumb = std::move(m_pendingVideoIconDockThumb);
        m_pendingVideoIconDockThumb.clear();
        pendingDockVideo = std::move(m_pendingVideoIconDockVideo);
        m_pendingVideoIconDockVideo.clear();
    }
    if (!pendingCollThumb.empty() && m_renderer && m_isCollectionBrowserOpen) {
        if (validateImageFile(pendingCollThumb)) {
            SDL_Texture* newTex = loadTextureFromFile(m_renderer, pendingCollThumb);
            if (newTex) {
                if (m_collectionThumbTexture) SDL_DestroyTexture(m_collectionThumbTexture);
                m_collectionThumbTexture = newTex;
            } else {
                std::error_code ec;
                std::filesystem::remove(pendingCollThumb, ec);
            }
        } else {
            std::error_code ec;
            std::filesystem::remove(pendingCollThumb, ec);
        }
    }
    if (!pendingCollVideo.empty() && m_renderer && m_isCollectionBrowserOpen && !m_isFullscreenPreview) {
        if (!m_videoPlayer.open(pendingCollVideo, m_renderer)) {
            std::error_code ec;
            std::filesystem::remove(pendingCollVideo, ec);
        }
    }
    if (!pendingDockThumb.empty() && m_renderer && (m_activeTab == Tab::VideoIcons || m_activeTab == Tab::Catalog)) {
        if (validateImageFile(pendingDockThumb)) {
            SDL_Texture* newTex = loadTextureFromFile(m_renderer, pendingDockThumb);
            if (newTex) {
                if (m_videoIconDockTexture) SDL_DestroyTexture(m_videoIconDockTexture);
                m_videoIconDockTexture = newTex;
            } else {
                std::error_code ec;
                std::filesystem::remove(pendingDockThumb, ec);
            }
        } else {
            std::error_code ec;
            std::filesystem::remove(pendingDockThumb, ec);
        }
    }
    if (!pendingDockVideo.empty() && m_renderer && (m_activeTab == Tab::VideoIcons || m_activeTab == Tab::Catalog) && !m_isFullscreenPreview && !m_isCollectionBrowserOpen) {
        if (!m_videoPlayer.open(pendingDockVideo, m_renderer)) {
            std::error_code ec;
            std::filesystem::remove(pendingDockVideo, ec);
        }
    }
    if (!previewPath.empty() && m_renderer) {
        if (validateImageFile(previewPath)) {
            SDL_Texture* newTex = loadTextureFromFile(m_renderer, previewPath);
            if (newTex) {
                if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
                m_previewTexture = newTex;
            } else {
                std::error_code ec;
                std::filesystem::remove(previewPath, ec);
            }
        } else {
            std::error_code ec;
            std::filesystem::remove(previewPath, ec);
        }
    }
    if (!vidPath.empty() && m_renderer && m_isFullscreenPreview) {
        if (!m_videoPlayer.open(vidPath, m_renderer)) {
            // Failed to open -> remove corrupted cache file so it won't hang on black screen
            std::error_code ec;
            std::filesystem::remove(vidPath, ec);
        }
    }
    if ((m_isFullscreenPreview || m_isCollectionBrowserOpen || m_activeTab == Tab::VideoIcons || m_activeTab == Tab::Catalog) && m_videoPlayer.isPlaying()) {
        m_videoPlayer.update();
    }
#endif
    // Process background catalog fetch result safely on the main thread
    if (m_catalogFetchDone.exchange(false)) {
        std::string jsonStr;
        std::string err;
        bool ok = false;
        {
            std::lock_guard<std::mutex> lock(m_catalogMutex);
            jsonStr = std::move(m_fetchedJson);
            err = std::move(m_fetchError);
            ok = m_fetchSuccess;
        }
        if (m_catalogThread.joinable()) {
            m_catalogThread.join();
        }

        if (ok && !jsonStr.empty()) {
            std::string parseErr;
            if (m_catalogManager.loadFromJsonString(jsonStr, parseErr)) {
                m_catalogManager.saveToCacheFile(m_platform->getAppDirectory() + "/cache.json");
                refreshInstalledGames();
                rebuildCatalogFilter();

                m_videoIconsCatalog.clear();
                for (const auto& game : m_catalogManager.getAllGames()) {
                    std::vector<Variant> uniqueIcons = getUniqueIconVariants(game);
                    if (!uniqueIcons.empty()) {
                        GameCatalogEntry iconEntry = game;
                        iconEntry.variants = std::move(uniqueIcons);
                        m_videoIconsCatalog.push_back(std::move(iconEntry));
                    }
                }
                rebuildVideoIconsFilter();
                m_statusNotification = (m_language == Language::Russian)
                    ? ("Каталог успешно обновлён (" + std::to_string(m_catalogManager.getGamesCount()) + " игр)")
                    : ("Catalog updated successfully (" + std::to_string(m_catalogManager.getGamesCount()) + " games)");
                m_notificationFramesRemaining = 180;
            } else {
                m_statusNotification = (m_language == Language::Russian)
                    ? ("Ошибка структуры каталога: " + parseErr)
                    : ("Catalog schema error: " + parseErr);
                m_notificationFramesRemaining = 240;
            }
        } else {
            m_statusNotification = (m_language == Language::Russian)
                ? ("Ошибка сети: " + err)
                : ("Network error: " + err);
            m_notificationFramesRemaining = 240;
        }
    }

    // Proactive background update check after UI has settled (after 2 seconds)
    if (!m_startupUpdateChecked && SDL_GetTicks() > 2000) {
        m_startupUpdateChecked = true;
        if (!m_isCheckingUpdateStartup.load() && !m_isUpdatingNro.load()) {
            m_isCheckingUpdateStartup.store(true);
            if (m_startupUpdateThread.joinable()) {
                m_startupUpdateThread.join();
            }
            m_startupUpdateThread = std::thread([this]() {
                std::string versionJsonStr;
                std::string checkErr;
                std::string checkUrl = std::string(Config::VERSION_CHECK_URL) + "?t=" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
                bool checkOk = m_platform->fetchCatalog(checkUrl, versionJsonStr, checkErr);

                if (checkOk && !versionJsonStr.empty()) {
                    try {
                        auto vJson = nlohmann::json::parse(versionJsonStr);
                        if (vJson.contains("latestVersion")) {
                            std::string latestVer = vJson["latestVersion"].get<std::string>();
                            auto parseSem = [](const std::string& v) {
                                std::vector<int> p;
                                int val = 0;
                                bool hd = false;
                                for (char c : v) {
                                    if (c >= '0' && c <= '9') { val = val * 10 + (c - '0'); hd = true; }
                                    else if (c == '.') { p.push_back(val); val = 0; hd = false; }
                                }
                                if (hd || !p.empty()) p.push_back(val);
                                while (p.size() < 3) p.push_back(0);
                                return p;
                            };
                            if (parseSem(latestVer) > parseSem(Config::APP_VERSION)) {
                                std::string relNotes = "Вышла новая версия приложения с улучшениями и исправлениями.";
                                if (vJson.contains("releaseNotes")) {
                                    relNotes = vJson["releaseNotes"].get<std::string>();
                                }
                                std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
                                m_startupUpdateLatestVer = latestVer;
                                m_startupUpdateReleaseNotes = relNotes;
                            }
                        }
                    } catch (...) {}
                }
                m_startupUpdateDone.store(true);
                m_isCheckingUpdateStartup.store(false);
            });
        }
    }

    if (m_startupUpdateDone.exchange(false)) {
        if (m_startupUpdateThread.joinable()) {
            m_startupUpdateThread.join();
        }
        std::string newVer;
        std::string notes;
        {
            std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
            newVer = std::move(m_startupUpdateLatestVer);
            notes = std::move(m_startupUpdateReleaseNotes);
        }
        if (!newVer.empty()) {
            m_activeDialog = DialogType::UpdateAvailable;
            m_dialogOpenedAt = SDL_GetTicks();
            m_dialogTitle = (m_language == Language::Russian)
                ? ("Доступно обновление v" + newVer)
                : ("Update Available v" + newVer);
            m_dialogMessage = (m_language == Language::Russian)
                ? ("Вышла новая версия H3H-Backgrounds v" + newVer + ":\n\n" + (notes.empty() ? "Рекомендуется обновить приложение." : notes) + "\n\nОбновить приложение сейчас?")
                : ("New version H3H-Backgrounds v" + newVer + " is available:\n\n" + notes + "\n\nDo you want to update now?");
            m_dialogFocus = 0; // Default focus on 'Да, обновить'
        }
    }

    // Process background NRO update result safely on the main thread
    if (m_nroUpdateDone.exchange(false)) {
        std::string err;
        bool ok = false;
        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            err = std::move(m_nroUpdateError);
            ok = m_nroUpdateSuccess;
        }
        if (m_nroUpdateThread.joinable()) {
            m_nroUpdateThread.join();
        }

        if (ok) {
            m_activeDialog = DialogType::UpdateSuccess;
    m_dialogOpenedAt = SDL_GetTicks();
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление завершено!" : "Update Complete!";
            m_dialogMessage = (m_language == Language::Russian)
                ? "Приложение H3H-Backgrounds.nro успешно обновлено до актуальной версии!\nНажмите [A], чтобы перезапустить сейчас, или [B] для продолжения."
                : "H3H-Backgrounds.nro updated successfully!\nPress [A] to restart now, or [B] to continue.";
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Приложение обновлено!" : "Updated!";
        } else if (err == "ALREADY_UP_TO_DATE") {
            m_activeDialog = DialogType::MessageAlert;
    m_dialogOpenedAt = SDL_GetTicks();
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление не требуется" : "Up to date";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("У вас уже установлена актуальная версия:\nH3H-Backgrounds v" + std::string(Config::APP_VERSION) + ".\nНовых версий на сервере не найдено.")
                : ("You are already running the latest version:\nv" + std::string(Config::APP_VERSION) + ".");
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Установлена последняя версия" : "Up to date";
        } else {
            m_activeDialog = DialogType::MessageAlert;
    m_dialogOpenedAt = SDL_GetTicks();
            m_dialogTitle = (m_language == Language::Russian) ? "Ошибка обновления" : "Update Error";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("Не удалось проверить или применить обновление: " + err)
                : ("Failed to apply update: " + err);
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? ("Ошибка: " + err) : ("Error: " + err);
        }
        m_notificationFramesRemaining = 240;
    }

    // Process background queue task completion
    if (m_queueTaskFinished.exchange(false)) {
        // Immediately sync completed tasks into in-memory m_installedGames for instant UI responsiveness
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            for (const auto& task : m_downloadQueue) {
                if (task.state == TaskState::Completed) {
                    for (auto& game : m_installedGames) {
                        if (Config::normalizeTitleId(game.titleId) == Config::normalizeTitleId(task.titleId)) {
                            if (task.iconOnly) {
                                game.hasInstalledIcon = true;
                                game.installedIconPath = task.targetFilePath;
                                game.installedIconSizeBytes = task.totalBytes;
                            } else {
                                game.hasInstalledCover = true;
                                game.installedVariantId = task.variant.id;
                                game.installedCoverPath = task.targetFilePath;
                                game.installedCoverSizeBytes = task.variant.sizeBytes;
                                game.status = CoverStatus::Installed;
                            }
                        }
                    }
                }
            }
        }
        refreshInstalledGames();
        rebuildVideoIconsFilter();
    }

    // Process next pending download task in background
    if (!m_isProcessingQueue.load()) {
        if (m_queueThread.joinable()) {
            m_queueThread.join();
        }

        int nextPendingIdx = -1;
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            for (size_t i = 0; i < m_downloadQueue.size(); ++i) {
                if (m_downloadQueue[i].state == TaskState::Pending) {
                    nextPendingIdx = static_cast<int>(i);
                    break;
                }
            }
        }

        if (nextPendingIdx != -1) {
            m_isProcessingQueue.store(true);
            m_queueThread = std::thread([this, nextPendingIdx]() {
                processSingleDownloadTask(nextPendingIdx);
            });
        }
    }
}

int App::getMissingCoversCount() const {
    int count = 0;
    for (const auto& g : m_installedGames) {
        if (!g.hasInstalledCover && g.hasCatalogMatch && !getCoverVariants(g.catalogEntry).empty()) {
            bool alreadyInQueue = false;
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                for (const auto& task : m_downloadQueue) {
                    if (task.titleId == g.titleId && !task.iconOnly && task.state != TaskState::Failed) {
                        alreadyInQueue = true;
                        break;
                    }
                }
            }
            if (!alreadyInQueue) {
                count++;
            }
        }
    }
    return count;
}

void App::installAllMissing() {
    int missing = getMissingCoversCount();
    if (missing == 0) {
        m_statusNotification = (m_language == Language::Russian)
            ? "Все доступные видеофоны уже установлены или находятся в очереди!"
            : "All available video covers are already installed or in queue!";
        m_notificationFramesRemaining = 180;
        return;
    }

    m_activeDialog = DialogType::ConfirmInstallAll;
    m_dialogOpenedAt = SDL_GetTicks();
    m_dialogTitle = (m_language == Language::Russian)
        ? "Установка всех недостающих"
        : "Install All Missing Covers";
    m_dialogMessage = (m_language == Language::Russian)
        ? ("Найдено игр без видеофона: " + std::to_string(missing) + ".\nЗагрузить и установить видеофоны для всех?")
        : ("Found " + std::to_string(missing) + " games without covers.\nDownload and install covers for all?");
    m_dialogFocus = 0;
}

void App::processSingleDownloadTask(int taskIdx) {
    DownloadTask currentTask;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        if (taskIdx < 0 || taskIdx >= static_cast<int>(m_downloadQueue.size())) {
            m_isProcessingQueue.store(false);
            return;
        }
        m_downloadQueue[taskIdx].state = TaskState::Downloading;
        currentTask = m_downloadQueue[taskIdx];
    }

    // Standalone Video Icon Task Handler
    if (currentTask.iconOnly) {
        SystemInfo sysStorage = m_platform->getSystemInfo();
        uint64_t neededIconBytes = (currentTask.variant.iconSizeBytes > 0 ? currentTask.variant.iconSizeBytes : 500 * 1024) + Config::STORAGE_SAFETY_BUFFER_BYTES;
        if (sysStorage.freeStorageBytes > 0 && sysStorage.freeStorageBytes < neededIconBytes) {
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                    m_downloadQueue[taskIdx].state = TaskState::Failed;
                    m_downloadQueue[taskIdx].errorMessage = "Недостаточно места на MicroSD";
                }
            }
            m_queueTaskFinished.store(true);
            m_isProcessingQueue.store(false);
            return;
        }

        std::string err;
        auto progressCb = [this, taskIdx](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                m_downloadQueue[taskIdx].bytesDownloaded = bytesDownloaded;
                if (totalBytes > 0) {
                    m_downloadQueue[taskIdx].totalBytes = totalBytes;
                    m_downloadQueue[taskIdx].progressPercent = (static_cast<double>(bytesDownloaded) / totalBytes) * 100.0;
                }
                m_downloadQueue[taskIdx].downloadSpeedBps = speedBps;
            }
        };

        bool ok = m_platform->downloadFile(
            currentTask.variant.iconUrl,
            currentTask.tempFilePath,
            progressCb,
            m_cancelQueue,
            err
        );

        if (!ok) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                m_downloadQueue[taskIdx].state = TaskState::Failed;
                m_downloadQueue[taskIdx].errorMessage = err;
            }
            m_queueTaskFinished.store(true);
            m_isProcessingQueue.store(false);
            return;
        }

        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                m_downloadQueue[taskIdx].state = TaskState::Verifying;
            }
        }

        InstallResult res = Installer::installIcon(
            m_platform->getIconsDirectory(),
            currentTask.titleId,
            currentTask.tempFilePath,
            currentTask.variant.iconSizeBytes,
            true
        );

        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                if (res.success) {
                    m_downloadQueue[taskIdx].state = TaskState::Completed;
                    m_downloadQueue[taskIdx].progressPercent = 100.0;
                } else {
                    m_downloadQueue[taskIdx].state = TaskState::Failed;
                    m_downloadQueue[taskIdx].errorMessage = res.message;
                }
            }
        }

        m_queueTaskFinished.store(true);
        m_isProcessingQueue.store(false);
        return;
    }

    // Safety check: ensure MicroSD has sufficient free storage space + safety buffer
    SystemInfo sysStorage = m_platform->getSystemInfo();
    if (sysStorage.freeStorageBytes > 0 && currentTask.variant.sizeBytes > 0) {
        if (sysStorage.freeStorageBytes < currentTask.variant.sizeBytes + Config::STORAGE_SAFETY_BUFFER_BYTES) {
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                    m_downloadQueue[taskIdx].state = TaskState::Failed;
                    m_downloadQueue[taskIdx].errorMessage = "Недостаточно места на MicroSD (резерв 20 MB)";
                }
            }
            m_queueTaskFinished.store(true);
            m_isProcessingQueue.store(false);
            return;
        }
    }

    std::string err;
    auto progressCb = [this, taskIdx](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
            m_downloadQueue[taskIdx].bytesDownloaded = bytesDownloaded;
            if (totalBytes > 0) {
                m_downloadQueue[taskIdx].totalBytes = totalBytes;
                m_downloadQueue[taskIdx].progressPercent = (static_cast<double>(bytesDownloaded) / totalBytes) * 100.0;
            }
            m_downloadQueue[taskIdx].downloadSpeedBps = speedBps;
        }
    };

    bool ok = m_platform->downloadFile(
        currentTask.variant.url,
        currentTask.tempFilePath,
        progressCb,
        m_cancelQueue,
        err
    );

    if (!ok) {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
            m_downloadQueue[taskIdx].state = TaskState::Failed;
            m_downloadQueue[taskIdx].errorMessage = err;
        }
        m_queueTaskFinished.store(true);
        m_isProcessingQueue.store(false);
        return;
    }

    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
            m_downloadQueue[taskIdx].state = TaskState::Verifying;
        }
    }

    InstallResult res = Installer::installVariant(
        m_platform->getCoversDirectory(),
        currentTask.titleId,
        currentTask.tempFilePath,
        currentTask.variant.sha256,
        currentTask.variant.sizeBytes,
        true,
        !currentTask.appendAsNewSlot
    );

    // If variant includes a 4IFIR video icon (and coverOnly is false), download and install it as well
    if (res.success && !currentTask.coverOnly && currentTask.variant.hasIcon && !currentTask.variant.iconUrl.empty()) {
        std::string tempIconPath = m_platform->getIconsDirectory() + "/" + Config::getTempIconFileName(currentTask.titleId);
        std::string iconErr;
        bool iconDownloaded = m_platform->downloadFile(
            currentTask.variant.iconUrl,
            tempIconPath,
            nullptr,
            m_cancelQueue,
            iconErr
        );
        if (iconDownloaded) {
            Installer::installIcon(
                m_platform->getIconsDirectory(),
                currentTask.titleId,
                tempIconPath,
                currentTask.variant.iconSizeBytes,
                true
            );
        }
    }

    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
            if (res.success) {
                if (!currentTask.appendAsNewSlot) {
                    InstalledRegistry::instance().setVariantId(
                        m_platform->getAppDirectory(),
                        currentTask.titleId,
                        currentTask.variant.id
                    );
                }
                m_downloadQueue[taskIdx].state = TaskState::Completed;
                m_downloadQueue[taskIdx].progressPercent = 100.0;
            } else {
                m_downloadQueue[taskIdx].state = TaskState::Failed;
                m_downloadQueue[taskIdx].errorMessage = res.message;
            }
        }
    }

    m_queueTaskFinished.store(true);
    m_isProcessingQueue.store(false);
}

void App::queueDownloadIconOnly(const InstalledTitle& title, const Variant& variant) {
    if (!variant.hasIcon || variant.iconUrl.empty()) {
        m_statusNotification = (m_language == Language::Russian)
            ? "У этого варианта нет видеоиконки"
            : "This variant has no video icon";
        m_notificationFramesRemaining = 180;
        return;
    }

    DownloadTask task;
    task.id = title.titleId + "_" + variant.id + "_icon";
    task.titleId = title.titleId;
    task.gameTitle = title.name;
    task.variant = variant;
    task.variant.iconUrl = variant.iconUrl.empty() ? variant.url : variant.iconUrl;
    task.iconOnly = true;
    task.coverOnly = false;
    task.tempFilePath = m_platform->getIconsDirectory() + "/" + Config::getTempIconFileName(title.titleId);
    task.targetFilePath = m_platform->getIconsDirectory() + "/" + Config::getTargetIconFileName(title.titleId);
    task.backupFilePath = m_platform->getIconsDirectory() + "/" + Config::getBackupIconFileName(title.titleId);
    task.state = TaskState::Pending;
    task.totalBytes = (variant.iconSizeBytes > 0) ? variant.iconSizeBytes : 350 * 1024;

    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        m_downloadQueue.push_back(std::move(task));
    }
    m_statusNotification = (m_language == Language::Russian)
        ? ("В очередь: Иконка " + title.name + " (" + variant.name + ")")
        : ("Added to queue: Icon " + title.name + " (" + variant.name + ")");
    m_notificationFramesRemaining = 180;
}

void App::queueDownloadCoverOnly(const InstalledTitle& title, const Variant& variant) {
    DownloadTask task;
    task.id = title.titleId + "_" + variant.id + "_cover";
    task.titleId = title.titleId;
    task.gameTitle = title.name;
    task.variant = variant;
    task.iconOnly = false;
    task.coverOnly = true;
    task.tempFilePath = m_platform->getCoversDirectory() + "/" + Config::getTempCoverFileName(title.titleId);
    task.targetFilePath = m_platform->getCoversDirectory() + "/" + Config::getTargetCoverFileName(title.titleId);
    task.backupFilePath = m_platform->getCoversDirectory() + "/" + Config::getBackupCoverFileName(title.titleId);
    task.state = TaskState::Pending;
    task.totalBytes = variant.sizeBytes;

    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        m_downloadQueue.push_back(std::move(task));
    }
    m_statusNotification = (m_language == Language::Russian)
        ? ("В очередь: Только фон " + title.name + " (" + variant.name + ")")
        : ("Added to queue: Cover only " + title.name + " (" + variant.name + ")");
    m_notificationFramesRemaining = 180;
}

void App::executeDeleteIcon(const std::string& titleId) {
    bool deleted = Installer::deleteIcon(m_platform->getIconsDirectory(), titleId);
    if (deleted) {
        m_statusNotification = (m_language == Language::Russian)
            ? "Видеоиконка 4IFIR успешно удалена"
            : "4IFIR video icon deleted";
    } else {
        m_statusNotification = (m_language == Language::Russian)
            ? "Видеоиконка не найдена"
            : "Video icon not found";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
    rebuildVideoIconsFilter();
}

void App::queueDownload(const InstalledTitle& title, const Variant& variant) {
    DownloadTask task;
    task.id = title.titleId + "_" + variant.id;
    task.titleId = title.titleId;
    task.gameTitle = title.name;
    task.variant = variant;
    task.tempFilePath = m_platform->getCoversDirectory() + "/" + Config::getTempCoverFileName(title.titleId);
    task.targetFilePath = m_platform->getCoversDirectory() + "/" + Config::getTargetCoverFileName(title.titleId);
    task.backupFilePath = m_platform->getCoversDirectory() + "/" + Config::getBackupCoverFileName(title.titleId);
    task.state = TaskState::Pending;
    task.totalBytes = variant.sizeBytes;

    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        m_downloadQueue.push_back(std::move(task));
    }
    m_newlyDetectedTitleIds.erase(title.titleId);
    m_statusNotification = (m_language == Language::Russian)
        ? ("Добавлено в очередь: " + title.name + " (" + variant.name + ")")
        : ("Added to queue: " + title.name + " (" + variant.name + ")");
    m_notificationFramesRemaining = 180;
}

void App::queueDownloadAppendSlot(const InstalledTitle& title, const Variant& variant) {
    int nextSlotIdx = 0;
    std::string nextSlotPath = Installer::getNextAvailableCoverPath(m_platform->getCoversDirectory(), title.titleId, &nextSlotIdx);

    DownloadTask task;
    task.id = title.titleId + "_" + variant.id + "_slot" + std::to_string(nextSlotIdx);
    task.titleId = title.titleId;
    task.gameTitle = title.name;
    task.variant = variant;
    task.coverOnly = true;
    task.appendAsNewSlot = (nextSlotIdx > 0);
    task.tempFilePath = m_platform->getCoversDirectory() + "/" + Config::getTempCoverFileName(title.titleId);
    task.targetFilePath = nextSlotPath;
    task.backupFilePath = m_platform->getCoversDirectory() + "/" + Config::getBackupCoverFileName(title.titleId);
    task.state = TaskState::Pending;
    task.totalBytes = variant.sizeBytes;

    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        m_downloadQueue.push_back(std::move(task));
    }
    m_newlyDetectedTitleIds.erase(title.titleId);
    m_statusNotification = (m_language == Language::Russian)
        ? ("В очередь (Слот #" + std::to_string(nextSlotIdx + 1) + "): " + title.name)
        : ("Queued into Slot #" + std::to_string(nextSlotIdx + 1) + ": " + title.name);
    m_notificationFramesRemaining = 180;
}

void App::queueComboPack(const InstalledTitle& targetGame, const GameCatalogEntry& sourceEntry, int preferredCoverIdx) {
    auto covers = getCoverVariants(sourceEntry);
    auto icons = getUniqueIconVariants(sourceEntry);

    bool queuedCover = false;
    bool queuedIcon = false;

    if (!covers.empty()) {
        int cIdx = std::clamp(preferredCoverIdx, 0, static_cast<int>(covers.size()) - 1);
        Variant covVar = covers[cIdx];
        if (!icons.empty() && covVar.iconUrl.empty()) {
            covVar.hasIcon = true;
            covVar.iconUrl = icons[0].iconUrl;
            covVar.iconSizeBytes = icons[0].iconSizeBytes;
        }
        queueDownload(targetGame, covVar);
        queuedCover = true;
        queuedIcon = covVar.hasIcon && !covVar.iconUrl.empty();
    }

    if (!queuedIcon && !icons.empty()) {
        queueDownloadIconOnly(targetGame, icons[0]);
        queuedIcon = true;
    }

    m_newlyDetectedTitleIds.erase(targetGame.titleId);
    if (queuedCover && queuedIcon) {
        m_statusNotification = tr("КОМБО в очереди (Фон + HQ-иконка): ", "COMBO queued (Cover + HQ Icon): ") + targetGame.name;
    } else if (queuedCover) {
        m_statusNotification = tr("В очереди (Видеофон): ", "Queued (Video Cover): ") + targetGame.name;
    } else if (queuedIcon) {
        m_statusNotification = tr("В очереди (HQ-иконка): ", "Queued (HQ Icon): ") + targetGame.name;
    }
    m_notificationFramesRemaining = 180;
}

void App::executeActivateCoverSlot(const std::string& titleId, int slotIndex) {
    if (slotIndex <= 0) return;
    m_videoPlayer.close();
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    if (Installer::switchActiveCover(m_platform->getCoversDirectory(), titleId, slotIndex)) {
        m_statusNotification = tr("Активирован слот видеофона #", "Activated cover slot #") + std::to_string(slotIndex + 1);
        m_notificationFramesRemaining = 150;
        for (auto& g : m_installedGames) {
            if (g.titleId == titleId) {
                g.installedCoverVariants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), titleId);
                g.installedCoversCount = static_cast<int>(g.installedCoverVariants.size());
                for (const auto& var : g.installedCoverVariants) {
                    if (var.isActive) {
                        g.installedCoverPath = var.filePath;
                        g.installedCoverSizeBytes = var.sizeBytes;
                        break;
                    }
                }
                break;
            }
        }
    }
}

void App::executeRestoreBackup(const std::string& titleId) {
    InstallResult res = Installer::restoreBackup(m_platform->getCoversDirectory(), titleId);
    if (res.success) {
        m_statusNotification = "Копия успешно восстановлена!";
    } else {
        m_statusNotification = "Ошибка: " + res.message;
    }
    m_notificationFramesRemaining = 200;
    refreshInstalledGames();
}

void App::executeDeleteCover(const std::string& titleId) {
    bool deleted = Installer::deleteCover(m_platform->getCoversDirectory(), titleId, false);
    if (deleted) {
        InstalledRegistry::instance().remove(m_platform->getAppDirectory(), titleId);
        m_statusNotification = "Видеофон удалён (копия .bak сохранена)";
    } else {
        m_statusNotification = "Видеофон не найден";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
    rebuildVideoIconsFilter();
}

void App::executeCycleNextCover(const std::string& titleId) {
    // 1. Release any open file handle in video player before filesystem swap
    m_videoPlayer.close();
    std::this_thread::sleep_for(std::chrono::milliseconds(20));

    auto variants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), titleId);
    if (variants.size() <= 1) return;

    int targetIndex = 1;
    for (const auto& v : variants) {
        if (!v.isActive && v.index > 0) {
            targetIndex = v.index;
            break;
        }
    }

    bool switched = Installer::switchActiveCover(m_platform->getCoversDirectory(), titleId, targetIndex);
    if (switched) {
        m_statusNotification = (m_language == Language::Russian)
            ? ("Активным назначен видеофон #" + std::to_string(targetIndex))
            : ("Active video cover switched to #" + std::to_string(targetIndex));
    } else {
        m_statusNotification = "Не удалось сменить видеофон";
    }
    m_notificationFramesRemaining = 180;

    // Fast, safe local update: refresh variant state ONLY for this game without rescanning all SD games
    for (auto& g : m_installedGames) {
        if (g.titleId == titleId) {
            g.installedCoverVariants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), titleId);
            g.installedCoversCount = static_cast<int>(g.installedCoverVariants.size());
            for (const auto& var : g.installedCoverVariants) {
                if (var.isActive) {
                    g.installedCoverPath = var.filePath;
                    g.installedCoverSizeBytes = var.sizeBytes;
                    break;
                }
            }
            break;
        }
    }
}

void App::executeDeleteCoverVariant(const std::string& titleId, int index) {
    bool deleted = Installer::deleteCoverVariant(m_platform->getCoversDirectory(), titleId, index);
    if (deleted) {
        m_statusNotification = (m_language == Language::Russian)
            ? ("Вариант видеофона #" + std::to_string(index) + " удалён")
            : ("Cover variant #" + std::to_string(index) + " deleted");
    } else {
        m_statusNotification = "Файл видеофона не найден";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
}

void App::executeDeleteAllCovers(const std::string& titleId) {
    bool deleted = Installer::deleteAllCoverVariants(m_platform->getCoversDirectory(), titleId);
    if (deleted) {
        InstalledRegistry::instance().remove(m_platform->getAppDirectory(), titleId);
        m_statusNotification = (m_language == Language::Russian)
            ? "Все видеофоны игры удалены с консоли"
            : "All video covers removed for this game";
    } else {
        m_statusNotification = "Видеофоны не найдены";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
    rebuildVideoIconsFilter();
}

void App::handleInput() {
#ifdef HAS_SDL2
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_QUIT) {
            m_running = false;
        } else if (event.type == SDL_CONTROLLERBUTTONDOWN) {
            onButtonPress(event.cbutton.button);
        } else if (event.type == SDL_CONTROLLERDEVICEADDED) {
            if (SDL_IsGameController(event.cdevice.which)) {
                SDL_GameControllerOpen(event.cdevice.which);
            }
        } else if (event.type == SDL_CONTROLLERDEVICEREMOVED) {
            SDL_GameController* pad = SDL_GameControllerFromInstanceID(event.cdevice.which);
            if (pad) {
                SDL_GameControllerClose(pad);
            }
        } else if (event.type == SDL_CONTROLLERAXISMOTION) {
            // Analog stick scrolling (Left Stick Y / X)
            if (event.caxis.axis == SDL_CONTROLLER_AXIS_LEFTY) {
                uint32_t now = SDL_GetTicks();
                if (now - m_lastStickScrollTime > 160) {
                    if (event.caxis.value > 16000) {
                        onButtonPress(12 /* DPAD_DOWN */);
                        m_lastStickScrollTime = now;
                    } else if (event.caxis.value < -16000) {
                        onButtonPress(11 /* DPAD_UP */);
                        m_lastStickScrollTime = now;
                    }
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_LEFTX) {
                uint32_t now = SDL_GetTicks();
                if (now - m_lastStickScrollTime > 200) {
                    if (event.caxis.value > 18000) {
                        onButtonPress(14 /* DPAD_RIGHT */);
                        m_lastStickScrollTime = now;
                    } else if (event.caxis.value < -18000) {
                        onButtonPress(13 /* DPAD_LEFT */);
                        m_lastStickScrollTime = now;
                    }
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(15 /* BUTTON_ZL */);
                    m_lastTriggerTime = now;
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(16 /* BUTTON_ZR */);
                    m_lastTriggerTime = now;
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_RIGHTY) {
                uint32_t now = SDL_GetTicks();
                if (now - m_lastRightStickTime > 170) {
                    if (event.caxis.value > 18000) {
                        onButtonPress(18 /* RSTICK_DOWN -> Alpha Jump +1 */);
                        m_lastRightStickTime = now;
                    } else if (event.caxis.value < -18000) {
                        onButtonPress(17 /* RSTICK_UP -> Alpha Jump -1 */);
                        m_lastRightStickTime = now;
                    }
                }
            }
        } else if (event.type == SDL_MOUSEWHEEL) {
            if (event.wheel.y > 0) {
                onButtonPress(11 /* DPAD_UP */);
            } else if (event.wheel.y < 0) {
                onButtonPress(12 /* DPAD_DOWN */);
            }
        } else if (event.type == SDL_FINGERDOWN) {
            if (!m_touchDown) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                m_touchDown = true;
                m_activeFingerId = event.tfinger.fingerId;
                m_touchStartX = mx;
                m_touchStartY = my;
                m_touchLastX = mx;
                m_touchLastY = my;
                m_touchStartTime = SDL_GetTicks();
                m_isTouchDragging = false;
                m_touchDragAccumulator = 0;
            }
        } else if (event.type == SDL_FINGERMOTION) {
            if (m_touchDown && event.tfinger.fingerId == m_activeFingerId) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                int diffX = mx - m_touchStartX;
                int diffY = my - m_touchStartY;
                if (!m_isTouchDragging && (std::abs(diffX) > 15 || std::abs(diffY) > 15)) {
                    m_isTouchDragging = true;
                }

                if (m_isTouchDragging) {
                    int dy = my - m_touchLastY;
                    handleTouchDrag(m_touchStartX, m_touchStartY, dy);
                }
                m_touchLastX = mx;
                m_touchLastY = my;
            }
        } else if (event.type == SDL_FINGERUP) {
            if (m_touchDown && event.tfinger.fingerId == m_activeFingerId) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                if (!m_isTouchDragging) {
                    handleTouchTap(m_touchStartX, m_touchStartY);
                } else {
                    handleTouchSwipe(m_touchStartX, m_touchStartY, mx, my);
                }
                m_touchDown = false;
                m_isTouchDragging = false;
                m_touchDragAccumulator = 0;
            }
        } else if (event.type == SDL_MOUSEBUTTONDOWN) {
            if (event.button.which != SDL_TOUCH_MOUSEID) {
                handleTouchTap(event.button.x, event.button.y);
            }
        } else if (event.type == SDL_KEYDOWN) {
            // Keyboard simulation on PC
            switch (event.key.keysym.sym) {
                case SDLK_UP:     onButtonPress(SDL_CONTROLLER_BUTTON_DPAD_UP); break;
                case SDLK_DOWN:   onButtonPress(SDL_CONTROLLER_BUTTON_DPAD_DOWN); break;
                case SDLK_LEFT:   onButtonPress(SDL_CONTROLLER_BUTTON_DPAD_LEFT); break;
                case SDLK_RIGHT:  onButtonPress(SDL_CONTROLLER_BUTTON_DPAD_RIGHT); break;
                case SDLK_RETURN:
                case SDLK_a:      onButtonPress(SDL_CONTROLLER_BUTTON_A); break;
                case SDLK_ESCAPE:
                case SDLK_b:      onButtonPress(SDL_CONTROLLER_BUTTON_B); break;
                case SDLK_x:      onButtonPress(SDL_CONTROLLER_BUTTON_X); break;
                case SDLK_y:      onButtonPress(SDL_CONTROLLER_BUTTON_Y); break;
                case SDLK_q:      onButtonPress(SDL_CONTROLLER_BUTTON_LEFTSHOULDER); break;
                case SDLK_e:      onButtonPress(SDL_CONTROLLER_BUTTON_RIGHTSHOULDER); break;
                case SDLK_MINUS:
                case SDLK_m:
                case SDLK_r:      onButtonPress(SDL_CONTROLLER_BUTTON_BACK); break; // Minus (Refresh)
                case SDLK_EQUALS:
                case SDLK_PLUS:
                case SDLK_p:      onButtonPress(SDL_CONTROLLER_BUTTON_START); break; // Plus (Update NRO)
                case SDLK_PAGEUP:   onButtonPress(17); break; // Alpha Jump Up
                case SDLK_PAGEDOWN: onButtonPress(18); break; // Alpha Jump Down
                default: break;
            }
        }
    }
#endif
}

void App::onButtonPress(int button) {
    m_buttonPressAnim = 1.0f;

    // Top-Level Modal Dialog Handler: Must process first and block all underlying views
    if (m_activeDialog != DialogType::None) {
        if (SDL_GetTicks() - m_dialogOpenedAt < 150) {
            return;
        }
        if (m_activeDialog == DialogType::UpdateAvailable) {
            if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
                m_dialogFocus = 1 - m_dialogFocus;
            } else if (button == 0 /* A */) {
                if (m_dialogFocus == 0) {
                    m_activeDialog = DialogType::None;
                    updateApplicationNro();
                } else {
                    m_activeDialog = DialogType::None;
                }
            } else if (button == 1 /* B */) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::UpdateProgress) {
            // While downloading, allow B to hide modal to background
            if (button == 1 /* B */) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::UpdateSuccess) {
            if (button == 0 /* A - Restart App */) {
                m_running = false; // Exit to hbmenu so user launches newly updated NRO
            } else if (button == 1 /* B - Continue */) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::MessageAlert || m_activeDialog == DialogType::IntegrityCheckResult) {
            if (button == 0 || button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::ConfirmInstallLocalRecording) {
            if (button == 0) {
                m_activeDialog = DialogType::None;
                executeInstallLocalRecording();
            } else if (button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::ConfirmDeleteCorrupted) {
            if (button == 13 || button == 14) {
                m_dialogFocus = 1 - m_dialogFocus;
            } else if (button == 0) {
                if (m_dialogFocus == 0) {
                    m_activeDialog = DialogType::None;
                    executeDeleteCorruptedCovers();
                } else {
                    m_activeDialog = DialogType::None;
                }
            } else if (button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }

        bool isInstallWithIcon = (m_activeDialog == DialogType::ConfirmInstall && m_pendingActionVariant.hasIcon);
        bool isDeleteBoth = false;
        if (m_activeDialog == DialogType::ConfirmDelete) {
            for (const auto& g : m_installedGames) {
                if (g.titleId == m_pendingActionTitleId) {
                    if (g.hasInstalledCover && g.hasInstalledIcon) {
                        isDeleteBoth = true;
                    }
                    break;
                }
            }
        }

        if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            if (isInstallWithIcon || isDeleteBoth) {
                m_dialogFocus = (button == 13) ? ((m_dialogFocus + 3) % 4) : ((m_dialogFocus + 1) % 4);
            } else {
                m_dialogFocus = 1 - m_dialogFocus;
            }
            return;
        }

        // Direct Quick Shortcuts for Multi-Option Dialogs:
        // [X] -> Only Icon
        if (button == 2 /* X */) {
            if (isInstallWithIcon) {
                InstalledTitle targetGame;
                bool found = false;
                for (const auto& g : m_installedGames) {
                    if (g.titleId == m_pendingActionTitleId) { targetGame = g; found = true; break; }
                }
                if (!found) { targetGame.titleId = m_pendingActionTitleId; targetGame.name = m_previewGameName; targetGame.hasCatalogMatch = true; }
                queueDownloadIconOnly(targetGame, m_pendingActionVariant);
                m_activeDialog = DialogType::None;
                return;
            } else if (isDeleteBoth) {
                executeDeleteIcon(m_pendingActionTitleId);
                m_activeDialog = DialogType::None;
                return;
            }
        }
        // [Y] -> Only Video Cover
        if (button == 3 /* Y */) {
            if (isInstallWithIcon) {
                InstalledTitle targetGame;
                bool found = false;
                for (const auto& g : m_installedGames) {
                    if (g.titleId == m_pendingActionTitleId) { targetGame = g; found = true; break; }
                }
                if (!found) { targetGame.titleId = m_pendingActionTitleId; targetGame.name = m_previewGameName; targetGame.hasCatalogMatch = true; }
                queueDownloadCoverOnly(targetGame, m_pendingActionVariant);
                m_activeDialog = DialogType::None;
                return;
            } else if (isDeleteBoth) {
                executeDeleteCover(m_pendingActionTitleId);
                m_activeDialog = DialogType::None;
                return;
            }
        }

        if (button == 0 /* A - Confirm */) {
            if (m_activeDialog == DialogType::ConfirmInstall) {
                InstalledTitle targetGame;
                bool found = false;
                for (const auto& g : m_installedGames) {
                    if (g.titleId == m_pendingActionTitleId) { targetGame = g; found = true; break; }
                }
                if (!found) { targetGame.titleId = m_pendingActionTitleId; targetGame.name = m_previewGameName; targetGame.hasCatalogMatch = true; }

                if (isInstallWithIcon) {
                    if (m_dialogFocus == 0) {
                        // Install Both (Cover + Icon)
                        queueDownload(targetGame, m_pendingActionVariant);
                    } else if (m_dialogFocus == 1) {
                        // Install ONLY Icon
                        queueDownloadIconOnly(targetGame, m_pendingActionVariant);
                    } else if (m_dialogFocus == 2) {
                        // Install ONLY Cover
                        queueDownloadCoverOnly(targetGame, m_pendingActionVariant);
                    }
                    // focus == 3 is cancel
                } else {
                    if (m_dialogFocus == 0) {
                        queueDownload(targetGame, m_pendingActionVariant);
                    }
                }
            } else if (m_activeDialog == DialogType::ConfirmInstallAll) {
                if (m_dialogFocus == 0) {
                    for (const auto& g : m_installedGames) {
                        auto covs = getCoverVariants(g.catalogEntry);
                        if (!g.hasInstalledCover && g.hasCatalogMatch && !covs.empty()) {
                            bool alreadyInQueue = false;
                            {
                                std::lock_guard<std::mutex> lock(m_queueMutex);
                                for (const auto& task : m_downloadQueue) {
                                    if (task.titleId == g.titleId && !task.iconOnly && task.state != TaskState::Failed) {
                                        alreadyInQueue = true;
                                        break;
                                    }
                                }
                            }
                            if (!alreadyInQueue) {
                                queueDownload(g, covs[0]);
                            }
                        }
                    }
                    m_activeTab = Tab::Downloads;
                }
            } else if (m_activeDialog == DialogType::ConfirmRestore) {
                if (m_dialogFocus == 0) {
                    executeRestoreBackup(m_pendingActionTitleId);
                }
            } else if (m_activeDialog == DialogType::ConfirmDelete) {
                if (isDeleteBoth) {
                    if (m_dialogFocus == 0) {
                        executeDeleteCover(m_pendingActionTitleId);
                        executeDeleteIcon(m_pendingActionTitleId);
                    } else if (m_dialogFocus == 1) {
                        executeDeleteIcon(m_pendingActionTitleId);
                    } else if (m_dialogFocus == 2) {
                        executeDeleteCover(m_pendingActionTitleId);
                    }
                } else {
                    if (m_dialogFocus == 0) {
                        bool hadCover = false;
                        for (const auto& g : m_installedGames) {
                            if (g.titleId == m_pendingActionTitleId) { hadCover = g.hasInstalledCover; break; }
                        }
                        if (hadCover) executeDeleteCover(m_pendingActionTitleId);
                        else executeDeleteIcon(m_pendingActionTitleId);
                    }
                }
            }
            m_activeDialog = DialogType::None;
        } else if (button == 1 /* B - Cancel */) {
            m_activeDialog = DialogType::None;
        }
        return;
    }

    // Unified Glass Action Sheet [X] Modal Handler
    if (m_isActionSheetOpen && m_activeDialog == DialogType::None) {
        if (SDL_GetTicks() - m_actionSheetOpenedAt < 120) {
            return;
        }
        if (button == 1 /* B */ || button == 2 /* X */) {
            closeActionSheet();
            return;
        }
        int itemCount = static_cast<int>(m_actionSheetItems.size());
        if (itemCount > 0) {
            if (button == 11 /* UP */) {
                m_actionSheetSelectedIndex = (m_actionSheetSelectedIndex <= 0) ? (itemCount - 1) : (m_actionSheetSelectedIndex - 1);
                return;
            }
            if (button == 12 /* DOWN */) {
                m_actionSheetSelectedIndex = (m_actionSheetSelectedIndex + 1) % itemCount;
                return;
            }
            if (button == 0 /* A - Execute Action */) {
                executeActionSheetSelection();
                return;
            }
        }
        return;
    }

    // Collection Browser Modal Handler (Browse variants by name with static + live mini-previews)
    if (m_isCollectionBrowserOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview && !m_isGamePickerOpen) {
        if (SDL_GetTicks() - m_collectionOpenedAt < 150) {
            return;
        }
        if (button == 1 /* B - Back to Catalog */) {
            closeCollectionBrowser();
            return;
        }
        int vCount = static_cast<int>(m_collectionVariants.size());
        auto triggerCollectionPreviewRefresh = [this]() {
            m_cancelCollectionThumb.store(true);
            m_videoPlayer.close();
            if (m_collectionThumbTexture) {
                SDL_DestroyTexture(m_collectionThumbTexture);
                m_collectionThumbTexture = nullptr;
            }
            m_collectionPreviewDirty = true;
            m_lastCollectionMoveTime = SDL_GetTicks();
        };
        if (button == 11 /* UP */) {
            if (m_collectionSelectedIndex > 0) {
                m_collectionSelectedIndex--;
                if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                    m_collectionScrollOffset = m_collectionSelectedIndex;
                }
                triggerCollectionPreviewRefresh();
            }
            return;
        }
        if (button == 12 /* DOWN */) {
            if (m_collectionSelectedIndex + 1 < vCount) {
                m_collectionSelectedIndex++;
                if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                    m_collectionScrollOffset = m_collectionSelectedIndex - 5 + 1;
                }
                triggerCollectionPreviewRefresh();
            }
            return;
        }
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_collectionSelectedIndex = std::max(0, m_collectionSelectedIndex - 5);
            if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                m_collectionScrollOffset = m_collectionSelectedIndex;
            }
            if (!m_collectionVariants.empty()) {
                triggerCollectionPreviewRefresh();
            }
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            m_collectionSelectedIndex = std::min(vCount - 1, m_collectionSelectedIndex + 5);
            if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                m_collectionScrollOffset = std::max(0, m_collectionSelectedIndex - 5 + 1);
            }
            if (!m_collectionVariants.empty()) {
                triggerCollectionPreviewRefresh();
            }
            return;
        }
        if (button == 15 /* ZL - Fast Page Up 15 */) {
            m_collectionSelectedIndex = std::max(0, m_collectionSelectedIndex - 15);
            if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                m_collectionScrollOffset = m_collectionSelectedIndex;
            }
            if (!m_collectionVariants.empty()) {
                triggerCollectionPreviewRefresh();
            }
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 15 */) {
            m_collectionSelectedIndex = std::min(vCount - 1, m_collectionSelectedIndex + 15);
            if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                m_collectionScrollOffset = std::max(0, m_collectionSelectedIndex - 5 + 1);
            }
            if (!m_collectionVariants.empty()) {
                triggerCollectionPreviewRefresh();
            }
            return;
        }
        if (button == 3 /* Y - Assign to another game */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                openGamePicker(m_collectionVariants[m_collectionSelectedIndex], m_collectionGameName);
            }
            return;
        }
        if (button == 0 /* A - Direct install for this game, or GamePicker if generic pack */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                const Variant& chosenVar = m_collectionVariants[m_collectionSelectedIndex];
                if (m_collectionTitleId.empty() || m_collectionTitleId == "0000000000000000") {
                    openGamePicker(chosenVar, m_collectionGameName);
                    return;
                }
                bool isPureIcon = (chosenVar.id.rfind("icon-", 0) == 0) || (chosenVar.width == 256 && chosenVar.height == 256);
                if (isPureIcon) {
                    InstalledTitle targetGame;
                    targetGame.titleId = m_collectionTitleId;
                    targetGame.name = m_collectionGameName;
                    targetGame.hasCatalogMatch = true;
                    queueDownloadIconOnly(targetGame, chosenVar);
                    m_statusNotification = tr("Иконка добавлена в загрузки: ", "Queued icon download: ") + m_collectionGameName;
                    m_notificationFramesRemaining = 120;
                    if (!m_linkingTargetTitleId.empty()) {
                        cancelForwarderLinkMode();
                        closeCollectionBrowser();
                    }
                    return;
                }
                bool isInstalled = false;
                std::string gName = m_collectionGameName;
                for (const auto& ig : m_installedGames) {
                    if (ig.titleId == m_collectionTitleId) {
                        isInstalled = true;
                        gName = ig.name;
                        break;
                    }
                }
                m_pendingActionTitleId = m_collectionTitleId;
                m_pendingActionVariant = chosenVar;
                m_previewGameName = gName;
                m_activeDialog = DialogType::ConfirmInstall;
                m_dialogOpenedAt = SDL_GetTicks();
                m_dialogTitle = getStrings(m_language).confirmInstallTitle;
                if (isInstalled) {
                    m_dialogMessage = (m_language == Language::Russian)
                        ? ("Установить вариант '" + chosenVar.name + "' (" + styleToString(chosenVar.style) + ") для игры " + gName + "?")
                        : ("Install variant '" + chosenVar.name + "' (" + styleToString(chosenVar.style) + ") for " + gName + "?");
                } else {
                    m_dialogMessage = (m_language == Language::Russian)
                        ? ("Игра " + gName + " пока не установлена на Switch.\n\nСохранить видеофон '" + chosenVar.name + "' в recordings/covers заранее?")
                        : ("Game " + gName + " is not installed yet.\n\nPre-install video cover '" + chosenVar.name + "' to recordings/covers?");
                }
                m_dialogFocus = (m_collectionPreviewIconMode && chosenVar.hasIcon) ? 1 : 0;
                if (!m_linkingTargetTitleId.empty()) {
                    cancelForwarderLinkMode();
                    closeCollectionBrowser();
                }
            }
            return;
        }
        if (button == 10 /* R - Toggle 16:9 Cover vs 256x256 Video Icon Preview */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                const auto& cv = m_collectionVariants[m_collectionSelectedIndex];
                bool isPureIcon = (cv.id.rfind("icon-", 0) == 0) || (cv.width == 256 && cv.height == 256);
                if (!isPureIcon && cv.hasIcon && !cv.iconUrl.empty()) {
                    m_collectionPreviewIconMode = !m_collectionPreviewIconMode;
                    triggerCollectionPreviewRefresh();
                } else if (!getUniqueIconVariants(m_collectionEntry).empty()) {
                    openFullscreenVideoIconPreview(m_collectionEntry, 0);
                }
            }
            return;
        }
        if (button == 8 /* R3 */ || button == 9 /* L - Toggle Favorite */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                toggleFavoriteVariant(m_collectionTitleId, m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 2 /* X - Fullscreen live video (Cover or Icon depending on current mode) */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                const auto& cv = m_collectionVariants[m_collectionSelectedIndex];
                bool isPureIcon = (cv.id.rfind("icon-", 0) == 0) || (cv.width == 256 && cv.height == 256);
                bool showAsIcon = isPureIcon || (m_collectionPreviewIconMode && cv.hasIcon && !cv.iconUrl.empty());
                if (showAsIcon) {
                    auto uIcons = getUniqueIconVariants(m_collectionEntry);
                    int icoIdx = 0;
                    std::string wantUrl = !cv.iconUrl.empty() ? cv.iconUrl : cv.url;
                    for (size_t k = 0; k < uIcons.size(); ++k) {
                        if (uIcons[k].iconUrl == wantUrl || uIcons[k].id == cv.id) {
                            icoIdx = static_cast<int>(k);
                            break;
                        }
                    }
                    openFullscreenVideoIconPreview(m_collectionEntry, icoIdx);
                } else {
                    GameCatalogEntry tempEntry = m_collectionEntry;
                    tempEntry.variants = getCoverVariants(m_collectionEntry);
                    int covIdx = std::clamp(m_collectionSelectedIndex, 0, std::max(0, static_cast<int>(tempEntry.variants.size()) - 1));
                    openFullscreenPreviewForCatalogGame(tempEntry, covIdx);
                }
            }
            return;
        }
        return;
    }


    // Target Game Picker Handler (Assign video theme to any installed game)
    if (m_isGamePickerOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview) {
        if (SDL_GetTicks() - m_gamePickerOpenedAt < 150) {
            return;
        }
        if (button == 1 /* B */) {
            closeGamePicker();
            return;
        }
        if (button == 11 /* UP */) {
            if (m_gamePickerSelectedIndex > 0) m_gamePickerSelectedIndex--;
            return;
        }
        if (button == 12 /* DOWN */) {
            if (m_gamePickerSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                m_gamePickerSelectedIndex++;
            }
            return;
        }
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_gamePickerSelectedIndex = std::max(0, m_gamePickerSelectedIndex - 5);
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            if (!m_installedGames.empty()) {
                m_gamePickerSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_gamePickerSelectedIndex + 5);
            }
            return;
        }
        if (button == 15 /* ZL - Fast Page Up 10 */) {
            m_gamePickerSelectedIndex = std::max(0, m_gamePickerSelectedIndex - 10);
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 10 */) {
            if (!m_installedGames.empty()) {
                m_gamePickerSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_gamePickerSelectedIndex + 10);
            }
            return;
        }
        if (button == 0 /* A - Select Game */) {
            if (!m_installedGames.empty() && m_gamePickerSelectedIndex >= 0 &&
                m_gamePickerSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& targetGame = m_installedGames[m_gamePickerSelectedIndex];
                m_pendingActionTitleId = targetGame.titleId;
                m_pendingActionVariant = m_gamePickerPendingVariant;
                m_activeDialog = DialogType::ConfirmInstall;
                m_dialogOpenedAt = SDL_GetTicks();
                m_dialogTitle = (m_language == Language::Russian) ? "Назначение видеофона" : "Assign Video Theme";
                m_dialogMessage = (m_language == Language::Russian)
                    ? ("Установить видеофон '" + m_pendingActionVariant.name + "'\nдля игры: " + targetGame.name + " [" + targetGame.titleId + "]?")
                    : ("Install video theme '" + m_pendingActionVariant.name + "'\nfor game: " + targetGame.name + " [" + targetGame.titleId + "]?");
                m_dialogFocus = 0;
                closeGamePicker();
            }
            return;
        }
        return;
    }

    // Local Recordings Browser Handler (Feature 3)
    if (m_isRecordingsBrowserOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview) {
        if (SDL_GetTicks() - m_recordingsOpenedAt < 150) {
            return;
        }
        if (button == 1 /* B */) {
            closeRecordingsBrowser();
            return;
        }
        if (button == 11 /* UP */) {
            if (m_recordingsSelectedIndex > 0) m_recordingsSelectedIndex--;
            return;
        }
        if (button == 12 /* DOWN */) {
            if (m_recordingsSelectedIndex + 1 < static_cast<int>(m_localRecordings.size())) {
                m_recordingsSelectedIndex++;
            }
            return;
        }
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_recordingsSelectedIndex = std::max(0, m_recordingsSelectedIndex - 5);
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            if (!m_localRecordings.empty()) {
                m_recordingsSelectedIndex = std::min(static_cast<int>(m_localRecordings.size()) - 1, m_recordingsSelectedIndex + 5);
            }
            return;
        }
        if (button == 15 /* ZL - Fast Page Up 10 */) {
            m_recordingsSelectedIndex = std::max(0, m_recordingsSelectedIndex - 10);
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 10 */) {
            if (!m_localRecordings.empty()) {
                m_recordingsSelectedIndex = std::min(static_cast<int>(m_localRecordings.size()) - 1, m_recordingsSelectedIndex + 10);
            }
            return;
        }
        if (button == 2 /* X - Preview clip */) {
            if (!m_localRecordings.empty() && m_recordingsSelectedIndex >= 0 &&
                m_recordingsSelectedIndex < static_cast<int>(m_localRecordings.size())) {
                const auto& rec = m_localRecordings[m_recordingsSelectedIndex];
                Variant clipVar;
                clipVar.id = "local:" + rec.filename;
                clipVar.name = rec.filename;
                clipVar.style = CoverStyle::Gameplay;
                clipVar.url = rec.fullPath;
                clipVar.previewUrl = rec.fullPath;
                m_previewVariants = {clipVar};
                m_previewVariantIndex = 0;
                m_previewTitleId = m_recordingsTargetTitleId;
                m_previewGameName = m_recordingsTargetGameName;
                m_previewIsGameInstalled = true;
                m_previewHasInstalledCover = false;
                m_previewIsIconSquare = false;
                m_previewShowSwitchHud = false;
                m_previewOpenedAt = SDL_GetTicks();
                m_isFullscreenPreview = true;
                m_videoPlayer.open(rec.fullPath, m_renderer);
            }
            return;
        }
        if (button == 0 /* A - Install clip */) {
            if (!m_localRecordings.empty() && m_recordingsSelectedIndex >= 0 &&
                m_recordingsSelectedIndex < static_cast<int>(m_localRecordings.size())) {
                const auto& rec = m_localRecordings[m_recordingsSelectedIndex];
                m_pendingRecordingToInstallPath = rec.fullPath;
                m_pendingRecordingToInstallName = rec.filename;
                m_activeDialog = DialogType::ConfirmInstallLocalRecording;
    m_dialogOpenedAt = SDL_GetTicks();
                m_dialogTitle = "Установка видеофона";
                m_dialogMessage = "Установить запись '" + rec.filename +
                                  "' в качестве видеофона для игры " + m_recordingsTargetGameName + "?";
                m_dialogFocus = 0;
            }
            return;
        }
        return;
    }

    // Fullscreen Preview Input Handler
    if (m_isFullscreenPreview) {
        if (SDL_GetTicks() - m_previewOpenedAt < 200) {
            return;
        }
        if (button == 16 /* ZR - Toggle Switch Horizon OS Home Screen Overlay on 16:9 covers */) {
            if (!m_previewIsIconSquare) {
                m_previewShowSwitchHud = !m_previewShowSwitchHud;
            }
            return;
        }
        if (button == 10 /* R - Toggle between 16:9 Video Cover and 256x256 Video Icon Preview */) {
            const GameCatalogEntry* catMatch = m_catalogManager.findByTitleId(m_previewTitleId);
            if (!m_previewIsIconSquare) {
                // Switch from 16:9 Cover -> 256x256 Video Icon
                if (catMatch) {
                    auto uIcons = getUniqueIconVariants(*catMatch);
                    if (!uIcons.empty()) {
                        int icoIdx = 0;
                        if (!m_previewVariants.empty() && m_previewVariantIndex >= 0 &&
                            m_previewVariantIndex < static_cast<int>(m_previewVariants.size())) {
                            const auto& curV = m_previewVariants[m_previewVariantIndex];
                            for (size_t k = 0; k < uIcons.size(); ++k) {
                                if (!curV.iconUrl.empty() && uIcons[k].iconUrl == curV.iconUrl) {
                                    icoIdx = static_cast<int>(k);
                                    break;
                                }
                            }
                        }
                        openFullscreenVideoIconPreview(*catMatch, icoIdx);
                        return;
                    }
                }
                if (!m_previewVariants.empty() && m_previewVariantIndex >= 0 &&
                    m_previewVariantIndex < static_cast<int>(m_previewVariants.size())) {
                    const auto& curV = m_previewVariants[m_previewVariantIndex];
                    if (curV.hasIcon && !curV.iconUrl.empty()) {
                        GameCatalogEntry tmpEntry;
                        tmpEntry.titleId = m_previewTitleId;
                        tmpEntry.title = m_previewGameName;
                        tmpEntry.variants = {curV};
                        openFullscreenVideoIconPreview(tmpEntry, 0);
                        return;
                    }
                }
            } else {
                // Switch from 256x256 Video Icon -> 16:9 Video Cover
                if (catMatch && !getCoverVariants(*catMatch).empty()) {
                    openFullscreenPreviewForCatalogGame(*catMatch, 0);
                    return;
                }
            }
            return;
        }
        if (button == 8 /* R3 */ || button == 9 /* L - Toggle Favorite */) {
            if (!m_previewVariants.empty() && m_previewVariantIndex >= 0 &&
                m_previewVariantIndex < static_cast<int>(m_previewVariants.size())) {
                toggleFavoriteVariant(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
            }
            return;
        }
        if (button == 1 /* B */ || button == 2 /* X */) {
            closeFullscreenPreview();
            return;
        }
        if (!m_previewVariants.empty()) {
            int vCount = static_cast<int>(m_previewVariants.size());
            if (button == 13 /* DPAD_LEFT */) {
                m_previewVariantIndex = (m_previewVariantIndex == 0) ? vCount - 1 : m_previewVariantIndex - 1;
                loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
                return;
            } else if (button == 14 /* DPAD_RIGHT */) {
                m_previewVariantIndex = (m_previewVariantIndex + 1) % vCount;
                loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
                return;
            } else if (button == 3 /* Y - Assign to another game */) {
                Variant var = m_previewVariants[m_previewVariantIndex];
                std::string gName = m_previewGameName;
                closeFullscreenPreview();
                openGamePicker(var, gName);
                return;
            } else if (button == 0 /* A - Install / Save */) {
                if (m_previewIsIconSquare) {
                    InstalledTitle targetGame;
                    targetGame.titleId = m_previewTitleId;
                    targetGame.name = m_previewGameName;
                    targetGame.hasCatalogMatch = true;
                    Variant chosenVar = m_previewVariants[m_previewVariantIndex];
                    closeFullscreenPreview();
                    queueDownloadIconOnly(targetGame, chosenVar);
                    return;
                }
                if (m_previewTitleId == "0000000000000000") {
                    Variant var = m_previewVariants[m_previewVariantIndex];
                    std::string gName = m_previewGameName;
                    closeFullscreenPreview();
                    openGamePicker(var, gName);
                    return;
                }
                Variant chosenVar = m_previewVariants[m_previewVariantIndex];
                std::string titleId = m_previewTitleId;
                std::string gName = m_previewGameName;
                bool isInstalled = m_previewIsGameInstalled;
                closeFullscreenPreview();
                m_pendingActionTitleId = titleId;
                m_pendingActionVariant = chosenVar;
                if (m_pendingActionVariant.id.rfind("local:", 0) == 0) {
                    m_pendingRecordingToInstallPath = m_pendingActionVariant.url;
                    m_pendingRecordingToInstallName = m_pendingActionVariant.name;
                    m_activeDialog = DialogType::ConfirmInstallLocalRecording;
                    m_dialogOpenedAt = SDL_GetTicks();
                    m_dialogTitle = (m_language == Language::Russian) ? "Установка записи" : "Install Recording";
                    m_dialogMessage = (m_language == Language::Russian)
                        ? ("Установить запись '" + m_pendingRecordingToInstallName + "' в качестве видеофона для игры " + gName + "?")
                        : ("Install recording '" + m_pendingRecordingToInstallName + "' as video theme for " + gName + "?");
                    m_dialogFocus = 0;
                    return;
                }
                m_activeDialog = DialogType::ConfirmInstall;
                m_dialogOpenedAt = SDL_GetTicks();
                m_dialogTitle = getStrings(m_language).confirmInstallTitle;
                if (isInstalled) {
                    m_dialogMessage = "Установить вариант '" + m_pendingActionVariant.name + "' (" +
                                      styleToString(m_pendingActionVariant.style) + ") для игры " + gName + "?";
                } else {
                    m_dialogMessage = "Игра " + gName + " пока не установлена на Switch.\n\n"
                                      "Сохранить видеофон '" + m_pendingActionVariant.name +
                                      "' в recordings/covers заранее, чтобы он активировался при установке игры?";
                }
                m_dialogFocus = 0;
                return;
            }
        }
        return;
    }

    // =========================================================================
    // ЖЕСТКОЕ ПРАВИЛО КНОПОК ВЕЗДЕ (v1.5.0 Global Unified Control Contract)
    // =========================================================================
    // 1. Правый стик Вверх/Вниз (17 / 18) -> Алфавитный турбо-прыжок A–Z
    if (button == 17) {
        jumpAlphabetical(-1);
        return;
    }
    if (button == 18) {
        jumpAlphabetical(1);
        return;
    }

    // 2. [L] / [R] (9 / 10) -> ВСЕГДА глобальное переключение вкладок без исключений!
    if (button == 9 /* LEFTSHOULDER (L) */) {
        switchGlobalTab(-1);
        return;
    }
    if (button == 10 /* RIGHTSHOULDER (R) */) {
        switchGlobalTab(1);
        return;
    }

    // 3. [+] PLUS (6) -> ВСЕГДА системная проверка и установка OTA-обновления NRO
    if (button == 6 /* START (+) */) {
        updateApplicationNro();
        return;
    }

    // 4. [B] (1) -> Назад / Выход на Главную / Отмена привязки форвардера
    if (button == 1 /* B - Back */) {
        if (m_activeTab == Tab::MyGames && m_myGamesActivePane == MyGamesPane::VariantsList) {
            m_myGamesActivePane = MyGamesPane::GamesList;
            return;
        }
        if (m_activeTab == Tab::Catalog && !m_linkingTargetTitleId.empty()) {
            cancelForwarderLinkMode();
            m_activeTab = Tab::MyGames;
            return;
        }
        if (m_activeTab != Tab::Home) {
            if (m_activeTab == Tab::VideoIcons || m_activeTab == Tab::Catalog) {
                m_cancelCollectionThumb.store(true);
                m_collectionTransferQueued = false;
                m_videoIconDockDirty = false;
                m_catalogDockDirty = false;
                m_videoPlayer.close();
            }
            m_activeTab = Tab::Home;
            return;
        }
        m_running = false;
        return;
    }

    // 5. Обработка вкладок по единому контракту (A = Основное, X = Шторка действий, Y = Поиск, - = Фильтр, ZL/ZR = ±8)
    if (m_activeTab == Tab::Home) {
        if (button == 13 /* DPAD_LEFT */) {
            m_homeFocusedTile = (m_homeFocusedTile == 0) ? 4 : m_homeFocusedTile - 1;
            return;
        }
        if (button == 14 /* DPAD_RIGHT */) {
            m_homeFocusedTile = (m_homeFocusedTile == 4) ? 0 : m_homeFocusedTile + 1;
            return;
        }
        if (button == 0 /* A - Activate selected tile */) {
            switch (m_homeFocusedTile) {
                case 0:
                    m_activeTab = Tab::Catalog;
                    m_catalogViewMode = CatalogViewMode::Categories;
                    if (m_filteredCatalogGames.empty() && m_catalogSearchQuery.empty()) {
                        rebuildCatalogFilter();
                    }
                    m_catalogDockDirty = true;
                    m_catalogDockCurrentKey.clear();
                    m_lastCatalogMoveTime = SDL_GetTicks();
                    break;
                case 1:
                    m_activeTab = Tab::VideoIcons;
                    rebuildVideoIconsFilter();
                    m_videoIconDockDirty = true;
                    m_lastVideoIconMoveTime = SDL_GetTicks();
                    break;
                case 2:
                    m_activeTab = Tab::MyGames;
                    rebuildMyGamesFilter();
                    break;
                case 3:
                    m_activeTab = Tab::Downloads;
                    break;
                case 4:
                    m_activeTab = Tab::Settings;
                    break;
            }
            return;
        }
        if (button == 3 /* Y - Всегда Поиск -> переход в Каталог и клавиатура */) {
            m_activeTab = Tab::Catalog;
            openCatalogKeyboard();
            return;
        }
        if (button == 2 /* X - Единая шторка действий или Обновить базу */) {
            if (!m_newlyDetectedTitleIds.empty() || getMissingCoversCount() > 0) {
                openActionSheetForCurrentContext();
            } else {
                fetchRemoteCatalog();
            }
            return;
        }
        if (button == 4 /* MINUS (-) - Умное пакетное действие под выбранный раздел Главной */) {
            if (m_homeFocusedTile == 1) {
                // Пакетная установка всех недостающих Ultra-HQ 256x256 иконок для установленных игр на Switch!
                int queuedIcons = 0;
                for (const auto& ig : m_installedGames) {
                    if (ig.titleId.empty() || ig.titleId == "0000000000000000" || ig.hasInstalledIcon) continue;
                    if (!ig.hasCatalogMatch) continue;
                    auto uIcons = getUniqueIconVariants(ig.catalogEntry);
                    if (!uIcons.empty()) {
                        queueDownloadIconOnly(ig, uIcons[0]);
                        queuedIcons++;
                    }
                }
                if (queuedIcons > 0) {
                    m_activeTab = Tab::Downloads;
                    m_homeFocusedTile = 3;
                    m_statusNotification = tr("В очередь добавлены Ultra-HQ иконки для ваших игр: ",
                                              "Queued Ultra-HQ icons for your games: ") + std::to_string(queuedIcons);
                    m_notificationFramesRemaining = 180;
                } else {
                    m_statusNotification = tr("На всех ваших играх из базы уже стоят HQ-иконки!",
                                              "All matching console games already have HQ icons!");
                    m_notificationFramesRemaining = 150;
                }
            } else if (m_homeFocusedTile == 4) {
                m_autoRotateCoversOnBoot = !m_autoRotateCoversOnBoot;
                saveAppSettings();
                m_statusNotification = m_autoRotateCoversOnBoot
                    ? tr("Авто-ротация слотов при запуске: ВКЛЮЧЕНА", "Auto-rotate cover slots on boot: ENABLED")
                    : tr("Авто-ротация слотов при запуске: ВЫКЛЮЧЕНА", "Auto-rotate cover slots on boot: DISABLED");
                m_notificationFramesRemaining = 140;
            } else if (!m_newlyDetectedTitleIds.empty()) {
                installAllNewlyDetectedGames();
            } else {
                installAllMissing();
            }
            return;
        }
        return;
    } else if (m_activeTab == Tab::VideoIcons) {
        int total = static_cast<int>(m_filteredVideoIcons.size());
        auto notifyVideoIconFocusChanged = [this]() {
            m_cancelCollectionThumb.store(true);
            m_videoPlayer.close();
            if (m_videoIconDockTexture) {
                SDL_DestroyTexture(m_videoIconDockTexture);
                m_videoIconDockTexture = nullptr;
            }
            m_videoIconDockCurrentKey.clear();
            m_videoIconDockDirty = true;
            m_lastVideoIconMoveTime = SDL_GetTicks();
        };
        if (button == 11 /* DPAD_UP */) {
            if (m_videoIconsSelectedIndex > 0) {
                m_videoIconsSelectedIndex--;
                if (m_videoIconsSelectedIndex < m_videoIconsScrollOffset) {
                    m_videoIconsScrollOffset = m_videoIconsSelectedIndex;
                }
                notifyVideoIconFocusChanged();
            }
            return;
        }
        if (button == 12 /* DPAD_DOWN */) {
            if (m_videoIconsSelectedIndex + 1 < total) {
                m_videoIconsSelectedIndex++;
                if (m_videoIconsSelectedIndex >= m_videoIconsScrollOffset + 5) {
                    m_videoIconsScrollOffset = m_videoIconsSelectedIndex - 4;
                }
                notifyVideoIconFocusChanged();
            }
            return;
        }
        if (button == 13 /* DPAD_LEFT - Cycle Icon Variant Prev */) {
            if (m_videoIconsSelectedIndex >= 0 && m_videoIconsSelectedIndex < total) {
                const auto& entry = m_filteredVideoIcons[m_videoIconsSelectedIndex];
                int vCount = static_cast<int>(entry.variants.size());
                if (vCount > 1) {
                    int cur = getSelectedVideoIconVariantIndex(entry);
                    m_videoIconVariantIdx[entry.titleId] = (cur == 0) ? (vCount - 1) : (cur - 1);
                    notifyVideoIconFocusChanged();
                }
            }
            return;
        }
        if (button == 14 /* DPAD_RIGHT - Cycle Icon Variant Next */) {
            if (m_videoIconsSelectedIndex >= 0 && m_videoIconsSelectedIndex < total) {
                const auto& entry = m_filteredVideoIcons[m_videoIconsSelectedIndex];
                int vCount = static_cast<int>(entry.variants.size());
                if (vCount > 1) {
                    int cur = getSelectedVideoIconVariantIndex(entry);
                    m_videoIconVariantIdx[entry.titleId] = (cur + 1) % vCount;
                    notifyVideoIconFocusChanged();
                }
            }
            return;
        }
        if (button == 15 /* ZL - Page Up 8 */) {
            m_videoIconsSelectedIndex = std::max(0, m_videoIconsSelectedIndex - 8);
            m_videoIconsScrollOffset = std::max(0, m_videoIconsScrollOffset - 8);
            notifyVideoIconFocusChanged();
            return;
        }
        if (button == 16 /* ZR - Page Down 8 */) {
            if (total > 0) {
                m_videoIconsSelectedIndex = std::min(total - 1, m_videoIconsSelectedIndex + 8);
                m_videoIconsScrollOffset = std::min(std::max(0, total - 5), m_videoIconsScrollOffset + 8);
                notifyVideoIconFocusChanged();
            }
            return;
        }
        if (button == 0 /* A - Install selected video icon variant */) {
            if (m_videoIconsSelectedIndex >= 0 && m_videoIconsSelectedIndex < total) {
                const auto& entry = m_filteredVideoIcons[m_videoIconsSelectedIndex];
                if (!entry.variants.empty()) {
                    int vIdx = getSelectedVideoIconVariantIndex(entry);
                    const auto& chosenVar = entry.variants[vIdx];
                    if (entry.titleId == "0000000000000000") {
                        Variant icoVar = chosenVar;
                        if (icoVar.id.rfind("icon-", 0) != 0) icoVar.id = "icon-" + icoVar.id;
                        openGamePicker(icoVar, entry.title);
                    } else {
                        InstalledTitle targetGame;
                        targetGame.titleId = entry.titleId;
                        targetGame.name = entry.title;
                        targetGame.hasCatalogMatch = true;
                        targetGame.catalogEntry = entry;
                        queueDownloadIconOnly(targetGame, chosenVar);
                        m_statusNotification = (m_language == Language::Russian)
                            ? ("Добавлена в загрузки: " + entry.title + " (" + chosenVar.name + ")")
                            : ("Queued icon download: " + entry.title + " (" + chosenVar.name + ")");
                        m_notificationFramesRemaining = 120;
                    }
                }
            }
            return;
        }
        if (button == 2 /* X - Единая шторка действий [X] */) {
            openActionSheetForCurrentContext();
            return;
        }
        if (button == 3 /* Y - Всегда Поиск */) {
            openVideoIconsKeyboard();
            return;
        }
        if (button == 4 /* MINUS (-) - Всегда Фильтр */) {
            m_videoIconsFilterMode = (m_videoIconsFilterMode + 1) % 3;
            rebuildVideoIconsFilter();
            notifyVideoIconFocusChanged();
            return;
        }
        return;
    } else if (m_activeTab == Tab::MyGames) {
        if (m_filteredMyGamesIndices.empty() && m_myGamesFilterMode == 0 && m_myGamesSearchQuery.empty()) {
            rebuildMyGamesFilter();
        }
        int filteredCount = static_cast<int>(m_filteredMyGamesIndices.size());

        // [Y] - Всегда Поиск (экранная клавиатура по Моим играм)
        if (button == 3 /* Y */) {
            openMyGamesKeyboard();
            return;
        }

        // [-] (MINUS) - Всегда переключение чип-фильтра (Все / С фоном / Без фона / Новинки ★)
        if (button == 4 /* MINUS (-) */) {
            m_myGamesFilterMode = (m_myGamesFilterMode + 1) % 4;
            if (m_myGamesFilterMode == 3 && m_newlyDetectedTitleIds.empty()) {
                m_myGamesFilterMode = 0;
            }
            rebuildMyGamesFilter();
            const char* fNamesRu[4] = {"Все игры", "С видеофоном", "Без видеофона", "Новинки на консоли ★"};
            const char* fNamesEn[4] = {"All Games", "With Cover", "Missing Cover", "New on Console ★"};
            m_statusNotification = std::string(tr("Фильтр игр: ", "Games Filter: ")) +
                (m_language == Language::English ? fNamesEn[m_myGamesFilterMode] : fNamesRu[m_myGamesFilterMode]);
            m_notificationFramesRemaining = 90;
            return;
        }

        // [X] - Всегда единая шторка контекстных действий!
        if (button == 2 /* X */) {
            openActionSheetForCurrentContext();
            return;
        }

        // [L3] - Быстрый доступ к записям 4IFIR на SD
        if (button == 7 /* L3 */ && filteredCount > 0) {
            int realIdx = m_filteredMyGamesIndices[std::clamp(m_myGamesSelectedIndex, 0, filteredCount - 1)];
            const auto& g = m_installedGames[realIdx];
            openRecordingsBrowser(g.titleId, g.name);
            return;
        }

        if (m_myGamesActivePane == MyGamesPane::GamesList) {
            if (button == 8 /* R3 - Toggle Batch Selection */ && filteredCount > 0) {
                int realIdx = m_filteredMyGamesIndices[std::clamp(m_myGamesSelectedIndex, 0, filteredCount - 1)];
                toggleBatchSelection(m_installedGames[realIdx].titleId);
                return;
            }
            if (button == 11 /* DPAD_UP */) {
                if (m_myGamesSelectedIndex > 0) {
                    m_myGamesSelectedIndex--;
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
            } else if (button == 12 /* DPAD_DOWN */) {
                if (m_myGamesSelectedIndex + 1 < filteredCount) {
                    m_myGamesSelectedIndex++;
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
            } else if (button == 15 /* ZL - Page Up 8 */) {
                m_myGamesSelectedIndex = std::max(0, m_myGamesSelectedIndex - 8);
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
                return;
            } else if (button == 16 /* ZR - Page Down 8 */) {
                if (filteredCount > 0) {
                    m_myGamesSelectedIndex = std::min(filteredCount - 1, m_myGamesSelectedIndex + 8);
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
                return;
            } else if ((button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) && filteredCount > 0) {
                int realIdx = m_filteredMyGamesIndices[std::clamp(m_myGamesSelectedIndex, 0, filteredCount - 1)];
                const auto& g = m_installedGames[realIdx];
                if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                    openCollectionBrowser(g.catalogEntry);
                } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                    m_myGamesActivePane = MyGamesPane::VariantsList;
                    m_selectedVariantIndex = 0;
                } else if (button == 0) {
                    // Идея 2: Обратная привязка кастомного форвардера/репака через умный поиск в Каталоге
                    startForwarderLinkSearch(g);
                }
            }
        } else if (m_myGamesActivePane == MyGamesPane::VariantsList && filteredCount > 0) {
            int realIdx = m_filteredMyGamesIndices[std::clamp(m_myGamesSelectedIndex, 0, filteredCount - 1)];
            const auto& g = m_installedGames[realIdx];
            int vCount = static_cast<int>(g.catalogEntry.variants.size());
            if (button == 11 /* DPAD_UP */) {
                if (m_selectedVariantIndex > 0) {
                    m_selectedVariantIndex--;
                    if (m_selectedVariantIndex < m_variantScrollOffset) {
                        m_variantScrollOffset = m_selectedVariantIndex;
                    }
                }
            } else if (button == 12 /* DPAD_DOWN */) {
                if (m_selectedVariantIndex + 1 < vCount) {
                    m_selectedVariantIndex++;
                    if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                        m_variantScrollOffset = m_selectedVariantIndex - 4 + 1;
                    }
                }
            } else if (button == 15 /* ZL */) {
                m_selectedVariantIndex = std::max(0, m_selectedVariantIndex - 4);
                m_variantScrollOffset = std::min(m_variantScrollOffset, m_selectedVariantIndex);
            } else if (button == 16 /* ZR */) {
                if (vCount > 0) {
                    m_selectedVariantIndex = std::min(vCount - 1, m_selectedVariantIndex + 4);
                    if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                        m_variantScrollOffset = m_selectedVariantIndex - 3;
                    }
                }
            } else if (button == 13 /* DPAD_LEFT */) {
                m_myGamesActivePane = MyGamesPane::GamesList;
            } else if (button == 0 /* A - Install Variant */ && vCount > 0) {
                const auto& selV = g.catalogEntry.variants[std::clamp(m_selectedVariantIndex, 0, vCount - 1)];
                bool isPureIcon = (selV.id.rfind("icon-", 0) == 0) || (selV.width == 256 && selV.height == 256);
                if (isPureIcon) {
                    queueDownloadIconOnly(g, selV);
                    m_statusNotification = tr("Видеоиконка добавлена в загрузки: ", "Queued icon download: ") + g.name;
                    m_notificationFramesRemaining = 120;
                } else {
                    m_pendingActionTitleId = g.titleId;
                    m_pendingActionVariant = selV;
                    m_activeDialog = DialogType::ConfirmInstall;
                    m_dialogOpenedAt = SDL_GetTicks();
                    m_dialogTitle = getStrings(m_language).confirmInstallTitle;
                    m_dialogMessage = (m_language == Language::Russian)
                        ? ("Установить вариант '" + m_pendingActionVariant.name + "' (" + styleToString(m_pendingActionVariant.style) + ") для " + g.name + "?")
                        : ("Install variant '" + m_pendingActionVariant.name + "' (" + styleToString(m_pendingActionVariant.style) + ") for " + g.name + "?");
                    m_dialogFocus = 0;
                }
            }
        }
    } else if (m_activeTab == Tab::Catalog) {
        int totalGames = static_cast<int>(m_filteredCatalogGames.size());
        auto notifyCatalogFocusChanged = [this]() {
            m_cancelCollectionThumb.store(true);
            m_collectionTransferQueued = false;
            m_videoPlayer.close();
            if (m_videoIconDockTexture) {
                SDL_DestroyTexture(m_videoIconDockTexture);
                m_videoIconDockTexture = nullptr;
            }
            m_catalogDockCurrentKey.clear();
            m_catalogDockDirty = true;
            m_lastCatalogMoveTime = SDL_GetTicks();
        };

        // [X] - Всегда единая шторка контекстных действий!
        if (button == 2 /* X */) {
            openActionSheetForCurrentContext();
            return;
        }

        // [Y] - Всегда Поиск (экранная клавиатура)
        if (button == 3 /* Y */) {
            openCatalogKeyboard();
            notifyCatalogFocusChanged();
            return;
        }

        // [-] (Minus) - Всегда переключение чип-фильтров (Идея 6)
        if (button == 4 /* MINUS */) {
            cycleCatalogSortMode();
            notifyCatalogFocusChanged();
            return;
        }

        // [R3] - Быстрый хоткей Избранного
        if (button == 8 /* R3 */ && totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
            const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
            auto covVars = getCoverVariants(curGame);
            if (!covVars.empty()) {
                int vIdx = std::clamp(getSelectedCatalogVariantIndex(curGame), 0, static_cast<int>(covVars.size()) - 1);
                toggleFavoriteVariant(curGame.titleId, covVars[vIdx]);
            } else if (!curGame.variants.empty()) {
                toggleFavoriteVariant(curGame.titleId, curGame.variants[0]);
            }
            return;
        }

        // [L3] - Быстрый полноэкранный просмотр текущего варианта на правом стенде
        if (button == 7 /* L3 */ && totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
            const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
            if (!curGame.variants.empty()) {
                openFullscreenPreviewForCatalogGame(curGame, getSelectedCatalogVariantIndex(curGame));
            }
            return;
        }

        // Navigation
        if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) {
                m_catalogSelectedIndex--;
                notifyCatalogFocusChanged();
            }
            return;
        }
        if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) {
                m_catalogSelectedIndex++;
                notifyCatalogFocusChanged();
            }
            return;
        }
        if (button == 13 /* DPAD_LEFT - Cycle Live Variant on Right Stage (or -5 if single variant) */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
                auto covVars = getCoverVariants(curGame);
                if (covVars.size() > 1) {
                    int cur = getSelectedCatalogVariantIndex(curGame);
                    m_catalogVariantIdx[curGame.titleId] = (cur == 0) ? (static_cast<int>(covVars.size()) - 1) : (cur - 1);
                    notifyCatalogFocusChanged();
                } else if (m_catalogSelectedIndex > 0) {
                    m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
                    notifyCatalogFocusChanged();
                }
            }
            return;
        }
        if (button == 14 /* DPAD_RIGHT - Cycle Live Variant on Right Stage (or +5 if single variant) */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
                auto covVars = getCoverVariants(curGame);
                if (covVars.size() > 1) {
                    int cur = getSelectedCatalogVariantIndex(curGame);
                    m_catalogVariantIdx[curGame.titleId] = (cur + 1) % static_cast<int>(covVars.size());
                    notifyCatalogFocusChanged();
                } else if (m_catalogSelectedIndex + 1 < totalGames) {
                    m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
                    notifyCatalogFocusChanged();
                }
            }
            return;
        }

        // [ZL] / [ZR] - Быстрый постраничный скролл ±8 по Жесткому правилу
        if (button == 15 /* ZL */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 8);
            m_catalogScrollOffset = std::max(0, m_catalogScrollOffset - 8);
            notifyCatalogFocusChanged();
            return;
        }
        if (button == 16 /* ZR */) {
            if (totalGames > 0) {
                m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 8);
                m_catalogScrollOffset = std::min(std::max(0, totalGames - 5), m_catalogScrollOffset + 8);
                notifyCatalogFocusChanged();
            }
            return;
        }

        // [A] - Open Collection Browser modal
        if (button == 0 /* A */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                openCollectionBrowser(m_filteredCatalogGames[m_catalogSelectedIndex]);
            }
            return;
        }
        return;
    } else if (m_activeTab == Tab::Downloads) {
        if (button == 0 /* A - Retry selected failed task or all failed tasks */) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            int qSize = static_cast<int>(m_downloadQueue.size());
            int retried = 0;
            if (m_downloadsSelectedIndex >= 0 && m_downloadsSelectedIndex < qSize &&
                m_downloadQueue[m_downloadsSelectedIndex].state == TaskState::Failed) {
                m_downloadQueue[m_downloadsSelectedIndex].state = TaskState::Pending;
                m_downloadQueue[m_downloadsSelectedIndex].errorMessage.clear();
                retried = 1;
            } else {
                for (auto& t : m_downloadQueue) {
                    if (t.state == TaskState::Failed) {
                        t.state = TaskState::Pending;
                        t.errorMessage.clear();
                        retried++;
                    }
                }
            }
            if (retried > 0) {
                m_statusNotification = (m_language == Language::Russian)
                    ? ("Перезапуск неудачных загрузок: " + std::to_string(retried))
                    : ("Retrying failed tasks: " + std::to_string(retried));
                m_notificationFramesRemaining = 120;
            }
            return;
        } else if (button == 4 /* MINUS (-) - Remove/cancel selected task */) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            int qSize = static_cast<int>(m_downloadQueue.size());
            if (m_downloadsSelectedIndex >= 0 && m_downloadsSelectedIndex < qSize) {
                if (m_downloadQueue[m_downloadsSelectedIndex].state != TaskState::Downloading &&
                    m_downloadQueue[m_downloadsSelectedIndex].state != TaskState::Verifying) {
                    std::string removedTitle = m_downloadQueue[m_downloadsSelectedIndex].gameTitle;
                    m_downloadQueue.erase(m_downloadQueue.begin() + m_downloadsSelectedIndex);
                    if (m_downloadsSelectedIndex >= static_cast<int>(m_downloadQueue.size())) {
                        m_downloadsSelectedIndex = std::max(0, static_cast<int>(m_downloadQueue.size()) - 1);
                    }
                    m_statusNotification = tr("Удалено из очереди: ", "Removed from queue: ") + removedTitle;
                    m_notificationFramesRemaining = 90;
                }
            }
            return;
        } else if (button == 2 /* X - Clear finished/failed tasks */) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            m_downloadQueue.erase(
                std::remove_if(m_downloadQueue.begin(), m_downloadQueue.end(),
                    [](const DownloadTask& t) {
                        return t.state == TaskState::Completed || t.state == TaskState::Failed;
                    }),
                m_downloadQueue.end()
            );
            m_downloadsSelectedIndex = std::clamp(m_downloadsSelectedIndex, 0, std::max(0, static_cast<int>(m_downloadQueue.size()) - 1));
            m_statusNotification = (m_language == Language::Russian) ? "Завершённые задачи очищены" : "Finished tasks cleared";
            m_notificationFramesRemaining = 90;
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_downloadsSelectedIndex > 0) {
                m_downloadsSelectedIndex--;
                if (m_downloadsSelectedIndex < m_downloadsScrollOffset) {
                    m_downloadsScrollOffset = m_downloadsSelectedIndex;
                }
            }
        } else if (button == 12 /* DPAD_DOWN */) {
            int qSize = 0;
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                qSize = static_cast<int>(m_downloadQueue.size());
            }
            if (m_downloadsSelectedIndex + 1 < qSize) {
                m_downloadsSelectedIndex++;
                if (m_downloadsSelectedIndex >= m_downloadsScrollOffset + 5) {
                    m_downloadsScrollOffset = m_downloadsSelectedIndex - 4;
                }
            }
        } else if (button == 15 /* ZL - Page Up 8 */) {
            m_downloadsSelectedIndex = std::max(0, m_downloadsSelectedIndex - 8);
            m_downloadsScrollOffset = std::max(0, m_downloadsScrollOffset - 8);
        } else if (button == 16 /* ZR - Page Down 8 */) {
            int qSize = 0;
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                qSize = static_cast<int>(m_downloadQueue.size());
            }
            if (qSize > 0) {
                m_downloadsSelectedIndex = std::min(qSize - 1, m_downloadsSelectedIndex + 8);
                int maxOff = std::max(0, qSize - 5);
                m_downloadsScrollOffset = std::min(maxOff, m_downloadsScrollOffset + 8);
            }
        } else if (button == 3 /* Y - Search in Catalog */) {
            m_activeTab = Tab::Catalog;
            openCatalogKeyboard();
        }
    } else if (m_activeTab == Tab::Settings) {
        if (button == 11 /* DPAD_UP */) {
            if (m_settingsSelectedIndex > 0) m_settingsSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_settingsSelectedIndex < 7) m_settingsSelectedIndex++;
        } else if (button == 0 /* A - Activate Selected Setting */) {
            switch (m_settingsSelectedIndex) {
                case 0: // Check & Update NRO
                    updateApplicationNro();
                    break;
                case 1: // Refresh Catalog (Turbo .gz)
                    fetchRemoteCatalog();
                    break;
                case 2: // Идея 4: Toggle Auto-Rotation of Multi-Cover Slots on Boot
                    m_autoRotateCoversOnBoot = !m_autoRotateCoversOnBoot;
                    saveAppSettings();
                    m_statusNotification = m_autoRotateCoversOnBoot
                        ? tr("Авто-ротация слотов при входе: ВКЛ", "Auto-rotate cover slots on boot: ON")
                        : tr("Авто-ротация слотов при входе: ВЫКЛ", "Auto-rotate cover slots on boot: OFF");
                    m_notificationFramesRemaining = 120;
                    break;
                case 3: // Clear thumbnail previews cache
                    clearThumbnailCache();
                    break;
                case 4: // Clear video player cache
                    clearVideoPreviewCache();
                    break;
                case 5: // Clear Local Catalog Cache (cache.json)
                    m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
                    refreshInstalledGames();
                    m_statusNotification = getStrings(m_language).cacheClearedMsg;
                    m_notificationFramesRemaining = 120;
                    break;
                case 6: // Integrity check
                    runIntegrityCheck();
                    break;
                case 7: // Toggle Language
                    m_language = (m_language == Language::Russian) ? Language::English : Language::Russian;
                    saveAppSettings();
                    m_statusNotification = (m_language == Language::Russian) ? "Язык интерфейса: Русский" : "Interface language: English";
                    m_notificationFramesRemaining = 120;
                    break;
            }
        } else if (button == 2 /* X - Refresh Catalog */) {
            fetchRemoteCatalog();
        } else if (button == 3 /* Y - Search Catalog */) {
            m_activeTab = Tab::Catalog;
            openCatalogKeyboard();
        }
    }
}

void App::render() {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    m_renderFrameIndex++;

    if (m_isFullscreenPreview) {
        renderFullscreenPreview();
        SDL_RenderPresent(m_renderer);
        return;
    }

    // Clear background with hardware buffer clear
    SDL_SetRenderDrawColor(m_renderer, Theme::COLOR_BG_BASE.r, Theme::COLOR_BG_BASE.g, Theme::COLOR_BG_BASE.b, 255);
    SDL_RenderClear(m_renderer);

    renderHeader();

    switch (m_activeTab) {
        case Tab::Home:       renderTabHome(); break;
        case Tab::Catalog:    renderTabCatalog(); break;
        case Tab::VideoIcons: renderTabVideoIcons(); break;
        case Tab::MyGames:    renderTabMyGames(); break;
        case Tab::Downloads:  renderTabDownloads(); break;
        case Tab::Settings:   renderTabSettings(); break;
    }

    renderFooter();

    if (m_isRecordingsBrowserOpen) {
        renderRecordingsBrowser();
    }
    if (m_isCollectionBrowserOpen) {
        renderCollectionBrowser();
    }
    if (m_isGamePickerOpen) {
        renderGamePicker();
    }
    if (m_isActionSheetOpen) {
        renderActionSheet();
    }

    if (m_activeDialog != DialogType::None) {
        renderDialog();
    }

    // Alpha-Jump (Right Stick A–Z) Glass HUD Overlay
    if (m_alphaJumpFrames > 0) {
        int aw = 148, ah = 148;
        int ax = (Theme::SCREEN_WIDTH - aw) / 2;
        int ay = (Theme::SCREEN_HEIGHT - ah) / 2 - 20;
        drawRoundedRect(ax, ay, aw, ah, 28, {0x09, 0x11, 0x1E, 0xEE});
        drawNeonRoundedOutline(ax, ay, aw, ah, 28, 3);
        drawTextCentered(m_alphaJumpText, Theme::SCREEN_WIDTH / 2, ay + 34, Theme::COLOR_FOCUS_CYAN, 48);
        drawTextCentered(tr("АЛФАВИТ R↕", "A–Z JUMP R↕"), Theme::SCREEN_WIDTH / 2, ay + 112, Theme::COLOR_TEXT_MUTED, 11);
        m_alphaJumpFrames--;
    }

    // Status notification overlay
    if (m_notificationFramesRemaining > 0) {
        int notifW = std::clamp(measureTextWidth(m_statusNotification, 14) + 48, 320, 880);
        int notifX = (Theme::SCREEN_WIDTH - notifW) / 2;
        drawRoundedRect(notifX, 622, notifW, 36, 10, Theme::COLOR_BG_ELEVATED);
        drawNeonRoundedOutline(notifX, 622, notifW, 36, 10, 2);
        drawTextCentered(m_statusNotification, Theme::SCREEN_WIDTH / 2, 631, Theme::COLOR_FOCUS_CYAN, 14);
        m_notificationFramesRemaining--;
    }

    SDL_RenderPresent(m_renderer);
#endif
}

void App::renderHeader() {
    const auto& s = getStrings(m_language);
    (void)s;

    // 4IFIR Cyber-Glass Top Bar (matching TorrentShopNX Header)
    drawRect(0, 0, Theme::SCREEN_WIDTH, 64, Theme::COLOR_BG_HEADER);
    drawRect(0, 63, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // Left Branding: App Name + Tag Badge
    // Triple animated equalizer accent bars (Cyber Audio Visualizer)
    int h0 = static_cast<int>(m_equalizerHeights[0]);
    int h1 = static_cast<int>(m_equalizerHeights[1]);
    int h2 = static_cast<int>(m_equalizerHeights[2]);
    drawRoundedRect(30, 42 - h0, 4, h0, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(38, 44 - h1, 4, h1, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(46, 42 - h2, 4, h2, 2, Theme::COLOR_FOCUS_CYAN);

    // App Title
    drawText(Config::APP_NAME, 62, 18, Theme::COLOR_TEXT_PRIMARY, 20);
    int titleW = measureTextWidth(Config::APP_NAME, 20);

    // Version Tag Pill
#ifdef H3H_AFTER_DARK
    std::string tagText = "18+";
#else
    std::string tagText = "NX";
#endif
    int nxW = measureTextWidth(tagText, 12) + 16;
    int nxX = 64 + titleW + 12;
    drawRoundedRect(nxX, 20, nxW, 24, 6, Theme::COLOR_FOCUS_CYAN);
    drawTextCentered(tagText, nxX + nxW / 2, 24, Theme::COLOR_BG_BASE, 12);

    std::string verText = "v" + std::string(Config::APP_VERSION);
    drawText(verText, nxX + nxW + 8, 24, Theme::COLOR_TEXT_MUTED, 12);

    // Global Unified Top Tab Strip: [L] Главная | Каталог | Иконки | Мои игры | Загрузки | Настройки [R]
    const char* tabLabelsRu[6] = {"Главная", "Каталог", "Иконки", "Мои игры", "Загрузки", "Настройки"};
    const char* tabLabelsEn[6] = {"Home", "Catalog", "Icons", "My Games", "Queue", "Settings"};
    int stripStartX = 310;
    int stripY = 16;
    drawRoundedRect(stripStartX, stripY + 4, 24, 24, 5, {0x16, 0x20, 0x32, 0xEE});
    drawRoundedOutline(stripStartX, stripY + 4, 24, 24, 5, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered("L", stripStartX + 12, stripY + 9, Theme::COLOR_FOCUS_CYAN, 11);

    int tCurX = stripStartX + 28;
    int tItemW = 82;
    int tGap = 4;
    for (int ti = 0; ti < 6; ++ti) {
        bool isCur = (static_cast<int>(m_activeTab) == ti);
        drawRoundedRect(tCurX, stripY, tItemW, 32, 8, isCur ? Theme::COLOR_FOCUS_FILL : Color{0x10, 0x17, 0x26, 0xCC});
        if (isCur) {
            drawNeonRoundedOutline(tCurX, stripY, tItemW, 32, 8, 2);
        } else {
            drawRoundedOutline(tCurX, stripY, tItemW, 32, 8, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        }
        const char* lbl = (m_language == Language::English) ? tabLabelsEn[ti] : tabLabelsRu[ti];
        drawTextCentered(lbl, tCurX + tItemW / 2, stripY + 9, isCur ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 11, tItemW - 6);
        if (ti == 3 && !m_newlyDetectedTitleIds.empty()) {
            drawCircle(tCurX + tItemW - 7, stripY + 7, 4, Theme::COLOR_WARNING, true);
        }
        tCurX += tItemW + tGap;
    }
    drawRoundedRect(tCurX, stripY + 4, 24, 24, 5, {0x16, 0x20, 0x32, 0xEE});
    drawRoundedOutline(tCurX, stripY + 4, 24, 24, 5, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered("R", tCurX + 12, stripY + 9, Theme::COLOR_FOCUS_CYAN, 11);

    // Live Active Download status or Catalog + New Games indicator on the right (x = 890..1244)
    bool hasActiveDownload = false;
    double activePct = 0.0;
    double activeSpeedKb = 0.0;
    int pendingTotal = 0;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        for (const auto& t : m_downloadQueue) {
            if (t.state == TaskState::Downloading || t.state == TaskState::Verifying) {
                hasActiveDownload = true;
                activePct = t.progressPercent;
                activeSpeedKb = t.downloadSpeedBps / 1024.0;
                pendingTotal++;
            } else if (t.state == TaskState::Pending) {
                pendingTotal++;
            }
        }
    }

    if (hasActiveDownload) {
        int pillX = 944;
        int pillY = 10;
        int pillW = 300;
        int pillH = 24;
        drawRoundedRect(pillX, pillY, pillW, pillH, 6, {0x0E, 0x17, 0x26, 0xF2});
        drawNeonRoundedOutline(pillX, pillY, pillW, pillH, 6, 1);
        drawLoadingSpinner(pillX + 14, pillY + 12, 5, Theme::COLOR_FOCUS_CYAN);
        char dlBuf[96];
        if (activeSpeedKb >= 1024.0) {
            std::snprintf(dlBuf, sizeof(dlBuf), "%s %d%% (%.1f MB/s) [%d]",
                          tr("Загрузка:", "DL:"),
                          static_cast<int>(activePct), activeSpeedKb / 1024.0, pendingTotal);
        } else {
            std::snprintf(dlBuf, sizeof(dlBuf), "%s %d%% (%d KB/s) [%d]",
                          tr("Загрузка:", "DL:"),
                          static_cast<int>(activePct), static_cast<int>(activeSpeedKb), pendingTotal);
        }
        drawText(dlBuf, pillX + 26, pillY + 5, Theme::COLOR_FOCUS_CYAN, 11, pillW - 32);
    } else if (!m_newlyDetectedTitleIds.empty()) {
        std::string newBadge = tr("★ Новинки на консоли: ", "★ New on Console: ") + std::to_string(m_newlyDetectedTitleIds.size());
        drawTextRight(newBadge, 1244, 13, Theme::COLOR_WARNING, 12);
    } else {
        size_t catGames = m_catalogManager.getGamesCount();
        size_t catIcons = m_videoIconsCatalog.size();
        std::string metaLine1 = (m_language == Language::Russian)
            ? ("База: " + std::to_string(catGames) + " игр • " + std::to_string(catIcons) + " HQ-иконок")
            : ("DB: " + std::to_string(catGames) + " games • " + std::to_string(catIcons) + " HQ icons");
        drawTextRight(metaLine1, 1244, 13, Theme::COLOR_TEXT_SECONDARY, 12);
    }

    double freeSdGb = static_cast<double>(m_sysInfo.freeStorageBytes) / (1024.0 * 1024.0 * 1024.0);
    double totalSdGb = static_cast<double>(m_sysInfo.totalStorageBytes) / (1024.0 * 1024.0 * 1024.0);
    if (totalSdGb <= 0.1) {
        totalSdGb = 220.1;
        freeSdGb = 49.2;
    }
    char sdBuf[128];
    std::snprintf(sdBuf, sizeof(sdBuf), "SD: %.1f / %.1f GB • [+] OTA", freeSdGb, totalSdGb);
    drawTextRight(sdBuf, 1244, 37, Theme::COLOR_TEXT_MUTED, 11);
}

void App::renderFooter() {
    const auto& s = getStrings(m_language);
    (void)s;

    // Bottom Bar Background
    drawRect(0, 665, Theme::SCREEN_WIDTH, 55, Theme::COLOR_STATUS_BAR_BG);
    drawRect(0, 665, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // Left: Battery glyph & %, Wi-Fi, Clock
    int battX = 30;
    drawRoundedRect(battX, 683, 30, 16, 3, {0x1C, 0x24, 0x33, 0xFF});
    drawRoundedOutline(battX, 683, 30, 16, 3, Theme::COLOR_TEXT_MUTED, Theme::COLOR_TEXT_MUTED, 1);
    drawRoundedRect(battX + 30, 687, 3, 8, 1, Theme::COLOR_TEXT_MUTED);
    int fillW = std::clamp((m_sysInfo.batteryPercent * 26) / 100, 2, 26);
    Color battCol = (m_sysInfo.batteryPercent < 20) ? Theme::COLOR_DANGER : (m_sysInfo.batteryPercent < 50 ? Theme::COLOR_WARNING : Theme::COLOR_SUCCESS);
    drawRoundedRect(battX + 2, 685, fillW, 12, 2, battCol);

    std::string battStr = std::to_string(m_sysInfo.batteryPercent) + "%";
    drawText(battStr, battX + 38, 683, Theme::COLOR_TEXT_PRIMARY, 13);
    int curLeftX = battX + 38 + measureTextWidth(battStr, 13) + 14;

    drawWifiIcon(curLeftX + 6, 691, m_sysInfo.isNetworkConnected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED);
    curLeftX += 18;

    std::string netStr = m_sysInfo.isNetworkConnected ? tr("Онлайн", "Online") : tr("Офлайн", "Offline");
    drawText(netStr, curLeftX, 683, m_sysInfo.isNetworkConnected ? Theme::COLOR_SUCCESS : Theme::COLOR_TEXT_MUTED, 13);
    curLeftX += measureTextWidth(netStr, 13) + 14;

    std::time_t now = std::time(nullptr);
    std::tm* tmLocal = std::localtime(&now);
    char timeBuf[32];
    if (tmLocal) {
        std::strftime(timeBuf, sizeof(timeBuf), "%H:%M", tmLocal);
    } else {
        std::snprintf(timeBuf, sizeof(timeBuf), "14:33");
    }
    drawText(timeBuf, curLeftX, 683, Theme::COLOR_TEXT_PRIMARY, 14);

    // Right: Unified Strict Button Contract Prompts (Identical muscle memory across tabs!)
    int curRightX = 1248;
    auto drawPrompt = [&](const std::string& key, const std::string& label, Color badgeCol = Theme::COLOR_TEXT_PRIMARY) {
        int labelW = measureTextWidth(label, 12);
        int itemW = 22 + 6 + labelW;
        int itemX = curRightX - itemW;
        drawButtonBadge(itemX, 682, key, label, badgeCol);
        curRightX = itemX - 16;
    };

    if (m_activeTab == Tab::Home) {
        drawPrompt("A", tr("Открыть", "Open"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Выход", "Exit"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("X", !m_newlyDetectedTitleIds.empty() ? tr("Меню [★]", "Actions [★]") : tr("Обновить базу", "Refresh DB"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("Y", tr("Поиск", "Search"), Theme::COLOR_FOCUS_PINK);
        std::string minusFooterLbl;
        Color minusFooterCol = Theme::COLOR_WARNING;
        if (m_homeFocusedTile == 1) {
            minusFooterLbl = tr("HQ-иконки", "HQ Icons");
            minusFooterCol = Theme::COLOR_FOCUS_PINK;
        } else if (m_homeFocusedTile == 4) {
            minusFooterLbl = tr("Авто-ротация", "Auto-Rotate");
            minusFooterCol = Theme::COLOR_WARNING;
        } else if (!m_newlyDetectedTitleIds.empty()) {
            minusFooterLbl = tr("Новинки ★", "Install New ★");
        } else {
            minusFooterLbl = tr("Все недостающие", "Install Missing");
        }
        drawPrompt("-", minusFooterLbl, minusFooterCol);
        drawPrompt("L/R", tr("Разделы", "Tabs"), Theme::COLOR_FOCUS_CYAN);
    } else if (m_activeTab == Tab::Catalog || m_activeTab == Tab::VideoIcons || m_activeTab == Tab::MyGames) {
        drawPrompt("A", (m_activeTab == Tab::VideoIcons) ? tr("Установить", "Install") : tr("Выбрать", "Select"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Назад", "Back"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("X", tr("Действия", "Actions"), Theme::COLOR_FOCUS_PINK);
        drawPrompt("Y", tr("Поиск", "Search"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("-", tr("Фильтр", "Filter"), Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("R↕", tr("А–Я", "A–Z"), Theme::COLOR_WARNING);
        drawPrompt("L/R", tr("Разделы", "Tabs"), Theme::COLOR_FOCUS_CYAN);
    } else if (m_activeTab == Tab::Downloads) {
        drawPrompt("A", tr("Повторить", "Retry"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Назад", "Back"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("X", tr("Очистить", "Clear"), Theme::COLOR_DANGER);
        drawPrompt("Y", tr("Поиск", "Search"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("-", tr("Убрать", "Remove"), Theme::COLOR_FOCUS_PINK);
        drawPrompt("L/R", tr("Разделы", "Tabs"), Theme::COLOR_FOCUS_CYAN);
    } else if (m_activeTab == Tab::Settings) {
        drawPrompt("A", tr("Применить", "Apply"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Назад", "Back"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("X", tr("Обновить базу", "Refresh DB"), Theme::COLOR_FOCUS_PINK);
        drawPrompt("+", tr("Обновить NRO", "Update NRO"), Theme::COLOR_WARNING);
        drawPrompt("L/R", tr("Разделы", "Tabs"), Theme::COLOR_FOCUS_CYAN);
    }
}

void App::renderTabHome() {
    const auto& s = getStrings(m_language);
    (void)s;

    size_t totalGames = m_catalogManager.getGamesCount();
    size_t totalVariants = m_catalogManager.getTotalVariantsCount();
    size_t totalIcons = m_videoIconsCatalog.size();
    size_t totalIconVariants = 0;
    for (const auto& icEntry : m_videoIconsCatalog) {
        totalIconVariants += icEntry.variants.size();
    }

    int installedRealCount = 0;
    int installedCoveredCount = 0;
    int installedIconsCount = 0;
    for (const auto& ig : m_installedGames) {
        if (ig.titleId.empty() || ig.titleId == "0000000000000000") continue;
        installedRealCount++;
        if (ig.hasInstalledCover) installedCoveredCount++;
        if (ig.hasInstalledIcon) installedIconsCount++;
    }

    int activeQueueTasks = 0;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        for (const auto& t : m_downloadQueue) {
            if (t.state != TaskState::Completed) activeQueueTasks++;
        }
    }

    double freeSdGb = static_cast<double>(m_sysInfo.freeStorageBytes) / (1024.0 * 1024.0 * 1024.0);
    if (freeSdGb <= 0.1) freeSdGb = 49.2;

    // =========================================================================================
    // 1. ВЕРХНЯЯ ПАНОРАМА: HORIZON CYBER-STAGE (x = 40, y = 78, w = 1200, h = 294)
    // =========================================================================================
    int stageX = 40;
    int stageY = 78;
    int stageW = 1200;
    int stageH = 294;
    drawGlassCard(stageX, stageY, stageW, stageH, false, true);
    drawNeonRoundedOutline(stageX, stageY, stageW, stageH, 18, 2);

    // Левый блок панорамы: Инфо-хаб активного раздела (x = 64, w = 608)
    int lx = stageX + 26;
    int ly = stageY + 20;

    std::string pillTag, heroTitle, heroSub1, heroSub2;
    Color accentCol = Theme::COLOR_FOCUS_CYAN;

    if (m_homeFocusedTile == 0) {
#ifdef H3H_AFTER_DARK
        pillTag = tr("AFTER DARK 18+ • SPLIT-STUDIO 16:9 + 1:1", "AFTER DARK 18+ • SPLIT-STUDIO 16:9 + 1:1");
        heroTitle = tr("Коллекция видеофонов After Dark", "After Dark Live Video Studio");
#else
        pillTag = tr("SPLIT-STUDIO • КАТАЛОГ 16:9 + 1:1", "SPLIT-STUDIO • 16:9 + 1:1 CATALOG");
        heroTitle = tr("Живой каталог видеофонов", "Live Video Backgrounds Studio");
#endif
        heroSub1 = std::to_string(totalGames) + tr(" игр в базе  •  ", " games in DB  •  ") +
                   std::to_string(totalVariants) + tr(" HD-вариантов", " HD variants");
        heroSub2 = tr("Список слева + живое комбо-превью 16:9 и 256x256 прямо справа без лишних окон!",
                      "Split list on the left + live 16:9 & 256x256 combo stage on the right!");
        accentCol = Theme::COLOR_FOCUS_CYAN;
    } else if (m_homeFocusedTile == 1) {
        pillTag = tr("ULTRA-HQ 256x256 • LANCZOS + CAS", "ULTRA-HQ 256x256 • LANCZOS + CAS");
        heroTitle = tr("Живые видеоиконки Horizon OS", "Horizon OS Live Video Icons");
        heroSub1 = std::to_string(totalIcons) + tr(" игр (", " games (") + std::to_string(totalIconVariants) +
                   tr(" иконок)  •  ", " icons)  •  ") +
                   std::to_string(installedIconsCount) + tr(" активно на Switch", " active on Switch");
        heroSub2 = tr("Бесшовный цикл xfade, четкость CAS и высокий профиль H.264 без мыла и рывков.",
                      "Seamless xfade loop, CAS sharpening & High Profile H.264 clarity.");
        accentCol = Theme::COLOR_FOCUS_PINK;
    } else if (m_homeFocusedTile == 2) {
        pillTag = tr("МОЯ КОНСОЛЬ • МУЛЬТИ-СЛОТЫ И ФОРВАРДЕРЫ", "MY CONSOLE • MULTI-SLOTS & FORWARDERS");
        heroTitle = tr("Менеджер установленных игр", "Installed Console Games Manager");
        heroSub1 = tr("На вашей консоли: ", "On console: ") + std::to_string(installedRealCount) +
                   tr(" игр  •  Оформлено: ", " games  •  Styled: ") + std::to_string(installedCoveredCount);
        heroSub2 = tr("Ротация до 4 видеофонов на одну игру и привязка любых кастомных портов в 1 клик.",
                      "Up to 4 cover rotation slots per game & 1-click forwarder binding.");
        accentCol = Theme::COLOR_SUCCESS;
    } else if (m_homeFocusedTile == 3) {
        pillTag = tr("TURBO STREAM • ПОТОКОВАЯ ОЧЕРЕДЬ", "TURBO STREAM • DOWNLOAD QUEUE");
        heroTitle = tr("Менеджер загрузок 4IFIR", "4IFIR Streaming Queue");
        heroSub1 = tr("Активных задач в очереди: ", "Active tasks in queue: ") + std::to_string(activeQueueTasks);
        heroSub2 = tr("Фоновая докачка фонов и HQ-иконок с мгновенной активацией на SD-карте.",
                      "Background streaming for covers & HQ icons with instant SD activation.");
        accentCol = Theme::COLOR_FOCUS_CYAN;
    } else {
        pillTag = tr("СИСТЕМА • ПАМЯТЬ MICROSD И OTA", "SYSTEM • MICROSD STORAGE & OTA");
        heroTitle = tr("Настройки, кэш и авто-ротация", "Settings, Cache & Auto-Rotation");
        char sdLine[96];
        std::snprintf(sdLine, sizeof(sdLine), "%s %.1f GB  •  %s %s",
                      tr("Свободно на SD:", "Free on SD:"), freeSdGb,
                      tr("Авто-ротация:", "Auto-Rotate:"),
                      m_autoRotateCoversOnBoot ? tr("ВКЛ", "ON") : tr("ВЫКЛ", "OFF"));
        heroSub1 = sdLine;
        heroSub2 = tr("Турбо-обновление сжатой базы (.gz), проверка целостности и очистка кэша.",
                      "Compressed (.gz) catalog sync, integrity check & cache cleanup.");
        accentCol = Theme::COLOR_WARNING;
    }

    int pTagW = measureTextWidth(pillTag, 11) + 22;
    drawRoundedRect(lx, ly, pTagW, 24, 6, {accentCol.r, accentCol.g, accentCol.b, 0x26});
    drawRoundedOutline(lx, ly, pTagW, 24, 6, accentCol, accentCol, 1);
    drawTextCentered(pillTag, lx + pTagW / 2, ly + 5, accentCol, 11);

    if (!m_newlyDetectedTitleIds.empty()) {
        std::string newStr = tr("★ Новинки: ", "★ New: ") + std::to_string(m_newlyDetectedTitleIds.size());
        int nw = measureTextWidth(newStr, 11) + 18;
        int nx = lx + pTagW + 10;
        drawRoundedRect(nx, ly, nw, 24, 6, {0xF5, 0x9E, 0x0B, 0x30});
        drawRoundedOutline(nx, ly, nw, 24, 6, Theme::COLOR_WARNING, Theme::COLOR_WARNING, 1);
        drawTextCentered(newStr, nx + nw / 2, ly + 5, Theme::COLOR_WARNING, 11);
    }

    drawText(heroTitle, lx, ly + 36, Theme::COLOR_TEXT_PRIMARY, 24, 595);
    drawText(heroSub1, lx, ly + 74, accentCol, 15, 595);
    drawText(heroSub2, lx, ly + 104, Theme::COLOR_TEXT_MUTED, 12, 595);

    // Мини-метрики консоли в ряд (3 стеклянных чипа)
    int chipY = ly + 142;
    struct MiniMetric {
        std::string val;
        std::string lbl;
        Color col;
    };
    MiniMetric metrics[3] = {
        {std::to_string(totalVariants), tr("720p Фонов", "720p Covers"), Theme::COLOR_FOCUS_CYAN},
        {std::to_string(totalIcons), tr("HQ Иконок 1:1", "HQ 1:1 Icons"), Theme::COLOR_FOCUS_PINK},
        {std::to_string(installedCoveredCount) + "/" + std::to_string(std::max(1, installedRealCount)),
         tr("На Switch", "On Switch"), Theme::COLOR_SUCCESS}
    };
    int mxPos = lx;
    for (int m = 0; m < 3; ++m) {
        drawRoundedRect(mxPos, chipY, 186, 52, 10, {0x0E, 0x15, 0x24, 0xEE});
        drawRoundedOutline(mxPos, chipY, 186, 52, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        drawText(metrics[m].val, mxPos + 14, chipY + 7, metrics[m].col, 17, 160);
        drawText(metrics[m].lbl, mxPos + 14, chipY + 30, Theme::COLOR_TEXT_MUTED, 11, 160);
        mxPos += 196;
    }

    int missingIconsForConsole = 0;
    for (const auto& ig : m_installedGames) {
        if (ig.titleId.empty() || ig.titleId == "0000000000000000" || ig.hasInstalledIcon || !ig.hasCatalogMatch) continue;
        if (!getUniqueIconVariants(ig.catalogEntry).empty()) {
            missingIconsForConsole++;
        }
    }

    // Две крупные кнопки быстрого действия в панораме (y = ly + 208 = 306, h = 42)
    int actY = ly + 208;
    drawRoundedRect(lx, actY, 245, 42, 10, Theme::COLOR_FOCUS_FILL);
    drawNeonRoundedOutline(lx, actY, 245, 42, 10, 2);
    drawTextCentered(tr("[A] Открыть раздел", "[A] Open Section"), lx + 122, actY + 13, Theme::COLOR_FOCUS_CYAN, 13);

    std::string minusBtnTxt;
    Color minusCol = Theme::COLOR_FOCUS_PINK;
    if (m_homeFocusedTile == 1) {
        minusBtnTxt = (missingIconsForConsole > 0)
            ? (tr("[-] Поставить HQ-иконки (", "[-] Install HQ Icons (") + std::to_string(missingIconsForConsole) + ")")
            : tr("[-] Все HQ-иконки стоят ✓", "[-] All HQ Icons Set ✓");
        minusCol = (missingIconsForConsole > 0) ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_SUCCESS;
    } else if (m_homeFocusedTile == 4) {
        minusBtnTxt = m_autoRotateCoversOnBoot
            ? tr("[-] Авто-ротация: ВКЛ", "[-] Auto-Rotate: ON")
            : tr("[-] Авто-ротация: ВЫКЛ", "[-] Auto-Rotate: OFF");
        minusCol = m_autoRotateCoversOnBoot ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING;
    } else if (!m_newlyDetectedTitleIds.empty()) {
        minusBtnTxt = tr("[-] Комбо новинок (", "[-] Auto-Combo New (") + std::to_string(m_newlyDetectedTitleIds.size()) + ")";
        minusCol = Theme::COLOR_WARNING;
    } else {
        minusBtnTxt = tr("[-] Оформить недостающие", "[-] Install All Missing");
        minusCol = Theme::COLOR_FOCUS_PINK;
    }
    drawRoundedRect(lx + 258, actY, 320, 42, 10, {minusCol.r, minusCol.g, minusCol.b, 0x22});
    drawRoundedOutline(lx + 258, actY, 320, 42, 10, minusCol, minusCol, 1);
    drawTextCentered(minusBtnTxt, lx + 258 + 160, actY + 13, minusCol, 13, 304);

    // =========================================================================================
    // ПРАВЫЙ БЛОК ПАНОРАМЫ: РЕАЛЬНЫЙ ЖИВОЙ ПУЛЬТ ВАШЕЙ КОНСОЛИ (x = 698, y = 96, w = 516, h = 258)
    // Показывает реальные игры со Switch, доступные им HQ-иконки, живую очередь или память SD!
    // =========================================================================================
    int mockX = stageX + 658;
    int mockY = stageY + 18;
    int mockW = 516;
    int mockH = 258;
    drawRoundedRect(mockX, mockY, mockW, mockH, 14, {0x09, 0x10, 0x1D, 0xFA});
    drawRoundedOutline(mockX, mockY, mockW, mockH, 14, accentCol, Theme::COLOR_BORDER, 2);

    if (m_homeFocusedTile == 0 || m_homeFocusedTile == 2) {
        // Реальный список игр с вашей консоли (в первую очередь — без оформления, готовые к прокачке!)
        drawText(tr("ВАША КОНСОЛЬ • БЫСТРЫЙ РАДАР ИГР", "YOUR CONSOLE • QUICK GAME RADAR"),
                 mockX + 16, mockY + 13, accentCol, 11);
        int unstyledReady = getMissingCoversCount();
        std::string rightHdr = (unstyledReady > 0)
            ? (tr("Ждут фон: ", "Missing: ") + std::to_string(unstyledReady))
            : tr("Все с фонами ✓", "All styled ✓");
        drawTextRight(rightHdr, mockX + mockW - 16, mockY + 13,
                      unstyledReady > 0 ? Theme::COLOR_WARNING : Theme::COLOR_SUCCESS, 11);
        drawRect(mockX + 16, mockY + 34, mockW - 32, 1, Theme::COLOR_BORDER);

        std::vector<int> radarIdx;
        // 1) Сначала игры на консоли без фона, но с готовым совпадением в базе
        for (int idx = 0; idx < static_cast<int>(m_installedGames.size()); ++idx) {
            const auto& g = m_installedGames[idx];
            if (g.titleId.empty() || g.titleId == "0000000000000000") continue;
            if (!g.hasInstalledCover && g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                radarIdx.push_back(idx);
            }
        }
        // 2) Затем игры с фоном, но без доступной в базе HQ-иконки
        for (int idx = 0; idx < static_cast<int>(m_installedGames.size()) && radarIdx.size() < 4; ++idx) {
            const auto& g = m_installedGames[idx];
            if (g.titleId.empty() || g.titleId == "0000000000000000") continue;
            if (g.hasInstalledCover && !g.hasInstalledIcon && g.hasCatalogMatch && !getUniqueIconVariants(g.catalogEntry).empty()) {
                if (std::find(radarIdx.begin(), radarIdx.end(), idx) == radarIdx.end()) radarIdx.push_back(idx);
            }
        }
        // 3) Затем кастомные порты без привязки и остальные установленные игры
        for (int idx = 0; idx < static_cast<int>(m_installedGames.size()) && radarIdx.size() < 4; ++idx) {
            const auto& g = m_installedGames[idx];
            if (g.titleId.empty() || g.titleId == "0000000000000000") continue;
            if (std::find(radarIdx.begin(), radarIdx.end(), idx) == radarIdx.end()) radarIdx.push_back(idx);
        }

        if (radarIdx.empty()) {
            std::string emptyHint = tr("Нажмите [A], чтобы открыть каталог (", "Press [A] to browse catalog (") +
                                    std::to_string(totalGames) + tr(" игр)", " titles)");
            drawTextCentered(emptyHint,
                             mockX + mockW / 2, mockY + 122, Theme::COLOR_TEXT_MUTED, 13, mockW - 40);
        } else {
            int ry = mockY + 42;
            for (size_t k = 0; k < std::min<size_t>(4, radarIdx.size()); ++k) {
                const auto& g = m_installedGames[radarIdx[k]];
                drawRoundedRect(mockX + 14, ry, mockW - 28, 48, 9, {0x11, 0x19, 0x2B, 0xEE});
                drawRoundedOutline(mockX + 14, ry, mockW - 28, 48, 9, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);

                // Мини-обложка 36x36
                int tx = mockX + 22, ty = ry + 6;
                drawRoundedRect(tx, ty, 36, 36, 7, {0x18, 0x22, 0x36, 0xFF});
                if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                    const auto& fv = g.catalogEntry.variants[0];
                    std::string rUrl = fv.previewUrl;
                    if (rUrl.empty()) {
                        std::string dId = extractDriveIdFromUrl(fv.url);
                        if (!dId.empty()) rUrl = "https://drive.google.com/thumbnail?id=" + dId + "&sz=w320";
                    }
                    SDL_Texture* mt = getOrRequestRowThumb(g.titleId + "_" + fv.id, rUrl, k == 0);
                    if (mt) {
                        SDL_Rect md{tx + 1, ty + 1, 34, 34};
                        SDL_RenderCopy(m_renderer, mt, nullptr, &md);
                    }
                }

                drawText(g.name, tx + 46, ry + 7, Theme::COLOR_TEXT_PRIMARY, 13, 285);
                std::string subLine = g.hasCatalogMatch
                    ? (std::to_string(getCoverVariants(g.catalogEntry).size()) + tr(" фон.", " cov.") +
                       (!getUniqueIconVariants(g.catalogEntry).empty() ? " + HQ 256x256" : ""))
                    : tr("Кастомный порт • Нажмите для привязки", "Custom port • Tap to bind");
                drawText(subLine, tx + 46, ry + 26, Theme::COLOR_TEXT_MUTED, 10, 285);

                // Кнопка-статус справа (тап ставит комбо или открывает игру!)
                int bx = mockX + mockW - 134;
                if (!g.hasInstalledCover && g.hasCatalogMatch) {
                    drawRoundedRect(bx, ry + 11, 112, 26, 6, Theme::COLOR_FOCUS_FILL);
                    drawRoundedOutline(bx, ry + 11, 112, 26, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
                    drawTextCentered(tr("+ Установить", "+ Install"), bx + 56, ry + 17, Theme::COLOR_FOCUS_CYAN, 10);
                } else if (!g.hasInstalledIcon && g.hasCatalogMatch && !getUniqueIconVariants(g.catalogEntry).empty()) {
                    drawRoundedRect(bx, ry + 11, 112, 26, 6, {0xEC, 0x48, 0x99, 0x2A});
                    drawRoundedOutline(bx, ry + 11, 112, 26, 6, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
                    drawTextCentered(tr("+ HQ Иконка", "+ HQ Icon"), bx + 56, ry + 17, Theme::COLOR_FOCUS_PINK, 10);
                } else if (!g.hasCatalogMatch) {
                    drawRoundedRect(bx, ry + 11, 112, 26, 6, {0xF5, 0x9E, 0x0B, 0x26});
                    drawRoundedOutline(bx, ry + 11, 112, 26, 6, Theme::COLOR_WARNING, Theme::COLOR_WARNING, 1);
                    drawTextCentered(tr("Привязать ➔", "Bind Port ➔"), bx + 56, ry + 17, Theme::COLOR_WARNING, 10);
                } else {
                    std::string actLbl = (g.installedCoversCount > 1)
                        ? (tr("Слотов: ", "Slots: ") + std::to_string(g.installedCoversCount))
                        : tr("Оформлено ✓", "Active ✓");
                    drawRoundedRect(bx, ry + 11, 112, 26, 6, {0x10, 0xB9, 0x81, 0x24});
                    drawRoundedOutline(bx, ry + 11, 112, 26, 6, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
                    drawTextCentered(actLbl, bx + 56, ry + 17, Theme::COLOR_SUCCESS, 10);
                }
                ry += 52;
            }
        }
    } else if (m_homeFocusedTile == 1) {
        // Реальный список ВАШИХ игр на Switch, для которых доступны Ultra-HQ 256x256 иконки!
        drawText(tr("ULTRA-HQ 256x256 ДЛЯ ВАШИХ ИГР", "ULTRA-HQ ICONS FOR YOUR GAMES"),
                 mockX + 16, mockY + 13, Theme::COLOR_FOCUS_PINK, 11);
        std::string rHdr = (missingIconsForConsole > 0)
            ? (tr("Готово к установке: ", "Ready to install: ") + std::to_string(missingIconsForConsole))
            : (tr("В базе: ", "In DB: ") + std::to_string(totalIcons));
        drawTextRight(rHdr, mockX + mockW - 16, mockY + 13, Theme::COLOR_FOCUS_CYAN, 11);
        drawRect(mockX + 16, mockY + 34, mockW - 32, 1, Theme::COLOR_BORDER);

        struct IconMatchRow {
            std::string titleId;
            std::string name;
            Variant iconVar;
            bool installed;
            bool onConsole;
        };
        std::vector<IconMatchRow> rows;
        for (const auto& ig : m_installedGames) {
            if (ig.titleId.empty() || ig.titleId == "0000000000000000" || !ig.hasCatalogMatch) continue;
            auto uIcons = getUniqueIconVariants(ig.catalogEntry);
            if (!uIcons.empty() && !ig.hasInstalledIcon) {
                rows.push_back({ig.titleId, ig.name, uIcons[0], false, true});
            }
        }
        for (const auto& ig : m_installedGames) {
            if (rows.size() >= 4) break;
            if (ig.titleId.empty() || ig.titleId == "0000000000000000" || !ig.hasCatalogMatch) continue;
            auto uIcons = getUniqueIconVariants(ig.catalogEntry);
            if (!uIcons.empty() && ig.hasInstalledIcon) {
                rows.push_back({ig.titleId, ig.name, uIcons[0], true, true});
            }
        }
        for (const auto& icE : m_videoIconsCatalog) {
            if (rows.size() >= 4) break;
            if (icE.variants.empty()) continue;
            bool dup = false;
            for (const auto& r : rows) if (r.titleId == icE.titleId) { dup = true; break; }
            if (!dup) rows.push_back({icE.titleId, icE.title, icE.variants[0], isIconInstalled(icE.titleId), false});
        }

        int ry = mockY + 42;
        for (size_t k = 0; k < std::min<size_t>(4, rows.size()); ++k) {
            const auto& r = rows[k];
            drawRoundedRect(mockX + 14, ry, mockW - 28, 48, 9, {0x11, 0x19, 0x2B, 0xEE});
            drawRoundedOutline(mockX + 14, ry, mockW - 28, 48, 9, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);

            int tx = mockX + 22, ty = ry + 6;
            drawRoundedRect(tx, ty, 36, 36, 7, {0x18, 0x22, 0x36, 0xFF});
            std::string iu = r.iconVar.previewUrl;
            if (iu.empty()) {
                std::string dId = extractDriveIdFromUrl(!r.iconVar.iconUrl.empty() ? r.iconVar.iconUrl : r.iconVar.url);
                if (!dId.empty()) iu = "https://drive.google.com/thumbnail?id=" + dId + "&sz=w320";
            }
            SDL_Texture* mt = getOrRequestRowThumb("icon_" + r.titleId + "_" + r.iconVar.id, iu, k == 0);
            if (mt) {
                SDL_Rect md{tx + 1, ty + 1, 34, 34};
                SDL_RenderCopy(m_renderer, mt, nullptr, &md);
            }
            drawRoundedOutline(tx, ty, 36, 36, 7, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_CYAN, 1);

            drawText(r.name, tx + 46, ry + 7, Theme::COLOR_TEXT_PRIMARY, 13, 285);
            int kb = static_cast<int>((r.iconVar.iconSizeBytes > 0 ? r.iconVar.iconSizeBytes : r.iconVar.sizeBytes) / 1024);
            std::string sub = (r.onConsole ? tr("На вашей консоли • ", "On Switch • ") : tr("В каталоге • ", "Catalog • ")) +
                              (kb > 0 ? (std::to_string(kb) + " KB Ultra-HQ") : "256x256 Ultra-HQ");
            drawText(sub, tx + 46, ry + 26, Theme::COLOR_TEXT_MUTED, 10, 285);

            int bx = mockX + mockW - 134;
            if (r.installed) {
                drawRoundedRect(bx, ry + 11, 112, 26, 6, {0x10, 0xB9, 0x81, 0x28});
                drawRoundedOutline(bx, ry + 11, 112, 26, 6, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
                drawTextCentered(tr("АКТИВНА ✓", "ACTIVE ✓"), bx + 56, ry + 17, Theme::COLOR_SUCCESS, 10);
            } else {
                drawRoundedRect(bx, ry + 11, 112, 26, 6, {0xEC, 0x48, 0x99, 0x28});
                drawRoundedOutline(bx, ry + 11, 112, 26, 6, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
                drawTextCentered(tr("+ Поставить", "+ Install HQ"), bx + 56, ry + 17, Theme::COLOR_FOCUS_PINK, 10);
            }
            ry += 52;
        }
    } else if (m_homeFocusedTile == 3) {
        // Живой монитор очереди скачивания прямо на Главной!
        drawText(tr("МОНИТОР ПОТОКОВЫХ ЗАГРУЗОК", "LIVE DOWNLOAD MONITOR"),
                 mockX + 16, mockY + 13, Theme::COLOR_FOCUS_CYAN, 11);
        std::vector<DownloadTask> qSnap;
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            qSnap = m_downloadQueue;
        }
        drawTextRight(std::to_string(qSnap.size()) + tr(" задач", " tasks"), mockX + mockW - 16, mockY + 13, Theme::COLOR_TEXT_MUTED, 11);
        drawRect(mockX + 16, mockY + 34, mockW - 32, 1, Theme::COLOR_BORDER);

        if (qSnap.empty()) {
            drawTextCentered(tr("Очередь сейчас свободна", "Download queue is idle"),
                             mockX + mockW / 2, mockY + 96, Theme::COLOR_TEXT_PRIMARY, 15);
            drawTextCentered(tr("Нажмите [-] для авто-установки всех недостающих фонов",
                                "Press [-] to auto-queue all missing game covers"),
                             mockX + mockW / 2, mockY + 128, Theme::COLOR_FOCUS_CYAN, 12, mockW - 44);
            std::string totSet = tr("На консоли уже активно: ", "Currently active on Switch: ") +
                                 std::to_string(installedCoveredCount) + tr(" фонов и ", " covers & ") +
                                 std::to_string(installedIconsCount) + tr(" HQ-иконок", " HQ icons");
            drawTextCentered(totSet, mockX + mockW / 2, mockY + 178, Theme::COLOR_SUCCESS, 12, mockW - 44);
        } else {
            int ry = mockY + 42;
            for (size_t k = 0; k < std::min<size_t>(4, qSnap.size()); ++k) {
                const auto& t = qSnap[k];
                drawRoundedRect(mockX + 14, ry, mockW - 28, 48, 9, {0x11, 0x19, 0x2B, 0xEE});
                drawRoundedOutline(mockX + 14, ry, mockW - 28, 48, 9, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
                drawText(t.gameTitle, mockX + 26, ry + 7, Theme::COLOR_TEXT_PRIMARY, 12, 330);
                if (t.state == TaskState::Downloading) {
                    drawCapsuleProgressBar(mockX + 26, ry + 29, 320, 10, t.progressPercent);
                    drawTextRight(std::to_string(static_cast<int>(t.progressPercent)) + "%", mockX + mockW - 24, ry + 16, Theme::COLOR_FOCUS_CYAN, 12);
                } else if (t.state == TaskState::Completed) {
                    drawText(tr("Успешно активировано ✓", "Installed & active ✓"), mockX + 26, ry + 26, Theme::COLOR_SUCCESS, 11);
                } else if (t.state == TaskState::Failed) {
                    drawText(tr("Ошибка — нажмите [A] в Загрузках", "Failed — retry in Queue"), mockX + 26, ry + 26, Theme::COLOR_DANGER, 11);
                } else {
                    drawText(tr("Ожидание в очереди...", "Waiting in queue..."), mockX + 26, ry + 26, Theme::COLOR_TEXT_MUTED, 11);
                }
                ry += 52;
            }
        }
    } else {
        // Реальная диагностика MicroSD и быстрые системные переключатели (фокус на Настройках)
#ifdef HAS_SDL2
        uint32_t nowT = SDL_GetTicks();
        if (m_lastStorageRefreshTick == 0 || nowT - m_lastStorageRefreshTick > 4000) {
            refreshStorageStats();
            m_lastStorageRefreshTick = nowT;
        }
#endif
        drawText(tr("ПАМЯТЬ MICROSD И СИСТЕМА 4IFIR", "MICROSD STORAGE & QUICK TOGGLES"),
                 mockX + 16, mockY + 13, Theme::COLOR_WARNING, 11);
        double totGb = static_cast<double>(m_storageStats.totalSdBytes) / (1024.0 * 1024.0 * 1024.0);
        double frGb = static_cast<double>(m_storageStats.freeSdBytes) / (1024.0 * 1024.0 * 1024.0);
        if (totGb <= 0.1) { totGb = 220.1; frGb = freeSdGb; }
        double usedPct = std::clamp((totGb - frGb) / totGb * 100.0, 0.0, 100.0);
        char pctStr[48];
        std::snprintf(pctStr, sizeof(pctStr), "%.1f / %.1f GB", frGb, totGb);
        drawTextRight(pctStr, mockX + mockW - 16, mockY + 13, Theme::COLOR_TEXT_PRIMARY, 11);

        drawCapsuleProgressBar(mockX + 16, mockY + 38, mockW - 32, 12, usedPct);

        double covMb = static_cast<double>(m_storageStats.coversBytes) / (1024.0 * 1024.0);
        double icoMb = static_cast<double>(m_storageStats.iconsBytes) / (1024.0 * 1024.0);
        double cacheMb = static_cast<double>(m_storageStats.thumbsBytes + m_storageStats.vidCacheBytes) / (1024.0 * 1024.0);

        struct SysQuickRow {
            std::string left;
            std::string right;
            Color col;
        };
        char r1[64], r2[64], r3[64];
        std::snprintf(r1, sizeof(r1), "%d %s (%.1f MB)", m_storageStats.coversCount, tr("шт.", "pcs"), covMb);
        std::snprintf(r2, sizeof(r2), "%d %s (%.1f MB)", m_storageStats.iconsCount, tr("шт.", "pcs"), icoMb);
        std::snprintf(r3, sizeof(r3), "%.1f MB", cacheMb);

        SysQuickRow sRows[4] = {
            {tr("Установленные видеофоны 720p", "Installed 720p Video Covers"), r1, Theme::COLOR_SUCCESS},
            {tr("Установленные HQ-иконки 256x256", "Installed 256x256 HQ Icons"), r2, Theme::COLOR_FOCUS_PINK},
            {tr("Кэш миниатюр и видеоплеера", "Thumbnails & Video Preview Cache"), r3, Theme::COLOR_FOCUS_CYAN},
            {tr("Авто-ротация слотов при запуске [-]", "Auto-Rotate Cover Slots on Boot [-]"),
             m_autoRotateCoversOnBoot ? tr("ВКЛЮЧЕНО ✓", "ENABLED ✓") : tr("ВЫКЛЮЧЕНО", "DISABLED"),
             m_autoRotateCoversOnBoot ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING}
        };

        int ry = mockY + 62;
        for (int k = 0; k < 4; ++k) {
            drawRoundedRect(mockX + 14, ry, mockW - 28, 42, 8, {0x11, 0x19, 0x2B, 0xEE});
            drawRoundedOutline(mockX + 14, ry, mockW - 28, 42, 8, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
            drawText(sRows[k].left, mockX + 26, ry + 13, Theme::COLOR_TEXT_PRIMARY, 12, 320);
            drawTextRight(sRows[k].right, mockX + mockW - 26, ry + 13, sRows[k].col, 12, 150);
            ry += 46;
        }
    }

    // =========================================================================================
    // 2. НИЖНЯЯ ДОК-ЛЕНТА РАЗДЕЛОВ: 5x CYBER-DOCK CARDS С ЖИВЫМИ МЕТРИКАМИ (y = 390, h = 242)
    // =========================================================================================
    struct DockTileDef {
        int index;
        std::string title;
        std::string subBadge;
    };

    char sdShort[32];
    std::snprintf(sdShort, sizeof(sdShort), "%.0f GB SD", freeSdGb);

    DockTileDef tiles[5] = {
        {0, tr("Каталог", "Catalog"), std::to_string(totalGames) + tr(" игр", " games")},
        {1, tr("Видеоиконки", "Video Icons"), std::to_string(totalIcons) + " ULTRA-HQ"},
        {2, tr("Мои игры", "My Games"), std::to_string(installedCoveredCount) + "/" + std::to_string(std::max(1, installedRealCount)) + tr(" актив.", " set")},
        {3, tr("Загрузки", "Downloads"), activeQueueTasks > 0 ? (std::to_string(activeQueueTasks) + tr(" в очереди", " active")) : tr("Готово", "Ready")},
        {4, tr("Настройки", "Settings"), sdShort}
    };

    int tileW = 228;
    int tileH = 240;
    int tileGap = 15;
    int totalRowW = 5 * tileW + 4 * tileGap;
    int tileStartX = (Theme::SCREEN_WIDTH - totalRowW) / 2;
    int tileStartY = 392;

    for (int i = 0; i < 5; ++i) {
        bool isFocused = (m_homeFocusedTile == i);
        int tx = tileStartX + i * (tileW + tileGap);
        drawDashboardTile(tx, tileStartY, tileW, tileH, tiles[i].index, tiles[i].title, tiles[i].subBadge, isFocused);
    }
}

void App::renderTabMyGames() {
    if (m_filteredMyGamesIndices.empty() && m_myGamesFilterMode == 0 && m_myGamesSearchQuery.empty() && !m_installedGames.empty()) {
        rebuildMyGamesFilter();
    }

    // Left List Pane (450px wide) - 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 450, 570, false, false);

    // Compact Search [Y] + Filter [-] Bar at top of Left Pane (y = 86..114)
    bool hasMgSearch = !m_myGamesSearchQuery.empty();
    drawRoundedRect(38, 86, 226, 28, 7, hasMgSearch ? Theme::COLOR_FOCUS_FILL : Color{0x12, 0x19, 0x28, 0xEE});
    drawRoundedOutline(38, 86, 226, 28, 7, hasMgSearch ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, hasMgSearch ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, 1);
    std::string mgSearchTxt = hasMgSearch
        ? (std::string("[Y] ") + m_myGamesSearchQuery)
        : tr("[Y] Поиск моих игр...", "[Y] Search my games...");
    drawText(mgSearchTxt, 48, 93, hasMgSearch ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 11, 206);

    const char* mgFiltShortRu[4] = {"[-] Все", "[-] С фоном", "[-] Без фона", "[-] Новинки ★"};
    const char* mgFiltShortEn[4] = {"[-] All", "[-] Covered", "[-] Missing", "[-] New ★"};
    std::string mgFiltStr = (m_language == Language::English) ? mgFiltShortEn[m_myGamesFilterMode % 4] : mgFiltShortRu[m_myGamesFilterMode % 4];
    Color mgFiltCol = (m_myGamesFilterMode == 3) ? Theme::COLOR_WARNING : (m_myGamesFilterMode > 0 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY);
    drawRoundedRect(270, 86, 132, 28, 7, (m_myGamesFilterMode > 0) ? Theme::COLOR_FOCUS_FILL : Color{0x12, 0x19, 0x28, 0xEE});
    drawRoundedOutline(270, 86, 132, 28, 7, mgFiltCol, mgFiltCol, 1);
    drawTextCentered(mgFiltStr, 270 + 66, 93, mgFiltCol, 11, 124);

    const int visibleCount = 7;
    int totalCount = static_cast<int>(m_filteredMyGamesIndices.size());

    if (m_myGamesSelectedIndex >= totalCount) {
        m_myGamesSelectedIndex = std::max(0, totalCount - 1);
    }
    if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex;
    }
    if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + visibleCount) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex - visibleCount + 1;
    }

    if (totalCount > 0) {
        std::string posStr = std::to_string(m_myGamesSelectedIndex + 1) + "/" + std::to_string(totalCount);
        drawTextRight(posStr, 470, 93, Theme::COLOR_FOCUS_CYAN, 11);
    } else {
        drawTextCentered(tr("Игры не найдены", "No games match filter"), 255, 290, Theme::COLOR_TEXT_MUTED, 14);
        drawTextCentered(tr("Нажмите [-] или [Y] для сброса", "Press [-] or [Y] to reset"), 255, 318, Theme::COLOR_FOCUS_CYAN, 12);
    }

    int startY = 122;
    int endIdx = std::min(totalCount, m_myGamesScrollOffset + visibleCount);
    for (int i = m_myGamesScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_myGamesSelectedIndex);
        int realIdx = m_filteredMyGamesIndices[i];
        const auto& game = m_installedGames[realIdx];
        bool isNewGame = (m_newlyDetectedTitleIds.count(game.titleId) > 0);

        bool isFocused = (m_myGamesActivePane == MyGamesPane::GamesList && isSelected);
        drawGlassCard(35, startY, 440, 60, isFocused, isSelected);

        std::string dispName = isNewGame ? ("★ " + game.name) : game.name;
        drawText(dispName, 48, startY + 10, isSelected ? Theme::COLOR_FOCUS_CYAN : (isNewGame ? Theme::COLOR_WARNING : Theme::COLOR_TEXT_PRIMARY), 14, 268);
        std::string subTid = game.titleId + (game.installedCoversCount > 1 ? (" • " + std::to_string(game.installedCoversCount) + " слота") : "");
        drawText(subTid, 48, startY + 34, Theme::COLOR_TEXT_MUTED, 11, 268);

        // Status pill: Cover & Video Icon
        if (game.hasInstalledCover && game.hasInstalledIcon) {
            drawRoundedRect(330, startY + 18, 135, 24, 5, {0x10, 0xB9, 0x81, 0x33});
            drawRoundedOutline(330, startY + 18, 135, 24, 5, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
            drawTextCentered(tr("ФОН + ИКОНКА", "COMBO ACTIVE"), 330 + 67, startY + 23, Theme::COLOR_SUCCESS, 10);
        } else if (game.hasInstalledCover) {
            drawRoundedRect(365, startY + 18, 100, 24, 5, {0x10, 0xB9, 0x81, 0x22});
            drawRoundedOutline(365, startY + 18, 100, 24, 5, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
            drawTextCentered(tr("ФОН ЕСТЬ", "COVER ON"), 365 + 50, startY + 23, Theme::COLOR_SUCCESS, 10);
        } else if (game.hasInstalledIcon) {
            drawRoundedRect(355, startY + 18, 110, 24, 5, {0x0E, 0x74, 0x90, 0x33});
            drawRoundedOutline(355, startY + 18, 110, 24, 5, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
            drawTextCentered(tr("ИКОНКА 1:1", "ICON ON"), 355 + 55, startY + 23, Theme::COLOR_FOCUS_CYAN, 10);
        } else if (!game.hasCatalogMatch) {
            drawRoundedRect(350, startY + 18, 115, 24, 5, {0xF5, 0x9E, 0x0B, 0x22});
            drawRoundedOutline(350, startY + 18, 115, 24, 5, Theme::COLOR_WARNING, Theme::COLOR_WARNING, 1);
            drawTextCentered(tr("ПРИВЯЗАТЬ", "LINK [A]"), 350 + 57, startY + 23, Theme::COLOR_WARNING, 10);
        } else {
            drawRoundedRect(370, startY + 18, 95, 24, 5, {0x28, 0x33, 0x47, 0x55});
            drawRoundedOutline(370, startY + 18, 95, 24, 5, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
            drawTextCentered(tr("НЕТ ФОНА", "NO COVER"), 370 + 47, startY + 23, Theme::COLOR_TEXT_MUTED, 10);
        }

        startY += 66;
    }

    // Smooth 60 FPS neon selection indicator bar on the left of MyGames list
    if (totalCount > 0 && m_myGamesActivePane == MyGamesPane::GamesList) {
        int barY = static_cast<int>(std::round(m_smoothMyGamesSelY)) + 8;
        drawRoundedRect(31, barY, 5, 44, 2, Theme::COLOR_FOCUS_CYAN);
    }

    // Right Details Pane (750px wide) - 4IFIR Cyber-Glass Container
    drawGlassCard(500, 80, 750, 570, false, false);

    if (totalCount > 0 && m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < totalCount) {
        int realSelIdx = m_filteredMyGamesIndices[m_myGamesSelectedIndex];
        const auto& selGame = m_installedGames[realSelIdx];

        drawText(selGame.name, 530, 102, Theme::COLOR_TEXT_PRIMARY, 21, 510);
        drawText("Title ID: " + selGame.titleId + "  |  " + selGame.author, 530, 134, Theme::COLOR_TEXT_MUTED, 13, 510);

        // Unified [X] Action Sheet Button at Top-Right of Right Pane (x = 1055, y = 102, w = 170, h = 42)
        drawRoundedRect(1055, 102, 170, 42, 10, Color{0xEC, 0x48, 0x99, 0x26});
        drawRoundedOutline(1055, 102, 170, 42, 10, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 2);
        drawTextCentered(tr("[X] Действия ▾", "[X] Actions ▾"), 1055 + 85, 115, Theme::COLOR_FOCUS_PINK, 13);

        // Status details
        std::string coverInfo;
        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
            coverInfo = tr("Активно: Видеофон (", "Active: Cover (") + std::to_string(selGame.installedCoverSizeBytes / 1024) +
                        " KB) + HQ-иконка 256x256 (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledCover) {
            coverInfo = tr("Активный видеофон: ", "Active cover: ") + Config::getTargetCoverFileName(selGame.titleId) +
                        " (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledIcon) {
            coverInfo = tr("Активна только HQ-иконка 256x256 (", "Active HQ Icon 256x256 (") + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB)";
        } else {
            coverInfo = tr("Оформление пока не установлено на консоль", "No video cover or icon installed yet");
        }
        drawText(coverInfo, 530, 164, (selGame.hasInstalledCover || selGame.hasInstalledIcon) ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 13, 690);

        // Идея 4: Визуальная полоса слотов ротации видеофонов (y = 194, h = 34)
        int slotX = 530;
        int slotY = 194;
        if (selGame.installedCoversCount > 0) {
            int maxDrawSlots = std::min(4, selGame.installedCoversCount);
            for (int sIdx = 0; sIdx < maxDrawSlots; ++sIdx) {
                const auto& scv = selGame.installedCoverVariants[sIdx];
                bool activeSlot = scv.isActive;
                std::string sLabel = activeSlot
                    ? (tr("★ Слот #1: Активен", "★ Slot #1: Active"))
                    : (tr("Слот #", "Slot #") + std::to_string(scv.index + 1));
                int sw = measureTextWidth(sLabel, 11) + 22;
                drawRoundedRect(slotX, slotY, sw, 32, 8, activeSlot ? Color{0x10, 0xB9, 0x81, 0x33} : Color{0x14, 0x1D, 0x2E, 0xEE});
                drawRoundedOutline(slotX, slotY, sw, 32, 8, activeSlot ? Theme::COLOR_SUCCESS : Theme::COLOR_FOCUS_CYAN, activeSlot ? Theme::COLOR_SUCCESS : Theme::COLOR_FOCUS_CYAN, 1);
                drawTextCentered(sLabel, slotX + sw / 2, slotY + 9, activeSlot ? Theme::COLOR_SUCCESS : Theme::COLOR_FOCUS_CYAN, 11);
                slotX += sw + 8;
            }
        }
        // [+ В новый слот] / [Записи SD] pills
        if (selGame.hasCatalogMatch && !getCoverVariants(selGame.catalogEntry).empty()) {
            std::string addSlotLbl = tr("+ В новый слот [X]", "+ Add Slot [X]");
            int asW = measureTextWidth(addSlotLbl, 11) + 20;
            if (slotX + asW <= 1070) {
                drawRoundedRect(slotX, slotY, asW, 32, 8, Theme::COLOR_FOCUS_FILL);
                drawRoundedOutline(slotX, slotY, asW, 32, 8, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
                drawTextCentered(addSlotLbl, slotX + asW / 2, slotY + 9, Theme::COLOR_FOCUS_CYAN, 11);
                slotX += asW + 8;
            }
        }
        std::string sdClipLbl = tr("[L3] Записи SD", "[L3] SD Clips");
        int sdW = measureTextWidth(sdClipLbl, 11) + 18;
        drawRoundedRect(1225 - sdW, slotY, sdW, 32, 8, Color{0x14, 0x1D, 0x2E, 0xEE});
        drawRoundedOutline(1225 - sdW, slotY, sdW, 32, 8, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        drawTextCentered(sdClipLbl, 1225 - sdW / 2, slotY + 9, Theme::COLOR_TEXT_SECONDARY, 11);

        // Available variants from catalog
        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = tr("Варианты в базе (", "Catalog Variants (") + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 244, Theme::COLOR_TEXT_PRIMARY, 15);

        if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            drawTextRight(tr("[B] К списку игр  •  [X] Комбо / Новый слот / Превью", "[B] Games  •  [X] Combo / Slot / Preview"), 1225, 246, Theme::COLOR_FOCUS_CYAN, 12);
        } else {
            drawTextRight(tr("[A] Выбрать вариант  •  [X] Все действия", "[A] Select  •  [X] All Actions"), 1225, 246, Theme::COLOR_TEXT_MUTED, 12);
        }

        if (totalVariants > 0) {
            const int visibleVariants = 4;
            if (m_variantScrollOffset < 0) m_variantScrollOffset = 0;
            if (m_selectedVariantIndex < m_variantScrollOffset) {
                m_variantScrollOffset = m_selectedVariantIndex;
            } else if (m_selectedVariantIndex >= m_variantScrollOffset + visibleVariants) {
                m_variantScrollOffset = m_selectedVariantIndex - visibleVariants + 1;
            }

            int vY = 276;
            int endVIdx = std::min(totalVariants, m_variantScrollOffset + visibleVariants);
            for (int vIdx = m_variantScrollOffset; vIdx < endVIdx; ++vIdx) {
                const auto& v = selGame.catalogEntry.variants[vIdx];
                bool isVarSelected = (vIdx == m_selectedVariantIndex);
                bool isVarFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                drawGlassCard(525, vY, 700, 74, isVarFocused, isVarSelected);

                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                drawText(vTitle, 545, vY + 12, isVarSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15, 430);

                double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
                char szBuf[16];
                if (mb >= 0.1) snprintf(szBuf, sizeof(szBuf), "%.1f MB", mb);
                else snprintf(szBuf, sizeof(szBuf), "~3.5 MB");
                std::string meta = std::to_string(v.width) + "x" + std::to_string(v.height) + " @" +
                                   std::to_string(static_cast<int>(v.fps)) + "fps • " + std::string(szBuf);
                drawText(meta, 545, vY + 42, Theme::COLOR_TEXT_MUTED, 12, 220);

                int vBadgeX = 740;
                bool isActiveOnConsole = (selGame.hasInstalledCover && v.id == selGame.installedVariantId);
                if (isActiveOnConsole) {
                    drawRoundedRect(vBadgeX, vY + 39, 88, 22, 4, {0x10, 0xB9, 0x81, 0x44});
                    drawRoundedOutline(vBadgeX, vY + 39, 88, 22, 4, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
                    drawTextCentered(tr("АКТИВЕН", "ACTIVE"), vBadgeX + 44, vY + 44, Theme::COLOR_SUCCESS, 10);
                    vBadgeX += 94;
                }
                if (v.hasAudio) {
                    drawRoundedRect(vBadgeX, vY + 39, 58, 22, 4, {0x10, 0xB9, 0x81, 0x33});
                    drawRoundedOutline(vBadgeX, vY + 39, 58, 22, 4, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
                    drawTextCentered(tr("ЗВУК", "AUDIO"), vBadgeX + 29, vY + 44, Theme::COLOR_SUCCESS, 10);
                    vBadgeX += 64;
                }
                if (v.hasIcon) {
                    drawRoundedRect(vBadgeX, vY + 39, 72, 22, 4, Theme::COLOR_ICON_BADGE_FILL);
                    drawRoundedOutline(vBadgeX, vY + 39, 72, 22, 4, Theme::COLOR_ICON_BADGE, Theme::COLOR_ICON_BADGE, 1);
                    drawTextCentered("256x256", vBadgeX + 36, vY + 44, Theme::COLOR_ICON_BADGE, 10);
                }

                Color btnFill = isVarFocused ? Theme::COLOR_FOCUS_FILL : Color{0x15, 0x20, 0x30, 0x88};
                Color btnBorder = (isVarFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER;
                Color btnTextCol = (isVarFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY;

                if (v.hasIcon) {
                    drawRoundedRect(980, vY + 19, 125, 36, 8, btnFill);
                    drawRoundedOutline(980, vY + 19, 125, 36, 8, btnBorder, btnBorder, 1);
                    drawTextCentered(tr("[A] Комбо", "[A] Combo"), 980 + 62, vY + 29, btnTextCol, 12);

                    drawRoundedRect(1112, vY + 19, 98, 36, 8, {0x0E, 0x74, 0x90, 0x33});
                    drawRoundedOutline(1112, vY + 19, 98, 36, 8, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
                    drawTextCentered(tr("Иконка", "Icon"), 1112 + 49, vY + 29, Theme::COLOR_FOCUS_CYAN, 12);
                } else {
                    drawRoundedRect(1005, vY + 19, 205, 36, 8, btnFill);
                    drawRoundedOutline(1005, vY + 19, 205, 36, 8, btnBorder, btnBorder, 1);
                    drawTextCentered(isActiveOnConsole ? tr("[A] Переустановить", "[A] Reinstall") : tr("[A] Установить", "[A] Install"),
                                     1005 + 102, vY + 29, btnTextCol, 12);
                }

                vY += 82;
            }

            if (endVIdx < totalVariants) {
                std::string belowStr = tr("▼ Еще вариантов: ", "▼ More variants: ") + std::to_string(totalVariants - endVIdx);
                drawTextCentered(belowStr, 875, vY + 2, Theme::COLOR_FOCUS_PINK, 12);
            }
        } else {
            // Идея 2: Карточка обратной привязки кастомного форвардера / репака к любой игре из базы
            drawRoundedRect(530, 286, 690, 178, 16, {0x12, 0x1A, 0x2B, 0xF2});
            drawRoundedOutline(530, 286, 690, 178, 16, Theme::COLOR_WARNING, Theme::COLOR_FOCUS_CYAN, 2);
            drawText(tr("Нестандартный Title ID (кастомный форвардер, порт или репак)",
                        "Custom Title ID (Homebrew Forwarder, Port or Repack)"),
                     554, 306, Theme::COLOR_WARNING, 16, 640);
            drawText(tr("Нажмите [A], чтобы автоматически найти эту игру по названию в каталоге",
                        "Press [A] to auto-search this game by name in the catalog and bind"),
                     554, 338, Theme::COLOR_TEXT_PRIMARY, 13, 640);
            drawText(tr("и привязать любой видеофон + HQ-иконку 256x256 прямо к этому ярлыку!",
                        "any video cover + 256x256 HQ icon directly to this Title ID!"),
                     554, 360, Theme::COLOR_TEXT_MUTED, 13, 640);

            drawRoundedRect(554, 398, 460, 46, 10, Theme::COLOR_FOCUS_FILL);
            drawNeonRoundedOutline(554, 398, 460, 46, 10, 2);
            drawTextCentered(tr("[A] Найти в базе и привязать к этому Title ID", "[A] Find in Catalog & Bind to Title ID"),
                             554 + 230, 413, Theme::COLOR_FOCUS_CYAN, 14);
        }
    }
}

void App::renderCategoriesView() {
    renderTabCatalog();
}

void App::renderTabVideoIcons() {
    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 74, 1220, 576, false, false);

    // Top Row: Section Title + Interactive Search Bar + Filter Button
    drawText(tr("Видеоиконки 1:1", "1:1 Video Icons"), 50, 88, Theme::COLOR_TEXT_PRIMARY, 22);

    // Prominent Search Bar (x=280, y=82, w=630, h=38)
    bool hasIconSearch = !m_videoIconsSearchQuery.empty();
    drawGlassCard(280, 82, 630, 38, hasIconSearch, false);
    drawSearchIcon(298, 101, hasIconSearch ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED);
    std::string iconSearchLabel = hasIconSearch
        ? (tr("Поиск: ", "Search: ") + m_videoIconsSearchQuery)
        : tr("Поиск видеоиконки по названию игры или TitleID...", "Search video icon by game title or TitleID...");
    drawText(iconSearchLabel, 314, 92, hasIconSearch ? Theme::COLOR_TEXT_PRIMARY : Theme::COLOR_TEXT_MUTED, 13, 480);
    drawRoundedRect(816, 88, 84, 26, 6, Theme::COLOR_FOCUS_FILL);
    drawRoundedOutline(816, 88, 84, 26, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered(tr("[Y] Поиск", "[Y] Search"), 858, 93, Theme::COLOR_FOCUS_CYAN, 11);

    // Filter pill at top-right (x=925, y=82, w=305, h=38) with dynamic counts
    size_t totalAllIcons = m_videoIconsCatalog.size();
    size_t installedIconsCount = 0;
    for (const auto& icEntry : m_videoIconsCatalog) {
        if (isIconInstalled(icEntry.titleId)) {
            installedIconsCount++;
        }
    }
    size_t notInstalledIconsCount = (totalAllIcons >= installedIconsCount) ? (totalAllIcons - installedIconsCount) : 0;

    std::string filterLabel;
    if (m_videoIconsFilterMode % 3 == 0) {
        filterLabel = tr("Все (", "All (") + std::to_string(totalAllIcons) + ")";
    } else if (m_videoIconsFilterMode % 3 == 1) {
        filterLabel = tr("Установленные (", "Installed (") + std::to_string(installedIconsCount) + ")";
    } else {
        filterLabel = tr("Не установленные (", "Not Installed (") + std::to_string(notInstalledIconsCount) + ")";
    }
    std::string fText = tr("[-] Фильтр: ", "[-] Filter: ") + filterLabel;
    drawPillButton(925, 82, 305, 38, fText, false, Theme::COLOR_FOCUS_CYAN);

    if (m_filteredVideoIcons.empty()) {
        drawText(tr("Видеоиконки не найдены по заданным критериям.", "No video icons match your filter criteria."), 60, 180, Theme::COLOR_TEXT_MUTED, 16);
        drawText(tr("Нажмите [Y] для смены поискового запроса или [-] для сброса фильтра.", "Press [Y] to change search query or [-] to cycle filter."), 60, 215, Theme::COLOR_FOCUS_CYAN, 14);
        return;
    }

    const int visibleRows = 5;
    int totalCount = static_cast<int>(m_filteredVideoIcons.size());
    if (m_videoIconsScrollOffset < 0) m_videoIconsScrollOffset = 0;
    if (m_videoIconsScrollOffset + visibleRows > totalCount) {
        m_videoIconsScrollOffset = std::max(0, totalCount - visibleRows);
    }

    // LEFT PANE (x=45, w=760): Interactive Video Icon List with 70x70 Auto-Thumbnails & < ◄/► Variant > Selector
    int listX = 45;
    int listW = 760;
    int y = 136;
    int endIdx = std::min(totalCount, m_videoIconsScrollOffset + visibleRows);

    for (int i = m_videoIconsScrollOffset; i < endIdx; ++i) {
        const auto& entry = m_filteredVideoIcons[i];
        bool isFocused = (i == m_videoIconsSelectedIndex);
        bool installed = isIconInstalled(entry.titleId);

        int varCount = std::max(1, static_cast<int>(entry.variants.size()));
        int selVarIdx = 0;
        auto vit = m_videoIconVariantIdx.find(entry.titleId);
        if (vit != m_videoIconVariantIdx.end() && varCount > 0) {
            selVarIdx = std::clamp(vit->second, 0, varCount - 1);
        }
        const Variant* curVar = entry.variants.empty() ? nullptr : &entry.variants[selVarIdx];

        drawGlassCard(listX, y, listW, 88, isFocused, isFocused);

        // 70x70 Auto-Loading Mini-Thumbnail Box (Variant A + B)
        int boxX = listX + 12;
        int boxY = y + 9;
        drawRoundedRect(boxX, boxY, 70, 70, 10, {0x14, 0x1A, 0x28, 0xFF});

        SDL_Texture* rowTex = nullptr;
        if (curVar) {
            std::string rowThumbUrl = curVar->previewUrl;
            if (rowThumbUrl.empty()) {
                std::string drvId = extractDriveIdFromUrl(!curVar->iconUrl.empty() ? curVar->iconUrl : curVar->url);
                if (!drvId.empty()) {
                    rowThumbUrl = "https://drive.google.com/thumbnail?id=" + drvId + "&sz=w320";
                }
            }
            rowTex = getOrRequestRowThumb("icon_" + entry.titleId + "_" + curVar->id, rowThumbUrl, isFocused);
        }

        if (rowTex) {
            SDL_Rect dst{boxX + 2, boxY + 2, 66, 66};
            SDL_RenderCopy(m_renderer, rowTex, nullptr, &dst);
        } else {
            for (int row = -8; row <= 8; ++row) {
                int pw = 12 - std::abs(row);
                drawRect(boxX + 28, boxY + 24 + row, pw, 1, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY);
            }
        }
        drawRoundedOutline(boxX, boxY, 70, 70, 10, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, 1);
        drawRoundedRect(boxX + 10, boxY + 50, 50, 15, 4, {0xEC, 0x48, 0x99, 0xE6});
        drawTextCentered("256x256", boxX + 35, boxY + 51, Theme::COLOR_TEXT_PRIMARY, 9);

        int infoX = boxX + 82;
        drawText(entry.title, infoX, y + 12, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15, 415);

        drawRect(infoX, y + 42, 152, 22, {0x1C, 0x24, 0x36, 0xAA});
        drawRectOutline(infoX, y + 42, 152, 22, Theme::COLOR_BORDER, 1);
        drawText(entry.titleId, infoX + 7, y + 45, Theme::COLOR_TEXT_MUTED, 11);

        // Multi-variant selector pill (< ◄ Вариант X/Y ► >) — Audit Finding #3
        int pillX = infoX + 160;
        int pillW = 166;
        if (varCount > 1) {
            std::string varStr = std::string(isFocused ? "◄ " : "") + tr("Вар. ", "Var ") +
                                 std::to_string(selVarIdx + 1) + "/" + std::to_string(varCount) +
                                 (isFocused ? " ►" : "");
            drawRoundedRect(pillX, y + 42, pillW, 22, 5, isFocused ? Color{0xEC, 0x48, 0x99, 0x33} : Theme::COLOR_FOCUS_FILL);
            drawRoundedOutline(pillX, y + 42, pillW, 22, 5, isFocused ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN, isFocused ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN, 1);
            drawTextCentered(varStr, pillX + pillW / 2, y + 45, isFocused ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN, 11);
        } else {
            std::string varStr = tr("1 вариант 1:1", "1 icon variant");
            drawRoundedRect(pillX, y + 42, pillW, 22, 5, Theme::COLOR_FOCUS_FILL);
            drawRoundedOutline(pillX, y + 42, pillW, 22, 5, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
            drawTextCentered(varStr, pillX + pillW / 2, y + 45, Theme::COLOR_FOCUS_CYAN, 11);
        }

        if (curVar) {
            drawText(curVar->name, pillX + pillW + 10, y + 45, Theme::COLOR_TEXT_MUTED, 11, 120);
        }

        // Right-side Install / Status button inside left row (x=648, w=144)
        int btnX = listX + listW - 156;
        if (installed) {
            drawRoundedRect(btnX, y + 25, 144, 38, 8, Theme::COLOR_SUCCESS_BADGE_FILL);
            drawRoundedOutline(btnX, y + 25, 144, 38, 8, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
            drawTextCentered(isFocused ? tr("АКТИВНА [+]", "ACTIVE [+]") : tr("УСТАНОВЛЕНО", "INSTALLED"), btnX + 72, y + 36, Theme::COLOR_SUCCESS, 11);
        } else {
            drawRoundedRect(btnX, y + 25, 144, 38, 8, isFocused ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_MUTED_BADGE_FILL);
            drawRoundedOutline(btnX, y + 25, 144, 38, 8, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, 1);
            drawTextCentered(tr("[A] Установить", "[A] Install"), btnX + 72, y + 36, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 12);
        }

        y += 98;
    }

    // Smooth 60 FPS neon selection indicator bar on the left of VideoIcons list
    if (totalCount > 0) {
        int barY = static_cast<int>(std::round(m_smoothVideoIconsSelY)) + 12;
        drawRoundedRect(38, barY, 5, 64, 2, Theme::COLOR_FOCUS_CYAN);
    }

    // RIGHT PANE (x=818, y=136, w=414, h=480): Live Switch Home Screen Icon Dock (Variant B)
    int dockX = 818;
    int dockY = 136;
    int dockW = 414;
    int dockH = 480;
    drawGlassCard(dockX, dockY, dockW, dockH, true, true);

    drawTextCentered(tr("МАКЕТ МЕНЮ SWITCH (256x256 LIVE)", "SWITCH HOME ICON DOCK (256x256 LIVE)"),
                     dockX + dockW / 2, dockY + 14, Theme::COLOR_FOCUS_CYAN, 12);

    // Adjacent ghosted Switch Home tiles on left & right of the 256x256 tile
    drawRoundedRect(dockX + 12, dockY + 86, 68, 200, 10, {0x0E, 0x14, 0x22, 0xAA});
    drawRoundedOutline(dockX + 12, dockY + 86, 68, 200, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    drawRoundedRect(dockX + dockW - 80, dockY + 86, 68, 200, 10, {0x0E, 0x14, 0x22, 0xAA});
    drawRoundedOutline(dockX + dockW - 80, dockY + 86, 68, 200, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);

    // Central 1:1 256x256 Live Switch Icon Tile (x = dockX + 79 = 897, y = dockY + 54 = 190, w = 256, h = 256)
    int tileX = dockX + (dockW - 256) / 2;
    int tileY = dockY + 54;
    SDL_Rect iconDst{tileX, tileY, 256, 256};

    drawRoundedRect(tileX - 4, tileY - 4, 264, 264, 14, {0x08, 0x0C, 0x14, 0xFF});

    const auto& selEntry = m_filteredVideoIcons[std::clamp(m_videoIconsSelectedIndex, 0, totalCount - 1)];
    int selVarIdx = getSelectedVideoIconVariantIndex(selEntry);
    const Variant* selVar = selEntry.variants.empty() ? nullptr : &selEntry.variants[selVarIdx];

    bool dockPlayingVideo = (!m_isFullscreenPreview && !m_isCollectionBrowserOpen && m_videoPlayer.isPlaying());
    if (dockPlayingVideo) {
        m_videoPlayer.render(m_renderer, &iconDst);
        drawRoundedRect(tileX + 8, tileY + 8, 96, 22, 5, {0x09, 0x12, 0x1E, 0xDD});
        drawRoundedOutline(tileX + 8, tileY + 8, 96, 22, 5, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
        drawTextCentered("LIVE 256x256", tileX + 56, tileY + 12, Theme::COLOR_SUCCESS, 10);
    } else if (m_videoIconDockTexture) {
        SDL_RenderCopy(m_renderer, m_videoIconDockTexture, nullptr, &iconDst);
        if (m_collectionVideoDownloading) {
            drawRoundedRect(tileX + 8, tileY + 8, 128, 24, 5, {0x09, 0x12, 0x1E, 0xDD});
            drawLoadingSpinner(tileX + 22, tileY + 20, 6, Theme::COLOR_FOCUS_CYAN);
            drawText(tr("Видео...", "Video..."), tileX + 34, tileY + 12, Theme::COLOR_FOCUS_CYAN, 10);
        }
    } else {
        SDL_Texture* fallbackRowTex = selVar ? findCachedThumbTexture(selEntry.titleId, *selVar, true) : nullptr;
        if (fallbackRowTex) {
            SDL_RenderCopy(m_renderer, fallbackRowTex, nullptr, &iconDst);
            if (m_collectionVideoDownloading) {
                drawRoundedRect(tileX + 8, tileY + 8, 148, 24, 5, {0x09, 0x12, 0x1E, 0xDD});
                drawLoadingSpinner(tileX + 22, tileY + 20, 6, Theme::COLOR_FOCUS_CYAN);
                uint64_t dlKb = m_collectionDownloadBytes.load() / 1024;
                std::string pTxt = (dlKb > 0) ? (std::to_string(dlKb) + " KB...") : tr("Видео...", "Video...");
                drawText(pTxt, tileX + 34, tileY + 12, Theme::COLOR_FOCUS_CYAN, 10);
            }
        } else {
            // Styled 4IFIR Cyber-Glass Icon Placeholder (never a plain black box!)
            drawRoundedRect(tileX + 6, tileY + 6, 244, 244, 12, {0x10, 0x18, 0x28, 0xFF});
            drawLoadingSpinner(tileX + 128, tileY + 104, 18, Theme::COLOR_FOCUS_CYAN);
            uint64_t dlKb = m_collectionDownloadBytes.load() / 1024;
            std::string loadMsg = (dlKb > 0)
                ? (tr("Загрузка: ", "Loading: ") + std::to_string(dlKb) + " KB")
                : tr("Загрузка 256x256...", "Loading 256x256...");
            drawTextCentered(loadMsg, tileX + 128, tileY + 142, Theme::COLOR_FOCUS_CYAN, 13);
            drawTextCentered("4IFIR HEVC 1:1", tileX + 128, tileY + 168, Theme::COLOR_FOCUS_PINK, 11);
        }
    }

    uint8_t pulseC = static_cast<uint8_t>(std::clamp(180.0f + 75.0f * m_glowPulse, 120.0f, 255.0f));
    drawRoundedOutline(tileX - 4, tileY - 4, 264, 264, 14, {0x00, pulseC, 0xFF, 0xFF}, Theme::COLOR_FOCUS_PINK, 3);

    // Selected Icon Details & Interactive Controls below the 256x256 tile
    drawTextCentered(selEntry.title, dockX + dockW / 2, tileY + 270, Theme::COLOR_TEXT_PRIMARY, 15, dockW - 28);
    if (selVar) {
        std::string vSub = selVar->name + " • " + std::to_string(selVarIdx + 1) + "/" + std::to_string(selEntry.variants.size());
        drawTextCentered(vSub, dockX + dockW / 2, tileY + 294, Theme::COLOR_FOCUS_CYAN, 12, dockW - 28);
    }

    // Variant Switcher Hint / Pill
    if (selEntry.variants.size() > 1) {
        drawRoundedRect(dockX + 52, tileY + 318, dockW - 104, 28, 7, {0xEC, 0x48, 0x99, 0x22});
        drawRoundedOutline(dockX + 52, tileY + 318, dockW - 104, 28, 7, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
        drawTextCentered(tr("◄ [Влево / Вправо] Сменить вариант ►", "◄ [Left / Right] Change Variant ►"),
                         dockX + dockW / 2, tileY + 324, Theme::COLOR_FOCUS_PINK, 11);
    } else {
        drawTextCentered(tr("Формат: 4IFIR HEVC 256x256 • Бесшовный цикл", "Format: 4IFIR HEVC 256x256 • Seamless Loop"),
                         dockX + dockW / 2, tileY + 324, Theme::COLOR_TEXT_MUTED, 11);
    }

    // Dock Action Buttons: [X] Действия ▾ and [A] Установить
    int bY = dockY + dockH - 52;
    drawRoundedRect(dockX + 18, bY, 182, 38, 8, {0xEC, 0x48, 0x99, 0x24});
    drawRoundedOutline(dockX + 18, bY, 182, 38, 8, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
    drawTextCentered(tr("[X] Действия ▾", "[X] Actions ▾"), dockX + 18 + 91, bY + 11, Theme::COLOR_FOCUS_PINK, 12);

    drawRoundedRect(dockX + 214, bY, 182, 38, 8, Theme::COLOR_FOCUS_FILL);
    drawNeonRoundedOutline(dockX + 214, bY, 182, 38, 8, 2);
    drawTextCentered(tr("[A] Установить", "[A] Install Icon"), dockX + 214 + 91, bY + 11, Theme::COLOR_FOCUS_CYAN, 12);
}

void App::renderTabCatalog() {
    // 4IFIR Cyber-Glass Split-Studio Container
    drawGlassCard(30, 74, 1220, 578, false, false);

    bool isFavTab = (m_catalogSortMode == CatalogSortMode::FavoritesOnly);

    // Полоса быстрых чип-фильтров Каталога [-] + Поле поиска [Y] справа (y = 82, h = 36)
    struct FilterChip {
        CatalogSortMode mode;
        const char* ru;
        const char* en;
    };
    const FilterChip chips[7] = {
        {CatalogSortMode::Default,       "Все",         "All"},
        {CatalogSortMode::InstalledOnly, "На консоли",  "Installed"},
        {CatalogSortMode::IconsOnly,     "256x256",     "256x256"},
        {CatalogSortMode::AudioOnly,     "Звук ♪",      "Audio ♪"},
        {CatalogSortMode::Fps60Only,     "60 FPS",      "60 FPS"},
        {CatalogSortMode::FavoritesOnly, "Избр. ★",     "Fav ★"},
        {CatalogSortMode::Alphabetical,  "А–Я",         "A–Z"}
    };

    drawRoundedRect(46, 85, 28, 30, 6, {0x16, 0x20, 0x32, 0xEE});
    drawRoundedOutline(46, 85, 28, 30, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered("-", 60, 91, Theme::COLOR_FOCUS_CYAN, 14);

    int chipX = 80;
    for (int ci = 0; ci < 7; ++ci) {
        bool active = (m_catalogSortMode == chips[ci].mode);
        const char* clbl = (m_language == Language::English) ? chips[ci].en : chips[ci].ru;
        int cw = measureTextWidth(clbl, 11) + 20;
        Color activeAccent = (chips[ci].mode == CatalogSortMode::FavoritesOnly || chips[ci].mode == CatalogSortMode::IconsOnly)
            ? Theme::COLOR_FOCUS_PINK
            : Theme::COLOR_FOCUS_CYAN;
        drawRoundedRect(chipX, 83, cw, 34, 9, active
            ? (activeAccent.r > 0x80 ? Color{0xEC, 0x48, 0x99, 0x2A} : Theme::COLOR_FOCUS_FILL)
            : Theme::COLOR_PILL_BG);
        drawRoundedOutline(chipX, 83, cw, 34, 9, active ? activeAccent : Theme::COLOR_BORDER, active ? activeAccent : Theme::COLOR_BORDER, active ? 2 : 1);
        drawTextCentered(clbl, chipX + cw / 2, 93, active ? activeAccent : Theme::COLOR_TEXT_MUTED, 11);
        chipX += cw + 6;
    }

    // Поле поиска [Y] справа сверху (x = 765, y = 82, w = 468, h = 36)
    bool hasSearch = !m_catalogSearchQuery.empty();
    drawGlassCard(765, 82, 468, 36, hasSearch, false);
    drawSearchIcon(783, 100, hasSearch ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED);
    std::string searchLabel = hasSearch
        ? (tr("Поиск: ", "Search: ") + m_catalogSearchQuery)
        : tr("Поиск по игре или TitleID...", "Search game or TitleID...");
    drawText(searchLabel, 798, 91, hasSearch ? Theme::COLOR_TEXT_PRIMARY : Theme::COLOR_TEXT_MUTED, 12, 335);
    drawRoundedRect(1147, 87, 78, 26, 6, Theme::COLOR_FOCUS_FILL);
    drawRoundedOutline(1147, 87, 78, 26, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered(tr("[Y] Поиск", "[Y] Search"), 1186, 93, Theme::COLOR_FOCUS_CYAN, 11);

    // Баннер режима привязки кастомного форвардера
    bool isLinkingForwarder = !m_linkingTargetTitleId.empty();
    if (isLinkingForwarder) {
        drawRoundedRect(46, 123, 1188, 28, 7, {0xF5, 0x9E, 0x0B, 0x2C});
        drawRoundedOutline(46, 123, 1188, 28, 7, Theme::COLOR_WARNING, Theme::COLOR_WARNING, 1);
        std::string bindMsg = tr("⚡ ПРИВЯЗКА К ИГРЕ: ", "⚡ BINDING TO: ") + m_linkingTargetGameName +
                              " [" + m_linkingTargetTitleId + "]  —  " +
                              tr("выберите любую игру ниже ([A] или [X])  •  [B] Отмена",
                                 "pick any catalog game below ([A] or [X])  •  [B] Cancel");
        drawTextCentered(bindMsg, 640, 130, Theme::COLOR_WARNING, 11, 1160);
    }

    int totalFiltered = static_cast<int>(m_filteredCatalogGames.size());
    if (totalFiltered == 0) {
        if (isFavTab) {
            drawRoundedRect(490, 200, 300, 240, 24, {0x14, 0x1A, 0x28, 0xFF});
            drawRoundedOutline(490, 200, 300, 240, 24, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 2);
            drawTextCentered("★", 640, 245, Theme::COLOR_FOCUS_PINK, 36);
            drawTextCentered(tr("Избранное пусто", "Favorites is Empty"), 640, 295, Theme::COLOR_TEXT_PRIMARY, 18);
            drawTextCentered(tr("Нажмите [X] -> В избранное ★ на любой игре,", "Press [X] -> Favorite ★ on any game"), 640, 330, Theme::COLOR_TEXT_MUTED, 13);
            drawTextCentered(tr("чтобы добавить её в быстрый доступ", "to add it to your quick favorites"), 640, 350, Theme::COLOR_TEXT_MUTED, 13);
            drawPillButton(540, 380, 200, 36, tr("[-] Сбросить фильтр", "[-] Reset Filter"), true, Theme::COLOR_FOCUS_CYAN);
        } else {
            drawTextCentered(tr("Игры по вашему запросу не найдены", "No games found matching your filter"), 640, 320, Theme::COLOR_TEXT_MUTED, 16);
            drawTextCentered(tr("Нажмите [Y] для изменения поиска или [-] для смены чип-фильтра", "Press [Y] to change search or [-] to cycle filter chip"), 640, 355, Theme::COLOR_FOCUS_CYAN, 13);
        }
        return;
    }

    // =========================================================================================
    // ЛЕВАЯ КОЛОНКА SPLIT-STUDIO (x = 46, w = 738): Чистые карточки каталога без визуального шума
    // =========================================================================================
    const int visibleCount = isLinkingForwarder ? 4 : 5;
    m_catalogSelectedIndex = std::clamp(m_catalogSelectedIndex, 0, totalFiltered - 1);
    if (m_catalogSelectedIndex < m_catalogScrollOffset) {
        m_catalogScrollOffset = m_catalogSelectedIndex;
    }
    if (m_catalogSelectedIndex >= m_catalogScrollOffset + visibleCount) {
        m_catalogScrollOffset = m_catalogSelectedIndex - visibleCount + 1;
    }

    int listX = 46;
    int listW = 738;
    int y = isLinkingForwarder ? 158 : 134;
    int endIdx = std::min(totalFiltered, m_catalogScrollOffset + visibleCount);

    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        const auto& game = m_filteredCatalogGames[i];
        bool isFocused = (i == m_catalogSelectedIndex);
        bool isFav = hasGameFavorites(game.titleId);

        bool isOnConsole = false;
        bool hasActiveCoverOnConsole = false;
        for (const auto& ig : m_installedGames) {
            if (ig.titleId == game.titleId) {
                isOnConsole = true;
                hasActiveCoverOnConsole = ig.hasInstalledCover || ig.hasInstalledIcon;
                break;
            }
        }

        drawGlassCard(listX, y, listW, 88, isFocused, isFocused);

        // Обложка 68x68 слева
        int boxX = listX + 12;
        int boxY = y + 10;
        drawRoundedRect(boxX, boxY, 68, 68, 12, {0x14, 0x1A, 0x28, 0xFF});

        auto covVars = getCoverVariants(game);
        SDL_Texture* rowThumbTex = nullptr;
        if (!covVars.empty()) {
            int selV = isFocused ? std::clamp(getSelectedCatalogVariantIndex(game), 0, static_cast<int>(covVars.size()) - 1) : 0;
            const auto& fv = covVars[selV];
            std::string rUrl = fv.previewUrl;
            if (rUrl.empty()) {
                std::string drvId = extractDriveIdFromUrl(fv.url);
                if (!drvId.empty()) {
                    rUrl = "https://drive.google.com/thumbnail?id=" + drvId + "&sz=w320";
                }
            }
            rowThumbTex = getOrRequestRowThumb(game.titleId + "_" + fv.id, rUrl, isFocused);
        }

        if (rowThumbTex) {
            SDL_Rect dst{boxX + 2, boxY + 2, 64, 64};
            SDL_RenderCopy(m_renderer, rowThumbTex, nullptr, &dst);
        } else {
            drawRoundedRect(boxX + 21, boxY + 15, 26, 38, 4, {0x26, 0x32, 0x48, 0xFF});
            drawRoundedRect(boxX + 23, boxY + 17, 22, 10, 2, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN);
            drawRoundedRect(boxX + 23, boxY + 30, 22, 20, 2, {0x0E, 0x14, 0x22, 0xFF});
        }
        Color thumbOut = isFocused ? (isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN) : Theme::COLOR_BORDER;
        drawRoundedOutline(boxX, boxY, 68, 68, 12, thumbOut, thumbOut, isFocused ? 2 : 1);

        // Инфо о тайтле
        int infoX = boxX + 82;
        std::string dispTitle = (isFav ? "★ " : "") + game.title;
        drawText(dispTitle, infoX, y + 12, isFocused ? (isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN) : Theme::COLOR_TEXT_PRIMARY, 16, 495);

        std::string pubText = game.publisher.empty() ? "Nintendo Switch" : game.publisher;
        drawText(game.titleId + "  •  " + pubText, infoX, y + 36, Theme::COLOR_TEXT_MUTED, 11, 460);

        // Компактный ряд бейджей снизу строки (y + 56)
        int curBadgeX = infoX;
        int vCount = static_cast<int>(covVars.size());
        std::string vStr = std::to_string(vCount) + tr(" фон.", " cov.");
        int vBadgeW = measureTextWidth(vStr, 10) + 14;
        drawRoundedRect(curBadgeX, y + 56, vBadgeW, 20, 5, Theme::COLOR_FOCUS_FILL);
        drawRoundedOutline(curBadgeX, y + 56, vBadgeW, 20, 5, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered(vStr, curBadgeX + vBadgeW / 2, y + 59, Theme::COLOR_FOCUS_CYAN, 10);
        curBadgeX += vBadgeW + 6;

        auto gameIcons = getUniqueIconVariants(game);
        if (!gameIcons.empty()) {
            std::string icoBadgeStr = "HQ 1:1 (" + std::to_string(gameIcons.size()) + ")";
            int icoBadgeW = measureTextWidth(icoBadgeStr, 10) + 14;
            drawRoundedRect(curBadgeX, y + 56, icoBadgeW, 20, 5, Color{0xEC, 0x48, 0x99, 0x2E});
            drawRoundedOutline(curBadgeX, y + 56, icoBadgeW, 20, 5, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
            drawTextCentered(icoBadgeStr, curBadgeX + icoBadgeW / 2, y + 59, Theme::COLOR_FOCUS_PINK, 10);
            curBadgeX += icoBadgeW + 6;
        }

        bool anyAudio = false;
        for (const auto& cv : covVars) {
            if (cv.hasAudio) { anyAudio = true; break; }
        }
        if (anyAudio) {
            std::string audStr = tr("Звук ♪", "Audio ♪");
            int audW = measureTextWidth(audStr, 10) + 14;
            drawRoundedRect(curBadgeX, y + 56, audW, 20, 5, {0x10, 0xB9, 0x81, 0x26});
            drawRoundedOutline(curBadgeX, y + 56, audW, 20, 5, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
            drawTextCentered(audStr, curBadgeX + audW / 2, y + 59, Theme::COLOR_SUCCESS, 10);
            curBadgeX += audW + 6;
        }

        // Правый индикатор строки: статус на консоли + шеврон фокуса
        if (hasActiveCoverOnConsole) {
            drawRoundedRect(listX + listW - 118, y + 14, 104, 22, 6, {0x10, 0xB9, 0x81, 0x30});
            drawRoundedOutline(listX + listW - 118, y + 14, 104, 22, 6, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
            drawTextCentered(tr("АКТИВЕН ✓", "ACTIVE ✓"), listX + listW - 66, y + 18, Theme::COLOR_SUCCESS, 10);
        } else if (isOnConsole) {
            drawRoundedRect(listX + listW - 118, y + 14, 104, 22, 6, {0x00, 0xF0, 0xFF, 0x1E});
            drawRoundedOutline(listX + listW - 118, y + 14, 104, 22, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
            drawTextCentered(tr("НА SWITCH", "INSTALLED"), listX + listW - 66, y + 18, Theme::COLOR_FOCUS_CYAN, 10);
        }

        if (isFocused) {
            drawRoundedRect(listX + listW - 118, y + 48, 104, 26, 6, isLinkingForwarder ? Color{0xF5, 0x9E, 0x0B, 0x2E} : Theme::COLOR_FOCUS_FILL);
            drawRoundedOutline(listX + listW - 118, y + 48, 104, 26, 6,
                               isLinkingForwarder ? Theme::COLOR_WARNING : Theme::COLOR_FOCUS_CYAN,
                               isLinkingForwarder ? Theme::COLOR_WARNING : Theme::COLOR_FOCUS_CYAN, 1);
            drawTextCentered(isLinkingForwarder ? tr("[A] Связать", "[A] Bind") : tr("[A] Открыть", "[A] Open"),
                             listX + listW - 66, y + 54,
                             isLinkingForwarder ? Theme::COLOR_WARNING : Theme::COLOR_FOCUS_CYAN, 11);
        }

        y += 96;
    }

    // Неоновый маркер текущего ряда слева
    if (totalFiltered > 0) {
        int barY = static_cast<int>(std::round(m_smoothCatalogSelY)) + 12;
        drawRoundedRect(39, barY, 5, 64, 2, isFavTab ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN);
    }

    // =========================================================================================
    // ПРАВАЯ КОЛОНКА SPLIT-STUDIO (x = 798, w = 436): Постоянный Живой Комбо-Стенд 16:9 + 1:1
    // =========================================================================================
    int stX = 798;
    int stY = isLinkingForwarder ? 158 : 134;
    int stW = 436;
    int stH = isLinkingForwarder ? 474 : 498;
    drawGlassCard(stX, stY, stW, stH, true, true);

    const auto& selGame = m_filteredCatalogGames[m_catalogSelectedIndex];
    auto selCovers = getCoverVariants(selGame);
    auto selIcons = getUniqueIconVariants(selGame);
    int selVarIdx = selCovers.empty() ? 0 : std::clamp(getSelectedCatalogVariantIndex(selGame), 0, static_cast<int>(selCovers.size()) - 1);
    const Variant* activeCover = selCovers.empty() ? nullptr : &selCovers[selVarIdx];
    const Variant* activeIcon = selIcons.empty() ? nullptr : &selIcons[0];

    // Шапка правого стенда + позиция в списке
    drawText(tr("ЖИВОЕ КОМБО-ПРЕВЬЮ", "LIVE COMBO STAGE"), stX + 18, stY + 13, Theme::COLOR_FOCUS_CYAN, 11);
    std::string posCounter = std::to_string(m_catalogSelectedIndex + 1) + " / " + std::to_string(totalFiltered);
    drawTextRight(posCounter, stX + stW - 18, stY + 13, Theme::COLOR_TEXT_MUTED, 11);

    // Экран 16:9 (400 x 225)
    int pvX = stX + 18;
    int pvY = stY + 36;
    int pvW = 400;
    int pvH = 225;
    SDL_Rect pvDst{pvX + 2, pvY + 2, pvW - 4, pvH - 4};
    drawRoundedRect(pvX, pvY, pvW, pvH, 12, {0x07, 0x0B, 0x14, 0xFF});

    bool stagePlayingVideo = (!m_isFullscreenPreview && !m_isCollectionBrowserOpen && m_videoPlayer.isPlaying());
    if (stagePlayingVideo) {
        m_videoPlayer.render(m_renderer, &pvDst);
        drawRoundedRect(pvX + 10, pvY + 10, 96, 22, 5, {0x08, 0x12, 0x1E, 0xE6});
        drawRoundedOutline(pvX + 10, pvY + 10, 96, 22, 5, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
        drawTextCentered("LIVE 720p", pvX + 58, pvY + 14, Theme::COLOR_SUCCESS, 10);
    } else if (m_videoIconDockTexture) {
        SDL_RenderCopy(m_renderer, m_videoIconDockTexture, nullptr, &pvDst);
        if (m_collectionVideoDownloading || m_catalogDockDirty) {
            drawRoundedRect(pvX + 10, pvY + 10, 128, 22, 5, {0x08, 0x12, 0x1E, 0xE6});
            drawLoadingSpinner(pvX + 22, pvY + 21, 5, Theme::COLOR_FOCUS_CYAN);
            drawText(tr("Видео...", "Video..."), pvX + 34, pvY + 14, Theme::COLOR_FOCUS_CYAN, 10);
        }
    } else {
        SDL_Texture* fallbackTex = activeCover ? findCachedThumbTexture(selGame.titleId, *activeCover, false) : nullptr;
        if (fallbackTex) {
            SDL_RenderCopy(m_renderer, fallbackTex, nullptr, &pvDst);
            if (m_collectionVideoDownloading || m_catalogDockDirty) {
                drawRoundedRect(pvX + 10, pvY + 10, 128, 22, 5, {0x08, 0x12, 0x1E, 0xE6});
                drawLoadingSpinner(pvX + 22, pvY + 21, 5, Theme::COLOR_FOCUS_CYAN);
                drawText(tr("Буфер...", "Stream..."), pvX + 34, pvY + 14, Theme::COLOR_FOCUS_CYAN, 10);
            }
        } else {
            drawRoundedRect(pvX + 8, pvY + 8, pvW - 16, pvH - 16, 10, {0x0F, 0x17, 0x28, 0xFF});
            drawLoadingSpinner(pvX + pvW / 2, pvY + pvH / 2 - 14, 16, Theme::COLOR_FOCUS_CYAN);
            drawTextCentered(tr("Подгрузка живого кадра...", "Loading live frame..."), pvX + pvW / 2, pvY + pvH / 2 + 16, Theme::COLOR_FOCUS_CYAN, 12);
        }
    }
    drawNeonRoundedOutline(pvX, pvY, pvW, pvH, 12, 2);

    // Наложенный квадратный слот 256x256 HQ-иконки в правом нижнем углу экрана 16:9 (80x80)
    if (activeIcon) {
        int icSz = 78;
        int icX = pvX + pvW - icSz - 10;
        int icY = pvY + pvH - icSz - 10;
        drawRoundedRect(icX - 3, icY - 3, icSz + 6, icSz + 6, 11, {0x06, 0x0A, 0x14, 0xF8});
        std::string icThumbUrl = activeIcon->previewUrl;
        if (icThumbUrl.empty()) {
            std::string dId = extractDriveIdFromUrl(!activeIcon->iconUrl.empty() ? activeIcon->iconUrl : activeIcon->url);
            if (!dId.empty()) icThumbUrl = "https://drive.google.com/thumbnail?id=" + dId + "&sz=w320";
        }
        SDL_Texture* icTex = getOrRequestRowThumb("icon_" + selGame.titleId + "_" + activeIcon->id, icThumbUrl, true);
        if (icTex) {
            SDL_Rect icDst{icX, icY, icSz, icSz};
            SDL_RenderCopy(m_renderer, icTex, nullptr, &icDst);
        } else {
            drawRoundedRect(icX, icY, icSz, icSz, 9, {0x16, 0x1E, 0x32, 0xFF});
            drawTextCentered("1:1 HQ", icX + icSz / 2, icY + icSz / 2 - 6, Theme::COLOR_FOCUS_PINK, 10);
        }
        drawRoundedOutline(icX - 3, icY - 3, icSz + 6, icSz + 6, 11, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_CYAN, 2);
        drawRoundedRect(icX + 4, icY + icSz - 18, icSz - 8, 14, 4, {0x08, 0x0E, 0x1C, 0xE8});
        drawTextCentered("256x256", icX + icSz / 2, icY + icSz - 16, Theme::COLOR_FOCUS_PINK, 9);
    }

    // Подсказка полноэкранного режима [L3] в левом нижнем углу 16:9 окна
    drawRoundedRect(pvX + 10, pvY + pvH - 28, 126, 20, 5, {0x08, 0x10, 0x1E, 0xDD});
    drawTextCentered(tr("[L3] На весь экран", "[L3] Fullscreen"), pvX + 73, pvY + pvH - 25, Theme::COLOR_TEXT_SECONDARY, 9);

    // Детали выбранной игры и текущего варианта под превью
    int metaY = pvY + pvH + 12;
    drawText(selGame.title, stX + 18, metaY, Theme::COLOR_TEXT_PRIMARY, 16, stW - 36);

    if (activeCover) {
        double mb = static_cast<double>(activeCover->sizeBytes) / (1024.0 * 1024.0);
        char specBuf[128];
        if (mb >= 0.1) {
            std::snprintf(specBuf, sizeof(specBuf), "%s  •  %.1f MB  •  %s",
                          activeCover->name.c_str(), mb,
                          activeCover->hasAudio ? tr("Со звуком ♪", "Audio ♪") : "1280x720 HD");
        } else {
            std::snprintf(specBuf, sizeof(specBuf), "%s  •  1280x720 HD  •  %s",
                          activeCover->name.c_str(),
                          activeCover->hasAudio ? tr("Со звуком ♪", "Audio ♪") : "30 FPS");
        }
        drawText(specBuf, stX + 18, metaY + 24, Theme::COLOR_FOCUS_CYAN, 11, stW - 36);
    }

    // Переключатель вариантов [◄ / ►] прямо на правом стенде
    int swY = metaY + 48;
    if (selCovers.size() > 1) {
        std::string swTxt = tr("◄ [Влево / Вправо] Вариант ", "◄ [Left / Right] Variant ") +
                            std::to_string(selVarIdx + 1) + " / " + std::to_string(selCovers.size()) + " ►";
        drawRoundedRect(stX + 18, swY, stW - 36, 28, 7, {0x00, 0xF0, 0xFF, 0x1A});
        drawRoundedOutline(stX + 18, swY, stW - 36, 28, 7, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered(swTxt, stX + stW / 2, swY + 6, Theme::COLOR_FOCUS_CYAN, 11);
    } else {
        std::string singleTxt = activeIcon
            ? tr("Готово к Комбо: 720p Фон + 256x256 Ultra-HQ Иконка", "Combo Ready: 720p Cover + 256x256 Ultra-HQ Icon")
            : tr("Готово к установке: 720p Видеофон 4IFIR", "Ready to install: 4IFIR 720p Video Cover");
        drawRoundedRect(stX + 18, swY, stW - 36, 28, 7, {0x12, 0x1A, 0x2B, 0xDD});
        drawRoundedOutline(stX + 18, swY, stW - 36, 28, 7, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        drawTextCentered(singleTxt, stX + stW / 2, swY + 7, activeIcon ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_MUTED, 10, stW - 48);
    }

    // Нижние кнопки действий правого стенда: [X] Действия ▾ и [A] Коллекция / Привязать
    int btnY = stY + stH - 52;
    drawRoundedRect(stX + 18, btnY, 192, 40, 9, {0xEC, 0x48, 0x99, 0x26});
    drawRoundedOutline(stX + 18, btnY, 192, 40, 9, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 2);
    drawTextCentered(tr("[X] Действия / Комбо ▾", "[X] Actions / Combo ▾"), stX + 18 + 96, btnY + 12, Theme::COLOR_FOCUS_PINK, 11);

    drawRoundedRect(stX + 224, btnY, 194, 40, 9, isLinkingForwarder ? Color{0xF5, 0x9E, 0x0B, 0x2C} : Theme::COLOR_FOCUS_FILL);
    drawNeonRoundedOutline(stX + 224, btnY, 194, 40, 9, 2);
    drawTextCentered(isLinkingForwarder ? tr("[A] Привязать к игре", "[A] Bind to Game") : tr("[A] Все варианты", "[A] All Variants"),
                     stX + 224 + 97, btnY + 12,
                     isLinkingForwarder ? Theme::COLOR_WARNING : Theme::COLOR_FOCUS_CYAN, 12);
}
void App::renderTabDownloads() {
    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    drawText(tr("Очередь загрузки видеофонов 4IFIR", "4IFIR Video Backgrounds Download Queue"), 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);

    std::vector<DownloadTask> tasksCopy;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        tasksCopy = m_downloadQueue;
    }

    if (tasksCopy.empty()) {
        drawText(tr("Очередь пуста. Выберите видеофон в разделе 'Мои игры' или установите все недостающие.",
                    "Queue is empty. Select a video cover in 'My Games' or install all missing covers."),
                 60, 160, Theme::COLOR_TEXT_MUTED, 15);
        drawText(tr("Нажмите [Y] на главной вкладке, чтобы автоматически добавить все игры в очередь.",
                    "Press [Y] on the Home tab to automatically queue all missing games."),
                 60, 195, Theme::COLOR_FOCUS_CYAN, 14);
        return;
    }

    const int visibleTasks = 5;
    int totalTasks = static_cast<int>(tasksCopy.size());
    m_downloadsSelectedIndex = std::clamp(m_downloadsSelectedIndex, 0, totalTasks - 1);
    if (m_downloadsSelectedIndex < m_downloadsScrollOffset) {
        m_downloadsScrollOffset = m_downloadsSelectedIndex;
    }
    if (m_downloadsSelectedIndex >= m_downloadsScrollOffset + visibleTasks) {
        m_downloadsScrollOffset = m_downloadsSelectedIndex - visibleTasks + 1;
    }
    if (m_downloadsScrollOffset < 0) m_downloadsScrollOffset = 0;

    std::string summary = tr("Задач в очереди: ", "Queued tasks: ") + std::to_string(totalTasks) +
        "  (" + std::to_string(m_downloadsSelectedIndex + 1) + " / " + std::to_string(totalTasks) + ")";
    drawText(summary, 520, 110, Theme::COLOR_FOCUS_CYAN, 13);

    int y = 160;
    int endIdx = std::min(totalTasks, m_downloadsScrollOffset + visibleTasks);
    for (int i = m_downloadsScrollOffset; i < endIdx; ++i) {
        const auto& task = tasksCopy[i];
        bool isSelected = (i == m_downloadsSelectedIndex);
        bool isDownloading = (task.state == TaskState::Downloading);

        // 4IFIR Frosted Card for each task with cursor focus support (Audit Finding #6)
        drawGlassCard(60, y, 1160, 80, isSelected || isDownloading, isSelected);

        // Title and variant
        if (task.iconOnly) {
            drawText(task.gameTitle + "  [" + tr("Иконка: ", "Icon: ") + task.variant.name + "]", 85, y + 14, (isSelected || isDownloading) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 890);
        } else if (task.coverOnly) {
            drawText(task.gameTitle + "  [" + tr("Только видеофон: ", "Cover Only: ") + task.variant.name + "]", 85, y + 14, (isSelected || isDownloading) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 890);
        } else {
            drawText(task.gameTitle + "  [" + task.variant.name + "]", 85, y + 14, (isSelected || isDownloading) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 890);
        }

        if (task.state == TaskState::Downloading) {
            // Sleek Capsule Progress Bar
            drawCapsuleProgressBar(85, y + 44, 480, 16, task.progressPercent);

            std::string progStr;
            if (task.iconOnly) {
                progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                    std::to_string(task.bytesDownloaded / 1024) + " / " +
                    std::to_string(task.totalBytes / 1024) + " KB)";
            } else {
                progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                    std::to_string(task.bytesDownloaded / (1024 * 1024)) + " / " +
                    std::to_string(task.totalBytes / (1024 * 1024)) + " MB)";
            }
            drawText(progStr, 580, y + 44, Theme::COLOR_FOCUS_CYAN, 13);

            double speedKb = task.downloadSpeedBps / 1024.0;
            std::string speedStr;
            if (speedKb >= 1024.0) {
                speedStr = std::to_string(static_cast<int>(speedKb / 1024.0)) + "." +
                    std::to_string(static_cast<int>((speedKb / 102.4)) % 10) + " MB/s";
            } else {
                speedStr = std::to_string(static_cast<int>(speedKb)) + " KB/s";
            }
            drawText(speedStr, 760, y + 44, Theme::COLOR_TEXT_MUTED, 13);

            drawRect(1010, y + 24, 180, 32, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawTextCentered(tr("Загрузка...", "Downloading..."), 1100, y + 31, Theme::COLOR_FOCUS_CYAN, 13);
        } else if (task.state == TaskState::Verifying) {
            std::string verMsg = task.iconOnly
                ? tr("Установка в 4IFIR (sdmc:/recordings/icons/)...", "Installing into 4IFIR (sdmc:/recordings/icons/)...")
                : tr("Установка в 4IFIR (sdmc:/recordings/covers/)...", "Installing into 4IFIR (sdmc:/recordings/covers/)...");
            drawText(verMsg, 85, y + 44, Theme::COLOR_WARNING, 14);
            drawRect(1010, y + 24, 180, 32, {0xF5, 0x9E, 0x0B, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_WARNING, 1);
            drawTextCentered(tr("Установка...", "Installing..."), 1100, y + 31, Theme::COLOR_WARNING, 13);
        } else if (task.state == TaskState::Completed) {
            std::string okMsg = task.iconOnly
                ? tr("Успешно активирована в sdmc:/recordings/icons/", "Activated in sdmc:/recordings/icons/")
                : tr("Успешно активирован в sdmc:/recordings/covers/", "Activated in sdmc:/recordings/covers/");
            drawText(okMsg, 85, y + 44, Theme::COLOR_SUCCESS, 14);
            drawRect(1010, y + 24, 180, 32, {0x10, 0xB9, 0x81, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_SUCCESS, 1);
            drawTextCentered(isSelected ? tr("[-] Убрать", "[-] Remove") : tr("[OK] Установлен", "[OK] Installed"), 1100, y + 31, Theme::COLOR_SUCCESS, 13);
        } else if (task.state == TaskState::Failed) {
            drawText(tr("Ошибка: ", "Error: ") + task.errorMessage, 85, y + 44, Theme::COLOR_DANGER, 13, 900);
            drawRect(1010, y + 24, 180, 32, {0xF4, 0x3F, 0x5E, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_DANGER, 1);
            drawTextCentered(isSelected ? tr("[A] Повторить", "[A] Retry") : tr("[X] Ошибка", "[X] Failed"), 1100, y + 31, Theme::COLOR_DANGER, 13);
        } else { // Pending
            drawText(tr("В очереди ожидания...", "Waiting in queue..."), 85, y + 44, Theme::COLOR_TEXT_MUTED, 14);
            drawRect(1010, y + 24, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_BORDER, 1);
            drawTextCentered(isSelected ? tr("[-] Отменить", "[-] Cancel") : tr("Ожидание", "Pending"), 1100, y + 31, isSelected ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_MUTED, 13);
        }

        y += 94;
    }

    // Smooth 60 FPS neon selection indicator bar on the left of Downloads list
    if (totalTasks > 0) {
        int barY = static_cast<int>(std::round(m_smoothDownloadsSelY)) + 12;
        drawRoundedRect(52, barY, 5, 56, 2, Theme::COLOR_FOCUS_CYAN);
    }
}

void App::renderTabSettings() {
    const auto& s = getStrings(m_language);
    (void)s;

#ifdef HAS_SDL2
    uint32_t nowTicks = SDL_GetTicks();
    if (m_lastStorageRefreshTick == 0 || nowTicks - m_lastStorageRefreshTick > 3000) {
        refreshStorageStats();
        m_lastStorageRefreshTick = nowTicks;
    }
#else
    refreshStorageStats();
#endif

    // Main 4IFIR Frosted Glass Container
    drawGlassCard(30, 80, 1220, 580, false, false);

    drawText(std::string("4IFIR System & Storage Manager  |  ") + Config::APP_NAME, 60, 95, Theme::COLOR_TEXT_PRIMARY, 20);

    // MicroSD Visual Dashboard Card at y = 120
    drawRect(50, 122, 1180, 100, Theme::COLOR_BG_SURFACE);
    drawRectOutline(50, 122, 1180, 100, Theme::COLOR_BORDER, 1);

    double freeGb = static_cast<double>(m_storageStats.freeSdBytes) / (1024.0 * 1024.0 * 1024.0);
    double totalGb = static_cast<double>(m_storageStats.totalSdBytes) / (1024.0 * 1024.0 * 1024.0);
    double usedGb = std::max(0.0, totalGb - freeGb);
    double usedPct = (totalGb > 0.0) ? (usedGb / totalGb * 100.0) : 0.0;

    char sdInfoBuf[128];
    if (m_language == Language::Russian) {
        snprintf(sdInfoBuf, sizeof(sdInfoBuf), "MicroSD: %.1f GB свободно из %.1f GB (%.1f%% занято)", freeGb, totalGb, usedPct);
    } else {
        snprintf(sdInfoBuf, sizeof(sdInfoBuf), "MicroSD: %.1f GB free of %.1f GB (%.1f%% used)", freeGb, totalGb, usedPct);
    }
    drawText(sdInfoBuf, 70, 132, Theme::COLOR_FOCUS_CYAN, 14);

    drawCapsuleProgressBar(70, 154, 1140, 14, usedPct);

    // Four metric badges inside dashboard (Covers, Video Icons, Thumbnails Cache, Video Cache)
    double coversMb = static_cast<double>(m_storageStats.coversBytes) / (1024.0 * 1024.0);
    double iconsMb = static_cast<double>(m_storageStats.iconsBytes) / (1024.0 * 1024.0);
    double thumbsMb = static_cast<double>(m_storageStats.thumbsBytes) / (1024.0 * 1024.0);
    double vidCacheMb = static_cast<double>(m_storageStats.vidCacheBytes) / (1024.0 * 1024.0);

    char covBuf[64], icoBuf[64], thBuf[64], vcBuf[64];
    if (m_language == Language::Russian) {
        snprintf(covBuf, sizeof(covBuf), "Видеофоны: %d шт. (%.1f MB)", m_storageStats.coversCount, coversMb);
        snprintf(icoBuf, sizeof(icoBuf), "Иконки: %d шт. (%.1f MB)", m_storageStats.iconsCount, iconsMb);
        snprintf(thBuf, sizeof(thBuf), "Кэш превью: %d шт. (%.1f MB)", m_storageStats.thumbsCount, thumbsMb);
        snprintf(vcBuf, sizeof(vcBuf), "Кэш видео: %d шт. (%.1f MB)", m_storageStats.vidCacheCount, vidCacheMb);
    } else {
        snprintf(covBuf, sizeof(covBuf), "Covers: %d (%.1f MB)", m_storageStats.coversCount, coversMb);
        snprintf(icoBuf, sizeof(icoBuf), "Icons: %d (%.1f MB)", m_storageStats.iconsCount, iconsMb);
        snprintf(thBuf, sizeof(thBuf), "Thumb Cache: %d (%.1f MB)", m_storageStats.thumbsCount, thumbsMb);
        snprintf(vcBuf, sizeof(vcBuf), "Video Cache: %d (%.1f MB)", m_storageStats.vidCacheCount, vidCacheMb);
    }

    drawText(covBuf, 70, 185, Theme::COLOR_SUCCESS, 13);
    drawText(icoBuf, 360, 185, Theme::COLOR_FOCUS_CYAN, 13);
    drawText(thBuf, 630, 185, Theme::COLOR_FOCUS_CYAN, 13);
    drawText(vcBuf, 920, 185, Theme::COLOR_FOCUS_PINK, 13);

    // Settings list options (8 rows including Idea 4: Auto-Rotate Cover Slots on Boot)
    struct SettingRow {
        std::string title;
        std::string desc;
        std::string value;
        Color valColor;
    };

    std::vector<SettingRow> rows = {
        {tr("Обновление приложения (NRO)", "Update Application (NRO)"),
         (m_language == Language::Russian)
             ? (std::string("Проверить и установить новую версию ") + Config::APP_NAME + " с GitHub [+]")
             : (std::string("Check and install the latest ") + Config::APP_NAME + " release from GitHub [+]"),
         std::string("v") + Config::APP_VERSION + " [A]", Theme::COLOR_FOCUS_CYAN},
        {tr("Турбо-обновление каталога (.gz)", "Turbo Catalog Update (.gz)"),
         tr("Загрузить сжатый индекс catalog.min.json.gz (~0.8 MB вместо 6.9 MB)", "Download compressed catalog.min.json.gz (~0.8 MB instead of 6.9 MB)"),
         "GitHub CDN [A]", Theme::COLOR_FOCUS_CYAN},
        {tr("Авто-ротация слотов видеофонов при входе", "Auto-Rotate Multi-Cover Slots on Boot"),
         tr("Автоматически менять активный фон при запуске для игр с 2+ установленными слотами", "Automatically cycle active cover on boot for games with 2+ installed slots"),
         m_autoRotateCoversOnBoot ? tr("ВКЛЮЧЕНО [A]", "ENABLED [A]") : tr("ВЫКЛЮЧЕНО [A]", "DISABLED [A]"),
         m_autoRotateCoversOnBoot ? Theme::COLOR_SUCCESS : Theme::COLOR_TEXT_MUTED},
        {tr("Очистить кэш мини-превью (галерея)", "Clear Thumbnail Cache (Gallery)"),
         tr("Удалить сохраненные миниатюры обложек (thumbs/) для освобождения места", "Delete cached cover & icon thumbnails (thumbs/) to free SD space"),
         tr("[A] Очистить", "[A] Clear"), Theme::COLOR_FOCUS_PINK},
        {tr("Очистить кэш видеоплеера (видео)", "Clear Video Preview Cache (MP4)"),
         tr("Удалить временные видеофайлы предпросмотра (mp4) на SD-карте", "Delete temporary preview video files (mp4) on SD card"),
         tr("[A] Очистить", "[A] Clear"), Theme::COLOR_FOCUS_PINK},
        {tr("Очистить локальный кэш каталога", "Reset Local Catalog Cache"),
         tr("Сбросить локальный файл cache.json и пересканировать игры", "Reset local cache.json and rescan installed games"),
         tr("[A] Сброс", "[A] Reset"), Theme::COLOR_WARNING},
        {tr("Проверка целостности фонов и иконок", "Verify Covers & Icons Integrity"),
         tr("Сканирование установленных видеофонов и видеоиконок на битые файлы", "Scan installed video covers and icons for corrupted files"),
         tr("[A] Сканировать", "[A] Scan"), Theme::COLOR_FOCUS_CYAN},
        {tr("Язык интерфейса / Language", "Interface Language / Язык"),
         tr("Выбор языка отображения меню и подсказок управления", "Select display language for menus and button prompts"),
         (m_language == Language::Russian ? "Русский [A]" : "English [A]"), Theme::COLOR_TEXT_PRIMARY}
    };

    int rowY = 232;
    for (size_t i = 0; i < rows.size(); ++i) {
        bool isFocused = (static_cast<int>(i) == m_settingsSelectedIndex);

        if (isFocused) {
            drawRect(50, rowY, 1180, 42, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(50, rowY, 1180, 42, 2);
        } else {
            drawRect(50, rowY, 1180, 42, Theme::COLOR_BG_SURFACE);
            drawRectOutline(50, rowY, 1180, 42, Theme::COLOR_BORDER, 1);
        }

        drawText(rows[i].title, 75, rowY + 5, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14, 850);
        drawText(rows[i].desc, 75, rowY + 24, Theme::COLOR_TEXT_MUTED, 11, 850);

        drawText(rows[i].value, 940, rowY + 12, rows[i].valColor, 13, 270);

        rowY += 47;
    }

    // Smooth 60 FPS neon selection indicator bar on the left of Settings rows
    int sBarY = static_cast<int>(std::round(m_smoothSettingsSelY)) + 5;
    drawRoundedRect(44, sBarY, 5, 32, 2, Theme::COLOR_FOCUS_CYAN);

    // Bottom Help Banner
    drawRect(50, 622, 1180, 32, Theme::COLOR_BG_BASE);
    drawRectOutline(50, 622, 1180, 32, Theme::COLOR_BORDER, 1);
    drawText(tr("Навигация: [D-Pad Вверх/Вниз] Выбор   |   [A] Применить / Очистить   |   [B] Главная",
                "Navigation: [D-Pad Up/Down] Select   |   [A] Apply / Clear   |   [B] Home"),
             75, 629, Theme::COLOR_TEXT_MUTED, 13);
}

void App::renderDialog() {
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x00, 0x00, 0x00, 0xCC});

    // 4IFIR Obsidian Glass Modal
    int dw = 700;
    int dh = 270;
    int dx = (Theme::SCREEN_WIDTH - dw) / 2;
    int dy = (Theme::SCREEN_HEIGHT - dh) / 2;

    drawRect(dx, dy, dw, dh, Theme::COLOR_BG_MODAL);
    drawNeonGradientOutline(dx, dy, dw, dh, 2);

    // Specialized dialog: Update Progress with Capsule Bar (Thread-safe via m_nroMutex — Audit Finding #5)
    if (m_activeDialog == DialogType::UpdateProgress) {
        std::string latestVer;
        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            latestVer = m_nroUpdateLatestVer;
        }
        std::string updTitle = latestVer.empty()
            ? m_dialogTitle
            : (tr("Загрузка обновления v", "Downloading Update v") + latestVer);
        drawText(updTitle, dx + 35, dy + 25, Theme::COLOR_FOCUS_CYAN, 20, dw - 70);
        drawText(m_dialogMessage, dx + 35, dy + 70, Theme::COLOR_TEXT_PRIMARY, 15, dw - 70);

        uint64_t bytes = m_nroUpdateBytesDownloaded.load();
        uint64_t total = m_nroUpdateTotalBytes.load();
        double pct = (total > 0) ? (static_cast<double>(bytes) / total * 100.0) : 0.0;

        // Sleek Capsule Progress Bar
        drawCapsuleProgressBar(dx + 35, dy + 115, dw - 70, 22, pct);

        std::string progStr = std::to_string(bytes / (1024 * 1024)) + "." +
                              std::to_string((bytes / (1024 * 102)) % 10) + " MB / " +
                              std::to_string(total / (1024 * 1024)) + "." +
                              std::to_string((total / (1024 * 102)) % 10) + " MB  (" +
                              std::to_string(static_cast<int>(pct)) + "%)";
        drawText(progStr, dx + 35, dy + 150, Theme::COLOR_FOCUS_CYAN, 14);
        drawText(tr("Обновление безопасно заменяет файл на SD карте без перезаписи в Horizon OS",
                    "Update safely replaces the NRO file on SD card via atomic rename"),
                 dx + 35, dy + 185, Theme::COLOR_TEXT_MUTED, 12, dw - 70);
        drawText(tr("[B] Скрыть окно в фон", "[B] Hide to background"), dx + 490, dy + 225, Theme::COLOR_TEXT_MUTED, 13);
        return;
    }

    drawText(m_dialogTitle, dx + 35, dy + 25, Theme::COLOR_FOCUS_CYAN, 20);

    // Specialized dialog: Update Available (Interactive Yes/No Prompt)
    if (m_activeDialog == DialogType::UpdateAvailable) {
        std::stringstream ss(m_dialogMessage);
        std::string rawLine;
        int msgY = dy + 68;
        while (std::getline(ss, rawLine, '\n')) {
            std::stringstream wordStream(rawLine);
            std::string word;
            std::string currentLine;
            while (wordStream >> word) {
                if (currentLine.empty()) {
                    currentLine = word;
                } else if (currentLine.length() + 1 + word.length() <= 54) {
                    currentLine += " " + word;
                } else {
                    drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_PRIMARY, 14, dw - 70);
                    msgY += 24;
                    currentLine = word;
                }
            }
            if (!currentLine.empty()) {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_PRIMARY, 14, dw - 70);
                msgY += 24;
            }
        }

        int btnW = 200;
        int btnH = 44;
        int btnY = dy + 200;

        // Button 0: [A] Да, обновить
        bool fYes = (m_dialogFocus == 0);
        drawGlassCard(dx + 120, btnY, btnW, btnH, fYes, false);
        drawText(tr("[A] Да, обновить", "[A] Yes, update"), dx + 145, btnY + 13, fYes ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);

        // Button 1: [B] Нет, позже
        bool fNo = (m_dialogFocus == 1);
        drawGlassCard(dx + 380, btnY, btnW, btnH, fNo, false);
        drawText(tr("[B] Нет, позже", "[B] No, later"), dx + 420, btnY + 13, fNo ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);
        return;
    }

    // Specialized dialog: Update Success
    if (m_activeDialog == DialogType::UpdateSuccess) {
        std::stringstream ss(m_dialogMessage);
        std::string line;
        int msgY = dy + 70;
        while (std::getline(ss, line, '\n')) {
            drawText(line, dx + 35, msgY, Theme::COLOR_TEXT_PRIMARY, 15);
            msgY += 26;
        }

        int btnW = 200;
        int btnH = 44;
        int btnY = dy + 195;
        drawRect(dx + 250, btnY, btnW, btnH, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(dx + 250, btnY, btnW, btnH, 2);
        drawText("[A] Перезапустить", dx + 275, btnY + 13, Theme::COLOR_FOCUS_CYAN, 15);
        return;
    }

    // Specialized dialog: Alert with auto word-wrap
    if (m_activeDialog == DialogType::MessageAlert) {
        std::stringstream ss(m_dialogMessage);
        std::string rawLine;
        int msgY = dy + 70;
        while (std::getline(ss, rawLine, '\n')) {
            std::stringstream wordStream(rawLine);
            std::string word;
            std::string currentLine;
            while (wordStream >> word) {
                if (currentLine.empty()) {
                    currentLine = word;
                } else if (currentLine.length() + 1 + word.length() <= 54) {
                    currentLine += " " + word;
                } else {
                    drawText(currentLine, dx + 35, msgY, Theme::COLOR_WARNING, 15, dw - 70);
                    msgY += 26;
                    currentLine = word;
                }
            }
            if (!currentLine.empty()) {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_WARNING, 15, dw - 70);
                msgY += 26;
            }
        }

        int btnW = 160;
        int btnH = 40;
        int btnY = dy + 195;
        drawRect(dx + 270, btnY, btnW, btnH, Theme::COLOR_BG_SURFACE);
        drawRectOutline(dx + 270, btnY, btnW, btnH, Theme::COLOR_BORDER, 1);
        drawText("[A] Закрыть", dx + 310, btnY + 12, Theme::COLOR_TEXT_PRIMARY, 14);
        return;
    }

    // Standard Confirmation Dialogs with auto word-wrap
    std::stringstream ss(m_dialogMessage);
    std::string rawLine;
    int msgY = dy + 70;
    while (std::getline(ss, rawLine, '\n')) {
        std::stringstream wordStream(rawLine);
        std::string word;
        std::string currentLine;
        while (wordStream >> word) {
            if (currentLine.empty()) {
                currentLine = word;
            } else if (currentLine.length() + 1 + word.length() <= 54) {
                currentLine += " " + word;
            } else {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14, dw - 70);
                msgY += 24;
                currentLine = word;
            }
        }
        if (!currentLine.empty()) {
            drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14, dw - 70);
            msgY += 24;
        }
    }

    bool isInstallWithIcon = (m_activeDialog == DialogType::ConfirmInstall && m_pendingActionVariant.hasIcon);
    bool isDeleteBoth = false;
    if (m_activeDialog == DialogType::ConfirmDelete) {
        for (const auto& g : m_installedGames) {
            if (g.titleId == m_pendingActionTitleId) {
                if (g.hasInstalledCover && g.hasInstalledIcon) {
                    isDeleteBoth = true;
                }
                break;
            }
        }
    }

    int btnY = dy + 190;
    int btnH = 42;

    if (isInstallWithIcon) {
        // Option 0: [A] Фон + Иконка
        bool f0 = (m_dialogFocus == 0);
        drawGlassCard(dx + 25, btnY, 155, btnH, f0, false);
        drawText("[A] Фон+Иконка", dx + 38, btnY + 12, f0 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 1: [X] Только иконка
        bool f1 = (m_dialogFocus == 1);
        drawGlassCard(dx + 190, btnY, 150, btnH, f1, false);
        drawText("[X] Иконка", dx + 215, btnY + 12, f1 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 2: [Y] Только фон
        bool f2 = (m_dialogFocus == 2);
        drawGlassCard(dx + 350, btnY, 150, btnH, f2, false);
        drawText("[Y] Только фон", dx + 370, btnY + 12, f2 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 3: [B] Отмена
        bool f3 = (m_dialogFocus == 3);
        drawGlassCard(dx + 510, btnY, 155, btnH, f3, false);
        drawText("[B] Отмена", dx + 555, btnY + 12, f3 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);
        return;
    }

    if (isDeleteBoth) {
        // Option 0: [A] Удалить всё
        bool f0 = (m_dialogFocus == 0);
        drawGlassCard(dx + 25, btnY, 155, btnH, f0, false);
        drawText("[A] Удалить всё", dx + 42, btnY + 12, f0 ? Theme::COLOR_DANGER : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 1: [X] Только иконку
        bool f1 = (m_dialogFocus == 1);
        drawGlassCard(dx + 190, btnY, 150, btnH, f1, false);
        drawText("[X] Иконку", dx + 220, btnY + 12, f1 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 2: [Y] Только видеофон
        bool f2 = (m_dialogFocus == 2);
        drawGlassCard(dx + 350, btnY, 150, btnH, f2, false);
        drawText("[Y] Видеофон", dx + 375, btnY + 12, f2 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 3: [B] Отмена
        bool f3 = (m_dialogFocus == 3);
        drawGlassCard(dx + 510, btnY, 155, btnH, f3, false);
        drawText("[B] Отмена", dx + 555, btnY + 12, f3 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);
        return;
    }

    int btnW = 180;
    // Confirm button
    bool focusConfirm = (m_dialogFocus == 0);
    drawGlassCard(dx + 130, btnY, btnW, btnH, focusConfirm, false);
    drawText("[A] Подтвердить", dx + 155, btnY + 12, focusConfirm ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14);

    // Cancel button
    bool focusCancel = (m_dialogFocus == 1);
    drawGlassCard(dx + 390, btnY, btnW, btnH, focusCancel, false);
    drawText("[B] Отмена", dx + 435, btnY + 12, focusCancel ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14);
}

void App::drawRect(int x, int y, int w, int h, Color color) {
#ifdef HAS_SDL2
    if (!m_renderer || w <= 0 || h <= 0) return;
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    SDL_Rect r{x, y, w, h};
    SDL_RenderFillRect(m_renderer, &r);
#else
    (void)x; (void)y; (void)w; (void)h; (void)color;
#endif
}

void App::drawRectOutline(int x, int y, int w, int h, Color color, int thickness) {
#ifdef HAS_SDL2
    if (!m_renderer || w <= 0 || h <= 0 || thickness <= 0) return;
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    for (int t = 0; t < thickness; ++t) {
        SDL_Rect r{x + t, y + t, w - 2 * t, h - 2 * t};
        SDL_RenderDrawRect(m_renderer, &r);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)color; (void)thickness;
#endif
}

void App::drawRoundedRect(int x, int y, int w, int h, int radius, Color color) {
#ifdef HAS_SDL2
    if (!m_renderer || w <= 0 || h <= 0) return;
    int r = std::min({radius, w / 2, h / 2});
    if (r <= 1) {
        drawRect(x, y, w, h, color);
        return;
    }
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    if (h > 2 * r) {
        SDL_Rect mid{x, y + r, w, h - 2 * r};
        SDL_RenderFillRect(m_renderer, &mid);
    }
    for (int dy = 0; dy < r; ++dy) {
        float yDist = static_cast<float>(r) - 0.5f - static_cast<float>(dy);
        int dx = static_cast<int>(std::round(std::sqrt(std::max(0.0f, static_cast<float>(r * r) - yDist * yDist))));
        int inset = std::max(0, r - dx);
        int x1 = x + inset;
        int x2 = x + w - 1 - inset;
        if (x2 >= x1) {
            SDL_RenderDrawLine(m_renderer, x1, y + dy, x2, y + dy);
            SDL_RenderDrawLine(m_renderer, x1, y + h - 1 - dy, x2, y + h - 1 - dy);
        }
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)radius; (void)color;
#endif
}

void App::drawRoundedOutline(int x, int y, int w, int h, int radius, Color topColor, Color bottomColor, int thickness) {
#ifdef HAS_SDL2
    if (!m_renderer || w <= 0 || h <= 0 || thickness <= 0) return;
    int outerR = std::min({radius, w / 2, h / 2});
    int innerR = std::max(0, outerR - thickness);
    for (int py = 0; py < h; ++py) {
        float factor = static_cast<float>(py) / static_cast<float>(std::max(1, h - 1));
        uint8_t cr = static_cast<uint8_t>(topColor.r + factor * (bottomColor.r - topColor.r));
        uint8_t cg = static_cast<uint8_t>(topColor.g + factor * (bottomColor.g - topColor.g));
        uint8_t cb = static_cast<uint8_t>(topColor.b + factor * (bottomColor.b - topColor.b));
        uint8_t ca = static_cast<uint8_t>(topColor.a + factor * (bottomColor.a - topColor.a));
        SDL_SetRenderDrawColor(m_renderer, cr, cg, cb, ca);

        int distEdge = std::min(py, h - 1 - py);
        int insetOut = 0;
        if (distEdge < outerR) {
            float dy = static_cast<float>(outerR) - 0.5f - static_cast<float>(distEdge);
            int dx = static_cast<int>(std::round(std::sqrt(std::max(0.0f, static_cast<float>(outerR * outerR) - dy * dy))));
            insetOut = std::max(0, outerR - dx);
        }

        if (distEdge < thickness) {
            int x1 = x + insetOut;
            int x2 = x + w - 1 - insetOut;
            if (x2 >= x1) {
                SDL_RenderDrawLine(m_renderer, x1, y + py, x2, y + py);
            }
        } else {
            int innerDist = distEdge - thickness;
            int insetIn = thickness;
            if (innerDist < innerR) {
                float dyIn = static_cast<float>(innerR) - 0.5f - static_cast<float>(innerDist);
                int dxIn = static_cast<int>(std::round(std::sqrt(std::max(0.0f, static_cast<float>(innerR * innerR) - dyIn * dyIn))));
                insetIn = thickness + std::max(0, innerR - dxIn);
            }
            int lx1 = x + insetOut;
            int lx2 = x + std::max(insetOut, insetIn - 1);
            int rx1 = x + w - 1 - std::max(insetOut, insetIn - 1);
            int rx2 = x + w - 1 - insetOut;
            if (lx2 >= lx1) SDL_RenderDrawLine(m_renderer, lx1, y + py, lx2, y + py);
            if (rx2 >= rx1) SDL_RenderDrawLine(m_renderer, rx1, y + py, rx2, y + py);
        }
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)radius; (void)topColor; (void)bottomColor; (void)thickness;
#endif
}

void App::drawNeonRoundedOutline(int x, int y, int w, int h, int radius, int thickness) {
    drawRoundedOutline(x, y, w, h, radius, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_PINK, thickness);
}

void App::drawNeonGradientOutline(int x, int y, int w, int h, int thickness) {
    drawNeonRoundedOutline(x, y, w, h, 0, thickness);
}

void App::drawLoadingSpinner(int cx, int cy, int r, Color col) {
#ifdef HAS_SDL2
    if (!m_renderer || r <= 2) return;
    // Draw 12 orbiting dots with smooth trailing alpha based on m_spinnerAngle
    for (int i = 0; i < 12; ++i) {
        float angle = m_spinnerAngle - static_cast<float>(i) * (6.2831853f / 12.0f);
        int px = cx + static_cast<int>(std::round(std::cos(angle) * static_cast<float>(r)));
        int py = cy + static_cast<int>(std::round(std::sin(angle) * static_cast<float>(r)));
        uint8_t alpha = static_cast<uint8_t>(std::max(30, 255 - i * 19));
        int dotR = (i < 3) ? 3 : 2;
        drawCircle(px, py, dotR, {col.r, col.g, col.b, alpha}, true);
    }
#else
    (void)cx; (void)cy; (void)r; (void)col;
#endif
}

void App::drawWifiIcon(int cx, int cy, Color col) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, col.r, col.g, col.b, col.a);
    // Wi-Fi dot at base
    drawCircle(cx, cy + 5, 2, col, true);
    // Lower arc (r = 5)
    for (int dx = -3; dx <= 3; ++dx) {
        int dy = static_cast<int>(std::round(std::sqrt(std::max(0.0f, 25.0f - dx * dx))));
        SDL_RenderDrawPoint(m_renderer, cx + dx, cy + 5 - dy);
        SDL_RenderDrawPoint(m_renderer, cx + dx, cy + 4 - dy);
    }
    // Upper arc (r = 9)
    for (int dx = -6; dx <= 6; ++dx) {
        int dy = static_cast<int>(std::round(std::sqrt(std::max(0.0f, 81.0f - dx * dx))));
        SDL_RenderDrawPoint(m_renderer, cx + dx, cy + 5 - dy);
        SDL_RenderDrawPoint(m_renderer, cx + dx, cy + 4 - dy);
    }
#else
    (void)cx; (void)cy; (void)col;
#endif
}

void App::drawSearchIcon(int cx, int cy, Color col) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    drawCircle(cx - 2, cy - 2, 6, col, false);
    drawCircle(cx - 2, cy - 2, 5, col, false);
    SDL_SetRenderDrawColor(m_renderer, col.r, col.g, col.b, col.a);
    SDL_RenderDrawLine(m_renderer, cx + 2, cy + 2, cx + 7, cy + 7);
    SDL_RenderDrawLine(m_renderer, cx + 3, cy + 2, cx + 8, cy + 7);
#else
    (void)cx; (void)cy; (void)col;
#endif
}

void App::drawGlassCard(int x, int y, int w, int h, bool isFocused, bool isElevated) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color bg = isElevated ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_SURFACE;
    drawRoundedRect(x, y, w, h, 16, bg);

    if (isFocused) {
        drawRoundedRect(x, y, w, h, 16, Theme::COLOR_FOCUS_FILL);
        drawNeonRoundedOutline(x, y, w, h, 16, 2);
    } else {
        drawRoundedOutline(x, y, w, h, 16, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)isFocused; (void)isElevated;
#endif
}

void App::drawCapsuleProgressBar(int x, int y, int w, int h, double percent) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    int r = h / 2;
    drawRoundedRect(x, y, w, h, r, {0x1C, 0x22, 0x30, 0xFF});
    drawRoundedOutline(x, y, w, h, r, {0x2D, 0x37, 0x48, 0xFF}, {0x2D, 0x37, 0x48, 0xFF}, 1);

    int fillW = static_cast<int>(w * std::clamp(percent / 100.0, 0.0, 1.0));
    if (fillW > 0) {
        drawRoundedRect(x, y, fillW, h, r, Theme::COLOR_FOCUS_CYAN);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)percent;
#endif
}

TTF_Font* App::getFont(int sizePx) {
#ifdef HAS_SDL2
    auto it = m_fonts.find(sizePx);
    if (it != m_fonts.end()) {
        return it->second;
    }

#ifdef __SWITCH__
    if (m_fontMemBuffer && m_fontMemSize > 0) {
        SDL_RWops* rw = SDL_RWFromMem(const_cast<void*>(m_fontMemBuffer), static_cast<int>(m_fontMemSize));
        if (rw) {
            TTF_Font* font = TTF_OpenFontRW(rw, 1, sizePx);
            if (font) {
                m_fonts[sizePx] = font;
                return font;
            }
        }
    }
#endif

    const char* fontCandidates[] = {
        "romfs:/font.ttf",
        "sdmc:/switch/H3H-Backgrounds/font.ttf",
        "sdmc:/switch/font.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    };

    for (const char* path : fontCandidates) {
        TTF_Font* font = TTF_OpenFont(path, sizePx);
        if (font) {
            m_fonts[sizePx] = font;
            return font;
        }
    }
#endif
    (void)sizePx;
    return nullptr;
}

int App::measureTextWidth(const std::string& text, int sizePx) {
    if (text.empty()) return 0;
#ifdef HAS_SDL2
    std::string wKey = std::to_string(sizePx) + ":" + text;
    auto wit = m_textWidthCache.find(wKey);
    if (wit != m_textWidthCache.end()) {
        return wit->second;
    }
    TTF_Font* font = getFont(sizePx);
    if (font) {
        int w = 0, h = 0;
        if (TTF_SizeUTF8(font, text.c_str(), &w, &h) == 0) {
            if (m_textWidthCache.size() > 1200) {
                m_textWidthCache.clear();
            }
            m_textWidthCache[wKey] = w;
            return w;
        }
    }
#endif
    int codepoints = 0;
    for (unsigned char c : text) {
        if ((c & 0xC0) != 0x80) codepoints++;
    }
    return codepoints * (sizePx / 2 + 1);
}

void App::drawTextCentered(const std::string& text, int cx, int y, Color color, int sizePx, int maxWidth) {
    if (text.empty()) return;
    int w = measureTextWidth(text, sizePx);
    if (maxWidth > 0 && w > maxWidth) w = maxWidth;
    drawText(text, cx - w / 2, y, color, sizePx, maxWidth);
}

void App::drawTextRight(const std::string& text, int rightX, int y, Color color, int sizePx, int maxWidth) {
    if (text.empty()) return;
    int w = measureTextWidth(text, sizePx);
    if (maxWidth > 0 && w > maxWidth) w = maxWidth;
    drawText(text, rightX - w, y, color, sizePx, maxWidth);
}

void App::drawText(const std::string& text, int x, int y, Color color, int sizePx, int maxWidth) {
#ifdef HAS_SDL2
    if (text.empty() || !m_renderer) return;

    uint32_t rgba = (static_cast<uint32_t>(color.r) << 24) |
                    (static_cast<uint32_t>(color.g) << 16) |
                    (static_cast<uint32_t>(color.b) << 8)  |
                    (static_cast<uint32_t>(color.a));
    TextCacheKey key{text, sizePx, rgba};
    auto it = m_textCache.find(key);
    if (it != m_textCache.end()) {
        it->second.lastUsedFrame = m_renderFrameIndex;
        int drawW = it->second.width;
        if (maxWidth > 0 && drawW > maxWidth) {
            drawW = maxWidth;
        }
        SDL_Rect srcRect = {0, 0, drawW, it->second.height};
        SDL_Rect dstRect = {x, y, drawW, it->second.height};
        SDL_RenderCopy(m_renderer, it->second.texture, &srcRect, &dstRect);
        return;
    }

    TTF_Font* font = getFont(sizePx);
    if (font) {
        SDL_Color sdlColor = {color.r, color.g, color.b, color.a};
        SDL_Surface* surf = TTF_RenderUTF8_Blended(font, text.c_str(), sdlColor);
        if (surf) {
            SDL_Texture* tex = SDL_CreateTextureFromSurface(m_renderer, surf);
            if (tex) {
                int w = surf->w;
                int h = surf->h;
                m_textCache[key] = TextCacheEntry{tex, w, h, m_renderFrameIndex};

                // Periodically prune stale entries if cache exceeds capacity
                if (m_textCache.size() > 600) {
                    for (auto cit = m_textCache.begin(); cit != m_textCache.end(); ) {
                        if (m_renderFrameIndex > cit->second.lastUsedFrame + 180) {
                            if (cit->second.texture) {
                                SDL_DestroyTexture(cit->second.texture);
                            }
                            cit = m_textCache.erase(cit);
                        } else {
                            ++cit;
                        }
                    }
                }

                int drawW = w;
                if (maxWidth > 0 && drawW > maxWidth) {
                    drawW = maxWidth;
                }
                SDL_Rect srcRect = {0, 0, drawW, h};
                SDL_Rect dstRect = {x, y, drawW, h};
                SDL_RenderCopy(m_renderer, tex, &srcRect, &dstRect);
            }
            SDL_FreeSurface(surf);
            return;
        }
    }

    drawBitmapTextFallback(text, x, y, color);
#else
    (void)text; (void)x; (void)y; (void)color; (void)sizePx; (void)maxWidth;
#endif
}

void App::drawBitmapTextFallback(const std::string& text, int x, int y, Color color) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    int curX = x;
    for (char c : text) {
        if (c >= 32 && c <= 126) {
            SDL_Rect r{curX, y + 2, 7, 12};
            SDL_RenderDrawRect(m_renderer, &r);
            curX += 9;
        } else {
            curX += 5;
        }
    }
#else
    (void)text; (void)x; (void)y; (void)color;
#endif
}

void App::run() {
    const uint32_t targetFrameTimeMs = 16; // 60 FPS pacing budget

    while (m_running) {
#ifdef HAS_SDL2
        uint32_t frameStart = SDL_GetTicks();
#endif
        handleInput();
        update();
        render();
#ifdef HAS_SDL2
        uint32_t frameElapsed = SDL_GetTicks() - frameStart;
        if (frameElapsed < targetFrameTimeMs) {
            SDL_Delay(targetFrameTimeMs - frameElapsed);
        } else {
            SDL_Delay(1);
        }
#else
        break; // In non-SDL test mode, run one cycle
#endif
    }
}




void App::renderFullscreenPreview() {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    SDL_SetRenderDrawColor(m_renderer, 0, 0, 0, 255);
    SDL_RenderClear(m_renderer);

    SDL_Rect fullScreenRect = {0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT};
    SDL_Rect targetRect = fullScreenRect;
    if (m_previewIsIconSquare) {
        // Switch Horizon OS Home Screen Game Tile Mockup backdrop
        drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x07, 0x0B, 0x13, 0xFF});

        // Subtle Switch Home top status bar & bottom applet dock circles
        drawText(tr("Макет главного экрана Switch (Horizon OS 256x256 Icon)", "Switch Home Screen Preview (Horizon OS 256x256 Icon)"),
                 440, 24, Theme::COLOR_TEXT_MUTED, 13);

        // Ghosted adjacent Home Menu game tiles on left & right to show 1:1 icon in real context
        drawRoundedRect(130, 165, 270, 270, 14, {0x11, 0x17, 0x24, 0xAA});
        drawRoundedOutline(130, 165, 270, 270, 14, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        drawTextCentered("GAME TILE", 265, 290, {0x38, 0x46, 0x5E, 0xFF}, 14);

        drawRoundedRect(880, 165, 270, 270, 14, {0x11, 0x17, 0x24, 0xAA});
        drawRoundedOutline(880, 165, 270, 270, 14, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        drawTextCentered("GAME TILE", 1015, 290, {0x38, 0x46, 0x5E, 0xFF}, 14);

        // Floating game title above focused Switch Home tile
        drawTextCentered(m_previewGameName, 640, 82, Theme::COLOR_FOCUS_CYAN, 20, 760);

        // Central focused 1:1 Game Icon Tile (360x360 display frame for 256x256 icon)
        targetRect = {460, 125, 360, 360};
        uint8_t pulseC = static_cast<uint8_t>(std::clamp(180.0f + 75.0f * m_glowPulse, 120.0f, 255.0f));
        drawGlassCard(448, 113, 384, 384, true, true);
        drawRoundedOutline(446, 111, 388, 388, 18, {0x00, pulseC, 0xFF, 0xFF}, Theme::COLOR_FOCUS_PINK, 3);

        // Switch Home applet row indicators below the icon row
        for (int aIdx = 0; aIdx < 6; ++aIdx) {
            int acx = 465 + aIdx * 70;
            drawCircle(acx, 535, 20, {0x16, 0x1F, 0x30, 0xFF}, true);
            drawCircle(acx, 535, 20, Theme::COLOR_BORDER, false);
        }
    }

    // Resolve instant fallback texture from row/collection/dock cache if m_previewTexture is still loading
    SDL_Texture* activePreviewTex = m_previewTexture;
    if (!activePreviewTex && !m_previewVariants.empty()) {
        int curV = std::clamp(m_previewVariantIndex, 0, static_cast<int>(m_previewVariants.size()) - 1);
        activePreviewTex = findCachedThumbTexture(m_previewTitleId, m_previewVariants[curV], m_previewIsIconSquare);
    }

    // 1. Draw Live Motion Video or Instant Cached Thumbnail or Rich 4IFIR Cyber-Glass Buffering Card (NEVER a black screen!)
    if (m_videoPlayer.isPlaying()) {
        m_videoPlayer.render(m_renderer, &targetRect);

        // Status badge: LIVE VIDEO
        drawRect(30, 20, 340, 32, {0x0F, 0x17, 0x2A, 0xDD});
        drawRectOutline(30, 20, 340, 32, Theme::COLOR_SUCCESS, 1);
        std::string badgeTxt = m_previewIsIconSquare
            ? (tr("ЖИВАЯ ВИДЕОИКОНКА (256x256 • #", "LIVE VIDEO ICON (256x256 • #") + std::to_string(m_videoPlayer.getDecodedFrames()) + ")")
            : (tr("ЖИВОЙ ВИДЕОФОН (30 FPS • #", "LIVE VIDEO COVER (30 FPS • #") + std::to_string(m_videoPlayer.getDecodedFrames()) + ")");
        drawText(badgeTxt, 45, 28, Theme::COLOR_SUCCESS, 13);
    } else if (activePreviewTex) {
        SDL_RenderCopy(m_renderer, activePreviewTex, nullptr, &targetRect);

        if (m_videoDownloading) {
            drawRect(30, 20, 360, 34, {0x0F, 0x17, 0x2A, 0xE6});
            drawRectOutline(30, 20, 360, 34, Theme::COLOR_FOCUS_CYAN, 1);
            drawLoadingSpinner(52, 37, 8, Theme::COLOR_FOCUS_CYAN);
            uint64_t dlBytes = m_previewDownloadBytes.load();
            uint64_t totBytes = m_previewDownloadTotal.load();
            char bufProg[96];
            if (totBytes > 0 && dlBytes > 0) {
                int pct = static_cast<int>(std::min<uint64_t>(99, (dlBytes * 100) / totBytes));
                if (m_previewIsIconSquare) {
                    std::snprintf(bufProg, sizeof(bufProg), "%s: %d%% (%llu KB)",
                                  tr("Буферизация видео", "Buffering video"), pct,
                                  static_cast<unsigned long long>(dlBytes / 1024));
                } else {
                    std::snprintf(bufProg, sizeof(bufProg), "%s: %d%% (%.1f MB)",
                                  tr("Буферизация видео", "Buffering video"), pct,
                                  static_cast<double>(dlBytes) / (1024.0 * 1024.0));
                }
            } else {
                std::snprintf(bufProg, sizeof(bufProg), "%s...", tr("Буферизация видео", "Buffering video"));
            }
            drawText(bufProg, 70, 29, Theme::COLOR_FOCUS_CYAN, 13);
        } else {
            drawRect(30, 20, 290, 32, {0x0F, 0x17, 0x2A, 0xDD});
            drawRectOutline(30, 20, 290, 32, Theme::COLOR_BORDER, 1);
            std::string badgeTxt = m_previewIsIconSquare
                ? tr("Видеоиконка (Статичный кадр)", "Video Icon (Static Frame)")
                : tr("Предпросмотр (Статичный кадр)", "Preview (Static Frame)");
            drawText(badgeTxt, 45, 28, Theme::COLOR_TEXT_MUTED, 13);
        }
    } else {
        // Rich 4IFIR Cyber-Glass Preview Card while first packet streams (eliminates black screen!)
        if (!m_previewIsIconSquare) {
            drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, Theme::COLOR_BG_BASE);
            drawGlassCard(220, 120, 840, 390, true, true);
            drawNeonGradientOutline(220, 120, 840, 390, 2);
            drawTextCentered(m_previewGameName, 640, 155, Theme::COLOR_TEXT_PRIMARY, 22, 780);
        } else {
            drawRoundedRect(targetRect.x + 8, targetRect.y + 8, targetRect.w - 16, targetRect.h - 16, 14, {0x11, 0x1A, 0x2B, 0xFF});
        }

        if (m_previewLoading || m_videoDownloading) {
            uint64_t dlBytes = m_previewDownloadBytes.load();
            uint64_t totBytes = m_previewDownloadTotal.load();
            double pct = (totBytes > 0 && dlBytes > 0)
                ? std::min(99.0, (static_cast<double>(dlBytes) / static_cast<double>(totBytes)) * 100.0)
                : 18.0;

            drawLoadingSpinner(640, m_previewIsIconSquare ? 245 : 250, 22, Theme::COLOR_FOCUS_CYAN);
            std::string loadingTxt = m_previewIsIconSquare
                ? tr("Загрузка видеоиконки (256x256)...", "Loading video icon (256x256)...")
                : tr("Загрузка видеофона (1280x720 HD)...", "Loading video cover (1280x720 HD)...");
            drawTextCentered(loadingTxt, 640, m_previewIsIconSquare ? 295 : 300, Theme::COLOR_FOCUS_CYAN, 17);

            int barW = m_previewIsIconSquare ? 260 : 460;
            drawCapsuleProgressBar(640 - barW / 2, m_previewIsIconSquare ? 335 : 345, barW, 14, pct);

            char subProg[128];
            if (dlBytes > 0) {
                std::snprintf(subProg, sizeof(subProg), "%s: %llu KB",
                              tr("Получено данных", "Received"),
                              static_cast<unsigned long long>(dlBytes / 1024));
            } else {
                std::snprintf(subProg, sizeof(subProg), "%s",
                              tr("Прямое потоковое подключение 4IFIR...", "Direct 4IFIR stream connection..."));
            }
            drawTextCentered(subProg, 640, m_previewIsIconSquare ? 362 : 375, Theme::COLOR_TEXT_MUTED, 13);
        } else {
            std::string offlineTxt = m_previewIsIconSquare
                ? tr("Видеоиконка недоступна офлайн", "Video icon unavailable offline")
                : tr("Видеофон недоступен офлайн (нет подключения)", "Video cover unavailable offline");
            drawTextCentered(offlineTxt, 640, m_previewIsIconSquare ? 290 : 320, Theme::COLOR_WARNING, 18);
            std::string hintTxt = m_previewIsIconSquare
                ? tr("Нажмите [A], чтобы установить видеоиконку", "Press [A] to install video icon")
                : tr("Нажмите [A], чтобы установить видеофон", "Press [A] to install video cover");
            drawTextCentered(hintTxt, 640, m_previewIsIconSquare ? 325 : 356, Theme::COLOR_TEXT_MUTED, 13);
        }
    }

    // 1.5. Variant C: Interactive Nintendo Switch Horizon OS Home Screen Simulator Overlay ([ZR] Toggle)
    if (!m_previewIsIconSquare && m_previewShowSwitchHud) {
        // Top-right user avatar & status bar mockup
        drawRoundedRect(980, 18, 260, 36, 18, {0x0B, 0x11, 0x1E, 0xCC});
        drawRoundedOutline(980, 18, 260, 36, 18, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered(tr("МАКЕТ МЕНЮ SWITCH [ZR]", "SWITCH HOME OVERLAY [ZR]"), 1110, 28, Theme::COLOR_FOCUS_CYAN, 11);

        // Floating title of focused game above tile #1
        drawRoundedRect(102, 110, 460, 34, 8, {0x09, 0x10, 0x1C, 0xD8});
        drawText(m_previewGameName, 118, 117, Theme::COLOR_FOCUS_CYAN, 16, 430);

        // 4 Translucent Switch Home Game Tiles across the center of the screen
        int tileY = 154;
        int tileSize = 236;
        int tileGap = 24;
        int startTileX = 110;
        for (int ti = 0; ti < 4; ++ti) {
            int tx = startTileX + ti * (tileSize + tileGap);
            bool isFocusedTile = (ti == 0);
            drawRoundedRect(tx, tileY, tileSize, tileSize, 14, isFocusedTile ? Color{0x10, 0x1A, 0x2C, 0x7A} : Color{0x0A, 0x10, 0x1C, 0x8C});
            if (isFocusedTile) {
                uint8_t pCol = static_cast<uint8_t>(std::clamp(180.0f + 75.0f * m_glowPulse, 130.0f, 255.0f));
                drawRoundedOutline(tx - 2, tileY - 2, tileSize + 4, tileSize + 4, 15, {0x00, pCol, 0xFF, 0xFF}, Theme::COLOR_FOCUS_PINK, 3);
                drawTextCentered(tr("АКТИВНАЯ ИГРА", "ACTIVE GAME"), tx + tileSize / 2, tileY + tileSize / 2 - 8, {0xFF, 0xFF, 0xFF, 0xDD}, 13);
            } else {
                drawRoundedOutline(tx, tileY, tileSize, tileSize, 14, {0x45, 0x56, 0x72, 0xAA}, {0x45, 0x56, 0x72, 0xAA}, 1);
                drawTextCentered("SWITCH GAME", tx + tileSize / 2, tileY + tileSize / 2 - 8, {0x88, 0x99, 0xB5, 0xAA}, 12);
            }
        }

        // Horizon OS Applet Dock Row below the game tiles
        for (int aIdx = 0; aIdx < 7; ++aIdx) {
            int acx = 400 + aIdx * 80;
            drawCircle(acx, 456, 24, {0x0D, 0x15, 0x24, 0xCC}, true);
            drawCircle(acx, 456, 24, Theme::COLOR_FOCUS_CYAN, false);
        }
    }

    // 2. Bottom 4IFIR Cyber-Glass HUD overlay
    int hudX = 40;
    int hudY = 585;
    int hudW = 1200;
    int hudH = 105;
    // Solid dark obsidian to prevent underlying video text/artifacts from bleeding through
    drawRect(hudX, hudY, hudW, hudH, {0x0D, 0x11, 0x1A, 0xF6});
    drawNeonGradientOutline(hudX, hudY, hudW, hudH, 2);

    if (!m_previewVariants.empty()) {
        int totalV = static_cast<int>(m_previewVariants.size());
        int curV = std::clamp(m_previewVariantIndex, 0, totalV - 1);
        const auto& v = m_previewVariants[curV];

        // Game Name (Left top)
        drawText(m_previewGameName, hudX + 25, hudY + 12, Theme::COLOR_TEXT_PRIMARY, 19, 540);

        // Variant Name & Style (Left middle)
        std::string varTitle = std::to_string(curV + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
        drawText(varTitle, hudX + 25, hudY + 38, Theme::COLOR_FOCUS_CYAN, 16, 540);

        // Tech specs + Audio pill (Left bottom)
        double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
        char mbBuf[16];
        if (mb >= 0.1) snprintf(mbBuf, sizeof(mbBuf), "%.1f MB", mb);
        else snprintf(mbBuf, sizeof(mbBuf), "~3.5 MB");

        std::string resStr = m_previewIsIconSquare ? tr("256x256 (Иконка)", "256x256 (Icon)") : "1280x720 @30fps";
        std::string specs = resStr + "  |  " + std::string(mbBuf) +
                            "  |  " + tr("Вар. ", "Var ") + std::to_string(curV + 1) + "/" + std::to_string(totalV);
        drawText(specs, hudX + 25, hudY + 71, Theme::COLOR_TEXT_MUTED, 13, 255);

        // Sequential dynamic badges starting at hudX + 285
        int badgeX = hudX + 285;

        if (!m_previewIsIconSquare) {
            if (v.hasAudio) {
                drawRect(badgeX, hudY + 66, 65, 24, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(badgeX, hudY + 66, 65, 24, Theme::COLOR_SUCCESS, 1);
                drawText(tr("ЗВУК", "AUDIO"), badgeX + 14, hudY + 71, Theme::COLOR_SUCCESS, 11);
                badgeX += 73;
            } else {
                drawRect(badgeX, hudY + 66, 80, 24, {0x28, 0x33, 0x47, 0x44});
                drawRectOutline(badgeX, hudY + 66, 80, 24, Theme::COLOR_BORDER, 1);
                drawText(tr("БЕЗ ЗВУКА", "NO AUDIO"), badgeX + 8, hudY + 71, Theme::COLOR_TEXT_MUTED, 11);
                badgeX += 88;
            }

            if (v.hasIcon) {
                drawRect(badgeX, hudY + 66, 80, 24, Theme::COLOR_ICON_BADGE_FILL);
                drawRectOutline(badgeX, hudY + 66, 80, 24, Theme::COLOR_ICON_BADGE, 1);
                drawText(tr("ИКОНКА", "ICON"), badgeX + 13, hudY + 71, Theme::COLOR_ICON_BADGE, 11);
                badgeX += 88;
            }
        } else {
            drawRect(badgeX, hudY + 66, 120, 24, Theme::COLOR_ICON_BADGE_FILL);
            drawRectOutline(badgeX, hudY + 66, 120, 24, Theme::COLOR_ICON_BADGE, 1);
            drawText(tr("ВИДЕОИКОНКА", "VIDEO ICON"), badgeX + 10, hudY + 71, Theme::COLOR_ICON_BADGE, 11);
            badgeX += 128;
        }

        // Active variant identification: exactly matches the installed variant
        bool isActiveVariant = false;
        if (m_previewIsIconSquare) {
            isActiveVariant = m_previewHasInstalledCover;
        } else {
            isActiveVariant = (m_previewHasInstalledCover && v.id == m_previewInstalledVariantId);
        }

        if (isActiveVariant) {
            drawRect(badgeX, hudY + 66, 150, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(badgeX, hudY + 66, 150, 24, Theme::COLOR_SUCCESS, 1);
            drawText(tr("АКТИВЕН НА SWITCH", "ACTIVE ON SWITCH"), badgeX + 10, hudY + 71, Theme::COLOR_SUCCESS, 11);
        }

        // Right side buttons
        if (m_previewTitleId == "0000000000000000") {
            drawRect(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(hudX + 900, hudY + 14, 270, 38, 2);
            drawText(tr("[A/Y] Выбрать игру для фона", "[A/Y] Pick Game for Cover"), hudX + 915, hudY + 24, Theme::COLOR_FOCUS_CYAN, 13);
        } else if (isActiveVariant) {
            drawRect(hudX + 900, hudY + 14, 270, 38, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_SUCCESS, 1);
            std::string aTxt = m_previewIsIconSquare ? tr("[A] Переустановить иконку", "[A] Reinstall Icon") : tr("[A] Переустановить", "[A] Reinstall");
            drawText(aTxt, hudX + (m_previewIsIconSquare ? 920 : 950), hudY + 24, Theme::COLOR_SUCCESS, 14);
        } else if (m_previewIsGameInstalled) {
            drawRect(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_CYAN, 1);
            std::string aTxt = m_previewIsIconSquare ? tr("[A] Установить видеоиконку", "[A] Install Video Icon") : tr("[A] Установить видеофон", "[A] Install Video Cover");
            drawText(aTxt, hudX + (m_previewIsIconSquare ? 915 : 930), hudY + 24, Theme::COLOR_FOCUS_CYAN, 14);
        } else {
            drawRect(hudX + 900, hudY + 14, 270, 38, {0x16, 0x20, 0x32, 0xAA});
            drawRectOutline(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_BORDER, 1);
            drawText(tr("[A] Скачать заранее", "[A] Pre-Download"), hudX + 942, hudY + 24, Theme::COLOR_TEXT_MUTED, 14);
        }

        // [ZR] Switch Home Overlay Toggle Button (Variant C)
        if (!m_previewIsIconSquare) {
            drawRoundedRect(hudX + 555, hudY + 14, 160, 38, 8, m_previewShowSwitchHud ? Theme::COLOR_FOCUS_FILL : Color{0x16, 0x20, 0x32, 0xAA});
            drawRoundedOutline(hudX + 555, hudY + 14, 160, 38, 8, m_previewShowSwitchHud ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, m_previewShowSwitchHud ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, 1);
            drawTextCentered(m_previewShowSwitchHud ? tr("[ZR] Макет: ВКЛ", "[ZR] HUD: ON") : tr("[ZR] Макет Switch", "[ZR] Switch HUD"),
                             hudX + 555 + 80, hudY + 25, m_previewShowSwitchHud ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 12);
        }

        // [R] Switch between 16:9 Cover and 256x256 Video Icon Preview
        const GameCatalogEntry* catMatchHud = m_catalogManager.findByTitleId(m_previewTitleId);
        bool canSwitchToIcon = (!m_previewIsIconSquare && ((v.hasIcon && !v.iconUrl.empty()) || (catMatchHud && !getUniqueIconVariants(*catMatchHud).empty())));
        bool canSwitchToCover = (m_previewIsIconSquare && catMatchHud && !getCoverVariants(*catMatchHud).empty());
        if (canSwitchToIcon) {
            drawRoundedRect(hudX + 725, hudY + 14, 165, 38, 8, Color{0xEC, 0x48, 0x99, 0x2E});
            drawRoundedOutline(hudX + 725, hudY + 14, 165, 38, 8, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
            drawTextCentered(tr("[R] Иконка 256x256", "[R] Icon 256x256"), hudX + 725 + 82, hudY + 25, Theme::COLOR_FOCUS_PINK, 12);
        } else if (canSwitchToCover) {
            drawRoundedRect(hudX + 725, hudY + 14, 165, 38, 8, Theme::COLOR_FOCUS_FILL);
            drawRoundedOutline(hudX + 725, hudY + 14, 165, 38, 8, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
            drawTextCentered(tr("[R] Видеофон 16:9", "[R] Cover 16:9"), hudX + 725 + 82, hudY + 25, Theme::COLOR_FOCUS_CYAN, 12);
        } else if (isVariantFavorite(m_previewTitleId, v.id)) {
            drawRect(hudX + 725, hudY + 14, 165, 38, {0xFF, 0xD7, 0x00, 0x33});
            drawRectOutline(hudX + 725, hudY + 14, 165, 38, {0xFF, 0xD7, 0x00, 0xFF}, 1);
            drawTextCentered(tr("★ ИЗБРАННОЕ", "★ FAVORITE"), hudX + 725 + 82, hudY + 25, {0xFF, 0xD7, 0x00, 0xFF}, 12);
        }

        if (!m_previewIsIconSquare) {
            drawText(tr("[L] Избранное", "[L] Favorite"), hudX + 670, hudY + 71, Theme::COLOR_TEXT_MUTED, 13);
            drawText(tr("[Y] На другую игру", "[Y] Other Game"), hudX + 810, hudY + 71, Theme::COLOR_FOCUS_CYAN, 13);
        }
        if (totalV > 1) {
            drawText(tr("[◄/►] Вариант", "[◄/►] Variant"), hudX + 975, hudY + 71, Theme::COLOR_FOCUS_PINK, 13);
        }
        drawText(tr("[B] Назад", "[B] Back"), hudX + 1105, hudY + 71, Theme::COLOR_TEXT_MUTED, 13);
    }
#endif
}

void App::openFullscreenPreviewForGame(const InstalledTitle& g, int variantIndex) {
#ifdef HAS_SDL2
    if (!g.hasCatalogMatch || g.catalogEntry.variants.empty()) return;

    m_previewTitleId = g.titleId;
    m_previewGameName = g.name;
    m_previewVariants = getCoverVariants(g.catalogEntry);
    m_previewVariantIndex = std::clamp(variantIndex, 0, static_cast<int>(m_previewVariants.size()) - 1);
    m_previewIsGameInstalled = true;
    m_previewHasInstalledCover = g.hasInstalledCover;
    m_previewIsIconSquare = false;
    m_previewShowSwitchHud = false;
    m_previewInstalledVariantId = g.installedVariantId;
    m_previewInstalledCoverSizeBytes = g.installedCoverSizeBytes;
    m_previewInstalledCoverPath = g.installedCoverPath;

    m_previewOpenedAt = SDL_GetTicks();
    m_isFullscreenPreview = true;
    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#endif
}

void App::openFullscreenPreviewForCatalogGame(const GameCatalogEntry& entry, int variantIndex) {
#ifdef HAS_SDL2
    if (entry.variants.empty()) return;

    m_previewTitleId = entry.titleId;
    m_previewGameName = entry.title;
    m_previewVariants = getCoverVariants(entry);
    m_previewVariantIndex = std::clamp(variantIndex, 0, static_cast<int>(m_previewVariants.size()) - 1);

    m_previewIsGameInstalled = false;
    m_previewHasInstalledCover = false;
    m_previewIsIconSquare = false;
    m_previewShowSwitchHud = false;
    m_previewInstalledVariantId.clear();
    m_previewInstalledCoverSizeBytes = 0;
    m_previewInstalledCoverPath.clear();

    for (const auto& g : m_installedGames) {
        if (g.titleId == entry.titleId) {
            m_previewIsGameInstalled = true;
            m_previewHasInstalledCover = g.hasInstalledCover;
            m_previewInstalledVariantId = g.installedVariantId;
            m_previewInstalledCoverSizeBytes = g.installedCoverSizeBytes;
            m_previewInstalledCoverPath = g.installedCoverPath;
            break;
        }
    }

    m_previewOpenedAt = SDL_GetTicks();
    m_isFullscreenPreview = true;
    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#endif
}

void App::loadPreviewTexture(const std::string& titleId, const Variant& variant) {
#ifdef HAS_SDL2
    m_videoPlayer.close();
    m_previewFadeAlpha = 255.0f;

    std::string cacheKey = m_previewIsIconSquare ? ("icon_" + titleId + "_" + variant.id) : (titleId + "_" + variant.id);
    m_previewCurrentVariantId = cacheKey;

    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string thumbFile = thumbDir + "/" + cacheKey + ".jpg";
    std::string vidFile = thumbDir + "/" + cacheKey + ".mp4";

    // 1. Check if THIS SPECIFIC VARIANT is the active installed cover/icon on console
    bool isThisVariantInstalled = false;
    if (m_previewIsIconSquare) {
        isThisVariantInstalled = (m_previewHasInstalledCover &&
                                  !m_previewInstalledCoverPath.empty() &&
                                  std::filesystem::exists(m_previewInstalledCoverPath, ec));
    } else {
        isThisVariantInstalled = (m_previewHasInstalledCover &&
                                  variant.id == m_previewInstalledVariantId &&
                                  !m_previewInstalledCoverPath.empty() &&
                                  std::filesystem::exists(m_previewInstalledCoverPath, ec));
    }

    if (isThisVariantInstalled) {
        // Play directly from SD card with 0 network delay!
        m_videoPlayer.open(m_previewInstalledCoverPath, m_renderer);
    } else if (std::filesystem::exists(vidFile, ec)) {
        uint64_t cachedSz = std::filesystem::file_size(vidFile, ec);
        uint64_t minSz = m_previewIsIconSquare ? 4096 : 50000;
        if (cachedSz >= minSz) {
            if (!m_videoPlayer.open(vidFile, m_renderer)) {
                std::filesystem::remove(vidFile, ec);
            }
        } else {
            std::filesystem::remove(vidFile, ec);
        }
    }

    // 2. Load static image if exists on disk (or check if already in m_rowThumbTextures)
    bool hasCachedThumb = (findCachedThumbTexture(titleId, variant, m_previewIsIconSquare) != nullptr);
    if (std::filesystem::exists(thumbFile, ec) && validateImageFile(thumbFile)) {
        SDL_Texture* newTex = loadTextureFromFile(m_renderer, thumbFile);
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
            hasCachedThumb = true;
        } else {
            std::filesystem::remove(thumbFile, ec);
        }
    } else if (std::filesystem::exists(thumbFile, ec)) {
        std::filesystem::remove(thumbFile, ec);
    }

    // 3. If video is already playing, no need to download
    if (m_videoPlayer.isPlaying()) {
        m_previewLoading = false;
        m_videoDownloading = false;
        m_previewTransferQueued = false;
        return;
    }

    // 4. Queue non-blocking background download (0 ms on main UI thread — never calls .join() here!)
    std::string videoUrl = m_previewIsIconSquare
        ? (!variant.iconUrl.empty() ? variant.iconUrl : variant.url)
        : variant.url;
    std::string thumbUrl = variant.previewUrl;
    if (thumbUrl.empty()) {
        std::string drvId = extractDriveIdFromUrl(!videoUrl.empty() ? videoUrl : variant.iconUrl);
        if (!drvId.empty()) {
            thumbUrl = "https://drive.google.com/thumbnail?id=" + drvId + (m_previewIsIconSquare ? "&sz=w320" : "&sz=w640");
        }
    }

    m_cancelPreview.store(true);
    m_previewDownloadBytes.store(0);
    m_previewDownloadTotal.store(m_previewIsIconSquare
        ? (variant.iconSizeBytes > 0 ? variant.iconSizeBytes : (variant.sizeBytes > 0 ? variant.sizeBytes : 180 * 1024))
        : (variant.sizeBytes > 0 ? variant.sizeBytes : 3500 * 1024));

    m_previewLoading = !hasCachedThumb;
    m_videoDownloading = !videoUrl.empty();

    m_queuedPreviewThumbUrl = thumbUrl;
    m_queuedPreviewVideoUrl = videoUrl;
    m_queuedPreviewThumbFile = thumbFile;
    m_queuedPreviewVidFile = vidFile;
    m_queuedPreviewKey = cacheKey;
    m_queuedPreviewIsIcon = m_previewIsIconSquare;
    m_previewTransferQueued = true;

    // Immediately kick off worker if not busy
    updateAsyncPreviewWorkers();
#endif
}

void App::closeFullscreenPreview() {
#ifdef HAS_SDL2
    m_isFullscreenPreview = false;
    m_previewTransferQueued = false;
    m_videoPlayer.close();
    m_cancelPreview.store(true);
    m_previewLoading = false;
    m_videoDownloading = false;
    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }
    m_previewCurrentVariantId.clear();
    m_previewTitleId.clear();
    m_previewGameName.clear();
    m_previewVariants.clear();
    m_previewVariantIndex = 0;

    // Restore inline live preview if returning to Collection Browser, VideoIcons Dock, or Catalog Split-Studio
    if (m_isCollectionBrowserOpen) {
        m_collectionPreviewDirty = true;
        m_lastCollectionMoveTime = SDL_GetTicks() - 100;
    } else if (m_activeTab == Tab::VideoIcons) {
        m_videoIconDockDirty = true;
        m_videoIconDockCurrentKey.clear();
        m_lastVideoIconMoveTime = SDL_GetTicks() - 100;
    } else if (m_activeTab == Tab::Catalog) {
        m_catalogDockDirty = true;
        m_catalogDockCurrentKey.clear();
        m_lastCatalogMoveTime = SDL_GetTicks() - 120;
    }
#endif
}



void App::openRecordingsBrowser(const std::string& titleId, const std::string& gameName) {
    m_recordingsTargetTitleId = titleId;
    m_recordingsTargetGameName = gameName;
    m_localRecordings = Installer::listLocalRecordings(m_platform->getRecordingsDirectory());
    m_recordingsSelectedIndex = 0;
    m_recordingsScrollOffset = 0;
    m_recordingsOpenedAt = SDL_GetTicks();
    m_isRecordingsBrowserOpen = true;
}

void App::closeRecordingsBrowser() {
    m_isRecordingsBrowserOpen = false;
}

void App::renderRecordingsBrowser() {
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x02, 0x05, 0x0C, 0xEE});

    // 4IFIR Frosted Glass Modal Container
    int bw = 1140;
    int bh = 600;
    int bx = (Theme::SCREEN_WIDTH - bw) / 2;
    int by = (Theme::SCREEN_HEIGHT - bh) / 2;

    drawGlassCard(bx, by, bw, bh, false, true);
    drawNeonGradientOutline(bx, by, bw, bh, 2);

    // Header
    drawText("4IFIR Recordings Library  |  sdmc:/recordings/", bx + 35, by + 25, Theme::COLOR_FOCUS_CYAN, 20);
    std::string subtitle = "Привязать геймплейную запись к: " + m_recordingsTargetGameName + " [" + m_recordingsTargetTitleId + "]";
    drawText(subtitle, bx + 35, by + 55, Theme::COLOR_TEXT_MUTED, 13, bw - 70);

    if (m_localRecordings.empty()) {
        drawGlassCard(bx + 40, by + 120, bw - 80, 360, false, false);
        drawText("В папке sdmc:/recordings/ не найдено видеофайлов (.mp4).", bx + 70, by + 240, Theme::COLOR_WARNING, 18);
        drawText("Запишите геймплей на Switch через рекордер 4IFIR, и ваши ролики появятся здесь!", bx + 70, by + 280, Theme::COLOR_TEXT_MUTED, 14);
    } else {
        int visibleCount = 5;
        if (m_recordingsSelectedIndex < m_recordingsScrollOffset) {
            m_recordingsScrollOffset = m_recordingsSelectedIndex;
        } else if (m_recordingsSelectedIndex >= m_recordingsScrollOffset + visibleCount) {
            m_recordingsScrollOffset = m_recordingsSelectedIndex - visibleCount + 1;
        }

        int itemY = by + 95;
        int itemH = 78;
        int maxIdx = std::min(m_recordingsScrollOffset + visibleCount, static_cast<int>(m_localRecordings.size()));

        for (int i = m_recordingsScrollOffset; i < maxIdx; ++i) {
            bool isFocused = (i == m_recordingsSelectedIndex);
            const auto& rec = m_localRecordings[i];

            if (isFocused) {
                drawRect(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(bx + 35, itemY, bw - 70, itemH, 2);
            } else {
                drawRect(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_BG_SURFACE);
                drawRectOutline(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_BORDER, 1);
            }

            // Video Tag
            drawRect(bx + 55, itemY + 20, 60, 38, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BG_ELEVATED);
            drawText("MP4", bx + 70, itemY + 31, isFocused ? Theme::COLOR_BG_BASE : Theme::COLOR_FOCUS_CYAN, 14);

            // Filename & Path
            drawText(rec.filename, bx + 130, itemY + 16, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, bw - 380);
            drawText(rec.fullPath, bx + 130, itemY + 44, Theme::COLOR_TEXT_MUTED, 12, bw - 380);

            // Size Pill
            drawText(rec.formattedSize, bx + bw - 220, itemY + 28, Theme::COLOR_FOCUS_CYAN, 15);

            itemY += itemH + 10;
        }

        // Counter Indicator
        std::string countStr = std::to_string(m_recordingsSelectedIndex + 1) + " / " + std::to_string(m_localRecordings.size());
        drawText(countStr, bx + bw - 130, by + 30, Theme::COLOR_TEXT_MUTED, 14);
    }

    // Bottom Help Banner
    drawRect(bx + 35, by + bh - 55, bw - 70, 38, Theme::COLOR_BG_BASE);
    drawRectOutline(bx + 35, by + bh - 55, bw - 70, 38, Theme::COLOR_BORDER, 1);
    if (!m_localRecordings.empty()) {
        drawText("[D-Pad] Выбор   |   [X] Предпросмотр   |   [A] Установить как видеофон   |   [B] Назад", bx + 55, by + bh - 43, Theme::COLOR_TEXT_MUTED, 13);
    } else {
        drawText("[B] Назад в меню", bx + 55, by + bh - 43, Theme::COLOR_TEXT_MUTED, 13);
    }
}

void App::executeInstallLocalRecording() {
    if (m_pendingRecordingToInstallPath.empty() || m_recordingsTargetTitleId.empty()) {
        return;
    }

    InstallResult res = Installer::installLocalRecording(
        m_platform->getCoversDirectory(),
        m_recordingsTargetTitleId,
        m_pendingRecordingToInstallPath,
        true
    );

    if (res.success) {
        std::string varId = "local:" + m_pendingRecordingToInstallName;
        InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), m_recordingsTargetTitleId, varId);
        refreshInstalledGames();
        closeRecordingsBrowser();
        m_statusNotification = "Запись 4IFIR успешно установлена!";
        m_notificationFramesRemaining = 180;
    } else {
        m_dialogTitle = "Ошибка установки записи";
        m_dialogMessage = res.message;
        m_activeDialog = DialogType::MessageAlert;
    m_dialogOpenedAt = SDL_GetTicks();
    }
}

void App::runIntegrityCheck() {
    // Audit Finding #4: Scan BOTH installed covers (recordings/covers/) AND installed video icons (recordings/icons/)
    IntegrityReport covReport = Installer::validateAllInstalledCovers(m_platform->getCoversDirectory());
    IntegrityReport icoReport = Installer::validateAllInstalledCovers(m_platform->getIconsDirectory());

    IntegrityReport report;
    report.totalChecked = covReport.totalChecked + icoReport.totalChecked;
    report.totalValid = covReport.totalValid + icoReport.totalValid;
    report.issues = covReport.issues;
    report.issues.insert(report.issues.end(), icoReport.issues.begin(), icoReport.issues.end());

    m_lastIntegrityTotalChecked = report.totalChecked;

    if (report.issues.empty()) {
        m_activeDialog = DialogType::IntegrityCheckResult;
        m_dialogOpenedAt = SDL_GetTicks();
        m_dialogTitle = tr("Целостность видеофонов и иконок", "Covers & Icons Integrity");
        if (report.totalChecked == 0) {
            m_dialogMessage = tr("В папках recordings/covers/ и recordings/icons/ пока нет установленных файлов.",
                                 "No installed covers or video icons found in recordings/covers/ or recordings/icons/.");
        } else {
            m_dialogMessage = tr("Проверено файлов (видеофоны + видеоиконки): ", "Verified files (covers + icons): ") +
                              std::to_string(report.totalChecked) +
                              tr("\n\nВсе установленные файлы полностью исправны, не повреждены и готовы к работе в меню Switch!",
                                 "\n\nAll installed files are valid, intact, and ready for the Switch Home Menu!");
        }
    } else {
        m_detectedIntegrityIssues = report.issues;
        m_activeDialog = DialogType::ConfirmDeleteCorrupted;
        m_dialogOpenedAt = SDL_GetTicks();
        m_dialogTitle = tr("Обнаружены повреждённые файлы!", "Corrupted Files Detected!");
        std::string msg = tr("Найдено повреждений: ", "Found corrupted: ") + std::to_string(report.issues.size()) +
                          tr(" из ", " of ") + std::to_string(report.totalChecked) + tr(" файлов:\n", " files:\n");
        for (size_t i = 0; i < report.issues.size() && i < 3; ++i) {
            msg += "• " + report.issues[i].filename + " (" + report.issues[i].reason + ")\n";
        }
        if (report.issues.size() > 3) {
            msg += "• ... +" + std::to_string(report.issues.size() - 3) + "\n";
        }
        msg += tr("\nУдалить повреждённые файлы во избежание сбоя или зависания меню Switch?",
                  "\nDelete corrupted files to prevent Switch Home Menu freezes?");
        m_dialogMessage = msg;
        m_dialogFocus = 0;
    }
}

void App::executeDeleteCorruptedCovers() {
    int deleted = Installer::deleteCorruptedCovers(m_detectedIntegrityIssues);
    for (const auto& issue : m_detectedIntegrityIssues) {
        InstalledRegistry::instance().remove(m_platform->getAppDirectory(), issue.titleId);
    }
    refreshInstalledGames();

    m_detectedIntegrityIssues.clear();
    m_statusNotification = tr("Удалено повреждённых файлов: ", "Deleted corrupted files: ") + std::to_string(deleted);
    m_notificationFramesRemaining = 180;
}


void App::openGamePicker(const Variant& variant, const std::string& sourceGameName) {
    m_gamePickerPendingVariant = variant;
    m_gamePickerSourceGameName = sourceGameName;
    m_gamePickerSelectedIndex = 0;
    m_gamePickerScrollOffset = 0;
    m_gamePickerOpenedAt = SDL_GetTicks();
    m_isGamePickerOpen = true;
}

void App::closeGamePicker() {
    m_isGamePickerOpen = false;
}

void App::renderGamePicker() {
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x02, 0x05, 0x0C, 0xEE});

    // 4IFIR Frosted Glass Modal Container
    int bw = 1140;
    int bh = 600;
    int bx = (Theme::SCREEN_WIDTH - bw) / 2;
    int by = (Theme::SCREEN_HEIGHT - bh) / 2;

    drawGlassCard(bx, by, bw, bh, false, true);
    drawNeonGradientOutline(bx, by, bw, bh, 2);

    // Header
    drawText((m_language == Language::Russian ? "Назначить видеофон на игру" : "Assign Video Theme to Game"),
             bx + 35, by + 25, Theme::COLOR_FOCUS_CYAN, 20);

    std::string subtitle = (m_language == Language::Russian ? "Видеофон: «" : "Video Theme: «") +
                           m_gamePickerPendingVariant.name + "» (" + styleToString(m_gamePickerPendingVariant.style) + ")  |  " +
                           (m_language == Language::Russian ? "Выберите игру на консоли:" : "Select target game on console:");
    drawText(subtitle, bx + 35, by + 55, Theme::COLOR_TEXT_MUTED, 13, bw - 70);

    if (m_installedGames.empty()) {
        drawGlassCard(bx + 40, by + 120, bw - 80, 360, false, false);
        drawText((m_language == Language::Russian ? "На консоли не обнаружено установленных игр." : "No installed games detected on console."),
                 bx + 70, by + 250, Theme::COLOR_WARNING, 18);
    } else {
        int visibleCount = 5;
        if (m_gamePickerSelectedIndex < m_gamePickerScrollOffset) {
            m_gamePickerScrollOffset = m_gamePickerSelectedIndex;
        } else if (m_gamePickerSelectedIndex >= m_gamePickerScrollOffset + visibleCount) {
            m_gamePickerScrollOffset = m_gamePickerSelectedIndex - visibleCount + 1;
        }

        int itemY = by + 95;
        int itemH = 78;
        int maxIdx = std::min(m_gamePickerScrollOffset + visibleCount, static_cast<int>(m_installedGames.size()));

        for (int i = m_gamePickerScrollOffset; i < maxIdx; ++i) {
            bool isFocused = (i == m_gamePickerSelectedIndex);
            const auto& game = m_installedGames[i];

            if (isFocused) {
                drawRect(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(bx + 35, itemY, bw - 70, itemH, 2);
            } else {
                drawRect(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_BG_SURFACE);
                drawRectOutline(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_BORDER, 1);
            }

            // Game Icon / Badge
            drawRect(bx + 55, itemY + 20, 60, 38, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BG_ELEVATED);
            drawText("NSP", bx + 70, itemY + 31, isFocused ? Theme::COLOR_BG_BASE : Theme::COLOR_FOCUS_CYAN, 14);

            // Title & Title ID
            drawText(game.name, bx + 130, itemY + 16, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, bw - 380);
            drawText("Title ID: " + game.titleId, bx + 130, itemY + 44, Theme::COLOR_TEXT_MUTED, 12, bw - 380);

            // Status Pill
            if (game.hasInstalledCover) {
                drawRect(bx + bw - 240, itemY + 26, 125, 26, {0x10, 0xB9, 0x81, 0x22});
                drawRectOutline(bx + bw - 240, itemY + 26, 125, 26, Theme::COLOR_SUCCESS, 1);
                drawText((m_language == Language::Russian ? "ЕСТЬ ФОН" : "HAS COVER"), bx + bw - 212, itemY + 32, Theme::COLOR_SUCCESS, 12);
            } else {
                drawRect(bx + bw - 240, itemY + 26, 125, 26, {0x28, 0x33, 0x47, 0x55});
                drawRectOutline(bx + bw - 240, itemY + 26, 125, 26, Theme::COLOR_BORDER, 1);
                drawText((m_language == Language::Russian ? "НЕТ ФОНА" : "NO COVER"), bx + bw - 212, itemY + 32, Theme::COLOR_TEXT_MUTED, 12);
            }

            itemY += itemH + 10;
        }

        // Counter Indicator
        std::string countStr = std::to_string(m_gamePickerSelectedIndex + 1) + " / " + std::to_string(m_installedGames.size());
        drawText(countStr, bx + bw - 130, by + 30, Theme::COLOR_TEXT_MUTED, 14);
    }

    // Bottom Help Banner
    drawRect(bx + 35, by + bh - 55, bw - 70, 38, Theme::COLOR_BG_BASE);
    drawRectOutline(bx + 35, by + bh - 55, bw - 70, 38, Theme::COLOR_BORDER, 1);
    drawText((m_language == Language::Russian ? "[D-Pad] Выбор игры   |   [A] Установить видеофон для этой игры   |   [B] Отмена"
                                              : "[D-Pad] Select game   |   [A] Install video theme for this game   |   [B] Cancel"),
             bx + 55, by + bh - 43, Theme::COLOR_TEXT_MUTED, 13);
}

// ----------------- Collection / Variant Browser & Live Dock Preview Implementation -----------------

void App::openCollectionBrowser(const GameCatalogEntry& entry) {
    auto covVars = getCoverVariants(entry);
    auto iconVars = getUniqueIconVariants(entry);
    // Append standalone 256x256 icon variants (icon-*) so all icons of this game can also be browsed & previewed here
    std::set<std::string> attachedIconUrls;
    for (const auto& cv : covVars) {
        if (cv.hasIcon && !cv.iconUrl.empty()) {
            std::string dId = extractDriveIdFromUrl(cv.iconUrl);
            attachedIconUrls.insert(!dId.empty() ? dId : cv.iconUrl);
        }
    }
    for (const auto& iv : iconVars) {
        std::string dId = extractDriveIdFromUrl(iv.iconUrl);
        std::string key = !dId.empty() ? dId : iv.iconUrl;
        if (iv.id.rfind("icon-", 0) == 0 || attachedIconUrls.count(key) == 0) {
            Variant pureIco = iv;
            if (pureIco.id.rfind("icon-", 0) != 0) {
                pureIco.id = "icon-" + pureIco.id;
            }
            covVars.push_back(std::move(pureIco));
        }
    }
    if (covVars.empty()) return;
    m_collectionEntry = entry;
    m_collectionMediaTitleId = entry.titleId;
    if (!m_linkingTargetTitleId.empty()) {
        m_collectionTitleId = m_linkingTargetTitleId;
        m_collectionGameName = m_linkingTargetGameName + " <- " + entry.title;
    } else {
        m_collectionTitleId = entry.titleId;
        m_collectionGameName = entry.title;
    }
    m_collectionVariants = covVars;
    m_collectionSelectedIndex = 0;
    m_collectionScrollOffset = 0;
    m_collectionOpenedAt = SDL_GetTicks();
    m_isCollectionBrowserOpen = true;
    m_collectionPreviewIconMode = (m_catalogSortMode == CatalogSortMode::IconsOnly);
    m_collectionPreviewDirty = false;
    loadCollectionThumbnail(m_collectionVariants[0]);
}

void App::closeCollectionBrowser() {
    m_isCollectionBrowserOpen = false;
    m_collectionPreviewDirty = false;
    m_collectionTransferQueued = false;
    m_videoPlayer.close();
    m_cancelCollectionThumb.store(true);
    m_collectionThumbLoading = false;
    m_collectionVideoDownloading = false;
    if (m_collectionThumbTexture) {
        SDL_DestroyTexture(m_collectionThumbTexture);
        m_collectionThumbTexture = nullptr;
    }
    m_collectionCurrentThumbVariantId.clear();
    m_pendingCollectionThumbToLoad.clear();
    m_pendingCollectionVideoToOpen.clear();
    m_collectionVariants.clear();

#ifdef HAS_SDL2
    if (m_activeTab == Tab::Catalog) {
        m_catalogDockDirty = true;
        m_catalogDockCurrentKey.clear();
        m_lastCatalogMoveTime = SDL_GetTicks() - 120;
    } else if (m_activeTab == Tab::VideoIcons) {
        m_videoIconDockDirty = true;
        m_videoIconDockCurrentKey.clear();
        m_lastVideoIconMoveTime = SDL_GetTicks() - 100;
    }
#endif
}

void App::loadCollectionThumbnail(const Variant& variant) {
#ifdef HAS_SDL2
    m_videoPlayer.close();
    m_cancelCollectionThumb.store(true);

    if (m_collectionThumbTexture) {
        SDL_DestroyTexture(m_collectionThumbTexture);
        m_collectionThumbTexture = nullptr;
    }

    bool isPureIcon = (variant.id.rfind("icon-", 0) == 0) || (variant.width == 256 && variant.height == 256);
    bool showAsIcon = isPureIcon || (m_collectionPreviewIconMode && variant.hasIcon && !variant.iconUrl.empty());
    const std::string& mediaTid = m_collectionMediaTitleId.empty() ? m_collectionTitleId : m_collectionMediaTitleId;
    std::string cacheKey = showAsIcon
        ? ("icon_" + mediaTid + "_" + variant.id)
        : (mediaTid + "_" + variant.id);
    m_collectionCurrentThumbVariantId = cacheKey;

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string thumbFile = thumbDir + "/" + cacheKey + ".jpg";
    std::string vidFile = thumbDir + "/" + cacheKey + ".mp4";

    // 1. Check if video is already cached or installed on SD — play live immediately!
    if (showAsIcon) {
        uint64_t minIcoSz = 4096;
        if (std::filesystem::exists(vidFile, ec) && std::filesystem::file_size(vidFile, ec) >= minIcoSz) {
            if (!m_videoPlayer.open(vidFile, m_renderer)) {
                std::filesystem::remove(vidFile, ec);
            }
        }
    } else {
        std::string installedPath = m_platform->getCoversDirectory() + "/" + Config::getTargetCoverFileName(m_collectionTitleId);
        std::string activeVarId = InstalledRegistry::instance().getVariantId(m_collectionTitleId);
        if (activeVarId == variant.id && std::filesystem::exists(installedPath, ec)) {
            m_videoPlayer.open(installedPath, m_renderer);
        } else if (std::filesystem::exists(vidFile, ec) && std::filesystem::file_size(vidFile, ec) >= 50000) {
            if (!m_videoPlayer.open(vidFile, m_renderer)) {
                std::filesystem::remove(vidFile, ec);
            }
        }
    }

    // 2. Load validated static thumbnail if cached on disk (or in m_rowThumbTextures)
    bool hasCachedThumb = (findCachedThumbTexture(mediaTid, variant, showAsIcon) != nullptr);
    if (std::filesystem::exists(thumbFile, ec) && validateImageFile(thumbFile)) {
        m_collectionThumbTexture = loadTextureFromFile(m_renderer, thumbFile);
        if (!m_collectionThumbTexture) {
            std::filesystem::remove(thumbFile, ec);
        } else {
            hasCachedThumb = true;
        }
    } else if (std::filesystem::exists(thumbFile, ec)) {
        std::filesystem::remove(thumbFile, ec);
    }

    if (m_videoPlayer.isPlaying()) {
        m_collectionThumbLoading = false;
        m_collectionVideoDownloading = false;
        m_collectionTransferQueued = false;
        return;
    }

    std::string videoUrl = showAsIcon
        ? (!variant.iconUrl.empty() ? variant.iconUrl : variant.url)
        : variant.url;
    std::string thumbUrl = variant.previewUrl;
    if (showAsIcon || thumbUrl.empty()) {
        std::string drvId = extractDriveIdFromUrl(videoUrl);
        if (!drvId.empty()) {
            thumbUrl = "https://drive.google.com/thumbnail?id=" + drvId + (showAsIcon ? "&sz=w320" : "&sz=w640");
        }
    }

    m_collectionDownloadBytes.store(0);
    m_collectionDownloadTotal.store(showAsIcon
        ? (variant.iconSizeBytes > 0 ? variant.iconSizeBytes : 180 * 1024)
        : (variant.sizeBytes > 0 ? variant.sizeBytes : 3500 * 1024));
    m_collectionThumbLoading = !hasCachedThumb;
    m_collectionVideoDownloading = !videoUrl.empty();

    m_queuedCollThumbUrl = thumbUrl;
    m_queuedCollVideoUrl = videoUrl;
    m_queuedCollThumbFile = thumbFile;
    m_queuedCollVidFile = vidFile;
    m_queuedCollKey = cacheKey;
    m_queuedCollIsIcon = showAsIcon;
    m_queuedCollForDock = false;
    m_collectionTransferQueued = true;

    updateAsyncPreviewWorkers();
#endif
}

void App::loadVideoIconDockPreview(const GameCatalogEntry& entry, const Variant& variant) {
#ifdef HAS_SDL2
    m_videoPlayer.close();
    m_cancelCollectionThumb.store(true);

    if (m_videoIconDockTexture) {
        SDL_DestroyTexture(m_videoIconDockTexture);
        m_videoIconDockTexture = nullptr;
    }

    std::string dockKey = "icon_" + entry.titleId + "_" + variant.id;
    m_videoIconDockCurrentKey = dockKey;
    m_collectionCurrentThumbVariantId = dockKey;

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string thumbFile = thumbDir + "/" + dockKey + ".jpg";
    std::string vidFile = thumbDir + "/" + dockKey + ".mp4";

    // 1. Check if cached 256x256 MP4 already exists in thumbs/ or is installed on SD
    if (std::filesystem::exists(vidFile, ec) && std::filesystem::file_size(vidFile, ec) >= 4096) {
        if (!m_videoPlayer.open(vidFile, m_renderer)) {
            std::filesystem::remove(vidFile, ec);
        }
    }

    // 2. Load cached static thumbnail if valid
    bool hasCachedThumb = (findCachedThumbTexture(entry.titleId, variant, true) != nullptr);
    if (std::filesystem::exists(thumbFile, ec) && validateImageFile(thumbFile)) {
        m_videoIconDockTexture = loadTextureFromFile(m_renderer, thumbFile);
        if (!m_videoIconDockTexture) {
            std::filesystem::remove(thumbFile, ec);
        } else {
            hasCachedThumb = true;
        }
    } else if (std::filesystem::exists(thumbFile, ec)) {
        std::filesystem::remove(thumbFile, ec);
    }

    if (m_videoPlayer.isPlaying()) {
        m_collectionThumbLoading = false;
        m_collectionVideoDownloading = false;
        m_collectionTransferQueued = false;
        return;
    }

    std::string videoUrl = !variant.iconUrl.empty() ? variant.iconUrl : variant.url;
    std::string thumbUrl = variant.previewUrl;
    if (thumbUrl.empty()) {
        std::string drvId = extractDriveIdFromUrl(videoUrl);
        if (!drvId.empty()) {
            thumbUrl = "https://drive.google.com/thumbnail?id=" + drvId + "&sz=w320";
        }
    }

    m_collectionDownloadBytes.store(0);
    m_collectionDownloadTotal.store(variant.iconSizeBytes > 0 ? variant.iconSizeBytes : (variant.sizeBytes > 0 ? variant.sizeBytes : 180 * 1024));
    m_collectionThumbLoading = !hasCachedThumb;
    m_collectionVideoDownloading = !videoUrl.empty();

    m_queuedCollThumbUrl = thumbUrl;
    m_queuedCollVideoUrl = videoUrl;
    m_queuedCollThumbFile = thumbFile;
    m_queuedCollVidFile = vidFile;
    m_queuedCollKey = dockKey;
    m_queuedCollIsIcon = true;
    m_queuedCollForDock = true;
    m_collectionTransferQueued = true;

    updateAsyncPreviewWorkers();
#endif
}

void App::renderCollectionBrowser() {
#ifdef HAS_SDL2
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x02, 0x05, 0x0C, 0xFA});

    // 4IFIR Frosted Glass Modal Container
    int bw = 1220;
    int bh = 660;
    int bx = (Theme::SCREEN_WIDTH - bw) / 2;
    int by = (Theme::SCREEN_HEIGHT - bh) / 2;

    drawGlassCard(bx, by, bw, bh, false, true);
    drawNeonGradientOutline(bx, by, bw, bh, 2);

    // Header
    bool isAD = Config::isAfterDark();
    if (isAD) {
        drawRect(bx + 25, by + 18, 175, 26, {0xEC, 0x48, 0x99, 0x33});
        drawRectOutline(bx + 25, by + 18, 175, 26, Theme::COLOR_FOCUS_PINK, 1);
        drawText("AFTER DARK 18+", bx + 35, by + 24, Theme::COLOR_FOCUS_PINK, 12);
    } else {
        drawRect(bx + 25, by + 18, 160, 26, {0x00, 0xF0, 0xFF, 0x33});
        drawRectOutline(bx + 25, by + 18, 160, 26, Theme::COLOR_FOCUS_CYAN, 1);
        drawText(tr("КОЛЛЕКЦИЯ 4IFIR", "4IFIR COLLECTION"), bx + 35, by + 24, Theme::COLOR_FOCUS_CYAN, 12);
    }

    drawText(m_collectionGameName, bx + 215, by + 17, Theme::COLOR_TEXT_PRIMARY, 21, 750);

    int totalV = static_cast<int>(m_collectionVariants.size());
    std::string countStr = std::to_string(m_collectionSelectedIndex + 1) + " / " + std::to_string(totalV);
    drawText(countStr, bx + bw - 140, by + 20, Theme::COLOR_FOCUS_CYAN, 16);

    // Divider line
    drawRect(bx + 25, by + 54, bw - 50, 1, Theme::COLOR_BORDER);

    // Left Column: Variants List (Width 640)
    int lx = bx + 25;
    int ly = by + 68;
    int lw = 635;
    int visibleCount = 5;

    if (m_collectionSelectedIndex < m_collectionScrollOffset) {
        m_collectionScrollOffset = m_collectionSelectedIndex;
    }
    if (m_collectionSelectedIndex >= m_collectionScrollOffset + visibleCount) {
        m_collectionScrollOffset = m_collectionSelectedIndex - visibleCount + 1;
    }

    if (m_collectionScrollOffset > 0) {
        drawText(tr("^ Еще фоны выше (влево: -5)", "^ More covers above (left: -5)"), lx + 200, ly - 14, Theme::COLOR_FOCUS_CYAN, 12);
    }

    int cardY = ly;
    int cardH = 88;
    int cardGap = 8;
    int endIdx = std::min(totalV, m_collectionScrollOffset + visibleCount);

    for (int i = m_collectionScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_collectionSelectedIndex);
        const auto& v = m_collectionVariants[i];

        if (isSelected) {
            drawRect(lx, cardY, lw, cardH, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(lx, cardY, lw, cardH, 2);
        } else {
            drawRect(lx, cardY, lw, cardH, {0x13, 0x1A, 0x2A, 0x99});
            drawRectOutline(lx, cardY, lw, cardH, Theme::COLOR_BORDER, 1);
        }

        // Title line
        bool isFav = isVariantFavorite(m_collectionTitleId, v.id);
        std::string titleStr = (isFav ? "[★] " : "") + std::to_string(i + 1) + ". " + v.name;
        drawText(titleStr, lx + 16, cardY + 14, isFav ? Color{0xFF, 0xD7, 0x00, 0xFF} : (isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY), 16, lw - 70);

        // Metadata badges
        int bxPos = lx + 16;

        // Style badge
        std::string styleStr = styleToString(v.style);
        drawRect(bxPos, cardY + 46, 110, 24, {0x28, 0x33, 0x47, 0x66});
        drawRectOutline(bxPos, cardY + 46, 110, 24, Theme::COLOR_BORDER, 1);
        drawText(styleStr, bxPos + 10, cardY + 51, Theme::COLOR_TEXT_MUTED, 11);
        bxPos += 120;

        // Audio badge
        if (v.hasAudio) {
            drawRect(bxPos, cardY + 46, 65, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(bxPos, cardY + 46, 65, 24, Theme::COLOR_SUCCESS, 1);
            drawText(tr("ЗВУК", "AUDIO"), bxPos + 14, cardY + 51, Theme::COLOR_SUCCESS, 11);
            bxPos += 75;
        } else {
            drawRect(bxPos, cardY + 46, 82, 24, Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 82, 24, Theme::COLOR_BORDER, 1);
            drawText(tr("БЕЗ ЗВУКА", "NO AUDIO"), bxPos + 9, cardY + 51, Theme::COLOR_TEXT_MUTED, 10);
            bxPos += 90;
        }

        // Icon badge
        if (v.hasIcon) {
            drawRect(bxPos, cardY + 46, 75, 24, Theme::COLOR_ICON_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 75, 24, Theme::COLOR_ICON_BADGE, 1);
            drawText(tr("ИКОНКА", "ICON"), bxPos + 11, cardY + 51, Theme::COLOR_ICON_BADGE, 11);
            bxPos += 83;
        } else {
            drawRect(bxPos, cardY + 46, 86, 24, Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 86, 24, Theme::COLOR_BORDER, 1);
            drawText(tr("БЕЗ ИКОНКИ", "NO ICON"), bxPos + 8, cardY + 51, Theme::COLOR_TEXT_MUTED, 10);
            bxPos += 94;
        }

        // Specs text
        double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
        char szBuf[32];
        if (mb >= 0.1) snprintf(szBuf, sizeof(szBuf), "%.1f MB", mb);
        else snprintf(szBuf, sizeof(szBuf), "~3.5 MB");

        std::string metaLine = std::to_string(v.width) + "x" + std::to_string(v.height) + " @" +
                               std::to_string((int)v.fps) + "fps  |  " + std::string(szBuf) +
                               (!v.codec.empty() ? ("  |  " + v.codec) : "");
        drawText(metaLine, bxPos, cardY + 51, Theme::COLOR_TEXT_MUTED, 12, lw - bxPos - 30);

        if (isSelected) {
            drawText(">", lx + lw - 30, cardY + 33, Theme::COLOR_FOCUS_CYAN, 18);
        }

        cardY += cardH + cardGap;
    }

    if (endIdx < totalV) {
        std::string belowStr = tr("v Еще варианты ниже: ", "v More below: ") + std::to_string(totalV - endIdx) + tr(" шт. (вправо: +5)", " (right: +5)");
        drawText(belowStr, lx + 180, ly + (cardH + cardGap) * visibleCount + 2, Theme::COLOR_FOCUS_PINK, 12);
    }

    // Right Column: Live Video & Static Mini-Preview Panel (Width 520)
    int rx = bx + 675;
    int ry = by + 68;
    int rw = 520;
    int rh = 530;

    drawGlassCard(rx, ry, rw, rh, false, false);

    // Determine whether current variant is being previewed as 16:9 Cover or 256x256 Video Icon
    bool hasSelVar = (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 && m_collectionSelectedIndex < totalV);
    bool isSelPureIcon = hasSelVar && ((m_collectionVariants[m_collectionSelectedIndex].id.rfind("icon-", 0) == 0) ||
                                       (m_collectionVariants[m_collectionSelectedIndex].width == 256 && m_collectionVariants[m_collectionSelectedIndex].height == 256));
    bool selHasAttachedIcon = hasSelVar && !isSelPureIcon && m_collectionVariants[m_collectionSelectedIndex].hasIcon &&
                              !m_collectionVariants[m_collectionSelectedIndex].iconUrl.empty();
    bool showCollIconMode = isSelPureIcon || (m_collectionPreviewIconMode && selHasAttachedIcon);

    // Live Preview Box (480 x 270)
    int px = rx + 20;
    int py = ry + 20;
    int pw = 480;
    int ph = 270;

    drawRect(px, py, pw, ph, {0x08, 0x0D, 0x16, 0xFA});
    SDL_Rect dst{px + 2, py + 2, pw - 4, ph - 4};
    if (showCollIconMode) {
        // Draw Switch Home Screen 1:1 Icon Mockup inside the 480x270 preview box
        drawRoundedRect(px + 20, py + 40, 88, 190, 10, {0x10, 0x17, 0x26, 0xAA});
        drawRoundedOutline(px + 20, py + 40, 88, 190, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        drawRoundedRect(px + pw - 108, py + 40, 88, 190, 10, {0x10, 0x17, 0x26, 0xAA});
        drawRoundedOutline(px + pw - 108, py + 40, 88, 190, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        dst = {px + (pw - 234) / 2, py + 18, 234, 234};
        drawRoundedRect(dst.x - 3, dst.y - 3, dst.w + 6, dst.h + 6, 12, {0x05, 0x09, 0x12, 0xFF});
        drawNeonRoundedOutline(dst.x - 3, dst.y - 3, dst.w + 6, dst.h + 6, 12, 2);
    }

    const std::string& mediaTid = m_collectionMediaTitleId.empty() ? m_collectionTitleId : m_collectionMediaTitleId;
    SDL_Texture* activeCollTex = m_collectionThumbTexture;
    if (!activeCollTex && hasSelVar) {
        activeCollTex = findCachedThumbTexture(mediaTid, m_collectionVariants[m_collectionSelectedIndex], showCollIconMode);
    }

    if (!m_isFullscreenPreview && m_videoPlayer.isPlaying()) {
        m_videoPlayer.render(m_renderer, &dst);
        drawRoundedRect(px + 10, py + 10, showCollIconMode ? 132 : 118, 22, 5, {0x09, 0x12, 0x1E, 0xDD});
        drawRoundedOutline(px + 10, py + 10, showCollIconMode ? 132 : 118, 22, 5, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
        drawTextCentered(showCollIconMode ? "LIVE ICON 256x256" : "LIVE PREVIEW", px + (showCollIconMode ? 76 : 69), py + 14, Theme::COLOR_SUCCESS, 10);
    } else if (activeCollTex) {
        SDL_RenderCopy(m_renderer, activeCollTex, nullptr, &dst);
        if (m_collectionVideoDownloading || m_collectionPreviewDirty) {
            drawRoundedRect(px + 10, py + 10, 175, 24, 5, {0x09, 0x12, 0x1E, 0xE6});
            drawLoadingSpinner(px + 24, py + 22, 6, Theme::COLOR_FOCUS_CYAN);
            uint64_t dlKb = m_collectionDownloadBytes.load() / 1024;
            std::string vTxt = (dlKb > 0)
                ? (tr("Видео: ", "Video: ") + std::to_string(dlKb) + " KB")
                : tr("Буферизация...", "Buffering...");
            drawText(vTxt, px + 36, py + 14, Theme::COLOR_FOCUS_CYAN, 11);
        }
    } else if (m_collectionThumbLoading || m_collectionVideoDownloading || m_collectionPreviewDirty) {
        drawRoundedRect(dst.x + 6, dst.y + 6, dst.w - 12, dst.h - 12, 10, {0x10, 0x18, 0x28, 0xFF});
        drawLoadingSpinner(px + pw / 2, py + ph / 2 - 22, 18, Theme::COLOR_FOCUS_CYAN);
        uint64_t dlKb = m_collectionDownloadBytes.load() / 1024;
        std::string loadHdr = showCollIconMode
            ? tr("Загрузка иконки 256x256...", "Loading 256x256 icon...")
            : tr("Загрузка превью...", "Loading preview...");
        drawTextCentered(loadHdr, px + pw / 2, py + ph / 2 + 8, Theme::COLOR_FOCUS_CYAN, 15);
        if (dlKb > 0) {
            drawTextCentered(std::to_string(dlKb) + " KB", px + pw / 2, py + ph / 2 + 32, Theme::COLOR_FOCUS_PINK, 12);
        }
    } else {
        drawTextCentered(tr("Нажмите [X] для полного экрана", "Press [X] for Fullscreen"), px + pw / 2, py + ph / 2 - 8, Theme::COLOR_TEXT_MUTED, 15);
    }
    drawNeonGradientOutline(px, py, pw, ph, 2);

    // Interactive [Фон 16:9] | [R] Иконка 256x256 toggle pill at top-right of preview box when variant has both Cover & Icon
    if (selHasAttachedIcon) {
        int togX = px + pw - 246;
        int togY = py + 8;
        drawRoundedRect(togX, togY, 104, 24, 6, !m_collectionPreviewIconMode ? Theme::COLOR_FOCUS_FILL : Color{0x09, 0x11, 0x1E, 0xE6});
        drawRoundedOutline(togX, togY, 104, 24, 6, !m_collectionPreviewIconMode ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, !m_collectionPreviewIconMode ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, 1);
        drawTextCentered(tr("Фон 16:9", "Cover 16:9"), togX + 52, togY + 5, !m_collectionPreviewIconMode ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 10);

        drawRoundedRect(togX + 108, togY, 130, 24, 6, m_collectionPreviewIconMode ? Color{0xEC, 0x48, 0x99, 0x3D} : Color{0x09, 0x11, 0x1E, 0xE6});
        drawRoundedOutline(togX + 108, togY, 130, 24, 6, m_collectionPreviewIconMode ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_BORDER, m_collectionPreviewIconMode ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_BORDER, 1);
        drawTextCentered(tr("[R] Иконка 1:1", "[R] Icon 1:1"), togX + 108 + 65, togY + 5, m_collectionPreviewIconMode ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_PRIMARY, 10);
    }

    // Details below preview
    if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
        m_collectionSelectedIndex < totalV) {
        const auto& selVar = m_collectionVariants[m_collectionSelectedIndex];

        drawText(selVar.name, px, py + ph + 16, Theme::COLOR_TEXT_PRIMARY, 17, pw);

        std::string detailStr;
        if (showCollIconMode) {
            uint64_t icoBytes = (selVar.iconSizeBytes > 0) ? selVar.iconSizeBytes : selVar.sizeBytes;
            double icoMb = static_cast<double>(icoBytes) / (1024.0 * 1024.0);
            char icoSzBuf[32];
            if (icoMb >= 0.05) snprintf(icoSzBuf, sizeof(icoSzBuf), "%.2f MB", icoMb);
            else snprintf(icoSzBuf, sizeof(icoSzBuf), "~0.35 MB");
            std::string icoCodec = !selVar.iconCodec.empty() ? selVar.iconCodec : "hevc";
            detailStr = tr("Видеоиконка 4IFIR  •  256x256 (", "4IFIR Video Icon  •  256x256 (") + icoCodec + ")  •  " + std::string(icoSzBuf);
        } else {
            double mb = static_cast<double>(selVar.sizeBytes) / (1024.0 * 1024.0);
            char szBuf[32];
            if (mb >= 0.1) snprintf(szBuf, sizeof(szBuf), "%.1f MB", mb);
            else snprintf(szBuf, sizeof(szBuf), "~3.5 MB");
            detailStr = styleToString(selVar.style) + "  •  " +
                        std::to_string(selVar.width) + "x" + std::to_string(selVar.height) +
                        " @" + std::to_string((int)selVar.fps) + "fps  •  " +
                        std::string(szBuf) +
                        (selVar.hasAudio ? tr("  •  Звук", "  •  Audio") : tr("  •  Без звука", "  •  No Audio"));
        }
        drawText(detailStr, px, py + ph + 44, showCollIconMode ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_MUTED, 12, pw);

        // Audit Finding #2: Separate [A] Direct Install for THIS game vs [Y] Assign to another game
        int b1w = 232;
        int b1h = 40;
        int b1x = px;
        int b1y = py + ph + 76;
        drawRect(b1x, b1y, b1w, b1h, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(b1x, b1y, b1w, b1h, 2);
        std::string aBtnTxt = (m_collectionTitleId == "0000000000000000")
            ? tr("[A] Выбрать игру", "[A] Pick Game")
            : tr("[A] Установить сразу", "[A] Install Now");
        drawTextCentered(aBtnTxt, b1x + b1w / 2, b1y + 11, Theme::COLOR_FOCUS_CYAN, 13);

        // [X] Fullscreen live video button
        int b2w = 232;
        int b2h = 40;
        int b2x = px + 248;
        int b2y = b1y;
        drawRect(b2x, b2y, b2w, b2h, {0x16, 0x20, 0x32, 0xDD});
        drawRectOutline(b2x, b2y, b2w, b2h, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered(tr("[X] На весь экран", "[X] Fullscreen"), b2x + b2w / 2, b2y + 11, Theme::COLOR_FOCUS_CYAN, 13);

        // Second row of action buttons: [Y] На другую игру and [L] В избранное
        int b3y = b1y + 48;
        int b3h = 36;
        drawRect(px, b3y, 232, b3h, {0x16, 0x20, 0x32, 0xAA});
        drawRectOutline(px, b3y, 232, b3h, Theme::COLOR_BORDER, 1);
        drawTextCentered(tr("[Y] На другую игру", "[Y] Other Game"), px + 116, b3y + 10, Theme::COLOR_TEXT_PRIMARY, 12);

        bool isSelFav = isVariantFavorite(m_collectionTitleId, selVar.id);
        int b4x = px + 248;
        if (isSelFav) {
            drawRect(b4x, b3y, 232, b3h, {0xFF, 0xD7, 0x00, 0x33});
            drawRectOutline(b4x, b3y, 232, b3h, {0xFF, 0xD7, 0x00, 0xFF}, 1);
            drawTextCentered(tr("[L] ★ В ИЗБРАННОМ", "[L] ★ FAVORITE"), b4x + 116, b3y + 10, {0xFF, 0xD7, 0x00, 0xFF}, 12);
        } else {
            drawRect(b4x, b3y, 232, b3h, {0x16, 0x20, 0x32, 0xAA});
            drawRectOutline(b4x, b3y, 232, b3h, Theme::COLOR_BORDER, 1);
            drawTextCentered(tr("[L] В избранное ★", "[L] Add Fav ★"), b4x + 116, b3y + 10, Theme::COLOR_TEXT_MUTED, 12);
        }

        drawText(tr("[A] Установить на эту игру • [Y] Назначить на любую другую игру",
                    "[A] Install for this game • [Y] Assign to any other installed game"),
                 px, b3y + 42, Theme::COLOR_TEXT_MUTED, 11, pw);
    }

    // Bottom Navigation Bar
    int footY = by + bh - 42;
    drawRect(bx + 25, footY, bw - 50, 32, {0x0D, 0x13, 0x1F, 0xDD});
    drawRectOutline(bx + 25, footY, bw - 50, 32, Theme::COLOR_BORDER, 1);
    drawText(tr("[D-Pad] Список  |  [R] Фон/Иконка  |  [A] Установить  |  [Y] Другая игра  |  [X] Полный экран  |  [L] Избр.  |  [B] Назад",
                "[D-Pad] List  |  [R] Cover/Icon  |  [A] Install  |  [Y] Other Game  |  [X] Fullscreen  |  [L] Fav  |  [B] Back"),
             bx + 35, footY + 8, Theme::COLOR_TEXT_MUTED, 12);
#endif
}


// ----------------- Catalog Filtering, Sorting & Horizon OS Keyboard -----------------

void App::rebuildCatalogFilter() {
    const auto& allGames = m_catalogManager.getAllGames();
    m_filteredCatalogGames.clear();

    std::string qLower = utf8ToLower(m_catalogSearchQuery);

    for (const auto& g : allGames) {
        // 1. Search Query filter (matches Title, Title ID, Publisher, and Variant Names in EN and RU)
        if (!qLower.empty()) {
            std::string titleLower = utf8ToLower(g.title);
            std::string tidLower = utf8ToLower(g.titleId);
            std::string pubLower = utf8ToLower(g.publisher);

            bool match = (titleLower.find(qLower) != std::string::npos) ||
                         (tidLower.find(qLower) != std::string::npos) ||
                         (pubLower.find(qLower) != std::string::npos);
            if (!match) {
                for (const auto& v : g.variants) {
                    std::string vname = utf8ToLower(v.name);
                    if (vname.find(qLower) != std::string::npos) {
                        match = true;
                        break;
                    }
                }
            }
            if (!match) continue;
        }

        // 2. Installed Only filter
        if (m_catalogSortMode == CatalogSortMode::InstalledOnly) {
            bool isInst = false;
            for (const auto& ig : m_installedGames) {
                if (ig.titleId == g.titleId) {
                    isInst = true;
                    break;
                }
            }
            if (!isInst) continue;
        }

        // 3. Audio Only filter
        if (m_catalogSortMode == CatalogSortMode::AudioOnly) {
            bool hasAud = false;
            for (const auto& v : g.variants) {
                if (v.hasAudio) {
                    hasAud = true;
                    break;
                }
            }
            if (!hasAud) continue;
        }

        // 3.1 Icons Only filter
        if (m_catalogSortMode == CatalogSortMode::IconsOnly) {
            bool hasIco = false;
            for (const auto& v : g.variants) {
                if (v.hasIcon) {
                    hasIco = true;
                    break;
                }
            }
            if (!hasIco) continue;
        }

        // 3.2 Smooth 60 FPS Only filter (Idea 6)
        if (m_catalogSortMode == CatalogSortMode::Fps60Only) {
            bool has60 = false;
            for (const auto& v : g.variants) {
                if (v.fps >= 50.0) {
                    has60 = true;
                    break;
                }
            }
            if (!has60) continue;
        }

        // 4. Favorites Only filter
        if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
            if (!hasGameFavorites(g.titleId)) {
                continue;
            }
        }

        m_filteredCatalogGames.push_back(g);
    }

    // 5. Sorting
    if (m_catalogSortMode == CatalogSortMode::Alphabetical) {
        std::sort(m_filteredCatalogGames.begin(), m_filteredCatalogGames.end(), [](const GameCatalogEntry& a, const GameCatalogEntry& b) {
            return a.title < b.title;
        });
    } else if (m_catalogSortMode == CatalogSortMode::VariantsCount) {
        std::sort(m_filteredCatalogGames.begin(), m_filteredCatalogGames.end(), [](const GameCatalogEntry& a, const GameCatalogEntry& b) {
            return a.variants.size() > b.variants.size();
        });
    }

    // Safe bounds clamp
    if (m_catalogSelectedIndex >= static_cast<int>(m_filteredCatalogGames.size())) {
        m_catalogSelectedIndex = std::max(0, static_cast<int>(m_filteredCatalogGames.size()) - 1);
    }
    m_catalogScrollOffset = 0;
}

void App::cycleCatalogSortMode() {
    int nextMode = (static_cast<int>(m_catalogSortMode) + 1) % 8;
    m_catalogSortMode = static_cast<CatalogSortMode>(nextMode);
    rebuildCatalogFilter();

    std::string modeDesc;
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: modeDesc = tr("Фильтр: Все игры", "Filter: All Games"); break;
        case CatalogSortMode::InstalledOnly: modeDesc = tr("Фильтр: Установленные на консоли", "Filter: Installed on Console"); break;
        case CatalogSortMode::IconsOnly: modeDesc = tr("Фильтр: С HQ-иконками 256x256", "Filter: With 256x256 HQ Icons"); break;
        case CatalogSortMode::AudioOnly: modeDesc = tr("Фильтр: Только со звуком ♪", "Filter: With Audio ♪"); break;
        case CatalogSortMode::Fps60Only: modeDesc = tr("Фильтр: Плавные 60 FPS", "Filter: Smooth 60 FPS"); break;
        case CatalogSortMode::FavoritesOnly: modeDesc = tr("Фильтр: ★ Избранное", "Filter: ★ Favorites"); break;
        case CatalogSortMode::Alphabetical: modeDesc = tr("Сортировка: По алфавиту (А–Я)", "Sort: Alphabetical (A–Z)"); break;
        case CatalogSortMode::VariantsCount: modeDesc = tr("Сортировка: По кол-ву вариантов", "Sort: By Variants Count"); break;
    }
    m_statusNotification = modeDesc;
    m_notificationFramesRemaining = 120;
}

void App::openCatalogKeyboard() {
#ifdef __SWITCH__
    SwkbdConfig kbd;
    char textBuf[256] = {0};
    if (!m_catalogSearchQuery.empty()) {
        strncpy(textBuf, m_catalogSearchQuery.c_str(), sizeof(textBuf) - 1);
    }

    Result rc = swkbdCreate(&kbd, 0);
    if (R_SUCCEEDED(rc)) {
        swkbdConfigMakePresetDefault(&kbd);
        swkbdConfigSetHeaderText(&kbd, Config::isAfterDark() ? "Поиск по каталогу H3H After Dark" : "Поиск по каталогу H3H Backgrounds");
        swkbdConfigSetGuideText(&kbd, "Введите название игры, Title ID или персонажа (напр. Mario, Zelda, NFS)");
        swkbdConfigSetOkButtonText(&kbd, "Найти");
        swkbdConfigSetInitialText(&kbd, textBuf);
        swkbdConfigSetStringLenMax(&kbd, 64);

        rc = swkbdShow(&kbd, textBuf, sizeof(textBuf));
        if (R_SUCCEEDED(rc)) {
            m_catalogSearchQuery = std::string(textBuf);
            // Trim whitespace
            while (!m_catalogSearchQuery.empty() && std::isspace(static_cast<unsigned char>(m_catalogSearchQuery.back()))) {
                m_catalogSearchQuery.pop_back();
            }
            while (!m_catalogSearchQuery.empty() && std::isspace(static_cast<unsigned char>(m_catalogSearchQuery.front()))) {
                m_catalogSearchQuery.erase(m_catalogSearchQuery.begin());
            }
            rebuildCatalogFilter();
            m_statusNotification = m_catalogSearchQuery.empty()
                ? "Поиск сброшен (показаны все игры)"
                : ("Результаты поиска для: \"" + m_catalogSearchQuery + "\" (" + std::to_string(m_filteredCatalogGames.size()) + " игр)");
            m_notificationFramesRemaining = 150;
        }
        swkbdClose(&kbd);
    }
#else
    // Desktop simulator
    if (m_catalogSearchQuery.empty()) {
        m_catalogSearchQuery = "Mario";
    } else {
        m_catalogSearchQuery.clear();
    }
    rebuildCatalogFilter();
    m_statusNotification = "Desktop test: " + m_catalogSearchQuery;
    m_notificationFramesRemaining = 120;
#endif
}



// ----------------- Feature 1: Favorites System -----------------

void App::loadFavorites() {
    m_favoriteKeys.clear();
    std::string favFile = m_platform->getAppDirectory() + "/favorites.json";
    std::error_code ec;
    if (!std::filesystem::exists(favFile, ec)) return;

    std::ifstream ifs(favFile);
    if (!ifs.is_open()) return;

    try {
        nlohmann::json j;
        ifs >> j;
        if (j.contains("keys") && j["keys"].is_array()) {
            for (const auto& k : j["keys"]) {
                if (k.is_string()) {
                    m_favoriteKeys.insert(k.get<std::string>());
                }
            }
        }
    } catch (...) {}
}

void App::saveFavorites() {
    nlohmann::json j;
    j["version"] = 1;
    j["keys"] = nlohmann::json::array();
    for (const auto& k : m_favoriteKeys) {
        j["keys"].push_back(k);
    }

    std::string appDir = m_platform->getAppDirectory();
    std::string targetFile = appDir + "/favorites.json";
    std::string tmpFile = targetFile + ".tmp";

    std::error_code ec;
    std::filesystem::create_directories(appDir, ec);

    std::ofstream ofs(tmpFile);
    if (ofs.is_open()) {
        ofs << j.dump(2);
        ofs.flush();
        ofs.close();
        std::filesystem::rename(tmpFile, targetFile, ec);
    }
}

bool App::isVariantFavorite(const std::string& titleId, const std::string& variantId) const {
    if (variantId.empty()) return false;
    if (!titleId.empty() && m_favoriteKeys.count(titleId + ":" + variantId) > 0) return true;
    if (m_favoriteKeys.count(variantId) > 0) return true;
    return false;
}

void App::toggleFavoriteVariant(const std::string& titleId, const Variant& variant) {
    if (variant.id.empty()) return;
    std::string key = (!titleId.empty() ? (titleId + ":" + variant.id) : variant.id);
    bool currentlyFav = isVariantFavorite(titleId, variant.id);

    if (currentlyFav) {
        m_favoriteKeys.erase(key);
        m_favoriteKeys.erase(variant.id);
        if (!titleId.empty()) m_favoriteKeys.erase(titleId + ":" + variant.id);
        m_statusNotification = "Удалено из избранного: " + variant.name;
    } else {
        m_favoriteKeys.insert(key);
        m_statusNotification = "Добавлено в избранное: " + variant.name;
    }
    m_notificationFramesRemaining = 90;
    saveFavorites();

    if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
        rebuildCatalogFilter();
    }
}

bool App::hasGameFavorites(const std::string& titleId) const {
    const auto* entry = m_catalogManager.findByTitleId(titleId);
    
    if (entry) {
        for (const auto& v : entry->variants) {
            if (isVariantFavorite(titleId, v.id)) return true;
        }
    }
    for (const auto& ig : m_installedGames) {
        if (ig.titleId == titleId) {
            for (const auto& v : ig.catalogEntry.variants) {
                if (isVariantFavorite(titleId, v.id)) return true;
            }
            break;
        }
    }
    return false;
}

// ----------------- Feature 6: Storage & Cache Manager -----------------

void App::refreshStorageStats() {
    m_sysInfo = m_platform->getSystemInfo();
    m_storageStats.totalSdBytes = m_sysInfo.totalStorageBytes;
    m_storageStats.freeSdBytes = m_sysInfo.freeStorageBytes;

    // Installed covers (*.mp4 in coversDir)
    std::string covDir = m_platform->getCoversDirectory();
    m_storageStats.coversCount = 0;
    m_storageStats.coversBytes = 0;
    std::error_code ec;
    if (std::filesystem::exists(covDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(covDir, ec)) {
            if (entry.is_regular_file(ec) && entry.path().extension() == ".mp4") {
                m_storageStats.coversCount++;
                m_storageStats.coversBytes += entry.file_size(ec);
            }
        }
    }

    // Installed 4IFIR video icons (*.mp4 in iconsDir)
    std::string icoDir = m_platform->getIconsDirectory();
    m_storageStats.iconsCount = 0;
    m_storageStats.iconsBytes = 0;
    if (std::filesystem::exists(icoDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(icoDir, ec)) {
            if (entry.is_regular_file(ec) && entry.path().extension() == ".mp4") {
                m_storageStats.iconsCount++;
                m_storageStats.iconsBytes += entry.file_size(ec);
            }
        }
    }

    // Cache folder (thumbs/*.jpg and thumbs/*.mp4)
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    m_storageStats.thumbsCount = 0;
    m_storageStats.thumbsBytes = 0;
    m_storageStats.vidCacheCount = 0;
    m_storageStats.vidCacheBytes = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".jpg" || ext == ".png") {
                    m_storageStats.thumbsCount++;
                    m_storageStats.thumbsBytes += entry.file_size(ec);
                } else if (ext == ".mp4" || ext == ".tmp") {
                    m_storageStats.vidCacheCount++;
                    m_storageStats.vidCacheBytes += entry.file_size(ec);
                }
            }
        }
    }
}

void App::clearThumbnailCache() {
    clearRowThumbTextures();
#ifdef HAS_SDL2
    if (m_videoIconDockTexture) {
        SDL_DestroyTexture(m_videoIconDockTexture);
        m_videoIconDockTexture = nullptr;
    }
#endif
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    int deleted = 0;
    uint64_t freed = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".jpg" || ext == ".png") {
                    freed += entry.file_size(ec);
                    std::filesystem::remove(entry.path(), ec);
                    deleted++;
                }
            }
        }
    }
    refreshStorageStats();
    double freedMb = static_cast<double>(freed) / (1024.0 * 1024.0);
    char buf[128];
    snprintf(buf, sizeof(buf), "Очищен кэш превью: %d файлов (%.1f MB)", deleted, freedMb);
    m_statusNotification = buf;
    m_notificationFramesRemaining = 120;
}

void App::clearVideoPreviewCache() {
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    int deleted = 0;
    uint64_t freed = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".mp4" || ext == ".tmp") {
                    freed += entry.file_size(ec);
                    std::filesystem::remove(entry.path(), ec);
                    deleted++;
                }
            }
        }
    }
    refreshStorageStats();
    double freedMb = static_cast<double>(freed) / (1024.0 * 1024.0);
    char buf[128];
    snprintf(buf, sizeof(buf), "Очищен кэш видео: %d файлов (%.1f MB)", deleted, freedMb);
    m_statusNotification = buf;
    m_notificationFramesRemaining = 120;
}

// ----------------- Feature 7: Batch Multi-Select Checklist -----------------

void App::toggleBatchSelection(const std::string& titleId) {
    if (titleId.empty()) return;
    if (m_batchSelectedTitleIds.count(titleId) > 0) {
        m_batchSelectedTitleIds.erase(titleId);
        m_statusNotification = "Снято выделение с игры";
    } else {
        m_batchSelectedTitleIds.insert(titleId);
        m_statusNotification = "Игра выбрана (Всего: " + std::to_string(m_batchSelectedTitleIds.size()) + " шт.)";
    }
    m_notificationFramesRemaining = 90;
}

void App::clearBatchSelection() {
    m_batchSelectedTitleIds.clear();
    m_statusNotification = "Пакетный выбор очищен";
    m_notificationFramesRemaining = 90;
}

void App::installBatchSelected() {
    if (m_batchSelectedTitleIds.empty()) return;
    int queuedCount = 0;

    for (const auto& tid : m_batchSelectedTitleIds) {
        const auto* entry = m_catalogManager.findByTitleId(tid);
        
        if (!entry || entry->variants.empty()) continue;

        const Variant* chosenVariant = &entry->variants[0];
        for (const auto& v : entry->variants) {
            if (isVariantFavorite(tid, v.id)) {
                chosenVariant = &v;
                break;
            }
        }

        InstalledTitle targetTitle;
        bool found = false;
        for (const auto& ig : m_installedGames) {
            if (ig.titleId == tid) {
                targetTitle = ig;
                found = true;
                break;
            }
        }
        if (!found) {
            targetTitle.titleId = tid;
            targetTitle.name = entry->title;
            targetTitle.hasCatalogMatch = true;
            targetTitle.catalogEntry = *entry;
        }

        bool alreadyInQueue = false;
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            for (const auto& t : m_downloadQueue) {
                if (t.titleId == tid && t.state != TaskState::Failed && t.state != TaskState::Completed) {
                    alreadyInQueue = true;
                    break;
                }
            }
        }

        if (!alreadyInQueue) {
            bool isPureIcon = (chosenVariant->id.rfind("icon-", 0) == 0) ||
                              (chosenVariant->width == 256 && chosenVariant->height == 256);
            if (isPureIcon) {
                queueDownloadIconOnly(targetTitle, *chosenVariant);
            } else {
                queueDownload(targetTitle, *chosenVariant);
            }
            queuedCount++;
        }
    }

    m_batchSelectedTitleIds.clear();
    m_activeTab = Tab::Downloads;
    m_statusNotification = "Добавлено в очередь загрузки: " + std::to_string(queuedCount) + " игр";
    m_notificationFramesRemaining = 150;
}


void App::handleTouchTap(int mx, int my) {
// If dialog is open, handle direct taps on dialog buttons
            if (m_activeDialog != DialogType::None) {
                int dw = 700;
                int dh = 270;
                int dx = (Theme::SCREEN_WIDTH - dw) / 2;
                int dy = (Theme::SCREEN_HEIGHT - dh) / 2;
                int btnY = dy + 190;

                if (m_activeDialog == DialogType::MessageAlert || m_activeDialog == DialogType::IntegrityCheckResult) {
                    if (mx >= dx + 260 && mx <= dx + 440 && my >= dy + 190 && my <= dy + 240) {
                        m_activeDialog = DialogType::None;
                    } else if (mx < dx || mx > dx + dw || my < dy || my > dy + dh) {
                        m_activeDialog = DialogType::None;
                    }
                } else if (m_activeDialog == DialogType::UpdateSuccess) {
                    if (mx >= dx + 240 && mx <= dx + 460 && my >= dy + 190 && my <= dy + 245) {
                        onButtonPress(0 /* A - Restart */);
                    }
                } else {
                    bool isInstallWithIcon = (m_activeDialog == DialogType::ConfirmInstall && m_pendingActionVariant.hasIcon);
                    bool isDeleteBoth = false;
                    if (m_activeDialog == DialogType::ConfirmDelete) {
                        for (const auto& g : m_installedGames) {
                            if (g.titleId == m_pendingActionTitleId) {
                                if (g.hasInstalledCover && g.hasInstalledIcon) { isDeleteBoth = true; }
                                break;
                            }
                        }
                    }

                    if (isInstallWithIcon || isDeleteBoth) {
                        if (my >= btnY && my <= btnY + 46) {
                            if (mx >= dx + 25 && mx <= dx + 180) {
                                m_dialogFocus = 0;
                                onButtonPress(0 /* A - Option 1 */);
                            } else if (mx >= dx + 190 && mx <= dx + 340) {
                                m_dialogFocus = 1;
                                onButtonPress(0 /* A - Option 2 */);
                            } else if (mx >= dx + 350 && mx <= dx + 500) {
                                m_dialogFocus = 2;
                                onButtonPress(0 /* A - Option 3 */);
                            } else if (mx >= dx + 510 && mx <= dx + 665) {
                                m_activeDialog = DialogType::None;
                            }
                        } else if (mx < dx || mx > dx + dw || my < dy || my > dy + dh) {
                            m_activeDialog = DialogType::None;
                        }
                    } else {
                        if (my >= btnY && my <= btnY + 46 && mx >= dx + 120 && mx <= dx + 320) {
                            m_dialogFocus = 0;
                            onButtonPress(0 /* A - Confirm */);
                        } else if (my >= btnY && my <= btnY + 46 && mx >= dx + 380 && mx <= dx + 580) {
                            m_dialogFocus = 1;
                            onButtonPress(1 /* B - Cancel */);
                        } else if (mx < dx || mx > dx + dw || my < dy || my > dy + dh) {
                            m_activeDialog = DialogType::None;
                        }
                    }
                }
                return;
            }

            // If Unified Glass Action Sheet [X] is open, handle touch taps on items or outside to close
            if (m_isActionSheetOpen) {
                int sx = 790, sy = 72, sw = 460, sh = 576;
                if (mx < sx || mx > sx + sw || my < sy || my > sy + sh) {
                    closeActionSheet();
                } else {
                    int itemStartY = 156;
                    int itemStep = 50;
                    if (my >= itemStartY && mx >= sx + 18 && mx <= sx + sw - 18) {
                        int clickedIdx = (my - itemStartY) / itemStep;
                        if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_actionSheetItems.size())) {
                            m_actionSheetSelectedIndex = clickedIdx;
                            executeActionSheetSelection();
                        }
                    }
                }
                return;
            }

            // If Fullscreen Preview is active, handle touch HUD buttons and swipe/taps
            if (m_isFullscreenPreview) {
                int hudX = 40;
                int hudY = 585;
                if (mx >= hudX + 900 && mx <= hudX + 1170 && my >= hudY + 14 && my <= hudY + 52) {
                    onButtonPress(0 /* A - Install / Save */);
                } else if (!m_previewIsIconSquare && mx >= hudX + 555 && mx <= hudX + 715 && my >= hudY + 14 && my <= hudY + 52) {
                    onButtonPress(16 /* ZR - Toggle Switch Home HUD Overlay */);
                } else if (mx >= hudX + 725 && mx <= hudX + 890 && my >= hudY + 14 && my <= hudY + 52) {
                    onButtonPress(10 /* R - Toggle 16:9 Cover vs 256x256 Icon Preview */);
                } else if (mx >= hudX + 660 && mx <= hudX + 805 && my >= hudY + 55 && my <= hudY + 95) {
                    onButtonPress(9 /* L - Favorite */);
                } else if (mx >= hudX + 810 && mx <= hudX + 965 && my >= hudY + 55 && my <= hudY + 95) {
                    onButtonPress(3 /* Y - Assign */);
                } else if (mx >= hudX + 1090 && mx <= hudX + 1190 && my >= hudY + 55 && my <= hudY + 95) {
                    closeFullscreenPreview();
                } else if (mx <= 120 && my >= 200 && my <= 520) {
                    onButtonPress(13 /* DPAD_LEFT - Prev */);
                } else if (mx >= 1160 && my >= 200 && my <= 520) {
                    onButtonPress(14 /* DPAD_RIGHT - Next */);
                } else {
                    closeFullscreenPreview();
                }
                return;
            }

            // If Game Picker Modal is open, handle touch navigation and selection
            if (m_isGamePickerOpen) {
                int bw = 1140, bh = 600;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeGamePicker();
                } else if (my >= by + 95 && my <= by + 95 + 5 * 88) {
                    int clickedIdx = m_gamePickerScrollOffset + (my - (by + 95)) / 88;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_installedGames.size())) {
                        m_gamePickerSelectedIndex = clickedIdx;
                        onButtonPress(0 /* A - Select Game */);
                    }
                }
                return;
            }

            // If Recordings Browser Modal is open, handle touch
            if (m_isRecordingsBrowserOpen) {
                int bw = 1140, bh = 600;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeRecordingsBrowser();
                } else if (my >= by + 95 && my <= by + 95 + 5 * 88) {
                    int clickedIdx = m_recordingsScrollOffset + (my - (by + 95)) / 88;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_localRecordings.size())) {
                        m_recordingsSelectedIndex = clickedIdx;
                        onButtonPress(0 /* A - Install */);
                    }
                }
                return;
            }

            // If Collection Browser Modal is open, handle touch
            if (m_isCollectionBrowserOpen) {
                int bw = 1220, bh = 660;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeCollectionBrowser();
                } else {
                    int lx = bx + 25, ly = by + 68, lw = 635;
                    // Left Column: tapping variant item
                    if (mx >= lx && mx <= lx + lw && my >= ly && my <= ly + 5 * 96) {
                        int clickedIdx = m_collectionScrollOffset + (my - ly) / 96;
                        if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_collectionVariants.size())) {
                            m_collectionSelectedIndex = clickedIdx;
                            // Tapping directly on the ИКОНКА badge (x in [lx+200, lx+310], lower half of row) activates Icon preview mode!
                            int relY = (my - ly) % 96;
                            if (mx >= lx + 200 && mx <= lx + 315 && relY >= 42 && m_collectionVariants[clickedIdx].hasIcon) {
                                m_collectionPreviewIconMode = true;
                            }
                            m_cancelCollectionThumb.store(true);
                            m_videoPlayer.close();
                            m_collectionPreviewDirty = true;
                            m_lastCollectionMoveTime = SDL_GetTicks() - 200;
                        }
                    } else {
                        int rx = bx + 675, ry = by + 68;
                        int px = rx + 20, py = ry + 20, pw = 480, ph = 270;
                        int b1y = py + ph + 76;
                        int b3y = b1y + 48;

                        // Tap top-right [Фон 16:9] | [R] Иконка 1:1 toggle inside preview box
                        if (mx >= px + pw - 250 && mx <= px + pw && my >= py && my <= py + 38) {
                            onButtonPress(10 /* R - Toggle Cover/Icon Preview */);
                        }
                        // Tap preview thumbnail -> open fullscreen live video
                        else if (mx >= px && mx <= px + pw && my >= py && my <= py + ph) {
                            onButtonPress(2 /* X - Video */);
                        }
                        // Button [A] Установить сразу (Direct install for this game)
                        else if (mx >= px && mx <= px + 232 && my >= b1y && my <= b1y + 40) {
                            onButtonPress(0 /* A - Direct Install */);
                        }
                        // Button [X] Видео в полный экран
                        else if (mx >= px + 248 && mx <= px + 480 && my >= b1y && my <= b1y + 40) {
                            onButtonPress(2 /* X - Video */);
                        }
                        // Button [Y] На другую игру (Game Picker)
                        else if (mx >= px && mx <= px + 232 && my >= b3y && my <= b3y + 36) {
                            onButtonPress(3 /* Y - Pick Another Game */);
                        }
                        // Button [L / R3] В избранное
                        else if (mx >= px + 248 && mx <= px + 480 && my >= b3y && my <= b3y + 36) {
                            onButtonPress(9 /* L - Favorite */);
                        }
                    }
                }
                return;
            }

            // Global Top Header Bar: [L] 6 Tabs [R] + [+] OTA (y in [8, 56])
            if (my >= 8 && my <= 56) {
                if (mx >= 305 && mx <= 336) {
                    switchGlobalTab(-1);
                    return;
                } else if (mx >= 338 && mx <= 850) {
                    int ti = (mx - 338) / 86;
                    if (ti >= 0 && ti <= 5 && static_cast<Tab>(ti) != m_activeTab) {
                        if (m_activeTab == Tab::VideoIcons || m_activeTab == Tab::Catalog) {
                            m_videoPlayer.close();
                            m_videoIconDockDirty = false;
                            m_catalogDockDirty = false;
                            m_collectionTransferQueued = false;
                            m_cancelCollectionThumb.store(true);
                        }
                        m_activeTab = static_cast<Tab>(ti);
                        if (ti >= 1 && ti <= 5) m_homeFocusedTile = ti - 1;
                        if (m_activeTab == Tab::VideoIcons) {
                            rebuildVideoIconsFilter();
                            m_videoIconDockDirty = true;
                            m_lastVideoIconMoveTime = SDL_GetTicks();
                        } else if (m_activeTab == Tab::MyGames) {
                            rebuildMyGamesFilter();
                        } else if (m_activeTab == Tab::Catalog) {
                            if (m_filteredCatalogGames.empty() && m_catalogSearchQuery.empty()) {
                                rebuildCatalogFilter();
                            }
                            m_catalogDockDirty = true;
                            m_catalogDockCurrentKey.clear();
                            m_lastCatalogMoveTime = SDL_GetTicks();
                        }
                        m_tabTransitionAlpha = 140.0f;
                    }
                    return;
                } else if (mx >= 852 && mx <= 886) {
                    switchGlobalTab(1);
                    return;
                } else if (mx >= 1130 && mx <= 1255) {
                    onButtonPress(6 /* + OTA Update */);
                    return;
                }
            }

            // Home Tab: Upper Panorama + Interactive Console Radar (y in [78, 372], x in [40, 1240])
            if (m_activeTab == Tab::Home && my >= 78 && my <= 372 && mx >= 40 && mx <= 1240) {
                // Button [-] Quick Batch Action (x in [320, 648], y in [300, 355])
                if (mx >= 320 && mx <= 648 && my >= 300 && my <= 355) {
                    onButtonPress(4 /* Minus - Smart Batch Action */);
                }
                // Right Interactive Console Panel tap (x in [698, 1214], y in [134, 352])
                else if (mx >= 698 && mx <= 1214 && my >= 134 && my <= 352) {
                    int rowHit = (my - 138) / 52;
                    if ((m_homeFocusedTile == 0 || m_homeFocusedTile == 2) && rowHit >= 0 && rowHit < 4) {
                        std::vector<int> radarIdx;
                        for (int idx = 0; idx < static_cast<int>(m_installedGames.size()); ++idx) {
                            const auto& g = m_installedGames[idx];
                            if (g.titleId.empty() || g.titleId == "0000000000000000") continue;
                            if (!g.hasInstalledCover && g.hasCatalogMatch && !g.catalogEntry.variants.empty()) radarIdx.push_back(idx);
                        }
                        for (int idx = 0; idx < static_cast<int>(m_installedGames.size()) && radarIdx.size() < 4; ++idx) {
                            const auto& g = m_installedGames[idx];
                            if (g.titleId.empty() || g.titleId == "0000000000000000") continue;
                            if (g.hasInstalledCover && !g.hasInstalledIcon && g.hasCatalogMatch && !getUniqueIconVariants(g.catalogEntry).empty()) {
                                if (std::find(radarIdx.begin(), radarIdx.end(), idx) == radarIdx.end()) radarIdx.push_back(idx);
                            }
                        }
                        for (int idx = 0; idx < static_cast<int>(m_installedGames.size()) && radarIdx.size() < 4; ++idx) {
                            const auto& g = m_installedGames[idx];
                            if (g.titleId.empty() || g.titleId == "0000000000000000") continue;
                            if (std::find(radarIdx.begin(), radarIdx.end(), idx) == radarIdx.end()) radarIdx.push_back(idx);
                        }
                        if (rowHit < static_cast<int>(radarIdx.size())) {
                            const auto& targetG = m_installedGames[radarIdx[rowHit]];
                            if (mx >= 1075 && !targetG.hasInstalledCover && targetG.hasCatalogMatch) {
                                queueComboPack(targetG, targetG.catalogEntry, 0);
                                m_activeTab = Tab::Downloads;
                                m_homeFocusedTile = 3;
                            } else if (mx >= 1075 && !targetG.hasInstalledIcon && targetG.hasCatalogMatch && !getUniqueIconVariants(targetG.catalogEntry).empty()) {
                                auto uIco = getUniqueIconVariants(targetG.catalogEntry);
                                queueDownloadIconOnly(targetG, uIco[0]);
                                m_statusNotification = tr("HQ-иконка добавлена в загрузки: ", "Queued HQ icon: ") + targetG.name;
                                m_notificationFramesRemaining = 140;
                            } else if (!targetG.hasCatalogMatch) {
                                startForwarderLinkSearch(targetG);
                            } else {
                                m_myGamesFilterMode = 0;
                                m_myGamesSearchQuery.clear();
                                rebuildMyGamesFilter();
                                for (size_t fi = 0; fi < m_filteredMyGamesIndices.size(); ++fi) {
                                    if (m_filteredMyGamesIndices[fi] == radarIdx[rowHit]) {
                                        m_myGamesSelectedIndex = static_cast<int>(fi);
                                        break;
                                    }
                                }
                                m_activeTab = Tab::MyGames;
                                m_homeFocusedTile = 2;
                            }
                        } else {
                            onButtonPress(0);
                        }
                    } else if (m_homeFocusedTile == 1) {
                        onButtonPress(0 /* A - Open Video Icons */);
                    } else if (m_homeFocusedTile == 4 && my >= 295) {
                        onButtonPress(4 /* Minus - Toggle Auto-Rotate */);
                    } else {
                        onButtonPress(0 /* A - Open focused section */);
                    }
                } else {
                    onButtonPress(0 /* A - Open focused section */);
                }
            }
            // Home Tab: Bottom 5x Cyber-Dock Cards (y in [388, 638], x in [35, 1245])
            else if (m_activeTab == Tab::Home && my >= 388 && my <= 638 && mx >= 35 && mx <= 1245) {
                int tileW = 228, tileGap = 15;
                int totalRowW = 5 * tileW + 4 * tileGap;
                int tileStartX = (Theme::SCREEN_WIDTH - totalRowW) / 2;
                int clickedTile = (mx - tileStartX) / (tileW + tileGap);
                if (clickedTile >= 0 && clickedTile <= 4) {
                    if (m_homeFocusedTile == clickedTile) {
                        onButtonPress(0 /* A - Activate selected tile */);
                    } else {
                        m_homeFocusedTile = clickedTile;
                    }
                }
            }
            // VideoIcons Tab: Search Bar click (x in [280, 910], y in [82, 120])
            else if (m_activeTab == Tab::VideoIcons && mx >= 280 && mx <= 910 && my >= 82 && my <= 120) {
                onButtonPress(3 /* Y - Open VideoIcons Search Keyboard */);
            }
            // VideoIcons Tab: Filter Pill click (x in [925, 1230], y in [82, 120])
            else if (m_activeTab == Tab::VideoIcons && mx >= 925 && mx <= 1230 && my >= 82 && my <= 120) {
                onButtonPress(4 /* Minus - Toggle Filter */);
            }
            // VideoIcons Tab: Left Split-Screen Item rows click (x in [45, 805], y in [136, 616])
            else if (m_activeTab == Tab::VideoIcons && mx >= 45 && mx <= 805 && my >= 136 && my <= 616) {
                int clickedIdx = m_videoIconsScrollOffset + (my - 136) / 98;
                if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_filteredVideoIcons.size())) {
                    bool wasSelected = (m_videoIconsSelectedIndex == clickedIdx);
                    m_videoIconsSelectedIndex = clickedIdx;
                    m_videoIconDockDirty = true;
                    m_lastVideoIconMoveTime = SDL_GetTicks() - 200;
                    // Tap on < ◄ Вар. X/Y ► > pill (x in [295, 470]) -> cycle variant
                    if (mx >= 295 && mx <= 470 && m_filteredVideoIcons[clickedIdx].variants.size() > 1) {
                        onButtonPress(14 /* DPAD_RIGHT - Next icon variant */);
                    }
                    // Tap on [A] Установить / АКТИВНА button (x in [645, 800])
                    else if (mx >= 645 && mx <= 800) {
                        if (isIconInstalled(m_filteredVideoIcons[clickedIdx].titleId)) {
                            openActionSheetForCurrentContext();
                        } else {
                            onButtonPress(0 /* A - Install */);
                        }
                    } else if (wasSelected) {
                        openFullscreenVideoIconPreview(m_filteredVideoIcons[clickedIdx], getSelectedVideoIconVariantIndex(m_filteredVideoIcons[clickedIdx]));
                    }
                }
            }
            // VideoIcons Tab: Right Split-Screen Live Switch Icon Dock (x in [818, 1232], y in [136, 616])
            else if (m_activeTab == Tab::VideoIcons && mx >= 818 && mx <= 1232 && my >= 136 && my <= 616) {
                int dockX = 818, dockY = 136, dockW = 414, dockH = 480;
                int bY = dockY + dockH - 52;
                // Tap on 256x256 live tile -> Fullscreen preview
                if (my >= dockY + 50 && my <= dockY + 315 && !m_filteredVideoIcons.empty()) {
                    const auto& selE = m_filteredVideoIcons[std::clamp(m_videoIconsSelectedIndex, 0, static_cast<int>(m_filteredVideoIcons.size()) - 1)];
                    openFullscreenVideoIconPreview(selE, getSelectedVideoIconVariantIndex(selE));
                }
                // Tap on variant switcher pill in dock (y in [504, 542])
                else if (my >= dockY + 365 && my <= dockY + 405) {
                    if (mx < dockX + dockW / 2) onButtonPress(13 /* DPAD_LEFT */);
                    else onButtonPress(14 /* DPAD_RIGHT */);
                }
                // Tap on [X] Действия ▾ button in dock
                else if (my >= bY && my <= bY + 40 && mx >= dockX + 18 && mx <= dockX + 200) {
                    onButtonPress(2 /* X - Action Sheet */);
                }
                // Tap on [A] Установить button in dock
                else if (my >= bY && my <= bY + 40 && mx >= dockX + 214 && mx <= dockX + 396) {
                    onButtonPress(0 /* A - Install */);
                }
            }
            // Catalog Tab: Filter Chips [-], Search Bar [Y], Forwarder Banner, and Game Rows
            else if (m_activeTab == Tab::Catalog) {
                // Idea 6: Clickable Filter Chips Strip (x in [46, 758], y in [78, 120])
                if (mx >= 46 && mx <= 758 && my >= 78 && my <= 120) {
                    if (mx < 80) {
                        cycleCatalogSortMode();
                    } else {
                        struct ChipHit {
                            CatalogSortMode mode;
                            const char* ru;
                            const char* en;
                        };
                        const ChipHit chips[7] = {
                            {CatalogSortMode::Default,       "Все",         "All"},
                            {CatalogSortMode::InstalledOnly, "На консоли",  "Installed"},
                            {CatalogSortMode::IconsOnly,     "256x256",     "256x256"},
                            {CatalogSortMode::AudioOnly,     "Звук ♪",      "Audio ♪"},
                            {CatalogSortMode::Fps60Only,     "60 FPS",      "60 FPS"},
                            {CatalogSortMode::FavoritesOnly, "Избр. ★",     "Fav ★"},
                            {CatalogSortMode::Alphabetical,  "А–Я",         "A–Z"}
                        };
                        int chipX = 80;
                        bool matchedChip = false;
                        for (int ci = 0; ci < 7; ++ci) {
                            const char* clbl = (m_language == Language::English) ? chips[ci].en : chips[ci].ru;
                            int cw = measureTextWidth(clbl, 11) + 20;
                            if (mx >= chipX && mx <= chipX + cw + 4) {
                                m_catalogSortMode = chips[ci].mode;
                                rebuildCatalogFilter();
                                matchedChip = true;
                                break;
                            }
                            chipX += cw + 6;
                        }
                        if (!matchedChip) {
                            cycleCatalogSortMode();
                        }
                    }
                }
                // Search Bar [Y] on the right (x in [765, 1235], y in [78, 120])
                else if (mx >= 765 && mx <= 1235 && my >= 78 && my <= 120) {
                    onButtonPress(3 /* Y - Open Search Keyboard */);
                }
                // Forwarder Linking Banner tap -> cancel if tapped on right edge
                else if (!m_linkingTargetTitleId.empty() && my >= 122 && my <= 153 && mx >= 980 && mx <= 1230) {
                    cancelForwarderLinkMode();
                }
                // Empty Favorites Reset Pill
                else if (m_filteredCatalogGames.empty() && m_catalogSortMode == CatalogSortMode::FavoritesOnly &&
                         mx >= 540 && mx <= 740 && my >= 375 && my <= 420) {
                    m_catalogSortMode = CatalogSortMode::Default;
                    rebuildCatalogFilter();
                }
                // Click on Left Split-Studio Game Row or Right Live Combo Stage
                else {
                    int yBase = m_linkingTargetTitleId.empty() ? 134 : 158;
                    int totalGames = static_cast<int>(m_filteredCatalogGames.size());
                    // Left Column rows (x in [44, 786])
                    if (mx >= 44 && mx <= 786 && my >= yBase && my <= 630) {
                        int clickedIdx = m_catalogScrollOffset + (my - yBase) / 96;
                        if (clickedIdx >= 0 && clickedIdx < totalGames) {
                            bool wasSelected = (m_catalogSelectedIndex == clickedIdx);
                            m_catalogSelectedIndex = clickedIdx;
                            if (!wasSelected) {
                                m_catalogDockDirty = true;
                                m_catalogDockCurrentKey.clear();
                                m_lastCatalogMoveTime = SDL_GetTicks() - 90;
                            } else {
                                onButtonPress(0 /* A - Open Collection / Bind */);
                            }
                        }
                    }
                    // Right Column Live Combo Stage (x in [798, 1236], y in [yBase, 634])
                    else if (mx >= 798 && mx <= 1236 && my >= yBase && my <= 634 && totalGames > 0) {
                        int stX = 798;
                        int stY = yBase;
                        int stW = 436;
                        int stH = m_linkingTargetTitleId.empty() ? 498 : 474;
                        int pvY = stY + 36;
                        int swY = pvY + 225 + 12 + 48;
                        int btnY = stY + stH - 52;
                        const auto& selG = m_filteredCatalogGames[std::clamp(m_catalogSelectedIndex, 0, totalGames - 1)];

                        // Tap on overlaid 256x256 icon square in bottom-right of 16:9 stage -> Icon Fullscreen Preview
                        if (mx >= stX + 18 + 400 - 94 && mx <= stX + 18 + 400 && my >= pvY + 225 - 94 && my <= pvY + 225 &&
                            !getUniqueIconVariants(selG).empty()) {
                            openFullscreenVideoIconPreview(selG, 0);
                        }
                        // Tap on 16:9 Live Preview Window -> Fullscreen Cover Preview
                        else if (my >= pvY && my <= pvY + 225) {
                            openFullscreenPreviewForCatalogGame(selG, getSelectedCatalogVariantIndex(selG));
                        }
                        // Tap on Variant Switcher Pill < ◄ [Влево / Вправо] ► >
                        else if (my >= swY - 4 && my <= swY + 32) {
                            if (mx < stX + stW / 2) onButtonPress(13 /* DPAD_LEFT */);
                            else onButtonPress(14 /* DPAD_RIGHT */);
                        }
                        // Tap on [X] Действия / Комбо ▾ button
                        else if (my >= btnY && my <= btnY + 42 && mx >= stX + 16 && mx <= stX + 212) {
                            onButtonPress(2 /* X - Open Action Sheet */);
                        }
                        // Tap on [A] Все варианты / Привязать button
                        else if (my >= btnY && my <= btnY + 42 && mx >= stX + 222 && mx <= stX + 422) {
                            onButtonPress(0 /* A - Open Collection / Bind */);
                        }
                    }
                }
            }
            else if (m_activeTab == Tab::MyGames) {
                if (m_filteredMyGamesIndices.empty() && m_myGamesFilterMode == 0 && m_myGamesSearchQuery.empty() && !m_installedGames.empty()) {
                    rebuildMyGamesFilter();
                }
                // Left Pane Top: Search [Y] (x in [35, 266]) & Filter [-] (x in [268, 408]) at y in [82, 118]
                if (my >= 82 && my <= 118 && mx >= 35 && mx <= 266) {
                    openMyGamesKeyboard();
                }
                else if (my >= 82 && my <= 118 && mx >= 268 && mx <= 408) {
                    onButtonPress(4 /* Minus - Cycle MyGames Filter */);
                }
                // Left Column: Games list item selection (x in [30, 480], y in [122, 588])
                else if (mx >= 30 && mx <= 480 && my >= 122 && my <= 588) {
                    int clickedIdx = m_myGamesScrollOffset + (my - 122) / 66;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_filteredMyGamesIndices.size())) {
                        if (m_myGamesSelectedIndex == clickedIdx) {
                            onButtonPress(0 /* A - Focus Variants or Forwarder Link Search */);
                        } else {
                            m_myGamesSelectedIndex = clickedIdx;
                            m_selectedVariantIndex = 0;
                            m_variantScrollOffset = 0;
                            m_myGamesActivePane = MyGamesPane::GamesList;
                        }
                    }
                }
                // Right Column Top-Right: [X] Действия ▾ Button (x in [1050, 1230], y in [98, 148])
                else if (mx >= 1050 && mx <= 1230 && my >= 98 && my <= 148) {
                    openActionSheetForCurrentContext();
                }
                // Right Column Slot Strip (y in [190, 230], x in [530, 1228])
                else if (my >= 190 && my <= 230 && mx >= 530 && mx <= 1228) {
                    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_filteredMyGamesIndices.size())) {
                        const auto& selGame = m_installedGames[m_filteredMyGamesIndices[m_myGamesSelectedIndex]];
                        std::string sdClipLbl = tr("[L3] Записи SD", "[L3] SD Clips");
                        int sdW = measureTextWidth(sdClipLbl, 11) + 18;
                        if (mx >= 1225 - sdW) {
                            openRecordingsBrowser(selGame.titleId, selGame.name);
                        } else {
                            int slotX = 530;
                            bool hitSlot = false;
                            int maxDrawSlots = std::min(4, selGame.installedCoversCount);
                            for (int sIdx = 0; sIdx < maxDrawSlots; ++sIdx) {
                                const auto& scv = selGame.installedCoverVariants[sIdx];
                                std::string sLabel = scv.isActive
                                    ? (tr("★ Слот #1: Активен", "★ Slot #1: Active"))
                                    : (tr("Слот #", "Slot #") + std::to_string(scv.index + 1));
                                int sw = measureTextWidth(sLabel, 11) + 22;
                                if (mx >= slotX && mx <= slotX + sw) {
                                    if (!scv.isActive) {
                                        executeActivateCoverSlot(selGame.titleId, scv.index);
                                    } else if (selGame.installedCoversCount > 1) {
                                        executeCycleNextCover(selGame.titleId);
                                    }
                                    hitSlot = true;
                                    break;
                                }
                                slotX += sw + 8;
                            }
                            if (!hitSlot) {
                                openActionSheetForCurrentContext();
                            }
                        }
                    }
                }
                // Right Column Variant Cards or Forwarder Link Card (y in [276, 608])
                else if (mx >= 525 && mx <= 1225 && my >= 276 && my <= 608) {
                    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_filteredMyGamesIndices.size())) {
                        const auto& selGame = m_installedGames[m_filteredMyGamesIndices[m_myGamesSelectedIndex]];
                        int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                        if (totalV > 0) {
                            int vClicked = m_variantScrollOffset + (my - 276) / 82;
                            if (vClicked >= 0 && vClicked < totalV) {
                                m_selectedVariantIndex = vClicked;
                                m_myGamesActivePane = MyGamesPane::VariantsList;
                                const auto& vChosen = selGame.catalogEntry.variants[vClicked];
                                if (vChosen.hasIcon) {
                                    if (mx >= 980 && mx < 1110) {
                                        queueDownload(selGame, vChosen);
                                    } else if (mx >= 1110 && mx <= 1220) {
                                        queueDownloadIconOnly(selGame, vChosen);
                                    } else {
                                        openFullscreenPreviewForGame(selGame, vClicked);
                                    }
                                } else {
                                    if (mx >= 1000 && mx <= 1220) {
                                        queueDownload(selGame, vChosen);
                                    } else {
                                        openFullscreenPreviewForGame(selGame, vClicked);
                                    }
                                }
                            }
                        } else {
                            // Idea 2: Forwarder Link Button at x in [550, 1020], y in [392, 450]
                            if (mx >= 540 && mx <= 1030 && my >= 286 && my <= 466) {
                                startForwarderLinkSearch(selGame);
                            }
                        }
                    }
                }
            }
            // Downloads Tab: interactive touch controls
            else if (m_activeTab == Tab::Downloads) {
                // Tapping directly on a download row selects it, or retries/removes if already selected: y in [160, 640]
                if (my >= 160 && my <= 640 && mx >= 60 && mx <= 1220) {
                    int clickedIdx = m_downloadsScrollOffset + (my - 160) / 94;
                    std::lock_guard<std::mutex> lock(m_queueMutex);
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_downloadQueue.size())) {
                        m_downloadsSelectedIndex = clickedIdx;
                        if (m_downloadQueue[clickedIdx].state == TaskState::Failed) {
                            m_downloadQueue[clickedIdx].state = TaskState::Pending;
                            m_downloadQueue[clickedIdx].errorMessage.clear();
                            m_statusNotification = tr("Перезапуск задачи...", "Retrying task...");
                            m_notificationFramesRemaining = 90;
                        }
                    }
                }
            }
            // Settings Tab: interactive setting rows (8 rows at y = 232, step = 47)
            else if (m_activeTab == Tab::Settings && mx >= 50 && mx <= 1230 && my >= 230 && my <= 615) {
                int clickedRow = (my - 232) / 47;
                if (clickedRow >= 0 && clickedRow <= 7) {
                    m_settingsSelectedIndex = clickedRow;
                    onButtonPress(0 /* A - Activate Setting */);
                }
            }
}

void App::handleTouchDrag(int startX, int startY, int deltaY) {
    m_touchDragAccumulator += deltaY;

    // Smooth half-row threshold (48px) for natural, fluid scrolling on Switch screen
    const int scrollThreshold = 48;

    while (m_touchDragAccumulator <= -scrollThreshold) {
        // Dragging UP -> scroll DOWN
        m_touchDragAccumulator += scrollThreshold;
        if (m_isCollectionBrowserOpen) {
            if (m_collectionScrollOffset + 5 < static_cast<int>(m_collectionVariants.size())) {
                m_collectionScrollOffset++;
                if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                    m_collectionSelectedIndex = m_collectionScrollOffset;
                }
            }
        } else if (m_isGamePickerOpen) {
            if (m_gamePickerScrollOffset + 5 < static_cast<int>(m_installedGames.size())) {
                m_gamePickerScrollOffset++;
                if (m_gamePickerSelectedIndex < m_gamePickerScrollOffset) {
                    m_gamePickerSelectedIndex = m_gamePickerScrollOffset;
                }
            }
        } else if (m_isRecordingsBrowserOpen) {
            if (m_recordingsScrollOffset + 5 < static_cast<int>(m_localRecordings.size())) {
                m_recordingsScrollOffset++;
                if (m_recordingsSelectedIndex < m_recordingsScrollOffset) {
                    m_recordingsSelectedIndex = m_recordingsScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::Catalog && startY >= 130 && startY <= 670) {
            if (m_catalogScrollOffset + 5 < static_cast<int>(m_filteredCatalogGames.size())) {
                m_catalogScrollOffset++;
                if (m_catalogSelectedIndex < m_catalogScrollOffset) {
                    m_catalogSelectedIndex = m_catalogScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::VideoIcons && startY >= 130 && startY <= 670) {
            if (m_videoIconsScrollOffset + 5 < static_cast<int>(m_filteredVideoIcons.size())) {
                m_videoIconsScrollOffset++;
                if (m_videoIconsSelectedIndex < m_videoIconsScrollOffset) {
                    m_videoIconsSelectedIndex = m_videoIconsScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::Downloads && startY >= 130 && startY <= 670) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (m_downloadsScrollOffset + 5 < static_cast<int>(m_downloadQueue.size())) {
                m_downloadsScrollOffset++;
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {
            if (m_myGamesScrollOffset + 7 < static_cast<int>(m_filteredMyGamesIndices.size())) {
                m_myGamesScrollOffset++;
                if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
                    m_myGamesSelectedIndex = m_myGamesScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 500 && startX <= 1250) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_filteredMyGamesIndices.size())) {
                const auto& selGame = m_installedGames[m_filteredMyGamesIndices[m_myGamesSelectedIndex]];
                int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                if (m_variantScrollOffset + 4 < totalV) {
                    m_variantScrollOffset++;
                    if (m_selectedVariantIndex < m_variantScrollOffset) {
                        m_selectedVariantIndex = m_variantScrollOffset;
                    }
                }
            }
        }
    }

    while (m_touchDragAccumulator >= scrollThreshold) {
        // Dragging DOWN -> scroll UP
        m_touchDragAccumulator -= scrollThreshold;
        if (m_isCollectionBrowserOpen) {
            if (m_collectionScrollOffset > 0) {
                m_collectionScrollOffset--;
                if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                    m_collectionSelectedIndex = m_collectionScrollOffset + 4;
                }
            }
        } else if (m_isGamePickerOpen) {
            if (m_gamePickerScrollOffset > 0) {
                m_gamePickerScrollOffset--;
                if (m_gamePickerSelectedIndex >= m_gamePickerScrollOffset + 5) {
                    m_gamePickerSelectedIndex = m_gamePickerScrollOffset + 4;
                }
            }
        } else if (m_isRecordingsBrowserOpen) {
            if (m_recordingsScrollOffset > 0) {
                m_recordingsScrollOffset--;
                if (m_recordingsSelectedIndex >= m_recordingsScrollOffset + 5) {
                    m_recordingsSelectedIndex = m_recordingsScrollOffset + 4;
                }
            }
        } else if (m_activeTab == Tab::Catalog && startY >= 130 && startY <= 670) {
            if (m_catalogScrollOffset > 0) {
                m_catalogScrollOffset--;
                if (m_catalogSelectedIndex >= m_catalogScrollOffset + 5) {
                    m_catalogSelectedIndex = m_catalogScrollOffset + 4;
                }
            }
        } else if (m_activeTab == Tab::VideoIcons && startY >= 130 && startY <= 670) {
            if (m_videoIconsScrollOffset > 0) {
                m_videoIconsScrollOffset--;
                if (m_videoIconsSelectedIndex >= m_videoIconsScrollOffset + 5) {
                    m_videoIconsSelectedIndex = m_videoIconsScrollOffset + 4;
                }
            }
        } else if (m_activeTab == Tab::Downloads && startY >= 130 && startY <= 670) {
            if (m_downloadsScrollOffset > 0) {
                m_downloadsScrollOffset--;
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {
            if (m_myGamesScrollOffset > 0) {
                m_myGamesScrollOffset--;
                if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + 7) {
                    m_myGamesSelectedIndex = m_myGamesScrollOffset + 6;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 500 && startX <= 1250) {
            if (m_variantScrollOffset > 0) {
                m_variantScrollOffset--;
                if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                    m_selectedVariantIndex = m_variantScrollOffset + 3;
                }
            }
        }
    }
}

void App::handleTouchSwipe(int startX, int startY, int endX, int endY) {
    int diffX = endX - startX;
    int diffY = endY - startY;

    if (m_isFullscreenPreview) {
        if (diffX < -60) {
            // Swiped Left -> Next Video
            onButtonPress(14 /* DPAD_RIGHT - Next */);
        } else if (diffX > 60) {
            // Swiped Right -> Prev Video
            onButtonPress(13 /* DPAD_LEFT - Prev */);
        } else if (diffY > 80) {
            // Swiped Down -> Close Preview
            closeFullscreenPreview();
        }
    } else if (!m_isCollectionBrowserOpen && !m_isGamePickerOpen && !m_isRecordingsBrowserOpen &&
               !m_isActionSheetOpen && m_activeDialog == DialogType::None) {
        if (std::abs(diffX) > 95 && std::abs(diffX) > std::abs(diffY) * 2) {
            // Global horizontal finger swipe across sections (same as L/R)
            switchGlobalTab(diffX < 0 ? 1 : -1);
        }
    }
}

void App::drawCircle(int cx, int cy, int r, Color col, bool fill) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, col.r, col.g, col.b, col.a);
    if (fill) {
        for (int dy = -r; dy <= r; ++dy) {
            int dx = static_cast<int>(std::sqrt(std::max(0, r * r - dy * dy)));
            SDL_RenderDrawLine(m_renderer, cx - dx, cy + dy, cx + dx, cy + dy);
        }
    } else {
        int x = r;
        int y = 0;
        int err = 0;
        while (x >= y) {
            SDL_RenderDrawPoint(m_renderer, cx + x, cy + y);
            SDL_RenderDrawPoint(m_renderer, cx + y, cy + x);
            SDL_RenderDrawPoint(m_renderer, cx - y, cy + x);
            SDL_RenderDrawPoint(m_renderer, cx - x, cy + y);
            SDL_RenderDrawPoint(m_renderer, cx - x, cy - y);
            SDL_RenderDrawPoint(m_renderer, cx - y, cy - x);
            SDL_RenderDrawPoint(m_renderer, cx + y, cy - x);
            SDL_RenderDrawPoint(m_renderer, cx + x, cy - y);
            if (err <= 0) {
                y += 1;
                err += 2 * y + 1;
            }
            if (err > 0) {
                x -= 1;
                err -= 2 * x + 1;
            }
        }
    }
#else
    (void)cx; (void)cy; (void)r; (void)col; (void)fill;
#endif
}

void App::drawButtonBadge(int x, int y, const std::string& key, const std::string& label, Color badgeCol) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    int r = 11;
    int circleCx = x + 11;
    int circleCy = y + 11;

    // Dark circular badge plate
    drawCircle(circleCx, circleCy, r, {0x18, 0x22, 0x34, 0xFF}, true);
    drawCircle(circleCx, circleCy, r, badgeCol, false);

    // Centered button letter
    int kw = measureTextWidth(key, 12);
    drawText(key, circleCx - kw / 2, circleCy - 7, badgeCol, 12);

    // Label text
    drawText(label, circleCx + r + 8, y + 2, Theme::COLOR_TEXT_PRIMARY, 13);
#else
    (void)x; (void)y; (void)key; (void)label; (void)badgeCol;
#endif
}

void App::drawTileIconVector(int cx, int cy, int tileIdx, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    // 1. If high-res pre-rendered 4IFIR Cyber-Glass icon texture is loaded, render it with smooth 60 FPS scale!
    if (tileIdx >= 0 && tileIdx < 5 && m_tabIconTextures[tileIdx]) {
        float scale = m_tileAnimScale[tileIdx];
        int iconSize = static_cast<int>(std::round(88.0f * (1.0f + (scale - 1.0f) * 1.65f)));
        SDL_Rect dst{cx - iconSize / 2, cy - iconSize / 2 - 2, iconSize, iconSize};
        SDL_RenderCopy(m_renderer, m_tabIconTextures[tileIdx], nullptr, &dst);
        return;
    }

    Color accent = isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY;

    if (tileIdx == 0) { // Каталог: 4IFIR Cartridge + Storefront (Cyan & Magenta)
        drawRoundedRect(cx - 38, cy - 24, 26, 40, 4, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 38, cy - 24, 26, 40, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawRoundedRect(cx - 36, cy - 22, 22, 8, 2, Theme::COLOR_FOCUS_PINK);
        drawRoundedRect(cx - 36, cy - 11, 22, 22, 2, {0x0B, 0x10, 0x1B, 0xFF});

        drawRoundedRect(cx - 6, cy - 14, 44, 32, 4, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 6, cy - 14, 44, 32, 4, accent, accent, 1);
        drawRoundedRect(cx - 8, cy - 21, 48, 8, 3, Theme::COLOR_FOCUS_CYAN);
        for (int s = 0; s < 4; ++s) {
            drawRoundedRect(cx - 6 + s * 12, cy - 21, 6, 8, 2, Theme::COLOR_FOCUS_PINK);
        }
        drawRoundedRect(cx + 2, cy - 3, 12, 20, 2, {0x00, 0xD2, 0xFF, 0x55});
        drawRoundedRect(cx + 20, cy - 3, 14, 14, 2, {0xEC, 0x48, 0x99, 0x66});
    } else if (tileIdx == 1) { // Видеоиконки: 4IFIR 1:1 Animated Square Frame
        drawRoundedRect(cx - 34, cy - 32, 68, 64, 14, {0x11, 0x18, 0x27, 0xFF});
        drawNeonRoundedOutline(cx - 34, cy - 32, 68, 64, 14, 2);
        // Play triangle in Electric Cyan
        for (int row = -10; row <= 10; ++row) {
            int w = 15 - std::abs(row);
            drawRect(cx - 5, cy - 4 + row, w, 1, Theme::COLOR_FOCUS_CYAN);
        }
        drawRoundedRect(cx - 26, cy + 12, 52, 14, 4, Theme::COLOR_FOCUS_PINK);
        drawTextCentered("256x256", cx, cy + 13, Theme::COLOR_TEXT_PRIMARY, 9);
    } else if (tileIdx == 2) { // Менеджер игр: 4IFIR Case labeled "MY GAMES"
        drawRoundedRect(cx - 34, cy - 16, 68, 44, 8, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 34, cy - 16, 68, 44, 8, accent, accent, 1);
        drawRoundedRect(cx - 24, cy - 27, 20, 14, 3, Theme::COLOR_FOCUS_PINK);
        drawRoundedRect(cx - 2, cy - 29, 20, 16, 3, Theme::COLOR_FOCUS_CYAN);
        drawRoundedRect(cx + 12, cy - 26, 16, 13, 3, {0xA8, 0x55, 0xF7, 0xFF});
        drawRoundedRect(cx - 34, cy + 5, 68, 16, 4, {0x09, 0x0D, 0x16, 0xEE});
        drawRoundedOutline(cx - 34, cy + 5, 68, 16, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered("MY GAMES", cx, cy + 7, Theme::COLOR_FOCUS_CYAN, 10);
    } else if (tileIdx == 3) { // Загрузки: 4IFIR Switch Console (Cyan & Magenta Joy-Cons)
        drawRoundedRect(cx - 40, cy - 15, 12, 40, 5, Theme::COLOR_FOCUS_CYAN);
        drawCircle(cx - 34, cy - 5, 3, {0x09, 0x0D, 0x16, 0xFF}, true);
        drawRoundedRect(cx - 26, cy - 17, 52, 44, 4, {0x0B, 0x10, 0x1B, 0xFF});
        drawRoundedOutline(cx - 26, cy - 17, 52, 44, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawRoundedRect(cx + 28, cy - 15, 12, 40, 5, Theme::COLOR_FOCUS_PINK);
        drawCircle(cx + 34, cy + 7, 3, {0x09, 0x0D, 0x16, 0xFF}, true);

        // Download Arrow pointing into screen
        drawRect(cx - 4, cy - 29, 8, 22, Theme::COLOR_FOCUS_CYAN);
        for (int row = 0; row < 10; ++row) {
            drawRect(cx - row, cy - 7 + row, 2 * row + 1, 1, Theme::COLOR_FOCUS_CYAN);
        }
    } else if (tileIdx == 4) { // Настройки: Cyber Cogwheel Gear (Screenshot 1)
        int rOut = 26;
        int rIn = 12;
        // Gear teeth (8 teeth)
        for (int i = 0; i < 8; ++i) {
            double angle = i * (3.14159265 / 4.0);
            int tx = cx + static_cast<int>(std::cos(angle) * 22);
            int ty = cy + static_cast<int>(std::sin(angle) * 22);
            drawRoundedRect(tx - 4, ty - 4, 8, 8, 2, accent);
        }
        // Central hub
        drawCircle(cx, cy, rOut, {0x26, 0x30, 0x44, 0xFF}, true);
        drawCircle(cx, cy, rOut, accent, false);
        drawCircle(cx, cy, rIn, {0x11, 0x18, 0x27, 0xFF}, true);
        drawCircle(cx, cy, 5, Theme::COLOR_FOCUS_CYAN, true);
    }
#endif
}

void App::drawCategoryEmblem(int cx, int cy, const std::string& iconType, Color col) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    if (iconType == "all_catalog") {
        // 2x2 Rounded Grid Squares
        int s = 9, g = 4;
        for (int r = 0; r < 2; ++r) {
            for (int c = 0; c < 2; ++c) {
                int qx = cx - s - g / 2 + c * (s + g);
                int qy = cy - s - g / 2 + r * (s + g);
                drawRect(qx, qy, s, s, col);
            }
        }
    } else if (iconType == "favorites") {
        // 5-point Star
        drawCircle(cx, cy, 10, col, true);
        drawCircle(cx, cy - 8, 4, col, true);
        drawCircle(cx + 8, cy - 2, 4, col, true);
        drawCircle(cx - 8, cy - 2, 4, col, true);
        drawCircle(cx + 5, cy + 7, 4, col, true);
        drawCircle(cx - 5, cy + 7, 4, col, true);
    } else if (iconType == "new_release") {
        // 4-point Sparkle Diamond
        for (int i = 0; i <= 14; ++i) {
            int w = 14 - i;
            drawRect(cx - w / 2, cy - 14 + i, w, 1, col);
            drawRect(cx - w / 2, cy + 14 - i, w, 1, col);
        }
    } else if (iconType == "top_100") {
        // Golden Trophy
        drawRect(cx - 8, cy - 12, 16, 12, col);
        drawRect(cx - 3, cy, 6, 8, col);
        drawRect(cx - 9, cy + 8, 18, 4, col);
        drawRectOutline(cx - 12, cy - 10, 24, 7, col, 2); // handles
    } else if (iconType == "action_adventure") {
        // Crossed Broadswords
        SDL_SetRenderDrawColor(m_renderer, col.r, col.g, col.b, col.a);
        for (int d = -1; d <= 1; ++d) {
            SDL_RenderDrawLine(m_renderer, cx - 12 + d, cy - 12, cx + 12 + d, cy + 12);
            SDL_RenderDrawLine(m_renderer, cx + 12 + d, cy - 12, cx - 12 + d, cy + 12);
        }
        drawRect(cx - 9, cy - 4, 6, 6, col);
        drawRect(cx + 3, cy - 4, 6, 6, col);
    } else if (iconType == "arcade") {
        // Joystick Base + Stick + Ball
        drawRect(cx - 12, cy + 3, 24, 10, col);
        drawRect(cx - 2, cy - 8, 4, 11, col);
        drawCircle(cx, cy - 9, 6, col, true);
    } else if (iconType == "horror") {
        // Skull
        drawCircle(cx, cy - 2, 11, col, true);
        drawRect(cx - 6, cy + 4, 12, 9, col);
        // Hollow eye sockets
        drawCircle(cx - 4, cy - 2, 3, {0x14, 0x1A, 0x28, 0xFF}, true);
        drawCircle(cx + 4, cy - 2, 3, {0x14, 0x1A, 0x28, 0xFF}, true);
    } else if (iconType == "metroidvania") {
        // Concentric Radar Rings
        drawCircle(cx, cy, 14, col, false);
        drawCircle(cx, cy, 8, col, false);
        drawCircle(cx, cy, 3, col, true);
    } else if (iconType == "party_multiplayer") {
        // Dual Gamepads
        drawRect(cx - 12, cy - 8, 16, 10, col);
        drawRect(cx - 4, cy + 1, 16, 10, col);
        drawCircle(cx - 8, cy - 3, 2, {0x14, 0x1A, 0x28, 0xFF}, true);
        drawCircle(cx + 8, cy + 6, 2, {0x14, 0x1A, 0x28, 0xFF}, true);
    } else if (iconType == "platformers") {
        // Platform + Jump Arc
        drawRect(cx - 14, cy + 8, 28, 4, col);
        drawCircle(cx, cy - 2, 9, col, false);
        drawRect(cx - 10, cy - 2, 20, 10, {0x14, 0x1A, 0x28, 0xFF}); // mask lower half
    } else if (iconType == "puzzles") {
        // Jigsaw Puzzle Piece
        drawRect(cx - 9, cy - 9, 18, 18, col);
        drawCircle(cx, cy - 9, 4, col, true);
        drawCircle(cx + 9, cy, 4, col, true);
    } else if (iconType == "roguelike_roguelite") {
        // D6 Die with dots
        drawRect(cx - 10, cy - 10, 20, 20, col);
        Color dotCol = {0x14, 0x1A, 0x28, 0xFF};
        drawCircle(cx - 5, cy - 5, 2, dotCol, true);
        drawCircle(cx + 5, cy + 5, 2, dotCol, true);
        drawCircle(cx, cy, 2, dotCol, true);
        drawCircle(cx - 5, cy + 5, 2, dotCol, true);
        drawCircle(cx + 5, cy - 5, 2, dotCol, true);
    } else if (iconType == "rpg_jrpg") {
        // Cut Crystal Gem
        for (int i = 0; i <= 14; ++i) {
            int w = (i < 6) ? (8 + i * 2) : (20 - (i - 6) * 2);
            drawRect(cx - w / 2, cy - 10 + i, w, 1, col);
        }
    } else if (iconType == "shooters") {
        // Crosshair Reticle
        drawCircle(cx, cy, 12, col, false);
        SDL_SetRenderDrawColor(m_renderer, col.r, col.g, col.b, col.a);
        SDL_RenderDrawLine(m_renderer, cx - 15, cy, cx + 15, cy);
        SDL_RenderDrawLine(m_renderer, cx, cy - 15, cx, cy + 15);
        drawCircle(cx, cy, 2, col, true);
    } else if (iconType == "simulation_cozy") {
        // Leaf
        drawCircle(cx, cy, 10, col, true);
        drawRect(cx - 2, cy + 5, 4, 7, col);
    } else if (iconType == "strategy_tactics") {
        // Chess Rook / Castle Tower
        drawRect(cx - 8, cy - 10, 16, 5, col);
        drawRect(cx - 6, cy - 5, 12, 12, col);
        drawRect(cx - 9, cy + 7, 18, 4, col);
        drawRect(cx - 2, cy - 10, 4, 3, {0x14, 0x1A, 0x28, 0xFF}); // center embrasure
    } else if (iconType == "visual_novels") {
        // Open Book
        drawRect(cx - 12, cy - 7, 11, 14, col);
        drawRect(cx + 1, cy - 7, 11, 14, col);
        drawRect(cx - 1, cy - 8, 2, 16, {0x14, 0x1A, 0x28, 0xFF});
    } else { // "ports_homebrew"
        // Switch Console
        drawRect(cx - 12, cy - 7, 24, 14, col);
        drawRect(cx - 6, cy - 5, 12, 10, {0x14, 0x1A, 0x28, 0xFF});
    }
#endif
}

void App::drawDashboardTile(int x, int y, int w, int h, int tileIdx, const std::string& title, const std::string& sub, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    // Smooth bouncy scale animation (60 FPS spring interpolation)
    float scale = (tileIdx >= 0 && tileIdx < 5) ? m_tileAnimScale[tileIdx] : (isFocused ? 1.055f : 1.0f);
    int drawW = static_cast<int>(std::round(static_cast<float>(w) * scale));
    int drawH = static_cast<int>(std::round(static_cast<float>(h) * scale));
    int drawX = x - (drawW - w) / 2;
    int drawY = y - (drawH - h) / 2;

    Color bg = isFocused ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_TILE;
    drawRoundedRect(drawX, drawY, drawW, drawH, 22, bg);

    if (isFocused) {
        drawRoundedRect(drawX, drawY, drawW, drawH, 22, Theme::COLOR_FOCUS_FILL);
        uint8_t alpha = static_cast<uint8_t>(std::clamp(m_glowPulse * 255.0f, 160.0f, 255.0f));
        Color cGlow = Theme::COLOR_FOCUS_CYAN; cGlow.a = alpha;
        Color pGlow = Theme::COLOR_FOCUS_PINK; pGlow.a = alpha;
        drawRoundedOutline(drawX, drawY, drawW, drawH, 22, cGlow, pGlow, 3);
    } else {
        drawRoundedOutline(drawX, drawY, drawW, drawH, 22, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }

    drawRoundedRect(drawX + 18, drawY + 2, drawW - 36, 2, 1, {0xFF, 0xFF, 0xFF, 0x1A});

    int iconCx = drawX + drawW / 2;
    int iconCy = drawY + (sub.empty() ? 70 : 76);
    drawTileIconVector(iconCx, iconCy, tileIdx, isFocused);

    if (sub.empty()) {
        drawTextCentered(title, drawX + drawW / 2, drawY + drawH - 34, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
    } else {
        drawTextCentered(title, drawX + drawW / 2, drawY + drawH - 68, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, drawW - 18);
        Color badgeAcc = (tileIdx == 1) ? Theme::COLOR_FOCUS_PINK : (isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED);
        int bw = std::min(drawW - 24, measureTextWidth(sub, 11) + 22);
        int bx = drawX + (drawW - bw) / 2;
        int by = drawY + drawH - 38;
        drawRoundedRect(bx, by, bw, 24, 7, isFocused ? Color{badgeAcc.r, badgeAcc.g, badgeAcc.b, 0x26} : Color{0x0D, 0x14, 0x22, 0xDD});
        drawRoundedOutline(bx, by, bw, 24, 7, badgeAcc, badgeAcc, 1);
        drawTextCentered(sub, bx + bw / 2, by + 5, badgeAcc, 11, bw - 8);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)tileIdx; (void)title; (void)sub; (void)isFocused;
#endif
}

void App::drawSummaryCard(int x, int y, int w, int h, const std::string& header, const std::string& line1, const std::string& line2, const std::string& badgeText) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    drawRoundedRect(x, y, w, h, 16, Theme::COLOR_BG_SURFACE);
    drawRoundedOutline(x, y, w, h, 16, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);

    drawRoundedRect(x + 16, y + 18, 3, 16, 2, Theme::COLOR_FOCUS_CYAN);
    drawText(header, x + 26, y + 16, Theme::COLOR_TEXT_MUTED, 13);

    drawText(line1, x + 20, y + 54, Theme::COLOR_TEXT_PRIMARY, 20);
    drawText(line2, x + 20, y + 92, Theme::COLOR_TEXT_MUTED, 13);

    if (!badgeText.empty()) {
        int badgeW = measureTextWidth(badgeText, 11) + 20;
        int badgeX = x + w - badgeW - 18;
        int badgeY = y + 16;
        drawRoundedRect(badgeX, badgeY, badgeW, 24, 6, Theme::COLOR_FOCUS_FILL);
        drawRoundedOutline(badgeX, badgeY, badgeW, 24, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered(badgeText, badgeX + badgeW / 2, badgeY + 4, Theme::COLOR_FOCUS_CYAN, 11);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)header; (void)line1; (void)line2; (void)badgeText;
#endif
}

void App::drawCategoryCard(int x, int y, int w, int h, const std::string& iconType, const std::string& title, const std::string& desc, const std::string& countText, bool isFocused, Color accentCol) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    Color bg = isFocused ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_SURFACE;
    drawRoundedRect(x, y, w, h, 14, bg);

    if (isFocused) {
        drawRoundedRect(x, y, w, h, 14, Theme::COLOR_FOCUS_FILL);
        drawNeonRoundedOutline(x, y, w, h, 14, 2);
    } else {
        drawRoundedOutline(x, y, w, h, 14, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }

    // Left Emblem Container (52x52 rounded box)
    int emSize = 52;
    int emX = x + 12;
    int emY = y + (h - emSize) / 2;
    drawRoundedRect(emX, emY, emSize, emSize, 12, {0x14, 0x1A, 0x28, 0xFF});
    drawRoundedOutline(emX, emY, emSize, emSize, 12, accentCol, accentCol, 1);

    // Vector Emblem inside container
    int emCx = emX + emSize / 2;
    int emCy = emY + emSize / 2;
    drawCategoryEmblem(emCx, emCy, iconType, accentCol);

    // Text info on the right
    int textX = emX + emSize + 12;
    drawText(title, textX, y + 12, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);
    drawText(desc, textX, y + 36, Theme::COLOR_TEXT_MUTED, 12, w - (textX - x) - 10);

    // Count Pill
    int badgeW = measureTextWidth(countText, 11) + 18;
    int badgeX = textX;
    int badgeY = y + 62;
    drawRoundedRect(badgeX, badgeY, badgeW, 22, 6, Theme::COLOR_FOCUS_FILL);
    drawRoundedOutline(badgeX, badgeY, badgeW, 22, 6, accentCol, accentCol, 1);
    drawTextCentered(countText, badgeX + badgeW / 2, badgeY + 3, accentCol, 11);
#else
    (void)x; (void)y; (void)w; (void)h; (void)iconType; (void)title; (void)desc; (void)countText; (void)isFocused; (void)accentCol;
#endif
}

void App::drawPillButton(int x, int y, int w, int h, const std::string& text, bool isFocused, Color textCol) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color bg = isFocused ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_PILL_BG;
    drawRoundedRect(x, y, w, h, 10, bg);
    if (isFocused) {
        drawNeonRoundedOutline(x, y, w, h, 10, 2);
    } else {
        drawRoundedOutline(x, y, w, h, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }
    drawText(text, x + 12, y + (h - 14) / 2, textCol, 13);
#else
    (void)x; (void)y; (void)w; (void)h; (void)text; (void)isFocused; (void)textCol;
#endif
}

bool App::isIconInstalled(const std::string& titleId) const {
    if (!m_platform) return false;
    std::string iconPath = m_platform->getIconsDirectory() + "/" + Config::getTargetIconFileName(titleId);
    std::error_code ec;
    return std::filesystem::exists(iconPath, ec);
}

void App::rebuildVideoIconsFilter() {
    m_filteredVideoIcons.clear();
    std::string q = utf8ToLower(m_videoIconsSearchQuery);

    for (const auto& entry : m_videoIconsCatalog) {
        if (m_videoIconsFilterMode == 1 && !isIconInstalled(entry.titleId)) {
            continue;
        }
        if (m_videoIconsFilterMode == 2 && isIconInstalled(entry.titleId)) {
            continue;
        }

        if (!q.empty()) {
            std::string t = utf8ToLower(entry.title);
            std::string id = utf8ToLower(entry.titleId);
            if (t.find(q) == std::string::npos && id.find(q) == std::string::npos) {
                continue;
            }
        }

        m_filteredVideoIcons.push_back(entry);
    }

    if (m_videoIconsSelectedIndex >= static_cast<int>(m_filteredVideoIcons.size())) {
        m_videoIconsSelectedIndex = std::max(0, static_cast<int>(m_filteredVideoIcons.size()) - 1);
    }
}

void App::openVideoIconsKeyboard() {
#ifdef __SWITCH__
    SwkbdConfig kbd;
    char textBuf[256] = {0};
    if (!m_videoIconsSearchQuery.empty()) {
        strncpy(textBuf, m_videoIconsSearchQuery.c_str(), sizeof(textBuf) - 1);
    }

    Result rc = swkbdCreate(&kbd, 0);
    if (R_SUCCEEDED(rc)) {
        swkbdConfigMakePresetDefault(&kbd);
        swkbdConfigSetHeaderText(&kbd, "Поиск видеоиконок 4IFIR");
        swkbdConfigSetGuideText(&kbd, "Введите название игры или TitleID");
        swkbdConfigSetOkButtonText(&kbd, "Поиск");
        swkbdConfigSetInitialText(&kbd, textBuf);
        swkbdConfigSetStringLenMax(&kbd, 64);

        rc = swkbdShow(&kbd, textBuf, sizeof(textBuf));
        if (R_SUCCEEDED(rc)) {
            m_videoIconsSearchQuery = std::string(textBuf);
            rebuildVideoIconsFilter();
        }
        swkbdClose(&kbd);
    }
#else
    m_videoIconsSearchQuery.clear();
    rebuildVideoIconsFilter();
#endif
}

void App::openFullscreenVideoIconPreview(const GameCatalogEntry& entry, int variantIndex) {
#ifdef HAS_SDL2
    if (entry.variants.empty()) return;

    std::vector<Variant> iconVars = getUniqueIconVariants(entry);
    if (iconVars.empty()) {
        iconVars = entry.variants;
    }

    int vIdx = std::clamp(variantIndex, 0, static_cast<int>(iconVars.size()) - 1);

    m_previewTitleId = entry.titleId;
    m_previewGameName = entry.title;
    m_previewVariants = iconVars;
    m_previewVariantIndex = vIdx;
    m_previewIsGameInstalled = true;
    m_previewHasInstalledCover = isIconInstalled(entry.titleId);
    m_previewIsIconSquare = true;
    m_previewInstalledVariantId = iconVars[vIdx].id;
    m_previewInstalledCoverPath = m_platform->getIconsDirectory() + "/" + Config::getTargetIconFileName(entry.titleId);
    m_isFullscreenPreview = true;
    m_previewOpenedAt = SDL_GetTicks();

    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#else
    (void)entry; (void)variantIndex;
#endif
}

void App::checkForUpdates(bool manualTrigger) {
    (void)manualTrigger;
    updateApplicationNro();
}

// =========================================================================================
// v1.5.0: Жесткое правило кнопок везде + Стеклянная шторка действий [X] + Идеи 1–6
// =========================================================================================

void App::switchGlobalTab(int delta) {
    if (m_isActionSheetOpen) {
        closeActionSheet();
    }
    if (m_activeTab == Tab::VideoIcons || m_activeTab == Tab::Catalog) {
        m_videoPlayer.close();
        m_videoIconDockDirty = false;
        m_catalogDockDirty = false;
        m_collectionTransferQueued = false;
        m_cancelCollectionThumb.store(true);
    }

    int cur = static_cast<int>(m_activeTab);
    int next = (cur + delta) % 6;
    if (next < 0) next += 6;
    m_activeTab = static_cast<Tab>(next);

    if (next >= 1 && next <= 5) {
        m_homeFocusedTile = next - 1;
    }

    if (m_activeTab == Tab::Catalog) {
        if (m_filteredCatalogGames.empty() && m_catalogSearchQuery.empty() && m_catalogSortMode == CatalogSortMode::Default) {
            rebuildCatalogFilter();
        }
        m_catalogDockDirty = true;
        m_catalogDockCurrentKey.clear();
#ifdef HAS_SDL2
        m_lastCatalogMoveTime = SDL_GetTicks();
#endif
    } else if (m_activeTab == Tab::VideoIcons) {
        rebuildVideoIconsFilter();
        m_videoIconDockDirty = true;
#ifdef HAS_SDL2
        m_lastVideoIconMoveTime = SDL_GetTicks();
#endif
    } else if (m_activeTab == Tab::MyGames) {
        rebuildMyGamesFilter();
    }

    m_tabTransitionAlpha = 140.0f;
}

void App::jumpAlphabetical(int dir) {
    auto extractBucket = [](const std::string& rawTitle) -> std::string {
        size_t i = 0;
        while (i < rawTitle.size()) {
            unsigned char c = static_cast<unsigned char>(rawTitle[i]);
            if (c <= 0x20 || c == '[' || c == '(' || c == '"' || c == '\'' || c == '-' || c == '_') {
                ++i;
                continue;
            }
            if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')) {
                char up = static_cast<char>(std::toupper(c));
                return std::string(1, up);
            }
            if (c >= '0' && c <= '9') {
                return "0-9";
            }
            // UTF-8 Cyrillic 2-byte character (0xD0 / 0xD1)
            if ((c == 0xD0 || c == 0xD1) && i + 1 < rawTitle.size()) {
                return rawTitle.substr(i, 2);
            }
            // Skip decorative UTF-8 symbols like ★ (0xE2 0x98 0x85)
            if (c >= 0xE0 && i + 2 < rawTitle.size()) {
                i += 3;
                continue;
            }
            return "#";
        }
        return "#";
    };

    int step = (dir >= 0) ? 1 : -1;

    if (m_activeTab == Tab::Catalog && !m_filteredCatalogGames.empty()) {
        int n = static_cast<int>(m_filteredCatalogGames.size());
        int cur = std::clamp(m_catalogSelectedIndex, 0, n - 1);
        std::string curB = extractBucket(m_filteredCatalogGames[cur].title);
        int idx = cur;
        for (int k = 0; k < n; ++k) {
            idx = (idx + step + n) % n;
            std::string b = extractBucket(m_filteredCatalogGames[idx].title);
            if (b != curB) {
                m_catalogSelectedIndex = idx;
                m_catalogScrollOffset = std::clamp(idx - 1, 0, std::max(0, n - 5));
                m_catalogDockDirty = true;
                m_catalogDockCurrentKey.clear();
#ifdef HAS_SDL2
                m_lastCatalogMoveTime = SDL_GetTicks();
#endif
                m_alphaJumpText = b;
                m_alphaJumpFrames = 52;
                return;
            }
        }
        m_alphaJumpText = curB;
        m_alphaJumpFrames = 40;
    } else if (m_activeTab == Tab::VideoIcons && !m_filteredVideoIcons.empty()) {
        int n = static_cast<int>(m_filteredVideoIcons.size());
        int cur = std::clamp(m_videoIconsSelectedIndex, 0, n - 1);
        std::string curB = extractBucket(m_filteredVideoIcons[cur].title);
        int idx = cur;
        for (int k = 0; k < n; ++k) {
            idx = (idx + step + n) % n;
            std::string b = extractBucket(m_filteredVideoIcons[idx].title);
            if (b != curB) {
                m_videoIconsSelectedIndex = idx;
                m_videoIconsScrollOffset = std::clamp(idx - 1, 0, std::max(0, n - 5));
                m_videoIconDockDirty = true;
#ifdef HAS_SDL2
                m_lastVideoIconMoveTime = SDL_GetTicks();
#endif
                m_alphaJumpText = b;
                m_alphaJumpFrames = 52;
                return;
            }
        }
        m_alphaJumpText = curB;
        m_alphaJumpFrames = 40;
    } else if (m_activeTab == Tab::MyGames && !m_filteredMyGamesIndices.empty()) {
        int n = static_cast<int>(m_filteredMyGamesIndices.size());
        int cur = std::clamp(m_myGamesSelectedIndex, 0, n - 1);
        std::string curB = extractBucket(m_installedGames[m_filteredMyGamesIndices[cur]].name);
        int idx = cur;
        for (int k = 0; k < n; ++k) {
            idx = (idx + step + n) % n;
            std::string b = extractBucket(m_installedGames[m_filteredMyGamesIndices[idx]].name);
            if (b != curB) {
                m_myGamesSelectedIndex = idx;
                m_myGamesScrollOffset = std::clamp(idx - 1, 0, std::max(0, n - 7));
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
                m_alphaJumpText = b;
                m_alphaJumpFrames = 52;
                return;
            }
        }
        m_alphaJumpText = curB;
        m_alphaJumpFrames = 40;
    }
}

void App::openActionSheetForCurrentContext() {
    m_actionSheetItems.clear();
    m_actionSheetSelectedIndex = 0;

    if (m_activeTab == Tab::Catalog) {
        if (m_filteredCatalogGames.empty()) return;
        int idx = std::clamp(m_catalogSelectedIndex, 0, static_cast<int>(m_filteredCatalogGames.size()) - 1);
        const auto& entry = m_filteredCatalogGames[idx];
        auto covs = getCoverVariants(entry);
        auto icons = getUniqueIconVariants(entry);
        bool isFav = hasGameFavorites(entry.titleId);

        m_actionSheetTitle = entry.title;
        m_actionSheetSubtitle = !m_linkingTargetTitleId.empty()
            ? (tr("Привязка к: ", "Binding to: ") + m_linkingTargetGameName + " [" + m_linkingTargetTitleId + "]")
            : ("Title ID: " + entry.titleId + " • " + std::to_string(covs.size()) + tr(" фонов, ", " covers, ") + std::to_string(icons.size()) + " HQ");

        m_actionSheetItems.push_back({ActionSheetCmd::InstallCombo,
            !m_linkingTargetTitleId.empty()
                ? tr("Привязать Комбо (Фон + Иконка)", "Bind Combo (Cover + HQ Icon)")
                : tr("Комбо-установка (Фон + HQ-иконка)", "Install Combo (Cover + HQ Icon)"),
            "1-КЛИК", Theme::COLOR_FOCUS_CYAN});

        if (!covs.empty()) {
            m_actionSheetItems.push_back({ActionSheetCmd::AppendNewSlot,
                tr("Добавить в новый слот ротации", "Append to New Rotation Slot"),
                "+СЛОТ", Theme::COLOR_FOCUS_PINK});
        }

        m_actionSheetItems.push_back({ActionSheetCmd::FullscreenPreview,
            tr("Живое превью на весь экран", "Fullscreen Live Video Preview"),
            "LIVE", Theme::COLOR_SUCCESS});

        m_actionSheetItems.push_back({ActionSheetCmd::AssignToAnotherGame,
            tr("Назначить на любую другую игру...", "Assign to Another Installed Game..."),
            "PICK", Theme::COLOR_WARNING});

        m_actionSheetItems.push_back({ActionSheetCmd::ToggleFavorite,
            isFav ? tr("Убрать из избранного ★", "Remove from Favorites ★") : tr("Добавить в избранное ★", "Add to Favorites ★"),
            "★", Color{0xFF, 0xD7, 0x00, 0xFF}});
    } else if (m_activeTab == Tab::VideoIcons) {
        if (m_filteredVideoIcons.empty()) return;
        int idx = std::clamp(m_videoIconsSelectedIndex, 0, static_cast<int>(m_filteredVideoIcons.size()) - 1);
        const auto& entry = m_filteredVideoIcons[idx];
        bool inst = isIconInstalled(entry.titleId);
        bool isFav = hasGameFavorites(entry.titleId);

        m_actionSheetTitle = entry.title;
        m_actionSheetSubtitle = "256x256 HQ Icon • " + entry.titleId;

        m_actionSheetItems.push_back({ActionSheetCmd::FullscreenPreview,
            tr("Живое превью 256x256 на весь экран", "Fullscreen 256x256 Live Preview"),
            "LIVE", Theme::COLOR_SUCCESS});

        m_actionSheetItems.push_back({ActionSheetCmd::InstallCombo,
            tr("Комбо-установка (Иконка + Видеофон)", "Install Combo (Icon + Video Cover)"),
            "1-КЛИК", Theme::COLOR_FOCUS_CYAN});

        m_actionSheetItems.push_back({ActionSheetCmd::AssignToAnotherGame,
            tr("Назначить иконку на другую игру...", "Assign Icon to Another Game..."),
            "PICK", Theme::COLOR_WARNING});

        m_actionSheetItems.push_back({ActionSheetCmd::ToggleFavorite,
            isFav ? tr("Убрать из избранного ★", "Remove from Favorites ★") : tr("Добавить в избранное ★", "Add to Favorites ★"),
            "★", Color{0xFF, 0xD7, 0x00, 0xFF}});

        if (inst) {
            m_actionSheetItems.push_back({ActionSheetCmd::DeleteInstalled,
                tr("Удалить установленную HQ-иконку", "Delete Installed HQ Video Icon"),
                "DEL", Theme::COLOR_DANGER});
        }
    } else if (m_activeTab == Tab::MyGames) {
        if (m_filteredMyGamesIndices.empty()) return;
        int idx = std::clamp(m_myGamesSelectedIndex, 0, static_cast<int>(m_filteredMyGamesIndices.size()) - 1);
        const auto& selGame = m_installedGames[m_filteredMyGamesIndices[idx]];

        m_actionSheetTitle = selGame.name;
        m_actionSheetSubtitle = "Title ID: " + selGame.titleId + " • " +
                                std::to_string(selGame.installedCoversCount) + tr(" слот(ов)", " slot(s)");

        if (selGame.hasCatalogMatch && !selGame.catalogEntry.variants.empty()) {
            m_actionSheetItems.push_back({ActionSheetCmd::InstallCombo,
                tr("Комбо-установка (Фон + HQ-иконка)", "Install Combo (Cover + HQ Icon)"),
                "1-КЛИК", Theme::COLOR_FOCUS_CYAN});

            if (!getCoverVariants(selGame.catalogEntry).empty()) {
                m_actionSheetItems.push_back({ActionSheetCmd::AppendNewSlot,
                    tr("Добавить вариант в новый слот ротации", "Append Variant to New Rotation Slot"),
                    "+СЛОТ", Theme::COLOR_FOCUS_PINK});
            }

            m_actionSheetItems.push_back({ActionSheetCmd::FullscreenPreview,
                tr("Живое превью на весь экран", "Fullscreen Live Video Preview"),
                "LIVE", Theme::COLOR_SUCCESS});
        }

        m_actionSheetItems.push_back({ActionSheetCmd::LinkForwarderToCatalog,
            tr("Найти в базе и привязать к этому Title ID", "Find in Catalog & Bind to Title ID"),
            "LINK", Theme::COLOR_WARNING});

        if (selGame.installedCoversCount > 1) {
            m_actionSheetItems.push_back({ActionSheetCmd::CycleActiveSlot,
                tr("Переключить активный слот видеофона", "Cycle Active Video Cover Slot"),
                "СЛОТ", Theme::COLOR_FOCUS_CYAN});
            m_actionSheetItems.push_back({ActionSheetCmd::DeleteExtraSlots,
                tr("Удалить доп. слоты (оставить основной)", "Delete Extra Slots (Keep Primary)"),
                "CLEAN", Theme::COLOR_FOCUS_PINK});
        }

        m_actionSheetItems.push_back({ActionSheetCmd::OpenLocalRecordings,
            tr("Установить свой клип с SD-карты", "Install Custom Clip from SD Card"),
            "SD", Theme::COLOR_TEXT_PRIMARY});

        if (!m_newlyDetectedTitleIds.empty()) {
            m_actionSheetItems.push_back({ActionSheetCmd::InstallNewGamesPack,
                tr("Оформить все новинки консоли", "Auto-Combo All New Console Games"),
                "★ " + std::to_string(m_newlyDetectedTitleIds.size()), Theme::COLOR_WARNING});
        }

        if (selGame.hasInstalledCover || selGame.hasInstalledIcon) {
            m_actionSheetItems.push_back({ActionSheetCmd::DeleteInstalled,
                tr("Удалить установленное оформление...", "Delete Installed Cover / Icon..."),
                "DEL", Theme::COLOR_DANGER});
        }
    } else if (m_activeTab == Tab::Home && !m_newlyDetectedTitleIds.empty()) {
        m_actionSheetTitle = tr("Умный детектор новинок", "New Console Games Detector");
        m_actionSheetSubtitle = tr("Обнаружено новых игр на консоли: ", "Newly detected titles: ") +
                                std::to_string(m_newlyDetectedTitleIds.size());
        m_actionSheetItems.push_back({ActionSheetCmd::InstallNewGamesPack,
            tr("Установить Комбо (Фон + Иконка) на новинки", "Install Combo Pack for All New Games"),
            "1-КЛИК", Theme::COLOR_WARNING});
    }

    if (m_actionSheetItems.empty()) return;

    m_isActionSheetOpen = true;
#ifdef HAS_SDL2
    m_actionSheetOpenedAt = SDL_GetTicks();
#endif
}

void App::closeActionSheet() {
    m_isActionSheetOpen = false;
    m_actionSheetItems.clear();
}

void App::executeActionSheetSelection() {
    if (m_actionSheetSelectedIndex < 0 || m_actionSheetSelectedIndex >= static_cast<int>(m_actionSheetItems.size())) {
        closeActionSheet();
        return;
    }
    ActionSheetCmd cmd = m_actionSheetItems[m_actionSheetSelectedIndex].cmd;
    closeActionSheet();

    if (cmd == ActionSheetCmd::InstallNewGamesPack) {
        installAllNewlyDetectedGames();
        return;
    }

    if (m_activeTab == Tab::Catalog && !m_filteredCatalogGames.empty()) {
        int idx = std::clamp(m_catalogSelectedIndex, 0, static_cast<int>(m_filteredCatalogGames.size()) - 1);
        const auto& entry = m_filteredCatalogGames[idx];

        InstalledTitle targetGame;
        bool isLinking = !m_linkingTargetTitleId.empty();
        std::string targetTid = isLinking ? m_linkingTargetTitleId : entry.titleId;
        bool foundInstalled = false;
        for (const auto& ig : m_installedGames) {
            if (ig.titleId == targetTid) {
                targetGame = ig;
                foundInstalled = true;
                break;
            }
        }
        if (!foundInstalled) {
            targetGame.titleId = targetTid;
            targetGame.name = isLinking ? m_linkingTargetGameName : entry.title;
            targetGame.hasCatalogMatch = true;
            targetGame.catalogEntry = entry;
        }

        int selCovIdx = getSelectedCatalogVariantIndex(entry);
        if (cmd == ActionSheetCmd::InstallCombo || cmd == ActionSheetCmd::AppendNewSlot) {
            if (targetTid == "0000000000000000") {
                auto covs = getCoverVariants(entry);
                if (!covs.empty()) {
                    int pickIdx = std::clamp(selCovIdx, 0, static_cast<int>(covs.size()) - 1);
                    openGamePicker(covs[pickIdx], entry.title);
                } else if (!entry.variants.empty()) {
                    openGamePicker(entry.variants[0], entry.title);
                }
            } else if (cmd == ActionSheetCmd::InstallCombo) {
                queueComboPack(targetGame, entry, selCovIdx);
                if (isLinking) cancelForwarderLinkMode();
            } else {
                auto covs = getCoverVariants(entry);
                if (!covs.empty()) {
                    int pickIdx = std::clamp(selCovIdx, 0, static_cast<int>(covs.size()) - 1);
                    queueDownloadAppendSlot(targetGame, covs[pickIdx]);
                    if (isLinking) cancelForwarderLinkMode();
                }
            }
        } else if (cmd == ActionSheetCmd::FullscreenPreview) {
            openFullscreenPreviewForCatalogGame(entry, selCovIdx);
        } else if (cmd == ActionSheetCmd::AssignToAnotherGame) {
            auto covs = getCoverVariants(entry);
            if (!covs.empty()) {
                int pickIdx = std::clamp(selCovIdx, 0, static_cast<int>(covs.size()) - 1);
                openGamePicker(covs[pickIdx], entry.title);
            } else if (!entry.variants.empty()) {
                openGamePicker(entry.variants[0], entry.title);
            }
        } else if (cmd == ActionSheetCmd::ToggleFavorite) {
            auto covs = getCoverVariants(entry);
            if (!covs.empty()) {
                int pickIdx = std::clamp(selCovIdx, 0, static_cast<int>(covs.size()) - 1);
                toggleFavoriteVariant(entry.titleId, covs[pickIdx]);
            } else if (!entry.variants.empty()) {
                toggleFavoriteVariant(entry.titleId, entry.variants[0]);
            }
        }
    } else if (m_activeTab == Tab::VideoIcons && !m_filteredVideoIcons.empty()) {
        int idx = std::clamp(m_videoIconsSelectedIndex, 0, static_cast<int>(m_filteredVideoIcons.size()) - 1);
        const auto& entry = m_filteredVideoIcons[idx];
        int vIdx = getSelectedVideoIconVariantIndex(entry);

        if (cmd == ActionSheetCmd::FullscreenPreview) {
            openFullscreenVideoIconPreview(entry, vIdx);
        } else if (cmd == ActionSheetCmd::InstallCombo) {
            if (entry.titleId == "0000000000000000" && !entry.variants.empty()) {
                Variant icoVar = entry.variants[vIdx];
                if (icoVar.id.rfind("icon-", 0) != 0) icoVar.id = "icon-" + icoVar.id;
                openGamePicker(icoVar, entry.title);
            } else {
                InstalledTitle targetGame;
                bool found = false;
                for (const auto& ig : m_installedGames) {
                    if (ig.titleId == entry.titleId) { targetGame = ig; found = true; break; }
                }
                if (!found) {
                    targetGame.titleId = entry.titleId;
                    targetGame.name = entry.title;
                    targetGame.hasCatalogMatch = true;
                }
                const auto* fullCat = m_catalogManager.findByTitleId(entry.titleId);
                if (fullCat) {
                    queueComboPack(targetGame, *fullCat, 0);
                } else if (!entry.variants.empty()) {
                    queueDownloadIconOnly(targetGame, entry.variants[vIdx]);
                }
            }
        } else if (cmd == ActionSheetCmd::AssignToAnotherGame) {
            if (!entry.variants.empty()) {
                Variant icoVar = entry.variants[vIdx];
                if (icoVar.id.rfind("icon-", 0) != 0) icoVar.id = "icon-" + icoVar.id;
                openGamePicker(icoVar, entry.title);
            }
        } else if (cmd == ActionSheetCmd::ToggleFavorite) {
            if (!entry.variants.empty()) {
                toggleFavoriteVariant(entry.titleId, entry.variants[vIdx]);
            }
        } else if (cmd == ActionSheetCmd::DeleteInstalled) {
            executeDeleteIcon(entry.titleId);
        }
    } else if (m_activeTab == Tab::MyGames && !m_filteredMyGamesIndices.empty()) {
        int idx = std::clamp(m_myGamesSelectedIndex, 0, static_cast<int>(m_filteredMyGamesIndices.size()) - 1);
        const auto& selGame = m_installedGames[m_filteredMyGamesIndices[idx]];
        int vIdx = std::clamp(m_selectedVariantIndex, 0, std::max(0, static_cast<int>(selGame.catalogEntry.variants.size()) - 1));

        if (selGame.titleId == "0000000000000000" && (cmd == ActionSheetCmd::InstallCombo || cmd == ActionSheetCmd::AppendNewSlot)) {
            openCollectionBrowser(selGame.catalogEntry);
        } else if (cmd == ActionSheetCmd::InstallCombo) {
            queueComboPack(selGame, selGame.catalogEntry, vIdx);
        } else if (cmd == ActionSheetCmd::AppendNewSlot) {
            auto covs = getCoverVariants(selGame.catalogEntry);
            if (!covs.empty()) {
                int cIdx = std::clamp(vIdx, 0, static_cast<int>(covs.size()) - 1);
                queueDownloadAppendSlot(selGame, covs[cIdx]);
            }
        } else if (cmd == ActionSheetCmd::FullscreenPreview) {
            openFullscreenPreviewForGame(selGame, vIdx);
        } else if (cmd == ActionSheetCmd::LinkForwarderToCatalog) {
            startForwarderLinkSearch(selGame);
        } else if (cmd == ActionSheetCmd::CycleActiveSlot) {
            executeCycleNextCover(selGame.titleId);
        } else if (cmd == ActionSheetCmd::DeleteExtraSlots) {
            m_videoPlayer.close();
            for (int s = selGame.installedCoversCount - 1; s >= 1; --s) {
                Installer::deleteCoverVariant(m_platform->getCoversDirectory(), selGame.titleId, selGame.installedCoverVariants[s].index);
            }
            refreshInstalledGames();
            rebuildMyGamesFilter();
            m_statusNotification = tr("Доп. слоты очищены (оставлен основной фон)", "Extra cover slots removed (primary kept)");
            m_notificationFramesRemaining = 120;
        } else if (cmd == ActionSheetCmd::OpenLocalRecordings) {
            openRecordingsBrowser(selGame.titleId, selGame.name);
        } else if (cmd == ActionSheetCmd::DeleteInstalled) {
            m_pendingActionTitleId = selGame.titleId;
            m_activeDialog = DialogType::ConfirmDelete;
#ifdef HAS_SDL2
            m_dialogOpenedAt = SDL_GetTicks();
#endif
            m_dialogFocus = 0;
            m_dialogTitle = tr("Удаление оформления", "Delete Installed Media");
            m_dialogMessage = tr("Удалить установленное видеооформление для игры ", "Delete installed video media for ") + selGame.name + "?";
        }
    }
}

void App::renderActionSheet() {
#ifdef HAS_SDL2
    if (!m_isActionSheetOpen || m_actionSheetItems.empty()) return;

    // Dim backdrop
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x03, 0x07, 0x11, 0xCC});

    int sx = 790;
    int sy = 72;
    int sw = 460;
    int sh = 576;

    drawGlassCard(sx, sy, sw, sh, true, true);
    drawNeonRoundedOutline(sx, sy, sw, sh, 16, 2);

    // Header badge + Title + Subtitle
    drawRoundedRect(sx + 20, sy + 16, 138, 22, 5, {0xEC, 0x48, 0x99, 0x2E});
    drawRoundedOutline(sx + 20, sy + 16, 138, 22, 5, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
    drawTextCentered(tr("[X] МЕНЮ ДЕЙСТВИЙ", "[X] ACTION SHEET"), sx + 20 + 69, sy + 20, Theme::COLOR_FOCUS_PINK, 10);

    drawText(m_actionSheetTitle, sx + 20, sy + 46, Theme::COLOR_TEXT_PRIMARY, 16, sw - 40);
    drawText(m_actionSheetSubtitle, sx + 20, sy + 68, Theme::COLOR_TEXT_MUTED, 11, sw - 40);
    drawRect(sx + 20, sy + 90, sw - 40, 1, Theme::COLOR_BORDER);

    int itemY = 156;
    int itemH = 42;
    for (size_t i = 0; i < m_actionSheetItems.size(); ++i) {
        bool sel = (static_cast<int>(i) == m_actionSheetSelectedIndex);
        const auto& item = m_actionSheetItems[i];

        drawRoundedRect(sx + 18, itemY, sw - 36, itemH, 10,
                        sel ? Theme::COLOR_FOCUS_FILL : Color{0x10, 0x17, 0x26, 0xDD});
        if (sel) {
            drawRoundedOutline(sx + 18, itemY, sw - 36, itemH, 10, item.accent, Theme::COLOR_FOCUS_CYAN, 2);
            drawRoundedRect(sx + 22, itemY + 8, 4, itemH - 16, 2, item.accent);
        } else {
            drawRoundedOutline(sx + 18, itemY, sw - 36, itemH, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        }

        int badgeW = measureTextWidth(item.badge, 10) + 18;
        drawText(item.label, sx + 34, itemY + 13, sel ? Theme::COLOR_TEXT_PRIMARY : Theme::COLOR_TEXT_SECONDARY, 13, sw - 74 - badgeW);

        int bx = sx + sw - 28 - badgeW;
        drawRoundedRect(bx, itemY + 9, badgeW, 24, 6, {item.accent.r, item.accent.g, item.accent.b, 0x28});
        drawRoundedOutline(bx, itemY + 9, badgeW, 24, 6, item.accent, item.accent, 1);
        drawTextCentered(item.badge, bx + badgeW / 2, itemY + 14, item.accent, 10);

        itemY += 50;
    }

    // Footer hint inside Action Sheet
    int fy = sy + sh - 42;
    drawRect(sx + 20, fy - 8, sw - 40, 1, Theme::COLOR_BORDER);
    drawTextCentered(tr("[▲/▼] Выбор   •   [A] Выполнить   •   [B / X] Закрыть",
                        "[▲/▼] Select   •   [A] Execute   •   [B / X] Close"),
                     sx + sw / 2, fy + 4, Theme::COLOR_TEXT_MUTED, 11, sw - 30);
#endif
}

void App::rebuildMyGamesFilter() {
    m_filteredMyGamesIndices.clear();
    std::string q = utf8ToLower(m_myGamesSearchQuery);

    for (int i = 0; i < static_cast<int>(m_installedGames.size()); ++i) {
        const auto& g = m_installedGames[i];
        // Always keep 4IFIR system menu entry accessible in "All" when not searching
        if (m_myGamesFilterMode == 1 && !g.hasInstalledCover && !g.hasInstalledIcon) {
            continue;
        }
        if (m_myGamesFilterMode == 2 && (g.hasInstalledCover || g.titleId == "0000000000000000")) {
            continue;
        }
        if (m_myGamesFilterMode == 3 && m_newlyDetectedTitleIds.count(g.titleId) == 0) {
            continue;
        }

        if (!q.empty()) {
            std::string nLow = utf8ToLower(g.name);
            std::string tLow = utf8ToLower(g.titleId);
            if (nLow.find(q) == std::string::npos && tLow.find(q) == std::string::npos) {
                continue;
            }
        }
        m_filteredMyGamesIndices.push_back(i);
    }

    if (m_myGamesSelectedIndex >= static_cast<int>(m_filteredMyGamesIndices.size())) {
        m_myGamesSelectedIndex = std::max(0, static_cast<int>(m_filteredMyGamesIndices.size()) - 1);
    }
    m_myGamesScrollOffset = 0;
}

void App::openMyGamesKeyboard() {
#ifdef __SWITCH__
    SwkbdConfig kbd;
    char textBuf[256] = {0};
    if (!m_myGamesSearchQuery.empty()) {
        strncpy(textBuf, m_myGamesSearchQuery.c_str(), sizeof(textBuf) - 1);
    }

    Result rc = swkbdCreate(&kbd, 0);
    if (R_SUCCEEDED(rc)) {
        swkbdConfigMakePresetDefault(&kbd);
        swkbdConfigSetHeaderText(&kbd, "Поиск среди установленных игр на Switch");
        swkbdConfigSetGuideText(&kbd, "Введите часть названия игры или Title ID");
        swkbdConfigSetOkButtonText(&kbd, "Найти");
        swkbdConfigSetInitialText(&kbd, textBuf);
        swkbdConfigSetStringLenMax(&kbd, 64);

        rc = swkbdShow(&kbd, textBuf, sizeof(textBuf));
        if (R_SUCCEEDED(rc)) {
            m_myGamesSearchQuery = std::string(textBuf);
            while (!m_myGamesSearchQuery.empty() && std::isspace(static_cast<unsigned char>(m_myGamesSearchQuery.back()))) {
                m_myGamesSearchQuery.pop_back();
            }
            while (!m_myGamesSearchQuery.empty() && std::isspace(static_cast<unsigned char>(m_myGamesSearchQuery.front()))) {
                m_myGamesSearchQuery.erase(m_myGamesSearchQuery.begin());
            }
            rebuildMyGamesFilter();
        }
        swkbdClose(&kbd);
    }
#else
    m_myGamesSearchQuery.clear();
    rebuildMyGamesFilter();
#endif
}

void App::startForwarderLinkSearch(const InstalledTitle& game) {
    if (game.titleId.empty() || game.titleId == "0000000000000000") return;

    m_linkingTargetTitleId = game.titleId;
    m_linkingTargetGameName = game.name;

    // Clean brackets, version suffixes and noise from forwarder / port title for smart auto-search
    std::string clean;
    bool inBracket = false;
    for (char c : game.name) {
        if (c == '[' || c == '(' || c == '{') { inBracket = true; continue; }
        if (c == ']' || c == ')' || c == '}') { inBracket = false; continue; }
        if (!inBracket) {
            if (c == '_' || c == '-' || c == ':' || c == '|') {
                clean.push_back(' ');
            } else {
                clean.push_back(c);
            }
        }
    }
    // Collapse multiple spaces and keep first 2 meaningful words for broad match
    std::vector<std::string> words;
    std::string curW;
    for (char c : clean) {
        if (std::isspace(static_cast<unsigned char>(c))) {
            if (!curW.empty()) {
                std::string low = utf8ToLower(curW);
                if (low != "switch" && low != "port" && low != "nsp" && low != "mod" && low != "ru" && low != "rus") {
                    words.push_back(curW);
                }
                curW.clear();
            }
        } else {
            curW.push_back(c);
        }
    }
    if (!curW.empty()) {
        std::string low = utf8ToLower(curW);
        if (low != "switch" && low != "port" && low != "nsp" && low != "mod" && low != "ru" && low != "rus") {
            words.push_back(curW);
        }
    }

    std::string autoQuery;
    for (size_t i = 0; i < std::min<size_t>(2, words.size()); ++i) {
        if (i > 0) autoQuery += " ";
        autoQuery += words[i];
    }

    m_catalogSortMode = CatalogSortMode::Default;
    m_catalogSearchQuery = autoQuery;
    rebuildCatalogFilter();
    if (m_filteredCatalogGames.empty() && !words.empty()) {
        m_catalogSearchQuery = words[0];
        rebuildCatalogFilter();
    }
    if (m_filteredCatalogGames.empty()) {
        m_catalogSearchQuery.clear();
        rebuildCatalogFilter();
    }

    m_activeTab = Tab::Catalog;
    m_homeFocusedTile = 0;
    m_tabTransitionAlpha = 140.0f;
    m_statusNotification = tr("Выберите любую игру в базе ([A] или [X]) для привязки к ", "Select any catalog game ([A] or [X]) to bind to ") + game.name;
    m_notificationFramesRemaining = 180;
}

void App::cancelForwarderLinkMode() {
    if (m_linkingTargetTitleId.empty()) return;
    m_linkingTargetTitleId.clear();
    m_linkingTargetGameName.clear();
    m_statusNotification = tr("Режим привязки форвардера завершен", "Forwarder binding mode closed");
    m_notificationFramesRemaining = 90;
}

void App::loadAppSettings() {
    if (!m_platform) return;
    std::string path = m_platform->getAppDirectory() + "/settings.json";
    std::error_code ec;
    if (!std::filesystem::exists(path, ec)) return;

    std::ifstream ifs(path);
    if (!ifs.is_open()) return;
    try {
        nlohmann::json j;
        ifs >> j;
        if (j.contains("autoRotateCoversOnBoot") && j["autoRotateCoversOnBoot"].is_boolean()) {
            m_autoRotateCoversOnBoot = j["autoRotateCoversOnBoot"].get<bool>();
        }
        if (j.contains("language") && j["language"].is_string()) {
            std::string lang = j["language"].get<std::string>();
            m_language = (lang == "en") ? Language::English : Language::Russian;
        }
    } catch (...) {}
}

void App::saveAppSettings() {
    if (!m_platform) return;
    std::string appDir = m_platform->getAppDirectory();
    std::error_code ec;
    std::filesystem::create_directories(appDir, ec);

    nlohmann::json j;
    j["version"] = 1;
    j["autoRotateCoversOnBoot"] = m_autoRotateCoversOnBoot;
    j["language"] = (m_language == Language::English) ? "en" : "ru";

    std::string path = appDir + "/settings.json";
    std::string tmp = path + ".tmp";
    std::ofstream ofs(tmp);
    if (ofs.is_open()) {
        ofs << j.dump(2);
        ofs.flush();
        ofs.close();
        std::filesystem::rename(tmp, path, ec);
    }
}

void App::detectNewInstalledGamesOnBoot() {
    if (!m_platform) return;
    m_newlyDetectedTitleIds.clear();

    std::string appDir = m_platform->getAppDirectory();
    std::string knownPath = appDir + "/known_titles.json";
    std::error_code ec;
    std::filesystem::create_directories(appDir, ec);

    std::set<std::string> previousKnown;
    bool hadKnownFile = std::filesystem::exists(knownPath, ec);
    if (hadKnownFile) {
        std::ifstream ifs(knownPath);
        if (ifs.is_open()) {
            try {
                nlohmann::json j;
                ifs >> j;
                if (j.contains("titles") && j["titles"].is_array()) {
                    for (const auto& item : j["titles"]) {
                        if (item.is_string()) {
                            previousKnown.insert(item.get<std::string>());
                        }
                    }
                }
            } catch (...) {}
        }
    }

    if (hadKnownFile) {
        for (const auto& g : m_installedGames) {
            if (g.titleId == "0000000000000000" || g.titleId.empty()) continue;
            if (previousKnown.count(g.titleId) == 0) {
                m_newlyDetectedTitleIds.insert(g.titleId);
            }
        }
    } else {
        // First run of v1.5.0: highlight uncovered installed games that have ready 4IFIR covers/icons
        for (const auto& g : m_installedGames) {
            if (g.titleId == "0000000000000000" || g.titleId.empty()) continue;
            if (!g.hasInstalledCover && !g.hasInstalledIcon && g.hasCatalogMatch && m_newlyDetectedTitleIds.size() < 12) {
                m_newlyDetectedTitleIds.insert(g.titleId);
            }
        }
    }

    // Save current snapshot of installed Title IDs for next launch comparison
    nlohmann::json outJ;
    outJ["version"] = 1;
    outJ["titles"] = nlohmann::json::array();
    for (const auto& g : m_installedGames) {
        if (!g.titleId.empty() && g.titleId != "0000000000000000") {
            outJ["titles"].push_back(g.titleId);
        }
    }
    std::string tmp = knownPath + ".tmp";
    std::ofstream ofs(tmp);
    if (ofs.is_open()) {
        ofs << outJ.dump(2);
        ofs.flush();
        ofs.close();
        std::filesystem::rename(tmp, knownPath, ec);
    }

    if (!m_newlyDetectedTitleIds.empty()) {
        m_statusNotification = tr("★ Обнаружены неоформленные игры на консоли: ", "★ Detected new games on console: ") +
                               std::to_string(m_newlyDetectedTitleIds.size()) +
                               tr(" шт. — нажмите [-] на Главной для Комбо-установки!", " — press [-] on Home for 1-Click Combo!");
        m_notificationFramesRemaining = 220;
    }
}

void App::runAutoCoverRotationOnBoot() {
    if (!m_autoRotateCoversOnBoot || !m_platform) return;

    int rotatedCount = 0;
    std::string covDir = m_platform->getCoversDirectory();
    uint32_t seed = static_cast<uint32_t>(std::time(nullptr));

    for (const auto& g : m_installedGames) {
        if (g.titleId.empty() || g.titleId == "0000000000000000") continue;
        if (g.installedCoversCount > 1) {
            std::vector<int> nonActiveIndices;
            for (const auto& cv : g.installedCoverVariants) {
                if (!cv.isActive && cv.index > 0) {
                    nonActiveIndices.push_back(cv.index);
                }
            }
            if (!nonActiveIndices.empty()) {
                int pick = nonActiveIndices[(seed + static_cast<uint32_t>(rotatedCount)) % nonActiveIndices.size()];
                if (Installer::switchActiveCover(covDir, g.titleId, pick)) {
                    rotatedCount++;
                }
            }
        }
    }

    if (rotatedCount > 0) {
        refreshInstalledGames();
        rebuildMyGamesFilter();
    }
}

void App::installAllNewlyDetectedGames() {
    if (m_newlyDetectedTitleIds.empty()) return;

    int queuedGames = 0;
    for (const auto& g : m_installedGames) {
        if (m_newlyDetectedTitleIds.count(g.titleId) > 0 && g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
            queueComboPack(g, g.catalogEntry, 0);
            queuedGames++;
        }
    }

    m_newlyDetectedTitleIds.clear();
    if (queuedGames > 0) {
        m_activeTab = Tab::Downloads;
        m_homeFocusedTile = 3;
        m_statusNotification = tr("★ Комбо-установка запущена для новинок: ", "★ Queued Combo Pack for new games: ") +
                               std::to_string(queuedGames) + tr(" шт.", " titles");
        m_notificationFramesRemaining = 180;
    } else {
        m_statusNotification = tr("Для новых игр пока нет прямых совпадений — используйте привязку в «Моих играх»",
                                  "No direct matches for new games — use Forwarder Link in My Games");
        m_notificationFramesRemaining = 160;
    }
}

int App::getSelectedCatalogVariantIndex(const GameCatalogEntry& entry) const {
    auto covVars = getCoverVariants(entry);
    if (covVars.empty()) return 0;
    auto it = m_catalogVariantIdx.find(entry.titleId);
    if (it == m_catalogVariantIdx.end()) return 0;
    return std::clamp(it->second, 0, static_cast<int>(covVars.size()) - 1);
}

void App::loadCatalogDockPreview(const GameCatalogEntry& entry, const Variant& variant) {
#ifdef HAS_SDL2
    m_videoPlayer.close();
    m_cancelCollectionThumb.store(true);

    if (m_videoIconDockTexture) {
        SDL_DestroyTexture(m_videoIconDockTexture);
        m_videoIconDockTexture = nullptr;
    }

    std::string dockKey = "catdock_" + entry.titleId + "_" + variant.id;
    m_catalogDockCurrentKey = dockKey;
    m_collectionCurrentThumbVariantId = dockKey;

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string thumbFile = thumbDir + "/" + entry.titleId + "_" + variant.id + ".jpg";
    std::string vidFile = thumbDir + "/" + entry.titleId + "_" + variant.id + ".mp4";

    // 1. Если этот вариант уже установлен на SD-карте или лежит в кэше — мгновенно запускаем видео!
    std::string installedPath = m_platform->getCoversDirectory() + "/" + Config::getTargetCoverFileName(entry.titleId);
    std::string activeVarId = InstalledRegistry::instance().getVariantId(entry.titleId);
    if (activeVarId == variant.id && std::filesystem::exists(installedPath, ec)) {
        m_videoPlayer.open(installedPath, m_renderer);
    } else if (std::filesystem::exists(vidFile, ec) && std::filesystem::file_size(vidFile, ec) >= 50000) {
        if (!m_videoPlayer.open(vidFile, m_renderer)) {
            std::filesystem::remove(vidFile, ec);
        }
    }

    // 2. Мгновенно подхватываем статическую миниатюру с диска или из кэша строк
    bool hasCachedThumb = (findCachedThumbTexture(entry.titleId, variant, false) != nullptr);
    if (std::filesystem::exists(thumbFile, ec) && validateImageFile(thumbFile)) {
        m_videoIconDockTexture = loadTextureFromFile(m_renderer, thumbFile);
        if (!m_videoIconDockTexture) {
            std::filesystem::remove(thumbFile, ec);
        } else {
            hasCachedThumb = true;
        }
    } else if (std::filesystem::exists(thumbFile, ec)) {
        std::filesystem::remove(thumbFile, ec);
    }

    if (m_videoPlayer.isPlaying()) {
        m_collectionThumbLoading = false;
        m_collectionVideoDownloading = false;
        m_collectionTransferQueued = false;
        return;
    }

    std::string videoUrl = variant.url;
    std::string thumbUrl = variant.previewUrl;
    if (thumbUrl.empty()) {
        std::string drvId = extractDriveIdFromUrl(videoUrl);
        if (!drvId.empty()) {
            thumbUrl = "https://drive.google.com/thumbnail?id=" + drvId + "&sz=w640";
        }
    }

    m_collectionDownloadBytes.store(0);
    m_collectionDownloadTotal.store(variant.sizeBytes > 0 ? variant.sizeBytes : 3500 * 1024);
    m_collectionThumbLoading = !hasCachedThumb;
    m_collectionVideoDownloading = !videoUrl.empty();

    m_queuedCollThumbUrl = thumbUrl;
    m_queuedCollVideoUrl = videoUrl;
    m_queuedCollThumbFile = thumbFile;
    m_queuedCollVidFile = vidFile;
    m_queuedCollKey = dockKey;
    m_queuedCollIsIcon = false;
    m_queuedCollForDock = true;
    m_collectionTransferQueued = true;

    updateAsyncPreviewWorkers();
#else
    (void)entry; (void)variant;
#endif
}

} // namespace ui
} // namespace h3h
