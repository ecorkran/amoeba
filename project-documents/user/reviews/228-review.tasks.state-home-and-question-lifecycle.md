---
docType: review
layer: project
reviewType: tasks
slice: state-home-and-question-lifecycle
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261112
dateUpdated: 20261112
reviewedSha: d413d6aaefb7268377a2663aced588ceaca91af7
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 1552723
cachedTokens: 1357216
cacheWriteTokens: 195485
completionTokens: 81165
durationSeconds: 363.8
costUsd: 0.453723
costBasis: provider
runId: run-20261112-p5-f2bee377
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every functional, technical and integration success criterion has a task"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing has no cycles, and test tasks follow implementation with one break"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md"
  - id: F003
    severity: pass
    category: verification
    summary: "Referenced modules, constants and fixtures exist"
    location: "src/amoeba/config/home.py:34"
  - id: F004
    severity: pass
    category: rules
    summary: "No deferral, no wait on real usage, config and state separated"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md"
  - id: F005
    severity: note
    category: nfr
    summary: "No load test is required; CI gates the plain pytest run"
    location: ".github/workflows/ci.yml:39-40"
  - id: F006
    severity: concern
    category: safety
    summary: "Task 13.4 rebuilds the live store on a self-asserted designation"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:45"
  - id: F007
    severity: concern
    category: process
    summary: "The final commit marker hard-codes issue numbers and may commit notes only"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:443"
  - id: F008
    severity: concern
    category: sizing
    summary: "One task file is overweight for the slice"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md"
  - id: F009
    severity: concern
    category: tests
    summary: "Task 7.1 has no test"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:241"
  - id: F010
    severity: concern
    category: coverage
    summary: "No single task owns the \"walk every state to its exit\" test"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:424"
  - id: F011
    severity: concern
    category: rules
    summary: "The set-aside `legacy-<stamp>` file has no exit"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:115"
  - id: F012
    severity: concern
    category: operations
    summary: "Dead end: a run whose start directory is gone is skipped forever"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:293"
  - id: F013
    severity: concern
    category: clarity
    summary: "`resume_bound_seconds(config, deps)` cannot read its poll timeout from `deps`"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:245"
  - id: F014
    severity: note
    category: clarity
    summary: "Name precision in 9.1"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:305"
  - id: F015
    severity: note
    category: schema
    summary: "The 003 rebuild must keep the composite key"
    location: "src/amoeba/store/schema/001_baseline.sql:80"
  - id: F016
    severity: note
    category: operations
    summary: "`pgrep` may not detect answering work during the backup"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:428"
  - id: F017
    severity: note
    category: verification
    summary: "Copied status claims and unverified facts"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:38"
  - id: F018
    severity: note
    category: tests
    summary: "Missing test cases and one misleading message"
    location: "project-documents/user/tasks/228-tasks.state-home-and-question-lifecycle.md:207"
  - id: F019
    severity: note
    category: operations
    summary: "Operator walkthrough: dead ends found"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:438"
---

# Review: tasks — slice 228

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Every functional, technical and integration success criterion has a task

Each design criterion maps to tasks and tests: legacy move and set-aside (2.1–2.7), dismiss (6.3–6.4), retract (6.5–6.6), limit reset (4.1–4.2), run_moved_on and run_gone (7.4–7.9), set_up remove (10.1–10.6), pruning (11.2–11.7), wrong_checkout (8.1–8.2), calls log (9.1–9.4), and the four checks (13.1). Gaps are in the findings below.

### [PASS] Sequencing has no cycles, and test tasks follow implementation with one break

Dependencies run in one direction: homes (1) → move (2) → migration 003 (3) → store writes (4–5) → operations (6–7) → wrong_checkout and calls log (8–9) → set_up (10) → prune (11, which needs the `file_problems` field from 9.3) → docs (12) → validation (13). Each implementation task is followed by its test task except 7.1.

### [PASS] Referenced modules, constants and fixtures exist

Searches confirm the 222–225 modules and helpers the tasks name, including `amoeba_home()` (removed by 1.1), `Store.open`, `EXPECTED_SCHEMA_VERSION = 2` (src/amoeba/store/migrations.py:25), `COUNT_AUTOMATIC_ANSWERS` and `SELECT_PM_PRECEDENT` (src/amoeba/store/sql.py:158, :171), and the walkthrough fixtures under tests/live/pause/. The named constants `RESUME_POLL_INTERVAL_SECONDS` (resume.py:38), `TERMINATE_GRACE_SECONDS` (processes.py:28), `BUSY_TIMEOUT_SECONDS` (store/store.py:28) and `RUN_POLL_TIMEOUT_SECONDS` (deps.py:28) also exist.

