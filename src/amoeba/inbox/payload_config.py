"""The one pydantic config every envelope and payload model shares."""

from __future__ import annotations

from typing import Final

from pydantic import ConfigDict

#: Unknown keys drop rather than fail, and validated models are immutable.
MODEL_CONFIG: Final = ConfigDict(extra="ignore", frozen=True)
