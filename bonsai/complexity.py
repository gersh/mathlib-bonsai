#!/usr/bin/env python3
"""Measure parsed syntax and elaborated kernel-expression nodes in affected files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

_MARKER = "BONSAI_METRICS="


class ComplexityError(ValueError):
    """A source file could not be measured using the trusted Lean frontend."""


def validate_relative_path(value: str) -> Path:
    item = PurePosixPath(value)
    if (
        item.as_posix() != value
        or item.is_absolute()
        or any(part in {".", ".."} for part in item.parts)
        or not (value == "Mathlib.lean" or (
            len(item.parts) >= 2 and item.parts[0] == "Mathlib" and item.suffix == ".lean"
        ))
    ):
        raise ComplexityError(f"invalid scored path: {value}")
    return Path(*item.parts)


def measure_file(root: Path, relative: str, executable: Path) -> dict[str, int]:
    path = root / validate_relative_path(relative)
    if not path.exists():
        return {"syntaxNodes": 0, "kernelExpressionNodes": 0}
    if path.is_symlink() or not path.is_file():
        raise ComplexityError(f"{relative}: expected a regular source file")

    process = subprocess.run(
        ["lake", "env", str(executable), str(path.resolve())],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if process.returncode:
        raise ComplexityError(
            f"{relative}: trusted Lean measurement failed\n{process.stdout[-8000:]}"
        )
    matches = re.findall(rf"^{re.escape(_MARKER)}(.+)$", process.stdout, re.MULTILINE)
    if len(matches) != 1:
        raise ComplexityError(f"{relative}: expected exactly one trusted complexity marker")
    try:
        value = json.loads(matches[0])
    except json.JSONDecodeError as error:
        raise ComplexityError(f"{relative}: invalid trusted complexity marker") from error
    if (
        not isinstance(value, dict)
        or value.get("schema") != 1
        or not isinstance(value.get("syntaxNodes"), int)
        or value["syntaxNodes"] < 0
        or not isinstance(value.get("kernelExpressionNodes"), int)
        or value["kernelExpressionNodes"] < 0
    ):
        raise ComplexityError(f"{relative}: invalid trusted complexity result")
    return {
        "syntaxNodes": value["syntaxNodes"],
        "kernelExpressionNodes": value["kernelExpressionNodes"],
    }


def measure_repository(root: Path, paths: list[str], executable: Path) -> dict[str, object]:
    unique = sorted(set(paths))
    if not unique:
        raise ComplexityError("no changed Lean source files to measure")
    files = {path: measure_file(root, path, executable) for path in unique}
    return {
        "schema": 1,
        "metric": "lean-affected-file-complexity-v1",
        "syntaxNodes": sum(item["syntaxNodes"] for item in files.values()),
        "kernelExpressionNodes": sum(item["kernelExpressionNodes"] for item in files.values()),
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    try:
        result = measure_repository(
            arguments.root.resolve(), arguments.paths, arguments.executable.resolve()
        )
    except (OSError, UnicodeError, ComplexityError) as error:
        print(f"complexity error: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