### [PASS] No deferral, no wait on real usage, config and state separated

Checked against the Amoeba Design Rules. No in-scope behavior is deferred. No step waits for real events. Config stays in `~/.config/amoeba`, and the store, answering directory, logs and calls log move to the state home. The set-aside file is the exception, covered below.

### [NOTE] No load test is required; CI gates the plain pytest run

The design says `status`'s time bound is "unchanged" but gives no numeric target. Task 7.9's call-count assertion pins the structure: one `sq runs list`, and file checks only. No `tests/load/` task is required. Task 5.2's claim that CI gates its test holds, since ci.yml runs `uv run pytest`. The current ci.yml has no separate `tests/load` step, although earlier reviews (120, 184, 185) cite one. That drift is outside this slice.

### [CONCERN] Task 13.4 rebuilds the live store on a self-asserted designation

sql.md requires that destructive statements on the production database target a store the Project Manager explicitly designated. Line 45 says approval of this task file is that designation. The file has not been approved (`status: not_started`), and a task file cannot designate itself. Task 13.4 moves real answers and runs `DROP TABLE questions` through migration 003 on the live store. Tasks 0–12 never touch that store and can proceed. The PM must name the live store in their own message before 13.4 runs. Until then, mark 13.4 `BLOCKED:`. Rewrite line 45 so the designation has to come from the PM.

### [CONCERN] The final commit marker hard-codes issue numbers and may commit notes only

Task 0.2 says the final commit names only issues still open. The marker hard-codes `(fixes #34, #36, #37)`, which contradicts 0.2. Section 13 changes no code by itself: 13.1 runs checks, 13.2 and 13.4 write notes, and 13.3 fixes only failed walkthrough steps. Unless a walkthrough step fails, the commit at 443 holds check-offs and notes only, which CLAUDE.md forbids. Move the marker to the last code-bearing point, or say the marker applies only if section 13 changes code, and make the message follow 0.2.

### [CONCERN] One task file is overweight for the slice

The file is 444 lines with 64 top-level tasks and roughly 250 checkboxes, for a 13-decision design. Cuts that keep every success criterion:
- Merge 0.1 and 0.2 into one setup task.
- Fold 7.1 (one flag) into 7.8, its only consumer.
- Drop the multi-process race test in 5.2 and use a second connection, as 2.4 does for the lock. Keep 2.4's two-process move test, since D2 step 1 names a second process.
- Remove the duplicate state walks in 6.8 and 7.9 by making one walk test own the states (see the walk-test finding).
- Consider moving 12.3 (edits to the 220, 226 and 227 planning documents) into its own planning step. It is design-directed, but it edits other slices' documents on the slice branch.

### [CONCERN] Task 7.1 has no test

7.1 adds `--all` to `RUNS_LIST_FLAGS` and updates the stub, but no test follows it. The only check is that existing run-list tests pass, so nothing asserts that the flag is passed or that the stub honors it. Task 7.9 exercises it indirectly. Add a test that asserts the argument list contains `--all`, or fold 7.1 into 7.8 and test there.

### [CONCERN] No single task owns the "walk every state to its exit" test

Integration Requirements say a test must walk each state to its exit. The tasks split this: 6.8 covers claimed, waiting_on_pm, closed-then-reopened and retracted; 7.9 adds the sweep rows; 13.1 says "if one is missing, add it". No task creates one walk test covering all the states, and 13.1 hands the gap to whoever runs it. Name one test file in 6.8 that later tasks extend, and make 13.1 run it. Name the exits for `answered`, settled and unresumed, too.

### [CONCERN] The set-aside `legacy-<stamp>` file has no exit

2.5 sets the legacy store aside as `amoeba.sqlite3.legacy-<UTC stamp>` and says it is "never opened again". 11.5 forbids pruning it. The only exit the design names is that the PM can delete it (design line 270). That is a manual file deletion with no command, and the file may hold the only copy of recent answers. The rule requires each state to end without anyone editing files. The design's rare-event argument limits the count per event, not in total. Either name a command or cleanup that ends the file, or state in the design and in docs/store-contract.md that manual deletion is the accepted exit.

### [CONCERN] Dead end: a run whose start directory is gone is skipped forever

