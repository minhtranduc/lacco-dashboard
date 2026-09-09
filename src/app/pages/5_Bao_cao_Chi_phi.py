"""Trang Streamlit — Báo cáo Chi phí: Theo Khối (so sánh `cost` thực tế với
`budget` cùng kỳ, theo Khối + xu hướng theo thời gian) và Theo Nhóm nhân sự
(`personnel_cost` theo `staff_group` + xu hướng) — 2 tab.

Theo CLAUDE.md mục 2 (tách lớp): trang này CHỈ gọi hàm từ
`src.services.report_chi_phi` rồi vẽ Plotly — KHÔNG viết SQL hay logic tính
KPI tại chỗ.

Theo CLAUDE.md mục 6 (rủi ro bảo mật nghiêm trọng nhất dự án): mọi
`@st.cache_data` PHẢI nhận tham số gắn `user_id`/`role_value` — xem
`_cached_data_scope` (lặp lại đúng mẫu đã có ở `src/app/main.py`, không tự
đặt quy ước cache mới). Toàn bộ dữ liệu phiên đăng nhập đọc từ
`st.session_state["lacco_auth_session"]` (đúng key đã dùng ở `main.py`),
KHÔNG dùng biến global.

*** BẮT BUỘC RBAC — 2 quyết định COO xác nhận 09/09/2026 (dữ liệu tài chính
nhạy cảm), xem docstring đầy đủ ở `src/services/report_chi_phi.py` ***

1) Tab "Theo Khối": ẨN HẲN sub-report cho role User (thay bằng thông báo rõ
   ràng "Không có dữ liệu ở cấp nhân viên cho báo cáo này") — kiểm tra
   `scope.role` TRƯỚC khi gọi service, KHÔNG chỉ dựa vào DataFrame rỗng trả
   về (dù service cũng tự chặn — phòng vệ kép).
2) Tab "Theo Nhóm nhân sự": ẨN HẲN toàn bộ tab nếu `scope.unrestricted` là
   `False` (Manager/User) — service raise `PermissionError` nếu bị gọi
   nhầm, trang này bọc `try/except PermissionError` quanh lệnh gọi service
   làm lớp phòng vệ thứ 2 (không để lộ traceback cho người dùng cuối).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
from loguru import logger

from src.auth.scope import DataScope, compute_data_scope
from src.db.models.enums import UserRole
from src.services import report_chi_phi
from src.services.db_connection import get_engine

st.set_page_config(page_title="LACCO Dashboard — Báo cáo Chi phí", layout="wide")

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


# ---------------------------------------------------------------------------
# Cache — Theo Khối
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60, show_spinner=False)
def _cached_cost_vs_budget_by_division(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache chi vs ngân sách theo Khối — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_chi_phi.get_cost_vs_budget_by_division(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_cost_vs_budget_trend(
    user_id: int,
    role_value: str,
    granularity: str,
    date_from: date | None,
    date_to: date | None,
    division_id: int | None,
) -> pd.DataFrame:
    """Cache xu hướng chi vs ngân sách theo Tháng/Tuần — khoá cache gắn
    `user_id`/`role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_chi_phi.get_cost_vs_budget_trend(
        scope,
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
        division_id=division_id,
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_division_list(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache danh sách Khối có dữ liệu trong phạm vi RBAC — khoá cache gắn
    `user_id`/`role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_chi_phi.get_division_list(scope)


