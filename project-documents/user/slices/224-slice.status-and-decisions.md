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
turns: 15
promptTokens: 1084013
cachedTokens: 983412
cacheWriteTokens: 100571
completionTokens: 32743
durationSeconds: 343.6
costUsd: 1.656563
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.6565626
    completionTokens: 32743
---

# Slice Design: Status and Decisions

## Overview

This slice is the read side of scenario A, and the part of scenario C that works through the CLI. It adds three operations:

- **`amoeba status`** shows each member of a program: its running and paused runs, why each paused run stopped, questions waiting on the PM with their reasons, answers that were not resumed, and paused question runs with no record (a missed hook). For each item that needs action, it names the operation that handles it. Run state comes from `sq runs list --json` and is never stored.
- **`amoeba decisions`** lists the recorded answers since the PM's marker, or since a given time. For each answer it gives who answered and what the answer was based on.
- **`amoeba mark_read --through <seq>`** moves the PM's marker forward to the last record the caller saw. It never moves past that record, and never moves backward.

It also gives `handle_pause` and `status` one shared definition of what Amoeba handles, so a missed hook that `status` reports is one that `handle_pause` will act on. It adds the schema test that 222 D3 assigned to this slice.

## Value

User value. Through any agent, the PM sees what is waiting on them and what was decided without them, and can clear what they have read. An agent can also find paused runs that the hook missed and pass them to `handle_pause`. 225 measures scenario A from `decisions` and `status`, and 226 puts these operations behind MCP.

## Technical Scope

**Included:**

- `status`, `decisions` and `mark_read`: operations, request and result models, and CLI subcommands (D2, D4 to D8).
- A reader for `sq runs list --json` (D1), and a reader for `cf list projects --json` that supplies member names (D6).
- `classify_pause`, moved out of `handle_pause` so both operations use it (D3).
- The schema test (D9), plus updates to `docs/store-contract.md` and to the CLI contract.

**Excluded:**

- Any store migration. The 222 and 223 schemas already hold everything this slice reads, and `pm_marker` already exists.
- Slice state. `status` shows a question's stored `slice_label`, which records what the question was asked about. It does not read or show Context Forge slice status. The plan entry is amended to match, in the same commit as this design: it keeps only the rule that slice state is never stored, which D9 enforces, and its scope sentence now matches D2 and D5. Nothing is built to show slice state, because the architecture's `status` row lists no slice state and neither 225 nor 226 needs it.
- Writes of any kind, apart from `mark_read` moving `pm_marker`.
- The `wrong_checkout` skip that 223 D3 left until #303. It changes `handle_pause`, not the read side, and is deferred to amoeba#37. Until then, `docs/squadron-hook.md` keeps 223's warning that a hand call must run in the run's own checkout.
- MCP (226), notifications, and closing out stale question rows (D4).

## Dependencies

### Prerequisites

- **Slice 223 complete.** The question and answer rows, migration `002`, `handle_pause`, `answer`, `run_file.read_run_facts`, the `answering_wait_seconds` config key, and `poll_run`.
- **Slice 222.** The store, the config, `resolve_member`, `project_of`, and the CLI's exit-code constants.
- **External: `ecorkran/squadron#303`, open on 20261107.** `sq runs list --json` with each run's working directory. Squadron 0.24.23 doesn't have it. D1 gives the shape built against and what waits for it.
- **Context Forge 0.19.26.** `cf list projects --json` prints an array of `{id, name, projectPath?, fileSlice, isActive}`. `projectPath` is absent on some entries, as observed on 20261107.

### Interfaces Required

- **From 223:** `store.questions` reads (`get_question`, `latest_answer`, `answers_of`), the `QuestionState`, `DeclineReason` and `ResumeOutcome` vocabularies, the `passages`, `evidence` and `cited` JSON parsers, `HandlePauseResult` and `SkipReason`, and the `deps` bundle.
- **From 222:** `Store.read()` and `Store.write()`, `programs.members_of` and `get_program`, `resolve_member`, `project_of`, `load_user_config`, and `AmoebaHomeError`, `ConfigError`, `ContextForgeError` and `StoreError`.

## Architecture

### Component Structure

