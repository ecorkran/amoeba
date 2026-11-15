---
docType: review
layer: project
reviewType: slice
slice: notes-and-release-notes
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/243-slice.notes-and-release-notes.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 68ad9b164f3098c959fedd90c2ddda26bac11578
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: xhigh
turns: 9
promptTokens: 420759
cachedTokens: 233184
cacheWriteTokens: 187567
completionTokens: 68056
durationSeconds: 307.3
costUsd: 0.237177
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: specification
    summary: "The recipient rule leaves its `since` boundary unstated"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:162"
  - id: F002
    severity: concern
    category: integration
    summary: "The plan's push criterion for notes is replaced by a store-level proxy"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:249"
  - id: F003
    severity: concern
    category: design-rules
    summary: "Release notes depend on unrelated commands to be pruned"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:196"
  - id: F004
    severity: concern
    category: specification
    summary: "The inbox exclusion for sent notes has a wrong rationale and contradicts self-notes"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:148"
  - id: F005
    severity: concern
    category: proportionality
    summary: "The design is heavier than its plan entry justifies"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md"
  - id: F006
    severity: concern
    category: nfr
    summary: "The architecture's write-lock constraint is not restated for the longer report transaction"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:90"
  - id: F007
    severity: concern
    category: specification
    summary: "The release event has two names"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:82"
  - id: F008
    severity: concern
    category: integration
    summary: "Changes to 240's modules are not recorded as amendments"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:208-215"
  - id: F009
    severity: pass
    category: alignment
    summary: "Release-note recipients follow the architecture's visibility rule"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:157-177"
  - id: F010
    severity: pass
    category: alignment
    summary: "No table, column or setting is added, and release ids cannot collide with sender ids"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:201"
---

# Review: slice — slice 243

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] The recipient rule leaves its `since` boundary unstated

D5 picks recipients with `visible_releases(..., since=now)` for `recorded`, `versioned` and `corrected` (line 162), and with `since` set to the report's own `reported_at` for `withdrawn` (line 172). The doc does not say whether that `since` is inclusive or exclusive as `changes` defines it, or that `now` is the stored report's `reported_at`. If the bound is exclusive, `recorded` notifies nobody, and so does a withdrawal. The architecture's guarantee that a consumer's inbox and `changes` agree depends on this boundary. Name the boundary and the timestamp in D5, referring to 227's definition rather than restating it.

### [CONCERN] The plan's push criterion for notes is replaced by a store-level proxy

Plan entry 243 requires "241's push fires for a note the same as for a request" (240-slices plan, line 89). The 241 design says that criterion is a test owned by 243 (241 design line 237) and that notes push "with no change to this slice" (241 design line 265). This design checks "the two facts the watcher reads" instead (line 249, and line 272). Those facts do not show that a channel event is sent for a note. Add the test to this slice's success criteria: a note delivery produces a channel event that names kind `note` and the sender as counterparty, with no message text. Alternatively, move the criterion to 241 and say so in both documents.

### [CONCERN] Release notes depend on unrelated commands to be pruned

D6 says `report_release` does not sweep because "it has no config in hand," so a release note waits for the next sweep caller. The design does not show that gap. 240 D6 defines `sweep_messages(store, config, now)` as a read-first wrapper for callers that hold config, and the sweep takes `prune_after_days` as a plain argument. The stated reason is therefore unverified, and the cleanup is named but its trigger is another command. In a store where only `report-release` and `inbox` run, release notes are never pruned. The walkthrough (line 342) says a note "is pruned `prune_after_days` after it was sent," which D6 does not guarantee. Either call the sweep from `report_release`, or state the actual exit and correct the walkthrough.

### [CONCERN] The inbox exclusion for sent notes has a wrong rationale and contradicts self-notes

Line 148 hides "notes the member sent" because "a provider's inbox would otherwise hold a copy of every release note it sent." Under D2 and D5 that does not happen: the sender gets no delivery, and release notes write deliveries only to consumers. The rule only matters for a self-note, which D2 (line 126) does deliver. So a self-note is delivered and then hidden from the reader. Remove the exclusion. The delivery rule already decides what `inbox` shows, which is simpler. Also remove the matching sentence in Departures (line 215).

