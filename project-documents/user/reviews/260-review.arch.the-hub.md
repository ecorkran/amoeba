---
docType: review
layer: project
reviewType: arch
slice: the-hub
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS (all eleven findings were checked, found valid and fixed in the document 20261120, see Resolution)
verdictSource: stated
sourceDocument: project-documents/user/architecture/260-arch.the-hub.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: d57913ed7e7fee8fe6efd0dde556415bb43c392f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: high
turns: 18
promptTokens: 1045448
cachedTokens: 929151
cacheWriteTokens: 116275
completionTokens: 17378
durationSeconds: 186.5
costUsd: 1.464586
costBasis: provider
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: feasibility
    summary: "The resume claim's time limit ignores network retries, so a slow resume can be handed out a second time"
    location: "project-documents/user/architecture/260-arch.the-hub.md:175-181"
  - id: F002
    severity: concern
    category: completeness
    summary: "A hook waiting on adoption's lock can write into the dated backup after the switch"
    location: "project-documents/user/architecture/260-arch.the-hub.md:222-228"
  - id: F003
    severity: concern
    category: completeness
    summary: "Adoption has no exit when its outcome is unknown, or when a step after the load fails"
    location: "project-documents/user/architecture/260-arch.the-hub.md:228"
  - id: F004
    severity: concern
    category: consistency
    summary: "On a second machine, `add` finds members by name, so a renamed member silently gets a duplicate"
    location: "project-documents/user/architecture/260-arch.the-hub.md:146-149"
  - id: F005
    severity: concern
    category: completeness
    summary: "A hub started fresh, not by adoption, has no way to get its `config.yaml`"
    location: "project-documents/user/architecture/260-arch.the-hub.md:84"
  - id: F006
    severity: concern
    category: feasibility
    summary: "Taking a backup at every start lets a crash loop rotate out the good backups"
    location: "project-documents/user/architecture/260-arch.the-hub.md:92"
  - id: F007
    severity: concern
    category: consistency
    summary: "When pending work is asked for is stated two different ways"
    location: "project-documents/user/architecture/260-arch.the-hub.md:172"
  - id: F008
    severity: concern
    category: completeness
    summary: "Kept results need to be in the same transaction and keyed by machine, and their lifetime must cover client retries"
    location: "project-documents/user/architecture/260-arch.the-hub.md:62"
  - id: F009
    severity: note
    category: consistency
    summary: "\"Who is calling\" says the client sends the machine; that must come from the token"
    location: "project-documents/user/architecture/260-arch.the-hub.md:151"
  - id: F010
    severity: note
    category: completeness
    summary: "Check 1 under Anticipated Slices can already be answered: the pause claim already has a time limit"
    location: "project-documents/user/architecture/260-arch.the-hub.md:285"
  - id: F011
    severity: note
    category: technology
    summary: "`amoeba-mcp` tick and tool calls under a hub outage"
    location: "project-documents/user/architecture/260-arch.the-hub.md:192"
---

# Review: arch — initiative 260

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] The resume claim's time limit ignores network retries, so a slow resume can be handed out a second time

The claim table says a resume's claim is handed out again after `resume_bound_seconds`. That bound (`src/amoeba/operations/resume.py:50-64`) adds up the wait, the polls, the kill graces and **one `BUSY_TIMEOUT_SECONDS`** for the final store write. Under the hub, that final write is a hub call, and the client retries it for `hub_retry_seconds`. The design makes that value a per-machine setting the hub never sees (line 133).

Here is the failure. The hub blips while a resume is recording its outcome. The resume process retries for `hub_retry_seconds`. On the hub's clock the claim reaches the limit with no outcome recorded. The next tick from another session on that machine takes the claim and starts `squadron resume` again for the same pause. That is the double resume the claim was added to stop.

`answer_bound_seconds` and `check_deadline` (`src/amoeba/wiring.py:297-309`) have the same problem. They check that a same-machine `answer` fits inside the MCP call deadline using local store waits only. With the hub, `answer` also spends a round trip and up to `hub_retry_seconds` for each hub call. But the config check runs where the config is (the hub), and the retry setting lives on each client, so no single place can do the check.

Fix this in the architecture. One option: the claim limit adds a retry allowance the hub knows, and the client caps its retries at it. Another: the hub sends its retry ceiling with the settings, and a client refuses a `hub_retry_seconds` above it. Either way, say where the MCP deadline check now runs.

### [CONCERN] A hook waiting on adoption's lock can write into the dated backup after the switch

