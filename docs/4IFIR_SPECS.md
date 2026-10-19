# 4IFIR Video Background Specification

## 1. Context and Hardware Environment

4IFIR («Чефир») is a high-performance custom firmware ecosystem for Nintendo Switch. One of its standout visual features is **Videofon** (Video Covers / Backgrounds): when the user navigates the Switch Home Menu (qlaunch) or 4IFIR overlay, dynamic video clips can play in place of or behind the static game banners.

### 1.1 Target Directory
On the micro-SD card, 4IFIR monitors and plays files from:
```
sdmc:/recordings/covers/
```

### 1.2 File Naming Conventions
- Base format: `<TITLEID>.mp4`
- Example: `01005CA01580E000.mp4` (Teenage Mutant Ninja Turtles: Shredder's Revenge)
- Characteristics:
  - Title ID is a 64-bit integer formatted as a 16-character hexadecimal string.
  - Case-sensitivity: Existing files on user SD cards (FAT32 or exFAT) may have been written by Windows, macOS, or Linux, and could have lowercase, uppercase, or mixed-case hex letters (e.g., `01005ca01580e000.mp4`).
  - **Resolution rule:** File lookup must be strictly case-insensitive.
  - **Write rule:** New files written by H3H Downloader or H3H Studio MUST always use uppercase letters (`01005CA01580E000.mp4`) for strict determinism.

---

## 2. Hardware Decoding Capabilities & Constraints

The Nintendo Switch Tegra X1 (T210 / T210B01) contains an integrated **NVDEC** hardware video decoder. While the hardware can decode up to 4K H.264/HEVC/VP9 in dedicated media apps, background video in 4IFIR runs simultaneously alongside the system OS, background services, memory management, and potentially active games.

Therefore, video background assets MUST be encoded with a conservative, high-efficiency profile that ensures:
1. Low memory footprint (no risk of out-of-memory crashes in qlaunch).
2. Zero dropped frames or UI stutter during home menu scrolling.
3. Minimal battery drain and heat generation.
4. Instant seek / loop restart without playback hitches.

---

## 3. Verified 4IFIR Encoding Profile

Based on architectural benchmarks of Tegra X1 NVDEC in low-power background overlays:

| Parameter | Recommended Specification | Acceptable Range | Rationale |
| :--- | :--- | :--- | :--- |
| **Container** | MP4 (`.mp4`) | MP4 only | Standard ISO Base Media File Format |
| **Video Codec** | H.264 / AVC (`avc1`) | H.264 (Baseline, Main, High) | Universal hardware acceleration without licensing or CPU overhead |
| **H.264 Profile** | High Profile | Baseline / Main / High | High profile provides optimal compression at 720p/1080p |
| **H.264 Level** | Level 4.0 or 4.1 | Level 3.1 - 4.1 | Guaranteed hardware decode support on Tegra X1 NVDEC |
| **Resolution** | 1280x720 (720p) | 1280x720 to 1920x1080 | 720p matches handheld native display 1:1, saves ~60% RAM bandwidth over 1080p |
| **Aspect Ratio** | 16:9 | 16:9 | Matches Switch screen aspect ratio perfectly |
| **Pixel Format** | `yuv420p` (8-bit 4:2:0) | `yuv420p` strictly | 10-bit (`yuv420p10le`) or 4:2:2/4:4:4 forces software decode and WILL drop frames |
| **Frame Rate** | 30.0 fps (or 60.0 fps) | 24 - 60 fps (CFR preferred) | 30 fps is ideal for ambient looping; 60 fps acceptable for high-motion gameplay |
| **Bitrate** | 2,500 - 4,500 kbps (VBR) | 1,500 - 6,000 kbps | Keeps typical 15-30s loop between 5 MB and 15 MB |
| **GOP / Keyframe** | 1-2 seconds (e.g. `g=30` at 30fps) | <= 2 seconds | Crucial for seamless loop wrapping and instant playback start |
| **Container Flag** | `+faststart` (`moov` at front) | Required | Places index header at start of file for immediate stream reading |
| **Audio Stream** | None (Muted) OR AAC Stereo 44.1/48kHz | Muted or AAC | Most home menu backgrounds should be silent so they don't clash with BGM |

### Recommended FFmpeg Command for Studio Export
```bash
ffmpeg -y -i input.mp4 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p" \
  -c:v libx264 -preset slow -profile:v high -level 4.1 -crf 20 -maxrate 4500k -bufsize 9000k \
  -g 30 -keyint_min 30 -sc_threshold 0 \
  -an \
  -movflags +faststart \
  "01005CA01580E000.mp4"
```
*(If audio is preserved, use `-c:a aac -b:a 128k -ar 48000 -ac 2`)*.

---

## 4. Verification via FFprobe

All MP4 files processed in H3H Studio and added to the official catalog MUST pass automatic FFprobe validation:
1. `streams[0].codec_name == "h264"`
2. `streams[0].pix_fmt == "yuv420p"`
3. `streams[0].width <= 1920 && streams[0].height <= 1080`
4. Container format contains `mp4` or `mov`.
5. First atom is `ftyp` immediately followed by or with early `moov`.
