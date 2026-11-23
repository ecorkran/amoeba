---
docType: slice-design
slice: members-by-name
project: amoeba
parent: user/architecture/260-slices.the-hub.md
dependencies:
- 260
interfaces:
- 262
- 263
- 264
dateCreated: 20261120
dateUpdated: 20261121
status: not_started
turns: 32
promptTokens: 3292508
cachedTokens: 3062008
cacheWriteTokens: 230458
completionTokens: 51404
durationSeconds: 589.3
costUsd: 6.356556
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-fable-5-2:
    rounds: 1
    costUsd: 6.3565559
    completionTokens: 51404
---

# Slice Design: members-by-name

## Overview

Today a member is a Context Forge project id. Context Forge makes that id on one machine, so the same repo on a second machine is a different id and cannot be the same member. Every call that names a member also runs the local `cf` to find it.

This slice gives a member a name and an id of its own. A Context Forge id now belongs to a **checkout**: one copy of the repo on one machine. A member has one checkout per machine and clone, and all of them share the member's inbox. Members are found by name in the store, and `cf` is asked only about the caller's own directory.

Ten more operations are served through the door: `add`, `rm`, `list`, `status`, `inbox`, `reply`, `cancel`, `changes`, `report_release`, and `send` when no wake is due.

The PM's install has no client file, so it keeps running on its local store. Its existing members are named on the first call after the upgrade.

## Value

User value. An agent in a repo on one machine sends a request to a repo by name, and an agent in a checkout of that repo on another machine reads it at its next `inbox`. Two machines, two clones or two worktrees of one repo are one member with one inbox.

It also removes the `cf` call from every member lookup, so a call no longer depends on what the calling machine's Context Forge knows about other repos.

## Technical Scope

Included:

- Migration 012: the member's id, name and `origin`, and the `checkouts` table.
- Naming the members that already exist, on the first call after the upgrade.
- The `origin` rule that decides when two checkouts are the same repo.
- `add` rewritten around checkouts, with `--name`. `rm` by name from anywhere, and `rm --checkout`.
- The caller lookup (machine and Context Forge project id) and the recipient lookup (name in the store).
- The wake command moved from the member to the checkout.
- Every lookup of another member through `cf` deleted.
- Each of the ten operations split into a client part that gathers local facts and a hub part that uses them.
- The ten operations served through the door. `amoeba hub rm-machine` also removes the machine's checkouts.

Excluded, because the slice plan puts them in later slices:

