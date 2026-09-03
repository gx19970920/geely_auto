"""Tests for the repository secret scanner."""

import tempfile
from pathlib import Path

from scripts.scan_secrets import scan


def _temp_tree() -> Path:
    # Use a directory outside the repo (and outside pytest's basetemp, which
    # the scanner intentionally skips) so the scanner sees the test files.
    return Path(tempfile.mkdtemp(prefix="geely-scan-test-"))


def test_secret_scanner_accepts_clean_tree() -> None:
    root = _temp_tree()
    (root / "clean.py").write_text('token = "<redacted>"\n', encoding="utf-8")

    assert scan(root) == []


def test_secret_scanner_flags_phone() -> None:
    root = _temp_tree()
    phone = "137" + "2" * 8
    (root / "bad.txt").write_text(phone, encoding="utf-8")

    assert scan(root) == ["bad.txt:1:phone"]
