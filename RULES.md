# Competition rules

These rules are the human contract. The scripts in `bonsai/` and the workflows in `.github/workflows/`
are the executable contract. When they disagree, maintainers pause the PR and repair the checker;
passing CI never makes an exploit eligible.

## 1. Objective

Minimize the official score while preserving exactly the public theorem surface exposed by
`import Mathlib`. The default branch is the current record. A PR must reduce its base branch by at
least one structural source unit. Renaming or whitespace minification alone cannot improve a score.

The baseline toolchain, `lake-manifest.json`, package configuration, scorer, surface exporter, and
workflows are protected. A normal entry may change only `Mathlib.lean` and `.lean` files under
`Mathlib/`.

## 2. Official score

The scored set is every regular file matching:

```text
Mathlib.lean
Mathlib/**/*.lean
```

The scorer reads strict UTF-8 with LF line endings, removes comments and layout, and counts
structural source units. Each identifier or keyword, operator token, delimiter, and literal costs
one unit regardless of spelling length. The ignored forms are:

- line comments beginning with `--` and ending at LF;
- nested block comments beginning with `/-` and ending with the matching `-/`, including `/--` and
  `/-!` documentation forms;
- whitespace outside a string, character literal, raw string, or `«quoted identifier»`.

For example, `by exact rfl` costs three units while `rfl` costs one. `x` and
`aVeryLongLocalName` each cost one, so shortening a local name does nothing. Qualified names retain
their structure: `Mathlib.Data.List` costs five units.

The scorer also fingerprints the exact spelling of every string, character, raw-string, and numeric
literal. The candidate inventory must be a sub-multiset of the baseline inventory: literals may be
retained or deleted, but an entry cannot introduce or alter one. Literal payload scalars must also
not increase. These are integrity guards, not secondary leaderboards; they prevent replacing proof
structure with data that a macro could decode. Non-layout, non-comment source scalars are reported
only as a diagnostic and never break ties.

Identifiers and quoted identifiers are limited to 256 scalars and operator tokens to 32. Files must
be strict UTF-8 regular files with LF endings; symbolic links are rejected. These generous limits
are above the Season 1 baseline and prevent a single token from becoming an unbounded data channel.

This is a deterministic contest lexer rather than Lean's extensible lexer. Outside protected
literals, every `--` and `/-` begins a comment; delimiters are singleton units and a contiguous
operator is one unit. The versioned implementation in `bonsai/scorer.py` is authoritative.

Why units? They reward deleting proof steps, applications, binders, and repeated terms without
rewarding one-letter names. Why ignore layout? Formatting and explanations should remain readable
without affecting a result. Why not count parsed syntax or kernel expressions? Both are affected by
extensible macros and elaboration internals, making the season harder to reproduce and audit.

### Elaboration-heartbeat requirement

An entry must improve two axes: structural units and Lean elaboration heartbeats. CI takes the union
of changed Lean source paths and elaborates each file sequentially in both the baseline and candidate
with `Elab.async` disabled. It sums Lean's internal allocation-based heartbeat counter. The
candidate must reduce that affected-file total by more than one user-facing heartbeat (1,000
internal heartbeats) per measured file; this allowance prevents tiny process-level variation from
deciding a result.

Heartbeats are a merge guard and reported delta, not a second global leaderboard score. Measuring
only affected files keeps PR verification tractable and makes the comparison relevant to the entry.
It also makes compressed macro decoding, much heavier automation, and other source-shortening
slowdowns lose mechanically. The toolchain, file set, async setting, and measurement script are
fixed by the base branch.

## 3. Required compatibility

CI builds `Mathlib` with warnings as errors, imports the root module, and extracts each public
Mathlib theorem from Lean's environment. Baseline and candidate must have the same:

- theorem declaration names;
- universe-parameter arities;
- binder names and binder information (explicit, implicit, strict implicit, or instance implicit);
- fully elaborated theorem types, compared using a 256-bit structural fingerprint after universe
  parameters are canonically numbered and non-semantic expression metadata is erased;
- public axiom declarations originating in Mathlib.

Private names and names Lean marks as generated implementation details (for example `_proof_1`,
`match_2`, or `_sizeOf_3`) are excluded. These auxiliaries are deliberately unstable when proof
bodies change and are not a supported theorem surface.

The theorem proof value is not compared. Definitions, tactics, notation, attributes, instances,
documentation, runtime performance, and non-theorem declarations are outside the formal surface
check except where they are needed to build and state the preserved theorems.

## 4. Soundness

Entries may not use `sorry`, `admit`, `sorryAx`, a new axiom, an unsound foreign function, a
precompiled object, generated unscored source, or any equivalent escape hatch. The surface exporter
checks the transitive axiom dependencies of public theorems and permits only Lean's foundational
`propext`, `Quot.sound`, and `Classical.choice`. CI also builds with warnings as errors.

The dependency lockfile and toolchain are fixed. Network access, environment-dependent elaboration,
reading untracked files, or code generation that changes the built theorem library is forbidden.

Comments, identifier spellings, literal payload, environment variables, and file names may not be
used as encoded proof programs. New syntax, macros, or tactics whose purpose is to pack many proof
operations into an undercounted token are likewise ineligible. The checker uses token limits,
literal-inventory monotonicity, a strict heartbeat improvement, a fixed dependency graph, isolated
trusted comparison, and human review as defense in depth; passing automation does not legalize an
evasion of these rules. Resetting or forging Lean's heartbeat counter is itself an evasion.

## 5. Pull requests

An entry should state:

- its claimed structural-unit saving;
- its affected-file heartbeat saving;
- the files and main theorems affected;
- the idea behind the shorter proof;
- any meaningful tradeoff in readability, elaboration time, or reuse.

CI compares against the PR's base commit, so accepted entries compose. If another entry lands first,
rebase and let the score run again. Maintainers may decline mechanically hostile obfuscation, severe
performance regressions, licensing problems, or techniques that violate the intent above.

## 6. Ties and records

Only strict improvements merge, so the default branch is always the global record. Git history is
the chronological leaderboard. For two competing PRs with the same idea, maintainers normally take
the first clean, reviewable submission; independent or meaningfully different proofs may both be
recorded in discussion even if only one can lower the branch.

## 7. Changing the rules

Rule and checker changes are maintainer PRs and never contest entries. They require CODEOWNER review.
A checker fix may invalidate an open result, but accepted commits are not silently rewritten. A new
Mathlib or Lean baseline starts a named season so scores from different public surfaces are never
presented as directly comparable.
