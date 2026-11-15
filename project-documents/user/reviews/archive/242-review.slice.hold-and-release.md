---
docType: review
layer: project
reviewType: slice
slice: hold-and-release
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/242-slice.hold-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 604a316c966f76c5daa7186de28ba5027f0d4eca
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
effort: xhigh
turns: 20
promptTokens: 1763634
cachedTokens: 1563423
cacheWriteTokens: 200187
completionTokens: 97247
durationSeconds: 450.5
costUsd: 0.509018
costBasis: provider
runId: run-20261115-slices-plan-e05f9be0
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "The design's dependency on 241 contradicts the plan and its \"share no code\" claim"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:60"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The held-claim move omits `claimed_at`, which the dead-claim rules read"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:142"
  - id: F003
    severity: concern
    category: alignment
    summary: "Two architecture divergences are missing from the Departures list"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:250-255"
  - id: F004
    severity: concern
    category: error-handling
    summary: "A failed release start leaves no reason where the PM looks"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:223"
  - id: F005
    severity: concern
    category: integration
    summary: "The design edits modules other slices own, and leaves a contract sentence false"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:64"
  - id: F006
    severity: concern
    category: operator-walkthrough
    summary: "The live-migration step strands running processes"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:354"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Recovery and some sections are heavier than the plan and architecture need"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:221"
  - id: F008
    severity: note
    category: integration
    summary: "The integration list contradicts itself"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:282"
  - id: F009
    severity: pass
    category: scope
    summary: "Scope matches the plan entry, and nothing in it is deferred"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:38-54"
  - id: F010
    severity: pass
    category: alignment
    summary: "Layering and dependency direction hold"
    location: "project-documents/user/slices/242-slice.hold-and-release.md:92"
---

# Review: slice — slice 242

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] The design's dependency on 241 contradicts the plan and its "share no code" claim

The design says 241 must be "built and integrated before this slice" and that "the slices share no code". The plan's 242 entry says "Dependencies: 240. Independent of 241." (`user/architecture/240-slices.agent-messaging.md:77`), and its implementation order says "242 and 243 need only 240" (`:114`). The frontmatter lists only `240` and `interfaces: []`, though the body names provided and consumed interfaces (lines 6–8). The code claim is wrong. 241 changes `sweep` (adds session pruning and a parameter, 241 design line 293), and 242 changes `sweep`'s callers and `status`, `list` and `handle_pause`, which 241 also touches. The migration numbering is a real reason to sequence them. The shared call sites are the reason to write that down. Reconcile the plan and the design, and fill in the frontmatter.

### [CONCERN] The held-claim move omits `claimed_at`, which the dead-claim rules read

The `waiting_on_request → claimed` move (D3) sets `answering_run_id`, `passages` and `evidence`. It does not set `claimed_at`. The dead-claim table in 223 (223 D7, lines 155–161) decides every `claimed` row by whether `claimed_at` is young or old. `claimed_at` is a `questions` column (222 design line 113). The design says held claims follow those rules "unchanged" (line 352), and says the claim differs from `start_new_claim` only in being an update (line 98). The column list as written leaves `claimed_at` NULL, so a crashed held claim has no age to test and no automatic exit. Add `claimed_at` to D3's column list.

### [CONCERN] Two architecture divergences are missing from the Departures list

Architecture line 99 says the expiry's "stored change, and the deliveries and question moves that follow from it, are written by the sweep." D4 has `handle_held` move an expired request's question to `waiting_on_pm` (line 163, and the note at line 168), so the question moves before the sweep records the expiry. Architecture line 159 names only `done` and sweep expiry as release triggers. D7 (lines 211–217) also releases on `decline`, `cancel` and `rm`. The plan wants those triggers, but the architecture does not name them. The Departures list has four items and neither of these. Declare both, or keep the expiry move in the sweep and say why it cannot be there.

### [CONCERN] A failed release start leaves no reason where the PM looks

