import unittest

from hallucinated_citation_checker.similarity import (author_overlap, bib_surnames,
                                                      record_surnames, title_similarity, year_of)


class SimTests(unittest.TestCase):
    def test_title_similarity(self):
        self.assertEqual(title_similarity("Deep  Learning!", "deep learning"), 1.0)
        self.assertEqual(title_similarity("", "x"), 0.0)
        self.assertAlmostEqual(title_similarity("a b c d", "a b c e"), 0.75)
        self.assertEqual(title_similarity("Café société", "Cafe societe"), 1.0)

    def test_surnames(self):
        self.assertEqual(bib_surnames("Doe, Jane and John Roe and others"), ["doe", "roe"])
        self.assertEqual(record_surnames(["Ada B. Lovelace"]), ["lovelace"])

    def test_overlap(self):
        self.assertIsNone(author_overlap([], ["a"]))
        self.assertEqual(author_overlap(["doe", "roe"], ["doe"]), 0.5)
        self.assertEqual(author_overlap(["van der berg"], ["berg"]), 1.0)

    def test_year(self):
        self.assertEqual(year_of("circa 1999"), 1999)
        self.assertIsNone(year_of("n.d."))


if __name__ == "__main__":
    unittest.main()
