---
docType: review
layer: project
reviewType: tasks
slice: requests
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/240-tasks.requests.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 10174be1f344c8b58777ff48de84edc9b2372da8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 9
promptTokens: 482591
cachedTokens: 365146
cacheWriteTokens: 117435
completionTokens: 6370
durationSeconds: 82.1
costUsd: 1.140856
costBasis: provider
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "`member_mismatch` rejections are never recorded, which D9 requires"
    location: "project-documents/user/tasks/240-tasks.requests.md:150"
  - id: F002
    severity: note
    category: production-state
    summary: "Phase 7 hand-off leaves out two details the design gives"
    location: "project-documents/user/tasks/240-tasks.requests.md:307-314"
  - id: F003
    severity: note
    category: formatting
    summary: "Cosmetic defects"
    location: "project-documents/user/tasks/240-tasks.requests.md:275"
  - id: F004
    severity: pass
    category: coverage
    summary: "Success criteria are covered"
    location: "project-documents/user/tasks/240-tasks.requests.md"
  - id: F005
    severity: pass
    category: sequencing
    summary: "Sequencing, sizing and commit markers"
    location: "project-documents/user/tasks/240-tasks.requests.md"
  - id: F006
    severity: pass
    category: verification
    summary: "Load test, CI gate and referenced helpers exist"
    location: "pyproject.toml:64"
---

# Review: tasks — slice 240

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] `member_mismatch` rejections are never recorded, which D9 requires

D9 says every `send`, `reply` or `cancel` that is rejected after its caller is resolved writes one `message_rejections` row. It allows exactly two exceptions: `not_a_member`, and a `cancel` whose caller is unknown (`project-documents/user/slices/240-slice.requests.md:198`). With `member_mismatch`, the directory has already resolved to a member, so the caller is known and a row is required.

The tasks miss this in three places:
- Task 6.2 lists which pre-transaction rejections write a row: malformed, over-limit and `unknown_recipient`. It says `not_a_member` writes none. It never mentions `member_mismatch`, so an implementer following the list will not record it.
- Task 5.1 has `resolve_caller` return a refusal. It doesn't say the refusal must carry the member the directory resolved to, and the writer needs that id to record the row.
- No test asserts the row. Task 5.2 checks only the code at the resolver level, and 6.3, 7.2 and 8.2 don't include a `member_mismatch` case.

The design states that "no send or reply that cannot be applied vanishes", and this case currently would.

Fix:
1. In 5.1, require the `member_mismatch` refusal to carry the directory's member id.
2. In 6.2, add `member_mismatch` to the list of rejections that write a row.
3. In 6.3, 7.2 and 8.2, add a case asserting that `member_mismatch` leaves one row under the directory's member.

### [NOTE] Phase 7 hand-off leaves out two details the design gives

The task file explains why the live migration moves to Phase 7: migrating before the merge would leave the installed tool refusing the store. That reason holds. Two details from the design's Special Considerations (`240-slice.requests.md:345`) are missing from the hand-off:
- The design says the restore path goes in the slice notes. The hand-off doesn't say to write it there.
- The design deletes the backups after the review passes. The hand-off deletes them as soon as the read-back passes.

Add a line that writes the restore path into the slice notes. This keeps the hand-off consistent with the design.

### [NOTE] Cosmetic defects

- Line 275, task 13.2: a sentence runs on with no full stop, in "…gets done Extend `tests/rule_blocks.py`…".
- Line 267: the `**Commit**:` marker after 12.2 has no blank line before it, unlike the other markers.

### [PASS] Success criteria are covered

Each criterion in the design (lines 278–299) maps to at least one task:

| Criterion | Tasks |
|---|---|
| Scenario D over the CLI and MCP | 12.1, 12.2, 14.1 |
| Every state has an exit | 12.2, 2.6, 10.6 |
| Two-process accept | 7.3 |
| Each reject code | 5.2, 6.3, 7.2, 8.2 |
| Two worktrees with different `since` | 9.2 |
| `chain_too_deep` and recorded rejections in `list` | 6.3, 10.4 |
| Over-limit text | 4.4, 6.3 |
| `list` and `status` content, `list -j` equals `status` | 10.3–10.5, 11.5 |
| Expired before the sweep writes it | 2.2, 9.2, 10.4 |
| One prune test per table | 2.6 |
| Timing bound | 11.6 |
| `StoreBusyError` reported in `sweep_problem` | 10.2, 10.4 |
| Missing config keys fail by name | 3.1 |
| `CHECK` pinning and contract docs | 1.2, 13.1, 15.2 |
| MCP parity | 11.1a–11.4 |
| 220 behavior unchanged | 10.4, 11.5 |

Task 15.2 also requires a note mapping every criterion to a passing test.

### [PASS] Sequencing, sizing and commit markers

- **Order:** dependencies run forward with no cycles: vocabulary → migration → store → config and moves → models → resolution → operations → status/list → doors → docs → live tier.
- **Test pairing:** every implementation task is followed straight away by its tests.
- **Commit markers:** they sit at green points, at sections 1, 2, 3, 5, 8, 9, 10, 12, 13 and 15.
- **Size:** one task file fits a 5/5 slice.

### [PASS] Load test, CI gate and referenced helpers exist

- **Load test:** task 9.3 adds `tests/load/test_messages_load.py`.
- **CI gate:** CI's `uv run pytest` step (`.github/workflows/ci.yml:40`) collects that file, because `pyproject.toml` ignores only `tests/live`. Task 9.3 explicitly checks collection, so the gate is stated rather than left implicit.
- **Helpers:** I confirmed these exist: `tests/user_configs.py#example_config_text`, `tests/operations/set_up_worker.py`, `tests/operations/test_every_state_exits.py`, `tests/operations/test_list_view.py`, `tests/cli/test_list_cli.py`, `tests/mcp_server/test_instructions.py` and `tests/cli/test_parser_names.py`.

### Run Digest

- Response length: 5375 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 482591 / 365146 / 117435 / 6370 / not computed
- Duration: 82.1 s
- Cost: $1.14 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Resolution

- **F001 fixed.** In 5.1 the `member_mismatch` refusal now carries the directory's member id. 6.2, 7.1 and 8.1 write its D9 row under that member, in a short transaction of its own. 6.3, 7.2 and 8.2 each assert one row under the directory's member and no other change.
- **F002 fixed in part.** The hand-off now writes the restore path into the slice notes before migrating. The backup deletion timing already matches the design: deletion happens at slice integration, after the review has passed, and the read-back check runs inside that step. It is unchanged.
- **F003 fixed.** Added the full stop in 13.2 and the blank line before the commit marker after 12.2.
