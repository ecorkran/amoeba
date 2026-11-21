---
docType: review
layer: project
reviewType: slice
slice: members-by-name
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/261-slice.members-by-name.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 63c02d65fae045f381aca2b679c3e601c73233d7
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: xhigh
turns: 9
promptTokens: 725352
cachedTokens: 484437
cacheWriteTokens: 240905
completionTokens: 99643
durationSeconds: 458.8
costUsd: 0.501499
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "The documented undo for a wrong origin attach does not work"
    location: "project-documents/user/slices/261-slice.members-by-name.md:565"
  - id: F002
    severity: fail
    category: scope
    summary: "The live-store migration is deferred, against the plan's criterion"
    location: "project-documents/user/slices/261-slice.members-by-name.md:436"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Absent or oversized gathered facts have no defined outcome"
    location: "project-documents/user/slices/261-slice.members-by-name.md:339-345"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Status and list latency has no bound, and naming's waits add up serially"
    location: "project-documents/user/slices/261-slice.members-by-name.md:406"
  - id: F005
    severity: concern
    category: architecture
    summary: "The import rule contradicts where the run reads live"
    location: "project-documents/user/slices/261-slice.members-by-name.md:103"
  - id: F006
    severity: concern
    category: specification
    summary: "A name can equal another member's id, and lookup then routes to the wrong member"
    location: "project-documents/user/slices/261-slice.members-by-name.md:248"
  - id: F007
    severity: concern
    category: architecture
    summary: "The no-origin rule is weakened, and the split is missing from the risk assessment"
    location: "project-documents/user/slices/261-slice.members-by-name.md:277"
  - id: F008
    severity: concern
    category: operations
    summary: "A member with no checkout and no origin has no working exit, and the origin rule for a checkout without one is undefined"
    location: "project-documents/user/slices/261-slice.members-by-name.md:594"
  - id: F009
    severity: concern
    category: scope
    summary: "Two mechanisms the design does not need, and an effort rating that does not match"
    location: "project-documents/user/slices/261-slice.members-by-name.md:189"
  - id: F010
    severity: note
    category: specification
    summary: "Two plan departures are not in the departures table"
    location: "project-documents/user/slices/261-slice.members-by-name.md:419-436"
  - id: F011
    severity: note
    category: specification
    summary: "The live variant's MCP part cannot run on a joined machine"
    location: "project-documents/user/slices/261-slice.members-by-name.md:403-404"
  - id: F012
    severity: note
    category: dependencies
    summary: "The design depends on a 260 design whose latest review is FAIL"
    location: "project-documents/user/slices/261-slice.members-by-name.md:73"
  - id: F013
    severity: pass
    category: architecture
    summary: "The served list and the mode switch match the plan's 261 entry"
    location: "project-documents/user/slices/261-slice.members-by-name.md:366"
  - id: F014
    severity: pass
    category: architecture
    summary: "Each operation splits into a client part and a hub part, as the architecture requires"
    location: "project-documents/user/slices/261-slice.members-by-name.md:117-122"
---

# Review: slice — slice 261

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] The documented undo for a wrong origin attach does not work

The risk mitigation says "a wrong attach is undone with `rm --checkout` and `add --name`", and the walkthrough repeats it at line 600. D7 checks steps in order. Step 2 says that when an active member has this `origin`, the checkout "is added to it, whatever its name." Line 281 says `--name` applies "for either way of choosing the member." After `rm --checkout`, the wrong member still holds the origin, so `add --name N` in that directory matches step 2 again. It attaches to the wrong member and renames that member to N. Step 4, the only step that creates a new member under `--name`, is unreachable. `rm` on the wrong member does not help either, because step 3 registers the most recently removed member with that origin again. The only route left is changing the repo's `origin`, which edits the user's repo to fix Amoeba's record.

The design accepts false origin matches (line 189, and the Risk Assessment calls a false merge the main risk), so it needs a working exit. One option is a flag that makes this checkout a new member and skips steps 2 and 3. Line 610 ("Dead ends found: none") must change with it.

