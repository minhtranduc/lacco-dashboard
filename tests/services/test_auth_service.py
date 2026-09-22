"""Test `src/services/auth_service.py` — truy vấn DB thô phục vụ tầng
`src/auth/` (CLAUDE.md mục 2: module này KHÔNG chứa logic RBAC, chỉ đọc/ghi
dữ liệu qua SQLAlchemy parameterized query, CLAUDE.md mục 4).

Khác với `tests/auth/test_scope.py`/`test_authentication.py` — 2 file đó
test `src/auth/` GIÁN TIẾP qua `compute_data_scope()`/`authenticate_and_log()`
— file này test TRỰC TIẾP từng hàm của `auth_service.py`.

Dùng `db_engine`/`seeded_scope_data` (SQLite in-memory qua tham số `engine=`,
xem `tests/conftest.py`) — KHÔNG kết nối MySQL "lacco" thật. `db_engine` có
scope="function" nên mỗi test có DB sạch riêng, không rò rỉ dữ liệu seed
thêm giữa các hàm test `fetch_customer_ids_for_*` dù dùng chung
`seeded_scope_data`.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.db.models.business import Debt, PriceRequest
from src.db.models.dimension import Department, Division, Employee
from src.db.models.enums import StaffGroup, UserRole
from src.db.models.security import AuditLog, LoginHistory, User
from src.services.auth_service import (
    fetch_all_customer_ids,
    fetch_customer_ids_for_department,
    fetch_customer_ids_for_division,
    fetch_customer_ids_for_employee,
    fetch_employee_context,
    fetch_user_by_id,
    fetch_user_by_username,
    fetch_users_for_credentials,
    record_audit_log,
    record_login_history,
    update_user_password_hash,
)


def _create_division_department_employee(engine) -> tuple[int, int, int]:
    """Seed tối thiểu 1 Division/1 Department/1 Employee — dùng cho các test
    không cần cấu trúc đầy đủ của `seeded_scope_data`."""
    with Session(engine) as session:
        division = Division(name="Khối Vận hành")
        session.add(division)
        session.flush()
        department = Department(name="Phòng Vận hành A", division_id=division.id)
        session.add(department)
        session.flush()
        employee = Employee(
            full_name="Phạm Thị Nhân Viên",
            department_id=department.id,
            staff_group=StaffGroup.FRONTLINE,
        )
        session.add(employee)
        session.commit()
        return division.id, department.id, employee.id


def _create_user(
    engine,
    *,
    username: str,
    role: UserRole = UserRole.USER,
    employee_id: int | None = None,
    is_active: bool = True,
    password_hash: str = "$2b$dummy-hash-not-verified",
) -> int:
    """Tạo 1 user tối thiểu qua ORM, cùng quy ước với `_create_user` của
    `tests/auth/test_scope.py`."""
    with Session(engine) as session:
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            employee_id=employee_id,
            is_active=is_active,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def test_fetch_users_for_credentials_returns_only_active_with_correct_shape(
    db_engine,
):
    """Chỉ trả về user `is_active=True`, dict đúng 7 khoá, `role` đã chuẩn
    hoá về plain string (không còn là `UserRole` enum member)."""
    _division_id, _department_id, employee_id = _create_division_department_employee(
        db_engine
    )
    active_id = _create_user(
        db_engine,
        username="active1",
        role=UserRole.MANAGER,
        employee_id=employee_id,
        is_active=True,
        password_hash="hash-active",
    )
    _create_user(db_engine, username="inactive1", role=UserRole.USER, is_active=False)

    rows = fetch_users_for_credentials(db_engine)

    assert len(rows) == 1
    row = rows[0]
    assert row == {
        "id": active_id,
        "username": "active1",
        "password_hash": "hash-active",
        "role": "Manager",
        "employee_id": employee_id,
        "is_active": True,
        "full_name": "Phạm Thị Nhân Viên",
    }
    assert type(row["role"]) is str
    assert not isinstance(row["role"], UserRole)


def test_fetch_user_by_username_found(db_engine):
    """Tìm thấy user theo `username` khớp chính xác, trả về dict đầy đủ."""
    user_id = _create_user(
        db_engine, username="tim-thay", role=UserRole.ADMIN, employee_id=None
    )

    result = fetch_user_by_username(db_engine, "tim-thay")

    assert result is not None
    assert result["id"] == user_id
    assert result["username"] == "tim-thay"
    assert result["role"] == "Admin"
    assert result["employee_id"] is None
    assert result["is_active"] is True


def test_fetch_user_by_username_not_found(db_engine):
    """Không tìm thấy `username` -> trả về `None`."""
    _create_user(db_engine, username="user-ton-tai")

    result = fetch_user_by_username(db_engine, "khong-ton-tai")

    assert result is None


def test_fetch_user_by_id_found(db_engine):
    """Tìm thấy user theo `id`, trả về dict (không có `password_hash`)."""
    user_id = _create_user(db_engine, username="theo-id", role=UserRole.USER)

    result = fetch_user_by_id(db_engine, user_id)

    assert result is not None
    assert result == {
        "id": user_id,
        "username": "theo-id",
        "role": "User",
        "employee_id": None,
        "is_active": True,
    }


def test_fetch_user_by_id_not_found(db_engine):
    """Không tìm thấy `id` -> trả về `None`."""
    result = fetch_user_by_id(db_engine, 999_999)

    assert result is None


def test_fetch_employee_context_found(db_engine):
    """Trả về đúng `department_id`/`division_id` (suy ra qua join
    `employee` -> `department`)."""
    division_id, department_id, employee_id = _create_division_department_employee(
        db_engine
    )

    result = fetch_employee_context(db_engine, employee_id)

    assert result == {
        "employee_id": employee_id,
        "department_id": department_id,
        "division_id": division_id,
    }


def test_fetch_employee_context_not_found(db_engine):
    """`employee_id` không tồn tại -> trả về `None`."""
    result = fetch_employee_context(db_engine, 999_999)

    assert result is None


def test_record_login_history_persists_row(db_engine):
    """Ghi thật 1 dòng `login_history`, id trả về khớp với dòng đã lưu."""
    user_id = _create_user(db_engine, username="login-user")

    returned_id = record_login_history(
        db_engine, user_id, success=True, ip_address="10.0.0.5"
    )

    with Session(db_engine) as session:
        row = session.get(LoginHistory, returned_id)
    assert row is not None
    assert row.user_id == user_id
    assert row.success is True
    assert row.ip_address == "10.0.0.5"


def test_record_audit_log_persists_row(db_engine):
    """Ghi thật 1 dòng `audit_log` với đầy đủ các trường, id trả về khớp."""
    user_id = _create_user(db_engine, username="audit-user")

    returned_id = record_audit_log(
        db_engine,
        user_id=user_id,
        action="update",
        table_name="users",
        record_id=user_id,
        old_value="active",
        new_value="locked",
    )

    with Session(db_engine) as session:
        row = session.get(AuditLog, returned_id)
    assert row is not None
    assert row.user_id == user_id
    assert row.action == "update"
    assert row.table_name == "users"
    assert row.record_id == user_id
    assert row.old_value == "active"
    assert row.new_value == "locked"


def test_update_user_password_hash_updates_existing_user(db_engine):
    """Cập nhật `password_hash` thành công, giá trị mới được lưu vào DB."""
    user_id = _create_user(db_engine, username="doi-mat-khau", password_hash="hash-cu")

    update_user_password_hash(db_engine, user_id, "hash-moi")

    with Session(db_engine) as session:
        user = session.get(User, user_id)
    assert user is not None
    assert user.password_hash == "hash-moi"


def test_update_user_password_hash_raises_for_unknown_user(db_engine):
    """`user_id` không tồn tại -> raise `ValueError`, không âm thầm bỏ qua."""
    with pytest.raises(ValueError):
        update_user_password_hash(db_engine, 999_999, "hash-bat-ky")


def test_fetch_customer_ids_for_employee_unions_all_three_tables(
    db_engine, seeded_scope_data
):
    """UNION `sales_order`/`debt`/`price_request` theo `employee_id`, và
    `price_request.customer_id IS NULL` bị loại khỏi kết quả (`.is_not(None)`
    trong `_execute_customer_id_union`)."""
    emp_user_id = seeded_scope_data["emp_user_id"]
    division_id = seeded_scope_data["division_id"]
    dept_a_id = seeded_scope_data["dept_a_id"]
    service_id = seeded_scope_data["service_id"]
    customer_y_id = seeded_scope_data["customer_y_id"]
    customer_z_id = seeded_scope_data["customer_z_id"]

    with Session(db_engine) as session:
        session.add_all(
            [
                # customer_y đến từ price_request (không phải sales_order)
                # của chính emp_user -> phải được UNION vào.
                PriceRequest(
                    service_id=service_id,
                    employee_id=emp_user_id,
                    customer_id=customer_y_id,
                    request_date=date(2026, 2, 1),
                    is_won=True,
                ),
                # customer_id=NULL -> phải bị loại trừ khỏi kết quả.
                PriceRequest(
                    service_id=service_id,
                    employee_id=emp_user_id,
                    customer_id=None,
                    request_date=date(2026, 2, 2),
                    is_won=False,
                ),
                # customer_z đến từ debt của chính emp_user.
                Debt(
                    customer_id=customer_z_id,
                    division_id=division_id,
                    department_id=dept_a_id,
                    employee_id=emp_user_id,
                    invoice_date=date(2026, 1, 1),
                    due_date=date(2026, 2, 1),
                    amount=500,
                ),
            ]
        )
        session.commit()

    result = fetch_customer_ids_for_employee(db_engine, emp_user_id)

    assert result == {
        seeded_scope_data["customer_x_id"],  # từ sales_order (order_x seed)
        customer_y_id,  # từ price_request
        customer_z_id,  # từ debt
    }
    assert None not in result


def test_fetch_customer_ids_for_department_unions_across_employees(
    db_engine, seeded_scope_data
):
    """Phạm vi theo `department_id` UNION qua nhiều nhân viên trong phòng
    (`sales_order`/`price_request` join qua `employee.department_id`), và
    `debt` lọc trực tiếp trên cột `debt.department_id` (không join qua
    employee — đúng thiết kế ghi trong docstring `Debt` ở `business.py`)."""
    dept_a_id = seeded_scope_data["dept_a_id"]
    division_id = seeded_scope_data["division_id"]
    emp_manager_id = seeded_scope_data["emp_manager_id"]
    emp_outsider_id = seeded_scope_data["emp_outsider_id"]
    service_id = seeded_scope_data["service_id"]
    customer_z_id = seeded_scope_data["customer_z_id"]

    with Session(db_engine) as session:
        session.add_all(
            [
                # emp_manager thuộc dept_a -> price_request của NV này phải
                # được tính vào phạm vi phòng dept_a.
                PriceRequest(
                    service_id=service_id,
                    employee_id=emp_manager_id,
                    customer_id=customer_z_id,
                    request_date=date(2026, 2, 3),
                    is_won=True,
                ),
                # debt.department_id=dept_a_id dù employee_id thuộc dept_b
                # (emp_outsider) -> vẫn phải tính vào dept_a vì debt lọc
                # trực tiếp trên cột department_id, không suy qua employee.
                Debt(
                    customer_id=customer_z_id,
                    division_id=division_id,
                    department_id=dept_a_id,
                    employee_id=emp_outsider_id,
                    invoice_date=date(2026, 1, 5),
                    due_date=date(2026, 2, 5),
                    amount=700,
                ),
            ]
        )
        session.commit()

    result = fetch_customer_ids_for_department(db_engine, dept_a_id)

    assert result == {
        seeded_scope_data["customer_x_id"],  # order_x, emp_user (dept_a)
        seeded_scope_data["customer_y_id"],  # order_y, emp_manager (dept_a)
        customer_z_id,  # price_request + debt thêm ở trên
    }


def test_fetch_customer_ids_for_division_includes_all_departments(
    db_engine, seeded_scope_data
):
    """Phạm vi theo `division_id` UNION qua MỌI phòng trong khối — khác biệt
    với phạm vi phòng: `customer_z` (đơn của `emp_outsider`, thuộc `dept_b`)
    không nằm trong phạm vi `dept_a` nhưng PHẢI nằm trong phạm vi cả khối vì
    `dept_a`/`dept_b` cùng thuộc 1 `division`."""
    division_id = seeded_scope_data["division_id"]

    result = fetch_customer_ids_for_division(db_engine, division_id)

    assert result == {
        seeded_scope_data["customer_x_id"],
        seeded_scope_data["customer_y_id"],
        seeded_scope_data["customer_z_id"],
    }


def test_fetch_all_customer_ids_returns_every_seeded_customer(
    db_engine, seeded_scope_data
):
    """Trả về TOÀN BỘ `customer.id`, không lọc theo employee/department/
    division — dùng cho phạm vi "unrestricted"."""
    result = fetch_all_customer_ids(db_engine)

    assert result == {
        seeded_scope_data["customer_x_id"],
        seeded_scope_data["customer_y_id"],
        seeded_scope_data["customer_z_id"],
    }
