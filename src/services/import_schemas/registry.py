"""Registry trung tâm: gắn (tên bảng) → (SQLAlchemy model, Pandera schema,
khoá ngoại cần kiểm tra tồn tại thật trong DB, cột kiểu Decimal cần ép kiểu
trước khi insert).

Đây là "tham số hoá theo bảng" mà framework generic
`src/services/import_pipeline.py` đọc vào — KHÔNG viết 18 hàm import riêng
lẻ, chỉ có 1 bộ hàm dùng chung, khác nhau ở entry trong registry này.

Thứ tự khai báo trong `IMPORT_REGISTRY` PHẢI đúng thứ tự phụ thuộc khoá
ngoại (bảng danh mục trước, bảng nghiệp vụ tham chiếu sau) — dùng làm thứ
tự mặc định khi chạy import toàn bộ 18 bảng dữ liệu mẫu (bước 2.4, mục 7).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.db.models.base import Base
from src.db.models.business import (
    Budget,
    Cost,
    CustomerClassificationHistory,
    Debt,
    PersonnelCost,
    PriceRequest,
    SalesOrder,
    SupplierEvaluation,
)
from src.db.models.dimension import (
    Customer,
    Department,
    Division,
    Employee,
    Service,
    Supplier,
)
from src.db.models.security import AuditLog, LoginHistory, User
from src.services.import_schemas import (
    business_schemas as bs,
    dimension_schemas as ds,
    security_schemas as ss,
)


@dataclass(frozen=True)
class ImportTableConfig:
    """Cấu hình import cho 1 bảng — tham số hoá cho framework generic.

    Attributes:
        table_name: tên bảng đích trong MySQL (khớp `__tablename__` model).
        model: class SQLAlchemy model tương ứng (từ `src/db/models/`).
        schema: Pandera `DataFrameSchema` dùng để validate file trước khi
            load (kiểu dữ liệu, not-null, giá trị hợp lệ).
        foreign_keys: map {tên cột FK trong file: model bảng cha}. Dùng để
            kiểm tra khoá ngoại có THỰC SỰ tồn tại trong bảng cha bằng
            query DB thật (`check_foreign_keys()` trong
            `import_pipeline.py`) — không chỉ dựa vào kiểu dữ liệu int.
        decimal_columns: tên các cột kiểu `Numeric` trong model — pipeline
            sẽ ép các cột này từ `float` (sau khi Pandera validate) sang
            `decimal.Decimal` trước khi insert, tránh sai số nhị phân của
            `float` khi ghi vào cột tiền tệ.
    """

    table_name: str
    model: type[Base]
    schema: object
    foreign_keys: dict[str, type[Base]] = field(default_factory=dict)
    decimal_columns: tuple[str, ...] = ()


# Thứ tự dict = thứ tự import mặc định khi chạy toàn bộ (bước 2.4, mục 7).
# 6 bảng danh mục trước, rồi users (cần employee đã có), rồi 8 bảng nghiệp
# vụ, cuối cùng login_history/audit_log (cần users đã có).
IMPORT_REGISTRY: dict[str, ImportTableConfig] = {
    # --- Nhóm danh mục (dimension) ---
    "division": ImportTableConfig(
        table_name="division",
        model=Division,
        schema=ds.division_schema,
    ),
    "department": ImportTableConfig(
        table_name="department",
        model=Department,
        schema=ds.department_schema,
        foreign_keys={"division_id": Division},
    ),
    "employee": ImportTableConfig(
        table_name="employee",
        model=Employee,
        schema=ds.employee_schema,
        foreign_keys={"department_id": Department},
    ),
    "service": ImportTableConfig(
        table_name="service",
        model=Service,
        schema=ds.service_schema,
    ),
    "customer": ImportTableConfig(
        table_name="customer",
        model=Customer,
        schema=ds.customer_schema,
    ),
    "supplier": ImportTableConfig(
        table_name="supplier",
        model=Supplier,
        schema=ds.supplier_schema,
    ),
    # --- users cần employee đã tồn tại (employee_id nullable nhưng phần
    # lớn dữ liệu mẫu sẽ gắn nhân viên thật để test FK check có tác dụng) ---
    "users": ImportTableConfig(
        table_name="users",
        model=User,
        schema=ss.users_schema,
        foreign_keys={"employee_id": Employee},
    ),
    # --- Nhóm nghiệp vụ (fact) — đúng thứ tự nêu trong yêu cầu bước 2.4 ---
    "sales_order": ImportTableConfig(
        table_name="sales_order",
        model=SalesOrder,
        schema=bs.sales_order_schema,
        foreign_keys={
            "customer_id": Customer,
            "service_id": Service,
            "employee_id": Employee,
        },
        decimal_columns=("revenue", "order_cost"),
    ),
    "price_request": ImportTableConfig(
        table_name="price_request",
        model=PriceRequest,
        schema=bs.price_request_schema,
        foreign_keys={
            "service_id": Service,
            "employee_id": Employee,
            "customer_id": Customer,
            "sales_order_id": SalesOrder,
        },
    ),
    "supplier_evaluation": ImportTableConfig(
        table_name="supplier_evaluation",
        model=SupplierEvaluation,
        schema=bs.supplier_evaluation_schema,
        foreign_keys={
            "supplier_id": Supplier,
            "service_id": Service,
            "employee_id": Employee,
        },
        decimal_columns=("score",),
    ),
    "cost": ImportTableConfig(
        table_name="cost",
        model=Cost,
        schema=bs.cost_schema,
        foreign_keys={"division_id": Division},
        decimal_columns=("amount",),
    ),
    "budget": ImportTableConfig(
        table_name="budget",
        model=Budget,
        schema=bs.budget_schema,
        foreign_keys={"division_id": Division},
        decimal_columns=("amount",),
    ),
    "personnel_cost": ImportTableConfig(
        table_name="personnel_cost",
        model=PersonnelCost,
        schema=bs.personnel_cost_schema,
        decimal_columns=("amount",),
    ),
    "debt": ImportTableConfig(
        table_name="debt",
        model=Debt,
        schema=bs.debt_schema,
        foreign_keys={
            "customer_id": Customer,
            "division_id": Division,
            "department_id": Department,
            "employee_id": Employee,
        },
        decimal_columns=("amount",),
    ),
    "customer_classification_history": ImportTableConfig(
        table_name="customer_classification_history",
        model=CustomerClassificationHistory,
        schema=bs.customer_classification_history_schema,
        foreign_keys={"customer_id": Customer},
    ),
    # --- Nhóm bảo mật/audit còn lại (cần users đã tồn tại) ---
    "login_history": ImportTableConfig(
        table_name="login_history",
        model=LoginHistory,
        schema=ss.login_history_schema,
        foreign_keys={"user_id": User},
    ),
    "audit_log": ImportTableConfig(
        table_name="audit_log",
        model=AuditLog,
        schema=ss.audit_log_schema,
        foreign_keys={"user_id": User},
    ),
}

# Thứ tự tường minh dùng khi chạy import toàn bộ — độc lập với thứ tự dict
# (dict Python giữ thứ tự insertion nhưng liệt kê tường minh ở đây để không
# ai vô tình đổi ý nghĩa khi sửa dict phía trên).
ORDERED_TABLE_NAMES: tuple[str, ...] = (
    "division",
    "department",
    "employee",
    "service",
    "customer",
    "supplier",
    "users",
    "sales_order",
    "price_request",
    "supplier_evaluation",
    "cost",
    "budget",
    "personnel_cost",
    "debt",
    "customer_classification_history",
    "login_history",
    "audit_log",
)
