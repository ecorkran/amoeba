---
docType: slice-plan
layer: project
project: amoeba
parent: user/architecture/220-arch.program-tool.md
archIndex: 220
component: program-tool
audience: [human, ai]
description: Slice plan for Amoeba initiative 220 — the code audit, the cut, the new store with config and set-up, pause handling through the CLI, status and decisions, switching on scenario A for real work, the MCP server, and program dependencies (scenario B).
dateCreated: 20261107
dateUpdated: 20261113
status: in_progress
---

# Slice Plan: Program Tool

## Parent Document

`220-arch.program-tool.md`

## Planning Context

Architecture-level. Initiatives 100, 120 and 140 built a resident supervisor that nobody has run. This plan first cuts that down to what scenarios A to C need, then builds the eight operations on a new store. Three things shape it:

- **Audit before cutting.** The architecture's table of what stays and what goes is a starting guess. The audit settles it piece by piece, so the cut deletes from a list, not from memory.
- **Scenario A comes first.** Pause handling and switching it on for real work come before anything else new. The counted trial and its go/rethink verdict were dropped (needs PM-driven work); the PM judges from `decisions` and `status` in normal use, and scenario B does not wait on a verdict.
- **CLI before MCP.** The operations are proven through the CLI, where a run can be driven and inspected by hand. MCP is a thin layer added once they work.

Slice numbers are execution order. The first slice takes the plan's index (220).

## Foundation Work

1. [x] **(220) Code Audit** — A document, `user/analysis/220-analysis.code-audit.md`, that sorts every module in `src` and its tests into keep, keep and rework, move to Squadron (filed as a Squadron issue), or delete, each judged against scenarios A to C. It names what the kept answering code depends on that is being deleted (nodes, journal entries, blocked states, the tick loop) and what replaces each. It decides whether slice 182's branch is merged, partly reused or redone, and confirms that 180's slice-writing pipeline goes. No code changes.
   **Value:** Architectural enablement. The cut works from a list, and the size of the rework is known before the store is designed.
   **Success Criteria:**
   - Every package under `src` and every test directory has a verdict and a one-line reason tied to a scenario or to nothing.
   - Each kept module lists what it imports that is being deleted, and what replaces it.
   - Slice 182 has a verdict: merge, reuse parts, or redo, with the parts named.
   - Anything marked move to Squadron has an issue filed, or the audit says why it is deleted instead.
   **Dependencies:** None.
   **Interfaces:** Produces the delete list for 221 and the reuse list for 222 and 223.
   **Risk Level:** Low
   **Relative Effort:** 2

## Migration / Refactoring Slices

2. [x] **(221) The Cut** — Delete what the audit rejects: the resident host and its lock and recovery, the tick loop, launch and dispatch, the HTTP server, the inbox, the change feed, the old CLI and inspection views, the old store and its migrations, and their tests. What stays is a library: the answering pipeline file, passage assembly, decision logic, the answer screen and the upstream readers, each with its tests passing on its own. The README drops the old pitch and says what Amoeba is now. Old slice documents keep their files.
   **Note (220 audit):** `upstream/` is mostly delete (only the Context Forge plan parsers are kept, reworked). The `sq` launch, poll and resume code that stays lives in `process/` and `runner/`, and some helpers must move before their packages go. The audit's Verdicts and Dependencies sections are the delete list.
   **Value:** Architectural value. The code shrinks to what the scenarios use, and everything after is written against a small base.
   **Success Criteria:**
   - Every item the audit marks delete is gone, along with its tests.
   - Format, lint, typecheck and the remaining tests pass.
   - The kept answering pieces run in their tests with no store, no tick and no resident process.
   - The live answering tests still pass, or the audit records why one waits on 223.
   - No kept module imports a deleted one.
   **Dependencies:** 220.
   **Interfaces:** Leaves the kept answering pieces and upstream readers as the library 222 and 223 build on.
   **Risk Level:** Medium. The answering pieces are tied to what goes, and pulling them apart is the real work.
   **Relative Effort:** 4

