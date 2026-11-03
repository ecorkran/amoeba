"""Question text for the live answering-run cases, shaped like Squadron's tails.

Squadron reports the last ``QUESTION_TAIL_CHARS`` characters of the agent's reply,
so a tail can begin mid-sentence. These are written inline: the live tier tests what
the models make of the wording, not where the wording came from.
"""

from __future__ import annotations

#: Asked on the slice whose rules say how long a file and a function may be.
PLAN_QUESTION = (
    "...the file is getting long. Before I split anything: how long may a source "
    "file be, and how long may one function be, in this project?"
)

#: The PM's earlier answer, and the same question in other words.
PM_QUESTION = "Should the log lines carry a timestamp?"
PM_ANSWER = "Yes. Use ISO 8601 in UTC on every line."
#: The same decision, given as a convention for every slice: the case where the
#: answer is meant to carry over to another slice.
PM_ANSWER_FOR_EVERY_SLICE = (
    "Yes, in every slice. Use ISO 8601 in UTC on every log line."
)
REWORDED_QUESTION = (
    "...I'm adding logging now. Do we want a time stamped on each line we write, "
    "and if so in what format?"
)

#: The PM's answer for one slice only, and the same wording asked on another slice.
PORT_QUESTION = "Which port does the dev server listen on?"
PORT_ANSWER = (
    "Port 8080. It is reserved for the web console only; every other slice gets "
    "its own port and must not use 8080."
)
