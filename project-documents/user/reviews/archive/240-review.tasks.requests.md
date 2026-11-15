---
docType: review
layer: project
reviewType: tasks
slice: requests
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/240-tasks.requests.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 5362b543917e4dcb1ccf184c667d1f6b132c3ef1
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
effort: xhigh
turns: 23
promptTokens: 1230812
cachedTokens: 1043583
cacheWriteTokens: 187211
completionTokens: 61302
durationSeconds: 272.8
costUsd: 0.37737
costBasis: provider
runId: run-20261115-tasks-plan-16a0f352
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: fail
    category: deferral
    summary: "Aged-note pruning is deferred to slice 243, contrary to the design and the parent architecture"
    location: "project-documents/user/tasks/240-tasks.requests.md:88"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Broken and forward task references"
    location: "project-documents/user/tasks/240-tasks.requests.md:136"
  - id: F003
    severity: concern
    category: sizing
    summary: "Task 11.1 is too large for one task"
    location: "project-documents/user/tasks/240-tasks.requests.md:229"
  - id: F004
    severity: concern
    category: coverage
    summary: "Reply and cancel tasks leave the suite red because INSTRUCTIONS isn't updated"
    location: "project-documents/user/tasks/240-tasks.requests.md:240"
  - id: F005
    severity: concern
    category: ci
    summary: "The load-test CI gate is implicit"
    location: ".github/workflows/ci.yml:39"
  - id: F006
    severity: concern
    category: coverage
    summary: "No task makes the Requesting and Handling blocks reach member repos"
    location: "project-documents/user/tasks/240-tasks.requests.md:305"
  - id: F007
    severity: concern
    category: scope
    summary: "The 242 timing constants are pulled into 240 without a recorded departure"
    location: "project-documents/user/tasks/240-tasks.requests.md:252"
  - id: F008
    severity: note
    category: error-handling
    summary: "Task 10.1 should require the swallow justification comment"
    location: "project-documents/user/tasks/240-tasks.requests.md:199"
  - id: F009
    severity: note
    category: coverage
    summary: "Design decisions D2 and D8 have no test step"
    location: "project-documents/user/tasks/240-tasks.requests.md:153"
  - id: F010
    severity: note
    category: commits
    summary: "A commit marker after 11.4 would be a working point"
    location: "project-documents/user/tasks/240-tasks.requests.md:264"
  - id: F011
    severity: pass
    category: coverage
    summary: "Success criteria are covered"
    location: "project-documents/user/tasks/240-tasks.requests.md"
  - id: F012
    severity: pass
    category: verification
    summary: "Prerequisites and named helpers exist, and the quoted sizes are correct"
    location: "project-documents/user/tasks/240-tasks.requests.md:51"
  - id: F013
    severity: pass
    category: sequencing
    summary: "Sequencing and test pairing are sound"
    location: "project-documents/user/tasks/240-tasks.requests.md"
---

# Review: tasks — slice 240

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Aged-note pruning is deferred to slice 243, contrary to the design and the parent architecture

Task 2.5 says "Notes are not pruned here: 243 adds the note statement and the aged-note due check." Task 13.3 (line 277) then amends slice D6 to drop the note statement. But D6 (`project-documents/user/slices/240-slice.requests.md:174`) and the architecture's Retention paragraph (`project-documents/user/architecture/240-arch.agent-messaging.md:103`) both put aged-note pruning in 240's sweep. Task 2.6 asserts that a directly inserted aged note is "left alone," so the `note` kind that 240's schema admits has no exit in this slice. The Amoeba design rules forbid this deferral, and a review that finds one rejects it. The task file also doesn't list this change among its departures: 13.3's amendments don't include it, so after the docs step the architecture would still say 240 prunes notes while the code would not.

Fix: keep the note statement and the aged-note due check in 2.5. Task 2.6 can insert a note row directly to test them. Drop the note amendment from 13.3. Slice 243's design (lines 201 and 203) describes the note statement as something it adds to 240's sweep, so its wording needs correcting to match.

### [CONCERN] Broken and forward task references

Task 5.1 says `resolve_recipient` "uses `member_reference` (3.4)," but section 3 ends at 3.3, the task that moves `_anchor` into `member_reference.py`. Task 11.1 (line 230) says `wiring_messages.py` holds "the bound constants of 11.6," which is a later task. Point 5.1 at 3.3. For the constants, either move them into 11.1 or reorder so 11.6 comes first.

### [CONCERN] Task 11.1 is too large for one task

Task 11.1 touches about ten source and doc files (`operations/names.py`, new `wiring_messages.py`, `wiring.py`, new `mcp/message_tools.py`, the `INSTRUCTIONS` text, new `cli/registration_messages.py`, `cli/parser.py`, `cli/commands.py`, new `cli/render/messages.py`, `docs/cli-contract.md`) and five test files. It is also the first door that exercises the full stack. Split it into 11.1a (shared wiring, the MCP row, its INSTRUCTIONS line, and their tests) and 11.1b (the CLI flags, renderer, and CLI tests). Each should leave the suite green.

### [CONCERN] Reply and cancel tasks leave the suite red because INSTRUCTIONS isn't updated

`tests/mcp_server/test_instructions.py:11` parametrizes over every row in `TOOLS` and asserts each tool name appears in `INSTRUCTIONS`. Task 11.1 updates INSTRUCTIONS for `send` only, and 11.2 does so for `inbox`. Tasks 11.3 (line 240) and 11.4 (line 244) add the `reply` and `cancel` rows but don't mention INSTRUCTIONS. "As 11.1" doesn't cover it, because 11.1's INSTRUCTIONS step names only `send`. Those tasks would fail the suite, which contradicts line 227's "the suite is green after every task." Add the INSTRUCTIONS step to 11.3 and 11.4.

