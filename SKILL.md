---
name: hallucinated-citation-checker
description: Check every entry of a BibTeX file against Crossref, OpenAlex, arXiv, Open Library and doi.org to catch fabricated or garbled references after AI drafting or before submission. Gives a CSV verdict per key; NOT_FOUND means review by hand.
---

# Hallucinated citation checker

Run this on a `.bib` file before submission, and after any AI-assisted drafting or reference cleanup.

## Steps

1. Run the checker (Python 3.10+, no dependencies; network needed):
   `python3 -m hallucinated_citation_checker refs.bib -o results.csv --mailto you@example.invalid`
   Replace the address with the user's own, or omit `--mailto`. Never invent an address.
2. Large files are slow on purpose (about one request per second per host, three seconds for arXiv). If it stops, re-run with `--resume`.
3. Read `results.csv` and report per key:
   - `VERIFIED`: a record matches on title, authors and year. Say nothing more.
   - `METADATA_MISMATCH`: a record exists but a field differs. Show the `detail` column and ask the user which side is right. Do not edit the bib on your own.
   - `NOT_FOUND`: no match in the sources checked. List these for manual review. Books, chapters, old, non-English and very new works are often missing. Never call a reference fake or delete it only because of this verdict.
   - `ERROR`: a service failed after retries. Re-run with `--resume`; do not treat it as a finding.
   - `SKIPPED`: the entry type was excluded or had nothing to check.
4. Summarize counts, then the items that need a human. Offer to look each one up by hand (publisher page, library catalogue, the paper's own reference list).

## Rules

- Only public identifiers and title/author/year are sent to the indexes. Do not add private text to a bib entry before checking.
- Exit code 0 means all verified or skipped; 1 means at least one entry needs attention; 2 is a usage error.
- Without shell access, use PROMPT.md and treat any model's memory of a paper as unverified.

Details: README.md (options, thresholds, benchmark, limits).
