import csv
import io
import json
import os
import tempfile
import unittest

from hallucinated_citation_checker import cli
from tests.fakes import ARXIV_OK, crossref_item, make_http

BIB = """@article{good, title={A Synthetic Study of Widgets}, year={2020}, doi={10.1234/good}}
@article{ghost, title={Nothing Like This Exists Anywhere}, year={2020}}
"""


def routes(down=False):
    if down:
        return [("crossref.org", (503, "")), ("doi.org", (503, "")), ("openalex.org", (503, ""))]
    return [("crossref.org/works/10.1234/good",
             (200, {"message": crossref_item("A Synthetic Study of Widgets", [("Ada", "Example")], 2020)})),
            ("crossref.org/works?", (200, {"message": {"items": []}})),
            ("openalex.org", (200, {"results": []}))]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bib = os.path.join(self.tmp.name, "refs.bib")
        self.out = os.path.join(self.tmp.name, "out.csv")
        with open(self.bib, "w") as f:
            f.write(BIB)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, rts, *extra):
        http, net, _ = make_http(rts, retries=2)
        args = cli.build_parser().parse_args([self.bib, "-o", self.out, *extra])
        buf = io.StringIO()
        code = cli.run(args, http=http, out=buf, err=io.StringIO())
        return code, buf.getvalue(), net

    def rows(self):
        with open(self.out, newline="") as f:
            return {r["key"]: r for r in csv.DictReader(f)}

    def test_csv_and_exit_code(self):
        code, text, _ = self.run_cli(routes())
        rows = self.rows()
        self.assertEqual(rows["good"]["verdict"], "VERIFIED")
        self.assertEqual(rows["ghost"]["verdict"], "NOT_FOUND")
        self.assertIn("NOT proof of fabrication", rows["ghost"]["note"])
        self.assertEqual(code, 1)
        self.assertIn("manual review", text)

    def test_json_output(self):
        _, text, _ = self.run_cli(routes(), "--json")
        d = json.loads(text)
        self.assertEqual(d["summary"], {"VERIFIED": 1, "NOT_FOUND": 1})
        self.assertEqual(len(d["results"]), 2)

    def test_resume_skips_done_and_retries_errors(self):
        code, _, _ = self.run_cli(routes(down=True))
        self.assertEqual({r["verdict"] for r in self.rows().values()}, {"ERROR"})
        self.run_cli(routes())  # without --resume: starts over
        _, _, net = self.run_cli(routes(), "--resume")
        self.assertEqual(net.calls, [])  # everything already verified or not found
        # simulate a crashed run: keep only the first row and an ERROR row
        rows = self.rows()
        rows["ghost"]["verdict"] = "ERROR"
        cli.write_csv(self.out, list(rows.values()))
        _, _, net = self.run_cli(routes(), "--resume")
        self.assertTrue(net.calls)
        self.assertFalse(any("good" in u for u, _ in net.calls))
        self.assertEqual(self.rows()["ghost"]["verdict"], "NOT_FOUND")
        with open(self.out) as f:
            self.assertEqual(len(list(csv.DictReader(f))), 2)  # one row per key

    def test_all_verified_exit_zero(self):
        with open(self.bib, "w") as f:
            f.write(BIB.split("\n")[0] + "\n")
        self.assertEqual(self.run_cli(routes())[0], 0)

    def test_usage_errors(self):
        args = cli.build_parser().parse_args([self.bib, "--sources", "bogus"])
        self.assertEqual(cli.run(args, err=io.StringIO()), 2)
        args = cli.build_parser().parse_args(["/nonexistent/x.bib"])
        self.assertEqual(cli.run(args, err=io.StringIO()), 2)


if __name__ == "__main__":
    unittest.main()
