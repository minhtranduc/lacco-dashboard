"""Test `src/services/report_cong_no.py` — báo cáo Công nợ Khối → Phòng →
Kinh doanh (CLAUDE.md mục 7, dòng "Công nợ").

Phạm vi test:
- `compute_aging_bucket()` — hàm thuần, kiểm tra đủ 5 nhóm (`BUCKET_NOT_DUE`
  + 4 mức `AGING_BUCKETS`) và đúng ranh giới ngày (0 vs 1, 30 vs 31, 60 vs
  61, 90 vs 91) — off-by-one ở đây ảnh hưởng trực tiếp số liệu hiển thị.
- `get_debt_aging_summary()` / `get_debt_aging_by_org()` — RBAC mẫu lọc #3
  (CLAUDE.md mục 7): lọc TRỰC TIẾP trên `Debt.department_id`/`employee_id`,
  không qua UNION `scope.customer_ids` — 1 case Admin (unrestricted, xem
  toàn bộ) + 1 case Manager/User bị giới hạn (không thấy dữ liệu Khối/Phòng
  khác) + 1 case phạm vi rỗng (Manager không có `department_id`).
- `check_division_department_mismatch()` — phát hiện dòng `debt` có
  `department.division_id != debt.division_id` (rủi ro dữ liệu ghi ở
  `Debt` model, mục 5 `erd-tuan-02.md`) và case dữ liệu nhất quán (rỗng).

Dùng fixture `db_engine` từ `tests/conftest.py` (SQLite in-memory, KHÔNG
đụng MySQL "lacco" thật) — seed dữ liệu `Debt`/`Division`/`Department`/
`Employee`/`Customer` riêng trong file này (không dùng `seeded_scope_data`,
fixture đó không seed bảng `debt`).

Không có test riêng cho quy tắc loại trừ `sales_order.status="Huỷ"` (CLAUDE.md
mục 7) — đã xác nhận không áp dụng ở đây: bảng `debt` (`src/db/models/
business.py`) không có cột `status`, quy tắc đó chỉ áp dụng cho tổng doanh
thu/lãi lỗ tính từ `sales_order`, không áp dụng cho công nợ.

`DataScope` được dựng trực tiếp (không qua `compute_data_scope()`) vì
`_apply_scope_filter()` trong `report_cong_no.py` chỉ đọc `scope.
unrestricted`/`scope.role`/`scope.department_id`/`scope.employee_id` — không
đọc `scope.customer_ids`, nên không cần seed bảng `users` + suy luận UNION
customer thật để test module này.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from src.auth.scope import DataScope
from src.db.models.business import Debt
from src.db.models.dimension import Customer, Department, Division, Employee
from src.db.models.enums import CustomerClassification, StaffGroup, UserRole
from src.services.report_cong_no import (
    AGING_BUCKETS,
    BUCKET_NOT_DUE,
    check_division_department_mismatch,
    compute_aging_bucket,
    get_debt_aging_by_org,
    get_debt_aging_summary,
)


def _make_scope(
    *,
    role: UserRole,
    unrestricted: bool = False,
    department_id: int | None = None,
    employee_id: int | None = None,
) -> DataScope:
    """Dựng `DataScope` tối thiểu cho test — xem giải thích ở docstring
    module vì sao không cần đi qua `compute_data_scope()` thật."""
    return DataScope(
        user_id=1,
        username="test-user",
        role=role,
        employee_id=employee_id,
        department_id=department_id,
        division_id=None,
        classification_hint=None,
        customer_ids=frozenset(),
        unrestricted=unrestricted,
        description="scope dựng riêng cho test report_cong_no",
    )


@pytest.fixture()
def debt_org_data(db_engine):
    """Seed 2 Khối, mỗi Khối 1 Phòng, mỗi Phòng 1 Nhân viên, cùng 2 khoản
    `Debt` NHẤT QUÁN (`division_id`/`department_id` khớp đúng phân cấp thật,
    không lệch) — dùng cho test RBAC + aging của
    `get_debt_aging_summary()`/`get_debt_aging_by_org()`.

    - Debt 1 (Khối 1/Phòng 1/NV 1): `due_date` cách `as_of_date` 15 ngày
      -> nhóm "0-30 ngày".
    - Debt 2 (Khối 2/Phòng 2/NV 2): `due_date` cách `as_of_date` 75 ngày
      -> nhóm "61-90 ngày".
    """
    as_of_date = date(2026, 6, 30)
    with Session(db_engine) as session:
        div1 = Division(name="Khối 1")
        div2 = Division(name="Khối 2")
        session.add_all([div1, div2])
        session.flush()

        dept1 = Department(name="Phòng 1", division_id=div1.id)
        dept2 = Department(name="Phòng 2", division_id=div2.id)
        session.add_all([dept1, dept2])
        session.flush()

        emp1 = Employee(
            full_name="Nhân viên 1",
            department_id=dept1.id,
            staff_group=StaffGroup.FRONTLINE,
        )
        emp2 = Employee(
            full_name="Nhân viên 2",
            department_id=dept2.id,
            staff_group=StaffGroup.FRONTLINE,
        )
        session.add_all([emp1, emp2])
        session.flush()

        cust1 = Customer(
            code="CUST-1",
            name="Khách hàng 1",
            current_classification=CustomerClassification.C,
        )
        cust2 = Customer(
            code="CUST-2",
            name="Khách hàng 2",
            current_classification=CustomerClassification.C,
        )
        session.add_all([cust1, cust2])
        session.flush()

        debt1 = Debt(
            customer_id=cust1.id,
            division_id=div1.id,
            department_id=dept1.id,
            employee_id=emp1.id,
            invoice_date=date(2026, 5, 1),
            due_date=as_of_date - timedelta(days=15),
            amount=1_000_000,
        )
        debt2 = Debt(
            customer_id=cust2.id,
            division_id=div2.id,
            department_id=dept2.id,
            employee_id=emp2.id,
            invoice_date=date(2026, 3, 1),
            due_date=as_of_date - timedelta(days=75),
            amount=2_000_000,
        )
        session.add_all([debt1, debt2])
        session.commit()

        return {
            "as_of_date": as_of_date,
            "div1_id": div1.id,
            "div2_id": div2.id,
            "dept1_id": dept1.id,
            "dept2_id": dept2.id,
            "emp1_id": emp1.id,
            "emp2_id": emp2.id,
        }


def _seed_mismatched_debt(engine) -> dict:
    """Seed 1 khoản `Debt` mà `department.division_id` KHÁC
    `debt.division_id` — ca lỗi dữ liệu mà `check_division_department_
    mismatch()` phải phát hiện (xem docstring module `report_cong_no.py`,
    mục #5 `erd-tuan-02.md`)."""
    with Session(engine) as session:
        div_a = Division(name="Khối A")
        div_b = Division(name="Khối B — chủ thật của Phòng B")
        session.add_all([div_a, div_b])
        session.flush()

        dept_b = Department(name="Phòng B", division_id=div_b.id)
        session.add(dept_b)
        session.flush()

        emp = Employee(
            full_name="Nhân viên lệch",
            department_id=dept_b.id,
            staff_group=StaffGroup.FRONTLINE,
        )
        session.add(emp)
        session.flush()

        cust = Customer(
            code="CUST-X",
            name="Khách hàng X",
            current_classification=CustomerClassification.C,
        )
        session.add(cust)
        session.flush()

        # Cố tình lệch: debt.division_id = div_a nhưng dept_b thật ra thuộc
        # div_b.
        mismatched_debt = Debt(
            customer_id=cust.id,
            division_id=div_a.id,
            department_id=dept_b.id,
            employee_id=emp.id,
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 2, 1),
            amount=500_000,
        )
        session.add(mismatched_debt)
        session.commit()

        return {
            "debt_id": mismatched_debt.id,
            "div_a_id": div_a.id,
            "div_b_id": div_b.id,
        }


