"""Service tính KPI báo cáo Kinh doanh — Doanh thu/lãi lỗ theo 3 chiều:
dịch vụ, khách hàng, Khối-Phòng-NV — cộng thêm xu hướng theo thời gian
(tháng/tuần).

Nguồn yêu cầu: `.claude/rules/trang-thai-yeu-cau.md`, nhóm "Kinh doanh" — cả
3 báo cáo con (theo dịch vụ / theo khách hàng / theo Khối-Phòng-NV) đã
"Đã rõ". Công thức lãi/lỗ = `revenue - order_cost` (CLAUDE.md, đã "Đã rõ").
Tỷ suất lợi nhuận (`profit_margin`), Top-N Nhân viên/Phòng, và xu hướng theo
Tháng/Tuần là 3 KPI bổ sung theo Phụ lục B (SDD gốc) — dùng lại đúng công
thức lãi/lỗ và bộ lọc RBAC/"Huỷ" đã "Đã rõ" ở trên, không phải công thức
nghiệp vụ mới cần xác nhận thêm.

Theo CLAUDE.md mục 2 (tách lớp): module này chỉ chứa truy vấn SQLAlchemy
(parameterized, cấm nối chuỗi SQL thủ công — CLAUDE.md mục 4) + tính toán
KPI, KHÔNG chứa code Streamlit/Plotly. Trang `src/app/pages/1_Bao_cao_Kinh_
doanh.py` chỉ gọi các hàm ở đây rồi vẽ biểu đồ.

*** BẮT BUỘC RBAC (CLAUDE.md mục 6) ***
Mọi hàm public ở đây nhận tham số `scope: DataScope` (từ
`src.auth.scope.compute_data_scope()`) và lọc theo `scope.customer_ids` qua
`SalesOrder.customer_id.in_(...)`, TRỪ KHI `scope.unrestricted is True`
(Admin) thì không lọc. KHÔNG tự viết logic phân quyền riêng ở đây.

*** ĐÃ XÁC NHẬN: loại trừ đơn "Huỷ" khỏi doanh thu/lãi lỗ (COO, bước 4.1) ***
`sales_order.status` là cột `String(50)` placeholder — danh sách giá trị
ĐẦY ĐỦ vẫn CHƯA được COO xác nhận (xem `erd-tuan-02.md` mục 1, và docstring
`SalesOrder` trong `src/db/models/business.py`). Dữ liệu mẫu hiện có các
giá trị: "Mới tạo", "Đang xử lý", "Đang vận chuyển", "Đã giao", "Huỷ". Riêng
giá trị "Huỷ" ĐÃ được COO xác nhận: PHẢI loại trừ khỏi doanh thu/lãi lỗ (xem
`STATUS_CANCELLED` bên dưới) — 3 hàm `get_revenue_profit_by_*` đều áp dụng
`_exclude_cancelled_orders()`. Số lượng/giá trị đơn "Huỷ" vẫn được theo dõi
riêng qua `get_cancelled_orders_summary()` (không cộng vào doanh thu).
CHƯA có xác nhận cho các status khác — KHÔNG tự suy rộng cách loại trừ này
sang giá trị nào khác ngoài "Huỷ" khi chưa hỏi lại.

*** RỦI RO ĐÃ GHI NHẬN (HD-11, tuần 3) — 1 khách hàng có thể thuộc phạm vi
của NHIỀU nhân viên/phòng khác nhau ***
`fetch_customer_ids_for_employee`/`_for_department` (src/services/
auth_service.py) suy luận phạm vi KH bằng UNION `customer_id` từ
`sales_order`/`debt`/`price_request`, không có cột FK trực tiếp `customer.
employee_id`. Khảo sát dữ liệu mẫu hiện tại (30 khách hàng) cho thấy 22/30
khách hàng (73%) xuất hiện dưới >1 `employee_id` khác PHÒNG nhau khi UNION
cả 3 bảng — nghĩa là 1 khách hàng có thể "thuộc phạm vi" của nhiều Manager/
User khác nhau cùng lúc theo cách suy luận hiện tại. Đây KHÔNG phải lỗi của
module báo cáo này (module chỉ dùng `scope.customer_ids` đã tính sẵn từ
`compute_data_scope`), nhưng ảnh hưởng trực tiếp đến độ chính xác số liệu
hiển thị cho Manager/User (có thể thấy doanh thu của KH không thực sự do
mình phụ trách, hoặc ngược lại). CẦN COO XÁC NHẬN cách xử lý (ví dụ: thêm
cột `customer.employee_id` chính chủ trong ERD) — KHÔNG tự ý chọn 1 cách xử
lý ở đây.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from loguru import logger
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.auth.scope import DataScope
from src.db.models import Customer, Department, Division, Employee, SalesOrder, Service
from src.services.db_connection import get_engine

STATUS_CANCELLED = "Huỷ"
"""Giá trị `sales_order.status` ứng với đơn bị huỷ — ĐÃ xác nhận với COO
(bước 4.1): loại trừ khỏi doanh thu/lãi lỗ. Chuỗi đã đối chiếu byte-for-byte
với dữ liệu thật trong DB (`SELECT DISTINCT status FROM sales_order`) —
dạng Unicode NFC (`ỷ` = U+1EF7, không phải tổ hợp dấu rời) — so sánh chuỗi
tiếng Việt sai dạng normalize sẽ âm thầm không loại trừ được gì."""


def _exclude_cancelled_orders(stmt):
    """Loại trừ đơn `status == STATUS_CANCELLED` — dùng cho các hàm tính
    TỔNG doanh thu/lãi lỗ. KHÔNG áp dụng cho `get_cancelled_orders_summary`
    (hàm đó cần đúng các đơn "Huỷ" để đếm/tổng hợp riêng)."""
    return stmt.where(SalesOrder.status != STATUS_CANCELLED)


def _apply_scope_filter(stmt, scope: DataScope):
    """Áp dụng lọc RBAC theo `scope.customer_ids` lên 1 câu `select()` đã có
    `SalesOrder` — bỏ qua nếu `scope.unrestricted` (Admin, CLAUDE.md mục 6).

    Dùng chung cho cả 3 hàm báo cáo bên dưới để đảm bảo áp dụng nhất quán,
    tránh lặp logic phân quyền ở nhiều nơi.
    """
    if scope.unrestricted:
        return stmt
    return stmt.where(SalesOrder.customer_id.in_(scope.customer_ids))


def _apply_date_filter(stmt, date_from: date | None, date_to: date | None):
    """Áp dụng lọc khoảng thời gian tuỳ chọn theo `sales_order.order_date`.

    Cả 2 tham số đều tuỳ chọn (None = không giới hạn) — dùng cho bộ lọc
    khoảng ngày trên trang Streamlit.
    """
    if date_from is not None:
        stmt = stmt.where(SalesOrder.order_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(SalesOrder.order_date <= date_to)
    return stmt


def _add_profit_margin_column(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm cột `profit_margin` (= `profit / revenue`) vào DataFrame đã có
    sẵn 2 cột `revenue`/`profit`.

    *** QUYẾT ĐỊNH chia cho 0: trả về `0.0`, KHÔNG trả `None` *** — cột này
    được dùng trực tiếp để hiển thị `st.metric`/định dạng phần trăm
    (`f"{x:.1%}"`) ở trang Streamlit; `None` sẽ làm lỗi định dạng chuỗi tại
    nơi hiển thị. Về nghiệp vụ, dòng/nhóm không có doanh thu thì quy ước tỷ
    suất lợi nhuận = 0% (không có gì để tính tỷ suất) thay vì  NaN/lỗi.
    Áp dụng dạng vector hoá (không lặp `apply(axis=1)`) để giữ hiệu năng.
    """
    df["profit_margin"] = (df["profit"] / df["revenue"]).where(df["revenue"] != 0, 0.0)
    return df


