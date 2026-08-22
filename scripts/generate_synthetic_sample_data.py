"""Sinh dữ liệu mẫu SYNTHETIC (giả lập) cho toàn bộ 18 bảng ERD của
Dashboard LACCO — bước 2.4.

QUAN TRỌNG: Dữ liệu sinh ra ở đây HOÀN TOÀN GIẢ LẬP — không phải số liệu
tài chính/khách hàng thật, không phải định dạng export thật từ FT/AMIS.
Mọi file output đều có tiền tố `synthetic_` (xem `data/sample/README.md`)
để không ai nhầm lẫn khi dùng làm dữ liệu demo/test pipeline.

Script này CHỈ sinh dữ liệu và ghi ra file — KHÔNG import vào DB (việc đó
do `scripts/run_synthetic_import_demo.py` đảm nhiệm, gọi
`src/services/import_pipeline.py`). Vì đây là script sinh dữ liệu một lần
(one-off), không phải logic nghiệp vụ tái sử dụng, nên đặt ở `scripts/`
theo đúng cấu trúc thư mục CLAUDE.md mục 2, KHÔNG đặt trong `src/services/`.

Chạy: `python scripts/generate_synthetic_sample_data.py`
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import bcrypt
import pandas as pd

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
SEED = 42
random.seed(SEED)

TODAY = date(2026, 8, 22)


def _month_starts(n_months: int, end: date = TODAY) -> list[date]:
    """Trả về n_months ngày đầu tháng gần nhất, tính lùi từ `end`."""
    months = []
    year, month = end.year, end.month
    for _ in range(n_months):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def _random_date(start: date, end: date) -> date:
    delta_days = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta_days, 0)))


def _write(df: pd.DataFrame, name: str, *, as_excel: bool = False) -> Path:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    if as_excel:
        path = SAMPLE_DIR / f"synthetic_{name}.xlsx"
        df.to_excel(path, index=False, engine="openpyxl")
    else:
        path = SAMPLE_DIR / f"synthetic_{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8")
    print(f"Wrote {len(df):>3} rows -> {path}")
    return path


# ---------------------------------------------------------------------------
# Nhóm bảng danh mục (dimension) — sinh trước, theo đúng thứ tự phụ thuộc FK
# ---------------------------------------------------------------------------


def gen_division() -> pd.DataFrame:
    names = [
        "Khối Kinh doanh trực tiếp",
        "Khối Vận hành",
        "Khối Pricing",
        "Khối Tài chính - Kế toán",
        "Khối Hỗ trợ",
    ]
    return pd.DataFrame({"id": range(1, len(names) + 1), "name": names})


def gen_department(division_df: pd.DataFrame) -> pd.DataFrame:
    dept_names_per_division = {
        1: ["Phòng Kinh doanh Cước biển", "Phòng Kinh doanh Hải quan"],
        2: ["Phòng Vận hành Kho vận", "Phòng Vận hành Vận tải"],
        3: ["Phòng Pricing Cước", "Phòng Pricing Hải quan"],
        4: ["Phòng Kế toán", "Phòng Tài chính"],
        5: ["Phòng Nhân sự", "Phòng IT"],
    }
    rows = []
    dept_id = 1
    for division_id, names in dept_names_per_division.items():
        for name in names:
            rows.append({"id": dept_id, "name": name, "division_id": division_id})
            dept_id += 1
    return pd.DataFrame(rows)


def gen_employee(department_df: pd.DataFrame, n: int = 30) -> pd.DataFrame:
    staff_groups = ["LĐ", "QL", "Frontline", "Middle", "Backend"]
    positions = [
        "Nhân viên",
        "Chuyên viên",
        "Trưởng nhóm",
        "Trưởng phòng",
        "Giám đốc Khối",
    ]
    dept_ids = department_df["id"].tolist()
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "full_name": f"Nhân viên Demo {i:02d}",
                "department_id": random.choice(dept_ids),
                "staff_group": random.choices(
                    staff_groups, weights=[1, 2, 8, 8, 6], k=1
                )[0],
                "position": random.choice(positions),
                "is_active": True if i > 2 else False,  # 2 dòng để test is_active=False
            }
        )
    return pd.DataFrame(rows)


def gen_service() -> pd.DataFrame:
    names = [
        "Cước biển",
        "Cước hàng không",
        "Hải quan",
        "Kho vận",
        "Vận tải nội địa",
        "Logistics trọn gói",
    ]
    return pd.DataFrame({"id": range(1, len(names) + 1), "name": names})


def gen_customer(n: int = 30) -> pd.DataFrame:
    sources = ["Giới thiệu", "Website", "Sales tự tìm", "Hội chợ triển lãm"]
    classifications = ["A", "B", "C"]
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "code": f"KHDEMO{i:04d}",
                "name": f"Công ty TNHH Khách Hàng Demo {i:02d}",
                "source": random.choice(sources),
                "current_classification": random.choices(
                    classifications, weights=[2, 5, 3], k=1
                )[0],
            }
        )
    return pd.DataFrame(rows)


def gen_supplier(n: int = 15) -> pd.DataFrame:
    rows = [
        {"id": i, "name": f"Nhà Cung Cấp Demo {i:02d}"} for i in range(1, n + 1)
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# users — cần employee đã sinh xong (employee_id nullable, ~2/3 có gắn NV)
# ---------------------------------------------------------------------------


USERS_ID_OFFSET = 100
"""ID bắt đầu của user synthetic — dời lên 100 để chừa id 1..99 cho các
tài khoản hệ thống/bootstrap (VD `system_import_bootstrap` do
`scripts/run_synthetic_import_demo.py` tự tạo TRƯỚC khi import file này,
xem docstring script đó) — tránh đụng PRIMARY KEY khi cả 2 nguồn cùng ghi
vào bảng `users`."""


def gen_users(employee_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """`password_hash` được bcrypt-hash NGAY tại bước sinh dữ liệu mẫu (mật
    khẩu giả định dùng chung `Synthetic@123!`, KHÔNG phải mật khẩu thật của
    ai) — theo docstring `src/services/import_schemas/security_schemas.py`:
    việc hash thuộc về tầng `src/auth/` (chưa xây), pipeline import chỉ
    load chuỗi hash có sẵn, không tự hash.
    """
    dummy_password = b"Synthetic@123!"
    password_hash = bcrypt.hashpw(dummy_password, bcrypt.gensalt()).decode()
    roles = ["Admin", "Manager", "User"]
    employee_ids = employee_df["id"].tolist()
    linked_employee_ids = random.sample(employee_ids, k=min(14, len(employee_ids)))
    rows = []
    for i in range(1, n + 1):
        emp_id = linked_employee_ids[i - 1] if i <= len(linked_employee_ids) else None
        rows.append(
            {
                "id": USERS_ID_OFFSET + i,
                "username": f"user_demo_{i:02d}",
                "password_hash": password_hash,
                "role": random.choices(roles, weights=[1, 4, 15], k=1)[0],
                "employee_id": emp_id,
                "is_active": True,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Nhóm bảng nghiệp vụ (fact)
# ---------------------------------------------------------------------------


def gen_sales_order(
    customer_df: pd.DataFrame, service_df: pd.DataFrame, employee_df: pd.DataFrame, n: int = 40
) -> pd.DataFrame:
    # Ghi chú: "status"/"invoice_status" là placeholder tự do (chưa có danh
    # sách enum chính thức từ FT — xem mục 1, 2 "Việc cần xác nhận" trong
    # erd-tuan-02.md). Giá trị dưới đây CHỈ mang tính minh hoạ cho dữ liệu
    # mẫu, KHÔNG phải danh sách trạng thái đã được xác nhận.
    statuses = ["Mới tạo", "Đang xử lý", "Đang vận chuyển", "Đã giao", "Huỷ"]
    invoice_statuses = ["Chưa xuất hoá đơn", "Đã xuất hoá đơn", "Đã thanh toán"]
    rows = []
    start = TODAY - timedelta(days=365)
    for i in range(1, n + 1):
        order_date = _random_date(start, TODAY)
        revenue = round(random.uniform(20_000_000, 500_000_000), 2)
        order_cost = round(revenue * random.uniform(0.6, 0.9), 2)
        invoice_status = random.choice(invoice_statuses)
        invoice_date = (
            order_date + timedelta(days=random.randint(1, 20))
            if invoice_status != "Chưa xuất hoá đơn"
            else None
        )
        rows.append(
            {
                "id": i,
                "customer_id": random.choice(customer_df["id"].tolist()),
                "service_id": random.choice(service_df["id"].tolist()),
                "employee_id": random.choice(employee_df["id"].tolist()),
                "order_date": order_date,
                "status": random.choice(statuses),
                "revenue": revenue,
                "order_cost": order_cost,
                "invoice_status": invoice_status,
                "invoice_date": invoice_date,
            }
        )
    return pd.DataFrame(rows)


def gen_price_request(
    service_df: pd.DataFrame,
    employee_df: pd.DataFrame,
    customer_df: pd.DataFrame,
    sales_order_df: pd.DataFrame,
    n: int = 35,
) -> pd.DataFrame:
    sales_order_ids = sales_order_df["id"].tolist()
    used_sales_order_ids: set[int] = set()
    rows = []
    start = TODAY - timedelta(days=365)
    for i in range(1, n + 1):
        is_won = random.random() < 0.4
        customer_id = (
            random.choice(customer_df["id"].tolist())
            if random.random() < 0.7
            else None
        )
        sales_order_id = None
        if is_won and len(used_sales_order_ids) < len(sales_order_ids):
            candidates = [sid for sid in sales_order_ids if sid not in used_sales_order_ids]
            if candidates:
                sales_order_id = random.choice(candidates)
                used_sales_order_ids.add(sales_order_id)
        rows.append(
            {
                "id": i,
                "service_id": random.choice(service_df["id"].tolist()),
                "employee_id": random.choice(employee_df["id"].tolist()),
                "customer_id": customer_id,
                "request_date": _random_date(start, TODAY),
                "is_won": is_won,
                "sales_order_id": sales_order_id,
            }
        )
    return pd.DataFrame(rows)


def gen_supplier_evaluation(
    supplier_df: pd.DataFrame, service_df: pd.DataFrame, employee_df: pd.DataFrame, n: int = 25
) -> pd.DataFrame:
    # GIẢ ĐỊNH thang điểm 0-100 — xem docs/architecture/erd-tuan-02.md mục
    # 10 (cập nhật 22/08/2026, data-import-agent bước 2.4).
    periods = _month_starts(6)
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "supplier_id": random.choice(supplier_df["id"].tolist()),
                "service_id": random.choice(service_df["id"].tolist()),
                "employee_id": random.choice(employee_df["id"].tolist()),
                "period": random.choice(periods),
                "score": round(random.uniform(40, 100), 2),
                "notes": "Đánh giá định kỳ (dữ liệu synthetic)" if i % 3 == 0 else None,
            }
        )
    return pd.DataFrame(rows)


def gen_cost(division_df: pd.DataFrame) -> pd.DataFrame:
    periods = _month_starts(6)
    rows = []
    row_id = 1
    for division_id in division_df["id"].tolist():
        for period in periods:
            rows.append(
                {
                    "id": row_id,
                    "division_id": division_id,
                    "period": period,
                    "amount": round(random.uniform(200_000_000, 900_000_000), 2),
                }
            )
            row_id += 1
    return pd.DataFrame(rows)


def gen_budget(division_df: pd.DataFrame) -> pd.DataFrame:
    periods = _month_starts(6)
    rows = []
    row_id = 1
    for division_id in division_df["id"].tolist():
        for period in periods:
            rows.append(
                {
                    "id": row_id,
                    "division_id": division_id,
                    "period": period,
                    "amount": round(random.uniform(250_000_000, 950_000_000), 2),
                }
            )
            row_id += 1
    return pd.DataFrame(rows)


def gen_personnel_cost() -> pd.DataFrame:
    staff_groups = ["LĐ", "QL", "Frontline", "Middle", "Backend"]
    periods = _month_starts(6)
    rows = []
    row_id = 1
    for staff_group in staff_groups:
        for period in periods:
            rows.append(
                {
                    "id": row_id,
                    "staff_group": staff_group,
                    "period": period,
                    "amount": round(random.uniform(80_000_000, 400_000_000), 2),
                }
            )
            row_id += 1
    return pd.DataFrame(rows)


def gen_debt(
    customer_df: pd.DataFrame,
    division_df: pd.DataFrame,
    department_df: pd.DataFrame,
    employee_df: pd.DataFrame,
    n: int = 30,
) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        division_id = random.choice(division_df["id"].tolist())
        # Chọn department THUỘC ĐÚNG division đã chọn — giữ dữ liệu mẫu
        # nhất quán 2 cột division_id/department_id (xem mục 5 "Việc cần
        # xác nhận" erd-tuan-02.md: model cho phép 2 cột lệch nhau, nhưng
        # dữ liệu mẫu không cố tình tạo lệch để tránh gây hiểu nhầm là bug).
        dept_candidates = department_df[
            department_df["division_id"] == division_id
        ]["id"].tolist()
        department_id = random.choice(dept_candidates)
        invoice_date = _random_date(TODAY - timedelta(days=365), TODAY - timedelta(days=1))
        # Trải đều 4 mức tuổi nợ 0-30/31-60/61-90/>90 ngày để dữ liệu mẫu
        # phủ đủ các ngưỡng báo cáo Công nợ.
        bucket = random.choice([15, 45, 75, 120])
        due_date = TODAY - timedelta(days=bucket)
        rows.append(
            {
                "id": i,
                "customer_id": random.choice(customer_df["id"].tolist()),
                "division_id": division_id,
                "department_id": department_id,
                "employee_id": random.choice(employee_df["id"].tolist()),
                "invoice_date": invoice_date,
                "due_date": due_date,
                "amount": round(random.uniform(10_000_000, 200_000_000), 2),
            }
        )
    return pd.DataFrame(rows)


def gen_customer_classification_history(
    customer_df: pd.DataFrame, n: int = 40
) -> pd.DataFrame:
    classifications = ["A", "B", "C"]
    snapshot_dates = _month_starts(4)
    rows = []
    row_id = 1
    customer_ids = customer_df["id"].tolist()
    # Đảm bảo mỗi customer có ít nhất 1 snapshot, phần còn lại random thêm.
    for cid in customer_ids:
        rows.append(
            {
                "id": row_id,
                "customer_id": cid,
                "classification": random.choice(classifications),
                "snapshot_date": random.choice(snapshot_dates),
            }
        )
        row_id += 1
        if row_id > n:
            break
    while row_id <= n:
        rows.append(
            {
                "id": row_id,
                "customer_id": random.choice(customer_ids),
                "classification": random.choice(classifications),
                "snapshot_date": random.choice(snapshot_dates),
            }
        )
        row_id += 1
    return pd.DataFrame(rows)


def gen_login_history(users_df: pd.DataFrame, n: int = 30) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "user_id": random.choice(users_df["id"].tolist()),
                "ip_address": f"10.0.{random.randint(0,255)}.{random.randint(1,254)}",
                "success": random.random() < 0.9,
            }
        )
    return pd.DataFrame(rows)


def gen_audit_log(users_df: pd.DataFrame, n: int = 30) -> pd.DataFrame:
    # "action" là placeholder tự do — danh sách enum CHƯA được xác nhận
    # (mục 8 "Việc cần xác nhận" erd-tuan-02.md). Giá trị dưới đây chỉ minh
    # hoạ, không phải danh sách chính thức.
    actions = ["create", "update", "delete"]
    tables = ["sales_order", "customer", "debt", "cost"]
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "user_id": random.choice(users_df["id"].tolist()),
                "action": random.choice(actions),
                "table_name": random.choice(tables),
                "record_id": random.randint(1, 30),
                "old_value": None,
                "new_value": "(dữ liệu synthetic - minh hoạ)",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    division_df = gen_division()
    department_df = gen_department(division_df)
    employee_df = gen_employee(department_df)
    service_df = gen_service()
    customer_df = gen_customer()
    supplier_df = gen_supplier()
    users_df = gen_users(employee_df)

    sales_order_df = gen_sales_order(customer_df, service_df, employee_df)
    price_request_df = gen_price_request(
        service_df, employee_df, customer_df, sales_order_df
    )
    supplier_evaluation_df = gen_supplier_evaluation(supplier_df, service_df, employee_df)
    cost_df = gen_cost(division_df)
    budget_df = gen_budget(division_df)
    personnel_cost_df = gen_personnel_cost()
    debt_df = gen_debt(customer_df, division_df, department_df, employee_df)
    classification_history_df = gen_customer_classification_history(customer_df)
    login_history_df = gen_login_history(users_df)
    audit_log_df = gen_audit_log(users_df)

    _write(division_df, "division")
    _write(department_df, "department")
    _write(employee_df, "employee")
    _write(service_df, "service")
    _write(customer_df, "customer")
    _write(supplier_df, "supplier")
    _write(users_df, "users")

    _write(sales_order_df, "sales_order", as_excel=True)
    _write(price_request_df, "price_request")
    _write(supplier_evaluation_df, "supplier_evaluation")
    _write(cost_df, "cost", as_excel=True)
    _write(budget_df, "budget")
    _write(personnel_cost_df, "personnel_cost")
    _write(debt_df, "debt")
    _write(classification_history_df, "customer_classification_history")
    _write(login_history_df, "login_history")
    _write(audit_log_df, "audit_log")

    print("\nDone generating SYNTHETIC sample data for 18 tables into", SAMPLE_DIR)


if __name__ == "__main__":
    main()
