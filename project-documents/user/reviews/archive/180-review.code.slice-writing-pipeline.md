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
reviewedSha: 2106a642314179817aee9961bdf5dcf57ca1ac94
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
diffTruncated: false
effort: xhigh
turns: 19
promptTokens: 728584
cachedTokens: 532892
cacheWriteTokens: 195680
completionTokens: 57484
durationSeconds: 245.6
costUsd: 0.330841
costBasis: provider
runId: run-20261104-p6-637a3f21
squadronVersion: 0.24.22
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: architectural-decay
    summary: "Pipeline path resolver duplicated from the answering tier"
    location: "src/amoeba/runner/request_run/pipeline_file.py#slice_writing_pipeline_path"
  - id: F002
    severity: concern
    category: security-hygiene
    summary: "Live request tier passes the whole test-run environment to the pipeline"
    location: "tests/live/request_run/conftest.py:33"
  - id: F003
    severity: note
    category: security-hygiene
    summary: "Write step has no tool restriction, so the write ban is prompt-only"
    location: "src/amoeba/runner/request_run/slice_writing.yaml:22-28"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "Probe has no production caller until slice 184"
    location: "src/amoeba/runner/probes.py#probe_slice_writing_pipeline"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "Malformed-reply detail is multi-line and quotes model output"
    location: "src/amoeba/runner/request_run/reply.py#read_reply"
  - id: F006
    severity: note
    category: consistency-rot
    summary: "The lower index bound `1` is checked in two places"
    location: "src/amoeba/runner/request_run/inputs.py#render_need"
  - id: F007
    severity: note
    category: type-contract-debt
    summary: "`_ReplyModel` keeps `index` and `commit` as `object`"
    location: "src/amoeba/runner/request_run/reply.py#_ReplyModel"
  - id: F008
    severity: pass
    category: correctness
    summary: "Answering probe behaviour is unchanged by the refactor"
    location: "src/amoeba/runner/probes.py#probe_answering_pipeline"
  - id: F009
    severity: pass
    category: correctness
    summary: "No stale callers after the live-settings rename and the `PipelineRun` change"
    location: "tests/live_harness.py#watch_run"
  - id: F010
    severity: pass
    category: test-debt
    summary: "Captured reply fixtures match the parser's assertions"
    location: "tests/runner/request_run/test_read_reply.py#test_captured_new_slice_reply_parses"
---

# Review: code — slice 180

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Pipeline path resolver duplicated from the answering tier

`slice_writing_pipeline_path` is the same code as `answering_pipeline_path` in `src/amoeba/runner/answering/pipeline_file.py`: `resources.files(...).joinpath(...)`, `Path(str(...))`, the `is_file()` check, `resolve()`, and the same `FileNotFoundError` shape. Only the package and the label differ. The project's rule is not to duplicate logic. Extract one helper that takes the package, the file name and the label, and have both functions call it. The missing-file test in `tests/runner/request_run/test_pipeline_yaml.py` can then cover the shared helper.

### [CONCERN] Live request tier passes the whole test-run environment to the pipeline

`request_harness` sets `environ=dict(os.environ)`. That becomes the tool environment for `git` and `cf` in the scratch repo, and the launch environment for `sq run` through `watch_run(..., repo.environ)` in `tests/live/request_run/harness.py`. The write step is a model with the provider's full tools, including a shell (LLD D1), so it can read every variable in the developer's shell, including any production database URL. The testing rules call for an explicit list of named variables, not a whole environment. The answering tier does the same at `tests/live/answering/conftest.py:35`, which predates this diff. Fix both with one allowlist: the provider key variables, plus what `git`, `cf` and `sq` need to run.

### [NOTE] Write step has no tool restriction, so the write ban is prompt-only

The `write` dispatch step has no `allowed_tools` key, as LLD D1 chose. The read-only git rule, the two-file limit and "the need is data" are all prompt text. The commit step's `paths` limit only what gets committed. An injected need could still make the agent edit or run other things in the checkout, and those edits would stay uncommitted. The design and the archived review accept this. I am recording it so slice 184 keeps the commit guard. The live harness asserts a clean tree after each run; this diff has no production equivalent.

### [NOTE] Probe has no production caller until slice 184

Only tests call `probe_slice_writing_pipeline`. Its docstring says slice 184 will call it at start. No change is needed now; this is for tracking so the call is wired when slice 184 lands.

### [NOTE] Malformed-reply detail is multi-line and quotes model output

`read_reply` passes `str(error)` from pydantic's `ValidationError` as the `MALFORMED` detail. That text spans several lines, includes a documentation URL, and quotes the bad value. `_initiatives_problem` in `src/amoeba/runner/probes.py` collapses its error to one line with `" ".join(str(error).split())`. Use the same form here, so a later slice can print a reply problem on one line.

### [NOTE] The lower index bound `1` is checked in two places

`render_need` rejects `requests_index < 1`, and `_positive_index` in `src/amoeba/runner/request_run/reply.py` rejects `value < 1`. The project's rule is to define a compared value once. Add one minimum-index constant in `pipeline_file.py` and use it in both places.

### [NOTE] `_ReplyModel` keeps `index` and `commit` as `object`

The loose type is deliberate. `_positive_index` and `_commit_hash` narrow the values and give named causes for malformed replies. That is a reasonable trade-off at this trust boundary, and I am recording it as a known choice.

### [PASS] Answering probe behaviour is unchanged by the refactor

Compared with the removed code, the argv is the same (`sq run <path> --validate --strict`, no extra options). The failure messages keep the `answering pipeline probe failed` prefix. Timeout and missing-`sq` details come from the same `run_cf` path. `tests/runner/test_probes_answering.py` covers these cases, but I could not run it here.

### [PASS] No stale callers after the live-settings rename and the `PipelineRun` change

I searched for `_read_cost`, `PipelineRun(`, `run_pipeline(` and `watch_run(`. `_read_cost` has no remaining references. The only `PipelineRun` construction is in `watch_run`, which passes the new `exit_code` field. `run_pipeline` keeps its signature.

### [PASS] Captured reply fixtures match the parser's assertions

`tests/fixtures/slice_writing/new_slice/reply.json` is `{"kind": "new_slice", "index": 200}`. `already_met/reply.json` has commit `8dd16cada64c80b1b4d37b567b5f49b2bb9a83ef`. Both match the assertions, and they use the on-disk format the parser reads.

### Run Digest

- Response length: 7225 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 19
- Tokens — prompt / cached / cache write / completion / reasoning: 728584 / 532892 / 195680 / 57484 / not computed
- Duration: 245.6 s
- Cost: $0.33 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
