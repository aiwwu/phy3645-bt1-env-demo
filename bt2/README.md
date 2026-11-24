# Bài 2 — Nạp dữ liệu nhiều triệu dòng vào PostgreSQL

Bài tập dùng dữ liệu taxi NYC công khai, gồm nhiều file CSV trên 1 triệu dòng mỗi file. Hai cách thực hiện là Python INSERT nhiều VALUES theo batch và nhập lệnh `\copy` trong psql. Mỗi file tương ứng một bảng trong cùng một database.

- [Báo cáo so sánh và kết quả thực đo](REPORT.md)
- [Số liệu từng lượt, số dòng và SHA-256](results/benchmark.json)
- [Bảng số đo CSV](results/benchmark.csv)
- [Dataset bổ sung trên 10 triệu dòng](results/large_dataset.json)
- [Theo dõi lần chạy đầy đủ](https://github.com/aiwwu/phy3645-bt1-env-demo/actions/workflows/bt2.yml)

## Chuẩn bị

Cần Python 3.11+, PostgreSQL và psql. Cài PostgreSQL theo hướng dẫn bài 1 ở README gốc. Dùng database thực hành riêng vì benchmark TRUNCATE các bảng trong schema `bt2_insert` và `bt2_copy`. Cần dự trù khoảng 5 GB đĩa trống cho file nguồn, CSV, hai bộ bảng và WAL, thực tế phụ thuộc cấu hình máy.

Từ thư mục repo:

```bash
cd bt2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Với PostgreSQL trên Linux, tạo role trùng tên đăng nhập và database ở lần đầu. Role này có thể đăng nhập bằng peer qua Unix socket. Nếu role đã tồn tại, bắt đầu từ `createdb`.

```bash
sudo -u postgres createuser --createdb "$USER"
createdb bt2_lab
export DATABASE_URL="postgresql:///bt2_lab"
```

Với một tài khoản PostgreSQL có sẵn, có thể đặt `DATABASE_URL` theo kết nối của tài khoản đó. libpq hỗ trợ đọc mật khẩu từ `.pgpass`. Chỉ dùng role có quyền tạo schema/bảng trong database thực hành.

PowerShell kích hoạt môi trường bằng `& .\.venv\Scripts\Activate.ps1`, đặt DSN bằng `$env:DATABASE_URL = 'postgresql://localhost/bt2_lab?user=postgres'`. Các lệnh Python bên dưới dùng được sau khi kích hoạt. psql cần có trong PATH.

## Tải và chuyển CSV

```bash
python prepare.py
python inspect_large.py
```

`prepare.py` tải hai file Yellow Taxi tháng 01 và 02 năm 2024 từ nguồn NYC TLC. Chương trình chuyển lần lượt 50.000 bản ghi từ Parquet sang CSV để giới hạn bộ nhớ, kiểm tra số bản ghi và tạo `data/manifest.json`. Mỗi file phải có trên 1 triệu bản ghi mới được chấp nhận. Giữ đủ mọi dòng, chọn các trường phục vụ phép đo và thêm ID theo thứ tự nguồn. `data/` được bỏ qua khi commit vì dữ liệu có thể tải lại bằng URL và vượt giới hạn kích thước tệp thông thường của GitHub.

| Cột đích | Trường Yellow Taxi nguồn | Kiểu PostgreSQL |
| --- | --- | --- |
| trip_id | Số thứ tự dòng, bắt đầu từ 1 | BIGINT PRIMARY KEY |
| provider_id | VendorID | TEXT |
| pickup_at | tpep_pickup_datetime | TIMESTAMP |
| dropoff_at | tpep_dropoff_datetime | TIMESTAMP |
| pickup_location_id | PULocationID | INTEGER |
| dropoff_location_id | DOLocationID | INTEGER |
| trip_distance | trip_distance | DOUBLE PRECISION |
| fare_amount | fare_amount | NUMERIC(18,2) |

`inspect_large.py` đọc metadata file FHV tháng 01/2024 bằng HTTP Range để xác minh dataset phụ trên 10 triệu bản ghi. Lệnh chuyển dataset này sang CSV cũng được nêu trong báo cáo.

## Cách A — Python INSERT theo lô

Có thể chạy cả phép so sánh bằng:

```bash
python benchmark.py --repeats 3 --batch-size 5000
python make_report.py
```

Trong `benchmark.py`, hàm `insert_python` đọc CSV từng batch, tạo câu `INSERT INTO ... VALUES (...), (...)` và bind các giá trị qua tham số psycopg. Mỗi file dùng một transaction. Nếu một dòng lỗi, transaction của file đó rollback. Hai tháng nạp vào `bt2_insert.yellow_202401` và `bt2_insert.yellow_202402`.

Benchmark gọi cả Python INSERT và psql COPY, đổi thứ tự giữa các lượt và ghi thời gian cùng fingerprint kiểm chứng. Cả hai phương pháp đều bắt đầu từ bảng rỗng có khóa chính và cùng cấu trúc. Advisory lock ngăn hai benchmark tranh các bảng trong cùng database.

## Cách B — Nhập lệnh thủ công trong psql

Chạy từ thư mục `bt2`, với cùng database như DATABASE_URL:

```bash
psql -X -d "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/manual.sql
```

Hoặc mở `psql -X -d "$DATABASE_URL"`, rồi nhập `\i sql/manual.sql`. Tệp này có DDL, TRUNCATE, hai lệnh `\copy`, transaction và truy vấn đếm dòng. Có thể gõ riêng từng lệnh để quan sát thời gian. Hai tháng nạp vào `bt2_copy.yellow_202401` và `bt2_copy.yellow_202402`.

`\copy` đọc file trên máy đang chạy psql. `COPY FROM '/path'` là lệnh SQL đọc file phía máy chủ, có yêu cầu quyền và đường dẫn khác. Với PostgreSQL từ xa, đường dẫn CSV của `\copy` vẫn thuộc máy client.

## Ôn CRUD, DML, DDL

```bash
psql -X -d "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/practice.sql
```

| Nhóm | Ý nghĩa | Ví dụ |
| --- | --- | --- |
| CRUD | Bốn thao tác trên bản ghi | Create → INSERT, Read → SELECT, Update → UPDATE, Delete → DELETE |
| DML | Thao tác dữ liệu | INSERT, UPDATE, DELETE. SELECT thường được tách riêng thành DQL trong tài liệu giảng dạy |
| DDL | Định nghĩa cấu trúc | CREATE TABLE, ALTER TABLE, DROP TABLE, TRUNCATE |

`DELETE` hỗ trợ WHERE. `TRUNCATE` làm rỗng cả bảng. `DROP TABLE` xóa cấu trúc bảng. PostgreSQL hỗ trợ rollback các thao tác DDL dùng trong tệp thực hành này. `practice.sql` thao tác trên bảng tạm và kết thúc bằng ROLLBACK.

## Tái lập kết quả

Workflow `bt2.yml` chạy toàn bộ dữ liệu trên GitHub Actions, đo ba lượt mỗi cách, kiểm tra SQL rồi commit `REPORT.md` và các tệp kết quả vào repo. Số liệu gồm thời điểm, hệ điều hành, PostgreSQL, Python và cấu hình ghi bền vững. Có thể chạy lại từ tab Actions bằng Run workflow.

Nguồn chính thức:

- [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [PostgreSQL psql](https://www.postgresql.org/docs/current/app-psql.html)
- [Psycopg tham số SQL](https://www.psycopg.org/psycopg3/docs/basic/params.html)
- [Apache Arrow đọc Parquet theo batch](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html)
