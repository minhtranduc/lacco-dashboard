"""Service tính KPI báo cáo Pricing — 2 báo cáo con:

1. **Thành đơn** = số lượng `price_request` đã chốt (`is_won = True` HOẶC
   `sales_order_id IS NOT NULL`) / tổng số `price_request` — theo Khối/
   Phòng/NV phụ trách, theo dịch vụ, theo khách hàng, và xu hướng theo
   thời gian.
2. **Nhà cung cấp** — điểm đánh giá trung bình (`supplier_evaluation.score`)
   theo nhà cung cấp, theo thời gian, có thể group theo dịch vụ.

Nguồn yêu cầu: `.claude/rules/trang-thai-yeu-cau.md`, nhóm "Pricing" — cả 2
báo cáo con ("Thành đơn", "Nhà cung cấp") đã "Đã rõ".

Theo CLAUDE.md mục 2 (tách lớp): module này chỉ chứa truy vấn SQLAlchemy
(parameterized, cấm nối chuỗi SQL thủ công — CLAUDE.md mục 4) + tính toán
KPI, KHÔNG chứa code Streamlit/Plotly. Trang `src/app/pages/4_Bao_cao_
Pricing.py` chỉ gọi các hàm ở đây rồi vẽ biểu đồ.

*** BẮT BUỘC RBAC — KHÁC với các module trước (CLAUDE.md mục 6) ***
`price_request`/`supplier_evaluation` KHÔNG có khách hàng làm chủ thể phân
quyền chính (`price_request.customer_id` nullable, `supplier_evaluation`
không có cột khách hàng nào cả). Chủ thể phân quyền ở module này là NHÂN
VIÊN PRICING phụ trách (`employee_id` trên cả 2 bảng). Vì vậy module này
KHÔNG dùng `scope.customer_ids` (khác `report_kinh_doanh.py`/
`report_khach_hang.py`) — mọi hàm join sang `Employee` để lấy
`department_id`, rồi lọc:
- Admin (`scope.unrestricted is True`): xem toàn bộ, không lọc.
- Manager: lọc `Employee.department_id == scope.department_id`.
- User: lọc `employee_id == scope.employee_id` (trực tiếp trên bảng
  `price_request`/`supplier_evaluation`, không cần qua Employee vì đã có
  cột `employee_id` sẵn — join Employee vẫn được giữ lại để dùng chung 1
  câu lệnh `_apply_org_scope_filter` áp Manager/User nhất quán).

`scope.department_id`/`scope.employee_id`/`scope.division_id` đã có sẵn
trực tiếp trên `DataScope` (`src/auth/scope.py`) — KHÔNG cần tự suy luận
lại qua join `employee` để lấy các giá trị này cho phía "user đang đăng
nhập"; việc join `Employee` trong các câu truy vấn dưới đây là để lấy
`department_id` của NHÂN VIÊN PHỤ TRÁCH request/đánh giá (dữ liệu đang truy
vấn), không phải của user đang xem báo cáo.

*** customer_id NULL trong `price_request` ***
`price_request.customer_id` cho phép NULL (báo giá cho khách hàng tiềm
năng chưa có mã, xem docstring `PriceRequest` trong
`src/db/models/business.py`). `get_win_rate_by_customer()` dùng LEFT JOIN
+ group theo `Customer.id` — các dòng NULL tự gộp thành 1 nhóm duy nhất
trong SQL `GROUP BY` (NULL được coi là 1 giá trị nhóm), sau đó gán nhãn
hiển thị "Khách hàng tiềm năng/chưa có mã" ở tầng DataFrame (KHÔNG loại bỏ
khỏi kết quả, KHÔNG lỗi/crash).

*** Thang điểm `supplier_evaluation.score`: 0-100 — ĐÃ COO XÁC NHẬN
22/08/2026 *** — ghi chú này theo đúng nội dung giao việc (báo cáo bước
Tuần 5, xây module Pricing). Lưu ý: docstring model `SupplierEvaluation`
trong `src/db/models/business.py` (viết từ Tuần 2, bước 2.3) vẫn ghi "chưa
được xác nhận trong phỏng vấn nghiệp vụ" — đây là docstring CŨ, CHƯA được
cập nhật để phản ánh xác nhận 22/08/2026 (module này không tự sửa file đó,
ngoài phạm vi được giao — chỉ ghi chú lại ở đây để tránh nhầm lẫn cho người
đọc code sau này). Điểm số dùng trực tiếp (không cần chuẩn hoá lại thang
đo) trong các hàm bên dưới.

*** ĐÃ XÁC NHẬN: quy ước tuần ISO 8601 cho biểu đồ xu hướng (COO,
07/09/2026) *** — áp dụng nhất quán với `report_kinh_doanh.py`
(`get_revenue_profit_trend`): `granularity="week"` dùng
`func.date_format(..., "%x-%v")`.

*** CHƯA XÁC NHẬN — cần hỏi lại nếu ảnh hưởng ***
- Rủi ro 1 khách hàng thuộc phạm vi nhiều NV/Phòng khác nhau (đã ghi nhận ở
  `report_kinh_doanh.py`) áp dụng cho `scope.customer_ids` — module này
  KHÔNG dùng `scope.customer_ids` nên rủi ro đó không áp dụng trực tiếp,
  nhưng module này có RỦI RO TƯƠNG TỰ ở cấp NHÂN VIÊN: nếu 1 `employee_id`
  đổi phòng ban theo thời gian, dữ liệu lịch sử (`price_request`/
  `supplier_evaluation` cũ) vẫn được tính vào phòng ban HIỆN TẠI của nhân
  viên đó (không có snapshot lịch sử phòng ban) — CHƯA hỏi COO/Trưởng
  phòng Vận hành về cách xử lý trường hợp này, không tự chọn cách xử lý.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from loguru import logger
from sqlalchemy import Engine, case, false, func, or_, select
from sqlalchemy.orm import Session

from src.auth.scope import DataScope
from src.db.models import (
    Customer,
    Department,
    Division,
    Employee,
    PriceRequest,
    Service,
    Supplier,
    SupplierEvaluation,
)
from src.db.models.enums import UserRole
from src.services.db_connection import get_engine

_CUSTOMER_PLACEHOLDER_LABEL = "Khách hàng tiềm năng/chưa có mã"
"""Nhãn hiển thị cho nhóm `price_request.customer_id IS NULL` — báo giá cho
khách hàng tiềm năng chưa có mã trong bảng `customer` (xem docstring
module)."""


def _won_expr():
    """Biểu thức SQL xác định 1 `price_request` đã "chốt đơn" — theo công
    thức đã "Đã rõ" (`.claude/rules/trang-thai-yeu-cau.md`, dòng "Thành
    đơn"): `is_won = True` HOẶC `sales_order_id IS NOT NULL` (2 điều kiện
    OR, không phải AND — 1 request có thể được đánh dấu `is_won` trước khi
    `sales_order_id` được điền, hoặc ngược lại tuỳ quy trình vận hành thực
    tế)."""
    return or_(PriceRequest.is_won.is_(True), PriceRequest.sales_order_id.isnot(None))


def _scope_is_empty(scope: DataScope) -> bool:
    """Kiểm tra scope có rỗng hay không, theo chủ thể phân quyền của module
    này (NHÂN VIÊN, không phải khách hàng — xem docstring module).

    Admin: không bao giờ rỗng. Manager: rỗng nếu `department_id is None`.
    User: rỗng nếu `employee_id is None`. Khớp với logic
    `compute_data_scope()` (`src/auth/scope.py`) — khi `employee_id` là
    `None` với role Manager/User, `department_id` cũng luôn `None`.
    """
    if scope.unrestricted:
        return False
    if scope.role == UserRole.MANAGER:
        return scope.department_id is None
    return scope.employee_id is None


def _apply_org_scope_filter(stmt, scope: DataScope, employee_id_col):
    """Áp dụng lọc RBAC theo NHÂN VIÊN phụ trách (CLAUDE.md mục 6, xem
    docstring module) — dùng chung cho mọi hàm báo cáo Pricing bên dưới.

    Args:
        stmt: câu `select()` đã JOIN sẵn `Employee` (bắt buộc — dùng để lọc
            theo `Employee.department_id` cho Manager).
        scope: phạm vi dữ liệu của user đang đăng nhập.
        employee_id_col: cột `employee_id` của bảng đang truy vấn
            (`PriceRequest.employee_id` hoặc `SupplierEvaluation.
            employee_id`) — dùng để lọc trực tiếp cho User.

    Admin (`scope.unrestricted`): không lọc. Manager: lọc theo
    `Employee.department_id == scope.department_id`. User: lọc theo
    `employee_id_col == scope.employee_id`. Nếu thiếu `department_id`/
    `employee_id` tương ứng (trường hợp lẽ ra đã bị chặn sớm bởi
    `_scope_is_empty`), trả về điều kiện luôn `False` để không vô tình lộ
    dữ liệu ngoài phạm vi.
    """
    if scope.unrestricted:
        return stmt
    if scope.role == UserRole.MANAGER:
        if scope.department_id is None:
            return stmt.where(false())
        return stmt.where(Employee.department_id == scope.department_id)
    if scope.employee_id is None:
        return stmt.where(false())
    return stmt.where(employee_id_col == scope.employee_id)


def _apply_date_filter(stmt, date_from: date | None, date_to: date | None, date_col):
    """Áp dụng lọc khoảng thời gian tuỳ chọn lên `date_col` (cột ngày của
    bảng đang truy vấn — `PriceRequest.request_date` hoặc
    `SupplierEvaluation.period`)."""
    if date_from is not None:
        stmt = stmt.where(date_col >= date_from)
    if date_to is not None:
        stmt = stmt.where(date_col <= date_to)
    return stmt


def _add_win_rate_column(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm cột `win_rate` (= `won_requests / total_requests`) vào DataFrame
    đã có sẵn 2 cột đó.

    *** QUYẾT ĐỊNH chia cho 0: trả về `0.0`, KHÔNG trả `None` *** — cùng
    quy ước với `_add_profit_margin_column` ở `report_kinh_doanh.py` (dùng
    trực tiếp cho `st.metric`/định dạng `f"{x:.1%}"`, tránh lỗi định dạng
    chuỗi). Vector hoá (không `apply(axis=1)`) để giữ hiệu năng.
    """
    df["win_rate"] = (df["won_requests"] / df["total_requests"]).where(
        df["total_requests"] != 0, 0.0
    )
    return df


