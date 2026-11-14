---
docType: slice-design
slice: human-cli
project: amoeba
parent: user/architecture/220-slices.program-tool.md
dependencies:
- 226-slice.mcp-server
- 228-slice.state-home-and-question-lifecycle
interfaces:
- 227-slice.program-dependencies
dateCreated: 20261113
dateUpdated: 20261113
status: not_started
---

# Slice Design: Human CLI

## Overview

The command works, but only for an agent: it takes a YAML file to register anything, prints JSON for everything, and names commands with underscores. This slice makes it usable by a person without changing what any operation decides.

- Every command prints text by default and the same result as JSON with `-j`/`--json` (D2).
- CLI names are kebab-case; MCP names stay snake_case; both come from `names.py` (D1).
- `set_up` becomes two operations, `add` and `rm`, on both doors (D4, D5, D6).
- `list` is the one view of what needs the PM, what is running and settled, and what is registered (D3).
- A member that names no rules reads the config's default rules files, each skipped when absent. Duplicate sections are dropped and `@path` imports are followed (D7 to D10).
- The reinstall and the hook change run back to back (D13). `docs/rules.md` explains rules from the user's side (D12).

**Value:** the PM registers a repo with one command, sees what needs a decision at a glance, and reads every result without a JSON viewer. A repo's rules work with no setup.

## Why the rules defaults matter

The answering model sees the member's rules as evidence for what the repo allows, and cites them. Rules and plan passages are never trimmed, so what they take is what the PM's earlier answers cannot have. This repo's `CLAUDE.md` is 19.8 KB, `AGENTS.md` adds 4.1 KB of its own, all of `.claude/rules/` is 52.2 KB and slice 226's plan files are 143 KB. The default is therefore the two root files, about 24 KB after duplicates; scoped language rules are opt-in through `--rules`.

## Technical Scope

**Included:** the names (D1); text rendering and `-j` (D2); `list` and its three registered views (D3); `add` and `rm` (D4 to D6); `rules_from` on members, `default_rules_paths` and `default_consumed` in the config (D7); optional default entries, duplicate dropping and import following (D8 to D10); migration 005 (D11); docs, the 227 design update and the cutover (D12, D13); tests (D14).

**Excluded:**

- Changing any operation's decision logic. `add` and `rm` build a request for the existing `set_up` engine, which keeps its module names and every guard.
- Commands that edit `config.yaml`. It stays the one file a person edits.
- Deleting a program row. A program is the target of its removed members' records (the foreign key), so the row cannot go while that history exists. D3 hides programs with no members and no concept instead, and says why what is left is bounded.
- Colour, paging and shell completion.
- Trimming rules by their `paths:` front matter. Every selected file is sent whole.

## Dependencies

- **226 merged:** `OperationName`, the tool table, `wiring.invoke`, `build_parser()`, `mcp/detached.py` (which builds the `handle_pause` command line from the name), and 226's parity tests.
- **228:** soft removal, `member_has_open_questions`, `prune_after_days`, `state_layout()`.
- **222 to 224:** `SetUpRequest` and its checks, `status` and its models, `decisions`, `project_names`, the `members` table.
- **Context Forge:** `cf list projects --json` gives `id`, `name` and, for most entries, `projectPath` (checked 20261113; some entries have none).
- No new packages, no Squadron or Context Forge change.

## Architecture

```
src/amoeba/
├── operations/names.py          # + ADD, RM, LIST; - SET_UP; cli_name
├── operations/add.py            # AddRequest; builds a SetUpRequest, calls set_up
├── operations/rm.py             # RmRequest; same
├── operations/list_view.py      # ListRequest, ListSubject, the four views
├── operations/list_registry.py  # programs, members, dependencies rows
├── operations/set_up_*.py       # + rules_default on MemberRequest; - rules_paths_required
├── store/schema/005_member_rules_from.sql
├── store/settled.py             # settled questions newer than a time
├── upstream/context_forge/projects.py   # + project_details (name, path or null)
├── config/user_config.py        # + default_rules_paths, default_consumed
├── answering/source_reads.py    # optional entries, import following
├── answering/rule_imports.py    # finds @path imports in a rules file's text
├── answering/passages.py        # duplicate rule sections dropped once, here
├── cli/parser.py                # build_parser(), kebab names, -j parent parser
├── cli/commands.py              # one runner per command
├── cli/render/                  # pure result -> text: add, rm, list, answer, ...
├── mcp/tools.py, mcp/detached.py
└── wiring.py                    # invoke: add, rm, list cases
docs/rules.md                    # new; docs/cli-contract.md and others rewritten
```

