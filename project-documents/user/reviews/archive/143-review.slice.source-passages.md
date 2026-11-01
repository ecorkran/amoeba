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
reviewedSha: 72279833c1be34d668d807377fe6be6cd7a67085
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 105416
cachedTokens: 11162
cacheWriteTokens: 94250
completionTokens: 5506
durationSeconds: 46.0
costUsd: 0.434022
costBasis: provider
runId: run-20261101-slices-plan-b480830b
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Source assembly matches the architecture's grounding model"
    location: "project-documents/user/slices/143-slice.source-passages.md#Technical Decisions"
  - id: F002
    severity: pass
    category: dependencies
    summary: "Layering and dependency direction are correct"
    location: "project-documents/user/slices/143-slice.source-passages.md#Component Structure"
  - id: F003
    severity: concern
    category: under-specification
    summary: "The required slice-plan row cannot be resolved for a case the design names"
    location: "project-documents/user/slices/143-slice.source-passages.md#D1 — Plan files are found by CF's document layout, listed at the target commit"
  - id: F004
    severity: concern
    category: proportionality
    summary: "The design is heavier than the slice needs; named cuts"
    location: "project-documents/user/slices/143-slice.source-passages.md"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Tree listings cannot show what kind of entry a name is"
    location: "project-documents/user/slices/143-slice.source-passages.md#D2 — Every read is pinned to one commit; the allowlist gains `show` and `log`"
  - id: F006
    severity: note
    category: alignment
    summary: "Branch-edited files keep their commit date, and the limitation is documented"
    location: "project-documents/user/slices/143-slice.source-passages.md:190"
  - id: F007
    severity: note
    category: under-specification
    summary: "Dependency metadata and the entry-point signature are incomplete"
    location: "project-documents/user/slices/143-slice.source-passages.md:6-9"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for every new read path"
    location: "project-documents/user/slices/143-slice.source-passages.md#D2, D3, D9"
---

# Review: slice — slice 143

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Source assembly matches the architecture's grounding model

The design follows 140's "Assembling sources" and "Stale precedent and growth" sections.
- **Pinned reads:** it reads the committed state of the target branch with `git show` at one pinned commit.
- **Sources:** rules come from configured paths and globs, so no prose is parsed. Plan files are concept, initiative plan, architecture, slice plan, design and tasks. Code is excluded.
- **PM answers:** only PM answers become passages, and the answerer's own answers are filtered out in one place (D6).
- **Size limit:** rules and plan are never trimmed. They fail with "sources too large". PM answers are kept same-slice first, then newest first (D7).
- **Configuration:** `rules_paths` and `passages_max_chars` are required keys with no defaults, as the architecture's "Cost and configuration" section asks.

### [PASS] Layering and dependency direction are correct

- `passages.py` is pure.
- Only `git_read.py` builds git arguments, and only `source_reads.py` knows the CF layout.
- 143 reads 141's record without writing to it.
- 143 provides 144 with values (`PassageSet`, `SourcesProblem`, `None`) and leaves decline mapping to 144.
- 140 is consumed as a written contract only.

### [CONCERN] The required slice-plan row cannot be resolved for a case the design names

D1 makes the slice plan the only required row, with pattern `{initiative}-slices.*.md`. `{initiative}` is the `cf.index` of the slice node's parent. The same decision says "a project-level slice plan has no architecture", so slices whose parent is not an initiative exist.
- The doc does not say what `SliceRef.initiative` is when the parent is not an initiative or has no `cf.index`.
- Unlike D6's `slice_label`, which raises `ValueError`, nothing says whether this case is a programming error, a `sources_missing`, or a different pattern.
- As written, a project-level slice would fail on its one required row, or break on a missing index.

Specify how the parent is resolved and what happens when it does not yield an initiative index.

### [CONCERN] The design is heavier than the slice needs; named cuts

The mechanism is sound, but several parts add weight without serving a requirement the slice has. Effort is rated 2, yet there are 11 decisions and five modules or edits.
- **D2 call-count formula as a test.** The `2 + d + r + 2f` formula and the "exactly N calls" assertion tie tests to the implementation's call pattern. Keep the "budget refusal at every call returns `None`" test. Cut the exact-count test and the "under one second" timing in the walkthrough. The architecture states no latency target.
- **D2 "Calls, and the budget" and "A refused call restarts" paragraphs.** These restate behavior that 141 D5 and 144 own. The needed content is two sentences: a refusal returns `None`, and nothing is cached.
- **D5 merge statistics.** The "11 merge commits for 20 merged slices" figure and the `--first-parent` discussion are not needed to define the date. Keep the known-limitation sentence.
- **D10 glob syntax.** Allowing `?` and `[…]` as well as `*` has no stated use. `*` in the last segment covers the example config. Restricting to `*` simplifies validation and tests.
- **Walkthrough step 4.** The inline script imports internal functions and rebuilds `TickBudget` by hand. A short integration test against a temporary repository covers the same checks without a script that goes stale when signatures change.
- **Restated documents.** The Overview, Value and Success Criteria repeat the same behavior (committed-only reads, trimming order, citation cases) three times.

### [CONCERN] Tree listings cannot show what kind of entry a name is

`parse_tree_listing` reads `git show <commit>:<dir>` output. For a tree, `git show` prints names only, with a trailing `/` on subdirectories. A symlink or submodule entry looks like a file. `git show C:<symlink>` prints the link target's path as the blob content.
- If a rules file such as `CLAUDE.md`, or a matched glob entry, is committed as a symlink, the answering run gets a one-line path as a "rule" passage. The design reports no error, so the grounding sources would be silently wrong.
- A root-level entry like `CLAUDE.md` also needs the root tree (`C:` with an empty path). D2 does not say whether `show_object_args` accepts an empty path, and its `r` count includes the root.

Say how symlink content is detected or refused (for example, a `sources_unreadable` when a blob parses as a single path line), and state the root-listing form.

### [NOTE] Branch-edited files keep their commit date, and the limitation is documented

D5 dates a file by its last commit reachable from the target, which matches the architecture's wording ("the date of its file's last commit on the target"). It states the gap openly: a plan or rules file edited on a slice branch and merged later keeps its branch commit date. A PM answer in between can then outrank the edit. The architecture's precedence principle is "a rule changed after the PM answer overrides it", so this is a bounded deviation. It is acceptable because planning and fixes commit directly to the target. 144 or 145 should keep a case that exercises it.

### [NOTE] Dependency metadata and the entry-point signature are incomplete

- Frontmatter `dependencies` lists only 141, while the prose depends on 128/132 (`git_read`, `resolve_checkout`, `read_target`) and shares `AnswererSettings` with 142.
- The `assemble_sources` signature in API Contracts includes `cf_project_id`, which does not appear in the Data Flow or in any decision. Either show where it is used or drop it from the contract 144 designs against.

### [PASS] Failure modes are enumerated for every new read path

Each new I/O path has an explicit outcome.
- **Git calls:** every non-zero exit from a `show` or `log` gives `sources_unreadable`. A listing, never an exit code, decides absence.
- **Budget refusal:** returns `None`, and the question stays pending.
- **Checkout and target:** `CheckoutUnresolved` and a failed target read give `sources_unreadable`.
- **File content:** a non-UTF-8 file is caught as one named exception, with a comment on why swallowing is correct.
- **Dates:** an unreadable date is `sources_unreadable`, with no fallback to now or the commit date.

All of this fits the project's rules against silent fallbacks and unjustified exception swallowing.

### Run Digest

- Response length: 7412 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 105416 / 11162 / 94250 / 5506 / not computed
- Duration: 46.0 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
