"""Command line: citecheck refs.bib -o results.csv"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter

from . import __version__
from .bibtex import parse_bib
from .checker import (ERROR, NOT_FOUND, VERDICTS, VERIFIED, SKIPPED, Checker, Config, Result)
from .http import Http
from .sources import ALL_SOURCES, Sources

FIELDS = ["key", "entry_type", "verdict", "rung", "source", "matched_id", "title_similarity",
          "bib_title", "found_title", "bib_year", "found_year", "detail", "note"]


def read_csv(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["key"]: r for r in csv.DictReader(f)}


def write_csv(path: str, rows: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="citecheck",
        description="Check BibTeX entries against Crossref, OpenAlex, arXiv, Open Library and doi.org. "
                    "NOT_FOUND means 'review by hand', not 'fabricated'.")
    p.add_argument("bibfile")
    p.add_argument("-o", "--output", default="results.csv")
    p.add_argument("--mailto", help="contact address added to the User-Agent and polite-pool requests")
    p.add_argument("--resume", action="store_true", help="skip keys already in the CSV (ERROR rows are retried)")
    p.add_argument("--sources", default=",".join(ALL_SOURCES),
                   help="comma list from: " + ",".join(ALL_SOURCES))
    p.add_argument("--rate", type=float, default=1.0, help="max requests per second per host (default 1.0)")
    p.add_argument("--json", action="store_true", help="print the results as JSON on stdout")
    p.add_argument("--skip-types", default="", help="comma list of entry types to skip, e.g. misc,online")
    p.add_argument("--title-threshold", type=float, default=0.80)
    p.add_argument("--author-threshold", type=float, default=0.50)
    p.add_argument("--year-tolerance", type=int, default=1)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def run(args, http: Http | None = None, out=sys.stdout, err=sys.stderr) -> int:
    enabled = [s.strip() for s in args.sources.split(",") if s.strip()]
    bad = [s for s in enabled if s not in ALL_SOURCES]
    if bad or not enabled:
        print(f"unknown source(s): {', '.join(bad) or '(none given)'}", file=err)
        return 2
    try:
        with open(args.bibfile, encoding="utf-8", errors="replace") as f:
            entries = parse_bib(f.read())
    except OSError as e:
        print(f"cannot read {args.bibfile}: {e}", file=err)
        return 2
    cfg = Config(args.title_threshold, args.author_threshold, args.year_tolerance,
                 frozenset(t.strip().lower() for t in args.skip_types.split(",") if t.strip()))
    http = http or Http(rate=args.rate, mailto=args.mailto)
    checker = Checker(Sources(http, enabled, args.mailto), cfg)

    done = read_csv(args.output) if args.resume else {}
    keep = {k: r for k, r in done.items() if r.get("verdict") != ERROR}
    if not args.resume and os.path.exists(args.output):
        os.remove(args.output)
    todo = [e for e in entries if e.key not in keep]
    print(f"{len(entries)} entries, {len(keep)} already done, {len(todo)} to check", file=err)

    new_file = not (args.resume and os.path.exists(args.output))
    with open(args.output, "a" if not new_file else "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for i, e in enumerate(todo, 1):
            r = checker.check(e)
            w.writerow(r.__dict__)
            f.flush()
            keep[e.key] = {k: str(v) for k, v in r.__dict__.items()}
            print(f"[{i}/{len(todo)}] {e.key}: {r.verdict}", file=err)

    rows = [keep[e.key] for e in entries if e.key in keep]
    write_csv(args.output, rows)  # one row per key, in file order
    counts = Counter(r["verdict"] for r in rows)
    if args.json:
        json.dump({"results": rows, "summary": dict(counts)}, out, indent=2)
        out.write("\n")
    else:
        for v in VERDICTS:
            print(f"{v:18} {counts.get(v, 0)}", file=out)
        if counts.get(NOT_FOUND):
            print("NOT_FOUND needs manual review; it is not proof of fabrication.", file=out)
    clean = counts.get(VERIFIED, 0) + counts.get(SKIPPED, 0)
    return 0 if clean == len(rows) else 1


def main(argv=None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
