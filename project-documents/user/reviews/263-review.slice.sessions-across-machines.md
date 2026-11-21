---
docType: review
layer: project
reviewType: slice
slice: sessions-across-machines
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/263-slice.sessions-across-machines.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: 0eb93d7881014ef96192a4a077e007f633c6e9a2
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 2044189
cachedTokens: 1823275
cacheWriteTokens: 220890
completionTokens: 88290
durationSeconds: 398.8
costUsd: 0.520012
costBasis: provider
runId: run-20261120-slices-plan-bec270e7
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: concern
    category: architecture-boundary
    summary: "`amoeba leave` returns a joined session to the local store, which the architecture rules out"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:157"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Claim-failure logging contradicts D4"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:281"
  - id: F003
    severity: concern
    category: no-deferral
    summary: "A directory that becomes a project has no exit except reconnecting"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:211"
  - id: F004
    severity: concern
    category: proportionality
    summary: "The design is about 40 times the plan entry, with the same behaviors stated in several sections"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md#success-criteria"
  - id: F005
    severity: concern
    category: fact-verification
    summary: "The source date for the timeouts behind the 300-second deadline is after today"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:82"
  - id: F006
    severity: note
    category: consistency
    summary: "Some departures from 260 and 262 are not in the departure tables"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:306"
  - id: F007
    severity: note
    category: parent-alignment
    summary: "The architecture narrows runs to questions, and the plan asks for runs"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:466"
  - id: F008
    severity: note
    category: integration
    summary: "Amendments to 262 are listed here but not applied there, and all three designs have open FAIL reviews"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md#amendments-to-260-and-262"
  - id: F009
    severity: note
    category: contract
    summary: "The reply's entry fields are not named, so \"no message text is in the reply\" cannot be checked"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:187"
  - id: F010
    severity: note
    category: operator-walkthrough
    summary: "A run answered from a machine with no open session has no named command to start it"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:698"
  - id: F011
    severity: note
    category: operator-walkthrough
    summary: "The Codex timeout step is a value change, and an abandoned call's outcome is left as \"may\""
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:688"
  - id: F012
    severity: pass
    category: integration
    summary: "241 integration points exist and match the stated values"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:89"
  - id: F013
    severity: pass
    category: consistency
    summary: "The claim-time departure is recorded where the slice says"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:93"
  - id: F014
    severity: pass
    category: arithmetic
    summary: "Deadline arithmetic is correct"
    location: "project-documents/user/slices/263-slice.sessions-across-machines.md:336"
---

# Review: slice — slice 263

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] `amoeba leave` returns a joined session to the local store, which the architecture rules out

D1 says a session open across `amoeba leave` "goes back to the local store." Success criterion 552 and walkthrough line 701 depend on this. The architecture says "There is no hub-less mode and no local store to fall back to. ... Nothing here is built for it" (260-arch, line 60). Its Machines section says a client with no client file "fails and says to run `amoeba join`" (line 140). The architecture never defines `leave`. It appears only in the 260 slice design (lines 232–240), where it is the exit from the joined state. So 263 adds a runtime path back to local-store mode that the parent does not describe. It also does not say what a session does after `leave` once 264 deletes `LocalSteps` (success criterion 577). The 260 guard that refuses to recreate a missing local store (260 slice, line 228) covers the data risk. The gap is a contract question. The architecture should name `leave` and its limit, or 263 should drop the local-store clause and state the post-264 behavior.

### [CONCERN] Claim-failure logging contradicts D4

D4 (line 220) logs one WARNING when a run of tick failures starts and one INFO on recovery. D7 (line 281) says claim failures "are logged as D4 logs a tick's: one ERROR when a run of failures starts." The sentence cites D4 but uses a different level. Success criterion 549 repeats ERROR. For the same hub outage, the operator would then see WARNING for ticks and ERROR for claims. Pick one level and state it once.

### [CONCERN] A directory that becomes a project has no exit except reconnecting

D3 keeps a "not a project" answer for the life of the process. A directory added with `amoeba add` after its session started gets no presence until the server reconnects (also success criterion 548 and walkthrough line 693). The stated reason is cost: asking `cf` every tick "for the whole life of every session opened outside a project." That cost goes away if `cf` is asked less often, for example once a minute, bounded by the existing `CF_GET_TIMEOUT_SECONDS`. The design already treats "a project added after the session started gets presence at the next tick" as wanted behavior (line 207). This case is the same behavior with one more manual step. Under the no-deferral rule, that is a deferral to an operator action. Either build the slower re-ask, or delete the claim and its success criterion and say presence needs a new session.

