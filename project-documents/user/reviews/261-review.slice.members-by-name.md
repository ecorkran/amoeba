---
docType: review
layer: project
reviewType: slice
slice: members-by-name
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/261-slice.members-by-name.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 2ffd4663a6385a68050425e30fd314f5122fa22b
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 1335376
cachedTokens: 1094585
cacheWriteTokens: 240775
completionTokens: 127763
durationSeconds: 576.1
costUsd: 0.602173
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: integration
    summary: "Members on a hub store can never be named"
    location: "project-documents/user/slices/261-slice.members-by-name.md:198"
  - id: F002
    severity: concern
    category: operability
    summary: "Walkthrough's `name_taken` guidance is a dead end when the member's checkout has no origin"
    location: "project-documents/user/slices/261-slice.members-by-name.md:621"
  - id: F003
    severity: concern
    category: operability
    summary: "Walkthrough misstates three behaviours and says \"Dead ends found: none\""
    location: "project-documents/user/slices/261-slice.members-by-name.md:630-635"
  - id: F004
    severity: concern
    category: data-integrity
    summary: "Naming drops a member's wake command, leaving only a log line"
    location: "project-documents/user/slices/261-slice.members-by-name.md:209"
  - id: F005
    severity: concern
    category: operability
    summary: "Live migration script: backup location and failure handling are unspecified"
    location: "project-documents/user/slices/261-slice.members-by-name.md:430"
  - id: F006
    severity: concern
    category: boundaries
    summary: "Import rules leave git and Squadron reads unguarded on the hub side"
    location: "project-documents/user/slices/261-slice.members-by-name.md:111-115"
  - id: F007
    severity: concern
    category: data-model
    summary: "Removed members: naming rule conflicts with the name rule, and `rm <name>` is undefined for them"
    location: "project-documents/user/slices/261-slice.members-by-name.md:211"
  - id: F008
    severity: concern
    category: state-lifecycle
    summary: "Two existing members for one repo: the only exit deletes the spare's inbox"
    location: "project-documents/user/slices/261-slice.members-by-name.md:221"
  - id: F009
    severity: concern
    category: architecture
    summary: "`report_release`'s advice contradicts the unknown-outcome rule the design cites"
    location: "project-documents/user/slices/261-slice.members-by-name.md:383-389"
  - id: F010
    severity: concern
    category: architecture
    summary: "The `runs` document carries client times with no rule governing them"
    location: "project-documents/user/slices/261-slice.members-by-name.md:348-356"
  - id: F011
    severity: concern
    category: proportionality
    summary: "The `runs` document carries more than this slice has a consumer for"
    location: "project-documents/user/slices/261-slice.members-by-name.md:353-356"
  - id: F012
    severity: concern
    category: integration
    summary: "The body-key basis is misquoted, and 260 D6 says \"one key\""
    location: "project-documents/user/slices/261-slice.members-by-name.md:234"
  - id: F013
    severity: concern
    category: consistency
    summary: "The wake-due check on `send` and the claim use different predicates"
    location: "project-documents/user/slices/261-slice.members-by-name.md:318-322"
  - id: F014
    severity: note
    category: under-specification
    summary: "`ContextForgeError` is defined in a module the design deletes"
    location: "project-documents/user/slices/261-slice.members-by-name.md:331"
  - id: F015
    severity: note
    category: nfr
    summary: "Latency restatement miscounts"
    location: "project-documents/user/slices/261-slice.members-by-name.md:419"
  - id: F016
    severity: note
    category: error-handling
    summary: "Naming's null `origin` on a git failure is a fallback the departures table does not list"
    location: "project-documents/user/slices/261-slice.members-by-name.md:207"
  - id: F017
    severity: note
    category: scope
    summary: "Bulk `--file` can no longer create another repo's member"
    location: "project-documents/user/slices/261-slice.members-by-name.md:299"
  - id: F018
    severity: note
    category: scope
    summary: "Architecture's anticipated-slice list disagrees with the plan on wake commands"
    location: "project-documents/user/architecture/260-arch.the-hub.md:299"
  - id: F019
    severity: note
    category: dependencies
    summary: "This design depends on 260 decisions that are still open"
    location: "project-documents/user/slices/261-slice.members-by-name.md:73"
  - id: F020
    severity: note
    category: documentation
    summary: "Frontmatter date is in the future"
    location: "project-documents/user/slices/261-slice.members-by-name.md:13"
  - id: F021
    severity: pass
    category: scope
    summary: "Scope matches the slice plan's entry for 261"
    location: "project-documents/user/slices/261-slice.members-by-name.md#Technical Scope"
