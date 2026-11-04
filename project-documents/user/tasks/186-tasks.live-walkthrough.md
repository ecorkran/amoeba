---
docType: tasks
slice: live-walkthrough
project: amoeba
lld: user/slices/186-slice.live-walkthrough.md
dependencies:
- 145
- 180
- 181
- 182
- 183
- 184
- 185
projectState: Slices 180 to 185 (program coordination) are designed and tasked; per
  the LLD's Prerequisites 186 starts after they merge, and Task 0.1 verifies that
  against the code. `scripts/answerer_walkthrough.py` (145) builds one scratch project
  with module constants and a one-checkout `Layout`. `scripts/program_walkthrough.py`,
  `scripts/program_walkthrough/`, `tests/runner/program/test_walkthrough_fixture.py`
  and `docs/program-walkthrough.md` do not exist. Nothing is added under `src/` by
  this slice.
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
turns: 20
promptTokens: 954995
cachedTokens: 859484
cacheWriteTokens: 95483
completionTokens: 25524
durationSeconds: 187.0
costUsd: 0.723474
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.7234743
    completionTokens: 25524
---

## Context Summary

- Working on the **live-walkthrough** slice (186), the last slice of initiative 180 (program coordination). It runs coordination end to end on real Squadron runs, real agents and real repos, in three cases: a new slice from source, an already-met request from source, and a request from release that waits for the PM's edge resolution.
- **Current state:** see `projectState`.
- **Dependencies:** 145 (the answerer walkthrough: scripts, helpers and doc this slice follows); 180 (request-run pipeline and its live variables); 181 (program store, `register-program`, `program` listings); 182 (program passages, `tests/runner/answering/program_rig.py`); 183 (edges, release, `resolve-edge`, edge rows on `program-blocked`); 184 (request runs, `requests` config); 185 (the `request` outcome of the answering run, `request_limit`).
- **What this slice delivers:** a project parameter on three of 145's helpers; three scratch project trees; one deterministic fixture test; `scripts/program_walkthrough.py` (`setup`); `docs/program-walkthrough.md`; the three live cases recorded in this file; and every captured question tail, answer-step request reply and request-run reply added to the fixtures. No product code changes.
- **Next planned work:** 160 (notification bridge) and 200 (program conversation), outside this slice.

**Branch:** read the target (`cf config get git.integration_branch`; empty means `main`). Before Task 0.1, create `186-slice.live-walkthrough` from the target and work there. No task merges or pushes this slice's branch. Merging follows the code review. The only git merge in this file is a walkthrough PM action inside the throwaway checkout under `D` (Task 9.3, LLD D4 item 2); it never touches this repository.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/186-slice.live-walkthrough.md` at the named decision (D1 to D9) or section. Paths are relative to the repository root. Follow `.claude/rules/python.md`: ruff and strict pyright, no silent fallbacks, every `try/except` justified. Read each file before editing it. Keep each file near 300 lines and each function near 50. A defect found in 180 to 185 is filed as an issue (D7), never fixed here. Where the code of 180 to 185 names a command, flag, column or state differently from their designs, follow the code and the `--help` output, and record `LLD name → code name` under Task 0.1.

**Order and blocking:** work tasks in file order. Tasks 1 to 6 need no Squadron release, no model and no keys. Tasks 7 to 12 are live and follow one another. No `BLOCKED:` line is pre-written: Task 5.2 and Task 7.1 run the start-up probe, and only when it fails because the installed `sq` lacks 180's D8 capabilities (the run I/O directory, the guarded commit step, the per-run cost cap `ecorkran/squadron#241`) or 140's D8 (`ecorkran/squadron#284`) does Task 7.1 write a line starting `BLOCKED:` under itself naming the missing capability and those issues, leave itself unchecked and stop. A session that finds that line deletes it and runs the probe again; it continues only if the probe now passes. The release is decided by the probe, never by a version number. Later live tasks name their prerequisite task.

