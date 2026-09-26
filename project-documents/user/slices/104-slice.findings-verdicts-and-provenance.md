---
docType: slice-design
slice: findings-verdicts-and-provenance
project: amoeba
parent: user/architecture/100-slices.substrate-run-state-store.md
dependencies: [101, 102, 103]
interfaces: [105, 106, 108, 109]
dateCreated: 20260926
dateUpdated: 20260926
status: not_started
---

# Slice Design: findings-verdicts-and-provenance

## Overview

The store holds nodes, blocked states, a journal, and an inbox, but no record of what a review said. This slice adds that record, and nothing more:

1. **Verdict records.** Each review result is stored with where it came from: the verdict, how Squadron reached it, whether the review was actually a provider failure, the model, the reviewed commit, the Squadron run, and the Squadron version.
2. **Findings, matched by content.** Each finding in a review is stored and given a content key. Squadron's `F001`-style numbers are kept only as data, because they are positions in a list and change every run.
3. **"What changed since last round?"** For any review, the store says which findings are new, which came back, and which are gone.
4. **A trust label on every verdict.** It separates a real PASS from one Squadron worked out itself, from a review whose findings did not parse, and from a provider failure.

The out-of-process Judge gets a way to submit reviews through the inbox. Two new inspection listings make it all visible.

**Split out on 20260926** (the first version of this design covered all of it):

- **Slice 108:** parsing Squadron's review output, and an `amoeba ingest review` command.
- **Slice 109:** judge samples and the calibration report, mechanical check results, and task-progress and dev-log records.

The full first draft, including the parser mapping and the judge and check designs, is in git history at commit `c525a63`. Slices 108 and 109 start from it.

## Value

Developer value.

- The Runner (120) can ask "is this the same finding as last round?" and "can I trust this PASS?" from the store alone. Neither CF's gate nor Squadron's output answers those.
- A Judge outside the process can record a review through the inbox, like every other outside writer.
- Every stored review says which Squadron version produced it. When Squadron changes its output, the affected records can be found.

## Technical Scope

**Included**

- Migration `005`, with two tables: `verdicts` and `finding_observations`.
- `amoeba.store.finding_identity`: the matching rule. Pure functions, versioned, importable without opening a store.
- Store operations: `record_verdict`, `verdict`, `verdicts`, `observations`, `findings`, `finding_changes`.
- The trust label on verdict records.
- A `verdict` inbox submission type, and a change to how `amoeba submit` reads flags, so number, true/false, and list fields work.
- `amoeba inspect verdicts` and `amoeba inspect findings`, registered in 102's listing registry. The registry gains options that take a value (`--node ID`).
- `docs/evidence-contract.md`, and updates to `store-contract.md`, `inbox-contract.md`, and `CHANGELOG.md`.

**Excluded**

- Reading Squadron's JSON or review files: slice 108. Here, callers pass values that are already parsed.
- Judge samples, calibration, check results, task progress, and dev-log records: slice 109.
- Noticing reviews that someone else launched: slice 105.
- Deciding whether a reworded finding is "the same issue": initiative 140. The matching rule only handles formatting differences.
- Marking findings addressed, disputed, accepted, or rejected: 120 and 140.
- Tagging findings by how checkable they are: 120.

## Dependencies

### Prerequisites

- **Slice 101:** `Store`, nodes, the migration mechanism (`EXPECTED_SCHEMA_VERSION` goes from 4 to 5).
- **Slice 102:** the inspection listing registry, `Store.open_read_only`, the command journal (a verdict may point at the Squadron run command that produced it), and the writer guard.
- **Slice 103:** the inbox submission types and `amoeba submit`, and its retry rule: resubmitting the same id is a no-op.
- **PyYAML, dev-only** (with `types-PyYAML`). Tests read the real review files' frontmatter with it. Slice 108 makes it a runtime dependency.

### Interfaces Required

From the store: `get_node`, `journal_entry`, error translation in `_execute`, and the one-transaction pattern that `apply_submission` uses. From the inbox: the table of payload models, the table of apply functions, and `validate_envelope`. From the CLI: `LISTINGS`, `run_listing`, and `_takes_object` in `cli/submit.py`.

**What Squadron emits today** (checked 20260926 against squadron 0.14.0, and confirmed by the Squadron session):

- Each finding is `{id, severity, category, summary, location}`.
  - `id` is a position number (`F001`, `F002`, …).
  - `severity` is lowercase.
  - A missing location is the literal text `unverified`.
