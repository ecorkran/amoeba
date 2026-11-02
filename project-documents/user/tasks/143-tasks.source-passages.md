---
docType: tasks
slice: source-passages
project: amoeba
lld: user/slices/143-slice.source-passages.md
dependencies:
- 141
- 142
projectState: Slices 120–132, 141 and 142 are merged; 140 is built. AnswererSettings
  already holds answer_limit and reserved_terms (142). The git allowlist is status
  and merge-base only. No passage, citation or committed-source reading code exists.
  Nothing calls assembly outside tests; slice 144 is the first caller.
dateCreated: 20261102
dateUpdated: 20261102
status: not_started
turns: 19
promptTokens: 1176013
cachedTokens: 1094648
cacheWriteTokens: 81327
completionTokens: 19345
durationSeconds: 151.1
costUsd: 0.628593
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 0.6285932
    completionTokens: 19345
revision_number: 2
---

## Context Summary

- Working on the **source-passages** slice (143) of the question-answerer initiative (140 architecture). It builds the passage set an answering run sees (project rules, CF plan files, PM precedent) from one committed commit of the target branch, renders it as 140's `passages.md`, and provides the pure citation check.
- **Current state:** see `projectState`.
- **Dependencies:** 141 (question record: `store.questions`, `QuestionRecord`, `QuestionState`, `AnsweredBy`) and 142 (merged; it already added `answer_limit` and `reserved_terms` to `AnswererSettings`, so this slice adds two more keys to that model). 140 is a written contract only (the `passages.md` format). No Squadron or LLM dependency.
- **What this slice delivers:** `show` and `log` in the git allowlist with argument builders; `passages.py` (pure: types, cutting, selection, assembly, rendering, citation check); `source_reads.py` (every git call); `sources.py` (`assemble_sources`, precedent, `slice_label`); the keys `rules_paths` and `passages_max_chars`; frozen fixtures; contract docs. Nothing calls `assemble_sources` outside tests.
- **Next planned work:** 144 (answering run, first caller), 145 (walkthrough).

**Branch:** all implementation happens on `143-slice.source-passages`, forked from the target (`cf config get git.integration_branch`; empty means `main`). No task here merges or pushes. Merging follows the code review.

**Reading note:** this file does not restate the LLD. "Per the LLD" means open `user/slices/143-slice.source-passages.md` at the named decision (D1–D11), "Architecture", "API Contracts" or "Success Criteria". Source lives under `src/amoeba/`; paths below are relative to it unless they start with `tests/`, `docs/` or `project-documents/`. Keep every new or changed source file near 300 lines and each function near 50. Follow `.claude/rules/python.md`: ruff and strict pyright, `StrEnum` for vocabularies, no silent fallbacks, every `try/except` justified.

**Order and dependencies:** work tasks in file order. Each task leaves the full suite passing.

**Commit cadence:** commit only at the `**Commit**:` markers. Run `uv run ruff format .` before each commit, and `uv run ruff check .` and `uv run pyright` before the markers that follow source changes.