### [CONCERN] The design is about 40 times the plan entry, with the same behaviors stated in several sections

The plan entry for this slice (260-slices, lines 121–136) is about 16 lines. This document runs to about 700 lines, with 15 decisions and about 36 success criteria. The same behaviors also appear in the decisions, both tables, the Verification walkthrough and the Operator walkthrough. Cuts that keep every requirement:
- Line 79: the `cf` and `sq` version facts. The slice says "This slice changes no call to either."
- Departures (lines 455–468) and Amendments (474–485) both describe the deadline change (462, 478, 484), the claim figure (93, 482, 484) and the after-step (463, 476). Put each change in one table and cross-reference it.
- Verification walkthrough items 4–8 and the Operator walkthrough's normal-path and runs items restate success criteria 536–562. Have the walkthrough name the criterion each step exercises.
- Risk Assessment (647–659) restates D4 and D15.

Keep D11's runs document. The plan asks for runs (260-slices, line 125), so it is not a cut. The Operator walkthrough and the tables are required by the design rules and the repo conventions.

### [CONCERN] The source date for the timeouts behind the 300-second deadline is after today

Line 82 says the Claude Code MCP page was "read 20261121." The frontmatter has `dateUpdated: 20261121` (line 13). Today is 2026-11-20, so the read date cannot be right. The claim that none of the three client timeouts cuts a call off inside 300 seconds underpins D9's deadline and the Codex step. Re-run the fetch and record its actual date.

### [NOTE] Some departures from 260 and 262 are not in the departure tables

- `session_end` makes one attempt and never retries (line 306). The architecture's retry rule says a client that gets no reply repeats the call (260-arch, line 126), and only the tick is exempt (line 132). The departure at line 464 covers result-keeping, not retry.
- MCP clean-up moves to the tick (line 274). The architecture says clean-up runs "from any call" (260-arch, line 177), and 262's departures row says the same (262, line 556). The Amendments table covers the after-step but not the clean-up trigger. Ticks run for every open session, so the effect is small, but the design should say so.

### [NOTE] The architecture narrows runs to questions, and the plan asks for runs

The architecture says "Questions from another machine's runs show as last reported" (260-arch, line 207). The plan says "Runs on other machines show in `list` and `status` as last reported, with the machine named" (260-slices, line 125). The slice follows the plan and records the departure at line 466, which is correct. The architecture should be aligned so the parent does not contradict its own slice plan.

### [NOTE] Amendments to 262 are listed here but not applied there, and all three designs have open FAIL reviews

262 line 202 still says `steps_for(layout)` picks a way "when a command starts" and the command keeps it. 263 needs `steps_for` to take the times and the session id, called on every tick (line 477). It also needs 262's after-step not to run on the MCP door (line 476). Two parts are already in place: 262 line 300 now reads 216.5, and the claim-time departure is recorded in 262's table (line 555), as line 93 says. Apply the rest in 262 with this revision, or the two designs disagree about one signature. Line 73 says the latest reviews of 260, 261 and 262 are all FAIL, so the interfaces under "Interfaces Required" may move too.

### [NOTE] The reply's entry fields are not named, so "no message text is in the reply" cannot be checked

D2's reply lists `entries` without their fields. The channel event is built from them (line 193), and the Special Considerations say "No message text is in the reply" (line 679). The architecture treats message text as data written by other repos' agents, handled as in 240 (260-arch, line 288). Name the entry fields, such as sequence number, kind and counterpart member id, so the no-text claim can be tested.

### [NOTE] A run answered from a machine with no open session has no named command to start it

The walkthrough says the run "resumes on its own machine within a few seconds if any session is open there." With no session open, the run waits. The exit exists: any `amoeba` call on that machine claims the work (260-arch, line 197), and `rm-machine` ends it (line 273). The walkthrough names neither. Otherwise, walking the operator path (start, normal path, each failure, end state, undo) found no other dead end.

### [NOTE] The Codex timeout step is a value change, and an abandoned call's outcome is left as "may"

A Codex user must raise `tool_timeout_sec` to at least 305 (line 688), from 185. The architecture says set-up is "one command per machine" (260-arch, line 39). This is a value change to a setting the install doc already asks Codex users to raise, so it is not a new kind of step. The walkthrough should say what happens when the client cuts off a call that is still running: the design should state whether the in-call resume and its outcome record still finish. Line 689 says "may"; the design should say "does."

