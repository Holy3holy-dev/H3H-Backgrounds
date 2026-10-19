# H3H Backgrounds — Design System

## 1. Visual Identity & Philosophy

**H3H Backgrounds** follows an authentic console UI philosophy:
- Purposeful, clean, and utilitarian without frivolous decorative noise.
- Designed specifically for 720p handheld and 1080p docked television viewing distances.
- High-contrast readability, crisp typography, and unambiguous focus states.
- Dedicated hardware-controller-first navigation.
- **Anti-AI Design Directive:** No generic purplish gradients, no glowing pseudo-glass cards, no arbitrary floating icons. Every visual element has a functional purpose.

---

## 2. Color Palette

The color system is inspired by high-grade dark mode console ergonomics with a vivid, warm cobalt/ember accent:

| Token | Hex Value | Usage |
| :--- | :--- | :--- |
| `color-bg-base` | `#121418` | Main screen background |
| `color-bg-surface` | `#1B1F26` | Card background, side navigation background |
| `color-bg-elevated`| `#252B35` | Popups, modals, active header panels |
| `color-border` | `#323B47` | Subtle dividers and card outlines |
| `color-focus-ring` | `#00E5FF` | High-visibility focus indicator (Cyan Neon) |
| `color-focus-fill` | `#0D3349` | Background highlight for selected list items |
| `color-text-primary`| `#FFFFFF` | Headings, game titles, active values |
| `color-text-muted` | `#9AA4B2` | Subtitles, Title IDs, file sizes, timestamps |
| `color-accent` | `#3B82F6` | Primary action button fill |
| `color-success` | `#10B981` | Installed badge, verified checksum indicator |
| `color-warning` | `#F59E0B` | Missing cover, backup available indicator |
| `color-danger` | `#EF4444` | Errors, delete confirmation |

---

## 3. Typography & Scaling

The interface renders at an internal logical coordinate space of **1280x720** (Handheld native), scaling smoothly with linear filtering to **1920x1080** when docked.

| Role | Size (720p) | Size (1080p) | Weight | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Hero Title** | 28 px | 42 px | Bold | App header, screen category |
| **Section Title** | 20 px | 30 px | Semi-Bold | Game title, modal title |
| **Body Regular** | 15 px | 22 px | Regular | Descriptions, variant info, button labels |
| **Monospace / Code** | 13 px | 19 px | Medium | 16-hex Title ID, SHA-256 hashes, paths |
| **Footnote / Badge** | 12 px | 18 px | Medium | Version numbers, duration, bitrate |

---

## 4. Controller Navigation & Input Mapping

Full Joy-Con and Nintendo Switch Pro Controller mapping:

| Input Button | Action (Switch Downloader) |
| :--- | :--- |
| **D-Pad / Left Stick** | Navigate items (Up/Down in lists, Left/Right in grids and tabs) |
| **(A)** | Primary Confirm / Select / Install / Open variant menu |
| **(B)** | Back / Cancel / Dismiss modal |
| **(X)** | Restore Backup (`.bak` -> `.mp4`) on selected title |
| **(Y)** | Delete installed cover (with confirmation prompt) |
| **(L) / (R)** | Switch main navigation tabs (Home -> My Games -> Catalog -> Downloads -> Settings) |
| **(+) Start** | Global quick action / manual refresh |
| **(-) Select** | Help overlay / Controller map cheat-sheet |

---

## 5. Main Screen Layouts

### 5.1 Screen 1: Dashboard (Главная)
- **Top Bar:** App title, current time, battery percentage, WiFi status, CFW status indicator (4IFIR Active).
- **Stat Cards (3 key metrics):**
  1. *Games Detected* (Total base games found on system).
  2. *Video Backgrounds Installed* (Matches found in `sdmc:/recordings/covers/`).
  3. *Catalog Availability* (Number of games with available covers in remote library).
- **Quick Jump Actions:** `[A] Browse My Games`, `[R] Open Remote Catalog`.

### 5.2 Screen 2: My Games (Мои игры)
- Left pane (400px): Vertical scroll list of installed games with 64x64 icon, title, Title ID, and status pill (`Installed`, `Update Available`, `No Cover`).
- Right pane (800px): Detail panel for selected game:
  - High-res icon, title, author, Title ID.
  - Active cover status (installed filename, file size, backup status).
  - List of available variants from catalog with direct `[A] Install` action.
  - Actions: `[X] Restore Backup`, `[Y] Delete Cover`.

### 5.3 Screen 3: Catalog (Каталог)
- Filter bar by style: `All`, `Cinematic`, `Gameplay`, `Animated Art`, `Minimal`, `Dark`.
- Grid/list view showing all available covers in the remote database.
- Fast indicator showing whether the title is currently installed on the user's Switch.

### 5.4 Screen 4: Downloads Queue (Загрузки)
- Live queue showing active and pending downloads.
- Real-time progress bar, downloaded / total bytes, current transfer speed (MB/s), estimated time remaining.
- Error state indicators with retry options.

### 5.5 Screen 5: Settings (Настройки)
- Catalog source URL configuration.
- Cache management: `Clear Local Catalog Cache`, `Scan SD for Orphan Covers`.
- Memory & Environment diagnostics: Applet Mode vs Application Mode, Heap usage, SD card free space.
- Language switcher: Russian (Русский) / English.

---

## 6. Bilingual Localization (RU / EN)

All user-visible strings are keyed into localization tables:
- `STR_NAV_HOME`: "Главная" / "Home"
- `STR_NAV_GAMES`: "Мои игры" / "My Games"
- `STR_NAV_CATALOG`: "Каталог" / "Catalog"
- `STR_NAV_DOWNLOADS`: "Загрузки" / "Downloads"
- `STR_NAV_SETTINGS`: "Настройки" / "Settings"
- `STR_BTN_INSTALL`: "Установить" / "Install"
- `STR_BTN_RESTORE`: "Восстановить копию" / "Restore Backup"
- `STR_BTN_DELETE`: "Удалить фон" / "Delete Cover"
- `STR_STATUS_INSTALLED`: "Установлен" / "Installed"
- `STR_STATUS_NO_COVER`: "Нет фона" / "No Cover"
- `STR_APPLET_WARNING`: "Запущено в режиме апплета (мало памяти). Для лучшей стабильности запускайте через [R] над игрой." / "Running in Applet Mode (limited memory). For optimal stability, launch by holding [R] over a game."
