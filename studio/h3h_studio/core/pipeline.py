import re
import subprocess
import threading
from typing import Callable, List, Optional


class FFmpegPipeline:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.logs: List[str] = []
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def run(
        self,
        command: List[str],
        total_duration_sec: float,
        on_progress: Optional[Callable[[float], None]] = None,
        on_log: Optional[Callable[[str], None]] = None
    ) -> bool:
        self.logs.clear()
        self._is_cancelled = False

        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in command)
        self._add_log(f"[*] Executing command:\n{cmd_str}\n")

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )
        except Exception as e:
            self._add_log(f"[-] Execution error: {e}")
            return False

        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

        if self.process.stderr:
            for line in self.process.stderr:
                self._add_log(line.rstrip())
                if on_log:
                    on_log(line.rstrip())

                if on_progress and total_duration_sec > 0:
                    match = time_pattern.search(line)
                    if match:
                        hours, mins, secs = match.groups()
                        current_sec = int(hours) * 3600 + int(mins) * 60 + float(secs)
                        progress = min(1.0, current_sec / total_duration_sec)
                        on_progress(progress)

        self.process.wait()
        success = (self.process.returncode == 0) and not self._is_cancelled

        if success:
            self._add_log("\n[+] FFmpeg process completed successfully.")
            if on_progress:
                on_progress(1.0)
        else:
            self._add_log(f"\n[-] FFmpeg process terminated with code {self.process.returncode}")

        return success

    def _add_log(self, text: str):
        self.logs.append(text)
