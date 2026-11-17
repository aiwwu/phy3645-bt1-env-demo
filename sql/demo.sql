-- Chạy bằng psql. Schema riêng để chạy lại và giữ các bảng khác nguyên vẹn.
BEGIN;
CREATE SCHEMA IF NOT EXISTS lab_courses;
SET LOCAL search_path TO lab_courses, pg_catalog;

CREATE TABLE IF NOT EXISTS students (
    student_id integer PRIMARY KEY,
    full_name text NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    course_id integer PRIMARY KEY,
    title text NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    student_id integer REFERENCES students (student_id),
    course_id integer REFERENCES courses (course_id),
    score numeric(4, 2) NOT NULL CHECK (score BETWEEN 0 AND 10),
    PRIMARY KEY (student_id, course_id)
);

INSERT INTO students VALUES (1, 'An'), (2, 'Bình'), (3, 'Chi')
ON CONFLICT (student_id) DO NOTHING;

INSERT INTO courses VALUES (1, 'Python'), (2, 'Cơ sở dữ liệu'), (3, 'Mạng máy tính')
ON CONFLICT (course_id) DO NOTHING;

INSERT INTO enrollments VALUES (1, 1, 8.50), (2, 1, 7.50), (1, 2, 9.00), (3, 2, 8.00)
ON CONFLICT (student_id, course_id) DO NOTHING;

-- SELECT + JOIN + WHERE: các lượt đăng ký có điểm từ 8 trở lên.
SELECT s.full_name, c.title, e.score
FROM enrollments AS e
JOIN students AS s USING (student_id)
JOIN courses AS c USING (course_id)
WHERE e.score >= 8
ORDER BY e.score DESC, s.student_id;

-- LEFT JOIN giữ cả môn chưa có lượt đăng ký.
SELECT c.title, COUNT(e.student_id) AS enrollments, ROUND(AVG(e.score), 2) AS average_score
FROM courses AS c
LEFT JOIN enrollments AS e USING (course_id)
GROUP BY c.course_id, c.title
ORDER BY c.course_id;

-- Thử UPDATE và DELETE, rồi phục hồi dữ liệu mẫu.
SAVEPOINT before_edit;
UPDATE enrollments SET score = 8.00
WHERE student_id = 2 AND course_id = 1
RETURNING student_id, course_id, score;
DELETE FROM enrollments
WHERE student_id = 2 AND course_id = 1
RETURNING student_id, course_id, score;
ROLLBACK TO SAVEPOINT before_edit;
COMMIT;
