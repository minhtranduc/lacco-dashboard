"""Test `src/services/report_khach_hang.py` — báo cáo Khách hàng:
"Tăng giảm loại KH (A/B/C)" (`get_classification_trend`) và "Theo nguồn
khách hàng" (`get_source_distribution`).

Theo CLAUDE.md mục 2 (tách lớp): 2 hàm này chứa toàn bộ truy vấn SQLAlchemy
+ tính KPI cho báo cáo Khách hàng, tách khỏi trang Streamlit — test ở đây
gọi thẳng hàm service, không qua UI.

Theo CLAUDE.md mục 6 + `.claude/rules/trang-thai-yeu-cau.md` (nhóm "Khách
hàng", cả 2 dòng "Đã rõ" 17/08/2026):
- "Tăng giảm loại KH (A/B/C)" dùng cột "Phân loại"/`CustomerClassificationHistory`
  (khác `Customer.current_classification` chỉ lưu trạng thái hiện tại).
- "Theo nguồn khách hàng" dùng `Customer.source`.
- Cả 2 hàm PHẢI lọc theo `scope.customer_ids`, TRỪ KHI `scope.unrestricted`
  (Admin) — dùng `DataScope`/`compute_data_scope()` thật, không tự viết
  logic phân quyền riêng trong test.

Quyết định "loại trừ đơn `sales_order.status='Huỷ'` khỏi tổng doanh thu/lãi
lỗ" (CLAUDE.md mục 7) ĐÃ ĐƯỢC XÉT nhưng KHÔNG áp dụng ở đây — module này
không đụng tới `sales_order.status`/doanh thu, chỉ đếm số lượng khách hàng
theo phân loại/nguồn, nên không có test nào cho quy tắc đó trong file này.

Dùng fixture `db_engine` (SQLite in-memory) và `seeded_scope_data` (từ
`tests/conftest.py`, xem `tests/auth/test_scope.py` cho pattern gốc) —
KHÔNG kết nối MySQL "lacco" thật. `seeded_scope_data` seed sẵn
customer_x/y/z gắn với employee_user/employee_manager/employee_outsider
qua `sales_order`, tái sử dụng được cho test `scope.customer_ids` ở đây vì
`compute_data_scope()` suy ra `customer_ids` giống hệt bất kể module báo
cáo nào tiêu thụ nó. `seeded_scope_data` không set `Customer.source` — các
test về nguồn khách hàng tự set/seed thêm khi cần.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from src.auth.scope import compute_data_scope
from src.db.models.business import CustomerClassificationHistory
from src.db.models.dimension import Customer
from src.db.models.enums import CustomerClassification, UserRole
from src.db.models.security import User
from src.services import report_khach_hang
from src.services.report_khach_hang import (
    UNKNOWN_SOURCE_LABEL,
    get_classification_trend,
    get_source_distribution,
)


def _create_user(
    engine, *, username: str, role: UserRole, employee_id: int | None
) -> int:
    """Tạo 1 user tối thiểu qua ORM — giống hệt helper trong
    `tests/auth/test_scope.py`, nhân bản lại ở đây vì mỗi file test tự seed
    dữ liệu tối thiểu của mình (theo pattern `tests/auth/test_authentication.py`)."""
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


def _seed_customers(engine, specs: list[dict]) -> dict[str, int]:
    """Tạo nhiều `Customer` cùng lúc. Mỗi spec là dict với khoá `code`
    (bắt buộc), `source` (optional, mặc định None) và `classification`
    (optional, mặc định C — không ảnh hưởng test vì
    `get_classification_trend` đọc từ `CustomerClassificationHistory`, không
    phải `Customer.current_classification`).

    Trả về dict {code: id} để test dùng trực tiếp.
    """
    with Session(engine) as session:
        customers = [
            Customer(
                code=spec["code"],
                name=spec.get("name", spec["code"]),
                source=spec.get("source"),
                current_classification=spec.get(
                    "classification", CustomerClassification.C
                ),
            )
            for spec in specs
        ]
        session.add_all(customers)
        session.flush()
        ids = {c.code: c.id for c in customers}
        session.commit()
        return ids


def _seed_classification_history(
    engine, entries: list[tuple[int, date, CustomerClassification]]
) -> None:
    """Tạo nhiều dòng `CustomerClassificationHistory`. Mỗi entry là tuple
    `(customer_id, snapshot_date, classification)`."""
    with Session(engine) as session:
        session.add_all(
            [
                CustomerClassificationHistory(
                    customer_id=customer_id,
                    snapshot_date=snapshot_date,
                    classification=classification,
                )
                for customer_id, snapshot_date, classification in entries
            ]
        )
        session.commit()


def _set_customer_sources(engine, updates: dict[int, str | None]) -> None:
    """Cập nhật `Customer.source` cho các customer đã tồn tại (dùng để gán
    `source` cho customer_x/y/z của `seeded_scope_data`, fixture đó không
    set sẵn `source`)."""
    with Session(engine) as session:
        for customer_id, source in updates.items():
            customer = session.get(Customer, customer_id)
            customer.source = source
        session.commit()


def _get_count(
    df: pd.DataFrame, snapshot_date: date, classification: str
) -> int | None:
    """Trả về `so_luong_kh` của 1 dòng (snapshot_date, classification) cụ
    thể trong DataFrame trả về từ `get_classification_trend`, hoặc None nếu
    không có dòng nào khớp (khách hàng ngoài phạm vi bị loại hẳn khỏi kết
    quả, không phải giá trị 0)."""
    matched = df[
        (df["snapshot_date"] == snapshot_date)
        & (df["classification"] == classification)
    ]
    if matched.empty:
        return None
    return int(matched["so_luong_kh"].iloc[0])


def _boom_get_engine(*_args, **_kwargs):
    """Dùng làm patch cho `get_engine` — nếu bị gọi tức là hàm service đã
    không short-circuit đúng khi scope rỗng, phải truy vấn DB, vi phạm
    docstring hàm ("không truy vấn" khi scope rỗng và không unrestricted)."""
    raise AssertionError(
        "get_engine() không được gọi khi scope rỗng và không unrestricted"
    )


# ---------------------------------------------------------------------------
# get_classification_trend
# ---------------------------------------------------------------------------


def test_classification_trend_admin_sees_all_customers_across_snapshots(db_engine):
    """Admin (unrestricted) thấy đầy đủ số lượng KH theo A/B/C ở CẢ 2 mốc
    snapshot_date, tổng hợp từ toàn bộ khách hàng, không giới hạn phạm vi."""
    ids = _seed_customers(
        db_engine,
        [{"code": f"CUST-{i}"} for i in range(1, 5)],
    )
    date1, date2 = date(2026, 7, 1), date(2026, 8, 1)
    _seed_classification_history(
        db_engine,
        [
            (ids["CUST-1"], date1, CustomerClassification.A),
            (ids["CUST-2"], date1, CustomerClassification.A),
            (ids["CUST-3"], date1, CustomerClassification.B),
            (ids["CUST-4"], date1, CustomerClassification.C),
            (ids["CUST-1"], date2, CustomerClassification.B),
            (ids["CUST-2"], date2, CustomerClassification.A),
            (ids["CUST-3"], date2, CustomerClassification.B),
            (ids["CUST-4"], date2, CustomerClassification.C),
        ],
    )
    user_id = _create_user(
        db_engine, username="admin_ct", role=UserRole.ADMIN, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is True

    df = get_classification_trend(scope, engine=db_engine)

    assert len(df) == 6
    assert _get_count(df, date1, "A") == 2
    assert _get_count(df, date1, "B") == 1
    assert _get_count(df, date1, "C") == 1
    assert _get_count(df, date2, "A") == 1
    assert _get_count(df, date2, "B") == 2
    assert _get_count(df, date2, "C") == 1


def test_classification_trend_restricted_scope_excludes_out_of_scope_customer(
    db_engine, seeded_scope_data
):
    """Manager (phạm vi theo department_id, chỉ thấy customer_x/y của
    `seeded_scope_data`) KHÔNG được đếm lịch sử phân loại của customer_z —
    khách hàng nằm ngoài phạm vi phải bị loại hẳn khỏi kết quả, không phải
    đếm bằng 0."""
    snapshot = date(2026, 7, 1)
    _seed_classification_history(
        db_engine,
        [
            (seeded_scope_data["customer_x_id"], snapshot, CustomerClassification.A),
            (seeded_scope_data["customer_y_id"], snapshot, CustomerClassification.B),
            (seeded_scope_data["customer_z_id"], snapshot, CustomerClassification.C),
        ],
    )
    user_id = _create_user(
        db_engine,
        username="manager_ct",
        role=UserRole.MANAGER,
        employee_id=seeded_scope_data["emp_manager_id"],
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is False
    assert seeded_scope_data["customer_z_id"] not in scope.customer_ids

    df = get_classification_trend(scope, engine=db_engine)

    assert len(df) == 2
    assert _get_count(df, snapshot, "A") == 1
    assert _get_count(df, snapshot, "B") == 1
    # customer_z (classification "C") ngoài phạm vi -> không có dòng "C".
    assert _get_count(df, snapshot, "C") is None


def test_classification_trend_empty_scope_returns_empty_without_querying_db(
    db_engine, seeded_scope_data, monkeypatch
):
    """User không gắn employee_id -> `compute_data_scope()` trả
    `customer_ids` rỗng, không unrestricted -> `get_classification_trend`
    phải trả DataFrame rỗng (đúng cột) MÀ KHÔNG gọi `get_engine()` (patch
    `get_engine` để raise nếu bị gọi, xác minh short-circuit thật sự xảy ra
    trước khi chạm DB) — theo pattern
    `tests/auth/test_scope.py::test_user_without_employee_id_has_empty_scope`."""
    user_id = _create_user(
        db_engine, username="orphan_ct", role=UserRole.USER, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is False
    assert scope.customer_ids == frozenset()

    monkeypatch.setattr(report_khach_hang, "get_engine", _boom_get_engine)

    df = get_classification_trend(scope)

    assert list(df.columns) == ["snapshot_date", "classification", "so_luong_kh"]
    assert df.empty


def test_classification_trend_normalizes_enum_to_plain_string(db_engine):
    """Cột `classification` trả về phải là chuỗi Python thuần "A"/"B"/"C",
    không phải instance `CustomerClassification` — model dùng
    `Enum(..., native_enum=False)` nên SQLAlchemy trả về enum member, hàm
    service phải tự chuẩn hoá (`c.value if hasattr(c, "value") else c`)."""
    ids = _seed_customers(db_engine, [{"code": "CUST-ENUM"}])
    snapshot = date(2026, 7, 1)
    _seed_classification_history(
        db_engine, [(ids["CUST-ENUM"], snapshot, CustomerClassification.A)]
    )
    user_id = _create_user(
        db_engine, username="admin_enum", role=UserRole.ADMIN, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)

    df = get_classification_trend(scope, engine=db_engine)

    assert len(df) == 1
    value = df["classification"].iloc[0]
    assert value == "A"
    assert type(value) is str
    assert not isinstance(value, CustomerClassification)
    assert df["classification"].dtype == object


# ---------------------------------------------------------------------------
# get_source_distribution
# ---------------------------------------------------------------------------


def test_source_distribution_admin_sees_all_sources(db_engine):
    """Admin (unrestricted) thấy phân bố nguồn KH tổng hợp trên toàn bộ
    khách hàng, nhóm đúng theo giá trị `source`."""
    _seed_customers(
        db_engine,
        [
            {"code": "CUST-S1", "source": "Website"},
            {"code": "CUST-S2", "source": "Website"},
            {"code": "CUST-S3", "source": "Giới thiệu"},
        ],
    )
    user_id = _create_user(
        db_engine, username="admin_src", role=UserRole.ADMIN, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is True

    df = get_source_distribution(scope, engine=db_engine)

    website = df[df["source"] == "Website"]["so_luong_kh"].iloc[0]
    gioi_thieu = df[df["source"] == "Giới thiệu"]["so_luong_kh"].iloc[0]
    assert int(website) == 2
    assert int(gioi_thieu) == 1
    assert len(df) == 2


def test_source_distribution_restricted_scope_excludes_out_of_scope_customer(
    db_engine, seeded_scope_data
):
    """Manager (phạm vi theo department_id) KHÔNG được đếm customer_z (nguồn
    "Cold call", ngoài phạm vi) vào phân bố nguồn — chỉ đếm customer_x/y
    (cùng nguồn "Website")."""
    _set_customer_sources(
        db_engine,
        {
            seeded_scope_data["customer_x_id"]: "Website",
            seeded_scope_data["customer_y_id"]: "Website",
            seeded_scope_data["customer_z_id"]: "Cold call",
        },
    )
    user_id = _create_user(
        db_engine,
        username="manager_src",
        role=UserRole.MANAGER,
        employee_id=seeded_scope_data["emp_manager_id"],
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is False
    assert seeded_scope_data["customer_z_id"] not in scope.customer_ids

    df = get_source_distribution(scope, engine=db_engine)

    assert len(df) == 1
    assert df["source"].iloc[0] == "Website"
    assert int(df["so_luong_kh"].iloc[0]) == 2
    assert "Cold call" not in df["source"].values


def test_source_distribution_null_source_uses_unknown_label(db_engine):
    """`Customer.source IS NULL` phải được thay bằng `UNKNOWN_SOURCE_LABEL`
    ("Không xác định"), không để lộ `None`/NaN ra kết quả hiển thị."""
    _seed_customers(db_engine, [{"code": "CUST-NULL-SRC", "source": None}])
    user_id = _create_user(
        db_engine, username="admin_null_src", role=UserRole.ADMIN, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)

    df = get_source_distribution(scope, engine=db_engine)

    assert len(df) == 1
    assert df["source"].iloc[0] == UNKNOWN_SOURCE_LABEL
    assert int(df["so_luong_kh"].iloc[0]) == 1


def test_source_distribution_empty_scope_returns_empty_without_querying_db(
    db_engine, seeded_scope_data, monkeypatch
):
    """Cùng pattern với
    `test_classification_trend_empty_scope_returns_empty_without_querying_db`
    nhưng cho `get_source_distribution`: scope rỗng (User không gắn
    employee_id) -> DataFrame rỗng đúng cột, KHÔNG gọi `get_engine()`."""
    user_id = _create_user(
        db_engine, username="orphan_src", role=UserRole.USER, employee_id=None
    )
    scope = compute_data_scope(user_id, engine=db_engine)
    assert scope.unrestricted is False
    assert scope.customer_ids == frozenset()

    monkeypatch.setattr(report_khach_hang, "get_engine", _boom_get_engine)

    df = get_source_distribution(scope)

    assert list(df.columns) == ["source", "so_luong_kh"]
    assert df.empty


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.MANAGER])
def test_manager_and_user_without_employee_id_both_have_empty_scope(
    db_engine, seeded_scope_data, role
):
    """Sanity check bổ sung: cả Manager lẫn User không gắn employee_id đều
    rơi vào nhánh phạm vi rỗng giống nhau (không chỉ riêng User) — đảm bảo
    2 test "empty scope" ở trên không tình cờ chỉ đúng với 1 role cụ thể."""
    user_id = _create_user(
        db_engine, username=f"orphan_{role.value.lower()}", role=role, employee_id=None
    )

    scope = compute_data_scope(user_id, engine=db_engine)

    assert scope.unrestricted is False
    assert scope.customer_ids == frozenset()
