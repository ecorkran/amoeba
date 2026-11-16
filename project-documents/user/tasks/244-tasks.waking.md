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
dateUpdated: 20261115
status: not_started
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

- [ ] **0.1 Target and prerequisites**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty. `git checkout {target}`; the planning documents (design, this file) are committed there, with no other uncommitted change
  - [ ] Confirm the prerequisites exist, by the designed name or another (a role built under another name is mapped in the next item, not blocked): `store/schema/` holds `001` to `008` and `EXPECTED_SCHEMA_VERSION` in `store/migrations.py` is 8; `send` has a request branch and a separate note path (243); `resolve_recipient` exists; `store/message_sweep.py` has `sweep` and `sweep_due`; `operations/message_sweep.py` has `sweep_messages`; `MemberStatus` exists; 241's `live_member_ids` and `session_stale_seconds` exist; `Deps.amoeba_script` and `START_BOUND_SECONDS` exist (242); `tests/test_message_timing.py` exists; `upstream/context_forge/project_of.py` returns `projectPath`. If a role has no built module at all, write `BLOCKED: <what>` under this task and stop (240 to 243 must be built and integrated first)
  - [ ] Record in a note the built name of each role, and the signatures of `resolve_recipient`, `live_member_ids`, `sweep` and `sweep_due`
  - [ ] Success: the target is checked out and clean; a note under this task gives the target and the role-to-built-name list
- [ ] **0.2 Branch, baseline and design alignment**
  - [ ] `git checkout -b 244-slice.waking {target}`; if the branch exists, `git checkout 244-slice.waking`
  - [ ] Run the checks once and note the baseline. Failures present before this slice are listed by test name and not fixed
  - [ ] Amend `user/slices/244-slice.waking.md` on this branch (the target takes no commit during Phase 6): in Special Considerations' Live store paragraph, install from the target at the Phase 7 hand-off, after the merge (the design says "from the slice branch", but an install before the merge would leave the installed tool refusing the store), delete the two backup files once the read-back passes (the design says "after the review passes"; the hand-off itself runs after it), and take "the previous code" as the target commit recorded in 10.1; in Development Approach, step 7 is the Phase 7 hand-off; in Departures, drop the "Dependencies" bullet's amendment of the plan's entry, since that entry already reads 240, 241, 242, 243
  - [ ] Success: `git branch --show-current` prints `244-slice.waking`; a note under this task gives the baseline result; `grep -n "from the slice branch" user/slices/244-slice.waking.md` finds nothing

**Commit**: `docs: align the 244 design with its task breakdown`

## 1. Config keys (D8; Development Approach step 1)

- [ ] **1.1 `wake_timeout_seconds` and `max_wakes_per_day`**
  - [ ] `config/user_config.py`: add `wake_timeout_seconds` (a number greater than 0) and `max_wakes_per_day` (an integer of at least 1), each required with no default in code, the same type pattern as `answering_wait_seconds` and `prune_after_days`
  - [ ] `docs/config-contract.md`: both keys in the key table and in the `## Example` block (the one place the suggested values appear), with one line each on what is stopped or limited and what happens when hit (D7). Zero is not a way to turn waking off: clearing `wake_command` is (D8)
  - [ ] Success: pyright clean; tests that load the example config still pass
- [ ] **1.2 Config tests**
  - [ ] `tests/config/test_user_config.py` (added functions): each key missing fails with `ConfigError` naming the key; a zero or negative `wake_timeout_seconds`, a zero `max_wakes_per_day` and a non-integer `max_wakes_per_day` each fail naming the key; `example_config_text()` loads with both keys. If a fixture config in an existing test lacks the keys, add them to that fixture only (no assertion changes)
  - [ ] Success: checks pass

**Commit**: `feat: add wake_timeout_seconds and max_wakes_per_day config keys`

## 2. Migration 9: `wake_command` and `wakes` (D3; step 1)

- [ ] **2.1 Vocabulary, migration and `Wake`**
  - [ ] `store/vocabulary.py`: `WakeOutcome` with `exited`, `timed_out`, `start_failed`, `wrapper_failed`, one-line comment each
  - [ ] `store/schema/009_wakes.sql`: `ALTER TABLE members ADD COLUMN wake_command TEXT`, and `CREATE TABLE wakes` with the D3 columns: `wake_id` text primary key, `member_id` referencing `members`, `directory` (null only for a `start_failed` row with no path), `command`, `started_at`, `deadline_at`, `log_stem`, `command_pid`, `ended_at`, `outcome`, `exit_code`, `detail`. Table `CHECK`s: `ended_at` and `outcome` both null or both set; `exit_code` set only for `exited`; the `outcome` list equals `WakeOutcome`. Indexes on `(member_id, started_at)` and `(started_at)`. Header comment: `ADD COLUMN` and `CREATE TABLE` only, so existing rows are untouched. `EXPECTED_SCHEMA_VERSION` (in `store/migrations.py`) becomes 9
  - [ ] `store/models.py`: frozen dataclass `Wake` with the row's fields; the members model gains `wake_command` (nullable). Existing member readers keep working, so a reader that builds a member from a row reads the new column explicitly
  - [ ] `docs/store-contract.md`: the column, the table and each of its columns, who writes each (the claim writes the row; `command_pid` and the end fields are written by the wrapper, or by `wake_after_send` for a start failure), the `WakeOutcome` values, version 9, and the retention rule (D10). Update stale-version assertions in the store migration tests and the schema pin in `tests/store/test_schema_holds_no_mirrored_state.py`; these are the only existing tests this task edits
  - [ ] Success: pyright clean; existing store tests pass
