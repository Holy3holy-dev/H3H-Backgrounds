
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
    sanitizeThumbCache();

    renderBootSplash("Загрузка базы каталога видеофонов и иконок...", 50.0);

    // Load initial catalog (cache -> romfs -> local dev)
    std::string catError;
    if (!m_catalogManager.loadFromFile(m_platform->getAppDirectory() + "/cache.json", catError)) {
        if (!m_catalogManager.loadFromFile("romfs:/catalog.json", catError)) {
            m_catalogManager.loadFromFile("catalog/data/catalog.json", catError);
        }
    }

    renderBootSplash("Сканирование установленных игр Nintendo Switch...", 80.0);

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

        // If current version is already up to date, skip download completely
        if (latestVer == Config::APP_VERSION) {
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
    if ((m_isFullscreenPreview || m_isCollectionBrowserOpen || m_activeTab == Tab::VideoIcons) &&
        (m_videoPlayer.isPlaying() || m_previewTexture != nullptr || m_collectionThumbTexture != nullptr || m_videoIconDockTexture != nullptr)) {
        m_previewFadeAlpha += (255.0f - m_previewFadeAlpha) * 0.20f;
    }

    // 8. Smooth 60 FPS list selection Y-interpolation across all tabs
    float targetCatY = 136.0f + static_cast<float>(std::clamp(m_catalogSelectedIndex - m_catalogScrollOffset, 0, 4)) * 98.0f;
    m_smoothCatalogSelY += (targetCatY - m_smoothCatalogSelY) * 0.30f;

    float targetIcoY = 136.0f + static_cast<float>(std::clamp(m_videoIconsSelectedIndex - m_videoIconsScrollOffset, 0, 4)) * 98.0f;
    m_smoothVideoIconsSelY += (targetIcoY - m_smoothVideoIconsSelY) * 0.30f;

    float targetMyGamesY = 105.0f + static_cast<float>(std::clamp(m_myGamesSelectedIndex - m_myGamesScrollOffset, 0, 7)) * 66.0f;
    m_smoothMyGamesSelY += (targetMyGamesY - m_smoothMyGamesSelY) * 0.30f;

    float targetDlY = 160.0f + static_cast<float>(std::clamp(m_downloadsSelectedIndex - m_downloadsScrollOffset, 0, 4)) * 94.0f;
    m_smoothDownloadsSelY += (targetDlY - m_smoothDownloadsSelY) * 0.30f;

    float targetSettingsY = 236.0f + static_cast<float>(std::clamp(m_settingsSelectedIndex, 0, 6)) * 54.0f;
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
    if (!pendingDockThumb.empty() && m_renderer && m_activeTab == Tab::VideoIcons) {
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
    if (!pendingDockVideo.empty() && m_renderer && m_activeTab == Tab::VideoIcons && !m_isFullscreenPreview) {
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
    if ((m_isFullscreenPreview || m_isCollectionBrowserOpen || m_activeTab == Tab::VideoIcons) && m_videoPlayer.isPlaying()) {
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
                            if (latestVer != Config::APP_VERSION) {
                                std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
                                m_startupUpdateLatestVer = latestVer;
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
        {
            std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
            newVer = std::move(m_startupUpdateLatestVer);
        }
        if (!newVer.empty()) {
            m_statusNotification = (m_language == Language::Russian)
                ? ("Обнаружено обновление v" + newVer + "! Нажмите [-] в Настройках")
                : ("New update v" + newVer + " detected! Press [-] in Settings");
            m_notificationFramesRemaining = 240;
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
        true
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
                InstalledRegistry::instance().setVariantId(
                    m_platform->getAppDirectory(),
                    currentTask.titleId,
                    currentTask.variant.id
                );
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
    m_statusNotification = (m_language == Language::Russian)
        ? ("Добавлено в очередь: " + title.name + " (" + variant.name + ")")
        : ("Added to queue: " + title.name + " (" + variant.name + ")");
    m_notificationFramesRemaining = 180;
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

    // Standard Nintendo Switch [B] button
    if (button == 1 /* B - Back */) {
        if (m_activeTab == Tab::MyGames && m_myGamesActivePane == MyGamesPane::VariantsList) {
            m_myGamesActivePane = MyGamesPane::GamesList;
            return;
        }
        if (m_activeTab != Tab::Home) {
            if (m_activeTab == Tab::VideoIcons) {
                m_cancelCollectionThumb.store(true);
                m_videoPlayer.close();
            }
            m_activeTab = Tab::Home;
            return;
        }
    }

    // Tab switching with Shoulder buttons (L/R) - Active in Home, MyGames, Downloads, Settings
    if (m_activeTab != Tab::Catalog) {
        if (button == 9 /* LEFTSHOULDER */) {
            uint32_t now = SDL_GetTicks();
            if (now - m_lastTabSwitchTime > 150) {
                if (m_activeTab == Tab::Home) {
                    m_homeFocusedTile = (m_homeFocusedTile == 0) ? 4 : m_homeFocusedTile - 1;
                } else {
                    if (m_activeTab == Tab::VideoIcons) {
                        m_cancelCollectionThumb.store(true);
                        m_videoPlayer.close();
                    }
                    int tabInt = static_cast<int>(m_activeTab);
                    tabInt = (tabInt <= 1) ? 5 : tabInt - 1;
                    m_activeTab = static_cast<Tab>(tabInt);
                    if (m_activeTab == Tab::VideoIcons) {
                        rebuildVideoIconsFilter();
                        m_videoIconDockDirty = true;
                        m_lastVideoIconMoveTime = SDL_GetTicks();
                    }
                }
                m_lastTabSwitchTime = now;
            }
            return;
        }
        if (button == 10 /* RIGHTSHOULDER */) {
            uint32_t now = SDL_GetTicks();
            if (now - m_lastTabSwitchTime > 150) {
                if (m_activeTab == Tab::Home) {
                    m_homeFocusedTile = (m_homeFocusedTile == 4) ? 0 : m_homeFocusedTile + 1;
                } else {
                    if (m_activeTab == Tab::VideoIcons) {
                        m_cancelCollectionThumb.store(true);
                        m_videoPlayer.close();
                    }
                    int tabInt = static_cast<int>(m_activeTab);
                    tabInt = (tabInt >= 5) ? 1 : tabInt + 1;
                    m_activeTab = static_cast<Tab>(tabInt);
                    if (m_activeTab == Tab::VideoIcons) {
                        rebuildVideoIconsFilter();
                        m_videoIconDockDirty = true;
                        m_lastVideoIconMoveTime = SDL_GetTicks();
                    }
                }
                m_lastTabSwitchTime = now;
            }
            return;
        }
    }

    // View-specific input handling
    if (m_activeTab == Tab::Home) {
        if (button == 1 /* B - Exit to hbmenu */) {
            m_running = false;
            return;
        }
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
                    break;
                case 1:
                    m_activeTab = Tab::VideoIcons;
                    rebuildVideoIconsFilter();
                    m_videoIconDockDirty = true;
                    m_lastVideoIconMoveTime = SDL_GetTicks();
                    break;
                case 2:
                    m_activeTab = Tab::MyGames;
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
        if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
            return;
        }
        if (button == 2 /* X - Refresh */) {
            fetchRemoteCatalog();
            return;
        }
        if (button == 4 /* MINUS (-) - Refresh Catalog */) {
            fetchRemoteCatalog();
            return;
        }
        if (button == 6 /* START (+) - Integrity Check */) {
            runIntegrityCheck();
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
        if (button == 1 /* B - Back to Home */) {
            m_videoPlayer.close();
            m_activeTab = Tab::Home;
            return;
        }
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
        if (button == 15 /* ZL - Page Up 5 */) {
            m_videoIconsSelectedIndex = std::max(0, m_videoIconsSelectedIndex - 5);
            m_videoIconsScrollOffset = std::max(0, m_videoIconsScrollOffset - 5);
            notifyVideoIconFocusChanged();
            return;
        }
        if (button == 16 /* ZR - Page Down 5 */) {
            if (total > 0) {
                m_videoIconsSelectedIndex = std::min(total - 1, m_videoIconsSelectedIndex + 5);
                m_videoIconsScrollOffset = std::min(std::max(0, total - 5), m_videoIconsScrollOffset + 5);
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
            return;
        }
        if (button == 2 /* X - Fullscreen Switch Home Screen Preview */) {
            if (m_videoIconsSelectedIndex >= 0 && m_videoIconsSelectedIndex < total) {
                const auto& entry = m_filteredVideoIcons[m_videoIconsSelectedIndex];
                int vIdx = getSelectedVideoIconVariantIndex(entry);
                openFullscreenVideoIconPreview(entry, vIdx);
            }
            return;
        }
        if (button == 3 /* Y - Search keyboard */) {
            openVideoIconsKeyboard();
            return;
        }
        if (button == 4 /* MINUS (-) - Filter toggle */) {
            m_videoIconsFilterMode = (m_videoIconsFilterMode + 1) % 3;
            rebuildVideoIconsFilter();
            notifyVideoIconFocusChanged();
            return;
        }
        if (button == 6 /* START (+) - Delete installed video icon */) {
            if (m_videoIconsSelectedIndex >= 0 && m_videoIconsSelectedIndex < total) {
                const auto& entry = m_filteredVideoIcons[m_videoIconsSelectedIndex];
                if (isIconInstalled(entry.titleId)) {
                    executeDeleteIcon(entry.titleId);
                }
            }
            return;
        }
        return;
    } else if (m_activeTab == Tab::MyGames) {
        // Feature 3: [+] (START) or L3 (Left Stick click) opens 4IFIR SD Recordings browser immediately
        if (button == 6 /* START (+) */ || button == 7 /* SDL_CONTROLLER_BUTTON_LEFTSTICK (L3) */) {
            if (!m_installedGames.empty()) {
                int idx = std::clamp(m_myGamesSelectedIndex, 0, static_cast<int>(m_installedGames.size()) - 1);
                const auto& g = m_installedGames[idx];
                openRecordingsBrowser(g.titleId, g.name);
                return;
            } else {
                m_statusNotification = "Нет установленных игр для привязки";
                m_notificationFramesRemaining = 120;
                return;
            }
        }
        // [-] (MINUS) restores .bak backup if available for selected game
        if (button == 4 /* MINUS (-) */) {
            if (!m_installedGames.empty()) {
                int idx = std::clamp(m_myGamesSelectedIndex, 0, static_cast<int>(m_installedGames.size()) - 1);
                const auto& g = m_installedGames[idx];
                if (g.hasBackup) {
                    m_pendingActionTitleId = g.titleId;
                    m_activeDialog = DialogType::ConfirmRestore;
                    m_dialogOpenedAt = SDL_GetTicks();
                    m_dialogTitle = "Восстановление резервной копии (.bak)";
                    m_dialogMessage = "Восстановить предыдущий видеофон из резервной копии для игры " + g.name + "?";
                    m_dialogFocus = 0;
                    return;
                }
            }
        }

        if (m_myGamesActivePane == MyGamesPane::GamesList) {
            // LEFT COLUMN: Games List navigation
            if (button == 1 /* B - Back to Home */) {
                m_activeTab = Tab::Home;
                return;
            }
            if (button == 8 /* R3 - Toggle Batch Selection */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    toggleBatchSelection(m_installedGames[m_myGamesSelectedIndex].titleId);
                }
                return;
            }
            if (button == 11 /* DPAD_UP */) {
                if (m_myGamesSelectedIndex > 0) {
                    m_myGamesSelectedIndex--;
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
            } else if (button == 12 /* DPAD_DOWN */) {
                if (m_myGamesSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                    m_myGamesSelectedIndex++;
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
            } else if (button == 15 /* ZL - Fast Page Up 10 */) {
                m_myGamesSelectedIndex = std::max(0, m_myGamesSelectedIndex - 10);
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
                return;
            } else if (button == 16 /* ZR - Fast Page Down 10 */) {
                if (!m_installedGames.empty()) {
                    m_myGamesSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_myGamesSelectedIndex + 10);
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
                return;
            } else if (button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) {
                // Move focus to right variants column or open collection browser
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                        openCollectionBrowser(g.catalogEntry);
                    } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_myGamesActivePane = MyGamesPane::VariantsList;
                        m_selectedVariantIndex = 0;
                    } else {
                        m_statusNotification = (m_language == Language::Russian)
                            ? "Для этой игры пока нет видеофонов в каталоге"
                            : "No video themes available for this game yet";
                        m_notificationFramesRemaining = 120;
                    }
                }
            } else if (button == 2 /* X - Fullscreen Preview or Open Catalog */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        openFullscreenPreviewForGame(g, m_selectedVariantIndex);
                    } else {
                        m_activeTab = Tab::Catalog;
                    }
                }
            } else if (button == 3 /* Y - Delete Cover/Icon or Install Missing */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasInstalledCover || g.hasInstalledIcon) {
                        m_pendingActionTitleId = g.titleId;
                        m_activeDialog = DialogType::ConfirmDelete;
                        m_dialogOpenedAt = SDL_GetTicks();
                        if (g.hasInstalledCover && g.hasInstalledIcon) {
                            m_dialogTitle = "Удаление фона и видеоиконки";
                            m_dialogMessage = "Выберите, что удалить для игры " + g.name + ":\n[A] Фон + Иконка   |   [X] Только иконку   |   [Y] Только фон";
                        } else if (g.hasInstalledCover) {
                            m_dialogTitle = "Удаление активного фона";
                            m_dialogMessage = "Удалить установленный видеофон для игры " + g.name + "?\n\n(Фон будет удалён с консоли, а варианты в каталоге останутся доступны для повторной установки в любой момент)";
                        } else {
                            m_dialogTitle = "Удаление видеоиконки";
                            m_dialogMessage = "Удалить установленную видеоиконку 4IFIR (256x256) для игры " + g.name + "?";
                        }
                        m_dialogFocus = 0;
                    } else {
                        installAllMissing();
                    }
                }
            }
        } else if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            // RIGHT COLUMN: Variants navigation
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
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
                } else if (button == 13 /* DPAD_LEFT */ || button == 1 /* B */) {
                    // Return focus back to left games column
                    m_myGamesActivePane = MyGamesPane::GamesList;
                } else if (button == 0 /* A - Install Variant */) {
                    const auto& selV = g.catalogEntry.variants[m_selectedVariantIndex];
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
                } else if (button == 2 /* X - Fullscreen Preview */) {
                    const auto& selV = g.catalogEntry.variants[m_selectedVariantIndex];
                    bool isPureIcon = (selV.id.rfind("icon-", 0) == 0) || (selV.width == 256 && selV.height == 256);
                    if (isPureIcon) {
                        auto uIcons = getUniqueIconVariants(g.catalogEntry);
                        int icoIdx = 0;
                        std::string wantUrl = !selV.iconUrl.empty() ? selV.iconUrl : selV.url;
                        for (size_t k = 0; k < uIcons.size(); ++k) {
                            if (uIcons[k].iconUrl == wantUrl || uIcons[k].id == selV.id) {
                                icoIdx = static_cast<int>(k);
                                break;
                            }
                        }
                        openFullscreenVideoIconPreview(g.catalogEntry, icoIdx);
                    } else {
                        openFullscreenPreviewForGame(g, m_selectedVariantIndex);
                    }
                } else if (button == 3 /* Y - Delete */) {
                    if (g.hasInstalledCover || g.hasInstalledIcon) {
                        m_pendingActionTitleId = g.titleId;
                        m_activeDialog = DialogType::ConfirmDelete;
                        m_dialogOpenedAt = SDL_GetTicks();
                        if (g.hasInstalledCover && g.hasInstalledIcon) {
                            m_dialogTitle = "Удаление фона и видеоиконки";
                            m_dialogMessage = "Выберите, что удалить для игры " + g.name + ":\n[A] Фон + Иконка   |   [X] Только иконку   |   [Y] Только фон";
                        } else if (g.hasInstalledCover) {
                            m_dialogTitle = "Удаление активного фона";
                            m_dialogMessage = "Удалить установленный видеофон для игры " + g.name + "?\n\n(Фон будет удалён с консоли, а варианты в каталоге останутся доступны для повторной установки в любой момент)";
                        } else {
                            m_dialogTitle = "Удаление видеоиконки";
                            m_dialogMessage = "Удалить установленную видеоиконку 4IFIR (256x256) для игры " + g.name + "?";
                        }
                        m_dialogFocus = 0;
                    }
                }
            }
        }
    } else if (m_activeTab == Tab::Catalog) {
        int totalGames = static_cast<int>(m_filteredCatalogGames.size());

        // [B] - Back to Home dashboard
        if (button == 1 /* B */) {
            m_activeTab = Tab::Home;
            return;
        }

        // [L] - Switch to "Весь каталог" tab
        if (button == 9 /* L / LEFTSHOULDER */ || button == 7 /* L3 */) {
            if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
                m_catalogSortMode = CatalogSortMode::Default;
                m_activeCategoryName = "Весь каталог";
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                m_statusNotification = "Каталог: Весь каталог";
                m_notificationFramesRemaining = 90;
            }
            return;
        }

        // [R] - Switch to "Избранное" tab
        if (button == 10 /* R / RIGHTSHOULDER */ || button == 8 /* R3 */) {
            if (m_catalogSortMode != CatalogSortMode::FavoritesOnly) {
                m_catalogSortMode = CatalogSortMode::FavoritesOnly;
                m_activeCategoryName = "Избранное";
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                m_statusNotification = "Каталог: Избранное";
                m_notificationFramesRemaining = 90;
            }
            return;
        }

        // [X] - Cycle Sort Mode
        if (button == 2 /* X */) {
            cycleCatalogSortMode();
            return;
        }

        // [Y] - Open Horizon Software Keyboard for Search
        if (button == 3 /* Y */) {
            openCatalogKeyboard();
            return;
        }

        // [-] (Minus) - Toggle Favorite for selected game
        if (button == 4 /* MINUS */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
                if (!curGame.variants.empty()) {
                    bool wasFav = hasGameFavorites(curGame.titleId);
                    if (wasFav) {
                        for (const auto& v : curGame.variants) {
                            m_favoriteKeys.erase(curGame.titleId + ":" + v.id);
                            m_favoriteKeys.erase(v.id);
                        }
                        m_statusNotification = "Удалено из избранного: " + curGame.title;
                    } else {
                        m_favoriteKeys.insert(curGame.titleId + ":" + curGame.variants[0].id);
                        m_statusNotification = "Добавлено в избранное ★: " + curGame.title;
                    }
                    m_notificationFramesRemaining = 90;
                    saveFavorites();
                    rebuildCatalogFilter();
                }
            } else {
                fetchRemoteCatalog();
            }
            return;
        }

        // Navigation
        if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) m_catalogSelectedIndex--;
            return;
        }
        if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) m_catalogSelectedIndex++;
            return;
        }
        if (button == 13 /* DPAD_LEFT - Page Up 5 */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
            return;
        }
        if (button == 14 /* DPAD_RIGHT - Page Down 5 */) {
            if (totalGames > 0) m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
            return;
        }

        // [ZL] - Quick Fullscreen Preview (opens Icon preview if IconsOnly filter is active, else Cover preview)
        if (button == 15 /* ZL */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
                if (!curGame.variants.empty()) {
                    if (m_catalogSortMode == CatalogSortMode::IconsOnly && !getUniqueIconVariants(curGame).empty()) {
                        openFullscreenVideoIconPreview(curGame, 0);
                    } else {
                        openFullscreenPreviewForCatalogGame(curGame, 0);
                    }
                }
            }
            return;
        }

        // [ZR] - Direct Video Icon 256x256 Preview for the selected Catalog game (if it has an icon)
        if (button == 16 /* ZR */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
                if (!getUniqueIconVariants(curGame).empty()) {
                    openFullscreenVideoIconPreview(curGame, 0);
                } else if (!curGame.variants.empty()) {
                    openFullscreenPreviewForCatalogGame(curGame, 0);
                }
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
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 0 /* A - Retry selected failed task or all failed tasks */) {
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
        } else if (button == 15 /* ZL - Fast Page Up 5 */) {
            m_downloadsSelectedIndex = std::max(0, m_downloadsSelectedIndex - 5);
            m_downloadsScrollOffset = std::max(0, m_downloadsScrollOffset - 5);
        } else if (button == 16 /* ZR - Fast Page Down 5 */) {
            int qSize = 0;
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                qSize = static_cast<int>(m_downloadQueue.size());
            }
            if (qSize > 0) {
                m_downloadsSelectedIndex = std::min(qSize - 1, m_downloadsSelectedIndex + 5);
                int maxOff = std::max(0, qSize - 5);
                m_downloadsScrollOffset = std::min(maxOff, m_downloadsScrollOffset + 5);
            }
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        }
    } else if (m_activeTab == Tab::Settings) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_settingsSelectedIndex > 0) m_settingsSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_settingsSelectedIndex < 6) m_settingsSelectedIndex++;
        } else if (button == 0 /* A - Activate Selected Setting */) {
            switch (m_settingsSelectedIndex) {
                case 0: // Check & Update NRO
                    updateApplicationNro();
                    break;
                case 1: // Refresh Catalog
                    fetchRemoteCatalog();
                    break;
                case 2: // Clear thumbnail previews cache
                    clearThumbnailCache();
                    break;
                case 3: // Clear video player cache
                    clearVideoPreviewCache();
                    break;
                case 4: // Clear Local Catalog Cache (cache.json)
                    m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
                    refreshInstalledGames();
                    m_statusNotification = getStrings(m_language).cacheClearedMsg;
                    m_notificationFramesRemaining = 120;
                    break;
                case 5: // Integrity check
                    runIntegrityCheck();
                    break;
                case 6: // Toggle Language
                    m_language = (m_language == Language::Russian) ? Language::English : Language::Russian;
                    m_statusNotification = (m_language == Language::Russian) ? "Язык интерфейса: Русский" : "Interface language: English";
                    m_notificationFramesRemaining = 120;
                    break;
            }
        } else if (button == 2 /* X - Clear Cache */) {
            m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
            refreshInstalledGames();
            m_statusNotification = getStrings(m_language).cacheClearedMsg;
            m_notificationFramesRemaining = 120;
        } else if (button == 3 /* Y - Refresh Catalog */) {
            fetchRemoteCatalog();
        } else if (button == 6 /* START / Plus - Update App NRO */) {
            updateApplicationNro();
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

    if (m_activeDialog != DialogType::None) {
        renderDialog();
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
    drawText(verText, nxX + nxW + 10, 24, Theme::COLOR_TEXT_MUTED, 13);

    // Variant D: Live Active Download Pill in Header (visible from any tab when downloading)
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
        int pillX = 485;
        int pillY = 16;
        int pillW = 280;
        int pillH = 32;
        drawRoundedRect(pillX, pillY, pillW, pillH, 8, {0x0E, 0x17, 0x26, 0xF2});
        drawNeonRoundedOutline(pillX, pillY, pillW, pillH, 8, 1);
        drawLoadingSpinner(pillX + 18, pillY + 16, 6, Theme::COLOR_FOCUS_CYAN);
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
        drawText(dlBuf, pillX + 32, pillY + 8, Theme::COLOR_FOCUS_CYAN, 11, pillW - 40);
    }

    // Right Side Metadata
    size_t catGames = m_catalogManager.getGamesCount();
    size_t catIcons = m_videoIconsCatalog.size();
    std::string dateStr = m_catalogManager.getUpdatedAt();
    if (dateStr.size() >= 10) dateStr = dateStr.substr(0, 10);
    else dateStr = "28.10.2026";

    std::string metaLine1 = (m_language == Language::Russian)
        ? ("Каталог: " + std::to_string(catGames) + " игр (" + std::to_string(catIcons) + " иконок) • Обновлен: " + dateStr)
        : ("Catalog: " + std::to_string(catGames) + " games (" + std::to_string(catIcons) + " icons) • Updated: " + dateStr);

    double freeSdGb = static_cast<double>(m_sysInfo.freeStorageBytes) / (1024.0 * 1024.0 * 1024.0);
    double totalSdGb = static_cast<double>(m_sysInfo.totalStorageBytes) / (1024.0 * 1024.0 * 1024.0);
    if (totalSdGb <= 0.1) {
        totalSdGb = 220.1;
        freeSdGb = 49.2;
    }
    char sdBuf[128];
    std::snprintf(sdBuf, sizeof(sdBuf), "SD: %.1f GB / %.1f GB • 4IFIR HEVC", freeSdGb, totalSdGb);
    std::string metaLine2 = sdBuf;

    drawTextRight(metaLine1, 1244, 14, Theme::COLOR_TEXT_SECONDARY, 13);
    drawTextRight(metaLine2, 1244, 36, Theme::COLOR_TEXT_MUTED, 12);
}

