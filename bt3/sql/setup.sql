-- Chạy sau khi nạp dữ liệu bài 2 bằng bt2/sql/manual.sql.
-- Hai biến thể trong mỗi cặp dùng chung index và thống kê này.
CREATE SCHEMA IF NOT EXISTS bt3;
CREATE OR REPLACE VIEW bt3.trips AS
SELECT * FROM bt2_copy.yellow_202401
UNION ALL
SELECT * FROM bt2_copy.yellow_202402;

CREATE INDEX IF NOT EXISTS bt3_pickup_at_202401_idx
ON bt2_copy.yellow_202401 (pickup_at);
CREATE INDEX IF NOT EXISTS bt3_pickup_at_202402_idx
ON bt2_copy.yellow_202402 (pickup_at);

ANALYZE bt2_copy.yellow_202401;
ANALYZE bt2_copy.yellow_202402;
