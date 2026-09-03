"""Truy vấn DB phục vụ tầng auth (`src/auth/`).

Theo CLAUDE.md mục 2 (tách lớp): logic xác thực/RBAC nằm ở `src/auth/`,
module NÀY chỉ chứa truy vấn DB thật (SQLAlchemy, parameterized — cấm nối
chuỗi SQL thủ công theo CLAUDE.md mục 4) mà `src/auth/` gọi sang khi cần.

Không có logic nghiệp vụ/quyết định RBAC ở đây — chỉ đọc/ghi dữ liệu thô.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, Select, select, union
from sqlalchemy.orm import Session

from src.db.models import (
    AuditLog,
    Customer,
    Debt,
    Department,
    Employee,
    LoginHistory,
    PriceRequest,
    SalesOrder,
    User,
)


def _role_value(role: Any) -> str:
    """`User.role` trả về `UserRole` enum member khi query qua ORM — hàm
    này chuẩn hoá về string để dùng trong credentials dict/so sánh."""
    return role.value if hasattr(role, "value") else role


def fetch_users_for_credentials(engine: Engine) -> list[dict[str, Any]]:
    """Lấy các tài khoản ĐANG ACTIVE để dựng `credentials` dict cho
    `streamlit_authenticator.Authenticate` (chỉ phục vụ widget UI đầy đủ
    của thư viện — xem `src/auth/authentication.py`). Hàm xác thực chính
    `authenticate_and_log` KHÔNG dùng hàm này — nó tự truy vấn
    `fetch_user_by_username` không lọc `is_active` để còn phân biệt lý do
    thất bại (tài khoản bị khoá vs sai mật khẩu).
    """
    with Session(engine) as session:
        stmt = (
            select(
                User.id,
                User.username,
                User.password_hash,
                User.role,
                User.employee_id,
                User.is_active,
                Employee.full_name,
            )
            .outerjoin(Employee, User.employee_id == Employee.id)
            .where(User.is_active.is_(True))
        )
        rows = session.execute(stmt).all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "password_hash": r.password_hash,
            "role": _role_value(r.role),
            "employee_id": r.employee_id,
            "is_active": r.is_active,
            "full_name": r.full_name,
        }
        for r in rows
    ]


def fetch_user_by_username(engine: Engine, username: str) -> dict[str, Any] | None:
    """Tìm 1 user theo `username` (so khớp chính xác — `src/auth/` chịu
    trách nhiệm chuẩn hoá `.strip().lower()` trước khi gọi, giống quy ước
    của `streamlit_authenticator`)."""
    with Session(engine) as session:
        stmt = select(
            User.id,
            User.username,
            User.password_hash,
            User.role,
            User.employee_id,
            User.is_active,
        ).where(User.username == username)
        row = session.execute(stmt).first()
    if row is None:
        return None
    return {
        "id": row.id,
        "username": row.username,
        "password_hash": row.password_hash,
        "role": _role_value(row.role),
        "employee_id": row.employee_id,
        "is_active": row.is_active,
    }


def fetch_user_by_id(engine: Engine, user_id: int) -> dict[str, Any] | None:
    """Tìm 1 user theo `id` — dùng trong `src/auth/scope.py` để tính phạm
    vi dữ liệu từ user đang đăng nhập (đọc từ `st.session_state`)."""
    with Session(engine) as session:
        stmt = select(
            User.id, User.username, User.role, User.employee_id, User.is_active
        ).where(User.id == user_id)
        row = session.execute(stmt).first()
    if row is None:
        return None
    return {
        "id": row.id,
        "username": row.username,
        "role": _role_value(row.role),
        "employee_id": row.employee_id,
        "is_active": row.is_active,
    }


def fetch_employee_context(engine: Engine, employee_id: int) -> dict[str, Any] | None:
    """Lấy `department_id`/`division_id` của 1 nhân viên (join
    `employee` -> `department` để suy ra `division_id`, vì `employee`
    không lưu trực tiếp `division_id`)."""
    with Session(engine) as session:
        stmt = (
            select(Employee.id, Employee.department_id, Department.division_id)
            .join(Department, Employee.department_id == Department.id)
            .where(Employee.id == employee_id)
        )
        row = session.execute(stmt).first()
    if row is None:
        return None
    return {
        "employee_id": row.id,
        "department_id": row.department_id,
        "division_id": row.division_id,
    }


def record_login_history(
    engine: Engine, user_id: int, success: bool, ip_address: str | None = None
) -> int:
    """Ghi 1 dòng `login_history` — BẮT BUỘC gọi cho MỌI lần đăng nhập
    (thành công lẫn thất bại), CLAUDE.md mục 6."""
    with Session(engine) as session:
        entry = LoginHistory(user_id=user_id, success=success, ip_address=ip_address)
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry.id


def record_audit_log(
    engine: Engine,
    *,
    user_id: int,
    action: str,
    table_name: str,
    record_id: int,
    old_value: str | None = None,
    new_value: str | None = None,
) -> int:
    """Ghi 1 dòng `audit_log` — BẮT BUỘC cho mọi thao tác tạo/sửa/khoá tài
    khoản qua module auth, CLAUDE.md mục 6. Gọi từ
    `src/auth/admin_actions.py`, KHÔNG gọi trực tiếp từ `src/app/`."""
    with Session(engine) as session:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_value=old_value,
            new_value=new_value,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry.id


def update_user_password_hash(
    engine: Engine, user_id: int, new_password_hash: str
) -> None:
    """Cập nhật `users.password_hash` — hash bcrypt phải được tính SẴN ở
    `src/auth/hashing.py` trước khi gọi hàm này (module này chỉ lưu trữ)."""
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None:
            raise ValueError(f"Không tìm thấy user id={user_id}")
        user.password_hash = new_password_hash
        session.commit()


def _execute_customer_id_union(engine: Engine, selects: list[Select]) -> set[int]:
    """Thực thi UNION nhiều truy vấn `customer_id` (SQLAlchemy `union`,
    parameterized — CLAUDE.md mục 4) và trả về tập hợp id duy nhất."""
    if not selects:
        return set()
    combined = union(*selects) if len(selects) > 1 else selects[0]
    with Session(engine) as session:
        rows = session.execute(combined).all()
    return {r[0] for r in rows if r[0] is not None}


def fetch_customer_ids_for_employee(engine: Engine, employee_id: int) -> set[int]:
    """Phạm vi KH suy ra cho 1 nhân viên (role User / KH loại C) — UNION
    `customer_id` từ `sales_order`/`debt`/`price_request` nơi
    `employee_id` khớp. Xem ghi chú "suy luận kỹ thuật" trong
    `src/auth/scope.py`."""
    selects: list[Select] = [
        select(SalesOrder.customer_id).where(SalesOrder.employee_id == employee_id),
        select(Debt.customer_id).where(Debt.employee_id == employee_id),
        select(PriceRequest.customer_id).where(
            PriceRequest.employee_id == employee_id,
            PriceRequest.customer_id.is_not(None),
        ),
    ]
    return _execute_customer_id_union(engine, selects)


def fetch_customer_ids_for_department(engine: Engine, department_id: int) -> set[int]:
    """Phạm vi KH suy ra cho 1 phòng (role Manager / KH loại B)."""
    selects: list[Select] = [
        select(SalesOrder.customer_id)
        .join(Employee, SalesOrder.employee_id == Employee.id)
        .where(Employee.department_id == department_id),
        select(Debt.customer_id).where(Debt.department_id == department_id),
        select(PriceRequest.customer_id)
        .join(Employee, PriceRequest.employee_id == Employee.id)
        .where(
            Employee.department_id == department_id,
            PriceRequest.customer_id.is_not(None),
        ),
    ]
    return _execute_customer_id_union(engine, selects)


def fetch_customer_ids_for_division(engine: Engine, division_id: int) -> set[int]:
    """Phạm vi KH suy ra cho 1 khối (role Admin gắn employee / KH loại A)."""
    selects: list[Select] = [
        select(SalesOrder.customer_id)
        .join(Employee, SalesOrder.employee_id == Employee.id)
        .join(Department, Employee.department_id == Department.id)
        .where(Department.division_id == division_id),
        select(Debt.customer_id).where(Debt.division_id == division_id),
        select(PriceRequest.customer_id)
        .join(Employee, PriceRequest.employee_id == Employee.id)
        .join(Department, Employee.department_id == Department.id)
        .where(
            Department.division_id == division_id,
            PriceRequest.customer_id.is_not(None),
        ),
    ]
    return _execute_customer_id_union(engine, selects)


def fetch_all_customer_ids(engine: Engine) -> set[int]:
    """Toàn bộ `customer_id` trong bảng `customer` — dùng cho phạm vi
    "unrestricted" (Admin quản trị hệ thống thuần tuý, không gắn nhân
    viên cụ thể). Xem ghi chú mơ hồ vai trò Admin trong `src/auth/scope.py`."""
    with Session(engine) as session:
        rows = session.execute(select(Customer.id)).all()
    return {r[0] for r in rows}