```
src/amoeba/
├── operations/
│   ├── pause_class.py      # classify_pause(): the one definition of what Amoeba handles (D3)
│   ├── status.py           # status() and StatusResult: scope, run placement, join (D2, D4)
│   ├── decisions.py        # decisions() and DecisionsResult (D5, D6)
│   ├── mark_read.py        # mark_read() (D7)
│   └── handle_pause.py     # (223) calls classify_pause
├── store/
│   ├── questions.py        # (223) + open_questions(member_ids)
│   └── decisions.py        # answers_since(), read_marker(), advance_marker()
├── upstream/
│   ├── squadron/run_list.py       # sq runs list --json → ListedRun (D1)
│   └── context_forge/projects.py  # cf list projects --json → names by id (D6)
└── cli/main.py             # + status, decisions, mark_read
```

The import direction stays as 222 set it: `cli → operations → store, config, upstream`. `run_list.py` and `projects.py` import nothing from `store`, `operations` or `answering`.

### Data Flow

**`status [--program P]`**, from anywhere:

1. **Scope** (D2). With `--program`, that program, or `rejected / unknown_program`. Without it, `resolve_member(cwd)` gives the member's program. From a directory that is in no program, the scope is every program.
2. **Store read.** One read transaction gets the programs in scope, their members, every question of those members that is `claimed`, `waiting_on_pm`, or `answered` with a latest answer whose `resume_outcome` is null or `refused`.
3. **Runs.** One `sq runs list --json` call, with no `--all`. Run placement (D4) matches each run to a member through its working directory, with one `project_of` call per distinct directory.
4. **Classify** (D3). Each paused run of a member in scope goes through `classify_pause`, with its question row and latest answer if one exists. A paused agent question with no row is classified from its run file (`execution_mode`).
5. **Join** (D4). Each question from step 2 is matched to its run by `run_id` across the whole listing. A run's question state goes on that run's entry. Every `waiting_on_pm` question is listed, together with where its run is now.
6. **Names.** One `cf list projects --json` call gives member names (D6).
7. The CLI prints `StatusResult` as JSON.

**`decisions [--since T] [--program P]`**: one read transaction reads the marker and the answer rows after the starting point, joined to their questions, members and programs. One `cf list projects --json` call gives names. The CLI prints `DecisionsResult`.

**`mark_read --through S`**: one `BEGIN IMMEDIATE` transaction checks `S` against the newest answer `seq`, and sets the marker to the larger of `S` and its current value.

### State Management

- `status` and `decisions` write nothing. `mark_read` writes only `pm_marker.last_seen_seq`.
- Run status, checkpoint kind and working directory are read from Squadron on each call. Member names are read from Context Forge on each call. None of these is stored (D9).

## Technical Decisions

### D1 — Reading runs: `sq runs list --json`, built to #303's proposed shape
Status: decided

- `upstream/squadron/run_list.py` has `list_runs(run) -> list[ListedRun] | RunListProblem`. A `ListedRun` holds `run_id`, `pipeline`, `status`, `working_directory` (an absolute path or `None`) and `checkpoint` (`kind`, `paused_at`, `question`, or `None`). The checkpoint is parsed by the same parser `poll_run` uses for `sq runs wait --json`, so `paused_at` is the same string 223 stores (223 D1). Status values are Squadron's vocabulary, which `poll_run` already defines. An unknown status is kept as a raw string, never mapped to a known value.
- No other module runs `sq runs list`. It is the only source of "which runs exist and where".
- **What the listing must cover.** It is called without `--all`. At 0.24.23 the default lists "running and resumable runs", and a paused run is resumable. `status` relies on the default including every running and every paused run, whatever its age or directory. The fixture task records a listing that has a paused run older than the others, and a paused run started in another directory. If the recorded default leaves out either one, `run_list.py` passes `--all` instead and drops completed runs itself. Either way, a run that is absent from the listing has finished or is gone (D4).
- **Hangs.** `list_runs` takes `timeout_seconds` and runs `sq` the way `poll_run` does, with the same timeout value that 223's `deps` passes to `poll_run`. The `cf` calls (`project_of` and D6's `project_names`) go through `run_cf`, which is already bounded and uses the timeout `deps` carries for `cf`. So every subprocess `status` starts is bounded by a value that already exists. The `project_of` calls run one after another, so the whole call takes at most the `sq` timeout, plus one `cf` timeout for `project_names`, plus one `cf` timeout per distinct run directory. A `sq` or `project_names` timeout is exit 3. A `project_of` timeout is a `lookup_failed` run (D4).
- Any non-zero exit, output that isn't JSON, or a missing field is a `RunListProblem` that quotes the output head. The operation raises it as `SquadronError`, exit 3. A Squadron with no `--json` on `sq runs list` fails the same way. The message says that `status` needs Squadron with `ecorkran/squadron#303`.
- **What waits on #303.** The issue proposes that the run file record the absolute working directory, and that `sq runs list --json` print one entry per run with the run id, pipeline, status, working directory and the `sq runs wait --json` checkpoint object, with a `null` directory for older run files. All of the code can be written now, against those fields, and tested with a fake `sq` replaying hand-written documents in that shape. The project's parsing rule needs a fixture of real output. So the slice is not complete until #303 has landed, its real output has been recorded into `tests/fixtures/squadron/runs_list/`, and the parser passes on that recording. If #303 lands with different field names, only `run_list.py` and its fixtures change. If #303 has not landed when implementation reaches that task, the task gets a `BLOCKED:` line.

