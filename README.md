# hallucinated-citation-checker

Check every entry in a BibTeX file against Crossref, OpenAlex, arXiv, Open Library and doi.org, so fabricated or garbled references from AI drafting get caught before submission. For researchers, students, editors and anyone who pastes reference lists from a chat assistant.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

The output is one CSV row per BibTeX key with a verdict: `VERIFIED`, `METADATA_MISMATCH`, `NOT_FOUND`, `ERROR` or `SKIPPED`. `NOT_FOUND` means "review by hand", never "fake". Python 3.10+, standard library only, resumable and rate-limited.

## Works with

| Surface | How (prompt / native skill / CLI / hook / MCP) | Status |
|---|---|---|
| Terminal (`citecheck`, `python -m`) | CLI | tested 2026-11-23, Python 3.14.10, live network run (see Example and Benchmark) |
| Unit tests | `python3 -m unittest`, offline, mocked network | tested 2026-11-23, Python 3.14.10 |
| Claude Code | native skill (`SKILL.md`, installed by `install.sh`) | install script tested offline 2026-11-23; skill loading in the agent not tested |
| Codex | native skill via `.agents/skills` | install script tested offline 2026-11-23; skill loading in the agent not tested |
| Gemini CLI | native skill via `.agents/skills` / pointer in `GEMINI.md` | not tested |
| Cursor | `AGENTS.md` / `.agents/skills` | not tested |
| Copilot | pointer to `AGENTS.md` | not tested |
| ChatGPT / Claude.ai / Gemini (chat) | prompt (`PROMPT.md`); a chat model without browsing cannot verify anything | not tested |

## Quick start

```sh
git clone https://github.com/hyderhusainarastu/hallucinated-citation-checker
cd hallucinated-citation-checker
python3 -m hallucinated_citation_checker examples/refs.bib -o results.csv --mailto you@example.invalid
# or: pip install .   then   citecheck refs.bib -o results.csv
```

Use your own address for `--mailto` (it goes into the User-Agent and the polite-pool parameter of Crossref and OpenAlex) or leave it out. Not published on PyPI yet; `pyproject.toml` is ready.

Options:

| Option | Meaning |
|---|---|
| `-o FILE` | output CSV (default `results.csv`) |
| `--resume` | skip keys already in the CSV; `ERROR` rows are retried |
| `--sources LIST` | any of `crossref,openalex,arxiv,openlibrary,doi` |
| `--rate N` | max requests per second per host (default 1.0; arXiv is held to one per 3 s) |
| `--json` | print results and summary as JSON on stdout |
| `--skip-types LIST` | entry types to skip, e.g. `misc,online` |
| `--title-threshold`, `--author-threshold`, `--year-tolerance` | match settings (defaults 0.80, 0.50, 1 year) |

Exit codes: 0 all verified or skipped, 1 something needs attention, 2 usage error.

AI coding agents: install as a skill with `./install.sh --claude` (Claude Code) or `./install.sh --agents --project .` (Codex, Cursor, Gemini CLI). `./install.sh --gemini|--cursor|--copilot` adds a pointer block instead. See `AGENTS.md` for the call contract.

## How it checks

For each entry the checker climbs a ladder and stops at the first rung that returns a record:

1. DOI: Crossref works API, then doi.org content negotiation (arXiv DOIs go to rung 2).
2. arXiv id (from `eprint`, `url`, `note` or an arXiv DOI): arXiv API.
3. ISBN: Open Library.
4. Title search with the first author: Crossref and OpenAlex.

A found record is compared with the entry: normalised title token overlap (Dice) against the title threshold, the share of the entry's author surnames present in the record against the author threshold, and year within the tolerance. All three pass: `VERIFIED`. A record exists but a field fails: `METADATA_MISMATCH`, with the difference in `detail`. A DOI or ISBN that does not resolve while a title search finds a matching work is also a mismatch (the identifier is wrong). Search hits whose title is below the threshold are ignored. Network failures retry with exponential backoff and end as `ERROR`, never `NOT_FOUND`.

