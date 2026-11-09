import re
from pathlib import Path

path = Path("studio/h3h_studio/ui/express_tab.py")
content = path.read_text(encoding="utf-8")

# 1. Update imports to include QVideoSink and QVideoFrame
content = content.replace(
    "from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput",
    "from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink, QVideoFrame"
)

# 2. Update PublishWorker to take icon_start_sec
old_worker_init = '''    def __init__(
        self,
        src_video: Path,
        title_id: str,
        game_name: str,
        variant_name: str,
        author: str,
        category: str,
        mode: str,  # 'cover', 'icon', 'both'
        start_sec: float,
        dur_sec: float,
        icon_dur_sec: float,
        volume_percent: int,
        crop_pan: float,
        video_w: int,
        video_h: int
    ):'''

new_worker_init = '''    def __init__(
        self,
        src_video: Path,
        title_id: str,
        game_name: str,
        variant_name: str,
        author: str,
        category: str,
        mode: str,  # 'cover', 'icon', 'both'
        start_sec: float,
        dur_sec: float,
        icon_start_sec: float,
        icon_dur_sec: float,
        volume_percent: int,
        crop_pan: float,
        video_w: int,
        video_h: int
    ):'''

assert old_worker_init in content, "old_worker_init not found"
content = content.replace(old_worker_init, new_worker_init, 1)

old_worker_assign = '''        self.start_sec = start_sec
        self.dur_sec = dur_sec
        self.icon_dur_sec = icon_dur_sec'''

new_worker_assign = '''        self.start_sec = start_sec
        self.dur_sec = dur_sec
        self.icon_start_sec = icon_start_sec
        self.icon_dur_sec = icon_dur_sec'''

assert old_worker_assign in content, "old_worker_assign not found"
content = content.replace(old_worker_assign, new_worker_assign, 1)

# In worker run(), pass icon_start_sec
old_icon_process = '''                ExpressProcessor.process_icon(
                    src_vid=self.src_video,
                    out_mp4=icon_mp4,
                    out_thumb=icon_thumb,
                    start_sec=self.start_sec,
                    dur_sec=self.icon_dur_sec,
                    crop_pan_percent=self.crop_pan,
                    video_w=self.video_w,
                    video_h=self.video_h
                )'''

new_icon_process = '''                ExpressProcessor.process_icon(
                    src_vid=self.src_video,
                    out_mp4=icon_mp4,
                    out_thumb=icon_thumb,
                    start_sec=self.icon_start_sec,
                    dur_sec=self.icon_dur_sec,
                    crop_pan_percent=self.crop_pan,
                    video_w=self.video_w,
                    video_h=self.video_h
                )'''

assert old_icon_process in content, "old_icon_process not found"
content = content.replace(old_icon_process, new_icon_process, 1)

# Write updated content
path.write_text(content, encoding="utf-8")
print("[+] Successfully patched PublishWorker in express_tab.py")