void App::renderFooter() {
    const auto& s = getStrings(m_language);
    (void)s;

    // Bottom Bar Background (matching TorrentShopNX Footer)
    drawRect(0, 665, Theme::SCREEN_WIDTH, 55, Theme::COLOR_STATUS_BAR_BG);
    drawRect(0, 665, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // Left: Battery glyph & %, Wi-Fi, Clock
    int battX = 30;
    drawRoundedRect(battX, 683, 30, 16, 3, {0x1C, 0x24, 0x33, 0xFF});
    drawRoundedOutline(battX, 683, 30, 16, 3, Theme::COLOR_TEXT_MUTED, Theme::COLOR_TEXT_MUTED, 1);
    drawRoundedRect(battX + 30, 687, 3, 8, 1, Theme::COLOR_TEXT_MUTED); // nub
    int fillW = std::clamp((m_sysInfo.batteryPercent * 26) / 100, 2, 26);
    Color battCol = (m_sysInfo.batteryPercent < 20) ? Theme::COLOR_DANGER : (m_sysInfo.batteryPercent < 50 ? Theme::COLOR_WARNING : Theme::COLOR_SUCCESS);
    drawRoundedRect(battX + 2, 685, fillW, 12, 2, battCol);

    std::string battStr = std::to_string(m_sysInfo.batteryPercent) + "%";
    drawText(battStr, battX + 38, 683, Theme::COLOR_TEXT_PRIMARY, 13);
    int curLeftX = battX + 38 + measureTextWidth(battStr, 13) + 16;

    // Crisp Vector Wi-Fi Status
    drawWifiIcon(curLeftX + 6, 691, m_sysInfo.isNetworkConnected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED);
    curLeftX += 18;

    std::string netStr = m_sysInfo.isNetworkConnected ? tr("Онлайн", "Online") : tr("Автономно", "Offline");
    drawText(netStr, curLeftX, 683, m_sysInfo.isNetworkConnected ? Theme::COLOR_SUCCESS : Theme::COLOR_TEXT_MUTED, 13);
    curLeftX += measureTextWidth(netStr, 13) + 18;

    // Digital Clock
    std::time_t now = std::time(nullptr);
    std::tm* tmLocal = std::localtime(&now);
    char timeBuf[32];
    if (tmLocal) {
        std::strftime(timeBuf, sizeof(timeBuf), "%H:%M:%S", tmLocal);
    } else {
        std::snprintf(timeBuf, sizeof(timeBuf), "14:33:44");
    }
    drawText(timeBuf, curLeftX, 683, Theme::COLOR_TEXT_PRIMARY, 14);

    // Right: Circular Joy-Con Button Badges laid out from right to left
    int curRightX = 1244;
    auto drawPrompt = [&](const std::string& key, const std::string& label, Color badgeCol = Theme::COLOR_TEXT_PRIMARY) {
        int labelW = measureTextWidth(label, 13);
        int itemW = 22 + 8 + labelW;
        int itemX = curRightX - itemW;
        drawButtonBadge(itemX, 682, key, label, badgeCol);
        curRightX = itemX - 20;
    };

    if (m_activeTab == Tab::Home) {
        drawPrompt("A", tr("Открыть", "Open"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Выход", "Exit"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("Y", tr("Установить все", "Install All"), Theme::COLOR_FOCUS_PINK);
        drawPrompt("X", tr("Обновить базу", "Refresh DB"), Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("+", tr("Проверка SD", "Verify SD"), Theme::COLOR_TEXT_PRIMARY);
    } else if (m_activeTab == Tab::VideoIcons) {
        drawPrompt("A", tr("Установить", "Install"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Назад", "Back"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("X", tr("На весь экран", "Fullscreen"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("◄/►", tr("Вариант", "Variant"), Theme::COLOR_FOCUS_PINK);
        drawPrompt("Y", tr("Поиск", "Search"), Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("-", tr("Фильтр", "Filter"), Theme::COLOR_TEXT_PRIMARY);
        if (m_videoIconsSelectedIndex >= 0 && m_videoIconsSelectedIndex < static_cast<int>(m_filteredVideoIcons.size())) {
            if (isIconInstalled(m_filteredVideoIcons[m_videoIconsSelectedIndex].titleId)) {
                drawPrompt("+", tr("Удалить", "Delete"), Theme::COLOR_DANGER);
            }
        }
    } else if (m_activeTab == Tab::Catalog) {
        drawPrompt("A", tr("Выбрать", "Select"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Назад", "Back"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("ZL", tr("Просмотр", "Preview"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("-", tr("В избр. ★", "Fav ★"), Theme::COLOR_FOCUS_PINK);
        drawPrompt("L/R", tr("Разделы", "Tabs"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("Y", tr("Поиск", "Search"), Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("X", tr("Сортировка", "Sort"), Theme::COLOR_TEXT_PRIMARY);
    } else if (m_activeTab == Tab::MyGames) {
        drawPrompt("A", tr("Выбрать", "Select"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Назад", "Back"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("Y", tr("Удалить", "Delete"), Theme::COLOR_DANGER);
        drawPrompt("X", tr("Видео", "Video"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("+", tr("Записи SD", "SD Clips"), Theme::COLOR_FOCUS_CYAN);
    } else if (m_activeTab == Tab::Downloads) {
        drawPrompt("A", tr("Повторить", "Retry"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Назад", "Back"), Theme::COLOR_TEXT_MUTED);
        drawPrompt("-", tr("Убрать", "Remove"), Theme::COLOR_FOCUS_PINK);
        drawPrompt("Y", tr("Все недостающие", "All Missing"), Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("X", tr("Очистить", "Clear"), Theme::COLOR_DANGER);
    } else if (m_activeTab == Tab::Settings) {
        drawPrompt("A", tr("Применить", "Apply"), Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", tr("Назад", "Back"), Theme::COLOR_TEXT_MUTED);
    }
}

void App::renderTabHome() {
    const auto& s = getStrings(m_language);
    (void)s;

    // 1. Center 5x Dashboard Tiles (w = 225, h = 208, gap = 14, title inside, smooth 60 FPS spring scale via m_tileAnimScale)
    struct TileDef {
        int index;
        std::string title;
    };

    TileDef tiles[5] = {
        {0, tr("Каталог", "Catalog")},
        {1, tr("Видеоиконки", "Video Icons")},
        {2, tr("Менеджер игр", "My Games")},
        {3, tr("Загрузки", "Downloads")},
        {4, tr("Настройки", "Settings")}
    };

    int tileW = 225;
    int tileH = 208;
    int tileGap = 14;
    int totalRowW = 5 * tileW + 4 * tileGap;
    int tileStartX = (Theme::SCREEN_WIDTH - totalRowW) / 2;
    int tileStartY = 104;

    for (int i = 0; i < 5; ++i) {
        bool isFocused = (m_homeFocusedTile == i);
        int tx = tileStartX + i * (tileW + tileGap);
        int ty = tileStartY;
        drawDashboardTile(tx, ty, tileW, tileH, tiles[i].index, tiles[i].title, "", isFocused);
    }

    // 2. Bottom Summary Panel (2 Wide Informative Cards)
    int boxX = 48;
    int boxY = 368;
    int boxW = 1184;
    int boxH = 258;

    drawGlassCard(boxX, boxY, boxW, boxH, false, false);

    // Outer Container Header
    drawRoundedRect(boxX + 24, boxY + 20, 4, 16, 2, Theme::COLOR_FOCUS_CYAN);
    std::string headerTitle = tr("КАТАЛОГ ВИДЕОФОНОВ 4IFIR ДЛЯ NINTENDO SWITCH", "4IFIR VIDEO BACKGROUNDS CATALOG FOR NINTENDO SWITCH");
    if (m_homeFocusedTile == 1) {
        headerTitle = tr("КАТАЛОГ ВИДЕОИКОНОК 256x256 (ЖИВОЙ МАКЕТ SWITCH)", "256x256 VIDEO ICONS CATALOG (LIVE SWITCH DOCK)");
    } else if (m_homeFocusedTile == 2) {
        headerTitle = tr("УСТАНОВЛЕННЫЕ ИГРЫ И АКТИВНЫЕ ВИДЕОФОНЫ НА КОНСОЛИ", "INSTALLED GAMES & ACTIVE CONSOLE WALLPAPERS");
    } else if (m_homeFocusedTile == 3) {
        headerTitle = tr("МЕНЕДЖЕР ПОТОКОВЫХ ЗАГРУЗОК И ОЧЕРЕДЬ", "STREAMING DOWNLOAD MANAGER & QUEUE");
    } else if (m_homeFocusedTile == 4) {
        headerTitle = tr("СИСТЕМНЫЕ НАСТРОЙКИ, КЭШ И ОБНОВЛЕНИЕ OTA", "SYSTEM SETTINGS, CACHE & OTA UPDATES");
    }
    drawText(headerTitle, boxX + 36, boxY + 18, Theme::COLOR_FOCUS_CYAN, 13);

    int subY = boxY + 52;
    int subH = 184;
    int cardW = 560;
    int cardGap = 24;
    int sc1X = boxX + 20;
    int sc2X = sc1X + cardW + cardGap;

    // Sub-card 1: Library Stats (560px wide)
    drawGlassCard(sc1X, subY, cardW, subH, false, false);
    drawText(m_homeFocusedTile == 1
                 ? tr("БИБЛИОТЕКА ВИДЕОИКОНОК 1:1", "1:1 VIDEO ICONS LIBRARY")
                 : tr("БИБЛИОТЕКА ВИДЕОФОНОВ И ИКОНОК", "VIDEO BACKGROUNDS & ICONS LIBRARY"),
             sc1X + 22, subY + 18, Theme::COLOR_TEXT_MUTED, 12);
    drawTextRight(tr("Живое превью + 60 FPS", "Live Preview + 60 FPS"), sc1X + cardW - 22, subY + 18, Theme::COLOR_FOCUS_CYAN, 12);

    size_t totalGames = m_catalogManager.getGamesCount();
    size_t totalVariants = m_catalogManager.getTotalVariantsCount();
    size_t totalIcons = m_videoIconsCatalog.size();
    size_t totalIconVariants = 0;
    for (const auto& icEntry : m_videoIconsCatalog) {
        totalIconVariants += icEntry.variants.size();
    }
    std::string bigStat = (m_homeFocusedTile == 1)
        ? (std::to_string(totalIcons) + tr(" тайтлов с иконками", " icon titles"))
        : (std::to_string(totalGames) + tr(" тайтлов в базе", " titles in DB"));
    drawText(bigStat, sc1X + 22, subY + 62, Theme::COLOR_TEXT_PRIMARY, 21);

    // Badge "Полная база" positioned dynamically after bigStat so it NEVER overlaps
    int statW = measureTextWidth(bigStat, 21);
    std::string badgeStr = tr("Полная база", "Full DB");
    int badgeW = measureTextWidth(badgeStr, 11) + 20;
    int badgeX = std::min(sc1X + 22 + statW + 14, sc1X + cardW - badgeW - 20);
    drawRoundedRect(badgeX, subY + 62, badgeW, 24, 6, {0x10, 0xB9, 0x81, 0x33});
    drawRoundedOutline(badgeX, subY + 62, badgeW, 24, 6, Theme::COLOR_SUCCESS, Theme::COLOR_SUCCESS, 1);
    drawTextCentered(badgeStr, badgeX + badgeW / 2, subY + 67, Theme::COLOR_SUCCESS, 11);

    std::string statsSub = (m_language == Language::Russian)
        ? (std::to_string(totalVariants) + " видеофонов и " + std::to_string(totalIconVariants) + " видеоиконок • 1080p / 720p • HEVC")
        : (std::to_string(totalVariants) + " covers & " + std::to_string(totalIconVariants) + " video icons • 1080p / 720p • HEVC");
    drawText(statsSub, sc1X + 22, subY + 136, Theme::COLOR_TEXT_MUTED, 12, cardW - 44);

    // Sub-card 2: Main Collections & Quick Action (560px wide, highlighted)
    drawGlassCard(sc2X, subY, cardW, subH, true, true);
    drawText(tr("РАЗДЕЛЫ КАТАЛОГА", "CATALOG SECTIONS"), sc2X + 22, subY + 18, Theme::COLOR_TEXT_MUTED, 12);
    drawTextRight("4IFIR Engine", sc2X + cardW - 22, subY + 18, Theme::COLOR_FOCUS_CYAN, 12);

    size_t totalCatAll = m_catalogManager.getGamesCount();
    size_t totalFavAll = m_favoriteKeys.size();
    struct PillData {
        std::string label;
        Color borderCol;
        Color fillCol;
    };
    PillData pData[3] = {
        {tr("Весь каталог (", "All Catalog (") + std::to_string(totalCatAll) + ")", Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_FILL},
        {tr("Избранное (", "Favorites (") + std::to_string(totalFavAll) + ")", Theme::COLOR_FOCUS_PINK, Color{0xEC, 0x48, 0x99, 0x24}},
        {tr("Поиск [Y]", "Search [Y]"), Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_FILL}
    };

    int curPillX = sc2X + 22;
    for (int p = 0; p < 3; ++p) {
        int pw = measureTextWidth(pData[p].label, 11) + 20;
        drawRoundedRect(curPillX, subY + 64, pw, 26, 6, pData[p].fillCol);
        drawRoundedOutline(curPillX, subY + 64, pw, 26, 6, pData[p].borderCol, pData[p].borderCol, 1);
        drawTextCentered(pData[p].label, curPillX + pw / 2, subY + 70, pData[p].borderCol, 11);
        curPillX += pw + 10;
    }

    drawText(tr("(A) Открыть раздел • (X) Обновить базу • (Y) Установить все недостающие",
                "(A) Open section • (X) Refresh catalog • (Y) Install all missing"),
             sc2X + 22, subY + 136, Theme::COLOR_FOCUS_CYAN, 12, cardW - 44);
}

void App::renderTabMyGames() {

    // Left List Pane (450px wide) - 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 450, 570, false, false);

    const int visibleCount = 8;
    int totalCount = static_cast<int>(m_installedGames.size());

    if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex;
    }
    if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + visibleCount) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex - visibleCount + 1;
    }

    if (totalCount > 0) {
        std::string posStr = std::to_string(m_myGamesSelectedIndex + 1) + " / " + std::to_string(totalCount);
        drawText(posStr, 380, 86, Theme::COLOR_FOCUS_CYAN, 12);
    }

    int startY = 105;
    int endIdx = std::min(totalCount, m_myGamesScrollOffset + visibleCount);
    for (int i = m_myGamesScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_myGamesSelectedIndex);
        const auto& game = m_installedGames[i];

        // 4IFIR Card with neon outline on focus
        bool isFocused = (m_myGamesActivePane == MyGamesPane::GamesList && isSelected);
        drawGlassCard(35, startY, 440, 60, isFocused, isSelected);

        drawText(game.name, 48, startY + 10, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15, 265);
        drawText(game.titleId, 48, startY + 34, Theme::COLOR_TEXT_MUTED, 12, 265);

        // Status pill: Cover & Video Icon
        if (game.hasInstalledCover && game.hasInstalledIcon) {
            drawRect(330, startY + 18, 135, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(330, startY + 18, 135, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ФОН + ИКОНКА", 342, startY + 23, Theme::COLOR_SUCCESS, 11);
        } else if (game.hasInstalledCover) {
            drawRect(370, startY + 18, 95, 24, {0x10, 0xB9, 0x81, 0x22});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ФОН ЕСТЬ", 380, startY + 23, Theme::COLOR_SUCCESS, 11);
        } else if (game.hasInstalledIcon) {
            drawRect(355, startY + 18, 110, 24, {0x0E, 0x74, 0x90, 0x33});
            drawRectOutline(355, startY + 18, 110, 24, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("ИКОНКА ЕСТЬ", 366, startY + 23, Theme::COLOR_FOCUS_CYAN, 11);
        } else {
            drawRect(370, startY + 18, 95, 24, {0x28, 0x33, 0x47, 0x55});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_BORDER, 1);
            drawText("НЕТ ФОНА", 384, startY + 23, Theme::COLOR_TEXT_MUTED, 11);
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

    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];

        drawText(selGame.name, 530, 110, Theme::COLOR_TEXT_PRIMARY, 22, 410);
        drawText("Title ID: " + selGame.titleId + "  |  " + selGame.author, 530, 145, Theme::COLOR_TEXT_MUTED, 14, 410);

        // Status details
        std::string coverInfo;
        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: Видеофон (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB) + Иконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledCover) {
            coverInfo = "Активный видеофон: " + Config::getTargetCoverFileName(selGame.titleId) + " (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: Иконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB, без видеофона)";
        } else {
            coverInfo = "Видеофон и видеоиконка не установлены";
        }
        drawText(coverInfo, 530, 175, (selGame.hasInstalledCover || selGame.hasInstalledIcon) ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);

        // Prominent Action Buttons (positioned below status, safe from top-right Tesla monitor HUD)
        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
            drawRect(530, 202, 185, 32, {0xEF, 0x44, 0x44, 0x33});
            drawRectOutline(530, 202, 185, 32, Theme::COLOR_DANGER, 1);
            drawText("[Y] Удалить фон", 545, 210, Theme::COLOR_DANGER, 13);

            drawRect(725, 202, 190, 32, {0x0E, 0x74, 0x90, 0x33});
            drawRectOutline(725, 202, 190, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("[Y] Удалить иконку", 735, 210, Theme::COLOR_FOCUS_CYAN, 12);

            if (selGame.hasBackup) {
                drawRect(925, 202, 140, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(925, 202, 140, 32, Theme::COLOR_ACCENT, 1);
                drawText("[-] Копия", 940, 210, Theme::COLOR_ACCENT, 12);
            }

            drawGlassCard(1075, 202, 150, 32, true, false);
            drawText("[+] Записи (SD)", 1088, 210, Theme::COLOR_FOCUS_CYAN, 12);
        } else if (selGame.hasInstalledCover) {
            drawRect(530, 202, 230, 32, {0xEF, 0x44, 0x44, 0x33});
            drawRectOutline(530, 202, 230, 32, Theme::COLOR_DANGER, 1);
            drawText("[Y] Удалить активный фон", 545, 210, Theme::COLOR_DANGER, 13);

            if (selGame.hasBackup) {
                drawRect(770, 202, 230, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_ACCENT, 1);
                drawText("[-] Восстановить (.bak)", 785, 210, Theme::COLOR_ACCENT, 13);
            }

            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
        } else if (selGame.hasInstalledIcon) {
            drawRect(530, 202, 230, 32, {0x0E, 0x74, 0x90, 0x33});
            drawRectOutline(530, 202, 230, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("[Y] Удалить иконку", 545, 210, Theme::COLOR_FOCUS_CYAN, 13);

            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
        } else {
            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
            int missing = getMissingCoversCount();
            if (missing > 0) {
                drawRect(530, 202, 250, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(530, 202, 250, 32, Theme::COLOR_ACCENT, 1);
                drawText("[Y] Установить все (" + std::to_string(missing) + ")", 545, 210, Theme::COLOR_ACCENT, 13);
            }
        }

        // Available variants from catalog (concise header to avoid collision with hints)
        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = "Варианты (" + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 248, Theme::COLOR_TEXT_PRIMARY, 16);

        if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            drawText("[B] К играм   |   [X] На весь экран", 870, 250, Theme::COLOR_FOCUS_CYAN, 12);
        } else {
            drawText("[A] К вариантам   |   [X] На весь экран", 870, 250, Theme::COLOR_TEXT_MUTED, 12);
        }

        if (totalVariants > 0) {
            const int visibleVariants = 4;
            if (m_variantScrollOffset < 0) m_variantScrollOffset = 0;
            if (m_selectedVariantIndex < m_variantScrollOffset) {
                m_variantScrollOffset = m_selectedVariantIndex;
            } else if (m_selectedVariantIndex >= m_variantScrollOffset + visibleVariants) {
                m_variantScrollOffset = m_selectedVariantIndex - visibleVariants + 1;
            }

            // Scroll indicator ABOVE
            if (m_variantScrollOffset > 0) {
                drawText("^ Еще варианты выше (D-Pad Влево)", 780, 252, Theme::COLOR_FOCUS_CYAN, 12);
            }

            int vY = 280;
            int endVIdx = std::min(totalVariants, m_variantScrollOffset + visibleVariants);
            for (int vIdx = m_variantScrollOffset; vIdx < endVIdx; ++vIdx) {
                const auto& v = selGame.catalogEntry.variants[vIdx];
                bool isVarSelected = (vIdx == m_selectedVariantIndex);

                // 4IFIR Cyber-Glass variant card
                bool isVarFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                drawGlassCard(525, vY, 700, 72, isVarFocused, isVarSelected);

                // Variant Title & Style (bounded so it never overlaps install button)
                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                if (v.hasIcon) {
                    vTitle += "  [Иконка]";
                }
                drawText(vTitle, 545, vY + 12, isVarSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 450);

                // Tech Specs Line (Width capped at 230 to avoid overlap with badges)
                std::string meta = std::to_string(v.width) + "x" + std::to_string(v.height) + " @" +
                                   std::to_string(static_cast<int>(v.fps)) + "fps  |  " +
                                   ([&]() {
                    double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
                    char buf[16];
                    if (mb >= 0.1) snprintf(buf, sizeof(buf), "%.1f MB", mb);
                    else snprintf(buf, sizeof(buf), "~3.5 MB");
                    return std::string(buf);
                })();
                drawText(meta, 545, vY + 41, Theme::COLOR_TEXT_MUTED, 12, 230);

                // Badges row: Active on console, Audio, and Video Icon
                int vBadgeX = 720;
                bool isActiveOnConsole = (selGame.hasInstalledCover && v.id == selGame.installedVariantId);
                if (isActiveOnConsole) {
                    drawRect(vBadgeX, vY + 38, 92, 22, {0x10, 0xB9, 0x81, 0x44});
                    drawRectOutline(vBadgeX, vY + 38, 92, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("УСТАНОВЛЕН", vBadgeX + 8, vY + 43, Theme::COLOR_SUCCESS, 10);
                    vBadgeX += 98;
                }

                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(vBadgeX, vY + 38, 62, 22, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(vBadgeX, vY + 38, 62, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", vBadgeX + 15, vY + 43, Theme::COLOR_SUCCESS, 10);
                    vBadgeX += 68;
                } else {
                    drawRect(vBadgeX, vY + 38, 78, 22, Theme::COLOR_MUTED_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 78, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", vBadgeX + 9, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                    vBadgeX += 84;
                }

                // Video Icon Status Pill (prominent cyan when present, muted when absent)
                if (v.hasIcon) {
                    drawRect(vBadgeX, vY + 38, 72, 22, Theme::COLOR_ICON_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 72, 22, Theme::COLOR_ICON_BADGE, 1);
                    drawText("ИКОНКА", vBadgeX + 11, vY + 43, Theme::COLOR_ICON_BADGE, 10);
                } else {
                    drawRect(vBadgeX, vY + 38, 86, 22, Theme::COLOR_MUTED_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 86, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ИКОНКИ", vBadgeX + 9, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                }

                // Install / Reinstall Button (Interactive touch zone)
                bool isFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                Color btnFill = isFocused ? Theme::COLOR_FOCUS_FILL : (isVarSelected ? Color{0x00, 0x55, 0x77, 0x33} : Color{0x15, 0x20, 0x30, 0x55});
                Color btnBorder = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER;
                Color btnTextCol = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED;

                if (v.hasIcon) {
                    drawRect(980, vY + 18, 125, 36, btnFill);
                    drawRectOutline(980, vY + 18, 125, 36, btnBorder, 1);
                    std::string btnText = isActiveOnConsole ? "[A] Фон" : "[A] Всё";
                    drawText(btnText, 995, vY + 27, btnTextCol, 13);

                    Color icoBtnFill = {0x0E, 0x74, 0x90, 0x33};
                    drawRect(1115, vY + 18, 95, 36, icoBtnFill);
                    drawRectOutline(1115, vY + 18, 95, 36, Theme::COLOR_FOCUS_CYAN, 1);
                    drawText("[A] Иконка", 1125, vY + 27, Theme::COLOR_FOCUS_CYAN, 12);
                } else {
                    drawRect(1005, vY + 18, 205, 36, btnFill);
                    drawRectOutline(1005, vY + 18, 205, 36, btnBorder, 1);
                    std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                    drawText(btnText, 1025, vY + 27, btnTextCol, 13);
                }

                vY += 80;
            }

            // Scroll indicator BELOW
            if (endVIdx < totalVariants) {
                std::string belowStr = "v Еще варианты ниже: " + std::to_string(totalVariants - endVIdx) + " шт. (D-Pad Вправо)";
                drawText(belowStr, 720, vY + 6, Theme::COLOR_FOCUS_PINK, 12);
            }
        } else {
            drawText((m_language == Language::Russian
                ? "Прямых вариантов для этой игры пока нет в каталоге."
                : "No direct variants found for this game in the catalog."),
                530, 290, Theme::COLOR_TEXT_MUTED, 14);

            drawText((m_language == Language::Russian
                ? "Вы можете привязать ЛЮБОЙ видеофон из каталога:"
                : "You can assign ANY video theme from the catalog:"),
                530, 318, Theme::COLOR_FOCUS_CYAN, 13);

            drawGlassCard(530, 350, 480, 56, true, false);
            std::string catBtnText = Config::isAfterDark()
                ? (m_language == Language::Russian ? "[X] Открыть каталог After Dark" : "[X] Open After Dark Catalog")
                : (m_language == Language::Russian ? "[X] Открыть онлайн-каталог" : "[X] Open Online Catalog");
            drawText(catBtnText, 555, 368, Theme::COLOR_FOCUS_CYAN, 16);
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

    // Dock Action Buttons: [X] На весь экран and [A] Установить
    int bY = dockY + dockH - 52;
    drawRoundedRect(dockX + 18, bY, 182, 38, 8, {0x14, 0x1E, 0x30, 0xEE});
    drawRoundedOutline(dockX + 18, bY, 182, 38, 8, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered(tr("[X] На весь экран", "[X] Fullscreen"), dockX + 18 + 91, bY + 11, Theme::COLOR_FOCUS_CYAN, 12);

    drawRoundedRect(dockX + 214, bY, 182, 38, 8, Theme::COLOR_FOCUS_FILL);
    drawNeonRoundedOutline(dockX + 214, bY, 182, 38, 8, 2);
    drawTextCentered(tr("[A] Установить", "[A] Install Icon"), dockX + 214 + 91, bY + 11, Theme::COLOR_FOCUS_CYAN, 12);
}

void App::renderTabCatalog() {
    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 74, 1220, 576, false, false);

    bool isFavTab = (m_catalogSortMode == CatalogSortMode::FavoritesOnly);
    size_t totalCatGames = m_catalogManager.getGamesCount();
    size_t totalFavorites = m_favoriteKeys.size();

    // 1. Top Bar: Segment Tabs, Search Bar, Filter/Sort Pill, Back Button (y=82, h=38)
    // Segment Tab 1: [L] Весь каталог
    std::string tab1Text = tr("[L] Весь каталог (", "[L] All Catalog (") + std::to_string(totalCatGames) + ")";
    int t1W = measureTextWidth(tab1Text, 13) + 24;
    drawRoundedRect(50, 82, t1W, 38, 10, !isFavTab ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_PILL_BG);
    if (!isFavTab) {
        drawNeonRoundedOutline(50, 82, t1W, 38, 10, 2);
    } else {
        drawRoundedOutline(50, 82, t1W, 38, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }
    drawTextCentered(tab1Text, 50 + t1W / 2, 91, !isFavTab ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 13);

    // Segment Tab 2: [R] Избранное
    std::string tab2Text = tr("[R] Избранное (", "[R] Favorites (") + std::to_string(totalFavorites) + ")";
    int t2W = measureTextWidth(tab2Text, 13) + 24;
    int t2X = 50 + t1W + 10;
    drawRoundedRect(t2X, 82, t2W, 38, 10, isFavTab ? Color{0xEC, 0x48, 0x99, 0x24} : Theme::COLOR_PILL_BG);
    if (isFavTab) {
        drawRoundedOutline(t2X, 82, t2W, 38, 10, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 2);
    } else {
        drawRoundedOutline(t2X, 82, t2W, 38, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }
    drawTextCentered(tab2Text, t2X + t2W / 2, 91, isFavTab ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_MUTED, 13);

    // Interactive Search Bar (x=465, y=82, w=420, h=38)
    bool hasSearch = !m_catalogSearchQuery.empty();
    drawGlassCard(465, 82, 420, 38, hasSearch, false);
    drawSearchIcon(482, 101, hasSearch ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED);
    std::string searchLabel = hasSearch
        ? (tr("Поиск: ", "Search: ") + m_catalogSearchQuery)
        : tr("Поиск по названию игры или TitleID...", "Search by game title or TitleID...");
    drawText(searchLabel, 498, 92, hasSearch ? Theme::COLOR_TEXT_PRIMARY : Theme::COLOR_TEXT_MUTED, 13, 290);
    drawRoundedRect(805, 88, 72, 26, 6, Theme::COLOR_FOCUS_FILL);
    drawRoundedOutline(805, 88, 72, 26, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered(tr("[Y] Поиск", "[Y] Search"), 841, 93, Theme::COLOR_FOCUS_CYAN, 11);

    // Sort / Filter Chip button (x=895, y=82, w=180, h=38)
    std::string sortStr = tr("[X] Фильтр: ", "[X] Filter: ");
    switch (m_catalogSortMode) {
        case CatalogSortMode::Alphabetical: sortStr += tr("А-Я", "A-Z"); break;
        case CatalogSortMode::VariantsCount: sortStr += tr("Варианты", "Variants"); break;
        case CatalogSortMode::AudioOnly: sortStr += tr("Звук ♪", "Audio ♪"); break;
        case CatalogSortMode::IconsOnly: sortStr += tr("256x256", "256x256"); break;
        case CatalogSortMode::InstalledOnly: sortStr += tr("На консоли", "Installed"); break;
        case CatalogSortMode::FavoritesOnly: sortStr += tr("Избранное ★", "Favorites ★"); break;
        default: sortStr += tr("Все", "All"); break;
    }
    drawPillButton(895, 82, 180, 38, sortStr, m_catalogSortMode != CatalogSortMode::Default, Theme::COLOR_FOCUS_CYAN);

    // Back to Home button (x=1085, y=82, w=145, h=38)
    drawPillButton(1085, 82, 145, 38, tr("(B) На главную", "(B) Home"), false, Theme::COLOR_TEXT_MUTED);

    // 2. Games List Area
    int totalFiltered = static_cast<int>(m_filteredCatalogGames.size());
    if (totalFiltered == 0) {
        if (isFavTab) {
            // Elegant empty state for Favorites
            drawRoundedRect(490, 200, 300, 240, 24, {0x14, 0x1A, 0x28, 0xFF});
            drawRoundedOutline(490, 200, 300, 240, 24, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 2);
            drawTextCentered("★", 640, 245, Theme::COLOR_FOCUS_PINK, 36);
            drawTextCentered(tr("Избранное пусто", "Favorites is Empty"), 640, 295, Theme::COLOR_TEXT_PRIMARY, 18);
            drawTextCentered(tr("Нажмите [-] на любой игре в каталоге,", "Press [-] on any game in the catalog"), 640, 330, Theme::COLOR_TEXT_MUTED, 13);
            drawTextCentered(tr("чтобы добавить её в быстрый доступ", "to add it to your quick favorites"), 640, 350, Theme::COLOR_TEXT_MUTED, 13);
            drawPillButton(540, 380, 200, 36, tr("[L] Открыть весь каталог", "[L] Open Full Catalog"), true, Theme::COLOR_FOCUS_CYAN);
        } else {
            drawTextCentered(tr("Игры по вашему запросу не найдены", "No games found matching your filter"), 640, 320, Theme::COLOR_TEXT_MUTED, 16);
            drawTextCentered(tr("Нажмите [Y] для изменения поиска или [X] для смены фильтра", "Press [Y] to change search or [X] to cycle filter"), 640, 355, Theme::COLOR_FOCUS_CYAN, 13);
        }
        return;
    }

    const int visibleCount = 5;
    if (m_catalogSelectedIndex < m_catalogScrollOffset) {
        m_catalogScrollOffset = m_catalogSelectedIndex;
    }
    if (m_catalogSelectedIndex >= m_catalogScrollOffset + visibleCount) {
        m_catalogScrollOffset = m_catalogSelectedIndex - visibleCount + 1;
    }

    int y = 136;
    int endIdx = std::min(totalFiltered, m_catalogScrollOffset + visibleCount);
    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        const auto& game = m_filteredCatalogGames[i];
        bool isFocused = (i == m_catalogSelectedIndex);
        bool isFav = hasGameFavorites(game.titleId);

        drawGlassCard(50, y, 1180, 88, isFocused, isFocused);

        // Cartridge / Auto-Loading 70x70 Cover Preview Box (Variant A)
        int boxX = 64;
        int boxY = y + 9;
        drawRoundedRect(boxX, boxY, 70, 70, 12, {0x14, 0x1A, 0x28, 0xFF});

        auto covVars = getCoverVariants(game);
        SDL_Texture* rowThumbTex = nullptr;
        if (!covVars.empty()) {
            const auto& fv = covVars[0];
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
            SDL_Rect dst{boxX + 2, boxY + 2, 66, 66};
            SDL_RenderCopy(m_renderer, rowThumbTex, nullptr, &dst);
        } else {
            // Draw mini cartridge symbol inside box while loading or offline
            drawRoundedRect(boxX + 22, boxY + 16, 26, 38, 4, {0x26, 0x32, 0x48, 0xFF});
            drawRoundedRect(boxX + 24, boxY + 18, 22, 10, 2, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN);
            drawRoundedRect(boxX + 24, boxY + 31, 22, 20, 2, {0x0E, 0x14, 0x22, 0xFF});
        }
        drawRoundedOutline(boxX, boxY, 70, 70, 12, isFocused ? (isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN) : Theme::COLOR_BORDER, isFocused ? (isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN) : Theme::COLOR_BORDER, 1);

        // Info Column
        int infoX = boxX + 86;
        drawText(game.title, infoX, y + 14, isFocused ? (isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN) : Theme::COLOR_TEXT_PRIMARY, 16, 600);

        // Subline: TitleID + Publisher
        std::string pubText = game.publisher.empty() ? "Nintendo Switch" : game.publisher;
        drawText(game.titleId + "  |  " + pubText, infoX, y + 42, Theme::COLOR_TEXT_MUTED, 12);

        // Badges: Cover Variants count & Video Icon
        int vCount = static_cast<int>(covVars.size());
        std::string vStr = std::to_string(vCount) + tr(" вар. фона", " covers");
        int vBadgeW = measureTextWidth(vStr, 11) + 16;
        int curBadgeX = infoX + 330;
        drawRoundedRect(curBadgeX, y + 42, vBadgeW, 22, 4, Theme::COLOR_FOCUS_FILL);
        drawRoundedOutline(curBadgeX, y + 42, vBadgeW, 22, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered(vStr, curBadgeX + vBadgeW / 2, y + 46, Theme::COLOR_FOCUS_CYAN, 11);

        auto gameIcons = getUniqueIconVariants(game);
        if (!gameIcons.empty()) {
            curBadgeX += vBadgeW + 8;
            std::string icoBadgeStr = "[ZR] 256x256 (" + std::to_string(gameIcons.size()) + ")";
            int icoBadgeW = measureTextWidth(icoBadgeStr, 11) + 16;
            drawRoundedRect(curBadgeX, y + 42, icoBadgeW, 22, 4, Color{0xEC, 0x48, 0x99, 0x2E});
            drawRoundedOutline(curBadgeX, y + 42, icoBadgeW, 22, 4, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
            drawTextCentered(icoBadgeStr, curBadgeX + icoBadgeW / 2, y + 46, Theme::COLOR_FOCUS_PINK, 11);
        }

        // Action Buttons on Right
        // 1. Favorite toggle button: [-] В избр. (x=805, y=y+25, w=115, h=38)
        drawRoundedRect(805, y + 25, 115, 38, 8, isFav ? Color{0xEC, 0x48, 0x99, 0x24} : Color{0x14, 0x1E, 0x30, 0xDD});
        drawRoundedOutline(805, y + 25, 115, 38, 8, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_BORDER, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_BORDER, 1);
        drawTextCentered(isFav ? tr("[-] В избр. ★", "[-] Fav ★") : tr("[-] В избр.", "[-] Fav"), 805 + 57, y + 36, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_MUTED, 12);

        // 2. Quick Preview button: [ZL] Просмотр (x=930, y=y+25, w=135, h=38)
        drawRoundedRect(930, y + 25, 135, 38, 8, Color{0x14, 0x1E, 0x30, 0xDD});
        drawRoundedOutline(930, y + 25, 135, 38, 8, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        drawTextCentered(tr("[ZL] Просмотр", "[ZL] Preview"), 930 + 67, y + 36, Theme::COLOR_TEXT_PRIMARY, 12);

        // 3. Select Themes button: [A] Выбрать (x=1075, y=y+25, w=140, h=38)
        drawRoundedRect(1075, y + 25, 140, 38, 8, isFocused ? Theme::COLOR_FOCUS_FILL : Color{0x18, 0x22, 0x34, 0xEE});
        drawNeonRoundedOutline(1075, y + 25, 140, 38, 8, isFocused ? 2 : 1);
        drawTextCentered(tr("[A] Выбрать", "[A] Select"), 1075 + 70, y + 36, Theme::COLOR_FOCUS_CYAN, 13);

        y += 98;
    }

    // Smooth 60 FPS neon selection indicator bar on the left of Catalog list
    if (totalFiltered > 0) {
        int barY = static_cast<int>(std::round(m_smoothCatalogSelY)) + 12;
        drawRoundedRect(44, barY, 5, 64, 2, isFavTab ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN);
    }
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

    // Settings list options (7 rows)
    struct SettingRow {
        std::string title;
        std::string desc;
        std::string value;
        Color valColor;
    };

    std::vector<SettingRow> rows = {
        {tr("Обновление приложения (NRO)", "Update Application (NRO)"),
         (m_language == Language::Russian)
             ? (std::string("Проверить и установить новую версию ") + Config::APP_NAME + " с GitHub")
             : (std::string("Check and install the latest ") + Config::APP_NAME + " release from GitHub"),
         std::string("v") + Config::APP_VERSION + " [A]", Theme::COLOR_FOCUS_CYAN},
        {tr("Обновление каталога видеофонов", "Update Video Backgrounds Catalog"),
         tr("Загрузить новейший каталог игр и обложек без обновления NRO", "Download the newest game & cover catalog without updating NRO"),
         "GitHub Releases [A]", Theme::COLOR_FOCUS_CYAN},
        {tr("Очистить кэш мини-превью (галерея)", "Clear Thumbnail Cache (Gallery)"),
         tr("Удалить сохраненные миниатюры обложек (thumbs/) для освобождения места", "Delete cached cover & icon thumbnails (thumbs/) to free SD space"),
         tr("[A] Очистить", "[A] Clear"), Theme::COLOR_FOCUS_PINK},
        {tr("Очистить кэш видеоплеера (видео)", "Clear Video Preview Cache (MP4)"),
         tr("Удалить временные видеофайлы предпросмотра (mp4) на SD-карте", "Delete temporary preview video files (mp4) on SD card"),
         tr("[A] Очистить", "[A] Clear"), Theme::COLOR_FOCUS_PINK},
        {tr("Очистить локальный кэш каталога", "Reset Local Catalog Cache"),
         tr("Сбросить локальный файл cache.json и пересканировать игры", "Reset local cache.json and rescan installed games"),
         tr("[A / X] Сброс", "[A / X] Reset"), Theme::COLOR_WARNING},
        {tr("Проверка целостности фонов и иконок", "Verify Covers & Icons Integrity"),
         tr("Сканирование установленных видеофонов и видеоиконок на битые файлы", "Scan installed video covers and icons for corrupted files"),
         tr("[A] Сканировать", "[A] Scan"), Theme::COLOR_FOCUS_CYAN},
        {tr("Язык интерфейса / Language", "Interface Language / Язык"),
         tr("Выбор языка отображения меню и подсказок управления", "Select display language for menus and button prompts"),
         (m_language == Language::Russian ? "Русский [A]" : "English [A]"), Theme::COLOR_TEXT_PRIMARY}
    };

    int rowY = 236;
    for (size_t i = 0; i < rows.size(); ++i) {
        bool isFocused = (static_cast<int>(i) == m_settingsSelectedIndex);

        if (isFocused) {
            drawRect(50, rowY, 1180, 48, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(50, rowY, 1180, 48, 2);
        } else {
            drawRect(50, rowY, 1180, 48, Theme::COLOR_BG_SURFACE);
            drawRectOutline(50, rowY, 1180, 48, Theme::COLOR_BORDER, 1);
        }

        drawText(rows[i].title, 75, rowY + 7, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15, 850);
        drawText(rows[i].desc, 75, rowY + 28, Theme::COLOR_TEXT_MUTED, 11, 850);

        drawText(rows[i].value, 940, rowY + 14, rows[i].valColor, 14, 270);

        rowY += 54;
    }

    // Smooth 60 FPS neon selection indicator bar on the left of Settings rows
    int sBarY = static_cast<int>(std::round(m_smoothSettingsSelY)) + 6;
    drawRoundedRect(44, sBarY, 5, 36, 2, Theme::COLOR_FOCUS_CYAN);

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

    // Restore inline live preview if returning to Collection Browser or VideoIcons Dock
    if (m_isCollectionBrowserOpen) {
        m_collectionPreviewDirty = true;
        m_lastCollectionMoveTime = SDL_GetTicks() - 100;
    } else if (m_activeTab == Tab::VideoIcons) {
        m_videoIconDockDirty = true;
        m_lastVideoIconMoveTime = SDL_GetTicks() - 100;
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
    m_collectionTitleId = entry.titleId;
    m_collectionGameName = entry.title;
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
    std::string cacheKey = showAsIcon
        ? ("icon_" + m_collectionTitleId + "_" + variant.id)
        : (m_collectionTitleId + "_" + variant.id);
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
    bool hasCachedThumb = (findCachedThumbTexture(m_collectionTitleId, variant, showAsIcon) != nullptr);
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

    SDL_Texture* activeCollTex = m_collectionThumbTexture;
    if (!activeCollTex && hasSelVar) {
        activeCollTex = findCachedThumbTexture(m_collectionTitleId, m_collectionVariants[m_collectionSelectedIndex], showCollIconMode);
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
    int nextMode = (static_cast<int>(m_catalogSortMode) + 1) % 7;
    m_catalogSortMode = static_cast<CatalogSortMode>(nextMode);
    rebuildCatalogFilter();

    std::string modeDesc;
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: modeDesc = "Сортировка: По умолчанию"; break;
        case CatalogSortMode::Alphabetical: modeDesc = "Сортировка: По алфавиту (А-Я)"; break;
        case CatalogSortMode::VariantsCount: modeDesc = "Сортировка: По кол-ву фонов (v)"; break;
        case CatalogSortMode::AudioOnly: modeDesc = "Фильтр: Только со звуком [ЗВУК]"; break;
        case CatalogSortMode::IconsOnly: modeDesc = "Фильтр: Только с видеоиконками [ИКОНКА]"; break;
        case CatalogSortMode::InstalledOnly: modeDesc = "Фильтр: Только установленные игры"; break;
        case CatalogSortMode::FavoritesOnly: modeDesc = "Фильтр: [*] Только избранное"; break;
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

            // Home Tab: 5x Dashboard Tiles at y in [100, 320]
            if (m_activeTab == Tab::Home && my >= 100 && my <= 320 && mx >= 40 && mx <= 1240) {
                int tileW = 225, tileGap = 14;
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
            // Home Tab: Bottom Summary Panel click (y in [368, 626])
            else if (m_activeTab == Tab::Home && my >= 368 && my <= 626 && mx >= 48 && mx <= 1232) {
                onButtonPress(0 /* A - Activate selected tile */);
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
                    // Tap on [A] Установить / АКТИВНА [+] button (x in [645, 800])
                    else if (mx >= 645 && mx <= 800) {
                        if (isIconInstalled(m_filteredVideoIcons[clickedIdx].titleId)) {
                            onButtonPress(6 /* + - Delete installed video icon */);
                        } else {
                            onButtonPress(0 /* A - Install */);
                        }
                    } else if (wasSelected) {
                        onButtonPress(2 /* X - Fullscreen Preview on second tap */);
                    }
                }
            }
            // VideoIcons Tab: Right Split-Screen Live Switch Icon Dock (x in [818, 1232], y in [136, 616])
            else if (m_activeTab == Tab::VideoIcons && mx >= 818 && mx <= 1232 && my >= 136 && my <= 616) {
                int dockX = 818, dockY = 136, dockW = 414, dockH = 480;
                int bY = dockY + dockH - 52;
                // Tap on 256x256 live tile -> Fullscreen preview
                if (my >= dockY + 50 && my <= dockY + 315) {
                    onButtonPress(2 /* X - Fullscreen Preview */);
                }
                // Tap on variant switcher pill in dock (y in [504, 542])
                else if (my >= dockY + 365 && my <= dockY + 405) {
                    if (mx < dockX + dockW / 2) onButtonPress(13 /* DPAD_LEFT */);
                    else onButtonPress(14 /* DPAD_RIGHT */);
                }
                // Tap on [X] На весь экран button in dock
                else if (my >= bY && my <= bY + 40 && mx >= dockX + 18 && mx <= dockX + 200) {
                    onButtonPress(2 /* X - Fullscreen Preview */);
                }
                // Tap on [A] Установить button in dock
                else if (my >= bY && my <= bY + 40 && mx >= dockX + 214 && mx <= dockX + 396) {
                    onButtonPress(0 /* A - Install */);
                }
            }
            // Catalog Tab: Top bar and list items
            else if (m_activeTab == Tab::Catalog) {
                // Top Tab 1: [L] Весь каталог (x in [50, 275], y in [74, 122])
                if (mx >= 50 && mx <= 275 && my >= 74 && my <= 122) {
                    onButtonPress(9 /* L - Весь каталог */);
                }
                // Top Tab 2: [R] Избранное (x in [276, 460], y in [74, 122])
                else if (mx >= 276 && mx <= 460 && my >= 74 && my <= 122) {
                    onButtonPress(10 /* R - Избранное */);
                }
                // Search Bar (x in [465, 885], y in [74, 122])
                else if (mx >= 465 && mx <= 885 && my >= 74 && my <= 122) {
                    onButtonPress(3 /* Y - Open Search Keyboard */);
                }
                // Sort Mode Button (x in [895, 1075], y in [74, 122])
                else if (mx >= 895 && mx <= 1075 && my >= 74 && my <= 122) {
                    onButtonPress(2 /* X - Cycle Sort */);
                }
                // Back to Home Button (x in [1085, 1235], y in [74, 122])
                else if (mx >= 1085 && mx <= 1235 && my >= 74 && my <= 122) {
                    onButtonPress(1 /* B - Back to Home */);
                }
                // Click on Game row items (y in [136, 630])
                else if (mx >= 50 && mx <= 1230 && my >= 136 && my <= 630) {
                    int clickedIdx = m_catalogScrollOffset + (my - 136) / 98;
                    int totalGames = static_cast<int>(m_filteredCatalogGames.size());
                    if (clickedIdx >= 0 && clickedIdx < totalGames) {
                        bool wasSelected = (m_catalogSelectedIndex == clickedIdx);
                        m_catalogSelectedIndex = clickedIdx;
                        // Click on pink [ZR] 256x256 Icon badge (x in [560, 795]) -> open Video Icon Preview directly!
                        if (mx >= 560 && mx <= 795 && !getUniqueIconVariants(m_filteredCatalogGames[clickedIdx]).empty()) {
                            onButtonPress(16 /* ZR - Video Icon Preview */);
                        }
                        // Click on Favorite button [-] (x in [805, 920])
                        else if (mx >= 805 && mx <= 920) {
                            onButtonPress(4 /* Minus - Toggle Favorite */);
                        }
                        // Click on Preview button [ZL] (x in [930, 1065])
                        else if (mx >= 930 && mx <= 1065) {
                            onButtonPress(15 /* ZL - Preview */);
                        }
                        // Click on Select button [A] (x in [1075, 1220]) or double-tap on row
                        else if ((mx >= 1075 && mx <= 1220) || wasSelected) {
                            onButtonPress(0 /* A - Open Collection Browser */);
                        }
                    }
                }
            }
            else if (m_activeTab == Tab::MyGames) {
                // Left Column: Games list item selection (x in [30, 480], y in [105, 640])
                if (mx >= 30 && mx <= 480 && my >= 105 && my <= 640) {
                    int clickedIdx = m_myGamesScrollOffset + (my - 105) / 66;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_installedGames.size())) {
                        if (m_myGamesSelectedIndex == clickedIdx) {
                            const auto& g = m_installedGames[clickedIdx];
                            if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                                openCollectionBrowser(g.catalogEntry);
                            } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                                m_myGamesActivePane = MyGamesPane::VariantsList;
                            }
                        } else {
                            m_myGamesSelectedIndex = clickedIdx;
                            m_selectedVariantIndex = 0;
                            m_variantScrollOffset = 0;
                            m_myGamesActivePane = MyGamesPane::GamesList;
                        }
                    }
                }
                // Right Column Action buttons at y in [200, 240]
                else if (my >= 200 && my <= 240) {
                    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
                            if (mx >= 530 && mx <= 720) {
                                executeDeleteCover(selGame.titleId);
                            } else if (mx >= 725 && mx <= 920) {
                                executeDeleteIcon(selGame.titleId);
                            } else if (mx >= 925 && mx <= 1070 && selGame.hasBackup) {
                                executeRestoreBackup(selGame.titleId);
                            } else if (mx >= 1075 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        } else if (selGame.hasInstalledCover) {
                            if (mx >= 530 && mx <= 760) {
                                onButtonPress(3 /* Y - Delete */);
                            } else if (mx >= 770 && mx <= 1000 && selGame.hasBackup) {
                                executeRestoreBackup(selGame.titleId);
                            } else if (mx >= 1015 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        } else if (selGame.hasInstalledIcon) {
                            if (mx >= 530 && mx <= 760) {
                                executeDeleteIcon(selGame.titleId);
                            } else if (mx >= 1015 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        } else {
                            if (mx >= 530 && mx <= 780 && getMissingCoversCount() > 0) {
                                installAllMissing();
                            } else if (mx >= 1015 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        }
                    }
                }
                // Right Column Variant Cards (y in [280, 600])
                else if (mx >= 525 && mx <= 1225 && my >= 280 && my <= 600) {
                    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                        int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                        if (totalV > 0) {
                            int vClicked = m_variantScrollOffset + (my - 280) / 80;
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
                            // No direct variants: "Открыть каталог" button at x in [530, 1010], y in [350, 410]
                            if (mx >= 530 && mx <= 1010 && my >= 350 && my <= 410) {
                                m_activeTab = Tab::Catalog;
                            }
                        }
                    }
                }
            }
            // Downloads Tab: interactive touch controls
            else if (m_activeTab == Tab::Downloads) {
                // Footer action buttons at y in [660, 720]
                if (my >= 660 && my <= 720) {
                    if (mx >= 130 && mx <= 310) {
                        onButtonPress(0 /* A - Retry failed */);
                    } else if (mx >= 350 && mx <= 500) {
                        onButtonPress(2 /* X - Clear */);
                    } else if (mx >= 510 && mx <= 740) {
                        onButtonPress(3 /* Y - Install all missing */);
                    } else if (mx >= 750 && mx <= 860) {
                        onButtonPress(1 /* B - Back */);
                    }
                }
                // Tapping directly on a download row selects it, or retries/removes if already selected: y in [160, 640]
                else if (my >= 160 && my <= 640 && mx >= 60 && mx <= 1220) {
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
            // Settings Tab: interactive setting rows at y in [230, 615]
            else if (m_activeTab == Tab::Settings && mx >= 50 && mx <= 1230 && my >= 230 && my <= 615) {
                int clickedRow = (my - 236) / 54;
                if (clickedRow >= 0 && clickedRow <= 6) {
                    m_settingsSelectedIndex = clickedRow;
                    onButtonPress(0 /* A - Activate Setting */);
                }
            }
            // Footer bar click on refresh: y in [660, 720]
            else if (my >= 660 && mx >= 1050) {
                onButtonPress(4 /* Minus / Refresh */);
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
            if (m_myGamesScrollOffset + 8 < static_cast<int>(m_installedGames.size())) {
                m_myGamesScrollOffset++;
                if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
                    m_myGamesSelectedIndex = m_myGamesScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 500 && startX <= 1250) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
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
                if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + 8) {
                    m_myGamesSelectedIndex = m_myGamesScrollOffset + 7;
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
    drawRoundedRect(drawX, drawY, drawW, drawH, 24, bg);

    if (isFocused) {
        drawRoundedRect(drawX, drawY, drawW, drawH, 24, Theme::COLOR_FOCUS_FILL);
        // Breathing cyber neon glow
        uint8_t alpha = static_cast<uint8_t>(std::clamp(m_glowPulse * 255.0f, 160.0f, 255.0f));
        Color cGlow = Theme::COLOR_FOCUS_CYAN; cGlow.a = alpha;
        Color pGlow = Theme::COLOR_FOCUS_PINK; pGlow.a = alpha;
        drawRoundedOutline(drawX, drawY, drawW, drawH, 24, cGlow, pGlow, 3);
    } else {
        drawRoundedOutline(drawX, drawY, drawW, drawH, 24, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }

    // Subtle top gloss highlight
    drawRoundedRect(drawX + 18, drawY + 2, drawW - 36, 2, 1, {0xFF, 0xFF, 0xFF, 0x1A});

    // Centered vector or texture icon in upper area of tile
    int iconCx = drawX + drawW / 2;
    int iconCy = drawY + 70;
    drawTileIconVector(iconCx, iconCy, tileIdx, isFocused);

    // Centered Title underneath (measured pixel width, never overflows or shifts!)
    drawTextCentered(title, drawX + drawW / 2, drawY + drawH - 34, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
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

} // namespace ui
} // namespace h3h
