"""What the program tables hold, as frozen values (slice 222, D3).

JSON array columns are decoded into tuples; timestamps are timezone-aware UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from amoeba.answering.values import (
    AnsweredBy,
    AnsweringEvidence,
    DeclineReason,
    PassageRef,
)
from amoeba.store.vocabulary import (
    ClosedReason,
    ConsumedMode,
    DeliveryEvent,
    Door,
    MessageKind,
    QuestionState,
    RequestState,
    ResumeOutcome,
    RulesFrom,
    StandingReach,
    WakeOutcome,
)


@dataclass(frozen=True)
class Program:
    """A named group of members. The two concept columns are both null or both set."""

    program_id: str
    #: Context Forge project id of the member that holds the concept document.
    concept_member: str | None
    #: Repo-relative path of the concept document in that member.
    concept_path: str | None
    registered_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MemberSettings:
    """What a member's answering depends on; the member's own part of the row."""

    #: The member's id: an opaque key, never parsed (261 D1).
    project_id: str
    rules_paths: tuple[str, ...]
    #: Config item keys taken off this member's not-authorized list.
    authorize_allow: tuple[str, ...]
    #: Config item keys put on it.
    authorize_deny: tuple[str, ...]
    #: Whether the rules are ``rules_paths`` or the config's default (229 D7).
    rules_from: RulesFrom


@dataclass(frozen=True)
class Member:
    """A repo in a program."""

    program_id: str
    settings: MemberSettings
    registered_at: datetime
    updated_at: datetime
    #: When ``set_up`` removed the member; ``None`` for an active one.
    removed_at: datetime | None
    #: The member's name (261 D1), never null on a row the store hands out.
    name: str
    #: The reduced remote (261 D3) that says which repo this is; ``None`` for none.
    origin: str | None

    @property
    def project_id(self) -> str:
        return self.settings.project_id


@dataclass(frozen=True)
class DependencyPair:
    """``consumer_id`` depends on ``provider_id``; both are members of one program."""

    program_id: str
    provider_id: str
    consumer_id: str
    consumed: ConsumedMode
    registered_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Release:
    """One row of ``releases``: a member's report for one commit (slice 227, D2)."""

    seq: int
    commit: str
    #: The release tag the report was versioned with; ``None`` until it is.
    version: str | None
    changed: str
    touched: tuple[str, ...]
    reported_at: datetime
    versioned_at: datetime | None


@dataclass(frozen=True)
class QuestionKey:
    """A question's identity: the run and the checkpoint time exactly as Squadron
    printed it (slice 223, D1)."""

    run_id: str
    paused_at: str


@dataclass(frozen=True)
class QuestionRecord:
    """One row of ``questions``."""

    key: QuestionKey
    member_id: str
    question: str
    checkout: str
    state: QuestionState
    answering_run_id: str | None
    waiting_reason: DeclineReason | None
    waiting_detail: str | None
    slice_label: str | None
    source_commit: str | None
    passages: tuple[PassageRef, ...] | None
    evidence: AnsweringEvidence | None
    claimed_at: datetime
    updated_at: datetime
    #: Set with ``state`` ``closed``; kept as history if ``answer`` reopens it.
    closed_reason: ClosedReason | None
    #: The dismissal reason, or the run's outcome when the sweep closed it.
    closed_detail: str | None
    closed_at: datetime | None
    #: The request a held question waits on (242 D2); kept through later states.
    request_id: str | None
    #: When ``start_ended_held`` last started ``handle_pause`` for the held row.
    start_attempted_at: datetime | None


@dataclass(frozen=True)
class AnswerRecord:
    """One row of ``answers``."""

    seq: int
    key: QuestionKey
    answered_by: AnsweredBy
    answer: str
    cited: tuple[str, ...] | None
    recorded_at: datetime
    resume_outcome: ResumeOutcome | None
    resume_detail: str | None
    resume_log: str | None
    resume_at: datetime | None
    #: Set when a PM answer was retracted; the answer stays delivered (228 D6).
    retracted_at: datetime | None
    retract_reason: str | None
    #: Set just before each resume spawn (228 D4).
    resume_started_at: datetime | None
    #: The door that carried a PM answer (226 D11); ``None`` for an answer written
    #: before migration 004 and for the answerer's automatic answers.
    via: Door | None
    #: The attempt that holds the resume claim, or ``None`` when it is free (262 D6).
    resume_claim_id: str | None
    #: Resumes ``claim_work`` has handed out for this answer (262 D10).
    resume_start_count: int


