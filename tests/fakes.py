"""Offline stand-ins for urllib: routes URLs to hand-written synthetic payloads."""

import io
import json
import urllib.error

from hallucinated_citation_checker.http import Http


class FakeResp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeNet:
    """routes: list of (url_substring, handler). handler is (status, body) or a callable(url)."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.calls.append((url, dict(req.header_items())))
        for sub, h in self.routes:
            if sub in url:
                status, body = h(url) if callable(h) else h
                if isinstance(body, (dict, list)):
                    body = json.dumps(body).encode()
                elif isinstance(body, str):
                    body = body.encode()
                if status >= 400:
                    raise urllib.error.HTTPError(url, status, "err", {}, io.BytesIO(body))
                return FakeResp(status, body)
        raise urllib.error.URLError("no route: " + url)


def make_http(routes, **kw):
    net = FakeNet(routes)
    sleeps = []
    http = Http(opener=net, sleep=sleeps.append, clock=lambda: 0.0, **kw)
    return http, net, sleeps


def crossref_item(title, authors, year, doi="10.1234/x"):
    return {"DOI": doi, "title": [title], "issued": {"date-parts": [[year]]},
            "author": [{"given": g, "family": f} for g, f in authors]}


ARXIV_OK = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>http://arxiv.org/abs/2001.00001v1</id><published>2020-01-02T00:00:00Z</published>
<title>A Synthetic   Study of
 Widgets</title><author><name>Ada Example</name></author><author><name>Ben Sample</name></author></entry></feed>"""
ARXIV_EMPTY = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
ARXIV_ERR = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>'
             '<id>http://arxiv.org/api/errors#bad</id><title>Error</title></entry></feed>')
