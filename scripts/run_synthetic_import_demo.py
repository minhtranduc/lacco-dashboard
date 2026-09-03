"""Chạy import THẬT toàn bộ dữ liệu mẫu SYNTHETIC (17 file trong
`data/sample/`, sinh bởi `generate_synthetic_sample_data.py`) vào MySQL
"lacco" bằng framework `src/services/import_pipeline.py`, rồi demo 1 file
lỗi cố ý để chứng minh pipeline báo lỗi rõ ràng — bước 2.4.

Ghi chú quan trọng về thứ tự bootstrap:

`import_history.imported_by` là FK NOT NULL tới `users.id` — nghĩa là để
ghi log cho NGAY CẢ lần import đầu tiên (bảng `division`), đã cần có sẵn
ít nhất 1 user tồn tại. Nhưng bảng `users` (dữ liệu mẫu synthetic 20 dòng)
lại nằm SAU trong thứ tự phụ thuộc khoá ngoại nghiệp vụ (users.employee_id
tham chiếu `employee`, `employee` tham chiếu `department`...). Đây là bài
toán "con gà quả trứng" thuần kỹ thuật, KHÔNG phải lỗi thiết kế ERD.

Giải quyết bằng cách tạo 1 "system bootstrap user" TRỰC TIẾP bằng
SQLAlchemy (không qua pipeline file-based, không qua Pandera) — tương tự
cách nhiều hệ thống thật có 1 tài khoản seed/admin kỹ thuật khởi tạo ngoài
luồng dữ liệu nghiệp vụ thông thường. Tài khoản này idempotent (script
chạy lại nhiều lần không tạo trùng) và được ghi 1 dòng vào `import_history`
(tự tham chiếu chính nó ở `imported_by`) để không có "lỗ hổng" trong lịch
sử import.

Chạy: `python scripts/run_synthetic_import_demo.py`
"""

from __future__ import annotations

from pathlib import Path

import bcrypt
import pandas as pd
from loguru import logger
from sqlalchemy import insert, select, text

from src.db.models.security import ImportHistory, User
from src.services.db_connection import get_engine
from src.services.import_pipeline import (
    STATUS_SUCCESS,
    log_import_history,
    run_import,
)
from src.services.import_schemas.registry import ORDERED_TABLE_NAMES

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
BOOTSTRAP_USERNAME = "system_import_bootstrap"

# Toàn bộ 18 bảng ERD — tất cả trừ import_history đều có file mẫu.
ALL_18_TABLES = (*ORDERED_TABLE_NAMES, "import_history")


def ensure_bootstrap_user(engine) -> int:
    """Tạo (nếu chưa có) 1 user hệ thống dùng LÀM `imported_by` cho các
    lần import đầu tiên, trước khi bảng `users` thật được import.

    KHÔNG dùng để đăng nhập thật — `password_hash` là bcrypt hash của 1
    chuỗi ngẫu nhiên không lưu lại ở đâu khác, chỉ để thoả ràng buộc NOT
    NULL của cột `password_hash`.
    """
    with engine.connect() as conn:
        existing_id = conn.execute(
            select(User.id).where(User.username == BOOTSTRAP_USERNAME)
        ).scalar()
    if existing_id is not None:
        logger.info(
            "Bootstrap user '{}' đã tồn tại (id={}), không tạo lại.",
            BOOTSTRAP_USERNAME,
            existing_id,
        )
        return existing_id

    # Chuỗi cố định, KHÔNG phải mật khẩu thật — tài khoản này không dùng để
    # đăng nhập, chỉ tồn tại để thoả NOT NULL của password_hash.
    password_hash = bcrypt.hashpw(
        b"SYSTEM_BOOTSTRAP_NOT_A_REAL_PASSWORD", bcrypt.gensalt()
    ).decode()
    with engine.begin() as conn:
        result = conn.execute(
            insert(User.__table__).values(
                username=BOOTSTRAP_USERNAME,
                password_hash=password_hash,
                role="Admin",
                employee_id=None,
                is_active=True,
            )
        )
        user_id = result.inserted_primary_key[0]

    log_import_history(
        engine,
        file_name="(bootstrap - không qua file, tự tạo bởi script)",
        import_type="system_bootstrap",
        row_count=1,
        error_count=0,
        status=STATUS_SUCCESS,
        imported_by=user_id,
    )
    logger.info("Đã tạo bootstrap user '{}' (id={}).", BOOTSTRAP_USERNAME, user_id)
    return user_id


def build_file_map() -> dict[str, Path]:
    file_map: dict[str, Path] = {}
    for table_name in ORDERED_TABLE_NAMES:
        csv_path = SAMPLE_DIR / f"synthetic_{table_name}.csv"
        xlsx_path = SAMPLE_DIR / f"synthetic_{table_name}.xlsx"
        if xlsx_path.exists():
            file_map[table_name] = xlsx_path
        elif csv_path.exists():
            file_map[table_name] = csv_path
        else:
            raise FileNotFoundError(
                f"Không tìm thấy file mẫu cho bảng '{table_name}' trong "
                f"{SAMPLE_DIR} (đã chạy generate_synthetic_sample_data.py "
                "chưa?)."
            )
    return file_map


