---
docType: review
layer: project
reviewType: slice
slice: store-config-and-set-up
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/222-slice.store-config-and-set-up.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: cb6a42e514d374cffa7ff15232acd2bb3c5b3469
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
effort: high
turns: 8
promptTokens: 442267
cachedTokens: 321989
cacheWriteTokens: 120268
completionTokens: 10343
durationSeconds: 81.3
costUsd: 0.617563
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Store, config and home match the architecture"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#technical-decisions"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Working-directory resolution runs after the commit, so a Context Forge failure misreports a committed write"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:133"
  - id: F003
    severity: concern
    category: layer-boundaries
    summary: "Malformed-request handling sits in the CLI, so the MCP door must duplicate it"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:129"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Request-document read and parse failures have no outcome or exit code"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:296-299"
  - id: F005
    severity: note
    category: scope
    summary: "The baseline schema pins columns for tables that 223, 224 and 227 design"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:177-180"
  - id: F006
    severity: note
    category: proportionality
    summary: "Per-member `add` items are the heaviest part of the authorize mechanism"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:175"
---

# Review: slice — slice 222

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Store, config and home match the architecture

- **Home and tests:** D1 and D10 give one fixed per-user location, one environment variable, and one reader of it (`config/home.py`). An AST test enforces that.
- **Config:** D5 puts the models, cost cap, answer limit and default not-authorized list in a user-level config with no defaults in code. Per-member rule paths and authorize changes go on the member at set-up.
- **Record shape:** D3 drops `requests_initiative` and the overrides table, moves `consumed` onto the pair, and keeps one `pm_marker` row. It keys questions on run id and `paused_at`, and it stores no run or slice state.
- **Writers:** D2 relies on the SQLite busy timeout and adds no lock file, as the architecture says.
- **Imports:** The import direction in Component Structure is acyclic. `store` never imports `config`, and `upstream` never imports `answering`.
- **Slice plan:** Every success criterion in the 222 plan entry is covered.

### [CONCERN] Working-directory resolution runs after the commit, so a Context Forge failure misreports a committed write

- **The gap:** Data Flow step 5 calls `cf` for the caller's directory after the transaction commits, to fill `working_directory`. When the request names every member explicitly, this is the first `cf` call for that directory.
- **What the caller sees:** D6 raises a `CfCallFailed` as `ContextForgeError`. D9 maps that to exit 3 with "nothing on stdout". The program was already written, but the caller is told the operation failed.
- **Why it matters:** The design deliberately keeps subprocesses out of the write lock (step 3). It then adds one after the commit with no handling for its failure.
- **Fix:** Resolve the directory to a `cf` project id in step 3, with the other `cf` calls. After the commit, only look up membership in the store, with no subprocess. Alternatively, state that a failure here still yields the committed result with a `working_directory` error entry.

### [CONCERN] Malformed-request handling sits in the CLI, so the MCP door must duplicate it

- **Where it lives:** Data Flow step 1 has `cli` parse the YAML, validate into `SetUpRequest`, and reject malformed documents "listing every problem". D7 defines `malformed` as a `SetUpProblem` code inside `SetUpResult`. The code that turns pydantic errors into `SetUpProblem`s and a `rejected` result is therefore in `cli`.
- **The conflict:** The architecture says MCP and the CLI have "no logic of their own". The slice's Integration Requirements say 226 wraps `set_up` "with no logic of its own". With this split, 226 must re-implement that conversion or return a different error shape. That duplicates logic and puts logic in a door.
- **Fix:** Put `parse_set_up_request(document) -> SetUpRequest | SetUpResult(rejected)` in `operations/set_up.py`. Both doors then call the same function.

### [CONCERN] Request-document read and parse failures have no outcome or exit code

- **The gap:** `amoeba set_up --file <path|->` is a new I/O path, and D9 presents its exit codes as complete: 0, 1, 2 and 3. These cases fall outside that table:
  - A missing or unreadable `--file` path.
  - Non-UTF-8 text in the file.
  - YAML that does not parse.
  - A document that parses to something other than a mapping.
  - `-` with no data on stdin.
- **Why the table does not cover them:** `malformed` is defined only for `SetUpRequest` validation failures. The typed operational errors listed for exit 3 (`ConfigError`, `AmoebaHomeError`, `ContextForgeError`, `StoreError`) do not include file errors. Config-file failures are enumerated in D5, but the request file's are not.
- **Fix:** Say whether each case is a `malformed` problem (exit 1) or a typed `RequestFileError` (exit 3). Add a test for each.

### [NOTE] The baseline schema pins columns for tables that 223, 224 and 227 design

- **Why it stays:** The slice plan assigns the whole baseline to 222, and D3 handles later changes with migration `002`. This is not a cut candidate.
- **Pinned detail:** The `answers` columns (`resume_outcome`, `resume_log`, `evidence`) and `questions.answering_run_id` are 223's design. `releases.UNIQUE (member_id, commit_sha)` is 227's. That unique key supports one version per commit, whereas the architecture identifies a report by member, commit and version.
- **Inconsistency:** `waiting_reason` is "checked in code" because `DeclineReason` "belongs to answering". `answered_by` is also an answering vocabulary, yet it gets a SQL `CHECK`. The store may already import `answering.values`. One rule should cover both.
- **Suggestion:** Have 223 and 227 revisit these columns when they are designed, and settle the `waiting_reason` rule now.

### [NOTE] Per-member `add` items are the heaviest part of the authorize mechanism

- **What `add` costs:** Allowing a config item for a member (`allow`) is the stated PM need. Adding new items per member (`add`) brings several things with it:
  - the `description` and `screen_phrases` columns,
  - the `authorize_key_taken` check,
  - ordering rules in D8.
- **Why it stays:** The plan entry and the architecture both say "any change to what its answers may authorize", so `add` is in scope.
- **If cut:** Use deferral if 223's live trial shows `add` is never used. The only schema change it would need is a new migration.

### Run Digest

- Response length: 6241 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 442267 / 321989 / 120268 / 10343 / not computed
- Duration: 81.3 s
- Cost: $0.62 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
