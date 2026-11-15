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
reviewedSha: 08157748ba87280675abe5b8e2a375630e89e6e0
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 14
effort: xhigh
turns: 15
promptTokens: 916541
cachedTokens: 716245
cacheWriteTokens: 200282
completionTokens: 64588
durationSeconds: 304.5
costUsd: 0.291066
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Correction's time handling is misstated and contradicts the recipient table"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:175"
  - id: F002
    severity: concern
    category: correctness
    summary: "The note recipient rule assumes distinct event times, which fixed-clock tests do not provide"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:163"
  - id: F003
    severity: concern
    category: cross-slice-consistency
    summary: "240's slice design is not in the amendment list"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:210-218"
  - id: F004
    severity: concern
    category: under-specification
    summary: "What `inbox` returns for notes under `since` is unstated"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:147"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Restated sections a reader can cut"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:210-245"
  - id: F006
    severity: note
    category: under-specification
    summary: "Consumers added after a report get correction and withdrawal notes for it"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:175"
  - id: F007
    severity: note
    category: dependencies
    summary: "Frontmatter dependencies omit 227 and 241"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:6-8"
  - id: F008
    severity: note
    category: nfr
    summary: "`report_release`'s worst-case duration is not bounded"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:91"
  - id: F009
    severity: pass
    category: scope
    summary: "Scope from the plan is covered, with nothing deferred"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:40-47"
  - id: F010
    severity: pass
    category: architecture-alignment
    summary: "Architecture alignment: kinds, storage and retention"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:71-77"
  - id: F011
    severity: pass
    category: integration
    summary: "Integration points with 241 and 242 agree"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:247-256"
  - id: F012
    severity: pass
    category: operator-walkthrough
    summary: "Operator walkthrough: every note state has an exit"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:325-337"
---

# Review: slice — slice 243

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Correction's time handling is misstated and contradicts the recipient table

Line 175 says "versioning and correction set `versioned_at` to `now`". 227's design (`project-documents/user/slices/227-slice.program-dependencies.md:106`) says a correction sets `reported_at` to now, and `versioned_at` to now only when the row has a version after the write. The store's correction statement does the same. The table at line 173 (a corrected report with no version reaches `from_source` consumers) is right only because `reported_at` moves. The boundary paragraph at line 163 says visibility depends on whether the consumer's own time column moved. Read literally, a correction of an unversioned report reaches no `from_source` consumer. Fix line 175 to match 227.

### [CONCERN] The note recipient rule assumes distinct event times, which fixed-clock tests do not provide

The boundary is `>=` against `now`, so a time that did not move is excluded only if it is strictly earlier than `now`. If an event's `now` equals the stored time, the old time counts as moved. The design's own unit tests use a fixed clock (line 302, for retention). If the matrix test (criterion at line 265, risk at line 308) uses one fixed clock, a `versioned` event would send a note to `from_source` consumers, and the table at line 171 says none. Fix: state the precondition that each event's time is later than the stored times it compares against, make the matrix test advance the injected clock between events, and fail the event explicitly when the precondition does not hold.

### [CONCERN] 240's slice design is not in the amendment list

The amendments change 240's `send` (`kind`, `to_program`, `--to` no longer required, resend comparison), `inbox` (`notes`, request reads by kind) and the reject paths for note ids. The docs step covers "the contract docs and the architecture and plan". It does not name 240's slice design or its task breakdown, which 240 is built from. The 240 design still says `--to` is required (`project-documents/user/slices/240-slice.requests.md:243`), its resend comparison omits `to_program` (`240-slice.requests.md:134`), and its `inbox` has no notes (`240-slice.requests.md:183-185`). The missing `to_program` is a correctness point: a note reused under the same id for another program would read as `unchanged` and be dropped. Add 240's design and task breakdown to the docs step.

### [CONCERN] What `inbox` returns for notes under `since` is unstated

