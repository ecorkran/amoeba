---
docType: review
layer: project
reviewType: tasks
slice: program-dependencies
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/227-tasks.program-dependencies.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: ca6de8ee060fa8606243c6a61518e9d777e33978
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 109199
cachedTokens: 11198
cacheWriteTokens: 97997
completionTokens: 3745
durationSeconds: 31.2
costUsd: 0.431409
costBasis: provider
runId: run-20261108-tasks-plan-9072574c
squadronVersion: 0.24.24
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are all covered"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:67-190"
  - id: F002
    severity: concern
    category: process
    summary: "Final commit marker would be a notes-only commit"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:176-190"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 4.1 cannot pass the test suite on its own"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:135-152"
  - id: F004
    severity: concern
    category: completeness
    summary: "Task 5.3 relies on a CLI contract location that task 0.2 never finds"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:57-65,170"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Task 3.1 is too granular"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:117-120"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 3.2's `project_names` ordering depends on what `project_names` takes"
    location: "project-documents/user/tasks/227-tasks.program-dependencies.md:123"
---

# Review: tasks — slice 227

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are all covered

Each criterion maps to a task:
- **`from_source` vs `from_release` visibility:** tasks 1.3 and 3.2.
- **Version added to an already reported commit, with no double sight for `from_source`:** tasks 1.3 and 2.3.
- **Two worktrees, each seeing everything since its own `since`:** task 3.2, "two `since` values".
- **CLI/MCP parity and `not_a_member` writing nothing:** tasks 2.3, 3.2, 4.1 and 4.2.
- **Format, lint, pyright, no migration, docs match code:** tasks 5.3 and 6.1.
- **Integration criterion (walkthrough step 5):** left as a pending line in task 6.2, which matches the design's "merge does not wait" wording.

I found no scope creep. D1–D8 each trace to a task. The SQL tests use throwaway stores. The design states no NFR, so no load test or CI wiring is needed.

### [CONCERN] Final commit marker would be a notes-only commit

Group 6 changes no source. Task 6.1 only verifies. Task 6.2 only records walkthrough results and the "Step 5 pending" line. The marker `docs: record program dependencies walkthrough` would therefore produce a commit that only adds notes and check-offs. The project rule says "Never make a commit that only checks boxes or only adds notes."

Either delete this marker so the group-6 notes ride along with the next commit, or fold the notes into the group-5 commit and move verification ahead of it. The design wants the walkthrough to gate review, but that does not require a separate commit.

### [CONCERN] Task 4.1 cannot pass the test suite on its own

Task 4.1 adds the two `OperationName` members and the CLI subcommands, and its success line says "tests pass". Task 4.2 adds the matching MCP rows afterwards. Task 4.1 itself says 226's parity tests compare `build_parser()` against `OperationName`. By the file's own wording, 226's MCP tool-name parity tests and the stdio tool-count test therefore fail between 4.1 and 4.2.

The commit comes after 4.2, so nothing broken is committed. A junior agent will still see red tests at the end of 4.1 and may try to "fix" them. Do one of the following:
- Merge 4.1 and 4.2 into one task.
- Scope 4.1's success line to its own new tests and say the MCP parity tests are expected to fail until 4.2.
- Add the `OperationName` members in 4.2 together with the MCP rows, and have 4.1 register the subcommands against string literals.

### [CONCERN] Task 5.3 relies on a CLI contract location that task 0.2 never finds

Task 5.3 says to find the CLI contract "in task 0.2's notes or under `docs/`". The 0.2 checklist does not include locating that doc. It covers imports, DDL, timestamp format, the stdio test and the baseline, but not the CLI contract file or `docs/store-contract.md` and `docs/mcp-server.md`. Add "locate the CLI contract doc, `docs/store-contract.md` and `docs/mcp-server.md`" to 0.2's note list, so 5.3 doesn't leave a junior agent to search with no guidance.

### [CONCERN] Task 3.1 is too granular

Task 3.1 defines `ChangesRequest`, `ChangesResult` and a `ChangesOutcome` enum, and tests three validation cases. That is a small piece of work that task 3.2 depends on immediately. Merge it into 3.2 as its first sub-item. This matches the slice's effort rating of 3 and the design's own four-step implementation note. The same applies, more mildly, to 1.1 and 1.2 and to 2.2 and 2.3. Those at least stand as test-with pairs, so they can stay.

### [NOTE] Task 3.2's `project_names` ordering depends on what `project_names` takes

Task 3.2 requires one `project_names` call "before the store read". Provider ids are only known after the store read through `pairs_of`. That works if 224's `project_names(run)` returns the whole Context Forge list, which is how the design describes it (a provider id "missing from Context Forge's list"). Task 0.2 already asks the agent to find its signature. Add one line there to confirm that it needs no ids as input.

### Run Digest

- Response length: 4821 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 109199 / 11198 / 97997 / 3745 / not computed
- Duration: 31.2 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
