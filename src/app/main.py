"""Trang Streamlit demo bước 3.1 — chứng minh: đăng nhập (bcrypt qua
`streamlit-authenticator`, dữ liệu `users` THẬT từ MySQL "lacco") ->
hiển thị đúng vai trò (role) + phạm vi dữ liệu khách hàng được phép xem
theo RBAC Khối/Phòng/NV + A/B/C (`src/auth/scope.py`).

CHƯA dựng báo cáo thật (Kinh doanh/Chi phí/Công nợ...) — chỉ chứng minh
middleware phân quyền trả đúng phạm vi, đúng phạm vi bước 3.1 đã giao.

Theo CLAUDE.md mục 2 (tách lớp): trang này CHỈ gọi hàm từ `src/auth/` và
`src/services/`, KHÔNG tự viết SQL hay logic phân quyền tại chỗ.

Theo CLAUDE.md mục 6 (rủi ro bảo mật nghiêm trọng nhất dự án): mọi
`@st.cache_data` liên quan dữ liệu người dùng/phiên đăng nhập PHẢI nhận
tham số gắn với `user_id`/`role` — xem `_cached_data_scope` bên dưới. Toàn
bộ dữ liệu phiên đăng nhập lưu trong `st.session_state` (theo từng phiên
trình duyệt), KHÔNG dùng biến global cấp module.
"""

from __future__ import annotations

import streamlit as st
from loguru import logger

from src.auth.authentication import authenticate_and_log
from src.auth.scope import DataScope, compute_data_scope
from src.db.models.enums import CustomerClassification, UserRole
from src.services.db_connection import get_engine
from src.services.monitoring import init_sentry

# Khởi tạo Sentry TRƯỚC khi bất kỳ phần nào khác của app chạy (bước 6.3,
# HD-20) — để bắt được lỗi runtime phát sinh ngay từ các dòng đầu tiên.
init_sentry()

st.set_page_config(page_title="LACCO Dashboard — Demo RBAC (bước 3.1)", layout="wide")

_SESSION_KEY = "lacco_auth_session"


def _scope_to_plain_dict(scope: DataScope) -> dict:
    """Chuyển `DataScope` sang dict chỉ chứa kiểu builtin thuần
    (str/int/bool/None/tuple[int]) — KHÔNG còn tham chiếu instance của bất
    kỳ class tự định nghĩa nào (`DataScope`, `UserRole`,
    `CustomerClassification`). Dùng làm giá trị trả về của
    `_cached_data_scope()` — xem lý do ở docstring hàm đó."""
    return {
        "user_id": scope.user_id,
        "username": scope.username,
        "role": scope.role.value,
        "employee_id": scope.employee_id,
        "department_id": scope.department_id,
        "division_id": scope.division_id,
        "classification_hint": (
            scope.classification_hint.value
            if scope.classification_hint is not None
            else None
        ),
        "customer_ids": tuple(sorted(scope.customer_ids)),
        "unrestricted": scope.unrestricted,
        "description": scope.description,
    }


