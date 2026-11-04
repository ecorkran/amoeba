---
docType: slice-design
slice: program-record
project: amoeba
parent: user/architecture/180-slices.program-coordination.md
dependencies:
- 101-slice.store-foundation-and-node-model
- 103-slice.durable-inbox-and-message-queue
- 122-slice.runner-tenant-and-control-surface
- 123-slice.lifecycle-model-and-reconciliation
- 128-slice.gates-git-and-human-steps
- 144-slice.answering-run
interfaces:
- 182-slice.program-concept-as-a-source
- 183-slice.edges-and-release
- 184-slice.request-runs
- 185-slice.request-outcome
dateCreated: 20261103
dateUpdated: 20261104
status: not_started
turns: 39
promptTokens: 3367393
cachedTokens: 3226076
cacheWriteTokens: 141249
completionTokens: 43975
durationSeconds: 482.6
costUsd: 2.65531
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.6553098
    completionTokens: 43975
---

# Slice Design: Program Record

## Overview

Programs come into existence. This slice adds a **program store**, one SQLite file in its own subdirectory of the supervisor directory, holding programs, their members, and how each member is consumed by the others. A **program inbox**, a second inbox root drained the same way the project inbox is, applies program and member registration. Each member's registration names the index of its requests initiative, and each program names the member and path of its concept document.

The Runner's tick gains a **program stage** after intents and resolutions and before the rest of the tick. In this slice it only finds the project's program and its member list. `amoeba inspect` names any member that cannot be read, and gains a program listing (members and their state) and a **program blocked list**: every member's blocked nodes plus every unreadable member, as one list.

Nothing runs differently after this slice. A project in no program, and a supervisor with no program store, tick exactly as after 140.

## Value

- **For the PM:** a program's projects, and everything blocked in them, read as one list. A member that is unlinked, has no store, no observed snapshot or no resolvable checkout shows on that list with the reason, instead of being silently skipped.
- **Architectural enablement:** every later 180 slice reads the program record. 182 reads the concept location, 183 adds edges to the program store and edge resolutions to the program inbox and hands the program stage's output to readiness, 184 reads the requests initiative index and each member's checkout, and 183 to 185 grow the blocked list. The store, the inbox root, the stage seam and the listing exist and are tested before any of them is used.

## Technical Scope

**Included**

- The program store: `ProgramStore`, its schema package and migrations, read-write and read-only opens, created atomically on the first program submission.
- 100's store locality rule changed for the program store, and the contract proof extended to check it.
- The program inbox: `programs/inbox/` with the same layout, durability and terminal places as `inbox/`; `submit_program()` and `amoeba submit register-program | register-member`; a `ProgramInboxTenant` built on a drain extracted from `InboxTenant`.
- Two bodies, `register_program` and `register_member`, with their shapes in `docs/inbox-contract.md`.
- Member readability: a closed vocabulary of reasons a member cannot be read, computed from store reads and one directory check.
- The program stage in the Runner's tick, its place in `docs/process-contract.md`.
- Listings `program`, `program-blocked` and `program-submissions`; the `inbox` listing gains a last column, `queue`, so program inbox files are visible.
- Two small moves that the above needs: `resolve_checkout` from `runner/dispatch/checkout.py` to `amoeba.upstream.context_forge`, and the repo-relative path rule from `runner/project_config.py` to `amoeba.store.paths`.

**Excluded**

- Edges, the edge resolution, requests and request runs (183, 184), concept passages (182).
- Removing a program, and removing a member that edges or requests reference (D10).
- Program submissions over the network, and a change feed for the program store (D10).
- Any change to project config (D4).

## Dependencies

### Prerequisites

- Initiatives 100, 120 and 140 complete (they are). No dependency on 180's pipeline: this slice is independent of it and may be built in parallel in a separate worktree.
- No external change. No new `sq`, `cf` or `git` command.

### Interfaces Required

- `Store.open_read_only` and its failure types (`docs/store-contract.md`, "Read-only access", "Failure modes").
- The inbox layout, durable write and sidecar modules (`amoeba.inbox.layout`, `amoeba.inbox.durable`, `amoeba.inbox.sidecars`) and `QuarantineReason`.
- The migration runner (`amoeba.store.migrations`) and the atomic store creation in `process/project_stores.py`.
- `Store.cf_links` and `Store.latest_cf_snapshots`, and `resolve_checkout` (slice 128).
- The blocked rows of one project (`inspection/core.py`, `_blocked_rows`).
- `STORE_FAILURES` and the Runner's one process-boundary catch (`runner/tenant.py`).

