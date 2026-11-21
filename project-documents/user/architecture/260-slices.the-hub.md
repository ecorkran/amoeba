---
docType: slice-plan
layer: project
project: amoeba
parent: user/architecture/260-arch.the-hub.md
archIndex: 260
component: the-hub
audience: [human, ai]
description: Slice plan for Amoeba initiative 260. The hub process, its door and machines; then members known by name across machines; then the work that needs local files, run through the hub; then sessions across machines; then moving the PM's live store to the hub and deleting the local-store way; then members in several programs.
dateCreated: 20261120
dateUpdated: 20261121
status: not_started
---

# Slice Plan: The Hub

## Parent Document

`260-arch.the-hub.md`

## Planning Context

Architecture-level. Initiatives 100 to 240 left a store, operations with two doors (CLI and MCP), an MCP server with push and presence, and waking, all on one machine. This plan puts the store behind one always-up process and makes every machine a client. Four things shape it:

- **The PM's install keeps working on its local store until adoption (264).** Which way a machine runs is decided on every call by one thing: whether it has a client file (architecture, "How the build gets there"). The PM's laptop has none until the release that ships slice 264. Every slice before that is proven with fixtures: one hub and two client homes with different machine names on one computer.
- **Each slice widens what the door serves.** With a client file, an operation the door does not serve yet fails and says so. 260 serves the operations that name no member, 261 the ones that do, 262 the ones that need local files, 263 the session's own calls.
- **Schema changes reach the local store at each release.** Each is an ordinary migration. The release's last step runs `scripts/update_live.py update`, which backs up the live store and config first; `scripts/update_live.py restore` is the restore path. Adoption in 264 migrates the laptop's store itself and then copies it.
- **The largest risk is third.** Pulling `handle_pause` and the resume apart needs machines and named members first, so it cannot go earlier.

Slice numbers are execution order. The first slice takes the plan's index (260).

## Foundation Work

