# Bài thực hành 1 — Môi trường Python, máy ảo, Docker và PostgreSQL

Bài thực hành chạy cùng một chương trình Python ở các môi trường khác nhau để quan sát phần nào được cô lập. Phần cơ sở dữ liệu dùng PostgreSQL và dữ liệu giả lập về sinh viên, môn học và lượt đăng ký.

## Bài thực hành 2

[Nạp dữ liệu nhiều triệu dòng vào PostgreSQL, so sánh Python và psql](bt2/README.md).

## Bài thực hành 3

[Tối ưu WHERE, GROUP BY và HAVING trên dữ liệu bài 2](bt3/README.md).

## 1. So sánh ba môi trường

| Môi trường | Cô lập ở mức nào? | Dùng khi nào? |
| --- | --- | --- |
| Python virtual environment | Tách nơi cài thư viện Python theo dự án. Vẫn dùng hệ điều hành, kernel và mạng của máy đang chạy. | Hai dự án cần phiên bản khác nhau của cùng một thư viện. |
| Virtual machine (VM) | Hypervisor cung cấp phần cứng ảo. Hệ điều hành khách khởi động và chạy kernel riêng. | Thử cài Ubuntu hoặc kiểm tra chương trình trên hệ điều hành khách. |
| Docker container | Cô lập tiến trình, hệ thống tệp và các tài nguyên khác. Container Linux chia sẻ kernel với máy Linux đang chạy Docker Engine. | Đóng gói ứng dụng cùng runtime để chạy lại từ cùng một image. |

Docker **image** là mẫu chứa runtime và tệp cần thiết. **Container** là phiên bản đang chạy của image. Trên Windows hoặc macOS, Docker Desktop chạy Linux container trong một VM Linux, nên kernel chương trình in ra là kernel của VM đó.

Một số công cụ quản lý Python:

| Công cụ | Vai trò |
| --- | --- |
| `venv` | Mô-đun chuẩn để tạo môi trường từ trình thông dịch Python đang dùng. |
| `virtualenv` | Công cụ bên ngoài để tạo môi trường, có thể chọn trình thông dịch bằng `-p`. |
| `pyenv` | Cài đặt và chọn phiên bản trình thông dịch theo máy hoặc thư mục. Có thể dùng tiếp `venv` để tách thư viện. |
| `conda` | Quản lý môi trường và gói, bao gồm Python và các phụ thuộc ngoài Python. |
| `uv` | Quản lý phiên bản Python, môi trường dự án và các gói. `uv.lock` ghi lại kết quả giải phụ thuộc. |

## 2. Demo Python và virtual environment