Only public identifiers and the title, first author surname and year are sent. User-Agent: `hallucinated-citation-checker/<version>`, plus `mailto:` only when you pass `--mailto`. The BibTeX reader handles braces, quotes, `@string` macros, `#` concatenation and common escapes.

## Example

```
$ python3 -m hallucinated_citation_checker examples/refs.bib -o results.csv --mailto you@example.invalid
5 entries, 0 already done, 5 to check
[1/5] shannon1948: VERIFIED
[2/5] turing1950: VERIFIED
[3/5] vaswani2017: VERIFIED
[4/5] invented2021a: NOT_FOUND
[5/5] invented2022b: NOT_FOUND
VERIFIED           3
METADATA_MISMATCH  0
NOT_FOUND          2
ERROR              0
SKIPPED            0
NOT_FOUND needs manual review; it is not proof of fabrication.
```

Run on 2026-11-23; the CSV is saved as `examples/results.csv`. The first three entries are real classics, the last two are invented for this example.

## Benchmark

`benchmark/` holds 46 hand-labelled entries (`bench.bib`, `labels.csv`): 30 real works (journal articles, preprints, conference papers, books with and without ISBN, book chapters, one old non-English article), 8 invented references and 8 real works with one field corrupted (year, author, title or DOI). `python3 benchmark/bench.py` needs network and writes `benchmark/results.csv` and `benchmark/confusion.md`.

Measured 2026-11-23 (version 0.1.0, all five sources, rate 1.0):

| truth | n | VERIFIED | METADATA_MISMATCH | NOT_FOUND |
|---|---|---|---|---|
| real | 30 | 28 | 2 | 0 |
| corrupted | 8 | 0 | 8 | 0 |
| invented | 8 | 0 | 0 | 8 |

The two false alarms on real works: a textbook whose Open Library title is shorter than the cited one, and a 1986 book chapter whose index record carries a later reprint year. Read this as a smoke test, not an accuracy claim: the set is small, the works are well known and well indexed, and the author wrote the labels. Obscure, non-English or very new works will do worse, and a corrupted title with no identifier shows up as `NOT_FOUND`, not as a mismatch.

## How it differs

- Reference managers such as Zotero and JabRef can fetch metadata for an identifier you give them; they do not audit a whole `.bib` for entries that do not exist, and they do not write a verdict per key.
- Citegate is another checker for citations. It is listed here as an alternative; this README makes no claim about how it compares.
- This tool is a small, dependency-free script with a per-key CSV, a resume mode and an explicit "needs manual review" verdict.

## Limits

- `NOT_FOUND` is not proof of fabrication. Books, chapters, theses, reports, old, non-English and very recent works are often missing from these indexes.
- `VERIFIED` means a record with a matching title, authors and year exists. It does not check that the cited claim, page or quote is in the work (see quote-verification-toolkit).
- Title search can match a different work with a near-identical title; thresholds are tunable but not perfect. Editions and reprints can trigger year mismatches.
- Corporate authors and unusual name formats may fail the surname match. Entries with no title and no identifier are skipped.
- Needs network access and is slow by design (one request per second per host; arXiv one per three seconds). Index outages become `ERROR`.
- Only the BibTeX format is read (no BibLaTeX-specific `date`/`eprinttype` handling beyond `eprint`, `url`, `doi`, `isbn`, `year`).

## Tests

```sh
python3 -m unittest discover -s tests -t .
```

Runs offline: the network is replaced by hand-written synthetic fixtures for each source, verdict, 503 retries, resume, threshold edges and the BibTeX reader.

## Related

- scholarly-citation-resolver
- quote-verification-toolkit
- scholarly-metadata-resolution-pattern

## Keywords

hallucinated citations, fake references, BibTeX checker, reference checker, citation verification, Crossref, OpenAlex, arXiv, research integrity, LLM-generated references

---
Part of palimnote-tools - more at https://github.com/hyderhusainarastu
