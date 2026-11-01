---
docType: tasks
slice: answering-pipeline
project: amoeba
lld: user/slices/140-slice.answering-pipeline.md
dependencies: []
projectState: Initiatives 100 and 120 are complete (the Runner supervises one Squadron
  pipeline per slice). Nothing of slice 140 is built; `src/amoeba/runner/answering/`
  does not exist. `sq` is installed; whether it has the D8 capabilities is not known
  until Task 1.1 checks it.
dateCreated: 20261101
dateUpdated: 20261101
status: not_started
turns: 44
promptTokens: 1621448
cachedTokens: 1533710
cacheWriteTokens: 87692
completionTokens: 22698
durationSeconds: 163.6
costUsd: 0.731509
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 0.7315088999999998
    completionTokens: 22698
revision_number: 2
---

## Context Summary

- Working on the **answering-pipeline** slice (140), the first slice of initiative 140 (question answerer). It ships the two-step Squadron pipeline the answering run (144) launches, its input and output file contracts, a start-up probe, a live test tier, and the Squadron capability request.
- **Current state:** see `projectState`.
- **Dependencies:** none inside Amoeba. External: a Squadron release with the five D8 capabilities (LLD D8). Tasks that need a real run carry `BLOCKED:` lines naming the Squadron issue.
- **What this slice delivers:** `src/amoeba/runner/answering/` (`pipeline_file.py`, `inputs.py`, `artifacts.py`, `answering.yaml`), `probe_answering_pipeline` in `runner/probes.py`, `tests/live/`, the Squadron issue, and contract text.
- **Next planned slice:** 141 (question record). 142 wires the probe into start-up; 144 launches the pipeline.

