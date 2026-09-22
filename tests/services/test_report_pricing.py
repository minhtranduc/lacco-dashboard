"""Test `src/services/report_pricing.py` — báo cáo Pricing (2 báo cáo con:
"Thành đơn" và "Nhà cung cấp"), cả 2 đã "Đã rõ" theo
`.claude/rules/trang-thai-yeu-cau.md`.

RBAC ở module này KHÁC với `report_kinh_doanh.py`/`report_khach_hang.py`
(CLAUDE.md mục 6, mẫu lọc RBAC số 1): `price_request`/`supplier_evaluation`
không có "khách hàng" làm chủ thể phân quyền tự nhiên
(`price_request.customer_id` nullable, `supplier_evaluation` không có cột
khách hàng nào), nên module lọc theo NHÂN VIÊN PHỤ TRÁCH — đọc trực tiếp
`DataScope.department_id` (Manager) / `DataScope.employee_id` (User) từ
`src/auth/scope.py`, KHÔNG dùng `DataScope.customer_ids` như các module
"Kinh doanh"/"Khách hàng". Đã xác minh trực tiếp từ code
`_apply_org_scope_filter` trong `report_pricing.py` trước khi viết test
này.

Dùng fixture `db_engine` + `seeded_scope_data` có sẵn ở `tests/conftest.py`
(SQLite in-memory qua `engine=`, KHÔNG đụng MySQL "lacco" thật) — 1
Division, 2 Department (A, B), 3 Employee (`emp_manager`/`emp_user` ở
Department A, `emp_outsider` ở Department B). Test trong file này seed
thêm riêng dữ liệu `PriceRequest`/`Supplier`/`SupplierEvaluation` gắn với
3 nhân viên đó (fixture `seeded_pricing_data` cục bộ, không sửa
`tests/conftest.py`).

`DataScope` dùng trong test được tạo qua `compute_data_scope()` thật (tạo
`User` ORM thật rồi gọi hàm thật) — giống quy ước ở `tests/auth/
test_scope.py` — thay vì tự dựng `DataScope(...)` thủ công, để test đi qua
đúng luồng thật (trừ test `_scope_is_empty` ở cuối file, cần dựng thủ công
vì test hàm thuần theo tổ hợp field không dễ tái tạo qua DB).

Ghi chú phạm vi: quy tắc loại trừ đơn `sales_order.status = "Huỷ"` khỏi
tổng doanh thu/lãi lỗ (CLAUDE.md mục 7) áp dụng cho `sales_order`, KHÔNG áp
dụng cho `price_request`/`supplier_evaluation` — 2 bảng này không có cột
`status` kiểu đó và "Thành đơn"/"Nhà cung cấp" không phải báo cáo doanh
thu/lãi lỗ. Xác nhận từ code (`report_pricing.py` không có logic loại trừ
nào tương tự) — không áp cho test nào trong file này.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.scope import DataScope, compute_data_scope
from src.db.models.business import PriceRequest, SalesOrder, SupplierEvaluation
from src.db.models.dimension import Supplier
from src.db.models.enums import UserRole
from src.db.models.security import User
from src.services.report_pricing import (
    _CUSTOMER_PLACEHOLDER_LABEL,
    _scope_is_empty,
    get_supplier_list,
    get_supplier_score_by_supplier,
    get_supplier_score_trend,
    get_win_rate_by_customer,
    get_win_rate_by_org,
    get_win_rate_trend,
)


def _create_user(
    engine, *, username: str, role: UserRole, employee_id: int | None
) -> int:
    """Tạo 1 user tối thiểu qua ORM (giống `tests/auth/test_scope.py`) —
    `password_hash` là placeholder vì `compute_data_scope()` không kiểm tra
    mật khẩu."""
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


def _register_sqlite_date_format(engine) -> None:
    """Đăng ký hàm `date_format(value, fmt)` tương thích MySQL lên connection
    SQLite in-memory dùng cho test — `_period_expr` trong `report_pricing.py`
    dùng `func.date_format(...)` (đúng dialect MySQL thật của
    `src/services/db_connection.py`), nhưng SQLite KHÔNG có hàm này sẵn
    (`OperationalError: no such function: date_format`, đã xác minh khi viết
    file test này). CHỈ hỗ trợ đúng 2 định dạng `_period_expr` thực sự dùng
    (`"%Y-%m-01"`, `"%x-%v"` — tuần ISO). Mẫu giống hệt
    `tests/services/test_report_don_hang.py::_register_sqlite_date_format`,
    lặp lại cục bộ để file test độc lập — thuần tuý hạ tầng test, không sửa
    code nguồn."""

    def _date_format(value: str | date | None, fmt: str) -> str | None:
        if value is None:
            return None
        parsed = value if isinstance(value, date) else date.fromisoformat(value)
        if fmt == "%Y-%m-01":
            return parsed.strftime("%Y-%m-01")
        if fmt == "%x-%v":
            iso_year, iso_week, _ = parsed.isocalendar()
            return f"{iso_year:04d}-{iso_week:02d}"
        raise ValueError(f"Định dạng date_format chưa hỗ trợ trong test: {fmt!r}")

    raw_connection = engine.raw_connection()
    raw_connection.driver_connection.create_function("date_format", 2, _date_format)


def _admin_scope(engine) -> DataScope:
    user_id = _create_user(
        engine, username="admin-pricing", role=UserRole.ADMIN, employee_id=None
    )
    return compute_data_scope(user_id, engine=engine)


def _manager_scope(engine, *, employee_id: int) -> DataScope:
    user_id = _create_user(
        engine,
        username="manager-pricing",
        role=UserRole.MANAGER,
        employee_id=employee_id,
    )
    return compute_data_scope(user_id, engine=engine)


def _user_scope(engine, *, employee_id: int) -> DataScope:
    user_id = _create_user(
        engine, username="user-pricing", role=UserRole.USER, employee_id=employee_id
    )
    return compute_data_scope(user_id, engine=engine)


@pytest.fixture()
def seeded_pricing_data(db_engine, seeded_scope_data):
    """Seed `PriceRequest`/`Supplier`/`SupplierEvaluation` gắn với 3 nhân
    viên của `seeded_scope_data` (2 ở Department A — `emp_manager`,
    `emp_user`; 1 ở Department B — `emp_outsider`).

    `PriceRequest` của `emp_user` (4 dòng, dùng để test công thức
    win_rate và cột `_won_expr`):
    - req1: `customer_id=customer_x`, `is_won=True` -> chốt qua `is_won`.
    - req2: `customer_id=customer_x`, `is_won=False`,
      `sales_order_id=order_x` (đã seed sẵn ở `seeded_scope_data`) -> chốt
      qua nhánh OR thứ 2 của `_won_expr` (`sales_order_id IS NOT NULL`).
    - req3: `customer_id=None` (khách hàng tiềm năng/chưa có mã) ->
      dùng để test `_CUSTOMER_PLACEHOLDER_LABEL`.
    - req4: `customer_id=customer_x`, `is_won=False`, không có
      `sales_order_id` -> KHÔNG chốt.
    => `emp_user`: 4 request, 3 chốt -> `win_rate = 0.75`.

    `PriceRequest` của `emp_manager` (2 dòng, cùng Department A với
    `emp_user`): 1 chốt, 1 không -> `win_rate = 0.5`.

    `PriceRequest` của `emp_outsider` (Department B, "người ngoài" so với
    Department A): 2 dòng, cả 2 đều chốt -> `win_rate = 1.0`.

    `SupplierEvaluation`: `sup_alpha` được `emp_user` (Dept A) đánh giá 2
    lần (80, 90 -> avg 85), `sup_beta` được `emp_outsider` (Dept B) đánh
    giá 1 lần (60) -> dùng để test RBAC Manager Dept A chỉ thấy `sup_alpha`.
    """
    with Session(db_engine) as session:
        sup_alpha = Supplier(name="NCC Alpha")
        sup_beta = Supplier(name="NCC Beta")
        session.add_all([sup_alpha, sup_beta])
        session.flush()

        service_id = seeded_scope_data["service_id"]
        emp_user_id = seeded_scope_data["emp_user_id"]
        emp_manager_id = seeded_scope_data["emp_manager_id"]
        emp_outsider_id = seeded_scope_data["emp_outsider_id"]
        customer_x_id = seeded_scope_data["customer_x_id"]
        customer_y_id = seeded_scope_data["customer_y_id"]
        customer_z_id = seeded_scope_data["customer_z_id"]

        price_requests = [
            # emp_user (Department A) -> 4 request, 3 chốt, win_rate=0.75.
            PriceRequest(
                service_id=service_id,
                employee_id=emp_user_id,
                customer_id=customer_x_id,
                request_date=date(2026, 1, 5),
                is_won=True,
                sales_order_id=None,
            ),
            PriceRequest(
                service_id=service_id,
                employee_id=emp_user_id,
                customer_id=customer_x_id,
                request_date=date(2026, 1, 20),
                is_won=False,
                sales_order_id=None,
            ),
            PriceRequest(
                service_id=service_id,
                employee_id=emp_user_id,
                customer_id=None,
                request_date=date(2026, 2, 3),
                is_won=True,
                sales_order_id=None,
            ),
            PriceRequest(
                service_id=service_id,
                employee_id=emp_user_id,
                customer_id=customer_x_id,
                request_date=date(2026, 2, 10),
                is_won=False,
                sales_order_id=None,
            ),
            # emp_manager (Department A) -> 2 request, 1 chốt, win_rate=0.5.
            PriceRequest(
                service_id=service_id,
                employee_id=emp_manager_id,
                customer_id=customer_y_id,
                request_date=date(2026, 1, 8),
                is_won=True,
                sales_order_id=None,
            ),
            PriceRequest(
                service_id=service_id,
                employee_id=emp_manager_id,
                customer_id=customer_y_id,
                request_date=date(2026, 1, 9),
                is_won=False,
                sales_order_id=None,
            ),
            # emp_outsider (Department B) -> 2 request, cả 2 chốt, win_rate=1.0.
            PriceRequest(
                service_id=service_id,
                employee_id=emp_outsider_id,
                customer_id=customer_z_id,
                request_date=date(2026, 1, 15),
                is_won=True,
                sales_order_id=None,
            ),
            PriceRequest(
                service_id=service_id,
                employee_id=emp_outsider_id,
                customer_id=customer_z_id,
                request_date=date(2026, 1, 16),
                is_won=True,
                sales_order_id=None,
            ),
        ]
        session.add_all(price_requests)
        session.flush()

        # req2 của emp_user cần sales_order_id trỏ tới order_x đã seed sẵn
        # ở seeded_scope_data (gán sau khi flush để có id request rõ ràng
        # theo thứ tự khai báo ở trên — req2 là phần tử thứ 2, index 1).
        price_requests[1].sales_order_id = _order_x_id(session, employee_id=emp_user_id)

        evaluations = [
            SupplierEvaluation(
                supplier_id=sup_alpha.id,
                service_id=service_id,
                employee_id=emp_user_id,
                period=date(2026, 1, 15),
                score=80,
            ),
            SupplierEvaluation(
                supplier_id=sup_alpha.id,
                service_id=service_id,
                employee_id=emp_user_id,
                period=date(2026, 2, 15),
                score=90,
            ),
            SupplierEvaluation(
                supplier_id=sup_beta.id,
                service_id=service_id,
                employee_id=emp_outsider_id,
                period=date(2026, 1, 20),
                score=60,
            ),
        ]
        session.add_all(evaluations)
        session.commit()

        return {
            "sup_alpha_id": sup_alpha.id,
            "sup_beta_id": sup_beta.id,
        }


def _order_x_id(session: Session, *, employee_id: int) -> int:
    """Lấy id của `order_x` đã seed sẵn ở `seeded_scope_data` — nhận diện
    qua `employee_id` (order_x là đơn duy nhất gắn với `emp_user` trong dữ
    liệu seed gốc) — dùng để test nhánh `sales_order_id IS NOT NULL` của
    `_won_expr` mà không cần tạo thêm `SalesOrder` mới."""
    stmt = select(SalesOrder).where(SalesOrder.employee_id == employee_id)
    order = session.execute(stmt).scalars().first()
    assert order is not None, "order_x không tìm thấy trong seeded_scope_data"
    return order.id


# ---------------------------------------------------------------------------
# get_win_rate_by_org
# ---------------------------------------------------------------------------


def test_get_win_rate_by_org_admin_sees_all_employees(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Admin (`unrestricted=True`) phải thấy dữ liệu win-rate của CẢ 3
    nhân viên (2 ở Department A, 1 ở Department B) — không lọc theo
    Khối/Phòng dù Admin có gắn `employee_id` hay không (CLAUDE.md mục 6)."""
    scope = _admin_scope(db_engine)

    df = get_win_rate_by_org(scope, engine=db_engine)

    employee_ids = set(df["employee_id"])
    assert employee_ids == {
        seeded_scope_data["emp_manager_id"],
        seeded_scope_data["emp_user_id"],
        seeded_scope_data["emp_outsider_id"],
    }
    assert df["total_requests"].sum() == 8


