---
docType: review
layer: project
reviewType: slice
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: b0f76d5e3ce48e60230002501723af46fa88d03b
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Scope and exclusions match the architecture's assigned boundaries exactly"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:15-57"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Dependency direction and writer model conform to the sole-writer architecture"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:119-124"
  - id: F003
    severity: pass
    category: architectural-principles
    summary: "Provenance and \"unknown is a value\" principles are carried through, not just cited"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:223-240"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Failure modes on the new I/O paths are enumerated with explicit exits; no TBDs"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:271-278"
  - id: F005
    severity: pass
    category: integration-points
    summary: "Consumed and provided interfaces match the sibling slices as written"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:59-92"
  - id: F006
    severity: concern
    category: error-handling
    summary: "A verdict submission naming a nonexistent project ends in quarantine — a terminal state D6's read-back surfaces never show"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:261"
  - id: F007
    severity: note
    category: data-quality
    summary: "The D5 cross-source double-record consequence is accepted with adequate containment"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:242-259"
  - id: F008
    severity: note
    category: robustness
    summary: "Walkthrough setup drops 104's documented startup-wait and isolation caveats"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:376-387"
  - id: F009
    severity: note
    category: nfr
    summary: "No parent NFR required restatement; the one applicable property is carried through"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:371-374"
---

# Review: slice — slice 108

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Scope and exclusions match the architecture's assigned boundaries exactly

The architecture reserves to this component only "parsing of Squadron **review output** … as an adapter outside the store" and explicitly excludes "parsing of other SQ output or of CF MCP results (the Runner's control surface, initiative 120)." The slice's D1 states the same placement and the same "review output only" limit, and its Excluded list maps every adjacent concern to its owner: run files stay in `process/observers/sq_runs.py`, CF MCP parsing is 120's, detection is 105's, judge samples are 109's. Nothing reaches beyond the assigned scope; the additions it does make (`verdict_to_payload`, `provider_failure_problem`) are justified by the one integration point it owns (submit requires a payload dict) and are gated on 104's behavior-preservation tests.

### [PASS] Dependency direction and writer model conform to the sole-writer architecture

`upstream` imports only store vocabularies and dataclasses, never `Store`, `amoeba.inbox`, or `amoeba.process`; the store never imports `upstream`; and `cli/ingest.py` is the only module knowing both parser and inbox. This matches the architecture's writer model — the inbox is "the one surface that parts *outside* the resident process write to directly" — and the slice goes further than most by requiring a test that asserts both import prohibitions (Technical Requirements, :357). Ingest composing `VerdictInput` and submitting a payload through 103 rather than opening the store is exactly right.

### [PASS] Provenance and "unknown is a value" principles are carried through, not just cited

D3's "Nothing is defaulted" list raises `SquadronParseError` naming key and source for every missing/contradictory required field — the architecture's "the store never fills a gap with a plausible default," enforced at the earliest layer. D4 implements the architecture's "Every ingested record stores the upstream version it was parsed from" (Schema versioning against unversioned upstreams) and adds the disagreement check the principle implies. D3's provenance mappings (`source`, `fallback_used`, provider-failure flag, `sq_run_id`) are a direct instance of "Provenance on every ingested fact," and positional finding ids stay data-only per "Identity is content-based."

### [PASS] Failure modes on the new I/O paths are enumerated with explicit exits; no TBDs

