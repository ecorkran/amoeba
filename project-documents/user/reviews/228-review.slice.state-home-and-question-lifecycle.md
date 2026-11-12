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
reviewedSha: dc1600f8ddb8c8c0b131151f1a4316e3bcb4774d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
turns: 7
promptTokens: 255474
cachedTokens: 192384
completionTokens: 49387
reasoningTokens: 46393
durationSeconds: 246.2
costUsd: 0.0332
costBasis: alias_pricing
runId: run-20261112-p4-1fa91a7d
squadronVersion: 0.24.27
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Home split, layering and the pull/read-only posture stay inside the architecture"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md"
  - id: F002
    severity: concern
    category: error-handling
    summary: "A sweep write failure aborts `status`, hiding the PM's waiting list"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md#D4 — The automatic close sweep"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Legacy-move limit hits and leftovers are unspecified"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md#D2 — Moving the legacy state on first use"
  - id: F004
    severity: concern
    category: state-integrity
    summary: "Any state-home store silently wins, and the real record is retired and later pruned"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md#D2 — Moving the legacy state on first use"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Per-row `sq` polls buy a detail string that one listing already carries"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md#D4 — The automatic close sweep"
  - id: F006
    severity: note
    category: architecture-alignment
    summary: "`status` writing and the new operations are not reflected back into the parent documents"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md#D13 — CLI, config and contract docs"
  - id: F007
    severity: note
    category: hidden-dependencies
    summary: "Member soft-removal is enforced by filtering at every call site"
    location: "project-documents/user/slices/228-slice.state-home-and-question-lifecycle.md#D8 — `set_up` removal"
---

# Review: slice — slice 228

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Home split, layering and the pull/read-only posture stay inside the architecture

Description: `config.yaml` stays in `~/.config/amoeba/` and only the store, `answering/` and `logs/` move under `${XDG_STATE_HOME:-~/.local/state}/amoeba` (D1), which matches both `220-arch.program-tool.md` ("One store at a fixed per-user location, with no flags. Tests point it elsewhere through one environment variable, read in one config place") and the design rule "config is config; state is state". `AMOEBA_HOME` remains the single redirect. `store/relocate.py` takes both paths as arguments and imports nothing from `config`; only `config/home.py` reads `AMOEBA_HOME`, `XDG_STATE_HOME` or `Path.home`, and the 222 D10 AST test is extended rather than replaced. No watcher, timer or background retry is introduced ("Nothing to run", "Called, never calling around"), and `dismiss`/`retract` are no-subprocess compare-and-set writes that keep the "one operation, two doors" model (request models validate raw input inside the operation, so 226 passes input through unchanged).

### [CONCERN] A sweep write failure aborts `status`, hiding the PM's waiting list

Description: D4 makes `status` a writer for the first time (224 D-exclusions kept it read-only, apart from `mark_read`), and it names handling only for the `sq` side: "A `PollFailure` leaves the row open, and its waiting entry shows `run_state: unknown` with the error." Nothing is said about the write failing. Under 222 D9 / 224 D8, any `StoreError` is exit 3, so a `StoreBusyError` on the sweep's short `BEGIN IMMEDIATE` transaction (entirely plausible: the hook, `answer` and `status` are concurrent short-lived writers by design) turns the whole call into `error: StoreBusyError` with no stdout — the PM loses the waiting list and the `closed_now` report because a background closure lost a lock. That contradicts 224 D4's own rule, "the rest of `status` is shown, because one broken checkout must not hide the PM's waiting questions." The requirement the gap leaves unmet is the plan criterion "a question whose run completed... lists both in `closed_now` once" — it silently does not hold when the sweep's write contends. State the strategy (catch the store error around the sweep, leave rows open, report it in `problems`/`file_problems`, still print the list), or state explicitly that a lost lock on the sweep is fatal to `status` and why.

### [CONCERN] Legacy-move limit hits and leftovers are unspecified

