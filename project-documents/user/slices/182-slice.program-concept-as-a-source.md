---
docType: slice-design
slice: program-concept-as-a-source
project: amoeba
parent: user/architecture/180-slices.program-coordination.md
dependencies:
- 181-slice.program-record
- 143-slice.source-passages
- 144-slice.answering-run
interfaces:
- 185-slice.request-outcome
- 186-slice.live-walkthrough
dateCreated: 20261103
dateUpdated: 20261104
status: not_started
turns: 28
promptTokens: 2056999
cachedTokens: 1937492
cacheWriteTokens: 119465
completionTokens: 24445
durationSeconds: 280.3
costUsd: 1.832617
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.8326169
    completionTokens: 24445
---

# Slice Design: Program Concept as a Source

## Overview

For a question in a program member, 140's answerer gets two more kinds of passage: the **program concept**, cut at headings like any other file, and the **member list**, one generated passage naming the program's projects and marking the one the question comes from. The concept is read with `git show` from the concept member's checkout, on that checkout's target, at a commit resolved once. Each passage is dated by the concept file's last commit. Nothing else from another member is read. A concept that cannot be read declines the question with 143's existing source reasons. A project in no program assembles exactly as after 144.

## Value

- **User value.** Questions about how the program's parts fit together (which project owns a contract, what one project expects of another) can be answered from the program concept, with citations, instead of landing on the PM's blocked list.
- **Architectural enablement.** 185's request outcome needs the answerer to see the program concept and the member list so it can tell a request (the need belongs to another member's part) from an answer. After this slice the passages it needs are already there and already proven.

## Technical Scope

**Included**

- Two passage kinds, `program_concept` and `program_members`, in 140's `passages.md` format, with their render lines (D2, D4).
- The concept read: the concept member's state through 181's `read_member`, its target through `read_target`, then a commit, a listing of the concept file's parent directory, the file's date and its text, all with the existing git allowlist (D3).
- The member list passage, generated from the program record (D4).
- Where program passages go in the set, and the size rule: never trimmed, counted with rules and plan (D5).
- The visibility rule, enforced by what the code reads and proven by a test (D6).
- The answering stage gets the tick's program, and the launch adds the program passages only for a member (D7).
- Both answering steps' instructions name the two new kinds (D8).
- Docs: the visibility rule and the program passages in `docs/process-contract.md`; `CHANGELOG.md`.

**Excluded**