---

# Review: slice — slice 261

**Verdict:** FAIL

> Verdict note: the frontmatter verdict is CONCERNS. The reviewer stated FAIL; its fail findings were fixed; all twenty findings were checked 20261120; seventeen changed the design, three needed no change, see Resolution.
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Members on a hub store can never be named

`open_hub_store` does not run naming, because "a hub store gets members only through `add`." 260 says the opposite: until 261 the hub names an unnamed member by its id (260 D11). Migration 012 makes every existing member's `name` null (line 175 only blocks inserts). The hub has no `cf` (architecture, Envisioned State; line 115), so it cannot name them. A hub store that holds members at schema 11 (a pre-upgrade backup started with `serve --from-backup`, which the architecture supports) therefore fails every read of those members. Line 517 makes that failure the intended behaviour. The architecture requires that "no call ever sees a member without a name." The only repair, `amoeba add --project <id> --name`, must read the member, so the state has no exit. That breaks the "every state has an exit" rule. Line 492 ("none once any command has run") is also false for a hub.

Fix: name each existing row by its id in the migration (the rule 260 D11 already uses), and keep a separate "named from Context Forge" marker that the local naming step reads. No row is then null, and the local store still renames from Context Forge.

### [CONCERN] Walkthrough's `name_taken` guidance is a dead end when the member's checkout has no origin

The walkthrough says to run `amoeba add` in the member's checkout and then retry here. If that checkout has no `origin` either, step 1 records nothing (lines 274–275), and the retry is refused again. The detail at line 281 has the same gap. The way out is an `origin` remote on that checkout, or `--name` for a separate member; neither is stated.

The moved-repo step (line 626) also omits a hazard. A checkout that still has the old remote can reset the member's `origin` to the old host when it runs `add` (lines 274–276). The walkthrough should say so.

### [CONCERN] Walkthrough misstates three behaviours and says "Dead ends found: none"

- Line 633 (Undo): `add` "registers it again with its history." That holds only when the repo has an `origin` (step 3, line 278). Without one, step 4 creates a new member with a new id and no history.
- Line 630: wake command "From anywhere else it is refused." The wake command is set on the caller's checkout (line 297). From another repo on the same machine it sets that repo's checkout. Only `--project` is refused.
- Line 635: a checkout whose project has no path (line 176) cannot be cleared by `rm --checkout`, which needs a path (line 308). The only exit is `rm <name>`, which removes the whole member. That is a dead end too.

### [CONCERN] Naming drops a member's wake command, leaving only a log line

For a member Context Forge no longer lists, the command is "dropped and logged." This happens on the PM's live store, and the risk section names "a lost wake command" as live-data risk (line 580). The migration only adds (line 180), so nothing requires nulling the column. Keep the command in `members.wake_command` and show it in `list members`. Null it only when a checkout takes it. A log line is not a recovery path.

### [CONCERN] Live migration script: backup location and failure handling are unspecified

- Line 145 says "Nothing new is written outside the store." The script writes a backup of the store and config (line 430). The backup's directory is not stated, and no cleanup is named. Anything written needs a named cleanup or a stated reason it is bounded.
- The mitigation (line 586) says `update` "restores by itself on a failed check." D16 does not say so. It also does not say what happens if the restore itself fails, or what a failed `update` leaves behind.

Specify the backup path and its cleanup, whether the script restores on its own, and the outcome of each failure.

### [CONCERN] Import rules leave git and Squadron reads unguarded on the hub side

The rules restrict only `project_of` and `projects` (`cf`) to the three client-part modules. Nothing restricts `upstream.git_read` or the Squadron runner. An `operations.served` or hub-part module could import either and pass the static test. The fixture's empty `PATH` (line 115) catches a call only where a fixture test reaches it. Unit tests of hub parts run on a throwaway store with no such guard (line 413). Extend the import rule to `git_read` and the Squadron runner, with the same three modules as the only importers.

### [CONCERN] Removed members: naming rule conflicts with the name rule, and `rm <name>` is undefined for them

D4 names a removed member "without the clash checks." D1 (line 162) forbids a name equal to any other member's id, active or removed. Both cannot hold. D6 (line 254) finds names only among active members, yet line 256 says removing one twice is `unchanged`. Today that holds by id. By name, the second `amoeba rm widget` finds nothing and returns `not_a_member`. Decide whether removed members get the id check and are searched by name, or whether the rules cover only active members and the design says so.

### [CONCERN] Two existing members for one repo: the only exit deletes the spare's inbox

