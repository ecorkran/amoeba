---
docType: slice-design
slice: standing-answers
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 223
- 228
- 229
interfaces:
- 231
- 232
dateCreated: 20261119
dateUpdated: 20261120
status: not_started
---

# Slice Design: Standing Answers

## Overview

A standing answer is a ruling the PM gives once, ahead of time, in the PM's own words. It names the situation it covers and what to do, and it has a reach: every member, one program, or one member. Every answering run is sent the standing answers that reach the member, as passages the reply can cite. This slice builds the record, three operations (give, list, withdraw) and the passages. It is the first slice of scenario F in the concept, and the architecture's "Standing answers" section is its parent.

## Value

Today the PM's answers count only in the repo they were given in, and only after a question has actually waited there. A ruling such as "CONCERNS reviews never block a merge" has to be given again in every repo, each time after a run has stopped for it. With this slice the PM says it once, to any agent, and it holds everywhere it reaches from the next question on.

## Technical Scope

In:

- The `standing_answers` table (migration `010`) and its store functions.
- `standing` (give), `withdraw` and a `standing` view of `list`, on the CLI and MCP.
- A new passage kind, `standing_answer`, added to every answering run for a member the standing answer reaches.
- The answer and check prompts learn the kind.
- `rm` of a member withdraws the standing answers whose reach is that member.
- Docs: `cli-contract.md`, `mcp-server.md`, `store-contract.md`, `rules.md`.

Out, each in the slice named:

- Handling pauses that are not agent questions, and doing work in a repo (231).
- Promoting a stored answer, and finding rulings without being asked (232).

## Dependencies

### Prerequisites