D7 logs a `LaunchError` or `AmoebaScriptMissing` and leaves the row `waiting_on_request`. D9 (line 238) shows `waiting on request <id> (<state>)` with no `next` and no failure. If the start fails every time (script missing, spawn refused), the PM sees a finished request that nothing acts on, with no reason. Architecture line 70 requires "No silent drops", with a failure "visible in `inbox` or `list`". The walkthrough's "Dead ends found: none" (line 369) misses this. The request read that `status` and `decisions` make for held rows also has no stated failure handling; lines 173 and 286 cover only `handle_pause`. Record the last start problem on the held row (no migration is needed, since this design leaves `waiting_detail` unset on those rows) and show it in `status`. State what `status` and `decisions` do when the read fails.

### [CONCERN] The design edits modules other slices own, and leaves a contract sentence false

240's design lists what 242 takes from it: `RequestView`, `effective_state`, and the writers (240 design line 269). It has no by-id read. 242 adds `get_request` to 240's `store/messages.py` (line 64), and moves `resolve_amoeba_script` out of `mcp/detached.py` (lines 66 and 91), a module 226 owns (226 design line 42). The plan assigns neither edit to 242. 240 is not built yet (plan line 33 is unchecked), so its design can add `get_request` at no cost, and should. Also, 228's store-contract text names 003's `questions` rebuild as "the one exception" and requires a new one to carry its own justification (228 design line 309). Migration 8 is a second rebuild. D2 gives the justification (line 128), but the docs item at line 274 does not say the exception sentence changes.

### [CONCERN] The live-migration step strands running processes

The migration step is "migrate by running `amoeba list`". Stopping processes is required only for restore. Under the existing newer-schema guard (line 266), a process from the schema 6 build refuses the migrated store. Any open session's `amoeba-mcp` will fail every call until it restarts. 241's live-store step names "the restart of client sessions" (241 design line 309). 242 omits it, so "Dead ends found: none" (line 369) is wrong. Add the stop-and-restart step to the migration, and a read-back from a restarted session.

### [CONCERN] Recovery and some sections are heavier than the plan and architecture need

The plan gives 242 "Relative Effort: 3" (plan line 80) and names the release trigger but not recovery. The design adds recovery to three commands, a gate, a retry rule for never-runnable rows, and a touch CAS on `updated_at` (line 221). That CAS is tested by "two concurrent recoveries start one child" (line 301). D4 already makes a redundant start harmless, because the second `handle_pause` loses the claim CAS (line 153). So the CAS only avoids a spawn, and a plain write of `updated_at` gives the gate what it needs. Keep recovery, since without it a lost start ends only by PM `dismiss` or `answer`. Cut the CAS and its test. The "Patterns and Conventions" section (lines 257–261) restates AGENTS.md, and "Risk Assessment" (lines 329–337) restates the architecture's risks. Each can shrink to a line or two.

### [NOTE] The integration list contradicts itself

"Provides to Other Slices" lists `waiting_on_request`, `questions.request_id` and `release_held`, then says "243 and 244 do not use them." Either the list is for consumers that exist, or the sentence is wrong. The plan says "Provides `waiting_on_request` and the request-done trigger" (plan line 78). Reword the item.

### [PASS] Scope matches the plan entry, and nothing in it is deferred

Every item in the plan's 242 entry has a home in the design: migration 8, the exact-id hold, `done` before and after the pause, the check and screen, the answer limit, the declined, cancelled, expired and `rm` moves, release on terminal states, retry of a refused resume, the exits, `dismiss`, `status` and `decisions`, and the live store. The Excluded items are other slices or the architecture's one-wait-on-one-request rule. I found no "later" or "build if needed" language.

### [PASS] Layering and dependency direction hold

The import chain stays `cli/mcp → wiring → operations → store, answering, upstream`. `resolve_amoeba_script` is called in `wiring` and passed down, so `operations` never imports `mcp`. Line 258 keeps every question move compare-and-set and no transaction open across a subprocess.

### Run Digest

- Response length: 10044 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 1763634 / 1563423 / 200187 / 97247 / not computed
- Duration: 450.5 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