## Feature Slices (in implementation order)

3. [x] **(222) Store, Config and Set-up** — The new store and the first operation. One SQLite store at a fixed per-user location, which tests redirect through one environment variable read in one config place. A new baseline schema: the question record keyed on run id and `paused_at`; programs, members, member-to-member dependency pairs carrying `consumed`; reported releases; per-member settings; and the PM's single `decisions` marker. One user-level config file for models, cost cap, per-run answer limit and the default list of what answers may not authorize, with no defaults in code. `set_up` registers programs, members (rule file paths and any change to the authorize list) and dependency pairs. From inside a repo the member is the Context Forge project for the working directory, and worktrees of one repo are one member. Short-lived writers rely on SQLite's busy timeout, with no single-writer lock.
   **Value:** Architectural enablement, and the first thing the PM can run: a program set up and read back.
   **Success Criteria:**
   - A test run never touches the real store; a test checks the environment variable is honored and that nothing else picks the location.
   - A missing config value fails with an error that names it.
   - `set_up` through the CLI registers a program, members and pairs; a repeat call changes nothing; a malformed call is rejected with a reason.
   - Two worktrees of one repo resolve to the same member; a directory in no program is reported as such.
   - Several processes writing at once all succeed or fail with a named error.
   **Dependencies:** 221.
   **Interfaces:** Provides the store, config reader, member resolution and `set_up` to every later slice. Schema and config go in the project's contract docs.
   **Risk Level:** Low
   **Relative Effort:** 3

4. [x] **(223) Pause Handling** — Scenario A through the CLI. `handle_pause` takes a run id: it handles only an agent question from an in-process run in a program member and leaves every other run alone; claims the question; gathers context (slice from the run's parameters, rules, the program concept and the member's PM answers from Context Forge and the store); starts the answering run from a scratch directory with the hook's opt-out and records its run id on the claim; records an answer that passes the check and the screen, then resumes; otherwise records the question as waiting on the PM with the reason. `answer` records the PM's answer, makes it the precedent for repeats, and resumes if the run is still at that pause. Both share one resume: compare the checkpoint, start `sq run --resume` detached from the recorded checkout with a log file, wait briefly for `running`, and record resumed, refused or not delivered. The answer step and check step enforce the member's authorize list, with the screen as backstop. The per-run limit counts only automatic answers. A dead claim is resolved by checking the recorded answering run first. Wiring the Squadron hook to `handle_pause` is a config line in a member, documented here.
   **Note (220 audit):** slice 182's branch is reused in parts, not merged; its take and rewrite groups feed the context step. See the Slice 182 section of `user/analysis/220-analysis.code-audit.md`.
   **Value:** User value. A run that stops on a question at night gets answered and carries on, or leaves a clear reason for the PM.
   **Success Criteria:**
   - On a real paused run, `handle_pause` answers and resumes it, and the record shows the question, passages, answer and resume outcome.
   - A run outside a program, a prompt-only run, a non-question checkpoint and an already-claimed question are each left alone with a reason.
   - An answer that authorizes something on the member's list waits on the PM; allowing that item for the member lets the same kind of answer through.
   - A run resumed by someone else before Amoeba gets to it is recorded as not delivered and is not resumed again.
   - A refused resume, or one whose process died, is resumed by a second `handle_pause` with the recorded answer and no new answering run.
   - `answer` on a waiting question resumes the run and is used for the same question next time; it never counts toward the answer limit.
   - Each live answering test that 221 deleted as `waits on 223` has its claim restored, from the commit the audit's Live tests section names.
   **Dependencies:** 222. External: `ecorkran/squadron#302` for the hook to start `handle_pause` (calling it by hand works without it).
   **Interfaces:** Provides `handle_pause` and `answer`, the question record's states and the resume outcomes. Consumes 140's answering pipeline and passages as kept by 221.
   **Risk Level:** High. It resumes real runs on a model's answer, and it is the test of the whole design.
   **Relative Effort:** 5

