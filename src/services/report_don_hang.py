"""Service tính KPI báo cáo Đơn hàng — Tình trạng đơn hàng (`status`) và
Tình trạng xuất hoá đơn (`invoice_status`), đếm số lượng đơn theo TỪNG giá
trị thực tế gặp trong dữ liệu, cộng thêm xu hướng theo thời gian
(tháng/tuần).

Nguồn yêu cầu: `.claude/rules/trang-thai-yeu-cau.md`, nhóm "Kinh doanh",
2 dòng "Tình trạng đơn hàng" và "Tình trạng xuất hóa đơn" — cả 2 đã "Đã rõ"
ở mức: được phép code phần đếm/hiển thị theo trạng thái. Danh sách ĐẦY ĐỦ
các giá trị `status` cụ thể (ngoài "Huỷ") vẫn CHƯA được Trưởng phòng Vận
hành xác nhận (xem `erd-tuan-02.md` mục 1, và docstring `SalesOrder` trong
`src/db/models/business.py`) — vì vậy module này KHÔNG hardcode danh sách
trạng thái, mà luôn `SELECT DISTINCT status`/`invoice_status` rồi group
count trên đúng các giá trị gặp trong dữ liệu thật.

Theo CLAUDE.md mục 2 (tách lớp): module này chỉ chứa truy vấn SQLAlchemy
(parameterized, cấm nối chuỗi SQL thủ công — CLAUDE.md mục 4) + tính toán
KPI, KHÔNG chứa code Streamlit/Plotly. Trang `src/app/pages/3_Bao_cao_Don_
hang.py` chỉ gọi các hàm ở đây rồi vẽ biểu đồ.

*** BẮT BUỘC RBAC (CLAUDE.md mục 6) ***
Mọi hàm public ở đây nhận tham số `scope: DataScope` (từ
`src.auth.scope.compute_data_scope()`) và lọc theo `scope.customer_ids` qua
`SalesOrder.customer_id.in_(...)`, TRỪ KHI `scope.unrestricted is True`
(Admin) thì không lọc. KHÔNG tự viết logic phân quyền riêng ở đây — tái
dùng đúng mẫu `_apply_scope_filter` đã có ở `src/services/
report_kinh_doanh.py`.

*** KHÁC BIỆT QUAN TRỌNG so với `report_kinh_doanh.py`: KHÔNG loại trừ đơn
"Huỷ" ở đây ***
`report_kinh_doanh.py` loại trừ đơn `status="Huỷ"` khỏi MỌI tổng doanh thu/
lãi lỗ (COO xác nhận 07/09/2026, bước 4.1, CLAUDE.md mục 7) — nhưng quy tắc
đó CHỈ áp dụng cho các hàm TÍNH TIỀN (doanh thu/lãi lỗ). Module này đếm SỐ
LƯỢNG đơn theo từng trạng thái, KHÔNG phải báo cáo doanh thu — đơn "Huỷ"
chính là 1 trong các giá trị `status` cần được đếm/hiển thị bình thường
như mọi giá trị khác, KHÔNG bị loại trừ khỏi kết quả của module này. Không
gọi/import `STATUS_CANCELLED`/`_exclude_cancelled_orders` từ
`report_kinh_doanh.py` ở đây.

*** RỦI RO ĐÃ GHI NHẬN (kế thừa từ `report_kinh_doanh.py`) — 1 khách hàng
có thể thuộc phạm vi của NHIỀU nhân viên/phòng khác nhau *** — xem chi tiết
đầy đủ trong docstring module `src/services/report_kinh_doanh.py`. Module
này dùng lại đúng `scope.customer_ids` đã tính sẵn, không tự xử lý rủi ro
này ở đây.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from loguru import logger
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.auth.scope import DataScope
from src.db.models import SalesOrder
from src.services.db_connection import get_engine


def _apply_scope_filter(stmt, scope: DataScope):
    """Áp dụng lọc RBAC theo `scope.customer_ids` lên 1 câu `select()` đã có
    `SalesOrder` — bỏ qua nếu `scope.unrestricted` (Admin, CLAUDE.md mục 6).

    Lặp lại đúng mẫu `_apply_scope_filter` ở `src/services/
    report_kinh_doanh.py` để nhất quán trong toàn dự án — không tự viết
    logic phân quyền riêng.
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


