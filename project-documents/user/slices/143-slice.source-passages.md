---
docType: slice-design
slice: source-passages
project: amoeba
parent: user/architecture/140-slices.question-answerer.md
dependencies:
- 141
interfaces:
- 144
dateCreated: 20261101
dateUpdated: 20261102
status: complete
turns: 30
promptTokens: 3070203
cachedTokens: 2927701
cacheWriteTokens: 142444
completionTokens: 34923
durationSeconds: 373.5
costUsd: 2.424114
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.4241135000000003
    completionTokens: 34923
---

# Slice Design: source-passages

## Overview

This slice builds the passage set an answering run sees, and the check that an answer cites only passages in that set. The sources are the project's rules (configured paths and globs), its CF plan, and the PM's recorded answers. Rules and plan are read with `git show` from one commit of the target branch. The set is cut at headings, dated, numbered `P1` to `Pn` and rendered in 140's `passages.md` format. Nothing calls assembly outside tests in this slice; 144 is the first caller.

## Value

Architectural enablement. 144 gets one call that returns a passage set or a named problem, and a pure citation check, so "the answer cites passages in the set" is a set lookup with no model involved. Everything is testable without Squadron or an LLM.

## Technical Scope

Included:

- Two new read commands in the Runner's git allowlist, `show` and `log`, with argument builders (D2).
- CF document layout knowledge, defined once in `source_reads.py` (D1).
- Locating the git directory and target for a slice: its checkout from the CF snapshot, and the target from `git.integration_branch` (D3).
- Reading committed sources: resolve the target to a commit, list directories, select rules and plan files, read each file and its last-change date (D1, D2, D5).
- Cutting files into passages (D4), and reading PM precedent from the question record (D6).
- Pure assembly: ordering, numbering, the size limit and the PM-answer trimming order (D7), and rendering to `passages.md`.
- The citation check (D8).
- `AnswererSettings` gains `rules_paths` and `passages_max_chars`, both required (D10).
- Fixture files: frozen copies of this project's own rules and plan files (D11).
- Process contract: the two answerer keys, the CF layout this slice reads, and the git allowlist.

Excluded:

- Launching the answering run, preparing the scratch directory and writing `passages.md` to it (140 and 144).
- Turning a problem into a decline, and the `DeclineReason` members for it (144, D9).
- Storing the passage set, the cited passages or the dropped PM answers on the question record (144, which adds those columns).
- Code as a source (arch, "Assembling sources").
- Any store write, migration or new store operation. This slice only reads 141's record.

## Dependencies

### Prerequisites

- **141 (question record).** Not yet implemented. This design reads `questions(project_id, *, state=None, node_id=None)`, the `question_records` columns `node_id`, `question`, `answer`, `answered_by` and `updated_at`, `QuestionState`, `AnsweredBy` and `ProjectSettings.answerer: AnswererSettings | None`. Checked 20261101 against 141's design (API Contracts, Database / Storage Schema, D3 and D6): every name matches. `Store.get_node` was checked against the code (`store/_base.py`). If 141's code departs from its design, 143's tasks follow the code.
- **142 (gate and submission) is not a dependency.** The slice plan lists only 141. 142 adds `answer_limit` and `reserved_terms` to `AnswererSettings` (142, D7, checked 20261101); 143 adds two more keys to the same model. Whichever is built second adds its keys to the model the first one left. The only overlap is that model and its load tests.
- **140, as a written contract only.** The `passages.md` format in 140's D3, and `QuestionInput.slice_label` and `prepare_scratch(..., passages_markdown, ...)` in its API Contracts, checked 20261101. No code is shared, so 143 does not wait on 140 or on its Squadron issue.
- **Runner slices 128 and 132, already merged.** `git_read`, `resolve_checkout`, `read_target`, `TickBudget` and `CfRun`. These are existing code, not slices this one waits on.

### Interfaces Required