## Architecture

### Component Structure

```
supervisor dir/
  {project}.sqlite3            unchanged: one store per project
  inbox/                       unchanged: project submissions
  programs/                    new
    programs.sqlite3           the program store
    inbox/{tmp,new,quarantine,failed}/   program submissions
```

| Component | Location | Role |
| --- | --- | --- |
| `ProgramStore` | `store/program_store.py`, `store/program_schema/` | Programs, members, overrides, program submission records. Applies a program submission in one transaction. |
| Program store paths | `store/paths.py` | `program_dir(store_dir)`, `program_store_path(store_dir)`, defined once. |
| Program envelope | `inbox/program_envelope.py` | `ProgramSubmissionKind`, payload models, `parse_program_envelope`, `submit_program()`. |
| Inbox drain | `process/inbox_drain.py` (extracted) | The file lifecycle both inbox tenants share: drain order, quarantine, attempt counting, parking, durable moves. |
| `ProgramInboxTenant` | `process/program_inbox_tenant.py` | Drains `programs/inbox/new/` into the program store. |
| Program store holder | `process/project_stores.py` | The read-write open of the program store, beside the project stores' (the writer guard's one module). |
| Member reads | `program/members.py` (new package `amoeba.program`) | `read_member(...) -> MemberState`: readable, or unreadable with a reason. Used by inspection in 181, and by the program stage from 183 (GitHub issue #26). |
| Program stage | `runner/program/stage.py` | Finds the project's program each tick; returns it, or `None`. |
| Program listings | `inspection/program.py` | `program`, `program-blocked`, `program-submissions` rows. |

`amoeba.program` exists because both the Runner and inspection need member reads and inspection may not import `amoeba.runner` (import rule 10). It imports `amoeba.store` and `amoeba.upstream` only.

### Data Flow

**Registration.**

1. The PM runs `amoeba submit register-program …` (or `submit_program()` from Python). The payload is validated first; an invalid one is refused with `SUBMISSION_REFUSED` and nothing is written. A valid one is written durably to `programs/inbox/new/`.
2. `ProgramInboxTenant`, composed after `InboxTenant`, drains the file. An envelope or payload that fails validation is quarantined with its reason, as in the project inbox.
3. The tenant opens the program store, creating it atomically if absent, and calls `ProgramStore.apply_submission`. In one `BEGIN IMMEDIATE` transaction it checks the id (first wins), applies the semantic checks, writes the program, members and overrides, and records the submission `applied` or `rejected` with a reason.
4. The file is deleted after the commit. A store failure is counted beside the file and stops the process below `inbox_max_attempts`, exactly as for project submissions.

**The tick.**

1. Intents applied, resolutions answered (unchanged).
2. **Program stage.** With no program store, nothing happens. Otherwise one read of the program store finds the project's program; a project in none stops here. For a member project, the result is the `Program`, held on the tick. No member store is opened. In 181 nothing consumes it; 183 grows it into the view it hands to readiness.
3. The rest of the tick, unchanged.

**Inspection.** `amoeba inspect program-blocked` opens the program store read-only, and for each program and member calls `read_member`, then lists the member's blocked nodes (if its store opens) and a `member_unreadable` row (if it is unreadable). Inspection works with the process stopped.

### State Management

- The program store is written only by the resident process: by `ProgramInboxTenant` in 181, and later by the program stage (183, 184). Nothing outside the process opens it read-write.
- Member readability is never stored. It is a function of member stores, snapshots and directories at the time of reading, so it cannot go stale.
- The program store has its own schema version line, starting at 1, independent of the project store's (15 after 144).

## Technical Decisions

### D1 — One program store in its own subdirectory, with its own class and schema line
Status: decided

- One file, `programs/programs.sqlite3`, holds every program. A subdirectory means no project id can collide with it, and `discover_project_ids`, which globs `*.sqlite3` at the top level only, never mistakes it for a project. A file `programs.sqlite3` at the top level (a project named `programs`) is a different path from the directory `programs/`.
- `ProgramStore` is its own class, not more mixins on `Store`: it has none of `Store`'s tables, and a separate class makes "no project rows in the program store" structural rather than a convention.
- It reuses `Store`'s machinery rather than copying it. `migrations.py` is parameterized by migrations package and expected version (today both are module constants); `Store` passes `amoeba.store.schema` and 15, `ProgramStore` passes `amoeba.store.program_schema` and 1. The connection helpers (`_connect`, `_connect_read_only`, error mapping to `StoreCorruptError`, `StoreBusyError`, `StorePermissionError`, `StoreSchemaError`) are lifted to a shared module both classes call. `open_read_only` has the same guarantees: never migrates, never creates, cannot write.
- The store does not exist until the first program submission. `ProgramInboxTenant` creates it with the same build-under-`.creating`-then-rename path `ProjectStores` uses (`_create_atomically`, made to take the store class). The resident process opens it read-write at start if the file exists; a failure to open is `STARTUP_FAILED`, like a project store.
- Rejected: program tables inside every member's project store (breaks 100's locality rule and needs a cross-store consistency story for the same program); one store file per program (adds discovery and a per-program file name rule for no current need).

