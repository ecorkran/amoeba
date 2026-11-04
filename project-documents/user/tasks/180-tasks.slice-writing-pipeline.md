---
docType: tasks
slice: slice-writing-pipeline
project: amoeba
lld: user/slices/180-slice.slice-writing-pipeline.md
dependencies:
- 100
- 120
- 140
projectState: Initiatives 100, 120 and 140 are complete and merged. `src/amoeba/runner/answering/`
  holds the shipped `answering.yaml`, its `pipeline_file.py` constants and `artifacts.py`
  reply parsers; `runner/probes.py` holds `probe_answering_pipeline`; `tests/live/`
  holds the answering live tier, whose settings are read in `tests/live/conftest.py`.
  Nothing under `src/amoeba/runner/request_run/` exists. The installed Squadron (0.24.17
  when the LLD was written) lacks the run I/O directory, the guarded commit step and
  `--max-cost` (LLD D8).
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
turns: 19
promptTokens: 1045492
cachedTokens: 958525
cacheWriteTokens: 86935
completionTokens: 21795
durationSeconds: 160.2
costUsd: 0.661905
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.6619049
    completionTokens: 21795
---

## Context Summary

- Working on the **slice-writing-pipeline** slice (180), the first slice of initiative 180 (program coordination). It ships the Squadron pipeline a request run (slice 184) launches in a provider's checkout: a write step and a guarded commit step that either add one slice entry to the provider's requests initiative or report that the provider already meets the need.
- **Current state:** see `projectState`.
- **Dependencies:** 122's probe pattern (`StartupFailedError`, `run_cf`, `output_head`), 140's pipeline-file pattern (`answering/pipeline_file.py`, `artifacts.py`, `probe_answering_pipeline`) and the live tier. External: a Squadron release with capabilities 1 to 3 of LLD D8 (new issue filed in Task 1, plus the open `ecorkran/squadron#241`).
- **What this slice delivers:** `src/amoeba/runner/request_run/` (`pipeline_file.py`, `inputs.py`, `reply.py`, `slice_writing.yaml`), `probe_slice_writing_pipeline` in `runner/probes.py`, the request live tier `tests/live/request_run/`, the Squadron issue, a dependency-register row (S16), and process-contract text.
- **Next planned slice:** 181 (program record). 184 wires the probe at start-up and launches the pipeline.

**Branch:** Task 1 edits planning and notes documents, so it runs and commits on the target (`cf config get git.integration_branch`; empty means `main`), with no branch. After its commit, create `180-slice.slice-writing-pipeline` from the target and do Task 2 onward there. No task merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/180-slice.slice-writing-pipeline.md` at the named decision (D1 to D10) or section. Source paths are relative to `src/amoeba/` unless they start with `tests/`, `docs/` or `project-documents/`. Follow `.claude/rules/python.md`: ruff and strict pyright, no silent fallbacks, every `try/except` justified. Read each file before editing it. Keep source files near 300 lines and functions near 50. Mirror the answering equivalents named in each task rather than inventing new shapes.

**Order and blocking:** work tasks in file order. Tasks 1 to 8 need no new Squadron, no model and no keys. Section 9 needs a Squadron release with D8. No `BLOCKED:` line is pre-written: Task 9.1 runs the check and, only when it fails for one of the reasons listed there, writes a line starting `BLOCKED:` under itself naming that reason and the issue numbers from Task 1.2 and `ecorkran/squadron#241`, leaves the task unchecked and stops. Later Section 9 tasks name their prerequisite task and start once it is checked. A session that finds a `BLOCKED:` line deletes it and runs the check again; it continues only if the check now passes. Whether a release has the capabilities is decided by running `sq`, never by its version number.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before markers that follow Python changes.

---

## 1. Squadron capability request and slice plan

