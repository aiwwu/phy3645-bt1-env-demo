"""In thông tin để đối chiếu khi chạy cùng một script ở nhiều môi trường."""

import json
import platform
import socket
import sys
from pathlib import Path


def main() -> None:
    os_release = Path("/etc/os-release")
    os_name = platform.system()
    if os_release.is_file():
        for line in os_release.read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                os_name = line.split("=", 1)[1].strip('"')
                break

    info = {
        "os": os_name,
        "kernel": platform.release(),
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        "executable": sys.executable,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "virtual_env_active": sys.prefix != sys.base_prefix,
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
