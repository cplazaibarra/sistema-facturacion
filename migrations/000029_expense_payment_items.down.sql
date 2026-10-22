DO $$ BEGIN IF EXISTS(SELECT 1 FROM expense_payment_items) THEN RAISE EXCEPTION 'Downgrade refused: posted payments must be preserved'; END IF; END $$;
DROP VIEW IF EXISTS expense_payment_events;
DROP TABLE IF EXISTS expense_payment_items;
