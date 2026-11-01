---
docType: review
layer: project
reviewType: slice
slice: source-passages
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/143-slice.source-passages.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: af5c121d9938de3184c4c4a26a801cc858932d2a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 280458
cachedTokens: 182094
cacheWriteTokens: 98356
completionTokens: 4698
durationSeconds: 44.1
costUsd: 0.459467
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Per-file git calls can exceed the tick budget, and a refusal restarts assembly from scratch"
    location: "project-documents/user/slices/143-slice.source-passages.md#D2 — Every read is pinned to one commit"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Symlink and submodule refusal adds a mode-parsing mechanism the slice does not need"
    location: "project-documents/user/slices/143-slice.source-passages.md#D2 (mode paragraph), D9"
  - id: F003
    severity: concern
    category: proportionality
    summary: "The slice is larger than its plan entry; several mechanisms can be cut or deferred"
    location: "project-documents/user/slices/143-slice.source-passages.md#Technical Scope"
  - id: F004
    severity: note
    category: dependencies
    summary: "Dependency list differs from the slice plan"
    location: "project-documents/user/slices/143-slice.source-passages.md:6-10"
  - id: F005
    severity: note
    category: architecture-boundaries
    summary: "Running git in the slice's checkout is a hidden dependency, though it is bounded"
    location: "project-documents/user/slices/143-slice.source-passages.md#D3"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the architecture's source assembly, ordering and trimming rules"
    location: "project-documents/user/slices/143-slice.source-passages.md#D1, D5, D6, D7"
  - id: F007
    severity: pass
    category: integration
    summary: "Layer boundaries, interfaces and failure vocabulary"
    location: "project-documents/user/slices/143-slice.source-passages.md#D9, Integration Points"
---

# Review: slice — slice 143

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Per-file git calls can exceed the tick budget, and a refusal restarts assembly from scratch

D2 makes every `git_read` call check the tick budget. When the budget refuses a call, the result is `None`, nothing is cached, and "the next tick starts assembly again from the commit read." The Data Flow shows how many calls one assembly makes. It makes 1 `log` for the commit, 1 `show` for `project-documents/user`, and 1 `show` per directory. It then makes 2 calls per file (`log` for date and mode, then `show`). The rules glob plus the six plan rows will usually mean dozens of subprocess calls for one question. The doc has no bound on that count. It does not compare the count with the tick budget's capacity. It does not say whether a restarted assembly can ever finish. If one assembly needs more calls than a tick allows, the question stays `pending` on every tick and never reaches the PM. That contradicts the architecture's "Declining is cheap and safe" and "Failures decline; nothing retries." The Success Criteria test refusal at the Nth call, but they never test that a realistic fixture set completes within a stated budget.

To resolve this, state the call count as a function of file count. State the budget it must fit within, or let assembly carry its partial reads across ticks. If neither is feasible, surface a persistent budget refusal as a problem, not an endless `None`.

### [CONCERN] Symlink and submodule refusal adds a mode-parsing mechanism the slice does not need

D2 changes the date call to `log -1 -c --raw --format=%cI`. It adds `parse_last_change` to handle both the plain and the merge (`-c` combined) raw-line forms. It rejects any mode other than `100644` or `100755` as `sources_unreadable`. The sources are the project's own committed rules and plan documents, which the doc itself says are already shared with its agents (Special Considerations, "Secrets"). A symlink there would at worst yield a one-line passage holding a path. The check set would see that passage and decline. No architecture goal needs the guard. It costs a more complex git argument builder, a two-format parser (the combined-diff format is the fragile part), a Technical Requirement, and fixture and test work. The `last_change_args` builder, `parse_last_change`, and the symlink test could all shrink to a plain `log -1 --format=%cI`. Cut the mode check, or defer it until a real sighting shows it matters.

### [CONCERN] The slice is larger than its plan entry; several mechanisms can be cut or deferred

The slice plan sizes 143 as pure, low-risk, "show and log only" (Risk Level: Low). This design adds more than that entry calls for:
- Commit pinning with a separate `log` call, plus `source_commit` on the result.
- Directory-listing-only existence checks. `parse_tree_listing` must also handle `show` of a tree, including the root tree.
- The symlink and submodule guard (see the previous finding).
- A strict glob grammar with per-key-path load errors for six distinct refusals (`?`, `[`, `]`, `**`, `*` outside the last segment, `..`).
- Lenient case and space normalization in `check_citations` for ids that Amoeba and Squadron both generate.

Each is defensible alone, but together they push this past "Relative Effort: 2". Candidates to defer are the mode guard and the extra glob refusals, which can collapse to "absolute path or `..` refused, `*` only in the last segment". `source_commit` is worth keeping, because 144 records it. Say which of these the slice plan entry requires.

### [NOTE] Dependency list differs from the slice plan

The slice plan entry lists 143 as dependent on 141 only, and "Independent of 140 and 142". Slice 143's frontmatter and Prerequisites add 142 and 140, "for configuration only" and "as a written contract only". The doc justifies both. The only real coupling is that 142 and 143 both extend `AnswererSettings`. The plan says they can be built in parallel worktrees, so say that this affects merge order only and is not a build dependency. Alternatively, update the plan's dependency line.

### [NOTE] Running git in the slice's checkout is a hidden dependency, though it is bounded

The architecture says the answering run "never touches a project checkout" and "does not hold or wait on a checkout." D3 uses the checkout only as a place to run object-only `git show` and `git log` calls. It reads nothing from the working tree or index, and the answering run itself still never sees the checkout. That is consistent with the architecture. The remaining dependency is on the last observed snapshot's checkout path and on a locally resolvable target ref. D3 turns an unresolved checkout into `sources_unreadable`, so this is a decline path and not a hang. Leave it as is.

### [PASS] Alignment with the architecture's source assembly, ordering and trimming rules

The design follows the architecture's "Assembling sources" and "Stale precedent and growth" sections:
- It reads rules and plan from the target's committed state.
- It cuts the text into numbered passages that keep their path.
- It dates rules and plan passages by their file's last commit, and PM answers by the time the answer was given.
- It excludes answerer-answered records by construction.
- It never trims rules or plan, and declines with a "sources too large" problem.
- It orders PM answers by same slice first, then newest first.
- It records dropped PM answers for 144.
- Code is excluded as a source.

### [PASS] Layer boundaries, interfaces and failure vocabulary

The design keeps pure logic (`passages.py`) apart from the I/O modules. It confines git argument construction to `git_read.py`. It leaves the decline reasons to 144, so no store change lands here. Every git failure mode (timeout, non-zero exit, non-UTF-8 file, missing directory, unresolved target) maps to a named `SourcesProblemKind`. Only a budget refusal gives `None`. The consumer contract for 144 (`assemble_sources`, `render_passages`, `check_citations`, `slice_label`) is concrete enough to design against without reading 143's code.

The architecture states no NFR (latency or throughput) for this path, so none needs restating.

### Run Digest

- Response length: 6978 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 280458 / 182094 / 98356 / 4698 / not computed
- Duration: 44.1 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