### [CONCERN] The load-test CI gate is implicit

Task 9.3 (line 191) relies on CI's bare `uv run pytest` step to run `tests/load/test_messages_load.py`. `pyproject.toml` ignores only `tests/live`, so the file is collected. But no step names the load tier, and `python.md` requires CI to gate load tests for slices that touch concurrency. This slice adds a two-process accept and a many-process load test. The existing `tests/load` files are gated the same way, so this is current repo practice, but the task should add the named gate (a `tests/load` step in `ci.yml`, or a CI wiring task) rather than only confirm collection.

### [CONCERN] No task makes the Requesting and Handling blocks reach member repos

The slice design's Operator walkthrough, Start step, says to paste both blocks into each repo's rules file, "an agent in each repo does it as a commit" (`project-documents/user/slices/240-slice.requests.md:351`). Task 13.2 writes the blocks into `docs/program-rules.md` only. The Phase 7 hand-off (line 305) covers the backup, config, install, and migration, but not this step. Without it, member repos never get the Handling block and their agents never check `inbox`, so the design's normal path cannot run. Assign the step, its owner, and the commit it makes to a task or to the hand-off.

### [CONCERN] The 242 timing constants are pulled into 240 without a recorded departure

Task 11.6 defines `START_BOUND_SECONDS` and `MAX_STARTS_PER_CALL` in 240's `wiring_messages.py`, and 13.3 rewrites `user/slices/242-slice.hold-and-release.md` to import them. The design says the term is added "once 242 lands" (`project-documents/user/slices/240-slice.requests.md:291`), so moving it forward is a reasonable answer to the deferral rule. But it places a run-start bound in a slice that has no run start, edits another slice's design from this one, and leaves the change out of the design's Departures list. Record it as a departure, and route the 242 edit to 242's owner so the 240 timing test doesn't depend on an unreviewed change in 242.

### [NOTE] Task 10.1 should require the swallow justification comment

`sweep_messages` catches `StoreBusyError`, logs it, and returns it as problem text. That is an acceptable swallow under CLAUDE.md's rule (b), but the rule requires an inline comment explaining why. Add that requirement to 10.1.

### [NOTE] Design decisions D2 and D8 have no test step

Two decided behaviors are untested: a pruned id sent again is a new request (design D2), and cycles are allowed (design D8). Neither is a success criterion, so this is a note, not a gap.

### [NOTE] A commit marker after 11.4 would be a working point

The marker after 12.2 covers six door tasks and two end-to-end tasks in one commit. Each of 11.1–11.4 leaves the suite green, so a marker after 11.4 would be a valid working point. Optional.

### [PASS] Success criteria are covered

I mapped each functional, technical, and integration criterion in the design (lines 278–299) to a task. Scenario D is covered by 12.1, 12.2, and 14.1. Every state's exit by 12.2, 2.6, and 10.6. The two-process accept and each reject code by 7.2, 7.3, 6.3, 8.2, and 5.2. Two worktrees by 9.2. Chain depth and recorded rejections by 6.3 and 10.4. Over-limit text by 4.4 and 6.3. `list` and `status` by 10.3–10.5 and 11.5. TTL expiry by 9.2 and 2.6. Prune per table by 2.6. The timing test by 11.6 and 9.3. The held store by 10.2 and 10.4. The config keys by 3.1. Docs and parity by 13.1 and 11.x. The verification walkthrough by 14.1 and 15.2.

### [PASS] Prerequisites and named helpers exist, and the quoted sizes are correct

Schema 001–005 is present, and `ACTIVE_MEMBER`, `apply_removal`, `resolve_member`, `project_of`, `CF_GET_TIMEOUT_SECONDS`, `BUSY_TIMEOUT_SECONDS`, `MCP_CALL_DEADLINE_SECONDS`, and `QUOTED_DATA_NOTICE` all exist where the task says. Every test helper named in 0.1 exists. The importer list in 3.2 is complete. The line counts quoted in the task (`sql.py` 484, `wiring.py` 342, `mcp/tools.py` 292, `status.py` 243) match the code. `pyproject.toml` ignores only `tests/live`, as the task states.

### [PASS] Sequencing and test pairing are sound

Apart from the two references flagged above, dependencies run forward from schema to store, operations, doors, docs, and live tests. There are no cycles. Each implementation task is followed by its test step. The single task file is the right size for a 5/5 slice.

### Run Digest

- Response length: 10385 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 23
- Tokens — prompt / cached / cache write / completion / reasoning: 1230812 / 1043583 / 187211 / 61302 / not computed
- Duration: 272.8 s
- Cost: $0.38 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

## Resolution

Resolved by the planning agent, 2026-11-15. The task file governs.

- F001 rejected: no note can exist before 243, which adds the note writer together with its prune statement and due clause (243 D6). That is slice ownership, not deferral; the architecture's Retention paragraph assigns no slice. 240's D6 wording ("from 243") was ambiguous and now says this outright.
- F002 fixed: 5.1 points at 3.3; 11.1a names the constants it creates.
- F003 fixed: 11.1 split into 11.1a (wiring, MCP row, INSTRUCTIONS) and 11.1b (CLI).
- F004 fixed: 11.3 and 11.4 add their INSTRUCTIONS lines.
- F005 dropped: the bare pytest step already runs `tests/load` in CI, as for the existing load tests.
- F006 dropped: rolling blocks into member repos is set-up in those repos, as for 227's blocks; 13.2 already says how.
- F007 fixed the other way: the run-start term is 242's. 11.6 has no start term, the 242 amendment is removed, and 242 adds `START_BOUND_SECONDS` to the timing test when it adds run starts, as both designs say.
- F008 fixed: 10.1 requires the swallow comment.
- F009, F010 dropped (notes).
