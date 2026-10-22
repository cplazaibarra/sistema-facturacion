DO $$ BEGIN IF EXISTS(SELECT 1 FROM purchase_payment_items) THEN RAISE EXCEPTION 'Downgrade refused: posted payments must be preserved'; END IF; END $$;
DROP VIEW IF EXISTS purchase_payment_events;
DROP TABLE IF EXISTS purchase_payment_items;
