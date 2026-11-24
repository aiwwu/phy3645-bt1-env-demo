# Báo cáo bài 2 — Nạp dữ liệu nhiều triệu dòng vào PostgreSQL

## Dữ liệu thực nghiệm

Dữ liệu công khai NYC TLC Yellow Taxi, tháng 01 và 02 năm 2024. Mỗi file nguồn là Parquet và được chuyển sang CSV để dùng chung cho hai cách nạp. Giữ toàn bộ bản ghi, chọn 7 trường nguồn và thêm trip_id theo vị trí dòng trong file. Mỗi file tương ứng một bảng. NULL được xuất thành trường CSV rỗng. Điểm đón/trả giữ nguyên dưới dạng mã vùng.

| File CSV | Số bản ghi | Dung lượng CSV (MiB) |
| --- | ---: | ---: |
| yellow_202401.csv | 2,964,624 | 188.75 |
| yellow_202402.csv | 3,007,526 | 191.52 |

Tổng cộng 5,972,150 bản ghi. Mỗi file đều có trên 1 triệu dòng dữ liệu, chưa tính header. SHA-256 của cả Parquet và CSV có trong benchmark.json.

## Môi trường và cách đo

- Thời điểm UTC 2026-11-24T20:47:40.435145+00:00.
- Máy chạy Linux-7.0.0-1014-aws-x86_64-with-glibc2.39, 4 CPU logic.
- Python 3.12.3, psycopg 3.3.9.
- Máy chủ PostgreSQL 16.16 (Ubuntu 16.16-1.pgdg24.04+1) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit.
- Thiết lập PostgreSQL `{"fsync": "on", "full_page_writes": "on", "shared_buffers": "16384", "synchronous_commit": "on"}`.

Cách A dùng Python đọc CSV bằng luồng và INSERT nhiều VALUES, mỗi batch tối đa 5,000 dòng. Giá trị được truyền qua placeholder của psycopg. Cách B dùng psql \copy từ CSV phía client. Benchmark gọi đúng lệnh psql cũng được cung cấp để chạy tay.

Mỗi bảng dùng một transaction cho toàn bộ file và có cùng khóa chính BIGINT. TRUNCATE được COMMIT trước khi bấm giờ. Thời gian đo gồm đọc CSV, truyền dữ liệu, ghi bảng, cập nhật khóa chính và COMMIT. Với psql, thời gian còn gồm khởi động client và kết nối. Tải mạng, chuyển Parquet, TRUNCATE và kiểm tra kết quả nằm ngoài khoảng đo. Giữ fsync, synchronous_commit và full_page_writes theo cấu hình ghi phía trên.

Chạy 3 lượt trên toàn bộ dữ liệu, đổi thứ tự INSERT/COPY ở lượt chẵn. Báo cáo lấy trung vị và ghi min–max. Các lượt có thể dùng cache của hệ điều hành. Kết quả phản ánh máy GitHub Actions tại lần chạy này, có thể thay đổi theo CPU, ổ đĩa, tải hệ thống và khoảng cách mạng tới database.

## Kết quả thực đo

| File | Cách | Trung vị (s) | Min–max (s) | Dòng/giây |
| --- | --- | ---: | ---: | ---: |
| yellow_202401.csv | insert | 46.642 | 46.489–47.189 | 63,561 |
| yellow_202401.csv | copy | 4.599 | 4.176–5.526 | 644,666 |
| yellow_202402.csv | insert | 46.782 | 46.734–47.627 | 64,288 |
| yellow_202402.csv | copy | 5.340 | 4.221–5.686 | 563,256 |

## Nhận xét và so sánh

- yellow_202401.csv có tỉ số thời gian INSERT/COPY là 10.14. Giá trị lớn hơn 1 cho thấy COPY tốn ít thời gian hơn trong phép đo này.
- yellow_202402.csv có tỉ số thời gian INSERT/COPY là 8.76. Giá trị lớn hơn 1 cho thấy COPY tốn ít thời gian hơn trong phép đo này.

