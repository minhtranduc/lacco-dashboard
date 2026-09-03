"""Middleware tính phạm vi dữ liệu (data scope) theo RBAC — CLAUDE.md mục 6.

3 cấp quyền (`users.role`) ánh xạ sang phân loại khách hàng A/B/C: KH loại
A do Giám đốc Khối quản lý (`division`), loại B do Trưởng phòng
(`department`), loại C do nhân viên kinh doanh (`employee`) — tiêu chí
A/B/C dùng nguyên trường "Phân loại" có sẵn trong FT (`.claude/rules/
trang-thai-yeu-cau.md`, dòng "Tăng giảm loại KH (A/B/C)", đã "Đã rõ").

*** SUY LUẬN KỸ THUẬT — CHƯA ĐƯỢC COO XÁC NHẬN ***
`customer` KHÔNG có cột `employee_id`/`department_id`/`division_id` trực
tiếp trong ERD hiện tại (`src/db/models/dimension.py`). Module này SUY RA
phạm vi KH bằng UNION `customer_id` từ `sales_order`/`debt`/`price_request`
theo `employee_id` (User) / `department_id` (Manager) / `division_id`
(Admin có gắn employee) — xem `src/services/auth_service.py`. Đây là giả
định kỹ thuật để middleware CHẠY ĐƯỢC cho demo bước 3.1, KHÔNG phải nghiệp
vụ đã COO chốt — cần xác nhận trước khi dùng cho báo cáo thật.

*** ĐÃ XÁC NHẬN: vai trò "Admin" (users.role) — COO, 25/08/2026 ***
CLAUDE.md mục 6 định nghĩa `users.role = Admin` là "quản trị hệ thống" —
KHÁC với "Giám đốc Khối" (đó là vai trò nghiệp vụ theo `division`, không
map 1-1 vào `users.role`). COO đã xác nhận 25/08/2026: **Admin luôn xem
toàn bộ dữ liệu (`unrestricted=True`), KHÔNG giới hạn theo Khối/Phòng dù
tài khoản Admin có gắn `employee_id` hay không** — khác với Manager/User
vốn vẫn giới hạn theo Khối/Phòng/A-B-C như thiết kế ban đầu. Đây KHÔNG
còn là suy luận kỹ thuật, không cần re-confirm lại nữa.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from src.db.models.enums import CustomerClassification, UserRole
from src.services import auth_service
from src.services.db_connection import get_engine


@dataclass(frozen=True)
class DataScope:
    """Kết quả tính phạm vi dữ liệu cho 1 user đang đăng nhập."""

    user_id: int
    username: str
    role: UserRole
    employee_id: int | None
    department_id: int | None
    division_id: int | None
    classification_hint: CustomerClassification | None
    customer_ids: frozenset[int]
    unrestricted: bool
    description: str


def compute_data_scope(user_id: int, *, engine=None) -> DataScope:
    """Tính phạm vi khách hàng mà 1 user được phép xem, theo role +
    Khối/Phòng/NV. Xem docstring module để biết đầy đủ các suy luận/giả
    định kỹ thuật CHƯA được COO xác nhận.

    Parameters
    ----------
    user_id : int
        `users.id` của user đang đăng nhập.
    engine : sqlalchemy.Engine, optional
        Cho phép truyền engine riêng (dùng trong test) — mặc định dùng
        `src.services.db_connection.get_engine()`.

    Raises
    ------
    ValueError
        Nếu không tìm thấy user tương ứng.
    """
    engine = engine or get_engine()
    user = auth_service.fetch_user_by_id(engine, user_id)
    if user is None:
        raise ValueError(f"Không tìm thấy user id={user_id}")

    role = UserRole(user["role"])
    employee_id = user["employee_id"]
    username = user["username"]

    if role == UserRole.ADMIN:
        # COO xác nhận 25/08/2026: Admin luôn xem toàn bộ dữ liệu, không
        # giới hạn theo Khối/Phòng — BỎ QUA hoàn toàn việc có/không có
        # employee_id (khác Manager/User, vẫn giới hạn theo Khối/Phòng/ABC
        # như cũ). employee_id/department_id/division_id vẫn được điền vào
        # DataScope nếu có, chỉ để hiển thị thông tin — KHÔNG dùng để giới
        # hạn phạm vi.
        context = (
            auth_service.fetch_employee_context(engine, employee_id)
            if employee_id is not None
            else None
        )
        logger.info(
            "user_id={} role=Admin -> unrestricted=True (COO xác nhận "
            "25/08/2026: Admin luôn xem toàn bộ, không giới hạn theo "
            "Khối/Phòng dù có gắn employee_id={}).",
            user_id,
            employee_id,
        )
        all_ids = auth_service.fetch_all_customer_ids(engine)
        return DataScope(
            user_id=user_id,
            username=username,
            role=role,
            employee_id=employee_id,
            department_id=context["department_id"] if context else None,
            division_id=context["division_id"] if context else None,
            classification_hint=None,
            customer_ids=frozenset(all_ids),
            unrestricted=True,
            description=(
                "Admin quản trị hệ thống — xem toàn bộ khách hàng (COO xác "
                "nhận 25/08/2026: không giới hạn theo Khối/Phòng dù có gắn "
                "employee_id)."
            ),
        )

    if employee_id is None:
        logger.warning(
            "user_id={} role={} không có employee_id -> không thể tính "
            "phạm vi Khối/Phòng/NV, trả về phạm vi rỗng.",
            user_id,
            role.value,
        )
        return DataScope(
            user_id=user_id,
            username=username,
            role=role,
            employee_id=None,
            department_id=None,
            division_id=None,
            classification_hint=None,
            customer_ids=frozenset(),
            unrestricted=False,
            description=(
                f"Tài khoản role={role.value} không gắn employee_id -> "
                "không xác định được Khối/Phòng/NV -> phạm vi rỗng."
            ),
        )

    context = auth_service.fetch_employee_context(engine, employee_id)
    if context is None:
        logger.error(
            "user_id={} employee_id={} không tìm thấy employee/department "
            "tương ứng -> phạm vi rỗng.",
            user_id,
            employee_id,
        )
        return DataScope(
            user_id=user_id,
            username=username,
            role=role,
            employee_id=employee_id,
            department_id=None,
            division_id=None,
            classification_hint=None,
            customer_ids=frozenset(),
            unrestricted=False,
            description=(
                "Không tìm thấy dữ liệu employee/department tương ứng -> phạm vi rỗng."
            ),
        )

    department_id = context["department_id"]
    division_id = context["division_id"]

    if role == UserRole.USER:
        customer_ids = auth_service.fetch_customer_ids_for_employee(engine, employee_id)
        classification_hint = CustomerClassification.C
        description = (
            "User (nhân viên kinh doanh) — KH loại C, chỉ xem KH do "
            f"employee_id={employee_id} phụ trách (suy ra từ sales_order/"
            "debt/price_request)."
        )
    else:  # UserRole.MANAGER — role Admin đã return sớm ở trên (unrestricted)
        customer_ids = auth_service.fetch_customer_ids_for_department(
            engine, department_id
        )
        classification_hint = CustomerClassification.B
        description = (
            "Manager (Trưởng phòng) — KH loại B, xem KH thuộc "
            f"department_id={department_id} (suy ra từ sales_order/debt/"
            "price_request)."
        )

    return DataScope(
        user_id=user_id,
        username=username,
        role=role,
        employee_id=employee_id,
        department_id=department_id,
        division_id=division_id,
        classification_hint=classification_hint,
        customer_ids=frozenset(customer_ids),
        unrestricted=False,
        description=description,
    )