**Task-level facts** (checked against the code on 20261102):
- `runner/git_read.py` (170 lines): `GIT_SUBCOMMANDS = {status, merge-base}` built from `SUBCOMMAND_*` constants; `is_ancestor_args(head, target)` is the model for an argument builder that refuses a value starting with `-`; `git_read(args, cwd, budget, run, timeout_seconds)` returns `GitReadResult(exit_code, stdout, stderr_head) | GitReadFailure(detail) | None` (`None` = budget refused). The module docstring says "the allowlist is two read commands".
- `tests/runner/test_git_read.py` has `test_a_subcommand_outside_the_allowlist_is_refused` parametrized over `["commit","checkout","push","merge"]` (none of them `show` or `log`), plus `tests/runner/test_git_read_only_place.py` (no module outside `git_read.py` starts `git`).
- `runner/dispatch/checkout.py`: `resolve_checkout(snapshot, slice_index, *, is_dir) -> Checkout | CheckoutUnresolved` (`.reason`). `runner/dispatch/checkout_reads.py`: `read_target(checkout, cf_project_id, budget, run, timeout_seconds) -> str | ReadFailure | None`. Read both files before using their return types (`Checkout`'s path attribute, `ReadFailure`'s detail attribute).
- `runner/project_config.py`: `AnswererSettings` is a frozen pydantic model with `extra="forbid"`; `answer_limit: Annotated[StrictInt, Field(ge=1)]`, `reserved_terms: tuple[...]`. Config tests in `tests/runner/test_project_config.py` write real YAML (`ANSWERER_FILE`, `_answerer_file(body)`); every existing fixture or test that builds an `answerer` section must gain the two new keys.
- `Store.get_node(node_id) -> Node | None` (`store/_base.py`); `Store.questions(project_id, *, state=None, node_id=None)` (`store/questions.py`). Test helpers: `tests/question_harness.py` (`seed_question`, `make_slice`); `tests/runner/git_repo.py` (`git`, `commit_file`, `make_repo`, `head_of`); purity check `tests/runner/purity.py::io_use(module)`; answering tests in `tests/runner/answering/`.
- Docs: `docs/process-contract.md` has "The answering pipeline" (~line 643), "The project config" (~722) and "Git and the pre-dispatch check" (~779, says "allows `status` and `merge-base` only"). The contract's "Squadron shapes" bullet (~539) is the model for recording upstream shape knowledge; 143's CF layout goes in a new "Context Forge shapes" section beside it.

---

## 1. Branch and baseline

- [x] **1.1 Create the slice branch and record the baseline**
  - [x] Run `cf config get git.integration_branch`. The result (or `main` if empty) is the target. Confirm you are on the target.
  - [x] Run `git checkout -b 143-slice.source-passages {target}`.
  - [x] Run `uv run pytest -q`, `uv run ruff check .` and `uv run pyright` once. Note any failures that exist before this slice.
  - [x] Success: on branch `143-slice.source-passages`, and the baseline result is known.

---

## 2. Git reads: `show` and `log`

- [x] **2.1 Allowlist and argument builders** (`runner/git_read.py`)
  - [x] Add `SUBCOMMAND_SHOW` and `SUBCOMMAND_LOG` constants and add both to `GIT_SUBCOMMANDS`. Update the module docstring (four read commands).
  - [x] Add `resolve_commit_args(target)` → `("log", "-1", "--format=%H", target)`; `show_object_args(commit, path)` → `("show", f"{commit}:{path}")` (an empty `path` gives `<commit>:`); `last_change_args(commit, path)` → `("log", "-1", "--format=%cI", commit, "--", path)`. Each refuses a `commit`/`target` that starts with `-` with `ValueError`, as `is_ancestor_args` does; a `path` is safe after `--` and inside `<commit>:<path>`. Per LLD D2.
  - [x] Success: imports; typecheck passes.

- [x] **2.2 `parse_tree_listing`** (`runner/git_read.py`)
  - [x] `parse_tree_listing(text) -> tuple[str, ...]`: skip a `tree …` header line and blank lines; keep file entries; drop entries ending in `/`. Lenient about trailing whitespace and CRLF. Per LLD D2.
  - [x] Success: returns names in the order git printed them.

- [x] **2.3 Tests for the git reads** (`tests/runner/test_git_read.py`)
  - [x] Builders: exact tuples for the three builders (root path case included); each refuses a value starting with `-`.
  - [x] `GIT_SUBCOMMANDS` holds all four; the refused-subcommand test still passes unchanged.
  - [x] `parse_tree_listing` on real `git show <commit>:<dir>` output from a temporary repository (`make_repo`, `commit_file`) with a file, a nested file and a subdirectory: files kept, the subdirectory dropped, the header skipped. Also the root listing (`<commit>:`).
  - [x] Real `git_read` runs of `resolve_commit_args`, `show_object_args` (blob content) and `last_change_args` (one ISO line) against that repository.
  - [x] Update the "two read commands" wording in `test_git_read_only_place.py` or elsewhere if a test or doc pins it.
  - [x] Success: `uv run pytest tests/runner/test_git_read.py tests/runner/test_git_read_only_place.py -q` passes.

