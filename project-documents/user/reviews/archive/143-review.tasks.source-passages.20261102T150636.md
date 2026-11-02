---
docType: review
layer: project
reviewType: tasks
slice: source-passages
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/143-tasks.source-passages.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: 2b26a68cbc35da0e66869c2cc486fa28a86110a0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 199958
cachedTokens: 99782
cacheWriteTokens: 100170
completionTokens: 4724
durationSeconds: 46.5
costUsd: 0.458749
costBasis: provider
runId: run-20261102-p5-b4493a64
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 4.3 calls `render_passages` before Task 4.4 defines it"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:129-139"
  - id: F002
    severity: concern
    category: scope-and-sequencing
    summary: "Duplicate-path handling happens after the files are read"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:130"
  - id: F003
    severity: concern
    category: ambiguity
    summary: "The rules-fixture directory is left to the implementer"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:103"
  - id: F004
    severity: note
    category: scope
    summary: "Task 7.3 adds a test that no success criterion requires"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:233"
  - id: F005
    severity: note
    category: clarity
    summary: "`match_rules_entry` leaves the entry-versus-listing comparison unstated"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:120"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Success criteria are covered"
    location: "project-documents/user/tasks/143-tasks.source-passages.md"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Sequencing, test-with pattern and commit markers"
    location: "project-documents/user/tasks/143-tasks.source-passages.md:87-255"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Proportionality"
    location: "project-documents/user/tasks/143-tasks.source-passages.md"
---

# Review: tasks — slice 143

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 4.3 calls `render_passages` before Task 4.4 defines it

Task 4.3 trims PM answers by measuring `len(render_passages(...))`, and its success line is "typecheck passes". `render_passages` is only written in Task 4.4. Task 4.3 cannot typecheck or run as written, which breaks the file's "each task leaves the suite passing" rule. Swap the order so rendering comes first, or merge 4.3 and 4.4 into one task. The two tasks also share the same combined test task, 4.5.

### [CONCERN] Duplicate-path handling happens after the files are read

Task 4.3 removes a path that appears twice inside `assemble`, which runs after every file has been read. Task 6.2 selects and reads files without removing duplicates. A file matched by two entries, or by an entry and a plan row, would be read twice. That costs two extra git calls and breaks the `2 + L + 2F` call-count formula. It would also read text that only counts against `max_chars` once. Slice D10 only says the file "appears once, at its first position", so the fix is a task-level choice. Have 6.2 remove duplicates at selection, before any reads. Then either keep 4.3's check as a safeguard or drop it, and add a test of the read count for a duplicated path.

### [CONCERN] The rules-fixture directory is left to the implementer

Task 3.3 says to take `python.md` and `git.md` from `.claude/rules/` or the guide's `rules/` directory, "whichever exists". The slice's example config uses `project-documents/ai-project-guide/project-guides/rules/*.md`, and `git.md` does exist there. Name that directory in the task so the frozen fixtures and the `rules_paths` test config stay consistent. Keep the "stop and report if a name is missing" instruction.

### [NOTE] Task 7.3 adds a test that no success criterion requires

The "rule committed between two calls appears in the second call" test traces to the State Management section of the slice, not to a Success Criteria item. It is cheap and covers real behaviour, so keep it, but it is the only test with no criterion behind it.

### [NOTE] `match_rules_entry` leaves the entry-versus-listing comparison unstated

Task 4.1 does not say that `match_rules_entry` compares only the entry's last path segment against the parent directory's listing. A junior implementer could reasonably compare the full path instead. One clarifying phrase would settle it.

### [PASS] Success criteria are covered

Each Functional and Technical requirement maps to a task:
- committed-only reads: 6.4
- dates and rendering: 4.5 and 6.4
- slice-132 order and the join property: 3.4 and 6.4
- `sources_missing`: 6.4
- answerer and blank PM-answer exclusion: 7.3
- size trimming: 4.5 and 6.4
- `check_citations`: 4.7
- config load errors: 5.2
- purity: 3.4
- allowlist and the "only place" test: 2.3
- budget refusal at every call, the exact call count and the early stop: 6.4
- failing `show`, non-UTF-8 and root-level entries: 6.4
- docs: 8.1

The slice states no NFR, so no load test or CI task is needed.

### [PASS] Sequencing, test-with pattern and commit markers

Tests follow their implementation tasks (2.1–2.2 then 2.3, 3.2 then 3.4, 4.1 then 4.2, 4.6 then 4.7, 5.1 then 5.2, 6.x then 6.4, 7.x then 7.3). Each of the seven `**Commit**:` markers sits at a tested, working point. The config keys land in Task 5, before the entry point that needs them in Task 7. There are no circular dependencies, and the task file contains no merge or push step.

### [PASS] Proportionality

A single task file fits a slice with relative effort 2 and three new modules. The test lists in 4.5 and 6.4 each trace to a slice requirement. The steps defer to the LLD decisions rather than restating them, and the one cross-reference I checked, 140's slice design at `user/slices/140-slice.answering-pipeline.md`, exists.

### Run Digest

- Response length: 4806 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 199958 / 99782 / 100170 / 4724 / not computed
- Duration: 46.5 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
