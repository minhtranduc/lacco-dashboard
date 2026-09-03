"""Model nhóm bảng bảo mật/audit: users, login_history, audit_log,
import_history.

Bắt buộc theo CLAUDE.md mục 6: mật khẩu dùng bcrypt (hash lưu ở
`users.password_hash`, việc hash thực hiện ở `src/auth/`, KHÔNG ở
`src/db/`), mọi phiên đăng nhập ghi `login_history`, mọi thay đổi dữ liệu
ghi `audit_log`. Nguồn thiết kế: `docs/architecture/erd-tuan-02.md`, mục
"Nhóm bảng bảo mật/audit".
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base
from src.db.models.enums import UserRole

if TYPE_CHECKING:
    # Chỉ dùng cho type-checking (mypy/IDE) — tránh import vòng lúc runtime.
    from src.db.models.dimension import Employee


class User(Base):
    """Tài khoản đăng nhập hệ thống. `password_hash` PHẢI được tạo bằng
    bcrypt ở tầng `src/auth/` — model này chỉ lưu trữ, không tự hash.

    `employee_id` cho phép NULL — giả định có tài khoản hệ thống (VD: Admin
    kỹ thuật) không gắn với 1 nhân viên nghiệp vụ cụ thể trong `employee`.
    CHƯA được COO xác nhận, xem mục 9 của "Việc cần xác nhận" trong
    `erd-tuan-02.md" — nếu xác nhận mọi tài khoản đều bắt buộc gắn nhân
    viên thì cần bỏ nullable ở cột này.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Bcrypt hash thường dài 60 ký tự — 255 để có khoảng đệm an toàn.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20), nullable=False
    )
    # Nullable — xem mục 9, erd-tuan-02.md.
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employee.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    employee: Mapped["Employee | None"] = relationship(back_populates="user_account")
    login_history: Mapped[list["LoginHistory"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")
    import_history: Mapped[list["ImportHistory"]] = relationship(
        back_populates="imported_by_user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


class LoginHistory(Base):
    """Lịch sử đăng nhập — ghi MỌI phiên đăng nhập (kể cả thất bại), bắt
    buộc theo CLAUDE.md mục 6.
    """

    __tablename__ = "login_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    login_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # 45 ký tự đủ chứa IPv6; cho phép NULL nếu không xác định được IP nguồn
    # (fallback kỹ thuật, không phải yêu cầu nghiệp vụ).
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    user: Mapped["User"] = relationship(back_populates="login_history")

    def __repr__(self) -> str:
        return (
            f"<LoginHistory id={self.id} user_id={self.user_id} success={self.success}>"
        )


class AuditLog(Base):
    """Lịch sử thay đổi dữ liệu — ghi MỌI thay đổi dữ liệu, bắt buộc theo
    CLAUDE.md mục 6.

    `action` dùng kiểu `String` placeholder — danh sách giá trị cụ thể (VD
    create/update/delete) CHƯA được xác nhận, xem mục 8 của "Việc cần xác
    nhận" trong `erd-tuan-02.md`. KHÔNG tự bịa danh sách enum cho cột này.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    # Placeholder — xem mục 8, erd-tuan-02.md.
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # ID của dòng bị thay đổi trong `table_name` — tham chiếu chung (không
    # phải FK vật lý vì bảng đích thay đổi tuỳ theo `table_name`).
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="audit_logs")

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} user_id={self.user_id} "
            f"table_name={self.table_name!r} record_id={self.record_id}>"
        )


class ImportHistory(Base):
    """Lịch sử import Excel/CSV — dùng ở bước 2.4 (import pipeline).

    `status` dùng kiểu `String` placeholder — danh sách giá trị cụ thể (VD
    success/partial/failed) CHƯA được xác nhận, xem mục 8 của "Việc cần xác
    nhận" trong `erd-tuan-02.md`. KHÔNG tự bịa danh sách enum cho cột này.
    """

    __tablename__ = "import_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    imported_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Loại dữ liệu import (VD: sales_order, cost, debt...) — chưa nằm trong
    # danh sách "cần xác nhận" chính thức của ERD, giữ String tự do để
    # không giới hạn sớm các loại import trong giai đoạn MVP.
    import_type: Mapped[str] = mapped_column(String(100), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # Placeholder — xem mục 8, erd-tuan-02.md.
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    imported_by_user: Mapped["User"] = relationship(back_populates="import_history")

    def __repr__(self) -> str:
        return (
            f"<ImportHistory id={self.id} file_name={self.file_name!r} "
            f"status={self.status!r}>"
        )
