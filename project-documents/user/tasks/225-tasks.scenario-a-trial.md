---
docType: tasks
slice: scenario-a-trial
project: amoeba
lld: user/slices/225-slice.scenario-a-trial.md
dependencies:
- 223-slice.pause-handling
- 224-slice.status-and-decisions
projectState: Slices 221 to 224 are designed with task files; this slice assumes 223
  and 224 are merged (`handle_pause`, `answer`, `status`, `decisions`, `mark_read`
  on the CLI, `docs/squadron-hook.md` written without the exact config line). Nobody
  has run Amoeba. `ecorkran/squadron#302` (pause command with per-run opt-out) and
  `#303` (`sq runs list --json`) may still be open.
dateCreated: 20261107
dateUpdated: 20261112
status: complete
turns: 8
promptTokens: 286106
cachedTokens: 248312
cacheWriteTokens: 37780
completionTokens: 7599
durationSeconds: 52.1
costUsd: 0.252267
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.2522666
    completionTokens: 7599
---

# Tasks: Scenario A Trial

## Context Summary

- Working on slice 225 (design: `user/slices/225-slice.scenario-a-trial.md`; decisions D1 to D10 are cited by number).
- A trial, not a build. Code is limited to the answering run's opt-out flag and the hook config line (D3, closes amoeba#35), plus D9 fixtures and fixes for real shapes the tests missed. Everything else is setup, running real work, a ledger and a verdict note.
- Changed: `operations/answering_run.py` (`PAUSE_COMMAND_OPT_OUT_FLAG`), `docs/squadron-hook.md`. New: `user/analysis/220-analysis.scenario-a-trial.md`, fixtures under `tests/fixtures/` as D9 requires. Edited at the end: the 227 entry in `user/architecture/220-slices.program-tool.md` (rethink only) and the initiative plan's 220 entry.
- The counted trial (old tasks 5.x and 6.x, D5 to D7, D10) is dropped: it needed PM-driven work on demand. What remains is the opt-out flag, the hook line, install, registration and the sanity pass; task 5 records the switch-on in the plans.
- D8: nothing that changes what an answer says (prompts, passage assembly, the screen's phrase list, models, limits) changes before the verdict; record such changes as proposed fixes.
- Tests use `AMOEBA_HOME`; nothing destructive runs against the real store `~/.config/amoeba/`. Never put secrets in fixtures or the note.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Work on branch `225-slice.scenario-a-trial`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- Next slices: 226 MCP server, 227 program dependencies (gated on the verdict).

## 0. Setup

- [x] **0.1 Create the branch**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [x] Confirm the working tree is clean and you are on the target
  - [x] `git checkout -b 225-slice.scenario-a-trial {target}`
  - [x] Success: `git branch --show-current` prints `225-slice.scenario-a-trial`
  Note: branch 225-slice.scenario-a-trial already existed and was checked out at main's tip (9cca9f4) with a clean tree; target is main (integration_branch empty).

- [x] **0.2 Confirm dependencies and locate inputs**
  - [x] Confirm `src/amoeba/operations/answering_run.py`, `handle_pause.py`, `status.py`, `decisions.py` and `docs/squadron-hook.md` exist and `amoeba status --help` runs; if not, write `BLOCKED: slices 223 and 224 not merged` under this task and stop
  - [x] Check `sq` for #302: `sq run --help` and the squadron config docs for a pause-command setting and a per-run opt-out. Note the exact flag name and config line, or "absent"
  - [x] Check `sq runs list --json` (#303) exists. Note the result
  - [x] Confirm the five D1 repos' paths and that `trading-data`, `trading-engine`, `trading-ui` each have `CLAUDE.md`, and `trading-data` has `project-documents/user/project-guides/000-concept.trading.md`; a missing file is written down, not created
  - [x] Find the initiative plan file containing the 220 entry (`grep -rl "Program Tool" project-documents/user`); note its path
  - [x] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [x] Success: a note under this task (copied into the trial note at 5.1) lists the #302 flag and config line (or absent), the #303 result, the member paths, the initiative plan path and the baseline result
  Note: all files present; `amoeba status --help` runs (via `uv run`; `amoeba` is not yet on PATH until 2.1). #302 shipped: config key `pipeline.on_pause_command` (set with `sq config set pipeline.on_pause_command "amoeba handle_pause"`, user-level in ~/.config/squadron/config.toml, or `--project` for per-repo .squadron.toml) and per-run opt-out `sq run --no-pause-hook`; key currently unset. #303: `sq runs list --json` exists (fields run_id, pipeline, status, working_directory, checkpoint); both squadron issues are CLOSED; sq 0.24.26. Member paths: /Users/manta/source/repos/manta/{trading-data,trading-engine,trading-ui}, each has CLAUDE.md; trading-data has project-documents/user/project-guides/000-concept.trading.md. Initiative plan: project-documents/user/project-guides/001-initiative-plan.amoeba.md. Baseline: format, ruff, pyright clean, 1452 tests pass.

## 1. Opt-out flag and hook line (D3)

- [x] **1.1 `PAUSE_COMMAND_OPT_OUT_FLAG` in the answering run, with test**
  - [x] If 0.2 found #302 absent, write `BLOCKED: waiting on squadron#302` under this task and stop
  - [x] In `operations/answering_run.py` define `PAUSE_COMMAND_OPT_OUT_FLAG` once, using #302's shipped form, and add it to the `sq run` command the answering run builds. The `answering_run` skip in `handle_pause` is unchanged
  - [x] Unit test: the command built for an answering run contains the flag exactly once; a test of the existing command builder's other arguments still passes unchanged. The test fails before the change
  - [x] Success: module imports; pyright strict clean; tests pass
  Note: slice 223 had already shipped the flag as `NO_PAUSE_HOOK_FLAG` (`--no-pause-hook`) in answering_run.py with tests (argv carries it exactly once; one-constant-in-one-module test). #302 is present, so no BLOCKED. This task renamed the constant to the design's `PAUSE_COMMAND_OPT_OUT_FLAG` (src, 3 test files, live harness); no behavior change, so no failing-before test is possible; existing tests cover it and pass.

- [x] **1.2 Document the hook line**
  - [x] In `docs/squadron-hook.md` replace the deferred-to-225 text with the exact config line from #302's shipped form, and how a watching PM passes the opt-out. State whether the setting is user-level (configured once; pauses outside members skip as `not_a_project` or `not_in_program`) or per-project (configured in each D1 member)
  - [x] Success: the file has the exact line copied from #302's docs, with no placeholder values left
  Note: docs/squadron-hook.md now has the exact `sq config set pipeline.on_pause_command "amoeba handle_pause"` line, the user-level vs per-project choice, and the `--no-pause-hook` opt-out.

- [x] **1.3 Checks**
  - [x] Run the checks once; fix failures introduced by this slice
  - [x] Success: all four pass
  Note: format, ruff, pyright clean; 1452 tests pass.

**Commit**: `feat: add pause-command opt-out to the answering run and document hook line` with the body line `Closes #35` (the issue closes when the slice merges)

## 2. Install and register (D1, D2)

- [x] **2.1 Install the tool**
  - [x] From the repo root on the slice branch: `uv tool install --force .` (not editable); `which amoeba` prints a path
  - [x] Record `git rev-parse --short HEAD` as the installed commit
  - [x] Success: `amoeba --help` runs from a directory outside the repo
  Note: installed with `uv tool install --force .` from the slice branch at commit 93e8f41; `which amoeba` = /Users/manta/.local/bin/amoeba; `amoeba --help` runs from /tmp.

- [x] **2.2 Write the config**
  - [x] Create `~/.config/amoeba/config.yaml` from the example in `docs/config-contract.md`. Credentials come from the environment, never the file. Answer and check models are non-Claude aliases until #299 lands (D8: do not change them mid-trial)
  - [x] Save a copy of the values used (no secrets) for the note
  - [x] Success: `amoeba status` run from outside every member exits without a config error
  Note: ~/.config/amoeba/config.yaml written from docs/config-contract.md's example. Values (no secrets): answer_model sonnet-high, check_model sonnet, max_cost_usd 0.5, answer_limit 3, passages_max_chars 60000, answering_wait_seconds 600, resume_wait_seconds 60, default five authorize_items. Deviation from task text: aliases are Claude aliases (the ones the live tier uses via AMOEBA_LIVE_*), not non-Claude, because squadron#299 is now CLOSED. `amoeba status` from /tmp exits 0 (lists old unplaced runs as directory_missing/no_directory).

- [x] **2.3 Register the trading program**
  - [x] From `trading-data`, run `amoeba set_up --file -` with the D1 program: `program: trading`, concept `member: trading-data` at `project-documents/user/project-guides/000-concept.trading.md`, members `trading-data`, `trading-engine`, `trading-ui`, each `rules_paths: [CLAUDE.md]`
  - [x] Run the same call again
  - [x] Success: first call prints `applied`; the repeat prints `unchanged`
  Note: first set_up call from trading-data printed `applied` (program trading + 3 members); repeat printed `unchanged`.

- [x] **2.4 Configure the hook**
  - [x] Add the line from `docs/squadron-hook.md` to Squadron's config (user-level), or to each D1 member's config if #302 is per-project
  - [x] Confirm the hook's environment reaches `sq`, `cf`, `git`, `amoeba` and the model credentials (D2): from a member, run a minimal command through the same mechanism the hook uses and check each is found
  - [x] Success: the check finds all five; nothing is written to the file with secrets in it
  Note: `sq config set pipeline.on_pause_command "amoeba handle_pause"` (user-level, ~/.config/squadron/config.toml). Checked via the hook's mechanism (no shell, inherited env, cwd = member): sq, cf, git, amoeba found; OPENROUTER_API_KEY set; ANTHROPIC/OPENAI/GEMINI keys unset in this env (Claude aliases rely on the SDK login); the sanity pass (4.1) proves the model path. cf resolves through an fnm multishell path of the starting shell.

## 3. Fixes for real shapes (D9, on demand)

- [x] **3.1 Fixture, test and fix for each real-run failure**
  - [x] Applies to any crash, parse failure or unreadable input from a real run (`handle_pause` exit 3, `RunFileProblem`, `PollFailure`, `sources_missing`, `sources_unreadable`). None occurred in the sanity pass (4.3) and the counted trial is dropped; a later real-run failure is filed as an issue
  - [x] Success: none occurred
  Note: none occurred.

**Commit** (once per fix, skipped when none occurred): `fix: handle real run shapes met in the scenario A trial`

## 4. Sanity pass (not counted)

- [x] **4.1 Run the live fixture pipeline in each member**
  - [x] In each of `trading-data`, `trading-engine` and `trading-ui`, run 223's live fixture pipeline (`<amoeba repo>/tests/live/pause/`) and leave it to pause; wait for the hook
  - [x] Run `amoeba decisions` and `amoeba status` from outside every member
  - [x] Success: for each member, `decisions` shows an `answerer` record with `resume.outcome: resumed`, or `status` lists the run under `waiting_on_pm`; no question record exists for the answering run's id
  Note: ran tests/live/pause/asks_question.yaml (model sonnet-high) in trading-data (run sanity-225-data-033755), trading-engine (sanity-225-engine-033858) and trading-ui (sanity-225-ui-033902) with the hook on. `decisions` (seq 1-9) shows `answerer` records with resume.outcome resumed for all three; every record is for the member runs, none for an answering run's id. The fixture re-asks after each resume, so each run ended `waiting_on_pm` with `answer_limit_reached` after 3 answers (expected for the fixture). These three sanity runs stay paused and predate trial_start, so list them as excluded in the note.

- [x] **4.2 Amoeba's own repo is left alone**
  - [x] Start the same pipeline in the amoeba repo and let it pause
  - [x] Success: `amoeba decisions` and `amoeba status` show nothing new for it
  Note: sanity-225-amoeba-034003 started in the amoeba repo and paused; after 40s `decisions` still has 9 records (last seq 9) and `status` has no entry for it.

- [x] **4.3 Missing-shape handling (D9)**
  - [x] If any step in 4.1 or 4.2 crashed, exited 3, or raised `RunFileProblem`, `PollFailure`, `sources_missing` or `sources_unreadable`, handle it under 3.1 before continuing. If none, note "none"
  - [x] Success: 4.1 and 4.2 succeed, or each failure has a 3.1 entry
  Note: none. No crash, exit 3, RunFileProblem, PollFailure, sources_missing or sources_unreadable.

## 5. Record the switch-on (the counted trial is dropped)

The counted trial (20 questions of real PM work, a ledger, a go/rethink verdict) is dropped: it needs the PM to generate work on demand. Amoeba stays on; `amoeba decisions` and `amoeba status` hold the evidence from normal use, and the PM judges from that.

- [x] **5.1 Record in the plans**
  - [x] In the initiative plan's 220 entry (path from 0.2), add one line: scenario A switched on 2026-11-12 (hook live at user level, `trading` program registered, sanity pass clean); the counted trial and verdict were dropped as needing PM-driven work; evidence comes from normal use
  - [x] In `user/architecture/220-slices.program-tool.md`: rewrite the 225 entry to say what was done; remove the go-verdict gate from the 227 entry and the "Gated on the Scenario A Trial" text so 227's dependencies are 225 and 226
  - [x] Success: no plan file says 227 waits on a verdict
  Note: verified by PM: initiative plan line 44 has the switch-on line; architecture 220 file has the 225 entry rewritten, 227 renamed "Scenario B" with dependencies "225 and 226"; grep for "verdict"/"go verdict"/"waits on the trial" finds no remaining claim that 227 waits on a verdict.

**Commit**: `docs: drop the counted scenario A trial and record switch-on in the plans`
