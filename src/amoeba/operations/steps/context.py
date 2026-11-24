"""What a step function is given besides its request (262 D3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from amoeba.config.user_config import UserConfig
from amoeba.store.store import Transaction


@dataclass(frozen=True)
class StepContext:
    """The open transaction, the clock's reading and, for a step whose table row says
    it needs one, the config. The acting machine is the transaction's own
    (``transaction.acting``), as for every store insert."""

    transaction: Transaction
    now: datetime
    config: UserConfig | None

    def require_config(self) -> UserConfig:
        """The config a step that declared ``needs_config`` was given.

        Raises:
            AssertionError: The step's table row says it needs none (a bug).
        """
        if self.config is None:
            raise AssertionError("this step's STEP_MODELS row says it needs no config")
        return self.config
