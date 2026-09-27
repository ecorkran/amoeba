---
docType: reference
project: amoeba
slice: findings-verdicts-and-provenance
dateCreated: 20260927
dateUpdated: 20260927
status: complete
---

# The Amoeba Evidence Contract

This document is the contract for review evidence in the store: verdict
records, the findings each review reported, how findings are matched across
rounds, and the trust label on every verdict. It is written so that slice 108
(the Squadron-output parser) and initiative 140 (judgment over findings) can be
designed **without reading the implementation**. If you have to open
`verdicts.py` to answer a design question, that is a gap here — say so.

## What the evidence store is

- **A record of what each review said.** One verdict per review, with where it
  came from, and one observation per finding, in the order the reviewer gave.
- **A content key per finding** that survives formatting changes between
  rounds, so "is this the same finding as last round?" is a store query.
- **"What changed since last round?"** for any review, worked out on request.
- **A trust label** on every verdict, separating a real PASS from one Squadron
  computed, from a review whose findings did not parse, from a provider failure.

## What it is not

- **Not a parser.** The store never reads Squadron's JSON or review files.
  Callers pass already-parsed values (`VerdictInput`). Parsing is slice 108.
- **Not a judge of sameness.** The matching rule removes formatting only. It
  does not decide that a reworded finding is the same issue; that is judgment,
  and belongs to initiative 140. See [What the rule does not match](#what-the-rule-does-not-match).
- **Not a tracker of finding state.** Nothing marks a finding addressed,
  disputed, accepted, or rejected. That is initiatives 120 and 140.
- **Not a discoverer.** Noticing reviews on disk that someone else launched is
  slice 105.

## Recording a review

```python
from amoeba.store import (
    FindingInput,
    FindingSeverity,
    Provenance,
    RecordSource,
    ReviewVerdict,
    Store,
    VerdictDerivation,
    VerdictInput,
)

record = store.record_verdict(
    VerdictInput(
        id="…",  # the caller's id; the retry key
        node_id=node.id,
        verdict=ReviewVerdict.CONCERNS,
        derivation=VerdictDerivation.STATED,
        fallback_used=None,
        findings_parsed=True,
        provider_failure=False,
        review_type="tasks",
        model="z-ai/glm-5.3",
        findings=(
            FindingInput(
                severity=FindingSeverity.CONCERN, summary="…", location="path.md:12-30"
            ),
        ),
        provenance=Provenance(
            upstream="squadron",
            upstream_version="0.14.0",
            source=RecordSource.ARTIFACT_FRONTMATTER,
        ),
    ),
    project_id="demo",
)
```

`record_verdict` is **one transaction**, in this order:

1. **The id is already recorded** → return the existing record and write
   nothing. If the content differs, log a WARNING; the first record wins.
2. **The node exists in `project_id`** → else `NodeNotFoundError`.
3. **The journal entry, if given, is on the same node** → else `ValueError`.
4. **A provider failure has verdict `UNKNOWN` and no findings** → else `ValueError`.
5. **`upstream_version` is not empty** → else `ValueError`.
6. Insert the verdict row. `recorded_seq` is assigned here: arrival order.
7. Insert one observation per finding, in the order given, with the raw text,
   the normalized text, the content key, and the rule version.

A failed check writes nothing.

### The retry rule

Every record carries its own id, so a retry never writes twice. The Runner can
create the id when it journals the Squadron command, so recording again after a
crash is harmless. Through the inbox, the record id is the submission id.

### `VerdictInput`

A frozen, keyword-only dataclass.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `str` | The retry key. |
| `node_id` | `str` | Must be in the project. |
| `verdict` | `ReviewVerdict` | `PASS`, `CONCERNS`, `FAIL`, `UNKNOWN`. |
| `derivation` | `VerdictDerivation` | **Required.** `stated`, `derived`, `imposed`, `not_reported`. |
| `fallback_used` | `bool \| None` | **Required.** Squadron's raw flag, kept as provenance only. |
| `findings_parsed` | `bool \| None` | **Required.** `False` means the findings did not parse. |
| `provider_failure` | `bool` | The review was a provider failure. |
| `review_type` | `str` | Squadron's `reviewType` (its JSON `template_name`). |
| `model` | `str` | The model that answered. |
| `findings` | `tuple[FindingInput, ...]` | In the reviewer's order. |
| `provenance` | `Provenance` | See [Provenance](#provenance). |
| `diff_truncated` | `bool \| None` | Squadron's `diffTruncated` (SQ 927); null when absent. |
| `requested_model` | `str \| None` | Squadron's `requestedModel` (SQ 927); set only on a substitution. |
| `reviewed_sha` | `str \| None` | The commit reviewed. |
| `score` | `float \| None` | Stored now; slice 109 uses it. |
| `criteria` | `Mapping \| None` | Stored as JSON; slice 109 uses it. |
| `tool_calls_made` | `int \| None` | |
| `sq_run_id` | `str \| None` | Squadron's `runId` (#139), pipeline runs only. |
| `journal_entry_id` | `str \| None` | The journaled Squadron run command, if any. |

"Not reported" is said explicitly: `derivation`, `fallback_used`, and
`findings_parsed` have no default. A caller passes `not_reported` or `None`.

`FindingInput` has `severity` (`FindingSeverity`: `pass`, `note`, `concern`,
`fail`), `summary`, and optional `position_id` (Squadron's `F001`, kept as data
only — it is a list position and changes every run), `category`, `location`.

`VerdictRecord` is `VerdictInput` plus `project_id`, `recorded_seq`,
`recorded_at`, and the computed `standing` property.

`parse_verdict` and `parse_severity` accept any letter case (Squadron writes
severity lowercase in one place and uppercase in another) and raise
`ValueError` on an unknown word. Nothing is ever mapped to a near match.

### Provenance

Every verdict carries `upstream` (e.g. `squadron`), `upstream_version`
(required, not empty), `source` (`stdout_json` or `artifact_frontmatter`), and
`source_path` (optional). Until Squadron stamps its version on its output, the
caller supplies it, for example from `sq --version`. **No code compares versions
or branches on them.** When Squadron changes its output, the version finds the
affected records; it never changes how they are read.

### Mapping Squadron's flags (for slice 108)

Checked 20260926 against squadron 0.14.0.

- `verdictSource` becomes `derivation`. A file with no `verdictSource` (older
  review files) is `not_reported`, which labels the verdict `unattested`.
- `fallback_used` is set in exactly two cases: a derived verdict whose findings
  parsed, and a CONCERNS or FAIL whose findings did **not** parse. So
  `fallback_used` with `stated` maps to `findings_parsed=False`. The raw flag is
  kept in `fallback_used`; the label never reads it.
- A provider failure is a normal review slot with `verdict: UNKNOWN` and a
  *Provider Failure* heading. Record it with `provider_failure=True` and no
  findings.
- A missing location is Squadron's literal `unverified`; pass it as is. The
  matching rule treats it as empty.

**Observed 20260927 on squadron `main`, after SQ 927 and #139 merged.** Not in
a PyPI release yet (the latest is 0.14.0). This is a dated observation, not a
version pin:

- `verdictSource: imposed` appears when Squadron caps a PASS to CONCERNS: the
  diff was truncated and the model made no successful tool calls. The capped
  review carries a synthetic finding with category `review-coverage` and no
  location.
- `diffTruncated` (JSON `diff_truncated`) is written only on reviews that had
  a diff. Absent means `diff_truncated=None`.
- `requestedModel` (JSON `requested_model`) appears only on a substitution;
  `aiModel` is then the model that actually answered, possibly a dated
  snapshot id. Map `aiModel` to `model` and `requestedModel` to
  `requested_model`.
- `squadronVersion` (JSON `squadron_version`) can supply `upstream_version`,
  and `runId` (JSON `run_id`, pipeline runs only) can supply `sq_run_id`.
- `providerFailure: true` marks a provider failure in frontmatter, alongside
  the *Provider Failure* heading.
- JSON also adds `diff_chars`, `diff_chars_injected`, `answering_models`,
  `model_substituted`, `finding_scan`, and `location_verified` per finding.
  The store has no field for them; slice 108 decides whether any is needed.
- Severity values and the `unverified` literal are unchanged. Under
  `--output json`, the "Saved review to" line now goes to stderr.

## The matching rule

`amoeba.store.finding_identity`, **version 1**. Pure functions over text,
importable without opening a store: `normalize_summary`, `normalize_location`,
`finding_identity`, `RULE_VERSION`.

| Step | Summary | Location |
| --- | --- | --- |
| 1 | Unicode NFKC | Missing, empty, or `unverified` (any case) → empty |
| 2 | Remove backticks | NFKC; `\` → `/`; drop a leading `./` |
| 3 | Casefold | Remove line references anywhere: `:12`, `:12-30`, `:12:4`, comma lists such as `:34-37,55-58`, `#L12`, `#L12-L30`, `, line 12`, `, lines 12-30` |
| 4 | Collapse whitespace runs; trim | Collapse whitespace; trim. **Case is kept** — paths are case-sensitive |
| 5 | Drop trailing `.`, `;`, `:` | — |

Heading anchors such as `slice.md#data-flow` are not line references and are
kept.

`finding_identity(location, summary)` is the hex SHA-256 of `"v1"`, the
normalized location, and the normalized summary, each written as
`{length}:{text}` and concatenated, so no character in a field can move text
across the field boundary. Severity and
category are **not** part of the key: severity is the reviewer's grade of an
issue, not the issue (one captured finding went from `concern` to `note`
between rounds), and category is free text picked fresh each run.

Every observation stores `identity_version`. Keys are compared only within one
version. The raw text is kept, so a version 2 can be computed for old rows by a
migration.

### What the rule catches

Whitespace, backticks, letter case, trailing punctuation, moved line numbers,
and the same finding at a different position in the list.

### What the rule does not match

**A reworded finding.** Between the two captured slice-102 task-review rounds
(`tests/fixtures/sq_reviews/`), Squadron reworded every carried-over finding.
Round 1's *"Every success criterion in the slice design traces to at least one
task"* came back as *"Every LLD success criterion traces to at least one task,
and no task is scope creep"*. The two rounds share **no** keys, and a test pins
that. Loosening the rule to match them is a deliberate decision for initiative
140, not a bug fix.

Two different findings with the same summary in the same file get the same
key. Both are stored; the collision shows as a repeated key within one review.

## The trust label

`VerdictStanding`, computed by `verdict_standing(...)` from stored fields,
checked **top to bottom**. It describes what kind of verdict this is; it does
not decide whether to act on it. It is never stored, so changing the rule
needs no data fix.

| Order | Label | When |
| --- | --- | --- |
| 1 | `provider_failure` | `provider_failure` is true |
| 2 | `unparsed` | `verdict` is `UNKNOWN` |
| 3 | `findings_unparsed` | `findings_parsed` is false |
| 4 | `imposed` | `derivation` is `imposed` (Squadron capped the verdict) |
| 5 | `derived` | `derivation` is `derived` (Squadron computed it from findings) |
| 6 | `unattested` | `derivation` is `not_reported` |
| 7 | `stated` | everything else: the reviewer said it |

"A PASS the reviewer didn't really give" is `verdict == PASS` with label
`derived`.

A real Squadron CONCERNS or FAIL with zero parsed findings always sets
`fallback_used`, so it lands as `findings_unparsed`. The table also labels a
CONCERNS with zero findings and `findings_parsed=True` as `stated`; that row is
covered for completeness, but Squadron cannot produce it today.

## What changed since the last round

`store.finding_changes(verdict_id) -> FindingChanges`, worked out when asked.

- **Comparable** standings: `stated`, `derived`, `imposed`, `unattested`
  (`COMPARABLE_STANDINGS`). A target that is not comparable returns
  `comparable=False`, no previous round, and empty lists.
- **The previous round** is the latest earlier verdict (by `recorded_seq`) on
  the same node, with the same `review_type`, whose standing is comparable. A
  provider failure, an unparsed verdict, or a review whose findings did not
  parse is **never** a baseline — otherwise a failed round would report every
  open finding as fixed.
- Each target finding is `recurring` if its key (within the same rule version)
  is in the previous round, else `new`. No previous round means every finding
  is `new`.
- `gone` holds the previous round's observations whose keys the target lacks,
  one per key.

`FindingChanges` carries `verdict_id`, `comparable`, `previous_verdict_id`,
`findings` (each a `TaggedFinding`: `observation` and `change`), and `gone`.

## Reading

| Method | Returns |
| --- | --- |
| `verdict(verdict_id)` | `VerdictRecord \| None` |
| `verdicts(project_id, *, node_id=None)` | In arrival order. |
| `observations(verdict_id)` | `FindingObservation`s in the reviewer's order. Raises `VerdictNotFoundError` for an unknown id. |
| `findings(project_id, *, node_id=None)` | One `FindingSummary` per key per node: latest severity, summary, and location; first and last verdict ids; how many reviews reported it. |
| `finding_changes(verdict_id)` | Above. Raises `VerdictNotFoundError` for an unknown id. |

All of them work through `Store.open_read_only`. `observations` and
`finding_changes` raise rather than return empty for an unknown id, because an
empty result would look like a real review with no findings.

## Through the inbox

The `verdict` submission kind records a review from outside the process — the
path for the out-of-process Judge. The payload is `VerdictInput`'s fields
except `id`, with `provenance` flattened to `upstream`, `upstream_version`,
`source`, and `source_path`. The submission id becomes the record id.

- An unknown word in an enum field (e.g. `derivation: guessed`) fails payload
  validation: the file is quarantined as `invalid_payload`. So does an omitted
  `derivation`, `fallback_used`, or `findings_parsed`.
- A failed check (unknown node, a malformed provider failure, an empty
  `upstream_version`) is recorded as `rejected` with the reason.
- Resubmitting the same id is a no-op, as for every kind.

```bash
amoeba submit verdict --project demo --by judge --node-id "$NODE" \
  --verdict CONCERNS --derivation stated --fallback-used null \
  --findings-parsed true --provider-failure false \
  --review-type tasks --model glm-5.3 \
  --upstream squadron --upstream-version 0.14.0 --source artifact_frontmatter \
  --findings '[{"severity": "concern", "summary": "…", "location": "x.md:12"}]'
```

See [`inbox-contract.md`](inbox-contract.md) for the flag rule.

## Inspection

- `amoeba inspect verdicts --project ID [--node ID]` — columns `recorded_seq,
  id, node_id, review_type, model, verdict, standing, upstream_version`. With
  `--json`, rows also carry `upstream`, `source`, `source_path`, `recorded_at`.
- `amoeba inspect findings --project ID [--node ID]` — one row per key.
- `amoeba inspect findings --project ID --verdict ID` — a header line naming
  the previous review (or saying `not comparable`), then that review's findings
  tagged `new`/`recurring`, then the `gone` ones. With `--json` there is no
  header; each row carries `previous_verdict_id`. An unknown id is an error.

Both read through a read-only handle, whether the process is running or not.

## Storage

Schema version 5 (migration `005`): `verdicts` and `finding_observations`. The
column names are defined once, in `amoeba.store.sql_evidence`. An unknown
vocabulary value in a stored row raises `UnknownVocabularyValueError` on read;
it is never defaulted.

## Future work

- Slice 108 parses Squadron's JSON and review files into `VerdictInput`, and
  re-runs this rule's captured-round tests through the parser.
- Slice 109 adds judge samples, calibration over `score` and `criteria`, and
  check records.
- Slice 105 records reviews it finds on disk through `record_verdict`; the
  retry rule makes finding the same file twice harmless.
- Initiative 140 owns deciding that two differently worded findings are the
  same issue.
