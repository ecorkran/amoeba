-- The door that carried each answer (slice 226, D11; 222 D3: ADD COLUMN only).
--
-- A PM answer arrives through the command line or the MCP server, and both can
-- answer for the PM, so the row records which. Nullable: answers written before this
-- migration, and the answerer's automatic answers (carried by no door), stay NULL
-- and are read as "no door", never as a guessed one. The CHECK list is pinned to
-- the Door enum by tests/store/test_vocabulary_pinning.py.

ALTER TABLE answers ADD COLUMN via TEXT CHECK (via IN ('cli', 'mcp'));
