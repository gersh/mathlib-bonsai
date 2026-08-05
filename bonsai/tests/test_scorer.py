from pathlib import Path
import tempfile
import unittest

from bonsai.scorer import ScoreError, count_symbols, score_repository
from bonsai.check_policy import allowed


class CountSymbolsTests(unittest.TestCase):
    def test_layout_is_free(self) -> None:
        self.assertEqual(count_symbols(" theorem  x : True := by\n  trivial\n"), 24)

    def test_line_and_nested_comments_are_free(self) -> None:
        self.assertEqual(count_symbols("a-- hello\nb/- outer /- inner -/ end -/c"), 3)

    def test_doc_comments_are_free(self) -> None:
        self.assertEqual(count_symbols("/-- docs -/theorem/-! more -/x"), len("theoremx"))

    def test_comment_markers_in_literals_are_charged(self) -> None:
        source = '"-- /-" r#"/- --"# \'-\' «x--y»'
        self.assertEqual(
            count_symbols(source),
            len('"-- /-"') + len('r#"/- --"#') + len("'-'") + len("«x--y»"),
        )

    def test_unicode_scalar_not_utf8_byte(self) -> None:
        self.assertEqual(count_symbols("∀ α, α → α"), 6)

    def test_unterminated_constructs_fail(self) -> None:
        for source in ("/- no", '"no', "r##\"no", "«no"):
            with self.subTest(source=source), self.assertRaises(ScoreError):
                count_symbols(source)

    def test_combining_scalar_is_independently_charged(self) -> None:
        self.assertEqual(count_symbols("e\N{COMBINING ACUTE ACCENT}"), 2)


class RepositoryTests(unittest.TestCase):
    def test_repository_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Mathlib").mkdir()
            (root / "Mathlib.lean").write_text("import Mathlib.X\n", encoding="utf-8")
            (root / "Mathlib" / "X.lean").write_text("theorem x:True:=by trivial\n")
            result = score_repository(root)
            self.assertEqual(result["total"], len("importMathlib.Xtheoremx:True:=bytrivial"))


class PolicyTests(unittest.TestCase):
    def test_only_mathlib_lean_source_is_allowed(self) -> None:
        for path in ("Mathlib.lean", "Mathlib/X.lean", "Mathlib/A/B.lean"):
            self.assertTrue(allowed(path), path)
        for path in ("lakefile.lean", "bonsai/scorer.py", "Mathlib/X.md", "Archive/X.lean"):
            self.assertFalse(allowed(path), path)


if __name__ == "__main__":
    unittest.main()
