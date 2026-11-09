import json

with open('downloader/include/core/config.hpp', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('APP_VERSION = "1.4.1"', 'APP_VERSION = "1.4.2"')
with open('downloader/include/core/config.hpp', 'w', encoding='utf-8') as f:
    f.write(text)

with open('version.json', 'r', encoding='utf-8') as f:
    v = json.load(f)

v['latestVersion'] = '1.4.2'
v['downloadUrl'] = 'https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.4.2/H3H-Backgrounds.nro'
v['afterDarkDownloadUrl'] = 'https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.4.2/H3H-AfterDark.nro'
v['releaseUrl'] = 'https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/tag/v1.4.2'
v['releaseNotes'] = 'v1.4.2: Лаконичный каталог (Весь каталог и Избранное), живые 60 FPS анимации (пульсация, вращение шестерни, скейл плиток, эквалайзер) и новые HD иконки вкладок 4IFIR Cyber-Glass'
v['changelogRu'] = 'v1.4.2: Упрощённый каталог и живые анимации\n- Каталог оптимизирован под 2 ключевых раздела: «Весь каталог» и «Избранное» с мгновенным переключением на [L] и [R]\n- Плавные 60 FPS микроанимации: пружинящее увеличение плиток (1.055x), вращающаяся шестерня в настройках, подпрыгивающая стрелка загрузок, живой аудио-эквалайзер в шапке\n- Новые 160x160 4IFIR Cyber-Glass иконки высокого разрешения для всех вкладок дашборда\n- Дышащая неоновая подсветка активных карточек и тактильная анимация нажатия кнопок'

with open('version.json', 'w', encoding='utf-8') as f:
    json.dump(v, f, indent=2, ensure_ascii=False)

print("Bumped version to 1.4.2 successfully!")
