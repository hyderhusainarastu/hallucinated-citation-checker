import unittest

from hallucinated_citation_checker.bibtex import Entry
from hallucinated_citation_checker.checker import (ERROR, MISMATCH, NOT_FOUND, SKIPPED, VERIFIED,
                                                   Checker, Config, arxiv_of, isbn_of)
from hallucinated_citation_checker.sources import Sources
from tests.fakes import ARXIV_EMPTY, ARXIV_ERR, ARXIV_OK, crossref_item, make_http

WIDGETS = "A Synthetic Study of Widgets"
AUTH = [("Ada", "Example"), ("Ben", "Sample")]


def entry(key="k", etype="article", **f):
    return Entry(key, etype, f)


def checker(routes, cfg=None, enabled=("crossref", "openalex", "arxiv", "openlibrary", "doi")):
    http, net, _ = make_http(routes, retries=2)
    return Checker(Sources(http, enabled), cfg), net


def cr_work(title=WIDGETS, year=2020, authors=AUTH):
    return (200, {"message": crossref_item(title, authors, year)})


class DoiRung(unittest.TestCase):
    def test_verified(self):
        c, _ = checker([("crossref.org/works/10.1234", cr_work())])
        r = c.check(entry(title=WIDGETS, author="Example, Ada and Sample, Ben", year="2020", doi="10.1234/x"))
        self.assertEqual((r.verdict, r.rung, r.source), (VERIFIED, "doi", "crossref"))

    def test_year_tolerance_edge(self):
        c, _ = checker([("crossref.org/works/", cr_work(year=2021))])
        e = dict(title=WIDGETS, year="2020", doi="10.1234/x")
        self.assertEqual(c.check(entry(**e)).verdict, VERIFIED)  # +1 allowed
        c2, _ = checker([("crossref.org/works/", cr_work(year=2022))])
        r = c2.check(entry(**e))
        self.assertEqual(r.verdict, MISMATCH)
        self.assertIn("year: bib=2020 vs crossref=2022", r.detail)

    def test_title_threshold_edge(self):
        c, _ = checker([("crossref.org/works/", cr_work(title="a b c e"))])
        e = dict(title="a b c d", doi="10.1234/x")
        self.assertEqual(c.check(entry(**e)).verdict, MISMATCH)  # 0.75 < 0.80
        c2, _ = checker([("crossref.org/works/", cr_work(title="a b c e"))], Config(title_threshold=0.75))
        self.assertEqual(c2.check(entry(**e)).verdict, VERIFIED)

    def test_author_mismatch_shows_diff(self):
        c, _ = checker([("crossref.org/works/", cr_work())])
        r = c.check(entry(title=WIDGETS, author="Nobody, Nina", doi="10.1234/x"))
        self.assertEqual(r.verdict, MISMATCH)
        self.assertIn("authors:", r.detail)

    def test_falls_back_to_doi_org(self):
        csl = {"DOI": "10.1234/x", "title": WIDGETS, "issued": {"date-parts": [[2020]]},
               "author": [{"given": "Ada", "family": "Example"}]}
        c, net = checker([("crossref.org/works/10.1234", (404, "")), ("doi.org/10.1234", (200, csl))])
        r = c.check(entry(title=WIDGETS, year="2020", doi="10.1234/x"))
        self.assertEqual((r.verdict, r.source), (VERIFIED, "doi"))
        accept = [h for u, h in net.calls if "doi.org/10" in u][0]["Accept"]
        self.assertIn("csl+json", accept)

    def test_wrong_doi_but_title_found_by_search_is_mismatch(self):
        c, _ = checker([("crossref.org/works/10.", (404, "")), ("doi.org/10.", (404, "")),
                        ("crossref.org/works?", (200, {"message": {"items": [crossref_item(WIDGETS, AUTH, 2020)]}}))])
        r = c.check(entry(title=WIDGETS, year="2020", author="Example, Ada", doi="10.9999/typo"))
        self.assertEqual((r.verdict, r.rung), (MISMATCH, "search"))
        self.assertIn("did not resolve", r.detail)


class ArxivRung(unittest.TestCase):
    def test_verified_and_id_forms(self):
        c, _ = checker([("export.arxiv.org", (200, ARXIV_OK))])
        r = c.check(entry("a", "misc", title=WIDGETS, year="2020", eprint="2001.00001"))
        self.assertEqual((r.verdict, r.rung), (VERIFIED, "arxiv"))
        self.assertEqual(arxiv_of({"doi": "10.48550/arXiv.2001.00001"}), "2001.00001")
        self.assertEqual(arxiv_of({"url": "https://arxiv.org/abs/2001.00001v2"}), "2001.00001")
        self.assertEqual(arxiv_of({"eprint": "arXiv:2001.00001"}), "2001.00001")

    def test_arxiv_doi_skips_doi_rung(self):
        c, net = checker([("export.arxiv.org", (200, ARXIV_OK))])
        c.check(entry(title=WIDGETS, doi="10.48550/arXiv.2001.00001"))
        self.assertFalse(any("crossref" in u for u, _ in net.calls))

    def test_mismatch_wrong_year(self):
        c, _ = checker([("export.arxiv.org", (200, ARXIV_OK))])
        r = c.check(entry(title=WIDGETS, year="2015", eprint="2001.00001"))
        self.assertEqual(r.verdict, MISMATCH)

    def test_unknown_id_then_nothing_found(self):
        for body in (ARXIV_EMPTY, ARXIV_ERR):
            c, _ = checker([("export.arxiv.org", (200, body))])
            self.assertEqual(c.check(entry(eprint="2001.99999")).verdict, NOT_FOUND)


