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
reviewedSha: a148a509fba8dab151c90daa03e7c987e7fdc41c
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 192093
cachedTokens: 95627
cacheWriteTokens: 96460
completionTokens: 5278
durationSeconds: 41.3
costUsd: 0.449035
costBasis: provider
runId: run-20261101-p56-29332206
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 7.1 success check can't run before any live test exists"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:160-164"
  - id: F002
    severity: concern
    category: coverage-gap
    summary: "\"Resolves from an installed wheel\" is only partly tested"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:136-139"
  - id: F003
    severity: concern
    category: scope-creep
    summary: "Task 5.2 asserts more than any success criterion asks for"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:132-134"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Several steps dictate implementation the slice leaves open"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:146-149"
  - id: F005
    severity: note
    category: traceability
    summary: "`AMOEBA_LIVE_SDK_MODEL` goes beyond LLD D10"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:162"
  - id: F006
    severity: note
    category: sequencing
    summary: "Several tasks have no `BLOCKED:` line and rely on the section note"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:189-191"
  - id: F007
    severity: pass
    category: coverage
    summary: "Coverage of the gated criteria"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:193-227"
  - id: F008
    severity: pass
    category: coverage
    summary: "Coverage of the ungated criteria and test-with ordering"
    location: "project-documents/user/tasks/140-tasks.answering-pipeline.md:47-187"
  - id: F009
    severity: pass
    category: verification
    summary: "Referenced existing symbols exist, and no load-test requirement applies"
    location: "src/amoeba/runner/cf_call.py:39"
---

# Review: tasks — slice 140

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 7.1 success check can't run before any live test exists

Task 7.1 builds the settings check as "session fixtures" and says it "raises `pytest.UsageError` at collection". It then requires that `uv run pytest tests/live` with the variables unset "fails naming the first missing one".

- A session fixture only runs when a test requests it. No live test exists until 9.2, which is blocked on Squadron. The 7.1 check therefore has nothing to fail, and a junior implementer can't satisfy it.
- A fixture doesn't run at collection time anyway. The collection-time failure in LLD D10 needs a hook such as `pytest_configure` or `pytest_collection_modifyitems` in `tests/live/conftest.py`.

Say which hook calls `read_live_settings`. Alternatively, add a placeholder test under `tests/live` so the success check can run. The criterion "fails with the variable's name when a model or cost variable is unset" depends on this.

### [CONCERN] "Resolves from an installed wheel" is only partly tested

The slice's Technical Requirements say: "The wheel built by `uv build` contains `answering.yaml`, and `answering_pipeline_path()` resolves to it from an installed wheel." Task 5.3 only checks that the archive lists the file. It never installs the wheel or resolves the path from it. Nothing else in the breakdown covers this.

Either add a step that installs the built wheel into a temporary venv and calls `answering_pipeline_path()`, or narrow the claim in the slice design. Without one of these, a wheel could ship the YAML at the right path while `importlib.resources` still fails to find it.

### [CONCERN] Task 5.2 asserts more than any success criterion asks for

The criterion is that the YAML's param, step and file names equal the constants. Task 5.2 adds several checks beyond that:

- Prompt-text content assertions: the answer step names both `kind` values, and the check step names `verdict` and both verdict values.
- A monkeypatched-package-root test for the `FileNotFoundError` path.
- Assertions that the two params have no default, that both steps are `dispatch`, and that neither declares a tool.

The prompt-text assertions are a reasonable drift guard, but no success criterion requires them. The `FileNotFoundError` test exists only because Task 2.1 invented that behavior. Cut the monkeypatched test and the prompt-content assertions. Keep the names-match check and the structural assertions that map to LLD D1 and D2.

### [CONCERN] Several steps dictate implementation the slice leaves open

Task 6.1 prescribes reusing `run_cf` and building argv from `SQ_EXECUTABLE`. Both exist, in `src/amoeba/runner/cf_call.py:39` and `src/amoeba/process/sq_outcome.py:27`. It then adds a conditional "if `probes.py` would pass about 300 lines, put it in `probe.py`" branch. The LLD only says the probe sits beside `probe_sq` in `runner/probes.py`. Pick one location and drop the hedge.

Task 7.2 imports `read_live_settings` from `tests/live/conftest.py` into a test under `tests/runner/answering/`. Importing from a conftest is fragile. Put the pure function in a small helper module instead.

Task 5.3 says "follow the style of the existing wheel-contents test if one exists". Check whether one exists and name it, or drop the clause.

### [NOTE] `AMOEBA_LIVE_SDK_MODEL` goes beyond LLD D10

LLD D10 and Verification Walkthrough step 4 name three environment variables. Tasks 7.1, 8.1 and 9.4 add a fourth, `AMOEBA_LIVE_SDK_MODEL`. It does trace to the success criterion that sets `check-model` to an SDK alias, and 8.1 records it in the process contract. The LLD walkthrough's export line is now incomplete, so update the LLD to match.

### [NOTE] Several tasks have no `BLOCKED:` line and rely on the section note

Section 9 tasks 9.1, 9.2 and 9.3 carry `BLOCKED:` lines. Tasks 9.4 and 9.5 name their dependencies. 9.4 says it depends on 9.1 and capability 4, and 9.5 depends on 9.2. This is acceptable.

### [PASS] Coverage of the gated criteria

All seven Squadron-gated criteria map to tasks:

- The four output files and the parsers: 9.2(a).
- The `pwned.txt` case: 9.2(b).
- The `check.prompt.md` contents: 9.2(c).
- Precedence in both directions, and both matching cases: 9.3.
- SDK alias refusal: 9.4.
- Validation of the shipped file and rejection by an `sq` without the capabilities: 9.1.

### [PASS] Coverage of the ungated criteria and test-with ordering

Probe failure paths are covered by 6.1 and 6.2. The Squadron issue and its number in the slice plan are covered by 1.1–1.3. The unit-test requirements are covered by 3.2, 3.4, 4.3 and 4.5. The process contract text and CHANGELOG are covered by 8.1 and 8.2. Each test task immediately follows its implementation task. Commit markers sit at the end of every section, and the file respects the project's no-merge rule.

### [PASS] Referenced existing symbols exist, and no load-test requirement applies

The following exist: `run_cf`, `output_head` (`cf_call.py:31`), `SQ_EXECUTABLE`, `poll_run` (`process/sq_outcome.py:220`), `mint_run_id` (`runner/launch.py:34`), `probe_sq` (`runner/probes.py:40`), `ProcessSettings.sq_timeout_seconds` (`process/settings.py:106`), `tests/runner/test_probes.py`, and the `tests/load` ignore with its comment in `pyproject.toml:60-62`. The slice restates no NFR, so no load-test or CI-gating task is needed.

### Run Digest

- Response length: 6588 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 192093 / 95627 / 96460 / 5278 / not computed
- Duration: 41.3 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
