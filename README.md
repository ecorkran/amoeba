# Amoeba: a tool that answers a paused run's first-level questions and keeps the record

Amoeba is being rebuilt as a tool that agents and pipelines call. When a Squadron run pauses on a question, Amoeba will answer it from the project's own rules, plan and the PM's earlier answers when those settle it, and record every answer and every decline, across a program of repos. It has no process of its own, and Squadron never needs it.

## What exists now

A library, and no command. The slice plan builds the rest on top of it.

- `amoeba.answering`: the answering pipeline (`answering.yaml`), the passage cutting and citation check, the six-check decision on whether an answer stands, and the answer screen.
- `amoeba.upstream`: bounded readers of what other tools say (`cf`, `git`, `sq runs wait --json`), and the argv for starting and resuming an `sq` run.

There is no store, no tick and no resident process. The old supervisor was cut in slice 221.

## Where the design lives

- Concept: `project-documents/user/project-guides/000-concept.amoeba.md`
- Architecture: `project-documents/user/architecture/220-arch.program-tool.md`
- Slice plan: `project-documents/user/architecture/220-slices.program-tool.md`
- The code audit that decided what stayed: `project-documents/user/analysis/220-analysis.code-audit.md`

## Checks

```
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

The live tier runs the real shipped pipeline through `sq` with real models, so it spends money and is never part of a bare `uv run pytest`. It needs `sq` and `cf` on `PATH`, a provider key in the shell, and these variables, which have no defaults:

- `AMOEBA_LIVE_ANSWER_MODEL`: the Squadron model alias for the answer step
- `AMOEBA_LIVE_CHECK_MODEL`: the alias for the check step
- `AMOEBA_LIVE_MAX_COST_USD`: the cost cap of one run, above zero

```
uv run pytest tests/live/answering
```
