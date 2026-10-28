---
docType: review
layer: project
reviewType: slice
slice: pipeline-supervisor
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/132-slice.pipeline-supervisor.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261028
dateUpdated: 20261028
reviewedSha: c4c99e490cc05b03ead5f5460d15b331376dd24c
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 114140
cachedTokens: 11220
cacheWriteTokens: 102916
completionTokens: 8555
durationSeconds: 76.9
costUsd: 0.49915
costBasis: provider
runId: run-20261028-p4-86ec9636
squadronVersion: 0.24.8
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Supervisor cut matches the Direction Change"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#Overview"
  - id: F002
    severity: concern
    category: layer-boundaries
    summary: "Store contract change is made inside the Runner slice, and the success criteria contradict it"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md:219"
  - id: F003
    severity: concern
    category: under-specification
    summary: "The auto-resume bound is not \"consecutive\", and it undercuts the stated value"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md:228-229"
  - id: F004
    severity: concern
    category: architectural-invariants
    summary: "The \"never merge to `main` under an integration branch\" invariant is delegated to Squadron without confirmation"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md:500"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Resume failure modes are only partly enumerated"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md:88,232-233,251"
  - id: F006
    severity: concern
    category: risk-handling
    summary: "The implement-step gap lets the Runner advance past unfinished work"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md:301,482"
  - id: F007
    severity: note
    category: architecture-alignment
    summary: "Checkout-hold rule is widened beyond the arch text"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md:196"
  - id: F008
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable"
    location: "project-documents/user/slices/132-slice.pipeline-supervisor.md#Technical-Decisions"
---

# Review: slice — slice 132

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Supervisor cut matches the Direction Change

The slice implements each item the arch's Direction Change lists:
- One configured-pipeline launch per slice.
- "Completed → done; resumable → resume; question → 140; anything else → blocked."
- No `cf_write`.
- No CF gate reads, hatches or merge policy.
- Resolutions cut to `resume` and `stop`.
- Config cut to a pipeline and its params.
- The clean-tree check kept.

The kept pieces (tenant, tick budget, fault isolation, detached launch, journal, probes) match the arch's "What stands" list. Dependency direction is sound:
- `supervise.py` is pure.
- The predecessor function stays the single point for 180's cross-project edges (D1).
- 140 and 160 consume a stable block payload and a two-value resolution vocabulary.

### [CONCERN] Store contract change is made inside the Runner slice, and the success criteria contradict it

D4 adds an "atomic completion" option to 100's `Store` ingestion write. The arch says the Runner "writes through 100's public API only" and that contract changes "land as their own slice ahead of the Runner" (arch, "Contract changes the Runner needs from 100"). The Migration Plan makes it the first task, which softens this. But Success Criteria (line 446) still require "100's contract suite unchanged", while step 3 adds a contract-suite test.

Cut one of two things:
- **Option A:** state that this is a deliberate, additive exception to the arch rule, and reword line 446 to "existing tests unchanged".
- **Option B:** use the lighter alternative. Mark the slice `done` first, then resolve the entry. A crash between the two leaves a `done` slice with an unresolved entry, which recovery and 121's terminal-`done` rule can absorb. That needs no store change.

### [CONCERN] The auto-resume bound is not "consecutive", and it undercuts the stated value

The text calls the limit "consecutive automatic resumes". The count is every transient resume since the last fresh launch or PM `resume`. Nothing resets it when the run makes progress. Each wait for `resets_at` also counts (line 229). A multi-hour `p456` run that hits a usage-limit window or a provider error across its three phases will exhaust the default of 3. It then lands in front of the PM as `auto_resume_exhausted`, although Value (line 50) says usage-limit pauses "no longer reach the PM."

Either:
- reset the count when a resumed run advances past the `updated_at` or step it was resumed from, which D5's confirmation logic already reads; or
- rename it a per-run total and drop the usage-limit claim from Value.

### [CONCERN] The "never merge to `main` under an integration branch" invariant is delegated to Squadron without confirmation

The arch's merge-policy section states "Never, under any policy… nothing merges to `main` when an integration branch is set" as a Runner guarantee. The slice moves it to "enforced by Squadron's merge step, not by Amoeba" (line 500) and allows user pipelines such as `p4567` that merge. D9 says every delete is "confirmed one by one against Squadron", but the table's merge row (line 285) says only "a merging pipeline, or the PM". It has no confirmation that Squadron's merge refuses `main` when an integration branch is configured. The Runner's own git reads (`target`, branch rules in D3) are the only place it could check.

Add a D9 row backed by a cited Squadron behavior. Alternatively, keep a pre-dispatch check that the project's pipeline target is not `main` when `git.integration_branch` is set.

### [CONCERN] Resume failure modes are only partly enumerated

D5 turns `sq run --resume` into an automatic action that fires every tick a candidate exists. The slice records that Squadron refuses to resume a run still live under its process (`_refuse_live_run`, line 88). An `orphaned` classification can be wrong when the process is slow, not dead. D5 and D6 say nothing about what happens to that refusal. They cover only:
- the run missing,
- exit 2,
- a resume that never takes.

State which path a live-run refusal takes. For example, treat it as `StillResuming` or re-observe, and say that it must not count toward the bound or block the slice.

### [CONCERN] The implement-step gap lets the Runner advance past unfinished work

Until Squadron ships its Unreleased fix, an `agent_question` from an implement step ends in `completed`. The Runner marks the slice `done` and launches its successor. The slice itself calls this "the one path where the Runner advances past unfinished work" and lists `p456` among the exposed pipelines, which is the primary use case. The arch's rule is that every in-run residue point (questions, "a task the agent marked blocked for a person") is blocked, not advanced past. The slice also does not map the "task marked blocked for a person" input from the arch's Technical Considerations at all.

The design needs a mitigation, not just a note. For example, make the Squadron release a prerequisite for configuring any implement-containing pipeline, or fail the config load for one until `sq` reports the fix. Otherwise state that the arch's blocked-task input is out of scope and why.

### [NOTE] Checkout-hold rule is widened beyond the arch text

The slice holds a checkout for `paused`, `failed` and `orphaned` runs, including blocked slices at `auto_resume_exhausted` or stopped. The arch says "until its run is no longer running or paused" and lists concurrency per checkout under "What stands". The slice flags the divergence and defers the arch edit to #22. The reasoning is sound, since a failed or orphaned run still leaves work in the checkout. Until #22 lands, the two documents disagree.

### [NOTE] Proportionality is acceptable

The slice is mostly deletion. New mechanisms are small and each has a stated reason:
- `supervise.py`
- `auto_resume_limit`
- `resume_cause`
- the cross-project blocked list

Reading `resets_at` goes beyond the plan entry's transient list. The slice says so and edits the plan entry. Deferring multi-review recording and retiring the routing store API is appropriate, since neither is required by the arch's direction.

### Run Digest

- Response length: 7022 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 114140 / 11220 / 102916 / 8555 / not computed
- Duration: 76.9 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
