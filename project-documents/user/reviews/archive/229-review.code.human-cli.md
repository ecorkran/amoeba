---
docType: review
layer: project
reviewType: code
slice: human-cli
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/229-slice.human-cli.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: 366985a2167b11fd7bdf58e79f877c075ceb859f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
diffTruncated: false
effort: xhigh
turns: 14
promptTokens: 1623089
cachedTokens: 1065357
cacheWriteTokens: 557722
completionTokens: 58425
durationSeconds: 259.8
costUsd: 0.858718
costBasis: provider
runId: run-20261114-p6-1504e37d
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: test-debt
    summary: "Removed-member test is named for default rules but asserts neither rules nor rules_from"
    location: "tests/operations/test_set_up_remove.py:136"
  - id: F002
    severity: concern
    category: type-contract-debt
    summary: "Change lines are written as strings, then split back apart by the renderer"
    location: "src/amoeba/operations/set_up_models.py:145"
  - id: F003
    severity: note
    category: other
    summary: "Waiting-question text is cut to 100 columns, with no pointer to the full text"
    location: "src/amoeba/cli/render/waiting.py:139"
  - id: F004
    severity: note
    category: performance-resource
    summary: "Import following builds a second directory-listing cache, and the existence check is never cached"
    location: "src/amoeba/answering/source_reads.py#_Reading"
  - id: F005
    severity: note
    category: security-hygiene
    summary: "`ls_tree_args` checks the commit for a leading `-` but not the directory"
    location: "src/amoeba/upstream/git_read.py:79"
  - id: F006
    severity: note
    category: documentation-drift
    summary: "Command placeholder convention in the render docstring does not match the code"
    location: "src/amoeba/cli/render/commands.py:4"
  - id: F007
    severity: note
    category: consistency-rot
    summary: "A second private base model duplicates `FrozenModel`"
    location: "src/amoeba/operations/list_registry.py:24"
  - id: F008
    severity: note
    category: documentation-drift
    summary: "`_ended` docstring says the text names which vocabulary, but the code tries both"
    location: "src/amoeba/store/settled.py:52"
  - id: F009
    severity: pass
    category: correctness
    summary: "Enum-to-dict coverage in the list renderer is complete"
    location: "src/amoeba/cli/render/waiting.py:48"
  - id: F010
    severity: pass
    category: correctness
    summary: "Render dispatch covers every `OperationResult` member"
    location: "src/amoeba/cli/render/dispatch.py"
  - id: F011
    severity: pass
    category: correctness
    summary: "Import following matches the documented depth, cycle and repo-boundary rules"
    location: "src/amoeba/answering/import_follow.py#follow_imports"
---

# Review: code — slice 229

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 13 successful tool call(s) of 13 made; 443046 of 443046 diff characters reached the model

## Findings

### [CONCERN] Removed-member test is named for default rules but asserts neither rules nor rules_from

`test_naming_a_removed_member_re_adds_it_on_the_default_rules` removes the consumer, re-adds it with no rules field, and asserts only the change line and `removed_at is None`. The fixture stored the consumer with `RULES` (named `["CLAUDE.md"]`, lines 53–57). `_merged_rules` in `src/amoeba/operations/set_up.py:179–183` keeps the stored `rules_paths` and `rules_from` when the request omits both. So the re-add stays named, which matches "an existing member keeps what it has" in `docs/rules.md` and the `rm` docstring. The behaviour is consistent with the docs, but the test name claims the opposite and nothing checks the rules. A change that reset revived members to the default would leave this test green. Rename it to say the stored rules are kept, and assert `rules_from` and `rules_paths`. Add a separate test for a revived member that was originally on the default, if that case matters.

### [CONCERN] Change lines are written as strings, then split back apart by the renderer

The engine builds each change as a string with `change_line` (line 140). The renderer then recovers verb, subject and detail by splitting on spaces. `parse_change_line` is `line.split(" ", 2)` followed by `ChangeVerb(verb)` and `ChangeSubject(subject)` (lines 147–148). Consumers are `_headline` and `_changes` in `src/amoeba/cli/render/registration.py`. The same strings are the public `changes` field in the JSON result, so the wire format and the text rendering depend on one another through a space split. Nothing fails today because every writer is in one module. But the structure is discarded at write time and rebuilt later, and an unexpected string raises `ValueError` after the write has committed. `_text_of` in `src/amoeba/cli/commands.py` runs after `invoke`, so that failure would surface with the change already on disk. Carry the `Change` values through `SetUpResult` and derive the string only for the JSON field.

