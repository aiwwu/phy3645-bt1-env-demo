"""Đối chiếu output chính xác và đo ba cặp SQL bằng EXPLAIN ANALYZE."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import platform
import statistics
import time

import psycopg

PAIR_CLAUSES = {"where": "WHERE", "group_by": "GROUP BY", "having": "HAVING"}
VARIANTS = ("before", "after")
EXPLAIN = "EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON) "
ROOT = Path(__file__).resolve().parent


def read_queries():
    queries = {}
    for pair, clause in PAIR_CLAUSES.items():
        queries[pair] = {
            variant: (ROOT / "sql" / f"{pair}_{variant}.sql").read_text().strip()
            for variant in VARIANTS
        }
        before, after = (queries[pair][variant] for variant in VARIANTS)
        # Các file chỉ có một câu SELECT, mệnh đề được thay đổi nằm ở cuối.
        marker = "\n" + clause + " "
        if before.count(marker) != 1 or after.count(marker) != 1:
            raise ValueError(f"Mệnh đề {clause} phải xuất hiện đúng một lần")
        if before.split(marker)[0] != after.split(marker)[0]:
            raise ValueError(f"Cặp {pair} có thay đổi ngoài {clause}")
        if before == after:
            raise ValueError(f"Cặp {pair} chưa có thay đổi")
    return queries


def compare_outputs(connection, before, after):
    """EXCEPT ALL hai chiều kiểm tra cả giá trị NULL và số lần lặp."""
    query = f"""
    WITH baseline AS MATERIALIZED ({before}),
         optimized AS MATERIALIZED ({after}),
         delta AS (
             (TABLE baseline EXCEPT ALL TABLE optimized)
             UNION ALL
             (TABLE optimized EXCEPT ALL TABLE baseline)
         )
    SELECT (SELECT COUNT(*) FROM baseline),
           (SELECT COUNT(*) FROM optimized),
           (SELECT COUNT(*) FROM delta)
    """
    before_count, after_count, different_rows = connection.execute(query).fetchone()
    if different_rows != 0:
        raise AssertionError(f"Output khác nhau ở {different_rows} dòng")
    return {
        "before_rows": before_count, "after_rows": after_count,
        "different_rows": different_rows,
        "method": "bidirectional EXCEPT ALL on materialized query results",
    }


def check_edge_cases(connection, queries):
    connection.execute("""
        CREATE TEMP TABLE bt3_edge_cases (
            trip_id bigint, provider_id text, pickup_at timestamp,
            dropoff_at timestamp, pickup_location_id integer,
            dropoff_location_id integer, trip_distance double precision,
            fare_amount numeric(18, 2)
        ) ON COMMIT DROP
    """)
    connection.execute("""
        INSERT INTO bt3_edge_cases
            (trip_id, provider_id, pickup_at, pickup_location_id,
             dropoff_location_id, fare_amount)
        VALUES
            (1, '1', '2024-01-15 00:00:00', 1, 2, 10),
            (2, '2', '2024-01-15 23:59:59.999999', 1, 2, 20),
            (3, NULL, '2024-01-14 23:59:59.999999', 1, 2, NULL),
            (4, '2', '2024-01-16 00:00:00', 3, 4, -5),
            (5, '2', '2024-01-15 12:00:00', 3, 4, 5),
            (6, NULL, '2024-01-15 12:00:00', 5, 6, NULL),
            (7, NULL, NULL, 5, 6, NULL),
            (8, '1', '2024-01-15 12:00:00', NULL, 7, 1),
            (9, '2', '2024-01-15 12:00:00', NULL, 7, 2),
            (10, '1', '2024-02-29 00:00:00', 8, NULL, 3),
            (11, NULL, '2024-01-15 12:00:00', 8, NULL, 4),
            (12, '1', '2024-01-15 12:00:00', NULL, NULL, 5),
            (13, '2', '2024-01-15 12:00:00', NULL, NULL, 6)
    """)
    return {
        pair: compare_outputs(
            connection,
            variants["before"].replace("bt3.trips", "bt3_edge_cases"),
            variants["after"].replace("bt3.trips", "bt3_edge_cases"),
        )
        for pair, variants in queries.items()
    }


def plan_nodes(node):
    nodes = [node["Node Type"]]
    for child in node.get("Plans", []):
        nodes.extend(plan_nodes(child))
    return nodes


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Không thể mã hóa {type(value)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    if args.repeats < 3 or args.repeats % 2 == 0:
        parser.error("repeats phải là số lẻ >= 3 để chọn plan ở trung vị")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        parser.error("Cần đặt DATABASE_URL tới database đã chuẩn bị")
    queries = read_queries()
    output_dir = ROOT / "results"
    (output_dir / "plans").mkdir(parents=True, exist_ok=True)

    with psycopg.connect(dsn, autocommit=True) as connection:
        # Session riêng, các SELECT dùng cùng cấu hình cho cả hai biến thể.
        connection.execute("SET jit = off")
        connection.execute("SET work_mem = '64MB'")
        connection.execute("SET statement_timeout = '180s'")
        if not connection.execute(
            "SELECT pg_try_advisory_lock(3645, 3)"
        ).fetchone()[0]:
            raise RuntimeError("Một benchmark bài 3 khác đang chạy")
        with connection.transaction():
            edge_cases = check_edge_cases(connection, queries)

        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            environment = {
                "measured_at_utc": datetime.now(timezone.utc).isoformat(),
                "platform": platform.platform(),
                "cpu_count": os.cpu_count(),
                "python": platform.python_version(),
                "psycopg": psycopg.__version__,
                "postgresql": connection.execute("SELECT version()").fetchone()[0],
                "settings": dict(connection.execute("""
                    SELECT name, setting FROM pg_settings WHERE name IN (
                        'jit', 'work_mem', 'shared_buffers',
                        'max_parallel_workers_per_gather', 'enable_seqscan',
                        'enable_indexscan', 'enable_hashagg', 'lc_collate'
                    )
                """).fetchall()),
            }
            data_counts = dict(connection.execute("""
                SELECT 'yellow_202401', COUNT(*) FROM bt2_copy.yellow_202401
                UNION ALL
                SELECT 'yellow_202402', COUNT(*) FROM bt2_copy.yellow_202402
            """).fetchall())
            if data_counts != {"yellow_202401": 2964624, "yellow_202402": 3007526}:
                raise AssertionError(f"Dữ liệu khác bài 2: {data_counts}")

            results = {}
            measurements = []
            for pair, variants in queries.items():
                equality = compare_outputs(connection, variants["before"], variants["after"])
                sample = connection.execute(
                    variants["after"] + " ORDER BY 1 NULLS FIRST, 2 NULLS FIRST LIMIT 5"
                ).fetchall()

                # Một lượt warm-up riêng, không đưa vào thống kê.
                for variant in VARIANTS:
                    connection.execute(EXPLAIN + variants[variant]).fetchone()

                plans = {variant: [] for variant in VARIANTS}
                for repeat in range(1, args.repeats + 1):
                    order = VARIANTS if repeat % 2 else tuple(reversed(VARIANTS))
                    for position, variant in enumerate(order, start=1):
                        started = time.perf_counter()
                        document = connection.execute(
                            EXPLAIN + variants[variant]
                        ).fetchone()[0][0]
                        wall_ms = (time.perf_counter() - started) * 1000
                        root = document["Plan"]
                        measurement = {
                            "pair": pair, "variant": variant,
                            "repeat": repeat, "position": position,
                            "execution_ms": document["Execution Time"],
                            "planning_ms": document["Planning Time"],
                            "client_wall_ms": wall_ms,
                            "shared_hit_blocks": root.get("Shared Hit Blocks", 0),
                            "shared_read_blocks": root.get("Shared Read Blocks", 0),
                            "temp_read_blocks": root.get("Temp Read Blocks", 0),
                            "temp_written_blocks": root.get("Temp Written Blocks", 0),
                        }
                        plans[variant].append(document)
                        measurements.append(measurement)
                        print(json.dumps(measurement), flush=True)

                summaries = {}
                for variant in VARIANTS:
                    ordered = sorted(plans[variant], key=lambda p: p["Execution Time"])
                    representative = ordered[len(ordered) // 2]
                    times = [plan["Execution Time"] for plan in ordered]
                    plan_path = output_dir / "plans" / f"{pair}_{variant}.json"
                    plan_path.write_text(
                        json.dumps(representative, indent=2) + "\n", encoding="utf-8"
                    )
                    summaries[variant] = {
                        "median_ms": statistics.median(times),
                        "min_ms": min(times), "max_ms": max(times),
                        "plan_nodes": plan_nodes(representative["Plan"]),
                        "plan_file": f"results/plans/{pair}_{variant}.json",
                        "shared_read_blocks": representative["Plan"].get("Shared Read Blocks", 0),
                        "temp_written_blocks": representative["Plan"].get("Temp Written Blocks", 0),
                    }
                results[pair] = {
                    "equality": equality, "sample": sample,
                    "summaries": summaries,
                    "speedup": summaries["before"]["median_ms"] / summaries["after"]["median_ms"],
                }

        output = {
            "environment": environment, "data_counts": data_counts,
            "repeats": args.repeats, "edge_cases": edge_cases,
            "queries": queries, "results": results, "measurements": measurements,
        }
        (output_dir / "benchmark.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2, default=json_value) + "\n",
            encoding="utf-8",
        )
        with (output_dir / "timings.csv").open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=list(measurements[0]))
            writer.writeheader()
            writer.writerows(measurements)
        print("Tất cả cặp truy vấn cho output giống nhau.", flush=True)


if __name__ == "__main__":
    main()
