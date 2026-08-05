import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bonsai.scorer import ScoreError, count_units, measure_source, score_repository
from bonsai.check_policy import allowed


class StructuralUnitTests(unittest.TestCase):
    def test_layout_is_free(self) -> None:
        self.assertEqual(count_units(" theorem  x : True := by\n  trivial\n"), 7)

    def test_line_nested_and_doc_comments_are_free(self) -> None:
        plain = "theorem x : True := by trivial"
        decorated = "/-- docs -/ theorem /- outer /- inner -/ end -/ x : True := by -- why\n trivial"
        self.assertEqual(count_units(plain), count_units(decorated))

    def test_identifier_spelling_does_not_change_score(self) -> None:
        self.assertEqual(count_units("fun x => x"), count_units("fun aVeryLongLocalName => aVeryLongLocalName"))
        self.assertEqual(count_units("fun x => x"), count_units("fun ξ => ξ"))

    def test_redundant_proof_commands_cost_units(self) -> None:
        self.assertEqual(count_units("by exact rfl") - count_units("rfl"), 2)

    def test_qualified_names_retain_structure(self) -> None:
        self.assertEqual(count_units("Mathlib.Data.List"), 5)

    def test_operators_are_tokens_not_character_minification(self) -> None:
        self.assertEqual(count_units("x := y"), count_units("x ⟷ y"))

    def test_literal_payload_is_tracked(self) -> None:
        score = measure_source('"-- /-" r#"/- --"# \'-\' 12345')
        self.assertEqual(score.units, 4)
        self.assertEqual(score.literal_payload, len("-- /-") + len("/- --") + 2 + 1 + 5)

    def test_comment_text_cannot_disguise_literal_payload(self) -> None:
        self.assertGreater(measure_source('r#"/- encoded --"#').literal_payload, 0)
        self.assertEqual(measure_source('/- encoded -- -/').literal_payload, 0)

    def test_unterminated_constructs_fail(self) -> None:
        for source in ("/- no", '"no', 'r##"no', "«no"):
            with self.subTest(source=source), self.assertRaises(ScoreError):
                count_units(source)

    def test_oversized_identifier_and_operator_fail(self) -> None:
        for source in ("x" * 257, "+" * 33, "«" + "x" * 257 + "»"):
            with self.subTest(length=len(source)), self.assertRaises(ScoreError):
                count_units(source)


class RepositoryTests(unittest.TestCase):
    def test_repository_total_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Mathlib").mkdir()
            (root / "Mathlib.lean").write_text("import Mathlib.X\n", encoding="utf-8")
            (root / "Mathlib" / "X.lean").write_text(
                'theorem longName : True := by exact trivial\n#check "payload"\n',
                encoding="utf-8",
            )
            result = score_repository(root)
            self.assertEqual(result["schema"], 2)
            self.assertEqual(result["metric"], "lean-structural-source-units-v1")
            self.assertEqual(result["total"], 15)
            self.assertEqual(result["literalPayload"], 7)

    def test_symlink_in_scored_tree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Mathlib").mkdir()
            target = root / "real.lean"
            target.write_text("theorem x : True := trivial\n", encoding="utf-8")
            (root / "Mathlib.lean").symlink_to(target)
            with self.assertRaises(ScoreError):
                score_repository(root)


class PolicyTests(unittest.TestCase):
    def test_only_mathlib_lean_source_is_allowed(self) -> None:
        for path in ("Mathlib.lean", "Mathlib/X.lean", "Mathlib/A/B.lean"):
            self.assertTrue(allowed(path), path)
        for path in (
            "lakefile.lean",
            "lake-manifest.json",
            "lean-toolchain",
            "bonsai/scorer.py",
            ".github/workflows/competition.yml",
            "Mathlib/X.md",
            "Mathlib/../bonsai/hidden.lean",
            "Archive/X.lean",
        ):
            self.assertFalse(allowed(path), path)


class ComparisonTests(unittest.TestCase):
    def _run_comparison(self, directory: Path, candidate_payload: int) -> subprocess.CompletedProcess[str]:
        common = {
            "schema": 2,
            "metric": "lean-structural-source-units-v1",
            "sourceScalars": 100,
            "limits": {"identifierScalars": 256, "operatorScalars": 32},
        }
        (directory / "baseline-score.json").write_text(
            json.dumps(common | {"total": 10, "literalPayload": 5, "files": {"Mathlib.lean": 10}}),
            encoding="utf-8",
        )
        (directory / "candidate-score.json").write_text(
            json.dumps(common | {
                "total": 9,
                "literalPayload": candidate_payload,
                "files": {"Mathlib.lean": 9},
            }),
            encoding="utf-8",
        )
        surface = '\n'.join((
            '{"schema":1,"rootModule":"Mathlib"}',
            '{"kind":"end","forbiddenAxioms":[]}',
            "",
        ))
        for name in ("baseline-surface.jsonl", "candidate-surface.jsonl"):
            (directory / name).write_text(surface, encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "bonsai.compare",
                "baseline-score.json",
                "candidate-score.json",
                "baseline-surface.jsonl",
                "candidate-surface.jsonl",
                "--output",
                "result.json",
            ],
            cwd=directory,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env={"PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        )

    def test_structural_reduction_with_stable_payload_is_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run_comparison(Path(directory), candidate_payload=5)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_literal_packing_is_rejected_despite_smaller_primary_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = self._run_comparison(root, candidate_payload=6)
            self.assertEqual(completed.returncode, 1)
            result = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertFalse(result["accepted"])
            self.assertFalse(result["literalPayloadSafe"])


if __name__ == "__main__":
    unittest.main()
