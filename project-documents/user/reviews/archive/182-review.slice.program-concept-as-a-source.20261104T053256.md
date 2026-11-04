---
docType: review
layer: project
reviewType: slice
slice: program-concept-as-a-source
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/182-slice.program-concept-as-a-source.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261103
dateUpdated: 20261103
reviewedSha: 6cf84b0dce4ce78fb03703aac5bf4ed23ec6a2a5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 186933
cachedTokens: 93756
cacheWriteTokens: 93171
completionTokens: 3025
durationSeconds: 27.4
costUsd: 0.413162
costBasis: provider
runId: run-20261104-slices-plan-7fbffa01
squadronVersion: 0.24.17
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Concept read matches the architecture's source model"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D3"
  - id: F002
    severity: pass
    category: boundaries
    summary: "Visibility rule, layering and dependency direction are correct"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D6"
  - id: F003
    severity: concern
    category: scope
    summary: "Arch's \"state of the edges and requests B is party to\" is deferred without being assigned to a later slice"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#Technical Scope"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Provenance fields and store move are heavier than this slice's consumers need"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D8"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Failure handling for timeouts and a partially failed member-store open is implicit"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D3"
  - id: F006
    severity: note
    category: consistency
    summary: "Size and call-count accounting"
    location: "project-documents/user/slices/182-slice.program-concept-as-a-source.md#D3"
---

# Review: slice — slice 182

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Concept read matches the architecture's source model

Arch "The program concept" says the file is read from the member's checkout on its target at a committed commit, dated by commit, and that a missing snapshot, checkout or file declines with 140's existing source reasons. D3 follows this. It reuses `read_member` and `read_target`, pins one commit, and stays within the existing git allowlist (`show` and `log`). Failures map to `sources_missing` or `sources_unreadable`, with no new `DeclineReason`. The slice also adds no new git verb, which matches the arch principle that 180 adds no other kind of command.

### [PASS] Visibility rule, layering and dependency direction are correct

D6 enforces "never sees another project's rules, plan or PM answers" by construction, because only one path is read from one other repo. It also adds a test with an explicit allowed set. The slice depends on 181, 143 and 144, and none of them depend back on it. The program stage still feeds the answering stage, and `runner/lifecycle` is untouched. The 181 interface amendments this slice needs (`Readable` keeping the checkout and CF project id, `updated_at` on `Program` and `Member`) are already in 181's Integration Points line for 182 (181:353).

### [CONCERN] Arch's "state of the edges and requests B is party to" is deferred without being assigned to a later slice

The arch's Cross-project visibility paragraph says the answerer sees the concept, the member list and the edge and request state. The slice excludes the edge and request state and says "185 adds them to the passages when its check needs them". The arch's slice list gives 182 only the concept and the visibility rule, so the exclusion is defensible, since no edges or requests exist before 183 and 184. But the arch assigns that part of the visibility rule to no slice, and D6's visibility rule text lists only concept and member list as program passages. Name 185 (or 183/184) as the owner in the slice. Also state that D6's rule is extended when the owner lands, so the arch sentence is not dropped.

### [CONCERN] Provenance fields and store move are heavier than this slice's consumers need

D8 moves `PassageKind` into the store, adds three keys to `PassageRef` and the `passage_index` encode/decode, and changes `inspect questions` output. `member` and `commit` are written for one kind only, and `kind` is written for all rows. The justification is that the record must say which repo and commit a passage came from. That is a reasonable need, but no consumer of these keys is identified. 185 is said to read `ProgramContext`, not `passage_index`. Cut or defer `kind` on non-program rows, or the `inspect` display change, unless 185 or 186 names a reader. If kept, the slice should name that reader. Other text can also be trimmed:
- D5's "A path that is both" paragraph handles a registration oddity and needs no decision.
- The "Rejected" bullets in D2 and D4 restate alternatives.
- The Verification Walkthrough's step 3 is a long scratch-setup command block that duplicates the 186 live walkthrough.

### [CONCERN] Failure handling for timeouts and a partially failed member-store open is implicit

The slice adds new I/O: a read-only open of another member's store, one `cf` call and four git calls. `read_program_sources` takes `timeout_seconds`, but no section says what a `cf` or git timeout, or a hung member-store open, produces. D3 covers a non-zero git exit and budget refusals (returns `None`). It never says whether a timeout is `sources_unreadable` or is handled like a budget refusal. State it, by pointing to 143's rule if it already covers it. Also state whether an error from `read_target` for the concept member's checkout (for example a failing `cf` call) maps to `sources_unreadable` with the member id. The `concept member <id> <reason>` template covers only `read_member`'s reasons.

### [NOTE] Size and call-count accounting

"One `cf` call and four git calls" lists target (cf), commit, listing, date and text, which is consistent. The Verification Walkthrough calls it "five-call count", which is also consistent. `passages.md` is already at 360 lines, over the ~300-line guideline. The slice limits growth there, which is appropriate. No NFR from the arch applies to this path, so none is missed.

### Run Digest

- Response length: 4995 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 186933 / 93756 / 93171 / 3025 / not computed
- Duration: 27.4 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
