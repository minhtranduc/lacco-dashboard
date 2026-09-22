"""Test `src/services/report_chi_phi.py` — 2 báo cáo con "Theo Khối"
(`cost` vs `budget`) và "Theo Nhóm nhân sự" (`personnel_cost`).

Trọng tâm test là RBAC đã "Đã rõ" tại CLAUDE.md mục 7 và
`.claude/rules/trang-thai-yeu-cau.md` (dòng "Chi phí | Theo Khối" và
"Chi phí | Theo Nhóm"), chốt bước 5.1 (09/09/2026):

1. "Theo Khối": Admin (`scope.unrestricted=True`) xem toàn bộ Khối; Manager
   chỉ xem đúng `scope.division_id` của mình; User bị CHẶN HẲN (trả về
   DataFrame rỗng, không phải lỗi — xem `_division_scope_blocked`).
2. "Theo Nhóm nhân sự": CHỈ Admin được xem — Manager/User bị chặn bằng
   `PermissionError` (`_require_admin`), vì bảng `personnel_cost` không có
   cột liên kết Khối/Phòng/NV để lọc RBAC thấp hơn.

Dùng `DataScope` dựng trực tiếp (dataclass, `src/auth/scope.py`) thay vì đi
qua `compute_data_scope()` — các hàm trong `report_chi_phi.py` chỉ đọc trực
tiếp `scope.unrestricted`/`scope.role`/`scope.division_id`/`scope.user_id`
(xem `_division_scope_blocked`/`_apply_division_filter`/`_require_admin`),
không suy luận qua `customer_ids`/`employee_id` như các module khác — dựng
`DataScope` trực tiếp vừa đủ trung thực với hành vi thật, vừa tránh phải
seed thêm `Employee`/`User`/`Department` không cần thiết cho module này.

**Không test quy tắc loại trừ đơn `status="Huỷ"`** (CLAUDE.md mục 7): quy
tắc đó áp dụng cho tổng doanh thu/lãi lỗ suy ra từ `sales_order`. Module
`report_chi_phi.py` chỉ tổng hợp `cost`/`budget`/`personnel_cost` — các
bảng này không có cột `status` đơn hàng, nên quy tắc không áp dụng ở đây
(đã đọc code xác nhận, không phải bỏ sót).

Hạ tầng: SQLite in-memory qua fixture `db_engine` (`tests/conftest.py`,
`StaticPool`) — KHÔNG kết nối MySQL "lacco" thật. Fixture seed dữ liệu
`Division`/`Cost`/`Budget`/`PersonnelCost` riêng cho module này
(`seeded_cost_data` bên dưới) vì `seeded_scope_data` sẵn có ở `conftest.py`
chỉ seed dữ liệu cho `compute_data_scope()` (Customer/SalesOrder), không có
Cost/Budget/PersonnelCost.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.auth.scope import DataScope
from src.db.models import Budget, Cost, Division, PersonnelCost
from src.db.models.enums import StaffGroup, UserRole
from src.services.report_chi_phi import (
    _division_scope_blocked,
    get_cost_vs_budget_by_division,
    get_cost_vs_budget_trend,
    get_division_list,
    get_personnel_cost_by_staff_group,
    get_personnel_cost_trend,
    get_staff_group_list,
)


def _sqlite_date_format(value: str | None, fmt: str) -> str | None:
    """Triển khai lại tối thiểu hàm MySQL `DATE_FORMAT(date_col, fmt)` cho
    2 định dạng `_period_expr` dùng (`report_chi_phi.py`) — SQLite (dùng
    trong test) không có hàm này, chỉ MySQL thật (prod) mới có. Đăng ký
    trực tiếp lên connection SQLite qua `sqlite3.Connection.create_function`
    (xem fixture `_date_format_shim`), KHÔNG đổi code nghiệp vụ prod."""
    if value is None:
        return None
    parsed = date.fromisoformat(value)
    if fmt == "%Y-%m-01":
        return parsed.replace(day=1).isoformat()
    if fmt == "%x-%v":
        iso_year, iso_week, _ = parsed.isocalendar()
        return f"{iso_year}-{iso_week:02d}"
    raise ValueError(f"_sqlite_date_format: fmt không hỗ trợ: {fmt!r}")


@pytest.fixture()
def _date_format_shim(db_engine):
    """Đăng ký hàm `date_format` tương đương MySQL lên connection SQLite
    in-memory của `db_engine` — cần cho các test gọi `get_cost_vs_budget_
    trend`/`get_personnel_cost_trend` (dùng `func.date_format(...)` qua
    `_period_expr`). `StaticPool` đảm bảo đây luôn là CÙNG 1 connection vật
    lý trong suốt vòng đời `db_engine`, nên đăng ký 1 lần là đủ cho mọi
    query sau đó trong cùng test."""
    raw_connection = db_engine.raw_connection()
    raw_connection.dbapi_connection.create_function(
        "date_format", 2, _sqlite_date_format
    )
    try:
        yield
    finally:
        raw_connection.close()


def _make_scope(
    *,
    role: UserRole,
    unrestricted: bool,
    division_id: int | None = None,
    user_id: int = 1,
    username: str = "test-user",
) -> DataScope:
    """Dựng 1 `DataScope` tối thiểu, đủ trường mà `report_chi_phi.py` thực
    sự đọc (`unrestricted`, `role`, `division_id`, `user_id` — chỉ dùng để
    log). Các trường không liên quan (`customer_ids`, `classification_hint`,
    ...) để giá trị mặc định trung tính vì module này không đọc tới."""
    return DataScope(
        user_id=user_id,
        username=username,
        role=role,
        employee_id=None,
        department_id=None,
        division_id=division_id,
        classification_hint=None,
        customer_ids=frozenset(),
        unrestricted=unrestricted,
        description="scope dựng trực tiếp cho test report_chi_phi",
    )


@pytest.fixture()
def seeded_cost_data(db_engine):
    """Seed 3 Khối + `cost`/`budget`/`personnel_cost` cho test
    `report_chi_phi.py`.

    - `div_a` ("Khối Kinh doanh"): có `cost` VÀ `budget` ở cả 2 kỳ
      (2026-01, 2026-02) — dùng cho test Manager-scoped (chỉ thấy Khối này)
      và test trend theo tháng.
    - `div_b` ("Khối Vận hành"): có `cost` VÀ `budget`, chỉ kỳ 2026-01 —
      dùng để xác nhận Khối khác bị loại trừ khỏi phạm vi Manager.
    - `div_c` ("Khối Không Ngân sách"): CHỈ có `cost`, KHÔNG có dòng
      `budget` nào — dùng test nhánh chia cho 0 của `variance_pct`
      (`budget_amount == 0` -> quy ước trả `0.0`, xem docstring module
      `report_chi_phi.py`).

    `personnel_cost`: 2 nhóm (LEADERSHIP kỳ 2026-01, FRONTLINE kỳ 2026-01
    VÀ 2026-02) — dùng test "Theo Nhóm nhân sự".
    """
    with Session(db_engine) as session:
        div_a = Division(name="Khối Kinh doanh")
        div_b = Division(name="Khối Vận hành")
        div_c = Division(name="Khối Không Ngân sách")
        session.add_all([div_a, div_b, div_c])
        session.flush()

        session.add_all(
            [
                Cost(division_id=div_a.id, period=date(2026, 1, 1), amount=1_000_000),
                Cost(division_id=div_a.id, period=date(2026, 2, 1), amount=1_500_000),
                Cost(division_id=div_b.id, period=date(2026, 1, 1), amount=800_000),
                Cost(division_id=div_c.id, period=date(2026, 1, 1), amount=500_000),
                Budget(division_id=div_a.id, period=date(2026, 1, 1), amount=1_200_000),
                Budget(division_id=div_a.id, period=date(2026, 2, 1), amount=1_500_000),
                Budget(division_id=div_b.id, period=date(2026, 1, 1), amount=900_000),
                # Cố ý KHÔNG tạo Budget cho div_c.
                PersonnelCost(
                    staff_group=StaffGroup.LEADERSHIP,
                    period=date(2026, 1, 1),
                    amount=300_000,
                ),
                PersonnelCost(
                    staff_group=StaffGroup.FRONTLINE,
                    period=date(2026, 1, 1),
                    amount=700_000,
                ),
                PersonnelCost(
                    staff_group=StaffGroup.FRONTLINE,
                    period=date(2026, 2, 1),
                    amount=800_000,
                ),
            ]
        )
        session.commit()

        return {
            "div_a_id": div_a.id,
            "div_b_id": div_b.id,
            "div_c_id": div_c.id,
        }


# ---------------------------------------------------------------------------
# _division_scope_blocked — quy tắc chặn "Theo Khối"
# ---------------------------------------------------------------------------


def test_division_scope_blocked_admin_never_blocked():
    """Admin (`unrestricted=True`) không bao giờ bị chặn, kể cả khi thiếu
    `division_id` (Admin không gắn employee_id vẫn `unrestricted=True`)."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True, division_id=None)
    assert _division_scope_blocked(scope) is False


