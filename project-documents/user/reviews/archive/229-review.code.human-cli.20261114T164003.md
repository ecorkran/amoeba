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
reviewedSha: 10109d2a97cb5a32d358307c40898783104db709
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
diffTruncated: false
effort: xhigh
turns: 20
promptTokens: 3023250
cachedTokens: 2454019
cacheWriteTokens: 569213
completionTokens: 68240
durationSeconds: 302.4
costUsd: 0.962609
costBasis: provider
runId: run-20261114-p6-1504e37d
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`add --file` with an empty or null document registers the working directory"
    location: "src/amoeba/operations/add.py:133"
  - id: F002
    severity: concern
    category: correctness
    summary: "Single-member `add` raises an uncaught pydantic error for two invalid flag combinations"
    location: "src/amoeba/operations/add.py:142"
  - id: F003
    severity: concern
    category: correctness
    summary: "A named rules entry in a missing subdirectory is reported as `sources_unreadable`"
    location: "src/amoeba/answering/rule_entries.py:84"
  - id: F004
    severity: concern
    category: type-contract-debt
    summary: "Refusal commands silently disappear if the question keys fail to parse"
    location: "src/amoeba/cli/render/registration.py:168"
  - id: F005
    severity: concern
    category: consistency-rot
    summary: "Command strings are hard-coded in several places, against the single-source rule"
    location: "src/amoeba/cli/render/registration.py:35"
  - id: F006
    severity: concern
    category: architectural-decay
    summary: "Rule-label rendering and the separator are duplicated across renderers"
    location: "src/amoeba/cli/render/registry.py:83"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "Project lookup and rejection logic is duplicated between `add` and `rm`"
    location: "src/amoeba/operations/rm.py:119"
  - id: F008
    severity: note
    category: architectural-decay
    summary: "Dead constant and a duplicated `.md` suffix"
    location: "src/amoeba/answering/rule_imports.py:20"
  - id: F009
    severity: note
    category: consistency-rot
    summary: "A dependency whose provider has no Context Forge name prints a bare id"
    location: "src/amoeba/cli/render/registry.py:76"
  - id: F010
    severity: note
    category: test-debt
    summary: "Some doc-contract assertions would pass without checking what they describe"
    location: "tests/test_contract_docs.py"
---

# Review: code — slice 229

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 19 successful tool call(s) of 19 made; 435303 of 435303 diff characters reached the model

## Findings

### [CONCERN] `add --file` with an empty or null document registers the working directory

An empty request file parses to `None`, so `add_document` returns `{"bulk": None}` (src/amoeba/cli/registration_arguments.py:217). `AddRequest._bulk_or_single` passes because no single-member fields were given. Then `if request.bulk is not None` (add.py:133) is false, and the code falls through to the single-member path. The result is that the working directory's project is registered with default rules, from a file that should have been rejected as malformed. The check should test whether `bulk` was given (`"bulk" in request.model_fields_set`), and a null bulk should be malformed. No test covers a null or empty `--file`; `test_file_alone_builds_the_bulk_request` only uses a mapping.

### [CONCERN] Single-member `add` raises an uncaught pydantic error for two invalid flag combinations

`single_member_request` builds `MemberRequest` and `SetUpRequest` (add.py:104-112). `add()` calls it at line 142, outside the `try` at lines 129-132. `MemberRequest` rejects `rules_default` with `rules_paths` (set_up_models.py:75) and any key in both `authorize_allow` and `authorize_deny` (`_no_key_in_both_lists`). `AddRequest` (add.py:58-77) checks neither. `wiring.OPERATIONAL_ERRORS` (wiring.py:89-95) does not include `ValidationError`, and `cli/main.py` catches only that tuple and `RequestDocumentError`. So `amoeba add --allow push --deny push` (argparse allows these as separate groups) prints a traceback, and the MCP `add` tool gets an uncaught exception instead of a `malformed` rejection. No test covers either combination on the single-member path (tests/operations/test_add_request.py only tests bulk combinations).

### [CONCERN] A named rules entry in a missing subdirectory is reported as `sources_unreadable`