5. [x] **(224) Status and Decisions** — The read side. `status` shows, per member, running and paused runs, why each paused run stopped, questions waiting on the PM with their reasons, answers not yet resumed, and paused question runs with no finished record (a missed hook), which an agent can pass to `handle_pause`. `decisions` lists what was answered, by whom and from what, since the PM's marker or a given time. `mark_read` moves the PM's marker to the last record the caller saw. Run state is read from Squadron, and neither run state nor slice state is ever copied into the store. `status` shows no slice state. `status` and `decisions` accept an explicit program from anywhere; without one, `status` covers the caller's program inside a member and every program outside, and `decisions` covers every program. `answer` takes an explicit question.
   **Value:** User value. The PM, through any agent, sees what is waiting on them and what was decided without them.
   **Success Criteria:**
   - `status` on a program with a running run, a paused question run, a waiting question and a missed hook shows each correctly.
   - A missed hook found by `status` and passed to `handle_pause` is answered and resumed.
   - `decisions` since the marker shows only newer records; `mark_read` moves the marker and never past what the caller saw.
   - Nothing in the store duplicates run status or slice state; a test checks the schema.
   **Dependencies:** 223. External: `ecorkran/squadron#303` (working directory in the run file and JSON from `sq runs list`).
   **Interfaces:** Provides `status`, `decisions` and `mark_read`.
   **Risk Level:** Low
   **Relative Effort:** 3

## Integration Work

6. [x] **(225) Scenario A Trial** — Amoeba switched on for real work in the PM's own repos. Done: the answering run's pause-hook opt-out flag and the exact hook config line are documented (`docs/squadron-hook.md`); the tool is installed and the `trading` program registered; the hook is configured at user level; a sanity pass with 223's live fixture pipeline in each member (and in Amoeba's own repo, which is left alone) came out clean. The counted trial (a ledger of real questions and a go/rethink verdict) was dropped because it needs the PM to generate work on demand. Evidence comes from normal use of `decisions` and `status`.
   **Value:** Verification. Amoeba is live on the PM's repos, so real use shows whether it saves the PM more than it costs.
   **Success Criteria:**
   - Real work runs in at least two members, with every question accounted for in `decisions`.
   - The note gives answered without the PM, waiting on the PM by reason, and wrong answers.
   - The note states go or rethink, and the initiative plan reflects it.
   - Any shape met in real runs that the tests lacked becomes a fixture.
   **Dependencies:** 223, 224. External: `ecorkran/squadron#302`.
   **Interfaces:** None new.
   **Risk Level:** Low
   **Relative Effort:** 2

7. [x] **(228) State Home and Question Lifecycle** — Fixes the design holes found running 225. State moves out of `~/.config`: `config.yaml` stays in `~/.config/amoeba/`; the store, `answering/` and `logs/` live under `${XDG_STATE_HOME:-~/.local/state}/amoeba/`, with `AMOEBA_HOME` still redirecting everything for tests, and an existing store moved over by code on first use. Every question gets an exit: `dismiss` (CLI) closes a `claimed` or `waiting_on_pm` question with a reason, never counts as precedent and drops out of `status`; `status` and `handle_pause` close, with the run's outcome, a waiting question whose run has moved on or been deleted; `retract` stops a PM answer being precedent. The answer limit counts automatic answers since the run's last PM answer, so a PM answer resets it, and a run at the limit is answerable and dismissible. `set_up` gains `remove` entries for members, pairs and concept, refusing a member with open questions. Answering scratch directories and logs of settled questions are pruned after a configured age. `handle_pause` skips as `wrong_checkout` when called outside the run's recorded directory (amoeba#37), and every call that writes no question row is appended to a calls log (amoeba#34). Closes amoeba#34, #36, #37.
   **Value:** User value. A stuck or stale question can always be cleared by the PM or an agent with a command, nothing is ever fixed by editing the store, and state is where state belongs.
   **Success Criteria:**
   - After a fresh install, `config.yaml` is the only file under `~/.config/amoeba/`; an existing store there is moved on first use, with every record intact.
   - A question in every state has a command or an automatic rule that ends it; no state needs a person editing files.
   - A PM answer resets the run's automatic-answer count; a dismissed or retracted answer is never shown to the answerer as precedent.
   - A call outside the run's recorded directory skips as `wrong_checkout` and writes no question row; every call that writes no row appears in the calls log.
   - `set_up` removes a member, pair or concept, and refuses a member with open questions.
   - Settled scratch directories and logs older than the configured age are pruned.
   **Dependencies:** 223, 224.
   **Interfaces:** Provides `dismiss`, `retract` and `set_up` removal; changes the home layout 226 and 227 read.
   **Risk Level:** Medium. Moves the live store; the move is tested only against throwaway homes and keeps the old file until the new one verifies.
   **Relative Effort:** 4

