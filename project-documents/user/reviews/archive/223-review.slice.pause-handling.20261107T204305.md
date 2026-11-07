---
docType: review
layer: project
reviewType: slice
slice: pause-handling
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/223-slice.pause-handling.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 31220185b39137142ea309856d40f202beb29874
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: high
turns: 10
promptTokens: 441686
cachedTokens: 319649
cacheWriteTokens: 122027
completionTokens: 10385
durationSeconds: 87.6
costUsd: 0.624783
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: architecture-boundaries
    summary: "Program-passage reads put store access inside the answering library"
    location: "project-documents/user/slices/223-slice.pause-handling.md#D11 — Changes to the answering library (line 310; also lines 126 and 131)"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The answering-run wait is unbounded in wall-clock time and leaves a claim that cannot recover"
    location: "project-documents/user/slices/223-slice.pause-handling.md#D6 — Wait (line 238); #D7 (lines 247-249)"
  - id: F003
    severity: note
    category: proportionality
    summary: "Small additions that nothing reads yet"
    location: "project-documents/user/slices/223-slice.pause-handling.md#D10 (lines 289-301); #D13 (line 331)"
  - id: F004
    severity: note
    category: architectural-alignment
    summary: "Claim order differs from the architecture's step order"
    location: "project-documents/user/slices/223-slice.pause-handling.md#Data Flow (step 4, line 141)"
  - id: F005
    severity: note
    category: hidden-dependencies
    summary: "Context lookups rely on conventions the design does not pin down"
    location: "project-documents/user/slices/223-slice.pause-handling.md#D5 (line 224); #D11 (line 310)"
  - id: F006
    severity: pass
    category: architectural-alignment
    summary: "Eligibility, record lifecycle and resume match the architecture"
    location: "project-documents/user/slices/223-slice.pause-handling.md#D3, #D4, #D8, #D9"
  - id: F007
    severity: pass
    category: architectural-alignment
    summary: "Authorize list, spend limits and Squadron independence are preserved"
    location: "project-documents/user/slices/223-slice.pause-handling.md#D11; #Special Considerations"
---

# Review: slice — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Program-passage reads put store access inside the answering library

D11 lists the program passages under "Changes to the answering library". It says they are redone against the new store: the concept member and path "come from `programs`", the member list "from `members_of`", and the concept checkout from `project_of`. The component tree repeats this with "(221) + … concept passages" under `answering/`.

This conflicts with the layering in two places:
- The import direction in this design is `cli → operations → store, config, upstream, answering`. 221 states the library has no store and that "223's design can call the library's entry points without touching a store type."
- 221 D4 has `store` import `answering.values`. If `answering` then imports `store.programs`, the packages form a cycle. The rewritten `tests/test_import_boundaries.py` enforces this direction.

D11 does not say which module holds the store reads, or how the answering library receives the concept and member data.

Suggested fix: keep the store, `project_of` and git reads in `operations/pause_context.py`. It already assembles passage inputs in D5. Pass plain values (member list, concept text and commit) into `answering.passages`. State in D11 that `answering` takes these as arguments and imports no store module.

### [CONCERN] The answering-run wait is unbounded in wall-clock time and leaves a claim that cannot recover

D6 says the parent "waits for the child process to exit, with no timeout of its own". It treats the cost cap and Squadron's stall detection as the bound. The cost cap limits spend, not elapsed time. The design also lists Squadron behavior as "not observed yet" in its risks, and nothing confirms that stall detection catches a hung provider call.

If the answering run hangs, two things go wrong:
- The `handle_pause` process that the hook started never exits. This conflicts with the architecture's "short-lived" principle.
- D7 maps `timed_out` (still running) to `skipped / already_claimed`. Every later call therefore backs off, and the question stays `claimed` with no visible reason. This conflicts with "fail where someone can see it".

D7 handles the settler dying. It does not handle the answering run hanging.

Suggested fix: name the failure mode and its handling. Either add a wall-clock ceiling (a config value like `resume_wait_seconds`) after which the parent terminates the process group and settles `answering_run_failed`. Or state which Squadron stall behavior makes this unnecessary, and add a live-test case that observes it. D7 also needs a rule for a `claimed` row whose answering run has been running longer than that ceiling.

### [NOTE] Small additions that nothing reads yet

The scope matches the slice plan's effort of 5, and the program passages are plan-assigned work. A few items have no named consumer and could be cut or deferred:
- `questions.pipeline` is described only as "for the record". Nothing in 224's `status` or `decisions` needs it.
- `questions.dropped_pm_answers` has no consumer in this slice or in 224.
- The `handle_pause.jsonl` call log is a new persisted artifact. The architecture does not list it under "Where things live". It does serve "fail where someone can see it", since the hook has no terminal. Keep it only if the store's `waiting_detail` does not already carry the same reasons. The missed-hook case is the one the store cannot record, because no row is written.

### [NOTE] Claim order differs from the architecture's step order

The architecture's scenario A claims the question (step 3) before working out context (step 4). The design gathers context and creates the scratch directory first, then inserts the claim. This lets it record `waiting_on_pm` with the reason in the same insert, and it records the answering run id at claim time as the architecture requires.

The cost is that a losing racer repeats the `cf` reads and scratch creation before backing off. The design handles this by removing the loser's scratch directory. The deviation is reasonable but is not stated as one.

### [NOTE] Context lookups rely on conventions the design does not pin down

- The slice-to-initiative lookup assumes an initiative's index is no higher than its slices' indexes, and that `cf list slices` returns entries the code can match by integer index. This holds today, but it is a Context Forge numbering convention. The design should state it as an assumption and give it a fixture.
- D11 reads `project_path` from `project_of(reference=…)`. 222's `project_of.py` returns `CFProject | CFProjectNotFound`. The design should confirm that `CFProject` carries `project_path` or add it in 222's parser.

### [PASS] Eligibility, record lifecycle and resume match the architecture

- **Eligibility:** D3 handles only agent questions from in-process runs in program members. Prompt-only runs, other checkpoint kinds and repos outside a program are left alone with a reason. Operational failures are not read as "not mine".
- **Question record:** D4 keys questions by run id and `paused_at`. It uses compare-and-set moves and a PM answer that wins over an in-flight answering run. It counts only automatic answers toward the limit.
- **Resume:** D8 follows the architecture's three steps. It re-reads the checkpoint, starts the detached `sq run --resume`, and polls for `running`. Its `resumed` and `not_delivered` outcomes are never overwritten, and a refused resume is retried by a second call that starts no new answering run.
- **Locking and dead claims:** No transaction is held across a subprocess, and D7 covers the dead-claim cases.

### [PASS] Authorize list, spend limits and Squadron independence are preserved

- **Authorize list:** The per-member list reaches the answer and check steps through a prompt file, and the screen is the backstop. Allowing an item for a member removes it from both.
- **Spend:** `max_cost_usd` and `answer_limit` are restated as the spend bounds. D6 also checks the limit before starting an answering run.
- **Squadron:** All Squadron coupling sits behind one version-checked reader (`run_file.py`) and the hook, and nothing in Squadron needs to know about Amoeba.
- **#302 gap:** The #302 opt-out is deferred explicitly, with a safe interim behavior (`not_a_project`).

### Run Digest

- Response length: 7514 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 441686 / 319649 / 122027 / 10385 / not computed
- Duration: 87.6 s
- Cost: $0.62 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
