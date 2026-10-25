---
docType: review
layer: project
reviewType: tasks
slice: routing-engine
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/126-tasks.routing-engine.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: 3c9094dfcdf0596992ad18d668d78a30d1e56092
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 209772
cachedTokens: 103124
cacheWriteTokens: 106642
completionTokens: 8388
durationSeconds: 62.7
costUsd: 0.521577
costBasis: provider
runId: run-20261025-p5-97da57a1
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md"
  - id: F002
    severity: concern
    category: scoping
    summary: "`inputs.py` and `table.py` will overrun the ~300-line limit as scheduled"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:94-119"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 6.3 leaves the tree red until 6.4 finishes"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:292-308"
  - id: F004
    severity: concern
    category: task-clarity
    summary: "Task 7.2 asks the implementer to discover facts the author could have checked"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:333-339"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "\"Unreadable table file\" is required by the slice design but not tested"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:191"
  - id: F006
    severity: note
    category: proportionality
    summary: "Some vocabulary tests are tautological"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:105"
  - id: F007
    severity: note
    category: risk
    summary: "The wheel test runs `uv build` in the default suite"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:201"
  - id: F008
    severity: note
    category: verification
    summary: "Test infrastructure the tasks lean on exists"
    location: "tests/runner/tick_support.py:216"
  - id: F009
    severity: note
    category: process
    summary: "Commit cadence is acceptable"
    location: "project-documents/user/tasks/126-tasks.routing-engine.md:54"
---

# Review: tasks — slice 126

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria trace to tasks

Each criterion in the slice design maps to at least one task.
- **Recomputation:** 4.5 and 6.5, including the table-edit-and-restart case.
- **Advance and rerun:** 6.2 and 6.5; the `max_attempts` fall-through is in 4.2 and 6.2.
- **Escalate:** 6.2.
- **Load refusal:** 3.3 plus the CLI exit-7 test in 5.2.
- **Unknown:** 4.2.
- **No route in code:** 4.6.
- **Time bound:** 7.1 and 7.3.
- **Crash and hold:** 6.5.
- **Technical requirements:** the wheel and default-table tests in 3.4, the CHANGELOG in 9.2, and the gates in 9.3.

Nearly every task traces to a criterion or a named design decision. The slice states no NFR, so no load-test or CI-gate task is needed.

### [CONCERN] `inputs.py` and `table.py` will overrun the ~300-line limit as scheduled

Tasks 2.1, 2.3 and 2.5 all put code in `inputs.py`:
- the `RoutingInput` enum, `VALUE_SETS`, `RoutingInputs` and the constants
- the `OutcomeEvidence` and `ReviewPart` dataclasses
- every outcome and review reducer, including the split-review combine

Tasks 3.1 and 3.2 likewise put the pydantic models, `Rule`, `RoutingTable`, parse and load, `TableError`, and about ten validation checks in `table.py`. Both files will likely land well over 300 lines. The file only catches this at Task 9.3, as a late `refactor:`.

Plan the split now:
- Move `OutcomeEvidence`, `ReviewPart` and `reduce` into their own module (for example `reduce.py`), leaving the vocabulary in `inputs.py`.
- Put the load-time validation in its own module beside `table.py`.

This departs from the component sketch in the slice design, but that sketch is not a hard contract and the ~300-line rule is.

### [CONCERN] Task 6.3 leaves the tree red until 6.4 finishes

Task 6.3 says "Do not commit until 6.4 passes", and the two tasks are committed together. That is one large uncommitted change: the `_decide` split, the stage wiring, and a sweep of every stand-in caller in the tests (effort 3 + 3).

Part of 6.3 can be committed on its own. Building `ProjectView` before the still-empty `[route]` slot changes no behavior, because routing is not wired yet and the stand-in still routes from tests. Split it:
1. Commit the view-before-slot refactor as `refactor:`, with the suite green.
2. Wire `route_outcomes` and retire the stand-in as one `feat:`.

This also cuts the effort of the remaining task and gives a safe resume point.

### [CONCERN] Task 7.2 asks the implementer to discover facts the author could have checked

Task 7.2 says to add the kind to "whatever set names the project-scoped kinds, if one exists". That hedge forces a junior to search for and decide on something the author could look up while writing the "checked against the code" notes. The same task also moves the overrun check before `raise_expected_faults`. The stated reason, that the order doesn't change any result, is sound, but it is not recorded as a deviation from the slice design's data flow.

Name the exact set or function, or state that none exists. Also list the placement among the "Task-level additions to the LLD", not only inside the task.

### [CONCERN] "Unreadable table file" is required by the slice design but not tested

The Load refusal criterion lists "a missing or unreadable table file". Task 3.1 implements `OSError` and non-UTF-8 handling, but the 3.3 test list names only a missing file. Add an unreadable case, such as a directory path or a non-UTF-8 byte string, so the `UnicodeDecodeError` branch is exercised.

### [NOTE] Some vocabulary tests are tautological

Task 2.1 builds enum-mirrored sets from their enums, so 2.2's "enum-mirrored sets equal their enum's values" check proves nothing. The "every set contains `UNKNOWN`" and "`RoutingInputs` refuses a bad value" checks are worth keeping. Drop the mirror assertion.

### [NOTE] The wheel test runs `uv build` in the default suite

The slice design requires a wheel-build test, so the task is correctly scoped. `uv build` may need to fetch the build backend, which makes the default suite network-dependent and slower. If that causes trouble, mark or skip the test offline rather than dropping it.

### [NOTE] Test infrastructure the tasks lean on exists

I confirmed that the referenced helpers are present:
- `tick_support.py`, `plan_tick_support.py`, `ast_strings.py`
- `test_cf_commands_defined_once.py`, `routing_helpers.py`, `routing_support.py`
- `evidence_harness.py`, `review_fixtures.py`, `inspection_harness.py`
- `test_import_boundaries.py`, `test_crash_recovery.py`, `test_factory.py`, `test_cli_lifecycle.py`

The tick rig exposes an injectable clock (`rig.clock.wall` / `monotonic`), so the "injected clock" in 7.3 is feasible. `src/amoeba/runner/dispatch/build_view.py` also exists, which suits the view-building helper that 6.3 allows for.

### [NOTE] Commit cadence is acceptable

Commits are spread across sections 1 to 9, and nothing is batched at the end. Implementation tasks without their own commit (2.1, 2.3, 2.5, 2.7, 3.1, 3.2, 4.1, 4.3, 6.1, 8.1) commit together with the test task that follows them. That fits the test-with pattern. A single task file is proportionate for a 3/5 slice.

### Run Digest

- Response length: 6407 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 209772 / 103124 / 106642 / 8388 / not computed
- Duration: 62.7 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
