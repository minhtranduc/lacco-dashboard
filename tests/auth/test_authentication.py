"""Test `src/auth/authentication.py::authenticate_and_log()` — CLAUDE.md
mục 6: mọi lần đăng nhập (thành công lẫn thất bại) phải ghi
`login_history`. Dùng fixture `db_engine` (SQLite in-memory, xem
`tests/conftest.py`) — KHÔNG kết nối MySQL "lacco" thật, seed riêng 1 user
đơn giản trong file này (không cần `seeded_scope_data`, không liên quan
RBAC theo Khối/Phòng)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import src.auth.authentication as authentication_module
from src.auth.authentication import _cookie_key, authenticate_and_log
from src.auth.hashing import hash_password
from src.db.models.enums import UserRole
from src.db.models.security import LoginHistory, User
from src.services.config import Settings

PLAIN_PASSWORD = "mat-khau-test-123"


def _seed_user(engine) -> int:
    with Session(engine) as session:
        user = User(
            username="testuser",
            password_hash=hash_password(PLAIN_PASSWORD),
            role=UserRole.USER,
            employee_id=None,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def _login_history_rows(engine, user_id: int) -> list[LoginHistory]:
    with Session(engine) as session:
        stmt = select(LoginHistory).where(LoginHistory.user_id == user_id)
        return list(session.execute(stmt).scalars().all())


def test_correct_password_succeeds_and_logs_success(db_engine):
    user_id = _seed_user(db_engine)

    result = authenticate_and_log("testuser", PLAIN_PASSWORD, engine=db_engine)

    assert result.success is True
    assert result.user_id == user_id
    assert result.role == UserRole.USER

    rows = _login_history_rows(db_engine, user_id)
    assert len(rows) == 1
    assert rows[0].success is True


def test_wrong_password_fails_and_logs_failure(db_engine):
    user_id = _seed_user(db_engine)

    result = authenticate_and_log("testuser", "mat-khau-sai", engine=db_engine)

    assert result.success is False
    assert result.reason == "wrong_password"

    rows = _login_history_rows(db_engine, user_id)
    assert len(rows) == 1
    assert rows[0].success is False


def test_unknown_username_fails_without_login_history(db_engine):
    _seed_user(db_engine)

    result = authenticate_and_log("khong-ton-tai", "mat-khau-bat-ky", engine=db_engine)

    assert result.success is False
    assert result.reason == "username_not_found"
    assert result.login_history_id is None


@pytest.fixture(autouse=True)
def _reset_dev_cookie_key_cache():
    """`_cookie_key()` cache `_dev_cookie_key_cache` ở cấp module (sinh
    đúng 1 lần/tiến trình cho nhánh dev — xem docstring hàm). Reset về
    `None` trước VÀ sau mỗi test trong file này để các test không rò rỉ
    trạng thái cache cho nhau (test A sinh key ngẫu nhiên, test B kỳ vọng
    "sinh mới" sẽ vô tình thấy cache của test A nếu không reset)."""
    authentication_module._dev_cookie_key_cache = None
    yield
    authentication_module._dev_cookie_key_cache = None


def test_cookie_key_uses_configured_value_when_present():
    """Nhánh 1: `settings.auth_cookie_key` có giá trị -> dùng trực tiếp,
    không sinh ngẫu nhiên, không quan tâm `app_environment`."""
    settings = Settings(auth_cookie_key="key-tu-env-that", app_environment="production")

    assert _cookie_key(settings) == "key-tu-env-that"


def test_cookie_key_raises_when_missing_in_production():
    """Nhánh 2: thiếu `auth_cookie_key` VÀ `app_environment="production"`
    -> từ chối khởi động bằng `RuntimeError` rõ ràng, KHÔNG được âm thầm
    chạy với key rỗng/công khai trên production."""
    settings = Settings(auth_cookie_key=None, app_environment="production")

    with pytest.raises(RuntimeError, match="AUTH_COOKIE_KEY"):
        _cookie_key(settings)


def test_cookie_key_generates_random_value_in_dev_when_missing():
    """Nhánh 3: thiếu `auth_cookie_key` VÀ môi trường khác "production"
    (dev/demo) -> sinh ngẫu nhiên bằng `secrets.token_hex(32)` (64 ký tự
    hex), KHÔNG còn là chuỗi hardcode cố định như trước bước 7.1."""
    settings = Settings(auth_cookie_key=None, app_environment="development")

    key = _cookie_key(settings)

    assert key != "lacco-dashboard-dev-only-cookie-key"  # chuỗi hardcode cũ
    assert len(key) == 64
    int(key, 16)  # phải là hex hợp lệ (token_hex) - raise ValueError nếu không


def test_cookie_key_dev_value_is_cached_per_process():
    """Nhánh 3 (tiếp): trong CÙNG 1 tiến trình, gọi `_cookie_key()` nhiều
    lần với cùng cấu hình dev PHẢI trả về CÙNG 1 giá trị đã sinh trước đó
    (cache `_dev_cookie_key_cache`) — nếu không, cookie sẽ mất hiệu lực
    ngay giữa các lần rerun của Streamlit trong cùng 1 process, không chỉ
    khi restart hẳn process."""
    settings = Settings(auth_cookie_key=None, app_environment="development")

    first_call = _cookie_key(settings)
    second_call = _cookie_key(settings)

    assert first_call == second_call


def test_cookie_key_dev_value_differs_across_simulated_process_restarts():
    """Nhánh 3 (tiếp): mô phỏng "restart process" bằng cách reset cache về
    `None` giữa 2 lần gọi -> key sinh ra lần 2 PHẢI khác lần 1 (đúng yêu
    cầu "sinh ngẫu nhiên mỗi lần chạy process", không phải 1 chuỗi cố định
    dùng lại mãi mãi)."""
    settings = Settings(auth_cookie_key=None, app_environment="development")

    first_key = _cookie_key(settings)
    authentication_module._dev_cookie_key_cache = None  # mô phỏng restart
    second_key = _cookie_key(settings)

    assert first_key != second_key
