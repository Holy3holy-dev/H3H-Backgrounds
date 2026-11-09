import os

app_cpp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloader", "src", "ui", "app.cpp")
with open(app_cpp_path, "r", encoding="utf-8") as f:
    text = f.read()

target = '''void App::executeDeleteCover(const std::string& titleId) {
    bool deleted = Installer::deleteCover(m_platform->getCoversDirectory(), titleId, false);
    if (deleted) {
        InstalledRegistry::instance().remove(m_platform->getAppDirectory(), titleId);
        m_statusNotification = "Видеофон удалён (копия .bak сохранена)";
    }

void App::executeCycleNextCover(const std::string& titleId) {
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
    refreshInstalledGames();
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
 else {
        m_statusNotification = "Видеофон не найден";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
    rebuildVideoIconsFilter();
}'''

fixed = '''void App::executeDeleteCover(const std::string& titleId) {
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
    refreshInstalledGames();
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
}'''

text_norm = text.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
fixed_norm = fixed.replace('\r\n', '\n')

if target_norm in text_norm:
    text_norm = text_norm.replace(target_norm, fixed_norm)
    with open(app_cpp_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text_norm)
    print('[+] app.cpp fixed successfully')
else:
    print('[-] target not found')
