-- Chạy trong bt2 để đường dẫn data/... được giải đúng.
\set ON_ERROR_STOP on
CREATE SCHEMA IF NOT EXISTS bt2_copy;
CREATE TABLE IF NOT EXISTS bt2_copy.yellow_202401 (
trip_id BIGINT PRIMARY KEY,
provider_id TEXT,
pickup_at TIMESTAMP,
dropoff_at TIMESTAMP,
pickup_location_id INTEGER,
dropoff_location_id INTEGER,
trip_distance DOUBLE PRECISION,
fare_amount NUMERIC(18, 2)
);
CREATE TABLE IF NOT EXISTS bt2_copy.yellow_202402 (
trip_id BIGINT PRIMARY KEY,
provider_id TEXT,
pickup_at TIMESTAMP,
dropoff_at TIMESTAMP,
pickup_location_id INTEGER,
dropoff_location_id INTEGER,
trip_distance DOUBLE PRECISION,
fare_amount NUMERIC(18, 2)
);

BEGIN;
TRUNCATE bt2_copy.yellow_202401, bt2_copy.yellow_202402;
COMMIT;
\timing on
BEGIN;
\copy bt2_copy.yellow_202401 FROM 'data/yellow_202401.csv' WITH (FORMAT csv, HEADER true, NULL '')
COMMIT;
BEGIN;
\copy bt2_copy.yellow_202402 FROM 'data/yellow_202402.csv' WITH (FORMAT csv, HEADER true, NULL '')
COMMIT;
SELECT '2024-01' AS source_month, COUNT(*) FROM bt2_copy.yellow_202401
UNION ALL
SELECT '2024-02', COUNT(*) FROM bt2_copy.yellow_202402;
