"""Pandera schema cho nhóm bảng nghiệp vụ (fact): sales_order, price_request,
supplier_evaluation, cost, budget, personnel_cost, debt,
customer_classification_history.

Nguồn đối chiếu: `src/db/models/business.py`. Xem quy ước chung (cột `id`
tường minh, `strict=True`, `coerce=True`, FK chỉ kiểm tra kiểu dữ liệu ở
đây — tồn tại thật trong bảng cha kiểm tra riêng bằng query DB) tại
docstring đầu file `dimension_schemas.py`.
"""

from __future__ import annotations

import pandera.pandas as pa

from src.db.models.enums import StaffGroup

_STAFF_GROUP_VALUES = [g.value for g in StaffGroup]

# Thang điểm supplier_evaluation.score: xem GIẢ ĐỊNH MẶC ĐỊNH 0-100 đã ghi
# trong docs/architecture/erd-tuan-02.md, mục 10 "Việc cần xác nhận" (cập
# nhật 22/08/2026, bước 2.4). Nếu COO xác nhận lại là thang 1-5, CHỈ cần đổi
# 2 hằng số dưới đây, không cần đổi cấu trúc bảng (Numeric(5,2) chứa được
# cả 2 thang).
SUPPLIER_EVALUATION_SCORE_MIN = 0
SUPPLIER_EVALUATION_SCORE_MAX = 100


sales_order_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "customer_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "service_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "employee_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "order_date": pa.Column(pa.DateTime, nullable=False, coerce=True),
        # Placeholder tự do — danh sách giá trị cụ thể CHƯA xác nhận, xem
        # mục 1 "Việc cần xác nhận" trong erd-tuan-02.md. Chỉ kiểm tra
        # not-null + độ dài khớp String(50) ở model, KHÔNG tự bịa enum.
        "status": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.str_length(min_value=1, max_value=50),
        ),
        "revenue": pa.Column(float, nullable=False, checks=pa.Check.ge(0)),
        "order_cost": pa.Column(float, nullable=False, checks=pa.Check.ge(0)),
        # Placeholder tự do — xem mục 2 "Việc cần xác nhận" trong
        # erd-tuan-02.md (chưa rõ có phải field độc lập với status không).
        "invoice_status": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.str_length(min_value=1, max_value=50),
        ),
        "invoice_date": pa.Column(
            pa.DateTime, nullable=True, required=False, coerce=True
        ),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

price_request_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "service_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "employee_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        # Nullable theo mục 7 "Việc cần xác nhận" erd-tuan-02.md (giả định:
        # báo giá cho KH tiềm năng chưa có trong bảng customer).
        "customer_id": pa.Column(
            "Int64", nullable=True, required=False, checks=pa.Check.gt(0)
        ),
        "request_date": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "is_won": pa.Column(bool, nullable=False),
        # Nullable — chỉ điền khi đã chốt thành đơn hàng thật.
        "sales_order_id": pa.Column(
            "Int64", nullable=True, required=False, checks=pa.Check.gt(0)
        ),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

supplier_evaluation_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "supplier_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "service_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "employee_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "period": pa.Column(pa.DateTime, nullable=False, coerce=True),
        # GIẢ ĐỊNH thang điểm 0-100 (xem hằng số ở đầu file + ghi chú trong
        # erd-tuan-02.md mục 10) — CHƯA phải xác nhận chính thức của COO.
        "score": pa.Column(
            float,
            nullable=False,
            checks=pa.Check.in_range(
                SUPPLIER_EVALUATION_SCORE_MIN, SUPPLIER_EVALUATION_SCORE_MAX
            ),
        ),
        "notes": pa.Column(str, nullable=True, required=False),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

cost_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "division_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "period": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "amount": pa.Column(float, nullable=False, checks=pa.Check.ge(0)),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

budget_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "division_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "period": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "amount": pa.Column(float, nullable=False, checks=pa.Check.ge(0)),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

personnel_cost_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "staff_group": pa.Column(
            str, nullable=False, checks=pa.Check.isin(_STAFF_GROUP_VALUES)
        ),
        "period": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "amount": pa.Column(float, nullable=False, checks=pa.Check.ge(0)),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

debt_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "customer_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "division_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "department_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "employee_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "invoice_date": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "due_date": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "amount": pa.Column(float, nullable=False, checks=pa.Check.ge(0)),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

customer_classification_history_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "customer_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "classification": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.isin(["A", "B", "C"]),
        ),
        "snapshot_date": pa.Column(pa.DateTime, nullable=False, coerce=True),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)
