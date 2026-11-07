---
docType: initiative-plan
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
dateCreated: 20260620
dateUpdated: 20261106
status: in_progress
---

# Initiative Plan: Amoeba

## Source

`000-concept.amoeba.md`, rewritten 20261106 from `notes/005-usage-scenarios.amoeba.md`. The earlier version of this plan is in git history.

## Index Convention

**20-based** (100, 120, 140, ...), the guide default. Indices are tentative and may be reassigned. Retired indices stay listed so that existing documents keep their meaning.

## Decomposition rationale

Initiatives 100 to 140 were built from the bottom up, and 160 to 200 were planned the same way. The new concept starts from three scenarios and one job description, and that job is a single coherent system: a tool that knows the program, handles first-level questions and keeps the record. So all remaining work goes in **one initiative**, with one architecture document and one slice plan.

Splitting it again (say, questions in one initiative and programs in another) would give two architecture documents that have to agree on the same operations, the same store and the same answer to "does anything stay running?". Split later only if the work itself shows a reason to.

## Initiatives

1. [x] **(100) Substrate & Run-State Store** — Built: the SQLite store, resident process, inbox of submission files, network API and related contracts. The concept keeps the store, reduced to what the scenarios need; the rest has to be justified by a scenario. 220's audit decides what stays. Dependencies: None. Status: complete
2. [x] **(120) Runner** — Built: launches and watches Squadron runs, resumes runs that stopped for a transient reason, hands paused runs to 140 and keeps the blocked list. The concept says Amoeba starts no work, so launching at least is in question. 220's audit decides what stays. Dependencies: [100]. Status: complete
3. [x] **(140) Question Answerer** — Built: the question record, source passages and the two-step answering pipeline, plus a gate around the answer. The record and the pipeline are the core of the new concept. Checks on an answer belong in the pipeline as Squadron steps, so the gate is in question. 220's audit decides what stays. Dependencies: [100, 120]. Status: complete
4. [ ] **(160) Translator & Notification** — Retired 20261106. The Translator is now the PM's separate chat agent app. The Discord bridge is dropped, because Amoeba notifies agents and agents already reach the PM. Status: deprecated
5. [ ] **(180) Program Coordination** — Retired 20261106. Slices 180 (slice-writing pipeline) and 181 (program record) are merged. Slice 182 (program concept as a source) is parked on its branch, unmerged, and slices 183 to 186 are paused. Edges with hold and release, requests between members, and ordering are not in any scenario, and some of them walk the dependency graph, which the concept rules out. What programs still need moves to 220. Status: deprecated
6. [ ] **(200) Multi-Agent Chat** — Retired 20261106. Not Amoeba: the PM's chat and agent-to-agent talk live elsewhere. Status: deprecated
7. [ ] **(220) Program Tool** — Everything the concept asks for, built by cutting down what exists before adding to it. Scope:
   - **Scenarios A, B and C** from the concept: a question while the PM is away, a change in one member reaching another, and the PM asking where things stand. Scenario A, end to end on a real run the PM started, is the first proof.
   - **One set of operations**, over MCP for agent sessions and a CLI for pipelines and scripts. No MCP server exists today.
   - **Answering on runs Amoeba did not launch**, resuming only the run that asked.
   - **The program model** at the size scenario B needs: members, what each depends on, and what each has released.
   - **The record** of who asked what, which model answered, from what, and what the PM overrode.
   - **An audit of today's code** against the scenarios, sorting about 34k lines in `src` and 69k in `tests` into keep, move to Squadron, or delete, and doing the deleting. Slices 182 to 186 are re-judged here.
   - **The architecture document answers the concept's six open questions**, starting with who notices a paused run, since that decides whether a resident process exists at all.

   Out of scope: launching member pipelines, notification mechanics, chat, and any check on an answer that could be a Squadron step. Dependencies: [100, 120, 140]. Status: not_started

## Cross-Initiative Dependencies

- **120 depends on 100, and 140 depends on 100 and 120.** These hold for the code as built. 220's audit may remove the dependencies along with the code.
- **220 depends on 100, 120 and 140.** It inherits their code and is what cuts it down, so it can change or delete any of it. It also inherits slices 180 and 181 from retired 180.

## External Dependencies

- **`ecorkran/squadron#299`:** answering on Claude models. Until it lands, the answering steps' `allowed_tools: []` is refused on the `sdk` profile, so scenario A can't run on those models.
- **The PM's chat agent app:** the natural agent to tell when a question goes to the PM, and it isn't finished. The architecture has to answer open question 5 without waiting for it.
- **Three more Squadron changes,** listed in `220-arch.program-tool`: a command started when a run pauses, the working directory in the run file with JSON from `sq runs list`, and a command step in pipelines.

## Sequencing

Work 220 in this order:

1. **Architecture:** one new document, `220-arch`, answering the six open questions.
2. **Audit:** sort the code against the scenarios and the architecture.
3. **Slice plan:** rebuilt from the audit result.
4. **Scenario A,** then whatever it shows is next. The slice plan sets the order of B and C.

Nothing new gets built before the audit, and slices 183 to 186 stay paused until the slice plan re-judges them.

## Notes

- Until 220's architecture exists, the older architecture documents (`100-arch`, `120-arch`, `140-arch`, `180-arch`) describe what was built. Where they differ from the concept, the concept governs.
- A new need starts as a new scenario in the concept, not as a new initiative here.
- Check off initiatives as their architecture documents and slice plans are complete.
