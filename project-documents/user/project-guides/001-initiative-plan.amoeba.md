---
docType: initiative-plan
layer: project
project: amoeba
source: user/project-guides/000-concept.amoeba.md
dateCreated: 20260620
dateUpdated: 20260620
status: not_started
---

# Initiative Plan: Amoeba

## Source

`000-concept.amoeba.md`

## Index Convention

**20-based** (100, 120, 140, 160) — the guide default. Initiatives here are moderate-breadth: each is a cohesive 3–12 slice body of work with room to insert (19 indices) between bands if one initiative spawns a sub-area during DFS development. A wider gap was considered and rejected — this is a single-supervisor tool, not a multi-team system, so large per-initiative expansion is unlikely. Indices are tentative and may be re-assigned.

## Decomposition rationale

The concept's Solution Approach named **7 components** (Runner, Run-state store, Routing engine, Judge, Notification bridge, Translator, Resident substrate). Those are *named pieces*, not initiatives — several are too small or too coupled to stand alone as a 3–12 slice initiative (the notification bridge is "a day of code"; the routing engine is a table plus the Runner's apply-step; the run-state store and the resident substrate are one foundational layer). Per the concept's **DFS-by-induced-failure** methodology — build the first vertical proof, then let failure tell you what to split — we group the 7 components into **4 initiatives** rather than fanning out heavily up front:

- **100** absorbs components 2 (Run-state store) + 7 (Resident substrate) — the foundational layer everything else reads/writes through.
- **120** absorbs components 1 (Runner) + 3 (Routing engine) — the deterministic spine; the project's core artifact.
- **140** is component 4 (Judge) plus the Amoeba-side consensus aggregation the concept identified as Amoeba's to own (finding D).
- **160** absorbs components 5 (Translator) + 6 (Notification bridge) — the human-edge layer; both are read/write-state surfaces with narrow command authority.

## Initiatives

1. [ ] **(100) Substrate & Run-State Store** — The foundational layer. A long-lived resident process to host the Runner loop, a durable message-queue for the Translator/Judge/(later) Cowork to leave each other messages, and the Amoeba-owned **structured run-state store**: per-node status (runnable / blocked-on-human / blocked-on-judge / done), open findings, blocked-states, and pending resolutions. Reuses the relocated Squadron daemon as its base where it fits (concept finding E: pipeline runs don't depend on the daemon, so it is safe to relocate). Establishes the **clean read/write interface** the other three initiatives attach to. Resolves the OQ6 boundary (Amoeba-internal component vs. peer primitive) at architecture time. Dependencies: None (foundation). Status: not_started
2. [ ] **(120) Runner & Routing Engine** — The deterministic state machine and the project's core artifact: `while runnable work exists → run CF/SQ command → parse structured findings → apply routing table → {advance | spawn Judge | write blocked-state}`. Owns the CF/SQ control surface (shell/MCP out to `cf` and `sq`; lenient findings parsing) and the **Tier 1/2/3 routing table**, including v1 tier *inference* inside Amoeba (concept decision: no Squadron tier field yet — inference leans on `severity` + heuristics, since Squadron's `category` is free-form; the emitted tier field is Squadron dependency **S1**). v1 routing is **continue / Judge / escalate** (auto-fix is a deferred Squadron-side capability, finding B/OQ1). The checkpoint-as-persisted-blocked-state mechanic lives here, writing through 100's store. Dependencies: [100]. Status: not_started
3. [ ] **(140) Judge & Consensus** — The ephemeral on-demand evaluation node (pseudopod): a Squadron pipeline invoked N times across runs and/or the multi-provider pools Squadron exposes, plus the **Amoeba-side agreement metric** that turns N verdicts into `(resolution, confidence)` (concept finding D — Squadron has no consensus primitive, so aggregation is Amoeba's to build). The Runner applies a deterministic threshold to the result; initial threshold is **always-escalate** until per-category trust is earned. Owns the OQ4 calibration parameters (N, per-run vs per-model, trust-earning mechanism). Reads findings + locked constraints from 100's store; the Runner (120) is what spawns/reabsorbs it. Dependencies: [100, 120]. Status: not_started
4. [ ] **(160) Translator & Notification** — The human-edge layer. A conversational AI (Claude Code VS Code extension and/or chat/SDK surface, interchangeable) that converts natural-language intent into the deterministic command sequence and converts structured findings back to natural language. Owns the **narrow fixed command-authority whitelist** (OQ5) and never runs the project directly — it only reads/writes 100's store. Includes the notification bridge: outbound Discord webhook on escalation and an inbound path that lands the human's reply back into the blocked node's resolution. Dependencies: [100, 120]. Status: not_started

## Cross-Initiative Dependencies

- **120 depends on 100**: the Runner reads/writes per-node status, findings, and blocked-states through the run-state store, and runs *inside* the resident substrate. The Runner cannot exist without a place to persist what it learns. Blocking — 100's store interface must be stable before 120's loop is designed against it.
- **140 depends on 100 and 120**: the Judge reads a finding and its locked constraints from the store (100) and is spawned/reabsorbed by the Runner against a finding the routing table flagged Tier-2 (120). It needs both the store interface and the Runner's finding/spawn contract. Blocking on both.
- **160 depends on 100 and 120**: the Translator reads/writes intent and escalations through the store (100) and issues commands that drive the Runner's loop (120); it must know the command surface and the blocked-state shape. Blocking on both.
- **140 and 160 are independent of each other**: both attach to the 100+120 spine but never interact directly — they communicate only through state, exactly as the concept's "parts never call each other directly" principle requires. They can be designed and built in either order (or in parallel) once the spine is stable.

## Sequencing

DFS, not BFS. The intended build order is **100 → 120 → (140 ‖ 160)**: stand up the foundation, build the deterministic spine, then attach the two judgment/edge layers. The first vertical proof (drive `trading-data` to add Kalshi) cuts across all four but is led by 120's loop; per "build by inducing failure," where the first proof stops that it shouldn't have is what tells us whether any of these four needs to split further. The Kalshi-API discovery research step (OQ7) is a front-loaded input to that first proof and is not itself an initiative.

## Notes

- Indices are tentative and may be reassigned as initiatives are added or reorganized.
- New initiatives discovered during development (e.g., a Squadron-side **tier-field emission** or **auto-fix** capability, both currently deferred Squadron upgrades) are added here with the next available base index when they materialize — they are intentionally *not* Amoeba initiatives, since the concept places that logic on the CF/SQ side of the boundary.
- Check off initiatives as their architecture documents and slice plans are complete.
- The 7→4 grouping is a deliberate anti-fan-out choice; if DFS reveals a grouped pair wants independent architecture (e.g., the resident substrate proves heavy enough to own its own arch separate from the run-state store), split at that point and re-index.