- [ ] **2.2 Migration test**
  - [ ] `tests/store/test_migration_009.py` (model on the latest migration test, e.g. `test_migration_006.py`): a version-8 database with members, programs and messages migrates to 9 with every existing row field-for-field equal, `wake_command` null for each member, `wakes` present and empty, `foreign_key_check` empty. The `outcome` `CHECK` list equals the `WakeOutcome` members (extend `tests/store/test_vocabulary_pinning.py`). The two `CHECK`s each reject a violating insert (an `outcome` without `ended_at`, an `exit_code` on `timed_out`) and accept a valid one. A store at version 10 is refused by the existing newer-schema guard
  - [ ] Success: checks pass

**Commit**: `feat: add migration 9, the wakes table and members.wake_command`

## 3. `store/wakes.py` (D2, D3, D7, D9, D10; step 1)

- [ ] **3.1 `LIVE_WAKE`, `claim_wake` and `can_wake`**
  - [ ] SQL in `store/sql_wakes.py`, with `LIVE_WAKE` as the one predicate (row not ended and `deadline_at` later than now), used by the claim and every read. `WAKE_WINDOW` (24 hours) is one constant. Every function in `store/wakes.py` takes `now` as an argument and never reads a clock or config
  - [ ] `claim_wake(transaction, member_id, now, wake_timeout_seconds, max_wakes_per_day, session_stale_seconds, wake_id, directory, log_stem)` as D2 states, in this order, stopping at the first failing check and returning the new `Wake` or nothing: (1) the member is active (`sql.ACTIVE_MEMBER`) with a non-null `wake_command`; (2) its id is not in `live_member_ids(transaction, now, session_stale_seconds)`; (3) no row of the member satisfies `LIVE_WAKE`; (4) fewer than `max_wakes_per_day` rows with `started_at` in `WAKE_WINDOW`, ended or not, any outcome; (5) insert the row with the given `wake_id`, `command` copied from the member, `deadline_at = started_at + wake_timeout_seconds`, and the given `log_stem`. The caller (6.3) makes `wake_id` (`uuid4().hex`) and `log_stem` (`<logs_dir>/wake/<wake_id>`, or null when `directory` is null), so the store reads no layout or config. With no directory it inserts the row already ended as `start_failed` with a reason in `detail` and returns nothing to start (D4)
  - [ ] `can_wake(transaction, member_id, now, max_wakes_per_day, session_stale_seconds) -> bool`: the same checks 1 to 4 as a read, for `wake_after_send`'s pre-check; `claim_wake` calls the same code so the two never differ
  - [ ] Success: pyright clean; the store module imports nothing from `operations`
- [ ] **3.2 Claim tests**
  - [ ] `tests/store/test_wakes.py` (clock passed in, no real time): the claim stops at the first failing check, one test per check and in the design's order (inactive or removed member; no command; a live session per 241's rule, where a session that is not push-confirmed does not block; a live row; the limit); a claimed row has the fields D3 lists and `deadline_at` fixed at the claim; a row whose deadline has passed is not live; a row ended earlier still counts toward the limit; the limit counts `start_failed` rows; a row 24 hours and one tick old no longer counts and the claim succeeds; a null directory inserts an ended `start_failed` row and returns nothing; `can_wake` and `claim_wake` agree over the same fixtures; a later edit of the member's `wake_command` leaves a stored row's `command` unchanged
  - [ ] Success: checks pass
- [ ] **3.3 Row reads, writes and prune**
  - [ ] `get_wake(transaction, wake_id)`; `set_command_pid(transaction, wake_id, pid)`; `finish_wake(transaction, wake_id, outcome, exit_code, detail, now)` as a compare-and-set on `ended_at IS NULL` that returns whether it ended the row
  - [ ] `wake_summary(transaction, member_id, now, max_wakes_per_day)`: what `list` shows (D9): the member's unended row with an `overdue` flag (true when the row is not live, decided by the negation of `LIVE_WAKE`, the one predicate), the count of rows in `WAKE_WINDOW`, and the newest ended row
  - [ ] `prune_wakes(transaction, cutoff)`: deletes rows with `started_at` before the cutoff whatever their state, returns the count; `wakes_due(transaction, cutoff)` reads whether any is aged
  - [ ] Success: pyright clean
- [ ] **3.4 Tests for 3.3**
  - [ ] `tests/store/test_wakes_rows.py`: `finish_wake` ends once and a second call returns false; `set_command_pid` is shown by `get_wake`; `prune_wakes` deletes an unended aged row and keeps a young one; `wakes_due` is true for an aged row and false for a young one; `wake_summary` returns the three parts, with `overdue` false for a live unended row and true for an unended row past its deadline
  - [ ] Success: checks pass

