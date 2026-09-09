# System Design Document — LACCO Dashboard (Giai đoạn 1)

> Tài liệu này là **SDD sống** (`docs/architecture/`, xem CLAUDE.md mục 2) — phản ánh hệ thống THỰC TẾ tại thời điểm cập nhật cuối, không phải bản thiết kế lý thuyết ban đầu. Cập nhật lần này: 09/09/2026, sau bước 5.2 (đồng bộ tài liệu), phản ánh trạng thái tới hết bước 5.1.
>
> Quan hệ với các tài liệu khác: `docs/architecture/erd-tuan-02.md` là biên bản quyết định ERD gốc (bước 2.1, còn nguyên giá trị lịch sử, có danh sách đầy đủ các giả định kỹ thuật kèm ngày/lý do — SDD này KHÔNG lặp lại toàn bộ nội dung đó, chỉ tóm tắt và dẫn chiếu). `CLAUDE.md` là "luật gốc" cho subagent (tách lớp, RBAC, công thức đã chốt). `Archive/System_Design_Document_Dashboard_LACCO.docx` và `Tai_lieu_Kien_truc_He_thong.docx` (thư mục gốc, ngoài repo git) là tài liệu SDD/kiến trúc GỐC từ trước khi redesign ERD (bước 2.1) — đã lỗi thời về schema/module, chỉ còn giá trị tham khảo danh mục KPI ban đầu (xem HD-16, HD-17), KHÔNG dùng làm chuẩn đối chiếu kỹ thuật nữa.

## 1. Tổng quan

Dashboard hỗ trợ ra quyết định cho Ban Lãnh đạo Công ty LACCO (Logistics & Giao nhận vận tải), Giai đoạn 1 (8 tuần, WebApp nội bộ). Ứng dụng Streamlit đọc dữ liệu tổng hợp từ 2 hệ thống nguồn (FT — vận hành/kinh doanh, AMIS — tài chính/nhân sự), lưu trong 1 kho dữ liệu MySQL riêng (không ghi ngược lại FT/AMIS), hiển thị báo cáo theo 6 nhóm nghiệp vụ với phân quyền 3 cấp.

Phạm vi Giai đoạn 1 (theo `Ke_hoach_Trien_khai_Dashboard_LACCO_voi_Claude.docx` mục 8): 6/6 nhóm báo cáo hoạt động, RBAC 3 cấp đúng theo Khối/Phòng/phân loại KH, có audit trail (login/thay đổi dữ liệu), có bộ tài liệu case study đi kèm. **CRM** và **Dòng tiền** đã chốt dời sang Giai đoạn 2 (xác nhận 17/08/2026, bước 1.3) — không thuộc phạm vi tài liệu này.

## 2. Kiến trúc 3 lớp

```
src/
├── db/           # Model SQLAlchemy thuần (KHÔNG chứa logic nghiệp vụ)
│   └── models/   # dimension.py, business.py, security.py, enums.py, base.py
├── services/     # TOÀN BỘ logic tính KPI + truy vấn SQLAlchemy (parameterized)
├── auth/         # Đăng nhập (bcrypt), tính DataScope (RBAC)
└── app/          # Streamlit — CHỈ gọi hàm service rồi vẽ Plotly, không SQL/tính toán tại chỗ
    ├── main.py   # Đăng nhập, session, điều hướng
    └── pages/    # 1 file/module báo cáo (multi-page convention của Streamlit)
migrations/       # Alembic — versioned schema
scripts/          # generate_synthetic_sample_data.py (dữ liệu mẫu dev), import pipeline
docs/
├── requirements/     # tài liệu nghiệp vụ gốc (RACI, yêu cầu thu thập)
├── architecture/     # SDD (tài liệu này), erd-tuan-02.md — cập nhật dần
└── teaching-notes/   # nhật ký học tập + HD-0x — KHÔNG chứa logic dự án
```

Nguyên tắc tách lớp (CLAUDE.md mục 2) là ràng buộc **bắt buộc** với mọi subagent viết code báo cáo — vi phạm phổ biến nhất từng gặp là viết SQL/tính KPI trực tiếp trong trang Streamlit thay vì service.

## 3. Tech stack

