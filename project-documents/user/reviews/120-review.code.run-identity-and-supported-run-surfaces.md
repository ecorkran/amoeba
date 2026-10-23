---
docType: review
layer: project
reviewType: code
slice: run-identity-and-supported-run-surfaces
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/120-slice.run-identity-and-supported-run-surfaces.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: de85034ca5acb475cfd425c8df3b373e7d0bc97d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 235703
cachedTokens: 16064
cacheWriteTokens: 219635
completionTokens: 4646
durationSeconds: 41.9
costUsd: 0.934474
costBasis: provider
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: performance
    summary: "Prune spawns one `sq` subprocess per owned run, serially, with no bound"
    location: "src/amoeba/cli/prune.py:150-165"
  - id: F002
    severity: concern
    category: design
    summary: "The literal `\"paused\"` is defined in several places, so `PAUSED_STATUS` can drift from `RunOutcome.PAUSED`"
    location: "src/amoeba/process/run_pruning.py:36"
  - id: F003
    severity: concern
    category: correctness
    summary: "Recovery blocks start-up with synchronous sleeps, and `issued_at` is assumed timezone-aware"
    location: "src/amoeba/process/observers/sq_run_id.py:100-112"
  - id: F004
    severity: note
    category: structure
    summary: "`SQ_EXECUTABLE` moved into `sq_outcome.py`, and `version_label.py` re-exports it by import"
    location: "src/amoeba/process/version_label.py:15"
  - id: F005
    severity: note
    category: testing
    summary: "Test helper uses `object`-typed sentinels with runtime asserts"
    location: "tests/process/test_prune_selection.py:20-45"
  - id: F006
    severity: note
    category: testing
    summary: "The help-text test depends on argparse formatting"
    location: "tests/test_settings_flags.py:68"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Exception handling in the outcome reader"
    location: "src/amoeba/process/sq_outcome.py:133-175"
  - id: F008
    severity: pass
    category: testing
    summary: "Test coverage matches the change"
    location: "tests/test_observer_sq_outcome.py"
---

# Review: code — slice 120

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Prune spawns one `sq` subprocess per owned run, serially, with no bound

`_select` calls `_poll_owned(sorted(owned), ...)`. `owned` holds every run id any project's journal ever adopted or completed, so it grows with history and includes runs of nodes that are already `done`. Each id costs one `sq runs wait` subprocess with a `sq_timeout_seconds` timeout (10 s by default). A hung `sq` therefore makes a preview take N × 10 s. With `--yes`, `_is_removed` polls every candidate again. The old code read the directory once.

Consider polling only the ids that could be candidates. Ids in `held` are never candidates, so they need no poll for selection, though they are still counted in `kept`. Alternatively, document the cost and cap it.

### [CONCERN] The literal `"paused"` is defined in several places, so `PAUSED_STATUS` can drift from `RunOutcome.PAUSED`

The project rule is to define comparison values once. `run_pruning.py` compares `document.outcome is RunOutcome.PAUSED` (the enum) and `document.status != PAUSED_STATUS` (a separate string constant). `STATUS_PAUSED` in `tests/contract/standin.py` is a third copy. If Squadron's status vocabulary and the outcome enum diverge, only one of these will notice. Derive `PAUSED_STATUS` from `RunOutcome.PAUSED.value`, or state in a comment that the two are intentionally independent.

### [CONCERN] Recovery blocks start-up with synchronous sleeps, and `issued_at` is assumed timezone-aware

`_not_found` calls `self._sleep(min(remaining, grace))` inside `observe`, once per in-grace entry. The load test shows the total is bounded by one grace period, because the deadlines are absolute. That bound only holds if recovery runs before the event loop and before any async code; the diff doesn't show the call site, so I couldn't confirm it.

`deadline - self._now()` also raises `TypeError` if a stored `issued_at` is naive, because `now` is built with `datetime.now(UTC)`. The new tests only cover aware values. Either guard the naive case (return `Unknown`, as `run_pruning` does for `updated_at`) or confirm in the store model that `issued_at` is always aware.

### [NOTE] `SQ_EXECUTABLE` moved into `sq_outcome.py`, and `version_label.py` re-exports it by import

Defining it once is good. `tests/test_version_label.py` still imports `SQ_EXECUTABLE` from `version_label`, so it works only because of that import. Pyright strict may flag the implicit re-export. Import it from `sq_outcome` in the test, or add it to `__all__`.

### [NOTE] Test helper uses `object`-typed sentinels with runtime asserts

`_document(paused_at: object = _DEFAULT, updated_at: object = _DEFAULT)` relies on `assert isinstance` to narrow the types. It works, but `datetime | None | _Unset` would let the type checker do that job.

### [NOTE] The help-text test depends on argparse formatting

The test asserts the exact string `"--sq-runs-dir PATH Legacy matching only"` after whitespace normalisation. Changing the wrapped help wording or the metavar breaks it without any behaviour change. Assert on the parser action's `help` attribute instead.

### [PASS] Exception handling in the outcome reader

Each `except` names a specific type (`FileNotFoundError`, `TimeoutExpired`, `OSError`, `JSONDecodeError`, `ValidationError`) and carries an inline justification. Each returns a `PollFailure` that names the run. `poll_run` also rejects a document whose outcome disagrees with the exit code, and one whose `run_id` is not the requested id. No blind `except` is used, so this fits the BLE rule and the project's exception policy.

### [PASS] Test coverage matches the change

Every outcome and every `PollFailure` path has a test, as do the grace-period branches and the dispatcher routing. The load tier asserts exact poll and scan counts, and a guard test checks that pruning no longer imports the run-file parser. Legacy rows are written through the store's own insert statement rather than hand-built.

### Run Digest

- Response length: 4615 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 235703 / 16064 / 219635 / 4646 / not computed
- Duration: 41.9 s
- Cost: $0.93 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Disposition (20261022)

- **F001 prune cost:** rejected. The slice design (D6) accepts one poll per owned id for a manual, rare command and names "skip held ids" as the first remedy, recorded in the 120 slice plan's Future Work (item 6). Skipping held ids would also change what the `kept` count means. A hung `sq` costs at most `sq_timeout_seconds` per id, and each is named on stderr.
- **F002 duplicate `"paused"`:** fixed. `PAUSED_STATUS` is now `RunOutcome.PAUSED.value`, and the contract stand-in's `STATUS_*` constants derive from `RunOutcome` too.
- **F003 sleeps and naive `issued_at`:** the sleep is rejected as a defect. Recovery runs synchronously in `ResidentProcess.run` before the loop (`host.py`, `recover_every_project`), with no event loop, and the bound is asserted in the load tier. The naive `issued_at` is fixed: such an entry now escalates (`Unknown`), with a test.
- **F004 re-export:** fixed. `tests/test_version_label.py` imports `SQ_EXECUTABLE` from `sq_outcome`.
- **F005 sentinel typing:** rejected. It is confined to one test helper and the asserts narrow the types at the call.
- **F006 help-text test:** fixed. It no longer depends on the metavar or exact wrapping, only on the legacy note appearing in the `--sq-runs-dir` entry.
