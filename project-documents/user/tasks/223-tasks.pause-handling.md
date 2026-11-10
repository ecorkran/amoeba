---
docType: tasks
slice: pause-handling
project: amoeba
lld: user/slices/223-slice.pause-handling.md
dependencies:
- 222-slice.store-config-and-set-up
projectState: Slices 221 and 222 are merged. `src/amoeba` holds `answering/`, `upstream/`,
  `config/`, `store/` (migration 001), `operations/` (member resolution, `set_up`,
  `answering_for`) and the `amoeba set_up` CLI. No pause handling exists. Nobody has
  run Amoeba.
dateCreated: 20261107
dateUpdated: 20261110
status: in_progress
turns: 11
promptTokens: 429930
cachedTokens: 379625
cacheWriteTokens: 50287
completionTokens: 13982
durationSeconds: 89.3
costUsd: 0.379261
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.37926139999999997
    completionTokens: 13982
---

# Tasks: Pause Handling

## Context Summary

- Working on slice 223 (design: `user/slices/223-slice.pause-handling.md`; decisions D1 to D15 are cited below by number).
- Adds `amoeba handle_pause <run_id>` (answers an agent question and resumes the run, or records it as waiting on the PM) and `amoeba answer` (PM answer, then resume). Both share one resume (D8).
- New modules: `store/questions.py`, `store/schema/002_pause_handling.sql`, `upstream/squadron/run_file.py`, `operations/{processes,deps,pause_context,answering_run,resume,pause_models,pause_eligibility,pause_existing,handle_pause,answer}.py` (deliberate departure from the design's single `handle_pause.py`: the project's ~300-line file limit applies to it, and the design's public API `operations.handle_pause.handle_pause` and the `SkipReason` and `HandlePauseResult` import paths are unchanged through re-exports). Changed: `config/home.py`, `answering/`, `cli/main.py`.
- Import direction: `cli → operations → store, config, upstream, answering`. `processes.py` imports nothing from Amoeba. `run_file.py` imports nothing from `answering`. `answering` imports nothing from `store`, `config` or `operations`.
- Every closed vocabulary is a `StrEnum`; no config key has a default in code; no silent fallbacks (`sdk` is never assumed for `execution_mode`).
- Checks, from the repo root: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`. "Checks pass" means all four.
- Take the audit's names (`user/analysis/220-analysis.code-audit.md`, sections Slice 182, Live tests) and 222's actual module paths over the design's sketches where they differ.
- Work on branch `223-slice.pause-handling`. Commit only at `**Commit**:` markers. Update this file through the `task-checker` agent. Do not merge or push.
- Next slices: 224 status and decisions, 225 scenario A trial, 226 MCP server.

## 0. Setup

- [x] **0.1 Create the branch**
  - [x] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [x] Confirm the working tree is clean and you are on the target
  - [x] `git checkout -b 223-slice.pause-handling {target}`
  - [x] Success: `git branch --show-current` prints `223-slice.pause-handling`

- [x] **0.2 Confirm 222 and locate inputs**
  - [x] Confirm `src/amoeba/store/`, `src/amoeba/config/` and `src/amoeba/operations/` exist and `amoeba set_up` runs; if not, write `BLOCKED: slice 222 not merged` under this task and stop
  - [x] Open the audit's Slice 182 section and Live tests section. Note under this task: the 182 take and rewrite groups (for `program_concept` and `program_members`, D11), the list of `waits on 223` test files and the commit to restore them from
  - [x] Find the module of each of: `poll_run`, `RunSummary`, `PollFailure`, `read_answer`, `read_check`, `decide_answer`, `evaluate_gate`, `prepare_scratch`, `compose_instructions`, `read_committed_sources`, `read_target`, `sources_reason`, `SourcesProblem`, `answering_for`, `resolve_member`, `project_of`, `members_of`, `programs`, `DeclineReason`, `QuestionState`, `ResumeOutcome`, `PassageRef`, `AnsweringEvidence`, `run_cf` (note "absent" for any that don't exist); note import paths
  - [x] Also note: the import path and signatures of the kept launch helpers in `upstream/squadron/launch.py` (`mint_run_id`, `build_argv`, `spawn`, `LaunchLogs`, `LaunchError`, `stderr_tail`; 221 task 2.5 keeps them) and of `resume_argv` in `upstream/squadron/resume_argv.py`; if any is absent, write `BLOCKED: slice 221 did not keep <name>` and stop; where `DEFAULT_TARGET_BRANCH` now lives (`upstream/context_forge/target_read.py`, moved unchanged by 221 task 2.8); the import paths the kept live files use for `SQ_EXECUTABLE`, `RunOutcome`, `RunOutcomeDocument`, `PollFailure`, `RunPoll`, `poll_run`, `QUESTION_TAIL_CHARS`; `sq --version` (0.24.24 or later; the live tests and the `--no-pause-hook` flag need it)
  - [x] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [x] Success: a note lists the audit groups, the restore commit, each import path and the baseline result
  - Notes (recorded 20261110):
    - Branch `223-slice.pause-handling` already existed at main's HEAD (a506eab), tree clean; target is `main` (`git.integration_branch` empty).
    - Audit Slice 182 groups. Take (copy from `182-slice.program-concept-as-a-source`): `answering.yaml` kind sentences, `passages.py` kinds and rendering, `program_passages.py`, `source_reads.py` renames, tests `test_passages.py`, `test_pipeline_yaml.py`, `test_program_passages.py`. Rewrite: `program_sources.py` (keep `_read_concept_file`, `_within_limit`, `without_path`, `_read_from_asker`, `SourcesProblem` kinds), the `sources.py` program hunk, `launch.py` program field, `program_rig.py`, `test_program_sources.py`, program section of `test_sources.py`, `test_program_passages_load.py`. Drop: no-program path (`program=None` optionality, commit `6c2499b` and its baseline tests).
    - Live tests that `wait on 223`: `tests/live/answering/stage_harness.py` and `tests/live/answering/test_answering_run.py`; restore from commit `ed6041a` (verified to exist).
    - Import paths (all under `src/amoeba/`): `poll_run`, `PollFailure`, `RunPoll` (type alias `RunOutcomeDocument | PollFailure`), `RunOutcome`, `RunOutcomeDocument`, `SQ_EXECUTABLE`, `QUESTION_TAIL_CHARS` in `upstream/squadron/run_outcome.py` (`poll_run(run_id, *, timeout_seconds)`); `RunSummary`, `decide_answer`, `sources_reason` in `answering/decide.py`; `read_answer`, `read_check` in `answering/artifacts.py`; `evaluate_gate(question, prior_answers: int, *, answer, settings)` and `compose_instructions(question, answer)` in `answering/gate.py`; `prepare_scratch(directory, question, passages_markdown, max_cost_usd)` in `answering/inputs.py`; `read_committed_sources` in `answering/source_reads.py`; `SourcesProblem` in `answering/passages.py`; `DeclineReason`, `PassageRef` (fields id, source, question_id, date; no `kind`), `AnsweringEvidence` in `answering/values.py`; `read_target` and `DEFAULT_TARGET_BRANCH` ("main") in `upstream/context_forge/target_read.py`; `project_of` in `upstream/context_forge/project_of.py`; `run_cf` in `upstream/context_forge/cli_call.py`; `answering_for` in `operations/member_answering.py`; `resolve_member` in `operations/members.py`; `members_of` and the other program reads are functions in the module `store/programs.py` (there is no `programs` function); `QuestionState`, `ResumeOutcome` in `store/vocabulary.py`; `mint_run_id(now)`, `build_argv(pipeline, run_id, params, *, target_key=TARGET_PARAM_KEY)`, `spawn(argv, checkout, logs, popen)`, `LaunchLogs(stdout, stderr)`, `LaunchError(failure, detail)`, `stderr_tail(path)` in `upstream/squadron/launch.py`; `resume_argv(run_id, instructions)` in `upstream/squadron/resume_argv.py`. All present; none absent.
    - Note: `upstream/squadron/launch.py` already defines `TARGET_PARAM_KEY = "slice"`; task 4.2 must not create a second constant of that name with a different meaning (decide there).
    - `sq --version`: `squadron 0.24.25` (>= 0.24.24).
    - Baseline: ruff format clean (164 files), ruff check clean, pyright 0 errors, pytest 756 passed.

## 1. Store and migration (D4, D10)

- [x] **1.1 Migration `002_pause_handling.sql`**
  - [x] Create `store/schema/002_pause_handling.sql`: `ALTER TABLE … ADD COLUMN` only, all nullable. `questions`: `slice_label`, `source_commit`, `passages`, `waiting_detail`, `evidence`. `answers`: `cited`, `resume_detail`, `resume_log`, `resume_at` (D10 table)
  - [x] Set `EXPECTED_SCHEMA_VERSION` to 2
  - [x] Success: a version-1 store opens and migrates to version 2 with data intact
  - Note: `docs/store-contract.md` already updated with the nine columns (the contract-docs test requires it); task 8.3 re-checks it.

- [x] **1.2 Migration tests**
  - [x] Extend the store tests: build a version-1 store with a question and an answer row, migrate, assert the rows survive and the nine columns exist and are null
  - [x] Success: tests pass; the existing SQL `CHECK`-vs-enum pin tests still pass

- [x] **1.3 JSON column serializers**
  - [x] In `store/question_json.py` add one serializer and one parser each for `passages` (array of `PassageRef`: id, kind, source, date), `evidence` (`AnsweringEvidence`: proposed answer, citations, check verdict and reason) and `cited` (array of passage ids). Use `PassageRef` and `AnsweringEvidence` from the modules recorded in task 0.2; if 221 has no such type, define it in `answering/values.py` (which `store` may already import)
  - [x] Parsers raise a typed `StoreError` subclass naming the column on bad JSON; no silent empty value
  - [x] Success: module imports; pyright strict clean
  - Note: `PassageRef` has no `kind` field, so the `passages` column stores `id`, `source`, `question_id`, `date`; `store/question_json.py` reuses `decode_mapping_list` (new in `store/row_values.py`).

- [x] **1.4 Serializer tests**
  - [x] Round-trip test per column; a bad-JSON test per parser
  - [x] Success: tests pass

- [x] **1.5 Question reads, insert and claim moves**
  - [x] In `store/questions.py` add reads `get_question(run_id, paused_at)`, `latest_question(run_id)` (latest `claimed_at`), `any_answering_run_id(run_id)` (true if some question has that `answering_run_id`)
  - [x] Add `insert_question(...)`: `INSERT … ON CONFLICT (run_id, paused_at) DO NOTHING`, returns whether this call wrote the row; state `claimed` (with `answering_run_id`, passages, slice label, source commit) or `waiting_on_pm` (with `waiting_reason`, `waiting_detail`)
  - [x] Add compare-and-set moves, each `UPDATE … WHERE state = 'claimed' AND answering_run_id = ?`, returning whether a row changed: `settle_waiting` (reason, detail, evidence) and `replace_claim` (swap `answering_run_id` and passages old to new, for D7 `not_found` old)
  - [x] Every write is one short `BEGIN IMMEDIATE` transaction; none is held across a subprocess
  - [x] Success: module imports; pyright strict clean

- [x] **1.6 Question tests**
  - [x] Reads: `get_question` and `latest_question` return the right row (two questions on one run, different `claimed_at`); `any_answering_run_id` true for a known id and false otherwise
  - [x] Insert race: second insert returns false and leaves the first row
  - [x] Each compare-and-set returns false when the state or `answering_run_id` differs, true otherwise
  - [x] Success: tests pass

- [x] **1.7 Answer reads and writes**
  - [x] In `store/answers.py` (a separate module to keep `questions.py` near ~300 lines; `store/questions.py` re-exports these names so the design's `store.questions` interface holds) add reads `answers_of(question)`, `latest_answer(question)` (highest `seq`), `automatic_answer_count(run_id)` (rows with `answered_by = 'answerer'`, this `run_id`, any `paused_at`)
  - [x] Add `add_pm_answer`: one transaction adds a `pm` answer row and sets `answered` from any state; does not clear `waiting_reason` or `waiting_detail`
  - [x] Add `record_resume(answer, outcome, detail, log, at)` with `WHERE resume_outcome IS NULL OR resume_outcome = 'refused'`
  - [x] Success: module imports; pyright strict clean

- [x] **1.8 Answer read and write tests**
  - [x] `answers_of` returns all rows in `seq` order; a newer PM answer adds a row and `latest_answer` returns it
  - [x] `automatic_answer_count` ignores PM answers and counts across `paused_at` values
  - [x] `add_pm_answer` sets `answered` from `claimed` and from `waiting_on_pm` and leaves `waiting_reason` in place
  - [x] `record_resume` never overwrites `resumed` or `not_delivered`, does overwrite `refused`
  - [x] Success: tests pass

- [x] **1.9 Automatic settle with gate**
  - [x] In `store/answers.py` add `settle_answered(…, gate)`, compare-and-set `claimed → answered` (same guard as 1.5). In one `BEGIN IMMEDIATE` transaction: count `prior` with `automatic_answer_count`, call `gate(prior)` (returns a decline or `None`); on a decline write nothing and return it; otherwise do the compare-and-set and insert the `answerer` answer row with `cited`; return `settled`, the decline, or `lost`
  - [x] Success: module imports; pyright strict clean
  - Note: `settle_answered` checks the claim is still held before calling the gate, so a lost claim returns `lost` even if the gate would decline; it also writes `questions.evidence` on settle.

- [x] **1.10 Automatic settle tests**
  - [x] A PM answer during a claim makes the later `settle_answered` return `lost`; a gate that declines writes nothing and its decline is returned; `gate` receives only automatic answers in `prior`; success writes the `answerer` row with `cited`
  - [x] Success: tests pass

- [x] **1.11 PM precedent read**
  - [x] Add `pm_precedent(store, member_id)` in `store/answers.py`: the newest PM answer for each of the member's questions, with question text, slice label and `recorded_at`; automatic answers excluded
  - [x] Add tests: two PM answers on one question gives only the newer; an automatic-only question gives nothing; another member's questions are excluded
  - [x] Success: tests pass

**Commit**: `feat: add pause-handling store migration and question access`

## 2. Run file, home paths and `sq` fixtures (D2, D12, D15)

- [x] **2.1 Home paths (D12)**
  - [x] In `config/home.py` add `answering_dir()` (`amoeba_home() / "answering"`), `logs_dir()` (`amoeba_home() / "logs"`), `squadron_runs_dir()` (`Path.home() / ".config" / "squadron" / "runs"`); directory names as constants in that file
  - [x] Extend `tests/config/test_home.py`: first two sit under `AMOEBA_HOME`; the third is under the (test-set) `HOME`; the AST test from 222 (only `home.py` calls `Path.home`) still passes
  - [x] Success: tests pass

- [x] **2.2 Record `sq` fixtures (D15)**
  - [x] Create `tests/live/pause/asks_question.yaml`: a dispatch that ends on a question about file length limits that the repo's rules settle. Task 9.2 reuses it
  - [x] Create `tests/fixtures/squadron/` with real 0.24.23 output (or the installed version; record it) of `sq runs wait <id> --timeout 0 --json` for: an `agent_question` pause, a pause of another checkpoint kind, a running run, a completed run. Name files for the case. Capture by running real `sq` (the `agent_question` pause comes from `asks_question.yaml`); never hand-write
  - [x] Copy one real schema-5 run file from `~/.config/squadron/runs/` into `tests/fixtures/squadron/` as the `run_file` fixture; strip nothing that the reader parses
  - [x] Add `tests/fixtures/squadron/README.md` with `sq --version` and capture date
  - [x] If a case cannot be captured, write `BLOCKED: cannot record <case>` under this task and stop
  - [x] Success: each JSON fixture parses; the pause fixture has `checkpoint.kind`, `paused_at` and `question`
  - Note: `asks_question.yaml` is a one-step `dispatch` that declares `artifact: design` and has no `slice` param; with none in scope Squadron's artifact post-condition fails and, because the reply ends on a question mark, the run pauses as `agent_question` (Squadron #249). An `implement` step would need `branch: enter` and a `slice` param, which would defeat the no-slice walkthrough. Recordings captured 20261110 with `sq` 0.24.25 in `tests/fixtures/squadron/`: `wait_paused_agent_question.json` (exit 3), `wait_paused_interactive_checkpoint.json` (exit 3, a real older local `slice` run, kind `interactive_checkpoint`), `wait_running.json` (exit 4, outcome `timed_out`), `wait_completed.json` (exit 0), `run_file_schema5.json` (real run file of the agent_question run, `params` {model}, mode `sdk`; keeps this machine's `pipeline_path`). Run ids in the recordings are the real captured ids; the fake `sq` helper re-addresses `run_id` to the id a test registers.

- [x] **2.3 Fake `sq` helper**
  - [x] Add a test helper that writes a fake `sq` first on `PATH`: replays a named fixture for `sq runs wait`, records its argv to a file for `sq run …` (including `--resume` with `--instructions`), exits with a configured code. A second helper returns an injectable `poll_run` fake
  - [x] Success: running the written script with the pause fixture prints that fixture; a `sq run` call appears in the argv record
  - Note: helper is `tests/fake_sq.py` (`write_fake_sq`, `FakeSq.run_calls`, `fake_poller`, `poll_result`, `failing_poll`), tested in `tests/test_fake_sq.py`. The existing `tests/sq_stub*.py` stub is a different, stateful design for the launch/resume tests and is left alone.

- [x] **2.4 Run file reader (D1, D2)**
  - [x] Create `upstream/squadron/run_file.py`: `ExecutionMode` (`StrEnum`: `sdk`, `prompt-only`), `RunFacts(params: dict[str, str], execution_mode)`, `RunFileProblem` (names file and field), `read_run_facts(runs_dir, run_id) -> RunFacts | RunFileProblem`. Check `schema_version` is 5. Missing file, other version, bad JSON, missing field and unknown mode are each a `RunFileProblem`
  - [x] Imports nothing from `answering`; `runs_dir` is an argument
  - [x] Add `tests/upstream/test_run_file.py`: the real fixture parses with the right params and mode; one test per problem kind; no case returns `sdk` by default
  - [x] Success: tests pass

**Commit**: `feat: add run file reader, home paths and Squadron recordings`

## 3. Answering library changes (D11)

- [x] **3.1 Not-authorized file**
  - [x] Add `pipeline_file.NOT_AUTHORIZED_FILE = "not_authorized.md"`; add `inputs.render_not_authorized(items)`: one `key: description` bullet per item; empty list renders `No item is barred for this repository.`
  - [x] `prepare_scratch` writes the file. Keep its four positional parameters `(directory, question, passages_markdown, max_cost_usd)`; add the items as a keyword-only `not_authorized` defaulting to `()` (renders the empty-list line), so the kept live harness still works. The names and signatures the kept live tests import (`SQ_EXECUTABLE`, `RunOutcome`, `RunOutcomeDocument`, `PollFailure`, `RunPoll`, `poll_run`, `QUESTION_TAIL_CHARS`, `mint_run_id`) are not changed
  - [x] Success: module imports; pyright strict clean

- [x] **3.2 Rewrite `answering.yaml` prompts**
  - [x] In both steps list `not_authorized.md` in `prompt_files` after `passages.md`. Replace the hard-coded authorize list in both prompts with text saying the list follows the passages; the answer step must decline, and the check step reply no, when an answer would authorize anything on it
  - [x] Success: `answering.yaml` contains no hard-coded authorize list (grep for the old items finds none)
  - Note: both prompts also carry 182's kind sentences (program_concept, program_members), with a pin test.

- [x] **3.3 Not-authorized tests**
  - [x] Test rendering: two items, empty list. Test `prepare_scratch` writes the file with the items given. Update the existing pin test so it covers the new file and the `prompt_files` order
  - [x] Add a test that runs real `sq run <answering.yaml> --validate` (with the pipeline's required params) and passes; the old probe test is deleted. If CI has no `sq`, put it in `tests/live/answering/` (run with `uv run pytest tests/live`), not in the default suite
  - [x] Success: tests pass
  - Note: `sq run answering.yaml --validate` test is `tests/live/answering/test_validate.py` (needs `sq`, so it runs with `uv run pytest tests/live` and the `AMOEBA_LIVE_*` variables; verified passing). CI has no `sq`. No old probe test existed to delete.

- [x] **3.4 Program passages**
  - [x] Add `ProgramSources` (concept as a `SourceFile`: member id, path, commit, date, text; and the member list). Port `program_concept` and `program_members` from the 182 take group; if that group is empty, write them new from the design of slice 182
  - [x] `answering.passages` gains both kinds and their rendering; `assemble` takes `ProgramSources`; both prompts list the two new kind words
  - [x] Port by copy from branch `182-slice.program-concept-as-a-source` (`git show 182-slice.program-concept-as-a-source:<path>`, no merge): the take group (`program_passages.py`, the `passages.py` kinds and rendering, the `answering.yaml` kind sentences, the `source_reads.py` renames) with the take-group tests (`test_passages.py`, `test_pipeline_yaml.py`, `test_program_passages.py`), re-pointed to 222's `Member` and `Program`. Do not port the drop group (the no-program path: `program=None` optionality, commit `6c2499b`, its baseline tests)
  - [x] `ProgramSources.concept` is optional (`None` when the program has no concept): no `program_concept` passage, member list still emitted. 182's branch requires a concept member; this is the gap the audit names
  - [x] Make plan row selection in `source_reads` optional when `slice_ref` is `None`
  - [x] `inputs.render_question` rejects a blank slice label today. A no-slice question must reach it and be rendered, not rejected: D5's `NO_SLICE_LABEL` is passed for it (the library takes the label as an argument; it does not import the constant), and a blank string stays rejected. Keep the live tests' constructor calls unchanged; they always pass a slice
  - [x] Find every existing caller of `assemble` and `source_reads` and every existing test of them (grep under `src` and `tests`); update each to the new signatures in this task
  - [x] Success: module imports; pyright strict clean; all four checks pass
  - Note: `ProgramSources(concept: SourceFile | None, members: SourceFile)` lives in `answering/passages.py` (not a separate `program_passages.py`, which would need a `TYPE_CHECKING` cycle). `Member`/`Program` are NOT imported into `answering` because task 3.6 forbids `answering` importing `store`: the member-list text and date helpers (`member_list_text`, `member_list_date`, marker constants, built on 222's `Member` and `Program`) therefore go into `operations` with task 4.4, and their tests (182's `test_program_passages` member-list cases) are ported there. `SourceFile` and `Passage` gained a required `member` field. `source_reads` made `GitReads`, `Listings`, `in_context`, `read_file` public; `locate_sources` and `read_committed_sources` take `SliceRef | None`. `assemble` takes required `program_sources`. `render_question` already accepts any non-blank single-line label, so no code change was needed for the no-slice label; tests added in `tests/answering/test_program_passages.py`. The only caller of `assemble` and `read_committed_sources` was `answering/sources.py::assemble_sources`, which had no callers and no tests; it is deleted because task 4.6's `gather` replaces it (gather must read program sources between the committed read and the assembly).

- [x] **3.5 Program passage and no-slice tests**
  - [x] Tests: `assemble` with program sources emits both kinds; with no slice it emits rules, program and precedent passages and no plan passages; `source_reads` with `slice_ref=None` selects no plan rows; `assemble` with `concept=None` emits the member list and no concept passage; `render_question` renders a no-slice question and still rejects a blank label
  - [x] Success: tests pass

- [x] **3.6 Import boundary**
  - [x] Add to `tests/test_import_boundaries.py`: `answering` imports nothing from `store`, `config` or `operations`. Confirm `store` importing `answering.values` is allowed
  - [x] Success: test passes; adding a forbidden import makes it fail (verify once, then revert)

**Commit**: `feat: add program passages and not-authorized list to answering library`

## 4. Context (D5)

- [x] **4.1 Record slice-lookup fixtures**
  - [x] Add to `tests/fixtures/context_forge/` real `cf list initiatives --json -a` output and `cf list slices <index> --json` output for plans in this repo, including an index that is in no plan. Capture with real `cf`; do not hand-write. Extend the README with `cf --version` and date
  - [x] Success: files parse as JSON; one slice index from the run fixture's range is in a plan, one is in none
  - Note: recorded 20261110 with cf 0.19.26 in `tests/fixtures/context_forge/` (`list_initiatives_a.json`, `list_slices_{100,120,140,180,220}.json`, and the stderr error documents `list_slices_{160,200}_error.json`); README extended. Slice 223 is in initiative 220's plan; 299 is in none. `tests/test_cf_fixtures.py` now names its four `cf get` recordings explicitly and has a test for the plan recordings.

- [x] **4.2 Slice resolution in `pause_context.py`**
  - [x] Define `TARGET_PARAM_KEY = "slice"` (the run parameter holding the slice index) and `NO_SLICE_LABEL = "none"` once in `operations/pause_context.py`
  - [x] `resolve_slice(run_facts, cf_run)`: parse `params[TARGET_PARAM_KEY]` as an index; search plans of initiatives with index no higher than it, highest first; label `<index> <name>`. A non-integer value, or one in no plan, is `sources_missing`. Absent parameter: the no-slice label (D5). A failing `cf` call is `sources_unreadable` with the output head
  - [x] Success: module imports; pyright strict clean
  - Note: `TARGET_PARAM_KEY` is NOT redefined: `upstream/squadron/launch.py` already defines `TARGET_PARAM_KEY = "slice"` (the run parameter holding the slice index), so `pause_context.py` imports it (one definition). `NO_SLICE_LABEL = "none"` and `READ_TIMEOUT_SECONDS = 30.0` (named constant, same precedent as `CF_GET_TIMEOUT_SECONDS`) are defined in `operations/pause_context.py`. The `cf list` command words are spelled once in `upstream/context_forge/target_read.py` (`list_initiatives_command`, `list_slices_command`, with the defined-once test extended); the runs are in the new `upstream/context_forge/plan_read.py` (`read_initiatives`, `read_slice_list`, tested in `tests/upstream/context_forge/test_plan_read.py`). `resolve_slice(checkout, cf_project_id, params, run)` takes the params dict from `RunFacts` rather than the whole `RunFacts`. A slice's initiative that has no plan (CF's `error: true` document) is skipped, not an error.

- [x] **4.3 Slice resolution tests**
  - [x] Using the 4.1 fixtures: slice found; slice in no plan and non-integer parameter each give `sources_missing`; no parameter gives the no-slice label; failing `cf` gives `sources_unreadable`
  - [x] Success: tests pass

- [x] **4.4 Program sources read**
  - [x] `read_program_sources(...)` in `pause_context.py`: concept member and path from `programs`, member list from `members_of`, concept member's checkout from `project_of(reference=…).project_path`, concept file read through the git allowlist at that checkout's target (the asker's own pinned commit if it is the concept member). Returns `ProgramSources` (task 3.4)
  - [x] Rewrite group of 182's `program_sources.py`: copy its git logic (`_read_concept_file`, `_within_limit`, `without_path`, `_read_from_asker`, the `SourcesProblem` kinds) from the 182 branch; replace `ProgramContext`, `read_member`, `_read_target` and `TickBudget` with the checkout, members from the store and the moved `read_target`. Keep 182's decisions D3 to D6 (the asker's own pinned commit; member-list wording; early size stop; no rules, plan or PM answers from other members)
  - [x] A program with no concept (both columns null) gives `ProgramSources` with `concept=None` and no read
  - [x] Success: module imports; pyright strict clean
  - Note: split for the ~300-line limit: the member-list text and date helpers, `ProgramRead`/`AskerReads` inputs, the concept read and `without_path` are in `operations/program_sources.py` (not `pause_context.py`). A concept member that is not a Context Forge project (`PROJECT_NOT_FOUND`) is `sources_missing`; a failing `cf` call is `sources_unreadable`. Ported tests live in `tests/operations/test_program_sources.py` with `program_rig.py`; the 182 `read_member` defect cases, budget refusals and call-count-by-budget cases have no counterpart (the store and tick budget are gone).

- [x] **4.5 Program sources tests**
  - [x] Using a temporary git repo: concept read at the other member's target; concept member equal to the asker uses its own pinned commit; unreadable file gives its `DeclineReason` through `sources_reason`
  - [x] Port the assertions of 182's `test_program_sources.py` (missing, unreadable, non-UTF-8, timeout, too large, asker holds the concept) and the program section of `test_sources.py` (concept once, problem as value, visibility), with its concept-repo fixtures (`program_rig.py`); the call-count and budget cases get new shapes. Add: program with no concept returns no concept and reads nothing
  - [x] Success: tests pass

- [x] **4.6 `gather`**
  - [x] `gather(checkout, member, program, run_facts, question, settings, cf_run) -> PauseContext | SourcesProblem` combines: `resolve_slice`; committed rules and plan files via `read_committed_sources` from the question's checkout at `read_target` (`rules_paths` from `answering_for`); `read_program_sources`; precedent from `questions.pm_precedent`. Each `SourcesProblem` maps to its `DeclineReason` through `sources_reason`
  - [x] Centralize the empty-means-main rule: `DEFAULT_TARGET_BRANCH` (task 0.2 note) is the one named constant in `target_read.py`, with a comment that it is Context Forge's own documented default for an empty `git.integration_branch`. `read_target` returns it for an empty value and the value as-is otherwise; no `"main"` literal elsewhere in `src` (grep to confirm; reference the constant). A failed `cf config get` call (nonzero exit, unreadable output; not an empty value) raises an explicit typed error that `gather` maps to `sources_unreadable` with the output head. Add no other fallback
  - [x] Success: module imports; pyright strict clean
  - Note: `gather(store, checkout, member, run_facts, settings, run)` has no `question` parameter (the question text is not used by the context; the caller passes it to the scratch), reads the store once in one short read transaction before any subprocess (program, members, PM precedent), and returns a `SourcesProblem` for the caller to map with `sources_reason`. `read_target` returns a `ReadFailure` value (not a raised error) for a failed `cf config get`; gather maps it to `sources_unreadable` with the output head, which satisfies the explicit-typed-failure requirement without a new exception. `DEFAULT_TARGET_BRANCH` was already the single `"main"` literal in `src` (grep confirmed). `PmAnswer.slice_label` became `str | None`: a PM answer to a question recorded before its slice was known (e.g. waiting on `answer_limit_reached`) renders with no `slice:` line instead of a made-up label. A PM precedent's record id is `<run_id>@<paused_at>`.

- [x] **4.7 `gather` tests**
  - [x] Using a temporary git repo and the 4.1 fixtures: full context with a slice; no-slice context has no plan passages; precedent passages present after a PM answer and absent for automatic answers; a failing sub-step returns its problem and nothing partial; in `read_target` tests: an empty `git.integration_branch` yields `DEFAULT_TARGET_BRANCH`, a non-empty value (e.g. `dev/erik`) is used as-is, and a failing `cf config get` call gives the typed error, which `gather` reports as `sources_unreadable`
  - [x] Success: tests pass

**Commit**: `feat: gather pause context from slice, program and precedent`

## 5. Answering run (D6)

- [x] **5.1 Spawn helper**
  - [x] Create `operations/processes.py` as a thin wrapper over the kept `upstream.squadron.launch.spawn` (exclusive `xb` logs, own session, `stdin` from `/dev/null`, inherited environment, `close_fds`); write no second spawn. `start_child(argv, cwd, logs: LaunchLogs)`: create the logs' parent directory, call `spawn(argv, cwd, logs, subprocess.Popen)`, return the child (a `WaitableChild` protocol defined here: `poll`, `wait(timeout)`, `pid`, satisfied by `Popen`) or the kept `LaunchError`. `terminate_group(child)`: `os.killpg` of the child's own session, then wait for exit. These are the only additions: the kept `ChildHandle` has `poll()` only, and 223's wait and terminate need more. `stderr_tail` is the kept one (last `STDERR_TAIL_LIMIT_BYTES`), not re-implemented. Imports only `upstream.squadron.launch` from Amoeba
  - [x] Success: module imports; pyright strict clean
  - Note: `start_child(argv, cwd, logs, popen=subprocess.Popen)` takes the popen factory as a defaulted parameter because the repo's containment test requires every test-started process to go through `process_containment.contained_popen`; production uses the default. `Spawner` (type alias) is the injectable form. `terminate_group` sends SIGTERM then SIGKILL (`TERMINATE_GRACE_SECONDS` = 5) to the child's own process group and waits. `processes.py` also imports `upstream.squadron.faults.LaunchFailure` (same package family as `launch`).

- [x] **5.2 Spawn helper tests**
  - [x] Tests of the wrapper with real short subprocesses (the kept `spawn`'s own tests moved by 221 are not repeated): logs are written, including when the log directory does not yet exist; a second `start_child` to the same log path returns a `LaunchError` (exclusive); wait times out on a sleeping child; `terminate_group` kills the child and its own child; `stdin` is empty; the kept `stderr_tail` returns the last lines of a child's stderr log
  - [x] Success: tests pass

- [x] **5.3 Shared `Deps`**
  - [x] Create `operations/deps.py` with one frozen dataclass `Deps` (cf runner, `poll_run` with its timeout, spawner, `answering_dir`, `logs_dir`, `squadron_runs_dir` paths), imported by `answering_run`, `resume`, `handle_pause`, `pause_existing` and `answer`. It imports nothing from those modules, so there is no cycle. The injected spawner and poller used by tasks 5.6 onward come from it
  - [x] Success: module imports; pyright strict clean
  - Note: `Deps` (operations/deps.py) also carries `clock` and `sleep` (so tests control time and the 0.5 s resume poll loop), and `production_deps(*, answering_dir, logs_dir, squadron_runs_dir)` builds the real edges for the CLI. `poll_run` in `Deps` is `Callable[[str], RunPoll]` with its timeout (`RUN_POLL_TIMEOUT_SECONDS` = 30) bound.

- [x] **5.4 Config keys**
  - [x] Add required keys `answering_wait_seconds` and `resume_wait_seconds` (number > 0) to the config model; a missing or non-positive value is a `ConfigError`; no default in code. Update `docs/config-contract.md` with both keys
  - [x] Add both keys to every existing test config fixture and to the example config in `docs/config-contract.md`, so existing configs and tests still load
  - [x] Add tests: missing, zero, negative, non-number each fail; valid passes
  - [x] Success: all four checks pass; the contract doc lists both keys
  - Note: both keys accept an int or float > 0 (booleans rejected); `docs/config-contract.md` lists them and its example sets 600 and 60; `tests/user_configs.py` updated.

- [x] **5.5 Scratch and run id**
  - [x] In `operations/answering_run.py` import `mint_run_id` (`amoeba-<UTC stamp>-<12 hex>`) from `upstream.squadron.launch`, where 221 keeps it (task 0.2 note) with its signature, because the kept live harness calls it; do not restore or copy it. `make_scratch` always passes the member's not-authorized items to `prepare_scratch` explicitly. Add `make_scratch(answering_dir, run_id, ...)`: exclusive directory create, then `prepare_scratch` including the not-authorized file. An `OSError` returns a failure value for `answering_launch_failed`
  - [x] Add tests: id format; two ids differ; existing directory fails; scratch holds `passages.md` and `not_authorized.md` with the member's items (not the empty-list line)
  - [x] Success: tests pass
  - Note (covers 5.5, 5.6 and 5.8): `operations/answering_run.py` holds `make_scratch` (a thin wrapper over the existing `answering.launch.prepare_scratch_directory`, which now takes a required keyword-only `not_authorized`), `answering_argv`, `start`, `wait`, `Claim` and the `NO_PAUSE_HOOK_FLAG` constant (`--no-pause-hook`, confirmed in `sq run --help` on sq 0.24.25; a test pins that it is spelled only there). Settle moved to `operations/answering_settle.py` (the ~300-line limit): `SettleResult` is `Answered | Waiting | Superseded` there, and `answer_claim` is start, wait, settle in order. `wait` also maps a child that exited with no run at Squadron to the library's `LaunchFailed` (non-zero exit, with the stderr tail) or `RunVanished` (exit 0). A gate refusal settles to waiting with the gate's reason, with `evidence` stored.

- [x] **5.6 Start and wait**
  - [x] `start(...)` builds the argv with the kept `build_argv(<answering.yaml>, <id>, {"answer-model": <answer_model>, "check-model": <check_model>}, target_key="answer-model")` (gives `sq run <answering.yaml> <answer_model> --run-id <id> -p check-model=<check_model>`; a `ValueError` from it is `answering_launch_failed`) and appends `--no-pause-hook`. Confirm the flag name with `sq run --help` (Squadron #302, closed, in 0.24.24) and define it once as a constant in `answering_run.py`; the answering run always passes it. Starts it with `processes.start_child` (the kept `spawn`) in the scratch, logs at `logs_dir() / "answering" / <id>.{stdout,stderr}.log` built from the run id as a `LaunchLogs`; a `LaunchError` is `answering_launch_failed`
  - [x] `wait(...)`: wait up to `answering_wait_seconds`; on timeout terminate the process group and return `answering_run_stalled` (`no result after <n> seconds`); otherwise one `poll_run(id)`; a `PollFailure` is `answering_run_failed`. `poll_run` keeps its hard-coded `--timeout 0` (a non-blocking read): the wait is on the child process, never a blocking `sq runs wait`, so `poll_run` is not changed (audit item: how `handle_pause` waits)
  - [x] Success: module imports; pyright strict clean

- [x] **5.7 Start and wait tests**
  - [x] Using the fake `sq` and injected spawner and poller: argv is exactly as designed and holds `--no-pause-hook` exactly once; spawn error, stall and poll failure each give their decline reason; no store transaction is open while the spawner or poller runs
  - [x] Success: tests pass
  - Note: the no-transaction-open check is in `test_answer_claim_starts_waits_and_settles_with_no_transaction_open` (takes a store write inside the injected spawner and poller callbacks); the stall test uses a real sleeping child.

- [x] **5.8 Settle**
  - [x] `settle(...)`: if completed, `read_answer` and `read_check` from scratch, `decide_answer(summary, answer, check, passage_ids)` with the claim's passage ids; a `Confirmed` answer goes to `settle_answered` with `gate = lambda prior: evaluate_gate(question, prior, answer=…, settings=…)` (the count happens inside the store transaction, 1.9). A gate decline or a `decide_answer` decline goes to `settle_waiting` with the reason, bounded detail and evidence. `settle` returns a `SettleResult` defined in `answering_run.py`: `answered`, `waiting` (reason, detail) or `superseded` (any `lost`/false return)
  - [x] Success: module imports; pyright strict clean

- [x] **5.9 Settle tests**
  - [x] Cases: confirmed and gate passes gives `answered` with an `answerer` row and `cited`; check said no gives `check_said_no`; screen refusal gives `reserved_term`; an item barred for one member and allowed for another gives different results; PM answer during settling gives `superseded`; answer limit counts automatic answers only (the gate declines with `answer_limit_reached` at the limit, and nothing is written for the answer)
  - [x] Success: tests pass

**Commit**: `feat: add answering run start, wait and settle`

## 6. Resume (D8)

- [x] **6.0 `ResumeResult` model**
  - [x] Create `operations/pause_models.py` with `ResumeResult` (`outcome`: `resumed`, `refused`, `not_delivered`; `detail`; `resume_log`). Task 7.1 adds the other models to this file
  - [x] Success: module imports; pyright strict clean
  - Note: `ResumeResult` is in `operations/pause_models.py`.

- [x] **6.0a Check the run lock against the real `sq`**
  - [x] Before any resume code: with the real `sq`, pause a run (`tests/live/pause/asks_question.yaml`), start one `sq run --resume <id>` that holds the run lock, and start a second `sq run --resume <id>` on the same run. Record the second's exit code, stderr text and whether the run stayed at the pause, under `tests/fixtures/squadron/` (README: `sq --version`, date). Never hand-write it
  - [x] Decide from the observation: D8 judges `refused` by "child exited, run still at this pause", whatever the exit code. If the held lock exits 2 or anything else, note it; do not carry `resume_progress`'s "exit 2 means refused" rule into new code (if `has_left` or `is_at` from `confirm.py` are reused, only the checkpoint compare is)
  - [x] If the lock cannot be provoked, write `BLOCKED: cannot provoke the run lock` under this task and stop (not triggered: the lock was provoked)
  - [x] Success: the fixture and a note of the observed exit code and stderr exist; the 6.2 refused-branch test replays that fixture
  - Note (observed 20261110, sq 0.24.25, real run `amoeba-fixture-lock-3`; recordings `tests/fixtures/squadron/resume_lock_*`, README section "The run lock"): the second `sq run --resume <id>` while the first held the run **exits 1** (not 2), prints `Error: Run '<id>' is still running under pid <pid> on <host>.` on **stdout**, and leaves **stderr empty**; the run was `running` under the first resume (not at the pause).
    - Consequences recorded in code: the refusal detail reads the stderr tail and falls back to the stdout tail; refusal is judged by "child gone and run still at this pause", never the exit code; when the poll already shows the holder's `running`, the loser reports `resumed` as well (the run is running).
    - No "exit 2 means refused" rule was carried over, and `has_left`/`is_at` were not reused.
    - The 6.2 refused-branch test replays the recorded stdout message and exit code 1 with an empty stderr.

- [x] **6.1 Implement `resume.py`**
  - [x] `resume.resume(store, question, answer_seq, *, deps) -> ResumeResult`. `RESUME_POLL_INTERVAL_SECONDS = 0.5` defined in the module
  - [x] Step 1: `poll_run(run_id)`; not `paused` or a different `paused_at` gives `not_delivered`, nothing started
  - [x] Step 2: argv is the kept `resume_argv(run_id, compose_instructions(question, answer))` (`upstream.squadron.resume_argv`), started via `processes.start_child` (the kept `spawn`), `cwd = questions.checkout`, logs as a `LaunchLogs` at `logs_dir() / "resume" / <run_id> / <answer_seq>-<UTC stamp>.{stdout,stderr}.log` (stdout path is `resume_log`); a `LaunchError` is `refused`
  - [x] Step 3: poll every interval up to `resume_wait_seconds`. `running`, or moved past (other `paused_at`, `completed`, `failed`) is `resumed`; child exited with the run still at this pause is `refused` with `stderr_tail` as detail; timeout with child alive and run unchanged: terminate the process group, wait for exit, poll once more; still at this pause is `refused` (`not running after <n> seconds`), `running` or moved past is `resumed` (`resume process terminated after taking the run`)
  - [x] Step 4: `record_resume`
  - [x] Success: module imports; pyright strict clean
  - Note: `resume(store, question, answer_seq, *, deps, wait_seconds)` takes `wait_seconds` (the `resume_wait_seconds` config value) as a keyword. It reads the answer text through the new `store.answers.get_answer(seq)`.
    - `upstream/squadron/errors.py::SquadronError` added. An unreadable first poll raises it, with nothing started or written; 7.2 and 8.1 use it.
    - `RunCheckpoint.paused_at_text` added in `run_outcome.py` (`paused_at.isoformat()`). It reproduces the recorded `paused_at` text exactly on three real recordings; the key's `paused_at` is always made this one way.
    - Polls after the child starts that are unreadable or show `not_found`/`unknown` status are `unclear`: the loop keeps waiting, and the final result is `refused`.
    - Resume log names: `<logs>/resume/<run_id>/<answer_seq>-<UTC stamp with microseconds>.{stdout,stderr}.log`.

- [x] **6.2 Resume tests**
  - [x] Every branch with injected poller and spawner: not paused, different `paused_at`, running, moved past, paused again before a poll saw running, child exited at the pause with stderr tail (using the real exit code and stderr recorded in 6.0a), timeout then still paused, timeout then running after the kill
  - [x] `--instructions` is a single argv element holding the composed text, including text with spaces, quotes and a leading `…`
  - [x] `resumed` and `not_delivered` are never overwritten; of two racing resumes the second's refusal does not replace the first's `resumed`
  - [x] No store transaction is open while spawning or polling
  - [x] Success: tests pass

**Commit**: `feat: add shared resume for paused runs`

## 7. `handle_pause` and `answer` (D3, D4, D7, D9)

- [x] **7.1 Result models and `SkipReason`**
  - [x] In `operations/pause_models.py` (created in 6.0) add `SkipReason` (`StrEnum`, the D3 table's eleven reasons) and `HandlePauseResult` (`outcome`: `skipped`, `waiting_on_pm`, `superseded`, `resumed`, `refused`, `not_delivered`; plus `skip_reason` or `waiting_reason`, `detail`, question key, claimed `checkout`, `answering_run_id`, `answer_seq`). `handle_pause.py` re-exports both, so the design's import path works. The split keeps each module near the ~300-line guideline
  - [x] Success: module imports; pyright strict clean
  - Note: module split for the ~300-line limit (covers 7.1, 7.2, 7.4, 7.6, 7.8 and 7.10):
    - `operations/pause_models.py`: `ResumeResult`, `SkipReason`, `HandlePauseOutcome`, `HandlePauseResult`
    - `pause_eligibility.py`: `check_eligibility`, `Skip`, `Eligible`
    - `pause_claim.py`: `start_new_claim`, `restart_dead_claim`
    - `pause_results.py`: `PauseTarget`, `finish`, `resume_answer`, `skipped`
    - `pause_existing.py`: `handle_existing` (settled-row and dead-claim paths)
    - `handle_pause.py`: the entry point; re-exports `SkipReason`, `HandlePauseResult`, `HandlePauseOutcome`
    - `SquadronError` is `upstream/squadron/errors.py` (added in 6.1)

- [x] **7.2 Eligibility checks (D3)**
  - [x] In `operations/pause_eligibility.py`, implement the checks in D3's order, first failure wins: `not_paused`, `not_agent_question` (detail gives raw kind), `no_question_text`, `answering_run` (via `any_answering_run_id`), `not_a_project`, `not_in_program`, `prompt_only` (run file read only after membership; a `RunFileProblem` raises `SquadronError`), `other_member`
  - [x] A Squadron or `cf` failure raises the operational error; it is never a skip
  - [x] Success: module imports; pyright strict clean
  - Note:
    - a Context Forge failure raises `ContextForgeError` (from `resolve_member`); a run file problem in a member raises `SquadronError`; a failing `sq` raises `SquadronError`
    - the `other_member` check needs the existing row and is made after `prompt_only`, as D3 orders them

- [x] **7.3 Eligibility tests**
  - [x] One test per `SkipReason` that these checks produce, using the fake `sq`, fake `cf` and store. Include: run-file problem in a non-member repo is not an error; run-file problem in a member raises; a failing `sq` or `cf` raises and writes nothing
  - [x] Success: tests pass
  - Note: test support added for section 7's tests:
    - `tests/operations/handle_rig.py`: a whole `handle_pause` world (real store and git checkout, replayed `cf` and `sq runs wait`, a spawner that plays Squadron)
    - `tests/operations/pause_support.py`: fake clock, sleep, child, spawner, `register_member`
    - `tests/cf_plan_run.py`: replays `cf get`, `list` and `config get`

- [x] **7.4 Claim step for a new question (D4, D6)**
  - [x] In `operations/handle_pause.py` (the entry point, calling `pause_eligibility`), when no row exists: `resolve_member`, `answering_for`; if `automatic_answer_count` already meets `answer_limit`, insert `waiting_on_pm / answer_limit_reached` and stop; `gather`; make scratch; insert in one transaction as `claimed` (with answering run id and passages) or `waiting_on_pm` (failure reason). A lost insert removes the scratch and returns `skipped / already_claimed`. Result carries `checkout`
  - [x] Success: module imports; pyright strict clean
  - Note:
    - scratch is made, and the `waiting_on_pm` row is written with the gathered `slice_label`, `source_commit` and passages when the failure came after context (scratch failure)
    - the `waiting_on_pm` row is written with none of them when the failure came before context (answer limit, context failure)

- [x] **7.5 Claim step tests**
  - [x] Answer limit already met inserts `waiting_on_pm / answer_limit_reached` and starts nothing; context failure inserts `waiting_on_pm` and starts nothing; scratch `OSError` inserts `waiting_on_pm / answering_launch_failed`; lost insert race removes scratch and skips
  - [x] Success: tests pass

- [x] **7.6 Answer step for a new claim (D6, D8)**
  - [x] After a successful claim: start, wait, settle (tasks 5.6 and 5.8); only an `answered` settle is resumed (D8). `waiting` and `superseded` settles map to the matching `HandlePauseResult` outcome without resuming
  - [x] Success: module imports; pyright strict clean

- [x] **7.7 Answer step tests**
  - [x] Answered and resumed end to end with fakes; declined answer is not resumed; `superseded` is returned and not resumed
  - [x] Success: tests pass

- [x] **7.8 Settled-row paths (D3, D4)**
  - [x] In `operations/pause_existing.py` (called by `handle_pause` when a row exists): `answered` with latest answer not `resumed` or `not_delivered`: resume with the latest answer, starting no answering run. `waiting_on_pm` and settled answers: `skipped` with `waiting_on_pm` or `settled`
  - [x] Success: module imports; pyright strict clean

- [x] **7.9 Settled-row tests**
  - [x] One test per path above. A refused earlier resume is retried with the recorded answer and no answering run starts
  - [x] Success: tests pass

- [x] **7.10 Dead-claim paths (D7)**
  - [x] In `pause_existing.py`, `claimed`: apply the D7 table with `poll_run(answering_run_id)` and the claim age against `answering_wait_seconds`. Running and young skip; running and old `settle_waiting` with `answering_run_stalled`; `completed`, `failed`, `paused`, `orphaned` settle from scratch then resume; `not_found` young skip; `not_found` old gather again, new scratch under a new id, `replace_claim`, spawn, continue as 7.6; `PollFailure` raises with nothing written
  - [x] Success: module imports; pyright strict clean
  - Note:
    - the claim's age is `now - updated_at` (the insert time, or the last `replace_claim`), so a replaced claim's age restarts
    - `unreadable` and `unknown_status` answering-run outcomes (not in the D7 table) raise `SquadronError` with nothing written, like a poll failure
    - a dead-claim restart whose context cannot be gathered again settles the old claim as `waiting_on_pm` with the source reason

- [x] **7.11 Dead-claim tests**
  - [x] One test per D7 row. A late reply after a stall is ignored because the row is no longer `claimed`
  - [x] Success: tests pass

- [x] **7.12 `answer` operation (D9)**
  - [x] `operations/answer.py`: `AnswerRequest` (`run_id`, optional `paused_at`, `text`) validated from a document; `AnswerResult` (`outcome` `recorded` or `rejected`, question key, `answer_seq`, `ResumeResult`, `problems`)
  - [x] Find by `(run_id, paused_at)` or the run's latest `claimed_at`; no row is `rejected / no_such_question` with detail telling to run `handle_pause` from the run's checkout. Text stripped, empty is `rejected / malformed`. `add_pm_answer`, then resume (D8) with the new answer
  - [x] Success: module imports; pyright strict clean
  - Note:
    - `operations/answer.py`: `AnswerRequest` (pydantic, `extra="forbid"`, `run_id`/`text` non-blank after stripping, optional `paused_at`), `AnswerOutcome`, `AnswerRejection` (`no_such_question`, `malformed`), `AnswerResult(outcome, rejection, key, answer_seq, resume, problems)`
    - if `sq` cannot be read when resuming, the PM answer stays recorded and `SquadronError` propagates

- [x] **7.13 `answer` tests**
  - [x] Cases: waiting question recorded and resumed; no question; empty text; unknown fields rejected; `paused_at` omitted picks the latest; override of an automatic answer is recorded and the newest PM answer is precedent in `pm_precedent`; already resumed question gives `not_delivered` and the override stands; `waiting_reason` is not cleared; PM answer skips screen and limit
  - [x] Success: tests pass

**Commit**: `feat: add handle_pause and answer operations`

## 8. CLI and contract docs (D13)

- [x] **8.1 CLI commands**
  - [x] In `cli/main.py` add `amoeba handle_pause <run_id>` and `amoeba answer <run_id> [--paused-at <ts>] --text <answer>`. Both print their result model as JSON on stdout. The CLI alone calls the home helpers and builds `Deps` (task 6.0)
  - [x] Exit codes extend 222's constants: `handle_pause` exits 0 for every outcome including `skipped`; `answer` exits 1 when `rejected`; 2 is usage; 3 is operational (`SquadronError`, `ContextForgeError`, `ConfigError`, `AmoebaHomeError`, any `StoreError`) with the message on stderr
  - [x] Success: `uv run amoeba handle_pause --help` and `answer --help` print usage
  - Note:
    - `cli/main.py` adds `handle_pause RUN_ID` and `answer RUN_ID [--paused-at TS] --text T`; results are printed with `dataclasses.asdict` as JSON (the 223 result models are frozen dataclasses).
    - `Deps` is built by `operations.deps.production_deps(...)`, called only from the CLI with the home helpers.
    - `SquadronError` joins the exit-3 set.
    - Exit codes are the 222 constants (`handle_pause` always exits 0 on a result; `answer` exits 1 when rejected).

- [x] **8.2 CLI subprocess tests**
  - [x] With fake `sq` and `cf` on `PATH`, `HOME` set to a temporary directory holding `.config/squadron/runs/<run_id>.json` (copied from the fixture), and the autouse `AMOEBA_HOME`: `handle_pause` skip exits 0 with JSON; operational failure exits 3 with stderr; `answer` rejected exits 1; usage error exits 2; no test reads the developer's real run files
  - [x] Success: tests pass
  - Note:
    - `tests/cli/test_pause_cli.py` runs the real `amoeba` script with the recorded-`sq` fake (`tests/fake_sq.py`) and a fake `cf` on `PATH`, `HOME` a temp dir holding the copied run file.
    - Covers: skip exit 0; operational failure exit 3 (no `sq` on PATH; missing config); `answer` rejected exit 1; `answer` recorded with a refused resume exit 0; `--paused-at`; usage errors exit 2; `--help`.

- [x] **8.3 Contract docs**
  - [x] Update `docs/store-contract.md`: the nine new columns, the vocabularies, which operation writes each column. Update `docs/config-contract.md` check against the code (both new keys already added in 5.3)
  - [x] Create `docs/cli-contract.md` (frontmatter as the other contract docs): argument shapes, JSON result output and the exit-code table (0, 1, 2, 3 with their causes) for `handle_pause` and `answer`, plus `set_up`'s from 222; 224 extends it for its operations
  - [x] Success: every column in `002_pause_handling.sql` appears in the doc with its writer; the CLI contract matches the code
  - Note:
    - `docs/store-contract.md` gained "Question lifecycle and who writes it" (the nine new columns were already there from task 1.1, each with its writer; the `DeclineReason` values written; resume rules).
    - `docs/config-contract.md` was checked against the code (both keys, example, tests).
    - New `docs/cli-contract.md` covers `set_up`, `handle_pause`, `answer`, JSON results and the exit-code table.
    - `tests/test_contract_docs.py` now also fails if the store contract misses a `DeclineReason`, or the CLI contract misses a command, an exit code, a `HandlePauseOutcome`, a `SkipReason` or an `AnswerRejection`.

**Commit**: `feat: add handle_pause and answer commands and contract docs`

## 9. Live tier, restored tests, hook doc (D14, D15)

- [ ] **9.1 Hook doc**
  - [ ] Write `docs/squadron-hook.md` with the four D14 points: configure `amoeba handle_pause <run_id>` run in the run's directory (the exact config line is deferred to 225, amoeba#35); only repos in a program need it and a run started with the opt-out is left alone; a hand call must run in the run's own checkout until #303; the hook's environment must reach `sq`, `cf`, `git` and model credentials
  - [ ] Success: the doc has frontmatter and states all four points

- [ ] **9.2 Live pause pipeline and test**
  - [ ] Using `tests/live/pause/asks_question.yaml` (created in task 2.2), add a live test that makes a throwaway worktree registered as a member under a test `AMOEBA_HOME`, starts the run, calls `amoeba handle_pause` on the pause, and asserts the record (question, passages, answer, `resumed`) and that the run left the pause. Gate on `AMOEBA_LIVE_*` like the existing live tests; outside the default suite
  - [ ] Success: with `AMOEBA_LIVE_*` set the test passes; without it the default suite does not collect it

- [ ] **9.2a Live case for the hook opt-out**
  - [ ] No live test covers it. In `tests/live/pause/` add a pipeline whose `pipeline.on_pause_command` (see `sq run --help`) writes a marker file and which ends paused. A test starts it with the argv from the answering run's builder (task 5.6, so `--no-pause-hook` comes from the one constant) and asserts no marker exists; the control starts the same pipeline without the flag and asserts the marker exists. No model call is needed. Gate like the other live tests
  - [ ] Success: with the flag no marker; without it the marker; outside the default suite

- [ ] **9.3 Restore waiting live tests**
  - [ ] Restore the `waits on 223` files named in the audit's Live tests section (`stage_harness.py`, `test_answering_run.py`) from the commit noted in task 0.2 (`git show <commit>:<path>`) and rewrite each to drive `handle_pause`; each keeps its claim. The restore brings back only those two files: `launch_rig.py`, `observe_support.py` and `question_harness.py` are deleted too, so treat them as a template and write what the rewrite needs
  - [ ] The kept live files (`harness.py`, `test_pipeline_run.py`, `test_precedence.py`, `question_tails.py`) still import and collect with the names listed in task 3.1; run `uv run pytest tests/live --collect-only` with `AMOEBA_LIVE_*` set and fix any import that 221 or this slice moved
  - [ ] Success: with `AMOEBA_LIVE_*` set the restored files pass; the default suite still passes

- [ ] **9.4 Comment on squadron#303**
  - [ ] #303 is closed and shipped only the working directory (`sq runs list --json`, `sq` 0.24.24). Post one comment on `ecorkran/squadron#303` asking for `params` and `execution_mode` in `sq runs wait --json` (or `sq runs list --json`), using `gh issue comment`; if that is not possible on a closed issue, open a new issue that cites #303 with `gh issue create`. Record the URL under this task
  - [ ] Success: the URL is noted; if `gh` fails, write `BLOCKED: <error>` and stop

## 10. Final validation

- [ ] **10.1 Full checks**
  - [ ] Run the checks once; fix failures introduced by this slice
  - [ ] Success: all four pass; `answering.yaml` has no hard-coded authorize list; no module outside `home.py` reads `AMOEBA_HOME` or calls `Path.home`

- [ ] **10.2 Verification walkthrough**
  - [ ] Run the design's Verification Walkthrough steps 1 to 5 from the repo root with a scratch `AMOEBA_HOME` and both wait keys set. Include the barred-then-allowed check: an answer authorizing a barred item waits on the PM, then after `set_up` allows the item for the member the same question is answered
  - [ ] Record each step's observed result in a note under this task. An unexpected result is a defect in this slice: fix it, or write `BLOCKED:` with the evidence
  - [ ] Success: the notes show `skipped / not_a_project`, `resumed`, the store rows, `skipped / settled`, and `recorded` for `answer`

**Commit**: `test: add live pause tier, restore answering tests, add hook doc`