The `ls-tree` existence check in `_select_entry` runs only for optional entries (lines 78-83). A named entry in a missing directory goes straight to `listings.of(parent)` (source_reads.py:137), which runs `git show <commit>:<dir>`. `ls_tree_args` documents that `show` treats an absent path as an error, unlike `ls-tree` (git_read.py:82-83). `GitReads.read` maps that exit to `sources_unreadable` (source_reads.py:110-113). `docs/rules.md` says a named entry matching nothing is `sources_missing`, and that "absent" never comes from a failed git call. The import path avoids this because `_is_present` calls `exists` first. The diff's tests cover the optional case (test_default_rules_reads.py) and the import case (test_rule_import_reads.py), not a named top-level entry in a missing subdirectory. Suggested fix: run `exists` for every entry with a parent, plus a test for `named_choice("docs/rules.md")` with no `docs/`.

### [CONCERN] Refusal commands silently disappear if the question keys fail to parse

`_open_question_help` gets its keys by re-parsing the prose detail that `set_up_remove` wrote (`parse_question_keys`, set_up_models.py:270). If the parse returns nothing, the renderer prints "clear each open question first:" and then no commands, with no error. The keys are already structured at the source (`row.key` in `set_up_remove`), so they should travel on `SetUpProblem` instead of through a sentence. The failure mode is silent, and the test only pins the happy path.

### [CONCERN] Command strings are hard-coded in several places, against the single-source rule

`render/commands.py` says every command is "defined once … built from `OperationName.cli_name` so a renamed command changes in one place." These modules bypass that: `NOT_A_PROJECT_FIXES` and `CLEAR_CONCEPT_COMMAND` are literals (registration.py:35-36), `RELISTING_COMMAND = "amoeba list"` (waiting.py:59), `render_decisions` builds `mark-read` inline (simple.py:101), and the operations embed CLI text (`add.py:45-48`, `rm.py:37`, and the `amoeba handle-pause` message in `answer.py`).

### [CONCERN] Rule-label rendering and the separator are duplicated across renderers

`registry._rules` (lines 83-86) and `registration._rules` (registration.py:131-134) both format "default (…)" and "none", each with its own label constant (`DEFAULT_RULES_LABEL`, `NONE` / `NO_RULES_LABEL`). `SEPARATOR = " · "` is defined three times: simple.py:29, waiting.py:40 and registry.py:26. These belong in one helper (for example in `render/text.py`), per the project's define-once rule.

### [NOTE] Project lookup and rejection logic is duplicated between `add` and `rm`

`add._member_project` (add.py:148-169) and `rm._working_directory_project` (rm.py:119-130) both map `project_of` results to `ContextForgeError` or a `NOT_A_PROJECT` rejection. Each defines its own `NOT_A_PROJECT_FIX` (add.py:45, rm.py:37) with different wording. One helper that takes the fix text as a parameter would remove the duplication.

### [NOTE] Dead constant and a duplicated `.md` suffix

`_IMPORT_MARK` is defined but never used. The `.md` suffix is defined twice: `_MARKDOWN_SUFFIX` here (line 22) and `MARKDOWN_SUFFIX` in source_reads.py:55.

### [NOTE] A dependency whose provider has no Context Forge name prints a bare id

`_member_block` prints `names.get(dep.provider, dep.provider)`, so an unlisted provider shows as a bare id. `render_dependencies` marks the same case `(not in Context Forge)`. The `names` map is built only from the members in the current view, so the two outputs disagree for the same condition.

### [NOTE] Some doc-contract assertions would pass without checking what they describe

`test_the_mcp_doc_names_every_tool_and_the_restart_note` asserts `"set_up" in text`. That passes on any incidental occurrence of the substring, so it does not verify the restart note its comment names. `test_the_cli_contract_names_each_field_of_the_registered_views` checks field names as bare substrings, so common words such as `name` or `path` pass whether or not the field is documented.

### Run Digest

- Response length: 9352 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 3023250 / 2454019 / 569213 / 68240 / not computed
- Duration: 302.4 s
- Cost: $0.96 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
