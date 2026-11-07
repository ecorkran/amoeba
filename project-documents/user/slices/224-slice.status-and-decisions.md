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
- **`ecorkran/squadron#303`** (open on 20261107): see D1.
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
- Called without `--all`, relying on the default to list every running and paused run. The fixture task records an older paused run and one from another directory. If the default leaves either out, `run_list.py` passes `--all` and drops completed runs itself. A run absent from the listing has finished or is gone.
- **Time bound.** `sq` runs with the timeout `deps` passes to `poll_run`. `cf` calls go through `run_cf` with its existing timeout. `project_of` calls run one after another, so a whole `status` call takes at most the `sq` timeout, plus one `cf` timeout for names, plus one `cf` timeout per distinct run directory. An `sq` or names timeout is exit 3. A `project_of` timeout is a `lookup_failed` run (D4).
- A non-zero exit, non-JSON output or a missing field is a `RunListProblem` quoting the output head, raised as `SquadronError` (exit 3). The message says `status` needs Squadron with #303.
- **Waits on #303.** Code and tests are written now against #303's proposed fields (run id, pipeline, status, working directory, the `sq runs wait --json` checkpoint, `null` directory for older run files), using a fake `sq`. The slice is not complete until #303 lands, its real output is recorded in `tests/fixtures/squadron/runs_list/`, and the parser passes on it. Different landed names change only `run_list.py` and its fixtures. If #303 has not landed by that task, it gets a `BLOCKED:` line.

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

- `None` (pre-#303 run file): `unplaced_runs`, reason `no_directory`.
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
unplaced_runs: [{run_id, status, reason}]
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

## Provides to Other Slices

- **225:** `decisions` records (`answered_by`, `prior_answer_seq`, `based_on`, `resume`) and `status`'s `waiting_on_pm` (`waiting_reason`, `run_state`) and `pause` classes. Together they cover every question sent to the PM: answered ones in `decisions`, unanswered ones, abandoned included, in `waiting_on_pm`.
- **226:** the three operations and their models, wrapped under the same names, and `next` entries whose `directory` MCP passes as `handle_pause`'s `cwd`.

## Verification Walkthrough

Needs Squadron with #303 and slices 222 and 223. Uses a test home so the real store is untouched. Before #303, `amoeba status` exits 3 with a `SquadronError` naming `sq runs list --json`.

1. **Set up**, in a throwaway worktree of the amoeba repo:
   ```bash
   export AMOEBA_HOME=$(mktemp -d)
   # write $AMOEBA_HOME/config.yaml from the example in docs/config-contract.md
   amoeba set_up --file - <<'EOF'
   program: trial
   members:
     - rules_paths: [CLAUDE.md]
   EOF
   ```
   Expect `applied`.
2. **Missed hook.** With no hook configured, run 223's live fixture pipeline (`tests/live/pause/`) with `sq run` until it pauses on its question. `amoeba status` shows the run with `pause: unhandled` and `next: {operation: handle_pause, run_id: …, directory: <worktree>}`.
3. **Catch up.** From that directory, `amoeba handle_pause <run_id>` gives `resumed`. `amoeba status` no longer shows the run as `unhandled`.
4. **Decisions.** `amoeba decisions` shows one `answerer` record with cited passages, check verdict, `resume.outcome: resumed`, and a numeric `read_through`.
5. **Mark read.** `amoeba mark_read --through <read_through>` gives `moved`. `amoeba decisions` then shows no records and `read_through: null`. `amoeba mark_read --through 999999` exits 1 with `beyond_last_record`.
6. **Waiting on the PM.** Run a pause the rules don't settle so `handle_pause` declines it. `amoeba status` lists it under `waiting_on_pm` with its reason and `next: {operation: answer, …}`. After `amoeba answer <run_id> --text "…"`, `amoeba decisions` shows a `pm` record whose `based_on.waiting_reason` is that reason.
7. **Scope.** From a directory in no program, `amoeba status` lists every program. `amoeba status --program nope` exits 1 with `unknown_program` and the known ids.

## Development Order

1. Extract `classify_pause`, with 223's tests passing unchanged.
2. `decisions`, `mark_read`, `project_names` and the schema test. None needs #303.
3. `run_list.py` and `status` against fixtures in #303's proposed shape.
4. After #303: record real fixtures, adjust `run_list.py` to the landed names, and run the walkthrough.
