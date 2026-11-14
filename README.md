# Amoeba: a tool that answers a paused run's first-level questions and keeps the record

Amoeba is a tool that agents and pipelines call. When a Squadron run pauses on a question, Amoeba answers it from the project's own rules, plan and the PM's earlier answers when those settle it, and records every answer and every decline, across a program of repos (a group of related repos). Questions those sources do not settle wait for the PM. It has no process of its own, and Squadron never needs it.

## For agents

If you are an agent session, use the `amoeba-mcp` server (`docs/mcp-server.md`) or the `amoeba` command with `-j`. You want it when the PM asks what is waiting, wants to answer a waiting question, wants to know what was decided while away, or wants a repo registered. Start with `list` (what needs the PM), then `answer` with a decision the PM actually gave, never one you composed. The server's own instructions carry the same map of tools.

## What exists now

The `amoeba` command, backed by one SQLite store. Its commands (`docs/cli-contract.md`) are `add`, `rm`, `list`, `handle-pause`, `answer`, `dismiss`, `retract`, `status`, `decisions` and `mark-read`. Each prints text for a person and, with `-j`, the JSON result an agent reads. `amoeba add` registers a repo with no other flag; `amoeba list` shows what needs you and what is registered. A member reads rules files with no setup (`docs/rules.md`). There is no resident process: each command is a short run, and Squadron never needs Amoeba.

- `amoeba.answering`: the answering pipeline (`answering.yaml`), the passage cutting and citation check, the six-check decision on whether an answer stands, and the answer screen.
- `amoeba.upstream`: bounded readers of what other tools say (`cf`, `git`, `sq`), and the argv for starting and resuming an `sq` run.
- `amoeba.store`, `amoeba.operations`, `amoeba.cli`: the store and its migrations, the operations, and the command line.
- `amoeba.mcp`: `amoeba-mcp`, the same operations as MCP tools for an agent session (`docs/mcp-server.md`: install, register, timeouts).

## Where things live

- **Config home**, `~/.config/amoeba/`: `config.yaml`, the one file you edit (`docs/config-contract.md`).
- **State home**, `~/.local/state/amoeba/`: everything Amoeba writes. The store `amoeba.sqlite3`, `answering/` scratch, and `logs/` (answering, resume, `calls/<date>.jsonl`). Old scratch and logs are pruned after `prune_after_days`; the store's rows are kept.
- `$AMOEBA_HOME`, when set, is both homes. `XDG_CONFIG_HOME` and `XDG_STATE_HOME` are ignored.
- An install from before slice 228 kept its state in the config home. The first command moves it, once (`docs/store-contract.md`, "Moving a pre-228 install").

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