### D2 — The program inbox is a second root drained by shared code
Status: decided

- `programs/inbox/` has `tmp/`, `new/`, `quarantine/` and `failed/`, the same file names, the same durability and the same terminal places as `inbox/`. `amoeba.inbox.layout`'s functions already take a root; they are called with `program_dir(store_dir)`.
- The per-file lifecycle in `InboxTenant` (parse, quarantine, apply, attempt counting, parking, durable moves) is extracted to `process/inbox_drain.py`, parameterized by root, parse function and apply function. `InboxTenant` keeps project attribution (`no_store_for_project`, `create_project`) and its apply; `ProgramInboxTenant` supplies program parsing and the program store's apply. Neither duplicates the file lifecycle.
- `ProgramInboxTenant` is composed directly after `InboxTenant` and shares `inbox_batch_size` and `inbox_max_attempts`. No new setting.
- The program envelope has `envelope_version`, `id`, `kind`, `submitted_by`, `submitted_at` and `payload`, and **no project id**: a program submission is not attributed to a project. Quarantine reasons are the existing ones that apply: `unparseable_envelope`, `unknown_envelope_version`, `unknown_kind`, `invalid_payload`.
- Rejected: program kinds in the project inbox (every project submission is attributed to one project's store, and a program submission belongs to none); a separate drain implementation (duplicates the crash-safety argument the inbox contract already makes).

### D3 — `register_program` replaces, `register_member` upserts; one program per project
Status: decided

- `register_program` creates a program, or replaces an existing one whole: its concept location, member set and override set become exactly what the body lists, so a member left out (a mistyped `project_id`, for example) is removed. That is safe in 181 because nothing references a member yet; 183 and 184 add the rule for a member that edges or requests reference. `register_member` upserts one member into an existing program and removes nothing. A re-submission of an identical body is `applied`, as `create_project` is.
- A project is a member of at most one program (unique `project_id` across `program_members`). Both shapes the architecture names (the `trading-*` product and the tool chain) are disjoint, and one program per project keeps "which program is this project in" a single lookup for every later slice. A project in another program is rejected `member_of_other_program`.
- After the write, the concept member must be a member of the program; otherwise the whole submission is rejected `concept_member_not_member` and nothing is written. `register_member` removes nothing, so it cannot break this; `register_program` is checked against the set it writes.
- Shape problems are quarantined (`invalid_payload`) before anything is written, naming the field: a missing `requests_initiative`, `concept_member` or `concept_path` is the "named error" the slice plan requires. Semantic problems that need the stored state are rejections with a code (see API Contracts).
- Rejected: a single body (adding one member would mean restating the concept location); a separate `remove_member` kind (replacing the program says the same thing with one rule).

### D4 — The requests initiative index is part of the member's registration, not project config
Status: decided

- The architecture and slice plan first put the index in each member's project config (`projects.yaml`). This design puts it on the member's registration in the program store instead, and both parents are amended to match: the architecture's "Request slices live in one requests initiative" principle, the plan's 181 entry and its Interfaces line, and the plan's configuration note.
- Why: the program blocked list must name a member whose checkout is missing, and the checkout of a member is the one that owns its requests initiative index (D6). `amoeba inspect` does not load project config (it opens stores read-only and nothing else), so with the index in config, inspection could not compute the checkout reason the slice plan requires. The only alternatives were persisting a per-member status written by each member's tick (a new table, a write path and stale values while the process is stopped) or giving `inspect` a `--project-config` flag. Keeping the index in the program record means one source, read the same way by the stage and by inspection.
- It also fits what the index is: it only means something for a project in a program. A project in no program never has it, and project config stays about how a project's own pipeline runs.
- The index is required with no default, a strict integer in the working initiative range 100–799 (`file-naming-conventions.md`). Changing it is a `register_member` with the new value. Whether the index collides with an existing planned initiative is 184's check, where the plan is read.
- Nothing else moves: 184's slice-writing pipeline models and cost cap, and 185's request limit, still come from per-project configuration.

### D5 — Consumption modes: a member default with per-pair overrides
Status: decided

- `ConsumptionMode` is a closed vocabulary: `from_source`, `from_release` (the architecture's two modes). Each member declares `consumed`, the mode every other member consumes it by. `overrides` maps a dependent member's project id to a different mode for that one pair.
- `overrides` is required and may be `{}`, so an omitted key never silently means "no exceptions" (the same rule as `reserved_terms`). An override naming the member itself is quarantined; one naming a project that is not a member after the write is rejected `override_not_member`. Upserting a member replaces its whole override set.
- 181 stores the modes and overrides only. The effective-mode computation (override if present, else the provider's `consumed`) is added in 183 with its first caller (GitHub issue #25).

### D6 — Member readability is a closed vocabulary computed from store reads and one directory check
Status: decided

`read_member(store_dir, member) -> Readable | Unreadable(reason, detail)`, checked in this order, first failure wins:

| Reason | When |
| --- | --- |
| `store_missing` | No `{project_id}.sqlite3` in the supervisor directory. |
| `store_unreadable` | The read-only open or a read raised a `StoreError` (corrupt, wrong schema version, busy past the timeout). The detail is the error. |
| `unlinked` | The project has no CF link, or more than one (the detail says which; none is chosen). |
| `snapshot_missing` | The link has no `observed` snapshot. |
| `checkout_unresolved` | `resolve_checkout` at the member's requests initiative index returns `CheckoutUnresolved`. The detail is its reason. |

- The checkout checked is the one that owns the requests initiative index, because that is the checkout request runs use (184). For a project with no worktrees it is the project path. 183 resolves the checkout of a providing slice by that slice's own index; this check does not replace that.
- No subprocess is started: everything is a store read plus `Path.is_dir`. Each member's read-only open waits at most the store busy timeout, so one call over a program waits at most that timeout times the member count. In 181 only inspection calls it, so no tick waits on a member store; when 183 adds member state to the stage (GitHub issue #26), that bound applies to the tick. Whether the checkout is clean or on its target is a dispatch question for 184, not readability.
- A member store's failure is the member's problem, not the process's: `read_member` catches `StoreError` from the member's read-only handle and returns `store_unreadable`. Only the program store's own failures exit the process (D7). That `except` is a specific-exception handler with a comment, per the exception rule.
- `resolve_checkout`, `Checkout` and `CheckoutUnresolved` move from `runner/dispatch/checkout.py` to `amoeba.upstream.context_forge` (they interpret a CF snapshot and depend only on `amoeba.store` types and CF constants). Their two callers (`runner/dispatch`, `runner/answering/sources.py`) import the exported names. Behavior is unchanged; their tests move with them.

### D7 — The program stage: placed by the architecture, read-only in this slice
Status: decided

- Place: in `ProjectTick.run`, directly after `_answer_resolutions()` and before Observe. That satisfies the architecture's order (intents, resolutions, program stage, then readiness), and keeps a PM resolution acknowledged before any later program-stage rule (183's supersession) can read the block.
- Behavior in 181: `ProgramStage.run(project_id) -> Program | None`. `None` when there is no program store or the project is in no program; nothing else is read. The tick keeps the result as `program`; nothing consumes it until 183, which replaces it with a view carrying the members and each member's `MemberState` (GitHub issue #26). It writes nothing, issues nothing and does not change `tick.wrote`.
- Failures: a `StoreError` from the **program store** propagates; it is in `STORE_FAILURES` (the same exception types), so the tenant re-raises and the process exits as a store failure. Every project's tick reads the program store, so this stops projects in no program too: the architecture's "behaves exactly as after 140" holds only while the program store is healthy, and its explicit failure rule wins. Any other exception is a bug and reaches the tenant's existing catch as a project-scoped `unexpected_fault`.
- `RunnerHost` gains `program_store: ProgramStore | None`, read every tick, because the store can appear at runtime when the first program is registered.
- Cost: one program store read per tick, no member store opened, no subprocess.
- `tick.py` is at 311 lines; the stage call is two lines and the stage lives in its own module. If the addition pushes `tick.py` over its budget, extract `_launch_context` and the escalation-closing helper to a sibling module in the same task.

### D8 — Inspection: supervisor-level listings over all programs
Status: decided

- `program`: one row per member of every program: `program_id`, `project_id`, `requests_initiative`, `consumed`, `overrides` (`dependent=mode`, comma-separated, empty when none), `concept_path` (on the concept member's row only), `state` (`readable` or the reason), `detail`.
- `program-blocked`: the program blocked list. Columns are `program_id` followed by the `blocked` listing's columns. Each member's blocked rows come from `inspection/core.py`'s `_blocked_rows`, unchanged. An unreadable member adds one row with `blocked_on` = `member_unreadable`, `reason` = `"<reason>: <detail>"`, and the node columns empty. A member whose store opens is listed both ways when it is also unreadable (unlinked, for example).
- `program-submissions`: applied and rejected program submissions in `applied_seq` order: `id`, `kind`, `submitted_by`, `submitted_at`, `outcome`, `reason`.
- `inbox` gains a **last** column `queue` (`project` or `program`) and lists both roots. Existing columns keep their names and positions, so positional and by-name readers of project inbox rows are unaffected; JSON rows gain one key, and a supervisor with no program files lists exactly the rows it did before. The inbox listing tests that assert the full column tuple are updated. No other listing changes.
- The slice plan names one command, `amoeba inspect program`. The listing registry is one table per listing, so members and the blocked list are two listings. Supervisor-level listings receive no options (`supervisor_rows(store_dir)`), so there is no `--program` filter; every row carries `program_id`, and programs are few. A filter needs a program listing scope and is deferred until a supervisor holds enough programs to need it.
- With no program store, all three return no rows. A program store at the wrong schema version raises, as a project store does. The server serves the new listings at `/v1/listings/{name}` with no change, because it derives routes from the registry.

### D9 — The locality rule and its proof
Status: decided

- `docs/store-contract.md` "Store locality" says: one store per project at `{project_id}.sqlite3`, plus one program store at `programs/programs.sqlite3`. The program store may hold programs, members, consumption modes and program submission records (183 and 184 add edges and requests). It may not hold any project's nodes, blocks, questions, journal, messages, verdicts, checks, snapshots or feed. A project store holds no program table. The resident process is the only read-write opener of either kind; a project's tick may open other members' stores **read-only**, and never writes them.
- The contract proof's `locality_problems` (`tests/contract/oracle.py`) adds two checks: the program store's tables are exactly the allowed set, and no project store has a program table. The top-level `*.sqlite3` check is unchanged and still passes, because the program store is in a subdirectory.
- A negative test adds a `nodes` table (and separately a `blocked_states` and a `question_records` table) to a scratch program store and asserts the proof fails naming it.
- `docs/process-contract.md` "The supervisor directory" table gains `programs/`; "The writer model" says the program store has the same single writer; `tests/test_writer_guard.py` also flags `ProgramStore.open(`.

### D10 — What is deferred
Status: decided

- **Removing a program, and removing a member that edges or requests reference.** In 181 a wrong member is removed by re-submitting `register_program` without it (D3), and a project moves between programs by removing it from one and registering it in the other. Removing a whole program, and the rules for a referenced member once 183 and 184 exist, are the slice plan's Future Work item "Member and program removal".
- **Program submissions over the network.** `amoeba serve` submits project kinds only; program kinds go through the file inbox. Added when 160 needs it.
- **A change feed for the program store.** 160 is the first consumer that would follow it.

### Technology Choices

No new library. SQLite through the existing store machinery, pydantic for the envelope and payloads, the existing listing registry and CLI derivation.

### Patterns and Conventions

- Every vocabulary is a `StrEnum` defined once: `ProgramSubmissionKind`, `ConsumptionMode`, `ProgramRejection`, `MemberUnreadableReason`, and the `member_unreadable` blocked-list kind. SQL `CHECK` constraints list the same values; a test pins each enum to its constraint.
- Rejection reasons are `"<code>: <detail>"`, as intent acknowledgments are; branch on the code.
- Payload field names are constants beside `ProgramSubmissionKind`, pinned to the payload models by a test, as `inbox_models.py` does for project kinds.
- The repo-relative path rule (`_checked_rules_path` in `runner/project_config.py`) moves to `amoeba.store.paths.validate_repo_relative_path(entry, *, glob_allowed)`. `rules_paths` calls it with `glob_allowed=True`, `concept_path` with `False`. One rule, two callers.

## Implementation Details

### API Contracts

**Submitting.**

```python
from amoeba.inbox import submit_program
from amoeba.store import ProgramSubmissionKind

submission_id = submit_program(
    kind=ProgramSubmissionKind.REGISTER_PROGRAM,
    payload={...},
    submitted_by="operator",
    submission_id=None,   # first wins, as for project submissions
    store_dir=None,
)
```

```
amoeba submit register-program --by operator --program-id trading \
    --concept-member trading-data --concept-path docs/program-concept.md \
    --members '[{"project_id": "trading-data", "requests_initiative": 790,
                 "consumed": "from_source", "overrides": {}},
                {"project_id": "trading-engine", "requests_initiative": 790,
                 "consumed": "from_source", "overrides": {"trading-ui": "from_release"}}]'
amoeba submit register-member --by operator --program-id trading \
    --member '{"project_id": "trading-ui", "requests_initiative": 790,
               "consumed": "from_release", "overrides": {}}'
```

Subcommands and flags derive from `ProgramSubmissionKind` and the payload fields by the existing flag rule. Program kinds take no `--project`. Each prints the submission id; `--id` reuses one.

**Bodies** (in `docs/inbox-contract.md`, new section "Program submissions").

| Field | Rule |
| --- | --- |
| `program_id` | Non-blank; passes `validate_path_component`. |
| `concept_member` | A project id (passes `validate_project_id`). `register_program` only. |
| `concept_path` | Repo-relative file path in the concept member's repo: stripped, non-blank, not absolute, no `..` segment, no `*`, names a file. `register_program` only. |
| `members` | A non-empty list of member objects, no project id twice. `register_program` only. |
| `member` | One member object. `register_member` only. |
| member `project_id` | Passes `validate_project_id`. The project need not have a store yet; a member without one shows as `store_missing`. |
| member `requests_initiative` | Strict integer, 100–799. Required. |
| member `consumed` | `from_source` or `from_release`. |
| member `overrides` | Required mapping, may be `{}`: dependent project id → `from_source` or `from_release`. Must not name the member itself. |

Unknown keys are refused (unlike the project envelope's ignored extras, a misspelled key here would silently drop a setting).

**Rejections** (the submission is recorded `rejected`; nothing else is written):

| Code | When |
| --- | --- |
| `unknown_program` | `register_member` names a program that does not exist. |
| `member_of_other_program` | A listed project is already a member of a different program. |
| `concept_member_not_member` | After the write, the concept member would not be a member of the program. |
| `override_not_member` | An override names a project that would not be a member of the program after the write. |

**Reading the outcome:** `amoeba inspect program-submissions`, or `ProgramStore.submission(id)` from code.

**`ProgramStore` methods** (in `docs/store-contract.md`, new section "The program store"):

```python
ProgramStore.open(path) / ProgramStore.open_read_only(path)
apply_submission(*, submission_id, kind, submitted_by, submitted_at, payload) -> ProgramSubmissionRecord
programs() -> list[Program]                       # program_id, concept_member, concept_path
members(program_id) -> list[Member]               # project_id, requests_initiative, consumed, overrides
program_of(project_id) -> Program | None
submissions() -> list[ProgramSubmissionRecord]
```

### Database / Storage Schema

`store/program_schema/001_program_record.sql` (program schema version 1):

```sql
CREATE TABLE schema_meta (...);   -- same shape as the project store's
CREATE TABLE programs (
  program_id TEXT PRIMARY KEY, concept_member TEXT NOT NULL, concept_path TEXT NOT NULL,
  registered_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE program_members (
  program_id TEXT NOT NULL REFERENCES programs(program_id),
  project_id TEXT NOT NULL UNIQUE,                       -- D3: one program per project
  requests_initiative INTEGER NOT NULL CHECK (requests_initiative BETWEEN 100 AND 799),
  consumed TEXT NOT NULL CHECK (consumed IN ('from_source', 'from_release')),
  registered_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (program_id, project_id));
CREATE TABLE consumption_overrides (
  program_id TEXT NOT NULL, provider_id TEXT NOT NULL, dependent_id TEXT NOT NULL,
  consumed TEXT NOT NULL CHECK (consumed IN ('from_source', 'from_release')),
  PRIMARY KEY (program_id, provider_id, dependent_id),
  FOREIGN KEY (program_id, provider_id) REFERENCES program_members(program_id, project_id),
  CHECK (provider_id <> dependent_id));
CREATE TABLE program_submissions (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, submitted_by TEXT NOT NULL,
  submitted_at TEXT NOT NULL, applied_seq INTEGER NOT NULL UNIQUE, applied_at TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('applied', 'rejected')), reason TEXT,
  payload TEXT NOT NULL);
```

`concept_member` and override dependents are checked in code inside the apply transaction (a foreign key from `programs` to `program_members` would be circular on creation). The `UNIQUE` on `project_id` backs `member_of_other_program` structurally; the code checks first so the rejection names it.

## Integration Points

### Provides to Other Slices

- **182:** `ProgramStore.program_of(project_id)` and the concept location; `members(program_id)` for the member list in passages; `updated_at` on `Program` and `Member` (the schema's columns) to date the member list; `read_member`, whose `Readable` result keeps the resolved `Checkout` and the CF project id of the member's one link, so 182 reads the concept from the concept member's checkout (182, D3).
- **183:** the program store and its migration line (edges are migration 002); the program inbox and its drain (the edge resolution is a third `ProgramSubmissionKind`); the stored modes and overrides; the program stage, whose `Program` result 183 grows into the view it hands to readiness; `read_member` to add member state to it; the `program-blocked` listing to add edge rows to.
- **184:** each member's `requests_initiative`; the checkout readability check; the program store for request rows.
- **185:** `program_of` to know whether a project can request at all.

### Consumes from Other Slices

- 100: the store machinery, inbox layout and drain semantics, the read-only open, the locality proof.
- 120: the tick structure, the tenant's failure handling, `STORE_FAILURES`, `resolve_checkout` (128).
- 140: nothing. The blocked rows already include question state and decline reason, and the program blocked list reuses them unchanged.
- 180: nothing.

## Success Criteria

### Functional Requirements

- Registering a program with its members through the program inbox writes the program store, created on first use; `amoeba inspect program` lists each member with its requests initiative, mode, overrides and state.
- A payload missing `requests_initiative`, `concept_member` or `concept_path`, or with an out-of-range index, an unknown mode, a self override, a duplicate member or an unknown key, is refused by `amoeba submit` and quarantined when hand-written, with `invalid_payload` naming the field.
- Each rejection code in API Contracts is produced by a body that triggers it, recorded on `program-submissions`, and writes nothing else.
- `register_program` on an existing program leaves exactly the listed members and overrides (a member left out is gone); `register_member` upserts without removing anything; an identical re-submission is `applied`; a reused submission id is a no-op.
- A member that is unlinked (no link, or two), has no store, an unreadable store, no observed snapshot or an unresolvable checkout at its requests index shows on `program-blocked` with that reason; members' blocked nodes appear with `program_id`. Nothing exits.
- The program stage runs after resolutions and before Observe; a project in no program, and a supervisor with no program store, tick with the same writes, commands and journal as before (a regression test compares a tick with and without an unrelated program registered).
- A program store failure during the stage or the program inbox apply exits the process as a store failure; a corrupt program store at start is `STARTUP_FAILED`.

### Technical Requirements

- The locality proof passes with a program store present and fails when the program store holds a `nodes`, `blocked_states` or `question_records` table, or a project store holds a program table.
- `migrations.py` parameterization and the drain extraction leave every existing store, migration and inbox test passing unchanged.
- The writer guard covers `ProgramStore.open`; import rules hold (inspection does not import `amoeba.runner`; `amoeba.program` imports only `amoeba.store` and `amoeba.upstream`).
- Format, lint and typecheck pass; tests cover each new module, with fixtures written by the tests (no live CF or `sq`).
- `docs/store-contract.md` (program store, locality, migrations), `docs/inbox-contract.md` (program submissions, inspection), `docs/process-contract.md` (supervisor directory, tenants, the program stage in the Runner tick, the writer model, inspection) and `CHANGELOG.md` are updated.

### Integration Requirements

- 182 can read a member's concept location and the member list from the program store alone.
- 183 can add a migration to the program store, a kind to the program inbox and rows to `program-blocked` without changing anything this slice built.

### Verification Walkthrough

Run against a throwaway supervisor directory; the real one is never touched. `amoeba start` needs `sq` installed for its start-up probe.

1. **A throwaway supervisor with two projects.**
   ```bash
   export AMOEBA_STORE_DIR=$(mktemp -d)
   amoeba submit create-project --project data --by operator
   amoeba submit create-project --project engine --by operator
   amoeba start
   amoeba inspect projects          # data, engine
   amoeba inspect program           # no rows: no program store yet
   ls "$AMOEBA_STORE_DIR"           # data.sqlite3 engine.sqlite3 inbox/ ... no programs/
   ```
2. **Register a program.**
   ```bash
   amoeba submit register-program --by operator --program-id demo \
       --concept-member data --concept-path docs/program-concept.md \
       --members '[{"project_id":"data","requests_initiative":790,"consumed":"from_source","overrides":{}},
                   {"project_id":"engine","requests_initiative":790,"consumed":"from_source","overrides":{"data":"from_release"}}]'
   amoeba inspect program-submissions   # one row, outcome applied
   ls "$AMOEBA_STORE_DIR/programs"      # inbox/ programs.sqlite3
   amoeba inspect program               # two rows; state unlinked for both
   amoeba inspect program-blocked       # two member_unreadable rows: "unlinked: ..."
   ```
3. **Bad bodies.** Drop `requests_initiative` from a `register-member` call: `amoeba submit` exits 9 (`SUBMISSION_REFUSED`) naming the field. `register-member --program-id nope ...` is recorded `rejected`, `unknown_program: ...`, on `program-submissions`.
4. **A missing member store.** `amoeba stop`, delete `engine.sqlite3`, `amoeba start`: `program-blocked` shows `engine` as `store_missing`, and `data` keeps ticking.
5. **Process contract and proofs.** `amoeba stop`; `echo junk > "$AMOEBA_STORE_DIR/programs/programs.sqlite3"`; `amoeba start` exits `STARTUP_FAILED` naming the program store. Then `uv run pytest tests/contract tests/test_writer_guard.py tests/test_import_boundaries.py` passes, including the locality proof's negative cases.

The CF-dependent reasons (`snapshot_missing`, `checkout_unresolved`, readable) are covered by tests with fixtures written by the tests; seeing them against a real CF project is 186's walkthrough.

## Risk Assessment

### Technical Risks

- **Refactoring 100's foundations.** The migration runner, connection helpers and inbox drain are shared by every store and submission. A regression there breaks everything, not just programs.
- **Tick order.** A stage inserted before Observe that raises would stop every member's tick. In 181 it only reads, and its only intended exit is a program store failure.

### Mitigation Strategies

- Do the three extractions (migrations parameterization, connection helpers, inbox drain) first, as pure refactors committed on their own, with the existing suites unchanged and green before any program code is added.
- The tick regression test (a project in no program, with a program store present, produces identical writes and commands) guards the stage; the member-failure tests (each reason produced without an exception escaping `read_member`) guard the blocked list.

## Implementation Notes

### Development Approach

Suggested order:

1. Refactors with no behavior change: parameterize `migrations.py`; lift connection helpers; extract `inbox_drain.py` from `InboxTenant`; move `resolve_checkout` to `amoeba.upstream.context_forge`; move the repo-relative path rule to `amoeba.store.paths`. Existing tests pass unchanged.
2. `ProgramStore`: schema 001, vocabularies, opens, `apply_submission` with every rejection, reads. Store-level tests.
3. Program envelope, `submit_program`, CLI subcommands, `ProgramInboxTenant`, atomic creation, host wiring (start-up open, `program_store` on the host). Inbox-level tests, including quarantine, the attempt limit and first-wins.
4. `amoeba.program.members.read_member` with one test per reason (fixtures written by the tests), then the program stage and its place in the tick, with the no-program regression test and the program-store-failure exit test.
5. Listings and the `inbox` `queue` column; inspection tests.
6. Locality rule, proof and negative tests; writer guard; contract docs; CHANGELOG.

Relative effort: 4. The five refactors in step 1 are most of the difference from the plan's 3; the plan entry is updated to match.

### Special Considerations

- **The project inbox is unchanged for submitters.** No project kind, path or reason changes. The only visible change to an existing listing is the `queue` column on `inspect inbox`.
- **No secrets.** Program payloads hold ids, paths and modes, stored as written; the same rule as every payload.
- **The concept path is not checked against the repo here.** Whether the file exists at the concept member's target is 182's source read, which declines with 140's source reason if it does not.
