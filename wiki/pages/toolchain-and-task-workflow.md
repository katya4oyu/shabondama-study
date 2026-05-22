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

This page is based on uv's official documentation and local command
verification. When uv behavior is unclear, follow
[Evidence-based agent workflow](./evidence-based-agent-workflow.md) before
changing project policy.

The project sets a fixed dependency-resolution cutoff in `pyproject.toml`:

```toml
[tool.uv]
exclude-newer = "2026-05-21T00:00:00Z"
```

Normal runs should use the committed lockfile:

```sh
uv sync --locked
uv run --locked detect-bubbles data/images/sample.jpg
```

Use normal `uv add` or `uv lock` commands when adding, upgrading, or otherwise
resolving dependency versions; the cutoff comes from `[tool.uv]`.

```sh
uv add PACKAGE
uv lock
```

The cutoff reduces exposure to very recent malicious or broken package releases.
The date is a project policy timestamp, not "the current time on every run".
Keep it fixed for a dependency decision, and bump it intentionally when updating
dependencies.

When using a relative duration such as `1 week`, uv resolves it to a concrete
timestamp during dependency resolution and stores that timestamp in `uv.lock`.
This project uses an absolute timestamp to make the policy explicit.

Direct dependencies are pinned in `pyproject.toml`, and `uv.lock` should be kept
with the repository.

Run Python entry points through `uv run --locked` when calling them directly:

```sh
uv run --locked detect-bubbles data/images/sample.jpg
```

## mise Tasks

Prefer `mise` for common project actions because it preserves command spelling
and cutoff behavior.

Current tasks:

- `mise run sync`: install dependencies from the committed lockfile.
- `mise run audit`: run `pip-audit` through `uv` without changing the lockfile.
- `mise run check`: run repository checks.
- `mise run detect -- data/images/sample.jpg`: run the current still-image bubble
  detector.

When adding a repeated experiment command, add a `mise` task if the command is
likely to be reused or compared later.

## Experiment Command Pattern

For one-off experiments, prefer a small script plus an explicit command recorded
in the wiki or README.

```sh
uv run --locked SCRIPT_OR_ENTRYPOINT INPUT -o OUTPUT
```

For repeated experiments, wrap that command in `mise.toml`, then record the
`mise run ...` invocation in the experiment notes.

## Related Pages

- [Project purpose](./project-purpose.md)
- [Experiment knowledge workflow](./experiment-knowledge-workflow.md)

## Official References

- [uv: Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [uv: Resolution](https://docs.astral.sh/uv/concepts/resolution/)
- [uv: CLI reference](https://docs.astral.sh/uv/reference/cli/)
