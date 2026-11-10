---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: How Squadron's pause command is wired to amoeba handle_pause, and what the hook needs.
dateCreated: 20261110
dateUpdated: 20261110
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
  directory. Squadron supplies both the run id and the directory (Squadron #302,
  `pipeline.on_pause_command`). The exact configuration line is added with #302's form
  when the scenario A trial (slice 225) wires a real repository (amoeba#35).
- **Which repos.** Only repos in a program need the hook. A repo that is not a Context
  Forge project, or is in no program, is skipped by `handle_pause` itself
  (`not_a_project`, `not_in_program`). A run started with the opt-out
  (`sq run --no-pause-hook`) is left alone: Amoeba's own answering runs always pass it,
  and a pause that does reach `handle_pause` from an answering run is skipped as
  `answering_run`.
- **A hand call.** Run by hand, `amoeba handle_pause <run_id>` must run in the run's own
  checkout. Squadron records nothing that confirms the directory until it adds the
  run's working directory to `sq runs wait --json` (see the `params` and
  `execution_mode` request on `ecorkran/squadron`); until then a call from another
  directory resumes the run there. The result's `checkout` field says where the
  question was claimed.
- **The environment.** The hook's environment must reach `sq`, `cf`, `git` and the
  model credentials the answering pipeline uses: `handle_pause` starts the answering
  run and the resume as children that inherit it.

## What a missed hook looks like

A pause for which the hook never ran leaves no row. Slice 224's `status` lists such
pauses; calling `amoeba handle_pause <run_id>` from the run's checkout handles one
late.
