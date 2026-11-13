import re

# 1. Patch catalog_manager.cpp
with open("downloader/src/core/catalog_manager.cpp", "r", encoding="utf-8") as f:
    cat_code = f.read()

old_block = """            std::string rawTitleId = jGame.value("titleId", "");
            if (!Config::isValidTitleId(rawTitleId)) {
                outError = "Invalid Title ID format encountered: " + rawTitleId;
                return false;
            }

            std::string normTitleId = Config::normalizeTitleId(rawTitleId);
            if (parsedIndex.find(normTitleId) != parsedIndex.end()) {
                outError = "Duplicate Title ID in catalog: " + normTitleId;
                return false;
            }"""

new_block = """            std::string rawTitleId = jGame.value("titleId", "");
            if (!Config::isValidTitleId(rawTitleId)) {
                // Gracefully skip single invalid record rather than breaking entire 1900+ game catalog
                continue;
            }

            std::string normTitleId = Config::normalizeTitleId(rawTitleId);
            if (parsedIndex.find(normTitleId) != parsedIndex.end()) {
                // Skip duplicate Title ID gracefully
                continue;
            }"""

if old_block in cat_code:
    cat_code = cat_code.replace(old_block, new_block)
    with open("downloader/src/core/catalog_manager.cpp", "w", encoding="utf-8") as f:
        f.write(cat_code)
    print("[+] Successfully patched catalog_manager.cpp")
else:
    print("[-] Old block not matched in catalog_manager.cpp")

# Also check for empty parsed games check
old_finish = """        m_games = std::move(parsedGames);
        m_titleIdIndex = std::move(parsedIndex);"""

new_finish = """        if (parsedGames.empty()) {
            outError = "Каталог не содержит валидных записей игр";
            return false;
        }
        m_games = std::move(parsedGames);
        m_titleIdIndex = std::move(parsedIndex);"""

if old_finish in cat_code and "Каталог не содержит валидных записей игр" not in cat_code:
    cat_code = cat_code.replace(old_finish, new_finish)
    with open("downloader/src/core/catalog_manager.cpp", "w", encoding="utf-8") as f:
        f.write(cat_code)
    print("[+] Successfully added empty parsedGames guard in catalog_manager.cpp")
