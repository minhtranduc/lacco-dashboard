# HD-23: Backup/restore MySQL định kỳ

**Tuần:** 7 — Kiểm thử & triển khai | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 19–20/10/2026

## Mục tiêu

Trước khi coi hệ thống sẵn sàng vận hành thật, dữ liệu trong MySQL "lacco" cần có cơ chế sao lưu tự động và đã được kiểm chứng là khôi phục được — không chỉ "có chạy mysqldump" mà phải chứng minh bằng một lần restore thật, so khớp dữ liệu. Bước này cũng giải quyết một rủi ro đã nêu từ bước 7.2: app, MySQL và (nếu không cẩn thận) cả bản backup đều nằm chung một ổ cứng — ổ hỏng là mất tất cả.

## Giải thích khái niệm

- **`--single-transaction`:** cho phép `mysqldump` chụp một bản chụp dữ liệu nhất quán (consistent snapshot) của các bảng InnoDB mà không khoá bảng, nhờ đó backup chạy được ngay cả khi ứng dụng đang có người dùng, không gây gián đoạn.
- **Tài khoản backup least-privilege:** áp dụng lại đúng nguyên tắc đã dùng ở Fix B (bước 7.1, xem HD-21) — tài khoản dùng để sao lưu chỉ cần quyền đọc (`SELECT`, `LOCK TABLES`, `SHOW VIEW`, `EVENT`, `TRIGGER`), không có quyền ghi/sửa/xoá. Nếu máy chạy backup bị xâm nhập, kẻ tấn công có tài khoản này cũng không phá được dữ liệu.
- **Backup "offsite" (lưu ngoài máy chính):** một bản sao lưu chỉ có giá trị nếu nó không cùng chịu rủi ro với dữ liệu gốc. Lưu bản backup trên cùng ổ cứng với MySQL thật chỉ chống được lỗi logic (xoá nhầm bảng), không chống được hỏng ổ cứng/mất máy.

## Cách tiếp cận / Quy trình đã dùng

**Quyết định của COO trước khi làm (qua `AskUserQuestion`):**

- Nơi lưu bản backup thứ 2: dùng OneDrive đã đồng bộ sẵn trên máy (máy không có Google Drive).
- Tần suất: hằng tuần (không phải hằng ngày).

**Một prompt CLI thực hiện tuần tự, theo đúng nguyên tắc least-privilege đã dùng ở bước 7.1:**

| Hạng mục | Cách làm |
|---|---|
| Tài khoản MySQL cho backup | `lacco_backup`@`localhost`, chỉ `SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER` trên `lacco.*` |
| Script backup | `scripts/deploy/backup_mysql.ps1` — `mysqldump --single-transaction --routines --triggers --events --no-tablespaces` ra file `.sql`, nén `.zip` bằng `Compress-Archive` (có sẵn trong PowerShell), copy sang thư mục OneDrive, giữ 8 bản gần nhất ở cả 2 nơi |
| Lịch chạy | Task Scheduler, trigger *Weekly* Chủ Nhật 2:00 sáng, tài khoản `SYSTEM`, `-StartWhenAvailable` (chạy bù nếu máy tắt đúng giờ đó) |
| Test restore | Restore vào database tạm `lacco_restore_test` (KHÔNG đụng `lacco` thật), so `COUNT(*)` từng bảng, xoá database tạm sau khi so xong |

## Bảng lỗi và tình huống thật đã gặp

