"""Service tính KPI báo cáo Công nợ — Khối → Phòng → Kinh doanh, phân theo
4 mức tuổi nợ quá hạn (aging).

Nguồn yêu cầu: `.claude/rules/trang-thai-yeu-cau.md`, dòng "Công nợ | Khối →
Phòng → Kinh doanh" — đã "Đã rõ": ngưỡng quá hạn 4 mức 0-30/31-60/61-90/
trên 90 ngày, nguồn AMIS.

Theo CLAUDE.md mục 2 (tách lớp): module này chỉ chứa truy vấn SQLAlchemy
(parameterized, cấm nối chuỗi SQL thủ công) + tính toán KPI, KHÔNG chứa code
Streamlit/Plotly. Trang `src/app/pages/6_Bao_cao_Cong_no.py` chỉ gọi các hàm
ở đây rồi vẽ biểu đồ.

*** ĐÃ XÁC NHẬN: cách tính aging — COO, 09/09/2026 ***
`aging_days = (as_of_date - due_date).days`, tính ĐỘNG tại thời điểm truy
vấn — KHÔNG lưu cột vật lý `aging_bucket` trong DB (đúng như thiết kế
`Debt` ở `src/db/models/business.py`, vốn cố tình không có cột này). Khác
với phương án "snapshot tại thời điểm import" (aging cố định theo ngày
import) — phương án đó đã bị loại bỏ theo quyết định này. Mọi hàm bên dưới
nhận tham số `as_of_date: date | None = None` (mặc định `date.today()`) để
cho phép test không phụ thuộc vào ngày chạy thật.

*** GIẢ ĐỊNH KỸ THUẬT bổ sung (chưa phải câu hỏi COO đã hỏi, chỉ là cách
lấp khoảng trống kỹ thuật để hàm chạy được) *** — COO chỉ chốt 4 mức "QUÁ
HẠN" (0-30/31-60/61-90/>90), không phải mọi khoản nợ trong bảng `debt` đều
đã quá hạn (`due_date` có thể còn ở tương lai so với `as_of_date`). Ở đây
thêm 1 nhóm phụ `"Chưa đến hạn"` (`aging_days <= 0`) để KHÔNG ép các khoản
nợ chưa đến hạn vào nhầm nhóm "0-30 ngày" (0-30 ngày quá hạn phải là
`0 < aging_days <= 30`, không phải `aging_days` âm/bằng 0) — nếu tổng dư nợ
hiển thị trên UI mà thiếu nhóm này thì sẽ không khớp tổng `SUM(debt.amount)`
thật. Đây là cách lấp khoảng trống hợp lý về kỹ thuật, KHÔNG phải công thức
nghiệp vụ tự suy diễn thêm — không đổi ý nghĩa 4 mức COO đã chốt.

*** BẮT BUỘC RBAC (CLAUDE.md mục 6) — LỌC TRỰC TIẾP theo cột `debt`, KHÔNG
qua suy luận UNION customer như `auth_service.py` ***
Theo yêu cầu giao việc: bảng `debt` đã có sẵn `division_id`/`department_id`/
`employee_id` riêng (không cần suy luận qua `customer_id` như
`fetch_customer_ids_for_employee`/`_for_department`) — tương tự cách
`get_revenue_profit_by_org()` (`report_kinh_doanh.py`) lọc trực tiếp theo
cột tổ chức thay vì qua `scope.customer_ids`. Quy tắc lọc:
- Admin (`scope.unrestricted is True`): xem toàn bộ, không lọc.
- Manager: lọc `Debt.department_id == scope.department_id`.
- User: lọc `Debt.employee_id == scope.employee_id`.
KHÔNG tự viết logic phân quyền nào khác ngoài quy tắc trên.

*** RỦI RO DỮ LIỆU CẦN KIỂM TRA (giao việc, mục 5 erd-tuan-02.md) ***
`debt` lưu ĐỘC LẬP cả `division_id` và `department_id` (không suy ra
`division_id` qua `department.division_id`) — có rủi ro 2 cột lệch nhau
(1 dòng `debt` có `department_id` thuộc về 1 `division` khác với
`debt.division_id`). Hàm `check_division_department_mismatch()` bên dưới
phát hiện và trả về các dòng lệch này để BÁO CÁO, KHÔNG tự chọn cột nào
"đúng hơn" để sửa — đây là quyết định COO cần xác nhận riêng (mục #5,
`erd-tuan-02.md`).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from loguru import logger
from sqlalchemy import Engine, false, select
from sqlalchemy.orm import Session

from src.auth.scope import DataScope
from src.db.models import Debt, Department, Division, Employee
from src.db.models.enums import UserRole
from src.services.db_connection import get_engine

BUCKET_NOT_DUE = "Chưa đến hạn"
"""Nhóm phụ cho khoản nợ CHƯA đến hạn (`aging_days <= 0`) — xem giải thích
đầy đủ ở docstring module (không phải 1 trong 4 mức COO đã chốt)."""

AGING_BUCKETS = ("0-30 ngày", "31-60 ngày", "61-90 ngày", "Trên 90 ngày")
"""4 mức tuổi nợ quá hạn ĐÃ CHỐT với COO (`.claude/rules/trang-thai-yeu-
cau.md`, dòng "Công nợ"): 0-30, 31-60, 61-90, trên 90 ngày."""

BUCKET_ORDER = (BUCKET_NOT_DUE, *AGING_BUCKETS)
"""Thứ tự hiển thị chuẩn cho cột `aging_bucket` — dùng để sắp xếp DataFrame
kết quả theo đúng thứ tự nghiệp vụ (không phải thứ tự alphabet)."""


def compute_aging_bucket(due_date: date, as_of_date: date) -> str:
    """Tính nhóm tuổi nợ quá hạn (aging bucket) cho 1 khoản nợ, tính ĐỘNG
    theo `as_of_date` (COO xác nhận 09/09/2026 — xem docstring module).

    Hàm thuần (pure function), không truy vấn DB — tách riêng để dễ unit
    test độc lập với dữ liệu thật.

    Args:
        due_date: `debt.due_date` của khoản nợ.
        as_of_date: Ngày tính mốc (thường là hôm nay, nhưng cho phép truyền
            cố định để test không phụ thuộc ngày chạy thật).

    Returns:
        Một trong 5 giá trị: `BUCKET_NOT_DUE` (chưa đến hạn, `aging_days <=
        0`), hoặc 1 trong 4 giá trị của `AGING_BUCKETS` (`"0-30 ngày"` ứng
        với `0 < aging_days <= 30`, v.v., `"Trên 90 ngày"` ứng với
        `aging_days > 90`).
    """
    aging_days = (as_of_date - due_date).days
    if aging_days <= 0:
        return BUCKET_NOT_DUE
    if aging_days <= 30:
        return AGING_BUCKETS[0]
    if aging_days <= 60:
        return AGING_BUCKETS[1]
    if aging_days <= 90:
        return AGING_BUCKETS[2]
    return AGING_BUCKETS[3]


def _apply_scope_filter(stmt, scope: DataScope):
    """Áp dụng lọc RBAC lên 1 câu `select()` đã có `Debt` — lọc TRỰC TIẾP
    theo `Debt.department_id`/`Debt.employee_id` (KHÔNG qua `scope.
    customer_ids`/UNION customer, xem docstring module).

    - Admin (`scope.unrestricted`): không lọc, xem toàn bộ.
    - Manager: lọc theo `scope.department_id` — nếu `None` (tài khoản
      Manager không xác định được phòng), trả về 0 dòng (an toàn, không lộ
      dữ liệu) thay vì báo lỗi.
    - User: lọc theo `scope.employee_id` — tương tự, `None` -> 0 dòng.
    - Vai trò khác (không nên xảy ra, `UserRole` chỉ có 3 giá trị): 0 dòng,
      an toàn theo mặc định (fail-safe, không lộ dữ liệu ngoài ý muốn).
    """
    if scope.unrestricted:
        return stmt
    if scope.role == UserRole.MANAGER:
        if scope.department_id is None:
            logger.warning(
                "report_cong_no: Manager user_id={} không có department_id "
                "-> lọc 0 dòng.",
                scope.user_id,
            )
            return stmt.where(false())
        return stmt.where(Debt.department_id == scope.department_id)
    if scope.role == UserRole.USER:
        if scope.employee_id is None:
            logger.warning(
                "report_cong_no: User user_id={} không có employee_id -> lọc 0 dòng.",
                scope.user_id,
            )
            return stmt.where(false())
        return stmt.where(Debt.employee_id == scope.employee_id)
    logger.error(
        "report_cong_no: user_id={} có role={} không xác định -> lọc 0 dòng "
        "(fail-safe).",
        scope.user_id,
        scope.role,
    )
    return stmt.where(false())


def _fetch_scoped_debt_rows(scope: DataScope, *, engine: Engine) -> pd.DataFrame:
    """Truy vấn toàn bộ dòng `debt` (đã lọc RBAC) kèm tên Khối/Phòng/NV,
    dùng chung cho các hàm tổng hợp bên dưới — tránh lặp câu `select()`.

    Returns:
        DataFrame với các cột: `division_id`, `division_name`,
        `department_id`, `department_name`, `employee_id`, `employee_name`,
        `due_date`, `amount`. Rỗng (đúng cột) nếu không có dòng nào khớp.
    """
    columns = [
        "division_id",
        "division_name",
        "department_id",
        "department_name",
        "employee_id",
        "employee_name",
        "due_date",
        "amount",
    ]
    stmt = (
        select(
            Division.id.label("division_id"),
            Division.name.label("division_name"),
            Department.id.label("department_id"),
            Department.name.label("department_name"),
            Employee.id.label("employee_id"),
            Employee.full_name.label("employee_name"),
            Debt.due_date,
            Debt.amount,
        )
        .join(Division, Debt.division_id == Division.id)
        .join(Department, Debt.department_id == Department.id)
        .join(Employee, Debt.employee_id == Employee.id)
    )
    stmt = _apply_scope_filter(stmt, scope)

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df["amount"] = df["amount"].astype(float)
    return df


def get_debt_aging_summary(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    as_of_date: date | None = None,
) -> pd.DataFrame:
    """Tổng hợp công nợ theo nhóm tuổi nợ (aging bucket), đã lọc RBAC —
    dùng cho biểu đồ tổng quan (VD bar 100% theo `aging_bucket`).

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập (lọc trực tiếp theo
            `debt.department_id`/`debt.employee_id`, xem docstring module).
        engine: SQLAlchemy Engine tuỳ chọn (mặc định `get_engine()`).
        as_of_date: Ngày tính mốc aging (mặc định `date.today()` — COO xác
            nhận 09/09/2026 tính ĐỘNG, không snapshot).

    Returns:
        DataFrame với các cột: `aging_bucket`, `debt_count`, `amount` — sắp
        xếp theo `BUCKET_ORDER` (Chưa đến hạn -> 0-30 -> 31-60 -> 61-90 ->
        Trên 90). Trả về DataFrame rỗng (đúng cột) nếu không có dữ liệu
        trong phạm vi được phép xem.
    """
    engine = engine or get_engine()
    as_of_date = as_of_date or date.today()
    columns = ["aging_bucket", "debt_count", "amount"]

    df = _fetch_scoped_debt_rows(scope, engine=engine)
    if df.empty:
        logger.warning(
            "get_debt_aging_summary: không có dữ liệu công nợ trong phạm vi "
            "(user_id={}).",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    df["aging_bucket"] = df["due_date"].apply(
        lambda d: compute_aging_bucket(d, as_of_date)
    )
    agg = df.groupby("aging_bucket", as_index=False).agg(
        debt_count=("amount", "count"), amount=("amount", "sum")
    )
    agg["aging_bucket"] = pd.Categorical(
        agg["aging_bucket"], categories=BUCKET_ORDER, ordered=True
    )
    agg = agg.sort_values("aging_bucket").reset_index(drop=True)
    agg["aging_bucket"] = agg["aging_bucket"].astype(str)
    logger.info(
        "get_debt_aging_summary: user_id={} as_of_date={} -> {} nhóm, tổng amount={}.",
        scope.user_id,
        as_of_date,
        len(agg),
        agg["amount"].sum(),
    )
    return agg


def get_debt_aging_by_org(
    scope: DataScope,
    *,
    engine: Engine | None = None,
    as_of_date: date | None = None,
) -> pd.DataFrame:
    """Công nợ theo phân cấp Khối → Phòng → Kinh doanh, cắt chéo với nhóm
    tuổi nợ (aging bucket), đã lọc RBAC.

    Trả về dữ liệu ở mức chi tiết nhất (1 dòng / nhân viên / aging_bucket)
    — trang Streamlit tự gộp lại theo Khối/Phòng/NV từ cùng 1 DataFrame này
    để tránh gọi DB nhiều lần (giống mẫu `get_revenue_profit_by_org` ở
    `report_kinh_doanh.py`).

    Args:
        scope: Phạm vi dữ liệu của user đang đăng nhập.
        engine: SQLAlchemy Engine tuỳ chọn.
        as_of_date: Ngày tính mốc aging (mặc định `date.today()`).

    Returns:
        DataFrame với các cột: `division_id`, `division_name`,
        `department_id`, `department_name`, `employee_id`, `employee_name`,
        `aging_bucket`, `debt_count`, `amount` — sắp xếp theo
        `division_name`, `department_name`, `employee_name`, rồi theo
        `BUCKET_ORDER`. Trả về DataFrame rỗng (đúng cột) nếu không có dữ
        liệu trong phạm vi được phép xem.
    """
    engine = engine or get_engine()
    as_of_date = as_of_date or date.today()
    columns = [
        "division_id",
        "division_name",
        "department_id",
        "department_name",
        "employee_id",
        "employee_name",
        "aging_bucket",
        "debt_count",
        "amount",
    ]

    df = _fetch_scoped_debt_rows(scope, engine=engine)
    if df.empty:
        logger.warning(
            "get_debt_aging_by_org: không có dữ liệu công nợ trong phạm vi "
            "(user_id={}).",
            scope.user_id,
        )
        return pd.DataFrame(columns=columns)

    df["aging_bucket"] = df["due_date"].apply(
        lambda d: compute_aging_bucket(d, as_of_date)
    )
    group_cols = [
        "division_id",
        "division_name",
        "department_id",
        "department_name",
        "employee_id",
        "employee_name",
        "aging_bucket",
    ]
    agg = df.groupby(group_cols, as_index=False).agg(
        debt_count=("amount", "count"), amount=("amount", "sum")
    )
    agg["aging_bucket"] = pd.Categorical(
        agg["aging_bucket"], categories=BUCKET_ORDER, ordered=True
    )
    agg = agg.sort_values(
        ["division_name", "department_name", "employee_name", "aging_bucket"]
    ).reset_index(drop=True)
    agg["aging_bucket"] = agg["aging_bucket"].astype(str)
    logger.info(
        "get_debt_aging_by_org: user_id={} as_of_date={} -> {} dòng "
        "(Khối-Phòng-NV x aging_bucket).",
        scope.user_id,
        as_of_date,
        len(agg),
    )
    return agg


def check_division_department_mismatch(*, engine: Engine | None = None) -> pd.DataFrame:
    """Kiểm tra dữ liệu: phát hiện các dòng `debt` mà `department.
    division_id != debt.division_id` (2 cột lưu độc lập, xem docstring
    module + mục #5 `erd-tuan-02.md`).

    Đây là kiểm tra CHẤT LƯỢNG DỮ LIỆU toàn hệ thống (không phải báo cáo
    theo user) — cố tình KHÔNG nhận `scope`, luôn quét toàn bộ bảng `debt`
    để có con số đầy đủ cho mục "cần xác nhận" báo cáo lại COO. KHÔNG tự
    chọn cột nào "đúng hơn" để sửa dữ liệu — chỉ phát hiện và báo cáo.

    Args:
        engine: SQLAlchemy Engine tuỳ chọn (mặc định `get_engine()`).

    Returns:
        DataFrame với các cột: `debt_id`, `customer_id`, `debt_division_id`,
        `debt_department_id`, `department_actual_division_id` — chỉ các
        dòng LỆCH (department.division_id khác debt.division_id). Rỗng nếu
        không phát hiện lệch nào.
    """
    engine = engine or get_engine()

    stmt = (
        select(
            Debt.id.label("debt_id"),
            Debt.customer_id.label("customer_id"),
            Debt.division_id.label("debt_division_id"),
            Debt.department_id.label("debt_department_id"),
            Department.division_id.label("department_actual_division_id"),
        )
        .join(Department, Debt.department_id == Department.id)
        .where(Department.division_id != Debt.division_id)
    )

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(
        rows,
        columns=[
            "debt_id",
            "customer_id",
            "debt_division_id",
            "debt_department_id",
            "department_actual_division_id",
        ],
    )
    if df.empty:
        logger.info(
            "check_division_department_mismatch: không phát hiện lệch "
            "division_id/department_id nào trong bảng debt."
        )
    else:
        logger.warning(
            "check_division_department_mismatch: phát hiện {} dòng debt có "
            "department.division_id khác debt.division_id -> CẦN COO XÁC "
            "NHẬN (mục #5, erd-tuan-02.md), KHÔNG tự sửa.",
            len(df),
        )
    return df
