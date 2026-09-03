"""Produce a ZIP-level APK inventory without decompiling protected code."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Return the uppercase SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def inspect_apk(path: Path) -> dict[str, Any]:
    """Return non-secret ZIP metadata and selected library presence."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        dex_files = sorted(
            name
            for name in names
            if name.startswith("classes") and name.endswith(".dex")
        )
        native_libraries = sorted(name for name in names if name.endswith(".so"))
        selected_libraries = [
            name
            for name in native_libraries
            if any(word in name.casefold() for word in ("geely", "zeekr", "kiwi"))
        ]
        manifest = archive.getinfo("AndroidManifest.xml")
        return {
            "file_name": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "zip_entry_count": len(names),
            "dex_files": dex_files,
            "native_library_count": len(native_libraries),
            "selected_native_libraries": selected_libraries,
            "android_manifest_size": manifest.file_size,
        }


def main() -> int:
    """Print a deterministic JSON inventory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect_apk(args.apk.resolve(strict=True)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