def make_error_demo_files() -> tuple[Path, Path]:
    """Tạo 2 file dữ liệu mẫu CÓ LỖI CỐ Ý (dựa trên `synthetic_department`)
    để demo 2 tầng validate khác nhau của pipeline báo lỗi rõ ràng (bước
    2.4, mục 8) — tách riêng để mỗi demo thể hiện đúng 1 tầng lỗi:

    1. `..._LOI_THIEU_COT.csv`: dòng 2 thiếu giá trị `name` (rỗng ->
       pandas đọc thành NaN) -> vi phạm ràng buộc not-null của Pandera
       (tầng 2 — validate cấu trúc/kiểu dữ liệu, CHƯA cần chạm DB).
    2. `..._LOI_FK.csv`: dữ liệu qua được Pandera (đủ cột, đúng kiểu, name
       khác rỗng) nhưng `division_id=9999` không tồn tại trong bảng cha
       `division` -> vi phạm `check_foreign_keys()` (tầng 3 — query DB
       thật, đúng yêu cầu bước 2.4: "kiểm tra bằng query thật vào DB,
       không chỉ kiểm tra kiểu dữ liệu").
    """
    missing_col_df = pd.DataFrame(
        {
            "id": [9001, 9002],
            "name": ["Phòng Demo Hợp Lệ", ""],
            "division_id": [1, 2],
        }
    )
    missing_col_path = SAMPLE_DIR / "synthetic_department_LOI_THIEU_COT.csv"
    missing_col_df.to_csv(missing_col_path, index=False, encoding="utf-8")

    fk_df = pd.DataFrame(
        {
            "id": [9101, 9102],
            "name": ["Phòng Demo Hợp Lệ 2", "Phòng Lỗi Demo FK"],
            "division_id": [1, 9999],
        }
    )
    fk_path = SAMPLE_DIR / "synthetic_department_LOI_FK.csv"
    fk_df.to_csv(fk_path, index=False, encoding="utf-8")

    return missing_col_path, fk_path


def print_table_counts(engine) -> None:
    print("\n=== SELECT COUNT(*) toàn bộ 18 bảng sau khi import ===")
    with engine.connect() as conn:
        for table_name in ALL_18_TABLES:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            print(f"  {table_name:<35} {count}")


def print_recent_import_history(engine, limit: int = 10) -> None:
    print(f"\n=== {limit} dòng gần nhất trong import_history ===")
    with engine.connect() as conn:
        rows = conn.execute(
            select(ImportHistory).order_by(ImportHistory.id.desc()).limit(limit)
        ).all()
    for row in reversed(rows):
        print(
            f"  id={row.id} file={row.file_name!r} import_type={row.import_type} "
            f"row_count={row.row_count} error_count={row.error_count} "
            f"status={row.status} imported_by={row.imported_by} "
            f"imported_at={row.imported_at}"
        )


def main() -> None:
    engine = get_engine()
    bootstrap_user_id = ensure_bootstrap_user(engine)

    file_map = build_file_map()

    print("\n=== Import 17 file dữ liệu mẫu (18 bảng - trừ import_history) ===")
    for table_name in ORDERED_TABLE_NAMES:
        result = run_import(
            file_map[table_name], table_name, bootstrap_user_id, engine=engine
        )
        marker = "OK" if result.success else "THAT BAI"
        print(
            f"  [{marker}] {table_name:<35} file={result.file_name} "
            f"rows={result.row_count} errors={result.error_count}"
        )
        if not result.success:
            for err in result.errors:
                print(f"      - {err}")

    print("\n=== Demo file loi co y (bang 'department') ===")
    missing_col_file, fk_file = make_error_demo_files()

    print("\n--- Demo 1: thieu gia tri cot bat buoc (Pandera not-null) ---")
    result_1 = run_import(
        missing_col_file, "department", bootstrap_user_id, engine=engine
    )
    print(f"file: {result_1.file_name}")
    print(f"status: {result_1.status}")
    print(f"row_count: {result_1.row_count}  error_count: {result_1.error_count}")
    print("Thong bao loi nguyen van:")
    for err in result_1.errors:
        print(f"  - {err}")

    print("\n--- Demo 2: khoa ngoai khong ton tai trong bang cha (query DB that) ---")
    result_2 = run_import(fk_file, "department", bootstrap_user_id, engine=engine)
    print(f"file: {result_2.file_name}")
    print(f"status: {result_2.status}")
    print(f"row_count: {result_2.row_count}  error_count: {result_2.error_count}")
    print("Thong bao loi nguyen van:")
    for err in result_2.errors:
        print(f"  - {err}")

    print_table_counts(engine)
    print_recent_import_history(engine, limit=10)


if __name__ == "__main__":
    main()
