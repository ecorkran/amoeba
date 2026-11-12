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
reviewedSha: 4056da1f50674170e4b0d233adfd93c4005bfe55
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
diffTruncated: false
effort: xhigh
turns: 14
promptTokens: 1593806
cachedTokens: 1034107
cacheWriteTokens: 559689
completionTokens: 77853
durationSeconds: 338.9
costUsd: 0.907486
costBasis: provider
runId: run-20261112-p6-b8c4559a
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`dismiss` is refused for a stale in-flight resume, and nothing else closes it"
    location: "src/amoeba/store/question_closing.py:101-102"
  - id: F002
    severity: concern
    category: correctness
    summary: "A second resume of the same answer can spawn while the first is running"
    location: "src/amoeba/operations/resume.py:139"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "Error translation in the state move does not log"
    location: "src/amoeba/operations/state_move.py:102"
  - id: F004
    severity: concern
    category: correctness
    summary: "The legacy store is deleted after its lock is released"
    location: "src/amoeba/operations/state_move_store.py#move_store"
  - id: F005
    severity: concern
    category: architectural-decay
    summary: "The \"not final\" rule and the \"where the run is\" mapping are each written twice"
    location: "src/amoeba/store/question_closing.py#dismiss_question"
  - id: F006
    severity: concern
    category: type-contract-debt
    summary: "Two test helpers lack return type annotations"
    location: "tests/operations/state_move_support.py:29"
  - id: F007
    severity: note
    category: other
    summary: "The set-aside legacy store has no recovery path"
    location: "src/amoeba/operations/state_move_store.py#_set_aside"
  - id: F008
    severity: note
    category: correctness
    summary: "Sidecar files are removed after the main file"
    location: "src/amoeba/operations/state_move_store.py#remove_store_files"
  - id: F009
    severity: note
    category: performance-resource
    summary: "The calls-log scan validates every line"
    location: "src/amoeba/operations/calls_log.py:174"
  - id: F010
    severity: note
    category: architectural-decay
    summary: "`store/sql.py` is 405 lines"
    location: "src/amoeba/store/sql.py"
---

# Review: code — slice 228

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 13 successful tool call(s) of 13 made; 440609 of 440609 diff characters reached the model

## Findings

### [CONCERN] `dismiss` is refused for a stale in-flight resume, and nothing else closes it

`dismiss_question` treats any answer with a NULL outcome and a non-null `resume_started_at` as in flight, with no time limit. `_mark_undelivered` in `question_sweep.py` reads the same field against `resume_bound_seconds`, so the two disagree about the same row. If the resume process dies after `mark_resume_started`, for example when the hook is killed during the resume wait, the field stays set. The sweep never judges a row at the run's current pause (`question_sweep.py:146-147`, and `question_sweep_scope.py#_fate` returns None for it), so for a run still paused there nothing expires the row. `dismiss` then reports "dismiss again once it has ended" (`dismiss.py:111`), which never happens. `set_up` removal is also blocked, because `member_open_questions` counts the row. The only exit is a manual `amoeba handle_pause`, which re-runs the resume (`pause_existing.py:66-71`). Neither message mentions it.

Fix: pass the resume bound into `dismiss_question`, so a stale `resume_started_at` counts as not in flight. Name `handle_pause` in the message.

### [CONCERN] A second resume of the same answer can spawn while the first is running

`mark_resume_started` (`store/answers.py`) only checks that the outcome is not final. It does not check whether a resume started recently, and nothing else reads `resume_started_at` as a guard. Two concurrent `handle_pause` calls, or a `handle_pause` racing an `amoeba answer`, can both pass the first poll while the run is still paused, and both spawn `sq run --resume`. The loser's REFUSED write is non-final, so `dismiss_question` sees no in-flight resume and can close the question and mark the answer `not_delivered` while the winner's resume is still running. The winner's later `record_resume` then returns False, and `resume()` reports `not_delivered` for an answer that was delivered. The window is narrow, but the outcome it writes is wrong when it is hit.