The state has an exit: `rm` the spare. The design does not say that `rm` deletes the spare's messages and history. "Merging members is not built" is a stated non-build of the remedy for a state the naming rule creates. Such a state could exist in the live store if one repo was registered under two Context Forge projects. Under the no-deferral rule, either build the merge or state plainly that the spare's inbox is lost, and have `rm` report what it removes.

### [CONCERN] `report_release`'s advice contradicts the unknown-outcome rule the design cites

Line 383 says the advice is "the architecture's: read the state before sending again." The architecture (line 129) says an unknown result tells the caller to read the state before sending anything again. The table gives `report_release` "Run it again." The departures table (lines 436–450) does not record this. Either use the architecture's advice, or record a departure and say why a repeat is safe, given `unchanged`.

### [CONCERN] The `runs` document carries client times with no rule governing them

The architecture says a time read from a client's files "is kept as an identifier and never compared with a hub time" (architecture, Architectural Principles, line 64). The document sends each paused run's run-file facts and its newest calls-log line to the hub (lines 351–352), and `status` places and shows them. The design does not say which timestamps these are, or that the hub keeps them only as identifiers. State it, and list what each field is used for.

### [CONCERN] The `runs` document carries more than this slice has a consumer for

Completed runs go in as "id and status only" (line 353), last in the size order. The design names no consumer for them in this slice. The question close sweep that would read them stays off the door until 262 (line 366). The plan's entry for this slice asks only for "the client sends its machine's Squadron run listing." Cut completed runs from the document. If the 768 KiB budget stays, state how many runs a machine typically holds, since the design gives no figure.

### [CONCERN] The body-key basis is misquoted, and 260 D6 says "one key"

The design says "260 D6 allows added keys." 260 D6 says the body "is JSON with one key, `document`" (260, line 262). The permission appears only in 260's Integration Points (260, line 575). 260 is in FAIL review and its D6 may change. Cite the Integration Points, and have 260's D6 and its Integration Points agree before this design is revised. The design already plans to re-read 260's D6, D8 and D9 (line 73); add the body shape to that list.

### [CONCERN] The wake-due check on `send` and the claim use different predicates

Line 318 says the claim and `can_wake` read a checkout with "both a command and a path." Line 322 says the hub's wake-due check needs "a checkout with a command on any machine." A checkout with a command and no path is not wakeable (line 320). So a `send` to that member is refused as `not_served` for a wake that can never start. Use one predicate in both places.

### [NOTE] `ContextForgeError` is defined in a module the design deletes

The class lives in `operations/members.py`, which D10 deletes. D5 (line 238), D11 and the walkthrough still raise it. Name its new module.

### [NOTE] Latency restatement miscounts

"That holds for nine of the ten operations," then the exceptions named are `add`, `status` and `list`. That is three, which leaves seven. Correct the count.

### [NOTE] Naming's null `origin` on a git failure is a fallback the departures table does not list

A failed or timed-out `git` call during naming yields a null `origin` and a logged warning. The reasoning is sound: a hung mount should not block every command. The architecture says naming records "its origin" (architecture, line 227). Add a departures row for this case.

### [NOTE] Bulk `--file` can no longer create another repo's member

This is recorded in the departures table (line 447). It is a visible change against the architecture's "daily use does not change" goal, and the stated reason holds given that a checkout creates a member (architecture, line 165). No action is needed beyond keeping the departures row.

### [NOTE] Architecture's anticipated-slice list disagrees with the plan on wake commands

The architecture's anticipated list puts "wake commands on checkouts" in 262. The slice plan's 261 entry puts them in 261 (plan, line 64), which matches this design. The architecture's list is provisional. Record the move in the departures table so the 262 author does not expect it there.

### [NOTE] This design depends on 260 decisions that are still open

The design relies on 260's D6, D8, D9, D11, D12 and D18 as of commit `729b57fb`, and 260's latest review is FAIL. The design already plans to re-read those decisions before its task breakdown, which is the right gate. The items it cites from 260 that I checked are present: migration 011, owner triggers on twelve tables, `rm-machine` removing session rows (so the session part of `rm-machine` is correctly outside this slice), and the load bounds.

### [NOTE] Frontmatter date is in the future

`dateUpdated: 20261121` is after today's date, 20261120.

### [PASS] Scope matches the slice plan's entry for 261

The plan's 261 entry is covered in full: names and naming, `add` with the four outcomes, `rm <name>`, both lookups, the registration cut-down, the ten served operations (with `send` refused when a wake is due), and `rm-machine` removing checkouts. The Excluded list matches what the plan assigns to 262–264. Migration 012 follows 260's migration 011 and its owner-trigger pattern.

### Run Digest

