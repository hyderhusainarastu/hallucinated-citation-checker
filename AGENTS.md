# hallucinated-citation-checker

Checks each entry of a BibTeX file against Crossref, OpenAlex, arXiv, Open Library and doi.org and writes a CSV verdict per key.

## Using this in your project

- Run `python3 -m hallucinated_citation_checker refs.bib -o results.csv --mailto <user address>` (or `citecheck ...` after `pip install .`). Python 3.10+, no dependencies, network required.
- Use the user's own address for `--mailto`, or omit it. Never invent one.
- Verdicts: `VERIFIED`, `METADATA_MISMATCH`, `NOT_FOUND`, `ERROR`, `SKIPPED`. Read the `detail` and `note` columns.
- Exit codes: 0 all verified or skipped, 1 some entry needs attention, 2 usage error.
- Long runs are slow by design. If interrupted, re-run the same command with `--resume`; `ERROR` rows are retried.
- `NOT_FOUND` means "check by hand". Never call a reference fabricated, and never delete or rewrite it, on that verdict alone.
- `METADATA_MISMATCH`: show the user the `detail` and let them decide which side is right. Do not auto-edit the bib.
- `ERROR` is an outage, not a finding. Re-run with `--resume`.
- No PROMPT.md rule: this is a CLI with a SKILL.md; chat-only users read PROMPT.md.
- Send nothing but public identifiers and title/author/year; do not add private text to entries before checking.
- Never claim a reference is verified from a model's memory. Only a tool result counts.
- Options: `--sources`, `--rate`, `--json`, `--skip-types`, `--title-threshold`, `--author-threshold`, `--year-tolerance` (see README).

## Working on this repo

- Setup: none (standard library only). Optional: `pip install -e .`.
- Test: `python3 -m unittest discover -s tests -t .` (runs offline; the network is mocked).
- Install test: `bash test_install.sh`.
- Benchmark (network, optional): `python3 benchmark/bench.py`. Report only numbers it prints, with the date. Never estimate.
- Layout: `hallucinated_citation_checker/` (bibtex, similarity, http, sources, checker, cli), `tests/`, `benchmark/`, `examples/`.
- Do not hand-edit `install.sh` or `test_install.sh`; they are shared templates.
- Keep examples synthetic or public classics. Do not commit result CSVs from real manuscripts.

<!-- cc-only -->
<!-- No Claude Code specific notes. -->
<!-- /cc-only -->
