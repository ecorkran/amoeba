---
docType: reference
layer: project
project: amoeba
audience: [human, ai]
description: The answer-first hooks: the PM sees a reply before any tool runs, then the agent goes on working.
dateCreated: 20261121
dateUpdated: 20261121
---

# Answer first

When the PM sends a message to a Claude Code session, the first thing he sees back is a
reply. The agent cannot run a tool until it has replied and its turn has ended, because
a reply written in the middle of a turn is not shown to him until the turn ends. Once he
has the reply, the agent is put straight back to work.

A rule in `CLAUDE.md` asks for this. These hooks enforce it: a refused tool call cannot
be talked around.

## What happens

1. The PM sends a message: a prompt that starts a turn, or a message sent while the
   agent is working.
2. Any tool call the agent makes is refused, with the reason: reply in text, then end
   the turn.
3. The agent writes its reply and ends its turn. The PM sees it.
4. The stop hook records that this message has been answered and keeps the turn going:
   "the PM has your reply; do the work if any is left". Tools run again.
5. If nothing was left to do, the agent ends its turn again and it ends.

Each PM message is released once, so a turn is kept going at most once per message.

Not PM messages, so they change nothing: tool results, hook feedback, task
notifications, messages from other sessions, and slash commands (a command's own
instructions say what its output must be). Tool calls made inside a subagent are never
refused; a subagent works for the agent and cannot reply to the PM.

## Install

```bash
amoeba answer-first install      # from a checkout: uv run amoeba answer-first install
amoeba answer-first uninstall
```

`install` adds the hook under `PreToolUse` and `Stop` in `~/.claude/settings.json` (or
`$CLAUDE_CONFIG_DIR/settings.json`), beside the hooks already there, and prints what it
wrote. It is safe to repeat. `uninstall` removes both entries and nothing else. Sessions
already open pick either change up on their next hook run.

The entries run the `amoeba-answer-first` executable of the Amoeba that ran the command,
by its full path. After moving or reinstalling Amoeba somewhere else, run `install`
again.

### By hand

The command writes the block below. **Install both or neither.** With only `PreToolUse`,
nothing ever releases a message and no tool runs again in any session.

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "*", "hooks": [{ "type": "command", "command": "amoeba-answer-first", "timeout": 10 }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "amoeba-answer-first", "timeout": 10 }] }
    ]
  }
}
```

`amoeba-answer-first` is installed with Amoeba (`uv tool install amoeba-ai`). From a
checkout, use `uv run --quiet --project <checkout> amoeba-answer-first`. Keep any hooks
already listed under those events; add these beside them.

To turn it off, remove both entries. Sessions already open pick the change up on their
next hook run.

## With the stand-in

The stand-in (`amoeba stand-in`, also a `Stop` hook) makes one decision per stop and does
not judge a turn it has already kept going. A turn that answer-first kept going is not
counted as that: when the work that follows ends with something handed to the PM, the
stand-in still judges it.

## State

One small file per session, `<state home>/answer-first/<session id>`, holding the id of
the last PM message released. The state home is `~/.local/state/amoeba`, or
`$AMOEBA_HOME`. A file untouched for 30 days is deleted the next time any release is
written. Deleting a file by hand only means that session's current PM message must be
answered again.

## When it goes wrong

The hook never blocks work on its own fault. Unreadable input, a missing transcript or a
bad `AMOEBA_HOME` is one line on stderr starting `amoeba-answer-first:` and exit 1, which
Claude Code shows without refusing anything.

The hook reads the session transcript, a format Claude Code does not publish. It looks
for entries marked as coming from a human (`origin.kind` is `human`). If a Claude Code
release changes that, the hook finds no PM message and does nothing: tools run as if it
were not installed. `src/amoeba/operations/answer_first.py` lists the shapes it reads.

Claude Code writes the transcript slightly behind the conversation. So a tool call made
in the instant after the PM sends a message can run before the hook sees the message,
and the hook decides whether a turn ended with a reply from the stop hook's own
`last_assistant_message` field, not from the transcript.

## Exit codes

| Event | Exit | Meaning |
|---|---|---|
| `PreToolUse` | 0 | The tool runs |
| `PreToolUse` | 2 | The tool is refused; stderr tells the agent to reply and end its turn |
| `Stop` | 0, no output | The turn ends |
| `Stop` | 0, a `block` decision on stdout | The PM has the reply; the agent keeps working |
| either | 1 | The hook failed; nothing is refused |