1. [ ] **(260) Hub and Door** — The hub process, the door, and machines.
   - **The process.** `amoeba hub serve` in a container, with the image definition and an example `hub.yaml` shipped. `hub.yaml` holds `bind`, the port, the `address` clients are told (both added by the slice design), `backup_dir`, `backup_hours`, `backups_kept` and the log limits, each required with no default in code; a missing or bad key stops the start and names it. Store work runs in a worker thread on its own connection per request.
   - **Certificate.** Made at first start in the state directory, with an end date that is never a limit. `cryptography` becomes a direct dependency.
   - **Machines.** A migration adds machines (name, token hash, last-called time, client version), the owner, and the owner on every record. The local store gets one machine standing for the install. `amoeba hub invite` (a new machine, or a new token for an existing one), `amoeba hub machines`, `amoeba hub rm-machine` (ends the token and removes the machine's session rows; later slices add what else it must end).
   - **The client.** `amoeba join <line>` fetches the certificate, checks it against the fingerprint in the line and saves it; `--address` changes only the address; a machine with a local store is refused unless `--set-aside-local`. `amoeba leave` removes the client file and puts a set-aside store back (added by the slice design, so the joined state has an exit). The client file holds the address, machine name and token, with owner-only permissions. The client trusts only the saved certificate, checked while the connection is set up. The mode is decided on every call, and with a client file no local store is opened or created.
   - **The door.** HTTPS with JSON. The machine comes from the token. Every call carries a client-made id; a writing call's result is kept in the call's own transaction under the machine and the id, returned to a repeat, and deleted by the sweep after its fixed lifetime. The connect, read and retry times are constants shared by client and hub. Outcomes are done, refused and unknown. The door version is checked on every call.
   - **Served.** The operations that name no member: `decisions`, `mark_read`, `dismiss`, `retract`, `standing`, `withdraw`. Every other operation, called with a client file, fails and says the door does not serve it yet.
   - **Backups and log.** Timed backups (only when the newest is older than `backup_hours`), backups before a migration in their own rotation, each holding the store, certificate and key. `amoeba hub backup`, and `amoeba hub serve --from-backup`. The log rotates by size with a keep count, and refused calls are lines in it.

   **Value:** Architectural enablement. There is a hub that stays up, that a second machine can join, and that already gives both machines the same decisions list and standing answers.
   **Success Criteria:**
   - A fixture hub with two client homes: `standing` set from one is read by `decisions` and `standing` from the other.
   - A hub with the wrong certificate never receives a token. A call with no token, a bad token or a removed machine's token is refused and logged.
   - A writing call repeated with the same id returns the first result and applies once, including when the hub is killed between the commit and the reply. The same id from another machine does not return it.
   - A hub that is down gives an error naming its address after the retry time. With no client file, the same command runs on the local store as before, and every existing test still passes.
   - A client with a different door version refuses and prints both versions and the upgrade command.
   - A hub restarted in a loop takes no new timed backup. A hub started with `--from-backup` on another state directory accepts the same clients with no new invite.
   - `rm-machine` and a re-invite each end the old token at once.
   - The load test runs many clients calling while others write, and asserts a bound on call time.
   - The hub's log and its backups each stay inside their keep counts.
   - The release's live update (`scripts/update_live.py update`) backs up the live store and config before it migrates the store. The slice tests the migration against a fixture store at the previous schema, and the restore path is in the slice notes.

   **Dependencies:** 240 (complete).
   **Interfaces:** Provides the hub process, the door and its call rules, machines and tokens, the client file and the per-call mode switch, the owner, and backups. Every later slice serves more operations through this door.
   **Risk Level:** High. It is new network code, a new always-up process and the access control everything else trusts.
   **Relative Effort:** 5

## Feature Slices (in implementation order)

2. [ ] **(261) Members by Name** — A member is known by a name on every machine.
   - **Schema.** A migration adds the member's name (unique) and its `origin`, and checkouts: a machine, that machine's Context Forge project id, the path, and the wake command, which moves here from the member's settings.
   - **Naming the members that exist.** The first call after the upgrade asks `cf` once for every member and records its name, checkout path and `origin`. A member `cf` no longer knows keeps its id as its name. Of two members with the same Context Forge name, the first registered gets it and the other keeps its id. Every other call runs this first if it has not run. `list` shows a member still named by its id.
   - **`add`.** It sends the checkout's `origin`, reduced to host and path. It looks for the `origin` first, then the name, with the four outcomes in the architecture. `--name` sets or changes the name. A wake command is accepted only for a checkout on the calling machine.
   - **`rm <name>`** works from any machine and directory, and cancels the member's open requests as `member_removed`.
   - **Lookup.** The caller is the member for the token's machine and the directory's Context Forge project id. A recipient is found by name in the store, with no `cf` call.
   - **Registration is cut down** to adding a checkout, setting a member's or a checkout's settings, and removing. The code that resolved other members through `cf` is deleted.
   - **Served.** `add`, `rm`, `inbox`, `reply`, `cancel`, `changes`, `report_release`, `send` for a recipient with no wake to start, and `list` and `status`, for which the client sends its machine's Squadron run listing. `rm-machine` now also removes the machine's checkouts.

   **Value:** User value. An agent on one machine can send a request to a repo and an agent in that repo on another machine reads it at its next `inbox`.
   **Success Criteria:**
   - The 240 three-repo chain runs between two fixture machines through the hub, by polling.
   - `add` on a second machine attaches to the member with the same `origin` when the SSH form is used on one and the HTTPS form on the other, and when the member was renamed.
   - `add` of a different repo under a taken name is refused with both remotes shown. A second checkout of a repo with no `origin` is refused and says why.
   - A wake command for another machine's checkout is refused.
   - Existing members are named on the first call after the upgrade, including the unknown-project case and the name clash, and no call ever sees an unnamed member.
   - `rm <name>` removes a member that has no checkout left.
   - Agents in two worktrees and on two machines of one repo read the same inbox, and the first `accept` wins.
   - With no client file, every existing behavior still passes on the local store, with recipients found in the store.
   - The release's live update (`scripts/update_live.py update`) backs up the live store and config before it migrates the store. The slice tests the migration against a fixture store at the previous schema, and the restore path is in the slice notes.

   **Dependencies:** 260.
   **Interfaces:** Provides member names, checkouts, the `origin` rule and both lookups. 262 uses checkouts to decide which machine work belongs to. 263 uses the caller lookup for a session's member.
   **Risk Level:** Medium. It changes the key every table refers to and deletes a large part of registration.
   **Relative Effort:** 4

3. [ ] **(262) Local Work Through the Hub** — The commands that need local files run on their machine and make their store steps as hub calls.
   - **Two checks first,** from the architecture's note under Anticipated Slices: list every transaction in the pause path and the answering settle that runs a check or reads a local value inside it (`settle_answered` is the known case), and every store function that takes the current time from its caller or sweep that compares a client's time with a store time. The design states how each one moves before anything is split.
   - **`handle_pause`, the answering run's store reads and its settle, and the sweeps** become client-run with hub steps. The answer limit is applied on the hub. Settings come from the hub with the first call.
   - **`answer` and the resume.** The answer is recorded on the hub. The resume gets a real claim: taken only when the started mark is empty, or older than the resume's bound with no outcome. The bound allows for the network retry time. A refused resume is not handed out again.
   - **Waking.** `send` checks presence across machines and the wake goes to a checkout with a wake command. The wake wrapper's store steps are hub calls.
   - **Work that belongs to a machine.** Every hub reply carries a flag that this machine has work waiting. A client that sees it makes one claim call and starts the work detached: a resume, a `handle-pause` for a held question whose request ended, or a wake. On the same machine as the cause, the work starts in that call, as today. `answer`, `send` and `list` name the machine being waited on and when it last called.
   - **Unknown.** A command that runs by itself stops at the step that got no reply and logs it. Its claim runs out and the work is handed out again.
   - **The hub's clock.** No hub call takes the time from the client. A run's paused time is only an identifier.
   - **Clean-up of local files** runs on each machine on today's trigger and asks the hub which runs are open.
   - **`rm-machine`** now also closes the machine's open questions as `machine_removed`, marks answers waiting to be resumed there as not delivered, and ends a wake running there.
   - **Served.** `answer`, `handle_pause`, `send` with waking, and the internal wake command.

   **Value:** User value. A run paused on one machine can be answered from another and resumes on its own machine; a request can wake a repo on the machine that has it.
   **Success Criteria:**
   - A fixture pipeline paused on machine A and answered from machine B resumes on A at A's next call, and `answer` on B names A.
   - Three clients on one machine see the work flag at once: the resume starts once. The same for a held question and for a wake.
   - A claim whose reply was lost is handed out again after its limit, and not before. A resume that is slow to record its outcome because the hub was stopped and restarted is not started a second time.
   - A refused resume is not retried by later calls, and is retried by a new `answer`.
   - The hub is stopped in the middle of a `handle-pause`: the command stops and logs it, and the next call from that machine starts it again from what the store holds.
   - The 242 hold-and-release fixture and the 244 waking fixture pass between two fixture machines.
   - A request whose only wakeable checkout is on a machine that is not calling waits, `send` and `list` say which machine, and the request still expires.
   - Two answering runs settling at once cannot both pass the answer limit.
   - A client whose clock is an hour off changes no expiry, age or claim.
   - `rm-machine` leaves no question, answer or wake that still names the machine as pending.
   - Each machine's scratch and logs are still cleaned past `prune_after_days`.
   - With no client file, every existing pause, resume and wake test still passes on the local store.

   **Dependencies:** 260, 261.
   **Interfaces:** Provides the work flag and the claim call, the resume claim, and the hub steps of the pause path. 263's tick carries the work flag. 320 later replaces the answering run that uses these steps.
   **Risk Level:** High. It is the largest refactor, it resumes real runs, and it is where one piece of work could start twice.
   **Relative Effort:** 5

4. [ ] **(263) Sessions Across Machines** — `amoeba-mcp` becomes a client.
   - **One tick.** Every `notify_poll_seconds`, one hub call reads the member's highest delivery number and refreshes the session row when a heartbeat is due. Its reply carries the work flag. Ticks run one after another, off the event loop, and do not retry.
   - **The directory.** A migration adds the client version and door version to a session row, the door version to a machine, and each machine's last reported runs (260 already added the machine, because its `rm-machine` removes a machine's sessions). `list` and `status` show who is working where, on which machine, and which sessions and machines are behind the hub's door version. Stale rows are judged on the hub's clock.
   - **Tools.** Every MCP tool goes through the door. The check that an `answer` fits inside the MCP call deadline runs on the hub with the network times added. The wake command field is never sent from MCP.
   - **Runs on other machines** show in `list` and `status` as last reported, with the machine named.
   - Channel events, the pinned handshake and the `inbox` rule are unchanged from 241.

   **Value:** User value. A session on one machine is told about mail sent from another within a tick, and `list` shows every session on every machine.
   **Success Criteria:**
   - The 241 live test passes with the request sent from a second fixture machine.
   - A session on each of two fixture machines appears in `list` from either, with its machine. A killed one reads as gone after `session_stale_seconds` on the hub's clock.
   - With the hub stopped, ticks do not pile up, tools return the error naming the hub, and push resumes at the first tick after it returns.
   - A session whose `amoeba-mcp` has an older door version gets the upgrade message from its tools, and `list` shows it as behind.
   - A tick's reply with the work flag set starts that machine's waiting resume.
   - The load test from 260 is extended to many ticking sessions with CLI calls writing, and asserts no tick is starved.
   - With no client file, the 241 tests still pass on the local store.

   **Dependencies:** 260, 261, 262.
   **Interfaces:** Provides the session rows of joined machines, which 262's cross-machine presence check reads, and the session directory. Consumes the work flag.
   **Risk Level:** Medium. The research-preview channel feature is unchanged; what is new is that every tick is a network call.
   **Relative Effort:** 2

