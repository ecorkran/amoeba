---
docType: review
layer: project
reviewType: slice
slice: state-home-and-question-lifecycle
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261112
dateUpdated: 20261112
reviewedSha: 2301b05662db999c3088facb45e699ec862ebe4a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
turns: 16
promptTokens: 930331
cachedTokens: 669184
completionTokens: 160469
reasoningTokens: 156859
durationSeconds: 1277.9
costUsd: 0.115055
costBasis: alias_pricing
runId: run-20261112-p4-1fa91a7d
squadronVersion: 0.24.27
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "A crash between the store rename and the directory move wedges the move permanently"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:157-167"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The calls log cannot record the error class it is claimed to record, and its directory is never created"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:279-285"
  - id: F003
    severity: concern
    category: failure-modes
    summary: "`last_call` is a new read path with no failure strategy"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:285"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "`sweep_run` writes before the eligibility checks, so \"writes nothing\" is not exact"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:118"
  - id: F005
    severity: note
    category: failure-modes
    summary: "`resume_bound_seconds` may be shorter than the longest resume"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md:196"
  - id: F006
    severity: note
    category: scope
    summary: "The state-home layout and prune list omit `logs/mcp/`"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md#d9--pruning"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Slice covers the plan entry, and dependency direction and the config/state split are correct"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md#technical-scope"
---

# Review: slice — slice 228

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] A crash between the store rename and the directory move wedges the move permanently

D2's guard admits a legacy home holding only `answering/` or `logs/` — which is exactly the state a crash during step 5 leaves, since step 4 already deleted the legacy `amoeba.sqlite3`. Step 1 then says "Open the legacy store and take `BEGIN IMMEDIATE` on it", and 222 D2 defines one open mode: a missing store is created. So the rerun fabricates an empty, migrated legacy store, step 2 skips the copy ("if the new store does not exist" is false), and the "Both stores exist" branch compares it with the real store, finds them different, raises `StoreRelocateError` and *changes nothing*. Every later command — the hook included — then fails the same way, and the exit is deleting a file Amoeba itself created, which contradicts this doc's own "Nothing is ever fixed by editing the store" (`summary`, Value) and the architecture's "Short-lived and restart-safe" principle. It also contradicts D2's test claim that a crash after each step is "followed by a clean rerun".

Fix worth stating: open the legacy store only when the file is present (or record move completion somewhere in the legacy home), and delete the legacy store before moving the directories rather than after.

### [CONCERN] The calls log cannot record the error class it is claimed to record, and its directory is never created

D11 says the log line is written to `calls_log_dir() / <UTC date>.jsonl` "whatever happened", "including a `ConfigError` or `AmoebaHomeError` raised before any store opens". But `calls_log_dir()` derives from `state_home()` (D1), so a home error is precisely the class for which no log path can be computed. Separately, nothing in the design says who creates `<state>/logs/calls/`: the ordering in Data Flow is `prepare_state_home` → config load → `Store.open` (api that creates parents), so a `ConfigError` on a fresh install — the missing `prune_after_days` case the Operator Walkthrough opens with — is raised before anything has created the state tree. The append then fails with `OSError`, which D11 deliberately downgrades to a stderr line, leaving no line in the log. The success criterion "Every `handle_pause` call, including a `ConfigError` exit, adds one calls-log line" is therefore not achievable as specified. Add to D11 that `append_call` creates its directory (as 223's log writes do), and either say where the `AmoebaHomeError` ending is recorded or drop it from the claim.

### [CONCERN] `last_call` is a new read path with no failure strategy

`status` calls `last_call` once per `unhandled` and `claim_stale` run, reading day files newest first. The design specifies the write-side failure (OSError → stderr, exit unchanged) but nothing for the read side: an unreadable day file, a truncated or non-JSON line from an interrupted append, or a permissions change. Any of these raising out of `status` breaks the one command the PM has for seeing a broken hook, against the architecture's "Fail where someone can see it" and 224's own pattern for the equivalent case (`lookup_failed` is surfaced and the rest of `status` still prints). State that a bad line or file is skipped or reported as a `last_call` problem in the result, never an exception.

### [NOTE] `sweep_run` writes before the eligibility checks, so "writes nothing" is not exact

The `handle_pause` flow runs `sweep_run` before eligibility, so a call that ends as `wrong_checkout` (D10: "and writes nothing"), `not_a_project` or `not_in_program` has already closed rows for that run id. The effect looks harmless — the sweep only closes rows whose run has left their pause — but 223's skip table is the contract other slices and the hook doc read for "left alone", and D10's wording now overstates it. Either move the sweep after eligibility (it needs no directory, so it could stay where it is only by design intent) or say plainly that the sweep writes even when the call is skipped.

### [NOTE] `resume_bound_seconds` may be shorter than the longest resume

The bound is stated as "the longest a resume can take before recording its outcome", but the terminate step in 223 D8 ("terminate the child's process group, wait for exit, poll once more") spends a grace period for SIGTERM and can spend a second one for SIGKILL, and the formula adds only one grace period plus one poll interval, on top of the spawn and the final poll. If the bound is short, the sweep marks an in-flight resume `not_delivered`, which 223 D8 makes final and never overwrites. A stated margin, the second grace period, or a rule that the sweep only marks `not_delivered` once the resume child is gone would remove the risk.

### [NOTE] The state-home layout and prune list omit `logs/mcp/`

This slice fixes the log home and enumerates in State Management what is written there and how each thing ends, and D9 prunes answering logs, resume logs and calls-log days. 226 D6 writes two files per detached call under `logs_dir()/mcp/handle_pause/` and names no cleanup; it lands after 228, so nothing in the plan ever bounds them. Since the doc's own claim is that nothing Amoeba writes grows without bound, either add `logs/mcp/` to D9's rule or state that 226 owns its own cleanup.

### [PASS] Slice covers the plan entry, and dependency direction and the config/state split are correct

Every item in the plan entry for 228 is present (homes and legacy move; `dismiss`, `retract`, automatic close, limit reset; `set_up remove` for members, pairs and concept via 222's existing `concept: null`; pruning with `prune_after_days`; `wrong_checkout`; calls log), with no scope beyond it. `cli → operations → store, config, upstream` is preserved, `store/relocate.py` takes paths rather than reading the environment, only `config/home.py` reads `AMOEBA_HOME`/`XDG_STATE_HOME`/`Path.home`, and moving the store, `answering/` and `logs/` out of `~/.config` while leaving `config.yaml` is exactly the Amoeba rule about config versus state. The prune mechanism reuses existing calls rather than adding a watcher, which the architecture's "Nothing to run" requires.

### Run Digest

- Response length: 7558 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 642407
- Effort: backend default
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 930331 / 669184 / not computed / 160469 / 156859
- Duration: 1277.9 s
- Cost: $0.12 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
