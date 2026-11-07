---
docType: review
layer: project
reviewType: slice
slice: scenario-a-trial
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/225-slice.scenario-a-trial.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: b2638232ef229769f348f1d60b56bc92477e429d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
effort: high
turns: 5
promptTokens: 305354
cachedTokens: 197201
cacheWriteTokens: 108145
completionTokens: 8390
durationSeconds: 71.6
costUsd: 0.53706
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Trial design matches the architecture's scenario A test and the slice plan entry"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md#Technical Decisions"
  - id: F002
    severity: pass
    category: integration
    summary: "Integration points with 223, 224 and Squadron are consistent"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md#Dependencies"
  - id: F003
    severity: concern
    category: under-specification
    summary: "Runs where the PM opts out have no ledger class or denominator rule"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md#D6 — The ledger: classifying every question"
  - id: F004
    severity: concern
    category: scope-alignment
    summary: "D7 adds two \"rethink\" triggers beyond the architecture's test, with no path for fixable failures"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md#D7 — The verdict rule"
  - id: F005
    severity: concern
    category: failure-modes
    summary: "The trial can measure its own implementation work and a tool that is replaced mid-trial"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md#D1 — Programs and members"
  - id: F006
    severity: concern
    category: proportionality
    summary: "Proportionality: some deliverables go beyond what the plan entry needs"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md#D4 — The `handle_pause` call log (amoeba#34)"
  - id: F007
    severity: note
    category: failure-modes
    summary: "Call-log write timing leaves a trace gap for killed calls"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md#D4 — The `handle_pause` call log (amoeba#34)"
---

# Review: slice — slice 225

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Trial design matches the architecture's scenario A test and the slice plan entry

The trial measures the share of real questions answered without the PM. Its first verdict condition, `auto_right` over half, restates the architecture's test: "If most still wait on the PM… the design is rethought". Counted questions are limited to agent questions from in-process runs in members, as in the architecture's "How scenario A runs" step 2. All of the plan entry's success criteria are covered:
- two members;
- waiting questions by reason;
- wrong answers and false screen matches, each with a fix kind;
- fixtures for shapes the tests missed;
- the verdict recorded in the initiative plan.

### [PASS] Integration points with 223, 224 and Squadron are consistent

- **Deferrals from 223:** #34 and #35 are both explicitly deferred to 225 in 223 (lines 212, 320 and 328), so the slice takes them legitimately.
- **`status` outside a member:** `cd /tmp && amoeba status` is supported. 224 gives "every program" from a directory in no program.
- **`decisions --since`:** it matches 224's contract.
- **Squadron boundary:** the slice depends on #302 and #303 only through general Squadron features and the user's own config. Squadron stays independent of Amoeba, as the architecture requires.
- **#302 not yet shipped:** D3 is gated by a `BLOCKED:` line if #302 hasn't landed, which follows the project rule.

### [CONCERN] Runs where the PM opts out have no ledger class or denominator rule

D3 documents how a person watching a run passes the opt-out. Such a run starts no `handle_pause` and leaves no call-log line. If it pauses, `status` lists it as `unhandled`, which D6 classes as `missed`, a failure of Amoeba. The Technical Requirements promise that "every missed hook `status` showed" is in the ledger.

The architecture's scenario A is the unattended case: "the person starts a run at night and walks away". Watched questions that the PM answers before Amoeba's claim land in `pm_first`, which counts against the share. Opted-out questions would count as `missed`.

Both effects pull the denominator toward attended work, and D7's majority test depends on that denominator. Name the opted-out case. Either:
- add an `opted_out` class that is excluded from the count, or
- state that `missed` is only for pauses with no opt-out.

Also say whether `pm_first` questions from a watching PM belong in the denominator.

### [CONCERN] D7 adds two "rethink" triggers beyond the architecture's test, with no path for fixable failures

The architecture gates scenario B on one question: do most questions still wait on the PM? D7 adds two further conditions that flip the verdict to "rethink":
- a single automatic answer that authorized a not-authorized item;
- a wrong-answer rate above one in five.

The one-in-five threshold has no stated basis in the architecture. The conditions are reasonable safety checks. But D8 says prompt, passage and screen defects are fixed after the verdict, and D7 itself computes the "with fixes applied" share. So a trial with a clear majority answered automatically and one screen lapse would give "rethink", and 227 would be held. Yet the lapse is a content or screen fix, not a design problem.

The verdict is binary and gates 227. Either:
- split conditions 2 and 3 into "go, with named fixes before 227 ships", reserving "rethink" for condition 1, or
- state that a failure of condition 2 or 3 is a design problem, and say why.

### [CONCERN] The trial can measure its own implementation work and a tool that is replaced mid-trial

Two issues affect whether the counted data is clean.
- **Self-reference.** D1 registers the `amoeba` repo as a member, and D5 counts every in-process agent question from any member after `trial_start`. The agent that implements the D9 fixes and the review-pass agents work in that repo. If they run through Squadron pipelines, their questions are about the trial itself, and answers to them feed the ledger they are fixing. Either exclude them explicitly or drop the `amoeba` program. Dropping it also removes a second `set_up` call. The slice plan needs only two members, which `trading` already provides.
- **Reinstall while hooks run.** D2 reinstalls with `uv tool install --force` after each D9 fix. A `handle_pause` process or a detached resume started earlier may be running from the replaced tool directory. D9 covers crashes found in real runs but not a crash caused by the reinstall. Add a rule to reinstall only when `status` shows no running resume or answering run, or say that a crash right after a reinstall is not a D9 shape.

### [CONCERN] Proportionality: some deliverables go beyond what the plan entry needs

Candidates to cut or defer, each beyond the slice plan entry's success criteria:
- **Counterfactual share (D7, last paragraph).** The "share with every `rule_line` and `passage` fix applied" is informative only and does not affect the verdict. Cut it, or reduce it to a count of proposed fixes by kind, which D10 already lists.
- **Answering spend (D10).** It is not in the plan entry's criteria, and the doc says its read command "is settled when the note is written". That is an open dependency on Squadron's output. Either name the command now, or defer spend to the "Spend cap per time window" item already in Future Work.
- **Call log scope (D4).** The slice plan entry does not mention the call log, and 223 deferred it "until 225 shows the need". D4 builds it up front and logs every call instead of #34's narrower proposal. The one writer is small. But it adds a new module, a config constant, a permanent unpruned log recording `cwd` and error text, and a documented line format.
  - A lighter option is to redirect the hook command's stderr and exit status to a file in the hook line itself. That needs no code, if #302 runs the command through a shell.
  - If the log stays, state why logging every call is needed, given that D6 already gets missed hooks from `status`.

### [NOTE] Call-log write timing leaves a trace gap for killed calls

The log is appended after the result is known. A hook process killed mid-call (machine asleep, session killed) therefore leaves no line, though D4 says "one line per call, whatever the result". D6's `status` source (`claim_stale`, `unhandled`) already covers this, so no change is needed. A one-line statement that the log records completed calls only would keep the claim accurate. A failed append is handled explicitly. Simultaneous pauses append to one file from separate processes. That is safe for single short lines, but it is worth saying that each line is written in one append.

### Run Digest

- Response length: 7847 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 305354 / 197201 / 108145 / 8390 / not computed
- Duration: 71.6 s
- Cost: $0.54 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
