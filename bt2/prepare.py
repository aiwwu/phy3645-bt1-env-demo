"""Tải dữ liệu TLC, chuyển từng batch sang CSV, ghi số dòng và SHA-256."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import urllib.request

import pyarrow.parquet as pq

COLUMNS = [
    "trip_id", "provider_id", "pickup_at", "dropoff_at",
    "pickup_location_id", "dropoff_location_id", "trip_distance", "fare_amount",
]
SOURCE_COLUMNS = {
    "yellow": [
        "VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime",
        "PULocationID", "DOLocationID", "trip_distance", "fare_amount",
    ],
    "fhvhv": [
        "hvfhs_license_num", "pickup_datetime", "dropoff_datetime",
        "PULocationID", "DOLocationID", "trip_miles", "base_passenger_fare",
    ],
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, path):
    if path.exists():
        return
    temporary = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(url, timeout=180) as response:
        with temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=SOURCE_COLUMNS, default="yellow")
    parser.add_argument("--months", nargs="+", default=["2024-01", "2024-02"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    for month in args.months:
        if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month):
            parser.error("Tháng phải có dạng YYYY-MM")
        name = f"{args.kind}_{month.replace('-', '')}"
        url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/{args.kind}_tripdata_{month}.parquet"
        parquet_path = args.data_dir / f"{name}.parquet"
        csv_path = args.data_dir / f"{name}.csv"
        print(f"Tải {url}", flush=True)
        download(url, parquet_path)
        source = pq.ParquetFile(parquet_path)
        if source.metadata.num_rows <= 1_000_000:
            raise ValueError(f"{name} có <= 1 triệu dòng")

        temporary = csv_path.with_suffix(".csv.part")
        row_count = 0
        with temporary.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(COLUMNS)
            for batch in source.iter_batches(
                batch_size=50_000, columns=SOURCE_COLUMNS[args.kind]
            ):
                values = [column.to_pylist() for column in batch.columns]
                for row in zip(*values):
                    row_count += 1
                    writer.writerow((row_count, *row))
        if row_count != source.metadata.num_rows:
            raise RuntimeError("Số dòng CSV khác số bản ghi Parquet")
        temporary.replace(csv_path)
        manifest.append({
            "name": name, "source_url": url, "rows": row_count,
            "csv_file": csv_path.name, "csv_bytes": csv_path.stat().st_size,
            "parquet_bytes": parquet_path.stat().st_size,
            "csv_sha256": sha256(csv_path),
            "parquet_sha256": sha256(parquet_path),
        })
        print(f"{name}: {row_count:,} dòng", flush=True)

    manifest_path = args.data_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
