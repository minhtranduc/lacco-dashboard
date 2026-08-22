"""Enum dùng chung giữa nhiều model, tách riêng để tránh import chéo giữa
`dimension.py`, `business.py` và `security.py`.

Chỉ chứa các enum đã "Đã rõ" về mặt nghiệp vụ (có danh sách giá trị cụ thể,
xác nhận trong CLAUDE.md hoặc `.claude/rules/trang-thai-yeu-cau.md`).

KHÔNG đặt ở đây các enum còn "cần xác nhận" danh sách giá trị — theo mục 1,
2, 8 của phần "Việc cần xác nhận trước khi sang bước 2.2" trong
`docs/architecture/erd-tuan-02.md` (`sales_order.status`, `invoice_status`,
`import_history.status`, `audit_log.action`). Các cột đó dùng kiểu `String`
placeholder ngay tại model tương ứng, không định nghĩa Enum ở đây để tránh
tự bịa danh sách giá trị.
"""

import enum


class StaffGroup(str, enum.Enum):
    """5 nhóm nhân sự dùng cho báo cáo Chi phí theo Nhóm.

    Nguồn: `.claude/rules/trang-thai-yeu-cau.md`, dòng "Chi phí | Theo Nhóm
    (LĐ/QL/Frontline/Middle/Backend)" — đã "Đã rõ", dùng nguyên nhóm nhân sự
    đã phân sẵn trong AMIS, không tự định nghĩa lại ranh giới 5 nhóm.
    """

    LEADERSHIP = "LĐ"
    MANAGEMENT = "QL"
    FRONTLINE = "Frontline"
    MIDDLE = "Middle"
    BACKEND = "Backend"


class CustomerClassification(str, enum.Enum):
    """Phân loại khách hàng A/B/C — dùng trực tiếp cho RBAC (CLAUDE.md mục 6).

    Nguồn: cột "Phân loại" có sẵn trong hệ thống FT — không tự định nghĩa lại
    ngưỡng xếp hạng, chỉ đọc giá trị có sẵn (đã "Đã rõ" 17/08/2026).
    """

    A = "A"
    B = "B"
    C = "C"


class UserRole(str, enum.Enum):
    """3 cấp quyền RBAC — đã chốt trong CLAUDE.md mục 6.

    Admin: quản trị hệ thống. Manager: chỉnh sửa/cập nhật dữ liệu và xem báo
    cáo. User: chỉ xem báo cáo.
    """

    ADMIN = "Admin"
    MANAGER = "Manager"
    USER = "User"
