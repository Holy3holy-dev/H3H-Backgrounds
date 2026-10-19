# H3H Backgrounds — Экосистема видеофонов для Nintendo Switch 4IFIR («Чефир»)

**H3H Backgrounds** — это открытая, высоконадёжная программная экосистема из трёх интегрированных продуктов, разработанная специально для кастомной прошивки **4IFIR** и её подсистемы динамических видеофонов (Videofon).

---

## 1. Архитектура экосистемы

```
+-------------------------------------------------------------------------------+
|                             GitHub Infrastructure                             |
|  +---------------------------+        +------------------------------------+  |
|  | GitHub Pages              |        | GitHub Releases                    |  |
|  | (Static Web + Catalog v1) |        | (MP4 Video Asset CDN)              |  |
|  +---------------------------+        +------------------------------------+  |
+-------------------------------------------------------------------------------+
           ^                                                ^
           | HTTPS JSON                                     | HTTPS MP4
           v                                                v
+--------------------------+    +-----------------------+   +-------------------+
|  H3H Backgrounds Library |    |   H3H Downloader      |   |  H3H Studio       |
|  (Web / React + Vite)    |    |   (Switch Homebrew)   |   |  (Windows Desktop)|
|                          |    |                       |   |                   |
| - Каталог видеофонов     |    | - Сканирование игр    |   | - Mode A: Artwork |
| - Мгновенный поиск       |    | - Title ID матчинг    |   | - Mode B: Game    |
| - Видеопревью            |    | - Проверка SHA-256    |   | - Mode C: Custom  |
| - Ручная загрузка MP4    |    | - Атомарный install   |   | - Анализ FFprobe  |
| - Модерация заявок       |    | - Бэкап и откат .bak  |   | - Экспорт в 4IFIR |
+--------------------------+    +-----------------------+   +-------------------+
```

---

## 2. Проверенный стандарт 4IFIR