@dataclass(frozen=True)
class PmPrecedent:
    """The newest PM answer to one of a member's questions."""

    key: QuestionKey
    question: str
    slice_label: str | None
    answer_seq: int
    answer: str
    recorded_at: datetime


@dataclass(frozen=True)
class Message:
    """One ``messages`` row: a request (240) or, from 243, a note."""

    message_id: str
    kind: MessageKind
    #: Project id of the sender.
    from_member: str
    #: Project id of the addressee; set for a request.
    to_member: str | None
    to_program: str | None
    #: The request this one serves, as given; the row may have been pruned.
    parent_id: str | None
    depth: int
    subject: str
    body: str
    #: The stored state, ``None`` for a note. Read ``effective_state``, not this.
    state: RequestState | None
    result: str | None
    result_commit: str | None
    result_version: str | None
    reason: str | None
    accepted_at: datetime | None
    created_at: datetime
    state_changed_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True)
class Delivery:
    """One ``deliveries`` row: something a member should learn about a request."""

    seq: int
    member_id: str
    message_id: str
    event: DeliveryEvent
    created_at: datetime


@dataclass(frozen=True)
class MessageRejection:
    """One ``message_rejections`` row: a call that was refused (240 D9)."""

    id: int
    #: The caller's project id.
    member_id: str
    #: An ``OperationName`` value.
    operation: str
    #: The recipient as the caller gave it; ``send`` only.
    to_ref: str | None
    message_id: str | None
    parent_id: str | None
    #: A ``RejectCode`` value.
    code: str
    detail: str
    created_at: datetime


@dataclass(frozen=True)
class Session:
    """One ``sessions`` row: an ``amoeba-mcp`` serving a member (slice 241, D6)."""

    session_id: str
    member_id: str
    #: The client's ``clientInfo.name``, or the placeholder when it was not one.
    client: str
    #: The server process's working directory.
    directory: str
    started_at: datetime
    heartbeat_at: datetime
    #: When the session's agent first answered a channel event; ``None`` until then.
    push_confirmed_at: datetime | None


@dataclass(frozen=True)
class PushRow:
    """A delivery as the channel event names it (slice 241, D4): no message text."""

    seq: int
    event: DeliveryEvent
    kind: MessageKind
    #: The message's member that is not the receiver; for a note, its sender.
    counterparty: str


@dataclass(frozen=True)
class Wake:
    """One ``wakes`` row: a wake of a member's command (244 D3)."""

    wake_id: str
    member_id: str
    #: The checkout the command runs in; ``None`` only for a ``start_failed`` row
    #: Context Forge gave no path for.
    directory: str | None
    #: The member's ``wake_command`` as claimed; a later edit changes nothing.
    command: str
    started_at: datetime
    #: ``started_at`` plus ``wake_timeout_seconds``, fixed at the claim.
    deadline_at: datetime
    #: The log files' path without the ``.stdout.log`` / ``.stderr.log`` suffix.
    log_stem: str | None
    #: The command's pid, also its process group id; ``None`` until it has started.
    command_pid: int | None
    ended_at: datetime | None
    outcome: WakeOutcome | None
    exit_code: int | None
    #: Why, for a start failure or an error; never argv text.
    detail: str | None


@dataclass(frozen=True)
class StandingAnswerRow:
    """One ``standing_answers`` row: a ruling the PM gave ahead of time (230 D1)."""

    standing_id: int
    #: The PM's words, situation and ruling together; never edited.
    text: str
    reach: StandingReach
    #: Set only for reach ``program``.
    program_id: str | None
    #: Set only for reach ``member``: the member's project id.
    member_id: str | None
    given_at: datetime
    withdrawn_at: datetime | None
    withdraw_reason: str | None
