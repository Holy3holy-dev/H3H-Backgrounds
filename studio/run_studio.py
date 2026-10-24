import os
import sys
from pathlib import Path

def setup_ffmpeg_environment():
    candidates = []
    if hasattr(sys, '_MEIPASS'):
        candidates.append(Path(sys._MEIPASS))
    candidates.append(Path(sys.executable).parent)
    candidates.append(Path(__file__).resolve().parent)
    candidates.append(Path.cwd())
    
    for candidate in candidates:
        ffmpeg_file = candidate / "ffmpeg.exe"
        if ffmpeg_file.exists():
            candidate_str = str(candidate.resolve())
            current_path = os.environ.get("PATH", "")
            if candidate_str not in current_path:
                os.environ["PATH"] = candidate_str + os.pathsep + current_path
            break

setup_ffmpeg_environment()

# Add studio directory to sys.path so h3h_studio imports work reliably
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from h3h_studio.main import main

if __name__ == "__main__":
    main()
