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
reviewedSha: 1959ad4204108aca250cc5cf661ed8584425e0ca
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: high
turns: 10
promptTokens: 527482
cachedTokens: 409577
cacheWriteTokens: 117893
completionTokens: 8442
durationSeconds: 69.8
costUsd: 0.597815
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Architectural boundaries and goals are respected"
    location: "project-documents/user/slices/227-slice.program-dependencies.md#Technical Scope"
  - id: F002
    severity: concern
    category: integration-mismatch
    summary: "Release-skill line is unconditional, but `touched` must be non-empty"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:140,145,225-227"
  - id: F003
    severity: concern
    category: hidden-dependency
    summary: "`parse_since` and the clock are presented as existing shared pieces, but 224 doesn't define them"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:94,171,316,410-411"
  - id: F004
    severity: concern
    category: proportionality
    summary: "D2 and D7 are heavier than the cases the slice needs"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:150-166,232-248"
  - id: F005
    severity: note
    category: design-assumption
    summary: "\"Never sees fewer\" in D4 overstates, and one window of reports is never shown"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:191-194"
  - id: F006
    severity: note
    category: behavior-clarity
    summary: "Common release flow may yield two reports for one change"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:225-227"
  - id: F007
    severity: note
    category: cross-slice-consistency
    summary: "226's stdio test needs a coordinated edit"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:247"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes and restart-safety are covered"
    location: "project-documents/user/slices/227-slice.program-dependencies.md:108-120,164,208"
---

# Review: slice — slice 227

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Architectural boundaries and goals are respected

The slice follows the architecture's principles for scenario B.
- **Pull, never push:** nothing is marked read, and no notification is sent.
- **Direct pairs only:** `changes` never walks the graph (D3).
- **Rule lines:** they live in `docs/program-rules.md` and are pasted only into member repos, so nothing in Squadron mentions Amoeba.
- **One operation, two doors:** both operations come from `OperationName`, with no logic in `cli` or `mcp`.
- **Import direction:** unchanged from 222 and 226.
- **No new table or migration:** it uses 222's `releases` and `dependency_pairs.consumed`.
- **Plan scope:** the plan entry's criteria are all covered.

### [CONCERN] Release-skill line is unconditional, but `touched` must be non-empty

D1 requires `touched` to have at least one item. It rejects an optional `touched` on the grounds that "a report that touches nothing other repos use should not be made", and says the provider rule line states when to report. The release-skill block (D6) has no such condition. It tells the skill to run `report_release` after every tag, with one `--touched` "for each thing… the release changed".

A release that touches nothing other repos use, and was not reported at merge, gets `rejected / malformed`. The skill then only "reports its error with the release result", so it neither retries nor skips.

The result is that a `from_release` consumer never sees that version. For these consumers the release report is the only report they ever see. The design doesn't say which is intended: skip the release report, or report with a placeholder `touched`.

Fix: add the same "when something other repos use changed" condition to the release-skill line, and say what the skill does for an internal-only release. Alternatively, let a version-adding report (case 3 in D2) take an empty `touched`.

### [CONCERN] `parse_since` and the clock are presented as existing shared pieces, but 224 doesn't define them

227 names `parse_since` as "224's rule". It says the function "moves to `operations/since.py`" if it lives in `decisions.py`, and that `decisions` then imports it from there.
- **No named function in 224:** 224's design states the `since` rule (line 207) but never names a function or module for it.
- **Conditional refactor:** the design therefore leaves a refactor of another slice's code open (the `since.py` move, and `decisions` importing from it). Whether that refactor happens depends on how 224 gets implemented. That is under-specification and a hidden dependency.
- **Possible duplicate clock:** step 1 of the implementation order builds "the clock" in `store/releases.py`. It is unclear whether this duplicates a clock that 223 and 224 already inject through `deps`.

Fix: make the dependency explicit. Either 224 owns a named, public `since` helper that 227 imports, or 227 creates `operations/since.py` and states that 224 is retrofitted to it. State the same for the clock, which should be reused from `deps` and not rebuilt.

### [CONCERN] D2 and D7 are heavier than the cases the slice needs

D2 is a six-row state machine with two rejection codes, `version_conflict` and `version_on_other_commit`. The slice itself calls these cases "rare" and says they are fixed "by hand in SQLite". It adds a `StrEnum` of outcome codes and a test per row, each asserting "no other row changed". D7 also adds a two-process concurrency test for behavior that `BEGIN IMMEDIATE` already guarantees.

The architecture requires only that repeats change nothing and that a later tag on a reported commit adds the version.

Candidates to cut or defer:
- Collapse the two conflict rejections into one `version_conflict` code.
- Drop the two-process concurrency test in favor of a single-process, two-transaction test.
- Fold "replaces `changed` and `touched`" into the same table row as `versioned`.

None of this blocks the slice, but the size should be justified or reduced.

### [NOTE] "Never sees fewer" in D4 overstates, and one window of reports is never shown

`since` is the committer time of the last merge on the consumer's branch. This matches the architecture's "usually its branch's last merge".

- **Overstated claim:** D4 says it "never sees fewer than the reports made since its last merge". A rebase or cherry-pick moves `%cI` later. `git log -1 --merges` also picks the nearest merge reachable from HEAD, not the latest by time.
- **Unseen window:** a provider report made after a consumer's slice design but before that slice's merge falls before the next design's `since`. It is never shown, and it is not marked anywhere as missed.

The architecture accepts the soft starting point, so this isn't blocking. The doc should soften the claim and name the window as known. Any pipeline step added via `#304` would inherit it.

### [NOTE] Common release flow may yield two reports for one change

D2's "adds the version" path only fires when the tag lands on the exact commit that was reported at merge. If a release flow adds a version-bump commit, `git rev-list -n 1 <tag>` is a new commit. The result is a second report with its own text. A `from_source` consumer sees both entries, and the `from_release` consumer sees only the release one. This is consistent with the architecture and probably acceptable. The walkthrough and `docs/program-rules.md` should say that the repeat-suppression only applies when the tag is on the reported commit.

### [NOTE] 226's stdio test needs a coordinated edit

226 says a new operation needs "no test changes", but its stdio test asserts a literal six tools. 227 changes that assertion to follow `OperationName`, and its walkthrough expects eight tools. The design is correct as written. 226's wording could say the stdio count is derived from the enum, so the two docs agree.

### [PASS] Failure modes and restart-safety are covered

Each new I/O path has an explicit outcome:
- **Malformed input:** `rejected / malformed`.
- **Non-member:** `rejected / not_a_member`.
- **`cf`, config and store failures:** exit 3.
- **Concurrency:** concurrent writers serialize under `BEGIN IMMEDIATE`, with `UNIQUE` as the backstop.
- **Atomic writes:** one transaction per `report_release`, so a process killed mid-call leaves either the old or the new state. This matches the "short-lived and restart-safe" principle.

The architecture states no numeric NFRs for this path, so none need restating.

### Run Digest

- Response length: 7521 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 527482 / 409577 / 117893 / 8442 / not computed
- Duration: 69.8 s
- Cost: $0.60 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
