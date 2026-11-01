---
docType: review
layer: project
reviewType: arch
slice: question-answerer
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/architecture/140-arch.question-answerer.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261031
dateUpdated: 20261031
reviewedSha: 2f5096c879dda9e68bcebbf9e411d46edaf7da4c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 321644
cachedTokens: 243864
cacheWriteTokens: 77770
completionTokens: 8792
durationSeconds: 103.4
costUsd: 0.84762
costBasis: provider
squadronVersion: 0.24.10
findings:
  - id: F001
    severity: fail
    category: consistency
    summary: "Nobody is clearly responsible for launching the answering run"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F002
    severity: fail
    category: feasibility
    summary: "The grounding check proves a quote exists, not that it supports the answer"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#architectural-principles"
  - id: F003
    severity: fail
    category: consistency
    summary: "The exact-repeat path skips the bounds and PM-reserved checks"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F004
    severity: concern
    category: dependencies
    summary: "The answering slice ships before the bounds that make it safe"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#anticipated-slices"
  - id: F005
    severity: concern
    category: completeness
    summary: "Matching is too loose: answers to one slice get reused for another, and stale precedent is never retired"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F006
    severity: concern
    category: completeness
    summary: "Who writes the decline block, and how a question moves from the answerer's block to the PM's, is unresolved"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F007
    severity: concern
    category: feasibility
    summary: "Reading \"committed state\" outside the checkout is not designed"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F008
    severity: concern
    category: completeness
    summary: "What happens when the answering run itself fails is not addressed"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
  - id: F009
    severity: concern
    category: dependencies
    summary: "A Squadron change is a hard dependency but no slice owns it"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#technical-considerations"
  - id: F010
    severity: concern
    category: feasibility
    summary: "The 400-character question tail is a weak input for answering and matching"
    location: "project-documents/user/architecture/140-arch.question-answerer.md:101-103"
  - id: F011
    severity: note
    category: completeness
    summary: "Existing questions and answers in the journal are not backfilled"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#current-state"
  - id: F012
    severity: note
    category: completeness
    summary: "Tick order and budget for the second tenant are not specified"
    location: "project-documents/user/architecture/140-arch.question-answerer.md#envisioned-state"
---

# Review: arch — initiative 140

**Verdict:** FAIL
**Model:** claude-opus-5-5

## Findings

### [FAIL] Nobody is clearly responsible for launching the answering run

The document gives three statements about who runs the answering step, and they cannot all hold:
- **Architectural Principles (line 49):** the answering step "runs as Squadron work under the same journaled launch-and-observe surface as every other run". The "Answering run" slice (line 117) says it is "launching and observing it through the Runner's control surface".
- **Envisioned State (line 89):** the answerer "writes only two things: question records and resolutions". It also says "the Runner stays the only part of Amoeba that issues commands against a project's runs", and "the two communicate only through state".
- **Design Goals (line 41):** "The Runner's outcome map, journal, and control surface stay as 132 left them."

That leaves two options, and each breaks one of these statements:
- **The answerer calls the control surface itself.** Then a second tenant issues `sq` commands. That breaks "Runner is the only issuer" and "communicate only through state".
- **The Runner launches the answering run because a question record asks for it.** Then the Runner needs things it does not have today. It needs a new kind of launch that is not tied to a slice node or checkout. 132's launch path resolves a checkout per node and runs the pre-dispatch check (`checkout_dirty`/`checkout_branch`). It needs a journal entry kind for a run that belongs to no slice. It needs observe and recovery for that run, and outcome handling that is not 132's D4 map. That breaks "the supervisor does not change shape."

This choice decides the tenant boundary, crash recovery, and which slice owns what. Make it in the architecture, not in the slice design.

### [FAIL] The grounding check proves a quote exists, not that it supports the answer

Line 47 defines grounding as "the cited source exists and contains the cited passage". That checks that the passage was quoted correctly. It does not check whether the passage supports the answer. An answering run can quote any real line, such as a `CLAUDE.md` rule about commit messages, and attach any answer to it. The check will pass. The document then relies on this check to justify dropping N-way agreement (line 111: "the grounding check already carries the trust").

Two other choices make this worse:
- **Line 33 rules out a shadow mode.** The first answering slice therefore resumes real runs on this check alone, with no data on how often grounded answers are wrong.
- **Line 39 says the design "leans toward" declining.** But the only mechanical gate is one that a fluent model passes almost every time.

The document needs a real trust mechanism, or it should drop the no-shadow-mode goal. Possible mechanisms:
- the citation must come from a fixed set of passages that Amoeba supplied
- a separate check that the passage relates to the answer
- per-project trust that starts with PM confirmation and widens from measured agreement

