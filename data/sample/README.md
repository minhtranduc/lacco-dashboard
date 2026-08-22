# Dữ liệu mẫu — data/sample/

**TOÀN BỘ file trong thư mục này là dữ liệu SYNTHETIC (giả lập)**, sinh bởi
`scripts/generate_synthetic_sample_data.py` (bước 2.4, `data-import-agent`).

- KHÔNG phải số liệu tài chính/khách hàng thật của LACCO.
- KHÔNG phải định dạng export thật từ hệ thống FT hoặc AMIS — chỉ là dữ
  liệu mẫu để test pipeline import (`src/services/import_pipeline.py`).
- Mọi tên khách hàng/nhà cung cấp/nhân viên đều có hậu tố "Demo" và mã số
  thứ tự (VD "Công ty TNHH Khách Hàng Demo 01") — không trùng với bất kỳ
  đối tượng thật nào một cách cố ý.
- Tên file có tiền tố `synthetic_` để không ai nhầm là file gốc từ FT/AMIS.
- Giá trị các cột "placeholder" (`sales_order.status`, `invoice_status`,
  `audit_log.action`) chỉ mang tính minh hoạ — KHÔNG phải danh sách enum
  chính thức đã được COO/Trưởng phòng Vận hành xác nhận (xem mục "Việc cần
  xác nhận" trong `docs/architecture/erd-tuan-02.md`).
- `synthetic_users.csv.password_hash`: bcrypt hash của 1 mật khẩu giả định
  dùng chung `Synthetic@123!` cho MỌI user mẫu — KHÔNG phải mật khẩu thật,
  không dùng để đăng nhập hệ thống thật.

## File demo lỗi cố ý (`synthetic_department_LOI_*.csv`)

2 file `synthetic_department_LOI_THIEU_COT.csv` và
`synthetic_department_LOI_FK.csv` KHÔNG thuộc bộ 17 file dữ liệu mẫu cho 18
bảng — đây là file demo cố tình chứa lỗi (thiếu cột bắt buộc / khoá ngoại
không tồn tại) để chứng minh `src/services/import_pipeline.py` báo lỗi rõ
ràng, không nuốt lỗi âm thầm (xem `scripts/run_synthetic_import_demo.py`).
KHÔNG dùng 2 file này khi import dữ liệu mẫu thật cho `department`.

Để sinh lại (ghi đè) toàn bộ file trong thư mục này:

```bash
python scripts/generate_synthetic_sample_data.py
```

Để chạy demo import thật (đọc file ở đây → validate → load vào MySQL
"lacco"), xem `scripts/run_synthetic_import_demo.py`.
