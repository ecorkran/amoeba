---
docType: review
layer: project
reviewType: code
slice: program-dependencies
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/227-slice.program-dependencies.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: 2f2fb83e3c62c230bf70ef5ce4320837142d7e46
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 30
diffTruncated: false
effort: xhigh
turns: 31
promptTokens: 2246751
cachedTokens: 1911666
cacheWriteTokens: 335063
completionTokens: 59525
durationSeconds: 264.4
costUsd: 0.587919
costBasis: provider
runId: run-20261114-p6-6b20c1ce
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: test-debt
    summary: "Load test cannot detect a `cf` call moved under the write lock"
    location: "tests/load/test_report_release_load.py:34-37"
  - id: F002
    severity: note
    category: architectural-decay
    summary: "`sql.py` is past the size guideline and this slice grew it"
    location: "src/amoeba/store/sql.py:166-205"
  - id: F003
    severity: note
    category: type-contract-debt
    summary: "`ReleaseReport.from_release` returns `ReleaseReport` rather than `Self`"
    location: "src/amoeba/operations/report_release_models.py#ReleaseReport.from_release"
  - id: F004
    severity: note
    category: security-hygiene
    summary: "No length or count caps on report text"
    location: "src/amoeba/operations/report_release_models.py#ReportReleaseRequest"
  - id: F005
    severity: note
    category: security-hygiene
    summary: "Cross-repo text reaches another agent unmarked"
    location: "src/amoeba/cli/render/releases.py#render_changes"
  - id: F006
    severity: note
    category: performance-resource
    summary: "`changes` does more work per call than it needs"
    location: "src/amoeba/operations/changes.py#changes"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "Duplicated logic in the release source and tests"
    location: "src/amoeba/operations/report_release.py#_apply"
  - id: F008
    severity: pass
    category: performance-resource
    summary: "Members are resolved before any transaction opens"
    location: "src/amoeba/operations/report_release.py#report_release"
  - id: F009
    severity: pass
    category: correctness
    summary: "Timestamp comparisons in the release queries order correctly"
    location: "src/amoeba/store/sql.py:198"
  - id: F010
    severity: pass
    category: documentation-drift
    summary: "Contract docs and rule blocks match the code"
    location: "docs/cli-contract.md:419"
---

# Review: code — slice 227

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 29 successful tool call(s) of 30 made; 174066 of 174066 diff characters reached the model

## Findings

### [CONCERN] Load test cannot detect a `cf` call moved under the write lock

The design's central concurrency claim is that no `cf` subprocess runs while the write lock is held. The `report_release` and `changes` docstrings both state it. The load test does not exercise it. `release_deps` wires in `FakeCf` (tests/operations/status_support.py:125-146), an in-process callable that returns immediately. A regression that moved `resolve_release_member` inside `store.write()` would add microseconds, and these tests would stay green.

The bounds are also loose. `LATENCY_BOUND_SECONDS` equals the 5-second busy timeout (line 34), so a write that takes almost five seconds passes. `BURST_BUDGET_SECONDS = 30.0` (line 37) leaves roughly an order of magnitude of headroom over 200 writes.

Suggested fix: give the test's `cf` double a realistic per-call delay (for example 50 ms) during the burst, then assert the burst budget against it. Tighten the per-write bound from a measured baseline rather than the busy timeout. I have not run the load test; this finding comes from reading it.

### [NOTE] `sql.py` is past the size guideline and this slice grew it

The file is 484 lines against a ~300-line guideline. The new release block adds about 40 lines. The file was already over before this slice, so this is not a blocker. A later split of the per-table statements into their own modules would keep it from growing further.

### [NOTE] `ReleaseReport.from_release` returns `ReleaseReport` rather than `Self`

The project rule asks for `Self` on factory return types. This module already imports `Self` (`from typing import Final, Self`) and uses it in `_mode_rules`, so the factory is inconsistent with its own file.

### [NOTE] No length or count caps on report text

`NonBlank` (src/amoeba/config/user_config.py:35) sets only `strip_whitespace` and `min_length=1`. `changed`, each `touched` item, and `version` have no maximum, and neither does the number of `touched` items. The text is stored and returned verbatim in `changes -j` to every consumer. Only the text rendering is cut to width. The design sets no cap either. A named constant and a Pydantic max length would bound it at the boundary.

### [NOTE] Cross-repo text reaches another agent unmarked

A `changed` string written by one repo's agent is printed into another repo's agent context. The consumer block says to judge each report against the slice, but nothing marks the text as data from another repo rather than instructions. This follows from the feature's design, so it is not a defect. The rule block or the rendered output could label the text as quoted report content.

### [NOTE] `changes` does more work per call than it needs

Each call makes two `cf` subprocess calls: `deps.project_names()` and `resolve_release_member` through `project_of`. It also runs one `visible_releases` query per provider. `SELECT_PAIRS_CONSUMED_BY` (src/amoeba/store/sql.py:144) filters on `consumer_id`, which is not the leading column of the `(provider_id, consumer_id)` primary key, so it scans `dependency_pairs`. All of this is bounded by member count and fine at current scale. It becomes worth changing if a repo gains many providers.

### [NOTE] Duplicated logic in the release source and tests

- `_rejected` is written twice, in `changes.py` and `report_release.py`, with the same shape.
- `_apply` repeats `_required(request.changed, ...)` and `_required(request.touched, ...)` in three branches.
- `render_report_release` builds the commit and version line with a nested tuple expression that duplicates `_entry`.
- Test fixtures repeat the same `insert_member(...)` boilerplate across at least five support files: `tests/store/release_support.py`, `tests/operations/release_support.py`, `tests/program/flow_support.py`, `tests/store/test_pairs_consumed_by.py` and `tests/operations/test_changes.py`.

### [PASS] Members are resolved before any transaction opens

I checked the code path. `report_release` calls `resolve_release_member` before `store.write()`. `resolve_member` (src/amoeba/operations/members.py:50-57) calls `project_of` before its own `store.read()`. `changes` resolves the names and the member before `store.read()`. No subprocess runs inside a transaction. The load test does not check this (see the CONCERN above).

### [PASS] Timestamp comparisons in the release queries order correctly

`encode_timestamp` writes UTC `isoformat()` text. Microseconds appear only when non-zero, and `+` sorts before `.` and before any digit. So `reported_at >=` and `versioned_at >=` on the stored text order the same way as the underlying datetimes. The `since` value passes through the same encoder via `parse_since`.

### [PASS] Contract docs and rule blocks match the code

I checked the `report-release` and `changes` sections against the code. The mode table matches `_plan`. The `not_reported` and `not_a_member` details match the operation. The warning codes match `_warnings`. The exit codes match `is_rejected`. The rule-block flags are checked against the parser by `tests/test_program_rules_doc.py`, and that check matches the parser. The design's "no deferral" rule is met in the new code. The one retained-data decision, that removed members' rows are kept, is stated in the design (`227-slice.program-dependencies.md`, end state), so it is not a deferral.

### Run Digest

- Response length: 9272 chars
- Response is newline-free: no
- Tool calls made: 30
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 31
- Tokens — prompt / cached / cache write / completion / reasoning: 2246751 / 1911666 / 335063 / 59525 / not computed
- Duration: 264.4 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
