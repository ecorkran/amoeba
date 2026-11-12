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
reviewedSha: fb7b3c94d43cd9da936334ad48f144dab38167da
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
diffTruncated: false
effort: xhigh
turns: 11
promptTokens: 1916743
cachedTokens: 1368541
cacheWriteTokens: 548190
completionTokens: 66462
durationSeconds: 291.7
costUsd: 0.882652
costBasis: provider
runId: run-20261112-p6-b8c4559a
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Dismiss closes an answer whose resume is already in flight"
    location: "src/amoeba/store/question_closing.py:93"
  - id: F002
    severity: concern
    category: correctness
    summary: "`resume()` discards whether its outcome was recorded"
    location: "src/amoeba/operations/resume.py:101"
  - id: F003
    severity: concern
    category: performance-resource
    summary: "Status rescans the whole calls log for each missed-hook run"
    location: "src/amoeba/operations/status_calls.py:28"
  - id: F004
    severity: concern
    category: error-handling-observability
    summary: "A housekeeping failure after a resume turns the call into an exit-3 error"
    location: "src/amoeba/operations/handle_pause.py:67"
  - id: F005
    severity: note
    category: error-handling-observability
    summary: "`append_call` ignores the byte count from `os.write`"
    location: "src/amoeba/operations/calls_log.py:104"
  - id: F006
    severity: note
    category: other
    summary: "Hook-driven closures are not reported by `status`"
    location: "src/amoeba/operations/status.py:196"
  - id: F007
    severity: note
    category: test-debt
    summary: "Concurrency test hides worker-thread failures"
    location: "tests/operations/test_set_up_concurrent.py#_race"
---

# Review: code — slice 228

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 9 successful tool call(s) of 10 made; 432827 of 432827 diff characters reached the model

## Findings

### [CONCERN] Dismiss closes an answer whose resume is already in flight

`dismiss_question`'s ANSWERED branch accepts any answer whose `resume_outcome` is null or refused. It never checks `resume_started_at`. `_attempt` in `resume.py` (lines 131-134) sets that column before the spawn, while the outcome is still null. A dismissal in that window closes the question and marks the answer `not_delivered` with detail "dismissed". The resume then spawns and the run receives the answer. When `resume()` tries to record the outcome, its CAS (`resume_outcome IS NULL OR refused`) no longer matches, so the write is dropped (see the next finding). The store then says closed and not delivered, the run has the answer, and the PM was told "dismissed". The sweep handles this window through `_mark_undelivered` in `question_sweep.py` (`_newest_sign` includes `resume_started_at`), but the operator path does not. Refuse the dismissal while `resume_started_at` is within the resume bound, or make the check part of the same compare-and-set.

### [CONCERN] `resume()` discards whether its outcome was recorded

`record_resume` returns `cursor.rowcount == 1`, but `resume()` ignores that value and returns the attempted result as if it were stored. When the CAS loses to a sweep or a dismissal, the caller gets an outcome the store never kept. The `ALREADY_FINAL` branch (lines 131-134) has a related problem. It returns `NOT_DELIVERED` with the text "resumed, by another call" when a concurrent resume has already recorded `RESUMED`, so `answer` or `handle_pause` reports `not_delivered` for an answer the store holds as `resumed`. Fix: when `record_resume` returns False, re-read the stored outcome and return that. In the `ALREADY_FINAL` case, return the stored outcome too.

### [CONCERN] Status rescans the whole calls log for each missed-hook run

`attach_last_calls` calls `last_call` once per run in a missed-hook class. `last_call` (`calls_log.py:122`) lists every day file. `_newest_for_run` (`calls_log.py:150-152`) reads each file whole and validates lines with `CallEntry.model_validate_json` from the end until it finds the run. A run with no entries, which is the case "the hook never reached" describes, validates every line in every retained day. Each `status` call therefore costs roughly (missed runs × retained lines) pydantic parses, and the retained window is `prune_after_days`. Fix: read the log once per `status` call, build a run_id → newest-entry map, and attach from the map.

### [CONCERN] A housekeeping failure after a resume turns the call into an exit-3 error

`handle_pause` runs `deps.prune` after `_handle_polled` may already have resumed the run and recorded its outcome. `prune` can raise `StoreError` from its `store.read()`, as its docstring says. That exception escapes `handle_pause`, so `_run_handle_pause` never prints the result and `main` exits 3, even though the resume succeeded and was recorded. `status.py:191` has the same problem: a read failure in housekeeping fails the whole status report. The slice already holds to "an auxiliary failure must not change the reported result" for the calls log (`calls_log.append_call`). Prune is the same kind of step, so it should report its failure in `PruneReport.problems` (or the call's detail) rather than raising.

### [NOTE] `append_call` ignores the byte count from `os.write`

`os.write` can return fewer bytes than requested without raising, and the return value is discarded even though the docstring promises the line goes out in one write. A short write leaves a truncated line with no newline, and the next append is glued onto it, so `last_call` skips both entries. This is rare on local disks. Looping over the remaining bytes would make it exact.

### [NOTE] Hook-driven closures are not reported by `status`

`closed_now` comes only from this call's own sweep (`status_closed.py:31`). A question that a later hook call closes is written only into that hook call's calls-log detail. `status` reads that detail only for missed-hook runs (`status_calls.py` `MISSED_HOOK_CLASSES`), so the closure is shown nowhere. Not-delivered answers still appear in `decisions`. This may be intended, since the run has moved on and nothing needs action. Check it against D12, which says "the PM sees each automatic closure once", because that is only true for closures made during a status call.

### [NOTE] Concurrency test hides worker-thread failures

`(outcome,) = outcomes` fails with an opaque `ValueError` when a worker thread raised. `threading` only prints the thread's exception and does not propagate it, so the test does not say what went wrong. Capture each thread's exception and re-raise it in the main thread.

### Run Digest

- Response length: 7010 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 1916743 / 1368541 / 548190 / 66462 / not computed
- Duration: 291.7 s
- Cost: $0.88 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