### [FAIL] The exact-repeat path skips the bounds and PM-reserved checks

In Envisioned State, step 2 ("Repeat") submits a prior answer "at once". It does not pass through step 4 ("Check"), where the citations, the per-run limit, and the PM-reserved screen run. The slice plan makes this real. "Question record and handoff" ships exact-repeat reuse (line 115). The PM-reserved screen and the per-run limit come two slices later, in "Bounds" (line 119).

Concrete failure: the PM answers "yes, merge to main" for one slice. The same normalized question then arrives from another slice. It is resumed with that authorization, with no screen and no count against the per-run limit. This directly breaks the principle "What the PM reserves, the answerer declines … however well it could be grounded" (line 51), and the bound in line 53. Every path that issues a resolution must go through the bounds and the reserved-action screen. Bounds must ship no later than the first slice that issues a resolution.

### [CONCERN] The answering slice ships before the bounds that make it safe

The slices run in this order: Answering run (line 117), then Bounds (line 119). Line 33 says answering is live "from the first slice that ships an answering step" with no shadow mode. So between those two slices, the answerer auto-resumes runs with no per-run limit and no PM-reserved screen. A run that asks a question again after each answer then loops until `max_cost_usd`, run after run. 132's D6 says a `resume` with instructions resets the D5 auto-resume count, so 132's own bound will not stop the loop either. Merge Bounds into the answering slice, or put it before that slice.

### [CONCERN] Matching is too loose: answers to one slice get reused for another, and stale precedent is never retired

Line 101 says normalization should absorb differences in "slice names". For questions like "which branch?", the slice name is the substance of the question. A PM answer of "use `140-slice.foo`" that is reused for slice 141 is wrong, and the deterministic path treats it as certain.

The record also has no answer to three questions:
- **Stale precedent.** Prior answers never expire when the rules or plan they rested on change. Line 37 says "a PM's answer becomes precedent the moment it is given", but nothing says what happens when `CLAUDE.md` changes later.
- **Compounding errors.** The answerer's own answers become precedent (line 37), and they are also cited as sources (line 47). One wrong grounded answer then becomes the citation for later answers.
- **What counts as an answer.** A PM `resume` on a question block may carry instructions that do not answer it ("just continue"), or carry none. Line 87 records every PM resume as precedent without telling these apart.

The document needs to state:
- the scope of a precedent (project, initiative or slice)
- what invalidates a precedent, such as a hash of the cited source or of the rules files
- that only PM answers, not the answerer's own, can be reused deterministically

### [CONCERN] Who writes the decline block, and how a question moves from the answerer's block to the PM's, is unresolved

Step 1 blocks the slice "as waiting on the answerer". Step 4 says a decline "becomes a `HUMAN` block". Line 89 says the answerer writes only records and resolutions, so it cannot write that block. Today the store gets in the way:
- 103's `journal_escalate` on an already-blocked node writes no second block. It points at the existing block, which here would be the `JUDGE` block.
- Swapping that block for a `HUMAN` one through the inbox means submitting a resolution. Under 127 that returns the node to `runnable` and wakes the Runner.

Line 93 lists this as an open "either/or", but it decides the store contract, 132's cross-project blocked listing, and 160's notification source. There is also a race that line 93 does not name. The PM can resolve a question block while an answering run is in flight. The answerer's later resolution is then rejected, and the answering run's cost is wasted. Settle the block kind, who writes the change from answerer to PM, and the rule for the PM racing the answerer, in the architecture.

### [CONCERN] Reading "committed state" outside the checkout is not designed

Line 97 requires sources "from committed state, not the working tree". Line 49 puts the answering run "outside the paused run's checkout". The document does not say which ref is read:
- the slice branch, where the paused agent may have committed its design or tasks
- the target or integration branch, where the plan lives
- `HEAD` of the paused checkout

It also does not say how a Squadron agent, which reads files with tools from its working directory, gets a tree built from that ref. A temporary `git worktree`, an exported snapshot, or pre-assembled source text in the prompt are three very different designs, with different cleanup and crash-recovery duties. Pre-assembled text would also let the grounding check compare against exactly what was supplied. This is the main mechanism of the answering slice and should be chosen here.

### [CONCERN] What happens when the answering run itself fails is not addressed

Step 3 assumes the answering run "returns an answer with its citations, or a decline". Nothing covers these cases:
- the run fails, is orphaned, hits `provider_error`, stalls, or exceeds `max_cost_usd`
- the answer artifact is missing or malformed
- the resident process crashes while an answering run is in flight

