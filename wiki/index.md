# Project Wiki Index

This is a reading router, not a catalog. Use it when the problem shape is known
but the right search term is not. For exhaustive discovery, use `rg` over
`wiki/pages` and durable project files.

## When Starting Wiki Work

Read [LLM-maintained wiki](./pages/llm-maintained-wiki.md) when deciding whether something
belongs in the wiki, durable docs, or issues.

Read [Wiki maintenance feedback loop](./pages/wiki-maintenance-feedback-loop.md) when a prior page was useful,
misleading, stale, or hard to find.

Read [Experiment knowledge workflow](./pages/experiment-knowledge-workflow.md) when adding
or reviewing experiment scripts, results, failures, or reusable lessons.

## When Starting Repository Work

Read [Project purpose](./pages/project-purpose.md) when you need the repository's
research goal, scope, and lightweight-method bias.

Read [Toolchain and task workflow](./pages/toolchain-and-task-workflow.md) when using
`uv`, adding `mise` tasks, running checks, or recording repeatable commands.

## When Reconstructing Project Context

Read [Project knowledge map](./pages/project-knowledge-map.md) when you need a short route into the
project's durable docs, local issues, recurring failure histories, or high-signal
search recipes.

```sh
rg -n "term|failure|experiment|decision" wiki/pages README.md mise.toml pyproject.toml
```
