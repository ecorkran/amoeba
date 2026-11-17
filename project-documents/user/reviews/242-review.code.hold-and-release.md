---
docType: review
layer: project
reviewType: code
slice: hold-and-release
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/242-slice.hold-and-release.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261116
dateUpdated: 20261116
reviewedSha: 369ff11fd8d59d945ca7c49a9cef81fe96d4cb2b
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 36
diffTruncated: false
effort: xhigh
turns: 37
promptTokens: 4450605
cachedTokens: 4039695
cacheWriteTokens: 410876
completionTokens: 68938
durationSeconds: 307.9
costUsd: 0.844868
costBasis: provider
runId: run-20261116-p6-0926c78b
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Quoted-data notice is set for decisions and status but never printed in text output"
    location: "src/amoeba/cli/render/simple.py:84"
  - id: F002
    severity: concern
    category: performance-resource
    summary: "Start trigger's per-call cap does not bound concurrent children"
    location: "src/amoeba/operations/request_release.py:47"
  - id: F003
    severity: note
    category: other
    summary: "Import block split by a blank line and comment in detached module"
    location: "src/amoeba/mcp/detached.py:24-28"
  - id: F004
    severity: note
    category: documentation-drift
    summary: "Dangling comment in CLI test"
    location: "tests/cli/test_hold_release_cli.py:30"
  - id: F005
    severity: pass
    category: correctness
    summary: "Migration 008 keeps every column and constraint of `questions`"
    location: "src/amoeba/store/schema/008_waiting_on_request.sql:19"
  - id: F006
    severity: pass
    category: performance-resource
    summary: "Request-release logs have a named cleanup"
    location: "src/amoeba/operations/prune.py:91"
  - id: F007
    severity: pass
    category: correctness
    summary: "Every held state has an exit"
    location: "src/amoeba/operations/cancel.py:49"
  - id: F008
    severity: pass
    category: error-handling-observability
    summary: "Spawn failures do not escape the start trigger"
    location: "src/amoeba/operations/processes.py:54"
---

# Review: code — slice 242

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 36 successful tool call(s) of 36 made; 257139 of 257139 diff characters reached the model

## Findings

### [CONCERN] Quoted-data notice is set for decisions and status but never printed in text output

`decisions()` sets `DecisionsResult.notice` when any record came from a request (src/amoeba/operations/decisions.py:99-104), and `status` sets `StatusResult.notice` for held and request-waiting entries (src/amoeba/operations/status.py:211-216). `render_decisions` (simple.py:84-97) never reads `result.notice`. It prints `record.question` and `record.answer`, which can carry another repo's request result. `render_waiting` (src/amoeba/cli/render/waiting.py:90-118) does not read it either. The only text-path notice comes from `message_sections` (src/amoeba/cli/render/messages.py:46-55), and only when a Requests or Rejected-calls section prints. A status with a request-declined waiting entry, whose `waiting_detail` is the addressee's reason text (waiting.py:142-143), can therefore show other repos' text with no notice. The JSON document carries the field, so only human output is affected. `tests/cli/test_render_held.py` covers only the HELD line, and no test checks the notice in decisions or status text. Fix: emit `result.notice` first in `render_decisions` and `render_waiting` when it is set, and add a render test for each.

### [CONCERN] Start trigger's per-call cap does not bound concurrent children

`MAX_STARTS_PER_CALL = 5` (line 37) limits starts per call, and the docstring says "children cannot pile up" (lines 6-10). The cap does not limit concurrency. Each started child runs `handle_pause`, whose `finally` (src/amoeba/operations/handle_pause.py:87-91) calls `start_ended_held` again. So when a child finishes its answering run, it starts up to five more due rows. The `answering_wait_seconds` gate only limits re-attempts of one row. A burst of ended requests, such as the `rm` cascade that cancels every request from a removed member, can therefore leave all N held questions in answering runs at once, each running an LLM call. The load test counts starts through an in-process fake, so it cannot see concurrent child processes. Fix options: a global cap on live `handle-pause` children, or letting only the operation's own call start rows and not children (accepting a slower drain). Either way, the docstring should state what is actually bounded.

### [NOTE] Import block split by a blank line and comment in detached module

A blank line and a `# Re-exported` comment separate `from amoeba import wiring` from the other first-party imports. Ruff's isort rule (I001) will probably rewrite this block and fail the pre-commit lint. I could not run ruff, so this is unverified. The `as` re-export form itself is fine.

### [NOTE] Dangling comment in CLI test

The comment "How long the test waits for the detached child's calls-log line…" sits after `HELD = ...` and documents no constant. The wait bounds live in `tests/release_child_wait.py`. Remove it or move it to the wait helper.

### [PASS] Migration 008 keeps every column and constraint of `questions`

I compared the rebuilt table with 003 and the ADD COLUMN migrations. Only 002 adds columns to `questions`, and 003's rebuild already includes them, so the copy list is complete. The schema directory has no index, trigger or view on `questions`. `migrate()` keeps foreign keys off and runs `foreign_key_check` before commit (src/amoeba/store/migrations.py:118-152). The state CHECK matches `QuestionState`, and the `closed_reason` CHECK is kept.

### [PASS] Request-release logs have a named cleanup

`prune` walks all of `logs/` (prune.py:83). A `request-release/` file falls through to the default branch of `_removable_log` and is removed by age. An emptied directory is removed, since only the answering, resume and calls directories are protected.

### [PASS] Every held state has an exit

A held question ends when its request is done, declined, cancelled or expired (`_evaluate` in src/amoeba/operations/pause_held.py), by a PM answer (`add_pm_answer` sets `answered` from any state, src/amoeba/store/answers.py:127-158), by dismiss, or by the sweep. Cancel is allowed from both `open` and `accepted` (`_CANCELLABLE`), so a stalled accepted request still exits through the sender's cancel.

### [PASS] Spawn failures do not escape the start trigger

`start_child` turns `OSError` into a `LaunchError` (processes.py:72-93), and `_start` writes that to the calls log instead of raising. Together with the `StoreError` handling in `start_ended_held`, this supports the "never raises" promise in `request_release.py`.

### Run Digest

- Response length: 9788 chars
- Response is newline-free: no
- Tool calls made: 36
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 37
- Tokens — prompt / cached / cache write / completion / reasoning: 4450605 / 4039695 / 410876 / 68938 / not computed
- Duration: 307.9 s
- Cost: $0.84 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
