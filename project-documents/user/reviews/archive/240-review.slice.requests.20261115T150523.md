---
docType: review
layer: project
reviewType: slice
slice: requests
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/240-slice.requests.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 11e55448e958e5dc0fc68839611894930a6a939a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: xhigh
turns: 9
promptTokens: 675897
cachedTokens: 496485
cacheWriteTokens: 179400
completionTokens: 72499
durationSeconds: 428.6
costUsd: 0.223537
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: fail
    category: architecture-boundary
    summary: "List and status expose request subjects without the quoted-data notice"
    location: "project-documents/user/slices/240-slice.requests.md:203-206"
  - id: F002
    severity: concern
    category: integration
    summary: "`highest_seq(member_id)` and `as_of_seq` are different numbers"
    location: "project-documents/user/slices/240-slice.requests.md:251"
  - id: F003
    severity: concern
    category: integration
    summary: "The terminal-state hook for 242 has no defined return values"
    location: "project-documents/user/slices/240-slice.requests.md:201"
  - id: F004
    severity: concern
    category: under-specification
    summary: "The `inbox` result field `problems` is never defined"
    location: "project-documents/user/slices/240-slice.requests.md:179"
  - id: F005
    severity: concern
    category: under-specification
    summary: "A repeated cancel has two contradictory outcomes"
    location: "project-documents/user/slices/240-slice.requests.md:157"
  - id: F006
    severity: concern
    category: failure-modes
    summary: "Resending a request that has already ended returns exit 0 with no way forward"
    location: "project-documents/user/slices/240-slice.requests.md:132"
  - id: F007
    severity: concern
    category: failure-modes
    summary: "The new `cf` calls have no timeout or hang handling"
    location: "project-documents/user/slices/240-slice.requests.md:257"
  - id: F008
    severity: concern
    category: architecture-alignment
    summary: "Malformed and over-limit sends are not recorded, against \"no silent drops\""
    location: "project-documents/user/slices/240-slice.requests.md:196"
  - id: F009
    severity: note
    category: consistency
    summary: "Cancel authority is wider than the architecture's wording"
    location: "project-documents/user/slices/240-slice.requests.md:141"
  - id: F010
    severity: note
    category: consistency
    summary: "Two names depart from the parent documents"
    location: "project-documents/user/slices/240-slice.requests.md:211"
  - id: F011
    severity: note
    category: consistency
    summary: "\"Defaults defined once in the config layer\" conflicts with the project's no-defaults rule"
    location: "project-documents/user/slices/240-slice.requests.md:211"
  - id: F012
    severity: note
    category: proportionality
    summary: "The note half of the schema is built before its writer"
    location: "project-documents/user/slices/240-slice.requests.md:124"
  - id: F013
    severity: note
    category: proportionality
    summary: "Two parent-rule additions are not in the architecture"
    location: "project-documents/user/slices/240-slice.requests.md:191"
  - id: F014
    severity: note
    category: walkthrough
    summary: "The operator walkthrough contradicts itself on editing files"
    location: "project-documents/user/slices/240-slice.requests.md:329-331"
  - id: F015
    severity: note
    category: state-and-config
    summary: "Backup cleanup and placement are ambiguous"
    location: "project-documents/user/slices/240-slice.requests.md:325"
  - id: F016
    severity: note
    category: under-specification
    summary: "The verification walkthrough is a draft to be refined after implementation"
    location: "project-documents/user/slices/240-slice.requests.md:283"
  - id: F017
    severity: pass
    category: architecture-alignment
    summary: "Sweep, read and write rules match the architecture"
    location: "project-documents/user/slices/240-slice.requests.md:103-105"
  - id: F018
    severity: pass
    category: architecture-alignment
    summary: "Request states, first-accept-wins and retention match the architecture"
    location: "project-documents/user/slices/240-slice.requests.md:147-160"
---

# Review: slice — slice 240

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] List and status expose request subjects without the quoted-data notice

D11 limits the `notice` field to the four message results (`send`, `inbox`, `reply`, `cancel`). D12 (line 213) puts each request's `subject` into `list` and `status`, in text and `-j` output. The `rejected_sends` entries also carry sender-supplied `to_ref`. The parent architecture says message text "reaches the receiving agent only through `inbox`, under the quoted-data notice" (240-arch, Technical Considerations, "Cross-repo prompt injection"), and "No silent drops" does not waive that. The plan says the notice "wraps all message text." Fix: add the notice field to the `list` and `status` results and their tool descriptions, or keep subjects out of them and show only id, state and age.

### [CONCERN] `highest_seq(member_id)` and `as_of_seq` are different numbers

The "Provides to 241" list names `store.deliveries.highest_seq(member_id)`, and the plan and architecture define the push check as the member's own highest sequence. D7 (line 183) defines `as_of_seq` as the store-wide `sqlite_sequence` maximum. The design never defines `highest_seq`. If 241 reuses `as_of_seq`, the watcher fires for other members' mail, which the architecture rules out. Fix: define `highest_seq` as `MAX(seq) WHERE member_id = ?`, say how a fall on prune is treated, and state that `as_of_seq` is not per-member.

### [CONCERN] The terminal-state hook for 242 has no defined return values

242 must start `handle_pause` for runs waiting on any request that reaches a terminal state through `reply`, `cancel`, `rm` or the sweep. The design returns `expired_ids` from the sweep and a `RequestView` from `reply`. `cancel_member_requests` (D10) specifies no return value, so 242 cannot learn which requests `rm` cancelled. Line 252 names "request-state-change events" from all four sources, and nothing defines them. Fix: give `cancel_member_requests` a return value (the cancelled ids and states) and define one result or event shape for `reply`, `cancel` and `rm`.

