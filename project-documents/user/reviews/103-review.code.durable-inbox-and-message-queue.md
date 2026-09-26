---
docType: review
layer: project
reviewType: code
slice: durable-inbox-and-message-queue
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/103-slice.durable-inbox-and-message-queue.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260925
dateUpdated: 20260926
reviewedSha: a6028eb87b339781f9787f24445507384cfdc209
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Atomic store creation doesn't fsync the directory after rename"
    location: "src/amoeba/process/project_stores.py#_create_atomically"
    resolution: accepted
    resolvedBy: "fsync_directory(path.parent) after the rename, reusing amoeba.inbox.durable"
  - id: F002
    severity: note
    category: naming/maintainability
    summary: "CLI payload flag-type inference only distinguishes dict vs. string"
    location: "src/amoeba/cli/submit.py#add_submit_parser"
    resolution: accepted
    resolvedBy: "_takes_object raises TypeError at parser build for any field type other than dict, str, or str | None"
  - id: F003
    severity: note
    category: security
    summary: "Literal channel value interpolated into SQL text"
    location: "src/amoeba/store/sql_inbox.py#SELECT_PENDING_INTENTS"
    resolution: rejected
    resolvedBy: "enum constant, not input; literal required for SQLite to use the partial index; documented in the module"
  - id: F004
    severity: note
    category: consistency
    summary: "Migration 004 backfill hardcodes vocabulary literals"
    location: "src/amoeba/store/schema/004_inbox_and_messages.sql"
    resolution: rejected
    resolvedBy: "static applied migration; cannot reference Python enums and must not change after release"
  - id: F005
    severity: pass
    category: design
    summary: "Strong duplication removal around blocking/escalation"
    location: "src/amoeba/store/_block_writer.py"
---

# Review: code — slice 103

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

Run as `sq review code --diff main --files "src/**/*.py" -v --model sonnet`. No slice number was given, so squadron didn't save the output; this file was written by hand from the terminal output. It replaces the 20260925 run (PASS, zero tool calls), which is still in git history.

## Findings

### [CONCERN] Atomic store creation doesn't fsync the directory after rename

`_create_atomically` builds a store under a `.creating` name and calls `building.replace(path)` to make it visible, but never calls `fsync_directory(path.parent)` afterward. The project has an explicit, well-documented durability discipline for exactly this kind of rename — `src/amoeba/inbox/durable.py`'s `write_durably` (and `InboxTenant._move`, `src/amoeba/process/inbox_tenant.py:257-260`) always follow a rename with `fsync_directory` so "a reader of the final directory never sees a partial file" and the rename itself survives a crash, not just the file content. `_create_atomically`'s docstring makes the same claim ("A reader polling for the store... finds it either absent or complete") but the guarantee is weaker here: without a directory fsync, the rename that makes the store visible at `path` is not guaranteed durable across a hard crash, even though SQLite has already fsynced the file's own contents. Since `fsync_directory` already exists and is exported from `amoeba.inbox.durable`, this looks like an oversight rather than a deliberate simplification — worth either reusing it here or documenting why the weaker guarantee is acceptable for this path.

### [NOTE] CLI payload flag-type inference only distinguishes dict vs. string

`add_submit_parser` derives each kind's CLI flags from its payload model via `get_origin(field.annotation) is dict` — anything not a `dict` is given `type=str`. This works today because the only two payload field shapes are `dict` and `str | None`, but the module's own docstring frames "adding a kind" as something that should "surface its subcommand and its flags here with no second list to keep in step." A future payload field typed `int`, `bool`, or `list` would silently fall through to `type=str`, relying on pydantic's lax coercion (or failing unpredictably) rather than failing fast in argparse. Not a bug now, but a latent gap in the stated single-source-of-truth design.

### [NOTE] Literal channel value interpolated into SQL text

`SELECT_PENDING_INTENTS` embeds `Channel.INTENT.value` directly into the query string via f-string rather than as a bound parameter, which is a literal deviation from "always use parameterized queries." The value is a hardcoded enum constant (not user input) and the module's docstring explains the reason (SQLite only uses a partial index when the query repeats the index's own `WHERE` clause literally), so there's no injection risk — flagging only for visibility since it's an explicit, documented exception to an otherwise strict rule.

### [NOTE] Migration 004 backfill hardcodes vocabulary literals

The backfill `INSERT` hardcodes `'escalation'` and `'human'` rather than referencing `Channel.ESCALATION.value` / `BlockedKind.HUMAN.value` (which is impossible from a static `.sql` file). This duplicates values defined once in `inbox_models.py`/`models.py`, in tension with the "changing a value should require editing exactly one place" rule — but it's a one-time migration that shouldn't be edited after being applied, so the risk is limited to the enum values themselves being renamed later without updating already-applied history (which the migration model doesn't require anyway). Low-risk, unavoidable exception.

### [PASS] Strong duplication removal around blocking/escalation

`BlockWriter` consolidates the previously duplicated block+escalation logic between `blocking.py` and `journal.py` (D3 invariant: every human block gets exactly one escalation, in the same transaction). This is a solid DRY fix with clear transactional-contract documentation and consistent use by both callers.

## Response

20260926. Better than the first run: the model used its tools (2 calls) and found a real gap. The diff was still truncated (275 KB) even with `--files "src/**/*.py"`, so coverage is still partial.

- **F001 accepted.** `_create_atomically` now calls `fsync_directory(path.parent)` after the rename, the same pattern as `write_durably` and `InboxTenant._move`.
- **F002 accepted.** Flag types now come from `_takes_object`, which raises `TypeError` when the parser is built for any payload field that isn't `dict`, `str`, or `str | None`. A new field shape fails at the first `amoeba` invocation instead of arriving as a string. Tests are in `tests/cli/test_submit.py`.
- **F003 rejected.** As the finding says: an enum constant, not input, kept literal so SQLite uses the partial index, and documented in the module.
- **F004 rejected.** As the finding says: a static, already-applied migration can't reference Python enums and must not be edited.