| Thành phần | Công nghệ |
|---|---|
| UI | Streamlit 1.46 + streamlit-authenticator (đăng nhập) |
| ORM / DB | SQLAlchemy 2.0 (Mapped/mapped_column) + MySQL (mysql-connector-python) |
| Migration | Alembic |
| Validate dữ liệu import | Pandera |
| Mật khẩu | bcrypt |
| Log | Loguru (cấm `print()` trong `src/`) |
| Biểu đồ | Plotly Express (line=xu hướng, bar/bar-100%=so sánh, không dùng pie khi nhiều hạng mục) |
| Test | pytest + pytest-cov, SQLite in-memory cho CI (không cần MySQL thật) |
| Lint | ruff |
| CI | GitHub Actions (`.github/workflows/ci.yml`) — lint (`ruff check`) + test trên mọi push/PR vào `main`/`dev` |

**Khoảng trống test quan trọng:** CI hiện chỉ đo coverage cho `src/auth` (`--cov=src/auth`) — toàn bộ `src/services/report_*.py` (6 module) và `src/app/` **chưa có test tự động nào chạy trong CI**, chỉ được xác minh thủ công qua smoke test (`streamlit.testing.v1.AppTest`) mỗi lần build, không lặp lại tự động khi code sau đổi. Đây là rủi ro hồi quy thực sự, ghi nhận lại ở mục 9.

## 4. Mô hình dữ liệu (tóm tắt — chi tiết đầy đủ ở `erd-tuan-02.md`)

18 bảng, 3 nhóm (`src/db/models/`):

- **Dimension** (6 bảng, `dimension.py`): `division` → `department` → `employee` (phân cấp RBAC Khối/Phòng/NV), `service`, `customer` (có `current_classification` A/B/C dùng trực tiếp cho RBAC), `supplier`.
- **Business/fact** (8 bảng, `business.py`): `sales_order` (đơn hàng — doanh thu/lãi lỗ, tình trạng đơn/hoá đơn), `price_request` + `supplier_evaluation` (Pricing), `cost` + `budget` + `personnel_cost` (Chi phí), `debt` (Công nợ), `customer_classification_history` (lịch sử A/B/C theo thời gian).
- **Security/audit** (4 bảng, `security.py`): `users`, `login_history`, `audit_log`, `import_history` — bắt buộc ghi mọi phiên đăng nhập và mọi thay đổi dữ liệu (CLAUDE.md mục 6).

