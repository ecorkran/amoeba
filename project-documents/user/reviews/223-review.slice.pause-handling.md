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
reviewedSha: 216067b9bbcb3149600918bc220684dddbd9e7e1
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: high
turns: 9
promptTokens: 449079
cachedTokens: 328956
cacheWriteTokens: 120113
completionTokens: 12768
durationSeconds: 103.9
costUsd: 0.641888
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and scope match the architecture"
    location: "project-documents/user/slices/223-slice.pause-handling.md#Architecture"
  - id: F002
    severity: note
    category: architecture-alignment
    summary: "Claim-after-context ordering is a justified, documented deviation"
    location: "project-documents/user/slices/223-slice.pause-handling.md:129"
  - id: F003
    severity: concern
    category: error-handling
    summary: "D7's `not_found` branch can double-spend while a live claimant's child is still starting"
    location: "project-documents/user/slices/223-slice.pause-handling.md:256-259"
  - id: F004
    severity: concern
    category: error-handling
    summary: "D8's timeout kill can destroy a resume that has just taken the lock"
    location: "project-documents/user/slices/223-slice.pause-handling.md:271"
  - id: F005
    severity: concern
    category: scope
    summary: "The opt-out for the answering run is deferred through a `BLOCKED:` task that contradicts the project's BLOCKED rule"
    location: "project-documents/user/slices/223-slice.pause-handling.md:238"
  - id: F006
    severity: concern
    category: testing
    summary: "CLI tests have no redirect for Squadron's real runs directory"
    location: "project-documents/user/slices/223-slice.pause-handling.md:328"
  - id: F007
    severity: concern
    category: integration
    summary: "The `handle_pause` checkout contract is not stated for 226's wrapper"
    location: "project-documents/user/slices/223-slice.pause-handling.md:386-392"
  - id: F008
    severity: concern
    category: proportionality
    summary: "The design restates itself in places and could be shorter"
    location: "project-documents/user/slices/223-slice.pause-handling.md:189-201"
  - id: F009
    severity: note
    category: error-handling
    summary: "Hook-time operational errors leave no record, which the architecture accepts"
    location: "project-documents/user/slices/223-slice.pause-handling.md:341"
---

# Review: slice — slice 223

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering, dependency direction and scope match the architecture

- The import direction stays `cli → operations → store, config, upstream, answering`.
- `processes.py` and `run_file.py` import nothing from Amoeba or `answering`.
- The boundary test that `amoeba.answering` imports no store, config or operations module protects the `store → answering.values` edge.
- Scope covers the plan's 223 entry: eligibility, context, answering run, shared resume, authorize list, dead claim, hook documentation and restored live tests.
- The exclusions (status and decisions, MCP, watchers, shared precedent) match the architecture's "pull, never push" and "called, never calling around".
- The per-run answer limit counts only automatic answers, as the architecture requires.

### [NOTE] Claim-after-context ordering is a justified, documented deviation

The architecture claims at step 3 and gathers context at step 4. The slice inserts the claim last, so one insert can record either the answering run id or the context failure. D4's compare-and-set guards keep the double-handling rules intact. The slice states the cost, which is that a losing racer repeats the `cf` and git reads. That cost is acceptable and no change is needed.

### [CONCERN] D7's `not_found` branch can double-spend while a live claimant's child is still starting

- `not_found` is treated as "the claimant died before the spawn", and the slice calls the double-spend window "milliseconds".
- The window is longer than that. After the claimant spawns `sq run --run-id`, Squadron does not write the run file until it has started, imported and loaded the pipeline. That takes seconds, and during that time `poll_run` returns `not_found`.
- A hook call and a catching-up agent racing in that gap would start a second answering run against a live claim.
- The architecture limits double-spend to "a process that died between claiming and starting", not a live claimant with a slow child.
- The `timed_out` rows already use `claimed_at` against `answering_wait_seconds`. Apply the same age gate to `not_found`. A young `not_found` claim returns `skipped / already_claimed`, and only an aged one gets a new answering run. This needs no new config.

### [CONCERN] D8's timeout kill can destroy a resume that has just taken the lock

- On timeout, with the child alive and the run unchanged at the last poll, the parent terminates the child's process group and records `refused`. The slice then says "the run never left `paused`, so nothing of it is lost."
- That only holds as of the last poll. The child can take the run lock and flip the run to `running` between that poll and the kill.
- The kill would then orphan a run Amoeba just resumed. The answer would be recorded `refused`, and every later `handle_pause` would skip it as `not_paused`. Nobody would see a reason.
- Re-poll after terminating, and classify from that result (resumed, moved past, or still paused). Alternatively, state why the kill is safe. Either way, add the case to D15's D8 branch list.

### [CONCERN] The opt-out for the answering run is deferred through a `BLOCKED:` task that contradicts the project's BLOCKED rule

- The plan and architecture say the answering run starts "with the hook's opt-out". The slice defers the flag until #302 ships and relies on the interim `answering_run` store skip. That fallback is sound.
- The slice also says that if #302 hasn't shipped, "the task is marked `BLOCKED:` and the rest of the slice goes ahead".
- Project rules define `BLOCKED:` as a task that cannot proceed and makes the agent stop, so "carry on" contradicts it.
- D14 repeats the pattern ("if #302 hasn't shipped when the task runs").
- State the interim behavior as the delivered behavior: no flag, skipped as `answering_run`. Make the flag a follow-up for 225, where #302 is a stated external dependency. That removes the BLOCKED marker.