@pytest.mark.parametrize(
    ("aging_days", "expected_bucket"),
    [
        (-5, BUCKET_NOT_DUE),  # due_date ở tương lai so với as_of_date
        (0, BUCKET_NOT_DUE),  # đến hạn đúng ngày as_of_date (aging_days = 0)
        (1, AGING_BUCKETS[0]),  # vừa quá hạn 1 ngày -> "0-30 ngày"
        (30, AGING_BUCKETS[0]),  # biên trên nhóm "0-30 ngày"
        (31, AGING_BUCKETS[1]),  # biên dưới nhóm "31-60 ngày"
        (60, AGING_BUCKETS[1]),  # biên trên nhóm "31-60 ngày"
        (61, AGING_BUCKETS[2]),  # biên dưới nhóm "61-90 ngày"
        (90, AGING_BUCKETS[2]),  # biên trên nhóm "61-90 ngày"
        (91, AGING_BUCKETS[3]),  # biên dưới nhóm "Trên 90 ngày"
    ],
)
def test_compute_aging_bucket_boundaries(aging_days, expected_bucket):
    """`compute_aging_bucket()` trả đúng nhóm ở từng ranh giới ngày (0/1,
    30/31, 60/61, 90/91) theo `aging_days = (as_of_date - due_date).days`."""
    as_of_date = date(2026, 6, 30)
    due_date = as_of_date - timedelta(days=aging_days)

    assert compute_aging_bucket(due_date, as_of_date) == expected_bucket


