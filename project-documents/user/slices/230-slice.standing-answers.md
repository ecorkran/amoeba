---
docType: slice-design
slice: standing-answers
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 222
- 223
- 226
- 228
- 229
interfaces:
- 231
- 232
dateCreated: 20261119
dateUpdated: 20261119
status: not_started
---

# Slice Design: Standing Answers

## Overview

A standing answer is a ruling the PM gives once, ahead of time, in the PM's own words. It names the situation it covers and what to do, and it has a reach: every member, one program, or one member. Every answering run is sent the standing answers that reach the member, as passages the reply can cite. This slice builds the record, three operations (give, list, withdraw) and the passages. It is the first slice of scenario F in the concept.

## Value

Today the PM's answers count only in the repo they were given in, and only after a question has actually waited there. A ruling such as "CONCERNS reviews never block a merge" has to be given again in every repo, each time after a run has stopped for it. With this slice the PM says it once, to any agent, and it holds everywhere it reaches from the next question on.

## Technical Scope

In:

- The `standing_answers` table (migration `010`) and its store functions.
- `standing` (give), `withdraw` and a `standing` view of `list`, on the CLI and MCP.
- A new passage kind, `standing_answer`, added to every answering run for a member the standing answer reaches.
- The answer and check prompts learn the kind.
- `rm` withdraws standing answers whose member or program it removes.
- Pruning of withdrawn standing answers.
- Docs: `cli-contract.md`, `mcp-server.md`, `store-contract.md`, `rules.md`.

Out, each in the slice named:

- Handling pauses that are not agent questions, and doing work in a repo (231).
- Promoting a stored answer, and finding rulings without being asked (232).

## Dependencies

### Prerequisites

- 222: the store, migrations, members and programs.
- 223: `handle_pause`, passage assembly, the answering run and its prompts.
- 226: the MCP server and its thin tools.
- 228: prune, and `rm`.
- 229: the CLI's text and JSON output, `list` and its views, and command naming.

### Interfaces Required

- `answering.passages.assemble` and `operations.pause_context.gather` (223, 143).
- `operations.list_registry` and `list_view` (229).
- `operations.set_up_remove` (228).
- `operations.prune` (228).

## Architecture

### Component Structure

| File | Change |
|---|---|
| `store/schema/010_standing_answers.sql` | New table |
| `store/standing.py` | New: insert, withdraw, list, the ones reaching a member, withdraw by member or program, delete withdrawn rows older than a time |
| `store/sql_standing.py` | New: the statements, composed from module constants |
| `store/vocabulary.py` | `StandingReach` (`all`, `program`, `member`) and the two automatic withdraw reasons |
| `operations/standing.py` | New: the `standing` operation |
| `operations/withdraw.py` | New: the `withdraw` operation |
| `operations/list_registry.py`, `list_view.py` | The `standing` view |
| `operations/names.py` | `STANDING`, `WITHDRAW` |
| `answering/passage_types.py` | `PassageKind.STANDING_ANSWER` |
| `answering/passages.py` | `StandingAnswer` input, its passages, the size check |
| `operations/pause_context.py` | Reads the standing answers reaching the member and passes them to `assemble` |
| `answering/answering.yaml` | Both prompts describe the kind |
| `operations/set_up_remove.py` | Withdraws on removal |
| `operations/prune.py` | Deletes old withdrawn rows |
| `cli/parser.py`, CLI renderers, `mcp/tools.py`, `mcp/server.py` | The two commands, the view, the two tools and the server instructions text |

### Data Flow

1. The PM tells an agent a ruling. The agent calls `standing` with the text and, if the PM limited it, a program or a member.
2. A run in a member pauses on a question. `handle_pause` gathers context as it does today, and also reads the standing answers that reach the member and are not withdrawn.
3. `assemble` numbers them as passages after the rules, plan, program and request passages and before the PM's stored answers.
4. The answer step cites one when the question is the situation it describes. The check step confirms that. The answer is recorded and the run resumed exactly as today, and `decisions` shows the standing answer among the cited passages.

### State Management

One table. A row is **active** until it is withdrawn, and a withdrawn row is deleted by prune. Nothing else is stored: which standing answers a question was sent is already in the question's stored passages.

## Technical Decisions

### D1: The record

```sql
CREATE TABLE standing_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    text            TEXT NOT NULL CHECK (length(trim(text)) > 0),
    reach           TEXT NOT NULL CHECK (reach IN ('all', 'program', 'member')),
    program_id      TEXT REFERENCES programs (program_id),
    member_id       TEXT REFERENCES members (project_id),
    given_at        TEXT NOT NULL,
    via             TEXT NOT NULL CHECK (via IN ('cli', 'mcp')),
    withdrawn_at    TEXT,
    withdraw_reason TEXT,
    CHECK ((reach = 'all') = (program_id IS NULL AND member_id IS NULL)),
    CHECK ((reach = 'program') = (program_id IS NOT NULL AND member_id IS NULL)),
    CHECK ((reach = 'member') = (member_id IS NOT NULL)),
    CHECK ((withdrawn_at IS NULL) = (withdraw_reason IS NULL))
);
```

