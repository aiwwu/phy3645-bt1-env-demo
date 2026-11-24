"""So sánh INSERT nhiều VALUES bằng Python và psql \\copy trên cùng CSV."""

import argparse
import csv
from datetime import datetime, timezone
from itertools import islice
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import time

import psycopg
from psycopg import sql

from prepare import COLUMNS, sha256

DEFINITION = """
trip_id BIGINT PRIMARY KEY,
provider_id TEXT,
pickup_at TIMESTAMP,
dropoff_at TIMESTAMP,
pickup_location_id INTEGER,
dropoff_location_id INTEGER,
trip_distance DOUBLE PRECISION,
fare_amount NUMERIC(18, 2)
"""


def reset_table(connection, schema, name):
    # Chỉ TRUNCATE bảng trong hai schema dành riêng cho benchmark.
    with connection.transaction():
        connection.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
            sql.Identifier(schema)))
        connection.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
            sql.Identifier(schema), sql.Identifier(name), sql.SQL(DEFINITION)))
        connection.execute(sql.SQL("TRUNCATE {}.{}").format(
            sql.Identifier(schema), sql.Identifier(name)))


def insert_python(connection, name, path, batch_size):
    with connection.transaction(), connection.cursor() as cursor:
        with path.open(encoding="utf-8", newline="") as source:
            reader = csv.reader(source)
            if next(reader) != COLUMNS:
                raise ValueError("CSV header không khớp")
            while batch := list(islice(reader, batch_size)):
                if any(len(row) != len(COLUMNS) for row in batch):
                    raise ValueError("CSV có dòng sai số cột")
                placeholders = sql.SQL(",").join(
                    sql.SQL("(") + sql.SQL(",").join(
                        sql.Placeholder() for _ in COLUMNS
                    ) + sql.SQL(")") for _ in batch
                )
                query = sql.SQL("INSERT INTO bt2_insert.{} VALUES {}").format(
                    sql.Identifier(name), placeholders)
                parameters = [
                    None if value == "" else value for row in batch for value in row
                ]
                cursor.execute(query, parameters)


def copy_commands(name, path):
    # psql meta-command cần đường dẫn trên một dòng, quote bằng dấu nháy đơn.
    filename = str(path.resolve())
    if any(character in filename for character in "\r\n\\"):
        raise ValueError("Đường dẫn chứa newline hoặc backslash không được hỗ trợ")
    filename = filename.replace("'", "''")
    return (
        "\\set ON_ERROR_STOP on\nBEGIN;\n"
        f"\\copy bt2_copy.{name} FROM '{filename}' WITH (FORMAT csv, HEADER true, NULL '')\n"
        "COMMIT;\n"
    )


def copy_psql(dsn, name, path, psql_program):
    environment = os.environ.copy()
    # Giữ DSN khỏi argv và file kết quả, dùng libpq qua PGDATABASE.
    environment["PGDATABASE"] = dsn
    subprocess.run(
        [psql_program, "-X", "-v", "ON_ERROR_STOP=1"],
        input=copy_commands(name, path), text=True, env=environment, check=True,
    )


def signature(connection, schema, name):
    query = sql.SQL("""
        SELECT count(*), min(trip_id), max(trip_id),
               sum(trip_id)::text,
               COALESCE(sum(fare_amount), 0)::text,
               COALESCE(sum(hashtextextended(ROW(
                   trip_id, provider_id, pickup_at, dropoff_at,
                   pickup_location_id, dropoff_location_id,
                   trip_distance, fare_amount
               )::text, 0)::numeric), 0)::text
        FROM {}.{}
    """).format(sql.Identifier(schema), sql.Identifier(name))
    return list(connection.execute(query).fetchone())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--psql", default="psql")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 8000 or args.repeats < 1:
        parser.error("batch-size phải từ 1 đến 8000, repeats >= 1")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        parser.error("Cần đặt DATABASE_URL tới database thực hành")
    manifest = json.loads((args.data_dir / "manifest.json").read_text())
    for item in manifest:
        if not re.fullmatch(r"(yellow|fhvhv)_20\d{4}", item["name"]):
            raise ValueError("Tên bảng không hợp lệ")
        path = args.data_dir / item["csv_file"]
        if path.parent.resolve() != args.data_dir.resolve():
            raise ValueError("CSV phải ở trong data-dir")
        if sha256(path) != item["csv_sha256"]:
            raise ValueError(f"SHA-256 CSV thay đổi: {path}")

    measurements = []
    args.results_dir.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(dsn, autocommit=True) as connection:
        environment = {
            "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "psycopg": psycopg.__version__,
            "postgresql": connection.execute("SELECT version()").fetchone()[0],
            "settings": dict(connection.execute(
                "SELECT name, setting FROM pg_settings WHERE name IN "
                "('fsync','synchronous_commit','full_page_writes','shared_buffers')"
            ).fetchall()),
        }
        # Ngăn hai lần chạy benchmark tranh TRUNCATE cùng bảng.
        if not connection.execute(
            "SELECT pg_try_advisory_lock(3645, 2)"
        ).fetchone()[0]:
            raise RuntimeError("Một benchmark khác đang chạy trong database")
        for repeat in range(1, args.repeats + 1):
            order = ["insert", "copy"] if repeat % 2 else ["copy", "insert"]
            for method in order:
                for item in manifest:
                    name = item["name"]
                    path = args.data_dir / item["csv_file"]
                    reset_table(connection, f"bt2_{method}", name)
                    started = time.perf_counter()
                    if method == "insert":
                        insert_python(connection, name, path, args.batch_size)
                    else:
                        copy_psql(dsn, name, path, args.psql)
                    elapsed = time.perf_counter() - started
                    fingerprint = signature(connection, f"bt2_{method}", name)
                    expected_rows = item["rows"]
                    if fingerprint[:4] != [
                        expected_rows, 1, expected_rows,
                        str(expected_rows * (expected_rows + 1) // 2),
                    ]:
                        raise RuntimeError("Số dòng hoặc dải ID nạp vào không khớp")
                    previous = next((
                        result["signature"] for result in measurements
                        if result["dataset"] == name
                    ), fingerprint)
                    if fingerprint != previous:
                        raise RuntimeError("Hai cách nạp trả fingerprint khác nhau")
                    result = {
                        "repeat": repeat, "method": method, "dataset": name,
                        "rows": expected_rows, "seconds": elapsed,
                        "rows_per_second": expected_rows / elapsed,
                        "signature": fingerprint,
                        "table_bytes": connection.execute(
                            "SELECT pg_total_relation_size(%s)",
                            (f"bt2_{method}.{name}",),
                        ).fetchone()[0],
                    }
                    measurements.append(result)
                    print(json.dumps(result, ensure_ascii=False), flush=True)

        output = {
            "environment": environment, "batch_size": args.batch_size,
            "repeats": args.repeats, "manifest": manifest,
            "measurements": measurements,
        }
        (args.results_dir / "benchmark.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with (args.results_dir / "benchmark.csv").open(
            "w", encoding="utf-8", newline=""
        ) as destination:
            writer = csv.DictWriter(destination, fieldnames=[
                "repeat", "method", "dataset", "rows", "seconds", "rows_per_second",
                "table_bytes",
            ], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(measurements)
        print("Hoàn tất. Tất cả fingerprint khớp.", flush=True)


if __name__ == "__main__":
    main()