def get_revenue_profit_by_service(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Doanh thu/lãi lỗ gộp theo dịch vụ (`service`), đã lọc theo RBAC.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập
            (`src.auth.scope.compute_data_scope()`).
        engine: SQLAlchemy Engine tuỳ chọn (mặc định `get_engine()`, cho
            phép truyền engine riêng khi test).
        date_from, date_to: Lọc theo `order_date`, tuỳ chọn (None = không
            giới hạn).

    Returns:
        DataFrame với các cột: `service_id`, `service_name`, `order_count`,
        `revenue`, `order_cost`, `profit`, `profit_margin` (= `profit /
        revenue`, `0.0` khi `revenue == 0` — xem `_add_profit_margin_column`)
        — sắp xếp giảm dần theo `revenue`. Trả về DataFrame rỗng (đúng cột)
        nếu `scope.customer_ids` rỗng và `scope.unrestricted` là False
        (không có dữ liệu để xem).
    """
    engine = engine or get_engine()
    columns = [
        "service_id",
        "service_name",
        "order_count",
        "revenue",
        "order_cost",
        "profit",
        "profit_margin",
    ]

    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_revenue_profit_by_service: scope rỗng (user_id={}) -> trả "
            "về DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    stmt = (
        select(
            Service.id.label("service_id"),
            Service.name.label("service_name"),
            func.count(SalesOrder.id).label("order_count"),
            func.coalesce(func.sum(SalesOrder.revenue), 0).label("revenue"),
            func.coalesce(func.sum(SalesOrder.order_cost), 0).label("order_cost"),
        )
        .join(SalesOrder, SalesOrder.service_id == Service.id)
        .group_by(Service.id, Service.name)
    )
    stmt = _apply_scope_filter(stmt, scope)
    stmt = _exclude_cancelled_orders(stmt)
    stmt = _apply_date_filter(stmt, date_from, date_to)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns[:-2])
    df["revenue"] = df["revenue"].astype(float)
    df["order_cost"] = df["order_cost"].astype(float)
    df["profit"] = df["revenue"] - df["order_cost"]
    df = _add_profit_margin_column(df)
    df = df.sort_values("revenue", ascending=False).reset_index(drop=True)
    logger.info(
        "get_revenue_profit_by_service: user_id={} -> {} dịch vụ.",
        scope.user_id,
        len(df),
    )
    return df


def get_revenue_profit_by_customer(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    top_n: int | None = None,
) -> pd.DataFrame:
    """Doanh thu/lãi lỗ gộp theo khách hàng (`customer`), đã lọc theo RBAC.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        date_from, date_to: Lọc theo `order_date`, tuỳ chọn.
        top_n: Nếu truyền, chỉ giữ `top_n` khách hàng có `revenue` cao nhất
            (dùng cho biểu đồ top khách hàng, tránh quá nhiều cột/dòng).

    Returns:
        DataFrame với các cột: `customer_id`, `customer_code`,
        `customer_name`, `order_count`, `revenue`, `order_cost`, `profit`,
        `profit_margin` (= `profit / revenue`, `0.0` khi `revenue == 0` —
        xem `_add_profit_margin_column`) — sắp xếp giảm dần theo `revenue`.
    """
    engine = engine or get_engine()
    columns = [
        "customer_id",
        "customer_code",
        "customer_name",
        "order_count",
        "revenue",
        "order_cost",
        "profit",
        "profit_margin",
    ]

    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_revenue_profit_by_customer: scope rỗng (user_id={}) -> "
            "trả về DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    stmt = (
        select(
            Customer.id.label("customer_id"),
            Customer.code.label("customer_code"),
            Customer.name.label("customer_name"),
            func.count(SalesOrder.id).label("order_count"),
            func.coalesce(func.sum(SalesOrder.revenue), 0).label("revenue"),
            func.coalesce(func.sum(SalesOrder.order_cost), 0).label("order_cost"),
        )
        .join(SalesOrder, SalesOrder.customer_id == Customer.id)
        .group_by(Customer.id, Customer.code, Customer.name)
    )
    stmt = _apply_scope_filter(stmt, scope)
    stmt = _exclude_cancelled_orders(stmt)
    stmt = _apply_date_filter(stmt, date_from, date_to)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns[:-2])
    df["revenue"] = df["revenue"].astype(float)
    df["order_cost"] = df["order_cost"].astype(float)
    df["profit"] = df["revenue"] - df["order_cost"]
    df = _add_profit_margin_column(df)
    df = df.sort_values("revenue", ascending=False).reset_index(drop=True)
    if top_n is not None:
        df = df.head(top_n).reset_index(drop=True)
    logger.info(
        "get_revenue_profit_by_customer: user_id={} -> {} khách hàng (top_n={}).",
        scope.user_id,
        len(df),
        top_n,
    )
    return df


def get_revenue_profit_by_org(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Doanh thu/lãi lỗ gộp theo phân cấp Khối-Phòng-NV, đã lọc theo RBAC.

    Join `sales_order.employee_id -> employee -> department -> division`.
    Trả về dữ liệu ở mức chi tiết nhất (1 dòng/nhân viên) — trang Streamlit
    tự quyết định cách gộp/drill-down (theo Khối, theo Phòng, hay theo NV)
    từ cùng 1 DataFrame này để tránh gọi DB nhiều lần.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        date_from, date_to: Lọc theo `order_date`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `division_id`, `division_name`,
        `department_id`, `department_name`, `employee_id`, `employee_name`,
        `order_count`, `revenue`, `order_cost`, `profit`, `profit_margin`
        (= `profit / revenue`, `0.0` khi `revenue == 0` — xem
        `_add_profit_margin_column`) — sắp xếp giảm dần theo `revenue`.
    """
    engine = engine or get_engine()
    columns = [
        "division_id",
        "division_name",
        "department_id",
        "department_name",
        "employee_id",
        "employee_name",
        "order_count",
        "revenue",
        "order_cost",
        "profit",
        "profit_margin",
    ]

    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_revenue_profit_by_org: scope rỗng (user_id={}) -> trả về "
            "DataFrame rỗng.",
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
            func.count(SalesOrder.id).label("order_count"),
            func.coalesce(func.sum(SalesOrder.revenue), 0).label("revenue"),
            func.coalesce(func.sum(SalesOrder.order_cost), 0).label("order_cost"),
        )
        .join(Employee, SalesOrder.employee_id == Employee.id)
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
    stmt = _apply_scope_filter(stmt, scope)
    stmt = _exclude_cancelled_orders(stmt)
    stmt = _apply_date_filter(stmt, date_from, date_to)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns[:-2])
    df["revenue"] = df["revenue"].astype(float)
    df["order_cost"] = df["order_cost"].astype(float)
    df["profit"] = df["revenue"] - df["order_cost"]
    df = _add_profit_margin_column(df)
    df = df.sort_values("revenue", ascending=False).reset_index(drop=True)
    logger.info(
        "get_revenue_profit_by_org: user_id={} -> {} dòng (Khối-Phòng-NV).",
        scope.user_id,
        len(df),
    )
    return df


