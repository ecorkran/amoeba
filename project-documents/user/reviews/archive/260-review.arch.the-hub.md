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
verdict: CONCERNS (reviewer stated FAIL; its three fail findings, F001 to F003, were checked, found valid and fixed 20261120, see Resolution)
verdictSource: stated
sourceDocument: project-documents/user/architecture/260-arch.the-hub.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: d01e60b464fbb74512460b896ac3ac375f0cb88f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: high
turns: 18
promptTokens: 1123003
cachedTokens: 1000346
cacheWriteTokens: 122635
completionTokens: 16109
durationSeconds: 182.6
costUsd: 1.504325
costBasis: provider
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: feasibility
    summary: "The resume has no claim, so several askers on one machine will each start a resume"
    location: "project-documents/user/architecture/260-arch.the-hub.md:161-162"
  - id: F002
    severity: fail
    category: completeness
    summary: "Adoption has a window where the laptop splits into two stores, and the file copy can lose data"
    location: "project-documents/user/architecture/260-arch.the-hub.md:182-204"
  - id: F003
    severity: fail
    category: completeness
    summary: "Restoring the hub on a new box ends with every client refusing to connect, and backups live on the disk they're meant to protect"
    location: "project-documents/user/architecture/260-arch.the-hub.md:81-92"
  - id: F004
    severity: concern
    category: feasibility
    summary: "Work for a machine with no session open never starts, including the cross-machine wake"
    location: "project-documents/user/architecture/260-arch.the-hub.md:158-166"
  - id: F005
    severity: concern
    category: completeness
    summary: "Automated multi-call commands have no rule for an \"unknown\" result partway through"
    location: "project-documents/user/architecture/260-arch.the-hub.md:117-121"
  - id: F006
    severity: concern
    category: feasibility
    summary: "Matching checkouts by remote address, and back-filling member names, are both under-specified"
    location: "project-documents/user/architecture/260-arch.the-hub.md:133-142"
  - id: F007
    severity: concern
    category: consistency
    summary: "The client file's copied timeouts go stale, so they are not \"set in one place\""
    location: "project-documents/user/architecture/260-arch.the-hub.md:128"
  - id: F008
    severity: concern
    category: technology
    summary: "Certificate pinning, and the backup timer, are left to the implementer and easy to get wrong"
    location: "project-documents/user/architecture/260-arch.the-hub.md:232"
  - id: F009
    severity: concern
    category: completeness
    summary: "`rm-machine` doesn't end every state tied to that machine"
    location: "project-documents/user/architecture/260-arch.the-hub.md:130"
  - id: F010
    severity: note
    category: consistency
    summary: "Store functions take `now` from the caller, which conflicts with \"the hub's clock is the clock\""
    location: "project-documents/user/architecture/260-arch.the-hub.md:63"
---

# Review: arch — initiative 260

**Verdict:** FAIL
**Model:** claude-opus-5-5

## Findings

### [FAIL] The resume has no claim, so several askers on one machine will each start a resume

"Work that belongs to a machine" says each piece of work is claimed before it starts, "a resume by its started mark … All three are compare-and-set today". It also says "The wake and the resume have such a limit today." Neither is true for the resume.

- **No claim exists.** `MARK_RESUME_STARTED` (`src/amoeba/store/sql.py:362-365`) is `UPDATE answers SET resume_started_at = ? WHERE seq = ? AND (resume_outcome IS NULL OR resume_outcome = 'refused')`. Nothing checks that `resume_started_at IS NULL`. So `mark_resume_started` returns True for every caller until the outcome is final.
- **The run check doesn't close the gap.** `resume.py:128-141` only guards with "the run is still at the pause". Two askers can both poll before either one resumes.
- **It was safe only because of how it's called today.** The one caller is `answer` in its own process. The design adds a caller on every `amoeba` call and every `amoeba-mcp` tick from every session on the machine. With three sessions open on the laptop, an answer from the desktop can start `squadron resume` up to three times for one pause.
- **No time limit exists either.** A started mark has no age after which the work is handed out again.
- **Refused resumes aren't placed.** The statement accepts `refused` as re-markable, so a refused resume counts as pending on every tick unless the design says otherwise. The document doesn't say whether a `refused` answer is pending work, or when it stops being retried.