def test_get_win_rate_by_org_manager_restricted_to_own_department(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Manager gắn `employee_id=emp_manager_id` (Department A) chỉ được
    thấy win-rate của nhân viên CÙNG Department A (`emp_manager`,
    `emp_user`) — dữ liệu của `emp_outsider` (Department B) phải bị loại
    trừ hoàn toàn, đúng mẫu lọc RBAC số 1 (`Employee.department_id`,
    CLAUDE.md mục 7)."""
    scope = _manager_scope(db_engine, employee_id=seeded_scope_data["emp_manager_id"])

    df = get_win_rate_by_org(scope, engine=db_engine)

    employee_ids = set(df["employee_id"])
    assert employee_ids == {
        seeded_scope_data["emp_manager_id"],
        seeded_scope_data["emp_user_id"],
    }
    assert seeded_scope_data["emp_outsider_id"] not in employee_ids


def test_win_rate_calculation_matches_won_over_total_requests(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Công thức "Thành đơn" (`.claude/rules/trang-thai-yeu-cau.md`) = Số
    lượng chốt đơn / Số lượng request giá. `emp_user` có 4 request, 3 chốt
    (1 qua `is_won=True`, 1 qua `sales_order_id IS NOT NULL` với
    `is_won=False` — kiểm tra đúng nhánh OR của `_won_expr`, 1 qua
    `is_won=True` không có customer_id) -> `win_rate` phải đúng bằng
    3 / 4 = 0.75."""
    scope = _admin_scope(db_engine)

    df = get_win_rate_by_org(scope, engine=db_engine)

    row = df[df["employee_id"] == seeded_scope_data["emp_user_id"]].iloc[0]
    assert row["total_requests"] == 4
    assert row["won_requests"] == 3
    assert row["win_rate"] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# get_win_rate_by_customer — placeholder cho customer_id NULL
# ---------------------------------------------------------------------------


def test_get_win_rate_by_customer_uses_placeholder_label_for_null_customer(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """`price_request.customer_id` NULL (báo giá cho khách hàng tiềm năng
    chưa có mã) phải được gộp thành 1 nhóm và gán nhãn hiển thị
    `_CUSTOMER_PLACEHOLDER_LABEL`, KHÔNG bị loại khỏi kết quả, KHÔNG lỗi
    (xem docstring module `report_pricing.py`)."""
    scope = _admin_scope(db_engine)

    df = get_win_rate_by_customer(scope, engine=db_engine)

    placeholder_rows = df[df["customer_name"] == _CUSTOMER_PLACEHOLDER_LABEL]
    assert len(placeholder_rows) == 1
    row = placeholder_rows.iloc[0]
    assert row["customer_id"] is None or pd.isna(row["customer_id"])
    assert row["customer_code"] == "—"
    assert row["total_requests"] == 1
    assert row["won_requests"] == 1

    customer_x_rows = df[df["customer_id"] == seeded_scope_data["customer_x_id"]]
    assert len(customer_x_rows) == 1
    assert customer_x_rows.iloc[0]["total_requests"] == 3


# ---------------------------------------------------------------------------
# get_win_rate_trend
# ---------------------------------------------------------------------------


def test_get_win_rate_trend_groups_by_month_admin_unrestricted(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Admin xem xu hướng thành đơn gộp theo tháng (`granularity="month"`,
    mặc định) trên TOÀN BỘ dữ liệu (8 request seed, trải 2 tháng: Tháng 1
    có 6 request/5 chốt — req1+req2 của `emp_user`, req5 của `emp_manager`,
    req7+req8 của `emp_outsider`; Tháng 2 có 2 request/1 chốt — req3 của
    `emp_user`)."""
    _register_sqlite_date_format(db_engine)
    scope = _admin_scope(db_engine)

    df = get_win_rate_trend(scope, engine=db_engine, granularity="month")

    assert len(df) == 2
    df = df.sort_values("period").reset_index(drop=True)
    jan, feb = df.iloc[0], df.iloc[1]
    assert jan["total_requests"] == 6
    assert jan["won_requests"] == 5
    assert feb["total_requests"] == 2
    assert feb["won_requests"] == 1
    assert feb["win_rate"] == pytest.approx(0.5)


def test_get_win_rate_trend_manager_scope_excludes_outsider_department(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Manager Department A chỉ thấy xu hướng thành đơn của `emp_manager` +
    `emp_user` (6 request tổng: 4 Tháng 1, 2 Tháng 2) — 2 request của
    `emp_outsider` (Department B, Tháng 1) phải bị loại khỏi cả tổng lẫn
    xu hướng."""
    _register_sqlite_date_format(db_engine)
    scope = _manager_scope(db_engine, employee_id=seeded_scope_data["emp_manager_id"])

    df = get_win_rate_trend(scope, engine=db_engine, granularity="month")

    assert df["total_requests"].sum() == 6


def test_get_win_rate_trend_raises_for_invalid_granularity(
    db_engine, seeded_scope_data
):
    """`granularity` chỉ chấp nhận `"month"`/`"week"` — giá trị khác phải
    raise `ValueError`, không âm thầm bỏ qua."""
    scope = _admin_scope(db_engine)

    with pytest.raises(ValueError):
        get_win_rate_trend(scope, engine=db_engine, granularity="quarter")


# ---------------------------------------------------------------------------
# get_supplier_score_by_supplier / get_supplier_score_trend / get_supplier_list
# ---------------------------------------------------------------------------


def test_get_supplier_score_by_supplier_admin_sees_all_suppliers(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Admin thấy điểm đánh giá trung bình của CẢ 2 nhà cung cấp
    (`sup_alpha` đánh giá bởi `emp_user`/Dept A, `sup_beta` bởi
    `emp_outsider`/Dept B) — `avg_score` tính đúng trung bình cộng."""
    scope = _admin_scope(db_engine)

    df = get_supplier_score_by_supplier(scope, engine=db_engine)

    assert set(df["supplier_id"]) == {
        seeded_pricing_data["sup_alpha_id"],
        seeded_pricing_data["sup_beta_id"],
    }
    alpha_row = df[df["supplier_id"] == seeded_pricing_data["sup_alpha_id"]].iloc[0]
    assert alpha_row["evaluation_count"] == 2
    assert alpha_row["avg_score"] == pytest.approx(85.0)


def test_get_supplier_score_by_supplier_manager_excludes_other_department(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Manager Department A chỉ thấy `sup_alpha` (đánh giá bởi `emp_user`,
    cùng Department A) — `sup_beta` (đánh giá bởi `emp_outsider`, Department
    B) phải bị loại trừ hoàn toàn, đúng mẫu lọc RBAC theo NHÂN VIÊN phụ
    trách đánh giá (không phải NCC được đánh giá)."""
    scope = _manager_scope(db_engine, employee_id=seeded_scope_data["emp_manager_id"])

    df = get_supplier_score_by_supplier(scope, engine=db_engine)

    assert set(df["supplier_id"]) == {seeded_pricing_data["sup_alpha_id"]}


def test_get_supplier_score_trend_admin_groups_by_month(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Xu hướng điểm đánh giá NCC theo tháng, Admin xem toàn bộ: Tháng 1 có
    2 đánh giá (80, 60 -> avg 70), Tháng 2 có 1 đánh giá (90)."""
    _register_sqlite_date_format(db_engine)
    scope = _admin_scope(db_engine)

    df = get_supplier_score_trend(scope, engine=db_engine, granularity="month")

    df = df.sort_values("period").reset_index(drop=True)
    assert len(df) == 2
    jan, feb = df.iloc[0], df.iloc[1]
    assert jan["evaluation_count"] == 2
    assert jan["avg_score"] == pytest.approx(70.0)
    assert feb["evaluation_count"] == 1
    assert feb["avg_score"] == pytest.approx(90.0)


def test_get_supplier_list_returns_only_suppliers_with_evaluations_in_scope(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """`get_supplier_list` trả về danh sách NCC có ít nhất 1 đánh giá TRONG
    phạm vi RBAC — Admin thấy cả 2 NCC (sắp xếp theo tên), Manager Department
    A chỉ thấy `sup_alpha`."""
    admin_scope = _admin_scope(db_engine)
    df_admin = get_supplier_list(admin_scope, engine=db_engine)
    assert list(df_admin["supplier_name"]) == ["NCC Alpha", "NCC Beta"]

    manager_scope = _manager_scope(
        db_engine, employee_id=seeded_scope_data["emp_manager_id"]
    )
    df_manager = get_supplier_list(manager_scope, engine=db_engine)
    assert list(df_manager["supplier_name"]) == ["NCC Alpha"]


# ---------------------------------------------------------------------------
# _scope_is_empty — edge case
# ---------------------------------------------------------------------------


def test_scope_is_empty_true_for_manager_without_department_id():
    """Manager không có `department_id` (trường hợp lẽ ra bị chặn sớm bởi
    `compute_data_scope()` khi `employee_id is None`, nhưng
    `_scope_is_empty` vẫn phải tự bảo vệ đúng theo docstring) -> `True`."""
    scope = DataScope(
        user_id=1,
        username="manager-no-dept",
        role=UserRole.MANAGER,
        employee_id=None,
        department_id=None,
        division_id=None,
        classification_hint=None,
        customer_ids=frozenset(),
        unrestricted=False,
        description="test",
    )
    assert _scope_is_empty(scope) is True


def test_scope_is_empty_true_for_user_without_employee_id():
    """User không có `employee_id` -> `True` (không xác định được phạm vi
    theo NHÂN VIÊN, chủ thể phân quyền chính của module này)."""
    scope = DataScope(
        user_id=2,
        username="user-no-emp",
        role=UserRole.USER,
        employee_id=None,
        department_id=None,
        division_id=None,
        classification_hint=None,
        customer_ids=frozenset(),
        unrestricted=False,
        description="test",
    )
    assert _scope_is_empty(scope) is True


def test_scope_is_empty_false_for_admin_even_without_employee_id():
    """Admin luôn `unrestricted=True` -> `_scope_is_empty` phải `False`
    dù không gắn `employee_id`/`department_id` (CLAUDE.md mục 6: Admin
    luôn xem toàn bộ, không giới hạn theo Khối/Phòng)."""
    scope = DataScope(
        user_id=3,
        username="admin-no-emp",
        role=UserRole.ADMIN,
        employee_id=None,
        department_id=None,
        division_id=None,
        classification_hint=None,
        customer_ids=frozenset(),
        unrestricted=True,
        description="test",
    )
    assert _scope_is_empty(scope) is False


def test_get_win_rate_by_org_returns_empty_dataframe_for_empty_manager_scope(
    db_engine, seeded_scope_data, seeded_pricing_data
):
    """Khi scope rỗng (Manager không có `department_id`), các hàm báo cáo
    phải trả về DataFrame RỖNG đúng cột, KHÔNG raise lỗi và KHÔNG vô tình
    trả về toàn bộ dữ liệu."""
    scope = DataScope(
        user_id=4,
        username="manager-empty",
        role=UserRole.MANAGER,
        employee_id=None,
        department_id=None,
        division_id=None,
        classification_hint=None,
        customer_ids=frozenset(),
        unrestricted=False,
        description="test",
    )

    df = get_win_rate_by_org(scope, engine=db_engine)

    assert df.empty
    assert list(df.columns) == [
        "division_id",
        "division_name",
        "department_id",
        "department_name",
        "employee_id",
        "employee_name",
        "total_requests",
        "won_requests",
        "win_rate",
    ]