class IsbnRung(unittest.TestCase):
    OL = {"ISBN:9780000000002": {"title": "A Synthetic Study of Widgets",
                                 "authors": [{"name": "Ada Example"}], "publish_date": "March 2020"}}

    def test_verified(self):
        c, _ = checker([("openlibrary.org", (200, self.OL))])
        r = c.check(entry(etype="book", title=WIDGETS, author="Example, Ada", year="2020", isbn="978-0-00-000000-2"))
        self.assertEqual((r.verdict, r.rung, r.source), (VERIFIED, "isbn", "openlibrary"))

    def test_empty_object_is_not_found(self):
        c, _ = checker([("openlibrary.org", (200, {}))])
        self.assertEqual(c.check(entry(isbn="9780000000002")).verdict, NOT_FOUND)

    def test_isbn_parsing(self):
        self.assertEqual(isbn_of({"isbn": "978-0-262-03561-3"}), "9780262035613")
        self.assertEqual(isbn_of({"isbn": "0 262 03384 X"}), "026203384X")


class SearchRung(unittest.TestCase):
    def test_openalex_verified(self):
        oa = {"results": [{"id": "W1", "title": WIDGETS, "publication_year": 2020,
                           "authorships": [{"author": {"display_name": "Ada Example"}}]}]}
        c, _ = checker([("crossref.org", (200, {"message": {"items": []}})), ("openalex.org", (200, oa))])
        r = c.check(entry(title=WIDGETS, author="Example, Ada", year="2020"))
        self.assertEqual((r.verdict, r.source), (VERIFIED, "openalex"))

    def test_unrelated_hits_are_not_found_with_review_note(self):
        other = crossref_item("Completely Different Topic Entirely", AUTH, 2020)
        c, _ = checker([("crossref.org", (200, {"message": {"items": [other]}})),
                        ("openalex.org", (200, {"results": []}))])
        r = c.check(entry(title=WIDGETS, year="2020"))
        self.assertEqual(r.verdict, NOT_FOUND)
        self.assertIn("NOT proof of fabrication", r.note)

    def test_mismatch_year_via_search(self):
        item = crossref_item(WIDGETS, AUTH, 2010)
        c, _ = checker([("crossref.org", (200, {"message": {"items": [item]}})),
                        ("openalex.org", (200, {"results": []}))])
        self.assertEqual(c.check(entry(title=WIDGETS, year="2020")).verdict, MISMATCH)


class ErrorsAndSkips(unittest.TestCase):
    def test_503_is_error_never_not_found(self):
        c, net = checker([("crossref.org", (503, "")), ("openalex.org", (503, "")), ("doi.org", (503, ""))])
        r = c.check(entry(title=WIDGETS, doi="10.1234/x"))
        self.assertEqual(r.verdict, ERROR)
        self.assertGreaterEqual(len(net.calls), 2 * 2)  # retried

    def test_identifier_outage_then_good_search_is_not_a_mismatch(self):
        items = {"message": {"items": [crossref_item(WIDGETS, AUTH, 2020)]}}
        c, _ = checker([("crossref.org/works/10.", (503, "")), ("doi.org/10.", (503, "")),
                        ("crossref.org/works?", (200, items))])
        r = c.check(entry(title=WIDGETS, year="2020", author="Example, Ada", doi="10.1234/x"))
        self.assertEqual(r.verdict, VERIFIED)
        self.assertNotIn("did not resolve", r.detail)

    def test_identifier_outage_and_no_search_hit_is_error(self):
        c, _ = checker([("crossref.org/works/10.", (503, "")), ("doi.org/10.", (503, "")),
                        ("crossref.org/works?", (200, {"message": {"items": []}})),
                        ("openalex.org", (200, {"results": []}))])
        r = c.check(entry(title=WIDGETS, year="2020", doi="10.1234/x"))
        self.assertEqual(r.verdict, ERROR)

    def test_one_source_down_other_verifies(self):
        oa = {"results": [{"id": "W1", "title": WIDGETS, "publication_year": 2020, "authorships": []}]}
        c, _ = checker([("crossref.org", (503, "")), ("openalex.org", (200, oa))])
        self.assertEqual(c.check(entry(title=WIDGETS, year="2020")).verdict, VERIFIED)

    def test_skip_type_and_empty_entry(self):
        c, net = checker([], Config(skip_types=frozenset({"misc"})))
        self.assertEqual(c.check(entry(etype="misc", title="x")).verdict, SKIPPED)
        self.assertEqual(c.check(entry(note="n")).verdict, SKIPPED)
        self.assertEqual(net.calls, [])

    def test_sources_filter(self):
        c, net = checker([("openalex.org", (200, {"results": []}))], enabled=("openalex",))
        self.assertEqual(c.check(entry(title=WIDGETS, doi="10.1/x")).verdict, NOT_FOUND)
        self.assertTrue(all("openalex" in u for u, _ in net.calls))


if __name__ == "__main__":
    unittest.main()