def test_division_scope_blocked_user_always_blocked():
    """User LUÔN bị chặn khỏi "Theo Khối", kể cả khi có `division_id` hợp
    lệ — `cost`/`budget` không có dữ liệu cấp nhân viên (quyết định COO
    09/09/2026)."""
    scope = _make_scope(role=UserRole.USER, unrestricted=False, division_id=42)
    assert _division_scope_blocked(scope) is True


def test_division_scope_blocked_manager_without_division_id():
    """Manager thiếu `division_id` (scope rỗng, VD tài khoản không gắn
    `employee_id` hợp lệ) bị chặn."""
    scope = _make_scope(role=UserRole.MANAGER, unrestricted=False, division_id=None)
    assert _division_scope_blocked(scope) is True


def test_division_scope_blocked_manager_with_division_id_not_blocked():
    """Manager có `division_id` hợp lệ KHÔNG bị chặn (chỉ bị lọc phạm vi,
    xem `_apply_division_filter`)."""
    scope = _make_scope(role=UserRole.MANAGER, unrestricted=False, division_id=1)
    assert _division_scope_blocked(scope) is False


# ---------------------------------------------------------------------------
# get_cost_vs_budget_by_division
# ---------------------------------------------------------------------------


def test_cost_vs_budget_by_division_admin_sees_all_divisions(
    db_engine, seeded_cost_data
):
    """Admin thấy đủ cả 3 Khối, gồm cả Khối không có `budget` (div_c) với
    `variance_pct == 0.0` theo quy ước chia cho 0."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    df = get_cost_vs_budget_by_division(scope, engine=db_engine)

    assert set(df["division_id"]) == {
        seeded_cost_data["div_a_id"],
        seeded_cost_data["div_b_id"],
        seeded_cost_data["div_c_id"],
    }
    div_c_row = df[df["division_id"] == seeded_cost_data["div_c_id"]].iloc[0]
    assert div_c_row["cost_amount"] == pytest.approx(500_000)
    assert div_c_row["budget_amount"] == pytest.approx(0)
    assert div_c_row["variance"] == pytest.approx(500_000)
    assert div_c_row["variance_pct"] == pytest.approx(0.0)

    div_a_row = df[df["division_id"] == seeded_cost_data["div_a_id"]].iloc[0]
    assert div_a_row["cost_amount"] == pytest.approx(2_500_000)
    assert div_a_row["budget_amount"] == pytest.approx(2_700_000)
    assert div_a_row["variance"] == pytest.approx(-200_000)
    assert div_a_row["variance_pct"] == pytest.approx(-200_000 / 2_700_000)

    # Sắp xếp giảm dần theo cost_amount.
    assert list(df["cost_amount"]) == sorted(df["cost_amount"], reverse=True)


def test_cost_vs_budget_by_division_manager_sees_only_own_division(
    db_engine, seeded_cost_data
):
    """Manager với `scope.division_id = div_a` chỉ thấy đúng div_a — div_b
    và div_c (Khối khác) bị loại trừ hoàn toàn khỏi kết quả."""
    scope = _make_scope(
        role=UserRole.MANAGER,
        unrestricted=False,
        division_id=seeded_cost_data["div_a_id"],
    )

    df = get_cost_vs_budget_by_division(scope, engine=db_engine)

    assert len(df) == 1
    assert df.iloc[0]["division_id"] == seeded_cost_data["div_a_id"]
    assert df.iloc[0]["cost_amount"] == pytest.approx(2_500_000)
    assert df.iloc[0]["budget_amount"] == pytest.approx(2_700_000)
    assert seeded_cost_data["div_b_id"] not in df["division_id"].values
    assert seeded_cost_data["div_c_id"] not in df["division_id"].values


def test_cost_vs_budget_by_division_user_returns_empty_dataframe(
    db_engine, seeded_cost_data
):
    """User bị chặn hẳn khỏi "Theo Khối" — DataFrame rỗng nhưng ĐÚNG cột
    (không phải lỗi/exception, khác với "Theo Nhóm nhân sự")."""
    scope = _make_scope(
        role=UserRole.USER,
        unrestricted=False,
        division_id=seeded_cost_data["div_a_id"],
    )

    df = get_cost_vs_budget_by_division(scope, engine=db_engine)

    assert df.empty
    assert list(df.columns) == [
        "division_id",
        "division_name",
        "cost_amount",
        "budget_amount",
        "variance",
        "variance_pct",
    ]


def test_cost_vs_budget_by_division_date_filter_restricts_periods(
    db_engine, seeded_cost_data
):
    """`date_from` loại trừ kỳ 2026-01 — chỉ còn div_a (kỳ 2026-02), vì
    div_b/div_c không có dòng nào trong kỳ 2026-02."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    df = get_cost_vs_budget_by_division(
        scope, engine=db_engine, date_from=date(2026, 2, 1)
    )

    assert len(df) == 1
    assert df.iloc[0]["division_id"] == seeded_cost_data["div_a_id"]
    assert df.iloc[0]["cost_amount"] == pytest.approx(1_500_000)
    assert df.iloc[0]["budget_amount"] == pytest.approx(1_500_000)
    assert df.iloc[0]["variance"] == pytest.approx(0)


