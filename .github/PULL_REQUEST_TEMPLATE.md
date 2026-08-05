## Claimed saving

<!-- Example: -3 structural units. CI will report the authoritative number. -->

## Claimed heartbeat improvement

<!-- Optional local estimate. CI measures the changed files in both trees. -->

## AST and kernel complexity

<!-- Note expected syntax/kernel changes. Both may stay equal but may not increase. -->

## Proofs changed

<!-- Name the main declarations and files. -->

## The idea

<!-- What mathematical or structural observation makes the proof smaller? -->

## Tradeoffs

<!-- Note elaboration-time, readability, automation, or reuse changes. Write “None known” if none. -->

- [ ] I changed only `Mathlib.lean` or `.lean` files under `Mathlib/`.
- [ ] I did not use `sorry`, `admit`, new axioms, generated source, or precompiled code.
- [ ] I did not encode proof steps in comments, names, literals, generated files, or custom syntax.
- [ ] I did not add or repurpose syntax, macros, tactics, or elaborators.
- [ ] I ran `lake build --wfail Mathlib` and `python3 -m bonsai.scorer .` locally.
