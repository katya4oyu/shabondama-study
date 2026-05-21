---
title: Experiment Knowledge Workflow
created_at: 2026-05-21
updated_at: 2026-05-21
status: active
kind: workflow
---

# Experiment Knowledge Workflow

This project should grow knowledge through small executable experiments, not
through one-off conclusions.

The experiment loop should follow the repository purpose in
[Project purpose](./project-purpose.md) and use the command conventions in
[Toolchain and task workflow](./toolchain-and-task-workflow.md).

## Default Loop

1. Write or update a focused script for one hypothesis.
2. Run it with `uv` or a `mise` task against known input data, or document why
   it was not run.
3. Save outputs under `data/outputs/` or another documented location.
4. Record reusable findings in the wiki.
5. Link the finding so future agents can discover it.

## What To Record

- Script path or command.
- Input path, source, and license when relevant.
- Important parameters and preprocessing.
- Machine used, especially whether it ran on an 8GB-class Apple Silicon Mac.
- Runtime, memory notes, input resolution, and output location when available.
- What worked, what failed, and the next hypothesis.

## Script Practice

Prefer one small script per hypothesis. It is acceptable for scripts to be
disposable, but the inputs, outputs, command, parameters, and dependency state
must be recoverable later.

If a script becomes a repeated comparison target, add or update a `mise` task so
the exact command is easy to rerun.

## Shared Code Bias

Avoid turning experiments into a framework. Each new script may test a different
algorithm, preprocessing path, model, or output shape, so compatibility pressure
between scripts is usually a cost.

Shared code should stay at the utility level: small file handling, logging,
timing, simple drawing helpers, or other operations that have been copied many
times and are independent of the algorithm being tested.

Do not extract core algorithm logic, experiment structure, or adapter layers just
because two scripts look similar. Prefer local duplication until the repeated
piece is proven boring and stable.

## Link Rule

Do not create a page that has no incoming route. A new experiment page must be
linked from [Project Wiki Index](../index.md) or from another already-linked page
in the same change.

If a wiki page was useful, make it easier to find. If it was misleading or stale,
fix the page, nearby links, or the index route before finishing the task.

## Research Bias

Prefer lightweight methods that can plausibly run on an 8GB-class Apple Silicon
Mac. Heavy models can be tested as upper-bound comparisons, but their findings
should explicitly state whether they are viable on the low-memory target.
