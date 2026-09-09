"""Service tính KPI báo cáo Chi phí — 2 báo cáo con:

1. **Theo Khối** — so sánh `cost` (chi thực tế) với `budget` (ngân sách) cùng
   kỳ theo Khối (`division`), gồm chênh lệch tuyệt đối (`variance`) và %
   (`variance_pct`), cộng xu hướng theo thời gian (tháng/tuần).
2. **Theo Nhóm nhân sự** — `personnel_cost` theo `staff_group` (LĐ/QL/
   Frontline/Middle/Backend, đã nhóm sẵn trong AMIS), cộng xu hướng theo
   thời gian.

Nguồn yêu cầu: `.claude/rules/trang-thai-yeu-cau.md`, nhóm "Chi phí" — cả 2
báo cáo con ("Theo Khối", "Theo Nhóm") đã "Đã rõ".

Theo CLAUDE.md mục 2 (tách lớp): module này chỉ chứa truy vấn SQLAlchemy
(parameterized, cấm nối chuỗi SQL thủ công — CLAUDE.md mục 4) + tính toán
KPI, KHÔNG chứa code Streamlit/Plotly. Trang `src/app/pages/5_Bao_cao_Chi_
phi.py` chỉ gọi các hàm ở đây rồi vẽ biểu đồ.

*** BẮT BUỘC RBAC — 2 QUYẾT ĐỊNH COO XÁC NHẬN 09/09/2026, DỮ LIỆU TÀI CHÍNH
NHẠY CẢM, ÁP DỤNG NGHIÊM NGẶT ***

1) Báo cáo "Theo Khối" (`cost`/`budget`):
   - Admin (`scope.unrestricted is True`): xem toàn bộ các Khối, không lọc.
   - Manager: lọc theo `scope.division_id` (đã có sẵn trực tiếp trên
     `DataScope` — `src/auth/scope.py`, suy ra từ `employee -> department ->
     division` qua `auth_service.fetch_employee_context`, KHÔNG cần tự join
     lại `department` ở đây) — chỉ xem đúng Khối của mình.
   - User: `cost`/`budget` KHÔNG có dữ liệu cấp nhân viên (chỉ có
     `division_id`) — module này CHẶN HẲN User khỏi sub-report "Theo Khối":
     mọi hàm `get_cost_vs_budget_*` trả về DataFrame RỖNG cho role User
     (xem `_division_scope_blocked`), KHÔNG hiển thị số liệu toàn Khối cho
     User dưới bất kỳ hình thức nào. Đây là DataFrame rỗng (không phải lỗi)
     vì về bản chất báo cáo này "không áp dụng" ở cấp User, khác với
     "Theo Nhóm nhân sự" bên dưới (đó là chặn quyền thật sự) — trang
     Streamlit vẫn nên ẩn hẳn tab/hiển thị thông báo rõ ràng cho User dựa
     trên `scope.role`, không chỉ dựa vào DataFrame rỗng.

2) Báo cáo "Theo Nhóm nhân sự" (`personnel_cost`):
   `personnel_cost` KHÔNG có cột liên kết Khối/Phòng/NV theo ERD
   (`docs/architecture/erd-tuan-02.md`, mục "Nhóm bảng nghiệp vụ" — chỉ có
   `id`, `staff_group`, `period`, `amount`; xem thêm docstring `PersonnelCost`
   trong `src/db/models/business.py`) — vì vậy KHÔNG THỂ lọc theo
   `scope.customer_ids`/`scope.division_id`/`scope.department_id`/
   `scope.employee_id` như mọi báo cáo khác. Quyết định COO 09/09/2026:
   **CHỈ Admin (`scope.unrestricted is True`) được xem báo cáo này** —
   Manager/User bị chặn hoàn toàn.
   **Cơ chế chặn đã chọn (áp dụng NHẤT QUÁN cho mọi hàm
   `get_personnel_cost_*` bên dưới): raise `PermissionError`** — không trả
   `None`/DataFrame rỗng, vì đây là chặn quyền thật sự (không phải "không
   có dữ liệu"), cần buộc trang Streamlit xử lý tường minh (try/except) và
   ẨN HẲN tab/mục "Theo Nhóm nhân sự" nếu `scope.unrestricted` là `False`
   (kiểm tra TRƯỚC khi gọi hàm, không dựa vào bắt exception làm luồng chính
   — xem `src/app/pages/5_Bao_cao_Chi_phi.py::main`).

*** Quy ước variance/variance_pct ***
`variance = cost_amount - budget_amount` (dương = chi vượt ngân sách, âm =
chi dưới ngân sách). `variance_pct = variance / budget_amount`, quy ước trả
về `0.0` khi `budget_amount == 0` (tránh chia cho 0, cùng quy ước
`_add_profit_margin_column` ở `report_kinh_doanh.py`) — KHÔNG trả `None`/NaN
vì cột này dùng trực tiếp để hiển thị `st.metric`/định dạng `f"{x:.1%}"`.

*** ĐÃ XÁC NHẬN: quy ước tuần ISO 8601 cho biểu đồ xu hướng (COO,
07/09/2026) *** — áp dụng nhất quán với `report_kinh_doanh.py`
(`get_revenue_profit_trend`): `granularity="week"` dùng
`func.date_format(..., "%x-%v")`.

*** Chỉ các Khối/Nhóm nhân sự CÓ ít nhất 1 dòng `cost`/`budget`/
`personnel_cost` trong khoảng lọc mới xuất hiện trong kết quả *** — module
này KHÔNG tự chèn dòng 0 cho Khối/Nhóm không có dữ liệu giao dịch nào (cùng
quy ước với các module báo cáo khác trong dự án — chỉ tổng hợp dữ liệu thực
có, không suy diễn số liệu không tồn tại).

*** CHƯA XÁC NHẬN — cần hỏi lại nếu ảnh hưởng ***
- Định dạng lưu trữ thực tế của cột `period` (ngày đại diện đầu kỳ hay giá
  trị khác) — xem ghi chú đầu `src/db/models/business.py`, chấp nhận làm
  mặc định theo `erd-tuan-02.md` mục "Việc cần xác nhận" dòng `period`,
  không phải quyết định của module này.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from loguru import logger
from sqlalchemy import Engine, false, func, select
from sqlalchemy.orm import Session

from src.auth.scope import DataScope
from src.db.models import Budget, Cost, Division, PersonnelCost
from src.db.models.enums import StaffGroup, UserRole
from src.services.db_connection import get_engine

# ---------------------------------------------------------------------------
# Helper dùng chung
# ---------------------------------------------------------------------------


def _period_expr(date_col, granularity: str):
    """Biểu thức SQL gộp `date_col` theo Tháng/Tuần — giữ nguyên quy ước đã
    "Đã rõ" ở `report_kinh_doanh.py::get_revenue_profit_trend` (ISO week,
    COO xác nhận 07/09/2026): `"month"` -> `date_format(date_col,
    "%Y-%m-01")`; `"week"` -> `date_format(date_col, "%x-%v")`."""
    if granularity == "month":
        return func.date_format(date_col, "%Y-%m-01")
    return func.date_format(date_col, "%x-%v")


def _apply_date_filter(stmt, date_from: date | None, date_to: date | None, date_col):
    """Áp dụng lọc khoảng thời gian tuỳ chọn lên `date_col` (cột `period`
    của bảng đang truy vấn)."""
    if date_from is not None:
        stmt = stmt.where(date_col >= date_from)
    if date_to is not None:
        stmt = stmt.where(date_col <= date_to)
    return stmt


def _add_variance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm cột `variance` (= `cost_amount - budget_amount`) và
    `variance_pct` (= `variance / budget_amount`, `0.0` khi
    `budget_amount == 0` — xem docstring module) vào DataFrame đã có sẵn 2
    cột `cost_amount`/`budget_amount`. Vector hoá, không `apply(axis=1)`."""
    df["variance"] = df["cost_amount"] - df["budget_amount"]
    df["variance_pct"] = (df["variance"] / df["budget_amount"]).where(
        df["budget_amount"] != 0, 0.0
    )
    return df


