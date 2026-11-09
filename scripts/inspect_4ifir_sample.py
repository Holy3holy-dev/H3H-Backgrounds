import subprocess
import json
from pathlib import Path

for name, rel in [('COVER', 'tmp/4ifir_video_icons_sample/recordings/covers/010090F012916000.mp4'),
                  ('ICON', 'tmp/4ifir_video_icons_sample/recordings/icons/010090F012916000.mp4')]:
    cmd = ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', rel]
    res = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(res.stdout)
    print(f'=== {name} ({rel}) ===')
    fmt = data.get('format', {})
    print(f"Duration: {fmt.get('duration')}s, Bitrate: {fmt.get('bit_rate')} bps, Size: {fmt.get('size')} bytes")
    for s in data.get('streams', []):
        ctype = s.get('codec_type')
        cname = s.get('codec_name')
        if ctype == 'video':
            print(f"Video: {cname} ({s.get('profile')}), {s.get('width')}x{s.get('height')}, fps: {s.get('r_frame_rate')}, pix_fmt: {s.get('pix_fmt')}")
            print(f"  Color range: {s.get('color_range')}, space: {s.get('color_space')}")
            print(f"  Nb frames: {s.get('nb_frames')}")
        elif ctype == 'audio':
            print(f"Audio: {cname}, {s.get('sample_rate')} Hz, {s.get('channels')} ch")
