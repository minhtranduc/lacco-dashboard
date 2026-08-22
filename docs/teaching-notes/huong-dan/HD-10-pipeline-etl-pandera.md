# HD-10: Xây pipeline ETL nhẹ với Claude Code + Pandera

**Tuần:** 2 — Data layer (schema, migration, import) | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 22/08/2026

## Mục tiêu

Xây dựng 1 framework import dùng chung (không viết 18 hàm import riêng lẻ trùng lặp) cho toàn bộ 18 bảng trong ERD, validate dữ liệu bằng Pandera trước khi ghi vào MySQL, ghi log mọi lần import vào bảng `import_history`, và chứng minh pipeline báo lỗi rõ ràng thay vì nuốt lỗi âm thầm — bằng dữ liệu mẫu giả lập (synthetic), vì chưa có dữ liệu export thật từ FT/AMIS.

## Quy trình đã dùng

1. Giao việc cho agent general-purpose mang persona `data-import-agent.md` (đúng quy ước "general-purpose + dán nguyên văn persona" đã chốt từ HD-07 — không thử gọi theo tên).
2. Yêu cầu agent tự sinh dữ liệu mẫu synthetic cho 18 bảng, đúng thứ tự phụ thuộc khoá ngoại (danh mục trước, nghiệp vụ sau), đặt tên file tiền tố `synthetic_` để không nhầm với export thật.
3. Yêu cầu xây 1 framework import dùng chung (`src/services/import_pipeline.py`) nhận vào đường dẫn file + tên bảng đích + Pandera schema tương ứng, thay vì lặp code cho từng bảng.
4. Viết Pandera schema riêng theo nhóm bảng (`import_schemas/dimension_schemas.py`, `business_schemas.py`, `security_schemas.py`), validate kiểu dữ liệu, cột bắt buộc, và khoá ngoại tồn tại thật trong bảng cha (query DB, không chỉ kiểm tra kiểu).
5. Chạy import thật cho cả 18 bảng vào database "lacco", đồng thời cố ý tạo 2 file lỗi (`synthetic_department_LOI_FK.csv`, `synthetic_department_LOI_THIEU_COT.csv`) để demo pipeline từ chối dữ liệu sai thay vì âm thầm bỏ qua.
6. Với mục #10 còn treo từ ERD (thang điểm `supplier_evaluation.score` 0–100 hay 1–5) — agent **tự chọn thang 0–100** làm mặc định để có thể viết được Pandera Check, ghi rõ đây là giả định đang chờ COO xác nhận lại (không phải quyết định chính thức), không chặn tiến độ.
7. Sau khi agent báo cáo xong, tôi (Claude, qua kênh xác minh độc lập) tự chạy `SELECT COUNT(*)` cho cả 18 bảng và đọc trực tiếp `import_history` — không chỉ tin báo cáo của agent.

## Kết quả thu được

Commit `7d047c1` — 31 file, 2474 dòng thêm. Đã xác minh trực tiếp trên máy (không chỉ tin báo cáo agent):

| Nhóm | File |
|---|---|
| Subagent | `.claude/agents/data-import-agent.md` |
| Kết nối DB | `src/services/db_connection.py` (81 dòng) |
| Framework import | `src/services/import_pipeline.py` (578 dòng) |
| Pandera schema | `src/services/import_schemas/` — 4 file (dimension, business, security, registry — tổng 626 dòng) |
| Script hỗ trợ | `scripts/generate_synthetic_sample_data.py` (514 dòng), `scripts/run_synthetic_import_demo.py` (227 dòng) |
| Dữ liệu mẫu | `data/sample/` — 19 file (17 hợp lệ + 2 file lỗi cố ý) + README |

**Số dòng thực tế sau import (tự query, khớp 100% với báo cáo agent):** 18 bảng ERD đều có dữ liệu (từ 5 dòng ở `division` đến 40 dòng ở `sales_order`/`customer_classification_history`), `import_history` có 20 dòng log (1 dòng bootstrap + 17 lần import thành công + 2 lần import lỗi cố ý).

**Demo báo lỗi (2 trường hợp, đều `status=failed` trong `import_history`, không insert dòng sai vào bảng đích):**
- Thiếu cột bắt buộc: báo rõ dòng 3, cột `name`, loại lỗi `not_nullable`.
- Khoá ngoại không tồn tại: báo rõ dòng 3, cột `division_id`, giá trị `9999` không tồn tại trong bảng cha `division`.

**Bảo mật:** xác nhận `.env` không lọt vào git (`git status`, `.gitignore`), grep toàn bộ file mới không tìm thấy 2 chuỗi mật khẩu thật.

## Phát hiện thêm khi xác minh độc lập (ngoài báo cáo của agent)

Sau khi commit, `git status` cho thấy `.gitignore` và một số file `data/sample/*.csv` bị đánh dấu "modified" trên working tree. Kiểm tra kỹ (`git diff -b`, so byte đầu file) xác nhận đây **không phải thay đổi nội dung thật** — toàn bộ khác biệt chỉ là ký tự xuống dòng (line ending): file trong working tree dùng CRLF (`\r\n`, kiểu Windows), còn bản đã commit dùng LF (`\n`). Nội dung dữ liệu giống hệt nhau. Đây là hệ quả thường gặp khi công cụ sinh file (ví dụ `csv.writer` mở file ở chế độ text trên Windows) ghi CRLF trong khi git lưu LF. Không ảnh hưởng đến dữ liệu hay pipeline, nhưng nên chuẩn hoá (thêm `.gitattributes` quy định `* text=auto eol=lf`, hoặc `git checkout -- .` để đưa working tree về đúng bản đã commit) trước khi commit tiếp theo, để tránh những commit "toàn bộ file đổi" không cần thiết chỉ vì line ending.

## Bài học rút ra

- **Không nên viết 18 hàm import riêng biệt** — 1 framework dùng chung nhận schema Pandera làm tham số giúp code ngắn hơn nhiều lần và dễ bảo trì khi ERD có bảng mới.
- **Chủ động demo trường hợp lỗi** (không chỉ demo đường thành công) là cách duy nhất để thực sự tin "không nuốt lỗi âm thầm" — nếu chỉ chạy dữ liệu sạch, sẽ không bao giờ biết pipeline xử lý lỗi tốt hay tệ.
- **"Xác minh trước khi tin" bắt được cả những thứ báo cáo agent không sai nhưng không đầy đủ** — số dòng và commit đều đúng như agent báo, nhưng chỉ khi tự chạy `git status` mới phát hiện vấn đề line-ending tồn đọng trên working tree, thứ agent không có lý do để tự báo cáo vì không nằm trong phạm vi được giao.
- **Không phải mọi giả định phát sinh đều cần dừng lại chờ COO** — thang điểm `score` được tự chọn tạm 0–100 kèm ghi chú rõ ràng "đang chờ xác nhận lại", đúng nguyên tắc đã áp dụng nhất quán từ HD-07/HD-08: phân biệt được cái gì chặn tiến độ và cái gì không.

## Kết quả

Pipeline import Excel/CSV → Pandera → MySQL đã hoạt động thật, đã test cả đường thành công lẫn đường lỗi, `import_history` ghi log đầy đủ. Còn 2 việc nhỏ trước khi khép Tuần 2: (1) COO xác nhận lại thang điểm `supplier_evaluation.score` (0–100 hay 1–5), (2) chuẩn hoá line-ending trong repo để tránh commit thừa về sau. Sẵn sàng cho bước 2.5 (review & nhật ký Tuần 2).
