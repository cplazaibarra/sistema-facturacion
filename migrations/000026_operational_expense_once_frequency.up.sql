ALTER TABLE operational_expenses DROP CONSTRAINT IF EXISTS operational_expenses_frequency_check;
ALTER TABLE operational_expenses ADD CONSTRAINT operational_expenses_frequency_check
    CHECK (frequency IN ('Una vez', 'Diario', 'Semanal', 'Quincenal', 'Mensual', 'Bimestral', 'Trimestral', 'Semestral', 'Anual'));
