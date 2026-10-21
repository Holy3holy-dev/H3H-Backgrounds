from pathlib import Path

p = Path("tg_bot/bot.py")
content = p.read_text(encoding="utf-8")

old_code = """def is_switch_720p_ready(stream_info: Dict[str, Any]) -> Tuple[bool, str]:
    \"\"\"Returns (is_ready, codec) if the video is already 1280x720 AVC or HEVC.\"\"\"
    codec = stream_info.get("codec_name", "").lower()
    width = stream_info.get("width", 0)
    height = stream_info.get("height", 0)

    if width == 1280 and height == 720:
        if codec in ("h264", "avc1"):
            return True, "h264"
        elif codec in ("hevc", "h265", "hvc1"):
            return True, "hevc"
    return False, codec

def passthrough_switch_video(src_vid: Path, out_mp4: Path, out_thumb: Path, is_hevc: bool = False) -> bool:
    \"\"\"Copies pre-encoded Switch video stream without lossy re-encoding and generates thumbnail.\"\"\"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    cmd_copy = [
        "ffmpeg", "-y", "-nostdin",
        "-i", str(src_vid),
        "-c:v", "copy",
        "-an",
        "-movflags", "+faststart"
    ]
    if is_hevc:
        cmd_copy.extend(["-tag:v", "hvc1"])
    cmd_copy.append(str(out_mp4))

    subprocess.run(cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)

    cmd_thumb = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "1",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    except Exception:
        pass
    return True

def transcode_to_switch_720p(src_vid: Path, out_mp4: Path, out_thumb: Path, codec: str = "h264") -> bool:
    \"\"\"Converts input video to Switch 720p 30fps H.264 or HEVC (+faststart) and extracts thumbnail.\"\"\"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    is_hevc = (codec.lower() in ("hevc", "h265"))

    cmd_ffmpeg = [
        "ffmpeg", "-y", "-nostdin",
        "-t", "30",
        "-i", str(src_vid),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
    ]

    if is_hevc:
        cmd_ffmpeg.extend([
            "-c:v", "libx265",
            "-preset", "ultrafast",
            "-threads", "2",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-b:v", "1800k",
            "-maxrate", "2400k",
            "-bufsize", "4000k",
            "-an",
            "-tag:v", "hvc1",
            "-movflags", "+faststart",
            str(out_mp4)
        ])
    else:
        cmd_ffmpeg.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-threads", "2",
            "-profile:v", "high",
            "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-b:v", "2500k",
            "-maxrate", "3000k",
            "-bufsize", "5000k",
            "-an",
            "-movflags", "+faststart",
            str(out_mp4)
        ])

    try:
        subprocess.run(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Конвертация FFmpeg превысила лимит времени (120с). Ролик слишком длинный или повреждён.")
    except subprocess.CalledProcessError as e:
        # Graceful fallback to libx264 if libx265 fails
        if is_hevc:
            return transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec="h264")
        err = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg ошибка: {err[-250:].strip()}")

    cmd_thumb = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "1",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
    except Exception:
        pass
    return True"""

new_code = """def is_switch_720p_ready(stream_info: Dict[str, Any]) -> Tuple[bool, str]:
    \"\"\"Returns (is_ready, codec) if the video is already 1280x720 AVC or HEVC.\"\"\"
    codec = stream_info.get("codec_name", "").lower()
    try:
        width = int(stream_info.get("width", 0))
        height = int(stream_info.get("height", 0))
    except (ValueError, TypeError):
        width, height = 0, 0

    if width == 1280 and height == 720:
        if codec in ("h264", "avc1"):
            return True, "h264"
        elif codec in ("hevc", "h265", "hvc1"):
            return True, "hevc"
    return False, codec

def passthrough_switch_video(src_vid: Path, out_mp4: Path, out_thumb: Path, is_hevc: bool = False) -> bool:
    \"\"\"Copies pre-encoded Switch video stream without lossy re-encoding and generates thumbnail.\"\"\"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    cmd_copy = [
        "ffmpeg", "-y", "-nostdin",
        "-i", str(src_vid),
        "-c:v", "copy",
        "-an",
        "-movflags", "+faststart"
    ]
    if is_hevc:
        cmd_copy.extend(["-tag:v", "hvc1"])
    cmd_copy.append(str(out_mp4))

    subprocess.run(cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)

    cmd_thumb = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "1",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    except Exception:
        pass
    return True

def transcode_to_switch_720p(src_vid: Path, out_mp4: Path, out_thumb: Path, codec: str = "h264") -> bool:
    \"\"\"Converts input video to Switch 720p 30fps H.264 or HEVC (+faststart) and extracts thumbnail.\"\"\"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    is_hevc = (codec.lower() in ("hevc", "h265"))

    # Fast input seek + 30s limit to avoid decoding huge files
    cmd_ffmpeg = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "0",
        "-t", "30",
        "-i", str(src_vid),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "-threads", "0",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart"
    ]

    if is_hevc:
        cmd_ffmpeg.extend([
            "-c:v", "libx265",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-x265-params", "fast-intra=1:no-info=1:no-open-gop=1:scenecut=0",
            "-b:v", "1800k",
            "-maxrate", "2400k",
            "-bufsize", "4000k",
            "-tag:v", "hvc1",
            str(out_mp4)
        ])
    else:
        cmd_ffmpeg.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-profile:v", "high",
            "-level", "4.1",
            "-b:v", "2500k",
            "-maxrate", "3000k",
            "-bufsize", "5000k",
            str(out_mp4)
        ])

    try:
        subprocess.run(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=300)
    except subprocess.TimeoutExpired:
        if is_hevc:
            print("[!] HEVC timed out on cloud CPU, auto-falling back to H.264 ultrafast...")
            return transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec="h264")
        raise RuntimeError("Конвертация FFmpeg превысила лимит времени (300с). Ролик слишком длинный или повреждён.")
    except subprocess.CalledProcessError as e:
        if is_hevc:
            return transcode_to_switch_720p(src_vid, out_mp4, out_thumb, codec="h264")
        err = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg ошибка: {err[-250:].strip()}")

    cmd_thumb = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "1",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
    except Exception:
        pass
    return True"""

if old_code in content:
    content = content.replace(old_code, new_code)
    p.write_text(content, encoding="utf-8")
    print("[+] Successfully patched tg_bot/bot.py with ultrafast encoder & auto-fallback!")
else:
    # Try normalizing line endings
    content_norm = content.replace("\r\n", "\n")
    old_norm = old_code.replace("\r\n", "\n")
    new_norm = new_code.replace("\r\n", "\n")
    if old_norm in content_norm:
        content_norm = content_norm.replace(old_norm, new_norm)
        p.write_text(content_norm, encoding="utf-8")
        print("[+] Successfully patched tg_bot/bot.py (normalized line endings)!")
    else:
        print("[-] Target code not found in tg_bot/bot.py")
