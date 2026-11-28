# Bài 3 — Tối ưu WHERE, GROUP BY và HAVING

Tiếp nối [bài 2](../bt2/README.md), dùng đủ 5.972.150 bản ghi taxi hai tháng 01–02/2024. Ba cặp SQL cho cùng kết quả và mỗi cặp chỉ thay đổi đúng một mệnh đề.

[Báo cáo, SQL và kết quả thực đo](REPORT.md) · [Số liệu JSON](results/benchmark.json) · [42 lượt đo CSV](results/timings.csv)

| Cặp | Bản trước | Bản sau |
| --- | --- | --- |
| WHERE | Ép pickup_at sang DATE | Khoảng timestamp nửa kín, có thể dùng B-tree cột gốc |
| GROUP BY | Hai mã vùng cộng biểu thức nối chuỗi phụ thuộc hai mã | Hai mã vùng |
| HAVING | COUNT(DISTINCT provider_id) > 1 | MIN(provider_id) <> MAX(provider_id) |

## Chuẩn bị dữ liệu

Cần Python 3.11+, PostgreSQL 16+ và psql trong PATH. Các lệnh dưới đây chạy từ thư mục gốc repo trên Bash. Database thực hành có tên bt2_lab như bài trước. Nếu đã nạp hai bảng bt2_copy của bài 2, bắt đầu từ bước tạo index.

~~~bash
cd bt2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python prepare.py
psql -X -d bt2_lab -v ON_ERROR_STOP=1 -f sql/manual.sql
cd ..
~~~

Tạo view, index và cập nhật thống kê dùng chung. Bước này thêm hai index vào các bảng bài 2.

~~~bash
psql -X -d bt2_lab -v ON_ERROR_STOP=1 -f bt3/sql/setup.sql
~~~

## Kiểm chứng và benchmark

~~~bash
cd bt3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql:///bt2_lab"
python benchmark.py --repeats 7
python make_report.py
~~~

Nếu dùng máy chủ khác, đặt DATABASE_URL theo kết nối PostgreSQL của bạn. Trên PowerShell, kích hoạt môi trường bằng .venv/Scripts/Activate.ps1 và đặt DATABASE_URL bằng cú pháp biến môi trường PowerShell.

Script kiểm tra các file chỉ khác mệnh đề đích, kiểm chứng trên trường hợp biên, đối chiếu output đầy đủ bằng EXCEPT ALL hai chiều, warm-up rồi đo mỗi truy vấn 7 lần. Mỗi lượt chẵn đổi thứ tự hai biến thể. Thời gian chính là Execution Time phía server. CSV có thêm thời gian client, buffers và lượng I/O tạm của EXPLAIN.

Các file trong sql/ chạy được riêng. Ví dụ trong psql khi đang ở bt3:

~~~sql
\i sql/where_before.sql
\i sql/where_after.sql
~~~

Để xem plan, thêm EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) trước câu SELECT trong file. Phép đo chuẩn dùng thiết lập chung jit = off và work_mem = '64MB' như benchmark.py.

## Đọc kết quả

- REPORT.md có đủ sáu truy vấn, giải thích tương đương và bảng so sánh.
- results/benchmark.json ghi môi trường, số dòng, kiểm chứng output và 42 lượt đo.
- results/timings.csv lưu số đo từng lượt.
- results/plans/ chứa sáu execution plan JSON của các lượt có thời gian trung vị.
- test_benchmark.py kiểm tra các file SQL vẫn chỉ thay đổi đúng mệnh đề đích.

HAVING được viết lại cho điều kiện có ít nhất hai provider khác nhau. Provider_id là TEXT, nên kết luận gắn với kiểu dữ liệu và collation ghi trong báo cáo. Việc bỏ biểu thức dư trong GROUP BY giữ nguyên hai khóa tạo nhóm. Với WHERE, pickup_at là TIMESTAMP không có múi giờ.

Workflow bt3.yml tải lại dữ liệu bài 2, nạp bằng psql, tạo index, kiểm chứng và đo trên GitHub Actions. Workflow commit báo cáo và số liệu thực tế sau khi mọi bước thành công.