Walkthrough step 2 says a pause hook that fires during the copy "waits on the lock for the store's busy time and fails". That is only true if adoption takes longer than the busy timeout, which is 5 seconds (`src/amoeba/store/store.py:28`). For a small store on a LAN, steps 2–5 can easily finish in under 5 seconds.

When they do, step 5 renames the store and releases the lock. The waiting hook already holds an open connection to the old file, now renamed. It gets the lock and commits its question **into the dated backup**. The hub never sees that question, and the hook reports success. The mode is decided per call, but this call decided before the client file existed. This is a silent lost write on the PM's live store, during the one migration the design rules say must have a safe restore.

Fix: before releasing the lock, commit a tombstone in the local store, in the same locked transaction. For example, set `user_version` to a sentinel or write an `adopted_to` row. Then every local write transaction checks for the tombstone and fails, naming the hub. Then change step 2 of the walkthrough to describe the actual behavior.

### [CONCERN] Adoption has no exit when its outcome is unknown, or when a step after the load fails

The document says: "If any step fails, nothing on the laptop has changed and the hub is emptied back to its owner and machines, so the command can be run again." That only works when the hub is the side that notices the failure, as with a row-count mismatch.

Two cases break it:
- **The reply to step 3 or 4 is lost** and the retries run out. The result is "unknown". The hub may hold the loaded store and config, but the laptop has no client file. A new `adopt` uses a new call id, and step 1 refuses because "the hub is not empty". No command empties a hub: the admin table at lines 100-106 has none.
- **Step 5 fails on the laptop**, for example the client file can't be written or the rename fails. The hub now holds the data, and "emptied back" needs another hub call that nobody makes.