If a worktree is removed or renamed, `wrong_checkout` skips every hook call for that run from then on. The skip writes no row, so `dismiss` and `answer` have nothing to act on. The run stays paused, and `status` shows it as `unhandled`. The only exit is Squadron's own command, which no document names. Neither the design nor 8.2 covers a recorded directory that no longer exists. `os.path.realpath` does not raise on a missing path, so the check reports a plain mismatch with no hint that the directory is gone. Name the Squadron exit in the status detail or the docs, and add a test where the recorded directory does not exist.

### [CONCERN] `resume_bound_seconds(config, deps)` cannot read its poll timeout from `deps`

The formula uses `RUN_POLL_TIMEOUT_SECONDS`, defined at `src/amoeba/operations/deps.py:28`. `deps` wraps the poll call in `partial(poll_run, timeout_seconds=...)` (deps.py:72), so the timeout cannot be read back from `deps`. The signature also takes an argument the formula does not use. Choose one: `resume_bound_seconds(config)` reading the constant, or a named timeout field on `Deps`. Say which.

### [NOTE] Name precision in 9.1

Task 9.1 says "through `bounded_text`". That is a module name. The function is `cut_to_bound`, imported at `src/amoeba/operations/pause_claim.py:54`. Also, `append_call(directory, entry, now)` takes a `directory` argument, yet the function writes to `calls_log_dir()`, and the JSON line carries its own `directory` field. The task does not say what the argument is. Name the function and rename or remove the argument.

### [NOTE] The 003 rebuild must keep the composite key

Line 80 declares a foreign key from another table to `questions (run_id, paused_at)`. The rebuilt `questions_new` must keep that pair as PRIMARY KEY or UNIQUE, or the foreign key has no valid parent. Task 3.3 says "existing constraints" but does not name this key. I checked that 001 and 002 define no indexes, triggers or views, so 3.3's "none is recreated" holds.

### [NOTE] `pgrep` may not detect answering work during the backup

13.2 and 13.4 treat `pgrep -f "amoeba handle_pause"` finding nothing as "nothing is running". That pattern matches the hook process. Answering work is launched from `src/amoeba/answering/launch.py`. I did not trace its process command line, so I cannot confirm the pattern misses it. If answering children run under another command line, the backup or upgrade could overlap a live writer. Add that process pattern, or record the command line used.

### [NOTE] Copied status claims and unverified facts

The Context Summary says the issues were "verified open 20261112", and the frontmatter repeats the claim. That is a copied status. Task 0.2 re-checks at execution, which is the right place, so the summary should drop "verified". I could not check these facts here: `gh issue view` and `sq --version` did not run. The design's "Checked on 0.24.27" (design line 73) and its listing counts (design line 200) are unverified in the same way.

### [NOTE] Missing test cases and one misleading message

- 6.5 lists `malformed` for a non-integer seq, but 6.6 tests only a blank reason and an unknown seq.
- 6.5 says closures are not listed and the marker and `read_through` are unchanged. No test checks these.
- 6.3 says a rejected `answered` question's detail reads "the answer was given". That is wrong for a `not_delivered` answer, which was never given. Make the wording depend on the outcome.

### [NOTE] Operator walkthrough: dead ends found

I stepped through the design's operator walkthrough: start, first call, normal path, failures, end state and undo. Every state exits through dismiss, answer, the sweep, a refused resume retried from `next`, or set_up, except the two dead ends above: the set-aside file and the run whose start directory is gone. A run dismissed while paused in Squadron exits through Squadron's `sq run --resume`, which the design names. Its `status` shows `next: null`, so Amoeba gives no pointer to that exit.

### Run Digest

- Response length: 14364 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 1552723 / 1357216 / 195485 / 81165 / not computed
- Duration: 363.8 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 19
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 19
- Finding-shaped matches — surviving validation: 19

## Resolution