**Branch:** all implementation happens on `140-slice.answering-pipeline`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/140-slice.answering-pipeline.md` at the named decision (D1–D10) or section. Source paths are relative to `src/amoeba/` unless they start with `tests/` or `docs/`. Keep source files near 300 lines and functions near 50. Run `uv run ruff format .`, `uv run ruff check .` and `uv run pyright` before each commit.

**Order:** work tasks in file order. If a task is `BLOCKED:`, continue with the next task whose dependencies are all checked off. The unit-tested Amoeba side (Sections 2–5) does not wait on Squadron.

**Commit cadence:** commit at each `**Commit**:` marker only.

## 1. Squadron capability request and slice plan

- [x] **1.1 Check what the installed `sq` can do** (effort 1)
  - [x] Read the LLD D8 (five capabilities). In a temporary directory outside the repo, write a one-step dispatch pipeline using a file-content key, and run `sq run <file> --validate`.
  - [x] Note under this task, as a dated observation with the `sq --version` output, which capabilities the installed `sq` lacks. Task 1.2 copies it into the issue. Do not branch on the version anywhere in code.
  - [x] Success: the observation names each of the five capabilities as present or missing, from a command run in this task.
  - **Observation (20261101, `sq --version` printed `squadron 0.24.12`).** Command run: `sq run <tmp>/t.yaml --validate` on a one-step dispatch pipeline carrying `allowed_tools: []`, `prompt_file: question.md` and `reply_file: out.json`; it printed `Pipeline 't' is valid.` and exited 0. Reading the installed dispatch step (`pipeline/steps/dispatch.py`), `expand` forwards only `prompt`, `model`, `pre_emption_fragment`, `allowed_tools`, `feedback`.
    - 1 file content in a prompt: **missing** (no such key; `prompt_file` was accepted but ignored).
    - 2 earlier step's reply in a later prompt: **missing** (no such key forwarded).
    - 3 reply and delivered prompt to files: **missing** (no such keys forwarded).
    - 4 hard no-tools guarantee: **missing**. Command run: a one-step dispatch with `allowed_tools: []`, model alias `haiku` (SDK session mode), prompt asking it to read `pyproject.toml` with a tool. `sq run <file> haiku -vv` completed (`profile: sdk-session`, project rules loaded) and the reply gave the file's real first line, `[project]`. The step ran with file access instead of failing.
    - 5 strict step validation: **missing** (unknown keys `prompt_file` and `reply_file` validate).

- [x] **1.2 File the Squadron issue** (effort 2)
  - [x] Repository: `ecorkran/squadron` (its package metadata names `https://github.com/ecorkran/squadron/issues`).
  - [x] Title: "Isolated file-in, file-out dispatch steps (for Amoeba's answering pipeline)". Body: the five capabilities of LLD D8 as requirements, each with its acceptance behavior as written there, and the note that the syntax is Squadron's to choose. Include Task 1.1's observation. Include no secrets or local paths.
  - [x] File it with `gh issue create --repo ecorkran/squadron`.
  - [x] Success: `gh issue view <n> --repo ecorkran/squadron` shows all five capabilities. The issue number is noted in the task file under this task.
  - Filed 20261101: `ecorkran/squadron#284` (https://github.com/ecorkran/squadron/issues/284); `gh issue view` shows all five capabilities.

- [x] **1.3 Name the issue in the slice plan** (effort 1)
  - [x] In `user/architecture/140-slices.question-answerer.md`, replace "(Squadron issue: not yet filed)" on entry 140 with the issue number, and name it as a dependency on entry 144 beside "Any Squadron issue 140 files".
  - [x] Success: the issue number appears on entries 140 and 144 of the slice plan.

**Commit**: `docs: file squadron capability request and name it in the 140 slice plan`

## 2. The constants module

- [ ] **2.1 Create `runner/answering/__init__.py` and `pipeline_file.py`** (effort 2)
  - [ ] Define once, as `Final` constants: the pipeline file name, the step names, the param names (`answer-model`, `check-model`), and every input and output file name (`question.md`, `passages.md`, `rules`, `.squadron.toml`, `answer.json`, `answer.prompt.md`, `check.json`, `check.prompt.md`).
  - [ ] `answering_pipeline_path()` returns the absolute `Path` of the shipped YAML via `importlib.resources`. It raises `FileNotFoundError` when the file is absent; no fallback path.
  - [ ] Success: pyright strict passes. The constants hold no behavior to test; the names-match test (Task 5.2) and the path test (Task 5.2) exercise them. Later tasks import the names from here.

## 3. Input contract

- [ ] **3.1 `QuestionInput` and `question.md` rendering** (effort 2)
  - [ ] In `runner/answering/inputs.py`: frozen dataclass `QuestionInput(slice_label, question)` as in LLD "API Contracts". `render_question(question) -> str` produces the exact `question.md` format of LLD D3: heading, `slice:` line, blank line, question text verbatim.
  - [ ] Raise `ValueError` for an empty `slice_label` or an empty `question`. Text is never trimmed or escaped.
  - [ ] Success: rendering a question containing blank lines, `{model}` and a leading `#` returns it unchanged after the header.

- [ ] **3.2 Tests for rendering** (effort 1)
  - [ ] `tests/runner/answering/test_inputs_render.py`: exact-string assertion against the D3 format; multi-line question verbatim; braces and markdown headings preserved; both `ValueError` cases.
  - [ ] Success: tests pass.

- [ ] **3.3 `prepare_scratch`** (effort 3)
  - [ ] Add `prepare_scratch(directory, question, passages_markdown, max_cost_usd)` per LLD D7 and "API Contracts". Writes `question.md`, `passages.md` (as given, byte for byte), an empty `rules/` directory and `.squadron.toml` with `"pipeline.max_cost_usd"` and `rules_dir` set to the absolute `rules` path, using the constants.
  - [ ] Raise `ValueError` (programming error, not a model outcome) for: a directory that does not exist, a directory that is not empty, `max_cost_usd <= 0`, an empty `passages_markdown`. No default for any argument.
  - [ ] Success: the directory listing after a call is exactly the four entries.

- [ ] **3.4 Tests for `prepare_scratch`** (effort 2)
  - [ ] `tests/runner/answering/test_prepare_scratch.py`: the four entries exist and `rules/` is empty; `passages.md` equals the input bytes including trailing newline and non-ASCII text; `.squadron.toml` parses with `tomllib` to the expected cap and an absolute `rules_dir` equal to `<directory>/rules`; each refusal raises and leaves the directory unchanged.
  - [ ] Success: tests pass.

**Commit**: `feat: add answering constants, input contract and scratch preparation`

## 4. Artifact contract

- [ ] **4.1 Reply types** (effort 2)
  - [ ] In `runner/answering/artifacts.py`: frozen dataclasses `ProposedAnswer(answer, cited)`, `AnswererDecline(reason)`, `CheckReply(verdict, reason: str | None)`, `ArtifactProblem(kind, detail)`; a `ProblemKind` enum (`missing`, `malformed`) and a `Verdict` enum (`yes`, `no`). `AnswerReply` is the union of the first two. Shapes per LLD D6.
  - [ ] Success: pyright strict passes; no string literal for `answer`, `decline`, `yes` or `no` outside the enum or one parse table.

- [ ] **4.2 `read_answer`** (effort 3)
  - [ ] `read_answer(directory) -> AnswerReply | ArtifactProblem` reads the answer reply file (name from the constants) and parses it as one JSON object. No extraction of its own (LLD D6).
  - [ ] `kind` matched case-insensitively after trimming. Unknown keys ignored. Malformed (with a detail naming the cause) for: not one JSON object; `kind` not `answer` or `decline`; empty answer text; `cited` not a list of strings; decline with no or empty reason. A missing file is `missing`.
  - [ ] Never raises for bad file content (unreadable bytes included). Does not check cited ids against anything and does not require `cited` to be non-empty.
  - [ ] Success: each rule above returns the named problem; a valid answer and a valid decline return the typed value.

- [ ] **4.3 Tests for `read_answer`** (effort 2)
  - [ ] `tests/runner/answering/test_read_answer.py`, one test per rule above plus: array instead of object, `kind: " ANSWER "`, extra keys ignored, empty `cited` list accepted, `cited: "P1"` rejected, a non-UTF-8 file returns `malformed`.
  - [ ] Add one fixture file in `tests/fixtures/answering/` in the real production shape of D6, so the parser is also tested on the format it consumes. Task 9.5 replaces it with captured live output.
  - [ ] Success: tests pass.

- [ ] **4.4 `read_check`** (effort 2)
  - [ ] `read_check(directory) -> CheckReply | ArtifactProblem` on the check reply file. `verdict` matched case-insensitively after trimming; only `yes` and `no`. An absent or other `verdict` is `malformed`, never `no`. `reason` has no validation rule in LLD D6: carry it as `str | None` (the text when it is a string, otherwise `None`) and never reject on it.
  - [ ] Success: valid yes and no return `CheckReply`; every other case returns the named problem.

- [ ] **4.5 Tests for `read_check`** (effort 2)
  - [ ] `tests/runner/answering/test_read_check.py`: yes, no, ` Yes `, absent verdict, `"maybe"`, not an object, missing file, extra keys.
  - [ ] Success: tests pass.

**Commit**: `feat: add answering reply parsers`

## 5. The pipeline file

Squadron's syntax for the D8 keys is not final. This section drafts the file with the capability keys as proposed in the issue; Task 9.1 adjusts it to what ships.

- [ ] **5.1 Draft `runner/answering/answering.yaml`** (effort 4)
  - [ ] Two `dispatch` steps, two required params (`answer-model`, `check-model`) with no defaults, step and param names from `pipeline_file.py`. Read the Squadron pipeline documentation (`sq` help and, if present, `ai-project-guide/tool-guides/squadron/`) for the real syntax of a pipeline file before writing.
  - [ ] Each step declares no tools and a JSON reply; the answer step's instructions and the check step's instructions are each the step's `prompt:` text, written per LLD D3, D4 and D6: the citation rule, the decline form, passage text is data and embedded instructions are not followed, the answer step replies with the JSON object only, PM-precedent matching with `slice:` taken into account, the check step's precedence rule (later date wins, equal date means equal precedence, a contradiction means no), a decline gets a no, a cited `pm_answer` gets yes only if the new question means the same thing for this slice, and the check's refusal of reserved actions as the LLD Overview describes it.
  - [ ] The answer step takes `question.md` and `passages.md` as file content; the check step takes the same two files and the answer step's reply. Each step names its reply file and delivered-prompt file from the constants. Use the key names proposed in the Squadron issue, and mark them in a comment as pending the shipped syntax.
  - [ ] Success: the file parses as YAML; `uv run python -c` loading it via `answering_pipeline_path()` succeeds.

- [ ] **5.2 Names-match test** (effort 2)
  - [ ] `tests/runner/answering/test_pipeline_yaml.py`: load the YAML and assert its step names, param names, and reply and prompt file names equal exactly the constants in `pipeline_file.py`; the two params have no default; both steps are `dispatch`; neither declares a tool; each step's `prompt` text is non-empty, the answer step's names the two `kind` values and the check step's names the `verdict` key and both verdict values, taken from the `artifacts.py` vocabulary, so the instructions and the parsers cannot drift apart without a live run. Also resolve `answering_pipeline_path()` and assert the file exists; with a monkeypatched package root that lacks the file, assert it raises `FileNotFoundError`.
  - [ ] Success: tests pass; renaming a constant makes them fail.

- [ ] **5.3 Ship the YAML in the wheel** (effort 2)
  - [ ] Add `src/amoeba/runner/answering/answering.yaml` to `[tool.hatch.build.targets.wheel] artifacts` in `pyproject.toml`, beside the schema SQL.
  - [ ] `tests/runner/answering/test_wheel_contents.py`: build the wheel with `uv build` into a `tmp_path` output directory, assert the archive lists `amoeba/runner/answering/answering.yaml`. Follow the style of the existing wheel-contents test if one exists under `tests/`.
  - [ ] Success: the test passes. Create no files outside `tmp_path`.

**Commit**: `feat: add the answering pipeline file and ship it in the wheel`

## 6. The start-up probe

- [ ] **6.1 `probe_answering_pipeline`** (effort 3)
  - [ ] In `runner/probes.py`, add `probe_answering_pipeline(settings, run)` per LLD D9. It runs `sq run <answering_pipeline_path()> --validate` once with the same detached-stdin, captured-output, timeout-bounded call as other `sq` and `cf` commands (reuse `run_cf` from `cf_call.py`; do not duplicate its timeout and error handling), with `ProcessSettings.sq_timeout_seconds` and a temporary working directory.
  - [ ] Exit 0 returns. Any other exit, a timeout or a missing `sq` raises `StartupFailedError` naming the command, the exit code and `output_head` of the output. Build the argv from `SQ_EXECUTABLE`.
  - [ ] Do not call it from start-up; 142 does (LLD D9). Do not compare `sq` versions.
  - [ ] If `probes.py` would pass about 300 lines, put the new function in `runner/answering/probe.py` and re-export nothing; callers import it from where it lives.
  - [ ] Success: pyright strict passes.

- [ ] **6.2 Tests for the probe** (effort 2)
  - [ ] Add to `tests/runner/test_probes.py` (or a new file beside it, selectable with `-k answering`): a stub `run` that exits 0 passes; exit 1 raises and the message holds the command, `1` and the output head; a `TimeoutExpired` raises naming the timeout; `FileNotFoundError` raises naming `sq`. Assert the argv, the timeout value and the temporary working directory.
  - [ ] Success: `uv run pytest tests/runner/test_probes.py -k answering -v` passes.

**Commit**: `feat: add the answering pipeline start-up probe`

## 7. Live tier scaffolding

- [ ] **7.1 `tests/live/` and its exclusion** (effort 2)
  - [ ] Add `--ignore=tests/live` to `addopts` in `pyproject.toml`, beside `tests/load`, and extend the comment there.
  - [ ] `tests/live/conftest.py`: session fixtures reading `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL` and `AMOEBA_LIVE_MAX_COST_USD`, read by one pure function `read_live_settings(environ)`. If any is unset, it raises `pytest.UsageError` at collection naming the variable; no skip, no default. A cost value that is not a positive number fails the same way. A fourth variable, `AMOEBA_LIVE_SDK_MODEL`, is read only by Task 9.4's own test, which fails naming it when unset; the other live tests do not need it (an addition to LLD D10's three variables, recorded in Task 8.1).
  - [ ] A helper `run_pipeline(directory, ...)` that mints a run id (reuse `mint_run_id`), launches `sq run <answering_pipeline_path()> --run-id <id> -p answer-model=<a>,check-model=<c>` with the scratch directory as working directory, and waits with `sq runs wait <id> --json` and a bounded timeout, returning the parsed outcome. Prefer the existing `poll_run` from `amoeba.process` over a second parser.
  - [ ] Success: `uv run pytest` (bare) collects nothing from `tests/live`; `uv run pytest tests/live` with the variables unset fails naming the first missing one.