## Decisions

### D1. Names

`OperationName` values stay snake_case: they are the MCP tool names and the `operation` in JSON `next` entries. A `cli_name` property gives the CLI form (`_` to `-`). `build_parser()` registers each command by `cli_name`, so `handle-pause` and `mark-read` exist once, derived. `dismiss`, `answer`, `status`, `decisions`, `retract`, `add`, `rm`, `list` have no underscore and are unchanged. `rm` also answers to `remove`. There is no alias for an old CLI name: a stale caller gets argparse's invalid-choice error and exit 2. `mcp/detached.py` builds its command line from `cli_name` and passes `--json`, so the receipt's log stays machine-readable.

### D2. Text output and `-j`

A parent parser adds `-j`/`--json` to every command, placed after the subcommand as `sq` and `cf` do. With it a command prints exactly what it prints today (`result_document`). Without it, a pure function in `cli/render/` turns the same result into text:

- The first line says what happened (`added`, `unchanged`, `rejected: ...`).
- Prose is cut to 100 columns with `…` (a question, an answer, a reason); the full text is in `-j`. Commands and paths are never cut: they sit on their own line, indented, and may run past 100 columns, so they can be pasted.
- No colour, no tables wider than the limit.
- Errors stay `error: <Name>: <message>` on stderr; exit codes (0, 1, 2, 3) are unchanged.
- `handle-pause` prints one line (`answered`, `waiting_on_pm: <reason>`, `skipped: <reason>`, with its detail). Nothing parses the hook's output.

Every renderer is tested against fixture results with the exact expected text.

### D3. `list`

`amoeba list [SUBJECT] [--all] [--program ID] [-j]`. One operation, `list`, with request `{subject, all, program}`.

| Subject | What it shows | Source |
|---|---|---|
| none | what needs the PM | the `status` operation, same code and same sweep |
| `programs`, `program` | each program: members, concept | store |
| `members`, `member` | each active member: CF name, id, repo path, program, rules, allow/deny, dependencies | store, `cf list projects` |
| `dependencies`, `dependency` | each pair: provider to consumer, `consumed` | store, `cf list projects` |

Default view, in order: **Waiting on you** (each `WaitingEntry`: member, run, how long, reason, the question cut to one line, and the command to answer it); **Paused, not handled** (runs whose `pause` is `unhandled`, `claim_stale` or `answered_unresumed`, with the command that handles them and, for the first two, the newest calls-log line); **Unplaced runs**; **Problems** (`sweep_problem`, `file_problems`, `problems`). Nothing waiting prints `Nothing needs you.`.

`--all` with `programs` also lists programs that have no members and no concept (D3, last paragraph); with `members` or `dependencies` it is a usage error, exit 2. With no subject it adds every other run under its member, then **Settled**: questions answered or closed within `prune_after_days` (the window the system already treats as recent; older ones are in `decisions --since`). `store/settled.py` reads them.

JSON: `list -j` is the `status` result document, nothing more. `list --all -j` is the same document plus one top-level key `settled`. The registered subjects have their own documents.

A member's repo path is CF's `projectPath`. When CF has none the text says `(no path in Context Forge)` and JSON has null. A member whose CF project is gone shows its id with `(not in Context Forge)`. A removed member is not listed.

`status` stays as its own operation and tool: it is the agent report, with `next` actions an agent calls, and the form a script reads. `list` is the person's view over the same result; the two share one code path, so they cannot disagree.

**Failures.** The registered views and `add` read Context Forge. `cf` absent, failing or timing out is exit 3 with the error and no partial view, as in 222 and 224. Amoeba does not match project names itself: `cf` resolves a name or id, its answer stands, and a reference it cannot resolve is `not_a_project` carrying its message (so a name `cf` finds ambiguous is whatever `cf` reports). A stored member id missing from `cf list projects` is shown as `(not in Context Forge)`.