# ---------------------------------------------------------------------------
# Cache — Theo Nhóm nhân sự (CHỈ Admin — xem docstring đầu file)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60, show_spinner=False)
def _cached_personnel_cost_by_staff_group(
    user_id: int, role_value: str, date_from: date | None, date_to: date | None
) -> pd.DataFrame:
    """Cache chi phí theo Nhóm nhân sự — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6). Chỉ được gọi khi `scope.unrestricted`
    (kiểm tra ở nơi gọi) — vẫn bọc try/except PermissionError làm phòng vệ
    thứ 2."""
    scope = _cached_data_scope(user_id, role_value)
    return report_chi_phi.get_personnel_cost_by_staff_group(
        scope, date_from=date_from, date_to=date_to
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_personnel_cost_trend(
    user_id: int,
    role_value: str,
    granularity: str,
    date_from: date | None,
    date_to: date | None,
    staff_group: str | None,
) -> pd.DataFrame:
    """Cache xu hướng chi phí theo Nhóm nhân sự — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6). Chỉ Admin (xem docstring hàm phía trên)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_chi_phi.get_personnel_cost_trend(
        scope,
        granularity=granularity,
        date_from=date_from,
        date_to=date_to,
        staff_group=staff_group,
    )


def _render_date_filters(*, key_prefix: str) -> tuple:
    """Vẽ 2 ô lọc khoảng ngày theo `period`, tuỳ chọn — mặc định không giới
    hạn (None, None) để không ẩn dữ liệu ngoài ý muốn khi mới vào trang."""
    use_filter = st.checkbox(
        "Lọc theo khoảng kỳ (period)", value=False, key=f"{key_prefix}_use_filter"
    )
    if not use_filter:
        return None, None
    col_from, col_to = st.columns(2)
    with col_from:
        date_from = st.date_input("Từ kỳ", value=None, key=f"{key_prefix}_from")
    with col_to:
        date_to = st.date_input("Đến kỳ", value=None, key=f"{key_prefix}_to")
    return date_from or None, date_to or None


def _render_variance_metrics(df: pd.DataFrame) -> None:
    total_cost = float(df["cost_amount"].sum())
    total_budget = float(df["budget_amount"].sum())
    total_variance = total_cost - total_budget
    variance_pct = (total_variance / total_budget) if total_budget else 0.0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng chi thực tế", f"{total_cost:,.0f}")
    col2.metric("Tổng ngân sách", f"{total_budget:,.0f}")
    col3.metric("Chênh lệch", f"{total_variance:,.0f}")
    col4.metric("Chênh lệch %", f"{variance_pct:.1%}" if total_budget else "N/A")


def _render_cost_by_division(user_id: int, role_value: str, date_from, date_to) -> None:
    df = _cached_cost_vs_budget_by_division(user_id, role_value, date_from, date_to)
    if df.empty:
        st.warning(
            "Không có dữ liệu chi phí/ngân sách theo Khối trong phạm vi được phép xem."
        )
        return

    _render_variance_metrics(df)

    fig = px.bar(
        df,
        x="division_name",
        y=["cost_amount", "budget_amount"],
        barmode="group",
        title="Chi thực tế vs Ngân sách theo Khối",
        labels={
            "division_name": "Khối",
            "value": "Số tiền",
            "variable": "Chỉ tiêu",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

    fig_pct = px.bar(
        df,
        x="division_name",
        y="variance_pct",
        title="Chênh lệch % (chi thực tế / ngân sách - 1) theo Khối",
        labels={"division_name": "Khối", "variance_pct": "Chênh lệch %"},
    )
    fig_pct.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig_pct, use_container_width=True)

    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_cost_trend(user_id: int, role_value: str, date_from, date_to) -> None:
    """Xu hướng chi vs ngân sách theo Tháng/Tuần — `px.line` (xu hướng theo
    thời gian, theo quy ước biểu đồ dự án), có thể lọc riêng 1 Khối."""
    granularity_label = st.radio(
        "Gộp theo", ["Tháng", "Tuần"], horizontal=True, key="cp_cost_trend_gran"
    )
    granularity = "month" if granularity_label == "Tháng" else "week"

    division_df = _cached_division_list(user_id, role_value)
    division_options = {"Tất cả Khối": None}
    if not division_df.empty:
        division_options.update(
            dict(zip(division_df["division_name"], division_df["division_id"]))
        )
    division_label = st.selectbox(
        "Khối", list(division_options.keys()), key="cp_cost_trend_division"
    )
    division_id = division_options[division_label]

    df = _cached_cost_vs_budget_trend(
        user_id, role_value, granularity, date_from, date_to, division_id
    )
    if df.empty:
        st.warning(
            "Không có dữ liệu xu hướng chi phí/ngân sách trong phạm vi được phép xem."
        )
        return

    _render_variance_metrics(df)

    df_long = df.melt(
        id_vars=["period"],
        value_vars=["cost_amount", "budget_amount"],
        var_name="chi_tieu",
        value_name="so_tien",
    )
    fig = px.line(
        df_long,
        x="period",
        y="so_tien",
        color="chi_tieu",
        markers=True,
        title=f"Xu hướng chi thực tế vs ngân sách theo {granularity_label.lower()}"
        + (f" — {division_label}" if division_id is not None else ""),
        labels={
            "period": granularity_label,
            "so_tien": "Số tiền",
            "chi_tieu": "Chỉ tiêu",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_theo_khoi_tab(scope: DataScope, user_id: int, role_value: str) -> None:
    """Nội dung tab "Theo Khối" — CHẶN HẲN với role User (COO xác nhận
    09/09/2026): `cost`/`budget` không có dữ liệu cấp nhân viên. Kiểm tra
    `scope.role` TRƯỚC khi gọi service (không chỉ dựa vào DataFrame rỗng)."""
    if scope.role == UserRole.USER:
        st.info(
            "Không có dữ liệu ở cấp nhân viên cho báo cáo 'Theo Khối' — "
            "bảng chi phí/ngân sách (`cost`/`budget`) chỉ lưu số liệu theo "
            "Khối, không có dữ liệu cấp nhân viên. Vui lòng liên hệ Quản lý "
            "Khối/Trưởng phòng để xem báo cáo này."
        )
        return

    date_from, date_to = _render_date_filters(key_prefix="cp_khoi_date")
    sub_division, sub_trend = st.tabs(["Theo Khối", "Xu hướng"])
    with sub_division:
        _render_cost_by_division(user_id, role_value, date_from, date_to)
    with sub_trend:
        _render_cost_trend(user_id, role_value, date_from, date_to)


def _render_personnel_by_group(
    user_id: int, role_value: str, date_from, date_to
) -> None:
    try:
        df = _cached_personnel_cost_by_staff_group(
            user_id, role_value, date_from, date_to
        )
    except PermissionError as exc:
        # Phòng vệ thứ 2 — tab này lẽ ra đã bị ẩn hẳn ở `main()` nếu không
        # phải Admin, xem docstring đầu file. Không để lộ traceback.
        st.error(f"Không có quyền xem báo cáo này: {exc}")
        logger.error("Tab 'Theo Nhóm nhân sự' bị chặn quyền ngoài dự kiến: {}", exc)
        return

    if df.empty:
        st.warning("Không có dữ liệu chi phí theo Nhóm nhân sự trong khoảng lọc.")
        return

    total_cost = float(df["cost_amount"].sum())
    col1, col2 = st.columns(2)
    col1.metric("Tổng chi phí nhân sự", f"{total_cost:,.0f}")
    col2.metric("Số nhóm có dữ liệu", len(df))

    fig = px.bar(
        df,
        x="staff_group",
        y="cost_amount",
        title="Chi phí theo Nhóm nhân sự (LĐ/QL/Frontline/Middle/Backend)",
        labels={"staff_group": "Nhóm nhân sự", "cost_amount": "Chi phí"},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_personnel_trend(user_id: int, role_value: str, date_from, date_to) -> None:
    granularity_label = st.radio(
        "Gộp theo", ["Tháng", "Tuần"], horizontal=True, key="cp_personnel_trend_gran"
    )
    granularity = "month" if granularity_label == "Tháng" else "week"

    group_options = ["Tất cả nhóm"] + report_chi_phi.get_staff_group_list()
    group_label = st.selectbox(
        "Nhóm nhân sự", group_options, key="cp_personnel_trend_group"
    )
    staff_group = None if group_label == "Tất cả nhóm" else group_label

    try:
        df = _cached_personnel_cost_trend(
            user_id, role_value, granularity, date_from, date_to, staff_group
        )
    except PermissionError as exc:
        st.error(f"Không có quyền xem báo cáo này: {exc}")
        logger.error("Tab 'Theo Nhóm nhân sự' bị chặn quyền ngoài dự kiến: {}", exc)
        return

    if df.empty:
        st.warning(
            "Không có dữ liệu xu hướng chi phí theo Nhóm nhân sự trong khoảng lọc."
        )
        return

    total_cost = float(df["cost_amount"].sum())
    col1, col2 = st.columns(2)
    col1.metric("Tổng chi phí (cả kỳ)", f"{total_cost:,.0f}")
    col2.metric("Số dòng", len(df))

    fig = px.line(
        df,
        x="period",
        y="cost_amount",
        color="staff_group",
        markers=True,
        title=f"Xu hướng chi phí theo Nhóm nhân sự — {granularity_label.lower()}",
        labels={
            "period": granularity_label,
            "cost_amount": "Chi phí",
            "staff_group": "Nhóm nhân sự",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_theo_nhom_nhan_su_tab(user_id: int, role_value: str) -> None:
    """Nội dung tab "Theo Nhóm nhân sự" — chỉ được `main()` gọi khi
    `scope.unrestricted` là `True` (Admin). Vẫn bọc PermissionError ở các
    hàm con làm phòng vệ thứ 2 (xem docstring đầu file)."""
    date_from, date_to = _render_date_filters(key_prefix="cp_nhom_date")
    sub_group, sub_trend = st.tabs(["Theo Nhóm", "Xu hướng"])
    with sub_group:
        _render_personnel_by_group(user_id, role_value, date_from, date_to)
    with sub_trend:
        _render_personnel_trend(user_id, role_value, date_from, date_to)


def main() -> None:
    """Entry point trang Báo cáo Chi phí — kiểm tra đăng nhập trước (đúng
    key `st.session_state["lacco_auth_session"]` dùng ở `main.py`), rồi
    hiển thị 2 tab: Theo Khối (ẩn nội dung cho User) / Theo Nhóm nhân sự
    (ẨN HẲN tab cho Manager/User — CHỈ Admin, xem docstring đầu file)."""
    st.title("Báo cáo Chi phí")

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

    # "Theo Nhóm nhân sự" ẨN HẲN tab nếu không phải Admin (COO xác nhận
    # 09/09/2026) — quyết định hiển thị tab dựa trên `scope.unrestricted`,
    # KHÔNG dựa vào việc bắt PermissionError (đó chỉ là phòng vệ thứ 2).
    if scope.unrestricted:
        tab_khoi, tab_nhom = st.tabs(["Theo Khối", "Theo Nhóm nhân sự"])
        with tab_khoi:
            _render_theo_khoi_tab(scope, user_id, role_value)
        with tab_nhom:
            _render_theo_nhom_nhan_su_tab(user_id, role_value)
    else:
        st.caption(
            "Báo cáo 'Theo Nhóm nhân sự' chỉ dành cho Admin — bảng chi phí "
            "nhân sự (`personnel_cost`) không có dữ liệu cấp Khối/Phòng/NV "
            "để lọc theo phân quyền (quyết định COO 09/09/2026)."
        )
        (tab_khoi,) = st.tabs(["Theo Khối"])
        with tab_khoi:
            _render_theo_khoi_tab(scope, user_id, role_value)


if __name__ == "__main__":
    main()
