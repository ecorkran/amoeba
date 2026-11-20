---
docType: review
layer: project
reviewType: slice
slice: standing-answers
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/230-slice.standing-answers.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261119
dateUpdated: 20261119
reviewedSha: 07a801726bd5488fc8f4ba81221b666ccc56df0d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 990174
cachedTokens: 773715
cacheWriteTokens: 216445
completionTokens: 72263
durationSeconds: 365.0
costUsd: 0.318399
costBasis: provider
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: data-model
    summary: "Migration number and schema version come from the old series"
    location: "project-documents/user/slices/230-slice.standing-answers.md:212"
  - id: F002
    severity: concern
    category: data-integrity
    summary: "Pruning deletes rows that 228 keeps, and cited rulings lose their text"
    location: "project-documents/user/slices/230-slice.standing-answers.md:176"
  - id: F003
    severity: concern
    category: scope
    summary: "The program-removal branch has no caller, and `via` has no reader"
    location: "project-documents/user/slices/230-slice.standing-answers.md:175"
  - id: F004
    severity: concern
    category: integration
    summary: "The reach query, as written, would read `members`, which 228 forbids"
    location: "project-documents/user/slices/230-slice.standing-answers.md:156"
  - id: F005
    severity: concern
    category: architecture
    summary: "The parent architecture does not include scenario F or the operations this slice adds"
    location: "project-documents/user/architecture/220-arch.program-tool.md:25"
  - id: F006
    severity: concern
    category: architecture
    summary: "Standing answers can make questions stop, against the architecture's first design goal"
    location: "project-documents/user/slices/230-slice.standing-answers.md:155"
  - id: F007
    severity: concern
    category: architecture
    summary: "Standing answers reverse a deferral the architecture states"
    location: "project-documents/user/architecture/220-arch.program-tool.md:156"
  - id: F008
    severity: concern
    category: security
    summary: "Who may write a standing answer rests on a tool description"
    location: "project-documents/user/slices/230-slice.standing-answers.md:131"
  - id: F009
    severity: concern
    category: error-handling
    summary: "Failure modes for the new I/O paths are not enumerated"
    location: "project-documents/user/slices/230-slice.standing-answers.md:89"
  - id: F010
    severity: concern
    category: integration
    summary: "Contract changes to 223, 226, 228 and 229 are not declared"
    location: "project-documents/user/slices/230-slice.standing-answers.md:197"
  - id: F011
    severity: note
    category: docs
    summary: "Plan wording differs in two places"
    location: "project-documents/user/slices/230-slice.standing-answers.md:6-11"
  - id: F012
    severity: pass
    category: architecture
    summary: "Dependency direction and SQL rules hold"
    location: "project-documents/user/slices/230-slice.standing-answers.md:79"
  - id: F013
    severity: pass
    category: design-rules
    summary: "Config and state placement hold"
    location: "project-documents/user/slices/230-slice.standing-answers.md:180"
  - id: F014
    severity: pass
    category: scope
    summary: "Plan scope is covered"
    location: "project-documents/user/slices/230-slice.standing-answers.md:32-45"
---

# Review: slice — slice 230

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Migration number and schema version come from the old series

Line 212 sets migration `010`, `EXPECTED_SCHEMA_VERSION` 10 and a version-9 test store. The component table (line 70) names `010_standing_answers.sql`. In the 220 chain the store is at version 5 before this slice: `001_baseline` (222), `002_pause_handling` (223), `003_question_lifecycle` (228), `004` for `answers.via` (226), and `005_member_rules_from` (229). Slices 224 and 227 add no migration. This slice's file is therefore `006`, and its test store is at version 5. `EXPECTED_SCHEMA_VERSION` equals the highest file number (222, line 124), so `010` leaves 006 to 009 missing and the version check fails. The number looks carried over from the old 100-series, where 121 is `009` and 123 is `010`. Correct the number, the version and the fixture, and check the chain against the sibling designs when tasks are written.

### [CONCERN] Pruning deletes rows that 228 keeps, and cited rulings lose their text

D8 says prune deletes withdrawn standing-answer rows "in the pass that already prunes settled questions." 228 D9 says the opposite: "The store's rows are not pruned. They are the record," and its State Management table says "Rows are the record and are kept." The existing pass deletes files only. Deleting rows is a new decision, and it needs to be made in 228 and the architecture.

It also conflicts with the architecture's "An exact record" principle (220 arch, line 34). A delivered answer's `decisions` entry cites `standing:<id>`, but the question's passage record holds only id, kind, source and date (223 D10), not the text. Once the row is deleted, the text the answer relied on survives only in the scratch file, which 228 also prunes. Pruning is plan-assigned, so the design should keep the text in some form: keep any row that a `questions.passages` record cites, or store the cited text on the answer at delivery.

### [CONCERN] The program-removal branch has no caller, and `via` has no reader

D8 says `rm` withdraws reach-`program` answers "when `rm` deletes a program," with reason `program_removed`. 229 excludes deleting a program row because the foreign key and history keep it, and its D3 hides empty programs instead. `rm` removes a member, a pair or a concept (220 arch, line 100). The branch and the `program_removed` constant can never run, and the walkthrough's "A member or program is removed" (line 261) describes something set-up cannot do. Cut both, or name the operation that deletes programs and add it to 229.

Separately, the `via` column (line 109) is written but no output, filter or walkthrough step reads it. Cut it, or name its reader.

### [CONCERN] The reach query, as written, would read `members`, which 228 forbids

Line 156 places the query for "reach `program` with the member's program" in `store/standing.py`. The member's program is stored in `members`. 228 D8 says `store/programs.py` owns every member read, with the `removed_at IS NULL` predicate, and an AST test forbids other modules from querying `members`. A join here fails that test and skips the removal filter. `pause_context.gather` already receives the member and the program (223 D5), so the query can take both as bound parameters with no join. The slice should say that.