- The request outcome, its check and anything that writes to the program store (185).
- Edges, requests and their state as passages. The architecture lets the answerer see "the state of the edges and requests B is party to"; there are none until 183 and 184. **185 owns it**: its check is the first reader, and it extends D6's visibility rule with that state when it lands, so the architecture's sentence is carried, not dropped.
- Recording which member and commit a concept passage was read from on the question record. No slice reads it yet (GitHub issue #27).
- A per-member description field in the program record (D4).
- Any new git verb, any `cf` call besides the existing target read, and any store migration.

## Dependencies

### Prerequisites

- **181 (program record).** Designed, not implemented. 182 starts after 181 merges. Checked 20261103 against 181's design: `ProgramStore.members(program_id)`, the program stage's `Program | None` on the tick (D7), `RunnerHost.program_store`, `read_member(store_dir, member)` (D6), and `resolve_checkout` in `amoeba.upstream.context_forge` (D6). If 181's code departs from its design, 182's tasks follow the code.
- **143 and 144 (complete).** `assemble_sources`, `source_reads`, `passages`, `launch.prepare_launch` and `passage_refs`, `SOURCES_REASONS`.
- No external change. No new `sq`, `cf` or `git` command.

### Interfaces Required

From 181, beyond what its design already lists for 182:

- `Readable` (the readable result of `read_member`) carries the member's resolved `Checkout` and the CF project id of its one link. 181's `read_member` already computes both on the way to `readable` (`unlinked` needs the link; `checkout_unresolved` needs `resolve_checkout`), so this only keeps them on the result. 181's design is amended to say so; its Integration Points line for 182 carries both fields and `updated_at` (checked 20261104).
- `Program` and `Member` carry `updated_at`, the columns 181's schema already has. The member-list passage is dated by them (D4).

From 143 and 144, used unchanged except where a decision here says otherwise:

- `read_target`, `git_read`, `show_object_args`, `last_change_args`, `resolve_commit_args`, `parse_tree_listing`.
- `source_reads._Git`, `_Listings` and `_read_file`, made public (`GitReads`, `Listings`, `read_file`) so the concept read uses the same failure rules instead of copying them.
- `assemble`, `render_passages`, `cut_passages`, `SourceFile`, `Passage`, `SourcesProblem`, `unreadable`.

## Architecture

### Component Structure

| Component | Location | Role |
| --- | --- | --- |
| Program passages, pure | `runner/answering/program_passages.py` (new) | `member_list_text(program, members, asking_project)`; the `ProgramSources` value. Added to the purity check |
| Concept read | `runner/answering/program_sources.py` (new) | `read_program_sources(...)`: member state, target, commit, listing, date, text. Every program-side read is here |
| Source reads | `runner/answering/source_reads.py` | `GitReads`, `Listings` and `read_file` made public; no behavior change |
| Passages | `runner/answering/passages.py` | `PassageKind` gains `program_concept` and `program_members`; `SourceFile` and `Passage` gain `member`; rendering writes the `member:` line; `assemble` takes the program sources after the plan |
| Entry point | `runner/answering/sources.py` | `assemble_sources` takes an optional `ProgramContext` and calls `read_program_sources` after the project's own reads |
| Launch | `runner/answering/launch.py`, `stage.py` | `LaunchContext` gains `program: ProgramContext | None`; `passage_refs` unchanged |
| Pipeline | `runner/answering/answering.yaml` | Both steps' instructions name the new kinds (D8) |

`passages.py` is at 360 lines. The member-list text and the `ProgramSources` value go in the new pure module so `passages.py` grows only by the `member` field and one render line.

### Data Flow

```
ProjectTick.run
  program stage (181)                       -> program: Program | None   (held on the tick)
  answering stage
    launch one pending question
      program is None -> ProgramContext None -> exactly 144's path
      else ProgramContext(program, members = program_store.members(program_id),
                          store_dir, asking_project)
      assemble_sources(..., program_context)
        project's own reads (143, unchanged)   -> CommittedSources(commit C, files)
        read_program_sources(program_context, max_chars - text already read, budget, ...)
          concept = member named by program.concept_member
          read_member(store_dir, concept)      -> Readable(checkout, cf_project_id) | Unreadable
                                                   Unreadable -> sources_unreadable "concept member <id> <reason>: <detail>"
          read_target(checkout, cf_project_id) -> target K       (one cf call, existing)
          git log -1 --format=%H K             -> commit Q        (every later read names Q)
          git show Q:<parent of concept_path>  -> listing; file absent -> sources_missing
          git log -1 --format=%cI Q -- <path>  -> date
          git show Q:<path>                    -> text; over the remaining size -> sources_too_large
          member_list_text(program, members, asking_project) -> one generated file, dated max(updated_at)
        -> ProgramSources(concept SourceFile(member, Q), member list SourceFile)
        assemble(rules, plan, program sources, PM answers, ...)
  -> PassageSet | SourcesProblem | None
```

A budget refusal anywhere returns `None`, as in 143: the question stays `pending` and the next tick starts again.

### State Management

None new. Assembly reads the program store (one `members` read per launch, for members only), the concept member's store read-only, and git, and returns a value. Nothing is cached. Program passages are recorded in the existing `passage_index` like any passage: id, source and date (D4).

## Technical Decisions

### D1 — Program passages are added only for a member, from the tick's program
Status: decided

- The program stage (181, D7) already reads the program store once per tick and holds `Program | None`. The answering stage runs later in the same tick and takes that value; it never looks the program up again.
- `None` means the launch builds exactly 144's passage set: no program store read, no other store opened, no extra git call. A regression test compares the rendered `passages.md`, the git and `cf` call list and the stored `passage_index` for a question in a project in no program, with and without an unrelated program registered.
- For a member, the launch reads `program_store.members(program_id)` once. A `StoreError` from the program store propagates and the process exits as a store failure, 181's rule for every program store read. It is in `STORE_FAILURES`, so the tenant's existing catch handles it.

### D2 — The concept is its own passage kind, labelled with its member
Status: decided

- `program_concept` is a new kind word, not `plan` or `rule`. The answer step has to know the passage describes the program, not the asking project, and which repo it came from, and 185's check must tell "this belongs to another member's part" from the asking project's own plan.
- A `program_concept` section renders `kind`, `member` (the concept member's project id), `source` (the repo-relative path in that member) and `date`. `member:` is a new line in 140's format, written only for this kind.
- The file is cut at headings by `cut_passages`, unchanged, so each section of the concept is citable on its own.

### D3 — The concept is read from the concept member's checkout, at its target, at one commit
Status: decided

- **Which checkout.** The one 181's `read_member` resolves for the concept member, the checkout that owns its requests initiative index (181, D6). For a member with no worktrees that is the project path. Using `read_member` gives 182 the same readability reasons the program blocked list shows, from one function, and opens the member's store read-only, as 181's locality rule allows.
- **Which target.** `read_target` in that checkout, with the member's CF project id: the same `git.integration_branch` lookup the dispatch and 143 use. The target is a property of the checkout's configuration, so a member whose worktrees have different targets is read on the target of the checkout named above.
- **Which commit.** `git log -1 --format=%H <target>` once; every later read names that commit (`Q`). An uncommitted or untracked edit to the concept is invisible.
- **Absence from listings, never from exit codes** (143, D2). The concept file's parent directory is listed at `Q`. The file missing from that listing is `sources_missing` naming the member and path. The parent directory must exist; a failure to list it, or any other non-zero exit, is `sources_unreadable` with the command and git's stderr head. A non-UTF-8 concept file is `sources_unreadable` naming it.
- **Dated by its last commit.** `git log -1 --format=%cI Q -- <path>`, converted to UTC by the existing formatter. 143's D5 limit applies unchanged: a concept edited on a branch keeps its branch commit date.
- **Calls.** One `cf` call and four git calls per member question: target, commit, listing, date, text. A test counts them.
- **The asker is the concept member.** The concept is read from the asker's own checkout at the commit `C` its own reads already pinned, so one question renders one commit of that repo. `read_member` is not called and no second `cf` target read is made. If the concept path is already among the files the asker's own reads selected, that file appears once, as `program_concept` at the concept position, with no further call. Otherwise it is listed, dated and read at `C` (three git calls). A test covers both cases.
- **Concept member unreadable** is `sources_unreadable` with detail `concept member <id> <reason>: <detail>`, where reason is 181's `MemberUnreadableReason` (`store_missing`, `store_unreadable`, `unlinked`, `snapshot_missing`, `checkout_unresolved`). That covers "missing snapshot or checkout" from the slice plan with the existing reason. A member store failure never exits the process: `read_member` already returns it as a reason.
- **Timeouts and other failures** follow 143's rules (143, D2 and D9), with every detail prefixed `concept member <id>: `. A git timeout or failure (`GitReadFailure`) and a failing `cf` target read (`ReadFailure` from `read_target`) are `sources_unreadable`. A budget refusal is `None`. A member store that stays busy is bounded by the store busy timeout, after which `read_member` returns `store_unreadable` (181, D6); there is no other wait.
- **Rejected:** reading the concept through the asking project's checkout. The concept lives in another repo, and only that member's checkout has its objects.

### D4 — The member list is one generated passage; each member's part comes from the concept
Status: decided

- The member list is built from the program record by `member_list_text`, a pure function. It is one passage with no headings, so it is never cut:

  ```
  Program: trading
  Projects in this program:
  - trading-data (holds the program concept)
  - trading-engine (this question comes from this project)
  - trading-ui
  ```

  Members in project-id order. The two markers are fixed text defined once beside the function. When the asker is the concept member, both markers go on its one line, joined by `; `: `- trading-data (holds the program concept; this question comes from this project)`.
- It renders `kind: program_members` and `date`, with no `source` or `member` line. Its passage's `source` field holds the program id, not rendered, so `passage_refs` records it in `passage_index` unchanged. Its date is the latest `updated_at` of the program and its members, so a membership change is dated when it was registered.
- **Each member's part of the program is the concept's text.** The program record holds ids, indexes and modes, not descriptions, and the concept document is where the program says what each project is for. The answerer reads both: the list says which projects exist and which one is asking, the concept says what each does.

### D5 — Program passages follow the plan, and are never trimmed
Status: decided

- **Order in the set:** rules, plan, the concept's passages, the member list, then PM answers. Ids `P1` to `Pn` in that order. The project's own sources come first so that a short set reads as the project first, the program second, precedent last.
- **Never trimmed.** The concept and member list count with rules and plan. If the rendered rules, plan and program passages together exceed `passages_max_chars`, the result is `sources_too_large`, exactly as for rules and plan alone (143, D7). PM answers are then fitted into what is left, unchanged.
- **Early stop.** `read_program_sources` is given the characters still allowed after the project's own text, and returns `sources_too_large` once the concept text exceeds it, without reading further.
- **Precedence is unchanged.** Every passage is dated; the later date wins, ties have equal precedence. A concept committed after a project rule that it contradicts wins, as a later rule would. That is the existing rule and is not special-cased.

### D6 — The visibility rule is what the code reads, and a test proves it
Status: decided

- Rule (to `docs/process-contract.md`, "The answering stage"): for a question in a program member, the passages are the asking project's rules, plan and PM answers, the program concept file and the member list. Nothing else from any other member is read: no rules entry, no plan row, no PM answer and no question record. 185 extends this rule with the edge and request state the asking project is party to.
- It holds by construction. `pm_precedent` reads the asking project's store only (unchanged). `read_program_sources` reads exactly one path from one other repo, the one the program record names, and from the concept member's store only its link and snapshot (inside `read_member`). It never calls `locate_sources` or `pm_precedent` for another project.
- **The test.** A program of two members where the concept member's repo has its own `CLAUDE.md`, rules glob matches and plan files, and its store holds PM-answered questions. A question in the other member renders a set whose sources are the asker's files, the concept path with `member:` set, and the member list, and whose PM passages are all from the asker's store. The test asserts every passage's `(kind, member, source)` against an explicit allowed set.
- The concept path itself is the PM's choice at registration. Pointing it at another member's rules file would show that file as the concept; that is a registration error, not something the reader second-guesses.

### D7 — The launch passes a program context, built once per launch
Status: decided

- `ProgramContext(program: Program, members: tuple[Member, ...], store_dir: Path, asking_project: str)` is a frozen value in `program_passages.py`. `AnsweringStage` receives the tick's `program` and the host's `program_store`; `LaunchContext` gains `program: ProgramContext | None`, built per launch only when `program` is not `None`.
- `assemble_sources` gains a keyword `program: ProgramContext | None` (no default; every caller says which). With `None` its body is 144's.
- A program problem is a `SourcesProblem` like any other, mapped by the existing `SOURCES_REASONS`, so no `DeclineReason` is added and `decide.py` does not change.

### D8 — Both answering steps are told what the new kinds mean
Status: decided

- `answering.yaml`'s answer and check instructions currently list the kinds as "rule, plan or pm_answer". Both gain the same three sentences:
  - The kinds are rule, plan, pm_answer, program_concept or program_members.
  - A program_concept passage comes from the concept document of the program this project belongs to, held in the member project its `member` line names; it describes how the program's projects fit together and what each one is for.
  - A program_members passage lists the program's projects and marks the one the question comes from.
- No other instruction changes. Citation, precedence, ties, the reserved-action refusal and PM-precedent matching apply to program passages as written. Deciding that a need belongs to another member is 185's change to these instructions.
- The pipeline file's existing tests that pin instruction text are updated with it. `question.md` does not change: the member list says which project is asking.

### Technology Choices

No new library. The existing git reads, `read_target` and the program store.

### Patterns and Conventions

- The new kind words are `PassageKind` members, defined once; rendering uses the enum.
- Every program-side read is in `program_sources.py`, as every project-side git read is in `source_reads.py`. Neither module spells the other's paths.
- Readers return a value, a `SourcesProblem` or `None`, and raise only for programming errors (a `ProgramContext` whose concept member is not in its members raises `ValueError`; 181's registration rule makes that impossible from stored data).

## Implementation Details

### API Contracts

```python
# runner/answering/passages.py
class PassageKind(StrEnum):
    RULE = "rule"; PLAN = "plan"; PM_ANSWER = "pm_answer"
    PROGRAM_CONCEPT = "program_concept"; PROGRAM_MEMBERS = "program_members"

# runner/answering/program_passages.py (pure)
@dataclass(frozen=True)
class ProgramContext:
    program: Program
    members: tuple[Member, ...]
    store_dir: Path
    asking_project: str

@dataclass(frozen=True)
class ProgramSources:
    concept: SourceFile          # kind program_concept, member set
    members: SourceFile          # kind program_members; path is the program id, not rendered

def member_list_text(program: Program, members: Sequence[Member], asking_project: str) -> str: ...

# runner/answering/program_sources.py
def read_program_sources(context: ProgramContext, max_chars: int, budget: TickBudget,
                         run: CfRun, timeout_seconds: float
                         ) -> ProgramSources | SourcesProblem | None: ...

# runner/answering/sources.py
def assemble_sources(store, project_id, record, snapshot, cf_project_id, settings,
                     budget, run, timeout_seconds, *, program: ProgramContext | None
                     ) -> PassageSet | SourcesProblem | None: ...
```

`SourceFile` and `Passage` gain `member: str | None`.

**`passages.md`** (140's D3 format, extended):

```markdown
## Passage P12

kind: program_concept
member: trading-data
source: docs/program-concept.md
date: 2026-11-02T14:03:11Z

## Contracts between projects
...

## Passage P15

kind: program_members
date: 2026-11-03T09:12:40Z

Program: trading
Projects in this program:
...
```

## Integration Points

### Provides to Other Slices

- **185 (request outcome):** program passages in every member question, with kinds that tell the program's concept and member list from the project's own sources, and the asking project marked. 185 extends the instructions from D8 and reads `ProgramContext` to name a provider. 185 also owns the edge and request state as passages, and extends D6's visibility rule with it.
- **186 (live walkthrough):** a member question answered from the concept is one of its observable steps.
- **183, 184:** nothing directly.

### Consumes from Other Slices

- **181:** the tick's `Program`, `members`, `read_member` with `Readable` carrying the checkout and CF project id, `updated_at` on `Program` and `Member`. A member that cannot be read is a decline reason, never an exit; a program store failure exits, per 181.
- **143 / 144:** source assembly, the git reads and their failure rules, the decline mapping, the answering launch and `passage_index`. Changed only as D2, D4, D5 and D7 say.
- **140:** the `passages.md` format, extended by one line and two kind words; the pipeline instructions (D8).

## Success Criteria

### Functional Requirements

- A question in a program member renders the concept's passages with `kind: program_concept`, the concept member and path, dated by the concept file's last commit on the concept member's target, followed by one `program_members` passage marking the asking project. An uncommitted edit and an untracked file in the concept member's checkout do not appear.
- A question in a project in no program, with or without a program store and an unrelated program, renders the same `passages.md`, makes the same git and `cf` calls and stores the same `passage_index` as after 144.
- A concept file missing at the target commit declines with `sources_missing`; a concept member that is unlinked, has no store, no observed snapshot or no resolvable checkout declines with `sources_unreadable` naming the member and 181's reason; a failing git read declines with `sources_unreadable`. None is omitted silently.
- No passage from another member's rules, plan or PM answers appears in a member's set (D6's test).
- With rules, plan and program passages over `passages_max_chars`, assembly fails with `sources_too_large`; PM answers are trimmed as before and program passages never are.

### Technical Requirements

- `program_passages.py` passes the purity check.
- A test counts the program side's calls (one `cf`, four git) and returns `None` when any one of them is refused by the budget.
- The concept fixture is a real-format markdown concept with front matter and level-2 sections, read from a temporary repository built by the existing `tests/runner/git_repo.py` helper with controlled commit dates. Concept-member store fixtures are written by the tests.
- Format, lint and typecheck (`ruff`, `pyright` strict) pass, with the runner, store and process suites.
- Docs: `docs/process-contract.md` (the visibility rule, program passages, the call count), `CHANGELOG.md`.

### Integration Requirements

- 185 can design its request outcome against the program passages and `ProgramContext` without reading 182's code.
- 140's live answering fixtures still pass against the updated instructions.

### Verification Walkthrough

Draft; refined after implementation. Nothing here needs a live model: assembly is deterministic, and the answering run itself is unchanged apart from its instructions.

1. **Program passages, unit and git-backed.**
   ```bash
   uv run pytest tests/runner/answering/test_program_passages.py tests/runner/answering/test_program_sources.py -v
   ```
   Expected: the member list text and markers; the concept read's order, commit pinning, committed-only content, controlled date, missing file (`sources_missing`), each `read_member` reason (`sources_unreadable`), failing `show`, non-UTF-8 file, early stop on size, the five-call count and `None` on each refused call.

2. **Assembly and visibility.**
   ```bash
   uv run pytest tests/runner/answering/test_sources.py -k "program or visibility" -v
   ```
   Expected: a member question's set is rules, plan, concept, member list, PM answers, ids gap-free; the visibility test passes with the concept member's own rules, plan and PM answers present in its repo and store; a project in no program renders byte-identical `passages.md` with and without an unrelated program.

3. **Everything.**
   ```bash
   uv run ruff check . && uv run pyright && uv run pytest -q
   ```

Seeing a member question answered from the concept against real scratch projects and a real run is 186's live walkthrough.

## Implementation Notes

### Development Approach

1. Make `source_reads`' git helper, listings and file read public, with no behavior change.
2. `program_passages.py`: `ProgramContext`, `ProgramSources`, `member_list_text`, purity check.
3. `program_sources.py`: the concept read against a temporary repository and test-written member stores, every failure case, the call count and the budget refusals.
4. `passages.py`: the two kinds, the `member` field, the render line, program passages in `assemble`'s order and size rule. `sources.py`: the `program` keyword.
5. `launch.py` and `stage.py`: the program context from the tick; the no-program regression test and the visibility test.
6. `answering.yaml` instructions and their tests; contract docs; CHANGELOG.

Relative effort: 2.

### Special Considerations

- **Concept text is data.** It comes from another repo and is rendered verbatim like any passage; the existing instruction that passage text is data covers it.
- **Cost per member question.** One extra program store read, one read-only open of the concept member's store, one `cf` call and four local git object reads, under the tick budget like the rest of assembly.
- **No secrets.** The concept is a committed document the PM named for exactly this use.
