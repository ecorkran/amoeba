---
docType: architecture
layer: project
project: amoeba
archIndex: 260
component: the-hub
initiative: the-hub
parent: ../project-guides/001-initiative-plan.amoeba.md
dependencies: [240-arch.agent-messaging]
relatedSlices: []
riskLevel: high
audience: [human, ai]
description: Architecture for Amoeba as one always-up process on a LAN machine, with every machine the PM works on as a client. The hub is the only thing that opens the store. Clients reach it over an authenticated network door, resolve their own repo locally, and do the work that needs local files. Members get a name that holds across machines, sessions are listed across machines, every record names its owner, and the PM's live store moves to the hub. Revised 20261120 from the architecture review.
dateCreated: 20261120
dateUpdated: 20261120
status: in_progress
---

# Architecture: The Hub

## Overview

Amoeba's store is a file on the PM's laptop, opened by whichever short-lived command runs next. The PM works on several machines and the laptop sleeps. So his decisions, the messages between repos and the record of who is working where exist on one machine only, and nothing can act while that machine is closed.

The hub is Amoeba as one process that stays up on a LAN machine that does not sleep. It holds the store. Every machine the PM works on is a client of it.

**Scope.** The hub process and its container, the network door with access control, `amoeba` and `amoeba-mcp` as clients, members known by name across machines, sessions listed across machines, an owner on every record, and moving the PM's live store to the hub.

**Motivation.** The stand-in agent (320) needs timers and a turn-end answer, and both need a process that is always there. It also needs one set of decisions for every machine. Neither exists on a laptop that sleeps, so the hub comes first.

