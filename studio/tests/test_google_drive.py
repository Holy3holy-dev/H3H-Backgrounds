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
