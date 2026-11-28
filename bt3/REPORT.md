# Báo cáo bài 3 — Tối ưu WHERE, GROUP BY và HAVING

## Bài toán và dữ liệu

Dùng lại hai file Yellow Taxi của bài 2, nạp vào bt2_copy.yellow_202401 và bt2_copy.yellow_202402. View bt3.trips kết hợp hai bảng bằng UNION ALL, giữ nguyên mọi bản ghi. Mỗi cặp chỉ thay đổi mệnh đề nêu trong tên cặp. SELECT, FROM và các mệnh đề còn lại giống hệt nhau.

| Bảng | Số bản ghi |
| --- | ---: |
| yellow_202401 | 2,964,624 |
| yellow_202402 | 3,007,526 |

Tổng cộng **5,972,150 bản ghi**.

## Môi trường và phương pháp

- Thời điểm UTC 2026-11-28T11:19:20.140053+00:00.
- Máy Linux-7.0.0-1018-aws-x86_64-with-glibc2.39, 4 CPU logic.
- PostgreSQL PostgreSQL 16.16 (Ubuntu 16.16-1.pgdg24.04+1) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit.
- Python 3.12.3, psycopg 3.3.9.
- Cấu hình session {"enable_hashagg": "on", "enable_indexscan": "on", "enable_seqscan": "on", "jit": "off", "max_parallel_workers_per_gather": "2", "shared_buffers": "16384", "work_mem": "65536"}.

Index B-tree trên pickup_at được tạo sẵn ở cả hai bảng nguồn và ANALYZE được chạy trước phép đo. Hai biến thể luôn dùng chung index, thống kê và cấu hình. Chi phí tạo index, tải CSV và nạp dữ liệu được tách khỏi thời gian chạy truy vấn.

Mỗi truy vấn có một lượt warm-up và **7 lượt đo**. Đổi thứ tự trước/sau ở lượt chẵn, dùng cùng snapshot REPEATABLE READ cho kiểm chứng toàn bộ dữ liệu và các lượt đo. Thời gian chính là Execution Time phía PostgreSQL từ EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON). TIMING OFF giảm chi phí đọc đồng hồ theo từng node. CSV lưu thêm Planning Time và thời gian quan sát ở client.

Kết quả phản ánh truy vấn đã warm-up trên máy GitHub Actions tại lần chạy này. Cache hệ điều hành có thể được dùng. CPU, ổ đĩa, phiên bản PostgreSQL, thống kê, work_mem và parallelism có thể làm tỉ lệ cải thiện thay đổi.

## Kết quả đo

| Cặp | Trước, trung vị (ms) | Sau, trung vị (ms) | Trước / Sau | Output khác nhau |
| --- | ---: | ---: | ---: | ---: |
| WHERE | 165.983 | 19.805 | 8.38× | 0 |
| GROUP BY | 955.639 | 621.139 | 1.54× | 0 |
| HAVING | 3899.158 | 845.354 | 4.61× | 0 |

Tỉ số lớn hơn 1 nghĩa là bản sau tốn ít thời gian hơn trong phép đo này.

## Chứng minh cùng output

Script kiểm tra hai chiều EXCEPT ALL trên toàn bộ output đã materialize. Phép kiểm tra đối chiếu giá trị từng dòng, NULL và số lần xuất hiện. Chỉ kết thúc thành công khi không còn dòng chênh lệch. Thứ tự dòng không phải một phần của kết quả SQL khi không có ORDER BY. Mẫu bên dưới được sắp theo hai cột đầu để trình bày ổn định.

Bộ kiểm tra riêng có 13 bản ghi, gồm NULL ở khóa nhóm và provider_id, nhóm toàn NULL, nhóm một/nhiều provider, NULL ở timestamp và fare, fare âm, ngày nhuận và các mốc sát nửa đêm. Các phép kiểm tra này được chạy trên PostgreSQL trước benchmark.

## Cặp WHERE

### Trước

~~~sql
SELECT COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
WHERE pickup_at::date = DATE '2024-01-15';
~~~

### Sau

~~~sql
SELECT COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
WHERE pickup_at >= TIMESTAMP '2024-01-15 00:00:00'
  AND pickup_at < TIMESTAMP '2024-01-16 00:00:00';
~~~

Hai điều kiện chọn đúng ngày 15/01/2024. Cột pickup_at là TIMESTAMP không có múi giờ, nên khoảng nửa kín từ 00:00 ngày 15 đến trước 00:00 ngày 16 tương đương với ép kiểu sang DATE. NULL bị loại ở cả hai cách. Bản viết lại giữ cột ở dạng nguyên thủy để B-tree trên pickup_at có thể phục vụ điều kiện khoảng. Bản ép kiểu không khớp với index cột gốc. Một expression index trên pickup_at::date sẽ là một cấu hình khác.

Output toàn bộ có 1 dòng ở mỗi biến thể và 0 dòng khác nhau.

- Trước có min–max 165.870–168.319 ms. Plan ở lượt trung vị gồm Aggregate → Gather → Aggregate → Append → Seq Scan → Seq Scan. [Xem plan đầy đủ](results/plans/where_before.json).
- Sau có min–max 19.671–19.977 ms. Plan ở lượt trung vị gồm Aggregate → Append → Index Scan → Index Scan. [Xem plan đầy đủ](results/plans/where_after.json).

