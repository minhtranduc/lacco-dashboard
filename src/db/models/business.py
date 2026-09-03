"""Model nhóm bảng nghiệp vụ (fact): sales_order, price_request,
supplier_evaluation, cost, budget, personnel_cost, debt,
customer_classification_history.

Nguồn thiết kế: `docs/architecture/erd-tuan-02.md`, mục "Nhóm bảng nghiệp
vụ (fact)". Không tự thêm bảng/cột ngoài ERD đã chốt.

Ghi chú kiểu dữ liệu `period` (dùng ở `Cost`, `Budget`, `PersonnelCost`,
`SupplierEvaluation`): ERD chỉ ghi tên cột "period" mà chưa xác nhận định
dạng lưu trữ cụ thể (VD "2026-08" dạng chuỗi hay ngày đại diện đầu kỳ). Ở
đây chọn kiểu `Date` — lưu ngày đại diện cho kỳ báo cáo (quy ước: ngày đầu
tháng/quý) — vì đây là lựa chọn kỹ thuật phổ biến, dễ so sánh/sắp xếp hơn
chuỗi tự do. Đây là GIẢ ĐỊNH KỸ THUẬT, không phải yêu cầu tường minh — cần
COO xác nhận định dạng kỳ báo cáo thực tế trước khi import dữ liệu thật.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base
from src.db.models.enums import CustomerClassification, StaffGroup

if TYPE_CHECKING:
    # Chỉ dùng cho type-checking (mypy/IDE) — tránh import vòng lúc runtime.
    from src.db.models.dimension import (
        Customer,
        Department,
        Division,
        Employee,
        Service,
        Supplier,
    )


class SalesOrder(Base):
    """Đơn hàng — phục vụ báo cáo Doanh thu/lãi lỗ theo dịch vụ/KH/Khối-
    Phòng-NV, Tình trạng đơn hàng, Tình trạng xuất hóa đơn.

    Đổi tên bảng thành `sales_order` (không đặt `order`) vì `ORDER` là từ
    khoá dành riêng trong MySQL 8.0 (dùng cho `ORDER BY`) — xem lý do đầy đủ
    trong `docs/architecture/erd-tuan-02.md`. Cột giá vốn đổi tên thành
    `order_cost` để không trùng tên với bảng `cost` (Chi phí theo Khối).

    `status` và `invoice_status` dùng kiểu `String` placeholder — danh sách
    giá trị cụ thể CHƯA được xác nhận, xem mục 1 và mục 2 của "Việc cần xác
    nhận trước khi sang bước 2.2" trong `erd-tuan-02.md`. KHÔNG tự bịa danh
    sách enum cho 2 cột này.
    """

    __tablename__ = "sales_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id"), nullable=False, index=True
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("service.id"), nullable=False, index=True
    )
    # Nhân viên kinh doanh phụ trách đơn hàng.
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employee.id"), nullable=False, index=True
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Placeholder — xem mục 1, erd-tuan-02.md. Độ dài 50 đủ chứa nhãn trạng
    # thái tiếng Việt (VD "Đang vận chuyển") khi có danh sách chính thức.
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    order_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # Placeholder — xem mục 2, erd-tuan-02.md (chưa rõ đây có phải field
    # độc lập với `status` hay là 1 giá trị trong cùng quy trình).
    invoice_status: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="sales_orders")
    service: Mapped["Service"] = relationship(back_populates="sales_orders")
    employee: Mapped["Employee"] = relationship(back_populates="sales_orders")
    price_request: Mapped["PriceRequest | None"] = relationship(
        back_populates="sales_order"
    )

    def __repr__(self) -> str:
        return (
            f"<SalesOrder id={self.id} customer_id={self.customer_id} "
            f"status={self.status!r}>"
        )


class PriceRequest(Base):
    """Yêu cầu báo giá — phục vụ báo cáo Pricing – Thành đơn
    (= số lượng chốt đơn / số lượng request giá).

    `customer_id` cho phép NULL — theo mục 7 của "Việc cần xác nhận" trong
    `erd-tuan-02.md`: giả định là báo giá cho khách hàng tiềm năng chưa có
    trong bảng `customer`. Đây là suy luận, CHƯA được COO xác nhận. Lưu ý
    ranh giới: KHÔNG mở rộng bảng này thành nơi lưu thông tin lead/khách
    hàng tiềm năng — đó là phạm vi CRM, đã chốt dời Giai đoạn 2.
    """

    __tablename__ = "price_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("service.id"), nullable=False, index=True
    )
    # Nhân viên Pricing phụ trách yêu cầu báo giá.
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employee.id"), nullable=False, index=True
    )
    # Nullable — xem mục 7, erd-tuan-02.md.
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id"), nullable=True, index=True
    )
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Điền khi chốt đơn — quan hệ 1-0..1 với sales_order ("chốt thành").
    sales_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_order.id"), nullable=True, index=True
    )

    service: Mapped["Service"] = relationship(back_populates="price_requests")
    employee: Mapped["Employee"] = relationship(back_populates="price_requests")
    customer: Mapped["Customer | None"] = relationship(back_populates="price_requests")
    sales_order: Mapped["SalesOrder | None"] = relationship(
        back_populates="price_request"
    )

    def __repr__(self) -> str:
        return (
            f"<PriceRequest id={self.id} service_id={self.service_id} "
            f"is_won={self.is_won}>"
        )


class SupplierEvaluation(Base):
    """Đánh giá nhà cung cấp — phục vụ báo cáo Pricing – Nhà cung cấp, do
    Nhân viên Pricing lập.

    `score` dùng `Numeric(5, 2)` — thang điểm cụ thể (VD 0-100 hay 1-5)
    chưa được xác nhận trong phỏng vấn nghiệp vụ; kiểu số thập phân này đủ
    linh hoạt cho cả 2 khả năng, không ép buộc thang điểm cụ thể.
    """

    __tablename__ = "supplier_evaluation"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("supplier.id"), nullable=False, index=True
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("service.id"), nullable=False, index=True
    )
    # Người đánh giá (Nhân viên Pricing).
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employee.id"), nullable=False, index=True
    )
    period: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="evaluations")
    service: Mapped["Service"] = relationship(back_populates="supplier_evaluations")
    employee: Mapped["Employee"] = relationship(back_populates="supplier_evaluations")

    def __repr__(self) -> str:
        return (
            f"<SupplierEvaluation id={self.id} supplier_id={self.supplier_id} "
            f"score={self.score}>"
        )


class Cost(Base):
    """Chi phí theo Khối, nguồn AMIS — phục vụ báo cáo Chi phí theo Khối
    (so sánh với `Budget` cùng kỳ).
    """

    __tablename__ = "cost"

    id: Mapped[int] = mapped_column(primary_key=True)
    division_id: Mapped[int] = mapped_column(
        ForeignKey("division.id"), nullable=False, index=True
    )
    period: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    division: Mapped["Division"] = relationship(back_populates="costs")

    def __repr__(self) -> str:
        return (
            f"<Cost id={self.id} division_id={self.division_id} "
            f"period={self.period} amount={self.amount}>"
        )


class Budget(Base):
    """Ngân sách theo Khối — phục vụ so sánh chi thực tế (`Cost`) với ngân
    sách được cấp trong cùng kỳ.
    """

    __tablename__ = "budget"

    id: Mapped[int] = mapped_column(primary_key=True)
    division_id: Mapped[int] = mapped_column(
        ForeignKey("division.id"), nullable=False, index=True
    )
    period: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    division: Mapped["Division"] = relationship(back_populates="budgets")

    def __repr__(self) -> str:
        return (
            f"<Budget id={self.id} division_id={self.division_id} "
            f"period={self.period} amount={self.amount}>"
        )


class PersonnelCost(Base):
    """Chi phí theo Nhóm nhân sự (LĐ/QL/Frontline/Middle/Backend), nguồn
    AMIS — đã nhóm sẵn, không cần tự định nghĩa lại ranh giới 5 nhóm.

    Không có FK tới `employee`/`division` theo đúng ERD — bảng này tổng
    hợp theo `staff_group` (toàn công ty), không theo từng Khối/Phòng.
    """

    __tablename__ = "personnel_cost"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_group: Mapped[StaffGroup] = mapped_column(
        Enum(StaffGroup, native_enum=False, length=20), nullable=False
    )
    period: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<PersonnelCost id={self.id} staff_group={self.staff_group} "
            f"period={self.period}>"
        )


class Debt(Base):
    """Công nợ — phục vụ báo cáo Công nợ Khối→Phòng→Kinh doanh, ngưỡng quá
    hạn 4 mức (0-30/31-60/61-90/>90 ngày).

    Lưu đồng thời cả `division_id` và `department_id` dù `department` vốn
    đã có `division_id` riêng — đây là thiết kế suy luận để truy vấn nhanh
    theo phân cấp Khối→Phòng→KD mà không cần join, KHÔNG phải yêu cầu tường
    minh từ phỏng vấn. Xem mục 5 của "Việc cần xác nhận" trong
    `erd-tuan-02.md` — cần COO xác nhận có chấp nhận rủi ro 2 cột lệch nhau
    (department không thuộc đúng division) hay nên bỏ `division_id` và suy
    ra qua `department.division_id` khi truy vấn.

    KHÔNG có cột vật lý `aging_bucket` trong model này. Theo nguyên tắc
    tách lớp CLAUDE.md mục 2 (logic không nằm trong `src/db/`), việc tính
    aging_bucket (0-30/31-60/61-90/>90 ngày từ `due_date`) sẽ nằm ở
    `src/services/` khi triển khai tới bước đó — đang chờ COO xác nhận
    cách hiển thị (hiện trạng tại thời điểm xem hay snapshot tại thời điểm
    import) trước khi code phần tính toán này. Xem mục 6,
    `erd-tuan-02.md`.
    """

    __tablename__ = "debt"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id"), nullable=False, index=True
    )
    division_id: Mapped[int] = mapped_column(
        ForeignKey("division.id"), nullable=False, index=True
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id"), nullable=False, index=True
    )
    # Nhân viên kinh doanh phụ trách khoản nợ.
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employee.id"), nullable=False, index=True
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="debts")
    division: Mapped["Division"] = relationship(back_populates="debts")
    department: Mapped["Department"] = relationship(back_populates="debts")
    employee: Mapped["Employee"] = relationship(back_populates="debts")

    def __repr__(self) -> str:
        return (
            f"<Debt id={self.id} customer_id={self.customer_id} "
            f"due_date={self.due_date} amount={self.amount}>"
        )


class CustomerClassificationHistory(Base):
    """Lịch sử phân loại khách hàng A/B/C theo thời gian — phục vụ báo cáo
    "Tăng giảm loại KH (A/B/C)" (xu hướng dịch chuyển cơ cấu KH theo
    tháng/quý), khác với `Customer.current_classification` chỉ lưu trạng
    thái hiện tại.

    Tần suất ghi 1 dòng mỗi lần import dữ liệu mới — tần suất cụ thể (mỗi
    tháng theo tần suất báo cáo Khách hàng, hay tần suất khác) CHƯA được
    xác nhận, xem mục 3 của "Việc cần xác nhận" trong `erd-tuan-02.md`.
    """

    __tablename__ = "customer_classification_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id"), nullable=False, index=True
    )
    classification: Mapped[CustomerClassification] = mapped_column(
        Enum(CustomerClassification, native_enum=False, length=1),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="classification_history")

    def __repr__(self) -> str:
        return (
            f"<CustomerClassificationHistory id={self.id} "
            f"customer_id={self.customer_id} "
            f"classification={self.classification} "
            f"snapshot_date={self.snapshot_date}>"
        )
