"""Test `src/services/monitoring.py` — CHỈ nhánh KHÔNG có `SENTRY_DSN`
(bước 6.3, HD-20).

Phạm vi test này CỐ Ý giới hạn: KHÔNG test việc gửi event thật lên Sentry
(gọi `sentry_sdk.init()` với DSN thật/giả rồi bắn log) — việc đó đã được
xác minh thật thủ công ở bước 6.3 (xem báo cáo HD-20, mục "VƯỚNG MẮC THẬT"
trong docstring đầu `src/services/monitoring.py`: phát hiện + xử lý xong
vụ trùng event do `LoguruIntegration` tự động bật). Viết lại test tự động
gọi Sentry thật ở đây sẽ tốn quota Sentry SaaS free tier (CLAUDE.md mục 3)
một cách không cần thiết cho việc chỉ xác nhận lại điều đã biết.

Theo CLAUDE.md mục 3 (Sentry SaaS free tier, `send_default_pii=False`/
`include_local_variables=False`/`traces_sample_rate=0` bắt buộc, tắt tường
minh `LoguruIntegration` tự động) — 3 tham số bảo mật này chỉ áp dụng khi
thật sự gọi `sentry_sdk.init()`, tức nhánh CÓ DSN, nằm ngoài phạm vi test
này.

Mọi test bên dưới LUÔN truyền `Settings` tường minh
(`Settings(sentry_dsn=None, app_environment="test")`) cho `init_sentry()`,
đúng theo mục đích tham số `app_settings` đã ghi trong docstring của hàm
(dùng cho "script chẩn đoán... có thể truyền Settings riêng khi cần, không
bắt buộc phụ thuộc singleton toàn cục") — KHÔNG gọi `init_sentry()` không
tham số, vì mặc định sẽ rơi về singleton `settings` đọc `.env` thật lúc
import, phụ thuộc vào trạng thái `SENTRY_DSN` trên từng máy dev (không
hermetic, có thể pass/fail khác nhau tuỳ máy).
"""

from __future__ import annotations

from unittest.mock import patch

from src.services.config import Settings
from src.services.monitoring import init_sentry


def test_init_sentry_returns_false_when_dsn_none():
    """`sentry_dsn=None` -> `init_sentry()` phải trả về `False` (bỏ qua,
    không init), đúng hợp đồng ghi trong docstring của hàm."""
    test_settings = Settings(sentry_dsn=None, app_environment="test")

    result = init_sentry(test_settings)

    assert result is False


def test_init_sentry_returns_false_when_dsn_empty_string():
    """`sentry_dsn=""` (chuỗi rỗng, giá trị falsy) cũng phải bị coi như
    "chưa cấu hình" -> trả về `False`, giống hệt trường hợp `None`."""
    test_settings = Settings(sentry_dsn="", app_environment="test")

    result = init_sentry(test_settings)

    assert result is False


def test_init_sentry_does_not_call_sentry_sdk_init_when_no_dsn():
    """Khi không có DSN, `sentry_sdk.init()` KHÔNG được gọi.

    Dùng `unittest.mock.patch` để mock chính xác lệnh gọi
    `src.services.monitoring.sentry_sdk.init` — phạm vi mock hẹp, chỉ nhằm
    xác nhận hàm không hề chạm tới Sentry SDK ở nhánh này (không gọi mạng
    thật lên sentry.io), không thay thế cho việc test nhánh có DSN (nằm
    ngoài phạm vi, xem docstring module).
    """
    test_settings = Settings(sentry_dsn=None, app_environment="test")

    with patch("src.services.monitoring.sentry_sdk.init") as mock_init:
        init_sentry(test_settings)

    mock_init.assert_not_called()


def test_init_sentry_does_not_raise_when_no_dsn():
    """Hàm phải "KHÔNG raise lỗi" (đúng hợp đồng docstring) khi thiếu DSN —
    giám sát lỗi là tính năng phụ trợ, không được làm sập luồng chạy chính
    (CLAUDE.md mục 4)."""
    test_settings = Settings(sentry_dsn=None, app_environment="test")

    try:
        init_sentry(test_settings)
    except Exception as exc:  # noqa: BLE001 - test này cố ý bắt mọi lỗi
        raise AssertionError(
            f"init_sentry() không được raise lỗi khi thiếu DSN, nhưng đã raise: {exc!r}"
        ) from exc