- [ ] **7.2 Tests for the tier's own rules** (effort 2)
  - [ ] `tests/runner/answering/test_live_tier_rules.py`: call `read_live_settings` with plain dicts: all three set returns the values; each one missing raises naming that variable; a non-numeric or non-positive cost raises naming the cost variable.
  - [ ] Success: tests pass without a real `sq` or any spend.

**Commit**: `test: add the live test tier scaffolding`

## 8. Process contract text

- [ ] **8.1 Document the pipeline in `docs/process-contract.md`** (effort 2)
  - [ ] Add a section after "Resolutions and resumption" (or beside "Squadron shapes") covering: the shipped pipeline and its path function; the launch argv shape and working directory; the input files and the `question.md` and `passages.md` formats (copy the formats from LLD D3); the output files and the reply JSON shapes (D6); the scratch directory contents including `.squadron.toml` and why `rules_dir` is set (D7); the probe and that it runs at start only when a project has an answerer section, wired by 142 (D9); the live tier and its variables (D10's three, plus `AMOEBA_LIVE_SDK_MODEL` for the SDK-alias test).
  - [ ] Do not write the dated `sq` observation yet; Task 9.5 adds it.
  - [ ] Success: each item above is present; the section links to the LLD rather than restating its rationale.

- [ ] **8.2 CHANGELOG** (effort 1)
  - [ ] Add an `### Added` entry under `[Unreleased]` in `CHANGELOG.md`, one or two lines in the style of the existing slice entries: the shipped answering pipeline file, input and reply contracts, the probe and the live tier, naming that real runs need a Squadron with the D8 capabilities.
  - [ ] Success: entry present.

- [ ] **8.3 Verify the Amoeba side** (effort 1)
  - [ ] Run once each: `uv run ruff format .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. Walk the LLD "Verification Walkthrough" steps 1, 2 and 5.
  - [ ] Success: the commands exit 0. Section 9 holds the criteria gated on Squadron; its tasks stay unchecked until unblocked.

**Commit**: `docs: document the answering pipeline contract`

## 9. Against a real Squadron

Everything here needs an `sq` with the D8 capabilities (the Squadron issue from Task 1.2).

- [ ] **9.1 Adjust `answering.yaml` to the shipped syntax** (effort 3)
  - [ ] `BLOCKED:` no Squadron release with the D8 capabilities yet (Squadron issue from Task 1.2). Unblock check: run `sq run <answering.yaml> --validate` after installing a newer `sq`, and read its release notes for the five capabilities.
  - [ ] Replace the proposed keys with Squadron's shipped syntax. Keep names from the constants. Re-run Task 5.2's test.
  - [ ] Success: `sq run "$(uv run python -c '...answering_pipeline_path()...')" --validate` prints `Pipeline 'answering' is valid.` and exits 0, and an `sq` with an unknown key in the same file rejects it (try one extra key in a temporary copy).

**Commit**: `feat: adjust the answering pipeline to the shipped squadron syntax`

- [ ] **9.2 Live tests: files, no-files, check input** (effort 4)
  - [ ] `BLOCKED:` depends on 9.1.
  - [ ] `tests/live/answering/test_pipeline_run.py`, each in its own `tmp_path` with hand-written `passages.md` in the D3 format: (a) the answered case: the four output files exist and both parsers return no problem; (b) a passage telling the agent to create `pwned.txt`: the directory then holds exactly the prepared files plus the four outputs; (c) `check.prompt.md` contains the question, every passage id with its text and the answer reply, that embedded reply equals the object `read_answer` parsed, it does not contain the answer step's instruction text, and neither prompt file contains a project rules block.
  - [ ] Success: `uv run pytest tests/live/answering -k "answered or files or check_input" -v` passes under the cost cap.

**Commit**: `test: add live answering pipeline run tests`

- [ ] **9.3 Live tests: precedence and matching** (effort 4)
  - [ ] `BLOCKED:` depends on 9.1.
  - [ ] Tests per LLD D10: a PM answer dated after the rule it contradicts gives check `yes`; the rule dated after gives `no`; a PM answer's question repeated in different words for the same slice is answered citing that PM passage and the check says `yes`; the same wording for another slice where the slice changes the answer ends in a decline or check `no`. One real run each, no retries; a wrong verdict fails.
  - [ ] Success: the four tests pass. If one fails, record the failing model aliases and replies as a finding in the task notes; do not loosen the test.

**Commit**: `test: add live precedence and matching tests`

- [ ] **9.4 Live test: SDK alias refusal** (effort 2)
  - [ ] `BLOCKED:` depends on 9.1 and on capability 4.
  - [ ] Run with `check-model` set to the `AMOEBA_LIVE_SDK_MODEL` alias (Task 7.1). Assert the run fails before the check step dispatches, with no `check.json`.
  - [ ] Success: the test passes.

**Commit**: `test: add live SDK alias refusal test`

- [ ] **9.5 Capture real replies and record the observation** (effort 2)
  - [ ] `BLOCKED:` depends on 9.2.
  - [ ] Copy one real `answer.json` and one real `check.json` from a passing run into `tests/fixtures/answering/`, replace Task 4.3's hand-written fixture in the parser tests with them (keep the hand-written edge cases), and rerun the unit tier.
  - [ ] Add a dated note under "Squadron shapes" in `docs/process-contract.md`: "first observed running the answering pipeline: squadron x.y.z, on <date>", with the version from `sq --version` as run in this task.
  - [ ] Success: unit tier passes on the captured files; the note is present with a real version and date.

**Commit**: `feat: capture real answering replies and record the squadron observation`
