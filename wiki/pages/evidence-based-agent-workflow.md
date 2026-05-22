---
title: Evidence-Based Agent Workflow
created_at: 2026-05-21
updated_at: 2026-05-21
status: active
kind: workflow
---

# Evidence-Based Agent Workflow

Work in this repository should be grounded in current evidence, not in a
language model's remembered approximation of how a tool or library works.

## Operating Principle

When a task depends on tool behavior, dependency behavior, file format details,
external APIs, or current project conventions, establish the facts first:

- Read the relevant local files.
- Run the local command help or a small verification command.
- Check official documentation for behavior that may change across versions.
- Record durable findings in the wiki when they should affect future work.

The goal is not merely to avoid mistakes. The goal is to make the next decision
better grounded than the previous one.

## Correction Loop

When a user points out a mistake, identify the deeper reason before patching the
surface symptom.

1. State what assumption was weak.
2. Verify the behavior with local commands or official references.
3. Update code or docs based on the verified behavior.
4. Preserve the operating lesson in the wiki if it can prevent repeated errors.

For example, the `uv` workflow should be based on uv's current official
reference and local command behavior, not on remembered package-manager patterns.

## Evidence Levels

- Strong: repository files, successful local commands, official documentation.
- Useful but incomplete: local `--help`, lockfile contents, package metadata.
- Weak: memory, generic experience with similar tools, plausible command names.

Prefer strong evidence for project policy, dependency management, publishing,
security-sensitive choices, and anything that future experiments will repeat.

## Related Pages

- [Toolchain and task workflow](./toolchain-and-task-workflow.md)
- [Experiment knowledge workflow](./experiment-knowledge-workflow.md)
- [Wiki maintenance feedback loop](./wiki-maintenance-feedback-loop.md)
