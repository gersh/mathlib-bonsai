# Mathlib Bonsai

**Cultivating smaller proofs in search of THE BOOK.**

Mathlib Bonsai is a continuous competition to make Mathlib's proofs smaller without changing the
public theorem surface. The default branch is the reigning entry. Open a pull request containing a
smaller implementation; GitHub Actions builds it, compares every public theorem name and elaborated
type with the PR's base commit, checks its axioms, and reports the symbol delta.

The frozen starting point is
[`leanprover-community/mathlib4@b2418b0`](https://github.com/leanprover-community/mathlib4/commit/b2418b04047e1da8b7dd99534965d44fc1de9288),
using Lean `v4.33.0-rc2`. Its initial score is **58,332,428 symbols** across 8,303 Lean files.

## Reigning Bonsai

| Rank | Gardener | Score | Saved this season | Entry |
|---:|---|---:|---:|---|
| 1 | [Mathlib community](https://github.com/leanprover-community/mathlib4/graphs/contributors) | 58,332,428 | — | Season 1 baseline |

Only strict improvements merge, so the first row is always the current champion. The accepted PR
history is the season's record book. [See the current contenders](https://github.com/gersh/mathlib-bonsai/pulls?q=is%3Aopen+label%3Abonsai%3Aeligible).

## The idea

Paul Erdős liked to imagine *The Book*: a place containing the perfect proof of every theorem.
Martin Aigner and Günter Ziegler later collected candidates in
[*Proofs from THE BOOK*](https://link.springer.com/book/10.1007/978-3-662-04315-8)—proofs valued for
the idea they reveal, not merely their brevity.

Formal libraries give that old aspiration an unusual experimental tool. When the statements are
held fixed, compression forces us to look for shared lemmas, stronger abstractions, cleaner
arguments, and proofs that let the structure of the mathematics do more of the work. The score is
objective; beauty is not. A short proof can be a trick, and a beautiful proof may need a few more
symbols. This competition uses size as a searchlight, not as a definition of elegance.

Read [THE_BOOK.md](THE_BOOK.md) for the full vision.

## Enter in three steps

1. Fork this repository and create a branch from `main`.
2. Change only `Mathlib.lean` or `*.lean` files below `Mathlib/`. Keep all public theorem names and
   statements intact, and do not use `sorry` or new axioms.
3. In your fork, run **Actions → Submission proof → Run workflow** on your branch. Once it passes,
   open a pull request. The competition bot independently reports the old score, new score, delta,
   build result, and theorem-surface result.

A PR is eligible to merge when it builds with warnings as errors, has an exact public theorem
surface, uses only Lean's accepted foundational axioms, and has a strictly lower total score.
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

The complete contract, including what counts as a symbol and what the automation compares, is in
[RULES.md](RULES.md). Contribution and repository setup instructions are in
[CONTRIBUTING.md](CONTRIBUTING.md).

## What is measured?

The official score covers `Mathlib.lean` and every `Mathlib/**/*.lean` file. One Unicode scalar
value in Lean source costs one symbol. Comments and layout whitespace cost zero. Text inside
strings, character literals, raw strings, and quoted identifiers is semantic source and is charged.
UTF-8 bytes, generated `.olean` files, tests, documentation, and competition infrastructure are not
part of the score.

This metric makes `∀` and `x` cost the same, makes formatting free, and keeps long local or tactic
names honest. Entrants cannot move code into an unscored file: CI rejects every PR change outside
the scored tree.

## What does “same surface” mean?

The trusted checker imports `Mathlib` and asks Lean for every public theorem originating in a
`Mathlib` module. For each theorem it compares the declaration name, universe arity, binder names
and binder modes, and the fully elaborated type expression. Proof bodies are intentionally omitted.
Lean-generated implementation details such as `_proof_1` and `match_2` are also omitted because
their unstable names are not a supported user surface.
Public Mathlib axioms must also remain identical, and proof dependencies may not introduce an axiom
outside `propext`, `Quot.sound`, and `Classical.choice`.

This is specifically a **public theorem-surface** competition. It does not promise binary or source
compatibility for every public definition, notation, attribute, tactic, or runtime behavior. See
[RULES.md](RULES.md) before relying on a loophole: semantic evasions are ineligible even when a
checker happens not to catch them yet.

## License and attribution

The library begins from Mathlib and remains available under its Apache 2.0 license. Preserve source
attribution as required by [LICENSE](LICENSE) and the copyright headers in its source files.