# ---------------------------------------------------------------------------
# get_cost_vs_budget_trend
# ---------------------------------------------------------------------------


def test_cost_vs_budget_trend_admin_month_granularity(
    db_engine, seeded_cost_data, _date_format_shim
):
    """Admin: xu hướng theo tháng gộp cả 3 Khối, 2 kỳ (2026-01, 2026-02),
    sắp xếp tăng dần theo `period`."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    df = get_cost_vs_budget_trend(scope, engine=db_engine, granularity="month")

    assert len(df) == 2
    jan, feb = df.iloc[0], df.iloc[1]
    assert jan["cost_amount"] == pytest.approx(2_300_000)  # 1.0M + 0.8M + 0.5M
    assert jan["budget_amount"] == pytest.approx(2_100_000)  # 1.2M + 0.9M
    assert feb["cost_amount"] == pytest.approx(1_500_000)
    assert feb["budget_amount"] == pytest.approx(1_500_000)
    assert feb["variance"] == pytest.approx(0)


def test_cost_vs_budget_trend_manager_scoped_to_own_division(
    db_engine, seeded_cost_data, _date_format_shim
):
    """Manager chỉ thấy xu hướng của đúng `scope.division_id` (div_a) —
    2 kỳ, không lẫn số liệu div_b/div_c."""
    scope = _make_scope(
        role=UserRole.MANAGER,
        unrestricted=False,
        division_id=seeded_cost_data["div_a_id"],
    )

    df = get_cost_vs_budget_trend(scope, engine=db_engine, granularity="month")

    assert len(df) == 2
    assert df.iloc[0]["cost_amount"] == pytest.approx(1_000_000)
    assert df.iloc[0]["budget_amount"] == pytest.approx(1_200_000)
    assert df.iloc[1]["cost_amount"] == pytest.approx(1_500_000)
    assert df.iloc[1]["budget_amount"] == pytest.approx(1_500_000)


def test_cost_vs_budget_trend_user_returns_empty_dataframe(db_engine, seeded_cost_data):
    """User bị chặn -> DataFrame rỗng đúng cột, giống `get_cost_vs_budget_
    by_division`."""
    scope = _make_scope(role=UserRole.USER, unrestricted=False, division_id=None)

    df = get_cost_vs_budget_trend(scope, engine=db_engine)

    assert df.empty
    assert list(df.columns) == [
        "period",
        "cost_amount",
        "budget_amount",
        "variance",
        "variance_pct",
    ]


def test_cost_vs_budget_trend_invalid_granularity_raises_value_error(
    db_engine, seeded_cost_data
):
    """`granularity` khác `"month"`/`"week"` raise `ValueError` ngay từ
    đầu, không phụ thuộc scope."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    with pytest.raises(ValueError):
        get_cost_vs_budget_trend(scope, engine=db_engine, granularity="year")


