---
docType: review
layer: project
reviewType: tasks
slice: runner-tenant-and-control-surface
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: e2aad877702bb3778b9a1d586ecc20a3c7f19dc8
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 37
turns: 20
promptTokens: 901904
cachedTokens: 687104
completionTokens: 59422
reasoningTokens: 55824
durationSeconds: 231.5
costUsd: 0.06117
costBasis: alias_pricing
runId: run-20261023-p56-63bf9ff6
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Param validation is specified before journaling but sequenced after it"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md:241"
  - id: F002
    severity: concern
    category: data-flow
    summary: "`finish.record` is never given the poll result, and nothing wires Observe to Finish"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md:226"
  - id: F003
    severity: concern
    category: test-correctness
    summary: "Task 3.1's public-API pin arithmetic is off by one"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md:114"
  - id: F004
    severity: concern
    category: documentation-accuracy
    summary: "The contract document's hosting-surface count is not the test pin's count"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md:357"
  - id: F005
    severity: note
    category: consistency
    summary: "The LLD's character count for a minted id is wrong; the task's is right and nothing reconciles them"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md:150"
  - id: F006
    severity: note
    category: task-granularity
    summary: "Task 3.1 is a large single unit, but the grouping is justified and correctly held together"
    location: "project-documents/user/tasks/122-tasks.runner-tenant-and-control-surface.md:107"
---

# Review: tasks — slice 122

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Param validation is specified before journaling but sequenced after it

LLD D2 says a value containing `,` (or a key containing `,`/`=`) "raises `ValueError` before journaling". Task 5.3 (line 167) faithfully says `build_argv` raises it and annotates "(called before journaling)". But Task 9.1's Act specifies the order as "mint the run id, `journal_issue(sq_run, …)`, then launch", and `build_argv` is inside `launch()` per Task 5.3. Executed as written, the `ValueError` fires after `journal_issue` has committed, leaving an unresolved `sq_run` entry with a bogus param set — exactly the state detection defers on and the Runner must then escalate. Either Task 9.1 must call `build_argv` (or a validator) before `journal_issue`, or Task 5.3 must expose it as a separate pre-journal step. No test currently asserts the "no entry written" property.

### [CONCERN] `finish.record` is never given the poll result, and nothing wires Observe to Finish

Task 8.1's signature is `record(store, entry, finished)`, but the penultimate step says a `completed` run resolves with `result={run_id, outcome, status}` — data that lives on the `RunOutcomeDocument` from `poll_run`, not on `InFlightRun` (`entry`, `run_id`, `state`, per Task 6.1 line 189). The `finished` parameter, and where it carries `outcome`/`status`, is never defined. Task 9.1's step list ("observe → record finished → decide → act → close") also never says how the finished set produced by Task 7.1 reaches `finish.record`. This matters beyond typing: the process contract requires `run_id` in the entry's `result` for Amoeba's run ownership (`record_runner_report` refuses an entry whose result lacks it, and pruning selects on it), so a result without it is a silent ownership loss. The only adequate assertion is the end-to-end test in Task 12.3, five tasks later — by then the defect is buried. Give Task 8.1 the polled document in its signature and have Task 9.1 name the observe→record hand-off explicitly.

### [CONCERN] Task 3.1's public-API pin arithmetic is off by one

`tests/test_process_public_api.py:13` pins 20 names today (verified). Task 2.3 adds `UpstreamShapeError` → 21; Task 3.1 adds `InFlight`. Task 3.1 says the pin "goes to 22 names", and Task 13.1 (lines 357, 363) repeats "22 names". 20 + 2 = 22 only if both count as separate additions on top of today's 20 — but line 114 explicitly says 2.3 already moved the pin. The correct final value is 22 only if 2.3 wrote 21 and 3.1 writes 22; as written, Task 3.1's own arithmetic (21 → 22) contradicts the numbers in the same clause. State the final expected count once (22) in Task 2.3 and have 3.1 and 13.1 reference it, rather than each restating a different intermediate.

### [CONCERN] The contract document's hosting-surface count is not the test pin's count

Task 13.1 instructs editing `docs/process-contract.md` so it says "hosting surface 22 names". The document's own sentence (`docs/process-contract.md:196`, "exactly these 13 names") and its four-group table enumerate the *hosting contract*, not the test pin — and the two numbers already diverge (the test pins 20, the table lists 13, a gap slice 120 left behind). Adding `UpstreamShapeError` and `InFlight` makes the table-derived figure 15, not 22. As written the task produces a document stating a number its own table does not support. Either say "update the hosting-surface paragraph and its table to include `UpstreamShapeError` and `InFlight`, and state its new count", or drop the number from the task and let the table speak.

### [NOTE] The LLD's character count for a minted id is wrong; the task's is right and nothing reconciles them

Task 5.1 asserts "36 characters (`amoeba-` 7 + timestamp 16 + `-` 1 + hex 12)", which is arithmetically correct. Slice D5 says "38 characters" and gives an example id that is itself 36 characters. An implementer reading both will resolve the conflict by picking one, and a test asserting 38 would be wrong. Task 13.1 updates contract text but no task corrects D5, and the tasks file's "Task-level additions to the LLD" list does not mention it. Add one line confirming 36, and note the D5 correction in Task 13.1.

### [NOTE] Task 3.1 is a large single unit, but the grouping is justified and correctly held together

Eight files plus the contract oracle in one effort-4 task is at the upper end. It is defensible: the task explains that the observer change breaks `tests/contract` until the stand-in and oracle are updated in the same commit, and a commit may not hold untested behavior. Splitting it would produce a red suite between commits. Recording it only so the size is a considered choice rather than an oversight — and so that, if the CONCERN about the pin arithmetic above is fixed by shrinking this task, the contract-suite coupling is the reason it cannot be shrunk much.

### Run Digest

- Response length: 6174 chars
- Response is newline-free: no
- Tool calls made: 37
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 203274
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 901904 / 687104 / not computed / 59422 / 55824
- Duration: 231.5 s
- Cost: $0.06 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
