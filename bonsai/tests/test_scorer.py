import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bonsai.scorer import ScoreError, count_units, measure_source, score_repository
from bonsai.check_policy import allowed
from bonsai.compare import compare_surfaces, load_surface
from bonsai.heartbeats import HeartbeatError, measure_repository, validate_relative_path


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
            self.assertEqual(sum(result["literalInventory"].values()), 1)

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
    def _run_comparison(
        self,
        directory: Path,
        candidate_payload: int,
        *,
        candidate_heartbeats: int = 8_000,
        candidate_inventory: dict[str, int] | None = None,
        candidate_syntax_nodes: int = 90,
        candidate_kernel_nodes: int = 100,
    ) -> subprocess.CompletedProcess[str]:
        baseline_inventory = {"0" * 64: 1}
        common = {
            "schema": 2,
            "metric": "lean-structural-source-units-v1",
            "sourceScalars": 100,
            "limits": {"identifierScalars": 256, "operatorScalars": 32},
            "literalInventory": baseline_inventory,
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
                "literalInventory": candidate_inventory or baseline_inventory,
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
        heartbeat_common = {
            "schema": 1,
            "metric": "lean-affected-file-elaboration-heartbeats-v1",
            "async": False,
            "unit": "internal-heartbeats",
        }
        (directory / "baseline-heartbeats.json").write_text(json.dumps(heartbeat_common | {
            "total": 10_000,
            "files": {"Mathlib.lean": 10_000},
        }), encoding="utf-8")
        (directory / "candidate-heartbeats.json").write_text(json.dumps(heartbeat_common | {
            "total": candidate_heartbeats,
            "files": {"Mathlib.lean": candidate_heartbeats},
        }), encoding="utf-8")
        complexity_common = {
            "schema": 1,
            "metric": "lean-affected-file-complexity-v1",
        }
        (directory / "baseline-complexity.json").write_text(json.dumps(complexity_common | {
            "syntaxNodes": 100,
            "kernelExpressionNodes": 100,
            "files": {"Mathlib.lean": {
                "syntaxNodes": 100,
                "kernelExpressionNodes": 100,
            }},
        }), encoding="utf-8")
        (directory / "candidate-complexity.json").write_text(json.dumps(complexity_common | {
            "syntaxNodes": candidate_syntax_nodes,
            "kernelExpressionNodes": candidate_kernel_nodes,
            "files": {"Mathlib.lean": {
                "syntaxNodes": candidate_syntax_nodes,
                "kernelExpressionNodes": candidate_kernel_nodes,
            }},
        }), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "bonsai.compare",
                "baseline-score.json",
                "candidate-score.json",
                "baseline-heartbeats.json",
                "candidate-heartbeats.json",
                "baseline-complexity.json",
                "candidate-complexity.json",
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

    def test_new_literal_is_rejected_even_when_total_payload_falls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = self._run_comparison(
                root,
                candidate_payload=4,
                candidate_inventory={"1" * 64: 1},
            )
            self.assertEqual(completed.returncode, 1)
            result = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertFalse(result["literalInventorySafe"])

    def test_heartbeats_must_decrease_beyond_per_file_tolerance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = self._run_comparison(root, candidate_payload=5, candidate_heartbeats=9_500)
            self.assertEqual(completed.returncode, 1)
            result = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertFalse(result["heartbeatsImproved"])

    def test_syntax_nodes_may_not_increase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = self._run_comparison(root, candidate_payload=5, candidate_syntax_nodes=101)
            self.assertEqual(completed.returncode, 1)
            result = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertFalse(result["syntaxNonincreasing"])

    def test_kernel_expression_nodes_may_not_increase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = self._run_comparison(root, candidate_payload=5, candidate_kernel_nodes=101)
            self.assertEqual(completed.returncode, 1)
            result = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertFalse(result["kernelExpressionNonincreasing"])

    def test_public_non_theorem_implementation_may_not_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prefix = '\n'.join((
                '{"schema":1,"rootModule":"Mathlib"}',
                '{"kind":"implementation","declaration":'
                '{"name":"Mathlib.example","valueFingerprint":["old"]}}',
                '{"kind":"end","forbiddenAxioms":[]}',
                "",
            ))
            changed = prefix.replace('["old"]', '["new"]')
            baseline_path = root / "baseline.jsonl"
            candidate_path = root / "candidate.jsonl"
            baseline_path.write_text(prefix, encoding="utf-8")
            candidate_path.write_text(changed, encoding="utf-8")
            result = compare_surfaces(
                load_surface(baseline_path), load_surface(candidate_path),
                baseline_path, candidate_path,
            )
            self.assertFalse(result["compatible"])
            self.assertTrue(result["implementationsChanged"])


class HeartbeatTests(unittest.TestCase):
    def test_paths_cannot_escape_scored_tree(self) -> None:
        self.assertEqual(validate_relative_path("Mathlib/X.lean"), Path("Mathlib/X.lean"))
        for path in ("../X.lean", "/Mathlib/X.lean", "Mathlib/../X.lean", "Archive/X.lean"):
            with self.subTest(path=path), self.assertRaises(HeartbeatError):
                validate_relative_path(path)

    def test_no_files_is_rejected(self) -> None:
        with self.assertRaises(HeartbeatError):
            measure_repository(Path.cwd(), [])


if __name__ == "__main__":
    unittest.main()