## Migration Work

5. [ ] **(264) Adoption** — The PM's live store moves to the hub and the local-store way is deleted.
   - **`amoeba adopt <join line>`,** with the six steps in the architecture: the checks, the adoption id, the copy under the local store's write lock, the load with row counts, the config, and the switch with the adopted mark. Running it again is safe. The slice design adds `amoeba discard-local`, which ends a handed-over store, migration 015 (the adoption row and the mark's reason) and `amoeba hub add-config-keys`.
   - **The hub's config.** `config.yaml` arrives from the laptop, or is written from the shipped example on a fresh hub. It is read on each call.
   - **Deleting.** The code path that runs operations on a local store, the mode switch, and the 228 state-move code. After this slice a command with no client file fails and says to run `amoeba join`.
   - **Tests.** The unit tests that ran operations on a local store run against an in-process hub on a throwaway store.
   - **The release.** The release skill and `scripts/update_live.py` update the hub first, then the client they run on, and list the others. Three shell scripts on the hub machine update it, restore or empty it, and print a join line.
   - **Documents.** `docs/cli-contract.md`, `docs/config-contract.md`, `docs/store-contract.md`, `docs/mcp-server.md` and `docs/squadron-hook.md` are brought in line, with a set-up page for the hub: start, invite, join, adopt, move, undo.
   - **The PM's install.** Not a task of the slice. The release that ships the slice sets the hub up on the LAN machine and adopts the laptop's store, through `update_live.py update`, which prints the dated backup's path. `live-update.yaml` names the three hub commands and `hub_address`, the address clients reach the hub at. The slice rehearses this on a copy of the live store.

   **Value:** User value. The PM's decisions, messages and sessions are one store on every machine he works on.
   **Success Criteria:**
   - A fixture laptop store with members, questions, requests, standing answers and wakes is adopted, and every row count matches on the hub.
   - Adoption never waits on a local session: it lists each one still open and whether it must be restarted. It is refused when the hub holds any record (sessions, reported runs and kept call results do not count).
   - A connection opened before the adoption fails its next write naming the hub, and a hook from this release fails with the join message and opens no store.
   - Adoption is cut off after the load and after the config: the same command run again finishes, with one copy of the data on the hub. If something was written locally between the attempts, the hub holds it.
   - Moving the hub: a backup started on another state directory serves the same clients after `join --address`, with nothing lost.
   - After the slice, no code opens a store outside the hub, its admin commands and the three hand-over commands (`adopt`, `join --set-aside-local`, `discard-local`), none of which creates one; a client with no client file fails with the join message.
   - A fresh hub with `config.yaml` written from the example serves a new machine's `add` and `send`.
   - A bad edit to the hub's `config.yaml` fails calls with the file and key named, and a fixed one takes effect on the next call.
   - A copy of the PM's live store is adopted in a rehearsal, and `list` shows what the installed release shows. The live store itself is adopted by the release.

   **Dependencies:** 260, 261, 262, 263.
   **Interfaces:** Provides the one mode. 300 builds on a hub that holds the PM's real data.
   **Risk Level:** High. It moves the PM's live store and deletes the way back into the old code, so the restore path is `update_live.py restore --local-store`, which puts the pre-migration backup back under the previous release.
   **Relative Effort:** 3

