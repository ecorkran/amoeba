---
docType: review
layer: project
reviewType: slice
slice: program-dependencies
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/227-slice.program-dependencies.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 753e33399d6bbd658422c46a33ac9af816588d9c
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
effort: high
turns: 8
promptTokens: 409959
cachedTokens: 300576
cacheWriteTokens: 109373
completionTokens: 7143
durationSeconds: 60.8
costUsd: 0.53984
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Consumer rule line's `since` fallback has no command"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#D4 — The starting point belongs to the caller"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "Two departures from the architecture and slice plan are left unreconciled"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#D2 and #D4"
  - id: F003
    severity: note
    category: dependencies
    summary: "Frontmatter omits 224 although the slice edits its code"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:6-8"
  - id: F004
    severity: note
    category: proportionality
    summary: "The `parse_since` extraction is a small addition that stays in scope"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Interfaces Required"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Layering, import direction and integration points"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Architecture"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes for the two new operations are enumerated"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Data Flow, #D2, #D5"
  - id: F007
    severity: pass
    category: risk
    summary: "Soft rule lines are handled as the architecture accepts"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#D6, #Risk Assessment"
---

# Review: slice — slice 227

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Consumer rule line's `since` fallback has no command

D4 gives the `git log -1 --diff-filter=A …` command for the starting point. For the case where it returns nothing, it gives only a description: "the time of the repo's first commit when there is none". D6 then tells the consumer block to use "D4's command and its fallback".

- **The gap:** a repo with no prior slice design is the first-use case, and that is the case the Integration Requirement (a real design run calls `changes`) exercises first. The agent has to invent a command for it, and a repo can have several root commits.
- **Why it matters:** this is the "retrieve a value from a source that may be empty" situation in the project rules. If the agent guesses wrong, `since` is wrong or `changes` rejects it as `malformed`. The design also wants a failed call recorded rather than treated as "no changes", and that is only reliable if the agent can form the call at all.
- **Fix:** name the exact fallback command and its handling of multiple roots. Then add it to the D7 rule-lines test next to the existing flag-name checks.

### [CONCERN] Two departures from the architecture and slice plan are left unreconciled

The design states both departures and justifies them, but neither parent document is changed.

- **D2 identity:** the architecture (line 103 of `220-arch.program-tool.md`) and slice plan item 8 say a report is "identified by member, commit and version". D2 narrows this to member and commit. A different version on a reported commit replaces the earlier one, and a version already on another commit is rejected as `version_conflict`. The reason is sound: 222's `UNIQUE (member_id, commit_sha)` allows nothing else. But under the architecture's wording, a different version would be a second report.
- **D4 starting point:** the architecture says "usually its branch's last merge". D4 uses the previous design's creation time instead, with a good argument about the window between design and merge.
- **Why it matters:** the slice plan already records a similar planning edit for the concept wording. Left as is, an implementer or the next reviewer reading the parent documents gets a different contract from the one built.
- **Fix:** add a one-line planning edit to the 220 architecture and the slice plan entry for each departure, or list both in the Implementation Notes as pending planning edits.

### [NOTE] Frontmatter omits 224 although the slice edits its code

The frontmatter lists only 225 and 226, which matches the slice plan. The slice also changes 224's `decisions` operation to call the new `parse_since()`, and consumes `project_names` from 224. The Prerequisites section names 224, so the dependency is visible. Listing it in `dependencies` would stop the edit to 224's code from being a hidden coupling.

### [NOTE] The `parse_since` extraction is a small addition that stays in scope

Moving 224 D5's `since` rule into `operations/since.py` touches an earlier slice. It avoids two copies of one rule, which the DRY principle asks for, and 224's tests are required to pass unchanged. The one edit to a 226 test (the literal tool count) is stated and bounded. I would not cut either. The rest of the design is proportionate: three rule blocks, three contract docs and the test list fit a relative effort of 3.

### [PASS] Layering, import direction and integration points

The import direction is `cli`/`mcp` → `operations` → `store`/`upstream`, and `store/releases.py` imports nothing from `operations`. The slice uses 226's extension recipe as written: an `OperationName` member, a CLI subcommand and a `ToolSpec` row. It reads 222's `releases` and `dependency_pairs` tables as built, and 222 marks `releases` as "Written by 227". Both operations run in-process, with a stated reason. This fits "one operation, two doors", because neither is long work. No state is mirrored, and no read marker is stored.

### [PASS] Failure modes for the two new operations are enumerated

- **Validation:** bad input returns `rejected / malformed`.
- **Non-member:** a directory that is not a member returns `rejected / not_a_member`.
- **`cf` failure:** it is raised before any store write, as `ContextForgeError`, exit 3.
- **Concurrent writers:** `BEGIN IMMEDIATE` serializes reports of one commit, and an `IntegrityError` is treated as a bug rather than caught.
- **Version conflict:** a version already on another commit is refused with the stored report in the detail.
- **Dead process:** each report is a single transaction, so a process that dies mid-call leaves nothing half-written. This matches "short-lived and restart-safe".

No architecture NFR (latency or throughput) applies to these paths, so none needs restating.

### [PASS] Soft rule lines are handled as the architecture accepts

The architecture accepts that agents may skip the rule lines and names `#304` as the fallback. The design makes a skip visible by requiring the Dependencies section to record the `changes` result or a failed call's error. It gives no example values in the rule text. It keeps Amoeba out of Squadron, since only member repos that opt in carry the lines.

### Run Digest

- Response length: 6473 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 409959 / 300576 / 109373 / 7143 / not computed
- Duration: 60.8 s
- Cost: $0.54 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution

- **[concern] `since` fallback has no command:** fixed. D4 now gives `git log --max-parents=0 --reverse --format=%cI | head -1` (earliest root, so several roots are handled), D6's consumer block points to it, and D7's rule-lines test checks the consumer block contains both commands.
- **[concern] Departures from architecture and slice plan unreconciled:** fixed by listing both (D2 identity, D4 starting point) under a new "Pending Planning Edits" heading in Implementation Notes, to be applied to `220-arch.program-tool.md` and slice plan entry 8 as a planning edit outside this slice.
- **[note] Frontmatter omits 224:** fixed. `224-slice.status-and-decisions` added to `dependencies`.
- **[note] `parse_since` extraction stays in scope:** no change; the reviewer recommends keeping it as is.
- **[pass] Layering, import direction and integration points:** no action.
- **[pass] Failure modes enumerated:** no action.
- **[pass] Soft rule lines handled as the architecture accepts:** no action.
