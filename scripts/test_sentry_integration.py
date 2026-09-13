"""Script CHẨN ĐOÁN xác minh Sentry đã hoạt động thật — bước 6.3, HD-20.

KHÔNG phải code sản phẩm (giống `scripts/load_test_services.py` ở bước
6.2) — chỉ dùng để tự kiểm tra bằng tay: init Sentry đúng cấu hình chốt
trong CLAUDE.md mục 6, sau đó (1) cố tình raise 1 exception thật và gọi
`sentry_sdk.capture_exception()`, (2) log 1 dòng ERROR qua Loguru để test
cầu nối Loguru -> Sentry (Cách A, xem `src/services/monitoring.py`).

KHÔNG để lại route/nút "trigger lỗi test" nào trong UI Streamlit thật —
script này chạy rời qua CLI, không import bởi `src/app/`.

Cách dùng: `python scripts/test_sentry_integration.py` (từ thư mục gốc
repo, cần `.env` đã có `SENTRY_DSN` thật trỏ tới project Sentry đã tạo).
Sau khi chạy, vào dashboard sentry.io kiểm tra 2 event vừa gửi xuất hiện
trong mục Issues của project.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sentry_sdk
from loguru import logger

from src.services.config import settings
from src.services.monitoring import init_sentry


def _test_capture_exception() -> None:
    """Cố tình raise 1 exception thật, bắt trong try/except, gửi thủ công."""
    try:
        raise ValueError(
            "[test_sentry_integration] Lỗi thử nghiệm bước 6.3/HD-20 — "
            "xác minh sentry_sdk.capture_exception() hoạt động thật."
        )
    except ValueError:
        event_id = sentry_sdk.capture_exception()
        logger.info("capture_exception() đã gửi, event_id={}", event_id)


def _test_loguru_bridge() -> None:
    """Log 1 dòng ERROR qua Loguru, xác minh cầu nối sang Sentry (Cách A)."""
    logger.error(
        "[test_sentry_integration] Lỗi thử nghiệm bước 6.3/HD-20 — xác minh "
        "cầu nối Loguru -> Sentry (Cách A, xem src/services/monitoring.py)."
    )


def main() -> None:
    if not settings.sentry_dsn:
        logger.error(
            "SENTRY_DSN chưa cấu hình trong .env — không thể chạy script "
            "xác minh này. Thêm SENTRY_DSN=<dsn thật> vào .env rồi chạy lại."
        )
        sys.exit(1)

    initialized = init_sentry()
    logger.info("init_sentry() trả về: {}", initialized)

    _test_capture_exception()
    _test_loguru_bridge()

    # Sentry SDK gửi event bất đồng bộ (background thread) — flush() chặn
    # tới khi gửi xong hoặc hết timeout, để chắc chắn 2 event trên đã rời
    # máy trước khi script kết thúc (không chỉ nằm trong buffer nội bộ).
    sentry_sdk.flush(timeout=10)
    logger.info(
        "Đã flush Sentry client (timeout=10s) — kiểm tra dashboard sentry.io "
        "mục Issues của project để xác nhận 2 event thử nghiệm đã xuất hiện."
    )


if __name__ == "__main__":
    main()