Fix: refuse to spawn when `resume_started_at` is within the resume bound and the outcome is NULL, using the same bound as the sweep. Keep stale starts retryable, which ties this to the previous finding.

### [CONCERN] Error translation in the state move does not log

`prepare_state_home` catches `OSError` and re-raises `StoreRelocateError` without `logger.exception`. `_move_lock` (line 56) converts `BlockingIOError` to `StoreBusyError` without logging either. The project rule is to re-raise after `logger.exception`, or to handle a specific exception with a justifying comment. `move_directories` in `state_move_dirs.py` does log before it raises, so the two modules are inconsistent. `state_move.py` has no logger at all.

### [CONCERN] The legacy store is deleted after its lock is released

`move_store` copies and verifies the legacy store under `_legacy_lock`, releases the lock, and then calls `remove_store_files(old)`. A write from an older amoeba binary that lands in that gap is lost, because the copy was taken earlier. The docstring says the delete happens after release but does not say why. The likelihood is low, since it needs an old process writing during the one-time move. Either delete inside the locked block, or document why the window is acceptable.

### [CONCERN] The "not final" rule and the "where the run is" mapping are each written twice

The rule "this answer can still be delivered" appears in several places: the Python check in `dismiss_question` (`not in (None, REFUSED)` plus the in-flight test), the same tuple in `question_sweep.py:224` (`_mark_undelivered`), and the SQL in `sql.py` (`_OPEN_QUESTION_CLAUSE`, `MARK_RESUME_STARTED`, `MARK_NOT_DELIVERED`). Separately, `question_sweep.fate_of_poll` (from `sq runs wait`) and `question_sweep_scope._fate` (from `sq runs list`) each map a run's state to a `RunFate`, so the two can drift. `dismiss_question` also puts domain policy (which answer states may be dismissed) in the persistence layer.

Fix: one named predicate for "not delivered yet" used by the Python callers, and one mapping from run state to fate.

### [CONCERN] Two test helpers lack return type annotations

`crash_after` has no return annotation, and `# noqa: ANN201` suppresses the lint rule instead of fixing the signature. It should return `Callable[[MoveStep], None]`. `_listed` in `tests/operations/test_status_sweep.py:60` is missing `-> ListedRun`. Strict pyright covers tests, and the project rule is to type-hint all function signatures.

### [NOTE] The set-aside legacy store has no recovery path

When the legacy and state stores both exist and differ, the legacy store is moved to `amoeba.sqlite3.legacy-<stamp>`. A test pins that it is never pruned, and one stderr line names it. Nothing in amoeba reads it or reconciles its answers with the active store, so recovering PM answers means hand-editing SQLite. Under the "every state has an exit" rule, document a manual procedure, or state that the set-aside is archive-only.

### [NOTE] Sidecar files are removed after the main file

`remove_store_files` and `_set_aside` delete or move the main file before `-wal` and `-shm`. A crash between steps leaves a WAL with no database beside it, and a later database created at that path could pick up the stale WAL on open. Removing the sidecars first avoids this.

### [NOTE] The calls-log scan validates every line

`_newest_per_run` validates each line as a `CallEntry` before checking the run id, and it reads each whole day file. `status` can scan up to `prune_after_days` (default 30) of files, and a missed-hook run with no entries reads all of them. A cheap run-id check before validation would cut that cost. Measure before changing it.

### [NOTE] `store/sql.py` is 405 lines

This is over the ~300-line guideline. It is mostly constants, so the cost is navigation. Splitting by table (members and pairs, questions, answers) would match the other store modules. Doing so also means updating `test_members_queried_in_one_place`, which scans `vars(sql)`.

### Run Digest

- Response length: 8374 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 1593806 / 1034107 / 559689 / 77853 / not computed
- Duration: 338.9 s
- Cost: $0.91 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
