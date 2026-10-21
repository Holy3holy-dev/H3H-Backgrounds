import re

path = r"downloader/include/ui/app.hpp"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add #include <set>
if "#include <set>" not in content:
    content = content.replace("#include <map>", "#include <map>\n#include <set>")

# 2. Add FavoritesOnly to CatalogSortMode and add StorageStats
old_sort_enum = """enum class CatalogSortMode {
    Default = 0,
    Alphabetical = 1,
    VariantsCount = 2,
    AudioOnly = 3,
    InstalledOnly = 4
};"""

new_sort_enum = """enum class CatalogSortMode {
    Default = 0,
    Alphabetical = 1,
    VariantsCount = 2,
    AudioOnly = 3,
    InstalledOnly = 4,
    FavoritesOnly = 5
};

struct StorageStats {
    uint64_t totalSdBytes{0};
    uint64_t freeSdBytes{0};
    int coversCount{0};
    uint64_t coversBytes{0};
    int thumbsCount{0};
    uint64_t thumbsBytes{0};
    int vidCacheCount{0};
    uint64_t vidCacheBytes{0};
};"""

assert old_sort_enum in content, "old_sort_enum not found"
content = content.replace(old_sort_enum, new_sort_enum)

# 3. Add method declarations after cycleCatalogSortMode()
old_methods = """    // Catalog Filtering, Sorting & Search
    void rebuildCatalogFilter();
    void openCatalogKeyboard();
    void cycleCatalogSortMode();"""

new_methods = """    // Catalog Filtering, Sorting & Search
    void rebuildCatalogFilter();
    void openCatalogKeyboard();
    void cycleCatalogSortMode();

    // Feature 1: Favorites System
    void loadFavorites();
    void saveFavorites();
    bool isVariantFavorite(const std::string& titleId, const std::string& variantId) const;
    void toggleFavoriteVariant(const std::string& titleId, const Variant& variant);
    bool hasGameFavorites(const std::string& titleId) const;

    // Feature 6: Storage & Cache Manager
    void refreshStorageStats();
    void clearThumbnailCache();
    void clearVideoPreviewCache();
    const StorageStats& getStorageStats() const { return m_storageStats; }

    // Feature 7: Batch Multi-Select Checklist
    void toggleBatchSelection(const std::string& titleId);
    void clearBatchSelection();
    void installBatchSelected();
    bool isBatchSelected(const std::string& titleId) const { return m_batchSelectedTitleIds.count(titleId) > 0; }
    size_t getBatchSelectionCount() const { return m_batchSelectedTitleIds.size(); }"""

assert old_methods in content, "old_methods not found"
content = content.replace(old_methods, new_methods)

# 4. Add private fields before end of class
old_priv = """    uint32_t m_lastTriggerTime{0};

};"""

new_priv = """    uint32_t m_lastTriggerTime{0};

    // Feature 1: Favorites
    std::set<std::string> m_favoriteKeys;

    // Feature 6: Storage Stats
    StorageStats m_storageStats;

    // Feature 7: Batch Selection
    std::set<std::string> m_batchSelectedTitleIds;

};"""

assert old_priv in content, "old_priv not found"
content = content.replace(old_priv, new_priv)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] app.hpp patched successfully")
