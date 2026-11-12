---
docType: slice-design
slice: state-home-and-question-lifecycle
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 223-slice.pause-handling
- 224-slice.status-and-decisions
interfaces:
- 226-slice.mcp-server
- 227-slice.program-dependencies
dateCreated: 20261112
dateUpdated: 20261112
status: not_started
turns: 53
promptTokens: 5403347
cachedTokens: 5218143
cacheWriteTokens: 185120
completionTokens: 53771
durationSeconds: 602.3
costUsd: 3.600678
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.6006780000000007
    completionTokens: 53771
revision_number: 2
---

# Slice Design: State Home and Question Lifecycle

## Overview

Running 225 showed design holes that the Amoeba design rules (CLAUDE.md, "Amoeba Design Rules") now forbid. This slice fixes them:

- **State leaves `~/.config`.** `config.yaml` stays in `~/.config/amoeba/`. The store, `answering/` and `logs/` move to `${XDG_STATE_HOME:-~/.local/state}/amoeba/`. An existing store is moved by code on first use and checked before the old copy is deleted. `AMOEBA_HOME` still redirects everything to one directory for tests.
- **Every question has an exit.** A new `closed` state. `dismiss` closes a `claimed` or `waiting_on_pm` question with a reason. `status` and `handle_pause` close questions whose run has moved on or been deleted, recording the run's outcome. `retract` stops a PM answer being precedent. A PM answer resets the run's answer limit.
- **Set-up can undo itself.** `set_up` gains `remove` entries for members and pairs. It refuses to remove a member with open questions.
- **Everything written has a cleanup.** Answering scratch directories and logs of settled questions are pruned after a configured age. The new calls log is pruned the same way.
- **The hook leaves a trace.** Every `handle_pause` call is appended to a calls log (amoeba#34). A call from outside the run's recorded directory skips as `wrong_checkout` (amoeba#37).

Closes amoeba#34, #36 and #37. Effort: 4/5.

## Value

User value. The PM, or any agent acting for the PM, can clear a stuck or stale question with a command. Nothing is ever fixed by editing the store. Records whose run has gone close on their own, so `status` shows only what is actually waiting. A hook call that did nothing leaves a reason that can be read. State lives where state belongs, and nothing Amoeba writes grows without bound.

It also settles the home layout and the question states that 226 (MCP) and 227 (program dependencies) read.

## Technical Scope

**Included:**

- Split homes, legacy-store move, path rewrite and verify (D1, D2).
- Migration `003`: the `closed` state and its columns, answer retraction, resume start time, member removal (D3).
- The automatic close sweep in `status` and `handle_pause` (D4).
- The `dismiss` and `retract` operations and their CLI commands (D5, D6).
- The answer limit counted since the run's last PM answer (D7).
- `set_up` `remove` entries (D8).
- Pruning, with the `prune_after_days` config key (D9).
- The `wrong_checkout` skip (D10) and the calls log (D11).
- Changes to `status` and `decisions` output (D12), contract docs, and the PM's upgrade steps (D13).

**Excluded:** MCP (226). Scenario B operations (227). Sharing PM precedent across a program. Any watcher, timer or background process: every cleanup here runs inside an existing call.

## Dependencies

### Prerequisites

- **Slices 222, 223, 224 and 225 merged** on `main`. The live store at `~/.config/amoeba/` (schema version 2) is the real data the move must carry over.
- **Squadron 0.24.24 or later.** Checked on 0.24.27, 20261112: a schema-5 run file written by 0.24.24 or later has `working_directory`. Older schema-5 files have no such key (69 of 137 schema-5 files on the PM's machine). `sq runs list --json` and `sq runs wait --json` are unchanged from 224.
- No new packages. The move uses `sqlite3.Connection.backup`.

### Interfaces Required

- **222:** `config.home`, `Store.open`, `migrate`, `set_up` and its checks, `resolve_member`, the D9 exit codes.
- **223:** `handle_pause` and its eligibility checks (`pause_eligibility.py`), `answer`, `resume` (`TERMINATE_GRACE_SECONDS` in `processes.py`), `run_file.read_run_facts`, `automatic_answer_count`, `pm_precedent`, `record_resume`.
- **224:** `classify_pause`, `status` and its placement (`status_placement.py` skips run directories under `answering_dir()`), `status_waiting.py`, `decisions`, `poll_run`, `list_runs`, and the D9 schema pin test.

## Architecture

### Component Structure

```
src/amoeba/
├── config/
│   ├── home.py           # config_home(), state_home(), legacy_state_home(), calls_log_dir()
│   └── user_config.py    # + prune_after_days
├── store/
│   ├── schema/003_question_lifecycle.sql
│   ├── migrations.py     # foreign keys off around a migration, foreign_key_check before commit
│   ├── relocate.py       # copy_store(old, new, path_prefixes) -> verified copy
│   ├── vocabulary.py     # + QuestionState.CLOSED, ClosedReason
│   ├── questions.py      # + close_question, dismiss_question, open rows incl. answered-unresumed
│   ├── answers.py        # + retract_answer, mark_resume_started; limit count and precedent change
│   └── programs.py       # + remove_member, remove_pair; removed members filtered
├── operations/
│   ├── state_move.py     # prepare_state_home(layout)
│   ├── question_sweep.py # sweep_run(), sweep_scope() (D4)
│   ├── dismiss.py        # dismiss() (D5)
│   ├── retract.py        # retract() (D6)
│   ├── prune.py          # prune() (D9)
│   ├── calls_log.py      # append_call(), last_call() (D11)
│   ├── handle_pause.py   # + sweep_run, wrong_checkout, prune
│   ├── status*.py        # + sweep_scope, closed class, last_call, prune
│   └── set_up*.py        # + remove
├── upstream/squadron/run_file.py  # + RunFacts.working_directory
└── cli/main.py           # + dismiss, retract; prepare_state_home; calls log at the boundary
```

Import direction is unchanged: `cli → operations → store, config, upstream`. `store/relocate.py` takes both paths as arguments and imports nothing from `config`. Only `config/home.py` reads `AMOEBA_HOME`, `XDG_STATE_HOME` or `Path.home`. The 222 D10 AST test gains `XDG_STATE_HOME`.

### Data Flow

**Every CLI command** (and every 226 MCP call): config load, then `open_state_store(layout)` (D2), which moves legacy state and then calls `Store.open` (which migrates to `003`), then the operation.

**`handle_pause <run_id>`:** `poll_run` → `sweep_run` closes this run's open rows at other pauses (D4) → eligibility checks, with `wrong_checkout` after `prompt_only` (D10) → the 223 paths, unchanged apart from the limit count (D7) → `prune` (D9) → the CLI appends one calls-log line (D11), whatever the outcome or error.

**`status`:** store read → `sq runs list` → placement and `classify_pause` (with the `closed` class) → `sweep_scope` closes open rows of members in scope whose run is not at that pause, judged from the `--all` listing alone (D4) → waiting list built from what is still open → `last_call` for each `unhandled` or `claim_stale` run (D11) → `prune` → JSON with `closed_now`.

**`dismiss`, `retract`:** validate the request, then one `BEGIN IMMEDIATE` compare-and-set write. No subprocess.

### State Management

| Where | What | How it ends |
|---|---|---|
| `~/.config/amoeba/config.yaml` | The user config | A person edits it. Nothing else lives under `~/.config/amoeba/` |
| `<state>/amoeba.sqlite3` | Questions, answers, programs, members, pairs, releases, marker | Rows are the record and are kept. Bounded: one question row per real pause in a member, capped per run by `answer_limit` between PM answers |
| `<state>/answering/<id>/` | Scratch per answering run | Pruned once its question is settled, or it has no question row, and it is older than `prune_after_days` (D9) |
| `<state>/logs/answering/`, `logs/resume/` | Answering and resume logs | Same rule as scratch (D9) |
| `<state>/logs/calls/<YYYY-MM-DD>.jsonl` | One line per `handle_pause` call | Day files older than `prune_after_days` are deleted (D9) |
| `<state>/logs/` other files (226's `logs/mcp/`) | Logs of detached MCP calls | Deleted when older than `prune_after_days` (D9) |
| `~/.config/amoeba/` store, `answering/`, `logs/` | Legacy state | Moved and deleted by the first call after install (D2) |

`<state>` is `state_home()`. With `AMOEBA_HOME` set, `<state>` and the config directory are both `$AMOEBA_HOME`.

## Technical Decisions

### D1 — Two homes, one variable to redirect both
Status: decided

`config/home.py`:

- `config_home()`: `$AMOEBA_HOME` when set, else `~/.config/amoeba`. Holds `config.yaml` only. `XDG_CONFIG_HOME` is still not consulted (222 D1). The plan keeps the config at `~/.config/amoeba/`, and it is already the XDG default.
- `state_home()`: `$AMOEBA_HOME` when set; else `$XDG_STATE_HOME/amoeba` when that variable is set and non-empty; else `~/.local/state/amoeba`. An empty `XDG_STATE_HOME` counts as unset, as the XDG spec defines it. A relative value raises `AmoebaHomeError`. The spec says to ignore such a value, but the project forbids silent fallbacks.
- `store_path()`, `answering_dir()` and `logs_dir()` move under `state_home()`. `calls_log_dir()` is `logs_dir() / "calls"`. `config_path()` is under `config_home()`.
- `legacy_state_home()` returns `~/.config/amoeba` when `AMOEBA_HOME` is unset and that path differs from `state_home()`; otherwise `None`. Only the move (D2) and run placement (D12) use it.
- `amoeba_home()` is removed. Each caller asks for the home it means, so no code can put state in the config directory by accident.
- `squadron_runs_dir()` is unchanged. Squadron's own layout is not Amoeba's to move.
- A `StateLayout` value (state home, store path, answering dir, logs dir, legacy home or `None`) is built once by the CLI and passed down, so operations still take paths, not the environment.

Tests: the autouse `AMOEBA_HOME` fixture is unchanged, so every test still gets one throwaway directory. `tests/config/test_home.py` adds: `XDG_STATE_HOME` honored, empty treated as unset, relative rejected, `AMOEBA_HOME` overriding both, `legacy_state_home()` being `None` under `AMOEBA_HOME`.

### D2 — Moving the legacy state on first use
Status: decided

`operations/state_move.prepare_state_home(layout) -> MoveReport` runs inside `state_move.open_state_store(layout)`, the only function that opens the store: it moves, then calls `Store.open`. The CLI and 226's MCP layer open the store only through it. An AST test checks that no module under `src/amoeba` except `state_move.py` calls `Store.open`, and a CLI test runs every subcommand against a legacy home and checks the move happened. So no entry point can create an empty state-home store before the move. It does nothing when `layout.legacy_home` is `None` or holds none of `amoeba.sqlite3`, `answering/` or `logs/`. Steps 1–4 run only when the legacy `amoeba.sqlite3` file exists. With only directories left (a crash during step 5), the call goes straight to step 5.

1. **Lock the old store.** Open the legacy store read-write without create (an `sqlite3` URI with `mode=rw`, never `Store.open`, which would create a missing store), and take `BEGIN IMMEDIATE` on it, using the normal busy timeout. This keeps out any process still running old code, and a second new process wanting to move. Whoever loses the lock waits, then finds the move done. Old code's write transactions are short, so the wait normally ends well inside the timeout. If it doesn't, the call raises `StoreBusyError` (exit 3; for the hook, a calls-log line and a missed hook in `status`), nothing has been written, and the next call tries the move again.
2. **Copy.** If the new store does not exist, a leftover `amoeba.sqlite3.moving` from a crash inside this step is deleted first. Only the lock holder reaches this step, so the file is never another process's live copy. `store/relocate.copy_store` then copies the old one with `Connection.backup` into `amoeba.sqlite3.moving` in the state home. It then rewrites every `answers.resume_log` value that starts with the legacy home to the new state home. That column holds absolute paths (223 D10), and no other column holds a path under the home. A `sqlite3.Error` or `OSError` from the copy (a full disk, an I/O error) deletes the `.moving` file and raises `StoreRelocateError` naming the cause. The old store is untouched, and the next call tries again.
3. **Verify the copy.** `PRAGMA integrity_check` returns `ok`. The schema version matches. Every table's row count matches. `MAX(answers.seq)` matches. No `resume_log` still starts with the legacy prefix. On any mismatch, delete the `.moving` file and raise `StoreRelocateError` (a `StoreError`, so exit 3) naming the check. The old store is not touched.
4. **Place it.** Rename `.moving` to `amoeba.sqlite3` (atomic within one directory), then commit and close the old connection. Delete the old `amoeba.sqlite3` and its `-wal` and `-shm` files.
5. **Move directories.** Move each entry of the legacy `answering/`, `logs/answering/` and `logs/resume/` into the same place under the state home: first to `.<name>.moving` with `shutil.move` (which copies when the two homes are on different filesystems), then rename. A leftover `.<name>.moving` from a crashed move is removed and that entry moved again. Empty legacy directories are removed. `config.yaml` is never touched.

**Both stores exist** (a crash between steps 4 and the delete, or a process on old code wrote to the legacy path after the move): under the step 1 lock, compare as in step 3. If they are the same, delete the legacy store and continue with step 5. If they differ, the state-home store wins, because it is the only one current code writes, and `open_state_store` guarantees it was created by the move, never empty by accident. The legacy store (with its `-wal` and `-shm` files) is moved into the state home as `amoeba.sqlite3.legacy-<UTC stamp>`, never opened again, and the move continues with step 5. One stderr line names the set-aside file and both stores' row counts and `MAX(answers.seq)`, so whatever the old process wrote can still be read there. D9 prunes the set-aside file after `prune_after_days`. This only happens when an old install kept running after the upgrade, which is rare, so it gets a set-aside file rather than a merge.

`MoveReport` (moved store yes or no, entries moved) goes to stderr as one line when something moved. Tests use explicit throwaway paths for both homes and never `Path.home`. They cover: a fresh move with every row and `resume_log` checked, a crash after each step and inside step 2 (simulated by stopping there) followed by a clean rerun, a copy error, including a crash during step 5 with the legacy store already deleted (no legacy store is created), identical and differing double stores, a held legacy write lock, and a cross-filesystem-style move (by injecting the mover).

### D3 — Migration `003_question_lifecycle.sql`
Status: decided

Adding a state means changing `questions.state`'s `CHECK` list. 222 D3 limited later migrations to `ADD COLUMN`. The alternative, a `closed_at` column beside an unchanged `state`, would split one state across two columns that every reader has to combine. So `003` rebuilds `questions` once, using SQLite's documented procedure: create `questions_new` with the wider `CHECK` and the new columns, copy the rows, drop `questions`, rename. This is the one exception to the `ADD COLUMN` rule, and the migration's header comment says why. Later migrations go back to `ADD COLUMN`.

| Table | Change |
|---|---|
| `questions` | `state` `CHECK` gains `closed`. New nullable `closed_reason` (`CHECK` in `ClosedReason`: `dismissed`, `run_moved_on`, `run_gone`), `closed_detail` (the dismissal reason, or the run's outcome at closing), `closed_at` |
| `answers` | `retracted_at`, `retract_reason` (D6). `resume_started_at`, set just before a resume is spawned (D4) |
| `members` | `removed_at` (D8) |

- `migrate` sets `PRAGMA foreign_keys = OFF` before `BEGIN IMMEDIATE`, since the pragma does nothing inside a transaction. Before commit it runs `PRAGMA foreign_key_check`: any row raises `StoreCorruptError` and rolls back. It turns foreign keys back on after commit or rollback. This applies to every migration and changes nothing for `001` and `002`.
- `EXPECTED_SCHEMA_VERSION` becomes 3. The vocabulary pin test covers `ClosedReason` and the wider `QuestionState`. The 224 D9 schema pin test and `docs/store-contract.md` gain each column, all as "record" apart from `members.removed_at` ("membership").
- `answer` sets `answered` from any state, including `closed`, so a PM who dismissed by mistake answers instead. The `closed_*` columns stay as history, the way `waiting_reason` does (223 D9).

### D4 — The automatic close sweep
Status: decided

`operations/question_sweep.py` closes records whose run has left their pause. A question is open when it is `claimed` or `waiting_on_pm`, or `answered` with its latest answer's `resume_outcome` null or `refused`. Each close is a compare-and-set on the row's `state` and `updated_at`, or on the answer's `resume_outcome`. A concurrent `answer`, `dismiss` or settle therefore wins, and the sweep skips that row.

| Open record, run not at its pause | Action |
|---|---|
| `waiting_on_pm` | `closed`, reason `run_moved_on` or `run_gone`, `closed_detail` the run's state |
| `claimed`, `claimed_at` older than `answering_wait_seconds` | Same. A young claim is left alone, since its answering run may still settle |
| `answered`, latest answer unresumed, its newest of `recorded_at`, `resume_started_at` and `resume_at` older than `resume_bound_seconds(config, deps)` | Answer's `resume_outcome` set to `not_delivered`, detail the run's state. No new question state: this is 223 D8's own meaning of not delivered |

- **"Not at its pause"** means the run is paused at another `paused_at`, or is `running`, `completed` or `failed`. That is `run_moved_on`, with the state or later `paused_at` as detail. A run `sq` no longer knows is `run_gone`: `not_found` from `poll_run` in `handle_pause`, or absent from the `--all` listing in `status`.
- **`resume_bound_seconds(config, deps)`** is `resume_wait_seconds + RESUME_POLL_INTERVAL_SECONDS + 2 × <poll_run timeout> + 2 × TERMINATE_GRACE_SECONDS + BUSY_TIMEOUT_SECONDS`, defined once in `resume.py`. It is the longest a resume can take before recording its outcome (223 D8 steps 3–4). It counts the last poll in the wait loop, the SIGTERM grace and then the SIGKILL grace in `terminate_group`, the poll after the kill, and the store write. `resume.py` sets `resume_started_at` just before every spawn, so a retried resume in flight is never marked `not_delivered` under it.
- **`sweep_run(store, config, run_id, polled, now)`** runs in `handle_pause` right after `poll_run`, before eligibility (except that an answering run's id never has rows). It closes this run's open rows at any other `paused_at`, or all of them if the run is no longer paused. It needs no directory or member, because the run id and Squadron's answer settle it. So the hook at a run's next pause closes the question left at the last one, with nobody calling `status`.
- **`sweep_scope(store, config, rows, listed, deps, now)`** runs in `status` for open rows of members in scope. Every row is judged from the one listing `status` already makes, which `run_list.py` now takes with `--all`. Checked on `sq` 0.24.27, 20261112: the default listing held 8 of the 100 completed runs, and `--all` held all 100 plus every running, paused and failed run. So a run in the listing gives its state or later pause, and a run absent from it is `run_gone`. `status` drops completed runs from its per-member run lists, so what it shows is unchanged. The sweep adds no `sq` call and nothing to `status`'s time bound.
- No transaction is held across a subprocess. Both sweeps read, call `sq` (`sweep_run` reuses `handle_pause`'s poll), then write in one short transaction.
- **A failed sweep write never fails the call.** A `StoreBusyError` on the sweep's transaction is caught, with a comment saying why: a closure that lost a lock must not hide the PM's waiting list. The rows stay open and close at a later call. `status` still prints everything, with the rows shown as before the sweep and the error in a new `sweep_problem` field. `handle_pause` puts it in its calls-log line's `detail` and carries on. Any other `StoreError` stays exit 3, as 222 D9 defines.
- `status` now writes. 224 kept it read-only. The plan assigns this to `status` because a run that completes never fires the hook again, so `status` is the only call that sees it.

### D5 — `dismiss`
Status: decided

```
amoeba dismiss <run_id> [--paused-at <ts>] --reason <text>
```

`dismiss.dismiss(store, document) -> DismissResult`, with `DismissRequest(run_id, paused_at?, reason)` validated inside the operation (222 D7).

- **Find** as `answer` does (223 D9): by key, or the run's row with the latest `claimed_at`. No row: `rejected / no_such_question`.
- **Reason**, stripped and non-empty, else `rejected / malformed`. It is stored as `closed_detail`.
- **`claimed` or `waiting_on_pm`**: compare-and-set to `closed`, `dismissed`. Outcome `dismissed`. A run at the answer limit is `waiting_on_pm`, so it can be dismissed. An in-flight answering run for a dismissed claim settles into nothing, because 223's settle is `WHERE state = 'claimed'`. It is not killed: its cost cap and `answering_wait_seconds` bound it, and its scratch is pruned like any other (D9).
- **Already `closed`**: outcome `unchanged`, with the existing reason.
- **`answered`**: `rejected / not_open`. The detail says the answer was already given, and that `retract` stops it being precedent.
- The run is not resumed and stays paused in Squadron, where Squadron's own commands deal with it. `status` shows it with the class `closed` (D12) and no `next`. `handle_pause` skips it as `closed`.
- A dismissed question has no PM answer, so it is never precedent. `pm_precedent` also leaves out `closed` questions explicitly (D6), so this holds if a later change lets a closed question carry a PM answer.
- Exit 0 for `dismissed` or `unchanged`, 1 for `rejected`.

### D6 — `retract`
Status: decided

```
amoeba retract <answer_seq> --reason <text>
```

`retract.retract(store, document) -> RetractResult`, with `RetractRequest(answer_seq, reason)`. The PM gets the `seq` from `decisions`.

- No such answer: `rejected / no_such_answer`. An `answerer` answer: `rejected / not_a_pm_answer`, since automatic answers are never precedent. A blank reason: `rejected / malformed`.
- Sets `retracted_at` and `retract_reason`. Outcome `retracted`, or `unchanged` if it was already retracted.
- `pm_precedent` takes the newest PM answer per question, as now. A question gives no precedent when that answer is retracted or the question is `closed`. An older PM answer to the same question is not brought back: the PM replaced it, then retracted the replacement.
- The answer stays delivered and stays in `decisions`, with `retracted_at` and `retract_reason`. It still counts as the run's last PM answer for the limit (D7), because the run did receive it.
- **Undo:** a new `answer` to the same question becomes the newest PM answer and therefore the precedent. Its resume reports `not_delivered` if the run has left that pause.

### D7 — The answer limit counts since the last PM answer
Status: decided

`automatic_answer_count(transaction, run_id)` counts `answerer` answers for the run with `seq` greater than the run's newest `pm` answer `seq`, or all of them when there is none. Its SQL constant changes, and both callers (`pause_claim.start_new_claim` and `answers.settle_answered`) already use the function, so nothing else changes. A PM answer is the PM stepping in, so the run gets a fresh `answer_limit` of automatic answers. The limit still stops a run that keeps asking. A run at the limit sits as `waiting_on_pm / answer_limit_reached`, where `answer` (which skips the limit, 223 D9) and `dismiss` both work.

### D8 — `set_up` removal
Status: decided

```yaml
program: trading
remove:
  members: [trading-api]          # CF name or id
  pairs:
    - {provider: trading-data, consumer: trading-ui}
```

- **Members are soft-removed.** `members.removed_at` is set. Their question, answer and release rows reference the member, and they are the record. A removed member's pairs are deleted. A removed member is treated as not a member everywhere, enforced in one place. `store/programs.py` defines the active-member predicate (`removed_at IS NULL`) once as an SQL constant, and every member and pair read there uses it. No other module queries `members`, which an AST test over the SQL constants checks. So `resolve_member` gives `NotInProgram`, `members_of` leaves the member out, `status` doesn't list it, and `member_of_other_program` ignores it, with no filter of their own. Naming it again under `members` re-registers it (clearing `removed_at`, possibly in another program), with `rules_paths` required as for a new member.
- **Pairs are deleted.** A pair carries no history.
- **The concept** is removed with `concept: null`, which 222 D7 already provides. This slice adds no second way. It adds a test and documents the line under removal in `docs/cli-contract.md`. Removing the concept member without clearing or moving the concept is rejected by the existing `concept_member_not_member` check.
- **New problems:** `member_has_open_questions` (the member has `claimed` or `waiting_on_pm` rows; the detail lists their keys and says to `dismiss` or `answer` them), `not_a_member` (the reference is no member of this program, past or present). `malformed` also covers a member under both `members` and `remove.members`, a pair under both `depends_on` and `remove.pairs`, and removing a member while naming it as a pair end.
- **Repeats** follow 222: removing an already removed member or an absent pair is no change, so a repeat request returns `unchanged`. `changes` gains `removed member <id>` and `removed pair <provider> -> <consumer>` lines.
- An answered question waiting on a resume does not block removal. It is not a question waiting on anyone, and D4 closes it.

### D9 — Pruning
Status: decided

New required config key `prune_after_days` (int ≥ 1, no default in code; 222 D5). `operations/prune.prune(store, layout, now, after_days) -> PruneReport`, called at the end of `handle_pause` (after any resume, so it never delays one) and of `status`.

- **Settled question:** `closed`, or `answered` with latest answer `resumed` or `not_delivered`.
- **`answering/<id>/` and `logs/answering/<id>.*`:** removed when older than the age (by mtime) and either no question has `answering_run_id = <id>` (a lost insert race, a crash before insert, or an id a restarted dead claim replaced) or that question is settled.
- **`logs/resume/<run_id>/`:** a file is removed when older than the age and its run has no open question (D4). The directory goes when empty. `answers.resume_log` keeps the path as history. `decisions` prints it as stored, and a missing file there is not an error; `docs/store-contract.md` says so.
- **`amoeba.sqlite3.legacy-<stamp>`** (D2) is removed when older than the age.
- **`logs/calls/<date>.jsonl`:** removed when the date is older than the age.
- **Any other file under `logs/`** (226's `logs/mcp/` included) is removed when older than the age, and an emptied directory goes with it.
- An entry tied to an open question is kept whatever its age. It is evidence for the PM and for the dead-claim path. D4 and the PM's commands bound how long a question stays open.
- An `OSError` on one entry is caught for that entry only, with a comment saying why: one locked file must not fail the operation that triggered pruning. It goes into `PruneReport.problems`, which `status` prints in its `file_problems` (D12). The other entries are still pruned.
- The store's rows are not pruned. They are the record, and State Management above says why they are bounded.

### D10 — `wrong_checkout`
Status: decided

- `RunFacts` gains `working_directory: Path | None`. It is present in schema-5 files from `sq` 0.24.24 on, and absent (`None`) in earlier schema-5 files, which is no error. `_Body` reads it as optional. A recorded file from 0.24.27 is the new fixture, beside the existing one without the key.
- `handle_pause` checks `realpath(directory) == realpath(working_directory)` after `prompt_only` (the run file is already read for that check) and before the row checks. A mismatch gives the skip `wrong_checkout` with the detail `called from <directory>; the run was started in <working_directory>`, and writes no question row. The D4 `sweep_run` runs before every skip, so a skipped call may already have closed this run's rows at other pauses. That is intended: it depends only on the run id and Squadron's answer, never on the directory. With `None`, the check is skipped, as before.
- It applies whatever the row state, so a dead claim or an unresumed answer is never resumed from a second worktree either.
- `docs/squadron-hook.md` drops its warning for runs started on `sq` 0.24.24 or later, and keeps it for older runs.

### D11 — The calls log
Status: decided

- The CLI's `handle_pause` path appends one JSON line per call to `calls_log_dir() / <UTC date>.jsonl`, whatever happened: `{at, run_id, directory, outcome, reason, detail}` for a result, `{at, run_id, directory, error: <ExceptionName>, detail}` for an exit-3 error. That includes a `ConfigError` raised before any store opens. `append_call` creates `calls_log_dir()` and its parents first, as 223's log writes do, so a fresh install with a bad config still gets the line. An `AmoebaHomeError` about the state home (D1) leaves no path to write to, so that ending goes to stderr only. Every call is logged, not just those that write no row. That is the simpler rule, and it covers amoeba#34's need. The CLI is where errors become exit codes, so it is the only place that sees every ending.
- `detail` is bounded with the existing `bounded_text`, so a line stays well under `PIPE_BUF`. The file is opened with `O_APPEND`, so concurrent hooks don't interleave.
- If writing the log fails (`OSError`), one line goes to stderr and the exit code is unchanged. The comment says why: the log is a trace and must not change the call's result.
- `calls_log.last_call(dir, run_id)` reads day files newest first and returns the newest line for that run, or `None`. `status` attaches it to each `unhandled` and `claim_stale` run as `last_call`, which shows why a hook missed. Pruning (D9) bounds how far back it reads. It never raises. A day file it cannot read, or a line that is not valid JSON (an interrupted append, for example), is skipped and named in `status`'s `file_problems` (D12), and the rest of `status` is still shown.

### D12 — `status` and `decisions` output
Status: decided

- **`PauseClass.CLOSED`:** the run's current pause has a `closed` row. `handle_pause` skips it as `SkipReason.CLOSED`. `status` shows it as stopped, with `closed_reason` and `closed_detail` in `detail`, and `next` null. 224's cross-check table test gains the class.
- **`closed_now`:** a new top-level list in `StatusResult`, `[{program, member, run_id, paused_at, question, closed_reason, closed_detail}]`, plus answers marked `not_delivered` (`{…, answer_seq, resume_outcome}`). It covers what this call closed, so the PM sees each automatic closure once, in the `status` that made it. Closures made by `handle_pause` appear in the calls log line's `detail`.
- **`waiting_on_pm`** lists only open questions. `run_state` is `at_pause`. `moved_on` and `not_listed` are gone, because those rows are closed in the same call. After a failed sweep write (D4), rows not yet closed keep 224's `moved_on` and `not_listed` until a later call closes them.
- **`last_call`** on `unhandled` and `claim_stale` runs (D11). **`file_problems`** when pruning or reading the calls log had any.
- **Placement** skips run directories under both `answering_dir()` and the legacy `<legacy home>/answering` (D1). Without the second, a paused answering run started before the move would appear as `directory_missing`.
- **`decisions`** records gain `retracted_at` and `retract_reason`. Closures are not answers, so `decisions` does not list them. The marker and `read_through` are unchanged.

### D13 — CLI, config and contract docs
Status: decided

- `cli/main.py` gains `dismiss` and `retract` (exit 0, 1, 2, 3 as 222 D9) and opens the store only through `open_state_store` (D2) in every command. `StoreRelocateError` is exit 3.
- `docs/cli-contract.md`: both new commands, `set_up` `remove`, the new `status` fields, the new skip reasons (`closed`, `wrong_checkout`), and the calls log's line format.
- `docs/config-contract.md`: `prune_after_days` in the key table and the example (value `30`), and the two homes.
- `docs/store-contract.md`: its description of the migration rule says `ADD COLUMN` stays the default, names `003`'s `questions` rebuild as the one exception and why (D3), and says a new exception needs the same justification in its design. Also migration `003`, the `closed` state and its reasons, which operation writes each new column, and the lifecycle table from D4/D5/D6.
- `README.md` "where things live": the two homes and `XDG_STATE_HOME`.

### Pending Planning Edits

Made outside this slice, when this design is accepted:

- **`220-arch.program-tool.md`:** the operation table gains `dismiss` and `retract`. "The question record" gains the `closed` state and its three reasons, and says a retracted PM answer is not precedent and a PM answer resets the answer limit. "Where things live" gains the two homes. A note says `status` closes records whose run has gone and prunes old files, and that this is still bounded and adds no `sq` call.
- **`226-slice.mcp-server.md`:** eight operations, not six. The tool table gains `dismiss` and `retract` (in-process). The stdio smoke test lists eight tools. The MCP layer opens the store through `open_state_store`.

### Patterns and Conventions

- New vocabularies (`ClosedReason`, `SkipReason.CLOSED` and `WRONG_CHECKOUT`, `PauseClass.CLOSED`, the dismiss, retract and `set_up` problem codes) are each a `StrEnum` defined once. Closed SQL vocabularies are pinned by the existing test.
- Every write that can race (sweep, dismiss, retract, resume start) is a compare-and-set in one short `BEGIN IMMEDIATE` transaction. The row count tells the writer whether it won.
- Request models validate raw input inside the operation, so 226 passes MCP input through unchanged.

## Implementation Details

### Migration Plan

**What moves:** the store file and the `answering/` and `logs/` trees, from `~/.config/amoeba/` to `${XDG_STATE_HOME:-~/.local/state}/amoeba/`. `config.yaml` stays.

**Consumers of the home functions:** `cli/main.py` (`store_path`, `config_path`, `_deps` building `answering_dir`, `logs_dir`) and `status_placement.py` (through `deps`). Removing `amoeba_home()` makes pyright list any caller this design missed. `tests/conftest.py` keeps `AMOEBA_HOME`. The live tests set `AMOEBA_HOME`, so they are unaffected.

**Data:** the store is copied with `backup`, `resume_log` paths are rewritten, and the copy is verified before the original is deleted (D2). Then `Store.open` migrates the moved store from 2 to 3 (D3) in its own transaction. If the migration fails, the moved store is still a valid version-2 store in the new place, and the error is exit 3.

**Behavior preserved:** every 222–225 test passes unchanged apart from the expected `status` output changes (D12) and the limit count (D7). The moved real store answers `amoeba decisions` with the same records as before the move (Walkthrough step 2).

### Database / Storage Schema

See D3. One rebuilt table (`questions`), five added columns elsewhere, schema version 3.

## Integration Points

### Provides to Other Slices

- **226 (MCP):** `dismiss` and `retract` with their request and result models. `set_up`'s `remove` inside the existing `SetUpRequest`. `prepare_state_home` and `StateLayout`, called once when the MCP process starts. The new `status` fields. `status`'s time bound is unchanged (D4). The MCP layer opens the store only through `open_state_store` (D2).
- **227:** removed members are filtered out by `store/programs.py`'s reads, which 227 uses rather than querying `members` itself, and `remove.pairs` clears stale pairs. 227's plan entry relies on this ("`set_up remove` (228) clears stale pairs").

### Consumes from Other Slices

- **223, 224:** as listed under Interfaces Required. If a named function has moved since those designs, the tasks use the current name. The behavior described here is the contract.
- **Squadron:** `working_directory` in the run file (D10). If `sq` stops writing it, the check falls back to 223's behavior (no check), as for older runs. A test pins both file shapes.

## Success Criteria

### Functional Requirements

- With `AMOEBA_HOME` unset in a throwaway `HOME`, a legacy `~/.config/amoeba/` holding a store, `answering/` and `logs/` ends with only `config.yaml` there after one command. The new store has every row, `resume_log` paths point under the state home, and it is at schema 3.
- A differing double store leaves the state-home store in use and the legacy one set aside as `amoeba.sqlite3.legacy-<stamp>` in the state home, named on stderr. A held legacy write lock delays the move and then the move completes.
- `dismiss` closes a `claimed` and a `waiting_on_pm` question (including one at the answer limit), returns `unchanged` on repeat, and rejects an `answered` one with `not_open`. `handle_pause` on the same pause skips as `closed`, and `status` shows class `closed`.
- `retract` on a PM answer removes it from `pm_precedent`. An `answerer` answer is rejected. A new PM answer restores precedent.
- After a PM answer, a run with `answer_limit` automatic answers already given gets another automatic answer.
- `handle_pause` at a run's later pause closes the open row at the earlier pause as `run_moved_on`. `status` closes a waiting row whose run completed (`run_moved_on`, detail `completed`) and one whose run is unknown to `sq` (`run_gone`), lists both in `closed_now` once, and never closes a young claim or an answer whose resume may be in flight.
- `set_up` removes a member (soft) and a pair, re-adds a removed member, rejects removing a member with open questions with their keys, and returns `unchanged` on repeat.
- Pruning removes settled and orphan scratch, logs and calls-log days older than `prune_after_days`, and keeps everything tied to an open question.
- `handle_pause` from another worktree of the run's repo skips as `wrong_checkout` and writes no row. A run file without `working_directory` keeps the old behavior.
- Every `handle_pause` call, including a `ConfigError` exit, adds one calls-log line. `status` shows `last_call` on a missed hook.

### Technical Requirements

- `ruff format --check`, `ruff check`, `pyright` (strict) and `pytest` pass.
- Migration `003` is tested on a version-2 store seeded with every state, and `foreign_key_check` is clean.
- The vocabulary pin, schema pin (224 D9), import-boundary and home AST tests are updated and pass.
- The three contract docs and the README match the code.

### Integration Requirements

- A question in every state has an exit with no file edits: `claimed` (settle, dead claim, sweep, dismiss), `waiting_on_pm` (answer, sweep, dismiss), `answered` and unresumed (resume, sweep), `answered` and settled (terminal), `closed` (terminal; `answer` reopens it), a retracted answer (terminal; a new answer replaces it). A test walks each state to its exit.
- 226 and 227 designs can read the layout and states from this document and the contract docs alone.

### Verification Walkthrough

Draft, refined after Phase 6. Run from the amoeba repo root with `sq` 0.24.24 or later and `cf` on `PATH`. Steps 1–2 use a throwaway `HOME`, so the real `~/.config` is never touched until step 9.

1. **Checks.** `uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest -q`. All pass.
2. **Legacy move, throwaway.**
   ```bash
   export FAKE_HOME=$(mktemp -d); unset AMOEBA_HOME XDG_STATE_HOME
   mkdir -p $FAKE_HOME/.config/amoeba
   cp ~/.config/amoeba/config.yaml $FAKE_HOME/.config/amoeba/   # then add prune_after_days: 30
   sqlite3 ~/.config/amoeba/amoeba.sqlite3 ".backup $FAKE_HOME/.config/amoeba/amoeba.sqlite3"
   cp -R ~/.config/amoeba/answering ~/.config/amoeba/logs $FAKE_HOME/.config/amoeba/ 2>/dev/null
   HOME=$FAKE_HOME .venv/bin/amoeba mark_read --through 0
   ls -A $FAKE_HOME/.config/amoeba        # config.yaml only
   ls $FAKE_HOME/.local/state/amoeba      # amoeba.sqlite3, answering/, logs/
   Q="select (select count(*) from questions), (select count(*) from answers), (select max(seq) from answers)"
   sqlite3 ~/.config/amoeba/amoeba.sqlite3 "$Q"; sqlite3 $FAKE_HOME/.local/state/amoeba/amoeba.sqlite3 "$Q"
   sqlite3 $FAKE_HOME/.local/state/amoeba/amoeba.sqlite3 "select version from schema_meta"
   ```
   stderr has one line saying the store moved, and `mark_read` prints `unchanged`. The two count lines match and the version is `3`. A second command prints no move line. The copied rows' `resume_log` paths name the real home, not `$FAKE_HOME`, so the rewrite is checked by the unit tests and in step 9. `mark_read` is used because it needs neither `cf` nor `sq`, which read `HOME` too. Commands that need them use step 3's `AMOEBA_HOME` setup.
3. **Setup for the lifecycle steps.** As 224's walkthrough step 1: `export AMOEBA_HOME=$(mktemp -d)`, a config with `prune_after_days`, and a one-member program `trial` registered from this checkout.
4. **Moved on.** `sq run tests/live/pause/asks_unsettled_question.yaml <alias> --run-id lc-1 --no-pause-hook`. Once paused, `amoeba handle_pause lc-1` gives `waiting_on_pm`. Resume it outside Amoeba with `sq run --resume lc-1 --instructions "Use teal."`. When it pauses again, `amoeba handle_pause lc-1` handles the new pause, and `sqlite3 $AMOEBA_HOME/amoeba.sqlite3 "select paused_at, state, closed_reason from questions where run_id='lc-1'"` shows the first row `closed | run_moved_on`.
5. **Dismiss.** `amoeba dismiss lc-1 --reason "not needed tonight"` gives `"outcome": "dismissed"`. Repeated, it gives `unchanged`. `amoeba handle_pause lc-1` gives `skipped / closed`. `amoeba status` shows the run with `"pause": "closed"` and no `next`, and nothing for it under `waiting_on_pm`.
6. **Limit reset and retract.** Run `asks_question.yaml` as `lc-2` until a `handle_pause` returns `waiting_on_pm / answer_limit_reached`. `amoeba answer lc-2 --text "About 300 lines."` resumes it, and the next pause is answered automatically (`"outcome": "resumed"`). `amoeba decisions` shows the PM record's `seq`. `amoeba retract <seq> --reason "wrong number"` gives `retracted`, and `decisions` shows `retracted_at`. At the next pause, the claim's `passages` (in the store) no longer include that PM answer.
7. **Wrong checkout.** From a second registered worktree of the member (as 222's walkthrough step 3), `amoeba handle_pause <a paused run started in the first worktree>` gives `skipped / wrong_checkout` naming both directories. `tail -1 $AMOEBA_HOME/logs/calls/$(date -u +%F).jsonl` shows the call.
8. **Removal and pruning.** `printf 'program: trial\nremove:\n  members: [<member>]\n' | amoeba set_up --file -` is rejected with `member_has_open_questions` while a waiting question exists. After `amoeba dismiss`, it gives `applied`, and repeated, `unchanged`. Set `prune_after_days: 1`, `touch -t 202601010000` a settled answering directory and an orphan one, run `amoeba status`, and both are gone while an open question's directory remains.
9. **Real upgrade (the install task does this, not the PM).** Add `prune_after_days: 30` to `~/.config/amoeba/config.yaml`, check `pgrep -f "amoeba handle_pause"` finds nothing, then `uv tool install --force .` and run `amoeba status`. `ls -A ~/.config/amoeba` shows `config.yaml` only, `~/.local/state/amoeba/amoeba.sqlite3` exists, and `sqlite3 ~/.local/state/amoeba/amoeba.sqlite3 "select count(*) from answers where resume_log like '$HOME/.config/%'"` prints `0`.

## Risk Assessment

### Technical Risks

- **Moving the live store.** A bad move could lose the only record of real answers.
- **The `questions` rebuild.** A wrong copy or foreign-key handling would corrupt the record.

### Mitigation Strategies

- The move copies, verifies and only then deletes. It is tested only on throwaway homes, including a copy of the real store (Walkthrough step 2) before the real upgrade (step 9).
- `003` runs in one transaction with `foreign_key_check` before commit, and is tested on a version-2 store seeded with every state and answer kind.

## Implementation Notes

### Development Approach

Each step ends with the checks passing:

1. Homes and `StateLayout` (D1), then the move and its crash tests (D2).
2. Migration `003` and the migration runner change (D3).
3. Limit count and precedent changes (D6 store side, D7).
4. `dismiss`, `retract` and their CLI (D5, D6).
5. The sweep in `handle_pause` and `status`, `resume_started_at`, and the `closed` class (D4, D12).
6. `wrong_checkout` and the calls log with `last_call` (D10, D11).
7. `set_up` removal (D8).
8. Pruning and `prune_after_days` (D9).
9. Contract docs and README (D13), then the walkthrough, with results in the task notes.

### Special Considerations

- **Operator walkthrough** (design rule). *Start:* the install task adds `prune_after_days: 30` to the live `config.yaml`, then installs (the installed tool rejects unknown keys, so the key goes in just before the install). Without the key every command, the hook included, exits 3 naming the key, each hook failure gets a calls-log line, and its pause shows as a missed hook in `status`. Recoverable: add the key, then call `handle_pause` from `next`. *First call:* moves the state and prints one line. A differing double store keeps the state-home store and sets the legacy one aside, named on stderr. *Normal path:* hooks answer or record waiting questions. Earlier pauses of the same run close as the run moves on, and `status` closes the rest. *Failures:* a stuck claim ages into the sweep or the dead-claim path. A refused resume is retried by `handle_pause` from `next`, or marked `not_delivered` once the run has moved on. A question at the limit is answered or dismissed. A wrong registration is removed with `set_up`. *End state:* nothing open whose run has gone, with scratch and logs pruned after the age. *Undo:* `answer` reopens a dismissed question, a new PM answer replaces a retracted one, and naming a removed member re-registers it. Dead ends found and removed while writing this design: the answered-but-unresumed record whose run moved on (D4), the claimed row whose run moved on while its claimant was dead (D4), and paused answering runs from before the move showing as `directory_missing` (D12). None remain.
- **Security.** The dismiss and retract reasons are stored and printed as data, and never reach a command line.
