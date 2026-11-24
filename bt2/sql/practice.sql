-- Bài ôn SQL tự chứa. Các thao tác nằm trong transaction và được ROLLBACK.
\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE bt2_demo (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    amount NUMERIC(12,2) CHECK (amount >= 0)
);
-- DDL
ALTER TABLE bt2_demo ADD COLUMN note TEXT;
-- CREATE trong CRUD dùng INSERT. CREATE TABLE thuộc DDL.
INSERT INTO bt2_demo VALUES (1, 'Chuyến A', 12.50, NULL), (2, 'Chuyến B', 20, NULL);
-- READ
SELECT * FROM bt2_demo WHERE amount >= 15 ORDER BY amount DESC;
-- UPDATE
UPDATE bt2_demo SET amount = 22 WHERE id = 2 RETURNING *;
-- DELETE
DELETE FROM bt2_demo WHERE id = 1 RETURNING *;
-- Truy vấn tổng hợp trên các bảng dữ liệu lớn.
SELECT '2024-01' AS source_month, COUNT(*) AS trips, SUM(fare_amount) AS fares
FROM bt2_copy.yellow_202401
UNION ALL
SELECT '2024-02', COUNT(*), SUM(fare_amount)
FROM bt2_copy.yellow_202402;
-- DDL
TRUNCATE bt2_demo;
DROP TABLE bt2_demo;
ROLLBACK;
