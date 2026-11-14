---
docType: review
layer: project
reviewType: code
slice: human-cli
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/229-slice.human-cli.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: 898a3ee2a4a2b972886672d57f6e122500d2b85b
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 26
diffTruncated: false
effort: xhigh
turns: 27
promptTokens: 6545149
cachedTokens: 5957629
cacheWriteTokens: 587482
completionTokens: 78300
durationSeconds: 353.8
costUsd: 1.184312
costBasis: provider
runId: run-20261114-p6-1504e37d
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Not-a-project advice is printed twice, and `rm` is told to run `add`"
    location: "src/amoeba/cli/render/registration.py:150"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "The operations layer emits CLI syntax, and the fix text is defined twice"
    location: "src/amoeba/operations/add.py:41"
  - id: F003
    severity: concern
    category: architectural-decay
    summary: "Dedup runs in two places, and the size cap matches the rendered text only by test"
    location: "src/amoeba/answering/source_reads.py:294"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "`source_reads.py` is 326 lines"
    location: "src/amoeba/answering/source_reads.py:268"
  - id: F005
    severity: note
    category: architectural-decay
    summary: "`build_parser` is about 80 lines"
    location: "src/amoeba/cli/parser.py#build_parser"
  - id: F006
    severity: note
    category: consistency-rot
    summary: "Status rejections print `rejected: : …` when no code is set"
    location: "src/amoeba/cli/render/waiting.py:94"
  - id: F007
    severity: note
    category: documentation-drift
    summary: "Re-adding a removed member silently resets its rules and allow/deny lists"
    location: "src/amoeba/operations/set_up.py#_merged_rules"
  - id: F008
    severity: note
    category: type-contract-debt
    summary: "`SetUpResult.changes` is a computed field on a model that forbids extra keys"
    location: "src/amoeba/operations/set_up_models.py#SetUpResult"
  - id: F009
    severity: note
    category: type-contract-debt
    summary: "`Any` is used for the subparser plumbing"
    location: "src/amoeba/cli/parser.py#_command"
  - id: F010
    severity: pass
    category: correctness
    summary: "Import following: depth, cycles and out-of-repo paths"
    location: "src/amoeba/answering/import_follow.py#follow_imports"
  - id: F011
    severity: pass
    category: correctness
    summary: "Renderer tables and the settled-question SQL agree with the code"
    location: "src/amoeba/cli/render/waiting.py#PAUSE_MEANING"
---

# Review: code — slice 229

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 26 successful tool call(s) of 26 made; 450658 of 450658 diff characters reached the model

## Findings

### [CONCERN] Not-a-project advice is printed twice, and `rm` is told to run `add`

In a directory that is not a Context Forge project, the CLI prints the same fix twice. The rejection detail already contains it: `operations/add.py:41` puts "run `cf init` here or pass --project NAME" into the detail, and `operations/project_lookup.py:40` appends cf's message. `_rejection` then prints "to fix, run one of: cf init / amoeba add --project NAME" (lines 150–152) for every not-a-project result.

That branch ignores `removing`, so `amoeba rm` in a non-project directory also suggests `amoeba add --project NAME`. That command registers a project rather than removing anything. `operations/rm.py:37` gives `rm` its own detail ("name the member to remove"), so the two messages disagree. No test catches this: `tests/cli/render/test_registration.py` uses a synthetic detail, and `tests/cli/test_rm_cli.py` checks only the `rejected:` prefix.

### [CONCERN] The operations layer emits CLI syntax, and the fix text is defined twice

`add.py:41-43` writes `cf init` and `--project NAME` into an operations-level constant. `rm.py:37` and `operations/answer.py:98` also build CLI command text. The operations layer serves both doors, including MCP, so door-specific wording does not belong there. The same fix is defined again in `cli/render/commands.py:18` (`CF_INIT_COMMAND`) and `:59` (`add_project_command`). The renderer should own the command text, with one definition of each command.

### [CONCERN] Dedup runs in two places, and the size cap matches the rendered text only by test

