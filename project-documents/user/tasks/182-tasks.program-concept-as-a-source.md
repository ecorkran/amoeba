---
docType: tasks
slice: program-concept-as-a-source
project: amoeba
lld: user/slices/182-slice.program-concept-as-a-source.md
dependencies:
- 181
- 143
- 144
projectState: Initiatives 100, 120 and 140 are complete and merged. `runner/answering/`
  builds a passage set from the project's own rules, plan and PM answers (`passages.py`
  360 lines, `source_reads.py`, `sources.py`, `launch.py`, `stage.py`); `PassageKind`
  has `rule`, `plan` and `pm_answer`; `answering.yaml` names those three kinds. Slice
  181 (program record) is designed and tasked but not implemented when this file was
  written; its code being on the target is the precondition checked in Task 0.1. Nothing under `runner/answering/`
  mentions a program.
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
turns: 21
promptTokens: 974592
cachedTokens: 884810
cacheWriteTokens: 89754
completionTokens: 17782
durationSeconds: 132.5
costUsd: 0.625668
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.6256679
    completionTokens: 17782
---

## Context Summary

- Working on the **program-concept-as-a-source** slice (182), the third slice of initiative 180 (program coordination). For a question in a program member, the answerer gets two more kinds of passage: the program concept (read with `git show` from the concept member's checkout, at its target, at one commit) and one generated member list. A project in no program assembles exactly as after 144.
- **Current state:** see `projectState`.
- **Dependencies:** 181 (`Program`, `Member`, `ProgramStore.members`, `read_member` and its `Readable` result, `RunnerHost.program_store`, the program stage), 143 (source assembly and git reads), 144 (the launch and `passage_index`).
- **What this slice delivers:** the `program_concept` and `program_members` kinds and the `member:` line; `program_passages.py` and `program_sources.py`; program passages in `assemble`'s order and size rule; the `program` keyword on `assemble_sources`; the tick's program reaching the launch; both pipeline steps' instructions naming the new kinds; the visibility rule, proven by a test; docs and CHANGELOG.
- **Next planned slice:** 183 (edges and consumption); 185 (request outcome) consumes these passages.

**Branch:** read the target (`cf config get git.integration_branch`; empty means `main`). Before Task 0.1, create `182-slice.program-concept-as-a-source` from the target and work there. No task merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/182-slice.program-concept-as-a-source.md` at the named decision (D1 to D8) or section. Source paths are relative to `src/amoeba/` unless they start with `tests/`, `docs/` or `project-documents/`. Follow `.claude/rules/python.md`: ruff and strict pyright, no silent fallbacks, every `try/except` justified. Read each file before editing it. Keep source files near 300 lines and functions near 50. Every vocabulary is a `StrEnum` defined once; no comparison value is repeated as a literal elsewhere.

**LLD alignment:** `ProgramContext` lives in `program_sources.py` and `read_program_sources` takes an `AskerReads` argument (D3's asker case); the LLD was amended to say so (D7 and API Contracts), because `tests/runner/purity.py` forbids a `pathlib` import in the pure `program_passages.py`.

**Order:** work tasks in file order. Only Task 8.3 needs live access (models and keys); no task needs live CF or `sq`. Assembly is deterministic and tested against temporary git repositories and test-written stores.

**Load tests:** `.claude/rules/python.md` requires one for code on environment-layer paths, and the concept read runs `cf` and git subprocesses inside the tick. Task 7.3 adds it under `tests/load/`; CI already runs `tests/load` as its own step (`.github/workflows/ci.yml`), so that gate exists.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before markers that follow Python changes.

---

## 0. Preflight

- [ ] **0.1 Confirm 181's code exists and record its real names** (effort 1)
  - [ ] Create the branch (see Branch above). Then check that 181's code is present on the target (read the files; change nothing): `ProgramStore` with `members(program_id)` and `program_of`; `Program` (with `concept_member`, `concept_path`, `updated_at`) and `Member` (with `project_id`, `updated_at`); `read_member`, `Readable`, `Unreadable`, `MemberUnreadableReason`; `RunnerHost.program_store`; `ProgramStage.run(project_id) -> Program | None` called in `ProjectTick.run`; `resolve_checkout` exported from `amoeba.upstream.context_forge`.
  - [ ] Confirm `Readable` carries the member's resolved `Checkout` and the CF project id of its one link (181's Task 5.1 owns adding them). If it does not, write `BLOCKED: 181's Readable lacks the checkout or the CF project id` under this task, leave it unchecked, and stop; 182 does not change 181's code.
  - [ ] Where 181's code differs in name or shape from this file, follow the code and use its names in every task below. Do not edit 181's design.
  - [ ] Success: each name above was found by reading the code (not assumed); any difference is noted at the top of the task you are on when you reach it. If 181's code is not on the target, write `BLOCKED: slice 181 code is absent from the target` under this task, leave it unchecked, and stop.

- [ ] **0.2 Pin the 144 baseline for a project in no program, before any change** (effort 2)
  - [ ] In `tests/runner/answering/test_sources.py`, using `launch_rig.py` and `sources_assembly.py`, add a test that launches one question in a project in no program and asserts three things against pinned data: the rendered `passages.md` equals `fixtures/expected_end_to_end.md` (the existing oracle); the ordered list of `cf` and `git` argv lists the launch made, recorded by a recording `cf_run` wrapper, equals a literal tuple written in the test; the `passage_index` rows stored for the launched question (id, source, date) equal a literal list written in the test.
  - [ ] Write the two literals by running the test on the unchanged code and copying what it recorded, so they are 144's behavior and not a guess.
  - [ ] Success: the test passes on the code as it stands; `uv run pytest tests/runner/answering/test_sources.py -k baseline` passes. Task 7.1 reuses it.

**Commit**: `test: pin the answering baseline for a project in no program`

---

## 1. Make the git read helpers public

- [ ] **1.1 Rename `_Git`, `_Listings` and `_read_file` in `runner/answering/source_reads.py`** (effort 1)
  - [ ] Rename to `GitReads`, `Listings` and `read_file` (and `_in_context` to `in_context`, which both callers need). No behavior change; update every use in the file and in tests (`grep -rn "_Git\|_Listings\|_read_file\|_in_context" src tests`).
  - [ ] `read_file` keeps its signature `(git, commit, chosen: SelectedFile)`; the concept read will call it with a `SelectedFile` of kind `program_concept` (Task 5.3).
  - [ ] Success: `uv run pytest tests/runner/answering/test_source_reads.py tests/runner/test_git_read_only_place.py` passes with no assertion changed; `uv run pyright` passes.

**Commit**: `refactor: make the source read helpers public`

---

## 2. Passage kinds, the `member` field and its render line

- [ ] **2.1 `PassageKind`, `SourceFile`, `Passage` and `_render_section` in `runner/answering/passages.py`** (effort 2)
  - [ ] Add `PROGRAM_CONCEPT = "program_concept"` and `PROGRAM_MEMBERS = "program_members"` to `PassageKind` (LLD API Contracts).
  - [ ] Add `member: str | None` to `SourceFile` and to `Passage`, with no default; update every constructor call (`grep -rn "SourceFile(\|Passage(" src tests`) to pass `member=None`. `_committed_passages` is the one function that builds passages from `SourceFile`s (it calls `cut_passages`, which stays unchanged and returns plain strings); it copies `source.member` onto each passage it builds. Task 4.1 reuses it for the program files.
  - [ ] `_render_section` writes `member: <id>` after `kind` when `passage.member` is not `None`, and writes **no** `source:` line for a `program_members` passage (its `source` field holds the program id for `passage_refs`, D4). Every other kind renders exactly as before.
  - [ ] Success: the file stays under about 375 lines (the member-list text goes in `program_passages.py`, not here).

- [ ] **2.2 Tests for the kinds and rendering** (effort 2)
  - [ ] In `tests/runner/answering/test_passages.py`: a `program_concept` passage renders `kind`, `member`, `source`, `date` in that order; a `program_members` passage renders `kind` and `date` only; rule, plan and `pm_answer` passages render byte-identically to before (existing tests still pass unedited apart from `member=None`).
  - [ ] A `program_concept` `SourceFile` with `member` set, front matter and two level-2 sections, run through `_committed_passages`, gives exactly three passages (the front matter before the first heading is its own passage, then one per section), each carrying the `member`.
  - [ ] Success: `uv run pytest tests/runner/answering/test_passages.py tests/runner/answering/test_launch_prepare.py` passes; `passage_refs` still records a `program_members` passage's source as its `source` field.

**Commit**: `feat: add program passage kinds and the member line`

---

## 3. The pure program passages module

- [ ] **3.1 Create `runner/answering/program_passages.py`** (effort 2)
  - [ ] Define `ProgramSources(concept: SourceFile, members: SourceFile)` (frozen dataclass, LLD API Contracts).
  - [ ] Define the two marker strings once, beside the function: "holds the program concept" and "this question comes from this project" (D4).
  - [ ] `member_list_text(program, members, asking_project) -> str` produces the D4 text: the `Program: <id>` line, `Projects in this program:`, then one `- <project_id>` line per member in project-id order, markers in parentheses, both markers joined by `; ` on one line when the asker is the concept member. It raises `ValueError` when `asking_project` or `program.concept_member` is not among `members`.
  - [ ] A function `member_list_date(program, members)` returns the latest `updated_at` of the program and its members (D4).
  - [ ] No file, process or store import: do not import `pathlib`.
  - [ ] Success: `uv run pyright` passes on the module.

- [ ] **3.2 Tests in `tests/runner/answering/test_program_passages.py`** (effort 2)
  - [ ] The member list text for three members matches the LLD's example exactly; members given out of order are listed in project-id order; the asker being the concept member gives the one-line `; ` form; an unknown asker or concept member raises `ValueError`.
  - [ ] `member_list_date` returns the latest of the program's and members' `updated_at`, including when a member is newer than the program.
  - [ ] `assert io_use(program_passages) == []` using `runner.purity.io_use`, as `test_passages.py` does for `passages`.
  - [ ] Success: `uv run pytest tests/runner/answering/test_program_passages.py` passes.

**Commit**: `feat: add the pure program passages module`

---

## 4. Program passages in `assemble`

- [ ] **4.1 Add program sources to `assemble` in `runner/answering/passages.py`** (effort 3)
  - [ ] Give `assemble` a required keyword `program_sources: ProgramSources | None` (no default; update every caller, `grep -rn "assemble(" src tests`). With `None` the result is exactly as before.
  - [ ] With a value, the order is: rules, plan (the `committed` files), then the concept's passages, then the member list (one passage, `kind` `program_members`, its `source` the program id), then PM answers. Build them all with the one existing `_committed_passages`, passing `(*committed, program_sources.concept, program_sources.members)`, so `member` is copied the same way for every file. Ids `P1` to `Pn` follow that order with no gaps (D5).
  - [ ] Program passages are never trimmed and count with rules and plan: if rules, plan and program passages together exceed `max_chars` the result is `sources_too_large`, its detail naming "rules, plan and program passages". PM answers are then fitted into what is left, unchanged.
  - [ ] Import `ProgramSources` from `program_passages.py` under the existing import style; avoid a circular import by having `program_passages.py` import only `passages` types it needs (if a cycle appears, take the `SourceFile` type through `TYPE_CHECKING` and `from __future__ import annotations`).
  - [ ] Unit: this size check measures rendered passages (headers included), as D5 says. Assembly is the authority at the limit; `read_program_sources`'s early stop (Task 5.3) is a cheaper, conservative check on raw text.
  - [ ] Success: `uv run pyright` passes; the existing `test_passages.py` tests pass with only the new keyword added. Measure `wc -l src/amoeba/runner/answering/passages.py`: it was 360 lines before this slice and must be at most 400 after this task. If it is over, extract `CitationKind`, `CitationProblem` and `check_citations` into `runner/answering/citations.py` as a pure move (update importers: `grep -rn "check_citations\|CitationKind\|CitationProblem" src tests`), in the same commit.

- [ ] **4.2 Tests for the program order and the size rule** (effort 3)
  - [ ] In `test_passages.py`: with program sources the kinds in order are rule, plan, program_concept (one per section), program_members, pm_answer; ids are `P1..Pn` gap-free; `program_sources=None` gives the same set as before for the existing fixtures.
  - [ ] Program passages over `max_chars` with rules and plan give `sources_too_large`; a limit that fits rules, plan and program passages but not all PM answers keeps the program passages and drops PM answers in the existing priority order, listing them in `dropped_pm_answers`.
  - [ ] Success: `uv run pytest tests/runner/answering/test_passages.py` passes.

**Commit**: `feat: place program passages after the plan in assemble`

---

## 5. The concept read

- [ ] **5.1 Test rig for program fixtures** (effort 3)
  - [ ] Create `tests/runner/answering/program_rig.py`. Read `tests/runner/answering/sources_repo.py`, `sources_assembly.py`, `tests/runner/git_repo.py` and the 181 test helpers that build a program store and member stores, and reuse them.
  - [ ] Provide: a function building a concept repository with `git_repo.commit_file` and controlled commit dates holding a real-format concept document (front matter and level-2 sections, such as `docs/program-concept.md`); a function writing a concept member's store (one CF link, an `observed` snapshot whose project path is that repository) so `read_member` returns `Readable`; and builders for `Program` and `Member` values for a two-member program, with the member that holds the concept selectable.
  - [ ] The store function takes an optional `defect: MemberUnreadableReason | None` and produces each of 181's five reasons: `store_missing` (write no store file), `store_unreadable` (write a file at the store path that is not an SQLite database), `unlinked` (a store with no CF link), `snapshot_missing` (a link with no `observed` snapshot), `checkout_unresolved` (a snapshot whose project path is not a directory). `None` gives the readable member.
  - [ ] A counting `cf` runner, wrapping `sources_assembly.run`, that records every `cf` call and every git argv in call order; `CountingBudget` (existing) counts asks.
  - [ ] Success: a test in `tests/runner/answering/test_program_rig.py` shows `read_member` returns `Readable` for the built concept member with `defect=None`. The per-reason results are asserted in Task 5.5.

- [ ] **5.2 `ProgramContext`, `AskerReads` and the member-state step in `runner/answering/program_sources.py`** (effort 3)
  - [ ] Create the module with the frozen `ProgramContext(program, members, store_dir, asking_project)` (D7) and `AskerReads(repo: Path, committed: CommittedSources)`. `ProgramContext` raises `ValueError` in `__post_init__` when `program.concept_member` is not among `members` (LLD, Patterns and Conventions).
  - [ ] Define `read_program_sources(context, asker, max_chars, budget, run, timeout_seconds) -> ProgramSources | SourcesProblem | None`. Its first step, for a concept member that is not the asker: find the concept `Member` in `context.members`, call `read_member(context.store_dir, member)`; an `Unreadable` returns `unreadable(f"concept member {id} {reason}: {detail}")` using 181's reason enum value.
  - [ ] Then `read_target(checkout.path, cf_project_id, budget, run, timeout_seconds)` using the `Readable`'s checkout and CF project id: `None` returns `None`; a `ReadFailure` returns `unreadable` with detail prefixed `concept member <id>: `.
  - [ ] Stop after this step for now (later tasks add the git reads); the function raises `NotImplementedError` after it. Remove that stub in Task 5.3.
  - [ ] Success: `uv run pyright` passes on the module.

- [ ] **5.3 The git reads: commit, listing, date, text** (effort 4)
  - [ ] Using `GitReads` with the concept member's checkout: `git log -1 --format=%H <target>` via `resolve_commit_args` (empty result: `unreadable` naming the target); list the concept path's parent directory at that commit with `Listings.of`; the file's name absent from the listing is `SourcesProblem(MISSING, ...)` naming the member and the path; then `read_file` with `SelectedFile(concept_path, PassageKind.PROGRAM_CONCEPT)` for the date and text. Every failure detail from these calls is prefixed `concept member <id>: ` through `in_context`.
  - [ ] The resulting `SourceFile` has `member` set to the concept member's project id. Build the member list with `member_list_text`, `member_list_date` and `SourceFile(path=program id, kind=PROGRAM_MEMBERS, member=None, ...)`, and return `ProgramSources`.
  - [ ] Early stop (D5): after the concept text is read, if its raw length exceeds `max_chars` return `SourcesProblem(TOO_LARGE, ...)` naming the concept path, without building the member list. Read the text through `read_file` (one git call each for date and text; a file over the limit is detected after its text is read, as in `read_committed_sources`). This is a conservative check on raw text; assembly (Task 4.1) is the authority on rendered size.
  - [ ] Every call goes through the existing budget and git allowlist. No new git verb is added, and no git argument list is written outside `runner/git_read.py`; if a listing or log is needed that has no helper, use the existing `resolve_commit_args`, `show_object_args`, `last_change_args` helpers only.
  - [ ] Success: `uv run pyright` passes; no `NotImplementedError` stub remains.

- [ ] **5.4 Tests: the concept read from another member, success paths** (effort 2)
  - [ ] In `tests/runner/answering/test_program_sources.py`, using the Task 5.1 rig: the returned concept `SourceFile` has the concept text, `member` set, kind `program_concept`, and a date equal to the controlled date of the commit that last changed the concept file (a later unrelated commit on the target does not change it).
  - [ ] Committed-only (D3): an uncommitted edit to the concept file and an untracked file beside it do not appear; a second commit made after the commit was resolved is invisible (assert every git read after the commit names that commit hash).
  - [ ] Concept read on the member's target: the rig's `cf` stub answers a target other than `main`, a branch holding a different concept text than `main`; the text from that branch is returned.
  - [ ] Success: `uv run pytest tests/runner/answering/test_program_sources.py` passes.

- [ ] **5.5 Tests: the concept read from another member, failures** (effort 3)
  - [ ] Concept file missing from the listing is `sources_missing` naming member and path; the parent directory missing is `sources_unreadable`; a non-UTF-8 concept file is `sources_unreadable` naming the path.
  - [ ] Each `read_member` reason, produced with the rig's `defect` argument and parametrized over `MemberUnreadableReason` (`store_missing`, `store_unreadable`, `unlinked`, `snapshot_missing`, `checkout_unresolved`), is `sources_unreadable` with detail `concept member <id> <reason>: <detail>`.
  - [ ] A failing `cf` target read and a failing `git show` are `sources_unreadable` with the `concept member <id>: ` prefix. Timeouts (D3): a `run` that raises `subprocess.TimeoutExpired` for the `cf` call, and separately one that raises it for a git call, each give `sources_unreadable` with the same prefix (`git_read` and `read_target` already map a timeout to a failure value).
  - [ ] Success: `uv run pytest tests/runner/answering/test_program_sources.py` passes.

- [ ] **5.6 Tests: size, call count, order and budget refusals** (effort 2)
  - [ ] Size: a concept whose raw text is longer than `max_chars` is `sources_too_large`, and the call count is still one `cf` and four git (nothing is read after the text). The rendered-size limit is tested in Task 4.2.
  - [ ] Call count and order: one `cf` call and four git calls, asserted from the rig's counters, in this order: `cf` target, `git log` for the commit, `git show` of the parent directory, `git log` for the file's date, `git show` of the file. A `CountingBudget` that refuses the first, second, third, fourth and fifth call each yields `None`.
  - [ ] Success: `uv run pytest tests/runner/answering/test_program_sources.py` passes.

**Commit**: `feat: read the program concept from the concept member's checkout`

- [ ] **5.7 The asker is the concept member** (effort 3)
  - [ ] In `read_program_sources`, when `context.asking_project` is `program.concept_member`: do not call `read_member` and make no `cf` call; use `asker.repo` and `asker.committed.commit` as the repository and commit (D3). If the concept path is among `asker.committed.files`, return that file re-labelled as a `program_concept` `SourceFile` (kind and `member` changed, text and date as read) with no git call. Otherwise list its parent directory, read its date and its text at that commit (three git calls), with the same missing-file and unreadable rules as Task 5.3.
  - [ ] Add the function `without_path(files: tuple[SourceFile, ...], path: str) -> tuple[SourceFile, ...]` to `program_sources.py`, returning `files` minus the one at `path`. `assemble_sources` calls it (Task 6.1) so the file is kept once, at the concept position. The size limit given to `read_program_sources` is the characters still allowed after the files that remain.
  - [ ] Tests in `test_program_sources.py`: asker holds the concept and the concept path is also a rules file: one `program_concept` file comes back, zero `cf` and zero git calls; the path is not in the project's files (not a rule, not a plan); asker holds the concept and the path is not among its own files: three git calls, none for the target or commit, all at `asker.committed.commit`, and a concept committed after that commit is not seen; `without_path` removes exactly the named file and leaves the others in order.
  - [ ] Success: `uv run pytest tests/runner/answering/test_program_sources.py` passes; `program_sources.py` stays near 300 lines (split `member state` into its own function if it grows).

**Commit**: `feat: read the concept from the asker's own pinned commit`

---

## 6. Wire the program into assembly and the launch

- [ ] **6.1 The `program` keyword on `assemble_sources` in `runner/answering/sources.py`** (effort 3)
  - [ ] Add the required keyword `program: ProgramContext | None` (no default). Update every caller (`grep -rn "assemble_sources(" src tests`, including `tests/runner/answering/sources_assembly.py`, which passes `program=None` unless a test overrides it through its `**kw`).
  - [ ] With `None` the function body is unchanged: no other store opened, no extra call, `assemble(..., program_sources=None)`.
  - [ ] With a context: after `read_committed_sources`, call `read_program_sources(program, AskerReads(checkout.path, committed), remaining, ...)` where `remaining` is `max_chars` minus the text of the project files that remain after removing the concept path when the asker holds the concept. Return `None` or a `SourcesProblem` as it does; otherwise, when the asker holds the concept, replace `committed.files` with `without_path(committed.files, program.program.concept_path)` (Task 5.7), and call `assemble` with the program sources.
  - [ ] Success: `uv run pyright` passes; the existing `test_sources.py` tests pass with only the new keyword added.

- [ ] **6.2 Tests in `tests/runner/answering/test_sources.py`** (effort 3)
  - [ ] Using `program_rig`: a question in the non-concept member renders rules, plan, `program_concept` passages, one `program_members` passage marking the asker, then PM answers, ids gap-free, and the commit recorded is the asker's commit `C`. A question in the concept member renders the concept once, at the concept position, with both markers on its one line.
  - [ ] `program=None` renders the same `passages.md` as before the slice (use the existing expected-output fixture); a refused budget call during the program reads returns `None` and the question stays pending.
  - [ ] Each program problem (`sources_missing`, `sources_unreadable`, `sources_too_large`) comes back from `assemble_sources` as a `SourcesProblem`, not an exception.
  - [ ] Success: `uv run pytest tests/runner/answering/test_sources.py -k program` passes.

- [ ] **6.3 `LaunchContext.program` and `prepare_launch` in `runner/answering/launch.py`** (effort 3)
  - [ ] Add `program: ProgramContext | None` to `LaunchContext` (no default) and pass it to `assemble_sources(..., program=context.program)`. `passage_refs` is unchanged.
  - [ ] Update every `LaunchContext(` construction (`runner/tick.py`'s `_launch_context`, `tests/runner/answering/launch_rig.py` and other test builders: `grep -rn "LaunchContext(" src tests`).
  - [ ] Success: `uv run pyright` passes; `uv run pytest tests/runner/answering -q` passes.

- [ ] **6.4 The tick's program reaches the answering stage (`runner/answering/stage.py`, `runner/tick.py`)** (effort 3)
  - [ ] Read `runner/tick.py` and 181's `ProgramStage` call. Keep the result of the program stage in `ProjectTick.run` (181 discards it) and pass it, with the host's current `program_store`, to the answering stage: `AnsweringStage.run` takes the `Program | None`, and the stage holds a `ProgramStore | None` given at construction (both required, no defaults). Update every caller: `grep -rn "AnsweringStage(\|answering.run(\|_answering.run(" src tests`.
  - [ ] Build the `ProgramContext` once per launch (D7), only when the program is not `None`: read `members(program.program_id)` once and use `launch.supervisor_dir` as `store_dir` (the directory holding `{project_id}.sqlite3`). A `program` with no `program_store` raises `ValueError` (programming error). A `StoreError` from `members` propagates (181's rule; it is in `STORE_FAILURES`).
  - [ ] The answering stage never looks the program up itself: it uses only the value the tick passes.
  - [ ] Success: `uv run pyright` passes; `uv run pytest tests/runner -q` passes.

- [ ] **6.5 Tests for the launch and tick wiring** (effort 4)
  - [ ] In `tests/runner/answering/test_launch_prepare.py` or `test_launch_answering.py`: a launch with a `ProgramContext` stores `passage_index` rows for the concept passages (source = concept path) and for the member list (source = program id), dates as rendered; `source_commit` is the asker's commit.
  - [ ] In `tests/runner/test_tick_answering.py`: a member project's tick launches with a program context (read of `members` happens once per launch); a project in no program makes no `members` read and no program context; a `StoreError` from `members` propagates out of the tick.
  - [ ] Success: `uv run pytest tests/runner -q` passes.

**Commit**: `feat: pass the tick's program to the answering launch`

---

## 7. Regression and visibility proofs

- [ ] **7.1 No-program regression test** (effort 3)
  - [ ] Extend Task 0.2's baseline test (same file, name contains `baseline`) to run it in two more setups, each asserting the same three pinned things (`passages.md` against `expected_end_to_end.md`, the literal `cf` and git call list, the literal `passage_index` rows): the program store absent from the host, and a program store holding a program the asking project is not a member of (LLD D1, Success Criteria).
  - [ ] Success: the test fails if `read_program_sources` or `members` is called for a non-member (assert with a spy that raises).

- [ ] **7.2 Visibility test** (effort 4)
  - [ ] In `test_sources.py` (name contains `visibility`): a two-member program where the concept member's repository also has its own `CLAUDE.md`, a rules glob match and plan files, and its store holds PM-answered questions. A question in the other member renders a set whose sources are the asker's own files, the concept path with `member:` set, and the member list; every PM passage comes from the asker's store.
  - [ ] Assert every passage's `(kind, member, source)` against an explicit allowed set built in the test, so an extra passage from the concept member fails the test (LLD D6).
  - [ ] Success: `uv run pytest tests/runner/answering/test_sources.py -k "program or visibility" -v` passes.

- [ ] **7.3 Load test for the program reads** (effort 3)
  - [ ] Add `tests/load/test_program_passages_load.py`, in the style of `tests/load/test_runner_tick_load.py` (assert exact counts and bounds, not a speed claim; record the measured figures and date in the module docstring). Use `program_rig` helpers (the `tests` directory is on the path for load tests as it is there).
  - [ ] Realistic configuration: a program of 20 members; a concept document of about 100 level-2 sections; 30 member questions assembled in turn against one `TickBudget`.
  - [ ] Assert: every question makes exactly one `cf` call and four git calls (none grows with member count or concept size); a budget that allows only part of the work returns `None` for the first refused question and stops there; total wall time is under a bound set at about ten times the figure measured on the development machine.
  - [ ] Success: `uv run pytest tests/load/test_program_passages_load.py` passes.

**Commit**: `test: prove the no-program regression, the visibility rule and the program read bounds`

---

## 8. Pipeline instructions

- [ ] **8.1 Name the new kinds in `runner/answering/answering.yaml`** (effort 2)
  - [ ] In both the answer and check steps, replace "a kind (rule, plan or pm_answer)" wording with the three sentences from the LLD (D8): the kinds are rule, plan, pm_answer, program_concept or program_members; a program_concept passage comes from the concept document of the program this project belongs to, held in the member project its `member` line names, and describes how the program's projects fit together and what each is for; a program_members passage lists the program's projects and marks the one the question comes from. Change nothing else, and do not touch `question.md`.
  - [ ] Both steps use the same three sentences.
  - [ ] Success: `answering.yaml` is still valid YAML with the same steps and params; Task 8.2 tests the sentences.

- [ ] **8.2 Tests for the instructions** (effort 2)
  - [ ] In `tests/runner/answering/test_pipeline_yaml.py`, update any assertion that pins the old kind wording; add one that both steps name `program_concept` and `program_members`, using `PassageKind` values rather than literals.
  - [ ] Success: `uv run pytest tests/runner/answering -q` passes.

**Commit**: `feat: name the program passage kinds in the answering instructions`

- [ ] **8.3 Run 140's live answering fixtures against the new instructions** (effort 2; verification only, no commit of its own)
  - [ ] Run `uv run pytest tests/live/answering/test_pipeline_run.py tests/live/answering/test_precedence.py tests/live/answering/test_answering_run.py` with `AMOEBA_LIVE_ANSWER_MODEL`, `AMOEBA_LIVE_CHECK_MODEL` and `AMOEBA_LIVE_MAX_COST_USD` set (names and meaning in `docs/answerer-walkthrough.md`; live runs and spend are pre-authorized). The tier fails at collection naming any unset variable; if one is unset and not in the environment or `.env`, write `BLOCKED: <variable name> is unset` under this task, leave it unchecked, and stop.
  - [ ] Success: the three files pass. A failure is investigated at its cause (read the failing test's output first); do not edit a live fixture to make it pass.


---

## 9. Docs and final validation

- [ ] **9.1 `docs/process-contract.md` and `CHANGELOG.md`** (effort 2)
  - [ ] In "The answering stage" (the passage set bullet near "The passage set (slice 143)"): add the program passages, the visibility rule verbatim from LLD D6 (including that 185 extends it), the order in the set, the never-trimmed size rule, and the cost: one `cf` call and four git calls per member question. Extend the `passages.md` format section with the `member:` line and the two kind words.
  - [ ] `CHANGELOG.md` under `[Unreleased] / Added`: "Slice 182: program concept as a source", naming the two kinds and that a project in no program is unchanged; plus one line in the project's existing form, "Slice 182: **behavior change** for program members: ...", saying that a question in a program member is now answered with the program concept and member list among its passages and can decline `sources_missing`, `sources_unreadable` or `sources_too_large` on their account. No config key is added.
  - [ ] Success: every statement in the docs matches the code as built; no line in either file describes a later slice as done.

- [ ] **9.2 Full validation** (effort 1)
  - [ ] Run once each: `uv run ruff format .`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`. Fix anything they report, at its cause.
  - [ ] Check `passages.py`, `program_sources.py`, `stage.py` and `launch.py` for size near the guidelines; split only if one is clearly over.
  - [ ] Success: all four pass; the LLD's three verification commands (Verification Walkthrough) pass as written.

**Commit**: `docs: document program passages and the visibility rule`
