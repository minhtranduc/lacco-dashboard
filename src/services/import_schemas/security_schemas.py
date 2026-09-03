"""Pandera schema cho nhóm bảng bảo mật/audit: users, login_history,
audit_log.

KHÔNG có schema cho `import_history` — bảng này do chính
`src/services/import_pipeline.py` tự ghi log sau mỗi lần import (thành
công hay thất bại), không nhận dữ liệu từ file import.

Ghi chú riêng cho `users.password_hash`: theo docstring model
`src/db/models/security.py`, việc hash mật khẩu bằng bcrypt PHẢI thực hiện
ở tầng `src/auth/` (chưa xây ở bước 2.4, dự kiến Tuần 3), KHÔNG phải trong
pipeline import (để tránh trộn logic auth vào tầng import). Vì vậy file dữ
liệu mẫu `users` chứa SẴN chuỗi bcrypt hash đã được tính trước lúc SINH dữ
liệu mẫu (xem `scripts/generate_synthetic_sample_data.py`) — với pipeline
import, cột này chỉ là 1 chuỗi ký tự bình thường như mọi cột khác, không có
xử lý đặc biệt gì thêm ở đây.
"""

from __future__ import annotations

import pandera.pandas as pa

from src.db.models.enums import UserRole

_ROLE_VALUES = [r.value for r in UserRole]


users_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "username": pa.Column(
            str, nullable=False, checks=pa.Check.str_length(min_value=1)
        ),
        "password_hash": pa.Column(
            str, nullable=False, checks=pa.Check.str_length(min_value=1)
        ),
        "role": pa.Column(str, nullable=False, checks=pa.Check.isin(_ROLE_VALUES)),
        # Nullable — xem mục 9 "Việc cần xác nhận" erd-tuan-02.md (giả định
        # tài khoản hệ thống không gắn nhân viên nghiệp vụ cụ thể).
        "employee_id": pa.Column(
            "Int64", nullable=True, required=False, checks=pa.Check.gt(0)
        ),
        "is_active": pa.Column(bool, nullable=False),
    },
    unique=["id", "username"],
    strict=True,
    coerce=True,
)

# login_at KHÔNG khai báo — model có server_default=func.now(), để MySQL tự
# điền khi insert thiếu cột.
login_history_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "user_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "ip_address": pa.Column(str, nullable=True, required=False),
        "success": pa.Column(bool, nullable=False),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)

# changed_at KHÔNG khai báo — model có server_default=func.now().
audit_log_schema = pa.DataFrameSchema(
    {
        "id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "user_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        # Placeholder tự do — danh sách giá trị cụ thể (VD create/update/
        # delete) CHƯA xác nhận, xem mục 8 "Việc cần xác nhận" trong
        # erd-tuan-02.md. KHÔNG tự bịa enum cho cột này.
        "action": pa.Column(
            str, nullable=False, checks=pa.Check.str_length(min_value=1)
        ),
        "table_name": pa.Column(
            str, nullable=False, checks=pa.Check.str_length(min_value=1)
        ),
        "record_id": pa.Column(int, nullable=False, checks=pa.Check.gt(0)),
        "old_value": pa.Column(str, nullable=True, required=False),
        "new_value": pa.Column(str, nullable=True, required=False),
    },
    unique=["id"],
    strict=True,
    coerce=True,
)