**Commit**: `feat: allow git show and log reads with argument builders and tree listing parser`

---

## 3. Passages: types and cutting

- [x] **3.1 Types** (`runner/answering/passages.py`, new)
  - [x] Define per LLD API Contracts and D9: `PassageKind` (`rule`, `plan`, `pm_answer`), frozen `Passage`, frozen `PassageSet` with the `ids` property, `SourceFile` (path, kind, date, text), `PmAnswer` (record id, question, answer, date, node id, slice label), `SourcesProblemKind` (`sources_too_large`, `sources_missing`, `sources_unreadable`), frozen `SourcesProblem(kind, detail)`, `CitationKind` (`uncited`, `unknown_ids`) and frozen `CitationProblem(kind, ids)`.
  - [x] The module does no I/O: import nothing from `pathlib`, `os`, `subprocess`. Use `PurePosixPath` only if pure matching needs it (check `io_use` allows it; it flags `pathlib` imports, so prefer plain string handling).
  - [x] Success: imports; typecheck passes.

- [x] **3.2 `cut_passages`** (`runner/answering/passages.py`)
  - [x] `cut_passages(text) -> tuple[str, ...]` per LLD D4: new passage at every ATX heading of level 1–3 (up to three leading spaces, `#`..`###`, then a space or end of line), outside ``` and `~~~` fenced blocks; deeper headings stay inside; a non-blank preamble (front matter included) is its own passage; a blank preamble is dropped; no headings gives one passage; empty text gives none. Text is never rewritten.
  - [x] Success: `"".join(cut_passages(text)) == text` for any text without a blank preamble.

- [x] **3.3 Fixture files** (`tests/runner/answering/fixtures/sources/`)
  - [x] Copy, at their real relative paths and frozen: `CLAUDE.md`, two rules files, `python.md` and `git.md`, from `project-documents/ai-project-guide/project-guides/rules/` (both exist there), the project concept and initiative plan from `project-documents/user/project-guides/` (`000-concept.*`, `001-initiative-plan.*`), `120-arch.*` and `120-slices.*` from `project-documents/user/architecture/`, `132-slice.*` from `user/slices/` and `132-tasks.*` from `user/tasks/`. Slice 132 is used because all its plan files exist (LLD D11).
  - [x] Check `ls` for each; if a named file does not exist under that exact name, stop and report which, rather than substituting a different slice.
  - [x] Success: all files present; none edited after copying.

- [x] **3.4 Tests for cutting** (`tests/runner/answering/test_passages.py`, new)
  - [x] Cases: a heading inside a code fence (both fence styles) does not cut; a level-4 heading does not cut; front matter is its own passage; a file with no headings is one passage; an empty file gives none; a blank preamble is dropped; a heading with three leading spaces cuts and four does not; `#` with no following space (`#tag`) does not cut.
  - [x] Property test: for every file under `tests/runner/answering/fixtures/sources/`, joining its passages gives back the file exactly, and each passage after the first starts with a heading line.
  - [x] Purity: add `passages` to the module list checked by `tests/runner/purity.py` (follow how existing pure modules such as `gate.py` are checked, in `tests/runner/test_answer_gate.py`).
  - [x] Success: `uv run pytest tests/runner/answering/test_passages.py -q` passes.

**Commit**: `feat: add passage types and heading-based cutting with frozen source fixtures`

---

## 4. Passages: selection, assembly, rendering, citations

- [x] **4.1 Selection from listings** (`runner/answering/passages.py`)
  - [x] `match_rules_entry(entry, listing) -> tuple[str, ...]`: given a rules entry and its parent directory's file listing, return matching file names. Only the entry's last path segment is compared, against each listed name; the parent directory is not part of the comparison. Glob rules per LLD D10 and Technology Choices; sorted by name.
  - [x] `select_plan_files(listings, slice_index, initiative_index) -> tuple[str, ...]`: given a mapping of directory → file listing and the D1 layout rows, return matches in the table's order, then by file name. The layout rows (directories and patterns) are passed in, not spelled here; they live in `source_reads.py` (Task 6.1). Define a small `PlanRow` dataclass in `passages.py` that `source_reads.py` fills.
  - [x] Success: no I/O; typecheck passes.