def _period_expr(date_col, granularity: str):
    """Biểu thức SQL gộp `date_col` theo Tháng/Tuần — giữ nguyên quy ước đã
    "Đã rõ" ở `report_kinh_doanh.py::get_revenue_profit_trend` (ISO week,
    COO xác nhận 07/09/2026): `"month"` -> `date_format(date_col,
    "%Y-%m-01")`; `"week"` -> `date_format(date_col, "%x-%v")`."""
    if granularity == "month":
        return func.date_format(date_col, "%Y-%m-01")
    return func.date_format(date_col, "%x-%v")


# ---------------------------------------------------------------------------
# Báo cáo con 1: Thành đơn
# ---------------------------------------------------------------------------


def get_win_rate_by_org(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Tỷ lệ thành đơn (`price_request`) gộp theo phân cấp Khối-Phòng-NV phụ
    trách, đã lọc theo RBAC (NHÂN VIÊN — xem docstring module).

    Join `price_request.employee_id -> employee -> department -> division`.
    Trả về dữ liệu ở mức chi tiết nhất (1 dòng/nhân viên) — trang Streamlit
    tự quyết định cách gộp/drill-down (theo Khối/Phòng/NV) từ cùng 1
    DataFrame này để tránh gọi DB nhiều lần (cùng pattern
    `get_revenue_profit_by_org` ở `report_kinh_doanh.py`).

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn (mặc định `get_engine()`).
        date_from, date_to: Lọc theo `request_date`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `division_id`, `division_name`,
        `department_id`, `department_name`, `employee_id`, `employee_name`,
        `total_requests`, `won_requests`, `win_rate` (= `won_requests /
        total_requests`, `0.0` khi `total_requests == 0`) — sắp xếp giảm
        dần theo `total_requests`. Trả về DataFrame rỗng (đúng cột) nếu
        scope rỗng theo `_scope_is_empty`.
    """
    engine = engine or get_engine()
    columns = [
        "division_id",
        "division_name",
        "department_id",
        "department_name",
        "employee_id",
        "employee_name",
        "total_requests",
        "won_requests",
        "win_rate",
    ]

    if _scope_is_empty(scope):
        logger.warning(
            "get_win_rate_by_org: scope rỗng (user_id={}) -> trả về DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    stmt = (
        select(
            Division.id.label("division_id"),
            Division.name.label("division_name"),
            Department.id.label("department_id"),
            Department.name.label("department_name"),
            Employee.id.label("employee_id"),
            Employee.full_name.label("employee_name"),
            func.count(PriceRequest.id).label("total_requests"),
            func.sum(case((_won_expr(), 1), else_=0)).label("won_requests"),
        )
        .join(Employee, PriceRequest.employee_id == Employee.id)
        .join(Department, Employee.department_id == Department.id)
        .join(Division, Department.division_id == Division.id)
        .group_by(
            Division.id,
            Division.name,
            Department.id,
            Department.name,
            Employee.id,
            Employee.full_name,
        )
    )
    stmt = _apply_org_scope_filter(stmt, scope, PriceRequest.employee_id)
    stmt = _apply_date_filter(stmt, date_from, date_to, PriceRequest.request_date)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns[:-1])
    df["total_requests"] = df["total_requests"].astype(int)
    df["won_requests"] = df["won_requests"].astype(int)
    df = _add_win_rate_column(df)
    df = df.sort_values("total_requests", ascending=False).reset_index(drop=True)
    logger.info(
        "get_win_rate_by_org: user_id={} -> {} dòng (Khối-Phòng-NV).",
        scope.user_id,
        len(df),
    )
    return df


def get_win_rate_by_service(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Tỷ lệ thành đơn gộp theo dịch vụ (`service`), đã lọc theo RBAC.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        date_from, date_to: Lọc theo `request_date`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `service_id`, `service_name`,
        `total_requests`, `won_requests`, `win_rate` — sắp xếp giảm dần
        theo `total_requests`.
    """
    engine = engine or get_engine()
    columns = [
        "service_id",
        "service_name",
        "total_requests",
        "won_requests",
        "win_rate",
    ]

    if _scope_is_empty(scope):
        logger.warning(
            "get_win_rate_by_service: scope rỗng (user_id={}) -> trả về "
            "DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    stmt = (
        select(
            Service.id.label("service_id"),
            Service.name.label("service_name"),
            func.count(PriceRequest.id).label("total_requests"),
            func.sum(case((_won_expr(), 1), else_=0)).label("won_requests"),
        )
        .join(PriceRequest, PriceRequest.service_id == Service.id)
        .join(Employee, PriceRequest.employee_id == Employee.id)
        .group_by(Service.id, Service.name)
    )
    stmt = _apply_org_scope_filter(stmt, scope, PriceRequest.employee_id)
    stmt = _apply_date_filter(stmt, date_from, date_to, PriceRequest.request_date)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns[:-1])
    df["total_requests"] = df["total_requests"].astype(int)
    df["won_requests"] = df["won_requests"].astype(int)
    df = _add_win_rate_column(df)
    df = df.sort_values("total_requests", ascending=False).reset_index(drop=True)
    logger.info(
        "get_win_rate_by_service: user_id={} -> {} dịch vụ.", scope.user_id, len(df)
    )
    return df