Description: Three hit-behaviors on this new I/O path are absent, and the design rule requires every limit to say what happens when it is hit:
- **Lock contention past the busy timeout.** Step 1 says "using the normal busy timeout" and that "whoever loses the lock waits, then finds the move done". If an old-code process holds a write transaction longer than `BUSY_TIMEOUT_SECONDS` (5.0, 222 D2), the loser gets `SQLITE_BUSY`; the document never says what that becomes. It matters because the main caller is the Squadron hook: exit 3 there means no question row, a missed hook and a calls-log line, on every pause until the other process goes away. Name the outcome and whether a retry/skip is intended.
- **A copy error.** Step 3 maps a verification mismatch to `StoreRelocateError`, but `Connection.backup` failing (ENOSPC, I/O error) is unmapped, and it is the one path that can leave a half-written copy.
- **Leftover `amoeba.sqlite3.moving`.** Step 5 explicitly handles a leftover `.<name>.moving` **directory** ("A leftover `.<name>.moving` from a crashed move is removed and that entry moved again"), but the store's `.moving` file is only deleted on a verification mismatch. A crash *inside* step 2 leaves it, and the crash tests cover "a crash after each step" — not a crash inside step 2. State that a stale `.moving` is removed/replaced on the next call, and add that crash boundary to the D2 tests.

### [CONCERN] Any state-home store silently wins, and the real record is retired and later pruned

Description: The "Both stores exist" rule assumes the state-home store is the verified copy: "If they differ, the state-home store wins, because it is the only one current code writes", after which the legacy store is renamed to `amoeba.sqlite3.legacy-<stamp>`, "never opened again", and D9 prunes it after `prune_after_days`. That assumption is only true if the move is the *only* thing that can create the state-home store — and that rests entirely on every entry point running `prepare_state_home` before config load (`Store.open` creates a missing store, 222 D2). The design enforces this for the CLI by convention and states the requirement for 226's MCP server ("called once when the MCP process starts"), but nothing structural does it: 226's design loads config and opens the store per call inside `wiring`, so one entry point that skips the call creates an empty store, the next call finds two differing stores, retires the real one as `legacy-<stamp>`, and the real questions and answers are deleted `prune_after_days` later. The plan criterion "an existing store there is moved on first use, with every record intact" fails silently in that case. Two cheap fixes, either sufficient: make the move part of the single place that builds `StateLayout` / opens the store so no entry point can skip it (plus a test that every CLI subcommand and the MCP start performs the move), and/or make the both-exist branch refuse (exit 3, no writes) when the state-home store is not a verified copy of the legacy one — e.g. it holds fewer rows or a lower `MAX(answers.seq)` — instead of winning by default.

### [CONCERN] Per-row `sq` polls buy a detail string that one listing already carries

Description: `sweep_scope` polls up to `SWEEP_POLL_LIMIT` (3) runs per `status` call, and the design then has to add the poll budget to `status`'s time bound for 226, introduce `WaitingRunState.UNKNOWN`, and leave rows open showing `run_state: unknown` with "not checked this call (poll limit)" — a state D12 gives no `next` or exit for (the backlog only shrinks if `status` is called more often than questions accumulate). Per the design's own account the poll is used for one thing: "A row whose run is missing from it ... gets one `poll_run` to learn `completed`, `failed` or `not_found`." 224 D1 already recorded the facts that make this unnecessary — the default listing "lists running, paused and failed runs and omits only completed ones, and every paused run that `--all` lists is also in the default", and it deliberately contemplated "`run_list.py` passes `--all` and drops completed runs itself". With completed runs present in the listing: present-and-completed → `run_moved_on` with detail `completed`; absent entirely → `run_gone`; paused at another `paused_at` → the listing already answers it; new runs are never needed. That removes all three polls, `SWEEP_POLL_LIMIT`, the `unknown` run state and its dangling rows, and the status-latency arithmetic, while still satisfying the plan's "close ... with the run's outcome, a waiting question whose run has moved on or been deleted". I could not run `sq` to confirm `--all`'s exact contents myself, so the implementer should verify against the installed Squadron; if it holds, take the cut (keeping completed runs for the sweep and filtering them out of the per-member run list).

