---
docType: review
layer: project
reviewType: slice
slice: human-cli
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/229-slice.human-cli.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261113
dateUpdated: 20261113
reviewedSha: 5df183c07dbcbc7fa63322f6f9264744aa125e36
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: high
turns: 10
promptTokens: 523309
cachedTokens: 402636
cacheWriteTokens: 120661
completionTokens: 10983
durationSeconds: 92.2
costUsd: 0.63367
costBasis: provider
squadronVersion: 0.24.28
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "No CLI way to clear a member's allow or deny list"
    location: "project-documents/user/slices/229-slice.human-cli.md#D4. `add`"
  - id: F002
    severity: concern
    category: state-lifecycle
    summary: "Orphaned and mistyped programs have no exit"
    location: "project-documents/user/slices/229-slice.human-cli.md:44, 133"
  - id: F003
    severity: concern
    category: under-specification
    summary: "Program-id collision is unspecified in D5"
    location: "project-documents/user/slices/229-slice.human-cli.md:133"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes for Context Forge calls in `list` and `add` are not enumerated"
    location: "project-documents/user/slices/229-slice.human-cli.md#D3. `list`"
  - id: F005
    severity: concern
    category: architecture-boundary
    summary: "`add --file` dispatch and result shape are unspecified after `SET_UP` leaves `OperationName`"
    location: "project-documents/user/slices/229-slice.human-cli.md:42, 126"
  - id: F006
    severity: concern
    category: architecture-alignment
    summary: "The architecture document is not updated for the operation rename"
    location: "project-documents/user/slices/229-slice.human-cli.md#D12. Documents"
  - id: F007
    severity: concern
    category: scope
    summary: "Proportionality: several mechanisms nothing in the slice requires"
    location: "project-documents/user/slices/229-slice.human-cli.md:85, 103-108, 168-170"
  - id: F008
    severity: note
    category: under-specification
    summary: "The 100-column rule conflicts with printed commands and paths"
    location: "project-documents/user/slices/229-slice.human-cli.md:92, 110"
  - id: F009
    severity: note
    category: operator-walkthrough
    summary: "Existing members keep `named` rules after the cutover"
    location: "project-documents/user/slices/229-slice.human-cli.md:166, 198"
  - id: F010
    severity: pass
    category: scope
    summary: "Scope matches the slice plan entry"
    location: "project-documents/user/slices/229-slice.human-cli.md#Technical Scope"
  - id: F011
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction hold, and the new I/O paths are mostly covered"
    location: "project-documents/user/slices/229-slice.human-cli.md#Architecture"
---

# Review: slice — slice 229

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] No CLI way to clear a member's allow or deny list

D4 gives `--allow KEY` and `--deny KEY` as repeatable flags. Under 222's set_up, a list field that is given replaces the stored value whole, and an omitted one is left alone. The flags can therefore only replace a list with a non-empty one or leave it as it is. Nothing lets the PM empty an allow list, for example to revoke "yes, merge it" for a repo. The slice plan promises "Every setting of a member can be set from the CLI; only `config.yaml` is edited by hand", and `rm` covers only members, pairs and the concept. The design needs an explicit way to clear each list, such as `--no-allow` and `--no-deny`. It should also say plainly that `--allow` replaces the list and does not add to it. The same gap exists on the MCP `add` tool, where an empty array needs a defined meaning.

### [CONCERN] Orphaned and mistyped programs have no exit

Program deletion is excluded, and an empty program "stays as an inert row". The slice also makes program creation easy. `add` with no `--program` creates a program per repo, and `--program ID` creates one when it is new. A mistyped `--program` therefore creates a program that nothing can remove. The only fix is `rm` and then `add --program right`, which leaves the typo program in `list programs` with 0 members indefinitely. A program that carries a concept is also left behind. The design neither names a cleanup nor says why the growth is bounded, which the "every state has an exit" rule requires. The cheapest fix is for `rm` to drop a program once it has no members and no concept. A short statement of why the leftover is bounded would also do. "Unchanged from 228" is not a reason when the parent decision leaves a dead end.

### [CONCERN] Program-id collision is unspecified in D5

For a new member with no `--program`, the design creates a program whose id is the CF project name. If a program with that id already exists, for example one the PM named by hand, the text is silent. The most likely reading is that the repo silently joins that program. Program membership decides which concept and which pairs the repo sees. The design should either reject with a clear code or state that it joins. The text output must also say which of the two happened.

