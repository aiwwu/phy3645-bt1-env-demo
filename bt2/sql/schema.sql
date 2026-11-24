-- Chạy trong database thực hành riêng.
CREATE SCHEMA IF NOT EXISTS bt2_insert;
CREATE SCHEMA IF NOT EXISTS bt2_copy;
-- Mỗi file tạo một bảng với cấu trúc sau. benchmark.py tạo tự động.
-- trip_id BIGINT PRIMARY KEY
-- provider_id TEXT
-- pickup_at TIMESTAMP
-- dropoff_at TIMESTAMP
-- pickup_location_id INTEGER
-- dropoff_location_id INTEGER
-- trip_distance DOUBLE PRECISION
-- fare_amount NUMERIC(18, 2)