- [x] **1.1 Check what the installed `sq` can do** (effort 1)
  - [x] Read LLD D8 (three capabilities). In a temporary directory outside the repo, write a one-step pipeline and run `sq run <file> --validate --strict` on it: once with a `commit` step carrying `paths` and `message`, where one `paths` entry contains the run param written `{requests-index}` (as the slice-plan glob does; try this form first), and once with `--io-dir <dir>` and `--max-cost 1` added. Also run `sq run --help` and `sq --version`.
  - [x] Note under this task, as a dated observation with the `sq --version` output, which of the three capabilities are present or missing. Task 1.2 copies it into the issue. Do not branch on the version anywhere in code.
  - [x] Success: the observation names each capability as present or missing, from commands run in this task.
  - **Observation (20261104, `sq --version`: `squadron 0.24.20`):** capability 1 (run I/O directory) missing: `--io-dir` exits 2, `No such option: --io-dir`. Capability 2 (guarded commit step) missing: `--validate --strict` exits 1, `Unknown step type 'commit'`; param substitution in `paths` could not be tested. Capability 3 (cost cap) missing: `--max-cost` exits 2, `No such option: --max-cost`; `ecorkran/squadron#241` is open.
- [x] **1.2 File the Squadron issue** (effort 2)
  - [x] Repository `ecorkran/squadron`. Title: "Run a pipeline in a project checkout without dirtying it (for Amoeba's slice-writing pipeline)". Body: capabilities 1 and 2 of LLD D8 as requirements, each with the acceptance behavior written there; capability 3 is the open `ecorkran/squadron#241`, linked, not re-requested. Add that the commit step's `paths` must accept the run's params, because the slice-plan glob contains the requests index. State that the syntax is Squadron's to choose. Include Task 1.1's observation. No secrets or local paths.
  - [x] If Task 1.1 found a capability already present, request only the missing ones.
  - [x] File it with `gh issue create --repo ecorkran/squadron`.
  - [x] Success: `gh issue view <n> --repo ecorkran/squadron` shows the requested capabilities. Note the issue number in this file under this task.
  - **Issue filed:** `ecorkran/squadron#292` (all three capabilities missing, so capabilities 1 and 2 requested, 3 linked to #241).
- [x] **1.3 Name the issue in the slice plan** (effort 1)
  - [x] In `user/architecture/180-slices.program-coordination.md`, name the new issue and `#241` on entry 180 (beside "Any capability `sq` or `cf` lacks") and replace "the run I/O directory and guarded commit issue from 180's design (D8)" on entry 184's dependency line with the issue number.
  - [x] Success: both numbers appear on entries 180 and 184.

**Commit**: `docs: name slice-writing squadron issues in the program slice plan`

- [x] **1.4 Add the register row** (effort 1)
  - [x] In `user/notes/001-squadron-dependencies.amoeba.md`, add row S16 in the table's style: the new issue and `#241`, blocking slice 184, with the observation date. Rewrite the "Net:" line below the table: its "nothing here blocks Amoeba" claim is false once S16 exists, so say that S16 gates slice 184 (request runs) and that nothing else here blocks Amoeba.
  - [x] Success: both numbers appear in row S16.

**Commit**: `docs: add slice-writing squadron request to the dependency register`

## 2. Package and names

- [x] **2.1 Package and constants** (effort 2)
  - [x] Create `runner/request_run/__init__.py` (docstring only) and `runner/request_run/pipeline_file.py`, mirroring `runner/answering/pipeline_file.py`.
  - [x] Define once: the pipeline file name `slice_writing.yaml`; the param names `requests-index` and `model`; the step names (write, commit); the input file `need.md`; the output files `reply.json` and `write.prompt.md`; the commit paths per LLD D2 (the initiative-plan glob, and the slice-plan glob built from the `requests-index` param name); the fixed commit message `docs: add request slice to the requests initiative plan`; the proposed `sq run` option names for the run I/O directory (`--io-dir`) and the cost cap (`--max-cost`), provisional until Task 9.1; the probe's nominal cost cap, 1 (USD).
  - [x] Do not add `slice_writing_pipeline_path()` yet; Task 5.1 adds it beside the YAML.
  - [x] Success: `uv run pyright` passes. No Python file outside `pipeline_file.py` repeats these literals once later tasks land (each imports them); `slice_writing.yaml` repeats them, and Task 5.5 asserts the two agree.

## 3. Input contract

- [x] **3.1 `inputs.py`: `RequestInput`, rendering and directory preparation** (effort 3)
  - [x] `RequestInput` frozen dataclass with `asking_project_id`, `asking_slice_label`, `requests_index`, `need` (LLD "API Contracts").
  - [x] `render_need(request)` returns the `need.md` text in the LLD D4 format: heading `# Request`, the `requested by:` line, the `requests initiative:` line, a blank line, the need verbatim.
  - [x] `prepare_request_directory(directory, request)` requires an existing, empty directory and writes only `need.md`. It raises `ValueError` when the directory does not exist or is not empty (mirror `prepare_scratch`).
  - [x] Raise `ValueError` (as `answering/inputs.py` does) for: a blank need, a requests index below 1, and a project id or slice label that is blank or contains a newline.
  - [x] Success: `render_need` output matches the D4 layout exactly; after `prepare_request_directory` the directory holds exactly one file.
- [x] **3.2 Tests for rendering and preparation** (effort 2)
  - [x] Create `tests/runner/request_run/__init__.py`, `test_inputs_render.py` and `test_prepare_directory.py`, mirroring `tests/runner/answering/test_inputs_render.py` and `test_prepare_scratch.py`.
  - [x] Rendering: the exact rendered text; the need kept verbatim (multi-line, braces and markdown preserved); each `ValueError` case above.
  - [x] Preparation: only `need.md` is written, with `render_need` content; refusals for a missing directory, a non-empty directory (left as it was) and each invalid request field.
  - [x] Success: the tests pass.

**Commit**: `feat: add slice-writing request input contract and directory preparation`

## 4. Reply contract

- [x] **4.1 `reply.py`: types and `read_reply`** (effort 3)
  - [x] Define frozen dataclasses `NewSlice(index: int)`, `AlreadyMet(commit: str)` and `ReplyProblem(kind, detail)` with a two-value `StrEnum` kind (`missing`, `malformed`), and the `kind` values `new_slice` and `already_met` as a `StrEnum`. Model on `answering/artifacts.py`.
  - [x] `read_reply(directory)` reads `reply.json` (name from `pipeline_file.py`) and applies LLD D7 exactly. It raises `ValueError` when `directory` is not an existing directory (a programming error, as in Task 3.1; model output cannot cause it). Otherwise it never raises for file content: an existing directory with no `reply.json` is `missing`; anything else wrong is `malformed` with a detail naming the cause. Unknown keys are ignored; `kind` is trimmed and matched case-insensitively.
  - [x] `index`: an integer, or a string of decimal digits after trimming; positive; a boolean is rejected. `commit`: a string of 7 to 40 hexadecimal characters after trimming, returned lower case.
  - [x] `malformed` covers: not one JSON object (including undecodable bytes), a `kind` other than the two, a `new_slice` with no or bad `index`, an `already_met` with no or bad `commit`. Nothing defaults.
  - [x] Success: `uv run pyright` passes; the function checks shape only (no index-is-new or commit-exists check).
- [x] **4.2 Tests for `read_reply`** (effort 3)
  - [x] `tests/runner/request_run/test_read_reply.py`, mirroring `tests/runner/answering/test_read_answer.py`. Use the real reply format the parser will consume (the LLD D7 JSON), written as files. These fixtures are hand-written from D7; the live cases (Task 9.4) parse real replies with `read_reply`, and Task 9.5 adds captured ones.
  - [x] Valid: both shapes; `kind` with different case and surrounding spaces; unknown keys ignored; index as an integer and as a padded digit string; commit of 7 and of 40 characters, upper case normalized to lower.
  - [x] `missing`: an existing directory with no `reply.json`. `ValueError`: a directory that does not exist, and a path that is a file. `malformed`: empty file, invalid JSON, a JSON array, invalid UTF-8, no `kind`, unknown `kind`, `new_slice` with no index, index `0`, negative, `true`, a float, non-digit string; `already_met` with no commit, 6 characters, 41 characters, non-hex, a number.
  - [x] A `ReplyProblem` carries a non-empty `detail` in every case.
  - [x] Success: the tests pass.

**Commit**: `feat: add slice-writing reply reader`

## 5. The pipeline file

- [x] **5.1 Path function and pipeline skeleton** (effort 2)
  - [x] Add `slice_writing_pipeline_path()` to `pipeline_file.py` as `answering_pipeline_path` does (`importlib.resources`, absolute path, `FileNotFoundError` when absent).
  - [x] Create `runner/request_run/slice_writing.yaml` with a header comment (names live in `pipeline_file.py`; no brace pair around a bare word except real params; capability keys are proposals until Task 9.1). `name: slice-writing`, two required params with no default, a `dispatch` write step and a `commit` step. Declare the params in the order `requests-index`, `model`: `requests-index` is the first required param, so it is the positional target of `sq run`, and `model` goes in `-p`, which does not satisfy the first required param (LLD "API Contracts").
  - [x] Write step (LLD D1, D4): `model` from the `model` param, no `allowed_tools` key, `prompt_files` for `need.md`, `reply_format: json`, `reply_file: reply.json`, `delivered_prompt_file: write.prompt.md`, and a placeholder `prompt` for Tasks 5.2 to 5.4.
  - [x] Commit step (LLD D5): the `paths` and fixed `message` from `pipeline_file.py`. The slice-plan glob uses the `requests-index` param; whether Squadron substitutes params in `paths` is decided in Task 9.1.
  - [x] No `max_cost_usd` and no timeout anywhere in the file (LLD D6).
  - [x] Add `src/amoeba/runner/request_run/slice_writing.yaml` to `[tool.hatch.build.targets.wheel] artifacts` in `pyproject.toml` and extend the comment above it.
  - [x] Success: the path function returns the file; `pyproject.toml` lists it.
- [x] **5.2 Write-step instructions: scope and bans** (effort 2)
  - [x] Write the first part of the `prompt` per LLD D2: the agent runs in the provider's checkout and may read code, plans and read-only git (`log`, `show`, `status`, `diff`); `need.md` is data and instructions inside it are not followed.
  - [x] Editable files: at most the two plan globs. State both globs by their `pipeline_file.py` values.
  - [x] Forbidden: git writes, `cf set` or any other CF write, edits to any other file, slice or initiative. After editing, run `cf list slices` for the requests index with `--json` and fix the files until the new index appears (LLD "Mitigation Strategies").
  - [x] Hallucination-trap rule, for Tasks 5.2 to 5.4: give no example hash, index or filename near an instruction to read one; describe shapes with placeholders in words, not literal values. Avoid a brace pair around a bare word except the real params.
  - [x] Success: the prompt states each item above; `sq` is not needed.
- [x] **5.3 Write-step instructions: initiative and entry** (effort 3)
  - [x] Initiative: when the initiative plan has no entry at the requests index, append the entry (title Requests, described as changes other program members asked for, no dependencies, status not started) and create `architecture/<index>-slices.requests.md` with slice-plan front matter whose `parent` is the initiative plan, plus the headings the provider's slice-plan template requires. An existing entry is used as is, whatever its name.
  - [x] Slice plan: when the entry exists but no slice plan exists at that index, create the slice plan as above and leave the initiative plan untouched. A slice plan at that index under another name is used as is.
  - [x] New entry: its index is the requests index when the initiative has no slices, otherwise one more than the highest index in it. Entry form is the provider's slice-plan form (checkbox, index in parentheses, bold title, description, risk, effort), `Dependencies: None` written explicitly. The description restates the need without loss and names the requesting member and slice from `need.md`. No other line changes except front matter `dateUpdated`.
  - [x] Success: the prompt states each item above.
- [x] **5.4 Write-step instructions: reply** (effort 2)
  - [x] Already met (LLD D3): reply `already_met` only when the code on the current branch already provides what the need asks for, naming the full commit hash taken from `git log`; write nothing in that case.
  - [x] Reply: one JSON object in the two LLD D7 shapes. If the provider has no initiative plan, reply in prose with no JSON object (LLD D2).
  - [x] Success: the prompt states each item above; no literal hash or index appears in it.
- [x] **5.5 Tests for the pipeline file** (effort 3)
  - [x] `tests/runner/request_run/test_pipeline_yaml.py`, mirroring `tests/runner/answering/test_pipeline_yaml.py`: step names and order; both params required with no default, and `requests-index` declared before `model`; the write step's model is the `model` param; its reply, delivered-prompt and prompt-file names equal the constants; no `allowed_tools` key; the commit step's `paths` equal the two constants; no `max_cost_usd` or timeout key anywhere.
  - [x] Prompt hygiene: every brace pair around a bare word (no spaces or quotes) in the prompt is a real param name (JSON shapes in the prompt are allowed); the prompt contains no literal 7-to-40-character hexadecimal string; it names both glob constants.
  - [x] Package path test: `slice_writing_pipeline_path()` is absolute, ends in `amoeba/runner/request_run/slice_writing.yaml`, and raises `FileNotFoundError` when the file is missing (monkeypatch as the answering test does).
  - [x] `tests/runner/request_run/test_wheel_contents.py`: build a wheel as `tests/runner/answering/test_wheel_contents.py` does; assert it lists `amoeba/runner/request_run/slice_writing.yaml`; extract it to a temporary directory and run `sys.executable -I -c` code that puts that directory first on `sys.path`, imports `slice_writing_pipeline_path` and prints it; assert the path is inside the extracted directory and the file exists.
  - [ ] Success: the tests pass.

**Commit**: `feat: add slice-writing pipeline file and wheel packaging`

## 6. Start-up probe

- [ ] **6.1 `probe_slice_writing_pipeline`** (effort 2)
  - [ ] In `runner/probes.py`, add `probe_slice_writing_pipeline(settings, run)` per LLD D9. Argv: `sq run <path> --validate --strict`, then the I/O-directory option with a temporary directory and the cost-cap option with the nominal cap (all from `pipeline_file.py`). Run once from another temporary directory, bounded by `settings.sq_timeout_seconds`, through `run_cf` as `probe_answering_pipeline` does.
  - [ ] Raise `StartupFailedError` for a non-zero exit (naming the command, exit code and `output_head`), a timeout, a missing `sq`, and a missing pipeline file, each with its own "slice-writing pipeline probe failed" message. Do not refactor `probe_answering_pipeline` and do not compare versions.
  - [ ] Do not wire it into start-up; 184 does.
  - [ ] Success: `uv run pyright` passes; `probes.py` stays readable (split a helper only if it passes ~300 lines).
- [ ] **6.2 Stub-`sq` tests** (effort 2)
  - [ ] `tests/runner/test_probes_request_run.py`, mirroring `tests/runner/test_probes_answering.py` (reuse its stub approach; import the stub if it is importable, else copy only the small stub class).
  - [ ] Cover: exit 0 passes with one call; the exact argv (path, `--validate`, `--strict`, I/O option with an existing temporary directory during the call, cost-cap option with the nominal value); `cwd` is a temporary directory, not the caller's; a non-zero exit raises `StartupFailedError` naming the exit code and output head; a timeout, a missing `sq` and a missing pipeline file each raise `StartupFailedError`.
  - [ ] Success: the tests pass.

**Commit**: `feat: add slice-writing pipeline start-up probe`

## 7. Live-tier settings

- [ ] **7.1 Scope the answering settings to `tests/live/answering`** (effort 2)
  - [ ] `tests/live/answering/conftest.py` already exists and holds the `live_harness` fixture, which takes a `live_settings` fixture. Move the collection-time `read_live_settings(os.environ)` call and the `live_settings` fixture from `tests/live/conftest.py` into that file, above `live_harness`, unchanged except for the imports it needs (`read_live_settings`). Keep in `tests/live/conftest.py` only what both tiers need (the `sys.path` entry for `tests/`).
  - [ ] Success: `uv run pytest tests/live/answering --collect-only` with the answering variables set collects the same tests as before; with `AMOEBA_LIVE_ANSWER_MODEL` unset it still fails naming the variable. `tests/live/conftest.py` no longer reads any answering setting.
- [ ] **7.2 Request live settings** (effort 2)
  - [ ] Add a settings reader for `AMOEBA_LIVE_REQUEST_MODEL` and `AMOEBA_LIVE_REQUEST_MAX_COST_USD` beside `tests/live_settings.py` (a new module, reusing `require_variable`; make the private `_read_cost` take the variable name so both readers share the positive-finite cost rule, behavior unchanged; no defaults, no skips).
  - [ ] Create `tests/live/request_run/__init__.py` and `tests/live/request_run/conftest.py` that reads them at collection and exposes a session fixture.
  - [ ] Success: collecting `tests/live/request_run` with a variable unset fails with `pytest.UsageError` naming it.
- [ ] **7.3 Tests for the settings rules** (effort 2)
  - [ ] `tests/runner/request_run/test_live_tier_rules.py`, mirroring `tests/runner/answering/test_live_tier_rules.py`: all set returns the values; each missing variable is named; one invalid cost is rejected naming `AMOEBA_LIVE_REQUEST_MAX_COST_USD`. The shared blank, zero, negative, `nan` and `inf` rules are already tested by the answering tier's rule tests, which must still pass.
  - [ ] Add one test that `tests/live/conftest.py` source no longer contains the answering variable names (read the file text).
  - [ ] Success: the tests pass and the answering tier's own rule tests still pass.

**Commit**: `test: add request live-tier settings and scope answering settings`

## 8. Process contract and validation

- [ ] **8.1 Process contract section** (effort 2)
  - [ ] In `docs/process-contract.md`, add `### The slice-writing pipeline` after the answering run section and before "Context Forge shapes", in the style of "The answering pipeline". Cover: the shipped file and path function; the two steps; the two required params; the file names; the `need.md` format; the two reply shapes and `read_reply`'s three results; the guarantee a completed run leaves (at most one commit touching only the two plan files, no change left in the checkout; bounded to the checkout and target, LLD D1); the `already_met` rule that the target's HEAD must not move (enforced by 184); no wall-clock bound; the probe and that 184 wires it.
  - [ ] State the launch argv from the LLD "API Contracts" and mark it **provisional until Task 9.2 confirms it against the shipped Squadron**.
  - [ ] Success: the section names every item above and refers to the LLD for rationale. The dated `sq` observation is added in Task 9.5.
- [ ] **8.2 Full validation pass** (effort 1)
  - [ ] Run `uv run ruff format .`, `uv run ruff check .`, `uv run pyright`, then `uv run pytest tests/runner/request_run tests/runner/answering tests/runner/test_probes_request_run.py tests/runner/test_probes_answering.py -q`, then the full `uv run pytest -q`. Run each once and read its output. Fix import-boundary failures (`tests/test_import_boundaries.py`) by importing only public names, not by editing the test.
  - [ ] Success: all pass. A failure unrelated to this slice is noted under this task with its test name.

**Commit**: `docs: add slice-writing pipeline to process contract`

## 9. Real runs against a Squadron release with D8

- [ ] **9.1 Check the release and finalize the pipeline** (effort 3)
  - [ ] From a temporary directory, run `sq run <slice_writing.yaml> --validate --strict` with the I/O-directory option (a temporary directory) and the cost-cap option. Then:
    - Exit 0: the capabilities are present; continue.
    - Output names an unknown `commit` step or an unknown option: the release lacks a capability. Write the `BLOCKED:` line (see "Order and blocking") and stop.
    - `sq` is not found, or the command times out: write the `BLOCKED:` line with that error and stop.
    - The file is rejected for another reason (a key or value in our file): fix the file as the message says and run again. If the only fix is a `paths` entry without the requests-index param, because `paths` does not accept params, do not widen the guard: write the `BLOCKED:` line naming that reason.
  - [ ] Change `slice_writing.yaml`, the option-name and commit constants in `pipeline_file.py`, the probe argv, and the tests of Tasks 5.5 and 6.2 to the shipped syntax. Re-run those tests.
  - [ ] Success: `sq run <file> --validate --strict` with the probe's options prints `Pipeline 'slice-writing' is valid.` and exits 0; the unit tier passes.

**Commit**: `feat: finalize slice-writing pipeline syntax against shipped squadron`

- [ ] **9.2 Live validation test and final launch argv** (effort 2)
  - [ ] Prerequisite: 9.1 is checked.
  - [ ] Live validation test `tests/live/request_run/test_validate.py`: the real `sq` validates the shipped file with the probe's argv (exit 0); a copy with one unknown step key is rejected by `--validate --strict` (non-zero exit).
  - [ ] Collection reads the request settings (Task 7.2), which this test does not use. Set both variables inline on the pytest command only, any model value and any positive cap (for example `AMOEBA_LIVE_REQUEST_MODEL=unused AMOEBA_LIVE_REQUEST_MAX_COST_USD=1 uv run pytest ...`). Do not export them: Task 9.4 relies on the session environment holding a real alias.
  - [ ] Remove the "provisional" marking from the launch argv in `docs/process-contract.md`, restating the argv `sq` accepted.
  - [ ] Success: the live validation test passes; the contract shows the final argv.

**Commit**: `test: add live slice-writing validation test and finalize launch argv in contract`

- [ ] **9.3 Live harness and scratch repository** (effort 4)
  - [ ] Prerequisite: 9.2 is checked.
  - [ ] Under `tests/live/request_run/`, add a harness mirroring `tests/live/answering/harness.py` and `tests/live_harness.py` (read both first). Build a scratch git repo with a minimal initiative plan, one existing initiative with one slice, and one small source file a "met" need can point to. Its target is its default branch (the throwaway registry sets no `git.integration_branch`); the harness holds that branch name in one constant and uses it in every git call and assertion.
  - [ ] Register the repo as a CF project with `cf init --lite` in a throwaway registry (`CONTEXT_FORGE_DATA_DIR` under `tmp_path`). Run `cf init` before the first commit and commit everything it wrote with the fixture files, so the tree is clean when the run starts. Record the start commit after setup.
  - [ ] Create an empty run I/O directory under `tmp_path`, call `prepare_request_directory`, and launch with the finalized argv from the repo as working directory, passing a run id from `mint_run_id` as `--run-id`. Wait for the process, then call `poll_run` on that id (as `tests/live_harness.py` does). On a non-zero exit raise with the head of the `sq` output.
  - [ ] The harness chooses a requests index that does not collide with the fixture's initiative. After every run it asserts: `poll_run` returns a `RunPoll` (not a `PollFailure`) with outcome `COMPLETED`; `write.prompt.md` in the I/O directory contains the need text; the checkout contains no file from the I/O directory; `git status --porcelain` is empty and HEAD is on the target; there is at most one new commit above the start commit, touching only files that match the two plan globs; `cf list initiatives --json -a` exits 0 and parses (the whole-plan read the provider's next tick makes).
  - [ ] Success: `uv run pyright` passes on the harness and `uv run pytest tests/live/request_run --collect-only` (variables set inline as in Task 9.2) collects without error. The harness's own checks are exercised by the cases in Task 9.4.
