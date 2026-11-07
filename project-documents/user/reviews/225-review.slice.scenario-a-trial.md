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
reviewedSha: 5d01bb57ae159e98f19d4972b710e1e97c57d88e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
effort: high
turns: 7
promptTokens: 305246
cachedTokens: 196568
cacheWriteTokens: 108670
completionTokens: 11768
durationSeconds: 95.6
costUsd: 0.572876
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Trial follows the architecture's scenario A test and boundaries"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md#D7 — The verdict rule"
  - id: F002
    severity: concern
    category: under-specification
    summary: "Automatic answers whose resume was refused or never happened have no ledger class"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:158-185"
  - id: F003
    severity: concern
    category: scope-creep
    summary: "A third verdict, \"go with fixes\", adds a gate the architecture and slice plan don't define"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:192, 212"
  - id: F004
    severity: concern
    category: under-specification
    summary: "The line between D8 \"does not change\" and D9 \"fixes\" is blurry, which puts the measurement at risk"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:195-205"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Overweight for a 2/5 slice: bookkeeping that duplicates existing mechanisms"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:127, 158-185"
  - id: F006
    severity: note
    category: error-handling
    summary: "Call log pulled forward from 223's deferral; failure visibility under a hook"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:139-148"
  - id: F007
    severity: note
    category: nfr
    summary: "Spend is not measured, though the slice's stated value is about cost"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:44, 210"
---

# Review: slice — slice 225

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Trial follows the architecture's scenario A test and boundaries

- **Verdict test:** D7's test matches the architecture's: the share of questions answered without the PM, and a rethink if most still wait on the PM.
- **Opt-out:** D3 puts the opt-out flag on the answering run. That is what the architecture's scenario A step 5 requires ("always with the hook's opt-out"), and 223 deferred it here.
- **Hook configuration:** the Squadron change stays general. Amoeba is not a trial member, so the trial never counts its own questions.
- **Real store:** it is read only through the CLI, and tests keep using `AMOEBA_HOME`.
- **Call-log failures:** D4 names each failure of the new write path. Those are a failed append, a call killed partway, simultaneous appends, and a failed `handle_pause` call.

### [CONCERN] Automatic answers whose resume was refused or never happened have no ledger class

- **The gap:**
  - D6 says each row gets "exactly one class", and the success criteria require "every counted question has one ledger class".
  - `auto_right` requires that the run "was resumed". `auto_wrong` needs an override or a judged-wrong answer. `waiting` is for questions sent to the PM. `missed` means no question row. `pm_first` is for a PM or outside resume.
  - An automatic answer that passed the check and screen but whose resume was `refused`, or whose process died, fits none of these. 224's `status` shows these as `answered_unresumed`.
- **Source coverage:** the three sources listed in D6 (`decisions`, `waiting_on_pm`/`unhandled`/`claim_stale`, the call log) don't name `answered_unresumed` either.
- **Why it matters:** these questions didn't save the PM anything, so they have to count against the share in D7. A reviewer left to improvise a class will skew the number the verdict rests on.
- **Suggested fix:** add a class, or fold them into `missed` or `waiting` with a stated rule. Add `answered_unresumed` to the `status` source.

### [CONCERN] A third verdict, "go with fixes", adds a gate the architecture and slice plan don't define

- **What the plan says:** the architecture and the slice plan entry give a binary result, "go on to 227, or rethink". The plan makes 227 depend on "225 with a go verdict, and 226".
- **What D7 and D10 add:**
  - A third tier. If any automatic answer authorized a barred item, the fixes become issues, and those issue numbers are added to 227's dependencies.
  - That holds scenario B behind prompt, passage or screen fixes. 227 (`report_release`, `changes`) doesn't use the answering code.
- **Why it matters:** it couples two independent areas through an undeclared dependency, and it rewrites another slice's plan entry.
- **Suggested fix:**
  - Keep the verdict binary.
  - File the authorize-list violations as issues against 223's check and screen, and don't gate 227 on them.
  - If the PM wants a safety gate, state it in the architecture or slice plan first.

### [CONCERN] The line between D8 "does not change" and D9 "fixes" is blurry, which puts the measurement at risk

- **D8's rule:** the answering prompts, passage assembly and screen are frozen, "otherwise the trial measures a moving system".
- **D9's triggers:** D9 allows code fixes for `sources_missing` or `sources_unreadable` on a real plan, and for "a question text that the answering pipeline mishandled".
- **Why it's ambiguous:**
  - Both of those can be fixed inside passage assembly or prompt handling, which D8 freezes.
  - A wrong answer and a crash are different cases, but "mishandled" doesn't say which one it means.
  - D2 also doesn't say whether rows before and after a D9 fix are compared or pooled.