- Response length: 13574 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 1335376 / 1094585 / 240775 / 127763 / not computed
- Duration: 576.1 s
- Cost: $0.60 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 21
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 21
- Finding-shaped matches — surviving validation: 21

## Resolution

Resolved 20261120 in `user/slices/261-slice.members-by-name.md`. Nothing was deferred and no issue was filed.

- [fail] Members on a hub store can never be named: changed. The state is real but narrow: a hub store gets members only through `add` and 264's adoption, both of which name them, so only a 260 fixture store seeded with members (or a backup of one) can hold an unnamed member. `open_hub_store` now names any such member by its id in one write (`name_by_id`, D4), so the member is readable and is renamed, attached or removed like any member named by its id. No marker column was added: the local store still uses a null name as its sign. The state table, the departures table, the integration line, a criterion, the tests and the walkthrough are updated.
- [concern] Walkthrough's `name_taken` guidance is a dead end when the member's checkout has no origin: changed. D7 step 5 and the walkthrough say to give the member's checkout the remote first, and that `add` there records nothing without it. D7 step 1 and the moved-repo step say a checkout left with the old remote puts the old `origin` back, and to change the remote in every checkout. A criterion covers the first.
- [concern] Walkthrough misstates three behaviours and says "Dead ends found: none": changed. Undo now says `rm` then `add` brings the member back only for a repo with an `origin`, with a departures row and the limit stated under "Dead ends". The wake-command step says the command applies to the checkout it is run in and only `--project` is refused. The checkout with no path is gone: naming creates no checkout for a project with no path, because `project_of` never resolves a directory to such a project, and `checkouts.path` is never null (D2, D4).
- [concern] Naming drops a member's wake command, leaving only a log line: changed in part. The command is still dropped for a member that gets no checkout, since it has nowhere to run, but the log line now holds the member's id and the command's text and the walkthrough says how to set it again. Keeping it in `members.wake_command` would leave a second place a command lives. Read 20261120: all four live members are listed by `cf` with a path, so none is dropped on the PM's store.
- [concern] Live migration script: backup location and failure handling are unspecified: changed. D16 states what `scripts/update_live.py` already does: the backup in `<state home>/backups/<stamp>/` with one set kept, the automatic restore on a failed read-back, what a failed install or a `cf` failure leaves and the two ways on, and the restore command. It runs when the release runs, not after the merge (260 D19). No second backup is designed. The state section, a criterion, the script test and the walkthrough match.
- [concern] Import rules leave git and Squadron reads unguarded on the hub side: no change. The proposed rule is false for this code: `program_sources` and the pause path import `git_read` and the Squadron modules and stay client-run until 262. The fixture hub's `PATH` has no `cf`, `sq` or `git`, and the criteria run all ten operations through it.
- [concern] Removed members: naming rule conflicts with the name rule, and `rm <name>` is undefined for them: changed. D1 applies the id check to active members' names only. A removed member is found by id only (D6), so `rm <id>` twice is `unchanged` and `rm <name>` twice is `not_a_member`, with a departures row and a criterion. Registering a removed member again also refuses a name that is now another member's id.
- [concern] Two existing members for one repo: the only exit deletes the spare's inbox: changed. D4 and the walkthrough say what `rm` does to the spare: open requests cancelled as `member_removed`, the row and past records kept, the inbox not read again. Merging stays out of the design. Read 20261120: the live store's four members have four different `origin`s, so the state does not exist there.
- [concern] `report_release`'s advice contradicts the unknown-outcome rule the design cites: changed. D12 says `report_release` is the exception and why a repeat is safe (checked in `operations/report_release.py`: the same report again is `unchanged`, a repeated withdrawal is rejected, a repeated correction is applied again), with a departures row.
- [concern] The `runs` document carries client times with no rule governing them: changed. D11 has a "Client times" paragraph: the paused time and the calls-log time are shown and matched by equality as identifiers, never compared with the hub's clock.
- [concern] The `runs` document carries more than this slice has a consumer for: changed, text only. Completed runs stay, because they have a consumer in this slice: the question close sweep, which runs with no client file and reads the same document. D11 now names it.
- [concern] The body-key basis is misquoted, and 260 D6 says "one key": changed. D5 cites 260's Integration Points, and the prerequisite's re-read list includes that rule. Whether 260's D6 should say so itself is 260's to settle.
- [concern] The wake-due check on `send` and the claim use different predicates: changed. Every checkout has a path now, so both test "a checkout with a command" (D9).
- [note] `ContextForgeError` is defined in a module the design deletes: changed. D10 moves it to `operations.here`.
- [note] Latency restatement miscounts: changed. Seven of the ten.
- [note] Naming's null `origin` on a git failure is a fallback the departures table does not list: changed. Row added.
- [note] Bulk `--file` can no longer create another repo's member: no change. The finding asks for none; the departures row stays.
- [note] Architecture's anticipated-slice list disagrees with the plan on wake commands: changed. Departures row added.
- [note] This design depends on 260 decisions that are still open: no change. The prerequisite already gates the task breakdown on re-reading 260.
- [note] Frontmatter date is in the future: changed. `dateUpdated` is 20261120.
- [pass] Scope matches the slice plan's entry for 261: no change.