**Commit**: `feat: add the wakes store, claim and limit checks`

## 4. `wake_command` through `add` (D1; step 2)

- [ ] **4.1 `MemberRequest.wake_command` and its write**
  - [ ] `operations/set_up_models.py`: `MemberRequest.wake_command: NonBlankText | None`, omitted meaning leave it and null meaning clear it, told apart by `model_fields_set` as `concept` is (read how `concept` does it first). A validator splits the text with `shlex.split` and rejects an unsplittable text, a text with no tokens, and a NUL or a newline, naming the field. The executable is not looked up (D1)
  - [ ] `operations/set_up_resolve.py` and the member writer: carry the value to the row; leave, set and clear as above. `operations/list_registry.py`: `list members` returns each member's `wake_command`
  - [ ] Success: pyright clean
- [ ] **4.2 Operation tests**
  - [ ] `tests/operations/test_add_wake_command.py`: set; clear with null; omitted leaves an existing value; a second `add` of other settings leaves it; blank, whitespace-only, unbalanced quotes, NUL and newline are each rejected naming `wake_command`; a text with an executable that does not exist is accepted; `list members` returns the command and null for a member without one
  - [ ] Success: checks pass
- [ ] **4.3 CLI flags and the bulk document**
  - [ ] `cli/registration_arguments.py` and the parser: `--wake-command COMMAND` and `--no-wake-command`, mutually exclusive, working directly, with `--project` and through `--file` (bulk JSON key `wake_command`: omitted leaves, null clears). `add --help` says the command runs unattended with the user's privileges, with only the `WAKE_ENV_NAMES` variables, is shown in plain text and so carries no secret, and must carry its own cost or time cap (Amoeba cannot check it). `cli/render/registry.py`: `list members` text shows the command on a `wake command:` line for a member that has one and no such line for one that does not; `-j` carries `wake_command` as the string or null
  - [ ] `docs/cli-contract.md`: the two flags and the bulk key (the section on the contract is 8.1); `docs/mcp-server.md`: one row stating the `add` tool does not take `wake_command`
  - [ ] Success: pyright clean
- [ ] **4.4 CLI and MCP tests**
  - [ ] `tests/cli/test_add_wake_command_cli.py`: `--wake-command` sets, `--no-wake-command` clears, both together are a usage error, `--project` from another directory, `--file` with set, omitted and null, an unsplittable text exits non-zero naming the field; `list members` text and `-j` show it, and for a member without one the text has no `wake command:` line and `-j` has null. If a 227 to 229 CLI test pins the exact `add` flag list, change only that assertion to include the two flags and say which test in a note
  - [ ] MCP: `tests/mcp_server/test_tools.py` (added function): the `add` tool's input schema has no `wake_command`, and a call passing it is rejected as an unknown field
  - [ ] Success: checks pass

**Commit**: `feat: set and clear wake_command with add and show it in list members`

## 5. `amoeba wake-run` (D5, D6; step 3)

- [ ] **5.1 `operations/wake_environment.py`**
  - [ ] `WAKE_ENV_NAMES` (`PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG`, `LC_ALL`, `TMPDIR`, `AMOEBA_HOME`) as one constant; `build_wake_environment(environ)` copies only those names that are set, nothing else
  - [ ] `wake_detail(error)`: the one place a `detail` text is made. For an `OSError` the exception class and its `strerror` (never the filename); for anything else the class name. It never holds argv text
  - [ ] Success: pyright clean
- [ ] **5.2 Tests for 5.1**
  - [ ] `tests/operations/test_wake_environment.py`: with `SENDER_SECRET_MARKER` and `AMOEBA_HOME` set among others, the result holds exactly the `WAKE_ENV_NAMES` names that were set, none other, and not the marker; a name that is unset is absent, not empty. `wake_detail`: a `FileNotFoundError` for a path holding a marker gives class and `strerror` without the marker; a `ValueError` gives its class name only
  - [ ] Success: checks pass
- [ ] **5.3 `operations/wake_run.py`: `run_wake`**
  - [ ] `run_wake(store, deps, wake_id, popen: WaitablePopen = subprocess.Popen)` as D6 states, with the clock from `deps.clock`. `popen` is the seam that starts the command: the existing `WaitablePopen` type (`operations/processes.py`, a Popen-shaped callable returning a `WaitableChild` with `pid` and `wait`), called with the argv, `cwd`, the explicit `env`, `start_new_session=True`, stdin `DEVNULL` and stdout and stderr inherited; its production default `subprocess.Popen` is stated once, in this signature. `deps.spawn` (`start_child`) is not used here: it makes its own log files, and the wrapper's stdout and stderr already are the wake's logs. Before the command: a `StoreError`, a missing row or an already ended row raises to the caller (exit 3, nothing recorded); a command text that cannot be split or an `OSError` from the start records `start_failed` with `wake_detail` and returns the exit-1 result. Run: start in a new session in the row's directory with `build_wake_environment`, stdin `DEVNULL`, stdout and stderr inherited; one short write sets `command_pid` (a held store there is a logged warning and the wait goes on); `child.wait(timeout=max(0, deadline_at - now))`; outcome `timed_out` on timeout, else `exited` with the code; then `terminate_group` either way; `finish_wake` in one short write bounded by `BUSY_TIMEOUT_SECONDS` (a failure to write is logged and raised: exit 3, row as in the first case). The traceback of any failure goes to the stderr log only
  - [ ] Success: pyright clean; the file about 200 lines or less
