# HD-08: Pattern sinh code ORM chuẩn với Claude Code

**Tuần:** 2 — Data layer (schema, migration, import) | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 22/08/2026

## Mục tiêu

Từ ERD đã chốt (`docs/architecture/erd-tuan-02.md`, 18 bảng), sinh code SQLAlchemy declarative models đầy đủ tại `src/db/models/`, đúng chuẩn PEP8/docstring theo CLAUDE.md, và xử lý đúng cách các mục thiết kế còn "cần xác nhận" — không để AI tự bịa giá trị khi thiếu thông tin.

## Quy trình đã dùng

1. Giao việc trực tiếp cho agent general-purpose mang persona `db-schema-agent.md` (xem HD-07 — đây là quy ước chính thức, không còn thử gọi subagent theo tên nữa).
2. Yêu cầu tự đề xuất cách chia file trước khi viết — agent chọn chia theo nhóm chức năng thay vì 1 file/bảng: `base.py` (Base declarative + mixin chung), `enums.py` (các Enum dùng chung), `dimension.py` (6 bảng danh mục), `business.py` (8 bảng nghiệp vụ), `security.py` (4 bảng bảo mật/audit), `__init__.py` (export tổng hợp).
3. Với các cột thuộc 9 mục "cần xác nhận" trong ERD (VD: `sales_order.status`, `import_history.status`) — bắt buộc dùng kiểu placeholder hợp lý kèm docstring trích đúng số mục ERD, không tự đoán danh sách giá trị.
4. Với `debt.aging_bucket` — theo đúng nguyên tắc tách lớp CLAUDE.md mục 2 (logic không nằm trong `src/db/`), **không tạo cột vật lý**, chỉ ghi chú việc tính toán sẽ nằm ở `src/services/` khi đến bước đó.
5. Sau khi viết xong, agent tự review lại theo đúng nguyên tắc trong `db-schema-agent.md` trước khi báo cáo.

## Kết quả thu được

Commit `3e99175` — đã xác minh trực tiếp trên máy (không chỉ tin báo cáo agent): 6 file, 871 dòng.

| File | Số dòng | Nội dung |
|---|---|---|
| `base.py` | 17 | Declarative Base + mixin chung |
| `enums.py` | 54 | Enum dùng chung giữa các model |
| `dimension.py` | 207 | 6 bảng danh mục |
| `business.py` | 343 | 8 bảng nghiệp vụ |
| `security.py` | 185 | 4 bảng bảo mật/audit |
| `__init__.py` | 65 | Export tổng hợp |

Xác minh trực tiếp file `business.py`: không có cột `aging_bucket` vật lý trong `Debt` (đúng yêu cầu), các placeholder trích đúng số mục ERD, FK có index đầy đủ, docstring rõ ràng cho mọi class.

## Phát sinh mới ngoài 9 mục ERD gốc (đã cập nhật vào `erd-tuan-02.md`)

- `period` (trên các bảng `cost`, `budget`, `personnel_cost`, `supplier_evaluation`) chọn kiểu `Date` — chấp nhận làm mặc định, không cần xác nhận thêm (không phá schema dù tần suất thật khác).
- `supplier_evaluation.score` dùng `Numeric(5,2)` nhưng chưa rõ thang điểm 0–100 hay 1–5 — thêm thành mục **#10** trong danh sách "cần xác nhận", không chặn bước 2.3, chỉ cần chốt trước khi `data-import-agent` viết validate ở bước 2.4.
- Agent tự thêm `unique=True` cho `service.name`, `customer.code`, `users.username` — ràng buộc kỹ thuật hợp lý, chấp nhận.

## Bài học rút ra

- Để AI tự đề xuất cách chia file trước khi viết (thay vì áp đặt sẵn) cho kết quả tổ chức code hợp lý hơn dự kiến ban đầu (chia theo nhóm chức năng, không phải 1 file/bảng rời rạc).
- Nguyên tắc "trích dẫn rõ nguồn khi thiếu thông tin, không tự bịa" đã áp dụng đúng ở tầng ERD (HD-07) tiếp tục phát huy hiệu quả ở tầng code — placeholder có comment trỏ về đúng mục ERD giúp việc theo dõi "cái gì đã chốt, cái gì còn treo" không bị đứt gãy giữa tài liệu thiết kế và code thật.
- Không phải mọi quyết định kỹ thuật phát sinh khi code đều cần dừng lại hỏi COO — phân biệt được quyết định thuần kỹ thuật không ảnh hưởng nghiệp vụ (kiểu `period`) với quyết định cần input nghiệp vụ thật (thang điểm `score`) giúp tiến độ không bị chặn không cần thiết.

## Kết quả

`src/db/models/` đã có đầy đủ 18 bảng dưới dạng SQLAlchemy declarative models, sẵn sàng cho bước 2.3 (Alembic). Còn 1 mục kỹ thuật mới (thang điểm `supplier_evaluation.score`) cần chốt trước bước 2.4, không chặn bước 2.3.