## Full-text review, 20261121

The whole design (664 lines) was read start to finish, with the architecture, the slice plan, the 260 design, the cited parts of 262 to 264, and the code each claim names; this review was made without reading the findings above. It found 17 things: 3 important, 13 minor and 1 that could not be confirmed at the time. All 17 are resolved in the design, and none ended as "no change". The unconfirmed one was settled by running `cf` in a throwaway Context Forge home and turned out to be real. The 260 design was read again at commit `9ee28aa5`, and the design's citations of it were brought in line.

- **1 (important). The pause path gave the member id to `cf -p`, and a member made by this slice has an id `cf` does not know,** so no pause in a newly added repo could gather its sources. The three calls now take the checkout's Context Forge id (D6, with D10, the Component Structure table, a departures row and a criterion).
- **2 (important). "Reducing a reduced form changes nothing" was false:** a reduced `origin` is neither accepted form, so the hub would empty it or change it. The hub now checks the form with `is_reduced_origin` and refuses anything else as `malformed_call` (D3, D12, the departures row, the API contract and a criterion).
- **3 (important). After a `cf` failure in the update's `amoeba list`, both ways on left a restore point that reinstalls code the store refuses.** The script now restores by itself on that failure, as it does on a failed read-back (D16, the walkthrough, a departures row and the criterion).
- **4. Which calls need `here` was stated two ways.** D5 now has one table: `list` with a subject, `rm --checkout`, `rm --pair`, `rm --concept --program`, `rm <name>` and `add --project` send none.
- **5. A refusal made by a hub part had no path through 260's handler.** `CallRefused` in `operations/errors.py` and one branch in `handle_call` (D12). D9 now says the door check looks at every machine and the claim at the acting one, and that the message names each machine.
- **6. The pin on `members.wake_command` collided with `test_members_queried_in_one_place.py`.** The statements are constants in `store/sql.py` that only `operations.naming` uses (D2).
- **7. Three problem codes in one place, four in another, and `not_a_checkout` in neither.** One list of five (D7), cited from D16, which now also lists `--attach-to` and `--new-member`.
- **8. `status` reads the runs at five points, not four.** The fifth, the close sweep's run-file check, stays in the sweep, so a run cut from the document for size never closes a live question (D11 and a criterion).
- **9. Exit 128 does not mean "not a repo".** That is now decided by a `.git` check before git runs (D5 and the facts list).
- **10. Which checkout, when a member has several on one machine, was said only for wakes.** The one added first, for the concept read (D6) and `MemberRow.path` (D13). `rm --checkout` compares the path as text and removes every row that holds it (D8).
- **11. `working_directory` for a call that gathers nothing was unstated.** It is null (D13), in D16's contract changes and the departures table.
- **12. The prerequisites named an old 260 commit and a re-read that was due.** The paragraph now cites `9ee28aa5` and what was read (Prerequisites).
- **13. A name could equal another member's id in a different case.** The check ignores case (D1 and a criterion).
- **14. The naming fixture could not come from the seed helpers.** It is built as `test_migration_010.py` builds its store (D15).
- **15. `--attach-to` did not say what happens when the member has a different `origin`.** Step 1's three rules apply (D7).
- **16. Modules that must change were missing from the Component Structure table.** Added: `set_up_remove`, `wake`, `pause_context`, `errors`, `hub.calls`, `wiring_results`, `mcp.message_tools`.
- **17 (was unconfirmed, now confirmed). In a registered worktree `cf get` gives the same project id and the worktree's own directory,** so updating the path on `add` would move a checkout between worktrees. The path is now set when the row is made; a moved repo is `rm --checkout`, then `add` (D7 step 1, State Management, the departures table, the walkthrough and a criterion).

Two changes came from re-reading 260 and not from a finding. `name_by_id` reads before it writes, so the hub's per-call store open stays the plain read 260 D8 now pins (D4). `ContextForgeError` moves to `operations/errors.py`, beside 260's `OPERATION_ERRORS`, and not to `operations.here` (D10).
