---
docType: review
layer: project
reviewType: slice
slice: the-cut
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/221-slice.the-cut.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261107
dateUpdated: 20261107
reviewedSha: 1ef86a09c6e67246431dd76bf42d0e36bdfff1f7
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
effort: high
turns: 6
promptTokens: 304069
cachedTokens: 195795
cacheWriteTokens: 108266
completionTokens: 7122
durationSeconds: 63.0
costUsd: 0.52472
costBasis: provider
runId: run-20261107-slices-plan-813acacc
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Migration steps cannot each end green: D2 severs change signatures whose callers are deleted later"
    location: "project-documents/user/slices/221-slice.the-cut.md:223-228"
  - id: F002
    severity: concern
    category: integration
    summary: "D6 rule 2 is scoped to all of `src/amoeba` and will block 222 and 226"
    location: "project-documents/user/slices/221-slice.the-cut.md:156-164"
  - id: F003
    severity: concern
    category: verification
    summary: "The delete-list check passes silently if it parses nothing"
    location: "project-documents/user/slices/221-slice.the-cut.md:282-293"
  - id: F004
    severity: note
    category: risk
    summary: "Live end-to-end coverage lapses between 221 and 223"
    location: "project-documents/user/slices/221-slice.the-cut.md:181"
  - id: F005
    severity: note
    category: scope
    summary: "Predicted verdicts and the architecture's \"keep and rework\" language"
    location: "project-documents/user/slices/221-slice.the-cut.md:130"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Layering, dependency direction and plan alignment"
    location: "project-documents/user/slices/221-slice.the-cut.md#Component Structure"
---

# Review: slice — slice 221

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Migration steps cannot each end green: D2 severs change signatures whose callers are deleted later

The plan requires format, lint, typecheck and the default suite to pass at the end of every step. Step 2 applies the D2 severs. For example, `assemble_sources` goes from `(Store, Node)` to `(slice ref, PmAnswer tuple)`. Step 3 is where the old callers go (`launch.py`, `stage.py`, `settle.py`, `finish.py`, the rest of `runner/`). Step 2 only lets the old code import moved value types from their new home. It says nothing about callers of severed signatures, so pyright fails until step 3.

Step 1 also deletes `cli/`, but D7 removes the `[project.scripts] amoeba` entry only in step 4. The console entry then points at a deleted package for three steps, and no check catches it.

Fix one of these:
- Sever each function in the same step that deletes its callers.
- State that the green rule applies only at the step 3 and step 4 markers.

Move the entry-point and wheel-artifact edits into step 1 next to the deletions they depend on.

The first option avoids editing doomed code just to keep it compiling, which is the cheaper route.

### [CONCERN] D6 rule 2 is scoped to all of `src/amoeba` and will block 222 and 226

Rule 2 says no module under `src/amoeba` imports outside the standard library, `pydantic`, `pydantic_core` and `yaml`. That is correct for `answering` and `upstream`. The architecture then adds a CLI (222), an MCP server (226) and a store. These will probably need a CLI framework or an MCP library, and the boundary test would fail on them.

This conflicts with the stated integration requirement that "222's design can add `amoeba.store` and a console entry point without removing anything left over" (line 268). The test would also force 222 to loosen a rule 221 wrote. Scope rule 2 to `amoeba.answering` and `amoeba.upstream`, which is the layering D3 actually defines. Leave later packages to their own slices.

### [CONCERN] The delete-list check passes silently if it parses nothing

Verification step 2 expects "print nothing". The `awk` pipeline also prints nothing if `/tmp/verdicts` ends up empty or malformed. That happens if the audit's table layout differs from what the command assumes, and the audit does not exist yet. A parse failure would then look like a successful cut. This leaves the criterion "no file maps to a `delete` or `squadron` row" (line 251) unverified. The project's own rules say a parser that returns empty on bad input needs a guard and a real-format test.

The check also re-implements the audit's longest-prefix rule in a second script. Cut it down by reusing the audit's section 11 tooling, or by adding two guards: fail if `/tmp/verdicts` is empty, and require at least one `keep` row and one `delete` row.

### [NOTE] Live end-to-end coverage lapses between 221 and 223

The architecture says the live answering tests "stay and become the check on scenario A". D8 deletes `test_answering_run.py` and `stage_harness.py` now, because they import the stage. It requires a claim and a restore commit in audit section 8, and the slice plan allows this ("or the audit records why one waits on 223"). The mitigation is adequate. The only residual risk is that 222 lands with no live run-level check, and that is acceptable.

### [NOTE] Predicted verdicts and the architecture's "keep and rework" language

The architecture table says `program/` is "kept and reworked" and that `runner/answering` launching is rewritten. D2 predicts `program/members.py`, `launch.py`, `stage.py` and `settle.py` become `delete`, with 222 and 223 rebuilding them. The audit owns these verdicts, and D1 requires the audit row to change in the same commit, so this is consistent with the plan. The audit, not this design, should record why each differs from the architecture's expectation.

### [PASS] Layering, dependency direction and plan alignment

`answering → upstream → stdlib/pydantic/yaml` matches the architecture's "small" goal and its read-don't-mirror principle. D4 puts the value vocabulary in `answering.values`, so 222's store depends on answering and not the reverse. D5 drops `max_concurrent_runs`, as the architecture requires. The slice leaves the new store, config loader, launch and resume, `status` and `decisions` to 222 to 224, and it does not merge the slice 182 branch. The plan's success criteria are all covered: deletions with tests, passing checks, standalone answering tests, live-test handling, no imports of deleted code, and the README rewrite. Nothing in the slice adds a new I/O path or touches an architecture NFR, so failure-mode enumeration and NFR restatement do not apply.

### Run Digest

- Response length: 5770 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 304069 / 195795 / 108266 / 7122 / not computed
- Duration: 63.0 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