- **Целевая директория на SD-карте:** `sdmc:/recordings/covers/`
- **Именование файла:** `<TITLEID>.mp4` (например: `01005CA01580E000.mp4` — TMNT: Shredder's Revenge)
- **Разрешение регистра:** Поиск существующих файлов на SD выполняется строго **без учёта регистра** (`01005ca01580e000.mp4` успешно находится). При записи новых файлов имя формируется строго в верхнем регистре.
- **Проверенный профиль кодирования:**
  - **Контейнер:** MP4 с флагом `+faststart` (атом `moov` в начале файла для мгновенного старта).
  - **Видеокодек:** H.264 / AVC High Profile, Level 4.1.
  - **Разрешение:** 1280x720 (720p) — 1:1 под экран Switch, экономит ~60% пропускной способности памяти по сравнению с 1080p.
  - **Формат пикселей:** `yuv420p` (8-bit 4:2:0) строго. 10-bit или 4:2:2 вызывают сброс на программное декодирование и просадки кадров на Tegra X1.
  - **Частота кадров:** 30.0 fps (CFR) для фоновых циклов; до 60.0 fps для динамичного геймплея.
  - **Аудио:** Без звука (`-an`) по умолчанию, либо AAC Stereo 48kHz.

---

## 3. Продукты экосистемы

### 3.1 H3H Backgrounds Downloader (`downloader/`)
Homebrew-приложение для Nintendo Switch (`.nro`):
- Определение установленных базовых игр через системные API `libnx` (`nsListApplicationRecord`, исключая DLC и обновления).
- Загрузка каталога по HTTPS с проверкой TLS и локальным кэшированием.
- Атомарная установка: скачивание во временный файл (`.tmp`), валидация размера и контрольной суммы SHA-256.
- При замене существующего фона старый файл автоматически сохраняется как `<TITLEID>.bak` с возможностью восстановления в один клик (`[X] Восстановить`).
- Аутентичный консольный UI на SDL2 (1280x720 VSync), навигация Joy-Con/Pro Controller, поддержка русского и английского языков.

### 3.2 H3H Backgrounds Library (`library/`)
Современный веб-каталог на React 19, TypeScript и Vite:
- Мгновенный поиск по названию игры и 16-значному Title ID.
- Фильтрация по стилям: *Cinematic*, *Gameplay*, *Animated Art*, *Minimal*, *Dark*, *Retro*, *Music*.
- Встроенный видеоплеер, карточки игр, копирование Title ID и SHA-256, инструкции по ручной установке.
- Форма подачи заявок от сообщества с валидацией Title ID в реальном времени и генератором GitHub Issue.
- Оптимизирован для ПК и смартфонов, статический деплой на GitHub Pages.

### 3.3 H3H Background Studio (`studio/`)
Windows-приложение на Python 3 и PySide6:
- **Режим A (Animated Artwork):** Импорт арта, создание математически бесшовного циклического движения камеры (Ken Burns sine-zoom, drift), виньетирование, экспорт.
- **Режим B (Gameplay / Trailer):** Импорт видео, нарезка фрагмента, создание плавного бесшовного перехода петли (crossfade loop seam), управление звуком.
- **Режим C (Custom Video):** Глубокий анализ существующих MP4 через FFprobe, проверка 6 критериев 4IFIR, отчёт об ошибках и транскодирование в один клик.
- Экспорт готовых `<TITLEID>.mp4` и сгенерированных метаданных каталога (`catalog_entry.json`).

---

## 4. Сборка и запуск

### 4.1 Nintendo Switch Downloader
- **Сборка через Docker CI (рекомендуется):**
  Автоматически собирается в GitHub Actions при каждом коммите с помощью контейнера `devkitpro/devkita64:latest`.
- **Локальная сборка `.nro` (при наличии devkitPro):**
  ```bash
  cd downloader
  make -j$(nproc)
  # Результат: downloader/H3H-Backgrounds.nro
  ```
- **Сборка и запуск десктопного симулятора/тестов (на ПК через g++):**
  ```bash
  g++ -std=c++17 -O2 -I downloader/include \
      downloader/src/core/*.cpp downloader/src/platform/desktop_platform.cpp downloader/src/ui/app.cpp downloader/src/main.cpp \
      -o downloader_sim.exe
  ./downloader_sim.exe
  ```

### 4.2 Web Library
```bash
cd library
npm install
npm run dev      # Запуск локального сервера разработки
npm run build    # Сборка статического сайта в dist/
```

### 4.3 Studio (Windows)
```bash
py run_studio.py
```

---

## 5. Тестирование и верификация

Все тесты выполняются автоматически и гарантируют 100% надёжность:

```bash
# 1. Тестирование ядра Downloader (SHA-256, Title ID, Catalog, Installer rollback):
g++ -std=c++17 -O2 -I downloader/include downloader/src/core/*.cpp downloader/src/platform/desktop_platform.cpp downloader/tests/test_core.cpp -o test_core.exe
./test_core.exe

# 2. Сквозное E2E тестирование 7 сценариев (установка, сетевой сбой, бэкап, откат, удаление, traversal):
g++ -std=c++17 -O2 -I downloader/include downloader/src/core/*.cpp downloader/src/platform/desktop_platform.cpp downloader/tests/test_e2e_scenarios.cpp -o test_e2e.exe
./test_e2e.exe

# 3. Валидация JSON схемы каталога:
py catalog/schema/test_validate_catalog.py
py catalog/schema/validate_catalog.py catalog/data/catalog.json

# 4. Тестирование H3H Studio (FFprobe анализ, H.264 профилирование, генерация Ken Burns, реальный FFmpeg транскодинг):
py studio/tests/test_studio.py
```

---

## 6. Безопасность и целостность данных

- Никаких изменений системных модулей, NAND (`bis:/`) или файлов игры (`.nsp`/`.xci`).
- Никакого доступа к сохранениям Nintendo Switch (`save:/`).
- Защита от path traversal: целевое имя файла формируется исключительно из проверенного 16-шестнадцатеричного Title ID.
- Автоматический откат при сбоях: существующие файлы никогда не удаляются без резервной копии (`.bak`).
