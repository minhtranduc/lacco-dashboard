# HD-09: Alembic 101 — quy trình migration an toàn

**Tuần:** 2 — Data layer (schema, migration, import) | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 22/08/2026

## Mục tiêu

Khởi tạo Alembic (công cụ quản lý version schema cho SQLAlchemy), sinh migration đầu tiên từ 18 model đã có ở bước 2.2, và chạy thật lên database MySQL "lacco" — kiểm chứng bằng cách đọc lại danh sách bảng thật trong DB, không chỉ tin log "thành công".

## Vì sao cần Alembic (giải thích nhanh)

SQLAlchemy models mô tả schema *mong muốn* trong code, nhưng không tự đồng bộ vào database thật. Alembic là công cụ chính thức đi kèm SQLAlchemy để quản lý *lịch sử thay đổi* schema — mỗi lần đổi cấu trúc bảng (thêm cột, đổi kiểu dữ liệu...) tạo ra 1 "migration" có thể chạy tiến (`upgrade`) hoặc lùi (`downgrade`), giúp biết chính xác DB đang ở phiên bản schema nào và đồng bộ được giữa nhiều môi trường (máy dev, máy demo...) mà không cần sửa bảng bằng tay.

## Quy trình đã dùng

1. **Cấu hình kết nối không hardcode mật khẩu** — tạo `.env` (không commit, đã có sẵn trong `.gitignore`) chứa thông tin kết nối MySQL thật, và `.env.example` (commit vào git, chỉ có tên biến + placeholder) làm mẫu cho người dùng sau.
2. **Kiểm tra DB đang rỗng trước khi migrate** — xác nhận database "lacco" không còn bảng nào (đã DROP 9 bảng thử nghiệm cũ từ trước bước 2.1) trước khi chạy migration đầu tiên, tránh migrate chồng lên dữ liệu cũ không mong muốn.
3. `alembic init migrations` — khởi tạo cấu trúc thư mục Alembic.
4. Sửa `migrations/env.py` để trỏ `target_metadata` về `Base.metadata` từ `src/db/models` (đã tạo ở bước 2.2) — đây là bước quan trọng nhất, thiếu bước này Alembic không biết schema mong muốn là gì.
5. `alembic revision --autogenerate -m "initial schema - 18 bang tu ERD"` — tự sinh migration từ chênh lệch giữa model và DB (DB rỗng → migration tạo mới toàn bộ 18 bảng).
6. Đối chiếu nội dung migration vừa sinh với `docs/architecture/erd-tuan-02.md` trước khi chạy thật.
7. `alembic upgrade head` — áp dụng migration lên database "lacco" thật.
8. **Xác minh bằng cách đọc lại danh sách bảng thật từ DB** (`SELECT table_name FROM information_schema.tables`), không chỉ tin thông báo "upgrade thành công" của Alembic.

## Lỗi gặp phải & cách xử lý

Mật khẩu MySQL chứa ký tự đặc biệt (`@` và `%`) làm hỏng cú pháp connection string khi Alembic đọc qua `alembic.ini` (`ConfigParser` hiểu nhầm `%` là ký tự interpolation của chính nó). Xử lý: URL-encode mật khẩu và tạo engine trực tiếp bằng `create_engine()` trong `env.py` thay vì để Alembic tự ghép chuỗi kết nối từ `alembic.ini`.

**Bài học kỹ thuật:** mật khẩu có ký tự đặc biệt (`@`, `%`, `:`, `/`...) cần được URL-encode khi đưa vào bất kỳ connection string dạng URL nào (không riêng Alembic) — nếu không sẽ gây lỗi parse khó đoán, đặc biệt với ConfigParser vốn đã tự dùng `%` cho mục đích khác.

**Lưu ý bảo mật riêng của lần này:** khi giải thích lỗi trên, mật khẩu thật đã bị dán nguyên văn vào cuộc trò chuyện báo cáo kết quả — dù không phải lỗi cố ý, đây là lời nhắc rằng khi mô tả lỗi liên quan đến giá trị nhạy cảm, nên mô tả *dạng* lỗi ("mật khẩu có ký tự đặc biệt gây lỗi parse") thay vì trích nguyên văn giá trị thật. Đã khuyến nghị đổi mật khẩu sau sự việc này.

## Kết quả thu được

Commit `7f27c1b` — 6 file (`.env.example`, `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/README`, file migration `02f963b388c8_initial_schema_18_bang_tu_erd.py`), 540 dòng. Đã xác minh trực tiếp: database "lacco" có đủ 19 bảng (18 bảng nghiệp vụ đúng như ERD + `alembic_version`) — không thiếu, không thừa. `.env` xác nhận không lọt vào git (kiểm tra bằng `git ls-files`).

## Bài học rút ra

- **Luôn kiểm tra DB đang ở trạng thái mong đợi trước khi chạy migration** (ở đây là "phải rỗng") — chạy autogenerate/upgrade mà không biết trạng thái DB hiện tại là rủi ro lớn nhất của Alembic, không phải bản thân câu lệnh.
- **Xác minh migration bằng cách đọc lại dữ liệu thật từ DB**, không dừng ở log "upgrade thành công" — nhất quán với nguyên tắc "xác minh trước khi tin" đã áp dụng xuyên suốt dự án (MCP ở HD-06, review ERD ở HD-07).
- **Ký tự đặc biệt trong mật khẩu là rủi ro kỹ thuật thật**, không chỉ lý thuyết — nên cân nhắc khi đặt mật khẩu cho các tài khoản dùng trong connection string, hoặc luôn nhớ URL-encode.

## Kết quả

Alembic đã cấu hình xong, migration đầu tiên đã chạy thành công lên database "lacco" thật — 18 bảng đúng theo ERD đã tồn tại, có lịch sử version (`alembic_version`). Sẵn sàng cho bước 2.4 (pipeline import Excel/CSV).
