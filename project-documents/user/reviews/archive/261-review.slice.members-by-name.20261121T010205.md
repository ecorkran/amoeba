---
docType: review
layer: project
reviewType: slice
slice: members-by-name
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/261-slice.members-by-name.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: d135433e4008eccaf3cc657974032f12dc5213d9
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 1095611
cachedTokens: 897050
cacheWriteTokens: 198545
completionTokens: 51672
durationSeconds: 249.7
costUsd: 0.359849
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: scope-alignment
    summary: "Breaking renames conflict with the parent's \"daily use does not change\" goal"
    location: "project-documents/user/slices/261-slice.members-by-name.md:387-390"
  - id: F002
    severity: concern
    category: architecture-conformance
    summary: "A no-origin repo can get a second member when its member was renamed"
    location: "project-documents/user/slices/261-slice.members-by-name.md:274-277"
  - id: F003
    severity: concern
    category: error-handling
    summary: "One member whose `git` call hangs blocks every command, with no exit in the walkthrough"
    location: "project-documents/user/slices/261-slice.members-by-name.md:215"
  - id: F004
    severity: concern
    category: operator-walkthrough
    summary: "The walkthrough says \"Dead ends found: none,\" but one `origin_taken` case has no exit"
    location: "project-documents/user/slices/261-slice.members-by-name.md:599"
  - id: F005
    severity: concern
    category: security
    summary: "\"Never logged\" depends on an error contract the design does not state"
    location: "project-documents/user/slices/261-slice.members-by-name.md:195"
  - id: F006
    severity: concern
    category: nfr
    summary: "NFRs touched by this slice are not restated with targets"
    location: "project-documents/user/slices/261-slice.members-by-name.md:405"
  - id: F007
    severity: pass
    category: integration
    summary: "Cited interfaces exist, and the hub-side design calls no `cf`, `git` or `sq`"
    location: "project-documents/user/slices/261-slice.members-by-name.md:118-123"
  - id: F008
    severity: note
    category: architecture-conformance
    summary: "State where `program_sources` runs, since it reads a checkout's files"
    location: "project-documents/user/slices/261-slice.members-by-name.md:256"
  - id: F009
    severity: note
    category: scope-alignment
    summary: "A third naming fallback is not in the parent or the departures table"
    location: "project-documents/user/slices/261-slice.members-by-name.md:208"
---

# Review: slice — slice 261

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Breaking renames conflict with the parent's "daily use does not change" goal

The parent's Design Goals say "Daily use does not change. The operations, their names and their results stay as they are" (`260-arch.the-hub.md:39`). This design removes `--project` (line 447), renames `project_id` to `member_id` in `MemberState` and `MemberRow`, and removes `path`, `in_context_forge` and `wake_command` from `MemberRow` (lines 387-388). The departures table (line 429) records this, but the parent is not amended, so the two documents disagree on a stated goal.

The rename is also heavier than the requirement. Forty-three files under `src/amoeba` contain `project_id`. Seven are SQL migrations, so 36 Python files change, which matches the design's estimate. The requirement is a stable opaque key. The design rejects keeping the name because the value is no longer a Context Forge id. A documented opaque column carries the same meaning without renaming the result models. The lighter option is to keep `project_id` as the key name, keep the result field names, and keep `--project` as the flag. Otherwise the PM should amend the parent's goal and its Changes table.

### [CONCERN] A no-origin repo can get a second member when its member was renamed

The parent says "The repo has no `origin`: it can have one checkout only. A second is refused and says why" (`260-arch.the-hub.md:160`). Step 5 refuses `no_origin` only when the checkout's name is taken. Step 4 creates a new member when the name is free.

Scenario: machine A adds a no-origin repo as `widget`. On A, `add --name widget-fork` renames that member (step 1, line 281 applies `--name` to the member). On machine B, the same repo has no `origin`, and its Context Forge name `widget` is now free. Step 4 creates a second member, and nothing is refused. The success criterion at line 489 covers only the default-name case.

Without an `origin` the store has no signal that the two checkouts are one repo, so the parent's rule cannot be enforced in this case. The design should either record this as a departure with its reason, or restate the parent's rule as "refused when the name is taken."

