---
docType: review
layer: project
reviewType: code
slice: answering-pipeline
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/140-slice.answering-pipeline.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 546c8659bcdd348eb5888867ae1f9b41aa246085
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 47317
cachedTokens: 13347
cacheWriteTokens: 33968
completionTokens: 2273
durationSeconds: 20.9
costUsd: 0.162745
costBasis: provider
squadronVersion: 0.24.14
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: performance-resource
    summary: "Live harness kills only the launcher, so a timed-out run may keep spending"
    location: "tests/live_harness.py:88-93"
    resolution: fixed
  - id: F002
    severity: concern
    category: test-debt
    summary: "A unit-tier test shells out to `uv build`"
    location: "tests/runner/answering/test_wheel_contents.py:16-26"
    resolution: deferred
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "`probe_answering_pipeline` can raise an exception outside its documented contract"
    location: "src/amoeba/runner/probes.py:68-90"
    resolution: fixed
  - id: F004
    severity: concern
    category: correctness
    summary: "`render_squadron_config` trusts its caller to validate the cap"
    location: "src/amoeba/runner/answering/inputs.py:42-49"
    resolution: fixed
  - id: F005
    severity: note
    category: error-handling-observability
    summary: "`prepare_scratch` is not atomic on I/O failure"
    location: "src/amoeba/runner/answering/inputs.py:70-76"
    resolution: deferred
  - id: F006
    severity: note
    category: consistency-rot
    summary: "Test imports depend on `sys.path` manipulation"
    location: "tests/live/conftest.py:15-20"
    resolution: deferred
  - id: F007
    severity: pass
    category: other
    summary: "Artifact parsers and pipeline names"
    location: "src/amoeba/runner/answering/artifacts.py"
---

# Review: code — slice 140

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Live harness kills only the launcher, so a timed-out run may keep spending

On timeout, `process.kill()` stops the `sq run` launcher but does not guarantee that the pipeline's model calls stop. The `Popen` call has no `start_new_session`, and there is no process-group kill and no `sq` cancel. `poll_run` is already used to watch the run, so the harness knows the run id. A hung run could therefore continue past the deadline, or leave orphaned children, in a tier that spends real money. Consider launching in its own process group and killing the group, or cancelling the run by id.

### [CONCERN] A unit-tier test shells out to `uv build`

This test runs a real `uv build --wheel` with a 300-second timeout inside the ordinary `tests/runner` tier. It depends on `uv` being installed and possibly on network or build-backend availability. A bare `pytest` run is then slow and can fail for environmental reasons. Mark it (for example `@pytest.mark.slow` or a packaging marker) and gate it in CI, or move it to its own tier.

### [CONCERN] `probe_answering_pipeline` can raise an exception outside its documented contract

The docstring says only `StartupFailedError` is raised. `answering_pipeline_path()` raises `FileNotFoundError` when the pipeline file is missing from the package, and that error propagates unwrapped. A broken install is exactly what a start-up probe should report uniformly. Catch `FileNotFoundError` and re-raise it as `StartupFailedError`, or document it in the docstring. No test covers this path.

### [CONCERN] `render_squadron_config` trusts its caller to validate the cap

`render_squadron_config` is public, but only `prepare_scratch` validates `max_cost_usd`. Called directly with `nan`, `inf` or a non-positive value, it silently writes a nonsensical cost cap. Move the validation into the renderer, or make the function private. Also, `render_question` rejects `\n` in `slice_label` but not `\r`.

### [NOTE] `prepare_scratch` is not atomic on I/O failure

Validation runs before any write, which is good. If a later write fails (disk full, permissions), the scratch directory is left half-populated. That is acceptable if the caller discards the directory on any exception, but it should be documented.

### [NOTE] Test imports depend on `sys.path` manipulation

The `sys.path` insertion and `# noqa: E402` exist only to import `tests/live_settings.py`. The unit test `test_live_tier_rules.py` imports `live_settings` as a top-level module, so it relies on pytest's rootdir or `pythonpath` configuration. Setting `pythonpath = ["tests"]` in the pytest config would remove the hack. Collection-time failure for missing variables is intentional and well documented.

### [PASS] Artifact parsers and pipeline names

The parsers return a typed value or a named problem and never raise on bad content. Every error branch is tested, including non-UTF-8 content, a directory in place of the file, and wrong types. Names are defined once in `pipeline_file.py`, and a test asserts the YAML uses exactly those names. The fixtures use the production shape. The code follows the Python rules (modern typing, `StrEnum`, specific exception catches with justifying comments).

### Run Digest

- Response length: 3771 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 47317 / 13347 / 33968 / 2273 / not computed
- Duration: 20.9 s
- Cost: $0.16 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