# ---------------------------------------------------------------------------
# Báo cáo con 1: Theo Khối (cost vs budget) — RBAC: Admin/Manager, User chặn
# ---------------------------------------------------------------------------


def _division_scope_blocked(scope: DataScope) -> bool:
    """`True` nếu sub-report "Theo Khối" phải trả về rỗng cho `scope` này.

    - Admin (`scope.unrestricted`): không bao giờ bị chặn.
    - User: LUÔN bị chặn — `cost`/`budget` không có dữ liệu cấp nhân viên
      (quyết định COO 09/09/2026, xem docstring module).
    - Manager: chỉ bị chặn nếu thiếu `scope.division_id` (scope rỗng, VD
      tài khoản không gắn `employee_id` hợp lệ).
    """
    if scope.unrestricted:
        return False
    if scope.role == UserRole.USER:
        return True
    return scope.division_id is None


def _apply_division_filter(stmt, scope: DataScope, division_id_col):
    """Áp dụng lọc RBAC theo Khối lên 1 câu `select()` đã có cột
    `division_id_col` (`Cost.division_id` hoặc `Budget.division_id`).

    Admin: không lọc. Manager: lọc `division_id_col == scope.division_id`.
    User: LUÔN trả điều kiện `False` (phòng vệ kép — sub-report này đã bị
    chặn từ sớm bởi `_division_scope_blocked`, nhưng hàm này tự chặn lại một
    lần nữa để không vô tình lộ dữ liệu nếu bị gọi nhầm, vì đây là dữ liệu
    tài chính nhạy cảm — CLAUDE.md mục 6).
    """
    if scope.unrestricted:
        return stmt
    if scope.role == UserRole.USER:
        return stmt.where(false())
    if scope.division_id is None:
        return stmt.where(false())
    return stmt.where(division_id_col == scope.division_id)