### [PASS] 241 integration points exist and match the stated values

The `amoeba.mcp` modules named as built from 241 exist, as do `store.push_reads` and the three config keys. The constants the design cites match the code: `CHANNEL_EVENT_MAX_ENTRIES` 10, `BUSY_TIMEOUT_SECONDS` 5, `CF_GET_TIMEOUT_SECONDS` 30, `MCP_CALL_DEADLINE_SECONDS` 180. The client file is read on every call (260 slice, line 154), so the walkthrough's "no restart" claim holds.

### [PASS] The claim-time departure is recorded where the slice says

262's departures table records the two-call claim rule and its 86-second figure against the architecture's 30-second retry alone (262, line 555), as line 93 says. 262 line 300 now reads 216.5, which matches this slice.

### [PASS] Deadline arithmetic is correct

135.5 = 60 + 0.5 + 60 + 10 + 5. 216.5 = 135.5 − 5 + 86. The limits are 143.5 = 300 − 156.5 and 209.5 = 300 − 90.5. The load test's 50 sessions at 0.5 s equal 500 sessions at 5 s, both 100 ticks per second.

### Run Digest

- Response length: 12576 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 2044189 / 1823275 / 220890 / 88290 / not computed
- Duration: 398.8 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14

## Resolution

Resolved 20261120 in `user/slices/263-slice.sessions-across-machines.md`. Nothing was deferred and no issue was filed.

- [concern] `amoeba leave` returns a joined session to the local store: changed. D1 no longer gives the tick a rule for `leave`. A session with no client file does what any call on that machine does: the local way until 264, and after 264 a failed tick with the join message, skipped until the machine joins again. The `leave` clause is gone from the criterion and the walkthrough.
- [concern] Claim-failure logging contradicts D4: changed. D7 logs claim failures exactly as D4 logs ticks, WARNING then INFO, and the criterion says WARNING.
- [concern] A directory that becomes a project has no exit except reconnecting: changed. A "not a project" answer is asked again once it is `CF_REASK_SECONDS` (60) old, so presence starts within about a minute with no reconnect. D3, the departures row, the criterion, the integration line and the walkthrough are updated, and the limit is removed from "Dead ends".
- [concern] The design is about 40 times the plan entry: changed in part. Cut the `cf` and `sq` version fact, merged the three deadline rows of the Amendments table into one and cross-referenced it from the departures row, replaced verification steps 4 to 8 with one step that names the criterion each part shows, and cut the mitigation list to references. The decisions, both tables and the operator walkthrough stay, as the finding says they should.
- [concern] The source date for the timeouts is after today: changed. The fetch was made in this session on 20261120; the fact now says so, and the frontmatter `dateUpdated` is 20261120. The fetch was not run again, because only the recorded date was wrong.
- [note] Some departures are not in the departure tables: changed. Added rows for `session_end` making one attempt and for the file clean-up running from the tick on the MCP door.
- [note] The architecture narrows runs to questions: changed. `260-arch.the-hub.md`, "Sessions across machines", now says runs and their questions show as last reported, and the departures row is removed.
- [note] Amendments to 262 are listed here but not applied there: changed. 262 now states that `steps_for` takes the times and a session id and is called per tick by 263, that `invoke` skips the after-step on the MCP door, and that the hub's deadline check uses `resume_claim_seconds`. The 260 rows wait for 260's next revision, which the Amendments section says. The open FAIL reviews of 260 to 262 are unchanged; the design's update-first rule covers them.
- [note] The reply's entry fields are not named: changed. D2 names them (`seq`, `event`, `kind`, `counterparty`), forbids others in the model, and adds a marker-string test.
- [note] A run answered from a machine with no open session has no named command: changed. The walkthrough names `amoeba list` on that machine, and `amoeba hub rm-machine` when the machine is gone.
- [note] The Codex timeout step, and "may": changed. The walkthrough now says the work does finish when the client cuts the call off, because the worker thread is abandoned and not stopped. The Codex step stays as a value change.
- [pass] 241 integration points exist and match the stated values: no change.
- [pass] The claim-time departure is recorded where the slice says: no change.
- [pass] Deadline arithmetic is correct: no change.

## Full-text review, 20261121

