"""Trang Streamlit — Báo cáo Pricing: Thành đơn (theo Khối-Phòng-NV/dịch
vụ/khách hàng + xu hướng) và Nhà cung cấp (điểm đánh giá trung bình theo
NCC + xu hướng, có thể group theo dịch vụ) — 2 tab.

Theo CLAUDE.md mục 2 (tách lớp): trang này CHỈ gọi hàm từ
`src.services.report_pricing` rồi vẽ Plotly — KHÔNG viết SQL hay logic
tính KPI tại chỗ. Ngoại lệ duy nhất: ở tab "Thành đơn" > "Theo Khối-Phòng-
NV", trang tự `groupby(...).sum()` lại DataFrame mức chi tiết nhất (1
dòng/nhân viên, đã tính sẵn `total_requests`/`won_requests` ở service) để
đổi mức xem Khối/Phòng/NV mà không gọi lại DB — giống hệt cách làm ở
`src/app/pages/1_Bao_cao_Kinh_doanh.py::_render_by_org` (cộng dồn số đã
tính đúng, KHÔNG phải công thức nghiệp vụ mới); `win_rate` được TÍNH LẠI từ
`won_requests`/`total_requests` đã gộp (không cộng dồn trực tiếp cột
`win_rate`, vì tỷ lệ không cộng gộp được).

Theo CLAUDE.md mục 6 (rủi ro bảo mật nghiêm trọng nhất dự án): mọi
`@st.cache_data` PHẢI nhận tham số gắn `user_id`/`role_value` — xem
`_cached_data_scope` (lặp lại đúng mẫu đã có ở `src/app/main.py`, không tự
đặt quy ước cache mới). Toàn bộ dữ liệu phiên đăng nhập đọc từ
`st.session_state["lacco_auth_session"]` (đúng key đã dùng ở `main.py`),
KHÔNG dùng biến global.

*** RBAC KHÁC với trang Kinh doanh/Khách hàng — xem docstring
`src/services/report_pricing.py` *** — module Pricing lọc theo NHÂN VIÊN
PRICING phụ trách (`employee_id`/`department_id`), KHÔNG dùng
`scope.customer_ids`. Trang này chỉ gọi `scope` để hiển thị/truyền xuống
service, không tự viết logic phân quyền riêng tại đây.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from loguru import logger

from src.auth.scope import DataScope, compute_data_scope
from src.services import export_utils, report_pricing
from src.services.db_connection import get_engine

st.set_page_config(page_title="LACCO Dashboard — Báo cáo Pricing", layout="wide")

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
def _cached_win_rate_by_org(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache tỷ lệ thành đơn theo Khối-Phòng-NV — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_pricing.get_win_rate_by_org(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_win_rate_by_service(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache tỷ lệ thành đơn theo dịch vụ — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_pricing.get_win_rate_by_service(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_win_rate_by_customer(
    user_id: int,
    role_value: str,
    date_from: date | None,
    date_to: date | None,
    top_n: int,
) -> pd.DataFrame:
    """Cache tỷ lệ thành đơn theo khách hàng — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_pricing.get_win_rate_by_customer(
        scope, date_from=date_from, date_to=date_to, top_n=top_n
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_win_rate_trend(
    user_id: int,
    role_value: str,
    granularity: str,
    date_from: date | None,
    date_to: date | None,
) -> pd.DataFrame:
    """Cache xu hướng tỷ lệ thành đơn theo Tháng/Tuần — khoá cache gắn
    `user_id`/`role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_pricing.get_win_rate_trend(
        scope, granularity=granularity, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_supplier_score_by_supplier(
    user_id: int,
    role_value: str,
    date_from: date | None,
    date_to: date | None,
    group_by_service: bool,
) -> pd.DataFrame:
    """Cache điểm đánh giá trung bình theo nhà cung cấp — khoá cache gắn
    `user_id`/`role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_pricing.get_supplier_score_by_supplier(
        scope, date_from=date_from, date_to=date_to, group_by_service=group_by_service
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_supplier_score_trend(
    user_id: int,
    role_value: str,
    granularity: str,
    date_from: date | None,
    date_to: date | None,
    supplier_id: int | None,
) -> pd.DataFrame:
    """Cache xu hướng điểm đánh giá NCC theo Tháng/Tuần — khoá cache gắn
    `user_id`/`role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_pricing.get_supplier_score_trend(
        scope,
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id,
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_supplier_list(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache danh sách nhà cung cấp có dữ liệu trong phạm vi RBAC — dùng
    đổ vào `st.selectbox` — khoá cache gắn `user_id`/`role_value` (CLAUDE.md
    mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_pricing.get_supplier_list(scope)


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
    vấn DB mới. Không bọc `@st.cache_data` (CLAUDE.md mục 6). Nút PDF tách
    2 bước (bấm tạo rồi mới hiện nút tải) — Streamlit đánh giá lại `data=`
    mỗi lần rerun trang, gọi trực tiếp sẽ tốn kaleido render lại ở MỌI lần
    rerun (đã kiểm chứng thật, xem báo cáo bước 6.1)."""
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


def _date_filter_subtitle(
    date_from: date | None, date_to: date | None, date_col_label: str
) -> str | None:
    """Mô tả bộ lọc khoảng ngày đang áp dụng, dùng làm `subtitle` cho PDF —
    trả `None` nếu không lọc."""
    if date_from is None and date_to is None:
        return None
    tu = date_from.strftime("%d/%m/%Y") if date_from else "..."
    den = date_to.strftime("%d/%m/%Y") if date_to else "..."
    return f"Lọc theo {date_col_label}: từ {tu} đến {den}"


def _render_date_filters(*, key_prefix: str, date_col_label: str) -> tuple:
    """Vẽ 2 ô lọc khoảng ngày, tuỳ chọn — mặc định không giới hạn (None,
    None) để không ẩn dữ liệu ngoài ý muốn khi mới vào trang."""
    use_filter = st.checkbox(
        f"Lọc theo khoảng ngày ({date_col_label})",
        value=False,
        key=f"{key_prefix}_use_filter",
    )
    if not use_filter:
        return None, None
    col_from, col_to = st.columns(2)
    with col_from:
        date_from = st.date_input("Từ ngày", value=None, key=f"{key_prefix}_from")
    with col_to:
        date_to = st.date_input("Đến ngày", value=None, key=f"{key_prefix}_to")
    return date_from or None, date_to or None


def _render_win_rate_metrics(df: pd.DataFrame) -> None:
    total_requests = int(df["total_requests"].sum())
    won_requests = int(df["won_requests"].sum())
    win_rate = won_requests / total_requests if total_requests else 0.0
    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng số request giá", total_requests)
    col2.metric("Số request đã chốt đơn", won_requests)
    col3.metric("Tỷ lệ thành đơn", f"{win_rate:.1%}" if total_requests else "N/A")


def _render_win_rate_by_org(user_id: int, role_value: str, date_from, date_to) -> None:
    level = st.radio(
        "Mức xem", ["Khối", "Phòng", "Nhân viên"], horizontal=True, key="pr_org_level"
    )
    df = _cached_win_rate_by_org(user_id, role_value, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu tỷ lệ thành đơn theo Khối-Phòng-NV trong phạm "
            "vi được phép xem."
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
        df.groupby(group_cols, as_index=False)[["total_requests", "won_requests"]]
        .sum()
        .sort_values("total_requests", ascending=False)
    )
    # win_rate TÍNH LẠI từ tổng đã gộp — KHÔNG cộng dồn trực tiếp cột
    # win_rate (tỷ lệ không cộng gộp được, xem docstring đầu file).
    agg["win_rate"] = (agg["won_requests"] / agg["total_requests"]).where(
        agg["total_requests"] != 0, 0.0
    )

    _render_win_rate_metrics(agg)
    st.caption(f"Số dòng ({level}): {len(agg)}")

    if level in ("Nhân viên", "Phòng"):
        top_n = st.slider(
            "Số dòng hiển thị (top theo số request)", 5, 50, 20, key="pr_org_top_n"
        )
        agg = agg.head(top_n).reset_index(drop=True)

    fig = px.bar(
        agg,
        x=x_col,
        y="total_requests",
        color="win_rate",
        title=f"Số request giá theo {level} (màu = tỷ lệ thành đơn)",
        labels={
            x_col: level,
            "total_requests": "Tổng số request",
            "win_rate": "Tỷ lệ thành đơn",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(agg, use_container_width=True, hide_index=True)

    _render_export_buttons(
        agg,
        fig,
        key_prefix="pr_org",
        file_stub="pricing_thanh_don_theo_khoi_phong_nv",
        title=f"Tỷ lệ thành đơn theo {level}",
        subtitle=_date_filter_subtitle(date_from, date_to, "request_date"),
    )


def _render_win_rate_by_service(
    user_id: int, role_value: str, date_from, date_to
) -> None:
    df = _cached_win_rate_by_service(user_id, role_value, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu tỷ lệ thành đơn theo dịch vụ trong phạm vi được phép xem."
        )
        return

    _render_win_rate_metrics(df)

    fig = px.bar(
        df,
        x="service_name",
        y="total_requests",
        color="win_rate",
        title="Số request giá theo dịch vụ (màu = tỷ lệ thành đơn)",
        labels={
            "service_name": "Dịch vụ",
            "total_requests": "Tổng số request",
            "win_rate": "Tỷ lệ thành đơn",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        df,
        fig,
        key_prefix="pr_service",
        file_stub="pricing_thanh_don_theo_dich_vu",
        title="Tỷ lệ thành đơn theo dịch vụ",
        subtitle=_date_filter_subtitle(date_from, date_to, "request_date"),
    )


def _render_win_rate_by_customer(
    user_id: int, role_value: str, date_from, date_to
) -> None:
    top_n = st.slider(
        "Số khách hàng hiển thị (top theo số request)", 5, 50, 20, key="pr_cust_top_n"
    )
    df = _cached_win_rate_by_customer(user_id, role_value, date_from, date_to, top_n)
    if df.empty:
        st.warning(
            "Không có dữ liệu tỷ lệ thành đơn theo khách hàng trong phạm vi "
            "được phép xem."
        )
        return

    null_count = df["customer_id"].isna().sum()
    if null_count:
        st.caption(
            f"Có {null_count} nhóm 'Khách hàng tiềm năng/chưa có mã' "
            "(price_request.customer_id NULL) — vẫn hiển thị, không loại khỏi báo cáo."
        )

    _render_win_rate_metrics(df)

    fig = px.bar(
        df,
        x="customer_name",
        y="total_requests",
        color="win_rate",
        title=f"Top {len(df)} khách hàng theo số request giá (màu = tỷ lệ thành đơn)",
        labels={
            "customer_name": "Khách hàng",
            "total_requests": "Tổng số request",
            "win_rate": "Tỷ lệ thành đơn",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        df,
        fig,
        key_prefix="pr_customer",
        file_stub="pricing_thanh_don_theo_khach_hang",
        title=f"Top {len(df)} khách hàng theo số request giá",
        subtitle=_date_filter_subtitle(date_from, date_to, "request_date"),
    )


def _render_win_rate_trend(user_id: int, role_value: str, date_from, date_to) -> None:
    """Xu hướng tỷ lệ thành đơn theo Tháng/Tuần — dùng `px.line` (xu hướng
    theo thời gian, theo quy ước biểu đồ dự án)."""
    granularity_label = st.radio(
        "Gộp theo", ["Tháng", "Tuần"], horizontal=True, key="pr_trend_granularity"
    )
    granularity = "month" if granularity_label == "Tháng" else "week"

    df = _cached_win_rate_trend(user_id, role_value, granularity, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu xu hướng tỷ lệ thành đơn trong phạm vi được phép xem."
        )
        return

    _render_win_rate_metrics(df)

    fig = px.line(
        df,
        x="period",
        y="win_rate",
        markers=True,
        title=f"Xu hướng tỷ lệ thành đơn theo {granularity_label.lower()}",
        labels={"period": granularity_label, "win_rate": "Tỷ lệ thành đơn"},
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        df,
        fig,
        key_prefix="pr_win_trend",
        file_stub="pricing_xu_huong_thanh_don",
        title=f"Xu hướng tỷ lệ thành đơn theo {granularity_label.lower()}",
        subtitle=_date_filter_subtitle(date_from, date_to, "request_date"),
    )


def _render_supplier_by_supplier(
    user_id: int, role_value: str, date_from, date_to
) -> None:
    group_by_service = st.checkbox(
        "Group theo dịch vụ", value=False, key="pr_supplier_group_service"
    )
    df = _cached_supplier_score_by_supplier(
        user_id, role_value, date_from, date_to, group_by_service
    )
    if df.empty:
        st.warning(
            "Không có dữ liệu đánh giá nhà cung cấp trong phạm vi được phép xem."
        )
        return

    avg_score = df["avg_score"].mean()
    col1, col2 = st.columns(2)
    col1.metric("Điểm trung bình chung", f"{avg_score:.1f}" if len(df) else "N/A")
    col2.metric("Số dòng", len(df))
    st.caption("Thang điểm 0-100 (đã COO xác nhận 22/08/2026).")

    color_col = "service_name" if group_by_service else None
    fig = px.bar(
        df,
        x="supplier_name",
        y="avg_score",
        color=color_col,
        barmode="group" if group_by_service else "relative",
        title="Điểm đánh giá trung bình theo nhà cung cấp"
        + (" (theo dịch vụ)" if group_by_service else ""),
        labels={
            "supplier_name": "Nhà cung cấp",
            "avg_score": "Điểm trung bình",
            "service_name": "Dịch vụ",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        df,
        fig,
        key_prefix="pr_supplier",
        file_stub="pricing_diem_nha_cung_cap",
        title="Điểm đánh giá trung bình theo nhà cung cấp",
        subtitle=_date_filter_subtitle(date_from, date_to, "period"),
    )


def _render_supplier_trend(user_id: int, role_value: str, date_from, date_to) -> None:
    """Xu hướng điểm đánh giá NCC theo Tháng/Tuần — `px.line`, có thể lọc
    riêng 1 nhà cung cấp qua `st.selectbox`."""
    granularity_label = st.radio(
        "Gộp theo", ["Tháng", "Tuần"], horizontal=True, key="pr_supplier_trend_gran"
    )
    granularity = "month" if granularity_label == "Tháng" else "week"

    supplier_df = _cached_supplier_list(user_id, role_value)
    supplier_options = {"Tất cả nhà cung cấp": None}
    if not supplier_df.empty:
        supplier_options.update(
            dict(zip(supplier_df["supplier_name"], supplier_df["supplier_id"]))
        )
    supplier_label = st.selectbox(
        "Nhà cung cấp", list(supplier_options.keys()), key="pr_supplier_trend_pick"
    )
    supplier_id = supplier_options[supplier_label]

    df = _cached_supplier_score_trend(
        user_id, role_value, granularity, date_from, date_to, supplier_id
    )
    if df.empty:
        st.warning(
            "Không có dữ liệu xu hướng đánh giá nhà cung cấp trong phạm vi "
            "được phép xem."
        )
        return

    avg_score = df["avg_score"].mean()
    col1, col2 = st.columns(2)
    col1.metric("Điểm trung bình (cả kỳ)", f"{avg_score:.1f}" if len(df) else "N/A")
    col2.metric("Số kỳ có dữ liệu", len(df))

    fig = px.line(
        df,
        x="period",
        y="avg_score",
        markers=True,
        title=f"Xu hướng điểm đánh giá NCC theo {granularity_label.lower()}"
        + (f" — {supplier_label}" if supplier_id is not None else ""),
        labels={"period": granularity_label, "avg_score": "Điểm trung bình"},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        df,
        fig,
        key_prefix="pr_supplier_trend",
        file_stub="pricing_xu_huong_diem_nha_cung_cap",
        title=f"Xu hướng điểm đánh giá NCC theo {granularity_label.lower()}",
        subtitle=_date_filter_subtitle(date_from, date_to, "period"),
    )


def main() -> None:
    """Entry point trang Báo cáo Pricing — kiểm tra đăng nhập trước (đúng
    key `st.session_state["lacco_auth_session"]` dùng ở `main.py`), rồi
    hiển thị 2 tab: Thành đơn (4 tab con) / Nhà cung cấp (2 tab con)."""
    st.title("Báo cáo Pricing")

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
    # RBAC module này lọc theo NHÂN VIÊN phụ trách, KHÔNG dùng
    # scope.customer_ids (xem docstring src/services/report_pricing.py) —
    # dùng report_pricing._scope_is_empty()-tương-đương tại đây: Manager
    # rỗng nếu thiếu department_id, User rỗng nếu thiếu employee_id.
    scope_empty = not scope.unrestricted and (
        (scope.role.value == "Manager" and scope.department_id is None)
        or (scope.role.value == "User" and scope.employee_id is None)
    )
    if scope_empty:
        st.warning(
            "Tài khoản này chưa xác định được phạm vi Khối/Phòng/NV để hiển "
            "thị báo cáo Pricing (xem `scope.description` để biết lý do)."
        )
        logger.warning(
            "Trang Báo cáo Pricing: user_id={} scope rỗng, description={}",
            user_id,
            scope.description,
        )
        st.stop()

    tab_win_rate, tab_supplier = st.tabs(["Thành đơn", "Nhà cung cấp"])

    with tab_win_rate:
        date_from, date_to = _render_date_filters(
            key_prefix="pr_winrate_date", date_col_label="request_date"
        )
        sub_org, sub_service, sub_customer, sub_trend = st.tabs(
            ["Theo Khối-Phòng-NV", "Theo dịch vụ", "Theo khách hàng", "Xu hướng"]
        )
        with sub_org:
            _render_win_rate_by_org(user_id, role_value, date_from, date_to)
        with sub_service:
            _render_win_rate_by_service(user_id, role_value, date_from, date_to)
        with sub_customer:
            _render_win_rate_by_customer(user_id, role_value, date_from, date_to)
        with sub_trend:
            _render_win_rate_trend(user_id, role_value, date_from, date_to)

    with tab_supplier:
        date_from_sup, date_to_sup = _render_date_filters(
            key_prefix="pr_supplier_date", date_col_label="period"
        )
        sub_by_supplier, sub_supplier_trend = st.tabs(["Theo nhà cung cấp", "Xu hướng"])
        with sub_by_supplier:
            _render_supplier_by_supplier(
                user_id, role_value, date_from_sup, date_to_sup
            )
        with sub_supplier_trend:
            _render_supplier_trend(user_id, role_value, date_from_sup, date_to_sup)


if __name__ == "__main__":
    main()
