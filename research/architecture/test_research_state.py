import json
import subprocess
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).parent


class ResearchStateTest(unittest.TestCase):
    def test_query_corpus_is_large_unique_and_well_formed(self):
        corpus = json.loads((HERE / "query_corpus.json").read_text())
        queries = corpus["queries"]
        self.assertGreaterEqual(len(queries), 30)
        ids = [row["id"] for row in queries]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row["question"] and row["requires"] for row in queries))
        self.assertGreaterEqual(len({row["category"] for row in queries}), 12)

    def test_current_intent_characterization_is_reproducible(self):
        completed = subprocess.run(
            [sys.executable, str(HERE / "probe_current_intent.py")],
            cwd=HERE.parents[1], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        observations = payload["counterexamples"]
        classes = {row["classification"] for row in observations}
        self.assertIn("silent_substitution", classes)
        self.assertIn("safe_operator_refusal", classes)

    def test_current_paraphrase_planning_instability_is_measured(self):
        completed = subprocess.run(
            [sys.executable, str(HERE / "probe_current_intent.py")],
            cwd=HERE.parents[1], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        paraphrases = json.loads(completed.stdout)["paraphrases"]
        families = {row["family"] for row in paraphrases}
        self.assertEqual(families, {"explain_change", "inspect_level"})

    def test_all_candidates_are_scored_on_same_corpus(self):
        completed = subprocess.run(
            [sys.executable, str(HERE / "compare_candidates.py")],
            cwd=HERE.parents[1], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rows = json.loads(completed.stdout)
        self.assertEqual(len(rows), 5)
        totals = {row["total"] for row in rows}
        self.assertEqual(len(totals), 1)
        total = totals.pop()
        self.assertGreaterEqual(total, 40)
        self.assertTrue(all(0 <= row["represented"] <= total for row in rows))


if __name__ == "__main__":
    unittest.main()
