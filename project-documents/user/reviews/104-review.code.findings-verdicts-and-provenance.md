---
docType: review
layer: project
reviewType: code
slice: findings-verdicts-and-provenance
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 4e4611475cf694430b6f1fc69dbc0460170af58e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 41
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Content-key separator invariant does not hold for input containing U+001F"
    location: "src/amoeba/store/finding_identity.py:24-26"
  - id: F002
    severity: concern
    category: api-design
    summary: "`findings --verdict` JSON form loses the comparable/not-comparable distinction"
    location: "src/amoeba/cli/inspect_evidence.py#finding_rows"
  - id: F003
    severity: note
    category: dry
    summary: "Verdict payload grammar defined twice; key names pinned, field types not"
    location: "src/amoeba/store/verdict_payload.py"
  - id: F004
    severity: note
    category: testing
    summary: "Load tier never drives the new verdict effect under concurrency"
    location: "tests/load/test_inbox_concurrent.py"
  - id: F005
    severity: note
    category: error-handling
    summary: "Unknown `--verdict` id exits as `STARTUP_FAILED`"
    location: "src/amoeba/cli/main.py#main"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Registry-driven listings and unusually thorough single-definition pins"
    location: "src/amoeba/cli/inspect.py#LISTINGS"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Rejection-as-branch and computed trust label, both mechanically enforced"
    location: "src/amoeba/store/_verdict_writer.py#VerdictWriter"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Migration test proves preservation; captured real data pins the rewording limit"
    location: "tests/store/test_migration_005.py#test_upgrade_keeps_every_prior_row"
---

# Review: code — slice 104

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] Content-key separator invariant does not hold for input containing U+001F

The comment claims `_KEY_SEPARATOR = "\x1f"` makes the join unambiguous because it "cannot survive normalization inside either field". Neither normalization step actually removes it: `\s` does not match U+001F (it is a Cc control character, not White_Space), NFKC leaves Cc unchanged, `casefold` leaves it unchanged, and `rstrip(_TRAILING_SUMMARY_PUNCTUATION)` does not strip it. So a raw `\x1f` in either field survives all of `normalize_summary` and `normalize_location`, and two genuinely different findings collide:

- `finding_identity("a\x1fb", "c")` → material `v1\x1fa\x1fb\x1fc`
- `finding_identity("a", "b\x1fc")` → material `v1\x1fa\x1fb\x1fc`

Both hash to the same stored identity, mislabeling one finding as `recurring`/`gone` relative to the other — and the key is persistent state, so the collision survives every later round. The likelihood is low (a review would have to embed the unit separator), but the comment is load-bearing: it justifies not length-prefixing, and it is false as written. Either drop Cc characters in both normalize functions, or length-prefix each field before hashing, and add a test pinning the shift case. The existing tests (`tests/store/test_finding_identity.py:52-64`) cover field-shift only for whitespace-separated text, which is why this slipped through.

### [CONCERN] `findings --verdict` JSON form loses the comparable/not-comparable distinction

