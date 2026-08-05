#!/usr/bin/env python3
"""Count Lean source symbols according to the Mathlib Bonsai rules.

The official score is the number of Unicode scalar values in Lean tokens.  Layout
and all three forms of Lean comments (line, block, and documentation) are free.
Text inside string/character literals and quoted identifiers is still charged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


class ScoreError(ValueError):
    """The source cannot be scored unambiguously."""


def _raw_string_start(text: str, offset: int) -> tuple[int, str] | None:
    """Return (opening length, closing delimiter) for a raw string at offset."""
    if text[offset] != "r":
        return None
    cursor = offset + 1
    while cursor < len(text) and text[cursor] == "#":
        cursor += 1
    if cursor >= len(text) or text[cursor] != '"':
        return None
    hashes = cursor - offset - 1
    return cursor - offset + 1, '"' + "#" * hashes


def _char_literal_end(text: str, offset: int) -> int | None:
    """Return the end of a syntactically shaped Lean character literal.

    A bare apostrophe is also an identifier-continuation character in Lean, so
    treating every apostrophe as the start of a literal would mis-score names
    such as ``x'``.
    """
    if text[offset] != "'" or offset + 2 >= len(text):
        return None
    cursor = offset + 1
    if text[cursor] in {"\n", "\r", "'"}:
        return None
    if text[cursor] != "\\":
        return cursor + 1 if text[cursor + 1] == "'" else None
    cursor += 1
    if cursor >= len(text):
        return None
    escape = text[cursor]
    width = 2 if escape == "x" else 4 if escape == "u" else 8 if escape == "U" else 0
    if width:
        digits = text[cursor + 1 : cursor + 1 + width]
        cursor += 1 + width
        if len(digits) != width or any(char not in "0123456789abcdefABCDEF" for char in digits):
            return None
    else:
        cursor += 1
    return cursor + 1 if cursor < len(text) and text[cursor] == "'" else None


def count_symbols(text: str, *, source: str = "<string>") -> int:
    """Count charged Unicode scalar values in one Lean source file."""
    if "\r" in text:
        raise ScoreError(f"{source}: use LF line endings")
    if "\x00" in text:
        raise ScoreError(f"{source}: NUL is not valid Lean source")

    count = 0
    offset = 0
    size = len(text)
    while offset < size:
        char = text[offset]

        # Layout outside a token is free. Lean itself only accepts spaces and
        # newlines as layout, but isspace catches invalid layout consistently;
        # the build is responsible for rejecting invalid Lean.
        if char.isspace():
            offset += 1
            continue

        # This deliberately recognizes a comment marker whenever it occurs in
        # code, a stricter rule than Lean's "not part of another token" wording.
        # It prevents custom operator syntax from turning comments into a way to
        # fool the counter.
        if text.startswith("--", offset):
            newline = text.find("\n", offset + 2)
            offset = size if newline < 0 else newline + 1
            continue
        if text.startswith("/-", offset):
            depth = 1
            offset += 2
            while offset < size and depth:
                if text.startswith("/-", offset):
                    depth += 1
                    offset += 2
                elif text.startswith("-/", offset):
                    depth -= 1
                    offset += 2
                else:
                    offset += 1
            if depth:
                raise ScoreError(f"{source}: unterminated block comment")
            continue

        raw = _raw_string_start(text, offset)
        if raw is not None:
            opening_length, closing = raw
            end = text.find(closing, offset + opening_length)
            if end < 0:
                raise ScoreError(f"{source}: unterminated raw string")
            after = end + len(closing)
            count += after - offset
            offset = after
            continue

        char_end = _char_literal_end(text, offset)
        if char_end is not None:
            count += char_end - offset
            offset = char_end
            continue

        if char == '"':
            delimiter = char
            start = offset
            offset += 1
            escaped = False
            while offset < size:
                current = text[offset]
                offset += 1
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == delimiter:
                    break
            else:
                raise ScoreError(f"{source}: unterminated {delimiter} literal")
            count += offset - start
            continue

        if char == "«":
            end = text.find("»", offset + 1)
            if end < 0:
                raise ScoreError(f"{source}: unterminated quoted identifier")
            after = end + 1
            count += after - offset
            offset = after
            continue

        count += 1
        offset += 1

    return count


def score_file(path: Path) -> int:
    if path.is_symlink():
        raise ScoreError(f"{path}: symlinks are not allowed in the scored tree")
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeError as error:
        raise ScoreError(f"{path}: source must be valid UTF-8") from error
    return count_symbols(text, source=str(path))


def scored_files(root: Path) -> list[Path]:
    files = [root / "Mathlib.lean"]
    files.extend((root / "Mathlib").rglob("*.lean"))
    missing = [path for path in files if not path.exists()]
    if missing:
        raise ScoreError(f"missing scored source: {missing[0]}")
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def score_repository(root: Path) -> dict[str, object]:
    details: dict[str, int] = {}
    for path in scored_files(root):
        relative = path.relative_to(root).as_posix()
        details[relative] = score_file(path)
    return {
        "schema": 1,
        "metric": "lean-unicode-scalars-without-comments-or-layout",
        "total": sum(details.values()),
        "files": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", help="emit the full JSON result")
    parser.add_argument("--output", type=Path, help="also write JSON to this path")
    arguments = parser.parse_args(argv)
    try:
        result = score_repository(arguments.root.resolve())
    except (OSError, ScoreError) as error:
        print(f"score error: {error}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    if arguments.json:
        sys.stdout.write(rendered)
    else:
        print(result["total"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
