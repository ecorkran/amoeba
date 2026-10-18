"""``amoeba serve``: the store, the inbox, and the change feed over HTTP.

A second process, separate from the resident one. It adds no state and no
write path: reads open stores read-only, the only write is ``inbox.submit()``,
and the feed is ``follow()`` served as Server-Sent Events. See
``docs/network-contract.md``.

This package's ``__init__`` imports nothing, so importing a submodule never
loads uvicorn unless that submodule does.
"""