def _plain_dict_to_scope(data: dict) -> DataScope:
    """Dựng lại `DataScope` từ dict thuần do `_cached_data_scope()` trả về
    — nghịch đảo của `_scope_to_plain_dict()`."""
    classification_hint = data["classification_hint"]
    return DataScope(
        user_id=data["user_id"],
        username=data["username"],
        role=UserRole(data["role"]),
        employee_id=data["employee_id"],
        department_id=data["department_id"],
        division_id=data["division_id"],
        classification_hint=(
            CustomerClassification(classification_hint)
            if classification_hint is not None
            else None
        ),
        customer_ids=frozenset(data["customer_ids"]),
        unrestricted=data["unrestricted"],
        description=data["description"],
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_data_scope(user_id: int, role_value: str) -> dict:
    """Cache phạm vi dữ liệu, TTL 60s để giảm truy vấn khi rerun liên tục.

    BẮT BUỘC nhận `user_id` VÀ `role_value` làm tham số (CLAUDE.md mục 6)
    — Streamlit tự dùng các tham số này làm khoá cache, đảm bảo dữ liệu
    phạm vi của user A không thể trả về cho user B dù cùng chạy trên 1
    server. `role_value` là phần đệm double-check, không phải nguồn khoá
    chính (khoá chính đã là `user_id`, duy nhất theo tài khoản).

    *** TRẢ VỀ dict THUẦN, KHÔNG PHẢI `DataScope` (đã sửa, bước 7.1) ***
    `st.cache_data` dùng `pickle` để lưu/đọc lại giá trị trả về. Lỗi thật
    gặp khi test qua UI: `_pickle.PicklingError: Can't pickle <enum
    'UserRole'>: it's not the same object as src.db.models.enums.UserRole`
    — do file-watcher dev-mode của Streamlit reload lại module `src/db/
    models/enums.py` khi phát hiện file trong `src/` thay đổi trên đĩa
    (rerun sau khi sửa code khác), tạo ra 2 class `UserRole` không cùng
    identity: 1 cái nằm trong `DataScope` đã tính trước đó, 1 cái mới sau
    reload — `pickle` từ chối vì không xác định được đúng class để phục
    hồi lại khi unpickle. Đây KHÔNG phải lỗi có thể sửa bằng `hash_funcs`
    (tham số đó chỉ ảnh hưởng cách Streamlit HASH đối số đầu vào để làm
    khoá cache, không ảnh hưởng cách SERIALIZE giá trị trả về — lỗi ở đây
    xảy ra khi ghi giá trị trả về vào cache, không phải khi tính khoá).
    Cách sửa triệt để: hàm này không còn trả về instance của bất kỳ class
    tự định nghĩa nào (`DataScope`/`UserRole`/`CustomerClassification`) —
    chỉ trả `dict` gồm str/int/bool/None/tuple[int], luôn pickle được bất
    kể module có bị reload hay không. `_render_scope()` gọi
    `_plain_dict_to_scope()` để dựng lại `DataScope` thật ngay sau khi lấy
    từ cache — `DataScope` gốc trong `src/auth/scope.py` và
    `compute_data_scope()` KHÔNG đổi, các nơi khác (test, service khác)
    vẫn dùng `DataScope` như cũ.
    """
    scope = compute_data_scope(user_id, engine=get_engine())
    return _scope_to_plain_dict(scope)


def _render_login_form() -> None:
    st.subheader("Đăng nhập")
    with st.form("lacco_login_form", clear_on_submit=False):
        username = st.text_input("Tên đăng nhập")
        password = st.text_input("Mật khẩu", type="password")
        submitted = st.form_submit_button("Đăng nhập")

    # Khối xử lý này CHỈ chạy đúng 1 lần cho mỗi lần bấm nút "Đăng nhập"
    # (do st.form_submit_button chỉ True đúng trên lượt rerun ứng với cú
    # click đó) — đảm bảo authenticate_and_log() không bị gọi lặp lại qua
    # các lần rerun khác của Streamlit, tránh ghi trùng login_history.
    if submitted:
        result = authenticate_and_log(username, password)
        if result.success:
            st.session_state[_SESSION_KEY] = {
                "user_id": result.user_id,
                "username": result.username,
                "role": result.role.value,
            }
            st.rerun()
        else:
            st.error(f"Đăng nhập thất bại (lý do: {result.reason}).")
            logger.info(
                "Login form: username='{}' thất bại, reason={}",
                username,
                result.reason,
            )


def _render_scope(session: dict) -> None:
    st.success(f"Xin chào **{session['username']}** — vai trò **{session['role']}**.")

    scope = _plain_dict_to_scope(
        _cached_data_scope(session["user_id"], session["role"])
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Employee ID", scope.employee_id if scope.employee_id else "—")
    col2.metric("Department ID", scope.department_id if scope.department_id else "—")
    col3.metric("Division ID", scope.division_id if scope.division_id else "—")

    st.write(f"**Diễn giải phạm vi:** {scope.description}")

    if scope.unrestricted:
        # Chuỗi tiếng Việt dài tự nhiên, không ép xuống dòng để giữ câu
        # nguyên vẹn — noqa E501.
        st.info(
            f"Không giới hạn — tổng {len(scope.customer_ids)} khách hàng trong hệ thống."  # noqa: E501
        )
    else:
        st.write(f"**Số khách hàng được phép xem:** {len(scope.customer_ids)}")
        if scope.customer_ids:
            preview = sorted(scope.customer_ids)[:20]
            st.write(f"`customer_id` (tối đa 20 dòng đầu): {preview}")
        else:
            st.warning(
                "Phạm vi rỗng — không tìm thấy khách hàng nào thuộc phạm vi "
                "này (xem mục 'cần xác nhận' trong báo cáo bước 3.1)."
            )

    st.divider()
    if st.button("Đăng xuất"):
        del st.session_state[_SESSION_KEY]
        st.rerun()


def main() -> None:
    """Entry point trang Streamlit — điều hướng giữa form đăng nhập
    (`_render_login_form`) và màn hình hiển thị phạm vi RBAC
    (`_render_scope`) dựa trên `st.session_state[_SESSION_KEY]`."""
    st.title("LACCO Dashboard — Demo RBAC (bước 3.1)")
    st.caption(
        "Demo middleware phân quyền: đăng nhập -> hiển thị đúng vai trò + "
        "phạm vi dữ liệu được phép xem. Chưa dựng báo cáo thật."
    )

    session = st.session_state.get(_SESSION_KEY)
    if session is None:
        _render_login_form()
    else:
        _render_scope(session)


if __name__ == "__main__":
    main()