### [CONCERN] The parent architecture does not include scenario F or the operations this slice adds

The architecture's scope is "Scenarios A, B and C" (line 25). Its operations table (lines 88–101) has no `standing` or `withdraw`, and its record section has no standing answers. Scenario F and the plan entry for 230 were added on 20261119, as the concept and plan show. The architecture was last updated 20261114. The slice builds against a scope its parent excludes, and the architecture's "new code is added only for a scenario" principle (line 35) cannot be checked against it. Before this slice is built, make a planning edit to the architecture that adds scenario F, the two operations, the `list standing` view and the standing-answer record.

### [CONCERN] Standing answers can make questions stop, against the architecture's first design goal

The architecture's first goal is "Amoeba creates no new reasons for a run to stop" (220 arch, line 31). This slice counts standing answers against `passages_max_chars` and never trims them (line 155). A ruling can therefore turn an answerable question into `sources_too_large` for every question of each member it reaches. Withdrawing the ruling does not help when rules, plan and program text alone exceed the cap. The only exit is raising `passages_max_chars` in config. The walkthrough at lines 260–263 says no state needs a file edited and that there are no dead ends, and both are wrong for this case. Either record the trade-off in the architecture as an accepted stop, or give standing answers a bounded share of the cap. Either way, the detail should say which part is over the limit.

### [CONCERN] Standing answers reverse a deferral the architecture states

The architecture keeps PM precedent per member, and says "Sharing them across a program waits until use shows the need" (line 156). Standing answers with reach `program` or `all` do that sharing, and the plan assigns them to 230. The plan's decision can stand, but the architecture's deferral has to be lifted in writing. Otherwise the parent and the child disagree about the first thing the parent deferred.

### [CONCERN] Who may write a standing answer rests on a tool description

The only guard on `standing` is the MCP tool description, which says to pass only a ruling the PM gave. The architecture's convention for PM-level writes is "An agent, for the PM" (`answer`, `dismiss` and `retract`, lines 91–95). This slice's operations have no caller entry, and a standing answer differs from `answer`: its reach can be every member. Finding 5's plan also has 231 (line 171) use the text unchanged as an instruction to a tool-using agent. The concept (line 174) says the authorize list "does not stop" a standing answer, while this slice applies the list (D7), as the plan requires. Add `standing` and `withdraw` to the architecture table with the same caller entry. Record which governs for 231 before 231 starts, and say in this slice what controls exist within 230.

### [CONCERN] Failure modes for the new I/O paths are not enumerated

The following new I/O paths have no stated handling:
- The reach read in `handle_pause` (line 89). 223 maps each source failure to a decline reason or to exit 3 (223 D3, D5). The slice does not say whether a busy or failed read gives `sources_unreadable`, a waiting question, or exit 3.
- The `cf` call that resolves `--member` (line 128). "Resolved the way `add --project` resolves one" leaves the failure outcome implicit: `cf` missing, a nonzero exit, or unparseable output.
- The `standing` and `withdraw` writes under contention. 228 D2 says a busy store is exit 3. This slice does not say so.
- Row deletion in prune (D8), which runs inside `handle_pause` and `status`. 228 covers only a busy sweep write.

Each needs one sentence naming the outcome.

### [CONCERN] Contract changes to 223, 226, 228 and 229 are not declared

"Consumes" says 223's answering run is "unchanged except for the added passages." This slice changes more than that:
- `assemble` gains a `standing_answers` parameter, on top of the `ProgramSources` change that 223 D11 already made.
- The `answering.yaml` prompts gain a kind, and 223 owns those prompts.
- `pause_context.gather` gains a new store read.
- 228's `prune` gains row deletion (finding 2).
- 229's `rm` withdraws standing answers in its transaction.
- 229's `list_registry` and `list_view` gain a subject, and 226 requires both doors to pass arguments through one `wiring.invoke` (plan entry 226). The new tools must follow that.

Declare each change in Provides or Consumes with its new signature. Line 59 also cites slice 143 as the owner of passages. Slice 143 is from the pre-220 series. The current owners are 221, which keeps the code, and 223, which extends it.

### [NOTE] Plan wording differs in two places

The frontmatter lists 222 and 226 as dependencies. The plan entry for 230 lists 223, 228 and 229. Both are harmless, since both come earlier in the implementation order, but the two should match. The plan also says "`list` shows it as withdrawn until it is pruned," while line 148 places withdrawn rows under `list standing --all`. Decide which wording the plan keeps.

### [PASS] Dependency direction and SQL rules hold

`StandingAnswer` is typed in `answering/passages.py`, so the answering library imports nothing from the store, as 223 D11's boundary requires. `pause_context` passes values to `assemble`. The SQL is composed from module constants and binds every value with `?` (lines 72 and 213), as the Amoeba SQL rule requires.

### [PASS] Config and state placement hold

No config key is added (D9). The cap and retention reuse `passages_max_chars` (222) and `prune_after_days` (228). The backup in Special Considerations goes under the state directory and names a restore path (line 248).

### [PASS] Plan scope is covered

The In list covers the plan entry's behaviors: give, list, withdraw, reach, passage, the authorize list and the live fixture. Scenarios 231 and 232 are left out, as the plan leaves them. The never-trimmed rule appears in D5 (line 155). Success Criteria (lines 203–221) cover each plan criterion.

### Run Digest

- Response length: 11999 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 990174 / 773715 / 216445 / 72263 / not computed
- Duration: 365.0 s
- Cost: $0.32 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
