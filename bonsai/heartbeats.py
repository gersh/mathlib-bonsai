#!/usr/bin/env python3
"""Measure deterministic Lean elaboration heartbeats for selected source files.

Each file is elaborated sequentially with async elaboration disabled. A trusted
trailer reads Lean's internal allocation-based heartbeat counter at the end of
the file. The result is a performance guard, not the primary Bonsai score.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile


_MARKER = "BONSAI_HEARTBEATS_INTERNAL="
_TRAILER = f'''\n\n#eval do
  let count ← IO.getNumHeartbeats
  return s!"{_MARKER}{{count}}"
'''


class HeartbeatError(ValueError):
    """A source file could not be measured reliably."""


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
        raise HeartbeatError(f"invalid scored path: {value}")
    return Path(*item.parts)


def measure_file(root: Path, relative: str) -> int:
    path = root / validate_relative_path(relative)
    if not path.exists():
        return 0
    if path.is_symlink() or not path.is_file():
        raise HeartbeatError(f"{relative}: expected a regular source file")
    source = path.read_text(encoding="utf-8", errors="strict")
    if "\r" in source or "\x00" in source:
        raise HeartbeatError(f"{relative}: invalid Lean source encoding")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".bonsai-heartbeats-", suffix=".lean", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(source + _TRAILER, encoding="utf-8")
        environment = os.environ.copy()
        environment["CI"] = "true"
        process = subprocess.run(
            ["lake", "env", "lean", "-DElab.async=false", str(temporary)],
            cwd=root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    finally:
        temporary.unlink(missing_ok=True)
    if process.returncode:
        tail = process.stdout[-8000:]
        raise HeartbeatError(f"{relative}: elaboration failed\n{tail}")
    matches = re.findall(rf'^"{re.escape(_MARKER)}([0-9]+)"$', process.stdout, re.MULTILINE)
    if len(matches) != 1:
        raise HeartbeatError(f"{relative}: expected exactly one trusted heartbeat marker")
    return int(matches[0])


def measure_repository(root: Path, paths: list[str]) -> dict[str, object]:
    unique = sorted(set(paths))
    if not unique:
        raise HeartbeatError("no changed Lean source files to measure")
    files = {path: measure_file(root, path) for path in unique}
    return {
        "schema": 1,
        "metric": "lean-affected-file-elaboration-heartbeats-v1",
        "async": False,
        "unit": "internal-heartbeats",
        "total": sum(files.values()),
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    try:
        result = measure_repository(arguments.root.resolve(), arguments.paths)
    except (OSError, UnicodeError, HeartbeatError) as error:
        print(f"heartbeat error: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
