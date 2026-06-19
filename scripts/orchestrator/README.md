# Orchestrator Scripts

This directory contains helper tools for the AI DevOps Orchestrator workflow.

## Current tool

### `collect_validation_snapshot.py`

Collects a read-only validation snapshot for review bundles.

It can collect:

- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- current branch
- current HEAD
- optional Python syntax validation for specified files
- forbidden-path change flags

The Python validation compiles source text in memory and does not write `.pyc` files.

Example:

```bash
python3 scripts/orchestrator/collect_validation_snapshot.py \
  --python-file analysis/strategy_ranking_engine.py \
  --pretty
```

## Safety boundaries

These scripts must remain read-only unless a future task explicitly expands scope after review.

Current scripts must not:

- Run `python3 main.py`.
- Run formal pipelines.
- Run backtests.
- Run migrations.
- Send LINE messages.
- Modify SQLite databases.
- Modify `.env`, credentials, tokens, or API keys.
- Modify cron.
- Commit, push, reset, checkout, or delete files.
- Place orders or trigger production side effects.