- `amoeba.runner.git_read.git_read` and `GIT_SUBCOMMANDS` (extended here).
- `amoeba.runner.dispatch.checkout.resolve_checkout(snapshot, slice_index, is_dir=…)` and `amoeba.runner.dispatch.checkout_reads.read_target(...)`.
- `Store.get_node(node_id)`: a node's `cf.index`, `title` and `parent_id`.
- From 141: `Store.questions`, `QuestionRecord`, `QuestionState`, `AnsweredBy`, `AnswererSettings`.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Git reads | `runner/git_read.py` (extended) | `show` and `log` in the allowlist; `resolve_commit_args`, `show_object_args`, `last_change_args`; `parse_tree_listing` |
| Passages | `runner/answering/passages.py` | Pure. The types (`PassageKind`, `Passage`, `PassageSet`, `SourceFile`, `PmAnswer`, `SourcesProblem`, `SourcesProblemKind`, `CitationProblem`), cutting (D4), plan-file selection and rules glob matching against listings (D1), `assemble`, `render_passages`, `check_citations` |
| Source reads | `runner/answering/source_reads.py` | The CF layout constants (D1) and `read_committed_sources`: every git call this slice makes |
| Entry point | `runner/answering/sources.py` | `assemble_sources(...)`, the one call 144 makes: locates the checkout and target (D3), reads PM precedent and `slice_label` (D6), and calls the other two |
| Settings | `runner/project_config.py` | `AnswererSettings.rules_paths`, `AnswererSettings.passages_max_chars` |

`passages.py` is pure and is added to `tests/runner/purity.py`. Everything that can be decided without I/O is in it, so the two I/O modules only fetch.

### Data Flow

```
144 (tests in 143)
  assemble_sources(store, project, question_record, snapshot, settings, budget, run, timeout)
    node      = store.get_node(record.node_id)          slice index, title, parent initiative
    resolve_checkout(snapshot, slice_index)              -> checkout path   (store read, no subprocess)
    read_target(checkout, cf_project_id, ...)            -> target branch   (cf config get git.integration_branch -p <cf_project_id>)
    committed = read_committed_sources(location, SliceRef(slice, initiative), settings.rules_paths,
                                       settings.passages_max_chars, ...)
                  git log -1 --format=%H <target>        -> commit C (every later read uses C)
                  git show C:project-documents/user      -> which plan directories exist
                  git show C:<dir>                       for each existing plan directory and each rules directory (C: for the root)
                  select rules files (config order) and plan files (D1 order), from the listings only
                  for each file: git log -1 --format=%cI C -- <path>   -> date
                                 git show C:<path>       -> text; stop with sources_too_large once the text read exceeds max_chars (D7)
                  calls made: 2 + L + 2F  (L directory listings, F files read; D2)
    pm        = pm_precedent(store, project_id)          answered_by=pm, answer and question present
    result    = assemble(committed, pm, question_node_id=record.node_id, max_chars=settings.passages_max_chars)
                  rules + plan passages, cut at headings; over max_chars -> SourcesProblem(sources_too_large)
                  PM answers in D7 order until the next one does not fit; the rest are dropped
                  ids P1..Pn in rendered order
  -> PassageSet | SourcesProblem | None (budget ran out)

144 later
  prepare_scratch(dir, question, render_passages(set), max_cost)      (140)
  check_citations(answer.cited, set.ids) -> CitationProblem | None
```

### State Management

None. Assembly reads git and the store and returns a value. Nothing is cached between questions or ticks: each assembly reads the target as it is at that moment, so a rule committed between two questions is in the second question's passages. 144 records what it needs from the result on the question record.

## Technical Decisions

### D1 — Plan files are found by CF's document layout, listed at the target commit

Status: decided

- Concept, initiative plan and tasks paths are not in any `cf` output. `archFile` is a bare file name, and `designFile` is null until a design exists, yet questions are asked during design. So the plan files are found the same way for every slice: by listing CF's document directories at the target commit and matching file names against CF's naming convention (`file-naming-conventions.md`).
- `source_reads.py` holds the layout as constants, the only module that reads it. Every value is upstream shape knowledge, recorded in the process contract as observed on CF 0.19.24:

| Plan file | Directory | Pattern |
| --- | --- | --- |
| Concept | `project-documents/user/project-guides` | `000-concept.*.md` |
| Initiative plan | `project-documents/user/project-guides` | `001-initiative-plan.*.md` |
| Architecture | `project-documents/user/architecture` | `{initiative}-arch.*.md` |
| Slice plan | `project-documents/user/architecture` | `{initiative}-slices.*.md` |
| Slice design | `project-documents/user/slices` | `{slice}-slice.*.md` |
| Tasks | `project-documents/user/tasks` | `{slice}-tasks.*.md` (split files `-1`, `-2` all match) |