For a not-comparable verdict (provider failure, `unparsed`, `findings_unparsed`), `finding_changes` returns empty `findings` and `gone`, so the JSON form of `findings --verdict ID` is a bare `[]` — indistinguishable from a comparable round with zero findings. The `comparable` flag reaches the user only via the table-mode header printed from `_change_rows` (`src/amoeba/cli/inspect_evidence.py`, `if not use_json: print(_header(changes))`). A JSON consumer would read a provider-failure round as "no changes" — exactly the misreading `COMPARABLE_STANDINGS` exists to prevent. The store API carries the flag (`FindingChanges.comparable`), so this is a boundary-only gap; adding `comparable` (and `previous_verdict_id` unconditionally) to each JSON row is a one-line fix. Two smaller warts in the same mode: `--node` is silently ignored when `--verdict` is given (`finding_rows` never reads `args.node` in that branch, despite the flag's "Only this node." help), and in table mode the pinned `FINDING_COLUMNS` include `node_id`, `times_seen`, `first_verdict_id`, and `last_verdict_id`, which are always blank for `--verdict` rows. The print-inside-a-rows-function side effect is also worth revisiting when a second caller for these row functions appears.

### [NOTE] Verdict payload grammar defined twice; key names pinned, field types not

The grammar exists as pydantic fields in `src/amoeba/inbox/evidence_payloads.py` and as manual narrowing in `src/amoeba/store/verdict_payload.py` (the store deliberately never imports pydantic — a defensible split). Key *names* are pinned in both directions by `tests/inbox/test_envelope.py` (`test_payload_fields_are_the_keys_the_store_reads`, `test_finding_payload_fields_are_the_keys_the_store_reads`), but field *types* are not. I traced the current fields and they line up: pydantic normalizes to the shapes `_text`/`_optional_bool`/`_optional_int`/`_optional_float` expect, and case-folding happens before the store sees values. A future type-level divergence would pass the envelope and then raise `ValueError` inside `apply_submission`, which the tenant classifies as "store unwell" and parks in `failed/` (`src/amoeba/process/inbox_tenant.py:135-150`) instead of quarantining as a bad submission. A property-style round-trip test — every payload `VerdictPayload.model_validate` accepts must also survive `verdict_from_payload` — would close the residual gap; `tests/store/test_verdict_submission.py` covers only a fixed payload set.

### [NOTE] Load tier never drives the new verdict effect under concurrency

The concurrent-drain load test drives only `CREATE_PROJECT` and `INTENT` (lines 97 and 120). The verdict effect adds a multi-row transaction (one verdict row plus N observation rows) to the same drained path; its exactly-once behavior is covered functionally (`tests/store/test_verdict_submission.py`) but never under the concurrent contention this tier exists to exercise. Per the load-test rule, a slice touching the inbox-apply/concurrency path should extend the concurrent test to include at least one verdict submission and assert observation counts.

### [NOTE] Unknown `--verdict` id exits as `STARTUP_FAILED`

`inspect findings --verdict nope` raises `VerdictNotFoundError`, which `main()` maps through the generic `StoreError` handler to `ExitCode.STARTUP_FAILED` — a code documented as "`start`: a store could not be opened, or recovery could not complete." The mapping is pre-existing; this slice is the first feature to turn a *user argument error* into it (`tests/cli/test_inspect_evidence.py#test_an_unknown_verdict_is_an_error` asserts only `code != OK`, so behavior is as designed). The error message itself is good — it names the offending id and stdout stays empty. Worth a dedicated exit code when the vocabulary is next touched.

### [PASS] Registry-driven listings and unusually thorough single-definition pins

Adding `verdicts` and `findings` was purely appending to `LISTINGS` plus two row functions and one `ValueOption`; the parser (`main.py:_add_inspect_parser`) and dispatch derive from the registry with no per-listing edits, and the pinning tests (`test_the_registered_listings_are_pinned`, `test_only_project_listings_require_a_project`) were updated to match. The same discipline holds across the store: PRAGMA-verified column order against `sql_evidence` constants with an order-sensitive tuple compare (`tests/store/test_migration_005.py#test_columns_match_the_single_definition_site`), payload keys ↔ pydantic fields (`tests/inbox/test_envelope.py`), kinds ↔ effects (`test_every_kind_has_an_effect`), and `EXPECTED_SCHEMA_VERSION == 5` pinned by test.

### [PASS] Rejection-as-branch and computed trust label, both mechanically enforced

The verdict writer follows the `BlockWriter` pattern exactly: checks return a `VerdictRejection`, the direct API raises on it, the inbox records it as a rejected submission — no exception-based control flow. That rule is now mechanically enforced for the new writer too: `tests/store/test_inbox_apply.py` parametrizes its AST scan over both `inbox` and `_verdict_writer` modules. The trust label is computed from stored fields and never stored (`evidence_models.verdict_standing`), its precedence table is tested over the full cross product of inputs (`test_every_standing_is_produced_by_the_table` proves every standing is reachable), and `COMPARABLE_STANDINGS` deliberately excludes failed/unparsed rounds so a failed baseline can never mark open findings gone.

### [PASS] Migration test proves preservation; captured real data pins the rewording limit

The migration test stages a genuine version-4 store through the store's own statements (nodes, journal entry, submission, message), then proves every prior row survives the upgrade bit-for-bit via before/after table dumps, alongside autoincrement-DDL and column-order assertions. Elsewhere in the tests: the walkthrough payloads are validated against captured Squadron text only (`tests/test_demo_evidence_payloads.py`), the rewording limit is pinned on the real 102 rounds with a comment blocking casual loosening (`test_captured_rounds_share_no_keys`), the writer-guard allowlist widening for `demo_evidence.py` is deliberate and drift-checked (the guard verifies the script both exists and actually opens a store), and the new `cli_harness` helpers (`start_running`, `await_condition`, `submit_cli`) removed real duplication across the e2e files rather than adding a third copy.

### Run Digest

- Response length: 8814 chars
- Response is newline-free: no
- Tool calls made: 41
- Tool calls failed: 2
- Stop reason: stop
- Reasoning characters: 133780
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

### Raw Response

## Summary
[CONCERNS] A disciplined, well-pinned slice — single definition sites, registry-driven CLI, rejection-as-branch, and real captured fixtures — with two concerns worth addressing: a false invariant claim in the finding-identity separator, and an information loss at the `findings --verdict` JSON boundary.

## Findings

### [CONCERN] Content-key separator invariant does not hold for input containing U+001F
category: correctness
location: src/amoeba/store/finding_identity.py:24-26

The comment claims `_KEY_SEPARATOR = "\x1f"` makes the join unambiguous because it "cannot survive normalization inside either field". Neither normalization step actually removes it: `\s` does not match U+001F (it is a Cc control character, not White_Space), NFKC leaves Cc unchanged, `casefold` leaves it unchanged, and `rstrip(_TRAILING_SUMMARY_PUNCTUATION)` does not strip it. So a raw `\x1f` in either field survives all of `normalize_summary` and `normalize_location`, and two genuinely different findings collide:

- `finding_identity("a\x1fb", "c")` → material `v1\x1fa\x1fb\x1fc`
- `finding_identity("a", "b\x1fc")` → material `v1\x1fa\x1fb\x1fc`

Both hash to the same stored identity, mislabeling one finding as `recurring`/`gone` relative to the other — and the key is persistent state, so the collision survives every later round. The likelihood is low (a review would have to embed the unit separator), but the comment is load-bearing: it justifies not length-prefixing, and it is false as written. Either drop Cc characters in both normalize functions, or length-prefix each field before hashing, and add a test pinning the shift case. The existing tests (`tests/store/test_finding_identity.py:52-64`) cover field-shift only for whitespace-separated text, which is why this slipped through.

### [CONCERN] `findings --verdict` JSON form loses the comparable/not-comparable distinction
category: api-design
location: src/amoeba/cli/inspect_evidence.py#finding_rows

For a not-comparable verdict (provider failure, `unparsed`, `findings_unparsed`), `finding_changes` returns empty `findings` and `gone`, so the JSON form of `findings --verdict ID` is a bare `[]` — indistinguishable from a comparable round with zero findings. The `comparable` flag reaches the user only via the table-mode header printed from `_change_rows` (`src/amoeba/cli/inspect_evidence.py`, `if not use_json: print(_header(changes))`). A JSON consumer would read a provider-failure round as "no changes" — exactly the misreading `COMPARABLE_STANDINGS` exists to prevent. The store API carries the flag (`FindingChanges.comparable`), so this is a boundary-only gap; adding `comparable` (and `previous_verdict_id` unconditionally) to each JSON row is a one-line fix. Two smaller warts in the same mode: `--node` is silently ignored when `--verdict` is given (`finding_rows` never reads `args.node` in that branch, despite the flag's "Only this node." help), and in table mode the pinned `FINDING_COLUMNS` include `node_id`, `times_seen`, `first_verdict_id`, and `last_verdict_id`, which are always blank for `--verdict` rows. The print-inside-a-rows-function side effect is also worth revisiting when a second caller for these row functions appears.

### [NOTE] Verdict payload grammar defined twice; key names pinned, field types not
category: dry
location: src/amoeba/store/verdict_payload.py

The grammar exists as pydantic fields in `src/amoeba/inbox/evidence_payloads.py` and as manual narrowing in `src/amoeba/store/verdict_payload.py` (the store deliberately never imports pydantic — a defensible split). Key *names* are pinned in both directions by `tests/inbox/test_envelope.py` (`test_payload_fields_are_the_keys_the_store_reads`, `test_finding_payload_fields_are_the_keys_the_store_reads`), but field *types* are not. I traced the current fields and they line up: pydantic normalizes to the shapes `_text`/`_optional_bool`/`_optional_int`/`_optional_float` expect, and case-folding happens before the store sees values. A future type-level divergence would pass the envelope and then raise `ValueError` inside `apply_submission`, which the tenant classifies as "store unwell" and parks in `failed/` (`src/amoeba/process/inbox_tenant.py:135-150`) instead of quarantining as a bad submission. A property-style round-trip test — every payload `VerdictPayload.model_validate` accepts must also survive `verdict_from_payload` — would close the residual gap; `tests/store/test_verdict_submission.py` covers only a fixed payload set.

### [NOTE] Load tier never drives the new verdict effect under concurrency
category: testing
location: tests/load/test_inbox_concurrent.py

The concurrent-drain load test drives only `CREATE_PROJECT` and `INTENT` (lines 97 and 120). The verdict effect adds a multi-row transaction (one verdict row plus N observation rows) to the same drained path; its exactly-once behavior is covered functionally (`tests/store/test_verdict_submission.py`) but never under the concurrent contention this tier exists to exercise. Per the load-test rule, a slice touching the inbox-apply/concurrency path should extend the concurrent test to include at least one verdict submission and assert observation counts.

### [NOTE] Unknown `--verdict` id exits as `STARTUP_FAILED`
category: error-handling
location: src/amoeba/cli/main.py#main

`inspect findings --verdict nope` raises `VerdictNotFoundError`, which `main()` maps through the generic `StoreError` handler to `ExitCode.STARTUP_FAILED` — a code documented as "`start`: a store could not be opened, or recovery could not complete." The mapping is pre-existing; this slice is the first feature to turn a *user argument error* into it (`tests/cli/test_inspect_evidence.py#test_an_unknown_verdict_is_an_error` asserts only `code != OK`, so behavior is as designed). The error message itself is good — it names the offending id and stdout stays empty. Worth a dedicated exit code when the vocabulary is next touched.

### [PASS] Registry-driven listings and unusually thorough single-definition pins
location: src/amoeba/cli/inspect.py#LISTINGS

Adding `verdicts` and `findings` was purely appending to `LISTINGS` plus two row functions and one `ValueOption`; the parser (`main.py:_add_inspect_parser`) and dispatch derive from the registry with no per-listing edits, and the pinning tests (`test_the_registered_listings_are_pinned`, `test_only_project_listings_require_a_project`) were updated to match. The same discipline holds across the store: PRAGMA-verified column order against `sql_evidence` constants with an order-sensitive tuple compare (`tests/store/test_migration_005.py#test_columns_match_the_single_definition_site`), payload keys ↔ pydantic fields (`tests/inbox/test_envelope.py`), kinds ↔ effects (`test_every_kind_has_an_effect`), and `EXPECTED_SCHEMA_VERSION == 5` pinned by test.

### [PASS] Rejection-as-branch and computed trust label, both mechanically enforced
location: src/amoeba/store/_verdict_writer.py#VerdictWriter

The verdict writer follows the `BlockWriter` pattern exactly: checks return a `VerdictRejection`, the direct API raises on it, the inbox records it as a rejected submission — no exception-based control flow. That rule is now mechanically enforced for the new writer too: `tests/store/test_inbox_apply.py` parametrizes its AST scan over both `inbox` and `_verdict_writer` modules. The trust label is computed from stored fields and never stored (`evidence_models.verdict_standing`), its precedence table is tested over the full cross product of inputs (`test_every_standing_is_produced_by_the_table` proves every standing is reachable), and `COMPARABLE_STANDINGS` deliberately excludes failed/unparsed rounds so a failed baseline can never mark open findings gone.

### [PASS] Migration test proves preservation; captured real data pins the rewording limit
location: tests/store/test_migration_005.py#test_upgrade_keeps_every_prior_row

The migration test stages a genuine version-4 store through the store's own statements (nodes, journal entry, submission, message), then proves every prior row survives the upgrade bit-for-bit via before/after table dumps, alongside autoincrement-DDL and column-order assertions. Elsewhere in the tests: the walkthrough payloads are validated against captured Squadron text only (`tests/test_demo_evidence_payloads.py`), the rewording limit is pinned on the real 102 rounds with a comment blocking casual loosening (`test_captured_rounds_share_no_keys`), the writer-guard allowlist widening for `demo_evidence.py` is deliberate and drift-checked (the guard verifies the script both exists and actually opens a store), and the new `cli_harness` helpers (`start_running`, `await_condition`, `submit_cli`) removed real duplication across the e2e files rather than adding a third copy.
