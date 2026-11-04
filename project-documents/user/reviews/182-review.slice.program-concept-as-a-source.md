---
docType: review
layer: project
reviewType: slice
slice: program-concept-as-a-source
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/182-slice.program-concept-as-a-source.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 4a6d02f21972cd99dbc7bf5b2b3ac696ad1e5de0
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 108420
cachedTokens: 11162
cacheWriteTokens: 97254
completionTokens: 3862
durationSeconds: 32.8
costUsd: 0.429598
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Scope and boundaries match the architecture"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#Technical Scope"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for every new read"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D3"
  - id: F003
    severity: pass
    category: boundary
    summary: "The visibility rule is enforced by construction and proven by a test"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D6"
  - id: F004
    severity: note
    category: scope
    summary: "\"Each member's part of the program\" is met through the concept text, not a generated field"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D4"
  - id: F005
    severity: note
    category: design-decision
    summary: "Precedence between the concept and project rules is inherited, not special-cased"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D5"
  - id: F006
    severity: note
    category: proportionality
    summary: "Asker-is-concept-member case adds a reclassification path"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D3"
  - id: F007
    severity: note
    category: dependency
    summary: "Dependency on an amendment to 181's unimplemented design"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#Interfaces Required"
---

# Review: slice — slice 182

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Scope and boundaries match the architecture

The slice does what the architecture's "program concept" and "cross-project visibility" sections assign to it. It adds passages to 140's source assembly. The concept is read from the member's checkout at its target, at one committed commit, and dated by that commit. A missing snapshot, checkout or file declines the question with 143's existing reasons (D3). Nothing is written to the program store, and no new git verb or `cf` command is added. The Runner stays the only issuer of commands. Dependencies point the right way: 182 consumes 181, 143 and 144, and provides to 185 and 186. No decline reason is added, and `decide.py` does not change (D7).

### [PASS] Failure modes are enumerated for every new read

D3 gives an explicit outcome for each failure of the new I/O path:
- **Concept member unreadable:** `sources_unreadable`, with 181's five reasons.
- **Concept file missing:** `sources_missing`, decided from the listing rather than the exit code.
- **Git or `cf` timeout or failure:** `sources_unreadable`.
- **Non-UTF-8 file:** `sources_unreadable`.
- **Budget refusal:** `None`, so the question stays pending.
- **Busy member store:** bounded by 181's busy timeout.
- **Program store failure:** exits the process as a store failure (D1).

The verification walkthrough maps a test to each case.

### [PASS] The visibility rule is enforced by construction and proven by a test

The architecture says the answerer never sees another project's rules, plan or PM answers. The design enforces this by what the code reads: exactly one path from one other repo, and only the link and snapshot from the concept member's store. The test asserts every passage's `(kind, member, source)` against an allowed set, with a concept member that has its own rules, plan and PM answers. The edge and request state that the architecture also lists is handed to 185 explicitly, in Excluded and in D6. That is a carried item, not a dropped one.

### [NOTE] "Each member's part of the program" is met through the concept text, not a generated field

The slice plan entry for 182 says source assembly "adds the member list and each member's part of the program". D4 supplies the member list and relies on the concept document for what each project does, and it excludes a per-member description field. This fits the architecture, which only names the member list and the concept, and it avoids adding schema. If a concept omits a member's part, nothing else covers it. Reconcile the plan entry's wording with D4 so 185 does not assume a field exists.

### [NOTE] Precedence between the concept and project rules is inherited, not special-cased

A concept committed after a project rule it contradicts wins by date, under the existing precedence rule. The architecture is silent here, and the design states the behavior openly. It is acceptable. If 185's check or live use shows program-level text overriding project rules in a surprising way, change it then.

### [NOTE] Asker-is-concept-member case adds a reclassification path

When the asker holds the concept, the file is read at the already-pinned commit `C`. If it is already among the asker's own selected files, it is relabelled as `program_concept` so it appears once. This is a real case, since the concept member's own questions hit it. The alternative is duplicate passages, so the branch is justified. The test covering both sub-cases is already planned. Otherwise the design is proportionate: two small new modules, one new field, and a made-public refactor of existing helpers instead of copied failure rules.

### [NOTE] Dependency on an amendment to 181's unimplemented design

182 needs `Readable` to carry the checkout and CF project id, and `Program` and `Member` to carry `updated_at`. The design records that it checked this against 181 (20261104) and that 181's Integration Points were amended. It also says 182's tasks follow 181's code if the two diverge. The dependency is visible and bounded, so nothing is hidden.

### Run Digest

- Response length: 4831 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 108420 / 11162 / 97254 / 3862 / not computed
- Duration: 32.8 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
