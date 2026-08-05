#!/usr/bin/env python3
"""Measure structural Lean source units for Mathlib Bonsai.

The primary score counts lexical structure, not spelling length. Identifiers,
keywords, operators, delimiters, and literals each cost one unit. Layout and all
Lean comment forms are free. Literal payload and non-layout source scalars are
recorded separately as anti-packing diagnostics.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import unicodedata


MAX_IDENTIFIER_SCALARS = 256
MAX_OPERATOR_SCALARS = 32
_SINGLETON_DELIMITERS = frozenset("()[]{}⟨⟩,;.")


class ScoreError(ValueError):
    """The source cannot be scored unambiguously."""


@dataclass(frozen=True)
class SourceScore:
    """The three measurements collected from one source string."""

    units: int = 0
    literal_payload: int = 0
    source_scalars: int = 0

    def plus(self, *, units: int = 0, literal_payload: int = 0,
             source_scalars: int = 0) -> "SourceScore":
        return SourceScore(
            self.units + units,
            self.literal_payload + literal_payload,
            self.source_scalars + source_scalars,
        )


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
    """Return the end of a syntactically shaped Lean character literal."""
    if text[offset] != "'" or offset + 2 >= len(text):
        return None
    cursor = offset + 1
    if text[cursor] in {"\n", "\r", "'"}:
        return None
    if text[cursor] != "\\":
        return cursor + 2 if text[cursor + 1] == "'" else None
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


def _identifier_char(char: str) -> bool:
    """A deliberately broad superset of Lean identifier-continuation chars."""
    return char in {"_", "'"} or unicodedata.category(char)[0] in {"L", "M", "N"}


def _check_token_length(length: int, limit: int, kind: str, source: str) -> None:
    if length > limit:
        raise ScoreError(
            f"{source}: {kind} has {length} scalars; the anti-packing limit is {limit}"
        )


def measure_source(text: str, *, source: str = "<string>") -> SourceScore:
    """Measure structural units, literal payload, and charged source scalars."""
    if "\r" in text:
        raise ScoreError(f"{source}: use LF line endings")
    if "\x00" in text:
        raise ScoreError(f"{source}: NUL is not valid Lean source")

    score = SourceScore()
    offset = 0
    size = len(text)
    while offset < size:
        char = text[offset]

        if char.isspace():
            offset += 1
            continue

        # Recognize comment markers everywhere outside protected literals. This
        # keeps custom operator syntax from making the scorer disagree with its
        # documented comment-removal rule.
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
            content_start = offset + opening_length
            end = text.find(closing, content_start)
            if end < 0:
                raise ScoreError(f"{source}: unterminated raw string")
            after = end + len(closing)
            score = score.plus(
                units=1,
                # Raw-string hash delimiters are data-bearing spelling too;
                # charge everything except the fixed r and two quote marks.
                literal_payload=after - offset - 3,
                source_scalars=after - offset,
            )
            offset = after
            continue

        char_end = _char_literal_end(text, offset)
        if char_end is not None:
            score = score.plus(
                units=1,
                literal_payload=char_end - offset - 2,
                source_scalars=char_end - offset,
            )
            offset = char_end
            continue

        if char == '"':
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
                elif current == '"':
                    break
            else:
                raise ScoreError(f"{source}: unterminated string literal")
            score = score.plus(
                units=1,
                literal_payload=offset - start - 2,
                source_scalars=offset - start,
            )
            continue

        if char == "«":
            end = text.find("»", offset + 1)
            if end < 0:
                raise ScoreError(f"{source}: unterminated quoted identifier")
            token_length = end - offset + 1
            _check_token_length(token_length - 2, MAX_IDENTIFIER_SCALARS,
                                "quoted identifier", source)
            score = score.plus(units=1, source_scalars=token_length)
            offset = end + 1
            continue

        if char.isdigit():
            start = offset
            offset += 1
            while offset < size and _identifier_char(text[offset]):
                offset += 1
            # Keep decimal fractions as one data-bearing literal, while leaving
            # name separators and range syntax as structural dots.
            if offset + 1 < size and text[offset] == "." and text[offset + 1].isdigit():
                offset += 1
                while offset < size and _identifier_char(text[offset]):
                    offset += 1
            token_length = offset - start
            score = score.plus(
                units=1,
                literal_payload=token_length,
                source_scalars=token_length,
            )
            continue

        if _identifier_char(char):
            start = offset
            offset += 1
            while offset < size and _identifier_char(text[offset]):
                offset += 1
            token_length = offset - start
            _check_token_length(token_length, MAX_IDENTIFIER_SCALARS, "identifier", source)
            score = score.plus(units=1, source_scalars=token_length)
            continue

        if char in _SINGLETON_DELIMITERS:
            score = score.plus(units=1, source_scalars=1)
            offset += 1
            continue

        start = offset
        offset += 1
        while offset < size:
            current = text[offset]
            if (
                current.isspace()
                or _identifier_char(current)
                or current in _SINGLETON_DELIMITERS
                or current in {'"', "«"}
                or text.startswith("--", offset)
                or text.startswith("/-", offset)
            ):
                break
            offset += 1
        token_length = offset - start
        _check_token_length(token_length, MAX_OPERATOR_SCALARS, "operator", source)
        score = score.plus(units=1, source_scalars=token_length)

    return score


def count_units(text: str, *, source: str = "<string>") -> int:
    """Return only the primary structural-unit score."""
    return measure_source(text, source=source).units


def score_file(path: Path) -> SourceScore:
    if path.is_symlink() or not path.is_file():
        raise ScoreError(f"{path}: every scored path must be a regular file")
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeError as error:
        raise ScoreError(f"{path}: source must be valid UTF-8") from error
    return measure_source(text, source=str(path))


def scored_files(root: Path) -> list[Path]:
    files = [root / "Mathlib.lean"]
    files.extend((root / "Mathlib").rglob("*.lean"))
    missing = [path for path in files if not path.exists()]
    if missing:
        raise ScoreError(f"missing scored source: {missing[0]}")
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def score_repository(root: Path) -> dict[str, object]:
    details: dict[str, int] = {}
    total = SourceScore()
    for path in scored_files(root):
        relative = path.relative_to(root).as_posix()
        score = score_file(path)
        details[relative] = score.units
        total = total.plus(
            units=score.units,
            literal_payload=score.literal_payload,
            source_scalars=score.source_scalars,
        )
    return {
        "schema": 2,
        "metric": "lean-structural-source-units-v1",
        "total": total.units,
        "literalPayload": total.literal_payload,
        "sourceScalars": total.source_scalars,
        "limits": {
            "identifierScalars": MAX_IDENTIFIER_SCALARS,
            "operatorScalars": MAX_OPERATOR_SCALARS,
        },
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
