"""Normalisation and comparison helpers for titles, authors and years."""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def tokens(text: str) -> list[str]:
    return [t for t in re.sub(r"[^a-z0-9]+", " ", fold(text)).split() if t]


def title_similarity(a: str, b: str) -> float:
    """Dice overlap of normalised token sets, 0.0 to 1.0."""
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    return 2 * len(ta & tb) / (len(ta) + len(tb))


def surname_of(name: str) -> str:
    """Last name from 'Family, Given' or 'Given Family'."""
    name = _WS.sub(" ", name or "").strip()
    if not name:
        return ""
    if "," in name:
        fam = name.split(",", 1)[0]
    else:
        fam = name.split(" ")[-1]
    return " ".join(tokens(fam))


def bib_surnames(author_field: str) -> list[str]:
    out = []
    for part in re.split(r"\s+and\s+", author_field or ""):
        part = part.strip()
        if not part or part.lower() == "others":
            continue
        s = surname_of(part)
        if s:
            out.append(s)
    return out


def record_surnames(names: list[str]) -> list[str]:
    return [s for s in (surname_of(n) for n in names) if s]


def author_overlap(bib: list[str], rec: list[str]) -> float | None:
    """Share of bib surnames present in the record; None if either side is empty."""
    if not bib or not rec:
        return None
    rset = set(rec)
    # compare on last token so 'van der berg' equals 'berg'
    rlast = {r.split()[-1] for r in rset}
    hit = sum(1 for b in bib if b in rset or b.split()[-1] in rlast)
    return hit / len(bib)


def year_of(text) -> int | None:
    m = re.search(r"(1[5-9]|20)\d{2}", str(text or ""))
    return int(m.group(0)) if m else None
