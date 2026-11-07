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
reviewedSha: 8e471be2446505c13d78a7bad1af148a90230d12
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
effort: high
turns: 6
promptTokens: 301858
cachedTokens: 195940
cacheWriteTokens: 105910
completionTokens: 6643
durationSeconds: 57.2
costUsd: 0.510522
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: hidden-dependency
    summary: "`opted_out` classification depends on an unpromised #302 behavior"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:131-137, 175-179"
  - id: F002
    severity: concern
    category: measurement-integrity
    summary: "Reinstalling during the trial can create false `missed` rows"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:124-129, 195-199"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Call log is heavier than needed and overrides 223's deferral"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:139-149"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Alignment with the architecture's scenario A test"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:188-193"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Failure modes of the new call-log write path are enumerated"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:145-148"
  - id: F006
    severity: note
    category: scope
    summary: "Trial verdict is count-only; spend is deferred to amoeba#38"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:211"
  - id: F007
    severity: note
    category: scope
    summary: "Go-with-fixes gates 227 on every wrong-answer fix"
    location: "project-documents/user/slices/225-slice.scenario-a-trial.md:193, 213"
---

# Review: slice — slice 225

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] `opted_out` classification depends on an unpromised #302 behavior

The `opted_out` class is excluded from the count, and `missed` is counted against the share. A run started with the opt-out leaves no question row and no call-log line. The review pass can only tell it from a missed hook if Squadron records the opt-out somewhere readable. D3 assumes it does ("where Squadron shows afterward that a run was started with it"), and D6 says the review pass reads it there. Neither the Prerequisites section nor the architecture's #302 row (a per-run opt-out, nothing about recording it) promises this. If #302 ships without it, every watched or opted-out run becomes `missed`. That lowers the measured share for a reason unrelated to Amoeba's answering. Fix: add the recorded opt-out to the #302 prerequisite and mark the D3 doc task `BLOCKED:` if it is absent. Otherwise define a fallback, such as the PM listing opted-out runs in the note.

### [CONCERN] Reinstalling during the trial can create false `missed` rows

D2 reinstalls the tool after each D9 fix. Its only guard is a point-in-time `pgrep` for `amoeba handle_pause`. A pause that fires during the reinstall, or after the check passes, finds no usable `amoeba`. It leaves no row and no call-log line, so it shows as `unhandled` in `status` and is classed `missed`. That counts against the share. D8 keeps the system fixed so the numbers mean something, but D2 is the one mechanism that changes the system mid-trial. D2 doesn't say how such a pause is classified. D8 also doesn't say what happens if #299 lands mid-trial and the models change. Fix: add a ledger rule that excludes or flags a pause that falls inside a recorded reinstall window, and state that #299 landing mid-trial doesn't change the configured models until after the verdict.

### [CONCERN] Call log is heavier than needed and overrides 223's deferral

223 explicitly deferred #34 ("Logging why a hook call was missed is deferred until 225 shows the need"). The slice plan entry for 225 says "Interfaces: None new". This slice adds a new module (`cli/call_log.py`), a config constant and a JSONL file at the start of the trial, before any trial evidence exists. D4 also logs every call, which is the heavier option compared with amoeba#34's proposal to log only calls that write no question row. Calls that write rows are already in `decisions` and `status`, so for them the log repeats store state. That sits uneasily with "read, don't mirror". The need for a log of the no-row calls is real: a hook has no terminal, and an exit 3 would otherwise leave nothing behind. Cut the logging to calls that end in exit 3 or write no row, which is what #34 proposed and what the ledger's `missed` rows need. The sanity-pass check in Walkthrough step 4 can then read `decisions` or `status` instead of `tail -1`. The Technical Requirements tests also shrink.

### [PASS] Alignment with the architecture's scenario A test

D7 applies the architecture's test directly: go when automatic answers are more than half of the counted questions, otherwise rethink. Wrong answers are recorded with a fix kind instead of acting as a second gate. The ledger draws on `decisions`, `status` and the call log, so no question goes uncounted. D8 keeps prompts, passages and the screen fixed during the trial, as a measurement needs. D10 updates the slice plan and the initiative plan as the plan entry requires.

### [PASS] Failure modes of the new call-log write path are enumerated

The doc covers a failed append (a warning on stderr, the call's own exit code kept, and the one handled exception commented), a call killed partway (no line, and `status` still shows the pause), and simultaneous calls (append-mode single writes). The log has no pruning, matching 223's logs. Together with the BLOCKED handling for an unlanded #302, this meets the failure-mode criterion.

### [NOTE] Trial verdict is count-only; spend is deferred to amoeba#38

The architecture motivates the test as "Amoeba costs more than it saves", but defines it as a count of questions answered. The slice follows the definition and defers spend, which is consistent. If the share comes out marginally above half, the verdict may be hard to defend without the cost figures. Consider capturing answering and resume costs in the ledger as it is filled in, even though D10 defers the analysis.

### [NOTE] Go-with-fixes gates 227 on every wrong-answer fix

A single `auto_wrong` row turns a go into go with fixes. D10 then adds the filed issues to 227's dependencies. One minor wrong answer can hold up scenario B behind content-only fixes (a prompt, passage or rule line) that the doc itself says are not design changes. Consider gating 227 only on fixes for wrong answers that touched the not-authorized list.

### Run Digest

- Response length: 6071 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 301858 / 195940 / 105910 / 6643 / not computed
- Duration: 57.2 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
