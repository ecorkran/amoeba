---
docType: review
layer: project
reviewType: code
slice: run-dispatch-and-outcome-ingestion
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/125-slice.run-dispatch-and-outcome-ingestion.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: 4db47c6b0c172a304ea7c3c173f8df46eefae7a7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 214199
cachedTokens: 3232
cacheWriteTokens: 210965
completionTokens: 5332
durationSeconds: 47.1
costUsd: 0.995648
costBasis: provider
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: design-dry
    summary: "Wire-level key strings are spelled in more than one place"
    location: "src/amoeba/runner/dispatch/pointer.py#PARAM_PROJECT"
  - id: F002
    severity: concern
    category: performance
    summary: "Dispatch view reads the whole project journal every tick, with no load test"
    location: "src/amoeba/runner/dispatch/build_view.py#build_dispatch_view"
  - id: F003
    severity: concern
    category: correctness
    summary: "A review file that resolves through a symlink gets a different ledger key than detection"
    location: "src/amoeba/process/review_scan.py#detection_key"
  - id: F004
    severity: concern
    category: error-handling
    summary: "A confirmed pointer write with no slice node raises inside the tick"
    location: "src/amoeba/runner/dispatch/pointer_apply.py#_confirm"
  - id: F005
    severity: note
    category: style
    summary: "Magic priority integers in the planner"
    location: "src/amoeba/runner/dispatch/planner.py#_PRIORITY"
  - id: F006
    severity: note
    category: correctness
    summary: "`watched_runs` accepts a `bool` as the slice index"
    location: "src/amoeba/runner/dispatch/pointer_watch.py#watched_runs"
  - id: F007
    severity: pass
    category: design
    summary: "Crash-safe ingest, store-owned routing flag, and test coverage"
    location: "src/amoeba/runner/ingest/record.py#ingest"
---

# Review: code — slice 125

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Wire-level key strings are spelled in more than one place

The project rule says a comparison or lookup value is defined once. These repeat:
- `PARAM_PROJECT = "project"` and `PARAM_EXPECTED = "expected"` are defined in `dispatch/pointer.py`. They are also defined in `process/observers/cf_readback.py`, and `store/journal_models.py` spells both as literals in `REQUIRED_PARAMETER_KEYS`. `pointer_watch.py` imports `PARAM_PROJECT` from `pointer.py`, so three definition sites exist.
- `_PROJECT_FILE_SLICE = "fileSlice"` in `dispatch/pointer_watch.py` duplicates `CF_FIELD_FILE_SLICE` in `cf_get.py`.
- `PAYLOAD_REASON_TEXT = "reason"` in `ingest/record.py` duplicates `PAYLOAD_REASON` in `ingest/outcome.py`.
- `pointer_watch.watch_pointers` builds its listing with literal `"node_id"`, `"run_id"`, `"worktree_id"` and `"observed"` keys, while the payload key `PAYLOAD_RUNS` is a constant.

If one copy changes, the others drift silently. Define each once, in the store or `cf_get` constants, and import it.

### [CONCERN] Dispatch view reads the whole project journal every tick, with no load test

Each tick calls `store.journal_entries(project_id)` for the full history, then `held_checkouts` scans all of it. It also calls `journal_entries(..., node_id=...)` for every current step. Migration 011 adds a partial index specifically so cost follows unrouted work rather than history. This path takes the opposite approach, so its cost grows with the journal.

The Python rules require a load test, with bounds on latency or resource use, for network and concurrency paths. The only change under `tests/load/` is the added `version_label` argument. Either read only unresolved entries plus the latest `sq_run` per node (a store query), or add a load test with a large journal that asserts the tick stays inside its deadline.

### [CONCERN] A review file that resolves through a symlink gets a different ledger key than detection

`detection_key` matches `directory == file.parent` as raw `Path`s. If the checkout from CF and the watch's `reviews_dir` differ only by a symlink or normalization, it returns `None`. `_recorded` in `ingest/reviews.py` then falls back to `file.resolve()`. That produces a path detection will not use, so detection can later ingest the Runner's own review as a new external one, the duplicate the key sharing is meant to prevent.

Compare resolved paths, or log a warning when a review lies outside every watch.

### [CONCERN] A confirmed pointer write with no slice node raises inside the tick

`_confirm` raises `ValueError` when the step has no parent slice node. This is reached from `apply_answer`, which `PointerStage._settle` calls for every open pointer write each tick. The entry stays unresolved, so the same exception recurs on every tick. Convert it to a node-scoped human block plus resolving the entry `failed`, the way `_fail` does. The same applies to `PointerStage._answer`, which raises `ValueError` on a state it treats as unreachable.

### [NOTE] Magic priority integers in the planner

`_PRIORITY` maps states to bare `0` and `1`. Named constants or an `IntEnum` would be easier to read and match the project's no-scattered-values rule. The `_action` match also uses a `case _` fallthrough that treats every non-POINTED, non-REISSUE state as `NEEDS_POINTER`. This is safe today only because `plan` pre-filters on `_PRIORITY`.

### [NOTE] `watched_runs` accepts a `bool` as the slice index

`isinstance(index, int)` admits `True`/`False`. `cf_readback._as_index` and `checkout._is_int` both exclude `bool` for this reason. Reuse one shared helper.

### [PASS] Crash-safe ingest, store-owned routing flag, and test coverage

Ingest blocks first, then records every review and resolves the entry in one `record_runner_report` transaction with deterministic verdict ids. Repeating it after a kill is a no-op, and the crash tests cover this. The store sets the `awaits_routing` flag inside `RESOLVE_JOURNAL_ENTRY` (issuer resolutions of `sq_run` only) and the routing decision clears it in its own transaction, so no caller can forget or forge it. Tests use real captures and cover each branch.

### Run Digest

- Response length: 5164 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 214199 / 3232 / 210965 / 5332 / not computed
- Duration: 47.1 s
- Cost: $1.00 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
