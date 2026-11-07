---
docType: review
layer: project
reviewType: slice
slice: status-and-decisions
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/224-slice.status-and-decisions.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 432605032539ac536623a92f1530a8d017a9376e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: high
turns: 9
promptTokens: 519307
cachedTokens: 404826
cacheWriteTokens: 114469
completionTokens: 8845
durationSeconds: 75.8
costUsd: 0.587673
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "One unrelated directory's `cf` failure fails all of `status`"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md:180-192"
  - id: F002
    severity: concern
    category: proportionality
    summary: "`status` carries an `answering_run` check that its own placement rule makes unreachable"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md:165,187,105"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design is heavier than a 3/5 read-side slice needs; cuts can be named"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#Technical Decisions"
  - id: F004
    severity: note
    category: scope
    summary: "D2 widens the architecture's \"explicit program\" rule; the plan sentence is not updated"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md:135-146"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md:98"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Read, don't mirror"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md:279-285"
  - id: F007
    severity: pass
    category: integration
    summary: "Integration with 223 and external dependency on #303"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md:123-133"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes for new I/O paths"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md:129-130"
---

# Review: slice — slice 224

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] One unrelated directory's `cf` failure fails all of `status`

D4 stops the whole call with `ContextForgeError` (exit 3) when `project_of` fails for any listed run's directory. That includes directories of repos that are not members of any program. `sq runs list` is called without `--all` and returns runs from every directory. So one broken or hung checkout elsewhere can hide `waiting_on_pm` and the missed-hook list.

This conflicts with the architecture's "Fail where someone can see it" principle and its requirement that status show every question that can't be handled. The `waiting_on_pm` rows come from the store and are joined to runs by `run_id` (D4, Questions). They don't need directory placement at all.

The lookups also run one after another, each bounded by the `cf` timeout. D1's "every subprocess is bounded" therefore does not bound the whole call. It can take up to N × timeout.

The design rejects a degraded result only for `sq` failure, where a second result shape would be needed. That reasoning doesn't apply to `cf` placement, because `unplaced_runs` already exists. Adding a `lookup_failed` reason, with the error text, keeps the failure visible and keeps the PM's waiting questions readable. That is one enum value, not a new shape.

### [CONCERN] `status` carries an `answering_run` check that its own placement rule makes unreachable

D4 drops every run whose directory is under `answering_dir()` before any `cf` call. 223 starts answering runs from `answering_dir()/<id>` (223 D12). So no answering run can reach `classify_pause` through `status`.

Even so, `status` step 2 reads "the set of all `answering_run_id` values" and `answering_run_ids()` is added to the store. The `answering_run` class is also in the status column of the D3 table ("not listed"). That is a second mechanism for the same exclusion. It adds a store read, a class value and a test case.

Pick one. The directory skip is needed to avoid `cf` calls. `handle_pause` keeps its store check, because it works from the caller's directory. Then `status` can drop the extra read and the dead class value. The "one definition" cross-check test still holds.

### [CONCERN] Design is heavier than a 3/5 read-side slice needs; cuts can be named

The design has eleven decisions, six new modules, an 11-value classification table and a live tier. Several parts restate other material or cover things this slice does not build:

