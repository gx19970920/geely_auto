"""Create a sanitized copy of a JSON/HAR or text protocol capture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from custom_components.geely_auto.redaction import redact_data, redact_text

_SAME_FILE_MESSAGE = "Refusing to overwrite the source capture"


def sanitize_content(content: str) -> str:
    """Sanitize JSON while preserving structure, or sanitize plain text."""
    try:
        parsed: Any = json.loads(content)
    except json.JSONDecodeError:
        return redact_text(content)
    return json.dumps(redact_data(parsed), ensure_ascii=False, indent=2) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Write a sanitized copy of a capture; the input is never changed."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    return parser


def main() -> int:
    """Sanitize one capture into a separately named output file."""
    args = build_parser().parse_args()
    source = args.input.resolve(strict=True)
    target = args.output.resolve()
    if source == target:
        raise SystemExit(_SAME_FILE_MESSAGE)
    sanitized = sanitize_content(source.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(sanitized, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