- `verdictSource` is `stated` or `derived`. A committed Squadron design adds `imposed`: Squadron capped the verdict itself.
- `fallback_used` is set in exactly two cases, both in JSON only:
  - a derived verdict, whose findings did parse;
  - a CONCERNS or FAIL whose findings did not parse.
- A provider failure writes `verdict: UNKNOWN` into the normal review slot.
- No Squadron output carries the run id or the Squadron version yet. Squadron has an issue open to add both.

## Architecture

### Component Structure

```
src/amoeba/store/
  finding_identity.py   normalize_location, normalize_summary, finding_identity; RULE_VERSION
  evidence_models.py    word lists (enums), VerdictInput, FindingInput, VerdictRecord, trust-label function
  sql_evidence.py       every statement and column name for the two tables
  mapping_evidence.py   row → record mapping (fails on an unknown enum value)
  verdicts.py           VerdictOperations mixin
  schema/005_verdicts_and_findings.sql
src/amoeba/inbox/
  evidence_payloads.py  VerdictPayload, FindingPayload (pydantic) → VerdictInput
src/amoeba/cli/
  inspect_evidence.py   the two listings and their row functions
tests/fixtures/sq_reviews/   real Squadron output (two JSON captures already committed; review files added here)
docs/evidence-contract.md
```

This follows the pattern 101–103 set for each concern: models, SQL, mapping, and an operations mixin added to `Store`. `store.py`, `cli/inspect.py`, and `cli/main.py` are near their line budgets, so the listing definitions live in `inspect_evidence.py` and are appended to `LISTINGS`. The store never imports the inbox's pydantic models. `finding_identity.py` imports nothing from the store.

### Data Flow

**Recording a review:** the Runner calls the store directly; the Judge goes through the inbox.

```
record_verdict(VerdictInput)                    # one transaction
  id already recorded?          → return the existing record (a WARNING if the content differs)
  node exists in this project?  → else fail
  journal entry, if given, is on the same node → else fail
  provider failure ⇒ verdict is UNKNOWN and there are no findings → else fail
  insert the verdict row (recorded_seq is assigned here: arrival order)
  for each finding, in the order given:
      key = finding_identity(location, summary)
      insert an observation row (the raw text, the normalized text, the key, the rule version)
```

Through the inbox, the `verdict` type runs the same writer inside `apply_submission`'s transaction. The submission id becomes the record id. A failed check is recorded as a rejection with a reason, as 103 does for its types. An unknown word in an enum field never gets that far: the payload fails validation and the file is quarantined.

**What changed since the last round:**

```
finding_changes(verdict_id)
  target = that verdict; if its findings can't be compared → "not comparable", empty lists
  previous = the latest earlier verdict on the same node, for the same review type,
             whose findings can be compared
  each target finding: RECURRING if its key is in previous, else NEW
  GONE = keys in previous that are not in target
```

Findings can be compared when the trust label is `stated`, `derived`, `imposed`, or `unattested`. A provider failure, an unparsed verdict, or a review whose findings did not parse is never a baseline. Otherwise a failed round would report every open finding as fixed.

### State Management

All durable state lives in the project store, in the two new tables. The trust label and the new/recurring/gone status are both worked out from stored rows when asked. Neither is stored, so changing either rule never needs a data fix.

## Technical Decisions

### Technology Choices

**Callers pass parsed values; the store reads nothing from Squadron.** *(PM directed 20260926.)* The store's input is `VerdictInput`. Squadron's JSON and review files are read by an adapter package in slice 108, which slice 105 and the Runner also use. Keeping it out of this slice keeps the slice small. The cost is that this slice tests the matching rule by feeding it real finding text straight from the fixtures, not through the production parser. Slice 108 then re-runs those tests through the parser.

**How findings are matched.** *(PM ratified 20260926.)* The key is the location with line numbers removed, plus the summary, both normalized. Severity and category are left out.

- *Why not severity:* it is the reviewer's grade of an issue, not the issue. In the captured 102 task-review rounds, one finding was downgraded from `concern` to `note` between rounds.
- *Why not category:* it is free text that the model picks fresh every run.
- *Why no line numbers:* they shift every round.

What the rule does **not** do, and the contract says so: match a reworded finding. In the same captured rounds, every carried-over finding was reworded. For example, *"The GRACE_EXPIRED exit criterion has no CLI-level test…"* became *"GRACE_EXPIRED → next-start recovery not tested as a distinct scenario"*. Those are two keys. Deciding they are the same issue is judgment, which belongs to initiative 140. A test built on that real text pins the limit.