### D2 — Scope of `status`
Status: decided

| Called with | Scope |
|---|---|
| `--program P` | Program `P`. An unknown `P` is `rejected / unknown_program`, and the detail lists the known program ids |
| no flag, from inside a member | That member's program |
| no flag, from a directory in no program, or not a project | Every program |

The slice plan says that an explicit program is taken from outside a member. Here it is accepted from anywhere, and leaving it out outside a member means all programs, not an error. There is one PM, and "what is waiting on me" covers every program. An MCP session that starts anywhere (226) gets that answer with no extra input. A `ContextForgeError` while resolving the working directory is an operational error, as in 222 D6. It never widens the scope.

Every member in scope is listed, including members with nothing to show, so the PM can see which repos are covered.

### D3 — One definition of what Amoeba handles
Status: decided

223 D3's checks are split. The checks that depend on the run, the question row and the run file move into `operations/pause_class.py`:

```python
classify_pause(outcome, question_row, latest_answer,
               run_facts, claim_age_limit, now) -> PauseClass
```

`run_facts` is read lazily, only when the result depends on it. `PauseClass` is a `StrEnum`:

| Class | When | `handle_pause` (223) | `status` |
|---|---|---|---|
| `not_paused` | Outcome is not `paused` | skip `not_paused` | not classified |
| `other_checkpoint` | Kind is not `agent_question` | skip `not_agent_question` | stopped, with the kind |
| `no_question_text` | No `question` or no `paused_at` | skip | stopped, with the reason |
| `prompt_only` | No row, and `execution_mode` is `prompt-only` | skip | stopped; belongs to its agent |
| `unhandled` | No row, and `execution_mode` is `sdk` | new question path | **missed hook** |
| `claim_live` | Row is `claimed`, and `claimed_at` is within the limit | skip `already_claimed`, or D7 by poll | answering |
| `claim_stale` | Row is `claimed`, and `claimed_at` is past the limit | D7 | **stale claim** |
| `waiting_on_pm` | Row is `waiting_on_pm` | skip | **waiting on the PM** |
| `answered_unresumed` | Row is `answered`, and the latest answer's outcome is null or `refused` | resume | **answered, not resumed** |
| `settled` | Latest answer is `resumed` or `not_delivered` | skip | stopped, with the outcome |

- `claim_age_limit` is the config's `answering_wait_seconds`, the same limit 223 D7 uses. `status` doesn't poll answering runs. `claim_live` versus `claim_stale` tells an agent whether `handle_pause` will act, and `handle_pause`'s D7 poll still makes the final call.
- A run file problem (`RunFileProblem`) is not a class. `handle_pause` raises it as `SquadronError`, as before. `status` shows that run as `run_file_unreadable`, with the problem text, and goes on. One unreadable run file must not hide every other run.
- The `answering_run` check stays in `handle_pause`, before `classify_pause`, with its store read. `status` never reaches an answering run, because D4 skips Amoeba's scratch directories, so it needs no second mechanism.
- The membership checks (`not_a_project`, `not_in_program` and `other_member`) stay in `handle_pause`, because they work from the caller's directory. `status` works from each run's listed directory instead (D4).
- The classes are not collapsed. Each one that `status` shows only as "stopped" maps to its own 223 `SkipReason`, and `handle_pause` needs that distinction. `status` puts the class in the run's `pause` field and adds no field of its own for it.
- 223's `SkipReason` values are unchanged. `handle_pause` maps each class to its existing reason, and 223's tests pass unchanged. One new table test runs the same fixtures through both operations, and asserts that every run `status` lists as a missed hook or stale claim is one that `handle_pause` doesn't skip.

