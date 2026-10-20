---
docType: review
layer: project
reviewType: arch
slice: runner-routing-engine
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/architecture/120-arch.runner-routing-engine.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 578d24458835b50d66e7ce82facf2b33cc3928ce
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 244117
cachedTokens: 148678
cacheWriteTokens: 95431
completionTokens: 18162
durationSeconds: 88.7
costUsd: 0.030325
costBasis: provider
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: fail
    category: consistency
    summary: "Intent precedence rules contradict each other"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F002
    severity: fail
    category: feasibility
    summary: "The tick-deadline bound is not what the design delivers"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F003
    severity: concern
    category: consistency
    summary: "The launch-confirmation design parses Squadron prose, which the document forbids"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F004
    severity: concern
    category: technology
    summary: "The start-up shape probe has no specified mechanism and conflicts with the no-prose rule"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F005
    severity: concern
    category: feasibility
    summary: "Launch-failure inference by grace period can race with a late launch"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F006
    severity: concern
    category: feasibility
    summary: "Every observation is recorded, which implies unbounded write volume with no cadence or retention"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F007
    severity: concern
    category: completeness
    summary: "Ingestion of \"every review artifact\" for a completed run has no source in the outcome contract"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F008
    severity: concern
    category: consistency
    summary: "Human \"accept\" of a CF-gated outcome has no defined CF-side effect"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F009
    severity: concern
    category: completeness
    summary: "Lifecycle node sourcing covers slices but not initiatives"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
  - id: F010
    severity: concern
    category: consistency
    summary: "Acknowledgment idempotency conflicts with the existing store contract"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F011
    severity: concern
    category: dependencies
    summary: "Dependencies on unreleased Squadron surfaces are not gated in the slice order"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#anticipated-slices"
  - id: F012
    severity: concern
    category: completeness
    summary: "Fault escalation for faults with no node is deferred to slice design"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#architectural-principles"
  - id: F013
    severity: concern
    category: completeness
    summary: "The routing table's format and every threshold are deferred, which undermines the \"one edit point\" goal"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#what-the-routing-table-matches-on"
  - id: F014
    severity: concern
    category: consistency
    summary: "Inferred tier is listed as a routing input before tier inference exists"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#the-routing-engine"
  - id: F015
    severity: concern
    category: antipattern
    summary: "Scope and proportionality: the lifecycle, intent, and decision machinery exceed the first proof"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#scope"
  - id: F016
    severity: note
    category: consistency
    summary: "`REVIEW_PRODUCING_KINDS` already contains `sq_run`"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#technical-considerations"
  - id: F017
    severity: note
    category: completeness
    summary: "CF failure snapshots also emit `cf_project_changed`, which the reconcile rule does not account for"
    location: "project-documents/user/architecture/120-arch.runner-routing-engine.md#envisioned-state"
---

# Review: arch — initiative 120

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Intent precedence rules contradict each other

The "Intent is a closed, declarative command set" bullet (line 148) states three precedence rules that cannot all hold:
1. "The nearest intent on its path" governs a node.
2. "A narrow intent overrides a broad one for its subtree regardless of arrival order," with the exception that "held true on any ancestor holds the whole subtree."
3. "For one target, the later intent … replaces the earlier."

Under rule 2's exception, a `resume` (held false) on a slice is overridden by a `pause` (held true) on its project, so the PM cannot resume one slice without clearing the project-level pause. The document has no "clear" or "unset" intent, so the only way out is to rewrite the broad intent. Rules 1 and 2 also disagree whenever an ancestor is held true. The vocabulary also never defines "held" separately from "driven," so the two intent dimensions are unclear. This is the contract 160 will translate natural language into, so it must be settled before 160 starts. Pick one precedence rule, define the clear operation, and state a single example that resolves.

### [FAIL] The tick-deadline bound is not what the design delivers

Line 47 says "worst-case tick length is bounded by the deadline, not by projects × calls × timeout," and that projects not reached "go first on the next tick." But the deadline is only checked between projects. Observe for one project reads its CF status, its slice list, `git status` for every checkout its nodes use, and `sq runs wait --timeout 0` for every in-flight run. Each call can take up to its per-call timeout. One project with five in-flight runs and three checkouts, all timing out, can overrun the deadline by eight timeouts. The "tenant obligation" is described as binding, so the bound has to hold. Either check the deadline before every subprocess call (and state how a partially observed project resumes), or drop the claim and state the actual worst case.