### [CONCERN] One member whose `git` call hangs blocks every command, with no exit in the walkthrough

The naming step gathers `git remote get-url origin` for every unnamed member, then writes once. Any failure other than exit 2 or 128, including a timeout, raises, writes nothing, and exits 3 on every call (line 215). A single checkout on a hung network mount therefore blocks every `amoeba` command on the PM's store, including `rm` and `add --name`, until the mount is fixed. The walkthrough covers only `cf` failing (line 594).

Because a missing `origin` only ever refuses and never matches (`:564`), a timed-out `git` could record `origin` as null with a logged line. The member is still named, and a later `add` in its checkout records the `origin`, as line 270 already allows. `cf` failures would keep blocking, as the design intends.

### [CONCERN] The walkthrough says "Dead ends found: none," but one `origin_taken` case has no exit

Line 599 says that when a repo moves to another host, "`amoeba add` in any registered checkout records the new `origin`." Line 271 refuses that when another active member already has the new `origin`, as `origin_taken`. The walkthrough does not describe that case. The refusal's detail text is not specified, and the way out (remove one of the two members with `amoeba rm`) appears nowhere. Line 607 then reports "Dead ends found: none." Per the Amoeba design rules, the walkthrough should list this one and say how the operator leaves it.

### [CONCERN] "Never logged" depends on an error contract the design does not state

Line 195 says a raw `origin` "is sent to the hub, reduced there, and never stored, logged or returned." The 260 design logs a `hub_fault` with `logger.exception`, so the full traceback goes to the hub log (`260-slice.hub-and-door.md:331-334`). If `reduce_origin` or the hub part raises with the input in the exception text, the password reaches the log. The design does not state that `reduce_origin` never raises on input or echoes it. The success criterion at line 492 also does not test a malformed address that carries a password. The fix is one stated rule for `reduce_origin`'s errors, plus a test with a malformed credential-bearing address.

### [CONCERN] NFRs touched by this slice are not restated with targets

The parent states a latency NFR: "A CLI call is a `cf` call plus one round trip" (`260-arch.the-hub.md:287`). It also requires a load test that "asserts a bound on call time" (`:286`). This slice touches both paths, but the design says only "260's door load test adds `send` and `inbox` callers." The target (2 seconds per call, 200 ms median) lives in 260's design, not here. This slice should restate the bound it inherits. It should also state that `add` adds a `git` subprocess to the CLI path, and give that call's timeout, since the parent's latency statement does not count it.

### [PASS] Cited interfaces exist, and the hub-side design calls no `cf`, `git` or `sq`

I confirmed these exist in the tree: `upstream/git_read.py` (`git_read`, with an allowlist that `remote` must join), `upstream/context_forge/project_of.py` (`project_of`, which D10 changes), `projects.py` (`project_details`, which treats `projectPath` as optional), `operations/member_reference.py`, `project_lookup.py`, `members.py`, `message_member.py` (`resolve_caller`, `resolve_actor`, `resolve_recipient`), `release_member.py` (`resolve_release_member`), `wiring_messages.py` (`MESSAGE_LOOKUPS`), `add_door.py` (`refuse_door_fields`) and `set_up_resolve.py`. The 260 decisions the design cites (D6, D8, D9, D11, D12, D18) match the 260 design. The hub-part rule at line 121 is consistent with the parent's "hub never reads a client's disk."

### [NOTE] State where `program_sources` runs, since it reads a checkout's files

`read_program_sources` runs git reads inside a checkout path (`operations/program_sources.py`, lines 180-191), and today it is reached only from `pause_context.py`, which is client-run and not served in 261. D6 says the path comes from "the acting machine" but does not say where the function runs. If the hub ever ran it, the acting machine's path would be the caller's disk, which the parent prohibits. The design should say it runs only in the client-run pause path, and 262 should keep it there.

### [NOTE] A third naming fallback is not in the parent or the departures table

The parent describes two fixed cases for naming existing members (`260-arch.the-hub.md:227`). This design adds a third: a Context Forge name that fails the pattern is named by its id (line 208). The same name is refused as `malformed` when `add` creates a member (line 163). Both choices are defensible, but the departures table does not record the third case, and the two paths disagree on the same input. The departures table should list it, with the reason.

