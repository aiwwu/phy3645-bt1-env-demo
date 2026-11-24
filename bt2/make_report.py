"""Sinh báo cáo từ số liệu đo thực tế, giữ kèm JSON và CSV gốc."""

import json
from pathlib import Path
import statistics


def main():
    result = json.loads(Path("results/benchmark.json").read_text())
    extra = json.loads(Path("results/large_dataset.json").read_text())
    rows = [
        "# Báo cáo bài 2 — Nạp dữ liệu nhiều triệu dòng vào PostgreSQL",
        "",
        "## Dữ liệu thực nghiệm",
        "",
        "Dữ liệu công khai NYC TLC Yellow Taxi, tháng 01 và 02 năm 2024. "
        "Mỗi file nguồn là Parquet và được chuyển sang CSV để dùng chung cho hai cách nạp. "
        "Giữ toàn bộ bản ghi, chọn 7 trường nguồn và thêm trip_id theo vị trí dòng trong file. "
        "Mỗi file tương ứng một bảng. NULL được xuất thành trường CSV rỗng. "
        "Điểm đón/trả giữ nguyên dưới dạng mã vùng.",
        "",
        "| File CSV | Số bản ghi | Dung lượng CSV (MiB) |",
        "| --- | ---: | ---: |",
    ]
    for item in result["manifest"]:
        rows.append(
            f'| {item["csv_file"]} | {item["rows"]:,} | '
            f'{item["csv_bytes"] / 1024**2:.2f} |'
        )
    total = sum(item["rows"] for item in result["manifest"])
    env = result["environment"]
    rows += [
        "",
        f"Tổng cộng {total:,} bản ghi. Mỗi file đều có trên 1 triệu dòng dữ liệu, "
        "chưa tính header. SHA-256 của cả Parquet và CSV có trong benchmark.json.",
        "",
        "## Môi trường và cách đo",
        "",
        f'- Thời điểm UTC {env["measured_at_utc"]}.',
        f'- Máy chạy {env["platform"]}, {env["cpu_count"]} CPU logic.',
        f'- Python {env["python"]}, psycopg {env["psycopg"]}.',
        f'- Máy chủ {env["postgresql"]}.',
        f'- Thiết lập PostgreSQL `{json.dumps(env["settings"], sort_keys=True)}`.',
        "",
        "Cách A dùng Python đọc CSV bằng luồng và INSERT nhiều VALUES, "
        f'mỗi batch tối đa {result["batch_size"]:,} dòng. Giá trị được truyền qua '
        "placeholder của psycopg. Cách B dùng psql \\copy từ CSV phía client. "
        "Benchmark gọi đúng lệnh psql cũng được cung cấp để chạy tay.",
        "",
        "Mỗi bảng dùng một transaction cho toàn bộ file và có cùng khóa chính BIGINT. "
        "TRUNCATE được COMMIT trước khi bấm giờ. Thời gian đo gồm đọc CSV, "
        "truyền dữ liệu, ghi bảng, cập nhật khóa chính và COMMIT. Với psql, "
        "thời gian còn gồm khởi động client và kết nối. Tải mạng, chuyển Parquet, "
        "TRUNCATE và kiểm tra kết quả nằm ngoài khoảng đo. "
        "Giữ fsync, synchronous_commit và full_page_writes theo cấu hình ghi phía trên.",
        "",
        f'Chạy {result["repeats"]} lượt trên toàn bộ dữ liệu, '
        "đổi thứ tự INSERT/COPY ở lượt chẵn. Báo cáo lấy trung vị và ghi min–max. "
        "Các lượt có thể dùng cache của hệ điều hành. "
        "Kết quả phản ánh máy GitHub Actions tại lần chạy này, có thể thay đổi "
        "theo CPU, ổ đĩa, tải hệ thống và khoảng cách mạng tới database.",
        "",
        "## Kết quả thực đo",
        "",
        "| File | Cách | Trung vị (s) | Min–max (s) | Dòng/giây |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    medians = {}
    for item in result["manifest"]:
        for method in ("insert", "copy"):
            measurements = [
                m for m in result["measurements"]
                if m["dataset"] == item["name"] and m["method"] == method
            ]
            times = [m["seconds"] for m in measurements]
            median = statistics.median(times)
            medians[(item["name"], method)] = median
            rows.append(
                f'| {item["csv_file"]} | {method} | {median:.3f} | '
                f'{min(times):.3f}–{max(times):.3f} | {item["rows"]/median:,.0f} |'
            )

    rows += ["", "## Nhận xét và so sánh", ""]
    for item in result["manifest"]:
        ratio = medians[(item["name"], "insert")] / medians[(item["name"], "copy")]
        rows.append(
            f'- {item["csv_file"]} có tỉ số thời gian INSERT/COPY là {ratio:.2f}. '
            "Giá trị lớn hơn 1 cho thấy COPY tốn ít thời gian hơn trong phép đo này."
        )
    rows += [
        "",
        "| Tiêu chí | Python INSERT theo lô | psql \\copy chạy tay |",
        "| --- | --- | --- |",
        "| Tốc độ | Có chi phí tạo câu SQL, bind tham số và chạy nhiều lệnh | Truyền luồng qua giao thức COPY, giảm chi phí từng câu lệnh |",
        "| Xử lý dữ liệu | Dễ kiểm tra, biến đổi từng dòng trước khi nạp | CSV cần khớp cột và kiểu dữ liệu bảng đích |",
        "| Bộ nhớ client | Giới hạn theo kích thước batch | Truyền luồng dữ liệu |",
        "| Tự động hóa | Thuận tiện cho pipeline Python | Chạy trực tiếp trong psql hoặc script SQL |",
        "| Lỗi | Exception làm rollback cả file trong thiết kế này | ON_ERROR_STOP và transaction làm rollback cả file |",
        "| Chạy lại | TRUNCATE bảng thực hành trước khi nạp | Cần TRUNCATE bảng thực hành trước khi nạp |",
        "",
        "COPY phù hợp với lần nạp lớn từ file đã chuẩn bị. INSERT theo lô hữu ích "
        "khi cần logic Python hoặc điều kiện theo bản ghi. Nếu nạp vào bảng nghiệp vụ "
        "đã có dữ liệu, có thể COPY vào staging rồi dùng INSERT ... ON CONFLICT "
        "để hợp nhất theo khóa.",
        "",
        "## Kiểm chứng và giới hạn",
        "",
        "Mọi lượt đều kiểm tra COUNT, MIN/MAX của trip_id, tổng trip_id, tổng fare_amount "
        "và tổng hash 64-bit trên toàn bộ 8 trường. Các fingerprint khớp giữa hai phương pháp "
        "và giữa các lần chạy. Hash có khả năng va chạm, vì vậy đây là kiểm tra toàn vẹn "
        "thực dụng. Tệp JSON lưu fingerprint để kiểm tra lại. "
        "Khóa chính ngăn trip_id trùng trong từng bảng.",
        "",
        "Các giá trị nguồn âm hoặc timestamp bất thường được giữ lại. "
        "fare_amount lưu NUMERIC(18,2) và PostgreSQL làm tròn đến 2 chữ số thập phân. "
        "trip_distance dùng DOUBLE PRECISION. Cùng kiểu dữ liệu và CSV được dùng cho cả hai phương pháp.",
        "",
        "Thiết kế một bảng mỗi file phù hợp yêu cầu bài tập. Trong hệ thống truy vấn lâu dài, "
        "có thể dùng một bảng trips phân vùng theo tháng và bảng tham chiếu vùng taxi. "
        "trip_id ở đây chỉ có ý nghĩa trong từng file, nên phải kèm tháng khi gộp dữ liệu.",
        "",
        "## Dataset bổ sung trên 10 triệu dòng",
        "",
        f'{extra["dataset"]} có **{extra["rows"]:,} bản ghi**, '
        f'dung lượng Parquet {extra["file_bytes"]/1024**2:.2f} MiB. '
        "Số lượng được đọc trực tiếp từ metadata Parquet bằng HTTP Range. "
        "Nguồn và cách kiểm tra có trong results/large_dataset.json. "
        "Dataset này được xác minh quy mô. Phép benchmark trong báo cáo dùng hai file Yellow Taxi phía trên.",
        "",
        "Có thể tải và chuyển CSV bằng `python prepare.py --kind fhvhv --months 2024-01 --data-dir data-large`, "
        "sau đó chạy `python benchmark.py --data-dir data-large --results-dir results-large`. "
        "Trường fare_amount của FHV là base_passenger_fare. "
        "Cần điều chỉnh dung lượng lưu trữ cho dataset lớn.",
        "",
        "## Tệp kết quả và nguồn",
        "",
        "- [Số đo từng lượt và môi trường](results/benchmark.json)",
        "- [Bảng số đo CSV](results/benchmark.csv)",
        "- [Metadata dataset bổ sung](results/large_dataset.json)",
        "- [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)",
        "- [PostgreSQL psql và copy](https://www.postgresql.org/docs/current/app-psql.html)",
        "- [Psycopg truyền tham số](https://www.psycopg.org/psycopg3/docs/basic/params.html)",
        "",
    ]
    Path("REPORT.md").write_text("\n".join(rows), encoding="utf-8")


if __name__ == "__main__":
    main()
