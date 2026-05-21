<!-- llm-wiki:start -->
## Wiki

`wiki/` is an Obsidian-compatible LLM-maintained knowledge base for Codex.
Use it to accumulate experiment results, reflections, lessons, recurring
mistakes, and design background so future work does not rediscover the same
context from scratch.

- Stable official records belong in durable docs.
- Unresolved repository-level decisions and work items belong in issues.
- Cross-cutting concepts, experiment memory, reflections, preferences, and reusable understanding belong in `wiki/`.
- Keep `wiki/pages/*.md` flat; do not create hierarchical topic folders.
- Keep `wiki/index.md` as a reading router: "when should I read what?"
- Do not use WikiLinks (`[[...]]`). Use regular Markdown links.
- Prefer links and `rg` search over tags.
- Do not create orphan wiki pages. Every new `wiki/pages/*.md` page must be linked
  from `wiki/index.md` or from another already-linked wiki page in the same change.
- For experiments, create or update the script first, run or document the run, then
  preserve reusable findings in the wiki so future work can build on them.
- Keep shared code at the utility level only. Do not extract algorithms,
  experiment structure, or compatibility layers just because a new script looks
  similar. Only factor out code after the same small operation has been copied
  many times and is clearly independent of the algorithm being tested.
- When updating the wiki, append an ingest/query/lint/maintenance entry to `wiki/log.md`.
- When a consulted wiki page helped or failed, improve the page, links, or index route so the knowledge base gets better.
<!-- llm-wiki:end -->