What the document needs:
- name a real claim: a new compare-and-set on `resume_started_at IS NULL OR resume_started_at < hub_now - limit`
- name the limit's config key
- say what happens to a refused resume

The earlier review accepted "the resume relies on `mark_resume_started` being compare-and-set". That premise is wrong.

### [FAIL] Adoption has a window where the laptop splits into two stores, and the file copy can lose data

"How the build gets there" picks the mode by one thing: whether a client file exists. The walkthrough (step 1) runs `amoeba join` and then `amoeba adopt`. Stepping through that as the operator:

1. **After `join`, before `adopt`.** Every new `amoeba` call on the laptop goes to the hub, whose store is empty. Then:
   - `list` and `inbox` show nothing.
   - Every caller is `not_a_member`.
   - A Squadron pause hook that fires now fails, or it writes a row to the hub. If it writes a row, `adopt` step 1 ("Refuses unless the hub's store is empty") refuses from then on. No command clears that.
   - "Empty" isn't defined either. The hub already holds the owner (created at first start) and the laptop's machine (created by `invite`).
2. **Sessions that were already running.** An `amoeba-mcp` started before `join` may have picked its mode at startup. The document doesn't say whether the mode is read per call or per process. If per process:
   - It keeps writing the laptop store through its open connection.
   - After `adopt` renames the file, those writes land in the "dated backup" that the restore path says "was not changed".
   - A process that reopens the store hits `Store.open`, which creates the store if it is missing (`src/amoeba/store/store.py:78`). That is a fresh empty local store, a silent local fallback the design goals forbid.
3. **The copy can miss recent commits.** The store runs in WAL mode (`PRAGMA journal_mode=WAL`, `store.py:103`). Step 2's "Sends the store file" doesn't say whether the WAL is checkpointed first or the SQLite backup API is used. A raw file copy leaves out commits still in `-wal`. The row-count check is "against the file it was sent", so it passes on the short copy.

What the document needs:
- `adopt` refuses while any local session row is live
- the mode is decided per call
- the local store path is opened without auto-create once a client file exists
- the copy is made with the backup API, or after a checkpoint taken under an exclusive lock
- "empty" is defined as "no rows except the owner and invited machines"
- alternatively, `join` and `adopt` become one command so the window doesn't exist

### [FAIL] Restoring the hub on a new box ends with every client refusing to connect, and backups live on the disk they're meant to protect

Walkthrough step 11 ("The hub's disk is lost") and "A new address" (line 129) both say a restored hub needs no new invites. Stepping through it:

- **The backups go down with the disk.** "The hub" puts the store, its backups and the certificate and key all in the one state mount. If the disk is lost, so are the backups. The only copy left is the laptop's dated backup from adoption, which is missing everything since.
- **The certificate isn't in the backup.** The backups are copies of the store. The certificate and key are separate files, so a hub restored from a backup makes a new certificate at first start. Every client pinned the old fingerprint and "refuses any other". `join --address` changes only the address and keeps the fingerprint. No command accepts a new fingerprint. The only way out is `rm-machine` plus a new invite on every machine, and re-`add` in every repo, because `rm-machine` drops checkouts.
- **The undo path has the same shape of problem.** "Restore path" starts a hub on the laptop from the backup and then "join it". But the backup's single machine is the install machine, which has no token. A fresh `invite` creates a different machine, so every stored path and checkout belongs to a machine no client is. The document also doesn't say that undo throws away every record written to the hub since adoption.

What the document needs:
- the backup includes the certificate and key, or the key moves into the store
- a `backup_dir` that can point at another volume
- `adopt`'s restore names how the install machine gets a token, for example `hub invite --machine <existing>`

### [CONCERN] Work for a machine with no session open never starts, including the cross-machine wake

Only a client process can pick up pending work, and only an `amoeba` call or an `amoeba-mcp` tick on that machine asks for it. A wake exists for the case where nobody is live in the recipient. If the recipient's wakeable checkout is on the desktop, and no session in any repo is open there, nothing on the desktop ever asks. The wake waits until the request expires.