What the rule does catch: whitespace, backticks, letter case, trailing punctuation, moved line numbers, and the same finding at a different position in the list. Squadron has no shared matching rule to reuse (confirmed by the Squadron session), and it will adopt this one if it ever wants one. Two different findings with the same summary in the same file get the same key. Both are still stored, and the collision shows as a repeated key within one review.

**"What changed" is worked out when asked, not stored.** *(PM pending.)* Nothing labels a finding new, recurring, or gone when a review is recorded. When `finding_changes` is called, the store compares that review's findings with the previous round's, right then. A stored label would go stale: a failed round arriving late, or a change to the matching rule, would leave it wrong. The comparison covers one node's reviews of one type, which is a handful of rows.

**Every verdict gets a trust label.** *(PM ratified 20260926, then adjusted the same day on the Squadron session's corrections.)* The label is worked out by one function from stored fields and checked top to bottom. It describes what kind of verdict this is; it does not decide whether to act on it.

| Label | When |
| --- | --- |
| `provider_failure` | the review was a provider failure |
| `unparsed` | the verdict is `UNKNOWN` |
| `findings_unparsed` | the findings did not parse (`findings_parsed` is false) |
| `imposed` | Squadron capped the verdict itself (`derivation` is `imposed`) |
| `derived` | Squadron computed the verdict from the findings (`derivation` is `derived`) |
| `unattested` | the input did not say how the verdict was reached (older review files) |
| `stated` | everything else: the reviewer said it |

The rule reads `derivation` and `findings_parsed`, never `fallback_used` directly. The caller maps Squadron's flags onto those two fields: `fallback_used` with `stated` means the findings did not parse. The raw `fallback_used` is kept as provenance. "A PASS the reviewer didn't really give" is `verdict == PASS` and label `derived`.

### Patterns and Conventions

**Every record carries its own id, so a retry never writes twice.** *(PM pending.)* This is 103's inbox rule applied to direct calls. The caller supplies the id. Recording an id that already exists returns the existing record and changes nothing, with a WARNING if the content differs; the first one wins. The Runner can create the id when it journals the Squadron command, so recording again after a crash is harmless. Through the inbox, the record id is the submission id.

**The Squadron version is a required label, never compared.** *(PM pending.)* Every verdict carries `upstream` (for example `squadron`), `upstream_version` (required, not empty), `source` (`stdout_json` or `artifact_frontmatter`), and `source_path`. Until Squadron stamps its version on its output, the caller supplies it, for example from `sq --version`. No code compares versions or branches on them. This matches how the recovery code already treats the `cf --version` label.

**`amoeba submit` reads flags by one rule.** *(PM pending.)* Today it accepts only text and JSON-object fields, and refuses to build when it meets anything else. The review submission has true/false values, numbers, and a list of findings. The new rule:

- A text or enum field (or an optional one) takes the flag as typed.
- Everything else takes JSON: `--score 82.5`, `--fallback-used null`, `--findings '[…]'`.

Pydantic checks the result either way.

**Word lists** are `StrEnum`s, each defined once in `evidence_models.py`:

- `ReviewVerdict`: `PASS`, `CONCERNS`, `FAIL`, `UNKNOWN`
- `FindingSeverity`: `pass`, `note`, `concern`, `fail`
- `VerdictDerivation`: `stated`, `derived`, `imposed`, `not_reported`
- `RecordSource`: `stdout_json`, `artifact_frontmatter`
- `FindingChange`: `new`, `recurring`, `gone`
- `VerdictStanding`: the trust label

Verdict and severity are accepted in any letter case, because Squadron writes severity lowercase in one place and uppercase in another. An unrecognized word fails validation and is never mapped to a near match. Squadron's `unverified` location text is defined once, in `finding_identity.py`.

**"Not reported" must be said explicitly.** `derivation`, `fallback_used`, and `findings_parsed` are required in the payload. A submitter passes `not_reported` or `null` rather than leaving them out.

**Errors.** Direct store calls raise on a failed check, as `block()` does. The inbox apply function returns a rejection reason for the same checks, tested as plain branches, never by catching the exception.

## Implementation Details

### API Contracts

**Store additions (exported from `amoeba.store`):**

| Method | Effect |
| --- | --- |
| `record_verdict(VerdictInput) -> VerdictRecord` | One transaction: id check, the checks above, the verdict row, one row per finding. |
| `verdict(verdict_id)` / `verdicts(project_id, *, node_id=None)` | In arrival order. |
| `observations(verdict_id)` | That review's findings, in the order given. |
| `findings(project_id, *, node_id=None)` | One row per key: node, latest severity and summary, the reviews it was first and last seen in, times seen. |
| `finding_changes(verdict_id) -> FindingChanges` | Whether the review is comparable, the previous review's id, each finding tagged `new` or `recurring`, and the `gone` keys. |

**`VerdictInput`** is a frozen dataclass with these fields:

- `id`, `node_id`, `verdict`, `derivation`
- `fallback_used: bool | None`, `findings_parsed: bool | None`, `provider_failure: bool`, `diff_truncated: bool | None`
- `review_type` (Squadron's `reviewType`, the same as its JSON `template_name`), `model`, `requested_model | None`, `reviewed_sha | None`
- `score: float | None`, `criteria: Mapping | None`, `tool_calls_made: int | None`
- `sq_run_id | None`, `journal_entry_id | None`
- `findings: Sequence[FindingInput]`, `provenance: Provenance`

`score` and `criteria` are stored now because review files carry them. Slice 109 adds what uses them.

**`FindingInput`** has these fields:

- `position_id | None`: Squadron's `F001`, kept as data only
- `severity`
- `category | None`
- `summary`
- `location | None`

`VerdictRecord` mirrors the input, plus `project_id`, `recorded_seq`, `recorded_at`, and a `standing` property.

**The matching rule (`amoeba.store.finding_identity`, version 1):**

| Step | Summary | Location |
| --- | --- | --- |
| 1 | Unicode NFKC | Missing, empty, or `unverified` (any case) → empty |
| 2 | Remove backticks | Unicode NFKC; `\` → `/`; drop a leading `./` |
| 3 | Lowercase (casefold) | Remove line references anywhere: `:12`, `:12-30`, `:12:4`, `#L12`, `#L12-L30`, and `, line 12` |
| 4 | Collapse runs of whitespace; trim | Collapse whitespace; trim. **Keep case**, because paths are case-sensitive |
| 5 | Drop a trailing `.`, `;`, or `:` | — |

`finding_identity(location, summary)` is the hex SHA-256 of `"v1"`, the location, and the summary, joined by a separator character. Each observation stores the rule version, and comparisons only happen within one version. The raw text is kept, so a future version 2 can be computed for old rows by a migration.

**The inbox `verdict` type:** the payload is `VerdictInput`'s fields except `id`, flattened. `provenance` becomes `upstream`, `upstream_version`, `source`, and `source_path`. The record id is the submission id.

**CLI:**

| Command | What it does |
| --- | --- |
| `amoeba submit verdict --project ID --by NAME --node-id ID --verdict V --derivation D --fallback-used JSON --findings-parsed JSON --provider-failure JSON --review-type T --model M --findings JSON --upstream U --upstream-version V --source S [optional fields] [--id ID]` | Flags come from the payload model, under the new flag rule. |
| `amoeba inspect verdicts --project ID [--node ID]` | Columns: `recorded_seq, id, node_id, review_type, model, verdict, standing, upstream_version` |
| `amoeba inspect findings --project ID [--node ID] [--verdict ID]` | One row per key. With `--verdict`, that review's findings tagged new/recurring, then the gone ones, with the previous review's id in a header line. |

Both listings accept `--json`. The registry today only has on/off flags and fixed choices, so `Listing` gains `value_options`, and `_add_inspect_parser` adds them. That is the one change to 102's CLI plumbing. It is additive.

### Database / Storage Schema

Migration `005_verdicts_and_findings.sql` sets `EXPECTED_SCHEMA_VERSION` to 5. There is nothing to backfill.

**`verdicts`:**

- `recorded_seq` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `id` (UNIQUE)
- `project_id`, `node_id` (FK), `journal_entry_id` (nullable FK)
- `verdict`, `derivation`
- `fallback_used`, `findings_parsed`, `diff_truncated` (INTEGER, nullable)
- `provider_failure` (INTEGER)
- `review_type`, `model`, `requested_model`, `reviewed_sha`
- `score` (REAL), `criteria` (JSON text), `tool_calls_made`
- `sq_run_id`
- `upstream`, `upstream_version`, `source`, `source_path`
- `recorded_at`

Index on `(project_id, node_id, review_type, recorded_seq)`, for finding the previous round.

**`finding_observations`:**

- `verdict_id` (FK), `ordinal`
- `position_id`, `severity`, `category`, `summary`, `location`
- `normalized_location`, `normalized_summary`
- `identity`, `identity_version`

Primary key on `(verdict_id, ordinal)`. Index on `identity`.

## Integration Points

### Provides to Other Slices

- **108:** `VerdictInput` as the parser's output, and the matching rule's tests, which 108 re-runs through the parser.
- **109:** the `verdicts` table and its `score` and `criteria` columns. 109 adds a judge-invocation column, the calibration report, and check records.
- **105:** `record_verdict` as the target for reviews it finds on disk. The retry rule makes finding the same file twice harmless. The trust label says "a failure file is a failure, not a review".
- **106:** recording a review for a journaled Squadron run, as part of the end-to-end proof.
- **Initiative 120:** `record_verdict`, `finding_changes`, the trust label, and `finding_identity`.
- **Initiative 140:** the `verdict` inbox type.

### Consumes from Other Slices

These consume 101–103 through their documented contracts. The changes are recorded in the contract docs and the `CHANGELOG`:

- `store-contract.md` drops its "not a findings store" line.
- The inbox gains the `verdict` type.
- `amoeba submit` reads flags by the new rule.
- `Listing` gains `value_options`.
- The test that pins 102's listing set, `test_slice_104_listings_are_not_registered_here`, is replaced by one pinning the new set.

## Success Criteria

### Functional Requirements

- The same finding text in two reviews, at different list positions, gets one key, and `finding_changes` reports it `recurring`.
- A changed line reference (`:119-163` → `:218-240`, `#L12` → none) or a formatting-only summary change (whitespace, backticks, case, trailing period) keeps the key. A different file path or different words change it.
- On the captured 102 task-review rounds in `tests/fixtures/sq_reviews/`, consecutive rounds share **no** keys. The test says so and names this as the rewording limit.
- `finding_changes` on round 2 names round 1 as the previous review and tags new, recurring, and gone correctly.
  - On a provider-failure review, it says "not comparable".
  - A provider failure recorded between two real rounds is skipped when finding the previous round.
- Each trust label is produced by a record built for it:
  - `derivation=derived` gives `derived`.
  - `findings_parsed=false` gives `findings_unparsed`.
  - `derivation=imposed` gives `imposed`.
  - A CONCERNS with zero findings and `findings_parsed=true` gives `stated`.
  - A provider failure gives `provider_failure`.
- A provider failure with findings, or with a verdict other than `UNKNOWN`, fails when recorded directly and is rejected through the inbox.
- Recording an id that already exists returns the existing record, writes nothing, and logs a WARNING if the content differs.
- A `verdict` submission applied by the running process produces a record whose id is the submission id. Applying it again changes nothing. An unrecognized `derivation` is quarantined.
- A verdict without `upstream_version` cannot be recorded.
- `amoeba inspect verdicts` and `amoeba inspect findings` work whether the process is running or stopped.

### Technical Requirements

- Each word list is a `StrEnum` defined once. All SQL and column names live in `sql_evidence.py`. The matching rule has one definition and a version constant. The trust label has one function.
- `finding_identity.py` imports nothing from the store, and is covered by a table of normalization cases.
- Real Squadron review files from `project-documents/user/reviews/` (including `archive/`) are copied into `tests/fixtures/sq_reviews/` unchanged. The README records why each file is there. Hand-written or hand-edited reviews (for example `103-review.code…`, which has `resolution:` keys Squadron never writes) are left out, or marked as such.
- A store at version 4 with nodes, journal entries, submissions, and messages upgrades to 5 with all of them intact.
- The writer guard is unchanged.
- `ruff`, `pyright` strict, and the full suite are clean. Source files stay near 300 lines.
- `docs/evidence-contract.md` covers the matching rule and what it does not match, the trust labels, how the previous round is chosen, and the provenance fields.

### Integration Requirements

- End to end through the real CLI: create a project, seed a node, submit two review rounds and a provider failure with `amoeba submit verdict`, `kill -9`, and `start`. Read-only inspection then shows three verdicts, the right changes on round 2, and nothing applied twice.
- `docs/evidence-contract.md` is enough for slice 108's design and initiative 140's design to proceed without reading the code.

### Verification Walkthrough

Draft; filled in with real output when implementation is done. Nothing outside the process can create nodes until initiative 120. So `scripts/demo_evidence.py` seeds one node in the `demo` project and prints its id. It runs with the process stopped, and it is added to the writer guard's allowed scripts, like `demo_inbox.py`. The review payloads sit beside it as JSON files. They use real finding text from the captured 102 rounds, reordered for the recurrence case.

```bash
export AMOEBA_STORE_DIR="$(mktemp -d)"
amoeba start &
amoeba submit create-project --project demo --by pm
amoeba stop
NODE=$(uv run python scripts/demo_evidence.py)
amoeba start &
BASE="--project demo --by pm --node-id $NODE --review-type tasks --model demo-model \
  --upstream squadron --upstream-version 0.14.0 --source artifact_frontmatter \
  --provider-failure false --fallback-used null"
```

**1. Round 1.**

```bash
amoeba submit verdict $BASE --id r1 --verdict CONCERNS --derivation stated \
  --findings-parsed true --findings "$(cat scripts/demo_evidence/round1.json)"
```

`amoeba inspect verdicts --project demo` shows `r1` labelled `stated`.

**2. Round 2.** One finding comes back at a new position with a moved line range, one is dropped, and one is new. Submit `round2.json` as `r2`, the same way.

`amoeba inspect findings --project demo --verdict r2` shows the previous review `r1`, one `recurring`, one `new`, and one `gone`.

**3. A provider failure between rounds is skipped.** Submit `r3` with `--verdict UNKNOWN --derivation not_reported --provider-failure true --findings-parsed null --findings '[]'`. Then submit round 2's payload again, as `r4`.

- `inspect verdicts` labels `r3` `provider_failure`.
- `inspect findings --verdict r3` says it is not comparable.
- `inspect findings --verdict r4` shows previous review `r2` and every finding `recurring`. `r3` was skipped.

**4. Verdicts that aren't what they look like.** Each submission carries one finding.

| Submission | Flags | Label |
| --- | --- | --- |
| `r5` | `--verdict PASS --derivation derived --findings-parsed true` | `derived` |
| `r6` | `--verdict CONCERNS --derivation stated --findings-parsed false` | `findings_unparsed` |
| `r7` | `--verdict CONCERNS --derivation imposed --findings-parsed true` | `imposed` |

**5. Retry and restart.** Resubmit round 1 with `--id r1`. Then `kill -9` the process and `amoeba start`.

`inspect verdicts` lists the same rows as before, and `inspect submissions --project demo` shows nothing applied twice.

**6. Provenance.** `amoeba inspect verdicts --project demo --json` shows `upstream`, `upstream_version`, `source`, and `recorded_at` on every record.

**7. The matching rule against real Squadron text.**

```bash
uv run pytest tests/store/test_finding_identity.py -v
```

The normalization cases pass. The captured-rounds test confirms that no key is shared across the reworded 102 rounds.

## Risk Assessment

### Technical Risks

The matching rule can be wrong without anything failing:

- If it is too loose, it merges two findings. The Runner then thinks one tracked issue is open when two are.
- If it is too strict, it splits one finding. The Runner then thinks it was fixed.

### Mitigation Strategies

- The rule only removes formatting. There is no fuzzy matching.
- Each observation records the rule version and keeps the raw text, so a correction is a new version plus a migration, and history is kept.
- The captured-rounds test pins the rewording limit, so loosening the rule has to be a visible decision.

## Implementation Notes

### Development Approach

1. `finding_identity.py` and its case table. Copy the fixtures and write the captured-rounds test. This is the riskiest piece, and it depends on nothing else.
2. The word lists, the input and record dataclasses, and the trust-label function, with a table-driven test.
3. Migration 005, `sql_evidence.py`, the mapping, and `record_verdict` with its checks and retry behavior. Then the read methods, and the 4 → 5 upgrade test.
4. `finding_changes`, including skipping failures when finding the previous round.
5. The `verdict` inbox type and the new `amoeba submit` flag rule. Extend 103's completeness tests.
6. `value_options` in the registry, and the two listings. Update the pinned-registry test.
7. `scripts/demo_evidence.py` and the payload files, the end-to-end CLI test, the docs, and the `CHANGELOG`.

Test each step right after building it. Commit after each step.

### Special Considerations

Several review files in this repository were edited by hand. Some carry `resolution:` and `resolvedBy:` keys, and one was written by hand after a tooling gap. The fixture README has to say which files are pure Squadron output, because the matching tests are only as honest as their input.