`_Reading.take` (`source_reads.py:294-296`) drops duplicate rule pieces to compute `chars`, which is what `passages_max_chars` is checked against. `_committed_passages` (`passages.py:316-320`) builds a second `RuleDeduper` and drops the same pieces again to produce passages. Each file is also cut twice. The two counts stay equal only because `test_the_counted_text_equals_the_numbered_text` checks them. One function that yields the deduped pieces per file, used by both callers, would remove the drift risk and the second cut.

### [NOTE] `source_reads.py` is 326 lines

The project guide asks for files of about 300 lines. The file now holds git reads, listings, plan selection and the `_Reading` ledger. `_Reading` (lines 268–305) is a separate concern and could move out alongside the dedup change above.

### [NOTE] `build_parser` is about 80 lines

`build_parser` (`parser.py:50-129`) is above the roughly 50-line guideline. It is a flat table, so grouping it into per-command helpers would be a small change.

### [NOTE] Status rejections print `rejected: : …` when no code is set

`render_waiting` maps a missing `rejection` to an empty code, so the line reads `rejected: : …`. `simple.py`'s `_rejected` falls back to plain `rejected`. `StatusResult.rejection` is optional (`operations/status_models.py:159`). I found no path that produces a rejected status with no code, so this is cosmetic. It should use the same fallback as `_rejected`.

### [NOTE] Re-adding a removed member silently resets its rules and allow/deny lists

`get_member` returns active members only (`store/programs.py`), so a removed member comes back with `stored = None`, which means default rules and empty allow/deny lists. The tests (`test_set_up_remove.py`, `test_add.py`) assert this, so it is a deliberate choice. The `add` module docstring says a removed member is revived "where it was", which is accurate for the program only. A reader could assume the rules survive, so the docstring should say what is reset.

### [NOTE] `SetUpResult.changes` is a computed field on a model that forbids extra keys

`changes` is a `computed_field` on a `FrozenModel` with `extra="forbid"`, so `model_dump` emits it. A round trip through `SetUpResult.model_validate(result.model_dump())` would probably reject that key. Nothing in the diff does this round trip, and I did not run it. Computing `changes` at the JSON boundary (`wiring.result_document`) would avoid the trap.

### [NOTE] `Any` is used for the subparser plumbing

`_command(commands: Any, …)` and the `register_add/rm/list(commands: Any, …)` helpers drop the type of argparse's subparsers action. A small Protocol with `add_parser` would keep the types. Pyright strict accepts explicit `Any`, so this is debt, not a failure.

### [PASS] Import following: depth, cycles and out-of-repo paths

I read `follow_imports` and traced the depth check. The entry is depth 0, and a chain `CLAUDE.md → f1 → f2 → f3` is read. `f4` declines with the full chain, which matches `test_a_chain_of_depth_four_declines_naming_the_chain`. `has_read` runs before the depth check, so a cycle ends quietly. `_resolve` normalizes the path and rejects any `..` escape before reading. `_is_present` consults `ls-tree` before `show`, so a missing directory counts as absence, not as an error.

### [PASS] Renderer tables and the settled-question SQL agree with the code

`PAUSE_MEANING` keys equal `HANDLED_BY_HANDLE_PAUSE` (`operations/status_runs.py:40-46`). `CLEARS_ON_LISTING` and `RUN_STATE_TEXT` cover every `UnplacedReason` and `WaitingRunState` value. `ENDED_TEXT` covers `ClosedReason` and `AnsweredBy`. The `OperationResult` union (`wiring.py:98-110`) lists the same 11 types that `render_result` matches. In `store/sql.py`, both halves of `SELECT_SETTLED_SINCE` return 7 columns, and `ORDER BY 7 DESC` refers to `settled_at` on both sides.

### Run Digest

- Response length: 10801 chars
- Response is newline-free: no
- Tool calls made: 26
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 27
- Tokens — prompt / cached / cache write / completion / reasoning: 6545149 / 5957629 / 587482 / 78300 / not computed
- Duration: 353.8 s
- Cost: $1.18 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