The same applies to a resume answered from another machine (step 3: "it resumes when the PM next opens a session there"). So across machines, waking works only if the target machine happens to have an unrelated live session.

The walkthrough calls this "one soft spot" and then reports "Dead ends found: none". Under the "Every state has an exit" and walkthrough rules, a feature that silently never runs is a dead end. It is also a regression: today `send` on one machine always reaches the wake.

A small fix that fits the design: `amoeba join` installs a per-user launchd or systemd timer that runs `amoeba tick` every `notify_poll_seconds`, or something coarser. If the PM doesn't want that, the document should say outright that cross-machine wakes and resumes need a session open on the target machine, and `send` should report it.

### [CONCERN] Automated multi-call commands have no rule for an "unknown" result partway through

"Repeats and failures" gives three outcomes. For "unknown" it says to "tell the caller to read the state (`inbox`, `list`)". That works for a person or an agent. It doesn't work for the callers that aren't one:

- the pause hook
- a detached `handle-pause`
- the resume
- the wake wrapper

These make chains of hub calls; Technical Considerations puts the pause path at about twenty transactions. During a hub restart, the hook can succeed at `claim_held`, launch the answering run, and then get "unknown" on the settle.

What the document needs: for each client-run command, what it does on "unknown" at each step (stop and leave the claim to age out, or retry on the next ask) and which existing dead-claim rule recovers it. One example: the held-question claim ages by `answering_wait_seconds`. The walkthrough's step 4 covers only a hook that fails before its first call.

### [CONCERN] Matching checkouts by remote address, and back-filling member names, are both under-specified

**Remote address.** "The hub records the repo's remote address with the member, and refuses a checkout whose remote differs." Three cases are missing:
- **Same repo, different URL.** One clone may use `git@github.com:o/r.git` and another `https://github.com/o/r`. Without a normalization rule, the same repo is refused.
- **No remote.** A repo with no remote, or with several, has no rule.
- **Migrated members.** Members carried over in the migration have no remote recorded. The document doesn't say whether the first second-machine `add` accepts any remote or refuses.

**Member names.** "One schema" says names "are filled from `cf` at the first call after the upgrade". Missing:
- which call fills them, and whether it fills all members or only the caller
- what happens when two local members share a Context Forge project name, which is the document's own step 10 case: the unique constraint can't be applied until the clash is settled
- whether every name is guaranteed filled before `adopt`. The hub has no `cf`, so a member left unnamed has no exit once it is there.

Each of these needs a stated rule.

### [CONCERN] The client file's copied timeouts go stale, so they are not "set in one place"

The invite copies `hub_connect_seconds`, `hub_read_seconds` and `hub_retry_seconds` into the client file "so they are still set in one place". After the copy, editing them in the hub's config changes nothing on clients already joined. The only re-fill path is a new invite, which means a new token.

Either:
- say each successful call returns the current values and the client rewrites its file, or
- treat them as client-local settings that the PM edits on each machine, and drop the "one place" claim.

### [CONCERN] Certificate pinning, and the backup timer, are left to the implementer and easy to get wrong

"The CLI calls the hub with a plain blocking call," and the client "records the fingerprint … and refuses any other". Neither stdlib `http.client`/`ssl` nor `httpx` (in the lock through `mcp`) offers fingerprint pinning. Each needs verification turned off (`CERT_NONE`) and a manual check of `getpeercert(binary_form=True)` after the handshake.

A naive version sends the request, token included, before comparing. That is exactly the leak the encryption is there to stop. The document should:
- name the client library
- require the fingerprint check to run in `connect()` before any bytes of the request are written
- require a test that a wrong certificate gets no token

Separately, the in-process backup timer runs inside the async server. A consistent copy of a large store (SQLite backup API or `VACUUM INTO`) must run in a worker thread, like other store work. Otherwise it breaks the "<1 ms sync in async" rule in `python.md`.

### [CONCERN] `rm-machine` doesn't end every state tied to that machine

