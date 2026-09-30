-- Migration 002: deliberately trivial.
--
-- This migration exists to exercise the N -> N+1 runner end to end before any
-- slice needs a real schema change, so slices 102-110 add tables onto a proven
-- mechanism rather than debugging the mechanism and their change at once.
--
-- It adds a free-text note column to nodes. The store does not read or write
-- it; it is storage the later slices may adopt or drop.

ALTER TABLE nodes ADD COLUMN note TEXT;
