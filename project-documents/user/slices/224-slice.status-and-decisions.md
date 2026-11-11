---
docType: slice-design
slice: status-and-decisions
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 223-slice.pause-handling
interfaces:
- 225-slice.scenario-a-trial
- 226-slice.mcp-server
dateCreated: 20261107
dateUpdated: 20261107
status: not_started
---

# Slice Design: Status and Decisions

## Overview

The read side of scenario A, and the CLI part of scenario C. Three operations:

- **`amoeba status`**: per member, running and paused runs, why each paused run stopped, questions waiting on the PM, answers not resumed, and missed hooks. Each actionable item names the operation that handles it.
- **`amoeba decisions`**: recorded answers since the PM's marker or a given time, with who answered and from what.
- **`amoeba mark_read --through <seq>`**: moves the PM's marker forward to the last record the caller saw.

It also moves 223's pause checks into one shared `classify_pause`, and adds the schema test 222 D3 assigned here.

Effort: 3/5.

## Scope

**Excluded:**

- Store migrations. 222 and 223 already hold everything read here, `pm_marker` included.
- Slice state. `status` shows a question's stored `slice_label` and nothing from Context Forge's slice status.
- Writes, apart from `mark_read` moving `pm_marker`.
- 223 D3's `wrong_checkout` skip, deferred to amoeba#37. Until then `docs/squadron-hook.md` keeps 223's warning that a hand call must run in the run's own checkout.
- MCP (226), notifications, and closing stale question rows (amoeba#36, D4).

## Dependencies

- **Slice 223:** question and answer rows and their reads, `handle_pause`, `answer`, `run_file.read_run_facts`, `poll_run` and its checkpoint parser, `answering_dir()`, `answering_wait_seconds`, and the `deps` bundle.
- **Slice 222:** the store, config, `resolve_member`, `project_of`, `run_cf`, and the exit-code constants and typed errors.
- **`ecorkran/squadron#303`:** shipped in `sq` 0.24.24 (checked 20261108); see D1.
- **The slice 220 audit** (`user/analysis/220-analysis.code-audit.md`): read its Verdicts rows for `inspection/`, `program/` and `cli/`, its Dependencies rows for `program/members.py`, `cli/main.py` and `process/sq_outcome.py`, and its Differences from the architecture. "Audit items" below settles what lands on this slice. `inspection/` is deleted whole; `inspection/questions.py` is only a column reference, so every `status` and `decisions` query here is new, written on the new store.
- **Context Forge 0.19.26:** `cf list projects --json` prints `{id, name, projectPath?, fileSlice, isActive}`. `projectPath` is missing on some entries.

## Components

```
src/amoeba/
├── operations/
│   ├── pause_class.py      # classify_pause() (D3)
│   ├── status.py           # status(), StatusResult (D2, D4, D8)
│   ├── decisions.py        # decisions(), DecisionsResult (D5)
│   ├── mark_read.py        # mark_read() (D7)
│   └── handle_pause.py     # (223) now calls classify_pause
├── store/
│   ├── questions.py        # (223) + open_questions(member_ids)
│   └── decisions.py        # answers_since(), read_marker(), advance_marker()
├── upstream/
│   ├── squadron/run_list.py       # list_runs() (D1)
│   └── context_forge/projects.py  # project_names() (D6)
└── cli/main.py             # + status, decisions, mark_read
```

Imports stay `cli → operations → store, config, upstream`. No subprocess runs inside a store transaction: `status` reads the store first, then calls `sq` and `cf`. Every vocabulary (`PauseClass`, unplaced reasons, rejection codes, `mark_read` outcomes) is a `StrEnum` defined once. Request models validate raw input inside the operation (222 D7). No new packages.

**`status` flow:** resolve scope (D2); one store read of programs, members and open questions; one `sq runs list --json` call; place runs (D4); classify each paused run (D3); join questions to runs by `run_id` (D4); one `cf list projects --json` call for names (D6); print `StatusResult` as JSON.

## Technical Decisions

### D1 — Reading runs: `sq runs list --json`, built to #303's proposed shape

- `run_list.list_runs(run) -> list[ListedRun] | RunListProblem`. A `ListedRun` holds `run_id`, `pipeline`, `status`, `working_directory` (absolute path or `None`) and `checkpoint` (`kind`, `paused_at`, `question`, or `None`), parsed by `poll_run`'s checkpoint parser so `paused_at` matches what 223 stores. An unknown status is kept as a raw string. No other module runs `sq runs list`.
- Called without `--all`, relying on the default to list every running and paused run. Observed 20261108 on `sq` 0.24.24: the default lists running, paused and failed runs and omits only completed ones, and every paused run that `--all` lists is also in the default. The fixture task still records an older paused run and one from another directory; if the default leaves either out, `run_list.py` passes `--all` and drops completed runs itself. A run absent from the listing has finished or is gone.
- `--json` prints the documents on stdout. `sq` may also print a warning on stderr (for example that some runs reference unavailable pipelines); that is not an error, and `list_runs` parses stdout only. The listing's `checkpoint` carries more fields than `ListedRun` keeps (`step`, `verdict`, `review_file`, …); the rest are ignored.
- **Time bound.** `sq` runs with the timeout `deps` passes to `poll_run`. `cf` calls go through `run_cf` with its existing timeout. `project_of` calls run one after another, so a whole `status` call takes at most the `sq` timeout, plus one `cf` timeout for names, plus one `cf` timeout per distinct run directory. An `sq` or names timeout is exit 3. A `project_of` timeout is a `lookup_failed` run (D4).
- A non-zero exit, non-JSON output or a missing field is a `RunListProblem` quoting the output head, raised as `SquadronError` (exit 3). The message says `status` needs Squadron with #303.
- **#303 has landed** (`sq` 0.24.24). Fixtures are recorded from real `sq runs list --json` output in `tests/fixtures/squadron/runs_list/`. Only if the installed `sq` lacks `runs list --json` does the slice fall back to hand-built stand-ins in #303's proposed shape (run id, pipeline, status, working directory, the `sq runs wait --json` checkpoint, `null` directory for older run files) with a fake `sq`; the slice is then not complete until real output is recorded and the parser passes on it. Different landed names change only `run_list.py` and its fixtures.

### D2 — Scope of `status`

| Called with | Scope |
|---|---|
| `--program P` | `P`. Unknown `P` is `rejected / unknown_program`, listing the known ids |
| no flag, inside a member | That member's program |
| no flag, elsewhere | Every program |

There is one PM, so "what is waiting on me" covers every program, and an MCP session started anywhere needs no input. A `ContextForgeError` while resolving the directory is an operational error and never widens the scope. Every member in scope is listed, even with nothing to show.

### D3 — One definition of what Amoeba handles

223 D3's run, row and run-file checks move to `classify_pause(outcome, question_row, latest_answer, run_facts, claim_age_limit, now) -> PauseClass`. `run_facts` is read only when needed.

| Class | When | `handle_pause` | `status` |
|---|---|---|---|
| `not_paused` | Outcome not `paused` | skip `not_paused` | not classified |
| `other_checkpoint` | Kind not `agent_question` | skip `not_agent_question` | stopped, with kind |
| `no_question_text` | No `question` or `paused_at` | skip | stopped, with reason |
| `prompt_only` | No row, `execution_mode` `prompt-only` | skip | stopped; its agent's |
| `unhandled` | No row, `execution_mode` `sdk` | new question | **missed hook** |
| `claim_live` | `claimed`, within limit | skip `already_claimed`, or 223 D7 poll | answering |
| `claim_stale` | `claimed`, past limit | 223 D7 | **stale claim** |
| `waiting_on_pm` | Row `waiting_on_pm` | skip | **waiting on the PM** |
| `answered_unresumed` | `answered`, latest outcome null or `refused` | resume | **answered, not resumed** |
| `settled` | Latest outcome `resumed` or `not_delivered` | skip | stopped, with outcome |

- `claim_age_limit` is `answering_wait_seconds`, as in 223 D7. `status` does not poll; `handle_pause`'s poll makes the final call.
- A `RunFileProblem` is not a class. `handle_pause` still raises it. `status` shows that run as `run_file_unreadable` with the problem text and goes on.
- The `answering_run` and membership checks stay in `handle_pause`, before `classify_pause`. `status` never sees answering runs (D4 skips their directories) and places runs by their own directory.
- 223's `SkipReason` values and tests are unchanged. One table test runs the same fixtures through both operations and asserts that every `unhandled` or `claim_stale` run in `status` is one `handle_pause` does not skip.

### D4 — Placing runs, and which questions are shown

**Runs**, by `working_directory`:

- `None` (run started before `sq` 0.24.24): `unplaced_runs`, reason `no_directory`, for a `paused` run only. Any other status with no directory is not listed (see Audit items).
- Directory missing (removed worktree): `unplaced_runs`, reason `directory_missing`. Checked before any `cf` call.
- Under `answering_dir()` (223 D12): not listed, no `cf` call. Scratch directories are never pruned, so without this skip each would cost a `cf` call.
- `project_of` gives `CFProjectNotFound`, or a project in no program in scope: not listed.
- `project_of` gives `CfCallFailed` or times out: `unplaced_runs`, reason `lookup_failed`, with the error text. The rest of `status` is shown, because one broken checkout must not hide the PM's waiting questions.
- A member in scope: listed under it.

`project_of` results are cached per directory for the call, so worktrees of one repo land on one member. `unplaced_runs` is not filtered by program, since the program can't be known.

**Questions** are joined to runs by `run_id` across the whole listing.

- Every `waiting_on_pm` question of a member in scope is listed, never dropped, with `run_state`: `at_pause` (`next` is `answer`), `moved_on` (detail gives the state, no `next`), or `not_listed` (no `next`). Stale rows stay until amoeba#36, built only if 225 shows they pile up.
- Claimed and answered questions appear only as their run's `pause` class. An answered question whose run moved on is in `decisions`.

### D5 — `decisions`

`decisions(store, document, *, deps) -> DecisionsResult`, with `DecisionsRequest(since?, program?)`.

- **Start.** Without `since`: `seq > last_seen_seq`. With `since`: `recorded_at >= since`. `since` is ISO-8601 with a UTC offset, converted to the store's UTC text form. No offset or unparsable is `rejected / malformed`.
- **Program.** Covers every program by default, from any directory. `program` narrows it; unknown is `rejected / unknown_program`. The caller's directory never narrows it, because the marker spans all programs.
- **Order.** Oldest first, by `seq`.
- **Each record:** `seq`, `recorded_at`, `program`, `member` (`{id, name}`), `run_id`, `paused_at`, `slice_label`, `question`, `answered_by` (`answerer` or `pm`), `answer`, and:
  - `prior_answer_seq`: newest earlier answer to the same question, or null. A PM answer after an automatic one is an override.
  - `based_on`: for `answerer`, the cited passages (`id`, `kind`, `source`, `date`, from `answers.cited` and the question's `passages`) and the check's verdict and reason from `evidence`. For `pm`, the question's `waiting_reason` and `waiting_detail`, or null if the PM answered first.
  - `resume`: `outcome` (or null), `detail`, `at`.
- **`read_through`:** the last listed `seq`, only when the listing started at the marker, was not narrowed, and is not empty. Otherwise null. So an agent can't mark records it was not shown.
- **`marker`:** the marker's value when read.
- 223's `answer` must keep `waiting_reason` and `waiting_detail` when it sets `answered` (223 D9 does). A test pins this.

### D6 — Member names

`status` and `decisions` show members as `{id, name}`. `projects.project_names(run) -> dict[str, str] | CfCallFailed` makes one `cf list projects --json` call per operation and reads only `id` and `name`. Names are never stored. A member id missing from the list is a `ContextForgeError` naming it. `CfCallFailed` is raised as `ContextForgeError` (exit 3).

### D7 — `mark_read`

`mark_read(store, document) -> MarkReadResult`, with `MarkReadRequest(through: int ≥ 0)`. In one `BEGIN IMMEDIATE` transaction:

- `through` above `MAX(answers.seq)` is `rejected / beyond_last_record`; the marker doesn't move.
- Otherwise `last_seen_seq = MAX(last_seen_seq, :through)`. Outcome `moved` or `unchanged`. The marker never moves backward, so concurrent calls leave the higher value.
- There is no "mark all". A record written after the caller's `decisions` call has a higher `seq` and stays unread.
- Result: `outcome`, `previous`, `current`.

### D8 — Result shapes and CLI

```
amoeba status [--program <id>]
amoeba decisions [--since <iso-8601>] [--program <id>]
amoeba mark_read --through <seq>
```

```yaml
programs:
  - program: trading
    members:
      - member: {id: project_17…, name: trading-core}
        runs:
          - {run_id, pipeline, status, working_directory,
             checkpoint: {kind, paused_at, question} | null,
             pause: <PauseClass | run_file_unreadable> | null,
             detail, next}
        waiting_on_pm:
          - {run_id, paused_at, question, slice_label, waiting_reason, waiting_detail, since,
             run_state, next}
unplaced_runs: [{run_id, status, reason, checkpoint_kind}]   # paused runs only; kind from the checkpoint
```

- Missed hooks and unresumed answers have no lists of their own; the `pause` class identifies them. For `answered_unresumed`, `detail` gives the resume outcome and reason.
- `next` is `{operation, run_id, paused_at?, directory?}` or null. For `unhandled`, `claim_stale` and `answered_unresumed` it is `handle_pause` with the run's `working_directory` as its `cwd`. For a waiting question `at_pause` it is `answer`.
- Exit codes (222's constants): `0` result; `1` rejected (`unknown_program`, `malformed`, `beyond_last_record`); `2` usage; `3` `SquadronError`, `ContextForgeError`, `ConfigError`, `AmoebaHomeError` or `StoreError`.
- Only `status` loads the config (for `answering_wait_seconds`).

Python entry points:

- `operations.status.status(store, config, document, *, directory, deps) -> StatusResult`
- `operations.decisions.decisions(store, document, *, deps) -> DecisionsResult`
- `operations.mark_read.mark_read(store, document) -> MarkReadResult`
- `deps` is 223's bundle plus `list_runs` and `project_names`.

### D9 — The store holds no mirrored state

`tests/store/test_schema_holds_no_mirrored_state.py` migrates a new store and pins the full `(table, column)` set from `PRAGMA table_info`. `docs/store-contract.md` lists each column under one reason: record, membership, settings, or the PM's marker. A new column fails the test until both are updated. `questions.checkout` and `questions.slice_label` are listed as record; the code never reads them as current state.

### D10 — Fixtures and tests

- **Real output** in `tests/fixtures/`: `cf list projects --json` from CF 0.19.26, with an entry lacking `projectPath`. After #303: `sq runs list --json` with a running run, a paused agent question, a paused run of another kind, a `null`-directory run, and D1's older and other-directory paused runs.
- **Unit tests** with fake `sq` and `cf`, as in 222 and 223: every `PauseClass` and D3's cross-check; D4's placement rules, including two worktrees on one member, `lookup_failed` with the rest shown, the scratch-directory skip, and each `run_state`; D2's three scopes; D5's starting points, narrowing and null `read_through` cases; D7's outcomes and concurrent calls; the `waiting_reason` pin; D9.
- 223's tests pass unchanged.

## Audit items

What the slice 220 audit (`user/analysis/220-analysis.code-audit.md`) leaves to this slice, and how it is settled.

- **Member readability: `status` does not report it.** The old `program/members.py` (readable or unreadable, with five reasons that all depend on deleted snapshots, links and per-project stores) is not reworked. `src/amoeba/program/` is deleted whole; if 221 left any of it, this slice deletes it. A member is a Context Forge project id (222), so there is nothing to read per member. What can fail is shown where it happens: a run's directory that cannot be placed is in `unplaced_runs` (`directory_missing`, `lookup_failed`), and an unreadable run file is `run_file_unreadable` (D3).
- **A member has no single checkout.** All worktrees of a repo are one member (222), so `status` shows no member checkout. Each run carries its own `working_directory`, and each `next` carries that run's directory. `questions.checkout` is a record of where a pause ran (D9), never a current location.
- **Matching a run to a member and detecting prompt-only runs.** `sq runs list --json` gives only `run_id`, `pipeline`, `status`, `working_directory` and `checkpoint` (checked 20261108 on `sq` 0.24.24); it has no run parameters and no `execution_mode`. Matching works with those fields: `working_directory`, then `project_of` (D4). `execution_mode` comes from 223's `run_file.read_run_facts`, read only for a placed paused `agent_question` run with no question row (D3). Run parameters are not needed here. Missing: a run with a `null` working directory cannot be placed, so a missed hook on a run from before `sq` 0.24.24 is never shown as `unhandled`. Real listing on the PM's machine: 84 runs, 83 with a `null` directory, and 1 paused `agent_question` run among them.
- **`unplaced_runs` lists paused runs only, with the checkpoint kind.** The same listing has 38 running and 18 failed runs with no directory; listing them would bury what the PM must act on, and none can be a missed hook. A paused run with no directory is listed with its `checkpoint_kind`, so an unplaced `agent_question` is visible. The reasons are unchanged.
- **CLI shapes and exit codes.** 223 D13 defines the `handle_pause` and `answer` shapes and the exit-code meanings (`0` result, `1` rejected, `2` usage, `3` operational, with the same error types); D8 gives the same table for the three read-side commands and takes 222's constants. One difference: `handle_pause` exits `0` for every outcome, while `status` and `decisions` exit `1` only when `rejected`. If 223's table changes, D8's follows it.
- **Question states and resume fields.** The reads use 222 and 223's names: `questions.state` is `claimed`, `answered` or `waiting_on_pm`; `answers.resume_outcome` is `resumed`, `refused` or `not_delivered`; `waiting_reason`, `waiting_detail`, `slice_label`, `passages`, `evidence`, `cited`, `resume_detail` and `resume_at` come from 222's baseline and 223's migration `002` (223 D10). The tasks read the real column names in the migrations first and use those over the design's.
- **Module homes.** Per 221, the `sq runs wait` reader is `upstream/squadron/run_outcome.py` (`poll_run`, checkpoint kinds, formerly `process/sq_outcome.py`) and the `cf` runner is `upstream/context_forge/cli_call.py` (`run_cf`, `CfCallFailed`). `run_list.py` sits beside the first, reuses its checkpoint parser and its `sq` executable constant, and imports nothing from `process/`.

## Provides to Other Slices

- **225:** `decisions` records (`answered_by`, `prior_answer_seq`, `based_on`, `resume`) and `status`'s `waiting_on_pm` (`waiting_reason`, `run_state`) and `pause` classes. Together they cover every question sent to the PM: answered ones in `decisions`, unanswered ones, abandoned included, in `waiting_on_pm`.
- **226:** the three operations and their models, wrapped under the same names, and `next` entries whose `directory` MCP passes as `handle_pause`'s `cwd`.

## Verification Walkthrough

Needs `sq` with `sq runs list --json` (`ecorkran/squadron#303`, shipped in 0.24.24; run on 0.24.26), `cf`, slices 222 and 223, and a model alias for the answering pipeline. All commands run from the repo root of the checkout under test. The store is a scratch home, so the real store is untouched. Without `sq runs list --json`, `amoeba status` exits 3 with a `SquadronError` naming `sq runs list --json`.

**Automated.** `tests/live/pause/test_status_walkthrough_live.py` runs steps 1 to 7 below with real `sq`, `cf` and models, in a throwaway member repo (its own Context Forge data directory and `AMOEBA_HOME`):

```bash
export AMOEBA_LIVE_ANSWER_MODEL=<alias> AMOEBA_LIVE_CHECK_MODEL=<alias> AMOEBA_LIVE_MAX_COST_USD=3
uv run pytest tests/live/pause/test_status_walkthrough_live.py
```

It passed on 20261111 (about 50 s). By hand, the same steps are:

1. **Set up.** In a throwaway git checkout registered with Context Forge (`cf init --lite --name <name>`):
   ```bash
   export AMOEBA_HOME=$(mktemp -d)
   # write $AMOEBA_HOME/config.yaml from the example in docs/config-contract.md,
   # with answer_model, check_model, max_cost_usd, answering_wait_seconds, resume_wait_seconds set
   amoeba set_up --file - <<'EOF'
   program: trial
   members:
     - rules_paths: [CLAUDE.md]
   EOF
   ```
   Expect `outcome: applied`.
2. **Missed hook.** Start the live pipeline with no pause hook: `sq run tests/live/pause/asks_question.yaml <model> --run-id <run_id> --no-pause-hook`, and wait until `sq runs wait <run_id> --timeout 0 --json` says `paused`. Then `amoeba status` prints `"outcome": "listed"` and, under the member, the run with `"pause": "unhandled"` and `"next": {"operation": "handle_pause", "run_id": "<run_id>", "paused_at": "<its paused_at>", "directory": "<the checkout>"}`.
3. **Catch up.** From that directory, `amoeba handle_pause <run_id>` prints `"outcome": "resumed"`. `amoeba status` no longer shows that pause as `unhandled`. **Caveat:** `asks_question.yaml` ends every step on a question, so the resumed run pauses again a few seconds later with a *new* `paused_at`. That second pause has no row and is `unhandled` in its own right: it is a new pause, not the original one, and `status` is right to show it. Check the original `paused_at` is not unhandled, or call `status` while the run is `running` (then `pause` is null).
4. **Decisions.** `amoeba decisions` prints one record with `"answered_by": "answerer"`, `based_on.cited` (one passage with `id`, `source`, `date`; `kind` is null for a file passage), `based_on.check_verdict: "yes"` with its reason, `"resume": {"outcome": "resumed", ...}`, and `"read_through": 1` (a number, the record's `seq`), `"marker": 0`.
5. **Mark read.** `amoeba mark_read --through <read_through>` prints `"outcome": "moved", "previous": 0, "current": 1`. `amoeba decisions` then prints `"records": []`, `"read_through": null`, `"marker": 1`. `amoeba mark_read --through 999999` exits 1 with `"rejection": "beyond_last_record"`.
6. **Waiting on the PM.** Start `tests/live/pause/asks_unsettled_question.yaml` the same way (a question about a logo colour that no rule settles). `amoeba handle_pause <run_id>` prints `"outcome": "waiting_on_pm"` with `waiting_reason: answerer_declined`. `amoeba status` lists it under the member's `waiting_on_pm` with that `waiting_reason`, `"run_state": "at_pause"` and `"next": {"operation": "answer", "run_id": "<run_id>", "paused_at": "<its paused_at>", "directory": null}`. After `amoeba answer <run_id> --text "Use teal."` (prints `recorded`, `resume.outcome: resumed`), `amoeba decisions` shows one record with `"answered_by": "pm"` and `based_on.waiting_reason` equal to the reason above.
7. **Scope.** From a directory in no program, `amoeba status` lists every program. `amoeba status --program nope` exits 1 with `"rejection": "unknown_program"` and `problems` naming the known ids (for example `known programs: trial`).

**Caveats found.**

- `amoeba status` lists the machine's real Squadron runs, so `unplaced_runs` shows every paused run with no placeable directory: a null `working_directory` (a run from before `sq` 0.24.24, 17 of the 32 paused runs on the PM's machine) or a removed worktree (`directory_missing`, for example the live tests' own throwaway members). It does not appear for a running, failed or completed run.
- `sq runs list --json` prints a warning on stderr when runs reference unavailable pipelines. It is ignored; stdout is parsed.
- A run's latest question row is used only when its `paused_at` equals the run's current checkpoint. A run that paused again after being answered is judged by its new pause.
- A cited passage's `kind` is `pm_answer` for a PM precedent and null for other passages: the store records no passage kind.

## Development Order

1. Extract `classify_pause`, with 223's tests passing unchanged.
2. `decisions`, `mark_read`, `project_names` and the schema test. None needs #303.
3. `run_list.py` and `status` against fixtures in #303's proposed shape.
4. After #303: record real fixtures, adjust `run_list.py` to the landed names, and run the walkthrough.
