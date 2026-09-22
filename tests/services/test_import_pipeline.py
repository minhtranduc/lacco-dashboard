"""Test `src/services/import_pipeline.py` — framework import generic dùng
chung cho cả 18 bảng (bước 2.4, xem CLAUDE.md mục 2 "tách lớp": logic đọc
file/validate/insert thuộc `src/services/`, KHÔNG thuộc `src/db/`).

Theo docstring của module gốc, mỗi lần gọi `run_import()` chạy tuần tự 5
bước: (1) đọc file, (2) validate Pandera (`lazy=True`), (3) kiểm tra khoá
ngoại bằng query DB thật, (4) insert 1 transaction (tất cả-hoặc-không),
(5) LUÔN ghi đúng 1 dòng `import_history` dù thành công hay thất bại. Các
test dưới đây bao phủ cả 5 hàm thành phần (đơn vị) lẫn `run_import()` /
`run_all_imports()` (tích hợp đầu-cuối), dùng bảng `division` (không có
FK, đơn giản nhất trong `IMPORT_REGISTRY`) làm ca thành công chính, và
bảng `department` (đúng 1 FK: `division_id` -> `Division`) cho các ca lỗi
khoá ngoại — theo đúng gợi ý trong `src/services/import_schemas/registry.py`.

Dùng fixture `db_engine` (SQLite in-memory, xem `tests/conftest.py`) —
KHÔNG kết nối MySQL "lacco" thật. File CSV dùng cho `read_import_file()` /
`run_import()` được ghi THẬT xuống `tmp_path` (không mock I/O), theo đúng
tinh thần "không nuốt lỗi âm thầm, luôn kiểm chứng bằng dữ liệu thật" của
CLAUDE.md mục 4.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.hashing import hash_password
from src.db.models.dimension import Department, Division, Service
from src.db.models.enums import UserRole
from src.db.models.security import ImportHistory, User
from src.services.import_pipeline import (
    STATUS_FAILED,
    STATUS_SUCCESS,
    ImportPipelineError,
    ImportRowError,
    check_foreign_keys,
    format_schema_errors,
    insert_rows,
    log_import_history,
    prepare_records_for_insert,
    read_import_file,
    run_all_imports,
    run_import,
)
from src.services.import_schemas import dimension_schemas as ds
from src.services.import_schemas.registry import IMPORT_REGISTRY, ORDERED_TABLE_NAMES

PLAIN_PASSWORD = "mat-khau-test-123"


def _seed_user(engine) -> int:
    """Seed 1 user tối thiểu — `import_history.imported_by` là FK NOT NULL
    tới `users.id` (xem `src/db/models/security.py`), giống mẫu
    `_seed_user()` trong `tests/auth/test_authentication.py`."""
    with Session(engine) as session:
        user = User(
            username="import-tester",
            password_hash=hash_password(PLAIN_PASSWORD),
            role=UserRole.ADMIN,
            employee_id=None,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def _write_csv(tmp_path: Path, name: str, content: str) -> Path:
    """Ghi `content` (đã có header + dữ liệu) thành file CSV thật dưới
    `tmp_path` — không mock I/O, `run_import`/`read_import_file` đọc file
    thật này."""
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _division_rows(engine) -> list[Division]:
    with Session(engine) as session:
        return list(session.execute(select(Division)).scalars().all())


def _department_rows(engine) -> list[Department]:
    with Session(engine) as session:
        return list(session.execute(select(Department)).scalars().all())


def _service_rows(engine) -> list[Service]:
    with Session(engine) as session:
        return list(session.execute(select(Service)).scalars().all())


def _import_history_rows(engine) -> list[ImportHistory]:
    with Session(engine) as session:
        stmt = select(ImportHistory).order_by(ImportHistory.id)
        return list(session.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Bước 1: read_import_file
# ---------------------------------------------------------------------------


def test_read_import_file_reads_valid_csv(tmp_path):
    """Đọc thật 1 file `.csv` hợp lệ trên đĩa -> DataFrame đúng số dòng/cột."""
    path = _write_csv(
        tmp_path, "division.csv", "id,name\n1,Khối Kinh doanh\n2,Khối Vận hành\n"
    )

    df = read_import_file(path)

    assert list(df.columns) == ["id", "name"]
    assert len(df) == 2
    assert df.iloc[0]["name"] == "Khối Kinh doanh"


def test_read_import_file_unsupported_extension_raises(tmp_path):
    """Đuôi file không nằm trong `.csv`/`.xlsx`/`.xls` -> `ImportPipelineError`,
    ngay cả khi file thật sự tồn tại trên đĩa."""
    path = tmp_path / "division.txt"
    path.write_text("id,name\n1,Khối A\n", encoding="utf-8")

    with pytest.raises(ImportPipelineError, match="không được hỗ trợ"):
        read_import_file(path)


def test_read_import_file_missing_file_raises(tmp_path):
    """File không tồn tại trên đĩa (dù đuôi hợp lệ) -> `ImportPipelineError`."""
    path = tmp_path / "khong-ton-tai.csv"

    with pytest.raises(ImportPipelineError, match="Không tìm thấy file"):
        read_import_file(path)


def test_read_import_file_empty_csv_raises(tmp_path):
    """File `.csv` rỗng hoàn toàn (0 byte) -> `pd.errors.EmptyDataError` bên
    trong được bọc lại thành `ImportPipelineError`."""
    path = _write_csv(tmp_path, "rong.csv", "")

    with pytest.raises(ImportPipelineError, match="rỗng"):
        read_import_file(path)


# ---------------------------------------------------------------------------
# Bước 2: format_schema_errors
# ---------------------------------------------------------------------------


def test_format_schema_errors_returns_row_errors_with_correct_row_number():
    """Trigger `pandera.errors.SchemaErrors` THẬT (lazy=True) bằng DataFrame
    vi phạm `division_schema` ở dòng dữ liệu thứ 2 (`id=-1` vi phạm
    `gt(0)`, `name=""` vi phạm `str_length(min_value=1)`) -> mỗi lỗi phải
    ra đúng `row_number = index + 2` (dòng 1 là header, dòng data đầu tiên
    là dòng 2 trong file gốc)."""
    invalid_df = pd.DataFrame({"id": [1, -1], "name": ["Khối A", ""]})

    with pytest.raises(pa.errors.SchemaErrors) as exc_info:
        ds.division_schema.validate(invalid_df, lazy=True)

    errors = format_schema_errors(exc_info.value)

    assert len(errors) == 2
    assert all(isinstance(err, ImportRowError) for err in errors)
    assert {err.row_number for err in errors} == {3}
    assert {err.column for err in errors} == {"id", "name"}
    assert all(err.message for err in errors)


# ---------------------------------------------------------------------------
# Bước 3: check_foreign_keys
# ---------------------------------------------------------------------------


def test_check_foreign_keys_flags_only_row_with_missing_division(db_engine):
    """Seed 1 `Division` thật (id do DB tự sinh), build DataFrame
    `department` với 1 `division_id` hợp lệ và 1 `division_id` không tồn
    tại -> chỉ đúng dòng có `division_id` sai bị gắn cờ
    `error_type="foreign_key_not_found"`."""
    with Session(db_engine) as session:
        division = Division(name="Khối Kinh doanh")
        session.add(division)
        session.commit()
        session.refresh(division)
        valid_division_id = division.id

    missing_division_id = valid_division_id + 999
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["Phòng Hợp lệ", "Phòng Sai"],
            "division_id": [valid_division_id, missing_division_id],
        }
    )

    errors = check_foreign_keys(df, IMPORT_REGISTRY["department"], db_engine)

    assert len(errors) == 1
    assert errors[0].column == "division_id"
    assert errors[0].error_type == "foreign_key_not_found"
    assert errors[0].row_number == 3  # index 1 (dòng 2 dữ liệu) + 2
    assert str(missing_division_id) in errors[0].message


def test_check_foreign_keys_returns_empty_when_all_ids_exist(db_engine):
    """Mọi `division_id` trong file đều tồn tại thật trong bảng `division`
    -> không có lỗi nào được trả về."""
    with Session(db_engine) as session:
        div_a = Division(name="Khối A")
        div_b = Division(name="Khối B")
        session.add_all([div_a, div_b])
        session.commit()
        session.refresh(div_a)
        session.refresh(div_b)
        ids = [div_a.id, div_b.id]

    df = pd.DataFrame(
        {"id": [1, 2], "name": ["Phòng 1", "Phòng 2"], "division_id": ids}
    )

    errors = check_foreign_keys(df, IMPORT_REGISTRY["department"], db_engine)

    assert errors == []


# ---------------------------------------------------------------------------
# Bước 4: prepare_records_for_insert / insert_rows
# ---------------------------------------------------------------------------


def test_prepare_records_for_insert_converts_nan_datetime_and_decimal():
    """DataFrame có cột NaN, cột `datetime64` và cột khai báo trong
    `config.decimal_columns` (dùng `IMPORT_REGISTRY["cost"]`, decimal_columns
    = ("amount",)) -> NaN thành `None`, ngày thành `datetime.date`, tiền
    thành `decimal.Decimal`."""
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "division_id": [1, 2],
            "period": pd.to_datetime(["2026-01-01", "2026-02-01"]),
            "amount": [100.5, 200.75],
            "note": [None, "có ghi chú"],
        }
    )

    records = prepare_records_for_insert(df, IMPORT_REGISTRY["cost"])

    assert records[0]["note"] is None
    assert records[0]["period"] == date(2026, 1, 1)
    assert isinstance(records[0]["period"], date)
    assert records[0]["amount"] == Decimal("100.5")
    assert isinstance(records[0]["amount"], Decimal)
    assert records[1]["note"] == "có ghi chú"
    assert records[1]["amount"] == Decimal("200.75")


def test_insert_rows_inserts_records_visible_via_direct_query(db_engine):
    """`insert_rows()` ghi thật vào bảng `division` trong 1 transaction —
    query lại trực tiếp qua `Session` để xác nhận dữ liệu đã landed đúng."""
    records = [{"id": 1, "name": "Khối A"}, {"id": 2, "name": "Khối B"}]

    insert_rows(records, IMPORT_REGISTRY["division"], db_engine)

    rows = _division_rows(db_engine)
    assert {row.name for row in rows} == {"Khối A", "Khối B"}


def test_insert_rows_empty_list_is_noop(db_engine):
    """Gọi `insert_rows([], ...)` không được ném lỗi và không insert gì."""
    insert_rows([], IMPORT_REGISTRY["division"], db_engine)

    assert _division_rows(db_engine) == []


# ---------------------------------------------------------------------------
# Bước 5: log_import_history
# ---------------------------------------------------------------------------


def test_log_import_history_writes_expected_row(db_engine):
    """Gọi `log_import_history()` trực tiếp -> đúng 1 dòng `import_history`
    được ghi, đủ các trường truyền vào."""
    user_id = _seed_user(db_engine)

    log_import_history(
        db_engine,
        file_name="division.csv",
        import_type="division",
        row_count=2,
        error_count=0,
        status=STATUS_SUCCESS,
        imported_by=user_id,
    )

    rows = _import_history_rows(db_engine)
    assert len(rows) == 1
    assert rows[0].file_name == "division.csv"
    assert rows[0].import_type == "division"
    assert rows[0].row_count == 2
    assert rows[0].error_count == 0
    assert rows[0].status == STATUS_SUCCESS
    assert rows[0].imported_by == user_id


# ---------------------------------------------------------------------------
# run_import — end-to-end
# ---------------------------------------------------------------------------


def test_run_import_happy_path_division_success(tmp_path, db_engine):
    """Đường thành công đầu-cuối cho bảng `division` (không có FK, đơn giản
    nhất): file CSV hợp lệ -> `ImportResult.success is True`, đúng số
    dòng, 0 lỗi, có ghi `import_history` trạng thái success, VÀ dữ liệu
    thật đã landed trong bảng `division`."""
    user_id = _seed_user(db_engine)
    path = _write_csv(
        tmp_path,
        "division_ok.csv",
        "id,name\n1,Khối Kinh doanh\n2,Khối Vận hành\n",
    )

    result = run_import(path, "division", imported_by=user_id, engine=db_engine)

    assert result.success is True
    assert result.status == STATUS_SUCCESS
    assert result.row_count == 2
    assert result.error_count == 0
    assert result.errors == ()

    history = _import_history_rows(db_engine)
    assert len(history) == 1
    assert history[0].status == STATUS_SUCCESS
    assert history[0].row_count == 2

    rows = _division_rows(db_engine)
    assert {row.name for row in rows} == {"Khối Kinh doanh", "Khối Vận hành"}


def test_run_import_schema_validation_failure(tmp_path, db_engine):
    """File CSV thiếu cột bắt buộc (`name`) cho bảng `division` -> Pandera
    thất bại ở bước 2 -> `ImportResult.success is False`, có lỗi chi tiết,
    VẪN ghi đúng 1 dòng `import_history` trạng thái failed (yêu cầu "LUÔN
    ghi đúng 1 dòng dù thành công hay thất bại"), VÀ không có dòng nào
    được insert vào `division`."""
    user_id = _seed_user(db_engine)
    path = _write_csv(tmp_path, "division_thieu_cot.csv", "id\n1\n2\n")

    result = run_import(path, "division", imported_by=user_id, engine=db_engine)

    assert result.success is False
    assert result.status == STATUS_FAILED
    assert len(result.errors) > 0

    history = _import_history_rows(db_engine)
    assert len(history) == 1
    assert history[0].status == STATUS_FAILED

    assert _division_rows(db_engine) == []


def test_run_import_foreign_key_violation(tmp_path, db_engine):
    """File CSV `department` hợp lệ theo Pandera nhưng tham chiếu
    `division_id` không tồn tại thật trong DB -> thất bại ở bước 3
    (`check_foreign_keys`), lỗi mang `error_type="foreign_key_not_found"`,
    VẪN ghi `import_history` trạng thái failed, VÀ không insert dòng nào
    vào `department`."""
    user_id = _seed_user(db_engine)
    with Session(db_engine) as session:
        division = Division(name="Khối Kinh doanh")
        session.add(division)
        session.commit()
        session.refresh(division)
        valid_division_id = division.id
    missing_division_id = valid_division_id + 999

    path = _write_csv(
        tmp_path,
        "department_fk_sai.csv",
        f"id,name,division_id\n1,Phòng Sai,{missing_division_id}\n",
    )

    result = run_import(path, "department", imported_by=user_id, engine=db_engine)

    assert result.success is False
    assert result.status == STATUS_FAILED
    assert any(err.error_type == "foreign_key_not_found" for err in result.errors)

    history = _import_history_rows(db_engine)
    assert len(history) == 1
    assert history[0].status == STATUS_FAILED

    assert _department_rows(db_engine) == []


def test_run_import_unknown_table_name_raises_keyerror(tmp_path, db_engine):
    """`table_name` không có trong `IMPORT_REGISTRY` -> `KeyError` ném ra
    ngay, không phải `ImportResult` (đây là lỗi lập trình/config, không phải
    lỗi dữ liệu nghiệp vụ đã lường trước)."""
    path = tmp_path / "bat-ky.csv"

    with pytest.raises(KeyError):
        run_import(path, "bang_khong_ton_tai", imported_by=1, engine=db_engine)


def test_run_import_file_read_error_still_logs_history(tmp_path, db_engine):
    """File không tồn tại trên đĩa -> thất bại ngay ở bước 1 (đọc file) ->
    `ImportResult.success is False`, VẪN ghi `import_history` với
    `row_count=0`, `status=failed`."""
    user_id = _seed_user(db_engine)
    path = tmp_path / "khong-ton-tai.csv"

    result = run_import(path, "division", imported_by=user_id, engine=db_engine)

    assert result.success is False
    assert result.status == STATUS_FAILED
    assert result.row_count == 0

    history = _import_history_rows(db_engine)
    assert len(history) == 1
    assert history[0].status == STATUS_FAILED
    assert history[0].row_count == 0


# ---------------------------------------------------------------------------
# run_all_imports
# ---------------------------------------------------------------------------


def test_run_all_imports_processes_multiple_tables_in_registry_order(
    tmp_path, db_engine
):
    """2 file hợp lệ cho 2 bảng không phụ thuộc FK lẫn nhau (`division`,
    `service`) -> cả 2 `ImportResult` đều thành công, dữ liệu landed đúng
    ở cả 2 bảng, VÀ thứ tự kết quả trả về khớp thứ tự `ORDERED_TABLE_NAMES`
    (division đứng trước service trong registry)."""
    user_id = _seed_user(db_engine)
    division_path = _write_csv(
        tmp_path, "division_all.csv", "id,name\n1,Khối Kinh doanh\n"
    )
    service_path = _write_csv(
        tmp_path, "service_all.csv", "id,name\n1,Cước\n2,Hải quan\n"
    )
    assert ORDERED_TABLE_NAMES.index("division") < ORDERED_TABLE_NAMES.index("service")

    results = run_all_imports(
        {"division": division_path, "service": service_path},
        imported_by=user_id,
        engine=db_engine,
    )

    assert len(results) == 2
    assert [r.table_name for r in results] == ["division", "service"]
    assert all(r.success for r in results)

    assert {row.name for row in _division_rows(db_engine)} == {"Khối Kinh doanh"}
    assert {row.name for row in _service_rows(db_engine)} == {"Cước", "Hải quan"}
