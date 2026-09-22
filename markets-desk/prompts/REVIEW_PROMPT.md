# Review prompt — Markets Desk

Review, read-only. Do not modify files.

<PASTE ONE OF: a ticket / challenge / report YAML, a diff, or "the repo">

Focus, in order:

1. **Boundary.** Anything that could place, size, route, sign, or spend.
   Anything that weakens `tests/test_boundary.py` or arms a venue.
2. **Invented facts.** Any number without a source and an `as_of`. Any
   `as_of` that is fetch time rather than fact time. Any naive timestamp.
3. **Soft evidence doing hard work.** A thesis leaning on
   `social`/`news`/`sentiment`.
4. **Contract drift.** A file that satisfies the schema while answering
   nothing the desk asked (an assignment audit would catch this — say if one
   should be run).
5. **Correlation.** A second mechanism where a theme cap already exists; a
   model reviewing its own model's ticket; two seats agreeing being presented
   as evidence.
6. **Prose that is not enforced.** A rule that lives only in a doc.

Return:
1. Must-fix, with the file and line.
2. Should-fix.
3. What you could not verify from here, and what would.
