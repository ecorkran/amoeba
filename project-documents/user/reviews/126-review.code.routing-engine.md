---
docType: review
layer: project
reviewType: code
slice: routing-engine
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/126-slice.routing-engine.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: 25a9f254acfd95c5890c276d719dbf8e9f7371fc
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 109240
cachedTokens: 3232
cacheWriteTokens: 106006
completionTokens: 3489
durationSeconds: 30.8
costUsd: 0.468372
costBasis: provider
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Inspection layer now imports from the runner package, and the boundary test was loosened to allow it"
    location: "src/amoeba/inspection/routing.py:11-14"
  - id: F002
    severity: concern
    category: performance
    summary: "Each listing row re-parses the stored table YAML"
    location: "src/amoeba/inspection/routing.py#_recomputes"
  - id: F003
    severity: concern
    category: error-handling
    summary: "An overrun check can fault the whole project on a single malformed in-flight entry"
    location: "src/amoeba/runner/routing/overrun.py#overrun_runs"
  - id: F004
    severity: concern
    category: correctness
    summary: "Default table path is resolved at import time through `str()` on a `Traversable`"
    location: "src/amoeba/process/settings.py:30-38"
  - id: F005
    severity: concern
    category: dry
    summary: "Route-name normalization is duplicated between validation and rule construction"
    location: "src/amoeba/runner/routing/table.py#_rule_of"
  - id: F006
    severity: note
    category: testing
    summary: "The wheel-contents test shells out to `uv build` and keys its skip on a stderr substring"
    location: "tests/runner/routing/test_wheel_contents.py:20-34"
  - id: F007
    severity: note
    category: testing
    summary: "The tick refactor and the new routing tests cover the key paths"
    location: "src/amoeba/runner/tick.py"
---

# Review: code — slice 126

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Inspection layer now imports from the runner package, and the boundary test was loosened to allow it

`inspection/routing.py` imports `amoeba.runner.routing.inputs` and `amoeba.runner.routing.recompute`. Rule 10 of `tests/test_import_boundaries.py` ("only `amoeba.cli` imports `amoeba.runner`") was rewritten with an `INSPECTION_RUNNER_IMPORTS` exemption so the import passes. The exempted modules are the pure ones, but `recompute` pulls in `engine`, `table` and `validate` transitively, so the exemption is wider than its two-name allowlist suggests. A cleaner split would move the pure pieces (`inputs`, `table`, `validate`, `engine`, `recompute`) to a shared package such as `amoeba.routing`. That keeps the rule intact and lets the runner and inspection both depend on it. `_runner_imports` also exempts the bare names `amoeba.runner` and `amoeba.runner.routing` for any inspection file, which weakens the guard further.

### [CONCERN] Each listing row re-parses the stored table YAML

`_recomputes` calls `store.routing_table_version` and then `recompute`, which runs `parse_table` (YAML parse, pydantic validation, rule construction). It does this for every decision row, even though the number of distinct table versions is small. A project with many decisions pays for the same parse repeatedly. Cache the parsed table by `decision.table_version` within one `routing_decision_rows` call.

### [CONCERN] An overrun check can fault the whole project on a single malformed in-flight entry

`overrun_runs` raises `ValueError` if any in-flight `sq_run` entry has no pipeline, a pipeline the table has no bound for, or a naive `issued_at`. `watch_overruns` runs on every tick before the faults are raised, so one such entry would fault the project on every tick. The docstring treats this as a programming error. But in-flight entries persist in the store across upgrades or table edits. Changing the shipped table's `time_bounds_minutes`, or using `--routing-table` with different bounds, could strand an old entry. The updated tests show the cost: several fixtures had to change pipeline `"noop"` and `"p"` to `"P4"`. Consider raising a distinct, per-entry `run_overrun`-style fault that names the entry, instead of failing the tick.

### [CONCERN] Default table path is resolved at import time through `str()` on a `Traversable`

`DEFAULT_ROUTING_TABLE_PATH = Path(str(resources.files("amoeba").joinpath(...)))` assumes the package is on a real filesystem. For a zipped install, `str()` of the traversable is not a readable path. `load_table` takes a `Path` and calls `read_bytes`, so it would fail at start-up. A wheel-contents test exists, but it only proves the file is packaged, not that this path is readable. Either use `resources.as_file`, or make the setting optional and read the packaged resource directly when it is unset.

### [CONCERN] Route-name normalization is duplicated between validation and rule construction

`_rule_of` re-does `Route(rule.route.strip().lower())`, which `validate._route_of` already does. Input-name normalization is shared through `normalize_input_name`, but route normalization is not. If the two drift, `_rule_of` would raise a raw `ValueError` after validation had passed. Expose one `normalize_route` helper in `validate.py` and use it in both places.

### [NOTE] The wheel-contents test shells out to `uv build` and keys its skip on a stderr substring

The test builds a wheel with a 180s timeout and skips only when stderr contains "hatchling". This is brittle across `uv` versions and slow for a unit-tier test. It does cover a real packaging risk, so it is worth keeping. Consider marking it so CI can gate it separately.

### [NOTE] The tick refactor and the new routing tests cover the key paths

Extracting `build_project_view` keeps `tick.py` short, and the ordering is documented: view built before routing, so a routing result is first seen on the next tick. The tests cover advance, rerun, hold, table-edit recompute, crash-recovery routing exactly once, and the overrun lifecycle, and they use real parsers and a real store rather than mocks. The `Route`-member scan test has a self-check, which is good practice.

### Run Digest

- Response length: 5123 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 109240 / 3232 / 106006 / 3489 / not computed
- Duration: 30.8 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
