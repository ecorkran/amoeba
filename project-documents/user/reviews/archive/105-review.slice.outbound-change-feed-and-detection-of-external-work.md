---
docType: review
layer: project
reviewType: slice
slice: outbound-change-feed-and-detection-of-external-work
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 321028cbc745a0048edae8a7916e6fbd930145d3
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Architecture alignment and dependency direction"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#Component-Structure"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated for every new I/O path"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#Patterns-and-Conventions"
  - id: F003
    severity: concern
    category: under-specification
    summary: "The replay invariant test cannot catch missed emissions it claims to"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:264"
  - id: F004
    severity: concern
    category: error-handling
    summary: "`sq --version` subprocess can block the synchronous host loop, violating 102's tenant contract"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:175"
  - id: F005
    severity: note
    category: under-specification
    summary: "`node_created` payload lacks the initial status needed for replay"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:256"
  - id: F006
    severity: note
    category: alignment
    summary: "\"Push, not poll\" tension is surfaced honestly, not hidden"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:195"
  - id: F007
    severity: note
    category: alignment
    summary: "D7's additive change to 104's completed contract is handled correctly"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md#D7"
  - id: F008
    severity: note
    category: alignment
    summary: "Dependency list correction at design time is documented, not silent"
    location: "project-documents/user/slices/105-slice.outbound-change-feed-and-detection-of-external-work.md:64"
---

# Review: slice — slice 105

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Architecture alignment and dependency direction

The store imports nothing from `amoeba.upstream`, `amoeba.process`, or `amoeba.feed` (Technical Requirements), emission sits in private writers so inbox applies and direct calls share it, and the tenant is the only module bridging parser and store — matching the architecture's writer model ("the resident process is the sole writer... the inbox is the one surface parts outside it write to"). Detection ownership (D5) implements the architecture's rule that the seam detects only what nobody in Amoeba issued, and the S8 swap path (D6's `ReviewSource` interface) matches the slice plan's requirement that "the subscriber contract is designed to make this a swap."

### [PASS] Failure modes enumerated for every new I/O path

Baseline failures (missing dir, unreadable file, file deleted mid-read, store failure, registration while stopped), file-level races (D6's four cases), parse failures as outcomes, attribution ambiguity, and store-failure-while-recording (attempts sidecar with bounded retries, mirroring 103's verified `inbox_max_attempts` pattern) are all given explicit handling. Nothing is TBD.

### [CONCERN] The replay invariant test cannot catch missed emissions it claims to

The design states "A new write path that forgets to emit fails this test," but the test as specified rebuilds node status only "from `node_created` and `node_status_changed`" — so a writer that forgets to emit `verdict_recorded`, `message_posted`, or `review_detected` passes. The test should also assert that the replayed change kinds/counts match the scripted operations (e.g., one `verdict_recorded` per verdict recorded, one `message_posted` per message row), or the claimed guarantee does not hold.

### [CONCERN] `sq --version` subprocess can block the synchronous host loop, violating 102's tenant contract

The version-label fallback runs "one `sq --version` per scan that found new files" with `sq_timeout_seconds = 10.0`. Slice 102's D2 (verified: 102:169, 102:210) states "A tenant that launches a long subprocess polls it and checks `stop_requested`; it does not block the loop invisibly" and imposes an explicit obligation that `tick()` return promptly. A blocking subprocess call with a 10-second timeout inside `tick()` blocks the whole loop (inbox application, other tenants) for up to 10s per scan, and ignores `stop_requested`. The design should specify non-blocking execution (poll with deadline, or capture the label outside `tick()`), or record the deviation explicitly.

### [NOTE] `node_created` payload lacks the initial status needed for replay

The payload table gives `node_created` only `kind` and `parent_id`, yet the invariant test rebuilds current statuses from the feed. Rebuilding requires the node's status at creation (whether `create_node` fixes it or accepts it as input). Either the payload should carry the initial status or the test spec should state how it is recovered.

### [NOTE] "Push, not poll" tension is surfaced honestly, not hidden

D2 reinterprets the architecture's "Push, not poll" goal as inbound-only and builds a polling follower for the outbound surface, with the latency bound stated in the contract and a concrete swap path (datagram wake-up) that requires no subscriber change. This is a scope reading of a stated goal that deserves PM ratification — appropriately marked "(PM pending)" — and the design states the cost plainly rather than calling polling push.

### [NOTE] D7's additive change to 104's completed contract is handled correctly

Extending `finding_changes` to group by `source_document` matches 104's verified previous-round rule (104:288: index on `(project_id, node_id, review_type, recorded_seq)`), is backward compatible (nulls match via `IS`, existing verdicts unaffected), and follows proper process: 104's design doc is not rewritten, `evidence-contract.md` and `CHANGELOG` are updated, and 104's tests must still pass. This is the right way to amend a shipped contract.

### [NOTE] Dependency list correction at design time is documented, not silent

Adding 103 to the prerequisite list ("*Added at slice design:*") with the reason — registration and reply delivery both go through the inbox — is correct and verified against the slice plan's dependency list (arch slices doc: 105 consumes "101, 102, 103, 104, 108"). The human-reply path correctly needs no watcher: applying a `resolution` flips status, which emits `node_status_changed` (line 353).

### Run Digest

- Response length: 6595 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 1
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 3906
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