### Run Digest

- Response length: 9191 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 1095611 / 897050 / 198545 / 51672 / not computed
- Duration: 249.7 s
- Cost: $0.36 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

### Raw Response

The `program_sources` read is only reached from `pause_context.py`, which is client-run and not served in 261. Next I'll check whether `add --concept` validation reads a client's disk, and confirm the `git_read` subcommand list and the `project_id` file count that the design cites.
The concept validation in `set_up_checks.py` only checks membership, so `add --concept` does not read a client's disk. Two more checks: whether the status path compares run-file times with hub time, and how `projectPath` is handled for projects that lack one.
## Summary

**Verdict: CONCERNS**

The design follows the parent's main structure: the hub calls no `cf`, `git` or `sq`, the client gathers local facts, names are read from the store, and the 260 decisions it cites match the 260 design. Six issues need fixing before task breakdown: a stated goal it breaks without amending the parent, a parent rule it does not enforce in one case, two operator dead ends, a secrecy guarantee that depends on an unstated error contract, and a missing NFR restatement.

I did not run `cf` or `git`, since this session has no shell. The facts section is taken as dated. `run_served` and `SERVED_OPERATIONS` come from 260, which is not built, so I checked them only as stated dependencies.

## Findings

### [CONCERN] Breaking renames conflict with the parent's "daily use does not change" goal
location: project-documents/user/slices/261-slice.members-by-name.md:387-390
category: scope-alignment

The parent's Design Goals say "Daily use does not change. The operations, their names and their results stay as they are" (`260-arch.the-hub.md:39`). This design removes `--project` (line 447), renames `project_id` to `member_id` in `MemberState` and `MemberRow`, and removes `path`, `in_context_forge` and `wake_command` from `MemberRow` (lines 387-388). The departures table (line 429) records this, but the parent is not amended, so the two documents disagree on a stated goal.

The rename is also heavier than the requirement. Forty-three files under `src/amoeba` contain `project_id`. Seven are SQL migrations, so 36 Python files change, which matches the design's estimate. The requirement is a stable opaque key. The design rejects keeping the name because the value is no longer a Context Forge id. A documented opaque column carries the same meaning without renaming the result models. The lighter option is to keep `project_id` as the key name, keep the result field names, and keep `--project` as the flag. Otherwise the PM should amend the parent's goal and its Changes table.

### [CONCERN] A no-origin repo can get a second member when its member was renamed
location: project-documents/user/slices/261-slice.members-by-name.md:274-277
category: architecture-conformance

The parent says "The repo has no `origin`: it can have one checkout only. A second is refused and says why" (`260-arch.the-hub.md:160`). Step 5 refuses `no_origin` only when the checkout's name is taken. Step 4 creates a new member when the name is free.

Scenario: machine A adds a no-origin repo as `widget`. On A, `add --name widget-fork` renames that member (step 1, line 281 applies `--name` to the member). On machine B, the same repo has no `origin`, and its Context Forge name `widget` is now free. Step 4 creates a second member, and nothing is refused. The success criterion at line 489 covers only the default-name case.

Without an `origin` the store has no signal that the two checkouts are one repo, so the parent's rule cannot be enforced in this case. The design should either record this as a departure with its reason, or restate the parent's rule as "refused when the name is taken."

### [CONCERN] One member whose `git` call hangs blocks every command, with no exit in the walkthrough
location: project-documents/user/slices/261-slice.members-by-name.md:215
category: error-handling

The naming step gathers `git remote get-url origin` for every unnamed member, then writes once. Any failure other than exit 2 or 128, including a timeout, raises, writes nothing, and exits 3 on every call (line 215). A single checkout on a hung network mount therefore blocks every `amoeba` command on the PM's store, including `rm` and `add --name`, until the mount is fixed. The walkthrough covers only `cf` failing (line 594).

Because a missing `origin` only ever refuses and never matches (`:564`), a timed-out `git` could record `origin` as null with a logged line. The member is still named, and a later `add` in its checkout records the `origin`, as line 270 already allows. `cf` failures would keep blocking, as the design intends.