def get_win_rate_by_customer(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    top_n: int | None = None,
) -> pd.DataFrame:
    """Tỷ lệ thành đơn gộp theo khách hàng (`customer`), đã lọc theo RBAC.

    `price_request.customer_id` cho phép NULL (báo giá cho khách hàng tiềm
    năng) — dùng LEFT JOIN nên các dòng NULL tự gộp vào 1 nhóm duy nhất
    trong SQL `GROUP BY` (xem docstring module), sau đó gán nhãn hiển thị
    `_CUSTOMER_PLACEHOLDER_LABEL` ở tầng DataFrame — KHÔNG loại khỏi kết
    quả, KHÔNG lỗi/crash.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        date_from, date_to: Lọc theo `request_date`, tuỳ chọn.
        top_n: Nếu truyền, chỉ giữ `top_n` khách hàng có `total_requests`
            cao nhất.

    Returns:
        DataFrame với các cột: `customer_id` (`None` cho nhóm khách hàng
        tiềm năng), `customer_code`, `customer_name` (đã gán nhãn placeholder
        cho nhóm NULL), `total_requests`, `won_requests`, `win_rate` — sắp
        xếp giảm dần theo `total_requests`.
    """
    engine = engine or get_engine()
    columns = [
        "customer_id",
        "customer_code",
        "customer_name",
        "total_requests",
        "won_requests",
        "win_rate",
    ]

    if _scope_is_empty(scope):
        logger.warning(
            "get_win_rate_by_customer: scope rỗng (user_id={}) -> trả về "
            "DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    stmt = (
        select(
            Customer.id.label("customer_id"),
            Customer.code.label("customer_code"),
            Customer.name.label("customer_name"),
            func.count(PriceRequest.id).label("total_requests"),
            func.sum(case((_won_expr(), 1), else_=0)).label("won_requests"),
        )
        .select_from(PriceRequest)
        .outerjoin(Customer, PriceRequest.customer_id == Customer.id)
        .join(Employee, PriceRequest.employee_id == Employee.id)
        .group_by(Customer.id, Customer.code, Customer.name)
    )
    stmt = _apply_org_scope_filter(stmt, scope, PriceRequest.employee_id)
    stmt = _apply_date_filter(stmt, date_from, date_to, PriceRequest.request_date)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns[:-1])
    null_mask = df["customer_id"].isna()
    if null_mask.any():
        df.loc[null_mask, "customer_code"] = "—"
        df.loc[null_mask, "customer_name"] = _CUSTOMER_PLACEHOLDER_LABEL
    df["total_requests"] = df["total_requests"].astype(int)
    df["won_requests"] = df["won_requests"].astype(int)
    df = _add_win_rate_column(df)
    df = df.sort_values("total_requests", ascending=False).reset_index(drop=True)
    if top_n is not None:
        df = df.head(top_n).reset_index(drop=True)
    logger.info(
        "get_win_rate_by_customer: user_id={} -> {} khách hàng (kèm nhóm "
        "'{}' nếu có customer_id NULL, top_n={}).",
        scope.user_id,
        len(df),
        _CUSTOMER_PLACEHOLDER_LABEL,
        top_n,
    )
    return df


