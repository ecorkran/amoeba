---
docType: initiative-plan
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
dateCreated: 20260620
dateUpdated: 20261028
status: in_progress
---

# Initiative Plan: Amoeba

## Source

`000-concept.amoeba.md`

## Index Convention

**20-based** (100, 120, 140, 160) — the guide default. Initiatives here are moderate-breadth: each is a cohesive 3–12 slice body of work with room to insert (19 indices) between bands if one initiative spawns a sub-area during DFS development. A wider gap was considered and rejected — this is a single-supervisor tool, not a multi-team system, so large per-initiative expansion is unlikely. Indices are tentative and may be re-assigned.

## Decomposition rationale

The concept's Solution Approach named **7 components** (Runner, Run-state store, Routing engine, Judge, Notification bridge, Translator, Resident substrate). Those are *named pieces*, not initiatives — several are too small or too coupled to stand alone as a 3–12 slice initiative (the notification bridge is "a day of code"; the routing engine is a table plus the Runner's apply-step; the run-state store and the resident substrate are one foundational layer). Per the concept's **DFS-by-induced-failure** methodology — build the first vertical proof, then let failure tell you what to split — we group the 7 components into **4 initiatives** rather than fanning out heavily up front:

- **100** absorbs components 2 (Run-state store) + 7 (Resident substrate) — the foundational layer everything else reads/writes through.
- **120** absorbs components 1 (Runner) + 3 (Routing engine) — the deterministic spine; the project's core artifact. Since 2026-10-28 the routing engine has shrunk to "done, resume, question, or blocked", because Squadron's pipelines own review routing.
- **140** started as component 4 (Judge). Since 2026-10-28 it is the question answerer: the judgment Amoeba spends is on answering agents' questions, since Squadron already judges reviews.
- **160** absorbs components 5 (Translator) + 6 (Notification bridge) — the human-edge layer; both are read/write-state surfaces with narrow command authority.

## Initiatives

