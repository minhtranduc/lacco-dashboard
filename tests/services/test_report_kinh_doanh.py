"""Test `src/services/report_kinh_doanh.py` — báo cáo Kinh doanh (doanh
thu/lãi lỗ theo dịch vụ/khách hàng/Khối-Phòng-NV + xu hướng theo thời gian).

Theo CLAUDE.md mục 6 (RBAC) + mục 7 (2 công thức đã chốt Tuần 4), 3 điều
BẮT BUỘC phải test cho MỌI hàm `get_revenue_profit_by_*`/`_trend`:
1. Admin (`scope.unrestricted=True`) thấy TOÀN BỘ dữ liệu, không lọc
   `customer_id`.
2. Manager/User (`scope.unrestricted=False`) CHỈ thấy dữ liệu trong
   `scope.customer_ids` (đã tính qua `compute_data_scope()` thật, không tự
   dựng list id tay).
3. Đơn `sales_order.status == STATUS_CANCELLED` ("Huỷ") LOẠI TRỪ khỏi mọi
   tổng doanh thu/lãi lỗ (COO xác nhận 07/09/2026, bước 4.1) nhưng VẪN được
   đếm riêng qua `get_cancelled_orders_summary()`.

Dùng fixture `db_engine`/`seeded_scope_data` từ `tests/conftest.py` (SQLite
in-memory qua `StaticPool`, KHÔNG kết nối MySQL "lacco" thật — xem
`tests/auth/test_scope.py` cho pattern gốc). Scope Admin/Manager dựng qua
`compute_data_scope()` thật (không tự construct `DataScope` tay) TRỪ 2 test
không cần chạm DB thật (granularity không hợp lệ, scope rỗng) — ở đó
`DataScope` được dựng tay trực tiếp vì mục đích chỉ là kiểm tra nhánh sớm
của hàm, không cần user/employee thật trong DB.

*** BLOCKER dialect MySQL/SQLite đã phát hiện khi viết test này (xem chi
tiết ở fixture `sqlite_date_format` bên dưới) *** — `get_revenue_profit_
trend()` dùng `func.date_format(...)` (cú pháp riêng của MySQL). SQLite
không có hàm `date_format` built-in, đã xác minh trực tiếp:
`sqlite3.OperationalError: no such function: date_format` khi gọi thẳng
trên `db_engine`. Đã grep toàn bộ `src/`/`tests/` — không có workaround có
sẵn cho vấn đề dialect này (các module khác dùng `date_format` tương tự,
VD `report_chi_phi.py`, đều chưa có test). Xử lý cục bộ trong file test
này bằng cách đăng ký hàm Python tương đương qua API chuẩn
`sqlite3.Connection.create_function` — KHÔNG sửa `tests/conftest.py`.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from src.auth.scope import DataScope, compute_data_scope
from src.db.models.business import SalesOrder
from src.db.models.dimension import Customer, Department, Division, Employee, Service
from src.db.models.enums import CustomerClassification, StaffGroup, UserRole
from src.db.models.security import User
from src.services import report_kinh_doanh
from src.services.report_kinh_doanh import (
    STATUS_CANCELLED,
    get_cancelled_orders_summary,
    get_revenue_profit_by_customer,
    get_revenue_profit_by_org,
    get_revenue_profit_by_service,
    get_revenue_profit_trend,
)

# ---------------------------------------------------------------------------
# Helpers dùng chung trong file (lặp lại cục bộ theo pattern
# `tests/auth/test_scope.py::_create_user` — không có module helper dùng
# chung giữa các thư mục test trong repo hiện tại).
# ---------------------------------------------------------------------------


def _create_user(
    engine, *, username: str, role: UserRole, employee_id: int | None
) -> int:
    """Tạo 1 user tối thiểu qua ORM để gọi `compute_data_scope()` thật —
    `password_hash` là placeholder vì hàm này không kiểm tra mật khẩu."""
    with Session(engine) as session:
        user = User(
            username=username,
            password_hash="$2b$dummy-hash-not-verified",
            role=role,
            employee_id=employee_id,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def _empty_scope(*, role: UserRole = UserRole.USER) -> DataScope:
    """Dựng tay 1 `DataScope` rỗng (`customer_ids=frozenset()`,
    `unrestricted=False`) — dùng CHỈ cho 2 nhóm test không cần chạm DB thật
    (nhánh early-return của mỗi hàm, và test `ValueError` của granularity):
    tương đương kết quả `compute_data_scope()` trả về cho User/Manager
    không có `employee_id` (xem `seeded_scope_data`/`test_scope.py`), nhưng
    không cần tạo user thật trong DB vì test không quan tâm khâu tính scope."""
    return DataScope(
        user_id=1,
        username="orphan",
        role=role,
        employee_id=None,
        department_id=None,
        division_id=None,
        classification_hint=None,
        customer_ids=frozenset(),
        unrestricted=False,
        description="test: scope rỗng",
    )


def _sqlite_date_format(value, fmt: str):
    """Triển khai SQLite tương đương cho ĐÚNG 2 pattern `func.date_format`
    mà `get_revenue_profit_trend()` dùng (`"%Y-%m-01"`/`"%x-%v"`) — không
    mô phỏng toàn bộ `DATE_FORMAT()` của MySQL, xem fixture
    `sqlite_date_format` để biết lý do cần hàm này."""
    if value is None:
        return None
    parsed = date.fromisoformat(value) if isinstance(value, str) else value
    if fmt == "%Y-%m-01":
        return parsed.strftime("%Y-%m-01")
    if fmt == "%x-%v":
        iso_year, iso_week, _ = parsed.isocalendar()
        return f"{iso_year:04d}-{iso_week:02d}"
    raise ValueError(f"Pattern date_format chưa hỗ trợ trong test: {fmt!r}")


@pytest.fixture()
def sqlite_date_format(db_engine):
    """Đăng ký hàm SQLite `date_format` tương đương (chỉ 2 pattern module
    nguồn dùng) lên connection duy nhất của `db_engine`.

    *** LÝ DO CẦN FIXTURE NÀY (blocker dialect đã xác minh) ***:
    `get_revenue_profit_trend()` (src/services/report_kinh_doanh.py) gọi
    `func.date_format(order_date, "%Y-%m-01" | "%x-%v")` — cú pháp hàm
    `DATE_FORMAT()` riêng của MySQL (dialect thật của dự án, xem
    `db_connection.py::build_mysql_url()`). SQLite KHÔNG có hàm
    `date_format` built-in — chạy thẳng statement này lên `db_engine` (SQLite
    in-memory của `tests/conftest.py`) raise
    `sqlite3.OperationalError: no such function: date_format` (đã xác minh
    trực tiếp bằng script độc lập trước khi viết fixture này). Đã grep toàn
    `src/`/`tests/` cho `create_function`/workaround dialect có sẵn trong
    repo — không có, đây là lần đầu có test chạm `get_revenue_profit_trend`.

    Workaround: `sqlite3.Connection.create_function` là API CHUẨN của
    module `sqlite3` (không phải hack riêng của SQLAlchemy) để đăng ký 1
    hàm Python làm hàm SQL cho connection hiện tại. `db_engine` dùng
    `StaticPool` (xem `tests/conftest.py`) -> chỉ có ĐÚNG 1 connection
    DBAPI cho toàn bộ engine trong suốt vòng đời fixture, nên đăng ký 1 lần
    ở đây là đủ cho mọi query sau đó trong cùng test. `raw.close()` ở cuối
    KHÔNG đóng connection thật (đặc tính của `StaticPool` — chỉ trả về
    pool), đã xác minh bằng cách query lại thành công sau khi gọi `close()`.
    KHÔNG sửa `tests/conftest.py` — toàn bộ workaround nằm gọn trong file
    test này.
    """
    raw = db_engine.raw_connection()
    try:
        raw.dbapi_connection.create_function("date_format", 2, _sqlite_date_format)
    finally:
        raw.close()
    return db_engine


@pytest.fixture()
def admin_scope(db_engine, seeded_scope_data):
    """Scope Admin THẬT (qua `compute_data_scope()`, không dựng tay) —
    `unrestricted=True`, thấy toàn bộ khách hàng seed sẵn trong
    `seeded_scope_data` (CLAUDE.md mục 6: Admin luôn unrestricted)."""
    user_id = _create_user(
        db_engine, username="admin_kd", role=UserRole.ADMIN, employee_id=None
    )
    return compute_data_scope(user_id, engine=db_engine)


@pytest.fixture()
def manager_scope(db_engine, seeded_scope_data):
    """Scope Manager THẬT (qua `compute_data_scope()`) — Trưởng Phòng Kinh
    doanh A (`emp_manager_id`), chỉ thấy `customer_x`/`customer_y` (đơn của
    Phòng A), KHÔNG thấy `customer_z` (Phòng B) — xem
    `tests/auth/test_scope.py::test_manager_scope_is_by_department`."""
    user_id = _create_user(
        db_engine,
        username="manager_kd",
        role=UserRole.MANAGER,
        employee_id=seeded_scope_data["emp_manager_id"],
    )
    return compute_data_scope(user_id, engine=db_engine)


@pytest.fixture()
def seeded_cancelled_order(db_engine, seeded_scope_data):
    """Seed thêm 1 `SalesOrder` với `status=STATUS_CANCELLED` (copy trực
    tiếp từ `report_kinh_doanh.STATUS_CANCELLED` — KHÔNG gõ lại ký tự
    tiếng Việt để tránh lệch Unicode NFC/NFD, xem docstring `STATUS_
    CANCELLED` trong module nguồn) với `revenue=9999` — 1 giá trị đặc thù,
    dễ nhận biết nếu lỡ bị cộng nhầm vào tổng doanh thu hợp lệ (6000, xem
    `seeded_scope_data`). Đơn này thuộc `customer_x`/`emp_user`/cùng
    `service` đã seed sẵn, cùng tháng 1/2026 với 3 đơn hợp lệ, để test
    đúng việc LOẠI TRỪ (không phải vô tình khác nhóm/khác kỳ)."""
    with Session(db_engine) as session:
        cancelled_order = SalesOrder(
            customer_id=seeded_scope_data["customer_x_id"],
            service_id=seeded_scope_data["service_id"],
            employee_id=seeded_scope_data["emp_user_id"],
            order_date=date(2026, 1, 15),
            status=STATUS_CANCELLED,
            revenue=9999,
            order_cost=1234,
            invoice_status="Chưa xuất",
        )
        session.add(cancelled_order)
        session.commit()
        session.refresh(cancelled_order)
        return cancelled_order.id


# ---------------------------------------------------------------------------
# get_revenue_profit_by_service — Admin vs Manager (restricted)
# ---------------------------------------------------------------------------


def test_get_revenue_profit_by_service_unrestricted_sums_all_customers(
    db_engine, seeded_scope_data, admin_scope
):
    """Admin (`unrestricted=True`) -> gộp CẢ 3 đơn (customer_x/y/z, cùng 1
    Service seed sẵn) thành 1 dòng dịch vụ, không lọc theo customer_id."""
    df = get_revenue_profit_by_service(admin_scope, engine=db_engine)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["service_id"] == seeded_scope_data["service_id"]
    assert row["order_count"] == 3
    assert row["revenue"] == 6000.0
    assert row["order_cost"] == 4300.0
    assert row["profit"] == 1700.0
    assert row["profit_margin"] == pytest.approx(1700.0 / 6000.0)


def test_get_revenue_profit_by_service_restricted_scope_only_own_orders(
    db_engine, seeded_scope_data, manager_scope
):
    """Manager (Phòng A) -> chỉ gộp order_x + order_y, LOẠI order_z (khách
    hàng ngoài `scope.customer_ids` của Phòng A)."""
    df = get_revenue_profit_by_service(manager_scope, engine=db_engine)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["order_count"] == 2
    assert row["revenue"] == 3000.0
    assert row["order_cost"] == 2300.0
    assert row["profit"] == 700.0


# ---------------------------------------------------------------------------
# get_revenue_profit_by_customer — Admin vs Manager (restricted) + top_n
# ---------------------------------------------------------------------------


def test_get_revenue_profit_by_customer_unrestricted_sees_all_three(
    db_engine, seeded_scope_data, admin_scope
):
    """Admin -> 3 dòng khách hàng (X/Y/Z), tổng revenue/profit khớp tổng
    của cả 3 đơn seed sẵn."""
    df = get_revenue_profit_by_customer(admin_scope, engine=db_engine)

    assert set(df["customer_id"]) == {
        seeded_scope_data["customer_x_id"],
        seeded_scope_data["customer_y_id"],
        seeded_scope_data["customer_z_id"],
    }
    assert df["revenue"].sum() == 6000.0
    assert df["profit"].sum() == 1700.0


def test_get_revenue_profit_by_customer_restricted_excludes_out_of_scope_customer(
    db_engine, seeded_scope_data, manager_scope
):
    """Manager (Phòng A) -> chỉ customer_x/customer_y, `customer_z` (Phòng
    B) không xuất hiện trong kết quả."""
    df = get_revenue_profit_by_customer(manager_scope, engine=db_engine)

    assert set(df["customer_id"]) == {
        seeded_scope_data["customer_x_id"],
        seeded_scope_data["customer_y_id"],
    }
    assert seeded_scope_data["customer_z_id"] not in set(df["customer_id"])
    assert df["revenue"].sum() == 3000.0


def test_get_revenue_profit_by_customer_top_n_truncates_to_highest_revenue(
    db_engine, seeded_scope_data, admin_scope
):
    """`top_n=1` -> chỉ giữ đúng 1 khách hàng có `revenue` cao nhất
    (customer_z, revenue=3000) — DataFrame đã sort giảm dần theo revenue."""
    df = get_revenue_profit_by_customer(admin_scope, engine=db_engine, top_n=1)

    assert len(df) == 1
    assert df.iloc[0]["customer_id"] == seeded_scope_data["customer_z_id"]
    assert df.iloc[0]["revenue"] == 3000.0


# ---------------------------------------------------------------------------
# get_revenue_profit_by_org — Admin vs Manager (restricted) + hierarchy join
# ---------------------------------------------------------------------------


def test_get_revenue_profit_by_org_unrestricted_joins_full_hierarchy(
    db_engine, seeded_scope_data, admin_scope
):
    """Admin -> 3 dòng (1/nhân viên), cột Khối/Phòng/NV join đúng:
    emp_user + emp_manager thuộc Phòng A, emp_outsider thuộc Phòng B, cả 3
    cùng 1 Khối seed sẵn."""
    df = get_revenue_profit_by_org(admin_scope, engine=db_engine)

    assert len(df) == 3
    by_employee = df.set_index("employee_id")
    assert (
        by_employee.loc[seeded_scope_data["emp_user_id"], "department_id"]
        == seeded_scope_data["dept_a_id"]
    )
    assert (
        by_employee.loc[seeded_scope_data["emp_manager_id"], "department_id"]
        == seeded_scope_data["dept_a_id"]
    )
    assert (
        by_employee.loc[seeded_scope_data["emp_outsider_id"], "department_id"]
        == seeded_scope_data["dept_b_id"]
    )
    assert (by_employee["division_id"] == seeded_scope_data["division_id"]).all()
    assert df["revenue"].sum() == 6000.0


def test_get_revenue_profit_by_org_restricted_excludes_outsider_employee(
    db_engine, seeded_scope_data, manager_scope
):
    """Manager (Phòng A) -> chỉ 2 dòng (emp_manager, emp_user), KHÔNG có
    emp_outsider (Phòng B, đơn của khách hàng ngoài scope)."""
    df = get_revenue_profit_by_org(manager_scope, engine=db_engine)

    assert set(df["employee_id"]) == {
        seeded_scope_data["emp_manager_id"],
        seeded_scope_data["emp_user_id"],
    }
    assert df["revenue"].sum() == 3000.0


# ---------------------------------------------------------------------------
# get_revenue_profit_trend — granularity="month"/"week" + ValueError
# ---------------------------------------------------------------------------


def test_get_revenue_profit_trend_month_granularity_groups_by_month(
    db_engine, sqlite_date_format, seeded_scope_data, admin_scope
):
    """`granularity="month"`: 3 đơn seed sẵn cùng tháng 1/2026 -> gộp về 1
    kỳ `period="2026-01-01"` (dtype `datetime64`, qua `pd.to_datetime`)."""
    df = get_revenue_profit_trend(admin_scope, engine=db_engine, granularity="month")

    assert len(df) == 1
    assert df.loc[0, "period"] == pd.Timestamp("2026-01-01")
    assert df.loc[0, "revenue"] == 6000.0
    assert df.loc[0, "profit"] == 1700.0


def test_get_revenue_profit_trend_week_granularity_uses_iso_week_format(
    db_engine, sqlite_date_format, seeded_scope_data, admin_scope
):
    """`granularity="week"`: cột `period` dạng chuỗi ISO week zero-padded
    `"YYYY-Www"` (VD `"2026-05"` theo đề bài). order_x (10/01) và order_y
    (11/01) rơi vào cùng tuần ISO 2026-W02 -> gộp chung; order_z (12/01)
    rơi vào tuần ISO 2026-W03 -> tách riêng (đã xác minh bằng
    `date.isocalendar()`)."""
    df = get_revenue_profit_trend(admin_scope, engine=db_engine, granularity="week")

    assert list(df["period"]) == ["2026-02", "2026-03"]
    week_02 = df.loc[df["period"] == "2026-02"].iloc[0]
    week_03 = df.loc[df["period"] == "2026-03"].iloc[0]
    assert week_02["revenue"] == 3000.0
    assert week_02["profit"] == 700.0
    assert week_03["revenue"] == 3000.0
    assert week_03["profit"] == 1000.0


def test_get_revenue_profit_trend_invalid_granularity_raises_value_error(db_engine):
    """`granularity` ngoài `"month"`/`"week"` -> `ValueError`. Kiểm tra
    xảy ra TRƯỚC khi chạm DB (hàm raise ở dòng đầu, trước khi resolve
    engine/scope) nên không cần seed dữ liệu hay `sqlite_date_format`."""
    scope = _empty_scope(role=UserRole.ADMIN)

    with pytest.raises(ValueError):
        get_revenue_profit_trend(scope, engine=db_engine, granularity="quarter")


# ---------------------------------------------------------------------------
# Loại trừ đơn "Huỷ" (STATUS_CANCELLED) — CLAUDE.md mục 7, bước 4.1
# ---------------------------------------------------------------------------


def test_cancelled_orders_excluded_from_revenue_by_service(
    db_engine, admin_scope, seeded_cancelled_order
):
    """Đơn Huỷ (revenue=9999, cùng Service với 3 đơn hợp lệ) KHÔNG được
    cộng vào tổng của `get_revenue_profit_by_service`."""
    df = get_revenue_profit_by_service(admin_scope, engine=db_engine)

    assert len(df) == 1
    assert df.iloc[0]["revenue"] == 6000.0
    assert 9999.0 not in df["revenue"].to_numpy()


def test_cancelled_orders_excluded_from_revenue_by_customer(
    db_engine, admin_scope, seeded_cancelled_order
):
    """Đơn Huỷ thuộc `customer_x` KHÔNG được cộng vào revenue của
    `customer_x` (hay bất kỳ dòng nào khác) trong
    `get_revenue_profit_by_customer`."""
    df = get_revenue_profit_by_customer(admin_scope, engine=db_engine)

    assert df["revenue"].sum() == 6000.0
    assert 9999.0 not in df["revenue"].to_numpy()


def test_cancelled_orders_excluded_from_revenue_by_org(
    db_engine, admin_scope, seeded_cancelled_order
):
    """Đơn Huỷ (nhân viên `emp_user`) KHÔNG được cộng vào tổng của
    `get_revenue_profit_by_org`."""
    df = get_revenue_profit_by_org(admin_scope, engine=db_engine)

    assert df["revenue"].sum() == 6000.0
    assert 9999.0 not in df["revenue"].to_numpy()


def test_cancelled_orders_excluded_from_revenue_trend(
    db_engine, sqlite_date_format, admin_scope, seeded_cancelled_order
):
    """Đơn Huỷ (order_date 15/01/2026, cùng tháng 1/2026 với 3 đơn hợp lệ)
    KHÔNG được cộng vào kỳ `"2026-01-01"` của `get_revenue_profit_trend`
    (`granularity="month"`)."""
    df = get_revenue_profit_trend(admin_scope, engine=db_engine, granularity="month")

    assert len(df) == 1
    assert df.loc[0, "revenue"] == 6000.0


def test_cancelled_orders_summary_counts_only_cancelled_orders(
    db_engine, admin_scope, seeded_cancelled_order
):
    """`get_cancelled_orders_summary` là hàm DUY NHẤT phải ĐẾM đơn Huỷ
    (ngược lại hoàn toàn với 4 test loại trừ ở trên) — 1 đơn, revenue=9999,
    KHÔNG lẫn với 3 đơn hợp lệ (6000)."""
    result = get_cancelled_orders_summary(admin_scope, engine=db_engine)

    assert result == {"cancelled_order_count": 1, "cancelled_revenue": 9999.0}


# ---------------------------------------------------------------------------
# _add_profit_margin_column — chia cho 0 trả 0.0, không NaN/lỗi
# ---------------------------------------------------------------------------


def test_profit_margin_is_zero_when_revenue_is_zero_not_nan(db_engine):
    """1 nhóm (dịch vụ) có `revenue=0` -> `profit_margin` phải là `0.0`
    tường minh, KHÔNG phải `NaN` hay lỗi chia cho 0 — xem quyết định trong
    docstring `_add_profit_margin_column` (module nguồn)."""
    with Session(db_engine) as session:
        division = Division(name="Khối Zero")
        session.add(division)
        session.flush()

        department = Department(name="Phòng Zero", division_id=division.id)
        session.add(department)
        session.flush()

        employee = Employee(
            full_name="Nhân viên Zero",
            department_id=department.id,
            staff_group=StaffGroup.FRONTLINE,
        )
        service = Service(name="Dịch vụ Zero")
        session.add_all([employee, service])
        session.flush()

        customer = Customer(
            code="CUST-ZERO",
            name="Khách hàng Zero",
            current_classification=CustomerClassification.C,
        )
        session.add(customer)
        session.flush()

        order = SalesOrder(
            customer_id=customer.id,
            service_id=service.id,
            employee_id=employee.id,
            order_date=date(2026, 2, 1),
            status="Đang vận chuyển",
            revenue=0,
            order_cost=0,
            invoice_status="Chưa xuất",
        )
        session.add(order)
        session.commit()
        customer_id = customer.id

    scope = DataScope(
        user_id=1,
        username="admin_zero",
        role=UserRole.ADMIN,
        employee_id=None,
        department_id=None,
        division_id=None,
        classification_hint=None,
        customer_ids=frozenset({customer_id}),
        unrestricted=True,
        description="test: Admin unrestricted",
    )

    df = get_revenue_profit_by_service(scope, engine=db_engine)

    assert len(df) == 1
    assert df.loc[0, "revenue"] == 0.0
    assert df.loc[0, "profit"] == 0.0
    assert df.loc[0, "profit_margin"] == 0.0
    assert not pd.isna(df.loc[0, "profit_margin"])


# ---------------------------------------------------------------------------
# Empty-scope edge case — User không có employee_id -> DataFrame/dict rỗng,
# KHÔNG chạm DB (early return TRƯỚC khi mở Session).
# ---------------------------------------------------------------------------

_EMPTY_SCOPE_CASES = [
    pytest.param(
        get_revenue_profit_by_service,
        {},
        [
            "service_id",
            "service_name",
            "order_count",
            "revenue",
            "order_cost",
            "profit",
            "profit_margin",
        ],
        id="by_service",
    ),
    pytest.param(
        get_revenue_profit_by_customer,
        {},
        [
            "customer_id",
            "customer_code",
            "customer_name",
            "order_count",
            "revenue",
            "order_cost",
            "profit",
            "profit_margin",
        ],
        id="by_customer",
    ),
    pytest.param(
        get_revenue_profit_by_org,
        {},
        [
            "division_id",
            "division_name",
            "department_id",
            "department_name",
            "employee_id",
            "employee_name",
            "order_count",
            "revenue",
            "order_cost",
            "profit",
            "profit_margin",
        ],
        id="by_org",
    ),
    pytest.param(
        get_revenue_profit_trend,
        {"granularity": "month"},
        ["period", "revenue", "profit"],
        id="trend_month",
    ),
]


@pytest.mark.parametrize(
    ("service_func", "kwargs", "expected_columns"), _EMPTY_SCOPE_CASES
)
def test_empty_scope_returns_empty_dataframe_without_querying_db(
    monkeypatch, db_engine, service_func, kwargs, expected_columns
):
    """User không có `employee_id` -> `scope.customer_ids` rỗng và
    `unrestricted=False` -> trả về DataFrame rỗng ĐÚNG cột, và KHÔNG được
    mở `Session`/chạm DB (patch `Session` trong module nguồn để assert
    fail nếu bị gọi — xác nhận đây thực sự là early-return, không phải
    query trả về 0 dòng)."""

    def _session_should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "Session(engine) không được gọi khi scope rỗng (phải early-return)."
        )

    monkeypatch.setattr(report_kinh_doanh, "Session", _session_should_not_be_called)

    scope = _empty_scope(role=UserRole.USER)

    df = service_func(scope, engine=db_engine, **kwargs)

    assert df.empty
    assert list(df.columns) == expected_columns


def test_empty_scope_cancelled_summary_returns_zeros_without_querying_db(
    monkeypatch, db_engine
):
    """Tương tự test trên, nhưng cho `get_cancelled_orders_summary` (trả
    `dict`, không phải `DataFrame`) — vẫn phải early-return trước khi mở
    `Session`."""

    def _session_should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "Session(engine) không được gọi khi scope rỗng (phải early-return)."
        )

    monkeypatch.setattr(report_kinh_doanh, "Session", _session_should_not_be_called)

    scope = _empty_scope(role=UserRole.USER)

    result = get_cancelled_orders_summary(scope, engine=db_engine)

    assert result == {"cancelled_order_count": 0, "cancelled_revenue": 0.0}
