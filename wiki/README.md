# Project Wiki

This directory is an Obsidian-compatible vault maintained as a project knowledge
base. It records experiment results, reflections, open lessons, and reusable
context for development.

## Layout

- `index.md`: reading router for common situations. It is not a page catalog.
- `log.md`: append-only chronology of ingest, query, lint, and maintenance work.
- `pages/*.md`: flat Markdown pages.
- `assets/*`: images and other small attachments referenced by pages.

## Page Frontmatter

Every page must start with YAML frontmatter:

```yaml
---
title: Page Title
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
status: draft
kind: concept
---
```

Allowed `status` values: `draft`, `active`, `stable`, `deprecated`.

Allowed `kind` values: `concept`, `entity`, `preference`, `experiment`,
`source`, `claim`, `workflow`, `decision`, `reflection`.

Use regular Markdown links. Do not use Obsidian WikiLinks.

## Link Discipline

Do not create orphan pages. Every new `wiki/pages/*.md` page must be reachable
through regular Markdown links from `wiki/index.md` or from another page that is
already reachable from the index.

When adding a page, update the route that explains when to read it. If a page was
hard to find during work, improve the index or nearby links before finishing.

## Experiment Knowledge

This project accumulates knowledge by writing small scripts, running experiments,
and preserving the findings that should influence future experiments.

For each meaningful experiment, record the script or command, input data,
parameters, machine, runtime notes, output location, result, failure mode, and
next hypothesis. Prefer improving existing experiment pages when the new result
belongs to the same line of investigation.
