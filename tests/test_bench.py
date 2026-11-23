import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "benchmark"))
import bench  # noqa: E402
import csv  # noqa: E402

from hallucinated_citation_checker.bibtex import parse_bib  # noqa: E402


class BenchTests(unittest.TestCase):
    def test_labels_match_bib_and_are_big_enough(self):
        with open(os.path.join(ROOT, "benchmark", "labels.csv"), newline="") as f:
            labels = list(csv.DictReader(f))
        with open(os.path.join(ROOT, "benchmark", "bench.bib")) as f:
            keys = [e.key for e in parse_bib(f.read())]
        self.assertGreaterEqual(len(labels), 40)
        self.assertEqual(sorted(keys), sorted(r["key"] for r in labels))
        self.assertEqual({r["truth"] for r in labels}, {"real", "corrupted", "invented"})

    def test_confusion(self):
        labels = [{"key": "a", "truth": "real"}, {"key": "b", "truth": "invented"}]
        t = bench.confusion(labels, {"a": {"verdict": "VERIFIED"}, "b": {"verdict": "NOT_FOUND"}})
        self.assertEqual(t["real"]["VERIFIED"], 1)
        self.assertEqual(t["invented"]["NOT_FOUND"], 1)
        self.assertIn("| real | 1 | 1 | 0 |", bench.render(t))


if __name__ == "__main__":
    unittest.main()