- **F001 (pass):** No change.
- **F002 (pass):** No change. The one break it names, task 7.1, is folded into 7.7 (see F009).
- **F003 (pass):** No change.
- **F004 (pass):** No change. The set-aside exception is handled under F011.
- **F005 (note):** No change. The review's own point stands: 7.8's call-count assertion pins the structure, and CI runs plain `pytest`. I replaced 5.2's multi-process race test with a second-connection test (see F008).
- **F006 (concern):** Rewrote the Context Summary line so it no longer says approval of the task file is the designation. Task 13.4 now begins with a designation check and writes `BLOCKED:` and stops unless the PM has named `~/.config/amoeba/amoeba.sqlite3` in their own message. Tasks 0 to 13.3 never touch the live store.
- **F007 (concern):** Removed the hard-coded `(fixes #34, #36, #37)` marker. The Context Summary now says the final commit body carries `Fixes #n` for each issue task 0.2 found open. I removed the §12 marker so the docs ride in the final commit, which also holds the 13.x notes, so that commit is never notes-only. Its message is now `docs: document the lifecycle contracts and record slice 228 validation`. 13.4 reports its results in the reply instead of writing a note after that commit.
- **F008 (concern):** Merged the old 0.1 and 0.2 into one branch-and-baseline task (new 0.2). Folded 7.1 into 7.7. Replaced 5.2's multi-process race with a second-connection test, and kept 2.4's two-process move test. Made `tests/operations/test_every_state_exits.py` the one owner of the state walk (see F010). Moved the 220, 226 and 227 plan edits out of the slice branch into new task 0.1, a planning commit on the target before the branch exists, which is where the Git Rules put planning work. The file is now 439 lines.
- **F009 (concern):** Folded 7.1 into 7.7 (`--all` plus its docstring, stub and fixtures) and added a test in 7.8 that `list_runs` passes `--all` and that the stub omits completed runs without it. Renumbered 7.2 to 7.9 as 7.1 to 7.8.
- **F010 (concern):** 6.8 now creates `tests/operations/test_every_state_exits.py` with cases for `claimed`, `waiting_on_pm`, `closed`, a retracted answer, and `answered` settled. 7.8 extends the same file with `claimed` (sweep), `answered` unresumed (sweep, dismiss) and `waiting_on_pm` (sweep). 13.1 runs the file and requires a case per state in the design's list, with no "add it if missing".
- **F011 (concern):** Chose the review's second option. The design (D9) and tasks 11.5 and 12.1 now say deleting the set-aside `amoeba.sqlite3.legacy-<stamp>` file is its accepted exit, and `docs/store-contract.md` will say so. No process reads it, and it may hold the only copy of recent answers, so no automatic cleanup. D13's store-contract bullet matches.
- **F012 (concern):** D10 and tasks 8.1 and 8.2 now say that when the recorded directory no longer exists, the `wrong_checkout` detail says so and names Squadron's own commands (`sq run --resume`) as the way to continue or leave the run. 8.2 adds a test with a missing recorded directory.
- **F013 (concern):** Chose `resume_bound_seconds(config)`, reading the `RUN_POLL_TIMEOUT_SECONDS` constant, since `deps` holds only the already-bound `poll_run`. Updated task 7.1 and its test, and design D4 (the signature and the `2 × RUN_POLL_TIMEOUT_SECONDS` term).
- **F014 (note):** Task 9.1 now names `cut_to_bound` (`upstream/bounded_text.py`). `append_call(log_dir, entry, now)` takes the calls log directory, which the CLI passes as `calls_log_dir()`, and says the entry's own `directory` field is the call's working directory. `last_call` takes `log_dir` too.
- **F015 (note):** Task 3.3 now says `questions_new` keeps `PRIMARY KEY (run_id, paused_at)`, the key `answers` references.
- **F016 (note):** The `pgrep` pattern in 13.2 is now `amoeba (handle_pause|answer|status|set_up|dismiss|retract)`. Answering and resume children are always started by one of those commands (`start_child` in `answering_run.py` and `resume.py`), so none runs without a matched parent. 13.4's recheck reuses it.
- **F017 (note):** Dropped "verified open 20261112" from the Context Summary and the frontmatter. Both now say the issues are tracked as open and task 0.2 rechecks. On the design's dated observations, I ran `sq --version` (0.24.28) and `sq runs list` with and without `--all` on 20261112. `--all` lists more runs than the default, which agrees with the design. The design's "checked on 0.24.27" counts are dated and I left them as written.
- **F018 (note):** 6.6 adds tests that a non-integer seq is `malformed`, that `decisions` does not list closures, and that the marker and `read_through` are unchanged after a retraction. 6.3 and design D5 now word the `not_open` detail by outcome: a `resumed` answer was delivered, and a `not_delivered` one was recorded but never delivered.
- **F019 (note):** The two dead ends are fixed under F011 and F012. For the dismissed run, the `closed` detail in 6.1 now names `sq run --resume` as the way to continue it, so `next: null` no longer leaves the PM without a pointer.
