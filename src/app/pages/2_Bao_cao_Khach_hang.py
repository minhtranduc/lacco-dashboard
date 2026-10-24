"""Trang Streamlit — Báo cáo Khách hàng (5 tab): Tăng giảm loại KH (A/B/C)
theo thời gian, Phân bố khách hàng theo nguồn, Theo nhân viên, Theo phòng
ban, Danh sách khách hàng.

Theo CLAUDE.md mục 2 (tách lớp): trang này CHỈ gọi hàm từ
`src/services/report_khach_hang.py` (logic KPI) và `src/auth/scope.py`
(RBAC) rồi vẽ Plotly — KHÔNG tự viết SQL hay logic tính toán tại chỗ.

Theo CLAUDE.md mục 6 (rủi ro bảo mật nghiêm trọng nhất dự án): mọi
`@st.cache_data` PHẢI nhận tham số gắn `user_id`/`role_value` — theo đúng
mẫu `_cached_data_scope()` đã có ở `src/app/main.py` (lặp lại y hệt pattern
đó ở đây, không tự đặt quy ước cache mới). Cấm biến global chứa dữ liệu báo
cáo — mọi dữ liệu phiên nằm trong `st.session_state` hoặc trả về từ hàm
cache theo user.

Trang yêu cầu đăng nhập trước khi hiển thị — tái sử dụng đúng session key
`_SESSION_KEY = "lacco_auth_session"` đã dùng ở `src/app/main.py` (session
chứa `{"user_id", "username", "role"}`), không tự đặt quy ước session mới.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from loguru import logger

from src.auth.scope import DataScope, compute_data_scope
from src.services import export_utils
from src.services.db_connection import get_engine
from src.services.report_khach_hang import (
    get_classification_trend,
    get_customer_count_by_department,
    get_customer_count_by_employee,
    get_customer_list,
    get_source_distribution,
)

st.set_page_config(page_title="LACCO Dashboard — Báo cáo Khách hàng", layout="wide")

# Trùng khoá session dùng ở src/app/main.py — KHÔNG tự đặt quy ước mới.
_SESSION_KEY = "lacco_auth_session"

_CLASSIFICATION_ORDER = ["A", "B", "C"]

# Cảnh báo bắt buộc theo quyết định COO 24/10/2026 (xem docstring module
# `src/services/report_khach_hang.py`) — hiển thị ngay dưới tiêu đề tab
# "Theo nhân viên"/"Theo phòng ban".
_DOUBLE_COUNT_WARNING = (
    "Lưu ý: 1 khách hàng có thể từng giao dịch với nhiều nhân viên/phòng, "
    "nên được đếm ở nhiều dòng — tổng cộng có thể lớn hơn tổng số khách "
    "hàng thực tế."
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_data_scope(user_id: int, role_value: str) -> DataScope:
    """Cache phạm vi dữ liệu, TTL 60s — BẮT BUỘC nhận `user_id` VÀ
    `role_value` làm tham số (CLAUDE.md mục 6), y hệt mẫu ở
    `src/app/main.py::_cached_data_scope`. Streamlit dùng các tham số này
    làm khoá cache, đảm bảo dữ liệu phạm vi của user A không lộ sang user B.
    """
    return compute_data_scope(user_id, engine=get_engine())


@st.cache_data(ttl=60, show_spinner="Đang tải dữ liệu phân loại khách hàng...")
def _cached_classification_trend(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache dữ liệu xu hướng A/B/C — khoá cache theo `user_id`+`role_value`
    (CLAUDE.md mục 6). Tự lấy lại `scope` (đã cache riêng ở
    `_cached_data_scope`) rồi gọi service, không nhận `DataScope` làm tham
    số cache trực tiếp để tránh phụ thuộc vào cách Streamlit hash 1 object
    tuỳ biến."""
    scope = _cached_data_scope(user_id, role_value)
    return get_classification_trend(scope, engine=get_engine())


