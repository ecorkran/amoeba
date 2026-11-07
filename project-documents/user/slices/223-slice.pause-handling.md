---
docType: slice-design
slice: pause-handling
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 222-slice.store-config-and-set-up
interfaces:
- 224-slice.status-and-decisions
- 225-slice.scenario-a-trial
- 226-slice.mcp-server
dateCreated: 20261107
dateUpdated: 20261107
status: not_started
---

# Slice Design: Pause Handling

## Overview

Scenario A through the CLI: `amoeba handle_pause <run_id>` (run in the paused run's checkout) answers an agent question and resumes the run, or records it as waiting on the PM. `amoeba answer` records the PM's answer and resumes. Both share one resume (D8). Also in scope: the dead claim, migration `002`, the hook doc, and restoring the live answering tests 221 deleted. A run that stops on a question at night gets answered and carries on, or leaves a recorded reason; 225 measures this before anything else is built.

**Excluded:** `status`, `decisions`, `mark_read` and the missed-hook listing (224). MCP (226). Any background retry, watcher or notification. Sharing PM precedent across a program. Configuring the hook in real repos (225).

## Dependencies

- **222:** the store and transactions, config loader, `resolve_member`, `answering_for` (`settings`, `not_authorized`), the `questions` and `answers` tables with `QuestionState` and `ResumeOutcome`.
- **221 and the audit (220):** the answering library at `amoeba/answering/` (inputs, passages, source reads, artifacts, `decide`, `gate`, `pipeline_file`, `values`), `upstream.squadron.run_outcome.poll_run`, and the Context Forge readers (`read_target`, plan reads, `run_cf`). The audit's Slice 182 section gives the 182 take and rewrite groups. The audit's Live tests section names the tests marked `waits on 223` and the commit to restore them from.
- **Squadron**, observed at 0.24.23 on 20261107:
  - `sq runs wait <id> --timeout 0 --json` prints `status`, `pipeline` and a `checkpoint` with `kind`, `paused_at` and `question`. `question` is the tail of the reply and can start with `…`.
  - `sq run --resume <id> --instructions <text>` resumes and adds the text to every dispatch.
  - `sq run --run-id <id>` creates a run under a given id.
  - The run file `~/.config/squadron/runs/<run_id>.json` (`schema_version` 5) holds `params` and `execution_mode` (`sdk` or `prompt-only`). Neither is in `sq runs wait --json`.
- **External, not blocking the build:** `ecorkran/squadron#299` (until it lands, the config names non-Claude models for the answer and check steps). `ecorkran/squadron#302` (the pause command and its opt-out; a hand call works without it).

## Architecture

### Component Structure

```
src/amoeba/
├── operations/
│   ├── handle_pause.py     # checks, new question, dead claim, already answered
│   ├── pause_context.py    # slice from run params, passages, PM precedent
│   ├── answering_run.py    # scratch, start, wait, settle (decide + gate)
│   ├── resume.py           # shared resume
│   ├── answer.py           # PM answer, then resume
│   └── processes.py        # spawn_detached(argv, cwd, logs); stderr_tail
├── store/
│   ├── questions.py        # question/answer reads and compare-and-set writes
│   └── schema/002_pause_handling.sql
├── upstream/squadron/
│   ├── run_outcome.py      # (221) poll_run
│   └── run_file.py         # RunFacts(params, execution_mode)
├── answering/              # (221) + not_authorized.md, no-slice reads, program passages
├── config/home.py          # + answering_dir(), logs_dir(), squadron_runs_dir()
└── cli/main.py             # + handle_pause, answer
```

Imports stay `cli → operations → store, config, upstream, answering`. `processes.py` imports nothing from Amoeba. `run_file.py` imports nothing from `answering`.

### Data Flow

**`handle_pause`**: `poll_run`, eligibility checks (D3), `resolve_member(cwd)`. The question key is `(run_id, checkpoint.paused_at)`. The existing row picks the path (D4):

- **No row.** Gather context (D5), prepare scratch (D6), then insert in one transaction: `claimed` with the answering run id and passages, or `waiting_on_pm` with the failure. On conflict, remove the scratch and return `skipped / already_claimed`. Claiming after context, the reverse of the architecture's order, means no claim exists without its answering run id or a failure reason. Then spawn, wait and settle (D6). Only an answer that settles as `answered` is resumed (D8).
- **`claimed`.** Dead-claim path (D7).
- **`answered`, latest answer not `resumed` or `not_delivered`.** Resume (D8) with the latest answer.
- **Otherwise** `skipped` with the state as reason.

**`answer`**: D9.

### State

- **Store.** Question rows, answer rows, resume outcome on the answer row (D10). Every write is one short `BEGIN IMMEDIATE` transaction. No transaction is held across a subprocess.
- **Files under `$AMOEBA_HOME`.** `answering/<answering_run_id>/` per answering run, and `logs/`. Both are kept as evidence (the dead-claim path reads the scratch) and never pruned until use shows the need.
- **Not stored.** Run status, checkpoint kind and slice state, read fresh each call.

## Technical Decisions

### D1 — One reader per Squadron fact, `paused_at` verbatim

- Status, checkpoint kind, question text and `paused_at` come only from `poll_run`. `params` and `execution_mode` come only from `run_file.py`. No other module runs `sq runs` or opens a run file.
- `paused_at` is stored exactly as `sq runs wait --json` prints it (e.g. `…+00:00`), and compared only against values from the same reader. The run file writes it differently (`…Z`) and is never read for it.
- Question text is stored verbatim, including a leading `…`.

### D2 — The run file reader

`run_file.read_run_facts(runs_dir, run_id) -> RunFacts | RunFileProblem`. Checks `schema_version` is 5. Returns `params` (str to str) and `execution_mode` as `ExecutionMode`. A missing file, other version, bad JSON, missing field or unknown mode is a `RunFileProblem` naming file and field; the caller raises `SquadronError` and never falls back to `sdk`. `runs_dir` is passed in. Squadron prints neither field in JSON, so this coupling lives in one module behind a version check. One task comments on `ecorkran/squadron#303` asking for both fields in `sq runs wait --json`.

### D3 — What `handle_pause` leaves alone

Checks run in this order. The first failure gives the `SkipReason` (`StrEnum` in `operations/handle_pause.py`):

| Reason | When |
|---|---|
| `not_paused` | Outcome is not `paused` (detail gives it) |
| `not_agent_question` | Checkpoint kind is not `agent_question` (detail gives it, raw if unknown) |
| `no_question_text` | No `question` or no `paused_at` |
| `answering_run` | Run id equals some question's `answering_run_id`. Independent of Context Forge and #302 |
| `not_a_project` | Working directory is no Context Forge project |
| `not_in_program` | Project is in no program |
| `prompt_only` | `execution_mode` is `prompt-only`. Checked after membership, so a run-file problem in a non-member repo is not an error |
| `other_member` | A row for this question exists under another member |
| `already_claimed` | A live claim exists (D7), or the insert race was lost |
| `waiting_on_pm` | The question is waiting on the PM |
| `settled` | Latest answer's outcome is `resumed` or `not_delivered` |

A Squadron or `cf` failure is an operational error (exit 3), not a skip: "can't tell" must not read as "not mine".

**The checkout is the working directory.** Squadron 0.24.23 resumes in the caller's directory and does not refuse a wrong one. So the result carries the claimed `checkout`, and D14 says a hand call must run in the run's own checkout. Once #303 records the directory, D2 returns it and a mismatch becomes the skip `wrong_checkout`.

### D4 — Question lifecycle

```
                 insert (context ok)                      settle: confirmed + screen ok
  (none) ───────────────────────────► claimed ───────────────────────────────► answered
     │                                   │  settle: declined / screen refused        ▲
     │ insert (context or scratch failed)▼                                            │
     └──────────────────────────────► waiting_on_pm ─────── answer (PM) ─────────────┘
                                         claimed ── answer (PM) ──► answered (in-flight result: superseded)
```

- Insert is `INSERT … ON CONFLICT (run_id, paused_at) DO NOTHING`. The process whose row was written is the claimant.
- Every move out of `claimed` is `UPDATE … WHERE state = 'claimed' AND answering_run_id = ?`. Nobody settles a claim they don't hold, and a PM answer mid-run wins.
- Answer rows are never changed apart from their resume columns (D8). A newer answer adds a row; the newest is the one a resume delivers.
- `waiting_reason` is a `DeclineReason` (222 D3). `waiting_detail` is the bounded detail from `decide`.

### D5 — Context: slice, passages, precedent

`pause_context.gather(checkout, member, program, run_facts, question, settings, cf_run) -> PauseContext | SourcesProblem`.

- **Slice.** The run's `slice` parameter (`TARGET_PARAM_KEY`, defined once in `pause_context.py`) is a slice index. Search the plans of initiatives with index no higher than it, highest first; the label is `<index> <name>`. A non-integer value, or one in no plan, is `sources_missing`, never "no slice", so a broken Context Forge convention shows as a waiting question, not a wrong slice. Tested on real `cf list initiatives --json -a` and `cf list slices <index> --json` output in `tests/fixtures/context_forge/`, including a slice in no plan.
- **No slice.** Rules, program passages and precedent, no plan passages, label `NO_SLICE_LABEL = "none"`. Plan row selection in `source_reads` becomes optional when `slice_ref` is `None`.
- **Committed reads.** Rules and plan files via `read_committed_sources` from the question's checkout at its `read_target`. `rules_paths` come from `answering_for`. Program passages: D11.
- **Precedent.** `questions.pm_precedent(store, member_id)`: the newest PM answer for each of the member's questions, with question text, slice label and `recorded_at`. Automatic answers are never precedent.
- **Failures.** Each `SourcesProblem` maps to its `DeclineReason` through the kept `sources_reason`. A failing `cf` call is `sources_unreadable` with the output head.

### D6 — The answering run

- **Id and scratch.** Id is `amoeba-<UTC stamp>-<12 hex>` (the deleted `mint_run_id`, restored in `answering_run.py`). Before the claim, `answering_dir() / <id>` is created exclusively and filled by `prepare_scratch`, including the not-authorized file (D11). An `OSError` inserts the row as `waiting_on_pm` with `answering_launch_failed`.
- **Command.** `sq run <answering.yaml> <answer_model> --run-id <id> -p check-model=<check_model>`. No pause opt-out flag, because #302 hasn't defined one. If the answering run pauses and the hook fires, it is skipped as `answering_run` (D3), since the claim already holds its id. Adding #302's flag is deferred to 225 (amoeba#35).
- **Order.** Insert the claim with the id, then spawn. A death in between leaves a claim for a run that never started (D7).
- **Spawn.** `processes.spawn_detached(argv, cwd=scratch, logs)`: exclusive log files, own session, `stdin` from `/dev/null`, inherited environment, closed descriptors. Logs at `logs_dir() / "answering" / <id>.{stdout,stderr}.log`. A spawn error settles as `answering_launch_failed`.
- **Wait.** Up to `answering_wait_seconds` (required config key, number > 0) for the child to exit. On timeout, terminate its process group and settle as `answering_run_stalled` (`no result after <n> seconds`). Otherwise one `poll_run(id)` gives a `RunSummary`; a `PollFailure` settles as `answering_run_failed` so the claim doesn't hang.
- **Settle.** If completed, `read_answer` and `read_check` from scratch. `decide_answer(summary, answer, check, passage_ids)` with the claim's passage ids. A `Confirmed` answer goes through `evaluate_gate(question, prior, answer=…, settings=…)`. Pass: compare-and-set `claimed → answered` and add an `answerer` answer row, one transaction. Decline: compare-and-set to `waiting_on_pm` with the reason.
- **Answer limit.** `prior` counts only automatic answers (`answered_by = 'answerer'`, this `run_id`, any `paused_at`), inside the settle transaction. PM answers never count. If `prior` already meets `answer_limit` when the question is first seen, insert as `waiting_on_pm` with `answer_limit_reached` and start nothing; the gate stays the final word.

### D7 — The dead claim

A `claimed` row seen by a later call is decided by `poll_run(answering_run_id)` and the claim's age against `answering_wait_seconds`:

| Answering run | `claimed_at` | Action |
|---|---|---|
| `timed_out` (still running) | young | `skipped / already_claimed` |
| `timed_out` | old | Compare-and-set to `waiting_on_pm` with `answering_run_stalled`. A later reply is ignored, since the row is no longer `claimed` |
| `completed`, `failed`, `paused`, `orphaned` | any | Settler died. Settle from scratch (D6), then resume |
| `not_found` | young | `skipped / already_claimed`. Squadron writes no run file until the pipeline loads, which takes seconds |
| `not_found` | old | Claimant died before spawn. Gather context again, new scratch under a new id, compare-and-set `answering_run_id` and passages from old id to new, spawn, continue as D6 |
| `PollFailure` | any | Operational error, nothing written |

With the age gate, only a claimant that died before its spawn causes a second answering run, the double-spend the architecture accepts.

### D8 — The resume

`resume.resume(store, question, answer_seq, *, deps) -> ResumeResult`, called by both operations.

1. **Checkpoint.** `poll_run(run_id)`. Not `paused`, or a different `paused_at`: `not_delivered`, nothing started.
2. **Start.** `sq run --resume <run_id> --instructions <compose_instructions(question, answer)>` via `spawn_detached` with `cwd = questions.checkout`. Logs at `logs_dir() / "resume" / <run_id> / <answer_seq>-<UTC stamp>.{stdout,stderr}.log`; the stdout path is `resume_log`. A spawn error is `refused`.
3. **Wait.** Poll every `RESUME_POLL_INTERVAL_SECONDS` (0.5, in `resume.py`) for up to `resume_wait_seconds` (required config key, number > 0):
   - `running`, or moved past this pause (other `paused_at`, `completed`, `failed`): **resumed**. A fast run can pause again before a poll sees `running`.
   - Child exited, run still at this pause: **refused**, stderr tail as detail (e.g. a held run lock).
   - Timeout with child alive and run unchanged: terminate the child's process group, wait for exit, poll once more, because the child may have taken the lock just before the kill. Still at this pause: **refused** (`not running after <n> seconds`). `running` or moved past: **resumed** (`resume process terminated after taking the run`); Squadron then reports the run through its own state.
4. **Record** `resume_outcome`, `resume_detail`, `resume_log`, `resume_at` with `WHERE resume_outcome IS NULL OR resume_outcome = 'refused'`. `resumed` and `not_delivered` are never overwritten, so of two racing resumes the run lock refuses the second and the first's `resumed` stands.

A refused resume, or a process that died between steps 2 and 4, leaves the answer with `refused` or no outcome. The next `handle_pause` takes the already-answered path and resumes with the recorded answer, starting no answering run.

### D9 — The `answer` operation

`answer.answer(store, config, document, *, deps) -> AnswerResult`. `document` is validated into `AnswerRequest` (`run_id`, optional `paused_at`, `text`); CLI and MCP pass input through unchanged.

- **Find.** By `(run_id, paused_at)`, or the run's row with the latest `claimed_at`. No row: `rejected / no_such_question`, since there is no checkout to resume from; the detail says to run `handle_pause` from the run's checkout.
- **Text.** Stripped, non-empty, else `rejected / malformed`. PM answers skip the screen and the limit.
- **Write.** One transaction adds a `pm` answer row and sets `answered` from any state. It does not clear `waiting_reason` or `waiting_detail` (224 reads them). The newest PM answer is the precedent (D5), which also covers overriding an automatic answer.
- **Resume.** D8. On an already resumed question the checkpoint compare gives `not_delivered`; the override still stands as precedent.
- **Result.** `outcome` (`recorded` or `rejected`), question key, `answer_seq`, `ResumeResult`, `problems`.

### D10 — Migration `002_pause_handling.sql`

`ALTER TABLE … ADD COLUMN` only, nullable (222 D3). `EXPECTED_SCHEMA_VERSION` becomes 2.

| Table | Column | Holds |
|---|---|---|
| `questions` | `slice_label` | D5's label, reused on precedent passages |
| `questions` | `source_commit` | Commit the passages were read at |
| `questions` | `passages` | JSON array of `PassageRef` (id, kind, source, date) |
| `questions` | `waiting_detail` | Bounded detail for `waiting_reason` |
| `questions` | `evidence` | JSON `AnsweringEvidence`: proposed answer, citations, check verdict and reason |
| `answers` | `cited` | JSON array of passage ids (automatic answers) |
| `answers` | `resume_detail` | Refusal or not-delivered detail |
| `answers` | `resume_log` | Resume stdout log path |
| `answers` | `resume_at` | When the outcome was recorded |

Each JSON column has one serializer and one parser in `store/questions.py`, tested round-trip. `docs/store-contract.md` gets the columns, the vocabularies and which operation writes each column.

### D11 — Changes to the answering library

- **Authorize list.** `pipeline_file.NOT_AUTHORIZED_FILE = "not_authorized.md"`. `inputs.render_not_authorized(items)` writes one `key: description` bullet per item; an empty list renders `No item is barred for this repository.` `prepare_scratch` writes it. In `answering.yaml` both steps list it in `prompt_files` after `passages.md`. The hard-coded list in both prompts is replaced by text saying the list follows the passages, and the answer step must decline, and the check step reply no, when an answer would authorize anything on it. The existing pin test covers the new file. Not passed as a `-p` parameter, because Squadron splits `-p` values on commas.
- **Screen.** `settings.reserved_terms` already holds only the member's barred items (222 D8), and `evaluate_gate` is unchanged. Allowing an item for a member removes it from both the prompt file and the screen.
- **Program passages.** `program_concept` and `program_members` come from the 182 take group in the audit's Slice 182 section; if that group is empty they are written new from 182's design. `answering.passages` gains both kinds and their rendering. `assemble` takes a `ProgramSources` value: the concept as a `SourceFile` (member id, path, commit, date, text) and the member list. Both prompts list the two new kind words.
- **Where program reads happen.** In `pause_context.py`, replacing 181's `read_member`: concept member and path from `programs`, member list from `members_of`, the concept member's checkout from `project_of(reference=…).project_path` (222 D6), and the concept file through the git allowlist at that checkout's target (182 D3; the asker's own pinned commit if it is the concept member).
- **Boundary.** `answering` imports nothing from `store`, `config` or `operations` (`store` already imports `answering.values`). `tests/test_import_boundaries.py` gains this rule.

