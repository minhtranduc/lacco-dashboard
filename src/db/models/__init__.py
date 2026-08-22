"""SQLAlchemy declarative models — Data layer của Dashboard LACCO.

Import tất cả model ở đây để đảm bảo mọi class được đăng ký vào
`Base.metadata` khi package này được import — cần thiết để Alembic
autogenerate (bước 2.3) phát hiện đầy đủ 18 bảng, và để các quan hệ
`relationship()` tham chiếu chéo giữa `dimension.py`, `business.py`,
`security.py` được resolve đúng theo tên class.

Chia 3 module theo đúng 3 nhóm bảng trong
`docs/architecture/erd-tuan-02.md`:

- `dimension.py` — bảng danh mục: Division, Department, Employee, Service,
  Customer, Supplier.
- `business.py` — bảng nghiệp vụ: SalesOrder, PriceRequest,
  SupplierEvaluation, Cost, Budget, PersonnelCost, Debt,
  CustomerClassificationHistory.
- `security.py` — bảng bảo mật/audit: User, LoginHistory, AuditLog,
  ImportHistory.
"""

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
from src.db.models.security import AuditLog, ImportHistory, LoginHistory, User

__all__ = [
    "Base",
    # dimension
    "Division",
    "Department",
    "Employee",
    "Service",
    "Customer",
    "Supplier",
    # business
    "SalesOrder",
    "PriceRequest",
    "SupplierEvaluation",
    "Cost",
    "Budget",
    "PersonnelCost",
    "Debt",
    "CustomerClassificationHistory",
    # security
    "User",
    "LoginHistory",
    "AuditLog",
    "ImportHistory",
]
