---
docType: review
layer: project
reviewType: arch
slice: program-tool
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/architecture/220-arch.program-tool.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 84bf5596fbea144a9a28e1d611ec317d643d5ca5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
turns: 11
promptTokens: 690784
cachedTokens: 587653
cacheWriteTokens: 103115
completionTokens: 11757
durationSeconds: 132.7
costUsd: 1.1785
costBasis: provider
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "\"The resume fails later … the run is still at that pause\" is wrong for failures after the resume starts"
    location: "project-documents/user/architecture/220-arch.program-tool.md:128-136"
  - id: F002
    severity: concern
    category: feasibility
    summary: "The answer screen is a substring match, but the policy it enforces is about meaning"
    location: "project-documents/user/architecture/220-arch.program-tool.md#what-an-answer-may-authorize"
  - id: F003
    severity: concern
    category: consistency
    summary: "\"Reporting the same commit twice changes nothing\" drops the release report for a commit already reported at merge"
    location: "project-documents/user/architecture/220-arch.program-tool.md:94-101"
  - id: F004
    severity: concern
    category: completeness
    summary: "One cursor per member treats \"seen\" as \"accounted for\", and worktrees share it"
    location: "project-documents/user/architecture/220-arch.program-tool.md:96"
  - id: F005
    severity: concern
    category: dependencies
    summary: "Whether the answering run handles its own pause depends on where the scratch directory is"
    location: "project-documents/user/architecture/220-arch.program-tool.md:119-122"
  - id: F006
    severity: concern
    category: completeness
    summary: "\"A claim whose recorded process has died\" doesn't say how death is detected, and a retake leaves an orphaned answering run"
    location: "project-documents/user/architecture/220-arch.program-tool.md:169"
  - id: F007
    severity: note
    category: consistency
    summary: "The frontmatter depends on documents this design says it replaces"
    location: "project-documents/user/architecture/220-arch.program-tool.md:9"
  - id: F008
    severity: note
    category: technology
    summary: "Some details of the MCP and store mechanics are unstated"
    location: "project-documents/user/architecture/220-arch.program-tool.md:174"
  - id: F009
    severity: note
    category: completeness
    summary: "Smaller things left undefined"
    location: "unverified"
  - id: F010
    severity: note
    category: antipattern
    summary: "Per-member authorization settings could wait"
    location: "project-documents/user/architecture/220-arch.program-tool.md:140"
---

# Review: arch — initiative 220

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] "The resume fails later … the run is still at that pause" is wrong for failures after the resume starts

The resume section promises that if "the resume fails later, `status` still shows it: the answer is recorded and the run is still at that pause. Calling `handle_pause` again resumes with the recorded answer." That only holds when the resume never took the run lock (a refusal, or a process that died before spawning). Once `sq run --resume` takes the lock, the run leaves the pause. A failure after that point is a `failed` run at some later step, not the original pause.

Then step 1's checkpoint comparison sees that the run "has moved". It records the answer as **not delivered** and blames "someone else", when the answer was in fact delivered and the run failed. `PIPELINES.md:388` says a `FAILED` step resumes like a paused one, so nothing in Squadron stops a later caller from resuming the failed run again with no answer attached.

The record needs a third outcome besides "resumed" and "not delivered": *delivered, run then failed*. `status` needs to tell the three apart. That means saying which run-file fields mark "left that pause": the status changing, `paused_at` being cleared, or both. The facts list doesn't establish this. Step 3's "wait briefly for the run to leave that pause" relies on the same unstated field.

### [CONCERN] The answer screen is a substring match, but the policy it enforces is about meaning

"What an answer may authorize" states a semantic policy: an answer may not authorize "a push, a merge to the main branch, a release, a destructive database statement or a policy change". Technical Considerations says the enforcement "is a substring match". These don't fit together:

- **False positives:** "merge the two helpers into one", "release the lock before writing" and "drop the unused column from the DTO" all match terms on the list. Each sends a harmless answer to the PM, which pushes down the exact number the scenario A test measures.
- **False negatives:** "ship it", "go ahead and tag 1.4" and "fold it into main" match nothing.
- **Per-member settings:** "a member can loosen or tighten that list, so 'yes, merge it' can be allowed" assumes the list holds concepts, not strings. It's unclear what a member actually edits.

Either state the screen honestly as a coarse keyword tripwire, accept its false-positive cost and drop the per-member "authorize" wording, or make the independent check step responsible for the semantic policy and keep the substring screen as a backstop. Today the document implies the screen enforces the policy.

### [CONCERN] "Reporting the same commit twice changes nothing" drops the release report for a commit already reported at merge

