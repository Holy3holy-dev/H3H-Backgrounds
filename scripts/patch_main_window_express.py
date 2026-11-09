from pathlib import Path

mw_path = Path("studio/h3h_studio/ui/main_window.py")
text = mw_path.read_text(encoding="utf-8")

# 1. Add import
if "from .express_tab import ExpressTab" not in text:
    text = text.replace(
        "from .github_publish_dialog import GitHubPublishDialog",
        "from .github_publish_dialog import GitHubPublishDialog\nfrom .express_tab import ExpressTab"
    )

# 2. Add Express Tab as the first tab in tabs
old_tab_block = """        self.tab_artwork = self._create_artwork_tab()
        self.tab_gameplay = self._create_gameplay_tab()
        self.tab_custom = self._create_custom_tab()

        self.tabs.addTab(self.tab_artwork, "Режим A: Animated Artwork (Изображение)")
        self.tabs.addTab(self.tab_gameplay, "Режим B: Gameplay & Trailer (Видеофрагмент)")
        self.tabs.addTab(self.tab_custom, "Режим C: Custom Video & Transcode (Анализ MP4)")"""

new_tab_block = """        self.tab_express = ExpressTab(self)
        self.tab_artwork = self._create_artwork_tab()
        self.tab_gameplay = self._create_gameplay_tab()
        self.tab_custom = self._create_custom_tab()

        self.tabs.addTab(self.tab_express, "⚡ Экспресс-публикатор 4IFIR (Фон / Иконка)")
        self.tabs.addTab(self.tab_artwork, "🎨 Режим A: Animated Artwork (Изображение)")
        self.tabs.addTab(self.tab_gameplay, "🎮 Режим B: Gameplay & Trailer (Видеофрагмент)")
        self.tabs.addTab(self.tab_custom, "⚙️ Режим C: Custom Video & Transcode (Анализ MP4)")"""

if old_tab_block in text:
    text = text.replace(old_tab_block, new_tab_block, 1)
    print("[+] Successfully added ExpressTab to tabs!")
else:
    # Try normalizing newlines
    normalized_old = old_tab_block.replace("\r\n", "\n")
    normalized_text = text.replace("\r\n", "\n")
    if normalized_old in normalized_text:
        normalized_text = normalized_text.replace(normalized_old, new_tab_block, 1)
        text = normalized_text
        print("[+] Successfully added ExpressTab to tabs (with normalized newlines)!")

mw_path.write_text(text, encoding="utf-8")
print("[+] main_window.py saved.")
