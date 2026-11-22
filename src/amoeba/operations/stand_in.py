"""The stand-in at the end of an agent's turn: settle what it hands the PM.

A Claude Code ``Stop`` hook gives this the agent's closing message. When the message
hands something to the PM (a question, a choice, a "want me to"), the stand-in asks a
model, with the PM's own last requests, his rules, the session's memory and his
standing answers in front of it, whether those settle it. If they do, the hook sends
the agent back to work with the decision instead of letting the turn end. If they do
not, the turn ends and the PM sees the question as before.

The stand-in settles what stands between the agent and work the PM asked for. It never
starts work he did not ask for: a summary's "next step" is a record, not a request.

This module holds the pure parts: spotting a hand-off, building the prompt and
reading the model's verdict. The process boundary is ``cli.stand_in_command``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, cast

#: Set in the environment of the model call, so the child session's own Stop hook
#: does nothing instead of judging the judge.
CHILD_ENV_VAR: Final = "AMOEBA_STAND_IN_CHILD"

#: Phrases that hand something to the PM. Matched without case; a closing message
#: with none of them, and no question mark, ends the turn with no model call.
HANDOFF_PATTERN: Final = re.compile(
    r"\?|\byour call\b|\bwant me to\b|\bshould i\b|\bshall i\b|\blet me know\b"
    r"|\bsay the word\b|\bif you want\b|\bwould you like\b|\bdo you want\b"
    r"|\bpm decision\b|\byour decision\b|\bdecide\b|\bconfirm\b|\bapprove\b"
    r"|\bwhich (?:one|option|way)\b|\boption [a-c1-3]\b|\bopen (?:item|question)s?\b"
    r"|\bawaiting\b|\bwaiting (?:on|for) you\b|\bbefore i (?:proceed|continue)\b"
    r"|\bi need\b|\bneed (?:you|your)\b|\bup to you\b|\byes or no\b|\bgo ahead\b",
    re.IGNORECASE,
)

#: The longest closing message, rules text and memory text put in the prompt.
MESSAGE_MAX_CHARS: Final = 12_000
RULES_MAX_CHARS: Final = 40_000
MEMORY_MAX_CHARS: Final = 30_000
STANDING_MAX_CHARS: Final = 20_000
#: The bound on each one of the PM's messages, so a long one never cuts the last.
REQUEST_MAX_CHARS: Final = 4_000
#: How many of the PM's latest messages and slash commands the model is shown.
PM_REQUESTS_SHOWN: Final = 3

#: The text that starts every reason the hook gives the agent.
REASON_PREFIX: Final = "Amoeba, standing in for the PM: "


class Verdict(StrEnum):
    SETTLED = "settled"
    FOR_PM = "for_pm"


@dataclass(frozen=True)
class Judgement:
    verdict: Verdict
    #: For ``settled``: what the agent is told to do. For ``for_pm``: why it is his.
    text: str


class VerdictError(ValueError):
    """The model's reply held no verdict this module can read."""


def hands_off(message: str) -> bool:
    """Whether a closing message hands anything to the PM."""
    return HANDOFF_PATTERN.search(message) is not None


def _cut(text: str, bound: int) -> str:
    if len(text) <= bound:
        return text
    return text[:bound] + "\n[... cut for length ...]"