### [CONCERN] The walkthrough says "Dead ends found: none," but one `origin_taken` case has no exit
location: project-documents/user/slices/261-slice.members-by-name.md:599
category: operator-walkthrough

Line 599 says that when a repo moves to another host, "`amoeba add` in any registered checkout records the new `origin`." Line 271 refuses that when another active member already has the new `origin`, as `origin_taken`. The walkthrough does not describe that case. The refusal's detail text is not specified, and the way out (remove one of the two members with `amoeba rm`) appears nowhere. Line 607 then reports "Dead ends found: none." Per the Amoeba design rules, the walkthrough should list this one and say how the operator leaves it.

### [CONCERN] "Never logged" depends on an error contract the design does not state
location: project-documents/user/slices/261-slice.members-by-name.md:195
category: security

Line 195 says a raw `origin` "is sent to the hub, reduced there, and never stored, logged or returned." The 260 design logs a `hub_fault` with `logger.exception`, so the full traceback goes to the hub log (`260-slice.hub-and-door.md:331-334`). If `reduce_origin` or the hub part raises with the input in the exception text, the password reaches the log. The design does not state that `reduce_origin` never raises on input or echoes it. The success criterion at line 492 also does not test a malformed address that carries a password. The fix is one stated rule for `reduce_origin`'s errors, plus a test with a malformed credential-bearing address.

### [CONCERN] NFRs touched by this slice are not restated with targets
location: project-documents/user/slices/261-slice.members-by-name.md:405
category: nfr

The parent states a latency NFR: "A CLI call is a `cf` call plus one round trip" (`260-arch.the-hub.md:287`). It also requires a load test that "asserts a bound on call time" (`:286`). This slice touches both paths, but the design says only "260's door load test adds `send` and `inbox` callers." The target (2 seconds per call, 200 ms median) lives in 260's design, not here. This slice should restate the bound it inherits. It should also state that `add` adds a `git` subprocess to the CLI path, and give that call's timeout, since the parent's latency statement does not count it.

### [PASS] Cited interfaces exist, and the hub-side design calls no `cf`, `git` or `sq`
location: project-documents/user/slices/261-slice.members-by-name.md:118-123
category: integration

I confirmed these exist in the tree: `upstream/git_read.py` (`git_read`, with an allowlist that `remote` must join), `upstream/context_forge/project_of.py` (`project_of`, which D10 changes), `projects.py` (`project_details`, which treats `projectPath` as optional), `operations/member_reference.py`, `project_lookup.py`, `members.py`, `message_member.py` (`resolve_caller`, `resolve_actor`, `resolve_recipient`), `release_member.py` (`resolve_release_member`), `wiring_messages.py` (`MESSAGE_LOOKUPS`), `add_door.py` (`refuse_door_fields`) and `set_up_resolve.py`. The 260 decisions the design cites (D6, D8, D9, D11, D12, D18) match the 260 design. The hub-part rule at line 121 is consistent with the parent's "hub never reads a client's disk."

### [NOTE] State where `program_sources` runs, since it reads a checkout's files
location: project-documents/user/slices/261-slice.members-by-name.md:256
category: architecture-conformance

`read_program_sources` runs git reads inside a checkout path (`operations/program_sources.py`, lines 180-191), and today it is reached only from `pause_context.py`, which is client-run and not served in 261. D6 says the path comes from "the acting machine" but does not say where the function runs. If the hub ever ran it, the acting machine's path would be the caller's disk, which the parent prohibits. The design should say it runs only in the client-run pause path, and 262 should keep it there.

### [NOTE] A third naming fallback is not in the parent or the departures table
location: project-documents/user/slices/261-slice.members-by-name.md:208
category: scope-alignment

The parent describes two fixed cases for naming existing members (`260-arch.the-hub.md:227`). This design adds a third: a Context Forge name that fails the pattern is named by its id (line 208). The same name is refused as `malformed` when `add` creates a member (line 163). Both choices are defensible, but the departures table does not record the third case, and the two paths disagree on the same input. The departures table should list it, with the reason.
