---
docType: review
layer: project
reviewType: slice
slice: findings-verdicts-and-provenance
targetKind: slice
rulesSource: project
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: eafcaa5f17954c0f50ab77013b19c72ce323138d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 31
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Matching rule, trust label, and provenance implement the architecture's identity, provenance, and unknown-as-value principles without drift"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md:151-184"
  - id: F002
    severity: pass
    category: integration
    summary: "Dependency directions, writer model, and integration claims verify against the completed 101–103 designs"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md:71-73"
  - id: F003
    severity: concern
    category: test-data
    summary: "The crux tests' fixture source — captured 102 task-review rounds under `project-documents/user/reviews/` — does not exist in this checkout"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md:320-341"
  - id: F004
    severity: note
    category: error-handling
    summary: "`finding_changes` on a nonexistent verdict id is unspecified"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md#data-flow"
  - id: F005
    severity: note
    category: upstream-shape
    summary: "`diff_truncated` is in the schema and `VerdictInput` but absent from the design's own \"What Squadron emits today\" list"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md:219-228"
  - id: F006
    severity: note
    category: upstream-shape
    summary: "The \"CONCERNS with zero findings, findings_parsed=true\" label criterion exercises a state real Squadron output cannot produce"
    location: "project-documents/user/slices/104-slice.findings-verdicts-and-provenance.md#functional-requirements"
---

# Review: slice — slice 104

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Matching rule, trust label, and provenance implement the architecture's identity, provenance, and unknown-as-value principles without drift

The key is location with line numbers removed plus normalized summary; severity is excluded with the architecture's own justification (reviewer's grade, downgraded `concern`→`note` between rounds), category is excluded as free-form data, and Squadron's positional `F001` is kept as data only — exactly the architecture's "Identity is content-based" and closed-vocabulary/free-form-data split. The trust label is one precedence-ordered pure function over stored fields, with `unparsed`, `findings_unparsed`, `unattested`, and explicit `not_reported`/`null` inputs making missing evidence explicit rather than defaulted; "A PASS the reviewer didn't really give" is `verdict == PASS` with label `derived`, reproducing the architecture's false-negative predicate. `upstream_version` is required but never compared, matching slice 102's provenance rule, and the rewording limit is pinned as a named contract boundary deferred to initiative 140, matching the architecture's normalization consideration.

### [PASS] Dependency directions, writer model, and integration claims verify against the completed 101–103 designs

Every claimed interface exists as described: `get_node` and `journal_entry`, `_execute` error translation, the `apply_submission` one-transaction pattern, `validate_envelope` and the kind→payload-model / kind→effect tables, `LISTINGS`/`run_listing`, the registry carrying only boolean flags and fixed choices (making the additive `value_options` claim accurate and minimal), `_takes_object`'s refuse-unknown-shape behavior, the `test_slice_104_listings_are_not_registered_here` pin, `EXPECTED_SCHEMA_VERSION = 4` going to 5, and the store-contract "not a findings store" line slated for removal. The Runner-writes-directly / Judge-through-inbox split matches the architecture's writer model; the store never importing inbox pydantic models preserves 103's direction; quarantine-vs-rejection reuses 103's established ladder; migration 005 correctly needs no backfill because it only adds tables; and `recorded_seq` arrival order plus id-first-wins retry mirror 103's D2/D4 decisions.

### [CONCERN] The crux tests' fixture source — captured 102 task-review rounds under `project-documents/user/reviews/` — does not exist in this checkout

The success criterion (line 320) requires that "the captured 102 task-review rounds in `tests/fixtures/sq_reviews/`" share no keys, and the Technical Requirement (line 340) states real review files are copied from `project-documents/user/reviews/` (including `archive/`). I verified that directory does not exist: `project-documents/` contains only `ai-project-guide/` and `user/`, with no `reviews/` under `user/`. `tests/fixtures/sq_reviews/` holds only two stdout captures dated 20260926 — single reviews of *different* slices (927 and this slice's own design), not consecutive rounds of one review type — and the fixtures README defers "more files" to implementation without saying from where. The Special Considerations (line 439) likewise names specific files (`103-review.code…`) that are absent, and the committed stdout fixture itself embeds a prior review finding flagging exactly this gap and asking that capture be made an explicit, verifiable prerequisite. As written, the slice's central risk mitigation — the rewording-limit test that pins the matching rule against real text — depends on input that cannot be located, and the design's own honesty rule ("the matching tests are only as honest as their input") is all that stands between this and quietly hand-building the "captured" rounds. Name the verifiable source (a git-history commit of this repo, or an explicit capture step against real artifacts) as a stated prerequisite.

### [NOTE] `finding_changes` on a nonexistent verdict id is unspecified

The Data Flow enumerates the "not comparable" case and the baseline-skip rules, but not the case where `verdict_id` names no verdict. The store's established convention is typed raise or explicit `None` (as `journal_entry` returns `None`); state which applies here so the error path isn't invented during implementation.

### [NOTE] `diff_truncated` is in the schema and `VerdictInput` but absent from the design's own "What Squadron emits today" list

Every other provenance field traces to the dated emitted-shapes list (lines 75–85) or to the upstream-delta note; `diff_truncated` appears in neither. If it is a real Squadron field (stdout JSON or frontmatter), add it to that list with its location so slice 105's parser design does not have to guess; if it is not, it is a nullable column that will only ever store null.

### [NOTE] The "CONCERNS with zero findings, findings_parsed=true" label criterion exercises a state real Squadron output cannot produce

Per the design's own emitted-shapes list (lines 82–84), a real CONCERNS/FAIL parsed with zero findings sets `fallback_used=true`, which the caller mapping turns into `findings_parsed=false` → `findings_unparsed`. The criterion is fine as table-driven coverage of the label function, but `evidence-contract.md` should state explicitly that the real-world zero-findings CONCERNS lands as `findings_unparsed` — and is therefore never a comparison baseline — since that conservative outcome is currently only implicit in the mapping sentence.

### Run Digest

- Response length: 7459 chars
- Response is newline-free: no
- Tool calls made: 31
- Tool calls failed: 1
- Stop reason: stop
- Reasoning characters: 73289
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Response

- **F003 (accepted, premise wrong).** `project-documents/user/reviews/` and `archive/` exist and are tracked; the reviewer's one failed tool call is the likely cause. The real gap stands: the design never named the rounds. Technical Requirements now list the exact files (part 1 and part 2, rounds 1 and 2, commits `bf6d292` and `20b3d70`), forbid substituting hand-built rounds, and use round 2's part 2 (a real provider failure) as the real input for `provider_failure` and "not comparable". Checked with the v1 rule: part 1 round 1 (9 findings) and round 2 (7 findings) share 0 keys.
- **F004 (accepted).** `verdict()` returns `None` like `get_node`/`journal_entry`; `observations` and `finding_changes` raise `VerdictNotFoundError`, since an empty result would look like a real empty review.
- **F005 (accepted).** `diff_truncated` and `requested_model` come from Squadron's committed but unbuilt SQ 927 design (in the first draft at `c525a63`, dropped in the split). Both are now in the emitted-shapes list, which says they stay null until Squadron ships them.
- **F006 (accepted).** The trust-label section now states that a real zero-finding CONCERNS or FAIL is `findings_unparsed` and never a baseline, and that the `stated` zero-findings criterion is label-table coverage only.