- `handle_pause` (apart from passing the caller's Context Forge id into `PauseTarget` where it is built, which D6 needs), `answer`, the question sweeps, starting a wake through the door, the work flag, the machine on question and wake rows, and clean-up of local files through the door (262).
- `amoeba-mcp` as a client, and runs on other machines shown in `list` and `status` (263).
- `amoeba adopt` and deleting the local-store way (264).

## Dependencies

### Prerequisites

- Slice 260, built. As of 20261120 it is designed and in review, not built. This design uses its decisions as written at commit `9ee28aa5`, read again on 20261121 after 260's full-text review: the door and its call format (260 D6), the call scope and what `handle_call` does when an operation raises (D8), kept results (D9), the served list and `run_served` (D11), machines, the owner, the acting machine and the two store openers (D12), `rm-machine` (D13), and the two-machine fixture and its seeding (D18). Three things there are used here by name: `OPERATION_ERRORS` in `operations/errors.py` (D8), `open_hub_store`, which never creates a store outside a first start (D12), and the body-key rule in its Integration Points (D5 here).
- No new package.

### Interfaces Required

- `operations.served.run_served` and `wire.protocol.SERVED_OPERATIONS`, `WRITING_CALLS` and `UNKNOWN_ADVICE` (260).
- `Store.act_as` and the acting machine, which gives every insert its owner, and gives this slice the calling machine.
- `open_state_store`, which creates the `local` machine. The naming step runs there.
- `hub.calls.handle_call` and `operations/errors.py` (260 D8). This slice adds one exception there and one branch to the handler (D12).
- `upstream.context_forge.project_of` for a directory, and `projects.project_details` (`cf list projects --json`).
- `upstream.git_read.git_read`, the one runner of `git`.
- `scripts/update_live.py`.

Facts about other tools, read 20261120 on this machine:

- `cf` 0.19.28. `cf get --json` in a directory gives `id` (`project_<time>_<random>`), `name` and `projectPath`. `cf list projects --json` gives `id` and `name` for every project and `projectPath` for 30 of the 31 here. No two of the 31 share a name.
- `cf get --json` in a directory answers only for a project that has a `projectPath`: `project_of` treats an answer without one as a failed call. So no call can come from a project with no path.
- The live store holds four members. `cf` lists all four with a path, and no two share a name or an `origin`. So on the PM's install naming gives each its Context Forge name, its `origin` and one checkout, and drops no wake command.
- `cf` commands that take `-p <id>` fail for an id Context Forge does not know: `cf config get git.integration_branch --json -p <32 hex characters>` exits 1 with "Project ... not found" (run 20261121). So a member id made here is never passed to `cf` (D6).
- Worktrees, run 20261121 in a throwaway Context Forge home. In a worktree registered with `cf worktree init`, `cf get --json` gives the same project `id` and the worktree's own directory as `projectPath`. `cf list projects --json` gives the primary checkout's path. So one checkout row can be reached from several directories, and D7 fixes its path when the row is made.
- `git` 2.50.1. `git remote get-url origin` prints the address. It exits 2 with `No such remote` when there is none, and 128 outside a repo. 128 is also git's code for other fatal errors, so D5 does not use it to mean "not a repo".

## Architecture

### Component Structure

| Package | Modules | Change |
|---|---|---|
| `amoeba.store` | `schema/012_members_by_name.sql` (new), `checkouts` and `sql_checkouts` (new); `programs`, `models`, `sql`, `wakes` | The migration. Checkout reads and writes. Member rows gain `name` and `origin` and lose `wake_command`. Lookups by name, by `origin` and by checkout. `claim_wake` reads the command from a checkout. |
| `amoeba.operations` | `origin` (new) | `reduce_origin` and `is_reduced_origin`, pure functions (D3). |
| | `here` (new) | The client part: what a call gathers from its own directory (D5). |
| | `naming` (new) | Naming the members that exist (D4). |
| | `caller` (new, replaces `members`, `member_reference`, `project_lookup`) | The caller lookup and the reference lookup, both on the store (D6). |
| | `add`, `rm`, `set_up`, `set_up_resolve`, `set_up_remove`, `set_up_remove_resolve`, `set_up_models` | Rewritten around checkouts and names (D7, D8, D10). |
| | `message_member`, `release_member`, `send`, `wake`, `inbox`, `reply`, `cancel`, `changes`, `report_release`, `standing`, `decisions`, `program_sources`, `pause_eligibility` | Take the gathered caller in place of a directory and a `cf` runner. Names come from the store. |
| | `pause_context`, `program_sources` | Every `cf -p` call takes a checkout's Context Forge id, never the member id (D6). |
| | `errors` | `ContextForgeError` moves here (D10). `CallRefused` is new (D12). |
| | `run_gather` (new), `runs_document` (new) | The client part's read of the machine's runs, and the plain document it produces (D11). |
| | `status`, `status_placement`, `status_runs`, `status_calls`, `list_view`, `list_registry` | Take the runs document in place of reading the disk. |
| | `served` | Ten more cases. |
| `amoeba.wire` | `protocol` | The ten names, the six new writing calls and their advice, and the two new body keys. |
| `amoeba.hub` | `admin` | `rm-machine` deletes checkouts. |
| | `calls` | The handler's branch for `CallRefused` (D12). |
| `amoeba` (wiring) | `wiring`, `wiring_registry`, `wiring_messages`, `wiring_releases`, `wiring_presence` | Each placement runs the client part, then the hub part or the door call. |
| | `wiring_results` | `result_from_document` rebuilds the ten operations' results. |
| `amoeba.mcp` | `message_tools` | The time each message tool's description states (D10). |
| `amoeba.cli` | `registration_arguments`, `commands`, `render/registration`, `render/registry` | `--name`, `rm --checkout`, and `--project` read as a member. The `cf` call for names in `commands` is deleted. |

Import rules added to `tests/test_import_boundaries.py`:

- `operations.here`, `operations.naming` and `operations.run_gather` are the only modules in `operations` that import `upstream.context_forge.project_of` or `projects`. `status_placement` loses its import; the lookup it needs is in the runs document.
- `operations.served` imports none of those three modules. They run only in the client part.
- `amoeba.hub` still imports nothing from `upstream` (260). The fixture hub's `PATH` holds no `cf`, `sq` or `git`, so a hub-side call to any of them fails a test.

### Data Flow

Every operation in this slice has two parts.

1. **The client part** runs on the calling machine. It reads only what that machine can: the directory's Context Forge project, the repo's `origin`, the machine's Squadron runs. Its output is a JSON document, the gathered facts.
2. **The hub part** takes the request document, the gathered facts and the calling machine, and does all store work. It calls no `cf`, `git` or `sq`.

With no client file, `wiring` runs the client part and then the hub part in one process on the local store, with the `local` machine as the calling machine. With a client file, it runs the client part and sends the document and the gathered facts in one door call; the hub runs the hub part with the token's machine.

A `send` from machine `alpha` to the member `forge`, whose only checkout is on machine `beta`:

1. On `alpha`, the client part runs `cf get --json` in the caller's directory and gets its project id.
2. The call carries the document and `here: {project_id}`.
3. On the hub, the caller is the member whose checkout is (`alpha`, that project id). The recipient is the active member named `forge`. The request and its delivery are written. No wake is due, because `forge` has no checkout with a wake command (D9).
4. On `beta`, an agent in a checkout of `forge` runs `inbox`. Its caller lookup gives the same member, and the request is there.

### State Management

| State | Where | Ends by |
|---|---|---|
| A member | `members` | `amoeba rm <name>`, from any machine. The row stays as the record of its questions, as today (228 D8). One row per repo ever registered |
| A member's name | `members.name` | Changed by `amoeba add --name`. A removed member's name is free for another member |
| A member with no name | `members.name` null, only between the migration and the first call | The naming step, which every local store open runs first. On a hub store, `open_hub_store` names it by its id (D4) |
| A checkout | `checkouts` | `amoeba rm --checkout <path>` on its machine, `amoeba rm <name>`, or `amoeba hub rm-machine`. Its path is set when the row is made and never changed; a repo moved on disk is `amoeba rm --checkout <old path>`, then `amoeba add` in the new place (D7) |
| A wake command | `checkouts.wake_command` | `amoeba add --no-wake-command` in that checkout, or the checkout's removal |
| The old wake command | `members.wake_command` | Moved to the checkout and set to null by the naming step. Never written again (D4) |
| A member with no checkout | `members` with no `checkouts` row | `amoeba add` in a checkout of the repo, which attaches by `origin`; `amoeba add --attach-to <name>` there when the member has no `origin` (D7); or `amoeba rm <name>`. Requests to it wait for their expiry, as the architecture says |

This slice writes nothing new outside the store. The backup `update_live.py` takes is the one it already keeps, one set at a time (D16).

## Technical Decisions

### D1 — The member's id and name
Status: decided

**The id.** `members.project_id` stays the member's key, under the same name in the store, the code and every result. It is now documented as an opaque text key that is never parsed. A member that exists today keeps its value, which is the Context Forge id it was registered under, so no row in any table changes. A member created from now on gets `uuid4().hex`.

- Rejected: renaming the key to `member_id`. It would change result fields and about 36 source files, and the architecture says results stay as they are. The store contract says what the value is.
- Rejected: using the first checkout's Context Forge id as a new member's id. If that directory is later pointed at another repo, a second member would be created under the first one's id.
- Rejected: the name as the key. A rename would rewrite every table.

**The name.** `members.name`, compared without regard to case (`COLLATE NOCASE`). A name matches `[A-Za-z0-9][A-Za-z0-9._-]*` and is at most 64 characters. That excludes the `:` that `--pair` and `--concept` split on. Every Context Forge id matches it.

A name is unique among active members, by a partial unique index over rows whose `removed_at` is null. A removed member keeps its name for display and does not hold it against anyone.

An active member's name may not equal the id of any other member, active or removed. Ids are shown in results and accepted as references (D6), so such a name would send a reference by id to the wrong member. The name is compared with ids without regard to case, as names are with each other, because `find_member` tries the name first. `add` refuses it as `name_taken`. A removed member's name is checked against nothing, because no lookup finds a removed member by its name (D6).

A new member's name is `--name`, or else the Context Forge project name of the checkout that creates it. A Context Forge name that does not match the pattern is refused as `malformed`, and the detail says to give `--name`.

`list members` marks a member whose name is its id, with the `add --name` command to rename it.

### D2 — The schema: migration 012
Status: decided

One migration, `012_members_by_name.sql`, run by both ways.

- `members.name TEXT COLLATE NOCASE`, null until named. `members.origin TEXT`, the reduced form (D3) or null.
- A unique index on `name` and one on `origin`, each over active rows only. SQLite treats nulls as distinct, so any number of members can have no `origin`.
- A `BEFORE INSERT` trigger on `members` that aborts when `name` is null, the same pattern 260 uses for the owner. So only rows from before the migration can be unnamed.
- **`checkouts`**: `checkout_id` (integer key), `member_id` (references `members.project_id`, as every other table's `member_id` does), `machine_id` (references `machines`), `cf_project_id`, `path` (never null), `wake_command` (null for none), `owner_id`, `added_at`, `updated_at`. Unique on `(machine_id, cf_project_id)`: one Context Forge project on one machine is one checkout of one member. An index on `member_id`. The 260 owner trigger is added for this table.

`members.wake_command` stays as a column. The migration cannot move it, because a checkout needs a machine and the local store's machine is made by the opener, not by a migration (260 D12). The naming step moves it (D4). After that the column is always null. The statements that read and clear it are constants in `store/sql.py`, where `tests/store/test_members_queried_in_one_place.py` requires every statement on `members` to be, and no other statement names the column. A test pins that, and that `operations.naming` is the only module that uses those constants; the hub's `name_by_id` (D4) is in that module.

The migration only adds. It deletes and rebuilds nothing.

### D3 — The `origin` rule
Status: decided

`operations.origin.reduce_origin(address)` gives `host/path` or nothing. It is a pure function. The client part runs it on what git printed, so only the reduced form is sent, as the plan says. The hub part does not reduce again, because the two accepted forms below do not include a reduced form: `github.com/ecorkran/amoeba` has no scheme and no colon, so it would read as a path and give nothing, and `example.com:8443/org/repo` would read as the SSH short form and come out changed. The hub part checks instead, with `is_reduced_origin` in the same module: the value is `host[:port]/path` with a host and a path, in lower case, with no `://`, no `@` in the host, no trailing slash and no trailing `.git`. A value that fails the check is refused as `malformed_call` and nothing is written (D12).

- Accepts the URL form (`scheme://[user[:password]@]host[:port]/path`) and the SSH short form (`[user@]host:path`).
- Drops the scheme and the user name and password. A port stays part of the host. Lower-cases the rest. Removes a trailing slash, then a trailing `.git`, then a trailing slash.
- An address with no host (a filesystem path or `file://`) gives nothing. A path means something only on its own machine, so it cannot say that two checkouts are the same repo.

So `git@github.com:ecorkran/amoeba.git` and `https://github.com/ecorkran/Amoeba/` both reduce to `github.com/ecorkran/amoeba`.

The address as git printed it can hold a password. It never leaves the client part: it is not sent, stored, logged or returned. Results and refusals show reduced forms only. `reduce_origin` never raises: text it cannot read as a host and a path gives nothing, the same as no `origin`. No exception or log line made by the client part or the hub part of `add` includes the raw address. The test for `reduce_origin` uses the real forms `git remote get-url` prints, including this repo's own, and asserts that every value it gives passes `is_reduced_origin`, one with a port included.

### D4 — Naming the members that exist
Status: decided

`open_state_store` runs `operations.naming.name_members` after it has the `local` machine and before it returns the store. So every command, the pause hook and `amoeba-mcp` name the members before anything else reads one. `open_hub_store` cannot run it, because the hub has no `cf`. It runs `operations.naming.name_by_id` instead, described under "On a hub store" below.

The steps:

1. One read: is any member unnamed? If not, return. This is the only cost after the first call.
2. One `cf list projects --json` call.
3. For each unnamed member whose project has a path, `git remote get-url origin` in that path.
4. One write transaction, over the members that are still unnamed, in `registered_at` order:
   - **Name.** The Context Forge name, when `cf` lists the project, the name matches the pattern, no active member already has it, and it is not another member's id. Otherwise the member's id. That covers the three fixed cases: a project `cf` no longer knows, a name clash (the member registered first gets the name), and a name with characters the pattern does not allow.
   - **`origin`.** The reduced address. Null when there is no path, the directory is missing, it is not a repo, it has no `origin`, the address has no host, or the `git` call failed or timed out (below). Null also when an active member already has that `origin`; the later-registered one keeps none, and the log line says so.
   - **Checkout.** For an active member whose project `cf` lists with a path: one row with the `local` machine, the member's id as `cf_project_id`, the path and the member's wake command. A project with no path gets no checkout. No call can come from it (see the facts above) and nothing can run in it, so the row would never be read.
   - `members.wake_command` is set to null. For a member that gets no checkout, the command had no directory to run in and is dropped. The log line holds the member's id and the command's text, so it can be set again with `amoeba add --wake-command` once the member has a checkout.

A removed member gets a name and an `origin` by the same rules without the clash checks, and no checkout. Its name is for display only (D1).

**On a hub store.** A hub store gets members through `add`, which names them, and through 264's adoption, which names them on the laptop before the copy. So the only hub store with an unnamed member is one that held members at schema 11: a 260 fixture seeded with them, or a backup of one started with `serve --from-backup`. No install has one. The case still gets an answer, so that it is not a failed read with no way out: after the migration, `open_hub_store` runs `name_by_id`, one write that gives every unnamed member its id as its name and sets its old wake command to null with the log line above. This is the architecture's rule for a member `cf` does not know. Ids are unique and no name equals another member's id (D1), so it cannot clash. It inserts nothing, so it needs no acting machine (260 D12). Such a member has no checkout and no `origin`, and is renamed, attached or removed like any other member named by its id (Operator Walkthrough). `name_by_id` starts with the same one read as step 1 above and writes only when that read finds an unnamed member. So on every later open, which on the hub is once per call, it takes no lock, and the open stays the plain read 260 D8 pins.

**Failures.** If `cf` fails, the step raises the operational error, nothing is written, and the call exits 3. The next call tries again. It never names a member by its id because `cf` was briefly broken. A machine where `cf` does not work could not resolve its own directory either.

A `git` call that fails or times out (a checkout on a hung mount, no `git`) does not stop the step. That member is named with no `origin`, and a warning is logged with the path. A missing `origin` only ever refuses and never matches, and the next `amoeba add` in that checkout records it (D7, step 1). Each call waits at most `ORIGIN_READ_TIMEOUT_SECONDS` (10, a constant in `operations.here`).

**How long it can take.** The step runs once per store. Its `cf list projects` call has the existing `CF_PROJECTS_TIMEOUT_SECONDS` (30). The `git` calls run one after another and share `NAMING_GIT_SECONDS` (30, a constant in `operations.naming`): once that much has been spent, the members not yet read are named with no `origin`, the same as a failed call, and the warning says so. So the first call after the upgrade waits at most about 70 seconds more than usual, whichever command it is.

**Two calls at once.** Both gather. The second to take the write lock finds no unnamed member and writes nothing.

**Two members that are one repo.** If two existing members have the same `origin`, they stay two members. The first has the `origin` and is the one a second machine attaches to. `list members` shows the other with no `origin`; like any repo without one, it keeps the one checkout it has. Merging members is not built. `amoeba rm` removes the spare, which does what removal always does (D8): its open requests are cancelled as `member_removed`, its row and past records stay, and nothing reads its inbox again. A request still wanted is sent again to the member that stays. The live store has no such pair (see the facts above).

### D5 — The client part and what it sends
Status: decided

`operations.here` holds the client part. It gathers two things, and each operation uses what it needs:

| Gathered | How | Used by |
|---|---|---|
| **The caller**: `{project_id}`, or `{not_a_project: <cf's message>}` | `cf get --json` in the directory | `send`, `inbox`, `reply`, `cancel`, `changes`, `report_release`, `status`, `list` with no subject, `rm` with nothing named |
| **The checkout**: `{project_id, name, path, origin}` with `origin` the reduced form (D3) or null, or `{not_a_project}` | The same `cf` call, then `git remote get-url origin` in `path`, reduced | `add` when an entry names no member |
| **The runs** (D11) | `sq runs list`, run files, the calls log | `status`, and `list` with no subject |

Through the door these travel beside `document` as the body keys `here` and `runs` (260, Integration Points: a call that needs values only the client can read adds a key beside `document`). With no client file the same values are passed in process.

The hub part never guesses a missing value. A call whose operation needs `here` or `runs` and arrives without it, or with one that does not parse, is refused as `malformed_call` (260 D6) and nothing runs (D12). Which calls need `here`, and so make the `cf` call:

| Call | `here` |
|---|---|
| `send`, `inbox`, `reply`, `cancel`, `changes`, `report_release`, `status` | Always |
| `list` with no subject | Always |
| `list programs`, `list members`, `list dependencies`, `list standing` | Never. They read the store and the calling machine only |
| `add` | When an entry names no member: bare `add`, `--attach-to`, `--new-member`, and a bulk file with such an entry. Not with `--project`, and not for a bulk file whose entries all name members |
| `rm` | Only when nothing says which program or checkout is meant: no member, no `--pair`, no `--checkout`, and no `--concept` together with `--program`. This is the case that reads the working directory today |

A call that does not need `here` sends none, and one that arrives with it anyway has it ignored.

A `cf` failure or timeout raises `ContextForgeError` in the client part, before any hub call, as today. Not being a project is a gathered value, not an error.

For the checkout, a path that is not a repo and exit 2 from git both give a null `origin`. "Not a repo" is decided before git runs and not from git's exit code or message: the path has no `.git` entry in it or in any directory above it, the same check `pause_eligibility` already makes for a checkout. Then no git call is made. Any other git result (a non-zero exit other than 2, git missing, or a directory that cannot be entered), or no answer within `ORIGIN_READ_TIMEOUT_SECONDS`, raises `ContextForgeError` naming the command, and nothing is sent. `remote` joins `git_read`'s allowed subcommands.

The client part gathers only what the request needs. `rm forge` and `add --project forge --rules ...` name their member, so they run no `cf` and work from any directory.

**What the hub trusts.** The machine comes from the token. The project id is what the client says, which the architecture accepts: any machine acts as the PM.

**The door a call came through.** `refuse_door_fields` moves into the client part of `add`. So the rule that MCP never sets a wake command is kept by the client, as the architecture says, and the hub part takes no `Door`.

### D6 — Who is calling, and who is named
Status: decided

`operations.caller` replaces `members.resolve_member`, `member_reference.anchor` and `project_lookup`. Neither function calls `cf`.

- **`find_caller(transaction, machine, here)`** gives the active member whose checkout is (`machine`, `here.project_id`), or `NotInProgram` (a project with no checkout on record), or `NotAProject`. These are today's three outcomes, so `not_a_member` and its two details are unchanged.
- **`find_member(transaction, reference)`** gives the active member whose name is `reference`, or else the one whose id is. Ids stay accepted because results show them and existing documents use them. No name equals another member's id (D1), so a reference never means two members.

Every reference in a request is read with `find_member`: `send`'s `to`, the explicit `member` of the four message operations, `standing`'s member, `depends_on` providers, pair ends, the concept's member, and the members `rm` names. `rm` also finds a removed member, by its id only. So `amoeba rm <id>` twice is `unchanged`, as today. By name the second call is `not_a_member`, because a removed member's name is free and may be another member's by then.

260's two readers (a names reader for `decisions`, a resolver for `standing`) are deleted. Both operations read the store.

`program_sources` read the concept from another member's checkout by asking `cf` for it. It now takes that member's checkout on the acting machine from `checkouts`: its path and its Context Forge id. With several there, it takes the one added first, the rule D9 states. With none there, it returns the existing `missing` problem, saying the concept member has no checkout on this machine. It runs only in the pause path, on the machine with the files. The hub never runs it, and 262 keeps it client-run.

**The member id is never given to `cf`.** Three calls in the pause path pass an id to `cf -p` today, and that id is the member id: `resolve_slice` and `_read_committed` in `pause_context` (the plan lists and `git.integration_branch` of the asking repo), and `read_target` in `program_sources` (the concept member's `git.integration_branch`). A member made by this slice has an id `cf` does not know, and `cf -p` fails for one (see the facts above). So each of the three now takes a checkout's Context Forge id: for the asking repo, the project id the caller lookup was given (`here.project_id`), and for the concept member, the `cf_project_id` of the checkout row read above. `pause_context.gather` takes that id as an argument beside the member. A test pins that no `cf` command line in `pause_context` or `program_sources` is built from `Member.project_id`.

`pause_eligibility` registers a project in no program by calling `add` with an empty document. It now runs `add`'s client part first. A refusal (a taken name, D7) is the existing skip that carries the rejection's text.

### D7 — `add`
Status: decided

`add` finds or creates one member, attaches the caller's checkout, and applies settings. The hub part runs in one transaction.

**Which member.** With `--project <name>` (the request field `project`, as today), it is that existing member, found with `find_member`, so the flag now takes a member's name or id; one that does not exist is `not_a_member`. No checkout is read or written.

With no member named, the gathered checkout decides, in this order:

1. **This checkout is on record** (this machine and project id): its member. The stored path is kept, whatever path arrived. A registered worktree has the same project id and its own directory as its path (see the facts above), so updating the path here would move the checkout, and with it the directory a wake runs in, to whichever worktree ran `add` last. When the repo itself was moved on disk, the row is replaced: `amoeba rm --checkout <old path>`, then `amoeba add` in the new place, which attaches by `origin` (step 2), or with `--attach-to <name>` when the member has no `origin`. A wake command the old row had is set again there. `list members` shows the stored path, so a stale one is visible.
   - If the member has no `origin` and this checkout has one that no other active member has, it is recorded.
   - If this checkout has no `origin`, the member's is kept. `add` never clears one.
   - If the member's `origin` differs from this checkout's (the repo moved to another host), it is replaced, and the change record shows both. If another active member has the new one, the call is refused as `origin_taken`. The detail names both members and says they are now the same repo, and gives the way on: `amoeba rm` one of the two, then `amoeba add` here again.
   - A checkout that still has the old remote puts the old `origin` back at its next `add`, by the same rule. So after a move the remote is changed in every checkout (`git remote set-url origin ...`). Each change record shows both values, so a flip is visible.
2. **An active member has this `origin`:** the checkout is added to it, whatever its name. The result names the member.
3. **A removed member has this `origin`:** the most recently removed one is registered again, in the program it was in unless `--program` says otherwise, and the checkout is added. If an active member now has its name, or its name is now another member's id, the call is refused as `name_taken` unless `--name` is given.
4. **The name is free** (`--name`, else the Context Forge name): a new member with this checkout. Its program is `--program`, else a new program named for the member, as today.
5. **The name is taken** by an active member:
   - This checkout has an `origin`: refused as `name_taken`. The detail shows both reduced remotes (`none recorded` when the member has none) and the ways on. For a different repo: `--name`. For the same repo, when the member has no `origin` recorded and has a checkout: give that checkout the same `origin` remote, run `amoeba add` there so the `origin` is recorded, then `amoeba add` here, which attaches. `add` there records nothing while that checkout has no remote. When the member has no checkout: `amoeba add --attach-to <name>` here.
   - This checkout has no `origin`: refused as `no_origin`. The detail says a repo with no `origin` remote can have one checkout, because nothing shows it is the same repo, and gives the two ways on: add a remote, or `--name` for a separate member.

   The name is the only sign that a second checkout with no `origin` is the same repo. So the refusal holds while the member keeps the name the second checkout arrives under. If that member was renamed, step 4 creates a second member.

A directory that is not a project is `not_a_project`, as today.

Two flags set the five steps aside. Each is for one state the steps cannot leave, and each is refused as `malformed` when this checkout is already on record, with `amoeba rm --checkout` named as the first step.

- **`--attach-to <name>`** attaches this checkout to that member. It is accepted only when the member has no checkout on any machine; otherwise it is refused as `member_has_checkouts`, because the `origin` decides. This is the way to give a checkout back to a member that has none and no `origin` to match on, such as one named by its id because its Context Forge project is gone. The checkout's `origin` is then handled by step 1's three rules, as for any checkout of the member: recorded when the member has none, kept when the checkout has none, and replaced, with both values in the change record, when the two differ. If another active member has the checkout's `origin`, the call is refused as `origin_taken`.
- **`--new-member`** creates a new member for this checkout and skips steps 2 and 3. It is the undo for a checkout that attached to the wrong member by `origin`: `amoeba rm --checkout <path>`, then `amoeba add --new-member --name <name>`. When another active member has this `origin`, the new member is created with none recorded, so it has this one checkout, like any repo with no `origin`. The name must be free.

**`--name <name>`** sets or changes the member's name, for either way of choosing the member. A name another active member has, or that is another member's id, is `name_taken`.

**Settings** (rules, authorize lists, `--depends-on`, `--concept`, `--program`) are applied by the existing engine and its checks, unchanged apart from where references are looked up.

**The wake command** (`--wake-command`, `--no-wake-command`) is set on the caller's checkout, so it is accepted only when no member is named. With `--project` it is `malformed`, and the detail says a wake command is set from its own checkout. The store function that writes it takes the acting machine and raises when the checkout is on another one. Since the checkout is found by the token's machine, no request can reach another machine's checkout; the check is there so a later caller cannot either.

**`--file`.** The bulk document keeps its shape, with `name` added to each entry. At most one entry may name no member; it is the working directory's and follows the five steps. Every other entry names an existing member. Creating a member for another repo from a bulk document is gone, because it needed `cf` to resolve that repo: the entry is `not_a_member`, and the detail says to run `amoeba add` in that repo.

Five new problem codes in `SetUpProblemCode`: `name_taken`, `origin_taken`, `no_origin` and `member_has_checkouts` here, and `not_a_checkout` from `rm` (D8).

### D8 — `rm`
Status: decided

- **`amoeba rm <name>...`** removes members found with `find_member`. It gathers nothing, so it works from any machine and directory, and for a member with no checkout left.
- **`amoeba rm`** with nothing named removes the caller's member, as today.
- **`amoeba rm --checkout <path>`** removes one checkout of the calling machine, found by its stored path, and leaves the member. It is how a deleted clone is cleared without removing the member or the machine. The path is compared as text with the stored one, after trailing slashes are dropped from both. It is not resolved against the disk, because the directory may be gone, so it is given as `list members` shows it; a path that is not absolute is `malformed`. If two checkouts on this machine hold that path (a Context Forge project made again in the same directory), both are removed. A path with no checkout on this machine is `not_a_checkout`, and the detail lists this machine's stored paths. It cannot be combined with members, `--pair` or `--concept`.
- `--pair`, `--concept` and `--program` are unchanged, with references found by name.

Removing a member does what it does today in the same transaction: the open-question refusal, the soft removal, its pairs deleted, its open requests cancelled as `member_removed`, its member-reach standing answers withdrawn. It now also deletes the member's checkouts on every machine, and their wake commands with them.

Removing the last checkout with `--checkout` leaves a member with none. `list members` shows it that way.

### D9 — The wake command on the checkout
Status: decided

`MemberSettings.wake_command` is removed. `claim_wake` and `can_wake` read the command from a checkout of the recipient on the acting machine that has a command. Every checkout has a path (D2). With several, the one added first is used. The wake row's `directory` and `command` are copied from that checkout, so `wake-run` is unchanged. `Recipient` loses `project_path` and `wake_command`; the claim reads them inside its own transaction.

**With no client file,** waking works as today: `send` claims and starts the wake in the same call. A member whose Context Forge project has no path has no checkout (D4), so no wake is claimed for it, where today the wake would be claimed and end as `start_failed`.

**Through the door,** this slice does not start wakes; that is 262. The hub part of `send` checks, before it writes, whether a wake is due: the recipient has a checkout with a command on any machine, and today's other `can_wake` conditions hold (no live session, no live wake, under the daily limit). The claim looks at the acting machine's checkouts and this check at every machine's, so `can_wake` takes which of the two is meant, and the other three conditions stay written once. If a wake is due, the hub part raises `CallRefused` with `not_served` (D12). The message says the door does not start wakes yet and names the member and every machine that has a checkout of it with a command, and nothing is written. The hub part knows it may not start a wake from `run_served`'s `edges`, which say so on the hub and not with no client file. A `send` to a member with no wake command, or with a live session, is served.

- Rejected: writing the request and skipping the wake. The request would wait for a wake that no slice-261 code can start, with nothing saying so.

### D10 — Registration cut down
Status: decided

Deleted:

- `operations/member_reference.py`, `operations/project_lookup.py` and `operations/members.py` (replaced by `caller`). `ContextForgeError` moves from `members` to `operations/errors.py`, beside the `OPERATION_ERRORS` tuple that holds it (260 D8). The hub imports that module, so it must not pull in the client part.
- The `cf` lookups in `set_up_resolve` and `set_up_remove_resolve`. Their `_Lookups` class and `Reference.known_to_cf` go, with the sentence `set_up_remove` adds to `not_a_member` from it; each reference is one store read inside the engine's transaction.
- `rm`'s anchors and its `cf` call per named member.
- The `reference` parameter of `project_of`. Only the directory form is left.
- `project_details` in `list_registry`.
- `Deps.project_names`, and the `cf list projects` call the CLI made to print names after `add` and `rm`.
- `MESSAGE_LOOKUPS` in `wiring_messages` becomes one `cf` call for each of the four operations. `tests/test_message_timing.py` and the tool descriptions that state the bound are updated.

Kept: the engine (`set_up`, its checks, its removal, its result), the bulk document, programs, pairs and the concept. They are what "set a member's settings" and "remove" are made of.

After the slice, `cf` is run in four places: `here` (the caller's directory), `naming` (once), `run_gather` (each run's directory, D11), and the pause path's reads of the plan and the target branch. This slice changes one thing in those: the id they pass to `cf -p` (D6).

### D11 — `list` and `status`
Status: decided

`status`, and `list` with no subject, read the machine's Squadron runs at five points today: the listing, each run directory's project, a paused run's file, the calls log, and the close sweep's check that a run missing from the listing still has a run file. The fifth stays in the sweep, which runs only with no client file in this slice (below). One client-part function, `run_gather.gather_runs`, makes the other four reads and returns a plain `runs` document. The hub part of `status` takes that document and reads no disk. With no client file the same function runs first and its document is passed in process.

The `runs` document holds:

- every run that is not completed, as the listing gave it. A run in an answering scratch directory is left out, as today;
- for each of those with a directory: missing, or the directory's Context Forge project id, or not a project, or the lookup's failure text;
- for each paused run: its run file's facts, or the read problem; and its newest calls-log line, with any read problems;
- for completed runs, the id and status only. The question close sweep reads them to close a question whose run has ended. It runs with no client file in this slice and through the door in 262;
- or, in place of all of it, the listing's problem text, which the hub part raises as today's `SquadronError`.

**Size.** The document is built in that order: paused runs, then other runs that are not completed, then completed ones. A run is added only while the encoded document stays under `RUNS_DOCUMENT_MAX_BYTES` (768 KiB, a constant in `runs_document`, below 260's 1 MiB body limit). Runs that do not fit are left out, and the document carries how many of each kind. The hub part puts that count in `file_problems`. A waiting question on a left-out run reads as not listed. The close sweep does not close it: for a run the document does not hold, the sweep keeps today's check (`run_file_exists`) and leaves the question open while the run file is there. So a cut document never closes a live question.

**Time.** The listing is one `sq` call with the existing `RUN_POLL_TIMEOUT_SECONDS` (30). The directory lookups are one `cf get` per distinct directory, and share `RUNS_GATHER_SECONDS` (60, a constant in `run_gather`). Once that is spent, each directory not yet looked up is recorded as a failed lookup whose text says the gather time ran out, so a paused run there shows as unplaced, as a failed lookup does today.

**Client times.** The run file's paused time and the time on a calls-log line are the calling machine's. The hub part shows them, and matches a paused time against a question's by equality, as an identifier, as `status` does today. It never compares either with the hub's clock. The ages `status` works out use store times and the hub's clock.

The hub part places each run under the member whose checkout is (calling machine, that project id), in place of today's match on the member id.

Three steps of `status` stay on the caller's machine and are edges the hub does not pass:

| Step | With no client file | Through the door |
|---|---|---|
| The question close sweep | Runs, as today | Not run. The plan puts the sweeps in 262, with the machine on question rows that tells whose listing may close a question |
| Pruning local scratch and logs | Runs, as today | Not run (262) |
| Starting `handle-pause` for held questions (`start_after`) | Runs, as today | Not run (262's work flag) |

The message expiry sweep is store work on the hub's clock, and runs in both.

Until 262 serves `handle_pause`, a hub's questions come only from test seeding, so nothing is left unswept in real use.

`list members` shows, for each member: name, id, program, `origin`, settings, and its checkouts, each with its machine's name, path, Context Forge id and wake command. A member with no checkout, and one named by its id, are marked. `list programs`, `list dependencies` and `list standing` take names from the store and make no `cf` call.

### D12 — What the door serves
Status: decided

Added to `SERVED_OPERATIONS`: `add`, `rm`, `list`, `status`, `inbox`, `reply`, `cancel`, `changes`, `report_release`, `send`. Still not served: `answer`, `handle_pause`, `wake-run`, and starting `amoeba-mcp`.

Added to `WRITING_CALLS`: `add`, `rm`, `send`, `reply`, `cancel`, `report_release`. `inbox` and `changes` are reads. `list` and `status` write only the message expiry, which is safe to run twice, so they keep no result.

`UNKNOWN_ADVICE` for five of the six, now that the reads are served, is the architecture's: read the state before sending again. `report_release` is the exception. No served read shows the caller its own stored report, and a repeat is safe, so its advice is to run it again.

| Operation | Advice |
|---|---|
| `send`, `reply`, `cancel` | Run `amoeba inbox` or `amoeba list` and look for the request before sending again |
| `add`, `rm` | Run `amoeba list members` |
| `report_release` | Run it again. A report that was applied answers `unchanged` and a withdrawal that was applied is rejected because nothing is stored; neither writes. A correction that was applied is applied again with the same text |

Each hub part runs inside 260's call scope, so its transactions and its kept result commit together.

**A refusal a hub part makes.** 260's handler turns an exception from an operation into `hub_error` or `hub_fault` only (260 D8). Three refusals in this slice are found by the hub part itself, after the call scope has begun: a missing or unreadable `here` or `runs` (D5) and an `origin` that is not in reduced form (D3), both `malformed_call`, and a `send` that would start a wake (D9), `not_served`. For these the hub part raises `CallRefused`, a new exception in `operations/errors.py` that carries a code and a message. The code is one of two constants in that module, `malformed_call` and `not_served`. They are plain strings, so `operations` imports nothing from `wire` for them, and a test asserts each is a `RefusalCode` value, the way 260 pins the served names. `CallRefused` is not in `OPERATION_ERRORS`. `handle_call`'s handler gets one more branch, before the other two: it rolls the operation's savepoint back, commits the touch, keeps no result, and refuses with that code and message, with the usual one line in the hub log. The client sees `HubRefusedError`, as for any refusal. With no client file none of the three can happen: the gathered values are passed in process, and `send` starts its wake. If `CallRefused` is raised there, it is a bug and is not caught.

The hub part of each operation reads the hub's `config.yaml` when the operation needs it today. With none, the call is refused as `hub_error` naming the file (260 D6).

### D13 — What results show
Status: decided

Names in every result come from the store, in the same transaction as the rest of the result.

- No result field is renamed or removed. `MemberState` gains `name`. `MemberRow` gains `origin` and `checkouts`. Its `path` is that of the member's checkout on the calling machine, the one added first when there are several, and null when it has none there. Its `wake_command` is the one a wake claimed on the calling machine would run (D9), null when no checkout there has one. `in_context_forge` says whether the member has a checkout there. `checkouts` lists every one.
- `SetUpResult.working_directory` is null when the call gathered nothing: `rm` and `add` that name their member run no `cf` (D5), so there is no working directory to report. Today it is null only for a malformed request. The field and its three shapes are unchanged.
- `SetUpResult` change records name members by name, so the CLI needs no lookup to print them.
- `MemberName`, `MemberRef` and the other `id` and `name` pairs keep their shape. `name` is never null now.
- `WorkingDirectoryNotInProgram.not_in_program` still holds the caller's Context Forge project id.

### D14 — `rm-machine`
Status: decided

`amoeba hub rm-machine` now also deletes the machine's checkouts, in its one transaction. Members stay; one left with no checkout is shown that way. 262 adds the questions, answers and wakes.

### D15 — Tests and the fixture
Status: decided

- **Unit.** Hub parts are plain functions on a throwaway store, with gathered facts built by hand. `reduce_origin`, the five steps of `add`, both lookups, and naming have a test per case in this design.
- **Naming** runs against a schema-11 store built the way `tests/store/test_migration_010.py` builds its version-nine store: migrated to 11, with rows inserted by plain SQL. The seed helpers in `tests/store/seed.py` insert through the current statements, which after 012 cannot make an unnamed member. The test uses a `cf` stub that lists some projects, leaves one out, gives one no path, and gives two the same name, and with real git repos from `tests/git_repo.py`. `name_by_id` runs against a schema-11 store opened with `open_hub_store`.
- **The two-machine fixture** (260's `tests/hub_fixture.py`) gains what members need: each client home has its own Context Forge stub, so one repo has a different project id on each machine, and its own clone with `origin` set. One clone uses the SSH form and the other the HTTPS form.
- **The chain.** `tests/hub/test_chain.py` runs 240's three-repo chain with CLI calls and no model, in the normal tier: the three repos are split across the two machines, and each step is followed by `inbox` from the other side. No member in it has a wake command, so every `send`, the child request with its `parent` link included, is served (D9).
- **Live.** The CLI part of `tests/live/messaging/test_messaging_live.py` (walkthrough steps 3 to 8, real `cf` and `git`) gains a variant with the repos on two fixture machines, each with its own Context Forge data directory. The variant is CLI only: `amoeba-mcp` does not start on a joined machine until 263.
- **Load.** 260's door load test adds `send` and `inbox` callers and keeps its two bounds (260 D18): every call finishes within 2 seconds with 16 clients calling at once, and the median of 100 calls on an idle hub is under 200 ms. The existing `tests/load/` tests run on the local store with their assertions unchanged, apart from the lock test below: their calls follow the new signatures, `test_wake_claim_load.py` seeds its wake command on a checkout (D9), and its send bound falls with the one lookup. `test_no_cf_under_write_lock.py` drives the placement, since the `cf` call moved there, and naming has the same check.
- **Latency.** The architecture counts a CLI call as one `cf` call plus one round trip. That holds for seven of the ten operations: one `cf get`, bounded by the existing `CF_GET_TIMEOUT_SECONDS` (30), and one door call, bounded by 260's `CALL_BOUND_SECONDS` (43). `add` with no member named adds one `git` call, bounded by `ORIGIN_READ_TIMEOUT_SECONDS` (10). `status`, and `list` with no subject, first gather the runs, bounded by 30 seconds for the listing and `RUNS_GATHER_SECONDS` (60) for the directory lookups, plus the one lookup in flight when that runs out (D11). That bound is reached only when `cf` or `sq` hangs. Naming adds at most about 70 seconds to the first call after the upgrade (D4).
- **No `cf` under a lock.** `tests/load/test_no_cf_under_write_lock.py` already asserts it; the naming step's gather is before its write.

### D16 — Documents and the live store
Status: decided

- `docs/store-contract.md`: `members.project_id` as an opaque key, `name`, `origin`, `checkouts`, and the retired `members.wake_command`.
- `docs/cli-contract.md`: `add --name`, `--project` as a member's name or id, `add --attach-to` and `--new-member`, `rm <name>` and `--checkout`, the five new problem codes (D7), the added result fields, `working_directory` null when nothing was gathered (D13), and `list members`.
- `docs/mcp-server.md`: the `add` and `rm` tool fields.
- `docs/program-rules.md` and `docs/rules.md` where they say a member is named by its Context Forge name or id.

The live store is migrated and its members named by `uv run python scripts/update_live.py update` when the release runs, as every migration is (260 D19). Nothing in this slice runs it on the live install. The script already does the following, and this slice adds no second backup:

- **Backup.** Before anything changes it copies the store and config to `<state home>/backups/<stamp>/`, with the commit that was installed. A successful update deletes every older set, so one is kept.
- **Update.** It installs the checkout and runs `amoeba list`, which migrates the store and names the members, then reads the store back.
- **A failed read-back** restores the store, the config and the previously installed commit by itself, and exits 1 saying what failed.
- **A failed install** stops the script with that error. Nothing was migrated and the backup stays. Run `update` again.
- **A failed `amoeba list`** (a `cf` failure during naming exits 3) stops the script the same way today, and that is changed here (below).
- **Restore.** `uv run python scripts/update_live.py restore` puts the newest backup back and reinstalls the commit recorded with it. A restore that fails partway leaves the backup as it was, and the same command is run again.
- **Sessions.** It prints the open `amoeba-mcp` sessions to restart, since an old server refuses the newer schema.

This slice adds two checks to the read-back, after the `amoeba list` the script already runs: no member has a null name, and every active member that `cf` lists with a path has a checkout on the `local` machine. It also makes a failed `amoeba list` restore by itself, exactly as a failed read-back does: the store, the config and the previously installed commit are put back and the script exits 1 saying what failed. Without this, the failure leaves the new code installed, the store at schema 12 and `backups/installed-commit` still naming the old commit, because `update` writes that record last. Naming the members by hand from there would leave the record wrong, so the next release's backup would pair a schema-12 store with a commit whose code refuses it. Running `update` again from there would back up the already migrated store and then delete the one backup taken before the migration. With the restore, neither state exists: the install is as it was before the update, and the way on is `update` again once `cf` works. A restore cannot run when the process itself is killed after the migration, which leaves the same state (issue #45). So `update` also checks for it when it starts: if the newest backup records the commit `update` is about to record as previous, and that backup's store is at a lower schema version than the live store, an earlier `update` migrated and never finished. `update` then keeps that backup as its restore point and takes no new one, so the rerun cannot delete the only backup the old code can read. A test runs `update` and `restore` against a copy of a schema-11 store in a throwaway home. The slice notes record the restore command.

### Departures from the parent documents

| Parent says | This design | Why |
|---|---|---|
| Plan: the migration adds the wake command to checkouts, "which moves here" | The naming step moves it; the old column stays and is null | A checkout needs a machine, and the opener makes the local machine, not a migration (260 D12) |
| Plan: the first call "asks `cf` once for every member" | One `cf list projects` call, and one `git` call per member | One call lists every project; `origin` is git's to give |
| Architecture: the caller sends its project id | `add` also sends the project's name, path and reduced `origin` | The hub needs them to create the member and the checkout |
| Architecture: the client sends the address and the hub reduces it. Plan: `add` sends it reduced | The client reduces, and the hub checks that what arrived is a reduced form and refuses anything else (D3) | The raw address can hold a password, so it stays on the client. The hub does not trust the client's form, and reducing a reduced form would change or empty it |
| Architecture: the hub reduces `origin` by scheme, user, `.git` and slash | Also treats an address with no host as no `origin` | A local path never matches across machines |
| Architecture: the hub keeps each writing call's result | `list` and `status` keep none | Their only write is the message expiry, which gives the same store when run twice |
| Architecture: `add` has four outcomes | Two more come first or beside them: the checkout already on record, and a removed member with the `origin` | Running `add` again in a registered repo, and `rm` then `add`, both work today |
| Today: `rm` then `add` registers the same member again | Only for a repo with an `origin`. With none, `add` creates a new member | Removal deletes the member's checkouts, and without an `origin` nothing else says the checkout is the same repo |
| Today: `rm` of a removed member is `unchanged` | By id. By name it is `not_a_member` | A removed member's name is free, so it cannot say which removed member is meant |
| Architecture: naming records each member's `origin` | A `git` call that fails or times out leaves that member with no `origin`, and a warning is logged | A hung mount must not stop every command. A missing `origin` only refuses, and the next `add` in that checkout records it |
| Architecture: naming records each member's path as its checkout | A member whose project has no path gets no checkout, and its wake command is dropped and logged | No call can come from a project with no path, and nothing can run in it |
| Architecture: the first `amoeba` call names the members | On a hub store, which has no `cf`, opening it names any unnamed member by its id | Only a 260 fixture store or its backup can hold one, and it must still be readable |
| Architecture: naming has two fixed cases (a project `cf` no longer knows, a name clash) | A third: a Context Forge name the pattern does not allow is named by its id. The same name is refused as `malformed` when `add` creates a member | Naming runs with nobody to refuse, and it must name every member. `add` has a caller who can give `--name` |
| Architecture: a second checkout of a repo with no `origin` is refused | Refused when it arrives under the member's name. After that member is renamed, a second member is created | With no `origin`, the name is all the store has to tell that two checkouts are one repo |
| Architecture: a name is unique in the store | Unique among active members, compared without case | A removed member must not hold a name forever |
| Architecture: registration is cut to adding a checkout, settings and removal | Also adds `rm --checkout`, `add --attach-to` and `add --new-member` | A deleted clone, a member with no checkout and no `origin`, and a wrong attach each need an exit |
| Architecture: daily use and results do not change | `--project` and a bulk entry's `project` name an existing member, so neither can create a member for another repo. No flag or result field is renamed or removed | Creating another repo's member needed `cf` to resolve it |
| Architecture: results stay as they are | `working_directory` is null for an `add` or `rm` that names its member (D13) | Those calls run no `cf`, so they work from any directory, and have no working directory to report |
| Today: a member's path is read from `cf` at each use, so a moved repo is followed | A checkout's path is stored when the row is made and not changed by `add`. A moved repo is `rm --checkout`, then `add` (D7) | The architecture stores the path. Updating it on `add` would move it between the worktrees of one project |
| Today: the member id is the id `cf -p` takes in the pause path | The pause path passes the checkout's Context Forge id (D6) | A member made from now on has an id `cf` does not know |
| Plan: the release's live update backs up, migrates and has a restore path | The script also restores by itself when its `amoeba list` fails (D16) | Naming can fail on `cf` after the migration has run, and the script's record of the installed commit would then be wrong |
| Plan: `send` is served "for a recipient with no wake to start" | A `send` that would start a wake is refused as `not_served` | Stated so the refusal is not read as a bug; waking through the door is 262 |
| Plan: `list` and `status` are served | Through the door they run no question sweep, no file prune and no held-question start | The plan puts all three in 262 |
| Plan, 244: a wake with no directory is claimed and ends `start_failed` | A member whose project has no path has no checkout, so no wake is claimed | Every checkout has a path, so the claim never starts what cannot run |
| Architecture, Anticipated Slices: wake commands on checkouts are in the third slice | The command moves to the checkout here; 262 starts wakes through the door | The plan's 261 entry puts the column and the move here |
| Architecture: an unknown outcome says to read the state before sending again | `report_release` says to run it again | No served read shows the caller its own report, and a repeat is safe (D12) |

## Implementation Details

### API Contracts

```
amoeba add [--name NAME] [--project NAME | --attach-to NAME | --new-member] [--program ID] [rules, allow, deny flags]
           [--depends-on PROVIDER[:MODE]] [--concept MEMBER:PATH]
           [--wake-command COMMAND | --no-wake-command] [--file PATH] [-j]
amoeba rm [NAME...] [--pair PROVIDER:CONSUMER] [--concept] [--program ID] [-j]
amoeba rm --checkout PATH [-j]
```

Every `NAME`, `MEMBER`, `PROVIDER` and `CONSUMER` is a member name or id.

Door body keys beside `document`:

- `here`: `{"project_id": ...}`, or `{"project_id": ..., "name": ..., "path": ..., "origin": ...}` for `add`, or `{"not_a_project": ...}`. D5's table says which calls send it; a call that needs it and lacks it is `malformed_call` (D5). `origin` is a reduced form or null, and any other value is `malformed_call` (D3).
- `runs`: the document in D11, required for `status` and `list` with no subject.

Neither changes the door version: both are added fields on added calls.

### Database / Storage Schema

Migration 012 as in D2. `EXPECTED_SCHEMA_VERSION` becomes 12. `tests/store/test_migration_012.py` covers: a schema-11 fixture's row counts unchanged; an insert with a null name refused; two active members with one name refused in either case; a removed member's name reusable; `(machine_id, cf_project_id)` unique.

### Migration Plan

- **Lookups.** Each caller of `resolve_member`, `anchor`, `resolve_caller`, `resolve_actor`, `resolve_recipient` and `resolve_release_member` moves to `caller`. The three old modules are deleted in the task that moves the last caller.
- **Existing data.** No row is rewritten by the migration. The naming step fills `name`, `origin` and `checkouts` once per store.
- **Behavior kept.** With no client file, the existing suite passes with two kinds of edit: a test that referred to a Context Forge project that is not a member now refers to a member, and a test that addressed a member by its Context Forge name seeds that name on the member.

## Integration Points

### Provides to Other Slices

- **Checkouts.** 262 reads them to decide which machine a wake or a resume belongs to, and extends `claim_wake` across machines.
- **`find_caller`.** 263 uses it for a session's member.
- **`find_member` and names in the store.** Every later operation finds members this way.
- **The client part and the `here` key.** 262's `answer` and `handle_pause` send the caller the same way.
- **The `runs` document.** 262's sweep reads it, and 263 stores what it reports for other machines.
- **Named members.** 264's adoption refuses a store with an unnamed member. After this slice a local store has none once any command has run, and a hub store has none once it is opened (D4).

### Consumes from Other Slices

From 260: the door, the call scope, kept results, machines and the acting machine, the fixture, and `rm-machine`'s transaction. A call that fails at the door fails with 260's errors and refusal codes; this slice adds none. It adds one way to reach two of the codes: `CallRefused`, raised by a hub part (D12).

## Success Criteria

### Functional Requirements

- 240's three-repo chain runs between two fixture machines through the hub, each step read by `inbox` polling from the other machine.
- `add` on a second machine attaches to the member with the same `origin` when one clone uses the SSH form and the other the HTTPS form, and when the member was renamed with `--name` in between. `list members` from either machine shows one member with two checkouts.
- `add` of a different repo under a taken name is refused as `name_taken` with both reduced remotes. `add --name` then creates it.
- A second checkout of a repo with no `origin`, arriving under the member's name, is refused as `no_origin`, and the detail says why.
- `add` run again in a registered checkout is `unchanged`. After the repo's `origin` is changed, it updates the member's `origin` and says so.
- `add` run in a second registered worktree of a registered project is `unchanged`, and the checkout's stored path is still the first one. After `rm --checkout <old path>`, `add` in the repo's new directory attaches to the same member with the new path.
- A pause in a member that `add` created in this slice, whose id is no Context Forge id, gathers its sources: with a `cf` stub that fails for any `-p` value but the checkout's Context Forge id, the plan, the target branch and another member's concept file are all read. The same holds when the pause itself registered the repo.
- Through the door, `add` from a clone with an SSH `origin` and from one with an HTTPS `origin` that has a port both record the reduced form the client sent, unchanged. A call whose `origin` is not a reduced form is refused as `malformed_call` and writes nothing.
- `add --project <name> --wake-command ...` is refused from any machine. The store function refuses a checkout on another machine.
- A raw `origin` holding a password appears in no call body, result, log line or store row. The same holds for a malformed address that holds one: `add` treats it as no `origin`.
- `add --name <another member's id>` is refused as `name_taken`. Naming gives a member whose Context Forge name is another member's id its own id.
- A checkout attached to the wrong member is moved with `rm --checkout` and `add --new-member --name`: a new member with this one checkout, and the first member unchanged.
- `add --attach-to <name>` attaches a checkout to a member that has no checkout and no `origin`, and is refused as `member_has_checkouts` for a member that has one.
- `add` in a registered checkout whose remote was removed keeps the member's `origin`.
- A door call that needs `here` or `runs` and lacks it is refused as `malformed_call`, the touch is committed and nothing else is written. `list members`, `rm <name>`, `rm --checkout` and `add --project` send no `here` and make no `cf` call, and their result's `working_directory` is null where it has one. A `runs` document that would pass `RUNS_DOCUMENT_MAX_BYTES` is cut, paused runs kept first, and `file_problems` says how many runs were left out. With no client file, an open question whose run was cut from the document stays open while its run file exists.
- With a `cf` stub that hangs, the runs gather stops looking directories up after `RUNS_GATHER_SECONDS` and the remaining paused runs show as unplaced. With a `git` stub that hangs, naming finishes within `NAMING_GIT_SECONDS` plus one call's timeout.
- The restore command for the live store is in the slice notes. The live store itself is migrated and named when the release runs `update_live.py` (D16).
- Naming: on a schema-11 store, the first call names every member. A member `cf` no longer lists is named by its id and has no checkout. Of two with one Context Forge name, the first registered has the name and the other its id. Each named member that `cf` lists with a path has a checkout with its path and its old wake command, and `members.wake_command` is null everywhere. A member whose project has no path is named and has no checkout, and the log line for a dropped wake command holds the member's id and the command. A `cf` failure exits 3 and writes nothing, and the next call names them.
- No operation reads a member with a null name: with naming disabled by a test hook, the first member read fails loudly.
- A hub started on a schema-11 store that holds members names each by its id. Through the door, `add --project <id> --name` then renames one, `add --attach-to <id>` gives one a checkout, and `rm <id>` removes one.
- `rm <id>` twice is `unchanged` the second time. `rm <name>` twice is `not_a_member` the second time.
- `name_taken` for the same repo, where the member's checkout has no remote: after a remote is added there and `add` is run there, `add` in the second checkout attaches.
- `rm <name>` from a directory that is not a project, on a machine with no checkout of it, removes a member that has no checkout left, and cancels its open requests as `member_removed`.
- `rm --checkout <path>` removes that checkout and leaves the member, with or without a trailing slash and with the directory deleted. An unknown path is `not_a_checkout` and the detail lists the machine's stored paths.
- With two checkouts of one member on one machine, the concept read and `list members`' `path` use the one added first, and a wake uses the first added that has a command.
- `add --name` with a name that is another member's id in a different case is refused as `name_taken`.
- Agents in two worktrees of one clone, and in clones on two machines, read the same request from `inbox`. Both `reply` with accept; the first wins and the second is told so, as in 240.
- `send` through the door to a member with a wake command and no live session is refused as `not_served` and writes nothing. To a member with none it is `sent`.
- `status` and `list` through the door show the calling machine's runs under the right members, from the `runs` document, with the hub's `PATH` holding no `cf`, `sq` or `git`.
- `hub rm-machine` removes the machine's checkouts. A member left with none is marked in `list members`.
- With no client file, every existing behavior passes on the local store, including waking, with recipients found in the store and no `cf` call for any member but the caller's directory.
- `scripts/update_live.py update` and `restore` pass against a copy of a schema-11 store, with the two added read-back checks. With a `cf` stub that fails, `update` restores the schema-11 store, the config and the previous commit by itself and exits 1, and `backups/installed-commit` is unchanged. `update` run again with `cf` working then succeeds, and a `restore` after it puts the schema-11 store back with the commit that reads it.

### Technical Requirements

- `ruff`, `pyright` strict and the full `pytest` run pass.
- The import rules in Component Structure are tested.
- `tests/test_message_timing.py` passes with one `cf` lookup per message operation.
- The door load test passes its two bounds with `send` and `inbox` callers (D15), with the measured figures in the slice notes.
- New source files stay near 300 lines.
- The documents in D16 are updated and `tests/test_contract_docs.py` passes.

### Integration Requirements

- 262 can find the machine of a recipient's wakeable checkout from `checkouts`.
- 263 can resolve a session's member with `find_caller`.
- The PM's install, with no client file, behaves as before, with its members named.

### Verification Walkthrough

Run on 20261123 against the built slice. The criteria above are tests on the two-machine fixture and the local store:

```bash
uv run pytest tests/hub tests/operations tests/store/test_migration_012.py tests/scripts
uv run pytest tests/load                     # the door load bounds (15.4)
uv run pytest tests/live/messaging           # real cf and git on two machines; needs the AMOEBA_LIVE_* variables
```

By hand, with a hub and two joined client homes `alpha` and `beta` (`tests/hub_fixture.py` builds both: `two_machine_hub(root)`, then `hub.clients["alpha"]` and `hub.clients["beta"]` run the real CLI; each client has its own `cf`, so one repo has a different Context Forge project id on each), a clone of `widget` in each (`git@github.com:org/shared-repo.git` on `alpha`, `https://github.com/org/shared-repo` on `beta`), a repo `tool` on `alpha`, and a different repo `other-widget` on `beta` that is also a Context Forge project named `widget`. Each command below is run in the directory named, as that machine. The output is what the fixture printed; ids and paths are abbreviated.

```bash
# alpha: the clone with the SSH origin
cd ~/alpha/widget && amoeba add
#   added
#     created program widget
#     added member widget
#       rules: default
#     added checkout ~/alpha/widget of widget
#     changed member widget origin github.com/org/shared-repo      (exit 0)

# beta: the clone with the HTTPS origin attaches to the same member
cd ~/beta/widget && amoeba add
#   added
#     added checkout ~/beta/widget of widget                       (exit 0)

amoeba list members                          # from either machine
#   widget · program widget
#     id: <32 hex>
#     origin: github.com/org/shared-repo
#     rules: default (CLAUDE.md, AGENTS.md)
#     checkouts:
#       alpha, Context Forge id cf-widget-alpha
#         ~/alpha/widget
#       beta, Context Forge id cf-widget-beta
#         ~/beta/widget

# a second repo on alpha sends to it, and beta reads it
cd ~/alpha/tool && amoeba add && amoeba send --id ask-1 --to widget --subject "add a flag" --body "please"
#   sent: ask-1                                                    (exit 0)
cd ~/beta/widget && amoeba inbox
#   Requests
#       ask-1 · from <id> · open · <1m
#         subject: add a flag
#         body: please
#   as_of_seq: 1 (pass it as --since next time)

# a different repo that is also called "widget"
cd ~/beta/other-widget && amoeba add
#   rejected: name_taken:                                          (exit 1)
#     member 'widget' has this name; its origin is github.com/org/shared-repo and this
#     checkout's is github.com/org/other-widget ... (the whole detail, with the ways on)
amoeba add --name widget-fork
#   added
#     created program widget-fork
#     added member widget-fork
#       rules: default
#     added checkout ~/beta/other-widget of widget-fork
#     changed member widget-fork origin github.com/org/other-widget (exit 0)

# remove from anywhere: no cf call, no working directory
cd /tmp && amoeba rm widget-fork
#   removed
#     removed member widget-fork                                   (exit 0)
amoeba rm --checkout ~/beta/widget           # on beta: the member stays, one checkout fewer
#   removed
#     removed checkout ~/beta/widget                               (exit 0)
```

Corrections the run found, fixed in this slice: a joined machine's `add` and `rm` text read the local `config.yaml` for the default rules, which is not the config that applies (the hub's is) and may not exist, so the command exited 3 after the hub had applied the change; the text now says `rules: default` alone there. And the text of `name_taken` and its kin cut the detail at the terminal width, losing the way on; those five refusals now wrap their whole detail. Both have tests (`test_add_and_rm_text_needs_no_config_on_a_joined_machine`, `test_a_refusal_that_holds_the_way_on_is_wrapped_in_full_never_cut`). `-j` was never affected.

On the local store, after upgrading: `amoeba list members` shows every member with a name, its checkout on `local`, and any member still named by its id.

## Risk Assessment

### Technical Risks

- **Naming runs on the PM's live store, once, with real `cf` and git.** A wrong name or a lost wake command is live data.
- **The `origin` match decides whether two repos become one member.** A false match merges two inboxes.
- **A repo with no `origin` can split into two members.** The name is the only sign that two such checkouts are one repo, so after a rename a second checkout becomes a second member with its own inbox. The architecture's rule cannot be kept in that case, which the departures table records.

### Mitigation Strategies

- Naming is tested against the real output shapes of `cf list projects` and `git remote get-url`. `update_live.py` backs up first, checks the result, and restores by itself on a failed check or a failed naming; D16 lists what a failed install leaves.
- `reduce_origin` gives nothing for any address it cannot read as a host and a path, and a missing `origin` only ever refuses; it never matches. A wrong attach is undone with `rm --checkout` and `add --new-member` (D7).
- `list members` shows each member's `origin`, so a member with none stands out. A split is undone with `amoeba rm` on the spare; adding an `origin` remote prevents it.

## Implementation Notes

### Development Approach

Suggested order. Each step leaves the suite passing on the local store.

1. Migration 012 and the store functions for names, `origin` and checkouts.
2. `reduce_origin`, the client part (`here`), and the naming step in `open_state_store`.
3. `caller`, and every operation moved onto it, with the pause path's `cf -p` calls given the checkout's Context Forge id (D6). Delete the three old lookup modules.
4. `add` and `rm`, the engine's references, and the CLI flags.
5. The wake command on the checkout.
6. Results and `list`, with names from the store.
7. `gather_runs` and the `runs` document.
8. The ten hub parts in `run_served`, `CallRefused` and its branch in `handle_call`, the fixture changes, and the chain test.
9. `rm-machine`, the documents, and `update_live.py`.

### Implementation Notes as built (20261123)

- **Load figures (15.4).** `tests/load/test_door_load.py` runs 16 threads (5 `decisions` readers, 5 writers, 3 `send` callers, 3 `inbox` callers): 260 calls in 8.1 s, slowest 0.158 s against the 2 s bound, median 7 ms. Idle, 100 calls each: `decisions` median 2.5 ms, `inbox` 2.5 ms, `send` 4.3 ms, against the 200 ms bound. `tests/test_ci_gates_load.py` pins that CI's `Tests` step runs the load tier.
- **Restore command and the rerun rule (16.1, closes #45).** `uv run python scripts/update_live.py restore` puts the newest backup (`<state home>/backups/<stamp>/`) back and reinstalls the version recorded with it. The script's older commit record does not exist in this tree (it installs a PyPI version since ce248104), so the design's `backups/installed-commit` became `backups/installed-version`, written last by a successful `update` or `restore`. `update` takes its `previous` from `--previous`, else that record, else `amoeba --version`. If the newest backup records `previous` and its store holds an older schema than the live one, an earlier `update` migrated and never finished: `update` keeps that backup as the restore point, takes none, and prints that it did. A kill before the migration leaves the store at the old schema, so a new backup is taken as before. Anything that fails after the install, a failed `amoeba list` included, restores and exits 1 naming the failure and the restored version. The null-name check reuses `sql.SELECT_UNNAMED_MEMBERS`; the other new statement is `SELECT_ACTIVE_MEMBERS_WITHOUT_CHECKOUT_ON`.
- **Modules beyond Component Structure.** Client-part split so the hub never imports it: `operations/here_document.py`, `operations/add_gather.py`, `operations/name_by_id.py` (5.2: D2's text puts `name_by_id` in `operations.naming`, which imports the client part, so it is its own module), `store/member_names.py`. Splits by concern to stay near 300 lines: `operations/add_member.py` with `add_names.py` and `add_origin.py`; `operations/set_up_plan.py`, `set_up_wake.py` and `set_up_state.py` out of `set_up.py` (269 lines, under its 344); `operations/served_types.py` and `served_runners.py` out of `served.py`; `operations/status_local.py` out of `status.py`; `operations/wake_door.py` (the hub's `send` refusal); `wiring_gather.py` (the client part's placement, replacing `wiring_registry.py` and `wiring_releases.py`, and `place_message`). Test infrastructure: `tests/hub_clients.py`, `tests/store/schema_11.py`.
- **The import rule is narrowed (13.7).** Only `here`, `naming` and `run_gather` import `project_of`, `project_details` or `project_names`; type-only imports (`CFProject`, `CFProjectNotFound`) are allowed because `working_directory` keeps its `CFProject` shape. The hub and `operations.served` reach none of the four client-part modules through any import (walked in `tests/test_import_boundaries.py`).
- **`handle_pause` (7.7).** `PauseTarget.cf_project_id` and the pause path's `cf -p` calls are changed here although the Excluded list leaves `handle_pause` to 262: the member id is no longer a Context Forge id, so the pause path needed the checkout's.
- **Unknown references are `not_a_member` (9.8)**, where today they are `not_a_project`: the engine finds references in the store, not in Context Forge.
- **Existing `tests/load` files (7.1, 7.3, 8.1).** `test_messages_load`, `test_wake_claim_load` and `test_report_release_load` follow the new signatures with bounds and assertions unchanged, apart from `test_wake_claim_load`'s send bound, which is computed from `worst_case_seconds` and fell from 105 s to 45 s with one `cf` lookup per operation; `test_no_cf_under_write_lock` drives the placement.
- **Test edits.** The tests changed under the "Behavior kept" rule are listed under their tasks (7.1 to 11.2) in `user/tasks/261-tasks.members-by-name.md`.
- **Design text changed under the small-conflict rule.** `operations` take a `clock` and `ServedEdges` gained `local` (the machine's own edges; `None` on the hub, which starts no wake and runs no sweep, prune or run start); `ListResult.from_document` and `result_from_document(name, document, request)` (a `list` result's type follows its subject); `SetUpResult` drops its computed `changes` when rebuilt from a document; `gather_values` uses `deps.cf_run` and `deps.git_run`; `UNKNOWN_ADVICE` words `reply`, `cancel` and `send` for each; the runs document keeps a lower kind out once a higher one is cut; paused runs come first in `status` and `list` text; `tests/test_read_side_defined_once.py` allows `wire/protocol.py` to hold the served name `list` and the body key `runs`.

### Special Considerations

- **Secrets.** The raw `origin` is the one new value that can hold a secret. It is reduced in the client part and never sent.
- **No `cf` or `git` under a lock.** The client part and the naming gather run before any transaction, as every `cf` call does today.
- **The acting machine is the calling machine.** Every lookup that takes a machine takes it from the store's acting machine, never from the request.

## Operator Walkthrough

Done as the person running it.

- **Upgrade on the PM's install.** `update_live.py update` runs as the last step of the release. It backs up to `<state home>/backups/<stamp>/`, and the `amoeba list` it runs names every member. `amoeba list members` shows the names, each member's checkout, and marks any member named by its id or with no checkout.
- **A member is named by its id.** Its project is gone from Context Forge, or its name clashed. `amoeba add --project <id> --name <name>` from anywhere renames it. If it has no checkout because its project is gone and the repo is still on disk, `amoeba add --attach-to <id>` in the repo gives it one. If the repo is gone, `amoeba rm <id>`. A wake command it had is in the naming log line, and is set again with `amoeba add --wake-command` in the checkout.
- **The update fails.** A failed read-back restores by itself and says what failed. So does a `cf` failure in `amoeba list`: the store, the config and the installed commit are back as they were, and `update` is run again once `cf` works. A failed install stops the script before anything is migrated: run `update` again. A restore that fails is run again; the backup is not changed by it.
- **A hub store from before this slice holds members.** Only a 260 fixture store or a backup of one can. The hub names each by its id when it opens the store, and they are handled as under "A member is named by its id".
- **`cf` is broken at the first call.** The call exits 3 with `cf`'s error. Nothing is written. Once `cf` works, the next call names the members.
- **A checkout is on a hung mount at the first call.** Its `git` call times out after 10 seconds, and all of them together stop after 30. The member is named with no `origin`, and the call goes on. `amoeba add` in that checkout later records the `origin`.
- **Normal path.** `amoeba add` in a repo on each machine. The first creates the member; the others attach by `origin`. `send --to <name>` from any member reaches it, and every checkout's agents read one inbox.
- **`add` is refused as `name_taken`.** The detail shows both remotes. A different repo: `--name`. The same repo whose member has no `origin` recorded: give the member's checkout the same `origin` remote, run `amoeba add` there, then here again. Without the remote, `add` there records nothing and this one is refused again. If the member has no checkout, `amoeba add --attach-to <name>` here.
- **`add` is refused as `no_origin`.** Add an `origin` remote to both clones and run `add` in the first one again, or use `--name` for a separate member.
- **`add` attached to the wrong member.** `amoeba rm --checkout <path>`, then `amoeba add --new-member --name <name>`. The new member has no `origin` recorded and this one checkout.
- **Two existing members were one repo.** Naming gave the `origin` to the one registered first. `amoeba rm` the spare: its open requests are cancelled as `member_removed` and its inbox is not read again. Send again what is still wanted.
- **A repo with no `origin` became two members.** `list members` shows both with no `origin`. `amoeba rm` the spare, and add an `origin` remote so later checkouts attach.
- **`status` or `list` is slow or cut.** With `cf` hanging, the directory lookups stop after 60 seconds and the runs not looked up show as unplaced. With more runs than fit, `file_problems` says how many were left out; paused runs are kept first.
- **The repo moved to another host.** Change the remote in every checkout, then `amoeba add` in one records the new `origin`. Checkouts on other machines are already attached and keep working. A checkout left with the old remote puts the old `origin` back at its next `add`; the result shows both values.
- **`add` is refused as `origin_taken`.** Another member already has this checkout's new `origin`, so the two are one repo. The detail names both. `amoeba rm <name>` the one to drop, then `amoeba add` here again: it records the `origin`, or attaches this checkout to the member that has it.
- **A clone was deleted.** `amoeba rm --checkout <path>` on that machine, with the path as `list members` shows it. The member and its other checkouts stay. A path that is not on record is refused, and the refusal lists the paths that are.
- **A repo was moved to another directory.** Calls from it still find the member, because the machine and project id are the same. `list members` still shows the old path, and a wake or a concept read would use it. `amoeba rm --checkout <old path>`, then `amoeba add` in the new place: it attaches by `origin`, or with `--attach-to <name>` when the member has no `origin`. Set the wake command again if it had one.
- **`add` is run in a second worktree of a registered project.** `unchanged`. The checkout keeps the path it was made with.
- **A machine is retired.** `amoeba hub rm-machine`. Its checkouts go. A member left with none is marked in `list members`, its mail waits for expiry, and `amoeba rm <name>` from any machine removes it, or `add` on another machine brings it back.
- **A wake command.** `amoeba add --wake-command ...` in the checkout that should run it. `--no-wake-command` there clears it. It always applies to the checkout it is run in. With `--project` it is refused, so no checkout's command is set from another.
- **`send` through the door to a member that would be woken.** Refused as `not_served`, naming the member and each machine that has a checkout of it with a wake command; nothing is written. `amoeba add --no-wake-command` in those checkouts lets the `send` through. Only fixtures are joined before 264, and 262 serves it.
- **A call's outcome is unknown.** The error says to run `inbox` or `list` (or `list members`) before sending again.
- **Undo.** `amoeba rm <name>` removes a member. `add` in its repo registers it again with its history when the repo has an `origin`. With none, nothing ties the checkout to the removed member, so `add` creates a new member and the old records stay with the removed row. For the upgrade itself, `uv run python scripts/update_live.py restore` puts the store back as it was before the migration.

Dead ends found: two, running the walkthrough on the built slice (a joined machine's `add` text needing a local config, and `name_taken`'s way on cut in text); both fixed, see the Verification Walkthrough. One limit, stated above: a repo with no `origin` that is removed and added again is a new member.

Dead ends found by the full-text design review of 20261121, and how each is resolved:

- A repo added after this slice could not have its pauses answered: the pause path gave the member id to `cf -p`, and a new member's id is not a Context Forge id. The pause path now passes the checkout's Context Forge id (D6).
- The hub reduced an `origin` that was already reduced, which empties it or changes it, so no second checkout could attach. The hub now checks the form and refuses anything else (D3).
- After a `cf` failure in the update's `amoeba list`, naming the members by hand or running `update` again left a restore point that reinstalls code the store refuses. The script now restores by itself on that failure (D16).
