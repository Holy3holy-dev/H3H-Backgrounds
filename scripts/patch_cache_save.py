with open('downloader/src/core/catalog_manager.cpp', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''bool CatalogManager::saveToCacheFile(const std::string& cacheFilePath) const {
    if (m_rawJson.empty()) return false;
    std::ofstream file(cacheFilePath, std::ios::trunc);
    if (!file.is_open()) return false;
    file << m_rawJson;
    return true;
}'''

replacement = '''bool CatalogManager::saveToCacheFile(const std::string& cacheFilePath) const {
    if (m_rawJson.empty()) return false;
    std::error_code ec;
    std::filesystem::create_directories(std::filesystem::path(cacheFilePath).parent_path(), ec);
    std::ofstream file(cacheFilePath, std::ios::trunc);
    if (!file.is_open()) return false;
    file << m_rawJson;
    return true;
}'''

content_norm = content.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
replacement_norm = replacement.replace('\r\n', '\n')

if target_norm in content_norm:
    new_content = content_norm.replace(target_norm, replacement_norm)
    with open('downloader/src/core/catalog_manager.cpp', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('SUCCESS: catalog_manager.cpp updated!')
else:
    print('Target not matched in catalog_manager.cpp.')
