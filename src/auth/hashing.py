"""Băm/kiểm tra mật khẩu — BẮT BUỘC dùng bcrypt qua `streamlit-authenticator`
(CLAUDE.md mục 3 & 6). KHÔNG tự viết thuật toán hash riêng, KHÔNG đổi sang
thư viện auth khác.

Module này chỉ bọc lại 2 hàm tĩnh của `streamlit_authenticator.Hasher`
(bản thân `Hasher` dùng `bcrypt.hashpw`/`bcrypt.checkpw` bên trong — xem
`streamlit_authenticator/utilities/hasher.py` trong site-packages) để phần
còn lại của `src/auth/` và `src/services/` không phải import trực tiếp
`streamlit_authenticator` ở nhiều nơi, và để có 1 điểm duy nhất nếu sau
này cần đổi tham số hash (vd. bcrypt cost factor).
"""

from __future__ import annotations

from streamlit_authenticator import Hasher


def hash_password(plain_password: str) -> str:
    """Băm mật khẩu plaintext bằng bcrypt (qua `streamlit_authenticator.Hasher`).

    Parameters
    ----------
    plain_password : str
        Mật khẩu dạng plaintext.

    Returns
    -------
    str
        Chuỗi bcrypt hash (dạng `$2b$...`).
    """
    return Hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Kiểm tra mật khẩu plaintext có khớp với bcrypt hash đã lưu hay không.

    Parameters
    ----------
    plain_password : str
        Mật khẩu người dùng nhập vào lúc đăng nhập.
    password_hash : str
        Bcrypt hash đang lưu trong `users.password_hash`.

    Returns
    -------
    bool
        True nếu khớp, False nếu sai mật khẩu.
    """
    return Hasher.check_pw(plain_password, password_hash)
