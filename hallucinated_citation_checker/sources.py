"""Lookups against public indexes. Each returns Record objects, or None / []
when the index has no match. HttpError propagates for outages."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import quote, urlencode

from .http import Http, HttpError
from .similarity import year_of

__all__ = ["Record", "Sources", "HttpError", "ALL_SOURCES"]

ALL_SOURCES = ("crossref", "openalex", "arxiv", "openlibrary", "doi")
_ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass
class Record:
    source: str
    id: str
    title: str
    authors: list = field(default_factory=list)  # full names as the index gives them
    year: int | None = None


def _json(body: bytes):
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except ValueError as e:
        raise HttpError(f"unreadable JSON response: {e}") from e


def _need_ok(status: int, host: str, body: bytes = b""):
    if status != 200:
        raise HttpError(f"HTTP {status} from {host}")


def _csl_name(a: dict) -> str:
    if a.get("family"):
        return f"{a.get('given', '')} {a['family']}".strip()
    return a.get("name") or a.get("literal") or ""


def _crossref_record(msg: dict) -> Record:
    titles = msg.get("title") or []
    parts = None
    for k in ("issued", "published-print", "published-online", "created"):
        dp = (msg.get(k) or {}).get("date-parts") or [[None]]
        if dp and dp[0] and dp[0][0]:
            parts = dp[0][0]
            break
    return Record("crossref", msg.get("DOI", ""), titles[0] if titles else "",
                  [_csl_name(a) for a in msg.get("author", [])], year_of(parts))


class Sources:
    def __init__(self, http: Http, enabled=ALL_SOURCES, mailto: str | None = None):
        self.http = http
        self.enabled = set(enabled)
        self.mailto = mailto

    def _mailto(self, sep: str) -> str:
        return f"{sep}mailto={quote(self.mailto)}" if self.mailto else ""

    # -- identifier lookups ------------------------------------------------

    def crossref_doi(self, doi: str) -> Record | None:
        status, body = self.http.get(
            f"https://api.crossref.org/works/{quote(doi, safe='/')}{self._mailto('?')}")
        if status == 404:
            return None
        _need_ok(status, "api.crossref.org")
        return _crossref_record(_json(body).get("message", {}))

    def doi_org(self, doi: str) -> Record | None:
        status, body = self.http.get(
            f"https://doi.org/{quote(doi, safe='/')}",
            {"Accept": "application/vnd.citationstyles.csl+json"})
        if status == 404:
            return None
        _need_ok(status, "doi.org")
        d = _json(body)
        title = d.get("title") or ""
        if isinstance(title, list):
            title = title[0] if title else ""
        dp = (d.get("issued") or {}).get("date-parts") or [[None]]
        year = year_of(dp[0][0]) if dp and dp[0] else None
        return Record("doi", d.get("DOI", doi), title,
                      [_csl_name(a) for a in d.get("author", [])], year)

    def arxiv(self, arxiv_id: str) -> Record | None:
        status, body = self.http.get(
            f"https://export.arxiv.org/api/query?{urlencode({'id_list': arxiv_id})}")
        _need_ok(status, "export.arxiv.org")
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            raise HttpError(f"unreadable arXiv response: {e}") from e
        entry = root.find(f"{_ATOM}entry")
        if entry is None:
            return None
        eid = (entry.findtext(f"{_ATOM}id") or "")
        if "/api/errors" in eid:
            return None
        title = re.sub(r"\s+", " ", entry.findtext(f"{_ATOM}title") or "").strip()
        names = [(a.findtext(f"{_ATOM}name") or "") for a in entry.findall(f"{_ATOM}author")]
        return Record("arxiv", arxiv_id, title, names,
                      year_of((entry.findtext(f"{_ATOM}published") or "")[:4]))

    def openlibrary(self, isbn: str) -> Record | None:
        key = "ISBN:" + re.sub(r"[^0-9Xx]", "", isbn)
        status, body = self.http.get(
            "https://openlibrary.org/api/books?" +
            urlencode({"bibkeys": key, "format": "json", "jscmd": "data"}))
        _need_ok(status, "openlibrary.org")
        d = _json(body).get(key)
        if not d:
            return None
        return Record("openlibrary", key, d.get("title", ""),
                      [a.get("name", "") for a in d.get("authors", [])],
                      year_of(d.get("publish_date")))

    # -- title search ------------------------------------------------------

    def crossref_search(self, title: str, first_surname: str = "") -> list[Record]:
        q = urlencode({"query.bibliographic": f"{title} {first_surname}".strip(), "rows": 5})
        status, body = self.http.get(f"https://api.crossref.org/works?{q}{self._mailto('&')}")
        _need_ok(status, "api.crossref.org")
        items = (_json(body).get("message") or {}).get("items") or []
        return [_crossref_record(i) for i in items]

    def openalex_search(self, title: str) -> list[Record]:
        q = urlencode({"search": title, "per-page": 5})
        status, body = self.http.get(f"https://api.openalex.org/works?{q}{self._mailto('&')}")
        _need_ok(status, "api.openalex.org")
        out = []
        for w in _json(body).get("results") or []:
            names = [(a.get("author") or {}).get("display_name", "") for a in w.get("authorships", [])]
            out.append(Record("openalex", w.get("id", ""), w.get("title") or w.get("display_name") or "",
                              names, w.get("publication_year")))
        return out
