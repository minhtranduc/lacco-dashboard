"""Kết nối MySQL dùng chung cho các service trong `src/services/`.

Tái sử dụng ĐÚNG cách build connection string đã có ở `migrations/env.py`:
đọc cấu hình qua `python-dotenv` (KHÔNG hardcode giá trị `.env` vào code),
escape mật khẩu bằng `urllib.parse.quote_plus` (mật khẩu MySQL thật hiện tại
có chứa ký tự `@`, nếu không escape sẽ làm sai cấu trúc URL kết nối).

Theo CLAUDE.md mục 2 (tách lớp): module này thuộc `src/services/`, không
thuộc `src/db/` (nơi đó chỉ chứa SQLAlchemy model, không được import
pandas/openpyxl/logic kết nối).
"""

from __future__ import annotations

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import Engine, create_engine

_REQUIRED_ENV_VARS = (
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
)

# Cache engine ở cấp module để không tạo lại connection pool mỗi lần gọi —
# đây KHÔNG phải biến global chứa dữ liệu nghiệp vụ (không vi phạm CLAUDE.md
# mục 6, quy tắc đó áp dụng cho cache Streamlit theo user/role).
_engine: Engine | None = None


def build_mysql_url() -> str:
    """Dựng connection string MySQL từ biến môi trường (`.env`).

    Đọc qua `python-dotenv`, escape mật khẩu bằng `quote_plus` để chịu được
    ký tự đặc biệt (VD `@`) trong mật khẩu thật — giống cách làm ở
    `migrations/env.py`.

    Raises:
        RuntimeError: nếu thiếu bất kỳ biến môi trường bắt buộc nào trong
            `.env` — báo lỗi rõ ràng thay vì để KeyError mù mờ (CLAUDE.md
            mục 4, không nuốt lỗi âm thầm).
    """
    load_dotenv()
    missing = [v for v in _REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            "Thiếu biến môi trường bắt buộc trong .env để kết nối MySQL: "
            f"{', '.join(missing)}. Kiểm tra lại file .env (xem mẫu ở "
            ".env.example)."
        )
    return (
        f"mysql+mysqlconnector://{quote_plus(os.environ['MYSQL_USER'])}:"
        f"{quote_plus(os.environ['MYSQL_PASSWORD'])}@"
        f"{os.environ['MYSQL_HOST']}:{os.environ['MYSQL_PORT']}/"
        f"{os.environ['MYSQL_DATABASE']}"
    )


def get_engine(*, echo: bool = False, force_new: bool = False) -> Engine:
    """Trả về SQLAlchemy Engine dùng chung (cached) kết nối tới MySQL "lacco".

    Args:
        echo: bật log SQL statement (dùng khi debug).
        force_new: bỏ qua cache, tạo Engine mới (dùng trong test).
    """
    global _engine
    if _engine is not None and not force_new:
        return _engine
    url = build_mysql_url()
    logger.debug(
        "Khởi tạo SQLAlchemy engine tới MySQL host={} db={}",
        os.environ.get("MYSQL_HOST"),
        os.environ.get("MYSQL_DATABASE"),
    )
    _engine = create_engine(url, echo=echo, pool_pre_ping=True)
    return _engine
