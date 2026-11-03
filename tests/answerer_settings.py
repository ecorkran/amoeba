"""One builder for ``AnswererSettings`` so tests state only what they care about."""

from __future__ import annotations

from amoeba.runner.project_config import AnswererSettings

ANSWER_MODEL = "answer-alias"
CHECK_MODEL = "check-alias"
MAX_CONCURRENT_RUNS = 2
MAX_COST_USD = 0.5

#: The four slice-144 keys as an operator writes them in ``projects.yaml``.
ANSWERING_KEYS_YAML = f"""\
answer_model: {ANSWER_MODEL}
check_model: {CHECK_MODEL}
max_concurrent_runs: {MAX_CONCURRENT_RUNS}
max_cost_usd: {MAX_COST_USD}
"""


def answerer_settings(
    *,
    answer_limit: int = 3,
    reserved_terms: tuple[str, ...] = (),
    rules_paths: tuple[str, ...] = (),
    passages_max_chars: int = 1000,
    answer_model: str = ANSWER_MODEL,
    check_model: str = CHECK_MODEL,
    max_concurrent_runs: int = MAX_CONCURRENT_RUNS,
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
        max_concurrent_runs=max_concurrent_runs,
        max_cost_usd=max_cost_usd,
    )
