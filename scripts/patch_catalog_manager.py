from pathlib import Path

path = Path("downloader/src/core/catalog_manager.cpp")
content = path.read_text(encoding="utf-8")

old_target = """bool CatalogManager::loadFromJsonString(const std::string& jsonStr, std::string& outError) {
    try {
        json root = json::parse(jsonStr);"""

new_repl = """bool CatalogManager::loadFromJsonString(const std::string& jsonStr, std::string& outError) {
    if (jsonStr.empty()) {
        outError = "Получен пустой ответ от сервера";
        return false;
    }

    size_t startPos = 0;
    if (jsonStr.size() >= 3 &&
        static_cast<unsigned char>(jsonStr[0]) == 0xEF &&
        static_cast<unsigned char>(jsonStr[1]) == 0xBB &&
        static_cast<unsigned char>(jsonStr[2]) == 0xBF) {
        startPos = 3;
    }

    while (startPos < jsonStr.size() &&
           (jsonStr[startPos] == ' ' || jsonStr[startPos] == '\\t' ||
            jsonStr[startPos] == '\\r' || jsonStr[startPos] == '\\n')) {
        startPos++;
    }

    if (startPos >= jsonStr.size()) {
        outError = "Получен пустой документ";
        return false;
    }

    if (jsonStr[startPos] == '<') {
        outError = "Сервер вернул HTML-страницу (блокировка сети или авторизация Wi-Fi)";
        return false;
    }

    try {
        json root = json::parse(startPos == 0 ? jsonStr : jsonStr.substr(startPos));"""

if old_target in content:
    content = content.replace(old_target, new_repl, 1)
    print("Replaced target in catalog_manager.cpp")
else:
    print("Target not found!")

old_catch = """    } catch (const std::exception& ex) {
        outError = std::string("JSON parse exception: ") + ex.what();
        return false;
    }"""

new_catch = """    } catch (const std::exception& ex) {
        std::string snippet = jsonStr.substr(0, std::min<size_t>(jsonStr.size(), 80));
        outError = std::string("Ошибка парсинга JSON: ") + ex.what() + " [Начало ответа: " + snippet + "]";
        return false;
    }"""

if old_catch in content:
    content = content.replace(old_catch, new_catch, 1)
    print("Replaced catch in catalog_manager.cpp")
else:
    print("Catch not found!")

path.write_text(content, encoding="utf-8")
print("Done!")