### [CONCERN] CLI tests have no redirect for Squadron's real runs directory

- D12 puts `squadron_runs_dir()` at the real `~/.config/squadron/runs`, called only by the CLI. Tests pass a fixture directory to the reader.
- D15 says CLI tests run `handle_pause` against a fake `sq` script. Nothing says how those tests supply the schema-5 run file. The `AMOEBA_HOME` fixture (222, D10) does not cover Squadron's directory.
- Those tests would read the developer's real run files, or fail when none exist. That conflicts with the architecture's rule that tests never touch real state.
- Say how the CLI resolves a test-controlled runs directory. For example, derive it from an injected `deps` path or a single env override read only in `home.py`.
- The clause "a test of D10's rule shows that tests never pass it to the reader" is hard to follow. D10 here is the migration, and the rule meant is 222's D10. Reword it.

### [CONCERN] The `handle_pause` checkout contract is not stated for 226's wrapper

- D3 makes the working directory the claimed checkout. A wrong-checkout resume is not refused by Squadron and works in the wrong worktree.
- The Python API takes `directory`, and the CLI takes only `<run_id>`.
- "Provides to 226" does not say that MCP must start `handle_pause` with `cwd` set to the run's checkout. It also does not say where an MCP caller gets that directory. That source is #303 via 224's listing.
- The architecture notes that MCP sessions can start anywhere. 226 would otherwise wrap the operation with the wrong directory.
- Add one line to "Provides to 226" naming the directory as a required input.

### [CONCERN] The design restates itself in places and could be shorter

The slice is effort 5 and mostly necessary: dead-claim recovery, the shared resume and the program passages all trace to the architecture or plan. These parts can be cut or merged:
- **D3's wrong-checkout analysis.** About 20 lines argue why no guard is added for a case with no designed caller. Two lines would carry it: the result's `checkout` field, and the hand-call note in D14. The Squadron code reading can go in a footnote or the audit.
- **Technical Scope versus Component Structure.** Technical Scope lists the same modules and decisions that Component Structure and each Dn already give.
- **D13 versus API Contracts.** D13's exit-code text and the API Contracts table cover the same ground.
- **Verification Walkthrough steps 6 and 7.** They repeat D15 coverage. Keep them as one-line pointers, as step 8 already does.
- **`answer --file <path|->`.** It is not required by the plan, since `--text` meets it. Defer it unless a real multi-line need exists.

### [NOTE] Hook-time operational errors leave no record, which the architecture accepts

An exit-3 failure during a hook call (for example, `cf` or `sq` failing) goes only to stderr. Squadron does not wait on or capture it. The pause then appears in 224's missed-hook listing, which is the architecture's stated recovery, and call logging is deferred (#34). The other failure paths are covered: answering stall, poll failure, spawn error, resume refusal, a settler dying mid-run, and a PM answer arriving mid-run.

### Run Digest

- Response length: 8237 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 449079 / 328956 / 120113 / 12768 / not computed
- Duration: 103.9 s
- Cost: $0.64 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Resolution

- **[PASS] Layering, dependency direction and scope:** no change needed.
- **[NOTE] Claim-after-context ordering:** no change; the deviation and its cost are already stated in Data Flow step 4.
- **[CONCERN] D7 `not_found` double-spend:** changed. `not_found` now uses the same `claimed_at` age gate as `timed_out`: a claim younger than `answering_wait_seconds` is `skipped / already_claimed`, and only an older one gets a new answering run. The "milliseconds" claim was removed.
- **[CONCERN] D8 timeout kill:** changed. After terminating the resume process, D8 waits for it to exit and polls once more. It records `refused` only if the run is still at the pause, and `resumed` if the run is `running` or has moved past. Added that case to D15's D8 branch list.
- **[CONCERN] `BLOCKED:` deferral of the opt-out:** changed. D6 now states the delivered behavior: no flag, and a hook call on the answering run is skipped as `answering_run`. Adding #302's flag and the exact hook config line to `docs/squadron-hook.md` is deferred to 225 as amoeba#35. D14 now gives the hand call only.
- **[CONCERN] CLI tests and Squadron's real runs directory:** changed. D12 now says CLI subprocess tests set `HOME` to a temporary directory holding `.config/squadron/runs/<run_id>.json`, copied from the recorded run file, so `Path.home()` resolves there with no new variable. Reworded the confusing D10 clause to name 222's D10.
- **[CONCERN] Checkout contract for 226:** changed. "Provides to 226" now says the run's checkout is a required input: MCP starts `handle_pause` with `cwd` set to it, taken from 224's listing (#303), never the server's own directory.
- **[CONCERN] Restatement and length:**
  - Changed: D3's wrong-checkout analysis is cut to one paragraph.
  - Changed: Technical Scope's included list is now one line pointing at Component Structure and D1 to D15.
  - Changed: the duplicate CLI exit-code table in API Contracts is removed, and D13 holds it.
  - Changed: walkthrough steps 6 and 7 are now one-line pointers.
  - Changed: `answer --file` is dropped, and `--text` meets the plan.
- **[NOTE] Hook-time operational errors leave no record:** no change. The architecture accepts this, `status` shows the missed hook, and call logging is already deferred as amoeba#34.