Under "every state has an exit", that is a dead end. Either:
- make `adopt` safe to repeat (the hub records an adoption id and the laptop's row counts, and accepts a repeat of the same adoption as already done), or
- add an admin command that empties a hub holding only adopted data.

Then add the case to the walkthrough.

### [CONCERN] On a second machine, `add` finds members by name, so a renamed member silently gets a duplicate

`add` on a second machine "finds the member by name". The name it looks up is the Context Forge project name, unless `--name` is given. The `origin` check applies only after a name has matched.

Two cases go wrong:
- The PM renamed the member with `amoeba add --name`.
- The member lost a name clash during "Naming the members that already exist" (line 214), so its name is its id.

In both cases a plain `amoeba add` on the second machine finds no member with that name and **creates a new one**. The new member has the same `origin` and a separate inbox. Agents addressing the original never reach sessions on the second machine, and nothing reports it.

Fix: look up the normalized `origin` first. If a member already has that `origin`, attach the checkout to it, or refuse with that member's name shown. Never create a second member whose `origin` matches an existing one.

### [CONCERN] A hub started fresh, not by adoption, has no way to get its `config.yaml`

"`config.yaml` … arrives at adoption. Before then the hub serves machines and invites only." The config has required keys with no defaults, and no code writes a template (`src/amoeba/config/user_config.py:170-184` fails with "no config at …"). Adoption is the only path described, and it needs a local store.

So these cases end at a hub that refuses every operation:
- a new user;
- a single-machine user, who the "One mode" principle says runs a hub;
- the live test fixture with client files (line 273).

The walkthrough never covers them. State the path: the PM writes `config.yaml` in the hub's config directory from the image's example, as with `hub.yaml`. Or `amoeba hub serve` refuses to start without it. Add it to the walkthrough.

### [CONCERN] Taking a backup at every start lets a crash loop rotate out the good backups

"The hub takes one when it starts and every `backup_hours` after that, and keeps the newest `backups_kept`." The container restarts the hub on failure (line 88).

Suppose a release ships a bad migration, or a bug that crashes the hub after start. Each restart takes a fresh backup of the damaged store and deletes the oldest good one. After `backups_kept` restarts, which takes seconds, every backup is a copy of the bad state.

The document also doesn't say whether the start backup comes before or after migrations run. The repo's migration rule needs a backup first, with a stated restore path.

Fix:
- The start backup runs before migrations.
- Skip it when the newest backup is younger than `backup_hours`, or keep the backup taken before each migration outside the rotation.
- Say that restoring from it is `serve --from-backup` with the previous image.

### [CONCERN] When pending work is asked for is stated two different ways

Line 172: "Each `amoeba` call **that could have caused such work**, and each `amoeba-mcp` tick, asks the hub what this machine should start."

Line 184: work for another machine "starts the next time **anything** on that machine talks to the hub: **any** `amoeba` call or any open session."

These conflict. For example, an `inbox` or `decisions` call can't cause a resume, so under line 172 it doesn't ask. Under line 184 it picks up the laptop's waiting resume.

Pick one. The cheap way to make "any call" true is to put the pending-work answer in every hub response, not to add a second round trip. Say which. The latency figure at line 270 ("a `cf` call plus one round trip") depends on it.

### [CONCERN] Kept results need to be in the same transaction and keyed by machine, and their lifetime must cover client retries

"The hub keeps each writing call's result for a short time and gives the same result to a repeat." Three things this depends on aren't stated:
- **The same transaction.** The kept result must be written in the same transaction as the operation. Otherwise a crash between the commit and saving the result lets a repeat apply twice. "One hub call is one whole transaction" implies this, but say so.
- **Keyed by machine.** Kept results must be keyed by the token's machine as well as the call id. Otherwise one machine's repeated id could return another machine's result.
- **Two settings that must agree.** Retention is `call_result_minutes`, in `hub.yaml` on the hub. The retry window is `hub_retry_seconds`, in each client file. If a client's retry window is longer than the retention, a late repeat applies twice. Nothing checks this, because the two values never meet. Have the hub refuse, or have the client cap, a retry window longer than the retention, for example by sending its ceiling with the settings, as in the first finding.

### [NOTE] "Who is calling" says the client sends the machine; that must come from the token

"It sends the machine and that project id. The hub maps them to the member." Line 113 says "the token names the machine". Line 114's guard, that a wake command can be set only from its own machine, holds only if the hub ignores any machine the client names and uses the token's machine. Otherwise machine A's token could claim to be machine B and set B's wake command. Change the wording to: the client sends the project id, and the hub takes the machine from the token.

### [NOTE] Check 1 under Anticipated Slices can already be answered: the pause claim already has a time limit

The held-question claim ages out by `answering_wait_seconds`:
- `src/amoeba/operations/pause_class.py:117` ("`claim_age_limit` is `answering_wait_seconds`");
- the sweep's `CLAIMED` branch, `src/amoeba/operations/question_sweep.py:190`.

The third row of the claim table can name the limit directly, and the slice doesn't need to add one. One more thing worth saying: the sweep branch closes the question only with a run fate, and the fate is read from local run files. So on the hub, only the run's own machine can close a stale claimed question that way, which is the same limit stated at line 184.

### [NOTE] `amoeba-mcp` tick and tool calls under a hub outage

The tick is a blocking stdlib HTTPS call run off the event loop. During an outage, each call blocks its worker thread for up to `hub_retry_seconds`. The document doesn't say whether ticks run one after another or can overlap. If `notify_poll_seconds` is shorter than `hub_retry_seconds` and ticks overlap, blocked threads pile up until the hub returns.

The tick also doesn't need the retry, because the next tick is the retry. State that ticks run one after another and skip the retry. Tool calls keep it, within the MCP deadline from the first finding.

### Run Digest

- Response length: 12292 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 1045448 / 929151 / 116275 / 17378 / not computed
- Duration: 186.5 s
- Cost: $1.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11

## Resolution

Third review round, no fail findings. Each finding was checked against the code and the document. All eleven hold. Worked into `260-arch.the-hub.md` 20261120. Earlier rounds are in `archive/` and git history.

- F001 (fixed): the connect, read and retry times are constants shared by the client and the hub, not per-machine settings. Every claim's limit allows for the retries of its last call, and the MCP deadline check runs on the hub with the network times added.
- F002 (fixed): adoption marks the local store as adopted before releasing the lock, and every local write checks the mark, so a hook that was waiting on the lock fails and names the hub.
- F003 (fixed): adoption carries an id written to the local store first. Running the command again is safe: a hub holding that adoption skips or redoes the load and carries on. A hub holding anything else refuses and says how to empty it.
- F004 (fixed): `add` looks for the `origin` first, then the name, so a renamed member never gets a second copy from another machine.
- F005 (fixed): on a fresh hub the person writes `config.yaml` from the image's example. The walkthrough has the case.
- F006 (fixed): a timed backup is taken only when the newest is older than `backup_hours`, so a crash loop takes none. Backups before a migration are taken first and kept in their own rotation; undoing a bad release is the previous image started from that file.
- F007 (fixed): every hub reply carries a flag that this machine has work waiting, at no extra call. A client that sees it makes one call to claim and start the work.
- F008 (fixed): a kept result is written in the call's own transaction, under the machine and the call id, and its lifetime is worked out from the fixed retry time.
- F009 (fixed): the client sends the project id; the hub takes the machine from the token.
- F010 (fixed, verified in `pause_class.py` and `question_sweep.py`): the claim table names `answering_wait_seconds`, the slice's first check is removed as answered, and the document says only the run's own machine can clear a stale pause claim.
- F011 (fixed): ticks run one after another and do not retry; tool calls keep the retry.