### [FAIL] The live-store migration is deferred, against the plan's criterion

The departures table (line 436) and D16 (line 417) move the live-store migration to the release run of `update_live.py`. The slice plan's 261 criteria require "the live store is backed up and migrated, with the restore path in the slice notes." The plan's Planning Context says schema changes "land on the local store as they come." The stated reason, "live updates ride with the release," is not a rule in AGENTS.md. The Amoeba design rules reject deferral, and the 260 slice review rated the same deferral FAIL (F001). The PM's standing designation for migrations means no task needs to block on it. Run the migration in this slice with the backup and restore path, as the plan says.

### [CONCERN] Absent or oversized gathered facts have no defined outcome

Nothing says what the hub part does when a body key it needs is missing. Line 454 says `here` is "absent when the request names its member," but `send`, `inbox`, `reply` and the others need a caller and name no member, so an absent `here` has no defined result. `runs` is required for `status` and `list` with no subject, with no rule for when it is absent. A status call without `runs` would show no runs and look correct, which is the silent fallback the principles forbid.

The 1 MiB claim at line 344 is bounded only for completed runs. Non-completed runs, each with a `cf` result, run-file facts and a calls-log line, have no cap. The design also does not say what happens when the call is refused as oversized. Specify that a missing or malformed `here` or `runs` is `malformed_call`, and give the cap or the oversize outcome for non-completed runs.

### [CONCERN] Status and list latency has no bound, and naming's waits add up serially

The architecture's latency rule is one `cf` call plus one round trip. The slice restates it with targets for nine operations. For `status` and `list` it says they "also make the `sq` and `cf` reads they make today." `status` makes one `cf get` per run directory (D11), each bounded at 30 seconds, so the total is unbounded.

The naming step has the same problem. Each member's `git` call can wait up to 10 seconds (line 213), and the calls run one after another for every unnamed member. Ten members on a slow mount would take about 100 seconds on the first call, and that call also runs in the pause hook and `amoeba-mcp`. The `cf list projects` call in naming has no stated timeout. State a total bound for `status`, `list` and naming, and say what happens when it is hit.

### [CONCERN] The import rule contradicts where the run reads live

The component table puts one interface, `run_reads`, with two sources: the disk (`sq runs list`, run files, the calls log) and the gathered document. `status` and `list` are served operations, and the import rules at lines 110–113 say `served` reaches no module that imports `upstream`. The disk source needs `upstream`, so the table as written breaks that rule, and the design does not say where the disk source lives. Name a module for it outside the served closure, or state that the disk source runs only in the client part, which D5 already implies.

### [CONCERN] A name can equal another member's id, and lookup then routes to the wrong member

D1 makes names unique only among names (line 158). D6 says "a name wins over an id" (line 248). `--name` accepts any string that matches the pattern, including another member's id, which results display and an agent may copy. After that, `send --to <id>` silently reaches the member with that name. The architecture requires a name to be "unique in the store." Refuse a name that equals any member's id, in `add` and in naming, and test it.

### [CONCERN] The no-origin rule is weakened, and the split is missing from the risk assessment

The architecture says a repo with no `origin` "can have one checkout only. A second is refused." The design refuses a second no-origin checkout only when it arrives under the member's name (line 277; departures row at line 429). After a rename, a second checkout of the same repo becomes a second member with a second inbox. That is the split the architecture's "several agents in one repo are one member" principle exists to prevent. The Risk Assessment (lines 555–565) considers only false merges. Either keep the architecture's rule or have the PM amend the architecture, and add the false split to the risks.

### [CONCERN] A member with no checkout and no origin has no working exit, and the origin rule for a checkout without one is undefined

Two dead ends contradict "Dead ends found: none" (line 610):

