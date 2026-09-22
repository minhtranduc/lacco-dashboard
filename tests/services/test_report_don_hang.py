"""Test `src/services/report_don_hang.py` — báo cáo "Tình trạng đơn hàng"
và "Tình trạng xuất hóa đơn" (CLAUDE.md mục 7, `.claude/rules/trang-thai-
yeu-cau.md`, 2 dòng "Kinh doanh" tương ứng, cả 2 đã "Đã rõ" ở mức được phép
code phần đếm/hiển thị theo trạng thái).

*** Xác nhận hành vi đơn "Huỷ" — KHÔNG loại trừ ở module này ***
Khác với `report_kinh_doanh.py` (loại trừ đơn `status="Huỷ"` khỏi doanh
thu/lãi lỗ, CLAUDE.md mục 7, COO xác nhận 07/09/2026), `report_don_hang.py`
đếm SỐ LƯỢNG đơn theo từng giá trị `status`/`invoice_status` — đọc trực
tiếp docstring module nguồn (dòng 28-37) xác nhận "Huỷ" là 1 giá trị cần
đếm bình thường như mọi giá trị khác, KHÔNG bị loại trừ. Các test dưới đây
(`test_get_order_status_counts_includes_status_huy_like_any_other_status`
và các test scope) khoá lại hành vi quan sát được thực tế, không suy diễn
theo quy tắc loại trừ của `report_kinh_doanh.py`.

Dùng chung fixture `db_engine`/`seeded_scope_data` (`tests/conftest.py`,
SQLite in-memory qua `StaticPool` — KHÔNG kết nối MySQL "lacco" thật).
`seeded_scope_data` chỉ có 3 đơn cùng `status="Đang vận chuyển"` trong cùng
1 tuần — không đủ để test group-by status/trend nhiều giá trị/nhiều kỳ, nên
file này tự seed thêm dữ liệu qua fixture riêng `extra_status_orders` (định
nghĩa trong chính file này, KHÔNG sửa `tests/conftest.py`).

*** Ghi chú hạ tầng test riêng cho `get_order_status_trend` ***
Hàm nguồn dùng `func.date_format(...)` — đúng dialect MySQL thật (`src/
services/db_connection.py` dùng `mysql+mysqlconnector`). SQLite KHÔNG có
hàm `date_format` sẵn (`OperationalError: no such function: date_format` —
đã xác minh thật khi viết file test này). Vì vậy các test trend đăng ký 1
hàm Python tương đương qua `sqlite3.Connection.create_function` (helper
`_register_sqlite_date_format` bên dưới) — CHỈ hỗ trợ đúng 2 định dạng mà
`report_don_hang.py` thực sự dùng (`"%Y-%m-01"`, `"%x-%v"`), thuần tuý hạ
tầng test, không sửa code nguồn.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.auth.scope import DataScope, compute_data_scope
from src.db.models.business import SalesOrder
from src.db.models.enums import UserRole
from src.db.models.security import User
from src.services.report_don_hang import (
    get_invoice_status_counts,
    get_order_status_counts,
    get_order_status_trend,
)


def _create_user(
    engine, *, username: str, role: UserRole, employee_id: int | None
) -> int:
    """Tạo 1 user tối thiểu qua ORM — mẫu giống hệt `tests/auth/
    test_scope.py::_create_user`, lặp lại cục bộ ở đây để file test độc
    lập (không import chéo giữa 2 module test)."""
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
    """Đăng ký hàm `date_format(value, fmt)` tương thích cho SQLite
    in-memory test DB — xem docstring module để biết lý do đầy đủ. CHỈ hỗ
    trợ đúng 2 định dạng `get_order_status_trend` thực sự dùng."""

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


@pytest.fixture()
def extra_status_orders(db_engine, seeded_scope_data):
    """Thêm 4 đơn hàng vào dữ liệu đã seed sẵn (`seeded_scope_data`) để có
    đủ giá trị `status`/`invoice_status` đa dạng ("Huỷ", "Mới tạo", "Đang
    xử lý"*, "Đã giao") trải trên nhiều tháng/tuần khác nhau, tái sử dụng
    đúng `customer_id`/`employee_id` đã seed — không tự tạo customer/
    employee mới để giữ đúng ranh giới RBAC (X, Y do Manager phụ trách
    phòng A quản lý được; Z ngoài phạm vi).

    (*) "Đang xử lý" không dùng trong dữ liệu seed thêm ở đây vì 4 giá trị
    "Đang vận chuyển"/"Huỷ"/"Mới tạo"/"Đã giao" đã đủ đa dạng để test group-
    by mà không cần thêm dòng; không hardcode toàn bộ danh sách trạng thái
    (module nguồn cố tình không hardcode — xem docstring `report_don_hang.py`).

    Dữ liệu thêm (cộng với 3 đơn gốc của `seeded_scope_data`, đều
    `status="Đang vận chuyển"`, ngày 2026-01-10/11/12):
    - customer_x, 2026-01-15, status="Huỷ", invoice_status="Chưa xuất"
    - customer_x, 2026-02-05, status="Mới tạo", invoice_status="Chưa xuất"
    - customer_y, 2026-01-20, status="Đã giao", invoice_status="Đã xuất"
    - customer_z, 2026-02-10, status="Huỷ", invoice_status="Đã xuất"
    """
    service_id = seeded_scope_data["service_id"]
    with Session(db_engine) as session:
        session.add_all(
            [
                SalesOrder(
                    customer_id=seeded_scope_data["customer_x_id"],
                    service_id=service_id,
                    employee_id=seeded_scope_data["emp_user_id"],
                    order_date=date(2026, 1, 15),
                    status="Huỷ",
                    revenue=500,
                    order_cost=100,
                    invoice_status="Chưa xuất",
                ),
                SalesOrder(
                    customer_id=seeded_scope_data["customer_x_id"],
                    service_id=service_id,
                    employee_id=seeded_scope_data["emp_user_id"],
                    order_date=date(2026, 2, 5),
                    status="Mới tạo",
                    revenue=700,
                    order_cost=200,
                    invoice_status="Chưa xuất",
                ),
                SalesOrder(
                    customer_id=seeded_scope_data["customer_y_id"],
                    service_id=service_id,
                    employee_id=seeded_scope_data["emp_manager_id"],
                    order_date=date(2026, 1, 20),
                    status="Đã giao",
                    revenue=1200,
                    order_cost=900,
                    invoice_status="Đã xuất",
                ),
                SalesOrder(
                    customer_id=seeded_scope_data["customer_z_id"],
                    service_id=service_id,
                    employee_id=seeded_scope_data["emp_outsider_id"],
                    order_date=date(2026, 2, 10),
                    status="Huỷ",
                    revenue=400,
                    order_cost=50,
                    invoice_status="Đã xuất",
                ),
            ]
        )
        session.commit()
    return seeded_scope_data


def _admin_scope(db_engine) -> DataScope:
    user_id = _create_user(
        db_engine, username="admin_don_hang", role=UserRole.ADMIN, employee_id=None
    )
    return compute_data_scope(user_id, engine=db_engine)


def _manager_scope(db_engine, seeded_scope_data) -> DataScope:
    user_id = _create_user(
        db_engine,
        username="manager_don_hang",
        role=UserRole.MANAGER,
        employee_id=seeded_scope_data["emp_manager_id"],
    )
    return compute_data_scope(user_id, engine=db_engine)


# ---------------------------------------------------------------------------
# get_order_status_counts
# ---------------------------------------------------------------------------


def test_get_order_status_counts_admin_sees_all_customers(
    db_engine, extra_status_orders
):
    """Admin (`unrestricted=True`) thấy số lượng đơn theo `status` gộp trên
    TẤT CẢ khách hàng (X, Y, Z) — tổng 7 đơn, 4 giá trị status khác nhau."""
    scope = _admin_scope(db_engine)

    df = get_order_status_counts(scope, engine=db_engine)

    assert list(df.columns) == ["status", "order_count"]
    counts = dict(zip(df["status"], df["order_count"]))
    assert counts == {
        "Đang vận chuyển": 3,
        "Huỷ": 2,
        "Mới tạo": 1,
        "Đã giao": 1,
    }
    assert int(df["order_count"].sum()) == 7


def test_get_order_status_counts_restricted_scope_excludes_out_of_scope_orders(
    db_engine, extra_status_orders
):
    """Manager (phạm vi Phòng A = customer X, Y) KHÔNG thấy đơn của
    customer Z (Phòng B) — tổng chỉ 5 đơn thay vì 7 của Admin, và riêng 2
    trạng thái có đóng góp từ Z ("Đang vận chuyển", "Huỷ") phải giảm đúng
    số lượng loại trừ."""
    scope = _manager_scope(db_engine, extra_status_orders)

    df = get_order_status_counts(scope, engine=db_engine)

    counts = dict(zip(df["status"], df["order_count"]))
    assert counts == {
        "Đang vận chuyển": 2,  # loại trừ order_z (customer Z)
        "Huỷ": 1,  # loại trừ order_z2 (customer Z)
        "Mới tạo": 1,
        "Đã giao": 1,
    }
    assert int(df["order_count"].sum()) == 5


def test_get_order_status_counts_includes_status_huy_like_any_other_status(
    db_engine, extra_status_orders
):
    """Khoá lại hành vi đã xác nhận từ đọc code nguồn: `status="Huỷ"` KHÔNG
    bị loại trừ ở báo cáo này (khác `report_kinh_doanh.py`) — đơn Huỷ được
    đếm bình thường như mọi trạng thái khác, không tách riêng/loại khỏi
    tổng."""
    scope = _admin_scope(db_engine)

    df = get_order_status_counts(scope, engine=db_engine)

    assert "Huỷ" in df["status"].values
    huy_count = int(df.loc[df["status"] == "Huỷ", "order_count"].iloc[0])
    assert huy_count == 2
    # Tổng toàn bộ (7) phải CỘNG cả 2 đơn Huỷ — nếu bị loại trừ như
    # report_kinh_doanh.py thì tổng sẽ chỉ còn 5.
    assert int(df["order_count"].sum()) == 7


def test_get_order_status_counts_empty_scope_returns_empty_dataframe(db_engine):
    """User không gắn `employee_id` -> `compute_data_scope` trả về phạm vi
    rỗng (`unrestricted=False`, `customer_ids=frozenset()`) -> hàm phải trả
    về DataFrame rỗng đúng cột, không query DB thêm."""
    user_id = _create_user(
        db_engine, username="orphan_counts", role=UserRole.USER, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is False
    assert scope.customer_ids == frozenset()

    df = get_order_status_counts(scope, engine=db_engine)

    assert df.empty
    assert list(df.columns) == ["status", "order_count"]


# ---------------------------------------------------------------------------
# get_invoice_status_counts
# ---------------------------------------------------------------------------


def test_get_invoice_status_counts_admin_sees_all_customers(
    db_engine, extra_status_orders
):
    """Admin thấy số lượng đơn theo `invoice_status` gộp trên tất cả khách
    hàng — tổng 7 đơn, 2 giá trị invoice_status."""
    scope = _admin_scope(db_engine)

    df = get_invoice_status_counts(scope, engine=db_engine)

    assert list(df.columns) == ["invoice_status", "order_count"]
    counts = dict(zip(df["invoice_status"], df["order_count"]))
    assert counts == {"Chưa xuất": 4, "Đã xuất": 3}
    assert int(df["order_count"].sum()) == 7


def test_get_invoice_status_counts_restricted_scope_excludes_out_of_scope_orders(
    db_engine, extra_status_orders
):
    """Manager (phạm vi customer X, Y) không thấy 2 đơn `invoice_status=
    "Đã xuất"` của customer Z (order_z, order_z2) — chỉ còn 1 đơn "Đã xuất"
    (order_y2) thay vì 3 của Admin."""
    scope = _manager_scope(db_engine, extra_status_orders)

    df = get_invoice_status_counts(scope, engine=db_engine)

    counts = dict(zip(df["invoice_status"], df["order_count"]))
    assert counts == {"Chưa xuất": 4, "Đã xuất": 1}
    assert int(df["order_count"].sum()) == 5


def test_get_invoice_status_counts_empty_scope_returns_empty_dataframe(db_engine):
    """Cùng nhánh phạm vi rỗng như `get_order_status_counts` — DataFrame
    rỗng đúng cột `invoice_status`, `order_count`."""
    user_id = _create_user(
        db_engine, username="orphan_invoice", role=UserRole.MANAGER, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is False
    assert scope.customer_ids == frozenset()

    df = get_invoice_status_counts(scope, engine=db_engine)

    assert df.empty
    assert list(df.columns) == ["invoice_status", "order_count"]


# ---------------------------------------------------------------------------
# get_order_status_trend
# ---------------------------------------------------------------------------


def test_get_order_status_trend_month_granularity_admin_groups_by_period_status(
    db_engine, extra_status_orders
):
    """`granularity="month"` gộp theo ngày đầu tháng của `order_date`, cột
    `period` ép kiểu `datetime64` — Admin thấy 5 dòng (period, status) trải
    trên 2 tháng (2026-01 có 3 status khác nhau, 2026-02 có 2 status khác
    nhau, đúng tổng 7 đơn như đã xác nhận ở test counts)."""
    _register_sqlite_date_format(db_engine)
    scope = _admin_scope(db_engine)

    df = get_order_status_trend(scope, engine=db_engine, granularity="month")

    assert list(df.columns) == ["period", "status", "order_count"]
    assert len(df) == 5
    assert str(df["period"].dtype).startswith("datetime64")

    rows = {
        (period.strftime("%Y-%m-%d"), status): int(count)
        for period, status, count in zip(df["period"], df["status"], df["order_count"])
    }
    assert rows == {
        ("2026-01-01", "Đang vận chuyển"): 3,
        ("2026-01-01", "Huỷ"): 1,
        ("2026-01-01", "Đã giao"): 1,
        ("2026-02-01", "Mới tạo"): 1,
        ("2026-02-01", "Huỷ"): 1,
    }
    assert int(df["order_count"].sum()) == 7


def test_get_order_status_trend_week_granularity_uses_iso_week_and_restricts_scope(
    db_engine, extra_status_orders
):
    """`granularity="week"` gộp theo tuần ISO 8601 (`"YYYY-Www"`, CLAUDE.md
    mục 7 — COO xác nhận 07/09/2026), cột `period` giữ dạng chuỗi (KHÔNG ép
    kiểu ngày). Dùng phạm vi Manager (customer X, Y) để đồng thời xác nhận
    RBAC cũng áp dụng cho hàm trend: tuần "2026-07" (chứa order_z2 của
    customer Z, ngoài phạm vi) không xuất hiện."""
    _register_sqlite_date_format(db_engine)
    scope = _manager_scope(db_engine, extra_status_orders)

    df = get_order_status_trend(scope, engine=db_engine, granularity="week")

    assert list(df.columns) == ["period", "status", "order_count"]
    # period giữ dạng chuỗi "YYYY-Www" — không ép datetime64 như granularity
    # "month" (1 tuần ISO không map 1-1 sang 1 ngày cụ thể).
    assert df["period"].map(type).eq(str).all()

    rows = {
        (period, status): int(count)
        for period, status, count in zip(df["period"], df["status"], df["order_count"])
    }
    assert rows == {
        ("2026-02", "Đang vận chuyển"): 2,  # order_x (01-10) + order_y (01-11)
        ("2026-03", "Huỷ"): 1,  # order_x2 (01-15)
        ("2026-04", "Đã giao"): 1,  # order_y2 (01-20)
        ("2026-06", "Mới tạo"): 1,  # order_x3 (02-05)
    }
    assert "2026-07" not in df["period"].values  # order_z2 (customer Z) loại trừ
    assert int(df["order_count"].sum()) == 5
    # period đã sắp xếp tăng dần đúng thứ tự thời gian (so sánh chuỗi vẫn
    # đúng nhờ zero-pad 2 chữ số).
    assert list(df["period"]) == sorted(df["period"])


def test_get_order_status_trend_invalid_granularity_raises_value_error():
    """`granularity` khác `"month"`/`"week"` -> `ValueError`, kiểm tra xảy
    ra TRƯỚC khi chạm DB (không cần fixture `db_engine`/`extra_status_orders`
    — hàm raise ngay ở đầu, trước dòng `engine = engine or get_engine()`)."""
    scope = DataScope(
        user_id=1,
        username="irrelevant",
        role=UserRole.ADMIN,
        employee_id=None,
        department_id=None,
        division_id=None,
        classification_hint=None,
        customer_ids=frozenset(),
        unrestricted=True,
        description="test",
    )

    with pytest.raises(ValueError):
        get_order_status_trend(scope, granularity="quarter")


def test_get_order_status_trend_empty_scope_returns_empty_dataframe(db_engine):
    """Phạm vi rỗng (User không gắn `employee_id`) -> DataFrame rỗng đúng
    cột, nhánh này trả về TRƯỚC khi build câu `date_format` nên không cần
    đăng ký `_register_sqlite_date_format`."""
    user_id = _create_user(
        db_engine, username="orphan_trend", role=UserRole.USER, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is False
    assert scope.customer_ids == frozenset()

    df = get_order_status_trend(scope, engine=db_engine, granularity="month")

    assert df.empty
    assert list(df.columns) == ["period", "status", "order_count"]
