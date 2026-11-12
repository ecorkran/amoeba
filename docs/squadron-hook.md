---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: How Squadron's pause command is wired to amoeba handle_pause, and what the hook needs.
dateCreated: 20261110
dateUpdated: 20261112
status: complete
---

# Squadron hook

When a run stops on an agent's question, Squadron can start a command. `amoeba
handle_pause <run_id>` is that command: it answers the question from the member's
committed rules, plan and PM precedent and resumes the run, or records the question as
waiting on the PM. This file says what the wiring must satisfy. The CLI is in
`cli-contract.md`.

## What to configure

- **The command.** Configure `amoeba handle_pause <run_id>`, run in the run's own
  directory. Squadron supplies both the run id (as the command's last argument) and the
  directory (Squadron #302, `pipeline.on_pause_command`). The configuration line:

  ```bash
  sq config set pipeline.on_pause_command "amoeba handle_pause"
  ```

  Squadron splits the value like a shell line and runs it without a shell, so `amoeba`
  must be on the `PATH` the pausing `sq run` has.
- **User-level or per-project.** The line above writes the user-level config
  (`~/.config/squadron/config.toml`), configured once. A pause in a repo outside any
  program then skips as `not_a_project` or `not_in_program`. To hook only some repos,
  run `sq config set --project pipeline.on_pause_command "amoeba handle_pause"` from
  each one instead; that writes the repo's `.squadron.toml`.
- **Which repos.** Only repos in a program need the hook. A repo that is not a Context
  Forge project, or is in no program, is skipped by `handle_pause` itself
  (`not_a_project`, `not_in_program`).
- **The opt-out.** A run started with `sq run --no-pause-hook` does not start the
  command. A PM who watches a run and will answer it personally passes this flag. Amoeba's
  own answering runs always pass it (`PAUSE_COMMAND_OPT_OUT_FLAG` in
  `operations/answering_run.py`); a pause that does reach `handle_pause` from an
  answering run is skipped as `answering_run`.
- **A hand call.** Run by hand, `amoeba handle_pause <run_id>` must run in the run's own
  checkout. For a run started on `sq` 0.24.24 or later the run file records where the
  run started, and a call from any other directory is skipped as `wrong_checkout`
  (the detail names both directories) and writes nothing. For a run started on an older
  `sq` nothing confirms the directory, so a call from another directory resumes the run
  there; the result's `checkout` field says where the question was claimed.
- **The environment.** The hook's environment must reach `sq`, `cf`, `git` and the
  model credentials the answering pipeline uses: `handle_pause` starts the answering
  run and the resume as children that inherit it.

## What a missed hook looks like

A pause for which the hook never ran leaves no row. `amoeba status` lists such pauses
as `unhandled`; calling `amoeba handle_pause <run_id>` from the run's checkout handles
one late.

A hook that ran and did nothing, or failed, leaves a line: every `handle_pause` call is
appended to `<state home>/logs/calls/<UTC date>.jsonl`, an error exit and a `ConfigError`
included (format in `cli-contract.md`). `status` shows the newest line for each
`unhandled` or `claim_stale` run as `last_call`, which says why the hook missed.
