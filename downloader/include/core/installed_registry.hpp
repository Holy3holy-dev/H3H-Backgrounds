#pragma once

#include <string>
#include <map>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <mutex>
#include "core/json.hpp"
#include "core/config.hpp"

namespace h3h {

class InstalledRegistry {
public:
    static InstalledRegistry& instance() {
        static InstalledRegistry reg;
        return reg;
    }

    void load(const std::string& appDir) {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (!appDir.empty()) m_appDir = appDir;
        if (m_appDir.empty()) return;

        m_installedMap.clear();
        std::string filePath = m_appDir + "/installed_variants.json";
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
                    std::string normKey = Config::normalizeTitleId(it.key());
                    if (it.value().is_string()) {
                        m_installedMap[normKey] = it.value().get<std::string>();
                    } else if (it.value().is_object() && it.value().contains("variantId")) {
                        m_installedMap[normKey] = it.value()["variantId"].get<std::string>();
                    }
                }
            }
        } catch (...) {
            // Corrupted file, fallback gracefully
        }
    }

    void save(const std::string& appDir) {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (!appDir.empty()) m_appDir = appDir;
        if (m_appDir.empty()) return;

        std::error_code ec;
        std::filesystem::create_directories(m_appDir, ec);

        std::string filePath = m_appDir + "/installed_variants.json";
        std::string tmpPath = filePath + ".tmp";

        try {
            nlohmann::json root = nlohmann::json::object();
            for (const auto& [titleId, variantId] : m_installedMap) {
                root[Config::normalizeTitleId(titleId)] = variantId;
            }

            {
                std::ofstream file(tmpPath, std::ios::out | std::ios::trunc);
                if (file.is_open()) {
                    file << root.dump(2);
                    file.flush();
                }
            }

            // FatFs / Switch critical fix: remove destination first if it exists,
            // because on FatFs / devkitA64 rename() fails with EEXIST if target exists!
            if (std::filesystem::exists(filePath, ec)) {
                std::filesystem::remove(filePath, ec);
            }
            std::filesystem::rename(tmpPath, filePath, ec);
            if (ec) {
                // Direct write fallback if rename fails on any filesystem
                std::ofstream directFile(filePath, std::ios::out | std::ios::trunc);
                if (directFile.is_open()) {
                    directFile << root.dump(2);
                    directFile.flush();
                }
            }
        } catch (...) {
            // Graceful fallback
        }
    }

    std::string getVariantId(const std::string& titleId) const {
        std::lock_guard<std::mutex> lock(m_mutex);
        std::string norm = Config::normalizeTitleId(titleId);
        auto it = m_installedMap.find(norm);
        if (it != m_installedMap.end()) {
            return it->second;
        }
        return "";
    }

    void setVariantId(const std::string& appDir, const std::string& titleId, const std::string& variantId) {
        if (titleId.empty() || variantId.empty()) return;
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            m_installedMap[Config::normalizeTitleId(titleId)] = variantId;
        }
        save(appDir);
    }

    void remove(const std::string& appDir, const std::string& titleId) {
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            m_installedMap.erase(Config::normalizeTitleId(titleId));
        }
        save(appDir);
    }

private:
    InstalledRegistry() = default;
    mutable std::mutex m_mutex;
    std::string m_appDir;
    std::map<std::string, std::string> m_installedMap;
};

} // namespace h3h