### D12 — Home paths

`config/home.py` gains `answering_dir()` (`amoeba_home() / "answering"`), `logs_dir()` (`amoeba_home() / "logs"`) and `squadron_runs_dir()` (`Path.home() / ".config" / "squadron" / "runs"`), names as constants there. Only `home.py` may call `Path.home` (222 D10). Operations take the paths as arguments; only the CLI calls the helpers.

Unit tests pass a fixture directory to the reader. CLI subprocess tests set `HOME` to a temporary directory holding `.config/squadron/runs/<run_id>.json`, copied from the recorded run file, so no test reads the developer's real run files.

### D13 — CLI

```
amoeba handle_pause <run_id>
amoeba answer <run_id> [--paused-at <ts>] --text <answer>
```

- Both print their result model as JSON on stdout.
- Exit codes extend 222's constants. `handle_pause` exits `0` for every outcome, including `skipped`. `answer` exits `1` when `rejected`. `2` is usage. `3` is operational: `SquadronError`, `ContextForgeError`, `ConfigError`, `AmoebaHomeError`, any `StoreError`, message on stderr.
- `HandlePauseResult.outcome` is `skipped`, `waiting_on_pm`, `superseded`, `resumed`, `refused` or `not_delivered`, plus `skip_reason` or `waiting_reason`, `detail`, question key, claimed `checkout`, `answering_run_id` and `answer_seq` where they apply.
- No call log. A call that writes no row leaves a pause 224 lists as a missed hook. Call logging stays unbuilt until use shows the need (amoeba#34; 225 D4).

### D14 — Wiring the hook

`docs/squadron-hook.md` says:

- Configure `amoeba handle_pause <run_id>`, run in the run's directory; Squadron supplies both (#302). The exact config line is added with #302's form in 225 (amoeba#35).
- Only repos in a program need it. A run started with the opt-out flag is left alone.
- A hand call must run in the run's own checkout, because until #303 nothing confirms it (D3).
- The hook's environment must reach `sq`, `cf`, `git` and model credentials, since the resume inherits it.

### D15 — Tests

- **Fake `sq`.** Unit and CLI tests put a fake `sq` first on `PATH` that replays recorded `sq runs wait --json` documents and exit codes. Recordings in `tests/fixtures/squadron/` are real 0.24.23 output: an `agent_question` pause (modeled on the run captured 20261107), another checkpoint kind, a running run, a completed run. A real schema-5 run file is the `run_file` fixture.
- **Unit coverage.** Every `SkipReason`, each producible `DeclineReason`, every row of D7, every D8 branch including the poll after the timeout kill. The compare-and-set guards (a PM answer during settling gives `superseded`; `resumed` is never overwritten). The answer limit ignoring PM answers. An item barred for one member and allowed for another. No transaction open while a subprocess runs (through the injected spawner and poller). Migration `002` on a version-1 store.
- **Live tier** (`tests/live/pause/`, outside the default suite): `asks_question.yaml`, whose dispatch ends on a question the repo's rules settle, run in a throwaway worktree registered as a member under a test `AMOEBA_HOME`. The test calls `amoeba handle_pause` on the pause and asserts the record (question, passages, answer, `resumed`) and that the run left the pause.
- **Restored tests.** The `waits on 223` files named in the audit's Live tests section are restored from the named commit and rewritten to drive `handle_pause`. Each keeps its claim.

## Interfaces

**Python API** (for 224 and 226):

- `operations.handle_pause.handle_pause(store, config, run_id, *, directory, deps) -> HandlePauseResult`
- `operations.answer.answer(store, config, document: object, *, deps) -> AnswerResult`
- `operations.resume.resume(...)`, internal
- `store.questions`: `get_question`, `latest_question`, `answers_of`, `latest_answer`, `automatic_answer_count`, `pm_precedent`, and the writes in D4 and D8
- `processes.spawn_detached(argv, cwd, logs)`
- `deps` bundles the `cf` runner, `poll_run` (with its timeout), the spawner and the paths

**To 224:** question states, `waiting_reason`, `waiting_detail`, and answer rows with `seq`, `answered_by`, `cited` and resume columns. An answer with `resume_outcome` null or `refused` means "answered, not resumed". `handle_pause` is what `status` points an agent at for a missed hook.

**To 225:** `docs/squadron-hook.md`, records ready for `decisions` to measure, and amoeba#34 and #35.

**To 226:** both operations with their request and result models and `deps`. MCP starts `handle_pause` as a detached CLI process with `cwd` set to the run's checkout, taken from 224's listing (Squadron's recorded directory, #303), never the MCP server's own directory (D3).

**From 222:** if a needed store read is missing from `store.programs`, add it there, don't copy it.

**Squadron failure:** if `sq` is missing or fails, every path stops with `SquadronError` before writing, except the D6 wait, which records a decline so the claim doesn't hang.

## Success Criteria

- On a real paused run in a member, `handle_pause` answers and resumes it, and the record shows question, passages, cited answer, check verdict and `resumed`.
- An answer authorizing an item on the member's list waits on the PM (`check_said_no` or `reserved_term`). After `set_up` allows that item for the member, the same question is answered.
- `answer` on a waiting question records it, resumes the run, and is precedent at a later pause.
- `ruff format --check`, `ruff check`, `pyright` (strict) and `pytest` pass, including D15's unit coverage.
- `answering.yaml` holds no hard-coded authorize list.
- `docs/squadron-hook.md`, `docs/store-contract.md` and `docs/config-contract.md` (both new keys) match the code.
- The live tier and restored `tests/live/answering` files pass with `AMOEBA_LIVE_*` set.
- The #303 comment is posted (D2).

### Verification Walkthrough

From the amoeba repo root, with a scratch home whose config is copied from `docs/config-contract.md` (both wait keys set, non-Claude models until #299 lands).

1. Set up:
   ```bash
   export AMOEBA_HOME="$(mktemp -d)"; cp <filled config> "$AMOEBA_HOME/config.yaml"
   printf 'program: demo\nmembers:\n  - rules_paths: [CLAUDE.md]\n' | uv run amoeba set_up --file -
   ```
   Expect `applied`, with amoeba as a member.
2. Make a real pause (no `slice` parameter, so the no-slice path is used):
   ```bash
   sq run tests/live/pause/asks_question.yaml <model> --run-id demo-pause-1
   sq runs wait demo-pause-1 --timeout 0 --json
   ```
   Expect `paused`, `agent_question`, a question about file length limits.
3. `cd /tmp && uv run --project <amoeba repo> amoeba handle_pause demo-pause-1` gives `skipped / not_a_project`.
4. `uv run amoeba handle_pause demo-pause-1` gives `resumed`, and `sq runs wait` shows the run running or past the pause. Then:
   ```bash
   sqlite3 "$AMOEBA_HOME/amoeba.sqlite3" "select state, slice_label, passages, evidence from questions; select answered_by, answer, cited, resume_outcome, resume_log from answers;"
   ```
   Expect `answered`, passages, check `yes`, an `answerer` answer with citations, `resumed`, and an existing log path. Running `handle_pause` again gives `skipped / settled`.
5. `uv run amoeba answer <run_id> --text "…"` on a `waiting_on_pm` question gives `recorded` and a resume result.

## Risks and Special Considerations

- **Resuming real runs on a model's answer.** A wrong answer reaches every dispatch of the resumed run. Bounded by the check, the authorize list and the screen; 225 measures wrong answers before anything more is built.
- **Unobserved Squadron resume timing.** D8 treats "moved past" as resumed. Anything the live test shows that the fixtures lack becomes a fixture.
- **Security.** Question text is stored and rendered as data, and reaches a command line only as the single `--instructions` argv element, with no shell.

## Implementation Order

Effort 5. Each step ends with the checks passing: store and migration (D4, D10); run file, home paths and `sq` fixtures (D2, D12); library (D11); context (D5); answering run (D6); resume (D8); `handle_pause` and `answer` (D3, D7, D9); CLI, config keys and contract docs (D13); live tier, restored tests, hook doc, #303 comment (D14, D15); the walkthrough, with results in the task notes.
