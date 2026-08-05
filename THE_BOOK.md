# Toward Erdős's Book

Paul Erdős's “Book” was imaginary and perfectly serious: for each theorem, there ought to be a proof
whose central idea is so clean that the proof feels inevitable. Aigner and Ziegler describe their
heroes as perfect proofs—arguments with brilliant ideas, surprising connections, and new insight.
Mathlib Bonsai asks what happens when we pursue that taste at library scale. Like a cultivated
miniature tree, the library should retain its mathematical shape while every proof is carefully
pruned toward a smaller, clearer form.

## Why formal compression might help

A conventional proof has a forgiving boundary. Familiar steps can be left to the reader, notation
can hide context, and two arguments that are “the same” may be written differently. Lean refuses
that ambiguity. Every step must ultimately elaborate to a proof term checked by a small kernel.
That makes formal source unusually measurable.

Now freeze the theorem statements and minimize what remains. The useful reductions tend to have a
mathematical character:

- a special-purpose calculation becomes an instance of a general lemma;
- repeated case analysis becomes the right induction principle;
- a long rewrite chain is replaced by a stronger invariant;
- several proofs reveal a shared abstraction;
- automation becomes effective after the statement is put in its natural form.

Not every reduction is profound. Renaming a local variable saves characters. A lucky tactic may
compress an argument without explaining it. Those are valid golf, but the project becomes valuable
when the leaderboard points reviewers toward a proof worth understanding.

## The score is a probe, not an aesthetic theory

There is no scalar-valued definition of beauty. Source size depends on the language, the existing
library, available automation, and the boundary chosen for the theorem. The smallest proof today may
borrow complexity from a large tactic or lemma. Conversely, a proof that exposes a reusable idea can
initially increase the total before later proofs use it.

For that reason the contest records an exact, reproducible score but asks every PR to explain the
idea. Review should distinguish three things:

1. **Compression:** did the total source become smaller?
2. **Correctness:** did Lean accept the library with the same theorem surface and trusted axioms?
3. **Insight:** what mathematical or structural idea made the reduction possible?

Automation settles the first two. People judge the third.

## The long vision

The default branch is a living approximation to The Book: the same mathematical promises, realized
by progressively smaller proofs. The commit history is part of the artifact. Each accepted PR says
that someone found a more compressed route through a fixed piece of mathematics, and its discussion
records why.

Eventually, the most interesting wins should be curated by theorem rather than only by global score:
before-and-after proof essays, alternative minimal proofs, and explanations of the abstractions that
made large families of theorems collapse. The dream is not a minified Mathlib nobody can read. It is
to use the pressure of minification to discover a Mathlib whose proofs say more with less—and then to
write down what they taught us.

## Further reading

- Martin Aigner and Günter M. Ziegler,
  [*Proofs from THE BOOK*](https://link.springer.com/book/10.1007/978-3-662-04315-8).
- The [Lean reference on modules and public declarations](https://lean-lang.org/doc/reference/latest/Source-Files-and-Modules/).
- The [Mathlib repository](https://github.com/leanprover-community/mathlib4).
