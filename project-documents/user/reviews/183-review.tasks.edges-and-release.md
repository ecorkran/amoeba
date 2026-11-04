---
docType: review
layer: project
reviewType: tasks
slice: edges-and-release
project: amoeba
verdict: FAIL
verdictSource: imposed
sourceDocument: project-documents/user/tasks/183-tasks.edges-and-release.md
aiModel: squadron-task-gate
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: 6c3f0b9b0f6262ca65af4f5c7d2f57ac23e35fd8
runId: run-20261104-tasks-plan-a982fbc3
squadronVersion: 0.24.19
findings:
  - id: F001
    severity: fail
    category: merge-step
    summary: "Merge step at line 224: - [ ] Main path, one test: ticks show `provider_not_done`; the provider's run completes and the head is recorded; `not_on_target` until the test merges the branch into the provider's target; satisfied; release writes the resolution; the next tick resumes the run and the instructions text is the one `release_instructions` builds; a late PM resolution on the block is rejected as already resolved."
    location: "project-documents/user/tasks/183-tasks.edges-and-release.md:224"
---

# Review: tasks — slice 183

**Verdict:** FAIL
**Model:** squadron-task-gate

## Findings

### [FAIL] Merge step at line 224: - [ ] Main path, one test: ticks show `provider_not_done`; the provider's run completes and the head is recorded; `not_on_target` until the test merges the branch into the provider's target; satisfied; release writes the resolution; the next tick resumes the run and the instructions text is the one `release_instructions` builds; a late PM resolution on the block is rejected as already resolved.

Line 224 schedules a merge: `- [ ] Main path, one test: ticks show `provider_not_done`; the provider's run completes and the head is recorded; `not_on_target` until the test merges the branch into the provider's target; satisfied; release writes the resolution; the next tick resumes the run and the instructions text is the one `release_instructions` builds; a late PM resolution on the block is rejected as already resolved.`. Merging happens in Phase 7 after code review passes; a task file must not contain it. Matched rule: git_object_window.

-> project-documents/user/tasks/183-tasks.edges-and-release.md

### Run Digest

- Response length: 126 chars
- Response is newline-free: yes
- Tool calls made: not offered
- Tool calls failed: not computed
- Stop reason: not computed
- Output budget: backend default
- System prompt: not computed
- Settings sources: not computed
- Reasoning characters: not computed
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / cache write / completion / reasoning: not computed / not computed / not computed / not computed / not computed
- Duration: not computed
- Cost: not reported
- `## Summary` located: not computed
- `## Findings` located: not computed
- Finding-shaped matches — whole response: not computed
- Finding-shaped matches — inside fences: not computed
- Finding-shaped matches — in findings section: not computed
- Finding-shaped matches — surviving validation: not computed
