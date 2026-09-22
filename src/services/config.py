"""Cấu hình ứng dụng qua Pydantic Settings + python-dotenv (bước 6.3, HD-20).

LƯU Ý: trước bước này, dự án CHƯA có class Pydantic Settings nào — cấu hình
MySQL vẫn đọc trực tiếp qua `os.environ` trong `db_connection.py` (xem
`build_mysql_url()`). File này là class Pydantic Settings ĐẦU TIÊN của dự
án, tạo mới để phục vụ cấu hình Sentry (`SENTRY_DSN`, `APP_ENVIRONMENT`) —
không refactor lại `db_connection.py` sang class này (ngoài phạm vi bước
6.3, xem báo cáo HD-20).

Bổ sung `auth_cookie_key` ở bước 7.1 (test suite & security review cuối
trước go-live) — thay cho việc `src/auth/authentication.py` đọc thẳng
`os.environ.get("AUTH_COOKIE_KEY", ...)` với giá trị fallback hardcode
(rủi ro bảo mật: chuỗi cố định lộ công khai trên GitHub). Xem
`src/auth/authentication.py::_cookie_key()`.

Theo CLAUDE.md mục 2 (tách lớp): đặt tại `src/services/` theo đúng tiền lệ
đã có của `db_connection.py` (mối quan tâm hạ tầng/kết nối, không phải logic
tính KPI nghiệp vụ) — không tạo layer "core" mới ngoài 4 layer đã chốt
trong kiến trúc (mục 2 CLAUDE.md).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình đọc từ file `.env` (xem `.env.example`).

    Field dùng snake_case theo PEP8 (CLAUDE.md mục 4) — pydantic-settings
    tự map case-insensitive sang biến môi trường viết hoa (VD `SENTRY_DSN`),
    không cần khai báo alias thủ công.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sentry_dsn: str | None = None
    app_environment: str = "development"
    auth_cookie_key: str | None = None


settings = Settings()