### [CONCERN] The launch-confirmation design parses Squadron prose, which the document forbids

Principle 51 says outcomes come "from the contract, not the conversation… never from stdout prose." Lines 126 and 124 then have the Runner grep the per-run log file for a `run_id=<id>` line. That line is Squadron's stderr prose, and the document itself says `sq run` has no JSON output. Either make it a supported surface (for example, a `sq runs wait --json` not-found shape that distinguishes "launching" from "unknown," or a `--json` launch result), or name this as a deliberate exception to principle 51 and give the line format a pinned contract.

### [CONCERN] The start-up shape probe has no specified mechanism and conflicts with the no-prose rule

Line 53 says `sq run --run-id`, `--decision`, `sq runs wait --json`, `cf status --json`, and `cf list slices --json` are "probed once at start from the tools themselves." It does not say how. Probing `sq run --run-id` by reading `--help` is prose parsing. Probing `sq runs wait --json` needs a run id and produces a side-effect-free not-found shape, which the doc never mentions. Probing `--decision` on a plain resume would need a real run. Specify each probe: the command, the input, and the output that counts as passing.

### [CONCERN] Launch-failure inference by grace period can race with a late launch

Line 126 says that after a restart, an entry whose id "still has no run state once the launch grace period has passed never started," and recovery marks it `not_applied` and may reissue it under the same id. A slow launch can create run state after the grace period. The reissue is then refused as "taken id," and the entry ends in an inconsistent state: `not_applied` in the journal, a live run on disk. The doc gives no rule for adopting a run whose id is taken during a reissue. Add one: a refused reissue of a taken id is adoption, not failure. The grace period is also a wall-clock input to recovery, and it is not in any table or setting.

### [CONCERN] Every observation is recorded, which implies unbounded write volume with no cadence or retention

Line 45 requires that "each read is recorded (in the store, or in the decision record that uses it) before Decide runs." Each tick polls every in-flight run, `git status` for every checkout, and CF status for every runnable project. Line 146 adds a check record per Tier-1 check per tick. The tick interval is never given. `cf_watch` already polls at 1 Hz (CHANGELOG slice 108), so an unspecified cadence multiplied by per-tick recording could grow the store without bound. The doc needs a tick period, a rule that records observations only when they change or when a decision uses them, and a retention statement for decision and check records.

### [CONCERN] Ingestion of "every review artifact" for a completed run has no source in the outcome contract

Line 97 says a finished run ingests "every review artifact it wrote." Line 128 gives a paused run's checkpoint with only "the review file behind that verdict" (the last one). The `--json` fields listed for a completed run (line 127) are only `outcome` and `status`. Nothing says how the Runner learns the full artifact list of a completed P6 run with several review rounds. Without that, `finding_changes` (which needs the previous round) and recurrence (`new`/`recurring`/`gone`) cannot be computed from a completed run. Either add an artifact list to S10's outcome or derive it from the attribution rule against the slice's review directory, and say which.

### [CONCERN] Human "accept" of a CF-gated outcome has no defined CF-side effect

Line 112 says that accepting an escalated completed outcome means "advance," and line 99 says "advance (mark done, make the next node runnable)." Line 142 says gates come from CF's `gateInfo`, which the Runner does not write. When the CF gate requires PASS, a store node marked done while CF's gate still reads blocked gives two systems that disagree about the same slice. The doc says the Runner "never writes `review: none`," but says nothing about how a human acceptance reaches CF. Specify whether a PM accept writes a CF review or decision, or whether the store's "done" is explicitly not CF's view, and what reconciliation does with the mismatch.

### [CONCERN] Lifecycle node sourcing covers slices but not initiatives

Line 75 says initiatives and slices are projected from `cf list slices --json` and `cf status --json`, and the step map (lines 79–85) puts P2, P3, and P7 at initiative level. `cf list slices --json` lists slices, not initiatives. The doc never says where initiative nodes come from or when they are created. It also says the Runner "parses no plan documents," then allows frontmatter reads for the ungate checks. Name the CF field that reports initiatives, or state that initiative nodes are created by a specific, named rule.

### [CONCERN] Acknowledgment idempotency conflicts with the existing store contract

