"""Trang Streamlit — Báo cáo Công nợ: Khối → Phòng → Kinh doanh, phân theo
4 mức tuổi nợ quá hạn (aging) + 1 nhóm phụ "Chưa đến hạn" (2 tab), cộng
thêm mục kiểm tra chất lượng dữ liệu (lệch `division_id`/`department_id`)
cho Admin.

Theo CLAUDE.md mục 2 (tách lớp): trang này CHỈ gọi hàm từ
`src.services.report_cong_no` rồi vẽ Plotly — KHÔNG viết SQL hay logic tính
KPI tại chỗ. Ngoại lệ duy nhất giống `1_Bao_cao_Kinh_doanh.py`: ở tab
"Theo Khối-Phòng-NV", trang tự `groupby(...).sum()` lại DataFrame mức chi
tiết nhất (đã tính sẵn `debt_count`/`amount` ở service) để đổi mức xem
Khối/Phòng/NV mà không gọi lại DB — cộng dồn số đã tính đúng, không phải
công thức nghiệp vụ mới.

*** ĐÃ XÁC NHẬN: aging tính ĐỘNG (COO, 09/09/2026) *** — trang này KHÔNG
cho phép người dùng chọn `as_of_date` tuỳ ý ở UI (mặc định `date.today()`
qua service) để đúng tinh thần "tính động tại thời điểm truy vấn", không
phải xem lại 1 mốc quá khứ tuỳ chọn.

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
from src.db.models.enums import UserRole
from src.services import export_utils, report_cong_no
from src.services.db_connection import get_engine

st.set_page_config(page_title="LACCO Dashboard — Báo cáo Công nợ", layout="wide")

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
def _cached_aging_summary(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache tổng hợp công nợ theo nhóm tuổi nợ — khoá cache gắn `user_id`/
    `role_value` (CLAUDE.md mục 6). Cố tình KHÔNG nhận `as_of_date` làm
    tham số UI (aging luôn tính theo `date.today()` tại thời điểm gọi —
    COO xác nhận 09/09/2026 tính ĐỘNG), TTL 60s đủ ngắn để không lệch quá
    nhiều so với ngày thật."""
    scope = _cached_data_scope(user_id, role_value)
    return report_cong_no.get_debt_aging_summary(scope)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_aging_by_org(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache công nợ theo Khối-Phòng-NV x aging_bucket (mức chi tiết nhất)
    — khoá cache gắn `user_id`/`role_value` (CLAUDE.md mục 6)."""
    scope = _cached_data_scope(user_id, role_value)
    return report_cong_no.get_debt_aging_by_org(scope)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_mismatch_check(user_id: int, role_value: str) -> pd.DataFrame:
    """Cache kết quả kiểm tra lệch `division_id`/`department_id` — kiểm tra
    CHẤT LƯỢNG DỮ LIỆU toàn hệ thống, không phụ thuộc phạm vi RBAC của
    user, nhưng vẫn gắn `user_id`/`role_value` vào khoá cache (CLAUDE.md
    mục 6, áp dụng nhất quán cho MỌI `@st.cache_data` trong trang, kể cả
    hàm không lọc theo scope) để tránh lẫn cache giữa các phiên. TTL 300s
    (5 phút) vì đây là kiểm tra cấu trúc dữ liệu, ít thay đổi hơn số liệu
    công nợ."""
    del user_id, role_value  # chỉ dùng để tạo khoá cache theo user, không lọc dữ liệu
    return report_cong_no.check_division_department_mismatch()


def _render_export_buttons(
    df: pd.DataFrame, fig: Any, *, key_prefix: str, file_stub: str, title: str
) -> None:
    """2 nút xuất Excel/PDF cho 1 báo cáo con (VIỆC 3, bước 6.1) — dùng
    đúng `df`/`fig` đã tính sẵn ở hàm `_render_*` gọi hàm này, KHÔNG truy
    vấn DB mới. Không bọc `@st.cache_data` (CLAUDE.md mục 6). Nút PDF tách
    2 bước (bấm tạo rồi mới hiện nút tải) — Streamlit đánh giá lại `data=`
    mỗi lần rerun trang, gọi trực tiếp sẽ tốn kaleido render lại ở MỌI lần
    rerun (đã kiểm chứng thật, xem báo cáo bước 6.1). Không có bộ lọc ngày
    trên trang này (aging tính động theo `date.today()`, xem docstring đầu
    file) nên `subtitle` chỉ ghi rõ mốc ngày tính aging."""
    col_excel, col_pdf = st.columns(2)
    today_str = date.today().isoformat()
    subtitle = f"Aging tính động theo ngày {date.today():%d/%m/%Y}"

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


def _render_overview(user_id: int, role_value: str) -> None:
    df = _cached_aging_summary(user_id, role_value)
    if df.empty:
        st.warning("Không có dữ liệu công nợ trong phạm vi được phép xem.")
        return

    total_amount = df["amount"].sum()
    total_count = int(df["debt_count"].sum())
    overdue_amount = df.loc[
        df["aging_bucket"] != report_cong_no.BUCKET_NOT_DUE, "amount"
    ].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng dư nợ", f"{total_amount:,.0f}")
    col2.metric("Trong đó đã quá hạn", f"{overdue_amount:,.0f}")
    col3.metric("Số khoản nợ", total_count)
    st.caption(
        f'Nhóm "{report_cong_no.BUCKET_NOT_DUE}" (chưa đến hạn) hiển thị '
        "riêng, không tính vào 4 mức quá hạn đã chốt với COO."
    )

    fig = px.bar(
        df,
        x="aging_bucket",
        y="amount",
        text="debt_count",
        title="Dư nợ theo nhóm tuổi nợ (aging bucket)",
        labels={"aging_bucket": "Nhóm tuổi nợ", "amount": "Dư nợ"},
        category_orders={"aging_bucket": list(report_cong_no.BUCKET_ORDER)},
    )
    fig.update_traces(texttemplate="%{text} khoản", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    _render_export_buttons(
        df,
        fig,
        key_prefix="cn_overview",
        file_stub="cong_no_tong_quan_aging",
        title="Dư nợ theo nhóm tuổi nợ (aging bucket)",
    )


def _render_by_org(user_id: int, role_value: str) -> None:
    level = st.radio(
        "Mức xem", ["Khối", "Phòng", "Nhân viên"], horizontal=True, key="cn_org_level"
    )
    df = _cached_aging_by_org(user_id, role_value)
    if df.empty:
        st.warning(
            "Không có dữ liệu công nợ theo Khối-Phòng-NV trong phạm vi được phép xem."
        )
        return

    if level == "Khối":
        group_cols, x_col = ["division_name"], "division_name"
    elif level == "Phòng":
        group_cols, x_col = ["division_name", "department_name"], "department_name"
    else:
        group_cols = ["division_name", "department_name", "employee_name"]
        x_col = "employee_name"

    agg = df.groupby(group_cols + ["aging_bucket"], as_index=False)[
        ["debt_count", "amount"]
    ].sum()

    total_amount = agg["amount"].sum()
    total_count = int(agg["debt_count"].sum())
    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng dư nợ", f"{total_amount:,.0f}")
    col2.metric("Số khoản nợ", total_count)
    col3.metric(f"Số dòng ({level})", agg[group_cols[-1]].nunique())

    fig = px.bar(
        agg,
        x=x_col,
        y="amount",
        color="aging_bucket",
        barmode="stack",
        title=f"Dư nợ theo {level}, phân theo nhóm tuổi nợ",
        labels={x_col: level, "amount": "Dư nợ", "aging_bucket": "Nhóm tuổi nợ"},
        category_orders={"aging_bucket": list(report_cong_no.BUCKET_ORDER)},
    )
    st.plotly_chart(fig, use_container_width=True)

    totals_by_group = (
        agg.groupby(group_cols, as_index=False)[["debt_count", "amount"]]
        .sum()
        .sort_values("amount", ascending=False)
        .reset_index(drop=True)
    )
    st.dataframe(totals_by_group, use_container_width=True, hide_index=True)
    with st.expander("Xem chi tiết theo nhóm tuổi nợ"):
        st.dataframe(agg, use_container_width=True, hide_index=True)

    # Xuất `agg` (có cột aging_bucket) chứ không phải `totals_by_group` —
    # đây là dữ liệu khớp với chart (stacked bar phân theo aging_bucket).
    _render_export_buttons(
        agg,
        fig,
        key_prefix="cn_org",
        file_stub="cong_no_theo_khoi_phong_nv",
        title=f"Dư nợ theo {level}, phân theo nhóm tuổi nợ",
    )


def _render_data_quality_check() -> None:
    """Chỉ hiển thị cho Admin — kiểm tra lệch `division_id`/`department_id`
    trong bảng `debt` (mục #5, `erd-tuan-02.md`, giao việc bước 5.x)."""
    session = st.session_state[_SESSION_KEY]
    user_id, role_value = session["user_id"], session["role"]
    mismatch_df = _cached_mismatch_check(user_id, role_value)
    if mismatch_df.empty:
        st.success(
            "Không phát hiện dòng `debt` nào có `department.division_id` "
            "khác `debt.division_id`."
        )
        return
    st.error(
        f"Phát hiện {len(mismatch_df)} dòng `debt` có `department.division_id` "
        "khác `debt.division_id` — CẦN COO xác nhận cách xử lý (mục #5, "
        "`erd-tuan-02.md`), báo cáo KHÔNG tự chọn cột nào để sửa."
    )
    st.dataframe(mismatch_df, use_container_width=True, hide_index=True)


def main() -> None:
    """Entry point trang Báo cáo Công nợ — kiểm tra đăng nhập trước (đúng
    key `st.session_state["lacco_auth_session"]` dùng ở `main.py`), rồi
    hiển thị 2 tab (Tổng quan theo aging / Theo Khối-Phòng-NV) cộng thêm 1
    mục kiểm tra chất lượng dữ liệu riêng cho Admin."""
    st.title("Báo cáo Công nợ — Khối → Phòng → Kinh doanh")

    session = st.session_state.get(_SESSION_KEY)
    if session is None:
        st.warning("Vui lòng đăng nhập ở trang chính (Home) trước khi xem báo cáo.")
        st.stop()

    user_id = session["user_id"]
    role_value = session["role"]
    st.caption(
        f"Đang xem với vai trò **{role_value}** — tài khoản **{session['username']}**. "
        f"Aging tính động theo ngày hôm nay ({date.today():%d/%m/%Y})."
    )

    scope = _cached_data_scope(user_id, role_value)
    if (
        not scope.unrestricted
        and scope.department_id is None
        and scope.employee_id is None
    ):
        st.warning(
            "Tài khoản này chưa xác định được phạm vi Khối/Phòng/NV nào để "
            "hiển thị báo cáo công nợ (xem `scope.description` để biết lý do)."
        )
        logger.warning(
            "Trang Báo cáo Công nợ: user_id={} scope rỗng, description={}",
            user_id,
            scope.description,
        )
        st.stop()

    tab_overview, tab_org = st.tabs(["Tổng quan theo aging", "Theo Khối-Phòng-NV"])
    with tab_overview:
        _render_overview(user_id, role_value)
    with tab_org:
        _render_by_org(user_id, role_value)

    if scope.role == UserRole.ADMIN:
        st.divider()
        st.subheader("Kiểm tra chất lượng dữ liệu (chỉ Admin)")
        _render_data_quality_check()


if __name__ == "__main__":
    main()
