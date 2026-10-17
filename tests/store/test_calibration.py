"""The descriptive calibration report (D3), and the constraints that never lapse."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from evidence_harness import PROJECT, provider_failure, seed_node, verdict_input

import amoeba
from amoeba.store import CalibrationRow, ReviewVerdict, Store
from amoeba.store.calibration import CALIBRATION_COLUMNS

#: D3's fields, exactly. A field comparing samples with each other is a defect.
D3_FIELDS = (
    "review_type",
    "model",
    "samples",
    "invocations",
    "pass",
    "concerns",
    "fail",
    "unknown",
    "provider_failures",
    "score_min",
    "score_mean",
    "score_max",
)


def _record(
    store: Store,
    sample_id: str,
    node: str,
    *,
    invocation: str | None,
    review_type: str,
    model: str,
    verdict: ReviewVerdict = ReviewVerdict.PASS,
    score: float | None = None,
) -> None:
    store.record_verdict(
        verdict_input(
            sample_id,
            node,
            judge_invocation_id=invocation,
            review_type=review_type,
            model=model,
            verdict=verdict,
            score=score,
            findings_parsed=True,
        ),
        project_id=PROJECT,
    )


def _seed(store: Store) -> None:
    node = seed_node(store)
    # judge.a / model-b: two invocations, mixed verdicts and scores.
    _record(
        store,
        "1",
        node,
        invocation="j1",
        review_type="judge.a",
        model="model-b",
        verdict=ReviewVerdict.PASS,
        score=81,
    )
    _record(
        store,
        "2",
        node,
        invocation="j1",
        review_type="judge.a",
        model="model-b",
        verdict=ReviewVerdict.CONCERNS,
        score=62,
    )
    _record(
        store,
        "3",
        node,
        invocation="j2",
        review_type="judge.a",
        model="model-b",
        verdict=ReviewVerdict.FAIL,
    )
    # judge.a / model-a: one scoreless UNKNOWN (not a provider failure).
    _record(
        store,
        "4",
        node,
        invocation="j1",
        review_type="judge.a",
        model="model-a",
        verdict=ReviewVerdict.UNKNOWN,
    )
    # judge.b / model-a
    _record(
        store,
        "5",
        node,
        invocation="j3",
        review_type="judge.b",
        model="model-a",
        verdict=ReviewVerdict.PASS,
        score=70,
    )
    # An ordinary review never appears.
    _record(store, "6", node, invocation=None, review_type="judge.a", model="model-b")


def test_one_row_per_review_type_and_model_in_order(store: Store) -> None:
    _seed(store)
    rows = store.calibration(PROJECT)
    assert [(r.review_type, r.model) for r in rows] == [
        ("judge.a", "model-a"),
        ("judge.a", "model-b"),
        ("judge.b", "model-a"),
    ]


def test_counts_and_score_statistics(store: Store) -> None:
    _seed(store)
    by_group = {(r.review_type, r.model): r for r in store.calibration(PROJECT)}

    busy = by_group[("judge.a", "model-b")]
    assert (busy.samples, busy.invocations) == (3, 2)  # the ordinary review is out
    assert (busy.pass_count, busy.concerns_count, busy.fail_count) == (1, 1, 1)
    assert busy.unknown_count == 0
    assert (busy.score_min, busy.score_mean, busy.score_max) == (62, 71.5, 81)

    scoreless = by_group[("judge.a", "model-a")]
    assert scoreless.unknown_count == 1  # an UNKNOWN sample counts under unknown
    assert scoreless.provider_failures == 0
    assert (scoreless.score_min, scoreless.score_mean, scoreless.score_max) == (
        None,
        None,
        None,
    )


def test_provider_failures_use_the_trust_label(store: Store) -> None:
    node = seed_node(store)
    failed = provider_failure("pf", node)
    store.record_verdict(
        dataclasses.replace(
            failed, judge_invocation_id="j1", model="model-a", review_type="judge.a"
        ),
        project_id=PROJECT,
    )
    [row] = store.calibration(PROJECT)
    assert row.provider_failures == 1
    assert row.unknown_count == 1  # a provider failure is also an UNKNOWN verdict


def test_a_project_with_no_samples_has_no_rows(store: Store) -> None:
    node = seed_node(store)
    _record(store, "1", node, invocation=None, review_type="r", model="m")
    assert store.calibration(PROJECT) == []


def test_calibration_writes_nothing_on_a_read_only_handle(store_file: Path) -> None:
    with Store.open(store_file) as writer:
        _seed(writer)
        tables = _table_counts(writer)
    with Store.open_read_only(store_file) as reader:
        assert len(reader.calibration(PROJECT)) == 3
        assert _table_counts(reader) == tables


def _table_counts(store: Store) -> dict[str, int]:
    connection = store._connection  # pyright: ignore[reportPrivateUsage]
    names = [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    ]
    return {
        name: int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
        for name in names
    }


def test_the_row_has_exactly_the_d3_fields() -> None:
    columns = {field: column for field, column in CALIBRATION_COLUMNS}
    fields = tuple(field.name for field in dataclasses.fields(CalibrationRow))
    assert fields == tuple(columns)
    assert tuple(columns.values()) == D3_FIELDS


def _string_constants_outside_docstrings(tree: ast.AST) -> list[str]:
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
            ):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def _names(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.append(node.id)
        elif isinstance(node, ast.Attribute):
            found.append(node.attr)
        elif isinstance(node, ast.arg):
            found.append(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.append(node.name)
        elif isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append(node.module or "")
            found.extend(alias.name for alias in node.names)
    return found


def test_src_never_references_squadrons_metrology_store() -> None:
    root = Path(amoeba.__file__).parent
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        mentions = _names(tree) + _string_constants_outside_docstrings(tree)
        if any("metrology" in text.lower() for text in mentions):
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
