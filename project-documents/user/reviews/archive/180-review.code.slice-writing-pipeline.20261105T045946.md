---
docType: review
layer: project
reviewType: code
slice: slice-writing-pipeline
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/180-slice.slice-writing-pipeline.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 6f22b2a71afe21df3811c023f48f90b24872fd64
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
diffTruncated: false
effort: xhigh
turns: 20
promptTokens: 664569
cachedTokens: 451994
cacheWriteTokens: 212565
completionTokens: 68253
durationSeconds: 292.3
costUsd: 0.331732
costBasis: provider
runId: run-20261104-p6-637a3f21
squadronVersion: 0.24.22
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: architectural-decay
    summary: "Slice-writing probe duplicates the answering probe"
    location: "src/amoeba/runner/probes.py:103-148"
  - id: F002
    severity: concern
    category: correctness
    summary: "Write prompt defines no reply for the \"already present under another name\" branch"
    location: "src/amoeba/runner/request_run/slice_writing.yaml:70-71"
  - id: F003
    severity: concern
    category: security-hygiene
    summary: "Write step relies on the prompt alone for the write ban against cross-project text"
    location: "src/amoeba/runner/request_run/slice_writing.yaml:22-28"
  - id: F004
    severity: note
    category: type-contract-debt
    summary: "`read_reply` accepts an `already_met` commit it has not checked exists"
    location: "src/amoeba/runner/request_run/reply.py#read_reply"
  - id: F005
    severity: note
    category: correctness
    summary: "`_require_single_line` rejects only CR and LF"
    location: "src/amoeba/runner/request_run/inputs.py#_require_single_line"
  - id: F006
    severity: note
    category: test-debt
    summary: "Launcher exit-grace and kill path has no default-tier test"
    location: "tests/live_harness.py#watch_run"
  - id: F007
    severity: note
    category: error-handling-observability
    summary: "Live harness hides the poll reason on a deadline"
    location: "tests/live/request_run/harness.py#_check_every_run"
  - id: F008
    severity: note
    category: architectural-decay
    summary: "Top-level slice-writing JSON fixtures are unused"
    location: "tests/fixtures/slice_writing/new_slice.json"
  - id: F009
    severity: note
    category: architectural-decay
    summary: "Probe and reader have no production caller yet"
    location: "src/amoeba/runner/probes.py:103"
  - id: F010
    severity: note
    category: test-debt
    summary: "Wheel test runs `uv build` in the default tier"
    location: "tests/runner/request_run/test_wheel_contents.py#test_wheel_lists_and_serves_the_pipeline_file"
  - id: F011
    severity: note
    category: consistency-rot
    summary: "Stale `noqa` on `watch_run`"
    location: "tests/live_harness.py:87"
  - id: F012
    severity: note
    category: documentation-drift
    summary: "Module docstrings are out of date"
    location: "tests/live_harness.py:1-6"
  - id: F013
    severity: pass
    category: correctness
    summary: "Reply parser, need renderer, and probe call shape match their tests"
    location: "src/amoeba/runner/request_run/reply.py#read_reply"
---

# Review: code — slice 180

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Slice-writing probe duplicates the answering probe

`probe_slice_writing_pipeline` repeats `probe_answering_pipeline` (`probes.py:74-100`) in structure: the pipeline-path lookup with its `FileNotFoundError` translation, the `run_cf(argv, partial(run, cwd=scratch), ...)` call, the `CfCallFailed` branch, and the non-zero-exit message. Only the path function, the extra options, and the label differ. Slice 184 will add a call site, and `probes.py` is already 270 lines. Extract one helper that takes the label, the path function, and the extra argv, and have both probes call it.

### [CONCERN] Write prompt defines no reply for the "already present under another name" branch

Lines 70-71 tell the agent that if an entry or slice plan already exists at the requests index under another name, it should "use it as it is." That adds nothing, but the reply rules (lines 86-90) define `new_slice` only "after adding a slice" and `already_met` only for a met need. Lines 72-74 also say the new index is one past the highest existing index, which conflicts with reusing an existing one. The model must guess between `new_slice` with a non-new index, `already_met` with an unrelated commit, or prose. `reply.py` accepts the first two as valid, so a wrong guess reaches the caller looking correct. No live case covers this branch; `tests/live/request_run/test_request_run.py` has first, second, and met cases only. Define the reply in the prompt and add a case, or record the branch as out of scope.

### [CONCERN] Write step relies on the prompt alone for the write ban against cross-project text

