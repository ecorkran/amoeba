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
dateUpdated: 20261108
status: not_started
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

- [ ] **0.1 Create the branch**
  - [ ] Read `cf config get git.integration_branch`; the target is its value, or `main` if empty
  - [ ] Confirm the working tree is clean and you are on the target
  - [ ] `git checkout -b 223-slice.pause-handling {target}`
  - [ ] Success: `git branch --show-current` prints `223-slice.pause-handling`

- [ ] **0.2 Confirm 222 and locate inputs**
  - [ ] Confirm `src/amoeba/store/`, `src/amoeba/config/` and `src/amoeba/operations/` exist and `amoeba set_up` runs; if not, write `BLOCKED: slice 222 not merged` under this task and stop
  - [ ] Open the audit's Slice 182 section and Live tests section. Note under this task: the 182 take and rewrite groups (for `program_concept` and `program_members`, D11), the list of `waits on 223` test files and the commit to restore them from
  - [ ] Find the module of each of: `poll_run`, `RunSummary`, `PollFailure`, `read_answer`, `read_check`, `decide_answer`, `evaluate_gate`, `prepare_scratch`, `compose_instructions`, `read_committed_sources`, `read_target`, `sources_reason`, `SourcesProblem`, `answering_for`, `resolve_member`, `project_of`, `members_of`, `programs`, `DeclineReason`, `QuestionState`, `ResumeOutcome`, `PassageRef`, `AnsweringEvidence`, `run_cf` (note "absent" for any that don't exist); note import paths
  - [ ] Run the checks once and note the baseline; failures present before this slice are written down, not fixed
  - [ ] Success: a note lists the audit groups, the restore commit, each import path and the baseline result

## 1. Store and migration (D4, D10)

- [ ] **1.1 Migration `002_pause_handling.sql`**
  - [ ] Create `store/schema/002_pause_handling.sql`: `ALTER TABLE … ADD COLUMN` only, all nullable. `questions`: `slice_label`, `source_commit`, `passages`, `waiting_detail`, `evidence`. `answers`: `cited`, `resume_detail`, `resume_log`, `resume_at` (D10 table)
  - [ ] Set `EXPECTED_SCHEMA_VERSION` to 2
  - [ ] Success: a version-1 store opens and migrates to version 2 with data intact

- [ ] **1.2 Migration tests**
  - [ ] Extend the store tests: build a version-1 store with a question and an answer row, migrate, assert the rows survive and the nine columns exist and are null
  - [ ] Success: tests pass; the existing SQL `CHECK`-vs-enum pin tests still pass

- [ ] **1.3 JSON column serializers**
  - [ ] In `store/question_json.py` add one serializer and one parser each for `passages` (array of `PassageRef`: id, kind, source, date), `evidence` (`AnsweringEvidence`: proposed answer, citations, check verdict and reason) and `cited` (array of passage ids). Use `PassageRef` and `AnsweringEvidence` from the modules recorded in task 0.2; if 221 has no such type, define it in `answering/values.py` (which `store` may already import)
  - [ ] Parsers raise a typed `StoreError` subclass naming the column on bad JSON; no silent empty value
  - [ ] Success: module imports; pyright strict clean

- [ ] **1.4 Serializer tests**
  - [ ] Round-trip test per column; a bad-JSON test per parser
  - [ ] Success: tests pass

- [ ] **1.5 Question reads, insert and claim moves**
  - [ ] In `store/questions.py` add reads `get_question(run_id, paused_at)`, `latest_question(run_id)` (latest `claimed_at`), `any_answering_run_id(run_id)` (true if some question has that `answering_run_id`)
  - [ ] Add `insert_question(...)`: `INSERT … ON CONFLICT (run_id, paused_at) DO NOTHING`, returns whether this call wrote the row; state `claimed` (with `answering_run_id`, passages, slice label, source commit) or `waiting_on_pm` (with `waiting_reason`, `waiting_detail`)
  - [ ] Add compare-and-set moves, each `UPDATE … WHERE state = 'claimed' AND answering_run_id = ?`, returning whether a row changed: `settle_waiting` (reason, detail, evidence) and `replace_claim` (swap `answering_run_id` and passages old to new, for D7 `not_found` old)
  - [ ] Every write is one short `BEGIN IMMEDIATE` transaction; none is held across a subprocess
  - [ ] Success: module imports; pyright strict clean

- [ ] **1.6 Question tests**
  - [ ] Reads: `get_question` and `latest_question` return the right row (two questions on one run, different `claimed_at`); `any_answering_run_id` true for a known id and false otherwise
  - [ ] Insert race: second insert returns false and leaves the first row
  - [ ] Each compare-and-set returns false when the state or `answering_run_id` differs, true otherwise
  - [ ] Success: tests pass

- [ ] **1.7 Answer reads and writes**
  - [ ] In `store/answers.py` (a separate module to keep `questions.py` near ~300 lines; `store/questions.py` re-exports these names so the design's `store.questions` interface holds) add reads `answers_of(question)`, `latest_answer(question)` (highest `seq`), `automatic_answer_count(run_id)` (rows with `answered_by = 'answerer'`, this `run_id`, any `paused_at`)
  - [ ] Add `add_pm_answer`: one transaction adds a `pm` answer row and sets `answered` from any state; does not clear `waiting_reason` or `waiting_detail`
  - [ ] Add `record_resume(answer, outcome, detail, log, at)` with `WHERE resume_outcome IS NULL OR resume_outcome = 'refused'`
  - [ ] Success: module imports; pyright strict clean

- [ ] **1.8 Answer read and write tests**
  - [ ] `answers_of` returns all rows in `seq` order; a newer PM answer adds a row and `latest_answer` returns it
  - [ ] `automatic_answer_count` ignores PM answers and counts across `paused_at` values
  - [ ] `add_pm_answer` sets `answered` from `claimed` and from `waiting_on_pm` and leaves `waiting_reason` in place
  - [ ] `record_resume` never overwrites `resumed` or `not_delivered`, does overwrite `refused`
  - [ ] Success: tests pass

- [ ] **1.9 Automatic settle with gate**
  - [ ] In `store/answers.py` add `settle_answered(…, gate)`, compare-and-set `claimed → answered` (same guard as 1.5). In one `BEGIN IMMEDIATE` transaction: count `prior` with `automatic_answer_count`, call `gate(prior)` (returns a decline or `None`); on a decline write nothing and return it; otherwise do the compare-and-set and insert the `answerer` answer row with `cited`; return `settled`, the decline, or `lost`
  - [ ] Success: module imports; pyright strict clean

- [ ] **1.10 Automatic settle tests**
  - [ ] A PM answer during a claim makes the later `settle_answered` return `lost`; a gate that declines writes nothing and its decline is returned; `gate` receives only automatic answers in `prior`; success writes the `answerer` row with `cited`
  - [ ] Success: tests pass

- [ ] **1.11 PM precedent read**
  - [ ] Add `pm_precedent(store, member_id)` in `store/answers.py`: the newest PM answer for each of the member's questions, with question text, slice label and `recorded_at`; automatic answers excluded
  - [ ] Add tests: two PM answers on one question gives only the newer; an automatic-only question gives nothing; another member's questions are excluded
  - [ ] Success: tests pass

**Commit**: `feat: add pause-handling store migration and question access`

## 2. Run file, home paths and `sq` fixtures (D2, D12, D15)

- [ ] **2.1 Home paths (D12)**
  - [ ] In `config/home.py` add `answering_dir()` (`amoeba_home() / "answering"`), `logs_dir()` (`amoeba_home() / "logs"`), `squadron_runs_dir()` (`Path.home() / ".config" / "squadron" / "runs"`); directory names as constants in that file
  - [ ] Extend `tests/config/test_home.py`: first two sit under `AMOEBA_HOME`; the third is under the (test-set) `HOME`; the AST test from 222 (only `home.py` calls `Path.home`) still passes
  - [ ] Success: tests pass

- [ ] **2.2 Record `sq` fixtures (D15)**
  - [ ] Create `tests/live/pause/asks_question.yaml`: a dispatch that ends on a question about file length limits that the repo's rules settle. Task 9.2 reuses it
  - [ ] Create `tests/fixtures/squadron/` with real 0.24.23 output (or the installed version; record it) of `sq runs wait <id> --timeout 0 --json` for: an `agent_question` pause, a pause of another checkpoint kind, a running run, a completed run. Name files for the case. Capture by running real `sq` (the `agent_question` pause comes from `asks_question.yaml`); never hand-write
  - [ ] Copy one real schema-5 run file from `~/.config/squadron/runs/` into `tests/fixtures/squadron/` as the `run_file` fixture; strip nothing that the reader parses
  - [ ] Add `tests/fixtures/squadron/README.md` with `sq --version` and capture date
  - [ ] If a case cannot be captured, write `BLOCKED: cannot record <case>` under this task and stop
  - [ ] Success: each JSON fixture parses; the pause fixture has `checkpoint.kind`, `paused_at` and `question`

- [ ] **2.3 Fake `sq` helper**
  - [ ] Add a test helper that writes a fake `sq` first on `PATH`: replays a named fixture for `sq runs wait`, records its argv to a file for `sq run …` (including `--resume` with `--instructions`), exits with a configured code. A second helper returns an injectable `poll_run` fake
  - [ ] Success: running the written script with the pause fixture prints that fixture; a `sq run` call appears in the argv record

- [ ] **2.4 Run file reader (D1, D2)**
  - [ ] Create `upstream/squadron/run_file.py`: `ExecutionMode` (`StrEnum`: `sdk`, `prompt-only`), `RunFacts(params: dict[str, str], execution_mode)`, `RunFileProblem` (names file and field), `read_run_facts(runs_dir, run_id) -> RunFacts | RunFileProblem`. Check `schema_version` is 5. Missing file, other version, bad JSON, missing field and unknown mode are each a `RunFileProblem`
  - [ ] Imports nothing from `answering`; `runs_dir` is an argument
  - [ ] Add `tests/upstream/test_run_file.py`: the real fixture parses with the right params and mode; one test per problem kind; no case returns `sdk` by default
  - [ ] Success: tests pass

**Commit**: `feat: add run file reader, home paths and Squadron recordings`

## 3. Answering library changes (D11)

- [ ] **3.1 Not-authorized file**
  - [ ] Add `pipeline_file.NOT_AUTHORIZED_FILE = "not_authorized.md"`; add `inputs.render_not_authorized(items)`: one `key: description` bullet per item; empty list renders `No item is barred for this repository.`
  - [ ] `prepare_scratch` writes the file
  - [ ] Success: module imports; pyright strict clean

- [ ] **3.2 Rewrite `answering.yaml` prompts**
  - [ ] In both steps list `not_authorized.md` in `prompt_files` after `passages.md`. Replace the hard-coded authorize list in both prompts with text saying the list follows the passages; the answer step must decline, and the check step reply no, when an answer would authorize anything on it
  - [ ] Success: `answering.yaml` contains no hard-coded authorize list (grep for the old items finds none)

- [ ] **3.3 Not-authorized tests**
  - [ ] Test rendering: two items, empty list. Test `prepare_scratch` writes the file with the items given. Update the existing pin test so it covers the new file and the `prompt_files` order
  - [ ] Success: tests pass

- [ ] **3.4 Program passages**
  - [ ] Add `ProgramSources` (concept as a `SourceFile`: member id, path, commit, date, text; and the member list). Port `program_concept` and `program_members` from the 182 take group; if that group is empty, write them new from the design of slice 182
  - [ ] `answering.passages` gains both kinds and their rendering; `assemble` takes `ProgramSources`; both prompts list the two new kind words
  - [ ] Make plan row selection in `source_reads` optional when `slice_ref` is `None`
  - [ ] Find every existing caller of `assemble` and `source_reads` and every existing test of them (grep under `src` and `tests`); update each to the new signatures in this task
  - [ ] Success: module imports; pyright strict clean; all four checks pass

- [ ] **3.5 Program passage and no-slice tests**
  - [ ] Tests: `assemble` with program sources emits both kinds; with no slice it emits rules, program and precedent passages and no plan passages; `source_reads` with `slice_ref=None` selects no plan rows
  - [ ] Success: tests pass

- [ ] **3.6 Import boundary**
  - [ ] Add to `tests/test_import_boundaries.py`: `answering` imports nothing from `store`, `config` or `operations`. Confirm `store` importing `answering.values` is allowed
  - [ ] Success: test passes; adding a forbidden import makes it fail (verify once, then revert)

**Commit**: `feat: add program passages and not-authorized list to answering library`

## 4. Context (D5)

- [ ] **4.1 Record slice-lookup fixtures**
  - [ ] Add to `tests/fixtures/context_forge/` real `cf list initiatives --json -a` output and `cf list slices <index> --json` output for plans in this repo, including an index that is in no plan. Capture with real `cf`; do not hand-write. Extend the README with `cf --version` and date
  - [ ] Success: files parse as JSON; one slice index from the run fixture's range is in a plan, one is in none

- [ ] **4.2 Slice resolution in `pause_context.py`**
  - [ ] Define `TARGET_PARAM_KEY = "slice"` (the run parameter holding the slice index) and `NO_SLICE_LABEL = "none"` once in `operations/pause_context.py`
  - [ ] `resolve_slice(run_facts, cf_run)`: parse `params[TARGET_PARAM_KEY]` as an index; search plans of initiatives with index no higher than it, highest first; label `<index> <name>`. A non-integer value, or one in no plan, is `sources_missing`. Absent parameter: the no-slice label (D5). A failing `cf` call is `sources_unreadable` with the output head
  - [ ] Success: module imports; pyright strict clean

- [ ] **4.3 Slice resolution tests**
  - [ ] Using the 4.1 fixtures: slice found; slice in no plan and non-integer parameter each give `sources_missing`; no parameter gives the no-slice label; failing `cf` gives `sources_unreadable`
  - [ ] Success: tests pass

- [ ] **4.4 Program sources read**
  - [ ] `read_program_sources(...)` in `pause_context.py`: concept member and path from `programs`, member list from `members_of`, concept member's checkout from `project_of(reference=…).project_path`, concept file read through the git allowlist at that checkout's target (the asker's own pinned commit if it is the concept member). Returns `ProgramSources` (task 3.4)
  - [ ] Success: module imports; pyright strict clean

- [ ] **4.5 Program sources tests**
  - [ ] Using a temporary git repo: concept read at the other member's target; concept member equal to the asker uses its own pinned commit; unreadable file gives its `DeclineReason` through `sources_reason`
  - [ ] Success: tests pass

- [ ] **4.6 `gather`**
  - [ ] `gather(checkout, member, program, run_facts, question, settings, cf_run) -> PauseContext | SourcesProblem` combines: `resolve_slice`; committed rules and plan files via `read_committed_sources` from the question's checkout at `read_target` (`rules_paths` from `answering_for`); `read_program_sources`; precedent from `questions.pm_precedent`. Each `SourcesProblem` maps to its `DeclineReason` through `sources_reason`
  - [ ] Success: module imports; pyright strict clean

- [ ] **4.7 `gather` tests**
  - [ ] Using a temporary git repo and the 4.1 fixtures: full context with a slice; no-slice context has no plan passages; precedent passages present after a PM answer and absent for automatic answers; a failing sub-step returns its problem and nothing partial
  - [ ] Success: tests pass

**Commit**: `feat: gather pause context from slice, program and precedent`

## 5. Answering run (D6)

- [ ] **5.1 Spawn helper**
  - [ ] Create `operations/processes.py`: `spawn_detached(argv, cwd, logs)` (exclusive log files, own session, `stdin` from `/dev/null`, inherited environment, closed descriptors) returning a handle that can wait with a timeout and terminate its process group; `stderr_tail(path, n)`. Imports nothing from Amoeba
  - [ ] Success: module imports; pyright strict clean

- [ ] **5.2 Spawn helper tests**
  - [ ] Tests with real short subprocesses: logs are written; a second spawn to the same log path fails (exclusive); wait times out on a sleeping child; terminate kills the child and its own child; `stdin` is empty; `stderr_tail` returns the last lines
  - [ ] Success: tests pass

- [ ] **5.3 Shared `Deps`**
  - [ ] Create `operations/deps.py` with one frozen dataclass `Deps` (cf runner, `poll_run` with its timeout, spawner, `answering_dir`, `logs_dir`, `squadron_runs_dir` paths), imported by `answering_run`, `resume`, `handle_pause`, `pause_existing` and `answer`. It imports nothing from those modules, so there is no cycle. The injected spawner and poller used by tasks 5.6 onward come from it
  - [ ] Success: module imports; pyright strict clean

- [ ] **5.4 Config keys**
  - [ ] Add required keys `answering_wait_seconds` and `resume_wait_seconds` (number > 0) to the config model; a missing or non-positive value is a `ConfigError`; no default in code. Update `docs/config-contract.md` with both keys
  - [ ] Add both keys to every existing test config fixture and to the example config in `docs/config-contract.md`, so existing configs and tests still load
  - [ ] Add tests: missing, zero, negative, non-number each fail; valid passes
  - [ ] Success: all four checks pass; the contract doc lists both keys

- [ ] **5.5 Scratch and run id**
  - [ ] In `operations/answering_run.py` restore `mint_run_id` (`amoeba-<UTC stamp>-<12 hex>`) from the deleted version (find it in the commit before slice 221) and add `make_scratch(answering_dir, run_id, ...)`: exclusive directory create, then `prepare_scratch` including the not-authorized file. An `OSError` returns a failure value for `answering_launch_failed`
  - [ ] Add tests: id format; two ids differ; existing directory fails; scratch holds `passages.md` and `not_authorized.md`
  - [ ] Success: tests pass

- [ ] **5.6 Start and wait**
  - [ ] `start(...)` builds `sq run <answering.yaml> <answer_model> --run-id <id> -p check-model=<check_model>` (no pause opt-out flag) and spawns it in the scratch with logs at `logs_dir() / "answering" / <id>.{stdout,stderr}.log`; a spawn error is `answering_launch_failed`
  - [ ] `wait(...)`: wait up to `answering_wait_seconds`; on timeout terminate the process group and return `answering_run_stalled` (`no result after <n> seconds`); otherwise one `poll_run(id)`; a `PollFailure` is `answering_run_failed`
  - [ ] Success: module imports; pyright strict clean

- [ ] **5.7 Start and wait tests**
  - [ ] Using the fake `sq` and injected spawner and poller: argv is exactly as designed (assert no pause flag); spawn error, stall and poll failure each give their decline reason; no store transaction is open while the spawner or poller runs
  - [ ] Success: tests pass

- [ ] **5.8 Settle**
  - [ ] `settle(...)`: if completed, `read_answer` and `read_check` from scratch, `decide_answer(summary, answer, check, passage_ids)` with the claim's passage ids; a `Confirmed` answer goes to `settle_answered` with `gate = lambda prior: evaluate_gate(question, prior, answer=…, settings=…)` (the count happens inside the store transaction, 1.9). A gate decline or a `decide_answer` decline goes to `settle_waiting` with the reason, bounded detail and evidence. `settle` returns a `SettleResult` defined in `answering_run.py`: `answered`, `waiting` (reason, detail) or `superseded` (any `lost`/false return)
  - [ ] Success: module imports; pyright strict clean

- [ ] **5.9 Settle tests**
  - [ ] Cases: confirmed and gate passes gives `answered` with an `answerer` row and `cited`; check said no gives `check_said_no`; screen refusal gives `reserved_term`; an item barred for one member and allowed for another gives different results; PM answer during settling gives `superseded`; answer limit counts automatic answers only (the gate declines with `answer_limit_reached` at the limit, and nothing is written for the answer)
  - [ ] Success: tests pass

**Commit**: `feat: add answering run start, wait and settle`

## 6. Resume (D8)

- [ ] **6.0 `ResumeResult` model**
  - [ ] Create `operations/pause_models.py` with `ResumeResult` (`outcome`: `resumed`, `refused`, `not_delivered`; `detail`; `resume_log`). Task 7.1 adds the other models to this file
  - [ ] Success: module imports; pyright strict clean

- [ ] **6.1 Implement `resume.py`**
  - [ ] `resume.resume(store, question, answer_seq, *, deps) -> ResumeResult`. `RESUME_POLL_INTERVAL_SECONDS = 0.5` defined in the module
  - [ ] Step 1: `poll_run(run_id)`; not `paused` or a different `paused_at` gives `not_delivered`, nothing started
  - [ ] Step 2: `sq run --resume <run_id> --instructions <compose_instructions(question, answer)>` via `spawn_detached`, `cwd = questions.checkout`, logs at `logs_dir() / "resume" / <run_id> / <answer_seq>-<UTC stamp>.{stdout,stderr}.log` (stdout path is `resume_log`); spawn error is `refused`
  - [ ] Step 3: poll every interval up to `resume_wait_seconds`. `running`, or moved past (other `paused_at`, `completed`, `failed`) is `resumed`; child exited with the run still at this pause is `refused` with `stderr_tail` as detail; timeout with child alive and run unchanged: terminate the process group, wait for exit, poll once more; still at this pause is `refused` (`not running after <n> seconds`), `running` or moved past is `resumed` (`resume process terminated after taking the run`)
  - [ ] Step 4: `record_resume`
  - [ ] Success: module imports; pyright strict clean

- [ ] **6.2 Resume tests**
  - [ ] Every branch with injected poller and spawner: not paused, different `paused_at`, running, moved past, paused again before a poll saw running, child exited at the pause with stderr tail, timeout then still paused, timeout then running after the kill
  - [ ] `--instructions` is a single argv element holding the composed text, including text with spaces, quotes and a leading `…`
  - [ ] `resumed` and `not_delivered` are never overwritten; of two racing resumes the second's refusal does not replace the first's `resumed`
  - [ ] No store transaction is open while spawning or polling
  - [ ] Success: tests pass

**Commit**: `feat: add shared resume for paused runs`

## 7. `handle_pause` and `answer` (D3, D4, D7, D9)

- [ ] **7.1 Result models and `SkipReason`**
  - [ ] In `operations/pause_models.py` (created in 6.0) add `SkipReason` (`StrEnum`, the D3 table's eleven reasons) and `HandlePauseResult` (`outcome`: `skipped`, `waiting_on_pm`, `superseded`, `resumed`, `refused`, `not_delivered`; plus `skip_reason` or `waiting_reason`, `detail`, question key, claimed `checkout`, `answering_run_id`, `answer_seq`). `handle_pause.py` re-exports both, so the design's import path works. The split keeps each module near the ~300-line guideline
  - [ ] Success: module imports; pyright strict clean

- [ ] **7.2 Eligibility checks (D3)**
  - [ ] In `operations/pause_eligibility.py`, implement the checks in D3's order, first failure wins: `not_paused`, `not_agent_question` (detail gives raw kind), `no_question_text`, `answering_run` (via `any_answering_run_id`), `not_a_project`, `not_in_program`, `prompt_only` (run file read only after membership; a `RunFileProblem` raises `SquadronError`), `other_member`
  - [ ] A Squadron or `cf` failure raises the operational error; it is never a skip
  - [ ] Success: module imports; pyright strict clean

- [ ] **7.3 Eligibility tests**
  - [ ] One test per `SkipReason` that these checks produce, using the fake `sq`, fake `cf` and store. Include: run-file problem in a non-member repo is not an error; run-file problem in a member raises; a failing `sq` or `cf` raises and writes nothing
  - [ ] Success: tests pass

- [ ] **7.4 Claim step for a new question (D4, D6)**
  - [ ] In `operations/handle_pause.py` (the entry point, calling `pause_eligibility`), when no row exists: `resolve_member`, `answering_for`; if `automatic_answer_count` already meets `answer_limit`, insert `waiting_on_pm / answer_limit_reached` and stop; `gather`; make scratch; insert in one transaction as `claimed` (with answering run id and passages) or `waiting_on_pm` (failure reason). A lost insert removes the scratch and returns `skipped / already_claimed`. Result carries `checkout`
  - [ ] Success: module imports; pyright strict clean

- [ ] **7.5 Claim step tests**
  - [ ] Answer limit already met inserts `waiting_on_pm / answer_limit_reached` and starts nothing; context failure inserts `waiting_on_pm` and starts nothing; scratch `OSError` inserts `waiting_on_pm / answering_launch_failed`; lost insert race removes scratch and skips
  - [ ] Success: tests pass

- [ ] **7.6 Answer step for a new claim (D6, D8)**
  - [ ] After a successful claim: start, wait, settle (tasks 5.6 and 5.8); only an `answered` settle is resumed (D8). `waiting` and `superseded` settles map to the matching `HandlePauseResult` outcome without resuming
  - [ ] Success: module imports; pyright strict clean

- [ ] **7.7 Answer step tests**
  - [ ] Answered and resumed end to end with fakes; declined answer is not resumed; `superseded` is returned and not resumed
  - [ ] Success: tests pass

- [ ] **7.8 Settled-row paths (D3, D4)**
  - [ ] In `operations/pause_existing.py` (called by `handle_pause` when a row exists): `answered` with latest answer not `resumed` or `not_delivered`: resume with the latest answer, starting no answering run. `waiting_on_pm` and settled answers: `skipped` with `waiting_on_pm` or `settled`
  - [ ] Success: module imports; pyright strict clean

- [ ] **7.9 Settled-row tests**
  - [ ] One test per path above. A refused earlier resume is retried with the recorded answer and no answering run starts
  - [ ] Success: tests pass

- [ ] **7.10 Dead-claim paths (D7)**
  - [ ] In `pause_existing.py`, `claimed`: apply the D7 table with `poll_run(answering_run_id)` and the claim age against `answering_wait_seconds`. Running and young skip; running and old `settle_waiting` with `answering_run_stalled`; `completed`, `failed`, `paused`, `orphaned` settle from scratch then resume; `not_found` young skip; `not_found` old gather again, new scratch under a new id, `replace_claim`, spawn, continue as 7.6; `PollFailure` raises with nothing written
  - [ ] Success: module imports; pyright strict clean

- [ ] **7.11 Dead-claim tests**
  - [ ] One test per D7 row. A late reply after a stall is ignored because the row is no longer `claimed`
  - [ ] Success: tests pass

- [ ] **7.12 `answer` operation (D9)**
  - [ ] `operations/answer.py`: `AnswerRequest` (`run_id`, optional `paused_at`, `text`) validated from a document; `AnswerResult` (`outcome` `recorded` or `rejected`, question key, `answer_seq`, `ResumeResult`, `problems`)
  - [ ] Find by `(run_id, paused_at)` or the run's latest `claimed_at`; no row is `rejected / no_such_question` with detail telling to run `handle_pause` from the run's checkout. Text stripped, empty is `rejected / malformed`. `add_pm_answer`, then resume (D8) with the new answer
  - [ ] Success: module imports; pyright strict clean

- [ ] **7.13 `answer` tests**
  - [ ] Cases: waiting question recorded and resumed; no question; empty text; unknown fields rejected; `paused_at` omitted picks the latest; override of an automatic answer is recorded and the newest PM answer is precedent in `pm_precedent`; already resumed question gives `not_delivered` and the override stands; `waiting_reason` is not cleared; PM answer skips screen and limit
  - [ ] Success: tests pass

**Commit**: `feat: add handle_pause and answer operations`

## 8. CLI and contract docs (D13)

- [ ] **8.1 CLI commands**
  - [ ] In `cli/main.py` add `amoeba handle_pause <run_id>` and `amoeba answer <run_id> [--paused-at <ts>] --text <answer>`. Both print their result model as JSON on stdout. The CLI alone calls the home helpers and builds `Deps` (task 6.0)
  - [ ] Exit codes extend 222's constants: `handle_pause` exits 0 for every outcome including `skipped`; `answer` exits 1 when `rejected`; 2 is usage; 3 is operational (`SquadronError`, `ContextForgeError`, `ConfigError`, `AmoebaHomeError`, any `StoreError`) with the message on stderr
  - [ ] Success: `uv run amoeba handle_pause --help` and `answer --help` print usage

- [ ] **8.2 CLI subprocess tests**
  - [ ] With fake `sq` and `cf` on `PATH`, `HOME` set to a temporary directory holding `.config/squadron/runs/<run_id>.json` (copied from the fixture), and the autouse `AMOEBA_HOME`: `handle_pause` skip exits 0 with JSON; operational failure exits 3 with stderr; `answer` rejected exits 1; usage error exits 2; no test reads the developer's real run files
  - [ ] Success: tests pass

- [ ] **8.3 Contract docs**
  - [ ] Update `docs/store-contract.md`: the nine new columns, the vocabularies, which operation writes each column. Update `docs/config-contract.md` check against the code (both new keys already added in 5.3)
  - [ ] Success: every column in `002_pause_handling.sql` appears in the doc with its writer

**Commit**: `feat: add handle_pause and answer commands and contract docs`

## 9. Live tier, restored tests, hook doc (D14, D15)

- [ ] **9.1 Hook doc**
  - [ ] Write `docs/squadron-hook.md` with the four D14 points: configure `amoeba handle_pause <run_id>` run in the run's directory (the exact config line is deferred to 225, amoeba#35); only repos in a program need it and a run started with the opt-out is left alone; a hand call must run in the run's own checkout until #303; the hook's environment must reach `sq`, `cf`, `git` and model credentials
  - [ ] Success: the doc has frontmatter and states all four points

- [ ] **9.2 Live pause pipeline and test**
  - [ ] Using `tests/live/pause/asks_question.yaml` (created in task 2.2), add a live test that makes a throwaway worktree registered as a member under a test `AMOEBA_HOME`, starts the run, calls `amoeba handle_pause` on the pause, and asserts the record (question, passages, answer, `resumed`) and that the run left the pause. Gate on `AMOEBA_LIVE_*` like the existing live tests; outside the default suite
  - [ ] Success: with `AMOEBA_LIVE_*` set the test passes; without it the default suite does not collect it

- [ ] **9.3 Restore waiting live tests**
  - [ ] Restore the `waits on 223` files named in the audit's Live tests section from the commit noted in task 0.2 and rewrite each to drive `handle_pause`; each keeps its claim
  - [ ] Success: with `AMOEBA_LIVE_*` set the restored files pass; the default suite still passes

- [ ] **9.4 Comment on squadron#303**
  - [ ] Post one comment on `ecorkran/squadron#303` asking for `params` and `execution_mode` (and the run's directory) in `sq runs wait --json`, using `gh issue comment`. Record the comment URL under this task
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
