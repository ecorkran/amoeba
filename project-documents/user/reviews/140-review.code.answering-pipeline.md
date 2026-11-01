---
docType: review
layer: project
reviewType: code
slice: answering-pipeline
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: PASS
verdictSource: resolved
sourceDocument: project-documents/user/slices/140-slice.answering-pipeline.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: de161e45c02fdf6dd356f33fc9d884757c48b307
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: type-contract-debt
    summary: "Reply-file parsing hand-rolled instead of using Pydantic at the external boundary"
    location: "src/amoeba/runner/answering/artifacts.py:72"
    resolution: fixed
  - id: F002
    severity: note
    category: error-handling-observability
    summary: "A crashed launch is reported as an ambiguous 'run not found' instead of naming the exit code"
    location: "tests/live_harness.py:87"
    resolution: fixed
  - id: F003
    severity: note
    category: architectural-decay
    summary: "Live-test launcher duplicates production's detached-subprocess isolation instead of reusing it"
    location: "tests/live_harness.py:56"
    resolution: fixed
---

## Summary

Reviewed the implementation of slice 140 (answering pipeline) at `de161e4`,
run after the slice merged to `main`. The `/code-review` skill flagged three
findings, none a correctness bug. All three were resolved directly:

- **F001.** `python.md` requires Pydantic at every external boundary (API
  input/output, file parsing, environment variables); `artifacts.py` parsed
  the two reply files with dataclasses and manual key-by-key checks instead.
  Rewrote both parsers as Pydantic models (`_AnswerReplyModel`,
  `_CheckReplyModel`) validated with `model_validate_json`, catching
  `ValidationError` to produce the same `ArtifactProblem` the hand-rolled
  version did — this keeps the module's stated contract ("never raise for bad
  file content") while removing the duplicated validation logic. A
  `BeforeValidator` reproduces the trim-and-lowercase matching the original
  gave `kind` and `verdict`; `cited`'s absence (vs. an empty list) is still
  distinguished and still malformed, matching the original's behavior
  exactly. All 75 existing tests in `tests/runner/answering/` passed
  unchanged after the rewrite — no test needed updating, which confirms the
  parsing contract did not move.

- **F002.** In `tests/live_harness.py`'s poll loop, if `sq` crashed before
  registering the run, the loop could exit on `process.poll() is not None`
  while `poll_run` still reported `NOT_FOUND`, so a live-test failure read as
  an ambiguous "run not found" instead of naming the crash. Now a dead
  process while the outcome is still "not yet" produces a `PollFailure`
  naming the argv and exit code.

- **F003.** The harness's `subprocess.Popen` call lacked `start_new_session`,
  unlike production's `spawn()` (`src/amoeba/runner/launch.py`), so a live
  test killed mid-run could leave the `sq` child in the test process's
  session instead of isolated the way production launches it. Full reuse of
  `spawn()` was not practical — it is built around the Runner's two-file,
  exclusive-create log convention and a `PopenFactory`, where the harness
  wants one combined tempfile read back into memory for the assertion. Added
  `start_new_session=True` directly instead, which is the actual isolation
  property the finding was about.

No findings touched the live tier's `BLOCKED:` gate (task file section 9):
Squadron still lacks the five D8 capabilities (confirmed again on `sq
0.24.12`), already filed as `ecorkran/squadron#284`, and that gate is
correctly left unchecked. That is expected, not a review finding.

## Verification

- `uv run pytest tests/runner/answering/ -q` — 75 passed.
- `uv run ruff format`, `uv run ruff check`, `uv run pyright` on both edited
  files — clean.
- Full non-live suite run separately to confirm no other regression.