### [CONCERN] Failure modes for Context Forge calls in `list` and `add` are not enumerated

`list members` and `list dependencies` call `cf list projects`. `add --project NAME|ID` resolves through a new `project_details`. D3 covers a project that is missing from the list and a missing path. It does not cover `cf` being absent, failing or timing out, or `--project NAME` matching more than one project. 222 and 224 map `cf` failures to exit 3. The design should say that the registered-subject views also exit 3 rather than printing half a view. It should also say what an ambiguous name does, since the id-or-name lookup is new here.

### [CONCERN] `add --file` dispatch and result shape are unspecified after `SET_UP` leaves `OperationName`

`SET_UP` is removed from `OperationName` and `wiring.invoke` gets only add, rm and list cases. `AddRequest` builds one member, but `--file` is the multi-member bulk path in the old `set_up` YAML shape, and it is CLI only. The design does not say which operation name `--file` goes through, which JSON document it returns, or which renderer prints it. It also does not say how that fits the arch principle "One operation, two doors... no logic of their own", since the CLI would be the only door with this capability. D14 tests `--file` equal to the old `set_up`, so the engine's result document is probably meant. If so, say so, and say that the `add` text renderer handles multi-member results.

### [CONCERN] The architecture document is not updated for the operation rename

The 220 architecture lists `set_up` as an operation and states "MCP and the CLI... with the same names". After this slice the operations are `add`, `rm` and `list`, `set_up` is no longer a tool, and CLI names differ from MCP names (kebab-case against snake_case). D12 updates the 227 design and about six docs but not the 220 architecture table or that principle. The architecture should be amended in this slice, or the slice should state that the slice plan supersedes it. Otherwise later reviewers will check against a document that contradicts the code.

### [CONCERN] Proportionality: several mechanisms nothing in the slice requires

These can be cut, or the section shortened:
- `rm` also answering to `remove`, and singular aliases for the `list` subjects (`program`, `member`, `dependency`). The slice plan lists `remove` as an alias, but nothing needs the list aliases.
- The "Why the rules defaults matter" section, which restates measurements and arguments already carried by D7 to D10 and the plan.
- D12's full inventory of documents to rewrite, which restates the docs the repo already keeps. A single line, "docs updated to the new names, plus `docs/rules.md`", is enough.
- `list` with no subject duplicates the `status` operation, so both stay registered and both are tool rows. Say why `status` stays (agents and the hook's catch-up path), or fold one into the other.

### [NOTE] The 100-column rule conflicts with printed commands and paths

D2 says no line is longer than 100 columns and cuts long text with `…`. D3 prints "the command to answer it" for each waiting entry, and repo paths in `list members`. A cut command cannot be pasted and a cut path is useless. State that commands and paths are exempt from the cut, or that they wrap at a boundary.

### [NOTE] Existing members keep `named` rules after the cutover

The two registered members stay `named` with `["CLAUDE.md"]`, so the default `AGENTS.md` reaches only new members. The walkthrough's "changing rules" step shows `add --default-rules`. D13 could include running it for the two existing members as part of the cutover, so that "a repo's rules work with no setup" holds for them too.

### [PASS] Scope matches the slice plan entry

Every plan item is present and none is dropped or deferred:
- text output and `-j`;
- kebab and snake names from one place;
- `add`, `rm`, `list` and the three registered views;
- default rules with optional entries, duplicate dropping and `@path` imports;
- the hook cutover.

The additions are `--default-rules`, `--no-rules` and migration 005. The plan's risk line already anticipated the one-column migration, and the design explains why a stored `rules_from` is needed.

### [PASS] Layering and dependency direction hold, and the new I/O paths are mostly covered

Renderers are pure functions in `cli/render/`. `add` and `rm` build a request for the existing engine, so no decision logic moves into a door. `source_reads` takes the optional-versus-named choice from its caller. `mcp/detached.py` depends on `names.py`. The design keeps the architecture's principles:
- no process stays running;
- `list` reads state and sends nothing;
- the question record stays exact.

The new I/O paths have explicit handling:
- `git ls-tree` exit codes, where "absent" never comes from an error;
- import depth, cycles, a missing target and size, each with a stated outcome;
- the cutover window, with its effect on `list` described;
- stale MCP sessions, which are told to restart in the docs.

Config keys with no code default, and state kept out of `~/.config`, follow the project rules.

### Run Digest

- Response length: 8705 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 523309 / 402636 / 120661 / 10983 / not computed
- Duration: 92.2 s
- Cost: $0.63 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
