"""Service tầng nghiệp vụ cho báo cáo Khách hàng — Tăng giảm loại KH (A/B/C)
theo thời gian và Phân bố khách hàng theo nguồn.

Theo CLAUDE.md mục 2 (tách lớp): module này chứa TOÀN BỘ truy vấn SQLAlchemy
+ tính toán KPI cho báo cáo Khách hàng. Trang Streamlit
(`src/app/pages/2_Bao_cao_Khach_hang.py`) CHỈ được gọi hàm ở đây rồi vẽ
Plotly — không tự viết SQL hay logic tính toán tại chỗ.

Theo CLAUDE.md mục 6 (RBAC, bắt buộc): mọi hàm ở đây trả dữ liệu cấp khách
hàng PHẢI nhận `scope: DataScope` (từ `src.auth.scope.compute_data_scope`,
đã có sẵn từ bước 3.1) và lọc theo `scope.customer_ids`, TRỪ KHI
`scope.unrestricted is True` (Admin) thì không lọc. KHÔNG tự viết logic
phân quyền riêng ở đây — tái sử dụng `DataScope` đã có.

Nguồn yêu cầu — `.claude/rules/trang-thai-yeu-cau.md`, nhóm "Khách hàng"
(cả 2 dòng đã "Đã rõ", 17/08/2026):
- "Tăng giảm loại KH (A/B/C)": dùng cột "Phân loại" có sẵn trong FT, đã
  lưu lịch sử theo thời gian ở `CustomerClassificationHistory`
  (`snapshot_date`, `classification`) — khác `Customer.current_classification`
  chỉ lưu trạng thái hiện tại.
- "Theo nguồn khách hàng": dùng cột `Customer.source` có sẵn trong FT.

*** GHI CHÚ RỦI RO RBAC — ĐÃ GHI NHẬN TỪ HD-11/Tuần 3 (xem
`src/auth/scope.py` + `src/services/auth_service.py`) ***
`scope.customer_ids` được `compute_data_scope()` suy luận bằng UNION
`customer_id` từ `sales_order`/`debt`/`price_request` theo `employee_id`
(User) / `department_id` (Manager). Kiểm tra trên dữ liệu thật (MySQL
"lacco", 07/09/2026) cho thấy: 24/30 khách hàng có >1 `employee_id` xuất
hiện trong UNION đó, và 22/30 khách hàng có >1 `department_id` — tức phần
lớn khách hàng "thuộc phạm vi" của nhiều nhân viên/phòng cùng lúc theo cách
suy luận hiện tại. Module này KHÔNG tự xử lý/thu hẹp lại rủi ro đó — chỉ
lọc đúng theo `scope.customer_ids` được `compute_data_scope()` trả về,
đúng nguyên tắc "không tự viết logic phân quyền riêng". Rủi ro này cần COO
xác nhận cách xử lý ở tầng `src/auth/`, KHÔNG xử lý ở tầng service báo cáo.

*** GHI CHÚ CHẤT LƯỢNG DỮ LIỆU — PHÁT HIỆN KHI KIỂM TRA DỮ LIỆU THẬT
07/09/2026, CHƯA XÁC NHẬN CÁCH XỬ LÝ ***
`customer_classification_history` có 1 số dòng trùng lặp/xung đột tại cùng
`(customer_id, snapshot_date)`:
- Trùng lặp thuần (cùng classification, ví dụ customer_id=27 có 2 dòng
  "B" cùng snapshot_date=2026-08-01): không ảnh hưởng kết quả vì hàm dưới
  đây dùng `COUNT(DISTINCT customer_id)`, không đếm trùng.
- Xung đột thật (2 dòng khác `classification` cùng 1
  `(customer_id, snapshot_date)`, ví dụ customer_id=2 có cả "B" và "C" tại
  2026-07-01; customer_id=7 có cả "A" và "B" tại 2026-08-01): hàm dưới đây
  KHÔNG tự chọn 1 giá trị "đúng" — khách hàng đó sẽ được đếm ở CẢ 2 cột
  phân loại cho mốc đó (không âm thầm loại bỏ dòng nào). Nghĩa là tổng số
  KH cộng dồn theo A+B+C tại 1 mốc có thể lớn hơn số KH riêng biệt thực tế
  tại mốc đó. Cần COO xác nhận đây là lỗi import (import 2 lần, ghi đè
  không đúng) hay có ý nghĩa nghiệp vụ khác trước khi quyết định cách xử lý
  (lấy dòng mới nhất theo `id`? loại trùng? sửa lại quy trình import?).
"""

from __future__ import annotations

import pandas as pd
from loguru import logger
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from src.auth.scope import DataScope
from src.db.models.business import CustomerClassificationHistory
from src.db.models.dimension import Customer
from src.services.db_connection import get_engine

# Customer.source cho phép NULL trong ERD (`src/db/models/dimension.py`) —
# nhãn hiển thị khi gặp giá trị NULL, KHÔNG phải giá trị nghiệp vụ tự bịa,
# chỉ dùng để nhóm hiển thị trên biểu đồ.
UNKNOWN_SOURCE_LABEL = "Không xác định"


