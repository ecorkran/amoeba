---
docType: review
layer: project
reviewType: slice
slice: outbound-change-feed-and-detection-of-external-work
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: 89a62b098407f8a5ee87ec6de6ef25ae5991642d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
durationSeconds: 47.6
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the event seam, writer model, and ownership split"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#Technical Decisions"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "\"Push, not poll\" is addressed honestly"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#D2"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Overweight design: cut or defer mechanisms nothing in this slice consumes"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#Technical Scope"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Defer rule can starve detection indefinitely, with no visibility or bound"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#D5"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Follower failure modes are not enumerated"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#Following the feed"
  - id: F006
    severity: concern
    category: specification
    summary: "`attribute_review` has three different signatures, and the detection pseudocode is incomplete"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#Component Structure"
  - id: F007
    severity: concern
    category: consistency
    summary: "Inconsistent policy on editing completed slices' documents"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#D8a"
  - id: F008
    severity: note
    category: scope
    summary: "Feed coverage is bounded to the tables that exist today"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#Patterns and Conventions"
  - id: F009
    severity: note
    category: integration
    summary: "Detection and Runner rely on 120 honoring unbuilt requirements"
    location: "project-documents/user/slices/106-slice.outbound-change-feed-and-detection-of-external-work.md#D5"
---

# Review: slice — slice 106

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the event seam, writer model, and ownership split

The design implements the arch's event-seam surface (outbound change feed, detection of work nobody in Amoeba issued). Inbound human replies go through 103's inbox, and the tenant is an in-process peer of `InboxTenant`. The store does not import `upstream`, `process`, or `feed`, so dependencies run one way. D5 follows the arch's rule that detection ownership follows who issued the action. D2 leaves the network transport to 109, matching the arch's "its own process" decision. The slice-plan criteria are covered: a subscriber is notified of status changes, external reviews are ingested with provenance, provider failures are detected as failures, and detection can be swapped via `ReviewSource`.

### [PASS] "Push, not poll" is addressed honestly

The design states that `follow()` polls `PRAGMA data_version` and does not call it push. It scopes the arch goal to inbound signals, and the goal's actual prohibition (re-reading or recomputing state) is not violated. It defers real push to 109. The arch sets no numeric NFR for this path, and the slice says so and states its own bounds (0.25 s follow, 2 s scan).

### [CONCERN] Overweight design: cut or defer mechanisms nothing in this slice consumes

The slice-plan criteria are a subscriber notification, external review ingestion, provider-failure detection, and a swappable source. The design adds more than that:
- **`read_transaction()` (D1a).** It amends 101's read-only handle, and its only consumers are 109 and 160. `change_head` and the snapshot-then-follow pattern are not used by any 106 deliverable. Defer it to 109, or to whichever slice first needs a consistent snapshot-plus-head read.
- **`record_runner_report` (API table).** This is the Runner's write path, added 20261008 for 110/120. D5 point 3 is a requirement on 120, and this slice can state that requirement in the contract without building the method. Defer it to 120, or to 110 if it must exist earlier.
- **Detection attempts sidecar and `failed` listing state.** The mechanism is a second bounded-failure path, reusing `AttemptsSidecar` and `write_durably`, plus a per-watch `baseline-{sha256}` variant. It handles a store failure on a single file, which is a rare event. Choosing a simpler rule (stop the process and let the operator intervene) would remove the parked state, its listing branch, and the baseline variant.
- **Five-row baseline failure table and `baseline_pending`/`unreachable`/`failed` watch states.** These could collapse to "baseline fails → retry next scan, log once."
- **D7 (`source_document`).** Adding a column and changing 104's `finding_changes` is a contract change to a completed slice. The need is real, since task reviews come in parts, but it is separate work. Consider splitting it into its own small slice or an explicit 104 follow-up.
- **The latency-posture paragraph and the 9-step walkthrough.** The paragraph restates 102's standing rule. Trim both.

Overall the design is the heavy option on most fronts where a lighter one meets the requirement.

### [CONCERN] Defer rule can starve detection indefinitely, with no visibility or bound

Detection skips a project while any review-producing journal entry is open. The doc does not say what happens when an entry stays open for a long time. Examples are a hung `sq run`, an entry that recovery turned into a `blocked_on_human` node while keeping the entry open (the arch says zero or several matches "becomes a `blocked_on_human` node carrying the journal entry"), or a stopped Runner. PM-launched reviews would then go undetected, and nothing in `inspect watches` shows a `deferred` state. Specify one of two things:
- whether such entries count as "open" for deferral;
- a surfaced `deferred` state plus a log line, so the starvation is visible.

### [CONCERN] Follower failure modes are not enumerated

The detection path has an explicit failure table. The new `follow()` I/O path does not. These cases are missing:
- `SQLITE_BUSY` or locked errors on the read-only connection during a writer commit or migration;
- a store at schema version 5 because the process has not yet been upgraded;
- the store directory or project vanishing mid-follow;
- the `stop` callable raising;
- the CLI's exit behavior on each.

"Raises `StoreError` subclasses" is implicit handling. State the retry-or-raise policy for each case, because 109 and 160 will build on this contract.

### [CONCERN] `attribute_review` has three different signatures, and the detection pseudocode is incomplete

The component list gives `attribute_review(nodes, slice_name)`. The detection flow gives `attribute_review(slice nodes, parsed.slice)`. The API table gives `attribute_review(store, project_id, slice_name)`. The doc also says this rule is exported for 120 to reuse, so the signature is an integration contract. Pick one and say whether it is pure or reads the store. Separately, the detection pseudocode falls through from the `unparseable` branch into attribution, with no `continue`/else.

### [CONCERN] Inconsistent policy on editing completed slices' documents

D7 says 104's design document is not edited because it stays the record of what 104 shipped. D8a says 103's line 319 "is updated to point at the effects." Both are completed slices, so the two rules conflict. Apply the D7 rule to both: record the correction in 106 and in `feed-contract.md` rather than editing 103.

### [NOTE] Feed coverage is bounded to the tables that exist today

The feed covers nodes, verdicts, messages, and detections. It does not cover blocked-state resolution, finding status, or journal entries. Node status changes cover block and resolve, so this is sufficient for the slice-plan criteria. The invariant test already flags future tables, and 108 plans to extend the kinds, so no action is needed. `feed-contract.md` should say plainly that the feed announces node, verdict, message, and detection changes only.

### [NOTE] Detection and Runner rely on 120 honoring unbuilt requirements

D5 points 3 and 5, and D4's attribution rule, are requirements on a Runner that does not exist yet. Both are recorded in `evidence-contract.md` and listed as Risks, which is the right place. The slice cannot enforce them, so 120's design should list them as prerequisites.

### Run Digest

- Response length: 7835 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 47.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
