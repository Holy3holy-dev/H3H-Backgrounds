#pragma once

#include "core/types.hpp"
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>

namespace h3h {

class CatalogManager {
public:
    CatalogManager();

    // Load and parse catalog from raw JSON string
    bool loadFromJsonString(const std::string& jsonStr, std::string& outError);

    // Load from local file (cache or fixture)
    bool loadFromFile(const std::string& filePath, std::string& outError);

    // Save current catalog to local cache file
    bool saveToCacheFile(const std::string& cacheFilePath) const;

    // Queries
    size_t getGamesCount() const { return m_games.size(); }
    size_t getTotalVariantsCount() const;
    int getSchemaVersion() const { return m_schemaVersion; }
    const std::string& getUpdatedAt() const { return m_updatedAt; }

    const std::vector<GameCatalogEntry>& getAllGames() const { return m_games; }

    // Find game by Title ID (strictly case-insensitive)
    const GameCatalogEntry* findByTitleId(const std::string& titleId) const;

    // Search games by title keyword (case-insensitive substring)
    std::vector<GameCatalogEntry> searchByTitle(const std::string& keyword) const;

    // Filter by visual style
    std::vector<GameCatalogEntry> filterByStyle(CoverStyle style) const;

    // Match a list of installed titles against this catalog
    void matchInstalledTitles(std::vector<InstalledTitle>& installedTitles) const;

private:
    int m_schemaVersion{1};
    std::string m_updatedAt;
    std::vector<GameCatalogEntry> m_games;
    std::unordered_map<std::string, size_t> m_titleIdIndex; // Normalized uppercase -> index in m_games
    std::string m_rawJson;
};

} // namespace h3h
