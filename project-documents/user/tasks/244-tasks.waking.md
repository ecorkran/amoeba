---
docType: tasks
slice: waking
project: amoeba
lld: user/slices/244-slice.waking.md
dependencies:
- 240-slice.requests
- 241-slice.push-and-presence
- 242-slice.hold-and-release
- 243-slice.notes-and-release-notes
projectState: Slices 220 to 229 are merged on main. Store schema version 5 (migrations
  001 to 005), state is in ~/.local/state/amoeba. Slices 240 (messages, send, sweep,
  migration 006), 241 (sessions, push, migration 007), 242 (hold and release, migration
  008, Deps.amoeba_script) and 243 (notes) are designed and tasked; this slice is
  built after all four are built and integrated, and adds migration 009. It is the
  last slice of the agent-messaging initiative.
dateCreated: 20261115
dateUpdated: 20261117
status: complete
turns: 20
promptTokens: 1094588
cachedTokens: 990721
cacheWriteTokens: 103841
completionTokens: 23703
durationSeconds: 159.8
costUsd: 0.751812
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.7518120000000001
    completionTokens: 23703
---

# Tasks: Waking

## Context Summary

- Working on slice 244 (design: `user/slices/244-slice.waking.md`; decisions D1 to D12 are cited by number). Effort 3/5, as the slice plan's entry 5 gives it. It delivers `members.wake_command` (set from the CLI), a wake that `send` starts for an `open` request when the recipient has no live session, no running wake and is under its daily limit, the `amoeba wake-run` wrapper, the `wakes` table, `list` and `status` lines for waking, and a live test with a fixture agent.
- Paths: a path without a prefix is under `src/amoeba/`; `tests/`, `docs/` and `project-documents/` paths are from the repo root, and `user/` means `project-documents/user/`.
- Built names: 240 to 243 are designed but not built, so the design names their modules by role. Task 0.1 finds each built name and records it; later tasks use the role names and mean the built name. Roles: `send` and its request branch (`operations/send.py`, `send_write.py`), `resolve_recipient` (`operations/message_member.py`), `SendResult` (`operations/message_models.py` or its results module), the sweep (`store/message_sweep.py`: `sweep`, `sweep_due`) and `sweep_messages` (`operations/message_sweep.py`), `MemberStatus` (`operations/status_models.py`), 241's `live_member_ids` and config key `session_stale_seconds`, 242's `Deps.amoeba_script` and `START_BOUND_SECONDS`, 240's `tests/test_message_timing.py`.
- Modules and names, from the design's Component Structure: `store/wakes.py`, `store/sql_wakes.py`, `operations/wake.py` (`wake_after_send`), `operations/wake_run.py` (`run_wake`), `operations/wake_status.py`. Closed values are defined once: `WakeOutcome` (in `store/vocabulary.py`), `WAKE_ENV_NAMES`, `WAKE_WINDOW`, `WAKE_BOUND_SECONDS`, the `wake` log directory name, `LIVE_WAKE`. No silent fallbacks; a swallowed exception names one type and carries a comment saying why. The one `except Exception` is the wrapper's process boundary (D6).
- Modules already over ~300 lines (`wiring.py` 342, `store/sql.py` 484) get no new logic: new code goes in new modules and the old file gains only a call. A new module that passes ~300 lines is split by concern.
- Import direction stays `cli/mcp → wiring → operations → store, upstream`; the store imports nothing from `operations`. `wake-run` is CLI-only: no `OperationName`, no MCP tool, no result model (D6).
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. "Checks pass" means all four, with no failure beyond the baseline noted in 0.2. The live tier is `uv run pytest tests/live/<dir>` (never part of a bare run; LLM spend is pre-authorized, and this slice's live test spends nothing).
- Tests use the autouse `AMOEBA_HOME` fixture, the stub `cf` (`tests/cf_stub.py`, `tests/cf_fixtures.py`), `tests/store/seed.py`, `tests/user_configs.py` (`example_config_text` loads the config contract's example), `tests/git_repo.py`, a settable clock and a real short-lived child for `wake_run`. Destructive SQL only against throwaway stores. No sample id, hash or timestamp sits near a value an agent must fetch (hallucination-trap rule), including docs that tests check.
- `tests/test_contract_docs.py` requires every new column, table, field, flag and config key in the contract docs, so each task that adds one adds its entry then. Section 8 writes the prose and the parent-document amendments.
- No existing test function or assertion in the 240 to 243 suites changes, except the ones tasks 2.1, 4.4, 6.1 and 6.8 name (the stale schema-version assertions and pin, the `add` flag-list pin, the `resolve_recipient` return comparison, 240's worst-case sum in `tests/test_message_timing.py`); every other task only adds test functions, or a config key in an existing fixture (1.2). If an existing test fails for a legitimate reason, fix the new code, not the test.
- Production state: sections 0 to 10 write no live store or config; tests use throwaway stores and a throwaway `AMOEBA_HOME`. The live migration, with backups and their removal, is the Phase 7 hand-off checklist at the end of this file. The "Amoeba Design Rules" block of `CLAUDE.md` designates the live store and config for migrations.
- Work on branch `244-slice.waking` (created in 0.2). Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.

## 0. Setup

- [x] **0.1 Target and prerequisites**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. `git checkout {target}`; the planning documents (design, this file) are committed there, with no other uncommitted change
  - [x] Confirm the prerequisites exist, by the designed name or another (a role built under another name is mapped in the next item, not blocked): `store/schema/` holds `001` to `008` and `EXPECTED_SCHEMA_VERSION` in `store/migrations.py` is 8; `send` has a request branch and a separate note path (243); `resolve_recipient` exists; `store/message_sweep.py` has `sweep` and `sweep_due`; `operations/message_sweep.py` has `sweep_messages`; `MemberStatus` exists; 241's `live_member_ids` and `session_stale_seconds` exist; `Deps.amoeba_script` and `START_BOUND_SECONDS` exist (242); `tests/test_message_timing.py` exists; `upstream/context_forge/project_of.py` returns `projectPath`. If a role has no built module at all, write `BLOCKED: <what>` under this task and stop (240 to 243 must be built and integrated first)
  - [x] Record in a note the built name of each role, and the signatures of `resolve_recipient`, `live_member_ids`, `sweep` and `sweep_due`
  - [x] Success: the target is checked out and clean; a note under this task gives the target and the role-to-built-name list

  Note: Target is `main` (integration_branch empty); prerequisites verified: schema 001-008, EXPECTED_SCHEMA_VERSION 8, `store/message_sweep.py` (`sweep(transaction, now, prune_after_days)`, `sweep_due(transaction, now, prune_after_days) -> bool`), `operations/message_sweep.py` (`sweep_messages(store, config, now)`), `MemberStatus` in `operations/status_models.py`, `live_member_ids(transaction, now, stale_seconds) -> frozenset[str]` in `store/sessions.py`, config `session_stale_seconds`, `Deps.amoeba_script` in `operations/deps.py`, `START_BOUND_SECONDS` in `operations/request_release.py`, `tests/test_message_timing.py`, `project_of` returns `CFProject.project_path`. Role-to-built-name: `send` request branch = `operations/send.py` + `operations/send_write.py` (`write_send`), note path = `operations/send_note.py`; `resolve_recipient(store, reference, run) -> str | Refusal` in `operations/message_member.py`; `SendResult` in `operations/message_results.py` (re-exported by `send.py`); `SendRequest`/`SendOutcome` in `operations/message_models.py`. All designed names exist; nothing blocked.
- [x] **0.2 Branch, baseline and design alignment**
  - [x] `git checkout -b 244-slice.waking {target}`; if the branch exists, `git checkout 244-slice.waking`
  - [x] Run the checks once and note the baseline. Failures present before this slice are listed by test name and not fixed
  - [x] Amend `user/slices/244-slice.waking.md` on this branch (the target takes no commit during Phase 6): in Special Considerations' Live store paragraph, install from the target at the Phase 7 hand-off, after the merge (the design says "from the slice branch", but an install before the merge would leave the installed tool refusing the store), delete the two backup files once the read-back passes (the design says "after the review passes"; the hand-off itself runs after it), and take "the previous code" as the target commit recorded in 10.1; in Development Approach, step 7 is the Phase 7 hand-off; in Departures, drop the "Dependencies" bullet's amendment of the plan's entry, since that entry already reads 240, 241, 242, 243
  - [x] Success: `git branch --show-current` prints `244-slice.waking`; a note under this task gives the baseline result; `grep -n "from the slice branch" user/slices/244-slice.waking.md` finds nothing

  Note: Branch `244-slice.waking` checked out. Baseline before any change: `ruff format --check`, `ruff check`, `pyright` clean; `pytest -q` 3774 passed, no failures (full run takes ~3 min). Design amended (Live store paragraph, Development Approach step 7, Departures Dependencies bullet dropped).

**Commit**: `docs: align the 244 design with its task breakdown`

## 1. Config keys (D8; Development Approach step 1)

- [x] **1.1 `wake_timeout_seconds` and `max_wakes_per_day`**
  - [x] `config/user_config.py`: add `wake_timeout_seconds` (a number greater than 0) and `max_wakes_per_day` (an integer of at least 1), each required with no default in code, the same type pattern as `answering_wait_seconds` and `prune_after_days`
  - [x] `docs/config-contract.md`: both keys in the key table and in the `## Example` block (the one place the suggested values appear), with one line each on what is stopped or limited and what happens when hit (D7). Zero is not a way to turn waking off: clearing `wake_command` is (D8)
  - [x] Success: pyright clean; tests that load the example config still pass
- [x] **1.2 Config tests**
  - [x] `tests/config/test_user_config.py` (added functions): each key missing fails with `ConfigError` naming the key; a zero or negative `wake_timeout_seconds`, a zero `max_wakes_per_day` and a non-integer `max_wakes_per_day` each fail naming the key; `example_config_text()` loads with both keys. If a fixture config in an existing test lacks the keys, add them to that fixture only (no assertion changes)
  - [x] Success: checks pass

  Note: the existing missing-key parametrization in tests/config/test_user_config.py reads TOP_LEVEL_KEYS, so the two keys were added to that list (fixture list only) and to tests/user_configs.py::user_config.

**Commit**: `feat: add wake_timeout_seconds and max_wakes_per_day config keys`

## 2. Migration 9: `wake_command` and `wakes` (D3; step 1)

- [x] **2.1 Vocabulary, migration and `Wake`**
  - [x] `store/vocabulary.py`: `WakeOutcome` with `exited`, `timed_out`, `start_failed`, `wrapper_failed`, one-line comment each
  - [x] `store/schema/009_wakes.sql`: `ALTER TABLE members ADD COLUMN wake_command TEXT`, and `CREATE TABLE wakes` with the D3 columns: `wake_id` text primary key, `member_id` referencing `members`, `directory` (null only for a `start_failed` row with no path), `command`, `started_at`, `deadline_at`, `log_stem`, `command_pid`, `ended_at`, `outcome`, `exit_code`, `detail`. Table `CHECK`s: `ended_at` and `outcome` both null or both set; `exit_code` set only for `exited`; the `outcome` list equals `WakeOutcome`. Indexes on `(member_id, started_at)` and `(started_at)`. Header comment: `ADD COLUMN` and `CREATE TABLE` only, so existing rows are untouched. `EXPECTED_SCHEMA_VERSION` (in `store/migrations.py`) becomes 9
  - [x] `store/models.py`: frozen dataclass `Wake` with the row's fields; the members model gains `wake_command` (nullable). Existing member readers keep working, so a reader that builds a member from a row reads the new column explicitly
  - [x] `docs/store-contract.md`: the column, the table and each of its columns, who writes each (the claim writes the row; `command_pid` and the end fields are written by the wrapper, or by `wake_after_send` for a start failure), the `WakeOutcome` values, version 9, and the retention rule (D10). Update stale-version assertions in the store migration tests and the schema pin in `tests/store/test_schema_holds_no_mirrored_state.py`; these are the only existing tests this task edits
  - [x] Success: pyright clean; existing store tests pass

  Note: existing tests edited: tests/store/test_schema_holds_no_mirrored_state.py (pin + new `waking` reason), tests/store/test_vocabulary_pinning.py (wakes.outcome added to the enum map), tests/store/test_schema.py (TABLES gains `wakes`; test renamed to thirteen) and tests/test_contract_docs.py (table count 12 to 13); helper tests/store/seed.py::insert_member gained an optional `wake_command`. No assertion about earlier behavior changed. No existing test pinned the schema version 8 literally (they use EXPECTED_SCHEMA_VERSION).
- [x] **2.2 Migration test**
  - [x] `tests/store/test_migration_009.py` (model on the latest migration test, e.g. `test_migration_006.py`): a version-8 database with members, programs and messages migrates to 9 with every existing row field-for-field equal, `wake_command` null for each member, `wakes` present and empty, `foreign_key_check` empty. The `outcome` `CHECK` list equals the `WakeOutcome` members (extend `tests/store/test_vocabulary_pinning.py`). The two `CHECK`s each reject a violating insert (an `outcome` without `ended_at`, an `exit_code` on `timed_out`) and accept a valid one. A store at version 10 is refused by the existing newer-schema guard
  - [x] Success: checks pass

**Commit**: `feat: add migration 9, the wakes table and members.wake_command`

## 3. `store/wakes.py` (D2, D3, D7, D9, D10; step 1)

- [x] **3.1 `LIVE_WAKE`, `claim_wake` and `can_wake`**
  - [x] SQL in `store/sql_wakes.py`, with `LIVE_WAKE` as the one predicate (row not ended and `deadline_at` later than now), used by the claim and every read. `WAKE_WINDOW` (24 hours) is one constant. Every function in `store/wakes.py` takes `now` as an argument and never reads a clock or config
  - [x] `claim_wake(transaction, member_id, now, wake_timeout_seconds, max_wakes_per_day, session_stale_seconds, wake_id, directory, log_stem)` as D2 states, in this order, stopping at the first failing check and returning the new `Wake` or nothing: (1) the member is active (`sql.ACTIVE_MEMBER`) with a non-null `wake_command`; (2) its id is not in `live_member_ids(transaction, now, session_stale_seconds)`; (3) no row of the member satisfies `LIVE_WAKE`; (4) fewer than `max_wakes_per_day` rows with `started_at` in `WAKE_WINDOW`, ended or not, any outcome; (5) insert the row with the given `wake_id`, `command` copied from the member, `deadline_at = started_at + wake_timeout_seconds`, and the given `log_stem`. The caller (6.3) makes `wake_id` (`uuid4().hex`) and `log_stem` (`<logs_dir>/wake/<wake_id>`, or null when `directory` is null), so the store reads no layout or config. With no directory it inserts the row already ended as `start_failed` with a reason in `detail` and returns nothing to start (D4)
  - [x] `can_wake(transaction, member_id, now, max_wakes_per_day, session_stale_seconds) -> bool`: the same checks 1 to 4 as a read, for `wake_after_send`'s pre-check; `claim_wake` calls the same code so the two never differ
  - [x] Success: pyright clean; the store module imports nothing from `operations`
- [x] **3.2 Claim tests**
  - [x] `tests/store/test_wakes.py` (clock passed in, no real time): the claim stops at the first failing check, one test per check and in the design's order (inactive or removed member; no command; a live session per 241's rule, where a session that is not push-confirmed does not block; a live row; the limit); a claimed row has the fields D3 lists and `deadline_at` fixed at the claim; a row whose deadline has passed is not live; a row ended earlier still counts toward the limit; the limit counts `start_failed` rows; a row 24 hours and one tick old no longer counts and the claim succeeds; a null directory inserts an ended `start_failed` row and returns nothing; `can_wake` and `claim_wake` agree over the same fixtures; a later edit of the member's `wake_command` leaves a stored row's `command` unchanged
  - [x] Success: checks pass
- [x] **3.3 Row reads, writes and prune**
  - [x] `get_wake(transaction, wake_id)`; `set_command_pid(transaction, wake_id, pid)`; `finish_wake(transaction, wake_id, outcome, exit_code, detail, now)` as a compare-and-set on `ended_at IS NULL` that returns whether it ended the row
  - [x] `wake_summary(transaction, member_id, now, max_wakes_per_day)`: what `list` shows (D9): the member's unended row with an `overdue` flag (true when the row is not live, decided by the negation of `LIVE_WAKE`, the one predicate), the count of rows in `WAKE_WINDOW`, and the newest ended row
  - [x] `prune_wakes(transaction, cutoff)`: deletes rows with `started_at` before the cutoff whatever their state, returns the count; `wakes_due(transaction, cutoff)` reads whether any is aged
  - [x] Success: pyright clean
  Note: `wake_summary(transaction, member_id, now)` takes no `max_wakes_per_day` (the limit is not needed to read the three parts; `wake_status` compares `used_in_window` with the limit). `overdue` is `NOT (LIVE_WAKE)` evaluated in SQL (`SELECT_UNENDED_WAKE`), so the predicate is written once. A member with several unended rows shows the newest by started_at.
- [x] **3.4 Tests for 3.3**
  - [x] `tests/store/test_wakes_rows.py`: `finish_wake` ends once and a second call returns false; `set_command_pid` is shown by `get_wake`; `prune_wakes` deletes an unended aged row and keeps a young one; `wakes_due` is true for an aged row and false for a young one; `wake_summary` returns the three parts, with `overdue` false for a live unended row and true for an unended row past its deadline
  - [x] Success: checks pass

**Commit**: `feat: add the wakes store, claim and limit checks`

## 4. `wake_command` through `add` (D1; step 2)

- [x] **4.1 `MemberRequest.wake_command` and its write**
  - [x] `operations/set_up_models.py`: `MemberRequest.wake_command: NonBlankText | None`, omitted meaning leave it and null meaning clear it, told apart by `model_fields_set` as `concept` is (read how `concept` does it first). A validator splits the text with `shlex.split` and rejects an unsplittable text, a text with no tokens, and a NUL or a newline, naming the field. The executable is not looked up (D1)
  - [x] `operations/set_up_resolve.py` and the member writer: carry the value to the row; leave, set and clear as above. `operations/list_registry.py`: `list members` returns each member's `wake_command`
  - [x] Success: pyright clean
- [x] **4.2 Operation tests**
  - [x] `tests/operations/test_add_wake_command.py`: set; clear with null; omitted leaves an existing value; a second `add` of other settings leaves it; blank, whitespace-only, unbalanced quotes, NUL and newline are each rejected naming `wake_command`; a text with an executable that does not exist is accepted; `list members` returns the command and null for a member without one
  - [x] Success: checks pass
- [x] **4.3 CLI flags and the bulk document**
  - [x] `cli/registration_arguments.py` and the parser: `--wake-command COMMAND` and `--no-wake-command`, mutually exclusive, working directly, with `--project` and through `--file` (bulk JSON key `wake_command`: omitted leaves, null clears). `add --help` says the command runs unattended with the user's privileges, with only the `WAKE_ENV_NAMES` variables, is shown in plain text and so carries no secret, and must carry its own cost or time cap (Amoeba cannot check it). `cli/render/registry.py`: `list members` text shows the command on a `wake command:` line for a member that has one and no such line for one that does not; `-j` carries `wake_command` as the string or null
  - [x] `docs/cli-contract.md`: the two flags and the bulk key (the section on the contract is 8.1); `docs/mcp-server.md`: one row stating the `add` tool does not take `wake_command`
  - [x] Success: pyright clean
  Note: the MCP door is closed by `operations/add_door.py` (`refuse_door_fields`, `WAKE_COMMAND_DOORS`), called from `wiring_registry.place_add` with the door, since both doors share `add`'s validation; the published schema omits the field with `SkipJsonSchema`. `wiring.py` only passes `door` on. Existing tests edited (pins/fixtures, no behavior assertion changed): tests/cli/test_list_cli.py and tests/operations/test_list_registry.py (the member JSON key-set pin gained `wake_command`), tests/cli/render/test_registry.py (its `_member` helper gained `wake_command: None`). No test pinned the exact `add` flag list.
- [x] **4.4 CLI and MCP tests**
  - [x] `tests/cli/test_add_wake_command_cli.py`: `--wake-command` sets, `--no-wake-command` clears, both together are a usage error, `--project` from another directory, `--file` with set, omitted and null, an unsplittable text exits non-zero naming the field; `list members` text and `-j` show it, and for a member without one the text has no `wake command:` line and `-j` has null. If a 227 to 229 CLI test pins the exact `add` flag list, change only that assertion to include the two flags and say which test in a note
  - [x] MCP: `tests/mcp_server/test_tools.py` (added function): the `add` tool's input schema has no `wake_command`, and a call passing it is rejected as an unknown field
  - [x] Success: checks pass

**Commit**: `feat: set and clear wake_command with add and show it in list members`

## 5. `amoeba wake-run` (D5, D6; step 3)

- [x] **5.1 `operations/wake_environment.py`**
  - [x] `WAKE_ENV_NAMES` (`PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG`, `LC_ALL`, `TMPDIR`, `AMOEBA_HOME`) as one constant; `build_wake_environment(environ)` copies only those names that are set, nothing else
  - [x] `wake_detail(error)`: the one place a `detail` text is made. For an `OSError` the exception class and its `strerror` (never the filename); for anything else the class name. It never holds argv text
  - [x] Success: pyright clean
- [x] **5.2 Tests for 5.1**
  - [x] `tests/operations/test_wake_environment.py`: with `SENDER_SECRET_MARKER` and `AMOEBA_HOME` set among others, the result holds exactly the `WAKE_ENV_NAMES` names that were set, none other, and not the marker; a name that is unset is absent, not empty. `wake_detail`: a `FileNotFoundError` for a path holding a marker gives class and `strerror` without the marker; a `ValueError` gives its class name only
  - [x] Success: checks pass
- [x] **5.3 `operations/wake_run.py`: `run_wake`**
  - [x] `run_wake(store, deps, wake_id, popen: WaitablePopen = subprocess.Popen)` as D6 states, with the clock from `deps.clock`. `popen` is the seam that starts the command: the existing `WaitablePopen` type (`operations/processes.py`, a Popen-shaped callable returning a `WaitableChild` with `pid` and `wait`), called with the argv, `cwd`, the explicit `env`, `start_new_session=True`, stdin `DEVNULL` and stdout and stderr inherited; its production default `subprocess.Popen` is stated once, in this signature. `deps.spawn` (`start_child`) is not used here: it makes its own log files, and the wrapper's stdout and stderr already are the wake's logs. Before the command: a `StoreError`, a missing row or an already ended row raises to the caller (exit 3, nothing recorded); a command text that cannot be split or an `OSError` from the start records `start_failed` with `wake_detail` and returns the exit-1 result. Run: start in a new session in the row's directory with `build_wake_environment`, stdin `DEVNULL`, stdout and stderr inherited; one short write sets `command_pid` (a held store there is a logged warning and the wait goes on); `child.wait(timeout=max(0, deadline_at - now))`; outcome `timed_out` on timeout, else `exited` with the code; then `terminate_group` either way; `finish_wake` in one short write bounded by `BUSY_TIMEOUT_SECONDS` (a failure to write is logged and raised: exit 3, row as in the first case). The traceback of any failure goes to the stderr log only
  - [x] Success: pyright clean; the file about 200 lines or less

  Note: 5.5's boundary is written in the same function as 5.3 (one `run_wake`). `AMOEBA_HOME` is not written in `wake_environment.py`: `tests/test_home_access.py` allows only `config/home.py` to name it, so `WAKE_ENV_NAMES` takes `HOME_VARIABLE` from there. `run_wake` returns the recorded `WakeOutcome` (the CLI maps it to exit 0, 1 or 3); a missing or ended row raises `WakeRunError`. In the tests, `__CF_USER_TEXT_ENCODING` (added by macOS to every process) is excluded from the environment check, and the secret-like marker is checked in `detail`, the log text and every row field except `command` (the row keeps the command it ran, D3).

**Commit**: `feat: add the wake wrapper logic`

- [x] **5.7 The `wake-run` subcommand**
  - [x] `cli/parser.py`, `cli/main.py` and `cli/commands.py`: register `wake-run WAKE_ID` as a CLI-only subcommand (no `OperationName`; read how `handle-pause` is registered and how `tests/cli/test_parser_names.py` pins the list, and add one named constant for the CLI-only names so that test says what it allows). Its branch in `main` comes before the config load and before the operation lookup: it opens the store through `open_state_store(layout)`, calls `run_wake`, and exits 0 when a command ran and was recorded as `exited` or `timed_out`, 1 for `start_failed`, 3 for an operational failure with one stderr line, which includes `wrapper_failed` (D6 reads the wrapper's own unexpected error as operational; its row is still recorded). The command is listed like any other in `--help`, and named in `docs/cli-contract.md` as started by Amoeba and not meant for people
  - [x] Success: pyright clean

  Note: the wrapper's code is in a new module `cli/wake_command.py` (not `commands.py`) to keep `commands.py` small; `main` also catches `WakeRunError` beside `OPERATIONAL_ERRORS`. `tests/mcp_server/test_tools.py::test_tool_names_are_the_operation_names_and_the_cli_commands_their_cli_names` also pins the command list, so its assertion subtracts `CLI_ONLY_COMMANDS` too.

- [x] **5.8 Subcommand tests**
  - [x] `tests/cli/test_wake_run_cli.py`: through `main`, with a throwaway store holding a claimed row and a real short command, exit 0 and the row ended; a missing executable exits 1; a `wrapper_failed` (`run_wake`'s `popen` patched to return a child that raises after the start) exits 3 with the row recorded; a missing row exits 3 with one stderr line and no traceback; a config file with the new keys missing does not stop the wrapper (no config is loaded); `tests/cli/test_parser_names.py` passes with the named constant
  - [x] Success: checks pass

**Commit**: `feat: add the wake-run subcommand`

## 6. The wake step in `send` (D2, D4, D5, D10, D11; step 4)

- [x] **6.1 `resolve_recipient`, `wake_command` and `wake_problem`**
  - [x] `resolve_recipient` returns `Recipient(member_id, project_path)`, `project_path` null when Context Forge did not know the reference (D4). Update its callers; if a 240 test compares its return to a bare id, change only that assertion and say which test in a note (the only permitted edit to an existing assertion in this task)
  - [x] `send`'s own write transaction reads the recipient's `wake_command` with the member row it already reads (no second read). `SendResult` gains `wake_problem` (string or null, null when nothing went wrong); the text renderer prints it as a line; `docs/cli-contract.md` and `docs/mcp-server.md` list the field
  - [x] Success: pyright clean; 240 to 243 `send` tests pass

  Note: `Recipient` also carries `wake_command`. `send` has no member read of its own for the recipient: `resolve_recipient` already reads the active member row (one read), so that read supplies the command and no second read exists; `send_write.py` is unchanged. The claim re-reads the member and is authoritative, so a command set or cleared between the two reads is settled by the claim. Existing assertions edited: `tests/operations/test_message_member.py::test_a_name_and_an_id_both_resolve_a_recipient` (the permitted one: compares `.member_id`) and `tests/test_wiring.py::test_the_message_documents_are_json_with_enums_as_strings` (its exact `send` document pin gained `wake_problem: None`).

- [x] **6.2 Tests for 6.1**
  - [x] `tests/operations/test_resolve_recipient.py` (added): the path is returned for a known reference and null for a reference read as an id. `tests/operations/test_send.py` (added): `wake_problem` is null on a normal send; `send` reads the recipient's `wake_command` in the same transaction (a test counts store opens for a recipient with no command: one open, as before this slice)
  - [x] Success: checks pass

**Commit**: `feat: return the checkout path from resolve_recipient and add wake_problem`

- [x] **6.3 `operations/wake.py`: `wake_after_send`**
  - [x] `wake_after_send(open_store, config, deps, recipient, wake_command)` returns a problem line or nothing, and is called by the request branch after the request's transaction has committed, and only while the request is `open` (outcome `sent`, or `unchanged` with the stored request still `open`; never for `accepted`, never from the note path). A recipient with no `wake_command` ends there: no store open
  - [x] Otherwise: open the store once, run `can_wake` in a read transaction (stop with no write lock when it fails), then `claim_wake` in one write transaction passing the checkout path, a fresh `uuid4().hex` as `wake_id` and `log_stem` built from `deps.logs_dir` (null with no checkout path). If a row is returned: `deps.amoeba_script()` and `deps.spawn([script, "wake-run", wake_id], checkout, LaunchLogs(...))` with logs `<logs_dir>/wake/<wake_id>.stdout.log` and `.stderr.log` (`log_stem` is the path without the suffix; the directory name is a constant); return without waiting. `LaunchError` (a value) and `AmoebaScriptMissing` (caught by type, with a comment that raising would report a failure for a request already written) are each recorded as `finish_wake(start_failed, <text>)` and logged with `logger.error`. A `StoreError` anywhere is caught by type, logged with `logger.exception`, and returned as one line; any other exception propagates (D2)
  - [x] `send`'s request branch calls it and sets `SendResult.wake_problem`; `send` exits as 240 says whatever the wake step did. The wake step makes no `cf` call, no `ps` call and never waits for the wrapper
  - [x] `WAKE_BOUND_SECONDS = 5 × BUSY_TIMEOUT_SECONDS` defined once here (D11)
  - [x] Success: pyright clean; `send.py` gains only the call

  Note: `wake_after_send(store, config, deps, recipient)` takes the open store `send` already has instead of an `open_store` factory (send is given a Store, so the wake step opens nothing: fewer waits than D11's 5 counts, so the bound only got safer) and reads `recipient.wake_command` (see 6.1). `wake_for_sent_request` holds the "request is open" rule (outcome sent, or unchanged with the stored request open) and sets `wake_problem` on the result; `send.py` gains only that call. `WAKE_RUN_COMMAND` lives in `operations/wake_run.py` (the CLI imports it). `_record_start_failure` returns nothing: the request is never changed by a wake failure. In 6.6 "opens the store no second time" is tested as "takes no store transaction in the wake step" (0 for no command; 1 read and 0 writes when the pre-check fails; 1 read and 1 write when it claims).
- [x] **6.4 Tests: when a wake starts and when it does not**
  - [x] `tests/operations/test_wake_after_send.py` (fake `spawn`, fake clock): a request to a member with a command, no live session and no live wake claims one row and spawns `[script, "wake-run", <id>]` in the checkout with the two log paths; a second send while the row is live spawns nothing; a push-confirmed session blocks the wake and a session without push confirmation does not; no command, a removed member and a note (to a member that has a command) spawn nothing; a null checkout path inserts a `start_failed` row, spawns nothing and the request stays `open`; a `LaunchError` and a missing script each end the row `start_failed` with the reason and leave the request `open`
  - [x] No message text reaches the wrapper: send a request whose subject and body hold marker strings and check the spawn's argv and log paths for them (the command itself is checked in 9.2)
  - [x] Success: checks pass
- [x] **6.5 Tests: the limit and the retry**
  - [x] Added to the same file: the limit stops the wake with no row written, the request stays `open` and in the recipient's `inbox`, and with the clock past the request's TTL the sweep expires it and the sender's `inbox` reports the end (240's own rig and expiry path); with the clock 24 hours and one tick past the oldest counted row the next send wakes; with `max_wakes_per_day` failing sends to a member whose command cannot start, the next send spawns no wrapper
  - [x] Retry rules: a same-id retry answering `unchanged` for an `open` request wakes when no wake is live and the limit allows (after a start failure), and starts nothing while one is live; for an `accepted` request it starts nothing
  - [x] Success: checks pass
- [x] **6.6 Tests: store behaviour and failures**
  - [x] Added to the same file: a recipient with no command opens the store no second time (a test counts opens); a recipient whose pre-check fails (live session, live wake, limit) takes no write lock (a test checks the write path was never entered); a `StoreError` in the claim is returned in `wake_problem`, the request stays written and `send` exits 0 or 1 as 240 says; a `StoreError` while recording a start failure leaves the row unended with the problem returned
  - [x] Success: checks pass
- [x] **6.7 Two sends at once (load test)**
  - [x] `tests/load/test_wake_claim_load.py` (model on `tests/load/test_report_release_load.py`, collected the same way): `WRITERS` threads (a named constant), each with its own store connection and the real `send` with a fake counting `spawn`, send a request each to one member with a wake command, together. Assert: exactly one `wakes` row and one spawn; every request is `open` and in the member's `inbox` (the guarantee D2 gives the second sender); no `send` call exceeds `WAKE_BOUND_SECONDS` plus 240's own bound for `send`, and the burst finishes within a named budget constant. A second case sends to as many members as threads: one row and one spawn each. CI already gates the file: `ci.yml` runs a bare `uv run pytest` and `pyproject.toml` ignores only `tests/live` (confirm both and note it)
  - [x] Success: checks pass
- [x] **6.8 The timing test**
  - [x] `tests/test_message_timing.py` (240's test; one of the named edits to existing tests, see Context Summary and 10.1): add `WAKE_BOUND_SECONDS` to `send`'s worst case beside `START_BOUND_SECONDS`, still asserting the sum is below `MCP_CALL_DEADLINE_SECONDS` and that the failing-bound test still fails; assert `WAKE_BOUND_SECONDS` equals `5 × BUSY_TIMEOUT_SECONDS`. The design's figure is 160 s against 180 s; if the computed sum reaches the deadline write `BLOCKED:` with the numbers under this task
  - [x] Success: checks pass

**Commit**: `feat: start a wake from send for an open request`

- [x] **6.9 Sweep step and due check**
  - [x] `store/message_sweep.py`: `sweep` gains `prune_wakes` as a further statement, with the same `prune_after_days` cutoff and no signature change; `sweep_due` counts an aged `wakes` row as due, so a quiet store is still not write-locked by a poll. `operations/message_sweep.py` needs no change if it already calls `sweep_due`; confirm and note it
  - [x] Success: pyright clean

  Note: `operations/message_sweep.py` needed no change: it already calls `sweep_due`, which now counts an aged `wakes` row. `prune` was not changed: the `logs/wake/` tests pass with its existing rule (the second test removes the emptied directory in a single prune run, since a prune within the hour of another is skipped by `.last-prune`).

- [x] **6.10 Cleanup tests**
  - [x] `tests/store/test_message_sweep.py` (added functions): an aged `wakes` row is deleted by `sweep` whether ended or unended (the unended case is a row past its deadline, as a killed wrapper leaves it); a young row stays; `sweep_due` is true for an aged row alone and false for a young one. `tests/operations/test_message_sweep_wrapper.py` (added): `sweep_messages` on a store holding only an aged row writes; with a young row it opens no write transaction
  - [x] Logs: `tests/operations/test_prune.py` or the prune test file (added function): old and new files under `logs/wake/` are created in a throwaway state directory; `prune`'s existing rule removes the old files and the emptied directory and keeps the new. Do not change `prune` unless this test fails
  - [x] Success: checks pass

**Commit**: `feat: delete aged wakes rows in the sweep`

## 7. `list` and `status` (D9; step 5)

- [x] **7.1 `WakeStatus` and `operations/wake_status.py`**
  - [x] `operations/status_models.py`: `WakeStatus` (`command`, `running`, `stopped`, `last_problem`) and `MemberStatus.wake`, present only for a member with a `wake_command` (null otherwise), with the nested fields D9 lists. `running` holds the member's unended row (`started_at`, `deadline_at`, `command_pid`, `log_stem`) plus the `overdue` flag from `wake_summary` (3.3): a row past its deadline is in this field with `overdue` true, though it no longer counts as a live wake (the design's "stops reading as running at `deadline_at`" is the claim's `LIVE_WAKE`, and the display says overdue). `operations/wake_status.py` builds it from one `wake_summary` read: `stopped` is set when the count in `WAKE_WINDOW` has reached `max_wakes_per_day` (`used`, `limit`); `last_problem` is the newest ended row when its outcome is `start_failed`, `timed_out`, `wrapper_failed` or `exited` with a non-zero code. `status` and `list` call it; `list -j` still equals the `status` document; `Nothing needs you.` is unchanged by waking
  - [x] `docs/cli-contract.md` and `docs/mcp-server.md`: the `wake` field and each nested field, including `overdue` (the prose is 8.1)
  - [x] Success: pyright clean; the read-side-defined-once test still passes (`list` reuses `status`'s builder)
- [x] **7.2 `wake_status` tests**
  - [x] `tests/operations/test_wake_status.py`: no `wake` for a member without a command; a live row is in `running` with `overdue` false; a row past its deadline with a null `ended_at` is in `running` with `overdue` true, carries `command_pid` and `log_stem`, and the member can be claimed again (it is not live); at the limit `stopped` has `used` and `limit` and below it is null; each of the four problem outcomes is `last_problem`, and `exited` with code 0 is not; the newest ended row decides; an `exited` zero row after an older failure clears it; `list -j` equals `status`; `Nothing needs you.` holds with a running wake
  - [x] No argv text in the document: run `run_wake` (5.3) for a member whose command's executable name holds a secret-like marker, so the row ends `start_failed` through the real `detail` path; build the `status` document and assert the marker occurs only in the `command` field, not in `last_problem.detail` or any other field
  - [x] Success: checks pass
- [x] **7.3 The Waking section of the text renderer**
  - [x] `cli/render/` (the module that renders member status): a **Waking** section per D9: the command; `running since <age>, stops <time>` when `overdue` is false; when true `overdue since <time>: its wrapper is gone; the command's own cap ends it, or check and stop pid <pid>, log <path>` (with no pid text when `command_pid` is null); `waking stopped: <used> of <limit> wakes used in the last 24 h`; `last wake <outcome> <age> ago: <detail>, log <path>`. Reuse the existing age formatter
  - [x] Success: pyright clean

  Note: the Waking section prints the `last wake` line whole (no cut), since its log path is for copying and its detail is only an exception class and OS message; the log is shown as the row's `log_stem` (the path without `.stdout.log` / `.stderr.log`), as the contract says. Existing test edited: `tests/operations/test_status_requests.py::test_the_status_keys_gain_only_the_notice_and_the_two_member_fields` (its member key-set pin gained `wake`). `list -j` equals `status` is tested in test_wake_status.py.

- [x] **7.4 Renderer tests**
  - [x] `tests/cli/render/test_waking_section.py` (added): each of the four lines for a built `WakeStatus`; the overdue line with and without a pid; no Waking section for a member without a command; render the same marker-bearing `start_failed` member as 7.2 builds: the marker appears only on the command line and the `last wake` line holds none
  - [x] Success: checks pass

**Commit**: `feat: show waking per member in list and status`

## 8. Documents and amendments (D12, Departures; step 6)

- [x] **8.1 The wake-command contract and contract prose**
  - [x] The docs need to name no agent CLI. If they name one, run it with `--help` and copy the flags it prints; if the command is not installed or prints no usage, the docs do not name it
  - [x] `docs/cli-contract.md`, a section "The wake command": the PM sets it with `amoeba add --wake-command`; it runs in the member's checkout with no arguments from Amoeba and no stdin; it must check `inbox` at its start, accept before working, decline with a reason when the rules do not settle it, reply `done` with the result, check `inbox` again before it ends, and exit; it must carry its own cost or time cap, which is the only bound if its wrapper is killed (Amoeba cannot check that the command has one: it is the PM's duty, and the docs say so); it runs with only the `WAKE_ENV_NAMES` variables, so a script loads its own secrets; it is stopped at `wake_timeout_seconds`; its stdout and stderr go to the wake's log (name the path); the command is shown in plain text by `list members`, `list -j` and `status`, so no secret in it; a pipe or an environment assignment needs a script. Name the `list` lines, including `overdue`. The example is a script command carrying a `--max-seconds` flag (9.1 builds the fixture agent that takes it)
  - [x] `docs/cli-contract.md` also: `wake-run` as internal; `SendResult.wake_problem`; the wake step's cases and exits (the design's D2 "What a wake does not do" list). `docs/store-contract.md`: "How each state ends with nobody editing a file" gains the wake row (end, overdue, retention) and the limit's exit by the clock
  - [x] `tests/test_contract_docs.py` or `tests/test_wake_docs.py` (added function): the example command in the `cli-contract.md` section carries a cap flag, and the test fails when the example does not (a negative case with the flag removed from a copy)
  - [x] Success: `tests/test_contract_docs.py` and the new docs test pass
- [x] **8.2 Amend the architecture and the plan**
  - [x] `user/architecture/240-arch.agent-messaging.md`: read the Waking section and the "Store and config" paragraph and amend each sentence that differs from the design's Departures: the directory is Context Forge's `projectPath` (not "the directory the member was registered with"); the wrapper records how the wake ended and the row is kept (not "clears it on exit"); one row per wake, a rolling 24 hours, no wrapper pid, no stored count; `wake-run` is CLI-only; `add` can clear the setting; the explicit environment (`WAKE_ENV_NAMES`, never the sender's); no Amoeba stop of a command after its wrapper is killed; the limit counts failed starts; a wake starts at `send` or a same-id retry while `open`; the sweep's fourth step. The settings sentence ("with defaults defined once in the config layer") must say the two wake keys are required with no default in code, the suggested values appearing only in the config contract's example (D8)
  - [x] `user/architecture/240-slices.agent-messaging.md`: plan entry 5 (244): the wording that differs (rows kept, per-row `wakes`, rolling day, `projectPath`). Its Dependencies line already reads 240, 241, 242, 243, so it is not touched. In Implementation Order, the Dependencies bullet's sentence "244 needs 241's live-session check." becomes "244 needs 240 to 243 built and integrated, 241's live-session check among them."
  - [x] Success: `grep -c "WAKE_ENV_NAMES" user/architecture/240-arch.agent-messaging.md` is at least 1; `grep -n "244 needs 241's live-session check\." user/architecture/240-slices.agent-messaging.md` finds nothing; `grep -n "with defaults defined once in the config layer" user/architecture/240-arch.agent-messaging.md` finds nothing; checks pass

Note: the architecture's settings sentence already said the two wake keys are required with no default in code (the phrase named in the Success line was absent), so only the other differing sentences were amended: checkout is Context Forge's projectPath, one kept row per wake and a rolling 24 hours with no wrapper pid, `wake-run` is CLI-only, `--no-wake-command`, the explicit `WAKE_ENV_NAMES` environment, failed starts counted, a wake at `send` or a same-id retry while `open`, and the sweep's fourth step.

**Commit**: `docs: document waking and amend the architecture and plan`

## 9. Fixture agent and live test (D12; step 6)

- [x] **9.1 `tests/live/waking/fixture_agent.py`**
  - [x] A stand-in agent: runs `amoeba inbox -j`, accepts then completes each open request with `amoeba reply` (read `docs/cli-contract.md` for the real flags), rereads `inbox` before it exits, and takes the `--max-seconds` cap that 8.1's example uses and enforces it. Flags on its command line tell it to wait on a gate file (`--gate-file PATH`), to sleep past the timeout (`--sleep-seconds N`), and to write its parent pid to a file (`--parent-pid-file PATH`; the wrapper's pid, for the SIGKILL test). These are flags, not environment variables, because the wrapper passes the command only the `WAKE_ENV_NAMES` variables (D6). It finds `amoeba` through `PATH` only, since the wrapper's environment is the explicit one (9.2 puts the installed script's directory on the `PATH` of the CLI calls that send, which the wrapper copies). Spend: none
  - [x] A second small script in the same directory, `recorder_command.py`, writes its own argv, its whole environment and what it reads from stdin to a file named by its first argument, then exits (used by 9.2's message-text case)
  - [x] Success: `uv run ruff check` and `uv run pyright` are clean on both scripts; 9.2 exercises them
- [x] **9.2 `tests/live/waking/` live tier**
  - [x] Layout: modelled on `tests/live/program/` and `tests/live/mcp/conftest.py`: real `cf` and two git fixture repos in one program. The CLI is the script beside `sys.executable` (`Path(sys.executable).with_name("amoeba")`), as `tests/live/pause/harness.py` and `tests/live/mcp/test_mcp_walkthrough_live.py` find theirs; `deps.amoeba_script()` looks in the same place, so the wrapper runs the same build
  - [x] Environment: each CLI call that sends gets `AMOEBA_HOME` set to a throwaway directory (the first test asserts the store lies under it) and a `PATH` that starts with `Path(sys.executable).parent`, so the fixture agent's `amoeba` calls reach the same script and store. A wake command is the quoted interpreter path, the fixture script's path and its flags, including the case's control flags from 9.1 (`shlex.quote` each). Only the `WAKE_ENV_NAMES` variables reach the command, so a case controls the fixture through these flags, never through the test's environment
  - [x] Config: the throwaway config is `example_config_text()` with its values for the two wake keys replaced by `wake_timeout_seconds` 5 and `max_wakes_per_day` 2 in the test's own copy; the contract's example keeps its suggested values (D8). Harness constants (the polling wait and its bound) are named at the top and every wait is a bounded poll
  - [x] Cases, each from the design's Verification Walkthrough steps 3 to 7: a request wakes the fixture once and a second request during the wake is in its `inbox`, both end `done` and `list` shows no last problem; the limit stops the third wake and the request stays `open` with the counts in `list`; a missing executable ends `start_failed` and the request stays `open`; the sleeping fixture ends `timed_out` after the timeout and its process group is gone; `--no-wake-command` leaves a later send starting nothing; a push-confirmed live session (a fixture `sessions` row) blocks the wake and an unconfirmed one does not; a note to a member with a command starts nothing
  - [x] The message-text case: the member's command is `recorder_command.py`; a request whose subject and body hold marker strings wakes it, and the file it wrote holds neither marker in its argv, its environment or its stdin (stdin is empty). This is the design's criterion on the command itself; 6.4's spawn check covers the wrapper
  - [x] The SIGKILL case: SIGKILL the wrapper while the fixture runs; the row stays unended, is live until its deadline then shows as overdue with the pid and log path, Amoeba sends no signal to the old command (the test checks it still runs, then kills it itself), the next send starts a new wake, and `sweep` with a clock past retention deletes the row
  - [x] Success: `uv run pytest tests/live/waking` passes; `tests/live/program`, `tests/live/messaging` and 241's channel tier still pass

  Note: the fixture agent also takes `--cf-data-dir PATH` (the throwaway Context Forge data directory its `amoeba` calls use), because a wake command gets only the `WAKE_ENV_NAMES` variables and `CONTEXT_FORGE_DATA_DIR` is not one of them; a real agent's repo needs no such flag. The 'second request during a wake' case opens its gate right after the second `send` (the 5 s wake timeout is running); the live `running` display is a separate case (`test_list_shows_a_live_wake_as_running`). 241's channel tier needs `AMOEBA_LIVE_CHANNEL_MODEL`; run once with `sonnet` and it passed.

**Commit**: `test: add the waking fixture agent and live tier`

## 10. Final verification

- [x] **10.1 Final verification**
  - [x] Run Verification Walkthrough steps 1 to 8 (all four checks; steps 2 to 7 under a throwaway `AMOEBA_HOME`; `uv run pytest tests/live/waking`); step 9 is the Phase 7 checklist below. The live tier may stand for the manual steps; note which
  - [x] Confirm by name: `tests/test_contract_docs.py`, `tests/test_import_boundaries.py`, `tests/test_store_opened_only_by_state_move.py`, `tests/test_read_side_defined_once.py`, `tests/store/test_vocabulary_pinning.py` and `tests/test_message_timing.py` pass; `grep -rn "except Exception" src/amoeba/operations/wake*.py` finds only the wrapper's process boundary
  - [x] Confirm 240 to 243 are unchanged apart from what the design names: `git diff {target} -- tests | grep '^-[^-]'` lists only the assertions tasks 2.1, 4.4, 6.1 and 6.8 name, and config keys added to fixtures by 1.2; every other test change is an added function
  - [x] In `user/slices/244-slice.waking.md`: update the Verification Walkthrough where Phase 6 changed it (it says it is refined when Phase 6 is complete)
  - [x] Success: all checks pass; every Success Criteria line in the design maps to a passing test named in a note under this task

  Note: Target commit before this slice (the "previous code" for the Phase 7 restore): `cac93f744452d14d42a5b41c9e02ee0c2ecb416e` (main). Verification Walkthrough steps 2 to 7 were run by hand under a throwaway `AMOEBA_HOME` and Context Forge data directory with this build's `amoeba` first on `PATH` (outputs are in the design); step 1 and step 8 were run as written: ruff format and check and pyright clean, `uv run pytest` 3976 passed, `uv run pytest tests/live/waking` 11 passed. `tests/live/program`, `tests/live/messaging`, `tests/live/notes` (11 passed together) and 241's `tests/live/channels` (4 passed with `AMOEBA_LIVE_CHANNEL_MODEL=sonnet`, which was not set and which spends on a real session) also pass. Named tests pass: tests/test_contract_docs.py, tests/test_import_boundaries.py, tests/test_store_opened_only_by_state_move.py, tests/test_read_side_defined_once.py, tests/store/test_vocabulary_pinning.py, tests/test_message_timing.py, tests/test_wake_docs.py. `grep -rn "except Exception" src/amoeba/operations/wake*.py` finds only the wrapper's process boundary (`wake_run.py`).

  Note: `git diff main -- tests | grep '^-[^-]'` lists only: tests/cli/test_parser_names.py and tests/mcp_server/test_tools.py (the command-list pins now subtract `CLI_ONLY_COMMANDS`), tests/operations/test_message_member.py (`resolve_recipient` return compared as `Recipient`, 6.1), tests/store/test_schema.py and tests/test_contract_docs.py (table count 12 to 13, stale pins like 2.1's), tests/store/test_vocabulary_pinning.py (an import line), and tests/test_message_timing.py (`_with_start` adds `WAKE_BOUND_SECONDS`, 6.8); the other changed pins only gained the new key (member JSON key sets, the `send` document, the status member key set, the schema pin).

  Note: Success Criteria to passing tests. Functional: the fixture wakes once and a second request is in its inbox, both `done` = live `test_a_request_wakes_the_fixture_once_and_a_second_is_in_its_inbox`, unit `test_wake_after_send.py::test_a_request_to_a_member_with_a_command_claims_one_row_and_spawns_the_wrapper` and `::test_a_second_send_while_the_wake_is_live_spawns_nothing`. Live session, no command, note, unconfirmed session, same-id retries = `test_wake_after_send.py` (`test_a_push_confirmed_session_blocks_the_wake`, `test_a_session_without_push_confirmation_does_not_block`, `test_a_recipient_with_no_command_is_never_woken`, `test_a_note_to_a_member_with_a_command_starts_nothing`, `test_a_same_id_retry_of_an_open_request_wakes_again_after_a_start_failure`, `test_a_same_id_retry_starts_nothing_while_a_wake_is_live`, `test_a_same_id_retry_of_an_accepted_request_starts_nothing`) and live `test_a_confirmed_live_session_blocks_the_wake_and_an_unconfirmed_one_does_not`. Timeout stop with the group, and SIGTERM to leftovers = `test_wake_run.py::test_a_command_past_the_deadline_is_stopped_with_its_whole_group`, `::test_after_a_normal_exit_a_member_left_in_the_group_gets_sigterm`, live `test_a_command_that_sleeps_past_the_timeout_is_stopped_with_its_group`. Killed wrapper = live `test_a_killed_wrapper_leaves_an_overdue_row_and_a_command_amoeba_never_stops`, `test_wake_status.py::test_a_row_past_its_deadline_is_running_and_overdue_with_pid_and_log`, `tests/store/test_wakes.py::test_a_row_past_its_deadline_is_not_live`, `tests/store/test_message_sweep.py::test_the_sweep_deletes_an_aged_wake_row_ended_or_not_and_keeps_a_young_one`. Wrapper cannot read its row, start failures, wrapper failure, no argv text = `test_wake_run.py` (`test_a_missing_row_raises_with_no_command_run`, `test_an_ended_row_raises_with_no_command_run_and_no_row_change`, `test_a_store_that_cannot_be_read_raises_with_no_command_run`, `test_a_missing_executable_ends_start_failed_without_the_file_name`, `test_a_raise_after_the_start_records_wrapper_failed_and_stops_the_group`), `tests/cli/test_wake_run_cli.py`, `test_wake_status.py::test_no_command_text_reaches_the_document_beyond_the_command_field`, `tests/cli/render/test_waking_section.py::test_the_secret_like_marker_appears_only_on_the_command_line`. Limit and clock exit = `test_wake_after_send.py::test_the_limit_stops_the_wake_and_the_request_waits_in_the_inbox`, `::test_past_the_ttl_the_sweep_expires_a_request_the_limit_left_and_the_sender_hears`, `::test_a_day_and_a_tick_after_the_oldest_counted_row_the_next_send_wakes`, `tests/store/test_wakes.py::test_a_row_exactly_a_day_old_no_longer_counts`, live `test_the_limit_stops_the_next_wake_and_the_request_stays_open`. Start failures count toward the limit = `test_wake_after_send.py::test_failed_starts_use_the_limit_and_the_next_send_spawns_no_wrapper`, `::test_a_launch_error_ends_the_row_start_failed_and_the_request_stays_open`, `::test_a_missing_amoeba_script_ends_the_row_start_failed_with_its_text`, `::test_no_checkout_path_inserts_a_start_failed_row_and_the_request_stays_open`, live `test_a_missing_executable_ends_start_failed_and_the_request_stays_open`. No second store open and no write lock = `test_wake_after_send.py::test_a_recipient_with_no_command_takes_no_transaction_in_the_wake_step`, `::test_a_failed_pre_check_reads_once_and_never_takes_the_write_lock`, `tests/operations/test_resolve_recipient.py::test_the_member_is_read_once_for_the_id_the_path_and_the_command`. Non-zero exit as last problem, `StoreError` in `wake_problem` = `test_wake_status.py::test_each_problem_outcome_is_the_last_problem`, `test_wake_after_send.py::test_a_store_error_in_the_claim_is_returned_and_the_request_stays_written`, `::test_a_store_error_recording_a_start_failure_leaves_the_row_unended`. No message text reaches the command = `test_wake_after_send.py::test_no_message_text_reaches_the_wrapper`, live `test_the_command_receives_no_message_text`. Environment = `tests/operations/test_wake_environment.py::test_only_the_set_names_of_the_constant_are_copied`, `test_wake_run.py::test_the_command_runs_in_the_rows_directory_with_only_the_wake_names`. Docs example carries a cap = `tests/test_wake_docs.py`. `add` flags, `--file`, `--project`, MCP field = `tests/cli/test_add_wake_command_cli.py`, `tests/operations/test_add_wake_command.py`, `tests/mcp_server/test_tools.py::test_the_add_schema_has_no_wake_command_anywhere`, `tests/mcp_server/test_in_process.py::test_an_add_tool_call_passing_wake_command_is_rejected_as_an_unknown_field`. Technical: row cleanup = `tests/store/test_message_sweep.py` and `tests/operations/test_message_sweep_wrapper.py`; wake logs pruned = `tests/operations/test_prune.py::test_old_wake_logs_go_and_new_ones_stay`; config keys = `tests/config/test_user_config.py`; check lists pinned = `tests/store/test_vocabulary_pinning.py`; timing = `tests/test_message_timing.py::test_the_wake_bound_is_five_store_waits` and `::test_sends_worst_case_with_the_start_and_the_wake_is_the_design_figure` (105 + 30 + 25 = 160 s, below 180 s); concurrent sends = `tests/load/test_wake_claim_load.py`. The live-store criterion (backup, migrate to 9, read back) is the Phase 7 hand-off, not a task.

  Note: `cf check --fix --no-commit` (cf 0.19.28) fixed the slice design's frontmatter status (now `complete`). It still reports two findings not caused by this slice and left alone: `reviews/244-review.tasks.waking.md` has verdict FAIL (a planning-phase review whose findings were resolved in commit 2bd7fc0 but whose re-review was not rerun) and `project-guides/000-pre-concept.amoeba.md` lacks a `docType`; both are for the Project Manager.

**Commit**: `docs: refine the 244 walkthrough after final verification`

### Phase 7 hand-off (not tasks; nothing here is checked off in this file)

Phase 6 is complete when sections 0 to 10 are checked. These items are not tasks; the implementing agent does them in Phase 7, after the code review passes and the slice is merged (the merge is Phase 7's, not a task). Designated by `CLAUDE.md`.

**P7.1 Update the live install**

The release skill runs this as its last step; it is not run per merge. By hand, from the target checkout: `uv run python scripts/update_live.py update`. It backs up the live store and config to `~/.local/state/amoeba/backups/<stamp>/`, appends any config key the new code requires (value from the config contract's example), installs the target, migrates the store through `amoeba list`, and checks the schema version, integrity, foreign keys, the member count and the installed `amoeba-mcp` tool list. If any check fails it restores the backup and reinstalls the previous commit itself, and exits 1. It needs `--previous <commit>` only when no earlier run has recorded the installed commit. Paste its output into the slice notes, and restart the client sessions it lists (they run the old `amoeba-mcp` until restarted). `uv run python scripts/update_live.py restore` puts the newest backup back later; a successful update deletes the older backup set
