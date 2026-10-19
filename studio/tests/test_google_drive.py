"""
Unit tests for GoogleDriveHelper.
"""

import tempfile
import json
from pathlib import Path
import pytest

from studio.h3h_studio.core.google_drive import GoogleDriveHelper


class TestGoogleDriveHelper:
    def test_extract_file_id(self):
        urls = [
            ("https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view?usp=sharing", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
            ("https://drive.google.com/open?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
            ("https://drive.google.com/uc?export=download&id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
            ("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
        ]
        for url, expected in urls:
            assert GoogleDriveHelper.extract_file_id(url) == expected

    def test_to_direct_download_url(self):
        url = "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view?usp=sharing"
        direct = GoogleDriveHelper.to_direct_download_url(url)
        assert direct == "https://drive.google.com/uc?export=download&id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"

    def test_to_preview_url(self):
        url = "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view?usp=sharing"
        preview = GoogleDriveHelper.to_preview_url(url)
        assert preview == "https://drive.google.com/thumbnail?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs&sz=w640"

    def test_parse_batch_links(self):
        raw = """
        # My Game Covers on Google Drive
        01005CA01580E000 https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view?usp=sharing
        0100000000010000, https://drive.google.com/open?id=2CyjNWt1YSB6oGNeLwCeCakhVVrqumct
        """
        items = GoogleDriveHelper.parse_batch_links(raw)
        assert len(items) == 2
        assert items[0]["titleId"] == "01005CA01580E000"
        assert items[0]["driveId"] == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
        assert items[0]["directUrl"].startswith("https://drive.google.com/uc?export=download")
        assert items[1]["titleId"] == "0100000000010000"
        assert items[1]["driveId"] == "2CyjNWt1YSB6oGNeLwCeCakhVVrqumct"

    def test_extract_folder_id(self):
        folder_urls = [
            ("https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
            ("https://drive.google.com/drive/u/0/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs?usp=sharing", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
            ("https://drive.google.com/drive/u/1/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
            ("https://drive.google.com/open?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
            ("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"),
        ]
        for url, expected in folder_urls:
            assert GoogleDriveHelper.extract_folder_id(url) == expected


class TestGoogleDriveClient:
    def test_test_connection_no_token(self):
        from studio.h3h_studio.core.google_drive import GoogleDriveClient
        with pytest.raises(ValueError, match="не указан"):
            GoogleDriveClient.test_connection("")

    def test_test_connection_mock(self, monkeypatch):
        from studio.h3h_studio.core.google_drive import GoogleDriveClient
        import urllib.request
        from io import BytesIO

        mock_payload = {
            "user": {"displayName": "Switch User", "emailAddress": "user@gmail.com"},
            "storageQuota": {
                "limit": str(5 * 1024 * 1024 * 1024 * 1024),  # 5 TB
                "usage": str(500 * 1024 * 1024 * 1024)        # 500 GB
            }
        }

        class MockResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps(mock_payload).encode("utf-8")

        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=15: MockResponse())
        res = GoogleDriveClient.test_connection("dummy_token")
        assert res["ok"] is True
        assert res["displayName"] == "Switch User"
        assert res["emailAddress"] == "user@gmail.com"
        assert res["limit_gb"] == 5120.0
        assert res["usage_gb"] == 500.0
        assert "5120.0 ГБ" in res["quota_str"]

    def test_list_folder_files_mock(self, monkeypatch):
        from studio.h3h_studio.core.google_drive import GoogleDriveClient
        import urllib.request

        mock_files = {
            "files": [
                {"id": "file123", "name": "01007EF00011E000.mp4", "size": "15000000", "mimeType": "video/mp4"}
            ]
        }

        class MockResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return json.dumps(mock_files).encode("utf-8")

        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: MockResponse())
        files = GoogleDriveClient.list_folder_files("folder123", "dummy_token")
        assert len(files) == 1
        assert files[0]["name"] == "01007EF00011E000.mp4"

    def test_compliance_result_is_compliant_property(self):
        from studio.h3h_studio.core.compliance import ComplianceResult

        cr_valid = ComplianceResult(is_valid=True)
        assert cr_valid.is_valid is True
        assert cr_valid.is_compliant is True

        cr_invalid = ComplianceResult(is_valid=False, errors=["Too high FPS"])
        assert cr_invalid.is_valid is False
        assert cr_invalid.is_compliant is False

    def test_register_drive_video_with_compliance(self, tmp_path, monkeypatch):
        from studio.h3h_studio.core.compliance import ComplianceResult, ComplianceValidator
        from studio.h3h_studio.core.github_publisher import GitHubPublisher

        dummy_video = tmp_path / "01007EF00011E000.mp4"
        dummy_video.write_bytes(b"dummy video content" * 100)

        dummy_cat = tmp_path / "catalog.json"

        mock_cr = ComplianceResult(
            is_valid=True,
            width=1280,
            height=720,
            fps=30.0,
            duration_sec=15.0,
            codec="h264",
            has_audio=False
        )
        monkeypatch.setattr(ComplianceValidator, "validate", lambda p: mock_cr)
        monkeypatch.setattr(GitHubPublisher, "compute_sha256", lambda p: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

        res = GoogleDriveHelper.register_drive_video(
            catalog_path=dummy_cat,
            video_path=dummy_video,
            drive_url_or_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs",
            title_id="01007EF00011E000",
            game_title="Zelda TOTK"
        )
        assert res["success"] is True
        assert res["titleId"] == "01007EF00011E000"
        assert dummy_cat.exists()


