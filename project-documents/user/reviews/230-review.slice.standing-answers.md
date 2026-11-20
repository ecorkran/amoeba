---
docType: review
layer: project
reviewType: slice
slice: standing-answers
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: amoeba
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/230-slice.standing-answers.md
aiModel: openai/gpt-6.1-sol
aiProfile: openrouter
status: complete
dateCreated: 20261120
dateUpdated: 20261120
reviewedSha: b4b5f9f08ede2023769286241d9d29b4364fdb18
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 116872
cachedTokens: 74895
completionTokens: 967
reasoningTokens: 318
durationSeconds: 31.1
costUsd: 0.101113
costBasis: alias_pricing
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Scope and dependency boundaries match the architecture"
    location: "project-documents/user/slices/230-slice.standing-answers.md#Integration-Points"
  - id: F002
    severity: pass
    category: architectural-alignment
    summary: "Authorization, retention and size-limit behavior are aligned"
    location: "project-documents/user/slices/230-slice.standing-answers.md#Technical-Decisions"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Uncertain MCP writes need a standing-answer-specific recovery contract"
    location: "project-documents/user/slices/230-slice.standing-answers.md#D10:-Failures"
---

# Review: slice — slice 230

**Verdict:** CONCERNS
**Model:** openai/gpt-6.1-sol

## Findings

### [PASS] Scope and dependency boundaries match the architecture

The design delivers slice 230’s assigned record, give/list/withdraw operations, and answering passages. Work in a repository and curation remain correctly assigned to 231 and 232. CLI and MCP share `wiring.invoke`, and passage assembly receives store-independent values, preserving the answering library’s dependency boundary. The mechanism count is proportionate to the slice.

### [PASS] Authorization, retention and size-limit behavior are aligned

D5–D8 preserve the parent’s explicit requirements: applicable standing answers are never silently trimmed; overflow produces `sources_too_large`; automatic answers retain the authorization checks; and member removal withdraws member-scoped rulings. Immutable text and retained withdrawn rows preserve cited evidence. Walking through creation, use, withdrawal, overflow and removal reveals explicit exits without editing state files.

### [CONCERN] Uncertain MCP writes need a standing-answer-specific recovery contract

D10 covers store failures and `cf` timeouts, but does not specify recovery when the new MCP write tools time out or the client disconnects before receiving their result. This matters because D2 deliberately makes repeated `standing` calls create duplicate active rows.

Slice 226’s inherited deadline handling allows an abandoned worker to finish after a timeout. Its generic write advice points callers to `status` or `decisions`, neither of which establishes whether a new standing answer was recorded. The walkthrough’s statement that a failed call is “safe to repeat” therefore needs qualification for an uncertain MCP outcome.

Specify that these tools use the existing deadline mechanism, whether writes continue after disconnect, and how callers determine the committed outcome. In particular, direct uncertain `standing` callers to `list standing` before retrying, and uncertain `withdraw` callers to `list standing --all` or an explicitly safe repeat. Cover a committed write whose response is lost with a fixture test; no new retry framework is necessary.

### Run Digest

- Response length: 2491 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: stop
- Output budget: backend default
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 1320
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 116872 / 74895 / not computed / 967 / 318
- Duration: 31.1 s
- Cost: $0.10 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 3
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 3
- Finding-shaped matches — surviving validation: 3
