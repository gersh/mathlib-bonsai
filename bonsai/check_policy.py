#!/usr/bin/env python3
"""Reject Bonsai PR changes outside the scored Lean source tree."""

from __future__ import annotations

import argparse
from pathlib import PurePosixPath
import subprocess
import sys


def allowed(path: str) -> bool:
    item = PurePosixPath(path)
    return path == "Mathlib.lean" or (
        len(item.parts) >= 2 and item.parts[0] == "Mathlib" and item.suffix == ".lean"
    )


def changed_paths(repository: str, base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", repository, "diff", "--name-only", "-z", base, head],
        check=True,
        stdout=subprocess.PIPE,
    )
    return [part.decode("utf-8", errors="strict") for part in result.stdout.split(b"\0") if part]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository")
    parser.add_argument("base")
    parser.add_argument("head")
    args = parser.parse_args()
    try:
        paths = changed_paths(args.repository, args.base, args.head)
    except (subprocess.CalledProcessError, UnicodeError) as error:
        print(f"policy error: unable to inspect diff: {error}", file=sys.stderr)
        return 2
    rejected = [path for path in paths if not allowed(path)]
    if rejected:
        print("Contest entries may change only Mathlib Lean source:", file=sys.stderr)
        for path in rejected:
            print(f"  {path}", file=sys.stderr)
        return 1
    if not paths:
        print("policy error: the PR has no changes", file=sys.stderr)
        return 1
    print(f"Policy accepted {len(paths)} changed source file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
