"""Conservative repository scan for accidentally committed secret-shaped values."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_SKIP_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tools",
        ".venv",
        ".pytest-work",
        "captures",
        "ha-config",
        "worktools",
    }
)
_TEXT_SUFFIXES = frozenset(
    {".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
)
_PATTERNS = {
    "phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "vin": re.compile(r"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])"),
    "assigned_secret": re.compile(
        r"(?i)(access[_-]?token|refresh[_-]?token|authorization|cookie|password|"
        r"device[_-]?id)\s*[:=]\s*[\"']?(?!<redacted>|none|null|str\b)"
        r"[A-Za-z0-9_./+\-=]{12,}"
    ),
}


def scan(root: Path) -> list[str]:
    """Return relative paths and line numbers containing secret-shaped values."""
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in _TEXT_SUFFIXES:
            continue
        if any(part in _SKIP_PARTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "nosec-secret-scan" in line:
                continue
            for label, pattern in _PATTERNS.items():
                if pattern.search(line):
                    relative = path.relative_to(root)
                    findings.append(f"{relative}:{line_number}:{label}")
    return findings


def main() -> int:
    """Scan a repository and return nonzero when findings exist."""
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    findings = scan(args.root.resolve(strict=True))
    if findings:
        print("Potential sensitive values found:")
        print("\n".join(findings))
        return 1
    print("Secret-shaped value scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