**Lưu ý thiết kế đáng chú ý:**
- `debt` lưu cả `division_id` VÀ `department_id` độc lập (không suy qua `department.division_id`) — quyết định kỹ thuật để truy vấn nhanh Khối→Phòng→KD không cần join, **chưa COO xác nhận chính thức** (mục #5, `erd-tuan-02.md`); dữ liệu mẫu đảm bảo 2 cột luôn nhất quán (xem mục 9, sự cố `gen_debt()`).
- `sales_order.status`/`invoice_status` và `import_history.status`/`audit_log.action` dùng `String` placeholder — danh sách giá trị enum đầy đủ **chưa được xác nhận chính thức** với Vận hành, cố tình không định nghĩa `Enum` cứng để tránh tự bịa giá trị.
- `personnel_cost` KHÔNG có FK tới employee/division/department (tổng hợp toàn công ty) — hệ quả RBAC: không thể lọc theo scope, xem mục 5.

## 5. RBAC 3 cấp

`src/auth/scope.py::compute_data_scope(user_id)` trả về `DataScope` (dataclass): `role`, `employee_id`/`department_id`/`division_id`, `customer_ids` (frozenset), `unrestricted` (bool), `classification_hint`.

| Role | Phạm vi | Cơ chế |
|---|---|---|
| **Admin** | Toàn bộ, `unrestricted=True` | COO xác nhận 25/08/2026: bỏ qua hoàn toàn `employee_id` khi giới hạn — khác Manager/User |
| **Manager** | Theo `department_id` (KH loại B) | `fetch_customer_ids_for_department()` |
| **User** | Theo `employee_id` (KH loại C) | `fetch_customer_ids_for_employee()` |

`customer_ids` được suy luận bằng UNION `customer_id` từ `sales_order`/`debt`/`price_request` theo employee/department — đây là **giả định kỹ thuật chưa COO xác nhận chính thức** (`customer` không có cột `employee_id` trực tiếp trong ERD), cần thiết để middleware chạy được từ bước 3.1.

**Mẫu RBAC khi bảng không có `customer_id` là chủ thể chính** (áp dụng từ bước 5.1, 4 module mới):
- Pricing (`price_request`/`supplier_evaluation`): lọc theo `employee_id`/`department_id` của NHÂN VIÊN phụ trách, không theo customer.
- Chi phí "Theo Khối" (`cost`/`budget`, có `division_id`): Admin/Manager theo `division_id`, **User bị ẩn hẳn** (không có dữ liệu cấp nhân viên).
- Chi phí "Theo Nhóm nhân sự" (`personnel_cost`, không FK): **chỉ Admin xem được** — Manager/User: service raise `PermissionError`, UI ẩn hẳn tab dựa trực tiếp vào `scope.unrestricted` (không dựa vào bắt exception — đó chỉ là phòng vệ tầng 2).
- Công nợ (`debt`, có sẵn cả 3 cột `division_id`/`department_id`/`employee_id`): lọc trực tiếp theo các cột này, không qua UNION customer.

## 6. Bảo mật

- Mật khẩu: bcrypt, hash tại `src/auth/`, không hash trong `src/db/`.
- Mọi phiên đăng nhập (kể cả thất bại) → `login_history`. Mọi thay đổi dữ liệu → `audit_log`.
- **Rủi ro bảo mật nghiêm trọng nhất dự án** (CLAUDE.md mục 6): mọi `@st.cache_data` PHẢI nhận tham số gắn `user_id`/`role_value` — cache theo instance ứng dụng (không theo session) nên thiếu tham số này gây rò dữ liệu chéo người dùng. Audit độc lập bước 4.2 xác nhận 9/9 hàm cache trong 2 module đầu tuân thủ đúng; các module bước 5.1 review trực tiếp cũng tuân thủ đúng mẫu.
- Backlog bảo mật tồn đọng (chưa cấp bách trong Giai đoạn 1, xem mục 9): `.env` vẫn dùng `root` MySQL (chưa tạo user least-privilege); `_DEV_FALLBACK_COOKIE_KEY` trong `authentication.py` fallback âm thầm thay vì raise lỗi.

## 7. 6 module báo cáo (trạng thái tại 09/09/2026)

| Module | Service | Trang | RBAC | Bước |
|---|---|---|---|---|
| Kinh doanh | `report_kinh_doanh.py` | `1_Bao_cao_Kinh_doanh.py` | theo `customer_ids` | 4.1, 4.3 |
| Khách hàng | `report_khach_hang.py` | `2_Bao_cao_Khach_hang.py` | theo `customer_ids` | 4.1 |
| Đơn hàng | `report_don_hang.py` | `3_Bao_cao_Don_hang.py` | theo `customer_ids` | 5.1 |
| Pricing | `report_pricing.py` | `4_Bao_cao_Pricing.py` | theo nhân viên phụ trách | 5.1 |
| Chi phí | `report_chi_phi.py` | `5_Bao_cao_Chi_phi.py` | theo Khối (User bị ẩn); Theo Nhóm chỉ Admin | 5.1 |
| Công nợ | `report_cong_no.py` | `6_Bao_cao_Cong_no.py` | trực tiếp theo Khối/Phòng/NV của `debt` | 5.1 |

KPI/công thức chi tiết từng module: xem `.claude/rules/trang-thai-yeu-cau.md` (nguồn sự thật cho công thức "Đã rõ"/"Cần làm rõ") và CLAUDE.md mục 7 (quyết định áp dụng chung mọi module).

## 8. Quyết định nghiệp vụ đã chốt (áp dụng cho MỌI module liên quan)

| Quyết định | Ngày | Nguồn |
|---|---|---|
| Đơn `sales_order.status="Huỷ"` loại trừ khỏi mọi tổng doanh thu/lãi lỗ (KHÔNG áp dụng cho báo cáo đếm trạng thái như "Tình trạng đơn hàng") | 07/09/2026 | COO, `AskUserQuestion`, bước 4.1 |
| Nhóm theo Tháng/Tuần cho biểu đồ xu hướng dùng ISO week (MySQL `%x-%v`, tuần bắt đầu Thứ Hai), không theo quy ước AMIS/FT riêng | 07/09/2026 | COO, `AskUserQuestion`, bước 4.3 |
| Admin luôn xem toàn bộ dữ liệu, không giới hạn theo Khối/Phòng dù có gắn `employee_id` | 25/08/2026 | COO, bước 3.1 |
| `supplier_evaluation.score` thang điểm 0–100 | 22/08/2026 | COO, bước 2.4 |
| FT và AMIS dùng chung 1 bộ mã Khối/Phòng/NV/KH — FK trực tiếp, không cần bảng mapping trung gian | 22/08/2026 | COO, bước 2.1 |
| Aging bucket Công nợ (0-30/31-60/61-90/>90 ngày) tính ĐỘNG tại thời điểm xem, không lưu snapshot | 09/09/2026 | COO, `AskUserQuestion`, bước 5.1 |
| RBAC Chi phí "Theo Khối": Admin/Manager theo Khối/Phòng mình, User bị ẩn hẳn | 09/09/2026 | COO, `AskUserQuestion`, bước 5.1 |
| RBAC Chi phí "Theo Nhóm nhân sự": chỉ Admin | 09/09/2026 | COO, `AskUserQuestion`, bước 5.1 |
| CRM và Dòng tiền dời sang Giai đoạn 2 | 17/08/2026 | COO, bước 1.3 |

## 9. Vấn đề/giả định kỹ thuật còn mở (chưa chặn tiến độ Giai đoạn 1)

Tổng hợp từ `erd-tuan-02.md` (8/10 mục gốc còn mở) + phát sinh từ bước 5.1:

1. Danh sách đầy đủ giá trị `sales_order.status` khác "Huỷ" — chờ Trưởng phòng Vận hành.
2. `invoice_status` là field độc lập hay 1 giá trị trong cùng quy trình `status`? — chờ xác nhận.
3. Tần suất snapshot `customer_classification_history` — chờ xác nhận.
4. `debt` lưu cả `division_id`+`department_id` độc lập — chấp nhận rủi ro lệch hay bỏ 1 cột? (dữ liệu mẫu hiện luôn nhất quán sau khi sửa lỗi `gen_debt()`, xem bên dưới).
5. `price_request.customer_id` nullable vì báo giá cho KH tiềm năng — giả định chưa xác nhận; ranh giới CRM cần giữ nguyên (không mở rộng bảng này thành lưu lead).
6. `import_history.status`, `audit_log.action` — danh sách enum cụ thể chưa chốt.
7. `users.employee_id` nullable (tài khoản hệ thống không gắn nhân viên) — giả định chưa xác nhận.
8. Rủi ro nhân viên đổi phòng ban theo thời gian: dữ liệu Pricing/Chi phí tính theo phòng ban HIỆN TẠI của nhân viên, không có snapshot lịch sử — nếu 1 nhân viên từng đổi phòng, số liệu quá khứ hiển thị theo phòng mới, không phải phòng lúc phát sinh giao dịch.
9. Nhóm "Chưa đến hạn" (`aging_days <= 0`) trong Công nợ là giải pháp kỹ thuật tạm — cách hiển thị cụ thể (gộp chung 1 bucket riêng hay ẩn khỏi báo cáo aging) chưa xác nhận với COO.
10. **Đã xử lý, chỉ ghi nhận lịch sử:** lỗi bộ sinh dữ liệu mẫu `gen_debt()` (`division_id`/`department_id` từng sinh độc lập với `employee_id`, gây lệch ~87% dữ liệu mẫu) — đã sửa và xác minh 0/30 lệch, xem HD-15 phần bổ sung bước 5.1. Đây KHÔNG phải vấn đề dữ liệu thật (chỉ ảnh hưởng dữ liệu mẫu dev), nhưng là lời nhắc: mọi cột suy luận qua nhiều bảng cần kiểm tra tính nhất quán khi sinh dữ liệu mẫu mới.

## 10. Testing & CI

`tests/conftest.py` — fixture SQLite in-memory (không cần MySQL thật khi chạy CI). `ci.yml`: `ruff check src/ tests/ scripts/` + `pytest tests/ -v --cov=src/auth`. Coverage hiện CHỈ đo `src/auth` — xem mục 3 về khoảng trống test ở `src/services/report_*.py`.

RBAC được xác minh THẬT (không chỉ qua code) ở bước 4.1 (đăng nhập UI thật + đối chiếu độc lập bằng gọi trực tiếp `compute_data_scope()`) và bước 4.2 (audit cache multi-user bởi `qa-reviewer-agent`, độc lập với người viết code).

## 11. Tài liệu liên quan

- `CLAUDE.md` — luật gốc cho mọi subagent (tách lớp, RBAC, công thức đã chốt, quy ước chạy multi-agent).
- `.claude/rules/trang-thai-yeu-cau.md` — trạng thái "Đã rõ"/"Cần làm rõ" từng công thức báo cáo, tự nạp khi làm việc trong `src/services/`.
- `docs/architecture/erd-tuan-02.md` — biên bản quyết định ERD gốc, đầy đủ lý do từng giả định kỹ thuật.
- `docs/teaching-notes/huong-dan/HD-0x-*.md` — nhật ký kỹ thuật chi tiết từng bước (lỗi thật gặp phải, cách xử lý).
- `docs/teaching-notes/tuan-0x.md` — nhật ký tổng kết từng tuần.
