---
docType: review
layer: project
reviewType: tasks
slice: slice-writing-pipeline
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/180-tasks.slice-writing-pipeline.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: a55f965d63dee5efb512f7a82fa36f33c86c7ed2
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
effort: xhigh
turns: 19
promptTokens: 593586
cachedTokens: 456439
cacheWriteTokens: 137135
completionTokens: 56552
durationSeconds: 252.2
costUsd: 0.181747
costBasis: provider
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria traced to tasks"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:54-234"
  - id: F002
    severity: concern
    category: coverage
    summary: "No task checks that 184 can poll a request run with `poll_run`"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:211-223"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Tasks 9.2 and 9.3 cannot collect without the model settings"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:204-215"
  - id: F004
    severity: concern
    category: verification
    summary: "Scratch-repo setup may dirty the checkout the run must leave clean"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:213-214"
  - id: F005
    severity: note
    category: commit-cadence
    summary: "Commit types at two markers do not match their content"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:191"
  - id: F006
    severity: note
    category: commit-cadence
    summary: "Task 1 puts two planning documents in one commit"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:70"
  - id: F007
    severity: note
    category: granularity
    summary: "Tasks 3.3 and 9.2 are too small to stand alone"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:91-93"
  - id: F008
    severity: note
    category: proportionality
    summary: "Some tests go beyond what the success criteria need"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:215"
  - id: F009
    severity: note
    category: consistency
    summary: "`main` is hard-coded where the slice says \"target\""
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:214"
  - id: F010
    severity: note
    category: parser-fixtures
    summary: "Parser fixtures are hand-written until Section 9"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:109"
  - id: F011
    severity: pass
    category: sequencing
    summary: "Sequencing, dependencies and test-with pattern"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:48"
  - id: F012
    severity: pass
    category: verification
    summary: "Cited paths, helpers and anchors resolve"
    location: "project-documents/user/tasks/180-tasks.slice-writing-pipeline.md:10-16"
---

# Review: tasks — slice 180

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria traced to tasks

Each functional, unit-tier, technical and integration criterion in the slice design maps to a task. F1–F3 and walkthrough step 4 map to 9.4. F4 maps to 9.3's every-run checks. F5 maps to 9.2. The unit criteria map to 4.2, 6.2 and 1.2–1.3. The technical requirements map to 3.2/3.4, 4.2/9.5, 5.5, 7.1–7.3, 8.1 and 8.2, and walkthrough steps 1–6 map to 9.6. The only missing criterion is the `poll_run` check below. No task falls outside the slice's Included list.

### [CONCERN] No task checks that 184 can poll a request run with `poll_run`

The slice's Integration Requirements say 184 can launch the pipeline, "poll it with the existing `poll_run`", and parse the reply, with no further Squadron change. `poll_run` exists (`src/amoeba/process/sq_outcome.py:227`). Task 9.3 checks only the launch's exit code. No task calls `poll_run` on the run id the launch argv sets (`--run-id <id>`), so nothing shows the observation path 184 depends on. Add a step to 9.4: after a run, `poll_run` on that run id returns the outcome that gates `read_reply`, and the reply is read only from a completed run.

### [CONCERN] Tasks 9.2 and 9.3 cannot collect without the model settings

Task 7.2 reads `AMOEBA_LIVE_REQUEST_MODEL` and `AMOEBA_LIVE_REQUEST_MAX_COST_USD` at collection for all of `tests/live/request_run`, the same pattern as `tests/live/conftest.py:22-23`. Task 9.2's validate test and Task 9.3's scratch-repo test both live there, and neither calls a model. Only Task 9.4 says what to do when the variables are unset (write a `BLOCKED:` line). A session at 9.2 would hit a collection error with no instruction. State the choice in the task file. Either 9.2 and 9.3 require the two variables to be set, with the values the PM supplies (no model is called, so no spend), or the no-model checks move to a location that does not gate on the model settings. The slice's D10 requires collection-time failure, so the session should not have to decide this.

### [CONCERN] Scratch-repo setup may dirty the checkout the run must leave clean