Mẫu tối đa 5 dòng output chung

~~~json
[
  [
    77033,
    "1486583.28"
  ]
]
~~~

## Cặp GROUP BY

### Trước

~~~sql
SELECT pickup_location_id, dropoff_location_id,
       COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
GROUP BY pickup_location_id, dropoff_location_id,
         (pickup_location_id::text || '/' || dropoff_location_id::text);
~~~

### Sau

~~~sql
SELECT pickup_location_id, dropoff_location_id,
       COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
GROUP BY pickup_location_id, dropoff_location_id;
~~~

Biểu thức nối chuỗi được xác định hoàn toàn bởi pickup_location_id và dropoff_location_id. Khi hai giá trị khóa giống nhau, biểu thức này cũng giống nhau, kể cả khi một khóa là NULL. Vì vậy thêm biểu thức vào GROUP BY không chia nhóm nào thành các nhóm nhỏ hơn. Bỏ khóa dư giữ nguyên COUNT và SUM, giảm công việc tính biểu thức và xử lý khóa. Ví dụ mô phỏng việc liệt kê thừa khóa tính toán trong truy vấn tổng hợp.

Output toàn bộ có 32,457 dòng ở mỗi biến thể và 0 dòng khác nhau.

- Trước có min–max 949.469–960.613 ms. Plan ở lượt trung vị gồm Aggregate → Gather → Aggregate → Result → Append → Seq Scan → Seq Scan. [Xem plan đầy đủ](results/plans/group_by_before.json).
- Sau có min–max 617.246–628.795 ms. Plan ở lượt trung vị gồm Aggregate → Gather → Aggregate → Append → Seq Scan → Seq Scan. [Xem plan đầy đủ](results/plans/group_by_after.json).

Mẫu tối đa 5 dòng output chung

~~~json
[
  [
    1,
    1,
    523,
    "44713.98"
  ],
  [
    1,
    6,
    2,
    "150.00"
  ],
  [
    1,
    48,
    1,
    "124.00"
  ],
  [
    1,
    68,
    1,
    "147.20"
  ],
  [
    1,
    132,
    2,
    "426.70"
  ]
]
~~~

## Cặp HAVING

### Trước

~~~sql
SELECT pickup_location_id, dropoff_location_id,
       COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
GROUP BY pickup_location_id, dropoff_location_id
HAVING COUNT(DISTINCT provider_id) > 1;
~~~

### Sau

~~~sql
SELECT pickup_location_id, dropoff_location_id,
       COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
GROUP BY pickup_location_id, dropoff_location_id
HAVING MIN(provider_id) <> MAX(provider_id);
~~~

COUNT(DISTINCT provider_id) > 1 chọn nhóm có ít nhất hai nhà cung cấp khác nhau. Với TEXT và collation đang dùng, điều đó tương đương MIN khác MAX. Cả COUNT(DISTINCT), MIN và MAX đều bỏ qua NULL. Nhóm chỉ có NULL có COUNT bằng 0, trong khi phép so sánh MIN/MAX trả UNKNOWN. Cả hai đều loại nhóm đó trong HAVING. Với một giá trị phân biệt, MIN bằng MAX và cả hai điều kiện đều sai. COUNT DISTINCT có thể cần sắp xếp hoặc khử trùng trong nhóm. MIN/MAX có thể tổng hợp trực tiếp và cho phép planner chọn cách aggregate khác. Phép viết lại này dành cho điều kiện có ít nhất hai giá trị phân biệt, không áp dụng tùy ý cho COUNT DISTINCT > k với k lớn hơn 1.

Output toàn bộ có 17,106 dòng ở mỗi biến thể và 0 dòng khác nhau.

- Trước có min–max 3840.621–4017.604 ms. Plan ở lượt trung vị gồm Aggregate → Sort → Append → Seq Scan → Seq Scan. [Xem plan đầy đủ](results/plans/having_before.json).
- Sau có min–max 817.843–870.824 ms. Plan ở lượt trung vị gồm Aggregate → Gather → Aggregate → Append → Seq Scan → Seq Scan. [Xem plan đầy đủ](results/plans/having_after.json).

Mẫu tối đa 5 dòng output chung

~~~json
[
  [
    1,
    1,
    523,
    "44713.98"
  ],
  [
    1,
    138,
    2,
    "207.80"
  ],
  [
    1,
    265,
    19,
    "920.70"
  ],
  [
    3,
    3,
    16,
    "570.33"
  ],
  [
    3,
    51,
    7,
    "111.27"
  ]
]
~~~

## Tái lập và tài liệu

- [Hướng dẫn chạy](README.md).
- [Toàn bộ số đo và kiểm chứng](results/benchmark.json).
- [Số đo từng lượt CSV](results/timings.csv).
- [Workflow](https://github.com/aiwwu/phy3645-bt1-env-demo/actions/workflows/bt3.yml).
- [PostgreSQL 16 — EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html).
- [PostgreSQL 16 — Aggregate functions](https://www.postgresql.org/docs/16/functions-aggregate.html).
- [PostgreSQL 16 — GROUP BY và HAVING](https://www.postgresql.org/docs/16/queries-table-expressions.html).
