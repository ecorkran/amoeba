-- Where a member's rules come from (slice 229, D7, D11; 222 D3: ADD COLUMN only).
--
-- 'named' means the member's own rules_paths entries (an empty list is a valid
-- named choice: no rules); 'config_default' means the config's default_rules_paths,
-- read at answering time. Existing members keep the rules they had, so they are
-- 'named'. The CHECK list is pinned to the RulesFrom enum by
-- tests/store/test_vocabulary_pinning.py.

ALTER TABLE members ADD COLUMN rules_from TEXT NOT NULL DEFAULT 'named'
    CHECK (rules_from IN ('named', 'config_default'));
