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
reviewedSha: dfc83e6f160c0cc60fa8b369d1886c9e2bcef602
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 2004606
cachedTokens: 1795506
cacheWriteTokens: 209074
completionTokens: 91273
durationSeconds: 430.3
costUsd: 0.387076
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "report_release's new sweep role is not carried into 242's and 240's sweep mechanisms"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:200-202"
  - id: F002
    severity: concern
    category: operator-walkthrough
    summary: "A persistent write failure has no operator recovery, and the walkthrough says there are no dead ends"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:315-318"
  - id: F003
    severity: concern
    category: integration
    summary: "Note deliveries go through the writer 244 hooks into, and the request-only rule is not placed"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:231"
  - id: F004
    severity: concern
    category: documentation
    summary: "The amendment list leaves architecture sentences this design contradicts"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:216-220"
  - id: F005
    severity: concern
    category: architecture
    summary: "Release-note bodies are outside the architecture's text limits, and the bound cites numbers no design document sets"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:189"
  - id: F006
    severity: note
    category: architecture
    summary: "The matrix oracle and the recipient rule use different `since` values"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:245"
  - id: F007
    severity: note
    category: dependencies
    summary: "Dependencies differ between the frontmatter, the body and plan entry 4"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:6-9"
  - id: F008
    severity: note
    category: proportionality
    summary: "Some sections restate architecture text and can be cut"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:264-283"
  - id: F009
    severity: pass
    category: architecture
    summary: "No migration, config key or new state location"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:204-207"
  - id: F010
    severity: pass
    category: architecture
    summary: "Note kind, delivery and retention match the architecture"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:103-137"
  - id: F011
    severity: pass
    category: integration
    summary: "Release-note recipients reuse 227's visibility rule"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:158-179"
  - id: F012
    severity: pass
    category: integration
    summary: "Push path for notes is unchanged"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:230"
  - id: F013
    severity: pass
    category: architecture
    summary: "Write lock: no outside call inside the transaction"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:93"
  - id: F014
    severity: pass
    category: error-handling
    summary: "Failure paths and the 240 audit are explicit"
    location: "project-documents/user/slices/243-slice.notes-and-release-notes.md:139-156"
---

# Review: slice — slice 243

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] report_release's new sweep role is not carried into 242's and 240's sweep mechanisms

D6 makes `report_release` a sweep caller, so a release report can record a request's expiry. Two mechanisms that depend on the sweep are not updated:
- **Held questions.** 242 starts a held question only after the operations in `START_AFTER_OPERATIONS` (242:218), and `report_release` is not in that set. The architecture says the sweep's expiry starts `handle_pause` detached (architecture line 159). Decide whether `report_release` joins the set. If it does, the start must run after its commit, as 242 requires. That is what keeps the "no process start inside the lock" claim at line 93 true.
- **Note pruning in quiet stores.** 240 makes `sweep_messages` read first and write only when something is due (240:107). The new note prune is not in that check, so `list`, `status` and `handle-pause` may not prune notes. The walkthrough at line 317 says they do. Either add aged notes to the due check or state that only the write callers prune notes.

### [CONCERN] A persistent write failure has no operator recovery, and the walkthrough says there are no dead ends

Line 315 says a failing note write rolls the report back and exits 3, "so the same call can be run again." That only recovers from a transient failure. Because `report_release` now runs the prune (line 202), a prune or note statement that always raises makes every `report-release` exit 3. `send`, `reply` and `cancel` already run the same prune, so the new part is the release-report path. Line 318 says "Dead ends found: none." State the recovery for a persistent failure. Also decide whether a prune error may fail without blocking a release report, for example by reporting it as a detail note, as 240 does for the prune in `handle_pause` (240:107).

### [CONCERN] Note deliveries go through the writer 244 hooks into, and the request-only rule is not placed

Line 231 says 244 needs nothing because "waking is for requests only, and a note does not start a wake." But 240 says 244 hooks in at `send` and its delivery writer (240:271), and this slice writes every note delivery through that writer (line 84). The architecture starts a wake when `send` delivers a request (architecture line 165). If the hook sits in the writer and does not check the kind, a note wakes a repo, which starts an unattended run (architecture line 215). Say where the request-only condition lives, and make it a stated requirement on 244.

