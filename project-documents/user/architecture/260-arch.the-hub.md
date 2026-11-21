---
docType: architecture
layer: project
project: amoeba
archIndex: 260
component: the-hub
initiative: the-hub
parent: ../project-guides/001-initiative-plan.amoeba.md
dependencies: [240-arch.agent-messaging]
relatedSlices: [260, 261, 262, 263, 264, 265]
riskLevel: high
audience: [human, ai]
description: Architecture for Amoeba as one always-up process on a LAN machine, with every machine the PM works on as a client. The hub is the only thing that opens the store. Clients reach it over an authenticated network door, resolve their own repo locally, and do the work that needs local files. Members get a name that holds across machines, sessions are listed across machines, every record names its owner, and the PM's live store moves to the hub. Revised 20261120 from three architecture reviews.
dateCreated: 20261120
dateUpdated: 20261121
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
| The resume's started mark can be written again while the outcome is open (228) | It becomes a real claim: one taker at a time. |
| The config file is per user, on the machine (222) | One config, on the hub. A client's own file says how to reach the hub. |
| A one-time move of state out of `~/.config` (228) | Deleted. The move to the hub replaces it. |

## Architectural Principles

- **Only the hub opens the store.** Clients, hooks and `amoeba-mcp` never do. The one exception is the hub's own admin commands, run on the hub machine. A client opens a store in one case only: handing its own local store over. `amoeba adopt`, `amoeba join --set-aside-local` and `amoeba discard-local` open that machine's local store, never the hub's, and never create one.
- **One hub call is one whole transaction.** No transaction spans two network calls. Adoption holds the laptop's local write lock across its three hub calls, for at most 239 seconds; that is a lock on the store being handed over, not a hub transaction. Today's code already never holds a transaction across an outside call, so each existing transaction block becomes one hub call. A check that runs inside a transaction today, such as the answer limit in the answering settle, runs on the hub: the call carries the values and the hub applies the rule.
- **One mode.** There is no hub-less mode and no local store to fall back to. A single-machine user runs the hub on that machine. Two modes would mean two sets of decisions the first time a setting was wrong. A local fallback may come back later, only if running the hub on a single machine proves painful (PM, 20261120). Nothing here is built for it.
- **Same operations, three doors.** The network door serves the operations the CLI and MCP doors already have, with the same documents in and out. The CLI and `amoeba-mcp` become clients of it.
- **A repeated call is safe.** Every call carries an id the client makes. The hub keeps each writing call's result, written in the same transaction as the call's own work and kept under the calling machine and the call id, and gives that result to a repeat. So a lost reply never applies twice, and one machine can never be given another's result. The three adoption calls keep no result. Each is safe to repeat by what it carries: the adoption id, the content digest, the config text.
- **A path means nothing without its machine.** Every stored path (a checkout, a run's directory, a session's directory, a log) is stored with the machine it is on, and is only ever opened there.
- **The hub's clock is the clock.** Expiry, heartbeats, ages and ordering use the hub's time and the store's sequence numbers. A hub call never takes the current time from the client, although the store functions take it from their caller today. A time read from a client's files, such as when Squadron says a run paused, is kept as an identifier and never compared with a hub time.
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

One process, `amoeba hub serve`, in a container on the LAN machine. Amoeba ships the image definition. The container has one published port and three mounted directories:

- **config:** two files and nothing else. The directory is writable, because adoption writes `config.yaml` there. `hub.yaml` holds what only the serving process needs (its port, `backup_dir`, `backup_hours`, `backups_kept` and the log limits), each required, with no default in code. `config.yaml` is today's config file, unchanged in shape. On the PM's hub it arrives at adoption. On a hub started fresh (a new user, a single machine, a test fixture) the person writes it from the example the image ships, as with `hub.yaml`. Until it exists the hub serves machines and invites, and every operation that needs it fails with the file named, as a missing config does today.
- **state:** the store, the hub's certificate and key, and the hub's log.
- **backups:** wherever `backup_dir` points. It has no default, and it should be on a different disk from the state directory, because a backup on the disk it protects is lost with it.

The container runtime starts it at boot and restarts it on failure. The process keeps nothing in memory that matters.