Decision 3 makes the provider report at merge (no version) for `from_source` consumers and at release (with a version) for `from_release` consumers. The operations table makes `report_release` idempotent on the commit. When a release is tagged on the commit that was already reported at merge (no separate bump commit), the release report is a no-op. `from_release` consumers then never see the release, because they only see reports that carry a version.

The idempotency key needs to include the version, or a second report of the same commit needs to be able to *add* a version to the existing report. That second case also needs a defined effect on `from_source` consumers who already saw the report.

### [CONCERN] One cursor per member treats "seen" as "accounted for", and worktrees share it

Lines 105 and 110 are also affected. `changes` returns "what this member's dependencies reported since its marker", and the design agent "marks it read once its design accounts for it". A single forward-moving marker per member breaks in three ways:

- **Irrelevant now, relevant later:** a change that doesn't matter to this slice but matters to the next one. If the agent marks it read, the next slice never sees it. If it doesn't, every later design sees it again, along with everything behind it.
- **Reports arriving mid-design:** if `mark_read` moves the marker to "now", it skips reports that came in after `changes` was called. It must take the last report id the caller actually saw.
- **Parallel worktrees:** "all worktrees of a repo are one member". Two slices designed at once in different worktrees share one marker, so whichever finishes first hides the change from the other. The first review raised this (F009), and the revision doesn't address it.

Scenario B is gated on scenario A, so this doesn't block. It should be settled before the program dependencies slice. The simplest fix may be no cursor at all for `changes`: return reports since the consumer's last merged design, or since a time, and let the agent judge.

### [CONCERN] Whether the answering run handles its own pause depends on where the scratch directory is

Step 2 says the answering run's own pause is ignored "since it runs from a scratch directory" that resolves to no program. That safety depends on two things the document never pins down:

- where the scratch directory is
- how Context Forge resolves it (it may walk up parent directories)

Amoeba is itself a natural member of the Squadron / Context Forge / ai-project-guide program. If the scratch directory ever ends up under a member checkout, or under a directory Context Forge maps to a project, a paused answering run starts `handle_pause` on itself. That could recurse and spend money unattended.

Decision 1 already provides a per-run opt-out flag. The answering run should always pass it, so the guard is explicit and doesn't depend on directory layout. Step 5 already treats a paused answering run as "waits on the PM", which is consistent with this.

### [CONCERN] "A claim whose recorded process has died" doesn't say how death is detected, and a retake leaves an orphaned answering run

Step 3 records "the checkout and the process". A bare pid is unsafe because of pid reuse. Liveness needs pid plus process start time, or a lease with a heartbeat. The document also says "the first recorded answer wins", but when `handle_pause` dies, nothing is left to collect its answering run's output. That child's answer is never recorded. The retake doesn't race it, it just spends twice and throws the first result away.

Either record the answering run's own run id at claim time, so a retake can read that run's result (or wait for it) before starting a second, or state plainly that a retake always spends again. This is the same gap the first review raised (F003), narrowed but not closed.

### [NOTE] The frontmatter depends on documents this design says it replaces

`dependencies: [100-arch…, 120-arch…, 140-arch…]`, but Related Work (line 194) says this document replaces `100-arch`, `120-arch` and `180-arch` for new work. Only `140-arch` (the answering pipeline that is kept) is a real dependency. Listing replaced documents as dependencies points readers and tooling at the wrong context.

### [NOTE] Some details of the MCP and store mechanics are unstated

- **MCP library:** `pyproject.toml` has no MCP library. Line 174 leaves fitting the synchronous store into the MCP library's async model to slice design. That's acceptable for a per-session stdio server, but the first MCP slice should name the library. It should also say whether short operations run in a worker thread, to satisfy the Python rule against blocking work in async code.
- **Store location:** "one store at a fixed per-user location, with no flags" (line 148) still needs an override for tests, at least an environment variable read in one config place, so test runs never touch the real store.

### [NOTE] Smaller things left undefined

These are spread across the operations table, Technical Considerations and the question record, so they have no single location.

- **Answer limit:** it's unclear whether PM answers count toward the per-run limit.
- **PM marker:** it's unclear whether the PM's `decisions` marker is kept per program or globally.
- **Prompt-only runs:** the document says these "are outside `handle_pause`" (line 175) without saying how `handle_pause` recognizes them if they still produce paused run files that fire the hook.

Each is one sentence to settle in slice design.

### [NOTE] Per-member authorization settings could wait

Apart from the screen issue above, the design is proportionate. The one piece no scenario needs yet is letting each member loosen or tighten what answers may authorize. The user-level default list covers scenario A's first proof. Per-member overrides can be added when a repo actually needs "yes, merge it".

### Run Digest

- Response length: 10537 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 690784 / 587653 / 103115 / 11757 / not computed
- Duration: 132.7 s
- Cost: $1.18 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
