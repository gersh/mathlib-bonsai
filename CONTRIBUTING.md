# Contributing an entry

Thank you for helping search for smaller proofs. Start from the current `main`; old scores become
stale as soon as another entry lands.

```bash
git switch -c pruning/short-description
lake exe cache get

# edit Mathlib source, then:
lake build --wfail Mathlib
python3 -m bonsai.scorer .
python3 -m unittest discover -s bonsai/tests -v
```

Push the branch to your fork, enable GitHub Actions there if prompted, and run the **Submission
proof** workflow with your branch selected. It compares your commit with the reigning
`gersh/mathlib-bonsai:main`, uploads the complete result, and must pass before submission. The PR
workflow repeats the proof independently as the authoritative merge gate.
For a contributor's first PR, GitHub may ask a maintainer to approve the read-only central workflow
run. This approval starts verification; it is not approval of the code or of the eventual merge.

Only `Mathlib.lean` and `.lean` files under `Mathlib/` may change in an entry. This is both a security
boundary and what prevents moving implementation into an unscored script or dependency. If the
competition infrastructure needs a fix, open a separate issue or maintainer PR.

Use the pull-request template. Keep formatting and explanatory comments good—they are free. A short
proof that needs an explanation should get one. The source score ignores comments because the
project wants compressed formal arguments, not compressed communication. Identifier shortening is
also score-neutral: look for proof steps, applications, binders, and duplicated terms to remove.

GitHub Actions performs the authoritative comparison against the PR base. Locally, the scorer gives
the exact total, while the full surface check runs in the fork-side preflight and central PR CI.
Read [RULES.md](RULES.md) for the complete eligibility contract.

CI also re-elaborates every changed Lean file in the baseline and candidate with async elaboration
disabled. A winning entry must reduce that affected-file heartbeat total by more than the documented
one-heartbeat-per-file noise allowance. This is deliberately a Pareto competition: shorter source
that makes elaboration slower does not merge.

CI also counts raw parsed syntax nodes (excluding documentation comments) and elaborated kernel
expression nodes for the affected files. Neither count may increase. This permits cleanups that
elaborate to the same proof term while rejecting source compression that merely expands into more
syntax or kernel work. New or repurposed syntax, macros, tactics, and elaborators are not contest
entries; propose them separately for maintainer review.

## Concurrent entries and conflicts

Start from current `main` and keep the branch current. Maintainers review entries in the order they
first become both centrally eligible and review-ready. An approved PR may use GitHub auto-merge, but
it remains merge-ready only while it updates cleanly and still beats the reigning score. If an
earlier entry lands and your branch conflicts or no longer improves the score, revise it and rerun
Submission proof; the revised entry rejoins the back of the ready line. There is no repair window
that blocks later contributors.

For overlapping ideas, link the other PR and explain what is independent. GitHub discussion keeps
the attribution even when only one version can be the next strict record. Maintainers should not
resolve a contributor's substantive proof conflict by copying work from another queued entry.

## Possible upstream contribution

If a win is clear, reusable, and consistent with Mathlib style, the author and maintainers may
propose it to `leanprover-community/mathlib4`. Credit the Bonsai author and link the competition PR.
Upstream Mathlib decides independently whether the change belongs there.

## Maintainer setup

After pushing this repository to GitHub:

1. Make `main` the default branch.
2. Protect `main`; require the `Mathlib Bonsai / verify` check, one approving review, conversation
   resolution, and branches to be up to date.
3. Require CODEOWNER review and disallow force pushes/deletions.
4. Give Actions read access by default. The competition workflow itself is read-only; the separate
   trusted reporter receives only `actions: read` and `pull-requests: write`.
5. The reporter creates and maintains the `bonsai:eligible` and `bonsai:invalid` labels. Add an
   `infrastructure` label for non-entry work.
6. Enable native auto-merge and the update-branch button. Use auto-merge only after maintainer
   approval; branch-up-to-date protection prevents merging until the updated tree is verified.

The split workflow matters: candidate Lean code is untrusted native code. It never runs in a job
holding a write token or repository secrets. The reporter runs only after the verifier and consumes
the verifier's Markdown artifact; it never checks out or executes candidate code.
