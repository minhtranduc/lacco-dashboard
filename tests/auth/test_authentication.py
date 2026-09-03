"""Test `src/auth/authentication.py::authenticate_and_log()` — CLAUDE.md
mục 6: mọi lần đăng nhập (thành công lẫn thất bại) phải ghi
`login_history`. Dùng fixture `db_engine` (SQLite in-memory, xem
`tests/conftest.py`) — KHÔNG kết nối MySQL "lacco" thật, seed riêng 1 user
đơn giản trong file này (không cần `seeded_scope_data`, không liên quan
RBAC theo Khối/Phòng)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.authentication import authenticate_and_log
from src.auth.hashing import hash_password
from src.db.models.enums import UserRole
from src.db.models.security import LoginHistory, User

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
