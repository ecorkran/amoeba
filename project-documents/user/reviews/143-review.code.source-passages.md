---
docType: review
layer: project
reviewType: code
slice: source-passages
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/143-slice.source-passages.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: 0bb7004132416b5909eefb9a569e15f38aca4aa8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 66926
cachedTokens: 3232
cacheWriteTokens: 63692
completionTokens: 3601
durationSeconds: 32.7
costUsd: 0.29587
costBasis: provider
squadronVersion: 0.24.13
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: performance-resource
    summary: "PM precedent query is unbounded and does a node lookup per record"
    location: "src/amoeba/runner/answering/sources.py#pm_precedent"
  - id: F002
    severity: concern
    category: correctness
    summary: "Tree-listing parser can drop or alter legitimate file names"
    location: "src/amoeba/runner/git_read.py#_tree_entries"
  - id: F003
    severity: concern
    category: type-contract-debt
    summary: "`rules_paths` validation accepts entries that can never match"
    location: "src/amoeba/runner/project_config.py#_checked_rules_path"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "Duplicated helpers and an over-wide signature"
    location: "src/amoeba/runner/answering/sources.py:_unreadable"
  - id: F005
    severity: note
    category: correctness
    summary: "YAML comments in front matter are treated as headings"
    location: "src/amoeba/runner/answering/passages.py#cut_passages"
  - id: F006
    severity: note
    category: test-debt
    summary: "Test typing and unused fixture"
    location: "tests/runner/answering/test_sources.py#_run"
  - id: F007
    severity: pass
    category: security-hygiene
    summary: "Git read safety and error handling"
    location: "src/amoeba/runner/git_read.py#_refuse_option"
---

# Review: code — slice 143

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] PM precedent query is unbounded and does a node lookup per record

`pm_precedent` loads every ANSWERED question for the project. It then calls `store.get_node` once per PM-answered record to build the slice label. It runs on every `assemble_sources` call, so cost grows with the project's full answer history, not with the `passages_max_chars` budget that finally discards most of it. Cache nodes by `node_id` within the call, or batch-fetch them. Better still, order and limit the records before resolving labels. The query could also return newest-first so the loop can stop early.

### [CONCERN] Tree-listing parser can drop or alter legitimate file names

The parser skips any stripped line that starts with `tree `, so a real file named `tree notes.md` is silently dropped from the listing. It also `strip()`s every entry, which alters names with leading or trailing spaces. Because absence is decided from these listings, a dropped rules or plan file shrinks the offered set without any error. This is the failure mode the module docstring says it avoids. Skip only the first non-blank line when it is the header. A more robust option is `git ls-tree --name-only`, if the allowlist can take it.

### [CONCERN] `rules_paths` validation accepts entries that can never match

An entry with a trailing slash (`rules/`) or a bare `*` in a directory position passes validation, but its last segment is empty. `glob_matches("")` then matches nothing, so the failure shows up on every question as `sources_missing` instead of at config load. The same function also hard-codes `"*"` as `_GLOB`, while `passages.glob_matches` hard-codes it again. Reject an empty last segment at load, and define the wildcard once.

### [CONCERN] Duplicated helpers and an over-wide signature

`_unreadable` is defined in both `sources.py` and `source_reads.py`. The "no Context Forge index" `ValueError` is built in both `slice_label` and `_slice_ref`. `read_committed_sources` and `locate_sources` each take seven or eight positional parameters, and `repo, budget, run, timeout_seconds` are threaded through `assemble_sources` too. `_Git` already bundles those four, so it could be a public parameter object. `passages.py` is about 330 lines, over the ~300-line guideline, and the PM-ordering, rendering and citation code could move out.

### [NOTE] YAML comments in front matter are treated as headings

Front matter is not recognised as a block, so a `# comment` line inside a `---` block cuts a passage there. The round-trip test still passes because text is never rewritten. This is a splitting-quality edge case, not data loss. Tracking the front-matter block, or documenting the limit, would close it.

### [NOTE] Test typing and unused fixture

`_run` returns `Any` and uses `# type: ignore[no-any-return]`, which weakens the strict-pyright coverage the rules ask for in tests. `test_a_commit_added_after_the_first_call_is_not_mixed_in` also takes a `sources` fixture it never uses.

### [PASS] Git read safety and error handling

Option-like commits and targets are refused in every argument builder. Paths follow the `:` or `--`, so they cannot be read as options. The allowlist is extended explicitly and covered by a test. Non-zero git exits map to `sources_unreadable` rather than "absent". The `UnicodeDecodeError` handler is narrow and carries the required justification comment.

### Run Digest

- Response length: 4465 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 66926 / 3232 / 63692 / 3601 / not computed
- Duration: 32.7 s
- Cost: $0.30 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Resolution (20261102)

- **F001 — resolved.** `pm_precedent` reads each slice node once per call and reuses its label. The query stays unbounded on purpose: the size limit is applied to the rendered set, and PM answers must be ordered (same slice first, newest first) before any can be dropped, so every record is needed.
- **F002 — resolved.** The tree parser treats only the first non-blank line as the `tree …` header, so a file named `tree notes.md` is listed (`test_a_file_named_like_the_tree_header_is_still_listed`). Stripping stays: the parser is documented as lenient about trailing whitespace and CRLF, and a file name with leading or trailing spaces in a rules or plan directory is not a case this project has.
- **F003 — resolved.** A `rules_paths` entry ending in `/` now fails at load, naming its index. A bare `*` in a directory position was already rejected by the last-segment rule. The wildcard character is defined once, as `GLOB_WILDCARD` in `passages.py`, and the config validator and the glob matcher both use it.
- **F004 — partly resolved.** `unreadable()` now lives in `passages.py` and both readers use it; the missing-CF-index `ValueError` is built once (`_cf_index` in `sources.py`). No change to the parameter lists: `locate_sources`, `read_committed_sources` and `assemble_sources` are the contract the slice design fixes for slice 144, and `_Git` is a private bundle of the same four values. No change to the size of `passages.py` (about 360 lines): it is one pure module whose parts share the types, and `store.py` and `inbox.py` are already over the guideline.
- **F005 — resolved.** A leading `---` block that is closed by a second `---` line is front matter, and `#` lines inside it no longer cut. A file that opens with `---` and never closes it has no front matter. Tests cover both.
- **F006 — resolved.** `_run` in `test_sources.py` returns a typed callable and casts the real `subprocess.run` result instead of using a `type: ignore`; the unused `sources` fixture is gone from the pinned-commit test.

Full suite 4127 passed; ruff and pyright clean.