The hub contains Amoeba and nothing else: no `cf`, no Squadron, no agent runtime and no checkouts. Those arrive with 300's runner.

**Backups.** A backup is a consistent copy of the store, made with SQLite's own backup call, together with the certificate and key. So a hub started from a backup on any box is the same hub: the same machines, tokens and certificate. There are two kinds, kept apart so one cannot push out the other:

- **Timed.** One whenever the newest timed backup is older than `backup_hours`, checked at start and on a plain timer inside the process (not 300's scheduler). The newest `backups_kept` are kept. A hub that crashes and restarts in a loop therefore takes no new backup and cannot rotate the good ones out.
- **Before a migration.** One before the store's schema is changed, taken before the migration runs. The newest `backups_kept` of these are kept separately. Undoing a bad release is the previous image with `serve --from-backup` on that file.

The copy runs in a worker thread.

**The hub's log** is one file that rotates at `hub_log_max_bytes` and keeps `hub_logs_kept` files. Refused calls are lines in it, so a scanner hitting the port cannot fill the disk.

**Config.** The hub reads the config file on each call, as every command does today, so an edit takes effect at once with no restart. A bad edit fails every call that needs the config, on every machine, with the file and key in the error, exactly as a bad config does today. It never keeps running on an older copy.

**Admin commands** run on the hub machine, inside the container, and are CLI only:

| Command | Does |
|---|---|
| `amoeba hub serve` | Runs the hub. With `--from-backup <path>` and an empty state directory, it starts from that backup |
| `amoeba hub invite <machine>` | Prints one join line. For a new name it creates the machine. For an existing one it gives that machine a new token and ends the old one |
| `amoeba hub machines` | Lists machines with when each last called and the client version it called with |
| `amoeba hub rm-machine <machine>` | Removes a machine (see "Machines") |
| `amoeba hub backup` | Takes a backup now |

### The door and access control

The door is HTTPS with JSON, on the LAN. One call is not JSON: the adoption upload, whose body is the store copy. Each operation is one call that takes the operation's existing document plus who is calling.

- **Encrypted, with a pinned certificate.** The hub makes its own certificate and key at first start, in the state directory, with an end date far enough out that it is never a limit. The join line carries the certificate's fingerprint. At join, the client fetches the certificate, checks it against that fingerprint and saves it. From then on the client trusts that one certificate and nothing else, and the check happens while the connection is being set up, before any part of a request is sent. Host names are not checked; the certificate is the identity. A test proves that a hub with the wrong certificate never receives a token. The reason for encrypting is concrete: a token lets its holder set a wake command, so it must not cross the LAN in the clear.
- **One token per machine.** The hub stores only a hash. Every call carries the token; a call without a valid one is refused and logged. The token names the machine and, through it, the owner.
- **A token reaches only its own machine's commands.** A checkout's wake command can be set or changed only by the machine that checkout is on. So a leaked token cannot plant a command that runs on another machine, and removing the machine removes its checkouts and every wake command with them.
- **Otherwise all machines act as the PM.** There are no other per-machine rights.
- **The door a call came through is what the client says.** The rule that a wake command is set from the CLI only, never from MCP, is now kept by the client: `amoeba-mcp` never sends that field. The hub's own guard is the machine rule above.
- **A door version.** The hub states one number for the shape of the door. It changes only when an existing call changes in a way an older client cannot use; an added call or field does not change it. A client built for a different number refuses to proceed and prints both versions and the upgrade command. There is no negotiation.

### Repeats and failures

- **Retry.** A client that gets no reply repeats the same call, with the same call id, for a fixed retry time. If the hub applied the first one, the repeat returns that result.
- **The network times are constants, not settings.** The connect time, the read time and the retry time are each defined once in code that the client and the hub share, like the store's busy time today. Three things are worked out from them and must agree, which they cannot if each machine sets its own: how long the hub keeps a call's result (longer than the retry time), every claim's time limit (which allows for the retries of its last call), and the check that an `answer` fits inside the MCP call deadline. That check runs on the hub, where the config is, with the network times added. A change to one of these constants changes the door version. The two times only the adoption upload uses are outside this rule: nothing is worked out from them and the two sides need not agree.
- **Three outcomes.** A call ends as done, as refused (the hub answered no), or as unknown: no reply inside the retry time.
- **Unknown, for a person or an agent.** The result says so in those words and tells the caller to read the state (`inbox`, `list`) before sending anything again.
- **Unknown, for a command that runs by itself** (the pause hook, a detached `handle-pause`, the resume, the wake wrapper). It stops at that step and exits with the error in its log. It never guesses and never carries on. Whatever it had claimed is handed out again once that claim's time limit has passed (see "Work that belongs to a machine"), and the next attempt starts from what the store says, as a repeated `handle-pause` does today. One exception: the wake wrapper goes on when only the call that records its command's pid got no reply, as it does today when the store is held.
- **Kept results** are deleted by the hub's existing sweep once older than their fixed lifetime.
- **The tick does not retry.** An `amoeba-mcp` tick that gets no reply gives up, because the next tick is the retry. Ticks run one after another and never overlap, so an outage cannot pile up waiting calls. Tool calls keep the retry.

### Machines

A machine is a name the PM chose, a token, a last-called time and the client version it last called with.

- **Joining.** `amoeba hub invite desktop` on the hub prints one line holding the address, the certificate fingerprint and the token. `amoeba join <line>` on that machine writes the client file. That is the whole set-up for a machine with no Amoeba data of its own. The address should be a name that stays put, not a number the router hands out.
- **A machine that already has a local store** is refused by `join`, which names the two ways on: `amoeba adopt <line>` to move that store to an empty hub (below), or `amoeba join <line> --set-aside-local` to mark the local store as handed over, where it is, with a dated backup beside it, and join without it.
- **The client file** lives in the config directory with owner-only permissions, beside the saved certificate. It holds exactly the hub's address, the machine's name and its token. A client with no client file fails and says to run `amoeba join`.
- **A new address.** `amoeba join --address <address>` changes only the address in the client file. The token and certificate stay, so moving the hub or restoring it on a new box needs no new invites.
- **A lost or leaked token.** `amoeba hub invite <machine>` for the existing machine gives it a new token and ends the old one. Its checkouts and records stay.
- **Leaving.** `amoeba hub rm-machine` ends the token and, in one transaction:
  - removes the machine's checkouts and session rows;
  - closes every open question from a run on that machine as `machine_removed`. "Open" is today's meaning: claimed, waiting on the PM, held on a request, or answered with the resume not done. An answer waiting to be resumed there is marked not delivered with the same reason;
  - ends any wake still running in one of its checkouts as `machine_removed`, so it does not hold off another wake for that member.

  The machine's next call is refused. Bringing it back takes a new invite, a join, and `amoeba add` in each repo there.
- **A machine that goes quiet** stays listed with its last-called time. It accumulates nothing: what waits on it has its own end (below).

### Members by name

- **A member has a name,** unique in the store. It is what agents write in `send` and what `list` shows. It starts as the repo's Context Forge project name and can be set with `amoeba add --name`.
- **A checkout** ties a machine and that machine's Context Forge project id to a member, with the checkout's path and, optionally, its wake command.
- **Same repo means the same `origin`.** The client sends the address of the checkout's `origin` remote with every `add`. The hub reduces it to host and path: lower case, with the scheme, any user name, a trailing `.git` and a trailing slash removed, so the SSH and HTTPS forms of one repo match.
- **`amoeba add` looks for the `origin` first, then the name.**
  - A member already has that `origin`: the checkout is added to it, whatever it is named, and the result says which member. So a member that was renamed, or that kept its id as its name, never gets a second copy from another machine.
  - No member has that `origin`, and the name is free: a new member is created with this checkout.
  - No member has that `origin`, and the name is taken: refused, with both remotes shown, so two repos that share a name are never merged. The PM adds it with `--name`.
  - The repo has no `origin`: it can have one checkout only. A second is refused and says why.
- **Several agents in one repo are one member.** Agents on different machines, branches or worktrees of the same repo share the member and its inbox. Each sees the same mail, and the first `accept` of a request wins, as in 240. They cannot message each other, because an address is a member or a program, never a session. What a team would still need is per-person rights and lists, which is the owner seam and out of scope here.
- **Who is calling.** The client asks its local `cf` which project the directory is in, as today, so worktrees and subdirectories still resolve to one project. It sends that project id. The hub takes the machine from the token, never from anything the client says, and maps the two to the member. A project with no checkout on record is `not_a_member`, as today.
- **Who is addressed.** The name is looked up in the store. No `cf` call is made for a recipient, on any machine.
- **Removing by name.** `amoeba rm <name>` works from any machine and any directory, so a member whose last checkout is gone can still be removed. Removal cancels its open requests as `member_removed`, as in 240. Until then, a member with no checkout is shown that way in `list`, and requests to it wait for their expiry.
- **Registration is cut down to this:** add a checkout (creating the member if new), set a member's or a checkout's settings, and remove. Everything that resolved other members through `cf` goes.

### Three kinds of operation

| Kind | Operations | How it runs |
|---|---|---|
| Whole on the hub | `inbox`, `reply`, `cancel`, `send`, `answer`, `dismiss`, `retract`, `decisions`, `mark_read`, `changes`, `standing`, `withdraw` | The client adds who is calling and passes the document through. Names in results come from the store. |
| Client gathers, hub writes | `add`, `rm`, `list`, `status`, `report_release` | The client reads what only it can (its `cf` project, the repo's remote, its machine's Squadron runs) and sends that with the document. |
| Client runs, hub steps | `handle_pause`, the resume, the wake wrapper, presence and the push check, and the clean-up of local files | The command runs on the machine with the files. Each store step it makes today becomes one hub call. |

`answer` and `send` are whole on the hub for what they record. When the run, or the recipient's wakeable checkout, is on the calling machine, the reply also carries the claimed resume or wake and the client starts it in that same command.

The settings a client-run command needs (models, caps, timeouts) come from the hub with the first call, so the hub's config is the only one.

**Clean-up of local files.** Each machine keeps cleaning its own scratch and logs on today's trigger (at most once an hour, from any call). It asks the hub which runs are still open and deletes the rest past `prune_after_days`. The log of `handle-pause` calls stays on the machine whose hook made them. The hub cleans the store's rows and its own files.

### Work that belongs to a machine

Some work can only be done on one machine: resuming a run whose files are there, starting `handle-pause` for a held question when its request ends, and starting a wake in a checkout there.

- **Every reply says whether work is waiting.** Each hub reply, to any call and to each `amoeba-mcp` tick, carries one flag: this machine has work to start. It costs no extra call. A client that sees the flag makes one more call to claim the work, and starts it detached. This replaces today's "start after" step, which did the same on one machine after some operations only.
- **Each kind is claimed before it is started,** because several sessions on one machine ask at once. A claim goes to one asker. If the reply carrying it is lost, nothing runs, so every claim has a time limit on the hub's clock, after which the work is handed out again.

  | Work | Claim | Handed out again after |
  |---|---|---|
  | A wake | The wake row, as today | `wake_timeout_seconds`, as today |
  | A resume | New. The started mark is taken only when it is empty, or older than the limit with no outcome recorded | The resume's existing bound (`resume_bound_seconds`, worked out from `resume_wait_seconds`), with the network retry time in place of the one local store wait it allows for today. A resume that is slow to record its outcome because the hub blinked is still inside its claim |
  | `handle-pause` for a held question | The pause claim, as today | `answering_wait_seconds`, as today |

  A stale pause claim is closed today by a sweep that needs to know what became of the run, and only the run's own machine can read that. So it is that machine's next call that clears it, the same limit as for all work that belongs to a machine.

  Today's started mark is not a claim: it can be written again by any caller while the outcome is open. That was safe with one caller. It is not safe with every session on a machine asking, so the resume gets the claim above.
- **A refused resume is not pending work.** Only an answer whose resume was never started, or whose claim ran out, is handed out. A resume that Squadron refused is recorded as refused and shown in `list` with the reason, and is tried again only the ways it is today: a new `answer`, or `handle-pause` for that run. So nothing retries on every tick.
- **Same machine, no wait.** When the PM answers from the machine the run is on, the resume starts in that same call, as today. A `send` from the machine that has the recipient's wakeable checkout starts the wake in that same call, as today.
- **Another machine, and what that needs.** Work for another machine starts the next time anything on that machine talks to the hub: any `amoeba` call or any open session, in any repo. If nothing is running there, it waits. This is stated plainly because it is a limit: a wake or a resume across machines needs the target machine to be awake with something of Amoeba's running. Nothing is installed on clients to poll in the background. The call that causes the wait says so: `answer` and `send` name the machine the work is waiting for and when it last called, and `list` shows the same.
- **Waking.** `send` checks presence across all machines. If nobody is live in the recipient, the wake goes to a checkout that has a wake command. The first machine with such a checkout to ask claims it, with today's limits and wrapper. If none asks, the request waits for the next agent or its expiry, exactly as a member without a wake command does today. Waking a repo with no machine awake is what 300's runner on the hub is for, and it is in 300's scope in the plan.
- **Every wait ends.** Pending work is never its own record. It ends when the machine does it, when the record behind it ends (the question is dismissed or closed, the request expires or is cancelled), or when the machine is removed, by the writes listed under "Leaving".

### Sessions across machines

`amoeba-mcp` stays a local process started by the session, because it must know the session's directory and push into that session. It becomes a client.

- **One tick.** Every `notify_poll_seconds` it makes one hub call that reads its member's highest delivery number, and refreshes its session row when a heartbeat is due. Its reply carries the work flag like any other. The call runs off the event loop, as its store reads do today, one tick at a time and without retry. Channel events, the pinned handshake and the `inbox` rule are unchanged from 240.
- **The directory.** A session row gains its machine and its client version. `list` and `status` show who is working where, across machines. A stale row is judged against the hub's clock.
- **Runs on other machines.** `list` and `status` check the fate of Squadron runs only on the machine that calls them, since only it can read those run files. Runs on another machine, and questions from them, show as last reported, with that machine named.

### Owner

The hub creates one owner, the PM, when it first starts. Machines belong to an owner. Every table that holds records has its owner, taken from the calling machine. Reads do not filter by owner, because there is one. This is the seam for a later version with more than one person, and nothing more is built on it here.

### How the build gets there

The hub's side of every operation is today's operation code. During this initiative that code is reached two ways, and which one a machine uses is decided by one thing: whether it has a client file.

- **No client file:** the command runs the client part and the hub part in one process on the local store, as today. The PM's install stays this way until adoption.
- **A client file:** everything goes to the hub. An operation the door does not serve yet fails and says so. Only test fixtures run this way before the adoption slice (264).

Four rules keep this simple:

- **Decided on every call,** never once per process. A session's `amoeba-mcp` that was started before the machine joined uses the hub from its next call.
- **With a client file, no local store is ever opened or created.** The code that opens a local store is not reached, so a missing file can never be quietly recreated. After adoption one exception stays: `adopt` run again and `discard-local` open a handed-over store read-only to compare its digest. Nothing creates one.
- **One schema.** Every schema change in this initiative (member names, checkouts, machines, owner) is an ordinary migration that both ways run on. The local store gets one machine, standing for the install.
- **One lookup.** Once members have names, both ways find a recipient in the store.

**Naming the members that already exist.** The migration cannot ask `cf`, so the first `amoeba` call after the upgrade does, once, for every member in the store: it records each one's Context Forge name as its member name, its path as its checkout, and its `origin`. Two cases have a fixed answer. A member `cf` no longer knows keeps its id as its name. If two members have the same Context Forge name, the one registered first gets the name and the other keeps its id as its name. `list` shows any member still named by its id, and `amoeba add --name` renames it. Until this has run, every other call on that install runs it first, so no call ever sees a member without a name.

The adoption slice (264) moves the PM's store to the hub and deletes the no-client-file way. After it there is one mode.

### Moving the PM's live store

The live store and config are designated for this move. By this point the laptop's store is already at the new schema and its members are named, so the move is a copy. It is one command, `amoeba adopt <join line>`, run on the laptop in place of `join`, by the release that ships it (`scripts/update_live.py update`), after review and the merge. The client file is written last, so there is no time when the laptop points at a hub that does not yet have its data.

1. **Checks.** It refuses unless the hub is empty, meaning it holds no record: nothing but its owner, its machines, and what the hub writes for them by itself (sessions, last reported runs, kept call results). This check is made before anything on the laptop changes. It then backs the store up, migrates it, and lists each session still open on the laptop with whether it must be restarted; the migration has already stopped those sessions writing, so none has to be closed and none holds adoption up. It refuses if any member is still unnamed.
2. **Name the adoption.** It writes an adoption id into the local store and commits it. Every later step carries that id.
3. **Copy under lock.** It takes the local store's write lock and holds it until step 6, so no hook or command can write in between. It copies the store with SQLite's own backup call, which includes everything committed, and sends the copy.
4. **Load.** The hub loads the copy, records the adoption id, renames the install's one machine to the name in the join line, and puts the join line's token on it. It checks the copy's row counts against counts the laptop took under the lock before it touches its own store, then replaces its store with the copy in one step. A mismatch refuses the load and leaves the hub as it was.
5. **Config.** The laptop sends its config file. The hub validates it and writes it as its `config.yaml`. If the hub already has one, it keeps its own and the result says so. `hub.yaml` is untouched.
6. **Switch.** In the transaction that holds the lock, the laptop marks its store as adopted, naming the hub and the copy's digest, and commits. It then writes the client file and prints the backup's path. The store stays at its path, marked; the dated backup was taken before the migration.

**The adopted mark** closes one gap. A hook that was already waiting on the lock decided to use the local store before the client file existed. When the lock is released it would write into the handed-over store, and that write would be lost without a word. Every local write checks the mark first, so that hook fails and names the hub, and its run shows on `list` as a paused run with no record.

**Running it again is safe.** If a reply is lost, or the switch fails on the laptop, the hub may already hold the data while the laptop has no client file. The same command run again carries the same adoption id from the local store. A hub that already holds that adoption, and whose loaded content digest equals the laptop's now, skips the load and goes on to the config and the switch. If the laptop's digest differs, because something was written locally between the two attempts, and the hub's own has not moved, it loads the new copy in place of the old. If both moved, it refuses, because two stores are never merged. A hub that holds anything else refuses and says what it holds. The way to empty a hub is `docker/hub-restore.sh --empty`, which sets its store, certificate, key and backups aside and starts it new. The backups go too, because a hub does not start on an empty state directory while its `backup_dir` holds a backup.

After this, no client reads a local store or a local `config.yaml`, and the 228 state-move code is deleted.

### Moving or undoing the hub

A hub is its backup. To run it somewhere else, the laptop included: `amoeba hub backup` on the old box, `amoeba hub serve --from-backup <path>` on the new one, and `amoeba join --address` on each machine. Machines, tokens, the certificate and every record carry over, so nothing is lost and nothing is re-invited. This is also how to stop using the LAN box.

If adoption went wrong in a way found later, there are two ways back. `amoeba leave`, empty the hub, and `amoeba adopt <line> --again` adopts the laptop's store, as it was at adoption, into the emptied hub. Or `scripts/update_live.py restore --local-store` puts the pre-migration backup and the config back under the previous release. Both need the handed-over store or its backup, which `amoeba discard-local` deletes.

## Operator walkthrough

Done as the PM running it.

1. **Start.** On the LAN machine: write `hub.yaml` in the config directory (the image ships an example) and start the container. A missing or bad key stops the start and names it. `amoeba hub invite laptop` prints a join line. On the laptop: `amoeba adopt <line>`, which the release runs. On each other machine: an invite, a join, and `amoeba add` in each repo there.
2. **Adoption is refused.** The hub is not empty: it says what it holds. A pause hook fires during the copy: it fails with the join message, and a command of an older release that was already running fails because the lock wait ran out or because it finds the store marked as adopted. Either way its run shows on `list` as a paused run with no record, with the command to handle it. A reply is lost or the switch fails: run the same command again.
   - **A fresh hub, with no store to adopt** (a new user, or one machine). Write `hub.yaml` and `config.yaml` from the image's examples, start the hub, then an invite, a join and `amoeba add` in each repo.
3. **Normal path.** A session on the desktop sends a request to `context-forge`. A session open in context-forge on the laptop gets the push within a tick and handles it. `list` on either machine shows the same requests, questions and sessions.
4. **A run pauses on the laptop; the PM answers from the desktop.** The answer is recorded and `answer` says the run is on the laptop and when the laptop last called. The laptop resumes it at its next call. If the laptop is asleep, it resumes when the PM next opens a session there. Three sessions open on the laptop ask at once; one gets the resume.
5. **A request to a repo whose only wakeable checkout is on a machine that is off.** `send` says the wake is waiting for that machine. The request waits for an agent or its expiry.
6. **The hub is down.** A call retries for the fixed retry time, then fails with the hub's address in the error. `amoeba-mcp` stays up, its tools return that error, and it recovers at its next tick. The container restarts the hub. A pause hook that fires meanwhile fails the same way, and its run shows on that machine's `list` as a paused run Amoeba has no record of, as a missed hook does today, with the command to handle it.
7. **The hub restarts in the middle of a `handle-pause`.** The command gets unknown at one step, stops, and logs it. Its claim runs out, and the next call from that machine sees the work flag and starts `handle-pause` again from what the store holds. This holds once the question's row is written. If the hub went down before that, there is no claim to run out: the run shows on that machine's `list` as a paused run with no record, with the command to handle it, as in step 6.
8. **A reply is lost.** The client repeats the call and gets the first result. If the hub stays unreachable, the result is unknown and says to check `inbox` or `list` first.
9. **Changing a setting.** Edit the config file in the hub's config directory. The next call uses it. A bad edit fails every call with the file and key named, until it is fixed. Nothing is set on the clients.
10. **Upgrading.** The release updates the hub first, then the client it runs on, and lists the machines and sessions that are behind. Most releases leave the door version alone and nothing else happens. When it does change:
    - a one-shot `amoeba` call on a machine not yet upgraded refuses and prints the upgrade command;
    - an open session's `amoeba-mcp` is still the old program, so its tools return the same message until that session is restarted. `list` and `hub machines` show which sessions and machines are behind;
    - a pause hook on a machine not yet upgraded fails, and its run shows as a paused run with no record, as in step 6.
11. **A token leaks.** `amoeba hub invite <machine>` gives it a new one and ends the old.
12. **A machine is retired, or never comes back.** `amoeba hub rm-machine`. Its checkouts, wake commands and sessions go, its open questions close as `machine_removed`, and a wake running there is ended. Members that had a checkout elsewhere carry on. A member with no checkout left stays, with its mail, until `amoeba rm <name>` from any machine or a new `add`.
13. **Two repos with one name.** The second `add` is refused with both remotes shown. The PM adds it with `--name`.
14. **The hub's disk is lost.** Start a hub on a new box from the newest backup in `backup_dir`. If the address changed, `amoeba join --address` on each machine. The certificate and tokens came with the backup, so every client connects as before. What was recorded since that backup is lost; that is at most `backup_hours`.
15. **Undo the whole thing.** Move the hub to the laptop, as under "Moving or undoing the hub".

Dead ends found: none. One limit, stated in the design: work for a machine waits until something on that machine calls the hub, and the call that caused it says so. Each such wait ends with its record.

## Technical Considerations

- **The pause path is the large change.** `handle_pause`, the resume and their sweeps make about twenty store transactions between reads of local run files. Each becomes a hub call. The answering pipeline is deleted by 320, so it is changed only where it touches the store: its reads, its final write, and the answer-limit check, which moves to the hub.
- **Operations must be pulled apart.** Today one function reads local files, writes the store and starts commands. Each needs a clear line between what the client gathers, what the hub does and what the client then starts. The existing injected edges mark most of that line already.
- **The server.** A small web app on the server library that `mcp` already installs, so the door adds no new server dependency. Making the certificate needs `cryptography` as a direct dependency. Each request does its store work in a worker thread on its own connection, so no store call runs on the event loop and SQLite orders the writers as it does today. The backup copy runs the same way.
- **The client's connection.** Python's standard library, with a TLS setting that trusts only the saved certificate and does not check the host name. That makes the certificate check part of setting up the connection, which is what keeps the token from being sent to the wrong hub. It is not done by turning checking off and comparing afterwards.
- **Load test.** Required by the Python rules for network code. It runs many sessions ticking while CLI calls write, and asserts a bound on call time and that no tick is starved.
- **Latency.** A whole-on-hub CLI call is a `cf` call plus one round trip; a client-run command makes one call per store step, counted in 262 D16. The push tick is one small call per live session. How fast a turn-end answer must be is 320's question.
- **What a token is worth.** It allows what the PM's own commands allow on that one machine, a wake command included, and everything in the store. That is why the door is encrypted, tokens are per machine, and a wake command can be set only from its own machine. Message text is still data written by other repos' agents, and is treated exactly as in 240.
- **Logs stay where the work ran.** A wake's or a resume's log is on the machine that ran it. The hub stores the machine and the path, and `list` shows both.
- **Testing.** The hub runs in-process against a throwaway store in unit tests. A live fixture runs one hub and two client homes with different machine names on one computer, which exercises every cross-machine path without a second computer.
- **Facts about other tools are dated.** The Context Forge id format was read 20261120. Each slice re-checks what it depends on.

## Anticipated Slices

Provisional. Each slice up to adoption leaves the PM's install working on its local store; the release that ships adoption moves it.

- **Hub and door:** `amoeba hub serve`, the certificate, machines and tokens, invite and join, call ids and repeats, the door version, the owner, backups and the log, the container, and the whole-on-hub operations served through it.
- **Members by name:** member names and naming the existing ones, checkouts, the `origin` rule, caller and recipient lookup, `rm` by name, registration cut down, and the wake command moved to the checkout.
- **Local work through the hub:** `handle_pause`, the resume and its new claim, the wake wrapper and waking a checkout on its machine, work that belongs to a machine, what each command does on unknown, and clean-up of local files.

  Two checks belong to this slice's design and are not yet done. They are stated here because the design will be written without this document's working context. (A third, whether the pause claim has a time limit, was answered 20261120: it does, `answering_wait_seconds`, in `operations/pause_class.py` and the claimed branch of `operations/question_sweep.py`.)
  1. **Which transactions run a check or read a local value inside them?** List every one in the pause path and the answering settle before splitting anything. `settle_answered` in `store/answers.py`, which takes the answer-limit gate as a function, is the known case. Each moves to the hub with its values sent in the call.
  2. **Which store functions take the current time from their caller, and which sweeps compare a client's time with a store time?** `mark_resume_started`, `claim_held` and `claim_wake` take it today, and `operations/question_sweep.py` compares answer times. On the hub every one uses the hub's time, and a run's paused time from Squadron is only ever an identifier.
- **Sessions across machines:** `amoeba-mcp` as a client, the single tick, presence with machines, and the directory in `list` and `status`.
- **Adoption:** `amoeba adopt`, starting a hub from a backup, the hub's config, deleting the local-store way and the 228 state move, and the contract documents.
- **Members in several programs** (added by the PM 20261120): membership becomes its own record keyed by member and program, so a repo two programs depend on is a member of both. Today a member row holds one program. It runs after adoption, as an ordinary migration on the hub.

## Related Work

- `000-concept.amoeba.md`, "How it runs", and `001-initiative-plan.amoeba.md`, initiative 260: the scope this starts from.
- `240-arch.agent-messaging`: messages, push, presence, hold and release, and waking, which this carries across machines.
- `220-arch.program-tool`: the operations, the two doors, the pause entry and the resume.
- `notes/008-code-sort.amoeba.md`: the line counts used above.
- `notes/006-long-running-agents.amoeba.md`: the long-running agent this is the first step of.
- `user/reviews/260-review.arch.the-hub.md`: the latest review of this document. The first review is in git history.
- Retired slice 109 (network API): an earlier door on the resident supervisor. Nothing of it is reused.
- `docs/cli-contract.md`, `docs/config-contract.md`, `docs/store-contract.md`, `docs/mcp-server.md`, `docs/squadron-hook.md`: the contracts this changes.
