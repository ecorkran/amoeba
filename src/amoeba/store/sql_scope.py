"""SQL for the call scope's savepoints (slice 260, D8).

SQLite releases or rolls back to the most recent savepoint of a name, so nesting
needs one fixed name and no SQL is built from a runtime value.
"""

from __future__ import annotations

from typing import Final

SAVEPOINT_NAME: Final = "amoeba_call_scope"
SAVEPOINT: Final = f"SAVEPOINT {SAVEPOINT_NAME}"
RELEASE_SAVEPOINT: Final = f"RELEASE {SAVEPOINT_NAME}"
ROLLBACK_TO_SAVEPOINT: Final = f"ROLLBACK TO {SAVEPOINT_NAME}"
