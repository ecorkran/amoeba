---
docType: review
layer: project
reviewType: code
slice: answering-run
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/144-slice.answering-run.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 5cac398801a67ef4f5447fd72bb6567c25d7deab
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
diffTruncated: false
turns: 6
promptTokens: 503899
cachedTokens: 198192
cacheWriteTokens: 305699
completionTokens: 3539
durationSeconds: 29.8
costUsd: 1.336525
costBasis: provider
squadronVersion: 0.24.16
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: performance-resource
    summary: "Scratch directory is left behind when `begin_answering` does not begin"
    location: "src/amoeba/runner/answering/launch.py:launch_answering"
    resolution: fixed
  - id: F002
    severity: concern
    category: correctness
    summary: "Declining from the launch path can raise if the PM answers in between"
    location: "src/amoeba/runner/answering/launch.py:_decline"
    resolution: no_change_needed
  - id: F003
    severity: concern
    category: correctness
    summary: "`_write_evidence` overwrites unconditionally with NULLs"
    location: "src/amoeba/store/questions.py:_write_evidence"
    resolution: fixed
  - id: F004
    severity: note
    category: consistency-rot
    summary: "The completion pass counts `sq_answer` entries as open"
    location: "src/amoeba/runner/lifecycle/completion.py:48"
    resolution: fixed
  - id: F005
    severity: note
    category: consistency-rot
    summary: "Verified: other journal readers are consistent with D3"
    location: "src/amoeba/runner/tick.py:274-279"
    resolution: no_change_needed
  - id: F006
    severity: pass
    category: other
    summary: "Crash safety, exception handling and config validation"
    location: "src/amoeba/runner/answering/finish.py"
    resolution: no_change_needed
---

# Review: code — slice 144

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Scratch directory is left behind when `begin_answering` does not begin

`prepare_launch` creates and fills the scratch directory (`scratch.mkdir()` plus `prepare_scratch`) before `begin_answering` runs. If `begin_answering` returns `SETTLED` or `BLOCK_RESOLVED` (the PM answered first), `launch_answering` returns `SKIPPED` and nothing removes the directory. Each lost race therefore leaves an orphaned directory under `answering/`. The tests for this case (`test_a_block_resolved_before_the_journal_starts_nothing`) only assert that no entry was journaled and no process was spawned. They don't check the directory. Remove it on the `SKIPPED` path. If the cleanup is deliberately left for a later slice, say so in a comment.

### [CONCERN] Declining from the launch path can raise if the PM answers in between

`_decline` calls `store.decline_question` on a record read earlier in the tick. If the PM's answer is acknowledged between that read and the decline, the record is no longer `pending`. `decline_question` then raises `InvalidTransitionError`, which `QuestionOperations` documents. That exception propagates out of the stage and escalates the whole project, even though the situation is a normal race. The `begin_answering` path handles the same race with `SETTLED`. `_decline` should handle it too, for example by re-reading the record or catching that specific error and returning `SKIPPED`.

### [CONCERN] `_write_evidence` overwrites unconditionally with NULLs

`UPDATE_QUESTION_EVIDENCE` sets all five columns on every call. A call with only `detail` therefore nulls `proposed_answer`, `cited_passages`, `check_verdict` and `check_reason`. The call in `submit_answer` with `detail=None` also nulls `decline_detail`. This is harmless today, because only the stranded-pass and launch-path declines pass `detail` alone and those records have no evidence yet. It is a trap for any later caller that settles a record already holding evidence. Either document the "replaces all five" contract on the method, or use `COALESCE` for fields the caller left unset.

### [NOTE] The completion pass counts `sq_answer` entries as open

`mark_done` for hand-completed slices builds `has_open_entry` from all unresolved entries. The slice makes `sq_answer` irrelevant to the "node is done" check in `SELECT_UNRESOLVED_ENTRY_FOR_NODE` (D4) and to `supervision_entries`. This pass still treats an in-flight answerer run as blocking. The effect is only a short delay until the answering entry resolves, so it is safe. It does leave two different rules for the same question. Consider filtering by kind here too, or add a comment.

### [NOTE] Verified: other journal readers are consistent with D3

`_run_entries` and `_in_flight_run_ids` already filter on `SQ_RUN`. The remaining readers (`build_view`, `resolutions/stage`, `run_to_resume`) were updated to use `supervision_entries`. `tests/runner/test_sq_answer_readers.py` covers each of them, which is good coverage.

### [PASS] Crash safety, exception handling and config validation

The ordering is sound: the record is settled first and idempotently, and the entry is resolved last. `begin_answering` journals the entry and moves the record in one `BEGIN IMMEDIATE` transaction. The only `try/except` blocks are narrow and specific: `OSError` in `_prepare_scratch` and `JSONDecodeError` in `_load_json`. Both carry justifying comments. The new settings have no silent defaults. The model aliases reuse `param_problem`, so a comma in an alias fails at load. The decline-reason maps are defined once, with a test that each map covers its whole vocabulary. Tests accompany each new module.

### Run Digest

- Response length: 4357 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 503899 / 198192 / 305699 / 3539 / not computed
- Duration: 29.8 s
- Cost: $1.34 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
