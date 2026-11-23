#!/usr/bin/env python3
"""Run the checker over benchmark/bench.bib and print a confusion table.

Needs network access. Usage: python3 benchmark/bench.py [--mailto ADDR] [--rate 1.0]
Writes benchmark/results.csv and benchmark/confusion.md.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from hallucinated_citation_checker import cli  # noqa: E402
from hallucinated_citation_checker.checker import VERDICTS  # noqa: E402

TRUTHS = ("real", "corrupted", "invented")


def confusion(labels: list[dict], results: dict) -> dict:
    """{truth: {verdict: count}} for every labelled key that has a result."""
    table = {t: {v: 0 for v in VERDICTS} for t in TRUTHS}
    for row in labels:
        res = results.get(row["key"])
        if res:
            table[row["truth"]][res["verdict"]] += 1
    return table


def render(table: dict) -> str:
    cols = [v for v in VERDICTS if any(table[t][v] for t in TRUTHS)] or list(VERDICTS)
    lines = ["| truth | n | " + " | ".join(cols) + " |", "|---|---|" + "---|" * len(cols)]
    for t in TRUTHS:
        n = sum(table[t].values())
        lines.append(f"| {t} | {n} | " + " | ".join(str(table[t][c]) for c in cols) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mailto")
    ap.add_argument("--rate", type=float, default=1.0)
    a = ap.parse_args(argv)
    out = os.path.join(HERE, "results.csv")
    args = cli.build_parser().parse_args(
        [os.path.join(HERE, "bench.bib"), "-o", out, "--rate", str(a.rate)]
        + (["--mailto", a.mailto] if a.mailto else []))
    cli.run(args, out=io.StringIO())
    with open(os.path.join(HERE, "labels.csv"), newline="", encoding="utf-8") as f:
        labels = list(csv.DictReader(f))
    table = render(confusion(labels, cli.read_csv(out)))
    with open(os.path.join(HERE, "confusion.md"), "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