- `{slice}` is the slice node's `cf.index`. `{initiative}` is the `cf.index` of its parent node. That parent is always an initiative node with an index: the Runner creates slice nodes only from `cf list slices <initiative>`, under the initiative node it read them from (`runner/lifecycle/reconcile.py`, `_create_slice`). A slice node with no parent, a parent that is not an initiative, or a parent without `cf.index` raises `ValueError` as a programming error, as `slice_label` does (D6). Every match is included, in the table's order, then by file name. One listing of `project-documents/user` says which of the four directories exist, and one listing of each existing directory covers all six rows.
- **Only the slice plan is required.** A slice exists in CF only through a slice plan, so finding none means the layout or the target is wrong, and assembly fails with `sources_missing`. Every other row may match nothing: there are no tasks before Phase 5 and no design before Phase 4, and an initiative whose `archFile` is null has no architecture. A directory absent from the `project-documents/user` listing counts as matching nothing.
- **Rejected:** three `cf` calls per question (`list initiatives`, `list slices`, `list tasks`). They still leave concept and initiative plan unknown, return bare names whose directory must be assumed anyway, and read CF's view of the working directory rather than the target commit. **Also rejected:** plan paths in project configuration. The design and tasks files differ per slice, so the configuration would need index placeholders, which is a template language for a fact CF's convention already fixes.

### D2 — Every read is pinned to one commit; the allowlist gains `show` and `log`

Status: decided

- The first read resolves the target branch to a commit: `git log -1 --format=%H <target>`. Every later read names that commit, not the branch. A merge to the target during assembly therefore cannot mix files from two commits, and the commit goes in the result (`PassageSet.source_commit`) for 144 to record.
- `GIT_SUBCOMMANDS` becomes `{status, merge-base, show, log}`. Both new commands are read-only. The module docstring and the allowlist test are updated with them. The slice plan's "reads git with `show` and `log` only" is met: no `ls-tree` or `cat-file`.
- Argument builders, each refusing a value that starts with `-`, as `is_ancestor_args` does:
  - `resolve_commit_args(target)`: `log -1 --format=%H <target>`
  - `show_object_args(commit, path)`: `show <commit>:<path>` (a blob prints its content, a tree prints its entries). An empty `path` gives `<commit>:`, the root tree, which lists root-level rules entries such as `CLAUDE.md`.
  - `last_change_args(commit, path)`: `log -1 --format=%cI <commit> -- <path>`; the output is one ISO 8601 line, read by D5
