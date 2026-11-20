---
docType: review
layer: project
reviewType: code
slice: standing-answers
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/230-slice.standing-answers.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 26e603000ddbbca306c2d60adb6ba7a509a7ef40
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
diffTruncated: false
effort: xhigh
turns: 36
promptTokens: 2322612
cachedTokens: 2027105
cacheWriteTokens: 295483
completionTokens: 64611
durationSeconds: 278.0
costUsd: 0.46216
costBasis: provider
runId: run-20261120-p6-fd5a9ca4
squadronVersion: 0.24.34
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Ruling text in `list standing` is not held to the 100-column contract"
    location: "src/amoeba/cli/render/registry.py:134"
  - id: F002
    severity: concern
    category: security-hygiene
    summary: "Standing rulings are a persistent, reach-wide write path controlled only by prose"
    location: "src/amoeba/mcp/standing_tools.py:16"
  - id: F003
    severity: note
    category: type-contract-debt
    summary: "The renderers guess when a result has no reach or no withdraw reason"
    location: "src/amoeba/cli/render/standing.py:35"
  - id: F004
    severity: note
    category: error-handling-observability
    summary: "A ruling larger than the passage cap is accepted at give time and fails only at the next pause"
    location: "src/amoeba/operations/standing.py#standing"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "`MEMBER_REMOVED_REASON` has two import paths"
    location: "src/amoeba/store/message_transitions.py:27"
  - id: F006
    severity: note
    category: test-debt
    summary: "The lock ordering that `standing --member` relies on is not pinned by a test"
    location: "src/amoeba/operations/standing.py:81"
---

# Review: code — slice 230

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 34 successful tool call(s) of 35 made; 141995 of 141995 diff characters reached the model

## Findings

### [CONCERN] Ruling text in `list standing` is not held to the 100-column contract

`_standing_block` writes each line of a ruling with `indented(line)` and no cut or wrap. The module docstring of `registry.py` says every line other than a path is held to 100 columns. `cli/render/text.py` says prose is cut to 100 columns with `…`. A ruling of a few hundred characters prints as one line far past 100 columns. Design 230 D4 does not ask for cutting, and the PM needs the whole ruling, so the fix is to word-wrap the text to `COLUMNS` with `INDENT`, not to cut it. No test catches this: `tests/cli/test_list_cli.py::test_list_standing_shows_active_rows_and_all_adds_withdrawn` uses only one-line rulings. A render test with a long ruling would close the gap.

### [CONCERN] Standing rulings are a persistent, reach-wide write path controlled only by prose

Any agent session can call the MCP `standing` tool. The ruling then applies to every later answering run it reaches (reach `all` by default) until someone calls `withdraw`. The only control is the sentence in `PM_RULING_RULE`: "Call it only for a ruling the PM actually gave." `answer` has the same rule, so the trust model is not new. But `answer` affects one question, and a standing row affects every later one with no human in the loop. The row also records no origin: `store/schema/010_standing_answers.sql` has no door or actor column, so `list standing` cannot show which rulings an agent wrote. The text is written raw into the answering prompt: `answering/passages.py:280` appends `passage.text` without escaping, so a ruling containing a `## Passage` heading or `kind:` lines can forge a passage section. Suggested: record the door of origin on the row and show it in `list standing`, and decide whether standing text should reject passage-section markers. Design D2 chose the prose control, so the PM should confirm it.

### [NOTE] The renderers guess when a result has no reach or no withdraw reason

`render_standing` treats `reach is None` as a rejection (`result.outcome is StandingOutcome.REJECTED or result.reach is None`) and prints `rejected: rejected`. `wiring_results.is_rejected` keys on outcome only, so a non-rejected result with no reach would print "rejected" and still exit 0. Current code always sets reach for `given` and `unchanged`, so this cannot happen today, but it is a silent guess where the rules call for a failure. The same pattern is in `_standing_block` (`registry.py:138`): `f"{row.withdraw_reason}"` would print `None` if the withdrawn and reason fields ever diverged. The database `CHECK` enforces that pair, but neither `StandingResult` nor `StandingRow` encodes it. A model validator that ties reach and the withdrawn fields to the outcome, plus an explicit raise in the renderer, would fix it.

### [NOTE] A ruling larger than the passage cap is accepted at give time and fails only at the next pause

`StandingRequest.text` is only `NonBlankText`, and `standing()` has no configuration, so nothing checks a ruling's size against `passages_max_chars`. The cap is enforced in `answering/passages.py::assemble` at pause time. A ruling over the cap, or a set that grows past it, makes every pause of every reached member decline `sources_too_large` until the PM withdraws something. Design D5 accepts this, and the detail names both shares, so there is an exit. But the PM learns about it at a later pause, not from the `standing` call. The give result could report the standing total against the cap.

### [NOTE] `MEMBER_REMOVED_REASON` has two import paths

The constant moved to `store/vocabulary.py` for `store/standing.py`. `message_transitions.py` keeps it through a new `__all__` re-export. Tests use both paths: `tests/operations/test_handle_pause.py:33` and `tests/operations/test_rm_cascade.py:21` import from `message_transitions`, while `tests/operations/test_rm.py:34` and `tests/store/test_standing.py:20` import from `vocabulary`. Pointing the two `message_transitions` imports at `vocabulary` and dropping the re-export and the `__all__` entry would leave one path.

### [NOTE] The lock ordering that `standing --member` relies on is not pinned by a test

The module docstring says `--member` is resolved through `cf` before the write transaction opens, "so no subprocess runs while the write lock is held." `_member_project_id` runs at line 81, before `store.write()` at line 51. `tests/operations/test_standing.py` checks the `cf` call's `cwd` and that a `cf` failure writes nothing, but not that the lock is free during the call. `tests/load/test_no_cf_under_write_lock.py` already probes this for `report_release`, and the same probe would cover `standing --member`.

### Run Digest

- Response length: 9549 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 36
- Tokens — prompt / cached / cache write / completion / reasoning: 2322612 / 2027105 / 295483 / 64611 / not computed
- Duration: 278.0 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