8. [x] **(226) MCP Server** — An MCP server over the operations built so far, with the same names and no logic of its own. Long work (`handle_pause`, `answer` with a resume) starts a detached CLI process and returns at once. Store calls run off the async loop. This completes scenario C: any agent session can see status and decisions and answer for the PM.
   **Value:** User value. The PM can ask any agent what is waiting and answer through it, from any directory.
   **Success Criteria:**
   - Every operation available on the CLI is available over MCP with the same inputs and results.
   - A long call over MCP returns at once and its work shows in `status`.
   - No operation logic lives in the MCP layer; a test checks both doors call the same functions.
   **Dependencies:** 224 and 228.
   **Required fixes to the existing design:** use the names the code has (`start_child`, `terminate_group`), not `spawn_detached`; `answer` over MCP takes a question key from `status` and records the caller as `via: mcp`; long waits run detached and every MCP call has a deadline so none outlives a client timeout. Redesigned after 228: both doors place operation arguments in one `wiring.invoke`; each answer records its door (`answers.via`, migration 004); detached logs are pruned by 228's `prune`; the walkthrough is a live fixture test, not a PM step.
   **Interfaces:** Provides the MCP server and its install instructions, and `answers.via`.
   **Risk Level:** Low
   **Relative Effort:** 3

## Human CLI

9. [x] **(229) Human CLI** — Makes the command usable by a person. Text output by default and `-j`/`--json` on every command. CLI names are kebab-case (`handle-pause`, `mark-read`) and MCP names stay snake_case, both derived once in `names.py`. `set_up` is replaced by two operations, `add` and `rm` (also `remove`), each a CLI command and an MCP tool: `add` registers the working directory's repo (or `--project NAME`) with `--program`, `--rules` (repeatable), `--allow`/`--deny`, `--depends-on PROVIDER[:from_source|from_release]` and `--concept MEMBER:PATH`, with `--file` for bulk; with no `--program` the repo joins its current program or starts a one-member program named after its Context Forge project. A new `list` is the one view: no argument shows what needs the PM; `--all` adds running work and settled questions; `list programs`, `list members` and `list dependencies` show what is registered, with repo names and paths. A member that names no rules reads the config's `default_rules_paths` (`CLAUDE.md`, `AGENTS.md`), each skipped when absent; `--rules` replaces them. Exact-duplicate rule passages are dropped before numbering and counting, and `@path` imports inside the rules files are followed. The docs explain rules from the user's side. The step that reinstalls the tool and changes the `pipeline.on_pause_command` hook to `amoeba handle-pause` runs back to back.
   **Value:** User value. The PM can register a repo with one command, see what needs a decision at a glance, and read every result without a JSON viewer. A repo's rules work with no setup.
   **Success Criteria:**
   - Every command prints text by default and the same result as JSON with `-j`; `list --json` returns the full status report.
   - `amoeba add` in a repo with a Context Forge project registers it with no other flag; with none, it is a clear error.
   - A member with no named rules reads whichever of `CLAUDE.md` and `AGENTS.md` exist at the committed target, each section once; neither existing is `sources_missing` and names what was tried.
   - A rules entry the member named that matches nothing still fails; an entry from the config default never does.
   - Every setting of a member can be set from the CLI; only `config.yaml` is edited by hand.
   - After the hook change, a real paused run in a fixture pipeline is handled through `amoeba handle-pause`; the old name is gone from the code, docs and hook.
   **Dependencies:** 226 and 228.
   **Interfaces:** Provides the renamed commands and tools, `add`, `rm`, `list`, and the default rules; 227 uses these names.
   **Risk Level:** Medium. Renames every command and the live hook; a migration adds one column to `members`.
   **Relative Effort:** 4

