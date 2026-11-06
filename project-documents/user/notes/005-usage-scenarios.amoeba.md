---
docType: notes
layer: project
project: amoeba
source: user/notes/004-direction.amoeba.md
audience: [human, ai]
description: Usage-first reset, 20261106. What Amoeba is for, who runs it and how, three scenarios a human would actually live through, and what that implies for the code. Draft for PM markup; slices 183-186 are paused until this settles.
dateCreated: 20261106
dateUpdated: 20261106
status: complete
---

# Amoeba: who uses it, and how

Draft for markup. Nobody has run Amoeba yet, and nobody knows when they would. This page starts from the person and the agents using it, not from the store.

## What it is for

Two jobs Squadron can't do, because Squadron lives inside one repo and one run at a time:

1. **Programs.** A set of repos that depend on each other: `trading-*`, or Squadron + Context Forge + ai-project-guide. Amoeba knows the members, what each one is working on, and what each one is waiting on from the others.
2. **First-level human-in-the-loop.** An agent stops to ask a question. A model answers it from the right context (project rules, the program concept, your earlier answers), or the question comes to you. This is routing and context. The answering itself is a Squadron pipeline.

What it is **not**:

- A second pipeline engine.
- A pile of gates. Squadron has those.
- A chat system.

Determinism matters in one place: **the record**. Who asked what, which model answered, from what, and what you overrode. That's a table and a way to read it.

## The interface rule

**In normal use, a human never types an `amoeba` command.** If you have to stop and think "is that amoeba or squadron?", the design has failed.

- **Agents and pipelines** reach it through one set of operations, exposed two ways: MCP (for agent sessions) and a CLI (for pipelines and scripts, since Squadron steps run shell commands). Same operations, same names.
- **You** reach it from where you already are:
  - In a Claude Code session, by asking ("what's blocking trading?"). The session uses the MCP tools.
  - Through a notification when something needs you.
  - Later, possibly a dashboard or a chat front end. None is planned now.
- **Set-up** is the only exception: register a program and its members once, then forget it. Ideally that's also done by an agent ("add trading-ui to the trading program").

## Who runs it

The real question is whether anything has to happen when **no run is active and nobody asked**.

- **If no:** nothing stays running. Amoeba is a store, an MCP server (started by whatever session uses it, like every other MCP server) and a CLI. Squadron calls it at the moment it needs an answer. Nobody starts or stops anything.
- **If yes:** a background service starts at login (launchd), with no flags to remember, and watches every Squadron run, not only the ones it launched. You never interact with it directly.

**Recommendation:** start with no resident process, and add one only when a scenario below can't work without it. Today's Amoeba has a resident loop with 17 start-up flags, an inbox of submission files and a separate HTTP server. All of that is the "yes" answer, built before anyone asked the question.

## Scenario A: a question while you're away

You start `sq run p6` on trading-ui at night. At task 4 the agent asks: "keep the old order form or replace it?"

1. Squadron pauses the run on the question, as it does today.
2. Squadron (or a watcher) hands the question to Amoeba with the run id.
3. Amoeba gathers context: trading-ui's rules and plan, the trading concept, and your past answers to similar questions. It runs the answering pipeline.
4. If answered: the run resumes with the answer, and the answer is recorded.
5. If not: you get one notification ("trading-ui is waiting on: keep the old order form?"). You answer from wherever you are, and the run resumes.

**You type:** nothing, unless you're asked. **You see:** in the morning, the run is done, and a short list of what was decided on your behalf.

**Open:**

- Does Squadron call Amoeba when it pauses (a hook, so no watcher is needed), or does something poll? A hook is simpler and needs a Squadron change.
- Notification channel: macOS notification, phone push or Slack?
- Answering on Claude models needs ecorkran/squadron#299.

## Scenario B: a change in one member blocks another

trading-api changes the shape of its order endpoint. trading-ui's next slice uses that endpoint.

1. When trading-api's slice merges, its pipeline tells Amoeba what changed and which interfaces it touched. That's one step at the end of the pipeline.
2. When trading-ui starts its next slice, its pipeline asks Amoeba whether anything it depends on has changed.
3. Amoeba answers with the change and where it came from. The slice either picks it up (the design agent gets it as context) or stops with a reason.

**You type:** nothing. **You see:** the trading-ui slice either accounts for the API change or tells you why it stopped.

**Open:** how a member declares what it depends on. Today that's the 180-series program record. It may be too much or too little for this.

## Scenario C: you want to know where things stand

In any Claude Code session: "where's trading at?"

The session calls Amoeba through MCP and gets a short status for each member: what's running, what's blocked and why, and what was answered for you since you last looked.

**You type:** a question, in plain English, in the tool you already have open.

## What this implies for the code (to check, not decided)

A proper audit follows once you've marked this up. My expectations:

- **Keep and center:** the program record, the question/answer record, the context gathering for answers, and the answering pipeline itself (it's already a Squadron pipeline).
- **Move to Squadron or drop:** the gate- and contract-style machinery around the answerer, and anything that rebuilds pipeline policy.
- **Question each piece:** the resident loop and its tunables, the inbox submission files, the separate HTTP server, and launching runs. Each stays only if a scenario needs it.
- **Add:** an MCP server over the same operations the CLI has.

## Questions for you

1. Is the "no human commands in normal use" rule right?
2. Should Amoeba answer questions on runs it didn't launch? (I think yes. Otherwise you'd have to launch everything through Amoeba, and you won't.)
3. Is scenario B the coordination you meant, or is it something else, such as ordering work across members or agents talking to each other?
4. Which notification channel?
5. Is anything missing from A to C that you'd actually want this week?

### PM answers, 20261106

1. Yes, right for now. Human interaction will probably go through an agent.
2. Yes, answer questions on runs Amoeba didn't launch.
3. Mostly yes. The usual dependency is on a **release** of another member (Squadron / Context Forge / ai-project-guide). `trading-*` is probably the same, so there is one program type, not two.
4. Notify **agents** (Claude, Codex, ...). They already handle mobile push, macOS and so on. Amoeba does not build notification mechanics.
5. Nothing added. With the split below, the PM considers this note complete. Expect substantial updates downstream, possibly from the concept down.

### Where Amoeba sits (from the PM's agent note, 20261106)

- **Squadron** runs work inside one repo. A pipeline is a workflow graph ("do A, then B, loop on review"). It is the LangGraph-like piece: stateful, checkpointed, resumable.
- **Amoeba** knows the program. Its graph is a dependency graph between long-lived repos ("trading-ui can't ship until trading-api releases X"). Nobody executes that graph; pipelines and agents consult it. Amoeba also answers first-level questions and keeps the record of what was decided. It is closer to a package manager's dependency view than to an agent graph.
- **The chat agent** (the PM's separate app) is the front door for humans: the coordinated agent that knows things. It uses Amoeba as a tool over MCP, as Claude and Codex sessions and Squadron pipelines do.
- **Agent-to-agent talk** is not Amoeba. It belongs with chat, the agent dashboard or similar, later.

The trap to avoid: if Amoeba starts *executing* the dependency graph (launching member pipelines in order), it becomes a workflow engine on top of a workflow engine. That is the "complexity of both" problem again.