"The record is the memory" (line 55) needs a defined lifecycle for a question record (for example pending, answering with a run id, answered, declined) so that a restart can find in-flight answering runs and adopt or abandon them. Without it, a crash leaves the slice blocked on the answerer forever, or launches a duplicate answering run. The answerer also needs a rule for whether it retries transient failures or declines straight away. Given the "fail explicitly" principle, a decline is the obvious choice, but the document should say so.

### [CONCERN] A Squadron change is a hard dependency but no slice owns it

Line 95 says that if `sq` cannot deny write tools to a dispatch step, or set its working directory, "the gap is a Squadron change". The read-only principle (line 49) depends on this. Anticipated Slices has no step to confirm it and no Squadron work item. The minimum `sq` version is not stated either, although 132 pins 0.24.9 for `agent_question`. Add a spike to confirm this before the answering slice. Name the required `sq` capability and version, and make the answering slice depend on it. Otherwise the slice designer will hit an external blocker mid-slice.

### [CONCERN] The 400-character question tail is a weak input for answering and matching

The answerer and the deterministic matcher both work from `checkpoint.question`, which is the last 400 characters of the reply. A question like "redesign or leave it?" often refers to options and context earlier in the reply. Line 103 puts off reading the full reply until there is evidence, but nothing in the plan gathers that evidence before the answering slice ships live. The tail is also exactly where the prompt has the least context to resist the hallucination trap the project rules warn about. At minimum, the record slice should keep enough data, such as the run id and the run-state path, to measure how often questions are truncated. The question of reading the full reply should be settled before answers run live.

### [NOTE] Existing questions and answers in the journal are not backfilled

Line 66 and 132's "Provides" both name resolved `sq_run` entries' outcome documents as the source for "earlier answers to the same question". The new question record starts empty, and the document does not say whether earlier answers are imported or deliberately left behind. If they are left behind, say so, so the slice designer does not read 132's contract as a requirement.

### [NOTE] Tick order and budget for the second tenant are not specified

120 says the Runner "ticks last" in the resident process and that the tick never waits. The answerer is a new tenant (line 89), and the document does not say where it ticks relative to the Runner. That order decides whether a resolution it submits is applied in the same tick or the next one. The document also does not say how fault isolation and the tick budget apply to it. This is minor once the question of who launches the answering run is settled.

### Run Digest

- Response length: 12877 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 321644 / 243864 / 77770 / 8792 / not computed
- Duration: 103.4 s
- Cost: $0.85 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12

## Resolution (20261031)

All findings addressed in the revised architecture.

- **F001** Fixed. The answerer is a stage inside the Runner tenant, not a second tenant. Its run is a journaled `sq_answer` entry on the slice node, launched through the Runner's control surface without the checkout steps, with a recovery observer. The Runner stays the only `sq` issuer. The design goal now reads "the outcome map does not change; the control surface gains one command kind".
- **F002** Fixed. Amoeba supplies sources as numbered passages and citations must name ids from that set; a separate check step that sees only the question, the answer and the cited passages must confirm the passages settle the question. No shadow mode, on the strength of the two checks.
- **F003** Fixed. One gate (per-run answer limit and PM-reserved screen) for every resolution, reused PM answers included.
- **F004** Fixed. The bounds ship in the question record slice, the first that submits a resolution, before the answering run.
- **F005** Fixed. Only PM answers are reused without a run, only for the same slice, with identifiers kept by normalization. Other prior answers, the answerer's own included, go to the answering run as dated passages and must pass both checks. A resume without instructions is not precedent.
- **F006** Fixed. A waiting question is a `JUDGE` block with no payload (the record holds the question). A decline turns it into a `HUMAN` block through one store operation, not the inbox. The PM racing the answerer: the PM's resolution applies first in the tick; the answering run's result is discarded and recorded.
- **F007** Fixed. Sources are pre-assembled text from the target branch's committed state; the answering run has no file tools and runs in a scratch directory under the store directory.
- **F008** Fixed. Question record lifecycle `pending` → `answering` (entry id) → `answered` | `declined`; any answering-run failure declines with its reason, never retries; restart adopts in-flight runs through journal recovery.
- **F009** Fixed. A Squadron capability spike is the first anticipated slice; it pins the minimum `sq` version and the answering slice depends on it.
- **F010** Fixed. The record flags questions that look cut off, to measure truncation; the fix if needed is a Squadron request for the full reply in `sq runs wait --json`, not reading the run-state file.
- **F011** Fixed. Stated: no backfill; the record starts empty.
- **F012** Fixed. The answering stage runs in the Runner's tick after observe and ingest, under its budget and fault isolation.
