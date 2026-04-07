DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN (
    SELECT
      'ALTER TABLE ' || quote_ident(table_name) || ' ALTER COLUMN ' || quote_ident(column_name) || ' TYPE TIMESTAMPTZ USING ' || quote_ident(column_name) || ' AT TIME ZONE ''UTC''' AS cmd
    FROM information_schema.columns
    WHERE data_type = 'timestamp without time zone'
      AND table_schema = 'public'
  ) LOOP
    EXECUTE r.cmd;
  END LOOP;
END $$;