def get_order_status_counts(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Đếm số lượng đơn hàng theo TỪNG giá trị `status` thực tế gặp trong
    dữ liệu (KHÔNG hardcode danh sách trạng thái — group theo giá trị thật
    trong DB), đã lọc theo RBAC.

    *** KHÔNG loại trừ đơn "Huỷ" *** — đây là báo cáo đếm số lượng theo
    trạng thái, "Huỷ" là 1 trạng thái cần đếm như các trạng thái khác. Xem
    docstring module để biết lý do đầy đủ (khác với `report_kinh_doanh.py`,
    nơi "Huỷ" bị loại trừ khỏi tổng doanh thu/lãi lỗ).

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập
            (`src.auth.scope.compute_data_scope()`).
        engine: SQLAlchemy Engine tuỳ chọn (mặc định `get_engine()`, cho
            phép truyền engine riêng khi test).
        date_from, date_to: Lọc theo `order_date`, tuỳ chọn (None = không
            giới hạn).

    Returns:
        DataFrame với các cột: `status`, `order_count` — sắp xếp giảm dần
        theo `order_count`. Trả về DataFrame rỗng (đúng cột) nếu
        `scope.customer_ids` rỗng và `scope.unrestricted` là False (không
        có dữ liệu để xem).
    """
    engine = engine or get_engine()
    columns = ["status", "order_count"]

    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_order_status_counts: scope rỗng (user_id={}) -> trả về "
            "DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    stmt = select(
        SalesOrder.status.label("status"),
        func.count(SalesOrder.id).label("order_count"),
    ).group_by(SalesOrder.status)
    stmt = _apply_scope_filter(stmt, scope)
    stmt = _apply_date_filter(stmt, date_from, date_to)
    stmt = stmt.order_by(func.count(SalesOrder.id).desc())

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns)
    logger.info(
        "get_order_status_counts: user_id={} -> {} giá trị status khác nhau, "
        "tổng {} đơn.",
        scope.user_id,
        len(df),
        int(df["order_count"].sum()) if not df.empty else 0,
    )
    return df


def get_invoice_status_counts(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Đếm số lượng đơn hàng theo TỪNG giá trị `invoice_status` thực tế gặp
    trong dữ liệu (KHÔNG hardcode danh sách trạng thái), đã lọc theo RBAC.

    Cũng KHÔNG loại trừ đơn `status="Huỷ"` — cùng lý do như
    `get_order_status_counts` (đây là đếm số lượng theo trạng thái xuất
    hoá đơn, không phải tổng doanh thu).

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        date_from, date_to: Lọc theo `order_date`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `invoice_status`, `order_count` — sắp xếp
        giảm dần theo `order_count`. Trả về DataFrame rỗng (đúng cột) nếu
        `scope.customer_ids` rỗng và `scope.unrestricted` là False.
    """
    engine = engine or get_engine()
    columns = ["invoice_status", "order_count"]

    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_invoice_status_counts: scope rỗng (user_id={}) -> trả về "
            "DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    stmt = select(
        SalesOrder.invoice_status.label("invoice_status"),
        func.count(SalesOrder.id).label("order_count"),
    ).group_by(SalesOrder.invoice_status)
    stmt = _apply_scope_filter(stmt, scope)
    stmt = _apply_date_filter(stmt, date_from, date_to)
    stmt = stmt.order_by(func.count(SalesOrder.id).desc())

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns)
    logger.info(
        "get_invoice_status_counts: user_id={} -> {} giá trị invoice_status "
        "khác nhau, tổng {} đơn.",
        scope.user_id,
        len(df),
        int(df["order_count"].sum()) if not df.empty else 0,
    )
    return df


def get_order_status_trend(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    granularity: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
) -> pd.DataFrame:
    """Xu hướng số lượng đơn theo `status`, gộp theo tháng/tuần của
    `sales_order.order_date`, đã lọc theo RBAC — KHÔNG loại trừ đơn "Huỷ".

    Dùng chung cách gộp thời gian với `report_kinh_doanh.
    get_revenue_profit_trend` (ISO week, COO xác nhận 07/09/2026, CLAUDE.md
    mục 7) — qua SQLAlchemy `func.date_format` (KHÔNG raw SQL/f-string nối
    chuỗi):
    - `granularity="month"`: `func.date_format(order_date, "%Y-%m-01")` —
      cột `period` ép kiểu `datetime64` sau khi lấy dữ liệu.
    - `granularity="week"`: `func.date_format(order_date, "%x-%v")` — tuần
      ISO 8601 (`%v` = tuần 01-53 bắt đầu Thứ Hai, `%x` = năm ISO tương
      ứng). Cột `period` giữ dạng chuỗi `"YYYY-Www"`.

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        granularity: `"month"` (mặc định) hoặc `"week"`.
        date_from, date_to: Lọc theo `order_date`, tuỳ chọn.

    Returns:
        DataFrame với các cột: `period`, `status`, `order_count` — dạng dài
        (long format, 1 dòng/kỳ/trạng thái), sắp xếp tăng dần theo `period`
        — phù hợp để vẽ bar 100%/stacked bar theo thời gian trên trang
        Streamlit. Trả về DataFrame rỗng (đúng cột) nếu `scope.customer_ids`
        rỗng và `scope.unrestricted` là False.

    Raises:
        ValueError: nếu `granularity` không phải `"month"`/`"week"`.
    """
    if granularity not in ("month", "week"):
        raise ValueError(
            f"granularity phải là 'month' hoặc 'week', nhận: {granularity!r}"
        )

    engine = engine or get_engine()
    columns = ["period", "status", "order_count"]

    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_order_status_trend: scope rỗng (user_id={}) -> trả về DataFrame rỗng.",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    if granularity == "month":
        period_expr = func.date_format(SalesOrder.order_date, "%Y-%m-01")
    else:
        period_expr = func.date_format(SalesOrder.order_date, "%x-%v")

    stmt = select(
        period_expr.label("period"),
        SalesOrder.status.label("status"),
        func.count(SalesOrder.id).label("order_count"),
    ).group_by(period_expr, SalesOrder.status)
    stmt = _apply_scope_filter(stmt, scope)
    stmt = _apply_date_filter(stmt, date_from, date_to)
    stmt = stmt.order_by(period_expr)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns)
    if granularity == "month" and not df.empty:
        df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values(["period", "status"]).reset_index(drop=True)
    logger.info(
        "get_order_status_trend: user_id={} granularity={} -> {} dòng.",
        scope.user_id,
        granularity,
        len(df),
    )
    return df
