#pragma once

#include <string>
#include <map>
#include <fstream>
#include <filesystem>
#include <iostream>
#include "core/json.hpp"

namespace h3h {

class InstalledRegistry {
public:
    static InstalledRegistry& instance() {
        static InstalledRegistry reg;
        return reg;
    }

    void load(const std::string& appDir) {
        m_appDir = appDir;
        m_installedMap.clear();
        std::string filePath = appDir + "/installed_variants.json";
        std::error_code ec;
        if (!std::filesystem::exists(filePath, ec)) {
            return;
        }

        std::ifstream file(filePath);
        if (!file.is_open()) return;

        try {
            nlohmann::json root;
            file >> root;
            if (root.is_object()) {
                for (auto it = root.begin(); it != root.end(); ++it) {
                    if (it.value().is_string()) {
                        m_installedMap[it.key()] = it.value().get<std::string>();
                    } else if (it.value().is_object() && it.value().contains("variantId")) {
                        m_installedMap[it.key()] = it.value()["variantId"].get<std::string>();
                    }
                }
            }
        } catch (...) {
            // Corrupted file, fallback gracefully
        }
    }

    void save(const std::string& appDir) {
        if (!appDir.empty()) m_appDir = appDir;
        if (m_appDir.empty()) return;

        std::error_code ec;
        std::filesystem::create_directories(m_appDir, ec);

        std::string filePath = m_appDir + "/installed_variants.json";
        std::string tmpPath = filePath + ".tmp";

        try {
            nlohmann::json root = nlohmann::json::object();
            for (const auto& [titleId, variantId] : m_installedMap) {
                root[titleId] = variantId;
            }

            {
                std::ofstream file(tmpPath);
                if (file.is_open()) {
                    file << root.dump(2);
                }
            }
            std::filesystem::rename(tmpPath, filePath, ec);
        } catch (...) {
            // Graceful fallback
        }
    }

    std::string getVariantId(const std::string& titleId) const {
        auto it = m_installedMap.find(titleId);
        if (it != m_installedMap.end()) {
            return it->second;
        }
        return "";
    }

    void setVariantId(const std::string& appDir, const std::string& titleId, const std::string& variantId) {
        if (titleId.empty() || variantId.empty()) return;
        m_installedMap[titleId] = variantId;
        save(appDir);
    }

    void remove(const std::string& appDir, const std::string& titleId) {
        m_installedMap.erase(titleId);
        save(appDir);
    }

private:
    InstalledRegistry() = default;
    std::string m_appDir;
    std::map<std::string, std::string> m_installedMap;
};

} // namespace h3h
