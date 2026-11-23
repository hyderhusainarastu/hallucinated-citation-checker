import unittest

from hallucinated_citation_checker.http import HttpError
from tests.fakes import make_http


class HttpTests(unittest.TestCase):
    def test_503_retries_then_raises(self):
        http, net, sleeps = make_http([("example.invalid", (503, "down"))], retries=3)
        with self.assertRaises(HttpError):
            http.get("https://example.invalid/x")
        self.assertEqual(len(net.calls), 3)
        self.assertIn(2, sleeps)
        self.assertIn(4, sleeps)

    def test_404_returned_not_retried(self):
        http, net, _ = make_http([("example.invalid", (404, "no"))])
        self.assertEqual(http.get("https://example.invalid/x")[0], 404)
        self.assertEqual(len(net.calls), 1)

    def test_recovers_after_transient_failure(self):
        state = {"n": 0}

        def h(url):
            state["n"] += 1
            return (503, "x") if state["n"] < 2 else (200, "ok")

        http, _, _ = make_http([("example.invalid", h)])
        self.assertEqual(http.get("https://example.invalid/")[1], b"ok")

    def test_user_agent_and_mailto(self):
        http, net, _ = make_http([("example.invalid", (200, "ok"))])
        http.get("https://example.invalid/")
        ua = net.calls[0][1]["User-agent"]
        self.assertTrue(ua.startswith("hallucinated-citation-checker/"))
        self.assertNotIn("mailto", ua)
        http2, net2, _ = make_http([("example.invalid", (200, "ok"))], mailto="you@example.invalid")
        http2.get("https://example.invalid/")
        self.assertIn("mailto:you@example.invalid", net2.calls[0][1]["User-agent"])

    def test_per_host_rate_limit_sleeps(self):
        times = iter([0.0, 0.1, 0.1])
        sleeps = []
        from hallucinated_citation_checker.http import Http
        from tests.fakes import FakeNet
        net = FakeNet([("example.invalid", (200, "ok"))])
        http = Http(rate=1.0, opener=net, sleep=sleeps.append, clock=lambda: next(times))
        http.get("https://example.invalid/a")
        http.get("https://example.invalid/b")
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 0.9)


if __name__ == "__main__":
    unittest.main()
