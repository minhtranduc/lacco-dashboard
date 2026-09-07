"""Service tính KPI báo cáo Kinh doanh — Doanh thu/lãi lỗ theo 3 chiều:
dịch vụ, khách hàng, Khối-Phòng-NV.

Nguồn yêu cầu: `.claude/rules/trang-thai-yeu-cau.md`, nhóm "Kinh doanh" — cả
3 báo cáo con (theo dịch vụ / theo khách hàng / theo Khối-Phòng-NV) đã
"Đã rõ". Công thức lãi/lỗ = `revenue - order_cost` (CLAUDE.md, đã "Đã rõ").

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
        `revenue`, `order_cost`, `profit` — sắp xếp giảm dần theo `revenue`.
        Trả về DataFrame rỗng (đúng cột) nếu `scope.customer_ids` rỗng và
        `scope.unrestricted` là False (không có dữ liệu để xem).
    """
    engine = engine or get_engine()
    columns = [
        "service_id",
        "service_name",
        "order_count",
        "revenue",
        "order_cost",
        "profit",
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

    df = pd.DataFrame(rows, columns=columns[:-1])
    df["revenue"] = df["revenue"].astype(float)
    df["order_cost"] = df["order_cost"].astype(float)
    df["profit"] = df["revenue"] - df["order_cost"]
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
        `customer_name`, `order_count`, `revenue`, `order_cost`, `profit`
        — sắp xếp giảm dần theo `revenue`.
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

    df = pd.DataFrame(rows, columns=columns[:-1])
    df["revenue"] = df["revenue"].astype(float)
    df["order_cost"] = df["order_cost"].astype(float)
    df["profit"] = df["revenue"] - df["order_cost"]
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
        `order_count`, `revenue`, `order_cost`, `profit` — sắp xếp giảm dần
        theo `revenue`.
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

    df = pd.DataFrame(rows, columns=columns[:-1])
    df["revenue"] = df["revenue"].astype(float)
    df["order_cost"] = df["order_cost"].astype(float)
    df["profit"] = df["revenue"] - df["order_cost"]
    df = df.sort_values("revenue", ascending=False).reset_index(drop=True)
    logger.info(
        "get_revenue_profit_by_org: user_id={} -> {} dòng (Khối-Phòng-NV).",
        scope.user_id,
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
