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
reviewedSha: c529fd285ece34d53d6a277874e2b1a276e5e0e6
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 194501
cachedTokens: 96162
cacheWriteTokens: 98333
completionTokens: 5307
durationSeconds: 46.8
costUsd: 0.456868
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Any failed `git show` is read as \"path absent\", so a git error silently drops sources"
    location: "project-documents/user/slices/143-slice.source-passages.md#D2 — Every read is pinned to one commit; the allowlist gains `show` and `log`"
  - id: F002
    severity: concern
    category: performance
    summary: "The per-tick call budget has no stated target, and a refused call restarts assembly from zero"
    location: "project-documents/user/slices/143-slice.source-passages.md#D2 and #D10"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Module and mechanism count is heavy for a Low-risk, effort-2 slice"
    location: "project-documents/user/slices/143-slice.source-passages.md#Component Structure"
  - id: F004
    severity: note
    category: dependencies
    summary: "Dependence on 141 and 140 names is acknowledged but unverified"
    location: "project-documents/user/slices/143-slice.source-passages.md#Prerequisites"
  - id: F005
    severity: note
    category: correctness
    summary: "Fast-forward merges date a plan file at the branch commit, not the merge"
    location: "project-documents/user/slices/143-slice.source-passages.md#D5"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Layer boundaries, dependency directions and scope"
    location: "project-documents/user/slices/143-slice.source-passages.md#Technical Scope"
---

# Review: slice — slice 143

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Any failed `git show` is read as "path absent", so a git error silently drops sources

D2 says that once the commit is known to exist, any non-zero exit from `show` on a path means the path is absent at that commit. For a directory, that means "matches nothing" (D1).
- **Plan-file directories:** a design or tasks file is optional, so a transient git failure, a corrupt object or a missing pack gets treated as "no design yet". The set is then assembled without it.
- **Why it matters:** the arch's trust model is that the check step sees everything that could contradict an answer. A silently omitted design or tasks file removes a passage the check needs, and no problem is raised. This is the "never silent fallback" rule applied to I/O.
- **Smaller effect:** for rules entries and the required slice plan, the same conflation gives `sources_missing` where `sources_unreadable` is accurate.
- **What to fix:** D2 should say how "absent" is told apart from "failed". Options are matching git's "does not exist in" message, or checking existence through the parent directory's listing, which is already read. It should also say that any other non-zero exit is `sources_unreadable`. D9's table should match.

### [CONCERN] The per-tick call budget has no stated target, and a refused call restarts assembly from zero

Assembly makes one subprocess per file for content and one per file for the date. It adds three directory listings, one listing per rules glob, and one commit resolve. Nothing is cached between ticks (State Management). A budget refusal returns `None`, and the next tick starts over.
- **Livelock risk:** if the call count exceeds what one tick's budget allows, the question never gets past assembly and stays pending forever. That outcome is neither a decline nor an answer.
- **The only bound given:** the claim "about 20 files, well under one tick". The size of a tick budget is not restated. Nothing caps the number of files a rules glob can match: `rules/*.md` grows as rules are added.
- **What to fix:** state the call count as a function of file count (about 2N+k) and the budget it must fit within. Then either bound the file count (a `sources_too_large`-style failure on file count) or carry the already-read files across a refusal. The success criterion "refuses the Nth call returns `None`" tests the refusal but not that assembly can finish.

### [CONCERN] Module and mechanism count is heavy for a Low-risk, effort-2 slice

The slice plan rates 143 as Low risk and effort 2. The design adds nine components (two of them new files outside `runner/answering`), eleven decisions and a 9-file fixture set. Several can be cut or merged without losing any requirement:
- **Modules:** `precedent.py` is a store read plus a one-line label function. `sources.py` is a thin wrapper over `source_reads` and `assembly`. `plan_files.py` is separate from `plan_layout.py`, though both express CF layout. Fold `precedent.py` into `source_reads.py` or `assembly.py`, `sources.py` into the same entry module, and `plan_files.py` into `plan_layout.py`.
- **Result types:** `SourceFile`, `PmAnswer`, `SourcesProblemKind` and `CitationProblem` are separate types, and `PassageSet.cited()` is a helper for 144's recording. Keep the ones 144 consumes (`PassageSet`, `SourcesProblem`, `CitationProblem`). The intermediate carriers can be plain tuples or local dataclasses.
- **`parse_tree_listing`:** it is lenient parsing of `git show` tree output. If `ls-tree` is excluded by the plan, this is needed. If the "absent" fix above uses listings, it can carry both jobs.
- **Verification Walkthrough step 4:** it is a 20-line hand script against private module internals (`SourceLocation`, `SliceRef`). Steps 1–3 already cover the behavior, so cut step 4 or reduce it to a pointer at a test.
- **Fixtures:** `git.md` and the second rules file add nothing beyond `python.md` unless a glob test needs two matches. Pare down to what the glob and order tests need.

### [NOTE] Dependence on 141 and 140 names is acknowledged but unverified

The design reads `questions(project_id, state=…)`, `QuestionRecord` fields and the `passages.md` format in 140's D3 as written contracts. It says to re-check them before task breakdown, which is a reasonable control. The dependency directions are correct: 143 reads 141, shares no code with 140, and 144 consumes 143.

### [NOTE] Fast-forward merges date a plan file at the branch commit, not the merge

The arch says a file's date is its last commit on the target, and D5 refines that to first-parent history. With a fast-forward merge, a rule change can look older than a PM answer given between the branch commit and the merge, so the PM answer wins when the later rule should. The slice records this as an accepted limit in the process contract. That is consistent with the arch's "date it last changed on the target", so no action is needed beyond keeping the note.

### [PASS] Layer boundaries, dependency directions and scope

- **Boundaries:** the slice stays inside the Runner's read side. It adds only `show` and `log` to the git allowlist, keeps all git argument building in `git_read.py`, and puts CF layout knowledge in one `upstream/context_forge` module.
- **No store writes:** this matches the arch's rule that decline and submission records are written elsewhere.
- **Excluded to 144:** the scratch directory, the decline reasons and the stored passage set. This matches the slice plan's split.
- **Configuration:** `rules_paths` and `passages_max_chars` have no defaults, as the arch requires ("no hard-coded defaults"). The explicit-empty-list rule mirrors the reserved-terms rule.

### Run Digest

- Response length: 7172 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 194501 / 96162 / 98333 / 5307 / not computed
- Duration: 46.8 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