The whole design was read in order (678 lines), with the architecture, the slice plan and CLAUDE.md in full, the 260 and 262 designs in full, and the cited parts of 261 and 264. Claims about existing code were checked in `src/amoeba/`, `scripts/` and `tests/`, and migration 014's statements were run against a throwaway SQLite database. The earlier review above was not read until the findings were written. Counts: 0 important, 11 minor, 1 unverified, and 2 behaviors that were surprising but had exits. All were resolved 20261121 in `user/slices/263-slice.sessions-across-machines.md`, after re-reading 260 at commit `9ee28aa5`. Nothing was deferred, no issue was filed, and no finding ended as "no change".

- [minor 1] The test "every `OperationName` is in `SERVED_OPERATIONS`" could not pass, because `handle_pause` is client-run and never served: changed. D14 and the criterion now say every name but `handle_pause`, and that `handle_pause` is not in the list.
- [minor 2] The two session timing checks no longer kept a healthy session inside `session_stale_seconds`: changed. D5 adds a third check, `session_stale_seconds` at least `session_heartbeat_seconds + 2 * notify_poll_seconds`, tested against the example config (passes), the live config (passes) and heartbeat 5, poll 5, stale 10 (refused). It is in Component Structure, D14's config-contract line, D15, the departures table, a criterion and the walkthrough.
- [minor 3] The resource handlers were "unchanged" although the member can now appear after the first tick: changed. D10 has a table for the four handlers, and `resources/list` offers the resource in every session. D3, the departures table, the Migration Plan's test edits, a criterion and the walkthrough follow.
- [minor 4] `session_end` had no request model, and three of the four header values had no path to `client.call`: changed. D2 gives `session_end` its one field and empty reply. D6 says the four values travel as one session identity through `steps_for` and `DoorSteps`.
- [minor 5] `DeadlineError` and the client-name pattern lived where the hub may not import: changed. `DeadlineError` moves to `operations/errors.py` and joins 260's `OPERATION_ERRORS` (D9). The pattern and the session id's shape are constants in `wire.protocol` (D6). Both are in Component Structure and the amendments table.
- [minor 6] A machine read as behind or not by whoever called last, and a client ahead of the hub was told to upgrade: changed. D6: the touch for the two session calls sets `last_called_at` only. A door version above the hub's is listed as `ahead of the hub`, with the hub named as the one to upgrade (D6, D12). State Management, the amendments and departures tables, two criteria and the walkthrough follow.
- [minor 7] The `hub machines` display had no format or criterion, and `runs_problem` had no text: changed. D12 gives both, with a row in Component Structure, the amendments table, D14's cli-contract line and a criterion.
- [minor 8] The longest other tool was given as 176 seconds: changed. D9 has a table of its six parts, which add to 236.
- [minor 9] The by-hand check "no `resume-run` log under `logs/resume/`" could not hold: changed. The Verification Walkthrough checks that no `resume-run` process runs, and says the resume's logs are there as for any resume.
- [minor 10] Three departures rows cited plan text the plan does not have, and the amendments preamble was stale: changed. One row now cites the architecture, one cites 241 D3, one states the real departure (behind sessions are left out of the presence check), and the preamble is reworded.
- [minor 11] The new presence log line needed a fifth test edit and dropped the protocol version: changed. The line keeps today's text with the machine added at its end, so no test changes for it. The Migration Plan now lists six kinds of edit, the two new ones being the resource list (finding 3) and `tests/test_wiring_release.py::test_the_mcp_door_starts_the_ended_held_question_too`.
- [unverified] The three Claude Code timeout facts: settled in part. The installed 2.1.325 program's text confirms the three settings, the 30-minute idle limit for a stdio server, the 2-minute move to the background, and that 0 turns the move off. It does not show the unset value of `MCP_TOOL_TIMEOUT`, or what the agent is given when a call is moved to the background. Step 1 of the Development Approach is now a live test with a 220-second tool call, with the handling of each of its three results.
- [surprising] After `amoeba leave`, an open session's tick takes the local way and can make an empty store: stated. D1 says what happens, that `join --set-aside-local` ends it, and why it is accepted before 264. There is a criterion and a walkthrough line.
- [surprising] A tick in flight at exit can write the row again after `session_end`: stated. D8 gives its end: it goes stale after `session_stale_seconds` and the next refresh deletes it. State Management, a criterion and the walkthrough follow.
- Also brought in line: the after-step change on the MCP door is stated as this slice's own in D7 and the amendments table; 260 citations follow commit `9ee28aa5` (`rm-machine` and `hub machines` are 260 D13, `OPERATION_ERRORS` is 260 D8, a hub home refuses `amoeba-mcp` at start in D8).
