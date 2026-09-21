"""The Amoeba resident process: host loop, recovery, and the observers.

One long-lived process per supervisor owns the stores read-write, hosts
*tenants* (the inbox apply loop in slice 103, the Runner in initiative 120),
and reconciles every journaled-but-unresolved command on start.

The full contract is documented in ``docs/process-contract.md``, which is
written to be sufficient for building a tenant without reading this
implementation.
"""

from __future__ import annotations
