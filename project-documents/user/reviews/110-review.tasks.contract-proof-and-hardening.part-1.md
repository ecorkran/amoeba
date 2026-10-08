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
reviewedSha: 81ec58629fe490d0a8f07b6d5fcfb225da6f5c43
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 4
promptTokens: 84573
cachedTokens: 54528
completionTokens: 8849
reasoningTokens: 7433
durationSeconds: 25.6
runId: run-20261008-p5-9c7d33cf
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every slice success criterion traces to a task"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-1.md"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 11.1 under-declares its dependencies"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F003
    severity: note
    category: ci-gating
    summary: "Load-tier CI gating is confirmed rather than wired"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
  - id: F004
    severity: note
    category: scope-creep
    summary: "Task 9.0 adds a module move beyond the LLD component structure"
    location: "project-documents/user/tasks/110-tasks.contract-proof-and-hardening-2.md"
---

# Review: tasks — slice 110

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Every slice success criterion traces to a task

Cross-referencing the slice design's Success Criteria against the tasks:
- Clean-run assertions (three verdicts, two judge samples, `ingested`/`runner_issued`, `finding_changes`) → Task 5.9a.
- Three kill windows and snapshot comparison → Tasks 6.1–6.4; `mid-follow`/subscriber transcript (local and remote) → Tasks 6.5, 6.5a.
- `proof-b` isolation → Tasks 5.9a, 8.1.
- Three directory resolutions + relative refusal + slug refusal entry points → Tasks 2.4, 8.2.
- Four `done` refusals → Tasks 2.5, 2.6.
- Pruning dispositions + byte-identical runs dir → Tasks 9.2, 9.4, 9.5.
- Public-only guard and its self-test → Task 4.9; five export pins → Task 3.3 + Task 6.4a.
- Store/upstream import direction, writer guard, docs link check, line limits, ruff/pyright → Tasks 9.1, 10.5, 11.1.
- Contract index / Integration Requirements → Task 10.4; gap table → Task 10.5.
No success criterion was found without a corresponding task, and no task was found that fails to trace to a criterion.

### [CONCERN] Task 11.1 under-declares its dependencies

Task 11.1 ("Full validation and walkthrough") declares `Dependencies: 10.6`. Its dependency chain (11.1 ← 10.6 ← 10.5 ← 10.4 ← 10.1[5.9a] / 10.2[2.6] / 10.3[2.6]) therefore does **not** include Sections 7, 8, or 9. Yet Task 11.1's own steps require them: it runs `uv run pytest tests/load` (the restart matrix from Task 7.1), runs the LLD Verification Walkthrough including step 5 (pruning, Tasks 9.x) and step 4 (locality, Task 8.2), and greps for `run_pruning.py` importing no store internals (Task 9.1). A junior AI following the declared order could begin final validation before the restart matrix, locality, and pruning work exists, and would then either fail or silently validate an incomplete slice. Task 11.1 should declare 7.1, 8.2, and 9.5 (or a terminal task that transitively covers them) as dependencies.

### [NOTE] Load-tier CI gating is confirmed rather than wired

The restart matrix lives in `tests/load/` (Task 7.1), which is the load-tier artifact for this slice. Task 7.1 addresses CI explicitly by asserting "`ci.yml` needs no change (it already runs `tests/load`); confirm by reading it." This is an explicit confirmation step and the slice design states `ci.yml` already runs the load tier as its own step, so gating is not left implicit. Worth noting only because it is a confirmation, not a wiring task; if the CI configuration were ever to change, nothing in this breakdown would add the missing gate.

### [NOTE] Task 9.0 adds a module move beyond the LLD component structure

The slice design's Component Structure lists `run_pruning.py` under `amoeba.upstream.squadron` but does not list a `run_files.py`, nor the relocation of `parse_run_file`/`SquadronRun` out of `amoeba/process/observers/sq_runs.py`. Task 9.0 performs that move and correctly flags itself as "a small addition to the LLD … report it to the PM with the task summary." It traces to the Technical Requirement that `run_pruning.py` imports no store internals and sits next to 105's parser, so it is justified work rather than ungrounded scope, but it is genuinely beyond what the LLD enumerates and depends on the PM being informed.

### Run Digest

- Response length: 4345 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 25864
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / completion / reasoning: 84573 / 54528 / 8849 / 7433
- Duration: 25.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
