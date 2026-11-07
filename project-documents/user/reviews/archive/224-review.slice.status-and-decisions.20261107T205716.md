---
docType: review
layer: project
reviewType: slice
slice: status-and-decisions
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/224-slice.status-and-decisions.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: ca1938b01d5b2356922fd3a5e397af1615a22a1c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: high
turns: 10
promptTokens: 525012
cachedTokens: 408956
cacheWriteTokens: 116044
completionTokens: 7200
durationSeconds: 61.8
costUsd: 0.577936
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice state dropped from `status`, which the slice plan entry assigns to this slice"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#Technical Scope"
  - id: F002
    severity: concern
    category: architecture-alignment
    summary: "A question whose run is missing from the listing disappears from `status`, against \"never dropped\""
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D4 — Placing runs, and which questions are shown"
  - id: F003
    severity: concern
    category: integration
    summary: "225's \"from `decisions` alone\" claim contradicts the slice's own D5, and the count misses abandoned questions"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#Integration Requirements"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Timeout and hang handling is missing for the new subprocess paths"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D1 — Reading runs"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Parts of the design can be cut or deferred"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D5 — `decisions`"
  - id: F006
    severity: note
    category: scope
    summary: "D9 `wrong_checkout` and the `classify_pause` extraction are outside the plan entry but trace to 223 and 222"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D9 — `wrong_checkout` in `handle_pause`"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and the read-don't-mirror principle"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#Architecture"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure handling for the external dependencies is explicit"
    location: "project-documents/user/slices/224-slice.status-and-decisions.md#D1 — Reading runs"
---

# Review: slice — slice 224

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice state dropped from `status`, which the slice plan entry assigns to this slice

The slice plan entry for 224 says "Run state is read from Squadron and slice state from Context Forge, never copied into the store." Technical Scope (Excluded) says `status` "does not read or show Context Forge slice status" and shows only the stored `slice_label`. The architecture's `status` row lists running, blocked and why, waiting questions and unresumed answers, with no slice state. So the cut is defensible. But D2 flags the program-scope deviation from the plan explicitly, and this cut gets no deviation note and no reason. Either record it as a deliberate deferral that corrects the plan entry, or restore a minimal read. A one-line decision that the plan entry is amended would be enough. The slice should not drop plan scope silently.

### [CONCERN] A question whose run is missing from the listing disappears from `status`, against "never dropped"

The architecture principle is "Fail where someone can see it. A question that can't be handled stays visible in `status` with the reason. It is never dropped." D4 omits any stored question whose run is not in the listing, or is no longer paused at its `paused_at`. Two gaps follow.
- D1 calls `sq runs list --json` with no `--all`, and nowhere says what the default listing includes. If #303's default is bounded (recent runs, active runs only, or the current directory), a waiting question can drop out of `status` while its run is still paused. D4 treats "absent from the listing" the same as "moved on". State what the default listing must cover and fail loudly if the recorded fixture shows otherwise. Or use `--all` and say why that is not needed.
- A `waiting_on_pm` row whose run has moved on is invisible in `status`, and `decisions` shows it only if it has an answer. The slice defers closing these rows. The consequence is that these questions are never counted anywhere. See the next finding.

### [CONCERN] 225's "from `decisions` alone" claim contradicts the slice's own D5, and the count misses abandoned questions

Integration Requirements says 225 can compute "sent to the PM by reason" from `decisions` alone. D5 builds that count from PM answers on questions that waited, and says "Questions still waiting appear in `status`." So the count needs both operations. A question that was declined, then resumed outside Amoeba or whose run ended, never reaches either. The plan's 225 criterion is "every question accounted for in `decisions`", and the architecture's scenario A test depends on the share answered without the PM. Without a source for waited-and-abandoned questions, 225 undercounts the questions that went to the PM. Either give `decisions` or `status` a way to report these, or state which of the two operations 225 must combine and accept the undercount explicitly.

