#!/usr/bin/env python3
"""Update the README's reigning row from trusted score and GitHub PR metadata."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


START = "<!-- bonsai-leaderboard:start -->"
END = "<!-- bonsai-leaderboard:end -->"
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
NUMBER = re.compile(r"(?:0|[1-9][0-9]{0,2}(?:,[0-9]{3})*)")
GARDENER = re.compile(
    r"\[@(?P<login>[A-Za-z0-9-]+)\]\(https://github\.com/(?P<profile>[A-Za-z0-9-]+)\)"
)
ENTRY_LINK = re.compile(
    r"\[#(?P<number>[1-9][0-9]*)\]\((?P<url>https://github\.com/[^/]+/[^/]+/pull/"
    r"(?P<link_number>[1-9][0-9]*))\)"
)
HEADER = "| Rank | Gardener | Score | Saved this season | Entry |"
DIVIDER = "|---:|---|---:|---:|---|"
BLOCK = re.compile(re.escape(START) + r"(?P<body>.*?)" + re.escape(END), re.DOTALL)


@dataclass(frozen=True)
class LeaderboardEntry:
    number: int
    login: str
    score: int
    url: str


def _formatted_number(value: str, field: str) -> int:
    if NUMBER.fullmatch(value) is None:
        raise ValueError(f"leaderboard has an invalid {field}")
    return int(value.replace(",", ""))


def _existing_entries(readme: str, baseline_score: int) -> list[LeaderboardEntry]:
    matches = list(BLOCK.finditer(readme))
    if len(matches) != 1:
        raise ValueError("README must contain exactly one leaderboard marker pair")
    lines = [line.strip() for line in matches[0].group("body").splitlines() if line.strip()]
    if len(lines) < 2 or lines[:2] != [HEADER, DIVIDER]:
        raise ValueError("README leaderboard header is invalid")
    entries: list[LeaderboardEntry] = []
    for expected_rank, line in enumerate(lines[2:], start=1):
        columns = [column.strip() for column in line.split("|")]
        if len(columns) != 7 or columns[0] or columns[-1]:
            raise ValueError("README leaderboard row is invalid")
        rank, gardener, score_text, saved_text, link = columns[1:6]
        gardener_match = GARDENER.fullmatch(gardener)
        link_match = ENTRY_LINK.fullmatch(link)
        if rank != str(expected_rank) or gardener_match is None or link_match is None:
            raise ValueError("README leaderboard row is invalid")
        login = gardener_match.group("login")
        if login != gardener_match.group("profile") or LOGIN.fullmatch(login) is None:
            raise ValueError("README leaderboard row has an invalid gardener")
        number = int(link_match.group("number"))
        if number != int(link_match.group("link_number")):
            raise ValueError("README leaderboard row has an invalid PR link")
        score = _formatted_number(score_text, "score")
        saved = _formatted_number(saved_text, "saved total")
        if saved != baseline_score - score:
            raise ValueError("README leaderboard saved total disagrees with its score")
        entries.append(LeaderboardEntry(number, login, score, link_match.group("url")))
    if len({entry.number for entry in entries}) != len(entries):
        raise ValueError("README leaderboard contains a duplicate PR")
    if entries != sorted(entries, key=lambda entry: entry.score):
        raise ValueError("README leaderboard is not ordered by score")
    return entries


def _render(readme: str, entries: list[LeaderboardEntry], baseline_score: int) -> str:
    rows = [HEADER, DIVIDER]
    for rank, entry in enumerate(entries, start=1):
        rows.append(
            f"| {rank} | [@{entry.login}](https://github.com/{entry.login}) | "
            f"{entry.score:,} | {baseline_score - entry.score:,} | "
            f"[#{entry.number}]({entry.url}) |"
        )
    replacement = f"{START}\n\n" + "\n".join(rows) + f"\n\n{END}"
    updated, count = BLOCK.subn(replacement, readme)
    if count != 1:
        raise ValueError("README must contain exactly one leaderboard marker pair")
    return updated


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
    if baseline_score - score < 0:
        raise ValueError("reigning score exceeds the season baseline")
    entries = _existing_entries(readme, baseline_score)
    prior = next((entry for entry in entries if entry.number == number), None)
    if prior is not None and prior.score != score:
        raise ValueError("replayed PR score disagrees with its recorded leaderboard score")
    if prior is None and score >= min((entry.score for entry in entries), default=baseline_score):
        raise ValueError("new leaderboard entry is not a strict improvement")
    entries = [entry for entry in entries if entry.number != number]
    entries.append(LeaderboardEntry(number, login, score, url))
    entries.sort(key=lambda entry: entry.score)
    return _render(readme, entries, baseline_score)


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
