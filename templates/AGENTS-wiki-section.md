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
- When updating the wiki, append an ingest/query/lint/maintenance entry to `wiki/log.md`.
- When a consulted wiki page helped or failed, improve the page, links, or index route so the knowledge base gets better.