- [ ] **5.4 Tests for 5.3**
  - [ ] `tests/operations/test_wake_run.py` (a fake clock frozen at the claim time and a named short `TEST_WAKE_TIMEOUT_SECONDS` of at most one second as `wake_timeout_seconds`, so the wait on a real child is that short real time; a real short-lived child where a process matters): a command that exits 0 ends `exited` with code 0 and a `command_pid`; exit 3 ends `exited` with code 3; a command that outlives the deadline is stopped with its whole group and ends `timed_out` (a grandchild in the group is gone); after a normal exit a grandchild left in the group gets SIGTERM; the command runs in the row's directory with stdin closed and sees only the `WAKE_ENV_NAMES` names the wrapper has; a missing executable, a missing directory and a non-executable file each end `start_failed` with class and `strerror` and no filename; a marker in the executable name (the secret-like marker test) is in no row, no log line the wrapper prints and not the result; a store that cannot open or a missing or ended row raises with no command run and no row change; a held store while writing `command_pid` is a warning and the wake still ends recorded
  - [ ] Success: checks pass
- [ ] **5.5 The process boundary**
  - [ ] In `run_wake`, the one place this slice catches `Exception` (D6), with a comment saying it is the process boundary: `logger.exception`, `terminate_group` on a started command, then `finish_wake(wrapper_failed, wake_detail(error))` tried once (`start_failed` when the command had not started). Lint: ruff selects `BLE`, and BLE001 accepts an `except Exception` whose handler calls `logger.exception`, so no suppression is needed; run `uv run ruff check` and, only if it flags the line, add a line-level `# noqa: BLE001` with the reason, never a config change
  - [ ] Success: pyright and ruff clean
