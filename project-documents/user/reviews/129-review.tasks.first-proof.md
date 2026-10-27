---
docType: review
layer: project
reviewType: tasks
slice: first-proof
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/129-tasks.first-proof.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261027
dateUpdated: 20261027
reviewedSha: 7a7bd6005b6440fdcfb04cb8feed0af7744fa202
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 104037
cachedTokens: 11176
cacheWriteTokens: 92857
completionTokens: 5750
durationSeconds: 49.4
costUsd: 0.430858
costBasis: provider
runId: run-20261027-p5-85a72bbf
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are covered by tasks"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:71-333"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:96-146"
  - id: F003
    severity: concern
    category: consistency
    summary: "`--node` versus the LLD's `--node-id` will trip the final criteria check"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:62"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Several tasks are finer-grained than the slice needs"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:199-214"
  - id: F005
    severity: note
    category: commit-checkpoints
    summary: "Task 3.3 has one commit however many stops occur"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:173-185"
  - id: F006
    severity: note
    category: sequencing
    summary: "Task 1.2 creates the write-up even when the proof unit is missing"
    location: "project-documents/user/tasks/129-tasks.first-proof.md:81-90"
---

# Review: tasks — slice 129

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are covered by tasks

| LLD success criterion | Task |
| --- | --- |
| Four steps `done`, PM merges | 3.5 |
| No hand-run commands; D4 log agrees with store evidence | 3.3, 3.6 |
| `recomputes: yes` on all rows | 3.6 |
| Still `yes` after edits and restart | 5.3 |
| SIGKILL with P6 in flight | 3.4 |
| Every stop classified, one proposal per wrong stop | 4.1 |
| `inspect resolutions` columns, unacknowledged case, schema-mismatch exit | 2.3, 2.4 |
| D7 rule test | 5.2 |
| Full validation | 7.1 |
| Guide, store contract, substrate guide, README, CHANGELOG | 2.5, 6.1–6.3, 6.6 |
| 130/131 entries and Future Work | 6.4 |
| Issues #12, #13, #16 | 6.5 and the `Closes #16` in 2.4 |

Every task traces to the LLD. Nothing is scope creep.

### [PASS] Sequencing and test-with pattern

- Each implementation task is followed immediately by its test task: 2.1→2.2, 2.3→2.4 and 5.1→5.2→5.3.
- `inspect resolutions` is built before the proof (2.5 before 3.1), because Task 3.3 uses it.
- Commits fall at the end of each section or sub-group, and are not batched at the end.
- Dependencies are acyclic.
- Both D9 branches have a path: the defect path and the crash-miss path with a second unit.

### [CONCERN] `--node` versus the LLD's `--node-id` will trip the final criteria check

- The task file deliberately uses `--node`, the shared spelling in `inspection/listing.py`.
- The LLD still says `--node-id` in the API Contracts section (`project-documents/user/slices/129-slice.first-proof.md:269`) and in the Technical Requirements (`:308`).
- Task 7.1 (`:330`) checks the LLD's criteria one by one, and says to mark any unmet criterion `BLOCKED:`. The `--node-id` criterion would be flagged as unmet, or the reviewer would have to rediscover the reason.
- Fix: add a line to 7.1 saying `--node` satisfies the `--node-id` criterion, or amend the LLD wording in Task 2.5.

### [CONCERN] Several tasks are finer-grained than the slice needs

The slice is rated 3/5 and is mostly an operation, yet the file has about 27 tasks, many rated 1/5. Three merges would help:
- **Task 3.5** has no commit and no artifact of its own. Its three checks are the state that 3.6's audit and the exports record. Fold them into the head of 3.6, and keep the PM-merge note.
- **Tasks 6.4 and 6.5** (`:304-314`) are both small write-up-to-plan or issue updates that depend only on 4.2. Merge them into one "propagate the write-up's proposals" task. Task 6.5 has no commit of its own.
- **Tasks 3.1 and 3.2** are both 1/5 and form one setup-and-drive unit. Merging them leaves one `review:` commit.

### [NOTE] Task 3.3 has one commit however many stops occur

- Task 3.3 is an open-ended loop over an unknown number of stops, possibly across hours of wall-clock time.
- It commits once, at the end. The D4 command log and the draft stop rows exist only in an uncommitted write-up until then.
- The supervisor store holds the evidence either way. Still, consider a line allowing a `review:` commit of the write-up after each batch of stops, so the log cannot be lost.

### [NOTE] Task 1.2 creates the write-up even when the proof unit is missing

- The write-up header must record the D1 choice. If the proof unit is unnamed, Task 1.2 writes `BLOCKED:` and the header cannot be written.
- State whether the file is still created, with a placeholder header, or whether the creation and commit wait for the PM.

### Run Digest

- Response length: 4269 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 104037 / 11176 / 92857 / 5750 / not computed
- Duration: 49.4 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
