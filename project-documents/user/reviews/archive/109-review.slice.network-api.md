---
docType: review
layer: project
reviewType: slice
slice: network-api
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/109-slice.network-api.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 07aa0b7963eedfa5e37c8ac9c3ea858e56087bdd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 37.3
runId: run-20261008-p4-76c1c140
squadronVersion: 0.21.1
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Core architectural constraints honored"
    location: "project-documents/user/slices/109-slice.network-api.md#Overview"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Open SSE streams are never re-authenticated"
    location: "project-documents/user/slices/109-slice.network-api.md#State Management"
  - id: F003
    severity: concern
    category: architecture
    summary: "Multi-host claim conflicts with SQLite WAL"
    location: "project-documents/user/slices/109-slice.network-api.md#D8"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Status lookup race with quarantine and failed moves is unspecified"
    location: "project-documents/user/slices/109-slice.network-api.md#Data Flow"
  - id: F005
    severity: concern
    category: scope
    summary: "Scope extends well beyond the architecture's three surfaces"
    location: "project-documents/user/slices/109-slice.network-api.md#Technical Scope"
  - id: F006
    severity: concern
    category: under-specification
    summary: "Stall bound rests on an unverified uvicorn behavior"
    location: "project-documents/user/slices/109-slice.network-api.md#D5"
  - id: F007
    severity: note
    category: documentation
    summary: "Frontmatter dependencies omit 105, 107 and 108"
    location: "project-documents/user/slices/109-slice.network-api.md:6"
  - id: F008
    severity: note
    category: integration
    summary: "Token directory name could collide with project discovery"
    location: "project-documents/user/slices/109-slice.network-api.md#Database / Storage Schema"
  - id: F009
    severity: pass
    category: error-handling
    summary: "Failure modes and bounds enumerated for new I/O paths"
    location: "project-documents/user/slices/109-slice.network-api.md#D5a"
---

# Review: slice — slice 109

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Core architectural constraints honored

The architecture's constraints are met:
- `amoeba serve` is its own process and takes no lock (D8).
- It binds to `127.0.0.1` by default, and non-loopback binds require tokens and TLS (D6).
- Stores are opened read-only.
- The only write is `inbox.submit()` (D4).
- The writer guard is extended to cover `amoeba.serve` and `amoeba.inspection`.

Dependency directions are stated and correct. `serve` imports `inspection`, `inbox`, `feed` and `store`, and nothing imports `serve` except `cli/serve.py`. Restating the 106 `follow_interval_seconds` and 103 `idle_interval_seconds` latency bounds is the right treatment of the NFR, since the architecture sets no numeric targets. The slice says so explicitly.

### [CONCERN] Open SSE streams are never re-authenticated

Tokens are checked when a stream connects. The doc says the token file is re-read on every authenticated request "so a revocation takes effect at once", and D6 defines fail-closed behavior when the file breaks. But a stream lives for hours. The design doesn't say what happens to an already-open stream when:
- its token is revoked,
- the token file becomes unreadable or malformed, or
- the principal's scope changes.

As written, a revoked client keeps receiving the feed until it disconnects. That contradicts the "revocation takes effect at once" claim and the fail-closed table. Decide one of two things:
- Re-validate on each heartbeat and close the stream with a terminal event when validation fails.
- Document that revocation applies only to new connections, and add that to the contract and Success Criteria.

### [CONCERN] Multi-host claim conflicts with SQLite WAL

D8 says several servers "on different ports or hosts" may run at once. Read-only opens of a WAL-mode SQLite store need shared-memory access to `-shm`, which is not supported across hosts or network filesystems. Submissions from a server on another host would also need a shared inbox filesystem. The architecture's "no new state, no new write path" holds only for same-machine deployment. Restrict the claim to multiple servers on the same host, and state in `network-contract.md` that the server must run on the supervisor's machine.

### [CONCERN] Status lookup race with quarantine and failed moves is unspecified

The status flow handles the applied transition with a store, directory, store sequence. It says nothing about the process moving a file from `new/` to `quarantine/` or `failed/` while `locate` scans. If `locate` scans `quarantine/` and then `new/`, it can miss a file that moved in between. The client then gets `404 unknown_submission` for a submission that exists. Specify the scan order, or a re-scan, so a rename mid-lookup cannot produce a false 404. Add a test for it.

### [CONCERN] Scope extends well beyond the architecture's three surfaces

The architecture asks for reads, inbox writes and a live feed. This slice also adds:
- a relocation of 102, 104 and 105–108 listing code into a new `amoeba.inspection` package,
- a signature change from `argparse.Namespace` to `ListingQuery`,
- an `abbreviated_columns` change,
- `inbox.locate`,
- a token file and `amoeba token` CLI with scopes,
- a TLS requirement,
- listing discovery.

Each addition is justified, and the PM-ratification table gates the dependency, TLS, principal-binding, scope and exit-code decisions. But the registry move is a cross-slice refactor that depends on an ordering assumption: 105–108 task documents target `amoeba.cli`. The effort estimate also grew from 3 to 4. Consider splitting the registry move and `change_as_json` relocation into a precursor slice or task group, so the network work isn't blocked by a large no-behavior-change refactor. At minimum, make the ordering assumption a hard gate rather than a note.

### [CONCERN] Stall bound rests on an unverified uvicorn behavior

The `stream_stall_seconds` mechanism assumes "uvicorn's send waits for the transport to drain". Slow-header handling is explicitly deferred to verification (D5a), but this assumption isn't. If it fails, the stalled-peer and slot-exhaustion mitigations fail. Add the same verify-at-implementation task, with a fallback of an explicit write timeout around each send.

### [NOTE] Frontmatter dependencies omit 105, 107 and 108

The body states 105, 107 and 108 are an ordering assumption, not functional prerequisites, and the frontmatter lists only 101–104 and 106. This is consistent but easy to miss. The body also says the ordering is "recorded on the 109 entry in the slice plan". Confirm that entry actually exists.

### [NOTE] Token directory name could collide with project discovery

The new `{supervisor_dir}/serve/tokens` path sits beside project stores. I did not verify how `discover_project_ids` enumerates the supervisor directory. Confirm that a `serve/` directory is never treated as a project, and that `validate_project_id` rejects it. Add a test if it isn't already covered.

### [PASS] Failure modes and bounds enumerated for new I/O paths

Waits and failures are bounded and mapped to explicit statuses in D5a:
- a contended store,
- a slow body or slow headers,
- a stalled stream reader,
- idle connections,
- too many streams or connections,
- shutdown,
- token file corruption.

Errors that occur before streaming are separated from errors that occur during it. The retry-with-same-id semantics for submissions are explicit, and the checkpoint-pinning risk is covered by a named test.

### Run Digest

- Response length: 6925 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 37.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
