from pathlib import Path

harvester_file = Path("scripts/auto_video_harvester.py")
content = harvester_file.read_text(encoding="utf-8")

old_transcode = """    def transcode_video(self, raw_path: Path, out_mp4: Path, out_thumb: Path) -> bool:
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_thumb.parent.mkdir(parents=True, exist_ok=True)
        is_hevc = (self.codec == "hevc")

        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-t", "30",
            "-i", str(raw_path),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black",
            "-threads", "4",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart"
        ]"""

new_transcode = """    def check_audio_stream(self, raw_path: Path) -> bool:
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(raw_path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return bool(res.stdout.strip())
        except Exception:
            return False

    def transcode_video(self, raw_path: Path, out_mp4: Path, out_thumb: Path) -> tuple:
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_thumb.parent.mkdir(parents=True, exist_ok=True)
        is_hevc = (self.codec == "hevc")
        has_audio = self.check_audio_stream(raw_path)

        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-t", "30",
            "-i", str(raw_path),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black",
            "-threads", "4",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart"
        ]
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"])
        else:
            cmd.append("-an")"""

assert old_transcode in content, "old_transcode not found in auto_video_harvester.py"
content = content.replace(old_transcode, new_transcode)

# Replace return True/False in transcode_video
old_return = """        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        except Exception as e:
            print(f"[!] FFmpeg transcode error: {e}")
            return False

        # Thumbnail"""

new_return = """        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        except Exception as e:
            print(f"[!] FFmpeg transcode error: {e}")
            return False, False

        # Thumbnail"""

assert old_return in content, "old_return not found"
content = content.replace(old_return, new_return)

old_end_return = """        return True

    def process_and_upload_asset("""

new_end_return = """        return True, has_audio

    def process_and_upload_asset("""

assert old_end_return in content, "old_end_return not found"
content = content.replace(old_end_return, new_end_return)

# Update call in process_and_upload_asset
old_call = """            print(f"  -> Transcoding to 720p 30fps {self.codec.upper()}...")
            ok = self.transcode_video(raw_file, out_mp4, out_thumb)"""

new_call = """            print(f"  -> Transcoding to 720p 30fps {self.codec.upper()} (with audio auto-detection)...")
            ok, has_audio = self.transcode_video(raw_file, out_mp4, out_thumb)"""

assert old_call in content, "old_call not found"
content = content.replace(old_call, new_call)

# Update variant entry
old_var = """                "fps": 30.0,
                "hasAudio": False,
                "notes": f"Switch 720p 30fps {self.codec.upper()} | {var_name}"
            }"""

new_var = """                "fps": 30.0,
                "hasAudio": has_audio,
                "notes": f"Switch 720p 30fps {self.codec.upper()} | {var_name}" + (" | ЗВУК" if has_audio else "")
            }"""

assert old_var in content, "old_var not found"
content = content.replace(old_var, new_var)

harvester_file.write_text(content, encoding="utf-8")
print("[SUCCESS] auto_video_harvester.py patched with audio detection and AAC encoding!")
