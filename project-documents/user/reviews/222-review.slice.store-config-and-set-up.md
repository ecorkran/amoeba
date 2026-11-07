---
docType: review
layer: project
reviewType: slice
slice: store-config-and-set-up
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/222-slice.store-config-and-set-up.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: d7b8b9ba5b8d4c5c270bed7ce70a7f987d92923d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
effort: high
turns: 7
promptTokens: 334563
cachedTokens: 215561
cacheWriteTokens: 118994
completionTokens: 11731
durationSeconds: 92.4
costUsd: 0.615701
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Design matches the architecture's store, config and set-up decisions"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#Overview"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Layering and dependency directions are correct"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#Component Structure"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#D2"
  - id: F004
    severity: pass
    category: proportionality
    summary: "Scope is proportionate and the earlier review's concerns are resolved"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#D3"
  - id: F005
    severity: note
    category: hidden-dependency
    summary: "`set_up` needs the whole answering config but uses only the authorize item keys"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:130"
  - id: F006
    severity: note
    category: error-handling
    summary: "Failures before a claim leave no record when `handle_pause` runs from the detached hook"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md#D8"
  - id: F007
    severity: note
    category: integration-contract
    summary: "`releases` has no marker for when a version is added to an already-reported commit"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:176"
  - id: F008
    severity: note
    category: under-specification
    summary: "Minor internal inconsistencies in D6 and the component list"
    location: "project-documents/user/slices/222-slice.store-config-and-set-up.md:228"
---

# Review: slice — slice 222

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Design matches the architecture's store, config and set-up decisions

- **Location and test isolation.** One fixed per-user store, and one environment variable read in one place (D1, D10). This matches "Where things live".
- **Config.** Models, cost cap, answer limit and the authorize list are in one user-level config, with no defaults in code (D5).
- **Per-member settings.** Rule paths plus changes to the authorize list live on the member at set-up (D3, D7, D8).
- **Schema.** `consumed` is on the dependency pair, and `requests_initiative` and the overrides table are gone.
- **Question record.** It is keyed on run id and `paused_at`, with the states and resume outcomes the architecture fixes.
- **"Read, don't mirror."** The schema holds no run or slice state, and Context Forge names and paths are read from `cf` when needed (State Management).
- **Single marker.** `pm_marker` is a single row.
- **"One operation, two doors."** `set_up` validates its own input, so 226 can wrap it with no logic of its own.
- **Members.** A member resolves from the working directory through Context Forge, and worktrees of one repo are one member.
- **Slice plan.** Every success criterion in the plan entry for 222 has a matching requirement here. The plan's backlog item for member and pair removal is the same deferral as this doc's Future Work.

### [PASS] Layering and dependency directions are correct

- `store` imports only `answering.values` and takes its path as an argument.
- `config` imports `answering.settings` and nothing from `store`.
- `upstream` imports nothing from the new packages.
- Combining config with member settings sits in `operations`, the one layer allowed to see both.
- Only `cli` (and later 226) calls `amoeba_home()`, and `tests/test_import_boundaries.py` enforces the direction.

### [PASS] Failure modes are enumerated for each new I/O path

- **Write contention:** `BEGIN IMMEDIATE` plus the busy timeout, mapped to `StoreBusyError` naming the path and timeout.
- **Open failures:** each has a typed error (`StorePermissionError`, `StoreCorruptError`, `StoreSchemaError`).
- **Newer schema:** the store is left untouched.
- **`cf` failure or hang:** it goes through the bounded `run_cf`, and all `cf` calls finish before the transaction opens, so no subprocess holds a write lock (Data Flow step 4).
- **Request document and config:** both have explicit exit codes and error forms (D9, D5), and a bad config lists every problem in one pass.
- **Verification:** an 8-process contention test and a forced-timeout test.

The one busy-timeout figure the architecture implies is restated as 5.0 seconds. The architecture states no other NFR for this slice's paths.

### [PASS] Scope is proportionate and the earlier review's concerns are resolved