# ---------------------------------------------------------------------------
# get_division_list
# ---------------------------------------------------------------------------


def test_get_division_list_admin_sees_all(db_engine, seeded_cost_data):
    """Admin thấy đủ 3 Khối có ít nhất 1 dòng cost HOẶC budget."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    df = get_division_list(scope, engine=db_engine)

    assert set(df["division_id"]) == {
        seeded_cost_data["div_a_id"],
        seeded_cost_data["div_b_id"],
        seeded_cost_data["div_c_id"],
    }


def test_get_division_list_manager_sees_only_own_division(db_engine, seeded_cost_data):
    """Manager chỉ thấy đúng 1 Khối trong `scope.division_id`."""
    scope = _make_scope(
        role=UserRole.MANAGER,
        unrestricted=False,
        division_id=seeded_cost_data["div_b_id"],
    )

    df = get_division_list(scope, engine=db_engine)

    assert list(df["division_id"]) == [seeded_cost_data["div_b_id"]]


def test_get_division_list_user_returns_empty_dataframe(db_engine, seeded_cost_data):
    """User bị chặn -> danh sách Khối rỗng (đúng cột)."""
    scope = _make_scope(role=UserRole.USER, unrestricted=False, division_id=None)

    df = get_division_list(scope, engine=db_engine)

    assert df.empty
    assert list(df.columns) == ["division_id", "division_name"]


# ---------------------------------------------------------------------------
# get_personnel_cost_by_staff_group / get_personnel_cost_trend — chỉ Admin
# ---------------------------------------------------------------------------


def test_personnel_cost_by_staff_group_admin_succeeds(db_engine, seeded_cost_data):
    """Admin xem được, tổng hợp đúng theo `staff_group`, sắp xếp giảm dần
    theo `cost_amount` (FRONTLINE tổng 1.5M > LEADERSHIP 0.3M)."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    df = get_personnel_cost_by_staff_group(scope, engine=db_engine)

    assert list(df["staff_group"]) == ["Frontline", "LĐ"]
    assert df.iloc[0]["cost_amount"] == pytest.approx(1_500_000)
    assert df.iloc[1]["cost_amount"] == pytest.approx(300_000)