Line 148 requires that "applying an intent twice is the same as applying it once," and line 150 asks for an acknowledgment outcome (applied, no-op, rejected) that the submitter can read. The current `acknowledge_message` raises `InvalidTransitionError` on an already-acknowledged message (store-contract line 375; `tests/store/test_messages.py:187`). Changing that is a contract break that the doc lists only as one bullet among several. Name the breaking change, its callers, and the test that moves.

### [CONCERN] Dependencies on unreleased Squadron surfaces are not gated in the slice order

Line 69 says S9–S12 are on Squadron's main but not released. Line 53 says the Runner refuses to start without `sq run --run-id`, `--decision`, `sq runs wait --json`, and `cf status --json`. Line 124 says the recovery observer moves to `sq runs wait --json`. The anticipated slices (lines 160–167) have no release gate. As written, the "Substrate changes" slice can merge and the Runner tenant can be built, but nothing runs until a Squadron patch ships. Add an explicit gate before the Runner tenant slice, and say what the substrate slice does until then.

### [CONCERN] Fault escalation for faults with no node is deferred to slice design

Line 49 says a fault with no node "must still reach the PM, with at most one open escalation per project and fault kind," and that slice design decides what it attaches to. The store has no project-level blocked state, and "one open blocked state per node" (same line) does not cover this case. The no-storm guarantee and the "must still reach the PM" guarantee both depend on a storage location the doc leaves open. Decide it here, or name the attachment point (for example, a project-scoped escalation message with a dedupe key).

### [CONCERN] The routing table's format and every threshold are deferred, which undermines the "one edit point" goal

Design goal line 39 says the table is the single place routing behavior lives, and line 144 defers "the table format, and where it lives." The attempt limit, the per-pipeline time bound (line 126), the launch grace period, the tick deadline, and the per-call timeout are all table or settings values with no owner. The design relies on the table's format to define what a rule can match and how thresholds are versioned (line 55). Deferring the format to slice design leaves the most load-bearing decision of the component open. State at least the match grammar and which settings are table values versus config values.

### [CONCERN] Inferred tier is listed as a routing input before tier inference exists

Line 99 lists "each finding's inferred tier" among the routing inputs. Line 101 says tier inference ships after the first proof, and line 164 says the first table "routes on recorded evidence only, with no tier inference yet." Line 144's closed input list also includes "inferred tier." These cannot all be true for the first table. Remove tier from the v1 input list and mark it as a post-proof input, or state that v1 treats every finding as Tier 2, which is what line 101 implies.

### [CONCERN] Scope and proportionality: the lifecycle, intent, and decision machinery exceed the first proof

The first proof is one project and one unit. Yet the design includes a three-level intent hierarchy (project, initiative, slice) with ancestor lookup and per-node desired-state tables, a stored full copy of each table version, judge-eligible marks for a judge that does not exist, checks as a separate record type with two v1 checks, and a per-project merge-policy config. Cut or defer for v1:
- Intent targets: slice and project only. Initiative-level intents and ancestor lookup wait for multi-slice use.
- Table versioning: store the table's content hash and a version tag. Keep the full text in version control.
- Judge-eligible marks: add the field when 140 lands, since it is a table edit.
- Merge policy: a single config value defaulting to human, not a per-project mechanism.

Each cut removes an invariant the design currently has to keep true.

### [NOTE] `REVIEW_PRODUCING_KINDS` already contains `sq_run`

Line 150 asks to "register the Runner's review-producing `sq_run` use in `REVIEW_PRODUCING_KINDS`." `src/amoeba/store/journal_models.py:81` already defines `REVIEW_PRODUCING_KINDS = {SQ_RUN}`. The real change is the run-id key and the observer. Reword the bullet so it does not suggest a registration step that already exists.

### [NOTE] CF failure snapshots also emit `cf_project_changed`, which the reconcile rule does not account for

Line 89 says reconciliation "runs whenever a `cf_project_changed` entry arrives." `docs/feed-contract.md:79` says such an entry is emitted for every snapshot, including failures, whose `changed` is null. Reconciliation should run only on successful, changed snapshots. State that filter here, or the Runner will reconcile on every failed read.

### Run Digest

- Response length: 14793 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 244117 / 148678 / 95431 / 18162 / not computed
- Duration: 88.7 s
- Cost: $0.03 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17
