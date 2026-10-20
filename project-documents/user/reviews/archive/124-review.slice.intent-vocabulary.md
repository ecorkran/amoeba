---
docType: review
layer: project
reviewType: slice
slice: intent-vocabulary
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/124-slice.intent-vocabulary.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 1711b8df0e47bed63cb46cac405a3c6230871ce7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 9
promptTokens: 411639
cachedTokens: 292023
cacheWriteTokens: 119606
completionTokens: 12343
durationSeconds: 101.7
costUsd: 0.631881
costBasis: provider
runId: run-20261020-slices-plan-31ea04a8
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Intent semantics match the arch, and the two departures are declared and propagated"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#D5 — Merging, normalization and no-op"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure handling for apply is enumerated, and crash safety is explicit"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md#D9 — Applying intents: one stage, store-only, before observe"
  - id: F003
    severity: concern
    category: integration
    summary: "The drive index is built after Observe, but the arch scopes Observe by drive"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md:117-146"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Some mechanism is heavier than this slice needs"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md:200, 206-209, 287, 329"
  - id: F005
    severity: concern
    category: layering
    summary: "The `desired-states` listing needs tree logic that the doc excludes elsewhere"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md:43, 245"
  - id: F006
    severity: note
    category: specification
    summary: "The closed vocabulary is counted inconsistently"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md:34, 164, 279"
  - id: F007
    severity: note
    category: error-handling
    summary: "A bug-induced fault in apply stalls the whole project tick, including Observe"
    location: "project-documents/user/slices/124-slice.intent-vocabulary.md:236-237, 405"
---

# Review: slice — slice 124

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Intent semantics match the arch, and the two departures are declared and propagated

Drive resolves from the nearest target and hold from any target on the path (D6). Orphan rows are dropped from the index. Apply and acknowledge share one transaction (D9), and nothing is replayed. The two departures are stated as departures: hold stored as `true` or unset, and no-op defined as "the settings would not change". Both are written into the arch's intent paragraph and plan entry 5. The arch text already carries the slice 124 D5 references. The plan's last criterion (production `HumanStepPlanner` plus the drive filter, linking escalates nothing) is covered by D8.

### [PASS] Failure handling for apply is enumerated, and crash safety is explicit

D9 covers three paths:
- A store failure exits the process, with the intent left pending and replayed once.
- A non-store exception goes to 122's single catch.
- Every body or target error is a rejection, never an exception (D3).

The crash-safety test injects a failure inside `acknowledge_message`. The doc also shows that the first two paths are the only ones that can stall a project.

### [CONCERN] The drive index is built after Observe, but the arch scopes Observe by drive

The arch says Observe reads CF status, checkout state and the like "for each project that an intent says to drive or that has a run in flight". The data flow here reads `desired_states(P)` in the decide stage, after observe. The index is also described as "read once per tick" and "never cached across ticks". The design then states that Observe is not filtered by hold, but it does not say who owns scoping by drive. As written, 125 cannot narrow its CF-status and git reads to driven projects, because the index doesn't exist yet when Observe runs. The arch's Observe scope would go unmet.

Either build the index right after the apply stage and expose it to Observe, or state in "Provides to Other Slices → 125" that Observe scoping is 125's and name the predicate it will use.

### [CONCERN] Some mechanism is heavier than this slice needs

Effort is 2/5 and the vocabulary is small, but three pieces can be cut or deferred:
- **The "already passed" reason (D5, line 200).** Acknowledging `applied` with "every step up to tasks under the target is done" means scanning step completion under the target. For an initiative target that is every slice. No criterion or consumer needs it, and the outcome is already `applied`. Keep the outcome and drop the computed reason, or defer it.
- **`drive_source` and `hold_sources` on `Governance` (D6, line 287).** Only tests assert on them (line 329), and no listing uses them (the effective-state listing is excluded). The pure functions can return `driven` and `held` until something consumes the sources.
- **The per-step `current_steps` guard and filter are both kept (D7).** This one is justified, since the guard is the single enforcement point for 125, 127 and 128.

### [CONCERN] The `desired-states` listing needs tree logic that the doc excludes elsewhere

The Excluded section rejects an effective-state listing because it "needs the tree and the step map inside inspection". D10's columns include `linked`, `kind`, `cf_index` and `title`. In 123, `is_linked` is a `LifecycleTree` computation, and it is false for any node with an unlinked ancestor. The `linked` column therefore pulls the same Runner-side tree into `amoeba/inspection`. The doc doesn't say how inspection gets this without depending on `amoeba.runner.lifecycle`.

Either drop `linked` and the node-derived columns, leaving `target`, `drive`, `until`, `hold`, `message_id` and `updated_at`, or say how inspection computes `linked` without importing Runner code. Adding `cf_index`, `title` and `kind` to the existing `inspect nodes` listing would also work.

### [NOTE] The closed vocabulary is counted inconsistently

The overview says "six closed forms" and D1 says `IntentKind` has "these six values". The list and the API contract show five kinds: drive, exclude, pause, resume and clear. The six is the number of table rows, because drive appears twice. 160's whitelist is defined as a subset of `IntentKind`, so the count should be exact. Fix the wording to "five kinds, six body forms".

### [NOTE] A bug-induced fault in apply stalls the whole project tick, including Observe

The arch says a fault leaves the observation of in-flight runs running. Here an unexpected exception in apply skips the rest of that project's tick, and the failing intent is retried first on every tick. Ingestion for that project and its checkout release then wait until the bug is fixed. The doc accepts this (Special Considerations) because only a code bug can cause it, and the escalation is deduplicated. That is consistent with 122's single catch. If the first proof shows it matters, applying intents under their own per-intent fault scope would remove the stall.

There is also no cap on intents applied per tick. This is fine for store-only writes, and the arch's tick-deadline NFR is about subprocess calls, so no new target is needed.

### Run Digest

- Response length: 6492 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 411639 / 292023 / 119606 / 12343 / not computed
- Duration: 101.7 s
- Cost: $0.63 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