- [x] **4.2 Tests for selection** (`tests/runner/answering/test_passages.py`)
  - [x] Rules: literal hit and miss, `*.md` match, `*` in the middle of a segment, `?` and `[` treated literally, a name with regex metacharacters.
  - [x] Plan: over a small synthetic `PlanRow` set built in the test (the real rows are Task 6.1's, and Task 6.4 checks them against the fixture repository, so this test spells no real layout), with a hand-written listing: split task files (`132-tasks.x-1.md`, `-2.md`) match one row; a row with no match gives nothing for that row; an absent directory (no listing) matches nothing; `{initiative}` and `{slice}` substitution does not match `1320-…` for `132`; rows are returned in table order, then by file name.
  - [x] Success: tests pass.

- [x] **4.3 `render_passages` and dates** (`runner/answering/passages.py`)
  - [x] One date formatter `format_utc(datetime) -> str` producing `YYYY-MM-DDTHH:MM:SSZ` (converts offsets to UTC, drops sub-seconds), per D5. `parse_git_date(text) -> datetime | None` via `datetime.fromisoformat`; `None` for empty or unparseable (callers turn that into `sources_unreadable`; no fallback).
  - [x] Write 140's D3 format exactly: one `## Passage P<n>` section per passage; `kind`, then `source` (rule/plan) or `question` and `slice` (pm_answer), then `date`; a blank line; the text verbatim; one blank line between sections. Open 140's slice design (`user/slices/140-slice.answering-pipeline.md`, D3) and copy the line shapes from it; if it is unclear, stop and report. Use `PassageKind` values, never literal strings.
  - [x] Success: output for an empty set is defined and tested (state what it is in the test).
  - Note (20261102): line order follows 140's D3 template (kind, source, date, then question and slice for pm_answer), which differs from the wording above.

- [x] **4.4 `assemble`** (`runner/answering/passages.py`)
  - [x] `assemble(committed, pm_answers, *, question_node_id, max_chars, source_commit) -> PassageSet | SourcesProblem` per LLD D7. `committed` is the ordered list of `SourceFile`s (rules in configured order, then plan in D1 order). `source_reads` has already dropped a repeated path (Task 6.3), so `assemble` does not deduplicate.
  - [x] Cut each file; if the rendered rules and plan alone exceed `max_chars`, return `sources_too_large` with the measured size and the limit in `detail`.
  - [x] Order PM answers: same `node_id` as `question_node_id` first, newest first, then others newest first, ties by record id. Add each while the rendered set (`len(render_passages(...))`) stays within the limit; at the first that does not fit, drop it and every later one, listing record ids in `dropped_pm_answers`.
  - [x] Number `P1`..`Pn` after trimming, in rendered order.
  - [x] Success: typecheck passes.

- [x] **4.5 Tests for assembly and rendering** (`tests/runner/answering/test_passages.py`)
  - [x] Order: rules, plan, then PM answers; ids `P1..Pn` gap-free after trimming.
  - [x] Size: rules+plan over the limit gives `sources_too_large` with both numbers in `detail`; under the limit, same-slice PM answers come before others, newest first; the first misfit drops itself and every later answer even if a later one is smaller; `dropped_pm_answers` lists them in order and none appear in the set; ties on date order by record id.
  - [x] Dates: `format_utc` converts `+02:00` to UTC and drops sub-seconds; `parse_git_date("")` and garbage give `None`.
  - [x] Render: a fixed set equals a hand-written expected file (`tests/runner/answering/fixtures/expected_passages.md`) containing all three kinds; a passage text containing a line `## Passage P9` does not add an id to `PassageSet.ids` (LLD "Special Considerations").
  - [x] Success: tests pass.

- [x] **4.6 `check_citations`** (`runner/answering/passages.py`)
  - [x] `check_citations(cited, passage_ids) -> CitationProblem | None` per LLD D8: trim and upper-case each id; an empty list after trimming is `uncited`; ids not in the set, in cited order, once each, are `unknown_ids`; otherwise `None`.
  - [x] Success: no I/O.

- [x] **4.7 Tests for the citation check** (`tests/runner/answering/test_passages.py`)
  - [x] `[]` and `["  "]` → `uncited`; `["p3"]` and `[" P3"]` with `P3` in the set → `None`; two unknown ids → `unknown_ids` in cited order; a duplicate unknown id is reported once; a known plus an unknown id reports only the unknown; accepts a `frozenset` and a `set` for the ids.
  - [x] Success: `uv run pytest tests/runner/answering -q` passes; the purity test covers `passages`.

**Commit**: `feat: assemble, render and citation-check source passages`

---

## 5. Configuration keys

- [x] **5.1 `AnswererSettings.rules_paths` and `passages_max_chars`** (`runner/project_config.py`)
  - [x] Add `rules_paths: tuple[str, ...]`, required, no default. Each entry is stripped, non-blank, not absolute, has no `..` segment, and `*` appears only in the last segment. Validate with a field validator whose error names the entry's index, so the load error reads like `projects.amoeba.answerer.rules_paths.1: …` (per LLD D10; look at how the existing validators here produce key-path errors and follow them).
  - [x] Add `passages_max_chars: Annotated[StrictInt, Field(ge=1)]`, required, no default.
  - [x] Update the class docstring (it names two keys; now four).
  - [x] Update every existing test or fixture that writes an `answerer` section (`ANSWERER_FILE`, `_answerer_file` callers, factory, tick and answering tests; search with `grep -rn "answer_limit" tests src`) so each carries both new keys.
  - [x] Success: `uv run pytest -q` passes.

- [x] **5.2 Config tests** (`tests/runner/test_project_config.py`)
  - [x] Each fails at load with its key path: missing `rules_paths`; missing `passages_max_chars`; a blank entry; an absolute entry; an entry with a `..` segment; `*` outside the last segment; `passages_max_chars: 0`; a non-integer `passages_max_chars`.
  - [x] `rules_paths: []` loads; entries are stripped; `?`, `[` and a trailing-segment `*` are accepted; the two keys are read back from a real YAML file.
  - [x] Success: `uv run pytest tests/runner -q` passes.

**Commit**: `feat: add rules_paths and passages_max_chars answerer keys`

---

## 6. Committed source reads

- [ ] **6.1 CF layout constants** (`runner/answering/source_reads.py`, new)
  - [ ] Define once the D1 table as `PlanRow` values (directory, pattern with `{initiative}`/`{slice}` placeholders, `required` flag; only the slice plan row is required), the `project-documents/user` root constant, and `SliceRef(slice_index, initiative_index)`. No other module spells a directory or file-name pattern.
  - [ ] Success: imports; typecheck passes.

- [ ] **6.2 Fixture repository helper** (`tests/runner/git_repo.py` or `tests/runner/answering/sources_repo.py`)
  - [ ] Build a temporary repository from the frozen fixtures at their real relative paths on branch `main`, each commit with a controlled `GIT_COMMITTER_DATE` (extend `commit_file` with an optional `date` parameter without changing existing callers). Return the repo path and a mapping of path → expected committer date.
  - [ ] Success: the repository contains every fixture file and `git log` shows the controlled dates.

- [ ] **6.3 Locate and select** (`runner/answering/source_reads.py`)
  - [ ] `locate_sources(checkout, target, slice_ref, rules_paths, budget, run, timeout_seconds) -> SourceSelection | SourcesProblem | None`: resolves the commit, lists directories and selects the ordered file paths (rules in configured order, then plan in D1 order), per LLD D1, D2 and D10. A path already selected is skipped, so it is read once at its first position.
  - [ ] Problems per LLD D2 and D9: any failed git call or non-zero exit is `sources_unreadable` (command and stderr head); an unmatched rules entry or no slice plan is `sources_missing`; `None` from `git_read` returns `None`. Absence comes only from listings.
  - [ ] Success: typecheck passes.

- [ ] **6.4 Tests for locate and select** (`tests/runner/answering/test_source_reads.py`, new)
  - [ ] Slice 132 / initiative 120: paths in the order rules, concept, initiative plan, `120-arch`, `120-slices`, `132-slice`, `132-tasks`.
  - [ ] A file matched by two rules entries, or by a rules entry and a plan row, appears once at its first position.
  - [ ] Pinned commit: a commit added to the target after the first call is not mixed in (a `run` wrapper commits after the first call); the returned commit is the first one.
  - [ ] No slice plan → `sources_missing`; no design and no tasks yields the rest; an unmatched rules entry → `sources_missing` naming it; a root-level entry (`CLAUDE.md`) is found through the root listing; an absent plan directory matches nothing; a target that does not resolve → `sources_unreadable`.
  - [ ] Success: `uv run pytest tests/runner/answering/test_source_reads.py -q` passes.

- [ ] **6.5 `read_committed_sources`** (`runner/answering/source_reads.py`)
  - [ ] `(checkout, target, slice_ref, rules_paths, max_chars, budget, run, timeout_seconds) -> CommittedSources | SourcesProblem | None`: calls `locate_sources`, then for each selected file reads its date (`last_change_args`, parsed with `parse_git_date`) and its text (`show_object_args`), per LLD D2, D5 and D7. `CommittedSources` holds the commit and the ordered `SourceFile`s.
  - [ ] Failures per LLD D2, D5 and D9: a failed or non-zero read, or an empty or unparseable date, is `sources_unreadable` (never a fallback); `UnicodeDecodeError` is caught around the file `show` only, with a comment saying why (binary file; `run_cf` decodes text), and is `sources_unreadable` naming the path; the running text total exceeding `max_chars` returns `sources_too_large` ("at least" the total) without reading the rest.
  - [ ] Keep functions near 50 lines.
  - [ ] Success: typecheck passes; file near 300 lines or less.

- [ ] **6.6 Tests for file reads** (`tests/runner/answering/test_source_reads.py`)
  - [ ] Each file has its controlled committer date and committed text; an uncommitted edit to a rules file and an untracked file matching the glob are absent.
  - [ ] A `run` wrapper making the `show` of one listed file exit non-zero → `sources_unreadable`, not a set without it; a non-UTF-8 file matched by a glob → `sources_unreadable` naming the path, no exception.
  - [ ] Date read never falls back (LLD D5): a `run` wrapper making the date read (`log`) for one listed file exit non-zero → `sources_unreadable`; the same wrapper returning an empty line, and again a garbage line, → `sources_unreadable`. In each case the result is not a set that carries the commit date or the current time for that file.
  - [ ] Budget: for every N from the first call to the last, a budget refusing the Nth call returns `None`. A recording budget shows exactly `2 + L + 2F` calls for the slice-132 fixture (state the expected number as a literal beside the formula), and the read completes under a budget allowing exactly that many.
  - [ ] Early stop: with a small `max_chars`, `sources_too_large` after fewer calls than the full set.
  - [ ] Success: `uv run pytest tests/runner/answering/test_source_reads.py -q` passes; `tests/runner/test_git_read_only_place.py` still passes.

**Commit**: `feat: read rules and plan sources from one committed target commit`

---

## 7. Entry point: `assemble_sources`

- [ ] **7.1 `slice_label` and `pm_precedent`** (`runner/answering/sources.py`, new)
  - [ ] `slice_label(node) -> str`: `"<cf.index> <title>"`; a node without `cf.index` raises `ValueError` (LLD D6). Read how `Node` exposes `cf.index` and `title` before writing.
  - [ ] `pm_precedent(store, project_id) -> tuple[PmAnswer, ...]`: from `store.questions(project_id, state=QuestionState.ANSWERED)` keep records with `answered_by = AnsweredBy.PM`, a non-blank `answer` and a non-blank `question`. Each carries the record id, question, answer, `updated_at` as its date, the slice node id and its label (via `store.get_node`; a record whose node is missing raises, as a programming error). Use the exact enum names 141 defines (open `store/question_models.py`).
  - [ ] Success: typecheck passes.

- [ ] **7.2 `assemble_sources`** (`runner/answering/sources.py`)
  - [ ] Signature per LLD API Contracts: `(store, project_id, record, snapshot, cf_project_id, settings, budget, run, timeout_seconds) -> PassageSet | SourcesProblem | None`.
  - [ ] Steps per LLD Data Flow and D3/D9: `store.get_node(record.node_id)`; derive `SliceRef` from the node's `cf.index` and its parent's `cf.index`; a node with no parent, a parent that is not an initiative, or a parent without `cf.index` raises `ValueError`. `resolve_checkout(snapshot, slice_index, is_dir=Path.is_dir)`; `CheckoutUnresolved` → `sources_unreadable` with its reason. `read_target`; `ReadFailure` → `sources_unreadable` with its detail; `None` → `None`. Then `read_committed_sources`, `pm_precedent`, `assemble`.
  - [ ] `None` from any budgeted call returns `None`. Problems are returned, never raised.
  - [ ] Success: typecheck passes; no new store operation or write.

- [ ] **7.3 Tests for the entry point** (`tests/runner/answering/test_sources.py`, new)
  - [ ] Precedent (real store via `tests/question_harness.py`): an `answered_by = answerer` record, a PM answer with blank text, and a PM answer with no question are excluded; a PM answer with text is a passage with its question, slice label and `updated_at` as UTC.
  - [ ] `slice_label` returns e.g. `143 Source Passages` shape for a node with index and title; raises `ValueError` without `cf.index`. A slice node with no parent, a non-initiative parent, or a parent without an index raises `ValueError`.
  - [ ] `CheckoutUnresolved` and a failed target read give `sources_unreadable` with their detail; a budget refusal at each step gives `None`.
  - [ ] End to end: against the fixture repository and a throwaway store, `assemble_sources` followed by `render_passages` equals an expected file (`tests/runner/answering/fixtures/expected_end_to_end.md`), including one same-slice and one other-slice PM answer and a rules glob. If the repository cannot be reached through `resolve_checkout` with a hand-built snapshot, follow how `tests/runner/dispatch/test_checkout.py` builds one.
  - [ ] Success: `uv run pytest tests/runner/answering -q` passes.

**Commit**: `feat: add assemble_sources with PM precedent and slice labels`

---

## 8. Documentation

- [ ] **8.1 Process contract** (`docs/process-contract.md`)
  - [ ] "The project config": document `rules_paths` and `passages_max_chars` with the load rules from LLD D10 and the example block (the example values appear only here).
  - [ ] "Git and the pre-dispatch check": change `status` and `merge-base` only to include `show` and `log`; note they read objects at a pinned commit, never the working tree.
  - [ ] New "Context Forge shapes" section next to the Squadron shapes bullet: the D1 layout table, an "observed on CF" line whose version is exactly what `cf --version` prints when you run it, with today's date, as a dated observation (if the command prints nothing, stop with an error; do not write a version from memory), and D5's note that a branch-edited file keeps its commit date.
  - [ ] "The answering pipeline": a short paragraph naming the passage set, `passages.md`, the citation check and that nothing calls assembly until 144.
  - [ ] Success: contract text matches the code; no mention of version numbers as dependencies.

- [ ] **8.2 Final checks**
  - [ ] Run `uv run ruff format .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest -q` once each. All pass; fix any failure.
  - [ ] Confirm `passages.py` is in the purity check, no module outside `git_read.py` starts `git`, and nothing outside tests calls `assemble_sources`.
  - [ ] Set the slice design's `status` and `dateUpdated` only if the process guide's Phase 6 close-out says to; otherwise leave them.
  - [ ] Success: all green; branch is ready for code review (do not merge).

**Commit**: `docs: document source passages, answerer keys and the Context Forge layout`