### [CONCERN] The `inbox` result field `problems` is never defined

D7 lists `problems` in the `inbox` result. No other part of the design says what fills it or when. A consumer cannot know its meaning. Fix: define the conditions that populate it, or remove it.

### [CONCERN] A repeated cancel has two contradictory outcomes

D4 says "any action on a terminal request" is `not_applicable`, and its table includes `cancel` (line 152). The API table (line 229) lists `cancel` outcomes `cancelled`, `unchanged` (already cancelled) and `rejected`, and exit 0 for `unchanged`. A second cancel is therefore either exit 1 `not_applicable` or exit 0 `unchanged`. Pick one. The success criteria depend on D4's rule.

### [CONCERN] Resending a request that has already ended returns exit 0 with no way forward

D2 returns `unchanged` for an identical resend whatever the stored state, and the CLI exits 0 for `unchanged`. An agent that retries an expired, declined or cancelled request with its original id gets success and no new request. The operator walkthrough says "Dead ends found: none" (line 338) and does not cover this path. Fix: for a stored request in a terminal state, return a non-zero outcome that names the state and tells the caller to use a new id, and add this step to the walkthrough.

### [CONCERN] The new `cf` calls have no timeout or hang handling

Line 257 says a `cf` failure exits 3 and writes nothing. It says nothing about a call that hangs. `inbox` makes two `cf` calls per poll, and agents poll at four moments per session, so a hung `cf` blocks the session at its start (risk noted at line 305). The architecture names only SQLite's busy timeout. The 220 code audit records a `cf_timeout_seconds` moving into user config. The design should say which timeout the new calls use and what a timeout returns.

### [CONCERN] Malformed and over-limit sends are not recorded, against "no silent drops"

D9 records only in-transaction rejections and returns `malformed` and over-limit errors without recording them. The architecture's "No silent drops" principle says a message that cannot be sent is "a recorded outcome with a reason, visible in `inbox` or `list`." The stated reason, "no sender to attach them to," fits `not_a_member` but not a malformed send from a resolved sender, which D3 resolves before any store lock. Fix: record malformed rejections when the sender is known, or name the exception to the architecture.

### [NOTE] Cancel authority is wider than the architecture's wording

The architecture allows cancel from "the sender's agent, or any agent acting for the PM" (The request's states). The plan says "by an explicit id from another session." The design lets any session that holds the id cancel, including the addressee's session. Decide whether the addressee may cancel and state it, because the rules say to decline with a reason, not cancel.

### [NOTE] Two names depart from the parent documents

The design renames the architecture's `request_open_ttl` to `request_open_ttl_hours` (the reason, units, is stated), and names the rules blocks "Requesting" and "Handling" where the plan and architecture say "consumer and provider messaging blocks" (the reason, collision with 227's blocks, is stated, line 242). Confirm both with the PM and update the parent documents so the names agree.

### [NOTE] "Defaults defined once in the config layer" conflicts with the project's no-defaults rule

The plan's success criteria and the architecture's "Store and config" section say the new keys have "defaults defined once in the config layer." The design makes both keys required with no default. That matches the project's no-defaults convention (222's review: missing keys "fail with an error instead of falling back to a default"; 180's review: "no defaults (a project rule)"). The design is right, but the parent wording should change so the next reviewer does not reopen it.

### [NOTE] The note half of the schema is built before its writer

`kind = note`, `to_program` and the note branches of the CHECK are written here but unused and untested in 240. The reason holds: the plan gives 243 no migration, and SQLite cannot widen a CHECK in place. Keep it, and make 243's reliance explicit. Alternatively, add a migration step to 243 and cut the columns here.

### [NOTE] Two parent-rule additions are not in the architecture

The architecture asks only for the depth limit. `parent_not_yours` protects what a chain means, so keep it. `parent_closed` adds a rejection and a test with no stated harm, because a child under a terminal parent just does not appear as waiting. It is a cut candidate, or it needs a stated reason.

### [NOTE] The operator walkthrough contradicts itself on editing files

The section says "with nobody needing to edit a file," then its Start step says to add the two config keys. It should say that the edit is the one manual step, and what an operator sees with an old config: `ConfigError` naming the key, on every command, until it is fixed.

### [NOTE] Backup cleanup and placement are ambiguous

"Copy `config.yaml` to `config.yaml.pre-240` beside it" can mean beside the SQLite backup in the state directory, which would put a config copy under state. It can also mean beside `config.yaml`. "`rm` clears it" can be read as `amoeba rm`, which removes a member and cancels its requests. Name both paths explicitly in the config directory, and say "delete with the shell `rm`."

### [NOTE] The verification walkthrough is a draft to be refined after implementation

The expected outputs are the acceptance check. Leaving them to change after Phase 6 lets the check follow the code. Fix the expected outputs before task breakdown, and change them afterwards only by a recorded decision.

### [PASS] Sweep, read and write rules match the architecture

`send`, `reply` and `cancel` sweep inside their own write transactions, `status`, `list` and `handle_pause` sweep, and `inbox` is a read with no marker. Expiry is read through `effective_state`. This matches the architecture's "Expiry" and "No shared read marker."

### [PASS] Request states, first-accept-wins and retention match the architecture

The D4 transitions match the architecture's state table. `accepted` never expires and exits by `done`, `decline` or `cancel`. Terminal rows are pruned by `prune_after_days`, and open and accepted rows are never pruned. Every scope item the plan gives 240 is present.

### Run Digest

- Response length: 11564 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 675897 / 496485 / 179400 / 72499 / not computed
- Duration: 428.6 s
- Cost: $0.22 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 18
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 18
- Finding-shaped matches — surviving validation: 18