def get_cost_vs_budget_by_division(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Tổng chi thực tế (`cost`) vs ngân sách (`budget`) gộp theo Khối, đã
    lọc theo RBAC (xem `_division_scope_blocked`/`_apply_division_filter`).

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn (mặc định `get_engine()`).
        date_from, date_to: Lọc theo `period`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `division_id`, `division_name`,
        `cost_amount`, `budget_amount`, `variance` (= `cost_amount -
        budget_amount`), `variance_pct` (= `variance / budget_amount`,
        `0.0` khi `budget_amount == 0`) — sắp xếp giảm dần theo
        `cost_amount`. Chỉ gồm các Khối có ít nhất 1 dòng `cost` hoặc
        `budget` trong khoảng lọc. Trả về DataFrame rỗng (đúng cột) nếu
        `_division_scope_blocked(scope)` là `True` (Manager thiếu
        `division_id`, hoặc role User — không có dữ liệu cấp nhân viên cho
        báo cáo này).
    """
    engine = engine or get_engine()
    columns = [
        "division_id",
        "division_name",
        "cost_amount",
        "budget_amount",
        "variance",
        "variance_pct",
    ]

    if _division_scope_blocked(scope):
        logger.warning(
            "get_cost_vs_budget_by_division: scope bị chặn (user_id={} "
            "role={}) -> trả về DataFrame rỗng.",
            scope.user_id,
            scope.role.value,
        )
        return pd.DataFrame(columns=columns)

    cost_stmt = (
        select(
            Division.id.label("division_id"),
            Division.name.label("division_name"),
            func.coalesce(func.sum(Cost.amount), 0).label("cost_amount"),
        )
        .join(Cost, Cost.division_id == Division.id)
        .group_by(Division.id, Division.name)
    )
    cost_stmt = _apply_division_filter(cost_stmt, scope, Cost.division_id)
    cost_stmt = _apply_date_filter(cost_stmt, date_from, date_to, Cost.period)

    budget_stmt = (
        select(
            Division.id.label("division_id"),
            Division.name.label("division_name"),
            func.coalesce(func.sum(Budget.amount), 0).label("budget_amount"),
        )
        .join(Budget, Budget.division_id == Division.id)
        .group_by(Division.id, Division.name)
    )
    budget_stmt = _apply_division_filter(budget_stmt, scope, Budget.division_id)
    budget_stmt = _apply_date_filter(budget_stmt, date_from, date_to, Budget.period)

    with Session(engine) as session:
        cost_rows = session.execute(cost_stmt).all()
        budget_rows = session.execute(budget_stmt).all()

    cost_df = pd.DataFrame(
        cost_rows, columns=["division_id", "division_name", "cost_amount"]
    )
    budget_df = pd.DataFrame(
        budget_rows, columns=["division_id", "division_name", "budget_amount"]
    )

    df = pd.merge(cost_df, budget_df, on=["division_id", "division_name"], how="outer")
    if df.empty:
        return pd.DataFrame(columns=columns)

    df["cost_amount"] = df["cost_amount"].fillna(0).astype(float)
    df["budget_amount"] = df["budget_amount"].fillna(0).astype(float)
    df = _add_variance_columns(df)
    df = df.sort_values("cost_amount", ascending=False).reset_index(drop=True)
    logger.info(
        "get_cost_vs_budget_by_division: user_id={} role={} -> {} Khối.",
        scope.user_id,
        scope.role.value,
        len(df),
    )
    return df


def get_cost_vs_budget_trend(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    granularity: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    division_id: int | None = None,
) -> pd.DataFrame:
    """Xu hướng chi thực tế vs ngân sách theo thời gian (gộp theo tháng
    hoặc tuần ISO của `period` — xem `_period_expr`), đã lọc theo RBAC.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        granularity: `"month"` (mặc định) hoặc `"week"`.
        date_from, date_to: Lọc theo `period`, tuỳ chọn.
        division_id: Nếu truyền, chỉ tính riêng 1 Khối (dùng khi trang
            Streamlit cho Admin chọn 1 Khối cụ thể để xem xu hướng riêng —
            với Manager, tham số này chỉ có tác dụng nếu trùng đúng
            `scope.division_id`, vì `_apply_division_filter` vẫn áp dụng
            song song, kết quả rỗng nếu khác Khối được phép xem).

    Returns:
        DataFrame với các cột: `period`, `cost_amount`, `budget_amount`,
        `variance`, `variance_pct` — sắp xếp tăng dần theo `period`. Trả về
        DataFrame rỗng (đúng cột) nếu `_division_scope_blocked(scope)`.

    Raises:
        ValueError: nếu `granularity` không phải `"month"`/`"week"`.
    """
    if granularity not in ("month", "week"):
        raise ValueError(
            f"granularity phải là 'month' hoặc 'week', nhận: {granularity!r}"
        )

    engine = engine or get_engine()
    columns = ["period", "cost_amount", "budget_amount", "variance", "variance_pct"]

    if _division_scope_blocked(scope):
        logger.warning(
            "get_cost_vs_budget_trend: scope bị chặn (user_id={} role={}) "
            "-> trả về DataFrame rỗng.",
            scope.user_id,
            scope.role.value,
        )
        return pd.DataFrame(columns=columns)

    cost_period_expr = _period_expr(Cost.period, granularity)
    budget_period_expr = _period_expr(Budget.period, granularity)

    cost_stmt = select(
        cost_period_expr.label("period"),
        func.coalesce(func.sum(Cost.amount), 0).label("cost_amount"),
    ).group_by(cost_period_expr)
    cost_stmt = _apply_division_filter(cost_stmt, scope, Cost.division_id)
    if division_id is not None:
        cost_stmt = cost_stmt.where(Cost.division_id == division_id)
    cost_stmt = _apply_date_filter(cost_stmt, date_from, date_to, Cost.period)

    budget_stmt = select(
        budget_period_expr.label("period"),
        func.coalesce(func.sum(Budget.amount), 0).label("budget_amount"),
    ).group_by(budget_period_expr)
    budget_stmt = _apply_division_filter(budget_stmt, scope, Budget.division_id)
    if division_id is not None:
        budget_stmt = budget_stmt.where(Budget.division_id == division_id)
    budget_stmt = _apply_date_filter(budget_stmt, date_from, date_to, Budget.period)

    with Session(engine) as session:
        cost_rows = session.execute(cost_stmt).all()
        budget_rows = session.execute(budget_stmt).all()

    cost_df = pd.DataFrame(cost_rows, columns=["period", "cost_amount"])
    budget_df = pd.DataFrame(budget_rows, columns=["period", "budget_amount"])

    df = pd.merge(cost_df, budget_df, on="period", how="outer")
    if df.empty:
        return pd.DataFrame(columns=columns)

    df["cost_amount"] = df["cost_amount"].fillna(0).astype(float)
    df["budget_amount"] = df["budget_amount"].fillna(0).astype(float)
    df = _add_variance_columns(df)
    if granularity == "month":
        df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values("period").reset_index(drop=True)
    logger.info(
        "get_cost_vs_budget_trend: user_id={} role={} granularity={} "
        "division_id={} -> {} kỳ.",
        scope.user_id,
        scope.role.value,
        granularity,
        division_id,
        len(df),
    )
    return df


def get_division_list(
    scope: DataScope, *, engine: Engine | None = None
) -> pd.DataFrame:
    """Danh sách Khối có ít nhất 1 dòng `cost` HOẶC `budget`, trong phạm vi
    RBAC hiện tại — dùng đổ vào `st.selectbox` (chọn Khối) trên trang
    Streamlit. Trả về DataFrame rỗng nếu `_division_scope_blocked(scope)`.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.

    Returns:
        DataFrame với 2 cột: `division_id`, `division_name` — sắp xếp theo tên.
    """
    engine = engine or get_engine()
    columns = ["division_id", "division_name"]

    if _division_scope_blocked(scope):
        return pd.DataFrame(columns=columns)

    cost_stmt = select(Division.id, Division.name).join(
        Cost, Cost.division_id == Division.id
    )
    cost_stmt = _apply_division_filter(cost_stmt, scope, Cost.division_id)
    budget_stmt = select(Division.id, Division.name).join(
        Budget, Budget.division_id == Division.id
    )
    budget_stmt = _apply_division_filter(budget_stmt, scope, Budget.division_id)

    with Session(engine) as session:
        rows = set(session.execute(cost_stmt).all()) | set(
            session.execute(budget_stmt).all()
        )

    df = pd.DataFrame(sorted(rows, key=lambda r: r[1]), columns=columns)
    return df


# ---------------------------------------------------------------------------
# Báo cáo con 2: Theo Nhóm nhân sự (personnel_cost) — RBAC: CHỈ Admin
# ---------------------------------------------------------------------------


def _require_admin(scope: DataScope, function_name: str) -> None:
    """Chặn quyền cho báo cáo "Theo Nhóm nhân sự" — CHỈ Admin
    (`scope.unrestricted`) được gọi các hàm `get_personnel_cost_*` (quyết
    định COO 09/09/2026, xem docstring module: `personnel_cost` không có
    cột liên kết Khối/Phòng/NV nên không thể lọc RBAC cho Manager/User).

    Raises:
        PermissionError: nếu `scope.unrestricted` là `False` (Manager/User).
    """
    if scope.unrestricted:
        return
    logger.warning(
        "{}: chặn quyền -> user_id={} role={} không phải Admin, "
        "personnel_cost không có dữ liệu cấp Khối/Phòng/NV để lọc RBAC.",
        function_name,
        scope.user_id,
        scope.role.value,
    )
    raise PermissionError(
        f"{function_name}: chỉ Admin được xem báo cáo 'Theo Nhóm nhân sự' "
        "— bảng personnel_cost không có cột liên kết Khối/Phòng/NV theo "
        "ERD (docs/architecture/erd-tuan-02.md) nên không thể lọc RBAC cho "
        "Manager/User (quyết định COO 09/09/2026)."
    )


def get_personnel_cost_by_staff_group(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Tổng `personnel_cost` gộp theo `staff_group`, CHỈ dành cho Admin.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        date_from, date_to: Lọc theo `period`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `staff_group`, `cost_amount` — sắp xếp giảm
        dần theo `cost_amount`. Chỉ gồm các nhóm có ít nhất 1 dòng dữ liệu
        trong khoảng lọc.

    Raises:
        PermissionError: nếu `scope.unrestricted` là `False` (Manager/User
            — xem `_require_admin`).
    """
    _require_admin(scope, "get_personnel_cost_by_staff_group")
    engine = engine or get_engine()

    stmt = select(
        PersonnelCost.staff_group.label("staff_group"),
        func.coalesce(func.sum(PersonnelCost.amount), 0).label("cost_amount"),
    ).group_by(PersonnelCost.staff_group)
    stmt = _apply_date_filter(stmt, date_from, date_to, PersonnelCost.period)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=["staff_group", "cost_amount"])
    df["staff_group"] = df["staff_group"].apply(
        lambda v: v.value if isinstance(v, StaffGroup) else v
    )
    df["cost_amount"] = df["cost_amount"].astype(float)
    df = df.sort_values("cost_amount", ascending=False).reset_index(drop=True)
    logger.info(
        "get_personnel_cost_by_staff_group: user_id={} (Admin) -> {} nhóm.",
        scope.user_id,
        len(df),
    )
    return df


