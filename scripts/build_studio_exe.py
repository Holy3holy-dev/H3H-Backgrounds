import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_studio():
    repo_root = Path(__file__).resolve().parent.parent
    studio_dir = repo_root / "studio"
    icon_path = studio_dir / "app_icon.ico"
    db_json = studio_dir / "h3h_studio" / "data" / "switch_titles_db.json"
    entry_point = studio_dir / "run_studio.py"
    dist_dir = studio_dir / "dist"
    build_dir = studio_dir / "build"

    winget_ffmpeg = Path(r"C:\Users\HL\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe")
    winget_ffprobe = Path(r"C:\Users\HL\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe")

    print("=" * 60)
    print("Building H3H Background Studio 100% Self-Contained Portable Exe")
    print("=" * 60)

    # Clean old build/dist
    if dist_dir.exists():
        shutil.rmtree(dist_dir, ignore_errors=True)
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "H3H-Background-Studio",
        f"--icon={icon_path}",
        f"--add-data={db_json};h3h_studio/data",
        "--paths", str(studio_dir),
        "--hidden-import", "PySide6.QtMultimedia",
        "--hidden-import", "PySide6.QtMultimediaWidgets",
        "--hidden-import", "cv2",
        "--hidden-import", "scenedetect",
        "--hidden-import", "requests",
        "--hidden-import", "PIL"
    ]

    # Embed ffmpeg and ffprobe directly into the onefile executable
    if winget_ffmpeg.exists():
        print(f"[+] Embedding FFmpeg binary into onefile: {winget_ffmpeg}")
        cmd.extend(["--add-binary", f"{winget_ffmpeg};."])
    if winget_ffprobe.exists():
        print(f"[+] Embedding FFprobe binary into onefile: {winget_ffprobe}")
        cmd.extend(["--add-binary", f"{winget_ffprobe};."])

    cmd.append(str(entry_point))

    print(f"Executing PyInstaller command...")
    res = subprocess.run(cmd, cwd=str(studio_dir))
    if res.returncode != 0:
        print(f"[-] PyInstaller failed with returncode {res.returncode}")
        return False

    exe_path = dist_dir / "H3H-Background-Studio.exe"
    if not exe_path.exists():
        print(f"[-] Target executable not found: {exe_path}")
        return False

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[+] Build succeeded! Executable size: {size_mb:.2f} MB ({exe_path.stat().st_size:,} bytes)")
    print(f"[+] Path: {exe_path}")

    # Copy to repo root for easy access
    root_exe = repo_root / "H3H-Background-Studio.exe"
    shutil.copy2(exe_path, root_exe)
    print(f"[+] Copied to: {root_exe}")

    # Create portable zip package
    portable_pkg_dir = dist_dir / "H3H-Background-Studio-Portable"
    portable_pkg_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(exe_path, portable_pkg_dir / "H3H-Background-Studio.exe")
    if winget_ffmpeg.exists():
        shutil.copy2(winget_ffmpeg, portable_pkg_dir / "ffmpeg.exe")
    if winget_ffprobe.exists():
        shutil.copy2(winget_ffprobe, portable_pkg_dir / "ffprobe.exe")

    # Add quick README
    readme_content = """==================================================
 H3H Background Studio (Portable Edition)
==================================================

Инструкция:
1. Запустите H3H-Background-Studio.exe
2. Программа готова к работе СРАЗУ:
   - FFmpeg и FFprobe уже полностью встроены внутрь программы!
   - Устанавливать Python, кодеки или настраивать переменные среды НЕ нужно.
3. Возможности:
   - Создание 10-20 секундных видеофонов для любых игр Nintendo Switch
   - Нарезка квадратных видеоиконок 4IFIR (256x256) в режиме 1:1
   - Отдельный скраббер и предпросмотр иконки с пресетами 2s, 4s, 6s, 8s
   - Кнопка «Как у фона» для мгновенной синхронизации таймингов
   - Прямая публикация в каталог сообщества H3H!

Создано для сообщества Nintendo Switch & 4IFIR.
"""
    (portable_pkg_dir / "README.txt").write_text(readme_content, encoding="utf-8")

    # Create zip archive
    zip_out = repo_root / "H3H-Background-Studio-v1.3.4-Portable.zip"
    print(f"[*] Packaging ZIP archive: {zip_out}...")
    shutil.make_archive(str(zip_out.with_suffix("")), "zip", str(portable_pkg_dir))
    zip_size_mb = zip_out.stat().st_size / (1024 * 1024)
    print(f"[+] ZIP Package created: {zip_out} ({zip_size_mb:.2f} MB)")

    return True

if __name__ == "__main__":
    success = build_studio()
    sys.exit(0 if success else 1)
