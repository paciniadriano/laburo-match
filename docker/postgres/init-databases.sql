-- Runs once, the first time the data volume is empty (docker-entrypoint-initdb.d).
-- The `laburo` database is created by POSTGRES_DB; tests get their own so the real
-- profile in `laburo` is never touched.
CREATE DATABASE laburo_test OWNER laburo;