**Empty programs.** A program with no active members and no concept is hidden from `list programs` unless `--all` is given. The row cannot be deleted (Excluded), and it is bounded: rows exist only for names someone typed to `--program`, a few at most, each a handful of bytes. `add` says `created program X` when it creates one, so a typo shows at once, and the fix is `rm` then `add --program right`; adding to the same name later revives the row.

### D4. `add`

`amoeba add [--program ID] [--project NAME] [--rules PATH]... [--default-rules] [--no-rules] [--allow KEY]... [--no-allow] [--deny KEY]... [--no-deny] [--depends-on PROVIDER[:MODE]]... [--concept MEMBER:PATH] [-j]`, or `amoeba add --file PATH`.

- `--project` names a Context Forge project (name or id); absent means the working directory's. From one repo the PM can register others.
- `--rules`, `--default-rules` and `--no-rules` are mutually exclusive. `--rules` replaces the member's rules with the named entries; `--default-rules` returns it to the config default; `--no-rules` stores none. None of the three leaves an existing member's rules as they are and gives a new member the default.
- `--allow` and `--deny` replace the member's list with the keys given; they do not add to it. `--no-allow` and `--no-deny` store an empty list. Neither flag leaves the list as it is. On MCP, `authorize_allow: []` is the empty list and an omitted field leaves it.
- `--depends-on PROVIDER:MODE` takes `from_source` or `from_release`; without `:MODE` it is the config's `default_consumed`.
- `--concept MEMBER:PATH` splits at the first `:`; an empty side is a usage error.
- `--file PATH` (or `-` for stdin) is the bulk path. The CLI reads the YAML (the existing `set_up` request shape) into the request's `bulk` field; it cannot be combined with other flags. `AddRequest` has `bulk` (a whole `SetUpRequest`) or the single-member fields, never both, so the MCP tool takes a bulk request too and there is nothing only one door can do.
- The MCP `add` tool takes the same fields as the flags (`rules_paths`, `rules_default`, `authorize_allow`, `authorize_deny`, `depends_on`, `concept`, `program`, `project`, `bulk`) plus `directory`.

`add` makes a `SetUpRequest` (the one member, or `bulk` as given) and calls the `set_up` engine. Both forms return the engine's result document, so the `add` renderer prints one line per changed member and program (`created program X`, `added member Y`, `changed ...`) and handles any number of members. `-j` prints that document. Every existing guard applies and is reported with its existing code: `not_a_project`, `member_of_other_program`, `unknown_provider`, `self_dependency`, `unknown_authorize_item`, `concept_member_not_member`. `rules_paths_required` is removed, since a new member now has a default. A repeat changes nothing and says `unchanged`.

### D5. Which program `add` uses

`--program ID` names it (created when new). Without it: the member's current program when it is registered, else a new program whose id is the member's Context Forge project name. A directory with no Context Forge project and no `--project` is rejected as `not_a_project` with text that says to run `cf init` or pass `--project`; nothing is created. If a program with that id already exists (one the PM named by hand to match), the member joins it, and the text says `added member Y to existing program X` rather than `created program X`, so a surprise is visible in the output. A repo never needs a program name just to exist, and a re-run never tries to move a member.

### D6. `rm`

`amoeba rm [MEMBER]... [--pair PROVIDER:CONSUMER]... [--concept] [--program ID] [-j]` (also `remove`). No `MEMBER` and no other flag: the working directory's project. `MEMBER` is a Context Forge name or id (an id works after the CF project is deleted). All named members and pairs must belong to one program, found from the store, or `--program` names it; members of different programs are rejected as `member_of_other_program`. `--concept` clears the program's concept, which is the only way to remove a concept member. `rm` builds the `remove` section of a `SetUpRequest`, so soft removal, `member_has_open_questions` and `not_a_member` are 228's, unchanged. A refusal for open questions prints the keys and the commands (`answer`, `dismiss`) that clear them.

### D7. Where the default rules live