### [NOTE] Waiting-question text is cut to 100 columns, with no pointer to the full text

`_waiting_entry` prints the question through `prose_line`, so a long question is cut with `…`. The next line is `answer it, or close it without an answer:` with no hint that `list -j` or `status -j` shows the whole question. `text.py` documents that the full text is in `-j`, but a person reading the list sees only the cut text and must already know the flag. Add one line such as `full question: amoeba list -j`, or print the question in full on this block.

### [NOTE] Import following builds a second directory-listing cache, and the existence check is never cached

`locate_sources` builds one `Listings`, and `_Reading.__init__` builds another, so the root and rules-directory listings fetched during selection are fetched again during import following. `Listings.exists` (`source_reads.py:143–148`) has no cache at all, and `follow_imports` calls it once per import (`import_follow.py#_is_present`). Each import therefore costs an `ls-tree` and a `git show` per directory. This is bounded by the import depth and the repo size, so it is not a blocker. Share one `Listings` instance, and cache `exists` as `of` does.

### [NOTE] `ls_tree_args` checks the commit for a leading `-` but not the directory

`ls_tree_args` calls `_refuse_option(commit)` (line 85), but the directory goes straight into argv as `f"{directory}/"`. `validate_repo_relative_path` in `src/amoeba/answering/settings.py` does not reject a leading `-`, so a rules entry such as `-x/rules.md` reaches git as an option-looking argument. Git would reject it and the result would be `sources_unreadable`. `ls-tree` has no option that writes anything, so this is not an injection path. It is still inconsistent with the module's stated rule, and `test_git_read.py` checks the refusal only for the commit. Refuse a leading `-` on the directory too, or pass `--` before it.

### [NOTE] Command placeholder convention in the render docstring does not match the code

The module docstring says every command is "complete except for the words only the person has … written as a `<...>` placeholder". `add_project_command` (line 58) emits `--project NAME`, a bare uppercase word, not a `<...>` placeholder. Either change the docstring or make the output `--project <name>`.

### [NOTE] A second private base model duplicates `FrozenModel`

This diff makes `FrozenModel` (`set_up_models.py:39`) the public base for "request and result models: no extra keys, frozen". `list_registry._Model` then defines the same `ConfigDict(extra="forbid", frozen=True)` for its own view models. Use `FrozenModel` there. Two bases with one config invite drift.

### [NOTE] `_ended` docstring says the text names which vocabulary, but the code tries both

The docstring says the `ended` text "names which" vocabulary it came from. The body tries `ClosedReason`, then `AnsweredBy`, and raises if neither matches. The vocabularies do not overlap, so the code is correct, but the docstring describes a mechanism that does not exist. Reword it to say the two vocabularies never share a value, so either parse is unambiguous.

### [PASS] Enum-to-dict coverage in the list renderer is complete

I checked each dict the renderer indexes against its enum. `ENDED_TEXT` covers `AnsweredBy` (`ANSWERER`, `PM`) and `ClosedReason` (`DISMISSED`, `RUN_MOVED_ON`, `RUN_GONE`). `PAUSE_MEANING` covers `HANDLED_BY_HANDLE_PAUSE` (`UNHANDLED`, `CLAIM_STALE`, `ANSWERED_UNRESUMED`), which is the only set that reaches `_paused_entry`. `RUN_STATE_TEXT`, `CLEARS_ON_LISTING` and the `UnplacedReason` cases are also complete. No `KeyError` is reachable from `list --all`.

### [PASS] Render dispatch covers every `OperationResult` member

`wiring.OperationResult` has 11 members (`SetUpResult`, `ListResult`, `ProgramsView`, `MembersView`, `DependenciesView`, `AnswerResult`, `StatusResult`, `DecisionsResult`, `MarkReadResult`, `DismissResult`, `RetractResult`). `render_result` has one case for each, so the match is exhaustive and pyright should not flag a missing return.

### [PASS] Import following matches the documented depth, cycle and repo-boundary rules

The new file is in full in the diff. The chain passed to each nested call is the files from the entry down to, but not including, the file being read, and the depth check fires at the fourth import. `_resolve` rejects any path that normpath leaves starting with `../`. `has_read` ends cycles quietly, and a missing target is skipped only when `optional` is set. These match `docs/rules.md` and the tests in `test_rule_import_reads.py`.

### Run Digest

- Response length: 9067 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 1623089 / 1065357 / 557722 / 58425 / not computed
- Duration: 259.8 s
- Cost: $0.86 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