Task 9.3 registers the scratch repo itself with `cf init --lite`, then asserts `git status --porcelain` is empty and that the only new commit is the run's. The answering fixture's docstring (`tests/live/answering/conftest.py:3-6`) describes the opposite design: the registration sits in a parent directory so "the scratch directory itself stays free of anything `cf init` writes." Task 9.3 cites that file only for the data-directory setup. It does not say where `cf init`'s files go. Either the clean-tree check fails at setup, or a session commits init files into the start commit and the assertions pass for the wrong reason. Name the mechanism. Use the answering pattern, which also changes the 9.3 success line about `cf list projects`, or run init before the start commit and state which files are expected.

### [NOTE] Commit types at two markers do not match their content

The marker after Section 8 is `docs:`, but 8.2 may change Python (its own text allows import-boundary fixes). The marker after 9.6 is `feat:` but carries test fixtures, a test and a process-contract note. Use the type that matches the bulk of each commit, or split the marker.

### [NOTE] Task 1 puts two planning documents in one commit

The planning cadence is one commit per document. Task 1 edits the program slice plan (`user/architecture/180-slices.program-coordination.md`) and the dependency register (`user/notes/001-squadron-dependencies.amoeba.md`) under one marker. Split it into two commits, or record that the two edits are one change.

### [NOTE] Tasks 3.3 and 9.2 are too small to stand alone

Task 3.3 is one function that writes one file. Task 3.4 already tests it, so it can fold into 3.1 or 3.4. Task 9.2 is one validate test. Task 9.1 already runs the same validate command by hand, so add the unknown-key case to 9.1's success line and drop 9.2 as a separate task.

### [NOTE] Some tests go beyond what the success criteria need

Three items are not required by a criterion. (a) `test_scratch_repo.py` in 9.3 tests the fixture builder. Keep it only if it is wanted as a pre-spend check, and say so. (b) The source-text test in 7.3 that reads `tests/live/conftest.py` breaks on any rewording. The collect-only check in 7.1's success already shows the move. (c) 6.2 lists stdin devnull, cwd cleanup and stderr quoting, which D9 does not require. Trim these to what D9 and the criteria name, or cite the answering test each one mirrors.

### [NOTE] `main` is hard-coded where the slice says "target"

Task 9.3 asserts "HEAD is on `main`", and 9.4 uses `main` in its merge-base and HEAD checks. The slice speaks of "the target", which can differ under `git.integration_branch`. The fixture uses `main`, so the checks pass, but the value appears in several places. Define the scratch target once in the harness and reference it.

### [NOTE] Parser fixtures are hand-written until Section 9

Task 4.2 builds its fixtures from the LLD's D7 shape, and 9.5 is the first real-format check. The answering pipeline already uses `reply_format: json` with `reply_file` (`src/amoeba/runner/answering/answering.yaml:23-25`). If the answering tier keeps a captured reply, use it in 4.2 so the object shape is confirmed before 4.1 is committed. The live case in 9.4 would still catch any mismatch.

### [PASS] Sequencing, dependencies and test-with pattern

The task graph has no cycles. Section 9 waits on a Squadron release, and the file says so and names each `BLOCKED:` condition. Each implementation task is followed by its test: 3.1/3.2, 3.3/3.4, 4.1/4.2, 6.1/6.2, 7.2/7.3 and 9.3/9.4. The Section 5 group is tested in 5.5 directly after. The constants come first (2.1) and later tasks import them.

### [PASS] Cited paths, helpers and anchors resolve

Checked and present: the answering pipeline files, `probes.py:68` (`probe_answering_pipeline`), `cf_call.py` (`run_cf`, `output_head`), `process/errors.py:26` (`StartupFailedError`), `tests/live_settings.py` (`require_variable`, `read_live_settings`), `tests/live/answering/conftest.py` (`live_harness`), the answering test files named in 3.2–7.3, the `docs/process-contract.md` headings "The answering pipeline" and "Context Forge shapes" plus the "Squadron shapes" bullet that 9.5 extends, the register's S14/S15 rows and "Net:" line, and both architecture phrases that 1.3 quotes. The `tests/live/conftest.py` lines that 7.1 moves (22–28) match its description.

### Run Digest

- Response length: 9039 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 19
- Tokens — prompt / cached / cache write / completion / reasoning: 593586 / 456439 / 137135 / 56552 / not computed
- Duration: 252.2 s
- Cost: $0.18 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
