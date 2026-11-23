import unittest

from hallucinated_citation_checker.bibtex import parse_bib


class BibTests(unittest.TestCase):
    def test_braces_quotes_and_nesting(self):
        es = parse_bib('''@article{a1,
  title = {Learning {AI} with {B}ib{T}e{X}},
  author = "Doe, Jane and Roe, Rich",
  year = 2020,
}''')
        self.assertEqual(len(es), 1)
        f = es[0].fields
        self.assertEqual(f["title"], "Learning AI with BibTeX")
        self.assertEqual(f["author"], "Doe, Jane and Roe, Rich")
        self.assertEqual(f["year"], "2020")

    def test_string_macros_and_concatenation(self):
        es = parse_bib('''@string{jx = "Journal of Examples"}
@string{pub = {Example Press}}
@book{b1, title = {T}, journal = jx, publisher = pub # " Ltd", year = {1999}}''')
        self.assertEqual(es[0].fields["journal"], "Journal of Examples")
        self.assertEqual(es[0].fields["publisher"], "Example Press Ltd")

    def test_comment_preamble_skipped_and_paren_delims(self):
        es = parse_bib('''@comment{@article{ghost, title={no}}}
@preamble{"\\\\newcommand{\\\\x}{y}"}
@misc(m1, title = {Paren entry}, year = {2001})
@article{a2, title={Second}}''')
        self.assertEqual([e.key for e in es], ["m1", "a2"])

    def test_escapes_and_accents(self):
        es = parse_bib(r'@article{e, title={Caf\'e \& Na\"{i}ve ratios}, doi={10.1/a\_b}}')
        self.assertEqual(es[0].fields["title"], "Cafe & Naive ratios")
        self.assertEqual(es[0].fields["doi"], "10.1/a_b")

    def test_quote_with_braced_quote_and_multiline(self):
        es = parse_bib('@article{q, title = "A {\\"o} b\n   c", year="2010"}')
        self.assertEqual(es[0].fields["year"], "2010")
        self.assertIn("b c", es[0].fields["title"])

    def test_first_duplicate_field_wins_and_types_lowercase(self):
        es = parse_bib("@ARTICLE{k, year={1}, year={2}}")
        self.assertEqual(es[0].type, "article")
        self.assertEqual(es[0].fields["year"], "1")

    def test_unterminated_entry_does_not_hang(self):
        es = parse_bib("@article{k, title={open")
        self.assertEqual(es[0].key, "k")


if __name__ == "__main__":
    unittest.main()