## Scenario B

10. [x] **(227) Program Dependencies** — Scenario B. `report_release` records what this member released (commit, version if any, what changed and what it touched), keyed on member and commit and holding the commit's current version, so a repeat changes nothing and a later tag on a reported commit adds the version. `changes` returns what this member's dependencies reported since a starting point the caller gives, filtered by each pair's `consumed`, with nothing marked read. Both are added to the CLI and MCP. The two rule lines (consumer: call `changes` before designing; provider: call `report_release`, and the same line in the release skill) are written as text a member pastes into its own rules file.
   **Value:** User value. A repo designing a slice sees what changed upstream without the PM relaying it.
   **Success Criteria:**
   - A `from_source` consumer sees a provider's merge report; a `from_release` consumer sees it only once it has a version.
   - Tagging a release on an already reported commit adds the version; a `from_source` consumer does not see it twice.
   - Two worktrees calling `changes` from different starting points each see everything since their own point.
   - The rule block's own git commands, run in fixture repos, give a starting point that still sees a provider's report, including after a rebase; a live test runs both operations against real Context Forge. No step waits on real use.
   - A wrong report is corrected in place or withdrawn, and a corrected one is visible again to consumers whose starting point predates the correction.
   **Dependencies:** 226, 228 and 229.
   **Required fixes to the existing design:** the commands use 229's names: the CLI says `report-release` and `changes` with text output and `-j`, the MCP tools stay `report_release` and `changes`; `report_release` has a correct/replace flag so a wrong `touched` list can be fixed; a provider missing from `cf list projects` is a warning, not exit 3, and `set_up remove` (228) clears stale pairs; `changes` takes its starting point from an explicit argument, with the git author time of the previous slice design as the hint (no stored marker, so parallel worktrees never hide changes from each other); the integration check is an automated fixture test, not a real design run in the PM's repos.
   **Interfaces:** Provides `report_release`, `changes` and the rule-line text.
   **Risk Level:** Medium. Nothing forces an agent to follow a rule line.
   **Relative Effort:** 3

## Implementation Order

`220 → 221 → 222 → 223 → 224 → 225 → 228 → 226 → 229 → 227`.

- **Dependencies.** Each slice builds on the one before through 224. 226 needs the operations it wraps. 228 comes before 226 and 227 because they read the home layout and the question states it changes. 229 renames what 226 built and changes `set_up`, so it comes after 226 and before 227, which then uses the new names. 227 needs 226, 228 and 229.
- **Risk.** 223 is the riskiest and the test of the design, so it comes right after the base it needs and before anything else new.
- **Parallel work.** 226 can run beside 225, since 225 is only setup and a sanity pass.

## Notes

- **External dependencies.** `#299`, `#302` and `#303` are closed and in the installed `sq`. `#304` stays on hold unless 227 shows agents skipping the rule lines.
- **Retired work.** Slices 183 to 186 are retired by the architecture and get no successors here. Slice 180's slice-writing pipeline goes in 221 unless the audit finds a use. Slice 182 is decided by the audit; its program-concept passages are wanted and land in 223's context step if it is redone.
- **Concept wording.** The concept still says a steered passage "can at worst produce a wrong reply" and that checks on an answer belong in the pipeline. Both are corrected as a planning edit, outside these slices.
- **No data migration.** Nobody has run Amoeba, so 222 starts from a new baseline and 221 deletes the old migrations.

## Future Work

Living backlog; entries may be added during slice design, task breakdown, or implementation.

1. [ ] **Pipeline step for program checks** — If agents skip the scenario B rule lines, add the check as a pipeline step once `ecorkran/squadron#304` lands. Dependencies: [227]. Effort: 2/5
