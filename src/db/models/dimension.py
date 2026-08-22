"""Model nhóm bảng danh mục (dimension): division, department, employee,
service, customer, supplier.

Nguồn thiết kế: `docs/architecture/erd-tuan-02.md`, mục "Nhóm bảng danh mục
(dimension)". Không tự thêm bảng/cột ngoài ERD đã chốt.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base
from src.db.models.enums import CustomerClassification, StaffGroup

if TYPE_CHECKING:
    # Chỉ dùng cho type-checking (mypy/IDE) — tránh import vòng lúc runtime.
    from src.db.models.business import (
        Cost,
        Budget,
        Debt,
        PriceRequest,
        SalesOrder,
        SupplierEvaluation,
        CustomerClassificationHistory,
    )
    from src.db.models.security import User


class Division(Base):
    """Khối — cấp cao nhất trong phân cấp RBAC theo Khối/Phòng (CLAUDE.md
    mục 6). Cũng là cấp tổng hợp cho báo cáo Chi phí theo Khối và Công nợ
    Khối→Phòng→Kinh doanh.
    """

    __tablename__ = "division"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    departments: Mapped[list["Department"]] = relationship(
        back_populates="division"
    )
    costs: Mapped[list["Cost"]] = relationship(back_populates="division")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="division")
    debts: Mapped[list["Debt"]] = relationship(back_populates="division")

    def __repr__(self) -> str:
        return f"<Division id={self.id} name={self.name!r}>"


class Department(Base):
    """Phòng — thuộc 1 Division, là cấp trung gian trong RBAC Khối/Phòng và
    trong báo cáo Công nợ Khối→Phòng→Kinh doanh.
    """

    __tablename__ = "department"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    division_id: Mapped[int] = mapped_column(
        ForeignKey("division.id"), nullable=False, index=True
    )

    division: Mapped["Division"] = relationship(back_populates="departments")
    employees: Mapped[list["Employee"]] = relationship(
        back_populates="department"
    )
    debts: Mapped[list["Debt"]] = relationship(back_populates="department")

    def __repr__(self) -> str:
        return (
            f"<Department id={self.id} name={self.name!r} "
            f"division_id={self.division_id}>"
        )


class Employee(Base):
    """Nhân viên — thuộc 1 Department; có `staff_group` phục vụ báo cáo Chi
    phí theo Nhóm (LĐ/QL/Frontline/Middle/Backend, đã "Đã rõ" theo AMIS).
    """

    __tablename__ = "employee"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id"), nullable=False, index=True
    )
    staff_group: Mapped[StaffGroup] = mapped_column(
        Enum(StaffGroup, native_enum=False, length=20), nullable=False
    )
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    department: Mapped["Department"] = relationship(
        back_populates="employees"
    )
    user_account: Mapped["User | None"] = relationship(
        back_populates="employee", uselist=False
    )
    sales_orders: Mapped[list["SalesOrder"]] = relationship(
        back_populates="employee"
    )
    price_requests: Mapped[list["PriceRequest"]] = relationship(
        back_populates="employee"
    )
    supplier_evaluations: Mapped[list["SupplierEvaluation"]] = relationship(
        back_populates="employee"
    )
    debts: Mapped[list["Debt"]] = relationship(back_populates="employee")

    def __repr__(self) -> str:
        return (
            f"<Employee id={self.id} full_name={self.full_name!r} "
            f"department_id={self.department_id}>"
        )


class Service(Base):
    """Dịch vụ (VD: Cước, Hải quan...) — dùng cho báo cáo Doanh thu theo
    dịch vụ, Pricing – Thành đơn, Pricing – Nhà cung cấp.
    """

    __tablename__ = "service"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Giả định name là định danh nghiệp vụ duy nhất (VD "Cước", "Hải quan").
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    sales_orders: Mapped[list["SalesOrder"]] = relationship(
        back_populates="service"
    )
    price_requests: Mapped[list["PriceRequest"]] = relationship(
        back_populates="service"
    )
    supplier_evaluations: Mapped[list["SupplierEvaluation"]] = relationship(
        back_populates="service"
    )

    def __repr__(self) -> str:
        return f"<Service id={self.id} name={self.name!r}>"


class Customer(Base):
    """Khách hàng — chỉ lưu trạng thái phân loại A/B/C **hiện tại**
    (`current_classification`). Lịch sử biến động theo thời gian nằm ở bảng
    `CustomerClassificationHistory` (xem docstring bảng đó trong
    `business.py`), vì câu hỏi nghiệp vụ gốc là "cơ cấu KH dịch chuyển như
    thế nào" — cần dữ liệu theo thời gian, không chỉ trạng thái hiện tại
    (xem `docs/architecture/erd-tuan-02.md`).
    """

    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # "Nguồn" khách hàng — cột có sẵn trong hệ thống FT (đã "Đã rõ").
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_classification: Mapped[CustomerClassification] = mapped_column(
        Enum(CustomerClassification, native_enum=False, length=1),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    sales_orders: Mapped[list["SalesOrder"]] = relationship(
        back_populates="customer"
    )
    price_requests: Mapped[list["PriceRequest"]] = relationship(
        back_populates="customer"
    )
    debts: Mapped[list["Debt"]] = relationship(back_populates="customer")
    classification_history: Mapped[list["CustomerClassificationHistory"]] = (
        relationship(back_populates="customer")
    )

    def __repr__(self) -> str:
        return (
            f"<Customer id={self.id} code={self.code!r} "
            f"classification={self.current_classification}>"
        )


class Supplier(Base):
    """Nhà cung cấp — dùng cho báo cáo Pricing – Nhà cung cấp
    (đánh giá qua `SupplierEvaluation`).
    """

    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    evaluations: Mapped[list["SupplierEvaluation"]] = relationship(
        back_populates="supplier"
    )

    def __repr__(self) -> str:
        return f"<Supplier id={self.id} name={self.name!r}>"
