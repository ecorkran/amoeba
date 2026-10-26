---
docType: review
layer: project
reviewType: code
slice: resolutions-and-resumption
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/127-slice.resolutions-and-resumption.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: e4ed5217fedd06dbcfca913d74ad1ce7b661eb0e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 173667
cachedTokens: 3232
cacheWriteTokens: 170433
completionTokens: 5796
durationSeconds: 47.9
costUsd: 0.81784
costBasis: provider
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Instructions starting with `-` may be parsed as an option by `sq`"
    location: "src/amoeba/runner/resolutions/argv.py#resume_argv"
  - id: F002
    severity: concern
    category: design
    summary: "`held_checkouts` and `ProjectView.held_checkouts` are now redundant with the holders mapping"
    location: "src/amoeba/runner/dispatch/hold.py:70-76"
  - id: F003
    severity: concern
    category: design
    summary: "Duplicated `_latest_run` helper"
    location: "src/amoeba/runner/resolutions/stage.py:60"
  - id: F004
    severity: concern
    category: testing
    summary: "No load-test coverage for the new per-tick stage and per-step reads"
    location: "tests/load/test_recovery_scale.py:221"
  - id: F005
    severity: note
    category: error-handling
    summary: "Poll-fault detail can render as the literal text \"None\""
    location: "src/amoeba/runner/resolutions/act.py#_poll_fault"
  - id: F006
    severity: note
    category: naming
    summary: "Local alias `Fault` in `observe_resume.py` shadows the name of `faults.Fault`"
    location: "src/amoeba/runner/observe_resume.py:30"
  - id: F007
    severity: note
    category: scope
    summary: "Unrelated comment and docstring trimming in `launch.py`"
    location: "src/amoeba/runner/launch.py:92-300"
  - id: F008
    severity: pass
    category: correctness
    summary: "Exception handling, journaling order, and transactional acknowledgment"
    location: "src/amoeba/store/blocking.py#acknowledge_resolution"
---

# Review: code — slice 127

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Instructions starting with `-` may be parsed as an option by `sq`

The PM's free-text instructions are appended as a separate argv element after `--instructions`. No shell is involved, so quoting is safe. If `sq` uses argparse or click, a value that starts with `-` (for example `- only the schema` or `--decision accept`) can be read as a flag instead of the option's value. `sq` would then exit with a usage error. `ResumeObserver` classifies exit code 2 as `REFUSED`, so a valid PM resolution would escalate as a refused resume with no hint of the real cause. The `--decision accept` case in `test_argv.py` only proves that the Runner builds a single element. The stub `sq` is hand-written and tolerates this input, so it doesn't show what the real `sq` does. Check how `sq` parses the value. If it can misparse, use the `--instructions=<text>` form or add a test against real `sq` parsing.

### [CONCERN] `held_checkouts` and `ProjectView.held_checkouts` are now redundant with the holders mapping

`held_checkouts()` is kept only as a wrapper over `checkout_holders()`, and production code no longer calls it. `build_dispatch_view` uses `checkout_holders` directly. `ProjectView` now carries both `held_checkouts` and `checkout_holders`. In `project_view.py`, `held_checkouts` is derived as `frozenset(dispatch.holders)`. Two fields hold the same information, so they can drift apart, which goes against the project's "one definition" and DRY rules. Drop the wrapper and the derived field, or derive one from the other in a single place. The tests in `test_hold.py` and `view_of` would then use the holders mapping.

### [CONCERN] Duplicated `_latest_run` helper

`_latest_run(entries)` is defined identically in `resolutions/stage.py` and `dispatch/build_view.py`. `classify.py` also inlines the same `next(... reversed ...)` expression. Define it once, for example next to `checkpoint_of` or in the journal models, and import it.

### [CONCERN] No load-test coverage for the new per-tick stage and per-step reads

The only load-tier change is a signature update. The tick now does extra work on every step each tick: `blocked_state_for(include_resolved=True)` per step in `_facts_for`, `resumed_from_pauses` (one journal read per unresolved resume), and `pending_resolutions` per project. The resume path also adds a subprocess spawn and an extra `sq runs wait` poll. The Python rules require a load test with latency or resource bounds for code on the network, concurrency, or environment paths. Add one that runs many steps with pending or in-flight resumes and asserts a bound on tick time and call count.

### [NOTE] Poll-fault detail can render as the literal text "None"

`PrepollDecision.detail` is `str | None`. `_poll_fault` interpolates it directly into the fault text. `WAIT` always sets it today, but the type allows `None`, so a future caller could produce "continuation of X: None". Consider making `detail` required on the `WAIT` path.

### [NOTE] Local alias `Fault` in `observe_resume.py` shadows the name of `faults.Fault`

`type Fault = Callable[[JournalEntry, str, str, TickFaults], ObservedRun]` is a callback type, not the `Fault` dataclass in `amoeba.runner.faults`. Rename it, for example to `RaiseFault`, to avoid confusion.

### [NOTE] Unrelated comment and docstring trimming in `launch.py`

Several comments and docstrings were shortened in places that are not part of this change: `stderr_confirms`, `TARGET_PARAM_KEY`, `PARAM_REISSUE_OF`, `LaunchTracker`, and `reap`. Some of the removed text recorded observed behavior, such as the Squadron version note. Keep the `spawn` extraction and restore the unrelated text, or move the trimming to a separate `style:` commit.

### [PASS] Exception handling, journaling order, and transactional acknowledgment

`acknowledge_resolution` takes the write lock before reading the flag and applies the effect in the same transaction, so a failed effect leaves the flag set. The new `except` clauses (`ValidationError`, `ValueError`) are narrow and each has a justifying comment. A resume is journaled before the spawn. A crash between the two is covered by `test_crash_resume.py` and ends as `no_claim_within_grace`, so the resume is never launched twice. Recovery maps a continuation's missing run to `Unknown` rather than `NotApplied`, so a resume can't be reissued as a fresh run.

### Run Digest

- Response length: 5312 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 173667 / 3232 / 170433 / 5796 / not computed
- Duration: 47.9 s
- Cost: $0.82 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
