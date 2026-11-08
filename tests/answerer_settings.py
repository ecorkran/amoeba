"""One builder for ``AnswererSettings`` so tests state only what they care about."""

from __future__ import annotations

from amoeba.answering.settings import AnswererSettings

ANSWER_MODEL = "answer-alias"
CHECK_MODEL = "check-alias"
MAX_COST_USD = 0.5


def answerer_settings(
    *,
    answer_limit: int = 3,
    reserved_terms: tuple[str, ...] = (),
    rules_paths: tuple[str, ...] = (),
    passages_max_chars: int = 1000,
    answer_model: str = ANSWER_MODEL,
    check_model: str = CHECK_MODEL,
    max_cost_usd: float = MAX_COST_USD,
) -> AnswererSettings:
    """Valid settings; each keyword overrides one key."""
    return AnswererSettings(
        answer_limit=answer_limit,
        reserved_terms=reserved_terms,
        rules_paths=rules_paths,
        passages_max_chars=passages_max_chars,
        answer_model=answer_model,
        check_model=check_model,
        max_cost_usd=max_cost_usd,
    )
