-- Migration 010: a node's link to Context Forge by index (slice 123, D1).
--
-- The column name here must match COL_NODE_CF_INDEX in sql.py, the single
-- definition site. Nothing to backfill: existing rows read as "not linked".

ALTER TABLE nodes ADD COLUMN cf_index INTEGER;

-- One linked node per (project, kind, CF project, index). The kind is part of
-- the key because an initiative and its first slice share an index; the CF
-- project because one Amoeba project may link several. Null indexes (step
-- nodes, unlinked nodes) never collide.
CREATE UNIQUE INDEX idx_nodes_cf_link
    ON nodes (project_id, kind, cf_project, cf_index) WHERE cf_index IS NOT NULL;
