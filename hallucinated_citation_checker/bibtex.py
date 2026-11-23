"""A small BibTeX reader: braces, quotes, @string macros, '#' concatenation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SKIP_TYPES = {"comment", "preamble"}
_NAME_RE = re.compile(r"[A-Za-z0-9_\-:.+/]+")
_ACCENTS = {
    "\\&": "&",
    "\\%": "%",
    "\\_": "_",
    "\\#": "#",
    "\\$": "$",
    "---": "-",
    "--": "-",
    "~": " ",
}


@dataclass
class Entry:
    key: str
    type: str
    fields: dict = field(default_factory=dict)


def clean_value(text: str) -> str:
    """Drop braces and common escapes, collapse whitespace."""
    text = re.sub(r"\\[`'^\"~=.][{]?([A-Za-z])[}]?", r"\1", text)  # \'e, \"{o}
    for old, new in _ACCENTS.items():
        text = text.replace(old, new)
    text = re.sub(r"\\[A-Za-z]+\s*", "", text) if "\\" in text else text
    text = text.replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", text).strip()


class _Scanner:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.macros: dict[str, str] = {}

    def skip_ws(self):
        n = len(self.s)
        while self.i < n and self.s[self.i].isspace():
            self.i += 1

    def balanced(self, open_ch: str, close_ch: str) -> str:
        """Read from an opening delimiter to its match; return the inside."""
        assert self.s[self.i] == open_ch
        depth, start, n = 0, self.i + 1, len(self.s)
        while self.i < n:
            c = self.s[self.i]
            if c == "\\":
                self.i += 2
                continue
            if c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    inside = self.s[start:self.i]
                    self.i += 1
                    return inside
            self.i += 1
        inside = self.s[start:]
        self.i = n
        return inside

    def quoted(self) -> str:
        assert self.s[self.i] == '"'
        self.i += 1
        start, depth, n = self.i, 0, len(self.s)
        while self.i < n:
            c = self.s[self.i]
            if c == "\\":
                self.i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == '"' and depth <= 0:
                inside = self.s[start:self.i]
                self.i += 1
                return inside
            self.i += 1
        self.i = n
        return self.s[start:]

    def value(self) -> str:
        parts = []
        while True:
            self.skip_ws()
            if self.i >= len(self.s):
                break
            c = self.s[self.i]
            if c == "{":
                parts.append(self.balanced("{", "}"))
            elif c == '"':
                parts.append(self.quoted())
            else:
                m = _NAME_RE.match(self.s, self.i)
                if not m:
                    break
                self.i = m.end()
                tok = m.group(0)
                parts.append(tok if tok.isdigit() else self.macros.get(tok.lower(), ""))
            self.skip_ws()
            if self.i < len(self.s) and self.s[self.i] == "#":
                self.i += 1
                continue
            break
        return "".join(parts)

    def fields(self, close_ch: str) -> dict:
        out: dict = {}
        while self.i < len(self.s):
            self.skip_ws()
            if self.i >= len(self.s):
                break
            c = self.s[self.i]
            if c == close_ch:
                self.i += 1
                break
            if c == ",":
                self.i += 1
                continue
            m = _NAME_RE.match(self.s, self.i)
            if not m:
                self.i += 1
                continue
            name = m.group(0).lower()
            self.i = m.end()
            self.skip_ws()
            if self.i < len(self.s) and self.s[self.i] == "=":
                self.i += 1
                val = self.value()
                out.setdefault(name, val)
        return out


def parse_bib(text: str) -> list[Entry]:
    """Return entries in file order. @string macros are expanded; @comment and
    @preamble blocks are skipped."""
    sc = _Scanner(text)
    entries: list[Entry] = []
    n = len(text)
    while True:
        at = text.find("@", sc.i)
        if at < 0:
            break
        sc.i = at + 1
        m = re.compile(r"[A-Za-z]+").match(text, sc.i)
        if not m:
            continue
        etype = m.group(0).lower()
        sc.i = m.end()
        sc.skip_ws()
        if sc.i >= n or text[sc.i] not in "{(":
            continue
        open_ch = text[sc.i]
        close_ch = "}" if open_ch == "{" else ")"
        if etype in _SKIP_TYPES:
            sc.balanced(open_ch, close_ch)
            continue
        if etype == "string":
            sc.i += 1
            body = sc.fields(close_ch)
            for k, v in body.items():
                sc.macros[k] = v
            continue
        sc.i += 1
        sc.skip_ws()
        km = re.compile(r"[^,\s{}]+").match(text, sc.i)
        if not km:
            continue
        key = km.group(0)
        sc.i = km.end()
        raw = sc.fields(close_ch)
        entries.append(Entry(key, etype, {k: clean_value(v) for k, v in raw.items()}))
    return entries