- `parse_tree_listing(text)` reads `git show <commit>:<dir>` output leniently: it skips the `tree …` header line and blank lines, keeps file entries, and drops entries ending in `/` (subdirectories). Directories are not walked.
- **Absence is read from listings, never from an exit code.** A non-zero exit can mean a missing path, a bad object, a corrupt repository or a lock, and git's exit code does not say which. So every non-zero exit, from any `show` or `log`, is `sources_unreadable` with the command and git's stderr head. Whether a file or directory exists is decided only from the listing of its parent: a plan directory from the `project-documents/user` listing, a plan file or glob match from its directory's listing, and a literal rules entry from its parent directory's listing. A file is read only after a listing has shown it, so a failed read of it is always an error, never "absent". `project-documents/user` and each rules entry's parent directory must exist; failing to list them is `sources_unreadable` naming the entry.
- **The call count.** One assembly makes `2 + L + 2F` git calls: the `log` for the commit, the `show` of `project-documents/user`, one `show` per directory listed (`L`: each existing plan directory and each rules entry's parent directory, the root counted once), and for each file read (`F`) one `log` for its date and one `show` for its text. For this project's configuration (three or four rules entries, up to six plan files from at most four directories) that is a few dozen calls of local object reads.
- **The budget, and what a refusal costs.** `git_read` checks the tick budget before every call. The budget is a time budget, not a call count: `tick_deadline_seconds` (5 seconds by default), shared by everything in the tick (`TickBudget.allows_call`). A refused call returns `None`, the question stays `pending`, and nothing is cached, so the next tick starts assembly again from the commit read. Restarting is cheap because the next tick has a fresh deadline, and a question can only starve if one assembly takes longer than a whole tick. Reading stops as soon as the text read exceeds `passages_max_chars` (D7), so `F` is bounded by the size limit and not by the number of files a glob matches. A question whose assembly keeps being refused is visible: it stays `pending` on the questions listing (141). A test counts the calls for the slice-132 fixture and fails if they differ from the formula (see Technical Requirements).
- **Not detected: symlinks and submodules.** A listing cannot tell them from files, and telling them apart would need the file mode from a second source. The sources are the project's own committed rules and plan documents. A symlink there would yield a one-line passage holding a path, which grounds no answer, and the check step would decline it. No guard is worth the extra parser.
- **Rejected:** batching the files into one `git show C:a C:b …`. The blobs come out concatenated with no separator, so they cannot be split reliably.

### D3 — Git runs in the slice's checkout, reading objects only

Status: decided

- `git show` needs a repository, so `assemble_sources` uses the slice's checkout as found by `resolve_checkout` from the link's latest observed snapshot (a store read), and the target as read by `read_target` in that checkout. These are the same functions the dispatch reads use, so the answering run reads the same target that the slice merges into.
- Reading `C:<path>` reads objects, never the working tree or the index. An uncommitted edit, an untracked file and the paused run's own changes are invisible. The architecture's "launch without a checkout" is unaffected: this needs no clean-tree check, no branch check and no checkout hold, and the answering run itself still never sees the checkout.
- `CheckoutUnresolved` and a failed target read are `sources_unreadable` with their detail. A budget refusal is `None`.

### D4 — Files are cut at headings of levels 1 to 3, losing no text

Status: decided

- `cut_passages(text)` starts a new passage at every ATX heading of level 1 to 3 (up to three leading spaces, then `#`, `##` or `###`, then a space or the end of the line), outside fenced code blocks (```` ``` ```` or `~~~`). Deeper headings stay inside their parent's passage. Text before the first heading, front matter included, is its own passage when it is not blank.
- **Never cut means nothing is lost.** Joining a file's passages gives back the file exactly, apart from a blank preamble. A property test asserts this on every fixture file. A long section stays one long passage.
- A file with no headings, such as a plain-text rules file, is one passage. An empty file gives none.
- The heading stays as the passage's first line, so a citation points at a named section. Passage text is never rewritten, escaped or prefixed (140, D3).
- **Rejected:** fixed-size chunks. They split sentences and rules mid-way, and give the check step citations with no section name. **Also rejected:** cutting at every heading level. A level-4 heading usually heads a few lines, and the passage count would grow with no gain in precision.

### D5 — Dates: the file's last commit, and the PM's answer time

Status: decided

- A rules or plan passage carries its file's last-change date: the committer date of the newest commit reachable from `C` that changed the file (`last_change_args`).
- **That is when the change was committed, not when it reached the target.** The two are the same for the files this slice reads. Planning documents (Phases 0–5) and fixes are committed directly on the target, never on a branch (project git rules, "Branch Naming"; `fixes.md`), and rules files change through guide updates and fixes on the target. A plan or rules file edited on a slice branch and merged later keeps its branch commit date. In that case a PM answer given between the commit and the merge outranks the edit, and the check step can say yes on it. That is a known limit.
- A PM passage carries its record's `updated_at`, the moment the acknowledgment marked it `answered` (141, Integration Points). `answered` is terminal, so the value never moves afterwards.
- Both are rendered as UTC, to the second, `YYYY-MM-DDTHH:MM:SSZ`, by one formatter (140, D3). Git's `%cI` offset is converted to UTC. Sub-second store precision is dropped. Two passages with the same second have equal precedence, which the check step is told how to handle (140, D3, "Ties").
- An empty or unparseable date is `sources_unreadable` (D2). It never falls back to the commit date or to now.

### D6 — PM precedent is every PM answer with text and a question

Status: decided

- `pm_precedent(store, project_id)` reads `questions(project_id, state=answered)` and keeps records with `answered_by = pm`, a non-blank `answer` and a non-blank `question`. That is 141's definition of precedent, plus a question: a `pm_answer` passage must carry the question it answered (140, D3), and without one the answer step has nothing to match by meaning.
- Answers with `answered_by = answerer` never pass this filter. That rule is in one place, and a test with an answerer-answered record proves it.
- Each `PmAnswer` carries the record id, the question, the answer, the date (D5), the slice node id, and the slice label.
- `slice_label(node)` is `"<cf.index> <title>"`, for example `143 Source Passages`. It is the label on PM passages and on `question.md`, which 144 renders with 140's `QuestionInput`, so the answer step compares two labels made by one function. A slice node without `cf.index` raises `ValueError`. The Runner only launches runs on CF-linked slices, so this is a programming error.

### D7 — The size limit, and the order PM answers are kept in

Status: decided

- `passages_max_chars` bounds the rendered `passages.md`, measured in characters (`len` of the rendered string). It measures what the answering run is actually sent, headers included.
- **Order in the set.** Rules files in configured order, then plan files in D1's order, each file's passages in file order, then PM answers in the order below. Ids are assigned `P1` to `Pn` in that order, after trimming, so the ids in the rendered file have no gaps.
- **Rules and plan are never trimmed.** If the rendered rules and plan passages alone exceed the limit, the result is `SourcesProblem(sources_too_large)` carrying the measured size and the limit.
- **Reading stops early.** `read_committed_sources` keeps a running total of the file text it has read, in the order above. The rendered set is never smaller than that text, so once the total exceeds `passages_max_chars` it returns `sources_too_large` without reading the remaining files, and the detail says the size is "at least" the total. This is what bounds the git calls (D2). A set whose text fits but whose rendered form, with headers, does not is caught when the set is rendered, by the check above.
- **PM answers are kept in this order:** answers for the question's own slice (same `node_id`), newest first, then all other answers, newest first. Ties on date go by record id, so the order is stable. Each answer is added while the rendered set stays within the limit. At the first one that does not fit, it and every later one are dropped. A smaller, lower-priority answer is not let in past a dropped one, because that would break the stated order.
- `PassageSet.dropped_pm_answers` lists the dropped record ids in order. 144 records them on the question, so a wrong answer can be traced to precedent the check step never saw (arch, "Stale precedent and growth").

### D8 — The citation check is a set lookup

Status: decided

- `check_citations(cited, passage_ids) -> CitationProblem | None`, where `passage_ids` is `PassageSet.ids`. It takes the ids, not the set, because 144 decides ticks after assembly, from the ids it recorded at launch (144, D7). Each cited id is trimmed and upper-cased before lookup, so `p3` and `" P3"` both match `P3`. That follows the project's lenient-parsing rule; the ids themselves are always `P` and a number.
- `CitationProblem(kind, ids)`, with `kind` either `uncited` (an empty list after trimming) or `unknown_ids` (every id not in the set, in cited order). Duplicate ids are allowed and checked once.
- This is the one place the "every cited id is in the set" rule lives. 140's parser checks only the shape (140, D6).

### D9 — Results are values; problems are a closed vocabulary that 144 maps to declines

Status: decided

- `assemble_sources` returns `PassageSet`, `SourcesProblem`, or `None` when the budget refused a call. It raises only on programming errors (a node without an index, an argument starting with `-`).
- `SourcesProblemKind` is a closed `StrEnum`:

| Kind | When |
| --- | --- |
| `sources_too_large` | Rules and plan passages alone exceed `passages_max_chars` (D7) |
| `sources_missing` | A configured rules entry matches nothing at the commit, or no slice plan is found (D1, D10) |
| `sources_unreadable` | No checkout, a failed target read, a target that does not resolve, a git timeout or failure, a file that is not UTF-8, or a date that cannot be read |

- `SourcesProblem(kind, detail)` names the path or command in `detail`.
- **A file that is not UTF-8.** `run_cf` decodes output as text, so a binary file raises `UnicodeDecodeError` out of the `show` call. `source_reads` catches that one exception around the file read, with a comment saying why swallowing it is correct, and returns `sources_unreadable` naming the path.
- 144 adds the `DeclineReason` members for these kinds and maps them, as it maps 140's `ArtifactProblem`. A problem is never retried: the question is declined and the PM sees it (arch, "Failures decline; nothing retries"). Only `None` leaves the question pending for the next tick.
- **Rejected:** adding the decline reasons here. Nothing in 143 declines, and a store vocabulary member with no writer has no test that reaches it.

### D10 — Two required configuration keys

Status: decided

```yaml
projects:
  amoeba:
    pipeline: p456
    answerer:
      answer_limit: 3                 # 142
      reserved_terms: [push, merge to main, release, DROP]   # 142
      rules_paths:
        - CLAUDE.md
        - project-documents/ai-project-guide/project-guides/rules/*.md
      passages_max_chars: 200000
```

- `rules_paths` is a list of repo-relative paths. Each entry is stripped and must be non-blank, must not be absolute and must not contain a `..` segment. The only glob character is `*`, allowed in the last segment only. Any other character, `?` and `[` included, is literal. The last-segment rule keeps glob expansion to one directory listing per entry. Each entry must match at least one file at the target commit, or assembly fails with `sources_missing` naming the entry. An entry that matches nothing is almost always a typo or a moved directory, and dropping it silently would remove rules the PM expects the answerer to follow.
- A file matched by two entries, or by an entry and a plan row, appears once, at its first position.
- `rules_paths: []` loads, as `reserved_terms: []` does in 142: an empty list is accepted only when written explicitly. A missing key fails at load.
- `passages_max_chars` is a `StrictInt` of at least 1. Both keys are required, with no defaults (`extra="forbid"`, as 141 set). The example values appear only in the process contract's example config.
- Load errors name the key path, for example `projects.amoeba.answerer.rules_paths.1: `*` allowed in the last segment only`.

### D11 — Fixtures are frozen copies of this project's own files, in a temporary repository

Status: decided

- `tests/runner/answering/fixtures/sources/` holds copies of real files from this repository, at their real relative paths: `CLAUDE.md`, two rules files (`python.md`, `git.md`), the concept, the initiative plan, `120-arch`, `120-slices`, `132-slice` and `132-tasks`. Slice 132 is used because every one of its plan files exists.
- The copies are frozen, so tests can assert exact passage counts and headings without breaking when the live documents change.
- A test helper (extending `tests/runner/git_repo.py`) builds a temporary repository from them with controlled commit dates (`GIT_COMMITTER_DATE`), so the dates in D5 are asserted exactly.
- **Rejected:** reading this repository's own history in tests. CI checks out a pull-request branch, often shallow and without a local `main`, so the result would depend on how the checkout was made.

### Technology Choices

- Stdlib only: `re` for the last-segment glob (the segment's literal parts are escaped and `*` becomes `.*`, so `?` and `[` stay literal, as D10 says), `pathlib.PurePosixPath` for path checks, `datetime.fromisoformat` for git dates, and a line scanner for headings. No markdown library: the only structure read is ATX headings and code fences, and a parser would add a dependency for that.
- Pydantic for the two settings, as 141 and 142 do.

### Patterns and Conventions

- Every git argument list is built in `git_read.py`, and every CF directory and file-name pattern lives in `source_reads.py`. No other module spells either.
- Passage kinds (`rule`, `plan`, `pm_answer`) are a `StrEnum` whose values are the `kind:` words in 140's format. Rendering uses the enum values, never literal strings.
- Readers return a value, a problem or `None`, and never raise for something the repository or configuration can cause. That matches the Runner's existing read modules.

## Implementation Details

### API Contracts

Python surface provided to 144 (signatures are the contract; bodies are implementation):

```python
class PassageKind(StrEnum): RULE = "rule"; PLAN = "plan"; PM_ANSWER = "pm_answer"

@dataclass(frozen=True)
class Passage:
    id: str                    # "P1".."Pn"
    kind: PassageKind
    source: str | None         # repo-relative path; None for pm_answer
    date: datetime             # UTC
    text: str                  # verbatim
    question: str | None       # pm_answer only
    slice_label: str | None    # pm_answer only
    question_id: str | None    # pm_answer only: the record it came from (not rendered)

@dataclass(frozen=True)
class PassageSet:
    passages: tuple[Passage, ...]
    source_commit: str
    dropped_pm_answers: tuple[str, ...]
    @property
    def ids(self) -> frozenset[str]: ...   # every passage id

def assemble_sources(store, project_id, record, snapshot, cf_project_id,
                     settings: AnswererSettings, budget, run, timeout_seconds
                     ) -> PassageSet | SourcesProblem | None: ...
def render_passages(passage_set: PassageSet) -> str: ...
def check_citations(cited: Sequence[str], passage_ids: Collection[str]) -> CitationProblem | None: ...
def slice_label(node: Node) -> str: ...
```

`render_passages` writes 140's D3 format exactly: one `## Passage P<n>` section per passage, the `kind`, `source` (rule and plan) or `question` and `slice` (pm_answer), and `date` lines, a blank line, then the text verbatim, with one blank line between sections. A test renders a fixed set and compares it to a hand-written expected file.

Project config (`docs/process-contract.md`, "The project config"): `rules_paths` and `passages_max_chars`, with the load rules from D10.

Process contract, "Squadron shapes" sibling section "Context Forge shapes": the D1 layout table, observed on CF 0.19.24, and D5's note that a branch-edited file keeps its commit date.

## Integration Points

### Provides to Other Slices

- **144 (answering run):** `assemble_sources`, `render_passages` (whose output goes to 140's `prepare_scratch` unchanged), `check_citations`, `slice_label` for `QuestionInput.slice_label`, and the `SourcesProblemKind` vocabulary to map to decline reasons. 144 records `source_commit`, the cited passages and `dropped_pm_answers` on the question record.
- **144:** keeps a case for D5's known limit: a plan file edited on a branch and merged after a PM answer keeps its branch commit date.
- **145 (walkthrough):** the "PM answer used for a reworded question" and "PM answer after a rule change stands" cases rest on D5's dates and D6's selection.

### Consumes from Other Slices

- **141:** the question record and its `answered_by`/`answer` fields. If 141's implementation renames them, 143's tasks follow. The behavior relied on is that an answerer's answer is never `answered_by = pm`.
- **140:** the `passages.md` format, as text. If 140's format changes once Squadron's capabilities land, `render_passages` and its expected-output test change with it. No code is imported.
- **128:** `git_read`, `resolve_checkout` and `read_target`. 143 adds subcommands to the allowlist and changes nothing else in them.

## Success Criteria

### Functional Requirements

- Assembly reads committed content only. With an uncommitted edit to a rules file and an untracked file matching a rules glob in the checkout, the passages hold the committed text and no untracked file.
- Every passage carries its id, its path (rule and plan) or its question and slice (PM answer), and its date. A rules or plan passage carries the committer date of the last commit that changed its file, in UTC.
- For slice 132 in the fixture repository, the set holds the configured rules files, then the concept, initiative plan, `120-arch`, `120-slices`, `132-slice` and `132-tasks`, in that order. Joining each file's passages gives back the file.
- A target with no slice plan for the slice's initiative fails with `sources_missing`. A slice with no design or tasks yet assembles without them.
- A rules entry that matches nothing fails with `sources_missing` naming the entry.
- An answer recorded with `answered_by = answerer` never appears as a passage. A PM answer without text, or with no question, does not appear either.
- With rules and plan over `passages_max_chars`, assembly fails with `sources_too_large`, whose detail carries the limit and the measured size, and stops reading further files once the text read exceeds the limit. Under the limit, PM answers for the same slice are kept before others, newest first, and from the first answer that does not fit, it and all later ones are listed in `dropped_pm_answers` and appear nowhere in the set.
- `check_citations` returns `uncited` for an empty list, `unknown_ids` with each id not in the set, and `None` for ids in the set in any case or with surrounding spaces.
- `rules_paths` and `passages_max_chars` are required with no defaults. A missing key, a blank entry, an absolute path, a `..` segment, a `*` outside the last segment and `passages_max_chars: 0` each fail at load with the key path. `rules_paths: []` loads.

### Technical Requirements

- Tests use the frozen copies of this project's rules and plan files (D11), not invented documents.
- `passages.py` passes the purity check.
- The git allowlist test covers `show` and `log`. `test_git_read_only_place.py` still passes: no module outside `git_read.py` starts `git`.
- A budget that refuses the Nth call returns `None` for every N from the first call to the last.
- Assembly of the slice-132 fixture set, run against a budget that records its calls, makes exactly `2 + L + 2F` calls for the `L` and `F` the fixture has, and completes under a budget that allows exactly that many. The test states the expected number as a literal beside the formula.
- A rules and plan set whose first files already exceed `passages_max_chars` gives `sources_too_large` after reading only those files: the recorded call count is lower than for the full set.
- A `show` that exits non-zero for a file present in its listing gives `sources_unreadable`, never a set without that file.
- A non-UTF-8 file matched by a rules glob gives `sources_unreadable` naming the path. No exception escapes.
- A root-level rules entry is found through the root listing.
- `render_passages` output for a fixed set equals a hand-written file in 140's format.
- Format, lint and typecheck (`ruff`, `pyright` strict) pass, with the runner and process suites.
- Docs: the two answerer keys and the CF layout section in `docs/process-contract.md`. The `git_read` module docstring lists the four subcommands.

### Integration Requirements

- 144 can be designed against the API Contracts without reading 143's code.
- `render_passages(set)` passes 140's `prepare_scratch` as `passages_markdown` unchanged.
- After 143, a project's behavior is unchanged apart from the two new required keys in its answerer section. Nothing calls `assemble_sources` outside tests.

### Verification Walkthrough

Verified 20261102 on branch `143-slice.source-passages`. Nothing calls assembly outside tests in this slice, so every step is a test run from the repository root. Counts are those observed; a later slice that adds tests to these modules raises them.

1. **Pure parts.**

   ```
   uv run pytest tests/runner/answering/test_passages.py -v
   ```

   Expected: 59 passed. Cutting (headings inside both fence styles, level 4, front matter, no headings, empty file, blank preamble, three versus four leading spaces, `#tag`, CRLF), the join-gives-back-the-file property over each of the nine frozen fixture files, plan and rules selection over hand-written listings, dates, assembly order and gap-free ids, the size limit and first-misfit rule, rendering against `tests/runner/answering/fixtures/expected_passages.md`, every citation case, and the purity check.

2. **Git reads against the fixture repository.**

   ```
   uv run pytest tests/runner/answering/test_source_reads.py -v
   ```

   Expected: 45 passed. The nine files in offer order, a file chosen twice kept once, the pinned commit, committed-only reads, controlled dates, a missing slice plan, an unmatched rules entry, a failing `show`, a non-UTF-8 file, an unreadable date (non-zero, empty, garbage), an unresolvable target, 26 calls for the slice-132 fixture (`2 + 6 + 2 * 9`), `None` when any one of the 26 calls is refused, and the early stop on an oversized set.

3. **Precedent and configuration.**

   ```
   uv run pytest tests/runner/answering/test_sources.py tests/runner/test_project_config.py -k "precedent or answerer" -v
   ```

   Expected: 28 passed, 34 deselected. A PM answer with no text or no question and an answerer-answered record are excluded; a PM answer with text carries its question, slice label and answer time. Each load error in D10 names its key path (`...rules_paths.1`).

   ```
   uv run pytest tests/runner/answering/test_sources.py -v
   ```

   Expected: 13 passed. The end-to-end case runs `assemble_sources` against a small repository and a throwaway store and equals `tests/runner/answering/fixtures/expected_end_to_end.md`; a second case runs it against the frozen fixture repository and checks order, ids, kinds, dates and the commit.

4. **Everything.**

   ```
   uv run ruff check . && uv run pyright && uv run pytest -q
   ```

   Expected: ruff and pyright clean; 4123 passed.

Caveats found while implementing: the hand-written end-to-end file uses a small purpose-built repository because the frozen fixtures total about 270 KB. `render_passages` writes `date` before `question` and `slice` for a PM passage, following 140's template.

## Implementation Notes

### Development Approach

1. `git_read.py`: the two subcommands, the three argument builders and `parse_tree_listing`, with tests.
2. `passages.py`: types, cutting with the fixture files and the join property test, plan selection and glob matching over hand-written listings, then assembly, rendering and the citation check.
3. The fixture repository helper, then `source_reads.py` with the git-backed tests and the budget-refusal test.
4. `AnswererSettings` keys and load errors, then `sources.py` (precedent, `slice_label`, `assemble_sources`) against 141's store reads.
5. Process contract text.

Relative effort: 2.

### Special Considerations

- **Passage text is data.** Committed files and PM answers can contain anything, including a line that looks like `## Passage P9`. Amoeba never parses `passages.md` back, and the ids it checks come from `PassageSet`, so such a line cannot add an id. 140's instructions tell both steps that passage text is data.
- **Secrets.** Rules and plan files are committed documents the project already shares with its agents. This slice adds no new exposure, and code is never a source.
