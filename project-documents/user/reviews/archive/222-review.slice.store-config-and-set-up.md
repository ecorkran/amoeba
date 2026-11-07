---
docType: review
layer: project
reviewType: slice
slice: store-config-and-set-up
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/222-slice.store-config-and-set-up.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: acfa2b4645c4d956e7660b101548f61ffd40ea2c
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
effort: high
turns: 6
promptTokens: 428686
cachedTokens: 310435
cacheWriteTokens: 118241
completionTokens: 7435
durationSeconds: 63.3
costUsd: 0.57922
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: scope-deferral
    summary: "Per-member authorize list is narrow-only, narrower than the architecture and plan wording"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:279"
  - id: F002
    severity: concern
    category: integration-contract
    summary: "Baseline tables are created partially, and the stated later-migration path cannot be done with SQLite `ALTER`"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:183"
  - id: F003
    severity: note
    category: verification
    summary: "Subdirectory resolution is asserted but not fixture-backed"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:221"
  - id: F004
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency directions match the architecture and slice 221"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#Component Structure"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#D2"
  - id: F006
    severity: pass
    category: proportionality
    summary: "Scope is proportionate to the plan entry"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#Technical Scope"
---

# Review: slice — slice 222

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Per-member authorize list is narrow-only, narrower than the architecture and plan wording

D8 says "A member can narrow the list but not extend it. Member-specific additions are deferred to issue #33." The architecture says a member "can change the list" and that per-member settings include "any change to what its answers may authorize". The slice plan entry for 222 repeats "any change to the authorize list". The PM's stated use case, allowing "yes, merge it" in one repo, is covered. Adding a repo-specific item that the default list lacks is not.

Dropping part of an assigned scope is a CONCERN even when it is documented. Either:
- record the narrowing-only reading in the slice plan and architecture so downstream slices (223's criterion, 226's request schema) rely on one definition, or
- design the extension here.

Extension is cheap: a second `authorize_deny` list of items with `key`, `description` and `screen_phrases`, stored on the member.

### [CONCERN] Baseline tables are created partially, and the stated later-migration path cannot be done with SQLite `ALTER`

D3 creates `questions`, `answers`, `releases` and `pm_marker` with only their keys and architecture-fixed columns. It leaves "the vocabulary of `waiting_reason`" and other columns to 223, 224 and 227 as `002+` migrations, and forbids editing `001`. SQLite's `ALTER TABLE` can add a column, but it cannot add a `CHECK` to an existing column, change a column's constraints, or add a `NOT NULL` column without a default. A closed vocabulary on `waiting_reason`, or any required new column on `questions`, forces a table-rebuild migration on a table that may already hold PM data.

The slice plan assigns the whole baseline to 222, so the tables stay. The design should add the following:
- State in D4 and `docs/store-contract.md` that later migrations needing a constraint change use the SQLite rebuild procedure, inside the migration's `BEGIN IMMEDIATE` transaction.
- Alternatively, leave `waiting_reason` as unconstrained text in `001`, with the vocabulary enforced in code by 223.

Without one of these, 223's design has no workable way to complete the schema it is promised.

### [NOTE] Subdirectory resolution is asserted but not fixture-backed

D6 says a subdirectory of a checkout resolves like the checkout "because CF matches the project whose directory contains the working directory". The D11 fixtures cover a default worktree, a non-default worktree and the `PROJECT_NOT_FOUND` case. They do not cover a subdirectory, and no success criterion exercises it. This path matters because agents often run from subdirectories. Add one recorded `cf get --json` from a subdirectory to D11, or drop the claim.

### [PASS] Layering and dependency directions match the architecture and slice 221

- `store` imports only `answering.values`, as 221 line 147 directs.
- `config` builds `AnswererSettings`, as 221 line 236 expects.
- `upstream` stays free of the new packages.
- Only the CLI (and later MCP) reads the home, and operations take `Store` and `UserConfig` as arguments.
- `set_up` validates its own input, so 226 can wrap it with no logic of its own, which matches "one operation, two doors".

### [PASS] Failure modes are enumerated for each new I/O path

Each new I/O path has an explicit strategy:
- **Lock contention:** `BEGIN IMMEDIATE` plus the busy timeout, mapped to `StoreBusyError` that names the path.
- **Open failures:** `StorePermissionError`, `StoreCorruptError` and `StoreSchemaError`, with the last leaving a newer-stamped store untouched.
- **`cf` failure or hang:** goes through the bounded `run_cf`, and `cf` calls run before the transaction so no subprocess holds a write lock.
- **Request document:** an unreadable, non-UTF-8 or non-YAML file exits 2, and a wrong-shape document is rejected as `malformed`.
- **Config:** every problem is listed in one pass.
- **Contention tests:** an 8-process test and a forced-timeout test cover it.

The "restart-safe" principle is met because each `set_up` call is one atomic transaction.

### [PASS] Scope is proportionate to the plan entry

The tests, the two contract docs, the 8-process concurrency test and the AST test for the home variable each trace to a slice plan success criterion or to the project's contract-doc and parsing-fixture rules. No lock file, `config init` command, read-only open mode or removal path was added. The rejected alternatives are stated, and removal sits in Future Work, matching the plan's backlog item 3.

### Run Digest

- Response length: 5448 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 428686 / 310435 / 118241 / 7435 / not computed
- Duration: 63.3 s
- Cost: $0.58 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
