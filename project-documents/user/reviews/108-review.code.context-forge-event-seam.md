---
docType: review
layer: project
reviewType: code
slice: context-forge-event-seam
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/108-slice.context-forge-event-seam.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: 552e26a5245e67746050d19c161287ef112c40b3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 85314
cachedTokens: 3232
cacheWriteTokens: 82080
completionTokens: 3547
durationSeconds: 30.5
costUsd: 0.370976
costBasis: provider
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: structure
    summary: "Orphaned table comment now sits above the new payload class"
    location: "src/amoeba/inbox/envelope.py:105-123"
  - id: F002
    severity: concern
    category: typing
    summary: "Test helpers and parameters are untyped or `Any`, against the strict pyright policy"
    location: "tests/store/test_cf_snapshots.py:33"
  - id: F003
    severity: concern
    category: testing
    summary: "No load test for a tenant that runs on the resident process loop"
    location: "src/amoeba/process/cf_watch.py#CFWatchTenant"
  - id: F004
    severity: note
    category: performance
    summary: "`_links` queries every open project's store on each scan interval"
    location: "src/amoeba/process/cf_watch.py:151-156"
  - id: F005
    severity: note
    category: typing
    summary: "Pyright suppressions in `_field_names`"
    location: "src/amoeba/cli/inspect_cf.py:42-47"
  - id: F006
    severity: note
    category: naming
    summary: "Single-letter local `c` in mapping code, and `_LINK_SELECT_LIST` reused for INSERT"
    location: "src/amoeba/store/mapping_cf.py:63"
  - id: F007
    severity: note
    category: security
    summary: "Test fixture is a copy of a real `projects.json`"
    location: "tests/cf_fixture.py:11"
  - id: F008
    severity: pass
    category: conventions
    summary: "Exception handling, SQL safety, and single-definition-site discipline"
    location: "src/amoeba/process/cf_watch.py:236-250"
---

# Review: code — slice 108

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Orphaned table comment now sits above the new payload class

The `#: The kind-to-payload-model table, defined once...` comment is still above `LinkCFProjectPayload`. It no longer sits above `KIND_PAYLOAD_MODELS`, so it now documents the wrong object and the table has no comment. Move the new class above that comment, next to `WatchReviewsPayload`.

### [CONCERN] Test helpers and parameters are untyped or `Any`, against the strict pyright policy

`_cf_changes` has no return annotation. The python rules include `tests/` in strict pyright and make zero errors a merge blocker. The same applies to `noise: Any` and `make: Any` in `tests/process/test_cf_watch.py` and `tests/upstream/context_forge/test_projects_file.py`. Use `Callable[[list[dict[str, Any]]], object]` and `Callable[[], bytes]` instead. `_cf_changes` in `tests/process/test_cf_watch.py` returns `list[Any]` where `list[Change]` is available.

### [CONCERN] No load test for a tenant that runs on the resident process loop

The python rules require at least one `tests/load/` test, asserting latency or resource bounds, for code on the concurrency and environment-layer paths. This tenant does a synchronous `stat`, a possible `read_bytes`, `json.loads`, and per-link SQLite reads and writes inside `tick`. The "one stat and nothing else" test covers functional behaviour only. I saw no test that bounds tick duration with many projects or links, or with a large `projects.json`. The `<1ms` sync-work budget is not verified.

### [NOTE] `_links` queries every open project's store on each scan interval

Once per `cf_scan_interval_seconds`, `_links` runs one SQL query per open project, even when the file is unchanged. The cost is bounded and probably fine at this scale. It is the part of an idle tick that grows with project count, so the load test above should cover it.

### [NOTE] Pyright suppressions in `_field_names`

The helper accepts `object` and then suppresses three pyright rules instead of narrowing each element with `isinstance(change, dict)`. The store mapping already guarantees an array of objects. Narrowing explicitly would remove the ignores and make the helper safe on its own.

### [NOTE] Single-letter local `c` in mapping code, and `_LINK_SELECT_LIST` reused for INSERT

`c = dict(zip(...))` goes against the "avoid single letters" rule. This may be deliberate if `mapping_feed.py` does the same. `sql_cf.py` also uses `_LINK_SELECT_LIST` to build the INSERT column list, where a neutral name such as `_LINK_COLUMN_LIST` would read better.

### [NOTE] Test fixture is a copy of a real `projects.json`

The fixture holds real project ids, names, and probably local paths. `*.json` files were excluded from this diff, so I could not check it for sensitive content such as `customData` or home-directory paths. Confirm that nothing private is committed.

### [PASS] Exception handling, SQL safety, and single-definition-site discipline

- **`_update_link`:** the broad `except Exception` logs with `logger.exception` and re-raises, so it satisfies rule (a). The `OSError` handlers are specific and commented.
- **SQL:** all statements are parameterised, and the outcome word is bound rather than inlined.
- **Constants:** column names, the outcome vocabulary, and the projected field names each have one definition site, and tests enforce this.
- **Failure paths:** failures are recorded as outcomes, nothing falls back silently to a default, and `_previous_state` raises on a bad baseline.
- **Test coverage:** coverage is thorough. It uses the real fixture, covers restart and kill-9 scenarios, and checks log-once behaviour.

### Run Digest

- Response length: 4509 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 85314 / 3232 / 82080 / 3547 / not computed
- Duration: 30.5 s
- Cost: $0.37 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
