#!/usr/bin/env python3
"""Compare Bonsai scores and compiler-generated theorem surfaces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_surface(path: Path) -> dict[str, object]:
    """Load the streaming JSON-lines format emitted by bonsai/surface.lean."""
    result: dict[str, object] = {"schema": None, "theorems": [], "axioms": [],
                                 "forbiddenAxioms": None}
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{number}: invalid JSON") from error
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{number}: expected an object")
            if number == 1:
                if record.get("schema") != 1 or record.get("rootModule") != "Mathlib":
                    raise ValueError(f"{path}: unsupported surface manifest")
                result["schema"] = 1
                continue
            kind = record.get("kind")
            if kind in {"theorem", "axiom"}:
                declaration = record.get("declaration")
                if not isinstance(declaration, dict):
                    raise ValueError(f"{path}:{number}: invalid declaration")
                target = "theorems" if kind == "theorem" else "axioms"
                assert isinstance(result[target], list)
                result[target].append(declaration)
            elif kind == "end":
                result["forbiddenAxioms"] = record.get("forbiddenAxioms")
            else:
                raise ValueError(f"{path}:{number}: invalid record kind")
    if result["schema"] != 1 or not isinstance(result["forbiddenAxioms"], list):
        raise ValueError(f"{path}: incomplete surface manifest")
    return result


def keyed_surface(value: object, path: Path) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise ValueError(f"{path}: unsupported surface manifest")
    declarations = value.get("theorems")
    if not isinstance(declarations, list):
        raise ValueError(f"{path}: missing theorem list")
    result: dict[str, dict[str, object]] = {}
    for item in declarations:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError(f"{path}: invalid theorem entry")
        name = item["name"]
        if name in result:
            raise ValueError(f"{path}: duplicate theorem {name}")
        result[name] = item
    return result


def compare_surfaces(baseline: object, candidate: object, baseline_path: Path,
                     candidate_path: Path) -> dict[str, object]:
    old = keyed_surface(baseline, baseline_path)
    new = keyed_surface(candidate, candidate_path)
    removed = sorted(old.keys() - new.keys())
    added = sorted(new.keys() - old.keys())
    changed = sorted(name for name in old.keys() & new.keys() if old[name] != new[name])

    old_axiom_entries = baseline.get("axioms") if isinstance(baseline, dict) else None
    new_axiom_entries = candidate.get("axioms") if isinstance(candidate, dict) else None
    old_axioms = {
        item.get("name"): item for item in old_axiom_entries
    } if isinstance(old_axiom_entries, list) else None
    new_axioms = {
        item.get("name"): item for item in new_axiom_entries
    } if isinstance(new_axiom_entries, list) else None
    axioms_changed = old_axioms != new_axioms
    candidate_forbidden = candidate.get("forbiddenAxioms") if isinstance(candidate, dict) else None
    forbidden = candidate_forbidden if isinstance(candidate_forbidden, list) else ["invalid manifest"]
    return {
        "compatible": not (removed or added or changed or axioms_changed or forbidden),
        "removed": removed,
        "added": added,
        "changed": changed,
        "axiomsChanged": axioms_changed,
        "forbiddenAxioms": forbidden,
        "baselineTheorems": len(old),
        "candidateTheorems": len(new),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_score", type=Path)
    parser.add_argument("candidate_score", type=Path)
    parser.add_argument("baseline_surface", type=Path)
    parser.add_argument("candidate_surface", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)

    try:
        baseline_score = load_json(args.baseline_score)
        candidate_score = load_json(args.candidate_score)
        baseline_surface = load_surface(args.baseline_surface)
        candidate_surface = load_surface(args.candidate_surface)
        if not isinstance(baseline_score, dict) or not isinstance(candidate_score, dict):
            raise ValueError("invalid score manifest")
        old_total = int(baseline_score["total"])
        new_total = int(candidate_score["total"])
        surface = compare_surfaces(
            baseline_surface, candidate_surface, args.baseline_surface, args.candidate_surface
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"comparison error: {error}", file=sys.stderr)
        return 2

    result = {
        "schema": 1,
        "baselineScore": old_total,
        "candidateScore": new_total,
        "delta": new_total - old_total,
        "smaller": new_total < old_total,
        "surface": surface,
        "accepted": new_total < old_total and bool(surface["compatible"]),
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")

    delta = result["delta"]
    sign = "+" if isinstance(delta, int) and delta >= 0 else ""
    status = "✅ eligible" if result["accepted"] else "❌ not eligible"
    markdown = (
        "## Mathlib Bonsai result\n\n"
        "| Check | Result |\n|---|---:|\n"
        f"| Baseline | {old_total:,} symbols |\n"
        f"| Candidate | {new_total:,} symbols |\n"
        f"| Change | {sign}{delta:,} symbols |\n"
        f"| Public theorem surface | {'exact match' if surface['compatible'] else 'changed'} |\n"
        f"| Verdict | {status} |\n"
    )
    if not surface["compatible"]:
        markdown += "\nThe first surface differences are:\n"
        for key in ("removed", "added", "changed", "forbiddenAxioms"):
            values = surface[key]
            if values:
                markdown += f"\n- {key}: " + ", ".join(f"`{item}`" for item in values[:10])
                if len(values) > 10:
                    markdown += f" (and {len(values) - 10} more)"
                markdown += "\n"
        if surface["axiomsChanged"]:
            markdown += "\n- the public Mathlib axiom set changed\n"
    if args.markdown:
        args.markdown.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