`config.yaml` gains two required keys, with no default in code (the config rule): `default_rules_paths` (a non-empty list of `rules_paths` entries; the example is `[CLAUDE.md, AGENTS.md]`) and `default_consumed` (`from_source` or `from_release`). A missing key fails with the key named, like every other.

Whether a member's rules are the default or named is stored, not inferred, because an empty list is already a valid named choice (no rules). Migration 005 (D11) adds `members.rules_from` (`named` or `config_default`). At answering time a `config_default` member reads the config's entries as they are then, so editing the config changes every default member. `MemberRequest` gains `rules_default: bool`; `rules_paths` keeps its meaning (omitted leaves it, given replaces it).

### D8. Default entries are optional

An entry from the config default that matches no file at the pinned commit is skipped. If every default entry is skipped the question declines `sources_missing` and waits on the PM; the detail names the entries tried (`no rules file found; tried: CLAUDE.md, AGENTS.md`). An entry the member named that matches nothing still fails the whole selection, as today. For an optional entry in a subdirectory, whether the directory exists is read with `git ls-tree` (exit 0 and empty output means absent); any non-zero exit is still `sources_unreadable`, so "absent" never comes from an error. The caller sets the choice; `source_reads` has no list of its own.

### D9. Duplicate rule sections are dropped

A rule passage whose text equals an earlier rule passage (after cutting at headings, compared exactly) is dropped; the first file keeps it and a citation names that file. Plan and program passages are never dropped. One helper in `passages.py` decides which pieces are new; both `read_committed_sources` (its running size, so duplicates do not trip `sources_too_large` early) and `_committed_passages` (numbering) call it. A section edited in one file but not the other is two different passages and both stay: it costs size, not correctness. Measured on this repo: 17.9 KB of `AGENTS.md` is dropped.

### D10. `@path` imports are followed

In a rule file ending `.md`, an import is a token starting with `@` at the start of a line or after whitespace, outside fenced blocks and inline code, whose path has no whitespace, ends in `.md` once trailing `.,;:)` is removed, and does not start with `/` or `~`. It resolves against the importing file's directory and must stay inside the repository. The imported file is read at the pinned commit, as a rule file placed after its importer, and may import in turn. Limits:

- **Depth:** `IMPORT_DEPTH` (3). Deeper than that declines `sources_unreadable`, the detail giving the chain; the repo file is what to fix.
- **Cycle or repeat:** a file already selected is not read twice; no error.
- **Missing target:** skipped when the chain began at a config-default entry; `sources_missing` (detail `import @x in F matches no file`) when it began at a named entry.
- **Size:** imported text counts against `passages_max_chars` like any rule text.

Requiring `.md` keeps `@types/node` and `@modelcontextprotocol/server` (this repo's `CLAUDE.md` has the latter in a commit example) from being read as imports.

### D11. Migration 005

`ALTER TABLE members ADD COLUMN rules_from TEXT NOT NULL DEFAULT 'named' CHECK (rules_from IN ('named','config_default'))`. `EXPECTED_SCHEMA_VERSION` becomes 5. Existing members, including the three registered ones (all in `trading`) with `["CLAUDE.md"]`, stay `named` and behave as before. Updates to `docs/store-contract.md` and the schema test.

### D12. Documents

`docs/rules.md` (new) explains rules from the user's side: what is read and why; that only committed files at the target are read; where it is set (`add`, the config default); the defaults and how to change them (`--rules`, `--default-rules`, `--no-rules`, editing `default_rules_paths`); how to see what a member uses (`list members`); duplicates and imports; what a missing file does (default skipped, named fails, nothing found waits on the PM); the size cap and how to size it. `docs/config-contract.md` gets the two keys and an example `passages_max_chars` of 250000 with the sum it must cover (the rules, the slice's plan files, the program concept, room for precedent). The other docs that name commands (`cli-contract`, `mcp-server` with the restart note, `squadron-hook`, README, CHANGELOG) move to the new names. The 220 architecture is amended in this slice: its operations table lists `add`, `rm` and `list` in place of `set_up`, and its "same names" principle says the MCP names are snake_case and the CLI names kebab-case, both from one list. The 227 design already uses the new names.

### D13. Cutover

One step in the implementation, run in this order with no pause between:

