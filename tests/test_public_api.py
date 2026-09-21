"""Regression test pinning the public export surface of ``amoeba.store``.

Downstream slices design against this surface, so a typo'd, dropped, or
accidentally-added export should fail ``pytest`` here rather than wait for
someone to re-run the manual walkthrough.
"""

from __future__ import annotations

import importlib
import inspect

import amoeba.store as store_package

#: The exported contract, written out rather than derived from ``__all__``:
#: deriving it from the thing under test would make the assertion vacuous.
EXPECTED_EXPORTS = {
    # Vocabularies
    "BLOCKED_KIND_TO_STATUS",
    "BLOCKED_STATUSES",
    "REQUIRED_PARAMETER_KEYS",
    "BlockedKind",
    "CommandKind",
    "JournalOutcome",
    "JournalResolver",
    "NodeKind",
    "NodeStatus",
    # Transfer objects
    "BlockedNode",
    "BlockedState",
    "CFReference",
    "JournalEntry",
    "Node",
    "Resolution",
    "SQReference",
    # The store
    "Store",
    # Exceptions
    "InvalidTransitionError",
    "NodeNotFoundError",
    "StoreBusyError",
    "StoreCorruptError",
    "StoreError",
    "StoreIntegrityError",
    "StorePermissionError",
    "StoreSchemaError",
    "UnknownVocabularyValueError",
}

#: Internal modules that must not become part of the contract.
INTERNAL_MODULES = {
    "sql",
    "sql_journal",
    "mapping",
    "mapping_journal",
    "migrations",
    "paths",
    "_base",
}

#: Store methods a downstream author codes against, per the API contract.
CONTRACT_METHODS = {
    "open",
    "open_read_only",
    "open_temporary",
    "close",
    "create_node",
    "update_node_status",
    "update_cf_reference",
    "update_sq_reference",
    "get_node",
    "nodes_for_project",
    "children_of",
    "block",
    "resolve",
    "blocked_state_for",
    "all_blocked_states",
    "runnable",
    "blocked",
    # The command journal, added by slice 102.
    "journal_issue",
    "journal_resolve",
    "journal_escalate",
    "journal_entry",
    "journal_entries",
    "unresolved_journal_entries",
}


def test_declared_exports_match_the_expected_surface() -> None:
    """``__all__`` is exactly the contract — nothing added, nothing dropped."""
    assert set(store_package.__all__) == EXPECTED_EXPORTS


def test_every_declared_export_is_importable() -> None:
    """Every name in ``__all__`` actually resolves on the package."""
    missing = [
        name for name in store_package.__all__ if not hasattr(store_package, name)
    ]

    assert missing == []


def test_walkthrough_names_import_directly() -> None:
    """The names the LLD's verification walkthrough uses import as written."""
    from amoeba.store import BlockedKind, NodeKind, NodeStatus, Store

    assert Store.__name__ == "Store"
    assert NodeStatus.RUNNABLE.value == "runnable"
    assert NodeKind.SLICE.value == "slice"
    assert BlockedKind.HUMAN.value == "human"


def test_internal_modules_are_not_re_exported() -> None:
    """SQL statements, row mapping, and migration machinery stay internal."""
    exported = set(store_package.__all__)

    assert exported & INTERNAL_MODULES == set()
    for internal in INTERNAL_MODULES:
        # Importable by path for the package's own use, but not part of the
        # exported contract.
        importlib.import_module(f"amoeba.store.{internal}")
        assert internal not in exported


def test_no_sql_statement_is_reachable_from_the_public_surface() -> None:
    """No exported name is an SQL string or a column constant."""
    for name in store_package.__all__:
        exported = getattr(store_package, name)
        if isinstance(exported, str):
            assert "SELECT" not in exported.upper()
            assert "INSERT" not in exported.upper()


def test_every_exported_callable_has_a_docstring() -> None:
    """A downstream author reading the surface finds it documented."""
    undocumented = [
        name
        for name in store_package.__all__
        if callable(getattr(store_package, name))
        and not inspect.getdoc(getattr(store_package, name))
    ]

    assert undocumented == []


def test_contract_methods_exist_and_are_documented() -> None:
    """Every method the contract names is present and carries a docstring."""
    missing = [
        name for name in CONTRACT_METHODS if not hasattr(store_package.Store, name)
    ]
    assert missing == []

    undocumented = [
        name
        for name in CONTRACT_METHODS
        if not inspect.getdoc(getattr(store_package.Store, name))
    ]
    assert undocumented == []