@pytest.mark.parametrize(
    "role", [UserRole.MANAGER, UserRole.USER], ids=["manager", "user"]
)
def test_personnel_cost_by_staff_group_non_admin_raises_permission_error(
    db_engine, seeded_cost_data, role
):
    """Manager/User bị chặn bằng `PermissionError` thật sự (không phải
    DataFrame rỗng) — `personnel_cost` không có cột liên kết Khối/Phòng/NV
    để lọc RBAC thấp hơn Admin."""
    scope = _make_scope(role=role, unrestricted=False)

    with pytest.raises(PermissionError):
        get_personnel_cost_by_staff_group(scope, engine=db_engine)


def test_personnel_cost_trend_admin_succeeds_and_sorted_by_period(
    db_engine, seeded_cost_data, _date_format_shim
):
    """Admin xem xu hướng dạng "long" (period, staff_group, cost_amount),
    3 dòng, sắp xếp tăng dần theo `period`."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    df = get_personnel_cost_trend(scope, engine=db_engine, granularity="month")

    assert len(df) == 3
    assert list(df["period"]) == sorted(df["period"])
    jan_rows = df[df["period"] == df["period"].iloc[0]]
    assert set(jan_rows["staff_group"]) == {"LĐ", "Frontline"}


def test_personnel_cost_trend_filter_by_staff_group(
    db_engine, seeded_cost_data, _date_format_shim
):
    """Truyền `staff_group=StaffGroup.FRONTLINE` chỉ trả về 2 dòng
    (2026-01 và 2026-02), loại trừ LEADERSHIP."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    df = get_personnel_cost_trend(
        scope, engine=db_engine, granularity="month", staff_group=StaffGroup.FRONTLINE
    )

    assert len(df) == 2
    assert set(df["staff_group"]) == {"Frontline"}


@pytest.mark.parametrize(
    "role", [UserRole.MANAGER, UserRole.USER], ids=["manager", "user"]
)
def test_personnel_cost_trend_non_admin_raises_permission_error(
    db_engine, seeded_cost_data, role
):
    """Manager/User bị chặn bằng `PermissionError`, nhất quán với
    `get_personnel_cost_by_staff_group`."""
    scope = _make_scope(role=role, unrestricted=False)

    with pytest.raises(PermissionError):
        get_personnel_cost_trend(scope, engine=db_engine)


def test_personnel_cost_trend_invalid_granularity_raises_value_error(
    db_engine, seeded_cost_data
):
    """Admin hợp lệ nhưng `granularity` sai -> `ValueError` (kiểm tra sau
    `_require_admin` nhưng vẫn raise đúng loại lỗi theo code thực tế)."""
    scope = _make_scope(role=UserRole.ADMIN, unrestricted=True)

    with pytest.raises(ValueError):
        get_personnel_cost_trend(scope, engine=db_engine, granularity="quarter")


def test_get_staff_group_list_returns_fixed_five_groups():
    """Danh sách cố định theo enum `StaffGroup`, không phụ thuộc DB/RBAC."""
    result = get_staff_group_list()

    assert result == ["LĐ", "QL", "Frontline", "Middle", "Backend"]
    assert result == [g.value for g in StaffGroup]