**LLD deviations found while breaking this down (both record the same cause):** a submission is applied only by the resident process (181, 145's Task 3.4 note), so the setup script cannot read `applied` from `inspect program-submissions` (LLD D5, Technical Requirements) and cannot print the asker slices' node ids (D6): neither exists until Amoeba has started. Setup therefore submits the registration and stops; Task 7.1 reads the `applied` outcome and the node ids after start, and the doc carries both commands. Task 12.3 amends the LLD to say so.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before markers that follow Python changes.

**D7 recovery applies to every live case task:** fixture cause, product cause, model judgement and environment, with the 186 additions (LLD D7). Each case runs once. A rerun goes on a new asker slice appended at the end of `notes-cli`'s plan (the next index after 102, since a slice is ready only when the next lower index is `done`), and both runs are recorded. A product defect (broken, or high severity and reasonably likely) is filed as an issue and the case marked `BLOCKED:` on it. A safe outcome that fails to show the case is recorded in the Result and does not block; the case is then closed as shown in part and marked not demonstrated. A failed request is left for the PM's resolution of the asker's block (184, D10); until that withdraws it, `request_limit: 1` blocks a new request to that provider. Any slice entry added or corrected in a scratch checkout is also made in the repository tree under `scripts/program_walkthrough/`, so a later run starts from the same plan; re-run the fixture test after the change. Those tree changes ride in the Task 12 commit.

**Live-result notes:** each live task writes what was observed (record fields, edge waits, journal entries, run ids, commits) in a "Result" sub-item under it. Write only what was seen.

**Live environment:** the five variables `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL`, `AMOEBA_LIVE_MAX_COST_USD`, `AMOEBA_LIVE_REQUEST_MODEL` and `AMOEBA_LIVE_REQUEST_MAX_COST_USD` must be exported where setup runs. `D` is a new directory under `$(mktemp -d)`. The real registry and the real supervisor directory are never written.

---

## 0. Preflight

- [ ] **0.1 Confirm the prerequisite code exists and record its real names** (effort 2)
  - [ ] Create the branch (see Branch). Then read, and change nothing, to confirm each is on the target: 180 (`runner/request_run/`, `probe_slice_writing_pipeline`, `tests/live/request_run/`, `tests/fixtures/slice_writing/`); 181 (`register-program` and the three `program` listings, `docs/process-contract.md`'s program stage section); 182 (`tests/runner/answering/program_rig.py`); 183 (`resolve-edge`, edge rows on `program-blocked` with the edge id in the `context` column per 183 D13); 184 (`ProjectSettings.requests`); 185 (`AnswererSettings.request_limit`, the `requested` question state, `read_answer` and its reply fixtures).
  - [ ] Run `uv run amoeba submit register-program --help`, `uv run amoeba submit resolve-edge --help` and `uv run amoeba inspect --help`. Under this task, record each flag or column name that differs from the LLD as `LLD name → code name`.
  - [ ] Find the fixture files the captures go to: 144's `tests/live/answering/fixtures/question_tails.json`, the fixtures `tests/runner/answering/test_read_answer.py` reads, and `tests/fixtures/slice_writing/`. Record each path under this task.
  - [ ] Read 145's `scripts/answerer_walkthrough.py`, `tests/test_answerer_walkthrough_script.py` and `docs/answerer-walkthrough.md`, which Tasks 1, 4 and 6 build on.
  - [ ] Success: each name was found by reading the code. If code from slice 180, 181, 182, 183, 184 or 185 is absent from the target, write `BLOCKED: slice <n> code is absent from the target` under this task, leave it unchecked, and stop.

## 1. Project parameter on 145's helpers (effort 3)

Per the LLD, D6 "Per-project steps". 145's `build_checkout`, `read_cf_project_id` and `submit_project` read the module constants `TREE`, `PROJECT_ID` and `CF_ARTIFACTS` and the one-checkout `Layout`. They gain one parameter in place; no module is added and nothing is copied.

- [ ] **1.1 Add `ProjectSpec` and thread it through the three helpers**
  - [ ] In `scripts/answerer_walkthrough.py` add a frozen `ProjectSpec(project_id, tree, cf_artifacts, checkout)`. Change `build_checkout`, `read_cf_project_id` and `submit_project` to take the spec (and the directory root for the failure message) instead of reading the constants and `layout.checkout`. `setup()` builds the spec from `PROJECT_ID`, `TREE`, `CF_ARTIFACTS` and `layout.checkout` and passes it, so 145's behavior is unchanged.
  - [ ] Split the live-variable checks in `read_live_settings` into two small functions that other scripts can import: one returning a non-empty variable's value or exiting naming it, one returning a variable that must be a number above zero. `read_live_settings` calls them and behaves as before.
  - [ ] Success: `uv run pytest tests/test_answerer_walkthrough_script.py` passes with no assertion changed; only call-sites of the three helpers may be edited if that test calls them directly. `uv run ruff check` and `uv run pyright` are clean on the script.
- [ ] **1.2 Share the stub tools with the new script's test**
  - [ ] Move the stub `git`, `cf` and `amoeba` writer fixture from `tests/test_answerer_walkthrough_script.py` into a helper module under `tests/` and import it back, unchanged in behavior. Task 4.4 uses it.
  - [ ] Success: `uv run pytest tests/test_answerer_walkthrough_script.py` passes; the helper holds the only copy.

**Commit**: `refactor: add a project parameter to the answerer walkthrough helpers`

---

## 2. Scratch project trees (effort 3)

Per the LLD, D1, D3 and "Scratch Project Contents". Three small trees under `scripts/program_walkthrough/`, each committed later as its checkout's first commit. Nothing in them may name a real project, a credential or a model alias. Each tree follows `file-naming-conventions.md` (front matter, names `000-concept.<name>.md`, `001-initiative-plan.<name>.md`, `architecture/100-arch.<name>.md`, `architecture/100-slices.<name>.md`, under `project-documents/user/` as in `scripts/answerer_walkthrough/project/`) and has a `.gitignore` holding `.env`. Use `cli`, `store` and `export` as the `<name>` of each tree's documents. No provider tree has an initiative in 700 to 709.

- [ ] **2.1 `notes-store/`**
  - [ ] `CLAUDE.md` with two short rules, `.gitignore`, concept, initiative plan (initiative 100), architecture, and a one-slice plan for itself (slice 100).
  - [ ] `src/notes_store/jsonl.py` with `read_notes(path)` and `write_note(path, note)`, and no function that returns notes by tag.
  - [ ] `docs/program-concept.md` in the concept format 182 requires (open 182's design on the concept document and follow it): names the three projects and each one's part. `notes-store` owns note files, reading, writing and querying notes, tags included; `notes-export` owns every output format and is released as a package; `notes-cli` owns commands and depends on the other two. It says nothing about which functions exist today.
  - [ ] Success: the files exist at those paths and the program concept names tag querying under `notes-store` and output formats under `notes-export`.
- [ ] **2.2 `notes-export/`**
  - [ ] `CLAUDE.md`, `.gitignore`, concept, initiative plan (100), architecture, one-slice plan (slice 100), and `src/notes_export/text.py`, a plain-text exporter. No Markdown exporter.
  - [ ] Success: the files exist; a search of the tree for "markdown" finds nothing.
- [ ] **2.3 `notes-cli/`**
  - [ ] `CLAUDE.md`, `.gitignore`, concept, initiative plan (100), architecture, and a slice plan with slices 100 Filter by tag, 101 Import a notes file and 102 Export to Markdown, each with a short description (D3 table).
  - [ ] Each entry ends with the forcing sentence in D3's pattern: before designing anything, write no design and end the reply with one question asking for the named member to provide the named capability, which the slice uses; if the prompt already begins with an answer to that question, write the design instead. Slice 100 names `notes-store` and a function returning the notes that carry a given tag; 101 names `notes-store` and a function that reads every note from a JSON Lines file; 102 names `notes-export` and Markdown export of a list of notes.
  - [ ] The sentences name the member and the capability. They never say "ask the PM", never reserve the question, and never say documents do not count (145's corrections).
  - [ ] Nothing in the tree says that any of the three capabilities exists.
  - [ ] Success: three entries, each ending with a forcing sentence; a search of the `notes-cli` tree for "tag", "JSON Lines" and "Markdown" finds only the three slice entries (descriptions and forcing sentences).

## 3. Fixture test (effort 3)

Per the LLD, D6 "Fixture test". No `sq` and no model. Proves the asker's source assembly over the trees has the passages each case depends on.

- [ ] **3.1 Test** `tests/runner/program/test_walkthrough_fixture.py` (create `tests/runner/program/__init__.py` if the directory lacks it and `tests/runner/` uses package markers)
  - [ ] Read `tests/runner/answering/program_rig.py`, `sources_repo.py`, the shared assembly helpers 145 added beside `sources_repo.py`, and 145's `tests/runner/answering/test_walkthrough_fixture.py`. Reuse them.
  - [ ] Commit every file of the three trees at its relative path on `main` of three repositories. Build the program context with 181's and 182's builders: members `notes-store`, `notes-export`, `notes-cli`, the concept in `notes-store` at `docs/program-concept.md`, each member readable.
  - [ ] For `notes-cli` slices 100, 101 and 102 (initiative 100, rules path `CLAUDE.md`) run `assemble_sources` with that context. Assert the member list names all three members; a `program_concept` passage from `notes-store` is present; it places tag lookup and file reading in `notes-store`'s part and Markdown export in `notes-export`'s part; and the concept, initiative plan, architecture and slice plan of `notes-cli` are among the sources.
  - [ ] Project ids and the program id come from constants imported from `program_walkthrough.py` once Task 4 creates it; until then define them in the test and move them in Task 4.1.
  - [ ] Success: `uv run pytest tests/runner/program/test_walkthrough_fixture.py -v` passes. Temporarily removing the Markdown sentence from the concept makes it fail; restoring it makes it pass.

**Commit**: `feat: add program walkthrough scratch trees and fixture test`

---

## 4. Setup script (effort 4)

Per the LLD, D5 and D6 "Script", "Registry isolation". File: `scripts/program_walkthrough.py`, stdlib only. It imports `ProjectSpec`, `build_checkout`, `read_cf_project_id`, `submit_project` and `run_step` from `answerer_walkthrough` (Task 1). It never opens a store, so `tests/test_writer_guard.py` needs no allow-list entry; confirm that. Project ids (`notes-cli`, `notes-store`, `notes-export`) and the program id `notes` are constants at the top, used by the script, the fixture test and nowhere else.

- [ ] **4.1 Arguments, refusals and constants**
  - [ ] `setup --dir D --env-file F`. Refuse an existing `D` and a missing `F`, naming each. Read the five live variables with Task 1.1's functions and exit naming the first one unset, empty or (for the two costs) not above zero. No defaults.
  - [ ] Define the three `ProjectSpec` values (checkout `D/checkouts/<project>`, the `cf set` pairs for each tree's concept, architecture and plan files) and the program registration members per D5.
  - [ ] Move the project and program id constants the fixture test defined into this module and import them there.
  - [ ] Success: each refusal exits non-zero with its message and creates nothing.
- [ ] **4.2 Build the three projects**
  - [ ] For each project, with `CONTEXT_FORGE_DATA_DIR=D/cf` and `AMOEBA_STORE_DIR=D/store` in the environment, call `build_checkout`, then `read_cf_project_id`, then `submit_project`. Every subprocess goes through `run_step`; the file has no other `subprocess` call.
  - [ ] Success: `git -C D/checkouts/<project> status` is clean and `git log` shows the project's commits for each of the three.
- [ ] **4.3 Register the program, write the config, print**
  - [ ] Submit `register-program` as in D5 (program `notes`, concept member `notes-store`, concept path `docs/program-concept.md`, members and consumption modes as listed there, each with `requests_initiative` 700). Do not read an outcome: it is applied after start (see deviations).
  - [ ] Write `D/projects.yaml` as in D5 with the live values as literals: `notes-cli` on `p4` with the `answerer` section (`request_limit: 1`), `notes-store` and `notes-export` on `p456` with their `requests` section. Use the key names 184 and 185 ship.
  - [ ] Print what was created, the two `export` lines (`AMOEBA_STORE_DIR`, `CONTEXT_FORGE_DATA_DIR`) and the `amoeba start --project-config D/projects.yaml --cf-data-dir D/cf` command.
  - [ ] Success: `D/projects.yaml` is written; Task 4.4 checks that it loads.
- [ ] **4.4 Tests** `tests/test_program_walkthrough_script.py`
  - [ ] Load the script as `tests/test_answerer_walkthrough_script.py` does, with `scripts/` on `sys.path` first so its import of `answerer_walkthrough` resolves. If pyright cannot resolve that import, add `scripts` to the pyright `extraPaths` in `pyproject.toml`.
  - [ ] Using Task 1.2's stubs, with a stub `cf get` that prints a project id derived from its working directory so the three ids differ: an existing `D`, a missing env file and each of the five variables unset are refused by name; a stub `git`, `cf` or `amoeba` exiting non-zero reports step, command and stderr and leaves `D`; a stub `cf` printing no id stops naming the step.
  - [ ] A full stubbed run builds three checkouts and logs, in order, the per-project steps and then one `register-program` call whose members JSON has the three projects with the D5 consumption modes and `requests_initiative` 700.
  - [ ] The config output loads through Amoeba's real project-config loader and carries the five live values literally, with `request_limit` 1 and `pipeline` `p4` for `notes-cli` and `p456` for both providers.
  - [ ] Success: tests pass without a real `cf`, `sq` or model. `uv run ruff check` and `uv run pyright` are clean on the script and the test, and `uv run pytest tests/test_answerer_walkthrough_script.py tests/runner/program/test_walkthrough_fixture.py` still passes.

**Commit**: `feat: add program walkthrough setup script`

---

## 5. Start-up check (effort 2)

Per Development Approach step 3. Needs `cf`, `git` and `amoeba`; no key is used until a run is driven.

- [ ] **5.1 Run setup** against a new directory under `$(mktemp -d)`, a placeholder `.env` file and the five live variables set to the values the earlier live tiers use.
  - [ ] Success: the script prints its exports and exits 0. `CONTEXT_FORGE_DATA_DIR=D/cf cf project list` lists three scratch projects. Each checkout is clean with its first commit, and `.env` is untracked.
- [ ] **5.2 Start Amoeba** with the printed command, observe the start-up log, then stop it.
  - [ ] Success: the log shows the `sq` probe and the slice-writing and answering probes passing, or a probe failure. Record which, with the log line, as a "Result" sub-item. A failure that names only 180's or 140's D8 capabilities is expected here and is not a defect.
  - [ ] A failure that names anything else (for example a config load error) is a defect in Task 4: fix it there before continuing.

No commit marker: this task changes no files when it passes. A fix to Task 2 or Task 4 made here is committed on its own as `fix: {summary}` before Task 6.

---

## 6. Walkthrough doc (effort 3)

Per the LLD, D6 "Doc". `docs/program-walkthrough.md` is the only full walkthrough. Check one file in `docs/` for front matter; `docs/answerer-walkthrough.md` has `docType: reference`.

- [ ] **6.1 Draft the doc**
  - [ ] Sections: purpose; prerequisites (a Squadron release with 180's D8 and 140's D8, keys in a `.env`, the five live variables, `cf`, `git`); set up and start; after start (the `applied` outcome from `amoeba inspect program-submissions`, `amoeba inspect program` showing all three members `readable`, the asker slice node ids from `amoeba inspect nodes --project notes-cli --json` matching `cf_index` 100 to 102); one section per case 1 to 3; final checks.
  - [ ] Each case section holds: the slice to drive, the exact `submit intent ... '{"intent": "drive"}'` command, the PM actions of D4 (and no others), and the rows to check after each hop with the field values from the LLD's Functional Requirements: `inspect questions --json`, `inspect program-blocked --json`, `inspect nodes`, `inspect journal`, and `git log` in each provider checkout.
  - [ ] Case 1 includes the PM's reserved action in `D/checkouts/notes-store` after the provider's slice is `done` and the edge waits `not_on_target`. Case 2 starts only after that action has left `notes-store` clean on `main`. Case 3 reads the edge id from the `context` of the `program-blocked --json` row and runs `submit resolve-edge --by pm --edge-id <id>` (check the flag names with `--help`).
  - [ ] Final checks: with `CONTEXT_FORGE_DATA_DIR` unset, `cf project list` lists no scratch project; the real supervisor directory holds no scratch project; nothing was written outside `D`.
  - [ ] Use the names recorded under Task 0.1. Every command has been checked with `--help` or run in Task 5. State that the results are filled in during Task 12.
  - [ ] Success: every command in the doc has been checked with `--help` or run.
- [ ] **6.2 Link it** from the program stage section of `docs/process-contract.md` with one sentence.
  - [ ] Success: the link resolves to the file.

**Commit**: `docs: add program walkthrough`

---

## 7. Start the program (effort 2)

Per the LLD, D5 and Success Criteria. First live task.

- [ ] **7.1 Start Amoeba and check the program**
  - Prerequisite: Tasks 5 and 6 complete, and the five live variables exported.
  - [ ] Run the start-up probe by starting Amoeba as in Task 5.2. If it fails for a missing capability, write the `BLOCKED:` line (see Order and blocking) and stop.
  - [ ] Check `amoeba inspect program-submissions` shows the registration `applied` and `amoeba inspect program` shows all three members `readable`. Find the three asker nodes with `amoeba inspect nodes --project notes-cli --json` and record their ids.
  - [ ] Success: the registration is `applied`, all three members are `readable`, and slices 100 to 102 are listed for `notes-cli`. If the registration is `rejected`, or a member is not `readable` after a few ticks, the cause is a defect in Task 4 or Task 2: fix it there before continuing.
  - [ ] Result: write the probe lines, the submission outcome and the member rows.

---

## 8. Case 1: a new slice from source (effort 4)

Per the LLD, D2, D3, D4 and Functional Requirements "Case 1". The asker's slices run one at a time: drive 100 only now, and drive 101 only after Task 9.3.

- [ ] **8.1 Drive slice 100 and record the request**
  - Prerequisite: Task 7.1 complete.
  - [ ] Drive slice 100 with `submit intent ... '{"intent": "drive"}'`. Wait for the design question and the answering run.
  - [ ] Check the question record is `requested` and carries a request id, and `program-blocked --json` shows an edge row for `notes-cli` to `notes-store`, unbound until the request run binds it.
  - [ ] A decline on a legitimate need (for example `reserved_term`) is a product finding under D7.
  - [ ] Result: slice 100 design run id, answering run id, record fields, the edge row.
- [ ] **8.2 The provider's request run writes the slice**
  - Prerequisite: Task 8.1 complete.
  - [ ] Wait for `notes-store`'s request run. Check `git -C D/checkouts/notes-store log` has one new commit on `main`; the new commit adds slice 700 in a new requests initiative 700 in the plan files; the edge is bound to it; no `notes-store` node was driven by the PM.
  - [ ] A request run that reports `already_met` for this need, or writes no slice, is model judgement (D7).
  - [ ] Result: request run id, commit, the slice entry, the edge row.
- [ ] **8.3 The provider builds undriven, the PM acts, the asker resumes**
  - Prerequisite: Task 8.2 complete.
  - [ ] Wait until `notes-store` slice 700 is `done` without any `submit intent`. Check the edge waits `not_on_target` (not `branch_head_missing`: that wait would mean no slice branch head was recorded).
  - [ ] Carry out the PM's reserved action from the doc in `D/checkouts/notes-store`: the slice branch `700-slice.<name>` into `main` (D4 item 2). Check the working tree is clean on `main` afterwards.
  - [ ] Check the edge is released, the asker's run resumes with instructions naming `notes-store`, the slice and the commit, the question record is `answered`, and slice 100 is `done`.
  - [ ] A provider review loop that never passes ends in a `paused` block on slice 700, which holds `notes-store`'s checkout: resolve it as the PM and record it.
  - [ ] Result: provider slice and branch, build run id, edge waits seen in order, the merge commit, the release instructions, journal entries, final states.

---

## 9. Case 2: already met, from source (effort 3)

Per the LLD, D3 and Functional Requirements "Case 2". Slice 101's capability, `read_notes`, already exists in `notes-store`.

- [ ] **9.1 Drive slice 101 and record the outcome**
  - Prerequisite: Task 8.3 complete, `notes-store` clean on `main` (`git status`), slice 100 `done`.
  - [ ] Drive slice 101. Check the question record is `requested`, `notes-store`'s request run ends `met` with a commit, `git merge-base --is-ancestor <commit> main` in `D/checkouts/notes-store` succeeds, and `git log` shows no commit added by the run.
  - [ ] Check no new node exists in `notes-store`, the edge is released through the same reachability observation, the asker's resume instructions name that commit, and slice 101 is `done`.
  - [ ] A request run that writes a slice for this need is model judgement (D7); record it and rerun once on a fresh `notes-cli` index.
  - [ ] Result: run ids, the commit, the edge row, the instructions, final states.

---

## 10. Case 3: from release (effort 3)

Per the LLD, D1, D4 and Functional Requirements "Case 3". `notes-export` is consumed `from_release`.

- [ ] **10.1 Drive slice 102 and record the request and the build**
  - Prerequisite: Task 9.1 complete.
  - [ ] Drive slice 102. Check the question record is `requested` (not declined `reserved_term`), and `notes-export`'s request run adds slice 700 in a new requests initiative 700, committed to `main`; the slice runs undriven and goes `done`.
  - [ ] A `reserved_term: release` decline of this need is a product finding: file an issue against 185's request screen (D7).
  - [ ] Result: run ids, the request commit, the slice, final provider state.
- [ ] **10.2 The PM's edge resolution releases the asker**
  - Prerequisite: Task 10.1 complete.
  - [ ] Check the edge waits `awaiting_release` after the slice is `done`, and the asker is still blocked. Read the edge id from the `context` of its `program-blocked --json` row.
  - [ ] Submit `amoeba submit resolve-edge` as the doc gives it. Check the edge is released, the asker's resume instructions name `notes-export`, the slice and the commit, and slice 102 is `done`.
  - [ ] Result: the edge rows before and after, the instructions, final states.

---

## 11. Final checks (effort 1)

- [ ] **11.1 Run the doc's final checks**
  - Prerequisite: Task 10.2 complete.
  - [ ] With `CONTEXT_FORGE_DATA_DIR` unset, `cf project list` lists no scratch project. The real supervisor directory holds no scratch project. `git status` in this repository shows only this slice's files.
  - [ ] Stop Amoeba.
  - [ ] Result: what each check showed.

---

## 12. Captures, doc and validation (effort 3)

Per the LLD, D8 and Integration Requirements. Take every capture, so nobody judges which are new.

- [ ] **12.1 Question tails**
  - Prerequisite: Tasks 8 to 10 recorded.
  - [ ] Copy every `checkpoint.question` from `uv run amoeba inspect questions --json` against `D/store`, for every question the run produced, including unplanned ones and reruns, into the `question_tails.json` found in Task 0.1. Each entry holds `question`, `run_id`, `captured` (YYYYMMDD) and `source` set to `186-walkthrough`.
  - [ ] Success: the new entries equal the number of question records in the walkthrough's store, and `tests/runner/answering/test_question_tails_fixture.py` still passes.
- [ ] **12.2 Request replies**
  - [ ] Copy every answer-step reply artifact with `kind: request` from the answering run directories under `D/store` (named by each record's run id) into the fixtures `test_read_answer.py` reads, and every request run's `reply.json` from `D/store/requests/<run_id>/` into `tests/fixtures/slice_writing/`. Each keeps its run id and `source: 186-walkthrough`.
  - [ ] Add a parser test in each existing test file (`tests/runner/answering/test_read_answer.py`, `tests/runner/request_run/test_read_reply.py`) that reads the new captures. A capture that does not parse as its kind is a deterministic defect: file an issue that includes a stub-tier case built from it, linked under this task (D8). Do not change the parser.
  - [ ] Success: `uv run pytest tests/runner/answering tests/runner/request_run` passes, and the count of captured files equals the count of runs that produced them.
  - [ ] Result: counts, and any issue filed with its number.
- [ ] **12.3 Update the doc and the LLD to what was run**
  - [ ] Correct any command, flag or column name in `docs/program-walkthrough.md` that differed, and add each case's recorded outcome as "Observed on {date}". Mark any case closed as shown in part "not demonstrated", and state milestone 5's end-to-end claim only for the cases shown (D7).
  - [ ] Amend the LLD (`user/slices/186-slice.live-walkthrough.md`) in D5, D6 and Technical Requirements: the setup script submits the registration and neither reads `applied` nor prints node ids; both are read after start. Change nothing else in it.
  - [ ] Success: someone following the doc from its first case meets no command that fails.
- [ ] **12.4 Full validation:** `uv run ruff format .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`.
  - [ ] Success: all pass, and `uv run pytest tests/live --collect-only` with the five live variables set still collects. Every case passed, or is marked `BLOCKED:` or not demonstrated with its issue linked in its Result.

**Commit**: `docs: record program walkthrough results and captured fixtures`