240 D7 (`240-slice.requests.md:184`) defines `deliveries` under `since` as every delivery with `seq > since`, and `requests` as the requests those deliveries concern. 243 adds `notes` but does not say whether note deliveries also appear in `deliveries`. It also does not say whether the `since` branch applies the retention window that the no-`since` branch applies ("inside retention"). A `since` poller (241's watcher, and the rules blocks) needs one answer for each. Fix: state whether `deliveries` excludes note deliveries (or give them a stated shape), and add the retention clause to the `since` branch.

### [CONCERN] Restated sections a reader can cut

- "Amendments to 240 and the parent documents" (210-218) restates D1, D3, D4, D5 and D6 item by item. Replace it with the list of documents to change and a pointer to the decisions.
- "Patterns and Conventions" (220-224): the try/except rule, "operations refuse without raising", and the exit-3 mapping repeat the project rules. Drop them.
- "API Contracts" (228-237): the operation table repeats D1 and D5, and the `NoteView` field list is also in the data flow. Keep one copy.
- "Rules text and docs" (243-245) repeats D8 and the Technical Scope docs list. Keep one.

Keep the D4 audit table (142-152) and the D5 matrix (165-173); they are the work list.

### [NOTE] Consumers added after a report get correction and withdrawal notes for it

Visibility in 227 is per provider and per time, not per pair. A consumer added after a merge report, whose mode can see it, gets no note for the original report but does get the correction or withdrawal note for it. Architecture line 84 says a correction or withdrawal goes "to the same consumers", which the slice reads as "those that see it in `changes`" (line 218). The rule at line 178 ("sends nothing retroactively") covers mode changes but not added pairs. State the consequence in D5 and confirm it is intended.

### [NOTE] Frontmatter dependencies omit 227 and 241

The frontmatter lists only 240, with `interfaces: []`. The body's prerequisites include 227 (`report_release`, `visible_releases`), 222 (`dependency_pairs`) and 241 (the push check, which a success criterion uses). The plan (`project-documents/user/architecture/240-slices.agent-messaging.md:90`) says "Uses 241's push when present", but the push criterion is unconditional. Add 227 and 241 to the frontmatter and say which one the plan means.

### [NOTE] `report_release`'s worst-case duration is not bounded

240 bounds the four message operations, using its `cf` and busy-wait timeouts, against `MCP_CALL_DEADLINE_SECONDS`. `report_release` is an MCP tool. It now runs a sweep and writes one row per recipient inside its write lock, but its worst case is not stated. Add the one-line arithmetic that 240 uses.

### [PASS] Scope from the plan is covered, with nothing deferred

Each plan item for 243 and each of its five success criteria maps to a decision or criterion here: notes to members and programs (D1, D2), stateless notes pruned by age (D6), release notes per visible consumer in one transaction (D5 and the atomicity test), the matrix over `consumed` and outcomes, and push through 241's check. The exclusions are other slices' work or things the plan does not assign.

### [PASS] Architecture alignment: kinds, storage and retention

Notes are `messages` rows with the architecture's kind and recipient rules. Release notes use the architecture's `consumed`-based visibility by calling 227's `visible_releases`. No table, config key or migration is added. Dependency direction holds (operations to store). The sweep-caller change is named as an architecture amendment rather than left implicit.

### [PASS] Integration points with 241 and 242 agree

241 (`project-documents/user/slices/241-slice.push-and-presence.md:237`) says a note is a delivery and its event names the kind, which matches 243's push test. 242 (`project-documents/user/slices/242-slice.hold-and-release.md:120`) counts only `request` rows, which matches D4.

### [PASS] Operator walkthrough: every note state has an exit

I walked the start, the normal path, a wrong note, a wrong release report, a provider with no consumers, a failed note write, removed consumers and an unread note. Each ends with no file edits: notes leave by prune, a correction is a new note, and a failed write rolls back and exits 3. I found no dead end, apart from the `since` retention gap in the `inbox` finding above.

### Run Digest

- Response length: 9596 chars
- Response is newline-free: no
- Tool calls made: 14
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 15
- Tokens — prompt / cached / cache write / completion / reasoning: 916541 / 716245 / 200282 / 64588 / not computed
- Duration: 304.5 s
- Cost: $0.29 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
