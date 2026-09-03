"""Framework generic: import Excel/CSV → validate (Pandera) → load MySQL,
dùng CHUNG cho toàn bộ 18 bảng của Dashboard LACCO (bước 2.4).

Theo CLAUDE.md mục 2 (tách lớp 3 tầng): toàn bộ logic đọc file / validate /
load nằm ở `src/services/` (module này), KHÔNG nằm trong `src/db/` (nơi đó
chỉ định nghĩa SQLAlchemy model, không được import pandas/openpyxl).

Luồng xử lý cho MỖI lần gọi `run_import()`:

    1. Đọc file (.csv/.xlsx/.xls) thành pandas DataFrame.
    2. Validate bằng Pandera schema tương ứng (`src/services/import_schemas/`),
       `lazy=True` để gom hết lỗi thay vì dừng ở lỗi đầu tiên.
    3. Nếu qua bước 2: kiểm tra khoá ngoại có THỰC SỰ tồn tại trong bảng cha
       bằng truy vấn DB thật (`check_foreign_keys`) — không chỉ dựa vào
       kiểu dữ liệu int như Pandera ở bước 2.
    4. Nếu qua bước 3: insert TOÀN BỘ dòng vào bảng đích trong 1 transaction
       duy nhất — theo kiểu "tất cả hoặc không" (all-or-nothing) cho MỖI
       file: 1 dòng lỗi chặn cả file, để tránh trạng thái dữ liệu nửa vời
       (một phần dòng đã insert, một phần bị bỏ qua) khó dò lại sau này.
       Đây là lựa chọn thiết kế của bước 2.4; giá trị status `"partial"`
       (xem `STATUS_PARTIAL`) được định nghĩa sẵn cho khả năng mở rộng
       sau này (insert từng dòng hợp lệ, bỏ qua dòng lỗi) nếu nghiệp vụ
       xác nhận chấp nhận được — HIỆN TẠI logic chưa tạo ra trạng thái này.
    5. LUÔN ghi đúng 1 dòng vào `import_history` — dù thành công hay thất
       bại ở bất kỳ bước nào (1-4) — theo yêu cầu bước 2.4.

Không dùng bare `except` (CLAUDE.md mục 4) — mỗi bước chỉ bắt các loại lỗi
cụ thể có thể xảy ra ở bước đó. Lỗi nằm ngoài dự liệu (bug thật, VD lỗi lập
trình) sẽ tiếp tục ném lên cho người gọi thấy, KHÔNG bị nuốt âm thầm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from loguru import logger
from sqlalchemy import Engine, insert, select
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from src.db.models.security import ImportHistory
from src.services.db_connection import get_engine
from src.services.import_schemas.registry import (
    IMPORT_REGISTRY,
    ORDERED_TABLE_NAMES,
    ImportTableConfig,
)

# Giá trị `import_history.status` — cột này là String placeholder trong
# model (danh sách giá trị cụ thể CHƯA được COO xác nhận, xem mục 8 "Việc
# cần xác nhận" trong docs/architecture/erd-tuan-02.md). Đây là GIẢ ĐỊNH
# giá trị cụ thể do bước 2.4 tự chọn để có thể code pipeline, tương tự cách
# xử lý mục 8 ở bước 2.2 cho các placeholder khác — không phải xác nhận
# chính thức, có thể đổi lại nếu COO chốt danh sách khác.
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_PARTIAL = "partial"  # reserved — xem ghi chú ở đầu file, chưa dùng.

_SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls")


class ImportPipelineError(Exception):
    """Lỗi ở cấp file (đọc file thất bại) — KHÔNG phải lỗi validate dữ liệu
    theo từng dòng (những lỗi đó dùng `ImportRowError` + `SchemaErrors`).
    """


@dataclass(frozen=True)
class ImportRowError:
    """1 lỗi cụ thể phát hiện được khi validate hoặc kiểm tra khoá ngoại.

    Luôn có đủ thông tin để người vận hành tra cứu lại đúng dòng/cột lỗi
    trong file gốc (CLAUDE.md mục 4 — không nuốt lỗi âm thầm).
    """

    row_number: int | None  # số dòng trong file gốc (header=1, data từ 2).
    column: str | None
    error_type: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - phục vụ log/hiển thị
        loc = f"dòng {self.row_number}" if self.row_number else "(không xác định dòng)"
        col = f"cột '{self.column}'" if self.column else "(không xác định cột)"
        return f"[{loc}, {col}, loại lỗi={self.error_type}] {self.message}"


@dataclass(frozen=True)
class ImportResult:
    """Kết quả 1 lần chạy `run_import()` — luôn trả về, kể cả khi thất bại."""

    file_name: str
    table_name: str
    status: str
    row_count: int
    error_count: int
    errors: tuple[ImportRowError, ...]

    @property
    def success(self) -> bool:
        return self.status == STATUS_SUCCESS


# ---------------------------------------------------------------------------
# Bước 1: đọc file
# ---------------------------------------------------------------------------


def read_import_file(file_path: Path) -> pd.DataFrame:
    """Đọc file `.csv`/`.xlsx`/`.xls` thành `pandas.DataFrame`.

    Raises:
        ImportPipelineError: file không tồn tại, định dạng không hỗ trợ,
            file rỗng, hoặc file bị hỏng/sai định dạng — luôn kèm tên file
            và lý do cụ thể trong thông báo lỗi.
    """
    suffix = file_path.suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise ImportPipelineError(
            f"Định dạng file không được hỗ trợ: '{suffix}' (file "
            f"'{file_path.name}'). Chỉ hỗ trợ: {', '.join(_SUPPORTED_EXTENSIONS)}."
        )
    try:
        if suffix == ".csv":
            return pd.read_csv(file_path)
        return pd.read_excel(file_path)
    except FileNotFoundError as exc:
        raise ImportPipelineError(
            f"Không tìm thấy file import: '{file_path}'."
        ) from exc
    except pd.errors.EmptyDataError as exc:
        raise ImportPipelineError(
            f"File '{file_path.name}' rỗng, không có dữ liệu để import."
        ) from exc
    except pd.errors.ParserError as exc:
        raise ImportPipelineError(
            f"File '{file_path.name}' bị lỗi định dạng CSV, không đọc được: {exc}"
        ) from exc
    except OSError as exc:
        # VD file Excel bị hỏng (zipfile.BadZipFile là subclass của OSError
        # khi openpyxl mở file .xlsx lỗi), hoặc lỗi quyền truy cập file.
        raise ImportPipelineError(
            f"Không đọc được file '{file_path.name}': {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Bước 2: validate bằng Pandera
# ---------------------------------------------------------------------------


def format_schema_errors(exc: pa.errors.SchemaErrors) -> list[ImportRowError]:
    """Chuyển `pandera.errors.SchemaErrors.failure_cases` (DataFrame nội bộ
    của Pandera) thành danh sách `ImportRowError` dễ đọc — luôn kèm số
    dòng, tên cột, loại lỗi (CLAUDE.md mục 4).
    """
    errors: list[ImportRowError] = []
    for _, case in exc.failure_cases.iterrows():
        idx = case["index"]
        row_number = int(idx) + 2 if pd.notna(idx) else None
        column = case["column"] if pd.notna(case["column"]) else None
        check = case["check"]
        failure_case = case["failure_case"]

        if check == "column_in_dataframe":
            column = str(failure_case)
            message = f"Thiếu cột bắt buộc '{column}' trong file."
        elif check == "column_in_schema":
            column = str(failure_case)
            message = (
                f"Cột lạ '{column}' không nằm trong schema — file có thể "
                "sai định dạng hoặc gõ nhầm tên cột."
            )
        elif isinstance(check, str) and check.startswith("coerce_dtype"):
            message = (
                f"Không ép được kiểu dữ liệu ở cột '{column}': giá trị "
                f"'{failure_case}' không hợp lệ."
            )
        else:
            message = (
                f"Vi phạm ràng buộc '{check}' tại cột '{column}': giá trị "
                f"'{failure_case}'."
            )

        errors.append(
            ImportRowError(
                row_number=row_number,
                column=column,
                error_type=str(check),
                message=message,
            )
        )
    return errors


# ---------------------------------------------------------------------------
# Bước 3: kiểm tra khoá ngoại bằng query DB thật
# ---------------------------------------------------------------------------


def check_foreign_keys(
    df: pd.DataFrame, config: ImportTableConfig, engine: Engine
) -> list[ImportRowError]:
    """Kiểm tra mọi giá trị FK trong file có tồn tại thật trong bảng cha.

    KHÔNG chỉ dựa vào kiểu dữ liệu (Pandera ở bước 2 chỉ đảm bảo là số
    nguyên dương) — ở đây query thật vào MySQL để chắc chắn giá trị đó có
    tồn tại, theo đúng yêu cầu bước 2.4 (VD: `sales_order.customer_id` phải
    tồn tại trong bảng `customer`).
    """
    errors: list[ImportRowError] = []
    for column, ref_model in config.foreign_keys.items():
        if column not in df.columns:
            continue
        non_null = df[column].dropna()
        if non_null.empty:
            continue
        candidate_ids = {int(v) for v in non_null.unique()}
        with engine.connect() as conn:
            existing_ids = set(
                conn.execute(
                    select(ref_model.id).where(ref_model.id.in_(candidate_ids))
                )
                .scalars()
                .all()
            )
        missing_ids = candidate_ids - existing_ids
        if not missing_ids:
            continue
        ref_table = ref_model.__tablename__
        mask = df[column].isin(missing_ids)
        for idx, value in df.loc[mask, column].items():
            errors.append(
                ImportRowError(
                    row_number=int(idx) + 2,
                    column=column,
                    error_type="foreign_key_not_found",
                    message=(
                        f"Giá trị {column}={int(value)} không tồn tại "
                        f"trong bảng cha '{ref_table}' (cột id)."
                    ),
                )
            )
    return errors


# ---------------------------------------------------------------------------
# Bước 4: chuẩn bị & insert dữ liệu
# ---------------------------------------------------------------------------


def _to_native(value: object) -> object:
    """Chuyển giá trị pandas/numpy về kiểu Python thuần (hoặc `None` nếu
    thiếu dữ liệu) để `mysql-connector-python` nhận đúng khi insert.
    """
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def prepare_records_for_insert(
    df: pd.DataFrame, config: ImportTableConfig
) -> list[dict]:
    """Chuyển DataFrame đã validate thành list[dict] sẵn sàng insert.

    - Cột kiểu ngày (`datetime64`) → `datetime.date` (khớp cột `Date` của
      SQLAlchemy model).
    - Cột khai báo trong `config.decimal_columns` → `decimal.Decimal` (khớp
      cột `Numeric` của model, tránh sai số nhị phân của `float`).
    - Giá trị thiếu (NaN/NaT/`pd.NA`) → `None` (khớp `nullable=True` của
      model, để MySQL ghi NULL thay vì chuỗi "nan").
    """
    work = df.copy()
    for col in work.columns:
        if pd.api.types.is_datetime64_any_dtype(work[col]):
            work[col] = work[col].dt.date
    for col in config.decimal_columns:
        if col in work.columns:
            work[col] = work[col].apply(
                lambda v: Decimal(str(v)) if pd.notna(v) else None
            )

    records = work.to_dict(orient="records")
    return [{k: _to_native(v) for k, v in rec.items()} for rec in records]


def insert_rows(records: list[dict], config: ImportTableConfig, engine: Engine) -> None:
    """Insert toàn bộ `records` vào bảng đích trong 1 transaction duy nhất.

    Dùng `sqlalchemy.insert()` (Core, parameterized) — tuân thủ CLAUDE.md
    mục 4: cấm nối chuỗi SQL thủ công dưới mọi hình thức.
    """
    if not records:
        return
    table = config.model.__table__
    with engine.begin() as conn:
        conn.execute(insert(table), records)


# ---------------------------------------------------------------------------
# Bước 5: ghi import_history
# ---------------------------------------------------------------------------


def log_import_history(
    engine: Engine,
    *,
    file_name: str,
    import_type: str,
    row_count: int,
    error_count: int,
    status: str,
    imported_by: int,
) -> None:
    """Ghi đúng 1 dòng vào `import_history` — gọi ở MỌI nhánh kết thúc của
    `run_import()`, kể cả khi thất bại (yêu cầu bắt buộc bước 2.4).
    """
    table = ImportHistory.__table__
    with engine.begin() as conn:
        conn.execute(
            insert(table),
            [
                {
                    "file_name": file_name,
                    "import_type": import_type,
                    "row_count": row_count,
                    "error_count": error_count,
                    "status": status,
                    "imported_by": imported_by,
                }
            ],
        )


def _log_errors(file_name: str, table_name: str, errors: list[ImportRowError]) -> None:
    logger.error(
        "Import '{}' -> bảng '{}' THẤT BẠI: {} lỗi.",
        file_name,
        table_name,
        len(errors),
    )
    for err in errors:
        logger.error(
            "  file={} dong={} cot={} loai_loi={} : {}",
            file_name,
            err.row_number,
            err.column,
            err.error_type,
            err.message,
        )


# ---------------------------------------------------------------------------
# Orchestrator chính — dùng chung cho cả 18 bảng
# ---------------------------------------------------------------------------


def run_import(
    file_path: str | Path,
    table_name: str,
    imported_by: int,
    *,
    engine: Engine | None = None,
) -> ImportResult:
    """Chạy toàn bộ pipeline (đọc → validate → kiểm tra FK → insert → log)
    cho 1 file, ứng với 1 bảng trong `IMPORT_REGISTRY`.

    Đây là hàm CORE duy nhất dùng chung cho cả 18 bảng — khác biệt giữa các
    bảng chỉ nằm ở `table_name` (tra cứu cấu hình tương ứng trong
    `IMPORT_REGISTRY`), KHÔNG có 18 hàm import riêng lẻ.

    Args:
        file_path: đường dẫn file `.csv`/`.xlsx`/`.xls`.
        table_name: tên bảng đích, PHẢI có trong `IMPORT_REGISTRY`.
        imported_by: `users.id` của người/tài khoản thực hiện import (ghi
            vào `import_history.imported_by`, cột NOT NULL).
        engine: SQLAlchemy Engine tuỳ chọn (mặc định dùng
            `get_engine()` — tự đọc `.env`).

    Returns:
        `ImportResult` — LUÔN trả về (không raise ra ngoài trong các
        trường hợp lỗi dữ liệu đã lường trước), kèm `status`
        success/failed và danh sách lỗi chi tiết nếu có.
    """
    file_path = Path(file_path)
    engine = engine or get_engine()

    if table_name not in IMPORT_REGISTRY:
        raise KeyError(
            f"Không có cấu hình import cho bảng '{table_name}'. Danh sách "
            f"bảng hợp lệ: {', '.join(IMPORT_REGISTRY)}."
        )
    config = IMPORT_REGISTRY[table_name]

    # --- Bước 1: đọc file ---
    try:
        df = read_import_file(file_path)
    except ImportPipelineError as exc:
        logger.error(
            "Import '{}' -> bảng '{}' THẤT BẠI khi đọc file: {}",
            file_path.name,
            table_name,
            exc,
        )
        log_import_history(
            engine,
            file_name=file_path.name,
            import_type=table_name,
            row_count=0,
            error_count=1,
            status=STATUS_FAILED,
            imported_by=imported_by,
        )
        return ImportResult(
            file_name=file_path.name,
            table_name=table_name,
            status=STATUS_FAILED,
            row_count=0,
            error_count=1,
            errors=(
                ImportRowError(
                    row_number=None,
                    column=None,
                    error_type="file_read_error",
                    message=str(exc),
                ),
            ),
        )

    total_rows = len(df)

    # --- Bước 2: validate bằng Pandera ---
    try:
        config.schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        errors = format_schema_errors(exc)
        _log_errors(file_path.name, table_name, errors)
        log_import_history(
            engine,
            file_name=file_path.name,
            import_type=table_name,
            row_count=total_rows,
            error_count=len(errors),
            status=STATUS_FAILED,
            imported_by=imported_by,
        )
        return ImportResult(
            file_name=file_path.name,
            table_name=table_name,
            status=STATUS_FAILED,
            row_count=total_rows,
            error_count=len(errors),
            errors=tuple(errors),
        )

    # --- Bước 3: kiểm tra khoá ngoại thật trong DB ---
    fk_errors = check_foreign_keys(df, config, engine)
    if fk_errors:
        _log_errors(file_path.name, table_name, fk_errors)
        log_import_history(
            engine,
            file_name=file_path.name,
            import_type=table_name,
            row_count=total_rows,
            error_count=len(fk_errors),
            status=STATUS_FAILED,
            imported_by=imported_by,
        )
        return ImportResult(
            file_name=file_path.name,
            table_name=table_name,
            status=STATUS_FAILED,
            row_count=total_rows,
            error_count=len(fk_errors),
            errors=tuple(fk_errors),
        )

    # --- Bước 4: insert ---
    records = prepare_records_for_insert(df, config)
    try:
        insert_rows(records, config, engine)
    except (IntegrityError, DataError, OperationalError) as exc:
        message = (
            f"Lỗi khi ghi vào bảng '{table_name}' từ file "
            f"'{file_path.name}': {exc.__class__.__name__}: {exc}"
        )
        logger.error(message)
        log_import_history(
            engine,
            file_name=file_path.name,
            import_type=table_name,
            row_count=total_rows,
            error_count=total_rows,
            status=STATUS_FAILED,
            imported_by=imported_by,
        )
        return ImportResult(
            file_name=file_path.name,
            table_name=table_name,
            status=STATUS_FAILED,
            row_count=total_rows,
            error_count=total_rows,
            errors=(
                ImportRowError(
                    row_number=None,
                    column=None,
                    error_type="db_insert_error",
                    message=message,
                ),
            ),
        )

    # --- Bước 5: log thành công ---
    logger.info(
        "Import '{}' -> bảng '{}' THÀNH CÔNG: {} dòng.",
        file_path.name,
        table_name,
        total_rows,
    )
    log_import_history(
        engine,
        file_name=file_path.name,
        import_type=table_name,
        row_count=total_rows,
        error_count=0,
        status=STATUS_SUCCESS,
        imported_by=imported_by,
    )
    return ImportResult(
        file_name=file_path.name,
        table_name=table_name,
        status=STATUS_SUCCESS,
        row_count=total_rows,
        error_count=0,
        errors=(),
    )


def run_all_imports(
    file_map: dict[str, str | Path],
    imported_by: int,
    *,
    engine: Engine | None = None,
) -> list[ImportResult]:
    """Chạy `run_import()` tuần tự cho nhiều bảng, theo đúng thứ tự phụ
    thuộc khoá ngoại (`ORDERED_TABLE_NAMES`) — bỏ qua bảng không có trong
    `file_map`. Tiếp tục chạy các bảng còn lại dù 1 bảng thất bại (mỗi bảng
    độc lập, tự ghi log riêng) — người gọi tự kiểm tra `.success` của từng
    kết quả trả về.
    """
    engine = engine or get_engine()
    results: list[ImportResult] = []
    for table_name in ORDERED_TABLE_NAMES:
        if table_name not in file_map:
            continue
        result = run_import(
            file_map[table_name], table_name, imported_by, engine=engine
        )
        results.append(result)
    return results
