---
docType: review
layer: project
reviewType: tasks
slice: network-api
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/109-tasks.network-api-1.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261008
dateUpdated: 20261008
reviewedSha: e3175941e3b9b62b982951f504ae9c54428c3817
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 49.4
runId: run-20261008-tasks-plan-43872396
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: concern
    category: design-gap
    summary: "Authenticator seam cannot express per-endpoint scope, and endpoint auth wiring is not in the read tasks"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:451"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Intermediate state of `run_listing` during Tasks 2.8–2.9 is unspecified"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:257"
  - id: F003
    severity: concern
    category: design-gap
    summary: "Likely import cycle between `registry.py` and row modules is treated as conditional"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:201"
  - id: F004
    severity: concern
    category: nfr-coverage
    summary: "Latency bound and stall/memory behavior have no `tests/load/` task or CI gate"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:21"
  - id: F005
    severity: concern
    category: design-clarity
    summary: "\"Private\" shared validation helper is called across modules, and `query_from_namespace` location is ambiguous"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:221"
  - id: F006
    severity: note
    category: task-scope
    summary: "Tasks 2.5b and 2.5c lack Steps sections, and 2.5a–c bundle multiple modules"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:170"
  - id: F007
    severity: note
    category: coverage
    summary: "Writer-guard coverage of `amoeba.serve` is deferred to file 2"
    location: "project-documents/user/tasks/109-tasks.network-api-2.md:57"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage for Group A and the Group B skeleton"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:88"
  - id: F009
    severity: pass
    category: process
    summary: "Test-with pattern, commit distribution, and gating"
    location: "project-documents/user/tasks/109-tasks.network-api-1.md:29"
---

# Review: tasks — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Authenticator seam cannot express per-endpoint scope, and endpoint auth wiring is not in the read tasks

Task 3.5a defines `authorize(principal) -> ApiErrorCode | None` and says Task 6.3 adds scope-aware use "without changing these signatures". The LLD requires an endpoint → required-scope table (D6). A method that receives only the principal cannot know whether the endpoint needs `read` or `submit`. `authenticate()` returning `None` also means "no principal" under `NoAuth` but "401" under `TokenAuth`, and the task does not say how callers tell these apart. Tasks 3.6 and 3.7 never say the endpoints call `authenticate`/`authorize`. Tests use `NoAuth` until Task 6.5, so a read endpoint added without the hook would pass every test until then. Fix the protocol signature now (required scope as an argument, or a result type that separates "anonymous" from "denied"). Also add a step in 3.6 (and later endpoint tasks) that wires auth in and tests it with a stub authenticator.

### [CONCERN] Intermediate state of `run_listing` during Tasks 2.8–2.9 is unspecified

Task 2.8 changes `cli/inspect.py` to build a `ListingQuery` and pass it to row functions. Only the core module is converted at that point. Modules converted in 2.9a–2.9f still take `argparse.Namespace`. The tasks do not say how `run_listing` dispatches to both signatures between 2.8 and 2.9f. This is also where the byte comparison could fail for reasons unrelated to the change. Specify a per-listing transitional rule that is removed in 2.9f. Alternatively, convert all row signatures in one mechanical pass with the byte comparison as the gate.

### [CONCERN] Likely import cycle between `registry.py` and row modules is treated as conditional

Task 2.1 puts the types in `registry.py` and `rows_core.py` imports them. Task 2.5d then has `registry.py` import every `rows_*` module to build `LISTINGS`. That is a circular import by construction, not a maybe. Task 2.5d's "if that creates a cycle" fallback of `inspection/types.py` also departs from the LLD Component Structure. Decide this in Task 2.1: either put the types in `types.py` from the start, or have `LISTINGS` assembled in a separate module. Record the LLD deviation for the PM.

### [CONCERN] Latency bound and stall/memory behavior have no `tests/load/` task or CI gate

The slice states a latency target under Value: a committed change is on the wire within `follow_interval_seconds` plus delivery. It also states the stall/flat-memory criterion. `tests/load/` exists in the repo (`test_inbox_concurrent.py`, `test_crash_loop.py` and others). The breakdown explicitly declines a load test and CI gate, and puts the latency check in the default suite (Task 5.10). The reasoning is documented, but it departs from the review rule. Either add a `tests/load/` task (latency and stall/memory) plus a CI-gating task, or get an explicit PM waiver recorded.

### [CONCERN] "Private" shared validation helper is called across modules, and `query_from_namespace` location is ambiguous

Task 2.6 asks for one "private helper" shared by `query_from_namespace` (which lives in `cli/inspect.py`) and `query_from_params` (in `inspection/query.py`). A private helper in `inspection/query.py` called from `cli/` is an access-convention violation. The step text ("Add `query_from_namespace`…") reads as if it belongs in `query.py`, and only the success criterion corrects that. Name the helper publicly, such as `build_query(listing, project, mapping)`, and state in the step where each builder lives.

### [NOTE] Tasks 2.5b and 2.5c lack Steps sections, and 2.5a–c bundle multiple modules

Tasks 2.5b and 2.5c have only an Objective and Success Criteria ("as 2.5a"). The module counts are unknown until Task 1.1 runs. Commit "per module" is fine, but each task should have its own checkbox steps so a junior AI can check progress. Task 2.10's optional `read_listing` ("tell the PM if no counterpart") is a reasonable hedge, but Task 3.8 depends on it, so settle it at Task 1.1.

### [NOTE] Writer-guard coverage of `amoeba.serve` is deferred to file 2

The LLD requires `amoeba.serve` and `amoeba.inspection` in the writer-guard scanned set. Task 2.10 handles `inspection`, and Task 3.9 (file 2) adds `serve`. This is covered, but only once Task 3.9 lands, and no `amoeba.serve` module exists to scan until then. No action is needed.

### [PASS] Success-criteria coverage for Group A and the Group B skeleton

The following are all traced to tasks:
- the byte-comparison criterion (Tasks 1.2 and 2.1–2.10)
- no re-export shims (2.12)
- no `argparse` in `amoeba.inspection`
- `ListingQueryError` on undeclared options (2.6/2.7)
- the `change_as_json` move (2.11)
- the layering rules (2.10, 3.5a)
- the error table and statuses (3.4/3.4a)
- unknown-parameter `400 invalid_query` (3.5)
- discovery from the registry (3.6/3.7)
- `ServeSettings` and `is_loopback` (3.2/3.3)
- the `serve`-not-a-project test (3.7)

Later criteria (submission, feed, auth, serve, e2e) sit in files 2 and 3.

### [PASS] Test-with pattern, commit distribution, and gating

Each implementation task is followed immediately by its test task, with explicit "commit with Task N" links (2.6/2.7, 3.2/3.3, 3.4/3.4a). Group A commits per module, behind a byte-comparison harness built first (1.2). Task 1.1 checks the 105–108 hard gate by file and surfaces the PM ratification points (D2, D6, `SERVE_REFUSED`). Dependencies are linear with no cycles.

### Run Digest

- Response length: 6613 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 49.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
