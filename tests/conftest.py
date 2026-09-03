"""Fixture pytest dùng chung — hạ tầng test SQLite in-memory, HOÀN TOÀN
độc lập với MySQL "lacco" thật và `.env` (bước 3.3, HD-13).

Lý do bắt buộc `poolclass=StaticPool` + `check_same_thread=False`: SQLite
`:memory:` là DB theo-từng-connection — nếu dùng `create_engine` mặc định,
mỗi lần lấy connection mới từ pool sẽ ra 1 DB rỗng khác, mất hết dữ liệu
seed. `StaticPool` ép toàn bộ engine dùng chung đúng 1 connection/1 DB
trong suốt vòng đời fixture.

Import đủ `dimension`, `business`, `security` (dù không dùng trực tiếp)
trước khi gọi `Base.metadata.create_all(engine)` — nếu không SQLAlchemy sẽ
không biết các bảng liên quan qua ForeignKey (`Base.metadata` chỉ có bảng
của model đã được import).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.db.models import base, business, dimension, security  # noqa: F401
from src.db.models.base import Base
from src.db.models.dimension import Customer, Department, Division, Employee, Service
from src.db.models.business import SalesOrder
from src.db.models.enums import CustomerClassification, StaffGroup


@pytest.fixture()
def db_engine():
    """Engine SQLite in-memory dùng chung 1 connection cho toàn bộ test
    (qua StaticPool), scope="function" để mỗi test có DB sạch riêng."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_scope_data(db_engine):
    """Seed dữ liệu tối thiểu để test đủ 3 nhánh của `compute_data_scope()`
    (`src/auth/scope.py`): Admin (unrestricted), Manager (phạm vi theo
    `department_id`), User (phạm vi theo `employee_id`).

    Cấu trúc: 1 Division, 2 Department (A, B) cùng Division; 3 Employee
    (2 ở Dept A — 1 sẽ dùng cho Manager, 1 cho User; 1 ở Dept B — "người
    ngoài"); 3 Customer (X do User-DeptA phụ trách, Y do Employee-DeptA-khác
    phụ trách — cùng phòng nhưng khác NV, Z do Employee-DeptB phụ trách).

    Trả về dict chứa các entity đã tạo (id) để test dùng trực tiếp, tránh
    query lại.
    """
    with Session(db_engine) as session:
        division = Division(name="Khối Kinh doanh")
        session.add(division)
        session.flush()

        dept_a = Department(name="Phòng Kinh doanh A", division_id=division.id)
        dept_b = Department(name="Phòng Kinh doanh B", division_id=division.id)
        session.add_all([dept_a, dept_b])
        session.flush()

        service = Service(name="Cước")
        session.add(service)
        session.flush()

        emp_manager = Employee(
            full_name="Nguyễn Văn Manager",
            department_id=dept_a.id,
            staff_group=StaffGroup.MANAGEMENT,
        )
        emp_user = Employee(
            full_name="Trần Thị User",
            department_id=dept_a.id,
            staff_group=StaffGroup.FRONTLINE,
        )
        emp_outsider = Employee(
            full_name="Lê Văn NgoàiPhòng",
            department_id=dept_b.id,
            staff_group=StaffGroup.FRONTLINE,
        )
        session.add_all([emp_manager, emp_user, emp_outsider])
        session.flush()

        customer_x = Customer(
            code="CUST-X",
            name="Khách hàng X",
            current_classification=CustomerClassification.C,
        )
        customer_y = Customer(
            code="CUST-Y",
            name="Khách hàng Y",
            current_classification=CustomerClassification.B,
        )
        customer_z = Customer(
            code="CUST-Z",
            name="Khách hàng Z",
            current_classification=CustomerClassification.C,
        )
        session.add_all([customer_x, customer_y, customer_z])
        session.flush()

        order_x = SalesOrder(
            customer_id=customer_x.id,
            service_id=service.id,
            employee_id=emp_user.id,
            order_date=date(2026, 1, 10),
            status="Đang vận chuyển",
            revenue=1000,
            order_cost=800,
            invoice_status="Chưa xuất",
        )
        order_y = SalesOrder(
            customer_id=customer_y.id,
            service_id=service.id,
            employee_id=emp_manager.id,
            order_date=date(2026, 1, 11),
            status="Đang vận chuyển",
            revenue=2000,
            order_cost=1500,
            invoice_status="Chưa xuất",
        )
        order_z = SalesOrder(
            customer_id=customer_z.id,
            service_id=service.id,
            employee_id=emp_outsider.id,
            order_date=date(2026, 1, 12),
            status="Đang vận chuyển",
            revenue=3000,
            order_cost=2000,
            invoice_status="Đã xuất",
        )
        session.add_all([order_x, order_y, order_z])
        session.commit()

        return {
            "division_id": division.id,
            "dept_a_id": dept_a.id,
            "dept_b_id": dept_b.id,
            "service_id": service.id,
            "emp_manager_id": emp_manager.id,
            "emp_user_id": emp_user.id,
            "emp_outsider_id": emp_outsider.id,
            "customer_x_id": customer_x.id,
            "customer_y_id": customer_y.id,
            "customer_z_id": customer_z.id,
        }