### [CONCERN] The amendment list leaves architecture sentences this design contradicts

The slice says the docs make "the same changes in each of them, so no two documents disagree." The architecture amendments name only `inbox` under "Operations" and the sweep callers under "Expiry." Three sentences still disagree with this design:
- The `send` row in Operations says a note goes "with an optional parent" (architecture line 115). D1 rejects `parent` on a note.
- The Envisioned State says a correction or withdrawal "sends a new note to the same consumers" (architecture line 84). D5 means the consumers that see the report in `changes`.
- The text-limit sentence (architecture line 122) says an over-limit message "is rejected and nothing is cut." Line 189 exempts release-note bodies (next finding).

Add the two mechanisms from the first finding (240's due check and 242's start set) to the list as well.

### [CONCERN] Release-note bodies are outside the architecture's text limits, and the bound cites numbers no design document sets

The architecture says text fields "have length limits held as constants" (architecture line 122). D5 gives a release note no limit of its own and says it is "not cut and not rejected." The bound it relies on is the report's limits, written in prose as `changed` 4000, 50 `touched` items of 200, and `version` 128. Problems:
- 227's design states no caps. Its code review found none (227-review, F004), and the architecture says the F004 fix made them constants (architecture line 122). This slice does not name those constants, and I could not confirm the values from any design or contract document. This review does not check the code.
- Repeating the numbers in prose breaks the one-definition rule. The release-note bound should be one named constant derived from the report constants, stated in `cli-contract.md`, with a test that the largest report composes within it.
- The exemption from the architecture's rule belongs in the architecture as well as in plan entry 4.

### [NOTE] The matrix oracle and the recipient rule use different `since` values

D5 sets the boundary at `since = now` (line 165). The matrix criterion (line 245) takes the `changes` oracle at "a `since` just before the event." The two readings differ when an earlier event's time falls inside the "just before" window, so a test could pass against the wrong rule. Use `since = now` in both places. The timestamp dependence is inherited from 227, where `changes` uses the same times. The failure mode at line 166 (an extra note, never a missing one) holds in the cases I traced. The architecture's rule that readers resume from sequence numbers (architecture line 66) concerns reads, and this rule selects recipients, so no further change is needed.

### [NOTE] Dependencies differ between the frontmatter, the body and plan entry 4

The frontmatter lists 227, 240 and 241. The body also names 222 as a prerequisite (line 61), and the frontmatter omits it. Plan entry 4 lists only 240 and says 241 is used "when present, with no code dependency on it." This slice's push test needs 241's code. The plan's order (240 → 241 → 242 → 243) makes that harmless in practice. Make the frontmatter, body and plan agree, and state whether the push test is required when 241 is absent.

### [NOTE] Some sections restate architecture text and can be cut

Plan entry 4 is rated Low risk with effort 2. The design runs about 320 lines with eight decisions. Most of it serves a stated criterion, so it is not overweight. These parts can be cut without losing a requirement:
- Special Considerations (lines 301-304) restate the architecture's "Cross-repo prompt injection" and "Identity is self-asserted." A pointer is enough.
- Verification Walkthrough steps 3 to 6 repeat the functional criteria as shell commands. Step 7 runs the live test that criterion line 262 already requires. Keep one set of steps as the live script.

### [PASS] No migration, config key or new state location

Notes are rows in 240's existing tables, and nothing is written under `~/.config`. This meets the config-is-config rule and matches 240's decision to create the note kind in schema 6 (240:329). No restore step is needed.

### [PASS] Note kind, delivery and retention match the architecture

A note is information with no state, addressed to one member or to a program with the sender excluded (architecture line 80). It is pruned by `prune_after_days` with its deliveries (architecture line 103). Resend follows the first-wins rule, and different content under a reused id is rejected (architecture line 66). D1 to D3 match.

### [PASS] Release-note recipients reuse 227's visibility rule

The slice calls 227's `visible_releases(transaction, provider_id, consumed, since)`, whose two `consumed` rules are at 227:130-131. Notes and `changes` therefore share one definition, as the architecture requires (architecture line 84). The outcome names match 227's `ReportReleaseResult` (227:118), and D5's table agrees with 227's write rules (227:102-108).

### [PASS] Push path for notes is unchanged

