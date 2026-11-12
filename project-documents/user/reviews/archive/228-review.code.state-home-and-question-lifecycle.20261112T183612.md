---
docType: review
layer: project
reviewType: code
slice: state-home-and-question-lifecycle
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261112
dateUpdated: 20261112
reviewedSha: f4c7d27b50537cac65c741e7e7c4c5c8356106ce
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
diffTruncated: false
effort: xhigh
turns: 23
promptTokens: 3246978
cachedTokens: 2684471
cacheWriteTokens: 562487
completionTokens: 78938
durationSeconds: 348.0
costUsd: 0.992106
costBasis: provider
runId: run-20261112-p6-b8c4559a
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "A paused run with no pause time closes every open question"
    location: "src/amoeba/operations/question_sweep.py:107-111"
  - id: F002
    severity: concern
    category: error-handling-observability
    summary: "Closures made by `status` are lost if the call fails after the sweep"
    location: "src/amoeba/operations/status.py:179-194"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "OSError from the state move bypasses the CLI error boundary"
    location: "src/amoeba/cli/main.py:345"
  - id: F004
    severity: concern
    category: correctness
    summary: "The \"same store\" check compares row counts, so an in-place difference deletes the legacy copy"
    location: "src/amoeba/store/relocate.py:105"
  - id: F005
    severity: note
    category: architectural-decay
    summary: "`SECONDS_PER_DAY` is never used"
    location: "src/amoeba/operations/prune.py:40"
  - id: F006
    severity: note
    category: documentation-drift
    summary: "A comment says prune problems are still to come"
    location: "src/amoeba/operations/status_models.py:166"
  - id: F007
    severity: note
    category: correctness
    summary: "`dismiss_question` can write and then return `False`"
    location: "src/amoeba/store/question_closing.py#dismiss_question"
  - id: F008
    severity: note
    category: consistency-rot
    summary: "Path checks use `os.path` where the rules ask for `pathlib`"
    location: "src/amoeba/operations/pause_eligibility.py#_wrong_checkout"
  - id: F009
    severity: note
    category: correctness
    summary: "A run started in a subdirectory of its checkout counts as a wrong checkout"
    location: "src/amoeba/operations/pause_eligibility.py#_wrong_checkout"
  - id: F010
    severity: note
    category: performance-resource
    summary: "Pruning walks the whole logs and scratch trees on every hook call"
    location: "src/amoeba/operations/prune.py#_Pass._prune_logs"
  - id: F011
    severity: note
    category: test-debt
    summary: "The live walkthrough can raise an IndexError and accepts two outcomes"
    location: "tests/live/pause/test_lifecycle_walkthrough_live.py#test_step_4_an_earlier_pause_closes_as_the_run_moves_on"
  - id: F012
    severity: note
    category: type-contract-debt
    summary: "Test helpers and a `type: ignore` sit under strict pyright"
    location: "tests/operations/test_state_move.py#test_a_copy_error_leaves_the_legacy_store_untouched_and_the_next_call_moves_it"
---

# Review: code — slice 228

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 21 successful tool call(s) of 22 made; 423945 of 423945 diff characters reached the model

## Findings

### [CONCERN] A paused run with no pause time closes every open question

`fate_of_poll` maps a `PAUSED` poll with no `checkpoint.paused_at_text` to a `RunFate` whose `current_paused_at` is `None`. `sweep_run` then judges every row, because `row.key.paused_at != None` is always true (lines 142-144). `handle_pause` therefore closes this run's waiting rows and old claimed and answered rows as `run_moved_on`, even though the run is still paused. The status path makes the opposite choice: `question_sweep_scope._fate` returns `None` (leave open) for the same case (`src/amoeba/operations/question_sweep_scope.py:61`). The two sweeps disagree. `test_fate_of_poll_covers_every_outcome` does not cover a paused poll without a checkpoint. Fix: return `None` from `fate_of_poll` in that case, as `status` does, and add a test. Closures can be undone (`answer` reopens a closed row), which is why this is not a FAIL.

### [CONCERN] Closures made by `status` are lost if the call fails after the sweep

`sweep_scope` commits its closures at line 179. Then `_names` (line 185) can raise `ContextForgeError`, and `deps.prune` (line 189) can raise `StoreError`. Both run before `closed_now_entries` is built. The rows are closed and the call errors out. The next `status` no longer treats them as candidates, so `closed_now` never reports them. Design D12 says `closed_now` lets "the PM see each automatic closure once, in the status that made it." Fix: resolve `names` before the sweep, and build `closed_now` from the sweep result before any call that can fail. Add a test where `project_names` fails after a sweep closes a row.