| # | Tình huống | Nguyên nhân | Cách xử lý / Bài học |
|---|---|---|---|
| 1 | Script tạo tài khoản `lacco_backup` báo `Access denied for user 'root'@'localhost'` | CLI (được giao việc) **không tự ý đọc mật khẩu root từ cấu hình MCP** khi gặp bước cần quyền root — đúng nguyên tắc, không lấy bí mật qua đường vòng. Thử nhập lại 1 lần vẫn lỗi tương tự | Reset mật khẩu root MySQL theo đúng quy trình chuẩn (dừng service → `mysqld --init-file` áp dụng `ALTER USER` → xoá init-file chứa mật khẩu dạng chữ thường → khởi động lại service). Mật khẩu mới lưu vào 1 file ngoài repo, **không in ra trong báo cáo gửi Cowork** — tránh lộ qua nội dung được dán lại vào chat |
| 2 | Vài tuần sau, thử tạo lại tài khoản backup vẫn báo `Access denied` dù mật khẩu root *đã* đổi thành công trước đó | COO dùng nhầm mật khẩu root **cũ** (trước lần reset) | CLI tra log `mysqld_reset.log` trước khi đổi root lần nữa — xác nhận lần reset trước đã thành công, nên **không reset lại** (đổi mật khẩu một tài khoản đang hoạt động tốt chỉ để thử là việc không nên làm). Bài học: khi một thao tác quản trị tưởng như lỗi, kiểm tra bằng chứng lịch sử trước khi lặp lại một hành động có tính phá huỷ (ở đây là đổi mật khẩu, làm mọi nơi khác dùng mật khẩu cũ ngừng hoạt động) |
| 3 | `redirect` (`>`) ra file `.sql` làm hỏng định dạng | PowerShell 5.1 mặc định ghi file redirect bằng UTF-16, trong khi `mysqldump`/MySQL cần UTF-8 | Dùng tham số `--result-file` của chính `mysqldump` thay vì redirect của shell |
| 4 | `mysqldump` báo thiếu quyền `PROCESS` khi dump | MySQL 8 mặc định cần quyền `PROCESS` để dump tablespace, nhưng tài khoản backup cố tình không có quyền này (least-privilege) | Thêm `--no-tablespaces` vào lệnh dump — không cần tablespace cho mục đích backup/restore logic thông thường |
| 5 | Sau khi push commit backup, CI kẹt ở trạng thái `queued` hơn 10 phút | Ban đầu nghi hết phút GitHub Actions miễn phí trong tháng. Kiểm tra billing: còn nguyên 2.000/2.000 phút — không phải nguyên nhân | Loại trừ lần lượt: không có run nào bị "treo" từ trước (`gh run list`), `ci.yml` không khai báo `concurrency` nên không bị run cũ chặn, Actions permissions bình thường. Cuối cùng xác nhận qua trang trạng thái GitHub (githubstatus.com): đang có sự cố `degraded_performance` cho Actions, mở ngay trước thời điểm run bị kẹt. Xử lý đúng: **không huỷ, không push lại, không ép `rerun`** — chỉ chờ GitHub tự khắc phục. Vài giờ sau, run tự chạy và pass bình thường khi không còn thao tác gì thêm |
| 6 | CI pass nhưng có 2 cảnh báo deprecation (Node.js 20 cho `actions/checkout@v4`/`setup-python@v5`; `ubuntu-latest` sắp đổi sang Ubuntu 26 từ 19/10/2026) | Hai action đã lên major version mới, cần Node 24; GitHub đang chuyển runner mặc định sang hệ điều hành mới hơn | Tra bản mới nhất thật bằng `gh api repos/actions/checkout/releases/latest` (không đoán số version) — ra `@v7`. Ghim cứng `runs-on: ubuntu-24.04` thay vì dùng nhãn `ubuntu-latest`, tránh bị đổi môi trường ngầm không báo trước |
| 7 | **Phát hiện phụ, không liên quan trực tiếp đến backup:** `ci.yml` thật vẫn chạy `pytest ... --cov=src/auth`, trong khi CLAUDE.md mục 5 đã ghi đúng là `--cov=src` từ bản v12 (23/09/2026) | Bản sửa v12 chỉ sửa **tài liệu tham khảo** trong CLAUDE.md, quên kiểm tra và sửa luôn **file workflow thật** có cùng lỗi. Hậu quả: suốt từ bước 7.1 đến nay, số liệu coverage hiển thị trên CI (90%) chỉ tính trên 126 dòng của `src/auth`, không phải trên toàn bộ 1.603 dòng của `src/` — con số đúng là 88%, như đã ghi trong các báo cáo trước | Sửa `ci.yml` khớp với CLAUDE.md. Bài học: khi một lỗi được phát hiện có ở nhiều nơi (tài liệu + code/cấu hình thật), sửa tài liệu không thay thế được việc sửa cấu hình thật — phải tự hỏi "lỗi này còn nằm ở đâu khác không", không dừng lại ở nơi đầu tiên tìm thấy |

## Kết quả thu được

