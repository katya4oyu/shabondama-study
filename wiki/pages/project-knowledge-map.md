---
title: Project Knowledge Map
created_at: 2026-05-21
updated_at: 2026-05-21
status: draft
kind: concept
---

# Project Knowledge Map

Use this page as the short route into the project's durable docs, wiki routes,
local issues, recurring failure histories, and high-signal search recipes.

## Durable Docs

- [Repository README](../../README.md): durable project purpose, setup policy,
  directory layout, and the current first experiment.
- [mise tasks](../../mise.toml): repeatable task definitions.
- [Python project config](../../pyproject.toml): dependencies and entry points.

## Wiki Routes

- [Project purpose](./project-purpose.md): research goal and scope.
- [Evidence-based agent workflow](./evidence-based-agent-workflow.md): how to
  ground tool, dependency, and correction work in current evidence.
- [Toolchain and task workflow](./toolchain-and-task-workflow.md): `uv`, `mise`,
  and command recording conventions.
- [Experiment knowledge workflow](./experiment-knowledge-workflow.md): how to
  turn scripts and runs into reusable knowledge.

## Bubble Detection Experiment Pages

- [Bubble detection test assets](./bubble-detection-test-assets.md): licensed image set, scope classification, smoke bubble asset acquisition.
- [HoughCircles tuning Phase 1](./hough-tuning-phase-1.md): param2/NMS sweep results, Phase 1 gate outcome.
- [Alternative detectors Phase 2](./alternative-detectors-phase-2.md): EXP-06〜10 results, iridescence mask, structural limits of transparent object detection.
- [Realtime pipeline and Rust](./realtime-pipeline-and-rust.md): recommended real-time pipeline for smoke bubbles, speed estimates, Rust migration plan.

## Search Recipes

```sh
rg -n "term|failure|experiment|decision" wiki/pages README.md mise.toml pyproject.toml
```

## Repeated Mistakes

- Add links to failure histories, regressions, or reflections as they appear.
