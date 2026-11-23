# Manual reference check (no tools needed)

Paste this into a chat assistant together with your bibliography. If your assistant cannot browse, it can only help you organise the checking. It cannot verify that a paper exists.

---

You are helping me check a reference list for fabricated or garbled citations. Rules:

1. You cannot verify existence from memory. A model recalling a paper is not evidence that it exists, and a model not recalling one is not evidence that it does not. Say this once, then proceed.
2. If you can search the web or open links, check each reference against Crossref, OpenAlex, arXiv, Open Library or the publisher page. Otherwise do not claim anything is verified.
3. For each reference, output one row: key, what to look up (DOI, arXiv id, ISBN, or exact title plus first author), and which of these checks apply:
   - the DOI or arXiv id resolves and its title matches the entry,
   - the first author's surname and the year match (a one-year difference is normal for preprints),
   - the venue or publisher matches.
4. Mark each row one of: VERIFIED (you or I saw a matching record), METADATA_MISMATCH (a record exists but title, authors or year differ; say which), NOT_FOUND (no match found; this means check by hand and is not proof of fabrication, because books, chapters, old and non-English works are often missing), or UNCHECKED (you could not look).
5. Never delete or rewrite a reference only because you could not find it. Never invent a DOI, page range or author to make an entry look complete.
6. Finish with counts per verdict and a short list of the entries I should check myself, with a search string for each.

My references:

[paste BibTeX here]

---

## Reading the CSV from the command line tool

If you ran `citecheck` instead, paste `results.csv` into the chat and ask: "Summarise the verdict counts, then list every METADATA_MISMATCH with its detail, then every NOT_FOUND for manual review." The `detail` column says which field differs; the `note` column repeats that NOT_FOUND is not proof of fabrication.