## Feature Slices After Adoption

6. [ ] **(265) Members in Several Programs** — A member can be in more than one program at once. Added by the PM 20261120: a repo that two programs both depend on (the agent kit is the first) has to be a member of both.
   - **Schema.** A migration adds a membership table keyed by member and program, fills it with one row per member from today's `program_id` column, and drops the column. Rules, authorize lists and checkouts stay on the member. Dependency pairs already name their program and do not change.
   - **`add --program ID`** on a member that is already registered adds that program to it. It no longer moves the member and no longer refuses with `member_of_other_program`. `add` with no `--program` on a registered member changes no membership.
   - **`rm NAME --program ID`** takes the member out of that one program and deletes its pairs there. `rm NAME` with no `--program` removes the member from every program, as removal does today. Leaving the last program is removing the member.
   - **A command that works on one program** (`--depends-on`, `--pair`, `--concept`) uses the member's program when it has one. For a member in several it needs `--program`, and without it is refused with the member's programs listed.
   - **Reads follow every membership.** `send` to a program reaches its other members, and the sender must be in it. `changes` and release notes cover the pairs in every program the member is in. A standing answer with reach `program` applies to a member in that program. An answering run reads the concept and sources of every program the member is in.
   - **Views.** `list` and `status` show a member under each of its programs, and `list members` shows all of them on the member's line. `--program` narrows as today.
   - **Documents.** `docs/store-contract.md`, `docs/cli-contract.md` and `docs/program-rules.md` are brought in line.

   **Value:** User value. One repo can serve two programs, and each program's members can message it and see its releases.
   **Success Criteria:**
   - A fixture member added to a second program appears in both in `list`, and a note sent to either program reaches it once.
   - A member in two programs sees a release report from a provider in each through `changes`.
   - A standing answer with reach `program` applies to a member in two programs when the question is in either, and one for a third program does not.
   - `rm NAME --program ID` leaves the member, its inbox and its other program untouched. Removing its last program removes the member and cancels its open requests as `member_removed`.
   - `--depends-on` with no `--program` on a member in two programs is refused and lists both.
   - After the migration every member has exactly the membership it had, with the row count checked, and the hub's before-migration backup path is in the slice notes.
   - No code reads a program from the member row.

   **Dependencies:** 260, 261, 264.
   **Interfaces:** Provides membership as its own record. 320's stand-in reads a member's programs from it.
   **Risk Level:** Low. It is wide (about 150 references in 26 files) but mechanical, and it runs after adoption so there is one code path and one store to migrate.
   **Relative Effort:** 3

## Implementation Order

`260 → 261 → 262 → 263 → 264 → 265`.

- **Dependencies.** Each slice needs the ones before it. 261 needs machines for checkouts. 262 needs checkouts to know which machine work belongs to. 263 carries 262's work flag. 264 needs every operation served through the door before it can delete the local-store way. 265 is last so the membership change is made once, on the hub, and not also on the local-store way that 264 deletes.
- **Risk.** 260 is first because everything trusts its access control. 262 is as early as its dependencies allow.

## Notes

- **Fixtures, not real use.** No slice waits on the PM using the hub. The two-machine fixture is one hub and two client homes on one computer.
- **Dated facts.** The Context Forge id format was read 20261120. 261 re-checks it, and 263 re-checks the Claude Code channel facts from 241.
- **300 is next.** Waking a repo with no machine awake needs runs on the hub from a clone, which is 300's runner.

## Future Work

Living backlog; entries may be added during slice design, task breakdown, or implementation.