- 222: the store, migrations, members and programs.
- 223: `handle_pause`, passage assembly, the answering run and its prompts.
- 226: the MCP server, its thin tools and the one `wiring.invoke` both doors call.
- 228: `rm`, the active-member rule in `store/programs.py`.
- 229: the CLI's text and JSON output, `list` and its views, and command naming.
- The store is at schema version 9 (`EXPECTED_SCHEMA_VERSION` in `store/migrations.py`, files `001` to `009`, checked 20261120; 240's slices added `006` to `009`).

### Interfaces Required

- `answering.passages.assemble` (kept by 221, extended by 223) and `operations.pause_context.gather` (223).
- `operations.list_view` and `list_registry` (229).
- `operations.set_up_remove.apply_removal` (228, renamed under 229's `rm`).
- `wiring.invoke` (226).

## Architecture

### Component Structure

| File | Change |
|---|---|
| `store/schema/010_standing_answers.sql` | New table |
| `store/standing.py` | New: insert, withdraw, list, the ones reaching a member, withdraw by member |
| `store/sql_standing.py` | New: the statements, composed from module constants |
| `store/vocabulary.py` | `StandingReach` (`all`, `program`, `member`) and the automatic withdraw reason `member_removed` |
| `operations/standing.py` | New: the `standing` operation |
| `operations/withdraw.py` | New: the `withdraw` operation |
| `operations/list_registry.py`, `list_view.py` | The `standing` view |
| `operations/names.py` | `STANDING`, `WITHDRAW` |
| `answering/passage_types.py` | `PassageKind.STANDING_ANSWER` |
| `answering/passages.py` | `StandingAnswer` input, its passages, the size check |
| `operations/pause_context.py` | Reads the standing answers reaching the member and passes them to `assemble` |
| `answering/answering.yaml` | Both prompts describe the kind |
| `operations/set_up_remove.py` | Withdraws on member removal |
| `wiring.py`, `cli/parser.py`, CLI renderers, `mcp/tools.py`, `mcp/server.py` | The two commands through `wiring.invoke`, the view, the two tools and the server instructions text |

### Data Flow

1. The PM tells an agent a ruling. The agent calls `standing` with the text and, if the PM limited it, a program or a member.
2. A run in a member pauses on a question. `handle_pause` gathers context as it does today, and also reads the standing answers that reach the member and are not withdrawn.
3. `assemble` numbers them as passages after the rules, plan, program and request passages and before the PM's stored answers.
4. The answer step cites one when the question is the situation it describes. The check step confirms that. The answer is recorded and the run resumed exactly as today, and `decisions` shows the standing answer among the cited passages.

### State Management

One table. A row is **active** until it is withdrawn, and then **withdrawn**, which is terminal. Rows are never deleted: a delivered answer cites a standing answer as `standing:<id>`, and the question's passage record holds the id, kind, source and date but not the text (223 D10), so the row is where that text stays readable. This matches the architecture: the question and answer rows are the record and are kept (228 D9). Bounded: each row exists because the PM gave a ruling, so they grow with the PM's rulings, as stored PM answers do. Which standing answers a question was sent is already in the question's stored passages, so nothing else is stored.

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
- **AUTOINCREMENT** so an id is never reused, as `answers.seq` does.
- `programs.program_id` and `members.project_id` are the two tables' keys, as `001_baseline.sql` and the `questions` table name them. Neither row is ever deleted (no statement in the store deletes from `members` or `programs`, checked 20261119), so both references stay valid.

### D2: `standing`

`amoeba standing --text TEXT [--program ID | --member NAME]`, MCP tool `standing` with `text`, `program`, `member` and `directory`.

- Neither flag: reach `all`. `--program`: that program, which must exist. `--member`: a Context Forge project name or id, resolved the way `add --project` resolves one, which must be an active member. Both flags together is a usage error.
- Result: `outcome` (`given` or `rejected`), `rejection` (`malformed`, `no_such_program`, `no_such_member`), `standing_id`, `reach`, `program`, `member`, `problems`. Exit 1 when rejected, else 0.
- A repeat with the same text and reach as an active row makes a second row. Nothing depends on uniqueness, and `withdraw` removes a duplicate.
- **Who may call it.** Like `answer`, it is called by an agent, for the PM (architecture operations table). The MCP tool description carries the rule `answer` already carries: it takes only a ruling the PM actually gave, passed on as given, never one the agent composed. That is the same control `answer` has, and within this slice it is enough because a standing answer gains no power `answer` lacks: every automatic answer that cites one still passes the authorize list, the check step and the answer screen (D7). What changes in 231, where the text becomes an unscreened instruction, is the architecture's decision and 231's to build.
- It can be called from anywhere. It needs a working directory only to resolve `--member` through `cf`.

### D3: `withdraw`

`amoeba withdraw STANDING_ID --reason TEXT`, MCP tool `withdraw`, called by an agent, for the PM, under the same rule as `standing`.

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
- `assemble` gains `standing_answers: Sequence[StandingAnswer]` (keyword-only, after `program_sources`), each an id, text and date. Their passages follow the request passage and come before PM answers, in id order. `source` is `standing:<id>`, and `question`, `slice_label`, `question_id` and `member` are unset.
- **Never trimmed.** They count in the size check with rules, plan and program text. When those together exceed `passages_max_chars` the result is the existing `sources_too_large`, and its detail gives both shares (rules, plan and program; standing answers) so the PM can tell which part is over: withdraw some, or raise the cap. A ruling the PM gave must not be dropped quietly to make room. The architecture records this as the one accepted new stop of scenario F. With the cap at 250,000 characters and rulings of a few hundred, it takes a great many.
- **Which ones a member is sent:** not withdrawn, and reach `all`, or reach `program` with the member's program, or reach `member` with the member. One query in `store/standing.py`, taking the member's `project_id` and `program_id` as bound parameters. It does not read or join `members`: 228 D8 gives every member read to `store/programs.py` and an AST test enforces it. `gather` already holds the active `Member`, which carries both values.
- `pause_context._read_store` runs the query in the same read transaction as `pm_precedent`, and `_StoredFacts` gains the result.
- `rules.md` gains a short section saying standing answers are read too and counted against the cap.

### D6: The prompts

Both steps add `standing_answer` to the list of kinds. The answer step adds:

> A standing_answer passage is a ruling the PM gave ahead of time. Its text describes a situation and says what to do in it. It answers the question when the question is that situation. It has no question line and no slice line, and it holds for every slice unless its own text says otherwise.

The check step adds the matching condition: when a cited passage is a standing_answer, the question is the situation that passage describes.

Nothing else in the prompts changes. "Later date wins" already orders a standing answer against a stored PM answer in the same repo, in both directions.

### D7: The authorize list still applies

An automatic answer that cites a standing answer is still written by a model, which decided that the situation matches. So the member's not-authorized list, the check step and the answer screen apply to it exactly as to any other automatic answer. The concept's statement that a standing answer is the PM's own authorization governs 231, where the PM's text is used unchanged as an instruction and no model writes anything. The architecture's "Standing answers" section records both.

### D8: Removal

`rm` of a member withdraws, in the same transaction, the active standing answers whose reach is that member, with reason `member_removed` (a constant in `store/vocabulary.py`). Reach `program` and `all` are untouched: `rm` never deletes a program (229 hides empty programs instead), so there is no program removal to follow. A member registered again later does not get its withdrawn standing answers back; the PM gives them again.

### D9: No config

No new config key. The cap is `passages_max_chars`.

### D10: Failures

- **The reach read in `handle_pause`.** It is part of `_read_store`'s one read transaction, so it fails as that read does today: a busy or failed store is a `StoreError`, exit 3, before any claim is written. No new decline reason.
- **`--member` resolution.** A `cf` failure, timeout or unusable output is exit 3 with nothing written, as for `add` and every other operation that calls `cf`. A name `cf` resolves that is not an active member is `rejected / no_such_member`.
- **`standing` and `withdraw` writes.** A busy store is exit 3 with nothing written, as for every other write. Each is one transaction, so there is no partial state.
- **`rm`'s withdraw.** It is inside `rm`'s transaction, so it commits or fails with the removal.

## Implementation Details

### API Contracts

`docs/cli-contract.md` gains `amoeba standing` and `amoeba withdraw` sections with the result tables in D2 and D3, the `standing` row in the `list` section, and both names in the Names section. `docs/mcp-server.md` gains the two tools and the `list` view. `docs/store-contract.md` gains the table, why each column exists, and a "Standing answers and who writes them" section covering give, withdraw and removal, and that rows are kept. The MCP server's instructions text gains one line: the PM gives a ruling for every later case with `standing`, and `withdraw` takes one back.

## Integration Points

### Provides to Other Slices

- 231: the standing answers reaching a member, and their passages, for pauses that are not agent questions.
- 232: `standing` as the way a found ruling is recorded, and `withdraw` as the way a contradicted one is retired.

### Consumes from Other Slices

Each is changed here, and the change is the whole of it:

- **221/223 `assemble`:** gains `standing_answers: Sequence[StandingAnswer]`, keyword-only. The `StandingAnswer` type lives in `answering/passages.py`, so the library still imports nothing from the store.
- **223 `answering.yaml`:** both prompts gain the `standing_answer` kind (D6).
- **223 `pause_context.gather`:** same signature; `_read_store` gains the reach query (D5).
- **228/229 `rm`:** `apply_removal` withdraws member-reach standing answers in its transaction (D8).
- **229 `list`:** gains the `standing` view on `list_view` and the MCP `list` tool's `view` argument.
- **226 `wiring.invoke`:** dispatches `standing` and `withdraw` for both doors, with no logic in either door.

## Success Criteria

### Functional Requirements

- A standing answer with reach `all` is cited in an automatic answer in a member that has no stored PM answers.
- One with reach `program` or `member` is not sent to an answering run outside its reach.
- A withdrawn one is not sent, and shows in `list standing --all` with its reason.
- An answer that cites a standing answer and would authorize a barred item is declined, as today.
- Removing a member withdraws the standing answers that reach only it.
- When rules and standing answers do not fit the cap, the question waits as `sources_too_large` and the detail gives both shares.

### Technical Requirements

- Migration `010` applies to a copy of a store at version 9 with rows in every table, and `EXPECTED_SCHEMA_VERSION` is 10.
- Every statement binds values with `?`, and the AST test that keeps `members` reads in `store/programs.py` passes unchanged.
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

Store first (migration, functions, reach query), then the two operations and the view through the CLI, then the passages and prompts, then `rm`, then MCP, then docs and the live test.

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
- **Too many or too long.** This is a stop the slice adds, and the architecture accepts it. The question waits as `sources_too_large` with both shares in the detail. When the standing answers' share is what tips it over, `withdraw` is the exit and needs no file edit; the next question uses the result. When rules, plan and program alone are over, that question was already too large before this slice, and its exit is unchanged (raise `passages_max_chars` or shorten the rules). The waiting question exits as any waiting question does.
- **Store busy or `cf` failing.** Exit 3 with nothing written; the call is safe to repeat.
- **A member is removed.** Its member-reach standing answers are withdrawn with `member_removed`. Program and `all` reach are untouched.
- **End state and clearing.** Active rows stay until withdrawn. Withdrawn rows stay as the record of what delivered answers cited, and are bounded by the number of rulings the PM gives. To stop everything applying: `list standing`, then `withdraw` each. There is no state that needs a file edited.
- **Dead ends found:** none. One thing to know: a standing answer cannot yet clear a pause that is not an agent question, such as the merge pause that started scenario F. Those pauses are still skipped until 231.
