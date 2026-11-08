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
dateUpdated: 20261108
status: not_started
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
- The trial runs in the PM's own repos (`trading-data`, `trading-engine`, `trading-ui`). Tasks that need the PM's real work to happen (5.x) are waiting steps, not PM approvals: an agent runs the review passes (D6) and records results. When a task cannot proceed because nothing has happened yet (no pauses), write `BLOCKED:` with the reason and stop.
- D8: nothing that changes what an answer says (prompts, passage assembly, the screen's phrase list, models, limits) changes before the verdict; record such changes as proposed fixes.
- Tests use `AMOEBA_HOME`; nothing destructive runs against the real store `~/.config/amoeba/`. Never put secrets in fixtures or the note.
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Work on branch `225-slice.scenario-a-trial`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- Next slices: 226 MCP server, 227 program dependencies (gated on the verdict).

## 0. Setup

- [ ] **0.1 Create the branch**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [ ] Confirm the working tree is clean and you are on the target
  - [ ] `git checkout -b 225-slice.scenario-a-trial {target}`
  - [ ] Success: `git branch --show-current` prints `225-slice.scenario-a-trial`

- [ ] **0.2 Confirm dependencies and locate inputs**
  - [ ] Confirm `src/amoeba/operations/answering_run.py`, `handle_pause.py`, `status.py`, `decisions.py` and `docs/squadron-hook.md` exist and `amoeba status --help` runs; if not, write `BLOCKED: slices 223 and 224 not merged` under this task and stop
  - [ ] Check `sq` for #302: `sq run --help` and the squadron config docs for a pause-command setting and a per-run opt-out. Note the exact flag name and config line, or "absent"
  - [ ] Check `sq runs list --json` (#303) exists. Note the result
  - [ ] Confirm the five D1 repos' paths and that `trading-data`, `trading-engine`, `trading-ui` each have `CLAUDE.md`, and `trading-data` has `project-documents/user/project-guides/000-concept.trading.md`; a missing file is written down, not created
  - [ ] Find the initiative plan file containing the 220 entry (`grep -rl "Program Tool" project-documents/user`); note its path
  - [ ] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [ ] Success: a note under this task (copied into the trial note at 5.1) lists the #302 flag and config line (or absent), the #303 result, the member paths, the initiative plan path and the baseline result

## 1. Opt-out flag and hook line (D3)

- [ ] **1.1 `PAUSE_COMMAND_OPT_OUT_FLAG` in the answering run, with test**
  - [ ] If 0.2 found #302 absent, write `BLOCKED: waiting on squadron#302` under this task and stop
  - [ ] In `operations/answering_run.py` define `PAUSE_COMMAND_OPT_OUT_FLAG` once, using #302's shipped form, and add it to the `sq run` command the answering run builds. The `answering_run` skip in `handle_pause` is unchanged
  - [ ] Unit test: the command built for an answering run contains the flag exactly once; a test of the existing command builder's other arguments still passes unchanged. The test fails before the change
  - [ ] Success: module imports; pyright strict clean; tests pass

- [ ] **1.2 Document the hook line**
  - [ ] In `docs/squadron-hook.md` replace the deferred-to-225 text with the exact config line from #302's shipped form, and how a watching PM passes the opt-out. State whether the setting is user-level (configured once; pauses outside members skip as `not_a_project` or `not_in_program`) or per-project (configured in each D1 member)
  - [ ] Success: the file has the exact line copied from #302's docs, with no placeholder values left

- [ ] **1.3 Checks**
  - [ ] Run the checks once; fix failures introduced by this slice
  - [ ] Success: all four pass

**Commit**: `feat: add pause-command opt-out to the answering run and document hook line` with the body line `Closes #35` (the issue closes when the slice merges)

## 2. Install and register (D1, D2)

- [ ] **2.1 Install the tool**
  - [ ] From the repo root on the slice branch: `uv tool install --force .` (not editable); `which amoeba` prints a path
  - [ ] Record `git rev-parse --short HEAD` as the installed commit
  - [ ] Success: `amoeba --help` runs from a directory outside the repo

- [ ] **2.2 Write the config**
  - [ ] Create `~/.config/amoeba/config.yaml` from the example in `docs/config-contract.md`. Credentials come from the environment, never the file. Answer and check models are non-Claude aliases until #299 lands (D8: do not change them mid-trial)
  - [ ] Save a copy of the values used (no secrets) for the note
  - [ ] Success: `amoeba status` run from outside every member exits without a config error

- [ ] **2.3 Register the trading program**
  - [ ] From `trading-data`, run `amoeba set_up --file -` with the D1 program: `program: trading`, concept `member: trading-data` at `project-documents/user/project-guides/000-concept.trading.md`, members `trading-data`, `trading-engine`, `trading-ui`, each `rules_paths: [CLAUDE.md]`
  - [ ] Run the same call again
  - [ ] Success: first call prints `applied`; the repeat prints `unchanged`

- [ ] **2.4 Configure the hook**
  - [ ] Add the line from `docs/squadron-hook.md` to Squadron's config (user-level), or to each D1 member's config if #302 is per-project
  - [ ] Confirm the hook's environment reaches `sq`, `cf`, `git`, `amoeba` and the model credentials (D2): from a member, run a minimal command through the same mechanism the hook uses and check each is found
  - [ ] Success: the check finds all five; nothing is written to the file with secrets in it

## 3. Fixes for real shapes (D9, on demand)

- [ ] **3.1 Fixture, test and fix for each real-run failure**
  - [ ] Applies to any crash, parse failure or unreadable input from a real run (`handle_pause` exit 3, `RunFileProblem`, `PollFailure`, `sources_missing`, `sources_unreadable`). Run this task when tasks 4 or 5 meet one; if none occurred by the end of task 5, mark it complete with the note "none occurred"
  - [ ] For each: save the raw output (secrets redacted) under `tests/fixtures/`; write a test that fails for the reported reason; make the fix; run the checks once; commit with the marker below; reinstall (2.1) only when `pgrep -f "amoeba handle_pause"` finds nothing
  - [ ] Anything touching answer content is a D8 change: record it under Proposed Fixes instead
  - [ ] Success: each shape has a fixture and a test that failed before its fix; all four checks pass

**Commit** (once per fix, skipped when none occurred): `fix: handle real run shapes met in the scenario A trial`

## 4. Sanity pass (not counted)

- [ ] **4.1 Run the live fixture pipeline in each member**
  - [ ] In each of `trading-data`, `trading-engine` and `trading-ui`, run 223's live fixture pipeline (`<amoeba repo>/tests/live/pause/`) and leave it to pause; wait for the hook
  - [ ] Run `amoeba decisions` and `amoeba status` from outside every member
  - [ ] Success: for each member, `decisions` shows an `answerer` record with `resume.outcome: resumed`, or `status` lists the run under `waiting_on_pm`; no question record exists for the answering run's id

- [ ] **4.2 Amoeba's own repo is left alone**
  - [ ] Start the same pipeline in the amoeba repo and let it pause
  - [ ] Success: `amoeba decisions` and `amoeba status` show nothing new for it

- [ ] **4.3 Missing-shape handling (D9)**
  - [ ] If any step in 4.1 or 4.2 crashed, exited 3, or raised `RunFileProblem`, `PollFailure`, `sources_missing` or `sources_unreadable`, handle it under 3.1 before continuing. If none, note "none"
  - [ ] Success: 4.1 and 4.2 succeed, or each failure has a 3.1 entry

## 5. The trial (D5, D6)

- [ ] **5.1 Create the note and record `trial_start`**
  - [ ] Create `user/analysis/220-analysis.scenario-a-trial.md` with `docType: analysis` frontmatter per `file-naming-conventions.md`, and sections: Setup (config values, installed commit, #302 form), Trial Window, Ledger, Counts, Verdict, Proposed Fixes, amoeba#36 need, Appendix (tally recipe)
  - [ ] Record `trial_start` (UTC, ISO-8601) as the start time of the first run after the sanity pass, from that run's run file in `sq runs list --json`. If no such run exists yet, write `BLOCKED: no run since the sanity pass` under this task and stop; resume once one has started
  - [ ] Success: the note exists with the setup and `trial_start` filled in

- [ ] **5.2 Review pass (repeat after each working session)**
  - [ ] From outside every member, run `amoeba decisions --since <trial_start>` and `amoeba status`; save both outputs
  - [ ] Catch-up (D6): for each run `status` lists as `unhandled`, `claim_stale` or `answered_unresumed`, run `amoeba handle_pause <run_id>` from its listed directory; count its question by that call's outcome
  - [ ] Add one ledger row per counted question, keyed `(run_id, paused_at)`: answered without the PM or not (an automatic answer that was resumed and neither overridden nor judged wrong); for the rest the `waiting_reason` or why Amoeba missed it (`cause unknown` if the catch-up does not show it); anything that went wrong (wrong answer, false screen match, should-have-answered); one line on the fix (rule line, passage, prompt change, code fix). A PM override is always a wrong answer
  - [ ] Detection: a PM override is a `pm` record in `decisions` for the same run after an `answerer` record. Judged wrong: read each automatic answer against its cited passages and the member's rules file; mark it wrong if it contradicts either or authorizes something the not-authorized list forbids. The PM can change any row
  - [ ] List excluded questions (watching-PM opt-out runs, PM answered or resumed outside Amoeba, Amoeba's own answering runs) separately, not in the count
  - [ ] Note the installed commit on each row
  - [ ] Run `amoeba mark_read --through <seq>` after reading
  - [ ] Any answer that authorized an item on the member's not-authorized list: file an issue against 223's check and screen (D7)
  - [ ] Success: every question in `decisions` and every missed hook in `status` after `trial_start` is a ledger row or an excluded entry

- [ ] **5.3 Stop check (D5)**
  - [ ] After each review pass, count ledger rows and members represented
  - [ ] If fewer than 20 counted questions, or fewer than two members, write `BLOCKED: trial needs more real work (<n> counted, <m> members)` under this task, leave it unchecked and stop; resume with the next working session's 5.2
  - [ ] Success: at least 20 counted questions from at least two members; record that pass as the stop pass in the note

## 6. Tally and verdict (D7, D10)

- [ ] **6.1 Tally**
  - [ ] Write the `jq` recipe over the CLI's JSON in the note's appendix and run it for the counts `decisions` and `status` hold: answered without the PM, waiting by reason, PM overrides
  - [ ] Count wrong answers, false screen matches and should-have-answered from the ledger's rows (these live only there)
  - [ ] Fill Counts with all five groups, naming the source of each
  - [ ] Success: the counts equal the number of ledger rows, with no row uncategorised

- [ ] **6.2 Verdict**
  - [ ] Go if more than half of counted questions were answered without the PM, rethink otherwise; write it with the share
  - [ ] List proposed fixes (including any D8-deferred change) with the evidence row for each
  - [ ] State whether the trial shows a need for amoeba#36 (closing waiting questions whose run moved on)
  - [ ] For a rethink, list the design questions the numbers raise
  - [ ] Success: the note states go or rethink with the share, the proposed fixes, the amoeba#36 answer and, if rethink, the design questions

- [ ] **6.3 Record in the plans**
  - [ ] Go: add one line to the 220 entry in the initiative plan (path from 0.2) with the share and a link to the note
  - [ ] Rethink: add `Status: on hold, scenario A trial verdict: rethink (see note)` to the 227 entry in `user/architecture/220-slices.program-tool.md` and to the initiative plan's 220 entry
  - [ ] Success: the plan files show the verdict line that matches the note

**Commit**: `docs: add scenario A trial note and verdict`