@st.cache_data(ttl=60, show_spinner="Đang tải dữ liệu nguồn khách hàng...")
def _cached_source_distribution(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache dữ liệu phân bố theo nguồn — khoá cache theo
    `user_id`+`role_value` (CLAUDE.md mục 6), cùng cơ chế như
    `_cached_classification_trend`."""
    scope = _cached_data_scope(user_id, role_value)
    return get_source_distribution(scope, engine=get_engine())


@st.cache_data(ttl=60, show_spinner="Đang tải số khách hàng theo nhân viên...")
def _cached_count_by_employee(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache số KH theo nhân viên — khoá cache theo `user_id`+`role_value`
    (CLAUDE.md mục 6), cùng cơ chế như `_cached_classification_trend`."""
    scope = _cached_data_scope(user_id, role_value)
    return get_customer_count_by_employee(scope, engine=get_engine())


@st.cache_data(ttl=60, show_spinner="Đang tải số khách hàng theo phòng ban...")
def _cached_count_by_department(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache số KH theo phòng ban — khoá cache theo `user_id`+`role_value`
    (CLAUDE.md mục 6), cùng cơ chế như `_cached_classification_trend`."""
    scope = _cached_data_scope(user_id, role_value)
    return get_customer_count_by_department(scope, engine=get_engine())


@st.cache_data(ttl=60, show_spinner="Đang tải danh sách khách hàng...")
def _cached_customer_list(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache danh sách KH — khoá cache theo `user_id`+`role_value`
    (CLAUDE.md mục 6). Ô tìm kiếm lọc client-side trên DataFrame trả về từ
    đây, không query lại DB mỗi lần gõ."""
    scope = _cached_data_scope(user_id, role_value)
    return get_customer_list(scope, engine=get_engine())


def _render_login_required() -> None:
    st.warning("Vui lòng đăng nhập ở trang chính (Home) trước khi xem báo cáo này.")


def _render_export_buttons(
    df: pd.DataFrame, fig: Any, *, key_prefix: str, file_stub: str, title: str
) -> None:
    """2 nút xuất Excel/PDF cho 1 báo cáo con (VIỆC 3, bước 6.1) — dùng
    đúng `df`/`fig` đã tính sẵn ở hàm `_render_*` gọi hàm này, KHÔNG truy
    vấn DB mới. Không bọc `@st.cache_data` (không truy vấn DB, không cần
    thiết — CLAUDE.md mục 6). Nút PDF tách 2 bước (bấm tạo rồi mới hiện nút
    tải) thay vì gọi `build_pdf_report_bytes` trực tiếp trong `data=` —
    Streamlit đánh giá lại `data=` mỗi lần rerun trang, gọi trực tiếp sẽ tốn
    kaleido render chart lại ở MỌI lần rerun (đã kiểm chứng thật, xem báo
    cáo bước 6.1)."""
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
                pdf_bytes = export_utils.build_pdf_report_bytes(df, fig, title=title)
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


def _render_classification_trend(df: pd.DataFrame) -> None:
    """Vẽ line chart xu hướng số lượng KH theo loại A/B/C qua các mốc
    `snapshot_date` thực tế — chỉ nhận DataFrame đã tính sẵn từ service,
    không tự tính toán ở đây (CLAUDE.md mục 2)."""
    st.subheader("Tăng giảm loại khách hàng A/B/C theo thời gian")

    if df.empty:
        st.info("Không có dữ liệu phân loại khách hàng trong phạm vi được phép xem.")
        return

    # Pivot sang wide để đảm bảo đủ 3 cột A/B/C (fill 0 nếu mốc nào đó
    # thiếu 1 loại) trước khi melt lại về long format cho px.line — không
    # phải logic tính KPI (chỉ là biến đổi hình dạng dữ liệu để vẽ), vẫn
    # đúng ranh giới tách lớp CLAUDE.md mục 2.
    pivot = df.pivot_table(
        index="snapshot_date",
        columns="classification",
        values="so_luong_kh",
        fill_value=0,
        aggfunc="sum",
    )
    for col in _CLASSIFICATION_ORDER:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot[_CLASSIFICATION_ORDER].reset_index()

    long_df = pivot.melt(
        id_vars="snapshot_date",
        value_vars=_CLASSIFICATION_ORDER,
        var_name="classification",
        value_name="so_luong_kh",
    )

    fig = px.line(
        long_df,
        x="snapshot_date",
        y="so_luong_kh",
        color="classification",
        markers=True,
        category_orders={"classification": _CLASSIFICATION_ORDER},
        labels={
            "snapshot_date": "Mốc snapshot",
            "so_luong_kh": "Số lượng khách hàng",
            "classification": "Loại KH",
        },
        title="Số lượng khách hàng theo loại A/B/C qua các mốc snapshot",
    )
    st.plotly_chart(fig, use_container_width=True)

    display_df = pivot.rename(columns={"snapshot_date": "Mốc snapshot"})
    with st.expander("Xem dữ liệu chi tiết"):
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        display_df,
        fig,
        key_prefix="kh_classification",
        file_stub="khach_hang_phan_loai_abc",
        title="Tăng giảm loại khách hàng A/B/C theo thời gian",
    )


def _render_source_distribution(df: pd.DataFrame) -> None:
    """Vẽ bar chart phân bố số lượng KH theo nguồn — chỉ nhận DataFrame đã
    tính sẵn từ service (CLAUDE.md mục 2)."""
    st.subheader("Phân bố khách hàng theo nguồn")

    if df.empty:
        st.info("Không có dữ liệu nguồn khách hàng trong phạm vi được phép xem.")
        return

    df_sorted = df.sort_values("so_luong_kh", ascending=True)
    fig = px.bar(
        df_sorted,
        x="so_luong_kh",
        y="source",
        orientation="h",
        text="so_luong_kh",
        labels={"so_luong_kh": "Số lượng khách hàng", "source": "Nguồn"},
        title="Số lượng khách hàng theo nguồn",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    display_df = df_sorted.sort_values("so_luong_kh", ascending=False).rename(
        columns={"source": "Nguồn", "so_luong_kh": "Số lượng khách hàng"}
    )
    with st.expander("Xem dữ liệu chi tiết"):
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        display_df,
        fig,
        key_prefix="kh_source",
        file_stub="khach_hang_theo_nguon",
        title="Phân bố khách hàng theo nguồn",
    )


def _render_count_by_employee(df: pd.DataFrame) -> None:
    """Vẽ bar chart số KH theo nhân viên + cảnh báo đếm trùng (quyết định
    COO 24/10/2026) — chỉ nhận DataFrame đã tính sẵn từ service."""
    st.subheader("Số lượng khách hàng theo nhân viên")
    st.warning(_DOUBLE_COUNT_WARNING)

    if df.empty:
        st.info(
            "Không có dữ liệu khách hàng theo nhân viên trong phạm vi được phép xem."
        )
        return

    df_sorted = df.sort_values("so_luong_kh", ascending=True)
    fig = px.bar(
        df_sorted,
        x="so_luong_kh",
        y="employee_name",
        orientation="h",
        text="so_luong_kh",
        hover_data=["department_name"],
        labels={
            "so_luong_kh": "Số lượng khách hàng",
            "employee_name": "Nhân viên",
            "department_name": "Phòng",
        },
        title="Số lượng khách hàng theo nhân viên",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    display_df = df[["employee_name", "department_name", "so_luong_kh"]].rename(
        columns={
            "employee_name": "Nhân viên",
            "department_name": "Phòng",
            "so_luong_kh": "Số lượng khách hàng",
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        display_df,
        fig,
        key_prefix="kh_by_employee",
        file_stub="khach_hang_theo_nhan_vien",
        title="Số lượng khách hàng theo nhân viên",
    )


def _render_count_by_department(df: pd.DataFrame) -> None:
    """Vẽ bar chart số KH theo phòng ban + cảnh báo đếm trùng (quyết định
    COO 24/10/2026) — chỉ nhận DataFrame đã tính sẵn từ service."""
    st.subheader("Số lượng khách hàng theo phòng ban")
    st.warning(_DOUBLE_COUNT_WARNING)

    if df.empty:
        st.info(
            "Không có dữ liệu khách hàng theo phòng ban trong phạm vi được phép xem."
        )
        return

    df_sorted = df.sort_values("so_luong_kh", ascending=True)
    fig = px.bar(
        df_sorted,
        x="so_luong_kh",
        y="department_name",
        orientation="h",
        text="so_luong_kh",
        hover_data=["division_name"],
        labels={
            "so_luong_kh": "Số lượng khách hàng",
            "department_name": "Phòng",
            "division_name": "Khối",
        },
        title="Số lượng khách hàng theo phòng ban",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    display_df = df[["department_name", "division_name", "so_luong_kh"]].rename(
        columns={
            "department_name": "Phòng",
            "division_name": "Khối",
            "so_luong_kh": "Số lượng khách hàng",
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        display_df,
        fig,
        key_prefix="kh_by_department",
        file_stub="khach_hang_theo_phong_ban",
        title="Số lượng khách hàng theo phòng ban",
    )


def _render_customer_list(df: pd.DataFrame) -> None:
    """Bảng danh sách KH + ô tìm kiếm theo tên/mã (lọc client-side trên
    DataFrame đã tải, không query lại DB) + nút xuất Excel (không có PDF vì
    không có chart)."""
    st.subheader("Danh sách khách hàng")

    if df.empty:
        st.info("Không có khách hàng nào trong phạm vi được phép xem.")
        return

    keyword = st.text_input("Tìm theo tên hoặc mã khách hàng", key="kh_list_search")
    keyword = keyword.strip()
    filtered = df
    if keyword:
        mask = df["name"].str.contains(keyword, case=False, regex=False) | df[
            "code"
        ].str.contains(keyword, case=False, regex=False)
        filtered = df[mask]

    st.caption(f"Hiển thị {len(filtered):,} / {len(df):,} khách hàng.")
    display_df = filtered.drop(columns=["id"]).rename(
        columns={
            "code": "Mã KH",
            "name": "Tên khách hàng",
            "source": "Nguồn",
            "current_classification": "Loại KH hiện tại",
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.download_button(
        "⬇️ Xuất Excel",
        data=export_utils.dataframe_to_excel_bytes(
            display_df, sheet_name="kh_list", title="Danh sách khách hàng"
        ),
        file_name=f"khach_hang_danh_sach_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="kh_list_export_xlsx",
    )


def main() -> None:
    """Entry point trang Streamlit — kiểm tra đăng nhập qua
    `st.session_state[_SESSION_KEY]` trước, sau đó tải + vẽ 5 tab báo cáo
    con của nhóm Khách hàng."""
    st.title("Báo cáo Khách hàng")
    st.caption(
        "Tăng giảm loại khách hàng A/B/C, phân bố theo nguồn, theo nhân "
        "viên/phòng ban và danh sách khách hàng. Dữ liệu đã lọc theo phạm "
        "vi RBAC của tài khoản đang đăng nhập."
    )

    session = st.session_state.get(_SESSION_KEY)
    if session is None:
        _render_login_required()
        return

    user_id = session["user_id"]
    role_value = session["role"]

    scope = _cached_data_scope(user_id, role_value)
    st.caption(f"**Phạm vi dữ liệu:** {scope.description}")
    if not scope.unrestricted and not scope.customer_ids:
        st.warning(
            "Phạm vi khách hàng của tài khoản này đang rỗng — không có dữ "
            "liệu để hiển thị. Xem ghi chú RBAC trong "
            "`src/auth/scope.py`/`src/services/auth_service.py`."
        )

    logger.info(
        "Bao_cao_Khach_hang: user_id={} role={} unrestricted={} -> tải báo cáo.",
        user_id,
        role_value,
        scope.unrestricted,
    )

    tab_trend, tab_source, tab_employee, tab_department, tab_list = st.tabs(
        [
            "Tăng giảm A/B/C",
            "Theo nguồn",
            "Theo nhân viên",
            "Theo phòng ban",
            "Danh sách khách hàng",
        ]
    )
    with tab_trend:
        _render_classification_trend(_cached_classification_trend(user_id, role_value))
    with tab_source:
        _render_source_distribution(_cached_source_distribution(user_id, role_value))
    with tab_employee:
        _render_count_by_employee(_cached_count_by_employee(user_id, role_value))
    with tab_department:
        _render_count_by_department(_cached_count_by_department(user_id, role_value))
    with tab_list:
        _render_customer_list(_cached_customer_list(user_id, role_value))


if __name__ == "__main__":
    main()
