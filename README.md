# Mathlib Bonsai

**Cultivating smaller proofs in search of THE BOOK.**

Mathlib Bonsai is an experimental continuous competition to make Mathlib's proofs smaller without
changing the public theorem surface. The default branch is the reigning entry. Open a pull request
containing a smaller implementation; GitHub Actions builds it, compares every public theorem name
and elaborated type with the PR's base commit, checks its axioms, and reports the structural-unit
delta.

This is a new experiment, not a finished theory of proof quality. Metrics and safeguards may improve
between explicitly versioned seasons; results within a season keep one fixed contract.

The frozen starting point is
[`leanprover-community/mathlib4@b2418b0`](https://github.com/leanprover-community/mathlib4/commit/b2418b04047e1da8b7dd99534965d44fc1de9288),
using Lean `v4.33.0-rc2`. Its initial score is **18,900,593 structural units** across 8,303 Lean
files.

## Reigning Bonsai

<!-- bonsai-leaderboard:start -->

| Rank | Gardener | Score | Saved this season | Entry |
|---:|---|---:|---:|---|
| 1 | [@MrBrain295](https://github.com/MrBrain295) | 18,900,584 | 9 | [#4](https://github.com/gersh/mathlib-bonsai/pull/4) |
| 2 | [@gersh](https://github.com/gersh) | 18,900,589 | 4 | [#3](https://github.com/gersh/mathlib-bonsai/pull/3) |
| 3 | [@gersh](https://github.com/gersh) | 18,900,591 | 2 | [#2](https://github.com/gersh/mathlib-bonsai/pull/2) |

<!-- bonsai-leaderboard:end -->

Only strict improvements merge, so the first row is always the current champion; lower rows retain
every prior champion from the season. [See the current contenders](https://github.com/gersh/mathlib-bonsai/pulls?q=is%3Aopen+label%3Abonsai%3Aeligible).

## The idea

Paul Erdős liked to imagine *The Book*: a place containing the perfect proof of every theorem.
Martin Aigner and Günter Ziegler later collected candidates in
[*Proofs from THE BOOK*](https://link.springer.com/book/10.1007/978-3-662-04315-8)—proofs valued for
the idea they reveal, not merely their brevity.

Formal libraries give that old aspiration an unusual experimental tool. When the statements are
held fixed, compression forces us to look for shared lemmas, stronger abstractions, cleaner
arguments, and proofs that let the structure of the mathematics do more of the work. The score is
objective; beauty is not. A short proof can be a trick, and a beautiful proof may need a few more
units. This competition uses size as a searchlight, not as a definition of elegance.

Read [THE_BOOK.md](THE_BOOK.md) for the full vision.

## Enter in three steps

1. Fork this repository and create a branch from `main`.
2. Change only `Mathlib.lean` or `*.lean` files below `Mathlib/`. Keep all public theorem names and
   statements intact, and do not use `sorry` or new axioms.
3. In your fork, run **Actions → Submission proof → Run workflow** on your branch. Once it passes,
   open a pull request. The competition bot independently reports the old score, new score, delta,
   build result, and theorem-surface result.

A PR is eligible to merge when it builds with warnings as errors, has an exact public theorem
surface, uses only Lean's accepted foundational axioms, has a strictly lower structural score, and
measurably reduces elaboration heartbeats across the files it changes. Its parsed syntax-node and
elaborated kernel-expression counts over those files must also not increase.
Several proofs may be improved in one PR, though small, well-explained entries are easier to review.

```bash
# One-time setup
lake exe cache get

# Check the library and calculate your score
lake build --wfail Mathlib
python3 -m bonsai.scorer .

# Test the trusted scorer
python3 -m unittest discover -s bonsai/tests -v
```

The fork-side Submission proof action produces a downloadable proof artifact for the exact commit
you intend to submit. Because fork workflows are contributor-controlled, the central PR action
repeats the verification from trusted `main` tooling before declaring an entry eligible.

The complete contract, including what counts as a source unit and what the automation compares, is in
[RULES.md](RULES.md). Contribution and repository setup instructions are in
[CONTRIBUTING.md](CONTRIBUTING.md).

## What is measured?

The official score covers `Mathlib.lean` and every `Mathlib/**/*.lean` file. Each identifier,
keyword, operator, delimiter, or literal costs one structural unit; spelling length does not matter.
Comments and layout cost zero. Thus `by exact rfl` costs three units and `rfl` costs one, while
renaming `longLocalName` to `x` saves nothing.

Existing literals may remain or be deleted, but their exact spellings cannot be added or changed;
unusually large identifiers/operators are rejected, and raw character count is diagnostic only.
Every entry must also reduce affected-file elaboration heartbeats beyond a small deterministic-noise
allowance. Parsed syntax nodes and elaborated kernel `Expr` nodes are non-regression guards: the
former exposes ordinary macro packing, while the latter exposes complexity hidden by macros,
tactics, or elaborators. Documentation comments remain free. Together with a fixed toolchain, exact
theorem-surface comparison, axiom auditing, a scored-tree-only change policy, isolated trusted CI,
and human review, this blocks the obvious packing and generated-code shortcuts. Tests,
documentation, competition infrastructure, and generated `.olean` files are unscored and cannot be
changed by an entry. The detailed anti-evasion contract is in [RULES.md](RULES.md).

## What does “same surface” mean?

The trusted checker imports `Mathlib` and asks Lean for every public theorem originating in a
`Mathlib` module. For each theorem it compares the declaration name, universe arity, binder names
and binder modes, and the fully elaborated type expression. Proof bodies are intentionally omitted.
Lean-generated implementation details such as `_proof_1` and `match_2` are also omitted because
their unstable names are not a supported user surface.
Public Mathlib axioms must also remain identical, and proof dependencies may not introduce an axiom
outside `propext`, `Quot.sound`, and `Classical.choice`.

Public non-theorem declarations are frozen more strongly: their elaborated types and, where present,
their values must match. Thus an entry cannot make a definition trivial while leaving theorem types
spelled the same. The only public declaration bodies intended to vary are theorem proofs.

This is specifically a **public theorem-surface** competition. It does not promise binary or source
compatibility for notation, attributes, tactics, generated private details, or runtime behavior.
See [RULES.md](RULES.md) before relying on a loophole: semantic evasions are ineligible even when a
checker happens not to catch them yet.

## Merge order and conflicts

Maintainers review entries in the order they first become centrally eligible and review-ready.
After approval, native GitHub auto-merge may merge an entry once its trusted check is green against
current `main`. A PR keeps that position only while it can update cleanly and remains a strict
improvement. A conflict or a non-winning score removes it from the merge-ready line; after revision
it re-enters with a new ready time. This avoids blocking the contest or letting an old stalled PR
absorb later work. PR history still records credit for independent discoveries.

## From Bonsai back to Mathlib

Especially clear, reusable improvements may be good candidates for upstream Mathlib. Maintainers
and authors can collaborate on an upstream PR with the Bonsai contributor credited. Competition
acceptance does not imply upstream acceptance: Mathlib appropriately makes its own judgments about
style, generality, performance, and maintenance.

## Seasons

The project may periodically move to a newer Mathlib commit and Lean toolchain. Each migration
starts a named season with a new frozen surface and baseline score, so unlike scores are never
compared. AI-assisted bulk migration and compatibility repair are welcome, but the resulting
baseline must pass the same reproducible build, surface, soundness, and metric audit before the
season opens.

## License and attribution

The library begins from Mathlib and remains available under its Apache 2.0 license. Preserve source
attribution as required by [LICENSE](LICENSE) and the copyright headers in its source files.