"Leaving" closes open questions as `machine_removed`, drops checkouts and sessions, and lets wake rows age out. It doesn't cover:

- **Answered, not yet resumed.** An answer whose run is on the removed machine is already answered, so it is not an open question. It needs `mark_not_delivered` with a reason, or `list` shows "waiting for <removed machine>" forever.
- **Claimed held questions.** A held question that machine had claimed.
- **Live wakes.** A live wake in one of its checkouts blocks every other wake for that member until `wake_timeout_seconds` (`_has_live_wake`, `src/amoeba/store/wakes.py:94-100`). It should be ended at removal.

"Every wait ends … or when the machine is removed" (line 166) needs to name the write that ends each of these. Bringing a machine back (step 8) also needs `amoeba add` again in every repo, which the walkthrough doesn't mention.

### [NOTE] Store functions take `now` from the caller, which conflicts with "the hub's clock is the clock"

The store functions take `now` from the caller's `deps.clock()`. Examples are `mark_resume_started`, `claim_held` and `claim_wake`. `QuestionKey.paused_at` comes from the client's Squadron run file, on the client's clock.

The hub-call layer has to drop any client-supplied `now`. It also has to keep client-clock values like `paused_at` as identifiers only, never comparing them with hub times in sweeps (`question_sweep.py:248` mixes answer timestamps). This is worth one line in the principle, so the slice that moves the pause path checks it.

### Run Digest

- Response length: 13837 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 143
- Effort: high
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 1123003 / 1000346 / 122635 / 16109 / not computed
- Duration: 182.6 s
- Cost: $1.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Resolution

Second review round. Each finding was checked against the code and the document before acting. All ten hold. Worked into `260-arch.the-hub.md` 20261120. The first round's review and resolution are in git history (`588353bc`).

- F001 (valid, fixed): confirmed in `store/sql.py`: `MARK_RESUME_STARTED` does not check that the mark is empty, so it is not a claim. The resume gets a real claim, taken only when the mark is empty or older than `resume_bound_seconds` with no outcome. A refused resume is not pending work and is retried only as today.
- F002 (valid, fixed): adoption is one command, `amoeba adopt <join line>`, with the client file written last, so there is no time between joining and adopting. It refuses while a local session is live, holds the local store's write lock from the copy to the switch, copies with SQLite's backup call, and defines an empty hub. The mode is decided on every call, and a machine with a client file never opens or creates a local store.
- F003 (valid, fixed): a backup holds the store, the certificate and the key, and goes to a required `backup_dir` meant for another disk. A hub started from a backup is the same hub, so clients connect unchanged. `hub invite` for an existing machine issues a new token. Undo is moving the hub to the laptop from a current backup, which loses nothing; the adoption backup is only the fallback, and the document says what it lacks.
- F004 (valid, limit stated): no background poller is installed on clients. The document states that work for another machine needs something of Amoeba's running there, `send` and `answer` report the machine being waited on, and the walkthrough lists it as a limit. A same-machine `send` still starts the wake in the same call. Waking with no machine awake is 300's runner on the hub.
- F005 (valid, fixed): a command that runs by itself stops on unknown, and its claim's time limit hands the work out again. A table names each claim and its limit.
- F006 (valid, fixed): `origin` is compared after reducing to host and path; a repo with no `origin` has one checkout only. Existing members are named, and their `origin` recorded, by the first call after the upgrade, for all members at once, with fixed answers for an unknown project and a name clash. Adoption refuses if any member is unnamed.
- F007 (valid, fixed): the three network settings are each machine's own, written at join and edited there. The "one place" claim is dropped.
- F008 (valid, fixed): the client saves the hub's certificate at join and trusts only it, so the check is part of setting up the connection. A test proves a wrong certificate gets no token. The backup copy runs in a worker thread.
- F009 (valid in part, fixed): the sweep's meaning of "open" already includes an answer not yet resumed, so that case was covered, but the document did not say so. "Leaving" now lists each write, including ending a live wake, and says a returning machine needs `add` in each repo.
- F010 (valid, fixed): the clock principle says a hub call never takes the time from the client and a client-file time is only an identifier. The local-work slice has a third stated check for it.
