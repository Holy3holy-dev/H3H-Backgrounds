import subprocess
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from h3h_studio.core.analyzer import VideoAnalyzer, VideoAnalysis
from h3h_studio.core.encoder import Encoder, PROFILES
from h3h_studio.core.ken_burns import KenBurnsGenerator
from h3h_studio.core.project import StudioProject


class TestStudioCore(unittest.TestCase):
    def test_compliance_evaluation_pass(self):
        a = VideoAnalysis(
            file_path="sample.mp4",
            container="mov,mp4,m4a,3gp,3g2,mj2",
            codec="h264",
            profile="High",
            level="41",
            width=1280,
            height=720,
            fps=30.0,
            pixel_format="yuv420p",
            is_faststart=True
        )
        VideoAnalyzer._evaluate_compliance(a)
        self.assertTrue(a.is_compliant)
        self.assertEqual(len(a.issues), 0)

    def test_compliance_evaluation_reject_10bit(self):
        a = VideoAnalysis(
            file_path="sample_10bit.mp4",
            container="mp4",
            codec="h264",
            width=1280,
            height=720,
            fps=30.0,
            pixel_format="yuv420p10le",
            is_faststart=True
        )
        VideoAnalyzer._evaluate_compliance(a)
        self.assertFalse(a.is_compliant)
        self.assertTrue(any("pixel format" in issue.lower() for issue in a.issues))

    def test_compliance_evaluation_reject_hevc(self):
        a = VideoAnalysis(
            file_path="sample_hevc.mp4",
            container="mp4",
            codec="hevc",
            width=1280,
            height=720,
            fps=30.0,
            pixel_format="yuv420p",
            is_faststart=True
        )
        VideoAnalyzer._evaluate_compliance(a)
        self.assertFalse(a.is_compliant)
        self.assertTrue(any("codec" in issue.lower() for issue in a.issues))

    def test_encoder_command_structure(self):
        cmd = Encoder.build_transcode_command(
            input_path=Path("raw.mov"),
            output_path=Path("out.mp4"),
            profile=PROFILES["720p_30fps"],
            mute_audio=True
        )
        cmd_str = " ".join(cmd)
        self.assertIn("-c:v libx264", cmd_str)
        self.assertIn("-profile:v high", cmd_str)
        self.assertIn("-level 4.1", cmd_str)
        self.assertIn("scale=1280:720", cmd_str)
        self.assertIn("format=yuv420p", cmd_str)
        self.assertIn("-an", cmd_str)
        self.assertIn("+faststart", cmd_str)

    def test_ken_burns_command_structure(self):
        cmd = KenBurnsGenerator.build_artwork_command(
            image_path=Path("cover.png"),
            output_path=Path("artwork.mp4"),
            duration_sec=10.0,
            effect_type="sine_zoom"
        )
        cmd_str = " ".join(cmd)
        self.assertIn("zoompan=", cmd_str)
        self.assertIn("sin(2*PI*on/", cmd_str)
        self.assertIn("1280x720", cmd_str)
        self.assertIn("+faststart", cmd_str)

    def test_project_save_load_roundtrip(self):
        tmp_proj_file = Path("test_proj.h3hproj")
        try:
            p1 = StudioProject(
                game_title="TMNT Shredder's Revenge",
                title_id="01005CA01580E000",
                variant_name="Intro Action",
                style="Gameplay",
                duration_sec=22.5
            )
            p1.save(tmp_proj_file)

            p2 = StudioProject.load(tmp_proj_file)
            self.assertEqual(p2.game_title, "TMNT Shredder's Revenge")
            self.assertEqual(p2.title_id, "01005CA01580E000")
            self.assertEqual(p2.duration_sec, 22.5)
        finally:
            if tmp_proj_file.exists():
                tmp_proj_file.unlink()

    def test_real_ffmpeg_transcode_and_ffprobe_analysis(self):
        """End-to-end integration test: generate a real 720p 4IFIR MP4 and analyze with FFprobe."""
        ffmpeg = Encoder.get_ffmpeg_path()
        if not ffmpeg:
            self.skipTest("ffmpeg not available")

        test_out = Path("test_4ifir_sample.mp4")
        try:
            # Generate 1-second synthetic video using FFmpeg testsrc
            cmd = [
                ffmpeg, "-y",
                "-f", "lavfi", "-i", "testsrc=duration=1:size=1280x720:rate=30",
                "-c:v", "libx264", "-profile:v", "high", "-level", "4.1",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                str(test_out)
            ]
            subprocess.run(cmd, check=True, capture_output=True)

            # Analyze with VideoAnalyzer
            analysis = VideoAnalyzer.analyze_file(test_out)
            self.assertEqual(analysis.codec, "h264")
            self.assertEqual(analysis.width, 1280)
            self.assertEqual(analysis.height, 720)
            self.assertEqual(analysis.pixel_format, "yuv420p")
            self.assertEqual(analysis.fps, 30.0)
            self.assertTrue(analysis.is_faststart)
            self.assertTrue(analysis.is_compliant)
            self.assertEqual(len(analysis.issues), 0)

            # Check SHA-256 calculation
            sha = Encoder.calculate_file_sha256(test_out)
            self.assertEqual(len(sha), 64)
        finally:
            if test_out.exists():
                test_out.unlink()


if __name__ == "__main__":
    unittest.main()