### D4 — Placing runs, and which questions are shown
Status: decided

**Runs.** Each listed run is placed by its `working_directory`:

- `None` (a run file from before #303): listed in the result's top-level `unplaced_runs` with reason `no_directory`.
- A directory that no longer exists (a removed worktree): `unplaced_runs` with reason `directory_missing`. This is checked before any `cf` call, because `cf` can't run in a missing directory.
- A directory under `answering_dir()` (223 D12), which is Amoeba's own answering scratch space: the run is not listed, and no `cf` call is made. Scratch directories are kept and never pruned (223), and they are never members. So without this skip, every resumable answering run would cost a `cf` call, and one `cf` timeout on them would fail `status`. `answering_dir()` reaches `status` through `deps`, as the other paths do.
- `project_of(directory=…)` gives `CFProjectNotFound`, or a project that is in no program in scope: the run is not listed. A repo outside a program is not Amoeba's business (architecture).
- `project_of` gives `CfCallFailed`, including a timeout: `unplaced_runs` with reason `lookup_failed` and the error text. The rest of `status` goes on. One broken checkout, often in a repo that is in no program, must not hide the PM's waiting questions, which come from the store and need no placement. The run stays visible with the reason.
- A member in scope: listed under that member.

`project_of` results are cached by directory for the one call. Worktrees of one repo have different directories and the same project id, so they land on one member. `unplaced_runs` lists every unplaced run, whatever its program, because Amoeba can't tell which program it belongs to.

**Questions.** Stored questions are matched to listed runs by `run_id`, not by directory, so this also works for `unplaced_runs`.

- **Waiting on the PM: never dropped.** Every `waiting_on_pm` question of a member in scope is in that member's `waiting_on_pm` list, with `run_state`:
  - `at_pause`: the run is listed and paused at this `paused_at`. `next` is `answer`.
  - `moved_on`: the run is listed in another state or at another pause. The detail gives that state. There is no `next`.
  - `not_listed`: the run is not in the listing. It has finished or is gone. There is no `next`.

  A `moved_on` or `not_listed` question stays listed, because no operation clears it yet. Closing such rows without the PM acting is deferred to amoeba#36, to be built if 225 shows that they pile up.
- **Claimed and answered questions** appear only through their run's entry (D8), as its `pause` class. An answered question whose run has moved on has its answer in `decisions`, with the resume outcome recorded or null. A claimed question whose run has moved on is settled by its live claimant. If the claimant died, the row stays `claimed` in the record, and the run needs nothing more.

### D5 — `decisions`
Status: decided

`decisions(store, document, *, deps) -> DecisionsResult`. `document` is validated into `DecisionsRequest` (`since` and `program`, both optional), the same way as `set_up`.

- **Starting point.** With no `since`, the listing starts after the marker (`seq > last_seen_seq`). With `since`, it starts at that time (`recorded_at >= since`). `since` must be ISO-8601 with a UTC offset. A timestamp with no offset, or one that can't be parsed, is `rejected / malformed`. It is converted to the store's UTC text form before comparing.
- **Program.** By default, `decisions` covers every program, from any directory. `program` narrows the listing, and an unknown program is `rejected / unknown_program`. A member's own directory does not narrow it, because the marker is one marker across all programs (architecture), and a listing narrowed without the caller asking would invite marking unseen records read.
- **Order.** Records are listed oldest first, by `seq`.
- **Each record:**
  - `seq`, `recorded_at`, `program`, `member` (`id` and `name`), `run_id`, `paused_at`, `slice_label` and `question`.
  - `answered_by` (`answerer` or `pm`) and `answer`.
  - `prior_answer_seq`: the newest earlier answer to the same question, or null. A PM answer with a prior automatic answer is an override, which 225 counts as a wrong answer.
  - `based_on`. For `answerer`: the cited passages, each with `id`, `kind`, `source` and `date`, taken from `answers.cited` and the question's stored `passages`, plus the check's verdict and reason from `evidence`. For `pm`: the question's `waiting_reason` and `waiting_detail` if it had been waiting on the PM, or null if the PM answered first.
  - `resume`: `outcome`, `detail` and `at` from the answer row. The outcome is null when no resume outcome was recorded.
- **`read_through`.** The `seq` of the last record listed, given only when the listing started at the marker, was not narrowed by `program`, and is not empty. Otherwise it is null. This is the value to pass to `mark_read`. Because a narrowed listing or a time-based listing never offers one, an agent following the result can't skip records it hasn't shown.
- **`marker`** is the marker's value when the listing was read.

**What 225 combines.** `decisions` covers every answered question. A PM answer carries the `waiting_reason` of a question that waited. `status`'s `waiting_on_pm` covers every question that is still unanswered, abandoned ones included (D4). So 225 counts questions sent to the PM, by reason, from both operations together, and no question is missing from both.

**Dependency on 223.** `based_on` for a PM answer reads `waiting_reason`, so 223's `answer` must not clear `waiting_reason` or `waiting_detail` when it sets the question to `answered`. 223 D9 doesn't clear them. A test in this slice pins that behavior.

### D6 — Member names
Status: decided

`status` and `decisions` show each member as `{id, name}`, because Context Forge ids are unreadable to the PM. Names are never stored (222 D3). `upstream/context_forge/projects.py` has `project_names(run) -> dict[str, str] | CfCallFailed`. It makes one `cf list projects --json` call per operation, and reads only `id` and `name`, because `projectPath` is optional in real output. A member id missing from the list is a `ContextForgeError` naming the id, because `set_up` registers only Context Forge projects. `CfCallFailed` is raised as `ContextForgeError`, exit 3, as everywhere since 222. The parser's fixture is real output (D10).

### D7 — `mark_read`
Status: decided

`mark_read(store, document) -> MarkReadResult`, validated into `MarkReadRequest(through: int ≥ 0)`.

- One `BEGIN IMMEDIATE` transaction reads `MAX(answers.seq)`. If `through` is higher, the result is `rejected / beyond_last_record`, and the marker doesn't move. A caller can't have seen a record that doesn't exist.
- Otherwise the transaction runs `UPDATE pm_marker SET last_seen_seq = MAX(last_seen_seq, :through)`. The outcome is `moved`, or `unchanged` when `through` is not past the current marker. The marker never moves backward. So two agents marking at the same time, from listings of different ages, leave the higher value.
- There is no "mark everything" form. A record written between a `decisions` call and `mark_read` has a higher `seq` than anything the caller saw, so it stays unread.
- The result holds `outcome`, `previous` and `current`.

### D8 — Result shapes and CLI
Status: decided

```
amoeba status [--program <id>]
amoeba decisions [--since <iso-8601>] [--program <id>]
amoeba mark_read --through <seq>
```

`StatusResult`, per member in scope:

```yaml
programs:
  - program: trading
    members:
      - member: {id: project_17…, name: trading-core}
        runs:                      # every listed run placed in this member
          - {run_id, pipeline, status, working_directory,
             checkpoint: {kind, paused_at, question} | null,
             pause: <PauseClass | run_file_unreadable> | null,
             detail, next}
        waiting_on_pm:             # every waiting question (D4)
          - {run_id, paused_at, question, slice_label, waiting_reason, waiting_detail, since,
             run_state, next}
unplaced_runs: [{run_id, status, reason}]
```

- A missed hook is a run whose `pause` is `unhandled` or `claim_stale`. An unresumed answer is a run whose `pause` is `answered_unresumed`, and its `detail` gives the resume outcome and the reason. These have no lists of their own: the `pause` class already identifies them.
- `next` is `{operation, run_id, paused_at?, directory?}`, or null when no operation applies. It names the operation and its inputs. For `unhandled`, `claim_stale` and `answered_unresumed` it is `handle_pause`, with the run's listed `working_directory` as the `cwd` that `handle_pause` needs (223, "Provides to 226"). For a waiting question at its pause it is `answer`. The values come from the records and the listing. Nothing is a placeholder.
- Exit codes use 222's constants. `0` for a result. `1` for `rejected` (`unknown_program`, `malformed`, `beyond_last_record`). `2` for a usage error. `3` for an operational error: `SquadronError`, `ContextForgeError`, `ConfigError`, `AmoebaHomeError` or any `StoreError`.
- `status` loads the config for `answering_wait_seconds`. `decisions` and `mark_read` don't load it.

### D9 — The store holds no mirrored state
Status: decided

`tests/store/test_schema_holds_no_mirrored_state.py` migrates a new store to `EXPECTED_SCHEMA_VERSION` and reads every table and column through `PRAGMA table_info`.

- **Inventory.** The full set of `(table, column)` pairs is pinned in the test. `docs/store-contract.md` lists each column under one of four reasons for being stored: record, membership, settings, or the PM's marker. A new column fails the test until both are updated, so a reviewer sees each addition and its reason. This is the only check: it catches a mirrored column whatever it is named.
- `questions.checkout` and `questions.slice_label` are in the inventory as record. They are what the claim recorded and what the question was asked about, and the code never reads either as current state.

### D10 — Fixtures and tests
Status: decided

- **Real output** in `tests/fixtures/`: `cf list projects --json` from CF 0.19.26, including an entry with no `projectPath`. Once #303 lands: `sq runs list --json` with a running run, a paused agent question, a paused run of another kind, a run with a `null` directory, and the older paused run and other-directory paused run that D1 requires.
- **Unit tests**, using a fake `sq` and a fake `cf` as in 222 and 223:
  - Every `PauseClass`, and D3's cross-check against `handle_pause`.
  - D4's placement rules, including two worktrees on one member, and a `cf` failure on one directory giving a `lookup_failed` run while the rest of `status` is shown. A waiting question listed with each `run_state`.
  - D2's three scope cases.
  - D5's starting points, narrowing, and `read_through` being null in each case that requires it.
  - D7's `moved`, `unchanged`, `beyond_last_record`, and two concurrent `mark_read` calls leaving the higher value.
  - The `waiting_reason` retention pin (D5), D4's skip of answering scratch directories, and the schema test (D9).
- **Live tier** (`tests/live/status/`, outside the default suite, needs Squadron with #303). It automates Verification Walkthrough steps 1 to 4 in a throwaway worktree registered as a member, using 223's live fixture pipeline.

### Technology Choices

No new packages. pydantic for the request and result models, and `argparse` subcommands in the existing `cli/main.py`, as in 222 and 223.

### Patterns and Conventions

- Request models validate unparsed input inside the operation, so the CLI and 226 pass input through unchanged (222 D7).
- Every vocabulary (`PauseClass`, the unplaced reasons, the rejection codes, `mark_read` outcomes) is a `StrEnum`, defined once.
- No subprocess runs inside a store transaction. `status` reads the store first, then calls `sq` and `cf`.

## Implementation Details

### API Contracts

The CLI and result shapes are in D8.

**Python (for 225 and 226)**

- `operations.status.status(store, config, document: object, *, directory, deps) -> StatusResult`
- `operations.decisions.decisions(store, document: object, *, deps) -> DecisionsResult`
- `operations.mark_read.mark_read(store, document: object) -> MarkReadResult`
- `operations.pause_class.classify_pause(...) -> PauseClass`
- `upstream.squadron.run_list.list_runs(run)`, and `upstream.context_forge.projects.project_names(run)`
- `deps` is 223's bundle plus the `list_runs` and `project_names` callables.

### Database / Storage Schema

No change. Reads: `programs`, `members`, `questions` (with 223's columns), `answers`, `pm_marker`. Write: `pm_marker.last_seen_seq`. `docs/store-contract.md` gains D9's column inventory and its reasons.

## Integration Points

### Provides to Other Slices

- **225**: the trial's counts, from `decisions` and `status` as D5 ("What 225 combines") describes.
- **226**: three more operations, with request and result models, to wrap with the same names. `status`'s run entries with a `handle_pause` `next` give the directory that MCP passes as `cwd` when it starts `handle_pause` detached.

### Consumes from Other Slices

- **223**: the question record and `handle_pause`. D3 changes `handle_pause` internally, and all of 223's tests must still pass.
- **222**: the store, the config and member resolution. Store reads that are missing are added to `store/questions.py` or `store/programs.py`, never copied into operations.
- **Squadron #303**: see D1. If `sq` fails, `status` stops with `SquadronError`. `decisions` and `mark_read` don't call `sq`.
- **Context Forge**: if `cf` fails, `status` and `decisions` stop with `ContextForgeError`. `mark_read` doesn't call `cf`.

## Success Criteria

### Functional Requirements

- `status` on a program with a running run, a paused agent-question run with a waiting question, an unresumed answer, a paused run of another kind, and a paused question run with no record shows each with the right `pause` class and `next` action, and the waiting question in `waiting_on_pm`.
- A missed hook from `status`, passed to `handle_pause` from its listed directory, is answered and resumed, and the next `status` no longer lists it.
- A waiting question whose run has moved past its pause, or is no longer listed, still appears in `waiting_on_pm`, with `run_state` `moved_on` or `not_listed` and no `next`. An answered question whose run has moved on appears in `decisions`.
- `status` from a member's checkout shows that program. With `--program` it shows the named program, and an unknown program is rejected. From outside every member it shows all programs.
- `decisions` with no `--since` lists only records newer than the marker, oldest first. `--since` lists by time. `--program` narrows the listing. `read_through` is non-null only for an unnarrowed listing that starts at the marker.
- `mark_read --through S` moves the marker to `S`, never backward and never past the newest record. A record written after the `decisions` call stays unread.

### Technical Requirements

- D9's schema test passes, and nothing in the store holds run status or slice state.
- `handle_pause` and `status` share `classify_pause`, and D3's cross-check test passes.
- All of 223's tests still pass.
- The `sq runs list --json`, run file and `cf list projects --json` parsers pass on recorded real output.
- Format, lint, typecheck and the default test suite pass. The live tier passes against Squadron with #303.
- `docs/store-contract.md` and the CLI contract document the three operations, their exit codes and D9's inventory.

### Integration Requirements

- 225 can compute its counts as D5 describes.
- 226 can wrap `status`, `decisions` and `mark_read` with no logic of its own, and start `handle_pause` for a missed hook using the directory `status` gives.

### Verification Walkthrough

Draft. It needs Squadron with #303 and slices 222 and 223 in place. It uses a test home so the real store is untouched.

1. **Set up.** In a throwaway worktree of the amoeba repo:
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
2. **A missed hook.** Run 223's live fixture pipeline (under `tests/live/pause/`) in the worktree with `sq run`, with no hook configured, until it pauses on its question. Then run:
   ```bash
   amoeba status
   ```
   Expect the member's `runs` to hold the run with `pause: unhandled`, and `next: {operation: handle_pause, run_id: …, directory: <worktree>}`.
3. **Catch up.** From the directory that `next` names, run `amoeba handle_pause <run_id>`. Expect `resumed`. Run `amoeba status` again: the run shows `running` or its next state, and its `pause` is no longer `unhandled`.
4. **Decisions.** Run `amoeba decisions`. Expect one record with `answered_by: answerer`, its cited passages and check verdict, `resume.outcome: resumed`, and a numeric `read_through`.
5. **Mark read.** Run `amoeba mark_read --through <read_through>` and expect `moved`. Then run `amoeba decisions` and expect no records and `read_through: null`. Run `amoeba mark_read --through 999999` and expect exit 1, `beyond_last_record`.
6. **Waiting on the PM.** Run a pause whose question the rules don't settle, and let `handle_pause` decline it. `amoeba status` shows it under `waiting_on_pm`, with its reason and `next: {operation: answer, …}`. After `amoeba answer <run_id> --text "…"`, `amoeba decisions` shows a `pm` record whose `based_on.waiting_reason` is that reason.
7. **Scope.** From a directory in no program, `amoeba status` lists every program. `amoeba status --program nope` exits 1 with `unknown_program` and the known ids.

Steps 2 and 3 need #303. Until it lands, `amoeba status` exits 3, with a `SquadronError` saying that it needs `sq runs list --json`.

## Implementation Notes

### Development Approach

1. Extract `classify_pause` from `handle_pause`, with 223's tests passing unchanged (D3).
2. Add `decisions`, `mark_read`, the `project_names` reader and the schema test. None of these depends on #303.
3. Add `run_list.py` and `status` against fixtures in #303's proposed shape.
4. Once #303 lands: record the real fixtures, adjust `run_list.py` to the landed names, and run the live tier.

Effort: 3/5.

### Special Considerations

- `status` makes one `cf get` call per distinct run directory, after D4 skips Amoeba's answering scratch directories. Each call is bounded by the `cf` timeout. The count is the number of member checkouts and worktrees with listed runs. Matching directories against `projectPath` would save them, but 222 D6 rejected path matching.
- Answer text and question text are shown in full. Both come from the PM's own runs and answers, and the callers are agents.