1. Edit the PM's `~/.config/amoeba/config.yaml`: add `default_rules_paths` and `default_consumed`, set `passages_max_chars` to 250000.
2. `uv tool install --force .` and `sq config set pipeline.on_pause_command "amoeba handle-pause"` in one command line.
3. For each member `amoeba list members` shows with named rules, `amoeba add --project NAME --default-rules`, so the registered members also read `AGENTS.md` and follow the config from then on.

Between 1 and 2 the old installed command rejects the new keys, so a pause landing in those seconds is logged as an error and shows in `list` as not handled, with the command that handles it. Open agent sessions keep running the old MCP server, whose detached `handle_pause` now fails with the CLI's invalid-choice error. They need a restart; the docs say so and the walkthrough's last check confirms a fresh session sees the new tools. The registered `amoeba-mcp` command name does not change.

### D14. Tests

All with fixtures and the live fixture pipeline; nothing waits on real use.

- **Names:** every `OperationName` has a CLI command (by `cli_name`) and a tool row, and nothing else; `remove` aliases `rm`; singular and plural `list` subjects; `--all` with a registered subject is exit 2.
- **Renderers:** exact text for each result shape, including a 300-character question cut to 100 columns and a run with no path in CF.
- **`add` and `rm`:** the request each builds, program resolution (D5), the default rules for a new member, `--default-rules` and `--no-rules`, the existing guards through the new door, and `--file` equal to the old `set_up`.
- **Rules:** git-fixture repos for default entries present, one present, none present, a named entry missing, an entry in a missing subdirectory. The duplicate and import tests use copies of this repo's real `CLAUDE.md` and `AGENTS.md`, plus fixtures for depth, cycle, a missing import under each source, a fenced `@x.md`, and `@types/node`. A test shows the early size check counts deduplicated text.
- **Store and config:** migration 005 from a version-4 database with a member present; a config missing each new key fails naming it.
- **Live:** `tests/live` runs a pipeline that pauses, through `amoeba handle-pause` set as the hook, and checks `list` shows the question or its answer; the live MCP walkthrough uses the new tool names.

## Operator walkthrough

- **First run.** In a repo: `amoeba add`. Text says the member was added to a new program named after the CF project, rules `default (CLAUDE.md, AGENTS.md)`. No CF project: `rejected: not_a_project`, with the fix in the text, nothing written.
- **A group.** In the second repo: `amoeba add --program first --depends-on first:from_source`. A provider that is not a member is `unknown_provider`, naming it.
- **A pause arrives.** The hook runs `amoeba handle-pause RUN`. It answers, or the question waits. `amoeba list` shows it under Waiting on you with the reason and the `amoeba answer` command. If the hook never ran, the run shows under Paused, not handled with the command to run.
- **A question can't be answered.** `sources_missing`: the detail names what was tried. The PM adds a file, or `add --rules PATH`. `sources_too_large`: the detail gives the size and the limit; raise `passages_max_chars` in `config.yaml`. Both are in `list` with that text.
- **Changing rules.** `amoeba add --rules docs/rules.md` (replace), `amoeba add --default-rules` (back). `amoeba list members` shows which.
- **Ending.** `amoeba rm` removes the working directory's repo. Open questions refuse it, with the keys and the commands that clear them. Removing the concept's member needs `--concept` to clear the concept first.
- **Dead ends checked.** A new member has rules. A config missing a key fails naming the key. An old command name exits 2 with the valid names listed. A stale agent session needs a restart, said in the docs. A program left with 0 members is visible and refilled by `add --program`.

## Success Criteria

As in the slice plan entry: text and `-j` on every command and `list -j` equal to the status document; `amoeba add` registering with no other flag; default rules read, skipped and declined as D8 says, each section once; named entries still failing; every member setting settable from the CLI; the hook handled through `amoeba handle-pause` and the old name gone from the code, docs and hook.

## Risks

- **Rename reach.** Every command, a hook and the tests change together. The parity tests and the live pipeline test are the check.
- **Text format churn.** Renderer tests hold the format, so a later change shows as one deliberate diff.
- **Import false positives.** Limited by D10's `.md` rule; a missed import is never an error under a default entry.