- [ ] **9.4 Live cases** (effort 4)
  - [ ] Prerequisite: 9.3 is checked. These cases spend money and need a real SDK alias: if `AMOEBA_LIVE_REQUEST_MODEL` is not set in the shell's own environment (not inline for an earlier task), write the `BLOCKED:` line naming it and stop. Each case runs once; a wrong outcome fails the test; nothing retries. Every case also passes the harness's every-run checks (Task 9.3).
  - [ ] Run with `--basetemp=/tmp/request-live` (LLD Verification Walkthrough step 4) so each case's repo and I/O directory stay on disk for Task 9.5. Note the path under this task.
  - [ ] Case 1, first request, no requests initiative: afterwards the initiative plan lists the initiative at the given index; `cf list slices <index> --json` shows exactly one entry, at the index `read_reply` returns as `NewSlice`; the target has exactly one new commit touching exactly the two plan files.
  - [ ] Case 2, run in the repository case 1 left, with a different need: the reply names the next index; `cf list slices <index> --json` shows both entries; the new commit touches only the slice plan file; the first entry's lines and every other initiative's entries are unchanged.
  - [ ] Case 3, a need the scratch source already meets: `read_reply` returns `AlreadyMet`; `git merge-base --is-ancestor <commit> <target>` succeeds; the target's HEAD did not move.
  - [ ] Success: the three tests pass. If one fails, record the model alias, the reply and the repo state as a finding under this task; do not loosen the test.

