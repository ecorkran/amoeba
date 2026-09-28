---
docType: review
layer: project
reviewType: slice
slice: squadron-review-parser-and-ingest
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: feebdadfa161d32acc04e8bca13ed5df77f29a96
revision_number: 3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 29
runId: run-20260928-slices-plan-a04bdb07
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: concern
    category: documentation
    summary: "D6 attributes a store-creation guarantee to 103 that no parent document states"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:276"
  - id: F002
    severity: concern
    category: integration-points
    summary: "`source_document` pass-through ownership contradicts slice 105's stated interface requirement"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:51"
  - id: F003
    severity: note
    category: error-handling
    summary: "Ingest's file-read path does not enumerate non-regular files or a blocking read"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:147"
  - id: F004
    severity: note
    category: dependency-direction
    summary: "109's planned extension of `to_verdict_input` and `ingest` is a 109→108 dependency the plan does not list"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md#provides-to-other-slices"
  - id: F005
    severity: pass
    category: dependency-direction
    summary: "Dependency direction and the sole-writer model are honored"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:119-124"
  - id: F006
    severity: pass
    category: error-handling
    summary: "New I/O and submission paths have enumerated failure modes with explicit handling"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md:291-298"
  - id: F007
    severity: pass
    category: principles-alignment
    summary: "Design decisions align with the architecture's principles"
    location: "project-documents/user/slices/108-slice.squadron-review-parser-and-ingest.md#technical-decisions"
---

# Review: slice — slice 108

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] D6 attributes a store-creation guarantee to 103 that no parent document states

"This opens no store. 103 guarantees that a store file which exists is complete, because the process renames it into place only after migrating it." I checked all three parent designs: 101's lifecycle is "open a store at a path (creating and migrating as needed)" with no temp-file-and-rename creation step; 103's `open_project` says "Create-or-open the project's store read-write … A new store is migrated to the current schema by `Store.open` as usual" — no rename is mentioned, and 103's D1 rename is the *inbox file* hand-off, not store creation; 102's "Files are written atomically (write `.tmp`, then rename)" is about Squadron's run files, not Amoeba's stores. The rename-after-migrate mechanism cited here does not exist in any parent document. The check itself is still sound — the design already acknowledges the race it does not close, and a partially-created store would surface through 103's apply-failure path (attempts sidecar, `failed/`) rather than silently corrupting a verdict — but the safety argument for skipping a store open currently rests on a guarantee the dependency does not make. Either 103's design should actually specify atomic store creation, or this line should be re-justified (e.g., "the existence check is advisory; every downstream failure mode is enumerated and parked").

### [CONCERN] `source_document` pass-through ownership contradicts slice 105's stated interface requirement

105's "Interfaces Required" says, of 108: "`to_verdict_input` carries `sourceDocument` into `VerdictInput.source_document` (D7)" under the heading "**From slice 108** (to be written into 108's design)", and its D7 says the column is "filled by 108's parser from the frontmatter's `sourceDocument`" (105:238). This design explicitly excludes that: the parser "does not pass the value to `VerdictInput`. Slice 105 adds that field (its D7) and the one-line pass-through in `to_verdict_input`" (108:51), and the Provides section (108:344) likewise says 105 passes it on. But 105's own task list changes "`VerdictInput`, the payload, and the previous-round query" (105:241) and never names `to_verdict_input`. If each slice implements exactly its own document, detected reviews carry a null `source_document` and part-1/part-2 reviews merge into one series. The failure is loud, not silent — 105's integration requirement ("`finding_changes` on part 1, round 2 names part 1, round 1 as the previous round, never a part-2 review") would fail — but the two documents should agree on who writes the one-line pass-through before either is implemented.

### [NOTE] Ingest's file-read path does not enumerate non-regular files or a blocking read

The data flow handles `OSError` and `UnicodeDecodeError` explicitly, there is no network or subprocess I/O in this slice, and `submit()` validates before writing — so the hang/timeout/peer-disconnect class is largely inapplicable. One residual case is unspecified: `--artifact`/`--stdout-json` naming a FIFO, device, or other special file would block on open/read rather than raise, and nothing checks the path is a regular file. The sibling reader in 105 handles this explicitly ("Not a regular file (directory, socket), or not `*.md` → Ignored"). Given the command is operator-run and interactive this is minor; a one-line regular-file check, or a stated acceptance, would close the gap.

### [NOTE] 109's planned extension of `to_verdict_input` and `ingest` is a 109→108 dependency the plan does not list

The slice states 109 "adds `judge_invocation_id` to `to_verdict_input` and to `ingest`". That makes 109 modify this slice's public API and CLI — a code dependency of 109 on 108 — while the slice plan lists 109's dependencies as `[104]` only. The coupling is stated openly here rather than hidden, and 108 precedes 109 in the implementation order so no cycle arises, but the plan's dependency entry for 109 is incomplete relative to what both documents describe.

### [PASS] Dependency direction and the sole-writer model are honored

The parser imports only store vocabularies and dataclasses and never `Store`, `amoeba.inbox`, or `amoeba.process`; the store never imports `amoeba.upstream`; `cli/ingest.py` is the only module that knows both the parser and the inbox — matching the pattern 103 set with `InboxTenant` and 105 restates for its detection tenant. Ingest writes only through 103's inbox and never opens a store read-write, preserving the architecture's writer model ("the inbox is the one surface that parts *outside* the resident process write to directly") and the writer-guard invariant. Both directions are pinned by an asserted test in Technical Requirements, and the sibling `run_pruning.py` 106 plans for this package is explicitly declared as a non-dependency.

### [PASS] New I/O and submission paths have enumerated failure modes with explicit handling

Every step of the ingest flow names its failure and its exit: unreadable file (`OSError`/`UnicodeDecodeError` → 12), parse failure (`SquadronParseError` → 12, with the underlying error chained), unresolvable version label (`UpstreamVersionError` → 12), refusal to submit into a nonexistent project (9, decided before any file is read), and inbox refusal (`InboxSubmitError` → 9) — with "at every failing step, nothing reaches `inbox/new/`" stated and tested for the process both running and stopped. Catches are typed and explicit; plain `ValueError` deliberately escapes to the boundary handler as `FAILURE`, per the project's exception rules. The four terminal submission outcomes (103's vocabulary) are each mapped to where the PM finds them.

### [PASS] Design decisions align with the architecture's principles

The adapter lives outside the store and parses only review output, exactly as the architecture assigns ("It owns parsing of Squadron **review output** … as an adapter outside the store"), with run files, CF MCP results, and pipeline state explicitly left to 102/120. "Nothing is defaulted" operationalizes the architecture's "Unknown is a value, not a default": missing required keys, unknown verdict/severity words, malformed YAML/JSON, and no-JSON-object all raise typed errors naming the key and source. D4 makes the upstream version a required label that is never compared or branched on, matching "Every ingested record stores the upstream version it was parsed from." D5's parsed-content digest implements content-based identity at the record level — satisfying 105's stated requirement — and the file-vs-stdout id divergence is analyzed with its visible effects enumerated and a caller rule stated, rather than papered over. The exclusions (dropped diagnostics with the id-stability consequence stated, deferred `source_document`, judge samples to 109, detection and attribution to 105) keep the slice inside the scope the architecture and the slice plan define.

### Run Digest

- Response length: 8890 chars
- Response is newline-free: no
- Tool calls made: 29
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 56486
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
