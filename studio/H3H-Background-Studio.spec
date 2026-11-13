# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:/videofon/studio/run_studio.py'],
    pathex=['E:/videofon/studio'],
    binaries=[('C:/Users/HL/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.1-full_build/bin/ffmpeg.exe', '.'), ('C:/Users/HL/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.1-full_build/bin/ffprobe.exe', '.')],
    datas=[('E:/videofon/studio/h3h_studio/data/switch_titles_db.json', 'h3h_studio/data'), ('E:/videofon/studio/h3h_studio/data/switch_home_template.png', 'h3h_studio/data')],
    hiddenimports=['PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'cv2', 'scenedetect', 'requests', 'PIL', 'h3h_studio', 'h3h_studio.core.title_id_resolver', 'h3h_studio.core.cloud_config', 'h3h_studio.core.express_processor', 'h3h_studio.core.online_fetcher', 'h3h_studio.core.animated_icons_fetcher', 'h3h_studio.ui.express_tab', 'h3h_studio.ui.icons_tab', 'h3h_studio.ui.online_icons_dialog', 'h3h_studio.ui.switch_preview_dialog'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='H3H-Background-Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['E:/videofon/studio/app_icon.ico'],
)