- **Suggested fix:**
  - Limit D9 to crashes, parse failures and unreadable-input errors, meaning cases where no answer was produced.
  - Record anything that changes answer content as a proposed fix.
  - Note the commit of each D9 fix on the ledger rows it affects.

### [CONCERN] Overweight for a 2/5 slice: bookkeeping that duplicates existing mechanisms

- **Reinstall-window bookkeeping:**
  - D2 sets up `pgrep` gating and records each reinstall's start and end. After each reinstall it runs `status` and passes each `unhandled` pause from that window to `handle_pause`, with a special `reinstall` flag on the ledger row.
  - That is the missed-hook catch-up 224 already provides, and the architecture accepts a missed hook as "waiting".
  - Cut it to "reinstall only when idle". Treat any pause caught during the install as an ordinary missed hook.
- **Class and fix taxonomy:**
  - Six classes plus five fix kinds per row is more than the plan's success criteria need. The plan wants answered without the PM, waiting on the PM by reason, and wrong answers.
  - `opted_out` and `pm_first` are reported as counts only. `opted_out` is empty unless #302 records the opt-out.
  - Fold both into one "excluded" class with a reason column.
- **Third verdict tier:** see the separate finding on "go with fixes".

### [NOTE] Call log pulled forward from 223's deferral; failure visibility under a hook

- **Pulled forward:** 223 deferred this log "until 225 shows the need (#34)". D4 builds it up front, justified by a missed row needing its cause. That is a fair call, and it is the only new I/O path in the slice.
- **Warning goes nowhere under a hook:** a failed append prints a stderr warning, but D4's own reasoning says a hook has no terminal. When the log breaks, a hook call leaves no trace anywhere. The sanity pass in step 4 reduces this by proving the log works before the trial starts. A `missed` row with no log line should be recorded as "cause unknown", not guessed.
- **Layering:** the log is written in the CLI, while the architecture says the CLI has "no logic of its own". Writing the line at the process boundary is defensible, and it keeps the operation unchanged. A line in the doc saying why would help, since 226's in-process MCP calls are not logged.

### [NOTE] Spend is not measured, though the slice's stated value is about cost

- **What the architecture says:** the "Unattended spend" consideration says a work run's cost cap restarts on each resume. Unattended spend can reach the answer limit times that cap.
- **What the slice does:** it copies the config limits into the note and defers spend measurement to amoeba#38. The architecture's verdict test is count-only, so this is acceptable.
- **The mismatch:** the Value section says the trial decides "whether Amoeba saves the PM more than it costs", and the verdict can't cover cost. The slice plan's Future Work item 2 (spend cap per time window) depends on 225. Each review pass could record the cost already in the `decisions` data at no extra mechanism. Otherwise, reword the Value line to match what is measured.

### Run Digest

- Response length: 7812 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 305246 / 196568 / 108670 / 11768 / not computed
- Duration: 95.6 s
- Cost: $0.57 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution

- **[PASS] Trial follows the architecture's scenario A test and boundaries:** no change needed.
- **[CONCERN] Refused or never-resumed automatic answers have no class:** changed. D6's `status` source now includes `answered_unresumed`. A new catch-up rule passes every `unhandled`, `claim_stale` and `answered_unresumed` run to `handle_pause` and classes the row by that call's outcome. An answer still not resumed at the stop pass is `missed`, which counts against the share.
- **[CONCERN] "Go with fixes" adds a gate the plan doesn't define:** changed. The verdict is binary again (D7, D10, success criteria). An answer that authorized a barred item is filed as an issue against 223's check and screen, and doesn't gate 227.
- **[CONCERN] D8/D9 line is blurry:** changed. D9 is limited to cases where no answer was produced (crash, parse failure, unreadable input). A fix only lets the existing path run, and anything that changes answer content is a D8 proposed fix. Rows before and after a fix are pooled, and each row notes the installed commit.
- **[CONCERN] Overweight bookkeeping:** changed. Cut the reinstall-window bookkeeping from D2: a pause during a reinstall is an ordinary missed hook, handled by D6's catch-up. Merged `opted_out` and `pm_first` into one `excluded` class with a reason. Kept the fix kinds, because the slice plan asks for each problem to be recorded "with what would have fixed it (a rule line, a passage, a prompt change)".
- **[NOTE] Call log pulled forward; failure visibility:** changed. D6 records a `missed` row with no log line as `cause unknown`, never guessed. D4 says why the log is written at the CLI boundary. Not adopted: the remark that 226's in-process MCP calls go unlogged. 226 starts `handle_pause` only as a detached CLI process, so those calls are logged, and D4 now says so.
- **[NOTE] Spend not measured:** changed. The Value line now matches what is measured, and points to amoeba#38 for spend. Not adopted: recording cost from `decisions` data. 224's `decisions` records carry no cost.
