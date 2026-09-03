"""Tests for the repository secret scanner."""

from scripts.scan_secrets import scan


def test_secret_scanner_accepts_clean_tree(tmp_path) -> None:
    (tmp_path / "clean.py").write_text('token = "<redacted>"\n', encoding="utf-8")

    assert scan(tmp_path) == []


def test_secret_scanner_flags_phone(tmp_path) -> None:
    phone = "137" + "2" * 8
    (tmp_path / "bad.txt").write_text(phone, encoding="utf-8")

    assert scan(tmp_path) == ["bad.txt:1:phone"]
