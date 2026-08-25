"""Thao tác quản trị tài khoản qua module auth — CLAUDE.md mục 6: mọi
thao tác tạo/sửa/khoá tài khoản qua module auth PHẢI ghi `audit_log`.

Bước 3.1 chỉ cần 1 thao tác cụ thể: đặt lại mật khẩu (dùng để gán mật khẩu
test thật cho 3 tài khoản demo, xem `scripts/`). Các thao tác khác (tạo
mới/khoá tài khoản) chưa nằm trong phạm vi bước này, có thể bổ sung theo
cùng khuôn mẫu (gọi `src/services/auth_service.py`, ghi `audit_log`) khi
cần.
"""

from __future__ import annotations

from loguru import logger

from src.auth.hashing import hash_password
from src.services import auth_service
from src.services.db_connection import get_engine


def reset_user_password(
    user_id: int,
    new_plain_password: str,
    *,
    actor_user_id: int,
    engine=None,
) -> int:
    """Đặt lại mật khẩu (bcrypt, qua `streamlit_authenticator.Hasher` —
    xem `src/auth/hashing.py`) cho 1 tài khoản và ghi `audit_log`.

    KHÔNG lưu plaintext HAY bcrypt hash đầy đủ vào `audit_log.old_value`/
    `new_value` (rủi ro bảo mật nếu lộ bảng audit_log) — chỉ ghi mô tả
    ngắn không thể suy ngược ra mật khẩu.

    Parameters
    ----------
    user_id : int
        `users.id` của tài khoản cần đặt lại mật khẩu.
    new_plain_password : str
        Mật khẩu mới, dạng plaintext (sẽ được hash ngay trong hàm này).
    actor_user_id : int
        `users.id` của người/tiến trình thực hiện thao tác (ghi vào
        `audit_log.user_id` — người chịu trách nhiệm hành động, KHÔNG phải
        chủ tài khoản bị đổi mật khẩu).
    engine : sqlalchemy.Engine, optional
        Cho phép truyền engine riêng (dùng trong test).

    Returns
    -------
    int
        id của dòng `audit_log` vừa ghi.
    """
    engine = engine or get_engine()
    new_hash = hash_password(new_plain_password)
    auth_service.update_user_password_hash(engine, user_id, new_hash)
    audit_id = auth_service.record_audit_log(
        engine,
        user_id=actor_user_id,
        action="password_reset",
        table_name="users",
        record_id=user_id,
        old_value="password_hash_updated",
        new_value="password_hash_updated",
    )
    logger.info(
        "Đã đặt lại mật khẩu cho user_id={} (thực hiện bởi "
        "actor_user_id={}), audit_log id={}.",
        user_id,
        actor_user_id,
        audit_id,
    )
    return audit_id
