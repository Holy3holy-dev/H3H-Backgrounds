import json

with open('downloader/include/core/config.hpp', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('APP_VERSION = "1.4.2"', 'APP_VERSION = "1.4.3"')
text = text.replace('APP_VERSION = "1.4.1"', 'APP_VERSION = "1.4.3"')
with open('downloader/include/core/config.hpp', 'w', encoding='utf-8') as f:
    f.write(text)

with open('version.json', 'r', encoding='utf-8') as f:
    v = json.load(f)

v['latestVersion'] = '1.4.3'
v['downloadUrl'] = 'https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.4.3/H3H-Backgrounds.nro'
v['afterDarkDownloadUrl'] = 'https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.4.3/H3H-AfterDark.nro'
v['releaseUrl'] = 'https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/tag/v1.4.3'
v['releaseNotes'] = 'v1.4.3: Новые 3D кибер-иконки вкладок, прямой вход в каталог без промежуточных меню, мгновенное переключение [L] Весь каталог / [R] Избранное и добавление в избранное на кнопку [-]'
v['changelogRu'] = 'v1.4.3: Профессиональные 3D иконки и полное обновление каталога\n- Новые высокодетализированные 3D Cyber-Glass иконки для всех 5 разделов (Каталог, Видеоиконки, Менеджер игр, Загрузки, Настройки)\n- Полный редизайн Каталога: удалены все устаревшие категории, прямой переход к списку игр\n- Сегментные вкладки [L] Весь каталог (1073 игр) и [R] Избранное в шапке с быстрым переключением на L/R/X\n- Быстрое добавление и удаление из избранного клавишей [-] (Minus) прямо в списке с мгновенным сохранением\n- Кнопка быстрого видеопросмотра [ZL] со звуком прямо из каталога'

with open('version.json', 'w', encoding='utf-8') as f:
    json.dump(v, f, indent=2, ensure_ascii=False)

print("Bumped version to 1.4.3 successfully!")
