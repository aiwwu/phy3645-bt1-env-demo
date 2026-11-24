"""Đọc footer Parquet từ HTTP Range để kiểm tra dataset phụ trên 10 triệu dòng."""

import io
import json
from pathlib import Path
import struct
import urllib.request

import pyarrow.parquet as pq

URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_2024-01.parquet"


def read_range(byte_range):
    request = urllib.request.Request(URL, headers={"Range": byte_range})
    with urllib.request.urlopen(request, timeout=180) as response:
        if response.status != 206:
            raise RuntimeError("Máy chủ phải hỗ trợ HTTP Range, dừng để tránh tải toàn bộ")
        return response.read(), response.headers["Content-Range"]


def main():
    tail, content_range = read_range("bytes=-8")
    if tail[4:] != b"PAR1":
        raise ValueError("Footer không phải Parquet")
    length = struct.unpack("<I", tail[:4])[0]
    footer, _ = read_range(f"bytes=-{length + 8}")
    metadata = pq.read_metadata(io.BytesIO(b"PAR1" + footer))
    if metadata.num_rows <= 10_000_000:
        raise ValueError("Dataset phụ không đạt 10 triệu bản ghi")
    result = {
        "source_url": URL,
        "dataset": "NYC TLC High Volume For-Hire Vehicle, January 2024",
        "rows": metadata.num_rows,
        "file_bytes": int(content_range.rsplit("/", 1)[1]),
        "verification": "Parquet metadata fetched with HTTP Range",
        "benchmark_performed": False,
    }
    Path("results").mkdir(exist_ok=True)
    Path("results/large_dataset.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
