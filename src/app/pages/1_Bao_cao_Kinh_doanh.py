"""Trang Streamlit — Báo cáo Kinh doanh: Doanh thu/lãi lỗ theo dịch vụ,
khách hàng, Khối-Phòng-NV, và xu hướng theo thời gian (4 tab).

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
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from loguru import logger

from src.auth.scope import DataScope, compute_data_scope
from src.services import export_utils, report_kinh_doanh
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


@st.cache_data(ttl=60, show_spinner=False)
def _cached_trend(
    user_id: int,
    role_value: str,
    granularity: str,
    date_from: date | None,
    date_to: date | None,
) -> pd.DataFrame:
    """Cache xu hướng doanh thu/lãi lỗ theo Tháng/Tuần — khoá cache gắn
    `user_id`/`role_value` (CLAUDE.md mục 6) cộng thêm `granularity` và
    khoảng ngày lọc, cùng mẫu các hàm `_cached_by_*` khác trong file."""
    scope = _cached_data_scope(user_id, role_value)
    return report_kinh_doanh.get_revenue_profit_trend(
        scope, granularity=granularity, date_from=date_from, date_to=date_to
    )


def _date_filter_subtitle(date_from: date | None, date_to: date | None) -> str | None:
    """Mô tả bộ lọc khoảng ngày đang áp dụng, dùng làm `subtitle` cho PDF —
    trả `None` nếu không lọc (để `build_pdf_report_bytes` bỏ qua dòng phụ)."""
    if date_from is None and date_to is None:
        return None
    tu = date_from.strftime("%d/%m/%Y") if date_from else "..."
    den = date_to.strftime("%d/%m/%Y") if date_to else "..."
    return f"Lọc theo order_date: từ {tu} đến {den}"


def _render_export_buttons(
    df: pd.DataFrame,
    fig: Any,
    *,
    key_prefix: str,
    file_stub: str,
    title: str,
    subtitle: str | None = None,
) -> None:
    """2 nút xuất Excel/PDF cho 1 báo cáo con (VIỆC 3, bước 6.1) — dùng
    đúng `df`/`fig` đã tính sẵn ở hàm `_render_*` gọi hàm này, KHÔNG truy
    vấn DB mới. Không bọc `@st.cache_data` (không truy vấn DB, không cần
    thiết — tránh rủi ro cache sai phạm vi không cần thiết theo CLAUDE.md
    mục 6). Nút PDF tách 2 bước (bấm tạo rồi mới hiện nút tải) thay vì gọi
    `build_pdf_report_bytes` trực tiếp trong `data=` — Streamlit ĐÁNH GIÁ
    LẠI `data=` mỗi lần rerun trang (mọi tương tác widget khác trên trang
    đều rerun), nếu gọi trực tiếp thì MỖI lần rerun đều tốn kaleido render
    chart lại (vài giây, hoặc treo/timeout ~20s nếu môi trường lỗi kaleido —
    đã gặp thật khi test module `export_utils`, xem báo cáo bước 6.1)."""
    col_excel, col_pdf = st.columns(2)
    today_str = date.today().isoformat()

    with col_excel:
        st.download_button(
            "⬇️ Xuất Excel",
            data=export_utils.dataframe_to_excel_bytes(
                df, sheet_name=key_prefix[:31], title=title
            ),
            file_name=f"{file_stub}_{today_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_export_xlsx",
        )

    with col_pdf:
        if st.button("⬇️ Xuất PDF", key=f"{key_prefix}_export_pdf_btn"):
            try:
                pdf_bytes = export_utils.build_pdf_report_bytes(
                    df, fig, title=title, subtitle=subtitle
                )
            except RuntimeError as exc:
                st.error(f"Không thể tạo file PDF: {exc}")
                logger.error(
                    "Xuất PDF lỗi tại '{}' (title='{}'): {}", key_prefix, title, exc
                )
            else:
                st.download_button(
                    "Tải file PDF",
                    data=pdf_bytes,
                    file_name=f"{file_stub}_{today_str}.pdf",
                    mime="application/pdf",
                    key=f"{key_prefix}_export_pdf_dl",
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
    total_margin = total_profit / total_revenue if total_revenue else 0.0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng doanh thu", f"{total_revenue:,.0f}")
    col2.metric("Tổng lãi/lỗ", f"{total_profit:,.0f}")
    col3.metric("Tỷ suất lợi nhuận", f"{total_margin:.1%}" if total_revenue else "N/A")
    col4.metric("Số dịch vụ", len(df))

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

    _render_export_buttons(
        df,
        fig,
        key_prefix="kd_service",
        file_stub="kinh_doanh_theo_dich_vu",
        title="Doanh thu / Lãi lỗ theo dịch vụ",
        subtitle=_date_filter_subtitle(date_from, date_to),
    )


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

    total_revenue = df["revenue"].sum()
    total_profit = df["profit"].sum()
    total_margin = total_profit / total_revenue if total_revenue else 0.0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng doanh thu", f"{total_revenue:,.0f}")
    col2.metric("Tổng lãi/lỗ", f"{total_profit:,.0f}")
    col3.metric("Tỷ suất lợi nhuận", f"{total_margin:.1%}" if total_revenue else "N/A")
    col4.metric("Số khách hàng", len(df))

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

    _render_export_buttons(
        df,
        fig,
        key_prefix="kd_customer",
        file_stub="kinh_doanh_theo_khach_hang",
        title="Doanh thu / Lãi lỗ theo khách hàng (toàn bộ, biểu đồ chỉ hiện top "
        f"{len(top_df)})",
        subtitle=_date_filter_subtitle(date_from, date_to),
    )


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

    total_revenue = agg["revenue"].sum()
    total_profit = agg["profit"].sum()
    total_margin = total_profit / total_revenue if total_revenue else 0.0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng doanh thu", f"{total_revenue:,.0f}")
    col2.metric("Tổng lãi/lỗ", f"{total_profit:,.0f}")
    col3.metric("Tỷ suất lợi nhuận", f"{total_margin:.1%}" if total_revenue else "N/A")
    col4.metric(f"Số dòng ({level})", len(agg))

    # Khối thường ít dòng — không cần giới hạn top-N. Nhân viên/Phòng có
    # thể nhiều dòng, thêm slider top-N giống mẫu `kd_top_n` ở
    # `_render_by_customer` nhưng dùng key riêng để không xung đột.
    if level in ("Nhân viên", "Phòng"):
        top_n = st.slider(
            "Số dòng hiển thị (top theo doanh thu)",
            5,
            50,
            20,
            key="kd_org_top_n",
        )
        agg = agg.head(top_n).reset_index(drop=True)

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

    _render_export_buttons(
        agg,
        fig,
        key_prefix="kd_org",
        file_stub="kinh_doanh_theo_khoi_phong_nv",
        title=f"Doanh thu / Lãi lỗ theo {level}",
        subtitle=_date_filter_subtitle(date_from, date_to),
    )


def _render_trend(user_id: int, role_value: str, date_from, date_to) -> None:
    """Tab "Xu hướng theo thời gian" — Doanh thu/Lãi lỗ gộp theo Tháng hoặc
    Tuần (`get_revenue_profit_trend`), vẽ `px.line` (xu hướng theo thời
    gian dùng line chart, KHÔNG dùng bar — theo quy ước biểu đồ dự án)."""
    granularity_label = st.radio(
        "Gộp theo", ["Tháng", "Tuần"], horizontal=True, key="kd_trend_granularity"
    )
    granularity = "month" if granularity_label == "Tháng" else "week"

    df = _cached_trend(user_id, role_value, granularity, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu xu hướng doanh thu/lãi lỗ trong phạm vi được phép xem."
        )
        return

    total_revenue = df["revenue"].sum()
    total_profit = df["profit"].sum()
    total_margin = total_profit / total_revenue if total_revenue else 0.0
    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng doanh thu", f"{total_revenue:,.0f}")
    col2.metric("Tổng lãi/lỗ", f"{total_profit:,.0f}")
    col3.metric("Tỷ suất lợi nhuận", f"{total_margin:.1%}" if total_revenue else "N/A")

    melted = df.melt(
        id_vars=["period"],
        value_vars=["revenue", "profit"],
        var_name="Chỉ tiêu",
        value_name="Giá trị",
    )
    label_map = {"revenue": "Doanh thu", "profit": "Lãi/lỗ"}
    melted["Chỉ tiêu"] = melted["Chỉ tiêu"].map(label_map)
    fig = px.line(
        melted,
        x="period",
        y="Giá trị",
        color="Chỉ tiêu",
        markers=True,
        title=f"Xu hướng Doanh thu / Lãi lỗ theo {granularity_label.lower()}",
        labels={"period": granularity_label},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        df,
        fig,
        key_prefix="kd_trend",
        file_stub="kinh_doanh_xu_huong",
        title=f"Xu hướng Doanh thu / Lãi lỗ theo {granularity_label.lower()}",
        subtitle=_date_filter_subtitle(date_from, date_to),
    )


def main() -> None:
    """Entry point trang Báo cáo Kinh doanh — kiểm tra đăng nhập trước
    (đúng key `st.session_state["lacco_auth_session"]` dùng ở `main.py`),
    rồi hiển thị 4 tab: theo dịch vụ / khách hàng / Khối-Phòng-NV / xu hướng
    theo thời gian."""
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

    tab_service, tab_customer, tab_org, tab_trend = st.tabs(
        [
            "Theo dịch vụ",
            "Theo khách hàng",
            "Theo Khối-Phòng-NV",
            "Xu hướng theo thời gian",
        ]
    )
    with tab_service:
        _render_by_service(user_id, role_value, date_from, date_to)
    with tab_customer:
        _render_by_customer(user_id, role_value, date_from, date_to)
    with tab_org:
        _render_by_org(user_id, role_value, date_from, date_to)
    with tab_trend:
        _render_trend(user_id, role_value, date_from, date_to)


if __name__ == "__main__":
    main()