INSTRUCTIONS: Final = """\
You stand in for the PM, the lead engineer who runs many AI coding agents. An agent \
has just ended its turn with the message below. Decide whether it hands the PM \
something that stands between the agent and work he asked for, and that his rules, \
memory and standing answers already settle, or that any competent senior engineer on \
his team would simply decide.

What he asked for is in his own last messages, given below. The last one governs; the \
earlier ones only say what a short last one ("yes", "go on") refers to. You never \
start work he did not ask for. It is his ("for_pm"), and the turn ends, whenever:
- His last message asks for no work: a question, a remark, a status request, a \
summary or context restore, or an instruction to wait, hold or take no action. The \
agent's reply to it is the whole job. A restore asks only for the context to be \
loaded, and the session then waits for him.
- The agent offers, lists or proposes work he has not asked for: a "next step", \
"remaining work", "I could also", "if you want it", "not started". A summary or \
status report records state. Its next-step lines are never a request from him and \
never a decision of his, whatever his rules say about not asking him questions.
- An instruction to wait or take no action is in force, from him or from the command \
he ran. Nothing in his rules, memory or standing answers overrides it.
- The work he asked for is finished and the message only reports it.

Inside work he did ask for, his standing instruction applies: when an agent reaches a \
"PM decision", pretend to be the PM and make the decision. Questions reaching him \
about work he already asked for are the failure measure: zero is the goal. Routine \
choices, confirmations of routine work, "want me to continue" with the work he asked \
for, option lists with an obvious recommendation, bookkeeping, and rare cases that \
already end in a named command are all yours to settle.

Asking him whether it may ask, tell or message another agent or session, about work \
he asked for, is always yours to settle, and the decision is: message that session \
directly, now. Whether that other session needs his sign-off for its own action (a \
release, a push) is that session's question to raise, never this agent's. He is not \
the relay between two sessions, and a question on both ends is two questions too many.

Also his ("for_pm"): an answer that changes product scope, spends real money beyond \
the work already asked for, deletes or overwrites data that cannot be recovered, \
publishes or sends something outside the machine that he has not asked for, or needs \
a fact only he has (a password, a machine name, a preference never stated anywhere \
below).

"settled" sends the agent back to work, so it always names work to do now. When your \
decision is that the agent does nothing, starts nothing or waits, the verdict is \
"for_pm": that is what lets the turn end.

Reply with one JSON object and nothing else:
{"verdict": "settled", "text": "<the decision, as a direct instruction to the agent: \
what to do now, in one to four plain sentences, adding no work beyond what he asked \
for>"}
or
{"verdict": "for_pm", "text": "<one sentence: why this is his>"}
"""


def build_prompt(
    *,
    requests: list[str],
    message: str,
    rules: str,
    memory: str,
    standing: str,
    cwd: str,
) -> str:
    """The one prompt the model is given; each part cut to its bound.

    ``requests`` are the PM's last messages and slash commands, oldest first.
    """
    requests_text = "\n\n".join(
        f"[{number} of {len(requests)}]\n{_cut(request, REQUEST_MAX_CHARS)}"
        for number, request in enumerate(requests, start=1)
    )
    rules_text = _cut(rules, RULES_MAX_CHARS) or "(none found)"
    memory_text = _cut(memory, MEMORY_MAX_CHARS) or "(none found)"
    standing_text = _cut(standing, STANDING_MAX_CHARS) or "(none)"
    message_text = _cut(message, MESSAGE_MAX_CHARS)
    return (
        f"{INSTRUCTIONS}\n"
        f"=== The PM's last messages, oldest first; the last governs ===\n"
        f"{requests_text}\n\n"
        f"=== The PM's rules (CLAUDE.md files) ===\n{rules_text}\n\n"
        f"=== The session's memory ===\n{memory_text}\n\n"
        f"=== The PM's standing answers ===\n{standing_text}\n\n"
        f"=== The working directory ===\n{cwd}\n\n"
        f"=== The agent's closing message ===\n{message_text}\n"
    )


_JSON_OBJECT: Final = re.compile(r"\{.*\}", re.DOTALL)


def read_verdict(reply: str) -> Judgement:
    """The verdict in the model's reply.

    Lenient about what surrounds the object (a code fence, a sentence before it), and
    strict about the object itself.

    Raises:
        VerdictError: No object, an unknown verdict, or no text.
    """
    found = _JSON_OBJECT.search(reply)
    if found is None:
        raise VerdictError(f"no JSON object in the reply: {reply[:200]!r}")
    try:
        document = json.loads(found.group(0))
    except json.JSONDecodeError as error:
        raise VerdictError(f"the reply's object is not JSON: {error}") from error
    if not isinstance(document, dict):
        raise VerdictError("the reply's JSON is not an object")
    fields = cast("dict[str, object]", document)
    verdict_text = fields.get("verdict")
    text = fields.get("text")
    try:
        verdict = Verdict(verdict_text)
    except ValueError as error:
        raise VerdictError(f"unknown verdict {verdict_text!r}") from error
    if not isinstance(text, str) or not text.strip():
        raise VerdictError("the verdict has no text")
    return Judgement(verdict=verdict, text=text.strip())