def test_get_debt_aging_summary_admin_sees_all_divisions(db_engine, debt_org_data):
    """Admin (`scope.unrestricted=True`) thấy tổng công nợ của CẢ 2 Khối,
    không bị lọc theo `department_id`/`employee_id`."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    result = get_debt_aging_summary(
        scope, engine=db_engine, as_of_date=debt_org_data["as_of_date"]
    )

    assert result["amount"].sum() == 3_000_000
    bucket_amounts = dict(zip(result["aging_bucket"], result["amount"], strict=True))
    assert bucket_amounts[AGING_BUCKETS[0]] == 1_000_000  # debt1
    assert bucket_amounts[AGING_BUCKETS[2]] == 2_000_000  # debt2


def test_get_debt_aging_summary_manager_sees_only_own_department(
    db_engine, debt_org_data
):
    """Manager bị lọc trực tiếp theo `Debt.department_id` (mẫu lọc RBAC #3,
    CLAUDE.md mục 7) — chỉ thấy công nợ của Phòng 1, không thấy Phòng 2."""
    scope = _make_scope(role=UserRole.MANAGER, department_id=debt_org_data["dept1_id"])

    result = get_debt_aging_summary(
        scope, engine=db_engine, as_of_date=debt_org_data["as_of_date"]
    )

    assert result["amount"].sum() == 1_000_000
    assert list(result["aging_bucket"]) == [AGING_BUCKETS[0]]


def test_get_debt_aging_summary_manager_without_department_id_is_empty(
    db_engine, debt_org_data
):
    """Manager không xác định được `department_id` (`None`) -> lọc
    fail-safe 0 dòng trong `_apply_scope_filter()` -> hàm trả về
    `DataFrame` rỗng đúng cột (nhánh `df.empty` của
    `get_debt_aging_summary()`)."""
    scope = _make_scope(role=UserRole.MANAGER, department_id=None)

    result = get_debt_aging_summary(
        scope, engine=db_engine, as_of_date=debt_org_data["as_of_date"]
    )

    assert result.empty
    assert list(result.columns) == ["aging_bucket", "debt_count", "amount"]


def test_get_debt_aging_by_org_admin_sees_all_org_rows(db_engine, debt_org_data):
    """Admin thấy đủ 2 dòng (1 dòng / nhân viên / aging_bucket), trải đều
    trên cả 2 Khối đã seed."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    result = get_debt_aging_by_org(
        scope, engine=db_engine, as_of_date=debt_org_data["as_of_date"]
    )

    assert len(result) == 2
    assert set(result["division_id"]) == {
        debt_org_data["div1_id"],
        debt_org_data["div2_id"],
    }


def test_get_debt_aging_by_org_user_sees_only_own_employee(db_engine, debt_org_data):
    """User bị lọc trực tiếp theo `Debt.employee_id` — chỉ thấy dòng của
    chính nhân viên mình, dữ liệu của nhân viên thuộc Khối/Phòng khác bị
    loại trừ hoàn toàn."""
    scope = _make_scope(role=UserRole.USER, employee_id=debt_org_data["emp1_id"])

    result = get_debt_aging_by_org(
        scope, engine=db_engine, as_of_date=debt_org_data["as_of_date"]
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["employee_id"] == debt_org_data["emp1_id"]
    assert row["department_id"] == debt_org_data["dept1_id"]
    assert row["aging_bucket"] == AGING_BUCKETS[0]
    assert row["amount"] == 1_000_000
    assert debt_org_data["emp2_id"] not in result["employee_id"].values


def test_check_division_department_mismatch_detects_mismatch(db_engine):
    """Phát hiện đúng dòng `debt` có `department.division_id !=
    debt.division_id` — ca lỗi dữ liệu cố tình seed qua
    `_seed_mismatched_debt()`."""
    seeded = _seed_mismatched_debt(db_engine)

    result = check_division_department_mismatch(engine=db_engine)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["debt_id"] == seeded["debt_id"]
    assert row["debt_division_id"] == seeded["div_a_id"]
    assert row["department_actual_division_id"] == seeded["div_b_id"]


def test_check_division_department_mismatch_no_mismatch_for_consistent_data(
    db_engine, debt_org_data
):
    """Dữ liệu `debt` nhất quán (`division_id`/`department_id` khớp đúng
    phân cấp thật, như `debt_org_data`) -> không phát hiện dòng lệch nào,
    trả về `DataFrame` rỗng."""
    result = check_division_department_mismatch(engine=db_engine)

    assert result.empty