### [NOTE] `status` writing and the new operations are not reflected back into the parent documents

Description: D13 updates `docs/cli-contract.md`, `docs/config-contract.md`, `docs/store-contract.md` and `README.md`, all inside the repo, but the slice changes three things the parent documents state: two new operations (`dismiss`, `retract`) absent from `220-arch.program-tool.md`'s operation table, a `closed` state absent from its question-record lifecycle ("It moves from claimed to answered or waiting on the PM"), and `status` becoming a writer/deleter where the architecture and 224 define it as the read side (`status` now closes rows and prunes files, and it runs on the 226 path the plan requires to be bounded). Sibling slice 227 shows the convention by naming its "Pending Planning Edits". Either name a planning edit to `220-arch.program-tool.md` (operation table, question record, the `status`-writes note) or say in D13 why the parent stays as written. Also unmentioned: 226's tool table and its stdio test's literal six-tool count (227 explicitly notes "the one edit to a 226 test") gain two rows from this slice.

### [NOTE] Member soft-removal is enforced by filtering at every call site

Description: "A removed member is treated as not a member everywhere" is delivered by remembering to filter in five places (`resolve_member`, `members_of`, `status`, `member_of_other_program`, pair reads), and 227 is asked to keep filtering in its reads as well. A new read path that forgets `members.removed_at` leaks a removed member, and the failure is silent (a member that should not exist shows up in `status` or a pair list). One read guard — `members_of` plus a single "active member" predicate that every member lookup goes through — would carry the rule once. The project convention "never scatter comparison values across code" points the same way.

### Run Digest

- Response length: 10868 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 189908
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 255474 / 192384 / not computed / 49387 / 46393
- Duration: 246.2 s
- Cost: $0.03 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution

- **[PASS] Home split, layering and pull/read-only posture:** no change needed.
- **[CONCERN] A sweep write failure aborts `status`:** D4 now catches `StoreBusyError` on the sweep's write and leaves the rows open for a later call. `status` still prints everything, with the error in a new `sweep_problem` field; `handle_pause` records it in its calls-log line. Other `StoreError`s stay exit 3. D12 says which `run_state` values unclosed rows keep.
- **[CONCERN] Legacy-move limit hits and leftovers:** D2 now says a busy timeout on the legacy lock is `StoreBusyError` (exit 3, nothing written, retried by the next call). A copy error deletes `.moving` and raises `StoreRelocateError` (old store untouched, retried next call). A leftover `amoeba.sqlite3.moving` is deleted by the lock holder before copying. The tests add a crash inside step 2 and a copy error.
- **[CONCERN] Any state-home store silently wins:** took the structural fix. `state_move.open_state_store(layout)` is the only function that opens the store, and it moves before calling `Store.open`. An AST test checks no other module calls `Store.open`, and a CLI test runs every subcommand against a legacy home. Data Flow, D13 and the 226 interface now use it.
- **[CONCERN] Per-row `sq` polls:** checked on `sq` 0.24.27 (20261112). The default listing held 8 of the 100 completed runs, and `--all` held all 100 plus every running, paused and failed run. `status` now lists with `--all` and judges every row from that one listing, with absent meaning `run_gone`; completed runs are dropped from the per-member run lists. Removed the polls, `SWEEP_POLL_LIMIT`, `run_state: unknown` and the time-bound arithmetic.
- **[NOTE] Parent documents not updated:** added "Pending Planning Edits" under D13: the operation table, question record, homes and `status`-writes note in `220-arch.program-tool.md`, and the eight-tool table, stdio smoke count and `open_state_store` in `226-slice.mcp-server.md`.
- **[NOTE] Soft-removal filtered at every call site:** D8 now defines the active-member predicate once in `store/programs.py`. Every member and pair read there uses it, no other module queries `members` (checked by a test), and 227 uses those reads.