### [CONCERN] The design is heavier than its plan entry justifies

The plan rates 243 Relative Effort 2 and Risk Low (240-slices plan, lines 92–93). This design runs about 343 lines, close to 240's design (about 358 lines, effort 5). Cut in this order:
- **Patterns and Conventions** (lines 217–221) restates AGENTS.md rules. Delete it.
- **Implementation Notes → Development Approach** (lines 318–324) is a task breakdown. Delete it and let the task breakdown carry it.
- **Rules text and docs** (lines 242–244) repeats Technical Scope (line 48) and D8. Delete it.
- **Departures** (lines 208–215): items 1, 4 and 5 repeat D1, D4 and D5. Keep only deviations from the architecture and plan, one line each.
- **Verification Walkthrough** (lines 282–303): steps 2–8 restate the success criteria and the live test. Keep the commands in one place and leave a pointer.

If the template requires a heading, keep the heading with minimal content.

### [CONCERN] The architecture's write-lock constraint is not restated for the longer report transaction

The architecture (Technical Considerations) says writers use SQLite's busy timeout and short transactions, and that none holds the write lock across an outside call. This slice puts note composition, the per-consumer `visible_releases` reads and the inserts inside `report_release`'s `store.write()` (lines 90 and 187). The design does not restate the constraint, does not say whether `_apply`, which runs in the same block, makes an outside call, and gives no hold-time bound (line 236 says only "one insert per consumer"). Restate it with its targets: no outside call inside the block, the wait for the write lock bounded by 240's `BUSY_TIMEOUT_SECONDS`, and hold time as a function of consumers × events.

### [CONCERN] The release event has two names

The `ReleaseNoteEvent` enum is `reported`, `versioned`, `corrected`, `withdrawn` (line 82). Elsewhere the first event is `recorded`: Technical Scope (line 45), the D5 table (lines 166–170), and walkthrough step 5 (line 299). The enum value also feeds the subject template, which would read "Release report reported: …". Pick the term 227 uses for the report outcome, and use it in the enum, the table, the subject and the walkthrough. The project rule is that closed vocabularies are enums defined once, so this must be settled before tasks are written.

### [CONCERN] Changes to 240's modules are not recorded as amendments

D4 changes several 240 modules, but the Departures list records none of them. The 242 design does record its 240 amendment. Specifically:
- `get_message` is 240's "one by-id read of a request" (240 design, store list; 242 Provides). D4 (line 146) needs it to return note rows, so `reply`, `cancel` and `parent` can answer `not_a_request` rather than `unknown_request`. 240 must say so.
- 240 D2's id comparison is `(kind, from_member, to_member, parent_id, subject, body)`. D3 (line 133) adds `to_program`. This is harmless for requests, but it changes 240's rule.
- 240 says new SQL goes in `store/sql_messages.py`, "not the already large `sql.py`" (240 design line 90). Line 83 puts `SELECT_PAIRS_PROVIDED_BY` in `sql.py`. Move it, or say why this query differs.

Record each as a departure, and amend the 240 design in this slice's docs step, as 242 does.

### [PASS] Release-note recipients follow the architecture's visibility rule

D5 sends a note to exactly the consumers whose `changes` shows the report, and calls `visible_releases` rather than copying its rule. The table matches the architecture's stated outcomes: no note to a `from_release` consumer at merge, a note when a version is added, and a new note on correction or withdrawal. The note and the report share one transaction (line 187), as the architecture requires.

### [PASS] No table, column or setting is added, and release ids cannot collide with sender ids

Notes use 240's `messages` and `deliveries` rows, so there is no migration and no config key. State stays in the store, consistent with the architecture's store and config section. The `release:` prefix cannot collide with a sender's id, because 240's id grammar has no colon (240 design D2, relied on at line 184 of this doc).

### Run Digest

- Response length: 8729 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 420759 / 233184 / 187567 / 68056 / not computed
- Duration: 307.3 s
- Cost: $0.24 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
