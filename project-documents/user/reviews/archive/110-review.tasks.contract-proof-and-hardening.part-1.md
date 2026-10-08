---
docType: review
layer: project
reviewType: tasks
slice: contract-proof-and-hardening
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: b125625692c18c030e6634fb30d69564e36dd647
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
turns: 11
promptTokens: 354159
cachedTokens: 314112
completionTokens: 25642
reasoningTokens: 23286
durationSeconds: 66.8
runId: run-20261008-p5-9c7d33cf
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: completeness
    summary: "Success criteria are fully traced to tasks"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F002
    severity: pass
    category: testing
    summary: "Load-tier restart matrix and CI gating are explicit"
    location: ".github/workflows/ci.yml:54"
  - id: F003
    severity: concern
    category: completeness
    summary: "No task implements `record_runner_report` when 106 ships without it"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md"
  - id: F004
    severity: concern
    category: sequencing
    summary: "File 2's \"needs only 101–104\" gate for Tasks 9.1–9.4 is internally inconsistent"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F005
    severity: concern
    category: design-deviation
    summary: "Task 9.1 silently renames an LLD-defined type without ratification"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Task 6.5 is oversized for a single Junior-AI task"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F007
    severity: note
    category: task-clarity
    summary: "Host working-directory split is asserted but only implied in the harness task"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Success criteria are fully traced to tasks

Every LLD Success Criterion has a corresponding task. The clean sequence criteria (three verdicts, two judge samples, one `ingested`, one `runner_issued`, `finding_changes` naming round 1) → Task 5.9; kill-point completion and snapshot equality → Tasks 6.2–6.4 and 7.1; subscriber transcript/replay → Task 6.5; `proof-b` keying → Tasks 5.9, 8.1; three directory resolutions and relative refusal → Tasks 2.1–2.2, 8.2; slug ids at every entry point → Tasks 2.3–2.4; the four `done` refusals → Tasks 2.5–2.6; pruning classifications → Tasks 9.1–9.5; export pins → Task 3.3 (with deferred feed/squadron pins in Task 6.5); public-only guard → Task 4.9; docs link resolution → Task 10.5; contract index / obligations / gap table → Tasks 10.4–10.5.

### [PASS] Load-tier restart matrix and CI gating are explicit

The slice restates the restart matrix in the load tier. Task 7.1 creates `tests/load/test_restart_matrix.py` (eleven `after-step-N` cases) and its steps explicitly require reading `ci.yml` and confirming `tests/load` is a gated, separate CI step. The existing workflow runs `uv run pytest tests/load` as its own failing step, so CI gating is verified in-task rather than left implicit.

### [CONCERN] No task implements `record_runner_report` when 106 ships without it

The slice's Interfaces Required states the report-back method is this slice's to add "if 106 ships without it." Task 1.1 only detects its absence and instructs the implementer to "stop and tell the PM" — there is no task anywhere in either file that adds the one-transaction store method. Task 5.4 depends on that method by name; if 106 lands without it, the branch has a committed deliverable with no task and the proof cannot be built. Either a conditional task should exist or the slice design should be amended to drop the commitment.

### [CONCERN] File 2's "needs only 101–104" gate for Tasks 9.1–9.4 is internally inconsistent

The hard gate asserts Tasks 9.1–9.4 "need only 101–104 and depend only on Sections 2–3." But Task 9.1 creates `src/amoeba/upstream/squadron/run_pruning.py` — the package the LLD says is created by 105 ("next to 105's parser") — and its steps require adding `classify_paused_runs`/`RunDisposition`/`DispositionKind` to the squadron pin test "from Task 3.3." Task 3.3 explicitly *skips* that pin when `src/amoeba/upstream/squadron/` is absent and defers it to Task 6.5. So Task 9.1 has an undeclared dependency on either 105 being present (making the gate claim wrong) or on Task 6.5 (breaking the stated ordering). The dependency declaration `Dependencies: 3.3` and the gate prose do not agree.

### [CONCERN] Task 9.1 silently renames an LLD-defined type without ratification

The LLD's "Patterns and Conventions" names the disposition `StrEnum` as `RunDisposition` and also, in API Contracts, names the result record `RunDisposition`. Task 9.1 resolves the clash by naming the enum `DispositionKind` and the record `RunDisposition`, and merely "tells the PM of the rename when reporting." This is a contract-surface naming decision embedded in an implementation task rather than ratified like D5 (which has a dedicated "PM ratification" section). It should be a ratified design decision or an LLD amendment, since the pinned export test and the 120-facing contract index both bind to it.

### [CONCERN] Task 6.5 is oversized for a single Junior-AI task

Task 6.5 (effort 4) bundles: writing any skipped feed/squadron export pins from Task 3.3, a local `amoeba feed --follow` subscriber, a remote SSE client with `Last-Event-ID` reconnect logic, local/remote/feed-from-zero transcript reconciliation, and a deliberate mid-sequence disconnect to exercise resume — all under one commit. These are independently verifiable concerns (pin completion, local subscriber, remote subscriber, reconciliation) and would be more completable if split, consistent with how the actor work was split into 5.8/5.8a/5.8b/5.8c.

### [NOTE] Host working-directory split is asserted but only implied in the harness task

Task 8.1 verifies "the harness starts the host with `cwd` set to one directory and runs actors with `cwd=work_dir`," but Task 4.6's `start_host(...)` step list does not state that the host's `cwd` is set to a directory distinct from `work_dir`; it only says `run_cli` runs "from `work_dir` (a different working directory from the host's)." The requirement is implied rather than specified in the task that must implement it, which risks an under-specified harness surfacing as a locality-test failure in Section 8.

### Run Digest

- Response length: 5937 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 81687
- Effort: backend default
- Turns: 11
- Tokens — prompt / cached / completion / reasoning: 354159 / 314112 / 25642 / 23286
- Duration: 66.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
