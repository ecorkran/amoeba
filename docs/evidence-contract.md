---
docType: reference
project: amoeba
slice: findings-verdicts-and-provenance
dateCreated: 20260927
dateUpdated: 20261009
status: complete
---

# The Amoeba Evidence Contract

This document is the contract for review evidence in the store: verdict
records, the findings each review reported, how findings are matched across
rounds, and the trust label on every verdict. It is written so that slice 105
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
  Callers pass already-parsed values (`VerdictInput`). Parsing is slice 105.
- **Not a judge of sameness.** The matching rule removes formatting only. It
  does not decide that a reworded finding is the same issue; that is judgment,
  and belongs to initiative 140. See [What the rule does not match](#what-the-rule-does-not-match).
- **Not a tracker of finding state.** Nothing marks a finding addressed,
  disputed, accepted, or rejected. That is initiatives 120 and 140.
- **Not a discoverer.** Noticing reviews on disk that someone else launched is
  slice 106.

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
| `score` | `float \| None` | Stored now; slice 107 uses it. |
| `criteria` | `Mapping \| None` | Stored as JSON; slice 107 uses it. |
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

### Parsing Squadron output

`amoeba.upstream.squadron` turns Squadron's review output into a `VerdictInput`.
It is pure: it reads text, not files, and opens no store. Two readers share one
mapping: `parse_review_json` (the stdout of `sq review … --output json`) and
`parse_review_artifact` (a saved review file). Both return a frozen
`ParsedReview`; `to_verdict_input` adds the node, path, and version label.
`amoeba ingest review` is the command-line caller (see
[`process-contract.md`](process-contract.md), "The CLI").

Squadron's key names are defined once, in `review_fields.py`. Nothing is
defaulted: a missing `verdict`, review type, or model, an unknown verdict or
severity word, a finding without `severity` or `summary`, malformed YAML or
JSON, and a provider failure with a verdict or findings all raise
`SquadronParseError`, naming the key and the source.

**The mapping** (design decision D3 in slice 105):

| `ParsedReview` field | From stdout JSON | From a review file |
| --- | --- | --- |
| `derivation` | `verdictSource`; `not_reported` if null or absent | the same key; `not_reported` if absent (older files) |
| `fallback_used` | `fallback_used`; `None` if absent | `None` (the file does not carry it) |
| `findings_parsed` | `False` when `fallback_used` is true and the derivation is `stated` or `not_reported`; `None` when `fallback_used` is absent; else `True` | `False` when the body has a *Findings Not Parsed* heading; else `True` |
| `provider_failure` | `False` (a failure produces no JSON) | `providerFailure` when the key is present; otherwise a *Provider Failure* heading (files from before Squadron wrote the key) |
| `requested_model` | only when `model_substituted` is true | `requestedModel` |
| `reviewed_sha`, `slice`, `source_document` | `None` | `reviewedSha`, `slice` (absent on PR reviews), `sourceDocument` |
| `sq_run_id`, stamp | `run_id`, `squadron_version` | `runId`, `squadronVersion` |
| `findings` | `structured_findings[]` | `findings:` (absent means none) |

Each finding maps `id` to `position_id`, reads `severity` case-insensitively,
and passes `category`, `summary`, and `location` through as written, including
Squadron's `unverified` literal (the matching rule treats it as empty).
Headings match at any level and in any case, outside fenced code blocks; text that only mentions a heading mid-line is not one. Keys the parser does not know are
ignored, including the `resolution:` and `resolvedBy:` keys added to review
files by hand. Keys dropped on purpose: `location_verified`, `finding_scan`,
`diff_chars`, `diff_chars_injected`, `answering_models`, `stop_reason`,
`tools_given`. `source_document` is read from files only, because JSON's
input path is whatever the caller typed.

**The version rule** (D4). Squadron's own stamp (`squadronVersion` or
`squadron_version`) is the version when present. A review with no stamp takes
the caller's label (`--upstream-version`). With neither, `to_verdict_input`
raises `UpstreamVersionError`; with both and different, it raises, naming both.
The label is never compared beyond that equality.

**The record id** (D5). `review_record_id` is `sq-review-` plus the first 32 hex
characters of the SHA-256 of a canonical JSON encoding of the `ParsedReview`,
tagged `parsed-review-v1`. It covers every `ParsedReview` field and nothing the
caller supplies (node, path, version label, journal entry). So:

- Adding `resolution:` keys or a `## Response` section does not change the id.
  Ingesting the same review from another path is a replay no-op, and the first
  ingest's `source_path` stays on the record.
- The id does not include the node. Ingesting the same review onto a second
  node is a silent replay no-op (the first record wins); pass a new `--id` to
  record it again. `ingest review` prints the id on stderr.
- Changing any covered field changes every id. That is a contract change: it
  needs a new format tag and a CHANGELOG entry.
- A review's file and its stdout capture get **different** ids, because they
  carry different fields (`reviewed_sha` exists only in the file). Ingesting
  both stores the review twice: two verdict rows, every finding key seen twice,
  and `finding_changes` reporting each finding as `recurring` against itself.
  **Ingest the file whenever one exists;** use stdout only for `--no-save` runs.

**Attribution** (D7). `ingest review --node` is the operator's explicit
choice and is not checked against the review's `slice`. The command prints the
node, the parsed slice (`-` when there is none), and the review type on stderr
before submitting, so a wrong node is visible. There is no delete: recover by
ingesting again onto the right node with a new `--id`.

**Dated observation, not a version pin.** Checked 20260928 against squadron
`373217ab` (0.15.0). Squadron moves without semver; the shapes above are what
the parser reads, and the version label only finds the affected records:

- `verdictSource: imposed` appears when Squadron caps a PASS to CONCERNS (the
  diff was truncated and the model made no successful tool calls). The capped
  review carries a synthetic finding with category `review-coverage`.
- `diffTruncated` is written only on reviews that had a diff.
- `requestedModel` appears only on a substitution; `aiModel` is then the model
  that answered.
- Under `--output json`, the "Saved review to" line goes to stderr. The JSON
  reader still decodes only the first object, so a trailing line is harmless.
- A run from the CLI has no `runId`; its JSON `run_id` is null.

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
  `--json`, rows also carry `upstream`, `source`, `source_path`, `sq_run_id`,
  `reviewed_sha` (both `null` when the review has none), `recorded_at`.
- `amoeba inspect findings --project ID [--node ID]` — one row per key.
- `amoeba inspect changes --project ID --verdict ID` — that review's findings
  tagged `new`/`recurring`, then the `gone` ones. Columns `change, severity,
  summary, location, key, previous_verdict_id` (`None` for a first round);
  `--json` rows also carry `verdict_id`. An unknown id exits `NOT_FOUND` (10).
  A review that is not comparable exits `NOT_COMPARABLE` (11) with nothing on
  stdout, so neither form can read a failed round as one with no changes.

All three read through a read-only handle, whether the process is running or not.

## Storage

Schema version 5 (migration `005`): `verdicts` and `finding_observations`. The
column names are defined once, in `amoeba.store.sql_evidence`. An unknown
vocabulary value in a stored row raises `UnknownVocabularyValueError` on read;
it is never defaulted.

## Future work

- Slice 107 adds judge samples, calibration over `score` and `criteria`, and
  check records.
- Slice 106 records reviews it finds on disk through `record_verdict`; the
  retry rule makes finding the same file twice harmless.
- Initiative 140 owns deciding that two differently worded findings are the
  same issue.
