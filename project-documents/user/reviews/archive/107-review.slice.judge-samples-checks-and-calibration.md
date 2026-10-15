---
docType: review
layer: project
reviewType: slice
slice: judge-samples-checks-and-calibration
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 29658d4520c3eea41c132c02effbc14f59dd8808
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 95705
cachedTokens: 8746
cacheWriteTokens: 86955
completionTokens: 5482
durationSeconds: 46.2
costUsd: 0.404191
costBasis: provider
runId: run-20261015-slices-plan-fa1ba72e
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: architectural-alignment
    summary: "Calibration report cannot honour the \"escalated-gate verdicts are inadmissible\" constraint"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:58"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Progress records and the check/progress inbox kinds are heavier than a no-consumer table needs"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:222-224"
  - id: F003
    severity: concern
    category: architectural-alignment
    summary: "D4 refuses instead of recording unknown, and the refusal message is wrong for one case it catches"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:202-206"
  - id: F004
    severity: concern
    category: error-handling
    summary: "D2 and D8 tighten shipped slice 104 behaviour, and the ordering of D2's check is under-specified"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:186"
  - id: F005
    severity: note
    category: scope
    summary: "Consensus and \"recommendations\" are deferred to 140, which narrows the architecture's wording"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:56"
  - id: F006
    severity: note
    category: design-quality
    summary: "One enum serves two vocabularies"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:226"
  - id: F007
    severity: pass
    category: architectural-alignment
    summary: "Layering, dependency direction, and closed vocabularies are respected"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md#Architecture"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes for the new inbox kinds and the migration are enumerated"
    location: "project-documents/user/slices/107-slice.judge-samples-checks-and-calibration.md:240"
---

# Review: slice — slice 107

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Calibration report cannot honour the "escalated-gate verdicts are inadmissible" constraint

The architecture lists this constraint as permanent: "escalated-gate verdicts are inadmissible as agreement data". It also says the store exposes calibration evidence as a report. The slice excludes the filter because "the store cannot tell which samples came from an escalated gate". It then says "140 applies that filter when it computes agreement."

140 can only apply a filter if the store records the attribute it filters on. Nothing in the design stores it. The `calibration` report (D3, lines 188-200) counts every judge sample, escalated or not, and publishes the counts as evidence. A consumer reading `split_invocations` or the verdict counts gets data the architecture calls inadmissible, with no way to exclude it.

Either:
- add the attribute (for example an opaque nullable `gate_context` or `escalated` field on the sample, supplied by the submitter), or
- say plainly in the contract and in `inspect calibration` output that the report is unfiltered, and name the slice that must add the attribute.

As written, the deferral leaves a hole that 140 cannot fill on its own.

### [CONCERN] Progress records and the check/progress inbox kinds are heavier than a no-consumer table needs

D6 says `task_progress` and `devlog` have "no home and no designed consumer", and their content is opaque JSON. The slice still builds this for them:
- a table,
- a `ProgressKind` enum,
- a payload model,
- a `SubmissionKind`,
- an effect,
- a `ChangeKind` and trigger,
- an `inspect progress` listing,
- a `submit progress` CLI flag set,
- three docs sections.

The architecture does assign the SQ 280 typed-artifact scope to this component, so dropping it entirely would be a different concern. But nothing reads these records. Opaque content with no consumer is an abstraction nothing uses yet. The architecture's own rule of resisting complexity applies.

Cut or defer:
- The `inspect progress` listing and the `progress_recorded` feed trigger, which have no reader.
- The inbox kind for `progress`, which could come with the first consumer. D7's argument (outside producers exist) holds for `check`, which the Runner and the PM depend on. It is much weaker for `devlog`.

Keep the table and `record_progress` if the slice plan insists on delivering the scope. Say which items the slice plan entry assigns to 107 so the cut does not drop assigned scope.

### [CONCERN] D4 refuses instead of recording unknown, and the refusal message is wrong for one case it catches