| Tiêu chí | Python INSERT theo lô | psql \copy chạy tay |
| --- | --- | --- |
| Tốc độ | Có chi phí tạo câu SQL, bind tham số và chạy nhiều lệnh | Truyền luồng qua giao thức COPY, giảm chi phí từng câu lệnh |
| Xử lý dữ liệu | Dễ kiểm tra, biến đổi từng dòng trước khi nạp | CSV cần khớp cột và kiểu dữ liệu bảng đích |
| Bộ nhớ client | Giới hạn theo kích thước batch | Truyền luồng dữ liệu |
| Tự động hóa | Thuận tiện cho pipeline Python | Chạy trực tiếp trong psql hoặc script SQL |
| Lỗi | Exception làm rollback cả file trong thiết kế này | ON_ERROR_STOP và transaction làm rollback cả file |
| Chạy lại | TRUNCATE bảng thực hành trước khi nạp | Cần TRUNCATE bảng thực hành trước khi nạp |

COPY phù hợp với lần nạp lớn từ file đã chuẩn bị. INSERT theo lô hữu ích khi cần logic Python hoặc điều kiện theo bản ghi. Nếu nạp vào bảng nghiệp vụ đã có dữ liệu, có thể COPY vào staging rồi dùng INSERT ... ON CONFLICT để hợp nhất theo khóa.

## Kiểm chứng và giới hạn

Mọi lượt đều kiểm tra COUNT, MIN/MAX của trip_id, tổng trip_id, tổng fare_amount và tổng hash 64-bit trên toàn bộ 8 trường. Các fingerprint khớp giữa hai phương pháp và giữa các lần chạy. Hash có khả năng va chạm, vì vậy đây là kiểm tra toàn vẹn thực dụng. Tệp JSON lưu fingerprint để kiểm tra lại. Khóa chính ngăn trip_id trùng trong từng bảng.

Các giá trị nguồn âm hoặc timestamp bất thường được giữ lại. fare_amount lưu NUMERIC(18,2) và PostgreSQL làm tròn đến 2 chữ số thập phân. trip_distance dùng DOUBLE PRECISION. Cùng kiểu dữ liệu và CSV được dùng cho cả hai phương pháp.

Thiết kế một bảng mỗi file phù hợp yêu cầu bài tập. Trong hệ thống truy vấn lâu dài, có thể dùng một bảng trips phân vùng theo tháng và bảng tham chiếu vùng taxi. trip_id ở đây chỉ có ý nghĩa trong từng file, nên phải kèm tháng khi gộp dữ liệu.

## Dataset bổ sung trên 10 triệu dòng

NYC TLC High Volume For-Hire Vehicle, January 2024 có **19,663,930 bản ghi**, dung lượng Parquet 450.86 MiB. Số lượng được đọc trực tiếp từ metadata Parquet bằng HTTP Range. Nguồn và cách kiểm tra có trong results/large_dataset.json. Dataset này được xác minh quy mô. Phép benchmark trong báo cáo dùng hai file Yellow Taxi phía trên.

Có thể tải và chuyển CSV bằng `python prepare.py --kind fhvhv --months 2024-01 --data-dir data-large`, sau đó chạy `python benchmark.py --data-dir data-large --results-dir results-large`. Trường fare_amount của FHV là base_passenger_fare. Cần điều chỉnh dung lượng lưu trữ cho dataset lớn.

## Tệp kết quả và nguồn

- [Số đo từng lượt và môi trường](results/benchmark.json)
- [Bảng số đo CSV](results/benchmark.csv)
- [Metadata dataset bổ sung](results/large_dataset.json)
- [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [PostgreSQL psql và copy](https://www.postgresql.org/docs/current/app-psql.html)
- [Psycopg truyền tham số](https://www.psycopg.org/psycopg3/docs/basic/params.html)
