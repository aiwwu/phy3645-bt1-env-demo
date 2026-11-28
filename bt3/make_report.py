"""Tạo báo cáo từ các phép đo và plan thực tế."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TITLES = {"where": "WHERE", "group_by": "GROUP BY", "having": "HAVING"}
EXPLANATIONS = {
    "where": (
        "Hai điều kiện chọn đúng ngày 15/01/2024. Cột pickup_at là TIMESTAMP "
        "không có múi giờ, nên khoảng nửa kín từ 00:00 ngày 15 đến trước 00:00 ngày 16 "
        "tương đương với ép kiểu sang DATE. NULL bị loại ở cả hai cách. "
        "Bản viết lại giữ cột ở dạng nguyên thủy để B-tree trên pickup_at có thể "
        "phục vụ điều kiện khoảng. Bản ép kiểu không khớp với index cột gốc. "
        "Một expression index trên pickup_at::date sẽ là một cấu hình khác."
    ),
    "group_by": (
        "Biểu thức nối chuỗi được xác định hoàn toàn bởi pickup_location_id "
        "và dropoff_location_id. Khi hai giá trị khóa giống nhau, biểu thức "
        "này cũng giống nhau, kể cả khi một khóa là NULL. Vì vậy thêm biểu thức "
        "vào GROUP BY không chia nhóm nào thành các nhóm nhỏ hơn. Bỏ khóa dư "
        "giữ nguyên COUNT và SUM, giảm công việc tính biểu thức và xử lý khóa. "
        "Ví dụ mô phỏng việc liệt kê thừa khóa tính toán trong truy vấn tổng hợp."
    ),
    "having": (
        "COUNT(DISTINCT provider_id) > 1 chọn nhóm có ít nhất hai nhà cung cấp "
        "khác nhau. Với TEXT và collation đang dùng, điều đó tương đương MIN "
        "khác MAX. Cả COUNT(DISTINCT), MIN và MAX đều bỏ qua NULL. Nhóm chỉ "
        "có NULL có COUNT bằng 0, trong khi phép so sánh MIN/MAX trả UNKNOWN. "
        "Cả hai đều loại nhóm đó trong HAVING. Với một giá trị phân biệt, MIN "
        "bằng MAX và cả hai điều kiện đều sai. "
        "COUNT DISTINCT có thể cần sắp xếp hoặc khử trùng trong nhóm. MIN/MAX "
        "có thể tổng hợp trực tiếp và cho phép planner chọn cách aggregate khác. "
        "Phép viết lại này dành cho điều kiện có ít nhất hai giá trị phân biệt, "
        "không áp dụng tùy ý cho COUNT DISTINCT > k với k lớn hơn 1."
    ),
}


def main():
    data = json.loads((ROOT / "results/benchmark.json").read_text())
    env = data["environment"]
    lines = [
        "# Báo cáo bài 3 — Tối ưu WHERE, GROUP BY và HAVING", "",
        "## Bài toán và dữ liệu", "",
        "Dùng lại hai file Yellow Taxi của bài 2, nạp vào "
        "bt2_copy.yellow_202401 và bt2_copy.yellow_202402. View bt3.trips "
        "kết hợp hai bảng bằng UNION ALL, giữ nguyên mọi bản ghi. "
        "Mỗi cặp chỉ thay đổi mệnh đề nêu trong tên cặp. "
        "SELECT, FROM và các mệnh đề còn lại giống hệt nhau.", "",
        "| Bảng | Số bản ghi |", "| --- | ---: |",
    ]
    for name, count in data["data_counts"].items():
        lines.append(f"| {name} | {count:,} |")
    lines += [
        "", f'Tổng cộng **{sum(data["data_counts"].values()):,} bản ghi**.', "",
        "## Môi trường và phương pháp", "",
        f'- Thời điểm UTC {env["measured_at_utc"]}.',
        f'- Máy {env["platform"]}, {env["cpu_count"]} CPU logic.',
        f'- PostgreSQL {env["postgresql"]}.',
        f'- Python {env["python"]}, psycopg {env["psycopg"]}.',
        f'- Cấu hình session {json.dumps(env["settings"], sort_keys=True)}.', "",
        "Index B-tree trên pickup_at được tạo sẵn ở cả hai bảng nguồn và "
        "ANALYZE được chạy trước phép đo. Hai biến thể luôn dùng chung index, "
        "thống kê và cấu hình. Chi phí tạo index, tải CSV và nạp dữ liệu "
        "được tách khỏi thời gian chạy truy vấn.", "",
        f'Mỗi truy vấn có một lượt warm-up và **{data["repeats"]} lượt đo**. '
        "Đổi thứ tự trước/sau ở lượt chẵn, dùng cùng snapshot REPEATABLE READ "
        "cho kiểm chứng toàn bộ dữ liệu và các lượt đo. Thời gian chính là "
        "Execution Time phía PostgreSQL từ EXPLAIN "
        "(ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON). TIMING OFF giảm chi phí "
        "đọc đồng hồ theo từng node. CSV lưu thêm Planning Time và thời "
        "gian quan sát ở client.", "",
        "Kết quả phản ánh truy vấn đã warm-up trên máy GitHub Actions tại lần "
        "chạy này. Cache hệ điều hành có thể được dùng. CPU, ổ đĩa, "
        "phiên bản PostgreSQL, thống kê, work_mem và parallelism có thể làm "
        "tỉ lệ cải thiện thay đổi.", "",
        "## Kết quả đo", "",
        "| Cặp | Trước, trung vị (ms) | Sau, trung vị (ms) | Trước / Sau | Output khác nhau |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for pair, result in data["results"].items():
        summaries = result["summaries"]
        lines.append(
            f'| {TITLES[pair]} | {summaries["before"]["median_ms"]:.3f} | '
            f'{summaries["after"]["median_ms"]:.3f} | {result["speedup"]:.2f}× | '
            f'{result["equality"]["different_rows"]} |'
        )
    lines += [
        "", "Tỉ số lớn hơn 1 nghĩa là bản sau tốn ít thời gian hơn trong phép đo này.", "",
        "## Chứng minh cùng output", "",
        "Script kiểm tra hai chiều EXCEPT ALL trên toàn bộ output đã materialize. "
        "Phép kiểm tra đối chiếu giá trị từng dòng, NULL và số lần xuất hiện. "
        "Chỉ kết thúc thành công khi không còn dòng chênh lệch. "
        "Thứ tự dòng không phải một phần của kết quả SQL khi không có ORDER BY. "
        "Mẫu bên dưới được sắp theo hai cột đầu để trình bày ổn định.", "",
        "Bộ kiểm tra riêng có 13 bản ghi, gồm NULL ở khóa nhóm và provider_id, "
        "nhóm toàn NULL, nhóm một/nhiều provider, NULL ở timestamp và fare, "
        "fare âm, ngày nhuận và các mốc sát nửa đêm. Các phép kiểm tra này "
        "được chạy trên PostgreSQL trước benchmark.", "",
    ]
    for pair, result in data["results"].items():
        lines += [
            f"## Cặp {TITLES[pair]}", "", "### Trước", "",
            "~~~sql", data["queries"][pair]["before"] + ";", "~~~", "",
            "### Sau", "", "~~~sql", data["queries"][pair]["after"] + ";", "~~~", "",
            EXPLANATIONS[pair], "",
            f'Output toàn bộ có {result["equality"]["before_rows"]:,} dòng '
            f'ở mỗi biến thể và {result["equality"]["different_rows"]} dòng khác nhau.', "",
        ]
        for variant, title in (("before", "Trước"), ("after", "Sau")):
            summary = result["summaries"][variant]
            lines.append(
                f'- {title} có min–max {summary["min_ms"]:.3f}–'
                f'{summary["max_ms"]:.3f} ms. Plan ở lượt trung vị gồm '
                f'{" → ".join(summary["plan_nodes"])}. '
                f'[Xem plan đầy đủ]({summary["plan_file"]}).'
            )
        if result["speedup"] <= 1:
            lines += ["", "Bản viết lại chưa cải thiện trung vị ở lần đo này."]
        lines += [
            "", "Mẫu tối đa 5 dòng output chung", "", "~~~json",
            json.dumps(result["sample"], ensure_ascii=False, indent=2), "~~~", "",
        ]
    lines += [
        "## Tái lập và tài liệu", "",
        "- [Hướng dẫn chạy](README.md).",
        "- [Toàn bộ số đo và kiểm chứng](results/benchmark.json).",
        "- [Số đo từng lượt CSV](results/timings.csv).",
        "- [Workflow](https://github.com/aiwwu/phy3645-bt1-env-demo/actions/workflows/bt3.yml).",
        "- [PostgreSQL 16 — EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html).",
        "- [PostgreSQL 16 — Aggregate functions](https://www.postgresql.org/docs/16/functions-aggregate.html).",
        "- [PostgreSQL 16 — GROUP BY và HAVING](https://www.postgresql.org/docs/16/queries-table-expressions.html).", "",
    ]
    (ROOT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