The new I/O is local file read plus one inbox submission — no network, so hang/timeout/peer-disconnect modes do not arise, and the modes that do exist are each mapped: `OSError`/`UnicodeDecodeError` → exit 12, `SquadronParseError` → 12, `UpstreamVersionError` → 12, `InboxSubmitError` → 9, with "nothing reaches `inbox/new/`" at each failing step (consistent with 103's contract that `submit()` leaves nothing behind on failure). I verified `SUBMISSION_REFUSED = 9` already exists in the shipped boundary handler and that 12 is unassigned. The explicit refusal to catch bare `ValueError` (so bugs still reach the boundary handler as `FAILURE`) follows the project exception rules.

### [PASS] Consumed and provided interfaces match the sibling slices as written

Verified against the referenced documents and the repository: 104's design confirms the PyYAML dev→runtime hand-off verbatim, that callers pass parsed values and the record id is the submission id, and the shipped store package really contains the `verdict_from_payload`/payload-key surface the inverse function targets; the four named `review_fixtures.py` users are exactly the four modules importing it; 105's design asks for precisely `ParsedReview.slice`, `source_document`, the parsed-content digest id, `SquadronParseError` details, and `ingest review --node` recovery — all provided; 106's required imports (:69) match the Provides list name for name. The `dependencies: [101, 103, 104]` correction of the plan's dependency list is flagged honestly in the Prerequisites section.

### [CONCERN] A verdict submission naming a nonexistent project ends in quarantine — a terminal state D6's read-back surfaces never show

The slice enumerates the wrong-node case (Excluded: "An unknown node shows up as a `rejected` submission, which the PM sees in `inspect submissions`") — correct, since 104's writer checks node existence inside the apply transaction. But it never enumerates the wrong-**project** case, and it terminates differently: per 103, a submission that cannot be attributed to an open project store is *quarantined* as `no_store_for_project` because "there is no store row to write" — it never becomes a submission record. `submit()` cannot catch it (only id *format* is validated at submit time; existence is apply-time), so the run exits `OK` and prints an id, and D6's stated outcome surfaces — `inspect submissions` and `inspect verdicts` — both show nothing. Only `inspect inbox` (quarantined listing) reveals what happened, and the slice's "A failing run prints the error on stderr" claim doesn't hold here because this isn't a failing run. This is precisely the kind of per-message-type failure mode the design should name. D6's submit-and-don't-wait stance is right, so the fix is documentation and test coverage, not a read-back: state in D6/Excluded that a nonexistent `--project` quarantines silently, name `inspect inbox` as the surface, and add a success-criteria case for it. Note the adjacent risk is real for a PM tool: `ingest review` is documented as the backfill path for pre-registration reviews (105), i.e., often run against directories/projects in flux.

### [NOTE] The D5 cross-source double-record consequence is accepted with adequate containment

File-vs-stdout captures of one review get different ids and, if both are ingested, produce doubled `times_seen` and spurious "recurring against itself" rows. The design documents the mechanism, the visible effects, the reason no cross-source key exists in Squadron, and a concrete caller rule ("ingest a review's file, not its stdout"), and 105's D5 independently forces the Runner and detection onto the file path. Accepted-and-documented is the right call at this layer; the residue is a counting artifact in a debugging store, not a correctness problem.

### [NOTE] Walkthrough setup drops 104's documented startup-wait and isolation caveats

104's walkthrough (marked "Run by hand … output below is real") found two things necessary that this draft omits: a `until amoeba status | grep running` wait before `stop`/`demo_evidence.py` (without it, `stop` can exit `NOT_RUNNING` against an initializing process and the later steps interleave with `ALREADY_RUNNING`), and `--sq-runs-dir "$(mktemp -d)"` so `amoeba start`'s recovery doesn't read the real `~/.config/squadron/runs`. The slice labels the walkthrough "Draft; refined with captured output when Phase 6 completes," so this is informational — carry the two caveats forward when it is refined.

### [NOTE] No parent NFR required restatement; the one applicable property is carried through

The parent architecture states no numeric latency/throughput targets, so there is no NFR to restate. The one qualitative path property it does state — inbox submissions "land durably and are applied on restart" when the process is down — is exercised here by the Integration Requirements ("Ingest works with the process stopped. The submission is applied at the next start") and the `kill -9`/`start` end-to-end test, inheriting 103's fsync contract rather than restating numbers it does not own.

### Run Digest

- Response length: 9800 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 1
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 42344
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
