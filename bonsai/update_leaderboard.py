#!/usr/bin/env python3
"""Update the README's reigning row from trusted score and GitHub PR metadata."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


START = "<!-- bonsai-leaderboard:start -->"
END = "<!-- bonsai-leaderboard:end -->"
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")


def _merged_pr(records: Any, commit_sha: str) -> dict[str, Any] | None:
    if not isinstance(records, list):
        raise ValueError("associated pull requests must be a JSON array")
    matches = [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("merge_commit_sha") == commit_sha
        and isinstance(record.get("merged_at"), str)
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("merge commit is associated with multiple merged pull requests")
    return matches[0]


def update_text(
    readme: str,
    score: int,
    baseline_score: int,
    records: Any,
    commit_sha: str,
) -> str:
    """Return an updated README, or the original text for a non-PR push."""
    pull_request = _merged_pr(records, commit_sha)
    if pull_request is None:
        return readme
    number = pull_request.get("number")
    author = pull_request.get("user")
    login = author.get("login") if isinstance(author, dict) else None
    url = pull_request.get("html_url")
    if not isinstance(number, int) or number <= 0:
        raise ValueError("merged pull request has an invalid number")
    if not isinstance(login, str) or LOGIN.fullmatch(login) is None:
        raise ValueError("merged pull request has an invalid author login")
    expected_suffix = f"/pull/{number}"
    if not isinstance(url, str) or not url.startswith("https://github.com/") or not url.endswith(
        expected_suffix
    ):
        raise ValueError("merged pull request has an invalid URL")
    if not isinstance(score, int) or not isinstance(baseline_score, int):
        raise ValueError("scores must be integers")
    saved = baseline_score - score
    if saved < 0:
        raise ValueError("reigning score exceeds the season baseline")

    table = "\n".join(
        (
            "| Rank | Gardener | Score | Saved this season | Entry |",
            "|---:|---|---:|---:|---|",
            f"| 1 | [@{login}](https://github.com/{login}) | {score:,} | {saved:,} | "
            f"[#{number}]({url}) |",
        )
    )
    replacement = f"{START}\n\n{table}\n\n{END}"
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    updated, count = pattern.subn(replacement, readme)
    if count != 1:
        raise ValueError("README must contain exactly one leaderboard marker pair")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("readme", type=Path)
    parser.add_argument("score", type=Path)
    parser.add_argument("season", type=Path)
    parser.add_argument("pull_requests", type=Path)
    parser.add_argument("--commit-sha", required=True)
    arguments = parser.parse_args()

    score = json.loads(arguments.score.read_text(encoding="utf-8"))["total"]
    season = json.loads(arguments.season.read_text(encoding="utf-8"))
    records = json.loads(arguments.pull_requests.read_text(encoding="utf-8"))
    original = arguments.readme.read_text(encoding="utf-8")
    updated = update_text(original, score, season["initialScore"], records, arguments.commit_sha)
    if updated != original:
        arguments.readme.write_text(updated, encoding="utf-8")
        print("updated reigning leaderboard")
    else:
        print("leaderboard already current or no merged pull request is associated with this push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