- **One text field.** The PM's words carry both the situation and the ruling ("When a merge pauses on unchecked task boxes, check them against the work..."). Splitting them into two fields would make the agent rewrite what the PM said.
- **The text is never edited.** A changed ruling is a withdraw and a new `standing`. The date of a passage is `given_at`, so the newer one wins under the prompts' existing "later date wins" rule even before the old one is withdrawn.
- **AUTOINCREMENT** so an id is never reused after prune, as `answers.seq` does.
- `programs.program_id` and `members.project_id` are the two tables' keys, as `001_baseline.sql` and the `questions` table name them.

### D2: `standing`

`amoeba standing --text TEXT [--program ID | --member NAME]`, MCP tool `standing` with `text`, `program`, `member` and `directory`.

- Neither flag: reach `all`. `--program`: that program, which must exist. `--member`: a Context Forge project name or id, resolved the way `add --project` resolves one, which must be a member. Both flags together is a usage error.
- Result: `outcome` (`given` or `rejected`), `rejection` (`malformed`, `no_such_program`, `no_such_member`), `standing_id`, `reach`, `program`, `member`, `problems`. Exit 1 when rejected, else 0.
- A repeat with the same text and reach as an active row makes a second row. Nothing depends on uniqueness, and `withdraw` removes a duplicate.
- The MCP tool description carries the rule `answer` already carries: it takes only a ruling the PM actually gave, passed on as given, never one the agent composed.
- It can be called from anywhere. It needs a working directory only to resolve `--member` through `cf`.

### D3: `withdraw`

`amoeba withdraw STANDING_ID --reason TEXT`, MCP tool `withdraw`.

- Sets `withdrawn_at` and `withdraw_reason`. The row is left out of every answering run that gathers context after that.
- Result: `outcome` (`withdrawn`, `unchanged` when already withdrawn, `rejected`), `rejection` (`no_such_standing_answer`, `malformed`), `standing_id`, `problems`. Exit 1 when rejected, else 0.
- There is no un-withdraw. Giving the ruling again is the undo.
- Answers already delivered from it stay delivered and stay in `decisions`. Withdrawing changes only what later questions are sent.

### D4: The `standing` view of `list`

`amoeba list standing [--all]`, and `view: standing` on the MCP `list` tool.

- Shows active standing answers, newest first: id, reach (`everything`, `program <id>` or `member <name>`), date and the text.
- `--all` adds withdrawn ones, with the date and reason.
- It is not part of the default `list`, which stays "what needs you".

### D5: The passages

- New `PassageKind.STANDING_ANSWER = "standing_answer"`.
- `assemble` gains `standing_answers: Sequence[StandingAnswer]`, each an id, text and date. Their passages follow the request passage and come before PM answers, in id order. `source` is `standing:<id>`, and `question`, `slice_label`, `question_id` and `member` are unset.
- **Never trimmed.** They count in the size check with rules, plan and program text. When those together exceed `passages_max_chars` the result is the existing `sources_too_large`, and its detail gives the standing answers' share so the PM can tell which to act on: withdraw some, or raise the cap. A ruling the PM gave must not be dropped quietly to make room.
- **Which ones a member is sent:** not withdrawn, and reach `all`, or reach `program` with the member's program, or reach `member` with the member. One query, in `store/standing.py`.
- `rules.md` gains a short section saying standing answers are read too and counted against the cap.

### D6: The prompts

Both steps add `standing_answer` to the list of kinds. The answer step adds:

> A standing_answer passage is a ruling the PM gave ahead of time. Its text describes a situation and says what to do in it. It answers the question when the question is that situation. It has no question line and no slice line, and it holds for every slice unless its own text says otherwise.

The check step adds the matching condition: when a cited passage is a standing_answer, the question is the situation that passage describes.

Nothing else in the prompts changes. "Later date wins" already orders a standing answer against a stored PM answer in the same repo, in both directions.

### D7: The authorize list still applies

An automatic answer that cites a standing answer is still written by a model, which decided that the situation matches. So the member's not-authorized list, the check step and the answer screen apply to it exactly as to any other automatic answer. The concept's statement that a standing answer is the PM's own authorization is carried out in 231, where the PM's text is used unchanged as an instruction and no model writes anything.

### D8: Removal and pruning

- `rm` of a member withdraws, in the same transaction, the active standing answers whose reach is that member, with reason `member_removed`. When `rm` deletes a program, it does the same for reach `program`, with reason `program_removed`. Both reasons are constants in `store/vocabulary.py`. `rm` keeps the `members` and `programs` rows (no statement in the store deletes from either, checked 20261119), so the two references stay valid for withdrawn rows until prune deletes them.
- Prune deletes standing answers withdrawn more than `prune_after_days` ago, in the pass that already prunes settled questions. Active ones are kept without limit: each one exists because the PM gave it, each has `withdraw`, and the size cap in D5 is what bounds their effect.

### D9: No config

No new config key. The cap is `passages_max_chars` and the retention is `prune_after_days`.

## Implementation Details

### API Contracts

