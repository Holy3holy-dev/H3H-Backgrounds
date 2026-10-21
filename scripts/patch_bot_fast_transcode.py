from pathlib import Path

bot_file = Path("tg_bot/bot.py")
content = bot_file.read_text(encoding="utf-8")

old_passthrough = """def passthrough_switch_video(src_vid: Path, out_mp4: Path, out_thumb: Path, is_hevc: bool = False) -> bool:
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
    return True"""

new_passthrough = """def passthrough_switch_video(src_vid: Path, out_mp4: Path, out_thumb: Path, is_hevc: bool = False) -> bool:
    \"\"\"Copies pre-encoded Switch video stream without lossy re-encoding and generates thumbnail.\"\"\"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    cmd_copy = [
        "ffmpeg", "-y", "-nostdin",
        "-i", str(src_vid),
        "-c:v", "copy",
        "-an",
        "-sn",
        "-dn",
        "-movflags", "+faststart"
    ]
    if is_hevc:
        cmd_copy.extend(["-tag:v", "hvc1"])
    cmd_copy.append(str(out_mp4))

    subprocess.run(cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)

    cmd_thumb = [
        "ffmpeg", "-y", "-nostdin",
        "-threads", "1",
        "-ss", "1",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    except Exception:
        pass
    return True"""

old_transcode = """def transcode_to_switch_720p(src_vid: Path, out_mp4: Path, out_thumb: Path, codec: str = "h264") -> bool:
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

new_transcode = """def transcode_to_switch_720p(src_vid: Path, out_mp4: Path, out_thumb: Path, codec: str = "h264") -> bool:
    \"\"\"Converts input video to Switch 720p 30fps H.264 or HEVC (+faststart) and extracts thumbnail.\"\"\"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    out_thumb.parent.mkdir(parents=True, exist_ok=True)

    is_hevc = (codec.lower() in ("hevc", "h265"))

    # Optimized for cloud containers (Render CPU quota):
    # -threads 2 prevents CFS quota exhaustion & thread contention
    # flags=fast_bilinear avoids heavy floating-point software scaling
    # -crf 23 eliminates two-pass VBV buffer lookahead overhead
    cmd_ffmpeg = [
        "ffmpeg", "-y", "-nostdin",
        "-threads", "2",
        "-ss", "0",
        "-t", "30",
        "-i", str(src_vid),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "-threads", "2",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-an",
        "-sn",
        "-dn",
        "-movflags", "+faststart"
    ]

    if is_hevc:
        cmd_ffmpeg.extend([
            "-c:v", "libx265",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-x265-params", "fast-intra=1:no-info=1:no-open-gop=1:scenecut=0:pools=2:frame-threads=2",
            "-crf", "26",
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
            "-crf", "23",
            "-maxrate", "3500k",
            "-bufsize", "6000k",
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
        "-threads", "1",
        "-ss", "1",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "-f", "image2",
        str(out_thumb)
    ]
    try:
        subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
    except Exception:
        pass
    return True"""

normalized_content = content.replace("\r\n", "\n")
assert old_passthrough in normalized_content, "old_passthrough not found"
assert old_transcode in normalized_content, "old_transcode not found"

normalized_content = normalized_content.replace(old_passthrough, new_passthrough)
normalized_content = normalized_content.replace(old_transcode, new_transcode)

# Restore CRLF
bot_file.write_text(normalized_content.replace("\n", "\r\n"), encoding="utf-8")
print("[SUCCESS] Fast transcode patch applied cleanly to tg_bot/bot.py!")