- A member named by its id because its project is gone from Context Forge has no checkout (D4 creates one only for a project `cf` lists) and no origin (D4 needs a path). The walkthrough's remedy, `amoeba add --name` "in its checkout" (line 594), has no checkout to run in. If the repo is still on disk, `add` there creates a second member under the Context Forge name. If the repo has an origin, the call is refused as `name_taken` with the advice to run `add` "in its existing checkout first" (line 598), and that checkout does not exist. The state table's exit, "a new add in a checkout of the repo" (line 141), works only for members that have an origin.
- D7 step 1 (lines 268–269) replaces the member's origin when it "differs from this checkout's." The design does not say what happens when this checkout has no origin because its remote was removed. If the member's origin becomes null, the next clone of the repo splits the member.

Specify the attach rule for a member with no checkout and no origin, fix the advice text, and state the step 1 rule for a checkout with no origin.

### [CONCERN] Two mechanisms the design does not need, and an effort rating that does not match

- The port drop in `reduce_origin` (line 189) handles remotes that differ only by port. Nothing in the design or the plan says such remotes exist. The design admits the drop adds a false-merge case, and the Risk Assessment calls false merges the main risk. Cut it unless a real remote needs it.
- `run_reads` as an interface with two implementations (lines 336–337) is heavier than needed. Only the client part reads the disk. D5 (line 230) says the hub gets the same values in process when there is no client file. The hub part only needs a plain document type and one gather function. That also removes the import conflict above.
- The plan rates this slice Relative Effort 4 and the 260 slice 5. This design has 16 decisions, ten operations, a new migration, a naming step, a read interface, a chain test, a live variant and an extended load test. Cut the items above, or ask the PM to revise the plan's effort.

### [NOTE] Two plan departures are not in the departures table

- The plan says `add` "sends the checkout's `origin`, reduced to host and path" (plan, item 2). The design sends the raw address and the hub reduces it (line 227; departures row at line 425). The design follows the architecture, which says the hub reduces, but raw sending puts a possible password on the wire, which the plan's version avoids. Record the departure and its reason.
- Line 368 says `list` and `status` "keep no result" because their only write is the message expiry. The architecture says the hub keeps each writing call's result. The reasoning holds because the expiry is idempotent, but the table should say so.

### [NOTE] The live variant's MCP part cannot run on a joined machine

Slice 260 (D2) refuses `amoeba-mcp` start on a joined machine, so no MCP part can run on a fixture home with a client file in this slice. Line 404 says the variant's MCP part "stays on the local store until 263." That works only in a home with no client file, where it cannot see the hub's messages. State that the variant is CLI-only. The chain test also needs members with no wake command. A `send` to a member with a wake command is refused as `not_served` (line 310), and the 240 chain (slice plan 240, Scenario D) sends with a `parent` link.

### [NOTE] The design depends on a 260 design whose latest review is FAIL

This design pins slice 260's decisions "as written at commit 729b57fb." The latest 260 slice review is FAIL, with three FAIL findings. None touches 261's inputs directly. But 260's pending findings on stderr logging and inbound timeouts (F005, F006) would change door behavior that 261 relies on, so recheck D6, D8 and D9 after 260 is revised. The design already says it will update, which is right.

### [PASS] The served list and the mode switch match the plan's 261 entry

The ten served operations and the excluded ones (`answer`, `handle_pause`, `wake-run`, `amoeba-mcp`) match the plan's 261 and 262 entries. The refusal of `send` to a recipient with a wake (line 310) is the plan's split, not a deferral of 261 scope.

### [PASS] Each operation splits into a client part and a hub part, as the architecture requires

The data flow keeps `cf`, `git` and `sq` on the calling machine, and the design gives the hub part no calls to them (the import finding above covers the one exception). The `here` and `runs` values travel as body keys, which slice 260 allows. The client part's failure modes for `cf get` and `git` (lines 232–234) are enumerated with explicit outcomes.

### Run Digest

- Response length: 13059 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 725352 / 484437 / 240905 / 99643 / not computed
- Duration: 458.8 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
