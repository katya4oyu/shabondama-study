---
title: Project Purpose
created_at: 2026-05-21
updated_at: 2026-05-21
status: active
kind: concept
---

# Project Purpose

`shabondama-study` is a study repository for finding practical ways to detect
and track soap bubbles in images and videos.

It is not a general-purpose library. The repository is a working area for trying
image processing algorithms, inference models, capture conditions, and
post-processing, then keeping the results reproducible and comparable.

## Research Goal

The main goal is to find lightweight methods that can run on Apple Silicon Macs,
especially an 8GB-class low-memory MacBook.

The main machine can be an M4 Pro / 48GB Mac mini, and heavy methods may be used
as upper-bound comparisons. A method is more valuable here when it is simple,
reproducible, and realistic on the low-memory target.

## What Matters

- Stable bubble detection and tracking on still images and short videos.
- Reproducible experiments with preserved inputs, commands, parameters, and
  outputs.
- Comparable results across algorithms and preprocessing choices.
- Failed experiments that explain what did not work.
- Practical runtime and memory behavior on the target machines.

## What Does Not Matter Yet

- Clean public APIs.
- Early abstraction.
- Shared algorithm frameworks or compatibility layers between experiments.
- Packaging the code as a reusable library.
- Judging an approach from one successful run.

## Related Pages

- [Experiment knowledge workflow](./experiment-knowledge-workflow.md)
- [Toolchain and task workflow](./toolchain-and-task-workflow.md)