1. [x] **(100) Substrate & Run-State Store** — The foundational layer. A long-lived resident process to host the Runner loop, a durable message-queue for the Translator/Judge/(later) Cowork to leave each other messages, and the Amoeba-owned **structured run-state store**: per-node status (runnable / blocked-on-human / blocked-on-judge / done), open findings, blocked-states, and pending resolutions. Built fresh — the Squadron daemon is not reused (concept grounding update 2026-09-13: it is frozen, unsupported, and unused by Squadron's own pipeline engine). Establishes the **clean read/write interface** the other three initiatives attach to. Resolves the OQ6 boundary (Amoeba-internal component vs. peer primitive) at architecture time. **Scope added 2026-09-13 (PM):** absorbs Squadron's unstarted initiative 280 (Shared Agent Artifact Store — typed `review_findings` / `checkpoint` / `task_progress` / `devlog` artifacts) and (confirmed by PM 2026-09-13) CF initiative 220 (event-driven daemon with server-initiated notifications — the push seam replacing `cf next` polling). Boundary: Squadron keeps per-pipeline `RunState`; Amoeba's store is the project-lifecycle layer and references SQ run IDs. See `notes/002-upstream-delta.amoeba.md` §2. Dependencies: None (foundation). Status: complete
2. [x] **(120) Runner** — The deterministic supervisor and the project's core artifact, a tenant of 100's resident process. **Direction set 2026-10-28** (`notes/004-direction.amoeba.md`): Squadron owns the pipeline — phases, order, review thresholds, revisions, judges, CF pointer moves and the merge — so the Runner does not repeat any of it. For each project it launches the configured Squadron pipeline (built-in or user-written) on the slices its intents drive, watches every run by id, marks completed runs done, resumes runs that crashed or stopped for a transient reason (`sq run --resume`), hands runs paused on an agent's question to 140, and puts everything else on one blocked list across projects. Owns the `sq`/`cf` control surface (journaled commands, detached launch, observation by run id, crash recovery), the lifecycle model that mirrors CF's plan into 100's node tree, and the intent vocabulary (drive and hold) the PM and 160 steer it with. The checkpoint-as-persisted-blocked-state mechanic lives here, writing through 100's store. Slices 120–128 built a fuller routing engine first; slice 132 cuts it down to this. Amoeba never mutates Squadron thresholds at runtime. Dependencies: [100]. Status: in_progress
3. [ ] **(140) Question Answerer** — *Re-scoped 2026-10-28* (`notes/004-direction.amoeba.md`). Answers what Squadron agents ask mid-run, so runs finish without the PM. A run whose agent stopped to ask ("which branch?", "redesign or leave?") pauses with checkpoint kind `agent_question` and the question in `checkpoint.question` (`sq runs wait --json`). 140 answers from what Amoeba holds — the project's rules and plan, the program concept (180), and earlier answers to the same question — and resumes the run with `sq run --resume <id> --instructions "<answer>"`, restating the question in the answer because the rerun may not see the earlier conversation. A question it cannot answer goes on 120's blocked list, and the PM's answer returns through the same resume. Bounds: it only ever resumes with instructions; it never edits code, merges, or changes thresholds. Every question and answer is recorded, so a repeat is answered the same way and the PM can see what was decided for them. Squadron dependencies: questions from implement steps and a reply field on `artifact_missing` failures (agreed with Squadron 2026-10-28, not yet shipped); until then the full reply is read from the run-state file. Dependencies: [100, 120]. Status: not_started
4. [ ] **(160) Translator & Notification** — The human-edge layer. A conversational AI (Claude Code VS Code extension and/or chat/SDK surface, interchangeable) that converts natural-language intent into the deterministic command sequence and converts structured findings back to natural language. Owns the **narrow fixed command-authority whitelist** (OQ5) and never runs the project directly — it only reads/writes 100's store. Includes the notification bridge: outbound Discord webhook on escalation and an inbound path that lands the human's reply back into the blocked node's resolution. Dependencies: [100, 120]. Status: not_started
5. [ ] **(180) Program Record** — *Added 2026-10-20 (PM); tentative.* A level above projects for products built from several repos (`trading` = `trading-data` + `trading-engine` + `trading-ui` + more). Owns a combined-concept document, the member-project list, and cross-project dependency edges, and surfaces a cross-project blocked-on-me view. Store change is small: one table plus a nullable program key on projects. Open question to settle at architecture: cross-project visibility (may an agent in one project read another's state). See the concept's "Multi-project programs" section. Dependencies: [100, 120]. Status: not_started
6. [ ] **(200) Multi-Agent Chat** — *Added 2026-10-20 (PM); tentative.* One channel where each project's resident agent is a participant, so the PM works across projects in a single conversation. A client over the slice 109 network API; this is the original orchestration concept that became Squadron, absorbed here now that Squadron drops comms. Anchored on 180's program context. Dependencies: [100, 180]. Status: not_started

## Cross-Initiative Dependencies

- **120 depends on 100**: the Runner reads/writes per-node status, findings, and blocked-states through the run-state store, and runs *inside* the resident substrate. The Runner cannot exist without a place to persist what it learns. Blocking — 100's store interface must be stable before 120's loop is designed against it.
- **140 depends on 100 and 120**: the answerer records questions and answers in the store (100) and takes the paused runs the Runner hands it, resuming them through the Runner's journaled control surface (120). Blocking on both.
- **160 depends on 100 and 120**: the Translator reads/writes intent and escalations through the store (100) and issues commands that drive the Runner's loop (120); it must know the command surface and the blocked-state shape. Blocking on both.
- **140 and 160 are independent of each other**: both attach to the 100+120 spine but never interact directly — they communicate only through state, exactly as the concept's "parts never call each other directly" principle requires. They can be designed and built in either order (or in parallel) once the spine is stable.
- **180 depends on 100 and 120**: a program record adds one table and a nullable program key to 100's store, and its cross-project blocked-on-me view and dependency edges are only meaningful once 120's Runner produces per-project blocked-states. Blocking on both.
- **200 depends on 100 and 180**: the chat is a client over 100's network API (slice 109), and it is anchored on 180's program context to know which projects' agents share a channel. Through 180 it also comes after 120.

## Sequencing

DFS, not BFS. The build order is **100 → 120 → 140 → 160**: stand up the foundation, build the supervisor, then the question answerer (the main reason a run stops today), then the notification bridge that carries what is left on the blocked list to the PM and the answer back. Per "build by inducing failure," the questions agents actually ask and the stops that still reach the blocked list decide what 140 and 160 need first.

The tentative 180 and 200 (added 2026-10-20) come after: **140 → 180 → 200**. 180's program concept is one of the sources 140 answers from, so 140 works per project first and gains program context when 180 lands.

## Notes

- Indices are tentative and may be reassigned as initiatives are added or reorganized.
- New initiatives discovered during development (e.g., a Squadron-side **tier-field emission** or **auto-fix** capability, both currently deferred Squadron upgrades) are added here with the next available base index when they materialize — they are intentionally *not* Amoeba initiatives, since the concept places that logic on the CF/SQ side of the boundary.
- Check off initiatives as their architecture documents and slice plans are complete.
- The 7→4 grouping is a deliberate anti-fan-out choice; if DFS reveals a grouped pair wants independent architecture (e.g., the resident substrate proves heavy enough to own its own arch separate from the run-state store), split at that point and re-index.
