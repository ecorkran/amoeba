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
reviewedSha: 94cebe8628ae77405de726112c60c1fac46b2622
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 191199
cachedTokens: 95670
cacheWriteTokens: 95523
completionTokens: 4751
durationSeconds: 40.1
costUsd: 0.440021
costBasis: provider
runId: run-20261101-p56-29332206
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: scope-consistency
    summary: "Task 7.1 makes the SDK alias a collection-time requirement for the whole live tier"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:163"
  - id: F002
    severity: concern
    category: process
    summary: "Task 10.1's commit carries only check-offs and notes"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:226"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Section 9 commit batches blocked tasks and sits outside the test-with pattern"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:216"
  - id: F004
    severity: note
    category: test-coverage
    summary: "Prompt content is only checked in the blocked live tier"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:128"
  - id: F005
    severity: note
    category: proportionality
    summary: "Proportionality of the Section 5.3 and 7.2 tests"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:136-139"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success-criteria coverage"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md"
  - id: F007
    severity: pass
    category: feasibility
    summary: "Referenced interfaces exist"
    location: "src/amoeba/runner/cf_call.py:31"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Task sequencing and commit distribution"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:43"
---

# Review: tasks — slice 140

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 7.1 makes the SDK alias a collection-time requirement for the whole live tier

Task 7.1 adds `AMOEBA_LIVE_SDK_MODEL` as a fourth variable and fails at collection if any of the four is unset. Only Task 9.4 uses it, so every other live test fails when the SDK alias is absent. The slice design's D10 names three variables. Verification Walkthrough step 4 (slice design lines 355-356) exports only those three, so the walkthrough would fail as written.
- Read `AMOEBA_LIVE_SDK_MODEL` lazily in the 9.4 fixture only, and fail naming the variable there.
- Keep the collection-time check to the design's three variables.
- Adjust Task 7.2's test and Task 8.1's contract text to match. Task 8.1 already records the addition, so only the wording of "four variables" changes.

### [CONCERN] Task 10.1's commit carries only check-offs and notes

The commit marker `chore: finish the 140 answering pipeline slice` follows a verification-only task. Task 10.1 changes no code. It sets `status` and records criterion notes. The project rule forbids a commit that only checks boxes or adds notes. Remove the marker so Task 10.1's check-offs and notes go into the Section 9 commit. If Section 9 stays blocked, they go into the Section 8 commit.

### [CONCERN] Section 9 commit batches blocked tasks and sits outside the test-with pattern

Tasks 9.1 to 9.5 share one commit marker at the end. Task 9.1 (YAML adjustment) is separable from the live tests, and 9.2 to 9.4 are blocked on it. If Squadron ships partially, nothing commits until 9.5. Move a marker after 9.1, for example `feat: adjust answering.yaml to shipped squadron syntax`. That keeps the committed YAML tied to the validated syntax before any live test depends on it.

### [NOTE] Prompt content is only checked in the blocked live tier

Task 5.1 requires about ten behavioral rules in the prompt text, but only structure is unit-tested (Task 5.2). Content is first exercised in Tasks 9.2 and 9.3, which are gated on Squadron. That matches the slice design, since the design calls for no unit test of prompt wording, and this note asks for no new test. Task 5.1 is large (effort 4), but splitting it would not help junior-AI completability enough to justify the extra task.

### [NOTE] Proportionality of the Section 5.3 and 7.2 tests

The 5.3 wheel test (`uv build` plus `uv run --isolated --with <wheel>`) and the 7.2 subprocess pytest test are heavier than typical unit tests. Each traces to a Technical Requirements bullet: wheel resolution, and tier exclusion with a named-variable failure. Keep them. If either proves flaky offline, the first candidate to trim is the isolated-run half of 5.3.

### [PASS] Success-criteria coverage

- **Squadron issue and slice-plan entries:** Tasks 1.1 to 1.3 cover them.
- **Rendering, `prepare_scratch` refusals and parsers:** Sections 3 and 4 cover them. Each implementation task is immediately followed by its test task.
- **Names-match test and wheel content:** Tasks 5.2 and 5.3.
- **Probe failure paths against a stub `sq`:** Task 6.2.
- **Live-tier exclusion and variable-name failure:** Tasks 7.1 and 7.2.
- **Process contract:** Task 8.1 covers the text, and Task 9.5 adds the dated observation.
- **Gated real-run criteria:** Task 9.1 for validation, 9.2 for files, pwned and check input, 9.3 for precedence and matching, and 9.4 for SDK refusal.

No task lacks a success-criterion source. I found no scope creep other than the SDK variable noted above. The slice states no NFR, so no load-test or CI-gate task is required.

### [PASS] Referenced interfaces exist

`output_head` and `run_cf` (`cf_call.py:31,39`), `SQ_EXECUTABLE` and `poll_run` (`process/sq_outcome.py:27,220`), `mint_run_id` (`runner/launch.py:34`), `probe_sq` (`runner/probes.py:40`) and `ProcessSettings.sq_timeout_seconds` (`process/settings.py:106`) are all present. The `--ignore=tests/load` addopts precedent is at `pyproject.toml:62`. Task 7.1's helper should pass a `datetime` to `mint_run_id`, which takes `now: datetime`.

### [PASS] Task sequencing and commit distribution

Dependencies run forward only. Constants come first, then inputs and artifacts, then the YAML, probe, live tier and docs, then the Squadron-gated work. Commit markers fall at the end of Sections 1, 3, 4, 5, 6, 7, 8 and 9, so they are spread through the file. Blocked tasks carry named `BLOCKED:` lines, and the unit-tested Amoeba side does not wait on Squadron.

### Run Digest

- Response length: 5381 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 191199 / 95670 / 95523 / 4751 / not computed
- Duration: 40.1 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
