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

The split workflow matters: candidate Lean code is untrusted native code. It never runs in a job
holding a write token or repository secrets. The reporter runs only after the verifier and consumes
the verifier's Markdown artifact; it never checks out or executes candidate code.
