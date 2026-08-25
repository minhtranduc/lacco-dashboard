"""Module đăng nhập — CLAUDE.md mục 3 & 6: mật khẩu bcrypt bắt buộc qua
`streamlit-authenticator`, đọc thông tin từ bảng `users` THẬT trong MySQL
"lacco" (KHÔNG hardcode danh sách user trong code). Mọi lần đăng nhập,
thành công lẫn thất bại, đều ghi `login_history`.

*** QUYẾT ĐỊNH THIẾT KẾ (ghi rõ để tránh hiểu nhầm khi đọc lại sau này) ***
`streamlit_authenticator.Authenticate.login()` là widget UI tự vẽ form và
tự quản lý `st.session_state` nội bộ; callback công khai của nó CHỈ được
gọi khi đăng nhập THÀNH CÔNG (xem `AuthenticationModel.login` trong
`site-packages/streamlit_authenticator/models/authentication_model.py`) —
không có hook công khai an toàn để ghi log mỗi lần đăng nhập THẤT BẠI mà
không bị double-log qua các lần Streamlit rerun lại script. Vì yêu cầu bắt
buộc "mọi lần đăng nhập kể cả thất bại phải ghi login_history" (CLAUDE.md
mục 6), module này cung cấp 2 phần:

  1. `build_credentials()` / `get_authenticator()` — dựng `credentials`
     dict THẬT từ bảng `users` và trả về `Authenticate` instance chuẩn của
     thư viện, để trang nào cần widget/cookie-persistent-session đầy đủ
     của `streamlit-authenticator` có thể dùng trực tiếp.
  2. `authenticate_and_log()` — hàm xác thực chính, dùng để gọi bên trong
     1 `st.form` tự viết ở `src/app/main.py` (đảm bảo chỉ chạy đúng 1 lần
     mỗi lần bấm nút đăng nhập, không phụ thuộc vòng đời widget nội bộ của
     thư viện). Hàm này vẫn kiểm tra mật khẩu bằng
     `streamlit_authenticator.Hasher.check_pw` (bcrypt, qua
     `src/auth/hashing.verify_password`) — KHÔNG tự viết hàm hash/so sánh
     mật khẩu riêng, đúng CLAUDE.md mục 3 & 6.

Giới hạn đã biết: nếu `username` không tồn tại trong bảng `users`, KHÔNG
thể ghi vào `login_history` (cột `user_id` là FK NOT NULL, không có user
hợp lệ để tham chiếu) — trường hợp này chỉ log qua Loguru, không ghi DB.
Đây là giới hạn của schema hiện tại (ERD đã chốt ở Tuần 2), không phải bug
— xem mục "cần xác nhận" trong báo cáo bước 3.1.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit_authenticator as stauth
from loguru import logger

from src.auth.hashing import verify_password
from src.db.models.enums import UserRole
from src.services import auth_service
from src.services.db_connection import get_engine

COOKIE_NAME = "lacco_dashboard_auth"
# Cookie key mặc định CHỈ dùng cho môi trường dev/demo cục bộ. Nếu triển
# khai thật, đặt biến môi trường AUTH_COOKIE_KEY trong .env — KHÔNG tự ý
# thêm biến này vào .env trong phạm vi bước 3.1 (ngoài phạm vi nhiệm vụ đã
# giao, xem chỉ dẫn "KHÔNG tự ý đổi .env").
_DEV_FALLBACK_COOKIE_KEY = "lacco-dashboard-dev-only-cookie-key"


def _cookie_key() -> str:
    return os.environ.get("AUTH_COOKIE_KEY", _DEV_FALLBACK_COOKIE_KEY)


def build_credentials(engine=None) -> dict:
    """Dựng dict `credentials` cho `streamlit_authenticator.Authenticate`
    TỪ dữ liệu thật trong bảng `users` (join `employee` lấy tên hiển
    thị). Chỉ gồm user `is_active=True`.
    """
    engine = engine or get_engine()
    rows = auth_service.fetch_users_for_credentials(engine)
    usernames: dict[str, dict] = {}
    for row in rows:
        usernames[row["username"]] = {
            "name": row["full_name"] or row["username"],
            # password_hash trong DB đã là bcrypt hash sẵn (tính lúc tạo
            # user, qua src/auth/hashing.py) -> auto_hash=False khi khởi
            # tạo Authenticate để KHÔNG hash lại lần 2.
            "password": row["password_hash"],
            "roles": [row["role"]],
        }
    return {"usernames": usernames}


def get_authenticator(engine=None) -> stauth.Authenticate:
    """Trả về `Authenticate` instance dựng từ dữ liệu `users` thật trong
    MySQL "lacco". `auto_hash=False` vì `password_hash` đã là bcrypt hash
    sẵn từ DB (tránh hash lại 2 lần).
    """
    credentials = build_credentials(engine)
    return stauth.Authenticate(
        credentials,
        cookie_name=COOKIE_NAME,
        cookie_key=_cookie_key(),
        cookie_expiry_days=1,
        auto_hash=False,
    )


@dataclass(frozen=True)
class AuthResult:
    """Kết quả 1 lần thử đăng nhập."""

    success: bool
    user_id: int | None
    username: str
    role: UserRole | None
    reason: str
    login_history_id: int | None


def authenticate_and_log(
    username: str,
    password: str,
    *,
    ip_address: str | None = None,
    engine=None,
) -> AuthResult:
    """Xác thực 1 lần đăng nhập và ghi `login_history` (CLAUDE.md mục 6 —
    ghi MỌI lần đăng nhập, kể cả thất bại).

    Mật khẩu được kiểm tra bằng `streamlit_authenticator.Hasher.check_pw`
    (bcrypt) qua `src/auth/hashing.verify_password` — KHÔNG tự viết hàm
    hash/so sánh mật khẩu riêng.

    Parameters
    ----------
    username : str
        Tên đăng nhập người dùng nhập (sẽ được `.strip().lower()`, cùng
        quy ước với `streamlit_authenticator`).
    password : str
        Mật khẩu plaintext người dùng nhập.
    ip_address : str, optional
        IP nguồn của lần đăng nhập (nếu xác định được).
    engine : sqlalchemy.Engine, optional
        Cho phép truyền engine riêng (dùng trong test).

    Returns
    -------
    AuthResult
        Kết quả xác thực, gồm cả `login_history_id` đã ghi (None nếu
        username không tồn tại — xem giới hạn ở docstring module).
    """
    engine = engine or get_engine()
    username_norm = username.strip().lower()
    user = auth_service.fetch_user_by_username(engine, username_norm)

    if user is None:
        logger.warning(
            "Đăng nhập thất bại: username='{}' không tồn tại trong bảng "
            "users -> KHÔNG ghi được login_history (không có user_id hợp "
            "lệ để tham chiếu FK NOT NULL).",
            username_norm,
        )
        return AuthResult(
            success=False,
            user_id=None,
            username=username_norm,
            role=None,
            reason="username_not_found",
            login_history_id=None,
        )

    role = UserRole(user["role"])

    if not user["is_active"]:
        history_id = auth_service.record_login_history(
            engine, user["id"], success=False, ip_address=ip_address
        )
        logger.warning(
            "Đăng nhập thất bại: user_id={} username='{}' đã bị khoá "
            "(is_active=False).",
            user["id"],
            username_norm,
        )
        return AuthResult(
            success=False,
            user_id=user["id"],
            username=username_norm,
            role=role,
            reason="account_inactive",
            login_history_id=history_id,
        )

    password_ok = verify_password(password, user["password_hash"])
    history_id = auth_service.record_login_history(
        engine, user["id"], success=password_ok, ip_address=ip_address
    )

    if not password_ok:
        logger.warning(
            "Đăng nhập thất bại: user_id={} username='{}' sai mật khẩu.",
            user["id"],
            username_norm,
        )
        return AuthResult(
            success=False,
            user_id=user["id"],
            username=username_norm,
            role=role,
            reason="wrong_password",
            login_history_id=history_id,
        )

    logger.info(
        "Đăng nhập thành công: user_id={} username='{}' role={}.",
        user["id"],
        username_norm,
        role.value,
    )
    return AuthResult(
        success=True,
        user_id=user["id"],
        username=username_norm,
        role=role,
        reason="ok",
        login_history_id=history_id,
    )
