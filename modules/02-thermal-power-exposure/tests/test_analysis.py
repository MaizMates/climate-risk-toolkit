import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from analysis import load_rows, results, score

class TestExposure(unittest.TestCase):
    def test_rows_are_ranked_and_scored(self):
        out = results(load_rows())
        self.assertEqual(len(out), 5)
        self.assertGreaterEqual(out[0]["screening_score"], out[-1]["screening_score"])

    def test_cooling_weight_is_applied(self):
        row = {"capacity_mw":"100", "annual_hot_days":"10", "cooling_type":"once_through"}
        self.assertEqual(score(row), 1400.0)

if __name__ == "__main__":
    unittest.main()