Cần Git, Python 3.11 trở lên và [uv](https://docs.astral.sh/uv/getting-started/installation/). Trên một terminal mới, chạy:

```bash
git clone https://github.com/aiwwu/phy3645-bt1-env-demo.git
cd phy3645-bt1-env-demo
python3 demo.py
uv sync --locked
uv run --locked python demo.py
```

Trên Windows có thể dùng `py -3 demo.py` ở lệnh chạy trực tiếp. Script chỉ dùng thư viện chuẩn để dễ chạy ở cả máy thật và máy ảo. Khi chạy qua `uv`, đường dẫn trình thông dịch nằm trong `.venv`, hai giá trị `prefix` và `base_prefix` khác nhau, và `virtual_env_active` là `true`. Kernel và hostname giữ nguyên nếu cả hai lệnh chạy trên cùng một máy. `uv run` tự chọn môi trường dự án nên không cần kích hoạt thủ công.

Có thể thử tạo một môi trường bằng công cụ chuẩn để đối chiếu:

```bash
python3 -m venv .venv-stdlib
.venv-stdlib/bin/python demo.py
```

Trên PowerShell, chạy `py -3 -m venv .venv-stdlib` và `& .\.venv-stdlib\Scripts\python.exe demo.py`.

## 3. Demo máy ảo Ubuntu

1. Tạo VM Ubuntu trong VirtualBox theo [hướng dẫn của Ubuntu](https://ubuntu.com/tutorials/how-to-run-ubuntu-desktop-on-a-virtual-machine-using-virtualbox). Cấu hình tham khảo cho Ubuntu Desktop là 2 CPU ảo, 4 GB RAM và 25 GB đĩa ảo. Đặt hostname cho máy khách là `lab-vm`.
2. Khởi động VM, mở terminal **trong Ubuntu**, rồi chạy:

```bash
sudo apt update
sudo apt install -y git python3
git clone https://github.com/aiwwu/phy3645-bt1-env-demo.git
cd phy3645-bt1-env-demo
python3 demo.py
lsblk
```

3. So sánh `os`, `hostname` và `kernel` với máy thật. `lsblk` cho thấy thiết bị đĩa mà VM nhìn thấy. Hai máy có thể dùng cùng phiên bản kernel, nên tên kernel trùng nhau vẫn có thể xảy ra. Điểm khác biệt là Ubuntu khởi động kernel riêng trên phần cứng ảo.

## 4. Demo Docker

Từ thư mục repo trên máy có Docker Engine đang chạy:

```bash
docker build -t phy3645-env-demo .
docker run --rm --hostname lab-docker phy3645-env-demo
```

Chương trình in `hostname` là `lab-docker`, hệ điều hành là bản Debian trong image `python:3.12-slim` và Python đến từ image. So sánh trường `kernel` với máy chạy Docker Engine. Trên Linux, hai giá trị khớp. `--rm` dọn container sau khi thoát và giữ lại image để chạy tiếp.

## 5. Cài PostgreSQL trên máy cá nhân và chạy SQL

RDBMS quản lý dữ liệu dưới dạng bảng. Trong [`sql/demo.sql`](sql/demo.sql), khóa ngoại liên kết bảng `enrollments` với `students` và `courses`. Khóa chính ghép chặn đăng ký trùng cho cùng sinh viên và môn. Ràng buộc `CHECK` giới hạn điểm từ 0 tới 10. `psql` là chương trình dòng lệnh để gửi câu lệnh SQL tới máy chủ PostgreSQL.

### CachyOS / Arch Linux

Với máy mới cài PostgreSQL, chạy `initdb` một lần. Nếu máy đã có cụm dữ liệu PostgreSQL, bắt đầu từ lệnh `systemctl`.

```bash
sudo pacman -S postgresql
sudo -iu postgres initdb --locale=C.UTF-8 --encoding=UTF8 -D /var/lib/postgres/data
sudo systemctl start postgresql
sudo -u postgres createdb phy3645_lab
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d phy3645_lab < sql/demo.sql
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y postgresql
sudo systemctl start postgresql
sudo -u postgres createdb phy3645_lab
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d phy3645_lab < sql/demo.sql
```

Trên Windows, có thể dùng [trình cài PostgreSQL](https://www.postgresql.org/download/windows/). Trong PowerShell tại thư mục repo, dùng `createdb -U postgres phy3645_lab`, sau đó chạy `psql -X -U postgres -v ON_ERROR_STOP=1 -d phy3645_lab -f sql/demo.sql`. Nếu Windows chưa tìm thấy hai chương trình, thêm thư mục `bin` của PostgreSQL vào PATH.

Chỉ chạy `createdb` ở lần đầu. Script dùng một schema riêng, có thể chạy lại, và dùng `SAVEPOINT` để thực hành `UPDATE` và `DELETE` rồi khôi phục dữ liệu mẫu. Truy vấn đầu lọc được ba lượt đăng ký từ 8 điểm. Truy vấn thứ hai tổng hợp theo môn:

| Môn | Lượt đăng ký | Điểm trung bình |
| --- | ---: | ---: |
| Python | 2 | 8.00 |
| Cơ sở dữ liệu | 2 | 8.50 |
| Mạng máy tính | 0 | `NULL` |

`COUNT(e.student_id)` đếm các đăng ký thực tế. `LEFT JOIN` giữ cả môn chưa có đăng ký và `AVG` trả `NULL` khi không có điểm.

## 6. Quy trình Git và GitHub

Sau khi sửa một tệp trong bản clone của mình, xem thay đổi, chọn tệp muốn commit rồi đẩy commit lên GitHub:

```bash
git status
git diff
git add README.md
git diff --cached
git commit -m "Cap nhat huong dan bai thuc hanh"
git push origin main
```

`git add` chọn nội dung để ghi vào commit. `git commit` lưu một mốc trong lịch sử cục bộ. `git push` chuyển commit lên repo từ xa. Repo này loại trừ môi trường Python cục bộ, ảnh đĩa VM và tệp `.env` bằng `.gitignore`.

## Tài liệu tham khảo

- [Python venv](https://docs.python.org/3/library/venv.html) · [virtualenv](https://virtualenv.pypa.io/) · [pyenv](https://github.com/pyenv/pyenv) · [conda](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html) · [uv lock và sync](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Ubuntu trên VirtualBox](https://ubuntu.com/tutorials/how-to-run-ubuntu-desktop-on-a-virtual-machine-using-virtualbox) · [Docker container và image](https://docs.docker.com/get-started/docker-overview/)
- [PostgreSQL trên Arch Linux](https://wiki.archlinux.org/title/PostgreSQL) · [Nhập môn SQL với PostgreSQL](https://www.postgresql.org/docs/current/tutorial-sql.html) · [Git remotes](https://git-scm.com/book/en/v2/Git-Basics-Working-with-Remotes)