241 says the same check pushes a note, and its event names the kind and the counterparty (241:237, 241:148). The push criterion at line 248 tests that path. The event carries no message text, as the architecture requires (architecture line 145).

### [PASS] Write lock: no outside call inside the transaction

Both write transactions keep `cf` calls, process starts and waits outside the lock, as the architecture requires (architecture line 212). The worst case is stated as numbers (45 s, under `MCP_CALL_DEADLINE_SECONDS`). This holds only if the held-question start from the first finding runs after commit.

### [PASS] Failure paths and the 240 audit are explicit

D4 lists each 240 read or write that can see a message row, with its behavior for a note, and requires a test per row. D2 and D3 name the rejection for each invalid note. The release-note write is atomic, and any raise rolls back the report and exits 3 (line 193).

### Run Digest

- Response length: 10685 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 2004606 / 1795506 / 209074 / 91273 / not computed
- Duration: 430.3 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14

## Resolution

- **[CONCERN] report_release's sweep role is not carried into 242's and 240's mechanisms:** Applied. D6 now decides that `report_release` does not join 242's `START_AFTER_OPERATIONS`, because 242 starts held questions from `effective_state` with no timer, and `report_release` starts no process. 240's `sweep_messages` due check gains aged notes, so `list`, `status` and `handle_pause` prune them, with a Technical Requirement and test. The amendment list names both.
- **[CONCERN] A persistent write failure has no operator recovery, and the walkthrough says there are no dead ends:** Applied. D6 decides a prune error is not split off to let the report through. The Operator Walkthrough separates a transient failure (run the command again) from a persistent store fault (the error names it, the provider's agent records it per the Provider block, and the same command is run once the store is fixed). "Dead ends found: none" now names that one dead end. The store's own repair is stated as outside this slice.
- **[CONCERN] Note deliveries go through the writer 244 hooks into, and the request-only rule is not placed:** Applied. The wake hook is placed in `send`'s request branch, never in the shared delivery writer, as a stated requirement on 244 with a test (a note to a wakeable member starts nothing). It is in Provides to Other Slices and the amendments, including a change to 240's 244 line.
- **[CONCERN] The amendment list leaves architecture sentences this design contradicts:** Applied. The list now names the architecture's `send` row (a note takes no `parent`), "Message kinds" ("same consumers"), the sender-picks-the-id principle (release-note ids are Amoeba's), the text-limit sentence, "Operations" `inbox` and "Expiry". It also adds 240's due check and 244 line, a no-change entry for 242 with its reason, and the plan's Dependencies line.
- **[CONCERN] Release-note bodies are outside the architecture's text limits, and the bound cites numbers no design document sets:** Applied. The prose numbers are removed. D5 now names the report constants in `report_release_models.py` and defines one constant, `MAX_RELEASE_NOTE_BODY_LENGTH`, derived from them plus the template. A test composes the largest report for each outcome and checks it is within the constant. `cli-contract.md` states it. The body no longer names the provider's member id (it is `from_member`), so its length does not depend on an id length no document sets. The architecture exemption is in the amendments.
- **[NOTE] The matrix oracle and the recipient rule use different `since` values:** Applied. The criterion, the assumption paragraph and the risk bullet now use the event's own `now` as the oracle's `since` (a withdrawal uses the report's `reported_at`, before the delete).
- **[NOTE] Dependencies differ between the frontmatter, the body and plan entry 4:** Applied. The frontmatter now includes 222. The body says the push test is required and that 241 precedes 243 in the plan's order. The plan's Dependencies line is amended to 222, 227, 240 and, for the push test, 241.
- **[NOTE] Some sections restate architecture text and can be cut:** Applied. Special Considerations is reduced to one pointer sentence, and Verification Walkthrough step 7 (the live test, already a criterion) is cut, with the intro naming the live test.
- **[PASS] No migration, config key or new state location:** No change needed.
- **[PASS] Note kind, delivery and retention match the architecture:** No change needed.
- **[PASS] Release-note recipients reuse 227's visibility rule:** No change needed.
- **[PASS] Push path for notes is unchanged:** No change needed.
- **[PASS] Write lock: no outside call inside the transaction:** No change needed. D6 now says `report_release` starts no process, which keeps this true.
- **[PASS] Failure paths and the 240 audit are explicit:** No change needed.

No finding was deferred, so no GitHub issue was filed.
