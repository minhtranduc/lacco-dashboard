# HD-06: Cấu hình MCP–MySQL — quy trình thực tế và các lỗi thường gặp

**Tuần:** 1 — Nền tảng & chốt yêu cầu | **Đối tượng phù hợp:** Chủ yếu IT/BA (có phần tóm tắt dành cho Lãnh đạo) | **Ngày thực hiện:** 17/08/2026

## Mục tiêu

Kết nối Claude Code CLI trực tiếp tới MySQL 8.0 cục bộ qua MCP (Model Context Protocol — chuẩn giao tiếp giúp AI gọi thẳng công cụ/nguồn dữ liệu ngoài, thay vì chỉ đọc văn bản người dùng dán vào) để Claude tự đọc schema/dữ liệu (chỉ SELECT) khi làm việc trong `src/services/`, `src/db/` — không cần dán thủ công cấu trúc bảng vào chat mỗi lần.

## Vì sao cần MCP thay vì dán tay

- Từ Tuần 2 trở đi, Claude Code sẽ liên tục cần biết tên bảng/cột thật để sinh code SQLAlchemy đúng — dán tay tốn thời gian và dễ dán nhầm/thiếu.
- MCP cho phép Claude tự kiểm tra schema hiện tại trước khi đề xuất thay đổi (migration Alembic), giảm rủi ro code sai lệch với DB thật.
- Gói dùng: `@benborla29/mcp-server-mysql` (cộng đồng — Anthropic không có server MySQL chính thức), mặc định **chỉ đọc** (SELECT), chặn INSERT/UPDATE/DELETE trừ khi chủ động bật cờ riêng.

## Quy trình thực tế đã đi qua — 6 lỗi, không phải quy trình lý tưởng

Cố tình ghi lại đầy đủ các lỗi gặp phải (không chỉ bản "đã sửa xong") vì đây là phần có giá trị học tập nhất của bước này.

| # | Lỗi gặp phải | Nguyên nhân | Cách phát hiện | Cách xử lý |
|---|---|---|---|---|
| 1 | `claude mcp list` (từ trong thư mục `lacco-dashboard`) không thấy server vừa thêm | Đăng ký server ở scope Local nhưng chạy lệnh `claude mcp add` khi đang đứng ở thư mục cha (`Lacco Dashboard`), không phải thư mục repo (`lacco-dashboard`) — scope Local gắn chặt với đúng thư mục lúc chạy lệnh | `claude mcp get <tên>` báo lỗi rõ ràng hơn `list` ("No MCP server named...") | Luôn `pwd`/xác nhận đúng thư mục gốc repo trước khi chạy `claude mcp add` |
| 2 | `Error: Access denied ... using password: NO` dù đã truyền mật khẩu | Đoán sai tên biến môi trường — dùng `MYSQL_PASSWORD`/`MYSQL_DATABASE` (tên "trực giác") trong khi gói `@benborla29/mcp-server-mysql` thực tế yêu cầu **`MYSQL_PASS`** và **`MYSQL_DB`** (viết tắt) | Đọc README thật của gói (`npm view @benborla29/mcp-server-mysql readme`) thay vì tin theo suy đoán/tài liệu tổng hợp bên ngoài | Dùng đúng tên biến đã xác minh từ README gốc |
| 3 | Biến môi trường không được áp dụng dù tên đúng | Đặt cờ `-e KEY=VALUE` SAU dấu `--` → bị coi là tham số của chính lệnh `npx`, không phải biến môi trường cho `claude mcp add` | So sánh `claude mcp get` — Args hiển thị đúng chuỗi nhưng hành vi thực tế vẫn dùng giá trị mặc định | `-e` phải đặt TRƯỚC dấu `--`: `claude mcp add mysql -s local -e KEY=VAL -- npx ...` |
| 4 | Đã sửa lệnh nhưng Claude Code vẫn báo không tìm thấy tool MCP mysql | Danh sách MCP tool chỉ được nạp lúc **khởi động phiên** — sửa cấu hình giữa chừng không tự nạp lại | Claude Code CLI tự báo "tools fetch failed — Connection closed" | Thoát và mở lại phiên CLI sau mỗi lần sửa cấu hình MCP |
| 5 | `ECONNREFUSED 127.0.0.1:3306` | MySQL server (service Windows `MySQL80`) đang ở trạng thái `Stopped` — không phải lỗi cấu hình mà do MySQL vật lý chưa chạy | PowerShell: `Get-Service`, `Get-Process`, `netstat -ano \| findstr ":3306"` | `Start-Service -Name "MySQL80"`; cân nhắc `Set-Service -StartupType Automatic` để khỏi lặp lại mỗi lần khởi động máy |
| 6 | Vẫn `Access denied` sau khi MySQL đã chạy | `MYSQL_PASS` bị để trống (rỗng) — không khớp mật khẩu thật đã đặt lúc cài MySQL | Test độc lập bằng `mysql.exe -u root -h 127.0.0.1 -P 3306 -p` trước khi sửa lại MCP, tránh restart CLI vô ích nếu vẫn sai | Nhập đúng mật khẩu thật; **quan trọng:** khi Claude Code CLI hỏi lại mật khẩu qua kênh hỏi-đáp thông thường, nó tự nhận diện đây là dữ liệu nhạy cảm và **từ chối nhận qua kênh đó** — yêu cầu người dùng tự gõ lệnh trực tiếp (tiền tố `!`, không qua ngữ cảnh mô hình) |