### [CONCERN] Timeout and hang handling is missing for the new subprocess paths

`status` adds three subprocess paths: `sq runs list --json`, `cf list projects --json`, and one `cf get` per distinct run directory through `project_of`. Non-zero exit, bad JSON and missing fields are covered (D1, D6). A hung or very slow `sq` or `cf` call is not mentioned. Neither is a `project_of` failure other than `CFProjectNotFound`, or what happens when one of several `cf get` calls fails after the others succeeded. `status` is the call an agent makes to see what is stuck, so a hang here matters. Name the timeout, or the 222/223 timeout the readers inherit, and state that a failed per-directory lookup is `ContextForgeError` (exit 3) and does not silently unplace the run.

### [CONCERN] Parts of the design can be cut or deferred

The effort is rated 3, and the design carries the following. Each item below is something no consumer in the slice plan or architecture requires.
- `decisions --limit` has no consumer: 225 reads everything since its start, and 226 wraps what exists. Cut it, with its test and the `read_through` interaction it creates.
- `name_problem: not_a_cf_project` and the null-name path in D6 add a second member shape for a case (a member deleted from Context Forge) that `set_up` already guards. Fail with `ContextForgeError`, or keep it only if a named case needs it.
- `status` per-member `runs` repeats every listed run, alongside `waiting_on_pm`, `answered_not_resumed` and `missed_hooks`, each with its own field set and a `next` object. The action lists plus `pause` classes would carry the same information. Consider dropping the full `runs` list or the per-list duplicated fields.
- `PauseClass` has 11 values and `status` shows most of them as "stopped". Collapse the display-only classes (`not_paused`, `no_question_text`, `other_checkpoint`, `prompt_only`, `settled`) into the existing fields unless `handle_pause` needs the distinction.

None of this is a violation by itself. The point is that the combined weight is high for a read-side slice.

### [NOTE] D9 `wrong_checkout` and the `classify_pause` extraction are outside the plan entry but trace to 223 and 222

The architecture and the slice plan entry do not list `wrong_checkout`, the `classify_pause` refactor of 223, or the schema-test inventory. 223 D3 explicitly defers `wrong_checkout` until #303 records the directory, and 222 D3 assigns the schema test to this slice. The plan criterion "a test checks the schema" covers D10. Shared classification is justified by the plan's "a missed hook found by `status` and passed to `handle_pause` is answered". These are acceptable. D9's dependence on a run-file schema version "that #303 lands with" is under-specified until #303 ships, but D1 handles that with a `BLOCKED:` line. Keep the D3 cross-check test, because it guards the shared-definition requirement.

### [PASS] Layering, dependency direction and the read-don't-mirror principle

The import direction `cli → operations → store, config, upstream` matches 222, and the `upstream` readers import nothing from `store` or `operations`. `status` and `decisions` write nothing, and `mark_read` writes only `pm_marker`. D10 turns "read, don't mirror" into a schema test with a forbidden-name list. D7's `MAX()` update under `BEGIN IMMEDIATE` handles concurrent markers and never moves backward, and a record written after a `decisions` call stays unread. `read_through` is withheld for narrowed or time-based listings, which keeps the single program-wide marker safe. No subprocess runs inside a store transaction. The D2 widening (an explicit program from anywhere, and all programs outside a member) is stated and reasoned, and fits the architecture's note that MCP sessions start anywhere.

### [PASS] Failure handling for the external dependencies is explicit

The Squadron-with-no-`--json` case, the missing-directory case, the unreadable run file (`run_file_unreadable`, which does not hide other runs), and the `cf` failure each have a named handling and exit code. Tracking #303 as an external prerequisite, with fixtures recorded from real output before completion, follows the project's parsing rule. Both rejected alternatives are stated with reasons.

### Run Digest

- Response length: 8250 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 525012 / 408956 / 116044 / 7200 / not computed
- Duration: 61.8 s
- Cost: $0.58 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