### [CONCERN] OSError from the state move bypasses the CLI error boundary

`main` maps only `RequestDocumentError`, `AmoebaHomeError`, `ConfigError`, `ContextForgeError`, `SquadronError` and `StoreError`. Several file operations in the move are not wrapped:
- the move-lock open (`src/amoeba/operations/state_move.py:51`)
- `remove_store_files` (`state_move_store.py:45`)
- `moving.rename` (`state_move_store.py:110`)
- `shutil.move` in `_set_aside` (`state_move_store.py:123`)
- `_remove_if_empty` in `state_move_dirs.py`, which runs outside its `try`

A `PermissionError` from any of these escapes as a traceback with exit 1, not the documented exit 3 with an `error:` line. For `handle_pause` it also skips the calls-log line that D11 requires "whatever the outcome or error". Fix: wrap these as `StoreRelocateError`, as `copy_store` already does. Add a test with an unwritable state home.

### [CONCERN] The "same store" check compares row counts, so an in-place difference deletes the legacy copy

`compare_stores` runs `_check_copy`, which checks integrity, schema version, table names, per-table row counts, `MAX(answers.seq)` and the resume-log prefix. It never compares contents. `move_store` treats a "same" result as safe and deletes the legacy file (`state_move_store.py:131-139` and `:141`). A legacy store that differs only by in-place writes, such as a `resume_outcome` set on an existing answer or a question state change, counts as "same". The legacy copy is then deleted and the write is lost. D2 says the set-aside file "holds the only copy of answers an old process wrote after the move", so the check should catch content differences. A content comparison has to allow for the `resume_log` rewrite that `copy_store` makes. Fix: compare a content digest before deciding "same", and add a test that changes one row in place without changing the counts.

### [NOTE] `SECONDS_PER_DAY` is never used

A search finds only the definition. Remove it.

### [NOTE] A comment says prune problems are still to come

`StatusResult.file_problems` is described as "(and, later, prune problems)". `status()` already passes `pruned.problems` into `file_problems`. Remove "and, later".

### [NOTE] `dismiss_question` can write and then return `False`

The `ANSWERED` branch returns `closed and mark_not_delivered(...)`. If the close succeeds and the mark returns `False`, the close is already written, but the docstring promises "False, nothing written". The mark's guard is the same one checked earlier in the same transaction, so this cannot happen today. Make the mark's failure raise, so the transaction rolls back, and correct the docstring.

### [NOTE] Path checks use `os.path` where the rules ask for `pathlib`

`_wrong_checkout` uses `os.path.realpath`, while `status_placement.place_runs` uses `Path.resolve()` for the same purpose. The Python rules call for `pathlib` throughout. Use `Path.resolve()` in both places.

### [NOTE] A run started in a subdirectory of its checkout counts as a wrong checkout

The check is exact equality after resolution. A hook whose working directory is a subdirectory of the recorded checkout is skipped as `wrong_checkout`. D10 is about a second worktree, which is a different checkout, so the design may not intend this. Confirm the intent. An ancestor test (`directory.is_relative_to(started_in)`) would also accept a parent directory, so it is not a drop-in fix.

### [NOTE] Pruning walks the whole logs and scratch trees on every hook call

`handle_pause` runs on every pause and calls `prune`. That runs `os.walk` over `logs/`, with an `lstat` per file. `last_call` also reads whole day files. Nothing measures this cost. Measure it with a fixture of realistic size before the slice closes, or bound the walk.

### [NOTE] The live walkthrough can raise an IndexError and accepts two outcomes

`closed[0][3]` is evaluated while the expected value is built. An empty `closed` raises `IndexError` and hides the real assertion. Step 7 accepts either the resolved or the unresolved form of the same path, because it joins the two checks with `or`. Assert the row count first, then compare, and pick one path form.

### [NOTE] Test helpers and a `type: ignore` sit under strict pyright

The `failing_copy` wrapper takes `*arguments: object`, drops `**keywords`, and needs `# type: ignore[arg-type]`. `_listed` in `tests/operations/test_status_sweep.py` and `crash_after` in `tests/operations/state_move_support.py` have no return annotation. The latter also carries a `noqa: ANN201` for a rule the project does not enable. The Python rules run pyright strict over tests, so type the wrapper with the real `copy_store` signature and annotate the helpers.

### Run Digest

- Response length: 10095 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 23
- Tokens — prompt / cached / cache write / completion / reasoning: 3246978 / 2684471 / 562487 / 78938 / not computed
- Duration: 348.0 s
- Cost: $0.99 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