`docs/cli-contract.md` gains `amoeba standing` and `amoeba withdraw` sections with the result tables in D2 and D3, the `standing` row in the `list` section, and both names in the Names section. `docs/mcp-server.md` gains the two tools and the `list` view. `docs/store-contract.md` gains the table, why each column exists, and a "Standing answers and who writes them" section covering give, withdraw, removal and prune. The MCP server's instructions text gains one line: the PM gives a ruling for every later case with `standing`, and `withdraw` takes one back.

## Integration Points

### Provides to Other Slices

- 231: the standing answers reaching a member, and their passages, for pauses that are not agent questions.
- 232: `standing` as the way a found ruling is recorded, and `withdraw` as the way a contradicted one is retired.

### Consumes from Other Slices

- 223's context gathering and answering run, unchanged except for the added passages.

## Success Criteria

### Functional Requirements

- A standing answer with reach `all` is cited in an automatic answer in a member that has no stored PM answers.
- One with reach `program` or `member` is not sent to an answering run outside its reach.
- A withdrawn one is not sent, and shows in `list standing --all` with its reason until pruned.
- An answer that cites a standing answer and would authorize a barred item is declined, as today.
- Removing a member withdraws the standing answers that reach only it.
- When rules and standing answers do not fit the cap, the question waits as `sources_too_large` and the detail names the standing answers' size.

### Technical Requirements

- Migration `010` applies to a copy of a store at version 9 with rows in every table, and `EXPECTED_SCHEMA_VERSION` is 10.
- Every statement binds values with `?`.
- Passage assembly tests cover order, numbering, the size check and the reach query with real rows.
- The prompt text in `answering.yaml` and the kind list are tested against `PassageKind`, so a kind cannot be added to one and not the other.
- Ruff, format, pyright and the full suite pass.

### Integration Requirements

- A live test runs 223's fixture pipeline in a fixture repo, asking a question that only a standing answer settles. The run is resumed with an answer citing it.
- The same live test with the standing answer withdrawn ends waiting on the PM.

### Verification Walkthrough

In a fixture repo registered as a member, with the live fixture pipeline from 223:

1. `amoeba standing --text "When an agent asks whether to bump the fixture version, the answer is no: fixture versions are never bumped."` prints the new id.
2. `amoeba list standing` shows it with reach `everything`.
3. Start the fixture pipeline with the question "Should I bump the fixture version?". After the pause, `amoeba list --all` shows the question answered and the run resumed, and `amoeba decisions -j` shows the answer citing a `standing_answer` passage with source `standing:<id>`.
4. `amoeba withdraw <id> --reason "walkthrough"`, then run the pipeline again. `amoeba list` shows the question waiting on the PM.
5. `amoeba list standing --all` shows the withdrawn row and its reason.

## Risk Assessment

### Technical Risks

- **A standing answer stretched to a situation it does not cover.** The model decides the match. The check step is asked the same question independently, the authorize list still applies, and `withdraw` plus a more exact wording is the fix. `decisions` shows every use.
- **Two standing answers that disagree.** The later date wins under the existing rule. Same-second ties decline, as two rules passages would.

## Implementation Notes

### Development Approach

Store first (migration, functions, reach query), then the two operations and the view through the CLI, then the passages and prompts, then `rm` and prune, then MCP, then docs and the live test.

### Special Considerations

- The live store is migrated by code on first use after install. Take a backup of `~/.local/state/amoeba/amoeba.sqlite3` into `~/.local/state/amoeba/backups/` first; restoring is copying it back.
- `scripts/update_live.py` is run after the slice merges.

## Operator Walkthrough

Walked as the person who runs it, by the designing agent.

- **Start.** Nothing to set up. An install with no standing answers behaves as before: the reach query returns nothing and no passage is added.
- **Normal path.** The PM says a ruling to an agent. The agent calls `standing`. From the next paused question in any repo it reaches, the ruling is one of the passages. The PM sees its uses in `decisions`.
- **A waiting question the ruling would have settled.** Giving a standing answer does not go back and answer questions already waiting. The PM answers that one with `answer` as today. Its exit is unchanged: `answer`, `dismiss`, or the run moving on.
- **A wrong ruling.** `withdraw` stops it from the next question. Answers already delivered are not undone; they are in `decisions`, and the runs that got them are the PM's to judge, as with any wrong answer today.
- **A ruling that is too broad.** Withdraw it and give it again with `--program` or `--member`, or with more exact wording.
- **Too many or too long.** The question waits as `sources_too_large` with the sizes in the detail. The PM withdraws some or raises `passages_max_chars`. The next question uses the result. The waiting question exits as any waiting question does.
- **A member or program is removed.** Its standing answers are withdrawn with a reason that says so. Ones with reach `all` are untouched.
- **End state and clearing.** Active rows stay until withdrawn. Withdrawn rows are deleted after `prune_after_days`. To clear everything: `list standing`, then `withdraw` each. There is no state that needs a file edited.
- **Dead ends found:** none. One thing to know: a standing answer cannot yet clear a pause that is not an agent question, such as the merge pause that started scenario F. Those pauses are still skipped until 231.
