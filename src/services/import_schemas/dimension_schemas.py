"""Pandera schema cho nhóm bảng danh mục (dimension): division, department,
employee, service, customer, supplier.

Nguồn đối chiếu: `src/db/models/dimension.py` (SQLAlchemy model đã chốt ở
bước 2.2) — schema ở đây PHẢI khớp kiểu dữ liệu/ràng buộc not-null với model
tương ứng, KHÔNG tự thêm cột/ràng buộc mới ngoài ERD
(`docs/architecture/erd-tuan-02.md`).

Quy ước áp dụng cho toàn bộ file trong module `import_schemas`:

- Cột `id`: file mẫu import kèm sẵn giá trị `id` (khoá chính) tường minh
  thay vì để DB tự autoincrement. Đây là lựa chọn kỹ thuật cho MVP/dữ liệu
  mẫu — giúp các bảng nghiệp vụ tham chiếu chéo (FK) dễ kiểm soát và test
  hơn. Dữ liệu export thật từ FT/AMIS nhiều khả năng dùng mã nghiệp vụ tự
  nhiên (VD mã khách hàng) thay vì `id` nội bộ — bước chuyển đổi mã nghiệp
  vụ → `id` nội bộ (lookup/upsert theo `code`/`name`) chưa nằm trong phạm vi
  bước 2.4, ghi nhận là việc cần làm thêm khi nối vào file export thật.
- Cột thời gian có `server_default` trong model (VD `customer.created_at`)
  KHÔNG khai báo trong schema và KHÔNG có trong file mẫu — để MySQL tự điền
  qua `server_default=func.now()` khi insert thiếu cột.
- `strict=True`: từ chối file có cột thừa ngoài danh sách khai báo (giúp
  phát hiện sớm file sai định dạng thay vì âm thầm bỏ qua cột lạ).
- `coerce=True`: Pandera tự ép kiểu dữ liệu về đúng kiểu khai báo và báo lỗi
  rõ ràng (kèm tên cột, vị trí dòng) nếu không ép được — thay cho việc tự
  viết code parse thủ công trong pipeline.
- Việc kiểm tra khoá ngoại (FK) có THỰC SỰ tồn tại trong bảng cha hay không
  KHÔNG nằm trong các schema này (Pandera chỉ thấy được 1 file, không có
  quyền truy vấn DB) — việc đó do `check_foreign_keys()` trong
  `src/services/import_pipeline.py` đảm nhiệm bằng query thật vào DB, theo
  đúng yêu cầu bước 2.4.
"""

from __future__ import annotations

import pandera.pandas as pa

from src.db.models.enums import CustomerClassification, StaffGroup

_STAFF_GROUP_VALUES = [g.value for g in StaffGroup]
_CLASSIFICATION_VALUES = [c.value for c in CustomerClassification]


division_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "name": pa.Column(str, nullable=False, checks=pa.Check.str_length(min_value=1)),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

department_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "name": pa.Column(str, nullable=False, checks=pa.Check.str_length(min_value=1)),
        "division_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

employee_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "full_name": pa.Column(
            str, nullable=False, checks=pa.Check.str_length(min_value=1)
        ),
        "department_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "staff_group": pa.Column(
            str, nullable=False, checks=pa.Check.isin(_STAFF_GROUP_VALUES)
        ),
        "position": pa.Column(str, nullable=True, required=False),
        "is_active": pa.Column(bool, nullable=False),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

service_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "name": pa.Column(str, nullable=False, checks=pa.Check.str_length(min_value=1)),
    },
    unique=["id", "name"],
    strict=True,
    coerce=True,
)

customer_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "code": pa.Column(str, nullable=False, checks=pa.Check.str_length(min_value=1)),
        "name": pa.Column(str, nullable=False, checks=pa.Check.str_length(min_value=1)),
        "source": pa.Column(str, nullable=True, required=False),
        "current_classification": pa.Column(
            str, nullable=False, checks=pa.Check.isin(_CLASSIFICATION_VALUES)
        ),
    },
    unique=["id", "code"],
    strict=True,
    coerce=True,
)

supplier_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "name": pa.Column(str, nullable=False, checks=pa.Check.str_length(min_value=1)),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)