def get_personnel_cost_trend(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    granularity: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    staff_group: StaffGroup | str | None = None,
) -> pd.DataFrame:
    """Xu hướng `personnel_cost` theo thời gian (gộp theo tháng hoặc tuần
    ISO của `period` — xem `_period_expr`), theo từng `staff_group`, CHỈ
    dành cho Admin.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        granularity: `"month"` (mặc định) hoặc `"week"`.
        date_from, date_to: Lọc theo `period`, tuỳ chọn.
        staff_group: Nếu truyền (`StaffGroup` hoặc giá trị chuỗi tương ứng,
            VD `"Frontline"`), chỉ tính riêng 1 nhóm — dùng khi trang
            Streamlit cho chọn 1 nhóm cụ thể để xem xu hướng riêng.

    Returns:
        DataFrame dạng "long" với các cột: `period`, `staff_group`,
        `cost_amount` — sắp xếp tăng dần theo `period` (phù hợp vẽ
        `px.line(..., color="staff_group")` nhiều đường trên cùng biểu đồ).

    Raises:
        PermissionError: nếu `scope.unrestricted` là `False` (Manager/User
            — xem `_require_admin`).
        ValueError: nếu `granularity` không phải `"month"`/`"week"`.
    """
    _require_admin(scope, "get_personnel_cost_trend")
    if granularity not in ("month", "week"):
        raise ValueError(
            f"granularity phải là 'month' hoặc 'week', nhận: {granularity!r}"
        )

    engine = engine or get_engine()
    period_expr = _period_expr(PersonnelCost.period, granularity)

    stmt = (
        select(
            period_expr.label("period"),
            PersonnelCost.staff_group.label("staff_group"),
            func.coalesce(func.sum(PersonnelCost.amount), 0).label("cost_amount"),
        )
        .group_by(period_expr, PersonnelCost.staff_group)
        .order_by(period_expr)
    )
    if staff_group is not None:
        stmt = stmt.where(PersonnelCost.staff_group == staff_group)
    stmt = _apply_date_filter(stmt, date_from, date_to, PersonnelCost.period)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=["period", "staff_group", "cost_amount"])
    df["staff_group"] = df["staff_group"].apply(
        lambda v: v.value if isinstance(v, StaffGroup) else v
    )
    df["cost_amount"] = df["cost_amount"].astype(float)
    if granularity == "month":
        df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values("period").reset_index(drop=True)
    logger.info(
        "get_personnel_cost_trend: user_id={} (Admin) granularity={} "
        "staff_group={} -> {} dòng.",
        scope.user_id,
        granularity,
        staff_group,
        len(df),
    )
    return df


def get_staff_group_list() -> list[str]:
    """Danh sách giá trị `staff_group` cố định (5 nhóm đã "Đã rõ" — LĐ/QL/
    Frontline/Middle/Backend, xem `StaffGroup` trong
    `src/db/models/enums.py`) — dùng đổ vào `st.selectbox` trên trang
    Streamlit. KHÔNG cần truy vấn DB (danh sách cố định theo enum, không
    phụ thuộc dữ liệu/RBAC — khác `get_division_list`/`get_supplier_list`
    ở các module khác, vốn chỉ liệt kê giá trị THỰC TẾ có dữ liệu)."""
    return [g.value for g in StaffGroup]
