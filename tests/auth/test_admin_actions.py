"""Test `src/auth/admin_actions.py::reset_user_password()` — CLAUDE.md
mục 6: mọi thay đổi dữ liệu qua module auth phải ghi `audit_log`, mật
khẩu dùng bcrypt. Dùng fixture `db_engine` (SQLite in-memory, xem
`tests/conftest.py`) — KHÔNG kết nối MySQL "lacco" thật, seed riêng 2
user (actor/admin và target) trong file này, cùng khuôn mẫu `_seed_user`
của `tests/auth/test_authentication.py`.

Trọng tâm test: (1) mật khẩu mới thực sự hoạt động (verify_password trả
True với hash mới), (2) `audit_log` ghi đúng `user_id=actor_user_id` (KHÔNG
phải `record_id` — chủ tài khoản bị đổi mật khẩu), (3) `old_value`/
`new_value` KHÔNG BAO GIỜ chứa plaintext hay bcrypt hash đầy đủ — chỉ chứa
placeholder cố định `"password_hash_updated"` đúng như docstring của
`reset_user_password()` yêu cầu.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.admin_actions import reset_user_password
from src.auth.hashing import hash_password, verify_password
from src.db.models.enums import UserRole
from src.db.models.security import AuditLog, User

ACTOR_PLAIN_PASSWORD = "mat-khau-actor-123"
TARGET_PLAIN_PASSWORD = "mat-khau-cu-123"
NEW_PLAIN_PASSWORD = "mat-khau-moi-123"


def _seed_user(engine, *, username: str, plain_password: str) -> int:
    """Tạo 1 user thật (bcrypt hash qua `hash_password`) — cùng khuôn mẫu
    `_seed_user` của `tests/auth/test_authentication.py`."""
    with Session(engine) as session:
        user = User(
            username=username,
            password_hash=hash_password(plain_password),
            role=UserRole.USER,
            employee_id=None,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def _get_user(engine, user_id: int) -> User:
    with Session(engine) as session:
        user = session.get(User, user_id)
        assert user is not None
        session.expunge(user)
        return user


def _audit_log_rows(engine) -> list[AuditLog]:
    with Session(engine) as session:
        stmt = select(AuditLog)
        return list(session.execute(stmt).scalars().all())


def test_reset_password_updates_hash_and_new_password_verifies(db_engine):
    """Hash mật khẩu trong DB phải đổi khác giá trị cũ, VÀ mật khẩu mới
    phải thực sự dùng đăng nhập được (verify_password trả True)."""
    actor_id = _seed_user(
        db_engine, username="actor1", plain_password=ACTOR_PLAIN_PASSWORD
    )
    target_id = _seed_user(
        db_engine, username="target1", plain_password=TARGET_PLAIN_PASSWORD
    )
    old_hash = _get_user(db_engine, target_id).password_hash

    reset_user_password(
        target_id,
        NEW_PLAIN_PASSWORD,
        actor_user_id=actor_id,
        engine=db_engine,
    )

    new_hash = _get_user(db_engine, target_id).password_hash
    assert new_hash != old_hash
    assert verify_password(NEW_PLAIN_PASSWORD, new_hash) is True
    assert verify_password(TARGET_PLAIN_PASSWORD, new_hash) is False


def test_reset_password_writes_single_audit_log_with_actor_as_user_id(db_engine):
    """`audit_log.user_id` phải là actor (người thực hiện), KHÔNG phải
    target (chủ tài khoản bị đổi mật khẩu) — đúng docstring
    `reset_user_password()`. `record_id` phải là target."""
    actor_id = _seed_user(
        db_engine, username="actor2", plain_password=ACTOR_PLAIN_PASSWORD
    )
    target_id = _seed_user(
        db_engine, username="target2", plain_password=TARGET_PLAIN_PASSWORD
    )
    assert actor_id != target_id

    reset_user_password(
        target_id,
        NEW_PLAIN_PASSWORD,
        actor_user_id=actor_id,
        engine=db_engine,
    )

    rows = _audit_log_rows(db_engine)
    assert len(rows) == 1
    entry = rows[0]
    assert entry.user_id == actor_id
    assert entry.action == "password_reset"
    assert entry.table_name == "users"
    assert entry.record_id == target_id


def test_reset_password_audit_log_never_stores_plaintext_or_full_hash(db_engine):
    """Yêu cầu bảo mật tường minh trong docstring `reset_user_password()`:
    KHÔNG lưu plaintext HAY bcrypt hash đầy đủ vào `old_value`/`new_value`
    — chỉ ghi placeholder cố định `"password_hash_updated"`."""
    actor_id = _seed_user(
        db_engine, username="actor3", plain_password=ACTOR_PLAIN_PASSWORD
    )
    target_id = _seed_user(
        db_engine, username="target3", plain_password=TARGET_PLAIN_PASSWORD
    )
    old_hash = _get_user(db_engine, target_id).password_hash

    reset_user_password(
        target_id,
        NEW_PLAIN_PASSWORD,
        actor_user_id=actor_id,
        engine=db_engine,
    )

    new_hash = _get_user(db_engine, target_id).password_hash
    entry = _audit_log_rows(db_engine)[0]

    for field_value in (entry.old_value, entry.new_value):
        assert field_value is not None
        assert NEW_PLAIN_PASSWORD not in field_value
        assert TARGET_PLAIN_PASSWORD not in field_value
        assert old_hash not in field_value
        assert new_hash not in field_value

    assert entry.old_value == "password_hash_updated"
    assert entry.new_value == "password_hash_updated"


def test_reset_password_returns_id_matching_persisted_audit_log(db_engine):
    """Giá trị `int` trả về từ `reset_user_password()` phải khớp đúng
    `audit_log.id` đã ghi thật trong DB."""
    actor_id = _seed_user(
        db_engine, username="actor4", plain_password=ACTOR_PLAIN_PASSWORD
    )
    target_id = _seed_user(
        db_engine, username="target4", plain_password=TARGET_PLAIN_PASSWORD
    )

    returned_id = reset_user_password(
        target_id,
        NEW_PLAIN_PASSWORD,
        actor_user_id=actor_id,
        engine=db_engine,
    )

    entry = _audit_log_rows(db_engine)[0]
    assert returned_id == entry.id


def test_reset_own_password_self_service_logs_user_id_equals_record_id(db_engine):
    """Ca actor_user_id == user_id (tự đổi mật khẩu của chính mình) — code
    hiện tại không cấm trường hợp này, vẫn phải hash/ghi audit_log đúng,
    với `user_id == record_id` trong dòng audit_log ghi ra."""
    self_id = _seed_user(
        db_engine, username="selfservice1", plain_password=TARGET_PLAIN_PASSWORD
    )

    returned_id = reset_user_password(
        self_id,
        NEW_PLAIN_PASSWORD,
        actor_user_id=self_id,
        engine=db_engine,
    )

    new_hash = _get_user(db_engine, self_id).password_hash
    assert verify_password(NEW_PLAIN_PASSWORD, new_hash) is True

    entry = _audit_log_rows(db_engine)[0]
    assert returned_id == entry.id
    assert entry.user_id == self_id
    assert entry.record_id == self_id