**Commit**: `test: add live slice-writing request tests`

- [ ] **9.5 Capture real replies and record the observation** (effort 2)
  - [ ] Prerequisite: 9.4 is checked.
  - [ ] Copy one real `new_slice` and one real `already_met` `reply.json` from the kept I/O directories under the Task 9.4 basetemp into `tests/fixtures/slice_writing/`, add parser tests that read them (keep the hand-written edge cases), and rerun the unit tier. If a captured reply does not parse as its kind, fix `read_reply` to accept the real shape and keep the captured file as the fixture.
  - [ ] Add a dated note under "Squadron shapes" in `docs/process-contract.md`: "first observed running the slice-writing pipeline: squadron x.y.z, on <date>", with the version from `sq --version` as run in this task, beside the answering pipeline's note.
  - [ ] Success: the unit tier passes on the captured files; the note holds a real version and date.
- [ ] **9.6 Final check** (effort 1)
  - [ ] Prerequisite: 9.5 is checked.
  - [ ] Check the LLD's Verification Walkthrough steps 1 to 6 as written (steps 3 and 4 with the finalized options), plus `uv run ruff format .`, `uv run ruff check .`, `uv run pyright` and the full `uv run pytest -q`. Confirm `cf list projects` with `CONTEXT_FORGE_DATA_DIR` unset shows no scratch project.
  - [ ] Success: every step gives the expected result; results are noted under this task.

**Commit**: `test: capture real slice-writing replies and record the squadron observation`