**Not in this initiative.** Running agents on the hub from a clone (300's runner), timers and the scheduler (300), the turn-end entry point (320), finding the hub automatically on the LAN, and more than one person using a hub.

## Design Goals

- **One store, everywhere.** A decision, message or standing answer recorded from any machine is the same record on every machine, at once.
- **Always there.** The hub starts at boot, restarts on failure, and backs its store up on its own.
- **A client is thin and loud.** A client holds no store and no copy of one. If it cannot reach the hub it fails with an error that names the hub's address. It never falls back to anything local.
- **Work happens where its files are.** Anything that reads a repo, a Squadron run file or starts a command runs on the machine that has them. The hub never reads a client's disk.
- **Daily use does not change.** The operations, their names and their results stay as they are. Set-up is one command per machine, once, and still one command per repo. Two things do move to the hub machine: editing the config, and upgrading first.

## Changes to earlier decisions

| Earlier | Now |
|---|---|
| No Amoeba process stays running (220, 240) | One does: the hub. |
| Many short-lived writers on one store file (220, 240) | Only the hub opens the store. |
| A member is a Context Forge project id (222) | A member has a name of its own. A Context Forge id belongs to one checkout on one machine. |
| Every member lookup calls the local `cf` (222, 240) | A client asks `cf` only about its own directory. Every other member is found in the store. |
| `wake_command` is a member setting, run in the member's one checkout (244) | A wake command belongs to a checkout, runs on the machine that has it, and can be set only from that machine. |
| Identity is self-asserted, fine on one machine (240) | The machine is proven by a token. Which repo on that machine, and which door, are still self-asserted. |
| `answer` resumes the run from wherever it is called (220) | The answer is recorded at once. The run's own machine does the resume. |
| The config file is per user, on the machine (222) | One config, on the hub. A client's own file says only how to reach the hub. |
| A one-time move of state out of `~/.config` (228) | Deleted. The move to the hub replaces it. |

## Architectural Principles

- **Only the hub opens the store.** Clients, hooks and `amoeba-mcp` never do. The one exception is the hub's own admin commands, run on the hub machine.
- **One hub call is one whole transaction.** No transaction spans two network calls. Today's code already never holds a transaction across an outside call, and its claims are compare-and-set, so each existing transaction block becomes one hub call. A check that runs inside a transaction today, such as the answer limit in the answering settle, runs on the hub: the call carries the values and the hub applies the rule. The slice that moves the pause path lists every such transaction before it starts.
- **One mode.** There is no hub-less mode and no local store to fall back to. A single-machine user runs the hub on that machine. Two modes would mean two sets of decisions the first time a setting was wrong. A local fallback may come back later, only if running the hub on a single machine proves painful (PM, 20261120). Nothing here is built for it.
- **Same operations, three doors.** The network door serves the operations the CLI and MCP doors already have, with the same documents in and out. The CLI and `amoeba-mcp` become clients of it.
- **A repeated call is safe.** Every call carries an id the client makes. The hub keeps each writing call's result for a short time and gives the same result to a repeat, so a lost reply never applies twice.
- **A path means nothing without its machine.** Every stored path (a checkout, a run's directory, a session's directory, a log) is stored with the machine it is on, and is only ever opened there.
- **The hub's clock is the clock.** Expiry, heartbeats, ages and ordering use the hub's time and the store's sequence numbers, never a client's clock.
- **Pending work is read, not queued.** What a machine should start next is worked out from records that already exist (an answered question, an ended request, an open request to a wakeable checkout). There is no new queue to drain or clean.
- **An owner on every record.** Today it is always the PM. Nothing filters by it yet.

## Current State

- The store is `~/.local/state/amoeba/amoeba.sqlite3` on the laptop. Every `amoeba` call, every `amoeba-mcp` and every wake wrapper opens it directly and relies on SQLite's busy timeout.
- The config is `~/.config/amoeba/config.yaml` on the same machine.
- A member's key is its Context Forge project id. Context Forge makes that id when a project is created on a machine (read 20261120: `project_<time>_<random>`), so the same repo on a second machine has a different id. Members cannot be shared across machines as stored.
- Every call that names a member runs the local `cf`, for the caller and for the recipient. Registration is about 3,000 lines, much of it resolving references this way.
- Operations mix three things in one function: reads of local files (`cf`, Squadron's run files, the repo's rules), store transactions, and starting local commands (a resume, a wake, a detached `handle-pause`).
- `amoeba-mcp` reads the store every few seconds for push and writes a session row for presence. Both stop at the machine's edge.
- About 680 lines move state out of `~/.config` on first use. That move is finished on the PM's install.

## Envisioned State

### The hub

One process, `amoeba hub serve`, in a container on the LAN machine. Amoeba ships the image definition. The container has one published port and two mounted directories:

- **config:** the config file, and nothing else.
- **state:** the store, its backups, the hub's certificate and key, and the hub's log.

The container runtime starts it at boot and restarts it on failure. The process keeps nothing in memory that matters.

The hub contains Amoeba and nothing else: no `cf`, no Squadron, no agent runtime and no checkouts. Those arrive with 300's runner.

**Backups.** The hub writes a consistent copy of the store when it starts and every `backup_hours` after that, and keeps the newest `backups_kept`. This is a plain timer inside the process, not 300's scheduler.

**The hub's log** is one file that rotates at `hub_log_max_bytes` and keeps `hub_logs_kept` files. Refused calls are lines in it, so a scanner hitting the port cannot fill the disk.

**Config.** The hub reads the config file on each call, as every command does today, so an edit takes effect at once with no restart. A bad edit fails every call that needs the config, on every machine, with the file and key in the error, exactly as a bad config does today. It never keeps running on an older copy.

**Admin commands** run on the hub machine, inside the container, and are CLI only:

| Command | Does |
|---|---|
| `amoeba hub serve` | Runs the hub |
| `amoeba hub invite <machine>` | Creates a machine and prints one join line for it |
| `amoeba hub machines` | Lists machines with when each last called and the client version it called with |
| `amoeba hub rm-machine <machine>` | Removes a machine (see "Machines") |
| `amoeba hub backup` | Takes a backup now |

### The door and access control

The door is HTTPS with JSON, on the LAN. Each operation is one call that takes the operation's existing document plus who is calling.

- **Encrypted, with a pinned certificate.** The hub makes its own certificate and key at first start, in the state directory. A client records the fingerprint when it joins and refuses any other. The fingerprint replaces hostname checking, and the certificate's end date is set far enough out that it is never a limit. The reason for encrypting is concrete: a token lets its holder set a wake command, so it must not cross the LAN in the clear.
- **One token per machine.** The hub stores only a hash. Every call carries the token; a call without a valid one is refused and logged. The token names the machine and, through it, the owner.
- **A token reaches only its own machine's commands.** A checkout's wake command can be set or changed only by the machine that checkout is on. So a leaked token cannot plant a command that runs on another machine, and removing the machine removes its checkouts and every wake command with them.
- **Otherwise all machines act as the PM.** There are no other per-machine rights.
- **The door a call came through is what the client says.** The rule that a wake command is set from the CLI only, never from MCP, is now kept by the client: `amoeba-mcp` never sends that field. The hub's own guard is the machine rule above.
- **A door version.** The hub states one number for the shape of the door. It changes only when an existing call changes in a way an older client cannot use; an added call or field does not change it. A client built for a different number refuses to proceed and prints both versions and the upgrade command. There is no negotiation.

### Repeats and failures

- **Retry.** A client that gets no reply repeats the same call, with the same call id, for `hub_retry_seconds`. If the hub applied the first one, the repeat returns that result.
- **Three outcomes.** A call ends as done, as refused (the hub answered no), or as unknown: no reply inside the retry time. An unknown result says so in those words and tells the caller to read the state (`inbox`, `list`) before sending anything again.
- **Kept results** are deleted after `call_result_minutes`, by the hub's existing sweep.

### Machines

A machine is a name the PM chose, a token, a last-called time and the client version it last called with.

- **Joining.** `amoeba hub invite laptop` on the hub prints one line holding the address, the certificate fingerprint, the token and the client's network settings. `amoeba join <line>` on the laptop writes the client file. That is the whole set-up for a machine. The address should be a name that stays put, not a number the router hands out.
- **The client file** lives in the config directory with owner-only permissions and holds: the hub's address, the fingerprint, the machine's name, its token, and three values a client needs before it can reach the hub (`hub_connect_seconds`, `hub_read_seconds`, `hub_retry_seconds`). The invite fills those three from the hub's config, so they are still set in one place. A client with no client file fails and says to run `amoeba join`.
- **A new address.** `amoeba join --address <address>` changes only the address in the client file. The token and fingerprint stay, so moving the hub or restoring it on a new box needs no new invites.
- **Leaving.** `amoeba hub rm-machine` revokes the token and removes the machine's checkouts and session rows. Open questions from runs on that machine close as `machine_removed`. Its wake rows age out with the rest. The machine's next call is refused.
- **A machine that goes quiet** stays listed with its last-called time. It accumulates nothing: what waits on it has its own end (below).

### Members by name

- **A member has a name,** unique in the store. It is what agents write in `send` and what `list` shows. It starts as the repo's Context Forge project name and can be set at `add`.
- **A checkout** ties a machine and that machine's Context Forge project id to a member, with the checkout's path and, optionally, its wake command.
- **`amoeba add` on the first machine** creates the member and its checkout. **On a second machine** it finds the member by name and adds a checkout. The hub records the repo's remote address with the member, and refuses a checkout whose remote differs, so two repos that share a name are never merged by accident.
- **Several agents in one repo are one member.** Agents on different machines, branches or worktrees of the same repo share the member and its inbox. Each sees the same mail, and the first `accept` of a request wins, as in 240. They cannot message each other, because an address is a member or a program, never a session. What a team would still need is per-person rights and lists, which is the owner seam and out of scope here.
- **Who is calling.** The client asks its local `cf` which project the directory is in, as today, so worktrees and subdirectories still resolve to one project. It sends the machine and that project id. The hub maps them to the member. A project with no checkout on record is `not_a_member`, as today.
- **Who is addressed.** The name is looked up in the store. No `cf` call is made for a recipient, on any machine.
- **Removing by name.** `amoeba rm <name>` works from any machine and any directory, so a member whose last checkout is gone can still be removed. Removal cancels its open requests as `member_removed`, as in 240. Until then, a member with no checkout is shown that way in `list`, and requests to it wait for their expiry.
- **Registration is cut down to this:** add a checkout (creating the member if new), set a member's or a checkout's settings, and remove. Everything that resolved other members through `cf` goes.

### Three kinds of operation

| Kind | Operations | How it runs |
|---|---|---|
| Whole on the hub | `inbox`, `reply`, `cancel`, `send`, `answer`, `dismiss`, `retract`, `decisions`, `mark_read`, `changes`, `standing`, `withdraw` | The client adds who is calling and passes the document through. Names in results come from the store. |
| Client gathers, hub writes | `add`, `rm`, `list`, `status`, `report_release` | The client reads what only it can (its `cf` project, the repo's remote, its machine's Squadron runs) and sends that with the document. |
| Client runs, hub steps | `handle_pause`, the resume, the wake wrapper, presence and the push check, and the clean-up of local files | The command runs on the machine with the files. Each store step it makes today becomes one hub call. |

The settings a client-run command needs (models, caps, timeouts) come from the hub with the first call, so the hub's config is the only one.

**Clean-up of local files.** Each machine keeps cleaning its own scratch and logs on today's trigger (at most once an hour, from any call). It asks the hub which runs are still open and deletes the rest past `prune_after_days`. The log of `handle-pause` calls stays on the machine whose hook made them. The hub cleans the store's rows and its own files.

### Work that belongs to a machine

Some work can only be done on one machine: resuming a run whose files are there, starting `handle-pause` for a held question when its request ends, and starting a wake in a checkout there.

- **A machine asks.** Each `amoeba` call that could have caused such work, and each `amoeba-mcp` tick, asks the hub what this machine should start, and starts it detached. This replaces today's "start after" step, which did the same on one machine.
- **Each kind is claimed before it is started.** Several sessions on one machine ask at once, so the hub hands each piece of work to one asker only: a wake by its wake row, a resume by its started mark, a held question by the pause claim. All three are compare-and-set today.
- **A claim that never starts is taken again.** If the reply carrying a claim is lost, nothing runs. Every claim has a time limit on the hub's clock, after which the next ask from that machine gets the work. The wake and the resume have such a limit today; the slice confirms the pause claim's or adds it.
- **Same machine, no wait.** When the PM answers from the machine the run is on, the resume starts in that same call, as today.
- **Another machine.** The answer is recorded at once and `answer` says which machine the run is on. That machine resumes it the next time anything there talks to the hub. `list` shows it as answered and waiting for that machine, with the machine's last-called time.
- **Waking.** `send` checks presence across all machines. If nobody is live in the recipient, the wake goes to a checkout that has a wake command. The first machine with such a checkout to ask claims it, with today's limits and wrapper. If no such machine is calling, the request waits for the next agent or its expiry, exactly as a member without a wake command does today, and `list` says which machine the wake is waiting for.
- **Every wait ends.** Pending work is never its own record. It ends when the machine does it, when the record behind it ends (the question is dismissed or closed, the request expires or is cancelled), or when the machine is removed.

### Sessions across machines

`amoeba-mcp` stays a local process started by the session, because it must know the session's directory and push into that session. It becomes a client.

- **One tick.** Every `notify_poll_seconds` it makes one hub call that reads its member's highest delivery number, refreshes its session row when a heartbeat is due, and asks for this machine's pending work. The call runs off the event loop, as its store reads do today. Channel events, the pinned handshake and the `inbox` rule are unchanged from 240.
- **The directory.** A session row gains its machine and its client version. `list` and `status` show who is working where, across machines. A stale row is judged against the hub's clock.
- **Runs on other machines.** `list` and `status` check the fate of Squadron runs only on the machine that calls them, since only it can read those run files. Questions from another machine's runs show as last reported, with that machine named.

### Owner

The hub creates one owner, the PM, when it first starts. Machines belong to an owner. Programs, members, questions, answers, standing answers, messages, sessions and wakes each record their owner, taken from the calling machine. Reads do not filter by owner, because there is one. This is the seam for a later version with more than one person, and nothing more is built on it here.

### How the build gets there

The hub's side of every operation is today's operation code. During this initiative that code is reached two ways, and which one a machine uses is decided by one thing: whether it has a client file.

- **No client file:** the command runs the client part and the hub part in one process on the local store, as today. The PM's install stays this way until adoption.
- **A client file:** everything goes to the hub. An operation the door does not serve yet fails and says so. Only test fixtures run this way before the last slice.

Three rules keep this simple:

- **One schema.** Every schema change in this initiative (member names, checkouts, machines, owner) is an ordinary migration that both ways run on. The local store gets one machine, standing for the install. Member names are filled from `cf` at the first call after the upgrade; a member `cf` no longer knows keeps its id as its name.
- **One lookup.** Once members have names, both ways find a recipient in the store.
- **It ends.** The last slice moves the PM's store to the hub and deletes the no-client-file way. After it there is one mode.

### Moving the PM's live store

The live store and config are designated for this move. By this point the laptop's store is already at the new schema, so the move is a copy. `amoeba adopt`, run once on the laptop after it has joined:

1. Refuses unless the hub's store is empty.
2. Sends the store file. The hub loads it, renames the install's one machine to the laptop's joined name, moves the laptop's token onto it, and checks the row counts against the file it was sent.
3. Sends the config file. The hub validates it and writes it as the hub's config.
4. Renames the laptop's store to a dated backup beside it and prints that path.

After this, no client reads a local store or a local `config.yaml`, and the 228 state-move code is deleted.

**Restore path.** Start a hub on the laptop itself with the backup file as its store and the old config, and join it. Nothing in the backup was changed.

## Operator walkthrough

Done as the PM running it.

1. **Start.** On the LAN machine: start the container. `amoeba hub invite laptop` prints a join line. On the laptop: `amoeba join <line>`, then `amoeba adopt`. On each other machine: an invite, a join, and `amoeba add` in each repo there.
2. **Normal path.** A session on the desktop sends a request to `context-forge`. A session open in context-forge on the laptop gets the push within a tick and handles it. `list` on either machine shows the same requests, questions and sessions.
3. **A run pauses on the laptop; the PM answers from the desktop.** The answer is recorded and `answer` says the run is on the laptop. The laptop resumes it at its next call. If the laptop is asleep, it resumes when the PM next opens a session there.
4. **The hub is down.** A call retries for `hub_retry_seconds`, then fails with the hub's address in the error. `amoeba-mcp` stays up, its tools return that error, and it recovers at its next tick. The container restarts the hub. A pause hook that fires meanwhile fails the same way. That run then shows on the laptop's `list` as a paused run Amoeba has no record of, as a missed hook does today, with the command to handle it.
5. **A reply is lost.** The client repeats the call and gets the first result. If the hub stays unreachable, the result is unknown and says to check `inbox` or `list` first.
6. **Changing a setting.** Edit the config file in the hub's config directory. The next call uses it. A bad edit fails every call with the file and key named, until it is fixed.
7. **Upgrading.** The release updates the hub first, then each client. Most releases leave the door version alone and nothing else happens. When it does change:
   - a one-shot `amoeba` call on a machine not yet upgraded refuses and prints the upgrade command;
   - an open session's `amoeba-mcp` is still the old program, so its tools return the same message until that session is restarted. `list` and `hub machines` show which sessions and machines are behind;
   - a pause hook on a machine not yet upgraded fails, and its run shows as a paused run with no record, as in step 4.
8. **A token leaks or a machine is retired.** `amoeba hub rm-machine`. Its checkouts and their wake commands go with it. The other machines are untouched. To bring the machine back: a new invite.
9. **The laptop never comes back.** `rm-machine` closes its open questions as `machine_removed` and drops its checkouts and sessions. Members that had a checkout elsewhere carry on. A member with no checkout left stays, with its mail, until `amoeba rm <name>` from any machine or a new `add`.
10. **Two repos with one name.** The second `add` is refused with both remotes shown. The PM adds it under another name.
11. **The hub's disk is lost.** Restore the newest backup, or the laptop's dated backup from adoption, and start the hub on it. If its address changed, `amoeba join --address` on each machine. Tokens are in the store, so no new invites.
12. **Undo the whole thing.** The restore path above.

Dead ends found: none. One soft spot: work for a machine waits until something on that machine calls the hub. That is the same condition under which the work could run at all, and each such wait ends with its record.

## Technical Considerations

- **The pause path is the large change.** `handle_pause`, the resume and their sweeps make about twenty store transactions between reads of local run files. Each becomes a hub call. The answering pipeline is deleted by 320, so it is changed only where it touches the store: its reads, its final write, and the answer-limit check, which moves to the hub.
- **Operations must be pulled apart.** Today one function reads local files, writes the store and starts commands. Each needs a clear line between what the client gathers, what the hub does and what the client then starts. The existing injected edges mark most of that line already.
- **The server.** A small web app on the server library that `mcp` already installs, so the door adds no new server dependency. Making the certificate needs `cryptography` as a direct dependency. Each request does its store work in a worker thread on its own connection, so no store call runs on the event loop and SQLite orders the writers as it does today. The CLI calls the hub with a plain blocking call.
- **Load test.** Required by the Python rules for network code. It runs many sessions ticking while CLI calls write, and asserts a bound on call time and that no tick is starved.
- **Latency.** A CLI call is a `cf` call plus one round trip. The push tick is one small call per live session. How fast a turn-end answer must be is 320's question.
- **What a token is worth.** It allows what the PM's own commands allow on that one machine, a wake command included, and everything in the store. That is why the door is encrypted, tokens are per machine, and a wake command can be set only from its own machine. Message text is still data written by other repos' agents, and is treated exactly as in 240.
- **Logs stay where the work ran.** A wake's or a resume's log is on the machine that ran it. The hub stores the machine and the path, and `list` shows both.
- **Testing.** The hub runs in-process against a throwaway store in unit tests. A live fixture runs one hub and two client homes with different machine names on one computer, which exercises every cross-machine path without a second computer.
- **Facts about other tools are dated.** The Context Forge id format was read 20261120. Each slice re-checks what it depends on.

## Anticipated Slices

Provisional. Each slice leaves the PM's install working on its local store; the last one moves it.

- **Hub and door:** `amoeba hub serve`, the certificate, machines and tokens, invite and join, call ids and repeats, the door version, the owner, backups and the log, the container, and the whole-on-hub operations served through it.
- **Members by name:** member names, checkouts, caller and recipient lookup, `rm` by name, and registration cut down.
- **Local work through the hub:** `handle_pause`, the resume, the wake wrapper and wake commands on checkouts, work that belongs to a machine, and clean-up of local files.
- **Sessions across machines:** `amoeba-mcp` as a client, the single tick, presence with machines, and the directory in `list` and `status`.
- **Adoption:** `amoeba adopt`, the restore path, the hub's config, deleting the local-store way and the 228 state move, and the contract documents.

## Related Work

- `000-concept.amoeba.md`, "How it runs", and `001-initiative-plan.amoeba.md`, initiative 260: the scope this starts from.
- `240-arch.agent-messaging`: messages, push, presence, hold and release, and waking, which this carries across machines.
- `220-arch.program-tool`: the operations, the two doors, the pause entry and the resume.
- `notes/008-code-sort.amoeba.md`: the line counts used above.
- `notes/006-long-running-agents.amoeba.md`: the long-running agent this is the first step of.
- `user/reviews/260-review.arch.the-hub.md`: the review of this document.
- Retired slice 109 (network API): an earlier door on the resident supervisor. Nothing of it is reused.
- `docs/cli-contract.md`, `docs/config-contract.md`, `docs/store-contract.md`, `docs/mcp-server.md`, `docs/squadron-hook.md`: the contracts this changes.
