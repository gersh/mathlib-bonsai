import unittest

from bonsai.update_leaderboard import END, START, update_text


README = f"""# Test

{START}

old

{END}

After.
"""


class LeaderboardTests(unittest.TestCase):
    def test_updates_from_exact_merge_commit(self):
        records = [{
            "number": 4,
            "merged_at": "2026-08-07T01:29:20Z",
            "merge_commit_sha": "abc123",
            "html_url": "https://github.com/gersh/mathlib-bonsai/pull/4",
            "user": {"login": "MrBrain295"},
        }]
        updated = update_text(README, 18_900_584, 18_900_593, records, "abc123")
        self.assertIn("[@MrBrain295](https://github.com/MrBrain295)", updated)
        self.assertIn("| 18,900,584 | 9 |", updated)
        self.assertIn("[#4](https://github.com/gersh/mathlib-bonsai/pull/4)", updated)

    def test_non_pr_push_is_unchanged(self):
        self.assertEqual(update_text(README, 9, 10, [], "abc123"), README)

    def test_rejects_unsafe_login(self):
        records = [{
            "number": 4,
            "merged_at": "2026-08-07T01:29:20Z",
            "merge_commit_sha": "abc123",
            "html_url": "https://github.com/gersh/mathlib-bonsai/pull/4",
            "user": {"login": "bad|login"},
        }]
        with self.assertRaisesRegex(ValueError, "author login"):
            update_text(README, 9, 10, records, "abc123")


if __name__ == "__main__":
    unittest.main()