The architecture's principle is "Unknown is a value, not a default. Missing or unparseable input is recorded as explicitly unknown and surfaces as a blocked-state". D4 submits nothing for a stdout capture with `verdict: UNKNOWN` plus a score. Nothing in the store shows the attempt, and no blocked-state surfaces. The reasoning (don't store a wrong fact) is sound, but it departs from the principle and the slice does not acknowledge the departure. State it as a deliberate exception, or record the refusal in a way the Runner can see.

The same rule also catches the post-fix case of an out-of-range score. The message is fixed text: "from before squadron 0.21.9 carries no verdict; ingest the saved review file". For that case the message is false, and the saved file holds the same `UNKNOWN`. The operator is sent to a dead end. The message should either distinguish the two cases or not claim a version.

### [CONCERN] D2 and D8 tighten shipped slice 104 behaviour, and the ordering of D2's check is under-specified

D2 rejects a sample whose invocation already has samples on another node or review type. The data-flow sketch (lines 133-138) puts this check after 104's checks and before the insert. Two cases are left implicit:
- **A rejected first sample.** It leaves no invocation record, so the "earlier sample" that defines the invocation's node and review type is whichever sample arrived first. A mistyped first sample therefore fixes the wrong node, and every later correct sample is rejected. The design should say the PM's remedy is a new invocation id, and the contract doc should say so.
- **Silent no-op on retry.** The retry rule (line 230) makes ingesting the same file under a second invocation a silent no-op. The design counts this as "WARNING if content differs", but `judge_invocation_id` is excluded from the digest, so the id collides and the second invocation silently loses its sample. A judge asking for N samples may then get N−1 and see no error.

Name the handling for both: a rejection reason that points at the retry path, or include `judge_invocation_id` in the record id.

### [NOTE] Consensus and "recommendations" are deferred to 140, which narrows the architecture's wording

The architecture's Design Goals say the store "surfaces recommendations". The Envisioned State says "judge invocations record … the consensus result the Judge computed". The architecture's Scope says consensus aggregation and routing policy belong to 140. The slice reads the Scope clause as controlling. That is defensible, and nothing here writes to Squadron, so the metrology constraint holds, with a test asserting no reference to its directory or config key. Make sure the slice plan entry records that the consensus-result record and recommendations are 140's, so the architecture's two sentences are not read as unmet.

### [NOTE] One enum serves two vocabularies

`RecordSource` gains `command_output` and `document`, and `REVIEW_SOURCES` is then needed to stop verdicts from using them. One enum with a per-record-type allowlist works, but the allowlist is a second place that must change with the enum. A separate source type for checks and progress records would remove the guard. This is minor and only worth it if the guard is expected to grow.

### [PASS] Layering, dependency direction, and closed vocabularies are respected

- The store does not import pydantic. Payload models live under `inbox/`, and Squadron parsing stays in `upstream/squadron/`.
- The new tables are written only through the apply loop or the in-process Runner, which keeps the sole-writer model.
- `CheckOutcome`, `CheckStanding`, and `ProgressKind` are `StrEnum`s defined once.
- `name` and `baseline_ref` are explicitly opaque and never routed on.
- Standing and calibration are computed on read.
- The check record carries what was examined and a `baseline_ref`, which satisfies the architecture's "baseline, not absolute, health signals" consideration.
- `upstream_version` is stored and never compared, as the architecture's versioning consideration requires.

### [PASS] Failure modes for the new inbox kinds and the migration are enumerated

Each new write path has a stated handling:
- Direct calls raise `NodeNotFoundError` or `ValueError`.
- Inbox effects return a rejection reason.
- Unknown vocabulary words are quarantined.
- A retried id returns the existing record.
- The 6 → 7 upgrade and the feed invariant are covered by named tests.

The architecture states no latency or throughput NFR for these paths, so nothing needs restating.

### Run Digest

- Response length: 8457 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 95705 / 8746 / 86955 / 5482 / not computed
- Duration: 46.2 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
