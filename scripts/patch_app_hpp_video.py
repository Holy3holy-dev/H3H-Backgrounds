from pathlib import Path

path = Path("downloader/include/ui/app.hpp")
content = path.read_text(encoding="utf-8")

old_inc = '#include "ui/i18n.hpp"'
new_inc = '#include "ui/i18n.hpp"\n#include "ui/video_player.hpp"'

old_prev = """    std::string m_pendingPreviewFileToLoad;
    std::atomic<bool> m_previewLoading{false};
    std::thread m_previewThread;
    std::atomic<bool> m_cancelPreview{false};
    std::mutex m_previewMutex;"""

new_prev = """    std::string m_pendingPreviewFileToLoad;
    std::atomic<bool> m_previewLoading{false};
    std::thread m_previewThread;
    std::atomic<bool> m_cancelPreview{false};
    std::mutex m_previewMutex;

    // Live Video Playback inside Fullscreen Preview
    VideoPlayer m_videoPlayer;
    std::string m_pendingVideoToOpen;
    std::atomic<bool> m_videoDownloading{false};"""

assert old_inc in content, "old_inc not found"
assert old_prev in content, "old_prev not found"

content = content.replace(old_inc, new_inc, 1)
content = content.replace(old_prev, new_prev, 1)

path.write_text(content, encoding="utf-8")
print("Patched downloader/include/ui/app.hpp successfully!")