- [ ] **5.6 Tests for 5.5**
  - [ ] Added to `tests/operations/test_wake_run.py`: a raise after the start from the child that a test `popen` returns (passed as `run_wake`'s `popen`) records `wrapper_failed` with the class name and stops the group; a raise before the start records `start_failed`; the second write failing leaves the row unended and the error logged once
  - [ ] Success: checks pass

**Commit**: `feat: add the wake wrapper logic`

- [ ] **5.7 The `wake-run` subcommand**
  - [ ] `cli/parser.py`, `cli/main.py` and `cli/commands.py`: register `wake-run WAKE_ID` as a CLI-only subcommand (no `OperationName`; read how `handle-pause` is registered and how `tests/cli/test_parser_names.py` pins the list, and add one named constant for the CLI-only names so that test says what it allows). Its branch in `main` comes before the config load and before the operation lookup: it opens the store through `open_state_store(layout)`, calls `run_wake`, and exits 0 when a command ran and was recorded as `exited` or `timed_out`, 1 for `start_failed`, 3 for an operational failure with one stderr line, which includes `wrapper_failed` (D6 reads the wrapper's own unexpected error as operational; its row is still recorded). The command is listed like any other in `--help`, and named in `docs/cli-contract.md` as started by Amoeba and not meant for people
  - [ ] Success: pyright clean
- [ ] **5.8 Subcommand tests**
  - [ ] `tests/cli/test_wake_run_cli.py`: through `main`, with a throwaway store holding a claimed row and a real short command, exit 0 and the row ended; a missing executable exits 1; a `wrapper_failed` (`run_wake`'s `popen` patched to return a child that raises after the start) exits 3 with the row recorded; a missing row exits 3 with one stderr line and no traceback; a config file with the new keys missing does not stop the wrapper (no config is loaded); `tests/cli/test_parser_names.py` passes with the named constant
  - [ ] Success: checks pass

**Commit**: `feat: add the wake-run subcommand`

## 6. The wake step in `send` (D2, D4, D5, D10, D11; step 4)

- [ ] **6.1 `resolve_recipient`, `wake_command` and `wake_problem`**
  - [ ] `resolve_recipient` returns `Recipient(member_id, project_path)`, `project_path` null when Context Forge did not know the reference (D4). Update its callers; if a 240 test compares its return to a bare id, change only that assertion and say which test in a note (the only permitted edit to an existing assertion in this task)
  - [ ] `send`'s own write transaction reads the recipient's `wake_command` with the member row it already reads (no second read). `SendResult` gains `wake_problem` (string or null, null when nothing went wrong); the text renderer prints it as a line; `docs/cli-contract.md` and `docs/mcp-server.md` list the field
  - [ ] Success: pyright clean; 240 to 243 `send` tests pass
- [ ] **6.2 Tests for 6.1**
  - [ ] `tests/operations/test_resolve_recipient.py` (added): the path is returned for a known reference and null for a reference read as an id. `tests/operations/test_send.py` (added): `wake_problem` is null on a normal send; `send` reads the recipient's `wake_command` in the same transaction (a test counts store opens for a recipient with no command: one open, as before this slice)
  - [ ] Success: checks pass

**Commit**: `feat: return the checkout path from resolve_recipient and add wake_problem`

- [ ] **6.3 `operations/wake.py`: `wake_after_send`**
  - [ ] `wake_after_send(open_store, config, deps, recipient, wake_command)` returns a problem line or nothing, and is called by the request branch after the request's transaction has committed, and only while the request is `open` (outcome `sent`, or `unchanged` with the stored request still `open`; never for `accepted`, never from the note path). A recipient with no `wake_command` ends there: no store open
  - [ ] Otherwise: open the store once, run `can_wake` in a read transaction (stop with no write lock when it fails), then `claim_wake` in one write transaction passing the checkout path, a fresh `uuid4().hex` as `wake_id` and `log_stem` built from `deps.logs_dir` (null with no checkout path). If a row is returned: `deps.amoeba_script()` and `deps.spawn([script, "wake-run", wake_id], checkout, LaunchLogs(...))` with logs `<logs_dir>/wake/<wake_id>.stdout.log` and `.stderr.log` (`log_stem` is the path without the suffix; the directory name is a constant); return without waiting. `LaunchError` (a value) and `AmoebaScriptMissing` (caught by type, with a comment that raising would report a failure for a request already written) are each recorded as `finish_wake(start_failed, <text>)` and logged with `logger.error`. A `StoreError` anywhere is caught by type, logged with `logger.exception`, and returned as one line; any other exception propagates (D2)
  - [ ] `send`'s request branch calls it and sets `SendResult.wake_problem`; `send` exits as 240 says whatever the wake step did. The wake step makes no `cf` call, no `ps` call and never waits for the wrapper
  - [ ] `WAKE_BOUND_SECONDS = 5 × BUSY_TIMEOUT_SECONDS` defined once here (D11)
  - [ ] Success: pyright clean; `send.py` gains only the call
- [ ] **6.4 Tests: when a wake starts and when it does not**
  - [ ] `tests/operations/test_wake_after_send.py` (fake `spawn`, fake clock): a request to a member with a command, no live session and no live wake claims one row and spawns `[script, "wake-run", <id>]` in the checkout with the two log paths; a second send while the row is live spawns nothing; a push-confirmed session blocks the wake and a session without push confirmation does not; no command, a removed member and a note (to a member that has a command) spawn nothing; a null checkout path inserts a `start_failed` row, spawns nothing and the request stays `open`; a `LaunchError` and a missing script each end the row `start_failed` with the reason and leave the request `open`
  - [ ] No message text reaches the wrapper: send a request whose subject and body hold marker strings and check the spawn's argv and log paths for them (the command itself is checked in 9.2)
  - [ ] Success: checks pass
- [ ] **6.5 Tests: the limit and the retry**
  - [ ] Added to the same file: the limit stops the wake with no row written, the request stays `open` and in the recipient's `inbox`, and with the clock past the request's TTL the sweep expires it and the sender's `inbox` reports the end (240's own rig and expiry path); with the clock 24 hours and one tick past the oldest counted row the next send wakes; with `max_wakes_per_day` failing sends to a member whose command cannot start, the next send spawns no wrapper
  - [ ] Retry rules: a same-id retry answering `unchanged` for an `open` request wakes when no wake is live and the limit allows (after a start failure), and starts nothing while one is live; for an `accepted` request it starts nothing
  - [ ] Success: checks pass
- [ ] **6.6 Tests: store behaviour and failures**
  - [ ] Added to the same file: a recipient with no command opens the store no second time (a test counts opens); a recipient whose pre-check fails (live session, live wake, limit) takes no write lock (a test checks the write path was never entered); a `StoreError` in the claim is returned in `wake_problem`, the request stays written and `send` exits 0 or 1 as 240 says; a `StoreError` while recording a start failure leaves the row unended with the problem returned
  - [ ] Success: checks pass
- [ ] **6.7 Two sends at once (load test)**
  - [ ] `tests/load/test_wake_claim_load.py` (model on `tests/load/test_report_release_load.py`, collected the same way): `WRITERS` threads (a named constant), each with its own store connection and the real `send` with a fake counting `spawn`, send a request each to one member with a wake command, together. Assert: exactly one `wakes` row and one spawn; every request is `open` and in the member's `inbox` (the guarantee D2 gives the second sender); no `send` call exceeds `WAKE_BOUND_SECONDS` plus 240's own bound for `send`, and the burst finishes within a named budget constant. A second case sends to as many members as threads: one row and one spawn each. CI already gates the file: `ci.yml` runs a bare `uv run pytest` and `pyproject.toml` ignores only `tests/live` (confirm both and note it)
  - [ ] Success: checks pass
- [ ] **6.8 The timing test**
  - [ ] `tests/test_message_timing.py` (240's test; one of the named edits to existing tests, see Context Summary and 10.1): add `WAKE_BOUND_SECONDS` to `send`'s worst case beside `START_BOUND_SECONDS`, still asserting the sum is below `MCP_CALL_DEADLINE_SECONDS` and that the failing-bound test still fails; assert `WAKE_BOUND_SECONDS` equals `5 × BUSY_TIMEOUT_SECONDS`. The design's figure is 160 s against 180 s; if the computed sum reaches the deadline write `BLOCKED:` with the numbers under this task
  - [ ] Success: checks pass

**Commit**: `feat: start a wake from send for an open request`

- [ ] **6.9 Sweep step and due check**
  - [ ] `store/message_sweep.py`: `sweep` gains `prune_wakes` as a further statement, with the same `prune_after_days` cutoff and no signature change; `sweep_due` counts an aged `wakes` row as due, so a quiet store is still not write-locked by a poll. `operations/message_sweep.py` needs no change if it already calls `sweep_due`; confirm and note it
  - [ ] Success: pyright clean
- [ ] **6.10 Cleanup tests**
  - [ ] `tests/store/test_message_sweep.py` (added functions): an aged `wakes` row is deleted by `sweep` whether ended or unended (the unended case is a row past its deadline, as a killed wrapper leaves it); a young row stays; `sweep_due` is true for an aged row alone and false for a young one. `tests/operations/test_message_sweep_wrapper.py` (added): `sweep_messages` on a store holding only an aged row writes; with a young row it opens no write transaction
  - [ ] Logs: `tests/operations/test_prune.py` or the prune test file (added function): old and new files under `logs/wake/` are created in a throwaway state directory; `prune`'s existing rule removes the old files and the emptied directory and keeps the new. Do not change `prune` unless this test fails
  - [ ] Success: checks pass

**Commit**: `feat: delete aged wakes rows in the sweep`

## 7. `list` and `status` (D9; step 5)

- [ ] **7.1 `WakeStatus` and `operations/wake_status.py`**
  - [ ] `operations/status_models.py`: `WakeStatus` (`command`, `running`, `stopped`, `last_problem`) and `MemberStatus.wake`, present only for a member with a `wake_command` (null otherwise), with the nested fields D9 lists. `running` holds the member's unended row (`started_at`, `deadline_at`, `command_pid`, `log_stem`) plus the `overdue` flag from `wake_summary` (3.3): a row past its deadline is in this field with `overdue` true, though it no longer counts as a live wake (the design's "stops reading as running at `deadline_at`" is the claim's `LIVE_WAKE`, and the display says overdue). `operations/wake_status.py` builds it from one `wake_summary` read: `stopped` is set when the count in `WAKE_WINDOW` has reached `max_wakes_per_day` (`used`, `limit`); `last_problem` is the newest ended row when its outcome is `start_failed`, `timed_out`, `wrapper_failed` or `exited` with a non-zero code. `status` and `list` call it; `list -j` still equals the `status` document; `Nothing needs you.` is unchanged by waking
  - [ ] `docs/cli-contract.md` and `docs/mcp-server.md`: the `wake` field and each nested field, including `overdue` (the prose is 8.1)
  - [ ] Success: pyright clean; the read-side-defined-once test still passes (`list` reuses `status`'s builder)
- [ ] **7.2 `wake_status` tests**
  - [ ] `tests/operations/test_wake_status.py`: no `wake` for a member without a command; a live row is in `running` with `overdue` false; a row past its deadline with a null `ended_at` is in `running` with `overdue` true, carries `command_pid` and `log_stem`, and the member can be claimed again (it is not live); at the limit `stopped` has `used` and `limit` and below it is null; each of the four problem outcomes is `last_problem`, and `exited` with code 0 is not; the newest ended row decides; an `exited` zero row after an older failure clears it; `list -j` equals `status`; `Nothing needs you.` holds with a running wake
  - [ ] No argv text in the document: run `run_wake` (5.3) for a member whose command's executable name holds a secret-like marker, so the row ends `start_failed` through the real `detail` path; build the `status` document and assert the marker occurs only in the `command` field, not in `last_problem.detail` or any other field
  - [ ] Success: checks pass
- [ ] **7.3 The Waking section of the text renderer**
  - [ ] `cli/render/` (the module that renders member status): a **Waking** section per D9: the command; `running since <age>, stops <time>` when `overdue` is false; when true `overdue since <time>: its wrapper is gone; the command's own cap ends it, or check and stop pid <pid>, log <path>` (with no pid text when `command_pid` is null); `waking stopped: <used> of <limit> wakes used in the last 24 h`; `last wake <outcome> <age> ago: <detail>, log <path>`. Reuse the existing age formatter
  - [ ] Success: pyright clean
- [ ] **7.4 Renderer tests**
  - [ ] `tests/cli/render/test_waking_section.py` (added): each of the four lines for a built `WakeStatus`; the overdue line with and without a pid; no Waking section for a member without a command; render the same marker-bearing `start_failed` member as 7.2 builds: the marker appears only on the command line and the `last wake` line holds none
  - [ ] Success: checks pass

**Commit**: `feat: show waking per member in list and status`

## 8. Documents and amendments (D12, Departures; step 6)

- [ ] **8.1 The wake-command contract and contract prose**
  - [ ] The docs need to name no agent CLI. If they name one, run it with `--help` and copy the flags it prints; if the command is not installed or prints no usage, the docs do not name it
  - [ ] `docs/cli-contract.md`, a section "The wake command": the PM sets it with `amoeba add --wake-command`; it runs in the member's checkout with no arguments from Amoeba and no stdin; it must check `inbox` at its start, accept before working, decline with a reason when the rules do not settle it, reply `done` with the result, check `inbox` again before it ends, and exit; it must carry its own cost or time cap, which is the only bound if its wrapper is killed (Amoeba cannot check that the command has one: it is the PM's duty, and the docs say so); it runs with only the `WAKE_ENV_NAMES` variables, so a script loads its own secrets; it is stopped at `wake_timeout_seconds`; its stdout and stderr go to the wake's log (name the path); the command is shown in plain text by `list members`, `list -j` and `status`, so no secret in it; a pipe or an environment assignment needs a script. Name the `list` lines, including `overdue`. The example is a script command carrying a `--max-seconds` flag (9.1 builds the fixture agent that takes it)
  - [ ] `docs/cli-contract.md` also: `wake-run` as internal; `SendResult.wake_problem`; the wake step's cases and exits (the design's D2 "What a wake does not do" list). `docs/store-contract.md`: "How each state ends with nobody editing a file" gains the wake row (end, overdue, retention) and the limit's exit by the clock
  - [ ] `tests/test_contract_docs.py` or `tests/test_wake_docs.py` (added function): the example command in the `cli-contract.md` section carries a cap flag, and the test fails when the example does not (a negative case with the flag removed from a copy)
  - [ ] Success: `tests/test_contract_docs.py` and the new docs test pass
- [ ] **8.2 Amend the architecture and the plan**
  - [ ] `user/architecture/240-arch.agent-messaging.md`: read the Waking section and the "Store and config" paragraph and amend each sentence that differs from the design's Departures: the directory is Context Forge's `projectPath` (not "the directory the member was registered with"); the wrapper records how the wake ended and the row is kept (not "clears it on exit"); one row per wake, a rolling 24 hours, no wrapper pid, no stored count; `wake-run` is CLI-only; `add` can clear the setting; the explicit environment (`WAKE_ENV_NAMES`, never the sender's); no Amoeba stop of a command after its wrapper is killed; the limit counts failed starts; a wake starts at `send` or a same-id retry while `open`; the sweep's fourth step. The settings sentence ("with defaults defined once in the config layer") must say the two wake keys are required with no default in code, the suggested values appearing only in the config contract's example (D8)
  - [ ] `user/architecture/240-slices.agent-messaging.md`: plan entry 5 (244): the wording that differs (rows kept, per-row `wakes`, rolling day, `projectPath`). Its Dependencies line already reads 240, 241, 242, 243, so it is not touched. In Implementation Order, the Dependencies bullet's sentence "244 needs 241's live-session check." becomes "244 needs 240 to 243 built and integrated, 241's live-session check among them."
  - [ ] Success: `grep -c "WAKE_ENV_NAMES" user/architecture/240-arch.agent-messaging.md` is at least 1; `grep -n "244 needs 241's live-session check\." user/architecture/240-slices.agent-messaging.md` finds nothing; `grep -n "with defaults defined once in the config layer" user/architecture/240-arch.agent-messaging.md` finds nothing; checks pass

**Commit**: `docs: document waking and amend the architecture and plan`

## 9. Fixture agent and live test (D12; step 6)

- [ ] **9.1 `tests/live/waking/fixture_agent.py`**
  - [ ] A stand-in agent: runs `amoeba inbox -j`, accepts then completes each open request with `amoeba reply` (read `docs/cli-contract.md` for the real flags), rereads `inbox` before it exits, and takes the `--max-seconds` cap that 8.1's example uses and enforces it. Flags on its command line tell it to wait on a gate file (`--gate-file PATH`), to sleep past the timeout (`--sleep-seconds N`), and to write its parent pid to a file (`--parent-pid-file PATH`; the wrapper's pid, for the SIGKILL test). These are flags, not environment variables, because the wrapper passes the command only the `WAKE_ENV_NAMES` variables (D6). It finds `amoeba` through `PATH` only, since the wrapper's environment is the explicit one (9.2 puts the installed script's directory on the `PATH` of the CLI calls that send, which the wrapper copies). Spend: none
  - [ ] A second small script in the same directory, `recorder_command.py`, writes its own argv, its whole environment and what it reads from stdin to a file named by its first argument, then exits (used by 9.2's message-text case)
  - [ ] Success: `uv run ruff check` and `uv run pyright` are clean on both scripts; 9.2 exercises them
- [ ] **9.2 `tests/live/waking/` live tier**
  - [ ] Layout: modelled on `tests/live/program/` and `tests/live/mcp/conftest.py`: real `cf` and two git fixture repos in one program. The CLI is the script beside `sys.executable` (`Path(sys.executable).with_name("amoeba")`), as `tests/live/pause/harness.py` and `tests/live/mcp/test_mcp_walkthrough_live.py` find theirs; `deps.amoeba_script()` looks in the same place, so the wrapper runs the same build
  - [ ] Environment: each CLI call that sends gets `AMOEBA_HOME` set to a throwaway directory (the first test asserts the store lies under it) and a `PATH` that starts with `Path(sys.executable).parent`, so the fixture agent's `amoeba` calls reach the same script and store. A wake command is the quoted interpreter path, the fixture script's path and its flags, including the case's control flags from 9.1 (`shlex.quote` each). Only the `WAKE_ENV_NAMES` variables reach the command, so a case controls the fixture through these flags, never through the test's environment
  - [ ] Config: the throwaway config is `example_config_text()` with its values for the two wake keys replaced by `wake_timeout_seconds` 5 and `max_wakes_per_day` 2 in the test's own copy; the contract's example keeps its suggested values (D8). Harness constants (the polling wait and its bound) are named at the top and every wait is a bounded poll
  - [ ] Cases, each from the design's Verification Walkthrough steps 3 to 7: a request wakes the fixture once and a second request during the wake is in its `inbox`, both end `done` and `list` shows no last problem; the limit stops the third wake and the request stays `open` with the counts in `list`; a missing executable ends `start_failed` and the request stays `open`; the sleeping fixture ends `timed_out` after the timeout and its process group is gone; `--no-wake-command` leaves a later send starting nothing; a push-confirmed live session (a fixture `sessions` row) blocks the wake and an unconfirmed one does not; a note to a member with a command starts nothing
  - [ ] The message-text case: the member's command is `recorder_command.py`; a request whose subject and body hold marker strings wakes it, and the file it wrote holds neither marker in its argv, its environment or its stdin (stdin is empty). This is the design's criterion on the command itself; 6.4's spawn check covers the wrapper
  - [ ] The SIGKILL case: SIGKILL the wrapper while the fixture runs; the row stays unended, is live until its deadline then shows as overdue with the pid and log path, Amoeba sends no signal to the old command (the test checks it still runs, then kills it itself), the next send starts a new wake, and `sweep` with a clock past retention deletes the row
  - [ ] Success: `uv run pytest tests/live/waking` passes; `tests/live/program`, `tests/live/messaging` and 241's channel tier still pass

**Commit**: `test: add the waking fixture agent and live tier`

## 10. Final verification

- [ ] **10.1 Final verification**
  - [ ] Run Verification Walkthrough steps 1 to 8 (all four checks; steps 2 to 7 under a throwaway `AMOEBA_HOME`; `uv run pytest tests/live/waking`); step 9 is the Phase 7 checklist below. The live tier may stand for the manual steps; note which
  - [ ] Confirm by name: `tests/test_contract_docs.py`, `tests/test_import_boundaries.py`, `tests/test_store_opened_only_by_state_move.py`, `tests/test_read_side_defined_once.py`, `tests/store/test_vocabulary_pinning.py` and `tests/test_message_timing.py` pass; `grep -rn "except Exception" src/amoeba/operations/wake*.py` finds only the wrapper's process boundary
  - [ ] Confirm 240 to 243 are unchanged apart from what the design names: `git diff {target} -- tests | grep '^-[^-]'` lists only the assertions tasks 2.1, 4.4, 6.1 and 6.8 name, and config keys added to fixtures by 1.2; every other test change is an added function
  - [ ] In `user/slices/244-slice.waking.md`: update the Verification Walkthrough where Phase 6 changed it (it says it is refined when Phase 6 is complete)
  - [ ] Success: all checks pass; every Success Criteria line in the design maps to a passing test named in a note under this task

**Commit**: `docs: refine the 244 walkthrough after final verification`

### Phase 7 hand-off (not tasks; nothing here is checked off in this file)

Phase 6 is complete when sections 0 to 10 are checked. These items are not tasks; the implementing agent does them in Phase 7, after the code review passes and the slice is merged (the merge is Phase 7's, not a task). Designated by `CLAUDE.md`.

**P7.1 Update the live install**

From the target checkout: `uv run python scripts/update_live.py update`. It backs up the live store and config to `~/.local/state/amoeba/backups/<stamp>/`, appends any config key the new code requires (value from the config contract's example), installs the target, migrates the store through `amoeba list`, and checks the schema version, integrity, foreign keys, the member count and the installed `amoeba-mcp` tool list. If any check fails it restores the backup and reinstalls the previous commit itself, and exits 1. It needs `--previous <commit>` only when no earlier run has recorded the installed commit. Paste its output into the slice notes, and restart the client sessions it lists (they run the old `amoeba-mcp` until restarted). `uv run python scripts/update_live.py restore` puts the newest backup back later; a successful update deletes the older backup set