def get_win_rate_trend(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    granularity: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Xu hướng tỷ lệ thành đơn theo thời gian, gộp theo tháng hoặc tuần
    ISO của `price_request.request_date` (xem `_period_expr` — cùng quy ước
    đã "Đã rõ" ở `report_kinh_doanh.py::get_revenue_profit_trend`), đã lọc
    theo RBAC.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        granularity: `"month"` (mặc định) hoặc `"week"`.
        date_from, date_to: Lọc theo `request_date`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `period`, `total_requests`, `won_requests`,
        `win_rate` — sắp xếp tăng dần theo `period`.

    Raises:
        ValueError: nếu `granularity` không phải `"month"`/`"week"`.
    """
    if granularity not in ("month", "week"):
        raise ValueError(
            f"granularity phải là 'month' hoặc 'week', nhận: {granularity!r}"
        )

    engine = engine or get_engine()
    columns = ["period", "total_requests", "won_requests", "win_rate"]

    if _scope_is_empty(scope):
        logger.warning(
            "get_win_rate_trend: scope rỗng (user_id={}) -> trả về DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    period_expr = _period_expr(PriceRequest.request_date, granularity)

    stmt = (
        select(
            period_expr.label("period"),
            func.count(PriceRequest.id).label("total_requests"),
            func.sum(case((_won_expr(), 1), else_=0)).label("won_requests"),
        )
        .join(Employee, PriceRequest.employee_id == Employee.id)
        .group_by(period_expr)
        .order_by(period_expr)
    )
    stmt = _apply_org_scope_filter(stmt, scope, PriceRequest.employee_id)
    stmt = _apply_date_filter(stmt, date_from, date_to, PriceRequest.request_date)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns[:-1])
    df["total_requests"] = df["total_requests"].astype(int)
    df["won_requests"] = df["won_requests"].astype(int)
    df = _add_win_rate_column(df)
    if granularity == "month":
        df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values("period").reset_index(drop=True)
    logger.info(
        "get_win_rate_trend: user_id={} granularity={} -> {} kỳ.",
        scope.user_id,
        granularity,
        len(df),
    )
    return df


# ---------------------------------------------------------------------------
# Báo cáo con 2: Nhà cung cấp
# ---------------------------------------------------------------------------


def get_supplier_score_by_supplier(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    group_by_service: bool = False,
) -> pd.DataFrame:
    """Điểm đánh giá trung bình theo nhà cung cấp (`supplier_evaluation.
    score`, thang 0-100 — COO xác nhận 22/08/2026), đã lọc theo RBAC.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        date_from, date_to: Lọc theo `period`, tuỳ chọn.
        group_by_service: Nếu `True`, group thêm theo dịch vụ (1 dòng/
            nhà cung cấp/dịch vụ) — nếu `False` (mặc định), gộp toàn bộ
            dịch vụ (1 dòng/nhà cung cấp).

    Returns:
        DataFrame với các cột: `supplier_id`, `supplier_name` (kèm
        `service_id`, `service_name` nếu `group_by_service=True`),
        `evaluation_count`, `avg_score` — sắp xếp giảm dần theo `avg_score`.
    """
    engine = engine or get_engine()
    columns = ["supplier_id", "supplier_name"]
    if group_by_service:
        columns += ["service_id", "service_name"]
    columns += ["evaluation_count", "avg_score"]

    if _scope_is_empty(scope):
        logger.warning(
            "get_supplier_score_by_supplier: scope rỗng (user_id={}) -> trả "
            "về DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    select_cols = [
        Supplier.id.label("supplier_id"),
        Supplier.name.label("supplier_name"),
    ]
    group_cols = [Supplier.id, Supplier.name]
    if group_by_service:
        select_cols += [
            Service.id.label("service_id"),
            Service.name.label("service_name"),
        ]
        group_cols += [Service.id, Service.name]
    select_cols += [
        func.count(SupplierEvaluation.id).label("evaluation_count"),
        func.avg(SupplierEvaluation.score).label("avg_score"),
    ]

    stmt = select(*select_cols).join(
        SupplierEvaluation, SupplierEvaluation.supplier_id == Supplier.id
    )
    if group_by_service:
        stmt = stmt.join(Service, SupplierEvaluation.service_id == Service.id)
    stmt = stmt.join(Employee, SupplierEvaluation.employee_id == Employee.id)
    stmt = stmt.group_by(*group_cols)
    stmt = _apply_org_scope_filter(stmt, scope, SupplierEvaluation.employee_id)
    stmt = _apply_date_filter(stmt, date_from, date_to, SupplierEvaluation.period)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns)
    df["evaluation_count"] = df["evaluation_count"].astype(int)
    df["avg_score"] = df["avg_score"].astype(float)
    df = df.sort_values("avg_score", ascending=False).reset_index(drop=True)
    logger.info(
        "get_supplier_score_by_supplier: user_id={} group_by_service={} -> {} dòng.",
        scope.user_id,
        group_by_service,
        len(df),
    )
    return df


def get_supplier_score_trend(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    granularity: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    supplier_id: int | None = None,
) -> pd.DataFrame:
    """Xu hướng điểm đánh giá trung bình nhà cung cấp theo thời gian, gộp
    theo tháng hoặc tuần ISO của `supplier_evaluation.period` (xem
    `_period_expr`), đã lọc theo RBAC.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        granularity: `"month"` (mặc định) hoặc `"week"`.
        date_from, date_to: Lọc theo `period`, tuỳ chọn.
        supplier_id: Nếu truyền, chỉ tính riêng 1 nhà cung cấp (dùng khi
            trang Streamlit cho chọn 1 NCC cụ thể để xem xu hướng riêng).

    Returns:
        DataFrame với các cột: `period`, `evaluation_count`, `avg_score` —
        sắp xếp tăng dần theo `period`.

    Raises:
        ValueError: nếu `granularity` không phải `"month"`/`"week"`.
    """
    if granularity not in ("month", "week"):
        raise ValueError(
            f"granularity phải là 'month' hoặc 'week', nhận: {granularity!r}"
        )

    engine = engine or get_engine()
    columns = ["period", "evaluation_count", "avg_score"]

    if _scope_is_empty(scope):
        logger.warning(
            "get_supplier_score_trend: scope rỗng (user_id={}) -> trả về "
            "DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    period_expr = _period_expr(SupplierEvaluation.period, granularity)

    stmt = (
        select(
            period_expr.label("period"),
            func.count(SupplierEvaluation.id).label("evaluation_count"),
            func.avg(SupplierEvaluation.score).label("avg_score"),
        )
        .join(Employee, SupplierEvaluation.employee_id == Employee.id)
        .group_by(period_expr)
        .order_by(period_expr)
    )
    if supplier_id is not None:
        stmt = stmt.where(SupplierEvaluation.supplier_id == supplier_id)
    stmt = _apply_org_scope_filter(stmt, scope, SupplierEvaluation.employee_id)
    stmt = _apply_date_filter(stmt, date_from, date_to, SupplierEvaluation.period)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns)
    df["evaluation_count"] = df["evaluation_count"].astype(int)
    df["avg_score"] = df["avg_score"].astype(float)
    if granularity == "month":
        df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values("period").reset_index(drop=True)
    logger.info(
        "get_supplier_score_trend: user_id={} granularity={} supplier_id={} -> {} kỳ.",
        scope.user_id,
        granularity,
        supplier_id,
        len(df),
    )
    return df


def get_supplier_list(
    scope: DataScope, *, engine: Engine | None = None
) -> pd.DataFrame:
    """Danh sách nhà cung cấp CÓ ít nhất 1 đánh giá trong phạm vi RBAC hiện
    tại — dùng để đổ dữ liệu `st.selectbox` (chọn NCC) trên trang Streamlit,
    tránh cho chọn NCC không có dữ liệu nào trong phạm vi được phép xem.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.

    Returns:
        DataFrame với 2 cột: `supplier_id`, `supplier_name` — sắp xếp theo
        tên.
    """
    engine = engine or get_engine()
    columns = ["supplier_id", "supplier_name"]

    if _scope_is_empty(scope):
        return pd.DataFrame(columns=columns)

    stmt = (
        select(Supplier.id.label("supplier_id"), Supplier.name.label("supplier_name"))
        .join(SupplierEvaluation, SupplierEvaluation.supplier_id == Supplier.id)
        .join(Employee, SupplierEvaluation.employee_id == Employee.id)
        .group_by(Supplier.id, Supplier.name)
    )
    stmt = _apply_org_scope_filter(stmt, scope, SupplierEvaluation.employee_id)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns)
    df = df.sort_values("supplier_name").reset_index(drop=True)
    return df
