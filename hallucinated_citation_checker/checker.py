"""Verification ladder and verdicts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .bibtex import Entry
from .similarity import (author_overlap, bib_surnames, record_surnames,
                         title_similarity, year_of)
from .sources import HttpError, Record, Sources

VERIFIED = "VERIFIED"
MISMATCH = "METADATA_MISMATCH"
NOT_FOUND = "NOT_FOUND"
ERROR = "ERROR"
SKIPPED = "SKIPPED"
VERDICTS = (VERIFIED, MISMATCH, NOT_FOUND, ERROR, SKIPPED)

NOT_FOUND_NOTE = ("Not found in the sources checked. This needs manual review and is NOT proof "
                  "of fabrication: books, chapters, old and non-English works are often missing.")

_ARXIV_DOI = re.compile(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})(v\d+)?", re.I)
_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(v\d+)?", re.I)
_ARXIV_ID = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?$", re.I)
_DOI = re.compile(r"10\.\d{4,9}/\S+")


@dataclass
class Config:
    title_threshold: float = 0.80
    author_threshold: float = 0.50
    year_tolerance: int = 1
    skip_types: frozenset = frozenset()


@dataclass
class Result:
    key: str
    entry_type: str
    verdict: str
    rung: str = ""
    source: str = ""
    matched_id: str = ""
    title_similarity: str = ""
    bib_title: str = ""
    found_title: str = ""
    bib_year: str = ""
    found_year: str = ""
    detail: str = ""
    note: str = ""


@dataclass
class Comparison:
    ok: bool
    sim: float
    diffs: list = field(default_factory=list)


def doi_of(fields: dict) -> str:
    for k in ("doi", "url"):
        v = fields.get(k, "")
        if k == "url" and "doi.org" not in v:
            continue
        m = _DOI.search(v)
        if m:
            return m.group(0).rstrip(".,;")
    return ""


def arxiv_of(fields: dict) -> str:
    m = _ARXIV_DOI.search(fields.get("doi", ""))
    if m:
        return m.group(1)
    for k in ("eprint", "url", "note"):
        v = fields.get(k, "").strip()
        m = _ARXIV_URL.search(v) or _ARXIV_ID.match(v)
        if m:
            return m.group(1)
    return ""


def isbn_of(fields: dict) -> str:
    raw = re.sub(r"[\s-]", "", fields.get("isbn", ""))
    m = re.search(r"\d{13}|\d{9}[\dXx]", raw)
    return m.group(0) if m else ""


def compare(fields: dict, rec: Record, cfg: Config) -> Comparison:
    bt = fields.get("title", "")
    sim = title_similarity(bt, rec.title) if bt else 1.0
    diffs = []
    if bt and sim < cfg.title_threshold:
        diffs.append(f"title: bib={bt!r} vs {rec.source}={rec.title!r} (similarity {sim:.2f})")
    ov = author_overlap(bib_surnames(fields.get("author", "")), record_surnames(rec.authors))
    if ov is not None and ov < cfg.author_threshold:
        diffs.append(f"authors: bib={fields.get('author')!r} vs {rec.source}={'; '.join(rec.authors)!r}")
    by = year_of(fields.get("year", ""))
    if by and rec.year and abs(by - int(rec.year)) > cfg.year_tolerance:
        diffs.append(f"year: bib={by} vs {rec.source}={rec.year}")
    return Comparison(not diffs, sim, diffs)


class Checker:
    def __init__(self, sources: Sources, cfg: Config | None = None):
        self.src = sources
        self.cfg = cfg or Config()

    def _on(self, name: str) -> bool:
        return name in self.src.enabled

    def _result(self, entry: Entry, verdict: str, rung="", rec: Record | None = None,
                cmp: Comparison | None = None, detail="", note="") -> Result:
        f = entry.fields
        r = Result(entry.key, entry.type, verdict, rung=rung, bib_title=f.get("title", ""),
                   bib_year=str(year_of(f.get("year", "")) or ""), detail=detail, note=note)
        if rec:
            r.source, r.matched_id = rec.source, rec.id
            r.found_title, r.found_year = rec.title, str(rec.year or "")
        if cmp:
            r.title_similarity = f"{cmp.sim:.3f}"
        if verdict == NOT_FOUND:
            r.note = NOT_FOUND_NOTE
        return r

    def check(self, entry: Entry) -> Result:
        f = entry.fields
        if entry.type in self.cfg.skip_types:
            return self._result(entry, SKIPPED, note=f"entry type @{entry.type} is configured to be skipped")
        doi, arx, isbn, title = doi_of(f), arxiv_of(f), isbn_of(f), f.get("title", "")
        if _ARXIV_DOI.search(doi):
            doi = ""  # arXiv DOIs are checked on the arXiv rung
        if not (doi or arx or isbn or title):
            return self._result(entry, SKIPPED, note="no identifier and no title to check")

        errors: list[str] = []
        stale: list[str] = []  # identifiers that did not resolve

        def lookup(rung, ident, fns):
            """Return (record, errored). errored is True when any source raised, so a
            None record then means 'unknown', not 'resolved to nothing'."""
            errored = False
            for fn in fns:
                try:
                    rec = fn(ident)
                except HttpError as e:
                    errors.append(f"{fn.__name__}: {e}")
                    errored = True
                    continue
                if rec is not None:
                    return rec, errored
            return None, errored

        ladder = []
        if doi:
            fns = [fn for name, fn in (("crossref", self.src.crossref_doi), ("doi", self.src.doi_org))
                   if self._on(name)]
            ladder.append(("doi", doi, fns))
        if arx and self._on("arxiv"):
            ladder.append(("arxiv", arx, [self.src.arxiv]))
        if isbn and self._on("openlibrary"):
            ladder.append(("isbn", isbn, [self.src.openlibrary]))

        for rung, ident, fns in ladder:
            rec, errored = lookup(rung, ident, fns)
            if rec is None:
                if not errored:  # only a true miss counts; an outage is not a finding
                    stale.append(f"{rung} {ident} did not resolve")
                continue
            cmp = compare(f, rec, self.cfg)
            if cmp.ok:
                return self._result(entry, VERIFIED, rung, rec, cmp)
            return self._result(entry, MISMATCH, rung, rec, cmp, detail="; ".join(cmp.diffs))

        if title:
            hit = self._search(entry, errors)
            if hit:
                rec, cmp = hit
                if cmp.ok and not stale:
                    return self._result(entry, VERIFIED, "search", rec, cmp)
                diffs = stale + cmp.diffs
                if cmp.ok:
                    diffs = [s + "; a record with matching title, authors and year exists" for s in stale]
                return self._result(entry, MISMATCH, "search", rec, cmp, detail="; ".join(diffs))

        if errors:
            return self._result(entry, ERROR, detail="; ".join(errors),
                                note="Lookup failed (network or service outage). Re-run with --resume.")
        detail = "; ".join(stale)
        return self._result(entry, NOT_FOUND, "search" if title else "", detail=detail)

    def _search(self, entry: Entry, errors: list):
        f = entry.fields
        title = f["title"]
        sn = bib_surnames(f.get("author", ""))
        calls = []
        if self._on("crossref"):
            calls.append(lambda: self.src.crossref_search(title, sn[0] if sn else ""))
        if self._on("openalex"):
            calls.append(lambda: self.src.openalex_search(title))
        best = None
        for call in calls:
            try:
                recs = call()
            except HttpError as e:
                errors.append(f"search: {e}")
                continue
            for rec in recs:
                cmp = compare(f, rec, self.cfg)
                if cmp.sim < self.cfg.title_threshold:
                    continue  # a different work, not evidence about this one
                if cmp.ok:
                    return rec, cmp
                if best is None or (len(cmp.diffs), -cmp.sim) < (len(best[1].diffs), -best[1].sim):
                    best = (rec, cmp)
        return best
