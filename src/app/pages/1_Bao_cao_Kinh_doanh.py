"""Trang Streamlit — Báo cáo Kinh doanh: Doanh thu/lãi lỗ theo dịch vụ,
khách hàng, và Khối-Phòng-NV (3 tab).

Theo CLAUDE.md mục 2 (tách lớp): trang này CHỈ gọi hàm từ
`src.services.report_kinh_doanh` rồi vẽ Plotly — KHÔNG viết SQL hay logic
tính KPI tại chỗ. Ngoại lệ duy nhất: ở tab "Theo Khối-Phòng-NV", trang tự
`groupby(...).sum()` lại DataFrame mức chi tiết nhất (1 dòng/nhân viên,
đã tính sẵn `revenue`/`order_cost`/`profit` ở service) để đổi mức xem
Khối/Phòng/NV mà không gọi lại DB — đây là cộng dồn lại số đã tính đúng
(cộng dồn có tính cộng gộp), KHÔNG phải công thức nghiệp vụ mới.

Theo CLAUDE.md mục 6 (rủi ro bảo mật nghiêm trọng nhất dự án): mọi
`@st.cache_data` PHẢI nhận tham số gắn `user_id`/`role_value` — xem
`_cached_data_scope` (lặp lại đúng mẫu đã có ở `src/app/main.py`, không tự
đặt quy ước cache mới). Toàn bộ dữ liệu phiên đăng nhập đọc từ
`st.session_state["lacco_auth_session"]` (đúng key đã dùng ở `main.py`),
KHÔNG dùng biến global.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
from loguru import logger

from src.auth.scope import DataScope, compute_data_scope
from src.services import report_kinh_doanh
from src.services.db_connection import get_engine

st.set_page_config(page_title="LACCO Dashboard — Báo cáo Kinh doanh", layout="wide")

# Đúng key đã dùng ở `src/app/main.py` — KHÔNG tự đặt quy ước session mới.
_SESSION_KEY = "lacco_auth_session"


@st.cache_data(ttl=60, show_spinner=False)
def _cached_data_scope(user_id: int, role_value: str) -> DataScope:
    """Cache phạm vi dữ liệu RBAC, TTL 60s — lặp lại đúng mẫu
    `_cached_data_scope` ở `src/app/main.py` (không import trực tiếp từ đó
    vì `main.py` gọi `st.set_page_config()` ở cấp module, không an toàn để
    import trong app multipage). BẮT BUỘC nhận `user_id` VÀ `role_value`
    làm tham số (CLAUDE.md mục 6) để Streamlit dùng làm khoá cache theo
    từng user, tránh lộ dữ liệu phạm vi của user A sang user B.
    """
    return compute_data_scope(user_id, engine=get_engine())


@st.cache_data(ttl=60, show_spinner=False)
def _cached_cancelled_summary(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> dict[str, int | float]:
    """Cache số lượng/giá trị đơn "Huỷ" (loại trừ khỏi doanh thu ở trên) —
    khoá cache gắn `user_id`/`role_value` (CLAUDE.md mục 6), cùng mẫu các
    hàm `_cached_by_*` khác trong file."""
    scope = _cached_data_scope(user_id, role_value)
    return report_kinh_doanh.get_cancelled_orders_summary(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_by_service(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache doanh thu/lãi lỗ theo dịch vụ — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6) cộng thêm khoảng ngày lọc."""
    scope = _cached_data_scope(user_id, role_value)
    return report_kinh_doanh.get_revenue_profit_by_service(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_by_customer(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache doanh thu/lãi lỗ theo khách hàng — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6) cộng thêm khoảng ngày lọc."""
    scope = _cached_data_scope(user_id, role_value)
    return report_kinh_doanh.get_revenue_profit_by_customer(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_by_org(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache doanh thu/lãi lỗ theo Khối-Phòng-NV (mức chi tiết nhất, 1
    dòng/nhân viên) — khoá cache gắn `user_id`/`role_value` (CLAUDE.md mục
    6) cộng thêm khoảng ngày lọc."""
    scope = _cached_data_scope(user_id, role_value)
    return report_kinh_doanh.get_revenue_profit_by_org(
        scope, date_from=date_from, date_to=date_to
    )


def _render_date_filters() -> tuple[date | None, date | None]:
    """Vẽ 2 ô lọc khoảng ngày (`order_date`), tuỳ chọn — mặc định không
    giới hạn (None, None) để không ẩn dữ liệu ngoài ý muốn khi mới vào
    trang."""
    use_filter = st.checkbox("Lọc theo khoảng ngày đặt hàng (order_date)", value=False)
    if not use_filter:
        return None, None
    col_from, col_to = st.columns(2)
    with col_from:
        date_from = st.date_input("Từ ngày", value=None, key="kd_date_from")
    with col_to:
        date_to = st.date_input("Đến ngày", value=None, key="kd_date_to")
    return date_from or None, date_to or None


def _render_by_service(user_id: int, role_value: str, date_from, date_to) -> None:
    df = _cached_by_service(user_id, role_value, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu doanh thu theo dịch vụ trong phạm vi được phép xem."
        )
        return

    total_revenue = df["revenue"].sum()
    total_profit = df["profit"].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng doanh thu", f"{total_revenue:,.0f}")
    col2.metric("Tổng lãi/lỗ", f"{total_profit:,.0f}")
    col3.metric("Số dịch vụ", len(df))

    cancelled = _cached_cancelled_summary(user_id, role_value, date_from, date_to)
    st.caption(
        f"Đã loại trừ {cancelled['cancelled_order_count']} đơn Huỷ "
        f"(giá trị {cancelled['cancelled_revenue']:,.0f} đ) khỏi doanh thu ở trên."
    )

    melted = df.melt(
        id_vars=["service_name"],
        value_vars=["revenue", "order_cost", "profit"],
        var_name="Chỉ tiêu",
        value_name="Giá trị",
    )
    label_map = {"revenue": "Doanh thu", "order_cost": "Giá vốn", "profit": "Lãi/lỗ"}
    melted["Chỉ tiêu"] = melted["Chỉ tiêu"].map(label_map)
    fig = px.bar(
        melted,
        x="service_name",
        y="Giá trị",
        color="Chỉ tiêu",
        barmode="group",
        title="Doanh thu / Giá vốn / Lãi lỗ theo dịch vụ",
        labels={"service_name": "Dịch vụ"},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_by_customer(user_id: int, role_value: str, date_from, date_to) -> None:
    top_n = st.slider(
        "Số khách hàng hiển thị (top theo doanh thu)", 5, 50, 20, key="kd_top_n"
    )
    df = _cached_by_customer(user_id, role_value, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu doanh thu theo khách hàng trong phạm vi được phép xem."
        )
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng doanh thu", f"{df['revenue'].sum():,.0f}")
    col2.metric("Tổng lãi/lỗ", f"{df['profit'].sum():,.0f}")
    col3.metric("Số khách hàng", len(df))

    top_df = df.head(top_n)
    fig = px.bar(
        top_df,
        x="customer_name",
        y="revenue",
        color="profit",
        title=f"Top {len(top_df)} khách hàng theo doanh thu",
        labels={
            "customer_name": "Khách hàng",
            "revenue": "Doanh thu",
            "profit": "Lãi/lỗ",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_by_org(user_id: int, role_value: str, date_from, date_to) -> None:
    level = st.radio(
        "Mức xem", ["Khối", "Phòng", "Nhân viên"], horizontal=True, key="kd_org_level"
    )
    df = _cached_by_org(user_id, role_value, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu doanh thu theo Khối-Phòng-NV trong phạm vi được phép xem."
        )
        return

    if level == "Khối":
        group_cols, x_col = ["division_name"], "division_name"
    elif level == "Phòng":
        group_cols, x_col = ["division_name", "department_name"], "department_name"
    else:
        group_cols = ["division_name", "department_name", "employee_name"]
        x_col = "employee_name"

    agg = (
        df.groupby(group_cols, as_index=False)[
            ["order_count", "revenue", "order_cost", "profit"]
        ]
        .sum()
        .sort_values("revenue", ascending=False)
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng doanh thu", f"{agg['revenue'].sum():,.0f}")
    col2.metric("Tổng lãi/lỗ", f"{agg['profit'].sum():,.0f}")
    col3.metric(f"Số dòng ({level})", len(agg))

    fig = px.bar(
        agg,
        x=x_col,
        y="revenue",
        color="profit",
        title=f"Doanh thu theo {level}",
        labels={x_col: level, "revenue": "Doanh thu", "profit": "Lãi/lỗ"},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(agg, use_container_width=True, hide_index=True)


def main() -> None:
    """Entry point trang Báo cáo Kinh doanh — kiểm tra đăng nhập trước
    (đúng key `st.session_state["lacco_auth_session"]` dùng ở `main.py`),
    rồi hiển thị 3 tab theo dịch vụ / khách hàng / Khối-Phòng-NV."""
    st.title("Báo cáo Kinh doanh — Doanh thu / Lãi lỗ")

    session = st.session_state.get(_SESSION_KEY)
    if session is None:
        st.warning("Vui lòng đăng nhập ở trang chính (Home) trước khi xem báo cáo.")
        st.stop()

    user_id = session["user_id"]
    role_value = session["role"]
    st.caption(
        f"Đang xem với vai trò **{role_value}** — tài khoản **{session['username']}**."
    )

    scope = _cached_data_scope(user_id, role_value)
    if not scope.unrestricted and not scope.customer_ids:
        st.warning(
            "Tài khoản này chưa xác định được phạm vi khách hàng nào để hiển "
            "thị báo cáo (xem `scope.description` để biết lý do)."
        )
        logger.warning(
            "Trang Báo cáo Kinh doanh: user_id={} scope rỗng, description={}",
            user_id,
            scope.description,
        )
        st.stop()

    date_from, date_to = _render_date_filters()

    tab_service, tab_customer, tab_org = st.tabs(
        ["Theo dịch vụ", "Theo khách hàng", "Theo Khối-Phòng-NV"]
    )
    with tab_service:
        _render_by_service(user_id, role_value, date_from, date_to)
    with tab_customer:
        _render_by_customer(user_id, role_value, date_from, date_to)
    with tab_org:
        _render_by_org(user_id, role_value, date_from, date_to)


if __name__ == "__main__":
    main()