- **Earlier concerns closed.**
  - The authorize list can now be extended per member through `authorize_deny` (D7, D8).
  - D3 states an `ALTER TABLE … ADD COLUMN`-only rule for later migrations. The rule is consistent with SQLite's limits.
  - D11 now records a subdirectory fixture.
- **Rejected extras.** No lock file, `config init`, read-only open mode or removal path was added.
- **Why the speculative-looking parts stay.** The tables for 223, 224 and 227 come from the slice plan's "new baseline schema" scope. `member_answering` is the loader 221 leaves to this slice. It is also the only way to test the "allow an item for one member" behavior. Nothing here is cheap enough to cut without dropping assigned scope.

### [NOTE] `set_up` needs the whole answering config but uses only the authorize item keys

- **What happens.** Data Flow step 2 loads the full `UserConfig` for `set_up`. `set_up` reads only the `authorize_items` keys, to validate `authorize_allow` and `authorize_deny`.
- **Why it matters.** D5 makes every key a later slice adds to the config required as well. So each addition (223's resume wait, for example) makes `set_up` and the other operations fail until the PM edits `config.yaml`. That includes `status`, `report_release` and `changes`, which do not use answering settings.
- **Why it is only a NOTE.** There is one PM, the failure names the missing key, and it matches the plan criterion that a missing config value fails with a named error. It does not block this slice.
- **For later slices.** 224 and 227 should decide whether their operations take the whole `UserConfig` or only what they use.

### [NOTE] Failures before a claim leave no record when `handle_pause` runs from the detached hook

- **What happens.** `answering_for` raises `ConfigError` for a stale authorize key (D8). `AmoebaHomeError`, `StoreBusyError` and `ContextForgeError` are likewise operational errors that exit 3 with a stderr message.
- **Why it matters.** When 223 hits one of these inside a hook, nobody reads stderr, and the question has not yet been claimed. The architecture says a question that can't be handled "stays visible in `status` with the reason."
- **Why it is only a NOTE.** `status` still lists paused question runs that have no finished record, but it shows no reason. That is 223's design, and this slice provides the typed errors it needs. 223 should state where these errors become a visible record.

### [NOTE] `releases` has no marker for when a version is added to an already-reported commit

- **What happens.** The architecture says a version tagged later on an already-reported commit makes the report visible to `from_release` consumers. D3's `releases` row keeps its original `seq` and `reported_at` when `version` is set. A consumer whose cursor is already past that row would never see the version.
- **Why it is only a NOTE.** The later column fits the ALTER-only rule, since a nullable `versioned_at` is allowed. 227 can add it without a rebuild. Its design should handle this case, and the store contract doc could name it.

### [NOTE] Minor internal inconsistencies in D6 and the component list

- **D6.** `CFProject` is said to hold `id`, `name` and `project_path`, but the parser "reads the `id` field and ignores everything else." Settle which fields the parser populates and which D11 fixtures assert them.
- **`ContextForgeError`.** The CLI catches it and `resolve_member` raises it, but no module in Component Structure owns it. Place it so the import direction `cli → operations → upstream` stays intact.

### Run Digest

- Response length: 7275 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 334563 / 215561 / 118994 / 11731 / not computed
- Duration: 92.4 s
- Cost: $0.62 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Resolution

- F001 (pass): No change needed.
- F002 (pass): No change needed.
- F003 (pass): No change needed.
- F004 (pass): No change needed.
- F005 (note): Rejected. Loading the whole config is what the plan asks for: a missing value fails with an error that names it. There is one PM, and a new key is one named edit. Loading only part of the config per operation would add mechanism. The review leaves the choice for 224 and 227 to their own designs.
- F006 (note): The fix belongs to 223. I added a line to Integration Points → Provides to Other Slices (223) saying the D9 errors can happen before a claim, and that 223 decides where they become a record `status` can show.
- F007 (note): Added a nullable `versioned_at` to the `releases` table in D3. A later tag sets it along with `version`, so `from_release` consumers can find a version added after their starting point.
- F008 (note): D6 now says the parser fills in `id`, `name` and `project_path`, and that the D11 fixtures check all three. `ContextForgeError` is now defined in `operations/members.py`, named in Component Structure, and noted in D6 as keeping the import direction.
