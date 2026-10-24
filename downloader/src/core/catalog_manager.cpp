#include "core/catalog_manager.hpp"
#include "core/config.hpp"
#include "core/json.hpp"

#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>

using json = nlohmann::json;

namespace h3h {

namespace {

std::string toLowerString(const std::string& str) {
    std::string lower = str;
    std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char c) {
        return std::tolower(c);
    });
    return lower;
}

} // namespace

CatalogManager::CatalogManager() = default;

size_t CatalogManager::getTotalVariantsCount() const {
    size_t count = 0;
    for (const auto& g : m_games) {
        count += g.variants.size();
    }
    return count;
}

bool CatalogManager::loadFromJsonString(const std::string& jsonStr, std::string& outError) {
    try {
        json root = json::parse(jsonStr);

        if (!root.is_object()) {
            outError = "Root must be a JSON object";
            return false;
        }

        if (!root.contains("schemaVersion") || !root["schemaVersion"].is_number_integer()) {
            outError = "Missing or invalid schemaVersion";
            return false;
        }

        int schemaVer = root["schemaVersion"].get<int>();
        if (schemaVer != 1) {
            outError = "Unsupported schema version: " + std::to_string(schemaVer) + ", expected 1";
            return false;
        }

        m_schemaVersion = schemaVer;
        m_updatedAt = root.value("updatedAt", "");

        if (!root.contains("games") || !root["games"].is_array()) {
            outError = "'games' array missing in catalog";
            return false;
        }

        std::vector<GameCatalogEntry> parsedGames;
        std::unordered_map<std::string, size_t> parsedIndex;

        for (const auto& jGame : root["games"]) {
            if (!jGame.is_object()) continue;

            std::string rawTitleId = jGame.value("titleId", "");
            if (!Config::isValidTitleId(rawTitleId)) {
                outError = "Invalid Title ID format encountered: " + rawTitleId;
                return false;
            }

            std::string normTitleId = Config::normalizeTitleId(rawTitleId);
            if (parsedIndex.find(normTitleId) != parsedIndex.end()) {
                outError = "Duplicate Title ID in catalog: " + normTitleId;
                return false;
            }

            GameCatalogEntry entry;
            entry.titleId = normTitleId;
            entry.title = jGame.value("title", "Unknown Title");
            entry.publisher = jGame.value("publisher", "");
            entry.iconUrl = jGame.value("iconUrl", "");

            if (jGame.contains("variants") && jGame["variants"].is_array()) {
                for (const auto& jVar : jGame["variants"]) {
                    if (!jVar.is_object()) continue;

                    Variant v;
                    v.id = jVar.value("id", "");
                    v.name = jVar.value("name", "Standard");
                    v.style = stringToStyle(jVar.value("style", ""));
                    v.version = jVar.value("version", "1.0");
                    v.url = jVar.value("url", "");
                    v.previewUrl = jVar.value("previewUrl", "");
                    v.sizeBytes = jVar.value("sizeBytes", static_cast<uint64_t>(0));
                    v.sha256 = jVar.value("sha256", "");
                    v.durationSec = jVar.value("durationSec", 0.0);
                    v.author = jVar.value("author", "Community");
                    v.codec = jVar.value("codec", "h264");
                    v.width = jVar.value("width", 1280);
                    v.height = jVar.value("height", 720);
                    v.fps = jVar.value("fps", 30.0);
                    v.hasAudio = jVar.value("hasAudio", false);
                    v.notes = jVar.value("notes", "");

                    v.hasIcon = jVar.value("hasIcon", false);
                    v.iconUrl = jVar.value("iconUrl", "");
                    v.iconSizeBytes = jVar.value("iconSizeBytes", static_cast<uint64_t>(0));
                    v.iconCodec = jVar.value("iconCodec", "hevc");
                    v.iconWidth = jVar.value("iconWidth", 256);
                    v.iconHeight = jVar.value("iconHeight", 256);
                    if (!v.iconUrl.empty()) {
                        v.hasIcon = true;
                    }

                    // Security check on download URLs
                    if (!v.url.empty() && v.url.rfind("https://", 0) != 0) {
                        outError = "Insecure or invalid variant URL: " + v.url;
                        return false;
                    }
                    if (!v.iconUrl.empty() && v.iconUrl.rfind("https://", 0) != 0) {
                        outError = "Insecure or invalid icon URL: " + v.iconUrl;
                        return false;
                    }

                    entry.variants.push_back(std::move(v));
                }
            }

            parsedIndex[normTitleId] = parsedGames.size();
            parsedGames.push_back(std::move(entry));
        }

        m_games = std::move(parsedGames);
        m_titleIdIndex = std::move(parsedIndex);
        m_rawJson = jsonStr;
        return true;
    } catch (const std::exception& ex) {
        outError = std::string("JSON parse exception: ") + ex.what();
        return false;
    }
}

bool CatalogManager::loadFromFile(const std::string& filePath, std::string& outError) {
    std::ifstream file(filePath);
    if (!file.is_open()) {
        outError = "Could not open catalog file: " + filePath;
        return false;
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    return loadFromJsonString(buffer.str(), outError);
}

bool CatalogManager::saveToCacheFile(const std::string& cacheFilePath) const {
    if (m_rawJson.empty()) return false;
    std::error_code ec;
    std::filesystem::create_directories(std::filesystem::path(cacheFilePath).parent_path(), ec);
    std::ofstream file(cacheFilePath, std::ios::trunc);
    if (!file.is_open()) return false;
    file << m_rawJson;
    return true;
}

const GameCatalogEntry* CatalogManager::findByTitleId(const std::string& titleId) const {
    std::string norm = Config::normalizeTitleId(titleId);
    auto it = m_titleIdIndex.find(norm);
    if (it != m_titleIdIndex.end()) {
        return &m_games[it->second];
    }
    return nullptr;
}

std::vector<GameCatalogEntry> CatalogManager::searchByTitle(const std::string& keyword) const {
    std::vector<GameCatalogEntry> results;
    if (keyword.empty()) {
        return m_games;
    }

    std::string lowerKey = toLowerString(keyword);
    for (const auto& game : m_games) {
        std::string lowerTitle = toLowerString(game.title);
        std::string lowerTid = toLowerString(game.titleId);
        if (lowerTitle.find(lowerKey) != std::string::npos || lowerTid.find(lowerKey) != std::string::npos) {
            results.push_back(game);
        }
    }
    return results;
}

std::vector<GameCatalogEntry> CatalogManager::filterByStyle(CoverStyle style) const {
    if (style == CoverStyle::Unknown) {
        return m_games;
    }

    std::vector<GameCatalogEntry> results;
    for (const auto& game : m_games) {
        GameCatalogEntry filtered = game;
        filtered.variants.clear();
        for (const auto& v : game.variants) {
            if (v.style == style) {
                filtered.variants.push_back(v);
            }
        }
        if (!filtered.variants.empty()) {
            results.push_back(filtered);
        }
    }
    return results;
}

void CatalogManager::matchInstalledTitles(std::vector<InstalledTitle>& installedTitles) const {
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
}

} // namespace h3h