- **Tài khoản MySQL:** `lacco_backup`@`localhost`, quyền `SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER` trên `lacco.*` — xác nhận qua `SHOW GRANTS`.
- **Backup thật đã chạy:** `lacco_20261019_223122.zip` (9.790 byte, nén từ file `.sql` 47 KB, 19 lệnh `CREATE TABLE` + 19 khối `INSERT`), có mặt ở cả `backups\` local và `D:\OneDrive\Backups\lacco-dashboard`, hai bản giống hệt nhau (cùng hash).
- **Test restore:** khớp tuyệt đối 19/19 bảng (ví dụ `users` 21 dòng, `login_history` 45 dòng, `sales_order` 40 dòng) giữa `lacco` và `lacco_restore_test`. Database tạm đã xoá sạch sau khi so.
- **Lịch chạy:** Scheduled Task "LACCO Dashboard Backup", trạng thái `Ready`, chạy Chủ Nhật 2:00 sáng, tài khoản `SYSTEM`, `StartWhenAvailable` đã bật.
- **Commit:** `fd2afdf` (script backup/restore, `.gitignore`, `.env.example`), `02ab732` (nâng cấp `actions/checkout@v7`/`actions/setup-python@v7`, ghim `ubuntu-24.04`, sửa `--cov=src`). CI xanh cho cả hai, không còn cảnh báo deprecation nào.
- **Coverage CI đúng:** 88% trên toàn bộ 1.603 dòng của `src/` (175/175 test pass) — khớp với số đã ghi trong CLAUDE.md và báo cáo bước 7.1.

## Bài học rút ra

- **"Sửa ở tài liệu" không phải lúc nào cũng là "sửa xong".** Lỗi `--cov=src/auth` đã được CLAUDE.md v12 ghi nhận và sửa đúng, nhưng vì chỉ sửa phần mô tả lệnh tham khảo trong tài liệu mà không rà lại chính file `ci.yml` đang chạy thật, lỗi gốc tồn tại thêm gần 1 tháng mà không ai biết — cho đến khi một việc khác (nâng cấp action) buộc phải mở lại đúng file đó. Khi phát hiện một lỗi cấu hình, luôn tự hỏi "lỗi này có nằm ở nơi nào khác đang chạy thật không", không chỉ sửa đúng một chỗ dễ thấy nhất.
- **Một con số "giảm" không phải lúc nào cũng là tin xấu.** Coverage báo giảm từ 90% xuống 88% sau khi sửa phạm vi đo — nhìn thoáng qua giống như thoái lui, nhưng thực chất là số liệu trước đó sai (đo thiếu phạm vi), số liệu sau mới đúng. Luôn hiểu rõ *vì sao* một chỉ số thay đổi trước khi phản ứng, thay vì mặc định "số giảm = có vấn đề".
- **Không phải sự cố nào cũng là lỗi của mình.** CI kẹt `queued` ban đầu giống hệt triệu chứng hết quota, nhưng tra đúng bằng chứng (billing, danh sách run, cấu hình `concurrency`, trang trạng thái GitHub) mới xác định đúng là sự cố phía GitHub. Phản ứng đúng với một sự cố hạ tầng ngoài tầm kiểm soát là **chờ có bằng chứng rõ ràng rồi mới hành động**, không phải thử các thao tác sửa lỗi (huỷ run, push lại, đổi cấu hình) một cách vội vàng — những thao tác đó có thể che mất nguyên nhân thật hoặc tạo thêm rối loạn.
- **Một thao tác quản trị có tính phá huỷ (đổi mật khẩu root) chỉ nên làm khi có bằng chứng nó thật sự cần thiết.** Lần thứ hai tưởng root "lại hỏng", kiểm tra log trước đã cho thấy lần reset trước vẫn còn hiệu lực — tránh được một lần đổi mật khẩu không cần thiết, vốn sẽ làm hỏng mọi kết nối khác đang dùng mật khẩu (vừa đổi) đúng.

## Kết quả

Bước 7.3 hoàn thành ngày 20/10/2026. MySQL "lacco" có cơ chế sao lưu tự động hằng tuần (mysqldump qua tài khoản least-privilege, nén, lưu 2 nơi — local và OneDrive, giữ 8 bản gần nhất), đã kiểm chứng khôi phục được bằng một lần restore thật khớp tuyệt đối 19/19 bảng. Quá trình làm phát hiện và xử lý thêm một lỗi cấu hình CI tồn đọng từ bước 7.1 (`ci.yml` đo coverage sai phạm vi) và nâng cấp 2 GitHub Action lên bản mới, loại bỏ toàn bộ cảnh báo deprecation.