- **D9** is a decision about work not in this slice (`wrong_checkout`, deferred to amoeba#37). Fold it into one line under Excluded.
- **Dependencies** (the #303 bullet) and **D1 "What waits on #303"** say the same thing twice. Keep it in D1.
- **D5 "What 225 combines"** and the Integration Points / Integration Requirements bullets restate each other. Keep one.
- **Verification Walkthrough** steps 2–5 repeat the live-tier test in D11. Keep the walkthrough and make the live tier reference it, or the reverse.
- **`status_views.py`** is a separate module only to hold result models. Put them beside `status()` unless the file passes the ~300-line limit.
- **Rejected-alternative paragraphs** in D1 and D6 are not needed for implementation.
- **The `answering_run` class in `status`** (see the previous finding).

None of this drops scope the plan assigns to 224. The goal is a shorter design and fewer places to keep consistent.

### [NOTE] D2 widens the architecture's "explicit program" rule; the plan sentence is not updated

Architecture decision 4 and the slice plan entry say `status`, `decisions` and `answer` take an explicit program when called from outside a member. D2 accepts `--program` from anywhere and treats "no flag, outside a member" as all programs. The rationale is sound: there is one PM and MCP sessions start anywhere. The design says it departs from the plan, and the plan's 224 entry (line 90) has been amended for slice state.

That entry still contains the sentence about taking an explicit program from outside a member. The design only says the entry was amended to drop slice state. Update the sentence in the same commit so the plan and design agree.

`status` narrows to the member's program inside a member, while `decisions` never narrows. D5 gives a reason for that (one marker across programs), so this is acceptable.

### [PASS] Layering and dependency direction

`cli → operations → store, config, upstream` is preserved. `run_list.py` and `projects.py` import nothing from `store`, `operations` or `answering`. The shared checkpoint parser is `poll_run`'s, which 223 places in `upstream/squadron/run_outcome.py`, so that import stays inside `upstream`. No subprocess runs inside a store transaction, which matches the architecture's short-lived, restart-safe principle.

### [PASS] Read, don't mirror

Run status and directories come from Squadron on each call, member names from Context Forge, and neither is stored. D10 pins the `(table, column)` inventory, which is the schema test 222 assigned to this slice. The marker moves only forward, inside `BEGIN IMMEDIATE`, and cannot pass the newest record. That fits the architecture's single marker and the plan's `mark_read` criteria.

### [PASS] Integration with 223 and external dependency on #303

`classify_pause` is extracted from `handle_pause` with 223's tests required to pass unchanged. The design pins the `waiting_reason` retention that `decisions` depends on. `answering_dir()`, `read_run_facts` and the `answering_run` check all exist in the 223 design. #303 is the plan's stated external dependency. The design builds against its proposed shape, requires recorded real output before the slice is complete, and uses a `BLOCKED:` line if #303 has not landed.

### [PASS] Failure modes for new I/O paths

The new `sq runs list` and `cf list projects` calls each have a timeout, a typed error, an exit code and a message. An unreadable run file is shown per run instead of failing the call. The architecture states no latency or throughput targets for these paths, so no NFR needs restating.

### Run Digest

- Response length: 7126 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 519307 / 404826 / 114469 / 8845 / not computed
- Duration: 75.8 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Resolution

- **[CONCERN] One directory's `cf` failure fails all of `status`:** Changed. A failed `project_of` lookup (including a timeout) is now an `unplaced_runs` entry with reason `lookup_failed` and the error text, and the rest of `status` is shown (D4). D1 now states the whole call's time bound: the `sq` timeout, plus one `cf` timeout for names, plus one per distinct run directory. The unit test was updated.
- **[CONCERN] Unreachable `answering_run` check in `status`:** Changed. Removed the `answering_run` class from `classify_pause`, the `answering_run_ids()` store read, and the step 2 read. `handle_pause` keeps its store check before calling `classify_pause`. `status` relies on D4's skip of scratch directories (D3).
- **[CONCERN] Design heavier than needed:**
  - Changed: folded D9 into one Excluded bullet (amoeba#37) and renumbered D10 to D9 and D11 to D10.
  - Changed: cut the #303 bullet under Dependencies to a pointer, and moved the issue's proposed shape into D1.
  - Changed: Integration Points and Integration Requirements now point to D5's "What 225 combines".
  - Changed: the live tier now automates Verification Walkthrough steps 1 to 4, rather than restating them.
  - Changed: merged `status_views.py` into `status.py`.
  - Changed: removed the rejected-alternative paragraphs in D1 and D6.
  - The `answering_run` class is handled in the item above.
- **[NOTE] D2 widens the "explicit program" rule; the plan sentence was not updated:** Changed. The 224 entry in `220-slices.program-tool.md` now states D2's and D5's scope rules, and the design's Excluded note says the entry matches.
- **[PASS] Layering and dependency direction:** No change needed.
- **[PASS] Read, don't mirror:** No change needed.
- **[PASS] Integration with 223 and external dependency on #303:** No change needed. `answering_run` stays in `handle_pause` only, as above.
- **[PASS] Failure modes for new I/O paths:** No change needed, apart from the `lookup_failed` change in the first item.
