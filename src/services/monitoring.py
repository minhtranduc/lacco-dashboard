"""Khởi tạo Sentry giám sát lỗi runtime (bước 6.3, HD-20).

Theo CLAUDE.md mục 6 (RBAC & bảo mật — app tài chính/khách hàng nội bộ):
- `send_default_pii=False` bắt buộc — không gửi thông tin định danh người
  dùng thật (IP, username...) lên Sentry SaaS.
- `include_local_variables=False` bắt buộc — tránh Sentry đính kèm biến cục
  bộ (có thể chứa DataFrame số liệu tài chính/khách hàng thật) vào traceback
  gửi lên cloud.
- `traces_sample_rate=0` — app nội bộ ~20 user, không cần performance
  tracing, tránh tốn quota free tier cho việc không cần thiết.

Bắc cầu Loguru -> Sentry — ĐÃ CHỌN CÁCH A (Loguru sink riêng), KHÔNG dùng
Cách B (propagate Loguru ngược về `logging` chuẩn để `LoggingIntegration`
của sentry-sdk tự bắt). Lý do: `sentry_sdk.integrations.logging.LoggingIntegration`
mặc định CHỈ bắt log qua module `logging` chuẩn của Python, KHÔNG tự bắt
log của Loguru (dự án dùng Loguru theo CLAUDE.md mục 4, không dùng
`logging` chuẩn ở bất kỳ đâu) — Cách B đòi hỏi thêm 1 lớp `PropagateHandler`
trung gian và tự quản lý mapping level hai chiều giữa 2 hệ thống log, dễ vỡ
khi 1 trong 2 bên đổi cấu hình sau này. Cách A đơn giản, tường minh, gọi
thẳng `sentry_sdk.capture_exception()`/`capture_message()` — dễ test độc
lập (xem `scripts/test_sentry_integration.py`).

VƯỚNG MẮC THẬT phát hiện khi test thật ở bước 6.3 (không phải lý thuyết —
xem báo cáo HD-20): `sentry-sdk` 2.69.1 (bản cài ở bước này) có sẵn
`sentry_sdk.integrations.loguru.LoguruIntegration`, và mặc định
`sentry_sdk.init(auto_enabling_integrations=True)` (giá trị mặc định) TỰ
BẬT integration này khi phát hiện package `loguru` đã cài — nghĩa là kể cả
KHÔNG viết sink riêng, sentry-sdk vẫn tự bắt log Loguru cấp ERROR+ (test
thật cho thấy 1 dòng `logger.error()` sinh RA 2 event trùng lặp trên
dashboard: 1 từ integration tự động của SDK, 1 từ sink `_sentry_loguru_sink`
tự viết bên dưới). Xử lý: khai báo `disabled_integrations=[LoguruIntegration()]`
tường minh khi `sentry_sdk.init()` để tắt hẳn integration tự động này, giữ
đúng 1 đường bắt log duy nhất (sink tự viết, Cách A) — tránh gửi trùng dữ
liệu lên Sentry (tốn quota free tier gấp đôi không cần thiết) và tránh 2
issue khác định dạng cho cùng 1 lỗi thật gây khó theo dõi trên dashboard.
"""

from __future__ import annotations

import sentry_sdk
from loguru import logger
from sentry_sdk.integrations.loguru import LoguruIntegration

from src.services.config import Settings
from src.services.config import settings as _default_settings


def _sentry_loguru_sink(message) -> None:
    """Loguru sink bắc cầu log ERROR+ sang Sentry (Cách A, xem docstring module).

    Nhận 1 `loguru.Message` (str-like, có `.record`). Nếu record có
    exception đính kèm (vd. `logger.exception(...)` hoặc
    `logger.opt(exception=True).error(...)`) thì gọi `capture_exception()`
    để giữ nguyên traceback gốc; ngược lại gọi `capture_message()` với level
    tương ứng.
    """
    record = message.record
    exception = record["exception"]
    if exception is not None and exception.value is not None:
        sentry_sdk.capture_exception(exception.value)
    else:
        sentry_sdk.capture_message(
            record["message"], level=record["level"].name.lower()
        )


def init_sentry(app_settings: Settings | None = None) -> bool:
    """Khởi tạo Sentry SDK + gắn Loguru sink bắc cầu, nếu đã có `SENTRY_DSN`.

    CHỈ init nếu `app_settings.sentry_dsn` có giá trị. Nếu không có (vd. máy
    dev chưa cấu hình `.env`), log 1 dòng cảnh báo qua Loguru và KHÔNG init,
    KHÔNG raise lỗi — giám sát lỗi là tính năng phụ trợ, không được làm sập
    app chính (CLAUDE.md mục 4, không nuốt lỗi âm thầm nhưng cũng không để
    thiếu cấu hình tuỳ chọn chặn luồng chạy chính).

    Args:
        app_settings: `Settings` cần dùng — mặc định dùng singleton
            `settings` của `src.services.config`. Tham số này tồn tại để
            script chẩn đoán (`scripts/test_sentry_integration.py`) có thể
            truyền `Settings` riêng khi cần, không bắt buộc phụ thuộc
            singleton toàn cục.

    Returns:
        `True` nếu đã init thật (có DSN), `False` nếu bỏ qua (DSN rỗng).
    """
    app_settings = app_settings or _default_settings
    if not app_settings.sentry_dsn:
        logger.warning("Sentry chưa cấu hình, bỏ qua giám sát lỗi")
        return False

    sentry_sdk.init(
        dsn=app_settings.sentry_dsn,
        environment=app_settings.app_environment,
        send_default_pii=False,
        include_local_variables=False,
        traces_sample_rate=0,
        # Tắt LoguruIntegration tự động bật sẵn của sentry-sdk — dùng đúng
        # 1 đường bắt log duy nhất là _sentry_loguru_sink bên dưới (Cách A),
        # tránh gửi trùng 2 event/lỗi lên Sentry (xem "VƯỚNG MẮC THẬT" ở
        # docstring đầu file).
        disabled_integrations=[LoguruIntegration()],
    )
    logger.add(_sentry_loguru_sink, level="ERROR")
    logger.info("Sentry đã khởi tạo, environment={}", app_settings.app_environment)
    return True