def get_revenue_profit_trend(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    granularity: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Xu hướng doanh thu/lãi lỗ theo thời gian, gộp theo tháng hoặc tuần
    của `sales_order.order_date`, đã lọc theo RBAC + loại trừ đơn "Huỷ".

    *** Cách gộp theo thời gian (dialect MySQL — `src/services/
    db_connection.py` dùng `mysql+mysqlconnector`, xem `build_mysql_url()`)
    ***, hoàn toàn qua SQLAlchemy `func.date_format` (KHÔNG raw SQL/f-string
    nối chuỗi):
    - `granularity="month"`: `func.date_format(order_date, "%Y-%m-01")` —
      gộp về ngày đầu tháng. Cột `period` được ép kiểu `datetime64` (qua
      `pd.to_datetime`) sau khi lấy dữ liệu, để `px.line` vẽ đúng trục thời
      gian liên tục (không phải trục danh mục).
    - `granularity="week"`: `func.date_format(order_date, "%x-%v")` — cặp
      định dạng tuần ISO 8601 của MySQL (`%v` = số tuần 01-53, tuần bắt đầu
      Thứ Hai; `%x` = năm ISO tương ứng, PHẢI dùng kèm `%v`, không dùng lẻ
      `%Y`). Cố tình KHÔNG dùng `%Y-%u` (`%u` là tuần kiểu Thứ Hai đầu tuần
      nhưng không phải chuẩn ISO, dễ lệch năm ở các tuần giáp Tết dương
      lịch). Cột `period` giữ dạng chuỗi `"YYYY-Www"` (VD `"2026-05"`) —
      chuỗi đã zero-pad nên sắp xếp tăng dần bằng string vẫn đúng thứ tự
      thời gian; không ép kiểu ngày vì 1 tuần ISO không map 1-1 sang 1 ngày
      cụ thể để làm mốc.

    *** ĐÃ XÁC NHẬN: quy ước tuần ISO 8601 (COO, 07/09/2026) *** — lựa
    chọn `%x-%v` (tuần ISO, bắt đầu Thứ Hai) ở trên ban đầu là giả định kỹ
    thuật, đã được COO xác nhận giữ nguyên, không đổi sang quy ước tuần
    kiểu khác (VD tuần kiểu Mỹ `%U`/`%u`) để khớp báo cáo AMIS/FT. Không
    còn là mục cần hỏi lại.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        granularity: `"month"` (mặc định) hoặc `"week"`.
        date_from, date_to: Lọc theo `order_date`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `period`, `revenue`, `profit` — sắp xếp tăng
        dần theo `period`. Trả về DataFrame rỗng (đúng cột) nếu
        `scope.customer_ids` rỗng và `scope.unrestricted` là False.

    Raises:
        ValueError: nếu `granularity` không phải `"month"`/`"week"`.
    """
    if granularity not in ("month", "week"):
        raise ValueError(
            f"granularity phải là 'month' hoặc 'week', nhận: {granularity!r}"
        )

    engine = engine or get_engine()
    columns = ["period", "revenue", "profit"]

    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_revenue_profit_trend: scope rỗng (user_id={}) -> trả về "
            "DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    if granularity == "month":
        period_expr = func.date_format(SalesOrder.order_date, "%Y-%m-01")
    else:
        period_expr = func.date_format(SalesOrder.order_date, "%x-%v")

    stmt = select(
        period_expr.label("period"),
        func.coalesce(func.sum(SalesOrder.revenue), 0).label("revenue"),
        func.coalesce(func.sum(SalesOrder.order_cost), 0).label("order_cost"),
    ).group_by(period_expr)
    stmt = _apply_scope_filter(stmt, scope)
    stmt = _exclude_cancelled_orders(stmt)
    stmt = _apply_date_filter(stmt, date_from, date_to)
    stmt = stmt.order_by(period_expr)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=["period", "revenue", "order_cost"])
    df["revenue"] = df["revenue"].astype(float)
    df["order_cost"] = df["order_cost"].astype(float)
    df["profit"] = df["revenue"] - df["order_cost"]
    df = df.drop(columns=["order_cost"])
    if granularity == "month":
        df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values("period").reset_index(drop=True)
    logger.info(
        "get_revenue_profit_trend: user_id={} granularity={} -> {} kỳ.",
        scope.user_id,
        granularity,
        len(df),
    )
    return df


def get_cancelled_orders_summary(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, int | float]:
    """Số lượng và tổng giá trị (`revenue`) đơn `status == STATUS_CANCELLED`
    — CHỈ để theo dõi tỷ lệ huỷ đơn, KHÔNG cộng vào doanh thu/lãi lỗ (3 hàm
    `get_revenue_profit_by_*` ở trên đã loại trừ các đơn này).

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        date_from, date_to: Lọc theo `order_date`, tuỳ chọn.

    Returns:
        Dict với 2 khoá: `cancelled_order_count` (int), `cancelled_revenue`
        (float). Trả về `{"cancelled_order_count": 0, "cancelled_revenue":
        0.0}` nếu `scope.customer_ids` rỗng và `scope.unrestricted` là False.
    """
    engine = engine or get_engine()

    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_cancelled_orders_summary: scope rỗng (user_id={}) -> trả về 0.",
            scope.user_id,
        )
        return {"cancelled_order_count": 0, "cancelled_revenue": 0.0}

    stmt = select(
        func.count(SalesOrder.id).label("cancelled_order_count"),
        func.coalesce(func.sum(SalesOrder.revenue), 0).label("cancelled_revenue"),
    ).where(SalesOrder.status == STATUS_CANCELLED)
    stmt = _apply_scope_filter(stmt, scope)
    stmt = _apply_date_filter(stmt, date_from, date_to)

    with Session(engine) as session:
        row = session.execute(stmt).one()

    result = {
        "cancelled_order_count": int(row.cancelled_order_count),
        "cancelled_revenue": float(row.cancelled_revenue),
    }
    logger.info(
        "get_cancelled_orders_summary: user_id={} -> {} đơn Huỷ, revenue={}.",
        scope.user_id,
        result["cancelled_order_count"],
        result["cancelled_revenue"],
    )
    return result
