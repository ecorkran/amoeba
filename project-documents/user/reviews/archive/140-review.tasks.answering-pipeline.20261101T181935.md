---
docType: review
layer: project
reviewType: tasks
slice: answering-pipeline
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/140-tasks.answering-pipeline.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: 74520585aac2b2a79b0516641c2141d7b39a38e0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 191459
cachedTokens: 93341
cacheWriteTokens: 98112
completionTokens: 4052
durationSeconds: 35.9
costUsd: 0.443154
costBasis: provider
runId: run-20261101-p56-29332206
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md"
  - id: F002
    severity: concern
    category: scope
    summary: "`read_check` adds a `reason` rejection rule the slice design does not specify"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:119"
  - id: F003
    severity: concern
    category: sequencing
    summary: "New live variable is bolted on in Task 9.4 and edits an earlier task's output"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:212-213"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 1.1 records into an artifact that does not exist until Task 1.2"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:50"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Granularity and implementation-detail steps exceed what the criteria need"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:67-76"
  - id: F006
    severity: note
    category: coverage
    summary: "\"Resolves from an installed wheel\" is only partly exercised"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:142-145"
  - id: F007
    severity: note
    category: sequencing
    summary: "Blocked work and commit cadence are handled correctly"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:191-231"
---

# Review: tasks — slice 140

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

Each criterion in the slice design traces to a task:
- Squadron issue and slice-plan entries: 1.1–1.3.
- `question.md` rendering, `prepare_scratch` refusals and parser malformed cases: 3.x and 4.x.
- Names-match test: 5.2.
- Wheel contents: 5.3.
- Probe failure paths against a stub `sq`: 6.x.
- `tests/live` exclusion and fail-with-variable-name: 7.x.
- Process contract and the dated `sq` observation: 8.1 and 9.5.
- Gated live criteria (files, no-files, check input, precedence, matching, SDK refusal, `--validate`): 9.1–9.4.

Task 10.1 closes the loop by checking each criterion against a task. There are no NFR statements, so no load-test or CI-gating task is needed.

### [CONCERN] `read_check` adds a `reason` rejection rule the slice design does not specify

Task 4.4 makes a check reply `malformed` when `reason` is absent or not a string. LLD D6's rejection list covers only `verdict`, so a reply with a valid `yes` or `no` but no `reason` would be rejected on a rule the design never states. The task admits the gap ("LLD D6 has no rule for `reason`") and resolves it itself. It can also turn an otherwise usable verdict into a problem that 144 must map to a decline. Either update D6 so the design and the task agree, or tolerate an absent `reason` and drop the extra rule and its test cases in 4.5.

### [CONCERN] New live variable is bolted on in Task 9.4 and edits an earlier task's output

Task 9.4 introduces `AMOEBA_LIVE_SDK_MODEL`, which fails at collection when unset, and tells the implementer to go back and edit Task 7.1's conftest and the section 8.1 contract text. This has two effects:
- 7.1's "fail naming the first missing one" behavior and 7.2's tests are defined for three variables, then silently change to four.
- Every live test fails at collection while Section 9 is blocked and the variable is unset.

Define the SDK variable once in 7.1, and in 7.2 and 8.1. Collection can then require it only for the SDK-refusal test, for example through a fixture used only by that test. Leaving it as a post-hoc edit invites drift.

### [CONCERN] Task 1.1 records into an artifact that does not exist until Task 1.2

Task 1.1 says to record the observation "in the Squadron issue (Task 1.2)", but the issue is filed in 1.2. Say that 1.1 keeps the observation in task notes and that 1.2 copies it into the issue body. Alternatively, merge 1.1 into 1.2 as its first step, which also removes a very small task.

### [CONCERN] Granularity and implementation-detail steps exceed what the criteria need

The file has about 28 tasks across 10 sections for one slice. Several can be trimmed:
- Task 2.2 tests that output file names are "distinct". That is a trivial constant check, and the real assertion, path resolution, is deferred to 5.2. Fold the resolver test into 5.2 and drop 2.2, or keep only the absent-YAML raise.
- Task 6.1 dictates internals the slice does not require: reusing `run_cf`, and an optional move to `runner/answering/probe.py`. That move conflicts with the design's component table, which extends `probes.py`.
- Tasks 1.3, 8.2 and 3.3's "split into scratch.py if >300 lines" are minor but add step noise.

Merge 2.1/2.2 into 5.2 and trim 6.1's prescriptions to "reuse the existing `sq` call helper".

### [NOTE] "Resolves from an installed wheel" is only partly exercised

The Technical Requirements say `answering_pipeline_path()` resolves to the file from an installed wheel. Task 5.3 asserts only that the built archive lists `amoeba/runner/answering/answering.yaml`. Listing the archive is an acceptable proxy, since `importlib.resources` resolves packaged files. Add a one-line note if full installed-resolution is intended.

### [NOTE] Blocked work and commit cadence are handled correctly

The Section 9 `BLOCKED:` lines name their dependencies and the Squadron issue. The unit-tested Sections 2–8 do not wait on Squadron. Commit markers follow each of Sections 1–9 and the final validation, so none are batched at the end. The referenced helpers `output_head`, `run_cf`, `SQ_EXECUTABLE`, `poll_run` and `mint_run_id` exist in the source tree. Task 7.1 should pass `mint_run_id` a `datetime`, since that is its signature.

### Run Digest

- Response length: 5257 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 191459 / 93341 / 98112 / 4052 / not computed
- Duration: 35.9 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
