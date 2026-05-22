# shabondama-study

シャボン玉の検出・トラッキングを試すための実験リポジトリです。

汎用ライブラリではありません。小さなスクリプトを書き、試し、結果と知見を `wiki/` に蓄積していきます。

## Quick Start

```bash
mise run sync
```

静止画の簡易検出:

```bash
mise run detect -- data/images/sample.jpg
```

直接 `uv` で実行する場合:

```bash
uv run --locked detect-bubbles data/images/sample.jpg -o data/outputs/sample-detected.png
```

## Project Notes

- 目的と非目標: [wiki/pages/project-purpose.md](wiki/pages/project-purpose.md)
- `uv` / `mise` の使い方: [wiki/pages/toolchain-and-task-workflow.md](wiki/pages/toolchain-and-task-workflow.md)
- 実験ワークフロー: [wiki/pages/experiment-knowledge-workflow.md](wiki/pages/experiment-knowledge-workflow.md)
- wiki の入口: [wiki/index.md](wiki/index.md)

## Layout

- `src/shabondama_study/`: Python code
- `data/images/`: input images
- `data/outputs/`: generated outputs
- `wiki/`: experiment notes and reusable project knowledge