def get_classification_trend(
    scope: DataScope, *, engine: Engine | None = None
) -> pd.DataFrame:
    """Xu hướng số lượng khách hàng theo loại A/B/C qua các mốc
    `snapshot_date` thực tế có trong `customer_classification_history`.

    Lọc theo `scope.customer_ids`, TRỪ KHI `scope.unrestricted` (Admin) thì
    không lọc — CLAUDE.md mục 6.

    Parameters
    ----------
    scope : DataScope
        Phạm vi dữ liệu của user đang đăng nhập, từ
        `src.auth.scope.compute_data_scope()`.
    engine : sqlalchemy.Engine, optional
        Cho phép truyền engine riêng (dùng trong test) — mặc định dùng
        `src.services.db_connection.get_engine()`.

    Returns
    -------
    pd.DataFrame
        Dạng "tidy" (long format), cột: `snapshot_date` (date),
        `classification` (str: "A"/"B"/"C"), `so_luong_kh` (int — số khách
        hàng riêng biệt tại mốc đó). Trả DataFrame rỗng (đúng cột) nếu
        `scope.customer_ids` rỗng và không unrestricted (không truy vấn).
    """
    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_classification_trend: user_id={} có scope rỗng (không "
            "unrestricted, customer_ids rỗng) -> trả DataFrame rỗng, "
            "không truy vấn DB.",
            scope.user_id,
        )
        return pd.DataFrame(columns=["snapshot_date", "classification", "so_luong_kh"])

    engine = engine or get_engine()

    stmt = (
        select(
            CustomerClassificationHistory.snapshot_date,
            CustomerClassificationHistory.classification,
            func.count(func.distinct(CustomerClassificationHistory.customer_id)).label(
                "so_luong_kh"
            ),
        )
        .group_by(
            CustomerClassificationHistory.snapshot_date,
            CustomerClassificationHistory.classification,
        )
        .order_by(CustomerClassificationHistory.snapshot_date)
    )
    if not scope.unrestricted:
        stmt = stmt.where(
            CustomerClassificationHistory.customer_id.in_(scope.customer_ids)
        )

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=["snapshot_date", "classification", "so_luong_kh"])
    if not df.empty:
        # Cột classification trả về enum member (CustomerClassification) do
        # dùng Enum(..., native_enum=False) trong model — chuẩn hoá về str
        # "A"/"B"/"C" để dễ vẽ Plotly/hiển thị.
        df["classification"] = df["classification"].apply(
            lambda c: c.value if hasattr(c, "value") else c
        )

    logger.info(
        "get_classification_trend: user_id={} unrestricted={} -> {} dòng, "
        "{} mốc snapshot_date thực tế.",
        scope.user_id,
        scope.unrestricted,
        len(df),
        df["snapshot_date"].nunique() if not df.empty else 0,
    )
    return df


def get_source_distribution(
    scope: DataScope, *, engine: Engine | None = None
) -> pd.DataFrame:
    """Phân bố số lượng khách hàng theo `Customer.source` ("Nguồn" khách
    hàng, cột có sẵn trong FT).

    Lọc theo `scope.customer_ids`, TRỪ KHI `scope.unrestricted` (Admin) thì
    không lọc — CLAUDE.md mục 6.

    Parameters
    ----------
    scope : DataScope
        Phạm vi dữ liệu của user đang đăng nhập.
    engine : sqlalchemy.Engine, optional
        Cho phép truyền engine riêng (dùng trong test).

    Returns
    -------
    pd.DataFrame
        Cột: `source` (str — đã thay `None`/NULL bằng
        `UNKNOWN_SOURCE_LABEL`), `so_luong_kh` (int). Trả DataFrame rỗng
        (đúng cột) nếu `scope.customer_ids` rỗng và không unrestricted.
    """
    if not scope.unrestricted and not scope.customer_ids:
        logger.warning(
            "get_source_distribution: user_id={} có scope rỗng -> trả "
            "DataFrame rỗng, không truy vấn DB.",
            scope.user_id,
        )
        return pd.DataFrame(columns=["source", "so_luong_kh"])

    engine = engine or get_engine()

    stmt = select(
        Customer.source,
        func.count(Customer.id).label("so_luong_kh"),
    ).group_by(Customer.source)
    if not scope.unrestricted:
        stmt = stmt.where(Customer.id.in_(scope.customer_ids))

    with Session(engine) as session:
        rows = session.execute(stmt).all()

    df = pd.DataFrame(rows, columns=["source", "so_luong_kh"])
    if not df.empty:
        df["source"] = df["source"].fillna(UNKNOWN_SOURCE_LABEL)

    logger.info(
        "get_source_distribution: user_id={} unrestricted={} -> {} nguồn khác nhau.",
        scope.user_id,
        scope.unrestricted,
        len(df),
    )
    return df
