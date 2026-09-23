# lacco-dashboard

Dashboard hỗ trợ ra quyết định LACCO — Giai đoạn 1 WebApp.

Dự án Dashboard hỗ trợ ra quyết định LACCO — khởi tạo 27/07/2026. Đây là dự án song song 2 mục tiêu: (1) xây dashboard nội bộ thật cho Ban Lãnh đạo Công ty LACCO, và (2) làm case study giảng dạy "Claude for Business" — mọi quyết định, lỗi thật gặp phải, và cách xử lý đều được ghi lại trong `docs/teaching-notes/`.

## Tổng quan

Ứng dụng Streamlit tổng hợp dữ liệu từ 2 hệ thống nguồn (FT — vận hành/kinh doanh, AMIS — tài chính/nhân sự) vào 1 kho dữ liệu MySQL riêng, hiển thị 6 nhóm báo cáo (Kinh doanh, Khách hàng, Đơn hàng, Pricing, Chi phí, Công nợ) với phân quyền 3 cấp (Admin/Manager/User) theo Khối/Phòng/phân loại khách hàng A/B/C.

Chi tiết kiến trúc, mô hình dữ liệu, RBAC, và các quyết định nghiệp vụ đã chốt: xem `docs/architecture/SDD.md`.

## Cấu trúc thư mục

```
src/db/models/    Model SQLAlchemy (dimension, business, security)
src/services/     Logic tính KPI + truy vấn (parameterized SQLAlchemy)
src/auth/         Đăng nhập (bcrypt), RBAC (DataScope)
src/app/          Streamlit — main.py + pages/ (1 file/module báo cáo)
migrations/       Alembic
scripts/          Sinh dữ liệu mẫu dev, import pipeline
docs/             Tài liệu yêu cầu, kiến trúc, nhật ký học tập
tests/            pytest (SQLite in-memory, không cần MySQL thật)
```

## Cài đặt & chạy (môi trường dev)

```bash
pip install -r requirements.txt
cp .env.example .env   # điền thông tin kết nối MySQL thật
alembic upgrade head    # tạo schema
python scripts/generate_synthetic_sample_data.py   # sinh dữ liệu mẫu (tuỳ chọn, cho dev)
streamlit run src/app/main.py
```

Chạy test: `pytest tests/ -v --cov=src`
Lint: `ruff check src/ tests/ scripts/`

## Deploy (Windows, chạy như dịch vụ nền)

1. Tạo venv `.venv` (Python 3.12) và `pip install -r requirements.txt`.
2. Tạo `.env` production từ `.env.example`: `APP_ENVIRONMENT=production`, `AUTH_COOKIE_KEY` sinh bằng `python -c "import secrets; print(secrets.token_hex(32))"`, tài khoản `lacco_app`/`lacco_migrate` (không dùng root). `.env` đã nằm trong `.gitignore`, không commit.
3. `alembic upgrade head`.
4. Mở PowerShell quyền Administrator: `scripts/deploy/install_service.ps1` — đăng ký Scheduled Task "LACCO Dashboard" chạy lúc khởi động máy (tài khoản SYSTEM), tự restart khi crash (vòng lặp trong `scripts/deploy/run_app.cmd`), đặt MySQL80 tự khởi động. Log tại `logs/streamlit.log`.
5. Mở cổng 8501 trên Windows Firewall và cố định IP của máy.

## Tài liệu

- `docs/architecture/SDD.md` — thiết kế hệ thống hiện tại (cập nhật dần theo code thật).
- `docs/architecture/erd-tuan-02.md` — biên bản quyết định ERD gốc.
- `CLAUDE.md` — quy ước bắt buộc cho mọi subagent làm việc trên dự án này.
- `docs/teaching-notes/` — nhật ký học tập theo tuần + hướng dẫn kỹ thuật (HD-0x).
