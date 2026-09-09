"""Trang Streamlit — Báo cáo Đơn hàng: Tình trạng đơn hàng (`status`) và
Tình trạng xuất hoá đơn (`invoice_status`), đếm số lượng đơn theo TỪNG giá
trị thực tế gặp trong dữ liệu (2 tab), cộng thêm xu hướng theo thời gian
cho tình trạng đơn hàng.

Theo CLAUDE.md mục 2 (tách lớp): trang này CHỈ gọi hàm từ
`src.services.report_don_hang` rồi vẽ Plotly — KHÔNG viết SQL hay logic
tính KPI tại chỗ.

Lưu ý quan trọng — khác với trang Kinh doanh (`1_Bao_cao_Kinh_doanh.py`):
đây là báo cáo ĐẾM SỐ LƯỢNG đơn theo trạng thái, KHÔNG phải báo cáo doanh
thu, nên KHÔNG loại trừ/hiển thị riêng đơn "Huỷ" — đơn "Huỷ" là 1 trong các
giá trị `status` được đếm/hiển thị bình thường như mọi giá trị khác (xem
docstring `src/services/report_don_hang.py`).

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
from src.services import report_don_hang
from src.services.db_connection import get_engine

st.set_page_config(page_title="LACCO Dashboard — Báo cáo Đơn hàng", layout="wide")

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
def _cached_status_counts(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache số lượng đơn theo `status` — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6) cộng thêm khoảng ngày lọc."""
    scope = _cached_data_scope(user_id, role_value)
    return report_don_hang.get_order_status_counts(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_invoice_status_counts(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache số lượng đơn theo `invoice_status` — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6) cộng thêm khoảng ngày lọc."""
    scope = _cached_data_scope(user_id, role_value)
    return report_don_hang.get_invoice_status_counts(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_status_trend(
    user_id: int,
    role_value: str,
    granularity: str,
    date_from: date | None,
    date_to: date | None,
) -> pd.DataFrame:
    """Cache xu hướng số lượng đơn theo `status` (Tháng/Tuần) — khoá cache
    gắn `user_id`/`role_value` (CLAUDE.md mục 6) cộng thêm `granularity` và
    khoảng ngày lọc, cùng mẫu các hàm `_cached_*` khác trong file."""
    scope = _cached_data_scope(user_id, role_value)
    return report_don_hang.get_order_status_trend(
        scope, granularity=granularity, date_from=date_from, date_to=date_to
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
        date_from = st.date_input("Từ ngày", value=None, key="dh_date_from")
    with col_to:
        date_to = st.date_input("Đến ngày", value=None, key="dh_date_to")
    return date_from or None, date_to or None


def _render_order_status(user_id: int, role_value: str, date_from, date_to) -> None:
    """Tab "Tình trạng đơn hàng" — đếm theo TỪNG giá trị `status` thực tế
    gặp trong dữ liệu (không hardcode danh sách trạng thái), cộng thêm xu
    hướng theo thời gian bằng bar 100% (nhiều hạng mục — theo quy ước
    Plotly của dự án, dùng bar 100% thay pie)."""
    df = _cached_status_counts(user_id, role_value, date_from, date_to)
    if df.empty:
        st.warning("Không có dữ liệu tình trạng đơn hàng trong phạm vi được phép xem.")
        return

    total_orders = int(df["order_count"].sum())
    col1, col2 = st.columns(2)
    col1.metric("Tổng số đơn", f"{total_orders:,}")
    col2.metric("Số giá trị status gặp trong dữ liệu", len(df))
    st.caption(
        "Đếm theo TẤT CẢ trạng thái thực tế gặp trong dữ liệu (bao gồm cả "
        '"Huỷ") — đây là báo cáo đếm số lượng, không phải doanh thu nên '
        "không loại trừ đơn Huỷ (khác với trang Báo cáo Kinh doanh)."
    )

    fig_bar = px.bar(
        df,
        x="status",
        y="order_count",
        title="Số lượng đơn theo tình trạng (status)",
        labels={"status": "Tình trạng đơn hàng", "order_count": "Số lượng đơn"},
    )
    st.plotly_chart(fig_bar, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Xu hướng theo thời gian")
    granularity_label = st.radio(
        "Gộp theo", ["Tháng", "Tuần"], horizontal=True, key="dh_trend_granularity"
    )
    granularity = "month" if granularity_label == "Tháng" else "week"
    trend_df = _cached_status_trend(
        user_id, role_value, granularity, date_from, date_to
    )
    if trend_df.empty:
        st.warning("Không có dữ liệu xu hướng tình trạng đơn hàng.")
        return

    # Nhiều hạng mục (nhiều giá trị status khác nhau) -> bar 100% thay pie,
    # theo đúng quy ước Plotly của dự án (CLAUDE.md/persona report-builder).
    pivot = trend_df.pivot_table(
        index="period", columns="status", values="order_count", fill_value=0
    )
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    pivot_pct = pivot_pct.reset_index()
    melted_pct = pivot_pct.melt(
        id_vars="period", var_name="Tình trạng", value_name="Tỷ lệ (%)"
    )
    fig_trend = px.bar(
        melted_pct,
        x="period",
        y="Tỷ lệ (%)",
        color="Tình trạng",
        title=f"Cơ cấu tình trạng đơn hàng theo {granularity_label.lower()} (bar 100%)",
        labels={"period": granularity_label},
    )
    fig_trend.update_layout(barmode="relative")
    st.plotly_chart(fig_trend, use_container_width=True)
    st.dataframe(trend_df, use_container_width=True, hide_index=True)


def _render_invoice_status(user_id: int, role_value: str, date_from, date_to) -> None:
    """Tab "Tình trạng xuất hoá đơn" — đếm theo TỪNG giá trị `invoice_
    status` thực tế gặp trong dữ liệu."""
    df = _cached_invoice_status_counts(user_id, role_value, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu tình trạng xuất hoá đơn trong phạm vi được phép xem."
        )
        return

    total_orders = int(df["order_count"].sum())
    col1, col2 = st.columns(2)
    col1.metric("Tổng số đơn", f"{total_orders:,}")
    col2.metric("Số giá trị invoice_status gặp trong dữ liệu", len(df))

    fig = px.bar(
        df,
        x="invoice_status",
        y="order_count",
        title="Số lượng đơn theo tình trạng xuất hoá đơn (invoice_status)",
        labels={
            "invoice_status": "Tình trạng xuất hoá đơn",
            "order_count": "Số lượng đơn",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    """Entry point trang Báo cáo Đơn hàng — kiểm tra đăng nhập trước (đúng
    key `st.session_state["lacco_auth_session"]` dùng ở `main.py`), rồi
    hiển thị 2 tab: tình trạng đơn hàng / tình trạng xuất hoá đơn."""
    st.title("Báo cáo Đơn hàng — Tình trạng đơn hàng & Xuất hoá đơn")

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
            "Trang Báo cáo Đơn hàng: user_id={} scope rỗng, description={}",
            user_id,
            scope.description,
        )
        st.stop()

    date_from, date_to = _render_date_filters()

    tab_status, tab_invoice = st.tabs(
        ["Tình trạng đơn hàng", "Tình trạng xuất hoá đơn"]
    )
    with tab_status:
        _render_order_status(user_id, role_value, date_from, date_to)
    with tab_invoice:
        _render_invoice_status(user_id, role_value, date_from, date_to)


if __name__ == "__main__":
    main()
