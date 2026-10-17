---
docType: review
layer: project
reviewType: tasks
slice: network-api
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-1.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: 364974b3c106633ee43ac06490d82dd99fe17a4d
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 192381
cachedTokens: 97087
cacheWriteTokens: 95288
completionTokens: 5508
durationSeconds: 57.8
costUsd: 0.446619
costBasis: provider
runId: run-20261017-p5-dcc30257
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Byte-identical baseline is deleted before Task 3.3 changes the CLI read path"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:286"
  - id: F002
    severity: concern
    category: task-sizing
    summary: "Tasks 2.5 and 2.6 form one very large, red-in-between commit"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:204-253"
  - id: F003
    severity: note
    category: scope
    summary: "Task 2.4 adds `feed/wire.py` to `SINGLE_DEFINITION_MODULES`"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:193"
  - id: F004
    severity: note
    category: proportionality
    summary: "Task 1.2 adds a \"every listing returns at least one row\" test"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:86"
  - id: F005
    severity: note
    category: proportionality
    summary: "Task 2.8 re-greps docs already confirmed clean"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:284"
  - id: F006
    severity: pass
    category: coverage
    summary: "Section 1–3 coverage of the slice design"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:56-370"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Test-with pattern and commit distribution"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:118-370"
  - id: F008
    severity: pass
    category: coverage
    summary: "Load test and CI gating exist in later files"
    location: "project-documents/user/tasks/109-tasks.network-api-3.md:225-236"
  - id: F009
    severity: pass
    category: dependencies
    summary: "Open PM item is flagged and scoped"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:43"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Byte-identical baseline is deleted before Task 3.3 changes the CLI read path

Task 2.8 proves `inspect` output is byte-identical, then deletes `$BASE`, which holds the seeded store and the capture script. Task 3.3 then changes `read_listing`, which the CLI calls. Every project listing now runs inside `read_transaction()` and also issues `change_head`. Its only guard is "`tests/test_cli_inspect.py` passes unchanged". The slice design's Technical Requirement is that `inspect` output and `--help` stay byte-identical. Either keep `$BASE` until Task 3.4 and rerun the diff there, or add a one-line rerun to Task 3.4's success criteria. The capture script already exists, so the rerun costs almost nothing.

### [CONCERN] Tasks 2.5 and 2.6 form one very large, red-in-between commit

Tasks 2.5 and 2.6 are committed together. The combined change moves 5 source modules and 4 test files, creates `core.py`, moves the registry, rewrites `run_listing` and `_add_inspect_parser`, and edits several test files. Task 2.5 cannot be verified on its own, because it says "the suite will not pass until Task 2.6", and each is rated Effort 3. The cadence rule ("no red suite") is respected only by merging the two. A junior AI could get lost mid-way.
- **Option 1:** split 2.6 so the registry move keeps temporary imports from the old modules until the end. The cost is a shim, which the slice design forbids.
- **Option 2:** keep the combined commit but add an intermediate checkpoint. Run `pyright` and `ruff` after 2.5, since they can pass before the registry is rewired. Add a "stop and ask the PM if 2.5 plus 2.6 touches more than the listed files" guard.
I'd take option 2.

### [NOTE] Task 2.4 adds `feed/wire.py` to `SINGLE_DEFINITION_MODULES`

The slice design requires this test only for `ApiErrorCode` and the exception table (Technical Requirements). The `feed/wire.py` entry is a small, defensible extra, since it protects the "one definition of a change's wire form" claim. I'd keep it, but it is the only task step that traces to no success criterion in Sections 1–3.

### [NOTE] Task 1.2 adds a "every listing returns at least one row" test

This test is conditional ("if one does not already assert it"). It supports the parity success criterion, because a listing with no seeded row would pass parity vacuously. It is proportionate; no change needed.

### [NOTE] Task 2.8 re-greps docs already confirmed clean

The Context Summary records no contract-doc references to the moved paths (grep, 20261017). Task 2.8 runs the grep again. That is cheap and safe, since files may have changed, so I'd leave it.

### [PASS] Section 1–3 coverage of the slice design

- **Migration byte-identical gate:** Tasks 1.3 and 2.8 cover it, including `--help`, table and `--json` output.
- **Inspection layering rule:** Task 2.7 covers it.
- **`discover_project_ids` and `change_line` moves:** Tasks 2.3 and 2.4.
- **`read_transaction()` and `change_head()`:** Tasks 3.1 and 3.2.
- **Shared-snapshot test for rows and `as_of_seq`:** Task 3.4.
- **Prerequisite check that 107 and 108 are merged:** Task 1.1.
- **Writer-guard unchanged:** confirmed in Task 2.7.

### [PASS] Test-with pattern and commit distribution

Each implementation task is followed immediately by its tests (2.1→2.2, 3.1→3.2, 3.3→3.4). Deferred commits are explicitly paired. Commits land at 1.2, 2.2, 2.3, 2.4, 2.6, 2.7, 3.2 and 3.4, so nothing is batched at the end. Dependencies are linear, with no cycles.

### [PASS] Load test and CI gating exist in later files

- **Load test:** the slice restates the delivery-latency NFR (p95 ≤ 1 s). Task file 3 creates `tests/load/test_serve_load.py` for it.
- **CI gating:** file 3 states that CI gates it with no workflow change, because the `Load tests` step already runs `uv run pytest tests/load`. It tells the implementer to confirm that step is still there. `.github/workflows/ci.yml` exists, so the explicit-gating requirement is met.
- **Contract docs:** the four contract-doc deltas and `CHANGELOG` are in file 3.

### [PASS] Open PM item is flagged and scoped

The slice design contradicts itself about where `ServeRefusedError` is mapped to an exit code. The task file names the conflict, recommends a resolution, and gates only Task 8.1 on the PM's answer, so Sections 1–7 are not blocked.

### Run Digest

- Response length: 5706 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 192381 / 97087 / 95288 / 5508 / not computed
- Duration: 57.8 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