## Kết quả xác minh cuối cùng

`claude mcp get mysql` báo `Connected` — nhưng trạng thái này **chỉ xác nhận tiến trình MCP khởi động được**, không xác nhận kết nối thật tới database. Bước xác minh bắt buộc: chạy một câu SELECT thật qua tool `mcp__mysql__mysql_query`:

```sql
SELECT table_name FROM information_schema.tables WHERE table_schema = 'lacco';
```

Kết quả: 9 bảng đã tồn tại (`department`, `division`, `employee`, `users`, `loginhistory`, `passwordhistory`, `userlog`, `importhistory`, `weeklysales`) — cần xác nhận nguồn gốc các bảng này trước khi Tuần 2 bắt đầu thiết kế schema mới, tránh ghi đè nhầm dữ liệu không thuộc dự án.

## Bài học rút ra

- **"Connected" ≠ "kết nối được tới dữ liệu thật".** `claude mcp list`/`get` chỉ xác nhận tiến trình MCP (stdio process) khởi động — luôn xác minh bằng 1 câu query thật trước khi coi bước cấu hình là xong.
- **Tên biến môi trường của gói MCP cộng đồng có thể khác tên "trực giác"** — luôn đọc README thật của gói, không suy đoán hay tin tuyệt đối vào tài liệu tổng hợp (kể cả do AI tra cứu hộ).
- **Scope "Local" gắn chặt với thư mục làm việc lúc chạy lệnh** — chạy sai thư mục là lỗi âm thầm, lệnh vẫn báo "thành công" nên rất dễ bỏ sót.
- **Sau khi thêm/sửa MCP server, phải restart phiên Claude Code CLI** — danh sách tool MCP không tự nạp lại giữa chừng.
- **Mật khẩu không nên đi qua các kênh có thể bị ghi vào lịch sử/log của AI** (kể cả câu hỏi dạng lựa chọn) — việc Claude Code CLI chủ động từ chối và yêu cầu người dùng tự gõ lệnh trực tiếp là hành vi bảo mật đúng, nên tôn trọng thay vì tìm cách "lách".
- **Output thô của `claude mcp get` có thể echo mật khẩu dạng plaintext ra terminal** — cẩn trọng khi copy/paste output này ra ngoài (kể cả dán cho một phiên Claude khác), tránh dán nguyên văn output chưa qua tóm tắt/che giấu.

## Việc cần làm sau (không chặn Tuần 2)

- Trước khi vào Tuần 3 (RBAC thật, có thể nhiều người dùng hệ thống), nên tạo user MySQL riêng chỉ có quyền `SELECT` trên database `lacco` (thay vì dùng `root`) — giảm rủi ro nếu công cụ truy vấn sau này không giới hạn nghiêm ngặt như MCP hiện tại:

```sql
CREATE USER 'lacco_readonly'@'localhost' IDENTIFIED BY '<mật khẩu khác>';
GRANT SELECT ON lacco.* TO 'lacco_readonly'@'localhost';
FLUSH PRIVILEGES;
```

- Xác nhận nguồn gốc 9 bảng đã có sẵn trong database `lacco` trước khi Tuần 2 bắt đầu tạo bảng mới.

## Kết quả

MCP server "mysql" đã kết nối thành công (scope Local, không lên Git, mật khẩu không đi qua chat), xác minh bằng query thật qua `mcp__mysql__mysql_query`. Từ Tuần 2 trở đi, Claude Code có thể tự đọc schema MySQL trực tiếp trong các phiên làm việc thuộc phạm vi `src/services/`, `src/db/`, `docs/requirements/`.