The write step declares no tool restriction, and `test_write_step_declares_no_tool_restriction` pins that. The model runs with the provider's full tools, including a shell. The `need.md` it reads is written by another project, and the only defence against instructions inside it is the prompt (lines 35-36 and 45-48). The commit step's `paths` limit what is committed, not what the agent runs. Nothing mechanical stops a prompt-injected need from leading to `git push`, edits to other tracked files, or `cf set`. The slice doc records this (`project-documents/user/slices/180-slice.slice-writing-pipeline.md:131,148`), and the archived design review raised it (`project-documents/user/reviews/archive/180-review.slice.slice-writing-pipeline.20261104T051110.md:72-80`). It is an accepted limit, not an oversight. The Project Manager should confirm that acceptance, or the design should narrow the tools.

### [NOTE] `read_reply` accepts an `already_met` commit it has not checked exists

The reader checks only that `commit` is 7 to 40 hex characters. A model can write a well-formed invented hash, and the reader returns `AlreadyMet`. The docstring defers existence to later slices, which is fine. Slice 184, the first production caller, must verify that the commit exists on the target and is an ancestor before it trusts the reply. The live met case checks ancestry only through the harness.

### [NOTE] `_require_single_line` rejects only CR and LF

`_LINE_BREAKS` is `frozenset("\r\n")`. The error says "single line," but `str.splitlines` also breaks on `\v`, `\f`, `\x1c`–`\x1e`, `\x85`, `\u2028`, and `\u2029`. A project id or label containing `\u2028` passes and breaks the header line of `need.md` in an editor or renderer. `test_inputs_render.py` covers only `\n` and `\r`. Use `len(value.splitlines()) == 1` and add cases for the other separators.

### [NOTE] Launcher exit-grace and kill path has no default-tier test

`_await_exit` and `PipelineRun.exit_code` (negative after a kill) are new in `watch_run`, and the answering path now runs through the same function with grace 0. Only the live tier exercises them, and that tier spends money and needs three variables. A test that stubs `poll_run` in `live_harness` and launches a short child process would cover the reported exit code and the kill after the grace, with no spend.

### [NOTE] Live harness hides the poll reason on a deadline

The first check raises `sq exited {exit_code}: {sq_output}` before anything else. On a deadline, `watch_run` sets the poll to `PollFailure("... did not finish in 900s")` and kills the launcher. The failure then reads as an sq exit and drops the poll reason. The later assertions already include `report`, which holds `pipeline.poll`. Include it in the first message too.

### [NOTE] Top-level slice-writing JSON fixtures are unused

`new_slice.json` has the same content as `new_slice/reply.json`, which `test_read_reply.py` reads through `CAPTURED / "new_slice"`. Nothing in the repo refers to the top-level file. `already_met.json` appears to be the same kind of duplicate. I confirmed it exists but did not open it. Delete the top-level files or point a test at them.

### [NOTE] Probe and reader have no production caller yet

`probe_slice_writing_pipeline` is called only from its test, and `read_reply` only from the live harness. The probe docstring says slice 184 calls the probe at start. Until then, a broken install of the pipeline file cannot stop the Runner. Confirm that slice 184's task list includes the call.

### [NOTE] Wheel test runs `uv build` in the default tier

`pyproject.toml` excludes only `tests/load` and `tests/live` (line 67), so this test runs on every bare `uv run pytest`. It runs `uv build --wheel` with a 300 s timeout, so the default unit tier now needs `uv` and a working hatchling build. Move it to its own marked tier, or accept the cost in writing.

### [NOTE] Stale `noqa` on `watch_run`

`# noqa: PLR0913` does nothing, because the ruff `select` list in `pyproject.toml` (line 50) does not include `PLR`. Remove it.

### [NOTE] Module docstrings are out of date

The docstring says the module runs the answering pipeline, but `watch_run` is now shared with the request tier. `src/amoeba/runner/request_run/pipeline_file.py` says the YAML "imports" these names. A YAML file cannot import, and the test only asserts that the file uses them. Update both.

### [PASS] Reply parser, need renderer, and probe call shape match their tests

From source: `read_reply` maps `FileNotFoundError` to `MISSING` and other `OSError`s to `MALFORMED`, and `_ReplyModel` ignores unknown keys. `probes.py` imports every name it uses. `run_cf` passes `timeout`, `stdin`, `capture_output`, and `text`, and maps timeouts and missing executables to the messages the probe tests match. The YAML's `paths`, `message`, `prompt_files`, and file-name values equal the `pipeline_file.py` constants. No line in the new or changed files exceeds 88 characters, per a grep with a known-length check.

### Run Digest

- Response length: 10401 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 664569 / 451994 / 212565 / 68253 / not computed
- Duration: 292.3 s
- Cost: $0.33 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
