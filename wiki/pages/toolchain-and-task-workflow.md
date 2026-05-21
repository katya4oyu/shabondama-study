---
title: Toolchain and Task Workflow
created_at: 2026-05-21
updated_at: 2026-05-21
status: active
kind: workflow
---

# Toolchain and Task Workflow

This project uses `uv` for Python dependency and command execution, and `mise`
as the task runner for repeatable project commands.

## uv Policy

Use `uv` for environment synchronization and script execution.

Always include the release-date cutoff used by this repository:

```sh
uv --exclude-newer 2026-05-21T00:00:00Z sync
```

The cutoff reduces exposure to very recent malicious or broken package releases.
Direct dependencies are pinned in `pyproject.toml`, and `uv.lock` should be kept
with the repository.

Run Python entry points through `uv run` when calling them directly:

```sh
uv --exclude-newer 2026-05-21T00:00:00Z run detect-bubbles data/images/sample.jpg
```

## mise Tasks

Prefer `mise` for common project actions because it preserves command spelling
and cutoff behavior.

Current tasks:

- `mise run sync`: install locked dependencies with the cutoff.
- `mise run audit`: run `pip-audit` through `uv`.
- `mise run check`: run repository checks.
- `mise run detect -- data/images/sample.jpg`: run the current still-image bubble
  detector.

When adding a repeated experiment command, add a `mise` task if the command is
likely to be reused or compared later.

## Experiment Command Pattern

For one-off experiments, prefer a small script plus an explicit command recorded
in the wiki or README.

```sh
uv --exclude-newer 2026-05-21T00:00:00Z run SCRIPT_OR_ENTRYPOINT INPUT -o OUTPUT
```

For repeated experiments, wrap that command in `mise.toml`, then record the
`mise run ...` invocation in the experiment notes.

## Related Pages

- [Project purpose](./project-purpose.md)
- [Experiment knowledge workflow](./experiment-knowledge-workflow.md)
